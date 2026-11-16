"""Step 1 - EME: how long must the multimode section be?  Transmission of the splitter against its length.

Model: the splitter of devices/mmi1x2_builder.py with a straight lead at each port, written to GDS and
loaded into a Layer Builder with gsip_process.lbr.

                         ┌────────────┐◁══ port 2       group 1   input lead               1 cell
        port 1 ══▷       │            │                 group 2   input taper              --cells cells, CVCS
                         └────────────┘◁══ port 3       group 3   multimode section        1 cell
                                                        group 4   output tapers            --cells cells, CVCS
                                                        group 5   output leads             1 cell

EME finds the modes of every cell once.  A different length of group 3 only changes the phase each mode
collects there, so the whole length sweep costs one mode calculation.

The whole cross-section is solved, with three ports: one mode port on the input, one on each output.

    1. the device as drawn:  power into each output, power reflected, and the field
    2. length sweep:  the same numbers against the length of the multimode section
    3. convergence:  the same sweep with fewer modes (--check)

    python mmi_length_eme.py
    python mmi_length_eme.py --modes 40 --check

Output in 1_mmi_length/:  mmi1x2.gds / .lms, mmi_length.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    LAM,
    LEAD,
    LENGTH_MMI,
    LENGTH_TAPER,
    OUTPUT_Y,
    WIDTH_MMI,
    add_layer_builder,
    import_lumapi,
    layout_gds,
    require_process_file,
    solvers,
    step_dir,
    t,
)

OUT = step_dir("1_mmi_length")
INSIDE = 1.0  # um of each lead inside the EME region
Y_SPAN, Z_SPAN = 6.0, 2.4  # EME window (um); metal walls
PORT_SPAN = 2 * OUTPUT_Y  # um: an output port reaches from the axis to as far beyond its waveguide


def build(m, gds, x: dict, mesh: float, modes: int, cells: int, surface_mesh: float = 0.01) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds)
    x0, x1 = x["taper_in"] - INSIDE, x["taper_out"] + INSIDE
    groups = [
        (INSIDE, 1, False),
        (LENGTH_TAPER, cells, True),
        (x["face_out"] - x["face_in"], 1, False),
        (LENGTH_TAPER, cells, True),
        (INSIDE, 1, False),
    ]
    solvers.add_eme(m, x0, groups, Y_SPAN, Z_SPAN, mesh, modes)
    solvers.set_eme_port(m, "port_1", "left")
    solvers.set_eme_port(m, "port_2", "right", y=OUTPUT_Y, y_span=PORT_SPAN)
    m.addemeport()
    solvers.set_eme_port(m, "port_3", "right", y=-OUTPUT_Y, y_span=PORT_SPAN)
    solvers.add_eme_profile(m, "field", x0, x1, Y_SPAN)
    # a mesh line on the top and the bottom of the silicon along the whole device
    solvers.add_mesh_box(
        m, "silicon mesh", -WIDTH_MMI / 2 - 0.2, WIDTH_MMI / 2 + 0.2, 0.0, t.T_SI, surface_mesh, x=(x0, x1), dy=mesh
    )


def sweep(m, lengths: tuple[float, float, int]) -> dict:
    s = solvers.eme_length_sweep(m, 3, *lengths)
    return dict(length=s["length"], T2=np.abs(s["s21"]) ** 2, T3=np.abs(s["s31"]) ** 2, R=np.abs(s["s11"]) ** 2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--modes", type=int, default=30, help="modes kept in every cell")
    ap.add_argument("--cells", type=int, default=12, help="cells along each taper")
    ap.add_argument("--mesh", type=float, default=0.02, help="mesh step of the cross-section (um)")
    ap.add_argument("--lengths", type=float, nargs=2, default=[2.0, 14.0], help="shortest and longest multimode section (um)")
    ap.add_argument("--points", type=int, default=121, help="lengths in the sweep")
    ap.add_argument("--check", action="store_true", help="repeat the sweep with fewer modes, to see whether it has converged")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds, x = layout_gds(OUT / "mmi1x2.gds")
    res = dict(length_mmi=LENGTH_MMI, width_mmi=WIDTH_MMI, output_y=OUTPUT_Y, lam=LAM, modes=a.modes, cells=a.cells, lead=LEAD)
    lines = [
        f"1x2 MMI, multimode section {WIDTH_MMI} um wide, strip, 220 nm silicon in oxide (gsip_process.lbr), TE0, {LAM} um; "
        f"EME with {a.modes} modes per cell, {a.cells} cells along each taper (CVCS), mesh {a.mesh * 1000:.0f} nm, whole cross-section"
    ]
    with lumapi.MODE(hide=True) as m:
        build(m, gds, x, a.mesh, a.modes, a.cells)
        m.save(str(OUT / "mmi1x2.lms"))
        solvers.run_eme(m)
        print(f"modes of {2 * a.cells + 3} cells found ({time.time() - t0:.0f} s)", flush=True)

        # ---- 1. the device as drawn: the layout has the length of the builder, so no group is stretched.
        # This comes before the sweep: a sweep leaves the length of its group at the last value it tried.
        m.emepropagate()
        S = np.abs(np.squeeze(m.getresult("EME", "user s matrix"))) ** 2
        f = solvers.eme_profile(m, "field")
        res.update(T2=float(S[1, 0]), T3=float(S[2, 0]), R=float(S[0, 0]), field_x=f["x"], field_y=f["y"], field_E=f["E"])
        res.update({f"x_{k}": v for k, v in x.items()})
        lines.append(
            f"\nthe device, {LENGTH_MMI} um: T = {S[1, 0]:.4f} + {S[2, 0]:.4f} = {S[1, 0] + S[2, 0]:.4f} "
            f"({-10 * np.log10(S[1, 0] + S[2, 0]):.3f} dB), reflected {S[0, 0]:.1e}"
        )
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 2. length sweep ----
        s = sweep(m, (a.lengths[0], a.lengths[1], a.points))
        total = s["T2"] + s["T3"]
        best = int(np.argmax(total))
        res.update(
            sweep_length=s["length"],
            sweep_T2=s["T2"],
            sweep_T3=s["T3"],
            sweep_R=s["R"],
            best_length=float(s["length"][best]),
            best_T=float(total[best]),
        )
        lines.append(f"\n{'length (um)':>12} {'T port 2':>9} {'T port 3':>9} {'sum':>8} {'loss dB':>8} {'reflected':>10}")
        for i in np.linspace(0, len(s["length"]) - 1, 13).round().astype(int):
            lines.append(
                f"{s['length'][i]:12.2f} {s['T2'][i]:9.4f} {s['T3'][i]:9.4f} {total[i]:8.4f} {-10 * np.log10(total[i]):8.3f} {s['R'][i]:10.1e}"
            )
        lines.append(
            f"\nlowest loss at a length of {s['length'][best]:.2f} um: {total[best]:.4f} of the power arrives "
            f"({-10 * np.log10(total[best]):.3f} dB), sweep step {s['length'][1] - s['length'][0]:.2f} um"
        )
        near = s["length"][total >= total[best] * 10 ** (-0.1 / 10)]  # lengths that lose at most 0.1 dB more
        res.update(tolerance_lo=float(near.min()), tolerance_hi=float(near.max()))
        lines.append(f"within 0.1 dB of that from {near.min():.2f} to {near.max():.2f} um")
        print("\n".join(lines[-2:]), f"({time.time() - t0:.0f} s)", flush=True)
        at_device = float(np.interp(LENGTH_MMI, s["length"], total))
        lines.append(
            f"cross-check: the sweep gives {at_device:.4f} at the device length, the device as drawn {S[1, 0] + S[2, 0]:.4f}"
        )
        print(lines[-1], flush=True)

        # ---- 3. convergence ----
        if a.check:
            fewer = max(a.modes // 2, 6)
            build(m, gds, x, a.mesh, fewer, a.cells)
            m.save(str(OUT / "mmi1x2.lms"))
            solvers.run_eme(m)
            c = sweep(m, (a.lengths[0], a.lengths[1], a.points))
            worst = float(np.max(np.abs(c["T2"] + c["T3"] - total)))
            res.update(check_modes=fewer, check_total=c["T2"] + c["T3"])
            lines.append(
                f"convergence: with {fewer} modes instead of {a.modes}, the summed transmission changes by at most {worst:.4f} over the "
                f"sweep, and the best length moves to {c['length'][int(np.argmax(c['T2'] + c['T3']))]:.2f} um"
            )
            print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)
            build(m, gds, x, a.mesh, a.modes, a.cells)  # leave the project as the main run had it
        m.switchtolayout()
        m.save(str(OUT / "mmi1x2.lms"))

    np.savez_compressed(OUT / "mmi_length.npz", **res)
    (OUT / "mmi_length.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

"""Step 2 - EME: how long must the taper be?  Transmission of the linear width taper against its length.

Model: the taper of devices/strip_waveguide_builder.py between the 0.5 um routing waveguide and the 3 um
wide waveguide, with a short straight at each end, written to GDS and loaded into a Layer Builder with
gsip_process.lbr.

        port 1 ══▷████ port 2            group 1   input straight          1 cell
                                         group 2   the taper               --cells cells, CVCS
        0.5 um      3 um                 group 3   wide straight           1 cell

EME cuts the device into cells, finds the modes of each cell once, and joins them.  A different taper
length only changes the phase that each mode collects in group 2, so the whole length sweep costs one
mode calculation.  That is why a taper is an EME problem and not an FDTD one.

The structure is mirror-symmetric in y and fed with TE0, so only half of it is solved, with an
anti-symmetric wall at y = 0, as in the official "Linear waveguide taper" example of Ansys.

    1. the device as drawn:  power that arrives in TE0 of the wide waveguide, and the field
    2. length sweep:  the same power against the length of the taper
    3. a taper that is too short, as its own layout:  its field, and a check of the sweep
    4. convergence:  the same sweep with fewer modes (--check)

    python taper_eme.py
    python taper_eme.py --modes 20 --cells 30

Output in 2_taper/:  taper.gds / .lms, taper.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import gdsfactory as gf
import numpy as np
from common import (
    LAM,
    TAPER_LENGTH,
    WIDE_WIDTH,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    solvers,
    step_dir,
    sw,
    t,
)

OUT = step_dir("2_taper")
LEAD = 1.0  # um of straight waveguide inside the EME region at each end of the device's taper
BEYOND = 1.0  # um that the layout continues beyond the EME region
Y_SPAN, Z_SPAN = 6.0, 2.4  # EME window (um); metal walls
SHORT = 3.0  # um: a taper that is clearly too short, for the field picture
TARGET = 0.99  # the summary reports the length from which the transmission stays above this


def write_gds(length: float, name: str, lead: float = LEAD):
    """Straight, taper, wide straight along x.  The taper is centred on the origin, as the Layer Builder box is."""
    c = gf.Component()
    tp = c << sw.taper(length=length, width1=WIDTH, width2=WIDE_WIDTH)
    tp.dmovex(-length / 2)
    narrow = c << sw.straight(length=lead + BEYOND, width=WIDTH)
    narrow.connect("o2", tp.ports["o1"])
    wide = c << sw.straight(length=lead + BEYOND, width=WIDE_WIDTH)
    wide.connect("o1", tp.ports["o2"])
    return t.write_gds_for_lumerical(c, OUT / f"{name}.gds", cellname=name)


def build(m, gds, length: float, mesh: float, modes: int, cells: int, lead: float = LEAD, surface_mesh: float = 0.01) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds)
    groups = [(lead, 1, False), (length, cells, True), (lead, 1, False)]
    x0, x1 = -length / 2 - lead, length / 2 + lead
    solvers.add_eme(m, x0, groups, Y_SPAN, Z_SPAN, mesh, modes, y_symmetry="Anti-Symmetric")
    solvers.set_eme_port(m, "port_1", "left")
    solvers.set_eme_port(m, "port_2", "right")
    solvers.add_eme_profile(m, "field", x0, x1, Y_SPAN)
    # a mesh line on the top and the bottom of the silicon along the whole device; the sidewalls move along the taper
    solvers.add_mesh_box(
        m, "silicon mesh", -WIDE_WIDTH / 2 - 0.2, WIDE_WIDTH / 2 + 0.2, 0.0, t.T_SI, surface_mesh, x=(x0, x1), dy=mesh
    )


def sweep(m, lengths: tuple[float, float, int]) -> dict:
    s = solvers.eme_length_sweep(m, 2, *lengths)
    return dict(length=s["length"], T=np.abs(s["s21"]) ** 2, R=np.abs(s["s11"]) ** 2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--modes", type=int, default=30, help="modes kept in every cell")
    ap.add_argument("--cells", type=int, default=20, help="cells along the taper")
    ap.add_argument("--mesh", type=float, default=0.02, help="mesh step of the cross-section (um)")
    ap.add_argument("--lengths", type=float, nargs=2, default=[1.0, 40.0], help="shortest and longest taper (um)")
    ap.add_argument("--points", type=int, default=79, help="lengths in the sweep")
    ap.add_argument("--check", action="store_true", help="repeat the sweep with fewer modes, to see whether it has converged")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = write_gds(TAPER_LENGTH, "taper")
    res = dict(width=WIDTH, wide_width=WIDE_WIDTH, taper_length=TAPER_LENGTH, lam=LAM, modes=a.modes, cells=a.cells)
    lines = [
        f"Linear taper {WIDTH} um -> {WIDE_WIDTH} um, strip, 220 nm silicon in oxide (gsip_process.lbr), TE0, {LAM} um; "
        f"EME with {a.modes} modes per cell, {a.cells} cells along the taper (CVCS), mesh {a.mesh * 1000:.0f} nm, half structure"
    ]
    with lumapi.MODE(hide=True) as m:
        build(m, gds, TAPER_LENGTH, a.mesh, a.modes, a.cells)
        m.save(str(OUT / "taper.lms"))
        solvers.run_eme(m)
        print(f"modes of {a.cells + 2} cells found ({time.time() - t0:.0f} s)", flush=True)

        # ---- 1. the device as drawn: the layout has the length of the builder, so no group is stretched.
        # This comes before the sweep: a sweep leaves the length of its group at the last value it tried.
        m.emepropagate()
        S = np.abs(np.squeeze(m.getresult("EME", "user s matrix"))) ** 2
        f = solvers.eme_profile(m, "field")
        res.update(T_device=float(S[1, 0]), R_device=float(S[0, 0]), field_x=f["x"], field_y=f["y"], field_E=f["E"])
        lines.append(f"\nthe device's taper, {TAPER_LENGTH} um: T = {S[1, 0]:.4f} ({-10 * np.log10(S[1, 0]):.3f} dB)")
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 2. length sweep ----
        s = sweep(m, (a.lengths[0], a.lengths[1], a.points))
        res.update(sweep_length=s["length"], sweep_T=s["T"], sweep_R=s["R"])
        neff_in = float(np.real(np.ravel(m.getresult("EME::Cells::cell_1", "neff")["neff"])[0]))
        res.update(neff_in=neff_in)
        lines.append(
            f"TE0 of the input waveguide as the EME finds it: n_eff = {neff_in:.4f} (step 1, mode solver: see strip_modes.txt)"
        )
        # the transmission ripples with the length, so one good point is not enough: take the length from which
        # every longer taper of the sweep is good as well
        below = np.nonzero(s["T"] < TARGET)[0]
        first = 0 if below.size == 0 else below.max() + 1
        shortest = float(s["length"][first]) if first < len(s["length"]) else float("nan")
        at_device = float(np.interp(TAPER_LENGTH, s["length"], s["T"]))
        res.update(length_target=shortest, target=TARGET)
        lines.append(f"\n{'length (um)':>12} {'T to TE0':>9} {'loss dB':>8} {'reflected':>10}")
        for i in np.linspace(0, len(s["length"]) - 1, 14).round().astype(int):
            lines.append(f"{s['length'][i]:12.1f} {s['T'][i]:9.4f} {-10 * np.log10(s['T'][i]):8.3f} {s['R'][i]:10.1e}")
        lines.append(
            f"\nT stays at or above {TARGET} from a length of {shortest:.1f} um (sweep step {s['length'][1] - s['length'][0]:.2f} um)"
        )
        lines.append(f"cross-check: the sweep gives {at_device:.4f} at the device length, the device as drawn {S[1, 0]:.4f}")
        print("\n".join(lines[-2:]), f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 3. the field in a taper that is too short: a second layout, so that picture and structure agree ----
        # its straights are longer, so that it fills the same stretch of x as the device: the wide waveguide then
        # shows what became of the light that left TE0
        lead = LEAD + (TAPER_LENGTH - SHORT) / 2
        short_gds = write_gds(SHORT, "taper_short", lead)
        build(m, short_gds, SHORT, a.mesh, a.modes, a.cells, lead)
        solvers.run_eme(m)
        m.emepropagate()
        f = solvers.eme_profile(m, "field")
        s_short = np.abs(np.squeeze(m.getresult("EME", "user s matrix"))) ** 2
        res.update(short_length=SHORT, short_x=f["x"], short_y=f["y"], short_E=f["E"], short_T=float(s_short[1, 0]))
        lines.append(f"a taper of {SHORT} um, simulated as its own layout: T = {s_short[1, 0]:.4f} "
                     f"(the sweep gives {float(np.interp(SHORT, s['length'], s['T'])):.4f})")  # fmt: skip
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 4. convergence ----
        if a.check:
            fewer = max(a.modes // 2, 4)
            build(m, gds, TAPER_LENGTH, a.mesh, fewer, a.cells)
            solvers.run_eme(m)
            c = sweep(m, (a.lengths[0], a.lengths[1], a.points))
            res.update(check_modes=fewer, check_T=c["T"])
            worst = float(np.max(np.abs(c["T"] - s["T"])))
            lines.append(f"convergence: with {fewer} modes instead of {a.modes}, T changes by at most {worst:.4f} over the sweep")
            print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # the project that is kept is the device as drawn, without results: with the modes of every cell in it
        # the file is several hundred MB, and the script rebuilds them in a minute
        build(m, gds, TAPER_LENGTH, a.mesh, a.modes, a.cells)
        m.save(str(OUT / "taper.lms"))

    np.savez_compressed(OUT / "taper.npz", **res)
    (OUT / "taper.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "taper_short.gds").unlink(missing_ok=True)  # a scratch layout: the picture is in the .npz
    solvers.clean_logs(OUT)
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

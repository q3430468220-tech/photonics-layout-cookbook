"""Step 1 - MODE (FDE): the rib waveguide: its modes, its single-mode width, its dispersion and its bend loss.

Model: a straight piece of the PDK cross-section ``rib``, drawn by devices/rib_waveguide_builder.py,
written to GDS and loaded into a Layer Builder with gsip_process.lbr.

    1. the structure: the refractive index the solver sees on the cross-section
    2. straight waveguide at 1.55 um:  TE0 and TE1, against the mode of the slab beside the core
    3. wavelength sweep 1.50 - 1.60 um:  n_eff and n_g of TE0
    4. bend radius sweep:  radiation loss, and the loss at the junction between a straight and a bend
    5. core width sweep:  n_eff of TE0 and TE1

A rib is guided sideways by the step between the 220 nm core and the 90 nm slab, not by silicon against
oxide.  So the reference index is that of the slab mode: a rib mode below it leaks into the slab.

Mesh: a uniform FDE mesh (--mesh) plus a mesh line on every silicon surface of the rib (--rib-mesh).

    python waveguide_modes_fde.py
    python waveguide_modes_fde.py --radii 5 10 20 --no-widths

Output in 1_waveguide_modes/:  rib.gds / .lms, rib_modes.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    LAM,
    LAM_MAX,
    LAM_MIN,
    RADIUS,
    REPO,
    SLAB_WIDTH,
    T_SLAB,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    rw,
    solvers,
    step_dir,
    t,
)

OUT = step_dir("1_waveguide_modes")
SCRATCH = REPO / "build" / "scratch"  # layouts of the width sweep, overwritten for every width
Y_SPAN, Z_SPAN = 8.0, 2.4  # FDE window (um); the 6 um slab ends inside it; PML on all sides
LENGTH = 6.0  # um of straight waveguide in the layout
N_GUESS = 2.6  # the search starts near this index


def core_range(width: float) -> tuple[float, float]:
    """The range of y that counts as "in the waveguide": the core and 0.35 um of evanescent field on each side."""
    return (-width / 2 - 0.35, width / 2 + 0.35)


def setup(m, gds, width: float, mesh: float, rib_mesh: float, trial_modes: int = 8) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds, LENGTH, SLAB_WIDTH + 4.0)
    solvers.add_fde(m, Y_SPAN, Z_SPAN, mesh, trial_modes=trial_modes, guess=N_GUESS)
    solvers.add_rib_mesh(m, width, rib_mesh)  # added last: a new object takes the selection


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--radii", type=float, nargs="*", default=[5, 6, 8, 10, 15, 20])
    ap.add_argument("--widths", type=float, nargs="*", default=[0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80])
    ap.add_argument("--no-widths", action="store_true", help="skip the core width sweep")
    ap.add_argument("--mesh", type=float, default=0.02, help="uniform FDE mesh step (um)")
    ap.add_argument("--rib-mesh", type=float, default=0.01, help="mesh step on the silicon surfaces of the rib (um)")
    ap.add_argument("--points", type=int, default=11, help="wavelengths in the sweep")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = t.write_gds_for_lumerical(rw.straight(length=LENGTH, width=WIDTH), OUT / "rib.gds", cellname="rib")
    core = core_range(WIDTH)
    res = dict(width=WIDTH, slab_width=SLAB_WIDTH, lam=LAM, radius=RADIUS, t_si=t.T_SI, t_slab=T_SLAB)
    lines = [
        f"Rib waveguide W = {WIDTH} um, 220 nm core on a 90 nm slab {SLAB_WIDTH} um wide (gsip_process.lbr); FDE mesh "
        f"{a.mesh * 1000:.0f} nm, rib-surface mesh {a.rib_mesh * 1000:.0f} nm, window {Y_SPAN} x {Z_SPAN} um"
    ]
    with lumapi.MODE(hide=True) as m:
        setup(m, gds, WIDTH, a.mesh, a.rib_mesh)

        # ---- 1. the structure as the solver sees it, and the slab mode that the rib is measured against ----
        index = solvers.index_map(m)
        at = lambda y, z: float(index["index"][np.argmin(np.abs(index["y"] - y)), np.argmin(np.abs(index["z"] - z))])  # noqa: E731
        n_si, n_ox = at(0, t.T_SI / 2), at(0, -0.5)
        n_slab = solvers.slab_te0_index(T_SLAB, LAM, n_si, n_ox)
        res.update(n_si=n_si, n_ox=n_ox, n_slab=n_slab)  # the map itself is only looked at here
        lines.append(
            f"index on the cross-section: core centre {n_si:.4f} (silicon), slab at y = 1.5 um {at(1.5, T_SLAB / 2):.4f} (silicon), "
            f"above the slab {at(1.5, 0.15):.4f}, below {n_ox:.4f} (oxide)"
        )
        lines.append(
            f"TE0 mode of the {T_SLAB * 1000:.0f} nm slab alone: n_eff = {n_slab:.4f} (three-layer slab with the indices above); "
            "a rib mode is guided sideways only above it"
        )

        # ---- 2. straight waveguide.  A mode counts only above the slab mode: below it, it leaks into the slab ----
        modes = solvers.guided_modes(m, core, n_slab)
        te0, te1 = solvers.pick(modes, "TE"), solvers.pick(modes, "TE", 1)
        if te0 is None or te0["te"] < 0.9:
            raise SystemExit("no TE0 mode found in the core: check the Layer Builder geometry and the search guess")
        m.copydcard(f"FDE::data::mode{te0['i']}", "straight")
        res.update(neff=te0["neff"].real, ng=te0["ng"], te=te0["te"], E=te0["E"], y=te0["y"], z=te0["z"])
        if te1 is not None:
            res.update(te1_neff=te1["neff"].real)
        lines.append(f"\nstraight, {LAM} um, guided modes (n_eff above the slab mode, power in the core region):")
        lines += solvers.mode_table({"TE0": te0, "TE1": te1})
        if te1 is not None:
            lines.append(
                f"TE1 lies {te1['neff'].real - n_slab:+.4f} from the slab mode: {'weakly guided' if te1['neff'].real > n_slab else 'leaks into the slab'}"
            )
        print("\n".join(lines[-5:]), f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 3. wavelength sweep ----
        sweep = solvers.wavelength_sweep(m, np.linspace(LAM_MIN, LAM_MAX, a.points), "TE", core, n_slab, te0["neff"].real)
        res.update(sweep_lam=sweep["lam"], sweep_neff=sweep["neff"], sweep_ng=sweep["ng"], ng_fit=sweep["ng_fit"])
        lines.append(
            f"\nsweep {LAM_MIN}-{LAM_MAX} um, TE0:  n_eff {sweep['neff'][0]:.4f} to {sweep['neff'][-1]:.4f};  n_g from the slope of "
            f"n_eff(lambda) = {sweep['ng_fit']:.4f}, solver n_g at {LAM} um = {te0['ng']:.4f}"
        )
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 4. bend radius sweep ----
        # the solver maps the bend onto a straight guide; that only works while the centre of the bend lies
        # outside the window, so a radius must exceed half the window width
        radii = sorted(r for r in set(a.radii) | {RADIUS} if r > Y_SPAN / 2 + 0.2)
        skipped = sorted(r for r in a.radii if r <= Y_SPAN / 2 + 0.2)
        bend = solvers.bend_sweep(m, radii, te0, "TE", core, n_slab)
        res.update({f"bend_{k}": v for k, v in bend.items() if k != "modes"})
        shown = bend["modes"].get(RADIUS)  # the mode at the design-rule radius, for the figure
        if shown is not None:
            res.update(bend_E=shown["E"], bend_E_radius=RADIUS)
        lines.append(
            f"\nbent waveguide, {LAM} um, TE0.  A 90 degree bend between two straights loses the radiation plus two junctions:"
        )
        lines += solvers.bend_table(bend)
        if skipped:
            lines.append(f"not computed: R = {skipped} um, inside the {Y_SPAN} um window (narrow the window to go tighter)")
        print("\n".join(lines[-len(radii) - 2 :]), f"({time.time() - t0:.0f} s)", flush=True)
        m.switchtolayout()
        m.save(str(OUT / "rib.lms"))

        # ---- 5. core width sweep: TE0 and the second TE mode ----
        if not a.no_widths:
            found = {k: [] for k in ("te0", "te1")}
            for w in a.widths:
                gds_w = t.write_gds_for_lumerical(
                    rw.straight(length=LENGTH, width=w), SCRATCH / "rib_width_sweep.gds", cellname=f"rib_w{round(w * 1000)}"
                )
                setup(m, gds_w, w, a.mesh, a.rib_mesh, trial_modes=10)
                modes = solvers.guided_modes(m, core_range(w), n_slab)
                for key, order in dict(te0=0, te1=1).items():
                    mode = solvers.pick(modes, "TE", order)
                    found[key].append(mode["neff"].real if mode else np.nan)
                print(
                    f"  width {w:.2f} um: TE0 {found['te0'][-1]:.4f}  TE1 {found['te1'][-1]:.4f}  ({time.time() - t0:.0f} s)",
                    flush=True,
                )
            widths = np.array(a.widths)
            res.update(widths=widths, **{f"width_{k}": np.array(v) for k, v in found.items()})
            lines.append(f"\ncore width sweep, n_eff (nan: not guided, that is, not above the slab mode at {n_slab:.4f}):")
            lines.append(f"{'W (um)':>7} {'TE0':>8} {'TE1':>8} {'TE1 - slab':>11}")
            lines += [
                f"{w:7.2f} {a0:8.4f} {b0:8.4f} {b0 - n_slab:11.4f}"
                for w, a0, b0 in zip(widths, found["te0"], found["te1"], strict=True)
            ]
            lines.append(solvers.cutoff_sentence(widths, np.array(found["te1"]), "TE1"))

    np.savez_compressed(OUT / "rib_modes.npz", **res)
    (OUT / "rib_modes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print(lines[-1])
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

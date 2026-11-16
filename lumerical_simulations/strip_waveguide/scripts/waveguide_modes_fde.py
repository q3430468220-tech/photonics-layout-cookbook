"""Step 1 - MODE (FDE): the strip waveguide: its modes, its single-mode width, its dispersion and its bend loss.

Model: a straight piece of the PDK cross-section ``strip``, drawn by devices/strip_waveguide_builder.py,
written to GDS and loaded into a Layer Builder with gsip_process.lbr.

    1. the structure: the refractive index the solver sees on the cross-section
    2. straight waveguide at 1.55 um:  TE0, TM0 and TE1: n_eff, n_g, mode profiles
    3. wavelength sweep 1.50 - 1.60 um:  n_eff and n_g of TE0
    4. bend radius sweep:  radiation loss, and the loss at the junction between a straight and a bend
    5. core width sweep:  n_eff of TE0, TM0 and TE1, to find the width where the second TE mode appears

Mesh: a uniform FDE mesh (--mesh) plus a mesh line on the four surfaces of the core (--core-mesh), so
that the result does not depend on where the window starts.

    python waveguide_modes_fde.py
    python waveguide_modes_fde.py --radii 3 5 10 --no-widths

Output in 1_waveguide_modes/:  strip.gds / .lms, strip_modes.npz / .txt
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
    WIDTH,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    solvers,
    step_dir,
    sw,
    t,
)

OUT = step_dir("1_waveguide_modes")
SCRATCH = REPO / "build" / "scratch"  # layouts of the width sweep, overwritten for every width
Y_SPAN, Z_SPAN = 5.0, 2.4  # FDE window (um), PML on all sides
LENGTH = 6.0  # um of straight waveguide in the layout
N_GUESS = 2.5  # the search starts near this index


def core_range(width: float) -> tuple[float, float]:
    """The range of y that counts as "in the waveguide": the core and 0.35 um of evanescent field on each side."""
    return (-width / 2 - 0.35, width / 2 + 0.35)


def setup(m, gds, width: float, mesh: float, core_mesh: float, trial_modes: int = 8) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds, LENGTH, Y_SPAN + 2.0)
    solvers.add_fde(m, Y_SPAN, Z_SPAN, mesh, trial_modes=trial_modes, guess=N_GUESS)
    solvers.add_strip_mesh(m, width, core_mesh)  # added last: a new object takes the selection


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--radii", type=float, nargs="*", default=[3, 4, 5, 7.5, 10])
    ap.add_argument("--widths", type=float, nargs="*", default=[0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80, 0.90, 1.00])
    ap.add_argument("--no-widths", action="store_true", help="skip the core width sweep")
    ap.add_argument("--mesh", type=float, default=0.02, help="uniform FDE mesh step (um)")
    ap.add_argument("--core-mesh", type=float, default=0.01, help="mesh step on the surfaces of the core (um)")
    ap.add_argument("--points", type=int, default=11, help="wavelengths in the sweep")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = t.write_gds_for_lumerical(sw.straight(length=LENGTH, width=WIDTH), OUT / "strip.gds", cellname="strip")
    core = core_range(WIDTH)
    res = dict(width=WIDTH, lam=LAM, radius=RADIUS, t_si=t.T_SI)
    lines = [
        f"Strip waveguide W = {WIDTH} um, 220 nm silicon in oxide (gsip_process.lbr); FDE mesh {a.mesh * 1000:.0f} nm, "
        f"core-surface mesh {a.core_mesh * 1000:.0f} nm, window {Y_SPAN} x {Z_SPAN} um"
    ]
    with lumapi.MODE(hide=True) as m:
        setup(m, gds, WIDTH, a.mesh, a.core_mesh)

        # ---- 1. the structure as the solver sees it ----
        index = solvers.index_map(m)
        at = lambda y, z: float(index["index"][np.argmin(np.abs(index["y"] - y)), np.argmin(np.abs(index["z"] - z))])  # noqa: E731
        n_si, n_ox = at(0, t.T_SI / 2), at(0, -0.5)
        res.update(n_si=n_si, n_ox=n_ox)  # the map itself is only looked at here; the summary keeps four of its values
        lines.append(
            f"index on the cross-section: core centre {n_si:.4f} (silicon), beside the core {at(WIDTH / 2 + 0.3, t.T_SI / 2):.4f}, "
            f"below {n_ox:.4f}, above {at(0, 0.7):.4f} (oxide)"
        )
        n_min = n_ox + 0.01  # a guided mode has an index above the cladding

        # ---- 2. straight waveguide ----
        modes = solvers.guided_modes(m, core, n_min)
        te0, tm0, te1 = solvers.pick(modes, "TE"), solvers.pick(modes, "TM"), solvers.pick(modes, "TE", 1)
        if te0 is None or te0["te"] < 0.9:
            raise SystemExit("no TE0 mode found in the core: check the Layer Builder geometry and the search guess")
        m.copydcard(f"FDE::data::mode{te0['i']}", "straight")
        res.update(neff=te0["neff"].real, ng=te0["ng"], te=te0["te"], E=te0["E"], y=te0["y"], z=te0["z"])
        if tm0 is not None:
            res.update(tm_neff=tm0["neff"].real, tm_ng=tm0["ng"], tm_E=tm0["E"])
        if te1 is not None:
            res.update(te1_neff=te1["neff"].real)
        lines.append(f"\nstraight, {LAM} um, guided modes (n_eff above the oxide, power in the core region):")
        lines += solvers.mode_table({"TE0": te0, "TM0": tm0, "TE1": te1})
        print("\n".join(lines[-5:]), f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 3. wavelength sweep ----
        sweep = solvers.wavelength_sweep(m, np.linspace(LAM_MIN, LAM_MAX, a.points), "TE", core, n_min, te0["neff"].real)
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
        bend = solvers.bend_sweep(m, radii, te0, "TE", core, n_min)
        res.update({f"bend_{k}": v for k, v in bend.items() if k != "modes"})
        lines.append(
            f"\nbent waveguide, {LAM} um, TE0.  A 90 degree bend between two straights loses the radiation plus two junctions:"
        )
        lines += solvers.bend_table(bend)
        if skipped:
            lines.append(f"not computed: R = {skipped} um, inside the {Y_SPAN} um window (narrow the window to go tighter)")
        print("\n".join(lines[-len(radii) - 2 :]), f"({time.time() - t0:.0f} s)", flush=True)
        m.switchtolayout()
        m.save(str(OUT / "strip.lms"))

        # ---- 5. core width sweep: TE0, TM0 and the second TE mode ----
        if not a.no_widths:
            found = {k: [] for k in ("te0", "tm0", "te1")}
            for w in a.widths:
                gds_w = t.write_gds_for_lumerical(
                    sw.straight(length=LENGTH, width=w), SCRATCH / "strip_width_sweep.gds", cellname=f"strip_w{round(w * 1000)}"
                )
                setup(m, gds_w, w, a.mesh, a.core_mesh, trial_modes=10)
                modes = solvers.guided_modes(m, core_range(w), n_min)
                for key, (pol, order) in dict(te0=("TE", 0), tm0=("TM", 0), te1=("TE", 1)).items():
                    mode = solvers.pick(modes, pol, order)
                    found[key].append(mode["neff"].real if mode else np.nan)
                print(
                    f"  width {w:.2f} um: TE0 {found['te0'][-1]:.4f}  TM0 {found['tm0'][-1]:.4f}  TE1 {found['te1'][-1]:.4f}  "
                    f"({time.time() - t0:.0f} s)",
                    flush=True,
                )
            widths = np.array(a.widths)
            res.update(widths=widths, **{f"width_{k}": np.array(v) for k, v in found.items()})
            lines.append("\ncore width sweep, n_eff (nan: not guided):")
            lines.append(f"{'W (um)':>7} {'TE0':>8} {'TM0':>8} {'TE1':>8}")
            lines += [
                f"{w:7.2f} {a0:8.4f} {b0:8.4f} {c0:8.4f}"
                for w, a0, b0, c0 in zip(widths, found["te0"], found["tm0"], found["te1"], strict=True)
            ]
            lines.append(solvers.cutoff_sentence(widths, np.array(found["te1"]), "TE1"))

    np.savez_compressed(OUT / "strip_modes.npz", **res)
    (OUT / "strip_modes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print(lines[-1])
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

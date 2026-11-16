"""Step 1 - MODE (FDE): the two supermodes of the coupled waveguides, and the length they need to exchange the light.

Model: two parallel strips of the coupler, drawn with the PDK, written to GDS and loaded into a Layer
Builder with gsip_process.lbr.

Two waveguides side by side do not have a mode each.  They share two: the even supermode, with the same
field in both cores, and the odd one, with opposite fields.  Light in one waveguide is the sum of the
two.  They travel at different speeds, so the sum moves across to the other waveguide and back.  All of
it has crossed after

    L_pi = lambda / (2 (n_even - n_odd))

and half of it after L_pi / 2.  The cross-section alone therefore gives the scale of the device.

    1. the supermodes at the gap of the device:  n_even, n_odd, L_pi, mode profiles
    2. wavelength sweep at the gap of the device:  L_pi against the wavelength
    3. gap sweep:  L_pi against the gap

Mesh: a uniform FDE mesh (--mesh), a mesh line on every surface of both cores, and a fine mesh in the gap.

    python supermodes_fde.py
    python supermodes_fde.py --gaps 0.2 0.3

Output in 1_supermodes/:  section.gds / .lms, supermodes.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    GAP,
    LAM,
    LAM_MAX,
    LAM_MIN,
    REPO,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    section_gds,
    solvers,
    step_dir,
    t,
)

OUT = step_dir("1_supermodes")
SCRATCH = REPO / "build" / "scratch"  # layouts of the gap sweep, overwritten for every gap
Y_SPAN, Z_SPAN = 6.0, 2.4  # FDE window (um), PML on all sides
N_GUESS = 2.45  # the search starts near the index of the single waveguide


def setup(m, gds, gap: float, mesh: float, fine: float) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds)
    solvers.add_fde(m, Y_SPAN, Z_SPAN, mesh, trial_modes=8, guess=N_GUESS)
    centre = (WIDTH + gap) / 2
    solvers.add_strip_mesh(m, WIDTH, fine, y=centre, name="core mesh upper")
    solvers.add_strip_mesh(m, WIDTH, fine, y=-centre, name="core mesh lower")
    solvers.add_mesh_box(m, "gap mesh", -gap / 2, gap / 2, 0.0, t.T_SI, fine)  # added last: a new object takes the selection


def supermodes(m, gap: float, n_min: float, guess: float = N_GUESS) -> tuple[dict, dict] | None:
    """The even and the odd TE supermode: the two TE modes of highest index that live in the pair of cores."""
    reach = WIDTH + gap / 2 + 0.35
    m.setanalysis("n", guess)
    modes = solvers.guided_modes(m, (-reach, reach), n_min)
    even, odd = solvers.pick(modes, "TE", 0), solvers.pick(modes, "TE", 1)
    return None if even is None or odd is None else (even, odd)


def crossover(even: dict, odd: dict, lam: float) -> float:
    return lam / (2 * (even["neff"].real - odd["neff"].real))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gaps", type=float, nargs="*", default=[0.20, 0.25, 0.30, 0.35, 0.40, 0.50])
    ap.add_argument("--mesh", type=float, default=0.02, help="uniform FDE mesh step (um)")
    ap.add_argument("--fine", type=float, default=0.01, help="mesh step on the cores and in the gap (um)")
    ap.add_argument("--points", type=int, default=6, help="wavelengths in the sweep")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = section_gds(OUT / "section.gds", GAP)
    res = dict(gap=GAP, width=WIDTH, lam=LAM)
    lines = [
        f"Two strips W = {WIDTH} um, 220 nm silicon in oxide (gsip_process.lbr); FDE mesh {a.mesh * 1000:.0f} nm, "
        f"{a.fine * 1000:.0f} nm on the cores and in the gap, window {Y_SPAN} x {Z_SPAN} um"
    ]
    with lumapi.MODE(hide=True) as m:
        setup(m, gds, GAP, a.mesh, a.fine)
        index = solvers.index_map(m)
        n_ox = float(index["index"][np.argmin(np.abs(index["y"])), np.argmin(np.abs(index["z"] + 0.5))])
        n_min = n_ox + 0.01

        # ---- 1. the supermodes of the device ----
        pair = supermodes(m, GAP, n_min)
        if pair is None:
            raise SystemExit("the two TE supermodes were not found: check the Layer Builder geometry and the search guess")
        even, odd = pair
        l_pi = crossover(even, odd, LAM)
        res.update(
            n_even=even["neff"].real,
            n_odd=odd["neff"].real,
            l_pi=l_pi,
            y=even["y"],
            z=even["z"],
            E_even=even["E"],
            E_odd=odd["E"],
        )
        lines.append(f"\ngap {GAP} um, {LAM} um:")
        lines += solvers.mode_table({"even": even, "odd": odd})
        lines.append(
            f"n_even - n_odd = {even['neff'].real - odd['neff'].real:.5f}  ->  L_pi = {l_pi:.2f} um (all the light has crossed), "
            f"L_pi / 2 = {l_pi / 2:.2f} um (half of it)"
        )
        print("\n".join(lines[-5:]), f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 2. wavelength sweep at the gap of the device ----
        lams = np.linspace(LAM_MIN, LAM_MAX, a.points)
        l_lam = []
        guess = even["neff"].real
        for lam in lams:
            m.switchtolayout()
            m.setanalysis("wavelength", lam * 1e-6)
            pair = supermodes(m, GAP, n_min, guess)
            l_lam.append(crossover(*pair, lam) if pair else np.nan)
        m.switchtolayout()
        m.setanalysis("wavelength", LAM * 1e-6)
        res.update(sweep_lam=lams, sweep_l_pi=np.array(l_lam))
        m.save(str(OUT / "section.lms"))

        # ---- 3. gap sweep: a new layout for every gap ----
        gaps = sorted(set(a.gaps) | {GAP})
        table = {k: [] for k in ("n_even", "n_odd", "l_pi")}
        for gap in gaps:
            if abs(gap - GAP) < 1e-9:
                found = (even, odd)
            else:
                setup(
                    m,
                    section_gds(SCRATCH / "coupler_gap_sweep.gds", gap, cellname=f"section_gap{round(gap * 1000)}"),
                    gap,
                    a.mesh,
                    a.fine,
                )
                found = supermodes(m, gap, n_min)
            table["n_even"].append(found[0]["neff"].real if found else np.nan)
            table["n_odd"].append(found[1]["neff"].real if found else np.nan)
            table["l_pi"].append(crossover(*found, LAM) if found else np.nan)
            print(f"  gap {gap:.2f} um: L_pi = {table['l_pi'][-1]:.2f} um  ({time.time() - t0:.0f} s)", flush=True)
        res.update(gaps=np.array(gaps), **{f"gap_{k}": np.array(v) for k, v in table.items()})

    slope, intercept = np.polyfit(res["gaps"], np.log(res["gap_l_pi"]), 1)
    res.update(fit_decay_nm=1000 / slope, fit_l0=float(np.exp(intercept)))
    lines.append(f"\ngap sweep, {LAM} um:")
    lines.append(f"{'gap (um)':>9} {'n_even':>9} {'n_odd':>9} {'L_pi (um)':>10}")
    rows = zip(res["gaps"], res["gap_n_even"], res["gap_n_odd"], res["gap_l_pi"], strict=True)
    lines += [f"{gap:9.2f} {n_even:9.5f} {n_odd:9.5f} {length:10.2f}" for gap, n_even, n_odd, length in rows]
    lines.append(
        f"fit: L_pi = {np.exp(intercept):.2f} um * exp(gap / {1000 / slope:.1f} nm) for gaps of {res['gaps'].min() * 1000:.0f} to "
        f"{res['gaps'].max() * 1000:.0f} nm; an interpolation formula, do not extrapolate"
    )
    lines.append(f"\nwavelength sweep at gap {GAP} um:")
    lines.append("  " + ",  ".join(f"{lam * 1000:.0f} nm: {length:.2f} um" for lam, length in zip(lams, l_lam, strict=True)))
    np.savez_compressed(OUT / "supermodes.npz", **res)
    (OUT / "supermodes.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print("\n".join(lines[-9:]))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

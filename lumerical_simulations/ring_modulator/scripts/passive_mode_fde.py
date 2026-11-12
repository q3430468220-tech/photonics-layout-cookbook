"""Step 2 - MODE (FDE): the passive rib waveguide: effective index, group index, bend loss, single-mode width.

Model: a straight piece of the PDK cross-section ``rib`` with the slab width of the ring, written to
GDS and loaded into a Layer Builder with gsip_process.lbr.  The silicon is the process file's
index-perturbation material without carriers, i.e. plain silicon.

    1. straight waveguide at 1.55 um:  n_eff, n_g, mode profile
    2. the ring itself: the same cross-section bent to the ring radius:  n_eff, n_g, radiation loss
    3. bend radius sweep:  radiation loss and overlap with the straight mode
    4. wavelength sweep 1.50 - 1.60 um:  n_eff(lambda), n_g(lambda)
    5. core width sweep:  n_eff of TE0 and TE1, to show where the waveguide stops being single-mode

Mesh: a uniform FDE mesh (--mesh) plus a mesh line on every silicon surface of the rib (add_rib_mesh,
--rib-mesh), so the result does not depend on where the window starts.  The mesh is not uniform, so
every sum over a field map is weighted by the area of its cells (np.gradient gives the cell widths).

Search: each point of a sweep starts from the n_eff of the previous point; the first point starts at N_GUESS.

    python passive_mode_fde.py
    python passive_mode_fde.py --radii 5 10 20 --no-widths

Output in 2_passive_mode_properties/:  rib.gds / .lms, rib_passive.npz / .txt
"""

from __future__ import annotations

import argparse
import math
import time

import numpy as np
from common import (
    LAM,
    LAM_MAX,
    LAM_MIN,
    RADIUS,
    SLAB_WIDTH,
    T_SI,
    WIDTH,
    add_layer_builder,
    add_rib_mesh,
    import_lumapi,
    require_process_file,
    section_gds,
    step_dir,
    um,
)

OUT = step_dir("2_passive_mode_properties")
Y_SPAN, Z_SPAN = 8.0, 2.4  # FDE window (um); the 6 um slab ends inside it; PML on all sides
N_GUESS = 2.6  # search guess for the first point of every sweep
TE_MIN, CORE_MIN = 0.9, 0.5  # the mode of the default waveguide must be this TE and this much in the core


def setup(m, gds, width: float, mesh: float, rib_mesh: float) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds, 6.0, SLAB_WIDTH + 4.0)
    m.addfde()
    m.set("solver type", "2D X normal")
    m.set("x", 0)
    m.set("y", 0)
    m.set("y span", Y_SPAN * um)
    m.set("z", T_SI / 2 * um)
    m.set("z span", Z_SPAN * um)
    for axis in ("y", "z"):
        m.set(f"define {axis} mesh by", "maximum mesh step")
        m.set(f"d{axis}", mesh * um)
    for bc in ("y min bc", "y max bc", "z min bc", "z max bc"):
        m.set(bc, "PML")
    # added last: a new object takes the selection, and every set() above is meant for the FDE
    add_rib_mesh(m, width, rib_mesh)  # a mesh line on every silicon surface, whatever the window
    m.setanalysis("wavelength", LAM * um)
    m.setanalysis("search", "near n")
    m.setanalysis("use max index", 0)
    m.setanalysis("n", N_GUESS)
    m.setanalysis("number of trial modes", 8)
    m.setanalysis("calculate group index", 1)
    m.setanalysis("bend location", "simulation center")
    m.setanalysis("bend orientation", 0)


def cell_areas(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Area of each cell of a field map indexed [y, z]; np.gradient gives the cell widths of a non-uniform mesh."""
    return np.outer(np.gradient(y), np.gradient(z))


def mode_info(m, i: int) -> dict:
    d = f"FDE::data::mode{i}"
    intensity = sum(np.abs(np.squeeze(m.getdata(d, c))) ** 2 for c in ("Ex", "Ey", "Ez"))
    y, z = np.squeeze(m.getdata(d, "y")), np.squeeze(m.getdata(d, "z"))
    power = intensity * cell_areas(y, z)  # power in each cell
    profile = power.sum(axis=1)  # power in each row of cells, against y
    info = dict(
        i=i,
        neff=complex(np.squeeze(m.getdata(d, "neff"))),
        te=float(np.squeeze(m.getdata(d, "TE polarization fraction"))),
        loss_dBcm=float(np.squeeze(m.getdata(d, "loss"))) / 100,
        y_centre=float((profile * y).sum() / profile.sum()) / um,
        core_fraction=float(profile[np.abs(y) < 0.6 * um].sum() / profile.sum()),
        E=intensity.astype(np.float32),
        y=y / um,
        z=z / um,
    )
    try:
        info["ng"] = float(np.real(np.squeeze(m.getdata(d, "ng"))))
    except Exception:
        info["ng"] = float("nan")
    return info


def cell_overlap(a: dict, b: dict) -> float:
    """Intensity overlap of two mode maps, every cell weighted by its area: 1 for identical maps.

    The maps must sit on the same grid, which the sweeps guarantee (same window and mesh); otherwise nan.
    """
    if a["E"].shape != b["E"].shape or not (np.allclose(a["y"], b["y"]) and np.allclose(a["z"], b["z"])):
        return float("nan")
    cell = cell_areas(a["y"], a["z"])
    ea, eb = a["E"].astype(float), b["E"].astype(float)
    cross = np.sum(np.sqrt(ea * eb) * cell) ** 2
    return float(cross / (np.sum(ea * cell) * np.sum(eb * cell)))


def guided_te_modes(m) -> list[dict]:
    """Guided TE modes, highest n_eff first: mostly TE and concentrated around the core.

    The filter matters: a search near the maximum index also returns slab and PML modes.
    """
    modes = [mode_info(m, i) for i in range(1, int(m.findmodes()) + 1)]
    modes = [x for x in modes if x["te"] > 0.5 and x["core_fraction"] > 0.3]
    return sorted(modes, key=lambda x: -x["neff"].real)


def find_te0(m, guess: float = N_GUESS) -> dict | None:
    """TE0 of the current structure, searched near ``guess`` (the n_eff of the previous point of a sweep)."""
    m.setanalysis("n", guess)
    modes = guided_te_modes(m)
    return modes[0] if modes else None


def check_default_mode(mode: dict, label: str) -> None:
    """Stop with a clear message if the mode of the default waveguide is not a TE mode of the core."""
    if mode["te"] < TE_MIN or mode["core_fraction"] < CORE_MIN:
        raise SystemExit(
            f"{label}: the mode found has TE fraction {mode['te']:.3f} (need >= {TE_MIN}) and core fraction "
            f"{mode['core_fraction']:.3f} (need >= {CORE_MIN}): it is not the TE0 of the core.  Check the geometry "
            "and the search guess before using these numbers."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--radii", type=float, nargs="*", default=[4, 5, 6, 8, 10, 15, 20])
    ap.add_argument("--widths", type=float, nargs="*", default=[0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80])
    ap.add_argument("--no-widths", action="store_true", help="skip the core width sweep")
    ap.add_argument("--mesh", type=float, default=0.02, help="uniform FDE mesh step (um)")
    ap.add_argument("--rib-mesh", type=float, default=0.01, help="mesh step on the silicon surfaces of the rib (um)")
    ap.add_argument("--points", type=int, default=11, help="wavelengths in the sweep")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = section_gds(OUT / "rib.gds", doped=False, contacts=False)
    res = dict(width=WIDTH, lam=LAM, radius=RADIUS, radii=np.array(a.radii, float))
    lines = [
        f"Rib waveguide W = {WIDTH} um, 220 nm core on a 90 nm slab (gsip_process.lbr); FDE mesh {a.mesh * 1000:.0f} nm, "
        f"rib-interface mesh {a.rib_mesh * 1000:.0f} nm"
    ]
    with lumapi.MODE(hide=True) as m:
        setup(m, gds, WIDTH, a.mesh, a.rib_mesh)

        # ---- 1. straight waveguide ----
        straight = find_te0(m)
        if straight is None:
            raise SystemExit("no guided TE0 mode found: check the Layer Builder geometry")
        check_default_mode(straight, "straight waveguide")
        m.copydcard(f"FDE::data::mode{straight['i']}", "straight_TE0")
        res.update(
            neff=straight["neff"].real, ng=straight["ng"], te=straight["te"], E=straight["E"], y=straight["y"], z=straight["z"]
        )
        lines.append(
            f"straight, {LAM} um:  n_eff = {straight['neff'].real:.5f}   n_g = {straight['ng']:.4f}   "
            f"TE fraction {straight['te']:.3f}"
        )
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # ---- 2. and 3. bent waveguide.  The ring centre lies at +y (the inside of the ring, where n sits in the
        # default device), so the mode must end at -y: the bend orientation is flipped until the mode centroid is there.
        m.switchtolayout()
        m.setanalysis("bent waveguide", 1)
        m.setanalysis("bend radius", RADIUS * um)
        orientation = 0
        ring = find_te0(m)
        if ring is not None and ring["y_centre"] > 0:  # wrong way round: turn the bend
            orientation = 180
            m.switchtolayout()
            m.setanalysis("bend orientation", orientation)
            ring = find_te0(m)
        if ring is None:
            raise SystemExit(f"no guided mode at R = {RADIUS} um")
        check_default_mode(ring, f"bent waveguide, R = {RADIUS} um")
        res.update(bend_orientation=orientation)
        bend = {k: [] for k in ("neff", "ng", "loss_dBcm", "loss_dB_turn", "shift_nm", "overlap", "overlap_cells")}
        lines.append(
            f"\nbent waveguide, {LAM} um (bend orientation {orientation} deg: the mode moves away from the ring centre):"
        )
        lines.append(
            "centroid shift and overlaps use the cell areas of the mesh; 'solver ovl' is Lumerical's m.overlap, "
            "'overlap' is the intensity overlap with the straight mode."
        )
        lines.append(
            f"{'R (um)':>7} {'n_eff':>9} {'n_g':>8} {'radiation dB/cm':>16} {'dB / round trip':>16} {'mode shift nm':>14} "
            f"{'overlap':>9} {'solver ovl':>10}"
        )
        guess = N_GUESS  # the first radius starts from N_GUESS; each later one from the previous n_eff
        for radius in sorted(set(a.radii) | {RADIUS}):
            m.switchtolayout()
            m.setanalysis("bend radius", radius * um)
            b = find_te0(m, guess)
            if b is None:
                for k in bend:
                    bend[k].append(np.nan)
                lines.append(f"{radius:7.1f}  no guided mode")
                continue
            guess = b["neff"].real
            solver_overlap = float(np.ravel(np.squeeze(m.overlap("straight_TE0", f"FDE::data::mode{b['i']}")))[1])
            turn = b["loss_dBcm"] * 2 * math.pi * radius * 1e-4
            values = dict(neff=b["neff"].real, ng=b["ng"], loss_dBcm=b["loss_dBcm"], loss_dB_turn=turn,
                          shift_nm=b["y_centre"] * 1000, overlap=solver_overlap, overlap_cells=cell_overlap(straight, b))  # fmt: skip
            for k, v in values.items():
                bend[k].append(v)
            if abs(radius - RADIUS) < 1e-9:
                res.update(ring_neff=b["neff"].real, ring_ng=b["ng"], ring_loss_dBcm=b["loss_dBcm"],
                           ring_E=b["E"], ring_y=b["y"], ring_z=b["z"])  # fmt: skip
            lines.append(
                f"{radius:7.1f} {b['neff'].real:9.5f} {b['ng']:8.4f} {b['loss_dBcm']:16.4f} {turn:16.5f} "
                f"{b['y_centre'] * 1000:14.1f} {values['overlap_cells']:9.4f} {solver_overlap:10.4f}"
            )
            print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)
        res["radii"] = np.array(sorted(set(a.radii) | {RADIUS}), float)
        res.update({f"bend_{k}": np.array(v) for k, v in bend.items()})
        m.switchtolayout()
        m.setanalysis("bent waveguide", 0)

        # ---- 4. wavelength sweep: one findmodes per wavelength (the built-in sweep can jump to PML modes) ----
        lams = np.linspace(LAM_MIN, LAM_MAX, a.points)
        neffs, ngs = [], []
        guess = N_GUESS
        for lam in lams:
            m.switchtolayout()
            m.setanalysis("wavelength", lam * um)
            mode = find_te0(m, guess)
            neffs.append(mode["neff"].real if mode else np.nan)
            ngs.append(mode["ng"] if mode else np.nan)
            if mode:
                guess = mode["neff"].real
        neffs, ngs = np.array(neffs), np.array(ngs)
        fit = np.polyfit(lams, neffs, 2)
        ng_fit = float(np.polyval(fit, LAM) - LAM * np.polyval(np.polyder(fit), LAM))
        res.update(sweep_lam=lams, sweep_neff=neffs, sweep_ng=ngs, ng_fit=ng_fit)
        k = int(np.nanargmax(np.abs(np.diff(ngs))))  # where the solver's n_g steps the most
        lines.append(
            f"\nsweep {LAM_MIN}-{LAM_MAX} um:  n_g from the slope of n_eff(lambda) = {ng_fit:.4f}  "
            f"(quadratic fit over the whole sweep)"
        )
        lines.append(
            f"  why it differs from the solver's n_g: Lumerical interpolates the tabulated silicon index linearly between "
            f"its sample wavelengths, so the slope dn/dlambda is piecewise constant; the solver's n_g steps from "
            f"{ngs[k]:.4f} at {lams[k] * 1000:.0f} nm to {ngs[k + 1]:.4f} at {lams[k + 1] * 1000:.0f} nm."
        )
        lines.append(
            f"  the fit is one average over {lams[0] * 1000:.0f}-{lams[-1] * 1000:.0f} nm; the solver's n_g is local at "
            f"{LAM * 1000:.0f} nm and is the value used for the FSR."
        )
        print("\n".join(lines[-3:]), f"({time.time() - t0:.0f} s)", flush=True)
        m.switchtolayout()
        m.setanalysis("wavelength", LAM * um)
        m.save(str(OUT / "rib.lms"))

        # ---- 5. core width sweep: TE0 and the next TE mode ----
        if not a.no_widths:
            te0, te1, te1_core = [], [], []
            guess = N_GUESS
            for w in a.widths:
                gds_w = section_gds(
                    OUT / "rib_width_sweep.gds", doped=False, contacts=False, width=w, cellname=f"rib_w{round(w * 1000)}"
                )
                setup(m, gds_w, w, a.mesh, a.rib_mesh)
                m.setanalysis("n", guess)
                modes = guided_te_modes(m)
                te0.append(modes[0]["neff"].real if modes else np.nan)
                te1.append(modes[1]["neff"].real if len(modes) > 1 else np.nan)
                te1_core.append(modes[1]["core_fraction"] if len(modes) > 1 else np.nan)
                if modes:
                    guess = te0[-1]
                print(f"  width {w:.2f} um: TE0 {te0[-1]:.4f}  TE1 {te1[-1]:.4f}  ({time.time() - t0:.0f} s)", flush=True)
            res.update(
                widths=np.array(a.widths), width_te0=np.array(te0), width_te1=np.array(te1), width_te1_core=np.array(te1_core)
            )
            lines.append(
                "\ncore width sweep (n_eff):  "
                + ", ".join(f"{w:.2f}: TE0 {x:.3f} / TE1 {y:.3f}" for w, x, y in zip(a.widths, te0, te1, strict=True))
            )

    fsr = LAM**2 / (res["ring_ng"] * 2 * math.pi * RADIUS) * 1000
    res["fsr_nm"] = fsr
    lines.append(f"\nring of R = {RADIUS} um:  n_g = {res['ring_ng']:.4f}  ->  FSR = lambda^2 / (n_g L) = {fsr:.2f} nm")
    np.savez_compressed(OUT / "rib_passive.npz", **res)
    (OUT / "rib_passive.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(lines[-1])
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

"""Step 2 - MODE (FDE): the passive rib waveguide: effective index, group index, bend loss.

Model: a straight section of the PDK cross-section ``rib_1550nm_TE`` with the slab width of the
ring, written to GDS and loaded into a Layer Builder with cornerstone_process.lbr.  The silicon is
the process file's index-perturbation material without carriers, i.e. plain silicon.

    1. straight waveguide at 1.55 um:  n_eff, n_g
    2. wavelength sweep 1.50 - 1.60 um:  n_eff(lambda)
    3. bent waveguide for several radii:  radiation loss, overlap with the straight mode

    python passive_mode_fde.py
    python passive_mode_fde.py --radii 15 20 25 30 40

Output in 2_passive_mode_properties/:  rib_w450.gds / .lms, rib_w450_passive.npz / .txt
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
    import_lumapi,
    require_process_file,
    section_gds,
    step_dir,
    um,
)

OUT = step_dir("2_passive_mode_properties")
NAME = f"rib_w{round(WIDTH * 1000)}"
Y_SPAN, Z_SPAN = 9.0, 2.2  # FDE window (um); PML on all sides
N_GUESS = 2.6


def setup(m, gds, mesh: float) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds, 6.0, SLAB_WIDTH + 2.0)
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
    m.setanalysis("wavelength", LAM * um)
    m.setanalysis("search", "near n")
    m.setanalysis("use max index", 0)
    m.setanalysis("n", N_GUESS)
    m.setanalysis("number of trial modes", 6)
    m.setanalysis("calculate group index", 1)
    m.setanalysis("bend location", "simulation center")
    m.setanalysis("bend orientation", 0)


def mode_info(m, i: int) -> dict:
    d = f"FDE::data::mode{i}"
    intensity = sum(np.abs(np.squeeze(m.getdata(d, c))) ** 2 for c in ("Ex", "Ey", "Ez"))
    y, z = np.squeeze(m.getdata(d, "y")), np.squeeze(m.getdata(d, "z"))
    profile = intensity.sum(axis=1)
    info = dict(
        i=i,
        neff=complex(np.squeeze(m.getdata(d, "neff"))),
        te=float(np.squeeze(m.getdata(d, "TE polarization fraction"))),
        loss_dBcm=float(np.squeeze(m.getdata(d, "loss"))) / 100,
        y_centre=float((profile * y).sum() / profile.sum()) / um,
        core_fraction=float(profile[np.abs(y) < 0.5 * um].sum() / profile.sum()),
        E=intensity.astype(np.float32),
        y=y / um,
        z=z / um,
    )
    try:
        info["ng"] = float(np.real(np.squeeze(m.getdata(d, "ng"))))
    except Exception:
        info["ng"] = float("nan")
    return info


def find_te0(m) -> dict | None:
    """The guided TE0 mode: mostly TE, concentrated in the core, highest n_eff.

    The filter matters: a search near the maximum index also returns slab and PML modes.
    """
    modes = [mode_info(m, i) for i in range(1, int(m.findmodes()) + 1)]
    modes = [x for x in modes if x["te"] > 0.5 and x["core_fraction"] > 0.3]
    return max(modes, key=lambda x: x["neff"].real) if modes else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--radii", type=float, nargs="*", default=[10, 15, 20, 25, 30, 40])
    ap.add_argument("--mesh", type=float, default=0.02, help="FDE mesh step (um)")
    ap.add_argument("--points", type=int, default=11, help="wavelengths in the sweep")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = section_gds(
        OUT / f"{NAME}.gds", {"cross_section": "rib_1550nm_TE", "settings": {"width": WIDTH, "width_slab": SLAB_WIDTH}}
    )
    res = dict(width=WIDTH, lam=LAM, radii=np.array(a.radii, float))
    lines = [
        f"Rib waveguide W = {WIDTH} um, 220 nm core on a 100 nm slab (cornerstone_process.lbr); FDE mesh {a.mesh * 1000:.0f} nm"
    ]
    with lumapi.MODE(hide=True) as m:
        setup(m, gds, a.mesh)
        straight = find_te0(m)
        if straight is None:
            raise SystemExit("no guided TE0 mode found: check the Layer Builder geometry")
        m.copydcard(f"FDE::data::mode{straight['i']}", "straight_TE0")
        res.update(
            neff=straight["neff"].real, ng=straight["ng"], te=straight["te"], E=straight["E"], y=straight["y"], z=straight["z"]
        )
        lines.append(
            f"straight, {LAM} um:  n_eff = {straight['neff'].real:.5f}   n_g = {straight['ng']:.4f}   "
            f"TE fraction {straight['te']:.3f}   power in |y| < 0.5 um: {straight['core_fraction']:.2f}"
        )
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)

        # wavelength sweep: one findmodes per wavelength (the built-in sweep can jump to PML modes)
        lams = np.linspace(LAM_MIN, LAM_MAX, a.points)
        neffs = []
        for lam in lams:
            m.switchtolayout()
            m.setanalysis("wavelength", lam * um)
            mode = find_te0(m)
            neffs.append(mode["neff"].real if mode else np.nan)
        neffs = np.array(neffs)
        fit = np.polyfit(lams, neffs, 2)
        ng_fit = float(np.polyval(fit, LAM) - LAM * np.polyval(np.polyder(fit), LAM))
        res.update(sweep_lam=lams, sweep_neff=neffs, ng_fit=ng_fit)
        lines.append(
            f"sweep {LAM_MIN}-{LAM_MAX} um:  n_g from the slope of n_eff(lambda) = {ng_fit:.4f}  (cross-check of the solver's n_g)"
        )
        print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)
        m.switchtolayout()
        m.setanalysis("wavelength", LAM * um)

        # bent waveguide
        m.setanalysis("bent waveguide", 1)
        bend = {k: [] for k in ("neff", "loss_dBcm", "loss_dB_turn", "shift_nm", "overlap")}
        lines.append(f"\nbent waveguide, {LAM} um:")
        lines.append(
            f"{'R (um)':>7} {'n_eff':>9} {'radiation dB/cm':>16} {'dB / round trip':>16} {'mode shift nm':>14} {'overlap with straight':>22}"
        )
        for radius in a.radii:
            m.switchtolayout()
            m.setanalysis("bend radius", radius * um)
            b = find_te0(m)
            if b is None:
                for k in bend:
                    bend[k].append(np.nan)
                lines.append(f"{radius:7.1f}  no guided mode")
                continue
            overlap = float(np.ravel(np.squeeze(m.overlap("straight_TE0", f"FDE::data::mode{b['i']}")))[1])
            turn = b["loss_dBcm"] * 2 * math.pi * radius * 1e-4
            for k, v in (
                ("neff", b["neff"].real),
                ("loss_dBcm", b["loss_dBcm"]),
                ("loss_dB_turn", turn),
                ("shift_nm", b["y_centre"] * 1000),
                ("overlap", overlap),
            ):
                bend[k].append(v)
            if abs(radius - RADIUS) < 1e-9:
                res.update(bend_E=b["E"], bend_y=b["y"], bend_z=b["z"])
            lines.append(
                f"{radius:7.1f} {b['neff'].real:9.5f} {b['loss_dBcm']:16.4f} {turn:16.5f} {b['y_centre'] * 1000:14.1f} {overlap:22.4f}"
            )
            print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)
        res.update({f"bend_{k}": np.array(v) for k, v in bend.items()})
        m.switchtolayout()
        m.setanalysis("bent waveguide", 0)
        m.save(str(OUT / f"{NAME}.lms"))

    fsr = LAM**2 / (res["ng"] * 2 * math.pi * RADIUS) * 1000
    lines.append(f"\nring of R = {RADIUS} um:  FSR = lambda^2 / (n_g L) = {fsr:.2f} nm")
    np.savez(OUT / f"{NAME}_passive.npz", **res)
    (OUT / f"{NAME}_passive.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(lines[-1])
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

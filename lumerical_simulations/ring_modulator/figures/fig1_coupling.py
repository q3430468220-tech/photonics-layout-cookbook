"""Figure 1 - FDTD: how much light crosses from the bus into the ring.

    a  field in the coupling region (logarithmic), with the waveguide outlines and the four ports
    b  power coupling kappa^2 versus gap at the design wavelength, with the exponential fit and the critical-coupling point
    c  kappa^2 versus wavelength for every simulated gap, marked at the design wavelength

The table (coupling_vs_gap.csv) holds the powers interpolated to the design wavelength.  Its arm_transmission
is NaN when the run had no reference arm: then kappa^2 is the raw |S41|^2, and the figure says so.

Reads 1_coupling_coefficient/*.npz, coupling_vs_gap.csv and, if present, the result of step 6.

    python fig1_coupling.py            ->  figures/fig1_coupling.png
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
sys.path.insert(0, str(ROOT.parents[1]))
import figstyle as fs  # noqa: E402

STEP = ROOT / "1_coupling_coefficient"
LAM = 1.55  # um, design wavelength
LAM_NM = round(LAM * 1000)  # nm
FIELD_GAP_NM = 300  # the gap whose field map is shown


def load() -> dict:
    """Everything the panels need: the table, the spectra de-embedded with the table's arm, the field maps."""
    if not (STEP / "coupling_vs_gap.csv").exists():
        raise SystemExit("run scripts/coupling_coefficient_fdtd.py first")
    with open(STEP / "coupling_vs_gap.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    d = dict(gap_nm=np.array([float(r["gap_um"]) for r in rows]) * 1000, kappa2=np.array([float(r["kappa2"]) for r in rows]),
             t2=np.array([float(r["t2_S21"]) for r in rows]))  # fmt: skip
    arm = float(rows[0]["arm_transmission"])  # the same in every row; NaN when there was no reference run
    d.update(arm=arm, deembedded=not math.isnan(arm))
    half_arm = math.sqrt(arm) if d["deembedded"] else 1.0
    if len(rows) > 1:  # a line through one point says nothing
        slope, intercept = np.polyfit(d["gap_nm"], np.log(d["kappa2"]), 1)
        d.update(fit_A=float(np.exp(intercept)), fit_g0=float(-1 / slope))
    d["runs"] = {}
    for path in sorted(STEP.glob("coupler_gap*.npz")):
        r = np.load(path, allow_pickle=True)
        order = np.argsort(r["lam"])
        lam_nm = np.asarray(r["lam"])[order] * 1000
        kappa2 = np.abs(np.asarray(r["S4"])[order]) ** 2 / half_arm
        d["runs"][round(float(r["gap"]) * 1000)] = dict(
            lam_nm=lam_nm, kappa2=kappa2, kappa2_design=float(np.interp(LAM_NM, lam_nm, kappa2)),
            x=r["field_x"], y=r["field_y"], E=r["field_E"],
            y_bus=float(r["y_bus"]), y_arm=float(r["y_arm"]), x_port=float(r["x_port"]), gds=path.with_suffix(".gds"),
        )  # fmt: skip
    step6 = ROOT / "6_interconnect_ring_modulator" / "ring_modulator.npz"
    if step6.exists():
        r6 = np.load(step6)
        d.update(k2_critical=float(r6["k2_critical"]), gap_critical_nm=float(r6["gap_critical"]) * 1000)
    return d


def _core_outlines(gds: Path) -> list[np.ndarray]:
    """Outlines of the waveguide cores (layer 1/0) of a coupler layout, in um."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds))
    region = kdb.Region(layout.top_cell().begin_shapes_rec(layout.layer(1, 0))).merged()
    return [np.array([(p.x * layout.dbu, p.y * layout.dbu) for p in poly.each_point_hull()]) for poly in region.each()]


def panel_field(fig, ax, d: dict, gap_nm: int = FIELD_GAP_NM, colorbar: bool = True) -> None:
    run = d["runs"][gap_nm if gap_nm in d["runs"] else sorted(d["runs"])[len(d["runs"]) // 2]]
    intensity = 20 * np.log10(np.maximum(run["E"] / run["E"].max(), 1e-6))
    image = ax.pcolormesh(run["x"], run["y"], intensity.T, cmap=fs.CMAP_FIELD, vmin=-40, vmax=0, shading="auto", rasterized=True)
    for outline in _core_outlines(run["gds"]):
        ax.plot(*np.vstack([outline, outline[:1]]).T, color=fs.INK, lw=0.3, alpha=0.55)
    ax.set_xlim(run["x"].min(), run["x"].max())
    ax.set_ylim(run["y"].min(), run["y"].max())
    fs.image_axes(ax, "x (µm)", "y (µm)")
    x, yb, ya = run["x_port"], run["y_bus"], run["y_arm"]
    for label, px, py in (("1", -x, yb), ("2", x, yb), ("3", -x, ya), ("4", x, ya)):
        ax.plot([px, px], [py - 1.0, py + 1.0], color=fs.ORANGE, lw=1.0, solid_capstyle="butt")
        ax.text(
            px + (0.45 if px < 0 else -0.45),
            py + 1.0,
            f"port {label}",
            color=fs.INK,
            fontsize=6,
            va="top",
            ha="left" if px < 0 else "right",
        )
    ax.annotate(
        "",
        xy=(-x + 2.6, yb - 0.9),
        xytext=(-x + 0.5, yb - 0.9),
        arrowprops=dict(arrowstyle="-|>", color=fs.INK, lw=0.6, mutation_scale=6),
    )
    ax.text(-x + 2.9, yb - 0.9, "TE0 in", fontsize=6, va="center")
    ax.text(
        0,
        ya + 0.9,
        f"ring arm (R = 10 µm at the coupling point), gap {gap_nm} nm",
        fontsize=6,
        ha="center",
        va="bottom",
        color=fs.SECONDARY,
    )
    if colorbar:
        fs.colorbar_beside(ax, image, "|E|² (dB)", width=0.012, pad=0.012, ticks=[-40, -30, -20, -10, 0])


def panel_kappa_gap(ax, d: dict) -> None:
    gaps = np.linspace(d["gap_nm"].min() - 30, d["gap_nm"].max() + 30, 200)
    notes = []
    if "fit_A" in d:
        ax.semilogy(gaps, d["fit_A"] * np.exp(-gaps / d["fit_g0"]), color=fs.MUTED, lw=0.8, zorder=1)
        lo, hi = d["gap_nm"].min(), d["gap_nm"].max()
        notes += [f"κ² = {d['fit_A']:.2f} · exp(−gap / {d['fit_g0']:.1f} nm)",
                  f"fitted for {lo:.0f} to {hi:.0f} nm; do not extrapolate"]  # fmt: skip
    ax.semilogy(d["gap_nm"], d["kappa2"], "o", color=fs.BLUE, ms=4, zorder=3)
    ax.set_ylim(top=ax.get_ylim()[1] * 3)  # headroom above the data for the note stack
    ax.set_xlabel("gap (nm)")
    ax.set_ylabel("power coupling κ²")
    ax.set_xlim(gaps.min(), gaps.max())
    balance = d["kappa2"] + d["t2"]
    notes.append(f"κ² + t² = {balance.min():.4f} … {balance.max():.4f}")
    if d["deembedded"]:
        notes.append(f"κ² = |S41|² / sqrt(T_arm), T_arm = {d['arm']:.4f} at {LAM_NM} nm")
    else:
        notes.append("no arm de-embedding: κ² is the raw |S41|²")
    for i, text in enumerate(notes):
        fs.note(ax, text, (0.97, 0.93 - 0.09 * i), ha="right", transform=ax.transAxes)
    if "k2_critical" in d:
        ax.plot([gaps.min(), d["gap_critical_nm"], d["gap_critical_nm"]], [d["k2_critical"], d["k2_critical"], ax.get_ylim()[0]],
                color=fs.ORANGE, lw=0.8, zorder=2)  # fmt: skip
        ax.plot(d["gap_critical_nm"], d["k2_critical"], "o", color=fs.ORANGE, ms=4, zorder=4)
        fs.note(ax, f"critical coupling\nκ² = {d['k2_critical']:.4f}, gap {d['gap_critical_nm']:.0f} nm",
                (d["gap_critical_nm"], d["k2_critical"]), xytext=(d["gap_critical_nm"] - 150, d["k2_critical"] / 3.2), ha="left", va="center")  # fmt: skip


def panel_kappa_spectrum(ax, d: dict) -> None:
    gaps = sorted(d["runs"], reverse=True)  # the largest gap is the lightest line
    for gap, color in zip(gaps, fs.sweep_colors(len(gaps)), strict=True):
        run = d["runs"][gap]
        ax.semilogy(run["lam_nm"], run["kappa2"], color=color)
        ax.plot(LAM_NM, run["kappa2_design"], "o", color=color, ms=2.5, zorder=3)  # the value in the table
        ax.text(run["lam_nm"].max() + 1.5, run["kappa2"][-1], f"{gap} nm", fontsize=6, va="center", color=fs.INK)
    ax.set_xlim(1500, 1600)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("power coupling κ²")
    ax.axvline(LAM_NM, color=fs.HAIRLINE, lw=0.5, zorder=0)
    fs.note(ax, "gap", (1.02, 1.0), ha="left", va="bottom", transform=ax.transAxes)


def main() -> None:
    d = load()
    fig, axes = fs.mosaic(fs.DOUBLE, 106, [["a", "a"], ["b", "c"]], height_ratios=[1.22, 1.0], width_ratios=[1, 1.15])
    panel_field(fig, axes["a"], d)
    panel_kappa_gap(axes["b"], d)
    panel_kappa_spectrum(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig1_coupling.png"))


if __name__ == "__main__":
    main()

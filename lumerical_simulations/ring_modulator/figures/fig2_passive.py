"""Figure 2 - MODE: the passive rib waveguide carries one TE mode, bends freely at 10 um, and is single-mode up to a width.

    a  straight TE0 intensity (linear), with the rib outline, n_eff and n_g
    b  the same mode bent to the ring radius: it moves outwards, with the ring centre and the centroid shift
    c  n_eff versus wavelength: group index from the slope, the solver n_g and the free spectral range of the ring
    d  bend radiation loss versus radius, with the solver floor
    e  n_eff of TE0 and TE1 versus core width, against the fundamental TE mode of the 90 nm slab

Reads 2_passive_mode_properties/rib_passive.npz.

    python fig2_passive.py            ->  figures/fig2_passive.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
sys.path.insert(0, str(ROOT.parents[1]))
import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402

DATA = ROOT / "2_passive_mode_properties" / "rib_passive.npz"
N_SI, N_SIO2 = 3.4764, 1.444  # slab reference: silicon between silica
FLOOR = 1e-3  # dB/cm: bend losses at or below this are the solver noise floor
WINDOW_Y, WINDOW_Z = (-1.5, 1.5), (-0.5, 0.75)  # um, panels a and b
CORE_CENTRE = 0.0  # y of the waveguide core, um
NEFF_LABEL = "n$_{\\mathrm{eff}}$"
NG_LABEL = "n$_{\\mathrm{g}}$"


def load() -> dict:
    """Every array and scalar of the passive-mode run, by its key."""
    if not DATA.exists():
        raise SystemExit("run the passive mode solver (2_passive_mode_properties) first")
    with np.load(DATA) as npz:
        return {key: npz[key] for key in npz.files}


def slab_te0_index(thickness: float, wavelength: float, n_core: float = N_SI, n_clad: float = N_SIO2) -> float:
    """n_eff of the fundamental TE mode of a symmetric three-layer slab.

    With u^2 + w^2 = V^2 and u tan(u) = w, the mode is the root of u tan(u) - w in (0, V); found by bisection.
    """
    k0 = 2 * np.pi / wavelength
    half = k0 * thickness / 2
    v = half * np.sqrt(n_core**2 - n_clad**2)

    def g(u: float) -> float:
        return u * np.tan(u) - np.sqrt(v * v - u * u)

    lo, hi = 1e-9, v * (1 - 1e-12)
    for _ in range(100):
        mid = (lo + hi) / 2
        if g(lo) * g(mid) <= 0:
            hi = mid
        else:
            lo = mid
    w = np.sqrt(v * v - ((lo + hi) / 2) ** 2)
    return float(np.sqrt(n_clad**2 + (w / half) ** 2))


def centroid(e: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple[float, float]:
    """Intensity-weighted centre of a mode map indexed [y, z], in um.

    The mesh is not uniform, so each cell is weighted by its area (np.gradient gives the cell widths).
    """
    weight = e * np.outer(np.gradient(y), np.gradient(z))
    weight = weight / weight.sum()
    return float((weight.sum(axis=1) * y).sum()), float((weight.sum(axis=0) * z).sum())


def signed(value: float, fmt: str) -> str:
    """Number with a typographic minus sign."""
    return format(value, fmt).replace("-", "−")


def _mode_map(ax, y: np.ndarray, z: np.ndarray, e: np.ndarray, width: float):
    """Normalised intensity of a mode with the rib outline, in the shared window."""
    image = ax.pcolormesh(y, z, (e / e.max()).T, cmap=fs.CMAP_FIELD, vmin=0, vmax=1, shading="auto", rasterized=True)
    ax.set_xlim(*WINDOW_Y)
    ax.set_ylim(*WINDOW_Z)
    fs.image_axes(ax, "y (µm)", "z (µm)")
    fs.rib_outline(ax, width, t.T_SI, t.T_SLAB90, t.RIB_SLAB_WIDTH, y0=CORE_CENTRE, color=fs.INK, lw=0.5)
    return image


def panel_straight(ax, d: dict):
    image = _mode_map(ax, d["y"], d["z"], d["E"], float(d["width"]))
    text = f"straight, TE0, {1000 * float(d['lam']):.0f} nm\n{NEFF_LABEL} = {float(d['neff']):.3f},  {NG_LABEL} = {float(d['ng']):.3f}"
    fs.note(ax, text, (0.03, 0.97), ha="left", va="top", transform=ax.transAxes)
    return image


def panel_bent(ax, d: dict):
    radii = d["radii"]
    idx = int(np.argmin(np.abs(radii - float(d["radius"]))))
    e, y, z = d["ring_E"], d["ring_y"], d["ring_z"]
    image = _mode_map(ax, y, z, e, float(d["width"]))
    ax.axvline(CORE_CENTRE, color=fs.MUTED, lw=0.5, zorder=3)
    cy, cz = centroid(e, y, z)
    ax.plot(cy, cz, "o", color=fs.ORANGE, ms=3, mew=0, zorder=5)
    ax.annotate("", xy=(1.2, 0.5), xytext=(0.4, 0.5),
                arrowprops=dict(arrowstyle="-|>", color=fs.INK, lw=0.6, mutation_scale=6))  # fmt: skip
    ax.text(0.8, 0.56, "ring centre", ha="center", va="bottom", fontsize=6, color=fs.INK)
    shift = signed(float(d["bend_shift_nm"][idx]), ".0f")
    fs.note(ax, f"R = {float(radii[idx]):.0f} µm: centroid shift {shift} nm, outwards", (-1.45, -0.42), ha="left", va="bottom")
    return image


def panel_dispersion(ax, d: dict) -> None:
    lam, neff = d["sweep_lam"] * 1000, d["sweep_neff"]
    ax.axvline(float(d["lam"]) * 1000, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(lam, neff, "o-", color=fs.BLUE, ms=3, lw=1, zorder=2, clip_on=False)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_xticks([1500, 1550, 1600])
    ax.set_ylim(2.45, 2.70)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel(f"effective index {NEFF_LABEL}")
    text = (
        f"{NG_LABEL}, slope over {lam.min():.0f} to {lam.max():.0f} nm = {float(d['ng_fit']):.3f}\n"
        f"{NG_LABEL}, solver at {float(d['lam']) * 1000:.0f} nm = {float(d['ng']):.3f}\n"
        f"FSR, R = {float(d['radius']):.0f} µm ring = {float(d['fsr_nm']):.1f} nm"
    )
    fs.note(ax, text, (0.97, 0.97), ha="right", va="top", transform=ax.transAxes)


def panel_bend(ax, d: dict) -> None:
    r, loss = d["radii"], d["bend_loss_dBcm"]
    above = loss > FLOOR
    below = ~above
    ax.axhspan(2e-4, FLOOR, color=fs.HAIRLINE, alpha=0.5, lw=0, zorder=0)
    ax.axvline(float(d["radius"]), color=fs.MUTED, lw=0.5, zorder=1)
    ax.semilogy(r[above], loss[above], "o-", color=fs.BLUE, ms=3.5, lw=1, zorder=3)
    ax.semilogy(r[below], np.full(int(np.sum(below)), FLOOR), "o", mfc=fs.SURFACE, mec=fs.BLUE, mew=0.8,
                ms=3.5, zorder=3)  # fmt: skip
    for x, v in zip(r[above], loss[above], strict=True):
        ax.text(x + 0.4, v, signed(v, ".1f" if v >= 1 else ".2f"), va="center", fontsize=6, color=fs.INK)
    ax.text(
        float(d["radius"]) + 0.4, 25, f"design R = {float(d['radius']):.0f} µm", ha="left", va="top", fontsize=6, color=fs.INK
    )
    ax.text(14.5, 4e-4, "below solver floor", ha="center", va="center", fontsize=6, color=fs.SECONDARY)
    ax.set_xlim(3, 21.5)
    ax.set_ylim(2e-4, 30)
    ax.set_xticks([4, 8, 12, 16, 20])
    ax.set_xlabel("bend radius (µm)")
    ax.set_ylabel("bend loss (dB cm$^{-1}$)")


def te1_note(w: np.ndarray, te1: np.ndarray, slab_neff: float) -> str:
    """Where the second TE mode is guided by the rib: its index must lie above the fundamental mode of the slab."""
    guided = np.isfinite(te1) & (te1 > slab_neff)
    if not guided.any():
        return "no TE1 above the slab mode"
    k = int(np.argmax(guided))
    return f"TE1 above the slab mode from {w[k]:.0f} nm\n({te1[k] - slab_neff:.3f} above it there)"


def panel_width(ax, d: dict, slab_neff: float) -> None:
    w = d["widths"] * 1000
    te0, te1 = d["width_te0"], d["width_te1"]
    has_te1 = np.isfinite(te1)
    ax.axhline(slab_neff, color=fs.MUTED, lw=0.8, zorder=1)
    ax.axvline(float(d["width"]) * 1000, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(w, te0, "o-", color=fs.BLUE, ms=3, lw=1, zorder=3)
    ax.plot(w[has_te1], te1[has_te1], "o-", color=fs.ORANGE, ms=3, lw=1, zorder=3)
    ax.set_xlim(270, 880)
    ax.set_ylim(2.05, 2.80)
    ax.set_xticks([300, 400, 500, 600, 700, 800])
    ax.text(w[-1] + 12, te0[-1], "TE0", va="center", fontsize=6, color=fs.INK)
    ax.text(w[-1] + 12, te1[-1], "TE1", va="center", fontsize=6, color=fs.INK)
    ax.text(
        860, slab_neff - 0.012, f"{t.T_SLAB90 * 1000:.0f} nm slab (TE0)", ha="right", va="top", fontsize=6, color=fs.SECONDARY
    )
    ax.text(
        float(d["width"]) * 1000 + 8,
        2.42,
        f"design {float(d['width']) * 1000:.0f} nm",
        ha="left",
        va="center",
        fontsize=6,
        color=fs.SECONDARY,
    )
    fs.note(
        ax,
        te1_note(w, te1, slab_neff),
        (0.03, 0.97),
        ha="left",
        va="top",
        transform=ax.transAxes,
        bbox=dict(fc="white", ec="none", pad=0.6),
        zorder=4,
    )
    ax.set_xlabel("core width (nm)")
    ax.set_ylabel(f"effective index {NEFF_LABEL}")


def main() -> None:
    d = load()
    slab_neff = slab_te0_index(t.T_SLAB90, float(d["lam"]))
    fig, axes = fs.mosaic(
        fs.DOUBLE, 112, [["a", "a", "a", "b", "b", "b"], ["c", "c", "d", "d", "e", "e"]], height_ratios=[1.0, 1.1]
    )
    image = panel_straight(axes["a"], d)
    panel_bent(axes["b"], d)
    fs.colorbar_beside(axes["b"], image, "|E|² (normalised)", ticks=[0, 0.5, 1])
    panel_dispersion(axes["c"], d)
    panel_bend(axes["d"], d)
    panel_width(axes["e"], d, slab_neff)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig2_passive.png"))


if __name__ == "__main__":
    main()

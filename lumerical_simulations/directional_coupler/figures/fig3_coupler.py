"""Figure 3 - FDTD: the coupler as drawn splits 50:50 at the design wavelength, and only there.

    a  |E| in the device: the light moves from the lower waveguide to the upper one, and half has crossed at the end
    b  power in the cross and the through port against wavelength
    c  loss and back-reflection against wavelength

Reads 3_coupler_fdtd/coupler_fdtd.npz and the layout 3_coupler_fdtd/directional_coupler.gds.

    python fig3_coupler.py            ->  figures/fig3_coupler.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/directional_coupler/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

STEP = ROOT / "3_coupler_fdtd"


def main() -> None:
    d = panels.load(STEP / "coupler_fdtd.npz")
    lam = d["lam"] * 1000
    back, cross, through = (np.abs(d[f"S{k}"]) ** 2 for k in "134")
    total = cross + through
    design = 1550.0
    at = lambda values: float(np.interp(design, lam, values))  # noqa: E731
    fig, axes = fs.mosaic(fs.DOUBLE, 98, [["a", "a"], ["b", "c"]], gridspec_kw=dict(height_ratios=[0.8, 1]))

    ax = axes["a"]
    image = panels.field_map(ax, d["field_x"], d["field_y"], d["field_E"], STEP / "directional_coupler.gds", ylim=(-3.4, 3.4))
    ax.set_aspect("equal")
    fs.colorbar_beside(ax, image, "|E| (normalised)", width=0.012, pad=0.012, ticks=[0, 0.5, 1])
    x_port = float(d["field_x"].max())
    for text, x, y, ha in (
        ("in", -x_port, -float(d["port_y"]), "left"),
        ("through", x_port, -float(d["port_y"]), "right"),
        ("cross", x_port, float(d["port_y"]), "right"),
    ):
        ax.text(x + (0.4 if ha == "left" else -0.4), y + 0.75, text, ha=ha, va="bottom", fontsize=6, color=fs.INK)
    text = f"gap {float(d['gap']) * 1000:.0f} nm, straight section {float(d['length']):.1f} µm, {design:.0f} nm"
    fs.note(ax, text, (0.5, 0.94), ha="center", va="top", transform=ax.transAxes)

    ax = axes["b"]
    ax.axhline(0.5, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.axvline(design, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(lam, cross, color=fs.BLUE, lw=1.2, zorder=3)
    ax.plot(lam, through, color=fs.ORANGE, lw=1.2, zorder=3)
    ax.text(lam.max() + 2, cross[-1], "cross", va="center", fontsize=6, color=fs.INK)
    ax.text(lam.max() + 2, through[-1], "through", va="center", fontsize=6, color=fs.INK)
    ax.set_xlim(lam.min(), lam.max() + 16)
    ax.set_xticks([1500, 1525, 1550, 1575, 1600])
    ax.set_ylim(0.2, 0.8)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("power")
    lam_half = float(d["lam_half"]) * 1000
    slope = float(np.polyfit(lam, cross / total, 1)[0]) * 100
    text = f"at {design:.0f} nm: {100 * at(cross):.1f} % cross, {100 * at(through):.1f} % through\nequal at {lam_half:.0f} nm\nthe split moves {slope:.2f} points per nm"
    fs.note(ax, text, (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)

    ax = axes["c"]
    ax.axvline(design, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(lam, panels.decibel(total), color=fs.BLUE, lw=1.2, zorder=3)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_xticks([1500, 1525, 1550, 1575, 1600])
    ax.set_ylim(0, max(0.05, float(panels.decibel(total).max()) * 1.6))
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("loss (dB)")
    right = ax.twinx()
    right.plot(lam, 10 * np.log10(back), color=fs.MUTED, lw=0.8, zorder=2)
    right.set_ylabel("back-reflection (dB)", color=fs.SECONDARY)
    right.spines["right"].set_visible(True)
    right.tick_params(colors=fs.SECONDARY)
    right.set_ylim(-70, -30)
    text = f"loss at {design:.0f} nm: {float(panels.decibel(at(total))):.3f} dB\nreflection (grey, right): {panels.minus(10 * np.log10(at(back)), '.0f')} dB"
    fs.note(ax, text, (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)

    for letter in "abc":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig3_coupler.png")


if __name__ == "__main__":
    main()

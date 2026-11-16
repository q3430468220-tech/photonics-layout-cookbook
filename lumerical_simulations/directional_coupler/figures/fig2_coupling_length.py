"""Figure 2 - FDTD: four lengths fix the coupler: the cross-over length, what the bends add, and the 50:50 length.

    a  fraction of the light that crosses against the length of the straight section: FDTD points, the sin^2 fit,
       and the same curve from the supermodes of step 1 (no bends)
    b  the same fraction against wavelength, one line per length

Reads 2_coupling_length/coupling_length.npz.

    python fig2_coupling_length.py            ->  figures/fig2_coupling_length.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/directional_coupler/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "2_coupling_length" / "coupling_length.npz"


def crossing(length, l_pi: float, l_bends: float):
    return np.sin(np.pi / 2 * (np.asarray(length) + l_bends) / l_pi) ** 2


def main() -> None:
    d = panels.load(DATA)
    l_pi, l_bends, l_half = float(d["l_pi"]), float(d["l_bends"]), float(d["l_half"])
    fig, axes = fs.mosaic(fs.DOUBLE, 64, [["a", "b"]], gridspec_kw=dict(width_ratios=[1.2, 1]))

    ax = axes["a"]
    grid = np.linspace(0.0, l_pi - l_bends, 200)
    ax.axhline(0.5, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(
        grid,
        crossing(grid, float(d["l_pi_supermodes"]), 0.0),
        color=fs.MUTED,
        lw=0.8,
        ls=(0, (3, 2)),
        zorder=2,
        label="supermodes of step 1, no bends",
    )
    ax.plot(grid, crossing(grid, l_pi, l_bends), color=fs.BLUE, lw=1.2, zorder=3, label="fit to the FDTD points")
    ax.plot(d["lengths"], d["fraction"], "o", color=fs.BLUE, ms=4, zorder=4, label="FDTD, whole layout")
    ax.plot(l_half, 0.5, "o", mfc=fs.SURFACE, mec=fs.INK, mew=0.8, ms=5, zorder=5)
    ax.set_xlim(-1.5, 34)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("length of the straight section (µm)")
    ax.set_ylabel("fraction that crosses")
    ax.legend(loc="lower right")
    fs.note(ax, f"50:50 at {l_half:.1f} µm", (l_half - 0.9, 0.53), ha="right", va="bottom")
    text = f"L$_{{\\pi}}$ = {l_pi:.1f} µm\nthe bends are worth {l_bends:.1f} µm"
    fs.note(ax, text, (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)
    k = int(np.argmin(d["lengths"]))
    fs.note(
        ax,
        f"{100 * float(d['fraction'][k]):.1f} % cross\nin the bends alone",
        (float(d["lengths"][k]), float(d["fraction"][k]) + 0.02),
        xytext=(3.0, 0.30),
        ha="left",
        va="bottom",
    )

    ax = axes["b"]
    lam = d["sweep_lam"] * 1000
    fraction = d["cross_lam"] / (d["cross_lam"] + d["through_lam"])
    ax.axhline(0.5, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.axvline(float(d["lam"]) * 1000, color=fs.HAIRLINE, lw=0.5, zorder=0)
    for row, length, colour in zip(fraction, d["lengths"], fs.sweep_colors(len(d["lengths"])), strict=True):
        ax.plot(lam, row, color=colour, lw=1.0, zorder=3)
        ax.text(lam.max() + 2, row[-1], f"{length:.0f} µm", va="center", fontsize=6, color=fs.INK)
    ax.set_xlim(lam.min(), lam.max() + 14)
    ax.set_xticks([1500, 1550, 1600])
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("fraction that crosses")
    fs.note(
        ax,
        "more crosses at longer wavelengths:\nthe mode reaches further into the gap",
        (0.03, 0.96),
        ha="left",
        va="top",
        transform=ax.transAxes,
        bbox=dict(fc=fs.SURFACE, ec="none", pad=0.6),
        zorder=4,
    )

    for letter in "ab":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig2_coupling_length.png")


if __name__ == "__main__":
    main()

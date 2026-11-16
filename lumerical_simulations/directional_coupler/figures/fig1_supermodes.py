"""Figure 1 - MODE: two coupled strips share an even and an odd supermode; their index difference sets the cross-over length.

    a  intensity of the even supermode: the light fills the gap
    b  intensity of the odd supermode: a zero in the middle of the gap
    c  cross-over length L_pi against the gap, with the exponential fit
    d  L_pi against wavelength at the gap of the device

Reads 1_supermodes/supermodes.npz.

    python fig1_supermodes.py            ->  figures/fig1_supermodes.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.ticker import NullFormatter

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/directional_coupler/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import NEFF, fs  # noqa: E402

DATA = ROOT / "1_supermodes" / "supermodes.npz"
WINDOW_Y, WINDOW_Z = (-1.3, 1.3), (-0.42, 0.64)  # um, panels a and b


def main() -> None:
    d = panels.load(DATA)
    gap, width, lam = float(d["gap"]), float(d["width"]), float(d["lam"]) * 1000
    fig, axes = fs.mosaic(fs.DOUBLE, 70, [["a", "c", "d"], ["b", "c", "d"]], gridspec_kw=dict(width_ratios=[1.15, 1, 0.8]))

    def outline(ax):
        for sign in (+1, -1):
            panels.strip_outline(ax, width, sign * (width + gap) / 2)

    image = panels.mode_map(
        axes["a"], d["y"], d["z"], d["E_even"], WINDOW_Y, WINDOW_Z, f"even,  {NEFF} = {float(d['n_even']):.4f}", outline
    )
    axes["a"].set_xlabel("")
    axes["a"].tick_params(labelbottom=False)
    panels.mode_map(axes["b"], d["y"], d["z"], d["E_odd"], WINDOW_Y, WINDOW_Z, f"odd,  {NEFF} = {float(d['n_odd']):.4f}", outline)
    bar = fig.colorbar(image, ax=[axes["a"], axes["b"]], fraction=0.035, pad=0.02, aspect=26, ticks=[0, 0.5, 1])
    bar.set_label("|E|² (normalised)", fontsize=6, labelpad=2)
    bar.ax.tick_params(labelsize=6, length=2, width=0.5)
    bar.outline.set_linewidth(0.5)

    ax = axes["c"]
    gaps, l_pi = d["gaps"] * 1000, d["gap_l_pi"]
    grid = np.linspace(gaps.min(), gaps.max(), 50)
    ax.semilogy(grid, float(d["fit_l0"]) * np.exp(grid / float(d["fit_decay_nm"])), color=fs.MUTED, lw=0.8, zorder=2)
    ax.semilogy(gaps, l_pi, "o", color=fs.BLUE, ms=3.5, zorder=3)
    ax.plot(gap * 1000, float(d["l_pi"]), "o", mfc=fs.SURFACE, mec=fs.INK, mew=0.8, ms=6, zorder=2)
    for g, value in zip(gaps, l_pi, strict=True):
        ax.text(g + 9, value * 0.9, f"{value:.0f}", ha="left", va="top", fontsize=6, color=fs.INK)
    ax.set_xlim(170, 545)
    ax.set_ylim(20, 800)
    ax.set_yticks([30, 100, 300])
    ax.set_yticklabels(["30", "100", "300"])
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("gap (nm)")
    ax.set_ylabel("cross-over length L$_{\\pi}$ (µm)")
    text = f"L$_{{\\pi}}$ = λ / 2 ({NEFF}$_{{,even}}$ − {NEFF}$_{{,odd}}$)\ngrows e-fold every {float(d['fit_decay_nm']):.0f} nm of gap"
    fs.note(ax, text, (0.04, 0.96), ha="left", va="top", transform=ax.transAxes)
    fs.note(ax, f"device: gap {gap * 1000:.0f} nm", (gap * 1000 + 14, float(d["l_pi"]) * 0.62), ha="left", va="center")

    ax = axes["d"]
    ax.axvline(lam, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(d["sweep_lam"] * 1000, d["sweep_l_pi"], "o-", color=fs.BLUE, ms=3, lw=1, zorder=3, clip_on=False)
    ax.set_xlim(1500, 1600)
    ax.set_xticks([1500, 1550, 1600])
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("L$_{\\pi}$ (µm)")
    change = (float(d["sweep_l_pi"][-1]) / float(d["sweep_l_pi"][0]) - 1) * 100
    fs.note(
        ax,
        f"gap {gap * 1000:.0f} nm\n{panels.minus(change, '.0f')} % over the band",
        (0.96, 0.96),
        ha="right",
        va="top",
        transform=ax.transAxes,
    )

    for letter in "abcd":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig1_supermodes.png")


if __name__ == "__main__":
    main()

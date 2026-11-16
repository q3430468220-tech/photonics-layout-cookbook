"""Figure 2 - EME: a taper that is too short scatters the light into higher modes; from 17 um on it passes 99 %.

    a  |E| in a taper of 3 um: part of the light goes into higher modes, which beat along the wide waveguide
    b  |E| in the taper of the device, 20 um: the mode widens with the waveguide
    c  power that arrives in TE0 of the wide waveguide against the taper length, and the same sweep with half the modes

Reads 2_taper/taper.npz.

    python fig2_taper.py            ->  figures/fig2_taper.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/strip_waveguide/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "2_taper" / "taper.npz"
X_SHOWN = (-11.0, 11.0)  # um: both layouts are simulated over this stretch of x
Y_SHOWN = (-2.6, 2.6)


def outline(ax, length: float, narrow: float, wide: float) -> None:
    """The silicon seen from above: input waveguide, taper centred on x = 0, wide waveguide."""
    half = length / 2
    upper = [(X_SHOWN[0], narrow / 2), (-half, narrow / 2), (half, wide / 2), (X_SHOWN[1], wide / 2)]
    for sign in (+1, -1):
        ax.plot([p[0] for p in upper], [sign * p[1] for p in upper], color=fs.INK, lw=0.4, zorder=4)


def field_panel(ax, x, y, e, length: float, d: dict, text: str):
    image = panels.field_map(ax, x, y, e, xlim=X_SHOWN, ylim=Y_SHOWN)
    outline(ax, length, float(d["width"]), float(d["wide_width"]))
    fs.note(ax, text, (0.02, 0.94), ha="left", va="top", transform=ax.transAxes)
    return image


def main() -> None:
    d = panels.load(DATA)
    device, short = float(d["taper_length"]), float(d["short_length"])
    fig, axes = fs.mosaic(fs.DOUBLE, 62, [["a", "c"], ["b", "c"]], gridspec_kw=dict(width_ratios=[1.25, 1]))

    field_panel(
        axes["a"],
        d["short_x"],
        d["short_y"],
        d["short_E"],
        short,
        d,
        f"taper {short:.0f} µm:  {100 * float(d['short_T']):.0f} % stays in TE0",
    )
    axes["a"].set_xlabel("")
    axes["a"].tick_params(labelbottom=False)
    image = field_panel(
        axes["b"],
        d["field_x"],
        d["field_y"],
        d["field_E"],
        device,
        d,
        f"taper {device:.0f} µm:  {100 * float(d['T_device']):.1f} % stays in TE0",
    )
    bar = fig.colorbar(image, ax=[axes["a"], axes["b"]], fraction=0.03, pad=0.015, aspect=30, ticks=[0, 0.5, 1])
    bar.set_label("|E| (normalised)", fontsize=6, labelpad=2)
    bar.ax.tick_params(labelsize=6, length=2, width=0.5)
    bar.outline.set_linewidth(0.5)

    ax = axes["c"]
    length, T = d["sweep_length"], d["sweep_T"]
    ax.axhline(float(d["target"]), color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.axvline(device, color=fs.MUTED, lw=0.5, zorder=1)
    if "check_T" in d:
        ax.plot(length, d["check_T"], color=fs.ORANGE, lw=0.8, zorder=2, label=f"{int(d['check_modes'])} modes per cell")
    ax.plot(length, T, color=fs.BLUE, lw=1.2, zorder=3, label=f"{int(d['modes'])} modes per cell")
    ax.plot(
        [short, device], [float(d["short_T"]), float(d["T_device"])], "o", mfc=fs.SURFACE, mec=fs.INK, mew=0.8, ms=4, zorder=5
    )
    ax.set_xlim(0, float(length.max()))
    ax.set_ylim(0.4, 1.02)
    ax.set_xlabel("taper length (µm)")
    ax.set_ylabel("power in TE0 of the wide waveguide")
    ax.legend(loc="lower right")
    fs.note(
        ax,
        f"{100 * float(d['target']):.0f} % from {float(d['length_target']):.1f} µm",
        (float(length.max()) - 0.5, float(d["target"]) - 0.012),
        ha="right",
        va="top",
    )
    fs.note(ax, f"device, {device:.0f} µm", (device + 0.6, 0.62), ha="left", va="center")
    fs.note(ax, "a", (short + 0.9, float(d["short_T"])), ha="left", va="center", color=fs.INK, fontweight="bold")
    fs.note(ax, "b", (device + 0.9, float(d["T_device"]) - 0.035), ha="left", va="center", color=fs.INK, fontweight="bold")
    ripple = float(np.max(T[length >= float(d["length_target"])]) - np.min(T[length >= float(d["length_target"])]))
    fs.note(
        ax,
        f"ripple beyond that: {100 * ripple:.1f} %",
        (float(length.max()) - 0.5, float(d["target"]) - 0.055),
        ha="right",
        va="top",
    )

    for letter in "abc":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig2_taper.png")


if __name__ == "__main__":
    main()

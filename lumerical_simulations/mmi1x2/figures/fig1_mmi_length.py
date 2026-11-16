"""Figure 1 - EME: the multimode section images the input onto the two outputs at one length, 5.5 um.

    a  |E| in the device as drawn: the input spreads, and two images form at the output face
    b  power into the two outputs against the length of the multimode section, with the same sweep at half the modes

Reads 1_mmi_length/mmi_length.npz and the layout 1_mmi_length/mmi1x2.gds.

    python fig1_mmi_length.py            ->  figures/fig1_mmi_length.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/mmi1x2/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

STEP = ROOT / "1_mmi_length"
Y_SHOWN = (-2.2, 2.2)


def main() -> None:
    d = panels.load(STEP / "mmi_length.npz")
    device = float(d["length_mmi"])
    fig, axes = fs.mosaic(fs.DOUBLE, 58, [["a", "b"]], gridspec_kw=dict(width_ratios=[1.45, 1]))

    ax = axes["a"]
    image = panels.field_map(ax, d["field_x"], d["field_y"], d["field_E"], STEP / "mmi1x2.gds", ylim=Y_SHOWN)
    ax.set_aspect("auto")  # the panel fills its cell; the note says by how much y is stretched
    fs.colorbar_beside(ax, image, "|E| (normalised)", width=0.018, ticks=[0, 0.5, 1])
    total = float(d["T2"]) + float(d["T3"])
    text = f"multimode section {float(d['width_mmi'])} × {device} µm:  {100 * float(d['T2']):.1f} % + {100 * float(d['T3']):.1f} % = {100 * total:.1f} %"
    fs.note(ax, text, (0.02, 0.95), ha="left", va="top", transform=ax.transAxes)
    stretched = ax

    ax = axes["b"]
    length, total_sweep = d["sweep_length"], d["sweep_T2"] + d["sweep_T3"]
    ax.axvspan(float(d["tolerance_lo"]), float(d["tolerance_hi"]), color=fs.HAIRLINE, alpha=0.5, lw=0, zorder=0)
    ax.axvline(device, color=fs.MUTED, lw=0.5, zorder=1)
    ax.plot(length, total_sweep, color=fs.BLUE, lw=1.2, zorder=3, label=f"sum, {int(d['modes'])} modes per cell")
    if "check_total" in d:
        ax.plot(
            length,
            d["check_total"],
            color=fs.ORANGE,
            lw=0.8,
            ls=(0, (3, 2)),
            zorder=4,
            label=f"sum, {int(d['check_modes'])} modes per cell",
        )
    ax.plot(length, d["sweep_T2"], color=fs.AQUA, lw=0.8, zorder=2, label="one output")
    ax.plot(device, total, "o", mfc=fs.SURFACE, mec=fs.INK, mew=0.8, ms=4, zorder=5)
    ax.set_xlim(float(length.min()), float(length.max()))
    ax.set_ylim(0, 1.08)
    ax.set_xlabel("length of the multimode section (µm)")
    ax.set_ylabel("power into the outputs")
    ax.legend(loc="upper right")
    loss = float(panels.decibel(float(d["best_T"])))
    fs.note(ax, f"best {float(d['best_length']):.1f} µm:\n{loss:.2f} dB", (device - 0.75, 1.0), ha="right", va="center")
    fs.note(
        ax,
        f"within 0.1 dB of it:\n{float(d['tolerance_lo']):.1f} to {float(d['tolerance_hi']):.1f} µm",
        (device + 0.45, 0.10),
        ha="left",
        va="center",
    )
    beyond = np.where(length > 8, total_sweep, 1.0)
    dark = int(np.argmin(beyond))
    fs.note(
        ax,
        f"dark at {length[dark]:.0f} µm",
        (float(length[dark]), float(beyond[dark]) + 0.01),
        xytext=(12.3, 0.55),
        ha="center",
        va="bottom",
    )

    panels.stretch_note(stretched)
    for letter in "ab":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig1_mmi_length.png")


if __name__ == "__main__":
    main()

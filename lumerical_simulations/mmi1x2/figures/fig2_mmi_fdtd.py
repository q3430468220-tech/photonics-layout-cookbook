"""Figure 2 - FDTD: the splitter as drawn divides the light evenly across the band, with little loss and reflection.

    a  |E| in the device: the input spreads in the multimode section and forms two images at the outputs
    b  power into each output and the loss against wavelength, with the EME value of step 1 at 1550 nm
    c  back-reflection against wavelength

Reads 2_mmi_fdtd/mmi_fdtd.npz, 1_mmi_length/mmi_length.npz and the layout 2_mmi_fdtd/mmi1x2.gds.

    python fig2_mmi_fdtd.py            ->  figures/fig2_mmi_fdtd.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/mmi1x2/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

STEP = ROOT / "2_mmi_fdtd"


def main() -> None:
    d = panels.load(STEP / "mmi_fdtd.npz")
    eme = panels.load(ROOT / "1_mmi_length" / "mmi_length.npz")
    lam = d["lam"] * 1000
    back, upper, lower = (np.abs(d[f"S{k}"]) ** 2 for k in "123")
    loss = panels.decibel(upper + lower)
    design = 1550.0
    at = lambda values: float(np.interp(design, lam, values))  # noqa: E731
    fig, axes = fs.mosaic(fs.DOUBLE, 96, [["a", "a"], ["b", "c"]], gridspec_kw=dict(height_ratios=[0.75, 1]))

    ax = axes["a"]
    image = panels.field_map(ax, d["field_x"], d["field_y"], d["field_E"], STEP / "mmi1x2.gds", ylim=(-2.2, 2.2))
    ax.set_aspect("auto")  # the panel fills the row; the note says by how much y is stretched
    fs.colorbar_beside(ax, image, "|E| (normalised)", width=0.012, pad=0.012, ticks=[0, 0.5, 1])
    text = f"multimode section {float(d['width_mmi'])} × {float(d['length_mmi'])} µm, {design:.0f} nm"
    fs.note(ax, text, (0.02, 0.94), ha="left", va="top", transform=ax.transAxes)
    stretched = ax

    ax = axes["b"]
    ax.axvline(design, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(lam, loss, color=fs.BLUE, lw=1.2, zorder=3, label="FDTD")
    eme_loss = float(panels.decibel(float(eme["T2"]) + float(eme["T3"])))
    ax.plot(design, eme_loss, "o", mfc=fs.SURFACE, mec=fs.INK, mew=0.8, ms=5, zorder=5, label="EME, step 1")
    ax.set_xlim(lam.min(), lam.max())
    ax.set_xticks([1500, 1525, 1550, 1575, 1600])
    ax.set_ylim(0, max(0.3, float(loss.max()) * 1.35))
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("loss (dB)")
    ax.legend(loc="upper right")
    imbalance = abs(10 * np.log10(at(upper) / at(lower)))
    equal = "the two outputs are equal within 0.001 dB" if imbalance < 0.001 else f"the two outputs differ by {imbalance:.3f} dB"
    text = (
        f"at {design:.0f} nm: {100 * at(upper):.1f} % + {100 * at(lower):.1f} %, loss {at(loss):.3f} dB\n"
        f"{equal}\nover the band: {loss.min():.2f} to {loss.max():.2f} dB"
    )
    fs.note(
        ax,
        text,
        (0.03, 0.96),
        ha="left",
        va="top",
        transform=ax.transAxes,
        bbox=dict(fc=fs.SURFACE, ec="none", pad=0.6),
        zorder=4,
    )

    ax = axes["c"]
    ax.axvline(design, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(lam, 10 * np.log10(back), color=fs.BLUE, lw=1.2, zorder=3)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_xticks([1500, 1525, 1550, 1575, 1600])
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("back-reflection (dB)")
    worst = float((10 * np.log10(back)).max())
    ax.set_ylim(min(-60.0, float((10 * np.log10(back)).min()) - 3), worst + 12)
    text = f"at {design:.0f} nm: {panels.minus(10 * np.log10(at(back)), '.0f')} dB\nat most {panels.minus(worst, '.0f')} dB over the band"
    fs.note(ax, text, (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)

    panels.stretch_note(stretched)
    for letter in "abc":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig2_mmi_fdtd.png")


if __name__ == "__main__":
    main()

"""Figure 3 - INTERCONNECT: the multiplier as the layer of a neural network that classifies images of 2 x 2 pixels.

    a  test images of the four classes, as the four inputs carry them: noise on every pixel, no pixel below zero
    b  the weights W that the softmax regression learns (rows: the classes; columns: the pixels)
    c  the accuracy on the test images against the wavelength: W read coherently, the same W read by photodiodes (the
       sign lost), and a W trained for photodiodes; the electronic layer as thin lines
    d  W read by photodiodes at 1550 nm: true class against the class read

Reads 3_classifier/classifier.npz.

    python fig3_classifier.py            ->  figures/fig3_classifier.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/svd_multiplier/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "3_classifier" / "classifier.npz"
CLASSES = ("top", "bottom", "left", "right")
PER_CLASS = 3
SIGNED = LinearSegmentedColormap.from_list("signed", [fs.ORANGE, "#ffffff", fs.BLUE])  # negative, zero, positive
COUNT = LinearSegmentedColormap.from_list("count", ["#ffffff", fs.BLUE])


def panel_images(ax, d: dict) -> None:
    x, labels = d["x_test"], d["labels_test"]
    gap = 1
    size = 2 + gap
    canvas = np.full((4 * size, PER_CLASS * size), np.nan)
    for c in range(4):
        picks = np.flatnonzero(labels == c)[:PER_CLASS]
        for j, k in enumerate(picks):
            canvas[c * size : c * size + 2, j * size : j * size + 2] = x[k].reshape(2, 2)
    cmap = colormaps["gray"].with_extremes(bad="white")
    ax.imshow(canvas, cmap=cmap, vmin=0, vmax=1.2, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([c * size + 0.5 for c in range(4)])
    ax.set_yticklabels(CLASSES)
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    fs.panel_title(ax, "four classes, with noise")


def panel_weights(ax, d: dict) -> None:
    w = d["W"]
    lim = float(np.abs(w).max())
    ax.imshow(w, cmap=SIGNED, norm=TwoSlopeNorm(0, -lim, lim))
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f"{w[i, j]:+.1f}", ha="center", va="center", fontsize=6, color="white")
    ax.set_xticks(range(4))
    ax.set_xticklabels(["TL", "TR", "BL", "BR"])
    ax.set_yticks(range(4))
    ax.set_yticklabels(CLASSES)
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    fs.panel_title(ax, "W, learned in numpy")


def panel_band(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    e_coh, e_lost, e_pow = (100 * float(v) for v in d["electronic"])
    for acc, ref, color, label in ((d["accuracy_coherent"], e_coh, fs.BLUE, "W, read coherently"),
                                   (d["accuracy_power"], e_pow, fs.AQUA, "W trained for photodiodes"),
                                   (d["accuracy_sign_lost"], e_lost, fs.ORANGE, "W, read by photodiodes")):  # fmt: skip
        ax.axhline(ref, color=color, lw=0.6, alpha=0.6, zorder=0)
        ax.plot(lam, 100 * acc, color=color, lw=1.0, label=label)
    ax.axhline(25, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(0, 105)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("test images classified right (%)")
    fs.note(ax, "a guess: 25 %", (1598, 27), ha="right", va="bottom")
    fs.note(ax, "thin: the electronic layer", (1578, 66), ha="right")
    ax.legend(frameon=False, fontsize=6, loc="lower left", handletextpad=0.4)
    fs.panel_title(ax, "the optical layer, programmed at 1550 nm")


def panel_confusion(ax, d: dict) -> None:
    m = d["confusion_sign_lost"]
    ax.imshow(m, cmap=COUNT, vmin=0, vmax=m.max())
    for i in range(4):
        for j in range(4):
            ax.text(
                j, i, f"{m[i, j]}", ha="center", va="center", fontsize=6, color="white" if m[i, j] > 0.6 * m.max() else fs.INK
            )
    ax.set_xticks(range(4))
    ax.set_xticklabels(CLASSES)
    ax.set_yticks(range(4))
    ax.set_yticklabels(CLASSES)
    ax.set_xlabel("class read")
    ax.set_ylabel("true class")
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    fs.panel_title(ax, "photodiodes lose the sign")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(
        fs.DOUBLE, 112, [["a", "b", "d"], ["c", "c", "c"]], width_ratios=[0.7, 1.0, 1.0], height_ratios=[1.0, 0.85]
    )
    panel_images(axes["a"], d)
    panel_weights(axes["b"], d)
    panel_band(axes["c"], d)
    panel_confusion(axes["d"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig3_classifier.png"))


if __name__ == "__main__":
    main()

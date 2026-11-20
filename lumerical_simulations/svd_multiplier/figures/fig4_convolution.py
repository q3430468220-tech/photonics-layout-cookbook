"""Figure 4 - INTERCONNECT: the multiplier as the convolution layer of a network that reads handwritten digits.

    a  a test digit, the four kernels trained for photodiodes, and the four maps the multiplier makes of the digit
       (INTERCONNECT, 1.55 um, read by photodiodes)
    b  the share of the 1797 test digits read right, against the wavelength, for the three sets of kernels and for the
       learned kernels read by photodiodes; the electronic networks as thin lines
    c  the kernels trained for photodiodes at 1.55 um: the true digit against the digit read

Reads 4_convolution/convolution.npz and data/optdigits.npz.

    python fig4_convolution.py            ->  figures/fig4_convolution.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/svd_multiplier/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "4_convolution" / "convolution.npz"
DIGITS = ROOT / "data" / "optdigits.npz"
EXAMPLE = 3  # the first test digit of this class is shown
SIGNED = LinearSegmentedColormap.from_list("signed", [fs.ORANGE, "#ffffff", fs.BLUE])
COUNT = LinearSegmentedColormap.from_list("count", ["#ffffff", fs.BLUE])
INK = LinearSegmentedColormap.from_list("ink", ["#ffffff", fs.INK])
LIGHT = LinearSegmentedColormap.from_list("light", ["#ffffff", "#9fdcf0", fs.BLUE, "#0b2a6b"])


def patches(x: np.ndarray) -> np.ndarray:
    return np.stack([x[:-1, :-1], x[:-1, 1:], x[1:, :-1], x[1:, 1:]], -1).reshape(49, 4)


def panel_maps(ax, d: dict, digits: dict) -> None:
    k = 2  # the kernels trained for photodiodes
    x = digits["x_test"][np.flatnonzero(digits["y_test"] == EXAMPLE)[0]] / 16.0
    t0 = d["T_interconnect"][k][len(d["lam"]) // 2]
    target = d["K"][k] / float(d["scale"][k])
    a0 = np.vdot(target, t0) / np.vdot(target, target)
    maps = (np.abs(patches(x) @ t0.T) * float(d["scale"][k]) / abs(a0)) ** 2  # (49, 4)
    ax.set_xlim(0, 32)
    ax.set_ylim(-1.5, 10.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.imshow(x, cmap=INK, vmin=0, vmax=1, extent=(0, 8, 1, 9), interpolation="nearest")
    fs.note(ax, f"a test digit, {EXAMPLE}", (4, 9.6), ha="center", va="bottom")
    ax.annotate("", xy=(10.6, 5), xytext=(8.6, 5), arrowprops={"arrowstyle": "->", "color": fs.SECONDARY, "lw": 0.8})
    lim = float(np.abs(d["K"][k]).max())
    top = float(maps.max())
    for j in range(4):
        x0 = 11 + j * 5.3
        ax.imshow(d["K"][k][j].reshape(2, 2), cmap=SIGNED, vmin=-lim, vmax=lim, extent=(x0 + 1.25, x0 + 3.25, 6.8, 8.8),
                  interpolation="nearest")  # fmt: skip
        ax.imshow(maps[:, j].reshape(7, 7), cmap=LIGHT, vmin=0, vmax=top, extent=(x0, x0 + 4.5, 1, 5.5), interpolation="nearest")
        fs.note(ax, f"kernel {j + 1}", (x0 + 2.25, 9.3), ha="center", va="bottom")
    fs.note(ax, "the four maps of the multiplier: |field|², 7 × 7 windows each", (11, 0.2), ha="left", va="top")
    fs.panel_title(ax, "a convolution in light: one 2 × 2 window at a time, four kernels at once")


def panel_band(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    colors = (fs.AQUA, fs.BLUE, fs.ORANGE)
    labels = {"Haar": "Haar kernels, read coherently", "learned": "learned kernels, read coherently",
              "photodiode": "kernels trained for photodiodes"}  # fmt: skip
    for j, name in enumerate(d["names"]):
        ax.axhline(100 * float(d["electronic"][j]), color=colors[j], lw=0.6, alpha=0.6, zorder=0)
        ax.plot(lam, 100 * d["accuracy"][j], color=colors[j], lw=1.0, label=labels[str(name)])
    ax.plot(lam, 100 * d["sign_lost"], color=fs.MUTED, lw=1.0, ls=(0, (4, 3)), label="learned kernels, read by photodiodes")
    ax.axhline(10, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(0, 102)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("test digits read right (%)")
    fs.note(ax, "a guess: 10 %", (1598, 11.5), ha="right", va="bottom")
    ax.legend(frameon=False, fontsize=6, loc="lower center", bbox_to_anchor=(0.5, 0.12), handletextpad=0.4)
    fs.panel_title(ax, "programmed at 1550 nm; thin lines: the electronic networks")


def panel_confusion(ax, d: dict) -> None:
    m = d["confusion"][2]
    ax.imshow(m, cmap=COUNT, vmin=0, vmax=m.max())
    for i in range(10):
        for j in range(10):
            if m[i, j]:
                ax.text(
                    j, i, f"{m[i, j]}", ha="center", va="center", fontsize=5, color="white" if m[i, j] > 0.6 * m.max() else fs.INK
                )
    ax.set_xticks(range(10))
    ax.set_yticks(range(10))
    ax.set_xlabel("digit read")
    ax.set_ylabel("true digit")
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    i0 = len(d["lam"]) // 2
    fs.panel_title(ax, f"photodiode kernels, 1550 nm: {100 * float(d['accuracy'][2][i0]):.1f} % right")


def main() -> None:
    d = panels.load(DATA)
    digits = panels.load(DIGITS)
    fig, axes = fs.mosaic(fs.DOUBLE, 112, [["a", "c"], ["b", "c"]], width_ratios=[1.45, 1.0], height_ratios=[0.85, 1.0])
    panel_maps(axes["a"], d, digits)
    panel_band(axes["b"], d)
    panel_confusion(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig4_convolution.png"))


if __name__ == "__main__":
    main()

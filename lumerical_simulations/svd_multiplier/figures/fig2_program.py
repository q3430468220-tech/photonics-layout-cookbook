"""Figure 2 - INTERCONNECT and Python: real matrices programmed into the multiplier as drawn.

    a  every entry of the first random matrix and of the ill-conditioned one: INTERCONNECT at 1.55 um, with the common
       factor taken out, against the target
    b  the relative error of every target: the recipe alone, the two meshes fitted alone, the fit of the whole
    c  the relative error against the wavelength, INTERCONNECT
    d  the singular values of every target, over the largest, against the smallest an attenuator can set (step 1)

Reads 2_program/program.npz and 1_attenuator/attenuator.npz.

    python fig2_program.py            ->  figures/fig2_program.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/svd_multiplier/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "2_program" / "program.npz"
ATTENUATOR = ROOT / "1_attenuator" / "attenuator.npz"


def target_of(d: dict, k: int) -> np.ndarray:
    m = d["targets"][k]
    return m / float(d["scale"][k])


def panel_entries(ax, d: dict) -> None:
    i0 = len(d["lam"]) // 2
    lim = 0
    for j, (k, color, label) in enumerate(zip(d["checked"], (fs.BLUE, fs.ORANGE), ("random 1", "ill-conditioned"), strict=True)):
        target = target_of(d, int(k))
        t = d["T_interconnect"][j][i0]
        a = np.vdot(target, t) / np.vdot(target, target)
        got = t / a
        ax.plot(target.ravel(), got.real.ravel(), "o", ms=3.2, mfc="none", mec=color, mew=0.8, label=label)
        lim = max(lim, float(np.abs(target).max()))
    lim *= 1.1
    ax.plot([-lim, lim], [-lim, lim], color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("entry of the target, M / s")
    ax.set_ylabel("entry in INTERCONNECT, T / a")
    ax.legend(frameon=False, fontsize=6, loc="upper left", handletextpad=0.2)
    fs.panel_title(ax, "every entry where it belongs")


def panel_errors(ax, d: dict) -> None:
    names = [str(x) for x in d["names"]]
    x = np.arange(len(names))
    for key, color, marker, label in (("error_recipe", fs.MUTED, "s", "the recipe alone"),
                                      ("error_start", fs.AQUA, "^", "meshes fitted alone"),
                                      ("error", fs.BLUE, "o", "fit of the whole")):  # fmt: skip
        ax.plot(x, d[key], marker, ms=3.5, color=color, lw=0, label=label)
    ax.axhline(0.01, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_yscale("log")
    ax.set_ylim(1e-14, 60)
    ax.set_xticks(x)
    ax.set_xticklabels([n.replace("random ", "") if n.startswith("random") else "ill" for n in names])
    ax.set_xlabel("target: random 1 to 12, and the ill-conditioned one")
    ax.set_ylabel("relative error at 1550 nm")
    fs.note(ax, "1 %", (-0.4, 0.013), ha="left", va="bottom")
    ax.legend(frameon=False, fontsize=6, loc="center left", bbox_to_anchor=(0.0, 0.55), handletextpad=0.2)
    fs.panel_title(ax, "the fit closes the gap, down to the floor")


def panel_band(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    for j, (color, label) in enumerate(((fs.BLUE, "random 1"), (fs.ORANGE, "ill-conditioned"))):
        ax.plot(lam, 1 - d["fidelity_ic"][j], color=color, lw=1.0, label=label)
        ax.plot(lam, 1 - d["fidelity_model"][j], color=color, lw=2.4, alpha=0.25, solid_capstyle="butt")
    ax.axhline(0.01, color=fs.HAIRLINE, lw=0.6, zorder=0)
    lo, hi = 1000 * d["band_um"][0]
    ax.axvspan(lo, hi, color=fs.HAIRLINE, alpha=0.25, lw=0, zorder=0)
    ax.set_yscale("log")
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(1e-8, 1)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("1 − F, INTERCONNECT")
    fs.note(ax, f"F > 0.99:\n{lo:.0f}–{hi:.0f} nm", (hi + 2, 3e-6), ha="left")
    fs.note(ax, "F = 0.99", (1598, 0.013), ha="right", va="bottom")
    fs.note(ax, "thick: the model", (1598, 1e-5), ha="right")
    ax.legend(frameon=False, fontsize=6, loc="lower left", handletextpad=0.4)
    fs.panel_title(ax, "set at 1550 nm")


def panel_sigma(ax, d: dict, a: dict) -> None:
    sigma = d["sigma"]
    floor = float(a["smallest"])
    for k, row in enumerate(sigma):
        color = fs.ORANGE if k == len(sigma) - 1 else fs.BLUE
        ax.plot(np.full(row.size, k), row, "o", ms=3.2, mfc="none", mec=color, mew=0.8)
    ax.axhspan(1e-5, floor, color=fs.RED, alpha=0.08, lw=0, zorder=0)
    ax.axhline(floor, color=fs.RED, lw=0.6, zorder=0)
    ax.set_yscale("log")
    ax.set_ylim(3e-4, 2)
    ax.set_xticks(range(len(sigma)))
    ax.set_xticklabels([str(k + 1) for k in range(len(sigma) - 1)] + ["ill"])
    ax.set_xlabel("target")
    ax.set_ylabel("singular value, over the largest")
    fs.note(ax, f"the leak of an attenuator, {floor:.1e} (step 1):\nnothing smaller can be set", (-0.4, 1.3e-3), ha="left",
            va="top", color=fs.RED)  # fmt: skip
    fs.panel_title(ax, "what the attenuators must set")


def main() -> None:
    d = panels.load(DATA)
    a = panels.load(ATTENUATOR)
    fig, axes = fs.mosaic(fs.DOUBLE, 118, [["a", "b"], ["c", "d"]], width_ratios=[0.8, 1.2], height_ratios=[1.0, 0.85])
    panel_entries(axes["a"], d)
    panel_errors(axes["b"], d)
    panel_band(axes["c"], d)
    panel_sigma(axes["d"], d, a)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig2_program.png"))


if __name__ == "__main__":
    main()

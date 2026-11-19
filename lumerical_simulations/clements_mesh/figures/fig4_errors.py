"""Figure 4 - couplers that a fabrication error of the gap moves away from 50:50.

    a  the split of a coupler at 1.55 um against the error of its gap
    b  every gap off by the same amount: 1 - F with the powers of the error-free mesh and with powers fitted to it
    c  every gap off by its own random amount: 1 - F against the width of the distribution, as programmed and fitted

Reads 4_coupler_errors/errors.npz.

    python fig4_errors.py            ->  figures/fig4_errors.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/clements_mesh/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "4_coupler_errors" / "errors.npz"


def panel_split(ax, d: dict) -> None:
    dg, split = d["shifts_nm"], d["shift_split"]
    ax.axhline(0.5, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.plot(dg, split, "o-", color=fs.BLUE, ms=3, lw=1.0)
    ax.set_xlabel("error of the gap (nm)")
    ax.set_ylabel("cross power of a coupler, 1550 nm")
    ax.set_xlim(dg.min() - 2, dg.max() + 2)
    per_gap, per_lam = float(d["split_per_nm_gap"]), float(d["split_per_nm_lam"])
    fs.note(
        ax,
        f"{100 * per_gap:+.2f} points per nm of gap\n= {abs(per_gap / per_lam):.1f} nm of wavelength",
        (2, 0.62),
        ha="left",
        va="top",
    )
    fs.note(ax, "narrower gap,\nstronger coupling", (-19, 0.40), ha="left", va="bottom")
    fs.panel_title(ax, "the split moves with the gap")


def panel_shift(ax, d: dict) -> None:
    dg = d["shifts_nm"]
    nominal, fitted = 1 - d["shift_nominal"], 1 - d["shift_fitted"]  # (shift, target): the DFT first
    ax.plot(dg, np.median(nominal[:, 1:], axis=1), color=fs.ORANGE, lw=1.0)
    ax.plot(dg, np.median(fitted[:, 1:], axis=1), color=fs.BLUE, lw=1.0)
    ax.fill_between(dg, fitted[:, 1:].min(axis=1), fitted[:, 1:].max(axis=1), color=fs.BLUE, alpha=0.15, lw=0)
    ax.plot(dg, nominal[:, 0], "D", color=fs.ORANGE, ms=2.6, lw=0)
    ax.plot(dg, fitted[:, 0], "D", color=fs.BLUE, ms=2.6, lw=0)
    ax.set_yscale("log")
    ax.set_xlim(dg.min() - 2, dg.max() + 2)
    ax.set_ylim(1e-8, 1)
    ax.set_xlabel("error of every gap (nm)")
    ax.set_ylabel("1 − F at 1550 nm")
    fs.note(ax, "as programmed", (13, 0.2), ha="right", color=fs.ORANGE)
    fs.note(ax, "fitted to the mesh\n(range of 10 random)", (-19, 2e-8), ha="left", va="bottom", color=fs.BLUE)
    fs.note(ax, "diamonds: the DFT", (19, 2e-8), ha="right", va="bottom")
    fs.panel_title(ax, "the same error on every coupler")


def panel_random(ax, d: dict) -> None:
    sig = d["sigmas_nm"]
    nominal, fitted = 1 - d["random_nominal"], 1 - d["random_fitted"]  # (sigma, sample)
    rng = np.random.default_rng(1)
    for k, _s in enumerate(sig):
        x = np.full(nominal.shape[1], k)
        ax.plot(x - 0.17 + rng.uniform(-0.08, 0.08, x.size), nominal[k], "o", ms=2.2, color=fs.ORANGE, alpha=0.7, lw=0)
        ax.plot(x + 0.17 + rng.uniform(-0.08, 0.08, x.size), fitted[k], "o", ms=2.2, color=fs.BLUE, alpha=0.7, lw=0)
        for dx, v in ((-0.17, nominal[k]), (0.17, fitted[k])):
            ax.plot([k + dx - 0.13, k + dx + 0.13], [np.median(v)] * 2, color=fs.INK, lw=0.8)
    ax.set_yscale("log")
    ax.set_ylim(1e-8, 1)
    ax.set_xticks(range(len(sig)))
    ax.set_xticklabels([f"{s:g}" for s in sig])
    ax.set_xlabel("σ of the random gap errors (nm)")
    ax.set_ylabel("1 − F at 1550 nm")
    fs.note(ax, "as programmed", (-0.4, 0.3), ha="left", color=fs.ORANGE)
    fs.note(ax, "fitted", (-0.4, 0.06), ha="left", color=fs.BLUE)
    fs.panel_title(ax, f"{nominal.shape[1]} meshes, each with its own errors")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 62, [["a", "b", "c"]], width_ratios=[0.9, 1.0, 1.0])
    panel_split(axes["a"], d)
    panel_shift(axes["b"], d)
    panel_random(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig4_errors.png"))


if __name__ == "__main__":
    main()

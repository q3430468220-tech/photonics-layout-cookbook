"""Figure 1 - INTERCONNECT: one block of the mesh, a Mach-Zehnder interferometer of two couplers and a heater.

    a  the power in the two outputs against the heater power on the arm, at 1.55 um, light into the upper input
    b  the extinction of the cross state against the wavelength: INTERCONNECT and the formula from the coupler's split
    c  the split of the half state against the wavelength

Reads 1_mzi/mzi.npz.

    python fig1_mzi.py            ->  figures/fig1_mzi.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/clements_mesh/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "1_mzi" / "mzi.npz"


def panel_sweep(ax, d: dict) -> None:
    p, p_pi = d["sweep_P_mW"], float(d["P_pi_mW"])
    ax.plot(p, d["cross"], color=fs.BLUE, lw=1.0)
    ax.plot(p, d["bar"], color=fs.ORANGE, lw=1.0)
    for k in (1, 2):
        ax.axvline(k * p_pi, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_xlim(0, p.max())
    ax.set_ylim(0, 1.12)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("heater power on the arm (mW)")
    ax.set_ylabel("power in the output, 1.55 µm")
    fs.note(ax, "cross", (15.9, 0.9), ha="left", color=fs.BLUE)
    fs.note(ax, "bar", (5.4, 0.9), ha="right", color=fs.ORANGE)
    fs.note(ax, f"P$_π$ = {p_pi:.2f} mW", (p_pi - 0.4, 1.07), ha="right")
    fs.note(ax, "2P$_π$", (2 * p_pi - 0.4, 1.07), ha="right")
    fs.panel_title(ax, "the heater sets the split")


def panel_extinction(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    ax.plot(lam, d["er_cross_formula_dB"], color=fs.MUTED, lw=2.4, alpha=0.45, solid_capstyle="butt")
    ax.plot(lam, d["er_cross_dB"], color=fs.BLUE, lw=1.0)
    ax.axhline(20, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ok = lam[d["er_cross_dB"] >= 20]
    ax.axvspan(ok.min(), ok.max(), color=fs.HAIRLINE, alpha=0.25, lw=0, zorder=0)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(0, 60)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("extinction of the cross state (dB)")
    fs.note(ax, f"{float(-10 * np.log10(d['bar_null'])):.1f} dB at 1550 nm", (1553, 52), ha="left")
    fs.note(ax, f"above 20 dB:\n{ok.min():.0f}–{ok.max():.0f} nm", (ok.max() + 3, 31), ha="left")
    fs.note(ax, "INTERCONNECT", (1508, 7), ha="left", color=fs.BLUE)
    fs.note(ax, "4κ²(1−κ²)/(1−2κ²)²\nfrom the coupler's split", (1508, 23), ha="left")
    fs.panel_title(ax, "the coupler sets the extinction")


def panel_half(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    ax.axhline(0.5, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.plot(lam, d["split_half"], color=fs.BLUE, lw=1.0)
    ax.plot(lam, d["kappa2"], color=fs.AQUA, lw=1.0, ls=(0, (4, 3)))
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(0.3, 0.7)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("share of the light that crosses")
    fs.note(ax, "the block, set to\nhalf at 1550 nm", (1506, 0.535), ha="left", color=fs.BLUE)
    fs.note(ax, "one coupler", (1566, 0.64), ha="right", color=fs.AQUA)
    fs.panel_title(ax, "two couplers drift less than one")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 62, [["a", "b", "c"]], width_ratios=[1.0, 1.05, 1.0])
    panel_sweep(axes["a"], d)
    panel_extinction(axes["b"], d)
    panel_half(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig1_mzi.png"))


if __name__ == "__main__":
    main()

"""Figure 1 - INTERCONNECT: one attenuator of the column, a Mach-Zehnder interferometer with a dump of its own.

    a  what stays on the row and what goes to the dump, against the heater power on the dump arm, at 1.55 um; the
       field the row keeps against sin(theta / 2)
    b  the phase of the row against the heater: what mesh V takes up
    c  the leak at 0 mW against the wavelength, INTERCONNECT and (1 - 2 kappa^2)^2 from the coupler's split: the
       smallest singular value the column can set

Reads 1_attenuator/attenuator.npz.

    python fig1_attenuator.py            ->  figures/fig1_attenuator.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/svd_multiplier/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "1_attenuator" / "attenuator.npz"


def panel_sweep(ax, d: dict) -> None:
    p, p_pi = d["sweep_P_mW"], float(d["P_pi_mW"])
    fine = np.linspace(0, p.max(), 400)
    ax.plot(fine, np.sin(np.pi * fine / p_pi / 2) ** 2 * float(d["keep"].max()), color=fs.MUTED, lw=2.4, alpha=0.45,
            solid_capstyle="butt")  # fmt: skip
    ax.plot(p, d["keep"], color=fs.BLUE, lw=1.0)
    ax.plot(p, d["dump"], color=fs.ORANGE, lw=1.0)
    for k in (1, 2):
        ax.axvline(k * p_pi, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_xlim(0, p.max())
    ax.set_ylim(0, 1.12)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("heater power on the dump arm (mW)")
    ax.set_ylabel("power, of the light into the row")
    fs.note(ax, "row", (p_pi + 1.0, 0.55), ha="left", color=fs.BLUE)
    fs.note(ax, "dump", (p_pi - 4.6, 0.25), ha="right", color=fs.ORANGE)
    fs.note(ax, "sin²(θ/2), ideal couplers", (p_pi + 0.6, 1.07), ha="left")
    fs.note(ax, f"P$_π$ = {p_pi:.2f} mW", (p_pi - 0.4, 1.07), ha="right")
    fs.panel_title(ax, "the heater sets what the row keeps")


def panel_phase(ax, d: dict) -> None:
    p, p_pi = d["sweep_P_mW"], float(d["P_pi_mW"])
    inner = (p > 0.05 * p_pi) & (p < 1.95 * p_pi)  # at 0 and 2 P_pi the row keeps nothing, and its phase means nothing
    theta = np.pi * p / p_pi
    ax.plot(p[inner], (theta[inner] - np.pi) / 2, color=fs.MUTED, lw=2.4, alpha=0.45, solid_capstyle="butt")
    ax.plot(p[inner], d["phase"][inner], color=fs.BLUE, lw=1.0)
    ax.axvline(p_pi, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.axhline(0, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_xlim(0, p.max())
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_ylim(-1.7, 1.7)
    ax.set_xlabel("heater power on the dump arm (mW)")
    ax.set_ylabel("phase of the row, against P$_π$ (rad)")
    fs.note(ax, f"slope {float(d['phase_slope']):.2f} rad per rad of θ", (0.6, 1.35), ha="left", color=fs.BLUE)
    fs.note(ax, "θ/2, ideal couplers", (0.6, 1.05), ha="left")
    fs.note(ax, "mesh V takes it up", (19.8, -1.4), ha="right")
    fs.panel_title(ax, "and turns its phase by half as much")


def panel_leak(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    to_db = lambda x: 10 * np.log10(np.maximum(x, 1e-30))  # noqa: E731
    ax.plot(lam, to_db(d["leak_lam_formula"]), color=fs.MUTED, lw=2.4, alpha=0.45, solid_capstyle="butt")
    ax.plot(lam, to_db(d["leak_lam"]), color=fs.BLUE, lw=1.0)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(-60, 0)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("power the row keeps at 0 mW (dB)")
    leak = float(d["leak"])
    fs.note(ax, f"{to_db(leak):.1f} dB at 1550 nm:\nσ$_{{min}}$ = {np.sqrt(leak):.1e} σ$_{{max}}$", (1556, -52), ha="left")
    fs.note(ax, "INTERCONNECT", (1506, -4.5), ha="left", color=fs.BLUE)
    fs.note(ax, "(1 − 2κ²)²\nfrom the coupler's split", (1506, -22), ha="left")
    fs.panel_title(ax, "the coupler sets how far down")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 62, [["a", "b", "c"]], width_ratios=[1.0, 1.0, 1.0])
    panel_sweep(axes["a"], d)
    panel_phase(axes["b"], d)
    panel_leak(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig1_attenuator.png"))


if __name__ == "__main__":
    main()

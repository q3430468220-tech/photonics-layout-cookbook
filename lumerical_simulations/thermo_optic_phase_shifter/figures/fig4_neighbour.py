"""Figure 4 - HEAT: what a waveguide beside the phase shifter feels.

    a  rise at the height of the core against the distance from the heated waveguide, per milliwatt: with the substrate
       held at 300 K and with 9.5 um of substrate in the model, each with and without trenches
    b  the share of the phase that a neighbour takes: the path through the oxide (simulated, no trenches) and the
       estimate of the path through the substrate of a real wafer, which the trenches do not stop

Reads 4_neighbour/neighbour.npz; the geometry comes from the builder of the device.

    python fig4_neighbour.py            ->  figures/fig4_neighbour.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/thermo_optic_phase_shifter/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

from devices import thermo_optic_phase_shifter_builder as tops  # noqa: E402

DATA = ROOT / "4_neighbour" / "neighbour.npz"
FLOOR = 1e-7  # K/mW: the bottom of panel a; below it the solver has nothing but rounding


def core_of(d: dict, name: str) -> float:
    return float(d["core_K_per_mW"][list(d["case_name"]).index(name)])


def panel_profiles(ax, d: dict) -> None:
    """The rise at the height of the core against the distance, for the four runs."""
    y = d["profile_y_um"]
    inner, outer = tops.TRENCH_GAP, tops.TRENCH_GAP + tops.TRENCH_WIDTH
    ax.axvspan(inner, outer, color=fs.HAIRLINE, alpha=0.35, lw=0)
    series = (
        ("reference_a", fs.ORANGE, "-", "no trenches, substrate at 300 K"),
        ("reference_b", fs.ORANGE, (0, (4, 3)), "no trenches, substrate in the model"),
        ("device_a", fs.BLUE, "-", "trenches, substrate at 300 K"),
        ("device_b", fs.BLUE, (0, (4, 3)), "trenches, substrate in the model"),
    )
    for name, color, style, _ in series:
        rise = np.array(d[f"{name}_profile_K_per_mW"], dtype=float)
        rise[rise < FLOOR] = np.nan  # nothing but rounding: not drawn on a logarithmic axis
        ax.plot(y, rise, color=color, lw=1.0, ls=style, zorder=2)
    ax.set_yscale("log")
    ax.set_xlim(0, 52)
    ax.set_ylim(FLOOR, 10)
    ax.set_xticks([0, 10, 20, 30, 40, 50])
    ax.set_yticks([1e-6, 1e-4, 1e-2, 1])
    ax.set_xlabel("distance from the heated waveguide (µm)")
    ax.set_ylabel("rise at the height of the core (K/mW)")
    fs.note(ax, "trench", ((inner + outer) / 2, 2.2e-7), ha="center", va="bottom")
    for k, (_, color, style, label) in enumerate(series):
        top = 0.955 - 0.068 * k
        ax.plot([0.36, 0.43], [top - 0.02, top - 0.02], color=color, lw=1.0, ls=style, transform=ax.transAxes)
        ax.text(0.45, top, label, fontsize=6, color=fs.INK, transform=ax.transAxes, va="top")
    fs.note(
        ax,
        "with trenches and the substrate held at 300 K\nnothing reaches the far side",
        (outer + 1.0, 1.5e-6),
        ha="left",
        va="bottom",
    )
    fs.panel_title(ax, "two-dimensional runs")


def panel_share(ax, d: dict) -> None:
    """The share of the heated arm's phase that a neighbour takes, against its distance."""
    y = d["profile_y_um"]
    oxide = np.array(d["reference_a_profile_K_per_mW"], dtype=float) / core_of(d, "reference_a")
    under = np.array(d["device_b_profile_K_per_mW"], dtype=float) / core_of(d, "device_b")
    wafer = d["estimate_curve_K_per_mW"] / float(d["core_drawn_K_per_mW"])
    shown = y >= 4.0
    ax.plot(y[shown], 100 * oxide[shown], color=fs.ORANGE, lw=1.0, zorder=2)
    beyond = y > tops.TRENCH_GAP + tops.TRENCH_WIDTH + 0.5
    ax.plot(y[beyond], 100 * under[beyond], color=fs.BLUE, lw=1.0, ls=(0, (4, 3)), zorder=2)
    ax.plot(d["estimate_curve_um"], 100 * wafer, color=fs.AQUA, lw=1.0, zorder=2)
    points = 100 * d["estimate_K_per_mW"] / float(d["core_drawn_K_per_mW"])
    ax.plot(d["estimate_distance_um"], points, "o", color=fs.AQUA, ms=3.5, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(4, 320)
    ax.set_ylim(1e-4, 100)
    ax.set_xticks([5, 10, 20, 50, 100, 200])
    ax.set_xticklabels(["5", "10", "20", "50", "100", "200"])
    ax.set_yticks([1e-4, 1e-2, 1, 100])
    ax.set_yticklabels(["0.0001", "0.01", "1", "100"])
    ax.set_xlabel("distance of the neighbour (µm)")
    ax.set_ylabel("share of the heated arm's phase (%)")
    fs.note(ax, "through the oxide,\nno trenches (simulated)", (6.3, 30), ha="left", va="center", color=fs.INK)
    fs.note(
        ax,
        f"through a wafer of {float(d['wafer_um']):.0f} µm\n(estimate by formula):\ntrenches do not stop it",
        (60, 2.4),
        ha="left",
        va="bottom",
        color=fs.INK,
    )
    fs.note(
        ax,
        f"trenches, {float(d['substrate_in_model_um']):g} µm of\nsubstrate (simulated)",
        (4.4, 2.5e-3),
        ha="left",
        va="top",
        color=fs.INK,
    )
    at_50 = float(points[list(d["estimate_distance_um"]).index(50.0)])
    fs.note(ax, f"{at_50:.2f} % at 50 µm", (50, at_50), xytext=(95, 0.05), ha="left", va="center")
    fs.panel_title(ax, "what the neighbour takes")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 72, [["a", "b"]], width_ratios=[1.15, 1.0])
    panel_profiles(axes["a"], d)
    panel_share(axes["b"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig4_neighbour.png"))


if __name__ == "__main__":
    main()

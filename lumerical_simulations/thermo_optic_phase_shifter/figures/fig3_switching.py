"""Figure 3 - HEAT, transient: how fast the phase shifter is, and what the trenches cost in speed.

    a  the device switched on and off again: the rise of the film and of the core against time
    b  the rise of the core for each trench gap, normalised to its final value, with the 63 % point of each
    c  the power for pi against the time constant for each gap, with lines of equal product

Reads 3_switching_time/switching.npz.

    python fig3_switching.py            ->  figures/fig3_switching.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/thermo_optic_phase_shifter/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

DATA = ROOT / "3_switching_time" / "switching.npz"
TAU_LEVEL = 1 - np.exp(-1)  # the time constant: the rise reaches this share of its final value
T_SHOWN = 150.0  # us: the stretch of time of panel b
PRODUCTS = (150, 200, 250)  # mW us: the lines of equal product of panel c


def cases(d: dict) -> list[dict]:
    """The runs in the order of the file (closest trench first, no trenches last), each with its colour and label."""
    names = [str(n) for n in d["case_name"]]
    trenched = [n for n in names if not np.isnan(d["case_gap_um"][names.index(n)])]
    shades = dict(zip(trenched, fs.sweep_colors(len(trenched) + 1)[::-1], strict=False))  # the closest trench darkest
    out = []
    for i, name in enumerate(names):
        gap = float(d["case_gap_um"][i])
        none = bool(np.isnan(gap))
        out.append(
            dict(
                name=name,
                none=none,
                color=fs.ORANGE if none else shades[name],
                label="no trenches" if none else f"{gap:g} µm",
                tau=float(d["case_tau_s"][i]) * 1e6,
                rise=float(d["case_t_rise_s"][i]) * 1e6,
                p_pi=float(d["case_P_pi_mW"][i]),
                product=float(d["case_product_mW_us"][i]),
                t=d[f"{name}_t_s"] * 1e6,
                core=d[f"{name}_core_K"].astype(float),
                final=float(d["case_final_K"][i]),
            )
        )
    return out


def small_table(ax, runs: list[dict], title: str, value, x0: float, y0: float, width: float) -> None:
    """A legend that also gives a number: a swatch, the name of each run and its value, in axes fractions.

    (x0, y0) is the top left corner, ``width`` the distance to the right edge of the numbers.
    """
    ax.text(x0, y0, title, fontsize=6, color=fs.SECONDARY, transform=ax.transAxes, va="top")
    for k, run in enumerate(runs):
        top = y0 - 0.075 * (k + 1)
        ax.plot([x0, x0 + 0.06], [top - 0.02, top - 0.02], color=run["color"], lw=1.2, transform=ax.transAxes, clip_on=False)
        ax.text(x0 + 0.09, top, run["label"], fontsize=6, color=fs.INK, transform=ax.transAxes, va="top")
        ax.text(x0 + width, top, value(run), fontsize=6, color=fs.INK, transform=ax.transAxes, va="top", ha="right")


def panel_pulse(ax, d: dict, device: dict) -> None:
    """The device, with the power on and then off: the film and the core."""
    high = float(d["t_high_s"]) * 1e6
    ax.axvspan(0, high, color=fs.HAIRLINE, alpha=0.3, lw=0)
    ax.plot(device["t"], d["device_film_K"], color=fs.ORANGE, lw=1.0)
    ax.plot(device["t"], device["core"], color=fs.BLUE, lw=1.0)
    ax.set_xlim(-20, device["t"].max())
    ax.set_ylim(0, 72)
    ax.set_xticks(np.arange(0, device["t"].max() + 1, 200))
    ax.set_xlabel("time (µs)")
    ax.set_ylabel("temperature rise (K)")
    film = float(np.max(d["device_film_K"]))
    fs.note(ax, f"film, {film:.1f} K", (high * 0.5, film + 2), ha="center", va="bottom", color=fs.INK)
    fs.note(ax, f"core, {device['final']:.1f} K", (high * 0.5, device["final"] - 2.5), ha="center", va="top", color=fs.INK)
    fs.note(ax, f"{float(d['power_mW']):.0f} mW on", (high * 0.5, 4), ha="center", va="bottom")
    fs.note(ax, "off", (high * 1.5, 4), ha="center", va="bottom")
    fall = float(d["device_t_fall_s"]) * 1e6
    fs.note(ax, f"rise 10–90 %: {device['rise']:.1f} µs\nfall 90–10 %: {fall:.1f} µs", (0.97, 0.96), ha="right", va="top",
            transform=ax.transAxes)  # fmt: skip
    fs.panel_title(ax, "the device, switched on and off")


def panel_rise(ax, runs: list[dict]) -> None:
    """The rise of the core of each case over its final value; a dot where it passes 63 %."""
    ax.axhline(TAU_LEVEL, color=fs.HAIRLINE, lw=0.5, zorder=0)
    for run in runs:
        shown = (run["t"] >= 0) & (run["t"] <= T_SHOWN)
        ax.plot(run["t"][shown], run["core"][shown] / run["final"], color=run["color"], lw=1.0, zorder=2)
        ax.plot(run["tau"], TAU_LEVEL, "o", color=run["color"], ms=3.5, zorder=3)
    ax.set_xlim(0, T_SHOWN)
    ax.set_ylim(0, 1.05)
    ax.set_xticks([0, 50, 100, 150])
    ax.set_yticks([0, 0.5, 1.0])
    ax.set_xlabel("time after the power goes on (µs)")
    ax.set_ylabel("rise of the core over its final value")
    ax.text(T_SHOWN * 0.985, TAU_LEVEL - 0.03, "63 %", fontsize=6, color=fs.SECONDARY, ha="right", va="top")
    small_table(ax, runs, "trench gap and time constant τ", lambda run: f"{run['tau']:.1f} µs", 0.47, 0.46, 0.5)
    fs.panel_title(ax, "trench gap and speed")


def panel_trade(ax, runs: list[dict]) -> None:
    """Power for pi against the time constant; along a grey line the product of the two is the same."""
    tau = np.linspace(2.0, 24.0, 200)
    for product in PRODUCTS:
        ax.plot(tau, product / tau, color=fs.HAIRLINE, lw=0.6, zorder=0)
        ax.text(23.6, product / 23.6 + 0.3, f"{product}", fontsize=5.5, color=fs.MUTED, ha="right", va="bottom")
    ax.plot([run["tau"] for run in runs], [run["p_pi"] for run in runs], color=fs.MUTED, lw=0.6, zorder=1)
    for run in runs:
        ax.plot(run["tau"], run["p_pi"], "o", color=run["color"], ms=5, zorder=3)
        ax.annotate(run["label"], (run["tau"], run["p_pi"]), xytext=(5, 4), textcoords="offset points", fontsize=6, color=fs.INK)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 30)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_yticks([0, 10, 20, 30])
    ax.set_xlabel("time constant τ (µs)")
    ax.set_ylabel("power for π (mW)")
    fs.note(ax, "grey: lines of equal\nproduct (mW µs)", (0.97, 0.96), ha="right", va="top", transform=ax.transAxes)
    small_table(ax, runs, "product (mW µs)", lambda run: f"{run['product']:.0f}", 0.04, 0.47, 0.4)
    fs.panel_title(ax, "power against time")


def main() -> None:
    d = panels.load(DATA)
    runs = cases(d)
    device = next(run for run in runs if run["name"] == "device")
    fig, axes = fs.mosaic(fs.DOUBLE, 68, [["a", "b", "c"]], width_ratios=[1.0, 1.1, 1.1])
    panel_pulse(axes["a"], d, device)
    panel_rise(axes["b"], runs)
    panel_trade(axes["c"], runs)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig3_switching.png"))


if __name__ == "__main__":
    main()

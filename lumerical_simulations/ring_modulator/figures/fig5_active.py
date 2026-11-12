"""Figure 5 - MODE (FDE): how the effective index of the doped ring responds to reverse bias, and what heat does.

    a  change of the effective index (10^-4) versus reverse bias
    b  free-carrier loss (dB/cm) versus reverse bias, with the loss at 0 V and at 4 V
    c  modulation efficiency V_pi L (V cm) versus reverse bias
    d  resonance shift of the ring (pm) versus reverse bias, with the slope and the heater equivalent

The message: the junction changes the index by 1.7e-4 over 4 V; the heater does the same with a third of a milliwatt.

Reads 5_active_mode_properties/active.npz.

    python fig5_active.py            ->  figures/fig5_active.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
sys.path.insert(0, str(ROOT.parents[1]))
import figstyle as fs  # noqa: E402

STEP = ROOT / "5_active_mode_properties"
SLOPE_WINDOW_V = 0.5  # reverse bias window for the slope near 0 V
XLIM = (-0.2, 4.2)  # the same bias axis in all four panels
XTICKS = [0, 1, 2, 3, 4]


def load() -> dict:
    """Reverse bias (V), its index change, loss, V_pi L and resonance shift, with the scalar results of the run."""
    if not (STEP / "active.npz").exists():
        raise SystemExit("run the active mode simulation first")
    r = np.load(STEP / "active.npz")
    bias = -r["V"]  # anode voltage 0 ... -4 V  ->  reverse bias 0 ... 4 V
    order = np.argsort(bias)
    d = dict(
        bias=bias[order], dn=r["dneff"][order] * 1e4, loss=r["loss_dBcm"][order],
        vpil=r["vpil_Vcm"][order], shift=r["shift_pm"][order],
        base_loss=float(r["base_loss_dBcm"]), thermal=float(r["thermal_pm_per_mW"]),
    )  # fmt: skip
    near = d["bias"] <= SLOPE_WINDOW_V + 1e-9
    d["slope_near0"] = float(np.polyfit(d["bias"][near], d["shift"][near], 1)[0])  # pm/V
    d["slope_window"] = float(d["bias"][near].max())  # V: the bias window of that fit, from the points it uses
    d["slope_full"] = float(d["shift"][-1] / d["bias"][-1])  # pm/V: end-point average over the whole range
    d["bias_max"] = float(d["bias"][-1])  # V
    d["heater_mW"] = float(d["shift"][-1] / d["thermal"])  # mW of heater power that shifts the ring as 4 V does
    return d


def _bias_axes(ax, ylabel: str) -> None:
    ax.set_xlim(*XLIM)
    ax.set_xticks(XTICKS)
    ax.set_xlabel("reverse bias (V)")
    ax.set_ylabel(ylabel)


def panel_index(ax, d: dict) -> None:
    ax.plot(d["bias"], d["dn"], "-o", color=fs.BLUE, ms=3, zorder=3)
    _bias_axes(ax, r"Δn$_{\mathrm{eff}}$ (10$^{-4}$)")
    ax.set_ylim(0, 2.0)
    fs.note(ax, f"{d['dn'][-1]:.2f} × 10$^{{-4}}$ at 4 V", (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)


def panel_loss(ax, d: dict) -> None:
    ax.plot(d["bias"], d["loss"], "-o", color=fs.BLUE, ms=3, zorder=3)
    _bias_axes(ax, "loss (dB cm$^{-1}$)")
    ax.set_ylim(8, 14)
    fs.note(ax, f"0 V: {d['loss'][0]:.1f} dB cm$^{{-1}}$\n4 V: {d['loss'][-1]:.1f} dB cm$^{{-1}}$\n"
            f"undoped: {d['base_loss']:.4f} dB cm$^{{-1}}$", (0.97, 0.96), ha="right", va="top",
            transform=ax.transAxes)  # fmt: skip


def panel_vpil(ax, d: dict) -> None:
    ok = np.isfinite(d["vpil"])  # 0 V has no V_pi L: the index does not move there
    ax.plot(d["bias"][ok], d["vpil"][ok], "-o", color=fs.BLUE, ms=3, zorder=3)
    _bias_axes(ax, r"V$_\pi$L (V cm)")
    ax.set_ylim(1.0, 2.0)
    fs.note(ax, f"{d['vpil'][ok][-1]:.2f} V cm at 4 V", (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)


def panel_shift(ax, d: dict) -> None:
    ax.plot(d["bias"], d["shift"], "-o", color=fs.BLUE, ms=3, zorder=3)
    _bias_axes(ax, "resonance shift (pm)")
    ax.set_ylim(0, 60)  # headroom for the note above the curve's end point at 4 V
    fs.note(
        ax,
        f"{d['slope_near0']:.1f} pm V$^{{-1}}$ over 0 to {d['slope_window']:.1f} V\n"
        f"{d['slope_full']:.1f} pm V$^{{-1}}$ average over 0 to {d['bias_max']:.0f} V",
        (0.03, 0.96),
        ha="left",
        va="top",
        transform=ax.transAxes,
    )
    fs.note(
        ax,
        f"heater: {d['thermal']:.0f} pm per mW\n4 V = {d['heater_mW']:.2f} mW of heater power",
        (0.97, 0.04),
        ha="right",
        va="bottom",
        transform=ax.transAxes,
    )


def main() -> None:
    d = load()
    fig, axes = fs.figure(fs.DOUBLE, 58, ncols=4)
    panel_index(axes[0], d)
    panel_loss(axes[1], d)
    panel_vpil(axes[2], d)
    panel_shift(axes[3], d)
    for letter, ax in zip("abcd", axes, strict=True):
        fs.panel_label(ax, letter)
    fs.save(fig, Path(__file__).with_name("fig5_active.png"))


if __name__ == "__main__":
    main()

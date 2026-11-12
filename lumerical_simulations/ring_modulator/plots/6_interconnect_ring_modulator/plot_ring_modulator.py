"""Step 6 plots: extinction and Q versus gap, spectra versus voltage, spectra versus heater power."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _style import data, plt, save

d = np.load(data("6_interconnect_ring_modulator", "ring_modulator.npz"))
gap = float(d["gap_design"]) * 1000


def spectrum(key: str) -> tuple[np.ndarray, np.ndarray]:
    lam, T = d[f"spec_lam_{key}"] * 1e9, d[f"spec_T_{key}"]
    order = np.argsort(lam)
    return lam[order], 10 * np.log10(np.clip(T[order], 1e-6, None))


fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
ax = axes[0]
ax.plot(d["gaps"] * 1000, d["ext_dB"], "o-", label="extinction at 0 V (dB)")
ax.axvline(float(d["gap_critical"]) * 1000, color="k", ls=":", lw=0.8)
ax.set(xlabel="gap (nm)", ylabel="extinction (dB)", title=f"Critical coupling near {float(d['gap_critical']) * 1000:.0f} nm")
twin = ax.twinx()
twin.plot(d["gaps"] * 1000, d["Q"] / 1000, "C1s--", label="loaded Q (thousands)")
twin.set_ylabel("loaded Q / 1000")
twin.grid(False)
ax.legend(loc="upper left", fontsize=8)
twin.legend(loc="lower right", fontsize=8)

# the resonance nearest the centre of the sweep at 0 V
lam0, T0 = spectrum(f"V{max(d['volts']):+.0f}")
near = np.abs(lam0 - lam0[len(lam0) // 2]) < 2.0
centre = float(lam0[near][np.argmin(T0[near])])

ax = axes[1]
for v in sorted(d["volts"], reverse=True):
    ax.plot(*spectrum(f"V{v:+.0f}"), lw=1, label=f"{v:.0f} V")
ax.set(
    xlim=(centre - 0.4, centre + 0.4),
    xlabel="wavelength (nm)",
    ylabel="transmission (dB)",
    title=f"Junction bias, gap {gap:.0f} nm, loaded Q = {float(d['Q_design']):.0f}",
)
ax.legend(fontsize=8)

ax = axes[2]
for p in d["heater_mW"]:
    ax.plot(*spectrum(f"P{p:.0f}"), lw=1, label=f"{p:.0f} mW")
rate = f"{float(d['thermal_pm_per_mW']):.1f} pm/mW" if "thermal_pm_per_mW" in d else ""
ax.set(xlim=(centre - 1.0, centre + 1.6), xlabel="wavelength (nm)", ylabel="transmission (dB)", title=f"Heater power: {rate}")
ax.legend(fontsize=8)
for ax in axes[1:]:
    ax.ticklabel_format(axis="x", useOffset=False)
save(fig, __file__, "ring_modulator.png")

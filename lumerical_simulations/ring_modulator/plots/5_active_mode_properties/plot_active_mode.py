"""Step 5 plots: change of effective index, loss and ring resonance shift versus voltage."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _style import data, plt, save

d = np.load(data("5_active_mode_properties", "active.npz"))
V = d["V"]
thermal = float(d["thermal_pm_per_mW"])
fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
axes[0].plot(V, d["dneff"] * 1e4, "o-")
axes[0].set(xlabel="anode voltage (V)", ylabel=r"$\Delta n_{eff}$ ($10^{-4}$)", title="Index change of the doped waveguide")
axes[1].plot(V, d["loss_dBcm"], "o-", color="C3")
axes[1].set(xlabel="anode voltage (V)", ylabel="free-carrier loss (dB/cm)", title="Loss falls as the junction depletes")
axes[2].plot(V, d["shift_pm"], "o-", color="C2", label="junction")
axes[2].axhline(thermal, color="C1", ls="--", label=f"1 mW of heater power: {thermal:.1f} pm")
axes[2].set(xlabel="anode voltage (V)", ylabel="resonance shift of the ring (pm)", title="Electrical versus thermal tuning")
axes[2].legend(fontsize=8)
np.seterr(all="ignore")
save(fig, __file__, "active_modes.png")

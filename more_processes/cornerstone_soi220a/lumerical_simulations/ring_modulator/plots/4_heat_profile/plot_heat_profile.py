"""Step 4 plots: temperature map at the reference power and the temperature rise versus power."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _style import data, plt, save

d = np.load(data("4_heat_profile", "heater_heat.npz"))
fig, (a0, a1) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
im = a0.tripcolor(d["T_y"], d["T_z"], d["T_map"] - 300.0, cmap="inferno", shading="gouraud", rasterized=True)
a0.set(
    xlim=(-8, 8),
    ylim=(-2.5, 3.2),
    xlabel="y (um)",
    ylabel="z (um)",
    title=f"Temperature rise (K) at {float(d['P_reference_mW']):.0f} mW; heater above, core at z = 0 ... 0.22 um",
)
a0.set_aspect("equal")
a0.grid(False)
fig.colorbar(im, ax=a0, fraction=0.03, pad=0.02)
a1.plot(d["powers_mW"], d["core_dT"], "o-", label=f"waveguide core: {float(d['dT_dP']):.2f} K/mW")
a1.plot(d["powers_mW"], d["heater_dT"], "s--", label="heater filament")
a1.set(xlabel="heater power (mW)", ylabel="temperature rise (K)", title="Linear in power")
a1.legend(fontsize=8)
np.seterr(all="ignore")
save(fig, __file__, "heat_profile.png")

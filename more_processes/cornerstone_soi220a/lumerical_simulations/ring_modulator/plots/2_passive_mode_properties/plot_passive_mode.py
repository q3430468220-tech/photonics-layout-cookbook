"""Step 2 plots: the TE0 mode, n_eff(lambda), and the bend loss versus radius."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _style import ROOT, plt, save

files = sorted((ROOT / "2_passive_mode_properties").glob("*_passive.npz"))
if not files:
    raise SystemExit("run passive_mode_fde.py first")
d = np.load(files[0])

fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
ax = axes[0]
E = d["E"].T
ax.pcolormesh(d["y"], d["z"], E / E.max(), cmap="magma", shading="auto", rasterized=True)
ax.set_xlim(-1.5, 1.5)
ax.set_ylim(-0.6, 0.8)
ax.set_aspect("equal")
ax.grid(False)
ax.set_xlabel("y (um)")
ax.set_ylabel("z (um)")
ax.set_title(f"TE0 intensity: n_eff = {float(d['neff']):.4f}, n_g = {float(d['ng']):.3f}")

ax = axes[1]
ax.plot(d["sweep_lam"] * 1000, d["sweep_neff"], "o-")
ax.set_xlabel("wavelength (nm)")
ax.set_ylabel("n_eff")
ax.set_title(f"Dispersion (n_g from the slope: {float(d['ng_fit']):.3f})")

ax = axes[2]
loss = np.clip(d["bend_loss_dBcm"], 1e-4, None)
ax.semilogy(d["radii"], loss, "o-", label="radiation loss (dB/cm)")
ax.semilogy(d["radii"], np.clip(1 - d["bend_overlap"], 1e-5, None), "s--", label="1 - overlap with the straight mode")
ax.axvline(25, color="k", lw=0.8, ls=":")
ax.text(25.5, loss.max() / 3, "official minimum\nradius 25 um", fontsize=8)
ax.set_xlabel("bend radius (um)")
ax.set_title("Bent rib waveguide (loss clipped at 1e-4 dB/cm)")
ax.legend(fontsize=8)
save(fig, __file__, "passive_modes.png")

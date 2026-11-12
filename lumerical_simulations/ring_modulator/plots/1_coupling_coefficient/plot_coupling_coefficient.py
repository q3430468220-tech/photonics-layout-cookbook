"""Step 1 plots: kappa^2 and t^2 versus gap with the exponential fit, and the field in the coupler."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _style import ROOT, data, plt, save

STEP = "1_coupling_coefficient"

with open(data(STEP, "coupling_vs_gap.csv"), encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
gap = np.array([float(r["gap_um"]) for r in rows]) * 1000
kappa2 = np.array([float(r["kappa2_S41"]) for r in rows])
t2 = np.array([float(r["t2_S21"]) for r in rows])
slope, intercept = np.polyfit(gap, np.log(kappa2), 1)

fig, (a0, a1) = plt.subplots(1, 2, figsize=(10, 3.6))
g = np.linspace(gap.min() - 20, gap.max() + 80, 200)
a0.semilogy(g, np.exp(intercept + slope * g), "C0--", lw=1, label=f"fit: {np.exp(intercept):.2f} exp(-gap / {-1 / slope:.0f} nm)")
a0.semilogy(gap, kappa2, "C0o", label=r"$\kappa^2$ = $|S_{41}|^2$ (FDTD)")
a0.set_xlabel("gap (nm)")
a0.set_ylabel(r"power coupling $\kappa^2$")
a0.set_title("Coupling into the ring, 1550 nm")
a0.legend()
a1.plot(gap, kappa2 + t2, "C2s-", label=r"$\kappa^2 + t^2$")
a1.plot(gap, t2, "C1o-", label=r"$t^2$ = $|S_{21}|^2$")
a1.set_xlabel("gap (nm)")
a1.set_ylabel("power")
a1.set_title("Power balance (1 = lossless coupler)")
a1.legend()
save(fig, __file__, "coupling_vs_gap.png")

files = sorted((ROOT / STEP).glob("coupler_gap*.npz"))
if files:
    d = np.load(files[len(files) // 2], allow_pickle=True)
    fig, ax = plt.subplots(figsize=(10, 2.8))
    field = d["field_E"].T
    im = ax.pcolormesh(d["field_x"], d["field_y"], field / field.max(), cmap="magma", shading="auto", rasterized=True)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(f"|E| at mid-height of the core, gap = {float(d['gap']) * 1000:.0f} nm, light enters at the lower left")
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    save(fig, __file__, "coupler_field.png")

"""Step 3 plots: net doping, holes and electrons at two bias points, C(V) and the RC bandwidth."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.tri import Triangulation

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _style import data, plt, save

d = np.load(data("3_charge_profile", "pn_rib_charge.npz"))
V = d["V"]
k0, k1 = int(np.argmax(V)), int(np.argmin(V))
window = dict(xlim=(-1.2, 1.2), ylim=(-0.05, 0.27))


def mesh(y, z, elements) -> Triangulation:
    """The solver's own triangles (1-based node numbers), so that nothing is drawn outside the silicon."""
    return Triangulation(y, z, triangles=np.asarray(elements, dtype=int) - 1)


fig, axes = plt.subplots(2, 3, figsize=(13, 5.6))
ax = axes[0, 0]
net = d["ND"].astype(float) - d["NA"].astype(float)
signed = np.sign(net) * np.log10(np.clip(np.abs(net), 1e15, None) / 1e15)
ax.tripcolor(
    mesh(d["doping_y"], d["doping_z"], d["doping_elements"]),
    signed,
    cmap="RdBu",
    vmin=-5,
    vmax=5,
    shading="gouraud",
    rasterized=True,
)
ax.set(title="Net doping: red = p, blue = n (log, 1e15 ... 1e20 cm$^{-3}$)", **window)
panels = (
    (axes[0, 1], "p", k0, "holes"),
    (axes[0, 2], "p", k1, "holes"),
    (axes[1, 1], "n", k0, "electrons"),
    (axes[1, 2], "n", k1, "electrons"),
)
for ax, key, k, label in panels:
    values = np.log10(np.clip(d[key][:, k], 1e14, None))
    im = ax.tripcolor(
        mesh(d["y"], d["z"], d["elements"]), values, cmap="viridis", vmin=15, vmax=18.5, shading="gouraud", rasterized=True
    )
    ax.set(title=f"log10 {label} (cm$^{{-3}}$) at {V[k]:.0f} V", **window)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
for ax in (axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 1], axes[1, 2]):
    ax.set_xlabel("y (um)")
    ax.set_ylabel("z (um)")
    ax.grid(False)

ax = axes[1, 0]
if "C_V" in d:
    ax.plot(V, d["C_V"] * 1e15 / float(d["L_pn_um"]), "o-", label="C (fF/um)")
    ax.set_xlabel("anode voltage (V)")
    ax.set_ylabel("capacitance (fF/um)")
    twin = ax.twinx()
    twin.plot(V, d["f_RC"] / 1e9, "C1s--", label="intrinsic f_RC (GHz)")
    twin.set_ylabel("f_RC (GHz)")
    twin.grid(False)
    ax.set_title(f"Junction {float(d['junction_y_um']) * 1000:+.0f} nm from the core centre")
    ax.legend(loc="upper left", fontsize=8)
    twin.legend(loc="lower left", fontsize=8)
save(fig, __file__, "charge_profile.png")

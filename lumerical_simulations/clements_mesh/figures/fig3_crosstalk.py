"""Figure 3 - the heat of the neighbours in the 4 x 4 mesh, and its calibration.

    a  the mesh at the powers of the DFT: how much the other heaters warm every waveguide under a heater position
    b  the share of a heater's phase that a waveguide takes, against the distance between them, for every pair
    c  1 - F of every target: without the heat, with it as programmed, after the linear calibration, after the fit

Reads 3_crosstalk/crosstalk.npz; the places of the blocks come from the builder of the mesh.

    python fig3_crosstalk.py            ->  figures/fig3_crosstalk.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/clements_mesh/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

from devices import clements_mesh_builder as cm  # noqa: E402

DATA = ROOT / "3_crosstalk" / "crosstalk.npz"


def panel_map(ax, d: dict) -> None:
    info = cm.clements_mesh().info
    n, length = info["n"], info["length"]
    S, F, dcl = info["section"], info["fan_length"], info["coupler_length"]
    for m in range(n):
        ax.plot([0, length / 1000], [-m, -m], color=fs.HAIRLINE, lw=0.8, zorder=0)
    for b in info["blocks"]:
        for x in (b["x0"] + S + F + dcl / 2, b["x0"] + 2 * S + 3 * F + 1.5 * dcl):
            p = b["upper"]
            ax.plot([(x - 35) / 1000, x / 1000, (x + 35) / 1000], [-p, -p - 0.5, -p], color=fs.MUTED, lw=0.8, zorder=1)
            ax.plot([(x - 35) / 1000, x / 1000, (x + 35) / 1000], [-p - 1, -p - 0.5, -p - 1], color=fs.MUTED, lw=0.8, zorder=1)
    extra = d["extra_K_dft"]
    norm = Normalize(0, extra.max())
    own = set(int(s) for s in d["own_site"])
    for s, (row, x, k) in enumerate(zip(d["site_row"], d["site_x"], extra, strict=False)):
        ax.add_patch(Rectangle(((x - 50) / 1000, -row - 0.13), 0.1, 0.26, color=fs.CMAP_HEAT(norm(k)),
                               ec=fs.INK if s in own else fs.MUTED, lw=0.6 if s in own else 0.4, ls="-" if s in own else ":", zorder=2))  # fmt: skip
    ax.set_xlim(-0.02, length / 1000 + 0.02)
    ax.set_ylim(-n + 0.5, 0.6)
    ax.set_yticks([-m for m in range(n)])
    ax.set_yticklabels([f"row {m}" for m in range(n)])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("position along the mesh (mm)")
    fs.colorbar_beside(ax, ScalarMappable(norm=norm, cmap=fs.CMAP_HEAT), "warmed by the others (K)")
    fs.panel_title(ax, "the DFT: what the neighbours add (solid: a heater, dotted: none)")


def panel_share(ax, d: dict) -> None:
    share = d["share"]
    rows, xs = d["site_row"], d["site_x"]
    pitch = cm.PITCH
    same, other = [], []
    for s in range(share.shape[0]):
        for j in range(share.shape[1]):
            if int(d["own_site"][j]) == s:
                continue
            dy = abs(rows[s] - d["heater_row"][j]) * pitch
            dx = abs(xs[s] - d["heater_x"][j])
            (same if dx < 1e-6 else other).append((np.hypot(dx, dy), 100 * share[s, j]))
    for pts, color, label in ((same, fs.BLUE, "beside it, at the same x"), (other, fs.AQUA, "elsewhere along the mesh")):
        a = np.array(pts)
        ax.plot(a[:, 0], a[:, 1], "o", ms=2.2, color=color, alpha=0.75, lw=0, label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(20, 3000)
    ax.set_xlabel("distance between the centres (µm)")
    ax.set_ylabel("share of the heater's phase (%)")
    ax.legend(frameon=False, fontsize=6, loc="lower left", handletextpad=0.2)
    fs.panel_title(ax, "through the substrate")


def panel_fidelity(ax, d: dict) -> None:
    cases = (("without\nthe heat", d["fidelity_without"]), ("as\nprogrammed", d["fidelity_naive"]),
             ("linear\ncalibration", d["fidelity_linear"]), ("fitted", d["fidelity_fitted"]))  # fmt: skip
    rng = np.random.default_rng(0)
    for k, (_, f) in enumerate(cases):
        v = 1 - np.asarray(f)
        ax.plot(k + rng.uniform(-0.18, 0.18, v.size - 1), v[1:], "o", ms=2.4, color=fs.AQUA, alpha=0.8, lw=0)
        ax.plot([k], [v[0]], "D", ms=4, color=fs.BLUE, lw=0)
        ax.plot([k - 0.28, k + 0.28], [np.median(v[1:])] * 2, color=fs.INK, lw=0.8)
    ax.set_yscale("log")
    ax.set_xticks(range(len(cases)))
    ax.set_xticklabels([c[0] for c in cases])
    ax.set_xlim(-0.6, len(cases) - 0.4)
    ax.set_ylabel("1 − F at 1550 nm")
    fs.note(ax, "DFT", (0.25, 1 - float(d["fidelity_without"][0])), ha="left", color=fs.BLUE)
    fs.panel_title(ax, "random unitaries and the DFT")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 120, [["a", "a"], ["b", "c"]], height_ratios=[0.85, 1.0])
    panel_map(axes["a"], d)
    panel_share(axes["b"], d)
    panel_fidelity(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig3_crosstalk.png"))


if __name__ == "__main__":
    main()

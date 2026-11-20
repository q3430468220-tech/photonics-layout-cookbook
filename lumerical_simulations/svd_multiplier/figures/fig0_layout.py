"""Figure 0 - the layout of the 4 x 4 real matrix multiplier, drawn from its GDS file.

    a  the whole multiplier: mesh V, the column of attenuators, mesh U
    b  the column of attenuators, enlarged: each row with its dump above it, the heater on the dump arm

Reads devices/gds/svd_multiplier.gds and the info of the builder (for where each part starts).  The layers and their
colours are those of the figure of the mesh (clements_mesh/figures/fig0_layout.py).

    python fig0_layout.py            ->  figures/fig0_layout.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import klayout.db as kdb
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/svd_multiplier/
sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT.parent / "clements_mesh" / "figures"))
import fig0_layout as mesh_figure  # noqa: E402  (the drawing of the layers, from the figure of the mesh)
from panels import fs  # noqa: E402

from devices import GDS  # noqa: E402
from devices import svd_multiplier_builder as sb  # noqa: E402


def main() -> None:
    layout = kdb.Layout()
    layout.read(str(GDS / "svd_multiplier.gds"))
    cell = layout.top_cell()
    info = sb.svd_multiplier().info
    att = info["a"]
    fig, axes = fs.mosaic(fs.DOUBLE, 88, [["a"], ["b"]], height_ratios=[0.5, 1.0])

    ax = axes["a"]
    mesh_figure.draw(ax, layout, cell)
    box = cell.dbbox()
    ax.set_xlim(box.left / 1000 - 0.02, box.right / 1000 + 0.02)
    ax.set_ylim(box.bottom / 1000 - 0.03, box.top / 1000 + 0.06)
    ax.set_xlabel("x (mm)")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    top = box.top / 1000 + 0.015
    for key, label in (("v", "mesh V: sets Vᵀ"), ("a", "attenuators: Σ"), ("u", "mesh U: sets U")):
        x0 = info["x"][key] / 1000
        x1 = x0 + (att["length"] if key == "a" else info[key]["length"]) / 1000
        ax.plot([x0 + 0.01, x1 - 0.01], [top, top], color=fs.SECONDARY, lw=0.6)
        fs.note(ax, label, ((x0 + x1) / 2, top + 0.008), ha="center", va="bottom")
    xa = info["x"]["a"] / 1000
    ax.add_patch(Rectangle((xa, box.bottom / 1000 - 0.01), att["length"] / 1000, (box.top - box.bottom) / 1000 + 0.02,
                           fill=False, ec=fs.SECONDARY, lw=0.6, ls=(0, (3, 2))))  # fmt: skip
    fs.panel_title(ax, f"{info['n']} × {info['n']} real matrix multiplier: {info['heaters']} heaters, {2 * info['heaters']} pads, "
                       f"{info['length'] / 1000:.2f} mm long")  # fmt: skip
    for _, color, alpha, label in mesh_figure.LAYERS:
        ax.plot([], [], "s", color=color, alpha=alpha, ms=5, label=label)
    ax.legend(
        frameon=False, fontsize=6, ncol=5, loc="lower right", bbox_to_anchor=(1.0, -0.62), handletextpad=0.2, columnspacing=1.0
    )

    ax = axes["b"]
    mesh_figure.draw(ax, layout, cell, scale=1000)  # in um
    xa_um = info["x"]["a"]
    pitch = att["pitch"]
    ax.set_xlim(xa_um, xa_um + att["length"])  # the column alone, from the last heater of mesh V to the first of mesh U
    ax.set_ylim(-(info["n"] - 1) * pitch - 14, pitch / 2 + 16)  # the waveguides and heaters; the pads run off the panel
    ax.set_xlabel("x (µm)")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    F, dcl, S = att["fan_length"], att["coupler_length"], att["section"]
    for unit in att["units"]:
        x0 = xa_um + unit["x0"]
        row = unit["dump_y"] - pitch / 2
        fs.note(ax, f"row {unit['row']}", (xa_um + 3, row - 2), ha="left", va="top")
        fs.note(ax, "θ", (x0 + 2 * F + dcl + S / 2, unit["dump_y"] - 2.5), ha="center", va="top")
        if unit["row"] == 1:
            fs.note(ax, "its dump →", (x0 - 3, unit["dump_y"]), ha="right", va="center")
    fs.panel_title(
        ax, "the attenuators: each row meets its dump in two couplers; the heater on the dump arm sets what the row keeps"
    )
    for key, a in axes.items():
        fs.panel_label(a, key)
    fs.save(fig, Path(__file__).with_name("fig0_layout.png"))


if __name__ == "__main__":
    main()

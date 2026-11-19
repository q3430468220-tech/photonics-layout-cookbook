"""Figure 0 - the layout of the 4 x 4 mesh, drawn from its GDS file.

    a  the whole mesh: waveguides, heaters with their trenches, wires and pads
    b  one block (column 0, rows 0 and 1) and the dummy path of an edge row (column 1, row 0), enlarged

Reads devices/gds/clements_mesh.gds and the info of the builder (for the places of the blocks).

    python fig0_layout.py            ->  figures/fig0_layout.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import klayout.db as kdb
from matplotlib.collections import PolyCollection
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/clements_mesh/
sys.path.insert(0, str(ROOT.parent))
from panels import fs  # noqa: E402

import gsip_technology as t  # noqa: E402
from devices import GDS  # noqa: E402
from devices import clements_mesh_builder as cm  # noqa: E402

# what is drawn, in this order, with its colour: the layers of the layout in the colours of the materials
LAYERS = (
    ("DEEPTRENCH", fs.HAIRLINE, 0.9, "trench"),
    ("M2", fs.MATERIAL_COLORS["aluminium"], 0.55, "metal 2"),
    ("M3", fs.MATERIAL_COLORS["aluminium"], 0.9, "pad"),
    ("WG", fs.MATERIAL_COLORS["silicon"], 1.0, "silicon"),
    ("HEATER", fs.MATERIAL_COLORS["tin"], 1.0, "heater (TiN)"),
)


def polygons(layout: kdb.Layout, cell: kdb.Cell, name: str) -> list:
    layer, datatype = tuple(getattr(t.LAYER, name))
    index = layout.find_layer(layer, datatype)
    if index is None:
        return []
    region = kdb.Region(cell.begin_shapes_rec(index))
    dbu = layout.dbu
    out = []
    for poly in region.each_merged():
        for p in poly.decompose_trapezoids() if poly.holes() else [poly]:
            out.append([(pt.x * dbu / 1000, pt.y * dbu / 1000) for pt in p.each_point_hull()])  # mm
    return out


def draw(ax, layout, cell, scale: float = 1.0) -> None:
    for name, color, alpha, _ in LAYERS:
        polys = [[(x * scale, y * scale) for x, y in p] for p in polygons(layout, cell, name)]
        ax.add_collection(PolyCollection(polys, facecolors=color, edgecolors="none", alpha=alpha))
    ax.set_aspect("equal")


def main() -> None:
    layout = kdb.Layout()
    layout.read(str(GDS / "clements_mesh.gds"))
    cell = layout.top_cell()
    info = cm.clements_mesh().info
    fig, axes = fs.mosaic(fs.DOUBLE, 78, [["a"], ["b"]], height_ratios=[1.0, 0.9])
    ax = axes["a"]
    draw(ax, layout, cell)
    box = cell.dbbox()
    ax.set_xlim(box.left / 1000 - 0.02, box.right / 1000 + 0.02)
    ax.set_ylim(box.bottom / 1000 - 0.02, box.top / 1000 + 0.02)
    ax.set_xlabel("x (mm)")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    x0 = info["blocks"][0]["x0"] / 1000
    x1 = (info["blocks"][0]["x0"] + 2 * info["block_length"]) / 1000
    ax.add_patch(Rectangle(
        (x0 - 0.005, -0.055), x1 - x0 + 0.01, 0.075, fill=False, ec=fs.SECONDARY, lw=0.6, ls=(0, (3, 2))))  # fmt: skip
    fs.note(ax, "b", (x1 + 0.01, 0.01), ha="left")
    fs.panel_title(ax, f"{info['n']} × {info['n']} mesh: {len(info['blocks'])} blocks, {len(info['heaters'])} heaters, "
                       f"{2 * len(info['heaters'])} pads, {info['length'] / 1000:.2f} mm long")  # fmt: skip
    for _k, (_, color, alpha, label) in enumerate(LAYERS):
        ax.plot([], [], "s", color=color, alpha=alpha, ms=5, label=label)
    ax.legend(
        frameon=False, fontsize=6, ncol=5, loc="upper right", bbox_to_anchor=(1.0, 1.12), handletextpad=0.2, columnspacing=1.0
    )

    ax = axes["b"]
    draw(ax, layout, cell, scale=1000)  # in um
    ax.set_xlim(x0 * 1000 - 32, x1 * 1000 + 5)
    ax.set_ylim(-54, 22)
    ax.set_xlabel("x (µm)")
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    S, F, dcl = info["section"], info["fan_length"], info["coupler_length"]
    b0 = info["blocks"][0]["x0"]
    labels = (
        (b0 + S / 2, 11, "φ"), (b0 + 1.5 * S + 2 * F + dcl, 11, "θ"),
        (b0 + S + F + dcl / 2, -22, "coupler"), (b0 + 2 * S + 3 * F + 1.5 * dcl, -22, "coupler"),
        (b0 + info["block_length"] + S + F + dcl / 2, -8, "dummy arm"),
        (b0 + info["block_length"] + 2 * S + 3 * F + 1.5 * dcl, -8, "dummy arm"),
    )  # fmt: skip
    for x, y, text in labels:
        fs.note(ax, text, (x, y), ha="center")
    fs.note(ax, "row 0", (x0 * 1000 - 30, 2), ha="left", va="bottom")
    fs.note(ax, "row 1", (x0 * 1000 - 30, -28), ha="left", va="bottom")
    fs.panel_title(ax, "one block, then the dummy path of row 0 in the next column (row 1 runs into the next block)")
    for key, a in axes.items():
        fs.panel_label(a, key)
    fs.save(fig, Path(__file__).with_name("fig0_layout.png"))


if __name__ == "__main__":
    main()

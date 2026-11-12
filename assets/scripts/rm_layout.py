"""Device layout of the heater-tuned ring modulator, taken apart layer group by layer group.

    a  the whole device: bus, ring, metal 2 wires and the five pads of metal 3; the sixteen layers as a table below
    b  silicon and implants: slab, core and the six implant masks, opaque and in order
    c  contacts, metal 1 and heater, over a pale ghost of the silicon
    d  via 1 and metal 2, over a pale ghost of metal 1 and the heater
    e  all layers, bottom to top with opaque fills; metal 2 as outline only

Reads rm_ring.gds (the flat layout of rm_builder.py). Layer numbers and colours come from gsip_technology,
dimensions from the defaults of rm_builder.ring_modulator; every number in the figure is computed from them.

    python -X utf8 assets/scripts/rm_layout.py     ->  assets/rm_layout.png
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repository root: figstyle.py, gsip_technology.py, rm_builder.py
sys.path.insert(0, str(ROOT))
import klayout.db as kdb  # noqa: E402
import matplotlib.colors as mcolors  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402
import rm_builder as rm  # noqa: E402

GDS = ROOT / "rm_ring.gds"
WINDOW = (-14.5, 14.5, -15.5, 13.5)  # um: x0, x1, y0, y1 of the zoom panels b to e
SCALE_DEVICE_UM = 50
SCALE_RING_UM = 5
# the sixteen layers, in the order of the legend table (six rows per column)
LAYERS = ("SLAB90", "WG", "N", "P", "NP", "PP", "NPP", "PPP", "VIAC", "M1", "HEATER", "VIA1", "M2", "VIA2", "M3", "PADOPEN")
TINT = {"SLAB90": 0.55, "M1": 0.35, "M2": 0.5, "M3": 0.72}  # large areas take a light tint of the layer colour
GHOST = "#ededea"  # pale silicon or metal, for orientation only
HALO = {"bbox": {"facecolor": "white", "edgecolor": "none", "pad": 0.8}}  # air behind a label on a ghost
LEGEND_X = (-150.0, -50.0, 50.0)  # um, left edge of the three legend columns
LEGEND_TOP, LEGEND_STEP = -192.0, 12.5  # um, first row and row pitch of the table
DEVICE_YLIM = (-270.0, 150.0)  # the legend sits below the device, in the same axes


# =====================================================================================
# geometry from the GDS
# =====================================================================================
def _contour(points, dbu: float) -> tuple[np.ndarray, list[int]]:
    xy = np.array([(p.x * dbu, p.y * dbu) for p in points], dtype=float)
    xy = np.vstack([xy, xy[:1]])
    return xy, [MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY]


def _polygon_path(poly, dbu: float) -> MPath:
    """Outline and holes of one polygon as a matplotlib path (um)."""
    contours = [_contour(poly.each_point_hull(), dbu)]
    contours += [_contour(poly.each_point_hole(i), dbu) for i in range(poly.holes())]
    return MPath(np.vstack([c[0] for c in contours]), [code for c in contours for code in c[1]])


def load(path: Path = GDS) -> dict[str, list[MPath]]:
    """The merged polygons of every layer of the device, in um."""
    layout = kdb.Layout()
    layout.read(str(path))
    top = layout.top_cell()
    shapes = {}
    for name in LAYERS:
        layer = layout.layer(*tuple(getattr(t.LAYER, name)))
        region = kdb.Region(top.begin_shapes_rec(layer)).merged()
        shapes[name] = [_polygon_path(poly, layout.dbu) for poly in region.each()]
    return shapes


def dimensions(info) -> dict[str, float]:
    """Dimensions of the device (um, deg): the defaults of ring_modulator and the lengths of its info."""
    params = inspect.signature(rm.ring_modulator).parameters
    d = {k: float(params[k].default) for k in ("radius", "width", "gap", "pn_angle", "heater_angle", "pad_size")}
    d["length_pn"] = float(info["length_pn"])
    d["length_heater"] = float(info["length_heater"])
    d["y_bus"] = -(d["radius"] + d["width"] + d["gap"])
    return d


# =====================================================================================
# colours: the layer colours of the PDK; large areas lighter, small features saturated
# =====================================================================================
def _rgb(colour: str) -> np.ndarray:
    return np.array(mcolors.to_rgb(colour))


def face(name: str) -> tuple[float, ...]:
    base = _rgb(t.LAYER_COLORS[name])
    return tuple(base + (1 - base) * TINT[name]) if name in TINT else tuple(base)


def edge(name: str) -> tuple[float, ...]:
    return tuple(_rgb(t.LAYER_COLORS[name]) * 0.55)  # a darker shade of the fill


# =====================================================================================
# drawing
# =====================================================================================
def draw(ax, shapes: dict[str, list[MPath]], name: str, mode: str = "fill", lw: float = 0.3) -> None:
    """One layer: ``fill`` (face and outline), ``line`` (outline only) or ``ghost`` (pale, for orientation)."""
    for path in shapes[name]:
        if mode == "ghost":
            fc, ec = GHOST, fs.HAIRLINE
        elif mode == "line":
            fc, ec = "none", edge(name)
        else:
            fc, ec = face(name), edge(name)
        ax.add_patch(PathPatch(path, facecolor=fc, edgecolor=ec, linewidth=lw))


def window(ax, title: str) -> None:
    """A zoom panel: the common window, equal aspect, no ticks, a thin frame."""
    ax.set_xlim(WINDOW[0], WINDOW[1])
    ax.set_ylim(WINDOW[2], WINDOW[3])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
    fs.panel_title(ax, title)


def legend(ax) -> None:
    """The sixteen layers as a small table: swatch, name, gds/datatype; three columns of at most six rows."""
    for x0 in LEGEND_X:
        ax.text(x0 + 20, LEGEND_TOP + LEGEND_STEP, "layer", fontsize=6, color=fs.SECONDARY, va="center")
        ax.text(x0 + 94, LEGEND_TOP + LEGEND_STEP, "gds/dt", fontsize=6, color=fs.SECONDARY, ha="right", va="center")
    ax.plot([LEGEND_X[0], LEGEND_X[0] + 288], [LEGEND_TOP + 6, LEGEND_TOP + 6], color=fs.HAIRLINE, lw=0.4)
    for i, name in enumerate(LAYERS):
        col, row = divmod(i, 6)
        x0, y = LEGEND_X[col], LEGEND_TOP - row * LEGEND_STEP
        layer = tuple(getattr(t.LAYER, name))
        fc = "none" if name == "PADOPEN" else face(name)
        ax.add_patch(Rectangle((x0, y - 4), 14, 8, facecolor=fc, edgecolor=edge(name), linewidth=0.4))
        ax.text(x0 + 20, y, name, fontsize=6, color=fs.INK, va="center")
        ax.text(x0 + 94, y, f"{layer[0]}/{layer[1]}", fontsize=6, color=fs.SECONDARY, ha="right", va="center")


# =====================================================================================
# panels
# =====================================================================================
def panel_device(ax, shapes, ports: dict[str, tuple[float, float]], dims: dict[str, float]) -> None:
    """a: the whole device, its pads and ports, the zoom window and the legend table."""
    for name in ("SLAB90", "WG", "M1", "HEATER", "M2", "M3"):
        draw(ax, shapes, name, lw=0.25)
    draw(ax, shapes, "PADOPEN", mode="line", lw=0.3)
    half = dims["pad_size"] / 2 + 3
    for name, (x, y) in ports.items():
        if name[0] in "GSH":
            up = y > 0
            ax.text(x, y + half if up else y - half, name[0], fontsize=7, color=fs.INK, ha="center",
                    va="bottom" if up else "top")  # fmt: skip
    ax.text(ports["o1"][0] - 4, ports["o1"][1], "in", fontsize=6, color=fs.INK, ha="right", va="center")
    ax.text(ports["o2"][0] + 4, ports["o2"][1], "through", fontsize=6, color=fs.INK, ha="left", va="center")
    ax.add_patch(
        Rectangle(
            (WINDOW[0], WINDOW[2]), WINDOW[1] - WINDOW[0], WINDOW[3] - WINDOW[2], fill=False, edgecolor=fs.INK, linewidth=0.5
        )
    )
    ax.text(WINDOW[1] + 3, -1.0, "b to e", fontsize=6, color=fs.SECONDARY, ha="left", va="center")
    ax.plot([98, 98 + SCALE_DEVICE_UM], [-144, -144], color=fs.INK, lw=1.2, solid_capstyle="butt")
    ax.text(98 + SCALE_DEVICE_UM / 2, -141, f"{SCALE_DEVICE_UM} µm", fontsize=6, color=fs.INK, ha="center", va="bottom")
    legend(ax)
    ax.set_xlim(-150, 150)
    ax.set_ylim(*DEVICE_YLIM)
    ax.set_aspect("equal")
    ax.set_axis_off()
    fs.panel_title(ax, "whole device")


def panel_silicon(ax, shapes, dims: dict[str, float]) -> None:
    """b: slab and the six implants, opaque; the core as an outline."""
    draw(ax, shapes, "SLAB90")
    for name in ("N", "P", "NP", "PP", "NPP", "PPP"):
        draw(ax, shapes, name, lw=0.25)
    draw(ax, shapes, "WG", mode="line", lw=0.6)
    window(ax, "silicon and implants")
    fs.note(ax, "p outside", (-8.9, 9.2), xytext=(-13.8, 12.8), ha="left", va="top", color=fs.INK)
    fs.note(ax, "n inside", (0, 5.2), ha="center", color=fs.INK)
    fs.note(
        ax, f"PN section, {dims['pn_angle']:g}°\n{dims['length_pn']:.2f} µm", (0, 1.2), ha="center", color=fs.INK, linespacing=1.3
    )
    fs.note(ax, "undoped at\nthe coupler", (0, -8.6), xytext=(0, -3.4), ha="center", color=fs.INK, linespacing=1.3)
    fs.note(ax, "bus", (-12.5, -11.0), xytext=(-13.9, -14.6), ha="left", color=fs.INK)
    fs.note(ax, f"gap {dims['gap']:.2f} µm", (0.0, -10.44), xytext=(13.9, -14.6), ha="right", color=fs.INK)
    ax.plot([8.5, 8.5 + SCALE_RING_UM], [11.0, 11.0], color=fs.INK, lw=1.2, solid_capstyle="butt")
    ax.text(8.5 + SCALE_RING_UM / 2, 11.5, f"{SCALE_RING_UM} µm", fontsize=6, color=fs.INK, ha="center", va="bottom")


def panel_contacts(ax, shapes, dims: dict[str, float]) -> None:
    """c: contact vias, metal 1 and the heater, over a ghost of the silicon."""
    draw(ax, shapes, "SLAB90", mode="ghost")
    draw(ax, shapes, "WG", mode="ghost")
    draw(ax, shapes, "M1")
    draw(ax, shapes, "HEATER")
    draw(ax, shapes, "VIAC")
    window(ax, "contacts, metal 1 and heater")
    fs.note(ax, "contact vias", (-8.6, 8.6), xytext=(-13.8, 13.0), ha="left", va="top", color=fs.INK)
    fs.note(ax, "metal 1 ·\nground\n(G)", (6.3, 10.9), xytext=(13.8, 13.2), ha="right", va="top", color=fs.INK, linespacing=1.3)
    fs.note(ax, "metal 1 ·\nsignal (S)", (0, -2.2), ha="center", color=fs.INK, linespacing=1.3)
    fs.note(
        ax,
        f"TiN heater, {dims['heater_angle']:g}°\n{dims['length_heater']:.2f} µm",
        (-8.5, -9.1),
        xytext=(-13.8, -10.6),
        ha="left",
        va="top",
        color=fs.INK,
        linespacing=1.3,
        **HALO,
    )
    fs.note(ax, "landing", (8.1, -8.1), xytext=(13.8, -14.6), ha="right", color=fs.INK, **HALO)


def panel_metal2(ax, shapes) -> None:
    """d: via 1 and the metal 2 wires, over a ghost of metal 1 and the heater."""
    draw(ax, shapes, "M1", mode="ghost")
    draw(ax, shapes, "HEATER", mode="ghost")
    draw(ax, shapes, "M2")
    draw(ax, shapes, "VIA1")
    window(ax, "via 1 and metal 2")
    fs.note(ax, "to pads G", (-13.8, 12.1), ha="left", va="bottom", color=fs.INK, **HALO)
    fs.note(ax, "to pad S", (4.0, 13.0), ha="left", va="top", color=fs.INK, **HALO)
    fs.note(ax, "to the heater\npads", (0, -13.3), ha="center", color=fs.INK, linespacing=1.3, **HALO)
    fs.note(ax, "via 1", (-2.0, -2.0), xytext=(-13.8, -4.4), ha="left", color=fs.INK, **HALO)


def panel_all(ax, shapes) -> None:
    """e: every layer, bottom to top, opaque; metal 2 as an outline so that the ring stays visible."""
    for name in ("SLAB90", "N", "P", "NP", "PP", "NPP", "PPP", "WG", "VIAC", "M1", "HEATER", "VIA1"):
        draw(ax, shapes, name)
    draw(ax, shapes, "M2", mode="line", lw=0.3)
    window(ax, "all layers")


def main() -> None:
    shapes = load()
    device = rm.ring_modulator()
    ports = {p.name: tuple(float(v) for v in p.center) for p in device.ports}
    dims = dimensions(device.info)
    fig, axes = fs.mosaic(fs.DOUBLE, 108, [["a", "b", "c"], ["a", "d", "e"]], width_ratios=[1.5, 1, 1])
    panel_device(axes["a"], shapes, ports, dims)
    panel_silicon(axes["b"], shapes, dims)
    panel_contacts(axes["c"], shapes, dims)
    panel_metal2(axes["d"], shapes)
    panel_all(axes["e"], shapes)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, ROOT / "assets" / "rm_layout.png")


if __name__ == "__main__":
    main()

"""Figure 0 - Layer Builder check: the 3D structure that the GDS layout and the process file produce.

    a  vertical cut through the PN section on the north side of the ring, from the buried oxide to metal 2:
       the layers of the device at their heights (the check itself also probes the substrate below)
    b  vertical cut through the coupler: ring core and bus core on a common slab, with the gap between them
    c  horizontal cut at the slab level (45 nm)
    d  horizontal cut at the core level (160 nm)
    e  horizontal cut at metal 1 and the heater (1.17 µm)
    f  horizontal cut at metal 2 (2.65 µm)

Reads 0_layer_builder_check/structure.npz: complex refractive indices at 1550 nm, sampled on planes of the finished device.

    python fig0_layer_builder.py     ->  figures/fig0_layer_builder.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

RING = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
REPO = Path(__file__).resolve().parents[3]  # repository root
sys.path.insert(0, str(REPO))
import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402

DATA = RING / "0_layer_builder_check" / "structure.npz"
HALF = 15.0  # µm, half-width of the horizontal cuts
ZOOM = 1.9  # µm, half-width of the coupler window in y
PN_WINDOW = (-4.5, 4.5, -0.7, 3.6)  # µm: panel a shows the device levels, however deep the cut of the check reaches
COUPLER_Z = (-0.5, 1.0)  # µm: panel b
SCALE_BAR = 5.0  # µm
MATERIALS = ["oxide", "silicon", "aluminium", "tin"]  # the order of fs.material_map
MATERIAL_LABELS = ["oxide", "silicon", "aluminium", "TiN"]


def load() -> dict:
    """All arrays of the Layer Builder check, as a plain dictionary."""
    if not DATA.exists():
        raise SystemExit("run the Layer Builder check first: 0_layer_builder_check/structure.npz is missing")
    with np.load(DATA) as npz:
        return {key: npz[key] for key in npz.files}


def _block_sum(mask: np.ndarray) -> np.ndarray:
    """Number of True cells in the 3 x 3 block around every cell."""
    pad = np.pad(mask.astype(int), 1)
    nx, ny = mask.shape
    return sum(pad[1 + i : 1 + i + nx, 1 + j : 1 + j + ny] for i in (-1, 0, 1) for j in (-1, 0, 1))


def _despeckle(cells: np.ndarray) -> np.ndarray:
    """Give the TiN class back to the neighbours where it is not a film.

    A cell on the edge of aluminium has a mixed index and falls into the TiN class. A TiN film is several cells thick,
    so a TiN cell with fewer than four TiN cells in its 3 x 3 block is such an edge cell; it takes its neighbours' class.
    """
    out = cells.copy()
    lone = (cells == 3) & (_block_sum(cells == 3) < 4)
    al, ox = _block_sum(cells == 2), _block_sum(cells == 0)
    out[lone] = np.where(al[lone] >= ox[lone], 2, 0)
    return out


def _image(ax, x: np.ndarray, y: np.ndarray, index: np.ndarray) -> None:
    """Material map of a complex index array indexed [x, y]; the cell colours are the four materials."""
    cells, cmap, _ = fs.material_map(index)
    cells = _despeckle(cells)
    ax.pcolormesh(x, y, cells.T, cmap=cmap, vmin=-0.5, vmax=len(MATERIALS) - 0.5, shading="auto", rasterized=True)


def panel_pn(ax, d: dict) -> None:
    """The PN section on the north side, seen like every other cross-section: the ring centre lies to the right."""
    across = float(d["radius"]) - d["pn_section_y"]  # position across the waveguide, positive towards the ring centre
    z = d["pn_section_z"]
    _image(ax, across, z, d["pn_section_index"])
    ax.set_xlim(max(PN_WINDOW[0], across.min()), min(PN_WINDOW[1], across.max()))
    ax.set_ylim(max(PN_WINDOW[2], z.min()), min(PN_WINDOW[3], z.max()))
    fs.image_axes(ax, "position across the waveguide (µm)", "z (µm)")
    ax.set_xticks([-4, -2, 0, 2, 4])
    ax.set_yticks([0, 1, 2, 3])
    fs.note(ax, "outside the ring · p, ground", (0.0, 1.03), ha="left", va="bottom", transform=ax.transAxes)
    fs.note(ax, "inside the ring · n, signal", (1.0, 1.03), ha="right", va="bottom", transform=ax.transAxes)
    fs.note(ax, "Si core", (-0.25, 0.16), (-0.7, 0.55), ha="right")
    fs.note(ax, f"{float(t.T_SLAB90) * 1000:.0f} nm slab", (2.6, 0.045), (3.2, -0.35))
    fs.note(ax, "contact via", (2.35, 0.6), (3.0, 0.75))
    fs.note(ax, "metal 1 (signal disc)", (2.6, 1.8), (2.0, 2.05))
    fs.note(ax, "metal 1 (ground arc)", (-2.6, 1.8), (-4.3, 2.05))
    fs.note(ax, "TiN heater", (0.0, 1.25), (0.0, 1.6), ha="center")
    fs.note(ax, "metal 2 wire", (2.0, 3.0), (2.6, 3.35))
    fs.note(ax, "top oxide", (-1.5, 3.25), (-4.3, 3.3))
    fs.note(ax, "buried oxide", (-1.0, -0.4), (-4.3, -0.4))


def panel_coupler(ax, d: dict) -> None:
    """The coupler on the south side: the ring core and the bus core on one slab, zoomed on the gap."""
    y, z = d["coupler_y"], d["coupler_z"]
    _image(ax, y, z, d["coupler_index"])
    width = float(d["width"])
    ring_y, bus_y = -float(d["radius"]), float(d["y_bus"])
    gap = (ring_y - width / 2) - (bus_y + width / 2)  # µm, between the two core edges
    centre = (ring_y + bus_y) / 2
    ax.set_xlim(centre - ZOOM, centre + ZOOM)
    ax.set_ylim(max(COUPLER_Z[0], z.min()), min(COUPLER_Z[1], z.max()))
    fs.image_axes(ax, "y (µm)", "z (µm)")
    ax.set_xticks([-12, -11, -10, -9])
    ax.set_yticks([-0.5, 0, 0.5, 1])
    z_dim = 0.31
    ax.annotate("", xy=(ring_y - width / 2, z_dim), xytext=(bus_y + width / 2, z_dim),
                arrowprops=dict(arrowstyle="|-|", lw=0.5, color=fs.INK, mutation_scale=4, shrinkA=0, shrinkB=0))  # fmt: skip
    fs.note(ax, f"gap {gap * 1000:.0f} nm", (centre, 0.42), ha="center", va="bottom")
    fs.note(ax, "bus", (bus_y, 0.22), (bus_y - 1.0, 0.62), ha="center")
    fs.note(ax, "ring", (ring_y, 0.22), (ring_y + 0.9, 0.62), ha="center")


def panel_level(ax, d: dict, key: str, title: str) -> None:
    """A horizontal cut of the layout at one level, with a 5 µm scale bar and no tick labels."""
    _image(ax, d[f"{key}_x"], d[f"{key}_yy"], d[f"{key}_index"])
    ax.set_xlim(-HALF, HALF)
    ax.set_ylim(-HALF, HALF)
    fs.image_axes(ax)
    ax.set_xticks([])
    ax.set_yticks([])
    fs.panel_title(ax, title)
    y, x0 = -HALF - 1.6, -HALF + 0.6  # just below the frame, clear of every structure
    ax.plot([x0, x0 + SCALE_BAR], [y, y], color=fs.INK, lw=1.2, solid_capstyle="butt", clip_on=False)
    ax.text(x0 + SCALE_BAR + 0.8, y, f"{SCALE_BAR:.0f} µm", color=fs.INK, fontsize=6, va="center", clip_on=False)


def material_legend(fig, anchor, top) -> None:
    """One frameless legend for the four materials, in the air above the coupler panel and level with the PN section."""
    handles = [Patch(facecolor=fs.MATERIAL_COLORS[m], edgecolor=fs.MUTED, linewidth=0.5) for m in MATERIALS]
    box = anchor.get_position()
    fig.legend(handles, MATERIAL_LABELS, loc="upper left", bbox_to_anchor=(box.x0, top.get_position().y1), ncol=2,
               frameon=False, fontsize=6, handlelength=1.2, handleheight=0.9, columnspacing=1.5,
               borderaxespad=0.0)  # fmt: skip


def main() -> None:
    d = load()
    layout = [["a"] * 5 + ["b"] * 3, ["c"] * 2 + ["d"] * 2 + ["e"] * 2 + ["f"] * 2]
    fig, axes = fs.mosaic(fs.DOUBLE, 112, layout, height_ratios=[1.0, 0.86])
    panel_pn(axes["a"], d)
    panel_coupler(axes["b"], d)
    panel_level(axes["c"], d, "slab", f"z = {float(d['slab_level']) * 1000:.0f} nm · slab")
    panel_level(axes["d"], d, "core", f"z = {float(d['core_level']) * 1000:.0f} nm · core")
    panel_level(axes["e"], d, "metal1", f"z = {float(d['metal1_level']):.2f} µm · metal 1 and heater")
    panel_level(axes["f"], d, "metal2", f"z = {float(d['metal2_level']):.2f} µm · metal 2")
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fig.canvas.draw()
    material_legend(fig, axes["b"], axes["a"])
    fs.save(fig, Path(__file__).with_name("fig0_layer_builder.png"))


if __name__ == "__main__":
    main()

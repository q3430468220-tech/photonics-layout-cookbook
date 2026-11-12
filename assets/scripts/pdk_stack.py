"""The whole process in one cross-section: the PDK at a glance, every layer at its true height.

    a  the full stack, to scale in both directions: substrate, buried oxide, top oxide and air, with the back end
       of the seven building blocks; every back-end layer is named beside its shape
    b  the front end of the same blocks on the same horizontal axis, z stretched x5: the three silicon
       thicknesses, the six implants, germanium and nitride

Layers carry the names and GDS numbers of gsip_technology.LAYER: a label is what you type in code.
The blocks are a schematic arrangement along one line; the sizes inside each block are those of
gsip_technology and rm_builder.  The figure uses no simulation data.

    python assets/scripts/pdk_stack.py   ->  assets/pdk_stack.png
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repository root: figstyle.py, gsip_technology.py, rm_builder.py
sys.path.insert(0, str(ROOT))
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402
import rm_builder as rm  # noqa: E402

C, L = fs.MATERIAL_COLORS, t.LAYER_COLORS
AIR = "#ffffff"
SUBSTRATE = "#d5dbe4"  # the substrate silicon, lighter than the device silicon so that its label reads
W_MM, H_MM = fs.DOUBLE, 106.0
SCALE = 5.15  # mm per micrometre along the horizontal axis, the same in both rows
STRETCH = 5.0  # vertical stretch of row b
X0, X1 = -0.4, 30.6  # horizontal extent (um)
Z_LO, Z_HI = -2.6, 6.1  # row a (um)
Y_B0, Y_B1 = -0.9, 5.0  # row b (stretched units: z = -0.18 .. 1.0 um)
LEFT_MM, TOP_A_MM, GAP_MM = 17.5, 7.0, 7.0

CORE = float(inspect.signature(t.rib).parameters["width"].default)  # rib core, um
SLAB_HALF = t.RIB_SLAB_WIDTH / 2
PN_NEAR, PN_FAR = t.PN_GAP_MEDIUM, t.PN_GAP_HIGH
VIA_CENTRE = rm.M1_GAP + rm.M1_WIDTH / 2  # via 1 on the metal 1 of the p side, from the core centre
TOOTH, PITCH = 0.3, 0.6  # grating teeth (um)
ROW_Y = (2.0, 3.4)  # row b: label rows of the implants (stretched units)
TOP_LABEL_Y = 4.25  # row b: common height of the labels of Ge and SiN (stretched units)
SCALE_BAR = 1.0  # um, scale bar of row a

# building blocks along the horizontal axis (um); each footprint is 1.2 um from the next one
TRENCH = (0.15, 0.85)  # deep trench: a slot through the oxide into the substrate, as at a chip facet
STRIP = (2.0, 2.0 + CORE)
GRATING = (3.5, 6.5)
C_PN = 11.3  # PN modulator: centre line of the rib
C_HEAT = 16.9  # thermal phase shifter: centre line of the strip
UNDERCUT = (16.1, 19.9)
C_GE = 22.6  # Ge on Si: centre of the mesa
C_WGN = 25.8  # SiN waveguide
X_PAD = 27.0  # bond pad: left edge; it runs off the right edge of the figure
PAD_M2 = 2.6  # um of metal 2 wire under the pad
IMPLANTS = (  # layer of the PDK, colour key, x0, x1, label row
    ("PPP", "p++", C_PN - SLAB_HALF, C_PN - PN_FAR, 0),
    ("PP", "p+", C_PN - PN_FAR, C_PN - PN_NEAR, 1),
    ("P", "p", C_PN - PN_NEAR, C_PN, 0),
    ("N", "n", C_PN, C_PN + PN_NEAR, 1),
    ("NP", "n+", C_PN + PN_NEAR, C_PN + PN_FAR, 0),
    ("NPP", "n++", C_PN + PN_FAR, C_PN + SLAB_HALF, 1),
)


def mm_rect(left: float, top: float, width: float, height: float) -> list[float]:
    """Axes rectangle in figure fractions, from millimetres measured from the top left corner."""
    return [left / W_MM, 1 - (top + height) / H_MM, width / W_MM, height / H_MM]


def xmm(x: float) -> float:
    """Millimetre position on the figure of a horizontal position in the axes (um)."""
    return LEFT_MM + (x - X0) * SCALE


def minus(v: float, _pos) -> str:
    return f"{v:g}".replace("-", "−")


def gds(key: str) -> str:
    """GDS layer/datatype of a layer of the PDK, e.g. '40/0'."""
    layer, datatype = tuple(getattr(t.LAYER, key))
    return f"{layer}/{datatype}"


def teeth() -> list[float]:
    """Left edges of the grating teeth."""
    return [GRATING[0] + 0.1 + i * PITCH for i in range(5)]


def rect(
    ax, x0: float, x1: float, z0: float, z1: float, color: str, k: float = 1.0, edge: str = fs.INK, lw: float = 0.3, z: float = 3
) -> None:
    """Rectangle of the cross-section, corners in um; z is stretched by k for display."""
    fs.box(ax, x0, x1, z0 * k, z1 * k, facecolor=color, edgecolor=edge, lw=lw, zorder=z)


def tag(
    ax, text: str, xy: tuple[float, float], color: str = fs.INK, ha: str = "left", leader: tuple[float, float] | None = None
) -> None:
    """A layer name beside its shape; a thin leader only where the name cannot sit next to the shape."""
    if leader is None:
        ax.text(*xy, text, ha=ha, va="center", fontsize=6, color=color, zorder=5)
    else:
        fs.note(ax, text, xy=leader, xytext=xy, ha=ha, color=color, zorder=5)


# =====================================================================================
# row a: the stack to scale, with the back end of every block
# =====================================================================================
def panel_stack(ax) -> None:
    ax.set_xlim(X0, X1)
    ax.set_ylim(Z_LO, Z_HI)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks(range(-2, 7))
    ax.yaxis.set_major_formatter(FuncFormatter(minus))
    ax.set_ylabel("z (µm)")
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    fs.panel_title(ax, "full stack, to scale")
    # substrate, buried oxide and top oxide: one body, with a hairline at z = 0
    rect(ax, X0 - 1, X1 + 1, Z_LO - 1, -t.T_BOX, SUBSTRATE, edge=fs.MUTED, lw=0.5, z=1)
    rect(ax, X0 - 1, X1 + 1, -t.T_BOX, t.Z_TOP, C["oxide"], edge=fs.MUTED, lw=0.5, z=1)
    ax.plot([X0, X1], [0, 0], color=fs.HAIRLINE, lw=0.4, zorder=1.5)
    rect(ax, *TRENCH, Z_LO - 1, Z_HI + 1, AIR, edge="none", z=2)  # air: the deep trench, open to the top
    for x in TRENCH:
        ax.plot([x, x], [Z_LO, t.Z_TOP], color=fs.MUTED, lw=0.5, zorder=2.5)
    rect(ax, *UNDERCUT, Z_LO - 1, -t.T_BOX, AIR, edge=fs.MUTED, lw=0.5, z=2)  # air: undercut below the oxide

    # 1 facet and strip waveguide
    rect(ax, *STRIP, 0, t.T_SI, C["silicon"])
    # 2 grating coupler: a 3 um SLAB150 with five full-height teeth
    rect(ax, *GRATING, 0, t.T_SLAB150, L["SLAB150"])
    for x in teeth():
        rect(ax, x, x + TOOTH, 0, t.T_SI, C["silicon"])
    # 3 PN modulator: slab, rib, contacts, metal 1, via 1 and metal 2 on the p side
    c = C_PN
    rect(ax, c - SLAB_HALF, c + SLAB_HALF, 0, t.T_SLAB90, C["silicon"])
    rect(ax, c - CORE / 2, c + CORE / 2, 0, t.T_SI, C["silicon"])
    for s in (-1, 1):
        rect(ax, *sorted((c + s * rm.VIA_GAP, c + s * (rm.VIA_GAP + rm.VIA_SIZE))), t.T_SLAB90, t.Z_M1, C["aluminium"])
        rect(ax, *sorted((c + s * rm.M1_GAP, c + s * (rm.M1_GAP + rm.M1_WIDTH))), t.Z_M1, t.Z_M1 + t.T_M1, C["aluminium"])
    via_x = c - VIA_CENTRE
    rect(ax, via_x - rm.VIA1_SIZE / 2, via_x + rm.VIA1_SIZE / 2, t.Z_M1 + t.T_M1, t.Z_M2, C["aluminium"])
    rect(ax, c - rm.M1_GAP - rm.M1_WIDTH, via_x + rm.VIA1_SIZE / 2, t.Z_M2, t.Z_M2 + t.T_M2, C["aluminium"])
    # 4 thermal phase shifter: strip, TiN film with a landing, via 1 and metal 2
    c = C_HEAT
    rect(ax, c - CORE / 2, c + CORE / 2, 0, t.T_SI, C["silicon"])
    film_right = c + rm.LANDING_REACH
    rect(ax, c - rm.HEATER_WIDTH / 2, film_right, t.Z_HEATER, t.Z_HEATER + t.T_HEATER, C["tin"])
    via_x = film_right - 0.4 - rm.VIA1_SIZE / 2  # 0.4 um of film beyond the via, as in rm_builder
    rect(ax, via_x - rm.VIA1_SIZE / 2, via_x + rm.VIA1_SIZE / 2, t.Z_HEATER + t.T_HEATER, t.Z_M2, C["aluminium"])
    rect(ax, via_x - rm.VIA1_SIZE / 2, film_right, t.Z_M2, t.Z_M2 + t.T_M2, C["aluminium"])
    # 5 germanium on silicon: a 3 um silicon mesa with a 2 um Ge block
    rect(ax, C_GE - 1.5, C_GE + 1.5, 0, t.T_SI, C["silicon"])
    rect(ax, C_GE - 1.0, C_GE + 1.0, t.T_SI, t.T_SI + t.T_GE, L["GE"])
    # 6 silicon nitride waveguide, on the oxide
    rect(ax, C_WGN - 0.5, C_WGN + 0.5, t.Z_NITRIDE, t.Z_NITRIDE + t.T_NITRIDE, L["WGN"])
    # 7 bond pad: a metal 2 wire, via 2, the metal 3 pad, and the window opened in the oxide above it
    via2_x = X_PAD + t.DESIGN_RULES["via2_enclosure_by_m3"]
    open_x = X_PAD + t.DESIGN_RULES["padopen_enclosure_by_m3"]
    rect(ax, X_PAD, X_PAD + PAD_M2, t.Z_M2, t.Z_M2 + t.T_M2, C["aluminium"])
    rect(ax, via2_x, via2_x + rm.VIA2_SIZE, t.Z_M2 + t.T_M2, t.Z_M3, C["aluminium"])
    rect(ax, X_PAD, X_PAD + rm.TAB, t.Z_M3, t.Z_M3 + t.T_M3, C["aluminium"])
    rect(ax, open_x, X_PAD + rm.TAB, t.Z_M3 + t.T_M3, Z_HI + 1, AIR, edge="none", z=3.5)
    ax.plot([open_x, open_x], [t.Z_M3 + t.T_M3, t.Z_TOP], color=fs.MUTED, lw=0.5, zorder=4)

    # scale bar: 1 um, to scale within the blocks
    ax.plot([25.0, 25.0 + SCALE_BAR], [-2.25, -2.25], color=fs.INK, lw=1.2, solid_capstyle="butt", zorder=5)
    tag(ax, f"{SCALE_BAR:g} µm", (25.0 + SCALE_BAR + 0.2, -2.25))
    # the three bands
    tag(ax, f"top oxide {t.Z_TOP:.1f} µm", (1.4, 5.25), color=fs.SECONDARY)
    tag(ax, f"buried oxide {t.T_BOX:g} µm", (1.4, -1.0), color=fs.SECONDARY)
    tag(ax, "silicon substrate, cut off", (1.4, -2.3), color=fs.SECONDARY)
    # back-end layers, each named once beside its shape
    m1_top = t.Z_M1 + t.T_M1
    tag(ax, f"DEEPTRENCH {gds('DEEPTRENCH')}", (1.4, 4.2), leader=(sum(TRENCH) / 2, 4.2))
    tag(ax, f"VIAC {gds('VIAC')}", (C_PN, 0.6), ha="center")
    tag(ax, f"M1 {gds('M1')}", (C_PN + 2.6, m1_top + 0.35), ha="center")
    tag(ax, f"M2 {gds('M2')}", (C_PN - rm.M1_GAP - rm.M1_WIDTH, t.Z_M2 + t.T_M2 + 0.45))
    tag(
        ax,
        f"VIA1 {gds('VIA1')}",
        (C_PN - VIA_CENTRE - rm.VIA1_SIZE, m1_top + 0.25),
        ha="right",
        leader=(C_PN - VIA_CENTRE - rm.VIA1_SIZE / 2, m1_top + 0.25),
    )
    tag(ax, f"HEATER {gds('HEATER')}", (C_HEAT - rm.HEATER_WIDTH / 2, 0.7))
    tag(ax, f"UNDERCUT {gds('UNDERCUT')}", ((UNDERCUT[0] + UNDERCUT[1]) / 2, -2.3), ha="center")
    tag(ax, f"VIA2 {gds('VIA2')}", (X_PAD - 0.5, 3.1), ha="right", leader=(via2_x, 3.1))
    tag(ax, f"M3 {gds('M3')}", (X_PAD - 0.5, 4.2), ha="right", leader=(X_PAD, 4.2))
    tag(ax, f"PADOPEN {gds('PADOPEN')}", (X_PAD - 0.5, 5.45), ha="right", leader=(open_x, 5.45))


# =====================================================================================
# row b: the front end, z stretched
# =====================================================================================
def tag_block(ax, text: str, xy: tuple[float, float]) -> None:
    """Two-line layer label centred on xy, in the ink."""
    ax.text(*xy, text, ha="center", va="center", fontsize=6, color=fs.INK, linespacing=1.1, zorder=5)


def panel_front(ax) -> None:
    k = STRETCH
    ax.set_facecolor(C["oxide"])
    ax.set_xlim(X0, X1)
    ax.set_ylim(Y_B0, Y_B1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    nm = (0.0, t.T_SLAB90, t.T_SI, t.T_SI + t.T_GE)
    ax.set_yticks([z * k for z in nm])
    ax.set_yticklabels([f"{round(z * 1000)}" for z in nm])
    ax.set_ylabel("z (nm)")
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.axhline(0, color=fs.HAIRLINE, lw=0.4, zorder=1)
    fs.panel_title(ax, f"front end, vertical scale ×{k:g}")
    rect(ax, *TRENCH, Y_B0 - 1, Y_B1 + 1, AIR, edge="none", z=2)  # the deep trench cuts through this level too
    for x in TRENCH:
        ax.plot([x, x], [Y_B0, Y_B1], color=fs.MUTED, lw=0.5, zorder=2.5)

    # 1 strip, 2 grating
    rect(ax, *STRIP, 0, t.T_SI, C["silicon"], k=k)
    rect(ax, *GRATING, 0, t.T_SLAB150, L["SLAB150"], k=k)
    for x in teeth():
        rect(ax, x, x + TOOTH, 0, t.T_SI, C["silicon"], k=k)
    # 3 PN modulator: slab of 90 nm, implants nested about the junction, core on top
    for _key, color, x0, x1, _row in IMPLANTS:
        rect(ax, x0, x1, 0, t.T_SLAB90, C[color], k=k)
        lo, hi = max(x0, C_PN - CORE / 2), min(x1, C_PN + CORE / 2)
        if hi > lo:
            rect(ax, lo, hi, 0, t.T_SI, C[color], k=k)
    for key, _color, x0, x1, row in IMPLANTS:
        xc = (x0 + x1) / 2
        ax.plot([xc, xc], [t.T_SLAB90 * k, ROW_Y[row] - 0.55], color=fs.MUTED, lw=0.4, zorder=4)
        ax.text(
            xc, ROW_Y[row], f"{key}\n{gds(key)}", ha="center", va="center", fontsize=6, color=fs.INK, linespacing=1.1, zorder=5
        )
    fs.note(
        ax,
        f"SLAB90\n{gds('SLAB90')} · {t.T_SLAB90 * 1000:.0f} nm",
        xy=(C_PN + PN_FAR + 1.0, t.T_SLAB90 * k),
        xytext=(C_PN + SLAB_HALF + 0.4, ROW_Y[0]),
        ha="left",
        color=fs.INK,
    )
    # 4 thermal phase shifter: the strip alone in row b (the heater is in row a)
    rect(ax, C_HEAT - CORE / 2, C_HEAT + CORE / 2, 0, t.T_SI, C["silicon"], k=k)
    # 5 germanium on silicon, 6 silicon nitride
    rect(ax, C_GE - 1.5, C_GE + 1.5, 0, t.T_SI, C["silicon"], k=k)
    rect(ax, C_GE - 1.0, C_GE + 1.0, t.T_SI, t.T_SI + t.T_GE, L["GE"], k=k)
    rect(ax, C_WGN - 0.5, C_WGN + 0.5, t.Z_NITRIDE, t.Z_NITRIDE + t.T_NITRIDE, L["WGN"], k=k)

    tag_block(ax, f"WG\n{gds('WG')} · {t.T_SI * 1000:.0f} nm", (STRIP[0] + CORE / 2, 2.0))
    tag_block(ax, f"SLAB150\n{gds('SLAB150')} · {t.T_SLAB150 * 1000:.0f} nm", ((GRATING[0] + GRATING[1]) / 2, 2.0))
    tag_block(ax, f"GE\n{gds('GE')} · {t.T_GE * 1000:.0f} nm", (C_GE, TOP_LABEL_Y))
    tag_block(ax, f"WGN\n{gds('WGN')} · {t.T_NITRIDE * 1000:.0f} nm", (C_WGN, TOP_LABEL_Y))


# =====================================================================================
# figure furniture: captions, note and the material legend, in millimetres
# =====================================================================================
CAPTIONS = (  # centre (um), caption, colour: ink for the blocks of the ring modulator
    (1.3, "deep trench ·\nstrip waveguide", fs.SECONDARY),
    ((GRATING[0] + GRATING[1]) / 2, "grating coupler", fs.SECONDARY),
    (C_PN, "PN modulator", fs.INK),
    (C_HEAT, "thermal\nphase shifter", fs.INK),
    (C_GE, "Ge on Si", fs.SECONDARY),
    (C_WGN, "SiN waveguide", fs.SECONDARY),
    ((X_PAD + X1) / 2, "bond pad", fs.INK),
)


def swatch(ov, x: float, y: float, text: str, color: str, slot: float) -> float:
    """A colour square and its name in the legend row; returns the start of the next slot."""
    ov.add_patch(Rectangle((x, y - 1.6), 3.2, 3.2, facecolor=color, edgecolor=fs.MUTED, lw=0.4))
    ov.text(x + 4.4, y, text, ha="left", va="center", fontsize=6, color=fs.INK)
    return x + slot


def furniture(ov) -> None:
    b_bottom = TOP_A_MM + (Z_HI - Z_LO) * SCALE + GAP_MM + (Y_B1 - Y_B0) * SCALE
    for x, text, color in CAPTIONS:
        ov.text(xmm(x), b_bottom + 1.6, text, ha="center", va="top", fontsize=6, color=color, linespacing=1.2)
    ov.text(
        LEFT_MM, 97.2, "in ink: used by the ring modulator of this tutorial", ha="left", va="top", fontsize=6, color=fs.SECONDARY
    )
    materials = (
        ("silicon", C["silicon"]),
        ("SiO$_2$", C["oxide"]),
        ("Ge", L["GE"]),
        ("SiN", L["WGN"]),
        ("Al", C["aluminium"]),
        ("TiN", C["tin"]),
        ("air", AIR),
    )
    doping = (
        ("n", C["n"]),
        ("n$^{+}$", C["n+"]),
        ("n$^{++}$", C["n++"]),
        ("p", C["p"]),
        ("p$^{+}$", C["p+"]),
        ("p$^{++}$", C["p++"]),
    )
    y, x = 102.5, LEFT_MM
    for text, color in materials:
        x = swatch(ov, x, y, text, color, 13.0)
    x += 6.0
    for text, color in doping:
        x = swatch(ov, x, y, text, color, 10.0)


def main() -> None:
    fig, axes = fs.figure(W_MM, H_MM)
    fig.set_layout_engine("none")  # every axes is placed in millimetres so that both rows share one scale
    width = (X1 - X0) * SCALE
    axes.set_position(mm_rect(LEFT_MM, TOP_A_MM, width, (Z_HI - Z_LO) * SCALE))
    top_b = TOP_A_MM + (Z_HI - Z_LO) * SCALE + GAP_MM
    ax_b = fig.add_axes(mm_rect(LEFT_MM, top_b, width, (Y_B1 - Y_B0) * SCALE))
    panel_stack(axes)
    panel_front(ax_b)
    fs.panel_label(axes, "a")
    fs.panel_label(ax_b, "b")
    ov = fig.add_axes([0, 0, 1, 1])
    ov.set_xlim(0, W_MM)
    ov.set_ylim(H_MM, 0)
    ov.set_axis_off()
    furniture(ov)
    fs.save(fig, ROOT / "assets" / "pdk_stack.png")


if __name__ == "__main__":
    main()

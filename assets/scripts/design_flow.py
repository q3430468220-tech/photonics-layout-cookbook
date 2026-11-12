"""The design flow of the cookbook in one picture.

The arrangement follows the flow chart of the Ansys / Tower Semiconductor workshop "Designing Foundry-Compatible
Photonic Components and Circuits" (slide "Foundry Compatible Design Flow"): four stages in a row and, below them,
the PDK that feeds them. Every picture inside the stages is a result of this repository, drawn from its own layout
and simulation data with the panel functions of the result figures.

    1  device layout          the ring modulator of rm_builder.py
    2  device simulation      FDTD, MODE, CHARGE and HEAT; each structure is built by the Layer Builder
    3  compact model          the numbers the device simulations hand over
    4  circuit simulation     INTERCONNECT: the resonance against junction bias and against heater power

Icons: with the PNG files of assets/third_party/ansys_workshop/ (read the NOTICE there) the figure shows the icons
of the workshop slides; without that folder, or with --own-icons, it draws its own.

    python assets/scripts/design_flow.py                 ->  assets/design_flow.png
    python assets/scripts/design_flow.py --own-icons     ->  build/design_flow_own_icons.png
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repository root
RESULTS = ROOT / "lumerical_simulations" / "ring_modulator"
sys.path[:0] = [str(ROOT), str(RESULTS / "figures"), str(Path(__file__).resolve().parent)]
import fig1_coupling as f1  # noqa: E402
import fig2_passive as f2  # noqa: E402
import fig3_charge as f3  # noqa: E402
import fig4_heat as f4  # noqa: E402
import fig6_circuit as f6  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rm_layout  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

import figstyle as fs  # noqa: E402

W, H = fs.DOUBLE, 99.0  # mm
ICONS = ROOT / "assets" / "third_party" / "ansys_workshop"
OWN_ICONS = "--own-icons" in sys.argv  # draw the three icons here even if the files of the slides are present

# colours of the workshop slide
CREAM, CREAM_EDGE = "#fff1d1", "#ffe2a4"  # the four stages
GOLD, GOLD_EDGE, CALLOUT_EDGE = "#ffb71b", "#6c4b05", "#bc8611"  # arrows, their outline, the outline of the callout
PDK_BLUE = "#0070c0"

# geometry in mm, origin at the bottom left
STAGE_Y0, STAGE_Y1 = 34.0, 97.5
STAGES = ((1.5, 38.0), (40.0, 98.0), (100.0, 139.0), (141.0, 181.5))  # x0, x1 of the four stages
BAR = (50.0, 116.0, 3.0, 12.5)  # the PDK: x0, x1, y0, y1
BADGE = (44.0, 66.5, 37.0, 47.0)  # LAYER BUILDER
CARD = (109.5, 137.0, 38.5, 81.0)  # the compact model
SHAFT, HEAD_W, HEAD_L = 2.7, 5.8, 4.4  # block arrows


# =====================================================================================
# drawing helpers
# =====================================================================================
def mm_axes(fig, x: float, y: float, w: float, h: float, zorder: float = 5):
    """An axes placed in millimetres; by default above the stage backgrounds and below the labels."""
    ax = fig.add_axes([x / W, y / H, w / W, h / H])
    ax.set_zorder(zorder)
    return ax


def overlay(fig, zorder: float):
    """A transparent axes over the whole figure whose data coordinates are millimetres."""
    ax = mm_axes(fig, 0, 0, W, H, zorder)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_axis_off()
    return ax


def centreline(points, radius: float, n: int = 14) -> np.ndarray:
    """A polyline whose corners are replaced by circular arcs."""
    pts = [np.array(p, dtype=float) for p in points]
    out = [pts[0]]
    for a, c, b in zip(pts[:-2], pts[1:-1], pts[2:], strict=True):
        u, v = (a - c) / np.linalg.norm(a - c), (b - c) / np.linalg.norm(b - c)
        centre = c + radius * (u + v)
        a0 = np.arctan2(*(-radius * v)[::-1])  # from the centre to the point where the arc leaves the first leg
        a1 = np.arctan2(*(-radius * u)[::-1])
        sweep = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        out += [centre + radius * np.array([np.cos(a0 + s * sweep), np.sin(a0 + s * sweep)]) for s in np.linspace(0, 1, n)]
    out.append(pts[-1])
    return np.array(out)


def block_arrow(points, radius: float = 5.0) -> np.ndarray:
    """Outline of a block arrow that follows a polyline with rounded corners; the last point is the tip."""
    line = centreline(points, radius)
    tip = line[-1]
    direction = (line[-1] - line[-2]) / np.linalg.norm(line[-1] - line[-2])
    base = tip - HEAD_L * direction
    line = np.vstack([line[:-1], base])  # the shaft ends where the head begins
    tangent = np.gradient(line, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    across = np.array([-direction[1], direction[0]])
    head = [base + across * HEAD_W / 2, tip, base - across * HEAD_W / 2]
    return np.vstack([line + normal * SHAFT / 2, head, (line - normal * SHAFT / 2)[::-1]])


def arrow(ax, points, hollow: bool = False, radius: float = 5.0) -> None:
    ax.add_patch(
        Polygon(
            block_arrow(points, radius),
            closed=True,
            facecolor="white" if hollow else GOLD,
            edgecolor=CALLOUT_EDGE if hollow else GOLD_EDGE,
            linewidth=0.5,
            joinstyle="miter",
        )
    )


def label_box(ax, x0: float, x1: float, y0: float, y1: float) -> None:
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="white", edgecolor=GOLD, linewidth=0.8))


def tag(ax, x: float, y: float, text: str) -> None:
    """The name of a tool on the corner of its picture, as on the slide."""
    ax.text(
        x,
        y,
        text,
        ha="left",
        va="top",
        fontsize=6.5,
        fontweight="bold",
        color=fs.INK,
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.6},
    )


def caption(ax, x: float, y: float, text: str) -> None:
    ax.text(x, y, text, ha="center", va="top", fontsize=5.5, color=fs.SECONDARY)


def underlined(fig, ax, x: float, y: float, lines: list[str], size: float = 9.5) -> None:
    """Bold centred title lines, each underlined, as the stage titles of the slide."""
    renderer = fig.canvas.get_renderer()
    for i, line in enumerate(lines):
        text = ax.text(x, y - i * 4.4, line, ha="center", va="baseline", fontsize=size, fontweight="bold", color=fs.INK)
        box = text.get_window_extent(renderer).transformed(ax.transData.inverted())
        ax.plot([box.x0, box.x1], [y - i * 4.4 - 0.75] * 2, color=fs.INK, lw=0.7, solid_capstyle="butt")


def strip(ax) -> None:
    """Turn a panel of a result figure into a thumbnail: no text, no ticks, no colour bar, a thin frame."""
    for artist in [*ax.texts, *ax.child_axes]:
        artist.remove()
    if ax.get_legend() is not None:
        ax.get_legend().remove()
    for loc in ("left", "center", "right"):
        ax.set_title("", loc=loc)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.minorticks_off()
    ax.set_aspect("auto")
    ax.set_axis_on()
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.4)
        spine.set_color(fs.MUTED)


def window(ax, cx: float, cy: float, width: float) -> None:
    """Limits around a centre that keep the picture undistorted in its box."""
    box = ax.get_position()
    height = width * (box.height * H) / (box.width * W)
    ax.set_xlim(cx - width / 2, cx + width / 2)
    ax.set_ylim(cy - height / 2, cy + height / 2)


# =====================================================================================
# the pictures inside the stages: panels of the result figures, reduced to thumbnails
# =====================================================================================
def thumb_layout(ax) -> None:
    shapes = rm_layout.load()
    for name in ("SLAB90", "WG", "M1", "HEATER", "M2", "M3"):
        rm_layout.draw(ax, shapes, name, lw=0.25)
    rm_layout.draw(ax, shapes, "PADOPEN", mode="line", lw=0.25)
    strip(ax)
    window(ax, 0.0, 0.0, 300.0)


def thumb_fdtd(ax) -> None:
    d = f1.load()
    f1.panel_field(ax.figure, ax, d, colorbar=False)
    for line in [ln for ln in ax.lines if ln.get_color() == fs.ORANGE]:  # the port markers lie outside the window
        line.remove()
    strip(ax)
    window(ax, 0.0, 0.3, 13.0)


def thumb_mode(ax) -> None:
    f2.panel_straight(ax, f2.load())
    strip(ax)
    window(ax, 0.0, 0.14, 2.1)


def thumb_charge(ax) -> None:
    d = f3.load()
    f3.panel_carriers(ax, d, int(np.argmax(d["RB"])))  # the widest depletion region: the highest reverse bias
    strip(ax)
    ax.set_xlim(-0.75, 0.75)
    ax.set_ylim(-0.05, 0.29)  # stretched vertically, as in the charge figure


def thumb_heat(ax) -> None:
    f4.panel_map(ax, f4.load())
    strip(ax)
    window(ax, 0.0, 0.9, 11.0)


def thumb_bias(ax, d: dict) -> None:
    f6.panel_zoom(ax, d)
    strip(ax)
    ax.set_xlim(-45, 95)
    ax.set_ylim(-50, 4)


def thumb_heater(ax, d: dict) -> None:
    f6.panel_heater(ax, d)
    strip(ax)
    ax.set_ylim(-50, 4)


# =====================================================================================
# icons: those of the workshop slides if their files are there, otherwise drawn here
# =====================================================================================
def icon_image(fig, name: str, x: float, y: float, h: float, zorder: float) -> bool:
    """Place assets/third_party/ansys_workshop/<name> with its lower left corner at (x, y) and height h; False if absent."""
    path = ICONS / name
    if OWN_ICONS or not path.exists():
        return False
    image = plt.imread(path)
    ax = mm_axes(fig, x, y, h * image.shape[1] / image.shape[0], h, zorder)
    ax.imshow(image, interpolation="lanczos")
    ax.set_axis_off()
    return True


def draw_stack(ax, x: float, y: float, w: float, h: float) -> None:
    """Three layers of a stack: the motif of the Layer Builder."""
    for colour, y0, y1 in (("#1f5fb4", 0.0, 0.48), ("#2f9e6e", 0.48, 0.62), ("#f5a623", 0.62, 1.0)):
        ax.add_patch(Rectangle((x, y + y0 * h), w, (y1 - y0) * h, facecolor=colour, edgecolor="none"))


def draw_builder_icon(ax, x: float, y: float, h: float) -> None:
    w = h * 0.77
    ax.add_patch(Rectangle((x, y), w, h, facecolor="#f0f0ee", edgecolor="none"))
    draw_stack(ax, x + 0.2 * w, y + 0.42 * h, 0.6 * w, 0.46 * h)
    ax.text(x + w / 2, y + 0.2 * h, "Build", ha="center", va="center", fontsize=5.5, color=fs.INK)


def draw_file_icon(ax, x: float, y: float, h: float) -> None:
    w, fold = h * 0.75, h * 0.2
    outline = [(x, y), (x + w, y), (x + w, y + h - fold), (x + w - fold, y + h), (x, y + h)]
    ax.add_patch(Polygon(outline, closed=True, facecolor="white", edgecolor=fs.INK, linewidth=0.7, joinstyle="miter"))
    ax.plot([x + w - fold, x + w - fold, x + w], [y + h, y + h - fold, y + h - fold], color=fs.INK, lw=0.7)
    draw_stack(ax, x + 0.18 * w, y + 0.1 * h, 0.64 * w, 0.3 * h)
    for cx, cy, r in ((0.36, 0.56, 0.085), (0.52, 0.68, 0.065)):  # two gears
        ax.add_patch(
            Circle((x + cx * w, y + cy * h), r * h, facecolor="white", edgecolor=fs.INK, linewidth=1.1, linestyle=(0, (0.9, 0.7)))
        )


def draw_factory_icon(ax, x: float, y: float, h: float) -> None:
    w = h * 1.6
    roof = [(0, 0), (1, 0), (1, 0.62), (0.76, 0.42), (0.76, 0.62), (0.52, 0.42), (0.52, 0.62), (0.28, 0.42), (0.28, 1), (0.1, 1),
            (0.1, 0.42), (0, 0.42)]  # fmt: skip
    ax.add_patch(Polygon([(x + px * w, y + py * h) for px, py in roof], closed=True, facecolor=fs.INK, edgecolor="none"))
    for px in (0.2, 0.46, 0.72):
        ax.add_patch(Rectangle((x + px * w, y + 0.12 * h), 0.12 * w, 0.14 * h, facecolor=PDK_BLUE, edgecolor="none"))


# =====================================================================================
# the figure
# =====================================================================================
def stages(base) -> None:
    for x0, x1 in STAGES:
        base.add_patch(
            Rectangle((x0, STAGE_Y0), x1 - x0, STAGE_Y1 - STAGE_Y0, facecolor=CREAM, edgecolor=CREAM_EDGE, linewidth=1.2)
        )


def pdk(fig, base, top) -> None:
    """The PDK bar and what it hands to the stages."""
    x0, x1, y0, y1 = BAR
    ym = (y0 + y1) / 2
    # layout: cells and layers
    arrow(base, [(x0 + 1, ym), (20.0, ym), (20.0, STAGE_Y0 + 0.2)])
    label_box(top, 25.0, 53.0, 14.0, 25.5)
    top.text(39.0, 22.6, "Pcells and GDS files", ha="center", va="center", fontsize=6.6, fontweight="bold")
    top.text(
        39.0,
        17.9,
        "gsip_technology.py\nrm_builder.py",
        ha="center",
        va="center",
        fontsize=5.2,
        color=fs.SECONDARY,
        linespacing=1.2,
    )
    # simulation: the process file
    arrow(base, [(58.0, y1 - 1), (58.0, BADGE[2] + 0.2)])
    label_box(top, 62.5, 97.5, 15.0, 31.5)
    top.text(
        64.3,
        25.0,
        "Foundry\nprocess file\nwith layer\ndefinition",
        ha="left",
        va="center",
        fontsize=6.6,
        fontweight="bold",
        linespacing=1.2,
    )
    top.text(64.3, 17.0, "gsip_csv/*.csv  →  gsip_process.lbr", ha="left", va="center", fontsize=5.2, color=fs.SECONDARY)
    if not icon_image(fig, "process_file_icon.png", 86.5, 20.0, 9.6, 12):
        draw_file_icon(top, 87.0, 20.0, 9.6)
    # circuit: the compact model library a foundry ships; the teaching PDK has none
    arrow(base, [(x1 - 1, ym), (162.0, ym), (162.0, STAGE_Y0 + 0.2)], hollow=True)
    label_box(top, 121.5, 157.0, 15.0, 27.0)
    top.text(
        139.25, 22.8, "Compact model\nlibrary (CML)", ha="center", va="center", fontsize=6.6, fontweight="bold", linespacing=1.2
    )
    top.text(
        139.25,
        17.5,
        "shipped by a real foundry PDK;\nhere stage 3 builds the model",
        ha="center",
        va="center",
        fontsize=5.2,
        color=fs.SECONDARY,
        linespacing=1.15,
    )
    # the bar itself
    top.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=PDK_BLUE, edgecolor=CALLOUT_EDGE, linewidth=0.5))
    if not icon_image(fig, "factory_icon.png", x0 + 3.2, y0 + 2.1, 5.3, 12):
        draw_factory_icon(top, x0 + 3.2, y0 + 2.1, 5.3)
    top.text((x0 + x1) / 2 + 4, ym + 2.0, "GSiP teaching PDK", ha="center", va="center", fontsize=9.5, color="white")
    top.text(
        (x0 + x1) / 2 + 4, ym - 2.3, "public layer map and process data", ha="center", va="center", fontsize=6.5, color="white"
    )
    top.text(
        W - 1.5,
        1.6,
        "arrangement after the design flow of the Ansys and Tower Semiconductor workshop (2025)",
        ha="right",
        va="center",
        fontsize=4.8,
        color=fs.MUTED,
    )


def stage_layout(fig, base, top) -> None:
    x0, x1 = STAGES[0]
    thumb_layout(mm_axes(fig, x0 + 3.0, 53.0, x1 - x0 - 6.0, 31.5))
    tag(top, x0 + 3.0, 84.5, "gdsfactory + KLayout")
    caption(top, (x0 + x1) / 2, 51.8, "rm_builder.py  →  rm_ring.gds")
    arrow(base, [(26.0, 48.0), (26.0, 42.0), (BADGE[0] + 0.2, 42.0)], radius=3.2)
    top.text(22.5, 44.5, "GDS\nfile", ha="right", va="center", fontsize=6.6, fontweight="bold", linespacing=1.2)


def stage_devices(fig, base, top) -> None:
    x0, _ = STAGES[1]
    cells = (
        ("FDTD", "coupler field", thumb_fdtd, 0, 1),
        ("MODE", "waveguide mode", thumb_mode, 1, 1),
        ("CHARGE", "carriers at 4 V", thumb_charge, 0, 0),
        ("HEAT", "temperature", thumb_heat, 1, 0),
    )
    w, h = 19.6, 13.4
    for name, text, draw, col, row in cells:
        x, y = x0 + 2.2 + col * (w + 1.6), 53.5 + row * (h + 4.4)
        draw(mm_axes(fig, x, y, w, h))
        tag(top, x, y + h, name)
        caption(top, x + w / 2, y - 0.7, text)
    # LAYER BUILDER: the GDS and the process file meet here
    bx0, bx1, by0, by1 = BADGE
    top.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, facecolor=GOLD, edgecolor="none"))
    top.text(bx0 + 1.6, (by0 + by1) / 2, "LAYER\nBUILDER", ha="left", va="center", fontsize=7.6, color="white", linespacing=1.25)
    if not icon_image(fig, "layer_builder_icon.png", bx1 - 7.6, by0 + 0.9, by1 - by0 - 1.8, 12):
        draw_builder_icon(top, bx1 - 7.6, by0 + 0.9, by1 - by0 - 1.8)
    x_up = x0 + 2.2 + w + 0.8  # between the two columns of pictures
    arrow(top, [(x_up, by1 - 0.2), (x_up, 52.6)])
    top.text(
        bx1 + 2.0,
        (by0 + by1) / 2,
        "builds every structure from the\nGDS and the process file:\nno stack is typed into a script",
        ha="left",
        va="center",
        fontsize=5.5,
        color=fs.SECONDARY,
        linespacing=1.2,
    )
    # what the simulations hand over
    px0, px1, py0, py1 = x0 + 44.8, STAGES[2][0] + 7.2, 55.5, 84.0
    notch = 7.0
    outline = [(px0, py0), (px1 - notch, py0), (px1, (py0 + py1) / 2), (px1 - notch, py1), (px0, py1)]
    top.add_patch(Polygon(outline, closed=True, facecolor=GOLD, edgecolor=CALLOUT_EDGE, linewidth=0.5, joinstyle="miter"))
    top.text(px0 + 1.5, py1 - 3.6, "Simulation data", ha="left", va="center", fontsize=7.4, fontweight="bold")
    items = ("κ² (gap)", "n$_{eff}$, n$_g$, loss", "Δn$_{eff}$ (V), C, R$_s$", "K/mW, τ")
    for i, item in enumerate(items):
        top.text(px0 + 1.7, py1 - 8.6 - i * 4.4, f"•  {item}", ha="left", va="center", fontsize=6.4)


def stage_model(top, d: dict) -> None:
    """The compact model: a symbol and the numbers the device simulations handed over."""
    active = np.load(RESULTS / "5_active_mode_properties" / "active.npz")
    k_max = int(np.argmin(active["V"]))  # the highest reverse bias
    x0, x1, y0, y1 = CARD
    top.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="white", edgecolor=GOLD, linewidth=0.8))
    xm, y_bus = (x0 + x1) / 2, y1 - 11.3
    top.plot([x0 + 4.2, x1 - 4.2], [y_bus, y_bus], color=fs.INK, lw=0.9, solid_capstyle="butt")
    top.add_patch(Circle((xm, y_bus + 4.1), 3.5, facecolor="none", edgecolor=fs.INK, linewidth=0.9))
    for x, text, ha in ((x0 + 4.2, "in", "right"), (x1 - 4.2, "out", "left")):
        top.text(x + (-0.7 if ha == "right" else 0.7), y_bus, text, ha=ha, va="center", fontsize=5.5, color=fs.SECONDARY)
    top.text(xm, y_bus - 3.4, "ring modulator model", ha="center", va="center", fontsize=6.4, fontweight="bold")
    k2 = float(d["k2_A"]) * np.exp(-float(d["gap_design"]) / float(d["k2_g0"]))
    rows = (
        ("κ²", f"{k2:.4f}"),
        ("n$_{eff}$", f"{float(d['neff']):.4f}"),
        ("n$_g$", f"{float(d['ng']):.3f}"),
        ("loss per turn", f"{float(d['total_turn_dB']):.3f} dB"),
        (f"Δn$_{{eff}}$ at {-float(active['V'][k_max]):g} V", f"{float(active['dneff'][k_max]) * 1e4:.2f} × 10$^{{-4}}$"),
        ("heater", f"{float(d['thermal_pm_per_mW']):.0f} pm/mW"),
    )
    for i, (name, value) in enumerate(rows):
        y = y_bus - 7.6 - i * 3.75
        top.text(x0 + 1.6, y, name, ha="left", va="center", fontsize=5.8, color=fs.SECONDARY)
        top.text(x1 - 1.6, y, value, ha="right", va="center", fontsize=5.8, color=fs.INK)


def stage_circuit(fig, base, top, d: dict) -> None:
    x0, x1 = STAGES[3]
    w = x1 - x0 - 6.4
    thumb_bias(mm_axes(fig, x0 + 3.2, 63.5, w, 20.5), d)
    tag(top, x0 + 3.2, 84.0, "INTERCONNECT")
    caption(top, (x0 + x1) / 2, 62.8, "resonance against junction bias, 0 to 4 V")
    thumb_heater(mm_axes(fig, x0 + 3.2, 40.5, w, 18.0), d)
    caption(top, (x0 + x1) / 2, 39.8, "resonance against heater power, 0 to 20 mW")
    arrow(top, [(CARD[1] - 0.2, 73.75), (x0 + 2.9, 73.75)])


def main() -> None:
    fig = plt.figure(figsize=(W * fs.MM, H * fs.MM))
    base, top = overlay(fig, 1), overlay(fig, 10)
    circuit = f6.load()
    stages(base)
    stage_layout(fig, base, top)
    stage_devices(fig, base, top)
    stage_model(top, circuit)
    stage_circuit(fig, base, top, circuit)
    pdk(fig, base, top)
    fig.canvas.draw()
    titles = (["1. Device layout"], ["2. Device simulation"], ["3. Compact Model", "Generation"], ["4. Circuit Simulation"])
    for (x0, x1), lines in zip(STAGES, titles, strict=True):
        underlined(fig, top, (x0 + x1) / 2, STAGE_Y1 - 5.6, lines)
    fs.save(fig, ROOT / "build" / "design_flow_own_icons.png" if OWN_ICONS else ROOT / "assets" / "design_flow.png")


if __name__ == "__main__":
    main()

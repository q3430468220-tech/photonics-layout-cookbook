"""The data flow of chapter 4: which step reads which result of an earlier step.

The steps stand in one column, in the order they run.  A result that a later step reads leaves its step sideways
and joins one of two lines.  The line on the left ends in step 5, the line on the right ends in step 6.  Nothing
else is passed between steps, so no line crosses another.

Steps 0 to 5 build their structure in the same way, from a GDS file and the process file through the Layer
Builder (the shaded group).  Step 6 is a circuit and has no geometry.

The connections are the table FLOW below and nothing else.  tests/test_data_flow.py compares that table with the
step folders that the scripts in ../scripts read: the figure cannot show a connection that the scripts do not
have, and cannot miss one.

Reads no data.

    python fig_data_flow.py            ->  figures/fig_data_flow.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.patches import Circle, FancyBboxPatch, Polygon

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
sys.path.insert(0, str(ROOT.parents[1]))
import figstyle as fs  # noqa: E402

# step, its name in the chapter, its solver, what it works on (step 6: what comes out of the chain)
STEPS = (
    (0, "The Layer Builder check", "MODE, as an index probe", "index maps of the finished device; nothing is passed on"),
    (1, "The coupling coefficient", "FDTD", "the bus beside the ring arm, at four gaps"),
    (2, "The passive waveguide", "MODE", "the undoped rib, straight and bent"),
    (3, "The PN junction", "CHARGE", "the doped rib under reverse bias"),
    (4, "The heater", "HEAT", "the rib with the heater, the vias and metal 1"),
    (5, "The active waveguide", "MODE", "the bent rib with the carriers, then with the heat"),
    (6, "The ring as a circuit element", "INTERCONNECT", "spectra, extinction, Q, bandwidth, heater tuning"),
)

# from step, to step, what is read.  This table is the figure; a test checks it against the scripts.
FLOW = (
    (1, 6, "κ²(gap)"),
    (2, 5, "bend orientation, n$_g$"),
    (2, 6, "n$_{eff}$, n$_g$, bend loss"),
    (3, 5, "carrier map"),
    (3, 6, "C, R$_s$, f$_{RC}$"),
    (4, 5, "temperature map"),
    (5, 6, "Δn$_{eff}$(V), loss(V), Δn$_{eff}$ per mW"),
)
READERS = (5, 6)  # the two steps that read earlier results: one line each
BUILT = range(6)  # the steps whose structure the Layer Builder makes

W, H = fs.DOUBLE, 104.0  # mm
X0, X1 = 46.0, 124.0  # the column of the steps
RAIL = {5: 13.0, 6: 171.0}  # x of the two lines
COLOUR = {5: fs.BLUE, 6: fs.ORANGE}
CARD_H, GAP = 10.6, 2.6
TOP = H - 2.5  # top of the shaded group
CORNER = 2.2  # radius of the corners of a line


def mix(colour, other, amount: float) -> tuple:
    a, b = np.array(to_rgb(colour)), np.array(to_rgb(other))
    return tuple(a + (b - a) * amount)


def centre(step: int) -> float:
    """Height of the middle of a step; step 6 stands below the group, a little apart."""
    y = TOP - 6.4 - step * (CARD_H + GAP) - CARD_H / 2
    return y - 2.8 if step == 6 else y


def rounded(points, radius: float = CORNER, n: int = 12) -> np.ndarray:
    """A line through the points with its right-angle corners rounded to quarter circles."""
    points = [np.array(p, float) for p in points]
    out = [points[0]]
    for before, corner, after in zip(points, points[1:], points[2:], strict=False):
        d_in = (corner - before) / np.linalg.norm(corner - before)
        d_out = (after - corner) / np.linalg.norm(after - corner)
        middle = corner - d_in * radius + d_out * radius
        for t in np.linspace(0, np.pi / 2, n):
            out.append(middle - d_out * radius * np.cos(t) + d_in * radius * np.sin(t))
    out.append(points[-1])
    return np.array(out)


def line(ax, points, colour) -> None:
    xy = rounded(points) if len(points) > 2 else np.array(points, float)
    ax.plot(xy[:, 0], xy[:, 1], color=colour, lw=1.0, solid_capstyle="butt", solid_joinstyle="round", zorder=2)


def arrowhead(ax, x: float, y: float, direction: int, colour) -> None:
    """A filled tip at (x, y), pointing right (+1) or left (-1)."""
    tail = x - direction * 2.4
    ax.add_patch(Polygon([(x, y), (tail, y + 1.0), (tail, y - 1.0)], closed=True, facecolor=colour, edgecolor="none", zorder=3))


def card(ax, step: int, name: str, solver: str, about: str) -> None:
    y = centre(step)
    ax.add_patch(
        FancyBboxPatch(
            (X0, y - CARD_H / 2), X1 - X0, CARD_H, boxstyle="round,pad=0,rounding_size=1.4", mutation_aspect=1,
            facecolor=mix(fs.SURFACE, fs.INK, 0.055), edgecolor=fs.HAIRLINE, linewidth=0.5, zorder=3,
        )
    )  # fmt: skip
    ax.add_patch(Circle((X0 + 5.6, y), 3.0, facecolor=fs.SURFACE, edgecolor=fs.MUTED, linewidth=0.5, zorder=4))
    ax.text(X0 + 5.6, y, str(step), ha="center", va="center_baseline", fontsize=7.5, fontweight="bold", zorder=5)
    ax.text(X0 + 11.2, y + 2.05, name, ha="left", va="center", fontsize=7, fontweight="bold", zorder=5)
    ax.text(X1 - 3.0, y + 2.05, solver, ha="right", va="center", fontsize=6, color=fs.SECONDARY, zorder=5)
    ax.text(X0 + 11.2, y - 2.3, about, ha="left", va="center", fontsize=6, color=fs.SECONDARY, zorder=5)


def rail(ax, reader: int) -> None:
    """The line of one reading step: every result it reads joins the line, and the line ends in the step."""
    x, colour = RAIL[reader], COLOUR[reader]
    side = -1 if x < X0 else 1  # the line runs left or right of the steps
    edge = X0 if side < 0 else X1
    sources = [(source, label) for source, target, label in FLOW if target == reader]
    first = sources[0][0]
    # from the first source sideways to the line, down the line, and into the reader with an arrowhead
    tip = edge + side * 0.4
    line(ax, [(edge, centre(first)), (x, centre(first)), (x, centre(reader)), (tip + side * 2.0, centre(reader))], colour)
    arrowhead(ax, tip, centre(reader), -side, colour)
    for source, label in sources:
        y = centre(source)
        if source != first:  # a later source joins the line; a dot marks the junction
            line(ax, [(edge, y), (x, y)], colour)
            ax.add_patch(Circle((x, y), 0.8, facecolor=colour, edgecolor="none", zorder=3))
        ax.text(edge + side * 3.0, y + 0.9, label, ha="right" if side < 0 else "left", va="bottom", fontsize=6.5, zorder=5)
    ax.text(
        edge + side * 4.2, centre(reader) + 0.9, f"read by step {reader}", ha="right" if side < 0 else "left", va="bottom",
        fontsize=6.5, fontweight="bold", zorder=5,
    )  # fmt: skip


def main() -> None:
    fig = plt.figure(figsize=(W * fs.MM, H * fs.MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_axis_off()
    # the group of the steps whose structure the Layer Builder makes
    bottom = centre(max(BUILT)) - CARD_H / 2 - 2.2
    ax.add_patch(
        FancyBboxPatch(
            (X0 - 2.6, bottom), X1 - X0 + 5.2, TOP - bottom, boxstyle="round,pad=0,rounding_size=2.2", mutation_aspect=1,
            facecolor=mix(fs.SURFACE, fs.INK, 0.028), edgecolor="none", zorder=0,
        )
    )  # fmt: skip
    ax.text(
        X0, TOP - 3.3, "Layer Builder: each structure from a GDS file and gsip_process.lbr", ha="left", va="center",
        fontsize=6, color=fs.SECONDARY, zorder=5,
    )  # fmt: skip
    for reader in READERS:
        rail(ax, reader)
    for step in STEPS:
        card(ax, *step)
    fs.save(fig, Path(__file__).with_name("fig_data_flow.png"))


if __name__ == "__main__":
    main()

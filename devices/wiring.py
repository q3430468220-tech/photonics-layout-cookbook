"""Metal 2 wires and pads with a row of via 2, shared by the device builders.

    square()           a square, centred and optionally rotated (a via 1, a via 2)
    box()              a rectangle given by its size along and across a direction
    polar()            a point at a radius and an angle
    unit()             the unit step of a horizontal or vertical segment
    reach_beyond()     how far a wire must run back past its start to enclose the via 1 under it
    wire()             a metal 2 wire through points, with square corners
    pad_with_tab()     a pad of metal 3 with its passivation opened, and a metal 2 tab with a row of via 2

The dimensions are the ones of the ring modulator, which was the first device to use them. Its layout
does not change when it uses this module: tests/test_connectivity.py checks the nets, and
devices/gds/ring_modulator.gds is the layout that the simulations load.
"""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology
import gdsfactory as gf

import gsip_technology as t

VIA1_SIZE = 1.00  # rule: >= 0.5
VIA2_SIZE = 2.00  # rule: >= 1.0
VIA2_PITCH = 6.00
TRACE = 6.00  # metal 2 wire width
TAB = 8.00  # metal 3 tab at a pad: metal 2 ends below it, joined by a row of via 2
ENCLOSURE_MARGIN = 0.10  # metal 2 beyond the via 1 enclosure rule, so that no wire end lies exactly on the limit


def polar(radius: float, angle: float) -> np.ndarray:
    return radius * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])


def box(centre, radial: float, tangential: float, angle: float = 0.0) -> list[tuple[float, float]]:
    """Rectangle centred on ``centre``: ``radial`` long along the direction ``angle``, ``tangential`` wide across it."""
    u = polar(1.0, angle)
    v = np.array([-u[1], u[0]])
    c = np.asarray(centre, dtype=float)
    return [tuple(c + sx * u * radial / 2 + sy * v * tangential / 2) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def square(centre, size: float, angle: float = 0.0) -> list[tuple[float, float]]:
    """Square of edge ``size`` centred on ``centre``, rotated by ``angle`` degrees."""
    return box(centre, size, size, angle)


def pad_with_tab(c: gf.Component, xy: tuple[float, float], size: float) -> tuple[float, float]:
    """Pad (metal 3 + opening) with a tab on the side that faces y = 0, where metal 2 comes up through a row of via 2.

    Returns the point in the middle of the tab, where the metal 2 wire ends.  The row of via 2 is centred on the
    tab and runs over the pad width, with the spacing of VIA2_PITCH.
    """
    px, py = xy
    (c << t.pad(size=size)).dmove(xy)
    side = -1.0 if py > 0 else 1.0  # the tab points towards y = 0
    y_edge = py + side * size / 2
    y_tab = y_edge + side * TAB
    tab = [(px - size / 2, y_edge), (px + size / 2, y_edge), (px + size / 2, y_tab), (px - size / 2, y_tab)]
    c.add_polygon(tab, layer=t.M3)
    c.add_polygon(tab, layer=t.M2)
    count = int((size - 2 * VIA2_SIZE) // VIA2_PITCH) + 1
    x0 = px - (count - 1) * VIA2_PITCH / 2
    for k in range(count):
        c.add_polygon(square((x0 + k * VIA2_PITCH, (y_edge + y_tab) / 2), VIA2_SIZE), layer=t.VIA2)
    return px, (y_edge + y_tab) / 2


def unit(p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
    """Unit step (sign of each component) from p to q, for a horizontal or vertical segment."""
    return float(np.sign(q[0] - p[0])), float(np.sign(q[1] - p[1]))


def reach_beyond(start: tuple[float, float], travel: tuple[float, float], squares: list) -> float:
    """How far metal 2 must run beyond start, backwards from travel, to enclose every via 1 square.

    squares: the corner points of each via 1 (rotated squares included).  The farthest corner behind the
    start sets the reach: the metal must extend past it by via1_enclosure_by_m2 plus ENCLOSURE_MARGIN.
    Corners ahead of the start lie on the wire itself.
    """
    behind = [-((x - start[0]) * travel[0] + (y - start[1]) * travel[1]) for square_ in squares for x, y in square_]
    return max([0.0, *behind]) + t.DESIGN_RULES["via1_enclosure_by_m2"] + ENCLOSURE_MARGIN


def wire(
    c: gf.Component, points: list[tuple[float, float]], start_reach: float, end_reach: float = 0.0, width: float = TRACE
) -> None:
    """Metal 2 wire through points: one path of constant width with square corners.

    Each segment is a rectangle.  At a corner both segments run width / 2 past the corner, which makes the
    outer corner square and leaves no notch.  The two free ends do not run past the width: start_reach and
    end_reach say how far the metal goes beyond the first and the last point (see reach_beyond).
    """
    h = width / 2
    last = len(points) - 2
    for i, ((x0, y0), (x1, y1)) in enumerate(itertools.pairwise(points)):
        if abs(x1 - x0) > 1e-9 and abs(y1 - y0) > 1e-9:
            raise ValueError("a wire segment must be horizontal or vertical")
        if abs(x1 - x0) < 1e-9 and abs(y1 - y0) < 1e-9:
            raise ValueError("a wire segment must have a length")
        ux, uy = unit((x0, y0), (x1, y1))
        before = start_reach if i == 0 else h
        after = end_reach if i == last else h
        ax, ay = x0 - ux * before, y0 - uy * before  # the segment, extended backwards at its start
        bx, by = x1 + ux * after, y1 + uy * after  # and forwards at its end
        if uy == 0:  # horizontal
            left, bottom, right, top = min(ax, bx), y0 - h, max(ax, bx), y0 + h
        else:  # vertical
            left, bottom, right, top = x0 - h, min(ay, by), x0 + h, max(ay, by)
        c.add_polygon([(left, bottom), (right, bottom), (right, top), (left, top)], layer=t.M2)

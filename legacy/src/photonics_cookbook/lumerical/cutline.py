"""Extract a 2D device cross-section from layout polygons along a cut line.

This is what makes the GDS -> CHARGE / FDE link *seamless*: instead of re-typing
widths and doping offsets into a Lumerical script, the bridge intersects the cut
line with every drawn layer and gets the lateral intervals; the process file adds
the vertical extent, materials and doses. What you simulate is exactly what you
drew -- including mistakes, which is the point.

Frame of the result: ``x`` runs along the cut (from ``p0`` towards ``p1``) and is 0
at ``origin`` (projected onto the line), e.g. the waveguide centre. ``z`` comes from
the process. In Lumerical this maps to a "2D Y-normal" CHARGE / FDE simulation
(x lateral, z vertical, y = propagation).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from photonics_cookbook.process import Process

GRID = 1e-3  # um, snap interval ends to the database unit
SEAM_SHIFT_UM = 1.37e-4  # sub-nm, deliberately off-grid (see cross_section)


@dataclass(frozen=True)
class Interval:
    role: str
    x0: float
    x1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    def overlaps(self, other: Interval, tol: float = 1e-9) -> bool:
        return min(self.x1, other.x1) - max(self.x0, other.x0) > tol


@dataclass
class CrossSection2D:
    cell: str
    p0: tuple[float, float]
    p1: tuple[float, float]
    origin: tuple[float, float]
    x_min: float
    x_max: float
    intervals: list[Interval] = field(default_factory=list)
    source: str = ""

    def by_role(self, role: str) -> list[Interval]:
        return [iv for iv in self.intervals if iv.role == role]

    def roles(self) -> list[str]:
        return sorted({iv.role for iv in self.intervals})

    def silicon_top_at(self, iv: Interval, process: Process) -> float | None:
        """Highest ``structure`` top overlapping ``iv`` (where a via lands)."""
        tops = []
        for other in self.intervals:
            lay = process.layer(other.role)
            if lay.kind == "structure" and other.overlaps(iv):
                tops.append(lay.zmax)
        return max(tops) if tops else None

    def solid_boxes(self, process: Process) -> list[tuple[Interval, tuple[float, float]]]:
        """(interval, (zmin, zmax)) for structure / via / metal intervals."""
        out = []
        for iv in self.intervals:
            lay = process.layer(iv.role)
            if lay.kind == "structure":
                out.append((iv, (lay.zmin, lay.zmax)))
            elif lay.kind == "via":
                z0 = self.silicon_top_at(iv, process)
                out.append((iv, (lay.zmin if z0 is None else z0, lay.zmax)))
            elif lay.kind == "metal":
                out.append((iv, (lay.zmin, lay.zmax)))
        return out

    def describe(self, process: Process) -> str:
        lines = [f"cross-section of '{self.cell}'  x = {self.x_min:.3f} .. {self.x_max:.3f} um"]
        for iv in sorted(self.intervals, key=lambda i: (process.layer(i.role).kind, i.x0)):
            lay = process.layer(iv.role)
            extra = f"{lay.dopant} {lay.concentration:.1e} cm^-3" if lay.kind == "doping" else lay.kind
            lines.append(f"  {iv.role:<10} {iv.x0:9.3f} .. {iv.x1:9.3f} um  (w = {iv.width:6.3f})  {extra}")
        return "\n".join(lines)

    def to_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path


# ----------------------------------------------------------------- geometry core
def line_polygon_intervals(
    contours: list[np.ndarray], p0: np.ndarray, p1: np.ndarray
) -> list[tuple[float, float]]:
    """Parameter intervals ``[t0, t1]`` (0..1 along p0->p1) inside a polygon with holes.

    Uses the even-odd rule over all contours, with a half-open vertex rule
    (a vertex exactly on the line counts as "below"), so touching vertices and
    collinear edges are handled consistently.
    """
    d = p1 - p0
    ts: list[float] = []
    for c in contours:
        a = c
        b = np.roll(c, -1, axis=0)
        sa = d[0] * (a[:, 1] - p0[1]) - d[1] * (a[:, 0] - p0[0])
        sb = d[0] * (b[:, 1] - p0[1]) - d[1] * (b[:, 0] - p0[0])
        cross = (sa > 0) != (sb > 0)
        if not np.any(cross):
            continue
        ea = a[cross]
        eb = b[cross]
        e = eb - ea
        den = d[0] * e[:, 1] - d[1] * e[:, 0]
        num = (ea[:, 0] - p0[0]) * e[:, 1] - (ea[:, 1] - p0[1]) * e[:, 0]
        ok = np.abs(den) > 1e-15
        ts.extend((num[ok] / den[ok]).tolist())
    ts.sort()
    out = []
    for t0, t1 in zip(ts[0::2], ts[1::2], strict=False):
        lo, hi = max(t0, 0.0), min(t1, 1.0)
        if hi > lo:
            out.append((lo, hi))
    return out


def _merge(intervals: list[tuple[float, float]], tol: float = 1e-6) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1] + tol:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(a, b) for a, b in merged]


def _snap(v: float) -> float:
    return round(round(v / GRID) * GRID, 6)


def cross_section(
    polygons: dict[tuple[int, int], list[list[np.ndarray]]],
    process: Process,
    p0: tuple[float, float],
    p1: tuple[float, float],
    origin: tuple[float, float] | None = None,
    cell: str = "",
    source: str = "",
) -> CrossSection2D:
    """Intersect role-mapped layer polygons with the segment ``p0 -> p1``.

    ``polygons`` maps ``(layer, datatype)`` to polygons given as contour lists
    (see :func:`photonics_cookbook.lumerical.gds_reader.read_gds_polygons`). Layers that
    the process does not know, and annotation layers, are ignored.
    """
    a = np.asarray(p0, dtype=float)
    b = np.asarray(p1, dtype=float)
    length = float(np.hypot(*(b - a)))
    if length <= 0:
        raise ValueError("cut line has zero length")
    u = (b - a) / length
    o = a if origin is None else np.asarray(origin, dtype=float)
    s_origin = float(np.dot(o - a, u))
    # Intersect with a copy of the line shifted by a sub-nm, off-grid distance. This removes
    # the degenerate cases (cut running exactly along a polygon edge or a seam between two
    # abutting polygons) without changing the result at the 1 nm database resolution.
    shift = SEAM_SHIFT_UM * np.array([-u[1], u[0]])
    a_s, b_s = a + shift, b + shift

    intervals: list[Interval] = []
    for gds, polys in polygons.items():
        role = process.role_of(gds)
        if role is None or process.layer(role).kind == "annotation":
            continue
        ts: list[tuple[float, float]] = []
        for contours in polys:
            ts.extend(line_polygon_intervals(contours, a_s, b_s))
        for lo, hi in _merge(ts):
            x0 = _snap(lo * length - s_origin)
            x1 = _snap(hi * length - s_origin)
            if x1 - x0 > GRID / 2:
                intervals.append(Interval(role, x0, x1))
    intervals.sort(key=lambda iv: (iv.role, iv.x0))
    return CrossSection2D(
        cell=cell,
        p0=(float(a[0]), float(a[1])),
        p1=(float(b[0]), float(b[1])),
        origin=(float(o[0]), float(o[1])),
        x_min=_snap(-s_origin),
        x_max=_snap(length - s_origin),
        intervals=intervals,
        source=source,
    )


def cross_section_from_gds(
    gds_path: str | Path,
    process: Process,
    p0: tuple[float, float],
    p1: tuple[float, float],
    origin: tuple[float, float] | None = None,
    cell: str | None = None,
) -> CrossSection2D:
    """Read ``gds_path`` (KLayout) and extract the cross-section along ``p0 -> p1``."""
    from photonics_cookbook.lumerical.gds_reader import read_gds_polygons

    gds_layers = [lay.gds for lay in process.layers.values()]
    name, polys, _ = read_gds_polygons(gds_path, cell=cell, layers=gds_layers)
    return cross_section(polys, process, p0, p1, origin=origin, cell=name, source=str(gds_path))


def geometry_polygons(geom, process: Process) -> dict[tuple[int, int], list[list[np.ndarray]]]:
    """Adapter: :class:`photonics_cookbook.geometry.Geometry` -> GDS-keyed polygons (no holes).

    Overlapping polygons on one layer are fine: intervals are merged per layer.
    """
    out: dict[tuple[int, int], list[list[np.ndarray]]] = {}
    for role, polys in geom.polygons.items():
        out.setdefault(process.gds(role), []).extend([[p] for p in polys])
    return out


def cut_angle_deg(xsec: CrossSection2D) -> float:
    return math.degrees(math.atan2(xsec.p1[1] - xsec.p0[1], xsec.p1[0] - xsec.p0[0]))

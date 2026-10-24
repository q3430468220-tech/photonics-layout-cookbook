"""Tool-independent geometry: polygons on *roles* plus port definitions.

Device recipes first produce a :class:`Geometry` (pure numpy, no gdsfactory), which
is then turned into a gdsfactory ``Component`` by :mod:`photonics_cookbook.cells`.
Keeping the drawing maths separate makes it

* testable without installing the layout stack,
* re-usable for previews (matplotlib) and for other tools,
* explicit for students: a layout is "just" polygons on layers + ports.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Default polygon tolerance (um): max. deviation of a discretised arc from the circle.
ARC_TOLERANCE_UM = 0.001
#: Database unit (um) -- 1 nm, as used by gdsfactory / KLayout.
DBU_UM = 0.001


@dataclass(frozen=True)
class PortSpec:
    """A port in the gdsfactory sense: where something connects."""

    name: str
    center: tuple[float, float]
    width: float
    orientation: float  # degrees; direction pointing *out* of the device
    role: str  # process role of the port layer, e.g. "core" or "metal"
    port_type: str = "optical"


@dataclass
class Geometry:
    """Polygons grouped by process role, plus ports and free-form info."""

    name: str
    polygons: dict[str, list[np.ndarray]] = field(default_factory=dict)
    ports: list[PortSpec] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)

    def add(self, role: str, points: np.ndarray | list[np.ndarray]) -> None:
        polys = points if isinstance(points, list) else [points]
        for p in polys:
            arr = np.asarray(p, dtype=float)
            if arr.ndim != 2 or arr.shape[1] != 2 or len(arr) < 3:
                raise ValueError(f"polygon on {role!r} must be an (N>=3, 2) array")
            self.polygons.setdefault(role, []).append(arr)

    def bbox(self, roles: list[str] | None = None) -> tuple[float, float, float, float]:
        pts = [
            p for r, polys in self.polygons.items() if roles is None or r in roles for p in polys
        ]
        if not pts:
            raise ValueError("geometry has no polygons on the requested roles")
        allp = np.vstack(pts)
        return (
            float(allp[:, 0].min()),
            float(allp[:, 1].min()),
            float(allp[:, 0].max()),
            float(allp[:, 1].max()),
        )

    def port(self, name: str) -> PortSpec:
        for p in self.ports:
            if p.name == name:
                return p
        raise KeyError(f"no port {name!r}; ports: {[p.name for p in self.ports]}")


# ----------------------------------------------------------------- primitives
def snap(value: float, grid: float = DBU_UM) -> float:
    """Snap a coordinate to the database grid (avoids off-grid ports)."""
    return round(round(value / grid) * grid, 6)


def rect(x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """Axis-aligned rectangle as a counter-clockwise polygon."""
    xa, xb = sorted((x0, x1))
    ya, yb = sorted((y0, y1))
    return np.array([[xa, ya], [xb, ya], [xb, yb], [xa, yb]], dtype=float)


def _n_arc_points(radius: float, span_deg: float, tol: float) -> int:
    if radius <= 0:
        return 2
    # sagitta of one segment <= tol  ->  dtheta = 2 acos(1 - tol / r)
    dtheta = 2.0 * math.acos(max(-1.0, 1.0 - tol / radius))
    return max(2, math.ceil(math.radians(abs(span_deg)) / dtheta) + 1)


def arc_band(
    r_in: float,
    r_out: float,
    theta0_deg: float,
    theta1_deg: float,
    center: tuple[float, float] = (0.0, 0.0),
    tol: float = ARC_TOLERANCE_UM,
) -> list[np.ndarray]:
    """Annular sector ``r_in <= r <= r_out``, ``theta0 <= theta <= theta1``.

    Spans larger than 180 deg are split into several simple polygons (no holes),
    so a full 360 deg annulus is returned as two half rings. ``r_in == 0`` gives a
    pie slice.
    """
    if r_out <= r_in or r_in < 0:
        raise ValueError(f"need 0 <= r_in < r_out, got r_in={r_in}, r_out={r_out}")
    if theta1_deg <= theta0_deg:
        raise ValueError(f"need theta1 > theta0, got {theta0_deg} .. {theta1_deg}")
    span = theta1_deg - theta0_deg
    n_pieces = max(1, math.ceil(span / 180.0 - 1e-9))
    edges = np.linspace(theta0_deg, theta1_deg, n_pieces + 1)
    cx, cy = center
    out = []
    for a0, a1 in zip(edges[:-1], edges[1:], strict=True):
        n_out = _n_arc_points(r_out, a1 - a0, tol)
        t_out = np.radians(np.linspace(a0, a1, n_out))
        outer = np.column_stack([cx + r_out * np.cos(t_out), cy + r_out * np.sin(t_out)])
        if r_in > 0:
            n_in = _n_arc_points(r_in, a1 - a0, tol)
            t_in = np.radians(np.linspace(a1, a0, n_in))
            inner = np.column_stack([cx + r_in * np.cos(t_in), cy + r_in * np.sin(t_in)])
        else:
            inner = np.array([[cx, cy]])
        out.append(np.vstack([outer, inner]))
    return out


def annulus(
    r_in: float, r_out: float, center: tuple[float, float] = (0.0, 0.0), tol: float = ARC_TOLERANCE_UM
) -> list[np.ndarray]:
    """Full ring between ``r_in`` and ``r_out`` (two hole-free half rings)."""
    return arc_band(r_in, r_out, -90.0, 270.0, center=center, tol=tol)


def polar(r: float, theta_deg: float, center: tuple[float, float] = (0.0, 0.0)) -> np.ndarray:
    t = math.radians(theta_deg)
    return np.array([center[0] + r * math.cos(t), center[1] + r * math.sin(t)])


def polygon_area(points: np.ndarray) -> float:
    """Signed area (shoelace); > 0 for counter-clockwise polygons."""
    x, y = points[:, 0], points[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

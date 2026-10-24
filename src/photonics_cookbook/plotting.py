"""Matplotlib previews: top view of a :class:`Geometry` and side view of a cut.

These are teaching aids (and are used to check geometry in CI without KLayout).
For real layout work open the GDS in KLayout (``c.show()`` with klive).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from photonics_cookbook.geometry import Geometry
from photonics_cookbook.process import Process

if TYPE_CHECKING:
    from photonics_cookbook.lumerical.cutline import CrossSection2D

#: (face colour, alpha, hatch) per role -- loosely KLayout-like.
ROLE_STYLE: dict[str, tuple[str, float, str]] = {
    "slab": ("#9ecae1", 0.55, ""),
    "core": ("#08519c", 0.85, ""),
    "shallow_etch": ("#6baed6", 0.6, "//"),
    "n": ("#fdae6b", 0.35, "\\\\"),
    "np": ("#fd8d3c", 0.35, "\\\\"),
    "npp": ("#d94801", 0.45, "xx"),
    "p": ("#a1d99b", 0.35, "//"),
    "pp": ("#74c476", 0.35, "//"),
    "ppp": ("#238b45", 0.45, "xx"),
    "via": ("#252525", 0.9, ""),
    "metal": ("#bdbdbd", 0.45, ""),
    "heater": ("#e7298a", 0.5, ""),
    "pad": ("#969696", 0.5, ""),
}
DRAW_ORDER = ["slab", "core", "shallow_etch", "n", "p", "np", "pp", "npp", "ppp", "metal", "heater", "pad", "via"]


def plot_geometry(
    geom: Geometry,
    process: Process | None = None,
    ax=None,
    roles: list[str] | None = None,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
    show_ports: bool = True,
    cut: tuple[tuple[float, float], tuple[float, float]] | None = None,
):
    """Top view of ``geom``. Returns the matplotlib axes."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Polygon

    if ax is None:
        _, ax = plt.subplots(figsize=(7, 7))
    order = [r for r in DRAW_ORDER if r in geom.polygons] + [
        r for r in geom.polygons if r not in DRAW_ORDER
    ]
    handles = []
    for role in order:
        if roles is not None and role not in roles:
            continue
        fc, alpha, hatch = ROLE_STYLE.get(role, ("#cccccc", 0.4, ""))
        for pts in geom.polygons[role]:
            ax.add_patch(
                Polygon(pts, closed=True, facecolor=fc, alpha=alpha, hatch=hatch, edgecolor=fc, lw=0.4)
            )
        label = role if process is None else f"{process.layer(role).name} {process.layer(role).gds_str} ({role})"
        handles.append(Patch(facecolor=fc, alpha=alpha, hatch=hatch, edgecolor=fc, label=label))
    if show_ports:
        for p in geom.ports:
            ax.plot(*p.center, marker="o", ms=4, color="crimson")
            ax.annotate(p.name, p.center, textcoords="offset points", xytext=(4, 4), fontsize=8, color="crimson")
    if cut is not None:
        (x0, y0), (x1, y1) = cut
        ax.plot([x0, x1], [y0, y1], "--", color="crimson", lw=1.2)
        ax.annotate("cut", (x1, y1), textcoords="offset points", xytext=(4, -10), fontsize=8, color="crimson")
    ax.set_aspect("equal")
    ax.autoscale_view()
    if xlim:
        ax.set_xlim(*xlim)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(geom.name)
    ax.legend(handles=handles, fontsize=7, loc="upper right", framealpha=0.9)
    return ax


def plot_cross_section(xsec: CrossSection2D, process: Process, ax=None, z_range=None):
    """Side view (x along the cut, z vertical) of an extracted cross-section."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 3.2))
    x0, x1 = xsec.x_min, xsec.x_max
    for b in process.background:
        ax.add_patch(Rectangle((x0, b.zmin), x1 - x0, b.zmax - b.zmin, color="#deebf7" if b.material != "si" else "#bdbdbd", alpha=0.5, lw=0))
    for iv, (z0, z1) in xsec.solid_boxes(process):
        fc, alpha, _ = ROLE_STYLE.get(iv.role, ("#cccccc", 0.6, ""))
        ax.add_patch(Rectangle((iv.x0, z0), iv.x1 - iv.x0, z1 - z0, facecolor=fc, alpha=max(alpha, 0.7), edgecolor="k", lw=0.3))
    si_top = process.si_top
    si = [(iv, z) for iv, z in xsec.solid_boxes(process) if process.layer(iv.role).kind == "structure"]
    for iv in xsec.intervals:
        lay = process.layer(iv.role)
        if lay.kind != "doping":
            continue
        fc, _, hatch = ROLE_STYLE.get(iv.role, ("#cccccc", 0.3, "//"))
        for s, (z0, z1) in si:  # implants only exist where there is silicon
            a, b = max(iv.x0, s.x0), min(iv.x1, s.x1)
            if b > a:
                ax.add_patch(Rectangle((a, z0), b - a, z1 - z0, facecolor="none", edgecolor=fc, hatch=hatch, lw=0.6))
        ax.text(0.5 * (iv.x0 + iv.x1), si_top + 0.03, iv.role, ha="center", va="bottom", fontsize=7, color=fc)
    ax.set_xlim(x0, x1)
    ax.set_ylim(*(z_range or (-0.5, process.stack_zmax + 0.2)))
    ax.set_xlabel("x along cut (um), 0 = waveguide centre")
    ax.set_ylabel("z (um)")
    ax.set_title(f"cross-section of {xsec.cell}")
    return ax


def save(fig_or_ax, path: str | Path, dpi: int = 160) -> Path:
    fig = getattr(fig_or_ax, "figure", fig_or_ax)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    return path

"""Read polygons from a GDS file with KLayout's Python API (``klayout.db``).

The GDS file is the *contract* between layout and simulation: whatever tool drew
it (gdsfactory, KLayout, a foundry PCell), the Lumerical bridge only needs the
GDS + a process file. ``klayout`` is installed together with gdsfactory.

Polygons are returned per ``(layer, datatype)`` after merging, as lists of contours
``[hull, hole1, hole2, ...]`` in micrometres.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

Contours = list[np.ndarray]  # [hull, *holes], each (N, 2) in um
LayerPolygons = dict[tuple[int, int], list[Contours]]


def _pick_top_cell(layout, cell: str | None):
    if cell:
        top = layout.cell(cell)
        if top is None:
            names = [c.name for c in layout.each_cell()]
            raise ValueError(f"cell {cell!r} not in GDS; cells: {names[:20]}")
        return top
    tops = layout.top_cells()
    if len(tops) == 1:
        return tops[0]
    names = [c.name for c in tops]
    raise ValueError(f"GDS has {len(tops)} top cells {names}; pass cell=... explicitly")


def read_gds_polygons(
    gds_path: str | Path,
    cell: str | None = None,
    layers: list[tuple[int, int]] | None = None,
) -> tuple[str, LayerPolygons, tuple[float, float, float, float]]:
    """Return ``(cell_name, polygons_by_layer, bbox_um)`` for ``cell`` (hierarchy flattened)."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds_path))
    top = _pick_top_cell(layout, cell)
    dbu = layout.dbu
    wanted = {tuple(x) for x in layers} if layers else None

    out: LayerPolygons = {}
    for li in layout.layer_indexes():
        info = layout.get_info(li)
        key = (int(info.layer), int(info.datatype))
        if wanted is not None and key not in wanted:
            continue
        region = kdb.Region(top.begin_shapes_rec(li))
        region.merge()
        polys: list[Contours] = []
        for poly in region.each():
            contours = [np.array([[p.x * dbu, p.y * dbu] for p in poly.each_point_hull()], dtype=float)]
            for h in range(poly.holes()):
                contours.append(
                    np.array([[p.x * dbu, p.y * dbu] for p in poly.each_point_hole(h)], dtype=float)
                )
            polys.append(contours)
        if polys:
            out[key] = polys
    b = top.dbbox()
    return top.name, out, (b.left, b.bottom, b.right, b.top)

"""gdsfactory cells built from the cookbook's device recipes.

This is the only module (besides the examples) that imports gdsfactory. Every cell
follows the same three steps -- worth reading if you are new to gdsfactory:

1. load the foundry *process* (role -> GDS layer, see ``photonics_cookbook.process``),
2. compute role-tagged polygons + ports (pure Python, ``photonics_cookbook.devices``),
3. put them into a ``gf.Component``: ``add_polygon`` per layer, ``add_port`` per port,
   and store simulation hints in ``component.info``.

``@gf.cell`` gives each parameter set a unique, cached cell name -- so calling the
function twice with the same arguments returns the same cell, and different
arguments never collide in the GDS.
"""

from __future__ import annotations

import json
import warnings
from typing import Any

import gdsfactory as gf
import numpy as np

from photonics_cookbook.devices.ring_modulator import ring_modulator_geometry
from photonics_cookbook.geometry import Geometry
from photonics_cookbook.process import Process, load_process

PORT_WIDTH_GRID_UM = 0.002  # kfactory: port widths must be an even number of 1 nm database units


def activate_pdk(process: str | Process = "cornerstone_si220_active", force: bool = False):
    """Activate the foundry PDK that belongs to ``process`` (e.g. cspdk for CORNERSTONE).

    Since gdsfactory 9.29 no PDK is active by default, and layer look-ups in
    ``add_polygon`` / ``add_port`` go through the active PDK -- so *always activate a
    PDK before drawing*. If a PDK is already active it is kept (switching PDKs
    invalidates cells that were already built) unless ``force`` is set.
    Returns the active PDK.
    """
    if not force:
        try:
            pdk = gf.get_active_pdk()
            if pdk is not None:
                return pdk
        except Exception:
            pass
    proc = process if isinstance(process, Process) else load_process(process)
    modules = list(proc.upstream_pdk.get("modules") or [])
    errors = []
    if modules:
        from photonics_cookbook.process.upstream import import_pdk

        try:
            _, pdk = import_pdk(modules)
            pdk.activate()
            return pdk
        except Exception as err:
            errors.append(str(err))
    try:  # last resort: gdsfactory's generic PDK
        from gdsfactory.gpdk import PDK as GENERIC

        GENERIC.activate()
        warnings.warn(
            f"upstream PDK for {proc.name!r} not available ({'; '.join(errors) or 'none declared'}); "
            "activated the gdsfactory generic PDK instead",
            stacklevel=2,
        )
        return GENERIC
    except Exception as err:
        raise RuntimeError(f"could not activate any PDK: {errors + [str(err)]}") from err


def _plain(value: Any) -> Any:
    """Convert numpy scalars / tuples to JSON-friendly Python types for ``c.info``."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _snap(v: float, grid: float) -> float:
    return round(round(float(v) / grid) * grid, 6)


def geometry_to_component(geom: Geometry, process: Process, c: gf.Component | None = None) -> gf.Component:
    """Write a :class:`Geometry` into a gdsfactory Component (new one if ``c`` is None)."""
    c = gf.Component() if c is None else c
    for role, polys in geom.polygons.items():
        layer = process.gds(role)
        try:  # make sure the layer exists even if the active PDK does not define it
            gf.kcl.layer(*layer)
        except Exception:
            pass
        for pts in polys:
            c.add_polygon([(float(x), float(y)) for x, y in pts], layer=layer)
    for p in geom.ports:
        c.add_port(
            name=p.name,
            center=(_snap(p.center[0], 0.001), _snap(p.center[1], 0.001)),
            width=_snap(p.width, PORT_WIDTH_GRID_UM),
            orientation=float(p.orientation),
            layer=process.gds(p.role),
            port_type=p.port_type,
        )
    for key, value in {**geom.info, "process": process.name}.items():
        value = _plain(value)
        try:
            c.info[key] = value
        except Exception:  # older kfactory Info only takes flat values -> store JSON text
            c.info[key] = json.dumps(value)
    return c


@gf.cell
def ring_modulator(
    radius: float = 10.0,
    width: float = 0.5,
    gap: float = 0.2,
    junction_offset: float = 0.0,
    inner_dopant: str = "n",
    contact_spacing: float = 0.8,
    contact_width: float = 2.0,
    via_enclosure: float = 0.5,
    with_pads: bool = True,
    pad_pitch: float = 100.0,
    pad_size: float = 80.0,
    process: str = "cornerstone_si220_active",
) -> gf.Component:
    """Doped all-pass microring modulator with lateral PN junction and GSG pads.

    In-plane defaults follow the Ansys Lumerical "Ring Modulator" example
    (R = 10 um, 500 nm rib); see :func:`photonics_cookbook.devices.ring_modulator_geometry`
    for every parameter (the less common ones are exposed there).

    Ports: ``o1``/``o2`` optical bus ends; ``e1``/``e3`` ground pads (outer P side),
    ``e2`` signal pad (inner N side).
    """
    proc = load_process(process)
    activate_pdk(proc)  # no-op if a PDK is already active
    geom = ring_modulator_geometry(
        proc,
        radius=radius,
        width=width,
        gap=gap,
        junction_offset=junction_offset,
        inner_dopant=inner_dopant,
        contact_spacing=contact_spacing,
        contact_width=contact_width,
        via_enclosure=via_enclosure,
        with_pads=with_pads,
        pad_pitch=pad_pitch,
        pad_size=pad_size,
    )
    c = gf.Component()
    geometry_to_component(geom, proc, c)
    return c

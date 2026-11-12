"""gdsfactory cells of the cookbook (registered in the cookbook PDK).

Two ways of building a cell are shown here -- both are standard gdsfactory:

``ring_modulator`` -- *polygons*
    1. load the foundry process (role -> GDS layer, see ``photonics_cookbook.process``),
    2. compute role-tagged polygons + ports in pure Python (``photonics_cookbook.devices``),
    3. put them into a ``gf.Component`` with ``add_polygon`` / ``add_port`` and store
       simulation hints in ``component.info``.

``straight_pn`` -- *cross-section extrusion*
    take the PDK cross-section ``"rib_pn"`` (a list of Sections: core, slab, implants,
    vias, metal) and extrude it along a path. Every waveguide-like device (phase
    shifters, routing, heaters ...) is built this way in gdsfactory.

``@gf.cell`` gives each parameter set a unique, cached cell name -- so calling the
function twice with the same arguments returns the same cell, and different
arguments never collide in the GDS.
"""

from __future__ import annotations

import json
from typing import Any

import gdsfactory as gf
import numpy as np
from gdsfactory.typings import CrossSectionSpec

from photonics_cookbook.devices.ring_modulator import ring_modulator_geometry
from photonics_cookbook.geometry import Geometry
from photonics_cookbook.pdk import activate_pdk, ensure_pdk
from photonics_cookbook.process import Process, load_process

PORT_WIDTH_GRID_UM = 0.002  # kfactory: port widths must be an even number of 1 nm database units

#: Cells registered in the cookbook PDK (see photonics_cookbook.pdk.builder).
CELLS = ("ring_modulator", "straight_pn")

__all__ = ["CELLS", "activate_pdk", "ensure_pdk", "geometry_to_component", "ring_modulator", "straight_pn"]


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


def _set_info(c: gf.Component, info: dict[str, Any]) -> None:
    for key, value in info.items():
        value = _plain(value)
        try:
            c.info[key] = value
        except Exception:  # older kfactory Info only takes flat values -> store JSON text
            c.info[key] = json.dumps(value)


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
    _set_info(c, {**geom.info, "process": process.name})
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
    ensure_pdk(proc)  # activates the cookbook PDK only if no PDK is active
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


@gf.cell
def straight_pn(
    length: float = 500.0,
    cross_section: CrossSectionSpec = "rib_pn",
    process: str = "cornerstone_si220_active",
) -> gf.Component:
    """Straight lateral-PN rib waveguide: the cross-section ``rib_pn`` extruded over ``length``.

    The building block of a PN depletion phase shifter (Ansys example: 500 um).
    Ports: ``o1``/``o2`` optical; ``n1``/``n2`` (N-side metal) and ``p1``/``p2``
    (P-side metal) electrical. ``info["lumerical"]`` holds a cut across the middle
    for the CHARGE / FDE export.

    Needs a PDK that defines ``rib_pn`` (the cookbook PDK); pass a CrossSection
    object to use any other profile.
    """
    proc = load_process(process)
    pdk = ensure_pdk(proc)
    if isinstance(cross_section, str) and cross_section not in pdk.cross_sections:
        raise ValueError(
            f"cross-section {cross_section!r} is not defined in the active PDK {pdk.name!r}. "
            f"Activate the cookbook PDK first: photonics_cookbook.pdk.activate_pdk({proc.name!r})"
        )
    xs = gf.get_cross_section(cross_section)
    c = gf.path.straight(length=length).extrude(xs)

    half = max(abs(s.offset) + s.width / 2 for s in xs.sections) + 1.0
    half = float(np.ceil(half * 1000) / 1000)
    x_cut = length / 2
    _set_info(
        c,
        {
            "length": length,
            "process": proc.name,
            "contacts": {"anode": "ppp", "cathode": "npp", "anode_ports": ["p1", "p2"], "cathode_ports": ["n1", "n2"]},
            "lumerical": {
                "cut_p0_um": [x_cut, -half],
                "cut_p1_um": [x_cut, half],
                "cut_origin_um": [x_cut, 0.0],
                "bend_radius_um": None,
                "norm_length_um": length,
                "anode_role": "ppp" if proc.has("ppp") else "p",
                "cathode_role": "npp" if proc.has("npp") else "n",
            },
        },
    )
    return c

"""Rib waveguide on the GSiP teaching process: straight and bend, ready for the Lumerical Layer Builder.

    o1 ══════════╗                      core: 220 nm silicon, 0.5 um wide
                 ╚══════════ o2         slab: 90 nm silicon, 6 um wide, on both sides of the core

A rib waveguide keeps a thin slab of silicon beside the core.  The slab is what the active devices need:
it carries the implants and the contacts of a modulator.  The price is a weaker confinement, so a rib
needs a larger bend radius than a strip: 10 um on this process.

    straight()        straight rib
    bend()            circular bend; refuses a radius below the design rule
    rib_waveguide()   straight, S-bend, straight: the device of the tutorial

The cross-section, the layers and the design rules come from gsip_technology.py.

    python devices/rib_waveguide_builder.py     ->  devices/gds/rib_waveguide.gds, DRC report, preview image
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t

WIDTH = 0.5  # um, core width
SLAB_WIDTH = t.RIB_SLAB_WIDTH  # 6.0 um
RADIUS = t.DESIGN_RULES["rib_bend_radius"]  # 10 um


def _cross_section(width: float, slab_width: float, radius: float) -> gf.CrossSection:
    if width < t.MIN_WIDTH_SPACE["WG"][0]:
        raise ValueError(f"width {width} um is below the minimum width of the waveguide layer, {t.MIN_WIDTH_SPACE['WG'][0]} um")
    if slab_width <= width:
        raise ValueError(f"slab_width {slab_width} um must exceed the core width {width} um")
    rule = t.DESIGN_RULES["rib_bend_radius"]
    if radius < rule:
        raise ValueError(
            f"radius {radius} um is below the rib bend radius, {rule} um (gsip_technology.DESIGN_RULES['rib_bend_radius'])"
        )
    return gf.get_cross_section("rib", width=width, width_slab=slab_width, radius=radius)


@gf.cell
def straight(length: float = 10.0, width: float = WIDTH, slab_width: float = SLAB_WIDTH) -> gf.Component:
    """Straight rib waveguide along x; ports o1 (west) and o2 (east)."""
    return gf.components.straight(length=length, cross_section=_cross_section(width, slab_width, RADIUS))


@gf.cell
def bend(radius: float = RADIUS, angle: float = 90.0, width: float = WIDTH, slab_width: float = SLAB_WIDTH) -> gf.Component:
    """Circular bend of ``angle`` degrees."""
    return gf.components.bend_circular(radius=radius, angle=angle, cross_section=_cross_section(width, slab_width, radius))


@gf.cell
def rib_waveguide(
    length: float = 15.0,
    radius: float = RADIUS,
    bend_angle: float = 45.0,
    width: float = WIDTH,
    slab_width: float = SLAB_WIDTH,
) -> gf.Component:
    """Straight, S-bend and straight in a row.

    Args:
        length: length of each of the two straights (um).
        radius: radius of the two arcs of the S-bend (um).
        bend_angle: angle of each arc (deg); the S-bend shifts the waveguide sideways by 2 R (1 - cos angle).
        width: core width (um).
        slab_width: width of the 90 nm slab, centred on the core (um).

    Ports: o1 and o2 at the two ends.  ``info`` stores the route length.
    """
    xs = _cross_section(width, slab_width, radius)
    c = gf.Component()
    # one path, so that core and slab are single polygons without seams
    path = (
        gf.path.straight(length) + gf.path.arc(radius, -bend_angle) + gf.path.arc(radius, bend_angle) + gf.path.straight(length)
    )
    route = c << gf.path.extrude(path, cross_section=xs)
    c.add_ports(route.ports)
    c.info["width"] = width
    c.info["slab_width"] = slab_width
    c.info["radius"] = radius
    c.info["length_route"] = round(path.length(), 3)
    return c


if __name__ == "__main__":
    from devices import write_device

    device = rib_waveguide()
    info = device.info
    print(
        f"rib {info['width']} um wide on a {info['slab_width']} um slab, S-bend of R = {info['radius']} um, route {info['length_route']} um"
    )
    sys.exit(write_device(device, "rib_waveguide"))

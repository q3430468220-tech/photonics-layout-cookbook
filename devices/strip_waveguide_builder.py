"""Strip waveguide on the GSiP teaching process: straight, bend and width taper, ready for the Lumerical Layer Builder.

    o1 ══════════╗
                 ╚═══════════◁████████ o2
       straight   S-bend      taper   wide straight

A strip waveguide is the 220 nm silicon layer etched through on both sides of the core.  It is the routing
waveguide of the process: 0.5 um wide, it bends at a radius of 5 um.  A wide strip has less sidewall loss
on long straight runs; a taper joins the two widths.

    straight()         straight strip
    bend()             circular or Euler bend; refuses a radius below the design rule
    taper()            linear width taper
    strip_waveguide()  the three in a row, as in the drawing: the device of the tutorial

The cross-section, the layers and the design rules come from gsip_technology.py.

    python devices/strip_waveguide_builder.py     ->  devices/gds/strip_waveguide.gds, DRC report, preview image
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t

WIDTH = 0.5  # um, single-mode routing width (step 1 of lumerical_simulations/strip_waveguide)
WIDE_WIDTH = 3.0  # um, wide waveguide for long straight runs
TAPER_LENGTH = 20.0  # um, between WIDTH and WIDE_WIDTH: the length at which step 2 finds the taper lossless
RADIUS = t.DESIGN_RULES["strip_bend_radius"]  # 5 um


def _check_width(width: float) -> None:
    if width < t.MIN_WIDTH_SPACE["WG"][0]:
        raise ValueError(f"width {width} um is below the minimum width of the waveguide layer, {t.MIN_WIDTH_SPACE['WG'][0]} um")


@gf.cell
def straight(length: float = 10.0, width: float = WIDTH) -> gf.Component:
    """Straight strip waveguide along x; ports o1 (west) and o2 (east)."""
    _check_width(width)
    return gf.components.straight(length=length, cross_section=gf.get_cross_section("strip", width=width))


@gf.cell
def bend(radius: float = RADIUS, angle: float = 90.0, width: float = WIDTH, euler: bool = False) -> gf.Component:
    """Bend of ``angle`` degrees.

    euler=False draws a circular arc of the given radius.  euler=True draws an Euler bend with the same
    footprint: its curvature rises from zero, so there is no jump at the joins to the straights, but its
    tightest point is sharper than ``radius``.  The design rule is checked against the nominal radius.
    """
    _check_width(width)
    rule = t.DESIGN_RULES["strip_bend_radius"]
    if radius < rule:
        raise ValueError(
            f"radius {radius} um is below the strip bend radius, {rule} um (gsip_technology.DESIGN_RULES['strip_bend_radius'])"
        )
    xs = gf.get_cross_section("strip", width=width, radius=radius)
    make = gf.components.bend_euler if euler else gf.components.bend_circular
    return make(radius=radius, angle=angle, cross_section=xs)


@gf.cell
def taper(length: float = TAPER_LENGTH, width1: float = WIDTH, width2: float = WIDE_WIDTH) -> gf.Component:
    """Linear taper from ``width1`` (port o1, west) to ``width2`` (port o2, east)."""
    _check_width(min(width1, width2))
    return gf.components.taper(
        length=length, width1=width1, width2=width2, cross_section=gf.get_cross_section("strip", width=width1)
    )


@gf.cell
def strip_waveguide(
    length: float = 15.0,
    radius: float = RADIUS,
    bend_angle: float = 45.0,
    taper_length: float = TAPER_LENGTH,
    wide_width: float = WIDE_WIDTH,
    wide_length: float = 10.0,
    width: float = WIDTH,
) -> gf.Component:
    """Straight, S-bend, taper and wide straight in a row.

    Args:
        length: length of each of the two straights around the S-bend (um).
        radius: radius of the two arcs of the S-bend (um).
        bend_angle: angle of each arc (deg); the S-bend shifts the waveguide sideways by 2 R (1 - cos angle).
        taper_length: length of the taper (um).  The default comes from step 2 of the simulations.
        wide_width, wide_length: the wide waveguide after the taper (um).
        width: core width of the routing waveguide (um).

    Ports: o1 at the start, o2 at the end of the wide waveguide.  ``info`` stores the lengths.
    """
    rule = t.DESIGN_RULES["strip_bend_radius"]
    if radius < rule:
        raise ValueError(
            f"radius {radius} um is below the strip bend radius, {rule} um (gsip_technology.DESIGN_RULES['strip_bend_radius'])"
        )
    _check_width(width)
    c = gf.Component()
    # one path, so that the straights and the two arcs form a single polygon without seams
    path = (
        gf.path.straight(length) + gf.path.arc(radius, -bend_angle) + gf.path.arc(radius, bend_angle) + gf.path.straight(length)
    )
    route = c << gf.path.extrude(path, cross_section=gf.get_cross_section("strip", width=width, radius=radius))
    tp = c << taper(length=taper_length, width1=width, width2=wide_width)
    tp.connect("o1", route.ports["o2"])
    wide = c << straight(length=wide_length, width=wide_width)
    wide.connect("o1", tp.ports["o2"])
    c.add_port("o1", port=route.ports["o1"])
    c.add_port("o2", port=wide.ports["o2"])
    c.info["width"] = width
    c.info["radius"] = radius
    c.info["length_route"] = round(path.length(), 3)
    c.info["length_taper"] = taper_length
    c.info["wide_width"] = wide_width
    return c


if __name__ == "__main__":
    from devices import write_device

    device = strip_waveguide()
    info = device.info
    print(f"strip {info['width']} um wide, S-bend of R = {info['radius']} um, route {info['length_route']} um, "
          f"taper {info['length_taper']} um to {info['wide_width']} um")  # fmt: skip
    sys.exit(write_device(device, "strip_waveguide"))

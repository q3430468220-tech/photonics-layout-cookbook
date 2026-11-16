"""Directional coupler on the GSiP teaching process, ready for the Lumerical Layer Builder.

    o2 ════╗                    ╔════ o3      cross port
           ╚════════════════════╝
           ╔════════════════════╗             two strip waveguides, ``gap`` apart over ``length``
    o1 ════╝                    ╚════ o4      through port
    (in)    S-bend   coupler   S-bend

Two strip waveguides run side by side.  Their modes overlap, and light entering at o1 moves across to the
other waveguide and back.  How much has crossed at the end depends on the gap and on the length: a short
coupler taps off a few per cent, a longer one splits the light in half.

    directional_coupler()   the device; gap, length and port spacing are arguments

The cross-section, the layers and the design rules come from gsip_technology.py.

    python devices/directional_coupler_builder.py     ->  devices/gds/directional_coupler.gds, DRC report, preview image
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t

WIDTH = 0.5  # um, core width of both waveguides
GAP = 0.20  # um, the minimum space of the waveguide layer: the strongest coupling the process allows
LENGTH = 15.0  # um, the 50:50 length at 1.55 um: step 2 of lumerical_simulations/directional_coupler finds 15.03
PORT_SPACING = 4.0  # um, centre to centre, at both ends
BEND_LENGTH = 10.0  # um, length of each S-bend along x


@gf.cell
def directional_coupler(
    gap: float = GAP,
    length: float = LENGTH,
    width: float = WIDTH,
    port_spacing: float = PORT_SPACING,
    bend_length: float = BEND_LENGTH,
) -> gf.Component:
    """Directional coupler: two parallel strips with an S-bend at each of the four ends.

    Args:
        gap: edge-to-edge gap between the two cores in the straight section (um).
        length: length of the straight section (um).  The default is the length at which the simulated
            device splits the light in half at 1.55 um.
        width: core width of both waveguides (um).
        port_spacing: centre-to-centre distance of the ports at each end (um).
        bend_length: length of each S-bend along x (um).

    Ports: o1 (input) and o2 on the west side, o4 (through, the waveguide of o1) and o3 (cross) on the east.
    ``info`` stores the dimensions and the smallest radius of curvature of the S-bends.
    """
    if gap < t.MIN_WIDTH_SPACE["WG"][1]:
        raise ValueError(f"gap {gap} um is below the minimum space of the waveguide layer, {t.MIN_WIDTH_SPACE['WG'][1]} um")
    if width < t.MIN_WIDTH_SPACE["WG"][0]:
        raise ValueError(f"width {width} um is below the minimum width of the waveguide layer, {t.MIN_WIDTH_SPACE['WG'][0]} um")
    if port_spacing <= width + gap:
        raise ValueError(f"port_spacing {port_spacing} um must exceed width + gap, {width + gap:.3f} um")
    xs = gf.get_cross_section("strip", width=width)
    c = gf.Component()
    ref = c << gf.components.coupler(gap=gap, length=length, dy=port_spacing, dx=bend_length, cross_section=xs,
                                     bend=gf.components.bend_s, allow_min_radius_violation=True)  # fmt: skip
    ref.dcenter = (0.0, 0.0)  # the middle of the straight section and of the gap is the origin
    c.add_ports(ref.ports)
    radius = float(ref.cell.info["min_bend_radius"])
    rule = t.DESIGN_RULES["strip_bend_radius"]
    if radius < rule:
        raise ValueError(
            f"the S-bends curve down to a radius of {radius:.2f} um, below the strip bend radius of {rule} um: "
            f"increase bend_length ({bend_length} um) or reduce port_spacing ({port_spacing} um)"
        )
    c.info["gap"] = gap
    c.info["length"] = length
    c.info["width"] = width
    c.info["port_spacing"] = port_spacing
    c.info["bend_length"] = bend_length
    c.info["min_bend_radius"] = round(radius, 3)
    return c


if __name__ == "__main__":
    from devices import write_device

    device = directional_coupler()
    info = device.info
    print(f"coupler: gap {info['gap']} um over {info['length']} um, S-bends {info['bend_length']} um long "
          f"(tightest radius {info['min_bend_radius']} um), ports {info['port_spacing']} um apart")  # fmt: skip
    sys.exit(write_device(device, "directional_coupler"))

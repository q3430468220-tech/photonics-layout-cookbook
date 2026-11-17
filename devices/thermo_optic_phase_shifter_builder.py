"""Thermo-optic phase shifter with thermal isolation trenches, on the GSiP teaching process, ready for the Layer Builder.

A current through the heater warms the waveguide core. Warmer silicon has a higher index, so the light
in the core gains phase. Two deep trenches beside the heater stop part of the heat from flowing sideways
into the oxide. The core then warms more for the same power, so less power gives a phase shift of pi. The
price is speed: the same heat has to warm the same mass, so the heater responds more slowly.

    part              layer        what it is
    ----------------  -----------  -----------------------------------------------------------------
    waveguide         WG           silicon core, 0.5 um wide, 220 nm high, from o1 to o2
    heater filament   HEATER       TiN film, 150 nm thick, 2.0 um wide, centred above the core
    landings          HEATER       the film widens at both ends of the filament; via 1 sits in each
    via 1             VIA1         one square in each landing, from the heater to metal 2
    wires             M2           metal 2 from each via 1 north to a pad, 2.0 um wide
    pads              M3, PADOPEN  metal 3 with the passivation opened; ports H1 (west) and H2 (east)
    trenches          DEEPTRENCH   one on each side of the core, along the free filament only
    optical ports     o1, o2       the two ends of the waveguide, 5 um beyond each landing

The trenches are optional. ``trench_gap=None`` draws the same device without them: the pads, the wires and
the heater stay where they are, so the two layouts differ only by the trenches. The simulations use it as
the reference.

Dimensions (um).  The origin lies at the centre of the heater, on the centre line of the core.  The
filament runs from x = -length / 2 to length / 2; each landing is 2 um long beyond it, and the via 1 of
each landing sits at its centre.  The trenches run from the inner edge of the metal 2 wires inwards, 2 um
from each wire.  The trench rules are in gsip_technology.DESIGN_RULES and MIN_WIDTH_SPACE; the builder
refuses a set of arguments that breaks one of them and names the rule.

    python devices/thermo_optic_phase_shifter_builder.py     ->  devices/gds/thermo_optic_phase_shifter.gds (flat,
                                                                 for the Layer Builder), the DRC report and two
                                                                 preview images in build/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t
from devices.wiring import TAB, VIA1_SIZE, pad_with_tab, reach_beyond, square, wire

# ---- dimensions (um), the module constants that the simulations import ----
WIDTH = 0.5  # core width: the single-mode strip of lumerical_simulations/strip_waveguide
LENGTH = 100.0  # heated length: the free filament between the two landings
HEATER_WIDTH = 2.0  # TiN film above the core (rule: at least the minimum width of the HEATER layer)
TRENCH_GAP = 2.0  # centre line of the core to the inner edge of each trench: the heater stands on a 4 um oxide ridge
TRENCH_WIDTH = 6.0  # from the inner edge of a trench outwards
LANDING_LENGTH = 2.0  # along x: each landing reaches this far beyond the end of the filament
LANDING_EXTRA = 0.4  # the landing is this much wider than the film, so that via 1 has room on each side
WIRE_WIDTH = 2.0  # metal 2 from a landing to its pad; its centre line is the centre line of the via 1
WG_EXTRA = 5.0  # waveguide beyond each landing, to the optical ports
PAD_SIZE = 80.0  # pad edge, as in the ring modulator
PAD_Y = 60.0  # centre of both pads: the tab of metal 2 then clears the trenches by the trench_to_metal rule
DEEPTRENCH = t.LAYER.DEEPTRENCH


def landing_width(heater_width: float) -> float:
    """Width of a heater landing: wide enough for via 1 with its enclosure, and wider than the film."""
    return max(heater_width, VIA1_SIZE + 2 * t.DESIGN_RULES["via1_enclosure_by_lower"]) + LANDING_EXTRA


def via_x(length: float) -> float:
    """x of the centre of each via 1 (the centre of the landing), measured from the origin."""
    return length / 2 + LANDING_LENGTH / 2


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def check_arguments(length: float, heater_width: float, trench_gap: float | None, trench_width: float, width: float) -> float:
    """Refuse the arguments that break a rule.  Returns the length of each trench along x (0 without trenches)."""
    if length <= 0:
        raise ValueError(f"length {length} um must be positive")
    film = t.MIN_WIDTH_SPACE["HEATER"][0]
    if heater_width < film:
        raise ValueError(f"heater_width {heater_width} um is below the minimum width of the heater film, {film} um")
    core = t.MIN_WIDTH_SPACE["WG"][0]
    if width < core:
        raise ValueError(f"width {width} um is below the minimum width of the waveguide layer, {core} um")
    if trench_gap is None:
        return 0.0
    trench_min = t.MIN_WIDTH_SPACE["DEEPTRENCH"][0]
    if trench_width < trench_min:
        raise ValueError(f"trench_width {trench_width} um is below the minimum width of the deep trench, {trench_min} um")
    eps = 1e-9
    rule = t.DESIGN_RULES["trench_to_heater"]
    clearance = trench_gap - heater_width / 2
    if clearance < rule - eps:
        raise ValueError(
            f"the trench is {clearance:.2f} um from the edge of the heater film (trench_gap {trench_gap} um, "
            f"heater_width {heater_width} um); the rule trench_to_heater needs {rule:.2f} um"
        )
    rule = t.DESIGN_RULES["trench_to_waveguide"]
    clearance = trench_gap - width / 2
    if clearance < rule - eps:
        raise ValueError(
            f"the trench is {clearance:.2f} um from the edge of the waveguide core (trench_gap {trench_gap} um); "
            f"the rule trench_to_waveguide needs {rule:.2f} um"
        )
    wall_min = t.MIN_WIDTH_SPACE["DEEPTRENCH"][1]  # the minimum space of the layer: the wall between two trenches
    wall = 2 * trench_gap
    if wall < wall_min - eps:
        raise ValueError(
            f"the wall between the two trenches is {wall:.2f} um wide (trench_gap {trench_gap} um on each side of the "
            f"centre line); the minimum space of the deep trench is {wall_min:.2f} um"
        )
    rule = t.DESIGN_RULES["trench_to_metal"]
    tab_bottom = PAD_Y - PAD_SIZE / 2 - TAB  # the metal 2 tab of each pad
    clearance = tab_bottom - (trench_gap + trench_width)
    if clearance < rule - eps:
        raise ValueError(
            f"the trench reaches {trench_gap + trench_width:.2f} um from the centre line, {clearance:.2f} um from the "
            f"metal 2 tab of the pads; the rule trench_to_metal needs {rule:.2f} um"
        )
    # the trenches end trench_to_metal before the metal 2 wires, which stand on the landings
    rule = t.DESIGN_RULES["trench_to_metal"]
    wire_inner = via_x(length) - WIRE_WIDTH / 2
    trench_len = 2 * (wire_inner - rule)
    if trench_len < trench_min - eps:
        minimum = (
            trench_min - (LANDING_LENGTH - WIRE_WIDTH) + 2 * rule
        )  # trench_len = length + LANDING_LENGTH - WIRE_WIDTH - 2 rule
        raise ValueError(
            f"a heated length of {length} um leaves {trench_len:.2f} um of trench between the landings; the minimum "
            f"width of the deep trench is {trench_min} um, so the length must be at least {minimum:.1f} um"
        )
    return trench_len


def _cell_rect(c: gf.Component, x0: float, y0: float, x1: float, y1: float, layer) -> None:
    c.add_polygon(_rect(x0, y0, x1, y1), layer=layer)


@gf.cell
def core_waveguide(length: float = LENGTH + 2 * (LANDING_LENGTH + WG_EXTRA), width: float = WIDTH) -> gf.Component:
    """Straight strip waveguide along x, from x = 0 to x = length; ports o1 and o2."""
    return gf.components.straight(length=length, cross_section=gf.get_cross_section("strip", width=width))


@gf.cell
def heater_film(length: float = LENGTH, heater_width: float = HEATER_WIDTH) -> gf.Component:
    """TiN filament centred above the core, with a landing at each end and a via 1 in each landing."""
    c = gf.Component()
    half = heater_width / 2
    _cell_rect(c, -length / 2, -half, length / 2, half, t.HEATER)
    lw = landing_width(heater_width)
    for sign in (-1.0, 1.0):
        x = sign * via_x(length)
        _cell_rect(c, x - LANDING_LENGTH / 2, -lw / 2, x + LANDING_LENGTH / 2, lw / 2, t.HEATER)
        c.add_polygon(square((x, 0.0), VIA1_SIZE), layer=t.VIA1)
    return c


@gf.cell
def trench_pair(length: float = LENGTH, gap: float = TRENCH_GAP, width: float = TRENCH_WIDTH) -> gf.Component:
    """Two deep trenches, one on each side of the core: from ``gap`` to ``gap + width`` from the centre line, centred on x = 0."""
    c = gf.Component()
    _cell_rect(c, -length / 2, gap, length / 2, gap + width, DEEPTRENCH)
    _cell_rect(c, -length / 2, -gap - width, length / 2, -gap, DEEPTRENCH)
    return c


@gf.cell
def thermo_optic_phase_shifter(
    length: float = LENGTH,
    heater_width: float = HEATER_WIDTH,
    trench_gap: float | None = TRENCH_GAP,
    trench_width: float = TRENCH_WIDTH,
    width: float = WIDTH,
) -> gf.Component:
    """Thermo-optic phase shifter: waveguide, heater with landings, two trenches, metal 2 wires and two pads.

    Args:
        length: heated length, the free filament between the two landings (um).
        heater_width: width of the TiN filament (um).
        trench_gap: centre line of the core to the inner edge of each trench (um); None draws no trenches.
        trench_width: width of each trench, from its inner edge outwards (um).
        width: core width (um).

    Ports: o1 and o2 at the ends of the waveguide, H1 (west) and H2 (east) on the pads.  ``info`` stores the
    numbers that the simulations need: the heated length, the length of the trenches, the isolated fraction of
    the filament, the heater width, the trench gap and width, and the resistance of the filament from the
    sheet resistance of the technology file.
    """
    trench_len = check_arguments(length, heater_width, trench_gap, trench_width, width)
    c = gf.Component()
    wg_length = length + 2 * (LANDING_LENGTH + WG_EXTRA)
    core = c << core_waveguide(length=wg_length, width=width)
    core.dmovex(-wg_length / 2)
    c.add_ports(core.ports)
    c << heater_film(length=length, heater_width=heater_width)
    if trench_gap is not None:
        c << trench_pair(length=trench_len, gap=trench_gap, width=trench_width)

    # ---- metal 2 from each via 1 north to its pad, with a row of via 2 under the pad's metal 2 tab ----
    for name, sign in (("H1", -1.0), ("H2", 1.0)):
        x = sign * via_x(length)
        end = pad_with_tab(c, (x, PAD_Y), PAD_SIZE)
        start_reach = reach_beyond((x, 0.0), (0.0, 1.0), [square((x, 0.0), VIA1_SIZE)])
        wire(c, [(x, 0.0), (x, end[1])], start_reach=start_reach, width=WIRE_WIDTH)
        c.add_port(name, center=(x, PAD_Y), width=PAD_SIZE, orientation=90, layer=t.M3, port_type="electrical")

    c.info["length_heater"] = length
    c.info["length_trenches"] = trench_len
    c.info["isolated_fraction"] = round(trench_len / length, 4)
    c.info["heater_width"] = heater_width
    c.info["trench_gap"] = trench_gap
    c.info["trench_width"] = trench_width
    c.info["width"] = width
    c.info["length_waveguide"] = wg_length
    c.info["heater_resistance"] = round(t.HEATER_SHEET_RESISTANCE * length / heater_width, 3)  # ohm: R = Rs * L / w
    return c


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.parse_args(argv)
    from devices import write_device

    device = thermo_optic_phase_shifter()
    info = device.info
    print(
        f"heater {info['length_heater']} um long, trenches along {info['length_trenches']} um "
        f"({info['isolated_fraction']:.0%} of the filament), filament resistance {info['heater_resistance']} ohm"
    )
    return write_device(device, "thermo_optic_phase_shifter", zoom=(-60, -12, -36, 22))


if __name__ == "__main__":
    sys.exit(main())

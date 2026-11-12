"""Heater-tuned microring modulator on the GSiP teaching process, ready for the Lumerical Layer Builder.

                [G1]       [S]       [G2]            north: GSG pads of the PN junction (metal 3)
                   \\        |        /
                    \\    .--|--.    /                metal 2 traces; S crosses the ring on metal 2
                     \\  /   |   \\  /
                      \\|   (o)   |/                  ring: rib waveguide, R = 10 um
                        \\       /                    PN section: 240 deg, n inside (S), p outside (G)
        o1 ==============`-._.-'============== o2    heater: TiN film above the core, 270 deg
                      /           \\                  bus: rib waveguide, point coupler at the bottom
                  [H1]             [H2]              south: heater pads

Three conductor levels are used, which is what a real active process offers:

    metal 1   contacts of the junction: a disc inside the ring (signal), an arc outside (ground)
    heater    TiN arc above the waveguide core, in the same plane as metal 1
    metal 2   routing; it crosses the heater and metal 1 where needed
    metal 3   pads, opened through the passivation

    optics       ring()            closed rib ring + the implants of the PDK cross-section rib_pn
                 bus()             straight rib bus waveguide
    electrics    pn_contacts()     contact vias, metal 1, and the via 1 landings (ports S, G1, G2)
                 heater()          TiN arc with two landings (ports H1, H2)
    device       ring_modulator()  assembles them, adds metal 2 traces and pads

All cross-sections, layers and design rules come from gsip_technology.py.

    python rm_builder.py     ->  rm_ring.gds (flat, for the Layer Builder), DRC report, preview images
"""

from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gdsfactory as gf

import gsip_technology as t

# ---- dimensions (um).  Radial distances are measured from the centre line of the ring waveguide. ----
SLAB_WIDTH = t.RIB_SLAB_WIDTH  # 6.0: slab of ring and bus
VIA_GAP = 1.90  # centre line -> near edge of the contact vias (N++ / P++ start at 1.25)
VIA_SIZE = 0.50  # contact via, square (rule: >= 0.4)
VIA_PITCH = 1.00  # along the arc
M1_GAP = 1.60  # centre line -> near edge of metal 1 (0.8 um away from the heater)
M1_WIDTH = 2.00  # outer electrode arc
HEATER_WIDTH = 1.60  # TiN film above the core (rule: >= 0.8)
LANDING = 2.40  # tangential width of a heater landing
LANDING_REACH = 2.40  # a landing extends this far outside the centre line
VIA1_SIZE = 1.00  # rule: >= 0.5
VIA2_SIZE = 2.00  # rule: >= 1.0
VIA2_PITCH = 6.00
ARC_MARGIN = 1.00  # vias stay this far from the ends of the doped arc
TRACE = 6.00  # metal 2 wire width
TAB = 8.00  # metal 3 tab at a pad: metal 2 ends below it, joined by a row of via 2
SLAB_NOTCH = 0.70  # the wedge between ring slab and bus slab is filled up to this width (rule: space >= 0.3)
ARC_STEP_DEG = 0.5  # polygon resolution of every arc
ENCLOSURE_MARGIN = 0.10  # metal 2 beyond the via 1 enclosure rule, so that no wire end lies exactly on the limit
DISC_VIAS = [(x, y) for x in (-2.0, 0.0, 2.0) for y in (-2.0, 0.0, 2.0)]  # via 1 on the inner disc: 3 x 3, 2 um pitch
ELECTRODE_ANGLES = {"G1": 135.0, "G2": 45.0}  # outer electrode: the ports and the via 1 row sit at these angles


# =====================================================================================
# geometry helpers
# =====================================================================================
def _arc_points(radius: float, a0: float, a1: float) -> np.ndarray:
    """Points on a circle around the origin from angle a0 to a1 (degrees, counter-clockwise if a1 > a0)."""
    n = max(math.ceil(abs(a1 - a0) / ARC_STEP_DEG), 2) + 1
    a = np.radians(np.linspace(a0, a1, n))
    return np.c_[radius * np.cos(a), radius * np.sin(a)]


def _sector(r0: float, r1: float, a0: float, a1: float) -> np.ndarray:
    """Annular sector between radii r0 < r1 and angles a0 < a1."""
    return np.vstack([_arc_points(r1, a0, a1), _arc_points(r0, a1, a0)])


def _polar(radius: float, angle: float) -> np.ndarray:
    return radius * np.array([math.cos(math.radians(angle)), math.sin(math.radians(angle))])


def _square(centre, size: float, angle: float = 0.0) -> list[tuple[float, float]]:
    """Square of edge ``size`` centred on ``centre``, rotated by ``angle`` degrees."""
    return _box(centre, size, size, angle)


def _box(centre, radial: float, tangential: float, angle: float = 0.0) -> list[tuple[float, float]]:
    """Rectangle centred on ``centre``: ``radial`` long along the direction ``angle``, ``tangential`` wide across it."""
    u = _polar(1.0, angle)
    v = np.array([-u[1], u[0]])
    c = np.asarray(centre, dtype=float)
    return [tuple(c + sx * u * radial / 2 + sy * v * tangential / 2) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _slab_fillets(radius: float, y_bus: float) -> list[list[tuple[float, float]]]:
    """Polygons that fill the two wedges between the slab of the ring and the slab of the bus.

    The ring slab is an annulus, the bus slab a band.  Where the outer circle of the annulus crosses the
    upper edge of the band, the two outlines part at a shallow angle and leave a wedge of missing slab
    that is narrower than the minimum space.  Each wedge is filled up to the point where it is
    ``SLAB_NOTCH`` wide.  The fillets overlap both slabs, so the merged outline has no seam.
    """
    r_out, y_edge = radius + SLAB_WIDTH / 2, y_bus + SLAB_WIDTH / 2  # outer circle, upper edge of the band
    y_wide = y_edge + SLAB_NOTCH
    if abs(y_edge) >= r_out or abs(y_wide) >= r_out:
        return []  # the outlines do not cross
    x_apex, x_wide = math.sqrt(r_out**2 - y_edge**2), math.sqrt(r_out**2 - y_wide**2)
    return [
        [
            (side * (x_apex - 0.3), y_edge - 0.1),
            (side * x_wide, y_edge - 0.1),
            (side * x_wide, y_wide + 0.1),
            (side * (x_apex - 0.3), y_edge + 0.1),
        ]
        for side in (+1, -1)
    ]


def _angles(pn_angle: float, heater_angle: float) -> tuple[float, float, float, float]:
    """Start / end angle of the PN section and of the heater.  Both are centred on north (90 deg)."""
    return 90 - pn_angle / 2, 90 + pn_angle / 2, 90 - heater_angle / 2, 90 + heater_angle / 2


def _lowest_y(component: gf.Component, layer) -> float:
    """Lowest point, in um, of the polygons that a component draws on one layer."""
    return float(np.vstack(component.get_polygons_points(by="tuple")[tuple(layer)])[:, 1].min())


def _via_row(c: gf.Component, layer, radius: float, a0: float, a1: float, size: float, pitch: float) -> int:
    """Square vias along an arc of the given radius between the angles a0 and a1, each rotated to follow the arc.

    The number of vias is odd, so that one sits in the middle of the arc: a cross-section cut through
    the symmetry axis of the device then shows a via in every row.
    """
    length = math.radians(a1 - a0) * radius
    count = max(int(length // pitch), 1)
    count -= 1 - count % 2
    start = (length - (count - 1) * pitch) / 2  # centre the row on the arc
    for k in range(count):
        angle = a0 + math.degrees((start + k * pitch) / radius)
        c.add_polygon(_square(_polar(radius, angle), size, angle), layer=layer)
    return count


def _electrode_vias(radius: float, angle: float) -> list[tuple[tuple[float, float], float]]:
    """Centre and rotation of the three via 1 of an outer electrode centred on angle: a row along the arc."""
    r_mid = radius + M1_GAP + M1_WIDTH / 2
    step = math.degrees(2.0 / r_mid)
    return [(tuple(_polar(r_mid, angle + k * step)), angle + k * step) for k in (-1, 0, 1)]


# =====================================================================================
# optics
# =====================================================================================
@gf.cell
def ring(radius: float = 10.0, width: float = 0.5, pn_angle: float = 240.0, p_inside: bool = False) -> gf.Component:
    """Closed rib ring; the arc of ``pn_angle`` degrees centred on north carries the six junction implants.

    The ring is extruded as one closed path so that core and slab have no seam.  Of the doped
    cross-section only the implant layers are added on top.
    """
    a0, a1, _, _ = _angles(pn_angle, 0)
    c = gf.Component()
    passive = gf.get_cross_section("rib", width=width, width_slab=SLAB_WIDTH, radius=radius)
    # the path overlaps itself by 1 deg and the result is merged, which removes the seam of a closed ring
    loop = gf.path.extrude(gf.Path(_arc_points(radius, 269.5, 630.5)), cross_section=passive)
    for layer in (t.WG, t.SLAB90):
        c.add_polygon(loop.get_region(layer, merge=True), layer=layer)
    doped = gf.get_cross_section("rib_pn", width=width, width_slab=SLAB_WIDTH, radius=radius, p_inside=p_inside)
    arc = gf.path.extrude(gf.Path(_arc_points(radius, a0, a1)), cross_section=doped)
    slab = c.get_region(t.SLAB90, merge=True)
    for layer in (t.N, t.P, t.NP, t.PP, t.NPP, t.PPP):
        # clipped to the slab: the end faces of two extruded sections can differ by 1 nm
        c.add_polygon(arc.get_region(layer, merge=True) & slab, layer=layer)
    return c


@gf.cell
def bus(length: float = 120.0, width: float = 0.5) -> gf.Component:
    """Straight rib bus waveguide centred on the origin; ports o1 (west) and o2 (east)."""
    c = gf.Component()
    ref = c << gf.components.straight(length=length, cross_section=gf.get_cross_section("rib", width=width))
    ref.dmovex(-length / 2)
    c.add_ports(ref.ports)
    return c


# =====================================================================================
# electrics
# =====================================================================================
@gf.cell
def pn_contacts(radius: float = 10.0, pn_angle: float = 240.0) -> gf.Component:
    """Contacts of the PN section.

    Inside the ring: a row of contact vias on the inner contact implant and a metal 1 disc that fills
    the ring.  Outside: a row of vias on the outer contact implant under a metal 1 arc.  Via 1 lands in
    the middle of the disc (port S) and at two places on the arc (ports G1, west, and G2, east).
    Which side is n and which is p is decided by the ring, not here.
    """
    a0, a1, _, _ = _angles(pn_angle, 0)
    c = gf.Component()
    r_in, r_out = radius - VIA_GAP - VIA_SIZE / 2, radius + VIA_GAP + VIA_SIZE / 2  # via centre lines
    for r in (r_in, r_out):
        margin = math.degrees(ARC_MARGIN / r)
        _via_row(c, t.VIAC, r, a0 + margin, a1 - margin, VIA_SIZE, VIA_PITCH)
    c.add_polygon(_arc_points(radius - M1_GAP, 0, 360)[:-1], layer=t.M1)  # inner disc
    c.add_polygon(_sector(radius + M1_GAP, radius + M1_GAP + M1_WIDTH, a0, a1), layer=t.M1)  # outer arc

    for centre in DISC_VIAS:  # via 1 on the disc: 3 x 3
        c.add_polygon(_square(centre, VIA1_SIZE), layer=t.VIA1)
    c.add_port("S", center=(0, 0), width=TRACE, orientation=90, layer=t.M2, port_type="electrical")
    r_mid = radius + M1_GAP + M1_WIDTH / 2
    for name, angle in ELECTRODE_ANGLES.items():
        for centre, rotation in _electrode_vias(radius, angle):  # via 1 on the arc: a row of three
            c.add_polygon(_square(centre, VIA1_SIZE, rotation), layer=t.VIA1)
        c.add_port(name, center=tuple(_polar(r_mid, angle)), width=TRACE, orientation=90, layer=t.M2, port_type="electrical")
    return c


@gf.cell
def heater(radius: float = 10.0, heater_angle: float = 270.0) -> gf.Component:
    """TiN heater: an arc above the waveguide core, ``heater_angle`` degrees centred on north.

    Each end widens into a landing that reaches outwards, where via 1 connects it to metal 2.
    Ports H1 (west) and H2 (east) sit on the via 1 of the landings.
    """
    _, _, h0, h1 = _angles(0, heater_angle)
    c = gf.Component()
    c.add_polygon(_sector(radius - HEATER_WIDTH / 2, radius + HEATER_WIDTH / 2, h0, h1), layer=t.HEATER)
    r0, r1 = radius - HEATER_WIDTH / 2, radius + LANDING_REACH
    r_via = r1 - 0.4 - VIA1_SIZE / 2  # 0.4 um of heater film beyond the via
    for name, angle in (("H1", h1), ("H2", h0)):
        c.add_polygon(_box(_polar((r0 + r1) / 2, angle), r1 - r0, LANDING, angle), layer=t.HEATER)
        c.add_polygon(_square(_polar(r_via, angle), VIA1_SIZE, angle), layer=t.VIA1)
        c.add_port(name, center=tuple(_polar(r_via, angle)), width=TRACE, orientation=270, layer=t.M2, port_type="electrical")
    return c


def _pad(c: gf.Component, xy: tuple[float, float], size: float) -> tuple[float, float]:
    """Pad (metal 3 + opening) with a tab on the side that faces the ring, where metal 2 comes up through a row of via 2.

    Returns the point in the middle of the tab, where the metal 2 wire ends.
    """
    px, py = xy
    (c << t.pad(size=size)).dmove(xy)
    side = -1.0 if py > 0 else 1.0  # the tab points towards y = 0
    y_edge = py + side * size / 2
    y_tab = y_edge + side * TAB
    tab = [(px - size / 2, y_edge), (px + size / 2, y_edge), (px + size / 2, y_tab), (px - size / 2, y_tab)]
    c.add_polygon(tab, layer=t.M3)
    c.add_polygon(tab, layer=t.M2)
    count = int((size - 2 * VIA2_SIZE) // VIA2_PITCH) + 1
    x0 = px - (count - 1) * VIA2_PITCH / 2
    for k in range(count):
        c.add_polygon(_square((x0 + k * VIA2_PITCH, (y_edge + y_tab) / 2), VIA2_SIZE), layer=t.VIA2)
    return px, (y_edge + y_tab) / 2


def _unit(p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
    """Unit step (sign of each component) from p to q, for a horizontal or vertical segment."""
    return float(np.sign(q[0] - p[0])), float(np.sign(q[1] - p[1]))


def _reach_beyond(start: tuple[float, float], travel: tuple[float, float], squares: list) -> float:
    """How far metal 2 must run beyond start, backwards from travel, to enclose every via 1 square.

    squares: the corner points of each via 1 (rotated squares included).  The farthest corner behind the
    start sets the reach: the metal must extend past it by via1_enclosure_by_m2 plus ENCLOSURE_MARGIN.
    Corners ahead of the start lie on the wire itself.
    """
    behind = [-((x - start[0]) * travel[0] + (y - start[1]) * travel[1]) for square in squares for x, y in square]
    return max([0.0, *behind]) + t.DESIGN_RULES["via1_enclosure_by_m2"] + ENCLOSURE_MARGIN


def _wire(
    c: gf.Component, points: list[tuple[float, float]], start_reach: float, end_reach: float = 0.0, width: float = TRACE
) -> None:
    """Metal 2 wire through points: one path of constant width with square corners.

    Each segment is a rectangle.  At a corner both segments run width / 2 past the corner, which makes the
    outer corner square and leaves no notch.  The two free ends do not run past the width: start_reach and
    end_reach say how far the metal goes beyond the first and the last point (see _reach_beyond).
    """
    h = width / 2
    last = len(points) - 2
    for i, ((x0, y0), (x1, y1)) in enumerate(itertools.pairwise(points)):
        if abs(x1 - x0) > 1e-9 and abs(y1 - y0) > 1e-9:
            raise ValueError("a wire segment must be horizontal or vertical")
        if abs(x1 - x0) < 1e-9 and abs(y1 - y0) < 1e-9:
            raise ValueError("a wire segment must have a length")
        ux, uy = _unit((x0, y0), (x1, y1))
        before = start_reach if i == 0 else h
        after = end_reach if i == last else h
        ax, ay = x0 - ux * before, y0 - uy * before  # the segment, extended backwards at its start
        bx, by = x1 + ux * after, y1 + uy * after  # and forwards at its end
        if uy == 0:  # horizontal
            left, bottom, right, top = min(ax, bx), y0 - h, max(ax, bx), y0 + h
        else:  # vertical
            left, bottom, right, top = x0 - h, min(ay, by), x0 + h, max(ay, by)
        c.add_polygon([(left, bottom), (right, bottom), (right, top), (left, top)], layer=t.M2)


# =====================================================================================
# device
# =====================================================================================
@gf.cell
def ring_modulator(
    radius: float = 10.0,
    width: float = 0.5,
    gap: float = 0.37,
    pn_angle: float = 240.0,
    heater_angle: float = 270.0,
    p_inside: bool = False,
    bus_length: float = 120.0,
    pad_size: float = 80.0,
    pad_pitch: float = 100.0,
    pad_distance: float = 95.0,
) -> gf.Component:
    """Microring modulator with a PN depletion section and a TiN heater.

    Args:
        radius: ring radius (um).
        width: core width of ring and bus (um).
        gap: edge-to-edge gap between ring and bus cores (um).  The default is the gap for critical
            coupling found by step 6 of lumerical_simulations/ring_modulator.
        pn_angle: angle of the doped arc, centred on north (deg).
        heater_angle: angle of the heater arc, centred on north (deg); larger than ``pn_angle``,
            so that the heater landings lie beyond the ends of the outer electrode.
        p_inside: False puts n (signal) inside the ring and p (ground) outside.
        bus_length: length of the bus waveguide; the optical ports o1 / o2 are at its ends (um).
        pad_size / pad_pitch / pad_distance: pad edge length, pitch within a row, and distance of
            the pad centres from the ring centre (um).

    Electrical ports: G1, S, G2 (PN junction, north) and H1, H2 (heater, south).  They mark where the wiring
    goes.  Their orientations are fixed in the code and do not turn to the via positions, and no tool routes them.
    ``info`` stores the lengths the simulations need: ring, doped arc, free heater filament.
    """
    a0, _, h0, _ = _angles(pn_angle, heater_angle)
    spacing = t.DESIGN_RULES["m1_to_heater"]
    if radius < t.DESIGN_RULES["rib_bend_radius"]:
        raise ValueError(
            f"radius {radius} um is below the rib bend radius, {t.DESIGN_RULES['rib_bend_radius']} um "
            "(gsip_technology.DESIGN_RULES['rib_bend_radius'])"
        )
    r_m1 = radius + M1_GAP
    clearance = math.radians(a0 - h0) * r_m1 - LANDING / 2  # outer electrode end <-> heater landing
    if clearance < spacing + 0.2:
        raise ValueError(
            f"heater_angle must exceed pn_angle by more: {clearance:.2f} um between the outer electrode and "
            f"a heater landing, need {spacing + 0.2:.2f} um"
        )
    if gap < t.MIN_WIDTH_SPACE["WG"][1]:
        raise ValueError(f"gap {gap} um is below the minimum space of the waveguide layer")
    y_bus = -(radius + width + gap)
    # the heater as drawn, both landings included, against the top edge of the bus core
    lowest = _lowest_y(heater(radius=radius, heater_angle=heater_angle), t.HEATER)
    bus_top = y_bus + width / 2
    rule = t.DESIGN_RULES["heater_to_waveguide"]
    if lowest - bus_top < rule:
        raise ValueError(
            f"the clearance between the heater and the bus core is {lowest - bus_top:.2f} um, the rule needs "
            f"{rule:.2f} um: the lowest point of the heater (heater_angle {heater_angle}, radius {radius}) is at "
            f"y = {lowest:.2f} um, and the top of the bus core, set by the radius and the gap {gap} um, is at "
            f"y = {bus_top:.2f} um"
        )

    c = gf.Component()
    c << ring(radius=radius, width=width, pn_angle=pn_angle, p_inside=p_inside)
    b = c << bus(length=bus_length, width=width)
    b.dmovey(y_bus)
    e = c << pn_contacts(radius=radius, pn_angle=pn_angle)
    h = c << heater(radius=radius, heater_angle=heater_angle)

    # ---- pads (metal 3) and traces (metal 2): G1 S G2 in the north, H1 H2 in the south ----
    pads = {
        "G1": (-pad_pitch, pad_distance),
        "S": (0.0, pad_distance),
        "G2": (pad_pitch, pad_distance),
        "H1": (-pad_pitch / 2, -pad_distance),
        "H2": (pad_pitch / 2, -pad_distance),
    }
    y_jog = (y_bus - pad_distance + pad_size / 2 + TAB) / 2  # half-way between the bus and the heater pads
    for name, xy in pads.items():
        end = _pad(c, xy, pad_size)
        x, y = (e if name in e.ports else h).ports[name].center
        if name == "S":  # straight up from the middle of the disc; it crosses heater and metal 1 on metal 2
            points = [(x, y), end]
            vias = [_square(centre, VIA1_SIZE) for centre in DISC_VIAS]
        elif name in ELECTRODE_ANGLES:  # sideways above the outer electrode, then up
            points = [(x, y), (end[0], y), end]
            vias = [_square(centre, VIA1_SIZE, rot) for centre, rot in _electrode_vias(radius, ELECTRODE_ANGLES[name])]
        else:  # heater: straight down across the bus, sideways, then down to the pad
            points = [(x, y), (x, y_jog), (end[0], y_jog), end]
            vias = [_square((x, y), VIA1_SIZE, math.degrees(math.atan2(y, x)))]  # the via turns with its landing
        # the wire leaves its via 1 (or the row of them) with just enough metal to enclose it; the pad end
        # stops in the middle of the pad tab, where the row of via 2 sits
        _wire(c, points, start_reach=_reach_beyond((x, y), _unit(points[0], points[1]), vias))
        c.add_port(name, center=xy, width=pad_size, orientation=90 if xy[1] > 0 else 270, layer=t.M3, port_type="electrical")
    c.add_ports(b.ports)

    # ring slab and bus slab overlap around the coupler: fill the wedges between them and merge
    for fillet in _slab_fillets(radius, y_bus):
        c.add_polygon(fillet, layer=t.SLAB90)
    c.flatten()
    slab = c.get_region(t.SLAB90, merge=True)
    c.remove_layers([t.SLAB90])
    c.add_polygon(slab, layer=t.SLAB90)

    circumference = 2 * math.pi * radius
    c.info["radius"] = radius
    c.info["width"] = width
    c.info["gap"] = gap
    c.info["length_ring"] = round(circumference, 3)
    c.info["length_pn"] = round(circumference * pn_angle / 360, 3)
    # each landing covers half its width at an end of the arc; what is left is the part that heats
    c.info["length_heater"] = round(circumference * heater_angle / 360 - LANDING, 3)
    return c


# =====================================================================================
# preview images (headless KLayout, colours of the PDK's layers.lyp)
# =====================================================================================
def render_png(
    gds_path: Path, png_path: Path, box: tuple[float, float, float, float] | None = None, size: tuple[int, int] = (1600, 1200)
) -> Path:
    import klayout.lay as lay

    lyp = Path(__file__).resolve().parent / "klayout_tech" / "layers.lyp"
    if not lyp.exists():
        t.write_klayout_tech(lyp.parent)
    view = lay.LayoutView()
    view.load_layout(str(gds_path), True)
    view.load_layer_props(str(lyp))
    view.max_hier()
    view.zoom_box(gf.kdb.DBox(*box)) if box else view.zoom_fit()
    view.save_image(str(png_path), *size)
    return png_path


if __name__ == "__main__":
    from gsip_drc import run_drc

    here = Path(__file__).resolve().parent
    device = ring_modulator()
    gds = t.write_gds_for_lumerical(device, here / "rm_ring.gds", cellname="rm_ring")
    info = device.info
    print(
        f"GDS -> {gds.name}   ring {info['length_ring']} um, PN section {info['length_pn']} um, "
        f"heater {info['length_heater']} um   ports: {[p.name for p in device.ports]}"
    )
    result = run_drc(device, rdb_path=here / "rm_ring_drc.lyrdb")
    print(result.summary())
    build = here / "build"
    build.mkdir(exist_ok=True)
    render_png(gds, build / "rm_ring_klayout.png")
    render_png(gds, build / "rm_ring_klayout_zoom.png", box=(-22, -18, 22, 20))
    sys.exit(0 if result.passed else 1)

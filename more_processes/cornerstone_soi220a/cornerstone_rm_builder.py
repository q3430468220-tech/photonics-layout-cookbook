"""Heater-tuned microring modulator on CORNERSTONE SOI220A, ready for the Lumerical Layer Builder.

                 [G1]      [S]      [G2]            north: GSG pads of the PN junction
                    \\       |       /                      S -> inside of the ring (n), G -> outside (p)
                     \\   .--|--.   /
                      \\ /   |   \\ /                 PN section: the upper 240 deg of the ring
                       |    (o)    |
                        \\         /
          o1 ============`-.___.-'============ o2    bus (rib waveguide), point coupler at the bottom
                          /  ~~~  \\                  heater: Al filament above the lower 76 deg of the ring
                       [H1]       [H2]              south: heater pads

SOI220A has one metal layer.  The PN electrodes and the heater therefore share the Al layer (GDS 13)
and cannot overlap: the PN section takes the upper part of the ring and the heater sits above the
undoped part next to the coupler.

    optics       ring()          closed rib ring + the implants of the PDK cross-section rib_1550nm_TE_pn
                 bus()           straight rib bus waveguide
    electrics    pn_contacts()   vias and electrodes of the junction (inner disc = S, two outer arcs = G)
                 heater()        filament and the two leads
    device       ring_modulator()  assembles them, adds pads and traces

All cross-sections, layers and design rules come from cornerstone_technology.py.

    python cornerstone_rm_builder.py     ->  rm_ring.gds (flat, for the Layer Builder), DRC report, preview images
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gdsfactory as gf

import cornerstone_technology as t

# ---- dimensions (um), chosen from the design rules in cornerstone_technology.py ----
SLAB_WIDTH = 14.0  # slab of the ring; wide enough for the contacts on both sides
VIA_GAP = 2.6  # core centre -> near edge of the via ([MZM]: 2.5)
VIA_WIDTH = 3.05  # rule: >= 3
METAL_GAP = 2.05  # core centre -> near edge of the PN electrodes; 2 x 2.05 = 4.1 >= 4 (electrode gap)
METAL_WIDTH = 6.55  # width of the outer electrode arcs; rule: >= 6
VIA_END_MARGIN = 1.0  # via pulled back from the ends of the doped arc (enclosure rule: 0.5)
S_TRACE_WIDTH = 10.0  # signal trace that leaves the ring between the two ground arcs
HEATER_WIDTH = t.DESIGN_RULES["heater_filament_width"]
LEAD_WIDTH = 6.5  # heater leads; rule: >= 6
LEAD_LENGTH = 15.0  # radial part of a heater lead
INNER_DISC_GAP = 6.0  # inner electrode stays this far inside the core under the heater
SLAB_CLOSE = 0.3  # closing radius that removes sub-rule slivers where ring slab and bus slab meet
ARC_STEP_DEG = 0.5  # polygon resolution of every arc
ELECTRODE_GAP = t.MIN_WIDTH_SPACE["ELECTRODE_LF"][1]


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


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _close(region: gf.kdb.Region, radius: float) -> gf.kdb.Region:
    """Morphological closing: fills gaps narrower than 2 x radius, then drops the 1-2 nm jogs it leaves."""
    d = round(radius / gf.kcl.dbu)
    return region.merged().sized(d, 2).merged().sized(-d, 2).merged().smoothed(2)


def _angles(pn_angle: float, heater_angle: float) -> tuple[float, float, float, float]:
    """Start / end angle of the PN section (around north) and of the heater (around south)."""
    return 90 - pn_angle / 2, 90 + pn_angle / 2, 270 - heater_angle / 2, 270 + heater_angle / 2


# =====================================================================================
# optics
# =====================================================================================
@gf.cell
def ring(radius: float = 25.0, width: float = 0.45, pn_angle: float = 240.0, p_inside: bool = False) -> gf.Component:
    """Closed rib ring; the arc of ``pn_angle`` degrees around north carries the junction implants.

    The ring is extruded once as a closed path so that core and slab have no seam.  Of the doped
    cross-section only the implant layers are added on top.
    """
    a0, a1, _, _ = _angles(pn_angle, 0)
    c = gf.Component()
    passive = gf.get_cross_section("rib_1550nm_TE", width=width, width_slab=SLAB_WIDTH, radius=radius)
    # the path overlaps itself by 1 deg and the result is merged, which removes the seam of a closed ring
    loop = gf.path.extrude(gf.Path(_arc_points(radius, 269.5, 630.5)), cross_section=passive)
    for layer in (t.CORE, t.SLAB):
        c.add_polygon(loop.get_region(layer, merge=True), layer=layer)
    doped = gf.get_cross_section("rib_1550nm_TE_pn", width=width, width_slab=SLAB_WIDTH, radius=radius, p_inside=p_inside)
    arc = gf.path.extrude(gf.Path(_arc_points(radius, a0, a1)), cross_section=doped)
    p_low = arc.get_region(t.P_LOW, merge=True)
    c.add_polygon(p_low, layer=t.P_LOW)
    for layer in (t.N_LOW, t.P_HI, t.N_HI):
        # clipped to the background p implant: the end faces of two extruded sections can differ by 1 nm
        c.add_polygon(arc.get_region(layer, merge=True) & p_low, layer=layer)
    return c


@gf.cell
def bus(length: float = 300.0, width: float = 0.45) -> gf.Component:
    """Straight rib bus waveguide centred on the origin; ports o1 (west) and o2 (east)."""
    c = gf.Component()
    ref = c << gf.components.straight(length=length, cross_section=gf.get_cross_section("rib_1550nm_TE", width=width))
    ref.dmovex(-length / 2)
    c.add_ports(ref.ports)
    return c


# =====================================================================================
# electrics
# =====================================================================================
@gf.cell
def pn_contacts(radius: float = 25.0, pn_angle: float = 240.0, heater_angle: float = 76.0) -> gf.Component:
    """Vias and electrodes of the PN section.

    Inside the ring: one via band and one electrode that fills the ring.  Under the heater the
    electrode retreats to a smaller disc so that it keeps the electrode gap to the filament.
    Outside: a via band and an electrode arc on each side of the signal trace (G1 west, G2 east).
    Ports (on the electrode layer): S at the ring centre, G1 / G2 at the middle of the outer arcs.
    """
    a0, a1, _, _ = _angles(pn_angle, heater_angle)
    r_in, r_out = radius - VIA_GAP, radius + VIA_GAP  # near edges of the two via bands
    c = gf.Component()

    # inner side: via band, then an electrode made of a sector (PN section) and a disc (the rest)
    d_in = math.degrees(VIA_END_MARGIN / (r_in - VIA_WIDTH))
    c.add_polygon(_sector(r_in - VIA_WIDTH, r_in, a0 + d_in, a1 - d_in), layer=t.VIA)
    disc = radius - INNER_DISC_GAP
    c.add_polygon(np.vstack([_arc_points(radius - METAL_GAP, a0, a1), _arc_points(disc, a1, a0 + 360)]), layer=t.METAL)

    # outer side: the signal trace leaves through the gap between the two ground arcs
    r_m = radius + METAL_GAP
    half_gap = math.degrees(math.asin((S_TRACE_WIDTH / 2 + ELECTRODE_GAP + 0.5) / r_m))
    d_out = math.degrees(VIA_END_MARGIN / r_out)
    for name, b0, b1 in (("G2", a0, 90 - half_gap), ("G1", 90 + half_gap, a1)):
        c.add_polygon(_sector(r_out, r_out + VIA_WIDTH, b0 + d_out, b1 - d_out), layer=t.VIA)
        c.add_polygon(_sector(r_m, r_m + METAL_WIDTH, b0, b1), layer=t.METAL)
        mid = _polar(r_m + METAL_WIDTH / 2, (b0 + b1) / 2)
        c.add_port(name, center=tuple(mid), width=METAL_WIDTH, orientation=90, layer=t.METAL, port_type="electrical")
    c.add_port("S", center=(0, 0), width=S_TRACE_WIDTH, orientation=90, layer=t.METAL, port_type="electrical")
    return c


@gf.cell
def heater(radius: float = 25.0, heater_angle: float = 76.0) -> gf.Component:
    """Al heater: a 2 um filament above the core over ``heater_angle`` degrees around south.

    Each end continues into a radial lead (perpendicular to the filament, so no acute notch).  A lead is
    centred on the filament end and covers LEAD_WIDTH / 2 of it.
    Ports H1 (west) and H2 (east) sit at the outer ends of the leads.
    """
    _, _, h0, h1 = _angles(0, heater_angle)
    c = gf.Component()
    c.add_polygon(_sector(radius - HEATER_WIDTH / 2, radius + HEATER_WIDTH / 2, h0, h1), layer=t.METAL)
    for name, a in (("H1", h0), ("H2", h1)):  # each lead is centred on a filament end and covers it completely
        u = _polar(1.0, a)  # radial unit vector
        v = np.array([-u[1], u[0]])  # tangential unit vector
        p0, p1 = u * (radius - HEATER_WIDTH / 2), u * (radius + LEAD_LENGTH)
        w = v * LEAD_WIDTH / 2
        c.add_polygon([p0 - w, p0 + w, p1 + w, p1 - w], layer=t.METAL)
        c.add_port(name, center=tuple(p1), width=LEAD_WIDTH, orientation=a, layer=t.METAL, port_type="electrical")
    return c


def _trace(c: gf.Component, pad_xy: tuple[float, float], pad_size: float, a: np.ndarray, b: np.ndarray) -> None:
    """Trapezoid in the electrode layer from the segment a-b to the facing edge of a pad."""
    px, py = pad_xy
    y_edge = py - math.copysign(pad_size / 2, py)  # the pad edge that faces the ring
    corners = [(px - pad_size / 2, y_edge), (px + pad_size / 2, y_edge)]
    lo, hi = sorted((tuple(a), tuple(b)))
    order = [lo, hi, corners[1], corners[0]] if py > 0 else [corners[0], corners[1], hi, lo]
    c.add_polygon(order, layer=t.METAL)


# =====================================================================================
# device
# =====================================================================================
@gf.cell
def ring_modulator(
    radius: float = 25.0,
    width: float = 0.45,
    gap: float = 0.42,
    pn_angle: float = 240.0,
    heater_angle: float = 76.0,
    p_inside: bool = False,
    bus_length: float = 300.0,
    pad_size: float = 80.0,
    pad_pitch: float = 100.0,
    pad_distance: float = 115.0,
) -> gf.Component:
    """Microring modulator with a PN depletion section and an Al heater.

    Args:
        radius: ring radius (um).  The official rib cross-section allows >= 25.
        width: core width of ring and bus (um).
        gap: edge-to-edge gap between ring and bus cores (um), >= 0.2.  The default is the gap for critical
            coupling found by step 6 of lumerical_simulations/ring_modulator.
        pn_angle: angle of the doped arc, centred on north (deg).
        heater_angle: angle of the heater filament, centred on south above the coupler (deg).
        p_inside: False puts n (signal) inside the ring and p (ground) outside.
        bus_length: length of the bus waveguide; the optical ports o1 / o2 are at its ends (um).
        pad_size / pad_pitch / pad_distance: pad edge length, pitch within a row, and distance of
            the pad centres from the ring centre (um).

    Electrical ports: G1, S, G2 (PN junction, north) and H1, H2 (heater, south).
    ``info`` stores the lengths the simulations need: ring, doped arc, and the free heater filament
    between its two leads.
    """
    _, a1, h0, _ = _angles(pn_angle, heater_angle)
    clearance = math.radians(h0 - a1) * (radius - METAL_GAP) - LEAD_WIDTH / 2  # leads are centred on the filament ends
    if clearance < ELECTRODE_GAP + 0.5:
        raise ValueError(
            f"pn_angle + heater_angle too large: {clearance:.1f} um between the PN electrodes and the heater "
            f"leads, need {ELECTRODE_GAP + 0.5} um"
        )
    if gap < t.MIN_WIDTH_SPACE["SI_ETCH2_LF_120NM"][1]:
        raise ValueError(f"gap {gap} um is below the minimum gap of the waveguide layer")

    c = gf.Component()
    c << ring(radius=radius, width=width, pn_angle=pn_angle, p_inside=p_inside)
    b = c << bus(length=bus_length, width=width)
    b.dmovey(-(radius + width + gap))
    e = c << pn_contacts(radius=radius, pn_angle=pn_angle, heater_angle=heater_angle)
    h = c << heater(radius=radius, heater_angle=heater_angle)

    # ---- pads and traces: G1 S G2 in the north, H1 H2 in the south ----
    pads = {
        "G1": (-pad_pitch, pad_distance),
        "S": (0.0, pad_distance),
        "G2": (pad_pitch, pad_distance),
        "H1": (-pad_pitch / 2, -pad_distance),
        "H2": (pad_pitch / 2, -pad_distance),
    }
    for name, xy in pads.items():
        (c << t.pad(size=pad_size)).dmove(xy)
        c.add_port(name, center=xy, width=pad_size, orientation=90 if xy[1] > 0 else 270, layer=t.METAL, port_type="electrical")
    c.add_polygon(_rect(-S_TRACE_WIDTH / 2, 0, S_TRACE_WIDTH / 2, pad_distance - pad_size / 2), layer=t.METAL)
    r_mid = radius + METAL_GAP + METAL_WIDTH / 2
    for name in ("G1", "G2"):
        ang = math.degrees(math.atan2(*e.ports[name].center[::-1]))  # middle of the ground arc
        _trace(c, pads[name], pad_size, _polar(r_mid, ang - 14), _polar(r_mid, ang + 14))
    for name in ("H1", "H2"):
        p = h.ports[name]
        u = _polar(1.0, p.orientation)
        w = np.array([-u[1], u[0]]) * LEAD_WIDTH / 2
        centre = np.array(p.center) - u * 1.0  # overlap the lead by 1 um
        _trace(c, pads[name], pad_size, centre - w, centre + w)
    c.add_ports(b.ports)

    # ring slab and bus slab meet at a shallow angle: merge them and close the slivers
    c.flatten()
    slab = _close(c.get_region(t.SLAB, merge=True), SLAB_CLOSE)
    c.remove_layers([t.SLAB])
    c.add_polygon(slab, layer=t.SLAB)

    circumference = 2 * math.pi * radius
    c.info["radius"] = radius
    c.info["width"] = width
    c.info["gap"] = gap
    c.info["length_ring"] = round(circumference, 3)
    c.info["length_pn"] = round(circumference * pn_angle / 360, 3)
    # the leads cover half their width at each end of the filament; what is left is the part that heats
    c.info["length_heater"] = round(circumference * heater_angle / 360 - LEAD_WIDTH, 3)
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
    from cornerstone_drc import run_drc

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
    assets = here / "assets"
    assets.mkdir(exist_ok=True)
    render_png(gds, assets / "rm_ring.png")
    render_png(gds, assets / "rm_ring_zoom.png", box=(-45, -45, 45, 45))
    sys.exit(0 if result.passed else 1)

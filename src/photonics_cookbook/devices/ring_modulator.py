"""Doped silicon microring modulator (MRM): all-pass ring, lateral PN junction, GSG pads.

Topology follows the Ansys Lumerical *Ring Modulator* application example
(https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator): a rib
ring of radius 10 um side-coupled to a bus, with a lateral PN depletion junction
along most of the circumference. Use the same in-plane numbers as the example so
you can cross-check your CHARGE / FDE / INTERCONNECT results with the official
files; the vertical stack (slab thickness, cladding) and the doses come from the
*process* file, which is exactly what changes from foundry to foundry.

Top view (not to scale)::

        G pad          S pad          G pad
          \\             |              /
           \\  (outer   bridge    outer) /
            \\  metal)   |      (metal)/
             ( P++ | P | core | N | N++ )   <- radial cross-section = CHARGE cut
                   \\_____ring_____/
      o1 =============== bus ================ o2

Signal (S) contacts the inner N side, both grounds (G) the outer P side, so a
positive S voltage reverse-biases the junction (inner/outer can be flipped with
``inner_dopant``).
"""

from __future__ import annotations

import math

import numpy as np

from photonics_cookbook.geometry import (
    Geometry,
    PortSpec,
    annulus,
    arc_band,
    polar,
    polygon_area,
    rect,
    snap,
)
from photonics_cookbook.process import Process


def _role(process: Process, role: str) -> str | None:
    return role if process.has(role) else None


def ring_modulator_geometry(
    process: Process,
    radius: float = 10.0,
    width: float = 0.5,
    gap: float = 0.2,
    junction_offset: float = 0.0,
    inner_dopant: str = "n",
    contact_spacing: float = 0.8,
    contact_width: float = 2.0,
    mid_spacing: float = 0.4,
    implant_overlap: float = 0.2,
    via_enclosure: float = 0.5,
    slab_margin: float = 0.5,
    bus_slab_margin: float = 2.0,
    bus_extension: float = 5.0,
    coupler_clearance: float = 1.5,
    coupler_window_deg: float = 30.0,
    bridge_width: float = 4.0,
    metal_spacing: float = 3.0,
    with_pads: bool = True,
    pad_size: float = 80.0,
    pad_pitch: float = 100.0,
    pad_offset: float = 30.0,
    cut_angle_deg: float = 0.0,
    name: str = "ring_modulator",
) -> Geometry:
    """Draw the ring modulator as role-tagged polygons (all lengths in um).

    Args:
        process: foundry process (roles -> GDS layers). Optional roles that the process
            does not define (e.g. medium-dose ``np``/``pp``) are simply not drawn.
        radius: ring radius at the waveguide centre line.
        width: rib (core) width of ring and bus.
        gap: edge-to-edge gap between bus and ring cores.
        junction_offset: radial offset of the PN junction from the waveguide centre
            (+ = towards the outside). Must stay inside the core.
        inner_dopant: ``"n"`` (default, N inside / P outside) or ``"p"``.
        contact_spacing: core edge -> heavily doped (++) region edge.
        contact_width: radial width of each ++ region (= metal band width).
        mid_spacing: core edge -> medium-dose (N+/P+) edge, used only if the process
            has ``np``/``pp`` layers.
        implant_overlap: how far low/medium implants extend under the ++ region.
        via_enclosure: ++ (and metal) enclosure of the vias.
        slab_margin: slab extension beyond the outer edge of the ++ regions.
        bus_slab_margin: slab half-width beyond the bus core edges.
        bus_extension: straight bus length beyond the ring slab on each side.
        coupler_clearance: min. distance between doping/metal and the bus core edge;
            sets the undoped window around the coupling point automatically.
        coupler_window_deg: lower bound of that window's half-angle.
        bridge_width: width of the metal bridge from the inner contact to the S pad.
        metal_spacing: min. metal-to-metal spacing (sets the gap in the outer contact).
        with_pads: add a GSG pad row (pitch ``pad_pitch``) above the ring.
        pad_size: square pad size.
        pad_pitch: GSG pitch.
        pad_offset: distance between the ring slab and the pad row.
        cut_angle_deg: polar angle of the suggested radial cut for CHARGE / FDE.
        name: geometry name.
    """
    # ------------------------------------------------------------ validation
    if inner_dopant not in ("n", "p"):
        raise ValueError("inner_dopant must be 'n' or 'p'")
    if not (0 < width < radius) or gap <= 0:
        raise ValueError("need 0 < width < radius and gap > 0")
    if abs(junction_offset) >= width / 2:
        raise ValueError("junction_offset must lie inside the core (|offset| < width/2)")
    if contact_width <= 2 * via_enclosure:
        raise ValueError("contact_width must exceed 2 * via_enclosure")
    if process.has("np") or process.has("pp"):
        if not (0 < mid_spacing < contact_spacing):
            raise ValueError("need 0 < mid_spacing < contact_spacing")

    R, w = radius, width
    outer_dopant = "p" if inner_dopant == "n" else "n"
    low = {"in": _role(process, inner_dopant), "out": _role(process, outer_dopant)}
    mid = {"in": _role(process, inner_dopant + "p"), "out": _role(process, outer_dopant + "p")}
    high = {"in": _role(process, inner_dopant + "pp"), "out": _role(process, outer_dopant + "pp")}
    has_slab = process.has("slab")
    has_via = process.has("via")
    has_metal = process.has("metal")

    # ------------------------------------------------------------ radii
    r_ci, r_co = R - w / 2, R + w / 2  # core edges
    r_j = R + junction_offset  # metallurgical junction
    r_o0, r_o1 = r_co + contact_spacing, r_co + contact_spacing + contact_width  # outer ++
    r_i1, r_i0 = r_ci - contact_spacing, r_ci - contact_spacing - contact_width  # inner ++
    r_slab_in, r_slab_out = r_i0 - slab_margin, r_o1 + slab_margin
    if r_slab_in < 1.0:
        raise ValueError(
            f"radius {R} um is too small for an inner contact of {contact_width} um at "
            f"{contact_spacing} um from the core (inner slab radius would be {r_slab_in:.2f} um)"
        )

    # ------------------------------------------------------------ angles
    y_bus = -(R + gap + w)  # bus centre line (ring centre at the origin)
    bus_top = y_bus + w / 2
    arg = (abs(bus_top) - coupler_clearance) / r_o1
    theta_c_geo = math.degrees(math.acos(min(1.0, max(-1.0, arg))))
    theta_c = max(coupler_window_deg, theta_c_geo)  # half-angle of the undoped coupler window
    th_a, th_b = -90.0 + theta_c, 270.0 - theta_c  # doped arc (counter-clockwise)
    theta_m = math.degrees(math.asin(min(1.0, (bridge_width / 2 + metal_spacing) / r_o0)))
    if th_a > 90.0 - theta_m - 10.0:
        raise ValueError("coupler window and bridge gap leave no room for the outer contact")
    if not (th_a < cut_angle_deg < 90.0 - theta_m) and not (90.0 + theta_m < cut_angle_deg < th_b):
        raise ValueError(f"cut_angle_deg={cut_angle_deg} is not inside the contacted doped arc")

    g = Geometry(name=name)

    # ------------------------------------------------------------ waveguides
    g.add("core", annulus(r_ci, r_co))
    if has_slab:
        g.add("slab", annulus(r_slab_in, r_slab_out))
    x_bus = r_slab_out + bus_extension
    g.add("core", rect(-x_bus, y_bus - w / 2, x_bus, y_bus + w / 2))
    if has_slab:
        hw = w / 2 + bus_slab_margin
        g.add("slab", rect(-x_bus, y_bus - hw, x_bus, y_bus + hw))

    # ------------------------------------------------------------ implants
    if low["out"]:
        g.add(low["out"], arc_band(r_j, r_o0 + implant_overlap, th_a, th_b))
    if low["in"]:
        g.add(low["in"], arc_band(r_i1 - implant_overlap, r_j, th_a, th_b))
    if mid["out"]:
        g.add(mid["out"], arc_band(r_co + mid_spacing, r_o0 + implant_overlap, th_a, th_b))
    if mid["in"]:
        g.add(mid["in"], arc_band(r_i1 - implant_overlap, r_ci - mid_spacing, th_a, th_b))
    if high["out"]:
        g.add(high["out"], arc_band(r_o0, r_o1, th_a, th_b))
    if high["in"]:
        g.add(high["in"], arc_band(r_i0, r_i1, th_a, th_b))

    # ------------------------------------------------------------ contacts
    outer_arcs = [(th_a, 90.0 - theta_m), (90.0 + theta_m, th_b)]  # split for the S bridge
    if has_via:
        rv_o0, rv_o1 = r_o0 + via_enclosure, r_o1 - via_enclosure
        rv_i0, rv_i1 = r_i0 + via_enclosure, r_i1 - via_enclosure
        d_o = math.degrees(via_enclosure / rv_o0)
        d_i = math.degrees(via_enclosure / rv_i0)
        g.add("via", arc_band(rv_i0, rv_i1, th_a + d_i, th_b - d_i))
        for a0, a1 in outer_arcs:
            g.add("via", arc_band(rv_o0, rv_o1, a0 + d_o, a1 - d_o))

    r_f = 0.5 * (r_o0 + r_o1)  # outer metal mid radius (route feet)
    phi = 45.0 if th_a + 10 < 45.0 < 90.0 - theta_m - 10 else 0.5 * (th_a + 90.0 - theta_m)
    d_f = math.degrees((bridge_width / 2) / r_f)
    y_pad0 = snap(r_slab_out + pad_offset)
    y_term = y_pad0 if with_pads else snap(r_slab_out + 10.0)
    ports: list[PortSpec] = []

    if has_metal:
        g.add("metal", arc_band(r_i0, r_i1, th_a, th_b))  # inner contact ring
        for a0, a1 in outer_arcs:
            g.add("metal", arc_band(r_o0, r_o1, a0, a1))
        # S bridge: from the inner contact, across the ring (1 um above it), to the S pad
        g.add("metal", rect(-bridge_width / 2, 0.5 * (r_i0 + r_i1), bridge_width / 2, y_term + 1.0))
        if with_pads:
            for xc, pname in ((-pad_pitch, "e1"), (0.0, "e2"), (pad_pitch, "e3")):
                g.add("metal", rect(xc - pad_size / 2, y_pad0, xc + pad_size / 2, y_pad0 + pad_size))
                ports.append(
                    PortSpec(pname, (snap(xc), snap(y_pad0 + pad_size)), pad_size, 90.0, "metal", "electrical")
                )
            # G routes: fan from the outer contact arcs to the G pads
            for sgn in (-1.0, 1.0):
                ang = phi if sgn > 0 else 180.0 - phi
                f1 = polar(r_f, ang - d_f)
                f2 = polar(r_f, ang + d_f)
                xp = sgn * pad_pitch
                pad_r = (xp + pad_size / 2, y_pad0 + 1.0)  # 1 um overlap into the pad
                pad_l = (xp - pad_size / 2, y_pad0 + 1.0)
                g.add("metal", _ccw(np.array([f1, pad_r, pad_l, f2], dtype=float)))
        else:
            for sgn, pname in ((-1.0, "e1"), (1.0, "e3")):
                xf = sgn * r_f * math.cos(math.radians(phi))
                yf = r_f * math.sin(math.radians(phi))
                g.add("metal", rect(xf - bridge_width / 2, yf, xf + bridge_width / 2, y_term))
                ports.append(
                    PortSpec(pname, (snap(xf), snap(y_term)), bridge_width, 90.0, "metal", "electrical")
                )
            ports.append(PortSpec("e2", (0.0, snap(y_term)), bridge_width, 90.0, "metal", "electrical"))

    # ------------------------------------------------------------ optical ports
    ports.insert(0, PortSpec("o1", (snap(-x_bus), snap(y_bus)), w, 180.0, "core", "optical"))
    ports.insert(1, PortSpec("o2", (snap(x_bus), snap(y_bus)), w, 0.0, "core", "optical"))
    g.ports = sorted(ports, key=lambda p: p.name)

    # ------------------------------------------------------------ info for simulation
    doped_angle = th_b - th_a
    c = math.cos(math.radians(cut_angle_deg))
    s = math.sin(math.radians(cut_angle_deg))
    r_cut0, r_cut1 = r_slab_in - 1.0, r_slab_out + 1.0
    anode = high["out"] if outer_dopant == "p" else high["in"]
    cathode = high["in"] if outer_dopant == "p" else high["out"]
    g.info.update(
        radius_um=R,
        width_um=w,
        gap_um=gap,
        inner_dopant=inner_dopant,
        junction_radius_um=r_j,
        coupler_window_half_angle_deg=round(theta_c, 3),
        bridge_gap_half_angle_deg=round(theta_m, 3),
        doped_angle_deg=round(doped_angle, 3),
        doped_length_um=round(R * math.radians(doped_angle), 4),
        slab_radii_um=[round(r_slab_in, 4), round(r_slab_out, 4)],
        contacts={"anode": anode, "cathode": cathode, "signal_port": "e2"},
        lumerical={
            # Radial cut through the doped, contacted part of the ring, from the inside out.
            "cut_p0_um": [round(r_cut0 * c, 4), round(r_cut0 * s, 4)],
            "cut_p1_um": [round(r_cut1 * c, 4), round(r_cut1 * s, 4)],
            "cut_origin_um": [round(R * c, 4), round(R * s, 4)],  # waveguide centre -> x = 0
            "bend_radius_um": R,
            "bend_center_side": "-x",  # ring centre lies towards -x in the cut frame
            "norm_length_um": round(R * math.radians(doped_angle), 4),
            "anode_role": anode,
            "cathode_role": cathode,
        },
    )
    return g


def _ccw(points: np.ndarray) -> np.ndarray:
    """Return the polygon with counter-clockwise orientation."""
    return points if polygon_area(points) > 0 else points[::-1].copy()

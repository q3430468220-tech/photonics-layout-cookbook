"""Lateral PN rib waveguide: the cross-section of a depletion phase shifter.

This is the *pure-geometry* half of the ``rib_pn`` cross-section that the cookbook
PDK registers (see :mod:`photonics_cookbook.pdk.builder`). A gdsfactory
cross-section is nothing more than a list of *sections*: (layer, offset from the
waveguide centre line, width). Keeping that list in plain Python lets us test it,
plot it, and feed the very same numbers to Lumerical.

Cross-section (looking along the waveguide, +y to the left of the propagation
direction, ``flip=False``)::

     -y                                0                                 +y
      |<- slab_margin ->|                                    |<- slab_margin ->|
      [ via ]           |          |<-- w -->|               |           [ via ]
      [  PPP (P++)   ]  |    P     |  core   |      N        |  [  NPP (N++)   ]
      ===================================== SLAB ================================
                         <- contact_spacing ->|  junction at y = junction_offset

Defaults match the cookbook ring modulator (500 nm rib, ++ regions 0.8 um from the
rib, 2 um wide, vias enclosed by 0.5 um), so the straight and the ring share one
CHARGE/FDE cross-section.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from photonics_cookbook.geometry import Geometry, PortSpec, rect, snap
from photonics_cookbook.process import Process, ProcessError

PORT_WIDTH_GRID_UM = 0.002  # port widths must be an even number of 1 nm database units


@dataclass(frozen=True)
class SectionSpec:
    """One gdsfactory ``Section``: a strip of ``role`` at ``offset`` with ``width``."""

    name: str
    role: str
    offset: float
    width: float
    port_names: tuple[str | None, str | None] = (None, None)
    port_types: tuple[str, str] = ("electrical", "electrical")

    @property
    def y0(self) -> float:
        return self.offset - self.width / 2

    @property
    def y1(self) -> float:
        return self.offset + self.width / 2


def _band(name: str, role: str, y0: float, y1: float, **kw) -> SectionSpec:
    if y1 - y0 <= 0:
        raise ValueError(f"section {name!r} would have zero or negative width ({y0} .. {y1})")
    return SectionSpec(name, role, snap(0.5 * (y0 + y1)), snap(y1 - y0), **kw)


def pn_rib_sections(
    process: Process,
    width: float = 0.5,
    junction_offset: float = 0.0,
    contact_spacing: float = 0.8,
    contact_width: float = 2.0,
    via_enclosure: float = 0.5,
    implant_overlap: float = 0.2,
    mid_spacing: float = 0.4,
    slab_margin: float = 0.5,
    flip: bool = False,
) -> list[SectionSpec]:
    """Sections of a lateral PN rib waveguide; the first one is the optical core.

    Args:
        process: foundry process; needs ``core``, ``slab``, ``n``, ``p``. ``npp``/``ppp``,
            ``np``/``pp``, ``via`` and ``metal`` are drawn when the process has them.
        width: rib (core) width.
        junction_offset: PN junction position from the rib centre, towards the N side.
        contact_spacing: rib edge -> P++ / N++ edge.
        contact_width: width of the P++ / N++ (and metal) stripes.
        via_enclosure: ++ enclosure of the via stripes.
        implant_overlap: how far the low-dose implants extend under the ++ stripes.
        mid_spacing: rib edge -> N+ / P+ edge (processes with ``np``/``pp`` only).
        slab_margin: slab extension beyond the ++ stripes.
        flip: put N on the -y side instead of +y.
    """
    for role in ("core", "slab", "n", "p"):
        if not process.has(role):
            raise ProcessError(f"process {process.name!r} has no {role!r} layer -- cannot build a PN rib")
    if not 0 < width:
        raise ValueError("width must be > 0")
    if abs(junction_offset) >= width / 2:
        raise ValueError("junction_offset must lie inside the rib (|offset| < width/2)")
    if contact_width <= 2 * via_enclosure:
        raise ValueError("contact_width must exceed 2 * via_enclosure")
    has_mid = process.has("np") and process.has("pp")
    if has_mid and not 0 < mid_spacing < contact_spacing:
        raise ValueError("need 0 < mid_spacing < contact_spacing")

    w2 = width / 2
    s = -1.0 if flip else 1.0  # sign of the N side
    j = s * junction_offset
    y_pp0 = w2 + contact_spacing  # inner edge of the ++ stripes (distance from centre)
    y_pp1 = y_pp0 + contact_width
    y_low = y_pp0 + implant_overlap
    y_slab = y_pp1 + slab_margin

    def side(lo: float, hi: float, sign: float) -> tuple[float, float]:
        """Band between |y| = lo and hi on the side ``sign``."""
        return (lo, hi) if sign > 0 else (-hi, -lo)

    width_port = snap(round(width / PORT_WIDTH_GRID_UM) * PORT_WIDTH_GRID_UM)
    specs = [SectionSpec("core", "core", 0.0, width_port, ("o1", "o2"), ("optical", "optical"))]
    specs.append(_band("slab", "slab", -y_slab, y_slab))
    # low-dose implants meet at the junction
    if s > 0:
        specs.append(_band("n", "n", j, y_low))
        specs.append(_band("p", "p", -y_low, j))
    else:
        specs.append(_band("n", "n", -y_low, j))
        specs.append(_band("p", "p", j, y_low))
    if has_mid:
        specs.append(_band("np", "np", *side(w2 + mid_spacing, y_low, s)))
        specs.append(_band("pp", "pp", *side(w2 + mid_spacing, y_low, -s)))
    for dop, sign in (("npp", s), ("ppp", -s)):
        if process.has(dop):
            specs.append(_band(dop, dop, *side(y_pp0, y_pp1, sign)))
    if process.has("via"):
        for tag, sign in (("n", s), ("p", -s)):
            specs.append(_band(f"via_{tag}", "via", *side(y_pp0 + via_enclosure, y_pp1 - via_enclosure, sign)))
    if process.has("metal"):
        cw = round(contact_width / PORT_WIDTH_GRID_UM) * PORT_WIDTH_GRID_UM
        for tag, sign in (("n", s), ("p", -s)):
            centre = sign * (y_pp0 + contact_width / 2)
            specs.append(
                SectionSpec(f"metal_{tag}", "metal", snap(centre), snap(cw), (f"{tag}1", f"{tag}2"))
            )
    return specs


def pn_cut_hints(specs: list[SectionSpec], process: Process, x_cut: float, length: float, margin: float = 1.0) -> dict:
    """``info['lumerical']`` for a straight PN waveguide along +x, cut at ``x_cut``."""
    half = max(abs(sp.offset) + sp.width / 2 for sp in specs) + margin
    half = math.ceil(half * 1000) / 1000
    return {
        "cut_p0_um": [round(x_cut, 4), -half],
        "cut_p1_um": [round(x_cut, 4), half],
        "cut_origin_um": [round(x_cut, 4), 0.0],
        "bend_radius_um": None,
        "norm_length_um": round(length, 4),
        "anode_role": "ppp" if process.has("ppp") else "p",
        "cathode_role": "npp" if process.has("npp") else "n",
    }


def pn_straight_geometry(process: Process, length: float = 500.0, **section_kwargs) -> Geometry:
    """Straight PN waveguide (0 <= x <= length) as role-tagged rectangles.

    The gdsfactory cell ``straight_pn`` builds the same thing by *extruding* the
    ``rib_pn`` cross-section along a path; this pure version is used for tests and
    previews.
    """
    if length <= 0:
        raise ValueError("length must be > 0")
    specs = pn_rib_sections(process, **section_kwargs)
    g = Geometry(name="straight_pn")
    for sp in specs:
        g.add(sp.role, rect(0.0, sp.y0, length, sp.y1))
        start, end = sp.port_names
        ptype = sp.port_types[0]
        if start:
            g.ports.append(PortSpec(start, (0.0, sp.offset), sp.width, 180.0, sp.role, ptype))
        if end:
            g.ports.append(PortSpec(end, (snap(length), sp.offset), sp.width, 0.0, sp.role, ptype))
    g.info.update(length_um=length, lumerical=pn_cut_hints(specs, process, length / 2, length))
    return g

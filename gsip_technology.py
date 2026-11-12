"""GSiP teaching process as a gdsfactory technology: the layout half of the foundry-compatible flow.

    gsip_technology.py        layers, design rules, layer stack, cross-sections, cells      (this file)
            |
    rm_builder.py             device layout drawn with the PDK cross-sections   ->  .gds
            |
    gsip_process_file_py/     the same process as CSV tables                    ->  gsip_process.lbr
            |
    lumerical_simulations/    GDS + .lbr in the Layer Builder  ->  FDTD / MODE / CHARGE / HEAT / INTERCONNECT

What this process is
--------------------
A *teaching* process, not a foundry's.  It is the Generic Silicon Photonics (GSiP) process of the
textbook by Chrostowski and Hochberg, in the layer numbering of the open-source gdsfactory generic PDK,
which was derived from the same book and adds a heater layer and a three-metal back end.  A real
foundry gives you these numbers in its PDK, under NDA.  The flow does not change when you swap them in.

Where every number comes from
-----------------------------
    [B]   L. Chrostowski and M. Hochberg, "Silicon Photonics Design", Cambridge University Press 2015.
          Table 10.1 (process parameters), Table 10.2 (GDS layer map, p. 353), Sec. 6.2 (doping levels).
          The book states that the GSiP kit is distributed "with no restrictions to its distribution".
    [BJ]  T. Baehr-Jones et al., "A 25 Gb/s Silicon Photonics Platform", arXiv:1203.0767 (2012):
          the published process that the book's table refers to.
    [GF]  gdsfactory generic PDK (MIT licence), gdsfactory/gpdk/layer_map.py and layer_stack.py.
          Its layer map says: "Generic layermap based on book ... Silicon Photonics Design ... page 353".
    [T]   teaching value chosen for this repository, with the reason given next to it.

Importing this module activates the PDK:

    import gdsfactory as gf
    import gsip_technology as t

    wg = gf.components.straight(length=20, cross_section="rib")
    ps = gf.components.straight(length=100, cross_section="rib_pn")
"""

from __future__ import annotations

from pathlib import Path

import gdsfactory as gf
from gdsfactory.cross_section import CrossSection, Section, xsection
from gdsfactory.technology import LayerLevel, LayerMap, LayerStack, LayerView, LayerViews, LogicalLayer
from gdsfactory.typings import Layer

# =====================================================================================
# 1. Process constants (um, cm^-3, ohm).  z = 0 is the top of the buried oxide.
# =====================================================================================
# ---- front end: silicon [B Table 10.1] ----
T_BOX = 2.0  # [B][BJ] buried oxide ([GF] uses 3.0)
T_SI = 0.22  # [B][BJ][GF] silicon device layer
ETCH_RIB = 0.13  # [B] "Silicon etch 2": rib waveguide etch
T_SLAB90 = T_SI - ETCH_RIB  # 0.09: slab left by the rib etch [B][GF]
ETCH_SHALLOW = 0.07  # [GF] grating etch; [B] gives 60 nm and notes 60-70 nm as the useful range
T_SLAB150 = T_SI - ETCH_SHALLOW  # 0.15 [GF]
T_GE = 0.50  # [B][BJ][GF] germanium, grown on the silicon
Z_NITRIDE, T_NITRIDE = 0.32, 0.35  # [GF] silicon nitride waveguide layer
SIDEWALL_ANGLE = 90.0  # [T] vertical; not published for a generic process (exercise: try 85 in the process file)

# ---- back end: contacts, heater, three metal levels [GF layer_stack.py unless tagged] ----
Z_M1, T_M1 = 1.10, 0.70  # metal 1; the contact via runs from the silicon up to Z_M1
Z_HEATER = 1.10  # heater film, deposited on the same oxide surface as metal 1
T_HEATER = 0.15  # [T] thin TiN film; [GF] has a 0.75 um placeholder, real TiN heaters are 0.1-0.2 um
Z_M2, T_M2 = 2.30, 0.70  # metal 2; via 1 lands on metal 1 or on the heater
Z_M3, T_M3 = 3.20, 2.00  # metal 3: thick top metal for pads; via 2 runs from metal 2 up to Z_M3
T_PASSIVATION = 0.50  # [T] oxide above metal 3, opened over the pads
Z_TOP = Z_M3 + T_M3 + T_PASSIVATION  # 5.70: top of the dielectric stack
T_SUBSTRATE_SIM = 10.0  # [GF] handle wafer kept in simulations (a real wafer is about 725 um)

# ---- doping: peak concentrations [B Sec. 6.2, listing with "N/P", "N+/P+", "N++/P++"; N and P also in Table 10.1] ----
DOPING = {
    "N": 5.0e17,
    "P": 7.0e17,
    "NP": 3.0e18,  # N+
    "PP": 2.0e18,  # P+
    "NPP": 5.0e20,  # N++
    "PPP": 1.9e20,  # P++ ([BJ] quotes 1.7e20)
    "GEN": 1.0e19,  # [T] germanium contact implants, not used by the ring modulator
    "GEP": 1.0e19,  # [T]
    "background_p": 1.0e15,  # [T] lightly p-type SOI
}

# ---- heater film [T] ----
TIN_RESISTIVITY = 1.5e-6  # ohm m: sputtered TiN is roughly 0.5-2e-6; this gives 10 ohm/sq at 150 nm
HEATER_SHEET_RESISTANCE = TIN_RESISTIVITY / (T_HEATER * 1e-6)  # ohm/sq

# ---- Lumerical database names of the materials (optical / CHARGE / HEAT) ----
MATERIALS = {
    "si": {"optical": "Si (Silicon) - Palik", "charge": "Si (Silicon)", "heat": "Si (Silicon)"},
    "sio2": {"optical": "SiO2 (Glass) - Palik", "charge": "SiO2 (Glass) - Sze", "heat": "SiO2 (Glass) - Sze"},
    "ge": {"optical": "Ge (Germanium) - Palik", "charge": "Ge (Germanium)", "heat": "Ge (Germanium)"},
    "sin": {
        "optical": "Si3N4 (Silicon Nitride) - Luke",
        "charge": "Si3N4 (Silicon nitride) - Sze",
        "heat": "Si3N4 (Silicon nitride) - Sze",
    },
    "al": {"optical": "Al (Aluminium) - Palik", "charge": "Al (Aluminium) - CRC", "heat": "Al (Aluminium) - CRC"},
    # The CHARGE / HEAT database has no TiN: the process file gives the film the aluminium model with its own numbers.
    "tin": {"optical": "TiN - Palik", "charge": "Al (Aluminium) - CRC", "heat": "Al (Aluminium) - CRC"},
}


# =====================================================================================
# 2. Layers.  Names and numbers of the gdsfactory generic PDK [GF]; the book's name is in the comment.
# =====================================================================================
class LayerMapGSiP(LayerMap):
    # ---- silicon, germanium, nitride ----
    WG: Layer = (1, 0)  # [B] "Si": full-thickness silicon, waveguide cores
    SLAB150: Layer = (2, 0)  # [B] "SiEtch1": drawn shapes keep a 150 nm slab (grating couplers)
    SLAB90: Layer = (3, 0)  # [B] "SiEtch2": drawn shapes keep a 90 nm slab (rib waveguides, contacts)
    DEEPTRENCH: Layer = (4, 0)  # [B] "SiEtch3": deep trench for edge coupling or thermal isolation
    GE: Layer = (5, 0)  # [B] "Ge": germanium growth for photodetectors
    UNDERCUT: Layer = (6, 0)  # [B] "OxEtch"; [GF] removes the substrate below a heater
    WGN: Layer = (34, 0)  # [GF] silicon nitride waveguide
    # ---- implants ----
    N: Layer = (20, 0)  # [B] "N"
    P: Layer = (21, 0)  # [B] "P"
    NP: Layer = (22, 0)  # [B] "N+"
    PP: Layer = (23, 0)  # [B] "P+"
    NPP: Layer = (24, 0)  # [B] "Npp": N++ for ohmic contacts
    PPP: Layer = (25, 0)  # [B] "Ppp": P++ for ohmic contacts
    GEN: Layer = (26, 0)  # [B] "GeN"
    GEP: Layer = (27, 0)  # [B] "GeP"
    # ---- contacts, heater, metals ----
    VIAC: Layer = (40, 0)  # [B] "VC": contact via between N++ / P++ and metal 1
    M1: Layer = (41, 0)  # [B] "M1"
    HEATER: Layer = (47, 0)  # [GF] heater film (TiN); the GSiP ring modulator PCell uses the same number
    VIA1: Layer = (44, 0)  # [B] "VL": via between metal 1 (or the heater) and metal 2
    M2: Layer = (45, 0)  # [B] "ML"
    VIA2: Layer = (43, 0)  # [GF] via between metal 2 and metal 3
    M3: Layer = (49, 0)  # [GF] thick top metal: pads
    PADOPEN: Layer = (46, 0)  # [B] "MLOpen": passivation opening over a pad
    # ---- not fabricated ----
    FLOORPLAN: Layer = (64, 0)  # [GF] design outline
    TEXT: Layer = (66, 0)  # [B][GF] text, not printed
    DEVREC: Layer = (68, 0)  # [B][GF] device recognition


LAYER = LayerMapGSiP

# What each layer is: (description, colour, KLayout fill pattern).  The colours are also used by the figures.
LAYER_INFO = {
    "WG": ("silicon core, 220 nm", "#4a5568", "solid"),
    "SLAB150": ("silicon slab, 150 nm", "#cbd5e0", "dotted"),
    "SLAB90": ("silicon slab, 90 nm", "#a0aec0", "coarsely dotted"),
    "DEEPTRENCH": ("deep trench", "#2d3748", "hollow"),
    "GE": ("germanium, 500 nm", "#b08968", "solid"),
    "UNDERCUT": ("substrate undercut", "#718096", "hollow"),
    "WGN": ("silicon nitride, 350 nm", "#38a169", "solid"),
    "N": ("n implant, 5e17", "#9ecae1", "lightly left-hatched"),
    "P": ("p implant, 7e17", "#fcbba1", "lightly right-hatched"),
    "NP": ("n+ implant, 3e18", "#4292c6", "left-hatched"),
    "PP": ("p+ implant, 2e18", "#fb6a4a", "right-hatched"),
    "NPP": ("n++ implant, 5e20", "#08519c", "strongly left-hatched dense"),
    "PPP": ("p++ implant, 1.9e20", "#cb181d", "strongly right-hatched dense"),
    "GEN": ("germanium n implant", "#6baed6", "left-hatched"),
    "GEP": ("germanium p implant", "#fc9272", "right-hatched"),
    "VIAC": ("contact via", "#1a202c", "solid"),
    "M1": ("metal 1, Al 0.7 um", "#ecc94b", "coarsely dotted"),
    "HEATER": ("heater, TiN 0.15 um", "#805ad5", "cross-hatched"),
    "VIA1": ("via 1", "#4a4a4a", "solid"),
    "M2": ("metal 2, Al 0.7 um", "#dd6b20", "dotted"),
    "VIA2": ("via 2", "#6b6b6b", "solid"),
    "M3": ("metal 3, Al 2 um", "#975a16", "lightly right-hatched"),
    "PADOPEN": ("pad opening", "#2c7a7b", "hollow"),
    "FLOORPLAN": ("design outline", "#a0aec0", "hollow"),
    "TEXT": ("text", "#319795", "hollow"),
    "DEVREC": ("device recognition", "#b794f4", "hollow"),
}
LAYER_COLORS = {name: info[1] for name, info in LAYER_INFO.items()}

LAYER_VIEWS = LayerViews()
for _name, (_description, _color, _hatch) in LAYER_INFO.items():
    LAYER_VIEWS.add_layer_view(
        name=_name,
        layer_view=LayerView(
            layer=tuple(getattr(LAYER, _name)),
            color=_color,
            hatch_pattern=_hatch,
            layer_in_name=True,
            transparent=_name in ("N", "P", "NP", "PP", "NPP", "PPP", "GEN", "GEP"),
            width=1,
        ),
    )

# Short handles for the code below and for device builders.
WG, SLAB90, SLAB150 = LAYER.WG, LAYER.SLAB90, LAYER.SLAB150
N, P, NP, PP, NPP, PPP = LAYER.N, LAYER.P, LAYER.NP, LAYER.PP, LAYER.NPP, LAYER.PPP
VIAC, M1, HEATER, VIA1, M2, VIA2, M3, PADOPEN = (
    LAYER.VIAC, LAYER.M1, LAYER.HEATER, LAYER.VIA1, LAYER.M2, LAYER.VIA2, LAYER.M3, LAYER.PADOPEN,
)  # fmt: skip

# =====================================================================================
# 3. Design rules (um).  Each value says where its rule is enforced: [DRC] gsip_drc.py, [builder] rm_builder.py,
#    or [construction].  [T] marks a teaching value.
#    [B Listing 10.4] gives one example rule: silicon width and space 0.2 um.  Everything else is [T]:
#    round numbers of the size a 248 nm process offers, so that the layout exercises make sense.
# =====================================================================================
# layer -> (minimum width, minimum space)
MIN_WIDTH_SPACE = {
    "WG": (0.20, 0.20),  # [B]
    "SLAB150": (0.30, 0.30),
    "SLAB90": (0.30, 0.30),
    "GE": (1.00, 1.00),
    "WGN": (0.40, 0.40),
    "N": (0.30, 0.30),
    "P": (0.30, 0.30),
    "NP": (0.30, 0.30),
    "PP": (0.30, 0.30),
    "NPP": (0.30, 0.30),
    "PPP": (0.30, 0.30),
    "VIAC": (0.40, 0.40),
    "M1": (0.50, 0.50),
    "HEATER": (0.80, 0.80),
    "VIA1": (0.50, 0.50),
    "M2": (1.00, 1.00),
    "VIA2": (1.00, 1.00),
    "M3": (3.00, 3.00),
    "PADOPEN": (20.0, 20.0),
}
DESIGN_RULES = {
    "grid": 0.001,  # [construction] 1 nm: the database unit of the GDS that write_gds_for_lumerical writes
    "viac_enclosure_by_contact_implant": 0.20,  # [DRC] N++ / P++ beyond every contact via
    "viac_enclosure_by_m1": 0.10,  # [DRC] metal 1 beyond every contact via
    "via1_enclosure_by_lower": 0.20,  # [DRC] metal 1 or the heater beyond every via 1
    "via1_enclosure_by_m2": 0.20,  # [DRC] metal 2 beyond every via 1; [builder] also sets the metal 2 ends with it
    "via2_enclosure_by_m2": 0.30,  # [DRC] metal 2 beyond every via 2
    "via2_enclosure_by_m3": 0.30,  # [DRC] metal 3 beyond every via 2
    "padopen_enclosure_by_m3": 2.00,  # [DRC] passivation opening inside the pad metal; pad() draws it with this margin
    "m1_to_heater": 0.60,  # [DRC] metal 1 and the heater lie in the same plane and keep this distance
    "contact_implant_to_core": 0.40,  # [DRC, warning] N++ / P++ edge to the edge of a waveguide core
    # [T] teaching values, not foundry rules.  The simulations do not set them: step 2 only shows that the bend
    # loss is below the solver floor from 6 um up, so 10 um is a choice with margin.
    "heater_to_waveguide": 0.50,  # [T][builder] clearance from the lowest point of the heater to the top of the bus core
    "rib_bend_radius": 10.0,  # [T][builder] smallest ring radius: ring_modulator refuses a tighter ring
    "strip_bend_radius": 5.0,  # [T] not enforced: the device has no strip bend
}


# =====================================================================================
# 4. The stack: one table, used by the gdsfactory LayerStack, the stack figure and the tests
#    that compare it with the process CSV.  (name, layer, z_min, z_max, material)
# =====================================================================================
STACK = [
    ("substrate", None, -T_BOX - T_SUBSTRATE_SIM, -T_BOX, "si"),
    ("box", None, -T_BOX, 0.0, "sio2"),
    ("cladding", None, 0.0, Z_TOP, "sio2"),
    ("slab150", "SLAB150", 0.0, T_SLAB150, "si"),
    ("slab90", "SLAB90", 0.0, T_SLAB90, "si"),
    ("core", "WG", 0.0, T_SI, "si"),
    ("germanium", "GE", T_SI, T_SI + T_GE, "ge"),
    ("nitride", "WGN", Z_NITRIDE, Z_NITRIDE + T_NITRIDE, "sin"),
    ("via_contact", "VIAC", T_SLAB90, Z_M1, "al"),
    ("metal1", "M1", Z_M1, Z_M1 + T_M1, "al"),
    ("heater", "HEATER", Z_HEATER, Z_HEATER + T_HEATER, "tin"),
    # this row is via 1 on metal 1.  Via 1 on the heater starts at the top of the heater film (1.25 um) and is
    # listed in process_layers.csv (Via1_on_heater), not here: a stack has one height per GDS layer, and VIA1 is one.
    ("via1", "VIA1", Z_M1 + T_M1, Z_M2, "al"),
    ("metal2", "M2", Z_M2, Z_M2 + T_M2, "al"),
    ("via2", "VIA2", Z_M2 + T_M2, Z_M3, "al"),
    ("metal3", "M3", Z_M3, Z_M3 + T_M3, "al"),
]


def _logical(name: str) -> LogicalLayer:
    return LogicalLayer(layer=tuple(getattr(LAYER, name)))


LAYER_STACK = LayerStack(
    layers={
        name: LayerLevel(
            layer=_logical(layer or "WG"),
            zmin=z0,
            thickness=z1 - z0,
            material=material,
            mesh_order={"core": 1, "slab90": 2, "slab150": 2}.get(name, 3 if layer else 100),
            background=layer is None,
        )
        for name, layer, z0, z1, material in STACK
    }
)


# =====================================================================================
# 5. Cross-sections
# =====================================================================================
PN_GAP_MEDIUM = 0.65  # [T] waveguide centre -> N+ / P+ edge: 0.4 um of lightly doped slab beside the 0.5 um core
PN_GAP_HIGH = 1.25  # [T] waveguide centre -> N++ / P++ edge: 1.0 um from the core edge
RIB_SLAB_WIDTH = 6.0  # [T] slab of the rib waveguide; wide enough for a contact on each side


def _waveguide(width: float, width_slab: float | None, radius: float, sections: tuple[Section, ...] = ()) -> CrossSection:
    if width_slab is not None:
        sections = (Section(width=width_slab, layer=SLAB90, name="slab"), *sections)
    return gf.cross_section.cross_section(width=width, layer=WG, sections=sections, radius=radius, radius_min=radius)


@xsection
def strip(width: float = 0.5, radius: float = 5.0) -> CrossSection:
    """Strip waveguide: 220 nm silicon, fully etched on both sides."""
    return _waveguide(width, None, radius)


@xsection
def rib(width: float = 0.5, width_slab: float = RIB_SLAB_WIDTH, radius: float = 10.0) -> CrossSection:
    """Rib waveguide: 220 nm core on a 90 nm slab."""
    return _waveguide(width, width_slab, radius)


@xsection
def rib_pn(
    width: float = 0.5,
    width_slab: float = RIB_SLAB_WIDTH,
    junction_offset: float = 0.0,
    gap_medium_doping: float = PN_GAP_MEDIUM,
    gap_high_doping: float = PN_GAP_HIGH,
    p_inside: bool = False,
    radius: float = 10.0,
) -> CrossSection:
    """Carrier-depletion phase shifter: the rib waveguide with six implants.

    Seen along the path, n is on the left and p on the right; on a counter-clockwise ring that puts
    n inside.  ``p_inside=True`` mirrors it.

         N++   |  N+  |   N    |core|    P   |  P+  |  P++
        -------+------+--------+####+--------+------+-------     gaps are measured from the waveguide centre
              -1.25  -0.65              0.65   1.25

    The implants are nested, as in gdsfactory's generic ``pn`` cross-section: N covers the whole n side,
    N+ everything beyond ``gap_medium_doping``, N++ everything beyond ``gap_high_doping``.

    Args:
        width: core width.
        width_slab: slab width; the implants end at the slab edge.
        junction_offset: position of the junction relative to the core centre, positive towards p.
        gap_medium_doping: waveguide centre to the N+ / P+ edge.
        gap_high_doping: waveguide centre to the N++ / P++ edge.
        p_inside: swap the two sides.
        radius: minimum bend radius.

    Contact vias and metal are not part of the cross-section; the device builder draws them.
    """
    half = width_slab / 2
    # Side of the n region.  gdsfactory puts a negative offset on the left of the path, which is +y for a
    # straight along +x: without p_inside the n implants lie at +y (tests/test_technology.py checks it).
    sign = 1.0 if p_inside else -1.0
    if not width / 2 < gap_medium_doping < gap_high_doping < half:
        raise ValueError("need width / 2 < gap_medium_doping < gap_high_doping < width_slab / 2")

    def band(layer, inner: float, side: float, name: str) -> Section:
        """Implant from ``inner`` (signed distance from the centre towards ``side``) to the slab edge."""
        w = half - inner
        return Section(width=w, offset=side * (inner + w / 2), layer=layer, name=name)

    sections = (
        band(N, -junction_offset, sign, "n"),  # from the junction to the slab edge on the n side
        band(P, junction_offset, -sign, "p"),
        band(NP, gap_medium_doping, sign, "np"),
        band(PP, gap_medium_doping, -sign, "pp"),
        band(NPP, gap_high_doping, sign, "npp"),
        band(PPP, gap_high_doping, -sign, "ppp"),
    )
    return _waveguide(width, width_slab, radius, sections)


@xsection
def nitride(width: float = 1.0, radius: float = 25.0) -> CrossSection:
    """Silicon nitride strip waveguide."""
    return gf.cross_section.cross_section(width=width, layer=LAYER.WGN, radius=radius, radius_min=radius)


def _wire(layer, width: float) -> CrossSection:
    return gf.cross_section.cross_section(
        width=width, layer=layer, radius=None, radius_min=None, port_names=("e1", "e2"), port_types=("electrical", "electrical")
    )


@xsection
def heater_metal(width: float = 2.0) -> CrossSection:
    """Heater filament in the TiN film."""
    return _wire(HEATER, width)


@xsection
def metal1(width: float = 2.0) -> CrossSection:
    return _wire(M1, width)


@xsection
def metal2(width: float = 5.0) -> CrossSection:
    return _wire(M2, width)


@xsection
def metal3(width: float = 10.0) -> CrossSection:
    return _wire(M3, width)


CROSS_SECTIONS = {
    "strip": strip,
    "rib": rib,
    "rib_pn": rib_pn,
    "nitride": nitride,
    "heater_metal": heater_metal,
    "metal1": metal1,
    "metal2": metal2,
    "metal3": metal3,
}


# =====================================================================================
# 6. Cells
# =====================================================================================
@gf.cell
def straight(length: float = 10.0, cross_section: str = "strip") -> gf.Component:
    return gf.components.straight(length=length, cross_section=cross_section)


@gf.cell
def bend_euler(angle: float = 90.0, cross_section: str = "strip") -> gf.Component:
    return gf.components.bend_euler(angle=angle, cross_section=cross_section)


@gf.cell
def bend_circular(angle: float = 90.0, cross_section: str = "rib") -> gf.Component:
    return gf.components.bend_circular(angle=angle, cross_section=cross_section)


@gf.cell
def pad(size: float = 80.0) -> gf.Component:
    """Probe / bond pad: metal 3 with the passivation opened over it.  Port ``e1`` at the centre."""
    c = gf.Component()
    h = size / 2
    o = h - DESIGN_RULES["padopen_enclosure_by_m3"]
    c.add_polygon([(-h, -h), (h, -h), (h, h), (-h, h)], layer=M3)
    c.add_polygon([(-o, -o), (o, -o), (o, o), (-o, o)], layer=PADOPEN)
    c.add_port("e1", center=(0, 0), width=size, orientation=90, layer=M3, port_type="electrical")
    return c


CELLS = {"straight": straight, "bend_euler": bend_euler, "bend_circular": bend_circular, "pad": pad}


# =====================================================================================
# 7. From layout to simulation
# =====================================================================================
def write_gds_for_lumerical(component: gf.Component, gdspath: str | Path, cellname: str | None = None) -> Path:
    """Write a flat GDS with a single named cell and no gdsfactory metadata cell.

    The Layer Builder loads one cell of one GDS file; a flat, single-cell file leaves nothing to choose.
    The mask layers are written unchanged.
    """
    flat = gf.Component()
    flat << component
    flat.flatten()
    flat.name = cellname or component.name
    gdspath = Path(gdspath)
    gdspath.parent.mkdir(parents=True, exist_ok=True)
    return flat.write_gds(gdspath, with_metadata=False)


# =====================================================================================
# 8. The PDK object and the KLayout technology
# =====================================================================================
# Electrical connectivity for netlist tracing.
LAYER_CONNECTIVITY = [
    ("NPP", "VIAC", "M1"),
    ("PPP", "VIAC", "M1"),
    ("M1", "VIA1", "M2"),
    ("HEATER", "VIA1", "M2"),
    ("M2", "VIA2", "M3"),
]

PDK = gf.Pdk(
    name="gsip_teaching",
    version="0.3 (GSiP layer map; teaching back end)",
    layers=LAYER,
    layer_stack=LAYER_STACK,
    layer_views=LAYER_VIEWS,
    cross_sections=CROSS_SECTIONS,
    cells=CELLS,
    connectivity=LAYER_CONNECTIVITY,
)


def activate_pdk() -> gf.Pdk:
    PDK.activate()
    return PDK


def write_klayout_tech(tech_dir: str | Path = "klayout_tech") -> Path:
    """Write ``layers.lyp`` (layer names and colours) and ``tech.lyt`` for KLayout.

    In KLayout: File > Load Layer Properties with ``layers.lyp``, or
    Tools > Manage Technologies > Import Technology with ``tech.lyt``.
    """
    out = Path(tech_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        PDK.klayout_technology.write_tech(tech_dir=out)
    except Exception as err:  # the layer colours are the part people need; never lose them
        print(f"tech.lyt not written ({err}); writing layers.lyp only")
        LAYER_VIEWS.to_lyp(out / "layers.lyp")
    return out


activate_pdk()

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    print(f"PDK {PDK.name}: {len(LAYER_INFO)} layers, {len(CROSS_SECTIONS)} cross-sections, {len(CELLS)} cells")
    for name, (description, _, _) in LAYER_INFO.items():
        gds = tuple(getattr(LAYER, name))
        print(f"  {gds[0]:>3}/{gds[1]}  {name:<10} {description}")
    print("stack (um):")
    for name, layer, z0, z1, material in STACK:
        print(f"  {name:<12} {z0:7.2f} .. {z1:5.2f}  {material:<5} {layer or 'everywhere'}")
    print(f"heater sheet resistance: {HEATER_SHEET_RESISTANCE:.1f} ohm/sq")
    print("KLayout technology ->", write_klayout_tech(here / "klayout_tech"))

"""CORNERSTONE SOI 220 nm active platform (SOI220A) as a gdsfactory technology.

This file is the layout half of the foundry-compatible flow:

    cornerstone_technology.py   layers, design rules, layer stack, cross-sections, cells   (this file)
            |
    rm_builder.py               device layout drawn with the PDK cross-sections  ->  .gds
            |
    cornerstone_process_file_py/   the same process as CSV tables  ->  cornerstone_process.lbr
            |
    lumerical_simulations/      GDS + .lbr in the Layer Builder  ->  FDTD / FDE / CHARGE / HEAT / INTERCONNECT

Every number below is public.  Tags used in the comments:

    [YAML]   github.com/cornerstone-uos/cornerstone-pdk, SOI220A/process_overview.yaml (v1.2.0, 2026-10-30)
    [XS]     same repository, SOI220A/cross-sections/cross_sections.yaml
    [DG]     CORNERSTONE Design Guidelines, 220 nm SOI Active MPW #47 (October 2025)
    [MZM]    measured on the official building block SOI220_1550nm_TE_rib_MZM_type1.gds
    [HTR]    measured on the official building block Heater.gds
    [assumed] not published; a typical value, flagged so that you can replace it

Teaching and simulation set-up only.  Before a tape-out take every value from the design
guidelines of the call you submit to (https://www.cornerstone.sotonfab.co.uk/).

Importing this module activates the PDK:

    import gdsfactory as gf
    import cornerstone_technology as t

    wg = gf.components.straight(length=20, cross_section="rib_1550nm_TE")
    ps = gf.components.straight(length=100, cross_section="rib_1550nm_TE_pn")
"""

from __future__ import annotations

from pathlib import Path

import gdsfactory as gf
from gdsfactory.cross_section import CrossSection, Section, xsection
from gdsfactory.technology import LayerLevel, LayerMap, LayerStack, LayerView, LayerViews, LogicalLayer
from gdsfactory.typings import Layer

# =====================================================================================
# 1. Process constants (um, cm^-3).  z = 0 is the top of the buried oxide.
# =====================================================================================
T_BOX = 2.0  # [DG 4] thermal SiO2 buried oxide.  [YAML] lists 3.0 -- see README "Known inconsistencies"
T_SI = 0.22  # [DG 4][YAML] crystalline Si device layer, +-20 nm
T_SLAB = 0.10  # [DG 4][YAML] rib slab left after Silicon Etch 2 (120 nm)
ETCH_GRATING = 0.07  # [DG 4] Silicon Etch 1 (grating couplers), +-10 nm
ETCH_RIB = 0.12  # [DG 4] Silicon Etch 2, +-10 nm
T_TOX = 1.0  # [DG 4, step 25] SiO2 top cladding above the Si, +-100 nm.  [YAML] lists 2.0
T_METAL = 1.6  # [DG Table 2][YAML] Al electrode stack, also used for heaters
T_DETECTOR_OXIDE = 0.2  # [DG, GDS 23] oxide left above the waveguide in a detector implant window
T_SUBSTRATE_SIM = 3.0  # [assumed] handle wafer kept in simulations (real wafer: ~725 um)
Z_METAL = T_SI + T_TOX  # bottom of the electrode layer (planar cladding [assumed])

TRENCH_WIDTH = 5.0  # [DG 5.2 / 9] trench the foundry opens on both sides of every GDS 3 shape
N_SIDEWALL_DEPTH = 0.11  # [DG 5.2] depth of the 45 deg self-aligned n implant into the rib sidewall

# Doping [DG Table 2].  The low-dose n value is the *net* concentration after it has
# compensated the background p implant, so the donor density is the sum of the two.
DOPING = {
    "p_slab": 5.7e17,  # "P+ region (A)": lower 100 nm of the silicon (the slab layer)
    "p_rib": 2.25e17,  # "P+ region (B)": upper 120 nm, which only survives inside the rib
    "n_net": 1.1e18,  # "N+ region (C)", net of the background p
    "ppp": 1.0e20,  # P++ ohmic contact
    "npp": 1.0e20,  # N++ ohmic contact
    "substrate_p": 1.0e15,  # [assumed] background of the SOI device layer
}

# Lumerical database names of the materials used by the process file.
MATERIALS = {
    "si": {"optical": "Si (Silicon) - Palik", "charge": "Si (Silicon)", "heat": "Si (Silicon)"},
    "sio2": {"optical": "SiO2 (Glass) - Palik", "charge": "SiO2 (Glass) - Sze", "heat": "SiO2 (Glass) - Sze"},
    "al": {"optical": "Al (Aluminium) - Palik", "charge": "Al (Aluminium) - CRC", "heat": "Al (Aluminium) - CRC"},
}


# =====================================================================================
# 2. Layers.  Names are the official SOI220A names [YAML] in upper case.
# =====================================================================================
class LayerMapSOI220A(LayerMap):
    SI_ETCH1_DUV_DF_70NM: Layer = (6, 0)  # grating couplers, drawn = etched 70 nm
    SI_ETCH2_LF_120NM: Layer = (3, 0)  # waveguide core, drawn = kept at 220 nm
    SI_ETCH2_DF_120NM: Layer = (4, 0)  # same etch, drawn = etched 120 nm
    SI_ETCH3_LF_100NM_TO_BOX: Layer = (5, 0)  # rib protect, drawn = 100 nm slab kept
    P_IMPLANT_LOW_DF: Layer = (7, 0)  # background low-dose p
    N_IMPLANT_LOW_DF: Layer = (8, 0)  # low-dose n (45 deg, self-aligned to the rib)
    P_IMPLANT_HI_DF: Layer = (9, 0)  # P++ ohmic contacts
    N_IMPLANT_HI_DF: Layer = (11, 0)  # N++ ohmic contacts
    VIA_DF: Layer = (12, 0)  # via through the top cladding
    ELECTRODE_LF: Layer = (13, 0)  # Al electrodes, pads and heater filaments
    DETECTOR_IMPLANT_DF: Layer = (23, 0)  # defect-detector implant window
    FLOORPLAN: Layer = (99, 0)  # cell outline
    LABEL_ETCH_DF: Layer = (100, 0)  # text, merged into Silicon Etch 2 by the foundry
    # Not a mask.  Written only by write_gds_for_lumerical(): the 110 nm sidewall strip the
    # self-aligned n implant dopes, which the Layer Builder cannot derive by itself.
    SIM_N_SIDEWALL: Layer = (208, 0)


LAYER = LayerMapSOI220A

# Short handles for the code below and for device builders.
CORE = LAYER.SI_ETCH2_LF_120NM
SLAB = LAYER.SI_ETCH3_LF_100NM_TO_BOX
P_LOW = LAYER.P_IMPLANT_LOW_DF
N_LOW = LAYER.N_IMPLANT_LOW_DF
P_HI = LAYER.P_IMPLANT_HI_DF
N_HI = LAYER.N_IMPLANT_HI_DF
VIA = LAYER.VIA_DF
METAL = LAYER.ELECTRODE_LF

# Official mixed-case layer names [YAML] and the colours of the official layers.lyp.
_VIEWS = {
    "SI_ETCH1_DUV_DF_70NM": ("Si_Etch1_DUV_DF_70nm", "#ff0000", "coarsely dotted"),
    "SI_ETCH2_LF_120NM": ("Si_Etch2_LF_120nm", "#9580ff", "solid"),
    "SI_ETCH2_DF_120NM": ("Si_Etch2_DF_120nm", "#8183ff", "left-hatched"),
    "SI_ETCH3_LF_100NM_TO_BOX": ("Si_Etch3_LF_100nm_to_BOX", "#80a8ff", "dotted"),
    "P_IMPLANT_LOW_DF": ("P_Implant_Low_DF", "#ff00ff", "lightly right-hatched"),
    "N_IMPLANT_LOW_DF": ("N_Implant_Low_DF", "#8000ff", "lightly left-hatched"),
    "P_IMPLANT_HI_DF": ("P_Implant_Hi_DF", "#0080ff", "strongly right-hatched dense"),
    "N_IMPLANT_HI_DF": ("N_Implant_Hi_DF", "#80a8ff", "strongly left-hatched dense"),
    "VIA_DF": ("Via_DF", "#800057", "cross-hatched"),
    "ELECTRODE_LF": ("Electrode_LF", "#b8a000", "coarsely dotted"),
    "DETECTOR_IMPLANT_DF": ("Detector_Implant_DF", "#ff0080", "plus"),
    "FLOORPLAN": ("Floorplan", "#808080", "hollow"),
    "LABEL_ETCH_DF": ("Label_Etch_DF", "#8000ff", "hollow"),
    "SIM_N_SIDEWALL": ("Sim_N_Sidewall", "#00c000", "hollow"),
}
OFFICIAL_LAYER_NAMES = {key: view[0] for key, view in _VIEWS.items()}

LAYER_VIEWS = LayerViews()
for _key, (_name, _color, _hatch) in _VIEWS.items():
    LAYER_VIEWS.add_layer_view(
        name=_name,
        layer_view=LayerView(
            layer=tuple(getattr(LAYER, _key)),
            color=_color,
            hatch_pattern=_hatch,
            layer_in_name=True,
            transparent="IMPLANT" in _key,
            width=1,
        ),
    )

# =====================================================================================
# 3. Design rules (um).  cornerstone_drc.py checks them; device builders read them.
# =====================================================================================
# layer -> (minimum feature, minimum gap)   [DG Table 3][YAML]
MIN_WIDTH_SPACE = {
    "SI_ETCH1_DUV_DF_70NM": (0.20, 0.25),
    "SI_ETCH2_LF_120NM": (0.35, 0.20),
    "SI_ETCH2_DF_120NM": (0.20, 0.35),
    "SI_ETCH3_LF_100NM_TO_BOX": (0.25, 0.25),
    "P_IMPLANT_LOW_DF": (0.50, 0.50),
    "N_IMPLANT_LOW_DF": (0.50, 0.50),
    "P_IMPLANT_HI_DF": (0.50, 0.50),
    "N_IMPLANT_HI_DF": (0.50, 0.50),
    "VIA_DF": (3.0, 5.0),
    # Gap: [DG Table 3] says 2 um, [YAML] and the official DRC deck say 4 um.  The stricter one.
    "ELECTRODE_LF": (6.0, 4.0),
    "DETECTOR_IMPLANT_DF": (5.0, 5.0),
}
DESIGN_RULES = {
    "grid": 0.001,  # [DG 5.5] 1 nm manufacturing grid
    "via_enclosure_by_high_dose": 0.5,  # [DG 5.3] P++/N++ extends >= 500 nm beyond every via
    "via_enclosure_by_electrode": 0.5,  # [DG 5.3] electrode extends >= 500 nm beyond every via
    "layer_overlap": 0.2,  # [DG 5.3] overlap between layers that must touch (alignment)
    "detector_to_electrode": 5.0,  # [DG 5.3] GDS 23 to GDS 13
    "heater_filament_width": 2.0,  # [HTR] official heater filament; narrower than the electrode rule
    "rib_bend_radius": 25.0,  # [XS] rib_1550nm_TE minimum bend radius
    "strip_bend_radius": 10.0,  # [XS] strip_1550nm minimum bend radius
    "waveguide_spacing": 5.0,  # [DG 5.3] recommended, to avoid coupling
    "design_area_full": (11470.0, 4900.0),  # [DG 5.1]
    "design_area_half": (5500.0, 4900.0),
}

# =====================================================================================
# 4. Layer stack (3D preview, gplugins).  The Lumerical stack lives in the process CSVs.
# =====================================================================================
_core = LogicalLayer(layer=tuple(CORE))
_slab = LogicalLayer(layer=tuple(SLAB)) | LogicalLayer(layer=tuple(P_HI)) | LogicalLayer(layer=tuple(N_HI))
_grating = LogicalLayer(layer=tuple(LAYER.SI_ETCH1_DUV_DF_70NM))
_via = LogicalLayer(layer=tuple(VIA))

LAYER_STACK = LayerStack(
    layers={
        "substrate": LayerLevel(
            layer=_core, zmin=-T_BOX - T_SUBSTRATE_SIM, thickness=T_SUBSTRATE_SIM, material="si", mesh_order=101, background=True
        ),
        "box": LayerLevel(layer=_core, zmin=-T_BOX, thickness=T_BOX, material="sio2", mesh_order=9, background=True),
        "tox": LayerLevel(layer=_core, zmin=0.0, thickness=Z_METAL, material="sio2", mesh_order=10, background=True),
        "slab": LayerLevel(
            layer=_slab, derived_layer=LogicalLayer(layer=tuple(SLAB)), zmin=0.0, thickness=T_SLAB, material="si", mesh_order=3
        ),
        "core": LayerLevel(layer=_core - _grating, derived_layer=_core, zmin=0.0, thickness=T_SI, material="si", mesh_order=2),
        "grating": LayerLevel(
            layer=_core & _grating, derived_layer=_grating, zmin=0.0, thickness=T_SI - ETCH_GRATING, material="si", mesh_order=1
        ),
        "via": LayerLevel(layer=_via, zmin=T_SLAB, thickness=Z_METAL - T_SLAB, material="al", mesh_order=1),
        "electrode": LayerLevel(
            layer=LogicalLayer(layer=tuple(METAL)), zmin=Z_METAL, thickness=T_METAL, material="al", mesh_order=1
        ),
    }
)


# =====================================================================================
# 5. Cross-sections.  Passive ones carry the official names and dimensions [XS].
# =====================================================================================
def _waveguide(width: float, width_slab: float | None, radius: float, sections: tuple[Section, ...] = ()) -> CrossSection:
    if width_slab is not None:
        sections = (Section(width=width_slab, layer=SLAB, name="slab"), *sections)
    return gf.cross_section.cross_section(width=width, layer=CORE, sections=sections, radius=radius, radius_min=radius)


@xsection
def strip_1550nm(width: float = 0.45, radius: float = 10.0) -> CrossSection:
    """C-band strip waveguide: 220 nm silicon etched to the BOX on both sides."""
    return _waveguide(width, None, radius)


@xsection
def strip_1310nm(width: float = 0.40, radius: float = 10.0) -> CrossSection:
    """O-band strip waveguide."""
    return _waveguide(width, None, radius)


@xsection
def rib_1550nm_TE(width: float = 0.45, width_slab: float = 10.45, radius: float = 25.0) -> CrossSection:
    """C-band rib waveguide: 220 nm core on a 100 nm slab.

    The slab covers the two 5 um trenches the foundry opens next to the core, hence 0.45 + 2 x 5.
    """
    return _waveguide(width, width_slab, radius)


@xsection
def rib_1310nm_TE(width: float = 0.40, width_slab: float = 10.40, radius: float = 25.0) -> CrossSection:
    """O-band rib waveguide."""
    return _waveguide(width, width_slab, radius)


@xsection
def rib_1550nm_TE_pn(
    width: float = 0.45,
    width_slab: float = 14.0,
    junction_offset: float = 0.0,
    gap_n_high_dose: float = 0.75,
    gap_p_high_dose: float = 0.80,
    slab_margin: float = 0.5,
    p_inside: bool = False,
    radius: float = 25.0,
) -> CrossSection:
    """Carrier-depletion phase shifter: the rib waveguide with the four implants.

    Seen along the path, n is on the left and p on the right; on a counter-clockwise ring
    that puts n inside.  ``p_inside=True`` mirrors it.

        N++ | N low |core| P low | P++          gaps and the n edge follow the official MZM [MZM]
        ----+-------+####+-------+----
        <------- background P low ------>

    Args:
        width: core width.
        width_slab: slab width.  Wider than the passive rib (10.45) so that the contacts sit on drawn slab.
        junction_offset: drawn edge of the low-dose n mask relative to the core centre, positive towards p.
            The foundry recommends 0: the implant is self-aligned to the rib sidewall, and the junction
            forms 110 nm inside the n-side sidewall wherever the edge is drawn inside the core [DG 5.2].
        gap_n_high_dose / gap_p_high_dose: core centre to the N++ / P++ edge.
        slab_margin: slab left outside the high-dose regions.
        p_inside: swap the two sides.
        radius: minimum bend radius.

    Vias and electrodes are not part of the cross-section; the device builder draws them.
    """
    half = width_slab / 2
    sign = 1.0 if p_inside else -1.0  # side of the n region; negative offset = left of the path
    n_low_width = half + junction_offset  # from the outer slab edge on the n side to the drawn edge
    hi_n = half - slab_margin - gap_n_high_dose
    hi_p = half - slab_margin - gap_p_high_dose
    if min(hi_n, hi_p) < MIN_WIDTH_SPACE["N_IMPLANT_HI_DF"][0]:
        raise ValueError("width_slab is too small for the high-dose contact regions")
    sections = (
        Section(width=width_slab, layer=P_LOW, name="p_low"),  # the n region must lie inside it [DG Table 2]
        Section(width=n_low_width, offset=sign * (half - n_low_width / 2), layer=N_LOW, name="n_low"),
        Section(width=hi_n, offset=sign * (gap_n_high_dose + hi_n / 2), layer=N_HI, name="n_high"),
        Section(width=hi_p, offset=-sign * (gap_p_high_dose + hi_p / 2), layer=P_HI, name="p_high"),
    )
    return _waveguide(width, width_slab, radius, sections)


@xsection
def dc(width: float = 80.0) -> CrossSection:
    """DC electrode trace in the Al layer; 80 um is the official pad / trace width [XS]."""
    return gf.cross_section.cross_section(
        width=width, layer=METAL, radius=None, radius_min=None, port_names=("e1", "e2"), port_types=("electrical", "electrical")
    )


@xsection
def heater_filament(width: float = 2.0) -> CrossSection:
    """Heater filament in the Al electrode layer, 2 um wide as in the official heater [HTR]."""
    return gf.cross_section.cross_section(
        width=width, layer=METAL, radius=None, radius_min=None, port_names=("e1", "e2"), port_types=("electrical", "electrical")
    )


CROSS_SECTIONS = {
    "strip_1550nm": strip_1550nm,
    "strip_1310nm": strip_1310nm,
    "rib_1550nm_TE": rib_1550nm_TE,
    "rib_1310nm_TE": rib_1310nm_TE,
    "rib_1550nm_TE_pn": rib_1550nm_TE_pn,
    "dc": dc,
    "heater_filament": heater_filament,
    "strip": strip_1550nm,  # default of the generic gdsfactory cells
    "rib": rib_1550nm_TE,
}


# =====================================================================================
# 6. Cells
# =====================================================================================
@gf.cell
def straight(length: float = 10.0, cross_section: str = "strip_1550nm") -> gf.Component:
    return gf.components.straight(length=length, cross_section=cross_section)


@gf.cell
def bend_euler(angle: float = 90.0, cross_section: str = "strip_1550nm") -> gf.Component:
    return gf.components.bend_euler(angle=angle, cross_section=cross_section)


@gf.cell
def bend_circular(angle: float = 90.0, cross_section: str = "rib_1550nm_TE") -> gf.Component:
    return gf.components.bend_circular(angle=angle, cross_section=cross_section)


@gf.cell
def pad(size: float = 80.0) -> gf.Component:
    """Bond / probe pad in the Al electrode layer.  The metal is not passivated, so no opening is drawn."""
    c = gf.Component()
    c.add_polygon([(-size / 2, -size / 2), (size / 2, -size / 2), (size / 2, size / 2), (-size / 2, size / 2)], layer=METAL)
    c.add_port("e1", center=(0, 0), width=size, orientation=90, layer=METAL, port_type="electrical")
    return c


CELLS = {"straight": straight, "bend_euler": bend_euler, "bend_circular": bend_circular, "pad": pad}


# =====================================================================================
# 7. What the foundry does to the masks  ->  layers the simulation needs
# =====================================================================================
def silicon_regions(component: gf.Component) -> dict[str, gf.kdb.Region]:
    """Silicon as fabricated, from the mask processing of [DG 9] and the self-aligned implant of [DG 5.2].

    Returns regions (database units) keyed by:
        trench      etched 120 nm by Silicon Etch 2: 5 um around every core shape, plus GDS 4,
                    plus the high-dose implants grown by 200 nm
        slab        100 nm silicon: the part of the trench protected by GDS 5 or by a
                    high-dose implant grown by 300 nm
        to_box      trench that is not protected, etched down to the BOX
        n_sidewall  strip of the core doped n through its sidewall (110 nm deep)

    Everything outside ``trench`` keeps the full 220 nm, including the field far from the
    waveguides, which no simulation in this repository needs.
    """
    dbu = component.kcl.dbu

    def region(layer) -> gf.kdb.Region:
        return component.get_region(layer, merge=True)

    def grown(r: gf.kdb.Region, d: float) -> gf.kdb.Region:
        return r.sized(round(d / dbu))

    core = region(CORE)
    high = region(P_HI) + region(N_HI)
    trench = (grown(core, TRENCH_WIDTH) + grown(high, 0.2)).merged() - core
    trench = (trench + region(LAYER.SI_ETCH2_DF_120NM) + region(LAYER.LABEL_ETCH_DF)).merged()
    protect = (region(SLAB) + grown(high, 0.3)).merged()
    n_open = region(N_LOW) - core  # the hard mask shields the top of the core
    return {
        "trench": trench,
        "slab": trench & protect,
        "to_box": trench - protect,
        "n_sidewall": grown(n_open, N_SIDEWALL_DEPTH) & core,
    }


def write_gds_for_lumerical(component: gf.Component, gdspath: str | Path, cellname: str | None = None) -> Path:
    """Write a flat GDS the Layer Builder can use directly.

    Compared with ``component.write_gds()``:
      * one flat cell and no gdsfactory metadata cell, so the Layer Builder picks the right top cell;
      * the simulation layer ``SIM_N_SIDEWALL`` (208/0) is added, see :func:`silicon_regions`.

    The mask layers are written unchanged.
    """
    flat = gf.Component()
    flat << component
    flat.flatten()
    flat.name = cellname or component.name
    sidewall = silicon_regions(flat)["n_sidewall"]
    if not sidewall.is_empty():
        flat.add_polygon(sidewall, layer=LAYER.SIM_N_SIDEWALL)
    gdspath = Path(gdspath)
    gdspath.parent.mkdir(parents=True, exist_ok=True)
    return flat.write_gds(gdspath, with_metadata=False)


# =====================================================================================
# 8. The PDK object and the KLayout technology
# =====================================================================================
# Electrical connectivity for netlist tracing: a via joins a high-dose region to the electrode.
LAYER_CONNECTIVITY = [("P_IMPLANT_HI_DF", "VIA_DF", "ELECTRODE_LF"), ("N_IMPLANT_HI_DF", "VIA_DF", "ELECTRODE_LF")]

PDK = gf.Pdk(
    name="cornerstone_soi220a",
    version="SOI220A 1.2.0 / MPW #47 design guidelines",
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
    print(f"PDK {PDK.name}: {len(CROSS_SECTIONS)} cross-sections, {len(CELLS)} cells")
    for key, name in OFFICIAL_LAYER_NAMES.items():
        gds = tuple(getattr(LAYER, key))
        print(f"  {gds[0]:>3}/{gds[1]}  {name}")
    print("KLayout technology ->", write_klayout_tech(here / "klayout_tech"))

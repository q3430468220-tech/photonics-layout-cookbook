"""01 -- Define your own gdsfactory PDK, step by step.

Run:
    uv run python examples/00_getting_started/01_define_your_pdk.py

A PDK ("process design kit") is how gdsfactory knows a foundry process. Once a
PDK is active you can say ``layer="NPP"``, ``cross_section="rib_pn"`` or
``gf.get_component("ring_modulator")`` and gdsfactory knows what you mean.

A gdsfactory PDK has six parts. Part A of this script writes each of them by hand
for a small CORNERSTONE-220-nm-active PDK, following the official tutorial
(https://gdsfactory.github.io/gdsfactory/notebooks/08_pdk.html):

    1. LayerMap      layer name -> (GDS layer, datatype)
    2. LayerStack    z-position, thickness, material of each layer (3D, simulation)
    3. LayerViews    colours / patterns for KLayout (.lyp file)
    4. cross-sections  waveguide profiles = lists of Sections (layer, width, offset)
    5. cells         parametric devices, @gf.cell functions
    6. Pdk(...)      bundles 1-5 (+ models, routing, connectivity) and is activated

Part B shows the cookbook's real CORNERSTONE PDK, which is *generated* from the
process YAML and *extends* gdsfactory's open cspdk -- the way you would build a
PDK for your own group: start from the foundry's open PDK, add what is missing.

Outputs (build/00_getting_started/):
    tutorial_pn_phase_shifter.gds, tutorial_layers.lyp        (part A)
    cornerstone_*.gds, klayout_tech/, lumerical_straight_pn/  (part B)
"""

from __future__ import annotations

import gdsfactory as gf
from gdsfactory.technology import LayerLevel, LayerMap, LayerStack, LayerView, LayerViews, LogicalLayer
from gdsfactory.typings import Layer

from photonics_cookbook.paths import build_dir

OUT = build_dir("00_getting_started")
nm = 1e-3


def title(text: str) -> None:
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


# =============================================================================
# PART A -- a PDK written by hand
# =============================================================================

# -----------------------------------------------------------------------------
# Step 1. LayerMap: give every GDS layer a name.
#   Numbers from the CORNERSTONE design guidelines (see the process YAML).
#   Defining the class registers the layers with gdsfactory's layout object.
# -----------------------------------------------------------------------------
class LayerMapTutorial(LayerMap):
    """The CORNERSTONE 220 nm active layers this tutorial needs."""

    WG: Layer = (3, 0)  # type: ignore[assignment]   full 220 nm silicon (Si etch 2)
    SLAB: Layer = (5, 0)  # type: ignore[assignment]   100 nm slab (Si etch 3 protect)
    P: Layer = (7, 0)  # type: ignore[assignment]   low-dose p implant
    N: Layer = (8, 0)  # type: ignore[assignment]   low-dose n implant
    PPP: Layer = (9, 0)  # type: ignore[assignment]   P++ contact implant
    NPP: Layer = (11, 0)  # type: ignore[assignment]   N++ contact implant
    VIA: Layer = (12, 0)  # type: ignore[assignment]   contact via
    METAL: Layer = (13, 0)  # type: ignore[assignment]   electrodes
    FLOORPLAN: Layer = (99, 0)  # type: ignore[assignment]   cell outline


LAYER = LayerMapTutorial

# -----------------------------------------------------------------------------
# Step 2. LayerStack: what each layer becomes after fabrication (z in um).
#   Used by the 3D viewer (c.to_3d()), gplugins solvers and KLayout 2.5D.
#   mesh_order: lower number wins where volumes overlap (like Lumerical).
#   background=True extrudes a level over the whole cell (BOX, cladding).
# -----------------------------------------------------------------------------
LAYER_STACK = LayerStack(
    layers={
        "box": LayerLevel(
            layer=LogicalLayer(layer=LAYER.WG), zmin=-2.0, thickness=2.0,
            material="sio2", mesh_order=10, background=True,
        ),
        "core": LayerLevel(
            layer=LogicalLayer(layer=LAYER.WG), zmin=0.0, thickness=220 * nm,
            material="si", mesh_order=2,
        ),
        "slab": LayerLevel(
            layer=LogicalLayer(layer=LAYER.SLAB), zmin=0.0, thickness=100 * nm,
            material="si", mesh_order=2,
        ),
        "via": LayerLevel(
            layer=LogicalLayer(layer=LAYER.VIA), zmin=100 * nm, thickness=1.12,
            material="al", mesh_order=1,
        ),
        "metal": LayerLevel(
            layer=LogicalLayer(layer=LAYER.METAL), zmin=1.22, thickness=1.6,
            material="al", mesh_order=1,
        ),
        "clad": LayerLevel(
            layer=LogicalLayer(layer=LAYER.WG), zmin=0.0, thickness=1.22,
            material="sio2", mesh_order=11, background=True,
        ),
    }
)
# Implants are not 3D volumes: their doses live in the process file and are used
# by the Lumerical CHARGE export (see docs/lumerical-bridge.md).

# -----------------------------------------------------------------------------
# Step 3. LayerViews: how KLayout draws each layer (written to a .lyp file).
# -----------------------------------------------------------------------------
LAYER_VIEWS = LayerViews()
for _name, _color, _hatch in [
    ("WG", "#ff9d9d", "coarsely dotted"),
    ("SLAB", "silver", "coarsely dotted"),
    ("P", "#a1d99b", "right-hatched"),
    ("N", "#fdae6b", "left-hatched"),
    ("PPP", "#238b45", "strongly right-hatched dense"),
    ("NPP", "#d94801", "strongly left-hatched dense"),
    ("VIA", "#252525", "cross-hatched"),
    ("METAL", "#969696", "dotted"),
    ("FLOORPLAN", "green", "hollow"),
]:
    _layer = getattr(LAYER, _name)
    LAYER_VIEWS.add_layer_view(
        _name,
        LayerView(layer=(_layer.layer, _layer.datatype), color=_color, hatch_pattern=_hatch, layer_in_name=True),
    )


# -----------------------------------------------------------------------------
# Step 4. Cross-sections: a waveguide profile is a list of Sections.
#   Section(width, offset from the centre line, layer). Extruding a cross-section
#   along any path (straight, bend, spline) gives a device -- no polygon maths.
# -----------------------------------------------------------------------------
def strip(width: float = 0.45, radius: float = 10.0) -> gf.CrossSection:
    """220 nm strip waveguide."""
    return gf.cross_section.cross_section(width=width, layer="WG", radius=radius, radius_min=5.0)


def rib(width: float = 0.45, slab_width: float = 7.0) -> gf.CrossSection:
    """Rib waveguide: core on WG plus a 100 nm slab section."""
    return gf.cross_section.cross_section(
        width=width,
        layer="WG",
        sections=(gf.Section(width=slab_width, offset=0, layer="SLAB", name="slab"),),
        radius=25.0,
        radius_min=25.0,
    )


def rib_pn(
    width: float = 0.5,
    contact_spacing: float = 0.8,
    contact_width: float = 2.0,
    via_enclosure: float = 0.5,
    implant_overlap: float = 0.2,
) -> gf.CrossSection:
    """Lateral PN rib (depletion phase shifter): N on +y, P on -y, junction at the centre.

    The cookbook PDK computes the same list in photonics_cookbook.devices.pn_waveguide.
    """
    y_pp = width / 2 + contact_spacing  # rib centre -> inner edge of N++/P++
    y_c = y_pp + contact_width / 2  # centre of the contact stripes
    y_low = y_pp + implant_overlap  # low-dose implants reach under the ++ stripes
    w_slab = 2 * (y_pp + contact_width + 0.5)
    w_via = contact_width - 2 * via_enclosure
    electrical = ("electrical", "electrical")
    sections = (
        gf.Section(width=w_slab, offset=0, layer="SLAB", name="slab"),
        gf.Section(width=y_low, offset=+y_low / 2, layer="N", name="n"),
        gf.Section(width=y_low, offset=-y_low / 2, layer="P", name="p"),
        gf.Section(width=contact_width, offset=+y_c, layer="NPP", name="npp"),
        gf.Section(width=contact_width, offset=-y_c, layer="PPP", name="ppp"),
        gf.Section(width=w_via, offset=+y_c, layer="VIA", name="via_n"),
        gf.Section(width=w_via, offset=-y_c, layer="VIA", name="via_p"),
        gf.Section(width=contact_width, offset=+y_c, layer="METAL", name="metal_n",
                   port_names=("n1", "n2"), port_types=electrical),
        gf.Section(width=contact_width, offset=-y_c, layer="METAL", name="metal_p",
                   port_names=("p1", "p2"), port_types=electrical),
    )
    return gf.cross_section.cross_section(width=width, layer="WG", sections=sections, radius=25.0, radius_min=25.0)


# -----------------------------------------------------------------------------
# Step 5. Cells: parametric devices. @gf.cell caches them and gives each
#   parameter set a unique name. Cells build on other cells by reference.
# -----------------------------------------------------------------------------
@gf.cell
def pn_phase_shifter(length: float = 100.0, cross_section: str = "rib_pn") -> gf.Component:
    """A straight extruded with ``rib_pn`` plus a floorplan box."""
    c = gf.Component()
    wg = c << gf.components.straight(length=length, cross_section=cross_section)
    c.add_ports(wg.ports)
    b = c.dbbox()
    c.add_polygon([(b.left, b.bottom), (b.right, b.bottom), (b.right, b.top), (b.left, b.top)], layer="FLOORPLAN")
    return c


# -----------------------------------------------------------------------------
# Step 6. The Pdk object bundles everything; activate() makes it the current one.
# -----------------------------------------------------------------------------
TUTORIAL_PDK = gf.Pdk(
    name="tutorial_cornerstone_mini",
    layers=LAYER,
    layer_stack=LAYER_STACK,
    layer_views=LAYER_VIEWS,
    cross_sections={"strip": strip, "rib": rib, "rib_pn": rib_pn},
    cells={"pn_phase_shifter": pn_phase_shifter, "straight": gf.components.straight},
)


def part_a() -> None:
    title("PART A -- a hand-written PDK")
    TUTORIAL_PDK.activate()
    print(f"active PDK      : {gf.get_active_pdk().name}")
    print(f"layer 'NPP'     : {gf.get_layer_tuple('NPP')}")
    print(f"cross-sections  : {sorted(TUTORIAL_PDK.cross_sections)}")
    print(f"cells           : {sorted(TUTORIAL_PDK.cells)}")

    xs = gf.get_cross_section("rib_pn")
    print("\nrib_pn sections (name, layer, offset, width):")
    for s in xs.sections:
        print(f"  {s.name:<10} {s.layer!s:<6} {s.offset:+7.3f} {s.width:7.3f}")

    c = gf.get_component("pn_phase_shifter", length=200)
    print(f"\npn_phase_shifter ports: {[(p.name, p.port_type) for p in c.ports]}")
    gds = c.write_gds(OUT / "tutorial_pn_phase_shifter.gds")
    lyp = LAYER_VIEWS.to_lyp(OUT / "tutorial_layers.lyp")
    print(f"written {gds}\nwritten {lyp}   (KLayout: File > Load Layer Properties)")


# =============================================================================
# PART B -- the cookbook PDK: generated from the process YAML, extends cspdk
# =============================================================================
def part_b() -> None:
    from photonics_cookbook.lumerical import export_lumerical, info_from_component, ports_from_component
    from photonics_cookbook.pdk import activate_pdk, write_klayout_tech

    title("PART B -- the generated CORNERSTONE active PDK")
    # Cells are cached by their arguments only, so drop the part-A cells before
    # switching PDK (otherwise e.g. straight(cross_section="rib_pn") would come back
    # with the tutorial's geometry). In real projects use one PDK per script.
    gf.clear_cache()
    pdk = activate_pdk("cornerstone_si220_active")
    print(f"active PDK  : {pdk.name}  (extends {[p.name for p in pdk.base_pdks]})")
    print(f"layers      : {len(pdk.layers.__members__)}   cells: {len(pdk.cells)}   cross-sections: {len(pdk.cross_sections)}")

    # same numbers as the hand-written LayerMap -- both come from the same design manual
    for name in ("WG", "SLAB", "P", "N", "PPP", "NPP", "VIA", "METAL"):
        assert gf.get_layer_tuple(name) == tuple(getattr(LayerMapTutorial, name)), name
    print("hand-written and generated LayerMaps agree on WG, SLAB, P, N, PPP, NPP, VIA, METAL")

    print("\nLayerStack levels:")
    for name, lvl in pdk.layer_stack.layers.items():
        print(f"  {name:<13} z = {lvl.zmin:+.3f} .. {lvl.zmin + lvl.thickness:+.3f} um  {lvl.material:<5} "
              f"Lumerical: {lvl.info.get('lumerical_optical', '')}")

    # cookbook cells and upstream (cspdk) cells live side by side in one PDK
    ring = gf.get_component("ring_modulator")
    pn = gf.get_component("straight_pn", length=500)
    mmi = gf.get_component("mmi1x2")  # a cspdk cell, unchanged
    for comp, fname in ((ring, "cornerstone_ring_modulator.gds"), (pn, "cornerstone_straight_pn.gds"), (mmi, "cornerstone_mmi1x2.gds")):
        print(f"written {comp.write_gds(OUT / fname)}")

    tech = write_klayout_tech("cornerstone_si220_active", OUT / "klayout_tech")
    print(f"KLayout technology files in {tech}")

    # a PDK device goes straight to Lumerical: CHARGE / FDE across the PN waveguide
    res = export_lumerical(
        OUT / "cornerstone_straight_pn.gds",
        "cornerstone_si220_active",
        OUT / "lumerical_straight_pn",
        ports=ports_from_component(pn),
        info=info_from_component(pn),
    )
    print(res)


if __name__ == "__main__":
    part_a()
    part_b()

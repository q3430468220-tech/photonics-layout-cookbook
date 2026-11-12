# Defining a gdsfactory PDK

Before you can draw anything for a foundry, gdsfactory has to know the foundry's process: which GDS layer is which, how thick everything is, how to display it, and which waveguide profiles and devices exist. That knowledge is a **PDK** (`gf.Pdk`). This page explains its parts, walks through the hand-written tutorial PDK, and then shows how the cookbook generates its real CORNERSTONE PDK from a process file on top of gdsfactory's open `cspdk`.

```bash
uv run python examples/00_getting_started/01_define_your_pdk.py   # the tutorial
uv run photonics-cookbook pdk-info                                   # what the cookbook PDK contains
uv run photonics-cookbook write-klayout-tech -o build/klayout_tech   # .lyp / .lyt for KLayout
```

The official gdsfactory reference is the [PDK notebook](https://gdsfactory.github.io/gdsfactory/notebooks/08_pdk.html); the examples here follow it and the structure of [`cspdk`](https://github.com/gdsfactory/cspdk).

## The six parts of a PDK

| part | gdsfactory class | what it answers | example |
|---|---|---|---|
| LayerMap | `gf.technology.LayerMap` | which GDS numbers does a layer name mean? | `NPP = (11, 0)` |
| LayerStack | `LayerStack` of `LayerLevel` | where is each layer in z, what material? | `core`: z = 0 … 0.22 µm, Si |
| LayerViews | `LayerViews` of `LayerView` | how does KLayout draw it? (`.lyp`) | NPP: orange, dense hatch |
| cross-sections | functions returning `gf.CrossSection` | what is a waveguide profile? | `rib_pn`: core + slab + N/P + N++/P++ + vias + metal |
| cells | `@gf.cell` functions | which parametric devices exist? | `ring_modulator(radius=10)` |
| everything else | `gf.Pdk(...)` fields | circuit models, routing strategies, layer transitions, connectivity, constants | taken over from `cspdk` |

Once a PDK is active, every name resolves through it: `layer="NPP"`, `cross_section="rib_pn"`, `gf.get_component("ring_modulator")`. Since gdsfactory 9.29 **no PDK is active by default**, so always activate one before drawing. Use one PDK per script: cells are cached by their arguments only, so after switching PDKs in the same Python session call `gf.clear_cache()` first (the tutorial does this between its two parts).

## Part A: writing a PDK by hand

`examples/00_getting_started/01_define_your_pdk.py` builds `tutorial_cornerstone_mini` in six short steps.

**1. LayerMap.** A class with one attribute per layer. Defining it registers the layers with gdsfactory.

```python
class LayerMapTutorial(LayerMap):
    WG: Layer = (3, 0)      # full 220 nm silicon
    SLAB: Layer = (5, 0)    # 100 nm slab
    N: Layer = (8, 0)
    NPP: Layer = (11, 0)
    ...
```

**2. LayerStack.** One `LayerLevel` per physical layer, with `zmin`, `thickness`, `material` and a `mesh_order` (lower wins where volumes overlap, as in Lumerical). `background=True` extrudes BOX and cladding over the whole cell. Implants are not volumes; their doses stay in the process file and are used by the CHARGE export.

**3. LayerViews.** `LayerView(layer=(11, 0), color="#d94801", hatch_pattern="strongly left-hatched dense")` for each layer; `LAYER_VIEWS.to_lyp("layers.lyp")` writes a KLayout layer-properties file.

**4. Cross-sections.** A cross-section is a list of `gf.Section(width, offset, layer)` around a main core section. The PN rib is the interesting one:

```python
gf.cross_section.cross_section(width=0.5, layer="WG", sections=(
    gf.Section(width=7.1, offset=0,      layer="SLAB"),
    gf.Section(width=1.25, offset=+0.625, layer="N"),     # junction at the centre
    gf.Section(width=1.25, offset=-0.625, layer="P"),
    gf.Section(width=2.0,  offset=+2.05,  layer="NPP"),
    gf.Section(width=1.0,  offset=+2.05,  layer="VIA"),
    gf.Section(width=2.0,  offset=+2.05,  layer="METAL", port_names=("n1", "n2"), port_types=("electrical", "electrical")),
    ...))
```

Extruding it along any path gives a device without any polygon maths: `gf.components.straight(length=500, cross_section="rib_pn")` is a PN phase shifter section, and the same profile along an arc would be a doped bend.

**5. Cells.** `@gf.cell` functions; they cache results and give every parameter set a unique cell name. Cells reference other cells (`c << gf.components.straight(...)`) to build hierarchy.

**6. The Pdk.** `gf.Pdk(name=..., layers=..., layer_stack=..., layer_views=..., cross_sections={...}, cells={...})`, then `.activate()`.

## Part B: the cookbook PDK, generated and extending cspdk

Writing a PDK from scratch duplicates what the foundry already published. For CORNERSTONE, gdsfactory maintains the open [`cspdk`](https://github.com/gdsfactory/cspdk) with passive layers, cells and circuit models, but no implants, vias or electrodes. The cookbook PDK takes `cspdk.si220` and adds what an active device needs:

```python
from photonics_cookbook.pdk import activate_pdk
pdk = activate_pdk("cornerstone_si220_active")      # or:
from photonics_cookbook.pdk.cornerstone_si220_active import PDK, LAYER
```

`photonics_cookbook.pdk.builder.build_pdk()` generates every part from `process/data/cornerstone_si220_active.yaml`:

| PDK part | generated by | from the YAML |
|---|---|---|
| LayerMap | `layer_map_from_process` | all `cspdk` layers + every layer's `name` and `gds` (conflicts are errors) |
| LayerStack | `layer_stack_from_process` | `background`, `zmin`/`thickness`/`material`; `core = WG - GRA` and a `GRA` level for the 70 nm grating etch, like cspdk; Lumerical material names in each level's `info`; works with `c.to_3d()` |
| LayerViews | `layer_views_from_process` | all `cspdk` views + `color`/`hatch` of the new layers |
| cross-sections | `make_rib_pn` | `rib_pn` from the role → layer-name map; geometry in `devices/pn_waveguide.py` |
| cells | `cells.CELLS` | `ring_modulator`, `straight_pn` + all `cspdk` cells (via `base_pdks`) |
| models, routing, connectivity | `Pdk(base_pdks=[cspdk])` | copied from `cspdk.si220` |

Because of `base_pdks=[cspdk]`, every upstream cell keeps working (`gf.get_component("mmi1x2")`), and cookbook cells sit next to them in the same layout. `uv run photonics-cookbook check-pdk cornerstone_si220_active` verifies that every layer the process shares with `cspdk` has the same name and numbers, and lists the ones the cookbook adds:

```text
  [ok       ] core          WG         (3, 0)     upstream WG = (3, 0)     same name and numbers
  [extension] npp           NPP        (11, 0)                             not upstream -> added by the cookbook PDK
```

## Making a PDK for another foundry

1. Start a process YAML (`photonics-cookbook bootstrap-process <pdk.module> -o my.yaml` drafts one from an installed gdsfactory PDK, or copy `_template.yaml`).
2. Give every layer its role, the upstream PDK's **name** where the layer already exists, GDS numbers, stack and physics; add `color`/`hatch` for new layers.
3. Point `upstream_pdk.modules` at the foundry's gdsfactory package if there is one; without it the PDK is built from the YAML alone.
4. `photonics-cookbook check-pdk` and `pdk-info`, then `activate_pdk("my_process")` or `activate_pdk("path/to/my.yaml")`.

The same file then drives the Lumerical bridge, so a new foundry immediately gets FDTD, MODE and CHARGE exports as well. See [process-adapters.md](process-adapters.md) for the file format.

## Viewing the layers in KLayout

`photonics-cookbook write-klayout-tech -o build/klayout_tech` writes `layers.lyp`, `tech.lyt` and `d25/<pdk>.lyd25` (a 2.5D view macro generated from the LayerStack). In KLayout, either load `layers.lyp` through *File → Load Layer Properties*, or register the whole technology through *Tools → Manage Technologies → Import Technology* and select `tech.lyt`. If you use the `klive` plug-in, `c.show()` sends a component to KLayout with the active PDK's layer views.

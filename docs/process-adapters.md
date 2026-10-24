# Process adapters: how one recipe fits many foundries

Device recipes in this cookbook never use raw GDS numbers. They draw on *roles* such as `core`, `slab`, `n`, `ppp`, `via` and `metal`, and a process file maps each role to the layer, stack and physics of one foundry platform. Swapping the process file re-targets the recipe; nothing else changes.

The same file is the single source of truth for both halves of the cookbook: `photonics_cookbook.pdk` generates a complete gdsfactory PDK from it (see [pdk-tutorial.md](pdk-tutorial.md)), and `photonics_cookbook.lumerical` uses it to write FDTD, MODE and CHARGE scripts.

```bash
uv run photonics-cookbook processes                            # list shipped processes
uv run photonics-cookbook show-process cornerstone_si220_active
uv run photonics-cookbook check-pdk cornerstone_si220_active   # compare with cspdk's LAYER map
uv run photonics-cookbook pdk-info cornerstone_si220_active     # the gdsfactory PDK built from it
```

## File format

Process files are YAML, in `src/photonics_cookbook/process/data/`. Units are micrometres and cm⁻³; z = 0 is the BOX / device-layer interface. Write exponents with a sign (`1.0e+18`) because YAML 1.1 reads `1.0e18` as a string; the loader converts it anyway, but other tools may not.

```yaml
name: cornerstone_si220_active
foundry: CORNERSTONE (University of Southampton)
upstream_pdk:                       # optional: gdsfactory PDK that the cookbook PDK extends
  python_package: cspdk
  modules: [cspdk.si220, cspdk.si220.cband]
materials:                          # key -> Lumerical database names
  si:   {kind: semiconductor, optical: "Si (Silicon) - Palik", charge: "Si (Silicon)", mesh_order: 2}
background:                         # unpatterned layers
  - {name: box, material: sio2, zmin: -2.0, zmax: 0.0}
layers:                             # role -> PDK name + GDS layer + physics (+ display)
  core: {name: WG,   gds: [3, 0],  kind: structure, material: si, zmin: 0.0, thickness: 0.22}
  slab: {name: SLAB, gds: [5, 0],  kind: structure, material: si, zmin: 0.0, thickness: 0.10}
  n:    {name: N,    gds: [8, 0],  kind: doping, dopant: n, concentration: 1.1e+18, color: "#fdae6b", hatch: left-hatched}
  via:  {name: VIA,  gds: [12, 0], kind: via, material: al, zmin: 0.10, thickness: 1.12}
```

| `kind` | meaning | required fields |
|---|---|---|
| `structure` | material extruded from `zmin` over `thickness` where drawn | `material`, `zmin`, `thickness` |
| `etch` | removes `depth` from the top of `core` where drawn (e.g. grating teeth) | `material` (fill), `depth` |
| `doping` | implant through the silicon where drawn | `dopant` (`n`/`p`), `concentration` |
| `via`, `metal` | conductors; vias land on the local silicon top in CHARGE | `material`, `zmin`, `thickness` |
| `annotation` | labels, outlines, DRC helpers (ignored by simulation) | none |

Every layer may also set `name` (its name in the gdsfactory PDK and in KLayout; defaults to the role in upper case — use the upstream PDK's name for layers it already has), `color` and `hatch` (KLayout display of layers the upstream PDK lacks; hatch names as in KLayout, e.g. `left-hatched`, `strongly right-hatched dense`), `mesh_order` and `description`.

The loader validates the file: a `core` layer is mandatory, GDS numbers and PDK names must be unique, materials must be defined and concentrations must be in a plausible range.

## Standard roles

| role | meaning | role | meaning |
|---|---|---|---|
| `core` | full-thickness waveguide silicon | `npp` / `ppp` | high-dose N++ / P++ for ohmic contacts |
| `slab` | partially etched (rib) silicon | `via` | contact from metal to silicon |
| `shallow_etch` | shallow etch (grating teeth) | `metal` | first metal / electrodes |
| `n` / `p` | low-dose junction implants | `heater`, `pad` | heater and pad layers |
| `np` / `pp` | medium-dose N+ / P+ (optional) | `ge`, `label`, `outline` | germanium, text, cell outline |

A recipe skips optional roles that a process does not define. For example, the ring modulator draws the N+ / P+ intermediate implants only if the process has `np` / `pp` layers; CORNERSTONE does not, so the low-dose implants are extended under the contacts instead.

## Adding a foundry

Start from `_template.yaml`, or draft a file from any installed gdsfactory PDK:

```bash
uv run photonics-cookbook bootstrap-process cspdk.si220 -o my_process.yaml
```

The draft contains every layer of the PDK's `LayerStack` plus the layers that only appear in its `LAYER` map (often implants and labels), each with its PDK `name`. Rename the keys to the standard roles, set `kind`, Lumerical material names, implant type and concentration, check the vertical stack against the design manual, add `references:` pointing to the public documents you used, then run `check-pdk`, `pdk-info` and `uv run pytest`. `activate_pdk("path/to/my_process.yaml")` gives you the gdsfactory PDK. Please never commit data that is under NDA; open PDKs and public design guidelines only.

## Where the CORNERSTONE numbers come from

Passive layers (`WG` 3/0, `SLAB` 5/0, `GRA` 6/0, `HEATER` 39/0, `PAD` 41/0, `FLOORPLAN` 99/0, `LBL` 100/0) use the names and numbers of gdsfactory's `cspdk`, which `check-pdk` verifies. The active layers (P 7/0, N 8/0, P++ 9/0, N++ 11/0, via 12/0, electrode 13/0) and doping levels come from the public CORNERSTONE 220 nm SOI active MPW design guidelines and the public layer table of the Luceda CORNERSTONE PDK. Always confirm them against the guidelines of the call you submit to.

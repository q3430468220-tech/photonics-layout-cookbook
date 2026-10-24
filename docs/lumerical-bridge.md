# The GDS → Lumerical bridge

The bridge turns a GDS file plus a process file into Lumerical scripts. It never needs the Python object that drew the layout, so it works for any GDS. This page explains the three routes, the coordinate conventions and the known pitfalls.

```python
from photonics_cookbook.lumerical import export_lumerical, info_from_component, ports_from_component

res = export_lumerical(
    "build/01_ring_modulator/ring_modulator.gds",   # any GDS
    "cornerstone_si220_active",                     # process name or path to a YAML file
    "build/01_ring_modulator/lumerical",            # output folder (ASCII path!)
    ports=ports_from_component(c),                  # optional: optical ports -> FDTD ports
    info=info_from_component(c),                    # optional: cut line, bend radius, contacts
)
print(res)
```

The same is available on the command line: `uv run photonics-cookbook to-lumerical my.gds --process cornerstone_si220_active --cut 5.45,0 14.55,0 --origin 10,0 --norm-length 46.5 --bend-radius 10`.

## Route 1: `gdsimport` (3D, FDTD / MODE)

`<cell>_geometry3d.lsf` calls the documented [`gdsimport`](https://optics.ansys.com/hc/en-us/articles/360034406974-gdsimport-Script-command) command once per drawn layer, `gdsimport(file, cell, "L:D", material, zmin, zmax)`, with z-range and optical material from the process file, and adds the unpatterned background layers as rectangles. Overlaps are resolved with Lumerical mesh orders (metal 1, silicon 2, oxide 3). Partial etches (kind `etch`, for example the 70 nm grating etch) are imported as an oxide copy with mesh order 1 so that they cut into the silicon. Only layers that actually contain shapes are imported.

`<cell>_fdtd3d.lsf` adds a 3D FDTD region around the optical layers. Its boundaries are pulled 1 µm inside every optical port so the waveguides run through the PML, and one Lumerical port is created per gdsfactory optical port with the correct injection axis and direction. Full 3D FDTD of a resonator is slow; for ring spectra, the Ansys workflow (FDTD of the coupling region, FDE of the ring waveguide, INTERCONNECT for the ring) is usually the better choice.

## Route 2: Layer Builder and `.lbr` process files

`<cell>_layerbuilder.lsf` creates a [Layer Builder](https://optics.ansys.com/hc/en-us/articles/360034382394-Layer-builder-Simulation-object) object from script. The stack is cut into contiguous, non-overlapping z-slices; each slice gets a Boolean pattern expression over GDS layers, for example `(3:0 or 5:0)` for the bottom 100 nm of a rib waveguide and `(3:0)` above it. The script then calls `saveprocessfile`, so the `.lbr` file is written by Lumerical itself. Afterwards any project can reuse it with `addlayerbuilder; loadgdsfile("x.gds"); loadprocessfile("process.lbr");`.

The `.lbr` XML format is not publicly documented, which is why the cookbook does not write it directly. This route is marked experimental: a few Layer Builder property names (`"gds cell"`, `"process"`, `"start position"`) differ between versions, so every uncertain call is wrapped in `try` and reported in the script prompt.

## Route 3: 2D cross-section, CHARGE → MODE FDE

This is the route that makes active devices seamless. A cut line through the layout is intersected with every drawn layer; the lateral intervals come from the GDS and the vertical extent, materials and doses from the process file.

`<cell>_charge2d.lsf` builds a CHARGE "2D Y-Normal" simulation: silicon rectangles for `core` and `slab`, one constant-doping box per implant interval (overlapping implants add up, as in the real process), the vias that land on the anode and cathode implant layers as electrical contacts, mesh refinement at the core and at every detected PN junction, a bias sweep on the anode with the cathode grounded, and a charge monitor that saves `n, p` to `<cell>_charge.mat`. The normalisation length is the doped length of the device, so currents and capacitances refer to the real device. Physics models follow the Ansys PN phase-shifter example: high-field (velocity saturation) mobility is switched on, which is off in the database default.

`<cell>_fde2d.lsf` builds a MODE FDE "2D Y normal" solver on the same frame, imports the carrier file as an `np density` grid attribute on silicon with the Soref-Bennett free-carrier model, solves the straight and bent waveguide (checking the bend direction automatically), sweeps the CHARGE bias points and reports Δn_eff, loss, VπL and, for rings, the resonance shift in pm/V.

Frame of both scripts: **x along the cut, x = 0 at the chosen origin (the waveguide centre), z vertical with z = 0 at the BOX / silicon interface, y = propagation direction.** No rotation or re-mapping is needed between CHARGE and FDE.

Cookbook cells store the right cut automatically. The ring modulator, for example, stores a radial cut through the contacted, doped arc in `c.info["lumerical"]` together with the bend radius, the doped length and the anode / cathode implant roles. For your own GDS, pass `cut=`, `origin=` and `norm_length_um=` explicitly. Check `<cell>_xsec.png` and `<cell>_xsec.json` before simulating: they show exactly what CHARGE will see.

## Running the scripts

You can open each `.lsf` in the matching Lumerical product and press Run, or let Python drive Lumerical through `lumapi`:

```python
from photonics_cookbook.lumerical.runner import run_script
run_script("charge", "build/01_ring_modulator/lumerical/ring_modulator_charge2d.lsf")
run_script("mode",   "build/01_ring_modulator/lumerical/ring_modulator_fde2d.lsf")
```

`lumapi` ships with Lumerical and is found through `LUMERICAL_ROOT` (the folder that contains `api/python`, e.g. `C:\Program Files\ANSYS Inc\v251\Lumerical`) or the usual install locations.

## Troubleshooting

| symptom | cause and fix |
|---|---|
| `failed to open data file ...~#xxx.data` in CHARGE / FDTD | The working folder contains non-ASCII characters (for example Chinese). Set `PHOTONICS_BUILD_DIR` to an ASCII path such as `D:\photonics_build` and regenerate. |
| `the cut crosses no via -- CHARGE needs contacts` | The cut line misses the contacts. Move it to the doped, contacted part of the device (for the ring: away from the coupler window and the signal-bridge gap). |
| material name not found | Database names differ slightly between versions. Fix the `optical` / `charge` names in the process YAML; the CHARGE script prints the available CT materials. |
| `NOTE: high-field mobility not set by script` | The material property path differs in your version. Enable it in the CHARGE material GUI, or tell us the path in an issue. |
| no V-dependence in FDE | The FDE script did not find `<cell>_charge.mat`; run the CHARGE script first in the same folder. |

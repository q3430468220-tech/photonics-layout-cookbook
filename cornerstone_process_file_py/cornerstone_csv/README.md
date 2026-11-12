# cornerstone_csv: the SOI220A process as tables

`cornerstone_process_file_compiler.py` reads these tables and writes `cornerstone_process.lbr`.
The column names are those of the Ansys template (article *Layer builder - Simulation object*,
package `process_file_py.zip`), so each table can be compared with the Ansys example line by line.

Units: `process_layers.csv` in nm; `doping_process_layers.csv` in m and cm⁻³. z = 0 is the top of
the buried oxide.

Source tags:

| tag | source |
|---|---|
| [YAML] | `SOI220A/process_overview.yaml`, v1.2.0, in [cornerstone-uos/cornerstone-pdk](https://github.com/cornerstone-uos/cornerstone-pdk) |
| [DG] | CORNERSTONE Design Guidelines, 220 nm SOI Active MPW #47, October 2025 ([PDF](https://cornerstone.sotonfab.co.uk/wp-content/uploads/2025/10/CORNERSTONE-47th-Call-Design-Guidelines_final-1.pdf)) |
| [assumed] | not published; a typical value. Replace it when you have a better one. |

## process_layers.csv

| layer | GDS expression | z range (nm) | material | basis |
|---|---|---|---|---|
| Si_Substrate | background | −5000 … −2000 | Si | real wafer is about 725 µm; 3 µm kept [assumed] |
| BOX | background | −2000 … 0 | SiO2 | [DG 4] 2 µm thermal oxide |
| TOX | background | 0 … 1220 | SiO2 | [DG 4, step 25] 1 µm ± 100 nm above the 220 nm silicon |
| Air | background | 1220 … 4220 | Air (n = 1) | the metal is not passivated |
| Si_slab | `5:0` | 0 … 100 | Si_np | [DG 4] 100 nm left after the 120 nm etch |
| Si_slab_contact | `9:0 or 11:0`, grown by 300 nm | 0 … 100 | Si_np | [DG 9] high-dose regions are added to the rib-protect mask, grown by 300 nm |
| Si_core | `3:0 and not(6:0)` | 0 … 220 | Si_np | [DG 4][YAML] |
| Si_grating | `3:0 and 6:0` | 0 … 150 | Si_np | [DG 4] 70 nm grating etch |
| Via_P | `12:0 and 9:0` | 100 … 1220 | Al | via from the slab top to the metal |
| Via_N | `12:0 and 11:0` | 100 … 1220 | Al | same, on the n side |
| Electrode | `13:0` | 1220 … 2820 | Al | [DG Table 2] metal stack about 1.6 µm; also the heater |
| Detector_window | `23:0` | 420 … 1220 | Air | [DG, GDS 23] oxide etched down to 200 nm above the waveguide |

Notes:

- **Waveguide trenches.** The foundry etches 5 µm wide trenches around every shape on GDS 3; farther
  away the silicon keeps its full 220 nm [DG 5.2, 9]. The tables model the inside of the trenches,
  which is where the light is: 220 nm where GDS 3 is drawn, 100 nm where GDS 5 is drawn, nothing
  elsewhere. Draw the slab (GDS 5) at least as wide as your simulation window.
- **The via is split in two** by intersecting it with the implant below. The p-side and the n-side
  via are then separate solids, and CHARGE can put one contact on each.
- **Sidewalls are vertical** (90°). The sidewall angle is not published.
- `Si_np` is an index-perturbation material on top of `Si (Silicon) - Palik`. Without carrier or
  temperature data it is plain silicon.
- Material names must match the Lumerical database exactly; the compiler stops if one is missing.

## doping_process_layers.csv

| layer | mask | dopant, peak (cm⁻³) | profile | basis |
|---|---|---|---|---|
| P_low | `7:0` | p, 6.14e17 | Gaussian, peak 170 nm below the surface, straggle 73.7 nm | fitted, see below |
| N_low_slab | `8:0 and not(3:0)` | n, 1.67e18 | uniform over the 100 nm slab | [DG Table 2] 1.1e18 net + 5.7e17 compensated |
| N_low_sidewall | `208:0` | n, 1.67e18 | uniform over the 220 nm rib | [DG 5.2] 110 nm deep through the sidewall |
| P_high | `9:0 and not(3:0)` | p, 1e20 | uniform over the 100 nm slab | [DG Table 2] |
| N_high | `11:0 and not(3:0)` | n, 1e20 | uniform over the 100 nm slab | [DG Table 2] |
| Wafer | background | p, 1e15 | constant | [assumed] |

How the published numbers become profiles:

- **Background p implant.** The guidelines give two concentrations: 5.7e17 in the lower 100 nm of
  the silicon (region A, the slab) and 2.25e17 in the upper 120 nm (region B, which survives only
  inside the rib). It is one implant, done before the waveguide etch. A Gaussian is fitted so that
  its average over each of the two depth ranges equals the published value. The peak depth of
  170 nm is [assumed]; the straggle and peak concentration follow from the fit.
  `tests/test_process_tables.py` checks the two averages.
- **Low-dose n implant.** The published 1.1e18 is the *net* concentration after compensating the
  background p implant, so the donor density is 1.1e18 + 5.7e17 = 1.67e18.
- **Self-aligned n implant.** The n implant is done at 45° with the oxide hard mask still on the
  waveguide. It enters the rib only through the sidewall, about 110 nm deep, wherever the mask edge
  is drawn inside the core [DG 5.2]. The Layer Builder cannot derive that strip, so
  `cornerstone_technology.write_gds_for_lumerical()` computes it and writes it to the
  simulation-only layer `208:0`. The junction therefore sits 110 nm inside the n-side sidewall,
  not at the drawn mask edge.
- "Uniform" profiles are Gaussians with a straggle much larger than the layer, masked to silicon.
- Lateral scatter is 5 nm [assumed].

## Other tables

| file | content |
|---|---|
| `index_perturbation_data.csv` | `Si_np`: Soref-Bennett coefficients of Nedeljkovic, Soref and Mashanovich (2011); dn/dT = 1.87e-4 K⁻¹ at 300 K |
| `dielectric_materials.csv` | `Air`, n = 1 |
| `active_material_models.csv` | the CHARGE (CT) and HEAT (HT) model attached to each optical material |
| `pattern_variations.csv` | core width: σ = 5 nm [assumed] |
| `stack_variations.csv` | silicon ± 20 nm, slab ± 10 nm, top oxide ± 100 nm [DG 4], each read as 3σ [assumed] |

The two variation tables are only used when `STATISTICAL_PROCESS_FILE = True` in the compiler.

## Known inconsistencies in the public sources

| quantity | design guidelines [DG] | process_overview.yaml [YAML] | used here |
|---|---|---|---|
| buried oxide | 2 µm | 3.0 µm | 2 µm |
| top cladding | 1 µm ± 100 nm | 2.0 µm ± 0.2 | 1 µm |
| electrode minimum gap | 2 µm | 4.0 µm (also the official DRC deck) | 4 µm in the DRC |

The stack values follow the guidelines, because they describe the active process step by step and
agree with the `layerstack.png` in the same repository. The YAML values equal those of the passive
platform. Ask CORNERSTONE before relying on either for a tape-out.

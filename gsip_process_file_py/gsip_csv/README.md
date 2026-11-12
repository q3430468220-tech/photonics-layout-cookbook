# gsip_csv: the teaching process as tables

Reference for [chapter 3, the process file](../README.md) of the [course](../../README.md): every
table, and the source of every number in it.

`gsip_process_file_compiler.py` reads these tables and writes `gsip_process.lbr`. The column
names are those of the Ansys template (article *Layer builder - Simulation object*, section
"Creating a process file using Python script"), so each table can be compared with the Ansys
example line by line.

Units: `process_layers.csv` in nm; `doping_process_layers.csv` in m and cm⁻³. z = 0 is the top of
the buried oxide.

## Where the numbers come from

This is a teaching process. No foundry stands behind it, and every number has one of four origins:

| tag | source |
|---|---|
| [B] | L. Chrostowski and M. Hochberg, *Silicon Photonics Design*, Cambridge University Press 2015: Table 10.1 (process parameters), Table 10.2 (GDS layer map), Sec. 6.2 (doping levels). The book distributes its Generic Silicon Photonics (GSiP) kit "with no restrictions to its distribution". |
| [BJ] | T. Baehr-Jones et al., *A 25 Gb/s Silicon Photonics Platform*, [arXiv:1203.0767](https://arxiv.org/abs/1203.0767): the published process the book's table refers to. |
| [GF] | [gdsfactory](https://github.com/gdsfactory/gdsfactory) generic PDK (MIT licence), `gpdk/layer_map.py` and `gpdk/layer_stack.py`. Its layer map is "based on book … Silicon Photonics Design … page 353". |
| [T] | teaching value chosen for this repository. The reason is given. Replace it with your foundry's number. |

A real PDK gives you all of these numbers, and many more, under NDA. Nothing in the flow changes
when you swap them in.

## process_layers.csv

The tests of `tests/test_process_tables.py` tie every row of this table to the PDK: the GDS layer
number of the row (and the layer under a via), its material, and its sidewall angle must equal
those of `gsip_technology.py`. The heights of the rows that the stack table lists must equal the
heights there, and the heights of the other rows (via 1 on the heater, pad opening, deep trench, undercut)
are checked against the stack and the constants of the technology file.

| layer | GDS expression | z range (nm) | material | basis |
|---|---|---|---|---|
| Si_Substrate | background | −12000 … −2000 | Si | [GF] 10 µm kept; a real wafer is about 725 µm |
| BOX | background | −2000 … 0 | SiO2 | [B][BJ] 2 µm |
| TOX | background | 0 … 5700 | SiO2 | [T] up to 0.5 µm above metal 3 |
| Si_slab150 | `2:0` | 0 … 150 | Si_np | [GF] 70 nm grating etch; [B] gives 60 nm and 60 to 70 nm as the useful range |
| Si_slab90 | `3:0` | 0 … 90 | Si_np | [B] 130 nm rib etch |
| Si_core | `1:0` | 0 … 220 | Si_np | [B][BJ][GF] |
| Ge | `5:0` | 220 … 720 | Ge | [B][BJ][GF] 500 nm on the silicon |
| SiN | `34:0` | 320 … 670 | Si3N4 | [GF] |
| Via_contact_P | `40:0 and 25:0` | 90 … 1100 | Al | [GF] slab top to metal 1 |
| Via_contact_N | `40:0 and 24:0` | 90 … 1100 | Al | same, on the n side |
| Metal1 | `41:0` | 1100 … 1800 | Al | [GF] |
| Heater | `47:0` | 1100 … 1250 | TiN | [GF] level; [T] 150 nm thick |
| Via1_on_metal1 | `44:0 and 41:0` | 1800 … 2300 | Al | [GF] |
| Via1_on_heater | `44:0 and 47:0` | 1250 … 2300 | Al | starts on the thinner film |
| Metal2 | `45:0` | 2300 … 3000 | Al | [GF] |
| Via2 | `43:0` | 3000 … 3200 | Al | [GF] |
| Metal3 | `49:0` | 3200 … 5200 | Al | [GF] thick top metal for pads |
| Pad_opening | `46:0` | 5200 … 5700 | Air | [T] passivation removed over a pad |
| Deep_trench | `4:0` | −7000 … 5700 | Air | [T] through the oxide, 5 µm into the substrate |
| Undercut | `6:0` | −7000 … −2000 | Air | [GF] 5 µm of substrate removed below the oxide |

Notes:

- **One GDS layer can become two process layers.** The contact via is intersected with the implant
  below it. The p-side and the n-side via are then separate solids, and CHARGE can put one contact
  on each. Via 1 is split the same way, because it starts lower on the heater film than on metal 1.
- **The heater thickness is a teaching value.** The gdsfactory generic stack carries a 0.75 µm
  placeholder. Sputtered TiN heaters are 0.1 to 0.2 µm thick, so 150 nm is used.
- **Sidewalls are vertical** (90°). A generic process has no published sidewall angle [T]. Exercise:
  set `sidewall_angle` of `Si_core` to 85 and rerun step 2. The test
  `test_sidewall_angle_is_the_technology_value` then fails until `SIDEWALL_ANGLE` in
  `gsip_technology.py` is changed to the same value.
- **Vias and metals are aluminium.** Real processes use tungsten plugs and copper or aluminium
  wiring. Lumerical's CHARGE and HEAT database has aluminium, which is enough for this device.
- `Si_np` is an index-perturbation material on top of `Si (Silicon) - Palik`. Without carrier or
  temperature data it is plain silicon.
- Ge, SiN, the pad opening, the deep trench and the undercut are not used by the ring modulator.
  They are in the tables so that the process file covers every layer of the PDK.

## doping_process_layers.csv

| layer | mask | dopant, concentration (cm⁻³) | basis |
|---|---|---|---|
| N | `20:0` | n, 5e17 | [B][BJ] |
| P | `21:0` | p, 7e17 | [B][BJ] |
| N_plus | `22:0` | n, 3e18 | [B] Sec. 6.2 |
| P_plus | `23:0` | p, 2e18 | [B] Sec. 6.2 |
| N_plusplus | `24:0` | n, 5e20 | [B][BJ] |
| P_plusplus | `25:0` | p, 1.9e20 | [B]; [BJ] quotes 1.7e20 |
| Ge_N, Ge_P | `26:0`, `27:0` | 1e19 | [T] not used by the ring modulator |
| Wafer | background | p, 1e15 | [T] |

How the profiles are modelled:

- **Flat in depth.** Every silicon implant is a Gaussian whose straggle (1 µm) is much larger than
  the 220 nm layer. The concentration is constant over the silicon, in the core and in the slab
  alike. This is the abrupt-junction picture of the textbook, which lets you compare CHARGE with
  the textbook formulas.
- **Nested masks.** In the cross-section `rib_pn` the N mask covers the whole n side, N+ everything
  beyond 0.65 µm and N++ everything beyond 1.25 µm, as in gdsfactory's generic `pn` cross-section.
  The concentrations add up: the N+ region holds 3.5e18, the contact region 5.035e20.
- **Lateral scatter** is 20 nm [T].

Step 3 of the simulations checks this table against the doping CHARGE actually sees. The solver's
net doping is averaged over each region of its mesh, with the nested masks added, and compared with
these values. All six regions agree within 0.5 %. The check tests concentration and lateral position.
It does not test depth, because the profiles are flat in depth by construction.

## Other tables

| file | content |
|---|---|
| `index_perturbation_data.csv` | `Si_np`: Soref-Bennett coefficients of Nedeljkovic, Soref and Mashanovich (2011); dn/dT = 1.87e-4 K⁻¹ at 300 K [T], the temperature term of the silicon index |
| `dielectric_materials.csv` | `Air`, n = 1 |
| `active_material_models.csv` | the CHARGE (CT) and HEAT (HT) model attached to each optical material |
| `material_property_overrides.csv` | the TiN heater film: see below |
| `pattern_variations.csv` | core width: σ = 5 nm [T] |
| `stack_variations.csv` | silicon thickness σ = 3.3 nm, slab thickness σ = 2 nm [T] |

**The TiN heater film.** Lumerical's CHARGE and HEAT database has no TiN. The compiler attaches the
aluminium model to the optical material `TiN - Palik` and overrides four numbers:

| property | value | basis |
|---|---|---|
| thermal conductivity | 28 W m⁻¹ K⁻¹ | [T] bulk TiN is about 29 |
| mass density | 5400 kg m⁻³ | bulk TiN |
| specific heat | 600 J kg⁻¹ K⁻¹ | bulk TiN |
| electrical conductivity | 6.67e5 S m⁻¹ | [T] 1.5 µΩ·m, which gives 10 Ω/sq at 150 nm |

The electrical value is checked against `TIN_RESISTIVITY` of `gsip_technology.py` by
`test_heater_film_properties`. The two variation tables are only used when
`STATISTICAL_PROCESS_FILE = True` in the compiler.

## What a real process file adds

- measured implant profiles instead of flat ones, and a sidewall angle;
- the foundry's own materials: silicide, tungsten plugs, copper, the exact oxides and nitrides;
- process corners that come from wafer data, not from round numbers;
- everything the photonic layers do not show: stress liners, fill, the full back end.

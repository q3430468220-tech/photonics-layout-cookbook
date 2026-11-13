# photonics-layout-cookbook

A hands-on tutorial for silicon photonics design, with [gdsfactory](https://github.com/gdsfactory/gdsfactory)
for the layout and Ansys Lumerical for the simulation. It starts from a PDK (process design kit),
draws a microring modulator with it, and simulates that layout: FDTD for the coupler, MODE for the
waveguide, CHARGE and HEAT for the junction and the heater, INTERCONNECT for the circuit.

[English](README.md) | [简体中文](README_zh-CN.md)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![gdsfactory](https://img.shields.io/badge/layout-gdsfactory%209-6f42c1)
![lumerical](https://img.shields.io/badge/simulation-Ansys%20Lumerical-orange)
![version](https://img.shields.io/badge/version-0.3-2f8f5b)

A common way to simulate a ring modulator is to draw it inside the simulator and type in the
layer stack by hand. When you design for a foundry, the process is fixed and the layout is what
you deliver, so the simulation has to show what that layout becomes on that process. This
repository does that for one device, from the layout to the circuit, in code you can run and
change.

<p align="center"><img src="assets/design_flow.png" width="100%" alt="Design flow: layout, device simulation, compact model, circuit simulation, with the PDK underneath"></p>

*The design flow. The figure follows a slide from the Ansys and Tower Semiconductor workshop
(2025). Its layouts, plots and numbers come from this repository.*

The process is a teaching process called GSiP, short for generic silicon photonics. It is written
down twice: as a gdsfactory PDK for layout, and as a process file for Lumerical's Layer Builder,
the tool that turns a layout file (GDS) into a 3D structure. Tests check that the two agree. The
device is drawn with the first and simulated with the second, so no simulation script defines the
structure by hand: thicknesses, materials and doping all come from the process file.

## Tutorial

Five chapters, meant to be read in order. The first two need no Lumerical.

| | chapter | what it covers |
|---|---|---|
| 1 | [The PDK](docs/pdk.md) | layers, stack, cross-sections and design rules, written as code |
| 2 | [The device](docs/device.md) | drawing the ring modulator, then checking it with a design-rule check (DRC) and a connectivity check |
| 3 | [The process file](gsip_process_file_py/README.md) | the same process as tables for the Layer Builder, and how to verify it |
| 4 | [The simulations](lumerical_simulations/ring_modulator/README.md) | seven steps from the coupler to the circuit, with the pitfalls of each |
| 5 | [Your own foundry](docs/your_foundry.md) | moving the flow to a real PDK without leaking NDA data |

## Quick start

You need Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/). If you plan to run the
simulations, clone into a path without non-ASCII characters; Lumerical solvers can fail otherwise.

**Layout and tests** (no Lumerical needed):

```bash
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync

uv run python gsip_technology.py     # list the layers and the stack, write the layer colours for KLayout
uv run python rm_builder.py          # draw the ring modulator, run the DRC, write rm_ring.gds
uv run pytest                        # 85 tests
```

`rm_builder.py` ends with `DRC passed: 0 errors, 0 warnings`. You can open `rm_ring.gds` in
[KLayout](https://www.klayout.de), a free layout viewer; the layer colours are in
`klayout_tech/layers.lyp`.

**Figures** (no Lumerical needed). The simulation results are kept in the repository, so every
figure of chapter 4 can be redrawn from them. Each one has a script in `figures/`, for example:

```bash
uv run python lumerical_simulations/ring_modulator/figures/fig2_passive.py
```

**Simulations** (Lumerical with FDTD, MODE, CHARGE, HEAT and INTERCONNECT). The scripts look for
Lumerical in its usual install folders; set `LUMERICAL_ROOT` if yours is elsewhere. Run the steps
in order. Each one writes its results into its own folder, and chapter 4 explains what it does.
The run times are from the author's machine.

```bash
export LUMERICAL_ROOT=/opt/lumerical/v251        # PowerShell: $env:LUMERICAL_ROOT = "C:\Program Files\ANSYS Inc\v251\Lumerical"
uv run python gsip_process_file_py/gsip_process_file_compiler.py   # optional: rebuild gsip_process.lbr from the CSV tables

cd lumerical_simulations/ring_modulator/scripts
uv run python layer_builder_check.py             # step 0, half a minute
uv run python coupling_coefficient_fdtd.py       # step 1, about 30 minutes
uv run python passive_mode_fde.py                # step 2, about 7 minutes
uv run python charge_profile.py                  # step 3, about 9 minutes
uv run python heat_profile.py                    # step 4, about 3 minutes
uv run python active_mode_fde.py                 # step 5, about 1 minute
uv run python ring_modulator_interconnect.py     # step 6, under 1 minute
```

## The PDK

<p align="center"><img src="assets/pdk_stack.png" width="100%" alt="Cross-section of the teaching process: the full stack to scale, and the silicon, germanium and nitride levels enlarged"></p>

*The process in one cross-section: (a) the full stack to scale, (b) the silicon, germanium and
nitride levels, stretched five times vertically. Along the bottom, labels in dark type mark what
the ring modulator uses.*

The PDK describes a teaching process. It follows the generic process in the textbook by
Chrostowski and Hochberg, with the layer numbers of the open-source gdsfactory generic PDK. It is
not the process of any foundry, and its numbers must not be used for a tape-out. The full active
processes of commercial foundries are under NDA, so a tutorial has to define a process of its own.

| group | layers (GDS layer/datatype) | notes |
|---|---|---|
| silicon | `WG` 1/0, `SLAB150` 2/0, `SLAB90` 3/0 | 220 nm core, 150 nm and 90 nm slabs |
| implants | `N` 20/0, `P` 21/0, `NP` 22/0, `PP` 23/0, `NPP` 24/0, `PPP` 25/0 | light, medium and heavy doping for n and p, 5 × 10¹⁷ to 5 × 10²⁰ cm⁻³ |
| germanium, nitride | `GE` 5/0, `GEN` 26/0, `GEP` 27/0, `WGN` 34/0 | 500 nm Ge, 350 nm SiN |
| contacts and metals | `VIAC` 40/0, `M1` 41/0, `VIA1` 44/0, `M2` 45/0, `VIA2` 43/0, `M3` 49/0, `PADOPEN` 46/0 | aluminium, three levels |
| heater | `HEATER` 47/0 | 150 nm titanium nitride (TiN), 10 Ω/sq |
| trenches | `DEEPTRENCH` 4/0, `UNDERCUT` 6/0 | facet trench, undercut for thermal isolation |

The process numbers in [gsip_technology.py](gsip_technology.py) carry a source tag: [B] the
textbook, [BJ] the paper by Baehr-Jones et al. that the textbook's process is based on, [GF] the
gdsfactory generic PDK, or [T] a teaching value chosen here, with the reason beside it.

## The ring modulator

<p align="center"><img src="assets/rm_layout.png" width="100%" alt="Layout of the ring modulator: the whole device, then silicon and implants, contacts and heater, metal 2, and all layers"></p>

*The device drawn by [rm_builder.py](rm_builder.py): the whole device (a), three groups of layers
(b to d), and all layers together (e).*

The device is a ring of rib waveguide with a 10 µm radius, next to a bus waveguide. A PN junction
covers 240° of the ring, with the n-doped side on the inside. A TiN heater runs above the core
over 270°. Metal 2 leads to five pads: a ground-signal-ground set (G-S-G) for the junction, and
two for the heater (H).

| parameter | default | notes |
|---|---|---|
| `radius` | 10 µm | circumference 62.83 µm |
| `width` | 0.5 µm | core 220 nm high, with a 90 nm slab on both sides |
| `gap` | 0.37 µm | between bus and ring; this value gives critical coupling (step 6) |
| `pn_angle` | 240° | 41.89 µm of junction, 67 % of the ring |
| `heater_angle` | 270° | 44.72 µm of heater between the landings at its two ends, 280 Ω |

The same function draws other sizes. It rejects parameters that break a design rule, for example
a radius below the 10 µm minimum, and names the rule. From the repository root:

```python
import gsip_technology as t          # importing it activates the PDK
import rm_builder as rm
from gsip_drc import run_drc

ring = rm.ring_modulator(radius=12, gap=0.40)
print(run_drc(ring).summary())       # DRC passed: 0 errors, 0 warnings
t.write_gds_for_lumerical(ring, "build/ring_r12.gds", cellname="ring_r12")
```

In Lumerical's script language, three commands turn a layout into a structure. Steps 0 to 5 all
begin this way, through `add_layer_builder` in
[scripts/common.py](lumerical_simulations/ring_modulator/scripts/common.py). Step 0 loads the whole
device; each later step loads only the section it simulates.

```text
addlayerbuilder;
loadgdsfile("rm_ring.gds");
loadprocessfile("gsip_process_file_py/gsip_process.lbr");
```

## Simulation results

The simulation runs in seven steps. Step 0 checks the structure. Steps 1 to 5 each compute one
property of the device: coupling, waveguide modes, junction, heater, modulation. Step 6 puts
those results into a circuit simulation of the ring. These results are for a teaching process and
have not been compared with a fabricated device. Chapter 4 has the method and the limits of each
step.

### Step 0: structure check

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig0_layer_builder.png" width="100%" alt="Material maps of the built structure: two vertical cuts and four horizontal cuts"></p>

This step checks what the Layer Builder built. The figure shows the materials the mode solver
sees in two vertical and four horizontal cuts. The script also lists the refractive index at ten
points, from the substrate up to metal 2, next to the material expected there. All ten agree.

### Step 1: coupling (FDTD)

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig1_coupling.png" width="100%" alt="Field in the coupler, power coupling against gap, power coupling against wavelength"></p>

κ² is the fraction of power that crosses from the bus into the ring. It drops exponentially with
the gap, from 0.118 at 200 nm to 0.0034 at 500 nm, and follows κ² = 1.26 · exp(−gap / 84.8 nm)
in that range. With a finer mesh κ² changes by 2 %, which is the accuracy of this step.

### Step 2: waveguide modes (MODE)

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig2_passive.png" width="100%" alt="Mode of the straight and the bent waveguide, index against wavelength, bend loss against radius, modes against core width"></p>

The straight rib waveguide has an effective index of 2.568 and a group index of 3.94. Bent to the
10 µm radius of the ring, its index is 2.570 and its bend loss is too small for the solver to
resolve. Loss only appears below 6 µm, so the 10 µm design rule has margin. The free spectral
range, the spacing between resonances, is 9.7 nm. Panel e shows that a 0.5 µm core is not
strictly single-mode: a second TE mode is guided, with an index only 0.011 above that of the slab.

The mesh matters here. With a uniform 20 nm mesh, the same bent waveguide gave 2.5765 in the wide
simulation window of this step and 2.5693 in the narrower window that step 5 uses. No mesh line
sat on the silicon surfaces, and where the lines fell depended on the window. The scripts now put
a mesh line on every silicon surface, and both windows give 2.570.

### Step 3: PN junction (CHARGE)

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig3_charge.png" width="100%" alt="Doping map, carriers at two biases, carrier profiles, capacitance, RC bandwidth, doping check"></p>

The junction capacitance falls from 0.40 fF/µm at 0 V to 0.21 fF/µm at 4 V reverse bias, and the
series resistance is 150 Ω at 0 V. For the 41.89 µm junction that gives an RC bandwidth of 64 GHz
at 0 V, rising to 131 GHz at 4 V. Panel g compares the doping the solver sees with the process
tables; they agree within 0.5 %.

### Step 4: heater (HEAT)

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig4_heat.png" width="100%" alt="Temperature map, vertical temperature profile, temperature against power, switch-on transient"></p>

One milliwatt of heater power warms the core by 2.35 K. Without the electrodes of the junction
the rise would be 2.98 K: their metal sits next to the heater and carries about a fifth of the
heat away. After a power step the core settles with a time constant of about 10 µs. The script
also checks the energy balance: of 10.00 mW applied, 10.00 mW arrives at the heat sink.

### Step 5: modulation (MODE)

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig5_active.png" width="100%" alt="Index change, loss, V pi L and resonance shift against reverse bias"></p>

The carriers from step 3 and the temperature from step 4 are loaded into the mode solver. At 4 V
reverse bias the effective index changes by 1.7 × 10⁻⁴ and the resonance moves by 45 pm. This gives
V_π·L = 1.8 V·cm, the product of voltage and length for a π phase shift; smaller is better. The
heater moves the resonance by 124 pm per milliwatt, so 4 V on the junction does as much as
0.36 mW in the heater. The heater therefore sets the operating point, and the junction modulates
around it.

### Step 6: the ring in a circuit (INTERCONNECT)

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig6_circuit.png" width="100%" alt="Spectrum, resonance at four biases, transmission against bias, extinction and Q against gap, resonance at four heater powers"></p>

The results of steps 1 to 5 become the parameters of one ring element in INTERCONNECT. A round
trip loses 0.069 dB: 0.014 dB in the waveguide and 0.056 dB to the free carriers of the junction.
The ring is critically coupled when the bus coupling κ² equals the fraction of power a round trip
loses, 0.0159. That happens at a gap of 371 nm, which is why the layout uses 0.37 µm. With
that gap the loaded Q is 31 000 and the simulated extinction is 46 dB. The resonance is 50 pm wide,
which is 6 GHz in frequency (a photon lifetime of 26 ps). The RC bandwidth of the junction is ten
times that, so the photon lifetime, not the junction, sets the speed of this modulator.

## Limitations

- The process model is idealised: vertical sidewalls, uniform doping in each implant region,
  aluminium for every metal, and bulk values for the TiN film.
- CHARGE and HEAT use straight 2D cross-sections. Only the mode solver bends the waveguide.
- Absorption by the heater and the metals above the waveguide is not modelled.
- The circuit model has no self-heating and no RF model of the pads and wires.
- The 2.2 dB/cm waveguide loss is a published value for a similar process, not a simulation.
- Mesh accuracy is about 5 × 10⁻⁴ in effective index and 2 % in κ². Near critical coupling the
  extinction is very sensitive to κ²: with 1 % more it is 40 dB, with 1 % less 77 dB, instead of
  46 dB. The simulation shows a deep resonance, not its exact depth.

## Using your own foundry PDK

The flow stays the same; you replace the process content: the layer map, stack and rules in
`gsip_technology.py`, and the tables in `gsip_process_file_py/gsip_csv/`, which you fill from the
foundry's design manual. Then compile, and run step 0 before anything else.
[Chapter 5](docs/your_foundry.md) goes through this in order and lists what to compare against at
each stage. Keep foundry data in a private repository; nothing received under NDA belongs in a
public one.

[more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) applies the
same flow to a real open process. It has a single metal layer and no heater layer, which leads to
a rather different device. That example is kept as it was released in v0.2; its README lists the
corrections made in v0.3 that it does not have yet.

## Roadmap

Unit devices come first, then the circuits and links built from them. [ROADMAP.md](ROADMAP.md)
has the full tables.

| area | planned |
|---|---|
| passive devices | strip waveguides, couplers and splitters, crossings, grating and edge couplers, ring filters, Mach-Zehnder interferometers, SiN waveguides |
| active devices | thermo-optic, PN and PIN phase shifters, variable optical attenuator, Mach-Zehnder modulator, germanium photodetector, tunable filters |
| optical computing | Mach-Zehnder meshes and microring weight banks: layout and link simulation |
| optical switching | switch cells and N×N fabrics: layout, loss and crosstalk |
| optical interconnects | WDM transmitters, demultiplexers and receivers: layout, link budget, eye diagram |

## Repository layout

```text
photonics-layout-cookbook/
├── gsip_technology.py        the PDK: layers, stack, cross-sections, design rules
├── gsip_drc.py               design-rule check
├── rm_builder.py             the ring modulator; writes rm_ring.gds
├── gsip_process_file_py/     process tables (CSV), the compiler, and the compiled gsip_process.lbr
├── lumerical_simulations/
│   └── ring_modulator/       scripts/, one folder of results per step, figures/
├── docs/                     chapters 1, 2 and 5
├── assets/                   figures of this page and their scripts
├── tests/                    PDK, layout, DRC, nets, process tables, figures
├── more_processes/           the same flow on CORNERSTONE SOI220A
├── figstyle.py               shared plotting style
├── lumerical_env.py          finds Lumerical and imports lumapi
└── klayout_tech/             layer colours for KLayout
```

## Contributing and licence

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). If the tutorial is useful in
your research or teaching, please cite it with [CITATION.cff](CITATION.cff). The code is under the
[MIT licence](LICENSE).

Three icons in the design-flow figure are taken from the workshop slides and are not covered by
the MIT licence; see the [notice](assets/third_party/ansys_workshop/NOTICE.md). This project is
not affiliated with or endorsed by Ansys, Tower Semiconductor, CORNERSTONE, the authors of the
textbook or the gdsfactory team. "Ansys" and "Lumerical" are trademarks of ANSYS, Inc.

## References

- L. Chrostowski and M. Hochberg, *Silicon Photonics Design: From Devices to Systems*, Cambridge
  University Press, 2015, [doi:10.1017/CBO9781316084168](https://doi.org/10.1017/CBO9781316084168)
- T. Baehr-Jones et al., "A 25 Gb/s Silicon Photonics Platform",
  [arXiv:1203.0767](https://arxiv.org/abs/1203.0767)
- M. Nedeljkovic, R. Soref and G. Z. Mashanovich, "Free-carrier electrorefraction and
  electroabsorption modulation predictions for silicon over the 1–14 µm infrared wavelength
  range", IEEE Photonics Journal 3, 1171 (2011),
  [doi:10.1109/JPHOT.2011.2171930](https://doi.org/10.1109/JPHOT.2011.2171930)
- gdsfactory: [repository](https://github.com/gdsfactory/gdsfactory),
  [documentation](https://gdsfactory.github.io/gdsfactory/)
- SiEPIC-Tools, which includes the GSiP library: [repository](https://github.com/SiEPIC/SiEPIC-Tools)
- Ansys Optics: [Layer builder](https://optics.ansys.com/hc/en-us/articles/360034382394-Layer-builder-Simulation-object),
  [Ring Modulator](https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator),
  [Workshop: Designing Foundry-Compatible Photonic Components and Circuits](https://optics.ansys.com/hc/en-us/articles/31257798958611-Workshop-Designing-Foundry-Compatible-Photonic-Components-and-Circuits)
- CORNERSTONE: [open PDK repository](https://github.com/cornerstone-uos/cornerstone-pdk)

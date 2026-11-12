# photonics-layout-cookbook

**A course in foundry-compatible silicon-photonics design: one process, described once for layout and once for simulation, and a heater-tuned microring modulator taken through both.**

[English](README.md) | [简体中文](README_zh-CN.md)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)
![gdsfactory](https://img.shields.io/badge/layout-gdsfactory%209-6f42c1)
![lumerical](https://img.shields.io/badge/simulation-Ansys%20Lumerical-orange)
![version](https://img.shields.io/badge/version-0.3-2f8f5b)

## Why this course exists

Most students learn to simulate a ring modulator from a drawing made inside the simulator, with a
layer stack typed in by hand. A foundry works the other way round. The process is fixed, so the
layout is the only thing you hand in, and the simulation has to describe what that layout becomes
in that process. A simulation that does not follow this rule can be right for the wrong device.

This repository shows the foundry direction end to end. It uses a teaching process whose numbers
come from public sources, so every file can be published, changed and broken.

<p align="center"><img src="assets/design_flow.png" width="100%" alt="Design flow: device layout with a GDS file, device simulation with the Layer Builder, compact model generation, and circuit simulation, with the GSiP teaching PDK below"></p>

**Figure 1.** The design flow. The arrangement follows the design flow of the Ansys and Tower
Semiconductor workshop (2025). The contents of the four stages come from this repository. Three
icons are taken from the workshop slides, see [the notice](assets/third_party/ansys_workshop/NOTICE.md).
The course is not affiliated with or endorsed by Ansys or Tower Semiconductor.

Read the figure from left to right. A device is drawn in gdsfactory and written to a GDS file. The
Layer Builder reads that file together with a process file, which describes the stack, the
materials and the doping of the same process. The simulations then run on the built structure.
No simulation script contains a thickness, a material or a doping level. Those values live in the
PDK and in the process file. The PDK holds the process in Python. The process file is compiled from CSV
tables that hold the same process. Both are written from the same numbers, and a test fails if they ever disagree.

The idea of the course fits in one sentence: **one process, described twice, from the same numbers.**
The first description is the PDK, which is used for layout. The second is the process file, which is
written as CSV tables and compiled for simulation. A device is drawn with the first and simulated with the second.
A number is changed in both descriptions, and the test of the process tables shows any place where they differ.

## The result first

The flow ends in a device with numbers you can check. The ring has a radius of 10 µm and a 0.37 µm
gap to the bus. Its junction is reverse biased to tune it, and its heater sets the working point.
Simulated together, these are the headline figures:

| question | answer | step |
|---|---|---|
| Does the gap give critical coupling? | yes, at a gap of 371 nm; the layout uses 0.37 µm | 1, 6 |
| How much light is lost per round trip at 0 V? | 0.069 dB, of which 0.056 dB are free carriers | 6 |
| How good is the resonance? | loaded Q = 31 200, extinction above 40 dB at 370 nm | 6 |
| How fast can it switch? | about 6 GHz, limited by the photon lifetime; the junction alone would allow 64 GHz | 3, 6 |
| How far does reverse bias move the resonance? | 44.9 pm at −4 V | 5, 6 |
| How far does the heater move it? | 124 pm/mW, so one free spectral range takes 79 mW | 4, 6 |

The rest of this page shows how each part of the repository produces these numbers, and what each
result teaches.

## The course

The course has five chapters. Each chapter is a document, and each one has steps you can run.

| chapter | document | what you learn | what you can do afterwards | Lumerical |
|---|---|---|---|---|
| 1 | [docs/pdk.md](docs/pdk.md) | what a PDK is, and how a process is written as code: layers, rules, stack, cross-sections | read any layer table and say what each row controls | no |
| 2 | [docs/device.md](docs/device.md) | how a device is drawn from the PDK, and why each part is where it is | build the ring modulator and a variant, run the design-rule check, explain each rule that fails | no |
| 3 | [gsip_process_file_py/README.md](gsip_process_file_py/README.md) | how the same process becomes a Lumerical process file, and how the file is checked against the tables | compile the process file, read its check, and find the source of any number in the tables | yes |
| 4 | [lumerical_simulations/ring_modulator/README.md](lumerical_simulations/ring_modulator/README.md) | seven simulation steps, from the layer check to a circuit element, and the pitfalls of each | run one step, read its result, and decide whether the result is trustworthy | yes, to run |
| 5 | [docs/your_foundry.md](docs/your_foundry.md) | how to port the flow to a real foundry PDK without putting NDA data in a public repository | plan the port of your own process, step by step | for the process file |

Without Lumerical you can still do a lot. You can run chapters 1 and 2 in full: draw the device, run
the design-rule check, read the layer stack, and open the GDS in KLayout. You can run the 85 tests.
You can read every result file and redraw every figure of chapter 4 from the kept data, because the
figure scripts read those files with NumPy and matplotlib only. Only the compiler of chapter 3 and
the simulations of chapter 4 need a licence.

## The PDK at a glance

A PDK (process design kit) is the set of files that lets a layout tool draw on a process. It holds
the layers, their numbers, the design rules, the stack of materials and the cells that use them.
This course uses a teaching PDK named `gsip_teaching`. It is the Generic Silicon Photonics (GSiP)
process of the textbook by Chrostowski and Hochberg, in the layer numbering of the open-source
gdsfactory generic PDK. No foundry stands behind it.

<p align="center"><img src="assets/pdk_stack.png" width="100%" alt="Cross-section of the GSiP teaching process: the full stack to scale with the back end, and the front end with vertical scale times five"></p>

**Figure 2.** The whole process in one cross-section. (a) The full stack to scale, with the back end
of seven building blocks. (b) The front end with a vertical scale of ×5, with the layers used by the
ring modulator of chapter 2 in colour.

Figure 2 shows the idea that matters most for layout. A layer is a drawn shape with a GDS number. The
same layer also has a height, a material and, for implants, a doping level. The layout carries only the
number. The simulator gets the rest from the process file.

The layers, grouped by what they do. Numbers are GDS layer/datatype. Concentrations are in cm⁻³.

| group | layer (GDS) | value | source |
|---|---|---|---|
| silicon | WG (1/0) | core, 220 nm | [B], [BJ], [GF] |
| | SLAB150 (2/0), SLAB90 (3/0) | slabs, 150 nm and 90 nm | [B], [GF] |
| | DEEPTRENCH (4/0), UNDERCUT (6/0) | deep trench, substrate undercut | [B], [GF] |
| implants | N (20/0), P (21/0) | 5 × 10¹⁷ and 7 × 10¹⁷ | [B] Sec. 6.2 |
| | NP (22/0), PP (23/0) | 3 × 10¹⁸ and 2 × 10¹⁸ | [B] Sec. 6.2 |
| | NPP (24/0), PPP (25/0) | 5 × 10²⁰ and 1.9 × 10²⁰ | [B] Sec. 6.2, [BJ] |
| germanium and nitride | GE (5/0) | germanium, 500 nm | [B], [BJ], [GF] |
| | GEN (26/0), GEP (27/0) | germanium implants, 10¹⁹ | [T] |
| | WGN (34/0) | silicon nitride, 350 nm | [GF] |
| back end | VIAC (40/0) | contact via, silicon to metal 1 | [B], [GF] |
| | M1 (41/0), M2 (45/0) | aluminium, 0.7 µm | [B], [GF] |
| | HEATER (47/0) | TiN film, 0.15 µm, 10 Ω/sq | [GF] for the layer, [T] for the thickness |
| | VIA1 (44/0), VIA2 (43/0) | vias between the metal levels | [B], [GF] |
| | M3 (49/0) | aluminium, 2 µm, pads | [GF] |
| | PADOPEN (46/0) | passivation opening over a pad | [B] |
| not fabricated | FLOORPLAN (64/0), TEXT (66/0), DEVREC (68/0) | outline, text, device recognition | [B], [GF] |

Twenty-three of the 26 layers are fabricated. The other three are for the designer only.

Every number in the code carries one of four source tags:

- **[B]** L. Chrostowski and M. Hochberg, *Silicon Photonics Design: From Devices to Systems*,
  Cambridge University Press, 2015. The layer map (Table 10.2), the process parameters (Table 10.1)
  and the doping levels (Section 6.2) come from it.
- **[BJ]** T. Baehr-Jones et al., "A 25 Gb/s Silicon Photonics Platform", arXiv:1203.0767 (2012).
  This is the published process that the book's table refers to. It gives the waveguide loss of
  2.2 ± 0.8 dB/cm.
- **[GF]** the gdsfactory generic PDK (MIT licence). Its layer map and layer stack give the numbers
  and heights that the book does not give.
- **[T]** a teaching value chosen for this repository. Each one is written next to the code with its
  reason, for example the heater film of 0.15 µm.

**Why a teaching PDK and not a real one?** The complete active processes of commercial foundries,
with silicon levels, implants, germanium, a heater and several metals, are distributed under NDA or
licence. None is public. The open CORNERSTONE SOI220A process is real and public, but it has one
metal layer and no heater layer, so it cannot show a full back end. It is the second example of the
repository, see [A second process](#a-second-process). A process made from public sources can be
published, changed and broken freely, and the flow is the same as with a real one. The numbers are
teaching numbers. They are not a foundry's, and they must not be used for a tape-out.

## The device

The device is a microring modulator with a heater. The ring is a rib waveguide of 10 µm radius. A PN
junction runs along 240° of the ring, and a TiN heater runs along 270° above the core. A bus waveguide
passes the ring at a point coupler. Chapter 2 builds it.

<p align="center"><img src="assets/rm_layout.png" width="100%" alt="Ring modulator layout: whole device with layer table, silicon and implants, contacts with metal 1 and the heater, via 1 and metal 2, and all layers together"></p>

**Figure 3.** The device, drawn by `rm_builder.py`. (a) The whole device with the layer table. (b)
Silicon and implants: the junction is on the upper 240° of the ring, n inside and p outside. (c)
Contacts, metal 1 and the heater. (d) Via 1 and metal 2. (e) All layers together.

The parameters of the default device, the arguments of `rm_builder.ring_modulator`:

| parameter | default | what it sets |
|---|---|---|
| `radius` | 10 µm | ring radius; the circumference is 62.83 µm |
| `width` | 0.5 µm | core width of ring and bus, on a 90 nm slab 6 µm wide |
| `gap` | 0.37 µm | edge-to-edge gap between ring and bus; close to the critical-coupling gap of step 6 (371 nm) |
| `pn_angle` | 240° | the doped arc, 41.89 µm, which is 67 % of the ring |
| `heater_angle` | 270° | the heater arc; the free filament is 44.72 µm, 71 % of the ring, 280 Ω |
| `pad_size`, `pad_pitch` | 80 µm, 100 µm | metal 3 pads: G S G in the north for the junction, H H in the south for the heater |

The device has seven ports: `o1` and `o2` for light, `G1`, `S` and `G2` for the junction, and `H1` and
`H2` for the heater. Its design-rule check reports 0 errors and 0 warnings.

### Why is the heater not on metal 1?

It is the first question most readers ask, and the answer is the first lesson of the device. The
heater and metal 1 both start 1.10 µm above the buried oxide, so they share a plane. A layer
holds one material only, so the process gives the heater its own layer, HEATER 47/0, and gives the
electrodes their own layer, M1 41/0. The design rules keep the two at least 0.6 µm apart. If the
heater were drawn on metal 1, it would short the contacts of the junction, and its resistance would be
lost in the metal. Metal 2 then carries the current from the heater landings to the pads. The routing
is in the layout, not in the simulator.

### Why are there two descriptions of one process?

Because the two tools read different things. The layout tool needs the layers, the design rules and
the cross-sections, so that it can draw the device and check it. The simulator needs the material of
every layer, its height and its doping, so that it can solve for light, carriers and heat. Writing
both by hand gives two sources that drift apart, so that a change of one layer changes the layout but
not the simulation, or the reverse. Here the process is written twice on purpose, in `gsip_technology.py`
and in the CSV tables of `gsip_process_file_py/gsip_csv`, from the same numbers. The tests in
`tests/test_process_tables.py` fail when the two differ. Step 3 then checks the doping seen by the
simulator against the tables, region by region.

### Drawing it and checking it

The snippet below draws the default device and a variant with a larger ring and a wider gap, checks
both with the design-rule check, and writes the variant to a GDS file for the Layer Builder. Run it
from the root of the clone, after `uv sync`. The writer creates the folder `build/` if it is missing:

```python
import gsip_technology as t  # importing it activates the gsip_teaching PDK
import rm_builder as rm
from gsip_drc import run_drc

device = rm.ring_modulator()                  # default: R = 10 um, gap 0.37 um
variant = rm.ring_modulator(radius=12, gap=0.40)

for name, component in (("default", device), ("variant", variant)):
    result = run_drc(component)
    print(name, result.summary())
    assert result.passed

t.write_gds_for_lumerical(variant, "build/ring_r12.gds", cellname="ring_r12")
```

`run_drc` is a design-rule check in pure Python, so it needs no Lumerical. It checks the minimum width
and space of each layer in the table of minimum widths, the enclosures of vias and contacts, the distance between metal 1 and the
heater, and the overlaps of the implants. Its `passed` flag is false if any error is found. It is a
teaching tool with the handful of rules that a device builder trips over first. It is not a foundry
rule deck, and it does not replace the rules of the foundry you submit to. The gap must be at least
the minimum space of the waveguide layer, 0.2 µm.

## Results

Chapter 4 runs the device through seven steps, from the layer check to a circuit element. Each step
asks one question. Its figure answers that question, and the numbers come from the result files of
the step folders. Every figure can be redrawn from the kept data without Lumerical.

**These are simulation results of a teaching process. Nothing here has been compared with a
fabricated device.** The numbers are not a foundry's. [Limitations](#limitations-and-disclaimer) lists
the assumptions behind them.

### Step 0. Did the Layer Builder build what the layout says?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig0_layer_builder.png" width="100%" alt="Layer Builder check: a cut through the PN section and a cut through the coupler, and four horizontal cuts through the finished structure at the slab, core, metal 1 and heater, and metal 2 levels"></p>

**Figure 4.** The structure as the solver sees it. (a) Cut through the PN section. (b) Cut through the
coupler. (c to f) Horizontal cuts at the slab, core, metal 1 and heater, and metal 2 levels.

Before any physics, the mode solver is used as a probe of the built structure. At ten points of the
finished 3D model it reports the refractive index it sees. The points include the substrate and the
buried oxide below the core, the contact vias, the heater film and the metal 2 wire. The values are:
silicon 3.476, oxide 1.444, aluminium 1.44 + 16i and TiN 3.54 + 6.52i. A wrong layer expression in the
process file would show up here as a missing or misplaced shape.

### Step 1. How strongly does the bus couple light into the ring?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig1_coupling.png" width="100%" alt="Coupling between bus and ring: field in the coupler, power coupling against gap with the exponential fit and the critical-coupling point, and against wavelength"></p>

**Figure 5.** The coupler. (a) The field in the coupler, with the ring arm continuing in an S-bend so
that all four ports face the same way. (b) The power coupling κ² against gap, with the fit and the
point of critical coupling. (c) κ² against wavelength.

The coupling region is simulated with FDTD, a time-domain solver. A reference run without the bus gives
the loss of the ring arm, which is divided out. κ² is 0.118, 0.0369, 0.0113 and 0.00344 at gaps of 200,
300, 400 and 500 nm. The fit κ² = 1.26 · exp(−gap / 84.8 nm) reproduces them, for gaps of 200 to 500 nm.
It is an interpolation formula, and it must not be extrapolated. The fit gives critical coupling,
κ² = 0.0159, at a gap of 371 nm. The sum κ² + t² is 0.9998 to 1.0000, which checks that the solver
conserves power. Each gap takes about 6 minutes on this machine.

The mesh sets how far κ² can be trusted. One gap of 400 nm was run three ways. A 10 nm mesh over the
coupler changes the raw |S41|² by −2.0 % and takes 18.6 minutes instead of 5.6. The default 20 nm
mesh is used for the tables. κ² is therefore known to about 2 %, which moves the gap of critical
coupling by about 2 nm.

### Step 2. How does the passive waveguide guide the mode?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig2_passive.png" width="100%" alt="Passive rib waveguide: straight and bent mode profiles, effective index against wavelength, bend loss against radius, and TE0 and TE1 against core width"></p>

**Figure 6.** The passive rib. (a) Straight mode. (b) Mode bent to R = 10 µm, shifted 26 nm outwards.
(c) Effective index against wavelength. (d) Bend loss against radius. (e) TE0 and TE1 against core width.

The mode solver finds the modes of a cross-section. The straight rib has an effective index of 2.5677, a
group index of 3.937 and a TE fraction of 0.987 at 1550 nm. Bent to 10 µm, the mode moves 26 nm
outwards and keeps an overlap of 0.995 with the straight mode, and its radiation loss is below the
solver floor. The bend loss is 0.56 dB/cm at R = 5 µm and 15.2 dB/cm at 4 µm, and it is below the
floor from 6 µm up. The free spectral range of the ring, λ² / (n_g L), is 9.71 nm.

The group index in panel (c) is taken from the slope of n_eff(λ) over 1500 to 1600 nm. It gives 3.916,
which is 0.5 % below the solver's value at 1550 nm. The reason is the material. Lumerical interpolates
the tabulated silicon index linearly between its sample wavelengths, so the material dispersion is
piecewise constant, and the solver's group index steps between 1530 and 1540 nm. The solver's value
at 1550 nm is the one used for the free spectral range.

**The 0.5 µm rib is not strictly single-mode.** Its TE1 mode has an effective index of 2.115, only
0.011 above the fundamental mode of the 90 nm slab (2.104), so it is close to cutoff. Panel (e) shows
where the second mode appears: at 0.45 µm the solver still returns a TE1 mode, but below the slab mode,
so it is not guided. The bend loss of TE1 was not simulated, which makes a good exercise for chapter 4.

**The mesh lesson of steps 2 and 5.** A uniform 20 nm mesh had no mesh line on the 90 nm slab surface
or on the core sidewalls. Which interfaces got a line depended on where the window started. The same
undoped rib bent to R = 10 µm gave n_eff = 2.5765 in the window of step 2 and 2.5693 in the window of
step 5. That is a difference of 0.007, more than the heater makes at 10 mW. With a mesh line on every
silicon surface the two windows agree: the mesh of the tables gives 2.5702 in step 2 and 2.5701 in step 5.
The absolute index is good to about 5 × 10⁻⁴. The differences that the simulations report, such as
the change of index with bias, were hardly affected. The steps add the mesh line with `common.add_rib_mesh`.
A pitfall comes with it. The new mesh object takes the selection in Lumerical, so the helper must run
after the last property of the solver object is set. Calling it right after `addfde()` makes the next
`set` fail with "the requested property 'solver type' was not found".

### Step 3. How much charge does the junction hold, and how fast can it move it?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig3_charge.png" width="100%" alt="PN junction: net doping, carriers at 0 V and 4 V, carrier densities across the junction, capacitance against bias, RC bandwidth, and process file against solver"></p>

**Figure 7.** The PN junction. (a) Net doping. (b, c) Net carriers at 0 V and at 4 V of reverse bias.
(d) Carrier densities across the junction. (e) Capacitance against bias, with the abrupt-junction
formula. (f) Intrinsic RC bandwidth. (g) Doping of the process file against the solver.

CHARGE solves the carriers of the reverse-biased junction in a two-dimensional cross-section. First the
simulator checks the doping: in all six regions the net doping agrees with the process tables within
0.5 %. The check tests the concentration and the lateral position of the regions, not their depth,
because the profiles are flat in depth by construction. The junction lies 5 nm from its drawn position.

The small-signal capacitance is taken from a series RC model. The admittance Y is inverted to an
impedance Z = 1/Y, the series resistance is R_s = Re Z, and the capacitance is C = −1/(ω Im Z). The
shortcut C = Im(Y)/ω is correct only when the series resistance is negligible, and it is not here.
The junction capacitance is 0.398 fF/µm at 0 V and 0.208 fF/µm at −4 V. The series resistance is
150 Ω at 0 V, and the intrinsic RC bandwidth rises from 64 GHz to 131 GHz.

The abrupt-junction formula of the textbook [B, Eq. 6.14] gives 0.356 fF/µm at 0 V. The simulation is
1.12 times that value at 0 V and 1.35 times at −4 V. The difference is a roughly constant extra
capacitance, about 0.04 to 0.05 fF/µm. The one-dimensional formula leaves out the field around the
220 nm high junction. We believe this is the cause, but the attribution was not tested. The reverse
current stays below 10⁻¹³ A. That value is the numerical floor of the solver, not a prediction of leakage.

### Step 4. How much heat does the heater put into the core?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig4_heat.png" width="100%" alt="Heater: temperature map at 10 mW, vertical profile through the heater, temperature rise against power, and the transient of the core"></p>

**Figure 8.** The heater. (a) Temperature map at 10 mW. (b) Vertical profile through the heater.
(c) Temperature rise against power. (d) Transient of the core.

The model is a two-dimensional cross-section that includes metal 1 and the vias, normalised to the length
of the filament. Averages are weighted by the area of the mesh cells. The core warms by 2.35 K per mW in
the heated section, and by 1.67 K per mW averaged over the ring. The metal 1 and the vias next to the
heater take 21 % of its efficiency: without them the core would warm by 2.98 K per mW. The heater film
itself warms by 5.41 K per mW. The free filament is 280 Ω, so 10 mW needs 1.67 V and 6.0 mA. The landings
and the current spreading into them add a few per cent to the resistance, which the estimate leaves out.

The transient is run at the reference power of 10 mW. The core reaches 63 % of its final rise after
10.3 µs, and its 10 to 90 % rise takes 34.3 µs. The response is not a single exponential, because heat
diffuses: the ratio of the rise time to the time constant is 3.3, where one exponential would give 2.2.
The value 0.35 / t_rise = 10 kHz is a rule of thumb for the bandwidth, not a measured −3 dB point.

The energy balance is part of the script. The heat flux through the buried oxide is integrated over the
heat sink, and 10.00 mW reach it for the 10.00 mW that were set. The ring average assumes electrodes
along the whole filament, but 6 % of the filament lies beyond them. If the inner metal 1 is drawn only
6 µm wide instead of up to the ring centre, the core reaches 2.50 K per mW instead of 2.35.

**The pitfall of this step.** The Joule heat must be a uniform heat source assigned to the solid heater,
so that it is generated in the volume of the film. A thermal power boundary condition on the same solid
looks equivalent. It cuts the film out of the thermal domain: the core temperature differs by only 0.4 %,
but the film comes out 23 K hotter in its middle than at its edges. A heat source drawn as a box over
the film is worse. It also heats the mesh cells that it touches, and 12 % more power than requested
arrives at the heat sink. The check that finds such an error is simple. Integrate the heat flux into the
substrate and compare it with the power you set.

### Step 5. How does the active waveguide change with bias and heat?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig5_active.png" width="100%" alt="Active waveguide against reverse bias: change of the effective index, loss, V pi L, and the resonance shift of the ring"></p>

**Figure 9.** The active waveguide against reverse bias. (a) Change of the effective index. (b) Loss.
(c) VπL. (d) Resonance shift of the ring.

The mode is solved again for the bent, doped rib, with the carriers of step 3 and the temperature of
step 4 loaded as attributes of the grid. At −4 V the effective index changes by 1.71 × 10⁻⁴, and VπL is
1.82 V·cm. The loss falls from 13.3 dB/cm at 0 V to 9.9 dB/cm at −4 V, while the undoped guide has
0.026 dB/cm. The free carriers of the PN section cost 0.056 dB per round trip at 0 V and 0.042 dB at −4 V.
The heater moves the effective index by 4.41 × 10⁻⁴ per mW in the heated section, which is 124 pm per mW
for the ring. So 4 V of reverse bias moves the resonance as much as 0.36 mW of heater power. The heater
sets the working point, and the junction modulates around it.

### Step 6. What does the ring do as a circuit element?

<p align="center"><img src="lumerical_simulations/ring_modulator/figures/fig6_circuit.png" width="100%" alt="Ring as a circuit element: spectrum with the free spectral range, resonance at four biases against the analytic ring, transmission against bias, extinction and Q against gap, and the resonance at four heater powers"></p>

**Figure 10.** The ring as an INTERCONNECT element. (a) Spectrum at 0 V with the free spectral range.
(b) Resonance at four biases, with the analytic all-pass ring. (c) Transmission at the resonance and half
a linewidth above it, against bias. (d) Extinction against gap. (e) Loaded Q against gap. (f) Resonance
at four heater powers.

The ring is placed in INTERCONNECT as one element, with the numbers of steps 1 to 5. The round trip loses
0.069 dB at 0 V: 0.014 dB to scattering at 2.2 dB/cm [BJ], and 0.056 dB to free carriers. At the gap of
371 nm the ring is at critical coupling. The design gap of 370 nm gives a loaded Q of 31 200, a linewidth
of 49.8 pm and an extinction above 40 dB. The simulation gives 46 dB with these inputs. Near critical
coupling the depth is very sensitive: the analytic ring gives 77, 46 and 40 dB for κ² changed by −1 %, 0
and +1 %, and κ² itself is known to about 2 %. The measured spacing of the two resonances around 1547 nm
is 9.67 nm, which is the free spectral range. The formula λ² / (n_g L) gives 9.73 nm at the design
resonance of 1551.6 nm. The absolute wavelength is only as good as the absolute index.

The photon lifetime sets the optical bandwidth. The linewidth in frequency, c / (λQ), is 6.2 GHz. It is
the usual photon-lifetime estimate. The exact small-signal response depends on the laser detuning, and on
resonance its pole lies at half this value. Combined with the RC bandwidth of 64 GHz, the −3 dB point of
the two cascaded first-order responses is 6.1 GHz.

The shift of the resonance is 14.9, 26.4 and 44.9 pm at −1, −2 and −4 V (step 5 gives 14.8, 26.3 and
44.8 pm). The average over 0 to 4 V is 11.2 pm/V. The transmission at the 0 V resonance wavelength is
−46.0, −5.6, −2.5 and −0.95 dB at 0, −1, −2 and −4 V. The heater tunes the resonance by 124.0 pm per mW,
so one free spectral range at the design resonance needs 79 mW.

The extinction depends strongly on the gap. It is above 40 dB at 370 nm and 15 dB at 340 and at 400 nm.
A real design sweeps the gap on the mask, and the layout default of 0.37 µm is this gap.

### The device in numbers

| quantity | value | step |
|---|---|---|
| ring radius, circumference | 10 µm, 62.83 µm | layout |
| PN section (junction arc) | 41.89 µm, 240°, 67 % of the ring | layout |
| heater filament | 44.72 µm, 280 Ω, 71 % of the ring | layout, step 4 |
| critical coupling | κ² = 0.0159 at a gap of 371 nm | 1, 6 |
| effective and group index, straight, 1550 nm | 2.5677 and 3.937 | 2 |
| junction capacitance at 0 V and −4 V | 0.398 and 0.208 fF/µm | 3 |
| intrinsic RC bandwidth at 0 V and −4 V | 64 and 131 GHz | 3 |
| heater efficiency, core in the heated section | 2.35 K/mW | 4 |
| thermal time constant (63 %) and 10 to 90 % rise | 10.3 µs and 34.3 µs; about 10 kHz bandwidth | 4 |
| index change and VπL at −4 V | 1.71 × 10⁻⁴ and 1.82 V·cm | 5 |
| round-trip loss at 0 V | 0.069 dB, of which 0.056 dB free carriers | 6 |
| loaded Q, linewidth and FSR at 370 nm | 31 200, 49.8 pm, 9.67 nm | 6 |
| extinction at 0 V | above 40 dB (46 dB with these inputs) | 6 |
| optical bandwidth | 6.2 GHz | 6 |
| resonance shift at −4 V | 44.9 pm | 6 |
| thermal tuning | 124 pm/mW; one FSR needs 79 mW | 6 |

### What the numbers say

- The photon lifetime limits the speed, at about 6 GHz, and not the junction, which allows 64 GHz. A
  faster modulator needs a lower Q, which means a smaller gap and less extinction.
- Free carriers set the loss: 0.056 dB of the 0.069 dB per round trip.
- The heater sets the working point, and the junction modulates around it. Four volts of reverse bias
  are worth 0.36 mW of heater power.
- The extinction is very sensitive to the gap: above 40 dB at 370 nm, 15 dB at 340 and at 400 nm. A real
  design sweeps the gap on the mask.
- The metal 1 and the vias next to the heater cost 21 % of its efficiency.
- The mesh matters more than the window. A mesh line that misses a 90 nm slab surface moved the effective
  index by 0.007, which is more than a heater at 10 mW produces.

The numbers also agree with the textbook in three places. The modulation efficiency of 1.4 to 1.8 V·cm
between −1 and −4 V is close to the 1.6 V·cm of Fig. 6.6 of [B]. A metal heater above a strip waveguide
needs 36 mW per free spectral range in Sec. 6.5.2 of [B]. Here it needs 79 mW, because only 71 % of the
ring is heated and the electrodes take 21 % of the heat. Corrected for both, it would be 44 mW. Section
13.1.2 of [B] describes a ring with a similar rib, about 75 % doped, with a capacitance of about 25 fF, a
resonance shift of 28 pm/V near 0 V and a Q lowered to 5000 for a bandwidth of 35 GHz. The ring here is
67 % doped, with a capacitance of 16.7 fF and a shift of 16.1 pm/V over 0 to 0.5 V. It is at critical
coupling with a Q of 31 200, and its photon lifetime gives a bandwidth of about 6 GHz. The two rings have
different radii and gaps, so the comparison shows the trade-off and not a matching number.

## Quick start

The layout, the design-rule check and the tests need only Python. The process file and the simulations
need Ansys Lumerical with the FDTD and CHARGE licences. The project uses [uv](https://docs.astral.sh/uv/)
for a reproducible Python environment, with Python 3.12 or 3.13.

**Keep the clone on a path without non-ASCII characters**, for example a folder such as
`photonics-layout-cookbook` directly under a short ASCII-only path. Lumerical solvers can fail otherwise.

```bash
# 1. environment (uv: https://docs.astral.sh/uv/), then the code and the packages
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync

# 2. the PDK: list the layers, the stack and the cross-sections; write the KLayout technology
uv run python gsip_technology.py

# 3. the design-rule check on its own, with planted violations that must be found
uv run python gsip_drc.py --demo

# 4. the device: rm_ring.gds, the DRC report and preview images in build/
uv run python rm_builder.py

# 5. the tests (85, no Lumerical needed)
uv run pytest
```

Redraw one figure from the kept result files, for example the passive waveguide of step 2. This needs no
Lumerical:

```bash
uv run python lumerical_simulations/ring_modulator/figures/fig2_passive.py
```

### The Lumerical part

Lumerical is found through the environment variable `LUMERICAL_ROOT`, which points to the folder that
contains `api/python/lumapi.py`. Without it, the usual install locations are searched.

```powershell
# PowerShell
$env:LUMERICAL_ROOT = "C:\Program Files\ANSYS Inc\v251\Lumerical"
```

```bash
# bash
export LUMERICAL_ROOT=/opt/lumerical/v251
```

Compile the process file first. This needs the FDTD and CHARGE licences, and it opens no window. The
compiler writes `gsip_process_file_py/gsip_process.lbr` and checks it by reloading the file and comparing
every property with the tables. [Chapter 3](gsip_process_file_py/README.md) explains each table.

```bash
uv run python gsip_process_file_py/gsip_process_file_compiler.py
```

Then run the seven steps in order, each from its script in `lumerical_simulations/ring_modulator/scripts/`.
Step 1 has a `--dry` option that runs one gap on a coarse mesh, without the reference run,
which is the cheapest way to see that the set-up works. A full run of step 1 takes about 6 minutes per gap. Scripts with options list them
with `--help`.

```bash
uv run python lumerical_simulations/ring_modulator/scripts/layer_builder_check.py
uv run python lumerical_simulations/ring_modulator/scripts/coupling_coefficient_fdtd.py --dry
uv run python lumerical_simulations/ring_modulator/scripts/passive_mode_fde.py
uv run python lumerical_simulations/ring_modulator/scripts/charge_profile.py
uv run python lumerical_simulations/ring_modulator/scripts/heat_profile.py
uv run python lumerical_simulations/ring_modulator/scripts/active_mode_fde.py
uv run python lumerical_simulations/ring_modulator/scripts/ring_modulator_interconnect.py
```

[Chapter 4](lumerical_simulations/ring_modulator/README.md) explains what each step does, which settings
matter, and what each one returns.

## Using the pieces in your own scripts

The layout part is an ordinary Python package. Importing `gsip_technology` activates the PDK, so import it
before you draw. The snippet of [the device](#drawing-it-and-checking-it) shows the pattern, and any script
that runs from the repository root can use the same builders.

In Lumerical, the Layer Builder takes one GDS file and one process file. Run these three commands in a
script or in the Layer Builder dialog, in this order:

```text
addlayerbuilder;
loadgdsfile("/full/path/to/rm_ring.gds");
loadprocessfile("/full/path/to/gsip_process_file_py/gsip_process.lbr");
```

`addlayerbuilder` creates the object. `loadgdsfile` loads the flat layout that `rm_builder.py` writes.
`loadprocessfile` loads the compiled process. Together they give the structure that the simulation scripts
build, so you can inspect it in the Layer Builder before you run a solver. Give full paths to both files, as the step
scripts do (see `scripts/common.py`).

## Repository layout

```text
photonics-layout-cookbook/
├── gsip_technology.py          the teaching PDK: layers, rules, stack, cross-sections, cells (chapter 1)
├── gsip_drc.py                 design-rule check in pure Python, klayout.db; --demo self-test
├── rm_builder.py               the ring modulator layout (chapter 2)
├── rm_ring.gds                 its output, flat, ready for the Layer Builder
├── lumerical_env.py            finds Lumerical (LUMERICAL_ROOT) and imports lumapi
├── figstyle.py                 the shared figure style
├── docs/                       chapters 1, 2 and 5: pdk.md, device.md, your_foundry.md
├── gsip_process_file_py/       chapter 3: the process as CSV tables and the compiler
│   ├── gsip_csv/               process tables; the README in the folder gives every source
│   ├── gsip_process_file_compiler.py   compiles the tables into gsip_process.lbr through lumapi
│   └── gsip_process.lbr        the compiled process file, kept in the repository
├── lumerical_simulations/ring_modulator/   chapter 4
│   ├── scripts/                common.py and one script per step, 0 to 6
│   ├── 0_layer_builder_check/ … 6_interconnect_ring_modulator/
│   │                           per step: small GDS, .txt summary, .npz result arrays (kept)
│   └── figures/                fig0 … fig6 scripts and PNG files; redrawn without Lumerical
├── assets/                     figures of this page, their scripts, third_party/ with the notice
├── klayout_tech/               layers.lyp and tech.lyt for viewing layouts in KLayout
├── tests/                      85 pytest tests: PDK, layout, DRC, process tables, figures
├── more_processes/cornerstone_soi220a/   a second process, self-contained, with its own tests
├── legacy/                     the v0.1 package, kept for reference, not maintained
├── ROADMAP.md  CONTRIBUTING.md  CITATION.cff  LICENSE
└── pyproject.toml  uv.lock     the uv project and its locked versions
```

## Your own foundry

The flow does not change when the numbers come from a real foundry. [Chapter 5](docs/your_foundry.md)
gives the full procedure. In short:

1. Replace the layer map, the constants, the rules and the cross-sections in `gsip_technology.py` with
   those of your PDK. Keep the foundry's own layer names.
2. Replace the rows of the tables in `gsip_process_file_py/gsip_csv/` with the foundry's numbers, and
   record the source of each number beside it. Mark every assumption.
3. Port the device builder to the foundry's cross-sections, and check it with a design-rule check that
   reads the foundry's rules.
4. Compile the process file, and run check 0 of the simulations before anything else. A wrong layer
   expression shows up as a wrong index.
5. Keep the foundry's data out of this repository. NDA data never goes into a public repository.

## A second process

[more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) runs the same flow on
CORNERSTONE SOI220A, a real and open foundry process at the University of Southampton. It has its own
technology file, design-rule check, device, process file, simulations and tests. Inside that folder,
`uv run pytest` gives 24 passed and 1 skipped.

It teaches what the generic process cannot. CORNERSTONE SOI220A has one metal layer and no heater layer,
so the heater is drawn in the electrode layer and shares the ring with the junction electrodes. The
junction takes the upper 240°, and the heater the lower 76°. Its n implant enters the rib through the
sidewall, so the junction is not where the mask edge is. The foundry generates the trenches around each
waveguide, and the process file reproduces that. Reading the two folders side by side shows what changes
when the process changes and what stays the same. A generic process can show the method. Only a real one
shows the trade-offs.

This second example is kept as it was released in v0.2. The corrections of this version were not ported
to it: the mesh lines on the silicon interfaces, the volume heat source, the series-RC extraction and the
refined resonances. Its absolute effective index can therefore be off by several 10⁻³ for the mesh reason
given in step 2, and its heater still uses the thermal power boundary condition that step 4 shows to be
wrong. Read its numbers with that in mind.

## Design principles

Each principle is here because the course depends on it.

- **One process, written from one set of numbers.** A number is written once in the Python PDK and once
  in the CSV tables of the process file. The two descriptions are kept equal by tests, so they cannot
  silently disagree. Two copies of a number drift apart, and the error then appears only on the mask or in
  the simulation. The tests find such a drift before a simulation runs.
- **The GDS is the contract.** The Layer Builder builds every structure from the GDS and the process file,
  so the solver sees what the layout says, not what the Python code intended. A few settings of the
  simulation scripts are read from the defaults of `rm_builder.ring_modulator`, and those defaults reach
  the simulations too.
- **Every number has a source.** Each number is tagged with a document, a result file or a teaching
  choice, and each teaching value is tagged [T] with its reason. A reader can check a number, and the
  course can be corrected.
- **Check each layer against something independent.** Step 0 compares the indices with the expected
  materials. Step 3 compares the doping with the tables. Step 4 compares the heat flux with the power.
  The mesh of the mode solver is checked the same way: the same rib gave two effective indices until every
  silicon surface had a mesh line. A flow can be consistent and still wrong, so each layer needs its own check.
- **Public data only.** Every number comes from a public document or is a labelled teaching value. A
  public course must be able to share its data, and a foundry's data cannot be shared.
- **Simulations keep their data.** Every figure can be redrawn without Lumerical from the kept result
  arrays. A reader without a licence can still check the plots.

## Limitations and disclaimer

These limitations are part of the results. Read them before you use a number.

- These are simulation results of a teaching process. Nothing has been compared with a fabricated device.
  Before a tape-out, every number comes from the foundry.
- The assumptions are: vertical sidewalls, flat doping profiles (an abrupt junction), a planar top oxide,
  aluminium for all vias and metals, and TiN data taken from bulk values. The CHARGE and HEAT database has
  no TiN, so the film uses the aluminium model with four properties overridden. The top surface is
  insulating in HEAT, so there is no convection and no radiation.
- CHARGE and HEAT use straight two-dimensional cross-sections. Only the mode solver bends the waveguide.
- Optical absorption by the heater and the metals is not included. Metal 2 crosses the waveguides 2.1 µm
  above the core, and the mode-solver window ends below the heater, with 0.88 µm of oxide between the core
  and the heater.
- The mesh limits the accuracy. The absolute effective index is good to about 5 × 10⁻⁴, and κ² of the FDTD
  step to about 2 %. Near critical coupling the extinction is uncertain by many dB, and the gap of critical
  coupling moves by about 2 nm.
- The circuit model has no self-heating, no two-photon absorption and no radio-frequency model of the pads
  and wires. The f_RC of step 3 is the intrinsic limit of the junction.
- The waveguide loss of 2.2 dB/cm is a published value for a comparable process, not a simulation.
- The second example, `more_processes/cornerstone_soi220a`, is kept as released in v0.2 and does not
  carry the corrections of this version.

The third-party icons in `assets/third_party/ansys_workshop/` are taken from the Ansys workshop slides, and
they are used under the terms of [their notice](assets/third_party/ansys_workshop/NOTICE.md). This project
is not affiliated with or endorsed by Ansys, Tower Semiconductor, CORNERSTONE, the authors of the textbook
or the gdsfactory team. "Ansys" and "Lumerical" are trademarks of ANSYS, Inc.

## Roadmap

The full plan, with the reason for each item, is in [ROADMAP.md](ROADMAP.md). In short:

| stage | what it adds | status |
|---|---|---|
| v0.1 | an installable package with a generated PDK on top of `cspdk` | released, in [legacy/](legacy/README.md) |
| v0.2 | the flat flow on CORNERSTONE SOI220A | released, in [more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) |
| v0.3 | this course: the GSiP teaching PDK with a full back end, seven simulation steps and five chapters | this version |
| next | a compact model of the ring for INTERCONNECT, built from steps 1 to 5; process corners; a gap sweep on the mask | planned |
| later | more devices on the same process, such as a phase shifter and a germanium photodetector | planned |

## Contributing, citing, licence

Contributions are welcome, especially chapters, exercises, new devices on the same process, and new
processes with public data. See [CONTRIBUTING.md](CONTRIBUTING.md). If the course helps your research or
teaching, please cite it with the information in [CITATION.cff](CITATION.cff). The code is released under
the [MIT licence](LICENSE).

## References

- L. Chrostowski and M. Hochberg, *Silicon Photonics Design: From Devices to Systems*, Cambridge
  University Press, 2015, [doi:10.1017/CBO9781316084168](https://doi.org/10.1017/CBO9781316084168)
- T. Baehr-Jones et al., "A 25 Gb/s Silicon Photonics Platform", [arXiv:1203.0767](https://arxiv.org/abs/1203.0767)
- M. Nedeljkovic, R. Soref and G. Z. Mashanovich, "Free-carrier electrorefraction and
  electroabsorption modulation predictions for silicon over the 1–14 µm infrared wavelength range",
  IEEE Photonics Journal 3, 1171 (2011), [doi:10.1109/JPHOT.2011.2171930](https://doi.org/10.1109/JPHOT.2011.2171930)
- gdsfactory, [repository](https://github.com/gdsfactory/gdsfactory) and
  [documentation](https://gdsfactory.github.io/gdsfactory/)
- SiEPIC-Tools with the GSiP library, [repository](https://github.com/SiEPIC/SiEPIC-Tools)
- Ansys Optics, [Layer builder - Simulation object](https://optics.ansys.com/hc/en-us/articles/360034382394-Layer-builder-Simulation-object)
- Ansys Optics, [Ring Modulator](https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator)
- Ansys Optics, [Workshop: Designing Foundry-Compatible Photonic Components and Circuits](https://optics.ansys.com/hc/en-us/articles/31257798958611-Workshop-Designing-Foundry-Compatible-Photonic-Components-and-Circuits)
- CORNERSTONE, [open PDK repository](https://github.com/cornerstone-uos/cornerstone-pdk)
- [KLayout](https://www.klayout.de/), [uv](https://docs.astral.sh/uv/)

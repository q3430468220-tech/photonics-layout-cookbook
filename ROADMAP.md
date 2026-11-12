# Roadmap

The cookbook grows along the design flow of [the front page](README.md): a device is laid out,
simulated and turned into a model for a circuit. A device is done when it has a builder that
passes the DRC, numbered simulation steps that load its GDS with the process file, figures
redrawn from the kept data, and a chapter that states the method, the results and the limits.
A process is done when it has a technology file, a DRC, process tables with a source for every
number, and a compiled process file that passes its check.

No item below has a date. Each one is listed in the order in which the flow needs it.

## Released

| version | what it added | where |
|---|---|---|
| v0.1 | an installable package with a generated PDK on top of `cspdk`, and a bridge that wrote Lumerical scripts | [legacy/](legacy/README.md) |
| v0.2 | the flat foundry-compatible flow on CORNERSTONE SOI220A: technology file, DRC, device, process file, six simulation steps | [more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) |
| v0.3 | this version: the GSiP teaching PDK with a complete back end, seven simulation steps, journal-style figures redrawn from kept data, and the five chapters of the course. The result arrays of every step are kept, so that every figure can be redrawn without Lumerical, and each step carries its own independent checks (a doping check, an energy balance, mesh checks) | the root of the repository |

v0.3 is organised as the five chapters of the course. Each chapter is one document:

| chapter | document | topic |
|---|---|---|
| 1 | [docs/pdk.md](docs/pdk.md) | The PDK: a process written as code |
| 2 | [docs/device.md](docs/device.md) | The device: drawing a heater-tuned ring modulator, and checking it |
| 3 | [gsip_process_file_py/README.md](gsip_process_file_py/README.md) | The process file: the same process for the simulator |
| 4 | [lumerical_simulations/ring_modulator/README.md](lumerical_simulations/ring_modulator/README.md) | The simulations: seven steps from the layout to the circuit |
| 5 | [docs/your_foundry.md](docs/your_foundry.md) | Your foundry: porting the flow to a real PDK |

## Next, on the same device

The next items extend the flow of the ring modulator in the order of the flow figure. Stage 3
of that figure, the compact model, is drawn but not built yet.

| item | what it adds | why it comes here |
|---|---|---|
| Compact model of the ring for INTERCONNECT | a model built from the data of steps 1 to 5, not typed by hand: κ²(gap), n_eff, n_g, the loss per turn, Δn_eff(V), and the K/mW of the heater | stage 3 of the flow figure; step 6 uses the same numbers today through the element's own inputs |
| Process corners from the statistical process file | the variation tables of the process file, with the reruns of the steps at the corners | the process file already has the variation tables; the flag that writes them is off today |
| Porting the corrections of v0.3 to the second example | the mesh lines on the silicon interfaces, the volume heat source, the series-RC capacitance, the refined resonances and the energy balance; the second example is kept as released in v0.2 until then | [more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) |
| Gap and junction-offset sweep on the mask | a test-structure block around the nominal design, with the gap as the variable | step 6 shows that the extinction depends strongly on the gap |

## More devices on the same process

Each device adds one new kind of simulation, and so teaches one new part of the process.

| device | new simulation | what it teaches |
|---|---|---|
| PN phase shifter and Mach-Zehnder modulator | a travelling-wave electrode in INTERCONNECT, on the CHARGE and MODE results of step 3 | the modulator as a long device, not a ring |
| Thermo-optic phase shifter with the undercut | HEAT with the undercut layer, then MODE | how a removed substrate changes the thermal path |
| Germanium photodetector | FDTD for the absorption, CHARGE for the reverse bias | the first device that needs the germanium layers |
| Grating coupler on the 150 nm slab | FDTD for the coupling to a fibre | the slab layer of the process used on its own |
| Silicon nitride waveguide | MODE on the nitride layer | a second core material in the same process file |

## Modules and circuits

These come after the devices. A module is several devices that share one process; a circuit is a
set of modules simulated together in INTERCONNECT.

| item | notes |
|---|---|
| Mach-Zehnder interferometer as a module | two couplers, two arms, and the phase shifter of the list above |
| Ring filter and add-drop ring | the ring of this course, with a second bus |
| Circuit simulation of a modulator link | the modulator, the photodetector and a driver model in one netlist |

## Other processes

A second process shows what is general in the flow and what belongs to one foundry. CORNERSTONE
SOI220A is the second process of this repository. Only processes with public data qualify.

| process | status of the public data |
|---|---|
| CORNERSTONE passive platforms | in the same official PDK repository as SOI220A |
| SiEPIC EBeam | an open PDK, passive |

## Infrastructure

| item | notes |
|---|---|
| Check of the technology file against the official `process_overview.yaml` in CI | today an optional test, see `more_processes/cornerstone_soi220a/tests/test_technology.py` |
| Comparison with measured devices | needs published data or a tape-out |

Suggestions are welcome. Open an issue with the device or process you would like to see, and the
public document it should follow. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add one.

# Roadmap

The cookbook is built bottom-up. First come the unit devices, the single components a circuit is
made of. The [device library](README.md#device-library) in the README shows each of them as a
drawing. The silicon devices, passive and active, are drawn on the same teaching PDK and simulated
with the same process file; the lithium niobate devices need a process of their own. Then come
the circuits that use them, in three directions: optical computing,
optical switching and optical interconnects. For those the deliverable is a layout plus a
link-level simulation in INTERCONNECT.

A device counts as done when it has a builder that passes the DRC, simulation scripts that load
its GDS together with the process file, figures drawn from the kept results, and a chapter that
explains the method, the numbers and the limits. Its card in the device library then gets a filled
dot and a link to that chapter. Nothing below has a date.

## Where we are

| version | what it added |
|---|---|
| v0.1 | a first package: a generated PDK and a bridge that wrote Lumerical scripts (removed from the tree, still in the git history) |
| v0.2 | the foundry-compatible flow on CORNERSTONE SOI220A, now in [more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) |
| v0.3 | the GSiP teaching PDK with a full back end, the heater-tuned ring modulator, seven simulation steps and five chapters |
| since v0.3 | the device library: builders in `devices/`, shared solver recipes, and the first four passive devices |

## Unit devices: passive

| device | main PDK layers | simulation | status |
|---|---|---|---|
| Strip waveguide, bend and taper | `WG` | MODE for the modes and the bend, EME for the taper | [done](lumerical_simulations/strip_waveguide/README.md) |
| Rib waveguide and bend | `WG`, `SLAB90` | MODE: index, group index, bend loss | [done](lumerical_simulations/rib_waveguide/README.md) |
| Directional coupler | `WG` | MODE for the supermodes, FDTD for the length and the spectrum | [done](lumerical_simulations/directional_coupler/README.md) |
| 1×2 MMI splitter | `WG` | EME for the length, FDTD for the spectrum | [done](lumerical_simulations/mmi1x2/README.md) |
| 2×2 MMI coupler | `WG` | EME, checked with FDTD | planned |
| Y-branch | `WG` | FDTD | planned |
| Waveguide crossing | `WG` | FDTD: loss and crosstalk | planned |
| Grating coupler | `WG`, `SLAB150` | FDTD, 2D then 3D: coupling to a fibre | planned |
| Edge coupler | `WG`, `DEEPTRENCH` | EME: overlap with a fibre mode | planned |
| Ring filter, all-pass and add-drop | `WG` | FDTD for the couplers, INTERCONNECT for the spectrum | planned |
| Mach-Zehnder interferometer | `WG` | INTERCONNECT, from the splitter and waveguide models | planned |
| Silicon nitride waveguide and the Si to SiN transition | `WGN`, `WG` | MODE, EME | planned |

## Unit devices: active

| device | main PDK layers | simulation | status |
|---|---|---|---|
| Microring modulator with a heater | `WG`, `SLAB90`, `N`, `P`, `NP`, `PP`, `NPP`, `PPP`, `VIAC`, `M1`, `VIA1`, `M2`, `VIA2`, `M3`, `PADOPEN`, `HEATER` | FDTD, MODE, CHARGE, HEAT, INTERCONNECT | done (v0.3) |
| Thermo-optic phase shifter, with and without undercut | `WG`, `HEATER`, `VIA1`, `M2`, `UNDERCUT` | HEAT for the temperature and the time constant, MODE for the phase: power per π | planned |
| PN phase shifter and travelling-wave Mach-Zehnder modulator | `WG`, `SLAB90`, `N`, `P`, `NP`, `PP`, `NPP`, `PPP`, `VIAC`, `M1`, `VIA1`, `M2`, `VIA2`, `M3` | CHARGE and MODE for the phase shifter; INTERCONNECT for the modulator, with the electrode as a transmission line | planned |
| PIN phase shifter and variable optical attenuator | `WG`, `SLAB90`, `NPP`, `PPP`, `VIAC`, `M1` | CHARGE in forward bias, MODE | planned |
| Germanium photodetector | `WG`, `GE`, `GEN`, `GEP`, `VIAC`, `M1` | FDTD for the absorption and the generation rate, then CHARGE for responsivity, dark current and bandwidth | planned |
| Tunable add-drop ring filter | `WG`, `HEATER` | FDTD for the couplers, HEAT and MODE for the tuning, INTERCONNECT for the spectrum | planned |
| 2×2 Mach-Zehnder switch | `WG`, `HEATER`, `VIA1`, `M2` | INTERCONNECT, from the splitter and thermo-optic phase shifter models: extinction, crosstalk and switching power | planned |

Before more devices are added, the ring modulator still needs two things. The first is a compact
model packaged for reuse in other circuits (stage 3 of the flow figure); today step 6 sets the
parameters of INTERCONNECT's ring modulator element straight from the result files. The second is
a set of process corners, from the variation tables in `gsip_process_file_py/gsip_csv/`, which the
compiler adds to the process file on request.

## Unit devices: thin-film lithium niobate

The GSiP process has no lithium niobate. These devices need a second teaching process: x-cut
lithium niobate on insulator, with a ridge etched part of the way through the film and gold
electrodes beside it. It will be written from published values, as a PDK and as a process file,
the way GSiP was, and it comes before any of the devices below.

| device | simulation | status |
|---|---|---|
| Rib waveguide and bend | MODE: the modes of the anisotropic crystal, group index, bend loss | planned |
| Edge coupler | EME: overlap with a fibre mode | planned |
| 1×2 MMI splitter | EME, checked with FDTD | planned |
| Electro-optic phase shifter | CHARGE for the static field between the electrodes, MODE for the index change it causes: voltage-length product | planned |
| Mach-Zehnder modulator | the phase shifter above; FEEM for the microwave mode of the electrode; INTERCONNECT for the electro-optic response | planned |
| Racetrack modulator | CHARGE and MODE for the tuning, INTERCONNECT for the spectrum | planned |
| Thermo-optic phase shifter | HEAT and MODE: power per π, used to set the bias point | planned |
| 2×2 electro-optic switch | INTERCONNECT, from the splitter and phase shifter models: extinction and crosstalk | planned |

The solver named for each step is a first plan. It will be checked when the chapter is written.

## Circuits and links

Each direction ends in a layout that passes the DRC and a link simulation built from the compact
models of the unit devices above.

| direction | layout | what the link simulation reports | unit devices it needs |
|---|---|---|---|
| Optical computing | an N×N Mach-Zehnder mesh (Reck and Clements arrangements); a microring weight bank | matrix fidelity under phase errors and loss; thermal crosstalk between heaters; phase calibration | Mach-Zehnder interferometers, splitters, thermo-optic phase shifters, ring filters, photodetectors |
| Optical switching | N×N fabrics built from the 2×2 switch (Beneš and path-independent-loss arrangements); a ring-based switch | insertion loss and crosstalk per path; extinction; switching time and power | 2×2 Mach-Zehnder switches, splitters, crossings, thermo-optic and PIN phase shifters, ring filters |
| Optical interconnects | a WDM transmitter with several ring modulators on one bus; a ring or Mach-Zehnder demultiplexer; a germanium receiver; a Mach-Zehnder modulator link | link budget; eye diagram; bit error rate against received power; crosstalk between channels; locking of the rings with their heaters | ring modulator, Mach-Zehnder modulator, photodetector, ring filters, splitters, grating or edge couplers |

## Housekeeping

| item | note |
|---|---|
| Port the v0.3 corrections to the CORNERSTONE example | mesh lines on the silicon surfaces, the volume heat source, the series-RC extraction, refined resonances |
| Rerun the FDTD coupler with a 10 nm mesh | κ² moves by 2 % between a 20 nm and a 10 nm mesh, see chapter 4 |
| More open processes | only processes whose data is public qualify |
| Comparison with measured devices | needs published data or a tape-out |

Suggestions are welcome: open an issue with the device or circuit you would like to see and the
public source it should follow. [CONTRIBUTING.md](CONTRIBUTING.md) explains how to add one.

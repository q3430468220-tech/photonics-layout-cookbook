# Roadmap

The cookbook is built bottom-up. First come the unit devices, the single components a circuit is
made of, passive and active. Each one is drawn on the same teaching PDK and simulated with the
same process file. Then come the circuits that use them, in three directions: optical computing,
optical switching and optical interconnects. For those the deliverable is a layout plus a
link-level simulation in INTERCONNECT.

A device counts as done when it has a builder that passes the DRC, simulation scripts that load
its GDS together with the process file, figures drawn from the kept results, and a chapter that
explains the method, the numbers and the limits. Nothing below has a date.

## Where we are

| version | what it added |
|---|---|
| v0.1 | a first package: a generated PDK and a bridge that wrote Lumerical scripts (removed from the tree, still in the git history) |
| v0.2 | the foundry-compatible flow on CORNERSTONE SOI220A, now in [more_processes/cornerstone_soi220a/](more_processes/cornerstone_soi220a/README.md) |
| v0.3 | the GSiP teaching PDK with a full back end, the heater-tuned ring modulator, seven simulation steps and five chapters |

## Unit devices: passive

| device | main PDK layers | simulation | status |
|---|---|---|---|
| Rib waveguide and bend | `WG`, `SLAB90` | MODE: index, group index, bend loss | done as step 2 of the ring modulator; the cells are part of the PDK |
| Strip waveguide, bends, tapers | `WG` | MODE, EME | planned |
| Directional coupler | `WG` | FDTD: S-parameters against gap and length | planned; step 1 of the ring already gives κ² against gap |
| MMI splitters, 1×2 and 2×2 | `WG` | EME, checked with FDTD | planned |
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

Before more devices are added, the ring modulator still needs two things. The first is a compact
model packaged for reuse in other circuits (stage 3 of the flow figure); today step 6 sets the
parameters of INTERCONNECT's ring modulator element straight from the result files. The second is
a set of process corners, from the variation tables in `gsip_process_file_py/gsip_csv/`, which the
compiler adds to the process file on request.

## Circuits and links

Each direction ends in a layout that passes the DRC and a link simulation built from the compact
models of the unit devices above.

| direction | layout | what the link simulation reports | unit devices it needs |
|---|---|---|---|
| Optical computing | an N×N Mach-Zehnder mesh (Reck and Clements arrangements); a microring weight bank | matrix fidelity under phase errors and loss; thermal crosstalk between heaters; phase calibration | Mach-Zehnder interferometers, splitters, thermo-optic phase shifters, ring filters, photodetectors |
| Optical switching | a 2×2 Mach-Zehnder switch cell; N×N fabrics (Beneš and path-independent-loss arrangements); a ring-based switch | insertion loss and crosstalk per path; extinction; switching time and power | Mach-Zehnder interferometers, splitters, crossings, thermo-optic and PIN phase shifters, ring filters |
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

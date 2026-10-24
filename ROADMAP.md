# Roadmap

The cookbook grows like a course: single devices first, then the functional modules built from them, then complete chip architectures. Each recipe is "done" when it has a gdsfactory cell, a process-independent geometry with unit tests, a Lumerical export that runs on the reference Lumerical version, and a short README that explains the design choices and gives a few exercises.

## Level 1: single devices

Single devices follow an official Ansys Lumerical application example wherever one exists, so the layout parameters and the simulation flow can be checked against Ansys' own files.

| # | device | Ansys reference example | Lumerical chain | status |
|---|---|---|---|---|
| 01 | Microring modulator, lateral PN, GSG pads | [Ring Modulator](https://optics.ansys.com/hc/en-us/articles/360042322794-Ring-Modulator) | CHARGE 2D → FDE (bent) → FDTD coupler → INTERCONNECT / CML | v0.1: layout, CHARGE, FDE, 3D FDTD export |
| 02 | PN depletion phase shifter | [PN depletion phase shifter](https://optics.ansys.com/hc/en-us/articles/360042328674-PN-depletion-phase-shifter) | CHARGE → FDE → CML Compiler | planned |
| 03 | Travelling-wave MZM (GSG/GS CPW electrodes) | [Travelling Wave MZM](https://optics.ansys.com/hc/en-us/articles/360042328774-Traveling-Wave-Mach-Zehnder-Modulator), [TW with distributed electrodes](https://optics.ansys.com/hc/en-us/articles/360055852653-Traveling-wave-modulators-with-distributed-electrodes) | CHARGE → FDE, electrode RF model → INTERCONNECT | planned |
| 04 | PIN phase shifter / PIN MZM | [PIN Mach-Zehnder modulator](https://optics.ansys.com/hc/en-us/articles/360042327854-PIN-Mach-Zehnder-modulator) | CHARGE (forward bias) → FDE | planned |
| 05 | Thermo-optic phase shifter (doped-Si and metal heaters) | Thermal switch example | HEAT → FDE | planned |
| 06 | Ge photodetector, vertical and lateral | [Vertical photodetector](https://optics.ansys.com/hc/en-us/articles/360042957893), Ge-on-Si lateral photodetector | FDTD (generation rate) → CHARGE | planned, needs a process with Ge |
| 07 | Passives: grating and edge couplers, MMI, directional coupler, y-branch, Euler bends, crossings | Grating coupler, y-branch, MMI examples | FDTD / EME / varFDTD S-parameters | planned |

## Level 2: functional modules

| # | module | key layout skills | simulation | status |
|---|---|---|---|---|
| 11 | 2×2 MZI unit cell with phase shifters | symmetric routing, heater placement, thermal isolation trenches | INTERCONNECT from the gdsfactory netlist | planned |
| 12 | Clements / Reck N×N MZI mesh | parametric arrays, path-length matching, pad fan-out | INTERCONNECT netlist export | planned |
| 13 | Add-drop and high-order (coupled) ring filters | gap control, FSR / Vernier design, heater per ring | FDTD coupler + INTERCONNECT | planned |
| 14 | WDM mux / demux (ring bank, lattice filter) | channel spacing, thermal tuning, crosstalk-aware routing | INTERCONNECT | planned |
| 15 | Ring-modulator WDM transmitter bank | shared bus, per-ring heaters and RF pads | INTERCONNECT (CML models from level 1) | planned |

## Level 3: architectures

| # | architecture | content | status |
|---|---|---|---|
| 21 | WDM optical interconnect link | MRM transmitter bank, drop-filter receiver with PDs, fibre I/O, pad ring | planned |
| 22 | Optical switch fabric | MZI crossbar / Beneš network, electrical routing to the chip edge | planned |
| 23 | Optical I/O (OIO) chiplet tile | multi-λ × multi-fibre ring-based I/O, EIC bump map, reticle-level floorplan | planned |

## Infrastructure and foundry adapters

| item | status |
|---|---|
| CORNERSTONE 220 nm SOI active (`cspdk` passives + public implant / via / metal layers) | v0.1 |
| SiEPIC EBeam (`ubcpdk`), gdsfactory generic PDK | planned |
| VTT 3 µm SOI, Luxtelligence thin-film LiNbO3, CORNERSTONE SiN / Ge-on-Si | planned |
| INTERCONNECT netlist export from `component.get_netlist()` | planned |
| KLayout DRC decks per process (width, spacing, enclosure of via in P++/N++) | planned |
| Case studies: reproduce published devices (e.g. heavily-doped narrow-trench MRMs) from layout to CHARGE/FDE | planned |
| Documentation site with notebooks (MkDocs or Jupyter Book) | planned |

Suggestions are welcome: open an issue with the device or architecture you would like to see, ideally with the paper or Ansys example it should follow.

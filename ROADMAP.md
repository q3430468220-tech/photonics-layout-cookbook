# Roadmap

The cookbook grows along the design flow. A device is done when it has a builder that passes the
DRC, numbered simulation steps that load its GDS with the process file, plots, and a README that
states the method, the results and the limits. A process is done when it has a technology file, a
DRC, process tables with a source for every number, and a compiled process file that passes its
read-back check.

## Done in v0.2

| item | where |
|---|---|
| CORNERSTONE SOI220A as a gdsfactory PDK, with the official layer names | `cornerstone_technology.py` |
| Design-rule check for the published rules | `cornerstone_drc.py` |
| Heater-tuned microring modulator layout | `rm_builder.py` |
| Layer Builder process file from CSV tables, with a read-back check | `cornerstone_process_file_py/` |
| Six simulation steps: FDTD, MODE, CHARGE, HEAT, MODE, INTERCONNECT | `lumerical_simulations/ring_modulator/` |

## Next on the same device

| item | notes |
|---|---|
| Compact model with CML Compiler | from the results of steps 1 to 5 |
| Time-domain modulation in INTERCONNECT | eye diagram at the optical bandwidth found in step 6 |
| Process corners | enable the variation tables, rerun steps 2 and 6 at the corners |
| Gap and junction-offset sweep on the mask | a test-structure block around the nominal design |
| Grating couplers and routing to a full test cell | with the official building blocks |

## More devices on SOI220A

| device | simulation chain | reference |
|---|---|---|
| PN depletion phase shifter and Mach-Zehnder modulator | CHARGE → MODE → INTERCONNECT, travelling-wave electrode | the official `MZM` building blocks; Ansys *Traveling Wave Mach-Zehnder Modulator* |
| Thermo-optic phase shifter | HEAT → MODE | the official `Heater` building block |
| Defect-mediated detector | FDTD → CHARGE | layer `Detector_Implant_DF` |
| Passives: grating coupler, MMI, crossing, rib-to-strip taper | FDTD, EME | the official building blocks as a cross-check |

## More processes

Only processes with public data qualify. Candidates:

| process | status of public data |
|---|---|
| CORNERSTONE SOI220 passive, SiN 300 nm, SOI 340 nm | in the same official repository |
| SiEPIC EBeam | open PDK, passive |
| gdsfactory generic PDK | open, not a real foundry process; useful for exercises |

## Infrastructure

| item | notes |
|---|---|
| A second process, to separate what is general from what is CORNERSTONE-specific | then extract the shared code |
| Check of the technology file against the official `process_overview.yaml` in CI | today an optional test, see `tests/test_technology.py` |
| Comparison with measured devices | needs published data or a tape-out |
| Documentation site | once there is more than one device |

Suggestions are welcome. Open an issue with the device or process you would like to see, and the
public document it should follow.

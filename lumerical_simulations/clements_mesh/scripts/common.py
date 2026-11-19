"""Shared by the steps of the Clements mesh: the layout, the results of the device chapters it is built from, and folders.

The mesh is a circuit of devices that have chapters of their own.  Nothing here is simulated again; every number is
read from the kept results of those chapters:

    directional_coupler/3_coupler_fdtd/coupler_fdtd.npz     the complex S-parameters of the coupler, 1.5 to 1.6 um
    directional_coupler/1_supermodes/supermodes.npz          the coupling length against the gap (step 4)
    directional_coupler/2_coupling_length/coupling_length.npz the length of the bends, and the FDTD coupling length
    strip_waveguide/1_waveguide_modes/strip_modes.npz        n_eff and n_g of the strip
    thermo_optic_phase_shifter/2_phase_shift/phase.npz       the change of n_eff per milliwatt, P_pi, the resistance
    thermo_optic_phase_shifter/4_neighbour/neighbour.npz     the conductivity of the substrate and the wafer (step 3)

The dimensions are read from devices/clements_mesh_builder.py, which draws the layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/clements_mesh/
FIGURES = ROOT / "figures"
SIMS = ROOT.parent
sys.path.insert(0, str(SIMS))  # lumerical_simulations/: flow.py

from flow import LAM, REPO, import_lumapi, um  # noqa: E402

from devices import clements_mesh_builder as cm  # noqa: E402
from devices import directional_coupler_builder as dcb  # noqa: E402
from devices import thermo_optic_phase_shifter_builder as tops  # noqa: E402

__all__ = ["C0", "FIGURES", "LAM", "LAYOUT", "LOSS_DB_CM", "REPO", "ROOT", "SCRATCH", "SIMS", "cm", "dcb", "import_lumapi",
           "inputs", "step_dir", "tops", "um"]  # fmt: skip

C0 = 299792458.0
LAYOUT = cm.clements_mesh().info  # the 4 x 4 mesh as drawn
SCRATCH = REPO / "build" / "scratch" / "clements_mesh"  # the S-parameter files and projects of check runs: not kept
# Propagation loss of the strip [assumption].  No chapter measures it; 2.2 dB/cm is the value that chapter 4 takes for
# the rib of this process (Baehr-Jones et al., arXiv:1203.0767).  Every path through a Clements mesh is about as long
# as every other, so a loss of this kind lowers all outputs alike and does not change the fidelity.
LOSS_DB_CM = 2.2
# The FDTD ports of the coupler stood 1 um beyond each end of the cell: the leads of 3 um, the region 1 um inside
# their end and the port 1 um inside the region (directional_coupler/scripts: LEAD, REGION_INSET, PORT_INSET).
COUPLER_PORT_EXTRA = 1.0


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def inputs() -> dict:
    """The numbers of the device chapters that the mesh is built from."""
    strip = np.load(SIMS / "strip_waveguide" / "1_waveguide_modes" / "strip_modes.npz")
    fdtd = np.load(SIMS / "directional_coupler" / "3_coupler_fdtd" / "coupler_fdtd.npz")
    phase = np.load(SIMS / "thermo_optic_phase_shifter" / "2_phase_shift" / "phase.npz")
    neighbour = np.load(SIMS / "thermo_optic_phase_shifter" / "4_neighbour" / "neighbour.npz")
    modes = np.load(SIMS / "directional_coupler" / "1_supermodes" / "supermodes.npz")
    length = np.load(SIMS / "directional_coupler" / "2_coupling_length" / "coupling_length.npz")
    drawn = list(phase["cases"]).index("drawn")
    return {
        "neff": float(strip["neff"]),
        "ng": float(strip["ng"]),
        "lam0": float(strip["lam"]),
        "coupler_lam": np.asarray(fdtd["lam"], dtype=float),  # um
        "coupler_S": {k: np.asarray(fdtd[f"S{k}"]) for k in (1, 2, 3, 4)},  # input at port 1, as the FDTD run
        "coupler_length": float(fdtd["length"]),
        "coupler_gap": float(fdtd["gap"]),
        "dneff_dP": float(phase["dneff_dP_drawn"]),  # per mW, averaged over the 100 um of film
        "dneff_dT": float(phase["dneff_dT_device"]),  # per kelvin of mean core temperature
        "P_pi": float(phase["P_pi_mW"][drawn]),
        "core_K_per_mW": float(phase["core_K_per_mW"][drawn]),
        "resistance": float(phase["resistance_ohm"]),
        "heater_length": float(phase["length_um"]),
        "k_silicon": float(neighbour["k_silicon"]),
        "wafer_um": float(neighbour["wafer_um"]),
        "neighbour_d": np.asarray(neighbour["estimate_distance_um"], dtype=float),
        "neighbour_K": np.asarray(neighbour["estimate_K_per_mW"], dtype=float),
        "gaps": np.asarray(modes["gaps"], dtype=float),
        "gap_l_pi": np.asarray(modes["gap_l_pi"], dtype=float),
        "l_pi_supermodes": float(modes["l_pi"]),
        "l_pi_fdtd": float(length["l_pi"]),
        "l_bends": float(length["l_bends"]),
    }

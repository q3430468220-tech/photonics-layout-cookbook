"""Shared by the simulation steps of the rib waveguide: its dimensions and its folders.

What every device shares comes from two files one level up:

    lumerical_simulations/flow.py       paths, wavelength band, add_layer_builder
    lumerical_simulations/solvers.py    the mode-solver recipes
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/rib_waveguide/
FIGURES = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent))  # lumerical_simulations/: flow.py and solvers.py

import flow  # noqa: E402
import solvers  # noqa: E402
from flow import LAM, LAM_MAX, LAM_MIN, REPO, T_SI, T_SLAB, add_layer_builder, import_lumapi, require_process_file, t, um  # noqa: E402

from devices import rib_waveguide_builder as rw  # noqa: E402

__all__ = [
    "FIGURES",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "RADIUS",
    "REPO",
    "ROOT",
    "SLAB_WIDTH",
    "T_SI",
    "T_SLAB",
    "WIDTH",
    "add_layer_builder",
    "flow",
    "import_lumapi",
    "require_process_file",
    "rw",
    "solvers",
    "step_dir",
    "t",
    "um",
]

# ---- the device: the dimensions of devices/rib_waveguide_builder.py ----
WIDTH = rw.WIDTH  # 0.5 um
SLAB_WIDTH = rw.SLAB_WIDTH  # 6.0 um
RADIUS = rw.RADIUS  # 10 um, the rib bend radius of the design rules


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d

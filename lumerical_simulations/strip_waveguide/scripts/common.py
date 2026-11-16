"""Shared by the simulation steps of the strip waveguide: its dimensions and its folders.

What every device shares comes from two files one level up:

    lumerical_simulations/flow.py       paths, wavelength band, add_layer_builder
    lumerical_simulations/solvers.py    the mode-solver and EME recipes
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/strip_waveguide/
FIGURES = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent))  # lumerical_simulations/: flow.py and solvers.py

import flow  # noqa: E402
import solvers  # noqa: E402
from flow import LAM, LAM_MAX, LAM_MIN, REPO, T_SI, add_layer_builder, import_lumapi, require_process_file, t, um  # noqa: E402

from devices import strip_waveguide_builder as sw  # noqa: E402

__all__ = [
    "FIGURES",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "RADIUS",
    "REPO",
    "ROOT",
    "TAPER_LENGTH",
    "T_SI",
    "WIDE_WIDTH",
    "WIDTH",
    "add_layer_builder",
    "flow",
    "import_lumapi",
    "require_process_file",
    "solvers",
    "step_dir",
    "sw",
    "t",
    "um",
]

# ---- the device: the dimensions of devices/strip_waveguide_builder.py ----
WIDTH = sw.WIDTH  # 0.5 um
WIDE_WIDTH = sw.WIDE_WIDTH  # 3.0 um
TAPER_LENGTH = sw.TAPER_LENGTH
RADIUS = sw.RADIUS  # 5 um, the strip bend radius of the design rules


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d

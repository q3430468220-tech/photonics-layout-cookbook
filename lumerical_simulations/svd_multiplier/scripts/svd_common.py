"""Shared by the steps of the real matrix multiplier: the layout, the numbers of the device chapters, and folders.

The multiplier is built of the same devices as the Clements mesh, and its circuit is that of the mesh twice with a
column of attenuators between: every number is read from the kept results of the device chapters, through the
common file of lumerical_simulations/clements_mesh (inputs()), and the model of the mesh (mesh_model.py) is reused.

The dimensions are read from devices/svd_multiplier_builder.py, which draws the layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/svd_multiplier/
FIGURES = ROOT / "figures"
SIMS = ROOT.parent
MESH_SCRIPTS = SIMS / "clements_mesh" / "scripts"
for p in (SIMS, MESH_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# the numbers of the device chapters and the assumptions of the mesh: the same as in its chapter
from common import COUPLER_PORT_EXTRA, LOSS_DB_CM, inputs  # noqa: E402  (clements_mesh/scripts/common.py)
from flow import LAM, REPO, import_lumapi, um  # noqa: E402

from devices import svd_multiplier_builder as sb  # noqa: E402

__all__ = ["COUPLER_PORT_EXTRA", "FIGURES", "LAM", "LAYOUT", "LOSS_DB_CM", "REPO", "ROOT", "SCRATCH", "SIMS", "import_lumapi",
           "inputs", "sb", "step_dir", "um"]  # fmt: skip

LAYOUT = sb.svd_multiplier().info  # the 4 x 4 multiplier as drawn
SCRATCH = REPO / "build" / "scratch" / "svd_multiplier"  # S-parameter files and projects of check runs: not kept


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d

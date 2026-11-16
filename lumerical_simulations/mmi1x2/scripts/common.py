"""Shared by the simulation steps of the 1x2 MMI splitter: its dimensions, its folders, and its layout with leads.

What every device shares comes from two files one level up:

    lumerical_simulations/flow.py       paths, wavelength band, add_layer_builder
    lumerical_simulations/solvers.py    the EME and FDTD recipes
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/mmi1x2/
FIGURES = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent))  # lumerical_simulations/: flow.py and solvers.py

import flow  # noqa: E402
import solvers  # noqa: E402
from flow import LAM, LAM_MAX, LAM_MIN, REPO, T_SI, add_layer_builder, import_lumapi, require_process_file, t, um  # noqa: E402

from devices import mmi1x2_builder as mb  # noqa: E402

__all__ = [
    "FIGURES",
    "GAP_MMI",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "LEAD",
    "LENGTH_MMI",
    "LENGTH_TAPER",
    "OUTPUT_Y",
    "REPO",
    "ROOT",
    "T_SI",
    "WIDTH",
    "WIDTH_MMI",
    "WIDTH_TAPER",
    "add_layer_builder",
    "flow",
    "import_lumapi",
    "layout_gds",
    "mb",
    "require_process_file",
    "solvers",
    "step_dir",
    "t",
    "um",
]

# ---- the device: the defaults of mmi1x2_builder.mmi1x2(), read from its signature ----
_defaults = {k: v.default for k, v in inspect.signature(mb.mmi1x2).parameters.items()}
LENGTH_MMI = float(_defaults["length_mmi"])
WIDTH_MMI = float(_defaults["width_mmi"])
WIDTH_TAPER = float(_defaults["width_taper"])
LENGTH_TAPER = float(_defaults["length_taper"])
GAP_MMI = float(_defaults["gap_mmi"])
WIDTH = float(_defaults["width"])
OUTPUT_Y = (WIDTH_TAPER + GAP_MMI) / 2  # the two outputs lie at y = +- this
LEAD = 3.0  # um of straight waveguide added at every port for the simulations


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def layout_gds(path: Path, length_mmi: float = LENGTH_MMI) -> tuple[Path, dict]:
    """The splitter with a straight lead at every port, centred on the middle of the multimode section.

    Returns the GDS path and the x positions the solvers need (um): the two faces of the multimode section,
    the narrow ends of the tapers, and the ends of the leads.
    """
    import gdsfactory as gf

    device = gf.components.extend_ports(component=mb.mmi1x2(length_mmi=length_mmi), length=LEAD)
    c = gf.Component()
    ref = c << device
    ref.dmovex(-length_mmi / 2)  # the builder puts the input face at x = 0
    x = dict(face_in=-length_mmi / 2, face_out=length_mmi / 2)
    x.update(taper_in=x["face_in"] - LENGTH_TAPER, taper_out=x["face_out"] + LENGTH_TAPER)
    x.update(lead_in=x["taper_in"] - LEAD, lead_out=x["taper_out"] + LEAD)
    return t.write_gds_for_lumerical(c, path, cellname=path.stem), x

"""Shared by the simulation steps of the directional coupler: its dimensions, its folders, and its layouts.

What every device shares comes from two files one level up:

    lumerical_simulations/flow.py       paths, wavelength band, add_layer_builder
    lumerical_simulations/solvers.py    the mode-solver and FDTD recipes
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/directional_coupler/
FIGURES = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent))  # lumerical_simulations/: flow.py and solvers.py

import flow  # noqa: E402
import solvers  # noqa: E402
from flow import LAM, LAM_MAX, LAM_MIN, REPO, T_SI, add_layer_builder, import_lumapi, require_process_file, t, um  # noqa: E402

from devices import directional_coupler_builder as dc  # noqa: E402

__all__ = [
    "BEND_LENGTH",
    "FIGURES",
    "GAP",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "LEAD",
    "LENGTH",
    "PORT_SPACING",
    "REPO",
    "ROOT",
    "T_SI",
    "WIDTH",
    "add_layer_builder",
    "coupler_gds",
    "dc",
    "flow",
    "import_lumapi",
    "require_process_file",
    "section_gds",
    "solvers",
    "step_dir",
    "t",
    "um",
]

# ---- the device: the defaults of directional_coupler_builder.directional_coupler(), read from its signature ----
_defaults = {k: v.default for k, v in inspect.signature(dc.directional_coupler).parameters.items()}
GAP = float(_defaults["gap"])
LENGTH = float(_defaults["length"])
WIDTH = float(_defaults["width"])
PORT_SPACING = float(_defaults["port_spacing"])
BEND_LENGTH = float(_defaults["bend_length"])
LEAD = 3.0  # um of straight waveguide added at every port for the FDTD runs


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def section_gds(path: Path, gap: float = GAP, length: float = 6.0, cellname: str | None = None) -> Path:
    """Two parallel strips ``gap`` apart, along x and centred on the origin: the cross-section of the coupler."""
    import gdsfactory as gf

    c = gf.Component()
    ref = c << gf.components.coupler_straight(length=length, gap=gap, cross_section=gf.get_cross_section("strip", width=WIDTH))
    ref.dcenter = (0.0, 0.0)
    return t.write_gds_for_lumerical(c, path, cellname=cellname or path.stem)


def coupler_gds(path: Path, length: float = LENGTH, gap: float = GAP, cellname: str | None = None) -> tuple[Path, dict]:
    """The coupler with a straight lead at every port; the middle of the straight section is the origin.

    Returns the GDS path and the positions the solver needs (um): the ends of the straight section, of the
    S-bends and of the leads along x, and the y of the ports.
    """
    import gdsfactory as gf

    device = gf.components.extend_ports(component=dc.directional_coupler(gap=gap, length=length), length=LEAD)
    c = gf.Component()
    ref = c << device
    ref.dcenter = (0.0, 0.0)
    x = dict(straight=length / 2, bend=length / 2 + BEND_LENGTH, lead=length / 2 + BEND_LENGTH + LEAD, port_y=PORT_SPACING / 2)
    return t.write_gds_for_lumerical(c, path, cellname=cellname or path.stem), x

"""Shared by the simulation steps of the thermo-optic phase shifter: its dimensions, its folders, and its cross-section as a GDS.

What every device shares comes from two files one level up and is passed on from here:

    lumerical_simulations/flow.py       paths, wavelength band, add_layer_builder
    lumerical_simulations/solvers.py    add_heat_cross_section and the other solver recipes

The dimensions are not typed here.  They are read from devices/thermo_optic_phase_shifter_builder.py, the layout
that the simulations draw.  The layer stack, the materials and the heat sink come from the process file, as for every
device:

    a GDS drawn with the PDK   +   gsip_process.lbr   ->   Layer Builder object
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/thermo_optic_phase_shifter/
FIGURES = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent))  # lumerical_simulations/: flow.py and solvers.py

import solvers  # noqa: E402
from flow import LAM, REPO, add_layer_builder, import_lumapi, require_process_file, t, um  # noqa: E402
from solvers import clean_logs  # noqa: E402

from devices import thermo_optic_phase_shifter_builder as tops  # noqa: E402

__all__ = [
    "DEVICE_INFO",
    "FIGURES",
    "HEATER_RESISTANCE",
    "HEATER_WIDTH",
    "HEAT_DIR",
    "ISOLATED_FRACTION",
    "LAM",
    "LENGTH",
    "REPO",
    "ROOT",
    "SCRATCH",
    "TRENCH_GAP",
    "TRENCH_LENGTH",
    "TRENCH_WIDTH",
    "WIDTH",
    "add_layer_builder",
    "clean_logs",
    "closest_trench_gap",
    "import_lumapi",
    "require_process_file",
    "section_gds",
    "solvers",
    "step_dir",
    "t",
    "temperature_map",
    "um",
]

# ---- the device: read from the builder, which draws the layout the simulations load ----
DEVICE_INFO = tops.thermo_optic_phase_shifter().info  # the device as drawn, with its default arguments
LENGTH = float(tops.LENGTH)  # um: heated length, the free filament between the two landings [T]
WIDTH = float(tops.WIDTH)  # um: core width, the single-mode strip of strip_waveguide [B][GF]
HEATER_WIDTH = float(tops.HEATER_WIDTH)  # um: TiN film above the core
TRENCH_GAP = float(tops.TRENCH_GAP)  # um: centre line of the core to the inner edge of each trench
TRENCH_WIDTH = float(tops.TRENCH_WIDTH)  # um: width of each trench, from its inner edge outwards
TRENCH_LENGTH = float(DEVICE_INFO["length_trenches"])  # um: the part of the heated length with a trench beside it
ISOLATED_FRACTION = float(DEVICE_INFO["isolated_fraction"])  # TRENCH_LENGTH / LENGTH
HEATER_RESISTANCE = float(DEVICE_INFO["heater_resistance"])  # ohm: the filament, from the sheet resistance of the PDK

SCRATCH = REPO / "build" / "scratch" / "tops" / "heat"  # sweep layouts and check runs: git-ignored, not kept
HEAT_DIR = ROOT / "1_heat_cross_section"  # the kept results of step 1, including the temperature maps for step 2


def step_dir(name: str) -> Path:
    """The folder of a step, created on first use."""
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def temperature_map(name: str, power_mW: float) -> Path:
    """The .mat file that step 1 exports for a run named ``name`` at ``power_mW``, e.g. device_T_10mW.mat.

    Step 2 imports it with importdataset as the "temperature" grid attribute of the Layer Builder.
    """
    return HEAT_DIR / f"{name}_T_{power_mW:g}mW.mat"


def closest_trench_gap(heater_width: float, width: float = WIDTH) -> float:
    """The smallest trench gap that the rules allow for this heater width.

    The trench must clear the heater film by trench_to_heater and the core by trench_to_waveguide
    (gsip_technology.DESIGN_RULES), and the wall between the two trenches must be as wide as the minimum space of
    the deep trench (gsip_technology.MIN_WIDTH_SPACE); all three are [T].  For the 2.0 um heater the first and the
    third rule both give the default gap of 2.0 um; a narrower heater does not let the trench come closer, because
    the wall may not be narrower.
    """
    to_heater = heater_width / 2 + t.DESIGN_RULES["trench_to_heater"]
    to_core = width / 2 + t.DESIGN_RULES["trench_to_waveguide"]
    wall = t.MIN_WIDTH_SPACE["DEEPTRENCH"][1] / 2
    return max(to_heater, to_core, wall)


def _strip(x0: float, x1: float, y0: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def section_gds(path: Path, trench_gap: float | None = TRENCH_GAP, heater_width: float = HEATER_WIDTH,
                trench_width: float = TRENCH_WIDTH, width: float = WIDTH, length: float = 6.0,
                cellname: str | None = None, heater: bool = True) -> Path:  # fmt: skip
    """GDS of a straight piece of the device along x, centred on the origin: the core, the heater film and the trenches.

    trench_gap: centre line of the core to the inner edge of each trench (um).  None draws the reference without
    trenches, which has the same core and film.
    heater: False leaves the film out, for the check of what the film does to the light (step 2).
    length: the length of the piece along x (um).  A two-dimensional solver does not use it; the Layer Builder box
    is built from it.
    The layers are the technology file's: WG, HEATER and DEEPTRENCH.
    """
    import gdsfactory as gf

    c = gf.Component()
    x0, x1 = -length / 2, length / 2
    c.add_polygon(_strip(x0, x1, -width / 2, width / 2), layer=t.LAYER.WG)
    if heater:
        c.add_polygon(_strip(x0, x1, -heater_width / 2, heater_width / 2), layer=t.LAYER.HEATER)
    if trench_gap is not None:
        for side in (+1, -1):
            y0, y1 = sorted((side * trench_gap, side * (trench_gap + trench_width)))
            c.add_polygon(_strip(x0, x1, y0, y1), layer=t.LAYER.DEEPTRENCH)
    return t.write_gds_for_lumerical(c, path, cellname=cellname or path.stem)

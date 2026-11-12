"""Shared by the six simulation steps: paths, the device parameters, and the Layer Builder set-up.

Every step builds its structure the same way, which is the point of the flow:

    a small GDS drawn with the PDK   +   cornerstone_process.lbr   ->   Layer Builder object

so the layer stack, the materials and the doping are never typed into a simulation script.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
REPO = ROOT.parents[1]
LBR = REPO / "cornerstone_process_file_py" / "cornerstone_process.lbr"
PLOTS = ROOT / "plots"
sys.path.insert(0, str(REPO))

import inspect  # noqa: E402

import cornerstone_technology as t  # noqa: E402
import rm_builder as rm  # noqa: E402
from lumerical_env import import_lumapi, lumerical_root  # noqa: E402

# Names the step scripts import from here.
__all__ = [
    "C0",
    "GAP",
    "HEATER_ANGLE",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "LBR",
    "L_HEATER",
    "L_PN",
    "L_RING",
    "PLOTS",
    "PN_ANGLE",
    "RADIUS",
    "REPO",
    "ROOT",
    "SI_MATERIAL",
    "SLAB_WIDTH",
    "T_BOX",
    "T_METAL",
    "T_SI",
    "T_SLAB",
    "WIDTH",
    "Z_METAL",
    "add_layer_builder",
    "import_lumapi",
    "lumerical_root",
    "plot_dir",
    "require_process_file",
    "rm",
    "section_gds",
    "step_dir",
    "strip",
    "t",
    "um",
]

um = 1e-6
C0 = 299792458.0
LAM = 1.55  # um, design wavelength
LAM_MIN, LAM_MAX = 1.50, 1.60

# ---- the device: the defaults of rm_builder.ring_modulator(), read from its signature ----

_defaults = {k: v.default for k, v in inspect.signature(rm.ring_modulator).parameters.items()}
RADIUS = float(_defaults.get("radius", 25.0))
WIDTH = float(_defaults.get("width", 0.45))
GAP = float(_defaults.get("gap", 0.25))
PN_ANGLE = float(_defaults.get("pn_angle", 240.0))
HEATER_ANGLE = float(_defaults.get("heater_angle", 76.0))
SLAB_WIDTH = rm.SLAB_WIDTH
L_RING = 2 * math.pi * RADIUS  # um
L_PN = L_RING * PN_ANGLE / 360  # doped arc
L_HEATER = L_RING * HEATER_ANGLE / 360 - rm.LEAD_WIDTH  # free filament between the two leads

# ---- process numbers the scripts need for windows and averages (all from the technology file) ----
T_SI, T_SLAB, Z_METAL, T_METAL, T_BOX = t.T_SI, t.T_SLAB, t.Z_METAL, t.T_METAL, t.T_BOX
SI_MATERIAL = "cornerstone Si_np"  # name of the silicon after the process file is loaded


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def plot_dir(name: str) -> Path:
    d = PLOTS / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def require_process_file() -> None:
    if not LBR.exists():
        raise SystemExit(f"{LBR} is missing: run cornerstone_process_file_py/cornerstone_process_file_compiler.py first")


def add_layer_builder(app, gds: Path, x_span: float, y_span: float, name: str = "device") -> None:
    """Add a Layer Builder centred on the origin and load the layout and the process file (spans in um)."""
    app.addlayerbuilder()
    app.set("name", name)
    app.set("x", 0)
    app.set("y", 0)
    app.set("z", 0)
    app.set("x span", x_span * um)
    app.set("y span", y_span * um)
    app.set("gds position reference", "Centered at origin")  # GDS coordinates = simulation coordinates
    app.loadgdsfile(gds.as_posix())
    app.loadprocessfile(LBR.as_posix())


def section_gds(path: Path, cross_section, length: float = 6.0, extra=None) -> Path:
    """GDS of a straight waveguide section along x, centred on the origin.

    ``cross_section`` is a PDK cross-section (name or object).  ``extra(component, x0, x1)`` may add
    polygons such as vias or a heater.  The file is written with write_gds_for_lumerical().
    """
    import gdsfactory as gf

    c = gf.Component()
    ref = c << gf.path.extrude(gf.path.straight(length), cross_section=gf.get_cross_section(cross_section))
    ref.dmovex(-length / 2)
    if extra is not None:
        extra(c, -length / 2, length / 2)
    return t.write_gds_for_lumerical(c, path, cellname=path.stem)


def strip(x0: float, x1: float, y0: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

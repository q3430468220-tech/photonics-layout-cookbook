"""What the simulations of every device share: the paths, the wavelength band, and the Layer Builder set-up.

Every solver run of this repository builds its structure the same way, which is the point of the flow:

    a GDS drawn with the PDK   +   gsip_process.lbr   ->   Layer Builder object

so the layer stack, the materials and the doping are never typed into a simulation script.

    lumerical_simulations/
        flow.py                 this file
        solvers.py              recipes that more than one device uses: mode solver, EME, FDTD
        <device>/scripts/       common.py holds the parameters of that device; one script per step

A step script imports from the ``common.py`` next to it, which passes on what it takes from here.
"""

from __future__ import annotations

import sys
from pathlib import Path

SIMULATIONS = Path(__file__).resolve().parent  # lumerical_simulations/
REPO = SIMULATIONS.parent
LBR = REPO / "gsip_process_file_py" / "gsip_process.lbr"
sys.path.insert(0, str(REPO))

import gsip_technology as t  # noqa: E402
from lumerical_env import import_lumapi, lumerical_root  # noqa: E402

__all__ = [
    "C0",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "LBR",
    "REPO",
    "SIMULATIONS",
    "SI_MATERIAL",
    "T_SI",
    "T_SLAB",
    "Z_M1",
    "add_layer_builder",
    "device_gds",
    "import_lumapi",
    "layout_extent",
    "lumerical_root",
    "require_process_file",
    "t",
    "um",
]

um = 1e-6
C0 = 299792458.0
LAM = 1.55  # um, design wavelength
LAM_MIN, LAM_MAX = 1.50, 1.60

# ---- process numbers the scripts need for windows and averages (all from the technology file) ----
T_SI, T_SLAB, Z_M1 = t.T_SI, t.T_SLAB90, t.Z_M1
SI_MATERIAL = "gsip Si_np"  # name of the silicon after the process file is loaded


def require_process_file() -> None:
    if not LBR.exists():
        raise SystemExit(f"{LBR} is missing: run gsip_process_file_py/gsip_process_file_compiler.py first")


def device_gds(name: str) -> Path:
    """The layout that ``devices/<name>_builder.py`` writes; stops with the command to run if it is missing."""
    gds = REPO / "devices" / "gds" / f"{name}.gds"
    if not gds.exists():
        raise SystemExit(f"{gds} is missing: run devices/{name}_builder.py first")
    return gds


def layout_extent(gds: Path) -> tuple[float, float, float, float]:
    """Bounding box of a GDS file in um: (left, bottom, right, top)."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds))
    box = layout.top_cell().dbbox()
    return box.left, box.bottom, box.right, box.top


def add_layer_builder(app, gds: Path, x_span: float | None = None, y_span: float | None = None, name: str = "device") -> None:
    """Add a Layer Builder centred on the origin and load the layout and the process file (spans in um).

    The Layer Builder builds only what lies inside its box, and the box is centred on the origin.  A layout
    that reaches further is cut off without a word, and the solver then finds air where the device should
    be.  Leave the spans out and the box is made large enough for the whole layout, wherever it lies.
    """
    if x_span is None or y_span is None:
        left, bottom, right, top = layout_extent(gds)
        x_span = 2 * max(abs(left), abs(right)) + 2.0 if x_span is None else x_span
        y_span = 2 * max(abs(bottom), abs(top)) + 2.0 if y_span is None else y_span
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

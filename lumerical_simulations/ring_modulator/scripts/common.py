"""Shared by the simulation steps: paths, the device parameters, and the Layer Builder set-up.

Every step builds its structure the same way, which is the point of the flow:

    a small GDS drawn with the PDK   +   gsip_process.lbr   ->   Layer Builder object

so the layer stack, the materials and the doping are never typed into a simulation script.
"""

from __future__ import annotations

import inspect
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
REPO = ROOT.parents[1]
LBR = REPO / "gsip_process_file_py" / "gsip_process.lbr"
FIGURES = ROOT / "figures"
sys.path.insert(0, str(REPO))

import gsip_technology as t  # noqa: E402
import rm_builder as rm  # noqa: E402
from lumerical_env import import_lumapi, lumerical_root  # noqa: E402

# Names the step scripts import from here.
__all__ = [
    "C0",
    "FIGURES",
    "GAP",
    "HEATER_ANGLE",
    "LAM",
    "LAM_MAX",
    "LAM_MIN",
    "LBR",
    "L_HEATER",
    "L_PN",
    "L_RING",
    "PN_ANGLE",
    "P_INSIDE",
    "RADIUS",
    "REPO",
    "ROOT",
    "SI_MATERIAL",
    "SLAB_WIDTH",
    "T_SI",
    "T_SLAB",
    "WIDTH",
    "Z_M1",
    "add_layer_builder",
    "add_rib_mesh",
    "import_lumapi",
    "lumerical_root",
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
RADIUS = float(_defaults["radius"])
WIDTH = float(_defaults["width"])
GAP = float(_defaults["gap"])
PN_ANGLE = float(_defaults["pn_angle"])
HEATER_ANGLE = float(_defaults["heater_angle"])
P_INSIDE = bool(_defaults["p_inside"])  # False: n inside the ring (+y in the section), p outside
SLAB_WIDTH = rm.SLAB_WIDTH
L_RING = 2 * math.pi * RADIUS  # um
L_PN = L_RING * PN_ANGLE / 360  # doped arc
L_HEATER = L_RING * HEATER_ANGLE / 360 - rm.LANDING  # free heater filament between its two landings

# ---- process numbers the scripts need for windows and averages (all from the technology file) ----
T_SI, T_SLAB, Z_M1 = t.T_SI, t.T_SLAB90, t.Z_M1
SI_MATERIAL = "gsip Si_np"  # name of the silicon after the process file is loaded


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def require_process_file() -> None:
    if not LBR.exists():
        raise SystemExit(f"{LBR} is missing: run gsip_process_file_py/gsip_process_file_compiler.py first")


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


RIB_MARGIN = 0.3  # um: the slab mesh box runs this far beyond each core edge


def add_rib_mesh(app, width: float = WIDTH, step: float = 0.01) -> None:
    """Two mesh overrides that put a mesh line on every silicon surface of the rib (spans in um).

    Why: a uniform FDE mesh (20 nm here) has no line on the 90 nm slab surface or on the core sidewalls,
    unless a cell boundary happens to fall there, and which surfaces get one depends on where the window
    starts.  The same undoped rib bent to R = 10 um gave n_eff = 2.57648 in the step-2 window (8 x 2.4 um)
    and 2.56932 in the step-5 window (3.4 x 1.9 um).  With a line on every interface both windows agree:
    uniform 10 nm gives 2.57102 in both, uniform 5 nm gives 2.57053 in both, and a 20 nm mesh with a 10 nm
    override over the rib gives 2.57016 and 2.57014.

    A mesh override forces a mesh line on each of its faces, so the faces are put on the silicon surfaces:
        core mesh   |y| <= width / 2,            T_SLAB <= z <= T_SI   (core sidewalls, slab top, core top)
        slab mesh   |y| <= width / 2 + 0.3 um,   0 <= z <= T_SLAB      (slab edges beyond the core, slab bottom)
    The mesh inside them is ``step`` in y and z.  Call it after the FDE object is added.
    """
    half = width / 2
    boxes = {
        "core mesh": (half, T_SLAB, T_SI),
        "slab mesh": (half + RIB_MARGIN, 0.0, T_SLAB),
    }
    for name, (half_y, z0, z1) in boxes.items():
        app.addmesh()
        app.set("name", name)
        app.set("x", 0)
        app.set("x span", 1 * um)
        app.set("y", 0)
        app.set("y span", 2 * half_y * um)
        app.set("z min", z0 * um)
        app.set("z max", z1 * um)
        app.set("override x mesh", 0)  # the structure is 2D in x: the x mesh of the FDE is not used
        app.set("override y mesh", 1)
        app.set("override z mesh", 1)
        app.set("set maximum mesh step", 1)
        app.set("dy", step * um)
        app.set("dz", step * um)


def strip(x0: float, x1: float, y0: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def section_gds(path: Path, doped: bool = True, contacts: bool = True, metal: bool = False, heater: bool = False,
                length: float = 6.0, width: float = WIDTH, cellname: str | None = None) -> Path:  # fmt: skip
    """GDS of a straight piece of the ring's cross-section, along x and centred on the origin.

    The piece is cut out of the device as rm_builder draws it, unrolled.  +y is the inside of the ring
    (the ring centre lies at +y).  The implant there is n with the default p_inside=False, and p with
    p_inside=True (P_INSIDE, read from rm_builder.ring_modulator).  The bend in steps 2 and 5 pushes the
    mode to -y, away from the centre.

        doped     the six implants of the PDK cross-section ``rib_pn``, with P_INSIDE; otherwise the plain ``rib``
        contacts  the two rows of contact vias, drawn as continuous strips
        metal     metal 1: the inner disc (from M1_GAP to the ring centre, y = RADIUS) and the outer arc
        heater    the TiN film above the core
    """
    import gdsfactory as gf

    xs = (
        gf.get_cross_section("rib_pn", width=width, width_slab=SLAB_WIDTH, p_inside=P_INSIDE)
        if doped
        else gf.get_cross_section("rib", width=width, width_slab=SLAB_WIDTH)
    )
    c = gf.Component()
    ref = c << gf.path.extrude(gf.path.straight(length), cross_section=xs)
    ref.dmovex(-length / 2)
    x0, x1 = -length / 2, length / 2
    if contacts:
        for side in (+1, -1):
            y0, y1 = sorted((side * rm.VIA_GAP, side * (rm.VIA_GAP + rm.VIA_SIZE)))
            c.add_polygon(strip(x0, x1, y0, y1), layer=t.VIAC)
    if metal:
        # inner disc: from the gap to the ring centre (y = RADIUS), which is as far as the disc reaches when seen
        # from the waveguide.  A straight cross-section cannot describe what lies beyond the centre of the ring.
        c.add_polygon(strip(x0, x1, rm.M1_GAP, RADIUS), layer=t.M1)
        c.add_polygon(strip(x0, x1, -rm.M1_GAP - rm.M1_WIDTH, -rm.M1_GAP), layer=t.M1)  # outer arc
    if heater:
        c.add_polygon(strip(x0, x1, -rm.HEATER_WIDTH / 2, rm.HEATER_WIDTH / 2), layer=t.HEATER)
    return t.write_gds_for_lumerical(c, path, cellname=cellname or path.stem)

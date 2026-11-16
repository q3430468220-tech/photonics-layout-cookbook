"""Shared by the simulation steps of the ring modulator: its parameters, its folders, and its cross-section as a GDS.

What every device shares comes from two files one level up and is passed on from here:

    lumerical_simulations/flow.py       paths, wavelength band, add_layer_builder
    lumerical_simulations/solvers.py    add_rib_mesh and the other solver recipes

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
FIGURES = ROOT / "figures"
sys.path.insert(0, str(ROOT.parent))  # lumerical_simulations/: flow.py and solvers.py

from flow import (  # noqa: E402
    C0,
    LAM,
    LAM_MAX,
    LAM_MIN,
    LBR,
    REPO,
    SI_MATERIAL,
    T_SI,
    T_SLAB,
    Z_M1,
    add_layer_builder,
    import_lumapi,
    lumerical_root,
    require_process_file,
    t,
    um,
)
from solvers import add_rib_mesh  # noqa: E402

from devices import ring_modulator_builder as rm  # noqa: E402

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

# ---- the device: the defaults of ring_modulator_builder.ring_modulator(), read from its signature ----
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


def step_dir(name: str) -> Path:
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def strip(x0: float, x1: float, y0: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def section_gds(path: Path, doped: bool = True, contacts: bool = True, metal: bool = False, heater: bool = False,
                length: float = 6.0, width: float = WIDTH, cellname: str | None = None) -> Path:  # fmt: skip
    """GDS of a straight piece of the ring's cross-section, along x and centred on the origin.

    The piece is cut out of the device as ring_modulator_builder draws it, unrolled.  +y is the inside of the ring
    (the ring centre lies at +y).  The implant there is n with the default p_inside=False, and p with
    p_inside=True (P_INSIDE, read from ring_modulator_builder.ring_modulator).  The bend in steps 2 and 5 pushes the
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

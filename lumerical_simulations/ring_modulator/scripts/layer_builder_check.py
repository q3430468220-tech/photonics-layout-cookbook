"""Check - what did the Layer Builder build?  Refractive-index slices of the finished device.

Before any physics, look at the structure.  The whole ring modulator (rm_ring.gds) is loaded with
gsip_process.lbr, and the mode solver's mesh is used as a probe: it reports the refractive index it
sees on a plane.  Two vertical cuts and four horizontal cuts are saved:

    cut through the PN section (north side of the ring)   substrate and buried oxide below, contacts, metal 1,
                                                          heater, the metal 2 wire above
    cut through the coupler (south side)                  ring and bus cores on the common slab, the gap
    z = 45 nm    slab level                               ring slab merged with bus slab
    z = 160 nm   core level                               ring and bus cores
    z = 1.17 um  metal 1 / heater level                   disc, arc, heater ring with its landings
    z = 2.65 um  metal 2 level                            the five wires

A layer expression that is wrong in the process file shows up here at once, as a missing or misplaced
shape.  No solver licence is used beyond MODE.

    python layer_builder_check.py

Output in 0_layer_builder_check/:  structure.npz
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import GAP, LAM, RADIUS, REPO, WIDTH, add_layer_builder, import_lumapi, require_process_file, step_dir, um

OUT = step_dir("0_layer_builder_check")
GDS = REPO / "rm_ring.gds"
SPAN = 36.0  # um: the Layer Builder covers the ring and the first part of the wires
PN_CUT_Z = (-5.5, 3.6)  # um: the PN cut reaches the substrate (-12 .. -2 um) and the buried oxide (-2 .. 0 um)
Y_BUS = -(RADIUS + WIDTH + GAP)

# name -> (solver type, centre (x, y, z), spans (um), mesh step (um))
VERTICAL = {
    "pn_section": ((0.0, RADIUS, sum(PN_CUT_Z) / 2), (0.0, 9.0, PN_CUT_Z[1] - PN_CUT_Z[0]), 0.02),
    "coupler": ((0.0, (Y_BUS - RADIUS) / 2, 0.25), (0.0, 5.0, 1.5), 0.01),
}
HORIZONTAL = {"slab": 0.045, "core": 0.16, "metal1": 1.17, "metal2": 2.65}
TOP_SPAN, TOP_MESH = 32.0, 0.05


def index_on_plane(m, solver: str, centre, spans, mesh: float) -> dict:
    """Mesh one plane and return the refractive index the solver sees there."""
    m.switchtolayout()
    m.select("FDE")
    m.delete()
    m.addfde()
    m.set("solver type", solver)
    x, y, z = centre
    axes = {"2D X normal": ("y", "z"), "2D Z normal": ("x", "y")}[solver]
    for axis, value in (("x", x), ("y", y), ("z", z)):
        m.set(axis, value * um)
    for axis, span in zip(("x", "y", "z"), spans, strict=True):
        if axis in axes:
            m.set(f"{axis} span", span * um)
            m.set(f"define {axis} mesh by", "maximum mesh step")
            m.set(f"d{axis}", mesh * um)
    m.setanalysis("wavelength", LAM * um)
    m.mesh()
    out = {axis: np.squeeze(m.getdata("FDE::data::material", axis)) / um for axis in axes}
    out["index"] = np.squeeze(m.getdata("FDE::data::material", f"index_{axes[0]}")).astype(np.complex64)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()  # no options: --help prints this text and exits before the solver is started
    require_process_file()
    if not GDS.exists():
        raise SystemExit(f"{GDS} is missing: run rm_builder.py first")
    lumapi = import_lumapi()
    t0 = time.time()
    res = dict(radius=RADIUS, width=WIDTH, gap=GAP, y_bus=Y_BUS)
    with lumapi.MODE(hide=True) as m:
        add_layer_builder(m, GDS, SPAN, SPAN)
        m.addfde()
        for name, (centre, spans, mesh) in VERTICAL.items():
            r = index_on_plane(m, "2D X normal", centre, spans, mesh)
            res.update({f"{name}_y": r["y"], f"{name}_z": r["z"], f"{name}_index": r["index"]})
            print(f"vertical cut {name}: {r['index'].shape}  ({time.time() - t0:.0f} s)", flush=True)
        for name, z in HORIZONTAL.items():
            r = index_on_plane(m, "2D Z normal", (0.0, 0.0, z), (TOP_SPAN, TOP_SPAN, 0.0), TOP_MESH)
            res.update({f"{name}_x": r["x"], f"{name}_yy": r["y"], f"{name}_index": r["index"], f"{name}_level": z})
            print(f"horizontal cut {name} at z = {z} um: {r['index'].shape}  ({time.time() - t0:.0f} s)", flush=True)
        m.switchtolayout()
        m.save(str(OUT / "structure.lms"))
    np.savez_compressed(OUT / "structure.npz", **res)

    # what should be there, read off the index: silicon ~3.48, oxide ~1.44, metals have a large imaginary part
    cut = res["pn_section_index"]
    y, z = res["pn_section_y"], res["pn_section_z"]
    at = lambda yy, zz: cut[np.argmin(np.abs(y - yy)), np.argmin(np.abs(z - zz))]  # noqa: E731
    lines = [
        "Refractive index seen by the mode solver on the cut through the PN section (x = 0, north side of the ring):",
        f"  substrate          (y = R,        z = -5.00): {at(RADIUS, -5.0):.3f}   expect silicon, about 3.48",
        f"  buried oxide       (y = R,        z = -1.00): {at(RADIUS, -1.0):.3f}   expect oxide, about 1.44",
        f"  core centre        (y = R,        z = 0.11): {at(RADIUS, 0.11):.3f}   expect silicon, about 3.48",
        f"  slab               (y = R - 1.0,  z = 0.05): {at(RADIUS - 1.0, 0.05):.3f}   expect silicon",
        f"  above the slab     (y = R - 1.0,  z = 0.15): {at(RADIUS - 1.0, 0.15):.3f}   expect oxide, about 1.44",
        f"  inner contact via  (y = R - 2.15, z = 0.60): {at(RADIUS - 2.15, 0.60):.3f}   expect aluminium (large imaginary part)",
        f"  heater film        (y = R,        z = 1.17): {at(RADIUS, 1.17):.3f}   expect TiN",
        f"  metal 1, outer arc (y = R + 2.6,  z = 1.45): {at(RADIUS + 2.6, 1.45):.3f}   expect aluminium",
        f"  metal 2 wire       (y = R,        z = 2.65): {at(RADIUS, 2.65):.3f}   expect aluminium",
        f"  between the levels (y = R,        z = 2.00): {at(RADIUS, 2.00):.3f}   expect oxide",
    ]
    (OUT / "structure.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

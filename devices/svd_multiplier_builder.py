"""Real matrix multiplier on the GSiP teaching process: any real N x N matrix, by its singular value decomposition.

A real matrix M, scaled so that its largest singular value is 1, is M = U Sigma V^T: two orthogonal matrices and a
diagonal of numbers between 0 and 1.  The multiplier sets the three in turn on the light (D. A. B. Miller,
"Self-configuring universal linear optical component", Photonics Research 1, 1, 2013; Y. Shen et al., "Deep learning
with coherent nanophotonic circuits", Nature Photonics 11, 441, 2017):

    part         what it is
    -----------  ------------------------------------------------------------------------------------------------
    mesh V       a Clements mesh of devices/clements_mesh_builder.py: it sets V^T
    attenuators  one Mach-Zehnder interferometer on every row, with a second waveguide of its own, half a pitch above
                 the row, that takes the light it does not pass (the dump).  Its heater, on the dump arm, sets how
                 much of the field stays on the row: sin(theta / 2), any value from 0 to 1
    mesh U       a second Clements mesh: it sets U

The phase that an attenuator adds to its row is taken up by the output phase shifters of mesh V, which stand just
before it; so one heater per attenuator is enough.  Every row runs through the same pieces in the column of the
attenuators, so all paths stay as long as each other (as in the mesh, match_delay).

    one attenuator, between its dump (above) and its row:

       dump  ...........╲          ╱══[ theta ]══╲          ╱...........  (open ends: the light it takes leaves here)
                         ═coupler═                ═coupler═
       row   ═══════════╱          ╲══════════════╱          ╲══════════

The heaters of rows 0 and 1 have their pads above, those of rows 2 and 3 below; the attenuators of the inner rows
stand one heater step further along x than those of the outer rows, so that their wires pass beside them.

Coordinates (um): row m at y = -m * pitch, as in the mesh; the inputs o1 ... oN on the west side, the outputs
o(N+1) ... o(2N) on the east.  The electrical ports carry the name of their heater with the part in front:
V_P0_w ... (mesh V), A0_w ... (attenuators), U_P0_w ... (mesh U).

    python devices/svd_multiplier_builder.py   ->  devices/gds/svd_multiplier.gds, the DRC report and two preview images
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t
from devices import clements_mesh_builder as cm
from devices import directional_coupler_builder as dcb

N = cm.N
PITCH = cm.PITCH
LEAD = 20.0  # straight waveguide before the first attenuator and after the last one


def attenuator_length() -> float:
    """One attenuator: fan, coupler, fan, the arm section with its heater, fan, coupler, fan."""
    dc = cm.coupler()
    dc_len = dc.ports["o4"].dcenter[0] - dc.ports["o1"].dcenter[0]
    return 4 * cm.FAN_LENGTH + 2 * dc_len + cm.SECTION


@gf.cell
def attenuator_column(n: int = N, pitch: float = PITCH) -> gf.Component:
    """A Mach-Zehnder attenuator on every row, its dump half a pitch above the row and its heater on the dump arm."""
    cm.check_arguments(n, pitch)
    c = gf.Component()
    xs = gf.get_cross_section("strip", width=dcb.WIDTH)
    rows = [-m * pitch for m in range(n)]
    half = pitch / 2
    # the dump of row 0 lies half a pitch above it, and the trenches of its heater reach 8 um higher still: the pads
    # above stand half a pitch further out than those of the mesh, so that no trench runs under their metal
    pad_north, pad_south = rows[0] + half + cm.PAD_OFFSET, rows[-1] - cm.PAD_OFFSET
    dc = cm.coupler()
    dc_len = dc.ports["o4"].dcenter[0] - dc.ports["o1"].dcenter[0]
    alen = attenuator_length()
    place = cm.stagger(list(range(n)), n)
    step = cm.heater_step()
    length = LEAD + step * max(place.values()) + alen + LEAD

    def straight(x0: float, x1: float, y: float) -> None:
        if x1 - x0 > 1e-6:
            s = c << gf.components.straight(length=x1 - x0, cross_section=xs)
            s.dmove((x0, y))

    heaters, units = [], []
    for m in range(n):
        x0 = LEAD + place[m] * step
        dump, row = rows[m] + half, rows[m]
        centre = (dump + row) / 2
        straight(0.0, x0, row)
        for start in (x0, x0 + 2 * cm.FAN_LENGTH + dc_len + cm.SECTION):
            for y, flip in ((dump, False), (row, True)):  # in: from the dump and the row to the ports of the coupler
                f = c << cm.fan(half)
                if flip:
                    f.dmirror_y()
                f.dmove((start, y))
            ref = c << dc
            ref.dmove((start + cm.FAN_LENGTH + dc_len / 2, centre))
            for y, flip in ((dump, True), (row, False)):  # out: back to the dump and the row
                f = c << cm.fan(half)
                if flip:
                    f.dmirror_y()
                f.dmove((start + cm.FAN_LENGTH + dc_len, centre + (dcb.PORT_SPACING / 2 if y == dump else -dcb.PORT_SPACING / 2)))
            if start == x0:  # the two arms between the couplers
                arm0 = start + 2 * cm.FAN_LENGTH + dc_len
                straight(arm0, arm0 + cm.SECTION, dump)
                straight(arm0, arm0 + cm.SECTION, row)
        straight(x0 + alen, length, row)
        heater_x = x0 + 2 * cm.FAN_LENGTH + dc_len + cm.SECTION / 2
        pad_y = pad_north if cm.is_north(m, n) else pad_south
        heaters.append({"kind": "attenuator", "block": -1, "row": m, **cm.add_heater(c, f"A{m}", heater_x, dump, pad_y)})
        units.append({"row": m, "x0": round(x0, 4), "dump_y": round(dump, 4)})
        c.add_port(f"d{m}_in", center=(x0, dump), width=dcb.WIDTH, orientation=180, layer=t.WG)
        c.add_port(f"d{m}_out", center=(x0 + alen, dump), width=dcb.WIDTH, orientation=0, layer=t.WG)
    for m in range(n):
        c.add_port(f"o{m + 1}", center=(0.0, rows[m]), width=dcb.WIDTH, orientation=180, layer=t.WG)
        c.add_port(f"o{n + m + 1}", center=(length, rows[m]), width=dcb.WIDTH, orientation=0, layer=t.WG)
    c.info["n"] = n
    c.info["pitch"] = pitch
    c.info["length"] = round(length, 4)
    c.info["attenuator_length"] = round(alen, 4)
    c.info["coupler_length"] = round(dc_len, 4)
    c.info["fan_length"] = cm.FAN_LENGTH
    c.info["section"] = cm.SECTION
    c.info["heater_length"] = cm.HEATER_LENGTH
    c.info["units"] = units
    c.info["heaters"] = heaters
    return c


@gf.cell
def svd_multiplier(n: int = N, pitch: float = PITCH) -> gf.Component:
    """Mesh V, the attenuators and mesh U, joined row by row.

    ``info`` holds the dimensions of the three parts, where each one starts along x, and the heaters of each, which
    the simulations read: "v" and "u" are the info of the two meshes, "a" that of the attenuators.
    """
    c = gf.Component()
    mesh = cm.clements_mesh(n=n, pitch=pitch)
    column = attenuator_column(n=n, pitch=pitch)
    xv, xa = 0.0, float(mesh.info["length"])
    xu = xa + float(column.info["length"])
    for part, cell, x in (("V", mesh, xv), ("A", column, xa), ("U", mesh, xu)):
        ref = c << cell
        ref.dmovex(x)
        for port in ref.ports:
            if port.port_type == "electrical":
                name = port.name if part == "A" else f"{part}_{port.name}"
                c.add_port(name, port=port)
            elif (
                (part == "V" and port.name in {f"o{m + 1}" for m in range(n)})
                or (part == "U" and port.name in {f"o{n + m + 1}" for m in range(n)})
                or (part == "A" and port.name.startswith("d"))
            ):
                c.add_port(port.name, port=port)
    c.info["n"] = n
    c.info["pitch"] = pitch
    c.info["x"] = {"v": xv, "a": xa, "u": xu}
    c.info["length"] = round(xu + float(mesh.info["length"]), 4)
    c.info["v"] = dict(mesh.info)
    c.info["a"] = dict(column.info)
    c.info["u"] = dict(mesh.info)
    c.info["heaters"] = len(mesh.info["heaters"]) * 2 + len(column.info["heaters"])
    return c


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.parse_args(argv)
    from devices import write_device

    device = svd_multiplier()
    info = device.info
    print(
        f"{info['n']} x {info['n']} real matrix multiplier: two meshes and {info['n']} attenuators, {info['heaters']} heaters, "
        f"{2 * info['heaters']} pads; {info['length'] / 1000:.2f} mm long"
    )
    xa = info["x"]["a"]
    return write_device(
        device, "svd_multiplier", zoom=(xa - 20, -info["pitch"] * 3.6, xa + info["a"]["length"] + 20, info["pitch"] * 1.2)
    )


if __name__ == "__main__":
    sys.exit(main())

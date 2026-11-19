"""Clements mesh of Mach-Zehnder interferometers on the GSiP teaching process: a programmable N x N interferometer.

An N x N Clements mesh (W. R. Clements et al., "Optimal design for universal multiport interferometers", Optica 3,
1460, 2016) has N waveguides and N columns of 2 x 2 blocks.  Column c pairs the waveguides (p, p + 1) for
p = c % 2, c % 2 + 2, ...: the blocks of one column sit between those of the next, like bricks, and there are
N (N - 1) / 2 of them.  Each block is a Mach-Zehnder interferometer with two phase shifters, and a last column
of phase shifters sits on the outputs.  Set to the right phases, the mesh realises any unitary matrix.

    one block (a Mach-Zehnder interferometer), between the rows p (upper) and p + 1 (lower):

       row p      ══[ phi ]══╲          ╱══[ theta ]══╲          ╱══
                              ═coupler═                ═coupler═
       row p + 1  ═══════════╱          ╲═════════════╱          ╲══

    part              what it is
    ----------------  ---------------------------------------------------------------------------------------
    coupler           the directional coupler of lumerical_simulations/directional_coupler, unchanged: its
                      ports are 4 um apart, so S-bends (the fan) open its ports out to the pitch of the rows
    theta             the thermo-optic phase shifter on the upper arm: it sets the split of the block
    phi               the same phase shifter on the upper input: it sets the phase between the two inputs
    outputs           one phase shifter on every output, after the last column (the column D of the paper)
    dummy path        an edge row that has no block in a column runs through the same fans and one arm of a coupler,
                      so that all paths of the mesh have the same length (match_delay)

Every phase shifter is the heated section of devices/thermo_optic_phase_shifter_builder.py: the TiN film with
its landings and via 1, a deep trench on each side, and a metal 2 wire from each landing to a pad.  The pads
lie in a row above the mesh for the heaters on the upper half of the rows and below it for the lower half,
each pad straight above or below its landing, so that no wire crosses another.  Pads that would land on the
same place are avoided by shifting blocks along x (for N > 4) and by staggering the output phase shifters.

Coordinates (um): row m lies at y = -m * pitch, so row 0 is the top one; the inputs o1 ... oN are on the west
side, from row 0 down, and the outputs o(N+1) ... o(2N) on the east side, from row 0 down.  The electrical
ports carry the name of their heater and its side: P<k>_w, P<k>_e (phi of block k), T<k>_w, T<k>_e (theta of
block k), D<m>_w, D<m>_e (output of row m).  Blocks are counted column by column, from the top.

    python devices/clements_mesh_builder.py     ->  devices/gds/clements_mesh.gds, the DRC report and two preview images
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t
from devices import directional_coupler_builder as dcb
from devices import thermo_optic_phase_shifter_builder as tops
from devices.wiring import pad_with_tab, reach_beyond, square, wire

# ---- dimensions (um) ----
N = 4  # the size of the mesh in this chapter
PITCH = 30.0  # rows centre to centre: the arms of a block are this far apart
FAN_LENGTH = 40.0  # along x, each S-bend between the 4 um ports of a coupler and the rows
HEATER_LENGTH = tops.LENGTH  # 100 um of film: the phase shifter of its chapter
SECTION = HEATER_LENGTH + 2 * (tops.LANDING_LENGTH + tops.WG_EXTRA)  # 114 um of straight waveguide under a heater
LEAD = 20.0  # straight waveguide before the first column and after the last phase shifter
PAD_SIZE = tops.PAD_SIZE  # 80 um
PAD_OFFSET = tops.PAD_Y  # from the outermost row to the centre of its row of pads: 60 um, as in the phase shifter
PAD_SPACE = 100.0  # the smallest distance between the centres of two pads: 80 um of metal and 20 um between


def coupler() -> gf.Component:
    """The directional coupler of its chapter, as simulated: 0.2 um gap, 15 um, ports 4 um apart."""
    return dcb.directional_coupler()


def fan_offset(pitch: float) -> float:
    """How far each S-bend of the fan moves a waveguide sideways: from the row to the port of the coupler."""
    return (pitch - dcb.PORT_SPACING) / 2


@gf.cell
def fan(pitch: float = PITCH, length: float = FAN_LENGTH) -> gf.Component:
    """S-bend from a row to a port of the coupler; o1 on the row, o2 at the coupler, fan_offset(pitch) lower."""
    xs = gf.get_cross_section("strip", width=dcb.WIDTH)
    return gf.components.bend_s(size=(length, -fan_offset(pitch)), cross_section=xs, allow_min_radius_violation=True)


@gf.cell
def coupler_arm(upper: bool = True) -> gf.Component:
    """One arm of the coupler alone: the same S-bends and straight section as the upper (or lower) waveguide of
    coupler(), with no second waveguide beside it.  Centred like the coupler, on the middle of its gap; ports o1
    (west) and o2 (east), PORT_SPACING / 2 above (or below) the centre."""
    xs = gf.get_cross_section("strip", width=dcb.WIDTH)
    dy = (dcb.PORT_SPACING - dcb.GAP - dcb.WIDTH) / 2
    sign = 1.0 if upper else -1.0
    y_port, y_arm = sign * dcb.PORT_SPACING / 2, sign * (dcb.GAP + dcb.WIDTH) / 2
    c = gf.Component()
    down = c << gf.components.bend_s(size=(dcb.BEND_LENGTH, -sign * dy), cross_section=xs, allow_min_radius_violation=True)
    down.dmove((-dcb.LENGTH / 2 - dcb.BEND_LENGTH, y_port))
    s = c << gf.components.straight(length=dcb.LENGTH, cross_section=xs)
    s.dmove((-dcb.LENGTH / 2, y_arm))
    up = c << gf.components.bend_s(size=(dcb.BEND_LENGTH, sign * dy), cross_section=xs, allow_min_radius_violation=True)
    up.dmove((dcb.LENGTH / 2, y_arm))
    c.add_port("o1", port=down.ports["o1"])
    c.add_port("o2", port=up.ports["o2"])
    c.info["length"] = round(2 * float(down.cell.info["length"]) + dcb.LENGTH, 4)
    return c


def block_length() -> float:
    """phi section, fan, coupler, fan, theta section, fan, coupler, fan."""
    dc = coupler()
    dc_len = dc.ports["o4"].dcenter[0] - dc.ports["o1"].dcenter[0]
    return 2 * SECTION + 4 * FAN_LENGTH + 2 * dc_len


def heater_centres() -> tuple[float, float]:
    """x of the centre of phi and of theta, from the west edge of a block."""
    phi = SECTION / 2
    theta = SECTION + 2 * FAN_LENGTH + (block_length() - 2 * SECTION - 4 * FAN_LENGTH) / 2 + SECTION / 2
    return phi, theta


def heater_step() -> float:
    """The distance between phi and theta of a block, which is also the step between staggered output heaters."""
    phi, theta = heater_centres()
    return theta - phi


def blocks(n: int) -> list[tuple[int, int]]:
    """The blocks column by column, from the top: (column, upper row)."""
    return [(c, p) for c in range(n) for p in range(c % 2, n - 1, 2)]


def is_north(row: int, n: int) -> bool:
    """A heater on this row has its pads above the mesh (upper half of the rows) or below it."""
    return row < n / 2


def stagger(rows: list[int], n: int) -> dict[int, int]:
    """For heaters that would share the same x on several rows: the place of each along x, 0 for the one nearest its
    row of pads.  The wires of an inner heater then pass the outer rows where those have no heater."""
    north = sorted(r for r in rows if is_north(r, n))
    south = sorted((r for r in rows if not is_north(r, n)), reverse=True)
    return {r: k for group in (north, south) for k, r in enumerate(group)}


def check_arguments(n: int, pitch: float) -> None:
    if n < 2:
        raise ValueError(f"n = {n}: a mesh needs at least two waveguides")
    lowest = tops.TRENCH_GAP + tops.TRENCH_WIDTH + t.DESIGN_RULES["trench_to_waveguide"] + dcb.WIDTH / 2
    if pitch < lowest:
        raise ValueError(
            f"pitch {pitch} um: the trenches of a heater reach {tops.TRENCH_GAP + tops.TRENCH_WIDTH} um from its row, "
            f"so the next row must be {lowest:.2f} um away by the rule trench_to_waveguide"
        )
    radius = float(fan(pitch).info["min_bend_radius"])
    rule = t.DESIGN_RULES["strip_bend_radius"]
    if radius < rule:
        raise ValueError(
            f"pitch {pitch} um: the S-bends of the fan curve down to a radius of {radius:.2f} um, below the strip bend "
            f"radius of {rule} um"
        )
    phi, theta = heater_centres()
    gap = theta - phi - 2 * tops.via_x(HEATER_LENGTH)  # between the inner landings of phi and theta
    if gap < PAD_SPACE - 1e-9 or block_length() - (theta - phi) - 2 * tops.via_x(HEATER_LENGTH) < PAD_SPACE - 1e-9:
        raise ValueError("the pads of two heaters of a block would overlap")


def add_heater(c: gf.Component, name: str, x: float, y: float, pad_y: float) -> dict:
    """The heated section on the waveguide at (x, y): film, landings, via 1, trenches, two wires and two pads."""
    film = c << tops.heater_film(length=HEATER_LENGTH, heater_width=tops.HEATER_WIDTH)
    film.dmove((x, y))
    trench_len = tops.check_arguments(HEATER_LENGTH, tops.HEATER_WIDTH, tops.TRENCH_GAP, tops.TRENCH_WIDTH, dcb.WIDTH)
    trenches = c << tops.trench_pair(length=trench_len, gap=tops.TRENCH_GAP, width=tops.TRENCH_WIDTH)
    trenches.dmove((x, y))
    up = 1.0 if pad_y > y else -1.0
    for side, sign in (("w", -1.0), ("e", 1.0)):
        vx = x + sign * tops.via_x(HEATER_LENGTH)
        end = pad_with_tab(c, (vx, pad_y), PAD_SIZE)
        start_reach = reach_beyond((vx, y), (0.0, up), [square((vx, y), tops.VIA1_SIZE)])
        wire(c, [(vx, y), (vx, end[1])], start_reach=start_reach, width=tops.WIRE_WIDTH)
        c.add_port(f"{name}_{side}", center=(vx, pad_y), width=PAD_SIZE, orientation=90 if up > 0 else 270,
                   layer=t.M3, port_type="electrical")  # fmt: skip
    return {"name": name, "x": round(x, 4), "y": round(y, 4), "pad_y": round(pad_y, 4)}


@gf.cell
def clements_mesh(n: int = N, pitch: float = PITCH, match_delay: bool = True) -> gf.Component:
    """The N x N mesh: waveguides, couplers, fans, heaters with trenches, wires and pads.

    Args:
        n: the number of waveguides, inputs and outputs.
        pitch: the distance between two neighbouring rows (um).
        match_delay: in a column, an edge row without a block runs through the same fans and one arm of a coupler
            (coupler_arm), towards the inside of the mesh, so that every path of the column is as long as every other.
            False draws it straight, as a first draft of this layout did: the rows then differ in length, and the
            matrix holds over a narrow band only (step 2 of the chapter).

    ``info`` holds the dimensions, the list of blocks with the x of their west edge, and every heater with its
    kind, block or row, the centre of its film and the row of its pads, which the simulations read.
    """
    check_arguments(n, pitch)
    c = gf.Component()
    xs = gf.get_cross_section("strip", width=dcb.WIDTH)
    rows = [-m * pitch for m in range(n)]
    pad_north = rows[0] + PAD_OFFSET
    pad_south = rows[-1] - PAD_OFFSET
    blen = block_length()
    phi_x, theta_x = heater_centres()
    dc = coupler()
    dc_len = dc.ports["o4"].dcenter[0] - dc.ports["o1"].dcenter[0]

    def straight(x0: float, x1: float, y: float) -> None:
        if x1 - x0 > 1e-6:
            s = c << gf.components.straight(length=x1 - x0, cross_section=xs)
            s.dmove((x0, y))

    ends = [0.0] * n  # how far each row has been drawn
    for m in range(n):
        c.add_port(f"o{m + 1}", center=(0.0, rows[m]), width=dcb.WIDTH, orientation=180, layer=t.WG)
    heaters: list[dict] = []
    placed: list[dict] = []
    dummies: list[dict] = []
    x = LEAD
    for column in range(n):
        members = [(k, p) for k, (cc, p) in enumerate(blocks(n)) if cc == column]
        place = stagger([p for _, p in members], n)
        width = blen * (1 + max(place.values())) if members else 0.0  # a column without a block (N = 2) takes no room
        for k, p in members:
            x0 = x + place[p] * blen
            for m in (p, p + 1):
                straight(ends[m], x0, rows[m])
            # phi on the upper input, theta on the upper arm: straight sections of SECTION
            straight(x0, x0 + SECTION, rows[p])
            straight(x0, x0 + SECTION, rows[p + 1])
            centre = (rows[p] + rows[p + 1]) / 2
            for start in (x0 + SECTION, x0 + 2 * SECTION + 2 * FAN_LENGTH + dc_len):
                for m, flip in ((p, False), (p + 1, True)):  # in: from the rows to the ports of the coupler
                    f = c << fan(pitch)
                    if flip:
                        f.dmirror_y()
                    f.dmove((start, rows[m]))
                coupler_ref = c << dc
                coupler_ref.dmove((start + FAN_LENGTH + dc_len / 2, centre))
                for m, flip in ((p, True), (p + 1, False)):  # out: from the coupler back to the rows
                    f = c << fan(pitch)
                    if flip:
                        f.dmirror_y()
                    f.dmove((start + FAN_LENGTH + dc_len, centre + (dcb.PORT_SPACING / 2 if m == p else -dcb.PORT_SPACING / 2)))
                if start == x0 + SECTION:  # the arms between the two couplers
                    arm0 = start + 2 * FAN_LENGTH + dc_len
                    straight(arm0, arm0 + SECTION, rows[p])
                    straight(arm0, arm0 + SECTION, rows[p + 1])
            for m in (p, p + 1):
                ends[m] = x0 + blen
            pad_y = pad_north if is_north(p, n) else pad_south
            heaters.append({"kind": "phi", "block": k, "row": p, **add_heater(c, f"P{k}", x0 + phi_x, rows[p], pad_y)})
            heaters.append({"kind": "theta", "block": k, "row": p, **add_heater(c, f"T{k}", x0 + theta_x, rows[p], pad_y)})
            placed.append({"block": k, "column": column, "upper": p, "x0": round(x0, 4)})
        # the edge rows without a block: the same path as a row of a block, with one arm of a coupler
        paired = {m for _, p in members for m in (p, p + 1)}
        for m in sorted(set(range(n)) - paired) if members and match_delay else []:
            upper = m < n - 1  # paired, in thought, with the row below it (row 0) or above it (the last row)
            centre = rows[m] + (-pitch / 2 if upper else pitch / 2)
            straight(ends[m], x, rows[m])
            straight(x, x + SECTION, rows[m])
            for start in (x + SECTION, x + 2 * SECTION + 2 * FAN_LENGTH + dc_len):
                f = c << fan(pitch)
                if not upper:
                    f.dmirror_y()
                f.dmove((start, rows[m]))
                arm = c << coupler_arm(upper)
                arm.dmove((start + FAN_LENGTH + dc_len / 2, centre))
                f = c << fan(pitch)
                if upper:
                    f.dmirror_y()
                f.dmove((start + FAN_LENGTH + dc_len, centre + (dcb.PORT_SPACING / 2 if upper else -dcb.PORT_SPACING / 2)))
                if start == x + SECTION:
                    arm0 = start + 2 * FAN_LENGTH + dc_len
                    straight(arm0, arm0 + SECTION, rows[m])
            ends[m] = x + blen
            dummies.append({"column": column, "row": m, "x0": round(x, 4), "upper": upper})
        x += width
    # the output phase shifters, staggered so that the wires of the inner rows pass the outer rows beside their heaters
    place = stagger(list(range(n)), n)
    step = heater_step()
    for m in range(n):
        x0 = x + place[m] * step
        straight(ends[m], x0, rows[m])
        straight(x0, x0 + SECTION, rows[m])
        ends[m] = x0 + SECTION
        pad_y = pad_north if is_north(m, n) else pad_south
        heaters.append({"kind": "out", "block": -1, "row": m, **add_heater(c, f"D{m}", x0 + SECTION / 2, rows[m], pad_y)})
    east = max(ends) + LEAD
    for m in range(n):
        straight(ends[m], east, rows[m])
        c.add_port(f"o{n + m + 1}", center=(east, rows[m]), width=dcb.WIDTH, orientation=0, layer=t.WG)

    c.info["n"] = n
    c.info["pitch"] = pitch
    c.info["block_length"] = round(blen, 4)
    c.info["section"] = SECTION
    c.info["fan_length"] = FAN_LENGTH
    c.info["fan_offset"] = fan_offset(pitch)
    c.info["fan_min_radius"] = round(float(fan(pitch).info["min_bend_radius"]), 3)
    c.info["coupler_length"] = round(dc_len, 4)
    c.info["heater_length"] = HEATER_LENGTH
    c.info["length"] = round(east, 4)
    c.info["match_delay"] = match_delay
    c.info["arm_length"] = float(coupler_arm(True).info["length"])
    c.info["blocks"] = placed
    c.info["dummies"] = dummies
    c.info["heaters"] = heaters
    return c


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=N, help="number of waveguides (default 4)")
    args = parser.parse_args(argv)
    from devices import write_device

    mesh = clements_mesh(n=args.n)
    info = mesh.info
    print(
        f"{info['n']} x {info['n']} Clements mesh: {len(info['blocks'])} blocks, {len(info['heaters'])} heaters, "
        f"{2 * len(info['heaters'])} pads; {info['length'] / 1000:.2f} mm long, rows {info['pitch']} um apart, "
        f"fan bends down to a radius of {info['fan_min_radius']} um"
    )
    name = "clements_mesh" if args.n == N else f"clements_mesh_{args.n}x{args.n}"
    x0 = info["blocks"][0]["x0"]
    return write_device(mesh, name, zoom=(x0 - 10, -info["pitch"] * 1.6, x0 + info["block_length"] + 10, info["pitch"] * 0.6))


if __name__ == "__main__":
    sys.exit(main())

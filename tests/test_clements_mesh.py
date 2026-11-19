"""The Clements mesh: the brick pattern of the paper, unbroken waveguides, one pair of pads per heater, and the DRC."""

from __future__ import annotations

import itertools

import gdsfactory as gf
import klayout.db as kdb
import pytest
from test_connectivity import number, pad_nets
from test_passive_devices import layers_used

import gsip_technology as t
from devices import GDS
from devices import clements_mesh_builder as cm
from devices import directional_coupler_builder as dcb
from devices import thermo_optic_phase_shifter_builder as tops
from gsip_drc import run_drc


@pytest.fixture(scope="module")
def mesh() -> gf.Component:
    return cm.clements_mesh()


def centre(port) -> tuple[float, float]:
    return float(port.center[0]), float(port.center[1])


# ---- the layout as a whole ----
def test_the_mesh_passes_the_drc_without_a_warning(mesh):
    result = run_drc(mesh)
    assert result.passed and not result.warnings, result.summary()


@pytest.mark.parametrize("kwargs", [{"n": 2}, {"n": 3}, {"n": 6}, {"pitch": 40.0}])
def test_other_sizes_pass_the_drc(kwargs: dict):
    result = run_drc(cm.clements_mesh(**kwargs))
    assert result.passed and not result.warnings, (kwargs, result.summary())


def test_the_mesh_uses_the_layers_of_its_two_devices(mesh):
    assert layers_used(mesh) == {"WG", "DEEPTRENCH", "HEATER", "VIA1", "M2", "VIA2", "M3", "PADOPEN"}


# ---- the arrangement of the paper ----
@pytest.mark.parametrize("n", [2, 3, 4, 5, 8])
def test_the_blocks_form_n_columns_like_bricks(n: int):
    found = cm.blocks(n)
    assert len(found) == n * (n - 1) // 2
    for column in range(n):
        uppers = [p for c, p in found if c == column]
        assert uppers == list(range(column % 2, n - 1, 2))  # each pairs (p, p + 1); the next column is shifted by one


def test_every_block_has_phi_and_theta_and_every_output_its_own_heater(mesh):
    heaters = mesh.info["heaters"]
    assert len(heaters) == 2 * len(cm.blocks(4)) + 4 == 16
    for k, (_, p) in enumerate(cm.blocks(4)):
        mine = {h["kind"]: h for h in heaters if h["block"] == k}
        assert set(mine) == {"phi", "theta"}
        assert mine["phi"]["row"] == mine["theta"]["row"] == p  # both on the upper waveguide of the block
        assert mine["phi"]["x"] < mine["theta"]["x"]  # phi on the input, theta on the arm
        block = next(b for b in mesh.info["blocks"] if b["block"] == k)
        assert block["x0"] < mine["phi"]["x"] < mine["theta"]["x"] < block["x0"] + mesh.info["block_length"]
    outputs = sorted(h["row"] for h in heaters if h["kind"] == "out")
    assert outputs == [0, 1, 2, 3]
    last = max(b["x0"] for b in mesh.info["blocks"]) + mesh.info["block_length"]
    assert all(h["x"] > last for h in heaters if h["kind"] == "out")


def test_the_waveguides_are_n_unbroken_paths_from_the_west_to_the_east(mesh):
    """In a coupler the two waveguides do not touch, so the core layer falls into exactly n pieces, one for each
    input, and each reaches the east side."""
    core = mesh.get_region(t.WG, merge=True)
    pieces = list(core.each_merged())
    assert len(pieces) == 4
    dbu = mesh.kcl.dbu
    west, east = 0.0, mesh.info["length"]
    for piece in pieces:
        box = piece.bbox()
        assert box.left * dbu == pytest.approx(west, abs=2e-3)
        assert box.right * dbu == pytest.approx(east, abs=2e-3)


def test_the_couplers_are_those_of_their_chapter(mesh):
    """The coupler is placed unchanged: 0.2 um gap over 15 um, ports 4 um apart; the fans open them to the rows."""
    assert dcb.GAP == 0.2 and dcb.LENGTH == 15.0 and dcb.PORT_SPACING == 4.0
    assert mesh.info["fan_offset"] == pytest.approx((cm.PITCH - dcb.PORT_SPACING) / 2)
    assert mesh.info["fan_min_radius"] >= t.DESIGN_RULES["strip_bend_radius"]
    # at the middle of each coupler the two cores are 0.2 um apart
    dbu = mesh.kcl.dbu
    core = mesh.get_region(t.WG, merge=True)
    for b in mesh.info["blocks"]:
        p = b["upper"]
        centre_y = -(p + 0.5) * cm.PITCH
        for x in (b["x0"] + cm.SECTION + cm.FAN_LENGTH + mesh.info["coupler_length"] / 2,
                  b["x0"] + 2 * cm.SECTION + 3 * cm.FAN_LENGTH + 1.5 * mesh.info["coupler_length"]):  # fmt: skip
            line = kdb.Region(
                kdb.Box(round(x / dbu), round((centre_y - 3) / dbu), round(x / dbu) + 1, round((centre_y + 3) / dbu))
            )
            cuts = sorted((s.bbox().bottom * dbu, s.bbox().top * dbu) for s in (core & line).each())
            assert len(cuts) == 2
            assert cuts[1][0] - cuts[0][1] == pytest.approx(dcb.GAP, abs=2e-3)


def test_the_arms_of_a_block_have_the_same_length(mesh):
    """A Mach-Zehnder is balanced: both arms run straight between the same two fans."""
    assert mesh.info["section"] == pytest.approx(tops.LENGTH + 2 * (tops.LANDING_LENGTH + tops.WG_EXTRA))


def test_the_edge_rows_without_a_block_run_through_a_dummy_path(mesh):
    """In columns 1 and 3, rows 0 and 3 have no block: each gets the fans and one arm of a coupler, towards the inside."""
    dummies = {(d["column"], d["row"]) for d in mesh.info["dummies"]}
    assert dummies == {(1, 0), (1, 3), (3, 0), (3, 3)}
    assert all(d["upper"] == (d["row"] == 0) for d in mesh.info["dummies"])
    assert mesh.info["arm_length"] > dcb.LENGTH + 2 * dcb.BEND_LENGTH  # the arm dips towards the gap: its path is longer
    draft = cm.clements_mesh(match_delay=False)
    assert draft.info["dummies"] == []
    result = run_drc(draft)
    assert result.passed and not result.warnings, result.summary()


# ---- ports and pads ----
def test_the_ports_are_n_inputs_n_outputs_and_two_pads_per_heater(mesh):
    names = {p.name for p in mesh.ports}
    optical = {f"o{i}" for i in range(1, 9)}
    electrical = {
        f"{h}_{s}" for h in [f"P{k}" for k in range(6)] + [f"T{k}" for k in range(6)] + [f"D{m}" for m in range(4)] for s in "we"
    }
    assert names == optical | electrical
    for m in range(4):
        assert centre(mesh.ports[f"o{m + 1}"]) == pytest.approx((0.0, -m * cm.PITCH), abs=2e-3)
        assert centre(mesh.ports[f"o{m + 5}"]) == pytest.approx((mesh.info["length"], -m * cm.PITCH), abs=2e-3)


def test_the_pads_do_not_overlap_and_lie_in_two_rows(mesh):
    pads = [p for p in mesh.ports if p.port_type == "electrical"]
    north = sorted(float(p.center[0]) for p in pads if p.center[1] > 0)
    south = sorted(float(p.center[0]) for p in pads if p.center[1] < 0)
    assert len(north) + len(south) == 32
    for row in (north, south):
        assert all(b - a >= cm.PAD_SPACE - 1e-6 for a, b in itertools.pairwise(row))
    assert {round(float(p.center[1]), 3) for p in pads} == {cm.PAD_OFFSET, round(-3 * cm.PITCH - cm.PAD_OFFSET, 3)}


def test_each_heater_joins_its_own_two_pads_and_no_other(mesh):
    nets = pad_nets(mesh)
    seen = set()
    for heater in mesh.info["heaters"]:
        w, e = number(nets[f"{heater['name']}_w"]), number(nets[f"{heater['name']}_e"])
        assert w == e, heater["name"]
        assert w not in seen, heater["name"]  # no two heaters share a net
        seen.add(w)


def test_no_trench_lies_near_a_metal_another_heater_or_another_waveguide(mesh):
    """The DRC checks the rules; here the trenches of every heater stay clear of the neighbouring rows."""
    dbu = mesh.kcl.dbu
    trench = mesh.get_region(t.LAYER.DEEPTRENCH, merge=True)
    reach = tops.TRENCH_GAP + tops.TRENCH_WIDTH
    assert cm.PITCH - reach >= t.DESIGN_RULES["trench_to_waveguide"] + dcb.WIDTH / 2
    assert len(list(trench.each())) == 2 * 16
    metal = mesh.get_region(t.M2, merge=True)
    grown = trench.sized(round(t.DESIGN_RULES["trench_to_metal"] / dbu) - 1)
    assert (grown & metal).is_empty()


# ---- refusals ----
@pytest.mark.parametrize(
    ("kwargs", "text"),
    [({"n": 1}, "at least two waveguides"), ({"pitch": 9.0}, "trench_to_waveguide"), ({"pitch": 300.0}, "strip bend radius")],
)
def test_arguments_that_break_a_rule_are_refused(kwargs: dict, text: str):
    with pytest.raises(ValueError, match=text):
        cm.clements_mesh(**kwargs)


# ---- the kept layout ----
def test_the_kept_layout_is_the_one_the_builder_draws(mesh):
    path = GDS / "clements_mesh.gds"
    assert path.exists(), "run devices/clements_mesh_builder.py"
    kept = kdb.Layout()
    kept.read(str(path))
    assert kept.top_cell().name == "clements_mesh"
    for name in t.LAYER_INFO:
        layer, datatype = tuple(getattr(t.LAYER, name))
        index = kept.find_layer(layer, datatype)
        on_disk = kdb.Region() if index is None else kdb.Region(kept.top_cell().begin_shapes_rec(index))
        drawn = mesh.get_region(getattr(t.LAYER, name), merge=True)
        assert (on_disk ^ drawn).sized(-1).is_empty(), f"{name} differs: run devices/clements_mesh_builder.py"


def test_no_polygon_of_the_kept_layout_is_larger_than_a_gds_record():
    kept = kdb.Layout()
    kept.read(str(GDS / "clements_mesh.gds"))
    for index in kept.layer_indexes():
        for shape in kept.top_cell().shapes(index).each():
            if shape.is_polygon():
                assert shape.polygon.num_points() <= t.MAX_POINTS

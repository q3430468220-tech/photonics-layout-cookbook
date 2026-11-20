"""The real matrix multiplier: its layout (devices/svd_multiplier_builder.py), its circuit and the programming of a real
matrix (lumerical_simulations/svd_multiplier/scripts/svd_model.py), and the results that the chapter keeps."""

from __future__ import annotations

import itertools
import math
import sys

import gdsfactory as gf
import klayout.db as kdb
import numpy as np
import pytest
from test_connectivity import number, pad_nets

import gsip_technology as t
from devices import GDS, REPO
from devices import clements_mesh_builder as cm
from devices import svd_multiplier_builder as sb
from gsip_drc import run_drc

CHAPTER = REPO / "lumerical_simulations" / "svd_multiplier"
sys.path.insert(0, str(CHAPTER / "scripts"))

import svd_model as sm  # noqa: E402
from svd_common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, inputs  # noqa: E402

mm = sm.mm


@pytest.fixture(scope="module")
def device() -> gf.Component:
    return sb.svd_multiplier()


@pytest.fixture(scope="module")
def setup():
    d = inputs()
    return d, mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA), sm.circuit(LAYOUT, d["heater_length"])


# ---- the layout ----
def test_the_multiplier_passes_the_drc_without_a_warning(device):
    result = run_drc(device)
    assert result.passed and not result.warnings, result.summary()


def test_it_is_two_meshes_with_a_column_of_attenuators_between(device):
    info = device.info
    mesh = cm.clements_mesh().info
    assert info["x"]["v"] == 0 and info["x"]["a"] == pytest.approx(mesh["length"])
    assert info["x"]["u"] == pytest.approx(mesh["length"] + info["a"]["length"])
    assert info["length"] == pytest.approx(2 * mesh["length"] + info["a"]["length"])
    assert info["heaters"] == 2 * 16 + 4
    assert info["a"]["attenuator_length"] == pytest.approx(4 * cm.FAN_LENGTH + 2 * info["a"]["coupler_length"] + cm.SECTION)


def test_every_dump_lies_half_a_pitch_above_its_row_and_carries_the_heater(device):
    att = device.info["a"]
    for unit, heater in zip(att["units"], att["heaters"], strict=True):
        assert unit["dump_y"] == pytest.approx(-unit["row"] * cm.PITCH + cm.PITCH / 2)
        assert heater["name"] == f"A{unit['row']}" and heater["kind"] == "attenuator"
        assert heater["y"] == pytest.approx(unit["dump_y"])


def test_the_light_runs_on_n_paths_from_west_to_east_and_the_dumps_end_open(device):
    """The core falls into the four rows, each from the west end to the east end, and the four dumps, each within the
    column of attenuators."""
    core = device.get_region(t.WG, merge=True)
    pieces = list(core.each_merged())
    assert len(pieces) == 2 * 4
    dbu = device.kcl.dbu
    full = [p for p in pieces if p.bbox().left * dbu == pytest.approx(0, abs=2e-3)]
    assert len(full) == 4
    assert all(p.bbox().right * dbu == pytest.approx(device.info["length"], abs=2e-3) for p in full)
    xa, la = device.info["x"]["a"], device.info["a"]["length"]
    for p in pieces:
        if p not in full:
            assert xa <= p.bbox().left * dbu and p.bbox().right * dbu <= xa + la


def test_the_ports_are_the_inputs_of_mesh_v_the_outputs_of_mesh_u_and_two_pads_per_heater(device):
    names = {p.name for p in device.ports}
    assert {f"o{i}" for i in range(1, 9)} <= names
    heaters = [f"V_{h['name']}" for h in LAYOUT["v"]["heaters"]] + [f"A{m}" for m in range(4)]
    heaters += [f"U_{h['name']}" for h in LAYOUT["u"]["heaters"]]
    assert {f"{h}_{s}" for h in heaters for s in "we"} == {p.name for p in device.ports if p.port_type == "electrical"}


def test_the_pads_do_not_overlap_and_each_heater_joins_its_own_two(device):
    pads = [p for p in device.ports if p.port_type == "electrical"]
    for side in (1, -1):
        xs = sorted(float(p.center[0]) for p in pads if np.sign(p.center[1]) == side)
        assert all(b - a >= cm.PAD_SPACE - 1e-6 for a, b in itertools.pairwise(xs))
    nets = pad_nets(device)
    seen = set()
    for p in pads:
        if p.name.endswith("_w"):
            w, e = number(nets[p.name]), number(nets[p.name[:-2] + "_e"])
            assert w == e and w not in seen, p.name
            seen.add(w)
    assert len(seen) == 36


def test_the_kept_layout_is_the_one_the_builder_draws(device):
    path = GDS / "svd_multiplier.gds"
    assert path.exists(), "run devices/svd_multiplier_builder.py"
    kept = kdb.Layout()
    kept.read(str(path))
    assert kept.top_cell().name == "svd_multiplier"
    for name in t.LAYER_INFO:
        layer, datatype = tuple(getattr(t.LAYER, name))
        index = kept.find_layer(layer, datatype)
        on_disk = kdb.Region() if index is None else kdb.Region(kept.top_cell().begin_shapes_rec(index))
        drawn = device.get_region(getattr(t.LAYER, name), merge=True)
        assert (on_disk ^ drawn).sized(-1).is_empty(), f"{name} differs: run devices/svd_multiplier_builder.py"


# ---- the circuit ----
def test_the_circuit_has_every_coupler_heater_and_site(setup):
    _d, _ph, c = setup
    assert c.n == 8
    assert len(c.couplers) == 2 * 12 + 2 * 4
    assert len(c.heaters) == 36
    own = mm.own_sites(c)
    assert len(own) == 36
    for j, s in enumerate(own):
        assert c.sites[s]["x"] == pytest.approx(c.heaters[j]["x"])
    for m in range(4):  # the attenuator of row m pairs it with its dump, row 4 + m
        pairs = [(cp["upper"], cp["lower"]) for cp in c.couplers if cp["lower"] == m and cp["upper"] == 4 + m]
        assert len(pairs) == 2


def test_every_row_of_the_light_is_as_long_as_every_other(setup):
    _d, _ph, c = setup
    arm = LAYOUT["v"]["arm_length"]
    total = [sum(p[2] for p in c.rows[m] if p[0] == "wg") + arm * sum(p[0] == "dc" for p in c.rows[m]) for m in range(4)]
    assert max(total) - min(total) < 1e-6


def test_the_ideal_attenuator_passes_sin_theta_over_2_with_a_phase_of_theta_over_2():
    for theta in np.linspace(0.1, 2 * np.pi - 0.1, 9):
        kept = sm.attenuator(theta)[1, 1]
        assert kept == pytest.approx(-1j * np.exp(1j * theta / 2) * np.sin(theta / 2), abs=1e-12)


def test_the_recipe_is_exact_on_the_ideal_multiplier(setup):
    _d, ph, c = setup
    rng = np.random.default_rng(3)
    for _ in range(5):
        m = rng.standard_normal((4, 4))
        r = sm.recipe(c, ph, m)
        phases = {h["name"]: p / ph.P_pi * np.pi for h, p in zip(c.heaters, r["powers"], strict=True)}
        got = sm.ideal_multiplier(4, phases)
        a = sm.best_factor(got, m / r["scale"])
        assert np.max(np.abs(got - a * m / r["scale"])) < 1e-12
        assert abs(a) == pytest.approx(1, abs=1e-12)


def test_the_fit_programs_a_random_matrix_on_the_drawn_circuit(setup):
    _d, ph, c = setup
    m = np.random.default_rng(5).standard_normal((4, 4))
    r = sm.program(c, ph, m, ph.lam0)
    assert r["error"] < 1e-9
    assert r["error_recipe"] > 0.1  # the recipe knows nothing of the phases of the waveguides
    assert np.all((r["powers"] >= 0) & (r["powers"] < 2 * ph.P_pi))


def test_the_leak_of_the_attenuator_is_that_of_the_coupler(setup):
    _d, ph, _c = setup
    c1 = sm.attenuator_circuit(LAYOUT, inputs()["heater_length"])
    t0 = sm.transfer(c1, ph, ph.lam0, mm.site_dn(c1, ph, [0.0]))[0]
    keep, dump = abs(t0[1, 1]) ** 2, abs(t0[0, 1]) ** 2
    s = ph.coupler(ph.lam0, (3, 4))
    k2, t2 = abs(s[3][0]) ** 2, abs(s[4][0]) ** 2
    assert keep / (keep + dump) == pytest.approx(((t2 - k2) / (t2 + k2)) ** 2, rel=2e-2)  # the rest: the loss of the coupler


# ---- the kept results ----
def test_the_kept_results_are_those_of_the_circuit_as_drawn(setup):
    _d, ph, c = setup
    att = np.load(CHAPTER / "1_attenuator" / "attenuator.npz")
    assert float(att["P_pi_mW"]) == pytest.approx(ph.P_pi)
    assert float(att["model_difference"]) < 1e-3
    program = np.load(CHAPTER / "2_program" / "program.npz")
    assert list(program["heater_names"]) == [h["name"] for h in c.heaters]
    for k in range(len(program["targets"])):
        target = program["targets"][k] / float(program["scale"][k])
        t_now = sm.matrix(c, ph, ph.lam0, program["powers_mW"][k])[0]
        assert sm.relative_error(t_now, target) == pytest.approx(float(program["error"][k]), abs=1e-9)
    assert float(program["model_difference"]) < 2e-3
    assert np.all(program["error"][:-1] < 1e-9)  # every random matrix
    assert float(program["sigma"][-1][-1]) < float(att["smallest"]) < float(program["error"][-1]) * 3  # the floor


def test_the_kept_classifier_uses_the_powers_it_programmed(setup):
    _d, ph, c = setup
    cl = np.load(CHAPTER / "3_classifier" / "classifier.npz")
    w = cl["W"]
    target = w / np.linalg.svd(w, compute_uv=False)[0]
    assert sm.relative_error(sm.matrix(c, ph, ph.lam0, cl["powers_mW"])[0], target) < 1e-2
    i0 = len(cl["lam"]) // 2
    assert float(cl["accuracy_coherent"][i0]) >= float(cl["electronic"][0]) - 0.01
    assert float(cl["accuracy_sign_lost"][i0]) < float(cl["accuracy_coherent"][i0]) - 0.1
    assert math.isclose(float(cl["P_pi_mW"]), ph.P_pi)


# ---- step 4: the convolution layer ----
def test_the_kept_digits_are_the_two_sets_of_the_repository():
    import digits

    x_train, _, x_test, y_test = digits.load()
    assert x_train.shape == (3823, 8, 8) and x_test.shape == (1797, 8, 8)
    assert x_train.max() == 16 and x_test.min() == 0
    assert np.bincount(y_test).tolist() == [178, 182, 177, 183, 181, 182, 181, 179, 174, 180]  # optdigits.names
    assert "CC BY 4.0" in digits.CITATION and "10.24432/C50P49" in digits.CITATION


def test_a_window_feeds_the_inputs_in_the_order_of_step_3():
    import conv_digits as cd

    x = np.arange(64, dtype=float).reshape(1, 8, 8)
    p = cd.patches(x)
    assert p.shape == (1, 49, 4)
    assert p[0, 0].tolist() == [0, 1, 8, 9]  # top left, top right, bottom left, bottom right
    assert p[0, 8].tolist() == [9, 10, 17, 18]  # the window moves by one pixel, row by row
    assert np.allclose(cd.HAAR @ cd.HAAR.T, np.eye(4))  # the Haar kernels are orthogonal


def test_the_kept_convolution_reads_every_digit_as_its_electronic_network(setup):
    import conv_digits as cd
    import digits

    _d, ph, c = setup
    d = np.load(CHAPTER / "4_convolution" / "convolution.npz")
    _, _, x_test, y_test = digits.load()
    x_test = x_test / 16.0
    i0 = len(d["lam"]) // 2
    for j, name in enumerate(d["names"]):
        mode = str(d["modes"][j])
        electronic = np.argmax(cd.scores(cd.activate(cd.patches(x_test) @ d["K"][j].T, mode), d["W"][j], d["b"][j]), 1)
        assert float(np.mean(electronic == y_test)) == pytest.approx(float(d["electronic"][j]))
        assert np.array_equal(electronic, d["read"][j]), name  # the optical layer at 1.55 um, digit by digit
        assert float(d["accuracy"][j][i0]) > 0.95
        target = d["K"][j] / float(d["scale"][j])
        assert sm.relative_error(sm.matrix(c, ph, ph.lam0, d["powers_mW"][j])[0], target) < 1e-3, name
    assert float(d["sign_lost"][i0]) < float(d["accuracy"][1][i0]) - 0.3
    assert np.allclose(d["sigma"][0], 1.0)

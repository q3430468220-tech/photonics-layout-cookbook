"""The model of the Clements mesh chapter: the decomposition of the paper, the circuit read from the layout, the heat
kernel against the phase shifter chapter, and the kept results against the layout that the builder draws now."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from devices import REPO
from devices import clements_mesh_builder as cm

CHAPTER = REPO / "lumerical_simulations" / "clements_mesh"
sys.path.insert(0, str(CHAPTER / "scripts"))

import mesh_model as mm  # noqa: E402
from common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, inputs  # noqa: E402


@pytest.fixture(scope="module")
def setup():
    d = inputs()
    return d, mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA), mm.circuit(LAYOUT, d["heater_length"])


# ---- the decomposition ----
@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 8])
def test_the_decomposition_rebuilds_random_unitaries(n: int):
    rng = np.random.default_rng(n)
    for _ in range(3):
        u = mm.haar(n, rng)
        theta, phi, delta = mm.clements(u)
        assert np.max(np.abs(mm.ideal_mesh(n, theta, phi, delta) - u)) < 1e-12


@pytest.mark.parametrize("u", [mm.dft(4), np.eye(4), np.eye(4)[[1, 0, 3, 2]], np.eye(4)[::-1]])
def test_the_decomposition_handles_blocks_that_cross_fully_or_not_at_all(u):
    theta, phi, delta = mm.clements(np.asarray(u, dtype=complex))
    assert np.max(np.abs(mm.ideal_mesh(4, theta, phi, delta) - u)) < 1e-12


def test_the_block_order_is_that_of_the_layout():
    for n in range(2, 9):
        assert mm.blocks(n) == cm.blocks(n)


def test_the_ideal_block_is_a_mach_zehnder():
    assert np.allclose(mm.block(0.0, 0.0), 1j * np.array([[0, 1], [1, 0]]))  # theta = 0: all light crosses
    assert np.allclose(np.abs(mm.block(np.pi, 0.3)), np.eye(2))  # theta = pi: none does
    assert np.allclose(mm.block(0.7, 1.1) @ mm.block(0.7, 1.1).conj().T, np.eye(2))


def test_the_block_multiplied_out_is_the_matrix_of_the_chapter():
    """The README writes T(theta, phi) = i e^(i theta/2) [[e^(i phi) sin, cos], [e^(i phi) cos, -sin]] of theta / 2."""
    for theta, phi in [(0.3, 1.9), (2.5, -0.7), (np.pi / 2, np.pi)]:
        s, c = np.sin(theta / 2), np.cos(theta / 2)
        written = 1j * np.exp(1j * theta / 2) * np.array([[np.exp(1j * phi) * s, c], [np.exp(1j * phi) * c, -s]])
        assert np.allclose(mm.block(theta, phi), written)


def test_the_nulls_of_the_chapter_zero_their_entry():
    """From the right, (a, b) T^-1 starts with 0; from the left, T (a, b) ends with 0: the formulas of the README."""
    rng = np.random.default_rng(3)
    for _ in range(20):
        a, b = rng.standard_normal(2) + 1j * rng.standard_normal(2)
        theta, phi = 2 * np.arctan(abs(b) / abs(a)), np.pi + np.angle(a) - np.angle(b)
        assert abs((np.array([a, b]) @ np.linalg.inv(mm.block(theta, phi)))[0]) < 1e-12
        theta, phi = 2 * np.arctan(abs(a) / abs(b)), np.angle(b) - np.angle(a)
        assert abs((mm.block(theta, phi) @ np.array([a, b]))[1]) < 1e-12


# ---- the circuit read from the layout ----
def test_every_heater_has_its_site_and_every_row_its_pieces(setup):
    _d, _ph, c = setup
    own = mm.own_sites(c)
    assert len(own) == len(LAYOUT["heaters"]) == 16
    for j, s in enumerate(own):
        assert c.sites[s]["row"] == c.heaters[j]["row"] and c.sites[s]["x"] == c.heaters[j]["x"]
    assert sum(1 for op in c.ops if op[0] == "dc") == len(c.couplers) == 12
    for m in range(c.n):  # the pieces of a row follow one another along x
        xs = [p[1] for p in c.rows[m]]
        assert xs == sorted(xs)


def test_every_path_is_as_long_as_every_other(setup):
    """The rows of the drawn mesh carry the same waveguide, counting a coupler as one arm: the delays match."""
    d, _ph, c = setup
    total = []
    for m in range(c.n):
        wg = sum(p[2] for p in c.rows[m] if p[0] == "wg")
        couplers = sum(1 for p in c.rows[m] if p[0] == "dc")
        total.append(wg + couplers * LAYOUT["arm_length"])
    assert max(total) - min(total) < 1e-6
    draft = mm.circuit(cm.clements_mesh(match_delay=False).info, d["heater_length"])
    lengths = [
        sum(p[2] for p in draft.rows[m] if p[0] == "wg") + LAYOUT["arm_length"] * sum(p[0] == "dc" for p in draft.rows[m])
        for m in range(4)
    ]
    assert max(lengths) - min(lengths) > 20  # the first draft did not match them: 24 um between its rows


def test_with_all_heaters_off_the_mesh_sends_input_m_to_output_n_minus_m(setup):
    _d, ph, c = setup
    u = mm.transfer(c, ph, ph.lam0, np.zeros(len(c.sites)))[0]
    p = np.abs(u) ** 2
    assert np.allclose(p / p.sum(axis=0), np.eye(4)[::-1], atol=1e-4)


def test_the_coupler_of_the_model_is_that_of_the_fdtd_run(setup):
    d, ph, _c = setup
    s = ph.coupler(ph.lam0, (3, 4))
    assert abs(s[3][0]) ** 2 == pytest.approx(0.4986, abs=5e-4)  # the summary of the coupler chapter
    assert abs(s[4][0]) ** 2 == pytest.approx(0.5007, abs=5e-4)
    assert np.angle(s[3][0] / s[4][0]) == pytest.approx(np.pi / 2, abs=1e-3)  # cross leads through by a quarter turn
    assert ph.P_pi == pytest.approx(d["P_pi"], rel=1e-6)  # lambda / (2 L dn/dP) is the P_pi of the phase shifter chapter


def test_a_lossless_mesh_of_50_50_couplers_is_programmed_exactly(setup):
    d, _, c = setup
    lossless = mm.Physics(d, 0.0, COUPLER_PORT_EXTRA)
    s = lossless.coupler(lossless.lam0, (3, 4))
    half = {k: (np.exp(1j * np.angle(s[4][0])) * np.array([[1, 1j], [1j, 1]]) / np.sqrt(2))[None] for k in range(len(c.couplers))}
    assert 1 - mm.program(c, lossless, mm.dft(4), lossless.lam0, couplers=half, restarts=0)["fidelity"] < 1e-12
    # the split of the FDTD coupler, without its loss: a small rest that the phases cannot take up
    norm = np.sqrt(abs(s[3][0]) ** 2 + abs(s[4][0]) ** 2)
    clean = {k: (np.array([[s[4][0], s[3][0]], [s[3][0], s[4][0]]]) / norm)[None] for k in range(len(c.couplers))}
    assert 1e-9 < 1 - mm.program(c, lossless, mm.dft(4), lossless.lam0, couplers=clean, restarts=0)["fidelity"] < 2e-7


# ---- the heat ----
def test_the_heat_kernel_reproduces_the_phase_shifter_chapter(setup):
    d, _, _ = setup
    L = d["heater_length"]
    for dist, expected in zip(d["neighbour_d"], d["neighbour_K"], strict=False):
        got = mm.mean_rise((-L / 2, L / 2, 0.0), (-L / 2, L / 2, dist), d["k_silicon"], d["wafer_um"])
        assert got == pytest.approx(expected, rel=1e-6)


def test_the_crosstalk_matrix_is_one_on_the_own_site_and_small_elsewhere(setup):
    d, _, c = setup
    _rise, share = mm.crosstalk_matrix(c, d["heater_length"], d["k_silicon"], d["wafer_um"], d["core_K_per_mW"])
    own = mm.own_sites(c)
    assert np.allclose(share[own, np.arange(16)], 1.0)
    other = share.copy()
    other[own, np.arange(16)] = 0
    assert 0 < other.max() < 0.01


# ---- the kept results belong to the layout as drawn ----
def test_the_kept_results_are_those_of_the_layout_the_builder_draws(setup):
    _d, ph, c = setup
    mzi = np.load(CHAPTER / "1_mzi" / "mzi.npz")
    assert float(mzi["P_pi_mW"]) == pytest.approx(ph.P_pi)
    program = np.load(CHAPTER / "2_program" / "program.npz")
    assert list(program["heater_names"]) == [h["name"] for h in LAYOUT["heaters"]]
    assert np.allclose(program["heater_x"], [h["x"] for h in LAYOUT["heaters"]])
    assert float(program["arm_length_um"]) == pytest.approx(LAYOUT["arm_length"])
    # the fidelity that step 2 kept is what the model gives now for the kept powers
    f = mm.fidelity(mm.transfer(c, ph, ph.lam0, mm.site_dn(c, ph, program["powers_mW"][0]))[0], program["targets"][0])
    assert f == pytest.approx(float(program["fidelity_lam0"][0]), abs=1e-9)
    crosstalk = np.load(CHAPTER / "3_crosstalk" / "crosstalk.npz")
    assert np.allclose(crosstalk["powers_nominal"], program["powers_mW"])
    assert np.allclose(crosstalk["site_x"], [s["x"] for s in c.sites])


def test_the_dft_heater_by_heater_in_the_chapter_is_the_kept_result(setup):
    """The table "The DFT, heater by heater" of the README: the phases of the recipe, their powers, the fitted powers that
    step 2 kept, and V = sqrt(P R); and the fidelity of the recipe alone that the text gives."""
    d, ph, c = setup
    program = np.load(CHAPTER / "2_program" / "program.npz")
    text = (CHAPTER / "README.md").read_text(encoding="utf-8")
    section = text.split("**The DFT, heater by heater.**", 1)[1].split("## The steps", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0][:1] in "PTD" and cells[0][1:].isdigit():
            rows[cells[0]] = [float(x) for x in cells[2:]]
    names = [h["name"] for h in c.heaters]
    assert list(rows) == names
    order = mm.heater_order(c)
    phase = np.zeros(16)
    phase[order["theta"]] = program["theta_dft"]
    phase[order["phi"]] = program["phi_dft"]
    phase[order["out"]] = program["delta_dft"]
    recipe = ph.phase_to_power(phase)
    fitted = program["powers_mW"][0]
    for j, name in enumerate(names):
        over_pi, recipe_mw, fitted_mw, volts = rows[name]
        assert over_pi == pytest.approx(phase[j] / np.pi, abs=5e-4), name
        assert recipe_mw == pytest.approx(recipe[j], abs=5e-3), name
        assert fitted_mw == pytest.approx(fitted[j], abs=5e-3), name
        assert volts == pytest.approx(np.sqrt(fitted[j] * 1e-3 * d["resistance"]), abs=5e-3), name
    f_recipe = mm.fidelity(mm.transfer(c, ph, ph.lam0, mm.site_dn(c, ph, recipe))[0], program["targets"][0])
    assert f"F = {f_recipe:.2f} only" in section
    assert d["resistance"] == 500.0 and "R = 500 Ω" in text

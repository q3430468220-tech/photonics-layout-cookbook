"""The process tables (CSV) against the technology file, and the scripts that cannot run without Lumerical."""

from __future__ import annotations

import csv
import math
import py_compile
import re
from pathlib import Path

import pytest

import cornerstone_technology as t

REPO = Path(__file__).resolve().parents[1]
CSV_DIR = REPO / "cornerstone_process_file_py" / "cornerstone_csv"
KNOWN_GDS = {tuple(getattr(t.LAYER, key)) for key in t.OFFICIAL_LAYER_NAMES}


def rows(name: str) -> list[dict[str, str]]:
    with open(CSV_DIR / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def layers_in(expression: str) -> set[tuple[int, int]]:
    return {(int(a), int(b)) for a, b in re.findall(r"(\d+):(\d+)", expression)}


PROCESS = {r["name"]: r for r in rows("process_layers.csv")}


def test_stack_heights_equal_the_technology_file():
    def span(name):  # (bottom, top) in um
        start, thickness = float(PROCESS[name]["start_position"]) / 1000, float(PROCESS[name]["thickness"]) / 1000
        return tuple(sorted((start, start + thickness)))

    assert span("BOX") == pytest.approx((-t.T_BOX, 0.0))
    assert span("Si_Substrate") == pytest.approx((-t.T_BOX - t.T_SUBSTRATE_SIM, -t.T_BOX))
    assert span("Si_core") == pytest.approx((0.0, t.T_SI))
    assert span("Si_slab") == pytest.approx((0.0, t.T_SLAB))
    assert span("Si_slab_contact") == pytest.approx((0.0, t.T_SLAB))
    assert span("Si_grating") == pytest.approx((0.0, t.T_SI - t.ETCH_GRATING))
    assert span("TOX") == pytest.approx((0.0, t.Z_METAL))
    assert span("Via_P") == span("Via_N") == pytest.approx((t.T_SLAB, t.Z_METAL))
    assert span("Electrode") == pytest.approx((t.Z_METAL, t.Z_METAL + t.T_METAL))
    assert span("Detector_window") == pytest.approx((t.T_SI + t.T_DETECTOR_OXIDE, t.Z_METAL))


def test_layer_expressions_use_only_known_gds_layers():
    for r in list(PROCESS.values()):
        assert layers_in(r["layer_number"]) <= KNOWN_GDS, r["name"]
    for r in rows("doping_process_layers.csv"):
        assert layers_in(r["mask layer number"]) <= KNOWN_GDS, r["name"]


def test_materials_exist_and_have_electrical_and_thermal_models():
    lumerical = {m["optical"] for m in t.MATERIALS.values()}
    custom = {r["name"] for r in rows("index_perturbation_data.csv")} | {r["name"] for r in rows("dielectric_materials.csv")}
    used = {r[col] for r in PROCESS.values() for col in ("pattern_material", "background_material")} - {"None"}
    assert used <= lumerical | custom
    assert used <= {r["material"] for r in rows("active_material_models.csv")}
    for r in rows("index_perturbation_data.csv"):
        assert r["base material"] in lumerical


def test_doping_reproduces_the_published_concentrations():
    doping = {r["name"]: r for r in rows("doping_process_layers.csv")}
    assert float(doping["P_high"]["concentration"]) == pytest.approx(t.DOPING["ppp"])
    assert float(doping["N_high"]["concentration"]) == pytest.approx(t.DOPING["npp"])
    assert float(doping["Wafer"]["concentration"]) == pytest.approx(t.DOPING["substrate_p"])
    # donors = published net n + the background p they compensate
    donors = t.DOPING["n_net"] + t.DOPING["p_slab"]
    assert float(doping["N_low_slab"]["concentration"]) == pytest.approx(donors, rel=0.01)
    assert float(doping["N_low_sidewall"]["concentration"]) == pytest.approx(donors, rel=0.01)

    # the Gaussian of the background p implant averages to the two published values
    p = doping["P_low"]
    peak, surface, rp, sigma = (float(p[k]) for k in ("concentration", "z surface position", "range", "straggle"))
    assert surface == pytest.approx(t.T_SI * 1e-6)

    def mean(depth0: float, depth1: float) -> float:  # depth below the silicon surface, um
        def cdf(x):
            return 0.5 * math.erf((x * 1e-6 - rp) / (math.sqrt(2) * sigma))

        return peak * sigma * math.sqrt(2 * math.pi) * (cdf(depth1) - cdf(depth0)) / ((depth1 - depth0) * 1e-6)

    assert mean(t.ETCH_RIB, t.T_SI) == pytest.approx(t.DOPING["p_slab"], rel=0.02)  # the slab layer
    assert mean(0.0, t.ETCH_RIB) == pytest.approx(t.DOPING["p_rib"], rel=0.02)  # the upper part of the rib


def test_variation_tables_have_one_flag_per_layer():
    n = len(PROCESS)
    for name, expected in (("pattern_variations.csv", n), ("stack_variations.csv", 2 * n)):
        with open(CSV_DIR / name, newline="") as f:
            for row in csv.reader(f):
                assert len(row) - 4 == expected, (name, row[0])
                assert set(row[4:]) <= {"0", "1"}


def test_scripts_compile():
    scripts = [
        *REPO.glob("lumerical_simulations/**/*.py"),
        *REPO.glob("cornerstone_process_file_py/*.py"),
        REPO / "lumerical_env.py",
    ]
    assert len(scripts) >= 14
    for script in scripts:
        py_compile.compile(str(script), doraise=True)

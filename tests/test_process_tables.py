"""The process tables (CSV) against the technology file, and the scripts that cannot run without Lumerical."""

from __future__ import annotations

import csv
import py_compile
import re
from pathlib import Path

import pytest

import gsip_technology as t

REPO = Path(__file__).resolve().parents[1]
CSV_DIR = REPO / "gsip_process_file_py" / "gsip_csv"
FABRICATED = {tuple(getattr(t.LAYER, name)) for name in t.LAYER_INFO if name not in ("FLOORPLAN", "TEXT", "DEVREC")}

# process layer of the CSV -> level of the technology file's STACK
STACK_OF = {
    "Si_Substrate": "substrate",
    "BOX": "box",
    "TOX": "cladding",
    "Si_slab150": "slab150",
    "Si_slab90": "slab90",
    "Si_core": "core",
    "Ge": "germanium",
    "SiN": "nitride",
    "Via_contact_P": "via_contact",
    "Via_contact_N": "via_contact",
    "Metal1": "metal1",
    "Heater": "heater",
    "Via1_on_metal1": "via1",
    "Metal2": "metal2",
    "Via2": "via2",
    "Metal3": "metal3",
}


def rows(name: str) -> list[dict[str, str]]:
    with open(CSV_DIR / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def layers_in(expression: str) -> set[tuple[int, int]]:
    return {(int(a), int(b)) for a, b in re.findall(r"(\d+):(\d+)", expression)}


PROCESS = {r["name"]: r for r in rows("process_layers.csv")}
STACK = {name: (z0, z1) for name, _, z0, z1, _ in t.STACK}

# every process row with a level of the STACK table; the heater's via 1 is a second row of the same level
ROW_LEVEL = {**STACK_OF, "Via1_on_heater": "via1"}
# rows that the STACK table does not list: process row -> PDK layer
OUTSIDE_STACK = {"Pad_opening": "PADOPEN", "Deep_trench": "DEEPTRENCH", "Undercut": "UNDERCUT"}
# a via lands on a conductor or an implant: the layer under it is listed with the level's own layer
UNDERLYING = {"Via_contact_P": "PPP", "Via_contact_N": "NPP", "Via1_on_metal1": "M1", "Via1_on_heater": "HEATER"}
STACK_ROW = {name: (layer, material) for name, layer, _, _, material in t.STACK}


def material_key(name: str) -> str:
    """MATERIALS key of a material as the process table names it.  Si_np is silicon with the index change of the
    carriers and the heat; Air is not in MATERIALS."""
    if name == "Si_np":
        return "si"
    if name == "Air":
        return "air"
    (key,) = [k for k, names in t.MATERIALS.items() if names["optical"] == name]
    return key


def span(name: str) -> tuple[float, float]:
    """(bottom, top) of a process layer in um."""
    start, thickness = float(PROCESS[name]["start_position"]) / 1000, float(PROCESS[name]["thickness"]) / 1000
    low, high = sorted((start, start + thickness))
    return low, high


@pytest.mark.parametrize("layer", sorted(STACK_OF))
def test_stack_heights_equal_the_technology_file(layer):
    assert span(layer) == pytest.approx(STACK[STACK_OF[layer]])


def test_every_row_is_in_the_stack_or_listed_outside_it():
    assert set(ROW_LEVEL) | set(OUTSIDE_STACK) == set(PROCESS)
    assert not set(ROW_LEVEL) & set(OUTSIDE_STACK)


@pytest.mark.parametrize("name", sorted(PROCESS))
def test_each_row_has_its_pdk_layer_and_material(name):
    """The layer number of a row is the PDK layer of its STACK level (plus the layer under a via), and its
    material is the STACK material of that level."""
    if name in OUTSIDE_STACK:
        layer, key = OUTSIDE_STACK[name], "air"
    else:
        layer, key = STACK_ROW[ROW_LEVEL[name]]
    expected = {tuple(getattr(t.LAYER, layer))} if layer else set()
    if name in UNDERLYING:
        expected.add(tuple(getattr(t.LAYER, UNDERLYING[name])))
    row = PROCESS[name]
    assert layers_in(row["layer_number"]) == expected, name
    material = row["pattern_material"] if row["pattern_material"] != "None" else row["background_material"]
    assert material_key(material) == key, name


def test_sidewall_angle_is_the_technology_value():
    for name, row in PROCESS.items():
        assert float(row["sidewall_angle"]) == pytest.approx(t.SIDEWALL_ANGLE), name


def test_layers_the_stack_table_cannot_express():
    heater_top = STACK["heater"][1]
    assert span("Via1_on_heater") == pytest.approx((heater_top, STACK["metal2"][0]))  # via 1 starts on the film
    assert span("Pad_opening") == pytest.approx((STACK["metal3"][1], t.Z_TOP))  # the passivation above the pad
    assert span("Deep_trench")[1] == pytest.approx(t.Z_TOP)
    assert span("Undercut")[1] == pytest.approx(-t.T_BOX)  # below the buried oxide


def test_layer_expressions_use_fabricated_gds_layers_only():
    for r in PROCESS.values():
        assert layers_in(r["layer_number"]) <= FABRICATED, r["name"]
    for r in rows("doping_process_layers.csv"):
        assert layers_in(r["mask layer number"]) <= FABRICATED, r["name"]
    drawn = set().union(*(layers_in(r["layer_number"]) for r in PROCESS.values()))
    drawn |= set().union(*(layers_in(r["mask layer number"]) for r in rows("doping_process_layers.csv")))
    assert drawn == FABRICATED  # every fabricated layer of the PDK appears in the process file


def test_contact_vias_are_split_by_the_implant_below():
    assert layers_in(PROCESS["Via_contact_P"]["layer_number"]) == {tuple(t.VIAC), tuple(t.PPP)}
    assert layers_in(PROCESS["Via_contact_N"]["layer_number"]) == {tuple(t.VIAC), tuple(t.NPP)}
    assert layers_in(PROCESS["Via1_on_heater"]["layer_number"]) == {tuple(t.VIA1), tuple(t.HEATER)}


def test_materials_exist_and_have_electrical_and_thermal_models():
    lumerical = {m["optical"] for m in t.MATERIALS.values()}
    custom = {r["name"] for r in rows("index_perturbation_data.csv")} | {r["name"] for r in rows("dielectric_materials.csv")}
    used = {r[col] for r in PROCESS.values() for col in ("pattern_material", "background_material")} - {"None"}
    assert used <= lumerical | custom
    active = {r["material"]: r for r in rows("active_material_models.csv")}
    assert used <= set(active)
    for key, names in t.MATERIALS.items():
        assert active[names["optical"]]["CT material"] == names["charge"], key
        assert active[names["optical"]]["HT material"] == names["heat"], key
    for r in rows("index_perturbation_data.csv"):
        assert r["base material"] in lumerical


def test_heater_film_properties():
    overrides = {(r["model"], r["property"]): float(r["value"]) for r in rows("material_property_overrides.csv")}
    assert {r["material"] for r in rows("material_property_overrides.csv")} == {t.MATERIALS["tin"]["optical"]}
    assert overrides[("CT", "conductivity.constant")] == pytest.approx(1 / t.TIN_RESISTIVITY, rel=1e-4)
    assert ("HT", "thermal conductivity.constant") in overrides
    assert float(PROCESS["Heater"]["thickness"]) / 1000 == pytest.approx(t.T_HEATER)


def test_doping_tables_follow_the_technology_file():
    doping = {r["name"]: r for r in rows("doping_process_layers.csv")}
    for name, layer in (("N", "N"), ("P", "P"), ("N_plus", "NP"), ("P_plus", "PP"), ("N_plusplus", "NPP"), ("P_plusplus", "PPP"),
                        ("Ge_N", "GEN"), ("Ge_P", "GEP")):  # fmt: skip
        r = doping[name]
        assert float(r["concentration"]) == pytest.approx(t.DOPING[layer]), name
        assert layers_in(r["mask layer number"]) == {tuple(getattr(t.LAYER, layer))}, name
        assert r["dopant"] == ("n" if "N" in name.split("_")[0] or name.endswith("_N") else "p"), name
    assert float(doping["Wafer"]["concentration"]) == pytest.approx(t.DOPING["background_p"])
    # the silicon implants are flat over the 220 nm of silicon: the straggle is much larger than the layer
    for name in ("N", "P", "N_plus", "P_plus", "N_plusplus", "P_plusplus"):
        assert float(doping[name]["z surface position"]) == pytest.approx(t.T_SI * 1e-6)
        assert float(doping[name]["straggle"]) >= 4 * t.T_SI * 1e-6


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
        *REPO.glob("gsip_process_file_py/*.py"),
        *REPO.glob("assets/scripts/*.py"),
        REPO / "lumerical_env.py",
        REPO / "figstyle.py",
    ]
    assert len(scripts) >= 12
    for script in scripts:
        py_compile.compile(str(script), doraise=True)

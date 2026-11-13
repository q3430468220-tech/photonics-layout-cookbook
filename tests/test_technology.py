"""The technology file against its public sources: the textbook's layer table and the open gdsfactory generic PDK."""

from __future__ import annotations

from pathlib import Path

import gdsfactory as gf
import klayout.db as kdb
import numpy as np
import pytest

import gsip_technology as t

# GDS layer map of the Generic Silicon Photonics PDK: Chrostowski & Hochberg, "Silicon Photonics Design",
# Table 10.2 (p. 353).  book name -> (GDS number, the name used here)
BOOK_TABLE_10_2 = {
    "Si": (1, "WG"),
    "SiEtch1": (2, "SLAB150"),
    "SiEtch2": (3, "SLAB90"),
    "SiEtch3": (4, "DEEPTRENCH"),
    "Ge": (5, "GE"),
    "OxEtch": (6, "UNDERCUT"),
    "N": (20, "N"),
    "P": (21, "P"),
    "N+": (22, "NP"),
    "P+": (23, "PP"),
    "Npp": (24, "NPP"),
    "Ppp": (25, "PPP"),
    "GeN": (26, "GEN"),
    "GeP": (27, "GEP"),
    "VC": (40, "VIAC"),
    "M1": (41, "M1"),
    "VL": (44, "VIA1"),
    "ML": (45, "M2"),
    "MLOpen": (46, "PADOPEN"),
    "Text": (66, "TEXT"),
    "devrec": (68, "DEVREC"),
}
# Table 10.1 and the doping levels of Sec. 6.2 of the same book.
BOOK_PROCESS = {"T_SI": 0.22, "ETCH_RIB": 0.13, "T_BOX": 2.0, "T_GE": 0.5}
BOOK_DOPING = {"N": 5e17, "P": 7e17, "NP": 3e18, "PP": 2e18, "NPP": 5e20, "PPP": 1.9e20}


def y_range(component: gf.Component, layer) -> tuple[float, float]:
    points = np.vstack(component.get_polygons_points(by="tuple")[tuple(layer)])
    return float(points[:, 1].min()), float(points[:, 1].max())


def test_layer_numbers_follow_the_book():
    for book_name, (number, name) in BOOK_TABLE_10_2.items():
        assert tuple(getattr(t.LAYER, name)) == (number, 0), book_name


def test_layer_names_and_numbers_equal_the_gdsfactory_generic_pdk():
    from gdsfactory.gpdk import LAYER as GENERIC

    shared = [name for name in t.LAYER_INFO if hasattr(GENERIC, name)]
    assert len(shared) >= 24  # everything except nothing: the map is the generic one, by design
    for name in shared:
        assert tuple(getattr(t.LAYER, name)) == tuple(getattr(GENERIC, name)), name


def test_every_layer_is_described_and_has_a_view():
    names = {name for name in dir(t.LAYER) if name.isupper()}
    assert names == set(t.LAYER_INFO)
    assert set(t.LAYER_VIEWS.layer_views) == set(t.LAYER_INFO)
    assert set(t.MIN_WIDTH_SPACE) <= set(t.LAYER_INFO)


def test_front_end_numbers_follow_the_book():
    for name, value in BOOK_PROCESS.items():
        assert getattr(t, name) == pytest.approx(value), name
    assert pytest.approx(0.09) == t.T_SLAB90
    for name, value in BOOK_DOPING.items():
        assert t.DOPING[name] == pytest.approx(value), name


def test_stack_is_consistent():
    stack = {name: (z0, z1) for name, _, z0, z1, _ in t.STACK}
    assert stack["via_contact"] == pytest.approx((t.T_SLAB90, t.Z_M1))  # from the slab up to metal 1
    assert stack["heater"][0] == pytest.approx(stack["metal1"][0])  # the two films share a plane
    assert stack["via1"] == pytest.approx((stack["metal1"][1], stack["metal2"][0]))
    assert stack["via2"] == pytest.approx((stack["metal2"][1], stack["metal3"][0]))
    assert stack["cladding"][1] == pytest.approx(t.Z_TOP)
    assert stack["metal3"][1] < t.Z_TOP  # passivation above the top metal
    assert stack["box"] == pytest.approx((-t.T_BOX, 0.0))
    for name, (z0, z1) in stack.items():
        assert z1 > z0, name
    assert pytest.approx(10.0) == t.HEATER_SHEET_RESISTANCE


@pytest.mark.parametrize(("name", "width", "width_slab"), [("strip", 0.5, None), ("rib", 0.5, 6.0)])
def test_passive_cross_sections(name, width, width_slab):
    c = gf.components.straight(length=5, cross_section=name)
    lo, hi = y_range(c, t.WG)
    assert hi - lo == pytest.approx(width)
    if width_slab is not None:
        lo, hi = y_range(c, t.SLAB90)
        assert hi - lo == pytest.approx(width_slab)


def test_pn_cross_section_is_nested_and_n_is_left_of_the_path():
    c = gf.components.straight(length=5, cross_section="rib_pn")
    half = t.RIB_SLAB_WIDTH / 2
    # a path along +x has its left side at +y: n there, p at -y
    assert y_range(c, t.N) == pytest.approx((0.0, half))
    assert y_range(c, t.P) == pytest.approx((-half, 0.0))
    assert y_range(c, t.NP) == pytest.approx((t.PN_GAP_MEDIUM, half))
    assert y_range(c, t.PP) == pytest.approx((-half, -t.PN_GAP_MEDIUM))
    assert y_range(c, t.NPP) == pytest.approx((t.PN_GAP_HIGH, half))
    assert y_range(c, t.PPP) == pytest.approx((-half, -t.PN_GAP_HIGH))


def test_pn_cross_section_options():
    mirrored = gf.components.straight(length=5, cross_section=gf.get_cross_section("rib_pn", p_inside=True))
    assert y_range(mirrored, t.NPP)[1] < 0 < y_range(mirrored, t.PPP)[0]
    shifted = gf.components.straight(length=5, cross_section=gf.get_cross_section("rib_pn", junction_offset=0.05))
    assert y_range(shifted, t.N)[0] == pytest.approx(-0.05)  # the junction moved 50 nm towards p
    assert y_range(shifted, t.P)[1] == pytest.approx(-0.05)
    with pytest.raises(ValueError, match="gap_medium_doping"):
        gf.get_cross_section("rib_pn", gap_medium_doping=2.0, gap_high_doping=1.0)


def test_pad_has_an_opening_inside_the_metal():
    pad = t.pad(size=80)
    metal, opening = pad.get_region(t.M3).bbox(), pad.get_region(t.PADOPEN).bbox()
    margin = (metal.width() - opening.width()) / 2 * pad.kcl.dbu
    assert margin == pytest.approx(t.DESIGN_RULES["padopen_enclosure_by_m3"])


def test_write_gds_for_lumerical(tmp_path: Path):
    c = gf.components.straight(length=5, cross_section="rib_pn")
    path = t.write_gds_for_lumerical(c, tmp_path / "pn.gds", cellname="pn")
    layout = kdb.Layout()
    layout.read(str(path))
    assert [cell.name for cell in layout.top_cells()] == ["pn"]  # one flat cell, no metadata cell
    assert layout.cells() == 1
    layers = {(info.layer, info.datatype) for info in layout.layer_infos()}
    assert {(1, 0), (3, 0), (20, 0), (21, 0), (22, 0), (23, 0), (24, 0), (25, 0)} <= layers


def test_klayout_technology_is_written(tmp_path: Path):
    out = t.write_klayout_tech(tmp_path)
    text = (out / "layers.lyp").read_text(encoding="utf-8")
    for name in t.LAYER_INFO:
        assert f"<name>{name}" in text, name
    # writing the technology again must not change the tracked copy: sorted symbols, no empty d25 folder
    lyt = out / "tech.lyt"
    if lyt.exists():  # absent when KLayout cannot write a technology, see write_klayout_tech
        symbols = [line for line in lyt.read_text(encoding="utf-8").splitlines() if "<symbols>" in line]
        assert symbols == sorted(symbols)
    assert not (out / "d25").exists()

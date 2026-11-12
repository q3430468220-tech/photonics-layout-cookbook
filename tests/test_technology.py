"""The technology file against the published CORNERSTONE SOI220A data."""

from __future__ import annotations

import os
import re
from pathlib import Path

import gdsfactory as gf
import klayout.db as kdb
import numpy as np
import pytest

import cornerstone_technology as t

# GDS numbers and names of SOI220A/process_overview.yaml (cornerstone-uos/cornerstone-pdk, v1.2.0).
OFFICIAL_LAYERS = {
    "Si_Etch1_DUV_DF_70nm": (6, 0),
    "Si_Etch2_LF_120nm": (3, 0),
    "Si_Etch2_DF_120nm": (4, 0),
    "Si_Etch3_LF_100nm_to_BOX": (5, 0),
    "P_Implant_Low_DF": (7, 0),
    "N_Implant_Low_DF": (8, 0),
    "P_Implant_Hi_DF": (9, 0),
    "N_Implant_Hi_DF": (11, 0),
    "Via_DF": (12, 0),
    "Electrode_LF": (13, 0),
    "Detector_Implant_DF": (23, 0),
    "Floorplan": (99, 0),
    "Label_Etch_DF": (100, 0),
}


def y_range(component: gf.Component, layer) -> tuple[float, float]:
    points = np.vstack(component.get_polygons_points(by="tuple")[tuple(layer)])
    return float(points[:, 1].min()), float(points[:, 1].max())


def test_layers_match_the_official_table():
    ours = {name: tuple(getattr(t.LAYER, key)) for key, name in t.OFFICIAL_LAYER_NAMES.items()}
    simulation_only = ours.pop("Sim_N_Sidewall")
    assert ours == OFFICIAL_LAYERS
    assert simulation_only not in OFFICIAL_LAYERS.values()


def test_every_mask_layer_has_a_view_and_rules():
    for key in t.MIN_WIDTH_SPACE:
        assert key in t.OFFICIAL_LAYER_NAMES
    assert set(t.LAYER_VIEWS.layer_views) == set(t.OFFICIAL_LAYER_NAMES.values())


@pytest.mark.parametrize(
    ("name", "width", "width_slab", "radius"),
    [
        ("strip_1550nm", 0.45, None, 10),
        ("strip_1310nm", 0.40, None, 10),
        ("rib_1550nm_TE", 0.45, 10.45, 25),
        ("rib_1310nm_TE", 0.40, 10.40, 25),
    ],
)
def test_passive_cross_sections_match_the_official_ones(name, width, width_slab, radius):
    xs = gf.get_cross_section(name)
    assert xs.width == pytest.approx(width)
    assert xs.radius == pytest.approx(radius)
    c = gf.components.straight(length=5, cross_section=name)
    lo, hi = y_range(c, t.CORE)
    assert hi - lo == pytest.approx(width)
    if width_slab is not None:
        lo, hi = y_range(c, t.SLAB)
        assert hi - lo == pytest.approx(width_slab)


def test_pn_cross_section_follows_the_guidelines():
    c = gf.components.straight(length=5, cross_section="rib_1550nm_TE_pn")
    core, p_low, n_low = y_range(c, t.CORE), y_range(c, t.P_LOW), y_range(c, t.N_LOW)
    n_high, p_high = y_range(c, t.N_HI), y_range(c, t.P_HI)
    # the n implant edge sits on the core centre and the n region lies inside the background p implant
    assert min(abs(n_low[0]), abs(n_low[1])) == pytest.approx(0.0, abs=1e-6)
    assert p_low[0] <= n_low[0] and n_low[1] <= p_low[1]
    # n on the left of the path (+y), p on the right; high doses keep clear of the core
    assert n_high[0] == pytest.approx(0.75) and p_high[1] == pytest.approx(-0.80)
    assert n_high[0] > core[1] and p_high[1] < core[0]


def test_p_inside_mirrors_the_junction():
    c = gf.components.straight(length=5, cross_section=gf.get_cross_section("rib_1550nm_TE_pn", p_inside=True))
    assert y_range(c, t.N_HI)[1] < 0 < y_range(c, t.P_HI)[0]


def test_self_aligned_n_sidewall_strip():
    c = gf.components.straight(length=5, cross_section="rib_1550nm_TE_pn")
    strip = t.silicon_regions(c)["n_sidewall"].bbox()
    dbu = c.kcl.dbu
    assert strip.top * dbu == pytest.approx(0.225)  # the n-side sidewall
    assert (strip.top - strip.bottom) * dbu == pytest.approx(t.N_SIDEWALL_DEPTH)


def test_write_gds_for_lumerical(tmp_path: Path):
    c = gf.components.straight(length=5, cross_section="rib_1550nm_TE_pn")
    path = t.write_gds_for_lumerical(c, tmp_path / "pn.gds", cellname="pn")
    layout = kdb.Layout()
    layout.read(str(path))
    assert [cell.name for cell in layout.top_cells()] == ["pn"]  # one flat cell, no metadata cell
    assert layout.cells() == 1
    layers = {(info.layer, info.datatype) for info in layout.layer_infos()}
    assert tuple(t.LAYER.SIM_N_SIDEWALL) in layers
    assert {(3, 0), (5, 0), (7, 0), (8, 0), (9, 0), (11, 0)} <= layers


def test_klayout_technology_is_written(tmp_path: Path):
    out = t.write_klayout_tech(tmp_path)
    text = (out / "layers.lyp").read_text(encoding="utf-8")
    for name in OFFICIAL_LAYERS:
        assert name in text


def test_against_a_checkout_of_the_official_repository():
    """Optional: set CORNERSTONE_PDK to a clone of github.com/cornerstone-uos/cornerstone-pdk."""
    root = os.environ.get("CORNERSTONE_PDK")
    if not root:
        pytest.skip("CORNERSTONE_PDK is not set")
    text = (Path(root) / "SOI220A" / "process_overview.yaml").read_text(encoding="utf-8")
    pairs = re.findall(r"- name: (\w+)\s+layer: \[(\d+), (\d+)\]", text)
    found = {name: (int(layer), int(datatype)) for name, layer, datatype in pairs}
    assert found == OFFICIAL_LAYERS

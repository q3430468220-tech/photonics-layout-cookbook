"""The gdsfactory PDK generated from the process file (needs gdsfactory + cspdk)."""

from __future__ import annotations

import pytest

gf = pytest.importorskip("gdsfactory")
pytest.importorskip("klayout.db")

from photonics_cookbook.lumerical import export_lumerical, info_from_component  # noqa: E402
from photonics_cookbook.pdk import activate_pdk, get_pdk, write_klayout_tech  # noqa: E402
from photonics_cookbook.process import load_process  # noqa: E402
from photonics_cookbook.process.upstream import check_against_pdk  # noqa: E402

PROC = "cornerstone_si220_active"


@pytest.fixture(scope="module")
def pdk():
    return activate_pdk(PROC)


def test_layer_map_extends_cspdk(pdk):
    members = pdk.layers.__members__
    for name, gds in {"WG": (3, 0), "SLAB": (5, 0), "GRA": (6, 0), "HEATER": (39, 0), "PAD": (41, 0)}.items():
        assert (members[name].layer, members[name].datatype) == gds  # from cspdk
    for name, gds in {"P": (7, 0), "N": (8, 0), "PPP": (9, 0), "NPP": (11, 0), "VIA": (12, 0), "METAL": (13, 0)}.items():
        assert (members[name].layer, members[name].datatype) == gds  # added by the cookbook
    assert gf.get_layer_tuple("NPP") == (11, 0)


def test_layer_stack(pdk):
    levels = pdk.layer_stack.layers
    for name in ("box", "clad", "core", "slab", "shallow_etch", "via", "metal"):
        assert name in levels, name
    assert levels["core"].thickness == pytest.approx(0.22)
    assert levels["shallow_etch"].thickness == pytest.approx(0.15)  # 220 nm - 70 nm grating etch
    assert levels["box"].background and levels["clad"].background
    assert levels["core"].info["lumerical_optical"] == "Si (Silicon) - Palik"


def test_layer_views(pdk, tmp_path):
    views = pdk.get_layer_views().layer_views
    assert {"WG", "SLAB", "NPP", "PPP", "VIA", "METAL"} <= set(views)
    out = write_klayout_tech(PROC, tmp_path / "tech")
    assert (out / "layers.lyp").exists()


def test_check_pdk_is_consistent():
    _, checks = check_against_pdk(load_process(PROC))
    status = {c.name: c.status for c in checks}
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert status["WG"] == "ok" and status["NPP"] == "extension"


def test_rib_pn_cross_section(pdk):
    xs = gf.get_cross_section("rib_pn")
    assert xs.name == "rib_pn"
    layers = {str(s.layer) for s in xs.sections}
    assert {"WG", "SLAB", "N", "P", "NPP", "PPP", "VIA", "METAL"} <= layers


def test_cells_from_pdk(pdk, tmp_path):
    assert {"ring_modulator", "straight_pn", "mmi1x2", "straight"} <= set(pdk.cells)
    ring = gf.get_component("ring_modulator")
    assert sorted(p.name for p in ring.ports) == ["e1", "e2", "e3", "o1", "o2"]
    pn = gf.get_component("straight_pn", length=100)
    assert {"o1", "o2", "n1", "n2", "p1", "p2"} <= {p.name for p in pn.ports}
    mmi = gf.get_component("mmi1x2")  # upstream cspdk cell keeps working
    assert len(mmi.ports) >= 3


def test_straight_pn_to_lumerical(pdk, tmp_path):
    pn = gf.get_component("straight_pn", length=500)
    gds = pn.write_gds(tmp_path / "pn.gds")
    res = export_lumerical(gds, PROC, tmp_path / "lum", info=info_from_component(pn), preview=False)
    assert "charge2d" in res.files and "fde2d" in res.files, res.skipped
    assert res.xsec is not None and len(res.xsec.by_role("via")) == 2


def test_pdk_is_cached():
    assert get_pdk(PROC) is get_pdk(PROC)

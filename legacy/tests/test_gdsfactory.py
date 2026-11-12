"""End-to-end with the real layout stack: gdsfactory cell -> GDS -> KLayout -> cut.

Skipped automatically if gdsfactory / klayout are not installed.
"""

from __future__ import annotations

import pytest

gf = pytest.importorskip("gdsfactory")
pytest.importorskip("klayout.db")

from photonics_cookbook.cells import activate_pdk, ring_modulator  # noqa: E402
from photonics_cookbook.lumerical import (  # noqa: E402
    cross_section_from_gds,
    export_lumerical,
    info_from_component,
    ports_from_component,
)
from photonics_cookbook.process import load_process  # noqa: E402

PROC = "cornerstone_si220_active"


@pytest.fixture(scope="module")
def component():
    activate_pdk(PROC)
    return ring_modulator(process=PROC)


def test_component_ports_and_layers(component):
    names = sorted(p.name for p in component.ports)
    assert names == ["e1", "e2", "e3", "o1", "o2"]
    optical = ports_from_component(component)
    assert {p.name for p in optical} == {"o1", "o2"}
    assert info_from_component(component)["lumerical"]["bend_radius_um"] == 10.0


def test_gds_round_trip_cut(component, tmp_path):
    proc = load_process(PROC)
    gds = component.write_gds(tmp_path / "ring.gds")
    lum = info_from_component(component)["lumerical"]
    x = cross_section_from_gds(gds, proc, lum["cut_p0_um"], lum["cut_p1_um"], lum["cut_origin_um"])
    (core,) = x.by_role("core")
    assert core.x0 == pytest.approx(-0.25, abs=3e-3) and core.x1 == pytest.approx(0.25, abs=3e-3)
    assert len(x.by_role("via")) == 2


def test_export_from_real_gds(component, tmp_path):
    gds = component.write_gds(tmp_path / "ring.gds")
    res = export_lumerical(
        gds, PROC, tmp_path / "lum", ports=ports_from_component(component), info=info_from_component(component)
    )
    assert {"geometry3d", "fdtd3d", "layerbuilder", "charge2d", "fde2d"} <= set(res.files)

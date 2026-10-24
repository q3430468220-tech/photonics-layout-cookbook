"""Generated Lumerical scripts: structure checks (no Lumerical needed)."""

from __future__ import annotations

import json
import re

import numpy as np
import pytest

from photonics_cookbook.devices import ring_modulator_geometry
from photonics_cookbook.lumerical import export as ex
from photonics_cookbook.lumerical.cutline import geometry_polygons
from photonics_cookbook.lumerical.scripts_3d import OpticalPort, builder_slices
from photonics_cookbook.process import load_process

PROC = "cornerstone_si220_active"


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    proc = load_process(PROC)
    g = ring_modulator_geometry(proc)
    polys = geometry_polygons(g, proc)
    allp = np.vstack([c[0] for v in polys.values() for c in v])
    bbox = (allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max())
    out = tmp_path_factory.mktemp("lum")
    gds = out / "ring_modulator.gds"
    gds.write_bytes(b"")  # the reader is replaced below; real GDS round trip: test_gdsfactory.py
    orig = ex.read_gds_polygons
    ex.read_gds_polygons = lambda path, cell=None, layers=None: ("ring_modulator", polys, bbox)
    try:
        ports = [OpticalPort(p.name, *p.center, p.width, p.orientation) for p in g.ports if p.port_type == "optical"]
        res = ex.export_lumerical(gds, proc, ports=ports, info=g.info, preview=False)
    finally:
        ex.read_gds_polygons = orig
    return res


def _strip_strings(text: str) -> str:
    return re.sub(r'"[^"\n]*"', '""', text)


def _code(text: str) -> str:
    return "\n".join(ln.split("#", 1)[0] for ln in _strip_strings(text).splitlines())


@pytest.mark.parametrize("key", ["geometry3d", "fdtd3d", "layerbuilder", "charge2d", "fde2d"])
def test_scripts_are_balanced(exported, key):
    text = exported.files[key].read_text(encoding="utf-8")
    code = _code(text)
    for a, b in ("()", "{}", "[]"):
        assert code.count(a) == code.count(b), f"{key}: unbalanced {a}{b}"
    assert text.count('"') % 2 == 0, f"{key}: odd number of quotes"
    assert "None" not in code and "nan" not in code.lower().replace("nanometre", "")


def test_all_targets_written(exported):
    assert not exported.skipped, exported.skipped
    meta = json.loads(exported.files["meta"].read_text())
    assert meta["process"] == PROC and len(meta["ports"]) == 2


def test_geometry3d_imports_every_drawn_layer(exported):
    text = exported.files["geometry3d"].read_text()
    for spec in ("3:0", "5:0", "12:0", "13:0"):
        assert f'gds_layer(gds_file, cell, "{spec}"' in text
    assert '"6:0"' not in text  # layers without shapes are not imported
    for spec in ("7:0", "8:0", "9:0", "11:0"):  # implants are not 3D geometry
        assert f'"{spec}"' not in text


def test_charge_script_contacts_and_doping(exported):
    text = exported.files["charge2d"].read_text()
    assert 'set("solid", "anode_via_1")' in text and 'set("solid", "cathode_via_1")' in text
    assert text.count("add_dope_box(") == 4 + 1  # 4 implants + the function definition
    assert 'set("filename", "ring_modulator_charge.mat")' in text
    assert "norm_length = 46.53" in text


def test_fde_uses_same_frame(exported):
    text = exported.files["fde2d"].read_text()
    assert 'set("solver type", "2D Y normal")' in text
    assert 'importdataset(charge_file)' in text and "bend_radius = 10*um" in text


def test_layer_builder_slices_are_contiguous():
    proc = load_process(PROC)
    sl = builder_slices(proc)
    for a, b in zip(sl[:-1], sl[1:], strict=True):
        assert a.z1 == pytest.approx(b.z0)
    rib = [s for s in sl if s.expression and "5:0" in s.expression]
    assert rib and rib[0].z1 == pytest.approx(0.10)

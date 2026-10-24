from __future__ import annotations

import math
import textwrap

import numpy as np
import pytest

from photonics_cookbook.devices import ring_modulator_geometry
from photonics_cookbook.geometry import annulus, arc_band, polygon_area
from photonics_cookbook.lumerical.cutline import cross_section, geometry_polygons, line_polygon_intervals
from photonics_cookbook.process import ProcessError, available_processes, load_process

PROC = "cornerstone_si220_active"


@pytest.fixture(scope="module")
def proc():
    return load_process(PROC)


# ------------------------------------------------------------------ process
def test_shipped_processes_load():
    names = available_processes()
    assert PROC in names
    for n in names:
        load_process(n)


def test_cornerstone_layers(proc):
    assert proc.gds("core") == (3, 0)
    assert proc.gds("slab") == (5, 0)
    assert proc.gds("ppp") == (9, 0) and proc.gds("npp") == (11, 0)
    assert proc.layer("npp").concentration == pytest.approx(1e20)
    assert proc.si_top == pytest.approx(0.22)
    assert proc.role_of((12, 0)) == "via"
    assert proc.material_name("si", "charge") == "Si (Silicon)"


def _write(tmp_path, body: str):
    p = tmp_path / "p.yaml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


BASE = """
name: t
materials:
  si: {kind: semiconductor, optical: "Si (Silicon) - Palik", charge: "Si (Silicon)"}
layers:
  core: {gds: [1, 0], kind: structure, material: si, zmin: 0, thickness: 0.22}
"""


def test_yaml_exponent_without_sign_is_accepted(tmp_path):
    p = _write(tmp_path, BASE + "  n: {gds: [2, 0], kind: doping, dopant: n, concentration: 1.0e18}\n")
    assert load_process(p).layer("n").concentration == pytest.approx(1e18)


@pytest.mark.parametrize(
    "extra, msg",
    [
        ("  n: {gds: [1, 0], kind: doping, dopant: n, concentration: 1.0e+18}\n", "used by both"),
        ("  n: {gds: [2, 0], kind: doping, dopant: x, concentration: 1.0e+18}\n", "dopant"),
        ("  n: {gds: [2, 0], kind: doping, dopant: n, concentration: 1.0e+24}\n", r"cm\^-3"),
        ("  m: {gds: [3, 0], kind: metal, material: al, zmin: 1, thickness: 1}\n", "undefined material"),
        ("  m: {gds: [3, 0], kind: magic}\n", "kind must be"),
    ],
)
def test_bad_process_files(tmp_path, extra, msg):
    with pytest.raises(ProcessError, match=msg):
        load_process(_write(tmp_path, BASE + extra))


# ------------------------------------------------------------------ geometry
def test_annulus_area():
    polys = annulus(9.75, 10.25, tol=1e-4)
    area = sum(polygon_area(p) for p in polys)
    assert area == pytest.approx(math.pi * (10.25**2 - 9.75**2), rel=1e-4)
    assert all(polygon_area(p) > 0 for p in polys)


def test_arc_band_splits_large_spans():
    assert len(arc_band(1, 2, 0, 90)) == 1
    assert len(arc_band(1, 2, 0, 270)) == 2


# ------------------------------------------------------------------ cut line
def test_line_through_square_with_hole():
    hull = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], float)
    hole = np.array([[4, 4], [6, 4], [6, 6], [4, 6]], float)
    iv = line_polygon_intervals([hull, hole], np.array([-1.0, 5.0]), np.array([11.0, 5.0]))
    got = [(round(a * 12 - 1, 6), round(b * 12 - 1, 6)) for a, b in iv]
    assert got == [(0, 4), (6, 10)]


def test_line_through_vertex():
    tri = np.array([[0, 0], [2, 1], [0, 2]], float)  # vertex (2, 1) on the line y = 1
    iv = line_polygon_intervals([tri], np.array([-1.0, 1.0]), np.array([3.0, 1.0]))
    assert [(round(a * 4 - 1, 6), round(b * 4 - 1, 6)) for a, b in iv] == [(0, 2)]


# ------------------------------------------------------------------ ring modulator
@pytest.fixture(scope="module")
def ring(proc):
    return ring_modulator_geometry(proc)


def test_ring_roles_and_ports(ring):
    for role in ("core", "slab", "n", "p", "npp", "ppp", "via", "metal"):
        assert role in ring.polygons, role
    assert [p.name for p in ring.ports] == ["e1", "e2", "e3", "o1", "o2"]
    o1, o2 = ring.port("o1"), ring.port("o2")
    assert o1.orientation == 180 and o2.orientation == 0 and o1.center[1] == o2.center[1]
    # bus centre = -(R + gap + w)
    assert o1.center[1] == pytest.approx(-(10 + 0.2 + 0.5))


def test_ring_cut_matches_design(proc, ring):
    lum = ring.info["lumerical"]
    x = cross_section(geometry_polygons(ring, proc), proc, lum["cut_p0_um"], lum["cut_p1_um"], lum["cut_origin_um"])
    core = x.by_role("core")
    assert len(core) == 1 and core[0].x0 == pytest.approx(-0.25, abs=2e-3) and core[0].x1 == pytest.approx(0.25, abs=2e-3)
    # N inside (x < 0 is towards the ring centre), P outside, junction at the rib centre
    (n,) = x.by_role("n")
    (p,) = x.by_role("p")
    assert n.x1 == pytest.approx(0, abs=2e-3) and p.x0 == pytest.approx(0, abs=2e-3)
    (npp,) = x.by_role("npp")
    (ppp,) = x.by_role("ppp")
    assert npp.x1 == pytest.approx(-0.25 - 0.8, abs=3e-3)
    assert ppp.x0 == pytest.approx(0.25 + 0.8, abs=3e-3)
    vias = x.by_role("via")
    assert len(vias) == 2
    assert any(v.overlaps(npp) for v in vias) and any(v.overlaps(ppp) for v in vias)


def test_coupler_window_is_undoped(proc, ring):
    # cut through the coupling point (theta = -90 deg): no implants, no metal
    x = cross_section(geometry_polygons(ring, proc), proc, (0, -5.0), (0, -15.0), (0, -10.0))
    assert not [iv for iv in x.intervals if proc.layer(iv.role).kind in ("doping", "via", "metal")]
    assert len(x.by_role("core")) == 2  # ring + bus


def test_signal_bridge_does_not_short_ground(proc, ring):
    # at theta = 90 deg the S bridge crosses the ring; the outer (G) contact must be open there
    x = cross_section(geometry_polygons(ring, proc), proc, (0, 5.0), (0, 15.0), (0, 10.0))
    vias = x.by_role("via")
    assert len(vias) == 1 and vias[0].x1 < 0  # only the inner (N++) via


def test_inner_dopant_flip(proc):
    g = ring_modulator_geometry(proc, inner_dopant="p")
    assert g.info["contacts"]["anode"] == "ppp"
    lum = g.info["lumerical"]
    x = cross_section(geometry_polygons(g, proc), proc, lum["cut_p0_um"], lum["cut_p1_um"], lum["cut_origin_um"])
    (ppp,) = x.by_role("ppp")
    assert ppp.x1 < 0


@pytest.mark.parametrize(
    "kwargs",
    [dict(radius=3.0), dict(junction_offset=0.3), dict(inner_dopant="x"), dict(cut_angle_deg=-90)],
)
def test_ring_rejects_bad_parameters(proc, kwargs):
    with pytest.raises(ValueError):
        ring_modulator_geometry(proc, **kwargs)

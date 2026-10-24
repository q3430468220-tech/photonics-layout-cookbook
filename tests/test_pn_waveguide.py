"""PN rib cross-section (rib_pn) geometry -- pure Python, no gdsfactory needed."""

from __future__ import annotations

import pytest

from photonics_cookbook.devices import pn_rib_sections, pn_straight_geometry, ring_modulator_geometry
from photonics_cookbook.lumerical.cutline import cross_section, geometry_polygons
from photonics_cookbook.lumerical.scripts_2d import charge2d_lsf, fde2d_lsf, junctions
from photonics_cookbook.process import ProcessError, load_process

PROC = "cornerstone_si220_active"


@pytest.fixture(scope="module")
def proc():
    return load_process(PROC)


def _by_name(specs):
    return {s.name: s for s in specs}


def test_sections_layout(proc):
    s = _by_name(pn_rib_sections(proc))
    assert list(s)[0] == "core" and s["core"].port_names == ("o1", "o2")
    # N on +y, P on -y, meeting at the junction (rib centre)
    assert s["n"].y0 == pytest.approx(0) and s["p"].y1 == pytest.approx(0)
    assert s["npp"].offset > 0 > s["ppp"].offset
    # ++ stripes start contact_spacing away from the rib edge
    assert s["npp"].y0 == pytest.approx(0.25 + 0.8) and s["ppp"].y1 == pytest.approx(-(0.25 + 0.8))
    # vias enclosed by ++ by via_enclosure, metal on top of ++
    for tag, dop in (("n", "npp"), ("p", "ppp")):
        via, pp, metal = s[f"via_{tag}"], s[dop], s[f"metal_{tag}"]
        assert via.y0 == pytest.approx(pp.y0 + 0.5) and via.y1 == pytest.approx(pp.y1 - 0.5)
        assert metal.offset == pytest.approx(pp.offset) and metal.width == pytest.approx(pp.width)
        assert metal.port_names == (f"{tag}1", f"{tag}2")
    # slab covers everything doped
    assert s["slab"].y1 >= s["npp"].y1 and s["slab"].y0 <= s["ppp"].y0


def test_junction_offset_and_flip(proc):
    s = _by_name(pn_rib_sections(proc, junction_offset=0.05))
    assert s["n"].y0 == pytest.approx(0.05) and s["p"].y1 == pytest.approx(0.05)
    f = _by_name(pn_rib_sections(proc, flip=True))
    assert f["n"].offset < 0 < f["p"].offset and f["npp"].offset < 0 < f["ppp"].offset


@pytest.mark.parametrize(
    "kwargs", [dict(junction_offset=0.3), dict(contact_width=0.8), dict(width=0)]
)
def test_rejects_bad_parameters(proc, kwargs):
    with pytest.raises(ValueError):
        pn_rib_sections(proc, **kwargs)


def test_needs_implants(tmp_path):
    p = tmp_path / "passive.yaml"
    p.write_text(
        "name: passive\n"
        "materials: {si: {kind: semiconductor, optical: x, charge: y}}\n"
        "layers:\n"
        "  core: {gds: [1, 0], kind: structure, material: si, zmin: 0, thickness: 0.22}\n",
        encoding="utf-8",
    )
    with pytest.raises(ProcessError):
        pn_rib_sections(load_process(p))


def test_straight_cut_equals_ring_cut(proc):
    """The straight PN waveguide and the ring modulator share one CHARGE cross-section."""
    g = pn_straight_geometry(proc, 500)
    lum = g.info["lumerical"]
    xs = cross_section(geometry_polygons(g, proc), proc, lum["cut_p0_um"], lum["cut_p1_um"], lum["cut_origin_um"])
    ring = ring_modulator_geometry(proc)
    rl = ring.info["lumerical"]
    xr = cross_section(geometry_polygons(ring, proc), proc, rl["cut_p0_um"], rl["cut_p1_um"], rl["cut_origin_um"])

    def widths(x, role):
        return sorted(round(iv.width, 2) for iv in x.by_role(role))

    for role in ("core", "slab", "n", "p", "npp", "ppp", "via"):
        assert widths(xs, role) == widths(xr, role), role
    assert junctions(xs, proc) == [0.0]


def test_straight_exports_to_charge_and_fde(proc):
    g = pn_straight_geometry(proc, 500)
    lum = g.info["lumerical"]
    x = cross_section(geometry_polygons(g, proc), proc, lum["cut_p0_um"], lum["cut_p1_um"], lum["cut_origin_um"], cell="straight_pn")
    charge = charge2d_lsf(x, proc, lum["norm_length_um"], lum["anode_role"], lum["cathode_role"])
    assert 'set("solid", "anode_via_1")' in charge and "norm_length = 500*um" in charge
    fde = fde2d_lsf(x, proc, bend_radius_um=None, doped_length_um=500)
    assert "bend_radius = 0;" in fde
    assert [p.name for p in g.ports] == ["o1", "o2", "n1", "n2", "p1", "p2"]

"""The device builder and the DRC."""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import klayout.db as kdb
import pytest
from test_connectivity import number, pad_nets

import gsip_technology as t
import rm_builder as rm
from gsip_drc import demo_component, run_drc


def test_default_ring_modulator_is_drc_clean(tmp_path: Path):
    device = rm.ring_modulator()
    result = run_drc(device, rdb_path=tmp_path / "drc.lyrdb")
    assert result.passed, result.summary()
    assert not result.warnings, result.summary()
    assert (tmp_path / "drc.lyrdb").exists()


def test_ports_and_info():
    device = rm.ring_modulator()
    assert {p.name for p in device.ports} == {"o1", "o2", "G1", "S", "G2", "H1", "H2"}
    info = device.info
    ring = 2 * math.pi * 10
    assert info["length_ring"] == pytest.approx(ring, abs=1e-3)
    assert info["length_pn"] == pytest.approx(ring * 240 / 360, abs=1e-3)
    assert info["length_heater"] == pytest.approx(ring * 270 / 360 - rm.LANDING, abs=1e-3)


def test_device_uses_the_whole_back_end():
    device = rm.ring_modulator()
    used = {name for name in t.LAYER_INFO if not device.get_region(getattr(t.LAYER, name)).is_empty()}
    assert used == {
        "WG",
        "SLAB90",
        "N",
        "P",
        "NP",
        "PP",
        "NPP",
        "PPP",
        "VIAC",
        "M1",
        "HEATER",
        "VIA1",
        "M2",
        "VIA2",
        "M3",
        "PADOPEN",
    }


def test_gap_is_the_edge_to_edge_distance():
    for gap in (0.25, 0.37):
        device = rm.ring_modulator(gap=gap)
        core = device.get_region(t.WG, merge=True)
        ring, bus = sorted(core.each(), key=lambda p: p.bbox().height(), reverse=True)[:2]
        distance = (ring.bbox().bottom - bus.bbox().top) * device.kcl.dbu
        assert distance == pytest.approx(gap, abs=0.002)


def test_a_contact_via_sits_on_the_symmetry_axis():
    """The cross-section figures cut the device at x = 0: both via rows must have a via there."""
    device = rm.ring_modulator()
    dbu = device.kcl.dbu
    axis = kdb.Region(kdb.Box(-1, 0, 1, round(20 / dbu)))  # the line x = 0 north of the ring centre
    hits = sorted(p.bbox().center().y * dbu for p in (device.get_region(t.VIAC, merge=True) & axis).each())
    assert len(hits) == 2
    assert hits[0] == pytest.approx(10 - rm.VIA_GAP - rm.VIA_SIZE / 2, abs=0.01)
    assert hits[1] == pytest.approx(10 + rm.VIA_GAP + rm.VIA_SIZE / 2, abs=0.01)


def test_other_sizes_stay_drc_clean():
    for kwargs in ({"radius": 12.0}, {"gap": 0.25}, {"pn_angle": 220.0, "heater_angle": 260.0}, {"p_inside": True}):
        result = run_drc(rm.ring_modulator(**kwargs))
        assert result.passed and not result.warnings, (kwargs, result.summary())


def test_rejected_parameters():
    with pytest.raises(ValueError, match="heater_angle must exceed"):
        rm.ring_modulator(pn_angle=265.0, heater_angle=270.0)  # a heater landing would touch the outer electrode
    with pytest.raises(ValueError, match="minimum space"):
        rm.ring_modulator(gap=0.1)
    with pytest.raises(ValueError, match="clearance between the heater and the bus core"):
        rm.ring_modulator(pn_angle=280.0, heater_angle=320.0)  # the heater reaches down over the bus waveguide
    with pytest.raises(ValueError, match="rib bend radius"):
        rm.ring_modulator(radius=8.0, pn_angle=220.0, heater_angle=250.0)  # tighter than the rib bend radius


def test_heater_clearance_is_measured_on_the_drawn_heater():
    """At the smallest gap the lowest point of the heater is about 0.8 um above the bus core: heater_angle 270 builds."""
    device = rm.ring_modulator(gap=0.2)
    assert run_drc(device).passed


SWEEP_REASONS = ("heater_angle must exceed", "clearance between the heater and the bus core", "minimum space", "rib bend radius")


def test_parameter_sweep_builds_clean_or_is_refused():
    """A reduced sweep of the builder: each variant builds DRC clean with its nets intact, or is refused
    with one of the stated reasons.  The pn 120 variants with heater 150 and 165 degrees once put metal 2 0.83 um
    from its neighbour, so they are in the grid."""
    built = refused = 0
    grid = itertools.product(
        (10.0, 12.0, 15.0), (0.2, 0.6), ((120.0, 30.0), (120.0, 45.0), (240.0, 20.0), (240.0, 60.0)), (False, True)
    )
    for radius, gap, (pn, extra), p_inside in grid:
        kwargs = dict(radius=radius, gap=gap, pn_angle=pn, heater_angle=pn + extra, p_inside=p_inside)
        try:
            device = rm.ring_modulator(**kwargs)
        except ValueError as err:
            assert any(reason in str(err) for reason in SWEEP_REASONS), (kwargs, str(err))
            refused += 1
            continue
        result = run_drc(device)
        assert result.passed and not result.warnings, (kwargs, result.summary())
        nets = pad_nets(device)
        assert number(nets["G1"]) == number(nets["G2"]), kwargs
        assert number(nets["H1"]) == number(nets["H2"]), kwargs
        assert len({number(nets[name]) for name in ("S", "G1", "H1")}) == 3, kwargs
        built += 1
    assert built > 0 and refused > 0


def test_drc_finds_the_planted_violations():
    result = run_drc(demo_component())
    rules = " | ".join(result.errors)
    for fragment in (
        "WG: narrower",
        "WG: space smaller",
        "contact via not enclosed by metal 1",
        "via 1 not enclosed by metal 1 or the heater",
        "via 1 not enclosed by metal 2",
        "closer than 0.6 um to the heater",
        "N++ overlaps P++",
    ):
        assert fragment in rules, fragment
    assert "implant drawn where there is no silicon" in result.warnings
    assert not result.passed


def test_drc_reads_a_gds_file(tmp_path: Path):
    path = t.write_gds_for_lumerical(rm.ring_modulator(), tmp_path / "rm.gds", cellname="rm")
    assert run_drc(path).passed

"""The device builder and the DRC."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import cornerstone_technology as t
import rm_builder as rm
from cornerstone_drc import demo_component, run_drc


def test_default_ring_modulator_is_drc_clean(tmp_path: Path):
    device = rm.ring_modulator()
    result = run_drc(device, rdb_path=tmp_path / "drc.lyrdb")
    assert result.passed, result.summary()
    # the only expected warning: the 2 um heater filament in the electrode layer
    assert list(result.warnings) == ["Electrode_LF: feature narrower than 6.0 um -- allowed for heater filaments only"]
    assert (tmp_path / "drc.lyrdb").exists()


def test_ports_and_info():
    device = rm.ring_modulator()
    assert {p.name for p in device.ports} == {"o1", "o2", "G1", "S", "G2", "H1", "H2"}
    info = device.info
    assert info["length_ring"] == pytest.approx(2 * math.pi * 25, abs=1e-3)
    assert info["length_pn"] == pytest.approx(info["length_ring"] * 240 / 360, abs=1e-3)
    assert info["length_heater"] == pytest.approx(info["length_ring"] * 76 / 360 - rm.LEAD_WIDTH, abs=1e-3)


def test_gap_is_the_edge_to_edge_distance():
    for gap in (0.25, 0.40):
        device = rm.ring_modulator(gap=gap)
        core = device.get_region(t.CORE, merge=True)
        ring, bus = sorted(core.each(), key=lambda p: p.bbox().height(), reverse=True)[:2]
        distance = (ring.bbox().bottom - bus.bbox().top) * device.kcl.dbu
        assert distance == pytest.approx(gap, abs=0.002)


def test_other_sizes_stay_drc_clean():
    for kwargs in ({"radius": 30.0}, {"gap": 0.4, "pn_angle": 220.0, "heater_angle": 90.0}, {"p_inside": True}):
        assert run_drc(rm.ring_modulator(**kwargs)).passed, kwargs


def test_rejected_parameters():
    with pytest.raises(ValueError, match="too large"):
        rm.ring_modulator(pn_angle=270.0, heater_angle=80.0)  # PN electrodes would touch the heater leads
    with pytest.raises(ValueError, match="minimum gap"):
        rm.ring_modulator(gap=0.1)


def test_drc_finds_the_planted_violations():
    result = run_drc(demo_component())
    rules = " | ".join(result.errors)
    for fragment in (
        "Si_Etch2_LF_120nm: feature narrower",
        "Si_Etch2_LF_120nm: gap smaller",
        "Electrode_LF: gap smaller",
        "not enclosed by P++ / N++",
        "not enclosed by Electrode_LF",
        "outside P_Implant_Low_DF",
    ):
        assert fragment in rules
    assert result.warnings and not result.passed


def test_drc_reads_a_gds_file(tmp_path: Path):
    path = t.write_gds_for_lumerical(rm.ring_modulator(), tmp_path / "rm.gds", cellname="rm")
    assert run_drc(path).passed

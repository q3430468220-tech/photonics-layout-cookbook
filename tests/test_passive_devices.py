"""The passive devices: every builder draws what its arguments say, passes the DRC, and refuses what breaks a rule."""

from __future__ import annotations

import math

import klayout.db as kdb
import pytest

import gsip_technology as t
from devices import GDS, directional_coupler_builder, mmi1x2_builder, rib_waveguide_builder, strip_waveguide_builder
from devices import ring_modulator_builder as ring_modulator_module
from gsip_drc import run_drc

sw, rw, dc, mb = strip_waveguide_builder, rib_waveguide_builder, directional_coupler_builder, mmi1x2_builder

DEVICES = {
    "strip_waveguide": sw.strip_waveguide,
    "rib_waveguide": rw.rib_waveguide,
    "directional_coupler": dc.directional_coupler,
    "mmi1x2": mb.mmi1x2,
    "ring_modulator": ring_modulator_module.ring_modulator,
}


def layers_used(device) -> set[str]:
    return {name for name in t.LAYER_INFO if not device.get_region(getattr(t.LAYER, name)).is_empty()}


def cut(device, layer, x: float) -> list[tuple[float, float]]:
    """The intervals of y (um) that a layer covers on the line x = const, from bottom to top."""
    dbu = device.kcl.dbu
    box = device.get_region(layer, merge=True).bbox()
    line = kdb.Region(kdb.Box(round(x / dbu) - 1, box.bottom - 10, round(x / dbu) + 1, box.top + 10))
    pieces = sorted((p.bbox().bottom * dbu, p.bbox().top * dbu) for p in (device.get_region(layer, merge=True) & line).each())
    return [(round(a, 3), round(b, 3)) for a, b in pieces]


def centre(port) -> tuple[float, float]:
    return float(port.center[0]), float(port.center[1])


# ---- all devices ----
@pytest.mark.parametrize("name", DEVICES)
def test_default_device_is_drc_clean(name: str):
    result = run_drc(DEVICES[name]())
    assert result.passed and not result.warnings, result.summary()


@pytest.mark.parametrize("name", DEVICES)
def test_the_kept_layout_is_the_one_the_builder_draws(name: str):
    """devices/gds/<name>.gds is what the simulations load: it must match the builder, layer by layer."""
    path = GDS / f"{name}.gds"
    assert path.exists(), f"run devices/{name}_builder.py"
    kept = kdb.Layout()
    kept.read(str(path))
    assert kept.top_cell().name == name
    device = DEVICES[name]()
    for layer_name in t.LAYER_INFO:
        layer, datatype = tuple(getattr(t.LAYER, layer_name))
        index = kept.find_layer(layer, datatype)
        on_disk = kdb.Region() if index is None else kdb.Region(kept.top_cell().begin_shapes_rec(index))
        drawn = device.get_region(getattr(t.LAYER, layer_name), merge=True)
        assert (on_disk ^ drawn).sized(-1).is_empty(), f"{layer_name} differs: run devices/{name}_builder.py"


# ---- strip waveguide ----
def test_strip_waveguide_dimensions():
    device = sw.strip_waveguide(length=15.0, radius=5.0, bend_angle=45.0, taper_length=20.0, wide_width=3.0, wide_length=10.0)
    assert layers_used(device) == {"WG"}
    start, end = centre(device.ports["o1"]), centre(device.ports["o2"])
    shift = 2 * 5.0 * (1 - math.cos(math.radians(45.0)))  # sideways shift of an S-bend of two 45 degree arcs
    reach = 2 * 5.0 * math.sin(math.radians(45.0))
    assert end[1] - start[1] == pytest.approx(-shift, abs=2e-3)
    assert end[0] - start[0] == pytest.approx(15.0 + reach + 15.0 + 20.0 + 10.0, abs=2e-3)
    assert device.ports["o1"].width == pytest.approx(0.5) and device.ports["o2"].width == pytest.approx(3.0)
    ((low, high),) = cut(device, t.WG, start[0] + 5.0)
    assert high - low == pytest.approx(0.5, abs=2e-3)
    ((low, high),) = cut(device, t.WG, end[0] - 5.0)
    assert high - low == pytest.approx(3.0, abs=2e-3)
    ((low, high),) = cut(device, t.WG, end[0] - 10.0 - 10.0)  # the middle of the taper
    assert high - low == pytest.approx((0.5 + 3.0) / 2, abs=5e-3)
    assert device.info["length_route"] == pytest.approx(30.0 + 2 * 5.0 * math.radians(45.0), abs=1e-3)


def test_strip_bend_and_taper_cells():
    assert sw.bend(radius=5.0, angle=90.0).info["length"] == pytest.approx(math.pi * 5.0 / 2, abs=2e-3)
    assert sw.bend(radius=5.0, euler=True).info["length"] > math.pi * 5.0 / 2  # an Euler bend is longer than the arc
    taper = sw.taper(length=12.0, width1=0.5, width2=2.0)
    assert taper.xsize == pytest.approx(12.0, abs=2e-3) and taper.ysize == pytest.approx(2.0, abs=2e-3)
    for kwargs in ({"radius": 8.0}, {"bend_angle": 30.0}, {"taper_length": 40.0, "wide_width": 2.0}):
        result = run_drc(sw.strip_waveguide(**kwargs))
        assert result.passed and not result.warnings, (kwargs, result.summary())


def test_strip_rejects_what_breaks_a_rule():
    with pytest.raises(ValueError, match="strip bend radius"):
        sw.strip_waveguide(radius=3.0)
    with pytest.raises(ValueError, match="strip bend radius"):
        sw.bend(radius=4.9)
    with pytest.raises(ValueError, match="minimum width"):
        sw.straight(width=0.15)


# ---- rib waveguide ----
def test_rib_waveguide_dimensions():
    device = rw.rib_waveguide(length=15.0, radius=10.0, bend_angle=45.0)
    assert layers_used(device) == {"WG", "SLAB90"}
    start, end = centre(device.ports["o1"]), centre(device.ports["o2"])
    assert end[1] - start[1] == pytest.approx(-2 * 10.0 * (1 - math.cos(math.radians(45.0))), abs=2e-3)
    x = start[0] + 5.0
    ((core_low, core_high),) = cut(device, t.WG, x)
    ((slab_low, slab_high),) = cut(device, t.SLAB90, x)
    assert core_high - core_low == pytest.approx(0.5, abs=2e-3)
    assert slab_high - slab_low == pytest.approx(t.RIB_SLAB_WIDTH, abs=2e-3)
    assert (slab_low + slab_high) / 2 == pytest.approx((core_low + core_high) / 2, abs=2e-3)  # the slab is centred on the core
    for kwargs in ({"radius": 15.0}, {"width": 0.6}, {"slab_width": 4.0}):
        result = run_drc(rw.rib_waveguide(**kwargs))
        assert result.passed and not result.warnings, (kwargs, result.summary())


def test_rib_rejects_what_breaks_a_rule():
    with pytest.raises(ValueError, match="rib bend radius"):
        rw.rib_waveguide(radius=8.0)
    with pytest.raises(ValueError, match="rib bend radius"):
        rw.bend(radius=5.0)
    with pytest.raises(ValueError, match="minimum width"):
        rw.straight(width=0.1)
    with pytest.raises(ValueError, match="must exceed the core width"):
        rw.straight(width=0.5, slab_width=0.5)


# ---- directional coupler ----
@pytest.mark.parametrize("gap", [0.2, 0.3])
def test_coupler_gap_is_the_edge_to_edge_distance(gap: float):
    device = dc.directional_coupler(gap=gap, length=12.0)
    assert layers_used(device) == {"WG"}
    (low0, high0), (low1, high1) = cut(device, t.WG, 0.0)  # the middle of the straight section
    assert low1 - high0 == pytest.approx(gap, abs=2e-3)
    assert high0 - low0 == pytest.approx(0.5, abs=2e-3) and high1 - low1 == pytest.approx(0.5, abs=2e-3)
    assert (high0 + low1) / 2 == pytest.approx(0.0, abs=2e-3)  # the gap is centred on y = 0
    for x in (-5.9, 5.9):  # the gap holds over the whole straight section
        (_, high0), (low1, _) = cut(device, t.WG, x)
        assert low1 - high0 == pytest.approx(gap, abs=2e-3)


def test_coupler_ports():
    device = dc.directional_coupler(length=12.0, port_spacing=4.0, bend_length=10.0)
    ports = {p.name: centre(p) for p in device.ports}
    assert set(ports) == {"o1", "o2", "o3", "o4"}
    half = 12.0 / 2 + 10.0
    assert ports["o1"] == pytest.approx((-half, -2.0), abs=2e-3)  # input, lower west
    assert ports["o2"] == pytest.approx((-half, 2.0), abs=2e-3)
    assert ports["o3"] == pytest.approx((half, 2.0), abs=2e-3)  # cross
    assert ports["o4"] == pytest.approx((half, -2.0), abs=2e-3)  # through: the waveguide of o1
    assert device.info["min_bend_radius"] >= t.DESIGN_RULES["strip_bend_radius"]
    for kwargs in ({"length": 0.0}, {"gap": 0.3, "length": 25.0}, {"port_spacing": 6.0, "bend_length": 15.0}):
        result = run_drc(dc.directional_coupler(**kwargs))
        assert result.passed and not result.warnings, (kwargs, result.summary())


def test_coupler_rejects_what_breaks_a_rule():
    with pytest.raises(ValueError, match="minimum space"):
        dc.directional_coupler(gap=0.15)
    with pytest.raises(ValueError, match="strip bend radius"):
        dc.directional_coupler(port_spacing=8.0, bend_length=5.0)  # S-bends too sharp
    with pytest.raises(ValueError, match="must exceed width \\+ gap"):
        dc.directional_coupler(port_spacing=0.6)


# ---- 1x2 MMI ----
def test_mmi_dimensions():
    device = mb.mmi1x2(length_mmi=6.0, width_mmi=2.5, width_taper=1.0, length_taper=10.0, gap_mmi=0.25)
    assert layers_used(device) == {"WG"}
    ((low, high),) = cut(device, t.WG, 3.0)  # inside the multimode section, which starts at x = 0
    assert (low, high) == pytest.approx((-1.25, 1.25), abs=2e-3)
    (low0, high0), (low1, high1) = cut(device, t.WG, 6.0 + 0.01)  # the wide ends of the two output tapers
    assert low1 - high0 == pytest.approx(0.25, abs=5e-3)
    assert high1 - low1 == pytest.approx(1.0, abs=5e-3) and high0 - low0 == pytest.approx(1.0, abs=5e-3)
    ports = {p.name: centre(p) for p in device.ports}
    assert ports["o1"] == pytest.approx((-10.0, 0.0), abs=2e-3)
    assert ports["o2"] == pytest.approx((16.0, 0.625), abs=2e-3)
    assert ports["o3"] == pytest.approx((16.0, -0.625), abs=2e-3)
    assert device.info["output_pitch"] == pytest.approx(1.25)
    for kwargs in ({"length_mmi": 8.0}, {"width_mmi": 3.0, "gap_mmi": 0.5}, {"length_taper": 5.0}):
        result = run_drc(mb.mmi1x2(**kwargs))
        assert result.passed and not result.warnings, (kwargs, result.summary())


def test_mmi_is_mirror_symmetric():
    device = mb.mmi1x2()
    region = device.get_region(t.WG, merge=True)
    mirrored = region.transformed(kdb.Trans(kdb.Trans.M0))  # y -> -y
    assert (region ^ mirrored).sized(-1).is_empty()


def test_mmi_rejects_what_breaks_a_rule():
    with pytest.raises(ValueError, match="minimum space"):
        mb.mmi1x2(gap_mmi=0.1)
    with pytest.raises(ValueError, match="wider than the"):
        mb.mmi1x2(width_taper=1.2, gap_mmi=0.25, width_mmi=2.5)
    with pytest.raises(ValueError, match="minimum width"):
        mb.mmi1x2(width=0.1)

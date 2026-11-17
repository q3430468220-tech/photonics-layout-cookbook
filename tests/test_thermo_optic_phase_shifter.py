"""The thermo-optic phase shifter: the layout is what its arguments say, passes the DRC, and refuses what breaks a rule.

The two trenches of the default device are 2 * trench_gap = 4 um apart, which is the minimum space of the deep
trench (gsip_technology.MIN_WIDTH_SPACE): the wall that carries the heater is as narrow as the rules allow.
"""

from __future__ import annotations

import gdsfactory as gf
import klayout.db as kdb
import numpy as np
import pytest
from test_connectivity import number, pad_nets
from test_passive_devices import cut, layers_used

import gsip_technology as t
from devices import GDS, REPO
from devices import thermo_optic_phase_shifter_builder as tops
from gsip_drc import demo_component, run_drc

DEEPTRENCH = t.LAYER.DEEPTRENCH


def device(**kwargs) -> gf.Component:
    return tops.thermo_optic_phase_shifter(**kwargs)


def centre(port) -> tuple[float, float]:
    return float(port.center[0]), float(port.center[1])


def within(a: kdb.Region, b: kdb.Region, distance: float, dbu: float) -> bool:
    """True when two regions lie closer than ``distance`` um.  One database unit is allowed: touching at the rule distance passes."""
    grown = a.sized(round(distance / dbu) - 1)
    return not (grown & b).is_empty()


# ---- the layout as a whole ----
def test_default_device_passes_the_drc_without_a_warning():
    result = run_drc(device())
    assert result.passed and not result.warnings, result.summary()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"trench_gap": None},
        {"length": 150.0, "trench_gap": 2.5},
        {"trench_gap": 2.5, "trench_width": 7.0},
        {"trench_gap": 2.5, "heater_width": 1.0},
    ],
)
def test_other_sets_of_arguments_pass_the_drc(kwargs: dict):
    result = run_drc(device(**kwargs))
    assert result.passed and not result.warnings, (kwargs, result.summary())


def test_the_device_uses_exactly_its_layers():
    assert layers_used(device()) == {"WG", "DEEPTRENCH", "HEATER", "VIA1", "M2", "VIA2", "M3", "PADOPEN"}
    assert layers_used(device(trench_gap=None)) == {"WG", "HEATER", "VIA1", "M2", "VIA2", "M3", "PADOPEN"}


def test_ports_are_the_two_optical_and_the_two_electrical_ones():
    component = device()
    assert {p.name for p in component.ports} == {"o1", "o2", "H1", "H2"}
    assert centre(component.ports["o1"]) == pytest.approx((-57.0, 0.0), abs=2e-3)
    assert centre(component.ports["o2"]) == pytest.approx((57.0, 0.0), abs=2e-3)
    assert component.ports["o1"].width == pytest.approx(0.5)
    assert centre(component.ports["H1"]) == pytest.approx((-51.0, 60.0), abs=2e-3)
    assert centre(component.ports["H2"]) == pytest.approx((51.0, 60.0), abs=2e-3)


def test_heater_is_centred_on_the_core_and_lands_at_both_ends():
    component = device()
    ((low, high),) = cut(component, t.HEATER, 0.0)  # the filament at the middle
    assert (low, high) == pytest.approx((-1.0, 1.0), abs=2e-3)  # 2 um wide, centred on y = 0
    ((core_low, core_high),) = cut(component, t.WG, 0.0)
    assert (core_low + core_high) / 2 == pytest.approx((low + high) / 2, abs=2e-3)
    for x in (-51.0, 51.0):  # the landing and its via 1
        ((low, high),) = cut(component, t.HEATER, x)
        assert high - low == pytest.approx(2.4, abs=2e-3)
        ((low, high),) = cut(component, t.VIA1, x)
        assert (low, high) == pytest.approx((-0.5, 0.5), abs=2e-3)
        ((low, high),) = cut(component, t.M2, x)  # the wire from the via and the tab of the pad: one piece
        assert low == pytest.approx(-0.8, abs=2e-3) and high == pytest.approx(20.0, abs=2e-3)


def test_trenches_lie_where_the_arguments_say():
    component = device(trench_gap=2.0, trench_width=6.0)
    assert cut(component, DEEPTRENCH, 0.0) == [(-8.0, -2.0), (2.0, 8.0)]
    assert cut(component, DEEPTRENCH, -47.9) == [(-8.0, -2.0), (2.0, 8.0)]
    assert cut(component, DEEPTRENCH, 48.5) == []  # the trenches end before the metal
    box = component.get_region(DEEPTRENCH, merge=True).bbox()
    assert box.left * component.kcl.dbu == pytest.approx(-48.0, abs=2e-3)
    assert box.right * component.kcl.dbu == pytest.approx(48.0, abs=2e-3)
    other = device(trench_gap=2.5, trench_width=7.0)
    assert cut(other, DEEPTRENCH, 0.0) == [(-9.5, -2.5), (2.5, 9.5)]


def test_no_trench_within_a_rule_distance_of_metal_or_heater():
    component = device()
    dbu = component.kcl.dbu
    trench = component.get_region(DEEPTRENCH, merge=True)
    for layer, rule in (("M2", "trench_to_metal"), ("M3", "trench_to_metal"), ("HEATER", "trench_to_heater")):
        metal = component.get_region(getattr(t.LAYER, layer), merge=True)
        assert not within(trench, metal, t.DESIGN_RULES[rule], dbu), layer
    # and the core, at the rule of the waveguide
    core = component.get_region(t.WG, merge=True)
    assert not within(trench, core, t.DESIGN_RULES["trench_to_waveguide"], dbu)


def test_removing_the_trenches_changes_nothing_else():
    with_trench, without = device(), device(trench_gap=None)
    assert with_trench.get_region(DEEPTRENCH).is_empty() is False
    assert without.get_region(DEEPTRENCH).is_empty()
    for name in t.LAYER_INFO:
        if name == "DEEPTRENCH":
            continue
        layer = getattr(t.LAYER, name)
        diff = with_trench.get_region(layer, merge=True) ^ without.get_region(layer, merge=True)
        assert diff.is_empty(), name


# ---- info against the geometry ----
def test_info_matches_the_geometry():
    component = device()
    info = component.info
    assert info["length_heater"] == 100.0
    trench = component.get_region(DEEPTRENCH, merge=True).bbox()
    along = (trench.right - trench.left) * component.kcl.dbu
    assert info["length_trenches"] == pytest.approx(along, abs=2e-3)
    assert info["length_trenches"] == pytest.approx(96.0)
    assert info["isolated_fraction"] == pytest.approx(0.96)
    assert info["heater_width"] == 2.0 and info["trench_gap"] == 2.0 and info["trench_width"] == 6.0
    ((low, high),) = cut(component, t.HEATER, 0.0)
    assert info["heater_width"] == pytest.approx(high - low, abs=2e-3)
    # the filament is 100 um long between the landings; resistance = sheet resistance x length / width
    assert info["heater_resistance"] == pytest.approx(t.HEATER_SHEET_RESISTANCE * 100.0 / 2.0, rel=1e-3)
    assert device(trench_gap=None).info["length_trenches"] == 0.0


# ---- refusals: each names the rule and the measured value ----
@pytest.mark.parametrize(
    ("kwargs", "text"),
    [
        ({"heater_width": 0.5}, "minimum width of the heater film"),
        ({"trench_gap": 1.5}, "trench_to_heater needs 1.00 um"),  # 0.50 um from the heater edge
        ({"heater_width": 0.8, "trench_gap": 1.6}, "trench_to_waveguide needs 1.50 um"),  # 1.35 um from the core edge
        ({"heater_width": 1.0, "trench_gap": 1.75}, "minimum space of the deep trench is 4.00 um"),  # a wall of 3.5 um
        ({"trench_width": 4.0}, "minimum width of the deep trench, 5.0 um"),
        ({"length": 8.0}, "at least 9.0 um"),  # 4 um of trench between the landings
        ({"trench_width": 9.0}, "trench_to_metal needs 2.00 um"),  # 1 um from the metal 2 tab
        ({"width": 0.1}, "minimum width of the waveguide layer"),
        ({"length": 0.0}, "must be positive"),
    ],
)
def test_arguments_that_break_a_rule_are_refused(kwargs: dict, text: str):
    with pytest.raises(ValueError, match=text):
        device(**kwargs)


def test_the_refusals_use_the_rule_values_of_the_technology_file():
    assert t.DESIGN_RULES["trench_to_heater"] == 1.0
    assert t.DESIGN_RULES["trench_to_metal"] == 2.0
    assert t.DESIGN_RULES["trench_to_waveguide"] == 1.5
    assert t.MIN_WIDTH_SPACE["DEEPTRENCH"] == (5.0, 4.0)
    # the default device stands on the narrowest wall the rules allow, and its trench is as close to the film as allowed
    wall, to_film = 2 * tops.TRENCH_GAP, tops.TRENCH_GAP - tops.HEATER_WIDTH / 2
    assert wall == pytest.approx(t.MIN_WIDTH_SPACE["DEEPTRENCH"][1])
    assert to_film == pytest.approx(t.DESIGN_RULES["trench_to_heater"])


# ---- the pads and the heater film ----
def test_the_two_pads_are_one_net_through_the_heater_film():
    nets = pad_nets(device())
    assert number(nets["H1"]) == number(nets["H2"])
    assert {name for name in nets["H1"] if not name.startswith("net")} == {"HEATER", "M2", "M3"}


def test_without_the_heater_film_the_pads_are_two_nets():
    component = device()
    flat = gf.Component()
    ref = flat << component
    flat.add_ports(ref.ports)
    flat.flatten()
    flat.remove_layers([t.HEATER])
    nets = pad_nets(flat)
    assert number(nets["H1"]) != number(nets["H2"])


# ---- the kept layout and the DRC of the planted violations ----
def test_the_kept_layout_is_the_one_the_builder_draws():
    """devices/gds/thermo_optic_phase_shifter.gds is what the simulations load: it must match the builder, layer by layer."""
    path = GDS / "thermo_optic_phase_shifter.gds"
    assert path.exists(), "run devices/thermo_optic_phase_shifter_builder.py"
    kept = kdb.Layout()
    kept.read(str(path))
    assert kept.top_cell().name == "thermo_optic_phase_shifter"
    drawn_device = device()
    for name in t.LAYER_INFO:
        layer, datatype = tuple(getattr(t.LAYER, name))
        index = kept.find_layer(layer, datatype)
        on_disk = kdb.Region() if index is None else kdb.Region(kept.top_cell().begin_shapes_rec(index))
        drawn = drawn_device.get_region(getattr(t.LAYER, name), merge=True)
        assert (on_disk ^ drawn).sized(-1).is_empty(), f"{name} differs: run devices/thermo_optic_phase_shifter_builder.py"


def test_the_kept_results_are_those_of_the_device_the_builder_draws():
    """The chapter quotes the kept simulation results: they must belong to the dimensions the builder draws now."""
    info = device().info
    chapter = REPO / "lumerical_simulations" / "thermo_optic_phase_shifter"
    heat = np.load(chapter / "1_heat_cross_section" / "heat.npz")
    row = list(heat["case_name"]).index("device")
    assert float(heat["case_trench_gap_um"][row]) == pytest.approx(info["trench_gap"])
    assert float(heat["case_trench_width_um"][row]) == pytest.approx(info["trench_width"])
    assert float(heat["case_heater_width_um"][row]) == pytest.approx(info["heater_width"])
    phase = np.load(chapter / "2_phase_shift" / "phase.npz")
    assert float(phase["length_um"]) == pytest.approx(info["length_heater"])
    for results in (heat, phase):
        assert float(results["isolated_fraction"]) == pytest.approx(info["isolated_fraction"])
        assert float(results["resistance_ohm"]) == pytest.approx(info["heater_resistance"])
    # steps 3 and 4 start from the numbers of steps 1 and 2: a rerun of one step alone would leave them behind
    switching = np.load(chapter / "3_switching_time" / "switching.npz")
    own = list(switching["case_name"]).index("device")
    assert float(switching["case_P_pi_mW"][own]) == pytest.approx(float(phase["P_pi_mW"][0]))
    neighbour = np.load(chapter / "4_neighbour" / "neighbour.npz")
    assert float(neighbour["P_pi_mW"]) == pytest.approx(float(phase["P_pi_mW"][1]))


def test_the_drc_finds_each_planted_violation_of_the_trench_rules():
    result = run_drc(demo_component())
    rules = " | ".join(result.errors)
    for fragment in (
        "DEEPTRENCH: narrower than 5.0 um",
        "DEEPTRENCH: space smaller than 4.0 um",
        "deep trench under the heater film",
        "heater film closer than 1.0 um to a deep trench",
        "deep trench under metal 2",
        "metal 1 closer than 2.0 um to a deep trench",
        "metal 3 closer than 2.0 um to a deep trench",
    ):
        assert fragment in rules, fragment
    assert any("deep trench closer than 1.5 um to a waveguide core" in warning for warning in result.warnings)

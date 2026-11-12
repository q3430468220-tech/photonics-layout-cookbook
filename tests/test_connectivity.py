"""The nets of the device: every pad reaches what it should, and nothing is shorted.

A design-rule check does not see a wrong connection. This test traces the conductors of the layout through
the vias listed in ``gsip_technology.LAYER_CONNECTIVITY`` and looks at what each pad is connected to.
"""

from __future__ import annotations

import klayout.db as kdb
import pytest

import gsip_technology as t
import rm_builder as rm

CONDUCTORS = ("NPP", "PPP", "M1", "HEATER", "M2", "M3")


def trace(device) -> tuple[dict[tuple[str, int], int], dict[str, list[kdb.Region]]]:
    """Net number of every conductor shape (layer name, index), and the shapes themselves."""
    shapes = {name: [kdb.Region(p) for p in device.get_region(getattr(t.LAYER, name), merge=True).each()] for name in CONDUCTORS}
    parent = {(name, i): (name, i) for name, regions in shapes.items() for i in range(len(regions))}

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for lower, via, upper in t.LAYER_CONNECTIVITY:
        for polygon in device.get_region(getattr(t.LAYER, via), merge=True).each():
            cut = kdb.Region(polygon)
            touched = [(name, i) for name in (lower, upper) for i, r in enumerate(shapes[name]) if not (r & cut).is_empty()]
            for node in touched[1:]:
                parent[find(node)] = find(touched[0])
    roots = sorted({find(node) for node in parent})
    return {node: roots.index(find(node)) for node in parent}, shapes


def pad_nets(device) -> dict[str, set[str]]:
    """For every pad: the conductor layers that its net contains."""
    net_of, shapes = trace(device)
    dbu = device.kcl.dbu
    out = {}
    for port in device.ports:
        if port.name[0] not in "GSH":
            continue
        x, y = (round(v / dbu) for v in port.dcenter)
        probe = kdb.Region(kdb.Box(x - 5, y - 5, x + 5, y + 5))
        (pad,) = [i for i, r in enumerate(shapes["M3"]) if not (r & probe).is_empty()]
        net = net_of[("M3", pad)]
        out[port.name] = {name for (name, _), n in net_of.items() if n == net}
        out[port.name].add(f"net{net}")
    return out


def layers(net: set[str]) -> set[str]:
    return {name for name in net if not name.startswith("net")}


def number(net: set[str]) -> str:
    (name,) = [name for name in net if name.startswith("net")]
    return name


@pytest.mark.parametrize("p_inside", [False, True])
def test_pads_reach_the_junction_and_the_heater(p_inside: bool):
    nets = pad_nets(rm.ring_modulator(p_inside=p_inside))
    inside, outside = ("PPP", "NPP") if p_inside else ("NPP", "PPP")
    assert layers(nets["S"]) == {inside, "M1", "M2", "M3"}  # signal: the disc inside the ring
    for ground in ("G1", "G2"):
        assert layers(nets[ground]) == {outside, "M1", "M2", "M3"}  # ground: the arc outside the ring
    for heater in ("H1", "H2"):
        assert layers(nets[heater]) == {"HEATER", "M2", "M3"}


def test_three_nets_and_no_short():
    nets = pad_nets(rm.ring_modulator())
    assert number(nets["G1"]) == number(nets["G2"])  # both ground pads meet on the outer arc
    assert number(nets["H1"]) == number(nets["H2"])  # the heater film joins its two pads
    assert len({number(nets[name]) for name in ("S", "G1", "H1")}) == 3


def test_every_via_lands_on_both_levels():
    """A via that touches only one of its two levels connects nothing."""
    device = rm.ring_modulator()
    for _lower, via, upper in t.LAYER_CONNECTIVITY:
        cuts = device.get_region(getattr(t.LAYER, via), merge=True)
        top = device.get_region(getattr(t.LAYER, upper), merge=True)
        assert (cuts - top).is_empty(), (via, upper)
    bottoms = {}
    for lower, via, _ in t.LAYER_CONNECTIVITY:
        bottoms.setdefault(via, kdb.Region())
        bottoms[via] += device.get_region(getattr(t.LAYER, lower), merge=True)
    for via, below in bottoms.items():
        assert (device.get_region(getattr(t.LAYER, via), merge=True) - below.merged()).is_empty(), via

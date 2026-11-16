"""The data-flow figure of chapter 4 shows the connections that the step scripts really have.

The figure is drawn from a table in its script.  These tests read the step scripts and compare: a step reads an
earlier step when its script names that step's folder.  A connection that is drawn and not read, or read and not
drawn, fails here.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RING = REPO / "lumerical_simulations" / "ring_modulator"
FOLDER = re.compile(r'"(\d)_[a-z_]+"')  # a step folder, as the scripts write it: "3_charge_profile"


def figure():
    path = RING / "figures" / "fig_data_flow.py"
    spec = importlib.util.spec_from_file_location("figure_data_flow", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_by_the_scripts() -> set[tuple[int, int]]:
    """(earlier step, step that reads it), from the folders each step script names besides its own."""
    connections = set()
    for script in sorted((RING / "scripts").glob("*.py")):
        text = script.read_text(encoding="utf-8")
        own = re.search(r'OUT = step_dir\("(\d)_', text)
        if own is None:  # common.py: not a step
            continue
        for source in set(FOLDER.findall(text)) - {own.group(1)}:
            connections.add((int(source), int(own.group(1))))
    return connections


def test_the_figure_draws_what_the_scripts_read():
    drawn = {(source, target) for source, target, _ in figure().FLOW}
    assert drawn == read_by_the_scripts()
    assert len(drawn) == len(figure().FLOW), "a connection is listed twice"
    assert all(source < target for source, target in drawn), "no step reads a later one"


def test_the_figure_names_the_steps_of_the_chapter():
    module = figure()
    chapter = (RING / "README.md").read_text(encoding="utf-8")
    assert [number for number, *_ in module.STEPS] == list(range(7))
    for number, name, *_ in module.STEPS:
        assert len(list(RING.glob(f"{number}_*"))) == 1, f"one folder for step {number}"
        assert f"Step {number}. {name}" in chapter, f"the chapter calls step {number} by another name"
    assert {target for _, target, _ in module.FLOW} == set(module.READERS)

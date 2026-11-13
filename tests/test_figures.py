"""Every figure of the tutorial is redrawn from the result data kept in the repository; no Lumerical is needed."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

import figstyle as fs

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((REPO / "lumerical_simulations" / "ring_modulator" / "figures").glob("fig*.py"))


def test_all_figure_scripts_are_found():
    names = {script.stem for script in SCRIPTS}
    assert {
        "fig0_layer_builder",
        "fig1_coupling",
        "fig2_passive",
        "fig3_charge",
        "fig4_heat",
        "fig5_active",
        "fig6_circuit",
    } <= names


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.stem)
def test_figure_is_redrawn(script: Path, tmp_path: Path, monkeypatch):
    written = []

    def save(fig, path, pdf: bool = False) -> Path:  # the signature of figstyle.save; writes to the test folder
        out = tmp_path / Path(path).name
        fig.savefig(out, dpi=100)
        plt.close(fig)
        written.append(out)
        return out

    monkeypatch.setattr(fs, "save", save)
    monkeypatch.setattr(sys, "argv", [str(script)])
    monkeypatch.syspath_prepend(str(script.parent))
    importlib.import_module(script.stem).main()
    assert len(written) == 1
    assert written[0].stat().st_size > 10_000


def test_every_figure_has_its_image_in_the_repository():
    for script in SCRIPTS:
        assert (script.parent / f"{script.stem}.png").exists(), script.stem

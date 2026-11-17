"""Every figure of the tutorials is redrawn from the result data kept in the repository; no Lumerical is needed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

import figstyle as fs

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((REPO / "lumerical_simulations").glob("*/figures/fig*.py"))
EXPECTED = {
    "ring_modulator": {
        "fig0_layer_builder",
        "fig1_coupling",
        "fig2_passive",
        "fig3_charge",
        "fig4_heat",
        "fig5_active",
        "fig6_circuit",
        "fig_data_flow",
    },
    "strip_waveguide": {"fig1_modes", "fig2_taper"},
    "rib_waveguide": {"fig1_modes"},
    "directional_coupler": {"fig1_supermodes", "fig2_coupling_length", "fig3_coupler"},
    "mmi1x2": {"fig1_mmi_length", "fig2_mmi_fdtd"},
    "thermo_optic_phase_shifter": {"fig1_heat", "fig2_phase", "fig3_switching", "fig4_neighbour"},
}


def name(script: Path) -> str:
    return f"{script.parents[1].name}/{script.stem}"


def test_all_figure_scripts_are_found():
    found: dict[str, set[str]] = {}
    for script in SCRIPTS:
        found.setdefault(script.parents[1].name, set()).add(script.stem)
    for device, figures in EXPECTED.items():
        assert figures <= found.get(device, set()), (device, figures - found.get(device, set()))


@pytest.mark.parametrize("script", SCRIPTS, ids=name)
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
    # two devices may have a figure script of the same name: load each one under its own module name
    spec = importlib.util.spec_from_file_location(f"figure_{script.parents[1].name}_{script.stem}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    assert len(written) == 1
    assert written[0].stat().st_size > 10_000


def test_every_figure_has_its_image_in_the_repository():
    for script in SCRIPTS:
        assert (script.parent / f"{script.stem}.png").exists(), name(script)

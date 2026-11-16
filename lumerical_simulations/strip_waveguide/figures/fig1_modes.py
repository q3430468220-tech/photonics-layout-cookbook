"""Figure 1 - MODE: the strip waveguide guides TE0 tightly, bends at 5 um without loss, and is single-mode below 0.5 um.

    a  TE0 intensity on the cross-section, with n_eff, n_g and the share of the intensity inside the core
    b  TM0 intensity on the same scale
    c  n_eff of TE0 against wavelength, with the group index
    d  loss of a 90 degree bend against the radius: the two junctions with the straights, and radiation
    e  n_eff of TE0, TM0 and TE1 against the core width, with the index of the oxide

Reads 1_waveguide_modes/strip_modes.npz.

    python fig1_modes.py            ->  figures/fig1_modes.png
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/strip_waveguide/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import NEFF, NG, fs  # noqa: E402

DATA = ROOT / "1_waveguide_modes" / "strip_modes.npz"
WINDOW_Y, WINDOW_Z = (-1.2, 1.2), (-0.42, 0.86)  # um, panels a and b; room above the core for the three lines of the note


def main() -> None:
    d = panels.load(DATA)
    width, lam = float(d["width"]), float(d["lam"]) * 1000
    fig, axes = fs.mosaic(fs.DOUBLE, 92, [["a", "b", "c"], ["d", "e", "e"]], gridspec_kw=dict(width_ratios=[1, 1, 0.95]))

    def outline(ax):
        panels.strip_outline(ax, width)

    share = f"{100 * panels.core_share(d['y'], d['z'], d['E'], width):.0f} % of |E|² in the core"
    text = f"TE0, {lam:.0f} nm\n{NEFF} = {float(d['neff']):.3f},  {NG} = {float(d['ng']):.3f}\n{share}"
    image = panels.mode_map(axes["a"], d["y"], d["z"], d["E"], WINDOW_Y, WINDOW_Z, text, outline)
    share = f"{100 * panels.core_share(d['y'], d['z'], d['tm_E'], width):.0f} % of |E|² in the core"
    text = f"TM0\n{NEFF} = {float(d['tm_neff']):.3f},  {NG} = {float(d['tm_ng']):.3f}\n{share}"
    panels.mode_map(axes["b"], d["y"], d["z"], d["tm_E"], WINDOW_Y, WINDOW_Z, text, outline)
    axes["b"].set_ylabel("")
    fs.colorbar_beside(axes["b"], image, "|E|² (normalised)", ticks=[0, 0.5, 1])

    panels.dispersion(axes["c"], d, (2.36, 2.54))

    panels.bend_loss(axes["d"], d, (5e-6, 0.2))
    axes["d"].set_xlim(2.5, 10.5)
    design = float(d["radius"])
    k = int(abs(d["bend_radii"] - design).argmin())
    fs.note(
        axes["d"],
        f"design R = {design:.0f} µm\n{2 * float(d['bend_junction_dB'][k]):.3f} dB",
        (design + 0.25, 6e-4),
        ha="left",
        va="center",
    )

    series = {"TE0": d["width_te0"], "TM0": d["width_tm0"], "TE1": d["width_te1"]}
    panels.width_sweep(axes["e"], d["widths"], series, float(d["n_ox"]), "oxide", width, (1.38, 2.85))
    guided = d["widths"][~(d["width_te1"] != d["width_te1"])]
    fs.note(
        axes["e"],
        f"one TE mode up to {1000 * d['widths'][d['width_te1'] != d['width_te1']].max():.0f} nm;\nTE1 guided from {1000 * guided.min():.0f} nm",
        (0.03, 0.96),
        ha="left",
        va="top",
        transform=axes["e"].transAxes,
    )
    fs.note(axes["e"], f"design {width * 1000:.0f} nm", (width * 1000 + 8, 2.05), ha="left", va="center")

    for letter in "abcde":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig1_modes.png")


if __name__ == "__main__":
    main()

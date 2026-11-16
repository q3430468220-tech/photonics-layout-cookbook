"""Figure 1 - MODE: the rib waveguide guides TE0 on its slab, needs a 10 um bend, and is single-mode below 0.5 um.

    a  TE0 intensity on the cross-section, with n_eff and n_g
    b  the same mode in a bend of the design radius: it moves outwards
    c  n_eff of TE0 against wavelength, with the group index
    d  loss of a 90 degree bend against the radius: the two junctions with the straights, and radiation
    e  n_eff of TE0 and TE1 against the core width, with the index of the slab mode

Reads 1_waveguide_modes/rib_modes.npz.

    python fig1_modes.py            ->  figures/fig1_modes.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/rib_waveguide/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import NEFF, NG, fs  # noqa: E402

DATA = ROOT / "1_waveguide_modes" / "rib_modes.npz"
WINDOW_Y, WINDOW_Z = (-1.5, 1.5), (-0.5, 0.75)  # um, panels a and b


def main() -> None:
    d = panels.load(DATA)
    width, lam, radius = float(d["width"]), float(d["lam"]) * 1000, float(d["radius"])
    fig, axes = fs.mosaic(fs.DOUBLE, 92, [["a", "b", "c"], ["d", "e", "e"]], gridspec_kw=dict(width_ratios=[1, 1, 0.95]))

    def outline(ax):
        fs.rib_outline(ax, width, float(d["t_si"]), float(d["t_slab"]), float(d["slab_width"]), color=fs.INK, lw=0.5)

    text = f"TE0, {lam:.0f} nm\n{NEFF} = {float(d['neff']):.3f},  {NG} = {float(d['ng']):.3f}"
    image = panels.mode_map(axes["a"], d["y"], d["z"], d["E"], WINDOW_Y, WINDOW_Z, text, outline)
    k = int(np.argmin(np.abs(d["bend_radii"] - radius)))
    shift = abs(float(d["bend_shift_nm"][k]))
    text = f"bent, R = {radius:.0f} µm\nthe mode moves {shift:.0f} nm outwards"
    panels.mode_map(axes["b"], d["y"], d["z"], d["bend_E"], WINDOW_Y, WINDOW_Z, text, outline)
    axes["b"].plot([0.0, 0.0], [WINDOW_Z[0], 0.42], color=fs.MUTED, lw=0.5, zorder=3)  # the middle of the core
    axes["b"].set_ylabel("")
    fs.colorbar_beside(axes["b"], image, "|E|² (normalised)", ticks=[0, 0.5, 1])

    panels.dispersion(axes["c"], d, (2.50, 2.64))

    panels.bend_loss(axes["d"], d, (5e-6, 1.0))
    axes["d"].set_xlim(4, 21)
    fs.note(
        axes["d"],
        f"design R = {radius:.0f} µm\n{2 * float(d['bend_junction_dB'][k]):.3f} dB",
        (radius + 0.4, 2e-3),
        ha="left",
        va="center",
    )

    series = {"TE0": d["width_te0"], "TE1": d["width_te1"]}
    slab_label = f"TE0 mode of the {float(d['t_slab']) * 1000:.0f} nm slab"
    panels.width_sweep(axes["e"], d["widths"], series, float(d["n_slab"]), slab_label, width, (2.05, 2.80))
    te1 = d["width_te1"]
    guided, missing = d["widths"][np.isfinite(te1)], d["widths"][~np.isfinite(te1)]
    above = float(te1[np.isfinite(te1)][0] - d["n_slab"])
    fs.note(
        axes["e"],
        f"one TE mode up to {1000 * missing.max():.0f} nm;\nTE1 guided from {1000 * guided.min():.0f} nm, {above:.3f} above the slab mode",
        (0.03, 0.96),
        ha="left",
        va="top",
        transform=axes["e"].transAxes,
    )
    fs.note(axes["e"], f"design {width * 1000:.0f} nm", (width * 1000 + 8, 2.40), ha="left", va="center")

    for letter in "abcde":
        fs.panel_label(axes[letter], letter)
    fs.save(fig, ROOT / "figures" / "fig1_modes.png")


if __name__ == "__main__":
    main()

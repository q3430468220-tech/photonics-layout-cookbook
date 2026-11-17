"""Figure 1 - HEAT: the trenches keep the heat in the wall of oxide under the heater.

    a  temperature rise at 10 mW without trenches: the heat spreads sideways in the oxide on its way down
    b  the same with the trenches of the device, on the same colour scale: the heat can only go down through the wall
    c  rise of the core per milliwatt against the trench gap, with the one-dimensional estimate and the limit of the rules
    d  rise of the core and of the film against the power, with and without trenches

Reads 1_heat_cross_section/heat.npz; the geometry comes from gsip_technology and from the builder of the device.

    python fig1_heat.py            ->  figures/fig1_heat.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.tri import Triangulation

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/thermo_optic_phase_shifter/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs, t  # noqa: E402

from devices import thermo_optic_phase_shifter_builder as tops  # noqa: E402

DATA = ROOT / "1_heat_cross_section" / "heat.npz"
T_AMBIENT = 300.0  # K: the substrate is held at this temperature
WIN_Y, WIN_Z = (-11.0, 11.0), (-2.9, 5.5)  # um: the window of the two maps
P_MAP = 10.0  # mW: the power of the two maps


def tint(name: str, amount: float) -> tuple:
    """A material colour mixed into the surface of the figure by ``amount``."""
    surface = np.array(to_rgb(fs.SURFACE))
    return tuple(surface + amount * (np.array(to_rgb(fs.MATERIAL_COLORS[name])) - surface))


def case(d: dict, name: str) -> int:
    return list(d["case_name"]).index(name)


def panel_map(ax, d: dict, which: str, vmax: float, title: str):
    """Temperature rise of one cross-section at the power of the maps, with the structures outlined."""
    tri = Triangulation(d[f"{which}_map_y_um"], d[f"{which}_map_z_um"], triangles=d[f"{which}_map_triangles"])
    rise = d[f"{which}_map_T"].astype(float) - T_AMBIENT
    image = ax.tripcolor(tri, rise, cmap=fs.CMAP_HEAT, vmin=0, vmax=vmax, shading="gouraud", rasterized=True)
    substrate = tint("substrate", 0.35)
    fs.box(ax, WIN_Y[0], WIN_Y[1], WIN_Z[0] - 1, -t.T_BOX, facecolor=substrate, edgecolor="none", zorder=0)
    ax.plot(WIN_Y, [-t.T_BOX, -t.T_BOX], color=fs.MUTED, lw=0.5, zorder=2)
    trenches = which == "device"
    if trenches:
        for side in (+1, -1):
            y0, y1 = sorted((side * tops.TRENCH_GAP, side * (tops.TRENCH_GAP + tops.TRENCH_WIDTH)))
            fs.box(ax, y0, y1, WIN_Z[0] - 1, WIN_Z[1] + 1, facecolor=fs.SURFACE, edgecolor=fs.MUTED, zorder=3)
            fs.note(ax, "air", ((y0 + y1) / 2, 2.2), ha="center")
    fs.box(ax, -tops.WIDTH / 2, tops.WIDTH / 2, 0.0, t.T_SI, edgecolor=fs.INK, lw=0.5, zorder=4)
    half = tops.HEATER_WIDTH / 2
    z_film = t.Z_HEATER + t.T_HEATER
    fs.box(ax, -half, half, t.Z_HEATER, z_film, edgecolor=fs.INK, lw=0.5, zorder=4)
    ax.set_xlim(*WIN_Y)
    ax.set_ylim(*WIN_Z)
    fs.image_axes(ax, "y (µm)", "z (µm)")
    ax.set_xticks(np.arange(-10, 11, 5))
    ax.set_yticks(np.arange(-2, 6, 2))
    if not trenches:  # the labels stand in the panel that has room for them
        fs.note(ax, "TiN film", (-half, z_film), xytext=(-5.2, 3.0), ha="right")
        fs.note(ax, "silicon core", (-tops.WIDTH / 2, t.T_SI / 2), xytext=(-5.2, 0.9), ha="right")
        fs.note(ax, "oxide", (WIN_Y[1] - 0.5, 4.7), ha="right")
        fs.note(ax, "silicon substrate, held at 300 K", (WIN_Y[0] + 0.4, (WIN_Z[0] - t.T_BOX) / 2), ha="left")
    fs.panel_title(ax, title)
    return image


def panel_gap(ax, d: dict) -> None:
    """Rise of the core per milliwatt against the trench gap."""
    group, gaps = d["case_group"], d["case_trench_gap_um"]
    rows = [i for i in range(len(gaps)) if (group[i] == "b" or d["case_name"][i] == "device") and not np.isnan(gaps[i])]
    rows.sort(key=lambda i: gaps[i])
    x, y = gaps[rows], d["case_core_K_per_mW"][rows]
    none = float(d["case_core_K_per_mW"][case(d, "reference")])
    closest = float(tops.TRENCH_GAP)  # the default of the builder is the closest gap the rules allow for its film
    device = case(d, "device")
    own = float(d["case_core_K_per_mW"][device])
    wall = np.linspace(1.5, 10.5, 200)
    one_d = float(d["case_eta_1D_Kum"][device]) * closest / wall / tops.LENGTH  # the estimate goes as 1 / gap
    ax.axvspan(1.2, closest, color=fs.HAIRLINE, alpha=0.35, lw=0)
    ax.axhline(none, color=fs.MUTED, lw=0.6, ls=(0, (4, 3)))
    ax.plot(wall, one_d, color=fs.MUTED, lw=0.7)
    ax.plot(x, y, color=fs.BLUE, lw=1.0, zorder=2)
    allowed = x >= closest - 1e-9
    ax.plot(x[allowed], y[allowed], "o", color=fs.BLUE, ms=4, zorder=3)
    ax.plot(x[~allowed], y[~allowed], "o", mfc=fs.SURFACE, mec=fs.BLUE, mew=0.8, ms=4, zorder=3)
    ax.plot(closest, own, "o", mfc="none", mec=fs.INK, ms=8, mew=0.6, zorder=4)
    ax.set_xlim(1.2, 10.5)
    ax.set_ylim(0, 5)
    ax.set_xticks([2, 4, 6, 8, 10])
    ax.set_xlabel("trench gap: centre line to the inner edge of a trench (µm)")
    ax.set_ylabel("rise of the core (K/mW)")
    fs.note(ax, f"device: {own:.2f} K/mW, {own / none:.2f} times the rise without trenches", (closest + 0.35, own + 0.25))
    fs.note(ax, f"no trenches: {none:.2f} K/mW", (10.4, none - 0.12), ha="right", va="top")
    fs.note(ax, "one-dimensional wall", (5.6, float(np.interp(5.6, wall, one_d)) - 0.1), ha="right", va="top")
    fs.note(ax, "closer than\nthe rules allow", (1.28, 0.25), ha="left", va="bottom")


def panel_power(ax, d: dict) -> None:
    """Rise of the core and of the film against the heater power, for the device and for the reference."""
    p = d["powers_mW"]
    x = np.array([0.0, p.max()])
    series = (
        ("device", "film", fs.ORANGE, "-", "film, with trenches"),
        ("device", "core", fs.BLUE, "-", "core, with trenches"),
        ("reference", "film", fs.ORANGE, (0, (4, 3)), "film, no trenches"),
        ("reference", "core", fs.BLUE, (0, (4, 3)), "core, no trenches"),
    )
    for which, part, color, style, label in series:
        rise = d[f"{which}_{part}_dT"]
        slope = float(np.sum(p * rise) / np.sum(p * p))  # the line through the origin, as in the summary
        ax.plot(x, slope * x, color=color, lw=1.0, ls=style, zorder=2)
        ax.plot(p, rise, "o", color=color, ms=3.5, zorder=3)
        ax.text(p.max() * 1.03, slope * p.max(), f"{label}\n{slope:.2f} K/mW", fontsize=6, va="center", color=fs.INK)
    ax.set_xlim(0, p.max() * 1.62)
    ax.set_ylim(0, 260)
    ax.set_xticks(np.arange(0, p.max() + 1, 10))
    ax.set_xlabel("heater power (mW)")
    ax.set_ylabel("temperature rise (K)")
    balance = float(np.max(np.abs(d["case_balance_pct_at_Pref"])))
    fs.note(ax, f"energy balance within {balance:.2f} % in every run", (0.03, 0.96), va="top", transform=ax.transAxes)


def main() -> None:
    d = panels.load(DATA)
    vmax = float(d["device_map_T"].max() - T_AMBIENT)  # both maps on the scale of the hotter one
    fig, axes = fs.mosaic(fs.DOUBLE, 118, [["a", "b"], ["c", "d"]], height_ratios=[1.0, 1.25])
    panel_map(axes["a"], d, "reference", vmax, f"without trenches, {P_MAP:.0f} mW")
    image = panel_map(axes["b"], d, "device", vmax, f"with trenches, {P_MAP:.0f} mW")
    fs.colorbar_beside(axes["b"], image, "temperature rise (K)", width=0.025, pad=0.025)
    panel_gap(axes["c"], d)
    panel_power(axes["d"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig1_heat.png"))


if __name__ == "__main__":
    main()

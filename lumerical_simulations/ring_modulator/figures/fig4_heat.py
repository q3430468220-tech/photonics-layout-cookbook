"""Figure 4 - HEAT: how the TiN heater warms the waveguide, and how fast.

    a  temperature rise at 10 mW across the device (y across the ring, z up), with the structures outlined
    b  vertical profile of the rise through the waveguide centre (y = 0), with the layers
    c  rise of the core and of the heater film versus power, the core without the electrodes, and the energy balance
    d  transient of the core rise after the heater is switched on, normalised to its final value

Reads 4_heat_profile/heater_heat.npz; the geometry comes from gsip_technology and rm_builder.
The transient and the run without electrodes must be in the file (heat_profile.py without --no-transient, --no-bare).

    python fig4_heat.py            ->  figures/fig4_heat.png
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.patches import Rectangle
from matplotlib.tri import LinearTriInterpolator

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
sys.path.insert(0, str(ROOT.parents[1]))
import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402
import rm_builder as rm  # noqa: E402

HEAT = ROOT / "4_heat_profile"
T_AMBIENT = 300.0  # K; the substrate is held at this temperature
CORE_WIDTH = 0.5  # um; the rib core of gsip_technology.rib
RADIUS = float(inspect.signature(rm.ring_modulator).parameters["radius"].default)  # um; the ring centre is this far in y
WIN_Y, WIN_Z = (-9.0, 9.0), (-3.0, 4.2)  # um; window of the map and of the profile
TAU_LEVEL = 1 - np.exp(-1)  # the time constant: the rise reaches this fraction of its final value after one tau


def load() -> dict:
    """The heat result: the map as a triangulation, the transient, and the device numbers."""
    path = HEAT / "heater_heat.npz"
    if not path.exists():
        raise SystemExit("run the heater heat simulation first")
    with np.load(path) as npz:
        d = {key: npz[key] for key in npz.files}
    if "transient_t" not in d or "tau" not in d:
        raise SystemExit("the transient run is missing from heater_heat.npz: run heat_profile.py without --no-transient")
    if "bare_dT_dP" not in d:
        raise SystemExit(
            "the run without metal 1 and vias is missing from heater_heat.npz: run heat_profile.py without --no-bare"
        )
    d["rise"] = d["T_map"].astype(float) - T_AMBIENT
    d["tri"] = fs.triangulation(d["T_y"], d["T_z"], d["T_elements"])
    return d


def slope_through_origin(p, dT) -> float:
    """Least-squares slope (K/mW) of a line through the origin: sum(P dT) / sum(P^2), as in heat_profile.py."""
    p, dT = np.asarray(p, dtype=float), np.asarray(dT, dtype=float)
    return float(np.sum(p * dT) / np.sum(p * p))


def derived(d: dict) -> dict:
    """Numbers that appear as text: slopes, electrode cost, transient times, operating point, energy balance."""
    p = d["powers_mW"]
    time_us = d["transient_t"] * 1e6
    norm = d["transient_core_dT"] / d["transient_core_dT"][-1]

    def crossing(level: float) -> float:
        i = int(np.argmax(norm >= level))
        return float(np.interp(level, norm[i - 1 : i + 1], time_us[i - 1 : i + 1]))

    core_slope = slope_through_origin(p, d["core_dT"])
    bare_slope = float(d["bare_dT_dP"])
    rise_us = float(d["t_rise"]) * 1e6
    peak = float(d["rise"].max())
    return dict(
        core_slope=core_slope,
        bare_slope=bare_slope,
        heater_slope=slope_through_origin(p, d["heater_dT"]),
        loss_pct=100 * (1 - core_slope / bare_slope),
        t_levels=[crossing(0.10), crossing(TAU_LEVEL), crossing(0.90)],
        tau_us=float(d["tau"]) * 1e6,
        rise_us=rise_us,
        bw_khz=0.35 / (rise_us * 1e-6) / 1e3,
        peak=peak,
        x_max=float(np.ceil(1.1 * peak / 10) * 10),  # K, right edge of the profile
        r_ohm=float(d["R_heater"]),
        v_volt=float(d["V_reference"]),
        i_ma=float(d["V_reference"]) / float(d["R_heater"]) * 1e3,
        p_ref=float(d["P_reference_mW"]),
        p_sink_mw=float(d["P_sink_mW"]) if "P_sink_mW" in d else None,  # the energy balance, when step 4 wrote it
    )


def tint(name: str, amount: float) -> tuple:
    """A material colour mixed into white by ``amount``: the light bands of the layers."""
    return tuple(1 - amount * (1 - np.array(to_rgb(fs.MATERIAL_COLORS[name]))))


def layers() -> list:
    """Layers of the cross-section at y = 0: label, z bottom, z top, band colour, side of the label."""
    z_heater = t.Z_HEATER + t.T_HEATER
    return [
        ("silicon substrate (300 K)", WIN_Z[0], -t.T_BOX, tint("substrate", 0.35), "right"),
        ("buried oxide", -t.T_BOX, 0.0, fs.MATERIAL_COLORS["oxide"], "right"),
        ("core", 0.0, t.T_SI, tint("silicon", 0.25), "left"),
        ("oxide", t.T_SI, t.Z_HEATER, fs.MATERIAL_COLORS["oxide"], "left"),
        ("heater", t.Z_HEATER, z_heater, tint("tin", 0.35), "left"),
        ("oxide", z_heater, WIN_Z[1], fs.MATERIAL_COLORS["oxide"], "left"),
    ]


def plain_axes(ax, xlabel: str, ylabel: str) -> None:
    """A line panel: labelled axes with the left and bottom spines only."""
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def panel_map(ax, d: dict) -> None:
    """Temperature rise at the reference power, with the structures outlined and labelled."""
    image = ax.tripcolor(d["tri"], d["rise"], cmap=fs.CMAP_HEAT, vmin=0, vmax=d["rise"].max(), shading="gouraud", rasterized=True)
    ax.add_patch(
        Rectangle(
            (WIN_Y[0], WIN_Z[0]),
            WIN_Y[1] - WIN_Y[0],
            -t.T_BOX - WIN_Z[0],
            facecolor=tint("substrate", 0.35),
            edgecolor="none",
            zorder=0,
        )
    )
    ax.set_xlim(*WIN_Y)
    ax.set_ylim(*WIN_Z)
    half_core, half_slab = CORE_WIDTH / 2, t.RIB_SLAB_WIDTH / 2
    heater_half = rm.HEATER_WIDTH / 2
    m1_out = rm.M1_GAP + rm.M1_WIDTH
    m1_inner = min(RADIUS, WIN_Y[1])  # the inner disc runs from the metal-1 gap to the ring centre; the window clips it
    via_out = rm.VIA_GAP + rm.VIA_SIZE
    z_m1_top = t.Z_M1 + t.T_M1
    z_heater_top = t.Z_HEATER + t.T_HEATER
    fs.box(ax, -half_slab, half_slab, 0.0, t.T_SLAB90, edgecolor=fs.MUTED)
    fs.box(ax, -half_core, half_core, 0.0, t.T_SI, edgecolor=fs.MUTED)
    fs.box(ax, -heater_half, heater_half, t.Z_HEATER, z_heater_top, edgecolor=fs.INK, lw=0.6)
    for sign in (1, -1):
        y0, y1 = sorted((sign * rm.VIA_GAP, sign * via_out))
        fs.box(ax, y0, y1, t.T_SLAB90, t.Z_M1, edgecolor=fs.INK)
        end = m1_inner if sign > 0 else m1_out
        y0, y1 = sorted((sign * rm.M1_GAP, sign * end))
        fs.box(ax, y0, y1, t.Z_M1, z_m1_top, edgecolor=fs.INK)
    ax.plot(WIN_Y, [-t.T_BOX, -t.T_BOX], color=fs.MUTED, lw=0.5, zorder=2)
    fs.image_axes(ax, "y (µm)", "z (µm)")
    ax.set_anchor("N")  # the equal aspect makes the map short: keep its top level with panel b
    ax.set_xticks(np.arange(-9, 10, 3))
    ax.set_yticks(np.arange(-3, 5, 1))
    fs.colorbar_beside(ax, image, "temperature rise (K)", width=0.018, pad=0.015)
    fs.note(ax, "n side (ring inside) at +y,  p side (outside) at −y", (WIN_Y[0] + 0.4, 3.6), ha="left")
    fs.note(ax, "TiN heater", (-0.5, z_heater_top), xytext=(-5.0, 2.9), ha="right")
    fs.note(ax, "metal 1", (-3.0, 1.45), xytext=(-5.0, 1.45), ha="right")
    fs.note(ax, "contact via", (rm.VIA_GAP + 0.25, 0.6), xytext=(5.0, 0.6), ha="left")
    fs.note(ax, "waveguide core", (0.0, 0.0), xytext=(0.0, -0.9), ha="center")  # from below: the vias block the sides
    fs.note(ax, "buried oxide", (WIN_Y[0] + 0.4, -1.0), ha="left")
    fs.note(ax, "silicon substrate (300 K)", (WIN_Y[0] + 0.4, -2.5), ha="left")
    fs.panel_title(ax, f"temperature rise at {d['P_reference_mW']:.0f} mW")


def panel_profile(ax, d: dict, k: dict) -> None:
    """Rise along y = 0 against z; the profile ends at the bottom of the mesh (the substrate band is the 300 K region)."""
    z = np.linspace(WIN_Z[0], WIN_Z[1], 400)
    profile = LinearTriInterpolator(d["tri"], d["rise"])(np.zeros_like(z), z)  # masked below the mesh: no line there
    for label, z0, z1, color, side in layers():
        ax.axhspan(z0, z1, color=color, lw=0, zorder=0)
        x = 1.0 if side == "left" else k["x_max"] - 1.0
        y = z1 + 0.3 if label == "heater" else (z0 + z1) / 2  # the heater band is too thin and the curve crosses it
        ax.text(x, y, label, fontsize=6, color=fs.INK, va="center", ha=side)
    ax.plot(profile, z, color=fs.CMAP_HEAT(0.85), lw=1.0, zorder=3)
    ax.set_xlim(0, k["x_max"])
    ax.set_ylim(*WIN_Z)
    ax.set_xticks([0, 20, 40, 60])
    ax.set_yticks(np.arange(-3, 5, 1))
    plain_axes(ax, "temperature rise (K)", "z (µm)")
    fs.note(ax, f"peak {k['peak']:.1f} K", (0.97, 0.9), ha="right", transform=ax.transAxes)


def panel_power(ax, d: dict, k: dict) -> None:
    """Rise of the core and of the heater film against power, with the core without electrodes and the energy balance."""
    p = d["powers_mW"]
    x = np.array([0.0, p.max()])
    ax.plot(x, k["bare_slope"] * x, color=fs.AQUA, lw=1.0, zorder=1)
    ax.plot(x, k["core_slope"] * x, color=fs.BLUE, lw=1.0, zorder=2)
    ax.plot(p, d["core_dT"], "o", color=fs.BLUE, ms=4, zorder=3)
    ax.plot(x, k["heater_slope"] * x, color=fs.ORANGE, lw=1.0, zorder=2)
    ax.plot(p, d["heater_dT"], "o", color=fs.ORANGE, ms=4, zorder=3)
    ax.axvline(k["p_ref"], ymax=0.62, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.set_xlim(0, p.max() * 1.5)
    ax.set_ylim(0, 165)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_yticks([0, 40, 80, 120])
    plain_axes(ax, "heater power (mW)", "temperature rise (K)")
    xl = p.max() * 1.05
    ax.text(xl, k["heater_slope"] * p.max(), f"heater film\n{k['heater_slope']:.2f} K/mW", fontsize=6, va="center")
    ax.text(xl, k["bare_slope"] * p.max() + 6, f"core, no electrodes\n{k['bare_slope']:.2f} K/mW", fontsize=6, va="bottom")
    ax.text(xl, k["core_slope"] * p.max() - 4, f"core\n{k['core_slope']:.2f} K/mW", fontsize=6, va="top")
    fs.note(ax, f"1 mW heats the core by {k['core_slope']:.2f} K", (0.03, 0.97), va="top", transform=ax.transAxes)
    fs.note(ax, f"electrodes cost {k['loss_pct']:.1f} % of the core rise", (0.03, 0.89), va="top", transform=ax.transAxes)
    fs.note(
        ax,
        f"R = {k['r_ohm']:.0f} Ω; {k['p_ref']:.0f} mW at {k['v_volt']:.2f} V, {k['i_ma']:.1f} mA",
        (0.03, 0.81),
        va="top",
        transform=ax.transAxes,
    )
    if k["p_sink_mw"] is not None:
        fs.note(
            ax,
            f"energy balance: {k['p_sink_mw']:.2f} of {k['p_ref']:.2f} mW reach the heat sink",
            (0.03, 0.73),
            va="top",
            transform=ax.transAxes,
        )


def panel_transient(ax, d: dict, k: dict) -> None:
    """Core rise normalised to its final value; markers at the 10 %, 63 % (1 - 1/e) and 90 % levels."""
    time_us = d["transient_t"] * 1e6
    norm = d["transient_core_dT"] / d["transient_core_dT"][-1]
    ax.plot(time_us, norm, color=fs.BLUE, lw=1.0, zorder=2)
    for level, t_us in zip((0.10, TAU_LEVEL, 0.90), k["t_levels"], strict=True):
        ax.plot(t_us, level, "o", color=fs.INK, ms=3, zorder=3)
        low = level < 0.2  # the 10 % marker sits on the time axis: its label goes beside it
        ax.text(
            t_us + 3,
            level if low else level - 0.05,
            f"{level * 100:.0f} %",
            fontsize=6,
            color=fs.INK,
            va="center" if low else "top",
        )
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 1.05)
    ax.set_xticks([0, 30, 60, 90, 120])
    ax.set_yticks([0, 0.5, 1.0])
    plain_axes(ax, "time (µs)", "normalised core rise (ΔT / ΔT$_\\infty$)")
    fs.note(ax, f"τ = {k['tau_us']:.1f} µs", (0.97, 0.3), ha="right", transform=ax.transAxes)
    fs.note(ax, f"rise time 10–90 % = {k['rise_us']:.1f} µs", (0.97, 0.22), ha="right", transform=ax.transAxes)
    fs.note(ax, f"rule of thumb 0.35 / t_rise = {k['bw_khz']:.1f} kHz", (0.97, 0.14), ha="right", transform=ax.transAxes)


def main() -> None:
    d = load()
    k = derived(d)
    # one grid per row: in a shared grid the column between a and d would have to hold the colour bar of a
    # and the axis labels of d, and the constrained layout gives up
    rows = [[[["a"] * 6 + ["b"] * 4]], [[["c", "d"]]]]
    fig, axes = fs.mosaic(fs.DOUBLE, 112, rows, height_ratios=[1.0, 1.05])
    panel_map(axes["a"], d)
    panel_profile(axes["b"], d, k)
    panel_power(axes["c"], d, k)
    panel_transient(axes["d"], d, k)
    fig.canvas.draw()  # settle the constrained layout before the labels of each row are aligned
    height_pt = fig.get_figheight() * 72
    row_ref = {"a": "a", "b": "a", "c": "c", "d": "c"}  # the labels of a row share the top of its first panel
    for key, ax in axes.items():
        top_ref = axes[row_ref[key]].get_position().y1
        dy = (top_ref - ax.get_position().y1) * height_pt
        fs.panel_label(ax, key, dy=dy)
    fs.save(fig, Path(__file__).with_name("fig4_heat.png"))


if __name__ == "__main__":
    main()

"""Figure 3 - CHARGE: the PN junction of the ring modulator, from the process file to the capacitance and bandwidth.

    a  net doping ND - NA over the slab (signed, logarithmic): the six implant regions and the contact vias
    b  net free-carrier density n - p around the rib at 0 V reverse bias (signed, logarithmic)
    c  the same at the highest reverse bias of the sweep: the neutral depletion region has widened
    d  electron and hole density across the junction at mid height of the rib, at 0, 1/4, 1/2 and the highest bias
    e  junction capacitance per length versus reverse bias: simulation and the abrupt-junction formula
    f  intrinsic RC bandwidth versus reverse bias, with the series resistance at 0 V
    g  process file versus solver: simulated over expected net doping in the six regions

Reads 3_charge_profile/pn_rib_charge.npz.  Every bias axis runs from 0 V to the highest reverse bias
of that file, so a longer sweep (--vmin of charge_profile.py) is drawn in full.

    python fig3_charge.py            ->  figures/fig3_charge.png
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.tri import LinearTriInterpolator, Triangulation

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO))
import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402
import rm_builder as rm  # noqa: E402

DATA = ROOT / "3_charge_profile" / "pn_rib_charge.npz"
RIB_WIDTH = 0.5  # um, core of the rib waveguide
Z_STRETCH = 4.0  # vertical stretch of the slab map in panel a
CUT_Z = 0.11  # um, mid height of the rib: the cut of panel d
CUT_FRACTIONS = (0.0, 0.25, 0.5, 1.0)  # of the highest reverse bias: the biases of panel d
MAP_DECADES = 5  # the signed log map saturates at 10^20 cm^-3, five decades above 10^15
Q = 1.602176634e-19  # C
EPS0 = 8.8541878128e-12  # F/m
K_B = 8.617333262e-5  # eV/K
T_KELVIN = 300.0
N_I = 1.0e10  # cm^-3, intrinsic carrier density of silicon at 300 K
EPS_SI = 11.7


def load() -> dict:
    """The charge result, the doping map and the summary numbers, with the reverse bias as a positive axis."""
    with np.load(DATA) as f:
        d = {key: f[key] for key in f.files}
    d["RB"] = -d["V"] + 0.0  # reverse bias (V): minus the anode voltage, 0 .. the most negative point of the sweep
    d["RB_MAX"] = float(np.max(d["RB"]))  # the end of every bias axis of this figure
    d["L_pn"] = float(d["L_pn_um"])
    d["tri_carrier"] = fs.triangulation(d["y"], d["z"], d["elements"])
    d["tri_doping"] = fs.triangulation(d["doping_y"], d["doping_z"], d["doping_elements"])
    d["net_doping"] = d["ND"] - d["NA"]
    return d


def bias_ticks(vmax: float) -> np.ndarray:
    """Whole volts from 0 V up to the highest reverse bias."""
    return np.arange(0, np.floor(vmax) + 1e-9)


def signed_log(x: np.ndarray) -> np.ndarray:
    """Sign of x times log10(|x| / 1e15 cm^-3): zero inside the 1e15 band, 5 at 1e20."""
    return np.sign(x) * np.log10(np.maximum(np.abs(x), 1e15) / 1e15)


def silicon_only(tri: Triangulation) -> Triangulation:
    """The same triangles, with the air above the silicon, the oxide below it and the slab edges hidden."""
    yc = tri.x[tri.triangles].mean(axis=1)
    zc = tri.y[tri.triangles].mean(axis=1)
    top = np.where(np.abs(yc) < RIB_WIDTH / 2, t.T_SI, t.T_SLAB90)
    out = Triangulation(tri.x, tri.y, tri.triangles)
    edge = np.abs(yc) > t.RIB_SLAB_WIDTH / 2 + 1e-6
    out.set_mask((zc > top + 1e-6) | (zc < -1e-6) | edge)
    return out


def _sign_tick_label(k: int) -> str:
    """Tick label of the signed log scale: k decades above 1e15, p for holes and n for electrons."""
    if k == 0:
        return "0"
    prefix = "n " if k > 0 else "p "
    return f"{prefix}10$^{{{15 + abs(k)}}}$"


def _sweep(cmap, n: int) -> list:
    """n colours of an ordered sweep, light to dark, taken from the magnitude ramp of a map."""
    return [cmap(x) for x in np.linspace(0.3, 1.0, n)]


def _signed_colorbar(fig, mappable, ax, label: str, **kwargs) -> None:
    bar = fs.colorbar(fig, mappable, ax, label, **({"fraction": 0.035, "aspect": 24} | kwargs))
    ticks = [-5, -2, 0, 2, 5]
    bar.set_ticks(ticks)
    bar.set_ticklabels([_sign_tick_label(k) for k in ticks])


def panel_doping(fig, ax, d: dict) -> None:
    """Net doping over the slab, stretched vertically, with the implant regions and the contact vias."""
    tri = silicon_only(d["tri_doping"])
    image = ax.tripcolor(
        tri,
        signed_log(d["net_doping"]),
        cmap=fs.CMAP_DOPING,
        vmin=-MAP_DECADES,
        vmax=MAP_DECADES,
        shading="gouraud",
        rasterized=True,
    )
    ax.set_xlim(-3.1, 3.1)
    ax.set_ylim(-0.03, 0.26)
    fs.image_axes(ax, "y (µm)", "z (µm)")  # sets an equal aspect, so the stretch is applied after it
    ax.set_aspect(Z_STRETCH)
    ax.set_anchor("W")
    fs.rib_outline(ax, RIB_WIDTH, t.T_SI, t.T_SLAB90, slab_width=t.RIB_SLAB_WIDTH, color=fs.INK, lw=0.5)
    # the implant regions, named above the silicon: P / N from the rib out to 0.65 um, P+ / N+ to 1.25 um, P++ / N++ beyond
    edges = [0.0, t.PN_GAP_MEDIUM, t.PN_GAP_HIGH, rm.VIA_GAP + rm.VIA_SIZE]
    centres = [(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)]
    for c, name in zip(centres, ["N", "N$^{+}$", "N$^{++}$"], strict=True):
        for sign, text in ((1, name), (-1, name.replace("N", "P"))):
            ax.annotate(
                text,
                (sign * c, 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=6,
                color=fs.INK,
                annotation_clip=False,
            )
    # contact vias: aluminium from the slab top upward, drawn to the top of the axes
    for sign in (1, -1):
        lo, hi = sorted((sign * rm.VIA_GAP, sign * (rm.VIA_GAP + rm.VIA_SIZE)))
        fs.box(ax, lo, hi, t.T_SLAB90, 0.26, facecolor=fs.MATERIAL_COLORS["aluminium"], edgecolor=fs.INK, lw=0.4)
        ax.text(
            sign * (rm.VIA_GAP + rm.VIA_SIZE / 2), 0.175, "via", rotation=90, ha="center", va="center", fontsize=6, color=fs.INK
        )
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
    ax.set_yticks([0, 0.1, 0.2])
    ax.annotate(
        f"vertical scale ×{Z_STRETCH:g}",
        (-3.0, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(0, 2),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=6,
        color=fs.SECONDARY,
        annotation_clip=False,
    )
    _signed_colorbar(fig, image, ax, "net doping ND − NA (cm$^{-3}$)")


def panel_carriers(ax, d: dict, k: int):
    """Net free-carrier density n - p around the rib at bias index k."""
    tri = silicon_only(d["tri_carrier"])
    net = d["n"][:, k].astype(float) - d["p"][:, k].astype(float)
    image = ax.tripcolor(
        tri, signed_log(net), cmap=fs.CMAP_DOPING, vmin=-MAP_DECADES, vmax=MAP_DECADES, shading="gouraud", rasterized=True
    )
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylim(-0.02, 0.24)
    fs.rib_outline(ax, RIB_WIDTH, t.T_SI, t.T_SLAB90, color=fs.INK, lw=0.5)
    fs.image_axes(ax, "y (µm)", "z (µm)")
    ax.set_xticks([-0.5, 0, 0.5])
    ax.set_yticks([0, 0.2])
    ax.text(-0.45, 0.17, "p", ha="center", va="center", fontsize=6, color=fs.SECONDARY)
    ax.text(0.45, 0.17, "n", ha="center", va="center", fontsize=6, color=fs.SECONDARY)
    fs.panel_title(ax, f"reverse bias {d['RB'][k]:g} V")
    return image


def panel_cut(ax, d: dict) -> None:
    """Electron and hole density across the junction at mid height of the rib."""
    yy = np.linspace(-0.25, 0.25, 501)
    zz = np.full_like(yy, CUT_Z)
    idx = [int(np.argmin(np.abs(d["RB"] - f * d["RB_MAX"]))) for f in CUT_FRACTIONS]
    e_cols, h_cols = _sweep(fs.CMAP_N, len(idx)), _sweep(fs.CMAP_P, len(idx))
    greys = np.linspace(0.72, 0.2, len(idx))
    for i, k in enumerate(idx):
        electrons = np.ma.filled(LinearTriInterpolator(d["tri_carrier"], d["n"][:, k].astype(float))(yy, zz), np.nan) / 1e17
        holes = np.ma.filled(LinearTriInterpolator(d["tri_carrier"], d["p"][:, k].astype(float))(yy, zz), np.nan) / 1e17
        ax.plot(yy * 1000, electrons, color=e_cols[i], lw=1.0, zorder=2)
        ax.plot(yy * 1000, holes, color=h_cols[i], lw=1.0, zorder=2)
    handles = [Line2D([], [], color=(g, g, g), lw=1.0) for g in greys]
    labels = [f"{d['RB'][k]:g} V" for k in idx]
    ax.legend(
        handles,
        labels,
        title="reverse bias",
        loc="upper right",
        ncol=1,
        handlelength=1.2,
        labelspacing=0.3,
        handletextpad=0.4,
        borderaxespad=0.2,
        title_fontsize=6,
    )
    ax.text(-160, 3.2, "holes", ha="center", va="bottom", fontsize=6, color=fs.INK)
    ax.text(190, 3.2, "electrons", ha="center", va="bottom", fontsize=6, color=fs.INK)
    ax.set_xlim(-250, 250)
    ax.set_ylim(0, 9.5)
    ax.set_xticks([-250, 0, 250])
    ax.set_xlabel("y (nm)")
    ax.set_ylabel("density (10$^{17}$ cm$^{-3}$)")
    fs.panel_title(ax, f"across the junction, z = {CUT_Z:g} µm")


def abrupt_capacitance(reverse: np.ndarray) -> np.ndarray:
    """Abrupt-junction capacitance per length (fF/µm) of the textbook (Chrostowski & Hochberg, Eq. 6.14)."""
    n_d, n_a = t.DOPING["N"] * 1e6, t.DOPING["P"] * 1e6  # m^-3
    v_bi = K_B * T_KELVIN * np.log(t.DOPING["N"] * t.DOPING["P"] / N_I**2)
    t_rib = t.T_SI * 1e-6  # m
    c_per_m = t_rib * np.sqrt(Q * EPS0 * EPS_SI / (2 * (1 / n_d + 1 / n_a) * (v_bi + reverse)))  # F/m
    return c_per_m * 1e9  # F/m -> fF/um


def panel_capacitance(ax, d: dict) -> None:
    """Simulated junction capacitance per length against the abrupt-junction formula (Chrostowski & Hochberg, Eq. 6.14).

    The ratio simulation / formula and the difference are computed at 0 V and at the highest reverse bias.
    The one-dimensional formula leaves out the field around the 220 nm high junction; that is a possible
    cause of the excess, and the attribution was not tested.
    """
    vmax = d["RB_MAX"]
    sim = d["C_V"] / d["L_pn"] * 1e15  # fF/um
    formula = abrupt_capacitance(d["RB"])
    k0, kmax = int(np.argmin(np.abs(d["RB"]))), int(np.argmax(d["RB"]))
    rb = np.linspace(0, vmax, 201)
    ax.plot(rb, abrupt_capacitance(rb), color=fs.MUTED, lw=0.8, zorder=1)
    ax.plot(d["RB"], sim, "o", color=fs.BLUE, ms=3.5, zorder=3)
    ax.set_xlim(0, vmax)
    top = float(np.ceil(1.34 * max(sim.max(), formula.max()) / 0.05) * 0.05)  # room for the note above the data
    ax.set_ylim(0, top)
    ax.set_yticks(np.arange(0.0, top + 1e-9, 0.1))
    ax.set_xticks(bias_ticks(vmax))
    ax.set_xlabel("reverse bias (V)")
    ax.set_ylabel("capacitance (fF/µm)")
    ratio_text = (
        "simulation / formula\n"
        f"{sim[k0] / formula[k0]:.2f} at 0 V  ({sim[k0] - formula[k0]:+.3f} fF/µm)\n"
        f"{sim[kmax] / formula[kmax]:.2f} at {d['RB'][kmax]:g} V  ({sim[kmax] - formula[kmax]:+.3f} fF/µm)"
    )
    fs.note(ax, ratio_text, (0.97, 0.97), ha="right", va="top", transform=ax.transAxes)
    k_label = int(np.argmin(np.abs(d["RB"] - 0.62 * vmax)))  # label both series beside the data, clear of the note
    ax.text(d["RB"][k_label], sim[k_label] + 0.035, "simulation", ha="center", va="bottom", fontsize=6, color=fs.INK)
    ax.text(d["RB"][k_label], formula[k_label] - 0.035, "abrupt-junction formula", ha="center", va="top", fontsize=6,
            color=fs.SECONDARY)  # fmt: skip
    fs.panel_title(ax, "junction capacitance")


def panel_bandwidth(ax, d: dict) -> None:
    """Intrinsic RC bandwidth against reverse bias, with the series resistance at 0 V."""
    vmax = d["RB_MAX"]
    kmax = int(np.argmax(d["RB"]))
    f_ghz = d["f_RC"] / 1e9
    ax.plot(d["RB"], f_ghz, "o-", color=fs.BLUE, ms=3.5, lw=1.0, zorder=3)
    ax.set_xlim(0, vmax)
    ax.set_ylim(0, 150)
    ax.set_xticks(bias_ticks(vmax))
    ax.set_xlabel("reverse bias (V)")
    ax.set_ylabel("f$_{RC}$ (GHz)")
    ax.text(0.15, f_ghz[0] - 10, f"{f_ghz[0]:.0f} GHz", ha="left", va="top", fontsize=6, color=fs.INK)
    ax.text(vmax - 0.15, f_ghz[kmax] + 6, f"{f_ghz[kmax]:.0f} GHz", ha="right", va="bottom", fontsize=6, color=fs.INK)
    rs0 = float(d["Rs_V"][0])
    ax.text(
        vmax - 0.1,
        6,
        f"R$_s$ at 0 V: {rs0:.0f} Ω\n{rs0 * d['L_pn'] * 1e-4:.2f} Ω cm (R$_s$ × L$_{{pn}}$)",
        ha="right",
        va="bottom",
        fontsize=6,
        color=fs.SECONDARY,
        linespacing=1.3,
    )
    fs.panel_title(ax, "intrinsic RC bandwidth")


def _math_name(name: str) -> str:
    return re.sub(r"(\+\+|\+)", lambda m: f"$^{{{m.group(1)}}}$", name)


def panel_check(ax, d: dict) -> None:
    """Simulated over expected net doping in the six regions of the process file."""
    names = [_math_name(str(s)) for s in d["check_names"]]
    ratio = d["check_simulated"] / d["check_expected"]
    y = np.arange(len(names))[::-1].astype(float)
    ax.axvline(1.0, color=fs.MUTED, lw=0.5, zorder=0)
    ax.plot(ratio, y, "o", color=fs.BLUE, ms=3.5, zorder=3)
    for r, yi in zip(ratio, y, strict=True):
        ax.text(1.0115, yi, f"{r:.3f}", ha="left", va="center", fontsize=6, color=fs.SECONDARY)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_xlim(0.98, 1.02)
    ax.set_xticks([0.98, 0.99, 1.00, 1.01, 1.02])
    ax.set_xlabel("simulated / expected")
    fs.panel_title(ax, "process file versus solver")


def main() -> None:
    d = load()
    fig, axes = fs.mosaic(fs.DOUBLE, 150, [["a", "a", "a"], ["b", "c", "g"], ["d", "e", "f"]], height_ratios=[1.0, 0.72, 1.3])
    panel_doping(fig, axes["a"], d)
    img_b = panel_carriers(axes["b"], d, 0)
    panel_carriers(axes["c"], d, int(np.argmax(d["RB"])))
    _signed_colorbar(
        fig,
        img_b,
        [axes["b"], axes["c"]],
        "net carrier n − p (cm$^{-3}$)",
        orientation="horizontal",
        fraction=0.07,
        pad=0.14,
        aspect=40,
    )
    panel_check(axes["g"], d)
    panel_cut(axes["d"], d)
    panel_capacitance(axes["e"], d)
    panel_bandwidth(axes["f"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig3_charge.png"))


if __name__ == "__main__":
    main()

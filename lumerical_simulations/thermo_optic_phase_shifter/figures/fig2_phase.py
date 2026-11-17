"""Figure 2 - MODE: the phase shift against the heater power, and what the trench wall does to the light.

    a  the TE0 mode of the strip at 1550 nm, whose effective index the temperature moves
    b  phase shift against the heater power, with and without trenches: the mode-solver runs with the temperature maps
       of step 1, and the lines through them; the power for pi and for 2 pi
    c  change of the effective index when the wall of a trench comes close to the core, with the tail of the mode

Reads 2_phase_shift/phase.npz; the geometry comes from gsip_technology and from the builder of the device.

    python fig2_phase.py            ->  figures/fig2_phase.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/thermo_optic_phase_shifter/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs, t  # noqa: E402

from devices import thermo_optic_phase_shifter_builder as tops  # noqa: E402

DATA = ROOT / "2_phase_shift" / "phase.npz"
ISOLATED, DRAWN, REFERENCE = 0, 1, 2  # the order of the cases in the file
WIN_Y, WIN_Z = (-0.95, 0.95), (-0.5, 0.72)  # um: the window of the mode panel


def panel_mode(ax, d: dict) -> None:
    share = panels.core_share(d["mode_y_um"], d["mode_z_um"], d["mode_E"].astype(float), tops.WIDTH)
    text = f"TE0, {panels.NEFF} = {d['device_neff'][0]:.4f}\n{100 * share:.0f} % of |E|² in the core"
    panels.mode_map(
        ax, d["mode_y_um"], d["mode_z_um"], d["mode_E"].astype(float), WIN_Y, WIN_Z, text,
        outline=lambda axis: panels.strip_outline(axis, tops.WIDTH),
    )  # fmt: skip
    ax.set_xticks([-0.5, 0, 0.5])
    ax.set_yticks([-0.4, 0, 0.4])
    fs.panel_title(ax, "the mode, cold")


def panel_phase(ax, d: dict) -> None:
    """Phase shift in units of pi against the total heater power."""
    lam, length = float(d["lam"]), float(d["length_um"])
    in_pi = lambda dn: 2 * length * dn / lam  # noqa: E731  the phase of a change of n_eff over the heated length, in pi
    p_max = 48.0
    x = np.array([0.0, p_max])
    slopes = {"with trenches": float(d["dneff_dP_isolated"]), "no trenches": float(d["dneff_dP_reference"])}
    colors = {"with trenches": fs.BLUE, "no trenches": fs.ORANGE}
    for level in (1, 2):
        ax.axhline(level, color=fs.HAIRLINE, lw=0.5, zorder=0)
    for label, slope in slopes.items():
        ax.plot(x, in_pi(slope * x), color=colors[label], lw=1.0, zorder=2)
        for level in (1, 2):
            power = level / in_pi(slope)
            if power < p_max:
                ax.plot([power, power], [0, level], color=colors[label], lw=0.5, ls=(0, (3, 2)), zorder=1)
    powers = d["powers_mW"][1:]
    ax.plot(powers, in_pi(d["device_neff"][1:] - d["device_neff"][0]), "o", color=fs.BLUE, ms=4, zorder=3)
    ax.plot(powers[:1], in_pi(d["reference_neff"][1:] - d["reference_neff"][0]), "o", color=fs.ORANGE, ms=4, zorder=3)
    ax.set_xlim(0, p_max)
    ax.set_ylim(0, 2.45)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["0", "π", "2π"])
    ax.set_xticks([0, 10, 20, 30, 40])
    ax.set_xlabel("heater power (mW)")
    ax.set_ylabel("phase shift")
    p_iso, p_ref = float(d["P_pi_mW"][ISOLATED]), float(d["P_pi_mW"][REFERENCE])
    fs.note(ax, f"with trenches\nπ at {p_iso:.1f} mW", (p_iso * 1.62, 1.66), ha="right", va="bottom", color=fs.INK)
    fs.note(ax, f"no trenches\nπ at {p_ref:.1f} mW", (p_ref * 1.45, 1.36), ha="left", va="top", color=fs.INK)
    fs.note(
        ax,
        f"device as drawn,\n{100 * float(d['isolated_fraction']):.0f} % of its film\nbeside trenches:\n"
        f"π at {d['P_pi_mW'][DRAWN]:.2f} mW\n2π at {d['P_2pi_mW'][DRAWN]:.2f} mW",
        ((p_ref + 2 * p_ref) / 2, 0.08),
        ha="center",
        va="bottom",
    )
    fs.note(ax, "points: mode-solver runs", (0.03, 0.97), va="top", transform=ax.transAxes)
    fs.panel_title(ax, f"{length:.0f} µm of film at {lam * 1000:.0f} nm")


def panel_wall(ax, d: dict) -> None:
    """How much a trench wall near the core moves the effective index: it follows the square of the mode's tail."""
    distance, change = d["wall_distance_um"], np.abs(d["wall_dneff"])
    k0 = 2 * np.pi / float(d["lam"])
    gamma = k0 * np.sqrt(float(d["device_neff"][0]) ** 2 - float(d["n_ox"]) ** 2)  # 1/um: decay of the tail in the oxide
    rule = t.DESIGN_RULES["trench_to_waveguide"]
    own = tops.TRENCH_GAP - tops.WIDTH / 2
    anchor = int(np.argmin(distance))  # the tail is drawn through the closest wall, where the change is largest
    line = np.linspace(0.4, 1.9, 50)
    ax.plot(line, change[anchor] * np.exp(-2 * gamma * (line - distance[anchor])), color=fs.MUTED, lw=0.7, zorder=1)
    ax.axvline(rule, color=fs.MUTED, lw=0.6, ls=(0, (4, 3)), zorder=0)
    ax.plot(distance, change, "o", color=fs.BLUE, ms=4, zorder=3)
    device = int(np.argmin(np.abs(distance - own)))
    ax.plot(distance[device], change[device], "o", mfc="none", mec=fs.INK, ms=8, mew=0.6, zorder=4)
    ax.set_yscale("log")
    ax.set_xlim(0.4, 1.95)
    ax.set_ylim(1e-15, 1e-4)
    ax.set_yticks([1e-14, 1e-12, 1e-10, 1e-8, 1e-6, 1e-4])
    ax.set_xticks([0.5, 1.0, 1.5])
    ax.set_xlabel("trench wall to the edge of the core (µm)")
    ax.set_ylabel(f"change of {panels.NEFF}")
    fs.note(ax, f"rule\n{rule:.1f} µm", (rule - 0.04, 2e-5), ha="right", va="top")
    fs.note(ax, f"device\n{own:.2f} µm", (own, change[device] * 8), ha="center", va="bottom")
    fs.note(ax, "tail of the mode:\nexp(−2γd),\n" + f"γ = {gamma:.1f} µm" + "$^{-1}$", (0.5, 3e-13), ha="left", va="bottom")
    fs.panel_title(ax, "the wall and the light")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 66, [["a", "b", "c"]], width_ratios=[1.0, 1.35, 1.1])
    panel_mode(axes["a"], d)
    panel_phase(axes["b"], d)
    panel_wall(axes["c"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig2_phase.png"))


if __name__ == "__main__":
    main()

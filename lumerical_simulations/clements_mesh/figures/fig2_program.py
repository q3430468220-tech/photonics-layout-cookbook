"""Figure 2 - INTERCONNECT: the 4 x 4 mesh programmed to a matrix.

    a  the 4-point DFT: every entry as a phasor, the target as a ring and the mesh (INTERCONNECT, 1.55 um) as a dot
    b  the heater powers of the DFT on the mesh, at the places where the heaters lie
    c  1 - F against the wavelength: the DFT in INTERCONNECT, and the random unitaries in the model
    d  what sets the band: its width for the drawn mesh, the first draft, and the couplers with their effects taken out

Reads 2_program/program.npz; the places of the blocks come from the builder of the mesh.

    python fig2_program.py            ->  figures/fig2_program.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.patches import Circle, FancyArrow, Rectangle

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/clements_mesh/
sys.path.insert(0, str(ROOT.parent))
import panels  # noqa: E402
from panels import fs  # noqa: E402

from devices import clements_mesh_builder as cm  # noqa: E402

DATA = ROOT / "2_program" / "program.npz"


def panel_phasors(ax, d: dict) -> None:
    target = d["targets"][0]
    u = d["U_interconnect"][0][len(d["lam"]) // 2]
    a = np.trace(target.conj().T @ u)
    u = u * np.exp(-1j * np.angle(a)) / np.sqrt(np.real(np.trace(u.conj().T @ u)) / target.shape[0])  # global phase, loss
    n = target.shape[0]
    r = 0.42
    for i in range(n):
        for j in range(n):
            cx, cy = j, n - 1 - i
            t = target[i, j]
            ax.add_patch(Circle((cx, cy), r * abs(t) / 0.5, fill=False, ec=fs.MUTED, lw=0.6))
            tip = r * abs(t) / 0.5 * np.exp(1j * np.angle(t))  # the phase of the target: a tick on its ring
            ax.plot(
                [cx + 0.8 * tip.real, cx + 1.18 * tip.real], [cy + 0.8 * tip.imag, cy + 1.18 * tip.imag], color=fs.MUTED, lw=1.4
            )
            v = u[i, j] * r / 0.5
            ax.add_patch(Circle((cx, cy), 0.05, color=fs.BLUE, lw=0))
            ax.add_patch(FancyArrow(cx, cy, v.real, v.imag, width=0.012, head_width=0.08, head_length=0.08,
                                    length_includes_head=True, color=fs.BLUE, lw=0))  # fmt: skip
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_aspect("equal")
    ax.set_xticks(range(n))
    ax.set_xticklabels([f"in {k + 1}" for k in range(n)])
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"out {n - k}" for k in range(n)])
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    f = float(d["fidelity_interconnect"][0][len(d["lam"]) // 2])
    ax.set_title(f"1 − F = {1 - f:.1e}", fontsize=6, color=fs.SECONDARY, loc="right", pad=2)
    fs.panel_title(ax, "the DFT, entry by entry")


def panel_heaters(ax, d: dict) -> None:
    info = cm.clements_mesh().info
    n, _pitch = info["n"], info["pitch"]
    length = info["length"]
    for m in range(n):
        ax.plot([0, length / 1000], [-m, -m], color=fs.HAIRLINE, lw=0.8, zorder=0)
    S, F, dcl = info["section"], info["fan_length"], info["coupler_length"]
    for b in info["blocks"]:
        for x in (b["x0"] + S + F + dcl / 2, b["x0"] + 2 * S + 3 * F + 1.5 * dcl):
            p = b["upper"]
            ax.plot([(x - 35) / 1000, x / 1000, (x + 35) / 1000], [-p, -p - 0.5, -p], color=fs.MUTED, lw=0.8, zorder=1)
            ax.plot([(x - 35) / 1000, x / 1000, (x + 35) / 1000], [-p - 1, -p - 0.5, -p - 1], color=fs.MUTED, lw=0.8, zorder=1)
    powers, p2pi = d["powers_mW"][0], 2 * float(d["P_pi_mW"])
    norm = Normalize(0, p2pi)
    for _name, _kind, row, x, p in zip(d["heater_names"], d["heater_kind"], d["heater_row"], d["heater_x"], powers, strict=False):
        ax.add_patch(
            Rectangle(((x - 50) / 1000, -row - 0.13), 0.1, 0.26, color=fs.CMAP_HEAT(norm(p)), ec=fs.INK, lw=0.4, zorder=2)
        )
        ax.text(x / 1000, -row + 0.2, f"{p:.1f}", ha="center", va="bottom", fontsize=5, color=fs.INK)
    ax.set_xlim(-0.02, length / 1000 + 0.02)
    ax.set_ylim(-n + 0.4, 0.75)
    ax.set_yticks([-m for m in range(n)])
    ax.set_yticklabels([f"row {m}" for m in range(n)])
    ax.set_xlabel("position along the mesh (mm)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    sm = ScalarMappable(norm=norm, cmap=fs.CMAP_HEAT)
    fs.colorbar_beside(ax, sm, "heater power (mW)")
    fs.panel_title(ax, f"the heaters for the DFT: {powers.sum():.0f} mW in all")


def panel_band(ax, d: dict) -> None:
    lam = 1000 * d["lam"]
    f = d["fidelity_model"]
    random = 1 - f[1:]
    ax.fill_between(lam, np.quantile(random, 0.1, axis=0), np.quantile(random, 0.9, axis=0), color=fs.AQUA, alpha=0.18, lw=0)
    ax.plot(lam, np.median(random, axis=0), color=fs.AQUA, lw=1.0)
    ax.plot(lam, 1 - d["fidelity_interconnect"][0], color=fs.BLUE, lw=1.0)
    ax.axhline(0.01, color=fs.HAIRLINE, lw=0.6, zorder=0)
    ax.set_yscale("log")
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(1e-7, 1)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("1 − F")
    fs.note(ax, "DFT, INTERCONNECT", (1598, 1e-5), ha="right", color=fs.BLUE)
    fs.note(ax, f"{len(random)} random unitaries,\nmedian and 10–90 %", (1598, 4e-7), ha="right", color=fs.AQUA)
    fs.note(ax, "F = 0.99", (1598, 0.013), ha="right", va="bottom")
    fs.panel_title(ax, "set at 1550 nm")


def panel_cases(ax, d: dict) -> None:
    labels = [str(x).replace(" um", " µm") for x in d["band_cases"]]
    widths = d["band_case_width_nm"]  # (case, target): the DFT first
    y = np.arange(len(labels))[::-1]
    med = np.median(widths[:, 1:], axis=1)
    lo, hi = widths[:, 1:].min(axis=1), widths[:, 1:].max(axis=1)
    ax.barh(y, med, height=0.55, color=[fs.BLUE if k == 0 else fs.HAIRLINE for k in range(len(labels))], lw=0)
    ax.errorbar(med, y, xerr=[med - lo, hi - med], fmt="none", ecolor=fs.SECONDARY, elinewidth=0.6, capsize=1.5)
    for yy, m, top in zip(y, med, hi, strict=False):
        ax.text(top + 3, yy, f"{m:.0f} nm", va="center", fontsize=6, color=fs.INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 125)
    ax.set_xlabel("band with F > 0.99 (nm), median of random unitaries")
    ax.spines["left"].set_visible(False)
    fs.panel_title(ax, "what sets the band")


def main() -> None:
    d = panels.load(DATA)
    fig, axes = fs.mosaic(fs.DOUBLE, 118, [["a", "b", "b"], ["c", "d", "d"]], width_ratios=[1.0, 0.9, 0.9],
                          height_ratios=[1.0, 0.95])  # fmt: skip
    panel_phasors(axes["a"], d)
    panel_heaters(axes["b"], d)
    panel_band(axes["c"], d)
    panel_cases(axes["d"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig2_program.png"))


if __name__ == "__main__":
    main()

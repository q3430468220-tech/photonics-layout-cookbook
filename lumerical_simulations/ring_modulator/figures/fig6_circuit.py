"""Figure 6 - INTERCONNECT: the ring modulator as a circuit element.

    a  transmission at 0 V over two free spectral ranges, with the FSR dimensioned
    b  the resonance at reverse bias 0, 1, 2 and 4 V, with the analytic all-pass ring underneath
    c  static transfer: transmission at the 0 V resonance and half a linewidth above it, versus reverse bias
    d  extinction at 0 V versus gap, with the analytic curve and the critical-coupling gap
    e  loaded Q versus gap, with the analytic curve and the bandwidth budget at the design gap
    f  thermal tuning: transmission for four heater powers, with the tuning rate and the power for one FSR

Reads 6_interconnect_ring_modulator/ring_modulator.npz, the result of the INTERCONNECT step.  Results written
before the element's 0 V index was corrected are drawn with the step-2 ring index, as they were computed.

    python fig6_circuit.py            ->  figures/fig6_circuit.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
sys.path.insert(0, str(ROOT.parents[1]))
import figstyle as fs  # noqa: E402

DATA = ROOT / "6_interconnect_ring_modulator" / "ring_modulator.npz"
ZOOM_BIASES = (0.0, 1.0, 2.0, 4.0)  # reverse bias of the resonance zoom (V)
HEAT_KEYS = ("heat_T_P0", "heat_T_P5", "heat_T_P10", "heat_T_P20")  # for heater_mW = 0, 5, 10, 20


def load() -> dict:
    """All arrays of the INTERCONNECT result."""
    if not DATA.exists():
        raise SystemExit("run the INTERCONNECT step (6_interconnect_ring_modulator) first")
    with np.load(DATA) as z:
        return {key: z[key] for key in z.files}


def endpoint_pm_per_V(volts: np.ndarray, shift_pm: np.ndarray) -> tuple[float, float]:
    """End-point average of the shift per volt: the shift at the highest reverse bias divided by that bias.

    Returns (pm/V, the bias in V as a positive number); the same definition as the INTERCONNECT step.
    """
    k = int(np.argmin(volts))
    v_end = -float(volts[k])
    return float(shift_pm[k]) / v_end, v_end


def design_fsr(d: dict) -> float:
    """lambda^2 / (n_g L) at the design resonance, in m: the free spectral range at which the tuning rate is measured."""
    return float(d["lam_res"]) ** 2 / (float(d["ng"]) * float(d["L_ring"]) * 1e-6)


# =====================================================================================
# analytic all-pass ring, written with the same constants as the INTERCONNECT model
# =====================================================================================
def bias_row(d: dict, volts: float) -> tuple[float, float]:
    """Index change dn and imaginary index k (both averaged over the ring) at a reverse bias, from the table."""
    row = int(np.argmin(np.abs(d["table"][:, 0] + volts)))  # the table holds the anode voltage, minus the reverse bias
    return float(d["table"][row, 1]), float(d["table"][row, 2])


def ring_loss_db(d: dict, k: float) -> float:
    """Round-trip power loss (dB): scattering, bend, and absorption 4 pi k / lam0 over the ring length."""
    absorption = 4 * np.pi * k / float(d["lam0"]) * float(d["L_ring"]) * 10 / np.log(10)  # lengths in um
    return float(d["scatter_turn_dB"]) + float(d["bend_turn_dB"]) + absorption


def base_index(d: dict) -> float:
    """Element index at 0 V: the INTERCONNECT value, or the step-2 ring index for results written before it existed."""
    return float(d["neff_element"]) if "neff_element" in d else float(d["neff"])


def _index(d: dict, lam_um, dn: float):
    """Effective index with first-order dispersion; lam in um."""
    neff, ng, lam0 = base_index(d), float(d["ng"]), float(d["lam0"])
    return neff + dn - (ng - neff) * (lam_um - lam0) / lam0


def kappa2(d: dict, gap_um):
    """Power coupling of the fitted exponential, kappa^2 = k2_A exp(-gap / k2_g0)."""
    return float(d["k2_A"]) * np.exp(-np.asarray(gap_um) / float(d["k2_g0"]))


def ring_transmission(d: dict, lam_um: np.ndarray, dn: float, k: float, k2) -> np.ndarray:
    """Power transmission of the all-pass ring; a is the round-trip amplitude, a^2 = 10^(-loss_dB / 10).

    The model needs no phase offset: with the same base index and loss, its resonance coincides with the simulated one.
    """
    a = 10 ** (-ring_loss_db(d, k) / 20)
    t = np.sqrt(1 - k2)
    phi = 2 * np.pi * float(d["L_ring"]) * _index(d, lam_um, dn) / lam_um
    c = np.cos(phi)
    return (a * a - 2 * a * t * c + t * t) / (1 - 2 * a * t * c + a * a * t * t)


def ring_extinction_db(d: dict, k: float, k2) -> np.ndarray:
    """Extinction at resonance; infinite at critical coupling, so the floor keeps the log finite."""
    a = 10 ** (-ring_loss_db(d, k) / 20)
    t = np.sqrt(1 - k2)
    t_min = ((a - t) / (1 - a * t)) ** 2
    return -10 * np.log10(np.maximum(t_min, 1e-12))


def ring_q(d: dict, k: float, k2) -> np.ndarray:
    """Loaded quality factor Q = pi ng L sqrt(a t) / (lam0 (1 - a t))."""
    a = 10 ** (-ring_loss_db(d, k) / 20)
    t = np.sqrt(1 - k2)
    return np.pi * float(d["ng"]) * float(d["L_ring"]) * np.sqrt(a * t) / (float(d["lam0"]) * (1 - a * t))


# =====================================================================================
# panels
# =====================================================================================
def panel_spectrum(ax, d: dict) -> None:
    """Transmission over the full span at 0 V, with the free spectral range between two resonances."""
    lam = d["full_lam"] * 1e9  # nm
    t_db = 10 * np.log10(d["full_T"])
    ax.plot(lam, t_db, color=fs.BLUE, lw=0.6)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_ylim(-50, 9)
    ax.set_yticks([-40, -30, -20, -10, 0])
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("transmission (dB)")
    # the resonances in the window: the central one (0 V) and the one a free spectral range below it
    dips = np.flatnonzero((t_db[1:-1] < t_db[:-2]) & (t_db[1:-1] <= t_db[2:]) & (t_db[1:-1] < -20)) + 1
    centre = int(dips[np.argmin(np.abs(lam[dips] - float(d["lam_res"]) * 1e9))])
    lower = int(dips[lam[dips] < lam[centre] - 1][-1])
    y_dim = 3.5
    for i in (lower, centre):  # guides run down into the notch, where the curve is at its bottom only
        ax.plot([lam[i], lam[i]], [t_db[i], y_dim], color=fs.MUTED, lw=0.4, solid_capstyle="butt")
    ax.annotate(
        "",
        xy=(lam[centre], y_dim),
        xytext=(lam[lower], y_dim),
        arrowprops=dict(arrowstyle="<->", color=fs.INK, lw=0.5, shrinkA=0, shrinkB=0, mutation_scale=5),
    )
    midpoint = (lam[lower] + lam[centre]) / 2  # the spacing is centred here
    fs.note(
        ax,
        f"measured FSR = {float(d['fsr']) * 1e9:.2f} nm\ncentred on {midpoint:.1f} nm",
        (midpoint, y_dim + 0.8),
        ha="center",
        va="bottom",
    )
    fs.note(ax, "0 V", (0.03, 0.06), transform=ax.transAxes)


def panel_zoom(ax, d: dict) -> None:
    """The central resonance at four reverse biases; the analytic ring is drawn underneath in grey."""
    lam_res = float(d["lam_res"])
    detune = (d["zoom_lam"] - lam_res) * 1e12  # pm
    k2 = kappa2(d, float(d["gap_design"]))
    colors = fs.sweep_colors(len(ZOOM_BIASES))
    handles, labels = [], []
    for volts, color in zip(ZOOM_BIASES, colors, strict=True):
        i = int(np.argmin(np.abs(d["zoom_V"] + volts)))
        dn, k = bias_row(d, volts)
        model = ring_transmission(d, d["zoom_lam"] * 1e6, dn, k, k2)
        ax.plot(detune, 10 * np.log10(model), color=fs.HAIRLINE, lw=2.2, zorder=1)  # halo under the simulated line
        (sim,) = ax.plot(detune, 10 * np.log10(d["zoom_T"][i]), color=color, lw=0.9, zorder=2)
        handles.append(sim)
        labels.append(f"{volts:g} V")
    (analytic,) = ax.plot([], [], color=fs.HAIRLINE, lw=2.2)
    handles.append(analytic)
    labels.append("analytic all-pass ring")
    ax.set_xlim(-100, 100)
    ax.set_ylim(-50, 24)  # the air above 0 dB holds the legend, clear of the notches
    ax.set_yticks([-40, -30, -20, -10, 0])
    ax.set_xlabel("detuning from the 0 V resonance (pm)")
    ax.set_ylabel("transmission (dB)")
    ax.legend(handles, labels, loc="upper right", handlelength=1.6, labelspacing=0.35)


def panel_transfer(ax, d: dict) -> None:
    """Transmission at two fixed wavelengths versus reverse bias, read from the zoom spectra."""
    bias = -d["zoom_V"]
    lam_res = float(d["lam_res"])
    half = float(d["fwhm_design"]) / 2
    on = 10 * np.log10([np.interp(lam_res, d["zoom_lam"], row) for row in d["zoom_T"]])
    off = 10 * np.log10([np.interp(lam_res + half, d["zoom_lam"], row) for row in d["zoom_T"]])
    ax.plot(bias, on, "o-", color=fs.BLUE, ms=2.5, lw=1.0)
    ax.plot(bias, off, "o-", color=fs.ORANGE, ms=2.5, lw=1.0)
    ax.set_xlim(0, 4)
    ax.set_ylim(-50, 5)
    ax.set_yticks([-40, -30, -20, -10, 0])
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_xlabel("reverse bias (V)")
    ax.set_ylabel("transmission (dB)")
    ax.text(4.08, on[-1], "at the 0 V\nresonance", fontsize=6, va="bottom", ha="left", clip_on=False)
    ax.text(4.08, off[-1], "half a linewidth\nabove it", fontsize=6, va="top", ha="left", clip_on=False)
    per_volt, v_end = endpoint_pm_per_V(d["zoom_V"], d["shift_pm"])
    fs.note(
        ax,
        f"resonance shift {per_volt:.1f} pm/V\naverage over 0 to {v_end:g} V",
        (3.85, -31),
        ha="right",
        va="center",
    )


def panel_extinction(ax, d: dict) -> None:
    """Extinction at 0 V versus gap: the simulated points, the analytic ring, and the critical gap."""
    k0 = bias_row(d, 0.0)[1]
    grid = np.linspace(0.23, 0.54, 3000)  # um
    ax.plot(grid * 1000, ring_extinction_db(d, k0, kappa2(d, grid)), color=fs.MUTED, lw=0.8, zorder=1)
    ax.plot(d["gaps"] * 1000, d["ext_dB"], "o", color=fs.BLUE, ms=3.0, zorder=3)
    gap_crit = float(d["gap_critical"]) * 1000
    ax.axvline(gap_crit, color=fs.ORANGE, lw=0.6, zorder=0)
    ax.set_xlim(230, 540)
    ax.set_ylim(0, 52)
    ax.set_yticks([0, 10, 20, 30, 40, 50])
    ax.set_xlabel("gap (nm)")
    ax.set_ylabel("extinction (dB)")
    fs.note(
        ax,
        f"critical coupling\nat gap {gap_crit:.0f} nm\nκ² = {float(d['k2_critical']):.4f}",
        (gap_crit - 35, 36),
        ha="right",
        va="center",
    )


def panel_bandwidth(ax, d: dict) -> None:
    """Loaded Q versus gap, and the bandwidth budget at the design gap."""
    k0 = bias_row(d, 0.0)[1]
    grid = np.linspace(0.23, 0.54, 600)  # um
    ax.plot(grid * 1000, ring_q(d, k0, kappa2(d, grid)) / 1e3, color=fs.MUTED, lw=0.8, zorder=1)
    ax.plot(d["gaps"] * 1000, d["Q"] / 1e3, "o", color=fs.BLUE, ms=3.0, zorder=3)
    ax.set_xlim(230, 540)
    ax.set_ylim(0, 66)
    ax.set_yticks([0, 20, 40, 60])
    ax.set_xlabel("gap (nm)")
    ax.set_ylabel("loaded Q (×10³)")
    fs.note(
        ax,
        "at the design gap, "
        f"{float(d['gap_design']) * 1000:.0f} nm\n"
        f"Q = {float(d['Q_design']):,.0f}, linewidth {float(d['fwhm_design']) * 1e12:.1f} pm\n"
        f"linewidth {float(d['f_photon']) / 1e9:.1f} GHz (photon lifetime)\n"
        f"RC bandwidth {float(d['f_RC']) / 1e9:.0f} GHz",
        (0.03, 0.97),
        ha="left",
        va="top",
        transform=ax.transAxes,
    )


def panel_heater(ax, d: dict) -> None:
    """Transmission for the four heater powers; one order, with all four resonances in the window."""
    lam = d["full_lam"] * 1e9  # nm
    res = float(d["lam_res"]) * 1e9
    shifts = d["heat_shift_pm"] / 1000  # nm
    lo, hi = res - 1.0, res + shifts.max() + 0.9
    win = (lam > lo) & (lam < hi)
    colors = fs.sweep_colors(len(HEAT_KEYS), fs.CMAP_SWEEP_WARM)
    for power, key, color in zip(d["heater_mW"], HEAT_KEYS, colors, strict=True):
        t_db = 10 * np.log10(d[key][win])
        x = lam[win]
        ax.plot(x, t_db, color=color, lw=1.3)
        i = int(np.argmin(t_db))
        # the leader starts at the top of the notch: a point below the axis would hide the whole label
        fs.note(ax, f"{power:g} mW", (x[i], -1.0), xytext=(x[i], 2.5), ha="center", va="bottom")
    ax.set_xlim(lo, hi)
    ax.set_ylim(-50, 16)
    ax.set_yticks([-40, -30, -20, -10, 0])
    ax.set_xticks(np.arange(np.ceil(lo), hi, 1.0))
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel("transmission (dB)")
    pm_per_mW = float(d["thermal_pm_per_mW"])
    fsr = design_fsr(d)
    fsr_mW = fsr * 1e12 / pm_per_mW
    fs.note(
        ax,
        f"heater tuning {pm_per_mW:.0f} pm/mW\none FSR at {res:.1f} nm ({fsr * 1e9:.2f} nm) = {fsr_mW:.0f} mW",
        (lo + 0.05, 8.5),
        ha="left",
        va="bottom",
    )


def main() -> None:
    d = load()
    fig, axes = fs.mosaic(fs.DOUBLE, 118, [["a", "b", "c"], ["d", "e", "f"]])
    panel_spectrum(axes["a"], d)
    panel_zoom(axes["b"], d)
    panel_transfer(axes["c"], d)
    panel_extinction(axes["d"], d)
    panel_bandwidth(axes["e"], d)
    panel_heater(axes["f"], d)
    for key, ax in axes.items():
        fs.panel_label(ax, key)
    fs.save(fig, Path(__file__).with_name("fig6_circuit.png"))


if __name__ == "__main__":
    main()

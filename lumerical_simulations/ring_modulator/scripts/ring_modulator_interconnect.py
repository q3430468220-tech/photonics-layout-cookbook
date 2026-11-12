"""Step 6 - INTERCONNECT: the ring modulator as a circuit element, built from the results of steps 1-5.

    step 1  kappa^2(gap)          -> coupling coefficient
    step 2  n_eff, n_g, bend loss -> effective index, group index, part of the loss
    step 3  C(V), Rs              -> RC bandwidth (reported next to the photon-lifetime bandwidth)
    step 5  d n_eff(V), loss(V)   -> the "measurement" table of the element, scaled to the doped fraction
    step 5  d n_eff per mW        -> shift of the effective index with heater power
    step 5  n_eff(0 V) - n_eff(no carriers) -> index of the element at 0 V, scaled to the doped fraction

The element is INTERCONNECT's "Optical Ring Modulator" driven by a DC source and measured with an
optical network analyser.  Its interface, as verified against the analytic all-pass ring:
``coupling coefficient 1`` is the *power* coupling kappa^2, ``loss`` is in dB/m, and the third column
of the measurement table is the *imaginary* part of the index.

    1. gap sweep at 0 V                 -> extinction, Q and photon-lifetime bandwidth versus gap, critical coupling
    2. voltage sweep at the design gap  -> spectra, resonance shift, modulation depth
    3. heater sweep at the design gap   -> thermal tuning

The samples are on a 0.4 pm grid, so the resonance positions, minima and widths are refined from them
(see spectrum_stats).  The absolute resonance wavelength is only as good as the absolute index.  Steps 2 and 5
use the same mesh over the rib and agree to a few 1e-5; the index itself is good to about 5e-4, which is
0.2 nm in the resonance.  So the wavelength axis is the element's reference.  The results of this step are
differences: shifts,
tuning rates, and Q and extinction at a given gap.

    python ring_modulator_interconnect.py                 # design gap = the swept gap with the highest extinction
    python ring_modulator_interconnect.py --gap 0.31

Output in 6_interconnect_ring_modulator/:  ring_modulator.icp / .npz / .txt
"""

from __future__ import annotations

import argparse
import csv
import math
import time

import numpy as np
from common import C0, L_HEATER, L_PN, L_RING, LAM, RADIUS, ROOT, import_lumapi, step_dir, um

OUT = step_dir("6_interconnect_ring_modulator")
# Scattering loss of the undoped rib waveguide.  Baehr-Jones et al. (arXiv:1203.0767) measured
# 2.2 +- 0.8 dB/cm on average for the 0.5 um rib waveguide of the process this PDK's numbers come from.
PASSIVE_LOSS_DBCM = 2.2
SPAN_HZ = 2.6e12  # about 21 nm around 1.55 um: two free spectral ranges of the R = 10 um ring
POINTS = 52001
ZOOM_NM = 0.6  # half-width of the window kept around the resonance for the voltage sweep
FLOOR = 1e-6  # smallest transmission a fitted minimum may take (-60 dB); a fit at or below it is a lower bound
DB = 10 / math.log(10)


def load_inputs() -> dict:
    d = {}
    with open(ROOT / "1_coupling_coefficient" / "coupling_vs_gap.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    gaps = np.array([float(r["gap_um"]) for r in rows])
    kappa2 = np.array([float(r["kappa2"]) for r in rows])
    slope, intercept = np.polyfit(gaps, np.log(kappa2), 1)
    d["k2_A"], d["k2_g0"] = math.exp(intercept), -1 / slope  # kappa^2 = A exp(-gap / g0), gap in um
    passive = np.load(ROOT / "2_passive_mode_properties" / "rib_passive.npz")
    d["neff"], d["ng"] = float(passive["ring_neff"]), float(passive["ring_ng"])
    d["bend_dB_turn"] = max(float(passive["ring_loss_dBcm"]) * L_RING * 1e-4, 0.0)
    active = np.load(ROOT / "5_active_mode_properties" / "active.npz")
    d["V"], d["dneff"], d["loss_dBcm"] = active["V"], active["dneff"], active["loss_dBcm"]
    d["dneff_dP"] = float(active["dneff_dP_section"])
    d["V5"], d["shift5_pm"] = active["V"], active["shift_pm"]  # the step-5 shifts, printed beside the circuit's
    # The element's index at 0 V is the step-2 ring index plus the carrier change of the doped fraction.
    # Step 2 (undoped bent rib) and step 5 (bent rib, no carriers) agree to a few 1e-5 (active.npz, base_minus_passive).
    # The index itself is good to about 5e-4, and the absolute wavelength no better: use the differences of this step.
    d["neff0V_minus_base"] = neff0V_minus_base(active)
    d["neff_element"] = d["neff"] + L_PN / L_RING * d["neff0V_minus_base"]
    charge = np.load(ROOT / "3_charge_profile" / "pn_rib_charge.npz")
    if "C_V" in charge:
        order = np.argsort(charge["V"])
        d["rc_V"], d["f_RC_V"] = charge["V"][order], charge["f_RC"][order]
        k0 = int(np.argmax(charge["V"]))
        d["C0_fF"], d["Rs"], d["f_RC"] = float(charge["C_V"][k0]) * 1e15, float(charge["Rs_V"][k0]), float(charge["f_RC"][k0])
    return d


def neff0V_minus_base(active) -> float:
    """n_eff at 0 V with carriers minus n_eff without carriers, for the doped bent rib of step 5.

    Read from the key step 5 stores; a file without it is evaluated from the sweep: neff at V = 0 minus base_neff.
    """
    if "neff0V_minus_base" in active.files:
        return float(active["neff0V_minus_base"])
    k0 = int(np.argmin(np.abs(active["V"])))
    return float(active["neff"][k0] - active["base_neff"])


def kappa2(gap_um, d: dict):
    return d["k2_A"] * np.exp(-np.asarray(gap_um) / d["k2_g0"])


def measurement_table(d: dict) -> np.ndarray:
    """[V, d n, k] for the whole ring: only the doped fraction of the ring carries the junction."""
    order = np.argsort(d["V"])
    fraction = L_PN / L_RING
    dn = d["dneff"][order] * fraction
    alpha = d["loss_dBcm"][order] * 100 / DB  # dB/cm -> 1/m (power)
    k = alpha * LAM * um / (4 * math.pi) * fraction
    return np.c_[d["V"][order], dn, k]


def refine_minimum(lam: np.ndarray, T: np.ndarray, k: int) -> tuple[float, float]:
    """Minimum of the parabola through sample k and its two neighbours: (wavelength in m, transmission).

    The fit is made in pm from sample k so that the coefficients are well scaled.  If the three points do not
    bracket a minimum, the sample itself is returned.
    """
    x = (lam[k - 1 : k + 2] - lam[k]) * 1e12  # pm
    a, b, c = np.polyfit(x, T[k - 1 : k + 2], 2)
    x_min = -b / (2 * a) if a > 0 else np.nan
    if not x[0] <= x_min <= x[2]:
        return float(lam[k]), float(T[k])
    return float(lam[k] + x_min * 1e-12), float(c - b * b / (4 * a))


def half_depth_crossings(lam: np.ndarray, T: np.ndarray, k: int, half: float) -> tuple[float, float]:
    """Wavelengths where the transmission crosses `half` on either side of sample k, by linear interpolation."""
    i = k
    while i > 0 and T[i - 1] < half:
        i -= 1
    j = k
    while j < len(T) - 1 and T[j + 1] < half:
        j += 1
    if i == 0 or j == len(T) - 1:  # the half-depth level is not reached inside the sweep
        return np.nan, np.nan
    lam_l = lam[i - 1] + (T[i - 1] - half) / (T[i - 1] - T[i]) * (lam[i] - lam[i - 1])
    lam_r = lam[j] + (half - T[j]) / (T[j + 1] - T[j]) * (lam[j + 1] - lam[j])
    return float(lam_l), float(lam_r)


def spectrum_stats(lam: np.ndarray, T: np.ndarray, target: float | None = None) -> dict:
    """Resonance nearest `target` (default: the centre of the sweep): position, extinction, linewidth and Q.

    The samples sit on a 0.4 pm grid, which is coarse against a 50 pm linewidth and too coarse for the depth
    near critical coupling.  The position and the minimum therefore come from a parabola through the lowest
    sample and its two neighbours, in linear transmission, and the linewidth from linear interpolation of the
    two half-depth crossings.  A minimum at or below FLOOR is clipped to it and the extinction is then a lower
    bound ("more than X dB").  The free spectral range is the mean spacing of the refined dips in the sweep.
    """
    order = np.argsort(lam)
    lam, T = lam[order], T[order]
    dips = [i for i in range(1, len(T) - 1) if T[i] < T[i - 1] and T[i] <= T[i + 1] and T[i] < 0.9 * T.max()]
    if not dips:
        return dict(lam_res=np.nan, ext_dB=0.0, ext_limit=False, fwhm=np.nan, Q=np.nan, fsr=np.nan, fsr_centre=np.nan)
    goal = lam[len(lam) // 2] if target is None else target
    k = min(dips, key=lambda i: abs(lam[i] - goal))
    lam_res, t_min = refine_minimum(lam, T, k)
    t_max = T.max()
    limit = t_min < FLOOR
    t_min = max(t_min, FLOOR)
    lam_l, lam_r = half_depth_crossings(lam, T, k, (t_max + t_min) / 2)
    fwhm = lam_r - lam_l
    centres = [refine_minimum(lam, T, i)[0] for i in dips]
    fsr = float(np.mean(np.diff(centres))) if len(dips) > 1 else np.nan
    fsr_centre = (centres[0] + centres[-1]) / 2 if len(dips) > 1 else np.nan  # centre of the spacing
    return dict(
        lam_res=lam_res,
        ext_dB=-10 * math.log10(t_min / t_max),
        ext_limit=bool(limit),
        fwhm=fwhm,
        Q=lam_res / fwhm,
        fsr=fsr,
        fsr_centre=fsr_centre,
    )


def extinction_text(s: dict) -> str:
    """Extinction in dB, as a lower bound when the fitted minimum reached the floor."""
    return f"more than {s['ext_dB']:.0f}" if s["ext_limit"] else f"{s['ext_dB']:.1f}"


def photon_bandwidth(lam_res: float, Q: float) -> float:
    """c / (lambda Q) = 1 / (2 pi tau_photon), in Hz: the linewidth in frequency.

    This is the usual photon-lifetime estimate of the optical bandwidth.  The exact small-signal response depends
    on the laser detuning; on resonance its pole lies at half this value.
    """
    return C0 / (lam_res * Q)


def cascade_3db(f1: float, f2: float) -> float:
    """Frequency where two cascaded first-order responses, (1 + (f/f1)^2)(1 + (f/f2)^2), fall to one half.

    The equation is quadratic in f^2 and is solved exactly: x = 2 / (s + sqrt(s^2 + 4 / (f1^2 f2^2))) with
    x = f^2 and s = 1/f1^2 + 1/f2^2.  It is the -3 dB point of this cascade and not a general rule.
    """
    s = 1 / f1**2 + 1 / f2**2
    return math.sqrt(2 / (s + math.sqrt(s * s + 4 / (f1**2 * f2**2))))


def allpass_extinction_db(loss_db_rt: float, k2: float) -> float:
    """Extinction at resonance of the all-pass ring: T_min = ((a - t) / (1 - a t))^2, a = round-trip amplitude."""
    a = 10 ** (-loss_db_rt / 20)
    t = math.sqrt(1 - k2)
    return -10 * math.log10(max(((a - t) / (1 - a * t)) ** 2, 1e-12))


def endpoint_pm_per_V(volts: np.ndarray, shift_pm: np.ndarray) -> tuple[float, float]:
    """End-point average of the resonance shift per volt: the shift at the highest reverse bias divided by that bias.

    Returns (pm/V, the bias in V as a positive number).
    """
    k = int(np.argmin(volts))
    v_end = -float(volts[k])
    return float(shift_pm[k]) / v_end, v_end


def heater_dn(d: dict, heater_mW: float) -> float:
    """Index change of the ring from the heater: the step-5 change per mW times the heated fraction of the ring."""
    return float(d["dneff_dP"]) * heater_mW * L_HEATER / L_RING


def heater_shift_m(d: dict, heater_mW: float, lam_m: float) -> float:
    """Predicted resonance shift (m): shift = dn x heated fraction x lambda / n_g."""
    return heater_dn(d, heater_mW) * lam_m / float(d["ng"])


class Ring:
    """The INTERCONNECT circuit: network analyser -> ring modulator -> network analyser, DC source on the junction."""

    def __init__(self, ic, d: dict, loss_dB_m: float, table: np.ndarray):
        self.ic, self.d = ic, d
        ic.addelement("Optical Network Analyzer")
        ic.set("name", "ONA")
        ic.set("center frequency", C0 / (LAM * um))
        ic.set("frequency range", SPAN_HZ)
        ic.set("number of points", POINTS)
        ic.addelement("Optical Ring Modulator")
        ic.set("name", "RING")
        ic.set("length", L_RING * um)
        ic.set("frequency", C0 / (LAM * um))
        ic.set("effective index", d["neff_element"])
        ic.set("group index", d["ng"])
        ic.set("loss", loss_dB_m)
        ic.set("coupling coefficient 2", 0.0)
        ic.set("measurement type", "effective index")
        ic.set("measurement", table)
        ic.addelement("DC Source")
        ic.set("name", "DC")
        ic.connect("ONA", "output", "RING", "port 1")
        ic.connect("RING", "port 2", "ONA", "input 1")
        ic.connect("DC", "output", "RING", "modulation")

    def spectrum(self, gap_um: float, volts: float = 0.0, heater_mW: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        ic = self.ic
        ic.switchtodesign()  # element properties can only be changed in design mode
        ic.select("RING")
        ic.set("coupling coefficient 1", float(kappa2(gap_um, self.d)))
        ic.set("effective index", self.d["neff_element"] + heater_dn(self.d, heater_mW))
        ic.select("DC")
        ic.set("amplitude", float(volts))
        ic.run()
        r = ic.getresult("ONA", "input 1/mode 1/transmission")
        lam, T = np.ravel(r["wavelength"]), np.abs(np.ravel(r["TE transmission"])) ** 2
        order = np.argsort(lam)
        return lam[order], T[order]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--gaps", type=float, nargs="*", default=[0.25, 0.28, 0.31, 0.34, 0.37, 0.40, 0.43, 0.47, 0.52], help="gap sweep (um)"
    )
    ap.add_argument("--gap", type=float, default=None, help="design gap (um); default: the swept gap with the highest extinction")
    ap.add_argument("--volts", type=float, nargs="*", default=[0.0, -1.0, -2.0, -4.0], help="bias points listed in the summary")
    ap.add_argument("--heater", type=float, nargs="*", default=[0.0, 5.0, 10.0, 20.0], help="heater power (mW)")
    a = ap.parse_args()
    lumapi = import_lumapi()
    t0 = time.time()
    d = load_inputs()
    table = measurement_table(d)
    scatter_turn = PASSIVE_LOSS_DBCM * L_RING * 1e-4
    passive_turn = scatter_turn + d["bend_dB_turn"]
    carrier_turn = float(table[np.argmax(table[:, 0]), 2]) * 4 * math.pi / (LAM * um) * L_RING * um * DB  # at 0 V
    total_turn = passive_turn + carrier_turn
    k2_critical = 1 - 10 ** (-total_turn / 10)
    gap_critical = -d["k2_g0"] * math.log(k2_critical / d["k2_A"])
    lines = [
        f"Ring modulator: R = {RADIUS} um, circumference {L_RING:.2f} um, doped arc {L_PN:.2f} um, heater filament {L_HEATER:.2f} um",
        f"kappa^2(gap) = {d['k2_A']:.3f} exp(-gap / {d['k2_g0'] * 1000:.1f} nm)  [step 1]     n_eff = {d['neff']:.5f}, n_g = {d['ng']:.4f}  [step 2]",
        f"element index at 0 V = {d['neff_element']:.5f} = {d['neff']:.5f} + doped fraction {L_PN / L_RING:.3f} x "
        f"({d['neff0V_minus_base']:+.6f}, n_eff(0 V) - n_eff(no carriers))  [steps 2, 5]",
        f"round-trip loss at 0 V: scattering {PASSIVE_LOSS_DBCM} dB/cm -> {scatter_turn:.4f} dB, "
        f"bend radiation {d['bend_dB_turn']:.4f} dB, free carriers {carrier_turn:.4f} dB  =  {total_turn:.4f} dB",
        f"critical coupling: kappa^2 = 1 - 10^(-loss/10) = {k2_critical:.4f}  ->  gap = {gap_critical * 1000:.0f} nm",
    ]
    print("\n".join(lines), flush=True)
    res = dict(table=table, k2_A=d["k2_A"], k2_g0=d["k2_g0"], total_turn_dB=total_turn, scatter_turn_dB=scatter_turn,
               carrier_turn_dB=carrier_turn, bend_turn_dB=d["bend_dB_turn"], k2_critical=k2_critical, gap_critical=gap_critical,
               gaps=np.array(a.gaps), volts=np.array(a.volts), heater_mW=np.array(a.heater), neff=d["neff"], ng=d["ng"],
               neff_element=d["neff_element"], neff0V_minus_base=d["neff0V_minus_base"],
               L_ring=L_RING, lam0=LAM)  # fmt: skip

    with lumapi.INTERCONNECT(hide=True) as ic:
        ring = Ring(ic, d, passive_turn / (L_RING * um), table)

        # ---- 1. gap sweep at 0 V ----
        ext, Q, ext_lim = [], [], []
        lines.append(
            f"\n{'gap (nm)':>9} {'kappa^2':>8} {'extinction dB':>16} {'loaded Q':>9} {'linewidth pm':>13} {'c/(lam Q) GHz':>14}"
        )
        for gap in a.gaps:
            s = spectrum_stats(*ring.spectrum(gap))
            ext.append(s["ext_dB"])
            ext_lim.append(s["ext_limit"])
            Q.append(s["Q"])
            lines.append(
                f"{gap * 1000:9.0f} {float(kappa2(gap, d)):8.4f} {extinction_text(s):>16} {s['Q']:9.0f} {s['fwhm'] * 1e12:13.1f} "
                f"{photon_bandwidth(s['lam_res'], s['Q']) / 1e9:14.1f}"
            )
            print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)
        res.update(ext_dB=np.array(ext), ext_limit=np.array(ext_lim), Q=np.array(Q))
        gap = a.gap if a.gap is not None else float(a.gaps[int(np.argmax(ext))])
        res["gap_design"] = gap
        summary_start = len(lines)

        # ---- 2. voltage sweep at the design gap: every bias point of the measurement table ----
        lam, T0 = ring.spectrum(gap)
        s0 = spectrum_stats(lam, T0)
        lam0 = s0["lam_res"]
        fsr_design = lam0**2 / (d["ng"] * L_RING * um)  # lambda^2 / (n_g L): the FSR at the design resonance
        res.update(full_lam=lam, full_T=T0)
        zoom = np.abs(lam - lam0) < ZOOM_NM * 1e-9
        volts_all = np.sort(table[:, 0])[::-1]  # 0 -> most negative
        zoom_T, shift, ext_v = [], [], []
        for v in volts_all:
            lam_v, T_v = ring.spectrum(gap, volts=v)
            sv = spectrum_stats(lam_v[zoom], T_v[zoom], target=lam0)
            zoom_T.append(T_v[zoom])
            shift.append((sv["lam_res"] - lam0) * 1e12)
            ext_v.append(sv["ext_dB"])
        zoom_T = np.array(zoom_T)
        per_volt, v_end = endpoint_pm_per_V(volts_all, np.array(shift))
        per_volt5, v5_end = endpoint_pm_per_V(d["V5"], d["shift5_pm"])
        res.update(zoom_lam=lam[zoom], zoom_T=zoom_T, zoom_V=volts_all, shift_pm=np.array(shift), ext_V=np.array(ext_v),
                   shift_per_V_pm=per_volt, shift_per_V_end_V=v_end)  # fmt: skip
        k2_design = float(kappa2(gap, d))
        lines.append(
            f"\ndesign gap {gap * 1000:.0f} nm (kappa^2 = {k2_design:.4f}):  loaded Q = {s0['Q']:.0f}, "
            f"linewidth {s0['fwhm'] * 1e12:.1f} pm, extinction {extinction_text(s0)} dB"
        )
        lines.append(
            f"measured spacing of the two resonances {s0['fsr'] * 1e9:.2f} nm, centred on {s0['fsr_centre'] * 1e9:.1f} nm; "
            f"lambda^2 / (n_g L) at the design resonance ({lam0 * 1e9:.2f} nm) = {fsr_design * 1e9:.2f} nm"
        )
        lines.append(
            f"{'V':>6} {'shift pm':>10} {'step 5 shift pm':>16} {'extinction dB':>14} {'T at the 0 V resonance, dB':>27}"
        )
        k_res = int(np.argmin(np.abs(lam[zoom] - lam0)))
        order5 = np.argsort(d["V5"])
        for v in a.volts:
            k = int(np.argmin(np.abs(volts_all - v)))
            s5 = float(np.interp(volts_all[k], d["V5"][order5], d["shift5_pm"][order5]))
            lines.append(
                f"{volts_all[k]:6.1f} {shift[k]:10.1f} {s5:16.1f} {ext_v[k]:14.1f} "
                f"{10 * math.log10(max(zoom_T[k, k_res], 1e-12)):27.2f}"
            )
        lines.append(
            f"resonance shift per volt, end-point average 0 to {v_end:g} V: {per_volt:.1f} pm/V "
            f"(step 5: {per_volt5:.1f} pm/V over 0 to {v5_end:g} V)"
        )
        f_photon = photon_bandwidth(lam0, s0["Q"])
        res.update(
            Q_design=s0["Q"], fwhm_design=s0["fwhm"], fsr=s0["fsr"], fsr_centre=s0["fsr_centre"], fsr_design=fsr_design,
            f_photon=f_photon, lam_res=lam0, ext_design=s0["ext_dB"], ext_design_limit=s0["ext_limit"],
        )  # fmt: skip
        k2_sens = [allpass_extinction_db(total_turn, k2_design * (1 + x)) for x in (-0.01, 0.0, 0.01)]
        lines.append(
            "near critical coupling the depth is very sensitive: the analytic all-pass ring with this loss and kappa^2 "
            f"changed by -1 %, 0 and +1 % has extinction {k2_sens[0]:.1f}, {k2_sens[1]:.1f} and {k2_sens[2]:.1f} dB"
        )
        lines.append(
            f"photon-lifetime estimate of the optical bandwidth: c / (lambda Q) = 1 / (2 pi tau_photon) = {f_photon / 1e9:.1f} GHz "
            "(the linewidth in frequency; the exact small-signal response depends on the laser detuning, "
            "and on resonance its pole lies at half this value)"
        )
        if "f_RC" in d:
            f_total = cascade_3db(f_photon, d["f_RC"])
            res.update(f_RC=d["f_RC"], f_total=f_total)
            lines.append(
                f"electrical: C = {d['C0_fF']:.1f} fF, Rs = {d['Rs']:.0f} ohm at 0 V -> intrinsic f_RC = {d['f_RC'] / 1e9:.0f} GHz  [step 3]"
            )
            lines.append(
                f"-3 dB point of the cascade (1 + (f/f1)^2)(1 + (f/f2)^2) = 2, f1 = photon-lifetime bandwidth, f2 = f_RC: "
                f"{f_total / 1e9:.1f} GHz (exact solution of this equation for two first-order responses, not a general rule)"
            )

        # ---- 3. heater sweep at the design gap ----
        lines.append(f"\n{'heater mW':>10} {'predicted pm':>13} {'resonance shift pm':>19}")
        shifts, predicted = [], []
        for power in a.heater:
            lam_p, T_p = ring.spectrum(gap, heater_mW=power)
            pred_m = heater_shift_m(d, power, lam0)
            target = lam0 + pred_m
            if not lam_p[0] <= target <= lam_p[-1]:
                raise SystemExit(
                    f"heater {power:g} mW: the predicted resonance at {target * 1e9:.2f} nm is outside the simulated span "
                    f"{lam_p[0] * 1e9:.2f} to {lam_p[-1] * 1e9:.2f} nm; use a lower heater power or a wider SPAN_HZ"
                )
            sp = spectrum_stats(lam_p, T_p, target=target)
            if not abs(sp["lam_res"] - target) <= fsr_design / 4:
                raise SystemExit(
                    f"heater {power:g} mW: no resonance within a quarter FSR ({fsr_design / 4 * 1e9:.2f} nm) of the predicted "
                    f"{target * 1e9:.2f} nm (nearest dip {sp['lam_res'] * 1e9:.2f} nm); the prediction and the simulation disagree"
                )
            shifts.append((sp["lam_res"] - lam0) * 1e12)
            predicted.append(pred_m * 1e12)
            lines.append(f"{power:10.1f} {predicted[-1]:13.1f} {shifts[-1]:19.1f}")
            res[f"heat_T_P{power:.0f}"] = T_p
        res.update(heat_shift_pm=np.array(shifts), heat_pred_pm=np.array(predicted))
        positive = [(p, s) for p, s in zip(a.heater, shifts, strict=True) if p > 0]
        if positive:
            rate = float(np.mean([s / p for p, s in positive]))
            lines.append(
                f"thermal tuning {rate:.1f} pm/mW; one FSR at the design resonance ({fsr_design * 1e9:.2f} nm) "
                f"needs {fsr_design * 1e12 / rate:.0f} mW"
            )
            res["thermal_pm_per_mW"] = rate
        ic.switchtodesign()
        ic.save(str(OUT / "ring_modulator.icp"))

    np.savez_compressed(OUT / "ring_modulator.npz", **res)
    (OUT / "ring_modulator.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[summary_start:]))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

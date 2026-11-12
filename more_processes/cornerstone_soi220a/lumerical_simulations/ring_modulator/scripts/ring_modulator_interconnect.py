"""Step 6 - INTERCONNECT: the ring modulator as a circuit element, built from the results of steps 1-5.

    step 1  kappa^2(gap)          -> coupling coefficient
    step 2  n_eff, n_g, bend loss -> effective index, group index, part of the loss
    step 3  C(V), Rs              -> RC bandwidth (reported next to the optical bandwidth)
    step 5  d n_eff(V), loss(V)   -> the "measurement" table of the element, scaled to the doped fraction
    step 5  d n_eff per mW        -> shift of the effective index with heater power

The element is INTERCONNECT's "Optical Ring Modulator" driven by a DC source and measured with an
optical network analyser.  Its interface, as verified against the analytic all-pass ring:
``coupling coefficient 1`` is the *power* coupling kappa^2, ``loss`` is in dB/m, and the third column
of the measurement table is the *imaginary* part of the index.

    1. gap sweep at 0 V               -> extinction and Q versus gap, critical coupling
    2. voltage sweep at the design gap -> spectra, resonance shift, modulation depth
    3. heater sweep at the design gap  -> thermal tuning

    python ring_modulator_interconnect.py                 # design gap = the one closest to critical coupling
    python ring_modulator_interconnect.py --gap 0.40

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
# Propagation loss of the undoped rib waveguide.  [DG Table 4] guarantees "< 4 dB/cm" for the TE mode;
# the upper bound is used.  Replace it with a measured value when you have one.
PASSIVE_LOSS_DBCM = 4.0
SPAN_HZ = 1.5e12  # about 12 nm around 1.55 um: three resonances of the R = 25 um ring
POINTS = 30001
DB = 10 / math.log(10)


def load_inputs() -> dict:
    d = {}
    with open(ROOT / "1_coupling_coefficient" / "coupling_vs_gap.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    gaps = np.array([float(r["gap_um"]) for r in rows])
    kappa2 = np.array([float(r["kappa2_S41"]) for r in rows])
    slope, intercept = np.polyfit(gaps, np.log(kappa2), 1)
    d["k2_A"], d["k2_g0"] = math.exp(intercept), -1 / slope  # kappa^2 = A exp(-gap / g0), gap in um
    passive = np.load(next((ROOT / "2_passive_mode_properties").glob("*_passive.npz")))
    d["neff"], d["ng"] = float(passive["neff"]), float(passive["ng"])
    radii = passive["radii"]
    d["bend_dB_turn"] = max(float(np.interp(RADIUS, radii, np.nan_to_num(passive["bend_loss_dB_turn"]))), 0.0)
    active = np.load(ROOT / "5_active_mode_properties" / "active.npz")
    d["V"], d["dneff"], d["loss_dBcm"] = active["V"], active["dneff"], active["loss_dBcm"]
    d["dneff_dP"] = float(active["dneff_dP_section"])
    charge = np.load(ROOT / "3_charge_profile" / "pn_rib_charge.npz")
    if "C_V" in charge:
        k0 = int(np.argmax(charge["V"]))
        d["C0_fF"], d["Rs"], d["f_RC"] = float(charge["C_V"][k0]) * 1e15, float(charge["Rs_V"][k0]), float(charge["f_RC"][k0])
    return d


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


def spectrum_stats(lam: np.ndarray, T: np.ndarray) -> dict:
    """Wavelength, extinction, linewidth and Q of the resonance nearest the centre of the sweep."""
    order = np.argsort(lam)
    lam, T = lam[order], T[order]
    dips = [i for i in range(1, len(T) - 1) if T[i] < T[i - 1] and T[i] <= T[i + 1] and T[i] < 0.9 * T.max()]
    if not dips:
        return dict(lam_res=np.nan, ext_dB=0.0, fwhm=np.nan, Q=np.nan, fsr=np.nan)
    k = min(dips, key=lambda i: abs(lam[i] - lam[len(lam) // 2]))
    half = (T.max() + T[k]) / 2
    i = j = k
    while i > 0 and T[i - 1] < half:
        i -= 1
    while j < len(T) - 1 and T[j + 1] < half:
        j += 1
    fwhm = lam[j] - lam[i]
    fsr = float(np.mean(np.diff(lam[dips]))) if len(dips) > 1 else np.nan
    return dict(lam_res=lam[k], ext_dB=-10 * math.log10(max(T[k] / T.max(), 1e-12)), fwhm=fwhm, Q=lam[k] / fwhm, fsr=fsr)


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
        ic.set("effective index", d["neff"])
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
        ic.set("effective index", self.d["neff"] + self.d["dneff_dP"] * heater_mW * L_HEATER / L_RING)
        ic.select("DC")
        ic.set("amplitude", float(volts))
        ic.run()
        r = ic.getresult("ONA", "input 1/mode 1/transmission")
        return np.ravel(r["wavelength"]), np.abs(np.ravel(r["TE transmission"])) ** 2


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gaps", type=float, nargs="*", default=[0.30, 0.34, 0.38, 0.42, 0.46, 0.50, 0.54], help="gap sweep (um)")
    ap.add_argument("--gap", type=float, default=None, help="design gap (um); default: the swept gap with the highest extinction")
    ap.add_argument("--volts", type=float, nargs="*", default=[0.0, -1.0, -2.0, -4.0])
    ap.add_argument("--heater", type=float, nargs="*", default=[0.0, 10.0, 20.0, 40.0], help="heater power (mW)")
    a = ap.parse_args()
    lumapi = import_lumapi()
    t0 = time.time()
    d = load_inputs()
    table = measurement_table(d)
    passive_turn = PASSIVE_LOSS_DBCM * L_RING * 1e-4 + d["bend_dB_turn"]
    carrier_turn = float(table[np.argmax(table[:, 0]), 2]) * 4 * math.pi / (LAM * um) * L_RING * um * DB  # at 0 V
    total_turn = passive_turn + carrier_turn
    k2_critical = 1 - 10 ** (-total_turn / 10)
    gap_critical = -d["k2_g0"] * math.log(k2_critical / d["k2_A"])
    lines = [
        f"Ring modulator: R = {RADIUS} um, circumference {L_RING:.2f} um, doped arc {L_PN:.2f} um, heated arc {L_HEATER:.2f} um",
        f"kappa^2(gap) = {d['k2_A']:.3f} exp(-gap / {d['k2_g0'] * 1000:.1f} nm)  [step 1]     n_eff = {d['neff']:.5f}, n_g = {d['ng']:.4f}  [step 2]",
        f"round-trip loss at 0 V: waveguide {PASSIVE_LOSS_DBCM} dB/cm -> {PASSIVE_LOSS_DBCM * L_RING * 1e-4:.4f} dB, "
        f"bend radiation {d['bend_dB_turn']:.4f} dB, free carriers {carrier_turn:.4f} dB  =  {total_turn:.4f} dB",
        f"critical coupling: kappa^2 = 1 - 10^(-loss/10) = {k2_critical:.4f}  ->  gap = {gap_critical * 1000:.0f} nm",
    ]
    print("\n".join(lines), flush=True)
    res = dict(
        table=table,
        k2_A=d["k2_A"],
        k2_g0=d["k2_g0"],
        total_turn_dB=total_turn,
        k2_critical=k2_critical,
        gap_critical=gap_critical,
        gaps=np.array(a.gaps),
        volts=np.array(a.volts),
        heater_mW=np.array(a.heater),
    )

    with lumapi.INTERCONNECT(hide=True) as ic:
        ring = Ring(ic, d, passive_turn / (L_RING * um), table)

        # ---- 1. gap sweep at 0 V ----
        ext, Q = [], []
        lines.append(f"\n{'gap (nm)':>9} {'kappa^2':>8} {'extinction dB':>14} {'loaded Q':>9} {'linewidth pm':>13}")
        for gap in a.gaps:
            s = spectrum_stats(*ring.spectrum(gap))
            ext.append(s["ext_dB"])
            Q.append(s["Q"])
            lines.append(
                f"{gap * 1000:9.0f} {float(kappa2(gap, d)):8.4f} {s['ext_dB']:14.1f} {s['Q']:9.0f} {s['fwhm'] * 1e12:13.1f}"
            )
            print(lines[-1], f"({time.time() - t0:.0f} s)", flush=True)
        res.update(ext_dB=np.array(ext), Q=np.array(Q))
        gap = a.gap if a.gap is not None else float(a.gaps[int(np.argmax(ext))])
        res["gap_design"] = gap

        # ---- 2. voltage sweep at the design gap ----
        spectra_v = {v: ring.spectrum(gap, volts=v) for v in a.volts}
        stats_v = {v: spectrum_stats(*s) for v, s in spectra_v.items()}
        s0 = stats_v[max(a.volts)]
        lam0 = s0["lam_res"]
        lines.append(
            f"\ndesign gap {gap * 1000:.0f} nm (kappa^2 = {float(kappa2(gap, d)):.4f}):  loaded Q = {s0['Q']:.0f}, "
            f"linewidth {s0['fwhm'] * 1e12:.1f} pm, FSR {s0['fsr'] * 1e9:.2f} nm, extinction {s0['ext_dB']:.1f} dB"
        )
        lines.append(f"{'V':>6} {'resonance shift pm':>19} {'extinction dB':>14} {'T at the 0 V resonance, dB':>27}")
        for v in a.volts:
            lam, T = spectra_v[v]
            order = np.argsort(lam)
            at_lam0 = float(np.interp(lam0, lam[order], T[order]))
            lines.append(
                f"{v:6.1f} {(stats_v[v]['lam_res'] - lam0) * 1e12:19.1f} {stats_v[v]['ext_dB']:14.1f} {10 * math.log10(max(at_lam0, 1e-12)):27.2f}"
            )
            res[f"spec_lam_V{v:+.0f}"], res[f"spec_T_V{v:+.0f}"] = lam, T
        f_photon = C0 / (lam0 * s0["Q"])
        lines.append(f"optical bandwidth from the photon lifetime: f = c / (lambda Q) = {f_photon / 1e9:.1f} GHz")
        if "f_RC" in d:
            lines.append(
                f"electrical: C = {d['C0_fF']:.1f} fF, Rs = {d['Rs']:.1f} ohm at 0 V -> intrinsic f_RC = {d['f_RC'] / 1e9:.0f} GHz  [step 3]; "
                "the slower of the two limits the modulator"
            )
        res.update(Q_design=s0["Q"], fwhm_design=s0["fwhm"], fsr=s0["fsr"], f_photon=f_photon)

        # ---- 3. heater sweep at the design gap ----
        lines.append(f"\n{'heater mW':>10} {'resonance shift pm':>19}")
        shifts = []
        for power in a.heater:
            lam, T = ring.spectrum(gap, heater_mW=power)
            s = spectrum_stats(lam, T)
            shifts.append((s["lam_res"] - lam0) * 1e12)
            lines.append(f"{power:10.1f} {shifts[-1]:19.1f}")
            res[f"spec_lam_P{power:.0f}"], res[f"spec_T_P{power:.0f}"] = lam, T
        positive = [(p, s) for p, s in zip(a.heater, shifts, strict=True) if p > 0]
        if positive:
            rate = float(np.mean([s / p for p, s in positive]))
            lines.append(
                f"thermal tuning {rate:.1f} pm/mW; one FSR ({s0['fsr'] * 1e9:.2f} nm) needs {s0['fsr'] * 1e12 / rate:.0f} mW"
            )
            res["thermal_pm_per_mW"] = rate
        ic.switchtodesign()
        ic.save(str(OUT / "ring_modulator.icp"))

    np.savez(OUT / "ring_modulator.npz", **res)
    (OUT / "ring_modulator.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[len(a.gaps) + 5 :]))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

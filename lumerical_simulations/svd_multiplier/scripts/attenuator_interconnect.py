"""Step 1 - INTERCONNECT: one attenuator of the column, a Mach-Zehnder interferometer with a dump of its own.

The attenuator of row 0 alone (svd_model.attenuator_circuit): its lead, two couplers, the heater on the dump arm.  It
is built in INTERCONNECT from the kept results of the device chapters and run with the network analyser.

    1. the heater swept from 0 to 2 P_pi at 1.55 um -> what stays on the row, what goes to the dump, its phase
    2. the same against the wavelength                -> how far down the row can be dimmed, across the band
    3. the Python model of the same circuit           -> the check that the two describe one circuit

With ideal 50:50 couplers the row keeps -i e^(i theta / 2) sin(theta / 2) of its field: an amplitude from 0 to 1 and a
phase that grows with theta, which mesh V takes up.  With the real coupler the row cannot be dimmed to nothing: at
theta = 0 it keeps (tau^2 - kappa^2)^2 of the power, which sets the smallest singular value the column can set.

    python attenuator_interconnect.py

Output in 1_attenuator/:  attenuator.icp (the circuit, without results), attenuator.npz, attenuator.txt
"""

from __future__ import annotations

import time

import numpy as np
import svd_interconnect as sx
import svd_model as sm
from svd_common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, SCRATCH, import_lumapi, inputs, step_dir

mm = sm.mm  # the model of the mesh chapter

OUT = step_dir("1_attenuator")
LAM_MAX = 1.6
POINTS = 101
SWEEP = np.linspace(0.0, 2.0, 41)  # the heater power in units of P_pi
ROW, DUMP = 1, 0  # the rows of attenuator_circuit()


def db(x) -> np.ndarray:
    return 10 * np.log10(np.maximum(np.asarray(x, dtype=float), 1e-30))


def main() -> None:
    t0 = time.time()
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = sm.attenuator_circuit(LAYOUT, d["heater_length"])
    sp = sx.write_sparameters(ph, SCRATCH / "coupler.dat")
    lumapi = import_lumapi()
    with lumapi.INTERCONNECT(hide=True) as ic:
        unit = sx.Multiplier(ic, c, ph, sp, LAM_MAX, POINTS)
        sweep = []
        for k in SWEEP:
            unit.set_sites(mm.site_dn(c, ph, [k * ph.P_pi]))
            t, lam = unit.measure([ROW])
            sweep.append(t[:, :, 0])  # (lam, out) for light into the row
            print(f"  heater at {k:.2f} P_pi: row keeps {abs(t[POINTS // 2, ROW, 0]) ** 2:.4f}", flush=True)
        unit.set_sites(mm.site_dn(c, ph, [0.0]))
        ic.switchtodesign()
        ic.save(str(OUT / "attenuator.icp"))
    sweep = np.array(sweep)  # (power, lam, out)
    i0 = POINTS // 2
    if abs(lam[i0] - ph.lam0) > 1e-9:
        raise RuntimeError(f"the middle sample is at {lam[i0]} um, not at {ph.lam0} um")

    # ---- 1. against the power, at 1.55 um ----
    keep = np.abs(sweep[:, i0, ROW]) ** 2
    dump = np.abs(sweep[:, i0, DUMP]) ** 2
    total = keep + dump
    amplitude = np.sqrt(keep / total)  # the field the row keeps, of all that passes
    ideal = np.abs(np.sin(np.pi * SWEEP / 2))
    j_pi = int(np.argmin(np.abs(SWEEP - 1.0)))  # the heater at P_pi: the row keeps all; its phase is the reference
    phase = np.unwrap(np.angle(sweep[:, i0, ROW]))
    phase = phase - phase[j_pi]  # (at 0 and 2 P_pi the row keeps nothing and its phase means nothing)
    phase_slope = float(np.polyfit(SWEEP[5:16] * np.pi, phase[5:16], 1)[0])  # rad per rad of theta, away from the null
    s = ph.coupler(ph.lam0, (3, 4))
    k2, t2 = float(abs(s[3][0]) ** 2), float(abs(s[4][0]) ** 2)
    leak = float(keep[0] / total[0])
    leak_formula = ((t2 - k2) / (t2 + k2)) ** 2

    # ---- 2. the leak against the wavelength: the smallest field the row can keep ----
    leak_lam = np.abs(sweep[0, :, ROW]) ** 2 / (np.abs(sweep[0, :, ROW]) ** 2 + np.abs(sweep[0, :, DUMP]) ** 2)
    coupler = ph.coupler(lam, (3, 4))
    kappa2 = np.abs(coupler[3]) ** 2 / (np.abs(coupler[3]) ** 2 + np.abs(coupler[4]) ** 2)
    leak_lam_formula = (1 - 2 * kappa2) ** 2
    j_half = int(np.argmin(np.abs(SWEEP - 0.5)))  # the heater at P_pi / 2: the row keeps a field of sin(pi / 4)
    half_lam = np.abs(sweep[j_half, :, ROW]) ** 2 / (np.abs(sweep[j_half, :, ROW]) ** 2 + np.abs(sweep[j_half, :, DUMP]) ** 2)
    smallest = float(np.sqrt(leak))  # the smallest field, so the smallest singular value over the largest

    # ---- 3. the Python model of the same circuit ----
    diff = 0.0
    for j, k in enumerate(SWEEP):
        model = sm.transfer(c, ph, lam, mm.site_dn(c, ph, [k * ph.P_pi]))[:, :, ROW]
        diff = max(diff, float(np.max(np.abs(sweep[j] - model))))
    loss_db = -float(db(total[0]))

    lines = [
        "INTERCONNECT, Lumerical 2025 R1: one attenuator of devices/svd_multiplier_builder.py (row 0 and its dump), built from",
        "  the FDTD S-parameters of the coupler, the strip of the strip waveguide chapter and the heater of the phase shifter chapter",
        f"  coupler at 1.55 um: |S31|^2 = {k2:.4f}, |S41|^2 = {t2:.4f}; P_pi = {ph.P_pi:.2f} mW; propagation loss {LOSS_DB_CM} dB/cm (assumed)",
        f"  analyser {lam[0]:.4f} to {lam[-1]:.4f} um, {POINTS} points; run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: the heater sets the field the row keeps from {smallest:.1e} to 1, as sin(theta / 2), and its phase moves by "
        f"{phase_slope:.2f} rad per rad of theta (1/2 for ideal couplers).  The row cannot be dimmed below {db(leak):.1f} dB at "
        f"1.55 um: a singular value smaller than {smallest:.1e} times the largest cannot be set.",
        "",
        "a. the heater swept at 1.55 um, light into the row",
        f"  at 0 mW the row keeps {leak:.2e} of what passes ({db(leak):.1f} dB); ((tau^2 - kappa^2) / (tau^2 + kappa^2))^2 = {leak_formula:.2e} ({db(leak_formula):.1f} dB)",
        f"  through the attenuator, the row and the dump together (the same at every power): {total[0]:.4f} ({loss_db:.3f} dB)",
        "  heater (P_pi)  row keeps (power)  dump  field kept  sin(theta/2)  phase of the row against P_pi (rad)",
    ]
    for j in range(0, len(SWEEP), 4):
        lines.append(
            f"  {SWEEP[j]:13.2f}  {keep[j]:17.4f}  {dump[j]:.4f}  {amplitude[j]:10.4f}  {ideal[j]:12.4f}  {phase[j]:+.4f}"
        )
    lines += [
        "",
        "b. against the wavelength",
        "  lambda (um)  kappa^2  leak at 0 mW (dB)  formula (dB)  field kept at P_pi / 2",
    ]
    for j in range(0, POINTS, 10):
        lines.append(
            f"  {lam[j]:11.4f}  {kappa2[j]:7.4f}  {db(leak_lam[j]):17.1f}  {db(leak_lam_formula[j]):12.1f}  {np.sqrt(half_lam[j]):22.4f}"
        )
    lines += [
        "  the leak is (1 - 2 kappa^2)^2 with the split kappa^2 of the FDTD coupler at each wavelength: deepest where it splits 50:50",
        "",
        f"c. the Python model of svd_model.py against INTERCONNECT, all {len(SWEEP)} powers and {POINTS} wavelengths: largest difference "
        f"of an entry {diff:.1e}, the reflection of the couplers that only INTERCONNECT includes.",
    ]
    text = "\n".join(lines)
    print(text)
    (OUT / "attenuator.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "attenuator.npz", lam=lam, sweep_P_pi=SWEEP, sweep_P_mW=SWEEP * ph.P_pi, keep=keep, dump=dump, amplitude=amplitude,
        phase=phase, phase_slope=phase_slope, leak=leak, leak_formula=leak_formula, leak_lam=leak_lam,
        leak_lam_formula=leak_lam_formula, half_lam=half_lam, kappa2=kappa2, smallest=smallest, model_difference=diff,
        loss_dB=loss_db, P_pi_mW=ph.P_pi,
    )  # fmt: skip


if __name__ == "__main__":
    main()

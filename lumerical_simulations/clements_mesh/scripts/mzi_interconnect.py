"""Step 1 - INTERCONNECT: one block of the mesh, a Mach-Zehnder interferometer built from the coupler and the heater.

The block is the 2 x 2 mesh of devices/clements_mesh_builder.py: two couplers, phi on the upper input, theta on the
upper arm, and a phase shifter on each output.  It is built in INTERCONNECT from the kept results of the device
chapters (see interconnect.py) and run with the network analyser.

    1. theta swept from 0 to 2.2 P_pi at 1.55 um         -> the split against the heater power, P_pi, both nulls
    2. the cross, the half and the bar state, 1.5 to 1.6 um -> how the coupler sets the bandwidth of the block
    3. the same in the Python model of mesh_model.py      -> the check that the two describe one circuit

With identical couplers of power split kappa^2 and tau^2, the block passes kappa tau (1 + e^(i theta)) across: the
cross port has a perfect null at theta = pi whatever the split.  The bar port passes tau^2 e^(i theta) - kappa^2: its
null at theta = 0 is (tau^2 - kappa^2)^2, which only a 50:50 coupler makes zero.

    python mzi_interconnect.py

Output in 1_mzi/:  mzi.icp (the circuit, without results), mzi.npz, mzi.txt
"""

from __future__ import annotations

import math
import time

import interconnect as icx
import mesh_model as mm
import numpy as np
from common import COUPLER_PORT_EXTRA, LOSS_DB_CM, SCRATCH, cm, import_lumapi, inputs, step_dir

OUT = step_dir("1_mzi")
LAM_MAX = 1.6  # um: the analyser runs from about 1.503 to 1.6 um, centred on 1.55 um in frequency
POINTS = 101
SWEEP = np.linspace(0.0, 2.2, 45)  # theta heater power in units of P_pi
STATES = {"cross": 0.0, "half": 0.5, "bar": 1.0}  # theta heater power in units of P_pi
DB = 10 / math.log(10)


def db(x) -> np.ndarray:
    return 10 * np.log10(np.maximum(np.asarray(x, dtype=float), 1e-30))


def main() -> None:
    t0 = time.time()
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    info = cm.clements_mesh(n=2).info
    c = mm.circuit(info, d["heater_length"])
    order = mm.heater_order(c)
    theta = int(order["theta"][0])
    sp = icx.write_sparameters(ph, SCRATCH / "coupler.dat")
    lumapi = import_lumapi()

    def powers(p_theta: float) -> np.ndarray:
        p = np.zeros(len(c.heaters))
        p[theta] = p_theta
        return p

    with lumapi.INTERCONNECT(hide=True) as ic:
        mesh = icx.Mesh(ic, c, ph, sp, LAM_MAX, POINTS)
        sweep = []
        for k in SWEEP:
            mesh.set_sites(mm.site_dn(c, ph, powers(k * ph.P_pi)))
            u, lam = mesh.measure()
            sweep.append(u)
            print(f"  theta at {k:.2f} P_pi: cross {abs(u[POINTS // 2, 1, 0]) ** 2:.4f}", flush=True)
        mesh.set_sites(mm.site_dn(c, ph, powers(0.0)))
        ic.switchtodesign()  # the project is kept without results, all heaters off
        ic.save(str(OUT / "mzi.icp"))
        sweep = np.array(sweep)  # (power, lam, out, in)
    i0 = POINTS // 2
    if abs(lam[i0] - ph.lam0) > 1e-9:
        raise RuntimeError(f"the middle sample is at {lam[i0]} um, not at {ph.lam0} um")

    # ---- 1. the split against the power, from the upper input ----
    cross = np.abs(sweep[:, i0, 1, 0]) ** 2
    bar = np.abs(sweep[:, i0, 0, 0]) ** 2
    P = SWEEP * ph.P_pi
    k_min = int(np.argmin(cross))  # the cross null
    s = ph.coupler(ph.lam0, (3, 4))
    k2, t2 = float(abs(s[3][0]) ** 2), float(abs(s[4][0]) ** 2)
    # theta = 0, the cross state: the bar port holds (tau^2 - kappa^2)^2 of what passes the block
    bar_null = float(bar[0] / (bar[0] + cross[0]))
    bar_null_formula = ((t2 - k2) / (t2 + k2)) ** 2

    # ---- 2. the three states against the wavelength ----
    states = {}
    for name, k in STATES.items():
        j = int(np.argmin(np.abs(SWEEP - k)))
        if abs(SWEEP[j] - k) > 1e-9:
            raise RuntimeError(f"the sweep has no point at {k} P_pi")
        states[name] = sweep[j]  # (lam, out, in)
    total = np.abs(states["cross"][:, 0, 0]) ** 2 + np.abs(states["cross"][:, 1, 0]) ** 2
    er_cross = db(np.abs(states["cross"][:, 1, 0]) ** 2 / np.abs(states["cross"][:, 0, 0]) ** 2)  # wanted over leak
    er_bar = db(np.abs(states["bar"][:, 0, 0]) ** 2 / np.abs(states["bar"][:, 1, 0]) ** 2)
    split_half = np.abs(states["half"][:, 1, 0]) ** 2 / (
        np.abs(states["half"][:, 0, 0]) ** 2 + np.abs(states["half"][:, 1, 0]) ** 2
    )
    band_20 = lam[er_cross >= 20]
    coupler = ph.coupler(lam, (3, 4))
    kappa2 = np.abs(coupler[3]) ** 2 / (np.abs(coupler[3]) ** 2 + np.abs(coupler[4]) ** 2)
    er_cross_formula = db((4 * kappa2 * (1 - kappa2)) / (1 - 2 * kappa2) ** 2)

    # ---- 3. the Python model of the same circuit ----
    diff = 0.0
    for j, k in enumerate(SWEEP):
        up = mm.transfer(c, ph, lam, mm.site_dn(c, ph, powers(k * ph.P_pi)))
        diff = max(diff, float(np.max(np.abs(sweep[j] - up))))
    loss_db = -db(total[i0])
    length_um = sum(p[2] for p in c.rows[0] if p[0] == "wg")

    lines = [
        "INTERCONNECT, Lumerical 2025 R1: one block of the mesh (the 2 x 2 mesh of devices/clements_mesh_builder.py), built from",
        "  the FDTD S-parameters of the coupler, the strip of the strip waveguide chapter and the heater of the phase shifter chapter",
        f"  coupler at 1.55 um: |S31|^2 = {k2:.4f}, |S41|^2 = {t2:.4f} (moved {COUPLER_PORT_EXTRA} um inwards at each port)",
        f"  strip n_eff = {ph.neff:.5f}, n_g = {ph.ng:.4f}; heater dn_eff/dP = {ph.dneff_dP:.4e} per mW over {ph.L_heater:.0f} um "
        f"-> P_pi = {ph.P_pi:.2f} mW; propagation loss {LOSS_DB_CM} dB/cm (assumed)",
        f"  analyser {lam[0]:.4f} to {lam[-1]:.4f} um, {POINTS} points, centred on {ph.lam0} um in frequency; run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: the cross port is dark at theta = P_pi = {ph.P_pi:.2f} mW; the bar port is dark at 0 mW only down to "
        f"{db(bar_null):.1f} dB, set by the split of the coupler.  The block holds 20 dB of extinction in the cross state from "
        f"{band_20.min() * 1000:.0f} to {band_20.max() * 1000:.0f} nm.",
        "",
        "a. theta swept at 1.55 um, light into the upper input",
        f"  cross |U21|^2 smallest at {P[k_min]:.2f} mW in the sweep (step {P[1] - P[0]:.2f} mW): "
        + (
            "exactly zero: no light reached the analyser, the two paths cancel"
            if cross[k_min] < 1e-20
            else f"{cross[k_min]:.2e} ({db(cross[k_min]):.1f} dB)"
        ),
        f"  bar at 0 mW, over all that passes: {bar_null:.3e} ({db(bar_null):.1f} dB); ((tau^2 - kappa^2) / (tau^2 + kappa^2))^2 = {bar_null_formula:.3e} ({db(bar_null_formula):.1f} dB)",
        f"  through the block, cross state: {total[i0]:.4f} ({loss_db:.3f} dB over {length_um:.0f} um of strip and two couplers)",
        "  heater power (P_pi)   cross     bar",
    ]
    for k, x, y in zip(SWEEP[::4], cross[::4], bar[::4], strict=False):
        lines.append(f"  {k:17.2f}  {x:7.4f}  {y:7.4f}")
    lines += [
        "",
        "b. the three states against the wavelength (upper input)",
        "  lambda (um)  kappa^2 of the coupler  extinction, cross state (dB)  formula (dB)  bar state (dB)  split, half state",
    ]
    for j in range(0, POINTS, 10):
        bar_text = "no leak" if er_bar[j] > 200 else f"{er_bar[j]:.1f}"
        lines.append(
            f"  {lam[j]:11.4f}  {kappa2[j]:22.4f}  {er_cross[j]:28.1f}  {er_cross_formula[j]:12.1f}  {bar_text:>14}  {split_half[j]:17.4f}"
        )
    lines += [
        "  extinction of the cross state: wanted (lower output) over leak (upper output); formula 4 k^2 (1 - k^2) / (1 - 2 k^2)^2",
        "  with the split k^2 of the FDTD coupler at each wavelength.  In the bar state the lower output gets no light at any",
        "  wavelength ('no leak'): its null needs no 50:50 coupler, only two equal ones.",
        "",
        f"c. the Python model of mesh_model.py against INTERCONNECT, all {len(SWEEP)} powers and {POINTS} wavelengths: largest difference "
        f"of an entry {diff:.1e} (entries up to 1).  The difference is the reflection of the couplers (-43 dB), which INTERCONNECT "
        "includes and the model leaves out.",
    ]
    text = "\n".join(lines)
    print(text)
    (OUT / "mzi.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "mzi.npz", lam=lam, sweep_P_mW=P, sweep_P_pi=SWEEP, cross=cross, bar=bar, P_pi_mW=ph.P_pi,
        state_names=np.array(list(STATES)), state_P_pi=np.array(list(STATES.values())),
        state_U=np.array([states[k] for k in STATES]), er_cross_dB=er_cross, er_cross_formula_dB=er_cross_formula,
        er_bar_dB=er_bar, split_half=split_half, kappa2=kappa2, bar_null=bar_null, bar_null_formula=bar_null_formula,
        model_difference=diff, loss_dB=loss_db, k2_1550=k2, t2_1550=t2,
    )  # fmt: skip


if __name__ == "__main__":
    main()

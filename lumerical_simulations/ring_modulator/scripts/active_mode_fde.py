"""Step 5 - MODE (FDE): the active waveguide: effective index and loss versus voltage and heater power.

The silicon of the process file is an index-perturbation material.  Its index responds to

    carriers     (Soref-Bennett coefficients of Nedeljkovic, Soref and Mashanovich, 2011), and
    temperature  (linear dn/dT),

once the simulation is given the carrier or temperature map.  Both maps come from earlier steps:

    electrical   Layer Builder with the PN section of step 3  +  "np Density" grid attribute
                 loaded with the carriers CHARGE exported   ->  n_eff(V), loss(V)
    thermal      Layer Builder with the heater section of step 4  +  "temperature" grid attribute
                 loaded with the temperature HEAT exported   ->  n_eff at the reference heater power

The waveguide is solved bent to the ring radius, with the bend orientation found in step 2: the mode
moves outwards, towards the p side, which changes how much of it sees each half of the junction.

The window is smaller than step 2's, so the mesh carries a line on every silicon surface (add_rib_mesh).
The undoped base solved here is compared with the step-2 ring: they must agree, or the two windows
disagree and the step-5 numbers need a check.

    python active_mode_fde.py
    python active_mode_fde.py --mesh 0.01

Output in 5_active_mode_properties/:  pn_rib.lms, heater.lms, active.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    L_HEATER,
    L_PN,
    L_RING,
    LAM,
    RADIUS,
    ROOT,
    SLAB_WIDTH,
    WIDTH,
    add_layer_builder,
    add_rib_mesh,
    import_lumapi,
    require_process_file,
    step_dir,
    um,
)

OUT = step_dir("5_active_mode_properties")
CHARGE_DIR, HEAT_DIR, PASSIVE_DIR = ROOT / "3_charge_profile", ROOT / "4_heat_profile", ROOT / "2_passive_mode_properties"
Y_SPAN = 3.4  # stays inside the contact vias (they start 1.9 um from the centre)
Z_MIN, Z_MAX = -0.9, 1.0  # stays below metal 1 and the heater film (they start at 1.1 um)
N_GUESS = 2.6
AGREE_TOL = 1e-3  # the undoped base here and the step-2 ring must agree to this n_eff


def setup(m, gds, y_builder: float, mesh: float, rib_mesh: float, orientation: int) -> None:
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds, 6.0, y_builder)
    m.addfde()
    m.set("solver type", "2D X normal")
    m.set("x", 0)
    m.set("y", 0)
    m.set("y span", Y_SPAN * um)
    m.set("z", (Z_MIN + Z_MAX) / 2 * um)
    m.set("z span", (Z_MAX - Z_MIN) * um)
    for axis in ("y", "z"):
        m.set(f"define {axis} mesh by", "maximum mesh step")
        m.set(f"d{axis}", mesh * um)
    for bc in ("y min bc", "y max bc", "z min bc", "z max bc"):
        m.set(bc, "PML")
    # added last: a new object takes the selection, and every set() above is meant for the FDE
    add_rib_mesh(m, WIDTH, rib_mesh)  # a mesh line on every silicon surface, whatever the window
    m.setanalysis("wavelength", LAM * um)
    m.setanalysis("search", "near n")
    m.setanalysis("use max index", 0)
    m.setanalysis("n", N_GUESS)
    m.setanalysis("number of trial modes", 4)
    m.setanalysis("bent waveguide", 1)
    m.setanalysis("bend radius", RADIUS * um)
    m.setanalysis("bend location", "simulation center")
    m.setanalysis("bend orientation", orientation)


def te0(m) -> dict:
    """n_eff (complex) and loss (dB/cm) of the TE mode with the highest index."""
    best = None
    for i in range(1, int(m.findmodes()) + 1):
        d = f"FDE::data::mode{i}"
        if float(np.squeeze(m.getdata(d, "TE polarization fraction"))) < 0.5:
            continue
        neff = complex(np.squeeze(m.getdata(d, "neff")))
        if best is None or neff.real > best["neff"].real:
            best = dict(neff=neff, loss=float(np.squeeze(m.getdata(d, "loss"))) / 100)
    if best is None:
        raise SystemExit("no TE mode found: check the Layer Builder geometry")
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mesh", type=float, default=0.02, help="uniform FDE mesh step (um)")
    ap.add_argument("--rib-mesh", type=float, default=0.01, help="mesh step on the silicon surfaces of the rib (um)")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    charge = np.load(CHARGE_DIR / "pn_rib_charge.npz")
    heat = np.load(HEAT_DIR / "heater_heat.npz")
    passive = np.load(PASSIVE_DIR / "rib_passive.npz")
    ng, orientation = float(passive["ring_ng"]), int(passive["bend_orientation"])
    ring_neff = float(passive["ring_neff"])  # step 2: the same undoped rib bent to the ring radius
    V = np.sort(charge["V"])[::-1]  # 0 V first, then 0 -> most negative
    lines = [
        f"Active rib waveguide W = {WIDTH} um, bent to R = {RADIUS} um, at {LAM} um; FDE mesh {a.mesh * 1000:.0f} nm, "
        f"rib-interface mesh {a.rib_mesh * 1000:.0f} nm; n_g = {ng:.4f} from step 2"
    ]
    res = dict(V=V, lam=LAM, ng=ng)

    with lumapi.MODE(hide=True) as m:
        # ---- electrical: carriers from CHARGE ----
        setup(m, CHARGE_DIR / "pn_rib.gds", SLAB_WIDTH + 2.0, a.mesh, a.rib_mesh, orientation)
        m.addgridattribute("np Density")
        m.set("name", "carriers")
        m.importdataset(str(CHARGE_DIR / "pn_rib_charge.mat"))
        m.select("carriers")
        m.set("enabled", 0)
        base = te0(m)  # the same waveguide with no free carriers at all
        m.switchtolayout()
        m.select("carriers")
        m.set("enabled", 1)
        neff, loss = [], []
        for v in V:
            m.switchtolayout()
            m.select("carriers")
            m.set("V_anode", float(v))
            mode = te0(m)
            neff.append(mode["neff"].real)
            loss.append(mode["loss"])
            print(
                f"  V = {v:+5.2f} V:  n_eff = {neff[-1]:.6f}   loss = {loss[-1]:6.3f} dB/cm   ({time.time() - t0:.0f} s)",
                flush=True,
            )
        m.switchtolayout()
        m.save(str(OUT / "pn_rib.lms"))

        # ---- thermal: temperature from HEAT ----
        setup(m, HEAT_DIR / "heater.gds", 42.0, a.mesh, a.rib_mesh, orientation)
        m.addgridattribute("temperature")
        m.set("name", "temperature")
        m.importdataset(str(HEAT_DIR / "heater_T.mat"))
        m.select("temperature")
        m.set("enabled", 0)
        cold = te0(m)
        m.switchtolayout()
        m.select("temperature")
        m.set("enabled", 1)
        hot = te0(m)
        m.switchtolayout()
        m.save(str(OUT / "heater.lms"))

    neff, loss = np.array(neff), np.array(loss)
    dneff = neff - neff[0]
    fraction_pn, fraction_heater = L_PN / L_RING, L_HEATER / L_RING
    shift_pm = dneff * fraction_pn * LAM / ng * 1e6  # resonance shift of the ring, pm
    with np.errstate(divide="ignore", invalid="ignore"):
        vpil = np.abs(V) * LAM * 1e-4 / (2 * np.abs(dneff))  # V cm
    p_ref = float(heat["P_reference_mW"])
    dneff_dP = (hot["neff"].real - cold["neff"].real) / p_ref  # per mW, in the heated section
    thermal_pm_per_mW = dneff_dP * fraction_heater * LAM / ng * 1e6

    # the undoped base against step 2 (same bent rib, other window); and the carrier effect at 0 V
    base_neff = base["neff"].real
    base_minus_passive = base_neff - ring_neff
    neff0V_minus_base = neff[0] - base_neff
    res.update(
        neff=neff,
        loss_dBcm=loss,
        dneff=dneff,
        shift_pm=shift_pm,
        vpil_Vcm=vpil,
        base_neff=base_neff,
        base_loss_dBcm=base["loss"],
        base_minus_passive=base_minus_passive,
        neff0V_minus_base=neff0V_minus_base,
        dneff_dP_section=dneff_dP,
        thermal_pm_per_mW=thermal_pm_per_mW,
        fraction_pn=fraction_pn,
        fraction_heater=fraction_heater,
        neff_cold=cold["neff"].real,
        neff_hot=hot["neff"].real,
    )

    lines += [
        f"no carriers: n_eff = {base_neff:.6f}, loss = {base['loss']:.4f} dB/cm",
        f"step 2, the same undoped rib bent to R = {RADIUS} um: n_eff = {ring_neff:.6f};  "
        f"base_minus_passive = {base_minus_passive:+.2e}",
        f"0 V with carriers minus no carriers: neff0V_minus_base = {neff0V_minus_base:+.2e}",
    ]
    if abs(base_minus_passive) > AGREE_TOL:
        warning = (
            f"WARNING: the step-5 and step-2 windows do not agree: base_minus_passive = {base_minus_passive:+.2e} "
            f"(tolerance {AGREE_TOL:.0e}).  Check the window and the mesh before using the step-5 numbers."
        )
        lines.append(warning)
        print(warning, flush=True)
    lines += [
        f"\n{'V':>6} {'n_eff':>10} {'d n_eff':>10} {'loss dB/cm':>11} {'ring shift pm':>14} {'VpiL V cm':>10}",
    ]
    lines += [
        f"{V[k]:6.2f} {neff[k]:10.6f} {dneff[k]:+10.2e} {loss[k]:11.3f} {shift_pm[k]:14.1f} {vpil[k] if k else float('nan'):10.2f}"
        for k in range(len(V))
    ]
    turn = loss * L_PN * 1e-4
    lines += [
        f"\nfree-carrier loss of the PN section per round trip: {turn[0]:.4f} dB at 0 V, {turn[-1]:.4f} dB at {V[-1]:.0f} V",
        f"ring shift = d n_eff x (doped fraction {fraction_pn:.0%}) x lambda / n_g",
        f"\nthermal: n_eff {cold['neff'].real:.6f} -> {hot['neff'].real:.6f} at {p_ref:.0f} mW in the heated section "
        f"= {dneff_dP:.3e} per mW",
        f"ring shift = that x (heated fraction {fraction_heater:.0%}) x lambda / n_g = {thermal_pm_per_mW:.1f} pm/mW",
        f"The junction at {V[-1]:.0f} V moves the resonance as much as {abs(shift_pm[-1]) / thermal_pm_per_mW:.2f} mW of heater power:",
        "the heater sets the operating point, the junction modulates around it.",
    ]
    np.savez_compressed(OUT / "active.npz", **res)
    (OUT / "active.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-7:]))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

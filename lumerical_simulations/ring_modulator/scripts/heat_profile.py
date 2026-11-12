"""Step 4 - HEAT: the Al heater above the ring: temperature rise of the waveguide per unit of power.

SOI220A forms heaters in the Al electrode layer, on top of the 1 um top cladding.  Model: a straight
section of the rib waveguide with a 2 um wide filament drawn in Electrode_LF above the core, written
to GDS and loaded into a Layer Builder with cornerstone_process.lbr (stack, thermal material models
and the air above the cladding all come from the process file).

The simulation is a 2D cross-section normalised to the length of the heated arc, so the power is the
total heater power.

Settings that matter (each one found by a failed run):
    * the heat source is a thermal power boundary condition on the *solid* ``Electrode``;
    * the heat sink is a temperature boundary condition on the *solid* ``Si_Substrate``,
      and the simulation region has to include that solid;
    * the region has to stay inside the layers of the process file, otherwise the solver stops with
      "No thermal material properties defined for domain".

    python heat_profile.py                    # 2, 5, 10, 20 mW
    python heat_profile.py --powers 5 10

Output in 4_heat_profile/:  heater.gds / .ldev, heater_T.mat (for step 5), heater_heat.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    L_HEATER,
    L_RING,
    SLAB_WIDTH,
    T_METAL,
    T_SI,
    WIDTH,
    Z_METAL,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    rm,
    section_gds,
    step_dir,
    strip,
    t,
    um,
)

OUT = step_dir("4_heat_profile")
NAME = "heater"
LENGTH = 6.0
Y_SPAN = 40.0  # heat spreads sideways over many times the oxide thickness
Z_MIN, Z_MAX = -4.8, 4.0  # substrate (-5 ... -2 um) to the air above the heater (up to 4.22 um)
T_AMBIENT = 300.0
P_REFERENCE = 10.0  # mW: the temperature map of this power is exported for step 5
AL_RESISTIVITY = 2.8e-8  # ohm m, bulk aluminium [assumed]; the real film stack is not published


def write_gds():
    def filament(c, x0, x1):
        c.add_polygon(strip(x0, x1, -rm.HEATER_WIDTH / 2, rm.HEATER_WIDTH / 2), layer=t.METAL)

    xs = {"cross_section": "rib_1550nm_TE", "settings": {"width": WIDTH, "width_slab": SLAB_WIDTH}}
    return section_gds(OUT / f"{NAME}.gds", xs, LENGTH, extra=filament)


def build(d, gds) -> None:
    d.switchtolayout()
    add_layer_builder(d, gds, LENGTH, Y_SPAN + 2.0)
    d.select("simulation region")
    d.set("dimension", "2D X-Normal")
    d.set("x", 0)
    d.set("y", 0)
    d.set("y span", Y_SPAN * um)
    d.set("z", (Z_MIN + Z_MAX) / 2 * um)
    d.set("z span", (Z_MAX - Z_MIN) * um)

    d.addheatsolver()
    d.select("HEAT")
    d.set("solver mode", "steady state")
    d.set("norm length", L_HEATER * um)
    d.set("min edge length", 0.02 * um)
    d.set("max edge length", 0.5 * um)

    d.addtemperaturebc()
    d.set("name", "substrate")
    d.set("surface type", "solid")
    d.set("solid", "Si_Substrate")
    d.set("temperature", T_AMBIENT)

    d.addthermalpowerbc()
    d.set("name", "heater")
    d.set("surface type", "solid")
    d.set("solid", "Electrode")
    d.set("power", P_REFERENCE * 1e-3)

    d.addtemperaturemonitor()
    d.set("name", "T")
    d.set("monitor type", "2D x-normal")
    d.set("x", 0)
    d.set("y", 0)
    d.set("y span", Y_SPAN * um)
    d.set("z", (Z_MIN + Z_MAX) / 2 * um)
    d.set("z span", (Z_MAX - Z_MIN) * um)


def read_temperature(d) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r = d.getresult("HEAT::T", "temperature")
    return np.real(np.squeeze(r["T"])), np.squeeze(r["y"]) / um, np.squeeze(r["z"]) / um


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--powers", type=float, nargs="*", default=[2.0, 5.0, 10.0, 20.0], help="heater power (mW)")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = write_gds()
    ldev, mat = OUT / f"{NAME}.ldev", OUT / f"{NAME}_T.mat"
    powers = sorted(set(a.powers) | {P_REFERENCE})
    core_dT, heater_dT = [], []
    res = dict(powers_mW=np.array(powers), L_heater=L_HEATER, L_ring=L_RING, P_reference_mW=P_REFERENCE)
    with lumapi.DEVICE(hide=True) as d:
        build(d, gds)
        d.save(str(ldev))
        for power in powers:
            d.switchtolayout()
            d.select("HEAT::boundary conditions::heater")
            d.set("power", power * 1e-3)
            d.select("HEAT::T")
            reference = abs(power - P_REFERENCE) < 1e-9
            d.set("save data", int(reference))
            if reference:
                d.set("filename", str(mat))
            d.run()
            T, y, z = read_temperature(d)
            core = (np.abs(y) < WIDTH / 2 + 0.02) & (z > -0.01) & (z < T_SI + 0.01)  # nodes of the silicon core
            metal = (np.abs(y) < rm.HEATER_WIDTH / 2) & (z > Z_METAL) & (z < Z_METAL + T_METAL)
            core_dT.append(float(np.mean(T[core]) - T_AMBIENT))
            heater_dT.append(float(np.mean(T[metal]) - T_AMBIENT))
            print(
                f"P = {power:5.1f} mW:  core +{core_dT[-1]:6.2f} K   heater +{heater_dT[-1]:6.2f} K   ({time.time() - t0:.0f} s)",
                flush=True,
            )
            if reference:
                res.update(T_map=T.astype(np.float32), T_y=y, T_z=z)
        d.switchtolayout()
        d.save(str(ldev))

    slope = float(np.polyfit(powers, core_dT, 1)[0])  # K per mW in the heated section
    resistance = AL_RESISTIVITY * L_HEATER * um / (rm.HEATER_WIDTH * um * T_METAL * um)
    current_10mW = (10e-3 / resistance) ** 0.5
    density = current_10mW / (rm.HEATER_WIDTH * um * T_METAL * um) * 1e-4  # A/cm^2
    res.update(core_dT=np.array(core_dT), heater_dT=np.array(heater_dT), dT_dP=slope, R_heater=resistance)
    lines = [
        f"Al heater: {rm.HEATER_WIDTH} um wide, {T_METAL} um thick, on {t.T_TOX} um of oxide above the core; heated arc {L_HEATER:.2f} um",
        f"{'P (mW)':>7} {'core dT (K)':>12} {'heater dT (K)':>14}",
        *[f"{p:7.1f} {c:12.2f} {h:14.2f}" for p, c, h in zip(powers, core_dT, heater_dT, strict=True)],
        f"\ncore temperature in the heated section: {slope:.3f} K/mW",
        f"averaged over the ring ({L_HEATER / L_RING:.0%} of it is heated): {slope * L_HEATER / L_RING:.3f} K/mW",
        f"\nfilament resistance with bulk Al resistivity [assumed]: {resistance:.2f} ohm",
        f"10 mW then needs {current_10mW * 1e3:.0f} mA, a current density of {density:.1e} A/cm^2.",
        "An Al heater this short is a low-resistance, current-driven element; the leads and probes add comparable resistance.",
        "Still air is modelled as a conductor; convection and radiation are neglected.",
    ]
    np.savez(OUT / f"{NAME}_heat.npz", **res)
    (OUT / f"{NAME}_heat.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-7:]))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

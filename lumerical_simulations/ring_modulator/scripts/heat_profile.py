"""Step 4 - HEAT: the TiN heater above the ring: temperature rise of the waveguide per unit of power.

Model: a straight piece of the ring's cross-section exactly as rm_builder draws it: rib waveguide,
contact vias, metal 1 on both sides, and the TiN film above the core.  It is written to GDS and loaded
into a Layer Builder with gsip_process.lbr; the stack and the thermal material models come from the
process file.  Metal 1 and the vias are part of the model on purpose: aluminium next to the heater
spreads its heat and the vias lead it into the slab.

The simulation is a 2D cross-section normalised to the length of the heater filament, so the power is
the total heater power.

Settings that matter (each one found by a failed or a misleading run):
    * the heat source is a uniform heat source assigned to the *solid* ``Heater``: the Joule heat is
      generated in the volume of the film, and the film conducts it.  A thermal power boundary condition
      on that solid looks equivalent, but it cuts the film out of the thermal domain: the core
      temperature comes out the same within 0.4 %, the film itself 23 K hotter on top than at its edges.
      A heat source drawn as a box over the film is worse: it also heats the mesh cells it touches,
      and 12 % more power than requested arrives at the heat sink;
    * the heat sink is a temperature boundary condition on the *solid* ``Si_Substrate``,
      and the simulation region has to include that solid;
    * the region has to stay inside the layers of the process file, otherwise the solver stops with
      "No thermal material properties defined for domain";
    * in the transient run the solver's shutter switches the heat source on, and a boundary condition
      with a time table sets the length of the run.  The source is set to the reference power again
      before the transient, because the power loop of main() leaves its last power in place;
    * the mesh is uneven, so the averages over the core and over the film are area-weighted
      (``region_weights``), not plain node means;
    * the slopes are least squares through the origin: the rise is proportional to power;
    * energy balance: the heat that reaches the heat sink must equal the power set (``heat_sink_power``).

Three runs:
    1. steady state at several powers            ->  temperature map, K/mW in the core and in the film
    2. the same without metal 1 and the vias     ->  what the electrodes cost in heater efficiency
    3. transient: the reference power is switched on  ->  time constant and 10-90 % rise time

    python heat_profile.py                    # 2, 5, 10, 20 mW
    python heat_profile.py --powers 5 10 --no-transient

Output in 4_heat_profile/:  heater.gds / .ldev, heater_T.mat (for step 5), heater_heat.npz / .txt
"""

from __future__ import annotations

import argparse
import time

import numpy as np
from common import (
    L_HEATER,
    L_PN,
    L_RING,
    T_SI,
    WIDTH,
    Z_M1,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    rm,
    section_gds,
    step_dir,
    t,
    um,
)
from matplotlib.tri import LinearTriInterpolator, Triangulation

OUT = step_dir("4_heat_profile")
NAME = "heater"
LENGTH = 6.0
Y_SPAN = 40.0  # heat spreads sideways over many times the oxide thickness
Z_MIN, Z_MAX = -(t.T_BOX + t.T_SUBSTRATE_SIM) + 0.5, t.Z_TOP - 0.2  # inside the substrate ... inside the top oxide
T_AMBIENT = 300.0
P_REFERENCE = 10.0  # mW: the temperature map of this power is exported for step 5
T_ON = 1e-7  # s: the heat source is switched on at this time of the transient run
T_END = 200e-6  # s: length of the transient run, many thermal time constants
K_OXIDE = 1.38  # W/m/K: thermal conductivity of "SiO2 (Glass) - Sze" in Lumerical's HEAT database.
# Used only by the energy-balance check (heat_sink_power); the solver takes its own value from the process file.
DELTA = 0.2  # um: height above the heat sink at which the flux is read off for the energy balance
CORE_BOX = (-(WIDTH / 2 + 0.02), WIDTH / 2 + 0.02, -0.01, T_SI + 0.01)  # (y0, y1, z0, z1) um: the silicon core
FILM_BOX = (-rm.HEATER_WIDTH / 2, rm.HEATER_WIDTH / 2, t.Z_HEATER - 0.01, t.Z_HEATER + t.T_HEATER + 0.01)  # the TiN film


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

    d.adduniformheat()  # Joule heat, generated in the volume of the TiN film
    d.set("name", "heater")
    d.set("geometry type", "volume")
    d.set("volume type", "solid")
    d.set("volume solid", "Heater")
    d.set("use solver norm length", 1)  # the total power belongs to the whole filament
    d.set("total power", P_REFERENCE * 1e-3)

    d.addtemperaturemonitor()
    d.set("name", "T")
    d.set("monitor type", "2D x-normal")
    d.set("x", 0)
    d.set("y", 0)
    d.set("y span", Y_SPAN * um)
    d.set("z", (Z_MIN + Z_MAX) / 2 * um)
    d.set("z span", (Z_MAX - Z_MIN) * um)


def region_weights(r: dict, box: tuple[float, float, float, float]) -> np.ndarray:
    """Weights that turn nodal values into the area-weighted mean over the rectangle ``box`` = (y0, y1, z0, z1) um.

    A triangle belongs to the rectangle when its centroid lies in it, and it counts by its area: the mesh is uneven,
    and a plain node mean would give a small cell the same weight as a large one.  Each triangle gives a third of its
    area to each of its three nodes, so ``weights @ T`` is the area-weighted mean.  Without an element list the nodes
    inside the rectangle are averaged with equal weight.
    """
    y0, y1, z0, z1 = box
    if "elements" not in r:
        inside = (r["y"] >= y0) & (r["y"] <= y1) & (r["z"] >= z0) & (r["z"] <= z1)
        if not inside.any():
            raise ValueError(f"no mesh nodes in the box {box}")
        return inside.astype(float) / inside.sum()
    tri = np.asarray(r["elements"], dtype=int) - 1  # Lumerical numbers the nodes from 1
    py, pz = r["y"][tri], r["z"][tri]  # triangles x 3 corners
    area = 0.5 * np.abs((py[:, 1] - py[:, 0]) * (pz[:, 2] - pz[:, 0]) - (py[:, 2] - py[:, 0]) * (pz[:, 1] - pz[:, 0]))
    cy, cz = py.mean(axis=1), pz.mean(axis=1)
    inside = (cy >= y0) & (cy <= y1) & (cz >= z0) & (cz <= z1)
    if not inside.any():
        raise ValueError(f"no mesh triangles with their centroid in the box {box}")
    w = np.bincount(tri[inside].ravel(), weights=np.repeat(area[inside] / 3, 3), minlength=len(r["y"]))
    return w / w.sum()


def slope_through_origin(p, dT) -> float:
    """Least-squares slope (K/mW) of a line through the origin: sum(P dT) / sum(P^2).

    The rise is proportional to the power in this model, so the line has no offset.  fig4_heat.py uses the same formula.
    """
    p, dT = np.asarray(p, dtype=float), np.asarray(dT, dtype=float)
    return float(np.sum(p * dT) / np.sum(p * p))


def heat_sink_power(r: dict) -> float:
    """Heat (mW) that flows from the heater into the substrate, from the temperature map of the reference power.

    The substrate is the heat sink at T_AMBIENT.  Just above it, at z = -T_BOX + DELTA in the buried oxide, the flux is
    k dT/dz = k dT / DELTA, with dT the rise above the sink.  Integrated along y over the window and along the filament,
    it is the heat that flows into the sink, and it has to equal the power set.  Only this check uses K_OXIDE.
    """
    tri = Triangulation(r["y"], r["z"], triangles=np.asarray(r["elements"], dtype=int) - 1)
    y_line = np.linspace(-Y_SPAN / 2, Y_SPAN / 2, 4000)  # um
    dT = LinearTriInterpolator(tri, r["T"] - T_AMBIENT)(y_line, np.full_like(y_line, -t.T_BOX + DELTA))
    ok = ~np.ma.getmaskarray(dT)  # the interpolator returns nothing outside the mesh
    flux = K_OXIDE * np.ma.getdata(dT)[ok] / (DELTA * um)  # W/m^2
    per_length = np.sum(flux) * (y_line[1] - y_line[0]) * um  # W/m, a sum over the y points
    return float(L_HEATER * um * per_length * 1e3)


def bare_heater(lumapi) -> float:
    """Core temperature rise (K) at the reference power when only the waveguide and the heater are there."""
    gds = section_gds(OUT / f"{NAME}_bare.gds", doped=False, contacts=False, metal=False, heater=True)
    with lumapi.DEVICE(hide=True) as d:
        build(d, gds)
        d.save(str(OUT / f"{NAME}_bare.ldev"))  # a project has to be saved before it can run
        d.run()
        r = read_temperature(d)
        d.switchtolayout()
        d.save(str(OUT / f"{NAME}_bare.ldev"))
    return float(region_weights(r, CORE_BOX) @ r["T"] - T_AMBIENT)


def transient(d) -> dict:
    """Switch the reference power on at t = 0 and record the core temperature over time."""
    d.switchtolayout()
    d.select("HEAT")
    d.set("solver mode", "transient")
    d.set("transient min time step", 2e-8)
    d.set("transient max time step", 2e-6)
    d.set("shutter mode", "step on")  # the shutter gates the heat source
    d.set("shutter ton", T_ON)
    d.set("shutter tslew", 2e-8)
    d.select("HEAT::boundary conditions::substrate")
    d.set("bc mode", "transient")  # a constant table: it only tells the solver how long to run
    d.set("transient time steps", np.array([0.0, T_ON, T_ON + T_END]))
    d.set("transient value table", np.full(3, T_AMBIENT))
    d.select("HEAT::heater")
    d.set("total power", P_REFERENCE * 1e-3)  # main() leaves its last power set: the transient is at the reference power
    d.select("HEAT::T")
    d.set("save data", 0)
    d.run()
    raw = d.getresult("HEAT::T", "temperature")
    time_s = np.ravel(np.squeeze(raw["t"])) - T_ON  # counted from the moment the heater is switched on
    r = temperature_result(raw)
    rise = region_weights(r, CORE_BOX) @ r["T"] - T_AMBIENT  # nodes x time in, one value per time step out
    final = rise[-1]
    crossing = lambda level: float(np.interp(level * final, rise, time_s))  # noqa: E731  (rise never falls)
    t10, t63, t90 = crossing(0.1), crossing(1 - np.exp(-1)), crossing(0.9)
    return dict(transient_t=time_s, transient_core_dT=rise, tau=t63, t_rise=t90 - t10, f_3dB=0.35 / (t90 - t10))


def temperature_result(r) -> dict:
    """Nodal temperature (K), node positions (um) and, when the result has them, the mesh elements of a HEAT::T result."""
    out = dict(T=np.real(np.squeeze(r["T"])), y=np.squeeze(r["y"]) / um, z=np.squeeze(r["z"]) / um)
    for key in ("connectivity", "elements"):
        if key in r:
            out["elements"] = np.asarray(r[key])
    return out


def read_temperature(d) -> dict:
    return temperature_result(d.getresult("HEAT::T", "temperature"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--powers", type=float, nargs="*", default=[2.0, 5.0, 10.0, 20.0], help="heater power (mW)")
    ap.add_argument("--no-transient", action="store_true", help="skip the transient run")
    ap.add_argument("--no-bare", action="store_true", help="skip the run without metal 1 and vias")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    gds = section_gds(OUT / f"{NAME}.gds", doped=True, contacts=True, metal=True, heater=True)
    ldev, mat = OUT / f"{NAME}.ldev", OUT / f"{NAME}_T.mat"
    powers = sorted(set(a.powers) | {P_REFERENCE})
    core_dT, heater_dT, slab_dT = [], [], []
    res = dict(powers_mW=np.array(powers), L_heater=L_HEATER, L_ring=L_RING, P_reference_mW=P_REFERENCE)
    with lumapi.DEVICE(hide=True) as d:
        build(d, gds)
        d.save(str(ldev))
        for power in powers:
            d.switchtolayout()
            d.select("HEAT::heater")
            d.set("total power", power * 1e-3)
            d.select("HEAT::T")
            reference = abs(power - P_REFERENCE) < 1e-9
            d.set("save data", int(reference))
            if reference:
                d.set("filename", str(mat))
            d.run()
            r = read_temperature(d)
            T, y, z = r["T"], r["y"], r["z"]
            core_dT.append(float(region_weights(r, CORE_BOX) @ T - T_AMBIENT))
            heater_dT.append(float(region_weights(r, FILM_BOX) @ T - T_AMBIENT))
            slab_dT.append(float(T.max() - T_AMBIENT))
            print(
                f"P = {power:5.1f} mW:  core +{core_dT[-1]:6.2f} K   heater +{heater_dT[-1]:6.2f} K   ({time.time() - t0:.0f} s)",
                flush=True,
            )
            if reference:
                res.update(T_map=T.astype(np.float32), T_y=y, T_z=z)
                if "elements" in r:
                    res["T_elements"] = r["elements"]
                    res["P_sink_mW"] = heat_sink_power(r)
                    print(
                        f"energy balance: {res['P_sink_mW']:.2f} mW reach the heat sink, {P_REFERENCE:.2f} mW were set",
                        flush=True,
                    )
        d.switchtolayout()
        d.save(str(ldev))
        if not a.no_transient:
            res.update(transient(d))
            d.switchtolayout()  # drop the stored time steps: they make the project file 15 times larger
            d.save(str(ldev))
            print(
                f"transient: tau = {res['tau'] * 1e6:.1f} us, 10-90 % rise {res['t_rise'] * 1e6:.1f} us  ({time.time() - t0:.0f} s)",
                flush=True,
            )
    if not a.no_bare:
        res["bare_dT_dP"] = bare_heater(lumapi) / P_REFERENCE
        print(f"without metal 1 and vias: {res['bare_dT_dP']:.3f} K/mW  ({time.time() - t0:.0f} s)", flush=True)

    slope = slope_through_origin(powers, core_dT)  # K per mW in the heated section
    heater_slope = slope_through_origin(powers, heater_dT)  # K per mW in the TiN film
    resistance = t.HEATER_SHEET_RESISTANCE * L_HEATER / rm.HEATER_WIDTH
    volts = (P_REFERENCE * 1e-3 * resistance) ** 0.5
    amps = volts / resistance
    res.update(core_dT=np.array(core_dT), heater_dT=np.array(heater_dT), max_dT=np.array(slab_dT), dT_dP=slope,
               heater_dT_dP=heater_slope, R_heater=resistance, V_reference=volts)  # fmt: skip
    beyond = (L_HEATER - L_PN) / L_HEATER  # share of the free filament outside the PN section, where the electrodes are
    lines = [
        f"TiN heater: {rm.HEATER_WIDTH} um wide, {t.T_HEATER} um thick, {Z_M1 - T_SI:.2f} um above the core; filament {L_HEATER:.2f} um",
        f"{'P (mW)':>7} {'core dT (K)':>12} {'heater dT (K)':>14}",
        *[f"{p:7.1f} {c:12.2f} {h:14.2f}" for p, c, h in zip(powers, core_dT, heater_dT, strict=True)],
        "averages over the mesh are area-weighted; slopes are least squares through the origin",
        f"\ncore temperature in the heated section: {slope:.3f} K/mW",
        f"heater film: {heater_slope:.3f} K/mW",
        f"averaged over the ring ({L_HEATER / L_RING:.0%} of it is heated): {slope * L_HEATER / L_RING:.3f} K/mW",
        f"  the average assumes electrodes along the whole filament, but {beyond:.0%} of the filament "
        f"({L_HEATER - L_PN:.1f} of {L_HEATER:.1f} um) lies beyond the electrodes",
    ]
    if "bare_dT_dP" in res:
        cost = 1 - slope / res["bare_dT_dP"]
        lines.append(
            f"without metal 1 and the contact vias the core would reach {res['bare_dT_dP']:.3f} K/mW: the electrodes cost {cost:.0%}"
        )
    lines += [
        f"\nfree filament: resistance {t.HEATER_SHEET_RESISTANCE:.1f} ohm/sq x {L_HEATER:.1f} um / {rm.HEATER_WIDTH} um"
        f" = {resistance:.0f} ohm",
        f"{P_REFERENCE:.0f} mW needs {volts:.2f} V and {amps * 1e3:.1f} mA across it",
        "R, V and I are those of the free filament: the landings and the current spreading into them add a few per cent"
        " that this estimate leaves out",
    ]
    if "tau" in res:
        ratio = res["t_rise"] / res["tau"]
        lines += [
            "",
            "transient, reference power switched on at t = 0:",
            f"  time constant tau: the core rise reaches 1 - 1/e = 63 % of its final value at {res['tau'] * 1e6:.1f} us",
            f"  10-90 % rise time: the time from the 10 % to the 90 % point of the final value is {res['t_rise'] * 1e6:.1f} us",
            f"  the response is not a single exponential (heat diffuses): t_rise / tau = {ratio:.2f}, "
            f"a single exponential would give ln 9 = {np.log(9):.2f}",
            f"  0.35 / t_rise = {res['f_3dB'] / 1e3:.1f} kHz is a rule of thumb for the bandwidth, not a measured 3 dB point",
        ]
    if "P_sink_mW" in res:
        p_sink = res["P_sink_mW"]
        off = 100 * (p_sink / P_REFERENCE - 1)
        lines += [
            "",
            f"energy balance: {p_sink:.2f} mW reach the heat sink, {P_REFERENCE:.2f} mW were set ({off:+.1f} %)",
            f"  flux k dT/dz at {DELTA} um above the substrate, k = {K_OXIDE} W/m/K; this check does not enter the simulation",
        ]
        if abs(p_sink - P_REFERENCE) > 0.02 * P_REFERENCE:
            lines.append(
                f"WARNING: the heat sink receives {off:+.1f} % of the power set: check the mesh and the heat sink "
                "before using these numbers"
            )
    lines.append("The top of the oxide is treated as insulating; convection and radiation are neglected.")
    np.savez_compressed(OUT / f"{NAME}_heat.npz", **res)
    (OUT / f"{NAME}_heat.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

"""Step 3 - HEAT, transient: how fast the phase shifter is, and what the trenches cost in speed.

Model: the cross-section of step 1, with the heater power switched on at t = 0.  The run starts cold; the mean
temperature of the core is read at every time step.  For the device the power is switched off again, so that the
fall is simulated as well as the rise.

Answers:
    a   the time constant (the rise reaches 1 - 1/e = 63 % of its final value) and the 10 to 90 % rise time of the
        device and of the reference without trenches; the fall of the device against its rise
    b   the same for the trench gaps of step 1, and with the power for pi of each gap the product of power and
        time, the figure of merit that papers on phase shifters quote
    c   checks: the final value against the steady state of step 1, the time step halved, a run twice as long, and
        an estimate of the time constant by hand

The power for pi of a gap is the value of step 2 for the fully isolated cross-section, scaled by the core rise per
milliwatt that step 1 found for that gap: a scaling, not a mode-solver run for every gap.  The reference is the test
of that scaling: step 2 solved it directly.

    python heat_transient.py
    python heat_transient.py --gaps 3 6

Output in 3_switching_time/:  switching.txt, switching.npz, heat_transient.ldev (the device, in layout mode).  The
layouts and projects of the other runs go to build/scratch/tops/time/.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from common import (
    HEAT_DIR,
    HEATER_WIDTH,
    LENGTH,
    REPO,
    ROOT,
    TRENCH_GAP,
    WIDTH,
    clean_logs,
    import_lumapi,
    require_process_file,
    section_gds,
    step_dir,
    t,
)
from solvers import (
    T_AMBIENT,
    add_heat_cross_section,
    area_trace,
    crossing_time,
    run_heat_transient,
)

OUT = step_dir("3_switching_time")
SCRATCH = REPO / "build" / "scratch" / "tops" / "time"  # layouts and projects of the sweep: git-ignored, not kept
PHASE_DIR = ROOT / "2_phase_shift"
HEAT_SOLID, SINK_SOLID = "Heater", "Si_Substrate"
P_REF = 10.0  # mW: the power that is switched; the times do not depend on it, the model is linear [construction]
Y_SPAN = 40.0  # um, as in step 1
Z_MIN, Z_MAX = -(t.T_BOX + t.T_SUBSTRATE_SIM) + 0.5, t.Z_TOP - 0.2
MIN_EDGE, MAX_EDGE = 0.02, 0.5  # um: the mesh of step 1
T_ON = 1e-7  # s: the heat source goes on at this time of the run
T_HIGH = 400e-6  # s: it stays on this long: many time constants of the slowest case
T_LOW = 400e-6  # s: the device is watched this long after the power goes off
MIN_STEP, MAX_STEP = 2e-8, 2e-6  # s: limits of the solver's time step, as in step 4 of the ring modulator
GAPS = (3.0, 4.0, 6.0)  # um: trench gaps of b, beside the device (TRENCH_GAP) and the reference without trenches
CORE_BOX = (-(WIDTH / 2 + 0.02), WIDTH / 2 + 0.02, -0.01, t.T_SI + 0.01)  # (y0, y1, z0, z1) um: the silicon core
FILM_BOX = (-HEATER_WIDTH / 2, HEATER_WIDTH / 2, t.Z_HEATER - 0.01, t.Z_HEATER + t.T_HEATER + 0.01)  # the TiN film
TAU_LEVEL = 1 - np.exp(-1)
TAIL = (60e-6, 150e-6)  # s: the late part of the rise, where only the slowest mode is left; fitted for the check by hand
# for the estimate by hand only; the solver takes its own values from the process file
K_OXIDE = 1.38  # W/m/K [assumed]: SiO2 (Glass) - Sze of the HEAT database, the value the energy balance of step 1 confirms
RHO_C_OXIDE = 2203 * 709  # J/m^3/K [assumed]: density times specific heat of fused silica, textbook values


def simulate(lumapi, name: str, gap: float | None, t_high: float, t_low: float, max_step: float, project: Path,
             gds: Path) -> dict:  # fmt: skip
    """One transient run.  Returns the times and the rise of the core and of the film at each of them."""
    section_gds(gds, trench_gap=gap)
    project.parent.mkdir(parents=True, exist_ok=True)
    with lumapi.DEVICE(hide=True) as d:
        add_heat_cross_section(d, gds, LENGTH, Y_SPAN, Z_MIN, Z_MAX, HEAT_SOLID, SINK_SOLID, MIN_EDGE, MAX_EDGE)
        d.save(str(project))
        r = run_heat_transient(d, project, P_REF, T_ON, t_high, t_low, MIN_STEP * max_step / MAX_STEP, max_step)
        d.switchtolayout()  # drop the stored time steps: they make the project file many times larger
        d.save(str(project))
    return dict(name=name, gap=gap, t=r["t"], core=area_trace(r, CORE_BOX) - T_AMBIENT, film=area_trace(r, FILM_BOX) - T_AMBIENT)


def times(run: dict, t_high: float) -> dict:
    """The time constant and the 10 to 90 % time of the rise; of the fall too when the run has one."""
    tt, core = run["t"], run["core"]
    on = (tt >= 0) & (tt <= t_high)
    final = float(core[on][-1])
    rise = lambda level: crossing_time(tt[on], core[on], level * final)  # noqa: E731
    out = dict(final=final, film_final=float(run["film"][on][-1]), tau=rise(TAU_LEVEL), t10=rise(0.1), t90=rise(0.9))
    out["t_rise"] = out["t90"] - out["t10"]
    out["settled_pct"] = float(100 * (1 - core[on][-1 - len(core[on]) // 10] / final))  # what the last tenth of the rise adds
    late = on & (tt >= TAIL[0]) & (tt <= TAIL[1])
    out["tau_tail"] = float(-1 / np.polyfit(tt[late], np.log(final - core[late]), 1)[0])  # s: how what is still missing decays
    off = tt >= t_high
    if off.sum() > 2:
        drop = final - core[off]  # how far the core has fallen: it rises from 0 like the trace of the rise
        fall = lambda level: crossing_time(tt[off] - t_high, drop, level * final)  # noqa: E731
        out.update(tau_fall=fall(TAU_LEVEL), t_fall=fall(0.9) - fall(0.1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gaps", type=float, nargs="*", default=list(GAPS), help="trench gaps beside the device's (um)")
    ap.add_argument("--no-checks", action="store_true", help="skip the runs with half the time step and twice the length")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    heat, phase = np.load(HEAT_DIR / "heat.npz"), np.load(PHASE_DIR / "phase.npz")
    names = list(heat["case_name"])
    eta = lambda case: float(heat["case_eta_core_Kum"][names.index(case)])  # noqa: E731  K um/mW of step 1
    steady = lambda case: float(heat["case_core_K_per_mW"][names.index(case)]) * P_REF  # noqa: E731  K at P_REF
    p_pi_isolated, p_pi_reference = float(phase["P_pi_mW"][0]), float(phase["P_pi_mW"][2])

    plan = [("device", TRENCH_GAP, "device", T_LOW)]
    plan += [(f"gap_{gap:g}", gap, f"gap_{gap:g}", 0.0) for gap in sorted(a.gaps)]
    plan += [("reference", None, "reference", 0.0)]
    runs, rows = {}, {}
    for name, gap, case, t_low in plan:
        kept = name == "device"
        project = OUT / "heat_transient.ldev" if kept else SCRATCH / "ldev" / f"{name}.ldev"
        gds = OUT / "device_section.gds" if kept else SCRATCH / "gds" / f"{name}.gds"
        runs[name] = simulate(lumapi, name, gap, T_HIGH, t_low, MAX_STEP, project, gds)
        row = times(runs[name], T_HIGH)
        p_pi = p_pi_isolated * eta("device") / eta(case)  # the scaling: P_pi is inversely proportional to the core rise per mW
        row.update(gap=gap, steady=steady(case), p_pi=p_pi, product=p_pi * row["tau"] * 1e6, steps=len(runs[name]["t"]))
        rows[name] = row
        print(f"  {name:<10} tau {row['tau'] * 1e6:6.2f} us   10-90 % {row['t_rise'] * 1e6:6.2f} us   final {row['final']:7.3f} K "
              f"(steady {row['steady']:7.3f} K)   {row['steps']} steps   ({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

    checks = {}
    if not a.no_checks:
        fine = simulate(lumapi, "device_fine", TRENCH_GAP, T_HIGH, T_LOW, MAX_STEP / 2, SCRATCH / "ldev" / "device_fine.ldev",
                        SCRATCH / "gds" / "device_fine.gds")  # fmt: skip
        long = simulate(lumapi, "device_long", TRENCH_GAP, 2 * T_HIGH, 0.0, MAX_STEP, SCRATCH / "ldev" / "device_long.ldev",
                        SCRATCH / "gds" / "device_long.gds")  # fmt: skip
        checks = dict(fine=times(fine, T_HIGH), long=times(long, 2 * T_HIGH), fine_steps=len(fine["t"]))
        print(f"  checks: tau {checks['fine']['tau'] * 1e6:.2f} us with half the time step, {checks['long']['tau'] * 1e6:.2f} us "
              f"in a run twice as long  ({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

    dev, ref = rows["device"], rows["reference"]
    worst = max(rows, key=lambda n: rows[n]["product"])  # the case with the largest product of power and time
    worst_gap = rows[worst]["gap"]
    height = (t.T_BOX + Z_MAX) * 1e-6  # m: the oxide column of the model, from the substrate to the top of the region
    trenched = [n for n in rows if rows[n]["gap"] is not None]
    ratios = [rows[n]["product"] / ref["product"] for n in trenched]  # the product of each trench over that without
    tails = [rows[n]["tau_tail"] * 1e6 for n in trenched if n != "device"]
    span = lambda v: f"{min(v):.1f}" if f"{min(v):.1f}" == f"{max(v):.1f}" else f"{min(v):.1f} to {max(v):.1f}"  # noqa: E731
    alpha = K_OXIDE / RHO_C_OXIDE  # m^2/s: thermal diffusivity of the oxide
    tau_column = 4 * height**2 / (np.pi**2 * alpha)  # the slowest mode of a column held cold at its foot, insulated on top
    scaling = 100 * (ref["p_pi"] / p_pi_reference - 1)
    lines = [
        f"HEAT, two-dimensional transient, Lumerical 2025 R1: mesh {MIN_EDGE:g} to {MAX_EDGE:g} um, time step {MIN_STEP:g} to "
        f"{MAX_STEP:g} s, {P_REF:g} mW switched on at t = 0 for {T_HIGH * 1e6:.0f} us; run time {(time.time() - t0) / 60:.1f} min",
        f"answer: the device has a time constant of {dev['tau'] * 1e6:.1f} us and rises from 10 to 90 % in "
        f"{dev['t_rise'] * 1e6:.1f} us; without trenches {ref['tau'] * 1e6:.1f} and {ref['t_rise'] * 1e6:.1f} us.  The trenches make "
        f"it {dev['tau'] / ref['tau']:.1f} times slower and lower the power for pi {ref['p_pi'] / dev['p_pi']:.2f} times "
        "(the cross-section with a trench on each side; step 2 has the device as drawn).",
        "",
        "a. rise and fall of the mean core temperature",
        f"{'case':>10} {'tau us':>8} {'10-90 % us':>11} {'t_rise/tau':>11} {'final K':>9} {'steady K':>9} {'diff %':>7}",
    ]
    for name in ("device", "reference"):
        row = rows[name]
        lines.append(f"{name:>10} {row['tau'] * 1e6:8.2f} {row['t_rise'] * 1e6:11.2f} {row['t_rise'] / row['tau']:11.2f} "
                     f"{row['final']:9.3f} {row['steady']:9.3f} {100 * (row['final'] / row['steady'] - 1):+7.2f}")  # fmt: skip
    lines += [
        f"  tau: the rise reaches 1 - 1/e = 63 % of its final value; a single exponential would give t_rise / tau = ln 9 = "
        f"{np.log(9):.2f}.  The response is not one exponential, because heat diffuses: it starts fast and ends slowly.",
        f"  fall of the device after {T_HIGH * 1e6:.0f} us of power: tau {dev['tau_fall'] * 1e6:.2f} us, 90 to 10 % in "
        f"{dev['t_fall'] * 1e6:.2f} us (rise: {dev['tau'] * 1e6:.2f} and {dev['t_rise'] * 1e6:.2f} us).  The model is linear, so the "
        "fall must mirror the rise.",
        f"  It does within {100 * abs(dev['t_fall'] / dev['t_rise'] - 1):.1f} % in the 10 to 90 % time; the time constant of the fall is "
        f"{100 * (dev['tau_fall'] / dev['tau'] - 1):+.1f} % off, because the solver starts the rise with its smallest time step and "
        "meets the switch-off with its largest (see c).",
        f"  0.35 / t_rise = {0.35 / dev['t_rise'] / 1e3:.1f} kHz for the device and {0.35 / ref['t_rise'] / 1e3:.1f} kHz for the "
        "reference: a rule of thumb for the bandwidth, not a simulated 3 dB point",
        "",
        "b. trench gap: time against power",
        f"{'gap (um)':>9} {'tau us':>8} {'10-90 % us':>11} {'P_pi mW':>8} {'P_pi x tau (mW us)':>19}",
    ]
    order = sorted(rows, key=lambda n: (rows[n]["gap"] is None, rows[n]["gap"] or 0.0))
    for name in order:
        row = rows[name]
        label = "none" if row["gap"] is None else f"{row['gap']:g}"
        lines.append(f"{label:>9} {row['tau'] * 1e6:8.2f} {row['t_rise'] * 1e6:11.2f} {row['p_pi']:8.2f} {row['product']:19.1f}")
    lines += [
        f"  P_pi of a gap = {p_pi_isolated:.2f} mW (step 2, fully isolated cross-section) x eta of the device / eta of that gap "
        "(step 1): a scaling",
        f"  the scaling gives {ref['p_pi']:.2f} mW without trenches; step 2 solved that case and found {p_pi_reference:.2f} mW "
        f"({scaling:+.2f} %)",
        f"  The product is smallest without trenches ({ref['product']:.0f} mW us) and largest at {worst_gap:g} um "
        f"({rows[worst]['product']:.0f}); the device has {dev['product']:.0f}.  Its trenches save power by a factor "
        f"{ref['p_pi'] / dev['p_pi']:.2f} and cost a factor {dev['tau'] / ref['tau']:.2f} in time.",
        "  A trench does not only keep the heat in: the heat now has to warm the whole wall of oxide before the core settles.",
        f"  With a trench the product is {min(ratios):.2f} to {max(ratios):.2f} times that of the guide without trenches: "
        + (
            "every trench of this table costs more time than it saves power."
            if min(ratios) > 1
            else "not every trench of this table costs more time than it saves power."
        ),
        "",
        "c. checks",
    ]
    if checks:
        fine, long = checks["fine"], checks["long"]
        lines += [
            f"  time step halved ({MIN_STEP / 2:g} to {MAX_STEP / 2:g} s, {checks['fine_steps']} steps against {dev['steps']}): tau "
            f"{fine['tau'] * 1e6:.2f} us ({100 * (fine['tau'] / dev['tau'] - 1):+.2f} %), 10-90 % {fine['t_rise'] * 1e6:.2f} us "
            f"({100 * (fine['t_rise'] / dev['t_rise'] - 1):+.2f} %); time constant of the fall {fine['tau_fall'] * 1e6:.2f} us "
            f"against {dev['tau_fall'] * 1e6:.2f} us: with the smaller step it lies {100 * (fine['tau_fall'] / fine['tau'] - 1):+.1f} % "
            "from that of the rise",
            f"  run twice as long ({2 * T_HIGH * 1e6:.0f} us): final rise {long['final']:.3f} K against {dev['final']:.3f} K "
            f"({100 * (long['final'] / dev['final'] - 1):+.3f} %), tau {long['tau'] * 1e6:.2f} us "
            f"({100 * (long['tau'] / dev['tau'] - 1):+.2f} %)",
        ]
    lines += [
        f"  final value against the steady state of step 1: device {100 * (dev['final'] / dev['steady'] - 1):+.2f} %, reference "
        f"{100 * (ref['final'] / ref['steady'] - 1):+.2f} %; the last tenth of the rise still adds {dev['settled_pct']:.3f} % "
        f"(device)",
        f"  by hand: between the trenches the oxide is a column h = {height * 1e6:.1f} um high (the region of the model ends "
        f"{t.Z_TOP - Z_MAX:.1f} um below the top of the cladding), cold at its foot and insulated on top and at its sides.",
        f"    Its slowest mode decays with 4 h^2 / (pi^2 alpha) = {tau_column * 1e6:.1f} us, with alpha = k / (rho c) = "
        f"{K_OXIDE} / {RHO_C_OXIDE:.3g} = {alpha:.2e} m^2/s (textbook values of fused silica; the solver uses the values of the "
        "process file)",
        f"    the late part of the simulated rise, from {TAIL[0] * 1e6:.0f} to {TAIL[1] * 1e6:.0f} us, decays with "
        f"{dev['tau_tail'] * 1e6:.1f} us ({100 * (dev['tau_tail'] / tau_column - 1):+.1f} %)"
        + (f"; the other gaps give {span(tails)} us: the same column, whatever its width" if tails else "")
        + f"; without trenches {ref['tau_tail'] * 1e6:.1f} us, and there the fit depends on its window: a layer has no slowest mode",
        f"    The time constant of the device, {dev['tau'] * 1e6:.1f} us, is shorter than that: the rise is a sum of the modes of "
        "the column, and the faster ones carry part of it.",
        "",
        "limits: a two-dimensional cross-section; the ends of the film, the metal wires and the air above the chip are not in",
        "  the model.  The times are those of the temperature of the core; the phase follows it without delay.",
    ]

    arrays = dict(
        power_mW=P_REF,
        t_high_s=T_HIGH,
        case_name=np.array(order),
        case_gap_um=np.array([np.nan if rows[n]["gap"] is None else rows[n]["gap"] for n in order]),
        case_tau_s=np.array([rows[n]["tau"] for n in order]),
        case_t_rise_s=np.array([rows[n]["t_rise"] for n in order]),
        case_final_K=np.array([rows[n]["final"] for n in order]),
        case_steady_K=np.array([rows[n]["steady"] for n in order]),
        case_P_pi_mW=np.array([rows[n]["p_pi"] for n in order]),
        case_product_mW_us=np.array([rows[n]["product"] for n in order]),
        device_tau_fall_s=dev["tau_fall"],
        device_t_fall_s=dev["t_fall"],
        tau_column_s=tau_column,
        case_tau_tail_s=np.array([rows[n]["tau_tail"] for n in order]),
        tail_window_s=np.array(TAIL),
    )
    for name in order:  # the traces, for the figure
        arrays[f"{name}_t_s"] = runs[name]["t"]
        arrays[f"{name}_core_K"] = runs[name]["core"].astype(np.float32)
    arrays["device_film_K"] = runs["device"]["film"].astype(np.float32)
    np.savez_compressed(OUT / "switching.npz", **arrays)
    (OUT / "switching.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean_logs(OUT)
    clean_logs(SCRATCH / "ldev")
    print("\n".join(lines))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

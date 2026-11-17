"""Step 4 - HEAT: what a waveguide beside the phase shifter feels.

In a mesh of interferometers the neighbours of a heated waveguide are other arms.  A neighbour that warms by a
fraction of the heated core's own rise takes the same fraction of its phase, unasked.  Heat reaches a neighbour on
two paths: sideways through the oxide, and down into the silicon substrate, along it, and up again.

Runs, all two-dimensional steady states of the cross-section of step 1 in a region 120 um wide:
    a   the substrate held at 300 K, as in steps 1 to 3: only the path through the oxide exists.  The rise at the
        height of the core against the distance from the heated waveguide, with and without the trenches
    b   the substrate in the model: the process file has 10 um of it, and now the bottom of the simulation region
        is held at 300 K instead of the whole solid.  This shows the path through the substrate, under the
        trenches, and how good the approximation of steps 1 to 3 is for the heated core itself
    c   not a simulation: an estimate by formula of the path through the substrate of a real wafer, which is far
        thicker than 10 um, so that the heat of a heater 100 um long spreads in three dimensions.  The formula of
        a slab with a cold bottom is first checked against run b

    python neighbour_heat.py

Output in 4_neighbour/:  neighbour.txt, neighbour.npz, neighbour_heat.ldev (the device with its substrate in the
model, in layout mode).  The other projects go to build/scratch/tops/neighbour/.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from common import (
    LENGTH,
    REPO,
    ROOT,
    TRENCH_GAP,
    TRENCH_WIDTH,
    WIDTH,
    clean_logs,
    import_lumapi,
    require_process_file,
    section_gds,
    step_dir,
    t,
    um,
)
from solvers import (
    SINK_NAME,
    T_AMBIENT,
    add_heat_cross_section,
    area_mean,
    conductivity_from_flux,
    read_temperature,
    run_checked,
    set_heat_power,
    temperature_along,
)

OUT = step_dir("4_neighbour")
SCRATCH = REPO / "build" / "scratch" / "tops" / "neighbour"
PHASE_DIR = ROOT / "2_phase_shift"
HEAT_SOLID, SINK_SOLID = "Heater", "Si_Substrate"
P_REF = 10.0  # mW [construction]: the model is linear, every result is given per milliwatt or as a fraction
Y_SPAN = 120.0  # um: the rise falls by a factor e about every 5 um, so 60 um to each side hold all of it
Z_MIN, Z_MAX = -(t.T_BOX + t.T_SUBSTRATE_SIM) + 0.5, t.Z_TOP - 0.2  # inside the substrate ... inside the top oxide
MIN_EDGE, MAX_EDGE = 0.02, 0.5  # um: the mesh of step 1
Z_CORE = t.T_SI / 2  # um: the height at which a neighbouring core lies
Z_SUBSTRATE = -t.T_BOX  # um: the surface of the substrate
H_MODEL = Z_SUBSTRATE - Z_MIN  # um: the substrate that run b has in its model
CORE_BOX = (-(WIDTH / 2 + 0.02), WIDTH / 2 + 0.02, -0.01, t.T_SI + 0.01)
DISTANCES = (5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0)  # um from the centre of the heated waveguide [construction]
PROFILE = np.arange(0.0, 55.01, 0.25)  # um: the points of the profile kept for the figure
SUBSTRATE_PLANES = (-8.5, -10.5)  # um: two planes in the substrate below the trenches (which end at -7 um), for run b
BOX_PLANES = (-0.5, -1.5)  # um: two planes in the buried oxide, for the same reading in run a
CHECK_AT = (10.0, 20.0, 30.0, 40.0)  # um: where the slab formula is compared with run b
NOTHING = 1e-9  # K/mW: a rise below this is the rounding of the solver, not a temperature
DECAY_FIT = (15.0, 50.0)  # um: where the fall of the rise in the oxide is fitted (run a, no trenches)
# for the estimate c only [assumed]: a 200 mm wafer is 725 um thick (the usual value; not a value of this process),
# and its back is taken as a perfect heat sink
WAFER = 725.0  # um
ESTIMATE_AT = (25.0, 50.0, 100.0, 250.0)  # um: distances of the table of c
ESTIMATE_CURVE = np.geomspace(10.0, 300.0, 60)  # um: the same estimate as a curve, for the figure


def simulate(lumapi, name: str, gap: float | None, substrate: bool, project: Path, gds: Path) -> dict:
    """One steady run.  substrate=True holds the bottom face of the region at 300 K, so the substrate is in the model."""
    section_gds(gds, trench_gap=gap)
    project.parent.mkdir(parents=True, exist_ok=True)
    with lumapi.DEVICE(hide=True) as d:
        add_heat_cross_section(d, gds, LENGTH, Y_SPAN, Z_MIN, Z_MAX, HEAT_SOLID, SINK_SOLID, MIN_EDGE, MAX_EDGE)
        if substrate:
            d.select(f"HEAT::boundary conditions::{SINK_NAME}")
            d.set("surface type", "simulation region")  # the bottom face of the region instead of the solid
            d.set("z min", 1)
        d.save(str(project))
        set_heat_power(d, P_REF)
        run_checked(d, project)
        r = read_temperature(d)
        d.switchtolayout()
        d.save(str(project))
    return r


def slab(distance, thickness: float):
    """ln coth(pi d / (4 H)): the rise at the distance d on the surface of a slab of thickness H whose bottom is
    held cold and whose surface is insulated, for a line source of heat on that surface, in units of
    (power per length) / (pi k)."""
    return np.log(1 / np.tanh(np.pi * np.asarray(distance, dtype=float) / (4 * thickness)))


def image_sum(d1: float, d2: float, thickness: float, images: int = 200000) -> float:
    """slab(d1) - slab(d2) from the sources themselves, as a check of the closed form.

    A cold bottom and an insulated surface are met by a row of line sources of alternating sign at the heights
    2 n H.  Each gives -ln(r) at the distance r.  The sum for one distance does not converge; the difference of two does.
    """
    n = np.arange(-images, images + 1)
    sign = np.where(n % 2 == 0, 1.0, -1.0)
    r1 = np.sqrt(d1**2 + (2 * n * thickness) ** 2)
    r2 = np.sqrt(d2**2 + (2 * n * thickness) ** 2)
    return float(np.sum(sign * (np.log(r2) - np.log(r1))))


def slab_check(r: dict, k_oxide: float, k_silicon: float) -> tuple[list[tuple[float, float, float]], float]:
    """The surface of the substrate in run b, simulated and by the slab formula.

    The oxide hands its heat to the substrate with the flux q(y) = k dT/dz just above the surface.  Each strip dy of
    it is a line source, and the formula adds them up:  T(y) = sum of q(y') dy' / (pi k_Si) x slab(|y - y'|, H).
    Returns rows of (distance, simulated rise, rise by the formula) in K/mW, and the power that the flux carries (mW).
    """
    step, delta = 0.02, 0.2  # um: the strips of the sum; the height over which the flux is taken
    y = np.arange(-Y_SPAN / 2 + step / 2, Y_SPAN / 2, step)  # strip centres: no strip lies on a point of the check
    drop = temperature_along(r, y, Z_SUBSTRATE + delta) - temperature_along(r, y, Z_SUBSTRATE)
    flux = k_oxide * drop / (delta * um)  # W/m^2, downwards
    power = float(np.sum(flux) * step * um * LENGTH * um * 1e3)  # mW through the surface of the substrate
    simulated = temperature_along(r, np.array(CHECK_AT), Z_SUBSTRATE) - T_AMBIENT
    rows = []
    for d, seen in zip(CHECK_AT, simulated, strict=True):
        formula = float(np.sum(flux * step * um * slab(np.abs(d - y), H_MODEL)) / (np.pi * k_silicon))
        rows.append((d, float(seen) / P_REF, formula / P_REF))
    return rows, power


def equal_length(distance, length: float, thickness: float):
    """The mean rise along a neighbour as long as the heater and parallel to it at the distance d, when the heater is a
    line of that length on the surface of a wafer of thickness H whose back is cold, in units of power / (pi k):

        [asinh(L / d) - sqrt(1 + (d / L)^2) + d / L] / L  -  ln 2 / (2 H)

    The bracket is the mean of 1 / r over the two lines: the heat of a point source on a thick wafer spreads in three
    dimensions and gives power / (2 pi k r).  The last term is what the cold back takes off, to first order in d / H
    and L / H.
    """
    q = np.asarray(distance, dtype=float) / length
    return (np.arcsinh(1 / q) - np.sqrt(1 + q * q) + q) / length - np.log(2) / (2 * thickness)


def main() -> None:
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    phase = np.load(PHASE_DIR / "phase.npz")
    p_pi = float(phase["P_pi_mW"][1])  # mW: the device as drawn (step 2)
    core_drawn = float(phase["core_K_per_mW"][1])  # K/mW of the core of the device as drawn (steps 1 and 2)

    plan = {
        "device_a": (TRENCH_GAP, False),
        "reference_a": (None, False),
        "device_b": (TRENCH_GAP, True),
        "reference_b": (None, True),
    }
    maps = {}
    for name, (gap, substrate) in plan.items():
        kept = name == "device_b"
        project = OUT / "neighbour_heat.ldev" if kept else SCRATCH / "ldev" / f"{name}.ldev"
        gds = OUT / "device_section.gds" if kept else SCRATCH / "gds" / f"{name}.gds"
        maps[name] = simulate(lumapi, name, gap, substrate, project, gds)
        print(f"  {name:<12} core {(area_mean(maps[name], CORE_BOX) - T_AMBIENT) / P_REF:.4f} K/mW   "
              f"{len(maps[name]['T'])} nodes   ({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

    core = {name: (area_mean(r, CORE_BOX) - T_AMBIENT) / P_REF for name, r in maps.items()}  # K/mW
    at = {name: (temperature_along(r, DISTANCES, Z_CORE) - T_AMBIENT) / P_REF for name, r in maps.items()}  # K/mW
    profile = {name: (temperature_along(r, PROFILE, Z_CORE) - T_AMBIENT) / P_REF for name, r in maps.items()}
    k_oxide = conductivity_from_flux(maps["reference_a"], Y_SPAN, *BOX_PLANES, P_REF, LENGTH)
    k_si = {n: conductivity_from_flux(maps[n], Y_SPAN, *SUBSTRATE_PLANES, P_REF, LENGTH) for n in ("device_b", "reference_b")}
    k_silicon = k_si["reference_b"]
    check, power_in = slab_check(maps["reference_b"], k_oxide, k_silicon)
    worst = max(abs(formula / seen - 1) for _, seen, formula in check)

    def rise(value: float) -> str:
        if np.isnan(value):
            return "in the trench"
        return "none" if abs(value) < NOTHING else f"{value:.3e}"

    def share(value: float, own: float) -> str:
        if np.isnan(value):
            return "-"
        return "none" if abs(value) < NOTHING else f"{100 * value / own:.4f} %"

    def table(suffix: str) -> list[str]:
        ref, dev = f"reference_{suffix}", f"device_{suffix}"
        rows = [
            f"{'distance (um)':>14} {'no trenches K/mW':>17} {'share of phase':>15} {'trenches K/mW':>14} {'share of phase':>15}"
        ]
        for i, d in enumerate(DISTANCES):
            rows.append(f"{d:14.1f} {rise(at[ref][i]):>17} {share(at[ref][i], core[ref]):>15} {rise(at[dev][i]):>14} "
                        f"{share(at[dev][i], core[dev]):>15}")  # fmt: skip
        return rows

    unit = 1e-3 / (np.pi * k_silicon) * 1e6  # K um/mW: 1 mW / (pi k), with the lengths of the formula in um
    estimate = [(d, float(unit * equal_length(d, LENGTH, WAFER))) for d in ESTIMATE_AT]
    curve = unit * equal_length(ESTIMATE_CURVE, LENGTH, WAFER)
    at_50 = dict(estimate)[50.0]
    closed, summed = float(slab(25.0, WAFER) - slab(250.0, WAFER)), image_sum(25.0, 250.0, WAFER)
    outer = TRENCH_GAP + TRENCH_WIDTH
    y, (near, far_end) = PROFILE, DECAY_FIT
    far = (y >= near) & (y <= far_end)
    decay = float(-1 / np.polyfit(y[far], np.log(profile["reference_a"][far]), 1)[0])  # um: the rise falls by e over it
    h_oxide = Z_MAX - Z_SUBSTRATE  # um: the oxide of the model, from the substrate to the top of the region
    decay_by_hand = 2 * h_oxide / np.pi
    i20 = DISTANCES.index(20.0)
    lines = [
        f"HEAT, two-dimensional steady state, Lumerical 2025 R1: mesh {MIN_EDGE:g} to {MAX_EDGE:g} um, region {Y_SPAN:g} um wide, "
        f"norm length {LENGTH:g} um; run time {(time.time() - t0) / 60:.1f} min",
        f"answer: through the oxide a neighbour 20 um away takes {100 * at['reference_a'][i20] / core['reference_a']:.2f} % of the "
        "phase without trenches and nothing with them.  The trenches cannot stop the path through the substrate; for a wafer "
        f"{WAFER:g} um thick it is estimated at {100 * at_50 / core_drawn:.2f} % of the phase 50 um away.",
        "",
        "a. the substrate held at 300 K: the path through the oxide",
        f"  heated core: {core['device_a']:.4f} K/mW with trenches, {core['reference_a']:.4f} K/mW without (step 1 has the same "
        "cross-sections in a region 40 um wide)",
        *table("a"),
        "  share of phase: the rise of the neighbouring core divided by the rise of the heated core.  A neighbour that is as long",
        "  as the heater and lies beside it takes that share of the phase of the heated arm.",
        f"  Without trenches the rise falls by a factor e every {decay:.2f} um (fitted from {DECAY_FIT[0]:g} to {DECAY_FIT[1]:g} um).  "
        f"By hand: a layer of oxide h = {h_oxide:g} um high,",
        "  cold at its foot and insulated on top, passes a rise sideways as exp(-pi d / (2 h)): a factor e every 2 h / pi = "
        f"{decay_by_hand:.2f} um ({100 * (decay / decay_by_hand - 1):+.1f} %).",
        f"  With trenches the device has air from {TRENCH_GAP:g} to {outer:g} um.  Beyond it the oxide stays at the temperature of the "
        f"substrate, which this run holds at 300 K ('none': below {NOTHING:g} K/mW, the rounding of the solver).",
        f"  the buried oxide conducts {k_oxide:.3f} W/m/K in this run (from the flux between z = {BOX_PLANES[0]} and {BOX_PLANES[1]} um)",
        "",
        f"b. the substrate in the model: {H_MODEL:g} um of silicon, the bottom of the region held at 300 K",
        f"  heated core: {core['device_b']:.4f} K/mW with trenches ({100 * (core['device_b'] / core['device_a'] - 1):+.2f} % against a) "
        f"and {core['reference_b']:.4f} K/mW without ({100 * (core['reference_b'] / core['reference_a'] - 1):+.2f} %): what steps 1 to 3 "
        "leave out by holding the substrate at 300 K",
        *table("b"),
        f"  the substrate conducts {k_silicon:.1f} W/m/K in this run (from the flux between z = {SUBSTRATE_PLANES[0]} and "
        f"{SUBSTRATE_PLANES[1]} um; the run with trenches gives {k_si['device_b']:.1f})",
        "  Beyond the trenches the device is no longer cold: heat that went down into the substrate has passed under them.",
        f"  A layer of {H_MODEL:g} um with a cold bottom carries heat sideways over a few micrometres only.  A real wafer is far "
        "thicker: see c.",
        "",
        f"c. estimate by formula, not a simulation: the path through the substrate of a wafer {WAFER:g} um thick",
        "  check of the method on run b (no trenches).  A line source on the surface of a slab of thickness H with a cold bottom",
        "  warms the surface at the distance d by  (P / L) / (pi k) x ln coth(pi d / (4 H)).  The oxide hands its heat to the",
        "  substrate over a strip some micrometres wide; the formula, summed over that strip, against the simulated surface:",
        f"{'distance (um)':>14} {'simulated K/mW':>15} {'formula K/mW':>13} {'difference':>11}",
        *[f"{d:14.1f} {seen:15.3e} {formula:13.3e} {100 * (formula / seen - 1):+10.1f}%" for d, seen, formula in check],
        f"  the flux into the substrate carries {power_in:.3f} of the {P_REF:g} mW; the closed form against the sum over its image "
        f"sources, for H = {WAFER:g} um and the difference between 25 and 250 um: {closed:.6f} and {summed:.6f}",
        "",
        f"  the wafer.  A heater {LENGTH:g} um long is short against {WAFER:g} um of silicon, so its heat spreads in three dimensions:",
        "  a point source on a thick wafer warms the surface at the distance r by  P / (2 pi k r).  Summed over the heater and",
        "  averaged over a neighbour of the same length beside it, at the distance d, with the cold back to first order:",
        "      mean rise = P / (pi k) x { [asinh(L / d) - sqrt(1 + (d / L)^2) + d / L] / L - ln 2 / (2 H) }",
        f"  with L = {LENGTH:g} um, H = {WAFER:g} um, k = {k_silicon:.1f} W/m/K, and the core of the device rising {core_drawn:.3f} K/mW:",
        f"{'distance (um)':>14} {'neighbour K/mW':>15} {'share of phase':>15}",
        *[f"{d:14.1f} {value:15.3e} {100 * value / core_drawn:14.2f}%" for d, value in estimate],
        f"  At P_pi = {p_pi:.2f} mW a neighbour 50 um away warms by {at_50 * p_pi:.2f} K and takes {100 * at_50 / core_drawn:.2f} % of pi.",
        "  The share falls slowly, about as 1 / d: this path sets the floor of the crosstalk, with or without trenches.",
        "  The estimate assumes a perfect heat sink under the wafer and one heater.  The three-dimensional formula is not checked",
        "  by a simulation here: the runs of this step are two-dimensional.",
        "",
        f"limits: runs a and b are two-dimensional and have no ends.  Run b has {H_MODEL:g} um of substrate, not a wafer.  A design",
        "  needs a three-dimensional model of the chip on its carrier; c gives the order of magnitude.",
    ]

    arrays = dict(
        distances_um=np.array(DISTANCES),
        profile_y_um=PROFILE,
        case_name=np.array(list(plan)),
        core_K_per_mW=np.array([core[n] for n in plan]),
        k_oxide=k_oxide,
        k_silicon=k_silicon,
        substrate_in_model_um=H_MODEL,
        decay_um=decay,
        decay_by_hand_um=decay_by_hand,
        check_distance_um=np.array([row[0] for row in check]),
        check_simulated_K_per_mW=np.array([row[1] for row in check]),
        check_formula_K_per_mW=np.array([row[2] for row in check]),
        check_worst_pct=100 * worst,
        wafer_um=WAFER,
        estimate_distance_um=np.array([row[0] for row in estimate]),
        estimate_K_per_mW=np.array([row[1] for row in estimate]),
        estimate_curve_um=ESTIMATE_CURVE,
        estimate_curve_K_per_mW=curve,
        core_drawn_K_per_mW=core_drawn,
        P_pi_mW=p_pi,
    )
    for name in plan:
        arrays[f"{name}_at_K_per_mW"] = at[name]
        arrays[f"{name}_profile_K_per_mW"] = profile[name]
    np.savez_compressed(OUT / "neighbour.npz", **arrays)
    (OUT / "neighbour.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean_logs(OUT)
    clean_logs(SCRATCH / "ldev")
    print("\n".join(lines))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

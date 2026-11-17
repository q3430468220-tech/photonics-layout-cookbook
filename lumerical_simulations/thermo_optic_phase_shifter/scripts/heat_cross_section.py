"""Step 1 - HEAT: how much the core and the heater film warm per milliwatt, with and without the trenches.

Model: a straight piece of the device's cross-section along x: the silicon core (WG), the TiN film (HEATER) above it and,
for the device, two deep trenches (DEEPTRENCH) beside the core.  It is written to GDS and loaded into a Layer Builder
with gsip_process.lbr, so the stack, the materials and the heat sink come from the process file.  The run is a
two-dimensional steady state normalised to the heated length of the device (LENGTH): the power that is set is the total
heater power, and the rise per unit power times the length (K um/mW) does not depend on that length.

Answers:
    how many kelvin the core gains per milliwatt, for the device and for the reference without trenches, and what the
    trenches buy (a); how the rise depends on the trench gap (b) and on the heater width (c); and whether the energy
    balance, the width of the region, the mesh, the width of the trench and a one-dimensional estimate agree (d).

Runs, each a session of its own:
    a   device and reference at each power of --powers (5, 10, 20, 40 mW): rises, slopes through the origin, linearity;
        temperature maps at 10 mW (kept for the figure) and at 10 and 20 mW (exported for step 2, the device; 10 mW for
        the reference)
    b   trench gap 1.75, 2.5, 3, 4, 6 and 10 um (the device is the 2.0 um row).  1.75 um is closer than the rules
        allow (the wall between the trenches would be 3.5 um, the film 0.75 um from the trench) and is shown for
        the trend only
    c   heater width 1.0, 1.5 and 3.0 um, each with the closest trench gap the rules allow (2.0, 2.0 and 2.5 um), and
        without trenches
    d   the region 20 and 80 um wide (40 um is the device); the mesh with the edges halved; trench widths of 4 and 10 um

    python heat_cross_section.py                 # the default powers, all runs
    python heat_cross_section.py --powers 10 20

Output in 1_heat_cross_section/:  device_section.gds, reference_section.gds (the cross-sections), heat.txt and heat.npz
(the summary and the arrays), heat_cross_section.ldev (the device, saved in layout mode), and the temperature maps
device_T_10mW.mat, device_T_20mW.mat and reference_T_10mW.mat for step 2.  The sweep layouts and their projects go to
build/scratch/tops/heat/.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from common import (
    HEATER_RESISTANCE,
    HEATER_WIDTH,
    ISOLATED_FRACTION,
    LENGTH,
    SCRATCH,
    TRENCH_GAP,
    TRENCH_LENGTH,
    TRENCH_WIDTH,
    WIDTH,
    clean_logs,
    closest_trench_gap,
    import_lumapi,
    require_process_file,
    section_gds,
    step_dir,
    t,
    temperature_map,
    um,
)
from solvers import (
    T_AMBIENT,
    add_heat_cross_section,
    area_mean,
    export_temperature,
    heat_sink_power,
    read_temperature,
    run_checked,
    set_heat_power,
    slope_through_origin,
    temperature_at,
)

OUT = step_dir("1_heat_cross_section")
HEAT_SOLID, SINK_SOLID = "Heater", "Si_Substrate"  # the solids that the process file gives the film and the substrate
P_SWEEP = (5.0, 10.0, 20.0, 40.0)  # mW: the device goes above the power for 2 pi, which step 2 computes [construction]
P_REF = 10.0  # mW: the maps at this power are kept for the figure and exported for step 2 [construction]
P_SECOND = 20.0  # mW: a second exported map, so that step 2 can check that the response is linear [construction]
Y_SPAN = 40.0  # um: heat spreads sideways over many times the oxide thickness; 20 and 80 um are checked in d
Z_MIN, Z_MAX = -(t.T_BOX + t.T_SUBSTRATE_SIM) + 0.5, t.Z_TOP - 0.2  # inside the substrate ... inside the top oxide
MIN_EDGE, MAX_EDGE = 0.02, 0.5  # um: the mesh of step 4 of the ring modulator
K_OXIDE = 1.38  # W/m/K [assumed]: SiO2 (Glass) - Sze in the HEAT database, the value the solver uses; only the energy
# balance (heat_sink_power) takes it from here, so it cannot change a simulated rise
Z_SINK = -t.T_BOX  # um: the top of the substrate, the heat sink
DELTA = 0.2  # um: the energy-balance plane lies this far above the sink
Z_PLANE = Z_SINK + DELTA
CORE_BOX = (-(WIDTH / 2 + 0.02), WIDTH / 2 + 0.02, -0.01, t.T_SI + 0.01)  # (y0, y1, z0, z1) um: the silicon core
GAPS = (1.75, 2.0, 2.5, 3.0, 4.0, 6.0, 10.0)  # um: trench gaps of b; the device is the 2.0 um gap
WIDTHS = (1.0, 1.5, 3.0)  # um: heater widths of c; the device is the 2.0 um width
TRENCH_WIDTHS = (4.0, 10.0)  # um: trench widths of d, beside the device's 6.0 um


def film_box(width: float) -> tuple[float, float, float, float]:
    """The TiN film of a given width, with a little margin above and below (um): (y0, y1, z0, z1)."""
    return (-width / 2, width / 2, t.Z_HEATER - 0.01, t.Z_HEATER + t.T_HEATER + 0.01)


@dataclass(frozen=True)
class Case:
    """One layout and the solver settings it is run with, at each of its powers."""

    name: str
    group: str  # a, b, c or d: the question it answers, as in the docstring
    heater_width: float = HEATER_WIDTH
    trench_gap: float | None = TRENCH_GAP  # None: no trenches
    trench_width: float = TRENCH_WIDTH
    y_span: float = Y_SPAN
    min_edge: float = MIN_EDGE
    max_edge: float = MAX_EDGE
    powers: tuple[float, ...] = (P_REF,)
    exports: tuple[float, ...] = ()  # powers whose temperature map is saved for step 2


def cases(powers: tuple[float, ...]) -> list[Case]:
    """Every run of the step, in the order of the report: the device and the reference, then b, c and d."""
    out = [
        Case("device", "a", powers=powers, exports=(P_REF, P_SECOND)),
        Case("reference", "a", trench_gap=None, powers=powers, exports=(P_REF,)),
    ]
    out += [Case(f"gap_{gap:g}", "b", trench_gap=gap) for gap in GAPS if gap != TRENCH_GAP]
    for width in WIDTHS:
        out.append(Case(f"width_{width:g}_trench", "c", heater_width=width, trench_gap=closest_trench_gap(width)))
        out.append(Case(f"width_{width:g}_none", "c", heater_width=width, trench_gap=None))
    out += [
        Case("device_y20", "d", y_span=20.0),
        Case("device_y80", "d", y_span=80.0),
        Case("reference_y20", "d", trench_gap=None, y_span=20.0),
        Case("reference_y80", "d", trench_gap=None, y_span=80.0),
        Case("device_mesh_half", "d", min_edge=MIN_EDGE / 2, max_edge=MAX_EDGE / 2),
        Case("reference_mesh_half", "d", trench_gap=None, min_edge=MIN_EDGE / 2, max_edge=MAX_EDGE / 2),
    ]
    out += [Case(f"device_trench{w:g}", "d", trench_width=w) for w in TRENCH_WIDTHS]
    return out


def paths(case: Case) -> tuple[Path, Path]:
    """The layout and the project of a run.  The device and the reference are kept in the step folder; the rest go to
    scratch."""
    if case.name == "device":
        return OUT / "device_section.gds", OUT / "heat_cross_section.ldev"
    if case.name == "reference":
        return OUT / "reference_section.gds", SCRATCH / "ldev" / "reference.ldev"
    return SCRATCH / "gds" / f"{case.name}.gds", SCRATCH / "ldev" / f"{case.name}.ldev"


def measure(r: dict, case: Case, power: float) -> dict:
    """The numbers of one run at one power: the rises of the core and the film, the power that reaches the sink, the
    peak, and the rise 2 um beyond the outer edge of a trench at z = -1 um (the trench width check)."""
    gap = case.trench_gap
    beyond = float("nan") if gap is None else temperature_at(r, gap + case.trench_width + 2.0, -1.0) - T_AMBIENT
    return dict(
        power=power,
        core=area_mean(r, CORE_BOX) - T_AMBIENT,
        film=area_mean(r, film_box(case.heater_width)) - T_AMBIENT,
        sink=heat_sink_power(r, case.y_span, Z_PLANE, Z_SINK, K_OXIDE, T_AMBIENT, LENGTH),
        peak=float(np.max(r["T"]) - T_AMBIENT),
        beyond=beyond,
        nodes=len(r["T"]),
        triangles=len(r["elements"]),
    )


def simulate(lumapi, case: Case, gds: Path, project: Path) -> tuple[list[dict], dict | None]:
    """One session: the layout of ``case`` at each of its powers.  Returns a row per power and the map at P_REF."""
    rows, at_ref = [], None
    with lumapi.DEVICE(hide=True) as d:
        add_heat_cross_section(d, gds, LENGTH, case.y_span, Z_MIN, Z_MAX, HEAT_SOLID, SINK_SOLID, case.min_edge,
                               case.max_edge)  # fmt: skip
        d.save(str(project))  # a project has to be saved before it can run
        for power in case.powers:
            set_heat_power(d, power)
            export = temperature_map(case.name, power) if power in case.exports else None
            export_temperature(d, export)
            run_checked(d, project)
            if export is not None and not export.exists():
                raise RuntimeError(f"the run of {case.name} at {power:g} mW wrote no temperature map: {export}")
            r = read_temperature(d)
            rows.append(measure(r, case, power))
            if power == P_REF:
                at_ref = r
            row = rows[-1]
            print(f"  {case.name:<19} P = {power:5.1f} mW   core {row['core']:8.3f} K   film {row['film']:8.3f} K   "
                  f"sink {row['sink']:8.4f} mW", flush=True)  # fmt: skip
        d.switchtolayout()
        d.save(str(project))  # kept in layout mode, without the fields
    return rows, at_ref


def summarise(case: Case, rows: list[dict]) -> dict:
    """Slopes through the origin, linearity, the energy balance and the one-dimensional estimate of one case."""
    p = np.array([row["power"] for row in rows])
    core = np.array([row["core"] for row in rows])
    film = np.array([row["film"] for row in rows])
    k_core, k_film = slope_through_origin(p, core), slope_through_origin(p, film)
    balance = 100 * (np.array([row["sink"] for row in rows]) / p - 1)
    at_ref = next(row for row in rows if row["power"] == P_REF)
    gap = case.trench_gap
    # one-dimensional ridge between the trenches: eta = 1e3 t / (k W), with t the oxide thickness and W the ridge width
    eta_1d = float("nan") if gap is None else 1e3 * (t.T_BOX * um) / (K_OXIDE * (2 * gap * um))
    return dict(
        core_K_per_mW=k_core,
        film_K_per_mW=k_film,
        eta_core_Kum=k_core * LENGTH,
        eta_film_Kum=k_film * LENGTH,
        film_to_core=k_film / k_core,
        linearity_pct=float(100 * np.max(np.abs(core / p - k_core)) / k_core),
        balance_pct_ref=float(100 * (at_ref["sink"] / P_REF - 1)),
        balance_pct_max=float(np.max(np.abs(balance))),
        eta_1d_Kum=eta_1d,
        beyond_dT=at_ref["beyond"],
    )


def cell(x: float, fmt: str) -> str:
    """A number in a table, or a dash for a value that does not apply."""
    return "-" if x is None or np.isnan(x) else format(x, fmt)


def report(results: dict, elapsed: float) -> tuple[dict, list[str]]:
    """The arrays of heat.npz and the lines of heat.txt, from the results of every run."""
    dev, ref = results["device"], results["reference"]
    sd, sr = dev["summary"], ref["summary"]
    f = ISOLATED_FRACTION
    eta_iso, eta_ref = sd["eta_core_Kum"], sr["eta_core_Kum"]
    eta_drawn = f * eta_iso + (1 - f) * eta_ref  # the 2 um at each end of the film have no trench: the reference there
    resistance = t.HEATER_SHEET_RESISTANCE * LENGTH / HEATER_WIDTH  # ohm: R = Rs L / w
    volts = (P_REF * 1e-3 * resistance) ** 0.5  # V: P = V^2 / R
    amps = volts / resistance

    def at(name: str) -> dict:
        return next(row for row in results[name]["rows"] if row["power"] == P_REF)

    def pct(a: float, b: float) -> float:
        return 100 * (a / b - 1)

    closest = closest_trench_gap(HEATER_WIDTH)
    powers = [row["power"] for row in dev["rows"]]
    worst = max(results, key=lambda n: results[n]["summary"]["balance_pct_max"])
    lines = [
        f"HEAT, two-dimensional steady state, Lumerical 2025 R1: mesh {MIN_EDGE:g} to {MAX_EDGE:g} um, norm length "
        f"{LENGTH:g} um, {SINK_SOLID} held at {T_AMBIENT:g} K, uniform heat on {HEAT_SOLID}; run time {elapsed / 60:.1f} min",
        f"device: TiN film {HEATER_WIDTH:g} um wide, {t.T_HEATER * 1e3:.0f} nm thick, {t.Z_HEATER - t.T_SI:.2f} um above the "
        f"core; trenches from {TRENCH_GAP:g} to {TRENCH_GAP + TRENCH_WIDTH:g} um from the centre line, beside "
        f"{TRENCH_LENGTH:g} of the {LENGTH:g} um of film (f = {f:.2f})",
        f"answer: the core of the fully isolated cross-section gains {eta_iso / LENGTH:.3f} K/mW ({eta_iso:.1f} K um/mW); "
        f"the device as drawn gains {eta_drawn / LENGTH:.3f} K/mW ({eta_drawn:.1f} K um/mW); without trenches the core gains "
        f"{eta_ref / LENGTH:.3f} K/mW ({eta_ref:.1f} K um/mW).  The trenches multiply the rise by {eta_iso / eta_ref:.2f} "
        f"(fully isolated) or {eta_drawn / eta_ref:.2f} (as drawn).",
        "",
        "a. device and reference against the power (rises in K above the substrate, sink in mW)",
        f"{'P (mW)':>7} {'core dev':>10} {'film dev':>10} {'core ref':>10} {'film ref':>10} {'sink dev':>10} {'sink ref':>10}",
    ]
    for i, p in enumerate(powers):
        a_, b_ = dev["rows"][i], ref["rows"][i]
        lines.append(f"{p:7.1f} {a_['core']:10.3f} {a_['film']:10.3f} {b_['core']:10.3f} {b_['film']:10.3f} "
                     f"{a_['sink']:10.3f} {b_['sink']:10.3f}")  # fmt: skip
    lines += [
        f"slope through the origin, device: core {sd['core_K_per_mW']:.4f} K/mW, film {sd['film_K_per_mW']:.4f} K/mW, "
        f"film/core {sd['film_to_core']:.3f}, eta core {sd['eta_core_Kum']:.2f} K um/mW",
        f"slope through the origin, reference: core {sr['core_K_per_mW']:.4f} K/mW, film {sr['film_K_per_mW']:.4f} K/mW, "
        f"film/core {sr['film_to_core']:.3f}, eta core {sr['eta_core_Kum']:.2f} K um/mW",
        f"linearity: the largest deviation of rise/P from the slope over {min(powers):g} to {max(powers):g} mW: "
        f"device {sd['linearity_pct']:.3f} %, reference {sr['linearity_pct']:.3f} %",
        "",
        f"device as drawn: the film is trenched along {TRENCH_LENGTH:g} of {LENGTH:g} um, so the effective "
        f"eta = f eta_iso + (1 - f) eta_ref = {f:.2f} x {eta_iso:.2f} + {1 - f:.2f} x {eta_ref:.2f} = {eta_drawn:.2f} K um/mW",
        f"  K/mW as drawn = eta / L = {eta_drawn:.2f} / {LENGTH:g} = {eta_drawn / LENGTH:.4f} K/mW.  The formula averages two "
        "two-dimensional results along the film; the ends are not solved in three dimensions.",
        "",
        f"b. trench gap, heater {HEATER_WIDTH:g} um, {P_REF:g} mW; closest gap the rules allow: {closest:g} um",
        f"{'gap (um)':>9} {'rule':>12} {'core K/mW':>10} {'eta':>9} {'film K/mW':>10} {'film/core':>10} {'eta 1D':>8} "
        f"{'eta/1D':>7} {'balance %':>10}",
    ]
    b_names = sorted(
        [n for n in results if results[n]["case"].group == "b"] + ["device"], key=lambda n: results[n]["case"].trench_gap
    )
    for name in [*b_names, "reference"]:
        case, s, row = results[name]["case"], results[name]["summary"], at(name)
        gap = case.trench_gap
        rule = "no trench" if gap is None else ("ok" if gap >= closest - 1e-9 else "below rule")
        label = "none" if gap is None else f"{gap:g}"
        ratio = None if gap is None else s["eta_core_Kum"] / s["eta_1d_Kum"]
        lines.append(f"{label:>9} {rule:>12} {s['core_K_per_mW']:10.4f} {s['eta_core_Kum']:9.1f} {s['film_K_per_mW']:10.4f} "
                     f"{s['film_to_core']:10.3f} {cell(s['eta_1d_Kum'], '8.1f'):>8} {cell(ratio, '7.3f'):>7} "
                     f"{pct(row['sink'], P_REF):10.3f}")  # fmt: skip
    lines += [
        f"eta 1D: one-dimensional ridge between the trenches, eta = 1e3 t / (k W), with t = {t.T_BOX:g} um of buried oxide, "
        f"k = {K_OXIDE} W/m/K and W = 2 gap.",
        "  eta/1D above 1 is the cost of the constriction: the heat enters the ridge at the core, in its middle, and has to "
        "spread sideways across the ridge, which the one-dimensional model assumes has already happened.",
        "",
        f"c. heater width, {P_REF:g} mW; each width with the closest gap the rules allow, and without trenches",
        f"{'width':>7} {'gap (um)':>9} {'core K/mW':>10} {'core none':>10} {'ratio':>7} {'film/core':>10} {'film/core none':>15}",
    ]
    for width in (*WIDTHS, HEATER_WIDTH):
        with_name = "device" if width == HEATER_WIDTH else f"width_{width:g}_trench"
        none_name = "reference" if width == HEATER_WIDTH else f"width_{width:g}_none"
        st, sn = results[with_name]["summary"], results[none_name]["summary"]
        gap = results[with_name]["case"].trench_gap
        lines.append(f"{width:7.2f} {gap:9.2f} {st['core_K_per_mW']:10.4f} {sn['core_K_per_mW']:10.4f} "
                     f"{st['core_K_per_mW'] / sn['core_K_per_mW']:7.3f} {st['film_to_core']:10.3f} "
                     f"{sn['film_to_core']:15.3f}")  # fmt: skip
    current_mA = amps * 1e3
    lines += [
        "",
        f"electrical, the free filament at {P_REF:g} mW: R = Rs L / w = {t.HEATER_SHEET_RESISTANCE:.1f} ohm/sq x "
        f"{LENGTH:g} um / {HEATER_WIDTH:g} um = {resistance:.0f} ohm (builder: {HEATER_RESISTANCE:.0f} ohm); "
        f"V = {volts:.2f} V; I = {current_mA:.2f} mA",
        "  R, V and I are those of the free filament: the landings and the current spreading into them add a few per cent",
        "",
        "d. checks",
        f"energy balance at {P_REF:g} mW (power that reaches the sink against the power set): device "
        f"{at('device')['sink']:.3f} mW ({sd['balance_pct_ref']:+.2f} %), reference {at('reference')['sink']:.3f} mW "
        f"({sr['balance_pct_ref']:+.2f} %); worst of all {len(results)} runs {results[worst]['summary']['balance_pct_max']:.2f} %"
        f" ({worst})",
        f"region width (eta, K um/mW): device {eta_of(results, 'device_y20'):.2f} at 20 um, {eta_iso:.2f} at 40 um, "
        f"{eta_of(results, 'device_y80'):.2f} at 80 um ({pct(eta_of(results, 'device_y20'), eta_iso):+.2f} % and "
        f"{pct(eta_of(results, 'device_y80'), eta_iso):+.2f} %); reference {eta_of(results, 'reference_y20'):.2f}, "
        f"{eta_ref:.2f}, {eta_of(results, 'reference_y80'):.2f} "
        f"({pct(eta_of(results, 'reference_y20'), eta_ref):+.2f} % and {pct(eta_of(results, 'reference_y80'), eta_ref):+.2f} %)",
        f"mesh (edges halved, {MIN_EDGE / 2:g} and {MAX_EDGE / 2:g} um): device eta {eta_of(results, 'device_mesh_half'):.2f} "
        f"({pct(eta_of(results, 'device_mesh_half'), eta_iso):+.3f} %) with {at('device_mesh_half')['nodes']} nodes against "
        f"{at('device')['nodes']}; reference {eta_of(results, 'reference_mesh_half'):.2f} "
        f"({pct(eta_of(results, 'reference_mesh_half'), eta_ref):+.3f} %)",
        f"trench width (device, gap {TRENCH_GAP:g} um): eta {eta_of(results, 'device_trench4'):.2f} K um/mW at 4 um, "
        f"{eta_iso:.2f} at 6 um, {eta_of(results, 'device_trench10'):.2f} at 10 um; rise 2 um beyond the outer edge of the "
        f"trench, at z = -1 um: {at('device_trench4')['beyond']:.3f}, {at('device')['beyond']:.3f}, "
        f"{at('device_trench10')['beyond']:.3f} K",
        "  The trench is air from the top of the cladding down to 5 um inside the substrate, and its walls are adiabatic.  The "
        "heat of the core goes down into the substrate, which is held at 300 K, and cannot cross the trench in the oxide.",
        "  So the oxide beyond the trench stays near the sink whatever the trench width; the width does not enter the answer.",
        f"one-dimensional ridge (device): eta 1D = {sd['eta_1d_Kum']:.1f} K um/mW from t = {t.T_BOX:g} um, k = {K_OXIDE} W/m/K, "
        f"W = 2 x {TRENCH_GAP:g} um = {2 * TRENCH_GAP:g} um, against {eta_iso:.1f} simulated "
        f"({pct(eta_iso, sd['eta_1d_Kum']):+.1f} %)",
        f"linearity: {sd['linearity_pct']:.3f} % device and {sr['linearity_pct']:.3f} % reference over the powers of a",
        "",
        "limits: a two-dimensional cross-section, with no ends, no metal over the film, no convection, and the top of the",
        "  oxide insulating.  The undercut is not in the model: in two dimensions it has no solid path to the sink, and the",
        "  solver does not converge (see the probe notes in the chapter).  Step 2 gives the phase; this step gives only heat.",
        "maps kept at 10 mW: device and reference (heat.npz arrays device_map_* and reference_map_*); exported for step 2: "
        "device_T_10mW.mat, device_T_20mW.mat, reference_T_10mW.mat",
    ]

    names = list(results)

    def column(fn) -> np.ndarray:
        return np.array([fn(results[n]) for n in names], dtype=float)

    arrays = dict(
        powers_mW=np.array(powers, dtype=float),
        case_name=np.array(names),
        case_group=np.array([results[n]["case"].group for n in names]),
        case_heater_width_um=column(lambda x: x["case"].heater_width),
        case_trench_gap_um=column(lambda x: np.nan if x["case"].trench_gap is None else x["case"].trench_gap),
        case_trench_width_um=column(lambda x: x["case"].trench_width),
        case_y_span_um=column(lambda x: x["case"].y_span),
        case_min_edge_um=column(lambda x: x["case"].min_edge),
        case_max_edge_um=column(lambda x: x["case"].max_edge),
        case_core_K_per_mW=column(lambda x: x["summary"]["core_K_per_mW"]),
        case_film_K_per_mW=column(lambda x: x["summary"]["film_K_per_mW"]),
        case_eta_core_Kum=column(lambda x: x["summary"]["eta_core_Kum"]),
        case_eta_film_Kum=column(lambda x: x["summary"]["eta_film_Kum"]),
        case_film_to_core=column(lambda x: x["summary"]["film_to_core"]),
        case_eta_1D_Kum=column(lambda x: x["summary"]["eta_1d_Kum"]),
        case_balance_pct_at_Pref=column(lambda x: x["summary"]["balance_pct_ref"]),
        case_linearity_pct=column(lambda x: x["summary"]["linearity_pct"]),
        case_rise_2um_beyond_trench_K=column(lambda x: x["summary"]["beyond_dT"]),
        case_nodes=column(lambda x: next(r["nodes"] for r in x["rows"] if r["power"] == P_REF)),
        case_triangles=column(lambda x: next(r["triangles"] for r in x["rows"] if r["power"] == P_REF)),
        fully_isolated_eta_Kum=np.array(eta_iso),
        device_as_drawn_eta_Kum=np.array(eta_drawn),
        isolated_fraction=np.array(f),
        resistance_ohm=np.array(resistance),
        voltage_V_at_Pref=np.array(volts),
        current_mA_at_Pref=np.array(current_mA),
    )
    for label in ("device", "reference"):
        rows = results[label]["rows"]
        arrays[f"{label}_core_dT"] = np.array([r["core"] for r in rows])
        arrays[f"{label}_film_dT"] = np.array([r["film"] for r in rows])
        arrays[f"{label}_sink_mW"] = np.array([r["sink"] for r in rows])
        arrays[f"{label}_peak_dT"] = np.array([r["peak"] for r in rows])
        m = results[label]["at_ref"]
        arrays[f"{label}_map_T"] = m["T"].astype(np.float32)  # K
        arrays[f"{label}_map_y_um"] = m["y"]
        arrays[f"{label}_map_z_um"] = m["z"]
        arrays[f"{label}_map_triangles"] = np.asarray(m["elements"], dtype=np.int32)  # zero-based node numbers
    return arrays, lines


def eta_of(results: dict, name: str) -> float:
    return results[name]["summary"]["eta_core_Kum"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--powers", type=float, nargs="+", default=list(P_SWEEP),
                    help="heater powers of the device and the reference (mW); must include 10 and 20 mW")  # fmt: skip
    a = ap.parse_args()
    if not {P_REF, P_SECOND} <= set(a.powers):
        ap.error(f"--powers must include {P_REF:g} and {P_SECOND:g} mW, the powers whose maps are exported")
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    results: dict = {}
    for case in cases(tuple(sorted(set(a.powers)))):
        gds, project = paths(case)
        project.parent.mkdir(parents=True, exist_ok=True)  # Lumerical does not make the folder of a project
        section_gds(gds, trench_gap=case.trench_gap, heater_width=case.heater_width, trench_width=case.trench_width)
        print(
            f"{case.name} ({case.group}): heater {case.heater_width:g} um, gap "
            f"{'none' if case.trench_gap is None else f'{case.trench_gap:g} um'}, region {case.y_span:g} um",
            flush=True,
        )
        rows, at_ref = simulate(lumapi, case, gds, project)
        results[case.name] = dict(case=case, rows=rows, at_ref=at_ref, summary=summarise(case, rows))
    arrays, lines = report(results, time.time() - t0)
    np.savez_compressed(OUT / "heat.npz", **arrays)
    (OUT / "heat.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean_logs(OUT)
    clean_logs(SCRATCH / "ldev")
    print("\n".join(lines))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

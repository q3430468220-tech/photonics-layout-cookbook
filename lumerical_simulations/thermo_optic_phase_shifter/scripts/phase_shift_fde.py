"""Step 2 - MODE (FDE): the phase shift: how much heater power for pi, and for 2 pi.

Model: the cross-section of step 1 (the core, the film above it, the trenches beside it), loaded into a Layer Builder
with gsip_process.lbr.  The silicon of the process file is an index-perturbation material with a linear thermo-optic
coefficient, so its index follows the temperature once the simulation is given a temperature map.  The maps are those
step 1 exported; each is laid over the structure as a "temperature" grid attribute.  The phase of a waveguide of
length L changes by 2 pi L (change of n_eff) / lambda, so

    P_pi = lambda / (2 L  d n_eff / dP)        with P the total heater power and L the heated length

Answers:
    a   n_eff of TE0 cold and with the maps of 10 and 20 mW: the change per milliwatt, its linearity, P_pi and P_2pi,
        for the device and for the reference without trenches; and the change of n_eff per kelvin of core temperature,
        which is compared with the thermo-optic coefficient of silicon in the process file
    b   the device as drawn, whose trenches run beside 96 % of the film
    c   what P_pi and P_2pi ask of the heater: the rise of the core and of the film, the voltage and the current
    d   whether the trench disturbs the light: the cold mode with the wall at the design distance and closer
    e   whether the film absorbs light: the loss of the cold mode with and without the film in the window
    f   checks: a finer mesh, a wider window, and the cold n_eff against the strip waveguide chapter

Windows.  For a, b and f the window holds silicon and oxide only: it ends inside the oxide wall, before the trench,
and below the film.  For d it is wider, so that the wall of the trench lies inside it; for e it is higher, so that
the film does.  All have PML on four sides and a mesh line on every surface of the core.

    python phase_shift_fde.py
    python phase_shift_fde.py --mesh 0.01 --core-mesh 0.005

Output in 2_phase_shift/:  phase.txt, phase.npz, phase_shift.lms (the device, in layout mode).  The layouts of the
checks go to build/scratch/tops/phase/.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np
from common import (
    HEAT_DIR,
    HEATER_RESISTANCE,
    ISOLATED_FRACTION,
    LAM,
    LENGTH,
    REPO,
    TRENCH_GAP,
    TRENCH_LENGTH,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    require_process_file,
    section_gds,
    solvers,
    step_dir,
    t,
    temperature_map,
    um,
)

OUT = step_dir("2_phase_shift")
SCRATCH = REPO / "build" / "scratch" / "tops" / "phase"  # layouts of the checks: git-ignored, not kept
STRIP_MODES = REPO / "lumerical_simulations" / "strip_waveguide" / "1_waveguide_modes" / "strip_modes.npz"
PERTURBATION = REPO / "gsip_process_file_py" / "gsip_csv" / "index_perturbation_data.csv"
Y_SPAN, Z_SPAN = 3.4, 1.8  # um: the window of a, b and f: inside the oxide wall (the trench starts at 2 um) and below the film
Y_WALL = 5.0  # um: the window of d, wide enough to hold the wall of the trench at every distance of the check
Z_FILM = (-1.0, 1.75)  # um: the window of e, from below the core to above the film (the film lies from 1.10 to 1.25 um)
N_GUESS = 2.45  # the search starts near this index
POWERS = (10.0, 20.0)  # mW: the maps that step 1 exported for the device; the reference has the first one
WALL_GAPS = (1.5, 1.25, 1.0, 0.75)  # um: trench gaps of d, closer than the rules allow; the device is TRENCH_GAP
CORE = (-WIDTH / 2 - 0.35, WIDTH / 2 + 0.35)  # the range of y that counts as "in the waveguide" when modes are sorted


def silicon_dn_dt() -> float:
    """The thermo-optic coefficient of the silicon of the process file (1/K), from the table the compiler reads."""
    with open(PERTURBATION, encoding="utf-8", newline="") as handle:
        row = next(r for r in csv.DictReader(handle) if r["name"] == "Si_np")
    return float(row["dn/dt"])


def setup(m, gds: Path, mesh: float, core_mesh: float, y_span: float = Y_SPAN, z: tuple[float, float] | None = None,
          trial_modes: int = 8) -> None:  # fmt: skip
    """The mode solver on the cross-section in ``gds``.  z: the window in z (um); the default is Z_SPAN about the
    middle of the silicon."""
    m.switchtolayout()
    m.deleteall()
    add_layer_builder(m, gds, 6.0, max(y_span + 2.0, 22.0))  # the builder holds the trenches whatever the window
    solvers.add_fde(m, y_span, Z_SPAN, mesh, trial_modes=trial_modes, guess=N_GUESS)
    if z is not None:  # add_fde leaves the solver selected
        m.set("z", (z[0] + z[1]) / 2 * um)
        m.set("z span", (z[1] - z[0]) * um)
    solvers.add_strip_mesh(m, WIDTH, core_mesh)  # added last: a new object takes the selection


def te0(m, n_min: float) -> dict:
    """The fundamental TE mode of the last set-up; stops when there is none."""
    mode = solvers.pick(solvers.guided_modes(m, CORE, n_min), "TE")
    if mode is None or mode["te"] < 0.9:
        raise SystemExit("no TE0 mode found in the core: check the Layer Builder geometry and the search guess")
    return mode


def add_map(m, name: str, mat: Path) -> None:
    """A temperature map of step 1 as a grid attribute, switched off until it is asked for."""
    if not mat.exists():
        raise SystemExit(f"{mat} is missing: run heat_cross_section.py (step 1) first")
    m.addgridattribute("temperature")
    m.set("name", name)
    # forward slashes: in a path with backslashes Lumerical reads the backslash and the t of this device's folder
    # as a tab, and the file is not found ("in matlabload: cannot open file")
    m.importdataset(mat.as_posix())
    m.select(name)
    m.set("enabled", 0)


def with_maps(m, maps: dict[float, Path], n_min: float) -> tuple[dict, dict[float, dict]]:
    """TE0 cold, and with each temperature map in turn (power in mW -> map).  One map is on at a time."""
    names = {power: f"temperature {power:g} mW" for power in maps}
    for power, mat in maps.items():
        add_map(m, names[power], mat)
    cold = te0(m, n_min)
    hot = {}
    for power in maps:
        m.switchtolayout()
        for other, name in names.items():
            m.select(name)
            m.set("enabled", int(other == power))
        hot[power] = te0(m, n_min)
    m.switchtolayout()
    for name in names.values():
        m.select(name)
        m.set("enabled", 0)
    return cold, hot


def silicon_share(m, mode: dict) -> tuple[float, float, float]:
    """The share of the electric energy of a mode that lies in silicon, the index of silicon and of oxide.

    The share is the sum of n^2 |E|^2 over the silicon cells divided by the sum over all cells, each cell weighted by
    its area.  It needs the index on the grid of the mode; nan when the two grids differ.
    """
    index = solvers.index_map(m)
    n = index["index"].astype(float)
    at = lambda y, z: float(n[np.argmin(np.abs(index["y"] - y)), np.argmin(np.abs(index["z"] - z))])  # noqa: E731
    n_si, n_ox = at(0.0, t.T_SI / 2), at(0.0, -0.5)
    if n.shape != mode["E"].shape:
        return float("nan"), n_si, n_ox
    energy = n**2 * mode["E"].astype(float) * solvers.cell_areas(mode["y"] * um, mode["z"] * um)
    return float(energy[n > (n_si + n_ox) / 2].sum() / energy.sum()), n_si, n_ox


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mesh", type=float, default=0.02, help="uniform FDE mesh step (um)")
    ap.add_argument("--core-mesh", type=float, default=0.01, help="mesh step on the surfaces of the core (um)")
    a = ap.parse_args()
    require_process_file()
    lumapi = import_lumapi()
    t0 = time.time()
    heat = np.load(HEAT_DIR / "heat.npz")
    names = list(heat["case_name"])
    rise = {  # K per mW of total heater power, from the slopes of step 1
        label: dict(core=float(heat["case_core_K_per_mW"][names.index(label)]),
                    film=float(heat["case_film_K_per_mW"][names.index(label)]))
        for label in ("device", "reference")
    }  # fmt: skip
    dn_dt = silicon_dn_dt()
    strip = np.load(STRIP_MODES)
    f = ISOLATED_FRACTION
    SCRATCH.mkdir(parents=True, exist_ok=True)
    device_gds = section_gds(OUT / "device_section.gds")
    reference_gds = section_gds(OUT / "reference_section.gds", trench_gap=None)
    res: dict = dict(lam=LAM, length_um=LENGTH, isolated_fraction=f, dn_dT_silicon=dn_dt)
    lines = [
        f"MODE (FDE), Lumerical 2025 R1: TE0 at {LAM} um, mesh {a.mesh * 1000:.0f} nm with {a.core_mesh * 1000:.0f} nm on the "
        f"surfaces of the core, window {Y_SPAN} x {Z_SPAN} um with PML; temperature maps of step 1 ({LENGTH:g} um of film)"
    ]

    with lumapi.MODE(hide=True) as m:
        # ---- a. the device and the reference, cold and with the maps of step 1 ----
        setup(m, device_gds, a.mesh, a.core_mesh)
        n_min = 1.46  # a guided mode has an index above the oxide (1.444)
        cold, hot = with_maps(m, {p: temperature_map("device", p) for p in POWERS}, n_min)
        share, n_si, n_ox = silicon_share(m, cold)
        m.switchtolayout()
        m.save(str(OUT / "phase_shift.lms"))
        powers = np.array(POWERS)
        d_dev = np.array([hot[p]["neff"].real - cold["neff"].real for p in POWERS])
        slope_dev = solvers.slope_through_origin(powers, d_dev)  # change of n_eff per mW, fully isolated cross-section
        linearity = float(100 * np.max(np.abs(d_dev / powers - slope_dev)) / slope_dev)
        print(f"device: n_eff {cold['neff'].real:.6f} cold, {d_dev[0]:+.3e} at {POWERS[0]:g} mW, {d_dev[1]:+.3e} at "
              f"{POWERS[1]:g} mW  ({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

        setup(m, reference_gds, a.mesh, a.core_mesh)
        cold_ref, hot_ref = with_maps(m, {POWERS[0]: temperature_map("reference", POWERS[0])}, n_min)
        d_ref = hot_ref[POWERS[0]]["neff"].real - cold_ref["neff"].real
        slope_ref = d_ref / POWERS[0]
        print(f"reference: n_eff {cold_ref['neff'].real:.6f} cold, {d_ref:+.3e} at {POWERS[0]:g} mW  "
              f"({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

        # ---- d. the wall of the trench and the light: the cold mode in a window that holds the wall ----
        wall_rows = []
        setup(m, reference_gds, a.mesh, a.core_mesh, y_span=Y_WALL)
        none = te0(m, n_min)
        for gap in (TRENCH_GAP, *WALL_GAPS):
            gds = device_gds if gap == TRENCH_GAP else section_gds(SCRATCH / f"wall_{gap:g}.gds", trench_gap=gap)
            setup(m, gds, a.mesh, a.core_mesh, y_span=Y_WALL)
            mode = te0(m, n_min)
            wall_rows.append((gap - WIDTH / 2, mode["neff"].real - none["neff"].real, mode["loss_dBcm"] - none["loss_dBcm"]))
            print(f"wall {gap - WIDTH / 2:.2f} um from the core: n_eff {wall_rows[-1][1]:+.2e}, added loss "
                  f"{wall_rows[-1][2]:+.1e} dB/cm  ({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

        # ---- e. the film and the light: the cold mode in a window that holds the film ----
        setup(m, reference_gds, a.mesh, a.core_mesh, z=Z_FILM, trial_modes=12)
        with_film = te0(m, n_min)
        bare_gds = section_gds(SCRATCH / "no_film.gds", trench_gap=None, heater=False)
        setup(m, bare_gds, a.mesh, a.core_mesh, z=Z_FILM, trial_modes=12)
        without_film = te0(m, n_min)
        print(f"film: loss {with_film['loss_dBcm']:.3g} dB/cm with the film, {without_film['loss_dBcm']:.3g} without  "
              f"({time.time() - t0:.0f} s)", flush=True)  # fmt: skip

        # ---- f. checks: a finer mesh (the device), a wider window (the reference) ----
        setup(m, device_gds, a.mesh / 2, a.core_mesh / 2)
        cold_fine, hot_fine = with_maps(m, {POWERS[0]: temperature_map("device", POWERS[0])}, n_min)
        slope_fine = (hot_fine[POWERS[0]]["neff"].real - cold_fine["neff"].real) / POWERS[0]
        setup(m, reference_gds, a.mesh, a.core_mesh, y_span=Y_WALL)
        cold_wide, hot_wide = with_maps(m, {POWERS[0]: temperature_map("reference", POWERS[0])}, n_min)
        slope_wide = (hot_wide[POWERS[0]]["neff"].real - cold_wide["neff"].real) / POWERS[0]
        print(f"checks done  ({time.time() - t0:.0f} s)", flush=True)

    # ---- the numbers ----
    p_pi = lambda slope: LAM / (2 * LENGTH * slope)  # noqa: E731  mW: lambda / (2 L dn_eff/dP), lengths in um
    slope_drawn = f * slope_dev + (1 - f) * slope_ref  # the ends of the film without a trench count as the reference
    dneff_dT = slope_dev / rise["device"]["core"]  # per kelvin of mean core temperature
    dneff_dT_ref = slope_ref / rise["reference"]["core"]
    predicted = float("nan") if np.isnan(share) else cold["ng"] / n_si * share * dn_dt
    rise_drawn = {k: f * rise["device"][k] + (1 - f) * rise["reference"][k] for k in ("core", "film")}
    table = {}
    for label, slope, k in (("device", slope_dev, rise["device"]), ("drawn", slope_drawn, rise_drawn),
                            ("reference", slope_ref, rise["reference"])):  # fmt: skip
        for phase, factor in (("pi", 1.0), ("2pi", 2.0)):
            power = factor * p_pi(slope)
            volts = (power * 1e-3 * HEATER_RESISTANCE) ** 0.5
            table[label, phase] = dict(power=power, core=k["core"] * power, film=k["film"] * power, volts=volts,
                                       mA=volts / HEATER_RESISTANCE * 1e3)  # fmt: skip
    film_loss = with_film["loss_dBcm"] - without_film["loss_dBcm"]  # dB/cm added by the film
    floor = abs(without_film["loss_dBcm"])  # what the solver reports for a lossless guide: its floor

    lines += [
        f"answer: the device as drawn needs {table['drawn', 'pi']['power']:.2f} mW for pi and "
        f"{table['drawn', '2pi']['power']:.2f} mW for 2 pi; without trenches it would need "
        f"{table['reference', 'pi']['power']:.2f} and {table['reference', '2pi']['power']:.2f} mW.  The trenches lower the "
        f"power by a factor {table['reference', 'pi']['power'] / table['drawn', 'pi']['power']:.2f}.",
        "",
        f"a. effective index of TE0 at {LAM} um, cold and with the temperature map of step 1",
        f"{'case':>10} {'P (mW)':>7} {'n_eff':>10} {'change':>11} {'per mW':>11}",
        f"{'device':>10} {0:7.1f} {cold['neff'].real:10.6f}",
        *[
            f"{'device':>10} {p:7.1f} {hot[p]['neff'].real:10.6f} {d:+11.3e} {d / p:11.3e}"
            for p, d in zip(POWERS, d_dev, strict=True)
        ],
        f"{'reference':>10} {0:7.1f} {cold_ref['neff'].real:10.6f}",
        f"{'reference':>10} {POWERS[0]:7.1f} {hot_ref[POWERS[0]]['neff'].real:10.6f} {d_ref:+11.3e} {slope_ref:11.3e}",
        f"device, slope through the origin: {slope_dev:.4e} per mW; the two powers differ from it by {linearity:.3f} %",
        f"P_pi = lambda / (2 L dn_eff/dP), with L = {LENGTH:g} um:",
        f"  fully isolated cross-section: {p_pi(slope_dev):.2f} mW for pi, {2 * p_pi(slope_dev):.2f} mW for 2 pi",
        f"  reference without trenches:   {p_pi(slope_ref):.2f} mW for pi, {2 * p_pi(slope_ref):.2f} mW for 2 pi",
        "  P_pi does not depend on L: a film twice as long needs half the rise for the same phase, and reaches it with the"
        " same power.  What L sets is the temperature (c).",
        "",
        f"change of n_eff per kelvin of mean core temperature: {dneff_dT:.3e} /K (device), {dneff_dT_ref:.3e} /K (reference);"
        f" the silicon of the process file has dn/dT = {dn_dt:.3e} /K",
        f"  the core rises by {rise['device']['core']:.4f} K/mW (device) and {rise['reference']['core']:.4f} K/mW (reference)"
        f" in step 1",
    ]
    if not np.isnan(predicted):
        lines += [
            f"  estimate (n_g / n_Si) x (share of the electric energy in silicon) x dn/dT = ({cold['ng']:.3f} / {n_si:.3f}) x "
            f"{share:.3f} x {dn_dt:.2e} = {predicted:.3e} /K ({100 * (predicted / dneff_dT - 1):+.1f} % against the simulation;"
            " the estimate neglects the dispersion of silicon)",
            f"  {100 * share:.0f} % of the electric energy of the mode is in silicon, and the light is slow (n_g = {cold['ng']:.2f} "
            f"against n_Si = {n_si:.2f}), so it stays longer in the heated silicon.",
            f"  The second effect outweighs the first: the effective index changes {100 * (dneff_dT / dn_dt - 1):.0f} % more per "
            "kelvin than the index of silicon itself.",
        ]
    lines += [
        "",
        f"b. the device as drawn: the trenches run beside {TRENCH_LENGTH:g} of the {LENGTH:g} um of film (f = {f:.2f})",
        f"  dn_eff/dP = f x {slope_dev:.4e} + (1 - f) x {slope_ref:.4e} = {slope_drawn:.4e} per mW",
        f"  P_pi = {p_pi(slope_drawn):.2f} mW, P_2pi = {2 * p_pi(slope_drawn):.2f} mW.  This is the number of the device; it "
        "averages two two-dimensional results along the film and does not solve the ends in three dimensions.",
        "",
        f"c. what the phase asks of the heater (R = {HEATER_RESISTANCE:.0f} ohm for the free film, from the sheet resistance)",
        f"{'case':>10} {'phase':>6} {'P (mW)':>8} {'core rise K':>12} {'film rise K':>12} {'V':>6} {'I (mA)':>7}",
    ]
    for (label, phase), row in table.items():
        lines.append(f"{label:>10} {phase:>6} {row['power']:8.2f} {row['core']:12.1f} {row['film']:12.1f} {row['volts']:6.2f} "
                     f"{row['mA']:7.2f}")  # fmt: skip
    lines += [
        "  rises are means over the core and over the film, above the substrate; 'drawn' is the device, with f of its film "
        "beside trenches",
        "",
        f"d. the wall of the trench and the light: TE0 cold, window {Y_WALL} x {Z_SPAN} um, against the same guide without trenches",
        f"{'wall to core edge (um)':>24} {'change of n_eff':>16} {'added loss dB/cm':>17}",
        *[f"{d:24.2f} {dn:+16.2e} {loss:+17.1e}" for d, dn, loss in wall_rows],
        f"  the device has its wall {TRENCH_GAP - WIDTH / 2:.2f} um from the edge of the core; the rule trench_to_waveguide asks "
        f"for {t.DESIGN_RULES['trench_to_waveguide']:.2f} um",
        "  Air has a lower index than oxide, so a wall cannot make the mode leak: the model has no loss from it at any distance.",
        f"  (In this low window the guide without trenches already reports {none['loss_dBcm']:.2g} dB/cm: the boundary above and "
        "below the core, which stays under the film, absorbs a little of the tail of the mode.  The column is the difference.)",
        "  A real wall is rough and scatters the light that reaches it; the change of n_eff shows how much light reaches it.",
        "",
        f"e. the film and the light: TE0 cold, window {Y_SPAN} um wide from z = {Z_FILM[0]} to {Z_FILM[1]} um",
        f"  with the film {with_film['loss_dBcm']:.3g} dB/cm, without it {without_film['loss_dBcm']:.3g} dB/cm: the film adds "
        f"{film_loss:.3g} dB/cm, {film_loss * LENGTH * 1e-4:.2g} dB over the {LENGTH:g} um of the device",
        f"  the value without the film, {floor:.1g} dB/cm, is what the solver reports for a guide without loss: its floor",
        "",
        "f. checks",
        f"  mesh halved ({a.mesh * 500:.0f} nm, {a.core_mesh * 500:.0f} nm on the core): dn_eff/dP = {slope_fine:.4e} per mW "
        f"({100 * (slope_fine / (d_dev[0] / POWERS[0]) - 1):+.2f} %), cold n_eff {cold_fine['neff'].real:.6f} "
        f"({cold_fine['neff'].real - cold['neff'].real:+.1e})",
        f"  window {Y_WALL} um wide instead of {Y_SPAN} um (reference): dn_eff/dP = {slope_wide:.4e} per mW "
        f"({100 * (slope_wide / slope_ref - 1):+.2f} %), cold n_eff {cold_wide['neff'].real:.6f} "
        f"({cold_wide['neff'].real - cold_ref['neff'].real:+.1e})",
        f"  the strip waveguide chapter has n_eff = {float(strip['neff']):.5f} and n_g = {float(strip['ng']):.4f} for the same "
        f"guide in a {5.0} x {2.4} um window; here {cold_ref['neff'].real:.5f} and {cold_ref['ng']:.4f}",
        "",
        "limits: the temperature is that of a two-dimensional cross-section, so the ends of the film are not solved; the oxide",
        "  has no thermo-optic coefficient in the process file (it is about a twentieth of that of silicon); the phase is that of",
        f"  TE0 at {LAM} um only.",
    ]

    res.update(
        powers_mW=np.array([0.0, *POWERS]),
        device_neff=np.array([cold["neff"].real, *[hot[p]["neff"].real for p in POWERS]]),
        reference_neff=np.array([cold_ref["neff"].real, hot_ref[POWERS[0]]["neff"].real]),
        dneff_dP_isolated=slope_dev,
        dneff_dP_reference=slope_ref,
        dneff_dP_drawn=slope_drawn,
        linearity_pct=linearity,
        dneff_dT_device=dneff_dT,
        dneff_dT_reference=dneff_dT_ref,
        dneff_dT_estimate=predicted,
        silicon_energy_share=share,
        n_si=n_si,
        n_ox=n_ox,
        ng=cold["ng"],
        core_K_per_mW=np.array([rise["device"]["core"], rise_drawn["core"], rise["reference"]["core"]]),
        film_K_per_mW=np.array([rise["device"]["film"], rise_drawn["film"], rise["reference"]["film"]]),
        cases=np.array(["isolated", "drawn", "reference"]),
        P_pi_mW=np.array([table[k, "pi"]["power"] for k in ("device", "drawn", "reference")]),
        P_2pi_mW=np.array([table[k, "2pi"]["power"] for k in ("device", "drawn", "reference")]),
        core_rise_at_pi_K=np.array([table[k, "pi"]["core"] for k in ("device", "drawn", "reference")]),
        film_rise_at_pi_K=np.array([table[k, "pi"]["film"] for k in ("device", "drawn", "reference")]),
        volts_at_pi=np.array([table[k, "pi"]["volts"] for k in ("device", "drawn", "reference")]),
        mA_at_pi=np.array([table[k, "pi"]["mA"] for k in ("device", "drawn", "reference")]),
        resistance_ohm=HEATER_RESISTANCE,
        wall_distance_um=np.array([row[0] for row in wall_rows]),
        wall_dneff=np.array([row[1] for row in wall_rows]),
        wall_loss_dBcm=np.array([row[2] for row in wall_rows]),
        film_loss_dBcm=np.array([with_film["loss_dBcm"], without_film["loss_dBcm"]]),
        mode_E=cold["E"],
        mode_y_um=cold["y"],
        mode_z_um=cold["z"],
        check_mesh_dneff_dP=slope_fine,
        check_window_dneff_dP=slope_wide,
        strip_chapter_neff=float(strip["neff"]),
    )
    np.savez_compressed(OUT / "phase.npz", **res)
    (OUT / "phase.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print("\n".join(lines))
    print(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()

"""Step 2 - INTERCONNECT: program the 4 x 4 mesh to a matrix, and see how well the drawn circuit holds it.

    1. the decomposition of the paper (Clements et al. 2016) gives theta, phi and the output phases of an ideal mesh
    2. the circuit as drawn is not ideal: its couplers split 49.86 : 50.07, its rows carry different fixed phases (a
       row that crosses a column without a block runs straight, the rows of a block run through fans), and its paths
       lose different amounts of light.  A least-squares fit corrects the heater powers for it, from the start of 1.
    3. INTERCONNECT runs the programmed circuit from 1.5 to 1.6 um; the Python model of the same circuit
       (mesh_model.py) is compared with it.

The targets are the 4-point discrete Fourier transform and RANDOM unitary matrices drawn uniformly (Haar measure,
seeded).  The fidelity is |Tr(U_target^H U)|^2 / (N Tr(U^H U)): 1 when the mesh is the target up to a global phase
and a common loss.

    python program_mesh.py

Output in 2_program/:  mesh.icp (the circuit, without results), program.npz, program.txt
"""

from __future__ import annotations

import time

import interconnect as icx
import mesh_model as mm
import numpy as np
from common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, SCRATCH, cm, import_lumapi, inputs, step_dir

OUT = step_dir("2_program")
RANDOM = 40  # random unitaries
SEED = 2016
CHECKED = 3  # random unitaries that INTERCONNECT runs, besides the DFT
LAM_MAX = 1.6
POINTS = 101


BAND_TARGETS = 11  # the DFT and the first random unitaries, for the comparison of the band (model only)


def variant_couplers(ph: mm.Physics, lam: np.ndarray, n_couplers: int, arm_length: float, split: bool, delay: bool):
    """The couplers with one or both of their wavelength effects taken out, at the wavelengths lam: split=False holds
    the split at its value at lam0; delay=False gives the coupler the delay of the dummy arm (a strip as long as its
    path) instead of its own.  Returns None when nothing is taken out (the FDTD coupler)."""
    if split and delay:
        return None
    s, s0 = ph.coupler(lam, (3, 4)), ph.coupler(ph.lam0, (3, 4))
    mag = {k: np.abs(s[k]) if split else np.full(lam.size, abs(s0[k][0])) for k in (3, 4)}
    if delay:
        arg = {k: np.unwrap(np.angle(s[k])) for k in (3, 4)}
    else:
        shift = ph.beta_length(lam, arm_length) - ph.beta_length(ph.lam0, arm_length)
        arg = {k: np.angle(s0[k][0]) + shift for k in (3, 4)}
    t = np.empty((lam.size, 2, 2), dtype=complex)
    t[:, 0, 0] = t[:, 1, 1] = mag[4] * np.exp(1j * arg[4])
    t[:, 0, 1] = t[:, 1, 0] = mag[3] * np.exp(1j * arg[3])
    return {k: t for k in range(n_couplers)}


def band(lam: np.ndarray, f: np.ndarray, level: float) -> tuple[float, float]:
    """The stretch of wavelengths around lam0 where the fidelity stays above level (um), from the samples."""
    i0 = int(np.argmin(np.abs(lam - 1.55)))
    if f[i0] < level:
        return np.nan, np.nan
    lo = i0
    while lo > 0 and f[lo - 1] >= level:
        lo -= 1
    hi = i0
    while hi < len(f) - 1 and f[hi + 1] >= level:
        hi += 1
    return float(lam[lo]), float(lam[hi])


def main() -> None:
    t0 = time.time()
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = mm.circuit(LAYOUT, d["heater_length"])
    rng = np.random.default_rng(SEED)
    targets = [mm.dft(c.n)] + [mm.haar(c.n, rng) for _ in range(RANDOM)]
    names = ["DFT"] + [f"random {k + 1}" for k in range(RANDOM)]

    # ---- 1 and 2: decomposition and fit ----
    results = []
    for name, u in zip(names, targets, strict=False):
        r = mm.program(c, ph, u, ph.lam0, restarts=2)
        results.append(r)
        print(f"  {name:10s} 1 - F = {1 - r['fidelity']:.2e}  {r['powers'].sum():6.1f} mW  ({r['tries']} fits)", flush=True)
    powers = np.array([r["powers"] for r in results])
    f0 = np.array([r["fidelity"] for r in results])
    ideal_error = max(r["ideal_error"] for r in results)

    # what sets the floor of the fidelity at lam0: the same fit without loss, and with lossless couplers too
    lossless = mm.Physics(d, 0.0, COUPLER_PORT_EXTRA)
    s = lossless.coupler(lossless.lam0, (3, 4))
    norm = np.sqrt(abs(s[3][0]) ** 2 + abs(s[4][0]) ** 2)
    clean = {k: (np.array([[s[4][0], s[3][0]], [s[3][0], s[4][0]]]) / norm)[None] for k in range(len(c.couplers))}
    half = {k: (np.exp(1j * np.angle(s[4][0])) * np.array([[1, 1j], [1j, 1]]) / np.sqrt(2))[None] for k in range(len(c.couplers))}
    floor = {}
    for label, phys, cp in (
        ("no propagation loss", lossless, None),
        ("no loss at all", lossless, clean),
        ("lossless 50:50 couplers", lossless, half),
    ):
        f = [mm.program(c, phys, u, phys.lam0, couplers=cp, restarts=0)["fidelity"] for u in targets[:6]]
        floor[label] = float(1 - min(f))

    # ---- 3: INTERCONNECT, and the model over the band ----
    sp = icx.write_sparameters(ph, SCRATCH / "coupler.dat")
    with import_lumapi().INTERCONNECT(hide=True) as ic:
        mesh = icx.Mesh(ic, c, ph, sp, LAM_MAX, POINTS)
        measured = []
        for j in range(1 + CHECKED):
            mesh.set_sites(mm.site_dn(c, ph, powers[j]))
            u, lam = mesh.measure()
            measured.append(u)
            print(f"  INTERCONNECT {names[j]}: F at 1.55 um = {mm.fidelity(u[POINTS // 2], targets[j]):.8f}", flush=True)
        mesh.set_sites(np.zeros(len(c.sites)))
        ic.switchtodesign()
        ic.save(str(OUT / "mesh.icp"))
    measured = np.array(measured)
    i0 = POINTS // 2
    f_ic = np.array([[mm.fidelity(measured[j][i], targets[j]) for i in range(POINTS)] for j in range(1 + CHECKED)])
    model = np.array([mm.transfer(c, ph, lam, mm.site_dn(c, ph, p)) for p in powers])  # (target, lam, out, in)
    f_model = np.array([[mm.fidelity(model[j][i], targets[j]) for i in range(POINTS)] for j in range(len(targets))])
    diff = float(np.max(np.abs(measured - model[: 1 + CHECKED])))
    bands = {level: [band(lam, f, level) for f in f_model] for level in (0.99, 0.999)}
    width = {level: np.array([(b - a) * 1000 for a, b in v]) for level, v in bands.items()}

    # what sets the band: the first draft of the layout, and the couplers with their wavelength effects taken out
    draft = mm.circuit(cm.clements_mesh(match_delay=False).info, d["heater_length"])
    cases = {
        "the drawn mesh": (c, True, True),
        "first draft: straight edge rows": (draft, True, True),
        "split held at 1.55 um": (c, False, True),
        "coupler with the delay of the arm": (c, True, False),
        "both": (c, False, False),
    }
    case_width = {}
    for label, (circ, split, delay) in cases.items():
        w = []
        for j in range(BAND_TARGETS):
            at0 = variant_couplers(ph, np.array([ph.lam0]), len(circ.couplers), LAYOUT["arm_length"], split, delay)
            if label == "the drawn mesh":
                p = powers[j]
            else:
                p = mm.program(circ, ph, targets[j], ph.lam0, couplers=at0, restarts=2)["powers"]
            cp = variant_couplers(ph, lam, len(circ.couplers), LAYOUT["arm_length"], split, delay)
            f = np.array([mm.fidelity(u, targets[j]) for u in mm.transfer(circ, ph, lam, mm.site_dn(circ, ph, p), cp)])
            a, b = band(lam, f, 0.99)
            w.append((b - a) * 1000)
        case_width[label] = np.array(w)
        print(f"  band, {label}: {np.round(w, 0)}", flush=True)
    s_lam = ph.coupler(lam, (4,))[4]
    coupler_delay = float(np.polyfit(1 / lam, np.unwrap(np.angle(s_lam)), 1)[0] / (2 * np.pi * ph.ng))  # um of strip
    draft_lengths = {m: sum(p[2] for p in draft.rows[m] if p[0] == "wg") for m in range(c.n)}

    # ---- the heaters ----
    order = mm.heater_order(c)
    total = powers.sum(axis=1)
    volts = np.sqrt(powers.max() * 1e-3 * d["resistance"])
    dft_theta = results[0]["theta"]
    lengths = {m: sum(p[2] for p in c.rows[m] if p[0] == "wg") for m in range(c.n)}

    lines = [
        "INTERCONNECT, Lumerical 2025 R1, and the Python model of the same circuit (mesh_model.py): the 4 x 4 mesh of",
        f"  devices/clements_mesh_builder.py, {len(c.couplers)} couplers, {len(c.heaters)} heaters, {len(c.sites)} sites under heater positions;",
        f"  P_pi = {ph.P_pi:.2f} mW, propagation loss {LOSS_DB_CM} dB/cm (assumed); analyser {lam[0]:.4f} to {lam[-1]:.4f} um, {POINTS} points;"
        f" run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: the drawn mesh holds the DFT with 1 - F = {1 - f0[0]:.1e} at 1.55 um, and every one of {RANDOM} random unitaries with "
        f"1 - F <= {np.max(1 - f0[1:]):.1e}.  What is left is mostly light lost unevenly along the paths.  The fidelity stays above 0.99 over "
        f"{np.median(width[0.99]):.0f} nm (median of the {len(targets)} targets); the couplers set that width.  The first draft of the "
        f"layout, with straight edge rows, held it over {np.median(case_width['first draft: straight edge rows']):.0f} nm.",
        "",
        "a. the decomposition of the paper, for an ideal mesh",
        f"  largest difference between the ideal mesh with these phases and its target, over all {len(targets)} targets: {ideal_error:.1e}",
        "  DFT:  theta / pi = "
        + " ".join(f"{v / np.pi:.3f}" for v in dft_theta)
        + "   phi / pi = "
        + " ".join(f"{v / np.pi:.3f}" for v in results[0]["phi"])
        + "   outputs / pi = "
        + " ".join(f"{v / np.pi:.3f}" for v in results[0]["delta"]),
        "",
        "b. the drawn circuit, fitted from the decomposition, at 1.55 um",
        f"  1 - F: DFT {1 - f0[0]:.2e}; random median {np.median(1 - f0[1:]):.2e}, largest {np.max(1 - f0[1:]):.2e}",
        f"  the worst of 6 targets: without propagation loss {floor['no propagation loss']:.1e}; with lossless couplers too "
        f"{floor['no loss at all']:.1e}; with lossless couplers of exactly 50:50, {floor['lossless 50:50 couplers']:.1e}.",
        "  The split of the couplers (49.90 : 50.10 of what passes) leaves a little that the phases cannot take up.  The larger",
        "  part comes from loss that differs between paths:",
        "  the paths cross different numbers of couplers (each loses 0.003 dB) and of fan bends (each 2.8 um longer than its",
        "  run along x).  The waveguide of the rows, with the arms of the dummy paths: "
        + ", ".join(f"row {m} {v:.0f} um" for m, v in lengths.items())
        + " (and 4 couplers on rows 0 and 3, 8 on rows 1 and 2).",
        "",
        "c. the heaters",
        "  DFT, mW:  " + "  ".join(f"{c.heaters[j]['name']} {powers[0][j]:.2f}" for j in range(len(c.heaters))),
        f"  total heater power: DFT {total[0]:.1f} mW; random mean {total[1:].mean():.1f} mW, from {total[1:].min():.1f} to "
        f"{total[1:].max():.1f} mW; the largest single heater {powers.max():.2f} mW ({volts:.2f} V on {d['resistance']:.0f} ohm)",
        f"  every heater is set in [0, 2 P_pi) = [0, {2 * ph.P_pi:.2f}) mW.",
        "",
        "d. INTERCONNECT against the model",
        "  target      F at 1.55 um, INTERCONNECT   model",
    ]
    for j in range(1 + CHECKED):
        lines.append(f"  {names[j]:10s} {f_ic[j][i0]:24.8f}  {f_model[j][i0]:.8f}")
    lines += [
        f"  largest difference of an entry over the band: {diff:.1e}: the reflections of the couplers, which only INTERCONNECT has",
        "",
        "e. the band (model; the analyser grid is 1 nm)",
        "  target      F > 0.99 from - to (nm)   width   F > 0.999 width   F at 1.53 um   F at 1.57 um",
    ]
    j53, j57 = int(np.argmin(np.abs(lam - 1.53))), int(np.argmin(np.abs(lam - 1.57)))
    for j in range(min(len(targets), 8)):
        a, b = bands[0.99][j]
        lines.append(f"  {names[j]:10s} {a * 1000:7.0f} - {b * 1000:7.0f}  {width[0.99][j]:12.0f}  {width[0.999][j]:15.0f}  "
                     f"{f_model[j][j53]:12.4f}  {f_model[j][j57]:12.4f}")  # fmt: skip
    lines += [
        f"  all {len(targets)} targets, width with F > 0.99: median {np.median(width[0.99]):.0f} nm, from {width[0.99].min():.0f} to {width[0.99].max():.0f} nm",
        "",
        f"f. what sets the band: the width with F > 0.99 (nm) for the DFT and {BAND_TARGETS - 1} random unitaries, each case programmed anew",
        "  case                                 DFT   random: median   from - to",
    ]
    for label, w in case_width.items():
        lines.append(f"  {label:34s} {w[0]:5.0f}  {np.median(w[1:]):15.0f}  {w[1:].min():5.0f} - {w[1:].max():.0f}")
    lines += [
        "  The first draft ran the edge rows straight through the columns without a block: rows 0 and 3 had "
        f"{draft_lengths[0]:.0f} um of waveguide and 4 couplers,",
        f"  rows 1 and 2 {draft_lengths[1]:.0f} um and 8 couplers.  The light that meets again in a later block then arrives",
        "  with a phase that runs away with the wavelength.  The drawn mesh gives those rows the same fans and one arm of a",
        "  coupler.  What is left is the coupler itself: its split changes with the wavelength (step 1), and its delay is that",
        f"  of {coupler_delay:.2f} um of strip, against {LAYOUT['arm_length']:.2f} um for the arm (the light in the coupled section has a lower",
        "  group index).  A path that spans the coupler's 35 um cannot be shorter than 35 um, so the arm cannot match it.",
        "  Without both effects the band is the whole range of the analyser.",
    ]
    text = "\n".join(lines)
    print(text)
    (OUT / "program.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "program.npz", names=np.array(names), targets=np.array(targets), powers_mW=powers, fidelity_lam0=f0,
        lam=lam, fidelity_model=f_model, fidelity_interconnect=f_ic, band_cases=np.array(list(case_width)),
        band_case_width_nm=np.array(list(case_width.values())), coupler_delay_um=coupler_delay,
        arm_length_um=LAYOUT["arm_length"],
        U_interconnect=measured, U_model_dft=model[0], heater_names=np.array([h["name"] for h in c.heaters]),
        heater_kind=np.array([h["kind"] for h in c.heaters]), heater_row=np.array([h["row"] for h in c.heaters]),
        heater_x=np.array([h["x"] for h in c.heaters]), theta_dft=dft_theta, phi_dft=results[0]["phi"],
        delta_dft=results[0]["delta"], P_pi_mW=ph.P_pi, width99_nm=width[0.99], width999_nm=width[0.999],
        floor_no_propagation_loss=floor["no propagation loss"],
        floor_no_loss=floor["no loss at all"], floor_half=floor["lossless 50:50 couplers"], ideal_error=ideal_error,
        model_difference=diff,
        order_theta=order["theta"], order_phi=order["phi"], order_out=order["out"],
    )  # fmt: skip


if __name__ == "__main__":
    main()

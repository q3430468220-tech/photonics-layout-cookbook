"""Step 3 - INTERCONNECT: the heat that every heater gives its neighbours, what it does to the matrix, and its calibration.

A heater warms its own waveguide by 3.79 K per mW (the phase shifter chapter, steps 1 and 2).  Its heat also passes
into the substrate, spreads there and warms every other waveguide of the mesh a little.  The trenches stop the path
through the oxide; they cannot stop the path through the substrate.  Step 4 of the phase shifter chapter estimated
that path for a wafer 725 um thick; mesh_model.crosstalk_matrix applies the same estimate to every heater and every
site of the drawn mesh, with the true positions of both (it reproduces the four values of that chapter exactly).

The estimate, not a simulation, is the weak part of this step: it is a formula for a point source on a thick wafer
with a perfect heat sink below, checked in that chapter against a two-dimensional HEAT run of a thin substrate only.

    1. the powers of step 2 with the heat of the neighbours added           -> how much the matrix suffers
    2. calibration A: solve a linear system so that every heated waveguide gets its intended phase
    3. calibration B: fit the powers with the heat of all neighbours in the model, as step 2 does without it
    4. INTERCONNECT runs the DFT in the three cases

    python thermal_crosstalk.py

Output in 3_crosstalk/:  crosstalk.npz, crosstalk.txt
"""

from __future__ import annotations

import time

import interconnect as icx
import mesh_model as mm
import numpy as np
from common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, ROOT, SCRATCH, import_lumapi, inputs, step_dir

OUT = step_dir("3_crosstalk")
LAM_MAX = 1.6
POINTS = 101


def calibrate_linear(own_share: np.ndarray, wanted: np.ndarray, two_pi: float) -> np.ndarray:
    """Powers P with own_share @ P = wanted on the heated waveguides.  A power that comes out negative is asked for
    one turn of phase (2 P_pi) more on its own waveguide, which is the same phase, and the system is solved again."""
    target = wanted.copy()
    for _ in range(len(target) + 1):
        p = np.linalg.solve(own_share, target)
        if (p >= -1e-12).all():
            return np.maximum(p, 0.0)
        target[p < 0] += two_pi
    raise RuntimeError("no calibration with powers of one sign")


def main() -> None:
    t0 = time.time()
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = mm.circuit(LAYOUT, d["heater_length"])
    program = np.load(ROOT / "2_program" / "program.npz")
    targets, nominal, names = program["targets"], program["powers_mW"], list(program["names"])
    rise, share = mm.crosstalk_matrix(c, d["heater_length"], d["k_silicon"], d["wafer_um"], d["core_K_per_mW"])
    own = mm.own_sites(c)
    own_share = share[own]  # (heater site, heater)
    other = share.copy()
    other[own, np.arange(len(c.heaters))] = 0.0

    def fid(p, crosstalk, j):
        return mm.fidelity(mm.transfer(c, ph, ph.lam0, mm.site_dn(c, ph, p, crosstalk))[0], targets[j])

    naive, lin, fit = [], [], []
    p_lin, p_fit = [], []
    for j, u in enumerate(targets):
        a = calibrate_linear(own_share, nominal[j], 2 * ph.P_pi)
        # the fit, from three starts: the powers as programmed, the linear calibration, and the decomposition
        tries = [mm.fit_powers(c, ph, u, start, ph.lam0, crosstalk=share) for start in (nominal[j], a)]
        tries.append(mm.program(c, ph, u, ph.lam0, crosstalk=share, restarts=1)["powers"])
        b = max(tries, key=lambda p: fid(p, share, j))
        naive.append(fid(nominal[j], share, j))
        lin.append(fid(a, share, j))
        fit.append(fid(b, share, j))
        p_lin.append(a)
        p_fit.append(b)
        print(
            f"  {names[j]:10s} 1 - F: as programmed {1 - naive[-1]:.1e}, linear {1 - lin[-1]:.1e}, fitted {1 - fit[-1]:.1e}",
            flush=True,
        )
    naive, lin, fit = map(np.array, (naive, lin, fit))
    p_lin, p_fit = np.array(p_lin), np.array(p_fit)
    without = np.array([fid(nominal[j], None, j) for j in range(len(targets))])

    sp = icx.write_sparameters(ph, SCRATCH / "coupler.dat")
    ic_f = {}
    with import_lumapi().INTERCONNECT(hide=True) as ic:
        mesh = icx.Mesh(ic, c, ph, sp, LAM_MAX, POINTS)
        for label, p in (("as programmed", nominal[0]), ("linear", p_lin[0]), ("fitted", p_fit[0])):
            mesh.set_sites(mm.site_dn(c, ph, p, share))
            u, _lam = mesh.measure()
            ic_f[label] = float(mm.fidelity(u[POINTS // 2], targets[0]))
            print(f"  INTERCONNECT DFT {label}: F = {ic_f[label]:.8f}", flush=True)

    # the temperatures: what the neighbours add to a waveguide, at the powers of the DFT
    extra_K = other @ nominal[0] * d["core_K_per_mW"]  # K on every site, from the other heaters
    worst_site = int(np.argmax(other.max(axis=1)))
    worst_heater = int(np.argmax(other[worst_site]))
    lines = [
        "INTERCONNECT, Lumerical 2025 R1, and the Python model: the 4 x 4 mesh with the heat that every heater gives every site",
        f"  the substrate path estimated as in the phase shifter chapter, step 4c: k = {d['k_silicon']:.1f} W/m/K, wafer {d['wafer_um']:.0f} um,",
        f"  heaters {d['heater_length']:.0f} um long, own rise {d['core_K_per_mW']:.3f} K/mW; run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: the heat of the neighbours lowers the fidelity of the DFT to 1 - F = {1 - naive[0]:.1e} and of the random "
        f"unitaries to a median of {np.median(1 - naive[1:]):.1e}.  A linear calibration of the heated waveguides brings the "
        f"median to {np.median(1 - lin[1:]):.1e}: worse, because it undoes the heat that both arms of a block share.  A fit "
        f"with every warmed waveguide in the model brings the median back to {np.median(1 - fit):.1e} (largest "
        f"{np.max(1 - fit):.1e}); without the heat it is {np.median(1 - without):.1e}.",
        "",
        "a. the shares: the rise of a waveguide per mW of another heater, over the rise of that heater's own waveguide",
        f"  largest: {100 * other.max():.2f} %: {c.heaters[worst_heater]['name']} on the waveguide {abs(c.sites[worst_site]['row'] - c.heaters[worst_heater]['row']) * LAYOUT['pitch']:.0f} um "
        f"beside it (row {c.sites[worst_site]['row']}, same x)",
        f"  summed over all heaters, for the site that collects most: {100 * other.sum(axis=1).max():.2f} %",
        "  heater   own row  nearest waveguide that it warms (share)",
    ]
    for j, h in enumerate(c.heaters):
        s = int(np.argmax(other[:, j]))
        lines.append(
            f"  {h['name']:7s} {h['row']:7d}  row {c.sites[s]['row']} at x = {c.sites[s]['x']:.0f} um ({100 * other[s, j]:.3f} %)"
        )
    lines += [
        f"  at the powers of the DFT ({nominal[0].sum():.1f} mW in all) the neighbours warm a waveguide by up to {extra_K.max():.2f} K "
        f"({extra_K.max() * d['dneff_dT'] * 2 * np.pi * d['heater_length'] / ph.lam0:.3f} rad over the 100 um of a site).",
        "",
        "b. the fidelity at 1.55 um",
        "  target      without the heat   as programmed   linear calibration   fitted",
    ]
    for j in range(min(8, len(targets))):
        lines.append(f"  {names[j]:10s} {1 - without[j]:16.1e}  {1 - naive[j]:14.1e}  {1 - lin[j]:19.1e}  {1 - fit[j]:7.1e}")
    lines += [
        f"  all {len(targets)} targets, 1 - F, median (largest): without the heat {np.median(1 - without):.1e} ({np.max(1 - without):.1e}); "
        f"as programmed {np.median(1 - naive):.1e} ({np.max(1 - naive):.1e}); linear {np.median(1 - lin):.1e} ({np.max(1 - lin):.1e}); "
        f"fitted {np.median(1 - fit):.1e} ({np.max(1 - fit):.1e})",
        "  The linear calibration sets the phase of the 16 heated waveguides.  It leaves the 24 sites without a heater warm.",
        "  A heater warms both arms of a block beside it by about as much, and what both arms gain cancels in the block: the",
        "  heat as programmed does less harm than its size suggests.  The linear calibration takes the heat out of the heated",
        "  arm only, and so leaves the difference.  The fit puts every site into the model and moves every heater a little.",
        "",
        "c. the power: DFT "
        + f"{nominal[0].sum():.2f} mW as programmed, {p_lin[0].sum():.2f} mW linear, {p_fit[0].sum():.2f} mW fitted; "
        f"random, mean change by the fit {np.mean(p_fit[1:].sum(1) - nominal[1:].sum(1)):+.2f} mW",
        "  heaters that the fit leaves at the bottom of their range (below 0.05 mW), where they would need less than no power: "
        + (
            ", ".join(
                f"{names[j]}: {c.heaters[k]['name']} ({nominal[j][k]:.2f} mW as programmed)"
                for j in range(len(targets))
                for k in np.flatnonzero(p_fit[j] < 0.05)
            )
            or "none"
        ),
        "",
        "d. INTERCONNECT, DFT at 1.55 um: "
        + ", ".join(f"{k} F = {v:.8f}" for k, v in ic_f.items())
        + f"; the model: {naive[0]:.8f}, {lin[0]:.8f}, {fit[0]:.8f}",
        "",
        "limits: the substrate path is the estimate of a formula (a point source on a wafer with a perfect heat sink below), not a",
        "  three-dimensional simulation; the carrier below the chip and the metal of the pads are not in it.  The path through",
        "  the oxide is left out: beyond the trenches the phase shifter chapter found 0.02 % at 10 um, with a thin substrate.",
    ]
    text = "\n".join(lines)
    print(text)
    (OUT / "crosstalk.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "crosstalk.npz", rise_K_per_mW=rise, share=share, own_site=own, site_row=np.array([s["row"] for s in c.sites]),
        site_x=np.array([s["x"] for s in c.sites]), heater_names=np.array([h["name"] for h in c.heaters]),
        heater_row=np.array([h["row"] for h in c.heaters]), heater_x=np.array([h["x"] for h in c.heaters]),
        names=np.array(names), fidelity_without=without, fidelity_naive=naive, fidelity_linear=lin, fidelity_fitted=fit,
        powers_nominal=nominal, powers_linear=p_lin, powers_fitted=p_fit, ic_dft=np.array([ic_f[k] for k in ("as programmed", "linear", "fitted")]),
        extra_K_dft=extra_K, own_rise_K_per_mW=d["core_K_per_mW"],
    )  # fmt: skip


if __name__ == "__main__":
    main()

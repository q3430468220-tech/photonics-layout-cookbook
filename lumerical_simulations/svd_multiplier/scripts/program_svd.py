"""Step 2 - INTERCONNECT and Python: a real matrix, programmed into the multiplier as drawn.

Every target is a real 4 x 4 matrix M.  The recipe of svd_model.py scales it by its largest singular value, splits it
by the SVD, sets mesh V to V^T and mesh U to U by the decomposition of Clements et al. and each attenuator to its
singular value; the fit then corrects all 36 heater powers for the circuit as drawn.

    1. twelve random matrices (entries drawn from a normal distribution, fixed seed), and one with singular values
       1, 0.3, 0.03 and 0.001: the last is below what an attenuator can set (step 1)
    2. the recipe alone, the two meshes fitted alone (the start), and the fit of the whole, in the Python model, at
       1.55 um                                                             -> how close the drawn multiplier comes
    3. INTERCONNECT, the first random matrix and the ill-conditioned one, over the band -> the check, and the band

The fidelity of a matrix that is not unitary is the square of the cosine between it and the target (svd_model.py);
the relative error |T - a M| / |a M| says the same in words that a reader of a number can use.

    python program_svd.py

Output in 2_program/:  multiplier.icp (the circuit, without results), program.npz, program.txt
"""

from __future__ import annotations

import time

import numpy as np
import svd_interconnect as sx
import svd_model as sm
from svd_common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, SCRATCH, import_lumapi, inputs, step_dir

mm = sm.mm
OUT = step_dir("2_program")
LAM_MAX = 1.6
POINTS = 101
SEED = 7
RANDOM = 12
ILL_SIGMA = np.array([1.0, 0.3, 0.03, 0.001])  # singular values of the ill-conditioned target
CHECKED = (0, RANDOM)  # the targets that INTERCONNECT runs: the first random one and the ill-conditioned one


def targets() -> tuple[list[str], np.ndarray]:
    rng = np.random.default_rng(SEED)
    names = [f"random {k + 1}" for k in range(RANDOM)]
    out = [rng.standard_normal((4, 4)) for _ in range(RANDOM)]
    q1, _ = np.linalg.qr(rng.standard_normal((4, 4)))
    q2, _ = np.linalg.qr(rng.standard_normal((4, 4)))
    out.append(q1 @ np.diag(ILL_SIGMA) @ q2.T)
    names.append("ill-conditioned")
    return names, np.array(out)


def band(lam: np.ndarray, err: np.ndarray, level: float, lam0: float) -> tuple[float, float]:
    """The width (nm) of the band around lam0 where the error stays below level, and its two ends."""
    i0 = int(np.argmin(np.abs(lam - lam0)))
    if err[i0] > level:
        return 0.0, 0.0
    lo = hi = i0
    while lo > 0 and err[lo - 1] <= level:
        lo -= 1
    while hi < len(lam) - 1 and err[hi + 1] <= level:
        hi += 1
    return float(lam[lo]), float(lam[hi])


def main() -> None:
    t0 = time.time()
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = sm.circuit(LAYOUT, d["heater_length"])
    names, ms = targets()

    # ---- 1, 2. the recipe and the fit, in the model ----
    runs = []
    for name, m in zip(names, ms, strict=True):
        t1 = time.time()
        r = sm.program(c, ph, m, ph.lam0)
        runs.append(r)
        print(f"  {name}: recipe 1 - F {1 - r['fidelity_recipe']:.2e}, fitted 1 - F {1 - r['fidelity']:.2e}, error {r['error']:.2e}, "
              f"{r['powers'].sum():.0f} mW, {time.time() - t1:.0f} s", flush=True)  # fmt: skip

    # ---- 3. INTERCONNECT over the band, and the model over the same wavelengths ----
    sp = sx.write_sparameters(ph, SCRATCH / "coupler.dat")
    lumapi = import_lumapi()
    measured = {}
    with lumapi.INTERCONNECT(hide=True) as ic:
        circuit = sx.Multiplier(ic, c, ph, sp, LAM_MAX, POINTS)
        for k in CHECKED:
            circuit.set_sites(mm.site_dn(c, ph, runs[k]["powers"]))
            t, lam = circuit.measure(range(4))
            measured[k] = t  # (lam, out of all 8 rows, in)
            print(f"  INTERCONNECT, {names[k]}: done", flush=True)
        circuit.set_sites(mm.site_dn(c, ph, np.zeros(len(c.heaters))))
        ic.switchtodesign()
        ic.save(str(OUT / "multiplier.icp"))
    i0 = POINTS // 2
    if abs(lam[i0] - ph.lam0) > 1e-9:
        raise RuntimeError(f"the middle sample is at {lam[i0]} um, not at {ph.lam0} um")
    checks = {}
    for k in CHECKED:
        target = runs[k]["target"]
        t_ic = measured[k][:, :4, :]
        t_model = sm.matrix(c, ph, lam, runs[k]["powers"])
        err_ic = np.array([sm.relative_error(t_ic[j], target) for j in range(len(lam))])
        err_model = np.array([sm.relative_error(t_model[j], target) for j in range(len(lam))])
        fid_ic = np.array([sm.fidelity(t_ic[j], target) for j in range(len(lam))])
        fid_model = np.array([sm.fidelity(t_model[j], target) for j in range(len(lam))])
        lo, hi = band(lam, 1 - fid_ic, 0.01, ph.lam0)  # F > 0.99, as in the chapter of the mesh
        # the light that each input loses in the dumps, at 1.55 um: the price of a matrix that is not unitary
        to_dumps = np.sum(np.abs(measured[k][i0, 4:, :]) ** 2, axis=0)
        checks[k] = {"t_ic": t_ic, "t_model": t_model, "err_ic": err_ic, "err_model": err_model, "band": (lo, hi),
                     "fid_ic": fid_ic, "fid_model": fid_model,
                     "difference": float(np.max(np.abs(t_ic - t_model))), "to_dumps": to_dumps,
                     "error_ic_1550": float(err_ic[i0]), "fidelity_ic_1550": sm.fidelity(t_ic[i0], target)}  # fmt: skip

    f_fit = np.array([r["fidelity"] for r in runs])
    e_fit = np.array([r["error"] for r in runs])
    e_rec = np.array([r["error_recipe"] for r in runs])
    e_start = np.array([r["error_start"] for r in runs])
    power = np.array([r["powers"].sum() for r in runs])
    rnd = slice(0, RANDOM)
    lines = [
        "INTERCONNECT, Lumerical 2025 R1, and the Python model of the same circuit (svd_model.py): the 4 x 4 real matrix multiplier",
        f"  of devices/svd_multiplier_builder.py, two meshes and four attenuators, {len(c.couplers)} couplers and {len(c.heaters)} heaters;",
        f"  P_pi = {ph.P_pi:.2f} mW, propagation loss {LOSS_DB_CM} dB/cm (assumed); analyser {lam[0]:.4f} to {lam[-1]:.4f} um, {POINTS} points;",
        f"  run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: the drawn multiplier holds every random matrix to a relative error of {e_fit[rnd].max():.1e} or less at 1.55 um, "
        f"after the fit; the recipe alone misses by {np.median(e_rec[rnd]):.2f} (median), because it knows nothing of the "
        f"phase of the waveguides, and the two meshes fitted alone come to {np.median(e_start[rnd]):.1e}.  F stays above "
        f"0.99 over {1000 * (checks[0]['band'][1] - checks[0]['band'][0]):.0f} nm for the first random matrix.  The "
        f"ill-conditioned matrix, whose smallest singular value is below what an attenuator can set, stops at {e_fit[RANDOM]:.1e}.",
        "",
        "a. the recipe, the meshes fitted alone, and the fit of the whole, at 1.55 um, the Python model",
        "  target            recipe: 1 - F   error    meshes alone: error   fitted: 1 - F   error     heaters (mW)  singular values of M / s",
    ]
    for name, r, p in zip(names, runs, power, strict=True):
        lines.append(
            f"  {name:16s}  {1 - r['fidelity_recipe']:13.2e}  {r['error_recipe']:6.3f}  {r['error_start']:19.2e}  {1 - r['fidelity']:14.2e}  "
            f"{r['error']:8.2e}  {p:12.0f}  {' '.join(f'{s:.3f}' for s in r['sigma'])}"
        )
    lines += [
        f"  random: fitted error median {np.median(e_fit[rnd]):.1e}, largest {e_fit[rnd].max():.1e}; heater power {power[rnd].min():.0f} to "
        f"{power[rnd].max():.0f} mW, mean {power[rnd].mean():.0f} mW (36 heaters, each in [0, 2 P_pi))",
        "",
        "b. INTERCONNECT against the model, over the band",
        "  target            error at 1.55 um   1 - F at 1.55 um   band with F > 0.99      largest difference of an entry   light lost in the dumps, per input",
    ]
    for k in CHECKED:
        ch = checks[k]
        lo, hi = ch["band"]
        lines.append(
            f"  {names[k]:16s}  {ch['error_ic_1550']:16.2e}  {1 - ch['fidelity_ic_1550']:16.2e}  {1000 * (hi - lo):9.0f} nm ({lo * 1000:.0f} to {hi * 1000:.0f})"
            f"  {ch['difference']:29.1e}   {' '.join(f'{x:.3f}' for x in ch['to_dumps'])}"
        )
    lines += [
        "  (the difference of an entry is the reflection of the couplers, which only INTERCONNECT includes)",
        "",
        "c. against the wavelength, INTERCONNECT: the relative error, and 1 - F",
        "  lambda (um)  " + "  ".join(f"{names[k]:>16s}  {'1 - F':>9s}" for k in CHECKED),
    ]
    for j in range(0, POINTS, 10):
        lines.append(
            f"  {lam[j]:11.4f}  "
            + "  ".join(f"{checks[k]['err_ic'][j]:16.3e}  {1 - checks[k]['fid_ic'][j]:9.2e}" for k in CHECKED)
        )
    text = "\n".join(lines)
    print(text)
    (OUT / "program.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "program.npz", names=np.array(names), targets=ms, scale=np.array([r["scale"] for r in runs]),
        sigma=np.array([r["sigma"] for r in runs]), powers_mW=np.array([r["powers"] for r in runs]),
        powers_recipe_mW=np.array([r["powers_recipe"] for r in runs]), fidelity=f_fit, error=e_fit,
        fidelity_recipe=np.array([r["fidelity_recipe"] for r in runs]), error_recipe=e_rec, error_start=e_start, lam=lam,
        checked=np.array(CHECKED), T_interconnect=np.array([checks[k]["t_ic"] for k in CHECKED]),
        T_model=np.array([checks[k]["t_model"] for k in CHECKED]), error_ic=np.array([checks[k]["err_ic"] for k in CHECKED]),
        error_model=np.array([checks[k]["err_model"] for k in CHECKED]),
        fidelity_ic=np.array([checks[k]["fid_ic"] for k in CHECKED]), fidelity_model=np.array([checks[k]["fid_model"] for k in CHECKED]), band_um=np.array([checks[k]["band"] for k in CHECKED]),
        to_dumps=np.array([checks[k]["to_dumps"] for k in CHECKED]), model_difference=max(ch["difference"] for ch in checks.values()),
        heater_names=np.array([h["name"] for h in c.heaters]), P_pi_mW=ph.P_pi,
    )  # fmt: skip


if __name__ == "__main__":
    main()

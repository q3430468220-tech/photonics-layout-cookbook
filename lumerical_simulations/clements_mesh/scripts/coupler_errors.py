"""Step 4 - INTERCONNECT: couplers that do not split 50:50, as a fabrication error of the gap makes them, and whether
the phases can make up for it.

A coupler's split comes from the coupling along it: the cross power is sin^2(psi), with psi = pi/2 (L + L_bends)/L_pi.
The coupling length grows exponentially with the gap (directional coupler chapter, step 1):
L_pi = l0 exp(gap / decay), with decay = 115.7 nm.  A gap that comes out wider by dg therefore scales psi by
exp(-dg / decay), at every wavelength.  The model keeps the FDTD coupler and changes only its split: psi(lam) is taken
from the FDTD cross power at each wavelength and scaled; the phases and the loss stay those of the FDTD run.

    1. every coupler off by the same dg (a wafer whose gaps all came out wider or narrower)
    2. every coupler off by its own random dg, drawn from a normal distribution of width sigma
    in both: the matrix with the powers of the error-free mesh (as programmed), and with powers fitted to the mesh
    as it came out (as calibrated: the errors are known, for example from a measurement of each block)
    3. INTERCONNECT runs one mesh of 2 with a coupler file each

The question is the one of D. A. B. Miller, "Perfect optics with imperfect components" (Optica 2, 747, 2015) for a
Clements mesh: with identical couplers of cross power f, a block passes at most 4 f (1 - f) across, so a matrix that
needs a block near full crossing cannot be set exactly; a mesh with errors still realises most matrices once its
phases are fitted.

    python coupler_errors.py

Output in 4_coupler_errors/:  errors.npz, errors.txt
"""

from __future__ import annotations

import math
import time

import interconnect as icx
import mesh_model as mm
import numpy as np
from common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, ROOT, SCRATCH, import_lumapi, inputs, step_dir

OUT = step_dir("4_coupler_errors")
SHIFTS_NM = np.array([-20.0, -15.0, -10.0, -5.0, 0.0, 5.0, 10.0, 15.0, 20.0])  # the same error on every coupler
SIGMAS_NM = np.array([2.5, 5.0, 10.0, 20.0])  # random errors
SAMPLES = 30
COMMON_TARGETS = 11  # the DFT and the first random unitaries of step 2
SEED = 1460
LAM_MAX = 1.6
POINTS = 101
CHECK_SIGMA = 10.0


def split_model(d: dict, ph: mm.Physics):
    """A function of the gap errors (nm, one per coupler) and the wavelengths: the coupler matrices {id: (lam, 2, 2)}
    and the S31, S41 that INTERCONNECT reads."""
    modes = np.load(ROOT.parent / "directional_coupler" / "1_supermodes" / "supermodes.npz")
    decay_um = float(modes["fit_decay_nm"]) / 1000

    def make(errors_nm, lam):
        lam = np.atleast_1d(np.asarray(lam, dtype=float))
        s = ph.coupler(lam, (3, 4))
        through = np.abs(s[3]) ** 2 + np.abs(s[4]) ** 2  # what passes, with the FDTD loss
        psi = np.arcsin(np.sqrt(np.abs(s[3]) ** 2 / through))
        out, files = {}, {}
        for k, dg in enumerate(np.atleast_1d(errors_nm)):
            p = psi * math.exp(-dg / 1000 / decay_um)
            s3 = np.sqrt(through) * np.sin(p) * np.exp(1j * np.angle(s[3]))
            s4 = np.sqrt(through) * np.cos(p) * np.exp(1j * np.angle(s[4]))
            t = np.empty((lam.size, 2, 2), dtype=complex)
            t[:, 0, 0] = t[:, 1, 1] = s4
            t[:, 0, 1] = t[:, 1, 0] = s3
            out[k] = t
            files[k] = {3: s3, 4: s4}
        return out, files

    return make, decay_um


def main() -> None:
    t0 = time.time()
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = mm.circuit(LAYOUT, d["heater_length"])
    K = len(c.couplers)
    make, decay_um = split_model(d, ph)
    program = np.load(ROOT / "2_program" / "program.npz")
    targets, nominal = program["targets"], program["powers_mW"]
    lam0 = np.array([ph.lam0])
    s0 = ph.coupler(lam0, (3, 4))
    f0 = float(abs(s0[3][0]) ** 2 / (abs(s0[3][0]) ** 2 + abs(s0[4][0]) ** 2))

    def fid(p, cp, u):
        return mm.fidelity(mm.transfer(c, ph, lam0, mm.site_dn(c, ph, p), cp)[0], u)

    # ---- 1. the same error on every coupler ----
    shift_split, shift_nominal, shift_fitted = [], [], []
    for dg in SHIFTS_NM:
        cp, _ = make(np.full(K, dg), lam0)
        shift_split.append(float(abs(cp[0][0, 0, 1]) ** 2 / (abs(cp[0][0, 0, 1]) ** 2 + abs(cp[0][0, 0, 0]) ** 2)))
        a, b = [], []
        for j in range(COMMON_TARGETS):
            a.append(fid(nominal[j], cp, targets[j]))
            b.append(mm.program(c, ph, targets[j], ph.lam0, couplers=cp, restarts=2)["fidelity"])
        shift_nominal.append(a)
        shift_fitted.append(b)
        print(f"  all gaps {dg:+5.1f} nm: split {shift_split[-1]:.4f}; 1 - F as programmed {np.median(1 - np.array(a)):.1e}, "
              f"fitted {np.median(1 - np.array(b)):.1e} (medians)", flush=True)  # fmt: skip
    shift_nominal, shift_fitted = np.array(shift_nominal), np.array(shift_fitted)

    # ---- 2. random errors ----
    rng = np.random.default_rng(SEED)
    rand_nominal, rand_fitted, rand_errors, rand_targets = [], [], [], []
    for sigma in SIGMAS_NM:
        a, b, e, u_all = [], [], [], []
        for _ in range(SAMPLES):
            errors = rng.normal(0.0, sigma, K)
            u = mm.haar(c.n, rng)
            p_nom = mm.program(c, ph, u, ph.lam0, restarts=1)["powers"]
            cp, _ = make(errors, lam0)
            a.append(fid(p_nom, cp, u))
            b.append(mm.program(c, ph, u, ph.lam0, couplers=cp, restarts=2)["fidelity"])
            e.append(errors)
            u_all.append(u)
        rand_nominal.append(a)
        rand_fitted.append(b)
        rand_errors.append(e)
        rand_targets.append(u_all)
        print(f"  sigma {sigma:4.1f} nm: 1 - F as programmed median {np.median(1 - np.array(a)):.1e}, fitted median "
              f"{np.median(1 - np.array(b)):.1e}, fitted worst {np.max(1 - np.array(b)):.1e}", flush=True)  # fmt: skip
    rand_nominal, rand_fitted = np.array(rand_nominal), np.array(rand_fitted)
    rand_errors, rand_targets = np.array(rand_errors), np.array(rand_targets)

    # ---- 3. INTERCONNECT: the first sample of sigma = CHECK_SIGMA ----
    i_sigma = int(np.argmin(np.abs(SIGMAS_NM - CHECK_SIGMA)))
    errors, u = rand_errors[i_sigma][0], rand_targets[i_sigma][0]
    p_nom = mm.program(c, ph, u, ph.lam0, restarts=1)["powers"]
    cp0, _ = make(errors, lam0)
    p_fit = mm.program(c, ph, u, ph.lam0, couplers=cp0, restarts=2)["powers"]
    _, files = make(errors, ph._lam)
    paths = {k: icx.write_sparameters(ph, SCRATCH / f"coupler_error_{k}.dat", couplers=files[k]) for k in range(K)}
    with import_lumapi().INTERCONNECT(hide=True) as ic:
        mesh = icx.Mesh(ic, c, ph, paths, LAM_MAX, POINTS)
        check = {}
        for label, p in (("as programmed", p_nom), ("fitted", p_fit)):
            mesh.set_sites(mm.site_dn(c, ph, p))
            uu, _lam = mesh.measure()
            check[label] = (float(mm.fidelity(uu[POINTS // 2], u)), fid(p, cp0, u))
            print(
                f"  INTERCONNECT, sigma {CHECK_SIGMA} nm, {label}: F = {check[label][0]:.6f} (model {check[label][1]:.6f})",
                flush=True,
            )

    per_nm_gap = float(np.polyfit(SHIFTS_NM[3:6], shift_split[3:6], 1)[0])
    mzi = np.load(ROOT / "1_mzi" / "mzi.npz")  # the split of the coupler against the wavelength, from step 1
    lam_mzi, k2_mzi = mzi["lam"], mzi["kappa2"]
    j0 = int(np.argmin(np.abs(lam_mzi - ph.lam0)))
    per_nm_lam = float((k2_mzi[j0 + 1] - k2_mzi[j0 - 1]) / ((lam_mzi[j0 + 1] - lam_mzi[j0 - 1]) * 1000))

    def q(x, level):
        return float(np.quantile(x, level))

    lines = [
        "The Python model of the mesh (mesh_model.py), checked by INTERCONNECT, Lumerical 2025 R1: the 4 x 4 mesh with couplers",
        f"  whose gap is off by dg; L_pi = l0 exp(gap / {decay_um * 1000:.1f} nm) from the supermodes of the directional coupler chapter;",
        f"  split at 1.55 um without error {f0:.4f}; run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: a gap off by 1 nm moves the split by {100 * per_nm_gap:+.2f} percentage points, as much as {abs(per_nm_gap / per_nm_lam):.1f} nm of wavelength does.  "
        f"With random errors of sigma = 5 nm the matrix as programmed keeps a median 1 - F of {np.median(1 - rand_nominal[1]):.1e}; fitted to the "
        f"mesh as it came out, {np.median(1 - rand_fitted[1]):.1e}.  At sigma = 20 nm the fit still brings the median to "
        f"{np.median(1 - rand_fitted[3]):.1e}, and its worst case is {np.max(1 - rand_fitted[3]):.1e}.",
        "",
        f"a. every gap off by the same dg; the DFT and {COMMON_TARGETS - 1} random unitaries of step 2",
        "  dg (nm)   split   1 - F as programmed: DFT, median of random   fitted: DFT, median, worst",
    ]
    for i, dg in enumerate(SHIFTS_NM):
        lines.append(f"  {dg:+7.1f}  {shift_split[i]:.4f}   {1 - shift_nominal[i][0]:9.1e}  {np.median(1 - shift_nominal[i][1:]):9.1e}"
                     f"          {1 - shift_fitted[i][0]:9.1e}  {np.median(1 - shift_fitted[i][1:]):9.1e}  {np.max(1 - shift_fitted[i]):9.1e}")  # fmt: skip
    lines += [
        "  A block with couplers of cross power f passes at most 4 f (1 - f) across.  With every coupler at 0.40 that is 0.96:",
        "  a matrix that needs a block near full crossing is out of reach, and no setting of the phases brings it back.",
        "",
        f"b. every gap off by its own dg, normal with width sigma; {SAMPLES} meshes, each with its own random unitary",
        "  sigma (nm)   1 - F as programmed: median, 90 %   fitted: median, 90 %, worst   fitted F > 0.999",
    ]
    for i, sigma in enumerate(SIGMAS_NM):
        a, b = 1 - rand_nominal[i], 1 - rand_fitted[i]
        lines.append(f"  {sigma:9.1f}   {np.median(a):9.1e}  {q(a, 0.9):9.1e}       {np.median(b):9.1e}  {q(b, 0.9):9.1e}  {b.max():9.1e}"
                     f"   {np.mean(b < 1e-3) * 100:5.0f} %")  # fmt: skip
    lines += [
        "",
        f"c. INTERCONNECT, the first mesh of sigma = {CHECK_SIGMA} nm, 12 coupler files: "
        + "; ".join(f"{k} F = {v[0]:.6f} (model {v[1]:.6f})" for k, v in check.items()),
        "",
        "limits: the error changes the split only.  A real error of the gap also moves the mean index of the coupled section, and so",
        "  the phase of the block; the phases of a fitted mesh take that up as well.  The width of the waveguide, which a real",
        "  process also gets wrong, is not varied.  The fit assumes that the errors are known: a real mesh has to measure them first.",
    ]
    text = "\n".join(lines)
    print(text)
    (OUT / "errors.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "errors.npz", shifts_nm=SHIFTS_NM, shift_split=np.array(shift_split), shift_nominal=shift_nominal,
        shift_fitted=shift_fitted, sigmas_nm=SIGMAS_NM, random_nominal=rand_nominal, random_fitted=rand_fitted,
        random_errors_nm=rand_errors, decay_um=decay_um, split_lam0=f0, split_per_nm_gap=per_nm_gap,
        split_per_nm_lam=per_nm_lam, check_ic=np.array([check[k][0] for k in ("as programmed", "fitted")]),
        check_model=np.array([check[k][1] for k in ("as programmed", "fitted")]),
    )  # fmt: skip


if __name__ == "__main__":
    main()

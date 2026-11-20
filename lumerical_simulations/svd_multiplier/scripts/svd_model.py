"""The real matrix multiplier as a circuit: mesh V, a column of attenuators, mesh U, as drawn; and its programming.

The circuit has 2N rows: the N rows of the light, 0 ... N - 1, and the N dumps of the attenuators, N ... 2N - 1 (the
dump of row m is row N + m).  It is built from the layout (devices/svd_multiplier_builder.py):

    mesh V, mesh U   the circuit of each mesh as mesh_model.circuit() reads it from the info of the mesh, moved to
                     where the mesh stands along x
    attenuator m     on row m: its lead, the fan, the coupler, the fan, its arm, the fan, the coupler, the fan, and the
                     rest of the column; on its dump: the same, with the heated section in the middle of the arm.  The
                     fans open the 4 um of the coupler to half a pitch.  The coupler pairs the dump (upper) and the row

The pieces are those of the mesh (mesh_model.py): the FDTD coupler, the strip as INTERCONNECT writes it, and sites
that a heater warms.  A coupler here joins any two rows (its "upper" and "lower"), not only neighbours; transfer()
therefore takes the rows of every coupler from its entry.

Programming a real matrix M (program()):

    1. scale: M / s, with s its largest singular value, so that every singular value is at most 1
    2. SVD: M / s = U diag(sigma) V^T, U and V real and orthogonal
    3. the recipe: the decomposition of Clements et al. for V^T and U (mesh_model.clements), and for attenuator m the
       phase theta = 2 asin(sigma_m), which passes sin(theta / 2) of the field of the row
    4. the fit: Levenberg-Marquardt on all heater powers, so that the N x N block of the drawn circuit that joins the
       rows is a M / s, with a a common complex factor (a loss and a phase that the fidelity forgives)

A non-unitary target needs a fidelity that does not assume the target is unitary: here
F = |<M, T>|^2 / (<M, M> <T, T>), the square of the cosine between the two matrices taken as vectors, which is 1 when
the measured matrix T is the target up to a common factor; and the relative error |T - a M| / |a M| with a chosen best.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "clements_mesh" / "scripts"))  # the model of the mesh

import mesh_model as mm
import numpy as np

Circuit, Physics = mm.Circuit, mm.Physics


# =====================================================================================
# the circuit as drawn
# =====================================================================================
def circuit(layout: dict, heater_length: float) -> Circuit:
    """The pieces of the whole multiplier, row by row, and its couplers, sites and heaters."""
    n = layout["n"]
    c = Circuit(n=2 * n, rows={m: [] for m in range(2 * n)})

    def take(sub: Circuit, dx: float, prefix: str) -> None:
        s0, k0, h0 = len(c.sites), len(c.couplers), len(c.heaters)
        c.heaters += [{**h, "name": prefix + h["name"], "x": round(h["x"] + dx, 4), "part": prefix[0]} for h in sub.heaters]
        c.sites += [{**s, "x": s["x"] + dx, "heater": s["heater"] + h0 if s["heater"] >= 0 else -1} for s in sub.sites]
        c.couplers += [{"upper": cp["upper"], "lower": cp["upper"] + 1, "x": cp["x"] + dx} for cp in sub.couplers]
        for m, pieces in sub.rows.items():
            for p in pieces:
                if p[0] == "wg":
                    c.rows[m].append(("wg", p[1] + dx, p[2], p[3] + s0 if p[3] >= 0 else -1))
                else:
                    c.rows[m].append(("dc", p[1] + dx, p[2] + k0))

    c.parts = {"V_": mm.circuit(layout["v"], heater_length), "U_": mm.circuit(layout["u"], heater_length)}  # each mesh alone
    take(c.parts["V_"], layout["x"]["v"], "V_")
    for unit, h in zip(layout["a"]["units"], layout["a"]["heaters"], strict=True):
        _attenuator(c, layout["a"], unit, h, layout["x"]["a"], unit["row"], n + unit["row"], heater_length)
    take(c.parts["U_"], layout["x"]["u"], "U_")
    _ops(c)
    return c


def _attenuator(c: Circuit, att: dict, unit: dict, h: dict, xa: float, row: int, dump: int, heater_length: float) -> None:
    """The pieces of one attenuator on its row and its dump, from the info of the column, appended to the circuit."""
    F, dcl, S, alen = att["fan_length"], att["coupler_length"], att["section"], att["attenuator_length"]
    fan = mm.fan_path_length(att["pitch"] / 2, F)
    pre = (S - heater_length) / 2
    x0 = xa + unit["x0"]
    k1, k2 = len(c.couplers), len(c.couplers) + 1
    c.couplers += [{"upper": dump, "lower": row, "x": x0 + F}, {"upper": dump, "lower": row, "x": x0 + 3 * F + dcl + S}]
    site = len(c.sites)
    c.heaters.append({**h, "name": h["name"], "x": round(h["x"] + xa, 4), "part": "A"})
    c.sites.append({"row": dump, "x": h["x"] + xa, "heater": len(c.heaters) - 1, "own": True})
    arm = x0 + 2 * F + dcl
    c.rows[row] += [("wg", xa, x0 - xa, -1), ("wg", x0, fan, -1), ("dc", x0 + F, k1), ("wg", x0 + F + dcl, fan, -1),
                    ("wg", arm, S, -1), ("wg", arm + S, fan, -1), ("dc", arm + S + F, k2), ("wg", arm + S + F + dcl, fan, -1),
                    ("wg", x0 + alen, xa + att["length"] - (x0 + alen), -1)]  # fmt: skip
    c.rows[dump] += [("wg", x0, fan, -1), ("dc", x0 + F, k1), ("wg", x0 + F + dcl, fan, -1), ("wg", arm, pre, -1),
                     ("wg", arm + pre, heater_length, site), ("wg", arm + pre + heater_length, pre, -1),
                     ("wg", arm + S, fan, -1), ("dc", arm + S + F, k2), ("wg", arm + S + F + dcl, fan, -1)]  # fmt: skip


def _ops(c: Circuit) -> None:
    ops = []
    for m, pieces in c.rows.items():
        for p in pieces:
            if p[0] == "wg" and p[2] > 1e-9:
                ops.append((p[1], 0, ("wg", m, p[2], p[3])))
    ops += [(cp["x"], 1, ("dc", cp["upper"], k)) for k, cp in enumerate(c.couplers)]
    ops.sort(key=lambda o: (o[0], o[1]))
    c.ops = [o[2] for o in ops]
    c.rows = {m: [p for p in pieces if p[0] == "dc" or p[2] > 1e-9] for m, pieces in c.rows.items()}


def attenuator_circuit(layout: dict, heater_length: float, k: int = 0) -> Circuit:
    """One attenuator of the column alone, with its lead: row 0 its dump, row 1 its row (as in the 2 x 2 of the mesh
    chapter, the upper waveguide first)."""
    att = layout["a"]
    unit = att["units"][k]
    c = Circuit(n=2, rows={0: [], 1: []})
    _attenuator(c, att, {**unit, "x0": unit["x0"]}, att["heaters"][k], 0.0, 1, 0, heater_length)
    _ops(c)
    return c


def transfer(c: Circuit, ph: Physics, lam, site_dn, couplers: dict | None = None) -> np.ndarray:
    """T[lam, out, in] of all 2N rows of the drawn circuit, for the index change of every site.  A coupler joins the two
    rows of its entry.  couplers: per coupler id, a 2 x 2 matrix [[tau, kappa], [kappa, tau]] for every lam."""
    lam = np.atleast_1d(np.asarray(lam, dtype=float))
    size = lam.size
    u = np.broadcast_to(np.eye(c.n, dtype=complex), (size, c.n, c.n)).copy()
    s = ph.coupler(lam, (3, 4))
    nominal = np.empty((size, 2, 2), dtype=complex)
    nominal[:, 0, 0] = nominal[:, 1, 1] = s[4]
    nominal[:, 0, 1] = nominal[:, 1, 0] = s[3]
    site_dn = np.asarray(site_dn, dtype=float)
    for op in c.ops:
        if op[0] == "wg":
            _, m, length, site = op
            u[:, m, :] *= ph.propagate(lam, length, site_dn[site] if site >= 0 else 0.0)[:, None]
        else:
            k = op[2]
            rows = [c.couplers[k]["upper"], c.couplers[k]["lower"]]
            t = nominal if couplers is None or k not in couplers else couplers[k]
            u[:, rows, :] = t @ u[:, rows, :]
    return u


def matrix(c: Circuit, ph: Physics, lam, powers, couplers: dict | None = None) -> np.ndarray:
    """The N x N block that joins the rows of the light: M[lam, out, in]."""
    n = c.n // 2
    return transfer(c, ph, lam, mm.site_dn(c, ph, powers), couplers)[:, :n, :n]


# =====================================================================================
# a real matrix, programmed
# =====================================================================================
def fidelity(t: np.ndarray, target: np.ndarray) -> float:
    """|<M, T>|^2 / (<M, M> <T, T>): 1 when T is the target up to a common complex factor."""
    inner = np.vdot(target, t)
    return float(abs(inner) ** 2 / (np.vdot(target, target).real * np.vdot(t, t).real))


def best_factor(t: np.ndarray, target: np.ndarray) -> complex:
    """The complex a that makes |T - a M| least."""
    return complex(np.vdot(target, t) / np.vdot(target, target))


def relative_error(t: np.ndarray, target: np.ndarray) -> float:
    a = best_factor(t, target)
    return float(np.linalg.norm(t - a * target) / np.linalg.norm(a * target))


def svd_parts(m: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """M = s U diag(sigma) V^T with sigma <= 1: U, sigma, V^T and the scale s (the largest singular value)."""
    u, sigma, vt = np.linalg.svd(np.asarray(m, dtype=float))
    s = float(sigma[0])
    return u, sigma / s, vt, s


def ideal(u: np.ndarray, sigma: np.ndarray, vt: np.ndarray) -> np.ndarray:
    return u @ np.diag(sigma) @ vt


def recipe(c: Circuit, ph: Physics, m: np.ndarray) -> dict:
    """The phases of the recipe as heater powers (mW), each in [0, 2 P_pi): Clements for V^T and for U, and
    theta = 2 asin(sigma) for the attenuators."""
    u, sigma, vt, s = svd_parts(m)
    phase = np.zeros(len(c.heaters))
    index = {h["name"]: j for j, h in enumerate(c.heaters)}
    for prefix, target in (("V_", vt), ("U_", u)):
        theta, phi, delta = mm.clements(np.asarray(target, dtype=complex))
        for k in range(len(theta)):
            phase[index[f"{prefix}T{k}"]] = theta[k]
            phase[index[f"{prefix}P{k}"]] = phi[k]
        for r, d in enumerate(delta):
            phase[index[f"{prefix}D{r}"]] = d
    for r, sg in enumerate(sigma):
        theta = 2 * math.asin(min(1.0, float(sg)))
        phase[index[f"A{r}"]] = theta
        # the attenuator passes -i e^(i theta / 2) sin(theta / 2) of its row: the output phase of mesh V, just before
        # it, takes up its phase
        phase[index[f"V_D{r}"]] += math.pi / 2 - theta / 2
    return {"powers": ph.phase_to_power(np.mod(phase, 2 * np.pi)), "u": u, "sigma": sigma, "vt": vt, "scale": s}


def attenuator(theta: float) -> np.ndarray:
    """The ideal attenuator, as the block of the mesh with 50:50 couplers and theta on the upper arm (the dump), seen
    from its row: the 2 x 2 matrix on (dump, row); the row keeps -i e^(i theta / 2) sin(theta / 2) of its field."""
    return mm.B @ mm.shifter(theta) @ mm.B


def ideal_multiplier(n: int, phases: dict) -> np.ndarray:
    """The multiplier with ideal couplers and nothing else, from the phases by heater name: mesh V, the attenuators
    (the row's own entry of each), mesh U."""

    def mesh(prefix: str) -> np.ndarray:
        k = len(mm.blocks(n))
        return mm.ideal_mesh(n, [phases[f"{prefix}T{j}"] for j in range(k)], [phases[f"{prefix}P{j}"] for j in range(k)],
                             [phases[f"{prefix}D{r}"] for r in range(n)])  # fmt: skip

    a = np.diag([attenuator(phases[f"A{r}"])[1, 1] for r in range(n)])
    return mesh("U_") @ a @ mesh("V_")


def _residual(t: np.ndarray, target: np.ndarray) -> np.ndarray:
    r = (t - best_factor(t, target) * target).ravel()
    return np.concatenate([r.real, r.imag])


def fit(
    c: Circuit, ph: Physics, target: np.ndarray, start, lam0: float, iterations: int = 200, couplers: dict | None = None
) -> np.ndarray:
    """Levenberg-Marquardt on the heater powers, as mesh_model.fit_powers: the block of the drawn circuit that joins
    the rows is the target, up to a common factor.  The powers are kept in [0, 2 P_pi)."""
    x = np.mod(np.asarray(start, dtype=float), 2 * ph.P_pi)

    def res(p):
        return _residual(matrix(c, ph, lam0, np.mod(p, 2 * ph.P_pi), couplers)[0], target)

    r = res(x)
    cost, lam = float(r @ r), 1e-3
    h = 1e-4 * ph.P_pi
    for _ in range(iterations):
        if cost < 1e-24:
            break
        jac = np.empty((r.size, x.size))
        for i in range(x.size):
            step = np.zeros_like(x)
            step[i] = h
            jac[:, i] = (res(x + step) - res(x - step)) / (2 * h)
        a, g = jac.T @ jac, jac.T @ r
        for _ in range(30):
            trial = x - np.linalg.solve(a + lam * np.diag(np.diag(a) + 1e-12), g)
            rt = res(trial)
            if float(rt @ rt) < cost:
                gain = (cost - float(rt @ rt)) / cost
                x, r, cost = trial, rt, float(rt @ rt)
                lam = max(lam / 3, 1e-12)
                break
            lam *= 4
        else:
            break
        if gain < 1e-10:
            break
    return np.mod(x, 2 * ph.P_pi)


def start(c: Circuit, ph: Physics, r: dict, lam0: float) -> np.ndarray:
    """A start for the fit of the whole: each mesh fitted alone, as drawn, to V^T and to U (mesh_model.program, which
    the mesh chapter shows to reach any unitary), the attenuators from the recipe, and the phase of each attenuator
    taken up by the output phase of mesh V, as in the recipe."""
    powers = np.array(r["powers"], dtype=float)
    index = {h["name"]: j for j, h in enumerate(c.heaters)}
    for prefix, target in (("V_", r["vt"]), ("U_", r["u"])):
        sub = c.parts[prefix]
        p = mm.program(sub, ph, np.asarray(target, dtype=complex), lam0, restarts=4)["powers"]
        for h, pw in zip(sub.heaters, p, strict=True):
            powers[index[prefix + h["name"]]] = pw
    for row, sg in enumerate(r["sigma"]):
        theta = 2 * math.asin(min(1.0, float(sg)))
        powers[index[f"V_D{row}"]] += ph.phase_to_power(math.pi / 2 - theta / 2)
    return np.mod(powers, 2 * ph.P_pi)


def program(c: Circuit, ph: Physics, m: np.ndarray, lam0: float, couplers: dict | None = None) -> dict:
    """The recipe and the fit for a real matrix M; the fidelities of both, at lam0.  The fit starts from the meshes
    fitted alone (start()); from the recipe of the ideal circuit it can end in a minimum that is not the target."""
    r = recipe(c, ph, m)
    target = ideal(r["u"], r["sigma"], r["vt"])  # M / s
    p0 = start(c, ph, r, lam0)
    p = fit(c, ph, target, p0, lam0, couplers=couplers)
    t_recipe = matrix(c, ph, lam0, r["powers"], couplers)[0]
    t_start = matrix(c, ph, lam0, p0, couplers)[0]
    t_fit = matrix(c, ph, lam0, p, couplers)[0]
    return {**r, "target": target, "powers_recipe": r["powers"], "powers_start": p0, "powers": p,
            "fidelity_recipe": fidelity(t_recipe, target), "fidelity_start": fidelity(t_start, target),
            "fidelity": fidelity(t_fit, target), "error_recipe": relative_error(t_recipe, target),
            "error_start": relative_error(t_start, target), "error": relative_error(t_fit, target)}  # fmt: skip

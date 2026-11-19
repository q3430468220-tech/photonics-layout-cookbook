"""The Clements mesh as a circuit: the drawn layout turned into a chain of waveguides, couplers and heated sections, its
transfer matrix, the decomposition of the paper, and the programming of the drawn circuit.

The circuit is read from the layout (devices/clements_mesh_builder.py).  Along each row it is a chain of pieces:

    straight    a straight strip waveguide: phase beta L, with beta from n_eff at lam0 and n_g around it
    fan         an S-bend of the fan: the same, over the length of its path
    site        100 um of straight waveguide that a heater can warm: its index rises by dn_eff per kelvin, or per
                milliwatt of its own heater (the film of a heater is 100 um long)
    coupler     the directional coupler of its chapter: its complex S-parameters from 3D FDTD, moved from the FDTD
                ports to the ends of the cell (1 um of strip at each port)
    arm         one arm of the coupler alone, on an edge row without a block (the dummy path of the layout): the strip
                over the length of its path

A site lies on every row under every heater, also on the rows that have no heater there: a heater warms its
neighbours too (step 3).  The phase convention is that of the FDTD S-parameters, e^(+i beta L): the phase grows
with frequency, and a warmer waveguide adds phase.

The decomposition (clements) is that of W. R. Clements et al., Optica 3, 1460 (2016), written for the block of this
mesh, T(theta, phi) = B P(theta) B P(phi), with B = [[1, i], [i, 1]] / sqrt 2 and P(a) = diag(e^(i a), 1): theta on
the upper arm, phi on the upper input.  It assumes ideal couplers and no other phase.  program() then corrects the
phases for the circuit as drawn by a least-squares fit, starting from the decomposition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

B = np.array([[1, 1j], [1j, 1]]) / math.sqrt(2)


def blocks(n: int) -> list[tuple[int, int]]:
    """The blocks column by column, from the top: (column, upper mode).  The same order as the layout's
    (devices/clements_mesh_builder.blocks, which a test compares)."""
    return [(c, p) for c in range(n) for p in range(c % 2, n - 1, 2)]


# =====================================================================================
# the ideal block and the decomposition of the paper
# =====================================================================================
def shifter(a: float) -> np.ndarray:
    return np.diag([np.exp(1j * a), 1.0])


def block(theta: float, phi: float) -> np.ndarray:
    """The Mach-Zehnder block with ideal couplers: phi on the upper input, theta on the upper arm."""
    return B @ shifter(theta) @ B @ shifter(phi)


def ideal_mesh(n: int, theta, phi, delta) -> np.ndarray:
    """The ideal mesh: the blocks column by column (as devices/clements_mesh_builder.blocks), then the output phases."""
    u = np.eye(n, dtype=complex)
    for k, (_, p) in enumerate(blocks(n)):
        u[p : p + 2] = block(theta[k], phi[k]) @ u[p : p + 2]
    return np.diag(np.exp(1j * np.asarray(delta))) @ u


def _null_from_right(a: complex, b: complex) -> tuple[float, float]:
    """theta, phi such that (a, b) @ T^-1 has a zero first entry: (a, b) is then a multiple of the second row of T."""
    theta = 2 * math.atan2(abs(b), abs(a))
    phi = 0.0 if abs(a) < 1e-15 or abs(b) < 1e-15 else math.pi + np.angle(a) - np.angle(b)
    return theta, float(phi)


def _null_from_left(a: complex, b: complex) -> tuple[float, float]:
    """theta, phi such that T (a, b) has a zero second entry."""
    theta = 2 * math.atan2(abs(a), abs(b))
    phi = 0.0 if abs(a) < 1e-15 or abs(b) < 1e-15 else float(np.angle(b) - np.angle(a))
    return theta, phi


def split(m: np.ndarray) -> tuple[complex, complex, float, float]:
    """Write a 2 x 2 unitary as diag(d1, d2) T(theta, phi): the step of the paper that moves the left blocks through
    the diagonal.  The entries of T are T11 = i e^(i phi) e^(i theta/2) sin(theta/2), T12 = i e^(i theta/2) cos(theta/2),
    T21 = i e^(i phi) e^(i theta/2) cos(theta/2), T22 = -i e^(i theta/2) sin(theta/2)."""
    s = min(1.0, abs(m[0, 0]))
    theta = 2 * math.asin(s)
    half = np.exp(1j * theta / 2)
    sin, cos = math.sin(theta / 2), math.cos(theta / 2)
    eps = 1e-12
    if cos > eps and sin > eps:
        d1 = m[0, 1] / (1j * half * cos)
        d2 = m[1, 1] / (-1j * half * sin)
        e_phi = m[0, 0] / (d1 * 1j * half * sin)
    elif cos <= eps:  # theta = pi: no light crosses; phi is free
        d1 = m[0, 0] / (1j * half * sin)
        d2 = m[1, 1] / (-1j * half * sin)
        e_phi = 1.0
    else:  # theta = 0: all light crosses; phi is free
        d1 = m[0, 1] / (1j * half * cos)
        d2 = m[1, 0] / (1j * half * cos)
        e_phi = 1.0
    return complex(d1), complex(d2), theta, float(np.angle(e_phi))


def clements(u: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """theta, phi of every block (in the order of blocks(n)) and the output phases delta, with ideal_mesh = u."""
    n = u.shape[0]
    w = np.array(u, dtype=complex)
    right, left = [], []  # (upper mode, theta, phi)
    for i in range(1, n):
        if i % 2 == 1:
            for j in range(i):  # null w[n-1-j, i-1-j] with a block on the columns (i-1-j, i-j), from the right
                m, r = i - 1 - j, n - 1 - j
                theta, phi = _null_from_right(w[r, m], w[r, m + 1])
                w[:, m : m + 2] = w[:, m : m + 2] @ np.linalg.inv(block(theta, phi))
                right.append((m, theta, phi))
        else:
            for j in range(1, i + 1):  # null w[n+j-i-1, j-1] with a block on the rows (n+j-i-2, n+j-i-1), from the left
                m, col = n + j - i - 2, j - 1
                theta, phi = _null_from_left(w[m, col], w[m + 1, col])
                w[m : m + 2] = block(theta, phi) @ w[m : m + 2]
                left.append((m, theta, phi))
    d = np.diag(w).copy()  # w is diagonal now: u = L1^-1 ... Llast^-1 D Rlast ... R1
    moved = []  # Llast^-1 D = D' T'last, then L(last-1)^-1 D' = D'' T'(last-1), ...: u = D T'1 ... T'last Rlast ... R1
    for m, theta, phi in reversed(left):
        sub = np.linalg.inv(block(theta, phi)) @ np.diag(d[m : m + 2])
        d1, d2, t2, p2 = split(sub)
        d[m], d[m + 1] = d1, d2
        moved.append((m, t2, p2))
    order = right + moved  # in the order of the light: R1 ... Rlast, then T'last ... T'1
    # each block goes into the first column after the blocks it follows on its two modes
    last = [-1] * n
    placed = {}
    for m, theta, phi in order:
        column = max(last[m], last[m + 1]) + 1
        if column % 2 != m % 2:
            column += 1
        last[m] = last[m + 1] = column
        placed[(column, m)] = (theta, phi)
    keys = blocks(n)
    if set(placed) != set(keys):
        raise RuntimeError("the decomposition did not fill the rectangular mesh")
    theta = np.array([placed[k][0] for k in keys])
    phi = np.array([placed[k][1] for k in keys])
    return np.mod(theta, 2 * np.pi), np.mod(phi, 2 * np.pi), np.mod(np.angle(d), 2 * np.pi)


def fidelity(u: np.ndarray, target: np.ndarray) -> float:
    """|Tr(target^H u)|^2 / (N Tr(u^H u)): 1 when u is the target up to a global phase and a common loss."""
    n = target.shape[0]
    return float(abs(np.trace(target.conj().T @ u)) ** 2 / (n * np.real(np.trace(u.conj().T @ u))))


def dft(n: int) -> np.ndarray:
    j, k = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    return np.exp(2j * np.pi * j * k / n) / math.sqrt(n)


def haar(n: int, rng: np.random.Generator) -> np.ndarray:
    """A random unitary, uniform over the unitary group (the QR recipe with the phases of R removed)."""
    z = (rng.standard_normal((n, n)) + 1j * rng.standard_normal((n, n))) / math.sqrt(2)
    q, r = np.linalg.qr(z)
    return q * (np.diag(r) / abs(np.diag(r)))


# =====================================================================================
# the circuit as drawn
# =====================================================================================
@dataclass
class Circuit:
    """The pieces of the drawn mesh.  ops: in the order of x, ('wg', row, length, site or -1) or ('dc', upper row, id)."""

    n: int
    ops: list = field(default_factory=list)
    sites: list = field(default_factory=list)  # {row, x, heater (index into heaters), own (bool)}
    heaters: list = field(default_factory=list)  # from the layout: name, kind, block, row, x, y
    couplers: list = field(default_factory=list)  # {upper, x}
    rows: dict = field(default_factory=dict)  # row -> its pieces in order, for INTERCONNECT


def fan_path_length(pitch: float, length: float) -> float:
    """The length of the path of one S-bend of the fan (the cubic Bezier curve that gdsfactory draws)."""
    from devices import clements_mesh_builder as cm

    ref = cm.fan(pitch)
    if "length" in ref.info:
        return float(ref.info["length"])
    raise KeyError("the S-bend has no length in its info")


def circuit(info: dict, heater_length: float) -> Circuit:
    """The chain of pieces along every row, from the layout's info."""
    n, S, F, dcl = info["n"], info["section"], info["fan_length"], info["coupler_length"]
    fan_len = fan_path_length(info["pitch"], F)
    segs: dict[int, list] = {m: [] for m in range(n)}
    couplers = []
    for b in info["blocks"]:
        x0, p = b["x0"], b["upper"]
        xs = [x0, x0 + S, x0 + S + F, x0 + S + F + dcl, x0 + S + 2 * F + dcl, x0 + 2 * S + 2 * F + dcl,
              x0 + 2 * S + 3 * F + dcl, x0 + 2 * S + 3 * F + 2 * dcl, x0 + 2 * S + 4 * F + 2 * dcl]  # fmt: skip
        ids = (len(couplers), len(couplers) + 1)
        couplers += [{"upper": p, "x": xs[2]}, {"upper": p, "x": xs[6]}]
        for m in (p, p + 1):
            segs[m] += [("straight", xs[0], xs[1]), ("fan", xs[1], xs[2]), ("dc", xs[2], xs[3], ids[0]),
                        ("fan", xs[3], xs[4]), ("straight", xs[4], xs[5]), ("fan", xs[5], xs[6]),
                        ("dc", xs[6], xs[7], ids[1]), ("fan", xs[7], xs[8])]  # fmt: skip
    for dmy in info.get("dummies", []):  # an edge row without a block: the same fans, and one arm of a coupler alone
        x0, m = dmy["x0"], dmy["row"]
        xs = [x0, x0 + S, x0 + S + F, x0 + S + F + dcl, x0 + S + 2 * F + dcl, x0 + 2 * S + 2 * F + dcl,
              x0 + 2 * S + 3 * F + dcl, x0 + 2 * S + 3 * F + 2 * dcl, x0 + 2 * S + 4 * F + 2 * dcl]  # fmt: skip
        segs[m] += [("straight", xs[0], xs[1]), ("fan", xs[1], xs[2]), ("arm", xs[2], xs[3]), ("fan", xs[3], xs[4]),
                    ("straight", xs[4], xs[5]), ("fan", xs[5], xs[6]), ("arm", xs[6], xs[7]), ("fan", xs[7], xs[8])]  # fmt: skip
    for m in range(n):  # fill the rest of every row with straight waveguide
        segs[m].sort(key=lambda s: s[1])
        filled, x = [], 0.0
        for s in segs[m]:
            if s[1] > x + 1e-9:
                filled.append(("straight", x, s[1]))
            filled.append(s)
            x = s[2]
        if info["length"] > x + 1e-9:
            filled.append(("straight", x, info["length"]))
        segs[m] = filled
    # the sites: under every heater position, on every row whose straight waveguide runs beneath it.  Two heaters on
    # different rows may share an x; the rows there still have one site each.
    sites = []
    for x in sorted({h["x"] for h in info["heaters"]}):
        a, b = x - heater_length / 2, x + heater_length / 2
        for m in range(n):
            if any(s[0] == "straight" and s[1] <= a + 1e-9 and b <= s[2] + 1e-9 for s in segs[m]):
                own = [j for j, h in enumerate(info["heaters"]) if h["row"] == m and abs(h["x"] - x) < 1e-6]
                sites.append({"row": m, "x": x, "heater": own[0] if own else -1, "own": bool(own)})
    ops, rows = [], {m: [] for m in range(n)}
    for m in range(n):
        mine = sorted((k for k, s in enumerate(sites) if s["row"] == m), key=lambda k: sites[k]["x"])
        for s in segs[m]:
            if s[0] == "straight":  # split at the sites that lie in it, from the west
                x = s[1]
                for k in mine:
                    a = sites[k]["x"] - heater_length / 2
                    if not (s[1] - 1e-9 <= a and a + heater_length <= s[2] + 1e-9):
                        continue
                    if a > x + 1e-9:
                        rows[m].append(("wg", x, a - x, -1))
                    rows[m].append(("wg", a, heater_length, k))
                    x = a + heater_length
                if s[2] > x + 1e-9:
                    rows[m].append(("wg", x, s[2] - x, -1))
            elif s[0] == "fan":
                rows[m].append(("wg", s[1], fan_len, -1))
            elif s[0] == "arm":  # an isolated waveguide of the coupler's shape: the strip, over the length of its path
                rows[m].append(("wg", s[1], info["arm_length"], -1))
            else:
                rows[m].append(("dc", s[1], s[3]))
    for m in range(n):
        for piece in rows[m]:
            if piece[0] == "wg":
                ops.append((piece[1], 0, ("wg", m, piece[2], piece[3])))
    for k, c in enumerate(couplers):
        ops.append((c["x"], 1, ("dc", c["upper"], k)))
    ops.sort(key=lambda o: (o[0], o[1]))
    return Circuit(n=n, ops=[o[2] for o in ops], sites=sites, heaters=list(info["heaters"]), couplers=couplers, rows=rows)


# =====================================================================================
# the physics of the pieces
# =====================================================================================
class Physics:
    """The numbers the pieces need, from the device chapters (common.inputs())."""

    def __init__(self, d: dict, loss_db_cm: float, port_extra: float):
        self.neff, self.ng, self.lam0 = d["neff"], d["ng"], d["lam0"]
        self.dn_dlam = (self.neff - self.ng) / self.lam0  # per um: n_g = n_eff - lam dn/dlam
        self.dneff_dP, self.dneff_dT = d["dneff_dP"], d["dneff_dT"]
        self.L_heater = d["heater_length"]
        self.P_pi = self.lam0 / (2 * self.L_heater * self.dneff_dP)
        self.alpha = loss_db_cm * 1e-4 * math.log(10) / 20  # amplitude loss per um
        self.port_extra = port_extra
        lam, S = d["coupler_lam"], d["coupler_S"]
        order = np.argsort(lam)
        self._lam = lam[order]
        self._S = {k: v[order] for k, v in S.items()}

    def n(self, lam):
        """The effective index at lam, to first order: n_g = n_eff - lam dn/dlam."""
        return self.neff + (np.asarray(lam) - self.lam0) * self.dn_dlam

    def beta_length(self, lam, length: float, dn=0.0):
        """The phase of a straight piece, beta L, as INTERCONNECT's straight waveguide writes it: the wavenumber at the
        reference frequency from n_eff + dn, and its change with frequency from n_g (no dispersion beyond it).  A
        heater's dn moves the first term only."""
        lam = np.asarray(lam, dtype=float)
        return 2 * np.pi * length * ((self.neff + dn) / self.lam0 + self.ng * (1 / lam - 1 / self.lam0))

    def propagate(self, lam, length: float, dn=0.0):
        """The field factor of a straight piece: e^(i beta L), with the loss."""
        return np.exp(1j * self.beta_length(lam, length, dn) - self.alpha * length)

    def coupler(self, lam, which: tuple[int, ...] = (1, 2, 3, 4)) -> dict[int, np.ndarray]:
        """S11, S21, S31, S41 of the coupler at lam, moved from the FDTD ports to the ends of the cell."""
        lam = np.atleast_1d(np.asarray(lam, dtype=float))
        back = np.exp(-1j * self.beta_length(lam, 2 * self.port_extra))  # the 1 um of lead at each port
        out = {}
        for k in which:
            s = self._S[k]
            mag = np.interp(lam, self._lam, np.abs(s))
            ph = np.interp(lam, self._lam, np.unwrap(np.angle(s)))
            out[k] = mag * np.exp(1j * ph) * back
        return out

    def phase_to_power(self, phase):
        """The heater power that gives a phase at lam0: P = phase / pi x P_pi."""
        return np.asarray(phase) / np.pi * self.P_pi

    def power_to_dn(self, power):
        return np.asarray(power) * self.dneff_dP


def transfer(c: Circuit, ph: Physics, lam, site_dn, couplers: dict | None = None) -> np.ndarray:
    """U[lam, out, in] of the drawn mesh, for the index change of every site.  couplers: per coupler id, a 2 x 2 forward
    matrix [[tau, kappa], [kappa, tau]] (upper, lower) for every lam, instead of the FDTD coupler (step 4)."""
    lam = np.atleast_1d(np.asarray(lam, dtype=float))
    L = lam.size
    u = np.broadcast_to(np.eye(c.n, dtype=complex), (L, c.n, c.n)).copy()
    s = ph.coupler(lam, (3, 4))
    nominal = np.empty((L, 2, 2), dtype=complex)
    nominal[:, 0, 0] = nominal[:, 1, 1] = s[4]  # through: o2 -> o3 and o1 -> o4
    nominal[:, 0, 1] = nominal[:, 1, 0] = s[3]  # cross
    site_dn = np.asarray(site_dn, dtype=float)
    for op in c.ops:
        if op[0] == "wg":
            _, m, length, site = op
            dn = site_dn[site] if site >= 0 else 0.0
            u[:, m, :] *= ph.propagate(lam, length, dn)[:, None]
        else:
            _, p, k = op
            t = nominal if couplers is None or k not in couplers else couplers[k]
            u[:, p : p + 2, :] = t @ u[:, p : p + 2, :]
    return u


def own_sites(c: Circuit) -> np.ndarray:
    """For every heater, the index of its own site."""
    out = np.full(len(c.heaters), -1)
    for k, s in enumerate(c.sites):
        if s["own"]:
            out[s["heater"]] = k
    if (out < 0).any():
        raise RuntimeError("a heater has no site of its own")
    return out


def site_dn(c: Circuit, ph: Physics, powers, crosstalk: np.ndarray | None = None) -> np.ndarray:
    """The index change of every site for the heater powers (mW).  crosstalk[site, heater]: the rise of the site per
    milliwatt of the heater over the rise of the heater's own site (1 there); None: each heater warms its own site only."""
    powers = np.asarray(powers, dtype=float)
    if crosstalk is None:
        dn = np.zeros(len(c.sites))
        dn[own_sites(c)] = ph.power_to_dn(powers)
        return dn
    return ph.power_to_dn(crosstalk @ powers)


def heater_order(c: Circuit) -> dict[str, np.ndarray]:
    """The heater indices of phi and theta of every block (in block order) and of the outputs (by row)."""
    k = len([h for h in c.heaters if h["kind"] == "theta"])
    out = {"phi": np.zeros(k, int), "theta": np.zeros(k, int), "out": np.zeros(c.n, int)}
    for j, h in enumerate(c.heaters):
        if h["kind"] == "out":
            out["out"][h["row"]] = j
        else:
            out[h["kind"]][h["block"]] = j
    return out


def phases_to_powers(c: Circuit, ph: Physics, theta, phi, delta) -> np.ndarray:
    """Heater powers (mW) for the phases of the decomposition, each in [0, 2 pi)."""
    order = heater_order(c)
    phase = np.zeros(len(c.heaters))
    phase[order["theta"]] = np.mod(theta, 2 * np.pi)
    phase[order["phi"]] = np.mod(phi, 2 * np.pi)
    phase[order["out"]] = np.mod(delta, 2 * np.pi)
    return ph.phase_to_power(phase)


# =====================================================================================
# programming the drawn circuit
# =====================================================================================
def _residual(u: np.ndarray, target: np.ndarray) -> np.ndarray:
    """u - a target with the best complex factor a: zero when u is the target up to a global phase and a common loss."""
    a = np.trace(target.conj().T @ u) / target.shape[0]
    r = (u - a * target).ravel()
    return np.concatenate([r.real, r.imag])


def fit_powers(c: Circuit, ph: Physics, target: np.ndarray, start, lam0: float, crosstalk=None, couplers=None,
               iterations: int = 200) -> np.ndarray:  # fmt: skip
    """Levenberg-Marquardt on the heater powers, so that the circuit at lam0 is the target.  The circuit is always
    evaluated at the powers a heater can have, in [0, 2 P_pi): a power the fit takes below zero is the same phase at
    2 P_pi less a little.  Without crosstalk that is the same circuit; with it, it is not, because a heater at 2 P_pi
    warms its neighbours, and the fit must see that."""
    x = np.mod(np.asarray(start, dtype=float), 2 * ph.P_pi)

    def res(p):
        p = np.mod(p, 2 * ph.P_pi)
        return _residual(transfer(c, ph, lam0, site_dn(c, ph, p, crosstalk), couplers)[0], target)

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
                x, r, cost = trial, rt, float(rt @ rt)
                lam = max(lam / 3, 1e-12)
                break
            lam *= 4
        else:
            break
    return np.mod(x, 2 * ph.P_pi)


def program(c: Circuit, ph: Physics, target: np.ndarray, lam0: float, crosstalk=None, couplers=None,
            restarts: int = 12, seed: int = 1) -> dict:  # fmt: skip
    """The heater powers for a target: the decomposition of the paper (ideal mesh), then the fit for the circuit as
    drawn from that start; when the fit ends below a fidelity of 1 - 1e-9, it is repeated from random starts and the
    best is kept."""
    theta, phi, delta = clements(target)
    ideal_error = float(np.max(np.abs(ideal_mesh(target.shape[0], theta, phi, delta) - target)))
    start = phases_to_powers(c, ph, theta, phi, delta)
    best, f_best, tries = None, -1.0, 0
    rng = np.random.default_rng(seed)
    for attempt in range(restarts + 1):
        guess = start if attempt == 0 else rng.uniform(0, 2 * ph.P_pi, start.size)
        p = fit_powers(c, ph, target, guess, lam0, crosstalk, couplers)
        f = fidelity(transfer(c, ph, lam0, site_dn(c, ph, p, crosstalk), couplers)[0], target)
        tries += 1
        if f > f_best:
            best, f_best = p, f
        if f_best > 1 - 1e-9:
            break
    return {"powers": best, "fidelity": f_best, "start": start, "tries": tries, "ideal_error": ideal_error,
            "theta": theta, "phi": phi, "delta": delta}  # fmt: skip


# =====================================================================================
# the heat that reaches the neighbours (step 3)
# =====================================================================================
_GL_X, _GL_W = np.polynomial.legendre.leggauss(96)


def mean_rise(src: tuple[float, float, float], dst: tuple[float, float, float], k_silicon: float, wafer: float) -> float:
    """The mean rise (K per mW) along a waveguide segment dst = (x0, x1, y), when a heater film src = (x0, x1, y) puts
    1 mW into the substrate, by the estimate of the phase shifter chapter (step 4c): a source on the surface of a
    wafer of thickness `wafer` warms the surface at the distance r by P / (2 pi k r), less P ln 2 / (2 pi k H) for the
    cold back, to first order; here averaged over the film and over the segment by Gauss-Legendre.  k in W/m/K, um."""
    (a1, b1, y1), (a2, b2, y2) = src, dst
    xs = (a1 + b1) / 2 + (b1 - a1) / 2 * _GL_X
    xr = (a2 + b2) / 2 + (b2 - a2) / 2 * _GL_X
    r = np.sqrt((xs[:, None] - xr[None, :]) ** 2 + (y1 - y2) ** 2)
    mean_inverse = float((_GL_W[:, None] * _GL_W[None, :] / r).sum() / 4)  # 1 / um
    k = k_silicon * 1e-6  # W / um / K
    P = 1e-3
    return P / (2 * np.pi * k) * mean_inverse - P * math.log(2) / (2 * np.pi * k * wafer)


def crosstalk_matrix(
    c: Circuit, heater_length: float, k_silicon: float, wafer: float, own_rise: float
) -> tuple[np.ndarray, np.ndarray]:
    """rise[site, heater] in K per mW, and share = rise / own_rise: 1 on the heater's own site, the estimate elsewhere.
    The path through the oxide is left out: every heater has its trenches, and the chapter found it negligible beyond
    them (0.02 % at 10 um)."""
    rows_y = {h["row"]: h["y"] for h in c.heaters}
    pitch = abs(rows_y[0] - rows_y[1]) if len(rows_y) > 1 else 0.0
    rise = np.zeros((len(c.sites), len(c.heaters)))
    for s, site in enumerate(c.sites):
        y_site = -site["row"] * pitch
        for j, h in enumerate(c.heaters):
            if site["heater"] == j:
                rise[s, j] = own_rise
                continue
            src = (h["x"] - heater_length / 2, h["x"] + heater_length / 2, h["y"])
            dst = (site["x"] - heater_length / 2, site["x"] + heater_length / 2, y_site)
            rise[s, j] = mean_rise(src, dst, k_silicon, wafer)
    return rise, rise / own_rise

// photonics-layout-cookbook: program the Clements mesh in the browser (website/fx/programmer.py puts the circuit
// into the page).
//
//   the matrix    M from the grid or a preset.  Its nearest unitary Q (the polar factor) is what a mesh of lossless
//                 interferometers can set; Q = M when M is unitary.
//   the phases    the decomposition of Clements et al. (2016) for the block B P(theta) B P(phi) of the chapter, as
//                 scripts/mesh_model.py writes it: theta, phi of every block and a phase for every output.
//   the voltages  the phases as heater powers, P = phase / pi x P_pi, then Levenberg-Marquardt on the sixteen powers
//                 so that the circuit as drawn (its couplers, its waveguides with their loss) is Q; V = sqrt(P R).
//   the light     the field of x through the drawn circuit, piece by piece; y = U x on the dials.
//
// The mathematics stands in MeshMath, with no page around it: website/tests/test_programmer.py runs it in node.
const MeshMath = (() => {
  "use strict";
  const TAU = 2 * Math.PI;
  const mod = (a, m) => ((a % m) + m) % m;

  // ---- complex numbers as [re, im], and n x n matrices of them ----
  const C = (re, im = 0) => [re, im];
  const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
  const mul = (a, b) => [a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]];
  const conj = (a) => [a[0], -a[1]];
  const abs = (a) => Math.hypot(a[0], a[1]);
  const arg = (a) => Math.atan2(a[1], a[0]);
  const scale = (a, s) => [a[0] * s, a[1] * s];
  const div = (a, b) => {
    const d = b[0] * b[0] + b[1] * b[1];
    return [(a[0] * b[0] + a[1] * b[1]) / d, (a[1] * b[0] - a[0] * b[1]) / d];
  };
  const expi = (t) => [Math.cos(t), Math.sin(t)];
  const zeros = (n, m = n) => Array.from({ length: n }, () => Array.from({ length: m }, () => C(0)));
  const eye = (n) => zeros(n).map((row, i) => row.map((_, j) => C(i === j ? 1 : 0)));
  const copy = (a) => a.map((row) => row.map((z) => [z[0], z[1]]));
  const matmul = (a, b) =>
    a.map((row) => b[0].map((_, j) => row.reduce((s, z, k) => add(s, mul(z, b[k][j])), C(0))));
  const adjoint = (a) => a[0].map((_, j) => a.map((row) => conj(row[j])));
  const frob = (a) => Math.sqrt(a.reduce((s, row) => s + row.reduce((t, z) => t + z[0] * z[0] + z[1] * z[1], 0), 0));
  const matvec = (a, v) => a.map((row) => row.reduce((s, z, k) => add(s, mul(z, v[k])), C(0)));

  function inverse(a) {
    // Gauss-Jordan with partial pivoting; null when the matrix is singular
    const n = a.length;
    const m = a.map((row, i) => [...row.map((z) => [z[0], z[1]]), ...eye(n)[i]]);
    const size = frob(a) || 1;
    for (let col = 0; col < n; col++) {
      let best = col;
      for (let r = col + 1; r < n; r++) if (abs(m[r][col]) > abs(m[best][col])) best = r;
      if (abs(m[best][col]) < 1e-12 * size) return null;
      [m[col], m[best]] = [m[best], m[col]];
      const p = m[col][col];
      m[col] = m[col].map((z) => div(z, p));
      for (let r = 0; r < n; r++) {
        if (r === col) continue;
        const f = m[r][col];
        m[r] = m[r].map((z, k) => sub(z, mul(f, m[col][k])));
      }
    }
    return m.map((row) => row.slice(n));
  }

  // the eigenvalues of a real symmetric matrix, by the cyclic method of Jacobi
  function symmetricEigenvalues(a) {
    const n = a.length;
    const m = a.map((row) => [...row]);
    for (let sweep = 0; sweep < 60; sweep++) {
      let off = 0;
      for (let p = 0; p < n; p++) for (let q = p + 1; q < n; q++) off += m[p][q] * m[p][q];
      if (off < 1e-30) break;
      for (let p = 0; p < n; p++) {
        for (let q = p + 1; q < n; q++) {
          if (Math.abs(m[p][q]) < 1e-300) continue;
          const theta = (m[q][q] - m[p][p]) / (2 * m[p][q]);
          const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
          const c = 1 / Math.sqrt(t * t + 1);
          const s = t * c;
          for (let k = 0; k < n; k++) {
            const kp = m[k][p];
            const kq = m[k][q];
            m[k][p] = c * kp - s * kq;
            m[k][q] = s * kp + c * kq;
          }
          for (let k = 0; k < n; k++) {
            const pk = m[p][k];
            const qk = m[q][k];
            m[p][k] = c * pk - s * qk;
            m[q][k] = s * pk + c * qk;
          }
        }
      }
    }
    return m.map((row, i) => row[i]);
  }

  // the singular values of a complex matrix: the eigenvalues of M^H M, a Hermitian matrix written as a real one
  // twice as large ([[Re, -Im], [Im, Re]], every eigenvalue twice)
  function singularValues(a) {
    const n = a.length;
    const h = matmul(adjoint(a), a);
    const big = Array.from({ length: 2 * n }, (_, i) =>
      Array.from({ length: 2 * n }, (_, j) => {
        const z = h[i % n][j % n];
        if (i < n === j < n) return z[0];
        return i < n ? -z[1] : z[1];
      }),
    );
    const values = symmetricEigenvalues(big).sort((x, y) => y - x);
    return values.filter((_, i) => i % 2 === 0).map((v) => Math.sqrt(Math.max(0, v)));
  }

  // the nearest unitary to a matrix (the polar factor), by the scaled iteration of Newton: Q <- (g Q + (g Q)^-H) / 2
  function polar(a) {
    let q = copy(a);
    let singular = false;
    if (!inverse(q)) {
      singular = true; // a singular matrix has more than one nearest unitary: nudge it, and take one of them
      const size = frob(a) || 1;
      q = q.map((row, i) => row.map((z, j) => add(z, C(1e-7 * size * (i === j ? 1 : 0.37 * Math.sin(3 * i + 7 * j)), 0))));
    }
    for (let k = 0; k < 100; k++) {
      const inv = inverse(q);
      if (!inv) break;
      const g = k < 12 ? Math.sqrt(frob(inv) / frob(q)) : 1;
      const next = q.map((row, i) => row.map((z, j) => scale(add(scale(z, g), scale(conj(inv[j][i]), 1 / g)), 0.5)));
      const change = frob(next.map((row, i) => row.map((z, j) => sub(z, q[i][j]))));
      q = next;
      if (change < 1e-15 && k > 2) break;
    }
    return { q, singular };
  }

  // ---- the block of the chapter and the decomposition of the paper ----
  const R2 = Math.SQRT1_2;
  const B = [[C(R2), C(0, R2)], [C(0, R2), C(R2)]];
  const shifter = (a) => [[expi(a), C(0)], [C(0), C(1)]];
  const block = (theta, phi) => matmul(matmul(matmul(B, shifter(theta)), B), shifter(phi));

  function blocks(n) {
    const out = [];
    for (let c = 0; c < n; c++) for (let p = c % 2; p < n - 1; p += 2) out.push([c, p]);
    return out;
  }

  function nullFromRight(a, b) {
    const theta = 2 * Math.atan2(abs(b), abs(a));
    const phi = abs(a) < 1e-15 || abs(b) < 1e-15 ? 0 : Math.PI + arg(a) - arg(b);
    return [theta, phi];
  }

  function nullFromLeft(a, b) {
    const theta = 2 * Math.atan2(abs(a), abs(b));
    const phi = abs(a) < 1e-15 || abs(b) < 1e-15 ? 0 : arg(b) - arg(a);
    return [theta, phi];
  }

  function split(m) {
    // a 2 x 2 unitary as diag(d1, d2) T(theta, phi)
    const s = Math.min(1, abs(m[0][0]));
    const theta = 2 * Math.asin(s);
    const half = expi(theta / 2);
    const sin = Math.sin(theta / 2);
    const cos = Math.cos(theta / 2);
    const i = C(0, 1);
    const eps = 1e-12;
    let d1;
    let d2;
    let ePhi = C(1);
    if (cos > eps && sin > eps) {
      d1 = div(m[0][1], scale(mul(i, half), cos));
      d2 = div(m[1][1], scale(mul(i, half), -sin));
      ePhi = div(m[0][0], scale(mul(d1, mul(i, half)), sin));
    } else if (cos <= eps) {
      d1 = div(m[0][0], scale(mul(i, half), sin));
      d2 = div(m[1][1], scale(mul(i, half), -sin));
    } else {
      d1 = div(m[0][1], scale(mul(i, half), cos));
      d2 = div(m[1][0], scale(mul(i, half), cos));
    }
    return [d1, d2, theta, arg(ePhi)];
  }

  function clements(u) {
    const n = u.length;
    const w = copy(u);
    const right = [];
    const left = [];
    for (let i = 1; i < n; i++) {
      if (i % 2 === 1) {
        for (let j = 0; j < i; j++) {
          const m = i - 1 - j;
          const r = n - 1 - j;
          const [theta, phi] = nullFromRight(w[r][m], w[r][m + 1]);
          const inv = adjoint(block(theta, phi));
          for (const row of w) {
            const [a, b] = [row[m], row[m + 1]];
            row[m] = add(mul(a, inv[0][0]), mul(b, inv[1][0]));
            row[m + 1] = add(mul(a, inv[0][1]), mul(b, inv[1][1]));
          }
          right.push([m, theta, phi]);
        }
      } else {
        for (let j = 1; j <= i; j++) {
          const m = n + j - i - 2;
          const [theta, phi] = nullFromLeft(w[m][j - 1], w[m + 1][j - 1]);
          const t = block(theta, phi);
          for (let k = 0; k < n; k++) {
            const [a, b] = [w[m][k], w[m + 1][k]];
            w[m][k] = add(mul(t[0][0], a), mul(t[0][1], b));
            w[m + 1][k] = add(mul(t[1][0], a), mul(t[1][1], b));
          }
          left.push([m, theta, phi]);
        }
      }
    }
    const d = w.map((row, i) => row[i]);
    const moved = [];
    for (const [m, theta, phi] of [...left].reverse()) {
      const sub2 = matmul(adjoint(block(theta, phi)), [[d[m], C(0)], [C(0), d[m + 1]]]);
      const [d1, d2, t2, p2] = split(sub2);
      d[m] = d1;
      d[m + 1] = d2;
      moved.push([m, t2, p2]);
    }
    const last = new Array(n).fill(-1);
    const placed = new Map();
    for (const [m, theta, phi] of [...right, ...moved]) {
      let column = Math.max(last[m], last[m + 1]) + 1;
      if (column % 2 !== m % 2) column += 1;
      last[m] = column;
      last[m + 1] = column;
      placed.set(`${column},${m}`, [theta, phi]);
    }
    const keys = blocks(n);
    if (keys.some(([c, p]) => !placed.has(`${c},${p}`))) throw new Error("the decomposition did not fill the mesh");
    return {
      theta: keys.map(([c, p]) => mod(placed.get(`${c},${p}`)[0], TAU)),
      phi: keys.map(([c, p]) => mod(placed.get(`${c},${p}`)[1], TAU)),
      delta: d.map((z) => mod(arg(z), TAU)),
    };
  }

  function idealMesh(n, theta, phi, delta) {
    let u = eye(n);
    blocks(n).forEach(([, p], k) => {
      const t = block(theta[k], phi[k]);
      const rows = [u[p], u[p + 1]];
      u[p] = rows[0].map((z, j) => add(mul(t[0][0], z), mul(t[0][1], rows[1][j])));
      u[p + 1] = rows[0].map((z, j) => add(mul(t[1][0], z), mul(t[1][1], rows[1][j])));
    });
    u = u.map((row, i) => row.map((z) => mul(expi(delta[i]), z)));
    return u;
  }

  // ---- the circuit as drawn ----
  function Circuit(data) {
    const n = data.n;
    const ops = data.ops;
    const [tr, ti] = data.through;
    const [kr, ki] = data.cross;
    const perMW = Math.PI / data.P_pi;
    const sitePhase = new Float64Array(data.sites);

    function setPowers(powers) {
      sitePhase.fill(0);
      data.heaters.forEach((h, j) => {
        sitePhase[h.site] = perMW * powers[j];
      });
    }

    // U of the circuit (re, im: n x n, row-major) for the heater powers in mW
    function transfer(powers, re = new Float64Array(n * n), im = new Float64Array(n * n)) {
      setPowers(powers);
      re.fill(0);
      im.fill(0);
      for (let i = 0; i < n; i++) re[i * n + i] = 1;
      for (const op of ops) {
        if (op[0] === 0) {
          let fr = op[2];
          let fi = op[3];
          if (op[4] >= 0 && sitePhase[op[4]] !== 0) {
            const c = Math.cos(sitePhase[op[4]]);
            const s = Math.sin(sitePhase[op[4]]);
            [fr, fi] = [fr * c - fi * s, fr * s + fi * c];
          }
          const o = op[1] * n;
          for (let j = 0; j < n; j++) {
            const a = re[o + j];
            const b = im[o + j];
            re[o + j] = a * fr - b * fi;
            im[o + j] = a * fi + b * fr;
          }
        } else {
          const o = op[1] * n;
          for (let j = 0; j < n; j++) {
            const ar = re[o + j];
            const ai = im[o + j];
            const br = re[o + n + j];
            const bi = im[o + n + j];
            re[o + j] = tr * ar - ti * ai + kr * br - ki * bi;
            im[o + j] = tr * ai + ti * ar + kr * bi + ki * br;
            re[o + n + j] = kr * ar - ki * ai + tr * br - ti * bi;
            im[o + n + j] = kr * ai + ki * ar + tr * bi + ti * br;
          }
        }
      }
      return [re, im];
    }

    // the field of x along the mesh: the power in every piece of light (rows in order, from the west), and y
    function light(powers, x) {
      setPowers(powers);
      const vr = x.map((z) => z[0]);
      const vi = x.map((z) => z[1]);
      const offset = [];
      data.pieces.forEach((m, k) => {
        if (offset[m] === undefined) offset[m] = k;
      });
      const at = offset.slice();
      const out = new Float64Array(data.pieces.length);
      for (let m = 0; m < n; m++) out[at[m]] = vr[m] * vr[m] + vi[m] * vi[m];
      for (const op of ops) {
        if (op[0] === 0) {
          let fr = op[2];
          let fi = op[3];
          if (op[4] >= 0 && sitePhase[op[4]] !== 0) {
            const c = Math.cos(sitePhase[op[4]]);
            const s = Math.sin(sitePhase[op[4]]);
            [fr, fi] = [fr * c - fi * s, fr * s + fi * c];
          }
          const m = op[1];
          [vr[m], vi[m]] = [vr[m] * fr - vi[m] * fi, vr[m] * fi + vi[m] * fr];
        } else {
          const p = op[1];
          const [ar, ai, br, bi] = [vr[p], vi[p], vr[p + 1], vi[p + 1]];
          vr[p] = tr * ar - ti * ai + kr * br - ki * bi;
          vi[p] = tr * ai + ti * ar + kr * bi + ki * br;
          vr[p + 1] = kr * ar - ki * ai + tr * br - ti * bi;
          vi[p + 1] = kr * ai + ki * ar + tr * bi + ti * br;
          for (const m of [p, p + 1]) {
            at[m] += 1;
            out[at[m]] = vr[m] * vr[m] + vi[m] * vi[m];
          }
        }
      }
      return { pieces: out, y: vr.map((r, m) => C(r, vi[m])) };
    }
    return { n, transfer, light, perMW };
  }

  // the best complex factor a with U = a T, and the fidelity |Tr(T^H U)|^2 / (N Tr(U^H U))
  function compare(re, im, target) {
    const n = target.length;
    let tr = 0;
    let ti = 0;
    let norm = 0;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const [a, b] = target[i][j];
        const ur = re[i * n + j];
        const ui = im[i * n + j];
        tr += a * ur + b * ui; // conj(T) U
        ti += a * ui - b * ur;
        norm += ur * ur + ui * ui;
      }
    }
    return { a: C(tr / n, ti / n), fidelity: (tr * tr + ti * ti) / (n * norm) };
  }

  function solve(a, b) {
    // Gaussian elimination with partial pivoting, real
    const n = b.length;
    const m = a.map((row, i) => [...row, b[i]]);
    for (let col = 0; col < n; col++) {
      let best = col;
      for (let r = col + 1; r < n; r++) if (Math.abs(m[r][col]) > Math.abs(m[best][col])) best = r;
      [m[col], m[best]] = [m[best], m[col]];
      const p = m[col][col] || 1e-300;
      for (let r = col + 1; r < n; r++) {
        const f = m[r][col] / p;
        if (f !== 0) for (let k = col; k <= n; k++) m[r][k] -= f * m[col][k];
      }
    }
    const x = new Array(n).fill(0);
    for (let r = n - 1; r >= 0; r--) {
      let s = m[r][n];
      for (let k = r + 1; k < n; k++) s -= m[r][k] * x[k];
      x[r] = s / (m[r][r] || 1e-300);
    }
    return x;
  }

  // Levenberg-Marquardt on the heater powers, as mesh_model.fit_powers: U of the drawn circuit = a target
  function fit(circuit, target, start, P_pi, iterations = 200) {
    const n = target.length;
    const span = 2 * P_pi;
    const re = new Float64Array(n * n);
    const im = new Float64Array(n * n);
    const residual = (p) => {
      circuit.transfer(p, re, im);
      const { a } = compare(re, im, target);
      const r = new Float64Array(2 * n * n);
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          const [tr, ti] = mul(a, target[i][j]);
          r[i * n + j] = re[i * n + j] - tr;
          r[n * n + i * n + j] = im[i * n + j] - ti;
        }
      }
      return r;
    };
    const dot = (u, v) => u.reduce((s, x, i) => s + x * v[i], 0);
    let x = start.map((p) => mod(p, span));
    let r = residual(x);
    let cost = dot(r, r);
    let lambda = 1e-3;
    const h = 1e-4 * P_pi;
    for (let it = 0; it < iterations && cost > 1e-24; it++) {
      const jac = x.map((_, i) => {
        const up = x.slice();
        const down = x.slice();
        up[i] += h;
        down[i] -= h;
        const a = residual(up);
        const b = residual(down);
        return a.map((v, k) => (v - b[k]) / (2 * h));
      }); // jac[i] is the column of parameter i
      const A = jac.map((ci) => jac.map((cj) => dot(ci, cj)));
      const g = jac.map((ci) => dot(ci, r));
      let moved = false;
      for (let k = 0; k < 30; k++) {
        const step = solve(A.map((row, i) => row.map((v, j) => (i === j ? v + lambda * (v + 1e-12) : v))), g);
        const trial = x.map((v, i) => v - step[i]);
        const rt = residual(trial);
        const ct = dot(rt, rt);
        if (ct < cost) {
          const gain = (cost - ct) / cost;
          x = trial;
          r = rt;
          cost = ct;
          lambda = Math.max(lambda / 3, 1e-12);
          moved = gain > 1e-9;
          break;
        }
        lambda *= 4;
      }
      if (!moved) break;
    }
    return x.map((p) => mod(p, span));
  }

  // the decomposition, its powers, and the fit for the circuit as drawn; random starts when the fit stops short
  function program(data, circuit, target, random = Math.random) {
    const { theta, phi, delta } = clements(target);
    const phase = new Array(data.heaters.length).fill(0);
    data.theta.forEach((j, k) => (phase[j] = theta[k]));
    data.phi.forEach((j, k) => (phase[j] = phi[k]));
    data.out.forEach((j, m) => (phase[j] = delta[m]));
    const recipe = phase.map((a) => (mod(a, TAU) / Math.PI) * data.P_pi);
    const n = target.length;
    const re = new Float64Array(n * n);
    const im = new Float64Array(n * n);
    const fidelityOf = (p) => {
      circuit.transfer(p, re, im);
      return compare(re, im, target).fidelity;
    };
    let best = fit(circuit, target, recipe, data.P_pi);
    let fBest = fidelityOf(best);
    let starts = 1;
    for (let k = 0; k < 8 && 1 - fBest > 1e-5; k++) {
      const p = fit(circuit, target, recipe.map(() => random() * 2 * data.P_pi), data.P_pi);
      const f = fidelityOf(p);
      starts += 1;
      if (f > fBest) [best, fBest] = [p, f];
    }
    return { recipe, fRecipe: fidelityOf(recipe), powers: best, fidelity: fBest, theta, phi, delta, starts };
  }

  // ---- numbers typed by a reader: 0.5, -1, .5i, i, -i, 0.35-0.35i, 1/2, √2/2; NaN parts when it is none ----
  function parse(text) {
    let t = String(text).trim().replace(/[−–]/g, "-").replace(/\s+/g, "").replace(/j$/, "i");
    if (t === "") return [0, 0];
    t = t.replace(/√(\d*\.?\d+)/g, (_, v) => String(Math.sqrt(Number(v))));
    const num = (s) => {
      if (s === "" || s === "+") return 1;
      if (s === "-") return -1;
      if (s.includes("/")) {
        const [a, b] = s.split("/");
        return a === "" || b === "" ? NaN : Number(a) / Number(b);
      }
      return Number(s);
    };
    const m = t.match(/^([+-]?[\d./]*?)([+-][\d./]*)i$/);
    if (m && m[1] !== "") return [num(m[1]), num(m[2])];
    if (t.endsWith("i")) return [0, num(t.slice(0, -1))];
    return [num(t), 0];
  }

  // a whole vector in one line: "1, 0, 0.5i, -1", in brackets or not; null when the text is a single number
  function parseList(text) {
    const inner = String(text).trim().replace(/^[([{]|[)\]}]$/g, "");
    const parts = inner.split(/[,;]/);
    if (parts.length < 2) return null;
    return parts.map((part) => parse(part));
  }

  return { parse, parseList, C, add, sub, mul, div, conj, abs, arg, expi, matmul, matvec, adjoint, frob, eye, copy, inverse, polar,
    scale, singularValues, block, blocks, clements, idealMesh, Circuit, compare, fit, program, mod };
})();

if (typeof module !== "undefined") module.exports = MeshMath;

// ---- the page ----
(() => {
  "use strict";
  if (typeof document === "undefined") return;
  const root = document.querySelector("[data-pg]");
  const raw = document.getElementById("pg-data");
  if (!root || !raw) return;
  const M = MeshMath;
  const D = JSON.parse(raw.textContent);
  const n = D.n;
  const calm = Boolean(window.COOKBOOK_CALM);
  const circuit = M.Circuit(D);
  const svg = root.querySelector(".pg-svg");
  const stage = root.querySelector("[data-pg-stage]");
  const tip = root.querySelector(".pg-tip");
  const DIAL = 30;

  const pieces = [...svg.querySelectorAll(".pg-pc")].sort((a, b) => a.dataset.k - b.dataset.k);
  const heaterNodes = [...svg.querySelectorAll(".pg-ht")];
  const volts = [...svg.querySelectorAll("[data-volt]")];
  const dialsIn = [...svg.querySelectorAll(".pg-dial-in")];
  const dialsOut = [...svg.querySelectorAll(".pg-dial-out")];
  const valIn = [...svg.querySelectorAll("[data-in-val]")];
  const valOut = [...svg.querySelectorAll("[data-out-val]")];
  const cells = [...root.querySelectorAll("[data-cell]")];
  const ucells = [...root.querySelectorAll("[data-ucell]")];
  const hcells = [...root.querySelectorAll("[data-hcell]")];
  const sliders = [...root.querySelectorAll("[data-x]")];
  const status = root.querySelector("[data-status]");
  const pipe = root.querySelector("[data-pipe]");
  const out = (key) => root.querySelector(`[data-${key}]`);
  const tableX = [...root.querySelectorAll("[data-tx]")];
  const tableY = [...root.querySelectorAll("[data-ty]")];
  const tableT = [...root.querySelectorAll("[data-tt]")];

  // ---- numbers as text ----
  const sign = (v) => (v < 0 ? "−" : "");
  const fixed = (v, d) => {
    const t = Math.abs(v).toFixed(d);
    return Number(t) === 0 ? (0).toFixed(d) : sign(v) + t;
  };
  function complexText(z, d = 3, plus = false) {
    const [re, im] = [Math.abs(z[0]) < 5e-4 ? 0 : z[0], Math.abs(z[1]) < 5e-4 ? 0 : z[1]];
    if (im === 0) return (plus && re > 0 ? "+" : "") + fixed(re, d);
    if (re === 0) return `${plus && im > 0 ? "+" : ""}${fixed(im, d)}i`;
    const e = Math.min(d, 2);
    return `${(plus && re > 0 ? "+" : "") + fixed(re, e)}${im < 0 ? "−" : "+"}${Math.abs(im).toFixed(e)}i`;
  }
  // an entry of U: one line, or two for a complex number (its real part, then its imaginary part)
  function cellText(z) {
    const text = complexText(z, 3);
    const at = text.search(/.[+−]/);
    if (!text.endsWith("i") || at < 0) return [text];
    return [text.slice(0, at + 1), text.slice(at + 1)].map((part) => Object.assign(document.createElement("span"), { textContent: part }));
  }
  const parse = M.parse;

  // ---- the state ----
  const state = {
    m: null, // the matrix typed, n x n of [re, im]
    exact: null, // a preset with all its digits, until a cell is typed into
    q: null, // what the mesh is given: its nearest unitary
    result: null, // the program: recipe, powers, fidelities
    mode: "fit",
    x: [M.C(1), M.C(0), M.C(0), M.C(0)],
    shown: new Array(D.heaters.length).fill(0), // the powers on the page now (they move towards the program)
    probe: null, // an input column alone, while the pointer is on an entry of a matrix
  };

  function setGrid(m) {
    cells.forEach((cell) => {
      const [i, j] = cell.dataset.cell.split("-").map(Number);
      cell.value = complexText(m[i][j], 3);
      cell.classList.remove("is-bad");
    });
  }

  function readGrid() {
    const m = M.eye(n).map((row) => row.map(() => M.C(0)));
    let bad = null;
    cells.forEach((cell) => {
      const [i, j] = cell.dataset.cell.split("-").map(Number);
      const z = parse(cell.value);
      const ok = Number.isFinite(z[0]) && Number.isFinite(z[1]);
      cell.classList.toggle("is-bad", !ok);
      if (!ok && !bad) bad = [i, j];
      m[i][j] = ok ? z : M.C(0);
    });
    return { m, bad };
  }

  // ---- the presets ----
  function gauss() {
    let u = 0;
    while (u === 0) u = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * Math.random());
  }
  function randomOrthogonal() {
    const cols = [];
    while (cols.length < n) {
      let v = Array.from({ length: n }, gauss);
      for (const c of cols) {
        const d = v.reduce((s, x, i) => s + x * c[i], 0);
        v = v.map((x, i) => x - d * c[i]);
      }
      const norm = Math.hypot(...v);
      if (norm > 1e-6) cols.push(v.map((x) => x / norm));
    }
    return Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => M.C(cols[j][i])));
  }
  function preset(key) {
    if (key === "orthogonal") return randomOrthogonal();
    if (key === "dft") {
      return Array.from({ length: n }, (_, j) => Array.from({ length: n }, (_, k) => M.expi((2 * Math.PI * j * k) / n).map((v) => v / Math.sqrt(n))));
    }
    if (key === "real") return Array.from({ length: n }, () => Array.from({ length: n }, () => M.C(Math.round(gauss() * 50) / 100)));
    return D.presets[key].m.map((row) => row.map((z) => M.C(z[0], z[1])));
  }

  // ---- what the matrix is, in words ----
  function describe(m) {
    const size = M.frob(m);
    if (size < 1e-9) return { q: null, text: "M is zero: there is nothing to set. Give the grid a matrix, or take a preset." };
    const sv = M.singularValues(m);
    const real = m.every((row) => row.every((z) => Math.abs(z[1]) < 1e-12));
    const spread = (sv[0] - sv[n - 1]) / sv[0];
    if (spread < 5e-3) {
      // unitary, or a multiple of one; to the digits it is typed with, the polar factor is what is meant
      const s = sv.reduce((a, v) => a + v, 0) / n;
      const q = spread < 1e-12 && Math.abs(s - 1) < 1e-12 ? m : M.polar(m).q;
      const what = real ? "real and orthogonal, so unitary" : "unitary";
      const digits = spread < 1e-9 ? "" : " to the digits it is written with";
      if (Math.abs(s - 1) < 5e-3) return { q, text: `M is ${what}${digits}: the mesh sets it as it is.` };
      return { q, text: `M is ${s.toFixed(3)} times a matrix that is ${what}${digits}: the mesh sets M / ${s.toFixed(3)}, and the factor is a gain or a loss outside it.` };
    }
    const { q, singular } = M.polar(m);
    const list = sv.map((v) => v.toFixed(2)).join(", ");
    return {
      q,
      text:
        `M is not unitary: it stretches some directions more than others (singular values ${list})` +
        `${singular ? ", and it is singular" : ""}. A mesh of lossless interferometers only turns the light, so it sets the ` +
        "nearest unitary instead, the polar factor Q (on the right). To set M itself, M = U Σ V^H takes two meshes and a " +
        "column of attenuators for Σ: the next chapter, optical computing.",
      notUnitary: true,
    };
  }

  // ---- programming ----
  function programNow() {
    const read = readGrid();
    const m = state.exact || read.m; // a preset keeps all its digits; the grid shows three
    const bad = state.exact ? null : read.bad;
    if (bad) {
      status.textContent = `Row ${bad[0] + 1}, column ${bad[1] + 1} is not a number: write 0.5, −1, 0.5i or 0.35−0.35i.`;
      status.classList.add("is-bad");
      return;
    }
    status.classList.remove("is-bad");
    state.m = m;
    const said = describe(m);
    root.classList.toggle("is-polar", Boolean(said.notUnitary));
    out("target-head").innerHTML = said.notUnitary ? "<em>Q x</em>" : "<em>M x</em>";
    if (!said.q) {
      state.q = null;
      state.result = null;
      status.textContent = said.text;
      pipe.textContent = "";
      moveTo(new Array(D.heaters.length).fill(0));
      return;
    }
    state.q = said.q;
    const t0 = performance.now();
    state.result = M.program(D, circuit, said.q);
    const ms = Math.max(1, Math.round(performance.now() - t0));
    const r = state.result;
    status.textContent = said.text;
    pipe.textContent =
      `decomposed into ${r.theta.length} blocks and ${r.delta.length} output phases → ` +
      `fitted to the drawn circuit in ${ms} ms${r.starts > 1 ? ` (${r.starts} starts)` : ""} → ${D.heaters.length} voltages`;
    moveTo(state.mode === "fit" ? r.powers : r.recipe);
    pulse();
  }

  // the heaters move from what they hold to the new powers, as a supply would ramp them
  let anim = 0;
  function moveTo(target) {
    cancelAnimationFrame(anim);
    if (calm) {
      state.shown = target.slice();
      draw();
      return;
    }
    const from = state.shown.slice();
    const t0 = performance.now();
    const T = 900;
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const step = (now) => {
      const t = Math.min(1, (now - t0) / T);
      state.shown = from.map((p, j) => p + (target[j] - p) * ease(t));
      draw();
      if (t < 1) anim = requestAnimationFrame(step);
    };
    anim = requestAnimationFrame(step);
  }

  function pulse() {
    if (calm) return;
    svg.classList.remove("is-pulse");
    void svg.getBBox();
    svg.classList.add("is-pulse");
  }

  // ---- drawing ----
  const bright = (p) => Math.pow(Math.max(0, Math.min(1, p)), 0.55);
  function setDial(g, z, ghost) {
    const px = z[0] * DIAL;
    const py = -z[1] * DIAL;
    g.querySelector(".pg-arrow").setAttribute("d", `M0 0L${px.toFixed(2)} ${py.toFixed(2)}`);
    const tipDot = g.querySelector(".pg-tip");
    tipDot.setAttribute("cx", px.toFixed(2));
    tipDot.setAttribute("cy", py.toFixed(2));
    g.style.setProperty("--o", bright(z[0] * z[0] + z[1] * z[1]).toFixed(3));
    if (ghost) {
      const gx = ghost[0] * DIAL;
      const gy = -ghost[1] * DIAL;
      g.querySelector(".pg-ghost").setAttribute("d", `M0 0L${gx.toFixed(2)} ${gy.toFixed(2)}`);
      const dot = g.querySelector(".pg-ghost-tip");
      dot.setAttribute("cx", gx.toFixed(2));
      dot.setAttribute("cy", gy.toFixed(2));
    }
  }

  const re = new Float64Array(n * n);
  const im = new Float64Array(n * n);
  function draw() {
    const powers = state.shown;
    // the heaters
    let total = 0;
    let vmax = 0;
    powers.forEach((p, j) => {
      const v = Math.sqrt(Math.max(0, p) * 1e-3 * D.R);
      total += p;
      vmax = Math.max(vmax, v);
      const share = p / (2 * D.P_pi);
      heaterNodes[j].style.setProperty("--h", share.toFixed(3));
      volts[j].textContent = ` ${v.toFixed(2)} V`;
      hcells[j].style.setProperty("--h", share.toFixed(3));
      hcells[j].querySelector("[data-hv]").textContent = `${v.toFixed(2)} V`;
      hcells[j].querySelector("[data-hp]").textContent = `${p.toFixed(2)} mW`;
    });
    out("total").textContent = total.toFixed(1);
    out("vmax").textContent = vmax.toFixed(2);

    // the matrix of the circuit, divided by the best common factor a: its global phase and its common loss
    circuit.transfer(powers, re, im);
    const target = state.q;
    // the phase is the one of the best factor a, U = a T; the loss is the mean transmission, Tr(U^H U) / N, which
    // does not depend on the target
    let transmission = 0;
    for (let k = 0; k < n * n; k++) transmission += re[k] * re[k] + im[k] * im[k];
    transmission /= n;
    out("loss").textContent = (-10 * Math.log10(transmission)).toFixed(2);
    let unit = M.C(1 / Math.sqrt(transmission));
    if (target) {
      const { a, fidelity } = M.compare(re, im, target);
      if (M.abs(a) > 1e-9) unit = M.conj(a).map((v) => v / M.abs(a) / Math.sqrt(transmission));
      out("infid").innerHTML = infidelityText(1 - fidelity);
    } else {
      out("infid").textContent = "–";
    }
    const u = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => M.mul(M.C(re[i * n + j], im[i * n + j]), unit)));
    ucells.forEach((cell) => {
      const [i, j] = cell.dataset.ucell.split("-").map(Number);
      const z = u[i][j];
      cell.replaceChildren(...cellText(z));
      cell.style.setProperty("--v", Math.min(1, M.abs(z)).toFixed(3));
      cell.classList.toggle("is-neg", Math.abs(z[1]) < 5e-3 && z[0] < 0);
      cell.classList.toggle("is-cx", Math.abs(z[1]) >= 5e-3);
      cell.classList.toggle("is-off", Boolean(target) && M.abs(M.sub(z, target[i][j])) > 0.02);
    });

    // the light
    // the light: y = U x for the vector as it is given; the dials and the brightness are drawn relative to |x|
    const x = state.probe !== null ? Array.from({ length: n }, (_, k) => M.C(k === state.probe ? 1 : 0)) : state.x;
    const size = Math.sqrt(x.reduce((s, z) => s + z[0] * z[0] + z[1] * z[1], 0));
    const per = size > 1e-12 ? 1 / size : 0;
    const { pieces: power, y } = circuit.light(powers, x);
    pieces.forEach((piece, k) => piece.style.setProperty("--o", bright(power[k] * per * per).toFixed(3)));
    const yy = y.map((z) => M.mul(z, unit));
    const t = target ? M.matvec(target, x) : new Array(n).fill(M.C(0));
    dialsIn.forEach((g, m) => setDial(g, M.scale(x[m], per)));
    dialsOut.forEach((g, m) => setDial(g, M.scale(yy[m], per), M.scale(t[m], per)));
    valIn.forEach((node, m) => (node.textContent = complexText(x[m], 2, true)));
    valOut.forEach((node, m) => (node.textContent = complexText(yy[m], 2, true)));
    tableX.forEach((node, m) => (node.textContent = complexText(x[m], 3)));
    tableY.forEach((node, m) => (node.textContent = complexText(yy[m], 3)));
    tableT.forEach((node, m) => (node.textContent = complexText(t[m], 3)));
    root.classList.toggle("is-dark", per === 0);
  }

  function infidelityText(v) {
    if (!(v >= 0) || !Number.isFinite(v)) return "–";
    if (v < 1e-12) return "&lt; 10<sup>−12</sup>";
    if (v >= 0.01) return v.toFixed(3);
    const e = Math.floor(Math.log10(v));
    return `${(v / 10 ** e).toFixed(1)} × 10<sup>−${-e}</sup>`;
  }

  // ---- the controls ----
  const presetButtons = [...root.querySelectorAll("[data-preset]")];
  presetButtons.forEach((b) =>
    b.addEventListener("click", () => {
      presetButtons.forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
      state.exact = preset(b.dataset.preset);
      setGrid(state.exact);
      programNow();
    }),
  );
  let typing = 0;
  cells.forEach((cell) =>
    cell.addEventListener("input", () => {
      presetButtons.forEach((o) => o.setAttribute("aria-pressed", "false"));
      state.exact = null;
      clearTimeout(typing);
      typing = setTimeout(programNow, 350);
    }),
  );
  cells.forEach((cell) => cell.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      clearTimeout(typing);
      programNow();
    }
  }));

  const modeButtons = [...root.querySelectorAll("[data-mode]")];
  modeButtons.forEach((b) =>
    b.addEventListener("click", () => {
      state.mode = b.dataset.mode;
      modeButtons.forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
      root.classList.toggle("is-recipe", state.mode === "recipe");
      out("mode-note").textContent = D.notes[state.mode];
      if (state.result) moveTo(state.mode === "fit" ? state.result.powers : state.result.recipe);
    }),
  );

  const vecButtons = [...root.querySelectorAll("[data-vec]")];
  const boxes = [...root.querySelectorAll("[data-xin]")];
  // a slider runs from -1 to 1 and is lit from its middle, where the port is dark, to its value
  function fill(slider) {
    const at = ((Math.max(-1, Math.min(1, Number(slider.value))) + 1) / 2) * 100;
    slider.style.setProperty("--lo", `${Math.min(50, at)}%`);
    slider.style.setProperty("--hi", `${Math.max(50, at)}%`);
  }
  // the boxes and the sliders show state.x; the box that is being typed into keeps its text
  function showVector(typing = null) {
    state.x.forEach((z, m) => {
      if (boxes[m] !== typing) {
        boxes[m].value = complexText(z, 3);
        boxes[m].classList.remove("is-bad");
      }
      sliders[m].value = String(Math.max(-1, Math.min(1, z[0])));
      fill(sliders[m]);
    });
  }
  function setVector(v, from) {
    state.x = v.map((a) => (Array.isArray(a) ? M.C(a[0], a[1]) : M.C(a)));
    showVector();
    vecButtons.forEach((o) => o.setAttribute("aria-pressed", String(o === from)));
    draw();
  }
  const VEC = {
    e1: () => [1, 0, 0, 0],
    e3: () => [0, 0, 1, 0],
    even: () => [0.5, 0.5, 0.5, 0.5],
    alt: () => [0.5, -0.5, 0.5, -0.5],
    rand: () => {
      const v = Array.from({ length: n }, gauss);
      const s = Math.hypot(...v);
      return v.map((a) => Math.round((a / s) * 100) / 100);
    },
  };
  vecButtons.forEach((b) => b.addEventListener("click", () => setVector(VEC[b.dataset.vec](), b)));
  sliders.forEach((s, m) =>
    s.addEventListener("input", () => {
      state.x[m] = M.C(Number(s.value), state.x[m][1]); // the slider moves the real part, the imaginary part stays
      showVector();
      vecButtons.forEach((o) => o.setAttribute("aria-pressed", "false"));
      draw();
    }),
  );
  const finite = (z) => Number.isFinite(z[0]) && Number.isFinite(z[1]);
  boxes.forEach((box, m) => {
    // a number is taken as it is typed; a list ("1, 0, 0.5i, -1") fills the boxes from x1 when it is done
    box.addEventListener("input", () => {
      vecButtons.forEach((o) => o.setAttribute("aria-pressed", "false"));
      if (/[,;]/.test(box.value)) {
        box.classList.remove("is-bad");
        return;
      }
      const z = M.parse(box.value);
      box.classList.toggle("is-bad", !finite(z));
      if (!finite(z)) return;
      state.x[m] = z;
      showVector(box);
      draw();
    });
    const done = () => {
      const list = M.parseList(box.value);
      if (list) {
        if (list.length > n || !list.every(finite)) {
          box.classList.add("is-bad");
          return;
        }
        state.x = Array.from({ length: n }, (_, k) => (k < list.length ? list[k] : M.C(0)));
        draw();
      }
      if (!box.classList.contains("is-bad")) showVector();
    };
    box.addEventListener("change", done);
    box.addEventListener("keydown", (event) => {
      if (event.key === "Enter") done();
    });
  });

  // an entry of a matrix: its column alone goes in, its row is marked on the way out
  function probe(i, j) {
    state.probe = j;
    dialsOut.forEach((g, m) => g.classList.toggle("is-probe", m === i));
    dialsIn.forEach((g, m) => g.classList.toggle("is-probe", m === j));
    draw();
  }
  function unprobe() {
    if (state.probe === null) return;
    state.probe = null;
    [...dialsIn, ...dialsOut].forEach((g) => g.classList.remove("is-probe"));
    draw();
  }
  [...cells, ...ucells].forEach((cell) => {
    const [i, j] = (cell.dataset.cell || cell.dataset.ucell).split("-").map(Number);
    cell.addEventListener("pointerenter", () => probe(i, j));
    cell.addEventListener("pointerleave", unprobe);
    cell.addEventListener("focus", () => probe(i, j));
    cell.addEventListener("blur", unprobe);
  });

  // a heater and its cell point at each other
  const WHAT = { phi: "the phase between the inputs of its block", theta: "the split of its block", out: "the phase of its output" };
  function point(j, on) {
    heaterNodes[j].classList.toggle("is-pointed", on);
    hcells[j].classList.toggle("is-pointed", on);
    if (!on) {
      tip.hidden = true;
      return;
    }
    const h = D.heaters[j];
    const p = state.shown[j];
    const frame = stage.getBoundingClientRect();
    const box = heaterNodes[j].querySelector(".pg-film").getBoundingClientRect();
    tip.innerHTML = "";
    const b = document.createElement("b");
    b.textContent = `${h.name} · ${Math.sqrt(Math.max(0, p) * 1e-3 * D.R).toFixed(2)} V`;
    const s = document.createElement("span");
    s.textContent = `${p.toFixed(2)} mW, a phase of ${((p / D.P_pi) % 2).toFixed(3)} π: ${WHAT[h.kind]}`;
    tip.append(b, s);
    tip.style.left = `${box.left + box.width / 2 - frame.left + stage.scrollLeft}px`;
    tip.style.top = `${box.top - frame.top}px`;
    tip.hidden = false;
  }
  heaterNodes.forEach((g, j) => {
    g.addEventListener("pointerenter", () => point(j, true));
    g.addEventListener("pointerleave", () => point(j, false));
  });
  hcells.forEach((cell, j) => {
    cell.addEventListener("pointerenter", () => point(j, true));
    cell.addEventListener("pointerleave", () => point(j, false));
  });

  // ---- start: the Hadamard matrix, light into the first input; the heaters ramp up when the band comes into view ----
  const first = presetButtons.find((b) => b.dataset.preset === "hadamard") || presetButtons[0];
  first.setAttribute("aria-pressed", "true");
  state.exact = preset(first.dataset.preset);
  setGrid(state.exact);
  showVector();
  draw();
  if (calm || !("IntersectionObserver" in window)) {
    programNow();
    return;
  }
  const seen = new IntersectionObserver(
    (entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      seen.disconnect();
      programNow();
    },
    { threshold: 0.35 },
  );
  seen.observe(stage);
})();

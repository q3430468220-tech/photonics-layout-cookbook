"""Step 4 - INTERCONNECT and Python: the multiplier as the convolution layer of a network that reads handwritten digits.

A convolution slides a small window over an image and multiplies every patch under it by the same few kernels.  With
a window of 2 x 2 pixels a patch is four numbers, the fields on the four inputs, and four kernels are the four rows of
a 4 x 4 matrix: the multiplier computes all four kernels on one patch at once, and the 49 patches of an 8 x 8 image
one after another.  This is how photonic convolution layers are built.

The digits are those of the UCI repository (scripts/digits.py, CC BY 4.0): 3823 to train, 1797 of other writers to
test, 8 x 8 counts from 0 to 16, used as fields from 0 to 1.  The 49 x 4 outputs go to an electronic layer of
196 x 10 weights and ten biases, one score per digit.  Three sets of kernels, each trained with its layer in numpy:

    Haar          fixed: the average, the edge across, the edge along and the diagonal of the patch.  An orthogonal
                  matrix: every singular value is 1, the attenuators pass everything.  Read coherently, then ReLU.
    learned       the kernels trained with the layer; read coherently, then ReLU
    photodiode    the kernels trained for a plain photodiode: the layer sees |K x|^2, the square law of the detector
                  as the nonlinearity of the network

    1. train each set in numpy on the training digits         -> the accuracy of the electronic network
    2. program each K (step 2), measure it in INTERCONNECT    -> its matrix over the band
    3. run the 1797 test digits through the measured matrix   -> the accuracy of the optical layer, per wavelength;
                                                                 the learned set read by photodiodes, as a check
                                                                 of what the sign is worth

Reading: the multiplier holds a K / s, a a common factor.  A coherent receiver takes Re(e^(-i arg a) T x) s / |a0|:
its reference travels as far as the signal, so the phase of a is removed at every wavelength, while the gain s / |a0|
is calibrated once, at 1.55 um.  A photodiode takes |T x|^2 (s / |a0|)^2.

    python conv_digits.py

Output in 4_convolution/:  convolution.icp (the circuit, without results), convolution.npz, convolution.txt
"""

from __future__ import annotations

import time

import digits
import numpy as np
import svd_interconnect as sx
import svd_model as sm
from svd_common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, SCRATCH, import_lumapi, inputs, step_dir

mm = sm.mm
OUT = step_dir("4_convolution")
LAM_MAX = 1.6
POINTS = 101
SEED = 5
STEPS = 4000  # of Adam, 256 digits each
HAAR = np.array([[1, 1, 1, 1], [1, 1, -1, -1], [1, -1, 1, -1], [1, -1, -1, 1]]) / 2  # rows: average, across, along, diagonal
SETS = (  # name, the read-out the network is trained for, fixed kernels or None
    ("Haar", "relu", HAAR),
    ("learned", "relu", None),
    ("photodiode", "square", None),
)


def patches(x: np.ndarray) -> np.ndarray:
    """(n, 8, 8) -> (n, 49, 4): every 2 x 2 window, stride 1, row by row; its pixels top left, top right, bottom left,
    bottom right go to inputs 1 to 4."""
    return np.stack([x[:, :-1, :-1], x[:, :-1, 1:], x[:, 1:, :-1], x[:, 1:, 1:]], -1).reshape(len(x), 49, 4)


def activate(f: np.ndarray, mode: str) -> np.ndarray:
    return np.maximum(f, 0.0) if mode == "relu" else f**2 if mode == "square" else np.abs(f)


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def train(x: np.ndarray, y: np.ndarray, mode: str, fixed: np.ndarray | None, rng: np.random.Generator):
    """Kernels K (4 x 4), weights W (196 x 10) and biases b (10): softmax of activate(K patches) W + b, by Adam."""
    p = patches(x)
    k = fixed.copy() if fixed is not None else rng.normal(0.0, 0.5, (4, 4))
    w = rng.normal(0.0, 0.05, (196, 10))
    b = np.zeros(10)
    target = np.eye(10)[y]
    params = [k, w, b]
    m1 = [np.zeros_like(q) for q in params]
    m2 = [np.zeros_like(q) for q in params]
    for t in range(1, STEPS + 1):
        pick = rng.integers(0, len(x), 256)
        pp = p[pick]
        f = pp @ k.T
        h = activate(f, mode).reshape(len(pick), 196)
        g = (softmax(h @ w + b) - target[pick]) / len(pick)
        gh = (g @ w.T).reshape(len(pick), 49, 4)
        gf = gh * (f > 0) if mode == "relu" else gh * 2 * f
        grads = (np.einsum("npo,npi->oi", gf, pp) if fixed is None else np.zeros_like(k), h.T @ g + 1e-3 * w, g.sum(0))
        for j, gq in enumerate(grads):
            m1[j] = 0.9 * m1[j] + 0.1 * gq
            m2[j] = 0.999 * m2[j] + 0.001 * gq**2
            params[j] -= 0.03 * (m1[j] / (1 - 0.9**t)) / (np.sqrt(m2[j] / (1 - 0.999**t)) + 1e-8)
    return k, w, b


def scores(features: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    return features.reshape(len(features), -1) @ w + b


def optical(t: np.ndarray, target: np.ndarray, scale: float, x: np.ndarray, reading: str) -> np.ndarray:
    """The outputs of the measured matrix T[lam, out, in] for every patch, as the receiver reads them: (lam, n, 49, 4)."""
    a = np.array([sm.best_factor(t[j], target) for j in range(len(t))])
    a0 = a[len(t) // 2]
    fields = np.einsum("loi,npi->lnpo", t, patches(x)) * (scale / abs(a0))
    if reading == "coherent":
        return (fields * np.exp(-1j * np.angle(a))[:, None, None, None]).real
    return np.abs(fields) ** 2


def confusion(true: np.ndarray, read: np.ndarray) -> np.ndarray:
    m = np.zeros((10, 10), dtype=int)
    np.add.at(m, (true, read), 1)
    return m


def main() -> None:
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    x_train, y_train, x_test, y_test = digits.load()
    x_train, x_test = x_train / 16.0, x_test / 16.0
    y_train, y_test = y_train.astype(int), y_test.astype(int)

    # ---- 1. the electronic networks ----
    nets = []
    for name, mode, fixed in SETS:
        k, w, b = train(x_train, y_train, mode, fixed, rng)
        acc = float(np.mean(np.argmax(scores(activate(patches(x_test) @ k.T, mode), w, b), 1) == y_test))
        nets.append({"name": name, "mode": mode, "k": k, "w": w, "b": b, "electronic": acc})
        print(f"  {name}: electronic {acc:.4f}", flush=True)
    learned = nets[1]
    sign_lost_electronic = float(
        np.mean(np.argmax(scores(np.abs(patches(x_test) @ learned["k"].T), learned["w"], learned["b"]), 1) == y_test)
    )

    # ---- 2. program and measure ----
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = sm.circuit(LAYOUT, d["heater_length"])
    for net in nets:
        net["run"] = sm.program(c, ph, net["k"], ph.lam0)
        print(f"  programmed {net['name']}: error {net['run']['error']:.1e}, {net['run']['powers'].sum():.0f} mW", flush=True)
    sp = sx.write_sparameters(ph, SCRATCH / "coupler.dat")
    lumapi = import_lumapi()
    with lumapi.INTERCONNECT(hide=True) as ic:
        circuit = sx.Multiplier(ic, c, ph, sp, LAM_MAX, POINTS)
        for net in nets:
            circuit.set_sites(mm.site_dn(c, ph, net["run"]["powers"]))
            t, lam = circuit.measure(range(4))
            net["t"] = t[:, :4, :]
            print(f"  INTERCONNECT, {net['name']}: done", flush=True)
        circuit.set_sites(mm.site_dn(c, ph, np.zeros(len(c.heaters))))
        ic.switchtodesign()
        ic.save(str(OUT / "convolution.icp"))
    i0 = POINTS // 2
    if abs(lam[i0] - ph.lam0) > 1e-9:
        raise RuntimeError(f"the middle sample is at {lam[i0]} um, not at {ph.lam0} um")

    # ---- 3. the test digits through the measured matrices ----
    for net in nets:
        target, scale = net["run"]["target"], net["run"]["scale"]
        reading = "coherent" if net["mode"] == "relu" else "power"
        out = optical(net["t"], target, scale, x_test, reading)  # (lam, n, 49, 4)
        h = np.maximum(out, 0.0) if reading == "coherent" else out
        read = np.argmax(np.einsum("lnf,fc->lnc", h.reshape(POINTS, len(x_test), 196), net["w"]) + net["b"], axis=2)
        net["accuracy"] = np.mean(read == y_test[None, :], axis=1)
        net["confusion"] = confusion(y_test, read[i0])
        net["confusion_electronic"] = confusion(
            y_test, np.argmax(scores(activate(patches(x_test) @ net["k"].T, net["mode"]), net["w"], net["b"]), 1)
        )
        net["error"] = np.array([sm.relative_error(net["t"][j], target) for j in range(POINTS)])
        net["fidelity"] = np.array([sm.fidelity(net["t"][j], target) for j in range(POINTS)])
        net["model_difference"] = float(np.max(np.abs(net["t"] - sm.matrix(c, ph, lam, net["run"]["powers"]))))
        ok = net["accuracy"] >= net["electronic"] - 0.01
        lo = hi = i0
        while lo > 0 and ok[lo - 1]:
            lo -= 1
        while hi < POINTS - 1 and ok[hi + 1]:
            hi += 1
        net["band"] = (float(lam[lo]), float(lam[hi])) if ok[i0] else (0.0, 0.0)
        net["read"] = read[i0]
    lost = optical(learned["t"], learned["run"]["target"], learned["run"]["scale"], x_test, "power")  # |field|^2
    read_lost = np.argmax(
        np.einsum("lnf,fc->lnc", np.sqrt(lost).reshape(POINTS, len(x_test), 196), learned["w"]) + learned["b"], axis=2
    )
    sign_lost = np.mean(read_lost == y_test[None, :], axis=1)

    lines = [
        "INTERCONNECT, Lumerical 2025 R1, and the Python model (svd_model.py): the 4 x 4 multiplier of",
        "  devices/svd_multiplier_builder.py as the convolution layer of a network that reads handwritten digits;",
        f"  {digits.CITATION}",
        f"  {len(x_train)} digits to train, {len(x_test)} of other writers to test; kernels of 2 x 2, stride 1, 49 patches per digit;",
        f"  analyser {lam[0]:.4f} to {lam[-1]:.4f} um, {POINTS} points; run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: with the multiplier as its convolution layer, the network reads {100 * nets[2]['accuracy'][i0]:.1f} % of the test digits "
        f"right at 1.55 um when its kernels were trained for photodiodes, {100 * nets[0]['accuracy'][i0]:.1f} % with the fixed Haar "
        f"kernels and {100 * nets[1]['accuracy'][i0]:.1f} % with learned kernels read coherently, each as its electronic network does "
        f"to within {100 * max(abs(n['accuracy'][i0] - n['electronic']) for n in nets):.1f} points.  The learned kernels read by "
        f"photodiodes, the sign lost, fall to {100 * sign_lost[i0]:.1f} %.",
        "",
        "a. the three networks",
        "  kernels      read-out              electronic  optical at 1.55 um  within 1 point of electronic     heaters (mW)  error of K (INTERCONNECT)  singular values of K / s",
    ]
    for n in nets:
        lo, hi = n["band"]
        lines.append(
            f"  {n['name']:11s}  {'coherent, then ReLU' if n['mode'] == 'relu' else '|field|^2, photodiode':20s}  {100 * n['electronic']:9.1f} %"
            f"  {100 * n['accuracy'][i0]:16.1f} %  {lo * 1000:.0f} to {hi * 1000:.0f} nm ({1000 * (hi - lo):.0f} nm)        "
            f"{n['run']['powers'].sum():12.0f}  {n['error'][i0]:25.1e}  {' '.join(f'{s:.3f}' for s in n['run']['sigma'])}"
        )
    lines += [
        f"  the learned kernels read by photodiodes (|field| in place of ReLU): electronic {100 * sign_lost_electronic:.1f} %, optical {100 * sign_lost[i0]:.1f} %",
        f"  the model against INTERCONNECT, all three, all wavelengths: largest difference of an entry {max(n['model_difference'] for n in nets):.1e}",
        "",
        "b. the kernels, as 2 x 2 windows (top left, top right / bottom left, bottom right), rows of K",
    ]
    for n in nets:
        lines.append(f"  {n['name']}:  " + "   ".join(f"[{r[0]:+.2f} {r[1]:+.2f} / {r[2]:+.2f} {r[3]:+.2f}]" for r in n["k"]))
    lines += ["", "c. the accuracy against the wavelength, INTERCONNECT (%)",
              "  lambda (um)  " + "  ".join(f"{n['name']:>10s}" for n in nets) + "   learned, sign lost"]  # fmt: skip
    for j in range(0, POINTS, 10):
        lines.append(
            f"  {lam[j]:11.4f}  " + "  ".join(f"{100 * n['accuracy'][j]:10.1f}" for n in nets) + f"   {100 * sign_lost[j]:18.1f}"
        )
    best = nets[2]
    lines += [
        "",
        f"d. {best['name']} kernels at 1.55 um, optical: true digit (rows) against the digit read (columns)",
        "       " + "".join(f"{k:6d}" for k in range(10)),
    ]
    for k, row in enumerate(best["confusion"]):
        lines.append(f"  {k:3d}  " + "".join(f"{v:6d}" for v in row))
    text = "\n".join(lines)
    print(text)
    (OUT / "convolution.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "convolution.npz", names=np.array([n["name"] for n in nets]), modes=np.array([n["mode"] for n in nets]), lam=lam,
        K=np.array([n["k"] for n in nets]), W=np.array([n["w"] for n in nets]), b=np.array([n["b"] for n in nets]),
        scale=np.array([n["run"]["scale"] for n in nets]), sigma=np.array([n["run"]["sigma"] for n in nets]),
        powers_mW=np.array([n["run"]["powers"] for n in nets]), heater_names=np.array([h["name"] for h in c.heaters]),
        T_interconnect=np.array([n["t"] for n in nets]), error=np.array([n["error"] for n in nets]),
        fidelity=np.array([n["fidelity"] for n in nets]), electronic=np.array([n["electronic"] for n in nets]),
        accuracy=np.array([n["accuracy"] for n in nets]), band_um=np.array([n["band"] for n in nets]),
        confusion=np.array([n["confusion"] for n in nets]), confusion_electronic=np.array([n["confusion_electronic"] for n in nets]),
        read=np.array([n["read"] for n in nets]), sign_lost=sign_lost, sign_lost_electronic=sign_lost_electronic,
        model_difference=max(n["model_difference"] for n in nets), P_pi_mW=ph.P_pi, seed=SEED,
    )  # fmt: skip


if __name__ == "__main__":
    main()

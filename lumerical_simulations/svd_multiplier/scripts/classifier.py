"""Step 3 - INTERCONNECT and Python: the multiplier as the layer of a neural network, on the smallest images there are.

An image of 2 x 2 pixels is four numbers, the powers on the four inputs.  Four classes: the top row lit, the bottom
row, the left column, the right column; every image has its own brightness and noise on every pixel, and no pixel is
below zero (light has no negative power).  A softmax regression, logits = W x with no bias, learns W in numpy; the
multiplier is programmed to W (step 2) and its matrix, from INTERCONNECT, takes the place of W.

    1. train W on 2000 images, test on 1000 others                  -> the accuracy of the electronic layer
    2. program W, measure the matrix in INTERCONNECT over the band    -> the accuracy of the optical layer, as the
                                                                         wavelength moves
    3. two ways of reading the outputs:
         coherent    the real part of the field, against a reference that travels as far as the signal: W x itself
         power       |field|^2 on a plain photodiode: the sign is lost, and top and bottom (whose logits are opposite)
                     look the same
       and a second W, trained for the photodiode (logits = (W x)^2), programmed and measured the same way

    python classifier.py

Output in 3_classifier/:  classifier.icp (the circuit, without results), classifier.npz, classifier.txt
"""

from __future__ import annotations

import time

import numpy as np
import svd_interconnect as sx
import svd_model as sm
from svd_common import COUPLER_PORT_EXTRA, LAYOUT, LOSS_DB_CM, SCRATCH, import_lumapi, inputs, step_dir

mm = sm.mm
OUT = step_dir("3_classifier")
LAM_MAX = 1.6
POINTS = 101
SEED = 11
TRAIN, TEST = 2000, 1000
NOISE = 0.2  # standard deviation of the noise on every pixel, against a brightness of 0.6 to 1
CLASSES = ("top", "bottom", "left", "right")
# pixels in the order top left, top right, bottom left, bottom right: input k of the multiplier is pixel k
PATTERNS = np.array([[1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 1, 0], [0, 1, 0, 1]], dtype=float)


def images(count: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    labels = rng.integers(0, 4, count)
    bright = rng.uniform(0.6, 1.0, count)
    x = bright[:, None] * PATTERNS[labels] + rng.normal(0.0, NOISE, (count, 4))
    return np.clip(x, 0.0, None), labels


def softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def train(
    x: np.ndarray, labels: np.ndarray, power: bool, rng: np.random.Generator, steps: int = 4000, rate: float = 0.3
) -> np.ndarray:
    """Softmax regression by gradient descent, no bias.  power: the logits are (W x)^2, what a photodiode reads."""
    y = np.eye(4)[labels]
    w = rng.normal(0.0, 0.3, (4, 4))
    for _ in range(steps):
        f = x @ w.T  # (count, class)
        z = f**2 if power else f
        g = (softmax(z) - y) / len(x)  # d loss / d z
        if power:
            g = g * 2 * f
        w -= rate * (g.T @ x + 1e-4 * w)
    return w


def accuracy(scores: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean(np.argmax(scores, axis=-1) == labels))


def coherent(t: np.ndarray, target: np.ndarray, x: np.ndarray) -> np.ndarray:
    """The real part of the output fields, with the common phase of the matrix removed: the reference of the receiver
    travels as far as the signal.  t: (lam, out, in); returns (lam, image, out)."""
    a = np.array([sm.best_factor(t[j], target) for j in range(len(t))])
    fields = np.einsum("loi,ni->lno", t, x)
    return (fields * np.exp(-1j * np.angle(a))[:, None, None]).real


def power(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.abs(np.einsum("loi,ni->lno", t, x)) ** 2


def band(lam: np.ndarray, ok: np.ndarray, lam0: float) -> tuple[float, float]:
    i0 = int(np.argmin(np.abs(lam - lam0)))
    if not ok[i0]:
        return 0.0, 0.0
    lo = hi = i0
    while lo > 0 and ok[lo - 1]:
        lo -= 1
    while hi < len(lam) - 1 and ok[hi + 1]:
        hi += 1
    return float(lam[lo]), float(lam[hi])


def main() -> None:
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    x_train, l_train = images(TRAIN, rng)
    x_test, l_test = images(TEST, rng)

    # ---- 1. the electronic layer ----
    weights = {"coherent": train(x_train, l_train, False, rng), "power": train(x_train, l_train, True, rng)}
    electronic = {
        "coherent": accuracy(x_test @ weights["coherent"].T, l_test),
        "power": accuracy((x_test @ weights["power"].T) ** 2, l_test),
        "sign lost": accuracy(np.abs(x_test @ weights["coherent"].T), l_test),  # W for the logits, read by a photodiode
    }
    print("  electronic: " + ", ".join(f"{k} {v:.3f}" for k, v in electronic.items()), flush=True)

    # ---- 2. program both, measure in INTERCONNECT ----
    d = inputs()
    ph = mm.Physics(d, LOSS_DB_CM, COUPLER_PORT_EXTRA)
    c = sm.circuit(LAYOUT, d["heater_length"])
    runs = {}
    for name, w in weights.items():
        runs[name] = sm.program(c, ph, w, ph.lam0)
        print(f"  programmed W ({name}): error {runs[name]['error']:.1e}, {runs[name]['powers'].sum():.0f} mW", flush=True)
    sp = sx.write_sparameters(ph, SCRATCH / "coupler.dat")
    lumapi = import_lumapi()
    measured = {}
    with lumapi.INTERCONNECT(hide=True) as ic:
        circuit = sx.Multiplier(ic, c, ph, sp, LAM_MAX, POINTS)
        for name in weights:
            circuit.set_sites(mm.site_dn(c, ph, runs[name]["powers"]))
            t, lam = circuit.measure(range(4))
            measured[name] = t[:, :4, :]
            print(f"  INTERCONNECT, W ({name}): done", flush=True)
        circuit.set_sites(mm.site_dn(c, ph, np.zeros(len(c.heaters))))
        ic.switchtodesign()
        ic.save(str(OUT / "classifier.icp"))
    i0 = POINTS // 2
    if abs(lam[i0] - ph.lam0) > 1e-9:
        raise RuntimeError(f"the middle sample is at {lam[i0]} um, not at {ph.lam0} um")

    # ---- 3. the accuracy of the optical layer, read two ways, against the wavelength ----
    tc, tp = measured["coherent"], measured["power"]
    acc = {
        "coherent": np.array([accuracy(s, l_test) for s in coherent(tc, runs["coherent"]["target"], x_test)]),
        "sign lost": np.array([accuracy(s, l_test) for s in power(tc, x_test)]),
        "power": np.array([accuracy(s, l_test) for s in power(tp, x_test)]),
    }
    err = {
        name: np.array([sm.relative_error(measured[name][j], runs[name]["target"]) for j in range(POINTS)]) for name in weights
    }
    agree = {}  # how many test images the optical layer classifies as the electronic one does, at 1.55 um
    agree["coherent"] = float(np.mean(np.argmax(coherent(tc, runs["coherent"]["target"], x_test)[i0], 1)
                                      == np.argmax(x_test @ weights["coherent"].T, 1)))  # fmt: skip
    agree["power"] = float(np.mean(np.argmax(power(tp, x_test)[i0], 1) == np.argmax((x_test @ weights["power"].T) ** 2, 1)))
    bands = {k: band(lam, v >= electronic[k] - 0.01, ph.lam0) for k, v in acc.items() if k != "sign lost"}
    diff = max(float(np.max(np.abs(measured[n] - sm.matrix(c, ph, lam, runs[n]["powers"])))) for n in weights)
    confusion = np.zeros((4, 4), dtype=int)  # the sign lost, at 1.55 um: true class, read class
    for true, read in zip(l_test, np.argmax(power(tc, x_test)[i0], 1), strict=True):
        confusion[true, read] += 1

    w_text = lambda w: [" ".join(f"{v:+6.2f}" for v in row) for row in w]  # noqa: E731
    lines = [
        "INTERCONNECT, Lumerical 2025 R1, and the Python model (svd_model.py): the 4 x 4 multiplier of",
        f"  devices/svd_multiplier_builder.py as a layer that classifies 2 x 2 images; {TRAIN} images to train, {TEST} to test, noise {NOISE}",
        f"  analyser {lam[0]:.4f} to {lam[-1]:.4f} um, {POINTS} points; run time {(time.time() - t0) / 60:.1f} min",
        "",
        f"answer: read coherently, the optical layer classifies {100 * acc['coherent'][i0]:.1f} % of the test images right at 1.55 um, "
        f"as the electronic layer does ({100 * electronic['coherent']:.1f} %), and keeps within 1 % of it over "
        f"{1000 * (bands['coherent'][1] - bands['coherent'][0]):.0f} nm.  Read by plain photodiodes, the same W falls to "
        f"{100 * acc['sign lost'][i0]:.1f} %: the sign is lost, and top and bottom, left and right, look alike.  A W trained for "
        f"the photodiode gets back to {100 * acc['power'][i0]:.1f} %.",
        "",
        "a. the electronic layer",
        f"  W trained for the logits W x: test accuracy {100 * electronic['coherent']:.1f} %;  read as |W x| (the sign lost): "
        f"{100 * electronic['sign lost']:.1f} %",
        f"  W trained for the photodiode, logits (W x)^2: {100 * electronic['power']:.1f} %",
        "  W (logits)                       W (photodiode)          (rows: top, bottom, left, right; columns: the pixels)",
    ]
    for a, b in zip(w_text(weights["coherent"]), w_text(weights["power"]), strict=True):
        lines.append(f"  {a}      {b}")
    lines += [
        "",
        "b. programmed and measured, at 1.55 um",
        "  W              error (model)  error (INTERCONNECT)  heaters (mW)  same class as electronic  singular values of W / s",
    ]
    for name in weights:
        r = runs[name]
        lines.append(f"  {name:13s}  {r['error']:13.1e}  {err[name][i0]:20.1e}  {r['powers'].sum():12.0f}  {100 * agree[name]:23.1f} %  "
                     f"{' '.join(f'{s:.3f}' for s in r['sigma'])}")  # fmt: skip
    lines += [
        f"  the model against INTERCONNECT, both W, all wavelengths: largest difference of an entry {diff:.1e}",
        "",
        "c. W for the logits, read by photodiodes at 1.55 um: true class (rows) against the class read (columns)",
        "              " + "".join(f"{k:>8s}" for k in CLASSES),
    ]
    for k, row in zip(CLASSES, confusion, strict=True):
        lines.append(f"  {k:10s}  " + "".join(f"{v:8d}" for v in row))
    lines += [
        "",
        "d. the accuracy against the wavelength (%)",
        "  lambda (um)  coherent  sign lost  photodiode W   error of W (coherent)",
    ]
    for j in range(0, POINTS, 10):
        lines.append(f"  {lam[j]:11.4f}  {100 * acc['coherent'][j]:8.1f}  {100 * acc['sign lost'][j]:9.1f}  {100 * acc['power'][j]:12.1f}"
                     f"   {err['coherent'][j]:20.2e}")  # fmt: skip
    for k, (lo, hi) in bands.items():
        lines.append(
            f"  {k}: within 1 % of the electronic layer from {lo * 1000:.0f} to {hi * 1000:.0f} nm ({1000 * (hi - lo):.0f} nm)"
        )
    text = "\n".join(lines)
    print(text)
    (OUT / "classifier.txt").write_text(text + "\n", encoding="utf-8")
    np.savez_compressed(
        OUT / "classifier.npz", lam=lam, x_test=x_test, labels_test=l_test, W=weights["coherent"], W_power=weights["power"],
        electronic=np.array([electronic["coherent"], electronic["sign lost"], electronic["power"]]),
        accuracy_coherent=acc["coherent"], accuracy_sign_lost=acc["sign lost"], accuracy_power=acc["power"],
        error_coherent=err["coherent"], error_power=err["power"], T_coherent=tc, T_power=tp,
        powers_mW=runs["coherent"]["powers"], powers_power_mW=runs["power"]["powers"], confusion_sign_lost=confusion,
        band_um=np.array([bands["coherent"], bands["power"]]), model_difference=diff, P_pi_mW=ph.P_pi,
    )  # fmt: skip


if __name__ == "__main__":
    main()

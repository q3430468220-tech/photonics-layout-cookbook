// photonics-layout-cookbook: read a digit with the multiplier of step 4 (website/fx/digits.py writes the data).
//
//   the digit   strokes drawn with the pointer are brought to the form of the data: scaled to fill the 32 x 32 grid
//               (the larger of their width and height), centred, drawn 4 pixels wide; each block of 4 x 4 pixels
//               counts its dark pixels, 0 to 16.  A test digit comes as it is.
//   the light   the 49 windows of 2 x 2 pixels, one after another, through the matrix that INTERCONNECT measured at
//               the chosen wavelength; a coherent receiver takes Re(e^(-i phase) T x) gain, a photodiode |T x|^2 gain^2.
//   the answer  the electronic layer of step 4 on the 196 values: ten scores and their softmax.
//
// DigitMath holds what has no page around it; website/tests/test_digits.py runs it in node against the chapter.
const DigitMath = (() => {
  "use strict";
  // the 49 windows of an 8 x 8 image (64 values, row by row): top left, top right, bottom left, bottom right
  function patches(img) {
    const out = [];
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) out.push([img[r * 8 + c], img[r * 8 + c + 1], img[(r + 1) * 8 + c], img[(r + 1) * 8 + c + 1]]);
    }
    return out;
  }
  // the four outputs of one window, as the receiver reads them
  function window4(set, k, x, signLost) {
    const [re, im] = set.T[k];
    const out = [];
    const c = Math.cos(set.phase[k]);
    const s = Math.sin(set.phase[k]);
    for (let o = 0; o < 4; o++) {
      let a = 0;
      let b = 0;
      for (let i = 0; i < 4; i++) {
        a += re[o][i] * x[i];
        b += im[o][i] * x[i];
      }
      a *= set.gain;
      b *= set.gain;
      if (set.mode === "square") out.push(a * a + b * b);
      else if (signLost) out.push(Math.hypot(a, b));
      else out.push(Math.max(0, a * c + b * s)); // the real part of (a + i b) e^(-i phase), then the ReLU
    }
    return out;
  }
  // the whole digit: the 49 x 4 values, the ten scores and their softmax
  function read(set, k, counts, signLost) {
    const img = counts.map((v) => v / 16);
    const values = patches(img).map((x) => window4(set, k, x, signLost));
    const flat = values.flat();
    const scores = set.b.slice();
    for (let f = 0; f < flat.length; f++) {
      if (!flat[f]) continue;
      const row = set.W[f];
      for (let d = 0; d < 10; d++) scores[d] += flat[f] * row[d];
    }
    const top = Math.max(...scores);
    const e = scores.map((v) => Math.exp(v - top));
    const sum = e.reduce((a, b) => a + b, 0);
    const p = e.map((v) => v / sum);
    return { values, scores, p, digit: p.indexOf(Math.max(...p)) };
  }
  // strokes (lists of [x, y] in any units) -> where they go on the 32 x 32 grid: scaled to fill it, centred
  function fit(strokes, pen = 4) {
    const pts = strokes.flat();
    if (!pts.length) return [];
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const size = Math.max(x1 - x0, y1 - y0, 1e-9);
    const k = (32 - pen) / size;
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    return strokes.map((s) => s.map(([x, y]) => [16 + (x - cx) * k, 16 + (y - cy) * k]));
  }
  // a 32 x 32 bitmap (1024 values, 0 or 1, row by row) -> 8 x 8 counts of its blocks of 4 x 4
  function blocks(bits) {
    const out = new Array(64).fill(0);
    for (let y = 0; y < 32; y++) for (let x = 0; x < 32; x++) out[(y >> 2) * 8 + (x >> 2)] += bits[y * 32 + x] ? 1 : 0;
    return out;
  }
  return { patches, window4, read, fit, blocks };
})();
if (typeof module !== "undefined") module.exports = DigitMath;

(() => {
  "use strict";
  if (typeof document === "undefined") return;
  const root = document.querySelector("[data-dg]");
  const raw = document.getElementById("dg-data");
  if (!root || !raw) return;
  const data = JSON.parse(raw.textContent);
  const calm = Boolean(window.COOKBOOK_CALM) || matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (sel) => root.querySelector(sel);
  const $$ = (sel) => Array.from(root.querySelectorAll(sel));
  const pad = $("[data-pad]");
  const ctx = pad.getContext("2d");
  const hint = $("[data-hint]");
  const seen = $("[data-seen]");
  const scan = $("[data-scan]");
  const lamInput = $("[data-lam]");
  const signBox = $("[data-sign-lost]");
  const readBox = $("[data-read-box]");
  const chipSvg = $(".dg-chip-svg");
  let set = data.sets.find((s) => s.key === "photodiode") || data.sets[0];
  let k = data.at;
  let strokes = [];
  let counts = null; // the 8 x 8 counts of the digit on the pad
  let shown = null; // the test digit on the pad, when it is one
  let playing = 0;
  const nextExample = {};

  // ---- colours: orange negative, white zero, blue positive; light from dark to cyan going white ----
  const signed = (v) => (v >= 0 ? [255 - 205 * v, 255 - 135 * v, 255 - 25 * v] : [255 + 20 * v, 255 + 120 * v, 255 + 160 * v]);
  const light = (v) => [10 + 60 * v + 185 * v * v, 16 + 215 * v + 24 * v * v, 40 + 215 * v];
  function paint(canvas, w, h, values, colour) {
    const c = canvas.getContext("2d");
    const img = c.createImageData(w, h);
    values.forEach((v, i) => {
      const [r, g, b] = colour(v);
      img.data.set([r, g, b, 255], i * 4);
    });
    c.putImageData(img, 0, 0);
  }

  // ---- the pad ----
  function drawPad() {
    const w = pad.width;
    ctx.clearRect(0, 0, w, w);
    if (shown) {
      const s = w / 8;
      shown.forEach((v, i) => {
        ctx.fillStyle = `rgba(235, 244, 255, ${(v / 16).toFixed(3)})`;
        ctx.fillRect((i % 8) * s, Math.floor(i / 8) * s, s + 0.5, s + 0.5);
      });
    }
    ctx.strokeStyle = "#eaf3ff";
    ctx.lineWidth = w / 15;
    ctx.lineCap = ctx.lineJoin = "round";
    for (const s of strokes) {
      ctx.beginPath();
      s.forEach(([x, y], i) => (i ? ctx.lineTo(x * w, y * w) : ctx.moveTo(x * w, y * w)));
      if (s.length === 1) ctx.lineTo(s[0][0] * w + 0.1, s[0][1] * w);
      ctx.stroke();
    }
    hint.hidden = Boolean(shown || strokes.length);
  }
  // the strokes on a grid of 32 x 32, as the data was made, and its blocks
  const grid = document.createElement("canvas");
  grid.width = grid.height = 32;
  function countsOfStrokes() {
    const g = grid.getContext("2d");
    g.clearRect(0, 0, 32, 32);
    g.strokeStyle = "#000";
    g.lineWidth = 4;
    g.lineCap = g.lineJoin = "round";
    for (const s of DigitMath.fit(strokes)) {
      g.beginPath();
      s.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
      if (s.length === 1) g.lineTo(s[0][0] + 0.01, s[0][1]);
      g.stroke();
    }
    const a = g.getImageData(0, 0, 32, 32).data;
    const bits = [];
    for (let i = 0; i < 1024; i++) bits.push(a[i * 4 + 3] > 127 ? 1 : 0);
    return DigitMath.blocks(bits);
  }
  let drawing = null;
  const at = (event) => {
    const box = pad.getBoundingClientRect();
    return [(event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height];
  };
  pad.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    pad.setPointerCapture(event.pointerId);
    if (shown) {
      shown = null;
      strokes = [];
    }
    drawing = [at(event)];
    strokes.push(drawing);
    drawPad();
  });
  pad.addEventListener("pointermove", (event) => {
    if (!drawing) return;
    drawing.push(at(event));
    drawPad();
  });
  const finish = () => {
    if (!drawing) return;
    drawing = null;
    counts = countsOfStrokes();
    run(true);
  };
  pad.addEventListener("pointerup", finish);
  pad.addEventListener("pointercancel", finish);
  $("[data-clear]").addEventListener("click", () => {
    strokes = [];
    shown = null;
    counts = null;
    drawPad();
    run(false);
  });
  $$("[data-example]").forEach((b) =>
    b.addEventListener("click", () => {
      const d = Number(b.dataset.example);
      const all = data.examples.filter((e) => e.digit === d);
      const j = (nextExample[d] = ((nextExample[d] ?? -1) + 1) % all.length);
      shown = all[j].x;
      strokes = [];
      counts = shown.slice();
      drawPad();
      run(true);
    }),
  );

  // ---- the kernels, the read-out, the wavelength ----
  function showSet() {
    $$("[data-set]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.set === set.key)));
    $("[data-set-note]").textContent = set.note;
    const lim = Math.max(...set.K.flat().map(Math.abs));
    $$("[data-kernel]").forEach((c) => {
      const m = Number(c.dataset.kernel);
      paint(c, 2, 2, set.K[m].map((v) => v / lim), signed);
    });
    readBox.hidden = set.key !== "learned";
    if (readBox.hidden) signBox.checked = false;
    showConfusion();
  }
  $$("[data-set]").forEach((b) =>
    b.addEventListener("click", () => {
      set = data.sets.find((s) => s.key === b.dataset.set);
      showSet();
      run(true);
    }),
  );
  signBox.addEventListener("change", () => run(true));
  lamInput.addEventListener("input", () => {
    k = Number(lamInput.value);
    $("[data-lam-value]").textContent = data.lam[k].toFixed(1);
    run(false);
  });
  $("[data-play]").addEventListener("click", () => run(true));

  // ---- the confusion of all test digits, from the chapter ----
  function showConfusion() {
    const box = $("[data-confusion]");
    const m = set.confusion;
    const top = Math.max(...m.flat());
    paint(box, 10, 10, m.flat().map((v) => Math.sqrt(v / top)), light);
  }

  // ---- the light ----
  function showOutputs(result, upto) {
    const lit = upto >= 49 ? 48 : upto;
    const top = Math.max(1e-9, ...result.values.flat());
    $$("[data-map]").forEach((c) => {
      const m = Number(c.dataset.map);
      paint(c, 7, 7, result.values.map((v, p) => (p <= upto ? v[m] / top : 0)), light);
    });
    const r = Math.floor(lit / 7);
    const c = lit % 7;
    const img = (counts || new Array(64).fill(0)).map((v) => v / 16);
    paint(scan, 8, 8, img.map((v, i) => {
      const inside = Math.floor(i / 8) - r >= 0 && Math.floor(i / 8) - r <= 1 && (i % 8) - c >= 0 && (i % 8) - c <= 1;
      return inside ? 0.25 + 0.75 * v : 0.06 + 0.45 * v;
    }), (v) => [40 + 200 * v, 60 + 190 * v, 110 + 145 * v]); // fmt: skip
    root.style.setProperty("--win-x", String(c));
    root.style.setProperty("--win-y", String(r));
    const x = DigitMath.patches(img)[lit];
    $$("[data-in]").forEach((li) => {
      const m = Number(li.dataset.in);
      li.style.setProperty("--v", x[m].toFixed(3));
      li.querySelector("span").textContent = x[m].toFixed(2);
    });
    $$("[data-out]").forEach((li) => {
      const m = Number(li.dataset.out);
      li.style.setProperty("--v", (result.values[lit][m] / top).toFixed(3));
      li.querySelector("span").textContent = result.values[lit][m].toFixed(2);
    });
    if (chipSvg) chipSvg.style.setProperty("--o", (x.reduce((a, b) => a + b, 0) / 4).toFixed(3));
  }
  function showAnswer(result) {
    $("[data-answer]").textContent = counts ? String(result.digit) : "–";
    $("[data-sure]").textContent = counts ? `${Math.round(100 * result.p[result.digit])} % sure` : "";
    $$("[data-bar]").forEach((li) => {
      const d = Number(li.dataset.bar);
      li.style.setProperty("--p", counts ? result.p[d].toFixed(4) : "0");
      li.classList.toggle("is-top", Boolean(counts) && d === result.digit);
      li.querySelector("small").textContent = counts ? `${Math.round(100 * result.p[d])} %` : "–";
    });
    const lost = set.key === "learned" && signBox.checked;
    const acc = lost ? data.signLost[k] : set.accuracy[k];
    $("[data-of]").innerHTML =
      `At ${data.lam[k].toFixed(1)} nm the chapter reads <b>${(100 * acc).toFixed(1)} %</b> of the ${data.tests} test digits right ` +
      `with these kernels${lost ? ", read by photodiodes" : ""}; the electronic network, ${(100 * set.electronic).toFixed(1)} %.`;
    root.classList.toggle("is-empty", !counts);
  }
  function run(animate) {
    cancelAnimationFrame(playing);
    const result = DigitMath.read(set, k, counts || new Array(64).fill(0), set.key === "learned" && signBox.checked);
    paint(seen, 8, 8, (counts || new Array(64).fill(0)).map((v) => v / 16), (v) => [20 + 215 * v, 26 + 218 * v, 44 + 211 * v]);
    if (!animate || calm || !counts) {
      showOutputs(result, 49);
      showAnswer(result);
      return;
    }
    root.classList.add("is-running");
    showAnswer({ ...result, p: new Array(10).fill(0), digit: 0 });
    $("[data-answer]").textContent = "…";
    $("[data-sure]").textContent = "";
    const start = performance.now();
    const step = (now) => {
      const upto = Math.max(0, Math.min(48, Math.floor((now - start) / 42))); // a frame can be stamped before the start
      showOutputs(result, upto);
      if (upto < 48) playing = requestAnimationFrame(step);
      else {
        root.classList.remove("is-running");
        showAnswer(result);
      }
    };
    playing = requestAnimationFrame(step);
  }

  // a test digit to begin with, so that the band is never empty
  showSet();
  const first = data.examples.find((e) => e.digit === 3) || data.examples[0];
  shown = first.x;
  counts = shown.slice();
  drawPad();
  let started = false;
  const begin = () => {
    if (started) return;
    started = true;
    run(true);
  };
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => entries.some((e) => e.isIntersecting) && begin(), { threshold: 0.3 }).observe(root);
    run(false);
  } else begin();
})();

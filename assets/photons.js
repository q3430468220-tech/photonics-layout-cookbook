// photonics-layout-cookbook: single photons through the directional coupler of the home page, and the two supermodes
// that carry them.  Everything comes from assets/data/photons.js (fx/photons.py), loaded when the plate comes near:
//
//   a photon     enters at the lower left at a random time (a laser's photons arrive at random, with no memory, so
//                the waits are exponential), runs along the waveguides, and inside the coupler is in both at once:
//                its brightness in the upper one is the FDTD share of power there, in the lower one the rest.
//   a detector   at the end of each output.  When a photon arrives, one of them clicks, with the probabilities of the
//                S-parameters (cross, through; the rest is lost).  The half that was not found goes out at once.
//   the counts   approach cross and through as the photons add up; the error shown is the binomial one, about 1/√N.
//   the modes    the even and the odd supermode of the straight section, and the photon's cross-section where the
//                marked photon is (or where the pointer is): even + e^(iΔφ) odd, with Δφ read from the FDTD share.
//                The dial shows Δφ as the angle between the two modes.
//
// Nothing runs while the plate is off the screen.  With reduced motion no photon runs; the modes show the end of
// the straight section.
(() => {
  "use strict";
  const plate = document.querySelector("[data-photons]");
  const near = window.COOKBOOK_NEAR;
  if (!plate || !near) return;
  const calm = Boolean(window.COOKBOOK_CALM);
  const here = document.currentScript ? document.currentScript.src : "";
  const stage = plate.querySelector(".field-stage");
  const field = plate.querySelector("canvas.field");
  const layer = plate.querySelector(".photon-layer");
  const dets = { cross: plate.querySelector('[data-det="cross"]'), through: plate.querySelector('[data-det="through"]') };
  const tally = plate.querySelector("[data-tally]");
  const tallyN = plate.querySelector("[data-tally-n]");
  const tallyEst = plate.querySelector("[data-tally-est]");
  const tallyFill = plate.querySelector("[data-tally-fill]");
  const modeRead = plate.querySelector("[data-mode-read]");
  const dialRead = plate.querySelector("[data-dial-read]");
  const dial = plate.querySelector("[data-dial]");
  const panels = [...plate.querySelectorAll("canvas[data-mode]")];
  if (!stage || !layer || !field) return;
  if (tally) tally.hidden = false; // with a script the tally is part of the caption from the start: nothing moves later
  if (tally && calm) tally.querySelector("p").textContent = "With reduced motion the photons do not run.";

  const TRAVEL = 3.6; // seconds from the left edge to the detectors
  const WAIT = 0.85; // mean wait between two photons, seconds, after a dead time of DEAD
  const DEAD = 0.18;
  const CYAN = [94, 231, 245];
  const PINK = [255, 143, 216];
  const GROUND = [7, 8, 22];
  const STOPS = [[3, 4, 10], [10, 53, 88], [15, 147, 168], [240, 180, 60], [255, 244, 210]]; // the field colours of home.js
  const fieldColour = (t) => {
    const position = Math.min(1, Math.max(0, t)) * (STOPS.length - 1);
    const low = Math.min(STOPS.length - 2, Math.floor(position));
    const part = position - low;
    return [0, 1, 2].map((k) => STOPS[low][k] * (1 - part) + STOPS[low + 1][k] * part);
  };

  let D = null; // the data
  let ctx = null;
  let geo = null; // the mapping from micrometres to the pixels of the stage
  const photons = [];
  const counts = { cross: 0, through: 0, lost: 0 };
  let clock = 0;
  let nextAt = 0.4;
  let visible = false;
  let frame = 0;
  let last = 0;
  let pointerX = null; // micrometres, while the pointer is over the field
  let tracked = null; // the x of the cross-section, micrometres
  let shown = NaN; // the phase drawn in the photon's panel
  let modes = null; // the two modes as numbers, once their pictures are read

  // ---- the data, as a value along x ----------------------------------------------------------------------------
  const along = (values, x) => {
    const [x0, x1, n] = D.x;
    const f = Math.min(n - 1, Math.max(0, ((x - x0) / (x1 - x0)) * (n - 1)));
    const i = Math.min(n - 2, Math.floor(f));
    return values[i] + (values[i + 1] - values[i]) * (f - i);
  };
  const share = (x) => Math.min(1, Math.max(0, along(D.share, x)));
  const lowerY = (x) => along(D.centre, x); // the centre of the lower waveguide; the upper one is its mirror image
  const phaseAt = (x) => along(D.phase, x);

  // ---- the place of the field on the screen: the canvas covers its box (object-fit: cover), centred -------------
  function layout() {
    const box = stage.getBoundingClientRect();
    const W = box.width;
    const H = field.getBoundingClientRect().height || box.height;
    if (!W || !H) return false;
    const [iw, ih] = D.image;
    const [x0, x1] = D.span.x;
    const [y0, y1] = D.span.y;
    const s = Math.max(W / iw, H / ih);
    const ox = (W - iw * s) / 2;
    const oy = (H - ih * s) / 2;
    const kx = (iw * s) / (x1 - x0);
    const ky = (ih * s) / (y1 - y0);
    const px = (x) => ox + (x - x0) * kx;
    const py = (y) => oy + (y1 - y) * ky;
    const seen = [x0 - ox / kx, x0 + (W - ox) / kx]; // the part of the field on the screen, micrometres
    // On a narrow screen only the straight section is on the screen, where the two waveguides lie a few pixels apart:
    // the photons are found at the right edge and counted in the tally only.  With reduced motion nothing is counted.
    const bare = W < 720 || calm;
    for (const element of Object.values(dets)) if (element) element.hidden = bare;
    // room for a detector right of its waveguide: its own width, the gap before it and a margin to the edge
    const badge = bare ? 0.6 * kx : Math.max(...Object.values(dets).map((element) => (element ? element.offsetWidth : 0))) + 34;
    const xd = Math.min(16.8, seen[1] - badge / kx);
    const start = Math.max(x0, seen[0]) - 0.6;
    geo = { W, H, kx, ky, px, py, seen, xd, start, speed: (xd - start) / TRAVEL };
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    layer.width = Math.round(W * ratio);
    layer.height = Math.round(H * ratio);
    layer.style.width = W + "px";
    layer.style.height = H + "px";
    ctx = layer.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    for (const [name, element] of Object.entries(dets)) {
      if (!element || bare) continue;
      const y = name === "cross" ? -lowerY(xd) : lowerY(xd);
      element.style.left = px(xd) + 10 + "px";
      element.style.top = py(y) + "px";
      element.classList.add("is-placed");
    }
    return true;
  }

  // ---- drawing ---------------------------------------------------------------------------------------------------
  // a photon's packet in one waveguide: an elongated glow with a white core; weight is its share of the photon
  function packet(x, y, weight) {
    if (weight < 0.012) return;
    const a = Math.pow(weight, 0.55);
    const cx = geo.px(x);
    const cy = geo.py(y);
    const ry = Math.max(6, 0.5 * geo.ky);
    const rx = Math.max(12, 0.8 * geo.kx);
    // a wide, faint halo first, then the packet
    const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, 2.6 * ry);
    halo.addColorStop(0, `rgba(94,231,245,${0.22 * a})`);
    halo.addColorStop(1, "rgba(94,231,245,0)");
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(cx, cy, 2.6 * ry, 0, 2 * Math.PI);
    ctx.fill();
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(rx / ry, 1);
    const glow = ctx.createRadialGradient(0, 0, 0, 0, 0, ry);
    glow.addColorStop(0, `rgba(255,255,255,${a})`);
    glow.addColorStop(0.18, `rgba(235,253,255,${0.95 * a})`);
    glow.addColorStop(0.45, `rgba(120,236,250,${0.5 * a})`);
    glow.addColorStop(1, "rgba(94,231,245,0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(0, 0, ry, 0, 2 * Math.PI);
    ctx.fill();
    ctx.restore();
    // the trail: where the packet has just been
    const tail = ctx.createLinearGradient(cx - 3.2 * rx, cy, cx, cy);
    tail.addColorStop(0, "rgba(94,231,245,0)");
    tail.addColorStop(1, `rgba(190,248,255,${0.45 * a})`);
    ctx.strokeStyle = tail;
    ctx.lineWidth = Math.max(1.2, 0.09 * geo.ky);
    ctx.beginPath();
    ctx.moveTo(cx - 3.2 * rx, cy);
    ctx.lineTo(cx, cy);
    ctx.stroke();
  }

  // one photon in two places: a faint thread between its two packets
  function thread(x, yUp, yLow, a) {
    const cx = geo.px(x);
    ctx.save();
    ctx.setLineDash([2, 4]);
    ctx.strokeStyle = `rgba(210,240,255,${0.32 * a})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx, geo.py(yUp));
    ctx.lineTo(cx, geo.py(yLow));
    ctx.stroke();
    ctx.restore();
  }

  // a click: a ring that opens at the detector
  function click(x, y, age) {
    const t = age / 0.6;
    if (t >= 1) return;
    const cx = geo.px(x);
    const cy = geo.py(y);
    ctx.strokeStyle = `rgba(255,255,255,${0.9 * (1 - t)})`;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(cx, cy, 4 + 22 * t, 0, 2 * Math.PI);
    ctx.stroke();
    const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, 14);
    core.addColorStop(0, `rgba(255,255,255,${1 - t})`);
    core.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, 14, 0, 2 * Math.PI);
    ctx.fill();
  }

  // the place of the cross-section: a thin line across both waveguides
  function slice(x) {
    const cx = geo.px(x);
    const top = geo.py(1.15);
    const bottom = geo.py(-1.15);
    const line = ctx.createLinearGradient(cx, top, cx, bottom);
    line.addColorStop(0, "rgba(255,255,255,0)");
    line.addColorStop(0.5, "rgba(255,255,255,0.55)");
    line.addColorStop(1, "rgba(255,255,255,0)");
    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx + 0.5, top);
    ctx.lineTo(cx + 0.5, bottom);
    ctx.stroke();
  }

  function draw() {
    ctx.clearRect(0, 0, geo.W, geo.H);
    ctx.globalCompositeOperation = "lighter";
    if (tracked !== null && Math.abs(tracked) <= D.straight + 1e-6) slice(tracked);
    for (const p of photons) {
      if (!p.found) {
        const w = share(p.x);
        const yLow = lowerY(p.x);
        packet(p.x, yLow, 1 - w);
        packet(p.x, -yLow, w);
        if (w > 0.04 && w < 0.96) thread(p.x, -yLow, yLow, Math.min(w, 1 - w) * 2);
      } else if (p.found !== "lost") {
        const y = p.found === "cross" ? -lowerY(geo.xd) : lowerY(geo.xd);
        click(geo.xd, y, clock - p.at);
      }
    }
    ctx.globalCompositeOperation = "source-over";
  }

  // ---- the photons -------------------------------------------------------------------------------------------------
  function detect(p) {
    const r = Math.random();
    p.found = r < D.cross ? "cross" : r < D.cross + D.through ? "through" : "lost";
    p.at = clock;
    counts[p.found] += 1;
    const element = dets[p.found];
    if (element) {
      element.querySelector("b").textContent = String(counts[p.found]);
      element.classList.remove("is-hit");
      void element.offsetWidth; // start the flash again
      element.classList.add("is-hit");
    }
    const n = counts.cross + counts.through + counts.lost;
    const estimate = counts.cross / n;
    const error = Math.sqrt(Math.max(estimate * (1 - estimate), 0.25 / n) / n);
    if (tallyN) tallyN.textContent = String(n);
    if (tallyEst) tallyEst.textContent = `cross ${estimate.toFixed(n < 100 ? 2 : 3)} ± ${error.toFixed(n < 100 ? 2 : 3)}`;
    if (tallyFill) tallyFill.style.width = (100 * estimate).toFixed(2) + "%";
  }

  function step(dt) {
    clock += dt;
    if (clock >= nextAt) {
      photons.push({ x: geo.start, found: null, at: 0 });
      nextAt = clock + DEAD + -Math.log(1 - Math.random()) * WAIT;
    }
    for (const p of photons) {
      if (p.found) continue;
      p.x += geo.speed * dt;
      if (p.x >= geo.xd) detect(p);
    }
    for (let i = photons.length - 1; i >= 0; i--) if (photons[i].found && clock - photons[i].at > 0.7) photons.splice(i, 1);
    // the cross-section follows the pointer, or the leading photon that is still in the straight section
    if (pointerX !== null) tracked = pointerX;
    else {
      let lead = null;
      for (const p of photons) if (!p.found && p.x <= D.straight && p.x >= -D.straight && (lead === null || p.x > lead)) lead = p.x;
      if (lead !== null) tracked = lead;
    }
  }

  function tick(now) {
    frame = 0;
    if (!visible || document.hidden) return;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
    last = now;
    step(dt);
    draw();
    modesAt(tracked === null ? -D.straight : tracked);
    frame = requestAnimationFrame(tick);
  }
  function run(on) {
    visible = on;
    if (calm) return;
    if (on && !frame) {
      last = 0;
      frame = requestAnimationFrame(tick);
    }
  }

  // ---- the supermodes ----------------------------------------------------------------------------------------------
  // The pictures hold |E| of each mode over the larger peak; the grey level times the peak is the field of unit power.
  // The odd mode gets its sign back from y: positive in the lower core, negative in the upper one.
  function readModes(done) {
    const m = D.modes;
    const [ny, nz] = m.size;
    const take = (src, then) => {
      const image = new Image();
      image.onload = () => {
        const c = document.createElement("canvas");
        c.width = ny;
        c.height = nz;
        const g = c.getContext("2d");
        g.drawImage(image, 0, 0);
        const px = g.getImageData(0, 0, ny, nz).data;
        const out = new Float32Array(ny * nz);
        for (let i = 0; i < ny * nz; i++) out[i] = (px[4 * i] / 255) * m.peak;
        then(out);
      };
      image.src = src;
    };
    take(m.even, (even) =>
      take(m.odd, (odd) => {
        for (let j = 0; j < ny; j++) {
          const y = m.y[0] + ((m.y[1] - m.y[0]) * j) / (ny - 1);
          const sign = -Math.tanh(y / m.sign);
          for (let k = 0; k < nz; k++) odd[k * ny + j] *= sign;
        }
        let top = 0;
        for (let i = 0; i < ny * nz; i++) top = Math.max(top, (even[i] + odd[i]) ** 2, (even[i] - odd[i]) ** 2);
        modes = { even, odd, ny, nz, top, peak: m.peak };
        done();
      }),
    );
  }

  // a picture of ny by nz pixels, drawn into a canvas of the panel's size, with the outlines of the two cores
  const scratch = document.createElement("canvas");
  function paint(canvas, fill) {
    const { ny, nz } = modes;
    scratch.width = ny;
    scratch.height = nz;
    const g = scratch.getContext("2d");
    const image = g.createImageData(ny, nz);
    for (let i = 0; i < ny * nz; i++) {
      const [r, gr, b] = fill(i);
      image.data[4 * i] = r;
      image.data[4 * i + 1] = gr;
      image.data[4 * i + 2] = b;
      image.data[4 * i + 3] = 255;
    }
    g.putImageData(image, 0, 0);
    const box = canvas.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const W = Math.max(1, Math.round(box.width * ratio));
    const H = Math.max(1, Math.round(box.height * ratio));
    if (canvas.width !== W || canvas.height !== H) {
      canvas.width = W;
      canvas.height = H;
    }
    const c = canvas.getContext("2d");
    c.imageSmoothingEnabled = true;
    c.imageSmoothingQuality = "high";
    c.drawImage(scratch, 0, 0, W, H);
    const m = D.modes;
    const X = (y) => ((y - m.y[0]) / (m.y[1] - m.y[0])) * W;
    const Y = (z) => ((m.z[1] - z) / (m.z[1] - m.z[0])) * H;
    c.strokeStyle = "rgba(255,255,255,0.42)";
    c.lineWidth = ratio;
    c.fillStyle = "rgba(255,255,255,0.42)";
    c.font = `${10 * ratio}px "JetBrains Mono", Consolas, monospace`;
    c.textAlign = "center";
    c.textBaseline = "top";
    // seen along the waveguides: the lower waveguide of the field above is the core on the left (y < 0)
    for (const [side, name] of [[-1, "lower"], [1, "upper"]]) {
      const y0 = side * m.core.yc - m.core.w / 2;
      c.strokeRect(X(y0), Y(m.core.z0 + m.core.h), X(y0 + m.core.w) - X(y0), Y(m.core.z0) - Y(m.core.z0 + m.core.h));
      c.fillText(name, X(side * m.core.yc), Y(m.core.z0) + 7 * ratio);
    }
  }
  const signed = (v, peak) => {
    const b = Math.pow(Math.min(1, Math.abs(v) / peak), 0.75);
    const c = v >= 0 ? CYAN : PINK;
    return [0, 1, 2].map((k) => GROUND[k] + (c[k] - GROUND[k]) * b);
  };
  function drawStill() {
    if (!modes) return;
    for (const canvas of panels) {
      if (canvas.dataset.mode === "even") paint(canvas, (i) => signed(modes.even[i], modes.peak));
      if (canvas.dataset.mode === "odd") paint(canvas, (i) => signed(modes.odd[i], modes.peak));
    }
    shown = NaN;
  }

  // the photon's cross-section and the dial, at x
  function modesAt(x) {
    if (!modes) return;
    const inside = Math.max(-D.straight, Math.min(D.straight, x));
    const phase = phaseAt(inside);
    if (Math.abs(phase - shown) < 0.004) return;
    shown = phase;
    const now = panels.find((canvas) => canvas.dataset.mode === "now");
    const cos = Math.cos(phase);
    const { even, odd, top } = modes;
    if (now) paint(now, (i) => fieldColour(Math.pow((even[i] ** 2 + odd[i] ** 2 + 2 * even[i] * odd[i] * cos) / top, 0.5 * 0.78)));
    const up = share(inside);
    if (modeRead) modeRead.textContent = `x = ${inside.toFixed(1).replace("-", "−")} µm, ${Math.round(100 * up)} % in the upper core`;
    if (dialRead) dialRead.textContent = phase.toFixed(2);
    if (dial) drawDial(phase);
  }

  const NS = "http://www.w3.org/2000/svg";
  let dialParts = null;
  function drawDial(phase) {
    if (!dialParts) {
      const make = (name, attributes) => {
        const element = document.createElementNS(NS, name);
        for (const [k, v] of Object.entries(attributes)) element.setAttribute(k, v);
        dial.appendChild(element);
        return element;
      };
      make("circle", { r: 46, class: "dial-ring" });
      for (let k = 0; k < 12; k++) {
        const a = (k * Math.PI) / 6;
        make("line", { x1: 46 * Math.cos(a), y1: 46 * Math.sin(a), x2: 41 * Math.cos(a), y2: 41 * Math.sin(a), class: "dial-tick" });
      }
      dialParts = {
        arc: make("path", { class: "dial-arc" }),
        even: make("line", { x1: 0, y1: 0, x2: 38, y2: 0, class: "dial-even" }),
        evenTip: make("circle", { cx: 38, cy: 0, r: 3.2, class: "dial-even-tip" }),
        odd: make("line", { x1: 0, y1: 0, class: "dial-odd" }),
        oddTip: make("circle", { r: 3.2, class: "dial-odd-tip" }),
      };
      make("circle", { r: 2.5, class: "dial-hub" });
    }
    const x = 38 * Math.cos(phase);
    const y = 38 * Math.sin(phase); // y down: the odd mode turns clockwise as it falls behind
    dialParts.odd.setAttribute("x2", x.toFixed(2));
    dialParts.odd.setAttribute("y2", y.toFixed(2));
    dialParts.oddTip.setAttribute("cx", x.toFixed(2));
    dialParts.oddTip.setAttribute("cy", y.toFixed(2));
    const r = 22;
    const large = phase > Math.PI ? 1 : 0;
    dialParts.arc.setAttribute("d", `M${r} 0A${r} ${r} 0 ${large} 1 ${(r * Math.cos(phase)).toFixed(2)} ${(r * Math.sin(phase)).toFixed(2)}`);
  }

  // ---- start -------------------------------------------------------------------------------------------------------
  function start(data) {
    D = data;
    const ready = () => {
      if (!layout()) return;
      drawStill();
      modesAt(tracked === null ? (calm ? D.straight : -D.straight) : tracked);
      if (calm) draw();
    };
    readModes(() => {
      ready();
      if (calm) return;
      new IntersectionObserver((entries) => run(entries.some((entry) => entry.isIntersecting))).observe(stage);
    });
    if ("ResizeObserver" in window) {
      let width = 0;
      new ResizeObserver(() => {
        const w = stage.getBoundingClientRect().width;
        if (w && w !== width) {
          width = w;
          if (modes) ready();
        }
      }).observe(stage);
    }
    stage.addEventListener("pointermove", (event) => {
      if (!geo || event.pointerType === "touch") return;
      const box = stage.getBoundingClientRect();
      const x = geo.seen[0] + ((event.clientX - box.left) / geo.kx);
      pointerX = Math.max(-D.straight, Math.min(D.straight, x));
      if (calm) {
        tracked = pointerX;
        draw();
        modesAt(tracked);
      }
    });
    stage.addEventListener("pointerleave", () => {
      pointerX = null;
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && visible) run(true);
    });
  }

  let loading = false;
  function load() {
    if (loading) return;
    loading = true;
    const url = new URL("data/photons.js", here || window.location.href);
    url.search = new URL(here || window.location.href).search; // the version of the page
    const script = document.createElement("script");
    script.src = url.href;
    script.onload = () => window.COOKBOOK_PHOTONS && start(window.COOKBOOK_PHOTONS);
    script.onerror = () => {
      loading = false;
    };
    document.head.appendChild(script);
  }
  near.whenNear(plate, (now) => now && load(), "700px");
})();

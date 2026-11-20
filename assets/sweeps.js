// photonics-layout-cookbook: the figures of the chapters that the reader can move. Five figures, one for each chapter
// that has a sweep: the taper, the bend radius, the straight section of the coupler, the multimode section, and the
// bias of the ring. Each figure is drawn at the size it has on the screen, so that its lettering keeps its size on a
// phone. Its control stands on the runs of the kept results and on nothing between them; the coupler law is a fit
// that is drawn as a line and named as one. The readout is shown; a screen reader hears it on release or on a key.
(() => {
  "use strict";
  const near = window.COOKBOOK_NEAR; // near.js is loaded before this script by the page
  if (!near) return;
  const NS = "http://www.w3.org/2000/svg";
  const svg = (name, attributes = {}, text) => {
    const element = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const clamp = near.clamp;
  const minus = (text) => text.replace("-", "−");
  const signed = (value, digits) => minus((value >= 0 ? "+" : "") + value.toFixed(digits));
  const pct = (value) => (value * 100).toFixed(1);
  const box = { left: 50, right: 14, top: 26, bottom: 40 }; // the unit of the axis has a line of its own above the plot
  const CHAR = 6.9; // the advance of a character of the mono face at 11 px (measured 6.55 with its spacing), with a margin

  // the index of the value nearest to a value, in a list of values
  const nearest = (values, value) => {
    let k = 0;
    for (let i = 1; i < values.length; i++) if (Math.abs(values[i] - value) < Math.abs(values[k] - value)) k = i;
    return k;
  };

  // the axes, the grid and the labels of a plot inside the box; returns how the values map to pixels
  function frame(g, W, H, o) {
    const plotW = W - box.left - box.right;
    const plotH = H - box.top - box.bottom;
    const px = (v) => box.left + ((v - o.x[0]) / (o.x[1] - o.x[0])) * plotW;
    const py = (v) => H - box.bottom - ((v - o.y[0]) / (o.y[1] - o.y[0])) * plotH;
    const at = (x) => o.x[0] + ((x - box.left) / plotW) * (o.x[1] - o.x[0]); // pixel to value, for the pointer
    for (const v of o.yTicks) {
      g.append(svg("path", { class: v === o.y[0] ? "chart-axis" : "chart-grid", d: `M${box.left} ${py(v)}H${W - box.right}` }));
      g.append(svg("text", { class: "chart-text", x: box.left - 8, y: py(v) + 4, "text-anchor": "end" }, o.yText(v)));
    }
    for (const v of o.xTicks) {
      g.append(svg("path", { class: "chart-axis", d: `M${px(v)} ${py(o.y[0])}v4` }));
      g.append(svg("text", { class: "chart-text", x: px(v), y: py(o.y[0]) + 17, "text-anchor": "middle" }, o.xText(v)));
    }
    g.append(svg("text", { class: "chart-text", x: W - box.right, y: H - 4, "text-anchor": "end" }, o.xLabel));
    g.append(svg("text", { class: "chart-text", x: 0, y: 11 }, o.yLabel));
    return { px, py, at, W, H, blocks: [] }; // blocks: the points that a label must not cover (the curves, the band)
  }

  // a path through the points (xs, ys) of the plot; its points are kept as blocks for the labels
  function trace(p, xs, ys) {
    const points = xs.map((x, i) => [p.px(x), p.py(ys[i])]);
    for (const point of points) p.blocks.push(point);
    return points.map((point, i) => (i ? "L" : "M") + point[0].toFixed(1) + " " + point[1].toFixed(1)).join("");
  }

  // a label inside the plot, off the curves, the band and the other labels: the first of its places where it covers
  // no block. A label may have several lines (text as a list); the places give the position of its first line.
  function note(g, p, text, places) {
    const lines = Array.isArray(text) ? text : [text];
    const width = Math.max(...lines.map((line) => line.length)) * CHAR;
    const height = 13 + (lines.length - 1) * 12;
    const boxOf = (place) => {
      const x0 = place.anchor === "end" ? place.x - width : place.x;
      return { x0, x1: x0 + width, y0: place.y - 10, y1: place.y - 10 + height };
    };
    const inside = (b) => b.x0 >= box.left && b.x1 <= p.W - box.right && b.y0 >= box.top && b.y1 <= p.H - box.bottom;
    const clear = (b) => p.blocks.every(([x, y]) => x < b.x0 - 5 || x > b.x1 + 5 || y < b.y0 - 5 || y > b.y1 + 5);
    const choice = places.find((place) => inside(boxOf(place)) && clear(boxOf(place))) || places[0];
    const placed = boxOf(choice);
    for (let x = placed.x0; x <= placed.x1; x += 3) for (let y = placed.y0; y <= placed.y1; y += 3) p.blocks.push([x, y]);
    const element = svg("text", { class: "chart-note", x: choice.x, y: choice.y, "text-anchor": choice.anchor });
    lines.forEach((line, i) => element.append(svg("tspan", { x: choice.x, dy: i ? 12 : 0 }, line)));
    g.append(element);
  }

  // a vertical line at the value of the design, with its name beside it, placed off the curves
  function design(g, p, o, value, text) {
    g.append(svg("path", { class: "chart-design", d: `M${p.px(value)} ${p.py(o.y[0])}V${p.py(o.y[1])}` }));
    const top = box.top + 14;
    const low = p.H - box.bottom - 8;
    note(g, p, text, [
      { x: p.px(value) + 7, y: low, anchor: "start" },
      { x: p.px(value) - 7, y: low, anchor: "end" },
      { x: p.px(value) + 7, y: top, anchor: "start" },
      { x: p.px(value) - 7, y: top, anchor: "end" },
    ]);
  }
  const dot = (g, p, x, y, title) => {
    const element = svg("circle", { class: "chart-dot", cx: p.px(x), cy: p.py(y), r: 4 });
    if (title) element.append(svg("title", {}, title));
    p.blocks.push([p.px(x), p.py(y)]);
    g.append(element);
  };
  const keys = (...pairs) => pairs.map(([kind, text]) => `<span><i class="key key-${kind}"></i>${text}</span>`).join(" ");

  // ---- one kind of figure: the control's places, and how the plot and the readout are drawn -----------------
  const kinds = {
    // the power in TE0 of the wide waveguide against the taper length, one run per length (step 2, EME)
    taper(d) {
      return {
        xs: d.x,
        label: (i) => `${d.x[i]} µm`,
        draw(g, W, H) {
          const o = {
            x: [d.x[0], d.x[d.x.length - 1]], y: [0.4, 1], xTicks: [1, 10, 20, 30, 40], yTicks: [0.4, 0.6, 0.8, 1],
            yText: (v) => String(Math.round(v * 100)), xText: (v) => String(v),
            xLabel: "taper length (µm)", yLabel: "power in TE0, %",
          };
          const p = frame(g, W, H, o);
          const target = svg("path", { class: "chart-target", d: `M${p.px(o.x[0])} ${p.py(d.target)}H${p.px(o.x[1])}` });
          g.append(target);
          const check = svg("path", { class: "chart-check", d: trace(p, d.x, d.check) });
          const cross = svg("path", { class: "chart-cross", d: trace(p, d.x, d.T) });
          g.append(check, cross);
          note(g, p, `${Math.round(d.target * 100)} % from ${d.reached} µm`, [
            { x: p.px(o.x[1]) - 6, y: p.py(d.target) + 15, anchor: "end" },
            { x: p.px(o.x[1]) - 6, y: p.py(d.target) - 6, anchor: "end" },
          ]);
          design(g, p, o, d.design, `device, ${d.design} µm`);
          const mark = svg("circle", { class: "chart-mark", r: 4.5 });
          g.append(mark);
          return {
            at: p.at,
            update(i) {
              mark.setAttribute("cx", p.px(d.x[i]));
              mark.setAttribute("cy", p.py(d.T[i]));
              const loss = -10 * Math.log10(d.T[i]);
              return `length ${d.x[i].toFixed(1)} µm <span>${pct(d.T[i])} % in TE0</span> <span>loss ${loss.toFixed(2)} dB</span>`;
            },
          };
        },
      };
    },

    // the loss of a 90 degree bend against its radius, one run per radius (step 1, MODE)
    rib(d) {
      return {
        xs: d.x,
        label: (i) => `${d.x[i]} µm`,
        draw(g, W, H) {
          const o = {
            x: [d.x[0], d.x[d.x.length - 1]], y: [0, 0.3], xTicks: [5, 10, 15, 20], yTicks: [0, 0.1, 0.2, 0.3],
            yText: (v) => v.toFixed(1), xText: (v) => String(v),
            xLabel: "bend radius (µm)", yLabel: "loss of a 90° bend, dB",
          };
          const p = frame(g, W, H, o);
          const cross = svg("path", { class: "chart-cross", d: trace(p, d.x, d.loss) });
          g.append(cross);
          d.x.forEach((x, i) => dot(g, p, x, d.loss[i], `MODE: radius ${x} µm, ${d.loss[i].toPrecision(2)} dB per 90°`));
          design(g, p, o, d.design, `design, ${d.design} µm`);
          const mark = svg("circle", { class: "chart-mark", r: 4.5 });
          g.append(mark);
          return {
            at: p.at,
            update(i) {
              mark.setAttribute("cx", p.px(d.x[i]));
              mark.setAttribute("cy", p.py(d.loss[i]));
              return `radius ${d.x[i]} µm <span>${d.loss[i].toPrecision(2)} dB per 90°</span> <span>mode moves ${Math.round(d.shift[i])} nm</span>`;
            },
          };
        },
      };
    },

    // the fraction of the light that crosses against the straight section: the four runs, and the law of step 2
    // (a fit), drawn as a line over the same range; the control stands on the runs only
    coupler(d) {
      const fit = (L) => Math.sin((Math.PI / 2) * ((L + d.l_bends) / d.l_pi)) ** 2;
      return {
        xs: d.x,
        label: (i) => `${d.x[i]} µm`,
        draw(g, W, H) {
          const o = {
            x: d.range, y: [0, 1], xTicks: d.x, yTicks: [0, 0.5, 1],
            yText: (v) => v.toFixed(1), xText: (v) => String(v),
            xLabel: "length of the straight section (µm)", yLabel: "fraction of the light",
          };
          const p = frame(g, W, H, o);
          const grid = Array.from({ length: 361 }, (_, i) => (i / 360) * (o.x[1] - o.x[0]) + o.x[0]);
          g.append(svg("path", { class: "chart-target", d: `M${p.px(o.x[0])} ${p.py(0.5)}H${p.px(o.x[1])}` }));
          g.append(svg("path", { class: "chart-through", d: trace(p, grid, grid.map((L) => 1 - fit(L))) }));
          g.append(svg("path", { class: "chart-cross", d: trace(p, grid, grid.map(fit)) }));
          d.x.forEach((x, i) => dot(g, p, x, d.fraction[i], `FDTD: ${x} µm, ${pct(d.fraction[i])} % cross`));
          design(g, p, o, d.design, `50:50, ${d.design.toFixed(2)} µm`);
          const mark = svg("circle", { class: "chart-mark", r: 4.5 });
          g.append(mark);
          return {
            at: p.at,
            update(i) {
              mark.setAttribute("cx", p.px(d.x[i]));
              mark.setAttribute("cy", p.py(d.fraction[i]));
              return `L = ${d.x[i].toFixed(1)} µm <span>${pct(d.fraction[i])} % cross, FDTD</span> <span>fit ${pct(fit(d.x[i]))} % cross</span>`;
            },
          };
        },
      };
    },

    // the power into the two outputs against the length of the multimode section, one run per length (step 1, EME)
    mmi(d) {
      return {
        xs: d.x,
        label: (i) => `${d.x[i]} µm`,
        draw(g, W, H) {
          const o = {
            x: [d.x[0], d.x[d.x.length - 1]], y: [0, 1.3], xTicks: [2, 4, 6, 8, 10, 12, 14], yTicks: [0, 0.5, 1],
            yText: (v) => (v * 100).toFixed(0), xText: (v) => String(v),
            xLabel: "length of the multimode section (µm)", yLabel: "power into the outputs, %",
          };
          const p = frame(g, W, H, o);
          const [low, high] = d.band;
          const band = { x: p.px(low), y: p.py(1.05), w: p.px(high) - p.px(low), h: p.py(0) - p.py(1.05) };
          for (let x = band.x; x <= band.x + band.w; x += 2) p.blocks.push([x, band.y], [x, band.y + band.h]);
          g.append(svg("rect", { class: "chart-band", x: band.x, y: band.y, width: band.w, height: band.h }));
          const check = svg("path", { class: "chart-check", d: trace(p, d.x, d.check) });
          const total = svg("path", { class: "chart-cross", d: trace(p, d.x, d.total) });
          g.append(check, total);
          for (let y = p.py(o.y[0]); y >= p.py(o.y[1]); y -= 3) p.blocks.push([p.px(d.design), y]); // the device line
          note(g, p, ["within 0.1 dB,", `${low} to ${high} µm`], [
            { x: p.px(d.design) + 7, y: box.top + 14, anchor: "start" },
            { x: box.left + 6, y: box.top + 14, anchor: "start" },
            { x: W - box.right - 6, y: box.top + 14, anchor: "end" },
            { x: box.left + 6, y: H - box.bottom - 8, anchor: "start" },
            { x: W - box.right - 6, y: H - box.bottom - 8, anchor: "end" },
          ]);
          design(g, p, o, d.design, `device, ${d.design} µm`);
          const mark = svg("circle", { class: "chart-mark", r: 4.5 });
          g.append(mark);
          return {
            at: p.at,
            update(i) {
              mark.setAttribute("cx", p.px(d.x[i]));
              mark.setAttribute("cy", p.py(d.total[i]));
              const loss = -10 * Math.log10(d.total[i]);
              return `length ${d.x[i].toFixed(1)} µm <span>${pct(d.total[i])} % into the outputs</span> <span>loss ${loss.toFixed(2)} dB</span>`;
            },
          };
        },
      };
    },

    // the transmission of the ring against the shift of its resonance, one curve for each simulated bias (step 6)
    ring(d) {
      return {
        xs: d.shift,
        label: (i) => `${d.volts[i].toFixed(2)} V reverse bias`,
        draw(g, W, H) {
          const o = {
            x: [d.x[0], d.x[d.x.length - 1]], y: [-50, 0], xTicks: [-40, 0, 40, 80], yTicks: [0, -10, -20, -30, -40, -50],
            yText: (v) => minus(String(v)), xText: (v) => minus(String(v)),
            xLabel: "shift from the resonance at 0 V (pm)", yLabel: "transmission, dB",
          };
          const p = frame(g, W, H, o);
          d.dB.forEach((row, k) => {
            if (k !== 0) g.append(svg("path", { class: "chart-context", d: trace(p, d.x, row) }));
          });
          g.append(svg("path", { class: "chart-design", d: `M${p.px(0)} ${p.py(o.y[0])}V${p.py(o.y[1])}` }));
          note(g, p, "0 V, design", [
            { x: p.px(0) - 8, y: box.top + 14, anchor: "end" },
            { x: p.px(0) + 8, y: box.top + 14, anchor: "start" },
            { x: p.px(0) - 8, y: p.py(-44), anchor: "end" },
            { x: p.px(0) + 8, y: p.py(-44), anchor: "start" },
          ]);
          const chosen = svg("path", { class: "chart-cross" });
          const mark = svg("circle", { class: "chart-mark", r: 4.5 });
          g.append(chosen, mark);
          return {
            at: p.at,
            update(i) {
              chosen.setAttribute("d", trace({ ...p, blocks: [] }, d.x, d.dB[i]));
              mark.setAttribute("cx", p.px(d.shift[i]));
              mark.setAttribute("cy", p.py(d.dip[i]));
              const shift = d.shift[i] === 0 ? "0.0" : signed(d.shift[i], 1);
              return `bias ${d.volts[i].toFixed(2)} V <span>resonance ${shift} pm</span> <span>dip ${minus(d.dip[i].toFixed(1))} dB</span>`;
            },
          };
        },
      };
    },
  };

  // ---- one figure: its control, its chart drawn when it nears the screen, and the pointer on the chart --------
  function mount(figure) {
    const data = JSON.parse(figure.querySelector('script[type="application/json"]').textContent);
    const make = kinds[data.kind];
    const element = figure.querySelector(".toy-chart");
    const input = figure.querySelector("input");
    const read = figure.querySelector(".toy-read");
    const say = figure.querySelector(".toy-say");
    if (!make || !element || !input || !read) return;
    const spec = make(data);
    const count = spec.xs.length;
    let index = nearest(spec.xs, data.design);
    let plot = null;
    let width = 0;
    let origin = 0; // where the chart starts on the screen, measured when it is drawn
    let queued = 0; // the pointer moves the control once per animation frame
    let lastX = 0;
    let dragging = false; // a drag announces nothing until it is released

    const show = () => {
      if (plot) read.innerHTML = plot.update(index);
    };
    const announce = () => {
      if (say) say.textContent = read.textContent.replace(/\s+/g, " ").trim();
    };
    const set = (value) => {
      index = clamp(Math.round(value), 0, count - 1);
      input.value = String(index);
      input.setAttribute("aria-valuetext", spec.label(index));
      show();
    };
    const render = () => {
      const rect = element.getBoundingClientRect();
      const w = Math.round(rect.width);
      if (!w || w === width) return;
      width = w;
      origin = rect.left;
      const h = Math.round(clamp(w * 0.4, 220, 340));
      element.setAttribute("viewBox", `0 0 ${w} ${h}`);
      element.replaceChildren();
      plot = spec.draw(element, w, h);
      show();
    };

    // the control: the slider, the keyboard and the touch of a phone all move it
    input.max = String(count - 1);
    input.value = String(index);
    input.setAttribute("aria-valuetext", spec.label(index));
    input.addEventListener("pointerdown", () => {
      dragging = true;
    });
    input.addEventListener("input", () => {
      set(Number(input.value));
      if (!dragging) announce(); // a key: each step is announced
    });

    // a mouse drags the control along the chart; a finger on the chart scrolls the page
    const pick = () => {
      queued = 0;
      if (plot) set(nearest(spec.xs, plot.at(lastX)));
    };
    const move = (event) => {
      lastX = event.clientX - origin;
      if (!queued) queued = requestAnimationFrame(pick);
    };
    const end = () => {
      element.removeEventListener("pointermove", move);
      if (dragging) {
        dragging = false;
        announce(); // a release is announced once
      }
    };
    element.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== "mouse" || !plot) return;
      dragging = true;
      origin = element.getBoundingClientRect().left;
      try {
        element.setPointerCapture(event.pointerId); // the moves go on to this chart even off its edge
      } catch {
        // a pointer that the browser does not know: the moves still reach the chart while the mouse is over it
      }
      lastX = event.clientX - origin;
      set(nearest(spec.xs, plot.at(lastX)));
      element.addEventListener("pointermove", move);
    });
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);

    // drawn when the figure is near the screen; again whenever its width changes
    near.whenNear(
      element,
      (on) => {
        if (!on) return;
        render();
        if ("ResizeObserver" in window && !figure.dataset.measured) {
          figure.dataset.measured = "1";
          new ResizeObserver(render).observe(element);
        }
      },
      "400px",
    );
  }

  for (const figure of document.querySelectorAll("[data-sweep]")) mount(figure);
})();

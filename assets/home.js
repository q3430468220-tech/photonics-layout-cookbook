// photonics-layout-cookbook: the moving parts of the home page and of the device library.
// The wafer that tilts under the pointer and names its dies, the fields drawn from the FDTD results,
// the coupler law with a movable length, and the resonance of the ring against the bias.
(() => {
  "use strict";
  const calm = Boolean(window.COOKBOOK_CALM);
  const data = window.COOKBOOK || null;
  const NS = "http://www.w3.org/2000/svg";
  const svg = (name, attributes = {}, text) => {
    const element = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  };
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const minus = (text) => text.replace("-", "−");

  // ---- the heading of the first screen runs behind the wafer and comes out on it in outline --------------------
  // The wafer lies above the end of the heading and hides it.  A copy of the heading in outline lies above
  // the wafer; it is shown only inside the ellipse that the tilted wafer covers on the screen.
  //
  // That ellipse is computed, not measured: the browser reports the box around the tilted square, which is
  // larger than the disc.  A circle of radius R, tilted by the angle a about its horizontal axis and seen from
  // the distance d, reaches from -R cos a d/(d + R sin a) at the far side to R cos a d/(d - R sin a) at the
  // near side.  Half the sum is the centre of the ellipse, half the difference its vertical half-axis ry; the
  // point of the circle on the axis of tilt, at (R, 0), then gives the horizontal one.
  const hollow = document.querySelector(".hero-hollow");
  const hero = hollow && hollow.closest(".hero");
  const heroWafer = hero && hero.querySelector(".wafer");
  const disc = heroWafer && heroWafer.querySelector(".wafer-disc");
  // where an element stands in the first screen, from the layout: a part that is still rising counts as arrived
  const place = (element) => {
    let x = 0;
    let y = 0;
    for (let e = element; e && e !== hero; e = e.offsetParent) {
      x += e.offsetLeft;
      y += e.offsetTop;
    }
    return [x, y];
  };
  let depth = 0;
  let tilt = 0;
  const outline = () => {
    if (!disc) return;
    if (!depth) {
      const style = getComputedStyle(heroWafer);
      depth = parseFloat(style.perspective);
      tilt = parseFloat(style.getPropertyValue("--tilt"));
    }
    const a = ((tilt + (parseFloat(heroWafer.style.getPropertyValue("--ty")) || 0)) * Math.PI) / 180;
    const R = disc.offsetWidth / 2;
    if (!(depth > 0) || !(R > 0) || Number.isNaN(a)) return;
    const far = (-R * Math.cos(a) * depth) / (depth + R * Math.sin(a));
    const near = (R * Math.cos(a) * depth) / (depth - R * Math.sin(a));
    const ry = (near - far) / 2;
    const rx = R / Math.sqrt(1 - ((near + far) / 2 / ry) ** 2);
    const [textX, textY] = place(hollow);
    const [waferX, waferY] = place(heroWafer); // the wafer is tilted inside this box, about its centre
    const cx = waferX + heroWafer.offsetWidth / 2 - textX;
    const cy = waferY + heroWafer.offsetHeight / 2 + (near + far) / 2 - textY;
    const n = (value) => value.toFixed(1);
    hollow.style.clipPath = `ellipse(${n(rx)}px ${n(ry)}px at ${n(cx)}px ${n(cy)}px)`;
    hero.classList.add("is-crossed"); // from now on the wafer lies above the filled heading (see the stylesheet)
  };
  if (disc) {
    // first when the browser reports, after drawing the page, that the first screen is visible: the layout is
    // known then; and again when everything has loaded, in case a font changed the height of the text
    if ("IntersectionObserver" in window) {
      const drawn = new IntersectionObserver(() => {
        drawn.disconnect();
        outline();
      });
      drawn.observe(hero);
    } else outline();
    addEventListener("resize", outline);
    addEventListener("load", () => setTimeout(outline, 300));
  }

  // ---- a full-width field opens as it is scrolled into view -------------------------------------------------
  const plates = [...document.querySelectorAll("[data-grow]")];
  if (plates.length && !calm) {
    const grow = () => {
      for (const plate of plates) {
        const p = clamp((innerHeight - plate.getBoundingClientRect().top) / (innerHeight * 0.6), 0, 1);
        plate.style.setProperty("--grow", (1 - Math.pow(1 - p, 3)).toFixed(3));
      }
    };
    let waiting = false;
    addEventListener(
      "scroll",
      () => {
        if (waiting) return;
        waiting = true;
        requestAnimationFrame(() => {
          waiting = false;
          grow();
        });
      },
      { passive: true },
    );
    grow();
  }

  // ---- the wafer -----------------------------------------------------------------------------------------
  for (const wafer of document.querySelectorAll("[data-wafer]")) {
    const tip = wafer.querySelector(".wafer-tip");
    const zone = wafer.closest("[data-hero]") || wafer;

    if (!calm && matchMedia("(hover: hover) and (pointer: fine)").matches) {
      let frame = 0;
      let targetX = 0;
      let targetY = 0;
      let x = 0;
      let y = 0;
      const step = () => {
        x += (targetX - x) * 0.07;
        y += (targetY - y) * 0.07;
        wafer.style.setProperty("--tx", x.toFixed(2) + "deg");
        wafer.style.setProperty("--ty", y.toFixed(2) + "deg");
        wafer.style.setProperty("--turn", (x * 1.8).toFixed(2) + "deg"); // the band turns with the pointer, at most 8 degrees
        wafer.style.setProperty("--gx", (30 + x * 5).toFixed(1) + "%");
        wafer.style.setProperty("--gy", (16 - y * 4).toFixed(1) + "%");
        if (wafer === heroWafer) outline();
        frame = Math.abs(targetX - x) + Math.abs(targetY - y) > 0.02 ? requestAnimationFrame(step) : 0;
      };
      zone.addEventListener(
        "pointermove",
        (event) => {
          const box = zone.getBoundingClientRect();
          targetX = ((event.clientX - box.left) / box.width - 0.5) * 9;
          targetY = ((event.clientY - box.top) / box.height - 0.5) * -7;
          // the dots of the ground light up around the pointer
          zone.style.setProperty("--px", (event.clientX - box.left).toFixed(0) + "px");
          zone.style.setProperty("--py", (event.clientY - box.top).toFixed(0) + "px");
          zone.classList.add("is-pointed");
          if (!frame) frame = requestAnimationFrame(step);
        },
        { passive: true },
      );
      zone.addEventListener("pointerleave", () => {
        targetX = targetY = 0;
        zone.classList.remove("is-pointed");
        if (!frame) frame = requestAnimationFrame(step);
      });
    }

    const show = (die) => {
      const box = die.getBoundingClientRect();
      const frame = wafer.getBoundingClientRect();
      tip.querySelector("b").textContent = die.dataset.name;
      tip.querySelector("span").textContent = die.dataset.solvers;
      tip.querySelector("i").textContent = die.dataset.state;
      tip.classList.toggle("is-done", die.dataset.state === "simulated");
      tip.hidden = false;
      const half = tip.offsetWidth / 2 + 8;
      const centre = box.left + box.width / 2;
      tip.style.left = clamp(centre, half, innerWidth - half) - frame.left + "px";
      tip.style.top = box.top - frame.top + "px";
    };
    const hide = () => (tip.hidden = true);
    wafer.addEventListener("pointerover", (event) => {
      const die = event.target.closest("a.die");
      if (die) show(die);
    });
    wafer.addEventListener("pointerout", (event) => {
      const die = event.target.closest("a.die");
      if (die && !die.contains(event.relatedTarget)) hide();
    });
    wafer.addEventListener("focusin", (event) => {
      const die = event.target.closest("a.die");
      if (die) show(die);
    });
    wafer.addEventListener("focusout", hide);
  }

  if (!data) return;

  // ---- the fields ----------------------------------------------------------------------------------------
  // The brightness is the field magnitude that FDTD computed.  The fringes are added here, at the wavelength
  // in the waveguide, to show which way the light runs; in a coupler the light that has crossed over lags
  // the light that stays by a quarter of a period.  A field is prepared when its canvas comes near the
  // screen, and it moves only while it is on the screen.
  const STOPS = [[3, 4, 10], [10, 53, 88], [15, 147, 168], [240, 180, 60], [255, 244, 210]]; // prettier-ignore
  const LUT = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    const position = (i / 255) * (STOPS.length - 1);
    const low = Math.min(STOPS.length - 2, Math.floor(position));
    const part = position - low;
    const [r, g, b] = [0, 1, 2].map((k) => Math.round(STOPS[low][k] * (1 - part) + STOPS[low + 1][k] * part));
    LUT[i] = (255 << 24) | (b << 16) | (g << 8) | r;
  }
  const running = new Set();
  let ticking = false;
  const tick = (now) => {
    if (!running.size) {
      ticking = false;
      return;
    }
    if (!document.hidden) {
      for (const entry of running) {
        if (now - entry.last < 32) continue; // about 30 pictures a second are enough
        entry.last = now;
        entry.draw(now / 1000);
      }
    }
    requestAnimationFrame(tick);
  };

  function field(canvas) {
    const info = data.fields[canvas.dataset.field];
    if (!info) return;
    const image = new Image();
    image.onload = () => {
      const w = image.naturalWidth;
      const h = image.naturalHeight;
      canvas.width = w;
      canvas.height = h;
      const context = canvas.getContext("2d");
      context.drawImage(image, 0, 0);
      const source = context.getImageData(0, 0, w, h).data;
      const magnitude = new Float32Array(w * h);
      for (let i = 0; i < w * h; i++) magnitude[i] = Math.pow(source[4 * i] / 255, 0.78) * 255;
      const output = context.createImageData(w, h);
      const pixels = new Uint32Array(output.data.buffer);
      const period = ((info.lam / info.neff) * w) / (info.x[1] - info.x[0]); // pixels per wavelength in the guide
      const twoArms = canvas.dataset.field === "coupler";
      const middle = Math.round(h / 2);
      const stay = new Float32Array(w).fill(1);
      const crossed = new Float32Array(w).fill(1);
      const still = calm || canvas.hasAttribute("data-static");
      const floor = 0.4;
      const draw = (seconds) => {
        if (!still) {
          const phase = seconds * 2 * Math.PI * 1.1;
          for (let x = 0; x < w; x++) {
            const angle = (2 * Math.PI * x) / period - phase;
            stay[x] = floor + (1 - floor) * (0.5 + 0.5 * Math.cos(angle));
            crossed[x] = floor + (1 - floor) * (0.5 + 0.5 * Math.cos(angle - Math.PI / 2));
          }
        }
        for (let y = 0; y < h; y++) {
          const factor = twoArms && y < middle ? crossed : stay; // the upper waveguide is the one the light crosses into
          const row = y * w;
          for (let x = 0; x < w; x++) pixels[row + x] = LUT[(magnitude[row + x] * factor[x]) | 0];
        }
        context.putImageData(output, 0, 0);
      };
      draw(0);
      if (still) return;
      const entry = { draw, last: 0 };
      new IntersectionObserver((entries) => {
        for (const item of entries) {
          if (item.isIntersecting) running.add(entry);
          else running.delete(entry);
        }
        if (running.size && !ticking) {
          ticking = true;
          requestAnimationFrame(tick);
        }
      }).observe(canvas);
    };
    image.src = info.src;
  }
  const near = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        near.unobserve(entry.target);
        field(entry.target);
      }
    },
    { rootMargin: "700px 0px" },
  );
  document.querySelectorAll("canvas[data-field]").forEach((canvas) => near.observe(canvas));

  // ---- charts --------------------------------------------------------------------------------------------
  // A chart is drawn at the size it has on the screen, so that its lettering keeps its size on a phone.
  // `draw` gets the width and the height in pixels and returns what a later call of `update` needs.
  function chart(element, draw) {
    let width = 0;
    const render = () => {
      const w = Math.round(element.getBoundingClientRect().width);
      if (!w || w === width) return;
      width = w;
      const h = Math.round(clamp(w * 0.46, 196, 262));
      element.setAttribute("viewBox", `0 0 ${w} ${h}`);
      element.replaceChildren();
      draw(w, h);
    };
    const first = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        first.disconnect();
        render();
        if ("ResizeObserver" in window) new ResizeObserver(render).observe(element);
      },
      { rootMargin: "500px 0px" },
    );
    first.observe(element);
  }
  const box = { left: 42, right: 10, top: 20, bottom: 36 };

  // ---- the coupler law with a movable length ------------------------------------------------------------
  const toy = document.querySelector("[data-coupler-toy]");
  if (toy) {
    const { l_pi: lPi, l_bends: lBends, l_half: lHalf, lengths, fraction } = data.coupler;
    const element = toy.querySelector("svg");
    const input = toy.querySelector("input");
    const read = toy.querySelector(".toy-read");
    const maxLength = Number(input.max);
    const cross = (length) => Math.sin(((Math.PI / 2) * (length + lBends)) / lPi) ** 2;
    let length = lHalf;
    let place = () => {};
    let lengthAt = () => length;
    const set = (value) => {
      length = clamp(value, 0, maxLength);
      const share = cross(length);
      input.value = length;
      place();
      read.innerHTML = `L = ${length.toFixed(1)} µm <span><i class="key key-cross"></i>${(share * 100).toFixed(1)} % cross</span> <span><i class="key key-through"></i>${((1 - share) * 100).toFixed(1)} % through</span>`;
    };
    chart(element, (W, H) => {
      const px = (value) => box.left + (value / maxLength) * (W - box.left - box.right);
      const py = (value) => H - box.bottom - value * (H - box.top - box.bottom);
      const line = (f) => {
        let d = "";
        for (let i = 0; i <= 200; i++) {
          const value = (i / 200) * maxLength;
          d += (i ? "L" : "M") + px(value).toFixed(1) + " " + py(f(value)).toFixed(1);
        }
        return d;
      };
      for (const value of [0, 0.5, 1]) {
        element.append(svg("path", { class: value ? "chart-grid" : "chart-axis", d: `M${box.left} ${py(value)}H${W - box.right}` }));
        element.append(svg("text", { class: "chart-text", x: box.left - 8, y: py(value) + 4, "text-anchor": "end" }, value.toFixed(1)));
      }
      for (let value = 0; value <= maxLength; value += 10) {
        element.append(svg("path", { class: "chart-axis", d: `M${px(value)} ${py(0)}v4` }));
        element.append(svg("text", { class: "chart-text", x: px(value), y: py(0) + 17, "text-anchor": "middle" }, value));
      }
      element.append(svg("text", { class: "chart-text", x: W - box.right, y: H - 3, "text-anchor": "end" }, "length of the straight section (µm)"));
      element.append(svg("text", { class: "chart-text", x: 0, y: 10 }, "fraction of the light"));
      element.append(svg("path", { class: "chart-through", d: line((value) => 1 - cross(value)) }));
      element.append(svg("path", { class: "chart-cross", d: line(cross) }));
      lengths.forEach((value, i) => {
        const dot = svg("circle", { class: "chart-dot", cx: px(value), cy: py(fraction[i]), r: 4 });
        dot.append(svg("title", {}, `FDTD: ${value} µm, ${(fraction[i] * 100).toFixed(1)} % cross`));
        element.append(dot);
      });
      const cursor = svg("path", { class: "chart-cursor" });
      const onThrough = svg("circle", { class: "chart-handle-through", r: 5.5 });
      const onCross = svg("circle", { class: "chart-handle-cross", r: 5.5 });
      element.append(cursor, onThrough, onCross);
      place = () => {
        const share = cross(length);
        cursor.setAttribute("d", `M${px(length)} ${py(0)}V${py(1)}`);
        onCross.setAttribute("cx", px(length));
        onCross.setAttribute("cy", py(share));
        onThrough.setAttribute("cx", px(length));
        onThrough.setAttribute("cy", py(1 - share));
      };
      lengthAt = (x) => ((x - box.left) / (W - box.left - box.right)) * maxLength;
      place();
    });
    input.addEventListener("input", () => set(Number(input.value)));
    let dragging = false;
    const fromPointer = (event) => set(lengthAt(event.clientX - element.getBoundingClientRect().left));
    element.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== "mouse") return; // a finger scrolls the page here; the slider below moves the length
      dragging = true;
      element.setPointerCapture(event.pointerId);
      fromPointer(event);
    });
    element.addEventListener("pointermove", (event) => dragging && fromPointer(event));
    element.addEventListener("pointerup", () => (dragging = false));
    element.addEventListener("pointercancel", () => (dragging = false));
    set(lHalf);
  }

  // ---- the resonance of the ring, one curve for each simulated bias ---------------------------------------
  const spectrum = document.querySelector("[data-spectrum]");
  if (spectrum) {
    const { detuning, dB, bias, lam0 } = data.spectrum;
    const element = spectrum.querySelector("svg");
    const input = spectrum.querySelector("input");
    const read = spectrum.querySelector(".toy-read");
    const x0 = detuning[0];
    const x1 = detuning[detuning.length - 1];
    const floor = -50;
    const dips = dB.map((values) => {
      let k = 0;
      values.forEach((value, i) => value < values[k] && (k = i));
      return { shift: detuning[k], depth: values[k] };
    });
    let chosen = clamp(Number(input.value), 0, bias.length - 1);
    let place = () => {};
    const set = (i) => {
      chosen = clamp(Math.round(i), 0, bias.length - 1);
      input.value = chosen;
      place();
      const shift = (dips[chosen].shift >= 0 ? "+" : "") + dips[chosen].shift.toFixed(1);
      read.innerHTML = `bias ${bias[chosen].toFixed(2)} V <span><i class="key key-cross"></i>resonance ${minus(shift)} pm</span> <span>dip ${minus(dips[chosen].depth.toFixed(1))} dB</span>`;
    };
    chart(element, (W, H) => {
      const px = (value) => box.left + ((value - x0) / (x1 - x0)) * (W - box.left - box.right);
      const py = (value) => box.top + (Math.max(floor, value) / floor) * (H - box.top - box.bottom);
      const path = (values) => {
        let d = "";
        values.forEach((value, k) => (d += (k ? "L" : "M") + px(detuning[k]).toFixed(1) + " " + py(value).toFixed(1)));
        return d;
      };
      for (let value = 0; value >= floor; value -= 10) {
        element.append(svg("path", { class: value ? "chart-grid" : "chart-axis", d: `M${box.left} ${py(value)}H${W - box.right}` }));
        element.append(svg("text", { class: "chart-text", x: box.left - 8, y: py(value) + 4, "text-anchor": "end" }, minus(String(value))));
      }
      for (let value = Math.ceil(x0 / 50) * 50; value <= x1; value += 50) {
        element.append(svg("path", { class: "chart-axis", d: `M${px(value)} ${py(floor)}v4` }));
        element.append(svg("text", { class: "chart-text", x: px(value), y: py(floor) + 17, "text-anchor": "middle" }, minus(String(value))));
      }
      element.append(svg("text", { class: "chart-text", x: W - box.right, y: H - 3, "text-anchor": "end" }, `wavelength − ${lam0.toFixed(3)} nm (pm)`));
      element.append(svg("text", { class: "chart-text", x: 0, y: 10 }, "transmission (dB)"));
      dB.forEach((values) => element.append(svg("path", { class: "chart-context", d: path(values) })));
      const line = svg("path", { class: "chart-cross" });
      const mark = svg("circle", { class: "chart-mark", r: 4.5 });
      element.append(line, mark);
      place = () => {
        line.setAttribute("d", path(dB[chosen]));
        mark.setAttribute("cx", px(dips[chosen].shift));
        mark.setAttribute("cy", py(dips[chosen].depth));
      };
      place();
    });
    input.addEventListener("input", () => set(Number(input.value)));
    set(chosen);
  }
})();

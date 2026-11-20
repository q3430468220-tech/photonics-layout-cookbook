// photonics-layout-cookbook: the roadmap as a sky (website/fx/roadmap.py puts the data into the page).
//
//   the systems   each process is a star; its devices circle it on tilted orbits, nearer and larger in front of it,
//                 further and smaller behind it.  A device that is done at the step shown is a bright planet.
//   the circuits  constellations along the top, joined by lines to the devices they need; a line carries light when
//                 both of its ends are done.
//   the track     each stop is a version of ROADMAP.md and lights what it brought; the first view plays the story
//                 once.  A stop after the present shows what a planned circuit or process still needs.
//   the pointer   a star or a constellation keeps its chain (what it rests on, what rests on it); the rest dims.
//                 A click opens its chapter.
//   the nebulae   every process sits in a cloud of gas drawn once from fractal noise, two layers that turn slowly
//                 against each other; a process that is not done yet has a dim cloud.  Faint spokes join a process
//                 to the devices it carries that are done.
//   the stars     a process that is done shines with the diffraction spikes of a hexagonal mirror, longer as it
//                 carries more devices; one that is not done yet is a dim, small star until a step lights it.
//   the night     behind it all, quiet: the band of the galaxy with its dark rift, stars of several colours and a
//                 few brighter ones, three faint galaxies far away, and now and then a meteor.
//   the names     a device names itself where its name meets no other name, planet or label; else it waits.
(() => {
  "use strict";
  const root = document.querySelector("[data-sky]");
  const raw = document.getElementById("sky-data");
  if (!root || !raw) return;
  const D = JSON.parse(raw.textContent);
  const svg = root.querySelector(".sky-svg");
  const stage = root.querySelector("[data-sky-stage]");
  const tip = root.querySelector(".sky-tip");
  const calm = Boolean(window.COOKBOOK_CALM);
  const NS = "http://www.w3.org/2000/svg";
  const up = (href) => (href ? `../${href}` : null); // the page is roadmap/index.html

  const make = (name, attrs = {}, parent = null) => {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  };

  // ---- the paints ----
  const defs = make("defs", {}, svg);
  const radial = (id, stops) => {
    const g = make("radialGradient", { id }, defs);
    for (const [offset, color, opacity] of stops) make("stop", { offset, "stop-color": color, "stop-opacity": opacity }, g);
  };
  radial("sky-sun-gsip", [["0", "#ffffff", 1], [".28", "#c4f6ff", 0.8], [".6", "#5ee7f5", 0.2], ["1", "#5ee7f5", 0]]);
  radial("sky-sun-cornerstone", [["0", "#ffffff", 1], [".28", "#c8f7f2", 0.75], [".6", "#6fd6d6", 0.18], ["1", "#6fd6d6", 0]]);
  radial("sky-sun-tfln", [["0", "#ffffff", 1], [".28", "#ece0ff", 0.75], [".6", "#a99bff", 0.18], ["1", "#a99bff", 0]]);
  radial("sky-neb-gsip", [["0", "#3d6bff", 0.16], [".6", "#3d6bff", 0.04], ["1", "#3d6bff", 0]]);
  radial("sky-neb-cornerstone", [["0", "#3bb8c4", 0.12], ["1", "#3bb8c4", 0]]);
  radial("sky-neb-tfln", [["0", "#b05cff", 0.13], [".6", "#ff8fd8", 0.03], ["1", "#ff8fd8", 0]]);
  radial("sky-glow", [["0", "#ffffff", 0.95], [".25", "#bff6ff", 0.6], ["1", "#5ee7f5", 0]]);
  radial("sky-flash", [["0", "#ffffff", 1], [".4", "#9ef3ff", 0.6], ["1", "#5ee7f5", 0]]);
  const beam = make("linearGradient", { id: "sky-beam", gradientUnits: "userSpaceOnUse", x1: "0", y1: "0", x2: "0", y2: "660" }, defs);
  make("stop", { offset: "0", "stop-color": "#ff8fd8" }, beam);
  make("stop", { offset: ".5", "stop-color": "#ffffff" }, beam);
  make("stop", { offset: "1", "stop-color": "#5ee7f5" }, beam);
  // paints in the frame of the element that uses them: centred on its origin, so that one paint serves every star
  const local = (id, r, stops) => {
    const g = make("radialGradient", { id, gradientUnits: "userSpaceOnUse", cx: "0", cy: "0", r: String(r) }, defs);
    for (const [offset, color, opacity] of stops) make("stop", { offset, "stop-color": color, "stop-opacity": opacity }, g);
  };
  radial("sky-galaxy", [["0", "#fff4e0", 0.95], [".3", "#e9eeff", 0.5], ["1", "#c6d8ff", 0]]);
  const streak = make("linearGradient", { id: "sky-meteor", x1: "0", y1: "0", x2: "1", y2: "0" }, defs);
  make("stop", { offset: "0", "stop-color": "#ffffff", "stop-opacity": 0 }, streak);
  make("stop", { offset: ".7", "stop-color": "#dff7ff", "stop-opacity": 0.45 }, streak);
  make("stop", { offset: "1", "stop-color": "#ffffff", "stop-opacity": 1 }, streak);
  local("sky-spike", 100, [["0", "#ffffff", 0.8], [".12", "#e6f6ff", 0.4], [".5", "#cfe9ff", 0.1], ["1", "#cfe9ff", 0]]);

  const layer = (cls) => make("g", { class: cls }, svg);
  const gField = layer("sky-field");
  const gNebula = layer("sky-nebulae");
  const gMeteors = layer("sky-meteors");
  const gOrbits = layer("sky-orbits");
  const gSpokes = layer("sky-spokes");
  const gLines = layer("sky-lines");
  const gBack = layer("sky-back");
  const gProcs = layer("sky-procs");
  const gFront = layer("sky-front");
  const gCircs = layer("sky-circs");

  // ---- the processes ----
  const procs = new Map();
  for (const p of D.processes) {
    const [x, y] = p.at;
    const key = p.id.slice(5);
    const cloud = make("g", { class: "sky-neb" }, gNebula);
    make("circle", { cx: x, cy: y, r: key === "gsip" ? 210 : 140, fill: `url(#sky-neb-${key})` }, cloud);
    const g = make("g", { class: "sky-proc sky-dimmable", tabindex: "0", role: "link", "aria-label": `${p.name}, ${p.done ? "done" : "planned"}` }, gProcs);
    const r = key === "gsip" ? 30 : 22;
    make("circle", { class: "sky-sun", cx: x, cy: y, r: r * 1.05, fill: `url(#sky-sun-${key})` }, g);
    make("circle", { class: "sky-sun", cx: x, cy: y, r: r * 0.22, fill: "#fff" }, g);
    // the spikes of a hexagonal mirror and the faint pair of its strut: the telescope draws them, so every star has
    // them at the same angles
    const spikes = make("g", { class: "sky-spikes", transform: `translate(${x} ${y})` }, g);
    const reach = make("g", { class: "sky-reach" }, spikes);
    for (const [deg, len, w] of [[30, 100, 1.1], [90, 100, 1.1], [150, 100, 1.1], [210, 100, 1.1], [270, 100, 1.1], [330, 100, 1.1]]) {
      make("path", { class: "sky-spike", d: `M0 ${-w}L${len} 0L0 ${w}Z`, transform: `rotate(${deg})`, fill: "url(#sky-spike)" }, reach);
    }
    // the name stands below the outermost orbit, where no device passes
    const below = Math.max(r, ...p.libraries.map((lib) => D.orbits[lib][1])) + 34;
    const name = make("text", { class: "sky-proc-name", x, y: y + below }, g);
    name.textContent = p.name;
    const what = make("text", { class: "sky-proc-what", x, y: y + below + 16 }, g);
    what.textContent = p.what;
    procs.set(p.id, { p, g, x, y, r, cloud, name, what, key, reach, layers: [] });
  }

  // ---- the orbits and the devices on them ----
  const hostOf = new Map(); // library -> process id
  for (const p of D.processes) for (const lib of p.libraries) hostOf.set(lib, p.id);
  for (const [lib, [rx, ry]] of Object.entries(D.orbits)) {
    const host = procs.get(hostOf.get(lib));
    if (host) make("ellipse", { class: "sky-orbit", cx: host.x, cy: host.y, rx, ry }, gOrbits);
  }
  const stars = new Map();
  for (const d of D.devices) {
    const host = procs.get(d.process);
    const [rx, ry, turns] = D.orbits[d.library];
    const g = make("g", { class: "sky-star sky-dimmable", tabindex: "0", role: "link", "aria-label": `${d.name}, ${d.done ? "simulated" : "planned"}` }, gFront);
    make("circle", { class: "sky-flash", r: 22 }, g);
    make("circle", { class: "sky-want", r: 10 }, g);
    make("circle", { class: "sky-glow", r: 9.5, fill: "url(#sky-glow)" }, g);
    make("path", { class: "sky-spark", d: "M-6.5 0H6.5M0 -6.5V6.5" }, g);
    make("circle", { class: "sky-core", r: 3.6 }, g);
    make("circle", { r: 13, fill: "transparent" }, g); // the hit area
    // neighbours on an orbit take turns: one name to the right of its planet, the next below it
    const right = d.slot % 2 === 0;
    const label = make("text", { class: `sky-label${d.done ? " is-named" : ""}`, x: right ? 11 : 0, y: right ? 4 : 22, "text-anchor": right ? "start" : "middle" }, g);
    label.textContent = d.name.replace(/,.*$/, "").replace(/ and .*$/, "");
    const a0 = (2 * Math.PI * d.slot) / d.of + (d.library === "active" ? 0.35 : 0);
    stars.set(d.id, { d, g, label, slot: right ? 0 : 1, at: right ? 0 : 1, width: 0, scale: 1, near: 0,
      x0: host.x, y0: host.y, rx, ry, w: (turns * 2 * Math.PI) / 60, a0, x: host.x, y: host.y, front: true });
  }
  // a faint spoke from a process to each device of its libraries: lit when both are done
  const spokes = [];
  for (const s of stars.values()) {
    const host = procs.get(s.d.process);
    spokes.push({ from: s.d.process, to: s.d.id, path: make("path", { class: `sky-spoke sky-dimmable sky-spoke-${host.key}` }, gSpokes) });
  }

  // ---- the circuits, and the lines to what they need ----
  const circs = new Map();
  for (const c of D.circuits) {
    const [x, y] = c.at;
    const g = make("g", { class: "sky-circ sky-dimmable", tabindex: "0", role: "link", "aria-label": `${c.name}, ${c.done ? "simulated" : "planned"}` }, gCircs);
    const s = 12;
    make("path", { class: "sky-circ-star", d: `M${x} ${y - s}Q${x} ${y} ${x + s} ${y}Q${x} ${y} ${x} ${y + s}Q${x} ${y} ${x - s} ${y}Q${x} ${y} ${x} ${y - s}Z` }, g);
    make("circle", { cx: x, cy: y, r: 16, fill: "transparent" }, g);
    const name = make("text", { class: "sky-circ-name", x: x + 18, y: y - 2 }, g);
    name.textContent = c.name;
    const dir = make("text", { class: "sky-circ-dir", x: x + 18, y: y + 13 }, g);
    dir.textContent = c.direction.toUpperCase();
    circs.set(c.id, { c, g, x, y, name, dir });
  }
  const lines = []; // { from, to, path, pulse }
  const addLine = (from, to, k) => {
    const path = make("path", { class: "sky-line sky-dimmable" }, gLines);
    const pulse = make("path", { class: "sky-pulse sky-dimmable" }, gLines);
    pulse.style.setProperty("--delay", `${(-k * 0.53) % 3}s`);
    lines.push({ from, to, path, pulse });
  };
  let k = 0;
  for (const c of D.circuits) for (const need of c.needs) addLine(c.id, need, k++);
  for (const p of D.processes) for (const single of p.single) addLine(p.id, single, k++);

  // ---- the motion: the devices circle their process ----
  const point = (id) => {
    if (stars.has(id)) return stars.get(id);
    if (circs.has(id)) return circs.get(id);
    return procs.get(id);
  };
  function place(t) {
    for (const s of stars.values()) {
      const a = s.a0 + s.w * t;
      const sin = Math.sin(a);
      s.x = s.x0 + s.rx * Math.cos(a);
      s.y = s.y0 + s.ry * sin;
      const scale = 0.72 + 0.45 * (sin + 1) / 2;
      s.g.setAttribute("transform", `translate(${s.x.toFixed(1)} ${s.y.toFixed(1)}) scale(${scale.toFixed(3)})`);
      s.scale = scale;
      s.near = Math.max(0, Math.min(1, (sin - 0.3) * 2.5));
      s.g.style.setProperty("--front", s.near.toFixed(2)); // the name shows in front
      const front = sin > -0.05;
      if (front !== s.front) {
        (front ? gFront : gBack).appendChild(s.g);
        s.front = front;
      }
    }
    for (const spoke of spokes) {
      const a = procs.get(spoke.from);
      const b = stars.get(spoke.to);
      spoke.path.setAttribute("d", `M${a.x} ${a.y}L${b.x.toFixed(1)} ${b.y.toFixed(1)}`);
    }
    for (const p of procs.values()) {
      for (const layer of p.layers) {
        const turn = (layer.w * t) % 360;
        const breathe = 1 + 0.025 * Math.sin(t * 0.21 + layer.phase);
        layer.img.setAttribute("transform", `translate(${p.x} ${p.y}) rotate(${turn.toFixed(2)}) scale(${breathe.toFixed(4)})`);
      }
    }
    for (const line of lines) {
      const a = point(line.from);
      const b = point(line.to);
      const lift = circs.has(line.from) ? 70 : 0;
      const d = `M${a.x.toFixed(1)} ${a.y.toFixed(1)}C${a.x.toFixed(1)} ${(a.y + lift).toFixed(1)} ${b.x.toFixed(1)} ${(b.y - lift).toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
      line.path.setAttribute("d", d);
      line.pulse.setAttribute("d", d);
    }
    names();
  }

  // ---- the names: each lit device in front names itself in the first free place, nearest first ----
  const SLOTS = [
    { x: 11, y: 4, anchor: "start" },
    { x: 0, y: 22, anchor: "middle" },
    { x: -11, y: 4, anchor: "end" },
    { x: 0, y: -13, anchor: "middle" },
  ];
  let fixed = []; // boxes that do not move: the names of the processes and of the circuits, the suns
  function boxOf(s, slot) {
    const w = s.width * s.scale;
    const h = 13 * s.scale;
    const ax = s.x + slot.x * s.scale;
    const ay = s.y + slot.y * s.scale;
    const x0 = slot.anchor === "start" ? ax : slot.anchor === "end" ? ax - w : ax - w / 2;
    return [x0 - 3, ay - 0.8 * h - 2, x0 + w + 3, ay + 0.3 * h + 2];
  }
  const meets = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
  function obstacles() {
    const box = (el) => {
      const b = el.getBBox();
      return [b.x - 3, b.y - 2, b.x + b.width + 3, b.y + b.height + 2];
    };
    fixed = [];
    for (const p of procs.values()) {
      fixed.push(box(p.name), box(p.what));
      fixed.push([p.x - p.r * 0.9, p.y - p.r * 0.9, p.x + p.r * 0.9, p.y + p.r * 0.9]);
    }
    for (const c of circs.values()) fixed.push(box(c.name), box(c.dir), [c.x - 12, c.y - 12, c.x + 12, c.y + 12]);
  }
  function measure() {
    for (const s of stars.values()) s.width = s.label.getComputedTextLength() || s.label.textContent.length * 6.4;
    obstacles();
    names();
  }
  function names() {
    if (!fixed.length) return;
    const taken = fixed.slice();
    for (const s of stars.values()) taken.push([s.x - 6 * s.scale, s.y - 6 * s.scale, s.x + 6 * s.scale, s.y + 6 * s.scale]);
    const showing = [...stars.values()].filter((s) => s.d.done && lit.has(s.d.id) && s.near > 0.12).sort((a, b) => b.near - a.near);
    const set = new Set(showing);
    for (const s of stars.values()) if (!set.has(s)) s.g.style.setProperty("--fit", "0");
    for (const s of showing) {
      const order = [s.at, s.slot, 0, 1, 2, 3].filter((k, i, all) => all.indexOf(k) === i); // where it stands first
      const own = (k) => boxOf(s, SLOTS[k]);
      const free = order.find((k) => {
        const b = own(k);
        return !taken.some((o) => meets(o, b)); // its own planet is never in the way: every place stands clear of it
      });
      if (free === undefined) {
        s.g.style.setProperty("--fit", "0");
        continue;
      }
      taken.push(own(free));
      s.g.style.setProperty("--fit", "1");
      if (free !== s.at) {
        const slot = SLOTS[free];
        s.label.setAttribute("x", String(slot.x));
        s.label.setAttribute("y", String(slot.y));
        s.label.setAttribute("text-anchor", slot.anchor);
        s.at = free;
      }
    }
  }

  // ---- the track: what is lit at each step ----
  const steps = D.steps;
  const ticks = [...root.querySelectorAll("[data-step]")];
  const labelOut = root.querySelector("[data-sky-step-label]");
  const whatOut = root.querySelector("[data-sky-step-what]");
  const statOut = Object.fromEntries([...root.querySelectorAll("[data-stat]")].map((b) => [b.dataset.stat, b]));
  let lit = new Set();
  let current = -1;
  function litAt(step) {
    const set = new Set();
    for (let i = 0; i <= Math.min(step, D.now); i++) for (const id of steps[i].lit) set.add(id);
    return set;
  }
  function show(step, animate) {
    const next = litAt(step);
    const focus = step > D.now ? steps[step].focus : null;
    for (const [id, s] of stars) {
      const on = next.has(id);
      if (on && !lit.has(id) && animate) {
        s.g.classList.remove("is-ignite");
        void s.g.getBBox();
        s.g.classList.add("is-ignite");
      }
      s.g.classList.toggle("is-lit", on);
    }
    for (const [id, p] of procs) {
      p.g.classList.toggle("is-dark", !next.has(id));
      p.cloud.classList.toggle("is-dark", !next.has(id));
      const carried = [...stars.values()].filter((s) => (s.d.process === id || p.p.single.includes(s.d.id)) && next.has(s.d.id)).length;
      p.what.textContent = carried && next.has(id) ? `${p.p.what} · ${carried} ${carried === 1 ? "device" : "devices"} done` : p.p.what;
      // the reach of the spikes grows with the log of what the process carries: 6 devices are not 6 times 1
      p.reach.style.setProperty("--s", next.has(id) ? Math.min(0.95, 0.26 + 0.2 * Math.log2(1 + carried)).toFixed(3) : "0");
    }
    for (const spoke of spokes) spoke.path.classList.toggle("is-lit", next.has(spoke.from) && next.has(spoke.to));
    for (const [id, c] of circs) c.g.classList.toggle("is-lit", next.has(id));
    const wanted = new Set();
    if (focus) {
      wanted.add(focus);
      if (circs.has(focus)) for (const need of circs.get(focus).c.needs) wanted.add(need);
      if (procs.has(focus)) for (const [id, s] of stars) if (s.d.process === focus) wanted.add(id);
    }
    for (const [id, node] of [...stars, ...circs, ...procs]) node.g.classList.toggle("is-wanted", wanted.has(id));
    for (const line of lines) {
      const on = next.has(line.from) && next.has(line.to);
      line.path.classList.toggle("is-lit", on);
      line.pulse.classList.toggle("is-lit", on && !calm);
      line.path.classList.toggle("is-wanted", !on && wanted.has(line.from) && wanted.has(line.to));
    }
    const count = (prefix) => [...next].filter((id) => id.startsWith(prefix)).length;
    const counts = { devices: count("dev:"), circuits: count("circ:"), processes: count("proc:") };
    for (const [key, b] of Object.entries(statOut)) {
      if (b.textContent !== String(counts[key])) {
        b.textContent = String(counts[key]);
        if (animate) {
          b.classList.remove("is-bump");
          void b.offsetWidth;
          b.classList.add("is-bump");
        }
      }
    }
    labelOut.textContent = steps[step].kind === "next" ? "Next" : steps[step].label;
    labelOut.parentElement.classList.toggle("is-next", steps[step].kind === "next");
    whatOut.textContent = steps[step].kind === "next" ? `${steps[step].what}, and what it still needs` : steps[step].what;
    ticks.forEach((t, i) => {
      t.classList.toggle("is-passed", i <= step);
      t.classList.toggle("is-current", i === step);
      t.setAttribute("aria-pressed", String(i === step));
    });
    root.querySelector(".sky-ticks").style.setProperty("--fill", `${(100 * step) / Math.max(1, steps.length - 1)}%`);
    lit = next;
    current = step;
    if (fixed.length) obstacles(); // the line under a process has changed
    names();
  }

  let playing = 0;
  function stop() {
    window.clearTimeout(playing);
    playing = 0;
  }
  function play() {
    stop();
    let i = 0;
    const go = () => {
      show(i, true);
      if (i < D.now) {
        i += 1;
        playing = window.setTimeout(go, 1250);
      } else {
        playing = 0;
      }
    };
    go();
  }
  ticks.forEach((t) => t.addEventListener("click", () => {
    stop();
    show(Number(t.dataset.step), true);
  }));
  root.querySelector("[data-sky-play]").addEventListener("click", play);

  // ---- the pointer: the chain of a node ----
  function chain(id) {
    const set = new Set([id]);
    if (stars.has(id)) {
      set.add(stars.get(id).d.process);
      for (const c of D.circuits) if (c.needs.includes(id)) set.add(c.id);
      for (const p of D.processes) if (p.single.includes(id)) set.add(p.id);
    } else if (circs.has(id)) {
      for (const need of circs.get(id).c.needs) {
        set.add(need);
        set.add(stars.get(need).d.process);
        for (const p of D.processes) if (p.single.includes(need)) set.add(p.id);
      }
    } else if (procs.has(id)) {
      for (const [sid, s] of stars) if (s.d.process === id || procs.get(id).p.single.includes(sid)) set.add(sid);
    }
    return set;
  }
  const idOf = new Map();
  for (const [id, node] of [...stars, ...circs, ...procs]) idOf.set(node.g, id);
  let focused = "";
  function focus(id) {
    if (id === focused) return;
    focused = id;
    root.classList.toggle("is-focus", Boolean(id));
    const set = id ? chain(id) : new Set();
    for (const [nid, node] of [...stars, ...circs, ...procs]) node.g.classList.toggle("is-on", set.has(nid));
    for (const line of lines) {
      const on = set.has(line.from) && set.has(line.to);
      line.path.classList.toggle("is-on", on);
      line.pulse.classList.toggle("is-on", on);
    }
    for (const spoke of spokes) spoke.path.classList.toggle("is-on", set.has(spoke.from) && set.has(spoke.to));
  }
  function nodeOf(target) {
    const g = target.closest && target.closest(".sky-star, .sky-circ, .sky-proc");
    return g ? idOf.get(g) : "";
  }
  function showTip(id) {
    const node = point(id);
    const frame = stage.getBoundingClientRect();
    const box = node.g.getBoundingClientRect();
    tip.replaceChildren();
    let state = "";
    let title = "";
    if (stars.has(id)) {
      const d = stars.get(id).d;
      const glyph = make("svg", { class: "glyph", "aria-hidden": "true" });
      make("use", { href: `#${d.symbol}` }, glyph);
      tip.append(glyph);
      title = d.name;
      const also = D.processes.filter((p) => p.single.includes(id)).map((p) => p.name);
      const home = procs.get(d.process).p.name;
      state = `${d.libname} · ${home}${also.length ? `, also run on ${also.join(", ")}` : ""} · ${d.done ? "simulated · open its chapter" : "planned"}`;
      tip.classList.toggle("is-done", d.done);
    } else if (circs.has(id)) {
      const c = circs.get(id).c;
      title = c.name;
      state = `${c.direction} · ${c.done ? "simulated · open its chapter" : `planned · needs ${c.needs.length} devices`}`;
      tip.classList.toggle("is-done", c.done);
    } else {
      const p = procs.get(id).p;
      title = p.name;
      state = p.done ? "a process file the flow reads" : "planned";
      tip.classList.toggle("is-done", p.done);
    }
    tip.classList.toggle("no-glyph", !stars.has(id));
    const b = document.createElement("b");
    b.textContent = title;
    const span = document.createElement("span");
    span.textContent = state;
    tip.append(b, span);
    tip.style.left = `${box.left + box.width / 2 - frame.left + stage.scrollLeft}px`;
    tip.style.top = `${box.top - frame.top}px`;
    tip.hidden = false;
  }
  svg.addEventListener("pointerover", (event) => {
    const id = nodeOf(event.target);
    if (!id) return;
    if (event.pointerType !== "touch") focus(id);
    showTip(id);
  });
  svg.addEventListener("pointerout", (event) => {
    if (nodeOf(event.relatedTarget || document.body)) return;
    focus("");
    tip.hidden = true;
  });
  svg.addEventListener("focusin", (event) => {
    const id = nodeOf(event.target);
    if (id) {
      focus(id);
      showTip(id);
    }
  });
  svg.addEventListener("focusout", () => {
    focus("");
    tip.hidden = true;
  });
  const open = (id) => {
    const href = stars.has(id) ? stars.get(id).d.href : circs.has(id) ? circs.get(id).c.href : procs.get(id).p.href;
    if (href) window.location.href = up(href);
  };
  svg.addEventListener("click", (event) => {
    const id = nodeOf(event.target);
    if (id) open(id);
  });
  svg.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    const id = nodeOf(event.target);
    if (id) open(id);
  });

  // ---- the field: faint stars behind everything, each with a twinkle and a colour of its own ----
  let seed = 7;
  const rand = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };
  // most stars look white; some are hot and blue, a few cool and warm
  const TINTS = [[0.68, "#dfe6ff"], [0.16, "#c6d8ff"], [0.11, "#ffe9c8"], [0.05, "#ffcf9e"]];
  const tint = () => {
    let u = rand();
    for (const [share, colour] of TINTS) {
      if (u < share) return colour;
      u -= share;
    }
    return TINTS[0][1];
  };
  for (let k = 0; k < 110; k++) {
    const star = make("circle", { class: "sky-dust", cx: (rand() * 1200).toFixed(1), cy: (rand() * 660).toFixed(1), r: (0.35 + rand() * rand() * 1.4).toFixed(2) }, gField);
    star.style.fill = tint();
    star.style.setProperty("--tw", `${(2.5 + rand() * 5).toFixed(2)}s`);
    star.style.setProperty("--td", `${(-rand() * 8).toFixed(2)}s`);
    star.style.setProperty("--to", (0.25 + rand() * 0.6).toFixed(2));
  }
  // four brighter stars, where nothing else stands: a small glow and a fine cross
  for (const [x, y, r, colour] of [[1150, 482, 1.6, "#ffffff"], [56, 566, 1.4, "#ffe9c8"], [748, 26, 1.5, "#c6d8ff"], [262, 650, 1.3, "#ffffff"]]) {
    const g = make("g", { class: "sky-bright", transform: `translate(${x} ${y})` }, gField);
    g.style.setProperty("--tw", `${(5 + rand() * 4).toFixed(2)}s`);
    g.style.setProperty("--td", `${(-rand() * 6).toFixed(2)}s`);
    make("circle", { class: "sky-bright-glow", r: r * 4.5, fill: "url(#sky-glow)" }, g);
    make("path", { class: "sky-bright-cross", d: `M${-r * 5.5} 0H${r * 5.5}M0 ${-r * 5.5}V${r * 5.5}` }, g);
    make("circle", { r, fill: colour }, g);
  }

  // ---- value noise, summed over octaves: the texture of the clouds, of the band of the galaxy, of the galaxies ----
  const smoothstep = (v) => v * v * (3 - 2 * v);
  const ramp = (a, b, v) => smoothstep(Math.max(0, Math.min(1, (v - a) / (b - a))));
  function noiseOf(seedOf, octaves = 4) {
    const hash = (x, y) => {
      let h = (x * 374761393 + y * 668265263 + seedOf * 1442695041) | 0;
      h = Math.imul(h ^ (h >>> 13), 1274126177);
      return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
    };
    const noise = (x, y) => {
      const xi = Math.floor(x);
      const yi = Math.floor(y);
      const u = smoothstep(x - xi);
      const v = smoothstep(y - yi);
      const a = hash(xi, yi);
      const b = hash(xi + 1, yi);
      const c = hash(xi, yi + 1);
      const d = hash(xi + 1, yi + 1);
      return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
    };
    const norm = 1 - 0.5 ** octaves;
    return (x, y) => {
      let sum = 0;
      let amp = 0.5;
      let f = 1;
      for (let o = 0; o < octaves; o++) {
        sum += amp * noise(x * f, y * f);
        f *= 2.07;
        amp *= 0.5;
      }
      return sum / norm;
    };
  }

  // ---- the band of the galaxy: soft dust with a dark rift along it, and many small stars in it ----
  // drawn once on a canvas that reaches past the frame on every side (the sky shows past its box), and faded at
  // the edges of that canvas so that it never ends in a line
  const BAND = { x: -300, y: -40, w: 1800, h: 740 };
  function galaxyBand() {
    const S = Math.min(1.6, (window.devicePixelRatio || 1) * 1.1);
    const lo = 4; // the dust at a quarter of the size: it is soft anyway
    const glow = noiseOf(41, 5);
    const rift = noiseOf(77, 4);
    const [x0, y0, x1, y1] = [-80, 640, 1280, 60]; // the axis: from the lower left to the upper right
    const len = Math.hypot(x1 - x0, y1 - y0);
    const across = (x, y) => ((x - x0) * -(y1 - y0) + (y - y0) * (x1 - x0)) / len;
    const along = (x, y) => ((x - x0) * (x1 - x0) + (y - y0) * (y1 - y0)) / len;
    const width = 95;
    const density = (x, y) => {
      const d = across(x, y) + 26 * (glow(along(x, y) / 260, 3.1) - 0.5); // the band wanders a little
      return Math.exp(-((d / width) ** 2));
    };
    const edge = (x, y) => ramp(0, 220, x - BAND.x) * ramp(0, 220, BAND.x + BAND.w - x) * ramp(0, 80, y - BAND.y) * ramp(0, 80, BAND.y + BAND.h - y);
    const dust = document.createElement("canvas");
    dust.width = BAND.w / lo;
    dust.height = BAND.h / lo;
    const dctx = dust.getContext("2d");
    const img = dctx.createImageData(dust.width, dust.height);
    for (let jj = 0; jj < dust.height; jj++) {
      for (let ii = 0; ii < dust.width; ii++) {
        const x = BAND.x + (ii + 0.5) * lo;
        const y = BAND.y + (jj + 0.5) * lo;
        const b = density(x, y);
        if (b < 0.02) continue;
        const lane = ramp(0.48, 0.72, rift(x / 110, y / 110)) * Math.exp(-(((across(x, y) - 10) / (0.45 * width)) ** 2));
        const a = b * (0.35 + 0.65 * glow(x / 150, y / 150)) * (1 - 0.8 * lane) * edge(x, y);
        const at = (jj * dust.width + ii) * 4;
        img.data[at] = 205;
        img.data[at + 1] = 214;
        img.data[at + 2] = 255;
        img.data[at + 3] = 255 * 0.17 * a;
      }
    }
    dctx.putImageData(img, 0, 0);
    const out = document.createElement("canvas");
    out.width = Math.round(BAND.w * S);
    out.height = Math.round(BAND.h * S);
    const ctx = out.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(dust, 0, 0, out.width, out.height);
    ctx.scale(S, S);
    let k = 1234567;
    const r = () => {
      k = (k * 16807) % 2147483647;
      return (k - 1) / 2147483646;
    };
    for (let n = 0; n < 4200; n++) {
      const x = BAND.x + r() * BAND.w;
      const y = BAND.y + r() * BAND.h;
      const b = density(x, y);
      if (r() > 0.9 * b * b + 0.01) continue; // many along the band, few away from it
      ctx.globalAlpha = (0.2 + 0.55 * r()) * edge(x, y);
      const u = r();
      ctx.fillStyle = u < 0.18 ? "#ffe9c8" : u < 0.4 ? "#c6d8ff" : "#eef2ff";
      ctx.beginPath();
      ctx.arc(x - BAND.x, y - BAND.y, 0.3 + r() * r() * 0.85, 0, 2 * Math.PI);
      ctx.fill();
    }
    return out.toDataURL("image/png");
  }

  // ---- three galaxies far away, where nothing else stands: two spirals and one seen edge-on ----
  function spiral(seedOf, size = 80) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(size, size);
    const grain = noiseOf(seedOf, 3);
    for (let jj = 0; jj < size; jj++) {
      for (let ii = 0; ii < size; ii++) {
        const u = (ii / size - 0.5) * 2;
        const v = (jj / size - 0.5) * 2;
        const rr = Math.hypot(u, v);
        if (rr >= 1) continue;
        const arms = 0.5 + 0.5 * Math.cos(2 * (Math.atan2(v, u) - 3.2 * Math.log(rr + 0.07))); // two logarithmic arms
        const core = Math.exp(-((rr / 0.15) ** 2));
        const disc = Math.exp(-rr * 3.4) * (1 - rr);
        const a = Math.min(1, core + disc * arms * (0.55 + 0.45 * grain(u * 4 + 3, v * 4 + 5)) * 1.1);
        const at = (jj * size + ii) * 4;
        img.data[at] = 215 + 40 * core;
        img.data[at + 1] = 225 + 20 * core;
        img.data[at + 2] = 255 - 30 * core;
        img.data[at + 3] = 255 * a;
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL("image/png");
  }
  const GALAXIES = [
    { kind: "spiral", x: 1148, y: 600, size: 32, tilt: -32, squash: 0.5, seed: 5 },
    { kind: "spiral", x: 44, y: 455, size: 20, tilt: 24, squash: 0.78, seed: 9 },
    { kind: "edge", x: 598, y: 630, rx: 11, ry: 1.3, tilt: -8 },
  ];
  for (const gx of GALAXIES) {
    if (gx.kind !== "edge") continue;
    const g = make("g", { class: "sky-galaxy", transform: `translate(${gx.x} ${gx.y}) rotate(${gx.tilt})` }, gField);
    make("ellipse", { rx: gx.rx, ry: gx.ry, fill: "url(#sky-galaxy)" }, g);
    make("ellipse", { rx: gx.rx * 0.22, ry: gx.ry * 1.9, fill: "url(#sky-galaxy)" }, g); // the bulge
  }

  // ---- the nebulae: fractal noise, bent by more noise, inside a soft disc; coloured from the core outwards ----
  function nebula(seedOf, colours, size = 200) {
    const smooth = smoothstep;
    const fbm = noiseOf(seedOf);
    const step = (a, b, v) => smooth(Math.max(0, Math.min(1, (v - a) / (b - a))));
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(size, size);
    const [inner, middle, outer] = colours;
    for (let j = 0; j < size; j++) {
      for (let i = 0; i < size; i++) {
        const nx = (i / size - 0.5) * 2;
        const ny = (j / size - 0.5) * 2;
        const r = Math.hypot(nx, ny);
        if (r >= 1) continue;
        const wx = fbm(nx * 1.7 + 4.1, ny * 1.7 + 1.3);
        const wy = fbm(nx * 1.7 + 8.3, ny * 1.7 + 6.2);
        const n = fbm(nx * 2.4 + 2.2 * wx, ny * 2.4 + 2.2 * wy);
        const dust = step(0.56, 0.78, fbm(nx * 3.6 + 11.5, ny * 3.6 + 3.7));
        const disc = Math.pow(1 - r, 1.35);
        const gas = step(0.3, 0.82, n) * disc * (1 - 0.65 * dust);
        const core = Math.pow(1 - r, 3.2);
        const mix = Math.min(1, core * 1.6 + n * 0.35);
        const col = mix > 0.5
          ? inner.map((c, k) => c * (mix - 0.5) * 2 + middle[k] * (1 - (mix - 0.5) * 2))
          : middle.map((c, k) => c * mix * 2 + outer[k] * (1 - mix * 2));
        const at = (j * size + i) * 4;
        img.data[at] = col[0];
        img.data[at + 1] = col[1];
        img.data[at + 2] = col[2];
        img.data[at + 3] = Math.min(255, 255 * (gas * 0.9 + core * 0.25));
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL("image/png");
  }
  const CLOUDS = {
    gsip: { r: 360, layers: [[[205, 240, 255], [80, 140, 255], [96, 60, 220]], [[255, 255, 255], [94, 231, 245], [200, 90, 220]]] },
    cornerstone: { r: 235, layers: [[[205, 245, 245], [60, 170, 185], [40, 90, 160]], [[255, 255, 255], [94, 231, 245], [60, 120, 200]]] },
    tfln: { r: 250, layers: [[[240, 215, 255], [169, 155, 255], [176, 92, 255]], [[255, 255, 255], [255, 143, 216], [120, 70, 220]]] },
  };
  const jobs = [];
  jobs.push(() => {
    const band = make("image", { class: "sky-band", href: galaxyBand(), x: BAND.x, y: BAND.y, width: BAND.w, height: BAND.h, preserveAspectRatio: "none" });
    gField.insertBefore(band, gField.firstChild);
  });
  jobs.push(() => {
    for (const gx of GALAXIES) {
      if (gx.kind !== "spiral") continue;
      const g = make("g", { class: "sky-galaxy", transform: `translate(${gx.x} ${gx.y}) rotate(${gx.tilt}) scale(1 ${gx.squash})` }, gField);
      make("image", { href: spiral(gx.seed), x: -gx.size / 2, y: -gx.size / 2, width: gx.size, height: gx.size }, g);
    }
  });
  let made = 0;
  for (const p of procs.values()) {
    const cloud = CLOUDS[p.key];
    if (!cloud) continue;
    cloud.layers.forEach((colours, k) => {
      const s = 11 + 17 * made++;
      jobs.push(() => {
        const R = cloud.r * (k ? 0.82 : 1);
        const img = make("image", { class: `sky-neb-img sky-neb-l${k}`, href: nebula(s, colours), x: -R, y: -R, width: 2 * R, height: 2 * R, preserveAspectRatio: "none" }, p.cloud);
        p.layers.push({ img, w: k ? -1.1 : 0.7, phase: k * 2.1 + made }); // degrees per second
        place(clock);
      });
    });
  }
  const work = () => {
    const job = jobs.shift();
    if (!job) return;
    job();
    window.setTimeout(work, 30);
  };
  window.setTimeout(work, 120);

  // ---- start: the sky in its present state; on the first view the story plays once ----
  let clock = 0;
  place(0);
  show(D.now, false);
  measure();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  if (calm || !("IntersectionObserver" in window)) return;
  let visible = false;
  // a meteor: a short streak, its tail fading backwards, that crosses part of the sky within a second
  function meteor() {
    const side = Math.random() < 0.5 ? 1 : -1;
    const tilt = ((18 + Math.random() * 20) * Math.PI) / 180;
    const vx = side * Math.cos(tilt);
    const vy = Math.sin(tilt);
    const x0 = 150 + Math.random() * 900;
    const y0 = 20 + Math.random() * 280;
    const travel = 170 + Math.random() * 120;
    const tail = 70 + Math.random() * 50;
    const g = make("g", { class: "sky-meteor" }, gMeteors);
    const body = make("g", { transform: `rotate(${((Math.atan2(vy, vx) * 180) / Math.PI).toFixed(1)})` }, g);
    make("path", { d: `M${-tail} -0.4L0 -0.85L0 0.85L${-tail} 0.4Z`, fill: "url(#sky-meteor)" }, body);
    make("circle", { r: 1.05, fill: "#ffffff" }, body);
    const at = (f) => `translate(${(x0 + vx * travel * f).toFixed(1)}px, ${(y0 + vy * travel * f).toFixed(1)}px)`;
    const flight = g.animate(
      [{ transform: at(0), opacity: 0 }, { transform: at(0.2), opacity: 0.9, offset: 0.2 }, { transform: at(1), opacity: 0 }],
      { duration: 850 + Math.random() * 350, easing: "cubic-bezier(.3, .6, .4, 1)", fill: "forwards" },
    );
    flight.onfinish = () => g.remove();
  }
  const nextMeteor = (wait) =>
    window.setTimeout(() => {
      if (visible && document.visibilityState === "visible") meteor();
      nextMeteor(10000 + Math.random() * 10000);
    }, wait);
  nextMeteor(5000 + Math.random() * 4000);
  let frame = 0;
  let t = 0;
  let last = 0;
  const loop = (now) => {
    frame = 0;
    if (!visible) return;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
    if (!focused) t += dt;
    last = now;
    clock = t;
    place(t);
    frame = requestAnimationFrame(loop);
  };
  let told = false;
  new IntersectionObserver(
    (entries) => {
      visible = entries.some((e) => e.isIntersecting);
      if (visible && !frame) {
        last = 0;
        frame = requestAnimationFrame(loop);
      }
      if (visible && !told) {
        told = true;
        play();
      }
    },
    { threshold: 0.25 },
  ).observe(stage);
})();

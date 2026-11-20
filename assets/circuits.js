// photonics-layout-cookbook: the chip of the circuits page.  The light of every piece of waveguide (--o), the glow of
// every heater (--h) and the detectors come from the data that website/fx/circuits.py puts into the page: the powers
// that the model of the Clements chapter gives for the heater settings that its step 2 found.
//
//   the matrix     Fourier transform, a random unitary (each click the next of those kept), or the heaters off
//   the input      a button, or the waveguide under the pointer; while nobody touches the page the light moves from
//                  one input to the next by itself
//   the chip       tilts a little under the pointer, as the wafer of the home page does
//   the tip        a heater says what it sets and its power; a planned circuit says which devices it needs
(() => {
  "use strict";
  const stage = document.querySelector("[data-chip]");
  const raw = document.getElementById("chip-data");
  if (!stage || !raw) return;
  const data = JSON.parse(raw.textContent);
  const cards = JSON.parse((document.getElementById("circuit-cards") || { textContent: "{}" }).textContent);
  const calm = Boolean(window.COOKBOOK_CALM);
  const fine = matchMedia("(hover: hover) and (pointer: fine)").matches;
  const chip = stage.querySelector(".chip-body");
  const pieces = [...stage.querySelectorAll(".pc")].sort((a, b) => a.dataset.k - b.dataset.k);
  const heaters = [...stage.querySelectorAll(".ht")].sort((a, b) => a.dataset.j - b.dataset.j);
  const fibres = [...stage.querySelectorAll(".fib")];
  const dets = [...stage.querySelectorAll(".det")];
  const tip = stage.querySelector(".chip-tip");
  const byKey = Object.fromEntries(data.targets.map((t) => [t.key, t]));
  const randoms = data.targets.filter((t) => t.key.startsWith("random-"));
  const targetButtons = [...document.querySelectorAll("[data-target]")];
  const inputButtons = [...document.querySelectorAll("[data-input]")];
  const cells = [...document.querySelectorAll("[data-cell]")];
  const bars = [...document.querySelectorAll("[data-bar]")];
  const read = (name) => document.querySelector(`[data-read="${name}"]`);
  const count = document.querySelector("[data-random-count]");
  const bright = (p) => Math.pow(Math.max(0, Math.min(1, p)), 0.55); // weak light stays visible
  let target = byKey[data.default];
  let random = 0;
  let input = 0;
  let lit = false;
  let touched = 0; // when the visitor last chose something: the demo waits for a while after it

  function apply() {
    const light = lit ? target.light[input] : null;
    pieces.forEach((piece, k) => piece.style.setProperty("--o", light ? bright(light[k]).toFixed(3) : "0"));
    heaters.forEach((heater, j) => heater.style.setProperty("--h", lit ? target.heaters[j].toFixed(3) : "0"));
    fibres.forEach((fibre) => fibre.classList.toggle("is-lit", lit && Number(fibre.dataset.row) === input));
    const out = target.out[input];
    dets.forEach((det) => det.style.setProperty("--o", lit ? bright(out[Number(det.dataset.row)]).toFixed(3) : "0"));
    cells.forEach((cell) => {
      const [o, i] = cell.dataset.cell.split("-").map(Number);
      cell.style.setProperty("--v", lit ? target.out[i][o].toFixed(3) : "0");
      cell.classList.toggle("is-col", i === input);
    });
    bars.forEach((bar) => bar.querySelector("b").style.setProperty("--v", lit ? out[Number(bar.dataset.bar)].toFixed(3) : "0"));
    read("fidelity").textContent = target.fidelity === null ? "no target" : target.fidelity.toFixed(7);
    read("total").textContent = target.total.toFixed(1);
    targetButtons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.target === target.key.replace(/-\d+$/, ""))));
    inputButtons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.input) === input)));
    if (count) count.textContent = target.key.startsWith("random-") ? `${random + 1}/${randoms.length}` : "";
  }

  function chooseTarget(key) {
    if (key === "random") {
      random = target.key.startsWith("random-") ? (random + 1) % randoms.length : random;
      target = randoms[random];
    } else {
      target = byKey[key];
    }
    apply();
  }
  function chooseInput(i) {
    if (i === input) return;
    input = i;
    apply();
  }

  targetButtons.forEach((b) => b.addEventListener("click", () => {
    touched = performance.now();
    chooseTarget(b.dataset.target);
  }));
  inputButtons.forEach((b) => b.addEventListener("click", () => {
    touched = performance.now();
    chooseInput(Number(b.dataset.input));
  }));

  // ---- the waveguide under the pointer is the input ----
  for (const hit of stage.querySelectorAll(".hit")) {
    hit.addEventListener("pointerenter", (event) => {
      if (event.pointerType === "touch") return;
      touched = performance.now();
      chooseInput(Number(hit.dataset.row));
    });
    hit.addEventListener("click", () => {
      touched = performance.now();
      chooseInput(Number(hit.dataset.row));
    });
  }

  // ---- the tip ----
  function place(event) {
    const box = stage.getBoundingClientRect();
    tip.style.left = `${Math.max(150, Math.min(box.width - 150, event.clientX - box.left))}px`;
    tip.style.top = `${event.clientY - box.top}px`;
  }
  function showHeater(heater, event) {
    const j = Number(heater.dataset.j);
    tip.querySelector("b").textContent = `Heater ${heater.dataset.name}`;
    tip.querySelector("span").textContent = `sets ${heater.dataset.what} · ${lit ? target.mW[j].toFixed(2) : "0"} mW of ${data.P2pi.toFixed(1)}`;
    tip.querySelector("ul").replaceChildren();
    place(event);
    tip.hidden = false;
  }
  function showBlock(block, event) {
    const card = cards[block.dataset.block];
    if (!card) return;
    tip.querySelector("b").textContent = card.name;
    tip.querySelector("span").textContent = card.done ? `${card.direction} · simulated · open the chapter` : `${card.direction} · planned · it needs`;
    tip.querySelector("ul").replaceChildren(...(card.done ? [] : card.needs).map((d) => {
      const li = document.createElement("li");
      li.textContent = `${d.name}${d.done ? ", simulated" : ""}`;
      li.classList.toggle("is-done", d.done);
      return li;
    }));
    place(event);
    tip.hidden = false;
  }
  stage.addEventListener("pointermove", (event) => {
    const heater = event.target.closest && event.target.closest(".ht");
    const block = event.target.closest && event.target.closest(".blk-planned, .blk-sim");
    if (heater) showHeater(heater, event);
    else if (block) showBlock(block, event);
    else tip.hidden = true;
  });
  stage.addEventListener("pointerleave", () => (tip.hidden = true));
  for (const block of stage.querySelectorAll(".blk-planned")) {
    block.addEventListener("focus", () => {
      const box = block.getBoundingClientRect();
      showBlock(block, { clientX: box.left + box.width / 2, clientY: box.top + 20 });
      block.classList.add("is-pointed");
    });
    block.addEventListener("blur", () => {
      tip.hidden = true;
      block.classList.remove("is-pointed");
    });
  }

  // ---- the tilt, as the wafer of the home page ----
  if (!calm && fine) {
    let frame = 0;
    let tx = 0;
    let ty = 0;
    let x = 0;
    let y = 0;
    const step = () => {
      x += (tx - x) * 0.07;
      y += (ty - y) * 0.07;
      chip.style.setProperty("--tx", `${x.toFixed(2)}deg`);
      chip.style.setProperty("--ty", `${y.toFixed(2)}deg`);
      chip.style.setProperty("--gx", `${(50 + x * 7).toFixed(1)}%`);
      chip.style.setProperty("--gy", `${(25 - y * 6).toFixed(1)}%`);
      frame = Math.abs(tx - x) + Math.abs(ty - y) > 0.02 ? requestAnimationFrame(step) : 0;
    };
    stage.addEventListener("pointermove", (event) => {
      const box = stage.getBoundingClientRect();
      tx = ((event.clientX - box.left) / box.width - 0.5) * 7;
      ty = ((event.clientY - box.top) / box.height - 0.5) * -6;
      if (!frame) frame = requestAnimationFrame(step);
    });
    stage.addEventListener("pointerleave", () => {
      tx = 0;
      ty = 0;
      if (!frame) frame = requestAnimationFrame(step);
    });
  }

  // ---- the chip comes in, then its light comes on; while nobody chooses, the light moves from input to input ----
  let visible = false;
  let demo = 0;
  const tick = () => {
    if (visible && !document.hidden && performance.now() - touched > 9000) chooseInput((input + 1) % data.inputs);
  };
  const start = () => {
    stage.classList.add("is-in");
    if (lit) return;
    window.setTimeout(() => {
      lit = true;
      apply();
    }, calm ? 0 : 650);
  };
  apply();
  if (calm || !("IntersectionObserver" in window)) {
    start();
    return;
  }
  new IntersectionObserver(
    (entries) => {
      visible = entries.some((e) => e.isIntersecting);
      if (visible) start();
      if (visible && !demo) demo = window.setInterval(tick, 3800);
      if (!visible && demo) {
        window.clearInterval(demo);
        demo = 0;
      }
    },
    { threshold: 0.25 },
  ).observe(stage);
})();

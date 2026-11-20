// photonics-layout-cookbook: the layers of the layout lifting into their levels, and the viewer of the same picture.
// On the home page the picture lies flat until the statement beside it comes up the screen, and is fully lifted when
// about 60 % of its words have lit up (LEAD), so the heights are on show while the rest is read. In the viewer the
// reader moves the lift with a slider and switches to true scale. A level under
// the pointer, under the finger, in focus or chosen in the key brightens; the others dim, and its name and heights
// are read in the place under the picture. Used by every picture of this kind on the page; one copy runs.
// It needs assets/near.js, loaded first (the home page does; the viewers of the chapters need nothing else).
(() => {
  "use strict";
  if (window.COOKBOOK_LAYERS) return; // a page that names this file twice: the first copy does the work
  window.COOKBOOK_LAYERS = true;
  const helpers = window.COOKBOOK_NEAR;
  const calm = Boolean(window.COOKBOOK_CALM);
  const params = new URLSearchParams(location.search); // for screenshots: ?lift=0..1 fixes the lift, ?layer=<level> points at it
  const clamp01 = (value) => (helpers ? helpers.clamp(value || 0, 0, 1) : Math.min(1, Math.max(0, value || 0)));
  const fixed = params.has("lift") ? clamp01(parseFloat(params.get("lift"))) : null;
  const shown = params.get("layer") || "";
  const roots = [...document.querySelectorAll("[data-layers]")];
  if (!roots.length) return;

  const states = roots.map((root) => {
    const source = root.dataset.follow === "statement" ? (root.closest(".band") || document).querySelector("[data-statement]") : null;
    return { root, source, slider: root.querySelector("[data-lift]"), readout: root.querySelector("[data-readout]"), near: false, lift: NaN, active: "", pinned: "" };
  });
  // the elements of one level, compared as values: a level name is never put into a selector
  const levelNodes = (root, key) => [...root.querySelectorAll("[data-level]")].filter((element) => element.dataset.level === key);

  // ---- the lift: the same measure as the words of the statement in site.js, divided by LEAD, so the picture is
  // fully lifted (and its height axis shown, from a lift of 0.9) when the statement is 60 % read: a reader who stops
  // with the heading near the top of the screen sees the heights ----------------------------------------------------
  const LEAD = 0.6;
  function progressOf(element) {
    const box = element.getBoundingClientRect();
    return clamp01((innerHeight * 0.92 - box.top) / (innerHeight * 0.47 + box.height / 2));
  }
  function setLift(state, value) {
    const next = Math.round(clamp01(value) * 1000) / 1000;
    if (next === state.lift) return;
    state.lift = next;
    state.root.style.setProperty("--lift", String(next));
    const label = next === 0 ? "as drawn" : next === 1 ? "lifted" : `${Math.round(next * 100)} %`;
    if (state.slider) {
      if (Number(state.slider.value) !== next) state.slider.value = String(next);
      state.slider.setAttribute("aria-valuetext", label);
    }
    const out = state.root.querySelector("[data-lift-out]");
    if (out) out.textContent = label;
  }

  // ---- a level in focus: its plates, ticks, key entry or probe, and its line in the readout ----------------------
  // announce: a deliberate choice (a click, Enter, Escape) is read out; pointing and focus only show it
  function activate(state, key, announce = false) {
    const { root } = state;
    if (key === state.active && !announce) return;
    state.active = key;
    root.classList.toggle("has-active", Boolean(key));
    root.querySelectorAll(".is-on").forEach((element) => element.classList.remove("is-on"));
    if (key) levelNodes(root, key).forEach((element) => element.classList.add("is-on"));
    root.querySelectorAll("[data-info]").forEach((info) => {
      info.hidden = info.dataset.info !== key;
    });
    const hint = root.querySelector(".readout-hint");
    if (hint) hint.hidden = Boolean(key);
    if (state.readout) state.readout.setAttribute("aria-live", announce ? "polite" : "off");
  }
  const levelOf = (target) => {
    const element = target && target.closest ? target.closest("[data-level]") : null;
    return element ? element.dataset.level : "";
  };
  function setScale(state, mode) {
    state.root.classList.toggle("is-true", mode === "true");
    state.root.querySelectorAll("[data-scale]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.scale === mode));
    });
  }

  for (const state of states) {
    const { root } = state;
    // the pointer: a level under it is in focus; a click pins it, a second click releases it
    root.addEventListener("pointerover", (event) => {
      if (!state.pinned && event.pointerType !== "touch") activate(state, levelOf(event.target));
    });
    root.addEventListener("pointerleave", () => {
      if (!state.pinned) activate(state, "");
    });
    root.addEventListener("click", (event) => {
      if (event.target.closest && event.target.closest("[data-scale], [data-lift]")) return; // the controls are not levels
      const key = levelOf(event.target);
      if (!key || key === state.pinned) {
        state.pinned = "";
        activate(state, "", true);
        return;
      }
      state.pinned = key;
      activate(state, key, true);
    });
    // the keyboard: an axis label, a key entry or a probe is a button; focusing it is pointing at it
    root.addEventListener("focusin", (event) => {
      const key = levelOf(event.target);
      if (key && !state.pinned) activate(state, key);
    });
    root.addEventListener("focusout", (event) => {
      if (event.relatedTarget && root.contains(event.relatedTarget)) return;
      if (!state.pinned) activate(state, "");
    });
    // the viewer: the slider moves the lift, the switch the scale
    if (state.slider) {
      state.slider.addEventListener("input", () => setLift(state, parseFloat(state.slider.value)));
    }
    root.querySelectorAll("[data-scale]").forEach((button) => {
      button.addEventListener("click", () => setScale(state, button.dataset.scale));
    });
    if (shown && levelNodes(root, shown).length) {
      state.pinned = shown;
      activate(state, shown, true);
    }
  }
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    for (const state of states) {
      if (state.pinned) {
        state.pinned = "";
        activate(state, "", true);
      }
    }
  });

  // ---- the lift as the statement is read. Nothing moves, and no listener runs, while the picture is away ------------
  let queued = false;
  function lift() {
    queued = false;
    for (const state of states) if (state.near && state.source) setLift(state, progressOf(state.source) / LEAD);
  }
  function schedule() {
    if (!queued) {
      queued = true;
      requestAnimationFrame(lift);
    }
  }
  // the scroll and resize listeners exist only while a picture that follows the statement is near the screen
  let watching = false;
  function watch(on) {
    if (on === watching) return;
    watching = on;
    const method = on ? "addEventListener" : "removeEventListener";
    window[method]("scroll", schedule, { passive: true });
    window[method]("resize", schedule, { passive: true });
    if (on) schedule();
  }
  const followers = states.filter((state) => state.source);
  const anyNear = () => states.some((state) => state.near);

  if (fixed !== null) {
    for (const state of states) setLift(state, fixed);
  } else if (calm) {
    for (const state of states) setLift(state, 1); // reduced motion or ?still: the final state, at once
  } else {
    for (const state of states) if (!state.source) setLift(state, 1); // the viewer: fully lifted until the reader moves the slider
    if (helpers) {
      for (const state of followers) {
        helpers.whenNear(
          state.root,
          (on) => {
            state.near = on;
            watch(anyNear());
            schedule();
          },
          "30%",
        );
      }
    } else {
      for (const state of followers) state.near = true; // no helper: the picture follows at once
      watch(anyNear());
    }
  }
})();

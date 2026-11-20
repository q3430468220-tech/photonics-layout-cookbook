// photonics-layout-cookbook: the mesh behind the footer. The drawing is loaded (assets/data/mesh.js) when the footer comes
// near the screen. When the footer first shows, the light comes on column by column from the left. While the pointer
// moves over the footer, its height picks the input: the nearest of the eight waveguides. A tap does so on a touch
// screen, and a scroll does not. Nothing listens while the footer is far away.
(() => {
  "use strict";

  // the input whose waveguide is nearest to the height y, for a drawing of the given height in user units (viewH) that
  // starts at the pixel top and is scaled by `scale` pixels per unit
  function nearest(rows, top, scale, y) {
    let best = 0;
    let gap = Infinity;
    rows.forEach((row, i) => {
      const d = Math.abs(top + row * scale - y);
      if (d < gap) {
        gap = d;
        best = i;
      }
    });
    return best;
  }

  // under node (the tests) only the function is needed
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { nearest };
    return;
  }

  const host = document.querySelector("[data-mesh]");
  const near = window.COOKBOOK_NEAR;
  if (!host || !near) return;
  const foot = host.closest(".foot") || host.parentElement;
  const calm = Boolean(window.COOKBOOK_CALM);
  const here = document.currentScript ? document.currentScript.src : "";
  let drawing = null; // the data of the drawing, once it is loaded
  let lights = []; // the light of each piece, in the order of the powers
  let input = 0; // the input that is lit
  let lit = false; // the light has come on: the footer has shown
  let loading = false;
  let stop = null; // the listeners of the pointer, while the footer is near
  let frame = 0;
  let pointerY = null;
  let touch = null; // where a touch started, to tell a tap from the start of a scroll

  // the light of one input: every piece takes its power; the stylesheet carries the change column by column
  function light(k) {
    const powers = drawing.powers[k];
    for (let j = 0; j < lights.length; j++) lights[j].style.setProperty("--o", (powers[j] / 1000).toFixed(3));
    input = k;
  }

  // the input of a height: the drawing is measured where it is on the screen now, so no listener follows the page
  function choose(y) {
    const svg = host.querySelector("svg");
    if (!svg || !drawing) return;
    const box = svg.getBoundingClientRect();
    const k = nearest(drawing.rows, box.top, box.height / drawing.viewH, y);
    if (k !== input) light(k);
  }

  function build(data) {
    drawing = data;
    host.innerHTML = data.svg;
    lights = [...host.querySelectorAll(".mesh-lit")];
    const show = () => {
      lit = true;
      if (calm) light(drawing.default);
      else requestAnimationFrame(() => {
        void host.getBoundingClientRect(); // the pieces are dark before this frame, so the light runs from there
        light(drawing.default);
      });
    };
    if (calm || !("IntersectionObserver" in window)) {
      show();
      return;
    }
    const seen = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        seen.disconnect();
        show();
      },
      { threshold: 0.15 },
    );
    seen.observe(foot);
  }

  function load() {
    if (loading) return;
    loading = true;
    const url = new URL("data/mesh.js", here || window.location.href);
    url.search = new URL(here || window.location.href).search; // the version of the page
    const script = document.createElement("script");
    script.src = url.href;
    script.onload = () => build(window.COOKBOOK_MESH_DRAWING);
    script.onerror = () => {
      loading = false;
    };
    document.head.appendChild(script);
  }

  // the pointer, while the footer is near: a frame at most per move, and only when the input changes
  function listen(on) {
    if (on && !stop) {
      const control = new AbortController();
      const options = { signal: control.signal };
      foot.addEventListener(
        "pointermove",
        (event) => {
          if (event.pointerType === "touch" || !lit) return;
          pointerY = event.clientY;
          if (!frame) {
            frame = requestAnimationFrame(() => {
              frame = 0;
              if (pointerY !== null) choose(pointerY);
            });
          }
        },
        options,
      );
      foot.addEventListener(
        "pointerdown",
        (event) => {
          if (event.pointerType === "touch") touch = { x: event.clientX, y: event.clientY };
        },
        options,
      );
      foot.addEventListener(
        "pointerup",
        (event) => {
          if (event.pointerType !== "touch" || !touch || !lit) return;
          const travel = Math.hypot(event.clientX - touch.x, event.clientY - touch.y);
          touch = null;
          if (travel < 6) choose(event.clientY);
        },
        options,
      );
      foot.addEventListener("pointercancel", () => (touch = null), options);
      stop = control;
    } else if (!on && stop) {
      stop.abort();
      stop = null;
      touch = null;
    }
  }

  near.whenNear(
    foot,
    (now) => {
      if (now && !drawing) load();
      listen(now);
    },
    "400px",
  );
})();

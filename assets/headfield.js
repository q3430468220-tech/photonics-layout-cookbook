// photonics-layout-cookbook: the moving fringes in the head of a device page.
// The stripes are a layer over the picture (assets/css/30-headfield.css). This script only says when they run: for
// three seconds each time the head comes on the screen, and for as long as the pointer is on it, and three seconds
// after it leaves. Nothing runs while the head is off the screen, and nothing is drawn by the script.
(() => {
  "use strict";
  if (window.COOKBOOK_CALM) return; // reduced motion or ?still: the still picture only
  const near = window.COOKBOOK_NEAR; // near.js is loaded before this script by the page
  const plates = document.querySelectorAll(".headfield[data-travel]");
  if (!near || !plates.length) return;
  const TRAVEL = 3000; // milliseconds of fringes each time the head comes on the screen

  for (const plate of plates) {
    let timer = 0;
    let pointed = false;
    const run = () => {
      clearTimeout(timer);
      plate.classList.add("is-moving");
      // while the pointer is on the plate the fringes go on; otherwise they stop after TRAVEL
      timer = pointed ? 0 : setTimeout(() => plate.classList.remove("is-moving"), TRAVEL);
    };
    const stop = () => {
      clearTimeout(timer);
      timer = 0;
      plate.classList.remove("is-moving");
    };
    near.whenNear(plate, (on) => (on ? run() : stop()), "0px");
    plate.addEventListener("pointerenter", () => {
      pointed = true;
      run();
    });
    plate.addEventListener("pointerleave", () => {
      pointed = false;
      run();
    });
  }
})();

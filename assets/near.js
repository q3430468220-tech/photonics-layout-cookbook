// photonics-layout-cookbook: two small helpers that the moving parts of the pages share.
// A page that has such a part loads this file before the script of the part.
//
//   COOKBOOK_NEAR.clamp(value, low, high)
//   COOKBOOK_NEAR.whenNear(element, callback, margin)
//       callback(true) when the element comes near the screen, callback(false) when it leaves again.
//       margin: how far outside the screen counts as near, as a CSS length ("200px" if left out).
//       Where a browser cannot watch, callback(true) is called once and the part simply stays ready.
//       Returns a function that ends the watching.
(() => {
  "use strict";
  if (window.COOKBOOK_NEAR) return; // loaded twice: the first copy stays
  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  function whenNear(element, callback, margin = "200px") {
    if (!element) return () => {};
    if (!("IntersectionObserver" in window)) {
      callback(true);
      return () => {};
    }
    let near = null;
    const watcher = new IntersectionObserver(
      (entries) => {
        const now = entries.some((entry) => entry.isIntersecting);
        if (now !== near) {
          near = now;
          callback(now);
        }
      },
      { rootMargin: `${margin} 0px` },
    );
    watcher.observe(element);
    return () => watcher.disconnect();
  }
  window.COOKBOOK_NEAR = { clamp, whenNear };
})();

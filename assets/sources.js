// Where a number comes from.  Each number with a source (data-source) gets a button around its text.  The text node itself
// is moved into the button, so the count-up of site.js, which writes into the number's first child, now writes into the
// button; the number still counts up.  A press on the button opens the panel of its group (.src-group > .src-panel): the
// panel is part of the page flow, directly under the row of numbers, so it pushes what follows down and never covers a
// number or the line of files.  It shows the template of that number (the line of the kept summary, the first line of its
// file, the links), and a small pointer above it marks the number the panel belongs to.  The pointer is placed again when
// the window changes size.  Escape, a press elsewhere, a second press on the number, or leaving the panel with the keyboard
// closes it.  Nothing listens while the panel is closed.
(function () {
  "use strict";
  const picks = [...document.querySelectorAll("[data-source]")];
  if (!picks.length) return;
  let open = null; // { button, panel }: the number whose panel is open
  let frame = 0;

  const panels = new Set();
  picks.forEach((element) => {
    const text = element.firstChild;
    const group = element.closest(".src-group");
    const panel = group && group.querySelector(":scope > .src-panel");
    if (!text || text.nodeType !== Node.TEXT_NODE || !panel) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "src-pick";
    button.setAttribute("aria-label", element.dataset.sourceLabel || "Where this number comes from");
    button.setAttribute("aria-haspopup", "true");
    button.setAttribute("aria-expanded", "false");
    element.insertBefore(button, text);
    button.appendChild(text);
    button.addEventListener("click", () => (open && open.button === button ? close(true) : show(button, element, panel)));
    if (!panels.has(panel)) {
      panels.add(panel);
      // leaving the panel with the keyboard closes it; the focus goes on where the reader is going
      panel.addEventListener("focusout", (event) => {
        const next = event.relatedTarget;
        if (!open || open.panel !== panel) return;
        if (next && (panel.contains(next) || next.closest(".src-pick"))) return;
        close(false);
      });
    }
  });

  function show(button, element, panel) {
    const template = document.getElementById(element.dataset.source);
    if (!template) return;
    if (open) close(false);
    panel.querySelector(".src-body").replaceChildren(template.content.cloneNode(true));
    panel.setAttribute("aria-label", element.dataset.sourceLabel || "Where this number comes from");
    button.setAttribute("aria-expanded", "true");
    button.setAttribute("aria-controls", panel.id);
    panel.hidden = false;
    open = { button, panel };
    place();
    panel.focus({ preventScroll: true }); // the reader hears the name of the panel
    const shown = panel.getBoundingClientRect();
    if (shown.bottom > innerHeight || shown.top < 0) panel.scrollIntoView({ block: "nearest" });
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("keydown", key, true);
    window.addEventListener("resize", resize);
  }

  // the panel moves along its group, still in the flow, so that the pointer stands under the middle of the number; the
  // pointer stays inside the panel
  function place() {
    if (!open) return;
    const { button, panel } = open;
    const at = button.getBoundingClientRect();
    const group = panel.parentElement.getBoundingClientRect();
    const width = panel.offsetWidth;
    const wanted = at.left + at.width / 2 - group.left - 28; // the pointer 28 px from the panel's left edge
    panel.style.marginLeft = Math.max(0, Math.min(wanted, group.width - width)) + "px";
    const box = panel.getBoundingClientRect();
    const x = Math.min(width - 14, Math.max(14, at.left + at.width / 2 - box.left));
    panel.style.setProperty("--caret", x + "px");
  }

  function resize() {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      place();
    });
  }

  function close(back) {
    if (!open) return;
    const { button, panel } = open;
    open = null;
    panel.hidden = true;
    button.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", outside, true);
    document.removeEventListener("keydown", key, true);
    window.removeEventListener("resize", resize);
    if (back) button.focus({ preventScroll: true });
  }

  function outside(event) {
    if (open.panel.contains(event.target) || event.target.closest(".src-pick")) return;
    close(false);
  }

  function key(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    }
  }
})();

// photonics-layout-cookbook: the device library — the devices that use a material, or that a solver simulates.
// A chip of the head chooses; the cards that match keep their light and the others step back.  A second click on the
// same chip shows all again.
(() => {
  "use strict";
  const box = document.querySelector("[data-lib-filter]");
  if (!box) return;
  const buttons = [...box.querySelectorAll("[data-filter]")];
  const cards = [...document.querySelectorAll(".card.device[data-mat]")];
  const note = box.querySelector("[data-lib-note]");
  const empty = note.textContent;
  for (const button of buttons) {
    button.addEventListener("click", () => {
      const on = button.getAttribute("aria-pressed") !== "true";
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b === button && on)));
      if (!on) {
        cards.forEach((card) => card.classList.remove("is-match", "is-muted"));
        note.textContent = empty;
        return;
      }
      const [kind, value] = button.dataset.filter.split(":");
      let found = 0;
      let done = 0;
      for (const card of cards) {
        const has = (card.dataset[kind] || "").split(" ").includes(value);
        card.classList.toggle("is-match", has);
        card.classList.toggle("is-muted", !has);
        if (has) {
          found += 1;
          if (!card.classList.contains("is-planned")) done += 1;
        }
      }
      const name = button.textContent.trim();
      const what = kind === "mat" ? `use ${name}` : `are simulated with ${value}`;
      note.textContent = found
        ? `${found} of ${cards.length} devices ${what}; ${done ? `${done} of them ${done === 1 ? "is" : "are"} done` : "none of them is done yet"}.`
        : `No device ${kind === "mat" ? `uses ${name}` : `is simulated with ${value}`} yet.`;
    });
  }
})();

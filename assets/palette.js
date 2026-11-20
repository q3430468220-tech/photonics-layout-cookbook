// photonics-layout-cookbook: the search over pages, sections and devices, opened with Ctrl+K (Cmd+K on a Mac), with "/",
// or from the button of the top bar.  The index is a script of the site (website/fx/palette.py), loaded the first time
// the search opens.  A result is a link: the dialog closes when one is followed.
(() => {
  "use strict";
  // What a key press asks for: "open", "close" or "" (nothing).  Ctrl+K and Cmd+K work everywhere, also in a field or a
  // slider; "/" opens the search only where the reader is not typing.  A pure function, so that the tests can run it.
  const keyAction = ({ key, ctrl = false, meta = false, alt = false, shift = false }, { typing = false, open = false } = {}) => {
    const k = String(key).toLowerCase();
    if (k === "k" && (ctrl || meta) && !alt && !shift) return open ? "close" : "open";
    if (k === "/" && !ctrl && !meta && !alt && !open && !typing) return "open";
    return "";
  };
  window.COOKBOOK_KEY_ACTION = keyAction;

  const box = document.querySelector("[data-palette]");
  const openers = [...document.querySelectorAll("[data-palette-open]")];
  if (!box || !openers.length) return;
  const input = box.querySelector("[data-palette-input]");
  const list = box.querySelector("[data-palette-list]");
  const say = box.querySelector("[data-palette-status]");
  const home = new URL(box.dataset.root, document.baseURI); // every address of the index is relative to the front page
  const LIMIT = 8;
  const GROUPS = [
    ["pages", "Pages", "book"],
    ["sections", "Sections", "file"],
    ["devices", "Devices", "grid"],
  ];
  const WEIGHT = { pages: 4, sections: 2, devices: 4 }; // a title counts more than a section, a section more than a description
  const PAUSE = 400; // ms without a key before the number of results is announced
  let entries = null; // the index, prepared for matching
  let loading = false;
  let shown = []; // the rows on the screen, in order
  let active = -1; // the row the keys have reached
  let pointed = null;
  let frame = 0;
  let announced = 0; // the timer of the status line
  let returnTo = null; // where the focus was when the search opened

  // ---- text for matching: lower case, without accents; each letter keeps its place in the text as written ----
  const plain = (char) => char.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const fold = (text) => {
    let folded = "";
    const origin = [];
    for (let i = 0; i < text.length; i++) {
      const letters = plain(text[i]);
      for (let k = 0; k < letters.length; k++) {
        folded += letters[k];
        origin.push(i);
      }
    }
    return { folded, origin };
  };
  const field = (text, weight) => ({ text, weight, ...fold(text) });
  const occurrences = (folded, word) => {
    const found = [];
    for (let i = folded.indexOf(word); i >= 0; i = folded.indexOf(word, i + 1)) found.push(i);
    return found;
  };
  // a word begins at i when the letter before it is not a letter or a digit
  const begins = (folded, i) => i === 0 || !/[\p{L}\p{N}]/u.test(folded[i - 1]);

  const prepare = (index) => {
    const ready = {};
    for (const kind of Object.keys(WEIGHT)) {
      ready[kind] = (index[kind] || []).map((item) => {
        const title = field(item.t, WEIGHT[kind]);
        const fields = [title, field(item.w, 1)];
        if (item.d) fields.push(field(item.d, 1));
        return { ...item, kind, title, fields };
      });
    }
    return ready;
  };

  // every word must occur in one of the fields of a row; a word at the start of a word counts double
  const score = (entry, words) => {
    let total = 0;
    for (const word of words) {
      let best = 0;
      for (const f of entry.fields) {
        const found = occurrences(f.folded, word);
        if (found.length) best = Math.max(best, f.weight * (found.some((i) => begins(f.folded, i)) ? 2 : 1));
      }
      if (!best) return 0;
      total += best;
    }
    return total;
  };
  // the positions, in the text as written, of the letters that the words match
  const marks = (f, words) => {
    const set = new Set();
    for (const word of words) {
      for (const i of occurrences(f.folded, word)) {
        for (let k = 0; k < word.length; k++) set.add(f.origin[i + k]);
      }
    }
    return set;
  };
  // the text as written, with the matching letters in a mark
  const lettered = (text, set) => {
    const out = document.createDocumentFragment();
    let from = 0;
    while (from < text.length) {
      const on = set.has(from);
      let to = from + 1;
      while (to < text.length && set.has(to) === on) to++;
      if (on) {
        const mark = document.createElement("mark");
        mark.textContent = text.slice(from, to);
        out.append(mark);
      } else {
        out.append(text.slice(from, to));
      }
      from = to;
    }
    return out;
  };

  // the rows for what is typed: the best matches, or every page when nothing is typed
  const find = (words) => {
    if (!words.length) return { total: 0, best: entries.pages };
    const hits = [];
    for (const kind of Object.keys(WEIGHT)) {
      for (const entry of entries[kind]) {
        const s = score(entry, words);
        if (s) hits.push({ entry, s });
      }
    }
    hits.sort((a, b) => b.s - a.s);
    return { total: hits.length, best: hits.slice(0, LIMIT).map((hit) => hit.entry) };
  };

  const row = (entry, words, icon) => {
    const link = document.createElement("a");
    link.id = `palette-row-${shown.length}`;
    link.className = "palette-row";
    link.setAttribute("role", "option");
    link.setAttribute("aria-selected", "false");
    link.setAttribute("tabindex", "-1");
    link.href = new URL(entry.u, home).href;
    const badge = document.createElement("span");
    badge.className = "palette-ico";
    badge.innerHTML = `<svg class="ico" aria-hidden="true"><use href="#i-${icon}"/></svg>`;
    const main = document.createElement("span");
    main.className = "palette-main";
    const title = document.createElement("span");
    title.className = "palette-title";
    title.append(lettered(entry.t, marks(entry.title, words)));
    const where = document.createElement("span");
    where.className = "palette-where";
    where.textContent = entry.w;
    main.append(title, where);
    link.append(badge, main);
    if (entry.kind === "devices") {
      const pill = document.createElement("span");
      pill.className = entry.s ? "pill pill-done" : "pill";
      pill.textContent = entry.s ? "simulated" : "planned";
      link.append(pill);
    }
    shown.push(link);
    return link;
  };

  // the status line: written at once when nothing is typed, and after a pause otherwise, so that the screen reader
  // announces the count once per pause and not once per key
  const announce = (text, now) => {
    clearTimeout(announced);
    if (now) {
      say.textContent = text;
      return;
    }
    announced = setTimeout(() => {
      say.textContent = text;
    }, PAUSE);
  };

  const render = () => {
    if (!entries) return;
    const typed = input.value.trim();
    const words = fold(typed).folded.split(/\s+/).filter(Boolean);
    const found = find(words);
    list.textContent = "";
    shown = [];
    active = -1;
    for (const [kind, name, icon] of GROUPS) {
      const group = found.best.filter((entry) => entry.kind === kind);
      if (!group.length) continue;
      const section = document.createElement("div");
      section.setAttribute("role", "group");
      section.setAttribute("aria-label", name);
      const head = document.createElement("p");
      head.className = "palette-group";
      head.setAttribute("aria-hidden", "true");
      head.textContent = name;
      section.append(head, ...group.map((entry) => row(entry, words, icon)));
      list.append(section);
    }
    if (!words.length) {
      announce(`Type to search ${entries.pages.length} pages, ${entries.sections.length} sections and ${entries.devices.length} devices.`, true);
    } else if (!found.total) {
      announce(`Nothing matches “${typed}”. Try a shorter word, or the name of a device.`, false);
    } else if (found.total > LIMIT) {
      announce(`The first ${LIMIT} of ${found.total} results. Type more to narrow them.`, false);
    } else {
      announce(`${found.total} ${found.total === 1 ? "result" : "results"}.`, false);
    }
    select(0, false);
  };

  // the row that the keys or the pointer have reached is marked, and the input names it
  const select = (index, scroll) => {
    if (!shown.length) {
      active = -1;
      input.removeAttribute("aria-activedescendant");
      return;
    }
    if (shown[active]) {
      shown[active].classList.remove("is-on");
      shown[active].setAttribute("aria-selected", "false");
    }
    active = (index + shown.length) % shown.length;
    const link = shown[active];
    link.classList.add("is-on");
    link.setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", link.id);
    if (scroll) link.scrollIntoView({ block: "nearest" });
  };

  const ready = () => {
    if (!window.COOKBOOK_SEARCH) {
      say.textContent = "The index of the site could not be read.";
      return;
    }
    entries = prepare(window.COOKBOOK_SEARCH);
    render();
  };
  // the index comes in a script element when the search is first opened (a page opened from disk cannot fetch it)
  const load = () => {
    if (entries || loading) return;
    if (window.COOKBOOK_SEARCH) {
      ready();
      return;
    }
    loading = true;
    say.textContent = "Loading the index…";
    const script = document.createElement("script");
    script.src = box.dataset.index;
    script.onload = ready;
    script.onerror = () => {
      say.textContent = "The index of the site could not be loaded.";
    };
    document.head.append(script);
  };

  const open = () => {
    if (!box.open) {
      const was = document.activeElement;
      returnTo = was && !box.contains(was) ? was : null;
      box.showModal();
    }
    input.focus();
    input.select();
    load();
    render();
  };
  // the focus goes back to where the reader was when the search opened (unless a link was followed)
  const close = (back = true) => {
    if (!box.open) return;
    box.close();
    clearTimeout(announced);
    if (back && returnTo && returnTo.isConnected) returnTo.focus({ preventScroll: true });
    returnTo = null;
  };

  openers.forEach((button) => button.addEventListener("click", open));
  box.querySelector("[data-palette-close]").addEventListener("click", () => close());
  input.addEventListener("input", render);
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      select(active + (event.key === "ArrowDown" ? 1 : -1), true);
    } else if (event.key === "Enter" && shown[active]) {
      event.preventDefault();
      shown[active].click();
    }
  });
  // the pointer marks the row under it; the work is done once per frame
  list.addEventListener("pointermove", (event) => {
    pointed = event.target.closest(".palette-row");
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      const i = shown.indexOf(pointed);
      if (i >= 0 && i !== active) select(i, false);
    });
  });
  list.addEventListener("click", (event) => {
    if (event.target.closest("a")) close(false); // the link is followed after the dialog has closed
  });
  box.addEventListener("click", (event) => {
    if (event.target === box) close(); // a click on the dimmed ground
  });

  // a field that the reader types in keeps its keys
  const typing = (element) =>
    element instanceof HTMLElement && (element.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(element.tagName));
  document.addEventListener("keydown", (event) => {
    const keys = { key: event.key, ctrl: event.ctrlKey, meta: event.metaKey, alt: event.altKey, shift: event.shiftKey };
    const action = keyAction(keys, { typing: typing(event.target), open: box.open });
    if (!action) return;
    event.preventDefault();
    if (action === "open") open();
    else close();
  });
})();

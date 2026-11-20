// photonics-layout-cookbook: learning on the page.
//
//   terms        a term that the build marked (website/data/glossary.json) shows its definition when the pointer or
//                the focus rests on it.
//   check        "Check yourself" becomes one card per question: the answer opens under its question, and the reader
//                says whether they had it.  What they said is kept in this browser, per chapter; the rail shows it.
//   progress     a link to a chapter whose questions were all answered right gets a mark, wherever it stands.
(() => {
  "use strict";
  const KEY = "cookbook-check:";
  const where = (path) => path.replace(/index\.html$/, "");
  const read = (path) => {
    try {
      return JSON.parse(localStorage.getItem(KEY + where(path)) || "null");
    } catch (error) {
      return null;
    }
  };
  const write = (path, value) => {
    try {
      localStorage.setItem(KEY + where(path), JSON.stringify(value));
    } catch (error) {
      /* a private window keeps nothing; the page works the same */
    }
  };

  // ---- the terms ----
  const terms = [...document.querySelectorAll(".gloss[data-def]")];
  if (terms.length) {
    const pop = document.createElement("div");
    pop.className = "gloss-pop";
    pop.setAttribute("role", "tooltip");
    pop.hidden = true;
    document.body.appendChild(pop);
    const show = (term) => {
      pop.textContent = term.dataset.def;
      pop.hidden = false;
      const r = term.getBoundingClientRect();
      const w = pop.offsetWidth;
      const left = Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width / 2 - w / 2));
      const above = r.top > pop.offsetHeight + 20;
      pop.style.left = `${left + scrollX}px`;
      pop.style.top = `${(above ? r.top - pop.offsetHeight - 10 : r.bottom + 10) + scrollY}px`;
    };
    const hide = () => (pop.hidden = true);
    for (const term of terms) {
      term.addEventListener("pointerenter", () => show(term));
      term.addEventListener("pointerleave", hide);
      term.addEventListener("focus", () => show(term));
      term.addEventListener("blur", hide);
    }
  }

  // ---- check yourself ----
  const head = document.getElementById("check-yourself");
  const questions = head && (() => {
    for (let el = head.nextElementSibling; el && !/^H[12]$/.test(el.tagName); el = el.nextElementSibling) if (el.tagName === "OL") return el;
    return null;
  })();
  const details = questions && (() => {
    for (let el = questions.nextElementSibling; el && !/^H[12]$/.test(el.tagName); el = el.nextElementSibling) {
      if (el.tagName === "DETAILS") return el;
      const inner = el.querySelector && el.querySelector("details");
      if (inner) return inner;
    }
    return null;
  })();
  const answers = details ? [...details.querySelectorAll("ol > li")] : [];
  const items = questions ? [...questions.children] : [];
  if (items.length && answers.length === items.length) {
    const path = location.pathname;
    const state = read(path) || { total: items.length, marks: {} };
    state.total = items.length;
    const summary = document.createElement("p");
    summary.className = "check-summary";
    questions.before(summary);
    const rail = document.querySelector('.toc a[href="#check-yourself"]');
    const update = () => {
      const marks = Object.values(state.marks);
      const had = marks.filter((m) => m === "had").length;
      const again = marks.filter((m) => m === "again").length;
      summary.innerHTML = "";
      const text = document.createElement("span");
      text.textContent = marks.length
        ? `${had} of ${items.length} you had${again ? `, ${again} to look at again` : ""}${had === items.length ? ": this chapter is checked" : ""}.`
        : `${items.length} questions. Think of an answer, then open the one under it.`;
      summary.appendChild(text);
      if (marks.length) {
        const reset = document.createElement("button");
        reset.type = "button";
        reset.textContent = "start again";
        reset.addEventListener("click", () => {
          state.marks = {};
          write(path, state);
          questions.querySelectorAll(".check-answer").forEach((a) => (a.hidden = true));
          questions.querySelectorAll("[data-open]").forEach((b) => b.setAttribute("aria-expanded", "false"));
          refresh();
        });
        summary.appendChild(reset);
      }
      if (rail) {
        let badge = rail.querySelector(".check-badge");
        if (!badge) {
          badge = document.createElement("span");
          badge.className = "check-badge";
          rail.appendChild(badge);
        }
        badge.textContent = marks.length ? `${had}/${items.length}` : "";
        badge.classList.toggle("is-done", had === items.length);
      }
    };
    const refresh = () => {
      items.forEach((li, i) => {
        li.dataset.mark = state.marks[i] || "";
      });
      update();
    };
    items.forEach((li, i) => {
      li.classList.add("check-item");
      const answer = document.createElement("div");
      answer.className = "check-answer";
      answer.hidden = true;
      answer.innerHTML = answers[i].innerHTML;
      const bar = document.createElement("div");
      bar.className = "check-bar";
      const open = document.createElement("button");
      open.type = "button";
      open.dataset.open = "";
      open.setAttribute("aria-expanded", "false");
      open.textContent = "show the answer";
      open.addEventListener("click", () => {
        answer.hidden = !answer.hidden;
        open.setAttribute("aria-expanded", String(!answer.hidden));
        open.textContent = answer.hidden ? "show the answer" : "hide the answer";
      });
      const mark = (value, label) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = `check-mark check-${value}`;
        b.textContent = label;
        b.addEventListener("click", () => {
          state.marks[i] = state.marks[i] === value ? undefined : value;
          if (!state.marks[i]) delete state.marks[i];
          write(path, state);
          refresh();
        });
        return b;
      };
      bar.append(open, mark("had", "I had it"), mark("again", "not yet"));
      li.append(bar, answer);
    });
    details.hidden = true;
    refresh();
  }

  // ---- progress: a mark on every link to a chapter that is checked ----
  for (const a of document.querySelectorAll(".band-course a[href], .pager a[href], .toc-chapters a[href]")) {
    let url;
    try {
      url = new URL(a.getAttribute("href"), location.href);
    } catch (error) {
      continue;
    }
    if (url.pathname === location.pathname) continue;
    const s = read(url.pathname);
    if (!s || !s.total) continue;
    const had = Object.values(s.marks || {}).filter((m) => m === "had").length;
    if (had === s.total) a.classList.add("is-checked");
  }
})();

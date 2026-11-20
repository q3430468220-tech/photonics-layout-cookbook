// photonics-layout-cookbook: the motion that every page shares.
// Headings that rise word by word and let a pulse of light run through them, things that rise into view,
// a statement whose words light up as it is scrolled, numbers that count up, device tiles that turn towards
// the pointer, the top bar, the light that follows the pointer over a card, and the parts of a chapter page.
(() => {
  "use strict";
  const root = document.documentElement;
  const still = /[?&]still\b/.test(location.search); // for screenshots: everything in place, nothing moving
  const calm = still || matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (still) root.classList.add("still");
  window.COOKBOOK_CALM = calm;
  window.COOKBOOK_READY = true; // the page head shows everything again if this never runs
  const watch = "IntersectionObserver" in window;

  // ---- numbers that count up -----------------------------------------------------------------------------
  // The page holds the final number from the start; without motion it simply stays.  A number counts up from
  // zero with the decimals it is written with, and ends on exactly the text the page was built with.
  // This watcher is made first, so that it measures before the other watchers change anything.
  const counters = [...document.querySelectorAll("[data-count]")];
  if (!calm && watch && counters.length) {
    const count = new IntersectionObserver(
      (entries) => {
        const due = entries.filter((entry) => entry.isIntersecting).map((entry) => entry.target);
        const widths = due.map((element) => element.getBoundingClientRect().width); // all measured, then all changed
        due.forEach((element, i) => {
          count.unobserve(element);
          const text = element.firstChild;
          const final = text.textContent;
          const match = final.trim().match(/^([−-]?)(\d+(?:\.(\d+))?)$/);
          if (!match) return;
          const end = parseFloat(match[2]);
          const decimals = (match[3] || "").length;
          element.style.minWidth = widths[i] + "px"; // nothing beside it may move
          const start = performance.now();
          const step = (now) => {
            const t = Math.min(1, (now - start) / 1200);
            if (t < 1) {
              text.textContent = match[1] + (end * (1 - Math.pow(1 - t, 3))).toFixed(decimals);
              requestAnimationFrame(step);
            } else {
              text.textContent = final;
              element.style.minWidth = "";
            }
          };
          requestAnimationFrame(step);
        });
      },
      { threshold: 0.6 },
    );
    counters.forEach((element) => {
      if (element.firstChild && element.firstChild.nodeType === Node.TEXT_NODE) count.observe(element);
    });
  }

  // ---- headings -----------------------------------------------------------------------------------------
  // The words of a large heading are boxes of their own already (website/build.py splits them).  In the first
  // screen they rise by themselves; further down they rise when the heading is scrolled into view.  After
  // that a pulse of light runs through the words, and again when the heading is pointed at.
  const headings = [...document.querySelectorAll("[data-words]")];
  if (!watch) headings.forEach((heading) => heading.classList.add("is-in")); // nothing may wait for a watcher that does not exist
  if (!calm && watch && headings.length) {
    const light = (heading) => {
      heading.classList.remove("is-lit");
      void heading.offsetWidth; // start the pulse again
      heading.classList.add("is-lit");
    };
    const seen = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const heading = entry.target;
          seen.unobserve(heading);
          heading.classList.add("is-in");
          setTimeout(() => light(heading), 1150 + 70 * heading.querySelectorAll(".w").length);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.2 },
    );
    for (const heading of headings) {
      seen.observe(heading);
      let last = 0;
      heading.addEventListener("pointerenter", () => {
        if (!heading.classList.contains("is-in") || performance.now() - last < 1600) return;
        last = performance.now();
        light(heading);
      });
    }
  }

  // ---- things that rise into view ----------------------------------------------------------------------
  const rising = document.querySelectorAll("[data-reveal]");
  if (calm || !watch) rising.forEach((element) => element.classList.add("is-in"));
  else {
    const reveal = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-in");
          reveal.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.06 },
    );
    rising.forEach((element) => reveal.observe(element));
  }

  // ---- a statement whose words light up as it is scrolled through the screen ---------------------------
  const statements = [...document.querySelectorAll("[data-statement]")].map((element) => {
    const list = [...element.querySelectorAll(".w")];
    if (calm) list.forEach((word) => word.classList.add("on"));
    return { element, list, lit: calm ? list.length : 0 };
  });
  function light() {
    for (const statement of statements) {
      const box = statement.element.getBoundingClientRect();
      // nothing lit when the statement enters at the bottom, all of it when its middle reaches 45 % of the screen
      const progress = (innerHeight * 0.92 - box.top) / (innerHeight * 0.47 + box.height / 2);
      const lit = Math.round(Math.min(1, Math.max(0, progress)) * statement.list.length);
      if (lit === statement.lit) continue;
      statement.list.forEach((word, i) => word.classList.toggle("on", i < lit));
      statement.lit = lit;
    }
  }

  // ---- scrolling: the top bar, the drift of the background, the reading progress, the list of sections ----
  const nav = document.querySelector("[data-nav]");
  const toc = document.querySelector("[data-toc]");
  const links = toc ? [...toc.querySelectorAll("a")] : [];
  const targets = links.map((link) => document.getElementById(decodeURIComponent(link.hash.slice(1))));
  const list = toc && toc.querySelector("ol");
  // how far the page is read: for the line at the top of a chapter and for the slow drift of the stars.
  // It is set on those two elements and not on the page, so that a long chapter is not restyled on every frame.
  const readers = [document.querySelector(".progress i"), document.querySelector(".stars")].filter(Boolean);
  let active = -2;

  function onScroll() {
    const y = scrollY;
    if (nav) nav.classList.toggle("is-scrolled", y > 8);
    const room = document.documentElement.scrollHeight - innerHeight;
    const read = room > 0 ? Math.min(1, y / room).toFixed(4) : "0";
    readers.forEach((element) => element.style.setProperty("--read", read));
    if (!calm && statements.length) light();
    if (!toc) return;
    let now = -1;
    targets.forEach((target, i) => {
      if (target && target.getBoundingClientRect().top <= 150) now = i;
    });
    if (now === active) return;
    active = now;
    links.forEach((link, i) => {
      link.classList.toggle("is-active", i === now);
      link.classList.toggle("is-read", i < now);
    });
    list.style.setProperty("--toc", (now >= 0 ? links[now].offsetTop + links[now].offsetHeight / 2 : 0) + "px");
    if (now >= 0) {
      const box = toc.getBoundingClientRect();
      const row = links[now].getBoundingClientRect();
      if (row.top < box.top + 24 || row.bottom > box.bottom - 24) toc.scrollTop += row.top - box.top - box.height / 2;
    }
  }
  let ticking = false;
  addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        onScroll();
      });
    },
    { passive: true },
  );
  // The first look at the scroll position: when the browser reports, after it has drawn the page, that the
  // page is on the screen.  The layout is known then, so nothing is laid out for this script alone, and the
  // script takes no part in the first drawing.
  if (watch) {
    const drawn = new IntersectionObserver(() => {
      drawn.disconnect();
      onScroll();
    });
    drawn.observe(document.body);
  } else onScroll();

  // ---- the pointer: light over a card, and a device picture that turns towards it ------------------------
  const fine = matchMedia("(hover: hover) and (pointer: fine)").matches;
  let turned = null;
  document.addEventListener(
    "pointermove",
    (event) => {
      const card = event.target.closest && event.target.closest(".card");
      if (turned && turned !== card) {
        turned.style.removeProperty("--rx");
        turned.style.removeProperty("--ry");
        turned = null;
      }
      if (!card) return;
      const box = card.getBoundingClientRect();
      const x = event.clientX - box.left;
      const y = event.clientY - box.top;
      card.style.setProperty("--mx", x + "px");
      card.style.setProperty("--my", y + "px");
      if (calm || !fine || !card.classList.contains("device")) return;
      card.style.setProperty("--ry", ((x / box.width - 0.5) * 9).toFixed(2) + "deg");
      card.style.setProperty("--rx", ((0.5 - y / box.height) * 7).toFixed(2) + "deg");
      turned = card;
    },
    { passive: true },
  );

  // ---- tables and headings of a chapter ----------------------------------------------------------------------
  // A table whose content does not fit the text column takes the room to its right on a wide screen.
  const roomy = () =>
    document.querySelectorAll(".prose > .table:not(.table-wide)").forEach((table) => {
      if (table.scrollWidth > table.clientWidth + 1) table.classList.add("table-roomy");
    });
  roomy();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(roomy);
  // The sign beside a heading puts the address of its section on the clipboard as well.
  document.querySelectorAll(".prose .here").forEach((link) =>
    link.addEventListener("click", () => {
      if (!navigator.clipboard) return;
      navigator.clipboard
        .writeText(new URL(link.getAttribute("href"), location.href).href)
        .then(() => {
          link.classList.add("is-copied");
          link.textContent = "copied";
          setTimeout(() => {
            link.classList.remove("is-copied");
            link.textContent = "#";
          }, 1400);
        })
        .catch(() => {});
    }),
  );

  // ---- copy buttons --------------------------------------------------------------------------------------
  document.addEventListener("click", (event) => {
    const button = event.target.closest && event.target.closest(".copy");
    if (!button) return;
    const block = button.closest(".code, .term");
    let text = block.querySelector("pre").innerText;
    if (block.classList.contains("term")) {
      text = text
        .split("\n")
        .filter((line) => line.startsWith("$ "))
        .map((line) => line.slice(2))
        .join("\n");
    }
    const label = button.querySelector("span") || button;
    const mark = button.querySelector("use");
    const done = () => {
      button.classList.add("is-done");
      label.textContent = "copied";
      if (mark) mark.setAttribute("href", "#i-check");
      setTimeout(() => {
        button.classList.remove("is-done");
        label.textContent = "copy";
        if (mark) mark.setAttribute("href", "#i-copy");
      }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, () => {});
  });

  // ---- a figure enlarged ---------------------------------------------------------------------------------
  const box = document.querySelector(".lightbox");
  if (box) {
    const close = () => {
      box.hidden = true;
      const old = box.querySelector("img");
      if (old) old.remove();
    };
    document.addEventListener("click", (event) => {
      const zoom = event.target.closest && event.target.closest(".zoom");
      if (!zoom) return;
      const image = zoom.querySelector("img").cloneNode();
      image.removeAttribute("loading");
      image.removeAttribute("width");
      image.removeAttribute("height");
      image.className = zoom.closest(".fig-paper") ? "paper" : "";
      close();
      box.append(image);
      box.hidden = false;
    });
    box.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
  }
})();

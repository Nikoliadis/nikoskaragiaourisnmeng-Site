// Interactive behaviour for the public site.
//
// One file, no framework, no inline code — the Content-Security-Policy forbids
// inline scripts. Everything here degrades gracefully: without JavaScript the
// pages still work, they are just less lively.

// ---------------------------------------------------------------------------
// Navbar: mobile menu + dropdowns
// ---------------------------------------------------------------------------
document.addEventListener("click", (e) => {
  const toggle = e.target.closest("[data-toggle]");
  const target = toggle && document.getElementById(toggle.dataset.toggle);
  if (target) {
    e.preventDefault();
    target.classList.toggle("hidden");
  }

  const openDropdown = e.target.closest("[data-dropdown]");

  // Close whatever is open elsewhere.
  document.querySelectorAll("[data-dropdown]").forEach((dd) => {
    if (dd !== openDropdown) {
      dd.classList.remove("is-open");
      const menu = dd.querySelector("[data-dropdown-menu]");
      if (menu) menu.classList.add("hidden");
    }
  });

  if (openDropdown) {
    const menu = openDropdown.querySelector("[data-dropdown-menu]");
    if (menu && !e.target.closest("[data-dropdown-menu]")) {
      menu.classList.toggle("hidden");
      // Drives the chevron flip in CSS.
      openDropdown.classList.toggle("is-open", !menu.classList.contains("hidden"));
    }
  }
});

// Escape closes whatever is open.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  document.querySelectorAll("[data-dropdown]").forEach((dd) => {
    dd.classList.remove("is-open");
    const menu = dd.querySelector("[data-dropdown-menu]");
    if (menu) menu.classList.add("hidden");
  });
  const mobile = document.getElementById("mobile-menu");
  if (mobile) mobile.classList.add("hidden");
});

// ---------------------------------------------------------------------------
// Filter the material on a category or section page as the visitor types
// ---------------------------------------------------------------------------
function setUpFilter() {
  const box = document.querySelector("[data-filter-input]");
  const list = document.querySelector("[data-filter-list]");
  if (!box || !list) return;

  const wrapper = document.querySelector("[data-filter]");
  if (wrapper) wrapper.classList.remove("hidden"); // only useful with JS running

  const items = [...list.querySelectorAll("[data-filter-item]")];
  const count = document.querySelector("[data-filter-count]");
  const empty = document.querySelector("[data-filter-empty]");
  const total = items.length;

  // Accent-insensitive: typing "μηχανολογια" should still find «Μηχανολογία».
  // NFD splits an accented letter into letter + accent, and the range below is
  // the combining accents, so stripping them leaves the bare letters.
  const normalise = (text) =>
    text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

  const haystacks = items.map((item) => normalise(item.textContent));

  function apply() {
    const needle = normalise(box.value.trim());
    let shown = 0;
    items.forEach((item, index) => {
      const match = !needle || haystacks[index].includes(needle);
      item.classList.toggle("hidden", !match);
      if (match) shown += 1;
    });
    if (count) {
      count.textContent = needle
        ? `${shown} από ${total} αρχεία`
        : `${total} ${total === 1 ? "αρχείο" : "αρχεία"}`;
    }
    if (empty) empty.classList.toggle("hidden", shown !== 0);
  }

  box.addEventListener("input", apply);
  box.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      box.value = "";
      apply();
    }
  });
  apply();
}

// ---------------------------------------------------------------------------
// Reveal cards as they scroll into view
// ---------------------------------------------------------------------------
function setUpReveal() {
  const targets = document.querySelectorAll("[data-reveal]:not(.is-visible)");
  if (!targets.length) return;

  const wantsLessMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (wantsLessMotion || !("IntersectionObserver" in window)) {
    targets.forEach((el) => el.classList.add("is-visible"));
    return;
  }

  // Anything the visitor can already see is shown immediately, unanimated.
  // Fading in content that is on screen the moment the page opens just delays
  // it — the effect belongs to what arrives later, as you scroll.
  targets.forEach((el) => {
    if (el.getBoundingClientRect().top < window.innerHeight * 0.9) {
      el.classList.add("is-visible", "reveal-instant");
    }
  });

  const STAGGER = 110; // ms between neighbours arriving together

  const observer = new IntersectionObserver(
    (entries) => {
      // Everything that came into view in this pass, in document order, so a
      // row of cards arrives one after another instead of all at once.
      const arriving = entries.filter((entry) => entry.isIntersecting);
      arriving.forEach((entry, index) => {
        const explicit = entry.target.dataset.revealDelay;
        const delay = explicit !== undefined ? Number(explicit) : index * STAGGER;
        setTimeout(() => entry.target.classList.add("is-visible"), delay);
        observer.unobserve(entry.target);
      });
    },
    // Start a little before the element is fully in view, so the movement is
    // finishing as the visitor's eye reaches it.
    { rootMargin: "0px 0px -5% 0px", threshold: 0.01 }
  );

  // Only what is still hidden needs watching.
  targets.forEach((el) => {
    if (!el.classList.contains("is-visible")) observer.observe(el);
  });

  // Safety net. Content that is merely animated must never end up permanently
  // invisible — if the observer misses an element (an odd layout, a page
  // restored from the back/forward cache, a browser quirk), show it anyway.
  setTimeout(() => {
    document.querySelectorAll("[data-reveal]:not(.is-visible)").forEach((el) => {
      const box = el.getBoundingClientRect();
      if (box.top < window.innerHeight * 1.5) el.classList.add("is-visible");
    });
  }, 1200);
}

// ---------------------------------------------------------------------------
// Toast — confirmation for actions the browser performs silently
// ---------------------------------------------------------------------------
function toast(message, icon = "check_circle") {
  const area = document.getElementById("toast-area");
  if (!area) return;

  const node = document.createElement("div");
  node.className = "toast";
  node.setAttribute("role", "status");
  const symbol = document.createElement("span");
  symbol.className = "material-symbols-outlined text-base text-brand-600 dark:text-brand-400";
  symbol.textContent = icon;
  node.append(symbol, document.createTextNode(message));
  area.append(node);

  setTimeout(() => {
    node.classList.add("is-leaving");
    node.addEventListener("animationend", () => node.remove(), { once: true });
  }, 2600);
}

// ---------------------------------------------------------------------------
// Downloads: confirm the click, and remember what has already been taken
// ---------------------------------------------------------------------------
const DOWNLOADED_KEY = "downloaded";

function readDownloaded() {
  try {
    return new Set(JSON.parse(localStorage.getItem(DOWNLOADED_KEY) || "[]"));
  } catch (e) {
    return new Set();
  }
}

function markDownloaded(href, card) {
  if (card) card.classList.add("is-downloaded");
  try {
    const seen = readDownloaded();
    seen.add(href);
    localStorage.setItem(DOWNLOADED_KEY, JSON.stringify([...seen]));
  } catch (e) {
    /* private mode — the badge just won't survive a reload */
  }
}

function setUpDownloads() {
  const seen = readDownloaded();
  document.querySelectorAll('a[href^="/lipsi/"]').forEach((link) => {
    const card = link.closest("[data-filter-item], article");
    if (seen.has(link.getAttribute("href")) && card) card.classList.add("is-downloaded");
  });
}

document.addEventListener("click", (e) => {
  const link = e.target.closest('a[href^="/lipsi/"]');
  if (!link) return;
  // The browser downloads without changing the page, so nothing would tell the
  // visitor it worked.
  markDownloaded(link.getAttribute("href"), link.closest("[data-filter-item], article"));
  toast("Η λήψη ξεκίνησε", "download_done");
});

// ---------------------------------------------------------------------------
// Counters that tick up when they scroll into view
// ---------------------------------------------------------------------------
function setUpCounters() {
  const counters = document.querySelectorAll("[data-count]:not(.counted)");
  if (!counters.length || !("IntersectionObserver" in window)) return;

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    counters.forEach((el) => el.classList.add("counted"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      observer.unobserve(el);
      el.classList.add("counted");

      const target = Number(el.dataset.count) || 0;
      if (target < 2) return; // nothing to watch tick from 0 to 1
      const duration = 600;
      const started = performance.now();
      const step = (now) => {
        const progress = Math.min((now - started) / duration, 1);
        // Ease out, so it slows as it lands on the real number.
        el.textContent = Math.round(target * (1 - Math.pow(1 - progress, 3)));
        if (progress < 1) requestAnimationFrame(step);
      };
      el.textContent = "0";
      requestAnimationFrame(step);
    });
  }, { threshold: 0.4 });

  counters.forEach((el) => observer.observe(el));
}

// ---------------------------------------------------------------------------
// Back to top
// ---------------------------------------------------------------------------
function setUpBackToTop() {
  const button = document.getElementById("back-to-top");
  if (!button) return;

  const update = () =>
    button.classList.toggle("is-visible", window.scrollY > window.innerHeight);

  window.addEventListener("scroll", update, { passive: true });
  button.addEventListener("click", () => {
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: smooth ? "smooth" : "auto" });
  });
  update();
}

// ---------------------------------------------------------------------------
// Progress bar for htmx-boosted navigation
// ---------------------------------------------------------------------------
function setUpProgress() {
  const bar = document.getElementById("page-progress");
  if (!bar) return;
  document.body.addEventListener("htmx:beforeRequest", () => {
    bar.classList.remove("is-done");
    bar.classList.add("is-loading");
  });
  document.body.addEventListener("htmx:afterRequest", () => {
    bar.classList.remove("is-loading");
    bar.classList.add("is-done");
  });
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
function initPage() {
  setUpFilter();
  setUpReveal();
  setUpBackToTop();
  setUpDownloads();
  setUpCounters();
}

document.addEventListener("DOMContentLoaded", () => {
  document.documentElement.classList.remove("no-js");
  initPage();
  setUpProgress();
});

// htmx replaces the body on a boosted navigation, so anything bound to page
// elements has to be wired up again for the new content.
document.addEventListener("htmx:afterSwap", () => {
  initPage();
  window.initHero && window.initHero();
});

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

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        // A small stagger reads as one movement rather than a popcorn effect.
        const delay = Number(entry.target.dataset.revealDelay || 0);
        setTimeout(() => entry.target.classList.add("is-visible"), delay);
        observer.unobserve(entry.target);
      });
    },
    { rootMargin: "0px 0px -10% 0px", threshold: 0.05 }
  );

  targets.forEach((el) => observer.observe(el));
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

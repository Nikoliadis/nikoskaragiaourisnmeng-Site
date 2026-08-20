// Light / dark theme.
//
// Loaded synchronously in <head> — deliberately not deferred, so the theme is
// on <html> before the first paint and the page never flashes white on its way
// to dark. Kept in a file (not an inline <script>) so the Content-Security-
// Policy can still forbid inline scripts.
(function () {
  var STORAGE_KEY = "theme";
  var root = document.documentElement;

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function stored() {
    try {
      var value = localStorage.getItem(STORAGE_KEY);
      return value === "dark" || value === "light" ? value : null;
    } catch (e) {
      return null; // private mode, storage disabled — fall back to the system
    }
  }

  function apply(theme) {
    root.dataset.theme = theme;
  }

  // First visit follows the operating system; afterwards the visitor's own
  // choice wins.
  apply(stored() || systemTheme());

  // Keep following the system for as long as no explicit choice was made.
  var media = window.matchMedia("(prefers-color-scheme: dark)");
  var onSystemChange = function () {
    if (!stored()) apply(systemTheme());
  };
  if (media.addEventListener) media.addEventListener("change", onSystemChange);
  else if (media.addListener) media.addListener(onSystemChange);

  // Re-queried every time: hx-boost swaps the whole body, so the buttons held
  // by a previous call are detached nodes that nobody can see any more.
  function label() {
    var isDark = root.dataset.theme === "dark";
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      var text = isDark ? "Εναλλαγή σε φωτεινό θέμα" : "Εναλλαγή σε σκοτεινό θέμα";
      button.setAttribute("aria-label", text);
      button.setAttribute("title", text);
      button.setAttribute("aria-pressed", String(isDark));
    });
  }

  // Delegated on document, not bound to the buttons themselves. hx-boost
  // replaces the <body> on every in-site navigation and takes the buttons'
  // listeners with it, so a directly bound toggle dies on the first menu click
  // and only comes back on a hard refresh. document survives every swap, and
  // one listener can never be attached twice.
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var button = target.closest("[data-theme-toggle]");
    if (!button) return;

    var next = root.dataset.theme === "dark" ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (e) {
      /* choice just won't persist */
    }
    label();
  });

  // The labels describe the *current* theme, and the buttons that arrive with
  // a swapped body come from the server without that state.
  document.addEventListener("DOMContentLoaded", label);
  document.addEventListener("htmx:afterSwap", label);
})();

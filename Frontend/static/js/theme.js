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

  // The toggle buttons only exist once the body is parsed.
  document.addEventListener("DOMContentLoaded", function () {
    var buttons = document.querySelectorAll("[data-theme-toggle]");

    function label() {
      var isDark = root.dataset.theme === "dark";
      buttons.forEach(function (button) {
        button.setAttribute(
          "aria-label",
          isDark ? "Εναλλαγή σε φωτεινό θέμα" : "Εναλλαγή σε σκοτεινό θέμα"
        );
        button.setAttribute("title", button.getAttribute("aria-label"));
        button.setAttribute("aria-pressed", String(isDark));
      });
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var next = root.dataset.theme === "dark" ? "light" : "dark";
        apply(next);
        try {
          localStorage.setItem(STORAGE_KEY, next);
        } catch (e) {
          /* choice just won't persist */
        }
        label();
      });
    });

    label();
  });
})();

// Mobile menu + navbar dropdown toggles (vanilla, no framework).
// Kept in a file rather than a <script> block so the Content-Security-Policy
// can forbid inline scripts entirely.
document.addEventListener("click", (e) => {
  const toggle = e.target.closest("[data-toggle]");
  const target = toggle && document.getElementById(toggle.dataset.toggle);
  if (target) {
    e.preventDefault();
    target.classList.toggle("hidden");
  }

  // Close open dropdowns when clicking elsewhere.
  if (!e.target.closest("[data-dropdown]")) {
    document.querySelectorAll("[data-dropdown-menu]").forEach((m) => m.classList.add("hidden"));
  }

  const dd = e.target.closest("[data-dropdown]");
  if (dd) {
    const menu = dd.querySelector("[data-dropdown-menu]");
    document.querySelectorAll("[data-dropdown-menu]").forEach((m) => {
      if (m !== menu) m.classList.add("hidden");
    });
    if (menu) menu.classList.toggle("hidden");
  }
});

// Escape closes whatever is open.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  document.querySelectorAll("[data-dropdown-menu]").forEach((m) => m.classList.add("hidden"));
  const mobile = document.getElementById("mobile-menu");
  if (mobile) mobile.classList.add("hidden");
});

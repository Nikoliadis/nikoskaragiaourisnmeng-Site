// Hero slideshow: cross-fade every 6s, pause on hover, dots jump to a photo.
// In a file rather than a <script> block so the CSP can forbid inline scripts.
(function () {
  const slides = document.querySelectorAll("[data-hero-slide]");
  const dots = document.querySelectorAll("[data-hero-dot]");
  if (slides.length < 2) return;

  const DELAY = 6000;
  const ACTIVE_DOT = "w-8 bg-white";
  const IDLE_DOT = "w-2 bg-white/40 hover:bg-white/70";

  let current = 0;
  let timer = null;

  function show(next) {
    slides[current].classList.remove("opacity-100");
    if (dots[current]) dots[current].className = dots[current].className.replace(ACTIVE_DOT, IDLE_DOT);

    current = (next + slides.length) % slides.length;

    slides[current].classList.add("opacity-100");
    if (dots[current]) dots[current].className = dots[current].className.replace(IDLE_DOT, ACTIVE_DOT);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function start() {
    // Someone who asked for less motion gets the first photo and nothing else.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    stop();
    timer = setInterval(() => show(current + 1), DELAY);
  }

  dots.forEach((dot, index) =>
    dot.addEventListener("click", () => {
      show(index);
      start();
    })
  );

  const hero = document.querySelector("[data-hero]");
  if (hero) {
    hero.addEventListener("mouseenter", stop);
    hero.addEventListener("mouseleave", start);
  }
  // Don't animate in a background tab.
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));

  start();
})();

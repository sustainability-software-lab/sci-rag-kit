// Mount the asciinema player on the homepage.
//
// The full transcript is written out below the player in the Example section,
// so nothing here is load-bearing: if the script fails to load, or the reader
// has JavaScript off, they still get the session.
//
// Material's palette toggle rewrites data-md-color-scheme on <body> without
// reloading, and the player picks its colors once at construction. So watch
// the attribute and rebuild when it changes; otherwise a reader who toggles to
// light is left with a dark terminal and no way to fix it.
(function () {
  var players = new Map();

  function themeFor(scheme) {
    // tango and asciinema supply the ANSI colors; home.css overrides the
    // background and body text so the player sits on the site's code surface.
    return scheme === "slate" ? "asciinema" : "tango";
  }

  function mount(el) {
    if (typeof AsciinemaPlayer === "undefined") {
      return;
    }
    var previous = players.get(el);
    if (previous && typeof previous.dispose === "function") {
      previous.dispose();
    }
    el.innerHTML = "";
    var player = AsciinemaPlayer.create(el.dataset.cast, el, {
      autoPlay: false,
      preload: true,
      idleTimeLimit: 1.5,
      speed: 1.4,
      fit: "width",
      theme: themeFor(document.body.getAttribute("data-md-color-scheme")),
      terminalFontFamily: "var(--md-code-font-family, monospace)",
    });
    players.set(el, player);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var elements = document.querySelectorAll(".srag-cast");
    if (!elements.length) {
      return;
    }
    elements.forEach(mount);
    new MutationObserver(function () {
      elements.forEach(mount);
    }).observe(document.body, {
      attributes: true,
      attributeFilter: ["data-md-color-scheme"],
    });
  });
})();

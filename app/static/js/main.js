(function () {
  var root = document.documentElement;
  var themeButtons = document.querySelectorAll("#themeToggle, #themeToggleMobile");
  var stored = localStorage.getItem("theme");

  function applyTheme(theme) {
    root.setAttribute("data-bs-theme", theme);
    themeButtons.forEach(function (btn) {
      btn.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
      var label = btn.querySelector("b");
      if (label) label.textContent = theme === "dark" ? "Light" : "Dark";
      else btn.textContent = theme === "dark" ? "☀" : "◐";
    });
  }
  applyTheme(stored || "light");
  themeButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      applyTheme(next); localStorage.setItem("theme", next);
    });
  });

  // Mobile navigation
  var sidebar = document.getElementById("appSidebar");
  var overlay = document.querySelector(".sidebar-overlay");
  function toggleSidebar() {
    if (!sidebar) return;
    sidebar.classList.toggle("open");
    if (overlay) overlay.classList.toggle("show", sidebar.classList.contains("open"));
  }
  document.querySelectorAll("[data-sidebar-toggle]").forEach(function (el) {
    el.addEventListener("click", toggleSidebar);
  });
  if (sidebar) sidebar.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () { sidebar.classList.remove("open"); if (overlay) overlay.classList.remove("show"); });
  });

  // Show/hide password
  document.querySelectorAll(".toggle-password").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.closest(".input-group").querySelector("input");
      var isHidden = input.getAttribute("type") === "password";
      input.setAttribute("type", isHidden ? "text" : "password");
      btn.textContent = isHidden ? "🙈" : "👁";
      btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
    });
  });
})();

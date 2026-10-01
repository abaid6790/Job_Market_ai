(function () {
  var root = document.documentElement;
  var toggleBtn = document.getElementById("themeToggle");
  var stored = localStorage.getItem("theme");

  function applyTheme(theme) {
    root.setAttribute("data-bs-theme", theme);
    if (!toggleBtn) return;
    var icon = toggleBtn.querySelector("i");
    var label = toggleBtn.querySelector("strong");
    if (icon) icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    if (label) label.textContent = theme === "dark" ? "Dark" : "Light";
    if (!icon && !label) toggleBtn.textContent = theme === "dark" ? "☀️" : "🌙";
  }

  applyTheme(stored || "light");

  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      var current = root.getAttribute("data-bs-theme");
      var next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      localStorage.setItem("theme", next);
    });
  }

  document.querySelectorAll(".toggle-password").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.closest(".input-group").querySelector("input");
      var isHidden = input.getAttribute("type") === "password";
      input.setAttribute("type", isHidden ? "text" : "password");
      btn.textContent = isHidden ? "🙈" : "👁";
      btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
    });
  });

  var sidebar = document.getElementById("appSidebar");
  var backdrop = document.querySelector(".sidebar-backdrop");
  document.querySelectorAll("[data-sidebar-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (sidebar) sidebar.classList.add("open");
      if (backdrop) backdrop.classList.add("show");
    });
  });
  document.querySelectorAll("[data-sidebar-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (sidebar) sidebar.classList.remove("open");
      if (backdrop) backdrop.classList.remove("show");
    });
  });
  document.querySelectorAll(".side-link").forEach(function (link) {
    link.addEventListener("click", function () {
      if (sidebar) sidebar.classList.remove("open");
      if (backdrop) backdrop.classList.remove("show");
    });
  });
})();

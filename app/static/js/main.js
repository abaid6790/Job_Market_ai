(function () {
  // --- Theme toggle (persisted in localStorage) ---
  var root = document.documentElement;
  var toggleBtn = document.getElementById("themeToggle");
  var stored = localStorage.getItem("theme");

  function applyTheme(theme) {
    root.setAttribute("data-bs-theme", theme);
    if (toggleBtn) toggleBtn.textContent = theme === "dark" ? "☀️" : "🌙";
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

  // --- Show/hide password ---
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

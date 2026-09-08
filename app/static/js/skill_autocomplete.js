(function () {
  var input = document.getElementById("skillNameInput");
  var box = document.getElementById("skillSuggestions");
  if (!input || !box) return;

  var debounceTimer = null;

  function hideSuggestions() {
    box.innerHTML = "";
    box.classList.remove("show");
  }

  function renderSuggestions(items) {
    box.innerHTML = "";
    if (!items.length) {
      hideSuggestions();
      return;
    }
    items.forEach(function (item) {
      var el = document.createElement("button");
      el.type = "button";
      el.className = "list-group-item list-group-item-action py-1";
      el.textContent = item.category ? item.name + " — " + item.category : item.name;
      el.addEventListener("mousedown", function (e) {
        e.preventDefault();
        input.value = item.name;
        hideSuggestions();
      });
      box.appendChild(el);
    });
    box.classList.add("show");
  }

  input.addEventListener("input", function () {
    var q = input.value.trim();
    clearTimeout(debounceTimer);
    if (q.length < 2) {
      hideSuggestions();
      return;
    }
    debounceTimer = setTimeout(function () {
      fetch("/api/skills/suggest?q=" + encodeURIComponent(q))
        .then(function (res) {
          return res.ok ? res.json() : [];
        })
        .then(renderSuggestions)
        .catch(function () {
          hideSuggestions();
        });
    }, 200);
  });

  input.addEventListener("blur", function () {
    setTimeout(hideSuggestions, 150);
  });
})();

// Small, dependency-free behaviours: nav, confirmations, register shortcuts, print.

(function () {
  "use strict";

  // Mobile navigation
  var toggle = document.querySelector("[data-rail-toggle]");
  if (toggle) {
    toggle.setAttribute("aria-expanded", "false");
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && document.body.classList.contains("nav-open")) {
        document.body.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
    document.querySelectorAll(".rail a").forEach(function (link) {
      link.addEventListener("click", function () {
        document.body.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // Destructive actions ask first.
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  // "Mark all present" in the attendance register.
  document.querySelectorAll("[data-mark-all]").forEach(function (button) {
    button.addEventListener("click", function () {
      var form = button.closest("form");
      if (!form) return;
      form.querySelectorAll('input[type="radio"][value="present"]').forEach(function (radio) {
        radio.checked = true;
      });
    });
  });

  // Print buttons on documents.
  document.querySelectorAll("[data-print]").forEach(function (button) {
    button.addEventListener("click", function () {
      window.print();
    });
  });

  // Attendance marks inputs: keep them inside the allowed range as you type.
  document.querySelectorAll(".input--marks").forEach(function (input) {
    var max = parseFloat(input.getAttribute("max"));
    input.addEventListener("blur", function () {
      if (input.value === "") return;
      var value = parseFloat(input.value);
      if (isNaN(value)) { input.value = ""; return; }
      if (value < 0) input.value = "0";
      if (!isNaN(max) && value > max) input.value = String(max);
    });
  });
})();

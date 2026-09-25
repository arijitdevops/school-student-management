/**
 * Progressive enhancement for the student management screens.
 *
 * Everything here is optional: each page works with JavaScript disabled, and
 * every server-side validation still runs regardless of what happens below.
 */
(function () {
  "use strict";

  /**
   * Enable or disable a mark input to match its "absent" checkbox.
   *
   * A disabled input is not submitted, so the server sees only the absent flag.
   *
   * @param {HTMLInputElement} checkbox The absent checkbox.
   */
  function syncAbsentToggle(checkbox) {
    var name = checkbox.getAttribute("data-target");
    if (!name) {
      return;
    }
    var input = document.querySelector('input[name="' + name + '"]');
    if (!input) {
      return;
    }
    input.disabled = checkbox.checked;
    if (checkbox.checked) {
      input.value = "";
    }
  }

  /**
   * Move focus to the next mark input when Enter is pressed, the way a
   * spreadsheet behaves, instead of submitting the form on the first row.
   *
   * @param {KeyboardEvent} event The keydown event.
   * @param {HTMLInputElement[]} inputs Every mark input on the page, in order.
   */
  function handleGridKeydown(event, inputs) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    var index = inputs.indexOf(event.target);
    for (var next = index + 1; next < inputs.length; next += 1) {
      if (!inputs[next].disabled) {
        inputs[next].focus();
        inputs[next].select();
        return;
      }
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggles = Array.prototype.slice.call(document.querySelectorAll(".absent-toggle"));
    toggles.forEach(function (checkbox) {
      syncAbsentToggle(checkbox);
      checkbox.addEventListener("change", function () {
        syncAbsentToggle(checkbox);
      });
    });

    var markInputs = Array.prototype.slice.call(document.querySelectorAll(".mark-input"));
    markInputs.forEach(function (input) {
      input.addEventListener("keydown", function (event) {
        handleGridKeydown(event, markInputs);
      });
      input.addEventListener("focus", function () {
        input.select();
      });
    });

    // Forms carrying data-confirm ask before they post; used for removals.
    var guarded = document.querySelectorAll("form[data-confirm]");
    Array.prototype.forEach.call(guarded, function (form) {
      form.addEventListener("submit", function (event) {
        if (!window.confirm(form.getAttribute("data-confirm"))) {
          event.preventDefault();
        }
      });
    });
  });
})();

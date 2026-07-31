"use strict";

(() => {
  const form = document.querySelector("[data-movement-form]");
  if (!form) {
    return;
  }

  const submitButton = form.querySelector("[data-movement-submit]");
  if (!submitButton) {
    return;
  }

  form.addEventListener("submit", (event) => {
    if (form.dataset.submitted === "true") {
      event.preventDefault();
      return;
    }
    if (!form.checkValidity()) {
      return;
    }
    form.dataset.submitted = "true";
    submitButton.disabled = true;
    submitButton.textContent = "Procesando...";
  });
})();

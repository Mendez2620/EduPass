"use strict";

(() => {
  const countdown = document.querySelector("[data-credential-countdown]");
  const renewalForm = document.querySelector("[data-renewal-form]");
  if (!countdown || !renewalForm) {
    return;
  }

  const expiration = Date.parse(countdown.dataset.expiresAt);
  if (Number.isNaN(expiration)) {
    countdown.textContent = "No fue posible calcular la vigencia.";
    return;
  }

  let submitted = false;
  let timerId = null;

  const submitRenewal = () => {
    if (submitted) {
      return;
    }
    submitted = true;
    if (timerId !== null) {
      window.clearInterval(timerId);
    }
    if (typeof renewalForm.requestSubmit === "function") {
      renewalForm.requestSubmit();
    } else {
      renewalForm.submit();
    }
  };

  const updateCountdown = () => {
    const remainingMilliseconds = expiration - Date.now();
    const remainingSeconds = Math.max(
      0,
      Math.ceil(remainingMilliseconds / 1000),
    );
    countdown.textContent = `Tiempo restante: ${remainingSeconds} segundos`;
    if (remainingMilliseconds <= 0) {
      submitRenewal();
    }
  };

  renewalForm.addEventListener("submit", () => {
    submitted = true;
    if (timerId !== null) {
      window.clearInterval(timerId);
    }
  });

  updateCountdown();
  if (!submitted) {
    timerId = window.setInterval(updateCountdown, 250);
  }
})();
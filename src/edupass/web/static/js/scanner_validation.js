"use strict";

(() => {
  const form = document.querySelector("[data-movement-form]");
  if (!form) {
    return;
  }

  const submitButton = form.querySelector("[data-movement-submit]");
  const tokenInput = form.querySelector("[data-token-input]");
  const startButton = document.querySelector("[data-camera-start]");
  const stopButton = document.querySelector("[data-camera-stop]");
  const video = document.querySelector("[data-camera-video]");
  const status = document.querySelector("[data-camera-status]");
  const tokenPattern = /^[A-Za-z0-9_-]{43}$/;

  let controls = null;
  let reader = null;
  let starting = false;
  let detected = false;

  const setStatus = (message) => {
    if (status) {
      status.textContent = message;
    }
  };

  const stopTracks = () => {
    if (!video || !video.srcObject) {
      return;
    }
    const tracks = video.srcObject.getTracks();
    tracks.forEach((track) => track.stop());
    video.srcObject = null;
  };

  const stopCamera = () => {
    if (controls) {
      try {
        controls.stop();
      } catch (_error) {
        // La detención debe ser idempotente incluso si el lector ya terminó.
      }
    }
    controls = null;
    reader = null;
    stopTracks();
    if (video) {
      video.hidden = true;
    }
    starting = false;
    if (startButton) {
      startButton.disabled = false;
    }
    if (stopButton) {
      stopButton.disabled = true;
    }
  };

  const cameraErrorMessage = (error) => {
    const name = error && error.name ? error.name : "";
    if (name === "NotAllowedError" || name === "SecurityError") {
      return "No se concedió permiso para utilizar la cámara. Usa la captura manual.";
    }
    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      return "No se encontró una cámara disponible. Usa la captura manual.";
    }
    return "No fue posible iniciar la cámara. Usa la captura manual.";
  };

  const handleResult = (result, _error, activeControls) => {
    if (activeControls) {
      controls = activeControls;
    }
    if (!result || detected) {
      return;
    }
    const token = result.getText();
    if (!tokenPattern.test(token)) {
      return;
    }
    detected = true;
    stopCamera();
    if (tokenInput) {
      tokenInput.value = token;
    }
    setStatus("QR detectado. Solicita la previsualización del movimiento.");
    if (submitButton) {
      submitButton.focus();
    }
  };

  const startCamera = async () => {
    if (starting || controls) {
      return;
    }
    if (!window.isSecureContext) {
      setStatus("La cámara requiere HTTPS o localhost. Usa la captura manual.");
      return;
    }
    if (
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia ||
      !window.ZXingBrowser ||
      !window.ZXingBrowser.BrowserQRCodeReader
    ) {
      setStatus("La cámara no está disponible en este navegador. Usa la captura manual.");
      return;
    }

    starting = true;
    detected = false;
    startButton.disabled = true;
    stopButton.disabled = false;
    setStatus("Solicitando acceso a la cámara...");
    try {
      reader = new window.ZXingBrowser.BrowserQRCodeReader();
      controls = await reader.decodeFromConstraints(
        {
          video: { facingMode: { ideal: "environment" } },
          audio: false,
        },
        video,
        handleResult
      );
      if (detected) {
        stopCamera();
        return;
      }
      video.hidden = false;
      starting = false;
      setStatus("Apunta la cámara al código QR del alumno.");
    } catch (error) {
      stopCamera();
      setStatus(cameraErrorMessage(error));
    }
  };

  if (startButton && stopButton && video && status && tokenInput) {
    startButton.addEventListener("click", startCamera);
    stopButton.addEventListener("click", () => {
      stopCamera();
      setStatus("Cámara detenida. Puedes usar la captura manual.");
    });
  }

  form.addEventListener("submit", (event) => {
    stopCamera();
    if (form.dataset.submitted === "true") {
      event.preventDefault();
      return;
    }
    if (!form.checkValidity()) {
      return;
    }
    form.dataset.submitted = "true";
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Procesando...";
    }
  });

  window.addEventListener("pagehide", stopCamera);
  window.addEventListener("beforeunload", stopCamera);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stopCamera();
    }
  });
})();

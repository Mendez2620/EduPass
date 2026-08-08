"use strict";

(() => {
  const form = document.querySelector("[data-movement-form]");
  if (!form) return;

  const tokenInput = form.querySelector("[data-token-input]");
  const csrfInput = form.querySelector('input[name="csrf_token"]');
  const submitButton = form.querySelector("[data-movement-submit]");
  const startButton = document.querySelector("[data-camera-start]");
  const stopButton = document.querySelector("[data-camera-stop]");
  const video = document.querySelector("[data-camera-video]");
  const status = document.querySelector("[data-camera-status]");
  const resultPanel = document.querySelector("[data-camera-result]");
  const endpoint = form.dataset.cameraEndpoint;
  const tokenPattern = /^[A-Za-z0-9_-]{43}$/;

  let controls = null;
  let reader = null;
  let starting = false;
  let processing = false;

  const setStatus = (message) => { status.textContent = message; };

  const renderResult = (payload) => {
    resultPanel.replaceChildren();
    const box = document.createElement("div");
    box.className = `validation-result validation-result-${payload.estado}`;
    const title = document.createElement("strong");
    title.textContent = payload.estado === "valido"
      ? `✓ ${payload.tipo_movimiento.toUpperCase()} REGISTRADA`
      : "QR inválido/vencido/utilizado";
    const detail = document.createElement("p");
    detail.textContent = payload.estado === "valido"
      ? `${payload.alumno_nombre} · ${payload.fecha_hora}`
      : payload.mensaje;
    box.append(title, detail);
    resultPanel.append(box);
  };

  const stopTracks = () => {
    if (!video.srcObject) return;
    video.srcObject.getTracks().forEach((track) => track.stop());
    video.srcObject = null;
  };

  const stopCamera = () => {
    if (controls) {
      try { controls.stop(); } catch (_error) { /* idempotente */ }
    }
    controls = null;
    reader = null;
    stopTracks();
    video.hidden = true;
    starting = false;
    processing = false;
    startButton.disabled = false;
    stopButton.disabled = true;
  };

  const sendCameraToken = async (token) => {
    if (processing) return;
    processing = true;
    setStatus("Procesando QR...");
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfInput ? csrfInput.value : "",
        },
        body: JSON.stringify({ token }),
      });
      const payload = await response.json();
      renderResult(payload);
      setStatus(response.ok
        ? "Listo para escanear el siguiente código"
        : "QR inválido/vencido/utilizado. Listo para escanear el siguiente código");
    } catch (_error) {
      renderResult({ estado: "rechazado", mensaje: "No fue posible registrar el movimiento." });
      setStatus("Listo para escanear el siguiente código");
    } finally {
      processing = false;
    }
  };

  const handleResult = (result, _error, activeControls) => {
    if (activeControls) controls = activeControls;
    if (!result || processing) return;
    const token = result.getText();
    if (tokenPattern.test(token)) sendCameraToken(token);
  };

  const startCamera = async () => {
    if (starting || controls) return;
    if (!window.isSecureContext) {
      setStatus("La cámara requiere HTTPS o localhost. Usa la captura manual.");
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia ||
        !window.ZXingBrowser || !window.ZXingBrowser.BrowserQRCodeReader) {
      setStatus("La cámara no está disponible. Usa la captura manual.");
      return;
    }
    starting = true;
    startButton.disabled = true;
    stopButton.disabled = false;
    setStatus("Procesando activación de cámara...");
    try {
      reader = new window.ZXingBrowser.BrowserQRCodeReader();
      controls = await reader.decodeFromConstraints(
        { video: { facingMode: { ideal: "environment" } }, audio: false },
        video,
        handleResult
      );
      video.hidden = false;
      starting = false;
      setStatus("Listo para escanear");
    } catch (_error) {
      stopCamera();
      setStatus("No fue posible iniciar la cámara. Usa la captura manual.");
    }
  };

  startButton.addEventListener("click", startCamera);
  stopButton.addEventListener("click", () => {
    stopCamera();
    setStatus("Cámara inactiva");
  });
  form.addEventListener("submit", () => {
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Procesando...";
    }
  });
  window.addEventListener("pagehide", stopCamera);
  window.addEventListener("beforeunload", stopCamera);
})();

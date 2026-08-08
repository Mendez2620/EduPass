import hashlib
from pathlib import Path
import re
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.auth import usuarios_service
from edupass.modules.credencial_qr import credencial_service
from edupass.web import create_app


class TestWebCameraQr(unittest.TestCase):
    PASSWORD = "ClaveCamara123"
    EXPECTED_JS_SHA256 = "066bc34edfcdd4a33f0964aeec967752a0dea1ccaf36e58e319ac9fcb5070f6a"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "camera_qr.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "camera-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        usuarios_service.crear_administrador(
            "Admin", "admin@edupass.test", self.PASSWORD, self.database_path
        )
        usuarios_service.crear_escaner(
            "Escaner", "scanner@edupass.test", self.PASSWORD, self.database_path
        )
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Camara", "CAM-0001", "1", "A",
            estado="activo", database_path=self.database_path,
        )
        self.vendor_dir = (
            SRC_PATH / "edupass" / "web" / "static" / "vendor" /
            "zxing-browser" / "0.2.1"
        )
        self.js_path = SRC_PATH / "edupass" / "web" / "static" / "js" / "scanner_validation.js"

    def tearDown(self):
        self.temp.cleanup()

    def _login(self, email="scanner@edupass.test"):
        return self.client.post("/login", data={"correo": email, "password": self.PASSWORD})

    def _body(self):
        return self.client.get("/scanner/validar").get_data(as_text=True)

    def _js(self):
        return self.js_path.read_text(encoding="utf-8")

    def test_01_visitante_redirigido(self):
        response = self.client.get("/scanner/validar")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_02_administrador_recibe_403(self):
        self._login("admin@edupass.test")
        self.assertEqual(self.client.get("/scanner/validar").status_code, 403)

    def test_03_escaner_accede(self):
        self._login()
        self.assertEqual(self.client.get("/scanner/validar").status_code, 200)

    def test_04_permissions_policy_camara_self(self):
        self._login(); response = self.client.get("/scanner/validar")
        self.assertIn("camera=(self)", response.headers["Permissions-Policy"])

    def test_05_permissions_policy_bloquea_microfono(self):
        self._login(); response = self.client.get("/scanner/validar")
        self.assertIn("microphone=()", response.headers["Permissions-Policy"])

    def test_06_boton_activar_camara(self):
        self._login(); body = self._body()
        self.assertIn("Activar cámara", body); self.assertIn("data-camera-start", body)

    def test_07_boton_cancelar_camara(self):
        self._login(); body = self._body()
        self.assertIn("Cancelar cámara", body); self.assertIn("data-camera-stop", body)

    def test_08_video_autoplay(self):
        self._login(); self.assertRegex(self._body(), r"<video[^>]*autoplay")

    def test_09_video_muted(self):
        self._login(); self.assertRegex(self._body(), r"<video[^>]*muted")

    def test_10_video_playsinline(self):
        self._login(); self.assertRegex(self._body(), r"<video[^>]*playsinline")

    def test_11_estado_accesible(self):
        self._login(); body = self._body()
        self.assertIn("data-camera-status", body); self.assertIn('aria-live="polite"', body)

    def test_12_captura_manual_presente(self):
        self._login(); self.assertIn("Captura manual", self._body())

    def test_13_selector_entrada_salida_eliminado(self):
        self._login(); body = self._body()
        self.assertNotIn('name="tipo_movimiento"', body)
        self.assertNotIn("<select", body)

    def test_14_csrf_capable_form_present(self):
        csrf_app = create_app({
            "TESTING": True, "SECRET_KEY": "csrf-camera",
            "DATABASE_PATH": Path(self.temp.name) / "csrf.sqlite",
            "WTF_CSRF_ENABLED": True,
        })
        csrf_client = csrf_app.test_client()
        usuarios_service.crear_escaner(
            "CSRF", "csrf@edupass.test", self.PASSWORD,
            Path(self.temp.name) / "csrf.sqlite",
        )
        login = csrf_client.get("/login").get_data(as_text=True)
        self.assertIn('name="csrf_token"', login)

    def test_15_zxing_is_local(self):
        self._login()
        self.assertIn("/static/vendor/zxing-browser/0.2.1/zxing-browser.min.js", self._body())

    def test_16_application_script_is_local(self):
        self._login(); self.assertIn("/static/js/scanner_validation.js", self._body())

    def test_17_scripts_are_in_required_order(self):
        self._login(); body = self._body()
        self.assertLess(body.index("zxing-browser.min.js"), body.index("scanner_validation.js"))

    def test_18_no_cdn_in_page(self):
        self._login(); body = self._body()
        self.assertNotIn("https://", body); self.assertNotIn("cdn", body.lower())

    def test_19_no_latest_reference(self):
        self._login(); self.assertNotIn("latest", self._body().lower())

    def test_20_vendor_exists(self):
        self.assertTrue((self.vendor_dir / "zxing-browser.min.js").is_file())
        self.assertTrue((self.vendor_dir / "LICENSE").is_file())

    def test_21_vendor_is_not_empty(self):
        self.assertGreater((self.vendor_dir / "zxing-browser.min.js").stat().st_size, 1000)

    def test_22_vendor_version_is_021(self):
        manifest = (self.vendor_dir / "VENDOR.md").read_text(encoding="utf-8")
        self.assertIn("`0.2.1`", manifest)

    def test_23_license_is_mit(self):
        license_text = (self.vendor_dir / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Licencia: `MIT`", (self.vendor_dir / "VENDOR.md").read_text(encoding="utf-8"))

    def test_24_javascript_checksum_matches(self):
        digest = hashlib.sha256((self.vendor_dir / "zxing-browser.min.js").read_bytes()).hexdigest()
        self.assertEqual(digest, self.EXPECTED_JS_SHA256)
        self.assertIn(digest, (self.vendor_dir / "VENDOR.md").read_text(encoding="utf-8"))

    def test_25_no_node_modules(self):
        self.assertFalse(any(path.is_dir() for path in PROJECT_ROOT.rglob("node_modules")))

    def test_26_no_vendor_package_json(self):
        self.assertFalse((self.vendor_dir / "package.json").exists())

    def test_27_checks_secure_context(self):
        self.assertIn("window.isSecureContext", self._js())

    def test_28_checks_media_devices(self):
        js = self._js(); self.assertIn("navigator.mediaDevices", js)
        self.assertIn("navigator.mediaDevices.getUserMedia", js)

    def test_29_requests_video(self):
        self.assertRegex(self._js(), r"video:\s*\{")

    def test_30_does_not_request_audio(self):
        self.assertIn("audio: false", self._js())

    def test_31_prefers_environment_camera(self):
        self.assertIn('ideal: "environment"', self._js())

    def test_32_validates_exactly_43_characters(self):
        self.assertIn("/^[A-Za-z0-9_-]{43}$/", self._js())

    def test_33_does_not_submit_the_manual_form_automatically(self):
        js = self._js()
        self.assertNotIn("form.submit(", js); self.assertNotIn("requestSubmit(", js)

    def test_34_detected_token_is_sent_directly(self):
        js = self._js()
        self.assertIn("sendCameraToken(token)", js)
        self.assertNotIn("tokenInput.value = token", js)

    def test_35_does_not_display_or_log_token(self):
        js = self._js()
        self.assertNotIn("console.", js); self.assertNotIn("status.textContent = token", js)

    def test_36_no_local_storage(self):
        self.assertNotIn("localStorage", self._js())

    def test_37_no_session_storage(self):
        self.assertNotIn("sessionStorage", self._js())

    def test_38_camera_uses_same_origin_json_post(self):
        js = self._js()
        self.assertIn("fetch(endpoint", js)
        self.assertIn('method: "POST"', js)
        self.assertIn('"X-CSRFToken"', js)
        self.assertIn("body: JSON.stringify({ token })", js)

    def test_39_no_websocket(self):
        self.assertNotIn("WebSocket", self._js())

    def test_40_stops_controls(self):
        self.assertIn("controls.stop()", self._js())

    def test_41_stops_media_tracks(self):
        js = self._js(); self.assertIn("getTracks()", js); self.assertIn("track.stop()", js)

    def test_42_stops_on_cancel(self):
        js = self._js(); self.assertIn('stopButton.addEventListener("click"', js)
        self.assertIn("stopCamera();", js)

    def test_43_manual_submit_does_not_stop_camera(self):
        js = self._js(); marker = 'form.addEventListener("submit"'
        self.assertIn(marker, js); self.assertNotIn("stopCamera();", js[js.index(marker):])

    def test_44_stops_on_pagehide(self):
        self.assertIn('window.addEventListener("pagehide", stopCamera)', self._js())

    def test_45_stops_on_navigation(self):
        self.assertIn('window.addEventListener("beforeunload", stopCamera)', self._js())

    def test_46_keeps_duplicate_detection_protection(self):
        js = self._js(); self.assertIn("if (processing) return", js)
        self.assertIn("processing = true", js); self.assertIn("processing = false", js)

    def test_47_manual_flow_works_without_javascript(self):
        token = credencial_service.generar_credencial(
            self.alumno["alumno_id"], self.database_path
        )["token"]
        self._login()
        response = self.client.post("/scanner/validar", data={
            "token": token, "preview_submit": "1"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("ENTRADA REGISTRADA", response.get_data(as_text=True))

    def test_48_camera_error_does_not_change_backend_errors(self):
        self._login()
        response = self.client.post("/scanner/validar", data={
            "token": "Z" * 43, "preview_submit": "1"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Token inválido.", response.get_data(as_text=True))
        self.assertNotIn("cámara disponible", response.get_data(as_text=True))

    def test_49_camera_layout_is_responsive(self):
        css = (SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn(".camera-video", css); self.assertIn("width: 100%", css)
        self.assertIn("@media (max-width: 390px)", css)

    def test_50_backend_transaction_contract_is_unchanged(self):
        route = (SRC_PATH / "edupass" / "web" / "scanner_routes.py").read_text(encoding="utf-8")
        service = (SRC_PATH / "edupass" / "modules" / "movimientos" / "movimientos_service.py").read_text(encoding="utf-8")
        repository = (SRC_PATH / "edupass" / "persistence" / "repositories" / "movimiento_repository.py").read_text(encoding="utf-8")
        self.assertIn("registrar_movimiento_automatico_directo", route)
        self.assertIn("BEGIN IMMEDIATE", repository)
        self.assertNotIn("getUserMedia", route)


if __name__ == "__main__":
    unittest.main()

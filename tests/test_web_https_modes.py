from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from flask import request
from werkzeug.middleware.proxy_fix import ProxyFix

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.web import create_app
from edupass.web import __main__ as web_main


class TestWebHttpsModes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "https_modes.sqlite"

    def tearDown(self):
        self.temp.cleanup()

    def _config(self, mode="off", **changes):
        config = {
            "TESTING": True,
            "SECRET_KEY": "https-test-secret",
            "DATABASE_PATH": self.database_path,
            "HTTPS_MODE": mode,
            "WTF_CSRF_ENABLED": False,
        }
        config.update(changes)
        return config

    def _secure_probe(self, app, headers=None):
        @app.get("/_secure_probe")
        def secure_probe():
            return "secure" if request.is_secure else "insecure"
        return app.test_client().get("/_secure_probe", headers=headers or {})

    def test_01_default_mode_is_off(self):
        with patch.dict(os.environ, {"EDUPASS_HTTPS_MODE": ""}, clear=False):
            os.environ.pop("EDUPASS_HTTPS_MODE", None)
            app = create_app(self._config())
        self.assertEqual(app.config["HTTPS_MODE"], "off")

    def test_02_off_keeps_http_scheme(self):
        app = create_app(self._config("off"))
        self.assertEqual(app.config["PREFERRED_URL_SCHEME"], "http")
        self.assertEqual(self._secure_probe(app).get_data(as_text=True), "insecure")

    def test_03_off_does_not_apply_proxyfix(self):
        app = create_app(self._config("off"))
        self.assertNotIsInstance(app.wsgi_app, ProxyFix)

    def test_04_off_does_not_trust_forwarded_proto(self):
        app = create_app(self._config("off"))
        response = self._secure_probe(app, {"X-Forwarded-Proto": "https"})
        self.assertEqual(response.get_data(as_text=True), "insecure")

    def test_05_off_does_not_mark_session_secure(self):
        app = create_app(self._config("off"))
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])

    def test_06_proxy_mode_is_allowed(self):
        app = create_app(self._config("proxy"))
        self.assertEqual(app.config["HTTPS_MODE"], "proxy")

    def test_07_proxy_applies_proxyfix(self):
        app = create_app(self._config("proxy"))
        self.assertIsInstance(app.wsgi_app, ProxyFix)

    def test_08_proxy_trusts_exactly_one_proto_and_host_proxy(self):
        proxy = create_app(self._config("proxy")).wsgi_app
        self.assertEqual(proxy.x_proto, 1)
        self.assertEqual(proxy.x_host, 1)
        self.assertEqual(proxy.x_for, 0)
        self.assertEqual(proxy.x_port, 0)
        self.assertEqual(proxy.x_prefix, 0)

    def test_09_proxy_forwarded_proto_makes_request_secure(self):
        app = create_app(self._config("proxy"))
        response = self._secure_probe(app, {"X-Forwarded-Proto": "https"})
        self.assertEqual(response.get_data(as_text=True), "secure")

    def test_10_proxy_uses_https_scheme(self):
        app = create_app(self._config("proxy"))
        self.assertEqual(app.config["PREFERRED_URL_SCHEME"], "https")

    def test_11_proxy_marks_session_secure(self):
        self.assertTrue(create_app(self._config("proxy")).config["SESSION_COOKIE_SECURE"])

    def test_12_proxy_marks_remember_cookie_secure(self):
        self.assertTrue(create_app(self._config("proxy")).config["REMEMBER_COOKIE_SECURE"])

    def test_13_proxy_rejects_wildcard_host_at_start(self):
        with patch.dict(os.environ, {"EDUPASS_HOST": "0.0.0.0"}):
            with self.assertRaisesRegex(RuntimeError, "127.0.0.1"):
                web_main._host_from_environment("proxy")

    def test_14_direct_mode_is_allowed(self):
        self.assertEqual(create_app(self._config("direct")).config["HTTPS_MODE"], "direct")

    def test_15_direct_does_not_apply_proxyfix(self):
        self.assertNotIsInstance(create_app(self._config("direct")).wsgi_app, ProxyFix)

    def test_16_direct_marks_secure_cookies(self):
        app = create_app(self._config("direct"))
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["REMEMBER_COOKIE_SECURE"])

    def test_17_direct_requires_certificate(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDUPASS_SSL_CERT", None)
            os.environ.pop("EDUPASS_SSL_KEY", None)
            with self.assertRaisesRegex(RuntimeError, "EDUPASS_SSL_CERT"):
                web_main._ssl_context_from_environment("direct")

    def test_18_direct_requires_private_key(self):
        cert = Path(self.temp.name) / "cert.pem"
        cert.write_text("temporary", encoding="utf-8")
        with patch.dict(os.environ, {"EDUPASS_SSL_CERT": str(cert)}, clear=False):
            os.environ.pop("EDUPASS_SSL_KEY", None)
            with self.assertRaisesRegex(RuntimeError, "EDUPASS_SSL_KEY"):
                web_main._ssl_context_from_environment("direct")

    def test_19_missing_certificate_prevents_start(self):
        key = Path(self.temp.name) / "key.pem"
        key.write_text("temporary", encoding="utf-8")
        with patch.dict(os.environ, {
            "EDUPASS_SSL_CERT": str(Path(self.temp.name) / "missing.pem"),
            "EDUPASS_SSL_KEY": str(key),
        }):
            with self.assertRaisesRegex(RuntimeError, "archivo existente"):
                web_main._ssl_context_from_environment("direct")

    def test_20_missing_key_prevents_start(self):
        cert = Path(self.temp.name) / "cert.pem"
        cert.write_text("temporary", encoding="utf-8")
        with patch.dict(os.environ, {
            "EDUPASS_SSL_CERT": str(cert),
            "EDUPASS_SSL_KEY": str(Path(self.temp.name) / "missing-key.pem"),
        }):
            with self.assertRaisesRegex(RuntimeError, "archivo existente"):
                web_main._ssl_context_from_environment("direct")

    def test_21_direct_passes_ssl_tuple(self):
        cert = Path(self.temp.name) / "cert.pem"
        key = Path(self.temp.name) / "key.pem"
        cert.write_text("certificate", encoding="utf-8")
        key.write_text("private key", encoding="utf-8")
        with patch.dict(os.environ, {
            "EDUPASS_SSL_CERT": str(cert), "EDUPASS_SSL_KEY": str(key)
        }):
            self.assertEqual(
                web_main._ssl_context_from_environment("direct"),
                (str(cert), str(key)),
            )

    def test_22_off_does_not_pass_certificate(self):
        self.assertIsNone(web_main._ssl_context_from_environment("off"))

    def test_23_proxy_does_not_pass_certificate(self):
        self.assertIsNone(web_main._ssl_context_from_environment("proxy"))

    def test_24_invalid_mode_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "off, proxy o direct"):
            create_app(self._config("invalid"))

    def test_25_main_output_does_not_print_secret_or_key(self):
        app = MagicMock()
        app.config = {"HTTPS_MODE": "off"}
        output = StringIO()
        with patch.object(web_main, "create_app", return_value=app), patch.dict(
            os.environ,
            {"EDUPASS_HOST": "127.0.0.1", "EDUPASS_PORT": "5000",
             "EDUPASS_SECRET_KEY": "SECRET-NOT-PRINTED"},
        ), redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(web_main.main(), 0)
        text = output.getvalue()
        self.assertNotIn("SECRET-NOT-PRINTED", text)
        self.assertNotIn("PRIVATE", text)

    def test_26_historical_create_app_still_works(self):
        app = create_app({
            "TESTING": True, "SECRET_KEY": "historical",
            "DATABASE_PATH": self.database_path,
        })
        self.assertEqual(app.config["HTTPS_MODE"], "off")

    def test_27_explicit_test_config_has_priority(self):
        with patch.dict(os.environ, {"EDUPASS_HTTPS_MODE": "proxy"}):
            app = create_app(self._config(
                "off", SESSION_COOKIE_SECURE=True,
                PREFERRED_URL_SCHEME="custom",
            ))
        self.assertEqual(app.config["HTTPS_MODE"], "off")
        self.assertTrue(app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app.config["PREFERRED_URL_SCHEME"], "custom")

    def test_28_hsts_is_not_enabled(self):
        app = create_app(self._config("proxy"))
        response = app.test_client().get("/login")
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_29_direct_has_no_silent_http_fallback(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDUPASS_SSL_CERT", None)
            os.environ.pop("EDUPASS_SSL_KEY", None)
            with self.assertRaises(RuntimeError):
                web_main._ssl_context_from_environment("direct")

    def test_30_certificate_paths_are_not_in_responses(self):
        cert_path = str(Path(self.temp.name) / "private-cert.pem")
        with patch.dict(os.environ, {"EDUPASS_SSL_CERT": cert_path}):
            app = create_app(self._config("direct"))
            body = app.test_client().get("/login").get_data(as_text=True)
        self.assertNotIn(cert_path, body)


if __name__ == "__main__":
    unittest.main()
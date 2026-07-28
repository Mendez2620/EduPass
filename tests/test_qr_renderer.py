from pathlib import Path
import inspect
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.credencial_qr import qr_renderer
from edupass.shared.errors import ValidationError


class TestQrRenderer(unittest.TestCase):
    TOKEN_A = "A" * 43
    TOKEN_B = "B" * 43

    def test_genera_svg_para_token_valido(self):
        svg = qr_renderer.generar_qr_svg(self.TOKEN_A)
        self.assertIn("<svg", svg)

    def test_devuelve_texto(self):
        self.assertIsInstance(qr_renderer.generar_qr_svg(self.TOKEN_A), str)

    def test_contiene_elemento_svg(self):
        svg = qr_renderer.generar_qr_svg(self.TOKEN_A)
        self.assertIn("</svg>", svg)

    def test_usa_documento_svg_completo(self):
        svg = qr_renderer.generar_qr_svg(self.TOKEN_A)
        self.assertTrue(svg.startswith("<?xml"))
        self.assertIn("xmlns=", svg)

    def test_svg_no_contiene_token_literal(self):
        svg = qr_renderer.generar_qr_svg(self.TOKEN_A)
        self.assertNotIn(self.TOKEN_A, svg)

    def test_svg_no_contiene_nombre_ni_matricula(self):
        svg = qr_renderer.generar_qr_svg(self.TOKEN_A)
        self.assertNotIn("Ana Alumna Demo", svg)
        self.assertNotIn("EDUPASS-1234", svg)

    def test_mismo_token_genera_resultado_consistente(self):
        self.assertEqual(
            qr_renderer.generar_qr_svg(self.TOKEN_A),
            qr_renderer.generar_qr_svg(self.TOKEN_A),
        )

    def test_tokens_distintos_generan_svg_diferente(self):
        self.assertNotEqual(
            qr_renderer.generar_qr_svg(self.TOKEN_A),
            qr_renderer.generar_qr_svg(self.TOKEN_B),
        )

    def test_rechaza_token_vacio(self):
        with self.assertRaises(ValidationError):
            qr_renderer.generar_qr_svg("")

    def test_rechaza_formato_invalido(self):
        with self.assertRaises(ValidationError):
            qr_renderer.generar_qr_svg("A" * 42 + "=")

    def test_no_crea_archivos(self):
        with tempfile.TemporaryDirectory() as directory:
            before = set(Path(directory).iterdir())
            qr_renderer.generar_qr_svg(self.TOKEN_A)
            after = set(Path(directory).iterdir())
        self.assertEqual(before, after)

    def test_no_requiere_pillow(self):
        source = inspect.getsource(qr_renderer).lower()
        self.assertNotIn("pillow", source)
        self.assertNotIn("from pil", source)

    def test_no_importa_flask(self):
        self.assertNotIn("flask", inspect.getsource(qr_renderer).lower())

    def test_no_importa_pyside6(self):
        self.assertNotIn("pyside6", inspect.getsource(qr_renderer).lower())


if __name__ == "__main__":
    unittest.main()
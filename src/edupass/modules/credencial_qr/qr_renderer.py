"""Renderizado en memoria de tokens QR opacos como SVG."""

from __future__ import annotations

from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from qrcode.image.svg import SvgPathFillImage

from edupass.modules.credencial_qr._token_utils import validar_formato_token


def generar_qr_svg(token: object) -> str:
    """Genera un documento SVG completo sin escribir archivos."""
    token_validado = validar_formato_token(token)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(token_validado)
    qr.make(fit=True)

    output = BytesIO()
    image = qr.make_image(image_factory=SvgPathFillImage)
    image.save(output)
    return output.getvalue().decode("utf-8")

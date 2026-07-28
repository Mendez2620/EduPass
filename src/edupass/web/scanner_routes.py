"""Rutas de validacion manual para personal autorizado de escaneo."""

from __future__ import annotations

from flask import Blueprint, current_app, make_response, render_template

from edupass.modules.validacion_qr import validacion_service
from edupass.shared.constants import ROL_ESCANER
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
)
from edupass.web.forms import ValidarTokenQRForm
from edupass.web.security import role_required


scanner_blueprint = Blueprint("scanner", __name__, url_prefix="/scanner")
_SECURITY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
}


def _render_validation(form, result=None, status=200):
    response = make_response(
        render_template(
            "scanner/validar_qr.html",
            form=form,
            result=result,
            title="Validar token QR",
        ),
        status,
    )
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


@scanner_blueprint.get("")
@role_required(ROL_ESCANER)
def dashboard():
    return render_template("scanner/dashboard.html", title="Escaneo")


@scanner_blueprint.route("/validar", methods=["GET", "POST"])
@role_required(ROL_ESCANER)
def validar_qr():
    form = ValidarTokenQRForm()
    if not form.is_submitted():
        return _render_validation(form)

    if not form.validate_on_submit():
        form.token.data = ""
        return _render_validation(
            form,
            {
                "estado": "rechazado",
                "mensaje": "Ingresa un token QR válido de 43 caracteres.",
            },
            400,
        )

    token = form.token.data
    form.token.data = ""
    try:
        result = validacion_service.consumir_token_qr(
            token,
            current_app.config["DATABASE_PATH"],
        )
        public_result = {
            "estado": "valido",
            "mensaje": result["mensaje"],
        }
    except QRVencidoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "El token ha vencido.",
        }
    except QRUtilizadoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "El token ya fue utilizado.",
        }
    except QRInvalidoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "El token proporcionado no es válido.",
        }
    except AlumnoInactivoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "El alumno se encuentra inactivo.",
        }
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible completar la validacion QR."
        )
        return _render_validation(
            form,
            {
                "estado": "rechazado",
                "mensaje": (
                    "No fue posible validar el token en este momento."
                ),
            },
            500,
        )

    return _render_validation(form, public_result)
"""Rutas de registro manual para personal autorizado de escaneo."""

from __future__ import annotations

from flask import Blueprint, current_app, make_response, render_template
from flask_login import current_user

from edupass.modules.movimientos import movimientos_service
from edupass.shared.constants import ROL_ESCANER
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
    SecuenciaMovimientoError,
    UsuarioEscanerInvalidoError,
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
            title="Registrar movimiento",
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
        form.tipo_movimiento.data = ""
        return _render_validation(
            form,
            {
                "estado": "rechazado",
                "mensaje": (
                    "Selecciona un tipo de movimiento e ingresa un token "
                    "QR válido de 43 caracteres."
                ),
            },
            400,
        )

    token = form.token.data
    tipo_movimiento = form.tipo_movimiento.data
    form.token.data = ""
    form.tipo_movimiento.data = ""
    try:
        result = movimientos_service.registrar_movimiento_con_token(
            token=token,
            tipo_movimiento=tipo_movimiento,
            usuario_id=current_user.usuario_id,
            database_path=current_app.config["DATABASE_PATH"],
        )
        public_result = {
            "estado": "valido",
            "mensaje": result["mensaje"],
        }
    except QRVencidoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "Token vencido.",
        }
    except QRUtilizadoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "Token ya utilizado.",
        }
    except QRInvalidoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "Token inválido.",
        }
    except AlumnoInactivoError:
        public_result = {
            "estado": "rechazado",
            "mensaje": "Alumno inactivo.",
        }
    except SecuenciaMovimientoError as exc:
        public_result = {
            "estado": "rechazado",
            "mensaje": str(exc),
        }
    except UsuarioEscanerInvalidoError:
        return _render_validation(
            form,
            {
                "estado": "rechazado",
                "mensaje": "Usuario de escáner no autorizado.",
            },
            403,
        )
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible registrar el movimiento."
        )
        return _render_validation(
            form,
            {
                "estado": "rechazado",
                "mensaje": "No fue posible registrar el movimiento.",
            },
            500,
        )

    return _render_validation(form, public_result)

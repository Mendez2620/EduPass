"""Registro directo de movimientos para personal de escaneo."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response, render_template, request
from flask_login import current_user

from edupass.modules.movimientos import movimientos_service
from edupass.shared.constants import ROL_ESCANER
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
    UsuarioEscanerInvalidoError,
)
from edupass.web.forms import PrevisualizarMovimientoForm
from edupass.web.security import role_required


scanner_blueprint = Blueprint("scanner", __name__, url_prefix="/scanner")
_SECURITY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=()",
}
def _render_validation(
    preview_form,
    result=None,
    status=200,
):
    response = make_response(
        render_template(
            "scanner/validar_qr.html",
            form=preview_form,
            result=result,
            title="Registrar movimiento",
        ),
        status,
    )
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


def _public_qr_error(error: Exception) -> str:
    if isinstance(error, QRVencidoError):
        return "Token vencido."
    if isinstance(error, QRUtilizadoError):
        return "Token ya utilizado."
    if isinstance(error, AlumnoInactivoError):
        return "Alumno inactivo."
    return "Token inválido."


@scanner_blueprint.get("")
@role_required(ROL_ESCANER)
def dashboard():
    return render_template("scanner/dashboard.html", title="Escaneo")


@scanner_blueprint.route("/validar", methods=["GET", "POST"])
@role_required(ROL_ESCANER)
def validar_qr():
    preview_form = PrevisualizarMovimientoForm()
    if request.method == "GET":
        return _render_validation(preview_form)
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        return _register_direct(preview_form, payload.get("token"), json_response=True)
    if not preview_form.validate_on_submit():
        preview_form.token.data = ""
        return _render_validation(
            preview_form,
            result={"estado": "rechazado", "mensaje": "Ingresa un token QR válido de 43 caracteres."},
            status=400,
        )
    token = preview_form.token.data
    preview_form.token.data = ""
    return _register_direct(preview_form, token, json_response=False)


def _register_direct(preview_form, token, *, json_response):
    try:
        movement = movimientos_service.registrar_movimiento_automatico_directo(
            token,
            current_user.usuario_id,
            database_path=current_app.config["DATABASE_PATH"],
        )
        result = {
            "estado": "valido",
            "mensaje": movement["mensaje"],
            "tipo_movimiento": movement["tipo_movimiento"],
            "alumno_nombre": movement["alumno_nombre"],
            "fecha_hora": movement["fecha_hora"],
        }
        status = 200
    except (QRVencidoError, QRUtilizadoError, QRInvalidoError, AlumnoInactivoError) as exc:
        result = {"estado": "rechazado", "mensaje": _public_qr_error(exc)}
        status = 400
    except UsuarioEscanerInvalidoError:
        result = {"estado": "rechazado", "mensaje": "Usuario de escáner no autorizado."}
        status = 403
    except RepositoryError:
        current_app.logger.warning("No fue posible registrar el movimiento.")
        result = {"estado": "rechazado", "mensaje": "No fue posible registrar el movimiento."}
        status = 500
    if json_response:
        response = jsonify(result)
        response.status_code = status
        for name, value in _SECURITY_HEADERS.items():
            response.headers[name] = value
        return response
    return _render_validation(preview_form, result=result, status=status)

"""Rutas de previsualización y registro para personal de escaneo."""

from __future__ import annotations

import secrets
from threading import Lock
from typing import Any

from flask import Blueprint, current_app, make_response, render_template, request
from flask_login import current_user

from edupass.modules.movimientos import movimientos_service
from edupass.shared.constants import ROL_ESCANER
from edupass.shared.errors import (
    AlumnoInactivoError,
    EstadoMovimientoCambiadoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
    TipoMovimientoInvalidoError,
    UsuarioEscanerInvalidoError,
)
from edupass.web.forms import (
    ConfirmarMovimientoForm,
    PrevisualizarMovimientoForm,
)
from edupass.web.security import role_required


scanner_blueprint = Blueprint("scanner", __name__, url_prefix="/scanner")
_SECURITY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=()",
}
_PREVIEW_EXTENSION = "movement_previews"
_PREVIEW_LOCK = Lock()


def _save_preview(preview: dict[str, Any]) -> str:
    preview_id = secrets.token_urlsafe(32)
    with _PREVIEW_LOCK:
        _preview_store_unlocked()[preview_id] = preview
    return preview_id


def _preview_store_unlocked() -> dict[str, dict[str, Any]]:
    return current_app.extensions.setdefault(_PREVIEW_EXTENSION, {})


def _get_preview(preview_id: str) -> dict[str, Any] | None:
    with _PREVIEW_LOCK:
        preview = _preview_store_unlocked().get(preview_id)
        return dict(preview) if preview is not None else None


def _update_preview(preview_id: str, preview: dict[str, Any]) -> None:
    with _PREVIEW_LOCK:
        if preview_id in _preview_store_unlocked():
            _preview_store_unlocked()[preview_id] = preview


def _delete_preview(preview_id: str) -> None:
    with _PREVIEW_LOCK:
        _preview_store_unlocked().pop(preview_id, None)


def _public_preview(preview: dict[str, Any]) -> dict[str, str]:
    return {
        "alumno_nombre": preview["alumno_nombre"],
        "matricula_enmascarada": preview["matricula_enmascarada"],
        "tipo_movimiento": preview["tipo_movimiento"],
    }


def _render_validation(
    preview_form,
    confirm_form=None,
    preview=None,
    result=None,
    status=200,
):
    response = make_response(
        render_template(
            "scanner/validar_qr.html",
            form=preview_form,
            confirm_form=confirm_form,
            preview=preview,
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

    if "confirm_submit" in request.form:
        return _confirm_movement(preview_form)
    return _preview_movement(preview_form)


def _preview_movement(preview_form):
    if not preview_form.validate_on_submit():
        preview_form.token.data = ""
        return _render_validation(
            preview_form,
            result={
                "estado": "rechazado",
                "mensaje": "Ingresa un token QR válido de 43 caracteres.",
            },
            status=400,
        )

    token = preview_form.token.data
    preview_form.token.data = ""
    try:
        preview = movimientos_service.previsualizar_movimiento_con_token(
            token,
            database_path=current_app.config["DATABASE_PATH"],
        )
    except (QRVencidoError, QRUtilizadoError, QRInvalidoError, AlumnoInactivoError) as exc:
        return _render_validation(
            preview_form,
            result={"estado": "rechazado", "mensaje": _public_qr_error(exc)},
        )
    except RepositoryError:
        current_app.logger.warning("No fue posible previsualizar el movimiento.")
        return _render_validation(
            preview_form,
            result={
                "estado": "rechazado",
                "mensaje": "No fue posible previsualizar el movimiento.",
            },
            status=500,
        )

    stored_preview = {
        "token_hash": preview["token_hash"],
        "usuario_id": current_user.usuario_id,
        "alumno_nombre": preview["alumno_nombre"],
        "matricula_enmascarada": preview["matricula_enmascarada"],
        "tipo_movimiento": preview["tipo_movimiento"],
    }
    preview_id = _save_preview(stored_preview)
    confirm_form = ConfirmarMovimientoForm()
    confirm_form.preview_id.data = preview_id
    confirm_form.tipo_esperado.data = stored_preview["tipo_movimiento"]
    return _render_validation(
        preview_form,
        confirm_form=confirm_form,
        preview=_public_preview(stored_preview),
    )


def _confirm_movement(preview_form):
    confirm_form = ConfirmarMovimientoForm()
    if not confirm_form.validate_on_submit():
        return _render_validation(
            preview_form,
            result={
                "estado": "rechazado",
                "mensaje": "La confirmación no es válida. Vuelve a escanear el QR.",
            },
            status=400,
        )

    preview_id = confirm_form.preview_id.data
    stored_preview = _get_preview(preview_id)
    if (
        stored_preview is None
        or stored_preview.get("usuario_id") != current_user.usuario_id
    ):
        return _render_validation(
            preview_form,
            result={
                "estado": "rechazado",
                "mensaje": "La previsualización ya no está disponible. Vuelve a escanear el QR.",
            },
            status=400,
        )

    if confirm_form.tipo_esperado.data != stored_preview["tipo_movimiento"]:
        confirm_form.tipo_esperado.data = stored_preview["tipo_movimiento"]
        return _render_validation(
            preview_form,
            confirm_form=confirm_form,
            preview=_public_preview(stored_preview),
            result={
                "estado": "advertencia",
                "mensaje": (
                    "La confirmación no coincide con la previsualización. "
                    "Revisa y vuelve a confirmar."
                ),
            },
            status=400,
        )

    try:
        result = movimientos_service.confirmar_movimiento_automatico(
            token_hash=stored_preview["token_hash"],
            tipo_esperado=stored_preview["tipo_movimiento"],
            usuario_id=current_user.usuario_id,
            database_path=current_app.config["DATABASE_PATH"],
        )
    except EstadoMovimientoCambiadoError as exc:
        stored_preview["tipo_movimiento"] = exc.tipo_movimiento_actual
        _update_preview(preview_id, stored_preview)
        confirm_form.tipo_esperado.data = exc.tipo_movimiento_actual
        return _render_validation(
            preview_form,
            confirm_form=confirm_form,
            preview=_public_preview(stored_preview),
            result={"estado": "advertencia", "mensaje": str(exc)},
        )
    except TipoMovimientoInvalidoError:
        return _render_validation(
            preview_form,
            confirm_form=confirm_form,
            preview=_public_preview(stored_preview),
            result={
                "estado": "rechazado",
                "mensaje": "La confirmación no es válida. Revisa el movimiento detectado.",
            },
            status=400,
        )
    except (QRVencidoError, QRUtilizadoError, QRInvalidoError, AlumnoInactivoError) as exc:
        _delete_preview(preview_id)
        return _render_validation(
            preview_form,
            result={"estado": "rechazado", "mensaje": _public_qr_error(exc)},
        )
    except UsuarioEscanerInvalidoError:
        return _render_validation(
            preview_form,
            result={
                "estado": "rechazado",
                "mensaje": "Usuario de escáner no autorizado.",
            },
            status=403,
        )
    except RepositoryError:
        current_app.logger.warning("No fue posible registrar el movimiento.")
        return _render_validation(
            preview_form,
            confirm_form=confirm_form,
            preview=_public_preview(stored_preview),
            result={
                "estado": "rechazado",
                "mensaje": "No fue posible registrar el movimiento.",
            },
            status=500,
        )

    _delete_preview(preview_id)
    return _render_validation(
        preview_form,
        result={
            "estado": "valido",
            "mensaje": result["mensaje"],
            "tipo_movimiento": result["tipo_movimiento"],
        },
    )

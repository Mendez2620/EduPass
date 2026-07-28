"""Rutas administrativas de consulta y credencial controlada."""

from __future__ import annotations

import base64
from typing import Any

from flask import Blueprint, current_app, make_response, render_template

from edupass.modules.alumnos import alumnos_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.credencial_qr.qr_renderer import generar_qr_svg
from edupass.shared.constants import ROL_ADMINISTRADOR
from edupass.shared.errors import (
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    RepositoryError,
    ValidationError,
)
from edupass.web.forms import GenerarCredencialForm, RenovarCredencialForm
from edupass.web.security import role_required


admin_blueprint = Blueprint("admin", __name__, url_prefix="/admin")
_SECURITY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
}


def _with_security_headers(response):
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


def _svg_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _render_credencial(
    credencial: dict[str, Any] | None,
    renovar_form: RenovarCredencialForm,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    qr_data_uri = None
    if credencial is not None:
        qr_data_uri = _svg_data_uri(generar_qr_svg(credencial["token"]))
    response = make_response(
        render_template(
            "admin/credencial.html",
            credencial=credencial,
            qr_data_uri=qr_data_uri,
            renovar_form=renovar_form,
            error_message=error_message,
            title="Credencial digital",
        ),
        status,
    )
    return _with_security_headers(response)


def _alumno_id_from_form(form) -> int:
    try:
        alumno_id = int(form.alumno_id.data)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            "El identificador del alumno no es valido."
        ) from exc
    if alumno_id <= 0:
        raise ValidationError("El identificador del alumno no es valido.")
    return alumno_id


def _handle_credencial_request(form, operation):
    if not form.validate_on_submit():
        return _render_credencial(
            None,
            RenovarCredencialForm(),
            error_message="No fue posible validar la solicitud.",
            status=400,
        )
    try:
        alumno_id = _alumno_id_from_form(form)
        credencial = operation(
            alumno_id,
            current_app.config["DATABASE_PATH"],
        )
        renovar_form = RenovarCredencialForm(
            alumno_id=credencial["alumno_id"]
        )
        return _render_credencial(credencial, renovar_form)
    except AlumnoNoEncontradoError:
        return _render_credencial(
            None,
            RenovarCredencialForm(),
            error_message="No se encontro el alumno solicitado.",
            status=404,
        )
    except AlumnoInactivoError:
        return _render_credencial(
            None,
            RenovarCredencialForm(),
            error_message="El alumno se encuentra inactivo.",
            status=409,
        )
    except ValidationError:
        return _render_credencial(
            None,
            RenovarCredencialForm(),
            error_message="No fue posible validar la solicitud.",
            status=400,
        )
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible preparar la credencial administrativa."
        )
        return _render_credencial(
            None,
            RenovarCredencialForm(),
            error_message=(
                "No fue posible generar la credencial en este momento."
            ),
            status=500,
        )


@admin_blueprint.get("")
@role_required(ROL_ADMINISTRADOR)
def dashboard():
    return render_template("admin/dashboard.html", title="Administracion")


@admin_blueprint.get("/alumnos")
@role_required(ROL_ADMINISTRADOR)
def alumnos_list():
    error_message = None
    alumnos = []
    try:
        service_rows = alumnos_service.listar_alumnos(
            current_app.config["DATABASE_PATH"]
        )
        alumnos = [
            {
                "alumno_id": row.get("alumno_id"),
                "nombre": row.get("nombre"),
                "matricula": row.get("matricula"),
                "grado": row.get("grado"),
                "grupo": row.get("grupo"),
                "estado": row.get("estado"),
            }
            for row in service_rows
        ]
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible obtener el listado administrativo de alumnos."
        )
        error_message = (
            "No fue posible consultar los alumnos en este momento."
        )

    return render_template(
        "admin/alumnos_list.html",
        alumnos=alumnos,
        error_message=error_message,
        credencial_form=GenerarCredencialForm(),
        title="Alumnos",
    )


@admin_blueprint.post("/credencial")
@role_required(ROL_ADMINISTRADOR)
def generar_credencial():
    return _handle_credencial_request(
        GenerarCredencialForm(),
        credencial_service.generar_credencial,
    )


@admin_blueprint.post("/credencial/renovar")
@role_required(ROL_ADMINISTRADOR)
def renovar_credencial():
    return _handle_credencial_request(
        RenovarCredencialForm(),
        credencial_service.renovar_token_qr,
    )
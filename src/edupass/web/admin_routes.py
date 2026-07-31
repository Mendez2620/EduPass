"""Rutas administrativas de consulta, credencial e historial."""

from __future__ import annotations

import base64
from typing import Any

from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from edupass.modules.alumnos import alumnos_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.credencial_qr.qr_renderer import generar_qr_svg
from edupass.modules.historial import historial_service
from edupass.shared.constants import ESTADO_ALUMNO_ACTIVO, ROL_ADMINISTRADOR
from edupass.shared.errors import (
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    MatriculaDuplicadaError,
    MovimientoNoEncontradoError,
    RepositoryError,
    ValidationError,
)
from edupass.web.forms import (
    AlumnoForm,
    EstadoAlumnoForm,
    GenerarCredencialForm,
    RenovarCredencialForm,
)
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


def _render_historial(*, status: int = 200, **context):
    response = make_response(
        render_template(
            "admin/historial.html",
            title="Historial de movimientos",
            **context,
        ),
        status,
    )
    return _with_security_headers(response)


def _render_movimiento_detalle(movimiento, *, status: int = 200):
    response = make_response(
        render_template(
            "admin/movimiento_detalle.html",
            movimiento=movimiento,
            title="Detalle de movimiento",
        ),
        status,
    )
    return _with_security_headers(response)


def _render_alumno_form(
    form: AlumnoForm,
    operation: str,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    title = "Registrar alumno" if operation == "crear" else "Editar alumno"
    return (
        render_template(
            "admin/alumno_form.html",
            form=form,
            operation=operation,
            error_message=error_message,
            title=title,
        ),
        status,
    )


def _render_alumno_operation_error(message: str, status: int):
    return (
        render_template(
            "admin/alumnos_list.html",
            alumnos=[],
            error_message=message,
            credencial_form=GenerarCredencialForm(),
            estado_form=EstadoAlumnoForm(),
            title="Alumnos",
        ),
        status,
    )


def _technical_alumno_error(operation: str):
    current_app.logger.warning(
        "No fue posible completar la operacion administrativa "
        "de alumnos: %s.",
        operation,
    )
    return _render_alumno_operation_error(
        "No fue posible completar la operación en este momento.",
        500,
    )

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


def _safe_students(rows):
    return [
        {
            "alumno_id": row.get("alumno_id"),
            "nombre": row.get("nombre"),
            "matricula": row.get("matricula"),
            "grado": row.get("grado"),
            "grupo": row.get("grupo"),
            "estado": row.get("estado"),
        }
        for row in rows
    ]


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
        alumnos = _safe_students(
            alumnos_service.listar_alumnos(
                current_app.config["DATABASE_PATH"]
            )
        )
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
        estado_form=EstadoAlumnoForm(),
        title="Alumnos",
    )


@admin_blueprint.route("/alumnos/nuevo", methods=["GET", "POST"])
@role_required(ROL_ADMINISTRADOR)
def alumno_nuevo():
    form = AlumnoForm()
    if not form.is_submitted():
        return _render_alumno_form(form, "crear")
    if not form.validate_on_submit():
        return _render_alumno_form(
            form,
            "crear",
            error_message="Revisa los datos obligatorios del alumno.",
            status=400,
        )

    try:
        alumnos_service.registrar_alumno(
            nombre=form.nombre.data,
            matricula=form.matricula.data,
            grado=form.grado.data,
            grupo=form.grupo.data,
            fotografia=None,
            estado=ESTADO_ALUMNO_ACTIVO,
            database_path=current_app.config["DATABASE_PATH"],
        )
    except MatriculaDuplicadaError:
        return _render_alumno_form(
            form,
            "crear",
            error_message="La matrícula ya está registrada.",
            status=409,
        )
    except ValidationError:
        return _render_alumno_form(
            form,
            "crear",
            error_message="Revisa los datos obligatorios del alumno.",
            status=400,
        )
    except RepositoryError:
        return _technical_alumno_error("registrar")

    flash("Alumno registrado correctamente.", "success")
    return redirect(url_for("admin.alumnos_list"))


@admin_blueprint.route(
    "/alumnos/<int:alumno_id>/editar",
    methods=["GET", "POST"],
)
@role_required(ROL_ADMINISTRADOR)
def alumno_editar(alumno_id: int):
    try:
        alumno = alumnos_service.consultar_alumno_por_id(
            alumno_id,
            current_app.config["DATABASE_PATH"],
        )
    except AlumnoNoEncontradoError:
        return _render_alumno_operation_error(
            "No se encontró el alumno solicitado.",
            404,
        )
    except ValidationError:
        return _render_alumno_operation_error(
            "Revisa los datos obligatorios del alumno.",
            400,
        )
    except RepositoryError:
        return _technical_alumno_error("consultar para editar")

    form = AlumnoForm()
    if not form.is_submitted():
        form.nombre.data = alumno["nombre"]
        form.matricula.data = alumno["matricula"]
        form.grado.data = alumno["grado"]
        form.grupo.data = alumno["grupo"]
        return _render_alumno_form(form, "editar")
    if not form.validate_on_submit():
        return _render_alumno_form(
            form,
            "editar",
            error_message="Revisa los datos obligatorios del alumno.",
            status=400,
        )

    try:
        alumnos_service.editar_alumno(
            alumno_id=alumno_id,
            nombre=form.nombre.data,
            matricula=form.matricula.data,
            grado=form.grado.data,
            grupo=form.grupo.data,
            fotografia=alumno["fotografia"],
            database_path=current_app.config["DATABASE_PATH"],
        )
    except AlumnoNoEncontradoError:
        return _render_alumno_operation_error(
            "No se encontró el alumno solicitado.",
            404,
        )
    except MatriculaDuplicadaError:
        return _render_alumno_form(
            form,
            "editar",
            error_message="La matrícula ya está registrada.",
            status=409,
        )
    except ValidationError:
        return _render_alumno_form(
            form,
            "editar",
            error_message="Revisa los datos obligatorios del alumno.",
            status=400,
        )
    except RepositoryError:
        return _technical_alumno_error("editar")

    flash("Alumno actualizado correctamente.", "success")
    return redirect(url_for("admin.alumnos_list"))


def _cambiar_estado_alumno(
    alumno_id: int,
    operation,
    success_message: str,
):
    form = EstadoAlumnoForm()
    if not form.validate_on_submit():
        return _render_alumno_operation_error(
            "Revisa los datos obligatorios del alumno.",
            400,
        )
    try:
        operation(alumno_id, current_app.config["DATABASE_PATH"])
    except AlumnoNoEncontradoError:
        return _render_alumno_operation_error(
            "No se encontró el alumno solicitado.",
            404,
        )
    except ValidationError:
        return _render_alumno_operation_error(
            "Revisa los datos obligatorios del alumno.",
            400,
        )
    except RepositoryError:
        return _technical_alumno_error("cambiar estado")

    flash(success_message, "success")
    return redirect(url_for("admin.alumnos_list"))


@admin_blueprint.post("/alumnos/<int:alumno_id>/activar")
@role_required(ROL_ADMINISTRADOR)
def alumno_activar(alumno_id: int):
    return _cambiar_estado_alumno(
        alumno_id,
        alumnos_service.activar_alumno,
        "Alumno activado correctamente.",
    )


@admin_blueprint.post("/alumnos/<int:alumno_id>/desactivar")
@role_required(ROL_ADMINISTRADOR)
def alumno_desactivar(alumno_id: int):
    return _cambiar_estado_alumno(
        alumno_id,
        alumnos_service.desactivar_alumno,
        "Alumno desactivado correctamente.",
    )

@admin_blueprint.get("/historial")
@role_required(ROL_ADMINISTRADOR)
def historial():
    try:
        alumnos = _safe_students(
            alumnos_service.listar_alumnos(
                current_app.config["DATABASE_PATH"]
            )
        )
        return _render_historial(
            alumnos=alumnos,
            historial=None,
            error_message=None,
        )
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible obtener los alumnos para el historial."
        )
        return _render_historial(
            alumnos=[],
            historial=None,
            error_message="No fue posible consultar el historial.",
            status=500,
        )


@admin_blueprint.get("/historial/<int:alumno_id>")
@role_required(ROL_ADMINISTRADOR)
def historial_alumno(alumno_id: int):
    raw_page = request.args.get("page", "1")
    try:
        page = int(raw_page)
        historial_data = historial_service.consultar_historial_alumno(
            alumno_id,
            pagina=page,
            database_path=current_app.config["DATABASE_PATH"],
        )
        return _render_historial(
            alumnos=[],
            historial=historial_data,
            error_message=None,
        )
    except (TypeError, ValueError, ValidationError):
        return _render_historial(
            alumnos=[],
            historial=None,
            error_message="La página solicitada no es válida.",
            status=400,
        )
    except (AlumnoNoEncontradoError, MovimientoNoEncontradoError):
        return _render_historial(
            alumnos=[],
            historial=None,
            error_message="No se encontró el historial solicitado.",
            status=404,
        )
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible consultar el historial del alumno."
        )
        return _render_historial(
            alumnos=[],
            historial=None,
            error_message="No fue posible consultar el historial.",
            status=500,
        )


@admin_blueprint.get(
    "/historial/<int:alumno_id>/movimientos/<int:movimiento_id>"
)
@role_required(ROL_ADMINISTRADOR)
def movimiento_detalle(alumno_id: int, movimiento_id: int):
    try:
        movimiento = historial_service.consultar_movimiento(
            movimiento_id,
            alumno_id=alumno_id,
            database_path=current_app.config["DATABASE_PATH"],
        )
        return _render_movimiento_detalle(movimiento)
    except MovimientoNoEncontradoError:
        return _render_movimiento_detalle(None, status=404)
    except RepositoryError:
        current_app.logger.warning(
            "No fue posible consultar el detalle del movimiento."
        )
        response = make_response(
            render_template(
                "admin/movimiento_detalle.html",
                movimiento=None,
                error_message="No fue posible consultar el movimiento.",
                title="Detalle de movimiento",
            ),
            500,
        )
        return _with_security_headers(response)


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

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
    session,
    url_for,
)

from edupass.modules.alumnos import alumnos_service, cuentas_alumno_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.credencial_qr.qr_renderer import generar_qr_svg
from edupass.modules.historial import historial_service
from edupass.modules.auth import usuarios_service
from edupass.shared.constants import ESTADO_ALUMNO_ACTIVO, ROL_ADMINISTRADOR
from edupass.shared.errors import (
    AuthorizationError,
    AutoBloqueoAdministradorError,
    DuplicateUserError,
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    AlumnoYaTieneUsuarioError,
    MatriculaDuplicadaError,
    MovimientoNoEncontradoError,
    RepositoryError,
    UltimoAdministradorActivoError,
    UsuarioNoEncontradoError,
    UsuarioNoEsAlumnoError,
    ValidationError,
    VinculoUsuarioAlumnoNoEncontradoError,
)
from edupass.web.forms import (
    AdministradorCrearForm,
    AdministradorEditarForm,
    AdministradorPasswordForm,
    AlumnoForm,
    CuentaAlumnoCrearForm,
    CuentaAlumnoEditarForm,
    CuentaAlumnoPasswordForm,
    EstadoAlumnoForm,
    EstadoUsuarioForm,
    EscanerCrearForm,
    EscanerEditarForm,
    EscanerPasswordForm,
    GenerarCredencialForm,
    RenovarCredencialForm,
)
from edupass.web.security import role_required
from flask_login import current_user, logout_user


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


def _safe_administrators(rows):
    return [
        {
            "usuario_id": row.get("usuario_id"),
            "nombre": row.get("nombre"),
            "correo": row.get("correo"),
            "estado": row.get("estado"),
            "rol_nombre": row.get("rol_nombre"),
        }
        for row in rows
    ]


def _render_administrador_form(
    form,
    operation: str,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    title = (
        "Registrar administrador"
        if operation == "crear"
        else "Editar administrador"
    )
    return (
        render_template(
            "admin/administrador_form.html",
            form=form,
            operation=operation,
            error_message=error_message,
            title=title,
        ),
        status,
    )


def _render_administrador_password(
    form,
    administrador,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    return (
        render_template(
            "admin/administrador_password.html",
            form=form,
            administrador=administrador,
            error_message=error_message,
            title="Restablecer contraseña",
        ),
        status,
    )


def _render_administrador_operation_error(message: str, status: int):
    return (
        render_template(
            "admin/administradores_list.html",
            administradores=[],
            error_message=message,
            estado_form=EstadoUsuarioForm(),
            title="Administradores",
        ),
        status,
    )


def _technical_administrador_error(operation: str):
    current_app.logger.warning(
        "No fue posible completar la operacion administrativa de usuarios: %s.",
        operation,
    )
    return _render_administrador_operation_error(
        "No fue posible completar la operación en este momento.",
        500,
    )


@admin_blueprint.get("")
@role_required(ROL_ADMINISTRADOR)
def dashboard():
    return render_template("admin/dashboard.html", title="Administracion")


@admin_blueprint.get("/administradores")
@role_required(ROL_ADMINISTRADOR)
def administradores_list():
    try:
        administradores = _safe_administrators(
            usuarios_service.listar_administradores(
                current_app.config["DATABASE_PATH"]
            )
        )
    except RepositoryError:
        return _technical_administrador_error("listar")

    return render_template(
        "admin/administradores_list.html",
        administradores=administradores,
        error_message=None,
        estado_form=EstadoUsuarioForm(),
        title="Administradores",
    )


@admin_blueprint.route("/administradores/nuevo", methods=["GET", "POST"])
@role_required(ROL_ADMINISTRADOR)
def administrador_nuevo():
    form = AdministradorCrearForm()
    if not form.is_submitted():
        return _render_administrador_form(form, "crear")
    if not form.validate_on_submit():
        return _render_administrador_form(
            form,
            "crear",
            error_message="Revisa los datos obligatorios del administrador.",
            status=400,
        )

    try:
        usuarios_service.crear_administrador(
            form.nombre.data,
            form.correo.data,
            form.password.data,
            current_app.config["DATABASE_PATH"],
        )
    except DuplicateUserError:
        return _render_administrador_form(
            form,
            "crear",
            error_message="El correo ya está registrado.",
            status=409,
        )
    except ValidationError:
        return _render_administrador_form(
            form,
            "crear",
            error_message="Revisa los datos obligatorios del administrador.",
            status=400,
        )
    except RepositoryError:
        return _technical_administrador_error("registrar")

    flash("Administrador registrado correctamente.", "success")
    return redirect(url_for("admin.administradores_list"))


@admin_blueprint.route(
    "/administradores/<int:usuario_id>/editar",
    methods=["GET", "POST"],
)
@role_required(ROL_ADMINISTRADOR)
def administrador_editar(usuario_id: int):
    try:
        administrador = usuarios_service.consultar_administrador(
            usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_administrador_operation_error(
            "No se encontró el administrador solicitado.", 404
        )
    except ValidationError:
        return _render_administrador_operation_error(
            "Revisa los datos obligatorios del administrador.", 400
        )
    except RepositoryError:
        return _technical_administrador_error("consultar para editar")

    form = AdministradorEditarForm()
    if not form.is_submitted():
        form.nombre.data = administrador["nombre"]
        form.correo.data = administrador["correo"]
        return _render_administrador_form(form, "editar")
    if not form.validate_on_submit():
        return _render_administrador_form(
            form,
            "editar",
            error_message="Revisa los datos obligatorios del administrador.",
            status=400,
        )

    try:
        usuarios_service.editar_administrador(
            usuario_id,
            form.nombre.data,
            form.correo.data,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_administrador_operation_error(
            "No se encontró el administrador solicitado.", 404
        )
    except DuplicateUserError:
        return _render_administrador_form(
            form,
            "editar",
            error_message="El correo ya está registrado.",
            status=409,
        )
    except ValidationError:
        return _render_administrador_form(
            form,
            "editar",
            error_message="Revisa los datos obligatorios del administrador.",
            status=400,
        )
    except RepositoryError:
        return _technical_administrador_error("editar")

    flash("Administrador actualizado correctamente.", "success")
    return redirect(url_for("admin.administradores_list"))


@admin_blueprint.route(
    "/administradores/<int:usuario_id>/password",
    methods=["GET", "POST"],
)
@role_required(ROL_ADMINISTRADOR)
def administrador_password(usuario_id: int):
    try:
        administrador = usuarios_service.consultar_administrador(
            usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_administrador_operation_error(
            "No se encontró el administrador solicitado.", 404
        )
    except ValidationError:
        return _render_administrador_operation_error(
            "Revisa los datos obligatorios del administrador.", 400
        )
    except RepositoryError:
        return _technical_administrador_error("consultar contraseña")

    form = AdministradorPasswordForm()
    if not form.is_submitted():
        return _render_administrador_password(form, administrador)
    if not form.validate_on_submit():
        return _render_administrador_password(
            form,
            administrador,
            error_message="Revisa los datos obligatorios del administrador.",
            status=400,
        )

    try:
        usuarios_service.restablecer_password_administrador(
            usuario_id,
            form.password.data,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_administrador_operation_error(
            "No se encontró el administrador solicitado.", 404
        )
    except ValidationError:
        return _render_administrador_password(
            form,
            administrador,
            error_message="Revisa los datos obligatorios del administrador.",
            status=400,
        )
    except RepositoryError:
        return _technical_administrador_error("restablecer contraseña")

    if usuario_id == current_user.usuario_id:
        logout_user()
        session.clear()
        flash(
            "Contraseña actualizada. Inicia sesión nuevamente.",
            "success",
        )
        return redirect(url_for("auth.login"))

    flash("Contraseña actualizada correctamente.", "success")
    return redirect(url_for("admin.administradores_list"))


def _cambiar_estado_administrador(
    usuario_id: int,
    operation,
    success_message: str,
):
    form = EstadoUsuarioForm()
    if not form.validate_on_submit():
        return _render_administrador_operation_error(
            "Revisa los datos obligatorios del administrador.", 400
        )
    try:
        operation(
            usuario_id,
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_administrador_operation_error(
            "No se encontró el administrador solicitado.", 404
        )
    except AutoBloqueoAdministradorError:
        return _render_administrador_operation_error(
            "No puedes desactivar tu propia cuenta.", 409
        )
    except UltimoAdministradorActivoError:
        return _render_administrador_operation_error(
            "No se puede desactivar al último administrador activo.", 409
        )
    except ValidationError:
        return _render_administrador_operation_error(
            "Revisa los datos obligatorios del administrador.", 400
        )
    except AuthorizationError:
        return _render_administrador_operation_error(
            "Acceso no autorizado.", 403
        )
    except RepositoryError:
        return _technical_administrador_error("cambiar estado")

    flash(success_message, "success")
    return redirect(url_for("admin.administradores_list"))


@admin_blueprint.post("/administradores/<int:usuario_id>/activar")
@role_required(ROL_ADMINISTRADOR)
def administrador_activar(usuario_id: int):
    return _cambiar_estado_administrador(
        usuario_id,
        usuarios_service.activar_administrador,
        "Administrador activado correctamente.",
    )


@admin_blueprint.post("/administradores/<int:usuario_id>/desactivar")
@role_required(ROL_ADMINISTRADOR)
def administrador_desactivar(usuario_id: int):
    return _cambiar_estado_administrador(
        usuario_id,
        usuarios_service.desactivar_administrador,
        "Administrador desactivado correctamente.",
    )


def _safe_scanners(rows):
    return [
        {
            "usuario_id": row.get("usuario_id"),
            "nombre": row.get("nombre"),
            "correo": row.get("correo"),
            "estado": row.get("estado"),
            "rol_nombre": row.get("rol_nombre"),
        }
        for row in rows
    ]


def _render_escaner_form(
    form,
    operation: str,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    title = "Registrar escáner" if operation == "crear" else "Editar escáner"
    return (
        render_template(
            "admin/escaner_form.html",
            form=form,
            operation=operation,
            error_message=error_message,
            title=title,
        ),
        status,
    )


def _render_escaner_password(
    form,
    escaner,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    return (
        render_template(
            "admin/escaner_password.html",
            form=form,
            escaner=escaner,
            error_message=error_message,
            title="Restablecer contraseña del escáner",
        ),
        status,
    )


def _render_escaner_operation_error(message: str, status: int):
    return (
        render_template(
            "admin/escaneres_list.html",
            escaneres=[],
            error_message=message,
            estado_form=EstadoUsuarioForm(),
            title="Personal de escaneo",
        ),
        status,
    )


def _technical_escaner_error(operation: str):
    current_app.logger.warning(
        "No fue posible completar la operacion administrativa de escaneres: %s.",
        operation,
    )
    return _render_escaner_operation_error(
        "No fue posible completar la operación en este momento.", 500
    )


@admin_blueprint.get("/escaneres")
@role_required(ROL_ADMINISTRADOR)
def escaneres_list():
    try:
        escaneres = _safe_scanners(
            usuarios_service.listar_escaneres(
                current_app.config["DATABASE_PATH"]
            )
        )
    except RepositoryError:
        return _technical_escaner_error("listar")
    return render_template(
        "admin/escaneres_list.html",
        escaneres=escaneres,
        error_message=None,
        estado_form=EstadoUsuarioForm(),
        title="Personal de escaneo",
    )


@admin_blueprint.route("/escaneres/nuevo", methods=["GET", "POST"])
@role_required(ROL_ADMINISTRADOR)
def escaner_nuevo():
    form = EscanerCrearForm()
    if not form.is_submitted():
        return _render_escaner_form(form, "crear")
    if not form.validate_on_submit():
        return _render_escaner_form(
            form,
            "crear",
            error_message="Revisa los datos obligatorios del escáner.",
            status=400,
        )
    try:
        usuarios_service.crear_escaner(
            form.nombre.data,
            form.correo.data,
            form.password.data,
            current_app.config["DATABASE_PATH"],
        )
    except DuplicateUserError:
        return _render_escaner_form(
            form,
            "crear",
            error_message="El correo ya está registrado.",
            status=409,
        )
    except ValidationError:
        return _render_escaner_form(
            form,
            "crear",
            error_message="Revisa los datos obligatorios del escáner.",
            status=400,
        )
    except RepositoryError:
        return _technical_escaner_error("registrar")
    flash("Escáner registrado correctamente.", "success")
    return redirect(url_for("admin.escaneres_list"))


@admin_blueprint.route(
    "/escaneres/<int:usuario_id>/editar", methods=["GET", "POST"]
)
@role_required(ROL_ADMINISTRADOR)
def escaner_editar(usuario_id: int):
    try:
        escaner = usuarios_service.consultar_escaner(
            usuario_id, current_app.config["DATABASE_PATH"]
        )
    except UsuarioNoEncontradoError:
        return _render_escaner_operation_error(
            "No se encontró el escáner solicitado.", 404
        )
    except ValidationError:
        return _render_escaner_operation_error(
            "Revisa los datos obligatorios del escáner.", 400
        )
    except RepositoryError:
        return _technical_escaner_error("consultar para editar")

    form = EscanerEditarForm()
    if not form.is_submitted():
        form.nombre.data = escaner["nombre"]
        form.correo.data = escaner["correo"]
        return _render_escaner_form(form, "editar")
    if not form.validate_on_submit():
        return _render_escaner_form(
            form,
            "editar",
            error_message="Revisa los datos obligatorios del escáner.",
            status=400,
        )
    try:
        usuarios_service.editar_escaner(
            usuario_id,
            form.nombre.data,
            form.correo.data,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_escaner_operation_error(
            "No se encontró el escáner solicitado.", 404
        )
    except DuplicateUserError:
        return _render_escaner_form(
            form,
            "editar",
            error_message="El correo ya está registrado.",
            status=409,
        )
    except ValidationError:
        return _render_escaner_form(
            form,
            "editar",
            error_message="Revisa los datos obligatorios del escáner.",
            status=400,
        )
    except RepositoryError:
        return _technical_escaner_error("editar")
    flash("Escáner actualizado correctamente.", "success")
    return redirect(url_for("admin.escaneres_list"))


@admin_blueprint.route(
    "/escaneres/<int:usuario_id>/password", methods=["GET", "POST"]
)
@role_required(ROL_ADMINISTRADOR)
def escaner_password(usuario_id: int):
    try:
        escaner = usuarios_service.consultar_escaner(
            usuario_id, current_app.config["DATABASE_PATH"]
        )
    except UsuarioNoEncontradoError:
        return _render_escaner_operation_error(
            "No se encontró el escáner solicitado.", 404
        )
    except ValidationError:
        return _render_escaner_operation_error(
            "Revisa los datos obligatorios del escáner.", 400
        )
    except RepositoryError:
        return _technical_escaner_error("consultar contraseña")

    form = EscanerPasswordForm()
    if not form.is_submitted():
        return _render_escaner_password(form, escaner)
    if not form.validate_on_submit():
        return _render_escaner_password(
            form,
            escaner,
            error_message="Revisa los datos obligatorios del escáner.",
            status=400,
        )
    try:
        usuarios_service.restablecer_password_escaner(
            usuario_id,
            form.password.data,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_escaner_operation_error(
            "No se encontró el escáner solicitado.", 404
        )
    except ValidationError:
        return _render_escaner_password(
            form,
            escaner,
            error_message="Revisa los datos obligatorios del escáner.",
            status=400,
        )
    except RepositoryError:
        return _technical_escaner_error("restablecer contraseña")
    flash("Contraseña del escáner actualizada correctamente.", "success")
    return redirect(url_for("admin.escaneres_list"))


def _cambiar_estado_escaner(usuario_id: int, operation, success_message: str):
    form = EstadoUsuarioForm()
    if not form.validate_on_submit():
        return _render_escaner_operation_error(
            "Revisa los datos obligatorios del escáner.", 400
        )
    try:
        operation(
            usuario_id,
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except UsuarioNoEncontradoError:
        return _render_escaner_operation_error(
            "No se encontró el escáner solicitado.", 404
        )
    except ValidationError:
        return _render_escaner_operation_error(
            "Revisa los datos obligatorios del escáner.", 400
        )
    except AuthorizationError:
        return _render_escaner_operation_error("Acceso no autorizado.", 403)
    except RepositoryError:
        return _technical_escaner_error("cambiar estado")
    flash(success_message, "success")
    return redirect(url_for("admin.escaneres_list"))


@admin_blueprint.post("/escaneres/<int:usuario_id>/activar")
@role_required(ROL_ADMINISTRADOR)
def escaner_activar(usuario_id: int):
    return _cambiar_estado_escaner(
        usuario_id,
        usuarios_service.activar_escaner,
        "Escáner activado correctamente.",
    )


@admin_blueprint.post("/escaneres/<int:usuario_id>/desactivar")
@role_required(ROL_ADMINISTRADOR)
def escaner_desactivar(usuario_id: int):
    return _cambiar_estado_escaner(
        usuario_id,
        usuarios_service.desactivar_escaner,
        "Escáner desactivado correctamente.",
    )


def _render_cuentas_alumno_list(
    cuentas,
    alumnos_sin_cuenta,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    return (
        render_template(
            "admin/cuentas_alumnos_list.html",
            cuentas=cuentas,
            alumnos_sin_cuenta=alumnos_sin_cuenta,
            error_message=error_message,
            estado_form=EstadoUsuarioForm(),
            title="Cuentas de alumnos",
        ),
        status,
    )


def _render_cuenta_alumno_form(
    form,
    operation: str,
    *,
    cuenta=None,
    error_message: str | None = None,
    status: int = 200,
):
    title = (
        "Crear cuenta de alumno"
        if operation == "crear"
        else "Editar cuenta de alumno"
    )
    return (
        render_template(
            "admin/cuenta_alumno_form.html",
            form=form,
            operation=operation,
            cuenta=cuenta,
            error_message=error_message,
            title=title,
        ),
        status,
    )


def _render_cuenta_alumno_password(
    form,
    cuenta,
    *,
    error_message: str | None = None,
    status: int = 200,
):
    return (
        render_template(
            "admin/cuenta_alumno_password.html",
            form=form,
            cuenta=cuenta,
            error_message=error_message,
            title="Restablecer contraseña de alumno",
        ),
        status,
    )


def _cuenta_alumno_operation_error(message: str, status: int):
    return _render_cuentas_alumno_list(
        [], [], error_message=message, status=status
    )


def _technical_cuenta_alumno_error(operation: str):
    current_app.logger.warning(
        "No fue posible completar la operacion de cuentas alumno: %s.",
        operation,
    )
    return _cuenta_alumno_operation_error(
        "No fue posible completar la operación en este momento.", 500
    )


def _cuenta_alumno_not_found():
    return _cuenta_alumno_operation_error(
        "No se encontró la cuenta de alumno solicitada.", 404
    )


def _configure_student_choices(form, students):
    form.alumno_id.choices = [
        (
            student["alumno_id"],
            f'{student["nombre"]} — {student["matricula"]} — '
            f'{student["estado"]}',
        )
        for student in students
    ]


@admin_blueprint.get("/cuentas-alumnos")
@role_required(ROL_ADMINISTRADOR)
def cuentas_alumnos_list():
    try:
        cuentas = cuentas_alumno_service.listar_cuentas_alumno(
            current_app.config["DATABASE_PATH"]
        )
        alumnos_sin_cuenta = (
            cuentas_alumno_service.listar_alumnos_sin_cuenta(
                current_app.config["DATABASE_PATH"]
            )
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("listar")
    return _render_cuentas_alumno_list(cuentas, alumnos_sin_cuenta)


@admin_blueprint.route("/cuentas-alumnos/nueva", methods=["GET", "POST"])
@role_required(ROL_ADMINISTRADOR)
def cuenta_alumno_nueva():
    try:
        students = cuentas_alumno_service.listar_alumnos_sin_cuenta(
            current_app.config["DATABASE_PATH"]
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("preparar registro")

    form = CuentaAlumnoCrearForm()
    _configure_student_choices(form, students)
    if not form.is_submitted():
        return _render_cuenta_alumno_form(form, "crear")
    if not form.validate_on_submit():
        try:
            submitted_student_id = int(request.form.get("alumno_id", ""))
        except (TypeError, ValueError):
            submitted_student_id = None
        available_ids = {student["alumno_id"] for student in students}
        if (
            submitted_student_id is not None
            and submitted_student_id > 0
            and submitted_student_id not in available_ids
        ):
            try:
                alumnos_service.consultar_alumno_por_id(
                    submitted_student_id,
                    current_app.config["DATABASE_PATH"],
                )
            except (AlumnoNoEncontradoError, ValidationError):
                pass
            except RepositoryError:
                return _technical_cuenta_alumno_error(
                    "validar alumno seleccionado"
                )
            else:
                return _render_cuenta_alumno_form(
                    form,
                    "crear",
                    error_message=(
                        "El alumno ya tiene una cuenta vinculada."
                    ),
                    status=409,
                )
        return _render_cuenta_alumno_form(
            form,
            "crear",
            error_message=(
                "Revisa los datos obligatorios de la cuenta del alumno."
            ),
            status=400,
        )
    try:
        cuentas_alumno_service.crear_cuenta_alumno(
            form.alumno_id.data,
            form.correo.data,
            form.password.data,
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except DuplicateUserError:
        return _render_cuenta_alumno_form(
            form,
            "crear",
            error_message="El correo ya está registrado.",
            status=409,
        )
    except AlumnoYaTieneUsuarioError:
        return _render_cuenta_alumno_form(
            form,
            "crear",
            error_message="El alumno ya tiene una cuenta vinculada.",
            status=409,
        )
    except AlumnoInactivoError:
        return _render_cuenta_alumno_form(
            form,
            "crear",
            error_message=(
                "No se puede activar una cuenta para un alumno inactivo."
            ),
            status=409,
        )
    except (AlumnoNoEncontradoError, UsuarioNoEncontradoError):
        return _cuenta_alumno_not_found()
    except AuthorizationError:
        return _cuenta_alumno_operation_error("Acceso no autorizado.", 403)
    except ValidationError:
        return _render_cuenta_alumno_form(
            form,
            "crear",
            error_message=(
                "Revisa los datos obligatorios de la cuenta del alumno."
            ),
            status=400,
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("registrar")

    flash("Cuenta de alumno registrada correctamente.", "success")
    return redirect(url_for("admin.cuentas_alumnos_list"))


@admin_blueprint.route(
    "/cuentas-alumnos/<int:usuario_id>/editar", methods=["GET", "POST"]
)
@role_required(ROL_ADMINISTRADOR)
def cuenta_alumno_editar(usuario_id: int):
    try:
        account = cuentas_alumno_service.consultar_cuenta_alumno(
            usuario_id, current_app.config["DATABASE_PATH"]
        )
    except (
        UsuarioNoEncontradoError,
        UsuarioNoEsAlumnoError,
        VinculoUsuarioAlumnoNoEncontradoError,
    ):
        return _cuenta_alumno_not_found()
    except ValidationError:
        return _cuenta_alumno_operation_error(
            "Revisa los datos obligatorios de la cuenta del alumno.", 400
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("consultar para editar")

    form = CuentaAlumnoEditarForm()
    if not form.is_submitted():
        form.correo.data = account["correo"]
        return _render_cuenta_alumno_form(
            form, "editar", cuenta=account
        )
    if not form.validate_on_submit():
        return _render_cuenta_alumno_form(
            form,
            "editar",
            cuenta=account,
            error_message=(
                "Revisa los datos obligatorios de la cuenta del alumno."
            ),
            status=400,
        )
    try:
        cuentas_alumno_service.editar_cuenta_alumno(
            usuario_id,
            form.correo.data,
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except DuplicateUserError:
        return _render_cuenta_alumno_form(
            form,
            "editar",
            cuenta=account,
            error_message="El correo ya está registrado.",
            status=409,
        )
    except (
        UsuarioNoEncontradoError,
        UsuarioNoEsAlumnoError,
        VinculoUsuarioAlumnoNoEncontradoError,
    ):
        return _cuenta_alumno_not_found()
    except AuthorizationError:
        return _cuenta_alumno_operation_error("Acceso no autorizado.", 403)
    except ValidationError:
        return _render_cuenta_alumno_form(
            form,
            "editar",
            cuenta=account,
            error_message=(
                "Revisa los datos obligatorios de la cuenta del alumno."
            ),
            status=400,
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("editar")

    flash("Cuenta de alumno actualizada correctamente.", "success")
    return redirect(url_for("admin.cuentas_alumnos_list"))


@admin_blueprint.route(
    "/cuentas-alumnos/<int:usuario_id>/password", methods=["GET", "POST"]
)
@role_required(ROL_ADMINISTRADOR)
def cuenta_alumno_password(usuario_id: int):
    try:
        account = cuentas_alumno_service.consultar_cuenta_alumno(
            usuario_id, current_app.config["DATABASE_PATH"]
        )
    except (
        UsuarioNoEncontradoError,
        UsuarioNoEsAlumnoError,
        VinculoUsuarioAlumnoNoEncontradoError,
    ):
        return _cuenta_alumno_not_found()
    except ValidationError:
        return _cuenta_alumno_operation_error(
            "Revisa los datos obligatorios de la cuenta del alumno.", 400
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("consultar contraseña")

    form = CuentaAlumnoPasswordForm()
    if not form.is_submitted():
        return _render_cuenta_alumno_password(form, account)
    if not form.validate_on_submit():
        return _render_cuenta_alumno_password(
            form,
            account,
            error_message=(
                "Revisa los datos obligatorios de la cuenta del alumno."
            ),
            status=400,
        )
    try:
        cuentas_alumno_service.restablecer_password_cuenta_alumno(
            usuario_id,
            form.password.data,
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except (
        UsuarioNoEncontradoError,
        UsuarioNoEsAlumnoError,
        VinculoUsuarioAlumnoNoEncontradoError,
    ):
        return _cuenta_alumno_not_found()
    except AuthorizationError:
        return _cuenta_alumno_operation_error("Acceso no autorizado.", 403)
    except ValidationError:
        return _render_cuenta_alumno_password(
            form,
            account,
            error_message=(
                "Revisa los datos obligatorios de la cuenta del alumno."
            ),
            status=400,
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("restablecer contraseña")

    flash(
        "Contraseña de la cuenta del alumno actualizada correctamente.",
        "success",
    )
    return redirect(url_for("admin.cuentas_alumnos_list"))


def _cambiar_estado_cuenta_alumno(
    usuario_id: int, operation, success_message: str
):
    form = EstadoUsuarioForm()
    if not form.validate_on_submit():
        return _cuenta_alumno_operation_error(
            "Revisa los datos obligatorios de la cuenta del alumno.", 400
        )
    try:
        operation(
            usuario_id,
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except AlumnoInactivoError:
        return _cuenta_alumno_operation_error(
            "No se puede activar una cuenta para un alumno inactivo.", 409
        )
    except (
        UsuarioNoEncontradoError,
        UsuarioNoEsAlumnoError,
        VinculoUsuarioAlumnoNoEncontradoError,
    ):
        return _cuenta_alumno_not_found()
    except AuthorizationError:
        return _cuenta_alumno_operation_error("Acceso no autorizado.", 403)
    except ValidationError:
        return _cuenta_alumno_operation_error(
            "Revisa los datos obligatorios de la cuenta del alumno.", 400
        )
    except RepositoryError:
        return _technical_cuenta_alumno_error("cambiar estado")

    flash(success_message, "success")
    return redirect(url_for("admin.cuentas_alumnos_list"))


@admin_blueprint.post("/cuentas-alumnos/<int:usuario_id>/activar")
@role_required(ROL_ADMINISTRADOR)
def cuenta_alumno_activar(usuario_id: int):
    return _cambiar_estado_cuenta_alumno(
        usuario_id,
        cuentas_alumno_service.activar_cuenta_alumno,
        "Cuenta de alumno activada correctamente.",
    )


@admin_blueprint.post("/cuentas-alumnos/<int:usuario_id>/desactivar")
@role_required(ROL_ADMINISTRADOR)
def cuenta_alumno_desactivar(usuario_id: int):
    return _cambiar_estado_cuenta_alumno(
        usuario_id,
        cuentas_alumno_service.desactivar_cuenta_alumno,
        "Cuenta de alumno desactivada correctamente.",
    )

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

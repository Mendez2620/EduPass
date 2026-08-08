"""Portal web personal y de solo lectura para alumnos."""

from __future__ import annotations

import base64

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
from flask_login import current_user

from edupass.modules.alumnos import alumno_portal_service
from edupass.modules.auth import usuarios_service
from edupass.modules.credencial_qr.qr_renderer import generar_qr_svg
from edupass.shared.constants import ROL_ALUMNO
from edupass.shared.errors import (
    EduPassError,
    AuthenticationError,
    AuthorizationError,
    MovimientoNoEncontradoError,
    RepositoryError,
    ValidationError,
)
from edupass.web.forms import (
    AlumnoGenerarCredencialForm,
    AlumnoRenovarCredencialForm,
    CambioPasswordObligatorioForm,
    NotificacionLeerForm,
    NotificacionesLeerTodasForm,
)
from edupass.web.security import role_required


alumno_blueprint = Blueprint("alumno", __name__, url_prefix="/alumno")
_SECURITY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Referrer-Policy": "no-referrer",
}
_CREDENTIAL_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; "
    "script-src 'self'; base-uri 'none'; frame-ancestors 'none'"
)
_CREDENTIAL_ENDPOINTS = {
    "alumno.credencial",
    "alumno.generar_credencial",
    "alumno.renovar_credencial",
}


@alumno_blueprint.before_request
def _require_completed_password_change():
    if (
        current_user.is_authenticated
        and current_user.rol_nombre == ROL_ALUMNO
        and current_user.requiere_cambio_password == 1
        and request.endpoint != "alumno.cambio_password_obligatorio"
    ):
        return redirect(url_for("alumno.cambio_password_obligatorio"))


@alumno_blueprint.route("/cambiar-password", methods=["GET", "POST"])
@role_required(ROL_ALUMNO)
def cambio_password_obligatorio():
    if current_user.requiere_cambio_password != 1:
        return redirect(url_for("alumno.dashboard"))
    form = CambioPasswordObligatorioForm()
    error_message = None
    status = 200
    if form.is_submitted():
        if not form.validate_on_submit():
            error_message = "Revisa los datos de la contraseña."
            status = 400
        else:
            try:
                usuarios_service.cambiar_password_obligatorio_alumno(
                    current_user.usuario_id,
                    form.password_actual.data,
                    form.password_nuevo.data,
                    current_app.config["DATABASE_PATH"],
                )
            except AuthenticationError:
                error_message = "La contraseña temporal no es correcta."
                status = 400
            except ValidationError as exc:
                error_message = str(exc)
                status = 400
            except AuthorizationError:
                return redirect(url_for("alumno.dashboard"))
            except RepositoryError:
                return _technical_error(
                    "alumno/cambio_password_obligatorio.html",
                    form=form,
                    title="Cambiar contraseña",
                )
            else:
                return redirect(url_for("alumno.dashboard"))
    return (
        render_template(
            "alumno/cambio_password_obligatorio.html",
            form=form,
            error_message=error_message,
            title="Cambiar contraseña",
        ),
        status,
    )


@alumno_blueprint.after_request
def _secure_portal_response(response):
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    if request.endpoint in _CREDENTIAL_ENDPOINTS:
        response.headers["Content-Security-Policy"] = _CREDENTIAL_CSP
    return response


def _svg_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _technical_error(template_name: str, **context):
    current_app.logger.warning(
        "No fue posible completar una operacion del portal del alumno."
    )
    return (
        render_template(
            template_name,
            error_message=(
                "No fue posible completar la operación en este momento."
            ),
            **context,
        ),
        500,
    )


def _render_credencial(
    perfil,
    *,
    credencial=None,
    error_message: str | None = None,
    status: int = 200,
):
    qr_data_uri = None
    safe_credential = None
    if credencial is not None:
        qr_data_uri = _svg_data_uri(generar_qr_svg(credencial["token"]))
        safe_credential = {
            key: value
            for key, value in credencial.items()
            if key != "token"
        }
    return (
        render_template(
            "alumno/credencial.html",
            perfil=perfil,
            credencial=safe_credential,
            qr_data_uri=qr_data_uri,
            generar_form=AlumnoGenerarCredencialForm(),
            renovar_form=AlumnoRenovarCredencialForm(),
            error_message=error_message,
            title="Mi credencial",
        ),
        status,
    )


@alumno_blueprint.get("")
@role_required(ROL_ALUMNO)
def dashboard():
    try:
        perfil = alumno_portal_service.obtener_perfil_propio(
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return _technical_error(
            "alumno/dashboard.html", perfil=None, title="Mi panel"
        )
    except EduPassError:
        return (
            render_template(
                "alumno/dashboard.html",
                perfil=None,
                error_message="No se encontró el perfil solicitado.",
                title="Mi panel",
            ),
            404,
        )
    return render_template(
        "alumno/dashboard.html",
        perfil=perfil,
        error_message=None,
        title="Mi panel",
    )


@alumno_blueprint.get("/credencial")
@role_required(ROL_ALUMNO)
def credencial():
    try:
        perfil = alumno_portal_service.obtener_perfil_propio(
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return _technical_error(
            "alumno/credencial.html",
            perfil=None,
            credencial=None,
            qr_data_uri=None,
            generar_form=AlumnoGenerarCredencialForm(),
            renovar_form=AlumnoRenovarCredencialForm(),
            title="Mi credencial",
        )
    except EduPassError:
        return _render_credencial(
            None,
            error_message="No se encontró el perfil solicitado.",
            status=404,
        )
    return _render_credencial(perfil)


def _handle_credential_generation(operation):
    form = (
        AlumnoGenerarCredencialForm()
        if operation is alumno_portal_service.generar_credencial_propia
        else AlumnoRenovarCredencialForm()
    )
    try:
        perfil = alumno_portal_service.obtener_perfil_propio(
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return _technical_error(
            "alumno/credencial.html",
            perfil=None,
            credencial=None,
            qr_data_uri=None,
            generar_form=AlumnoGenerarCredencialForm(),
            renovar_form=AlumnoRenovarCredencialForm(),
            title="Mi credencial",
        )
    except EduPassError:
        return _render_credencial(
            None,
            error_message="No se encontró el perfil solicitado.",
            status=404,
        )
    if not form.validate_on_submit():
        return _render_credencial(
            perfil,
            error_message="No fue posible validar la solicitud.",
            status=400,
        )
    try:
        generated = operation(
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return _technical_error(
            "alumno/credencial.html",
            perfil=perfil,
            credencial=None,
            qr_data_uri=None,
            generar_form=AlumnoGenerarCredencialForm(),
            renovar_form=AlumnoRenovarCredencialForm(),
            title="Mi credencial",
        )
    except EduPassError:
        return _render_credencial(
            perfil,
            error_message="No se encontró el perfil solicitado.",
            status=404,
        )
    return _render_credencial(perfil, credencial=generated)


@alumno_blueprint.post("/credencial/generar")
@role_required(ROL_ALUMNO)
def generar_credencial():
    return _handle_credential_generation(
        alumno_portal_service.generar_credencial_propia
    )


@alumno_blueprint.post("/credencial/renovar")
@role_required(ROL_ALUMNO)
def renovar_credencial():
    return _handle_credential_generation(
        alumno_portal_service.renovar_credencial_propia
    )


@alumno_blueprint.get("/historial")
@role_required(ROL_ALUMNO)
def historial():
    raw_page = request.args.get("page", "1")
    try:
        page = int(raw_page)
        if page <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return (
            render_template(
                "alumno/historial.html",
                historial=None,
                error_message="La página solicitada no es válida.",
                title="Mi historial",
            ),
            400,
        )
    try:
        result = alumno_portal_service.consultar_historial_propio(
            current_user.usuario_id,
            page,
            current_app.config["DATABASE_PATH"],
        )
    except ValidationError:
        return (
            render_template(
                "alumno/historial.html",
                historial=None,
                error_message="La página solicitada no es válida.",
                title="Mi historial",
            ),
            400,
        )
    except MovimientoNoEncontradoError:
        return (
            render_template(
                "alumno/historial.html",
                historial=None,
                error_message="No se encontró el historial solicitado.",
                title="Mi historial",
            ),
            404,
        )
    except RepositoryError:
        return _technical_error(
            "alumno/historial.html",
            historial=None,
            title="Mi historial",
        )
    except EduPassError:
        return (
            render_template(
                "alumno/historial.html",
                historial=None,
                error_message="No se encontró el historial solicitado.",
                title="Mi historial",
            ),
            404,
        )
    return render_template(
        "alumno/historial.html",
        historial=result,
        error_message=None,
        title="Mi historial",
    )


@alumno_blueprint.get("/historial/movimientos/<int:movimiento_id>")
@role_required(ROL_ALUMNO)
def movimiento_detalle(movimiento_id: int):
    try:
        movement = alumno_portal_service.consultar_movimiento_propio(
            current_user.usuario_id,
            movimiento_id,
            current_app.config["DATABASE_PATH"],
        )
    except MovimientoNoEncontradoError:
        return (
            render_template(
                "alumno/movimiento_detalle.html",
                movimiento=None,
                error_message="No se encontró el movimiento solicitado.",
                title="Detalle de movimiento",
            ),
            404,
        )
    except RepositoryError:
        return _technical_error(
            "alumno/movimiento_detalle.html",
            movimiento=None,
            title="Detalle de movimiento",
        )
    except EduPassError:
        return (
            render_template(
                "alumno/movimiento_detalle.html",
                movimiento=None,
                error_message="No se encontró el movimiento solicitado.",
                title="Detalle de movimiento",
            ),
            404,
        )
    return render_template(
        "alumno/movimiento_detalle.html",
        movimiento=movement,
        error_message=None,
        title="Detalle de movimiento",
    )


@alumno_blueprint.get("/notificaciones")
@role_required(ROL_ALUMNO)
def notificaciones():
    try:
        result = alumno_portal_service.consultar_notificaciones_propias(
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return _technical_error(
            "alumno/notificaciones.html",
            resultado=None,
            leer_form=NotificacionLeerForm(),
            todas_form=NotificacionesLeerTodasForm(),
            title="Notificaciones",
        )
    except EduPassError:
        return (
            render_template(
                "alumno/notificaciones.html",
                resultado=None,
                leer_form=NotificacionLeerForm(),
                todas_form=NotificacionesLeerTodasForm(),
                error_message="No se encontraron las notificaciones solicitadas.",
                title="Notificaciones",
            ),
            404,
        )
    return render_template(
        "alumno/notificaciones.html",
        resultado=result,
        leer_form=NotificacionLeerForm(),
        todas_form=NotificacionesLeerTodasForm(),
        error_message=None,
        title="Notificaciones",
    )


@alumno_blueprint.post("/notificaciones/<int:notificacion_id>/leer")
@role_required(ROL_ALUMNO)
def marcar_notificacion_leida(notificacion_id: int):
    form = NotificacionLeerForm()
    if not form.validate_on_submit():
        return "Solicitud inválida.", 400
    try:
        updated = alumno_portal_service.marcar_notificacion_propia_leida(
            current_user.usuario_id,
            notificacion_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return "No fue posible actualizar la notificación.", 500
    except EduPassError:
        return "Notificación no encontrada.", 404
    if not updated:
        return "Notificación no encontrada.", 404
    flash("Notificación marcada como leída.", "success")
    return redirect(url_for("alumno.notificaciones"))


@alumno_blueprint.post("/notificaciones/marcar-todas-leidas")
@role_required(ROL_ALUMNO)
def marcar_todas_notificaciones_leidas():
    form = NotificacionesLeerTodasForm()
    if not form.validate_on_submit():
        return "Solicitud inválida.", 400
    try:
        alumno_portal_service.marcar_notificaciones_propias_leidas(
            current_user.usuario_id,
            current_app.config["DATABASE_PATH"],
        )
    except RepositoryError:
        return "No fue posible actualizar las notificaciones.", 500
    except EduPassError:
        return "Notificaciones no encontradas.", 404
    flash("Todas las notificaciones fueron marcadas como leídas.", "success")
    return redirect(url_for("alumno.notificaciones"))

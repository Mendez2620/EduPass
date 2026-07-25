"""Rutas administrativas de solo lectura."""

from flask import Blueprint, current_app, render_template

from edupass.modules.alumnos import alumnos_service
from edupass.shared.constants import ROL_ADMINISTRADOR
from edupass.shared.errors import RepositoryError
from edupass.web.security import role_required


admin_blueprint = Blueprint("admin", __name__, url_prefix="/admin")


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
        title="Alumnos",
    )

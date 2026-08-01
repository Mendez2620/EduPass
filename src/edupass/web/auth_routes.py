"""Rutas de autenticacion de la interfaz web."""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from edupass.modules.auth import usuarios_service
from edupass.shared.constants import (
    ROL_ADMINISTRADOR,
    ROL_ALUMNO,
    ROL_ESCANER,
)
from edupass.shared.errors import AuthenticationError, RepositoryError
from edupass.web.forms import LoginForm, LogoutForm
from edupass.web.security import SessionUser


auth_blueprint = Blueprint("auth", __name__)


def _dashboard_endpoint(role_name: str) -> str | None:
    if role_name == ROL_ADMINISTRADOR:
        return "admin.dashboard"
    if role_name == ROL_ESCANER:
        return "scanner.dashboard"
    if role_name == ROL_ALUMNO:
        return "alumno.dashboard"
    return None


def _redirect_authenticated_user():
    endpoint = _dashboard_endpoint(current_user.rol_nombre)
    if endpoint is not None:
        return redirect(url_for(endpoint))

    logout_user()
    session.clear()
    flash("La sesion no tiene un rol autorizado.", "error")
    return redirect(url_for("auth.login"))


@auth_blueprint.get("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return _redirect_authenticated_user()


@auth_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_authenticated_user()

    form = LoginForm()
    if form.validate_on_submit():
        try:
            data = usuarios_service.autenticar_usuario(
                form.correo.data,
                form.password.data,
                current_app.config["DATABASE_PATH"],
            )
            user = SessionUser.from_service_data(data)
        except (AuthenticationError, RepositoryError, KeyError, TypeError):
            flash(
                "No fue posible iniciar sesion con las credenciales "
                "proporcionadas.",
                "error",
            )
        else:
            login_user(user)
            session.permanent = True
            endpoint = _dashboard_endpoint(user.rol_nombre)
            if endpoint is None:
                logout_user()
                session.clear()
                flash("La sesion no tiene un rol autorizado.", "error")
                return redirect(url_for("auth.login"))
            flash("Sesion iniciada correctamente.", "success")
            return redirect(url_for(endpoint))

    return render_template("auth/login.html", form=form, title="Iniciar sesion")


@auth_blueprint.post("/logout")
@login_required
def logout():
    form = LogoutForm()
    if form.validate_on_submit():
        logout_user()
        session.clear()
        flash("Sesion cerrada correctamente.", "success")
        return redirect(url_for("auth.login"))
    return redirect(url_for("auth.index"))

"""Fabrica de la aplicacion web de EduPass."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from flask import Flask, render_template
from flask_login import current_user

from edupass.persistence import database_manager
from edupass.web.admin_routes import admin_blueprint
from edupass.web.auth_routes import auth_blueprint
from edupass.web.extensions import csrf, login_manager
from edupass.web.forms import LogoutForm
from edupass.web.scanner_routes import scanner_blueprint
from edupass.web.security import load_user


def _session_lifetime() -> timedelta:
    raw_value = os.getenv("EDUPASS_SESSION_MINUTES", "30")
    try:
        minutes = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            "EDUPASS_SESSION_MINUTES debe ser un entero positivo."
        ) from exc
    if minutes <= 0:
        raise RuntimeError(
            "EDUPASS_SESSION_MINUTES debe ser un entero positivo."
        )
    return timedelta(minutes=minutes)


def _database_path() -> Path:
    configured_path = os.getenv("EDUPASS_DATABASE_PATH")
    if configured_path:
        return Path(configured_path).expanduser()
    return database_manager.get_database_path()


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Crea e inicializa una instancia configurable de EduPass web."""
    testing = bool(test_config and test_config.get("TESTING"))
    secret_key = os.getenv("EDUPASS_SECRET_KEY")
    if not testing and not secret_key:
        raise RuntimeError(
            "EDUPASS_SECRET_KEY es obligatoria para ejecutar la aplicacion."
        )

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        DATABASE_PATH=_database_path(),
        PERMANENT_SESSION_LIFETIME=_session_lifetime(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=False,
        WTF_CSRF_ENABLED=True,
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY debe configurarse para crear la aplicacion."
        )
    app.config["DATABASE_PATH"] = Path(app.config["DATABASE_PATH"])

    database_manager.initialize_database(app.config["DATABASE_PATH"])

    login_manager.login_view = "auth.login"
    login_manager.login_message = (
        "Debes iniciar sesion para acceder a esta pagina."
    )
    login_manager.login_message_category = "warning"
    login_manager.user_loader(load_user)
    login_manager.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(scanner_blueprint)

    @app.context_processor
    def provide_logout_form() -> dict[str, LogoutForm | None]:
        return {
            "logout_form": LogoutForm()
            if current_user.is_authenticated
            else None
        }

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html", title="Acceso denegado"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "errors/404.html",
            title="Recurso no encontrado",
        ), 404

    return app


__all__ = ["create_app"]

"""Punto de entrada para ejecutar EduPass web."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from edupass.persistence.database_manager import DatabaseManagerError
from edupass.web import create_app


def _port_from_environment() -> int:
    raw_port = os.getenv("EDUPASS_PORT", "5000")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("EDUPASS_PORT debe ser un entero valido.") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("EDUPASS_PORT debe estar entre 1 y 65535.")
    return port


def _host_from_environment(mode: str) -> str:
    host = os.getenv("EDUPASS_HOST", "127.0.0.1").strip()
    if not host:
        raise RuntimeError("EDUPASS_HOST no puede estar vacio.")
    if mode == "proxy" and host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError(
            "El modo proxy requiere EDUPASS_HOST=127.0.0.1 o localhost."
        )
    return host


def _required_file(variable_name: str) -> Path:
    raw_path = os.getenv(variable_name)
    if not raw_path:
        raise RuntimeError(f"{variable_name} es obligatoria en modo direct.")
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise RuntimeError(
            f"{variable_name} debe apuntar a un archivo existente."
        )
    return path


def _ssl_context_from_environment(mode: str):
    if mode != "direct":
        return None
    certificate = _required_file("EDUPASS_SSL_CERT")
    private_key = _required_file("EDUPASS_SSL_KEY")
    return str(certificate), str(private_key)


def main() -> int:
    try:
        app = create_app()
        mode = app.config["HTTPS_MODE"]
        host = _host_from_environment(mode)
        port = _port_from_environment()
        ssl_context = _ssl_context_from_environment(mode)
    except (DatabaseManagerError, FileNotFoundError, RuntimeError) as exc:
        print(f"[EduPass web] Error de configuracion: {exc}", file=sys.stderr)
        return 1

    scheme = "https" if mode in {"proxy", "direct"} else "http"
    print(
        f"[EduPass web] modo={mode} host={host} puerto={port} "
        f"esquema_esperado={scheme}"
    )
    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        ssl_context=ssl_context,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
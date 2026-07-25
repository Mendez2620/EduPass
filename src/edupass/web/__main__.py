"""Punto de entrada para ejecutar EduPass web."""

import os
import sys

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


def main() -> int:
    try:
        app = create_app()
        port = _port_from_environment()
    except (DatabaseManagerError, FileNotFoundError, RuntimeError) as exc:
        print(f"[EduPass web] Error de configuracion: {exc}", file=sys.stderr)
        return 1

    app.run(
        host=os.getenv("EDUPASS_HOST", "127.0.0.1"),
        port=port,
        debug=False,
        use_reloader=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

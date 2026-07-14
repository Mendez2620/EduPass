"""Punto de entrada de la aplicación gráfica EduPass."""

from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

from edupass.persistence import database_manager
from edupass.ui.alumnos_window import AlumnosWindow


def _show_startup_error(title: str, message: str) -> None:
    app = QApplication.instance()
    if isinstance(app, QApplication):
        try:
            QMessageBox.critical(None, title, message)
            return
        except Exception:
            traceback.print_exc(file=sys.stderr)
    print(f"{title}: {message}", file=sys.stderr)


def _handle_unexpected_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    traceback.print_exception(
        exc_type,
        exc_value,
        exc_traceback,
        file=sys.stderr,
    )

    app = QApplication.instance()
    if isinstance(app, QApplication):
        try:
            QMessageBox.critical(
                None,
                "Error inesperado",
                "Ocurrió un error inesperado. La operación no pudo completarse.",
            )
        except Exception:
            traceback.print_exc(file=sys.stderr)


def main() -> int:
    """Inicializa y ejecuta la aplicación gráfica EduPass."""
    previous_excepthook = sys.excepthook

    try:
        existing_app = QApplication.instance()
        if existing_app is None:
            app = QApplication(sys.argv)
        elif isinstance(existing_app, QApplication):
            app = existing_app
        else:
            raise RuntimeError(
                "Existe una instancia de Qt incompatible con QApplication."
            )

        app.setApplicationName("EduPass")
        app.setApplicationDisplayName("EduPass")
        sys.excepthook = _handle_unexpected_exception

        database_path = database_manager.initialize_database()
        controller = AlumnosWindow(database_path)
        controller.show()
        return app.exec()
    except database_manager.DatabaseManagerError:
        traceback.print_exc(file=sys.stderr)
        _show_startup_error(
            "Error de base de datos",
            "No fue posible inicializar la base de datos de EduPass.",
        )
        return 1
    except RuntimeError:
        traceback.print_exc(file=sys.stderr)
        _show_startup_error(
            "Error de interfaz",
            "No fue posible cargar la interfaz de EduPass.",
        )
        return 1
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _show_startup_error(
            "Error inesperado",
            "EduPass no pudo iniciarse correctamente.",
        )
        return 1
    finally:
        sys.excepthook = previous_excepthook


if __name__ == "__main__":
    raise SystemExit(main())

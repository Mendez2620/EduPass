"""Controlador de la ventana de administración de alumnos."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QWidget,
)

from edupass.modules.alumnos import alumnos_service
from edupass.shared.constants import (
    ESTADO_ALUMNO_ACTIVO,
    ESTADO_ALUMNO_INACTIVO,
)
from edupass.shared.errors import (
    AlumnoNoEncontradoError,
    ConsultaSqlError,
    EduPassError,
    MatriculaDuplicadaError,
    RepositoryError,
    ValidationError,
)


WidgetType = TypeVar("WidgetType", bound=QWidget)


class AlumnosWindow:
    """Controla la ventana Qt y delega las operaciones al servicio."""

    def __init__(self, database_path: Any) -> None:
        if QApplication.instance() is None:
            raise RuntimeError(
                "Debe existir una QApplication antes de crear AlumnosWindow."
            )

        self._database_path = database_path
        self._window = self._load_ui()
        self._alumno_id: int | None = None
        self._bind_widgets()
        self._connect_signals()
        self._apply_initial_state()

    @property
    def window(self) -> QMainWindow:
        """Devuelve la ventana principal cargada desde Qt Designer."""
        return self._window

    @property
    def alumno_id_seleccionado(self) -> int | None:
        """Devuelve el identificador del alumno seleccionado."""
        return self._alumno_id

    def show(self) -> None:
        """Muestra la ventana de administración de alumnos."""
        self._window.show()

    def close(self) -> None:
        """Cierra la ventana de administración de alumnos."""
        self._window.close()

    def _load_ui(self) -> QMainWindow:
        ui_path = Path(__file__).resolve().with_name("alumnos_window.ui")
        if not ui_path.is_file():
            raise RuntimeError("No se encontró el archivo visual de alumnos.")

        ui_file = QFile(str(ui_path))
        if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError("No se pudo abrir el archivo visual de alumnos.")

        loader = QUiLoader()
        try:
            window = loader.load(ui_file)
        finally:
            ui_file.close()

        if window is None:
            detail = loader.errorString() or "error desconocido"
            raise RuntimeError(
                f"No se pudo cargar la interfaz de alumnos: {detail}"
            )
        if not isinstance(window, QMainWindow):
            window.close()
            raise RuntimeError("La interfaz de alumnos no contiene un QMainWindow.")
        return window

    def _require_widget(
        self,
        widget_type: type[WidgetType],
        object_name: str,
    ) -> WidgetType:
        widget = self._window.findChild(widget_type, object_name)
        if widget is None:
            raise RuntimeError(
                f"Falta el widget obligatorio '{object_name}' o su tipo es incorrecto."
            )
        return widget

    def _bind_widgets(self) -> None:
        self.labelTitulo = self._require_widget(QLabel, "labelTitulo")
        self.labelDescripcion = self._require_widget(QLabel, "labelDescripcion")
        self.labelAlumnoId = self._require_widget(QLabel, "labelAlumnoId")
        self.labelEstadoActual = self._require_widget(QLabel, "labelEstadoActual")
        self.labelEstadoOperacion = self._require_widget(
            QLabel,
            "labelEstadoOperacion",
        )
        self.lineEditNombre = self._require_widget(QLineEdit, "lineEditNombre")
        self.lineEditMatricula = self._require_widget(
            QLineEdit,
            "lineEditMatricula",
        )
        self.lineEditGrado = self._require_widget(QLineEdit, "lineEditGrado")
        self.lineEditGrupo = self._require_widget(QLineEdit, "lineEditGrupo")
        self.lineEditFotografia = self._require_widget(
            QLineEdit,
            "lineEditFotografia",
        )
        self.comboBoxEstado = self._require_widget(QComboBox, "comboBoxEstado")
        self.pushButtonRegistrar = self._require_widget(
            QPushButton,
            "pushButtonRegistrar",
        )
        self.pushButtonBuscar = self._require_widget(
            QPushButton,
            "pushButtonBuscar",
        )
        self.pushButtonEditar = self._require_widget(
            QPushButton,
            "pushButtonEditar",
        )
        self.pushButtonActivar = self._require_widget(
            QPushButton,
            "pushButtonActivar",
        )
        self.pushButtonDesactivar = self._require_widget(
            QPushButton,
            "pushButtonDesactivar",
        )
        self.pushButtonLimpiar = self._require_widget(
            QPushButton,
            "pushButtonLimpiar",
        )

    def _connect_signals(self) -> None:
        self.pushButtonRegistrar.clicked.connect(self._register_alumno)
        self.pushButtonBuscar.clicked.connect(self._search_alumno)
        self.pushButtonEditar.clicked.connect(self._edit_alumno)
        self.pushButtonActivar.clicked.connect(self._activate_alumno)
        self.pushButtonDesactivar.clicked.connect(self._deactivate_alumno)
        self.pushButtonLimpiar.clicked.connect(self._clear_form)

    def _apply_initial_state(self) -> None:
        self._clear_selection(preserve_fields=False)
        self.labelEstadoOperacion.setText(
            "Listo para registrar o buscar un alumno."
        )
        self.lineEditNombre.setFocus()

    def _clear_selection(self, preserve_fields: bool = False) -> None:
        self._alumno_id = None
        self.labelAlumnoId.setText("Ninguno")
        self.labelEstadoActual.setText("Sin alumno seleccionado")
        self.pushButtonRegistrar.setEnabled(True)
        self.pushButtonBuscar.setEnabled(True)
        self.pushButtonEditar.setEnabled(False)
        self.pushButtonActivar.setEnabled(False)
        self.pushButtonDesactivar.setEnabled(False)
        self.pushButtonLimpiar.setEnabled(True)
        self.comboBoxEstado.setEnabled(True)

        if not preserve_fields:
            self.lineEditNombre.clear()
            self.lineEditMatricula.clear()
            self.lineEditGrado.clear()
            self.lineEditGrupo.clear()
            self.lineEditFotografia.clear()
            active_index = self.comboBoxEstado.findText(ESTADO_ALUMNO_ACTIVO)
            if active_index < 0:
                raise RuntimeError(
                    "La interfaz no contiene el estado activo requerido."
                )
            self.comboBoxEstado.setCurrentIndex(active_index)

    def _collect_form_data(self) -> dict[str, str]:
        return {
            "nombre": self.lineEditNombre.text(),
            "matricula": self.lineEditMatricula.text(),
            "grado": self.lineEditGrado.text(),
            "grupo": self.lineEditGrupo.text(),
            "fotografia": self.lineEditFotografia.text(),
            "estado": self.comboBoxEstado.currentText(),
        }

    def _set_selected_alumno(self, alumno: dict[str, Any]) -> None:
        required_fields = {
            "alumno_id",
            "nombre",
            "matricula",
            "grado",
            "grupo",
            "fotografia",
            "estado",
        }
        missing_fields = required_fields - alumno.keys()
        if missing_fields:
            raise RuntimeError(
                "El servicio devolvió datos incompletos para mostrar el alumno."
            )

        state = alumno["estado"]
        state_index = self.comboBoxEstado.findText(state)
        if state_index < 0:
            raise RuntimeError(
                "El estado del alumno no existe en la interfaz."
            )

        self._alumno_id = alumno["alumno_id"]
        self.labelAlumnoId.setText(str(self._alumno_id))
        self.labelEstadoActual.setText(state)
        self.lineEditNombre.setText(alumno["nombre"])
        self.lineEditMatricula.setText(alumno["matricula"])
        self.lineEditGrado.setText(alumno["grado"])
        self.lineEditGrupo.setText(alumno["grupo"])
        self.lineEditFotografia.setText(alumno["fotografia"] or "")
        self.comboBoxEstado.setCurrentIndex(state_index)
        self.comboBoxEstado.setEnabled(False)
        self.pushButtonRegistrar.setEnabled(False)
        self.pushButtonBuscar.setEnabled(True)
        self.pushButtonEditar.setEnabled(True)
        self.pushButtonLimpiar.setEnabled(True)
        self._update_action_buttons(state)

    def _update_action_buttons(self, state: str) -> None:
        if state == ESTADO_ALUMNO_ACTIVO:
            self.pushButtonActivar.setEnabled(False)
            self.pushButtonDesactivar.setEnabled(True)
            return
        if state == ESTADO_ALUMNO_INACTIVO:
            self.pushButtonActivar.setEnabled(True)
            self.pushButtonDesactivar.setEnabled(False)
            return
        raise RuntimeError("El estado del alumno no es compatible con la interfaz.")

    def _show_success(self, message: str) -> None:
        self.labelEstadoOperacion.setText(message)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self._window, title, message)

    def _show_critical(self, title: str, message: str) -> None:
        QMessageBox.critical(self._window, title, message)

    def _handle_domain_error(self, error: EduPassError, operation: str) -> None:
        if isinstance(error, MatriculaDuplicadaError):
            self._show_warning("Matrícula duplicada", str(error))
            if operation == "registrar":
                self.labelEstadoOperacion.setText(
                    "No se pudo registrar: matrícula duplicada."
                )
            else:
                self.labelEstadoOperacion.setText(
                    "No se pudo actualizar: matrícula duplicada."
                )
            return

        if isinstance(error, ValidationError):
            self._show_warning("Datos inválidos", str(error))
            self.labelEstadoOperacion.setText("Revisa los datos capturados.")
            return

        if isinstance(error, AlumnoNoEncontradoError):
            self._show_warning("Alumno no encontrado", str(error))
            if operation == "buscar":
                self.labelEstadoOperacion.setText(
                    "No se encontró un alumno con esa matrícula."
                )
            else:
                self._clear_selection(preserve_fields=True)
                self.labelEstadoOperacion.setText(
                    "El alumno seleccionado ya no está disponible."
                )
            return

        if isinstance(error, ConsultaSqlError):
            self._show_critical(
                "Error de persistencia",
                "No fue posible completar la operación de datos.",
            )
            self.labelEstadoOperacion.setText(
                "Ocurrió un error al acceder a los datos."
            )
            return

        if isinstance(error, RepositoryError):
            self._show_critical(
                "Error de persistencia",
                "No fue posible completar la operación de datos.",
            )
            self.labelEstadoOperacion.setText(
                "Ocurrió un error al acceder a los datos."
            )
            return

        self._show_critical(
            "Error de EduPass",
            "No fue posible completar la operación solicitada.",
        )
        self.labelEstadoOperacion.setText("Ocurrió un error de EduPass.")

    def _require_selection(self) -> int | None:
        if self._alumno_id is None:
            self._show_warning(
                "Sin alumno seleccionado",
                "Primero registra o busca un alumno.",
            )
            self.labelEstadoOperacion.setText(
                "Selecciona un alumno antes de continuar."
            )
            return None
        return self._alumno_id

    def _register_alumno(self, checked: bool = False) -> None:
        del checked
        data = self._collect_form_data()
        try:
            alumno = alumnos_service.registrar_alumno(
                nombre=data["nombre"],
                matricula=data["matricula"],
                grado=data["grado"],
                grupo=data["grupo"],
                fotografia=data["fotografia"],
                estado=data["estado"],
                database_path=self._database_path,
            )
        except EduPassError as error:
            self._handle_domain_error(error, "registrar")
            return

        self._set_selected_alumno(alumno)
        self._show_success("Alumno registrado correctamente.")

    def _search_alumno(self, checked: bool = False) -> None:
        del checked
        matricula = self.lineEditMatricula.text()
        self._clear_selection(preserve_fields=True)
        try:
            alumno = alumnos_service.consultar_alumno_por_matricula(
                matricula,
                database_path=self._database_path,
            )
        except EduPassError as error:
            self._handle_domain_error(error, "buscar")
            return

        self._set_selected_alumno(alumno)
        self._show_success("Alumno encontrado correctamente.")

    def _edit_alumno(self, checked: bool = False) -> None:
        del checked
        alumno_id = self._require_selection()
        if alumno_id is None:
            return

        data = self._collect_form_data()
        try:
            alumno = alumnos_service.editar_alumno(
                alumno_id=alumno_id,
                nombre=data["nombre"],
                matricula=data["matricula"],
                grado=data["grado"],
                grupo=data["grupo"],
                fotografia=data["fotografia"],
                database_path=self._database_path,
            )
        except EduPassError as error:
            self._handle_domain_error(error, "editar")
            return

        self._set_selected_alumno(alumno)
        self._show_success("Alumno actualizado correctamente.")

    def _activate_alumno(self, checked: bool = False) -> None:
        del checked
        alumno_id = self._require_selection()
        if alumno_id is None:
            return

        try:
            alumno = alumnos_service.activar_alumno(
                alumno_id,
                database_path=self._database_path,
            )
        except EduPassError as error:
            self._handle_domain_error(error, "activar")
            return

        self._set_selected_alumno(alumno)
        self._show_success("Alumno activado correctamente.")

    def _deactivate_alumno(self, checked: bool = False) -> None:
        del checked
        alumno_id = self._require_selection()
        if alumno_id is None:
            return

        try:
            alumno = alumnos_service.desactivar_alumno(
                alumno_id,
                database_path=self._database_path,
            )
        except EduPassError as error:
            self._handle_domain_error(error, "desactivar")
            return

        self._set_selected_alumno(alumno)
        self._show_success("Alumno desactivado correctamente.")

    def _clear_form(self, checked: bool = False) -> None:
        del checked
        self._clear_selection(preserve_fields=False)
        self.labelEstadoOperacion.setText(
            "Formulario limpio. Listo para registrar o buscar."
        )
        self.lineEditNombre.setFocus()

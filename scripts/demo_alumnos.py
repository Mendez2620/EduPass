"""Demostracion manual del flujo del modulo de alumnos de EduPass."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from edupass.modules.alumnos.alumnos_service import (
    activar_alumno,
    consultar_alumno_por_id,
    consultar_alumno_por_matricula,
    desactivar_alumno,
    editar_alumno,
    registrar_alumno,
)
from edupass.persistence import database_manager
from edupass.shared.errors import EduPassError, MatriculaDuplicadaError


SEPARATOR = "=" * 60
ALUMNO_FIELDS = (
    "nombre",
    "matricula",
    "grado",
    "grupo",
    "fotografia",
    "estado",
)


def _mostrar_paso(numero: int, titulo: str) -> None:
    print(f"\nPASO {numero}. {titulo}")
    print("-" * 60)


def _mostrar_datos(titulo: str, datos: dict) -> None:
    print(titulo)
    for campo in ALUMNO_FIELDS:
        if campo in datos:
            print(f"  {campo}: {datos[campo]!r}")


def _mostrar_alumno(titulo: str, alumno: dict) -> None:
    print(titulo)
    print(f"  ID: {alumno['alumno_id']}")
    print(f"  Nombre: {alumno['nombre']}")
    print(f"  Matrícula: {alumno['matricula']}")
    print(f"  Grado: {alumno['grado']}")
    print(f"  Grupo: {alumno['grupo']}")
    print(f"  Fotografía: {alumno['fotografia']}")
    print(f"  Estado: {alumno['estado']}")


def _verificar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def _ejecutar_demostracion() -> None:
    print(SEPARATOR)
    print("EDUPASS - DEMOSTRACIÓN DEL MÓDULO DE ALUMNOS")
    print(SEPARATOR)
    print("Se utilizará una base SQLite temporal.")
    print("La base local data/edupass.sqlite no será modificada.")
    print("Se demostrará la integración completa del módulo de alumnos.")

    with TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "edupass_demo.sqlite"

        _mostrar_paso(1, "INICIALIZACIÓN")
        print(f"Base temporal: {database_path.name}")
        database_manager.initialize_database(database_path)
        print("[OK] Base de datos temporal inicializada.")

        datos_iniciales = {
            "nombre": "  Ana López García  ",
            "matricula": "  edu-001  ",
            "grado": "  3  ",
            "grupo": "  a  ",
            "fotografia": "  fotos/ana.png  ",
            "estado": "  ACTIVO  ",
        }

        _mostrar_paso(2, "REGISTRO Y NORMALIZACIÓN")
        _mostrar_datos("Datos originales enviados:", datos_iniciales)
        registrado = registrar_alumno(
            database_path=database_path,
            **datos_iniciales,
        )
        _mostrar_alumno("Resultado normalizado y almacenado:", registrado)
        _verificar(
            isinstance(registrado["alumno_id"], int)
            and registrado["alumno_id"] > 0,
            "El identificador creado no es válido.",
        )
        _verificar(
            registrado["matricula"] == "EDU-001",
            "La matrícula inicial no fue normalizada correctamente.",
        )

        _mostrar_paso(3, "CONSULTA POR ID")
        consultado_por_id = consultar_alumno_por_id(
            registrado["alumno_id"],
            database_path,
        )
        _mostrar_alumno("Alumno encontrado por ID:", consultado_por_id)
        _verificar(
            consultado_por_id == registrado,
            "La consulta por ID no devolvió el alumno registrado.",
        )

        _mostrar_paso(4, "CONSULTA POR MATRÍCULA NORMALIZADA")
        consultado_por_matricula = consultar_alumno_por_matricula(
            "  edu-001  ",
            database_path,
        )
        _mostrar_alumno(
            "Alumno encontrado mediante '  edu-001  ':",
            consultado_por_matricula,
        )
        _verificar(
            consultado_por_matricula["alumno_id"] == registrado["alumno_id"],
            "La consulta por matrícula devolvió otro alumno.",
        )

        _mostrar_paso(5, "RECHAZO DE MATRÍCULA DUPLICADA")
        duplicado_rechazado = False
        try:
            registrar_alumno(
                nombre="Alumno Duplicado",
                matricula="  edu-001  ",
                grado="4",
                grupo="B",
                fotografia=None,
                estado="activo",
                database_path=database_path,
            )
        except MatriculaDuplicadaError as exc:
            duplicado_rechazado = True
            print("[OK] Matrícula duplicada rechazada correctamente.")
            print(f"Motivo: {exc}")
        _verificar(
            duplicado_rechazado,
            "La matrícula duplicada no fue rechazada.",
        )

        datos_edicion = {
            "nombre": "  Ana López García Actualizada  ",
            "matricula": "  edu-002  ",
            "grado": "  4  ",
            "grupo": "  B  ",
            "fotografia": "  fotos/ana_actualizada.png  ",
        }

        _mostrar_paso(6, "EDICIÓN")
        _mostrar_datos("Valores solicitados:", datos_edicion)
        editado = editar_alumno(
            registrado["alumno_id"],
            database_path=database_path,
            **datos_edicion,
        )
        _mostrar_alumno("Alumno actualizado:", editado)
        _verificar(
            editado["matricula"] == "EDU-002",
            "La nueva matrícula no fue normalizada correctamente.",
        )
        _verificar(
            editado["estado"] == "activo",
            "La edición modificó el estado del alumno.",
        )
        print("[OK] El estado activo se conservó durante la edición.")

        _mostrar_paso(7, "DESACTIVACIÓN")
        desactivado = desactivar_alumno(
            registrado["alumno_id"],
            database_path,
        )
        _mostrar_alumno("Alumno desactivado:", desactivado)
        _verificar(
            desactivado["estado"] == "inactivo",
            "El alumno no quedó inactivo.",
        )
        for campo in ("nombre", "matricula", "grado", "grupo", "fotografia"):
            _verificar(
                desactivado[campo] == editado[campo],
                f"La desactivación modificó el campo {campo}.",
            )
        print("[OK] Los demás datos permanecieron sin cambios.")

        _mostrar_paso(8, "CONSULTA FINAL INACTIVA")
        final_inactivo = consultar_alumno_por_id(
            registrado["alumno_id"],
            database_path,
        )
        _mostrar_alumno("Estado persistido después de desactivar:", final_inactivo)
        _verificar(
            final_inactivo["estado"] == "inactivo",
            "La consulta posterior no conservó el estado inactivo.",
        )

        _mostrar_paso(9, "ACTIVACIÓN")
        activado = activar_alumno(
            registrado["alumno_id"],
            database_path,
        )
        _mostrar_alumno("Alumno reactivado:", activado)
        _verificar(
            activado["estado"] == "activo",
            "El alumno no quedó activo.",
        )

        _mostrar_paso(10, "CONSULTA POR NUEVA MATRÍCULA")
        consultado_final = consultar_alumno_por_matricula(
            "  edu-002  ",
            database_path,
        )
        _mostrar_alumno("Alumno encontrado mediante '  edu-002  ':", consultado_final)
        _verificar(
            consultado_final["alumno_id"] == registrado["alumno_id"],
            "La nueva matrícula no corresponde al alumno original.",
        )

        print(f"\n{SEPARATOR}")
        print("DEMOSTRACIÓN COMPLETADA CORRECTAMENTE")
        print(SEPARATOR)
        print("Operaciones verificadas:")
        print("- Base temporal inicializada.")
        print("- Alumno registrado.")
        print("- Datos normalizados.")
        print("- Consulta por ID.")
        print("- Consulta por matrícula.")
        print("- Matrícula duplicada rechazada.")
        print("- Alumno editado.")
        print("- Alumno desactivado.")
        print("- Estado inactivo persistido.")
        print("- Alumno reactivado.")
        print("- Integración completa confirmada.")
        print("La base temporal será eliminada automáticamente.")

    print("[OK] Base de datos temporal eliminada automáticamente.")


def main() -> int:
    """Ejecuta la demostración y devuelve un código de salida."""
    try:
        _ejecutar_demostracion()
    except EduPassError as exc:
        print("\n[ERROR] La demostración no pudo completarse.")
        print(f"Motivo: {exc}")
        return 1
    except RuntimeError as exc:
        print("\n[ERROR] La demostración detectó una inconsistencia.")
        print(f"Motivo: {exc}")
        return 1
    except Exception:
        print("\n[ERROR] Ocurrió un error inesperado durante la demostración.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

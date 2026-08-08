"""Persistencia minima de EduPass con SQLite.

Este modulo solo inicializa la base de datos local desde schema.sql y permite
verificar las tablas creadas. No contiene reglas de negocio ni CRUD funcional.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_NAME = "edupass.sqlite"

EXPECTED_TABLES = {
    "roles",
    "usuarios",
    "alumnos",
    "usuario_alumno",
    "tutores",
    "alumno_tutor",
    "areas_internas",
    "usuario_area_permiso",
    "dispositivos_fijos",
    "qr_tokens",
    "movimientos",
    "notificaciones_alumno",
    "notificaciones_push",
    "intentos_rechazados",
}


class DatabaseManagerError(Exception):
    """Error base para fallos de inicializacion o acceso a SQLite."""


def get_project_root(start_path: Path | None = None) -> Path:
    """Devuelve la raiz del proyecto EduPass."""
    current_path = (start_path or Path(__file__)).resolve()
    candidates = [current_path] if current_path.is_dir() else [current_path.parent]
    candidates.extend(candidates[0].parents)

    for candidate in candidates:
        if (candidate / "README.md").exists() and (candidate / "src").exists():
            return candidate

    raise DatabaseManagerError("No se pudo ubicar la raiz del proyecto EduPass.")


def get_database_path(project_root: Path | None = None) -> Path:
    """Devuelve la ruta esperada del archivo SQLite local."""
    root = project_root or get_project_root()
    return root / "data" / DATABASE_NAME


def get_schema_path() -> Path:
    """Devuelve la ruta del archivo schema.sql usado para crear tablas."""
    return Path(__file__).resolve().with_name("schema.sql")


def get_connection(database_path: Path | None = None) -> sqlite3.Connection:
    """Abre una conexion SQLite y activa llaves foraneas."""
    db_path = database_path or get_database_path()

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseManagerError(f"No se pudo crear la carpeta de datos: {db_path.parent}") from exc

    try:
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection
    except sqlite3.Error as exc:
        raise DatabaseManagerError(f"No se pudo abrir la base de datos SQLite: {db_path}") from exc


def initialize_database(
    database_path: Path | None = None,
    schema_path: Path | None = None,
) -> Path:
    """Ejecuta schema.sql y crea las tablas minimas del MVP."""
    db_path = database_path or get_database_path()
    sql_path = schema_path or get_schema_path()

    if not sql_path.exists():
        raise FileNotFoundError(f"No se encontro el archivo de esquema: {sql_path}")

    try:
        schema_sql = sql_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatabaseManagerError(f"No se pudo leer el archivo de esquema: {sql_path}") from exc

    connection = None
    try:
        connection = get_connection(db_path)
        connection.executescript(schema_sql)
        user_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(usuarios);").fetchall()
        }
        if "requiere_cambio_password" not in user_columns:
            connection.execute(
                "ALTER TABLE usuarios ADD COLUMN "
                "requiere_cambio_password INTEGER NOT NULL DEFAULT 0;"
            )
        connection.commit()
    except sqlite3.Error as exc:
        if connection is not None:
            connection.rollback()
        raise DatabaseManagerError("Ocurrio un error SQL al ejecutar schema.sql.") from exc
    finally:
        if connection is not None:
            connection.close()

    return db_path


def list_tables(database_path: Path | None = None) -> list[str]:
    """Lista las tablas creadas en la base SQLite."""
    db_path = database_path or get_database_path()
    connection = None

    try:
        connection = get_connection(db_path)
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise DatabaseManagerError("No se pudieron consultar las tablas creadas.") from exc
    finally:
        if connection is not None:
            connection.close()

    return [row[0] for row in rows]


def verify_expected_tables(database_path: Path | None = None) -> tuple[bool, set[str]]:
    """Verifica que existan las tablas minimas esperadas."""
    created_tables = set(list_tables(database_path))
    missing_tables = EXPECTED_TABLES - created_tables
    return not missing_tables, missing_tables


def main() -> int:
    """Ejecuta una prueba manual simple de inicializacion."""
    try:
        database_path = initialize_database()
        tables = list_tables(database_path)
        is_ready, missing_tables = verify_expected_tables(database_path)
    except (DatabaseManagerError, FileNotFoundError) as exc:
        print(f"[EduPass] Error de persistencia: {exc}")
        return 1

    print(f"[EduPass] Base de datos lista: {database_path}")
    print("[EduPass] Tablas creadas:")
    for table_name in tables:
        print(f" - {table_name}")

    if not is_ready:
        print("[EduPass] Faltan tablas esperadas:")
        for table_name in sorted(missing_tables):
            print(f" - {table_name}")
        return 1

    print("[EduPass] Verificacion completada correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

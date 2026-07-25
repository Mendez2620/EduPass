from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager
from edupass.persistence.repositories import alumno_repository
from edupass.shared.errors import (
    ConsultaSqlError,
    MatriculaDuplicadaError,
    RepositoryError,
)


class TestAlumnoRepository(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "edupass_test.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _crear_alumno(self, **changes):
        data = {
            "nombre": "Ana López García",
            "matricula": "EDU-001",
            "grado": "3",
            "grupo": "A",
            "fotografia": None,
            "estado": "activo",
        }
        data.update(changes)
        return alumno_repository.crear_alumno(
            database_path=self.database_path,
            **data,
        )

    def test_crear_alumno_guarda_todos_los_campos(self):
        alumno_id = self._crear_alumno()

        alumno = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        self.assertIsInstance(alumno_id, int)
        self.assertGreater(alumno_id, 0)
        self.assertEqual(alumno["nombre"], "Ana López García")
        self.assertEqual(alumno["matricula"], "EDU-001")
        self.assertEqual(alumno["grado"], "3")
        self.assertEqual(alumno["grupo"], "A")
        self.assertIsNone(alumno["fotografia"])
        self.assertEqual(alumno["estado"], "activo")

    def test_obtener_alumno_por_id_existente_devuelve_diccionario(self):
        alumno_id = self._crear_alumno()

        alumno = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        self.assertIsInstance(alumno, dict)
        self.assertEqual(
            set(alumno),
            {
                "alumno_id",
                "nombre",
                "matricula",
                "grado",
                "grupo",
                "fotografia",
                "estado",
            },
        )

    def test_obtener_alumno_por_id_inexistente_devuelve_none(self):
        alumno = alumno_repository.obtener_alumno_por_id(
            9999,
            self.database_path,
        )

        self.assertIsNone(alumno)

    def test_obtener_alumno_por_matricula_existente(self):
        alumno_id = self._crear_alumno()

        alumno = alumno_repository.obtener_alumno_por_matricula(
            "EDU-001",
            self.database_path,
        )

        self.assertEqual(alumno["alumno_id"], alumno_id)
        self.assertEqual(alumno["matricula"], "EDU-001")

    def test_obtener_alumno_por_matricula_inexistente_devuelve_none(self):
        alumno = alumno_repository.obtener_alumno_por_matricula(
            "NO-EXISTE",
            self.database_path,
        )

        self.assertIsNone(alumno)

    def test_existe_matricula_devuelve_true_para_registro_existente(self):
        self._crear_alumno()

        existe = alumno_repository.existe_matricula(
            "EDU-001",
            self.database_path,
        )

        self.assertTrue(existe)

    def test_existe_matricula_devuelve_false_para_registro_inexistente(self):
        existe = alumno_repository.existe_matricula(
            "NO-EXISTE",
            self.database_path,
        )

        self.assertFalse(existe)

    def test_crear_alumno_rechaza_matricula_duplicada_exacta(self):
        primer_id = self._crear_alumno()

        with self.assertRaises(MatriculaDuplicadaError) as context:
            self._crear_alumno(nombre="Otra Alumna")

        alumno = alumno_repository.obtener_alumno_por_matricula(
            "EDU-001",
            self.database_path,
        )
        self.assertEqual(str(context.exception), "La matrícula ya está registrada.")
        self.assertEqual(alumno["alumno_id"], primer_id)
        self.assertEqual(alumno["nombre"], "Ana López García")

    def test_actualizar_alumno_guarda_datos_y_conserva_estado(self):
        alumno_id = self._crear_alumno()

        actualizado = alumno_repository.actualizar_alumno(
            alumno_id,
            "Ana López Actualizada",
            "EDU-002",
            "4",
            "B",
            "fotos/ana.jpg",
            self.database_path,
        )
        alumno = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        self.assertTrue(actualizado)
        self.assertEqual(alumno["nombre"], "Ana López Actualizada")
        self.assertEqual(alumno["matricula"], "EDU-002")
        self.assertEqual(alumno["grado"], "4")
        self.assertEqual(alumno["grupo"], "B")
        self.assertEqual(alumno["fotografia"], "fotos/ana.jpg")
        self.assertEqual(alumno["estado"], "activo")

    def test_actualizar_alumno_inexistente_devuelve_false(self):
        actualizado = alumno_repository.actualizar_alumno(
            9999,
            "Alumno Inexistente",
            "EDU-999",
            "1",
            "Z",
            None,
            self.database_path,
        )

        self.assertFalse(actualizado)

    def test_actualizar_alumno_rechaza_matricula_duplicada_y_revierte(self):
        self._crear_alumno()
        segundo_id = self._crear_alumno(
            nombre="Luis Pérez",
            matricula="EDU-002",
            grado="2",
            grupo="B",
        )

        with self.assertRaises(MatriculaDuplicadaError):
            alumno_repository.actualizar_alumno(
                segundo_id,
                "Luis Modificado",
                "EDU-001",
                "5",
                "C",
                "fotos/luis.jpg",
                self.database_path,
            )

        alumno = alumno_repository.obtener_alumno_por_id(
            segundo_id,
            self.database_path,
        )
        self.assertEqual(alumno["nombre"], "Luis Pérez")
        self.assertEqual(alumno["matricula"], "EDU-002")
        self.assertEqual(alumno["grado"], "2")
        self.assertEqual(alumno["grupo"], "B")
        self.assertIsNone(alumno["fotografia"])

    def test_actualizar_estado_alumno_cambia_solo_el_estado(self):
        alumno_id = self._crear_alumno()
        antes = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        actualizado = alumno_repository.actualizar_estado_alumno(
            alumno_id,
            "inactivo",
            self.database_path,
        )
        despues = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        self.assertTrue(actualizado)
        self.assertEqual(despues["estado"], "inactivo")
        for field in ("nombre", "matricula", "grado", "grupo", "fotografia"):
            self.assertEqual(despues[field], antes[field])

    def test_actualizar_estado_alumno_inexistente_devuelve_false(self):
        actualizado = alumno_repository.actualizar_estado_alumno(
            9999,
            "inactivo",
            self.database_path,
        )

        self.assertFalse(actualizado)

    def test_crear_alumno_con_fotografia_none_conserva_null(self):
        alumno_id = self._crear_alumno(fotografia=None)

        alumno = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        self.assertIsNone(alumno["fotografia"])

    def test_consultas_publicas_no_devuelven_sqlite_row(self):
        alumno_id = self._crear_alumno()

        por_id = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )
        por_matricula = alumno_repository.obtener_alumno_por_matricula(
            "EDU-001",
            self.database_path,
        )

        self.assertIsInstance(por_id, dict)
        self.assertIsInstance(por_matricula, dict)
        self.assertNotIsInstance(por_id, sqlite3.Row)
        self.assertNotIsInstance(por_matricula, sqlite3.Row)

    def test_operaciones_utilizan_base_sqlite_temporal(self):
        alumno_id = self._crear_alumno()

        alumno = alumno_repository.obtener_alumno_por_id(
            alumno_id,
            self.database_path,
        )

        self.assertTrue(self.database_path.is_file())
        self.assertEqual(self.database_path.parent, Path(self.temporary_directory.name))
        self.assertEqual(alumno["alumno_id"], alumno_id)

    def test_load_query_devuelve_consulta_existente_no_vacia(self):
        query = alumno_repository._load_query("select_alumno_by_id.sql")

        self.assertIsInstance(query, str)
        self.assertTrue(query.strip())

    def test_load_query_archivo_inexistente_genera_error_controlado(self):
        file_name = "consulta_inexistente.sql"

        with self.assertRaises(ConsultaSqlError) as context:
            alumno_repository._load_query(file_name)

        self.assertIn(file_name, str(context.exception))

    def test_load_query_nombre_vacio_genera_error_controlado(self):
        with self.assertRaises(ConsultaSqlError):
            alumno_repository._load_query("")

    def test_error_de_conexion_se_traduce_a_repository_error(self):
        original_error = sqlite3.OperationalError("fallo controlado")

        with patch.object(
            alumno_repository.database_manager,
            "get_connection",
            side_effect=original_error,
        ):
            with self.assertRaises(RepositoryError) as context:
                alumno_repository.obtener_alumno_por_id(
                    1,
                    self.database_path,
                )

        self.assertIs(context.exception.__cause__, original_error)
        self.assertNotIsInstance(context.exception, sqlite3.OperationalError)
        self.assertNotIn("SELECT", str(context.exception).upper())

    def test_listar_todos_devuelve_lista_vacia_sin_alumnos(self):
        self.assertEqual(
            alumno_repository.listar_todos(self.database_path),
            [],
        )

    def test_listar_todos_devuelve_todos_los_alumnos(self):
        self._crear_alumno()
        self._crear_alumno(
            nombre="Luis Pérez",
            matricula="EDU-002",
            grado="4",
            grupo="B",
        )

        alumnos = alumno_repository.listar_todos(self.database_path)

        self.assertEqual(len(alumnos), 2)
        self.assertEqual(
            [alumno["matricula"] for alumno in alumnos],
            ["EDU-001", "EDU-002"],
        )

    def test_listar_todos_conserva_orden_por_id(self):
        ids = [
            self._crear_alumno(),
            self._crear_alumno(
                nombre="Luis Pérez",
                matricula="EDU-002",
            ),
            self._crear_alumno(
                nombre="Marta Ruiz",
                matricula="EDU-003",
            ),
        ]

        alumnos = alumno_repository.listar_todos(self.database_path)

        self.assertEqual(
            [alumno["alumno_id"] for alumno in alumnos],
            ids,
        )

    def test_listar_todos_devuelve_campos_esperados(self):
        self._crear_alumno(fotografia="fotos/ana.png", estado="inactivo")

        alumno = alumno_repository.listar_todos(self.database_path)[0]

        self.assertEqual(
            alumno,
            {
                "alumno_id": 1,
                "nombre": "Ana López García",
                "matricula": "EDU-001",
                "grado": "3",
                "grupo": "A",
                "fotografia": "fotos/ana.png",
                "estado": "inactivo",
            },
        )
        self.assertNotIsInstance(alumno, sqlite3.Row)

    def test_listar_todos_traduce_error_sqlite(self):
        with patch.object(
            alumno_repository.database_manager,
            "get_connection",
            side_effect=sqlite3.OperationalError("fallo sqlite"),
        ):
            with self.assertRaises(RepositoryError) as context:
                alumno_repository.listar_todos(self.database_path)

        self.assertEqual(
            str(context.exception),
            "No se pudo completar la consulta de alumnos.",
        )

if __name__ == "__main__":
    unittest.main()

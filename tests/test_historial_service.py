from pathlib import Path
import inspect
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.auth import usuarios_service
from edupass.modules.historial import historial_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import movimiento_repository
from edupass.shared.errors import (
    AlumnoNoEncontradoError,
    MovimientoNoEncontradoError,
    RepositoryError,
    ValidationError,
)


class TestHistorialService(unittest.TestCase):
    PASSWORD = "ClaveFicticiaSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "historial.sqlite"
        )
        database_manager.initialize_database(self.database_path)
        self.scanner = usuarios_service.crear_usuario_demo(
            "Escaner Historial",
            "scanner.historial@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Historial",
            "HIS-0001",
            "3",
            "A",
            estado="activo",
            database_path=self.database_path,
        )
        self.otro_alumno = alumnos_service.registrar_alumno(
            "Otro Alumno",
            "HIS-0002",
            "4",
            "B",
            estado="activo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _insert_movements(self, count, alumno_id=None):
        selected_id = alumno_id or self.alumno["alumno_id"]
        connection = database_manager.get_connection(self.database_path)
        try:
            ids = []
            for index in range(count):
                movement_type = "entrada" if index % 2 == 0 else "salida"
                cursor = connection.execute(
                    """
                    INSERT INTO movimientos (
                        alumno_id, tipo_movimiento, fecha_hora, area_id,
                        punto_plantel, usuario_id, dispositivo_id
                    ) VALUES (?, ?, ?, NULL, ?, ?, NULL);
                    """,
                    (
                        selected_id,
                        movement_type,
                        f"2026-07-30T18:{index:02d}:00.000000Z",
                        "acceso_principal",
                        self.scanner["usuario_id"],
                    ),
                )
                ids.append(int(cursor.lastrowid))
            connection.commit()
            return ids
        finally:
            connection.close()

    def test_alumno_existente_sin_movimientos(self):
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["movimientos"], [])

    def test_estructura_vacia(self):
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["paginacion"]["total_movimientos"], 0)
        self.assertEqual(result["paginacion"]["total_paginas"], 0)

    def test_alumno_con_una_entrada(self):
        self._insert_movements(1)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["movimientos"][0]["tipo_movimiento"], "entrada")

    def test_alumno_con_entrada_y_salida(self):
        self._insert_movements(2)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(len(result["movimientos"]), 2)
        self.assertEqual(result["movimientos"][0]["tipo_movimiento"], "salida")

    def test_orden_descendente(self):
        ids = self._insert_movements(3)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(
            [item["movimiento_id"] for item in result["movimientos"]],
            list(reversed(ids)),
        )

    def test_datos_del_alumno(self):
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(
            set(result["alumno"]),
            {"alumno_id", "nombre", "matricula", "grado", "grupo", "estado"},
        )
        self.assertEqual(result["alumno"]["matricula"], "HIS-0001")

    def test_usuario_responsable(self):
        self._insert_movements(1)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["movimientos"][0]["usuario_nombre"], "Escaner Historial")

    def test_punto_del_plantel(self):
        self._insert_movements(1)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["movimientos"][0]["punto_plantel"], "acceso_principal")

    def test_pagina_uno(self):
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], pagina=1, database_path=self.database_path
        )
        self.assertEqual(result["paginacion"]["pagina"], 1)

    def test_calculo_total(self):
        self._insert_movements(3)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["paginacion"]["total_movimientos"], 3)

    def test_calculo_paginas(self):
        self._insert_movements(51)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(result["paginacion"]["total_paginas"], 2)

    def test_limite_cincuenta(self):
        self._insert_movements(51)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], database_path=self.database_path
        )
        self.assertEqual(len(result["movimientos"]), 50)

    def test_registros_cincuenta_y_cincuenta_y_uno(self):
        self._insert_movements(51)
        first = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], pagina=1, database_path=self.database_path
        )
        second = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], pagina=2, database_path=self.database_path
        )
        self.assertEqual((len(first["movimientos"]), len(second["movimientos"])), (50, 1))

    def test_pagina_siguiente(self):
        self._insert_movements(51)
        result = historial_service.consultar_historial_alumno(
            self.alumno["alumno_id"], pagina=1, database_path=self.database_path
        )
        self.assertTrue(result["paginacion"]["tiene_siguiente"])
        self.assertFalse(result["paginacion"]["tiene_anterior"])

    def test_pagina_cero(self):
        with self.assertRaises(ValidationError):
            historial_service.consultar_historial_alumno(
                self.alumno["alumno_id"], pagina=0, database_path=self.database_path
            )

    def test_pagina_negativa(self):
        with self.assertRaises(ValidationError):
            historial_service.consultar_historial_alumno(
                self.alumno["alumno_id"], pagina=-1, database_path=self.database_path
            )

    def test_pagina_no_entera(self):
        with self.assertRaises(ValidationError):
            historial_service.consultar_historial_alumno(
                self.alumno["alumno_id"], pagina="1", database_path=self.database_path
            )

    def test_tamano_cero(self):
        with self.assertRaises(ValidationError):
            historial_service.consultar_historial_alumno(
                self.alumno["alumno_id"], tamano_pagina=0, database_path=self.database_path
            )

    def test_tamano_superior_a_cincuenta(self):
        with self.assertRaises(ValidationError):
            historial_service.consultar_historial_alumno(
                self.alumno["alumno_id"], tamano_pagina=51, database_path=self.database_path
            )

    def test_alumno_id_invalido(self):
        for value in (0, -1, "1", True, None):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    historial_service.consultar_historial_alumno(
                        value, database_path=self.database_path
                    )

    def test_alumno_inexistente(self):
        with self.assertRaises(AlumnoNoEncontradoError):
            historial_service.consultar_historial_alumno(
                99999, database_path=self.database_path
            )

    def test_movimiento_existente(self):
        movimiento_id = self._insert_movements(1)[0]
        result = historial_service.consultar_movimiento(
            movimiento_id,
            alumno_id=self.alumno["alumno_id"],
            database_path=self.database_path,
        )
        self.assertEqual(result["movimiento_id"], movimiento_id)
        self.assertEqual(result["matricula"], "HIS-0001")

    def test_movimiento_inexistente(self):
        with self.assertRaises(MovimientoNoEncontradoError):
            historial_service.consultar_movimiento(
                99999, database_path=self.database_path
            )

    def test_movimiento_de_otro_alumno_rechazado(self):
        movimiento_id = self._insert_movements(1)[0]
        with self.assertRaises(MovimientoNoEncontradoError):
            historial_service.consultar_movimiento(
                movimiento_id,
                alumno_id=self.otro_alumno["alumno_id"],
                database_path=self.database_path,
            )

    def test_resultado_seguro(self):
        movimiento_id = self._insert_movements(1)[0]
        result = historial_service.consultar_movimiento(
            movimiento_id, database_path=self.database_path
        )
        forbidden = {"token", "token_hash", "password_hash", "correo", "fotografia"}
        self.assertTrue(forbidden.isdisjoint(result))

    def test_repository_error_propagado(self):
        original = RepositoryError("fallo controlado")
        with patch.object(
            movimiento_repository,
            "contar_por_alumno",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                historial_service.consultar_historial_alumno(
                    self.alumno["alumno_id"], database_path=self.database_path
                )
        self.assertIs(context.exception, original)

    def test_ausencia_de_flask(self):
        source = inspect.getsource(historial_service).lower()
        self.assertNotIn("from flask", source)
        self.assertNotIn("import flask", source)

    def test_ausencia_de_sql(self):
        source = inspect.getsource(historial_service).upper()
        self.assertNotIn("SELECT ", source)
        self.assertNotIn("INSERT INTO", source)


if __name__ == "__main__":
    unittest.main()

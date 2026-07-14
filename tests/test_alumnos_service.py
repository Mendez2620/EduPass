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

from edupass.modules.alumnos import alumnos_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import alumno_repository
from edupass.shared.constants import (
    ESTADO_ALUMNO_ACTIVO,
    ESTADO_ALUMNO_INACTIVO,
)
from edupass.shared.errors import (
    AlumnoNoEncontradoError,
    ConsultaSqlError,
    MatriculaDuplicadaError,
    RepositoryError,
    ValidationError,
)


class TestAlumnosService(unittest.TestCase):
    EXPECTED_KEYS = {
        "alumno_id",
        "nombre",
        "matricula",
        "grado",
        "grupo",
        "fotografia",
        "estado",
    }

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "edupass_service_test.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _datos_alumno(self, **changes):
        data = {
            "nombre": "Ana López García",
            "matricula": "EDU-001",
            "grado": "3",
            "grupo": "A",
            "fotografia": None,
            "estado": ESTADO_ALUMNO_ACTIVO,
        }
        data.update(changes)
        return data

    def _registrar_alumno(self, **changes):
        return alumnos_service.registrar_alumno(
            database_path=self.database_path,
            **self._datos_alumno(**changes),
        )

    def _assert_alumno_dict(self, alumno):
        self.assertIsInstance(alumno, dict)
        self.assertNotIsInstance(alumno, sqlite3.Row)
        self.assertEqual(set(alumno), self.EXPECTED_KEYS)

    def test_registrar_alumno_valido_con_estado_predeterminado(self):
        alumno = alumnos_service.registrar_alumno(
            nombre="Ana López García",
            matricula="EDU-001",
            grado="3",
            grupo="A",
            fotografia=None,
            database_path=self.database_path,
        )

        persistido = alumnos_service.consultar_alumno_por_id(
            alumno["alumno_id"],
            self.database_path,
        )
        self._assert_alumno_dict(alumno)
        self.assertIsInstance(alumno["alumno_id"], int)
        self.assertGreater(alumno["alumno_id"], 0)
        self.assertEqual(alumno["estado"], ESTADO_ALUMNO_ACTIVO)
        self.assertEqual(persistido, alumno)

    def test_registrar_alumno_normaliza_todos_los_datos(self):
        alumno = self._registrar_alumno(
            nombre="  Ana López García  ",
            matricula="  edu-001  ",
            grado="  3  ",
            grupo="  a  ",
            fotografia="  fotos/ana.png  ",
            estado="  ACTIVO  ",
        )

        self.assertEqual(alumno["nombre"], "Ana López García")
        self.assertEqual(alumno["matricula"], "EDU-001")
        self.assertEqual(alumno["grado"], "3")
        self.assertEqual(alumno["grupo"], "a")
        self.assertEqual(alumno["fotografia"], "fotos/ana.png")
        self.assertEqual(alumno["estado"], "activo")

    def test_registrar_alumno_normaliza_fotografia_none_y_vacia(self):
        cases = (("EDU-001", None), ("EDU-002", "   "))

        for matricula, fotografia in cases:
            with self.subTest(fotografia=fotografia):
                alumno = self._registrar_alumno(
                    matricula=matricula,
                    fotografia=fotografia,
                )
                self.assertIsNone(alumno["fotografia"])

    def test_registrar_alumno_normaliza_estado_inactivo(self):
        alumno = self._registrar_alumno(estado=" INACTIVO ")

        self.assertEqual(alumno["estado"], ESTADO_ALUMNO_INACTIVO)

    def test_registrar_alumno_conserva_espacios_internos_en_matricula(self):
        alumno = self._registrar_alumno(matricula="abc 123")

        self.assertEqual(alumno["matricula"], "ABC 123")

    def test_registrar_alumno_rechaza_campos_obligatorios_vacios(self):
        for field in ("nombre", "matricula", "grado", "grupo"):
            for value in ("", "   "):
                with self.subTest(field=field, value=value):
                    data = self._datos_alumno()
                    data[field] = value
                    with self.assertRaises(ValidationError):
                        alumnos_service.registrar_alumno(
                            database_path=self.database_path,
                            **data,
                        )

        self.assertFalse(
            alumno_repository.existe_matricula("EDU-001", self.database_path)
        )

    def test_registrar_alumno_rechaza_tipos_incorrectos_obligatorios(self):
        for field in ("nombre", "matricula", "grado", "grupo"):
            for value in (None, 123, [], True):
                with self.subTest(field=field, value=value):
                    data = self._datos_alumno()
                    data[field] = value
                    with self.assertRaises(ValidationError):
                        alumnos_service.registrar_alumno(
                            database_path=self.database_path,
                            **data,
                        )

    def test_registrar_alumno_rechaza_tipo_incorrecto_fotografia(self):
        for value in (123, [], True):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self._registrar_alumno(fotografia=value)

    def test_registrar_alumno_rechaza_estado_invalido(self):
        message = "El estado del alumno debe ser activo o inactivo."

        for value in ("", "pendiente", "habilitado", 1, None, True):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as context:
                    self._registrar_alumno(estado=value)
                self.assertEqual(str(context.exception), message)

    def test_registrar_alumno_rechaza_matricula_duplicada_exacta(self):
        primero = self._registrar_alumno()

        with self.assertRaises(MatriculaDuplicadaError) as context:
            self._registrar_alumno(nombre="Otra Alumna")

        persistido = alumnos_service.consultar_alumno_por_matricula(
            "EDU-001",
            self.database_path,
        )
        self.assertEqual(str(context.exception), "La matrícula ya está registrada.")
        self.assertEqual(persistido, primero)

    def test_registrar_alumno_rechaza_variantes_normalizadas_duplicadas(self):
        self._registrar_alumno()

        for matricula in ("edu-001", "  EDU-001  ", "  edu-001  "):
            with self.subTest(matricula=matricula):
                with self.assertRaises(MatriculaDuplicadaError):
                    self._registrar_alumno(
                        nombre="Otra Alumna",
                        matricula=matricula,
                    )

    def test_consultar_alumno_por_id_existente(self):
        registrado = self._registrar_alumno()

        consultado = alumnos_service.consultar_alumno_por_id(
            registrado["alumno_id"],
            self.database_path,
        )

        self.assertEqual(consultado, registrado)

    def test_consultar_alumno_por_id_inexistente_genera_error(self):
        with self.assertRaises(AlumnoNoEncontradoError) as context:
            alumnos_service.consultar_alumno_por_id(9999, self.database_path)

        self.assertEqual(str(context.exception), "No se encontró el alumno.")

    def test_consultar_alumno_por_matricula_normalizada(self):
        registrado = self._registrar_alumno()

        consultado = alumnos_service.consultar_alumno_por_matricula(
            "  edu-001  ",
            self.database_path,
        )

        self.assertEqual(consultado, registrado)

    def test_consultar_alumno_por_matricula_inexistente_genera_error(self):
        with self.assertRaises(AlumnoNoEncontradoError):
            alumnos_service.consultar_alumno_por_matricula(
                "EDU-999",
                self.database_path,
            )

    def test_consultar_alumno_por_matricula_vacia_genera_validation_error(self):
        with patch.object(
            alumnos_service.alumno_repository,
            "obtener_alumno_por_matricula",
        ) as mocked_repository:
            with self.assertRaises(ValidationError):
                alumnos_service.consultar_alumno_por_matricula(
                    "   ",
                    self.database_path,
                )

        mocked_repository.assert_not_called()

    def test_consultar_alumno_por_id_rechaza_identificadores_invalidos(self):
        message = "El identificador del alumno debe ser un entero mayor que cero."

        for alumno_id in (None, "1", 1.5, True, False, 0, -1):
            with self.subTest(alumno_id=alumno_id):
                with self.assertRaises(ValidationError) as context:
                    alumnos_service.consultar_alumno_por_id(
                        alumno_id,
                        self.database_path,
                    )
                self.assertEqual(str(context.exception), message)

    def test_editar_activar_y_desactivar_validan_id_antes_de_operar(self):
        operations = (
            (
                "editar",
                lambda: alumnos_service.editar_alumno(
                    "1", "Nombre", "EDU-001", "3", "A", None,
                    self.database_path,
                ),
            ),
            (
                "activar",
                lambda: alumnos_service.activar_alumno(0, self.database_path),
            ),
            (
                "desactivar",
                lambda: alumnos_service.desactivar_alumno(
                    False,
                    self.database_path,
                ),
            ),
        )

        for name, operation in operations:
            with self.subTest(operation=name):
                with self.assertRaises(ValidationError):
                    operation()

    def test_editar_alumno_actualiza_todos_los_campos_y_conserva_estado(self):
        registrado = self._registrar_alumno()

        editado = alumnos_service.editar_alumno(
            registrado["alumno_id"],
            "Ana Actualizada",
            "EDU-002",
            "4",
            "B",
            "fotos/nueva.png",
            self.database_path,
        )
        persistido = alumnos_service.consultar_alumno_por_id(
            registrado["alumno_id"],
            self.database_path,
        )

        self.assertEqual(editado, persistido)
        self.assertEqual(editado["nombre"], "Ana Actualizada")
        self.assertEqual(editado["matricula"], "EDU-002")
        self.assertEqual(editado["grado"], "4")
        self.assertEqual(editado["grupo"], "B")
        self.assertEqual(editado["fotografia"], "fotos/nueva.png")
        self.assertEqual(editado["estado"], ESTADO_ALUMNO_ACTIVO)

    def test_editar_alumno_normaliza_datos(self):
        registrado = self._registrar_alumno()

        editado = alumnos_service.editar_alumno(
            registrado["alumno_id"],
            "  Ana Editada  ",
            "  edu-002  ",
            "  4  ",
            "  b  ",
            "  fotos/editada.png  ",
            self.database_path,
        )

        self.assertEqual(editado["nombre"], "Ana Editada")
        self.assertEqual(editado["matricula"], "EDU-002")
        self.assertEqual(editado["grado"], "4")
        self.assertEqual(editado["grupo"], "b")
        self.assertEqual(editado["fotografia"], "fotos/editada.png")

    def test_editar_alumno_permite_su_misma_matricula_normalizada(self):
        registrado = self._registrar_alumno()

        editado = alumnos_service.editar_alumno(
            registrado["alumno_id"],
            "Ana Editada",
            "  edu-001  ",
            "4",
            "B",
            None,
            self.database_path,
        )

        self.assertEqual(editado["matricula"], "EDU-001")
        self.assertEqual(editado["nombre"], "Ana Editada")

    def test_editar_alumno_rechaza_matricula_de_otro_alumno(self):
        self._registrar_alumno()
        segundo = self._registrar_alumno(
            nombre="Luis Pérez",
            matricula="EDU-002",
            grado="2",
            grupo="B",
        )

        for matricula in ("EDU-001", "  edu-001  "):
            with self.subTest(matricula=matricula):
                with self.assertRaises(MatriculaDuplicadaError):
                    alumnos_service.editar_alumno(
                        segundo["alumno_id"],
                        "Luis Modificado",
                        matricula,
                        "5",
                        "C",
                        None,
                        self.database_path,
                    )

                persistido = alumnos_service.consultar_alumno_por_id(
                    segundo["alumno_id"],
                    self.database_path,
                )
                self.assertEqual(persistido, segundo)

    def test_editar_alumno_inexistente_genera_error(self):
        with self.assertRaises(AlumnoNoEncontradoError):
            alumnos_service.editar_alumno(
                9999,
                "Nombre",
                "EDU-999",
                "3",
                "A",
                None,
                self.database_path,
            )

    def test_editar_alumno_rechaza_campos_vacios_sin_cambiar_datos(self):
        registrado = self._registrar_alumno()

        for field in ("nombre", "matricula", "grado", "grupo"):
            with self.subTest(field=field):
                data = {
                    "nombre": "Ana Editada",
                    "matricula": "EDU-002",
                    "grado": "4",
                    "grupo": "B",
                }
                data[field] = "   "
                with self.assertRaises(ValidationError):
                    alumnos_service.editar_alumno(
                        registrado["alumno_id"],
                        fotografia=None,
                        database_path=self.database_path,
                        **data,
                    )

                persistido = alumnos_service.consultar_alumno_por_id(
                    registrado["alumno_id"],
                    self.database_path,
                )
                self.assertEqual(persistido, registrado)

    def test_editar_alumno_no_modifica_estado_inactivo(self):
        registrado = self._registrar_alumno(estado=ESTADO_ALUMNO_INACTIVO)

        editado = alumnos_service.editar_alumno(
            registrado["alumno_id"],
            "Ana Editada",
            "EDU-002",
            "4",
            "B",
            None,
            self.database_path,
        )

        self.assertEqual(editado["estado"], ESTADO_ALUMNO_INACTIVO)

    def test_desactivar_alumno_activo_cambia_solo_estado(self):
        registrado = self._registrar_alumno()

        desactivado = alumnos_service.desactivar_alumno(
            registrado["alumno_id"],
            self.database_path,
        )
        persistido = alumnos_service.consultar_alumno_por_id(
            registrado["alumno_id"],
            self.database_path,
        )

        self.assertEqual(desactivado, persistido)
        self.assertEqual(desactivado["estado"], ESTADO_ALUMNO_INACTIVO)
        for field in ("nombre", "matricula", "grado", "grupo", "fotografia"):
            self.assertEqual(desactivado[field], registrado[field])

    def test_activar_alumno_inactivo_cambia_solo_estado(self):
        registrado = self._registrar_alumno(estado=ESTADO_ALUMNO_INACTIVO)

        activado = alumnos_service.activar_alumno(
            registrado["alumno_id"],
            self.database_path,
        )

        self.assertEqual(activado["estado"], ESTADO_ALUMNO_ACTIVO)
        for field in ("nombre", "matricula", "grado", "grupo", "fotografia"):
            self.assertEqual(activado[field], registrado[field])

    def test_cambios_de_estado_son_idempotentes(self):
        activo = self._registrar_alumno()
        inactivo = self._registrar_alumno(
            nombre="Luis Pérez",
            matricula="EDU-002",
            estado=ESTADO_ALUMNO_INACTIVO,
        )

        operations = (
            (alumnos_service.activar_alumno, activo, ESTADO_ALUMNO_ACTIVO),
            (
                alumnos_service.desactivar_alumno,
                inactivo,
                ESTADO_ALUMNO_INACTIVO,
            ),
        )
        for operation, alumno, expected_state in operations:
            with self.subTest(operation=operation.__name__):
                result = operation(alumno["alumno_id"], self.database_path)
                self.assertEqual(result["estado"], expected_state)

    def test_cambios_de_estado_en_alumno_inexistente_generan_error(self):
        for operation in (
            alumnos_service.activar_alumno,
            alumnos_service.desactivar_alumno,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(AlumnoNoEncontradoError):
                    operation(9999, self.database_path)

    def test_operaciones_exitosas_devuelven_diccionario_completo(self):
        registrado = self._registrar_alumno()
        consultado = alumnos_service.consultar_alumno_por_id(
            registrado["alumno_id"],
            self.database_path,
        )
        editado = alumnos_service.editar_alumno(
            registrado["alumno_id"],
            "Ana Editada",
            "EDU-002",
            "4",
            "B",
            None,
            self.database_path,
        )
        desactivado = alumnos_service.desactivar_alumno(
            registrado["alumno_id"],
            self.database_path,
        )
        activado = alumnos_service.activar_alumno(
            registrado["alumno_id"],
            self.database_path,
        )

        for operation, alumno in (
            ("registrar", registrado),
            ("consultar", consultado),
            ("editar", editado),
            ("desactivar", desactivado),
            ("activar", activado),
        ):
            with self.subTest(operation=operation):
                self._assert_alumno_dict(alumno)
                self.assertNotIsInstance(alumno, tuple)
                self.assertNotIsInstance(alumno, bool)
                self.assertIsNotNone(alumno)

    def test_repository_error_se_propaga_sin_imprimir(self):
        original_error = RepositoryError("fallo controlado")

        with patch.object(
            alumnos_service.alumno_repository,
            "existe_matricula",
            side_effect=original_error,
        ), patch("builtins.print") as mocked_print:
            with self.assertRaises(RepositoryError) as context:
                self._registrar_alumno()

        self.assertIs(context.exception, original_error)
        mocked_print.assert_not_called()

    def test_consulta_sql_error_se_propaga_sin_transformarse(self):
        original_error = ConsultaSqlError("consulta no disponible")

        with patch.object(
            alumnos_service.alumno_repository,
            "obtener_alumno_por_id",
            side_effect=original_error,
        ):
            with self.assertRaises(ConsultaSqlError) as context:
                alumnos_service.consultar_alumno_por_id(1, self.database_path)

        self.assertIs(context.exception, original_error)

    def test_matricula_duplicada_del_repositorio_se_propaga(self):
        original_error = MatriculaDuplicadaError(
            "La matrícula ya está registrada."
        )

        with patch.object(
            alumnos_service.alumno_repository,
            "existe_matricula",
            return_value=False,
        ), patch.object(
            alumnos_service.alumno_repository,
            "crear_alumno",
            side_effect=original_error,
        ):
            with self.assertRaises(MatriculaDuplicadaError) as context:
                self._registrar_alumno()

        self.assertIs(context.exception, original_error)

    def test_registro_creado_no_recuperable_genera_repository_error(self):
        with patch.object(
            alumnos_service.alumno_repository,
            "existe_matricula",
            return_value=False,
        ), patch.object(
            alumnos_service.alumno_repository,
            "crear_alumno",
            return_value=42,
        ), patch.object(
            alumnos_service.alumno_repository,
            "obtener_alumno_por_id",
            return_value=None,
        ):
            with self.assertRaises(RepositoryError):
                self._registrar_alumno()

    def test_edicion_con_actualizacion_false_genera_no_encontrado(self):
        alumno = self._datos_alumno(alumno_id=1)

        with patch.object(
            alumnos_service.alumno_repository,
            "obtener_alumno_por_id",
            return_value=alumno,
        ), patch.object(
            alumnos_service.alumno_repository,
            "obtener_alumno_por_matricula",
            return_value=None,
        ), patch.object(
            alumnos_service.alumno_repository,
            "actualizar_alumno",
            return_value=False,
        ):
            with self.assertRaises(AlumnoNoEncontradoError):
                alumnos_service.editar_alumno(
                    1,
                    "Ana Editada",
                    "EDU-002",
                    "4",
                    "B",
                    None,
                    self.database_path,
                )

    def test_cambio_estado_con_actualizacion_false_genera_no_encontrado(self):
        alumno = self._datos_alumno(alumno_id=1)

        with patch.object(
            alumnos_service.alumno_repository,
            "obtener_alumno_por_id",
            return_value=alumno,
        ), patch.object(
            alumnos_service.alumno_repository,
            "actualizar_estado_alumno",
            return_value=False,
        ):
            with self.assertRaises(AlumnoNoEncontradoError):
                alumnos_service.desactivar_alumno(1, self.database_path)

    def test_flujo_completo_integrado_con_sqlite_temporal(self):
        registrado = self._registrar_alumno()
        por_id = alumnos_service.consultar_alumno_por_id(
            registrado["alumno_id"],
            self.database_path,
        )
        por_matricula = alumnos_service.consultar_alumno_por_matricula(
            "  edu-001  ",
            self.database_path,
        )
        editado = alumnos_service.editar_alumno(
            registrado["alumno_id"],
            "Ana López García",
            "edu-002",
            "4",
            "B",
            None,
            self.database_path,
        )
        desactivado = alumnos_service.desactivar_alumno(
            registrado["alumno_id"],
            self.database_path,
        )
        final_inactivo = alumnos_service.consultar_alumno_por_id(
            registrado["alumno_id"],
            self.database_path,
        )
        activado = alumnos_service.activar_alumno(
            registrado["alumno_id"],
            self.database_path,
        )

        self.assertEqual(por_id, registrado)
        self.assertEqual(por_matricula, registrado)
        self.assertEqual(editado["matricula"], "EDU-002")
        self.assertEqual(editado["grado"], "4")
        self.assertEqual(editado["grupo"], "B")
        self.assertEqual(desactivado["estado"], ESTADO_ALUMNO_INACTIVO)
        self.assertEqual(final_inactivo, desactivado)
        self.assertEqual(activado["estado"], ESTADO_ALUMNO_ACTIVO)

    def test_integracion_utiliza_exclusivamente_base_temporal(self):
        alumno = self._registrar_alumno()

        consultado = alumnos_service.consultar_alumno_por_id(
            alumno["alumno_id"],
            self.database_path,
        )

        self.assertTrue(self.database_path.is_file())
        self.assertEqual(
            self.database_path.parent,
            Path(self.temporary_directory.name),
        )
        self.assertEqual(consultado, alumno)


if __name__ == "__main__":
    unittest.main()

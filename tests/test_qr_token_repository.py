from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager
from edupass.persistence.repositories import qr_token_repository
from edupass.shared.constants import (
    QR_ESTADO_ACTIVO,
    QR_ESTADO_INVALIDADO,
    QR_ESTADO_UTILIZADO,
)
from edupass.shared.errors import ConsultaSqlError, RepositoryError


class TestQrTokenRepository(unittest.TestCase):
    AHORA = "2026-07-27T12:00:00.000000Z"
    EXPIRA = "2026-07-27T12:00:30.000000Z"
    DESPUES = "2026-07-27T12:00:31.000000Z"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "qr_repository.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )
        self.alumno_id = self._crear_alumno("QR-001", "activo")
        self.inactivo_id = self._crear_alumno("QR-002", "inactivo")
        self.token = "A" * 43
        self.token_hash = self._hash(self.token)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def _hash(token):
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def _crear_alumno(self, matricula, estado):
        connection = database_manager.get_connection(self.database_path)
        try:
            cursor = connection.execute(
                """
                INSERT INTO alumnos
                    (nombre, matricula, grado, grupo, fotografia, estado)
                VALUES (?, ?, ?, ?, NULL, ?);
                """,
                ("Alumno Demo", matricula, "3", "A", estado),
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()

    def _reemplazar(
        self,
        token_hash=None,
        alumno_id=None,
        generado_en=None,
        expira_en=None,
    ):
        return qr_token_repository.reemplazar_token_activo(
            alumno_id or self.alumno_id,
            token_hash or self.token_hash,
            generado_en or self.AHORA,
            expira_en or self.EXPIRA,
            self.database_path,
        )

    def _rows(self):
        connection = database_manager.get_connection(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM qr_tokens ORDER BY qr_id;"
                ).fetchall()
            ]
        finally:
            connection.close()

    def test_insertar_token_para_alumno_existente(self):
        row = self._reemplazar()

        self.assertGreater(row["qr_id"], 0)
        self.assertEqual(row["alumno_id"], self.alumno_id)
        self.assertEqual(row["estado"], QR_ESTADO_ACTIVO)

    def test_persiste_hash_y_no_token_original(self):
        self._reemplazar()

        row = self._rows()[0]
        self.assertEqual(row["token_hash"], self.token_hash)
        self.assertNotEqual(row["token_hash"], self.token)
        self.assertNotIn(self.token, row.values())

    def test_obtener_por_hash(self):
        esperado = self._reemplazar()

        obtenido = qr_token_repository.obtener_por_hash(
            self.token_hash,
            self.database_path,
        )

        self.assertEqual(obtenido, esperado)
        self.assertEqual(obtenido["alumno_estado"], "activo")

    def test_token_inexistente_devuelve_none(self):
        self.assertIsNone(
            qr_token_repository.obtener_por_hash(
                "f" * 64,
                self.database_path,
            )
        )

    def test_reemplazo_invalida_token_activo_anterior(self):
        self._reemplazar()
        segundo_hash = self._hash("B" * 43)

        self._reemplazar(segundo_hash)

        rows = self._rows()
        self.assertEqual(rows[0]["estado"], QR_ESTADO_INVALIDADO)
        self.assertEqual(rows[1]["estado"], QR_ESTADO_ACTIVO)

    def test_reemplazo_deja_exactamente_un_token_activo(self):
        for character in ("A", "B", "C"):
            self._reemplazar(self._hash(character * 43))

        activos = [r for r in self._rows() if r["estado"] == QR_ESTADO_ACTIVO]
        self.assertEqual(len(activos), 1)

    def test_obtener_vigente_antes_del_vencimiento(self):
        self._reemplazar()

        metadata = qr_token_repository.obtener_vigente_por_alumno(
            self.alumno_id,
            self.AHORA,
            self.database_path,
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["alumno_id"], self.alumno_id)

    def test_no_obtener_en_instante_exacto_de_vencimiento(self):
        self._reemplazar()

        metadata = qr_token_repository.obtener_vigente_por_alumno(
            self.alumno_id,
            self.EXPIRA,
            self.database_path,
        )

        self.assertIsNone(metadata)

    def test_no_obtener_despues_del_vencimiento(self):
        self._reemplazar()

        self.assertIsNone(
            qr_token_repository.obtener_vigente_por_alumno(
                self.alumno_id,
                self.DESPUES,
                self.database_path,
            )
        )

    def test_metadata_no_contiene_token_ni_hash(self):
        self._reemplazar()

        metadata = qr_token_repository.obtener_vigente_por_alumno(
            self.alumno_id,
            self.AHORA,
            self.database_path,
        )

        self.assertEqual(
            set(metadata),
            {"qr_id", "alumno_id", "generado_en", "expira_en", "usado_en", "estado"},
        )
        self.assertNotIn("token_hash", metadata)
        self.assertNotIn("token", metadata)

    def test_consumir_token_activo(self):
        self._reemplazar()

        result = qr_token_repository.consumir_condicionalmente(
            self.token_hash,
            self.AHORA,
            self.AHORA,
            self.database_path,
        )

        self.assertEqual(result.resultado, qr_token_repository.CONSUMO_CONSUMIDO)
        self.assertEqual(result.alumno_id, self.alumno_id)

    def test_consumo_asigna_estado_utilizado_y_usado_en(self):
        self._reemplazar()
        qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.AHORA, self.AHORA, self.database_path
        )

        row = self._rows()[0]
        self.assertEqual(row["estado"], QR_ESTADO_UTILIZADO)
        self.assertEqual(row["usado_en"], self.AHORA)

    def test_segundo_consumo_es_rechazado(self):
        self._reemplazar()
        primero = qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.AHORA, self.AHORA, self.database_path
        )
        segundo = qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.AHORA, self.AHORA, self.database_path
        )

        self.assertEqual(primero.resultado, qr_token_repository.CONSUMO_CONSUMIDO)
        self.assertEqual(segundo.resultado, qr_token_repository.CONSUMO_UTILIZADO)

    def test_token_vencido_es_clasificado(self):
        self._reemplazar()

        result = qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.EXPIRA, self.EXPIRA, self.database_path
        )

        self.assertEqual(result.resultado, qr_token_repository.CONSUMO_VENCIDO)

    def test_token_invalidado_es_clasificado(self):
        self._reemplazar()
        self._reemplazar(self._hash("B" * 43))

        result = qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.AHORA, self.AHORA, self.database_path
        )

        self.assertEqual(result.resultado, qr_token_repository.CONSUMO_INVALIDADO)

    def test_alumno_inactivo_es_clasificado(self):
        self._reemplazar(alumno_id=self.inactivo_id)

        result = qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.AHORA, self.AHORA, self.database_path
        )

        self.assertEqual(
            result.resultado,
            qr_token_repository.CONSUMO_ALUMNO_INACTIVO,
        )

    def test_token_inexistente_es_clasificado(self):
        result = qr_token_repository.consumir_condicionalmente(
            "f" * 64, self.AHORA, self.AHORA, self.database_path
        )

        self.assertEqual(result.resultado, qr_token_repository.CONSUMO_INEXISTENTE)

    def test_fk_de_alumno_invalido_es_controlada(self):
        with self.assertRaises(RepositoryError) as context:
            self._reemplazar(alumno_id=9999)

        self.assertIsInstance(context.exception.__cause__, sqlite3.IntegrityError)

    def test_error_sqlite_es_traducido(self):
        original = sqlite3.OperationalError("fallo controlado")
        with patch.object(
            qr_token_repository.database_manager,
            "get_connection",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                qr_token_repository.obtener_por_hash(
                    self.token_hash,
                    self.database_path,
                )

        self.assertIs(context.exception.__cause__, original)
        self.assertNotIn("SELECT", str(context.exception).upper())

    def test_sql_faltante_es_traducido(self):
        with patch.object(
            qr_token_repository,
            "_SELECT_BY_HASH_FILE",
            "consulta_inexistente.sql",
        ):
            with self.assertRaises(ConsultaSqlError):
                qr_token_repository.obtener_por_hash(
                    self.token_hash,
                    self.database_path,
                )

    def test_rollback_cuando_falla_insercion(self):
        self._reemplazar()

        with self.assertRaises(RepositoryError):
            self._reemplazar()

        row = self._rows()[0]
        self.assertEqual(row["estado"], QR_ESTADO_ACTIVO)
        self.assertEqual(len(self._rows()), 1)

    def test_dos_reemplazos_no_crean_dos_tokens_activos(self):
        hashes = [self._hash("D" * 43), self._hash("E" * 43)]
        for token_hash in hashes:
            self._reemplazar(token_hash)

        estados = [row["estado"] for row in self._rows()]
        self.assertEqual(estados.count(QR_ESTADO_ACTIVO), 1)
        self.assertEqual(estados.count(QR_ESTADO_INVALIDADO), 1)

    def test_consumo_condicional_fallido_no_modifica_fila(self):
        self._reemplazar()

        result = qr_token_repository.consumir_condicionalmente(
            self.token_hash, self.EXPIRA, self.EXPIRA, self.database_path
        )

        self.assertEqual(result.resultado, qr_token_repository.CONSUMO_VENCIDO)
        row = self._rows()[0]
        self.assertEqual(row["estado"], QR_ESTADO_ACTIVO)
        self.assertIsNone(row["usado_en"])

    def test_concurrencia_permite_un_solo_consumo_exitoso(self):
        self._reemplazar()
        barrier = threading.Barrier(2, timeout=5)

        def consume_once():
            barrier.wait()
            return qr_token_repository.consumir_condicionalmente(
                self.token_hash,
                self.AHORA,
                self.AHORA,
                self.database_path,
            ).resultado

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: consume_once(), range(2)))

        self.assertEqual(results.count(qr_token_repository.CONSUMO_CONSUMIDO), 1)
        self.assertEqual(results.count(qr_token_repository.CONSUMO_UTILIZADO), 1)


if __name__ == "__main__":
    unittest.main()

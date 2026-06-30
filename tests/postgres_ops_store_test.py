import unittest


class FakeCursor:
    def __init__(self, rowsets=None):
        self.rowsets = rowsets or {}
        self.current_rows = None
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized_sql = " ".join(sql.split())
        self.statements.append(normalized_sql)
        self.params.append(tuple(params or ()))
        self.current_rows = None
        for marker, rows in self.rowsets.items():
            if marker in normalized_sql:
                self.current_rows = list(rows)
                break

    def fetchall(self):
        rows = list(self.current_rows or [])
        self.current_rows = []
        return rows


class FakeConnection:
    def __init__(self, rowsets=None):
        self.cursor_instance = FakeCursor(rowsets=rowsets)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class PostgresOpsStoreTest(unittest.TestCase):
    def test_admin_gate_diagnoses_write_and_read_ops_schema(self):
        from server.postgres_ops_store import PostgresOpsStore

        conn = FakeConnection(
            rowsets={
                "FROM ops.admin_gate_diagnoses": [
                    (
                        "agd-pg-1",
                        "gear",
                        "gear_variant",
                        "variant-pg-1",
                        "system_gap_suspected",
                        "parser_or_mapping_bug",
                        "Needs recheck",
                        "Owner note",
                        "owner",
                        "fingerprint",
                        "2026-06-30T00:00:00+00:00",
                        {"targetStatus": "blocked"},
                        "2026-06-30T00:00:00+00:00",
                        "",
                    )
                ]
            }
        )
        store = PostgresOpsStore(lambda: conn)

        created = store.create_admin_gate_diagnosis(
            {
                "id": "agd-pg-1",
                "targetDomain": "gear",
                "targetType": "gear_variant",
                "targetId": "variant-pg-1",
                "diagnosis": "system_gap_suspected",
                "gapType": "parser_or_mapping_bug",
                "reason": "Needs recheck",
                "note": "Owner note",
                "actor": "owner",
                "targetFingerprint": "fingerprint",
                "createdAt": "2026-06-30T00:00:00+00:00",
                "updatedAt": "2026-06-30T00:00:00+00:00",
                "expiresAt": "",
            },
            {"targetStatus": "blocked"},
        )
        rows = store.list_admin_gate_diagnoses()

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(created["id"], "agd-pg-1")
        self.assertEqual(rows[0]["targetId"], "variant-pg-1")
        self.assertIn("INSERT INTO ops.admin_gate_diagnoses", sql)
        self.assertIn("INSERT INTO ops.audit_logs", sql)
        audit_params = conn.cursor_instance.params[1]
        self.assertIn("agd-pg-1", audit_params[4])
        self.assertIn("FROM ops.admin_gate_diagnoses", sql)
        self.assertTrue(conn.committed)


if __name__ == "__main__":
    unittest.main()

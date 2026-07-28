import json
import unittest

from server.gear_catalog_audit_store import (
    GearCatalogAuditPointerChanged,
    GearCatalogAuditQueryFailed,
    GearCatalogAuditStore,
)


POINTER_ROW = (
    17,
    "season-manifest:sha256:" + ("1" * 64),
    "active",
    "season-manifest:sha256:" + ("0" * 64),
    "season-17",
    "gear-release:sha256:" + ("2" * 64),
    "community-release:sha256:" + ("3" * 64),
    "talent-r1",
    {"gearRuleRevision": "gear-r1"},
    "season-manifest:sha256:" + ("0" * 64),
    {"gearRuleRevision": "gear-r1"},
    {"gearRuleRevision": "gear-r1"},
)


class FakeCursor:
    def __init__(self, rowsets=None, fail_marker=""):
        self.rowsets = rowsets or {}
        self.fail_marker = fail_marker
        self.marker_calls = {}
        self.current_rows = []
        self.statements = []
        self.params = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.statements.append(normalized)
        self.params.append(tuple(params or ()))
        if self.fail_marker and self.fail_marker in normalized:
            raise RuntimeError("forced audit query failure")
        self.current_rows = []
        for marker, configured in self.rowsets.items():
            if marker not in normalized:
                continue
            call_index = self.marker_calls.get(marker, 0)
            self.marker_calls[marker] = call_index + 1
            if (
                isinstance(configured, list)
                and configured
                and isinstance(configured[0], list)
            ):
                selected = configured[min(call_index, len(configured) - 1)]
            else:
                selected = configured
            self.current_rows = list(selected or [])
            break

    def fetchone(self):
        return self.current_rows.pop(0) if self.current_rows else None

    def fetchall(self):
        rows = list(self.current_rows)
        self.current_rows = []
        return rows


class FakeConnection:
    def __init__(self, rowsets=None, fail_marker=""):
        self.cursor_instance = FakeCursor(rowsets=rowsets, fail_marker=fail_marker)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def rowsets(pointer_rows=None):
    pointer_rows = pointer_rows or [[POINTER_ROW], [POINTER_ROW]]
    return {
        "gear_catalog_audit_pointer_binding": pointer_rows,
        "gear_catalog_audit_items": [
            (
                "1001",
                "Verified Helm",
                "head",
                285,
                "verified",
                {"sourceStatus": "verified"},
                True,
                True,
            )
        ],
        "gear_catalog_audit_variants": [
            (
                "variant-1",
                "1001",
                "hero-6",
                "head",
                "hero",
                285,
                {"bonus_id": "9001/9002", "ilevel": "285"},
                "verified",
                [],
                {
                    "trackKey": "hero",
                    "trackRank": 6,
                    "trackEvidence": [{"source": "verified-fixture"}],
                    "resolvedStats": {"haste_rating": 120},
                },
                "raid",
                True,
            )
        ],
        "gear_catalog_audit_options": [
            (
                "option-1",
                "gem:240892",
                "gem",
                "verified",
                {"gem_id": "240892"},
                {"statDeltas": {"haste_rating": 16}},
            )
        ],
        "gear_catalog_audit_community_templates": [
            (
                "community-template-1",
                "mage",
                "frost",
                {
                    "slots": {
                        "head": {
                            "itemId": "1001",
                            "bonusIds": ["9001", "9002"],
                            "trackKey": "hero",
                            "rank": 3,
                            "ilevel": 278,
                        }
                    }
                },
                {},
                [],
            )
        ],
        "gear_catalog_audit_personal_templates": [
            (
                "a" * 64,
                {
                    "rawString": json.dumps(
                        {
                            "schemaRevision": "gear-template-draft-v2",
                            "gearBySlot": {
                                "head": {
                                    "itemId": "1001",
                                    "bonusIds": ["9001", "9002"],
                                    "trackKey": "hero",
                                    "rank": 3,
                                    "ilevel": 278,
                                    "gemIds": ["240892", None],
                                }
                            },
                            "enhancementBySlot": {},
                        }
                    )
                },
                {},
            )
        ],
        "gear_catalog_audit_relation_sizes": [
            ("cache.websim_release_registry", 4096, 1024, 512)
        ],
        "gear_catalog_audit_release_events": [
            ("refresh_no_change", 2, "2026-07-28T09:00:00+08:00")
        ],
    }


def write_statements(statements):
    prefixes = ("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "TRUNCATE ", "ALTER ", "CREATE ", "DROP ")
    return [statement for statement in statements if statement.upper().startswith(prefixes)]


class GearCatalogAuditStoreTest(unittest.TestCase):
    def test_snapshot_is_fixed_query_read_only_bounded_and_rolled_back(self):
        connection = FakeConnection(rowsets())
        store = GearCatalogAuditStore(lambda: connection)

        snapshot = store.snapshot(
            statement_timeout_ms=15_000,
            lock_timeout_ms=1_000,
            batch_size=500,
        )

        statements = connection.cursor_instance.statements
        self.assertTrue(any(statement == "BEGIN READ ONLY" for statement in statements))
        self.assertTrue(any("SET LOCAL statement_timeout" in statement for statement in statements))
        self.assertTrue(any("SET LOCAL lock_timeout" in statement for statement in statements))
        self.assertEqual(write_statements(statements), [])
        self.assertLessEqual(store.query_count, 12)
        self.assertEqual(snapshot["queryMetrics"]["writes"], 0)
        self.assertEqual(snapshot["pointerBefore"], snapshot["pointerAfter"])
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)

    def test_snapshot_projects_structural_templates_without_raw_or_personal_identity(self):
        connection = FakeConnection(rowsets())
        snapshot = GearCatalogAuditStore(lambda: connection).snapshot()

        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("rawString", serialized)
        self.assertNotIn("userId", serialized)
        self.assertNotIn("community-template-1", serialized)
        self.assertRegex(
            snapshot["communityTemplates"][0]["templateIdentity"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            snapshot["personalGearTemplates"][0]["gearItems"][0]["itemId"],
            "1001",
        )
        self.assertEqual(
            snapshot["personalGearTemplates"][0]["gearItems"][0]["gemIds"],
            ["240892", None],
        )

    def test_snapshot_classifies_legacy_variant_families_without_ranking_leakage(self):
        configured = rowsets()
        configured["gear_catalog_audit_variants"] = [
            (
                "browse-hero",
                "1001",
                "hero-6",
                "head",
                "hero",
                285,
                {"bonus_id": "9001/9002", "ilevel": "285"},
                "verified",
                [],
                {
                    "itemLevelTrack": "hero",
                    "trackRank": 6,
                    "rank": 999,
                    "trackEvidence": [{"source": "verified-fixture"}],
                    "resolvedStats": {"haste_rating": 120},
                },
                "raid",
                True,
            ),
            (
                "exact-observed",
                "1001",
                "observed-278-a",
                "head",
                "observed_profile",
                278,
                {"bonus_id": "9100", "ilevel": "278"},
                "verified",
                [],
                {
                    "rank": 527,
                    "rankingEvidence": {"rank": 527, "score": 3400},
                    "resolvedStats": {"haste_rating": 100},
                },
                "observed_profile",
                False,
            ),
            (
                "placeholder",
                "1001",
                "needs-variant",
                "head",
                "needs-variant",
                0,
                {},
                "partial",
                ["missing variant"],
                {},
                "",
                False,
            ),
            (
                "preview",
                "1001",
                "battle-net-preview-250",
                "head",
                "battle_net_preview",
                250,
                {"ilevel": "250"},
                "verified",
                [],
                {},
                "battle_net_preview",
                False,
            ),
        ]
        connection = FakeConnection(configured)
        snapshot = GearCatalogAuditStore(lambda: connection).snapshot()
        variants = {
            row["variantId"]: row
            for row in snapshot["catalogRows"]["variants"]
        }

        self.assertEqual(variants["browse-hero"].get("rowFamily"), "browse")
        self.assertEqual(variants["browse-hero"]["trackKey"], "hero")
        self.assertEqual(variants["browse-hero"]["trackRank"], 6)
        self.assertEqual(variants["browse-hero"]["sourceType"], "raid")
        self.assertTrue(variants["browse-hero"]["hasVoidInstanceSource"])
        self.assertTrue(variants["browse-hero"]["hasTrackEvidence"])
        self.assertNotIn("sourceRows", variants["browse-hero"])
        self.assertEqual(
            variants["browse-hero"]["simcOptions"],
            {"bonus_id": "9001/9002", "ilevel": "285"},
        )
        self.assertEqual(
            variants["exact-observed"]["rowFamily"],
            "exact_instance",
        )
        self.assertEqual(variants["exact-observed"]["trackRank"], 0)
        self.assertNotIn("rank", variants["exact-observed"])
        self.assertNotIn("rankingEvidence", variants["exact-observed"])
        self.assertEqual(variants["placeholder"]["rowFamily"], "placeholder")
        self.assertEqual(variants["preview"]["rowFamily"], "reference")
        variant_query = next(
            statement
            for statement in connection.cursor_instance.statements
            if "gear_catalog_audit_variants" in statement
        )
        self.assertIn("source.instance_id = '1305'", variant_query)

    def test_snapshot_projects_item_reference_booleans(self):
        snapshot = GearCatalogAuditStore(
            lambda: FakeConnection(rowsets())
        ).snapshot()
        item = snapshot["catalogRows"]["items"][0]

        self.assertIs(item.get("hasSourceRefs"), True)
        self.assertIs(item.get("hasVariantRefs"), True)

    def test_changed_pointer_discards_mixed_snapshot_and_rolls_back(self):
        changed = list(POINTER_ROW)
        changed[0] = 18
        connection = FakeConnection(
            rowsets(pointer_rows=[[POINTER_ROW], [tuple(changed)]])
        )
        store = GearCatalogAuditStore(lambda: connection)

        with self.assertRaisesRegex(
            GearCatalogAuditPointerChanged,
            "AUDIT_POINTER_CHANGED",
        ):
            store.snapshot()

        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)

    def test_query_failure_rolls_back_and_closes(self):
        connection = FakeConnection(
            rowsets(),
            fail_marker="gear_catalog_audit_options",
        )

        with self.assertRaisesRegex(
            GearCatalogAuditQueryFailed,
            "AUDIT_QUERY_FAILED:gear_catalog_audit_options",
        ) as failure:
            GearCatalogAuditStore(lambda: connection).snapshot()

        self.assertEqual(failure.exception.query_marker, "gear_catalog_audit_options")
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)

    def test_relation_size_query_uses_only_the_frozen_allowlist(self):
        connection = FakeConnection(rowsets())
        GearCatalogAuditStore(lambda: connection).snapshot()

        cursor = connection.cursor_instance
        index = next(
            index
            for index, statement in enumerate(cursor.statements)
            if "gear_catalog_audit_relation_sizes" in statement
        )
        relation_params = cursor.params[index][0]
        self.assertIsInstance(relation_params, list)
        self.assertIn(
            "WHERE item_row.release_id = ANY",
            cursor.statements[index],
        )
        self.assertIn(
            "WHERE template_row.release_id = ANY",
            cursor.statements[index],
        )
        self.assertIn("cache.websim_release_registry", relation_params)
        self.assertIn("app.build_templates", relation_params)
        self.assertNotIn("caller_supplied_table", relation_params)
        self.assertIn("pg_total_relation_size", cursor.statements[index])
        self.assertIn("pg_column_size", cursor.statements[index])
        self.assertNotIn("0::bigint AS active_logical_bytes", cursor.statements[index])

    def test_invalid_limits_fail_before_connecting(self):
        connected = False

        def connection_factory():
            nonlocal connected
            connected = True
            return FakeConnection(rowsets())

        store = GearCatalogAuditStore(connection_factory)

        with self.assertRaisesRegex(ValueError, "batch_size"):
            store.snapshot(batch_size=1001)
        with self.assertRaisesRegex(ValueError, "statement_timeout_ms"):
            store.snapshot(statement_timeout_ms=30_001)
        with self.assertRaisesRegex(ValueError, "lock_timeout_ms"):
            store.snapshot(lock_timeout_ms=5_001)

        self.assertFalse(connected)


if __name__ == "__main__":
    unittest.main()

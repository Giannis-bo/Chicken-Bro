import json
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


class FakeCursor:
    def __init__(self, rows=None, rowsets=None):
        self.rows = list(rows or [])
        self.rowsets = rowsets or {}
        self.current_rows = None
        self.statements = []
        self.params = []
        self.rowcount = 1

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
                if isinstance(rows, dict):
                    key = tuple(params or ())
                    self.current_rows = list(rows.get(key, rows.get("*", [])))
                else:
                    self.current_rows = list(rows)
                break
        if (
            self.current_rows is None
            and "FROM cache.websim_active_manifest_pointer pointer" in normalized_sql
        ):
            self.current_rows = []

    def fetchone(self):
        if self.current_rows is not None:
            if not self.current_rows:
                return None
            return self.current_rows.pop(0)
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchall(self):
        if self.current_rows is not None:
            rows = list(self.current_rows)
            self.current_rows = []
            return rows
        rows = list(self.rows)
        self.rows = []
        return rows


class FakeConnection:
    def __init__(self, rows=None, rowsets=None):
        self.cursor_instance = FakeCursor(rows=rows, rowsets=rowsets)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class PreCutoverReleaseStore:
    def load_active_manifest_binding(self):
        return {
            "pointerMode": "pre_cutover",
            "generation": 0,
            "formalActiveManifest": False,
        }


class PostgresCacheStoreTest(unittest.TestCase):
    def test_sync_state_round_trip_uses_cache_schema_jsonb(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(rows=[({"ok": True, "dataStatus": "verified"}, "2026-06-28T01:00:00+00:00")])
        store = PostgresCacheStore(lambda: conn)

        store.save_sync_state("websim_sync", {"ok": True, "dataStatus": "verified"}, "2026-06-28T01:00:00+00:00")
        state = store.get_sync_state("websim_sync")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(state["dataStatus"], "verified")
        self.assertEqual(state["updatedAt"], "2026-06-28T01:00:00+00:00")
        self.assertIn("INSERT INTO cache.websim_sync_state", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertIn("state_json", sql)
        self.assertIn("SELECT state_json, updated_at FROM cache.websim_sync_state", sql)
        self.assertTrue(conn.committed)

    def test_season_instances_and_loot_read_models_use_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [
                    (
                        "dungeon-a",
                        "1300",
                        "Dungeon A",
                        "DA",
                        1800,
                        {"sourceRefs": [{"type": "journal"}]},
                    )
                ],
                "FROM cache.websim_instances ORDER BY": [
                    ("1300", "Dungeon A", "dungeon"),
                ],
                "FROM cache.websim_encounters": [
                    ("encounter-a", "1300", "Encounter A"),
                ],
                "FROM cache.websim_loot": [
                    (
                        "loot-a",
                        "1300",
                        "Dungeon A",
                        "encounter-a",
                        "Encounter A",
                        "item-a",
                        "Item A",
                        "trinket1",
                        "epic",
                        "https://render.worldofwarcraft.com/icon-a.jpg",
                        {"id": "item-a", "name": "Item A", "slot": "trinket1", "quality": "epic"},
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        season = store.get_active_season_payload()
        instances = store.get_websim_instances()
        loot = store.get_websim_loot({"instanceId": "1300"})

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(season["seasonRevision"], "season-pg-1")
        self.assertEqual(season["dungeons"][0]["instanceId"], "1300")
        self.assertEqual(instances[0]["encounters"][0]["id"], "encounter-a")
        self.assertEqual(loot["items"][0]["itemId"], "item-a")
        self.assertEqual(loot["items"][0]["instanceName"], "Dungeon A")
        self.assertIn("FROM cache.websim_season_state", sql)
        self.assertIn("FROM cache.websim_season_dungeons", sql)
        self.assertIn("FROM cache.websim_instances", sql)
        self.assertIn("FROM cache.websim_encounters", sql)
        self.assertIn("FROM cache.websim_loot", sql)

    def test_expired_active_season_is_returned_as_stale_not_missing(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2000-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        season = store.get_active_season_payload()

        self.assertEqual(season["seasonRevision"], "season-pg-1")
        self.assertEqual(season["dataStatus"], "stale")
        self.assertIn("season cache expired", season["errors"])

    def test_websim_gear_reports_expired_pg_season_as_stale_blocker(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2000-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "verified",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "frost", compact=True)

        self.assertEqual(payload["dataStatus"], "stale")
        self.assertEqual(len(payload["replacementCandidates"]), 16)
        self.assertEqual(payload["replacementCandidates"][0]["slot"], "head")
        self.assertEqual(payload["replacementCandidates"][0]["items"], [])
        self.assertIn("slots", payload)
        self.assertIsInstance(payload["equippedSet"], dict)
        self.assertIn("readiness", payload)
        self.assertIn("season cache expired", payload["catalogBlockers"])

    def test_gear_read_model_attaches_candidate_legality_debug_fields_to_full_payload(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "verified",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_sources", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_variants", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 0, ""),
                ],
                "FROM cache.websim_gear_sources": [
                    (
                        "source-head-a",
                        "head-a",
                        "raid",
                        "raid-head-a",
                        "The Voidspire",
                        "2001",
                        "",
                        "mythic",
                        "season-pg-1",
                        {},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "variant-head-a",
                        "head-a",
                        "head",
                        "head-a-mythic",
                        "Mythic Head A",
                        "raid",
                        "mythic",
                        289,
                        {"ilevel": "289", "bonus_id": "12345"},
                        "verified",
                        [],
                        {"sourceStatus": "verified"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_items": [
                    (
                        "head-a",
                        "Head A",
                        "head",
                        289,
                        {
                            "id": "head-a",
                            "name": "Head A",
                            "inventory_type": {"type": "HEAD", "name": "头部"},
                            "item_class": {"id": 4, "name": "Armor"},
                            "item_subclass": {"id": 1, "name": "Cloth"},
                            "quality": "epic",
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        full_payload = store.get_websim_gear("mage", "arcane", compact=False)
        compact_payload = store.get_websim_gear("mage", "arcane", compact=True)

        full_head = next(group for group in full_payload["replacementCandidates"] if group["slot"] == "head")["items"][0]
        compact_head = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "head")["items"][0]
        self.assertEqual(full_head["legalityStatus"], "legal")
        self.assertEqual(full_head["sourceTrust"], "official_current_season")
        self.assertEqual(full_head["legalityReasons"], [])
        self.assertNotIn("legalityReasons", compact_head)
        self.assertNotIn("sourceTrust", compact_head)

    def test_websim_gear_keeps_cached_read_model_when_pg_season_is_stale(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2000-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "partial",
                            "schemaRevision": "gear-catalog-test",
                            "itemDatabaseRevision": "items-rev",
                            "variantRevision": "variants-rev",
                            "itemCount": 1,
                            "sourceCount": 1,
                            "variantCount": 1,
                            "verifiedCount": 1,
                            "blockers": ["missing deterministic SimC variant preset"],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_sources": [
                    (
                        "11111111-1111-4111-8111-111111111111",
                        "item-a",
                        "dungeon",
                        "source-a",
                        "Encounter A",
                        "1300",
                        "encounter-a",
                        "mythic",
                        "season-pg-1",
                        {"recommendationScore": 88},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "22222222-2222-4222-8222-222222222222",
                        "item-a",
                        "trinket1",
                        "item-a-mythic",
                        "Mythic Item A",
                        "dungeon",
                        "mythic",
                        678,
                        {"ilevel": 678},
                        "verified",
                        [],
                        {"sourceStatus": "verified"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_items": [
                    (
                        "item-a",
                        "Item A",
                        "trinket1",
                        678,
                        {
                            "id": "item-a",
                            "name": "Item A",
                            "slot": "trinket1",
                            "quality": "epic",
                            "iconUrl": "https://render.worldofwarcraft.com/icon-a.jpg",
                            "sourceStatus": "verified",
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "arcane", compact=True)

        sql = "\n".join(conn.cursor_instance.statements)
        trinket_groups = [group for group in payload["replacementCandidates"] if group["slot"] == "trinket1"]
        self.assertEqual(payload["dataStatus"], "stale")
        self.assertIn("slots", payload)
        self.assertIsInstance(payload["equippedSet"], dict)
        self.assertIn("readiness", payload)
        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])
        self.assertEqual(payload["communityTemplateSync"]["templates"]["blocked"], 0)
        self.assertEqual(payload["communityTemplateSync"]["templates"]["pending"], 0)
        self.assertTrue(trinket_groups)
        trinket_group = trinket_groups[0]
        self.assertEqual(trinket_group["items"][0]["itemId"], "item-a")
        self.assertIn("season cache expired", payload["catalogBlockers"])
        self.assertIn("missing deterministic SimC variant preset", payload["catalogBlockers"])
        self.assertIn("FROM cache.websim_gear_sources", sql)
        self.assertIn("FROM cache.websim_gear_variants", sql)

    def test_gear_read_model_uses_cache_schema_catalog_rows(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "verified",
                            "schemaRevision": "gear-catalog-test",
                            "itemDatabaseRevision": "items-rev",
                            "variantRevision": "variants-rev",
                            "itemCount": 1,
                            "sourceCount": 1,
                            "variantCount": 1,
                            "verifiedCount": 1,
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_sources": [
                    (
                        "11111111-1111-4111-8111-111111111111",
                        "item-a",
                        "dungeon",
                        "source-a",
                        "Encounter A",
                        "1300",
                        "encounter-a",
                        "mythic",
                        "season-pg-1",
                        {"recommendationScore": 88},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "22222222-2222-4222-8222-222222222222",
                        "item-a",
                        "trinket1",
                        "item-a-mythic",
                        "Mythic Item A",
                        "dungeon",
                        "mythic",
                        678,
                        {"ilevel": 678},
                        "verified",
                        [],
                        {"sourceStatus": "verified"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_mod_options": [
                    (
                        "33333333-3333-4333-8333-333333333333",
                        "socket",
                        "socket-a",
                        "Gem A",
                        ["trinket1"],
                        {"gem_id": "213743"},
                        "verified",
                        {"displayLabel": "Gem A"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "item-a",
                        "Item A",
                        "trinket1",
                        678,
                        {
                            "id": "item-a",
                            "name": "Item A",
                            "slot": "trinket1",
                            "quality": "epic",
                            "iconUrl": "https://render.worldofwarcraft.com/icon-a.jpg",
                            "sourceStatus": "verified",
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "arcane", compact=True)

        sql = "\n".join(conn.cursor_instance.statements)
        trinket_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "trinket1")
        self.assertEqual(payload["catalogStatus"], "verified")
        self.assertEqual(payload["gearCatalogRevision"], "gear-catalog-test")
        self.assertEqual(trinket_group["items"][0]["itemId"], "item-a")
        self.assertEqual(trinket_group["items"][0]["variants"][0]["itemLevel"], 678)
        self.assertEqual(trinket_group["socketOptions"][0]["simcOptions"]["gem_id"], "213743")
        self.assertIn("FROM cache.websim_gear_sources", sql)
        self.assertIn("FROM cache.websim_gear_variants", sql)
        self.assertIn("FROM cache.websim_gear_mod_options", sql)
        self.assertIn("FROM cache.websim_items", sql)

    def test_gear_read_model_restores_pg_enchant_display_names_from_simc_ids(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "verified", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_sources", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_variants", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_mod_options", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_community_gear_templates", 0, ""),
                ],
                "FROM cache.websim_gear_sources": [
                    (
                        "source-feet",
                        "feet-a",
                        "raid",
                        "raid-feet",
                        "Sporefall",
                        "2001",
                        "",
                        "mythic",
                        "season-pg-1",
                        {},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "variant-feet",
                        "feet-a",
                        "feet",
                        "feet-a-mythic",
                        "Mythic Feet A",
                        "raid",
                        "mythic",
                        289,
                        {"ilevel": "289", "bonus_id": "12345"},
                        "verified",
                        [],
                        {"sourceStatus": "verified"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_mod_options": [
                    (
                        "enchant-7935",
                        "enchant",
                        "enchant-7935",
                        "7935",
                        ["feet"],
                        {"enchant_id": "7935"},
                        "verified",
                        {},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "feet-a",
                        "Feet A",
                        "feet",
                        289,
                        {
                            "id": "feet-a",
                            "name": "Feet A",
                            "inventory_type": {"type": "FEET", "name": "脚"},
                            "quality": "epic",
                            "iconUrl": "https://render.worldofwarcraft.com/feet-a.jpg",
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "arcane", compact=True)
        feet_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "feet")

        self.assertEqual(feet_group["enchantOptions"][0]["label"], "阳炎丝绸魔线")
        self.assertEqual(feet_group["enchantOptions"][0]["displayStatus"], "verified")

    def test_gear_read_model_keeps_crafted_candidates_beyond_compact_limit(self):
        from server.postgres_cache_store import PostgresCacheStore

        source_rows = []
        variant_rows = []
        item_rows = []
        for index in range(12):
            item_id = f"raid-wrist-{index}"
            source_rows.append(
                (
                    f"source-{item_id}",
                    item_id,
                    "raid",
                    f"raid-{item_id}",
                    "Sporefall",
                    "2001",
                    "",
                    "mythic",
                    "season-pg-1",
                    {},
                    "2026-06-28T01:00:00+00:00",
                )
            )
            item_level = 310 - index
            variant_rows.append(
                (
                    f"variant-{item_id}",
                    item_id,
                    "wrist",
                    f"{item_id}-mythic",
                    f"Mythic Wrist {index}",
                    "raid",
                    "mythic",
                    item_level,
                    {"ilevel": str(item_level), "bonus_id": "12345"},
                    "verified",
                    [],
                    {"sourceStatus": "verified"},
                    "2026-06-28T01:00:00+00:00",
                )
            )
            item_rows.append(
                (
                    item_id,
                    f"Raid Wrist {index}",
                    "wrist",
                    item_level,
                    {
                        "id": item_id,
                        "name": f"Raid Wrist {index}",
                        "inventory_type": {"type": "WRIST", "name": "腕部"},
                        "quality": "epic",
                    },
                    "verified",
                )
            )

        crafted_id = "crafted-wrist"
        source_rows.append(
            (
                "source-crafted-wrist",
                crafted_id,
                "crafted",
                "crafted-governed-wrist",
                "制造装备",
                "",
                "",
                "crafted_myth",
                "season-pg-1",
                {},
                "2026-06-28T01:00:00+00:00",
            )
        )
        variant_rows.append(
            (
                "variant-crafted-wrist",
                crafted_id,
                "wrist",
                "crafted-myth-285-haste-mastery",
                "神话 285 · 急速 + 精通",
                "crafted",
                "crafted_myth",
                285,
                {"ilevel": "285", "crafted_stats": "40/32"},
                "verified",
                [],
                {
                    "sourceStatus": "verified",
                    "craftedStatKey": "haste-mastery",
                    "craftedStatLabel": "急速 + 精通",
                    "statSummary": "智力 285；急速 + 精通",
                },
                "2026-06-28T01:00:00+00:00",
            )
        )
        item_rows.append(
            (
                crafted_id,
                "Crafted Wrist",
                "wrist",
                285,
                {
                    "id": crafted_id,
                    "name": "制造护腕",
                    "inventory_type": {"type": "WRIST", "name": "腕部"},
                    "quality": "epic",
                },
                "verified",
            )
        )

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "verified", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", len(item_rows), "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_sources", len(source_rows), "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_variants", len(variant_rows), "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 0, ""),
                ],
                "FROM cache.websim_gear_sources": source_rows,
                "FROM cache.websim_gear_variants": variant_rows,
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_items": item_rows,
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "arcane", compact=True)
        wrist_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "wrist")

        self.assertTrue(any(item.get("sourceType") == "crafted" for item in wrist_group["items"]))
        self.assertGreaterEqual(len(wrist_group["items"]), 13)

    def test_gear_read_model_splits_pg_community_and_baseline_templates(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "partial",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 0, ""),
                    ("websim_gear_sources", 0, ""),
                    ("websim_gear_variants", 0, ""),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 2, "2026-06-28T01:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [],
                "FROM cache.websim_gear_variants": [],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "44444444-4444-4444-8444-444444444444",
                        "mage",
                        "frost",
                        "Frost Gear Template",
                        "simc_preset",
                        "SimC preset",
                        "https://example.test/gear",
                        "synced",
                        "complete",
                        "sig-gear-a",
                        [{"type": "simc"}],
                        [{"slot": "head", "itemId": "250101", "simcReady": True}],
                        "head=template_helm,id=250101,ilevel=289",
                        16,
                        [],
                        "weekly",
                        {"scenarioKey": "mplus_mixed_route"},
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-a",
                    ),
                    (
                        "55555555-5555-4555-8555-555555555555",
                        "mage",
                        "frost",
                        "Observed Frost Gear",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/us/area-52/Treehealer",
                        "partial",
                        "partial",
                        "sig-gear-b",
                        [{"type": "raiderio"}],
                        [{"slot": "head", "itemId": "250101", "simcReady": True}],
                        "head=template_helm,id=250101,ilevel=289",
                        1,
                        ["neck"],
                        "observed",
                        {
                            "sampleCount": 1,
                            "profileHash": "profile:druid:restoration:treehealer",
                            "gearHash": "gear:druid:restoration:treehealer",
                        },
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-b",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "frost", compact=True)

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])
        self.assertEqual(payload["communityTemplateSync"]["templates"]["partial"], 0)
        self.assertEqual(payload["communityTemplateSync"]["templates"]["verified"], 0)
        self.assertEqual(payload["communityTemplateSync"]["templates"]["total"], 0)
        self.assertIn("FROM cache.websim_community_gear_templates", sql)

    def test_gear_read_model_gates_illegal_pg_baseline_templates(self):
        from server.postgres_cache_store import PostgresCacheStore

        legal_head = {
            "slot": "head",
            "simcSlot": "head",
            "itemId": "270001",
            "id": "270001",
            "name": "legal_head",
            "displayName": "Legal Head",
            "armorType": "Cloth",
            "simcReady": True,
        }
        illegal_main_hand = {
            "slot": "main_hand",
            "simcSlot": "main_hand",
            "itemId": "270002",
            "id": "270002",
            "name": "illegal_two_hand_mace",
            "weaponType": "Two-Handed Mace",
            "simcReady": True,
        }
        illegal_off_hand = {
            "slot": "off_hand",
            "simcSlot": "off_hand",
            "itemId": "270003",
            "id": "270003",
            "name": "held_offhand",
            "weaponType": "Held In Off-hand",
            "simcReady": True,
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "partial", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 0, ""),
                    ("websim_gear_sources", 0, ""),
                    ("websim_gear_variants", 0, ""),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 1, "2026-06-28T01:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [],
                "FROM cache.websim_gear_variants": [],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "44444444-4444-4444-8444-444444444444",
                        "mage",
                        "frost",
                        "Frost Mage Season Recommendation",
                        "season_recommendation",
                        "season_recommendation",
                        "https://example.test/gear",
                        "synced",
                        "complete",
                        "sig-gear-illegal",
                        [{"type": "season_recommendation"}],
                        [illegal_main_hand, illegal_off_hand, legal_head],
                        "main_hand=illegal_two_hand_mace,id=270002",
                        16,
                        [],
                        "season recommendation",
                        {"templateSlot": "baseline"},
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-illegal",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "frost", compact=True)

        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])

    def test_elemental_initial_payload_only_exposes_observed_template(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        def item_for_slot(slot, index):
            item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(280000 + index),
                "id": str(280000 + index),
                "name": f"elemental_{slot}",
                "displayName": f"Elemental {slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            if slot in {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}:
                item["armorType"] = "Mail"
            if slot == "main_hand":
                item["weaponType"] = "One-Handed Mace"
            if slot == "off_hand":
                item["weaponType"] = "Shield"
            return item

        gear_items = [item_for_slot(slot, index) for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)]

        def row(template_id, source_key, payload):
            return (
                template_id,
                "shaman",
                "elemental",
                template_id,
                source_key,
                source_key,
                "https://raider.io/characters/cn/sylvanas/听凭风引" if source_key == "raiderio_observed_profile" else "",
                "synced",
                "complete",
                template_id,
                [{"sourceKey": source_key}],
                gear_items,
                "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                16,
                [],
                "elemental template",
                payload,
                "2026-07-08T10:00:00+08:00",
                "2099-01-01T00:00:00+00:00",
                "scan-elemental",
            )

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-07-08T02:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "partial", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-07-08T02:01:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_gear_templates": [
                    row(
                        "observed_profile_shaman_elemental",
                        "raiderio_observed_profile",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:shaman:elemental:tingping",
                            "gearHash": "gear:shaman:elemental:tingping",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                        },
                    ),
                    row(
                        "season_recommendation_shaman_elemental",
                        "season_recommendation",
                        {"templateSlot": "baseline", "templateEvidence": {"recommendationConfidence": "provisional"}},
                    ),
                    row(
                        "recommended_bis_shaman_elemental",
                        "recommended_bis",
                        {
                            "templateType": "recommended_bis",
                            "templateEvidence": {
                                "schemaRevision": "recommended-bis-v1",
                                "status": "projected_bis",
                                "simc": {"status": "required", "highIterationRuns": 0, "pairwiseCompares": 0},
                                "anchorValidation": {"status": "pending"},
                            },
                        },
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("shaman", "elemental", compact=True, mode="initial")

        self.assertEqual([template["sourceKey"] for template in payload["communityTemplates"]], ["raiderio_observed_profile"])
        self.assertEqual(payload["baselineTemplates"], [])
        chain = payload["communityTemplateSync"]["templateChains"]
        self.assertEqual(chain["legacyFallback"]["totalSpecCount"], 0)
        self.assertEqual(chain["recommendedBis"]["totalSpecCount"], 0)

    def test_pg_gear_template_selectors_match_observed_only_golden_payload(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        fixture_path = Path(__file__).parent / "fixtures" / "pg-gear-template-selectors-observed-only.json"
        expected = json.loads(fixture_path.read_text(encoding="utf-8"))
        weapon_types = {
            "main_hand": "Wand",
            "off_hand": "Held In Off-hand",
        }
        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(610000 + index),
                "id": str(610000 + index),
                "name": f"observed_{slot}",
                "displayName": f"Observed {slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                **({"armorType": "Cloth"} if slot in {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"} else {}),
                **({"weaponType": weapon_types[slot]} if slot in weapon_types else {}),
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]

        def row(template_id, source_key, payload):
            return (
                template_id,
                "mage",
                "arcane",
                template_id,
                source_key,
                source_key,
                "https://raider.io/characters/cn/realm/Arcaneproof" if source_key == "raiderio_observed_profile" else "",
                "synced",
                "complete",
                template_id,
                [{"sourceKey": source_key}],
                gear_items,
                "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                16,
                [],
                "pg selector golden",
                payload,
                "2026-07-09T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                "scan-pg-selector-golden",
            )

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-07-09T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "partial", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-07-09T00:01:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_gear_templates": [
                    row(
                        "observed-profile-mage-arcane",
                        "raiderio_observed_profile",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:mage:arcane:observed",
                            "gearHash": "gear:mage:arcane:observed",
                            "fetchedAt": "2026-07-09T00:00:00+00:00",
                        },
                    ),
                    row(
                        "recommended-bis-mage-arcane",
                        "recommended_bis",
                        {
                            "templateType": "recommended_bis",
                            "templateEvidence": {
                                "schemaRevision": "recommended-bis-v1",
                                "status": "projected_bis",
                                "simc": {"status": "required", "highIterationRuns": 0, "pairwiseCompares": 0},
                                "anchorValidation": {"status": "pending"},
                            },
                        },
                    ),
                    row(
                        "season-recommendation-mage-arcane",
                        "season_recommendation",
                        {"templateSlot": "baseline", "templateEvidence": {"recommendationConfidence": "provisional"}},
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "arcane", compact=True, mode="initial")
        chain = payload["communityTemplateSync"]["templateChains"]
        stable_chain = {
            key: {
                nested_key: nested_value
                for nested_key, nested_value in (chain.get(key) or {}).items()
                if nested_key != "lastGuardCheckAt"
            }
            for key in ("communityObserved", "recommendedBis", "legacyFallback")
        }
        actual = {
            "communityTemplates": payload["communityTemplates"],
            "baselineTemplates": payload["baselineTemplates"],
            "baselineSet": payload["baselineSet"],
            "equippedSet": payload["equippedSet"],
            "templateChains": stable_chain,
        }

        self.assertEqual(actual, expected)

    def test_pg_initial_gear_selector_calls_gear_public_contract_module(self):
        import server.gear_public_contract as gear_public_contract
        import server.postgres_cache_store as postgres_cache_store

        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-07-09T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "partial", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-07-09T00:01:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_gear_templates": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)
        original_public_selector = gear_public_contract.public_gear_templates_for_spec
        original_baseline_fallback = gear_public_contract.public_baseline_fallback_templates_for_spec
        public_selector_calls = []
        baseline_fallback_calls = []

        def track_public_selector(templates, class_key, spec_key, **kwargs):
            public_selector_calls.append((list(templates or []), class_key, spec_key, kwargs))
            return original_public_selector(templates, class_key, spec_key, **kwargs)

        def track_baseline_fallback(class_key, spec_key, **kwargs):
            baseline_fallback_calls.append((class_key, spec_key, kwargs))
            return original_baseline_fallback(class_key, spec_key, **kwargs)

        with patch.object(
            postgres_cache_store.gear_public_contract,
            "public_gear_templates_for_spec",
            side_effect=track_public_selector,
        ), patch.object(
            postgres_cache_store.gear_public_contract,
            "public_baseline_fallback_templates_for_spec",
            side_effect=track_baseline_fallback,
        ):
            payload = store.get_websim_gear("mage", "arcane", compact=True, mode="initial")

        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])
        self.assertGreaterEqual(len(public_selector_calls), 2)
        self.assertEqual(len(baseline_fallback_calls), 1)
        self.assertTrue(
            all(call[2] == "arcane" for call in public_selector_calls),
            "PG gear selector should route public filtering through gear_public_contract",
        )

    def test_initial_payload_hides_source_less_observed_template_blocked_by_legality_gate(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        def item_for_slot(slot, index):
            item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(580000 + index),
                "id": str(580000 + index),
                "name": f"illegal_observed_{slot}",
                "displayName": f"Illegal Observed {slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            if slot in {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}:
                item["armorType"] = "Mail"
            if slot == "head":
                item["armorType"] = "Cloth"
            if slot == "main_hand":
                item["weaponType"] = "One-Handed Mace"
            if slot == "off_hand":
                item["weaponType"] = "Shield"
            return item

        gear_items = [item_for_slot(slot, index) for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-07-08T02:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {"status": "partial", "schemaRevision": "gear-catalog-test", "blockers": []},
                        "2026-07-08T02:01:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed-illegal-shaman-elemental",
                        "shaman",
                        "elemental",
                        "Illegal observed shaman",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "synced",
                        "complete",
                        "observed-illegal-shaman-elemental",
                        [{"sourceKey": "raiderio_observed_profile"}],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "illegal observed template",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 0,
                            "fetchedAt": "2026-07-08T02:00:00+00:00",
                            "profileHash": "",
                            "gearHash": "",
                            "character": {
                                "name": "Illegalshaman",
                                "region": "cn",
                                "realmSlug": "sylvanas",
                            },
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 2,
                                "score": 4200.0,
                            },
                        },
                        "2026-07-08T10:00:00+08:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-illegal-observed",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("shaman", "elemental", compact=True, mode="initial")

        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])

    def test_gear_read_model_ignores_expired_community_gear_templates(self):
        from server.postgres_cache_store import PostgresCacheStore

        def template_row(template_id, name, expires_at):
            return (
                template_id,
                "mage",
                "fire",
                name,
                "simc_preset",
                "SimC preset",
                "",
                "synced",
                "complete",
                template_id,
                [{"type": "simc_preset"}],
                [{"slot": "head", "itemId": "250101", "simcReady": True}],
                "head=template_helm,id=250101,ilevel=289",
                16,
                [],
                "weekly",
                {},
                "2026-07-05T00:00:00+00:00",
                expires_at,
                "scan-fire",
            )

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "partial",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-07-05T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 0, ""),
                    ("websim_gear_sources", 0, ""),
                    ("websim_gear_variants", 0, ""),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 2, "2026-07-05T00:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [],
                "FROM cache.websim_gear_variants": [],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_community_gear_templates": [
                    template_row(
                        "mage_fire_mid1_mage_fire_frostfire",
                        "MID1_Mage_Fire_Frostfire",
                        "2026-06-29T00:00:00+00:00",
                    ),
                    template_row(
                        "mage_fire_mid1_mage_fire_sunfury",
                        "MID1_Mage_Fire_Sunfury",
                        "2099-01-01T00:00:00+00:00",
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "fire", compact=True)

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])
        self.assertIn("expires_at IS NULL OR expires_at > now()", sql)

    def test_gear_read_model_counts_two_hand_main_hand_as_offhand_occupied(self):
        from server.postgres_cache_store import PostgresCacheStore

        community_items = []
        raw_lines = []
        for index, slot in enumerate(
            [
                "head",
                "neck",
                "shoulder",
                "back",
                "chest",
                "wrist",
                "hands",
                "waist",
                "legs",
                "feet",
                "finger1",
                "finger2",
                "trinket1",
                "trinket2",
                "main_hand",
            ],
            start=1,
        ):
            item_id = str(270000 + index)
            item = {
                "slot": slot,
                "itemId": item_id,
                "name": f"Observed {slot}",
                "ilevel": 704,
                "bonus_id": "12345",
                "simcReady": True,
            }
            community_items.append(item)
            raw_lines.append(f"{slot}=observed_{slot},id={item_id},ilevel=704,bonus_id=12345")

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "partial",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 0, ""),
                    ("websim_gear_sources", 0, ""),
                    ("websim_gear_variants", 0, ""),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 1, "2026-06-28T01:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [],
                "FROM cache.websim_gear_variants": [],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "55555555-5555-4555-8555-555555555555",
                        "deathknight",
                        "blood",
                        "Observed Blood Gear",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/us/area-52/Bloodtank",
                        "partial",
                        "partial",
                        "sig-gear-blood",
                        [{"type": "raiderio"}],
                        community_items,
                        "\n".join(raw_lines),
                        15,
                        ["off_hand"],
                        "observed",
                        {
                            "sampleCount": 1,
                            "profileHash": "profile:deathknight:blood:bloodtank",
                            "gearHash": "gear:deathknight:blood:bloodtank",
                        },
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-blood",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("deathknight", "blood", compact=True)

        self.assertEqual(len(payload["communityTemplates"]), 1)
        template = payload["communityTemplates"][0]
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["sourceStatus"], "synced")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertNotIn("off_hand=", template["rawString"])
        self.assertEqual(
            template["occupiedSlots"]["off_hand"],
            {
                "slot": "off_hand",
                "occupiedBy": "main_hand",
                "reason": "spec_two_hand_main_hand",
            },
        )

    def test_gear_read_model_uses_official_item_metadata_for_offhand_occupancy(self):
        from server.postgres_cache_store import PostgresCacheStore

        community_items = []
        raw_lines = []
        for index, slot in enumerate(
            [
                "head",
                "neck",
                "shoulder",
                "back",
                "chest",
                "wrist",
                "hands",
                "waist",
                "legs",
                "feet",
                "finger1",
                "finger2",
                "trinket1",
                "trinket2",
                "main_hand",
            ],
            start=1,
        ):
            item_id = "193723" if slot == "main_hand" else str(280000 + index)
            item = {
                "slot": slot,
                "itemId": item_id,
                "name": f"Observed {slot}",
                "ilevel": 704,
                "bonus_id": "12345",
                "simcReady": True,
            }
            community_items.append(item)
            raw_lines.append(f"{slot}=observed_{slot},id={item_id},ilevel=704,bonus_id=12345")

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "partial",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_sources", 0, ""),
                    ("websim_gear_variants", 0, ""),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 1, "2026-06-28T01:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [],
                "FROM cache.websim_gear_variants": [],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "66666666-6666-4666-8666-666666666666",
                        "druid",
                        "restoration",
                        "Observed Restoration Gear",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/us/area-52/Treehealer",
                        "partial",
                        "partial",
                        "sig-gear-restoration",
                        [{"type": "raiderio"}],
                        community_items,
                        "\n".join(raw_lines),
                        15,
                        ["off_hand"],
                        "observed",
                        {
                            "sampleCount": 1,
                            "profileHash": "profile:druid:restoration:treehealer",
                            "gearHash": "gear:druid:restoration:treehealer",
                        },
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-restoration",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "193723",
                        "Obsidian Goaltending Spire",
                        "main_hand",
                        298,
                        {
                            "name": "Obsidian Goaltending Spire",
                            "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
                            "item_class": {"id": 2, "name": "Weapon"},
                            "item_subclass": {"id": 10, "name": "Staff"},
                            "_metadata": {
                                "source": "Battle.net Game Data API",
                                "locale": "zh_CN",
                            },
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("druid", "restoration", compact=True)

        template = payload["communityTemplates"][0]
        main_hand = next(item for item in template["gearItems"] if item["slot"] == "main_hand")
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(main_hand["weaponType"], "Staff")
        self.assertNotIn("off_hand=", template["rawString"])
        self.assertEqual(
            template["occupiedSlots"]["off_hand"],
            {
                "slot": "off_hand",
                "occupiedBy": "main_hand",
                "reason": "two_hand_main_hand",
            },
        )

    def test_gear_read_model_normalizes_baseline_two_hand_metadata(self):
        from server.postgres_cache_store import PostgresCacheStore

        baseline_items = []
        raw_lines = []
        for index, slot in enumerate(
            [
                "head",
                "neck",
                "shoulder",
                "back",
                "chest",
                "wrist",
                "hands",
                "waist",
                "legs",
                "feet",
                "finger1",
                "finger2",
                "trinket1",
                "trinket2",
                "main_hand",
            ],
            start=1,
        ):
            item_id = "193723" if slot == "main_hand" else str(290000 + index)
            baseline_items.append(
                {
                    "slot": slot,
                    "itemId": item_id,
                    "name": f"Baseline {slot}",
                    "ilevel": 704,
                    "simcReady": True,
                    "sourceType": "simc_preset",
                }
            )
            raw_lines.append(f"{slot}=baseline_{slot},id={item_id},ilevel=704")

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "partial",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_sources", 0, ""),
                    ("websim_gear_variants", 0, ""),
                    ("websim_gear_mod_options", 0, ""),
                    ("websim_community_gear_templates", 1, "2026-06-28T01:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [],
                "FROM cache.websim_gear_variants": [],
                "FROM cache.websim_gear_mod_options": [],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "baseline-priest-shadow",
                        "priest",
                        "shadow",
                        "Shadow Baseline",
                        "simc_preset",
                        "SimC preset",
                        "",
                        "partial",
                        "partial",
                        "sig-baseline-shadow",
                        [{"type": "simc_preset"}],
                        baseline_items,
                        "\n".join(raw_lines),
                        15,
                        ["off_hand"],
                        "baseline",
                        {"templateSlot": "baseline"},
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-baseline",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "193723",
                        "Obsidian Goaltending Spire",
                        "main_hand",
                        298,
                        {
                            "name": "Obsidian Goaltending Spire",
                            "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
                            "item_class": {"id": 2, "name": "Weapon"},
                            "item_subclass": {"id": 10, "name": "Staff"},
                            "_metadata": {
                                "source": "Battle.net Game Data API",
                                "locale": "zh_CN",
                            },
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("priest", "shadow", compact=True)

        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])

    def test_gear_read_model_caches_repeated_payload_when_fingerprint_unchanged(self):
        import server.postgres_cache_store as postgres_cache_store

        if hasattr(postgres_cache_store, "PG_GEAR_PAYLOAD_CACHE"):
            postgres_cache_store.PG_GEAR_PAYLOAD_CACHE.clear()

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "verified",
                            "schemaRevision": "gear-catalog-test",
                            "itemDatabaseRevision": "items-rev",
                            "variantRevision": "variants-rev",
                            "blockers": [],
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "gear_payload_fingerprint": [
                    ("websim_items", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_sources", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_variants", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_gear_mod_options", 1, "2026-06-28T01:00:00+00:00"),
                    ("websim_community_gear_templates", 1, "2026-06-28T01:00:00+00:00"),
                ],
                "FROM cache.websim_gear_sources": [
                    (
                        "11111111-1111-4111-8111-111111111111",
                        "item-a",
                        "dungeon",
                        "source-a",
                        "Encounter A",
                        "1300",
                        "encounter-a",
                        "mythic",
                        "season-pg-1",
                        {"recommendationScore": 88},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "22222222-2222-4222-8222-222222222222",
                        "item-a",
                        "trinket1",
                        "item-a-mythic",
                        "Mythic Item A",
                        "dungeon",
                        "mythic",
                        678,
                        {"ilevel": 678},
                        "verified",
                        [],
                        {"sourceStatus": "verified"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_gear_mod_options": [
                    (
                        "33333333-3333-4333-8333-333333333333",
                        "socket",
                        "socket-a",
                        "Gem A",
                        ["trinket1"],
                        {"gem_id": "213743"},
                        "verified",
                        {"displayLabel": "Gem A"},
                        "2026-06-28T01:00:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "item-a",
                        "Item A",
                        "trinket1",
                        678,
                        {
                            "id": "item-a",
                            "name": "Item A",
                            "slot": "trinket1",
                            "quality": "epic",
                            "iconUrl": "https://render.worldofwarcraft.com/icon-a.jpg",
                            "sourceStatus": "verified",
                        },
                        "verified",
                    )
                ],
            }
        )
        store = postgres_cache_store.PostgresCacheStore(lambda: conn)

        first = store.get_websim_gear("mage", "arcane", compact=True)
        second = store.get_websim_gear("mage", "arcane", compact=True)

        source_build_queries = [
            sql for sql in conn.cursor_instance.statements if "SELECT id, item_id, source_type" in sql
        ]
        variant_build_queries = [
            sql for sql in conn.cursor_instance.statements if "SELECT id, item_id, slot, variant_key" in sql
        ]
        mod_option_build_queries = [
            sql for sql in conn.cursor_instance.statements if "SELECT id, option_type, option_key" in sql
        ]
        item_build_queries = [
            sql for sql in conn.cursor_instance.statements if "SELECT id, name, slot, item_level" in sql
        ]
        self.assertEqual(first["replacementCandidates"], second["replacementCandidates"])
        self.assertEqual(len(source_build_queries), 1)
        self.assertEqual(len(variant_build_queries), 1)
        self.assertEqual(len(mod_option_build_queries), 1)
        self.assertEqual(len(item_build_queries), 1)

    def test_websim_gear_initial_mode_uses_lightweight_template_read(self):
        from server.postgres_cache_store import PostgresCacheStore

        template_payload = {
            "templateSlot": "baseline",
            "templateEvidence": {"recommendationConfidence": "provisional"},
        }
        gear_items = [
            {
                "slot": "head",
                "simcSlot": "head",
                "itemId": "item-head",
                "id": "item-head",
                "name": "Initial Hood",
                "iconUrl": "https://render.worldofwarcraft.com/icon.jpg",
                "simcReady": True,
            }
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "status": "verified",
                            "schemaRevision": "gear-catalog-test",
                            "blockers": [],
                            "checkedAt": "2026-06-28T01:01:00+00:00",
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "season-rec-mage-frost",
                        "mage",
                        "frost",
                        "当前赛季大秘境 AOE 推荐模板",
                        "season_recommendation",
                        "当前赛季大秘境 AOE 推荐模板",
                        "",
                        "synced",
                        "complete",
                        "sig-season-rec",
                        [{"type": "season_recommendation"}],
                        gear_items,
                        "head=initial_hood,id=item-head",
                        16,
                        [],
                        "current-season",
                        template_payload,
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "season-rec-run",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "frost", compact=True, mode="initial")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["gearPayloadMode"], "initial")
        self.assertEqual(payload["communityTemplates"], [])
        self.assertEqual(payload["baselineTemplates"], [])
        self.assertEqual(len(payload["replacementCandidates"]), 16)
        self.assertNotIn("FROM cache.websim_gear_sources", sql)
        self.assertNotIn("FROM cache.websim_gear_variants", sql)
        self.assertNotIn("FROM cache.websim_gear_mod_options", sql)

    def test_talent_read_model_uses_cache_schema_rows(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "checkedAt": "2026-06-28T01:01:00+00:00",
                            "simc": {"build": "12.0.5.67823", "traitEdgeSource": "simc"},
                            "sourceStatus": "verified",
                            "templates": {"total": 1, "verified": 1, "blocked": 0},
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "FROM cache.websim_talents": [
                    (
                        "talent-a",
                        "mage",
                        "frost",
                        "spec",
                        1,
                        2,
                        12345,
                        "Talent A",
                        {"treeType": "spec", "rankEntries": [{"spellId": 12345, "points": 1}]},
                        "Deals frost damage.",
                        "https://render.worldofwarcraft.com/spell-a.jpg",
                        {"source": "simulationcraft"},
                    )
                ],
                "FROM cache.websim_profile_presets": [
                    ("preset-a", "mage", "frost", "Preset A", "mage=Preset", {"source": "simc"}, "2026-06-28T01:00:00+00:00")
                ],
                "FROM cache.websim_community_talent_templates": [
                    (
                        uuid.UUID("44444444-4444-4444-8444-444444444444"),
                        "mage",
                        "frost",
                        "spellslinger",
                        "mythic_plus",
                        "Template A",
                        "M+",
                        "manual_fixture",
                        "Manual Fixture",
                        "https://example.test/template",
                        "talents=abc",
                        "websim:mage:frost",
                        {"selectedNodes": [{"id": "talent-a", "rank": 1}]},
                        12,
                        10,
                        "weekly",
                        "verified",
                        "verified",
                        {"playerId": "mage-a", "heroLabel": "Spellslinger"},
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "sig-a",
                        [{"type": "manual"}],
                        "scan-a",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_talents("mage", "frost", "spellslinger")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["talentStatus"], "verified")
        self.assertEqual(payload["nodes"][0]["id"], "talent-a")
        self.assertEqual(payload["nodes"][0]["descriptionStatus"], "ready")
        self.assertEqual(payload["presets"][0]["id"], "preset-a")
        self.assertEqual(payload["communityTemplates"][0]["id"], "44444444-4444-4444-8444-444444444444")
        self.assertEqual(payload["communityTemplateSync"]["templates"]["verified"], 1)
        self.assertIn("FROM cache.websim_talents", sql)
        self.assertIn("FROM cache.websim_profile_presets", sql)
        self.assertIn("FROM cache.websim_community_talent_templates", sql)
        self.assertIn("expires_at IS NULL OR expires_at > now()", sql)

    def test_replace_community_talent_templates_validates_raiderio_structured_loadout(self):
        from server.postgres_cache_store import PostgresCacheStore

        nodes = [
            {
                "id": "simc-class-91001-mage-frost",
                "treeType": "class",
                "traitId": 91001,
                "spellId": 191001,
                "maxRank": 1,
                "grantedRank": 0,
                "rankEntries": [{"traitId": 91001, "spellId": 191001}],
                "row": 1,
                "col": 1,
            },
            {
                "id": "simc-spec-91002-mage-frost",
                "treeType": "spec",
                "traitId": 91002,
                "spellId": 191002,
                "maxRank": 1,
                "grantedRank": 0,
                "rankEntries": [{"traitId": 91002, "spellId": 191002}],
                "row": 1,
                "col": 2,
            },
            {
                "id": "simc-hero-91003-mage-frost-frostfire",
                "treeType": "hero",
                "heroKey": "frostfire",
                "traitId": 91003,
                "spellId": 191003,
                "maxRank": 1,
                "grantedRank": 0,
                "rankEntries": [{"traitId": 91003, "spellId": 191003}],
                "row": 1,
                "col": 3,
            },
        ]

        class ValidatingStore(PostgresCacheStore):
            def community_talent_authority_index(self, class_key, spec_key):
                by_id = {}
                for node in nodes:
                    for value in (node["traitId"], node["spellId"]):
                        by_id.setdefault(value, []).append(node)
                return by_id

            def get_websim_talents(self, class_key="mage", spec_key="arcane", hero_key=""):
                return {"talentStatus": "verified", "nodes": nodes, "treeSections": []}

        conn = FakeConnection()
        store = ValidatingStore(lambda: conn)

        counts = store.replace_community_talent_templates(
            [
                {
                    "id": "raiderio-rioone-frost",
                    "sourceKey": "raiderio",
                    "sourceStatus": "synced",
                    "sourceName": "Raider.IO",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "frostfire",
                    "scenarioKey": "mythic_plus",
                    "status": "verified",
                    "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                    "playerId": "Rioone",
                    "payload": {
                        "raiderio": {
                            "characterName": "Rioone",
                            "realmSlug": "isillien",
                            "loadoutSpecId": 64,
                            "loadout": [
                                {"traitId": 91001, "rank": 1},
                                {"traitId": 91002, "rank": 1},
                                {"traitId": 91003, "rank": 1},
                            ],
                        }
                    },
                }
            ],
            scan_run_id="scan-raiderio-validation",
        )

        insert_params = next(
            params
            for statement, params in zip(conn.cursor_instance.statements, conn.cursor_instance.params)
            if "INSERT INTO cache.websim_community_talent_templates" in statement
        )
        self.assertEqual(counts["verified"], 1)
        self.assertEqual(insert_params[19], "verified")
        self.assertIn("talentLoadoutParse", insert_params[4])
        self.assertIn('"status": "parsed"', insert_params[4])
        self.assertTrue(insert_params[13].startswith("websim:mage:frost:frostfire:"))
        self.assertIn("simc-class-91001-mage-frost", insert_params[14])
        self.assertIn("UPDATE cache.websim_community_talent_templates", "\n".join(conn.cursor_instance.statements))

    def test_promote_community_talent_inventory_keeps_one_active_template_per_hero_slot(self):
        from server import postgres_cache_store
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import normalize_community_talent_template

        def template(template_id, class_key, spec_key, hero_key, signature, max_key_level, sample_count=1):
            return {
                "id": template_id,
                "classKey": class_key,
                "specKey": spec_key,
                "heroKey": hero_key,
                "scenarioKey": "mythic_plus",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "status": "verified",
                "name": template_id,
                "talentState": {"selectedNodes": [{"id": f"node-{template_id}", "rank": 1}]},
                "sampleCount": sample_count,
                "maxKeyLevel": max_key_level,
                "signature": signature,
                "sourceRefs": [{"sourceKey": "raiderio", "id": template_id}],
                "updatedAt": f"2026-07-03T10:{max_key_level:02d}:00+00:00",
            }

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)
        templates = [
            template("unholy-rider-a", "deathknight", "unholy", "rider_of_the_apocalypse", "sig-rider-a", 24),
            template("unholy-rider-b", "deathknight", "unholy", "rider_of_the_apocalypse", "sig-rider-a", 22),
            template("unholy-rider-c", "deathknight", "unholy", "rider_of_the_apocalypse", "sig-rider-c", 25),
            template("unholy-rider-d", "deathknight", "unholy", "rider_of_the_apocalypse", "sig-rider-d", 21),
            template("blood-deathbringer-a", "deathknight", "blood", "deathbringer", "sig-blood-deathbringer", 20),
        ]

        def normalize_only(_store, source):
            return normalize_community_talent_template(source, source.get("sourceKey"), source.get("sourceStatus"))

        with patch.object(postgres_cache_store, "validate_community_talent_template", side_effect=normalize_only):
            counts = store.replace_community_talent_templates(
                templates,
                scan_run_id="scan-promote",
                include_details=True,
            )

        insert_params = [
            params
            for statement, params in zip(conn.cursor_instance.statements, conn.cursor_instance.params)
            if "INSERT INTO cache.websim_community_talent_templates" in statement
        ]
        inserted_legacy_ids = {payload["legacyId"] for payload in [postgres_cache_store._json_value(params[4], {}) for params in insert_params]}

        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["verified"], 2)
        self.assertEqual(counts["candidateTotal"], 5)
        self.assertEqual(len(counts["validatedTemplates"]), 5)
        self.assertEqual(len(counts["promotedTemplates"]), 2)
        self.assertEqual(len(insert_params), 2)
        self.assertEqual(inserted_legacy_ids, {"unholy_rider_a", "blood_deathbringer_a"})
        self.assertIn("UPDATE cache.websim_community_talent_templates", "\n".join(conn.cursor_instance.statements))
        for params in insert_params:
            payload = postgres_cache_store._json_value(params[4], {})
            self.assertEqual(payload["templateInventoryRole"], "promoted")
            self.assertIn("promotion", payload)

    def test_replace_community_talent_templates_expires_duplicate_active_slot_rows(self):
        from server import postgres_cache_store
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import normalize_community_talent_template

        def normalize_only(_store, source):
            return normalize_community_talent_template(source, source.get("sourceKey"), source.get("sourceStatus"))

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        with patch.object(postgres_cache_store, "validate_community_talent_template", side_effect=normalize_only):
            counts = store.replace_community_talent_templates(
                [
                    {
                        "id": "mage-frost-frostfire",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "sourceStatus": "synced",
                        "status": "verified",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "sampleCount": 2,
                        "maxKeyLevel": 24,
                        "signature": "sig-a",
                        "sourceRefs": [{"sourceKey": "raiderio"}],
                    }
                ],
                scan_run_id="scan-dedupe",
                target_slot_ids=["mage:frost:frostfire"],
            )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("ROW_NUMBER() OVER", sql)
        self.assertIn("PARTITION BY class_key, spec_key, hero_key", sql)
        self.assertIn("active_slot_rank > 1", sql)
        self.assertEqual(counts["duplicateActiveExpired"], 1)

    def test_targeted_talent_refresh_expires_only_slots_with_replacement_winners(self):
        from server import postgres_cache_store
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import normalize_community_talent_template

        def normalize_only(_store, source):
            return normalize_community_talent_template(source, source.get("sourceKey"), source.get("sourceStatus"))

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        with patch.object(postgres_cache_store, "validate_community_talent_template", side_effect=normalize_only):
            store.replace_community_talent_templates(
                [
                    {
                        "id": "mage-frost-frostfire-new",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "sourceStatus": "synced",
                        "status": "verified",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "sampleCount": 2,
                        "maxKeyLevel": 24,
                        "signature": "sig-a",
                        "sourceRefs": [{"sourceKey": "raiderio"}],
                    }
                ],
                scan_run_id="scan-targeted-refresh",
                target_slot_ids=["mage:frost:frostfire", "mage:frost:spellslinger"],
            )

        expire_params = next(
            params
            for statement, params in zip(conn.cursor_instance.statements, conn.cursor_instance.params)
            if "CONCAT(class_key, ':', spec_key, ':', hero_key) = ANY" in statement
            and "NOT (id = ANY" in statement
        )
        self.assertEqual(expire_params[3], ["mage:frost:frostfire"])
        self.assertNotIn("mage:frost:spellslinger", expire_params[3])

    def test_promote_community_talent_inventory_can_represent_six_distinct_dk_hero_slots(self):
        from server.postgres_cache_store import promote_community_talent_template_inventory

        def row(template_id, spec_key, hero_key, max_key_level=20, signature=""):
            return {
                "id": template_id,
                "classKey": "deathknight",
                "specKey": spec_key,
                "heroKey": hero_key,
                "scenarioKey": "mythic_plus",
                "sourceKey": "raiderio",
                "sourceStatus": "synced",
                "status": "verified",
                "payload": {},
                "sourceRefs": [{"sourceKey": "raiderio", "id": template_id}],
                "signature": signature or f"sig-{template_id}",
                "sampleCount": 1,
                "maxKeyLevel": max_key_level,
                "updatedAt": f"2026-07-03T10:{max_key_level:02d}:00+00:00",
            }

        promoted = promote_community_talent_template_inventory(
            [
                row("blood-sanlayn", "blood", "sanlayn", 19),
                row("blood-deathbringer", "blood", "deathbringer", 20),
                row("unholy-rider-a", "unholy", "rider_of_the_apocalypse", 24, signature="sig-rider-majority"),
                row("unholy-rider-b", "unholy", "rider_of_the_apocalypse", 23, signature="sig-rider-majority"),
                row("unholy-rider-c", "unholy", "rider_of_the_apocalypse", 25, signature="sig-rider-minority"),
                row("unholy-sanlayn", "unholy", "sanlayn", 21),
                row("frost-deathbringer", "frost", "deathbringer", 22),
                row("frost-rider", "frost", "rider_of_the_apocalypse", 21),
            ]
        )

        promoted_slots = {
            f"{template['classKey']}:{template['specKey']}:{template['heroKey']}"
            for template in promoted["promotedTemplates"]
        }
        promoted_ids = {template["id"] for template in promoted["promotedTemplates"]}

        self.assertEqual(
            promoted_slots,
            {
                "deathknight:blood:sanlayn",
                "deathknight:blood:deathbringer",
                "deathknight:unholy:rider_of_the_apocalypse",
                "deathknight:unholy:sanlayn",
                "deathknight:frost:deathbringer",
                "deathknight:frost:rider_of_the_apocalypse",
            },
        )
        self.assertEqual(len(promoted["promotedTemplates"]), 6)
        self.assertIn("unholy-rider-a", promoted_ids)
        self.assertNotIn("unholy-rider-c", promoted_ids)

    def test_promote_community_talent_inventory_prefers_wcl_evidence_tier(self):
        from server.postgres_cache_store import promote_community_talent_template_inventory

        def row(template_id, tier, max_key_level, sample_count=1, quality_score=0):
            payload = {
                "rioEvidence": {
                    "maxKeyLevel": max_key_level,
                    "sampleCount": sample_count,
                    "source": "run_detail",
                },
                "wclEvidence": {"tier": tier},
                "evidenceTier": tier,
                "qualityScore": quality_score,
            }
            return {
                "id": template_id,
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "frostfire",
                "scenarioKey": "mythic_plus",
                "sourceKey": "raiderio",
                "sourceStatus": "synced",
                "status": "verified",
                "payload": payload,
                "sourceRefs": [{"sourceKey": "raiderio", "id": template_id}],
                "signature": f"sig-{template_id}",
                "talentState": {"selectedNodes": [{"id": f"node-{template_id}", "rank": 1}]},
                "sampleCount": sample_count,
                "maxKeyLevel": max_key_level,
                "updatedAt": f"2026-07-03T10:{max_key_level:02d}:00+00:00",
            }

        promoted = promote_community_talent_template_inventory(
            [
                row("rio-only-higher-key", "wcl_missing", 25, sample_count=10, quality_score=62),
                row("wcl-supported", "wcl_character_supported", 22, sample_count=4, quality_score=74),
                row("wcl-exact-lower-key", "wcl_exact_template", 20, sample_count=2, quality_score=81),
            ]
        )

        winner = promoted["promotedTemplates"][0]
        self.assertEqual(winner["id"], "wcl-exact-lower-key")
        self.assertEqual(winner["payload"]["evidenceTier"], "wcl_exact_template")
        self.assertEqual(winner["payload"]["wclEvidence"]["tier"], "wcl_exact_template")
        self.assertEqual(winner["payload"]["qualityScore"], 81)
        self.assertIn("WCL exact template", winner["payload"]["promotionReason"])
        self.assertIn("WCL exact template", winner["payload"]["promotion"]["reason"])

    def test_promoted_verified_talent_source_refs_do_not_inherit_blocked_status(self):
        from server.postgres_cache_store import promote_community_talent_template_inventory

        def row(template_id, status, max_key_level):
            return {
                "id": template_id,
                "classKey": "monk",
                "specKey": "brewmaster",
                "heroKey": "master_of_harmony",
                "scenarioKey": "mythic_plus",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "sourceUrl": f"https://raider.io/characters/eu/ravencrest/{template_id}",
                "sourceStatus": "synced",
                "status": status,
                "payload": {"evidenceTier": "wcl_missing"},
                "sourceRefs": [
                    {
                        "id": f"ref-{template_id}",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "sourceUrl": f"https://raider.io/characters/eu/ravencrest/{template_id}",
                        "sourceStatus": "synced",
                        "status": "blocked",
                    }
                ],
                "signature": "shared-signature",
                "talentState": {"selectedNodes": [{"id": "node-shared", "rank": 1}]},
                "sampleCount": 2,
                "maxKeyLevel": max_key_level,
                "updatedAt": f"2026-07-04T01:{max_key_level:02d}:00+00:00",
            }

        promoted = promote_community_talent_template_inventory(
            [
                row("monksea", "verified", 24),
                row("blocked-same-signature", "blocked", 25),
            ]
        )

        winner = promoted["promotedTemplates"][0]
        self.assertEqual(winner["status"], "verified")
        self.assertEqual(
            {ref["status"] for ref in winner["sourceRefs"]},
            {"verified"},
        )
        self.assertEqual([ref["id"] for ref in winner["sourceRefs"]], ["monksea"])

    def test_expire_community_talent_template_sources_marks_active_rows_stale(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        result = store.expire_community_talent_template_sources(
            ["websim_baseline"],
            expired_at="2026-07-03T09:20:00+00:00",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["expired"], 1)
        self.assertIn("UPDATE cache.websim_community_talent_templates", sql)
        self.assertIn("source_key = ANY", sql)
        self.assertEqual(conn.cursor_instance.params[-1][2], ["websim_baseline"])
        self.assertTrue(conn.committed)

    def test_talent_read_model_keeps_pg_nodes_when_season_is_stale(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2000-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "checkedAt": "2026-06-28T01:01:00+00:00",
                            "simc": {"build": "12.0.5.67823", "traitEdgeSource": "simc"},
                            "sourceStatus": "partial",
                            "templates": {"total": 1, "verified": 1, "blocked": 0},
                        },
                        "2026-06-28T01:01:00+00:00",
                    )
                ],
                "FROM cache.websim_talents": [
                    (
                        "talent-a",
                        "mage",
                        "frost",
                        "spec",
                        1,
                        2,
                        12345,
                        "Talent A",
                        {"treeType": "spec", "rankEntries": [{"spellId": 12345, "points": 1}]},
                        "Deals frost damage.",
                        "https://render.worldofwarcraft.com/spell-a.jpg",
                        {"source": "simulationcraft"},
                    )
                ],
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "44444444-4444-4444-8444-444444444444",
                        "mage",
                        "frost",
                        "spellslinger",
                        "mythic_plus",
                        "Template A",
                        "M+",
                        "manual_fixture",
                        "Manual Fixture",
                        "https://example.test/template",
                        "talents=abc",
                        "websim:mage:frost",
                        {"selectedNodes": [{"id": "talent-a", "rank": 1}]},
                        12,
                        10,
                        "weekly",
                        "verified",
                        "verified",
                        {"playerId": "mage-a", "heroLabel": "Spellslinger"},
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "sig-a",
                        [{"type": "manual"}],
                        "scan-a",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_talents("mage", "frost", "spellslinger")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["dataStatus"], "stale")
        self.assertEqual(payload["talentStatus"], "simc")
        self.assertEqual(payload["nodes"][0]["id"], "talent-a")
        self.assertEqual(payload["communityTemplates"][0]["status"], "verified")
        self.assertIn("season cache expired", payload["blockers"])
        self.assertIn("FROM cache.websim_talents", sql)
        self.assertIn("FROM cache.websim_community_talent_templates", sql)

    def test_talent_import_read_model_uses_narrow_template_query(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "44444444-4444-4444-8444-444444444444",
                        "mage",
                        "frost",
                        "spellslinger",
                        "mythic_plus",
                        "Template A",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/template",
                        "CAEAAAAAAAAAAAAAAAAAAAAA",
                        "verified",
                        "verified",
                        12,
                        10,
                        "weekly",
                        "2026-06-30T00:00:00+00:00",
                    )
                ],
                "FROM cache.websim_talents": [("mage", "frost", 110, "2026-06-30T00:00:00+00:00")],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_talent_import("mage", "frost", "spellslinger")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["importCode"], "CAEAAAAAAAAAAAAAAAAAAAAA")
        self.assertEqual(payload["templateId"], "44444444-4444-4444-8444-444444444444")
        self.assertEqual(payload["source"], "community_template")
        self.assertEqual(payload["status"], "verified")
        self.assertIn("AND hero_key = %s", sql)
        self.assertIn(("mage", "frost", "spellslinger"), conn.cursor_instance.params)
        self.assertNotIn("FROM cache.websim_talents", sql)

    def test_pg_websim_talents_returns_pending_community_slot_for_missing_hero(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [{"type": "official"}],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    ({"sourceStatus": "synced", "templates": {"total": 1, "verified": 1, "blocked": 0}}, "2026-06-28T01:01:00+00:00"),
                    ({"sourceStatus": "synced", "templates": {"total": 1, "verified": 1, "blocked": 0}}, "2026-06-28T01:01:00+00:00"),
                ],
                "FROM cache.websim_talents": [
                    (
                        "talent-a",
                        "mage",
                        "frost",
                        "spec",
                        1,
                        2,
                        12345,
                        "Talent A",
                        {"treeType": "spec", "rankEntries": [{"spellId": 12345, "points": 1}]},
                        "Deals frost damage.",
                        "https://render.worldofwarcraft.com/spell-a.jpg",
                        {"source": "simulationcraft"},
                    )
                ],
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "44444444-4444-4444-8444-444444444444",
                        "mage",
                        "frost",
                        "frostfire",
                        "mythic_plus",
                        "Template Frostfire",
                        "M+",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/template",
                        "talents=abc",
                        "websim:mage:frost:frostfire:talent-a:1",
                        {"selectedNodes": [{"id": "talent-a", "rank": 1}]},
                        12,
                        23,
                        "weekly",
                        "verified",
                        "verified",
                        {"playerId": "mage-a", "heroLabel": "霜火"},
                        "2026-06-28T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "sig-a",
                        [{"type": "raiderio"}],
                        "scan-a",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_talents("mage", "frost", "spellslinger")

        self.assertEqual(len(payload["communityTemplates"]), 2)
        self.assertEqual([item["heroKey"] for item in payload["communityTemplates"]], ["spellslinger", "frostfire"])
        self.assertEqual(payload["communityTemplates"][0]["status"], "pending_collection")
        self.assertEqual(payload["communityTemplates"][0]["sourceName"], "社区样本待采集")
        self.assertEqual(payload["communityTemplates"][1]["status"], "verified")
        self.assertEqual(payload["communityTemplateSync"]["activeSpecSlots"]["pendingCollection"], 1)

    def test_admin_gate_records_read_cache_runtime_tables(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_talent_templates": [
                    (
                        "44444444-4444-4444-8444-444444444444",
                        "mage",
                        "frost",
                        "spellslinger",
                        "mythic_plus",
                        "Template A",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/template",
                        "verified",
                        "verified",
                        12,
                        10,
                        "weekly",
                        {"blockers": []},
                        "2026-06-30T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "sig-a",
                        [{"type": "raiderio"}],
                        "scan-a",
                    )
                ],
                "FROM cache.websim_talents GROUP BY": [
                    ("mage", "frost", 110, "2026-06-30T00:00:00+00:00")
                ],
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "55555555-5555-4555-8555-555555555555",
                        "warrior",
                        "arms",
                        "Gear Template A",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/gear-template",
                        "blocked",
                        "blocked",
                        "sig-gear-a",
                        [{"type": "raiderio"}],
                        [{"slot": "head"}],
                        "head=item_a,id=1",
                        1,
                        ["hands"],
                        "weekly",
                        {"blockers": ["missing required gear slots"]},
                        "2026-06-30T00:01:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-gear-a",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "22222222-2222-4222-8222-222222222222",
                        "item-a",
                        "Item A",
                        "head",
                        "Mythic Item A",
                        "dungeon",
                        "mythic",
                        678,
                        {"ilevel": 678},
                        "verified",
                        [],
                        {},
                        {
                            "item_class": {"id": 4, "name": "Armor"},
                            "item_subclass": {"id": 1, "name": "Cloth"},
                        },
                        "Arcane Warden - Magisters' Terrace",
                        "1300",
                        "2026-06-30T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        talents = store.admin_gate_talent_records()
        gear = store.admin_gate_gear_records()

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(talents["communityTalentTemplates"][0]["id"], "44444444-4444-4444-8444-444444444444")
        self.assertEqual(talents["talentTrees"][0]["nodeCount"], 110)
        self.assertEqual(gear["communityGearTemplates"][0]["id"], "55555555-5555-4555-8555-555555555555")
        self.assertEqual(gear["communityGearTemplates"][0]["missingSlots"], ["hands"])
        self.assertEqual(gear["gearVariants"][0]["id"], "22222222-2222-4222-8222-222222222222")
        self.assertEqual(gear["gearVariants"][0]["simcOptions"], {"ilevel": 678})
        self.assertEqual(gear["gearVariants"][0]["sourceLabel"], "Arcane Warden - Magisters' Terrace")
        self.assertEqual(gear["gearVariants"][0]["sourceInstanceId"], "1300")
        self.assertIn("FROM cache.websim_community_talent_templates", sql)
        self.assertIn("FROM cache.websim_talents", sql)
        self.assertIn("FROM cache.websim_community_gear_templates", sql)
        self.assertIn("FROM cache.websim_gear_variants", sql)
        self.assertNotRegex(sql, r"FROM cache\.websim_gear_variants v[\s\S]+LIMIT 500")

    def test_admin_gate_talent_records_omit_expired_community_templates(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_talent_templates": [
                    (
                        "expired-template",
                        "deathknight",
                        "unholy",
                        "rider_of_the_apocalypse",
                        "mythic_plus",
                        "Expired Raider.IO template",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/expired",
                        "synced",
                        "blocked",
                        496,
                        24,
                        "stale window",
                        {"errors": ["unknown structured talent entry"]},
                        "2026-06-28T12:28:54+00:00",
                        "2026-06-29T12:34:15+00:00",
                        "sig-expired",
                        [{"type": "raiderio"}],
                        "scan-expired",
                    ),
                    (
                        "fresh-template",
                        "deathknight",
                        "unholy",
                        "rider_of_the_apocalypse",
                        "mythic_plus",
                        "Fresh Raider.IO template",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/fresh",
                        "synced",
                        "verified",
                        499,
                        24,
                        "fresh window",
                        {},
                        "2026-07-02T21:21:01+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "sig-fresh",
                        [{"type": "raiderio"}],
                        "scan-fresh",
                    ),
                ],
                "FROM cache.websim_talents GROUP BY": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        talents = store.admin_gate_talent_records()

        ids = [item["id"] for item in talents["communityTalentTemplates"]]
        self.assertEqual(ids, ["fresh-template"])

    def test_admin_gate_gear_template_records_do_not_query_variants(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "55555555-5555-4555-8555-555555555555",
                        "warrior",
                        "arms",
                        "Gear Template A",
                        "raiderio",
                        "Raider.IO",
                        "https://example.test/gear-template",
                        "blocked",
                        "blocked",
                        "sig-gear-a",
                        [{"type": "raiderio"}],
                        [{"slot": "head"}],
                        "head=item_a,id=1",
                        1,
                        ["hands"],
                        "weekly",
                        {"blockers": ["missing required gear slots"]},
                        "2026-06-30T00:01:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-gear-a",
                    )
                ],
                "FROM cache.websim_gear_variants": [
                    (
                        "unexpected",
                        "item-a",
                        "Item A",
                        "head",
                        "Mythic Item A",
                        "dungeon",
                        "mythic",
                        678,
                        {},
                        "verified",
                        [],
                        {},
                        {},
                        "",
                        "",
                        "2026-06-30T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.admin_gate_gear_template_records()

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(len(templates["communityGearTemplates"]), 1)
        self.assertEqual(templates["communityGearTemplates"][0]["id"], "55555555-5555-4555-8555-555555555555")
        self.assertIn("expires_at IS NULL OR expires_at > now()", sql)
        self.assertNotIn("FROM cache.websim_gear_variants", sql)

    def test_admin_gate_gear_template_records_dedupes_baseline_display_slot_per_spec(self):
        from server.postgres_cache_store import PostgresCacheStore

        def row(template_id, spec_key, name, source_key, source_name, updated_at="2026-07-05T00:00:00+00:00"):
            return (
                template_id,
                "demonhunter",
                spec_key,
                name,
                source_key,
                source_name,
                "",
                "synced",
                "complete",
                template_id,
                [{"type": source_key}],
                [],
                "head=item_a,id=1",
                16,
                [],
                "daily",
                {},
                updated_at,
                "2099-01-01T00:00:00+00:00",
                "scan-demonhunter",
            )

        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    row(
                        "observed_profile_demonhunter_havoc",
                        "havoc",
                        "Raider.IO observed gear - Havoc",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                    ),
                    row(
                        "observed_profile_demonhunter_devourer",
                        "devourer",
                        "Raider.IO observed gear - Devourer",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                    ),
                    row(
                        "observed_profile_demonhunter_vengeance",
                        "vengeance",
                        "Raider.IO observed gear - Vengeance",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                    ),
                    row(
                        "demonhunter_devourer_mid1_demon_hunter_devourer_annihilator",
                        "devourer",
                        "MID1_Demon_Hunter_Devourer_Annihilator",
                        "simc_preset",
                        "SimC preset",
                        updated_at="2026-07-03T14:39:16+08:00",
                    ),
                    row(
                        "demonhunter_devourer_mid1_demon_hunter_devourer_void_scarred",
                        "devourer",
                        "MID1_Demon_Hunter_Devourer_Void-Scarred",
                        "simc_preset",
                        "SimC preset",
                        updated_at="2026-07-03T14:39:16+08:00",
                    ),
                    row(
                        "demonhunter_havoc_mid1_demon_hunter_havoc_fel_scarred",
                        "havoc",
                        "MID1_Demon_Hunter_Havoc_Fel-Scarred",
                        "simc_preset",
                        "SimC preset",
                    ),
                    row(
                        "demonhunter_vengeance_mid1_demon_hunter_vengeance_annihilator",
                        "vengeance",
                        "MID1_Demon_Hunter_Vengeance_Annihilator",
                        "simc_preset",
                        "SimC preset",
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.admin_gate_gear_template_records()["communityGearTemplates"]

        self.assertEqual(len(templates), 6)
        devourer_baselines = [
            template["id"]
            for template in templates
            if template["specKey"] == "devourer" and template["sourceKey"] == "simc_preset"
        ]
        self.assertEqual(
            devourer_baselines,
            ["demonhunter_devourer_mid1_demon_hunter_devourer_void_scarred"],
        )

    def test_admin_gate_gear_template_records_hydrate_official_item_metadata(self):
        from server.postgres_cache_store import PostgresCacheStore

        official_staff_payload = {
            "name": "Obsidian Goaltending Spire",
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 10, "name": "Staff"},
            "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
            "_metadata": {
                "source": "Battle.net Game Data API",
                "metadataStatus": "verified",
                "locale": "zh_CN",
            },
        }
        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_monk_brewmaster",
                        "monk",
                        "brewmaster",
                        "Observed Brewmaster",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "verified",
                        "complete",
                        "sig-brewmaster",
                        [{"type": "raiderio"}],
                        [
                            {
                                "slot": "main_hand",
                                "itemId": "193723",
                                "sourceType": "observed_profile",
                                "simcReady": True,
                            }
                        ],
                        "main_hand=item_193723,id=193723",
                        16,
                        [],
                        "daily",
                        {},
                        "2026-07-04T23:21:11+00:00",
                        "",
                        "scan-brewmaster",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "193723",
                        "Obsidian Goaltending Spire",
                        "main_hand",
                        298,
                        official_staff_payload,
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.admin_gate_gear_template_records()["communityGearTemplates"]

        self.assertEqual(templates[0]["gearItems"][0]["weaponType"], "Staff")
        self.assertEqual(templates[0]["gearItems"][0]["metadataSource"], "Battle.net Game Data API")
        self.assertEqual(templates[0]["gearItems"][0]["metadataStatus"], "verified")

    def test_admin_gate_gear_template_records_hydrate_official_jewelry_metadata(self):
        from server.postgres_cache_store import PostgresCacheStore

        official_ring_payload = {
            "name": "精工辛多雷指环",
            "item_class": {"id": 4, "name": "护甲"},
            "item_subclass": {"id": 0, "name": "其它"},
            "inventory_type": {"type": "FINGER", "name": "手指"},
            "_metadata": {
                "source": "Battle.net Game Data API",
                "metadataStatus": "verified",
                "locale": "zh_CN",
                "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_ring_80_05.jpg",
            },
        }
        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_mage_frost",
                        "mage",
                        "frost",
                        "Observed Frost Mage",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "verified",
                        "complete",
                        "sig-mage-frost",
                        [{"type": "raiderio"}],
                        [
                            {
                                "slot": "finger1",
                                "itemId": "240949",
                                "name": "masterwork_sindorei_band",
                                "sourceType": "observed_profile",
                                "simcReady": True,
                            }
                        ],
                        "finger1=item_240949,id=240949",
                        16,
                        [],
                        "daily",
                        {},
                        "2026-07-05T05:00:50+08:00",
                        "",
                        "scan-mage-frost",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "240949",
                        "Masterwork Sin'dorei Band",
                        "finger1",
                        285,
                        official_ring_payload,
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        template = store.admin_gate_gear_template_records()["communityGearTemplates"][0]
        item = template["gearItems"][0]

        self.assertEqual(item.get("displayName"), "精工辛多雷指环")
        self.assertEqual(item.get("localizedName"), "精工辛多雷指环")
        self.assertEqual(item.get("iconUrl"), "https://render.worldofwarcraft.com/us/icons/56/inv_ring_80_05.jpg")
        self.assertEqual(item.get("metadataSource"), "Battle.net Game Data API")
        self.assertEqual(item.get("metadataStatus"), "verified")

    def test_admin_gate_gear_template_records_hydrate_verified_pg_item_payload_without_metadata_marker(self):
        from server.postgres_cache_store import PostgresCacheStore

        verified_pg_payload = {
            "displayName": "虚空碎斧",
            "localizedName": "虚空碎斧",
            "inventory_type": {"type": "WEAPON", "name": "单手"},
            "item_class": {"id": 2, "name": "武器"},
            "item_subclass": {"id": 0, "name": "斧"},
            "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_axe_2h_orcraid_d_01.jpg",
            "quality": "史诗",
        }
        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_warrior_fury",
                        "warrior",
                        "fury",
                        "Observed Fury Warrior",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "verified",
                        "complete",
                        "sig-warrior-fury",
                        [{"type": "raiderio"}],
                        [
                            {
                                "slot": "main_hand",
                                "itemId": "250321",
                                "name": "voidsplinter_axe",
                                "sourceType": "observed_profile",
                                "simcReady": True,
                            }
                        ],
                        "main_hand=voidsplinter_axe,id=250321",
                        16,
                        [],
                        "daily",
                        {},
                        "2026-07-05T05:00:50+08:00",
                        "",
                        "scan-warrior-fury",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "250321",
                        "voidsplinter_axe",
                        "main_hand",
                        289,
                        verified_pg_payload,
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        template = store.admin_gate_gear_template_records()["communityGearTemplates"][0]
        item = template["gearItems"][0]

        self.assertEqual(item.get("displayName"), "虚空碎斧")
        self.assertEqual(item.get("localizedName"), "虚空碎斧")
        self.assertEqual(item.get("iconUrl"), "https://render.worldofwarcraft.com/us/icons/56/inv_axe_2h_orcraid_d_01.jpg")
        self.assertEqual(item.get("metadataSource"), "Battle.net Game Data API")
        self.assertEqual(item.get("metadataStatus"), "verified")

    def test_admin_gate_gear_template_records_normalizes_baseline_two_hand_metadata(self):
        from server.postgres_cache_store import PostgresCacheStore

        official_staff_payload = {
            "name": "Obsidian Goaltending Spire",
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 10, "name": "Staff"},
            "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
            "_metadata": {
                "source": "Battle.net Game Data API",
                "metadataStatus": "verified",
                "locale": "zh_CN",
            },
        }
        baseline_items = [
            {"slot": slot, "itemId": "193723" if slot == "main_hand" else str(300000 + index), "simcReady": True}
            for index, slot in enumerate(
                [
                    "head",
                    "neck",
                    "shoulder",
                    "back",
                    "chest",
                    "wrist",
                    "hands",
                    "waist",
                    "legs",
                    "feet",
                    "finger1",
                    "finger2",
                    "trinket1",
                    "trinket2",
                    "main_hand",
                ],
                start=1,
            )
        ]
        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "baseline-priest-shadow",
                        "priest",
                        "shadow",
                        "Shadow Baseline",
                        "simc_preset",
                        "SimC preset",
                        "",
                        "partial",
                        "partial",
                        "sig-baseline-shadow",
                        [{"type": "simc_preset"}],
                        baseline_items,
                        "main_hand=item_193723,id=193723",
                        15,
                        ["off_hand"],
                        "daily",
                        {"templateSlot": "baseline"},
                        "2026-07-04T23:21:11+00:00",
                        "",
                        "scan-baseline",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "193723",
                        "Obsidian Goaltending Spire",
                        "main_hand",
                        298,
                        official_staff_payload,
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        template = store.admin_gate_gear_template_records()["communityGearTemplates"][0]

        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["sourceStatus"], "synced")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["gearItems"][-1]["weaponType"], "Staff")

    def test_admin_gate_queue_summary_ignores_metadata_resolved_baseline_offhand(self):
        from server.postgres_cache_store import PostgresCacheStore

        baseline_items = [
            {"slot": slot, "itemId": "193723" if slot == "main_hand" else str(310000 + index), "simcReady": True}
            for index, slot in enumerate(
                [
                    "head",
                    "neck",
                    "shoulder",
                    "back",
                    "chest",
                    "wrist",
                    "hands",
                    "waist",
                    "legs",
                    "feet",
                    "finger1",
                    "finger2",
                    "trinket1",
                    "trinket2",
                    "main_hand",
                ],
                start=1,
            )
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_talent_templates": [],
                "FROM cache.websim_talents": [],
                "FROM cache.websim_gear_variants": [],
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    (
                        "baseline-priest-shadow",
                        "priest",
                        "shadow",
                        "Shadow Baseline",
                        "simc_preset",
                        "SimC preset",
                        "",
                        "partial",
                        "partial",
                        "sig-baseline-shadow",
                        [{"type": "simc_preset"}],
                        baseline_items,
                        "main_hand=item_193723,id=193723",
                        15,
                        ["off_hand"],
                        "daily",
                        {"templateSlot": "baseline"},
                        "2026-07-04T23:21:11+00:00",
                        "",
                        "scan-baseline",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "193723",
                        "Obsidian Goaltending Spire",
                        "main_hand",
                        298,
                        {
                            "name": "Obsidian Goaltending Spire",
                            "item_class": {"id": 2, "name": "Weapon"},
                            "item_subclass": {"id": 10, "name": "Staff"},
                            "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
                            "_metadata": {"source": "Battle.net Game Data API"},
                        },
                        "verified",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        summary = store.admin_gate_queue_summary()

        self.assertEqual(summary["domainCounts"].get("gear_templates"), None)

    def test_admin_gate_queue_summary_delegates_rows_to_cache_read_model_selector(self):
        from server import pg_cache_read_model_selectors
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_talent_templates": [("talents", "verified", [])],
                "FROM cache.websim_talents": [("mage", "frost", 0)],
                "FROM cache.websim_gear_variants": [("gear", "partial", '["missing gear"]')],
                "SELECT to_regclass": [(None,)],
            }
        )
        store = PostgresCacheStore(lambda: conn)
        expected = {"sentinel": "admin queue summary"}

        with patch.object(
            pg_cache_read_model_selectors,
            "build_admin_gate_queue_summary_read_model",
            return_value=expected,
        ) as selector:
            payload = store.admin_gate_queue_summary()

        self.assertIs(payload, expected)
        selector.assert_called_once_with(
            [
                ("talents", "verified", []),
                ("talents", "blocked", ["talent tree has no nodes"]),
                ("gear", "partial", ["missing gear"]),
            ]
        )

    def test_stat_weight_read_model_uses_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        stat_payload = {
            "classKey": "mage",
            "specKey": "frost",
            "scenarioKey": "mplus_mixed_route",
            "sourceStatus": "verified",
            "expiresAt": "2099-01-01T00:00:00+00:00",
            "staleAt": "2099-01-02T00:00:00+00:00",
            "weights": [{"key": "haste", "value": 1.2}],
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.stat_weight_cache WHERE cache_key": [
                    (stat_payload, "verified", "2026-07-03T00:00:00+00:00"),
                ],
                "FROM cache.stat_weight_cache ORDER BY": [
                    ("verified", "2026-07-03T00:00:00+00:00"),
                    ("blocked", "2026-07-03T00:01:00+00:00"),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        cached = store.get_stat_weight_payload("mage", "frost", "mplus_mixed_route")
        latest = store.latest_stat_weight_run_payload()
        detail = store.enrich_builds_detail_stat_weights(
            {
                "classKey": "mage",
                "specKey": "frost",
                "details": {"statWeights": {"stats": []}},
            }
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(cached["sourceStatus"], "verified")
        self.assertEqual(latest["sourceStatus"], "partial")
        self.assertEqual(latest["acceptedCount"], 1)
        self.assertEqual(latest["blockedCount"], 1)
        self.assertEqual(detail["details"]["statWeights"]["sourceStatus"], "verified")
        self.assertIn("FROM cache.stat_weight_cache", sql)

    def test_asset_read_model_uses_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_asset_registry": [
                    (
                        "asset-item-a",
                        "item",
                        "item-a",
                        "inventory",
                        "icon",
                        "https://render.worldofwarcraft.com/icon-a.jpg",
                        "icon_56",
                        "battle_net",
                        "verified",
                        ["gear"],
                        ["websim"],
                        "Item A",
                        {"id": "asset-item-a", "status": "verified"},
                    )
                ]
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_assets({"entityType": "item", "entityId": "item-a"})

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["assets"][0]["id"], "asset-item-a")
        self.assertEqual(payload["counts"]["byStatus"]["verified"], 1)
        self.assertIn("FROM cache.websim_asset_registry", sql)

    def test_postgres_native_sync_writers_use_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-07-03T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "checkedAt": "2026-07-03T01:01:00+00:00",
                            "simc": {"build": "12.0.7.68275", "traitEdgeSource": "simc"},
                            "sourceStatus": "verified",
                            "templates": {"total": 0, "verified": 0, "blocked": 0},
                        },
                        "2026-07-03T01:01:00+00:00",
                    )
                ],
                "SELECT id, spell_id, payload_json FROM cache.websim_talents": [
                    (
                        "simc-class-91001-mage-frost",
                        191001,
                        {
                            "treeType": "class",
                            "traitId": 91001,
                            "nodeId": 591001,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91001, "spellId": 191001}],
                            "source": "simulationcraft",
                        },
                    ),
                    (
                        "simc-spec-91002-mage-frost",
                        191002,
                        {
                            "treeType": "spec",
                            "traitId": 91002,
                            "nodeId": 591002,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91002, "spellId": 191002}],
                            "source": "simulationcraft",
                        },
                    ),
                    (
                        "simc-hero-91003-mage-frost-frostfire",
                        191003,
                        {
                            "treeType": "hero",
                            "heroKey": "frostfire",
                            "traitId": 91003,
                            "nodeId": 591003,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91003, "spellId": 191003}],
                            "source": "simulationcraft",
                        },
                    ),
                ],
                "FROM cache.websim_talents": [
                    (
                        "simc-class-91001-mage-frost",
                        "mage",
                        "frost",
                        "class:mage",
                        1,
                        1,
                        191001,
                        "Class Talent",
                        {
                            "treeType": "class",
                            "traitId": 91001,
                            "nodeId": 591001,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91001, "spellId": 191001}],
                            "source": "simulationcraft",
                        },
                        "Class talent description.",
                        "https://render.worldofwarcraft.com/class.jpg",
                        {"source": "simulationcraft"},
                    ),
                    (
                        "simc-spec-91002-mage-frost",
                        "mage",
                        "frost",
                        "spec:mage:frost",
                        1,
                        2,
                        191002,
                        "Spec Talent",
                        {
                            "treeType": "spec",
                            "traitId": 91002,
                            "nodeId": 591002,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91002, "spellId": 191002}],
                            "source": "simulationcraft",
                        },
                        "Spec talent description.",
                        "https://render.worldofwarcraft.com/spec.jpg",
                        {"source": "simulationcraft"},
                    ),
                    (
                        "simc-hero-91003-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "hero:frostfire",
                        1,
                        3,
                        191003,
                        "Hero Talent",
                        {
                            "treeType": "hero",
                            "heroKey": "frostfire",
                            "traitId": 91003,
                            "nodeId": 591003,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91003, "spellId": 191003}],
                            "source": "simulationcraft",
                        },
                        "Hero talent description.",
                        "https://render.worldofwarcraft.com/hero.jpg",
                        {"source": "simulationcraft"},
                    ),
                ],
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_community_talent_templates": [],
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("partial", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        store.save_raiderio_payload(
            {
                "sourceStatus": "synced",
                "checkedAt": "2026-07-03T01:00:00+00:00",
                "expiresAt": "2026-07-03T07:00:00+00:00",
            }
        )
        store.save_stat_weight_payload(
            {
                "classKey": "mage",
                "specKey": "frost",
                "scenarioKey": "mplus_mixed_route",
                "sourceStatus": "blocked",
                "checkedAt": "2026-07-03T01:01:00+00:00",
            }
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("INSERT INTO cache.raiderio_cache", sql)
        self.assertIn("ON CONFLICT (cache_key) DO UPDATE", sql)
        self.assertIn("INSERT INTO cache.stat_weight_cache", sql)
        self.assertIn("ON CONFLICT (cache_key) DO UPDATE", sql)
        self.assertTrue(conn.committed)

    def test_postgres_native_community_template_counts_use_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_talent_templates": [
                    ("verified", 2),
                    ("blocked", 1),
                ],
                "FROM cache.websim_community_gear_templates": [
                    ("partial", 3),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        talent_counts = store.community_talent_template_counts()
        gear_counts = store.community_gear_template_counts()

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(talent_counts["total"], 3)
        self.assertEqual(talent_counts["verified"], 2)
        self.assertEqual(talent_counts["blocked"], 1)
        self.assertEqual(gear_counts["total"], 3)
        self.assertEqual(gear_counts["partial"], 3)
        self.assertIn("FROM cache.websim_community_talent_templates", sql)
        self.assertIn("FROM cache.websim_community_gear_templates", sql)

    def test_postgres_native_community_template_writers_use_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_season_state": [
                    (
                        "season-pg",
                        "Season PG",
                        "season-pg-1",
                        "zh_CN",
                        "verified",
                        "2026-07-03T01:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        [],
                        {"seasonRevision": "season-pg-1", "raids": []},
                    )
                ],
                "FROM cache.websim_season_dungeons": [],
                "FROM cache.websim_sync_state": [
                    (
                        {
                            "checkedAt": "2026-07-03T01:01:00+00:00",
                            "simc": {"build": "12.0.7.68275", "traitEdgeSource": "simc"},
                            "sourceStatus": "verified",
                            "templates": {"total": 0, "verified": 0, "blocked": 0},
                        },
                        "2026-07-03T01:01:00+00:00",
                    )
                ],
                "SELECT id, spell_id, payload_json FROM cache.websim_talents": [
                    (
                        "simc-class-91001-mage-frost",
                        191001,
                        {
                            "treeType": "class",
                            "traitId": 91001,
                            "nodeId": 591001,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91001, "spellId": 191001}],
                            "source": "simulationcraft",
                        },
                    ),
                    (
                        "simc-spec-91002-mage-frost",
                        191002,
                        {
                            "treeType": "spec",
                            "traitId": 91002,
                            "nodeId": 591002,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91002, "spellId": 191002}],
                            "source": "simulationcraft",
                        },
                    ),
                    (
                        "simc-hero-91003-mage-frost-frostfire",
                        191003,
                        {
                            "treeType": "hero",
                            "heroKey": "frostfire",
                            "traitId": 91003,
                            "nodeId": 591003,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91003, "spellId": 191003}],
                            "source": "simulationcraft",
                        },
                    ),
                ],
                "FROM cache.websim_talents": [
                    (
                        "simc-class-91001-mage-frost",
                        "mage",
                        "frost",
                        "class:mage",
                        1,
                        1,
                        191001,
                        "Class Talent",
                        {
                            "treeType": "class",
                            "traitId": 91001,
                            "nodeId": 591001,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91001, "spellId": 191001}],
                            "source": "simulationcraft",
                        },
                        "Class talent description.",
                        "https://render.worldofwarcraft.com/class.jpg",
                        {"source": "simulationcraft"},
                    ),
                    (
                        "simc-spec-91002-mage-frost",
                        "mage",
                        "frost",
                        "spec:mage:frost",
                        1,
                        2,
                        191002,
                        "Spec Talent",
                        {
                            "treeType": "spec",
                            "traitId": 91002,
                            "nodeId": 591002,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91002, "spellId": 191002}],
                            "source": "simulationcraft",
                        },
                        "Spec talent description.",
                        "https://render.worldofwarcraft.com/spec.jpg",
                        {"source": "simulationcraft"},
                    ),
                    (
                        "simc-hero-91003-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "hero:frostfire",
                        1,
                        3,
                        191003,
                        "Hero Talent",
                        {
                            "treeType": "hero",
                            "heroKey": "frostfire",
                            "traitId": 91003,
                            "nodeId": 591003,
                            "specId": 64,
                            "maxRank": 1,
                            "grantedRank": 0,
                            "rankEntries": [{"traitId": 91003, "spellId": 191003}],
                            "source": "simulationcraft",
                        },
                        "Hero talent description.",
                        "https://render.worldofwarcraft.com/hero.jpg",
                        {"source": "simulationcraft"},
                    ),
                ],
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_community_talent_templates": [],
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("partial", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        talent_counts = store.replace_community_talent_templates(
            [
                {
                    "id": "template-a",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "frostfire",
                    "scenarioKey": "mythic_plus",
                    "name": "Template A",
                    "flowLabel": "主流",
                    "sourceKey": "raiderio",
                    "sourceName": "Raider.IO",
                    "sourceUrl": "https://raider.io/template-a",
                    "rawImportCode": "CAE_FAKE",
                    "websimExportCode": "",
                    "sampleCount": 3,
                    "maxKeyLevel": 12,
                    "analysisWindow": "test window",
                    "sourceStatus": "verified",
                    "status": "verified",
                    "payload": {
                        "playerId": "Mage A",
                        "raiderio": {
                            "characterName": "Mage A",
                            "realmSlug": "test-realm",
                            "loadoutSpecId": 64,
                            "loadout": [
                                {"traitId": 91001, "rank": 1},
                                {"traitId": 91002, "rank": 1},
                                {"traitId": 91003, "rank": 1},
                            ],
                        },
                    },
                    "signature": "sig-template-a",
                    "sourceRefs": [{"sourceKey": "raiderio"}],
                    "scanRunId": "scan-a",
                },
                {
                    "id": "template-blocked",
                    "classKey": "mage",
                    "specKey": "frost",
                    "sourceKey": "warcraftlogs",
                    "sourceStatus": "blocked",
                    "status": "blocked",
                    "payload": {"errors": ["missing talent state"]},
                },
            ],
            scan_run_id="scan-a",
        )
        gear_counts = store.replace_community_gear_templates(
            [
                {
                    "id": "gear-template-a",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "Gear Template A",
                    "sourceKey": "default_template",
                    "sourceName": "默认模板",
                    "sourceStatus": "verified",
                    "status": "complete",
                    "signature": "sig-gear-a",
                    "sourceRefs": [{"sourceKey": "default_template"}],
                    "gearItems": [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    "rawString": "head=item",
                    "readySlotCount": 1,
                    "missingSlots": [],
                    "analysisWindow": "gear window",
                    "payload": {"scenarioKey": "mplus_mixed_route"},
                    "scanRunId": "scan-a",
                }
            ],
            scan_run_id="scan-a",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(talent_counts["verified"], 1)
        self.assertEqual(talent_counts["blocked"], 0)
        self.assertEqual(talent_counts["candidateBlocked"], 1)
        self.assertEqual(gear_counts["partial"], 1)
        self.assertIn("INSERT INTO cache.websim_community_talent_templates", sql)
        self.assertIn("UPDATE cache.websim_community_talent_templates", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertIn("INSERT INTO cache.websim_community_gear_templates", sql)
        self.assertTrue(conn.committed)

    def test_replace_community_gear_templates_preserves_complete_winner_from_partial_downgrade(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("complete", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_community_gear_templates(
            [
                {
                    "id": "observed-profile-mage-frost",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "Partial observed gear",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceName": "Raider.IO observed gear",
                    "sourceStatus": "partial",
                    "status": "partial",
                    "signature": "sig-partial",
                    "sourceRefs": [{"sourceKey": "raiderio"}],
                    "gearItems": [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    "rawString": "head=item,id=190001",
                    "readySlotCount": 1,
                    "missingSlots": ["neck"],
                    "analysisWindow": "partial sample",
                    "payload": {"scenarioKey": "mplus_mixed_route"},
                    "scanRunId": "scan-partial",
                }
            ],
            scan_run_id="scan-partial",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["verified"], 1)
        self.assertEqual(counts["partial"], 0)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertIn("WHERE NOT ( cache.websim_community_gear_templates.status = 'complete'", sql)
        self.assertIn("EXCLUDED.status <> 'complete'", sql)

    def test_replace_community_gear_templates_corrects_invalid_stored_complete_winner(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "WHERE id = ANY": [
                    (
                        "observed-profile-mage-frost",
                        "mage",
                        "frost",
                        [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    )
                ],
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("partial", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_community_gear_templates(
            [
                {
                    "id": "observed-profile-mage-frost",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "Audited partial observed gear",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceName": "Raider.IO observed gear",
                    "sourceStatus": "partial",
                    "status": "partial",
                    "signature": "sig-audited-partial",
                    "sourceRefs": [{"sourceKey": "raiderio"}],
                    "gearItems": [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    "rawString": "head=item,id=190001",
                    "readySlotCount": 1,
                    "missingSlots": ["neck"],
                    "analysisWindow": "audited partial sample",
                    "payload": {"scenarioKey": "mplus_mixed_route"},
                    "scanRunId": "scan-audited-partial",
                }
            ],
            scan_run_id="scan-audited-partial",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["partial"], 1)
        self.assertIn("SELECT id, class_key, spec_key, source_key, source_url", sql)
        self.assertIn("cache.websim_community_gear_templates.id = ANY", sql)
        self.assertTrue(
            any(
                "observed-profile-mage-frost" in value
                for params in conn.cursor_instance.params
                for value in params
                if isinstance(value, list)
            )
        )

    def test_replace_community_gear_templates_corrects_source_less_elemental_complete_winner(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "WHERE id = ANY": [
                    (
                        "observed_profile_shaman_elemental",
                        "shaman",
                        "elemental",
                        "raiderio_observed_profile",
                        "",
                        "synced",
                        "complete",
                        16,
                        [],
                        [
                            {"slot": "main_hand", "itemId": "237849", "weaponType": "Two-Handed Mace", "simcReady": True},
                            {"slot": "off_hand", "itemId": "245769", "weaponType": "Held In Off-hand", "simcReady": True},
                        ],
                        {},
                    )
                ],
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("partial", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_community_gear_templates(
            [
                {
                    "id": "observed_profile_shaman_elemental",
                    "classKey": "shaman",
                    "specKey": "elemental",
                    "name": "Raider.IO observed gear",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceName": "Raider.IO observed gear",
                    "sourceUrl": "https://raider.io/characters/us/stormrage/Kiliwynn",
                    "sourceStatus": "partial",
                    "status": "partial",
                    "signature": "sig-source-backed-partial",
                    "sourceRefs": [
                        {
                            "sourceKey": "raiderio_observed_profile",
                            "sourceUrl": "https://raider.io/characters/us/stormrage/Kiliwynn",
                        }
                    ],
                    "gearItems": [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    "rawString": "head=item,id=190001",
                    "readySlotCount": 1,
                    "missingSlots": ["neck"],
                    "analysisWindow": "source-backed partial observed",
                    "payload": {
                        "sampleCount": 1,
                        "gearHash": "gear:shaman:elemental:source-backed",
                    },
                    "scanRunId": "scan-source-backed-partial",
                }
            ],
            scan_run_id="scan-source-backed-partial",
        )

        self.assertEqual(counts["partial"], 1)
        self.assertTrue(
            any(
                "observed_profile_shaman_elemental" in value
                for params in conn.cursor_instance.params
                for value in params
                if isinstance(value, list)
            )
        )

    def test_replace_community_gear_templates_reconciles_stale_complete_without_candidate(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "WHERE source_key = ANY": [
                    (
                        "observed-profile-shaman-elemental",
                        "shaman",
                        "elemental",
                        "raiderio_observed_profile",
                        "",
                        "synced",
                        "complete",
                        16,
                        [],
                        [{"slot": "head", "itemId": "190001", "simcReady": True}],
                        {"readySlotCount": 16, "missingSlots": []},
                    )
                ],
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("partial", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_community_gear_templates(
            [
                {
                    "id": "observed-profile-mage-arcane",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "name": "Complete observed gear",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceName": "Raider.IO observed gear",
                    "sourceStatus": "synced",
                    "status": "complete",
                    "signature": "sig-complete",
                    "sourceRefs": [{"sourceKey": "raiderio"}],
                    "gearItems": [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    "rawString": "head=item,id=190001",
                    "readySlotCount": 16,
                    "missingSlots": [],
                    "analysisWindow": "complete sample",
                    "payload": {"scenarioKey": "mplus_mixed_route"},
                    "scanRunId": "scan-reconcile",
                }
            ],
            scan_run_id="scan-reconcile",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["partial"], 1)
        self.assertIn("WHERE source_key = ANY", sql)
        self.assertIn("UPDATE cache.websim_community_gear_templates", sql)
        self.assertIn("observed-profile-shaman-elemental", conn.cursor_instance.params[-2])

    def test_reconcile_community_gear_slot_coverage_applies_legality_gate(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "itemId": "900001" if slot == "main_hand" else "900002" if slot == "off_hand" else str(910000 + index),
                "name": f"Observed {slot}",
                "itemLevel": 707,
                "simcReady": True,
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "WHERE source_key = ANY": [
                    (
                        "observed_profile_hunter_survival",
                        "hunter",
                        "survival",
                        "raiderio_observed_profile",
                        "",
                        "synced",
                        "complete",
                        16,
                        [],
                        gear_items,
                        {"sampleCount": 1},
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "900001",
                        "Main Dagger",
                        "main_hand",
                        707,
                        {
                            "id": "900001",
                            "name": "Main Dagger",
                            "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                            "item_class": {"id": 2, "name": "Weapon"},
                            "item_subclass": {"id": 15, "name": "Dagger"},
                        },
                        "verified",
                    ),
                    (
                        "900002",
                        "Offhand Shield",
                        "off_hand",
                        707,
                        {
                            "id": "900002",
                            "name": "Offhand Shield",
                            "inventory_type": {"type": "SHIELD", "name": "Shield"},
                            "item_class": {"id": 4, "name": "Armor"},
                            "item_subclass": {"id": 6, "name": "Shield"},
                        },
                        "verified",
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        reconciled = store._reconcile_community_gear_slot_coverage(
            conn.cursor(),
            {"raiderio_observed_profile"},
            scan_run_id="scan-legality",
        )

        self.assertEqual(reconciled, 1)
        update_params = next(
            params
            for statement, params in zip(conn.cursor_instance.statements, conn.cursor_instance.params)
            if "UPDATE cache.websim_community_gear_templates" in statement
        )
        self.assertEqual(update_params[0], "partial")
        self.assertEqual(update_params[1], "partial")
        self.assertEqual(update_params[2], 15)
        self.assertIn("off_hand", str(update_params[3]))
        self.assertIn("off_hand gear incompatible with hunter/survival weapon rule: Shield", str(update_params[4]))

    def test_reconcile_community_gear_slot_coverage_allows_raiderio_snapshot_after_weapon_rule_update(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "itemId": "258412" if slot == "main_hand" else "249284" if slot == "off_hand" else str(920000 + index),
                "name": f"Observed {slot}",
                "itemLevel": 707,
                "simcReady": True,
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        authoritative_payload = {
            "sourceUrl": "https://raider.io/characters/cn/the-great-sea/哈哈丶帅猎猎",
            "sampleCount": 1,
            "profileHash": "profile:hunter:survival:real",
            "gearHash": "gear:hunter:survival:real",
            "fetchedAt": "2026-07-08T10:00:00+00:00",
            "character": {
                "name": "哈哈丶帅猎猎",
                "region": "cn",
                "realmSlug": "the-great-sea",
            },
        }
        conn = FakeConnection(
            rowsets={
                "WHERE source_key = ANY": [
                    (
                        "observed_profile_hunter_survival",
                        "hunter",
                        "survival",
                        "raiderio_observed_profile",
                        "https://raider.io/characters/cn/the-great-sea/哈哈丶帅猎猎",
                        "synced",
                        "complete",
                        16,
                        [],
                        gear_items,
                        authoritative_payload,
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "258412",
                        "Observed Crossbow",
                        "main_hand",
                        707,
                        {
                            "id": "258412",
                            "name": "Observed Crossbow",
                            "inventory_type": {"type": "RANGED", "name": "Ranged"},
                            "item_class": {"id": 2, "name": "Weapon"},
                            "item_subclass": {"id": 18, "name": "Crossbow"},
                        },
                        "verified",
                    ),
                    (
                        "249284",
                        "Observed Dagger",
                        "off_hand",
                        707,
                        {
                            "id": "249284",
                            "name": "Observed Dagger",
                            "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                            "item_class": {"id": 2, "name": "Weapon"},
                            "item_subclass": {"id": 15, "name": "Dagger"},
                        },
                        "verified",
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        reconciled = store._reconcile_community_gear_slot_coverage(
            conn.cursor(),
            {"raiderio_observed_profile"},
            scan_run_id="scan-legality",
        )

        self.assertEqual(reconciled, 0)
        self.assertFalse(
            any("UPDATE cache.websim_community_gear_templates" in statement for statement in conn.cursor_instance.statements)
        )

    def test_replace_community_gear_templates_promotes_stale_partial_when_current_coverage_is_complete(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        complete_gear = [
            {"slot": slot, "itemId": f"19{index:04d}", "simcReady": True}
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "WHERE source_key = ANY": [
                    (
                        "observed-profile-druid-restoration",
                        "druid",
                        "restoration",
                        "raiderio_observed_profile",
                        "",
                        "partial",
                        "partial",
                        15,
                        ["off_hand"],
                        complete_gear,
                        {"readySlotCount": 15, "missingSlots": ["off_hand"]},
                    )
                ],
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("complete", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_community_gear_templates(
            [
                {
                    "id": "observed-profile-mage-arcane",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "name": "Complete observed gear",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceName": "Raider.IO observed gear",
                    "sourceStatus": "synced",
                    "status": "complete",
                    "signature": "sig-complete",
                    "sourceRefs": [{"sourceKey": "raiderio"}],
                    "gearItems": complete_gear,
                    "rawString": "head=item,id=190001",
                    "readySlotCount": 16,
                    "missingSlots": [],
                    "analysisWindow": "complete sample",
                    "payload": {"scenarioKey": "mplus_mixed_route"},
                    "scanRunId": "scan-reconcile",
                }
            ],
            scan_run_id="scan-reconcile",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["verified"], 1)
        self.assertIn("UPDATE cache.websim_community_gear_templates", sql)
        self.assertIn("status IN ('complete', 'partial')", sql)
        self.assertTrue(
            any(
                params[0] == "synced"
                and params[1] == "complete"
                and params[-1] == "observed-profile-druid-restoration"
                for params in conn.cursor_instance.params
                if len(params) >= 2
            )
        )

    def test_replace_community_gear_templates_preserves_partial_with_more_ready_slots(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates WHERE expires_at": [("partial", 1)],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_community_gear_templates(
            [
                {
                    "id": "observed-profile-mage-frost",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "Weaker partial observed gear",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceName": "Raider.IO observed gear",
                    "sourceStatus": "partial",
                    "status": "partial",
                    "signature": "sig-weaker-partial",
                    "sourceRefs": [{"sourceKey": "raiderio"}],
                    "gearItems": [{"slot": "head", "itemId": "190001", "simcReady": True}],
                    "rawString": "head=item,id=190001",
                    "readySlotCount": 1,
                    "missingSlots": ["neck", "shoulder"],
                    "analysisWindow": "weaker partial sample",
                    "payload": {"scenarioKey": "mplus_mixed_route"},
                    "scanRunId": "scan-weaker-partial",
                }
            ],
            scan_run_id="scan-weaker-partial",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["partial"], 1)
        self.assertIn("cache.websim_community_gear_templates.ready_slot_count > EXCLUDED.ready_slot_count", sql)

    def test_restore_community_template_availability_keeps_repair_to_current_winners(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        result = store.restore_community_template_availability(
            availability_expires_at="2026-07-20T00:00:00+00:00",
            checked_at="2026-07-06T00:00:00+00:00",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["talentRestored"], 1)
        self.assertEqual(result["gearRestored"], 1)
        self.assertIn("PARTITION BY class_key, spec_key, hero_key", sql)
        self.assertIn("PARTITION BY class_key, spec_key", sql)
        self.assertIn("status = 'verified'", sql)
        self.assertIn("status = 'complete'", sql)
        self.assertIn("source_key <> ALL", sql)
        self.assertIn("communityTemplateFreshness", sql)
        gear_blocked_sources = conn.cursor_instance.params[1][0]
        self.assertIn("source_reference", gear_blocked_sources)
        self.assertIn("manual_fixture", gear_blocked_sources)
        self.assertIn("fallback", gear_blocked_sources)
        freshness_payloads = [
            param
            for params in conn.cursor_instance.params
            for param in params
            if isinstance(param, str) and "availability_repair_after_ttl_split" in param
        ]
        self.assertEqual(len(freshness_payloads), 2)

    def test_community_gear_template_live_health_summary_reads_current_rows(self):
        from server.postgres_cache_store import PostgresCacheStore

        def row(template_id, class_key, spec_key, source_key, status, ready, missing, scan_run_id, expires_at=None, source_url="", payload=None):
            return (
                template_id,
                class_key,
                spec_key,
                template_id,
                source_key,
                source_key,
                source_url,
                "synced" if status == "complete" else "partial",
                status,
                template_id,
                [],
                [{"slot": "head", "itemId": "190001", "simcReady": True}],
                "head=item,id=190001",
                ready,
                missing,
                "test window",
                payload or {},
                "2026-07-05T00:00:00+00:00",
                expires_at,
                scan_run_id,
            )

        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    row(
                        "observed-mage-fire",
                        "mage",
                        "fire",
                        "raiderio_observed_profile",
                        "complete",
                        16,
                        [],
                        "scan-live",
                        source_url="https://raider.io/characters/cn/realm/Magefire",
                        payload={
                            "sampleCount": 1,
                            "profileHash": "sha256:observed-mage-fire",
                            "gearHash": "sha256:observed-mage-fire-gear",
                            "templateEvidence": {
                                "scenarioResults": {
                                    "mplus_aoe": {"dps": 123456, "iterations": 10000}
                                }
                            },
                        },
                    ),
                    row("observed-monk-windwalker", "monk", "windwalker", "raiderio_observed_profile", "partial", 15, ["trinket2"], "scan-live"),
                    row(
                        "recommended-bis-mage-fire",
                        "mage",
                        "fire",
                        "recommended_bis",
                        "complete",
                        16,
                        [],
                        "scan-live",
                        payload={
                            "templateType": "recommended_bis",
                            "templateEvidence": {
                                "schemaRevision": "recommended-bis-v1",
                                "status": "projected_bis",
                                "optimizerVersion": "gear-bis-optimizer-v1",
                            },
                        },
                    ),
                    row(
                        "season-mage-fire",
                        "mage",
                        "fire",
                        "season_recommendation",
                        "complete",
                        16,
                        [],
                        "scan-live",
                        payload={
                            "templateSlot": "baseline",
                            "templateEvidence": {
                                "recommendationConfidence": "provisional",
                            },
                        },
                    ),
                    row("baseline-mage-fire", "mage", "fire", "simc_preset", "complete", 16, [], "scan-live"),
                    row("baseline-monk-windwalker", "monk", "windwalker", "simc_preset", "partial", 10, ["trinket2"], "scan-live"),
                    row("expired-baseline-monk-windwalker", "monk", "windwalker", "simc_preset", "partial", 1, ["head"], "scan-expired", "2020-01-01T00:00:00+00:00"),
                ],
                "FROM cache.websim_sync_state": {
                    ("recommended_bis_v1_guard",): [
                        (
                            {
                                "schemaRevision": "recommended-bis-v1-guard-state-v1",
                                "status": "partial",
                                "guardMode": "readiness_only",
                                "expectedSpecCount": 2,
                                "optimizerRequiredSpecCount": 2,
                                "fullOptimizerRunRequiredSpecCount": 2,
                                "lastGuardCheckAt": "2026-07-07T13:00:00+00:00",
                            },
                            "2026-07-07T13:00:00+00:00",
                        )
                    ],
                    ("community_best_v2_guard",): [
                        (
                            {
                                "schemaRevision": "community-best-v2-guard-state-v1",
                                "status": "partial",
                                "guardMode": "readiness_only",
                                "expectedSpecCount": 2,
                                "coveredSpecCount": 1,
                                "simcReplayRequiredSpecCount": 1,
                                "lastGuardCheckAt": "2026-07-07T13:05:00+00:00",
                            },
                            "2026-07-07T13:05:00+00:00",
                        )
                    ],
                },
            }
        )
        store = PostgresCacheStore(lambda: conn)

        with patch("server.postgres_cache_store.expected_spec_pairs", return_value=["mage:fire", "monk:windwalker"]):
            summary = store.community_gear_template_live_health_summary()

        self.assertEqual(summary["templates"], {"total": 5, "verified": 3, "partial": 2, "blocked": 0})
        self.assertEqual(summary["preflight"]["status"], "partial")
        self.assertEqual(summary["communityImportTemplates"]["status"], "partial")
        self.assertEqual(summary["communityImportTemplates"]["totalTemplateSlotCount"], 4)
        self.assertEqual(summary["communityImportTemplates"]["coveredTemplateSlotCount"], 3)
        self.assertEqual(summary["communityImportTemplates"]["missingTemplateSlotCount"], 1)
        self.assertEqual(summary["communityImportTemplates"]["realCommunityCompleteSpecCount"], 1)
        self.assertEqual(summary["communityImportTemplates"]["baselineAvailableSpecCount"], 2)
        self.assertIn("80/80", summary["communityImportTemplates"]["countingPolicy"])
        self.assertEqual(summary["realCommunityTemplates"]["coveredSpecCount"], 1)
        self.assertEqual(summary["realCommunityTemplates"]["partialSpecCount"], 0)
        self.assertEqual(summary["baselineTemplates"]["availableSpecCount"], 2)
        self.assertEqual(summary["seasonRecommendation"]["completeSpecCount"], 1)
        self.assertEqual(summary["seasonRecommendation"]["provisionalSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["communityObserved"]["verifiedSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["communityObserved"]["blockedSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["legacyFallback"]["totalSpecCount"], 2)
        self.assertEqual(summary["templateChains"]["legacyFallback"]["starterBaselineSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["recommendedBis"]["totalSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["recommendedBis"]["projectedSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["recommendedBis"]["expectedSpecCount"], 2)
        self.assertEqual(summary["templateChains"]["recommendedBis"]["blockedSpecCount"], 1)
        self.assertEqual(summary["templateChains"]["recommendedBis"]["optimizerRequiredSpecCount"], 2)
        self.assertEqual(summary["templateChains"]["recommendedBis"]["fullOptimizerRunRequiredSpecCount"], 2)
        self.assertEqual(
            summary["templateChains"]["recommendedBis"]["missingSpecs"],
            ["monk:windwalker"],
        )
        self.assertEqual(summary["recommendedBisGuard"]["schemaRevision"], "recommended-bis-v1-guard-state-v1")
        self.assertEqual(summary["recommendedBisGuard"]["guardMode"], "readiness_only")
        self.assertEqual(summary["recommendedBisGuard"]["optimizerRequiredSpecCount"], 2)
        self.assertEqual(summary["communityObservedGuard"]["schemaRevision"], "community-best-v2-guard-state-v1")
        self.assertEqual(summary["communityObservedGuard"]["guardMode"], "readiness_only")
        self.assertEqual(summary["communityObservedGuard"]["simcReplayRequiredSpecCount"], 1)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["totalSlotCount"], 32)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["readySlotCount"], 16)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["missingSlotCount"], 16)
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        self.assertEqual(
            summary["preflight"]["canonicalSlotMatrix"]["missingBySlot"],
            {slot: 1 for slot in CANONICAL_GEAR_SLOTS},
        )

    def test_postgres_native_observed_and_crafted_backfill_writers_use_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Observed Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    }
                ],
            },
            mode="test",
        )
        crafted = store.backfill_crafted_gear_from_seed(
            [
                {
                    "itemId": "260100",
                    "name": "Crafted Sword",
                    "slot": "main_hand",
                    "itemLevel": 285,
                    "crafted_stats": "32/49",
                }
            ],
            mode="test",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(crafted["variantCount"], 1)
        self.assertIn("INSERT INTO cache.websim_items", sql)
        self.assertIn("INSERT INTO cache.websim_gear_sources", sql)
        self.assertIn("INSERT INTO cache.websim_gear_variants", sql)
        self.assertIn("observed_profile", params)
        self.assertIn("crafted", params)
        self.assertTrue(conn.committed)

    def test_observed_backfill_variants_are_scoped_to_profile_identity(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "region": "cn",
                        "realmSlug": "realm",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "249343",
                                "name": "Shared Trinket",
                                "slot": "trinket_1",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    },
                    {
                        "name": "Mage B",
                        "profileUrl": "https://raider.io/characters/us/realm/MageB",
                        "region": "us",
                        "realmSlug": "realm",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "249343",
                                "name": "Shared Trinket",
                                "slot": "trinket_1",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    },
                ],
            },
            mode="test",
        )

        variant_params = [
            params
            for statement, params in zip(conn.cursor_instance.statements, conn.cursor_instance.params)
            if "INSERT INTO cache.websim_gear_variants" in statement
        ]

        self.assertEqual(observed["variantCount"], 2)
        self.assertEqual(len(variant_params), 2)
        self.assertNotEqual(variant_params[0][2], variant_params[1][2])
        self.assertIn("observed-profile", variant_params[0][2])
        self.assertIn("observed-profile", variant_params[1][2])

    def test_observed_backfill_preserves_official_item_metadata_payload(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Warlock A",
                        "profileUrl": "https://raider.io/characters/us/realm/WarlockA",
                        "classKey": "warlock",
                        "specKey": "destruction",
                        "gear": [
                            {
                                "itemId": "245770",
                                "name": "Aln'hara Cane",
                                "slot": "main_hand",
                                "ilevel": 295,
                                "bonus_id": "12214/13655",
                            }
                        ],
                    }
                ],
            },
            mode="test",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("INSERT INTO cache.websim_items", sql)
        self.assertIn("cache.websim_items.payload_json #>> '{_metadata,source}'", sql)
        self.assertIn("Battle.net Game Data API", sql)
        self.assertIn("cache.websim_items.payload_json ? 'inventory_type'", sql)
        self.assertIn("cache.websim_items.payload_json ? 'item_class'", sql)
        self.assertIn("COALESCE(cache.websim_items.payload_json #>> '{_metadata,iconUrl}', cache.websim_items.payload_json->>'iconUrl', '') <> ''", sql)
        self.assertIn("THEN cache.websim_items.payload_json", sql)
        self.assertIn("ELSE EXCLUDED.payload_json", sql)

    def test_save_websim_item_metadata_writes_official_payload_to_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        saved = store.save_websim_item_metadata(
            "249919",
            {
                "id": 249919,
                "name": "辛多雷希望指环",
                "inventory_type": {"type": "FINGER", "name": "手指"},
                "item_class": {"id": 4, "name": "护甲"},
                "item_subclass": {"id": 0, "name": "其它"},
                "quality": {"name": "史诗"},
            },
            {"assets": [{"key": "icon", "value": "https://render.worldofwarcraft.com/us/icons/56/inv_jewelry_ring_01.jpg"}]},
            fallback_slot="finger2",
            fallback_name="Sin'dorei Band of Hope",
            english_payload={"name": "Sin'dorei Band of Hope"},
            locale="zh_CN",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        params = conn.cursor_instance.params[-1]
        payload = __import__("json").loads(params[4])
        self.assertEqual(saved["displayName"], "辛多雷希望指环")
        self.assertEqual(saved["iconUrl"], "https://render.worldofwarcraft.com/us/icons/56/inv_jewelry_ring_01.jpg")
        self.assertIn("INSERT INTO cache.websim_items", sql)
        self.assertEqual(params[0], "249919")
        self.assertEqual(params[1], "辛多雷希望指环")
        self.assertEqual(params[5], "verified")
        self.assertEqual(payload["_metadata"]["source"], "Battle.net Game Data API")
        self.assertEqual(payload["_metadata"]["locale"], "zh_CN")
        self.assertEqual(payload["_metadata"]["englishName"], "Sin'dorei Band of Hope")
        self.assertEqual(payload["displayName"], "辛多雷希望指环")
        self.assertEqual(payload["localizedName"], "辛多雷希望指环")
        self.assertEqual(payload["iconUrl"], "https://render.worldofwarcraft.com/us/icons/56/inv_jewelry_ring_01.jpg")
        self.assertTrue(conn.committed)

    def test_community_gear_template_item_metadata_gaps_finds_sparse_pg_rows(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_mage_frost",
                        "mage",
                        "frost",
                        "raiderio_observed_profile",
                        "complete",
                        [
                            {"slot": "finger2", "itemId": "249919", "name": "sindorei_band_of_hope"},
                            {"slot": "head", "itemId": "250060", "name": "虚空粉碎者的面纱"},
                        ],
                    )
                ],
                "FROM cache.websim_items": [
                    ("249919", "Sin'dorei Band of Hope", "finger1", None, {}, "verified"),
                    (
                        "250060",
                        "虚空粉碎者的面纱",
                        "head",
                        None,
                        {
                            "name": "虚空粉碎者的面纱",
                            "displayName": "虚空粉碎者的面纱",
                            "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg",
                            "inventory_type": {"type": "HEAD"},
                            "item_class": {"id": 4},
                            "_metadata": {"source": "Battle.net Game Data API"},
                        },
                        "verified",
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        gaps = store.community_gear_template_item_metadata_gaps(limit=20)

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["itemId"], "249919")
        self.assertEqual(gaps[0]["slot"], "finger2")
        self.assertIn("missing_official_payload_shape", gaps[0]["reasons"])
        self.assertIn("missing_icon", gaps[0]["reasons"])
        self.assertEqual(gaps[0]["templates"][0]["templateId"], "observed_profile_mage_frost")

    def test_websim_item_metadata_gaps_finds_used_sparse_item_rows(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "WITH item_usage AS": [
                    ("263193", "Trollhunter's Bands", "wrist", {}, "verified", 11),
                    (
                        "250060",
                        "虚空粉碎者的面纱",
                        "head",
                        {
                            "name": "虚空粉碎者的面纱",
                            "displayName": "虚空粉碎者的面纱",
                            "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg",
                            "inventory_type": {"type": "HEAD"},
                            "item_class": {"id": 4},
                            "_metadata": {"source": "Battle.net Game Data API"},
                        },
                        "verified",
                        8,
                    ),
                ]
            }
        )
        store = PostgresCacheStore(lambda: conn)

        gaps = store.websim_item_metadata_gaps(limit=20)

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["itemId"], "263193")
        self.assertEqual(gaps[0]["slot"], "wrist")
        self.assertEqual(gaps[0]["usageCount"], 11)
        self.assertIn("missing_official_payload_shape", gaps[0]["reasons"])
        self.assertIn("missing_icon", gaps[0]["reasons"])

    def test_postgres_observed_backfill_uses_simc_json_stats_not_raiderio_stats(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "simcJson": {
                            "sim": {
                                "players": [
                                    {
                                        "gear": {
                                            "head": {
                                                "id": 190001,
                                                "ilevel": 707,
                                                "encoded_item": (
                                                    "observed_helm,id=190001,"
                                                    "bonus_id=1808,ilevel=707,gem_id=240906,enchant_id=8017"
                                                ),
                                                "intellect": 1234,
                                                "stamina": 4567,
                                                "haste_rating": 89,
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Observed Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonuses": [1808],
                                "gems": [240906],
                                "enchants": [8017],
                                "itemStats": [{"key": "intellect", "label": "Intellect", "value": 9999}],
                            }
                        ],
                    }
                ],
            },
            mode="test",
        )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertEqual(observed["partialCount"], 0)
        self.assertIn("statSource", params)
        self.assertIn("simulationcraft", params)
        self.assertIn("1234", params)
        self.assertNotIn("9999", params)

    def test_postgres_observed_backfill_persists_profile_simc_replay_summary(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "simcJson": {
                            "sim": {
                                "options": {"iterations": 1000},
                                "players": [
                                    {
                                        "collected_data": {
                                            "dps": {"mean": 237956},
                                        },
                                        "gear": {
                                            "head": {
                                                "id": 190001,
                                                "ilevel": 707,
                                                "encoded_item": "observed_helm,id=190001,bonus_id=1808,ilevel=707",
                                                "intellect": 1234,
                                                "stamina": 4567,
                                            }
                                        },
                                    }
                                ],
                            }
                        },
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Observed Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonuses": [1808],
                            }
                        ],
                    }
                ],
            },
            mode="test",
        )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertIn("observedProfileSimcReplay", params)
        self.assertIn("observed_profile_replay", params)
        self.assertIn("237956", params)
        self.assertIn("iterations", params)

    def test_postgres_observed_backfill_keeps_statless_rows_partial(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Observed Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    }
                ],
            },
            mode="test",
        )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(observed["verifiedCount"], 0)
        self.assertEqual(observed["partialCount"], 1)
        self.assertIn("missing SimulationCraft item stats", params)

    def test_postgres_observed_backfill_skips_existing_verified_rows_before_target_limit(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "SELECT item_id, slot, item_level, simc_options_json FROM cache.websim_gear_variants": [
                    ("190001", "head", 707, {"ilevel": "707", "bonus_id": "1808"}),
                ]
            }
        )
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Existing Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            },
                            {
                                "itemId": "190002",
                                "name": "New Gloves",
                                "slot": "hands",
                                "ilevel": 707,
                                "bonus_id": "1809",
                            },
                        ],
                    }
                ],
            },
            mode="test",
            target_limit=1,
        )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(observed["skippedExistingVerifiedVariants"], 1)
        self.assertIn("190002", params)
        self.assertNotIn("Existing Helm", params)

    def test_postgres_observed_backfill_updates_existing_verified_rows_with_profile_replay(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "SELECT item_id, slot, item_level, simc_options_json FROM cache.websim_gear_variants": [
                    ("190001", "head", 707, {"ilevel": "707", "bonus_id": "1808"}),
                ]
            }
        )
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "simcJson": {
                            "sim": {
                                "options": {"iterations": 1000},
                                "players": [
                                    {
                                        "collected_data": {"dps": {"mean": 237956}},
                                        "gear": {
                                            "head": {
                                                "id": 190001,
                                                "ilevel": 707,
                                                "encoded_item": "existing_helm,id=190001,bonus_id=1808,ilevel=707",
                                                "intellect": 1234,
                                                "stamina": 4567,
                                            }
                                        },
                                    }
                                ],
                            }
                        },
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Existing Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    }
                ],
            },
            mode="test",
            target_limit=1,
        )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertEqual(observed["skippedExistingVerifiedVariants"], 0)
        self.assertIn("observedProfileSimcReplay", params)
        self.assertIn("237956", params)

    def test_postgres_observed_backfill_reuses_existing_stats_for_new_profile_identity(self):
        from server.postgres_cache_store import PostgresCacheStore

        stat_payload = {
            "statSource": "simulationcraft",
            "itemStats": [{"key": "intellect", "value": 1234}],
            "stats": [{"key": "intellect", "value": 1234}],
            "statSummary": "智力 1234",
        }
        conn = FakeConnection(
            rowsets={
                "SELECT item_id, slot, item_level, simc_options_json FROM cache.websim_gear_variants": [
                    ("190001", "head", 707, {"ilevel": "707", "bonus_id": "1808"}),
                ],
                "payload_json FROM cache.websim_gear_variants": [
                    ("190001", "head", 707, {"ilevel": "707", "bonus_id": "1808"}, stat_payload),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        observed = store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "region": "cn",
                        "realmSlug": "realm",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Existing Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    }
                ],
            },
            mode="test",
            target_limit=1,
        )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(observed["variantCount"], 1)
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertEqual(observed["skippedExistingVerifiedVariants"], 0)
        self.assertIn("https://raider.io/characters/cn/realm/MageA", params)
        self.assertIn("statSource", params)

    def test_observed_item_probe_profile_preserves_observed_variant_options(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        profile, class_key, spec_key, item_line, errors = store._observed_item_probe_simc_text(
            {
                "itemId": "268285",
                "name": "Putrid Tender's Battleplate",
                "slot": "chest",
                "itemLevel": 298,
                "bonuses": [6652, 13577, 13335, 13786],
                "enchants": [7987],
            },
            [
                (
                    "paladin",
                    "retribution",
                    "Ret Paladin",
                    "paladin=\"Ret Paladin\"\nspec=retribution\nlevel=90\nchest=old_chest,id=1,ilevel=1\n",
                )
            ],
        )

        self.assertEqual(errors, [])
        self.assertEqual((class_key, spec_key), ("paladin", "retribution"))
        self.assertIn("chest=putrid_tender_s_battleplate,id=268285,ilevel=298,bonus_id=6652/13577/13335/13786,enchant_id=7987", item_line)
        self.assertIn(item_line, profile)
        self.assertNotIn("chest=old_chest", profile)
        self.assertIn("iterations=1", profile)
        self.assertIn("calculate_scale_factors=0", profile)

    def test_postgres_observed_backfill_falls_back_to_item_probe_when_profile_simc_is_unsupported(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "SELECT class_key, spec_key, name, profile FROM cache.websim_profile_presets": [
                    (
                        "paladin",
                        "retribution",
                        "Ret Paladin",
                        "paladin=\"Ret Paladin\"\nspec=retribution\nlevel=90\nchest=old_chest,id=1,ilevel=1\n",
                    )
                ],
                "SELECT item_id, slot, item_level, simc_options_json, payload_json": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)
        simc_json = {
            "sim": {
                "players": [
                    {
                        "gear": {
                            "chest": {
                                "id": 268285,
                                "ilevel": 298,
                                "encoded_item": "putrid_tender_s_battleplate,id=268285,bonus_id=6652/13577,ilevel=298,enchant_id=7987",
                                "strint": 135,
                                "stamina": 1974,
                            }
                        }
                    }
                ]
            }
        }

        with patch.object(
            PostgresCacheStore,
            "_run_observed_profile_simc_json",
            return_value={"ok": False, "errors": ["Holy Paladin is not currently supported"]},
        ) as profile_runner, patch.object(
            PostgresCacheStore,
            "_run_observed_item_probe_simc_json",
            return_value=simc_json,
        ) as item_runner:
            observed = store.backfill_observed_gear_from_raiderio(
                {
                    "sourceStatus": "verified",
                    "profiles": [
                        {
                            "name": "Holy Paladin",
                            "profileUrl": "https://raider.io/characters/us/area-52/Holy",
                            "classKey": "paladin",
                            "specKey": "holy",
                            "gear": [
                                {
                                    "itemId": "268285",
                                    "name": "Putrid Tender's Battleplate",
                                    "slot": "chest",
                                    "itemLevel": 298,
                                    "bonuses": [6652, 13577],
                                    "enchants": [7987],
                                }
                            ],
                        }
                    ],
                },
                mode="test",
                enable_simc_stats=True,
                timeout_seconds=90,
                item_probe_limit=1,
            )

        params = repr(conn.cursor_instance.params)
        profile_runner.assert_called_once()
        item_runner.assert_called_once()
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertEqual(observed["partialCount"], 0)
        self.assertEqual(observed["simcItemProbeCount"], 1)
        self.assertEqual(observed["simcItemProbeResolvedCount"], 1)
        self.assertIn("simulationcraft_observed_item_probe", params)
        self.assertIn("strint", params)

    def test_observed_item_probe_tries_next_profile_after_simc_failure(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "SELECT class_key, spec_key, name, profile FROM cache.websim_profile_presets": [
                    (
                        "paladin",
                        "holy",
                        "Holy Paladin",
                        "paladin=\"Holy Paladin\"\nspec=holy\nlevel=90\nchest=old_chest,id=1,ilevel=1\n",
                    ),
                    (
                        "warrior",
                        "arms",
                        "Arms Warrior",
                        "warrior=\"Arms Warrior\"\nspec=arms\nlevel=90\nchest=old_chest,id=1,ilevel=1\n",
                    ),
                ],
                "SELECT item_id, slot, item_level, simc_options_json, payload_json": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)
        simc_json = {
            "sim": {
                "players": [
                    {
                        "gear": {
                            "chest": {
                                "id": 268285,
                                "ilevel": 298,
                                "encoded_item": "putrid_tender_s_battleplate,id=268285,bonus_id=6652/13577,ilevel=298",
                                "strint": 135,
                                "stamina": 1974,
                            }
                        }
                    }
                ]
            }
        }

        with patch.object(
            PostgresCacheStore,
            "_run_observed_profile_simc_json",
            return_value={"ok": False, "errors": ["Holy Paladin is not currently supported"]},
        ), patch.object(
            PostgresCacheStore,
            "_run_observed_item_probe_simc_json",
            side_effect=[
                {"ok": False, "errors": ["Holy Paladin is not currently supported"]},
                simc_json,
            ],
        ) as item_runner:
            observed = store.backfill_observed_gear_from_raiderio(
                {
                    "sourceStatus": "verified",
                    "profiles": [
                        {
                            "name": "Holy Paladin",
                            "profileUrl": "https://raider.io/characters/us/area-52/Holy",
                            "classKey": "paladin",
                            "specKey": "holy",
                            "gear": [
                                {
                                    "itemId": "268285",
                                    "name": "Putrid Tender's Battleplate",
                                    "slot": "chest",
                                    "itemLevel": 298,
                                    "armorType": "plate",
                                    "bonuses": [6652, 13577],
                                }
                            ],
                        }
                    ],
                },
                mode="test",
                enable_simc_stats=True,
                item_probe_limit=1,
            )

        params = repr(conn.cursor_instance.params)
        self.assertEqual(item_runner.call_count, 2)
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertEqual(observed["simcItemProbeCount"], 1)
        self.assertEqual(observed["simcItemProbeResolvedCount"], 1)
        self.assertIn("probeClassKey", params)
        self.assertIn("warrior", params)

    def test_postgres_observed_backfill_preserves_verified_variant_from_partial_downgrade(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        store.backfill_observed_gear_from_raiderio(
            {
                "sourceStatus": "verified",
                "profiles": [
                    {
                        "name": "Mage A",
                        "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "itemId": "190001",
                                "name": "Observed Helm",
                                "slot": "head",
                                "ilevel": 707,
                                "bonus_id": "1808",
                            }
                        ],
                    }
                ],
            },
            mode="test",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("ON CONFLICT (item_id, variant_key) DO UPDATE", sql)
        self.assertIn("WHERE NOT ( cache.websim_gear_variants.status = 'verified'", sql)
        self.assertIn("EXCLUDED.status <> 'verified'", sql)

    def test_postgres_observed_backfill_runs_simc_when_enabled(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)
        simc_json = {
            "sim": {
                "players": [
                    {
                        "gear": {
                            "head": {
                                "id": 190001,
                                "ilevel": 707,
                                "encoded_item": "observed_helm,id=190001,bonus_id=1808,ilevel=707",
                                "intellect": 1234,
                            }
                        }
                    }
                ]
            }
        }

        with patch.object(PostgresCacheStore, "_run_observed_profile_simc_json", return_value=simc_json, create=True) as runner:
            observed = store.backfill_observed_gear_from_raiderio(
                {
                    "sourceStatus": "verified",
                    "profiles": [
                        {
                            "name": "Mage A",
                            "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                            "classKey": "mage",
                            "specKey": "frost",
                            "gear": [
                                {
                                    "itemId": "190001",
                                    "name": "Observed Helm",
                                    "slot": "head",
                                    "ilevel": 707,
                                    "bonus_id": "1808",
                                }
                            ],
                        }
                    ],
                },
                mode="test",
                enable_simc_stats=True,
                timeout_seconds=90,
            )

        runner.assert_called_once()
        self.assertEqual(observed["verifiedCount"], 1)
        self.assertEqual(observed["simcResolvedProfileCount"], 1)
        self.assertEqual(observed["simcResolvedSlotCount"], 1)

    def test_build_community_gear_templates_uses_pg_profile_presets(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [
                    (
                        "preset-a",
                        "mage",
                        "frost",
                        "Preset A",
                        "head=observed_helm,id=190001,ilevel=707,bonus_id=1808",
                        {},
                        "2026-07-03T00:00:00+00:00",
                    )
                ]
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_community_gear_templates(scan_run_id="scan-a")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["classKey"], "mage")
        self.assertEqual(templates[0]["specKey"], "frost")
        self.assertEqual(templates[0]["scanRunId"], "scan-a")
        self.assertIn("FROM cache.websim_profile_presets", sql)

    def test_build_season_recommended_gear_templates_uses_complete_community_winners(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(310000 + index),
                "id": str(310000 + index),
                "name": f"community_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "synced",
                        "complete",
                        "community-signature",
                        [{"sourceKey": "raiderio_observed_profile"}],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "community winner",
                        {"templateSlot": "community_best"},
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "frostfire",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["sourceKey"], "season_recommendation")
        self.assertEqual(templates[0]["sourceName"], "当前赛季大秘境 AOE 推荐模板")
        self.assertEqual(templates[0]["status"], "complete")
        self.assertEqual(templates[0]["readySlotCount"], 16)
        self.assertEqual(templates[0]["payload"]["templateSlot"], "baseline")
        self.assertEqual(templates[0]["payload"]["templateEvidence"]["seedTemplateId"], "community-mage-frost")
        self.assertEqual(templates[0]["payload"]["templateEvidence"]["talentAnchor"]["heroKey"], "frostfire")
        self.assertIn("FROM cache.websim_community_gear_templates", sql)

    def test_build_season_recommended_gear_templates_skips_elemental_real_player_pilot(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(510000 + index),
                "id": str(510000 + index),
                "name": f"elemental_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
                **({"armorType": "Mail"} if slot in {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"} else {}),
                **({"weaponType": "One-Handed Mace"} if slot == "main_hand" else {}),
                **({"weaponType": "Shield"} if slot == "off_hand" else {}),
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_shaman_elemental",
                        "shaman",
                        "elemental",
                        "真实高分玩家角色模板 · 听凭风引（元素萨）",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/sylvanas/听凭风引",
                        "synced",
                        "complete",
                        "community-elemental-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/sylvanas/听凭风引",
                            }
                        ],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:shaman:elemental:tingping",
                            "gearHash": "gear:shaman:elemental:tingping",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                        },
                        "2026-07-08T10:00:00+08:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-shaman-elemental-stormbringer",
                        "shaman",
                        "elemental",
                        "stormbringer",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-08T10:00:00+08:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        self.assertEqual(templates, [])

    def test_cleanup_real_player_gear_template_pilot_residue_deletes_elemental_legacy_rows(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        result = store.cleanup_real_player_gear_template_pilot_residue(
            scan_run_id="cleanup-test",
            checked_at="2026-07-08T03:00:00+00:00",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        params = conn.cursor_instance.params
        self.assertIn("DELETE FROM cache.websim_community_gear_templates", sql)
        self.assertIn("DELETE FROM cache.websim_gear_variants", sql)
        self.assertIn("UPDATE cache.websim_community_gear_templates SET name", sql)
        self.assertIn("jsonb_set", sql)
        self.assertTrue(any("shaman" in param_set and "elemental" in param_set for param_set in params))
        self.assertTrue(
            any("听凭风引（元素萨）· 真实高分玩家角色模板" in param_set for param_set in params)
        )
        self.assertTrue(
            any("元素萨 · 系统评分推荐模板（待 SimC 验证）" in param_set for param_set in params)
        )
        self.assertIn("communityTemplateRowsDeleted", result)
        self.assertIn("observedVariantRowsDeleted", result)
        self.assertIn("renamedTemplateRows", result)
        self.assertEqual(result["publicImportPolicy"], "all_specs")
        self.assertIn("recommended_bis", result["publicHiddenSourceKeys"])
        self.assertIn("season_recommendation", result["publicHiddenSourceKeys"])
        self.assertEqual(result["destructiveCleanupScope"], ["shaman:elemental"])
        self.assertGreaterEqual(result["renamedTemplateRows"], 2)

    def test_cleanup_real_player_gear_template_backfills_missing_observed_variants_from_active_row(self):
        from server.postgres_cache_store import PostgresCacheStore

        profile_ref = {
            "profileUrl": "https://raider.io/characters/cn/sylvanas/听凭风引",
            "sourceName": "Raider.IO observed profile: 听凭风引",
            "characterName": "听凭风引",
            "region": "cn",
            "realmSlug": "sylvanas",
            "rankingEvidence": {"source": "raiderio_spec_ranking", "rank": 1, "score": 4249.17},
        }
        gear_items = [
            {
                "slot": "head",
                "simcSlot": "head",
                "itemId": "550001",
                "id": "550001",
                "name": "existing_head",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "statSource": "simulationcraft",
                "itemStats": [{"key": "intellect", "value": 1000}],
                "observedProfileRefs": [profile_ref],
            },
            {
                "slot": "neck",
                "simcSlot": "neck",
                "itemId": "550002",
                "id": "550002",
                "name": "missing_neck",
                "ilevel": "707",
                "bonus_id": "1808",
                "gem_id": "240983",
                "simcReady": True,
                "statSource": "simulationcraft",
                "itemStats": [{"key": "mastery_rating", "value": 500}],
                "observedProfileRefs": [profile_ref],
            },
        ]
        conn = FakeConnection(
            rowsets={
                "SELECT gear_items_json FROM cache.websim_community_gear_templates": [
                    (gear_items,),
                ],
                "SELECT slot FROM cache.websim_gear_variants": [
                    ("head",),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        result = store.cleanup_real_player_gear_template_pilot_residue(
            scan_run_id="cleanup-test",
            checked_at="2026-07-08T03:00:00+00:00",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        params = conn.cursor_instance.params
        self.assertIn("INSERT INTO cache.websim_gear_variants", sql)
        self.assertEqual(result["observedVariantRowsBackfilled"], 1)
        self.assertTrue(any("550002" in param_set and "neck" in param_set for param_set in params))

    def test_build_season_recommended_gear_templates_blocks_without_talent_anchor(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(320000 + index),
                "id": str(320000 + index),
                "name": f"community_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "synced",
                        "complete",
                        "community-signature",
                        [{"sourceKey": "raiderio_observed_profile"}],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "community winner",
                        {"templateSlot": "community_best"},
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        self.assertEqual(templates, [])

    def test_build_season_recommended_gear_templates_scores_candidates_instead_of_copying_seed(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        seed_items = []
        alternative_items = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item_id = str(330000 + index)
            base_item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": item_id,
                "id": item_id,
                "name": f"seed_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            seed_items.append(base_item)
            alternative_items.append(dict(base_item))
        seed_items[0] = {
            **seed_items[0],
            "itemId": "339001",
            "id": "339001",
            "name": "versatility_seed_head",
            "ilevel": "715",
            "itemStats": [
                {"key": "intellect", "value": 1200},
                {"key": "versatility", "value": 600},
            ],
        }
        alternative_items[0] = {
            **alternative_items[0],
            "itemId": "339002",
            "id": "339002",
            "name": "haste_mastery_head",
            "ilevel": "730",
            "itemStats": [
                {"key": "intellect", "value": 2200},
                {"key": "haste", "value": 900},
                {"key": "mastery", "value": 900},
            ],
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost-seed",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜 A",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/FrostSeedA",
                        "synced",
                        "complete",
                        "community-seed-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/FrostSeedA",
                                "rankingEvidence": {
                                    "source": "raiderio_spec_ranking",
                                    "rank": 1,
                                    "score": 4249.17,
                                },
                            }
                        ],
                        seed_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in seed_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:mage:frost:seed-a",
                            "gearHash": "gear:mage:frost:seed-a",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                        },
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                    (
                        "community-mage-frost-alt",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜 B",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/FrostSeedB",
                        "synced",
                        "complete",
                        "community-alt-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/FrostSeedB",
                                "rankingEvidence": {
                                    "source": "raiderio_spec_ranking",
                                    "rank": 2,
                                    "score": 4200.0,
                                },
                            }
                        ],
                        alternative_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in alternative_items),
                        16,
                        [],
                        "community candidate",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:mage:frost:seed-b",
                            "gearHash": "gear:mage:frost:seed-b",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 2,
                                "score": 4200.0,
                            },
                        },
                        "2026-07-05T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "frostfire",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        self.assertEqual(len(templates), 1)
        head = next(item for item in templates[0]["gearItems"] if item["slot"] == "head")
        self.assertEqual(head["itemId"], "339002")
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["scoringVersion"], "season-rec-score-v1")
        self.assertGreater(evidence["candidateCount"], 16)
        self.assertEqual(evidence["slotDecisions"]["head"]["selectedItemId"], "339002")
        self.assertFalse(evidence["slotDecisions"]["head"]["lowYieldStatPenalty"]["applied"])
        self.assertEqual(evidence["recommendationConfidence"], "provisional")

    def test_build_season_recommended_gear_templates_uses_pg_stat_weight_cache(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        seed_items = []
        alternative_items = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item_id = str(333000 + index)
            base_item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": item_id,
                "id": item_id,
                "name": f"seed_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            seed_items.append(base_item)
            alternative_items.append(dict(base_item))
        seed_items[0] = {
            **seed_items[0],
            "itemId": "333901",
            "id": "333901",
            "name": "default_haste_head",
            "itemStats": [
                {"key": "intellect", "value": 1000},
                {"key": "haste", "value": 500},
            ],
        }
        alternative_items[0] = {
            **alternative_items[0],
            "itemId": "333902",
            "id": "333902",
            "name": "cached_mastery_head",
            "itemStats": [
                {"key": "intellect", "value": 1000},
                {"key": "mastery", "value": 350},
            ],
        }
        stat_payload = {
            "classKey": "mage",
            "specKey": "frost",
            "scenarioKey": "mplus_aoe_pack",
            "sourceStatus": "verified",
            "weights": [
                {"key": "intellect", "value": 1.45},
                {"key": "mastery", "value": 2.0},
                {"key": "haste", "value": 0.1},
                {"key": "crit", "value": 0.8},
                {"key": "versatility", "value": 0.2},
            ],
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost-seed",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜 A",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/MageSeed",
                        "synced",
                        "complete",
                        "community-seed-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/MageSeed",
                            }
                        ],
                        seed_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in seed_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "gearHash": "gear:mage:frost:seed",
                        },
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                    (
                        "community-mage-frost-alt",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜 B",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/MageAlt",
                        "synced",
                        "complete",
                        "community-alt-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/MageAlt",
                            }
                        ],
                        alternative_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in alternative_items),
                        16,
                        [],
                        "community candidate",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "gearHash": "gear:mage:frost:alt",
                        },
                        "2026-07-05T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "frostfire",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
                "FROM cache.stat_weight_cache WHERE cache_key": [
                    (stat_payload, "verified", "2026-07-07T00:00:00+00:00"),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        self.assertEqual(len(templates), 1)
        head = next(item for item in templates[0]["gearItems"] if item["slot"] == "head")
        self.assertEqual(head["itemId"], "333902")
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["statWeights"]["sourceStatus"], "verified")
        self.assertEqual(evidence["statWeights"]["sourceScenarioKey"], "mplus_aoe_pack")
        self.assertIn(("mage:frost:mplus_aoe_pack",), conn.cursor_instance.params)

    def test_build_season_recommended_gear_templates_scores_pg_catalog_replacements(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        seed_items = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item_id = str(340000 + index)
            seed_items.append(
                {
                    "slot": slot,
                    "simcSlot": slot,
                    "itemId": item_id,
                    "id": item_id,
                    "name": f"seed_{slot}",
                    "ilevel": "707",
                    "bonus_id": "1808",
                    "simcReady": True,
                    "itemStats": [{"key": "intellect", "value": 1000}],
                }
            )
        seed_items[0] = {
            **seed_items[0],
            "itemId": "349001",
            "id": "349001",
            "name": "community_versatility_head",
            "ilevel": "715",
            "itemStats": [
                {"key": "intellect", "value": 1200},
                {"key": "versatility", "value": 600},
            ],
        }
        catalog_head_payload = {
            "id": 349002,
            "displayName": "Catalog Haste Mastery Head",
            "name": "Catalog Haste Mastery Head",
            "inventory_type": {"name": "Head"},
            "item_class": {"id": 4, "name": "Armor"},
            "item_subclass": {"id": 1, "name": "Cloth"},
            "metadataSource": "Battle.net Game Data API",
            "metadataStatus": "verified",
            "_metadata": {"source": "Battle.net Game Data API", "englishName": "Catalog Haste Mastery Head"},
            "itemStats": [
                {"key": "intellect", "value": 1250},
                {"key": "haste", "value": 360},
                {"key": "mastery", "value": 320},
            ],
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost-seed",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/FrostSeed",
                        "synced",
                        "complete",
                        "community-seed-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/FrostSeed",
                                "rankingEvidence": {
                                    "source": "raiderio_spec_ranking",
                                    "rank": 1,
                                    "score": 4249.17,
                                },
                            }
                        ],
                        seed_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in seed_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:mage:frost:catalog-replacement",
                            "gearHash": "gear:mage:frost:catalog-replacement",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                        },
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                ],
                "SELECT id, item_id, source_type, source_key, source_label": [
                    (
                        "source-349002",
                        "349002",
                        "crafted",
                        "crafted:cloth",
                        "Crafted cloth",
                        "",
                        "",
                        "",
                        "season-test",
                        {"recommendationScore": 100},
                        "2026-07-07T00:00:00+00:00",
                    )
                ],
                "SELECT id, item_id, slot, variant_key, label, source_type, difficulty_key": [
                    (
                        "variant-349002",
                        "349002",
                        "head",
                        "crafted-715",
                        "Crafted 715",
                        "crafted",
                        "crafted",
                        715,
                        {"ilevel": "715", "bonus_id": "1808"},
                        "verified",
                        [],
                        {
                            "status": "verified",
                            "itemStats": catalog_head_payload["itemStats"],
                            "statSource": "simulationcraft",
                        },
                        "2026-07-07T00:00:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "349002",
                        "Catalog Haste Mastery Head",
                        "head",
                        715,
                        catalog_head_payload,
                        "verified",
                    )
                ],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "frostfire",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        self.assertEqual(len(templates), 1)
        head = next(item for item in templates[0]["gearItems"] if item["slot"] == "head")
        self.assertEqual(head["itemId"], "349002")
        self.assertTrue(head["simcReady"])
        self.assertNotIn("verified Battle.net metadata", head.get("blockers") or [])
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["slotDecisions"]["head"]["selectedItemId"], "349002")
        self.assertIn("gear_catalog_replacement_candidates", evidence["candidatePoolSources"])

    def test_build_season_recommended_gear_templates_repairs_partial_seed_weapons_from_catalog(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        seed_items = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item_id = str(350000 + index)
            seed_items.append(
                {
                    "slot": slot,
                    "simcSlot": slot,
                    "itemId": item_id,
                    "id": item_id,
                    "name": f"seed_{slot}",
                    "ilevel": "707",
                    "bonus_id": "1808",
                    "simcReady": True,
                    "itemStats": [{"key": "intellect", "value": 1000}],
                }
            )
        seed_items[CANONICAL_GEAR_SLOTS.index("main_hand")] = {
            "slot": "main_hand",
            "simcSlot": "main_hand",
            "itemId": "359001",
            "id": "359001",
            "name": "community_illegal_two_hand_mace",
            "ilevel": "715",
            "bonus_id": "1808",
            "weaponType": "Two-Handed Mace",
            "simcReady": True,
            "itemStats": [{"key": "intellect", "value": 1400}],
        }
        seed_items[CANONICAL_GEAR_SLOTS.index("off_hand")] = {
            "slot": "off_hand",
            "simcSlot": "off_hand",
            "itemId": "359002",
            "id": "359002",
            "name": "community_held_offhand",
            "ilevel": "707",
            "bonus_id": "1808",
            "weaponType": "Held In Off-hand",
            "simcReady": True,
            "itemStats": [{"key": "intellect", "value": 800}],
        }
        catalog_main_payload = {
            "id": 359101,
            "displayName": "Catalog Legal One-Hand Mace",
            "name": "Catalog Legal One-Hand Mace",
            "inventory_type": {"type": "WEAPON", "name": "Main Hand"},
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 15, "name": "Dagger"},
            "metadataSource": "Battle.net Game Data API",
            "metadataStatus": "verified",
            "_metadata": {"source": "Battle.net Game Data API"},
            "itemStats": [
                {"key": "intellect", "value": 1500},
                {"key": "haste", "value": 420},
                {"key": "mastery", "value": 380},
            ],
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost-partial",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/FrostPartial",
                        "partial",
                        "partial",
                        "community-partial-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/FrostPartial",
                                "rankingEvidence": {
                                    "source": "raiderio_spec_ranking",
                                    "rank": 1,
                                    "score": 4249.17,
                                },
                            }
                        ],
                        seed_items,
                        "\n".join(
                            f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808"
                            for item in seed_items
                        ),
                        14,
                        ["main_hand", "off_hand"],
                        "community partial legality gate",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:mage:frost:partial-repair",
                            "gearHash": "gear:mage:frost:partial-repair",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                            "legalityStatus": "partial",
                            "legalitySkippedSlots": ["main_hand", "off_hand"],
                        },
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                ],
                "SELECT id, item_id, source_type, source_key, source_label": [
                    (
                        "source-359101",
                        "359101",
                        "dungeon",
                        "dungeon:test",
                        "Dungeon test",
                        "",
                        "",
                        "",
                        "season-test",
                        {"recommendationScore": 100},
                        "2026-07-07T00:00:00+00:00",
                    )
                ],
                "SELECT id, item_id, slot, variant_key, label, source_type, difficulty_key": [
                    (
                        "variant-359101",
                        "359101",
                        "main_hand",
                        "mplus-715",
                        "Myth 715",
                        "dungeon",
                        "myth",
                        715,
                        {"ilevel": "715", "bonus_id": "1808"},
                        "verified",
                        [],
                        {
                            "status": "verified",
                            "itemStats": catalog_main_payload["itemStats"],
                            "statSource": "simulationcraft",
                        },
                        "2026-07-07T00:00:00+00:00",
                    )
                ],
                "FROM cache.websim_items": [
                    (
                        "359101",
                        "Catalog Legal One-Hand Mace",
                        "main_hand",
                        715,
                        catalog_main_payload,
                        "verified",
                    )
                ],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "frostfire",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_season_recommended_gear_templates(scan_run_id="season-rec-test")

        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["status"], "complete")
        self.assertEqual(templates[0]["missingSlots"], [])
        main_hand = next(item for item in templates[0]["gearItems"] if item["slot"] == "main_hand")
        self.assertEqual(main_hand["itemId"], "359101")
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["seedTemplateStatus"], "partial")
        self.assertEqual(evidence["seedTemplateMissingSlots"], ["main_hand", "off_hand"])
        self.assertEqual(evidence["slotDecisions"]["main_hand"]["selectedItemId"], "359101")
        self.assertIn("gear_catalog_replacement_candidates", evidence["candidatePoolSources"])

    def test_build_recommended_bis_prototype_templates_writes_dps_projected_evidence(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        seed_items = []
        alternative_items = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item_id = str(360000 + index)
            base_item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": item_id,
                "id": item_id,
                "name": f"seed_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            seed_items.append(base_item)
            alternative_items.append(dict(base_item))
        alternative_items[0] = {
            **alternative_items[0],
            "itemId": "369002",
            "id": "369002",
            "name": "projected_mastery_head",
            "itemStats": [
                {"key": "intellect", "value": 1100},
                {"key": "mastery", "value": 500},
            ],
        }
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost-seed",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜 A",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/MageSeed",
                        "synced",
                        "complete",
                        "community-seed-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/MageSeed",
                            }
                        ],
                        seed_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in seed_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "gearHash": "gear:mage:frost:seed",
                        },
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                    (
                        "community-mage-frost-alt",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜 B",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/MageAlt",
                        "synced",
                        "complete",
                        "community-alt-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/MageAlt",
                            }
                        ],
                        alternative_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in alternative_items),
                        16,
                        [],
                        "community candidate",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "gearHash": "gear:mage:frost:alt",
                        },
                        "2026-07-05T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    ),
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-mage-frost-frostfire",
                        "mage",
                        "frost",
                        "frostfire",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_recommended_bis_prototype_templates(scan_run_id="recommended-bis-test")

        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["sourceKey"], "recommended_bis")
        self.assertEqual(template["payload"]["templateSlot"], "recommended_bis")
        self.assertEqual(template["payload"]["templateType"], "recommended_bis")
        self.assertEqual(template["payload"]["countingPolicy"], "recommended_bis_v1 projected DPS prototype; not legacy fallback and not verified BiS")
        evidence = template["payload"]["templateEvidence"]
        self.assertEqual(evidence["schemaRevision"], "recommended-bis-v1")
        self.assertEqual(evidence["status"], "projected_bis")
        self.assertEqual(evidence["optimizerVersion"], "gear-bis-optimizer-v1")
        self.assertGreater(evidence["candidatePool"]["candidateCount"], 16)
        self.assertEqual(evidence["statPriorPolicy"]["role"], "candidate_recall_only")
        self.assertEqual(evidence["statPriorPolicy"]["finalDecision"], "simc_gear_compare_required")
        self.assertEqual(evidence["simc"]["status"], "required")
        self.assertEqual(evidence["simc"]["highIterationRuns"], 0)
        self.assertEqual(evidence["simc"]["pairwiseCompares"], 0)
        self.assertEqual(evidence["anchorValidation"]["status"], "pending")
        self.assertIn("high-iteration SimC compare has not run", evidence["blockers"])
        self.assertIn("observed anchor validation is pending", evidence["blockers"])

    def test_build_recommended_bis_prototype_templates_names_elemental_pilot_clearly(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(370000 + index),
                "id": str(370000 + index),
                "name": f"elemental_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
                **({"armorType": "Mail"} if slot in {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"} else {}),
                **({"weaponType": "One-Handed Mace"} if slot == "main_hand" else {}),
                **({"weaponType": "Shield"} if slot == "off_hand" else {}),
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_shaman_elemental",
                        "shaman",
                        "elemental",
                        "听凭风引（元素萨）· 真实高分玩家角色模板",
                        "raiderio_observed_profile",
                        "Raider.IO 真实玩家角色装备",
                        "https://raider.io/characters/cn/sylvanas/听凭风引",
                        "synced",
                        "complete",
                        "community-elemental-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/sylvanas/听凭风引",
                                "characterName": "听凭风引",
                                "region": "cn",
                                "realmSlug": "sylvanas",
                                "rankingEvidence": {
                                    "source": "raiderio_spec_ranking",
                                    "rank": 1,
                                    "score": 4249.17,
                                },
                            }
                        ],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:shaman:elemental:tingping",
                            "gearHash": "gear:shaman:elemental:tingping",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                        },
                        "2026-07-08T10:00:00+08:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_recommended_bis_prototype_templates(scan_run_id="recommended-bis-test")

        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["name"], "元素萨 · 系统评分推荐模板（待 SimC 验证）")
        self.assertEqual(template["sourceName"], "系统评分推荐模板（projected_bis）")
        evidence = template["payload"]["templateEvidence"]
        self.assertEqual(evidence["templateName"], "元素萨 · 系统评分推荐模板（待 SimC 验证）")
        self.assertEqual(evidence["sourceName"], "系统评分推荐模板（projected_bis）")
        self.assertEqual(evidence["status"], "projected_bis")
        self.assertEqual(evidence["simc"]["status"], "required")
        self.assertEqual(evidence["anchorValidation"]["status"], "pending")

    def test_build_recommended_bis_prototype_templates_applies_elemental_enhancement_anchor(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        armor_slots = {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}

        def observed_item(slot, index):
            item_id = str(371000 + index)
            item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": item_id,
                "id": item_id,
                "name": f"observed_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            if slot in armor_slots:
                item["armorType"] = "Mail"
            if slot == "main_hand":
                item["weaponType"] = "One-Handed Mace"
            if slot == "off_hand":
                item["weaponType"] = "Shield"
            return item

        gear_items = [observed_item(slot, index) for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)]
        by_slot = {item["slot"]: item for item in gear_items}
        by_slot["head"].update({
            "bonus_id": "6652/13335",
            "gem_id": "240908",
            "enchant_id": "8017",
        })
        by_slot["back"].update({
            "itemId": "371004",
            "id": "371004",
            "bonus_id": "12214/13667",
            "embellishment": "arcanoweave_lining",
            "itemStats": [{"key": "intellect", "value": 900}],
        })
        by_slot["wrist"].update({
            "gem_id": "240908",
            "embellishment": "arcanoweave_lining",
        })

        catalog_head = {
            **by_slot["head"],
            "name": "catalog_same_head_without_enhancements",
            "bonus_id": "",
            "gem_id": "",
            "enchant_id": "",
            "itemStats": [{"key": "intellect", "value": 5000}],
        }
        catalog_back = {
            **by_slot["back"],
            "itemId": "379999",
            "id": "379999",
            "name": "catalog_high_score_plain_back",
            "bonus_id": "1808",
            "embellishment": "",
            "itemStats": [{"key": "intellect", "value": 5000}],
        }

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_shaman_elemental",
                        "shaman",
                        "elemental",
                        "听凭风引（元素萨）· 真实高分玩家角色模板",
                        "raiderio_observed_profile",
                        "Raider.IO 真实玩家角色装备",
                        "https://raider.io/characters/cn/sylvanas/听凭风引",
                        "synced",
                        "complete",
                        "community-elemental-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/sylvanas/听凭风引",
                                "characterName": "听凭风引",
                                "region": "cn",
                                "realmSlug": "sylvanas",
                                "rankingEvidence": {
                                    "source": "raiderio_spec_ranking",
                                    "rank": 1,
                                    "score": 4249.17,
                                },
                            }
                        ],
                        gear_items,
                        "\n".join(
                            f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id={item.get('bonus_id', '1808')}"
                            for item in gear_items
                        ),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:shaman:elemental:tingping",
                            "gearHash": "gear:shaman:elemental:tingping",
                            "rankingEvidence": {
                                "source": "raiderio_spec_ranking",
                                "rank": 1,
                                "score": 4249.17,
                            },
                        },
                        "2026-07-08T10:00:00+08:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-shaman-elemental",
                        "shaman",
                        "elemental",
                        "farseer",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-08T10:00:00+08:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)
        store._season_recommended_catalog_candidates_by_slot = lambda class_key, spec_key: {
            "head": [catalog_head],
            "back": [catalog_back],
        }

        templates = store.build_recommended_bis_prototype_templates(scan_run_id="recommended-bis-test")

        self.assertEqual(len(templates), 1)
        by_output_slot = {item["slot"]: item for item in templates[0]["gearItems"]}
        self.assertEqual(by_output_slot["head"]["itemId"], by_slot["head"]["itemId"])
        self.assertEqual(by_output_slot["head"].get("gem_id"), "240908")
        self.assertEqual(by_output_slot["head"].get("enchant_id"), "8017")
        self.assertEqual(by_output_slot["back"]["itemId"], "371004")
        self.assertEqual(by_output_slot["back"].get("embellishment"), "arcanoweave_lining")
        self.assertEqual(by_output_slot["wrist"].get("embellishment"), "arcanoweave_lining")
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["status"], "projected_bis")
        self.assertEqual(evidence["enhancementOptimization"]["status"], "pilot_applied")
        self.assertIn("recommended_bis enhancement optimization still requires SimC validation", evidence["blockers"])

    def test_build_recommended_bis_prototype_templates_applies_persisted_elemental_simc_evidence(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item = {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(372000 + index),
                "id": str(372000 + index),
                "name": f"elemental_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            if slot in {"head", "shoulder", "chest", "wrist", "hands", "waist", "legs", "feet"}:
                item["armorType"] = "Mail"
            if slot == "main_hand":
                item["weaponType"] = "One-Handed Mace"
            if slot == "off_hand":
                item["weaponType"] = "Shield"
            gear_items.append(item)

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "observed_profile_shaman_elemental",
                        "shaman",
                        "elemental",
                        "听凭风引（元素萨）· 真实高分玩家角色模板",
                        "raiderio_observed_profile",
                        "Raider.IO 真实玩家角色装备",
                        "https://raider.io/characters/cn/sylvanas/听凭风引",
                        "synced",
                        "complete",
                        "community-elemental-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/sylvanas/听凭风引",
                                "characterName": "听凭风引",
                                "rankingEvidence": {"source": "raiderio_spec_ranking", "rank": 1, "score": 4249.17},
                            }
                        ],
                        gear_items,
                        "\n".join(
                            f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808"
                            for item in gear_items
                        ),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "profileHash": "profile:shaman:elemental:tingping",
                            "gearHash": "gear:shaman:elemental:tingping",
                            "rankingEvidence": {"source": "raiderio_spec_ranking", "rank": 1, "score": 4249.17},
                        },
                        "2026-07-08T10:00:00+08:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [],
                "FROM cache.websim_sync_state": {
                    ("recommended_bis_v1_simc_evidence",): [
                        (
                            {
                                "schemaRevision": "recommended-bis-v1-simc-evidence-overrides-v1",
                                "evidenceBySpec": {
                                    "shaman:elemental": {
                                        "status": "passed",
                                        "checkedAt": "2026-07-08T13:24:00+08:00",
                                        "source": "manual_cloud_simc_compare",
                                        "scenarioKey": "mplus_aoe",
                                        "simcVersion": "1205-01",
                                        "iterations": 10000,
                                        "winnerProfile": "recommended_enhanced_projected",
                                        "winnerDps": 188418.99492534876,
                                        "winnerErrorPct": 0.031889607114364595,
                                        "observedProfile": "observed_full",
                                        "observedDps": 187783.45715070626,
                                        "observedErrorPct": 0.036767306803863184,
                                        "deltaDpsVsObserved": 635.5377746424929,
                                        "deltaPctVsObserved": 0.3384418331016453,
                                        "talentAnchorStatus": "stale",
                                    }
                                },
                            },
                            "2026-07-08T13:24:00+08:00",
                        )
                    ]
                },
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_recommended_bis_prototype_templates(scan_run_id="recommended-bis-test")

        self.assertEqual(len(templates), 1)
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["status"], "projected_bis")
        self.assertEqual(evidence["simc"]["status"], "passed")
        self.assertEqual(evidence["simc"]["highIterationRuns"], 1)
        self.assertEqual(evidence["simc"]["winnerDps"], 188418.99492534876)
        self.assertEqual(evidence["simc"]["manualCompare"]["deltaPctVsObserved"], 0.3384418331016453)
        self.assertNotIn("high-iteration SimC compare has not run", evidence["blockers"])
        self.assertNotIn("recommended_bis enhancement optimization still requires SimC validation", evidence["blockers"])
        self.assertIn("missing verified community talent anchor", evidence["blockers"])
        self.assertIn("pairwise gear compare has not run", evidence["blockers"])
        self.assertIn("observed anchor validation is pending", evidence["blockers"])

    def test_build_recommended_bis_prototype_templates_keeps_dps_with_missing_talent_anchor_blocker(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(361000 + index),
                "id": str(361000 + index),
                "name": f"frost_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
                "itemStats": [{"key": "intellect", "value": 1000}],
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-mage-frost",
                        "mage",
                        "frost",
                        "Raider.IO 观测装备 · 法师冰霜",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "https://raider.io/characters/cn/realm/MageNoTalent",
                        "synced",
                        "complete",
                        "community-frost-signature",
                        [
                            {
                                "sourceKey": "raiderio_observed_profile",
                                "sourceUrl": "https://raider.io/characters/cn/realm/MageNoTalent",
                            }
                        ],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "community winner",
                        {
                            "templateSlot": "community_best",
                            "sampleCount": 1,
                            "gearHash": "gear:mage:frost:no-talent",
                        },
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_recommended_bis_prototype_templates(scan_run_id="recommended-bis-test")

        self.assertEqual(len(templates), 1)
        evidence = templates[0]["payload"]["templateEvidence"]
        self.assertEqual(evidence["status"], "projected_bis")
        self.assertEqual(evidence["talentAnchor"]["status"], "blocked")
        self.assertIn("missing verified community talent anchor", evidence["blockers"])

    def test_build_recommended_bis_prototype_templates_skips_non_dps_specs(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        gear_items = [
            {
                "slot": slot,
                "simcSlot": slot,
                "itemId": str(370000 + index),
                "id": str(370000 + index),
                "name": f"holy_{slot}",
                "ilevel": "707",
                "bonus_id": "1808",
                "simcReady": True,
            }
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_community_gear_templates": [
                    (
                        "community-priest-holy",
                        "priest",
                        "holy",
                        "Raider.IO 观测装备 · 牧师神圣",
                        "raiderio_observed_profile",
                        "Raider.IO observed gear",
                        "",
                        "synced",
                        "complete",
                        "community-holy-signature",
                        [{"sourceKey": "raiderio_observed_profile"}],
                        gear_items,
                        "\n".join(f"{item['slot']}={item['name']},id={item['id']},ilevel=707,bonus_id=1808" for item in gear_items),
                        16,
                        [],
                        "community winner",
                        {"templateSlot": "community_best"},
                        "2026-07-06T00:00:00+00:00",
                        "2099-01-01T00:00:00+00:00",
                        "scan-community",
                    )
                ],
                "FROM cache.websim_items": [],
                "FROM cache.websim_community_talent_templates": [
                    (
                        "talent-priest-holy",
                        "priest",
                        "holy",
                        "oracle",
                        "raiderio",
                        "Raider.IO",
                        "verified",
                        "verified",
                        {"evidenceTier": "verified"},
                        "2026-07-06T00:00:00+00:00",
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_recommended_bis_prototype_templates(scan_run_id="recommended-bis-test")

        self.assertEqual(templates, [])

    def test_build_community_gear_templates_uses_trusted_observed_variants(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        trusted_rows = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            item_id = str(190000 + index)
            payload = {
                "classKey": "mage",
                "specKey": "frost",
                "statSource": "simulationcraft",
                "itemStats": [{"key": "intellect", "value": 1000 + index}],
                "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                "characterName": "MageA",
                "region": "cn",
                "realmSlug": "realm",
            }
            if slot == "main_hand":
                payload["weaponType"] = "Dagger"
            elif slot == "off_hand":
                payload["weaponType"] = "Held In Off-hand"
            trusted_rows.append(
                (
                    f"variant-a-{slot}",
                    item_id,
                    f"Observed {slot}",
                    slot,
                    707,
                    {"ilevel": "707", "bonus_id": "1808"},
                    "verified",
                    [],
                    payload,
                    {},
                    "2026-07-05T00:00:00+00:00",
                )
            )

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": [
                    *trusted_rows,
                    (
                        "variant-untrusted",
                        "199999",
                        "Untrusted Should Stay Out",
                        "neck",
                        707,
                        {"ilevel": "707", "bonus_id": "1808"},
                        "verified",
                        [],
                        {
                            "classKey": "mage",
                            "specKey": "frost",
                            "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        },
                        {},
                        "2026-07-05T00:00:00+00:00",
                    ),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_community_gear_templates(scan_run_id="scan-observed")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(template["classKey"], "mage")
        self.assertEqual(template["specKey"], "frost")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["scanRunId"], "scan-observed")
        self.assertEqual(template["sourceUrl"], "https://raider.io/characters/cn/realm/MageA")
        self.assertEqual(template["sampleCount"], 1)
        self.assertTrue(template["gearHash"])
        self.assertEqual(template["sourceRefs"][0]["sourceUrl"], "https://raider.io/characters/cn/realm/MageA")
        self.assertNotIn("199999", [item["itemId"] for item in template["gearItems"]])
        self.assertEqual(len(template["gearItems"]), 16)
        self.assertIn("FROM cache.websim_gear_variants v", sql)

    def test_build_community_gear_templates_keeps_elemental_observed_to_single_profile(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        profile_a = "https://raider.io/characters/us/stormrage/Kiliwynn"
        profile_b = "https://raider.io/characters/us/frostmourne/Zorthar"
        observed_rows = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
            if slot == "off_hand":
                continue
            item_id = str(390000 + index)
            payload = {
                "classKey": "shaman",
                "specKey": "elemental",
                "statSource": "simulationcraft",
                "itemStats": [{"key": "intellect", "value": 1000}],
                "profileUrl": profile_a,
                "sourceLabel": "Raider.IO observed profile: Kiliwynn",
                "rankingEvidence": {
                    "source": "raiderio_spec_ranking",
                    "rank": 1,
                    "score": 4249.17,
                },
            }
            if slot == "main_hand":
                payload["weaponType"] = "Two-Handed Mace"
            observed_rows.append(
                (
                    f"variant-a-{slot}",
                    item_id,
                    f"Observed A {slot}",
                    slot,
                    707,
                    {"ilevel": "707", "bonus_id": "1808"},
                    "verified",
                    [],
                    payload,
                    {},
                    "2026-07-05T00:00:00+00:00",
                )
            )
        observed_rows.append(
            (
                "variant-b-off-hand",
                "399999",
                "Observed B Off Hand",
                "off_hand",
                707,
                {"ilevel": "707", "bonus_id": "1808"},
                "verified",
                [],
                {
                    "classKey": "shaman",
                    "specKey": "elemental",
                    "statSource": "simulationcraft",
                    "itemStats": [{"key": "intellect", "value": 500}],
                    "profileUrl": profile_b,
                    "sourceLabel": "Raider.IO observed profile: Zorthar",
                    "weaponType": "Held In Off-hand",
                },
                {},
                "2026-07-05T00:00:00+00:00",
            )
        )
        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": observed_rows,
                "FROM cache.websim_items": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_community_gear_templates(scan_run_id="scan-observed")

        self.assertEqual(templates, [])

    def test_build_community_gear_templates_selects_single_profile_winner_for_all_specs(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        profile_a = "https://raider.io/characters/us/stormrage/Magealpha"
        profile_b = "https://raider.io/characters/us/area-52/Magewinner"

        def observed_rows(profile_url, character_name, base_item_id, rank, score, updated_at):
            rows = []
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
                item_id = str(base_item_id + index)
                payload = {
                    "classKey": "mage",
                    "specKey": "frost",
                    "statSource": "simulationcraft",
                    "itemStats": [{"key": "intellect", "value": 1000 + index}],
                    "profileUrl": profile_url,
                    "characterName": character_name,
                    "region": "us",
                    "realmSlug": "area-52" if character_name == "Magewinner" else "stormrage",
                    "sourceLabel": f"Raider.IO observed profile: {character_name}",
                    "rankingEvidence": {
                        "source": "raiderio_spec_ranking",
                        "rank": rank,
                        "score": score,
                        "maxKeyLevel": 20,
                    },
                }
                if slot == "main_hand":
                    payload["weaponType"] = "Dagger"
                elif slot == "off_hand":
                    payload["weaponType"] = "Held In Off-hand"
                simc_options = {"ilevel": "707", "bonus_id": "1808"}
                if character_name == "Magewinner" and slot == "finger1":
                    simc_options.update(
                        {
                            "gem_id": "240983",
                            "enchant_id": "7340",
                            "embellishment": "222873",
                        }
                    )
                rows.append(
                    (
                        f"variant-{character_name}-{slot}",
                        item_id,
                        f"Observed {character_name} {slot}",
                        slot,
                        707,
                        simc_options,
                        "verified",
                        [],
                        payload,
                        {},
                        updated_at,
                    )
                )
            return rows

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": [
                    *observed_rows(profile_a, "Magealpha", 410000, 2, 4100.0, "2026-07-05T00:00:00+00:00"),
                    *observed_rows(profile_b, "Magewinner", 420000, 1, 4300.0, "2026-07-05T01:00:00+00:00"),
                ],
                "FROM cache.websim_items": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_community_gear_templates(scan_run_id="scan-observed")

        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(template["classKey"], "mage")
        self.assertEqual(template["specKey"], "frost")
        self.assertEqual(template["sourceUrl"], profile_b)
        self.assertEqual(template["sampleCount"], 1)
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["scanRunId"], "scan-observed")
        self.assertTrue(template["profileHash"])
        self.assertTrue(template["gearHash"])
        self.assertTrue(all(item["itemId"].startswith("4200") for item in template["gearItems"]))
        finger = next(item for item in template["gearItems"] if item["slot"] == "finger1")
        self.assertEqual(finger["gem_id"], "240983")
        self.assertEqual(finger["enchant_id"], "7340")
        self.assertEqual(finger["embellishment"], "222873")

    def test_build_community_gear_templates_materializes_complete_raiderio_profiles(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        profile_url = "https://raider.io/characters/cn/the-masters-glaive/悲嘆之息"

        def profile_item(slot, index):
            item = {
                "slot": slot,
                "itemId": str(430000 + index),
                "name": f"Observed Priest {slot}",
                "itemLevel": 707,
                "bonuses": [{"id": 1808}],
            }
            if slot == "main_hand":
                item["weaponType"] = "Dagger"
            elif slot == "off_hand":
                item["weaponType"] = "Held In Off-hand"
            if slot == "finger1":
                item["gems"] = [{"item_id": 240983}]
                item["enchants"] = [{"enchant_id": 7340}]
                item["embellishment"] = "222873"
            return item

        raiderio_payload = {
            "sourceStatus": "verified",
            "checkedAt": "2026-07-08T08:00:00+00:00",
            "profiles": [
                {
                    "name": "悲嘆之息",
                    "region": "cn",
                    "realmSlug": "the-masters-glaive",
                    "classKey": "priest",
                    "specKey": "discipline",
                    "profileUrl": profile_url,
                    "rankingEvidence": {
                        "source": "raiderio_spec_ranking",
                        "rank": 3,
                        "score": 4201.5,
                    },
                    "gear": [profile_item(slot, index) for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)],
                }
            ],
        }
        aggregate_variant_rows = []
        for index, slot in enumerate(CANONICAL_GEAR_SLOTS[:8], start=1):
            aggregate_variant_rows.append(
                (
                    f"aggregate-{slot}",
                    str(440000 + index),
                    f"Aggregate {slot}",
                    slot,
                    707,
                    {"ilevel": "707", "bonus_id": "1808"},
                    "verified",
                    [],
                    {
                        "classKey": "priest",
                        "specKey": "discipline",
                        "statSource": "simulationcraft",
                        "itemStats": [{"key": "intellect", "value": 1000 + index}],
                        "profileUrl": f"https://raider.io/characters/cn/old-realm/partial-{slot}",
                    },
                    {},
                    "2026-07-07T00:00:00+00:00",
                )
            )

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": aggregate_variant_rows,
                "FROM cache.raiderio_cache": [
                    (raiderio_payload, "2026-07-08T08:00:00+00:00", "2099-01-01T00:00:00+00:00")
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_community_gear_templates(scan_run_id="scan-raiderio-profile")

        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(template["classKey"], "priest")
        self.assertEqual(template["specKey"], "discipline")
        self.assertEqual(template["sourceUrl"], profile_url)
        self.assertEqual(template["sampleCount"], 1)
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["scanRunId"], "scan-raiderio-profile")
        self.assertEqual(template["sourceRefs"][0]["characterName"], "悲嘆之息")
        self.assertEqual(template["sourceRefs"][0]["region"], "cn")
        self.assertEqual(template["sourceRefs"][0]["realmSlug"], "the-masters-glaive")
        self.assertTrue(template["profileHash"])
        self.assertTrue(template["gearHash"])
        self.assertTrue(all(item["itemId"].startswith("4300") for item in template["gearItems"]))
        finger = next(item for item in template["gearItems"] if item["slot"] == "finger1")
        self.assertEqual(finger["gem_id"], "240983")
        self.assertEqual(finger["enchant_id"], "7340")
        self.assertEqual(finger["embellishment"], "222873")

    def test_build_community_gear_templates_selects_top_profile_after_weapon_rule_update(self):
        from server.postgres_cache_store import PostgresCacheStore
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        def profile_gear(start, main_hand_id, off_hand_id=None):
            items = []
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1):
                if slot == "off_hand" and not off_hand_id:
                    continue
                item_id = main_hand_id if slot == "main_hand" else off_hand_id if slot == "off_hand" else str(start + index)
                items.append(
                    {
                        "slot": slot,
                        "itemId": item_id,
                        "name": f"Observed {slot}",
                        "itemLevel": 707,
                        "bonuses": [{"id": 1808}],
                    }
                )
            return items

        raiderio_payload = {
            "sourceStatus": "verified",
            "checkedAt": "2026-07-08T08:00:00+00:00",
            "profiles": [
                {
                    "name": "Topdagger",
                    "region": "us",
                    "realmSlug": "area-52",
                    "classKey": "hunter",
                    "specKey": "survival",
                    "profileUrl": "https://raider.io/characters/us/area-52/Topdagger",
                    "rankingEvidence": {"source": "raiderio_spec_ranking", "rank": 1, "score": 4300},
                    "gear": profile_gear(450000, "900001", "900002"),
                },
                {
                    "name": "Legalnext",
                    "region": "us",
                    "realmSlug": "area-52",
                    "classKey": "hunter",
                    "specKey": "survival",
                    "profileUrl": "https://raider.io/characters/us/area-52/Legalnext",
                    "rankingEvidence": {"source": "raiderio_spec_ranking", "rank": 2, "score": 4290},
                    "gear": profile_gear(460000, "900003"),
                },
            ],
        }
        item_rows = [
            (
                "900001",
                "Observed Dagger",
                "main_hand",
                707,
                {
                    "id": "900001",
                    "name": "Observed Dagger",
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 15, "name": "Dagger"},
                },
                "verified",
            ),
            (
                "900002",
                "Observed Offhand Dagger",
                "off_hand",
                707,
                {
                    "id": "900002",
                    "name": "Observed Offhand Dagger",
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 15, "name": "Dagger"},
                },
                "verified",
            ),
            (
                "900003",
                "Legal Polearm",
                "main_hand",
                707,
                {
                    "id": "900003",
                    "name": "Legal Polearm",
                    "inventory_type": {"type": "TWOHWEAPON", "name": "Two-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 6, "name": "Polearm"},
                },
                "verified",
            ),
        ]
        illegal_variant_rows = [
            (
                f"topdagger-{slot}",
                "900001" if slot == "main_hand" else "900002" if slot == "off_hand" else str(470000 + index),
                f"Illegal observed {slot}",
                slot,
                707,
                {"ilevel": "707", "bonus_id": "1808"},
                "verified",
                [],
                {
                    "classKey": "hunter",
                    "specKey": "survival",
                    "statSource": "simulationcraft",
                    "itemStats": [{"key": "agility", "value": 1000 + index}],
                    "profileUrl": "https://raider.io/characters/us/area-52/Topdagger",
                    "characterName": "Topdagger",
                    "region": "us",
                    "realmSlug": "area-52",
                    "rankingEvidence": {"source": "raiderio_spec_ranking", "rank": 1, "score": 4300},
                    "fetchedAt": "2026-07-08T08:00:00+00:00",
                    "scanRunId": "scan-old-variant",
                },
                {},
                "2026-07-08T07:00:00+00:00",
            )
            for index, slot in enumerate(CANONICAL_GEAR_SLOTS, start=1)
        ]

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": illegal_variant_rows,
                "FROM cache.websim_gear_variants WHERE source_type": [],
                "FROM cache.raiderio_cache": [
                    (raiderio_payload, "2026-07-08T08:00:00+00:00", "2099-01-01T00:00:00+00:00")
                ],
                "FROM cache.websim_items": item_rows,
            }
        )
        store = PostgresCacheStore(lambda: conn)

        templates = store.build_community_gear_templates(scan_run_id="scan-raiderio-profile")

        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["sourceUrl"], "https://raider.io/characters/us/area-52/Topdagger")
        self.assertEqual(template["sampleCount"], 1)
        self.assertEqual(template["status"], "complete")
        self.assertEqual(template["readySlotCount"], 16)
        self.assertEqual(template["missingSlots"], [])
        self.assertEqual(template["sourceRefs"][0]["characterName"], "Topdagger")

    def test_build_community_gear_templates_does_not_globally_truncate_observed_variants(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": [],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        store.build_community_gear_templates(scan_run_id="scan-observed")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertIn("FROM cache.websim_gear_variants v", sql)
        self.assertNotIn("LIMIT 4000", sql)

    def test_postgres_native_simc_generated_data_writer_uses_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_simc_generated_data(
            {
                "talents": [
                    {
                        "id": "talent-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "treeId": "tree-a",
                        "row": 1,
                        "col": 2,
                        "spellId": 123,
                        "name": "Talent A",
                        "payload": {"treeType": "spec"},
                    }
                ],
                "presets": [
                    {
                        "id": "preset-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "name": "Preset A",
                        "profile": "mage=frost",
                    }
                ],
                "spellDetails": [
                    {
                        "spellId": 123,
                        "name": "Talent A",
                        "description": "A spell",
                        "iconUrl": "https://example.test/icon.jpg",
                        "locale": "zh_CN",
                    }
                ],
                "source": "simc",
                "build": "simc-build",
            }
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["talents"], 1)
        self.assertEqual(counts["profiles"], 1)
        self.assertEqual(counts["presets"], 1)
        self.assertEqual(counts["spellDetails"], 1)
        self.assertIn("DELETE FROM cache.websim_talents", sql)
        self.assertIn("DELETE FROM cache.websim_profile_presets", sql)
        self.assertIn("INSERT INTO cache.websim_talents", sql)
        self.assertIn("INSERT INTO cache.websim_profile_presets", sql)
        self.assertIn("INSERT INTO cache.websim_spell_details", sql)
        self.assertIn("COALESCE(cache.websim_spell_details.payload_json->>'source', '') = 'simulationcraft'", sql)
        self.assertIn("ELSE cache.websim_spell_details.description", sql)

    def test_postgres_native_journal_writer_uses_cache_schema(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        counts = store.replace_websim_journal_data(
            {
                "season": {
                    "seasonId": "season-pg",
                    "seasonLabel": "Season PG",
                    "seasonRevision": "season-pg-rev",
                    "locale": "zh_CN",
                    "dataStatus": "verified",
                    "verifiedAt": "2026-07-03T01:00:00+00:00",
                    "expiresAt": "2026-07-04T01:00:00+00:00",
                    "sourceRefs": [{"source": "blizzard"}],
                    "dungeons": [
                        {
                            "id": "dungeon-a",
                            "instanceId": "1300",
                            "name": "Dungeon A",
                            "shortName": "DA",
                            "timerSeconds": 1800,
                        }
                    ],
                },
                "instances": [
                    {
                        "id": "1300",
                        "name": "Dungeon A",
                        "category": "Dungeon",
                        "encounters": [
                            {
                                "id": "9001",
                                "name": "Boss A",
                                "items": [
                                    {
                                        "id": "loot-1300-9001-111",
                                        "itemId": "111",
                                        "name": "Item A",
                                        "slot": "head",
                                        "quality": "epic",
                                        "iconUrl": "https://example.test/item-a.jpg",
                                        "payload": {"item_level": 678},
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(counts["dungeons"], 1)
        self.assertEqual(counts["instances"], 1)
        self.assertEqual(counts["encounters"], 1)
        self.assertEqual(counts["items"], 1)
        self.assertEqual(counts["loot"], 1)
        self.assertIn("DELETE FROM cache.websim_loot", sql)
        self.assertIn("DELETE FROM cache.websim_encounters", sql)
        self.assertIn("DELETE FROM cache.websim_instances", sql)
        self.assertIn("INSERT INTO cache.websim_season_state", sql)
        self.assertIn("INSERT INTO cache.websim_season_dungeons", sql)
        self.assertIn("INSERT INTO cache.websim_instances", sql)
        self.assertIn("INSERT INTO cache.websim_encounters", sql)
        self.assertIn("INSERT INTO cache.websim_items", sql)
        self.assertIn("INSERT INTO cache.websim_loot", sql)
        self.assertIn("cache.websim_items.payload_json #>> '{_metadata,source}'", sql)
        self.assertIn("cache.websim_items.payload_json ? 'inventory_type'", sql)
        self.assertIn("cache.websim_items.payload_json ? 'item_class'", sql)
        self.assertIn("THEN cache.websim_items.payload_json", sql)

    def test_postgres_native_gear_catalog_writer_derives_loot_sources(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_loot l": [
                    (
                        "loot-1300-9001-111",
                        "111",
                        "head",
                        "Item A",
                        "1300",
                        "Dungeon A",
                        "Dungeon",
                        "9001",
                        "Boss A",
                    ),
                    (
                        "loot-1301-9002-111",
                        "111",
                        "head",
                        "Item A",
                        "1301",
                        "Dungeon B",
                        "Dungeon",
                        "9002",
                        "Boss B",
                    )
                ]
            }
        )
        store = PostgresCacheStore(lambda: conn)

        state = store.rebuild_websim_gear_catalog_from_loot(
            {"seasonRevision": "season-pg-rev", "dataStatus": "verified"}
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(state["runner"], "postgres")
        self.assertEqual(state["itemCount"], 1)
        self.assertEqual(state["sourceCount"], 2)
        self.assertEqual(state["variantCount"], 1)
        self.assertEqual(state["partialCount"], 1)
        self.assertIn("INSERT INTO cache.websim_gear_sources", sql)
        self.assertIn("source_label, instance_id, encounter_id, difficulty_key, season_revision", sql)
        self.assertIn("INSERT INTO cache.websim_gear_variants", sql)
        self.assertIn("slot, label, source_type, difficulty_key, item_level, simc_options_json, status, blockers_json", sql)
        self.assertIn("INSERT INTO cache.websim_sync_state", sql)

    def test_postgres_native_gear_catalog_promotes_official_loot_from_observed_variant(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_loot l": [
                    (
                        "loot-1300-9001-111",
                        "111",
                        "head",
                        "Observed Hood",
                        "1300",
                        "Dungeon A",
                        "Dungeon",
                        "9001",
                        "Boss A",
                    )
                ],
                "FROM cache.websim_gear_variants v": [
                    (
                        "partial-111",
                        "111",
                        "head",
                        "dungeon",
                        {
                            "sourceKey": "loot:loot-1300-9001-111",
                            "sourceType": "dungeon",
                            "sourceLabel": "Boss A - Dungeon A",
                            "seasonRevision": "season-pg-rev",
                        },
                        {"inventory_type": {"type": "HEAD", "name": "Head"}},
                    )
                ],
                "WHERE source_type = 'observed_profile'": [
                    (
                        "observed-111",
                        "111",
                        "head",
                        "observed-707",
                        "Observed 707",
                        707,
                        {"bonus_id": "12345"},
                        {
                            "statSource": "simulationcraft",
                            "itemStats": [{"key": "intellect", "label": "智力", "value": 321}],
                            "statSummary": "智力 321",
                            "observedProfileRefs": [{"sourceName": "Raider.IO"}],
                            "classKeys": ["mage"],
                            "specKeys": ["frost"],
                        },
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        state = store.rebuild_websim_gear_catalog_from_loot(
            {"seasonRevision": "season-pg-rev", "dataStatus": "verified"}
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(state["verifiedCount"], 1)
        self.assertEqual(state["partialCount"], 0)
        self.assertEqual(state["variantCount"], 1)
        self.assertEqual(state["status"], "verified")
        self.assertTrue(any("observed_profile" in param for params in conn.cursor_instance.params for param in params if isinstance(param, str)))
        self.assertTrue(
            any(
                "observedVariantSource" in param and "simulationcraft" in param
                for params in conn.cursor_instance.params
                for param in params
                if isinstance(param, str)
            )
        )
        self.assertIn("DELETE FROM cache.websim_gear_variants WHERE id = ANY", sql)

    def test_gear_authority_context_loader_is_read_only_and_bounded(self):
        from server import postgres_cache_store

        class CountingConnection(FakeConnection):
            def __init__(self):
                super().__init__()
                self.cursor_calls = 0

            def cursor(self):
                self.cursor_calls += 1
                return super().cursor()

        conn = CountingConnection()
        store = postgres_cache_store.PostgresCacheStore(
            lambda: conn,
            gear_release_store=PreCutoverReleaseStore(),
        )
        intent = {"schemaRevision": "selection-intent-v1"}
        runtime_authority = {"dependencyRevisions": {"simcRuntimeRevision": "simc-v1"}}
        expected = {"contractRevision": "gear-authority-context-v1", "missingFields": []}

        def assert_read_only_then_delegate(cursor, selection_intent, authority, *, cache=None):
            self.assertIs(cursor, conn.cursor_instance)
            self.assertEqual(cursor.statements, ["SET TRANSACTION READ ONLY"])
            self.assertIs(selection_intent, intent)
            self.assertIs(authority, runtime_authority)
            self.assertIsInstance(cache, postgres_cache_store.AuthorityContextCache)
            self.assertLessEqual(cache.max_entries, 64)
            self.assertLessEqual(cache.max_bytes, 8 * 1024 * 1024)
            return expected

        with patch.object(
            postgres_cache_store,
            "load_gear_authority_context",
            side_effect=assert_read_only_then_delegate,
        ) as loader:
            result = store.get_gear_authority_context(intent, runtime_authority)

        self.assertEqual(result, expected)
        self.assertEqual(conn.cursor_calls, 1)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)
        loader.assert_called_once()

    def test_candidate_release_readers_delegate_to_single_release_repository(self):
        from server import postgres_cache_store

        class CandidateReleaseStore:
            def __init__(self):
                self.calls = []

            def load_candidate_authority_context(self, intent, runtime_authority, gear_release_id):
                self.calls.append(("authority", intent, runtime_authority, gear_release_id))
                return {
                    "manifest": {"gearCatalogReleaseId": gear_release_id},
                    "missingFields": [],
                }

            def load_community_release(self, gear_release_id, community_release_id):
                self.calls.append(("community", gear_release_id, community_release_id))
                return {"winners": [{"templateId": "winner-a"}]}

        release_store = CandidateReleaseStore()
        store = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("candidate facade must not open the staging store directly"),
            gear_release_store=release_store,
        )
        intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-r1",
                "gearCatalogRevision": "gear-release:a",
            },
            "eligibilityContext": {"classKey": "warrior", "specKey": "arms", "level": 80},
            "slots": {},
        }
        runtime = {"dependencyRevisions": {
            "gearRuleRevision": "rule-r1",
            "resolverContractRevision": "resolver-r1",
            "serializerRevision": "serializer-r1",
            "simcRuntimeRevision": "simc-r1",
            "statPolicyRevision": "stat-r1",
            "selectionSchemaRevision": "selection-intent-v1",
        }}

        authority = store.get_candidate_gear_authority_context(intent, runtime, "gear-release:a")
        cached_authority = store.get_candidate_gear_authority_context(intent, runtime, "gear-release:a")
        community = store.get_candidate_community_release("gear-release:a", "community-release:a")

        self.assertEqual(authority["manifest"]["gearCatalogReleaseId"], "gear-release:a")
        self.assertEqual(cached_authority, authority)
        self.assertEqual(community["winners"][0]["templateId"], "winner-a")
        self.assertEqual(store._gear_authority_context_cache.entry_count, 1)
        self.assertEqual(store.gear_authority_cache_metrics(), {
            "entryCount": 1,
            "byteSize": store._gear_authority_context_cache.byte_size,
            "maxEntries": 32,
            "maxBytes": 4 * 1024 * 1024,
        })
        self.assertEqual(release_store.calls, [
            ("authority", intent, runtime, "gear-release:a"),
            ("community", "gear-release:a", "community-release:a"),
        ])

    def test_formal_authority_reuses_binding_after_one_pointer_identity_query(self):
        from server import postgres_cache_store

        class ActiveReleaseStore:
            def __init__(self):
                self.generation = 9
                self.binding_calls = 0
                self.pointer_calls = 0
                self.authority_calls = 0

            def get_active_pointer(self):
                self.pointer_calls += 1
                return {
                    "pointerMode": "active",
                    "generation": self.generation,
                    "manifestRevision": f"manifest-{self.generation}",
                }

            def load_active_manifest_binding(self):
                self.binding_calls += 1
                return {
                    "pointerMode": "active",
                    "generation": self.generation,
                    "manifestRevision": f"manifest-{self.generation}",
                    "formalActiveManifest": True,
                    "manifest": {"manifestRevision": f"manifest-{self.generation}"},
                }

            def load_active_authority_context(self, intent, runtime_authority, binding):
                self.authority_calls += 1
                return {
                    "manifest": binding["manifest"],
                    "dependencyVector": runtime_authority["dependencyRevisions"],
                    "missingFields": [],
                }

        release_store = ActiveReleaseStore()
        store = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("formal authority must stay in the release repository"),
            gear_release_store=release_store,
        )
        intent = {"schemaRevision": "selection-intent-v1"}
        runtime = {"dependencyRevisions": {"simcRuntimeRevision": "simc-v1"}}

        first = store.get_gear_authority_context(intent, runtime)
        second = store.get_gear_authority_context(intent, runtime)
        release_store.generation = 10
        third = store.get_gear_authority_context(intent, runtime)

        self.assertEqual(first["manifest"]["manifestRevision"], "manifest-9")
        self.assertEqual(second["manifest"]["manifestRevision"], "manifest-9")
        self.assertEqual(third["manifest"]["manifestRevision"], "manifest-10")
        self.assertEqual(release_store.pointer_calls, 3)
        self.assertEqual(release_store.binding_calls, 2)
        self.assertEqual(release_store.authority_calls, 2)

    def test_gear_resolver_context_is_one_read_only_revision_query(self):
        from server import postgres_cache_store

        revision_row = (
            "season-17-active",
            {"status": "partial"},
            {"status": "partial"},
            10,
            "2026-07-10T10:00:00+00:00",
            20,
            "2026-07-10T10:01:00+00:00",
            5,
            "2026-07-10T10:02:00+00:00",
            12,
            "2026-07-10T10:03:00+00:00",
        )
        conn = FakeConnection(rows=[revision_row])
        store = postgres_cache_store.PostgresCacheStore(
            lambda: conn,
            gear_release_store=PreCutoverReleaseStore(),
        )
        runtime_authority = {"dependencyRevisions": {"simcRuntimeRevision": "simc-v1"}}
        expected = {
            "contractRevision": "gear-resolver-context-v1",
            "formalActiveManifest": False,
        }

        with patch.object(
            postgres_cache_store,
            "resolver_authoring_context",
            return_value=expected,
        ) as projector:
            result = store.get_gear_resolver_context(runtime_authority)

        self.assertEqual(result, expected)
        self.assertEqual(conn.cursor_instance.statements[0], "SET TRANSACTION READ ONLY")
        self.assertIn("gear_authority_revision", conn.cursor_instance.statements[1])
        self.assertEqual(len(conn.cursor_instance.statements), 2)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)
        projector.assert_called_once_with(revision_row, runtime_authority)

    def test_formal_manifest_routes_authority_and_resolver_context_to_exact_release_binding(self):
        from server import postgres_cache_store

        manifest = {
            "schemaRevision": "active-season-manifest-v1",
            "manifestRevision": "season-manifest:sha256:active",
            "seasonRevision": "season-r1",
            "gearCatalogReleaseId": "gear-release:active",
            "communityTemplateReleaseId": "community-release:active",
            "talentCatalogRevision": "talent-r1",
            "dependencyRevisions": {
                "gearRuleRevision": "rule-r1",
                "resolverContractRevision": "resolver-r1",
                "serializerRevision": "serializer-r1",
                "simcRuntimeRevision": "simc-r1",
                "statPolicyRevision": "stat-r1",
                "selectionSchemaRevision": "selection-intent-v1",
                "capabilityRevision": "capability-r1",
            },
            "rollbackManifestRevision": "",
            "formalActiveManifest": True,
        }
        binding = {
            "pointerMode": "active",
            "generation": 3,
            "manifestRevision": manifest["manifestRevision"],
            "formalActiveManifest": True,
            "manifest": manifest,
            "gearRelease": {"releaseId": "gear-release:active"},
            "communityRelease": {"releaseId": "community-release:active"},
        }

        class ActiveReleaseStore:
            def __init__(self):
                self.calls = []

            def load_active_manifest_binding(self):
                self.calls.append(("binding",))
                return binding

            def load_active_authority_context(self, intent, runtime_authority, exact_binding):
                self.calls.append(("authority", intent, runtime_authority, exact_binding))
                return {
                    "manifest": {"formalActiveManifest": True, "manifestRevision": manifest["manifestRevision"]},
                    "missingFields": [],
                }

            def active_resolver_context(self, exact_binding, runtime_authority):
                self.calls.append(("resolver", exact_binding, runtime_authority))
                return {
                    "contractRevision": "gear-resolver-context-v1",
                    "formalActiveManifest": True,
                    "manifestRevision": manifest["manifestRevision"],
                    "pointerGeneration": 3,
                    "authoredAgainst": {
                        "seasonRevision": "season-r1",
                        "gearCatalogRevision": "gear-release:active",
                    },
                }

            def load_active_public_gear(self, exact_binding, class_key, spec_key, *, include_catalog, catalog_slot=""):
                self.calls.append(("browse", exact_binding, class_key, spec_key, include_catalog, catalog_slot))
                return {
                    "gearRelease": {
                        "releaseId": "gear-release:active",
                        "releaseStatus": "validated",
                        "contentHash": "sha256:gear",
                    },
                    "communityRelease": {"releaseId": "community-release:active"},
                    "communityTemplates": [{
                        "id": "winner-a",
                        "classKey": class_key,
                        "specKey": spec_key,
                        "status": "complete",
                        "sourceStatus": "synced",
                        "gearItems": [],
                    }],
                    "gearSnapshot": None,
                }

            def load_community_release(self, gear_release_id, community_release_id):
                self.calls.append(("community", gear_release_id, community_release_id))
                return {
                    "gearRelease": {"releaseId": gear_release_id},
                    "communityRelease": {"releaseId": community_release_id},
                    "winners": [{
                        "templateId": "winner-a",
                        "classKey": "mage",
                        "specKey": "arcane",
                        "selectionIntent": {"schemaRevision": "selection-intent-v1"},
                    }],
                }

        release_store = ActiveReleaseStore()
        store = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("formal readers must not query mutable staging"),
            gear_release_store=release_store,
        )
        intent = {"schemaRevision": "selection-intent-v1"}
        runtime = {"dependencyRevisions": {"simcRuntimeRevision": "simc-r1"}}

        authority = store.get_gear_authority_context(intent, runtime)
        resolver = store.get_gear_resolver_context(runtime)
        browse = store.get_websim_gear("mage", "arcane", compact=True, mode="initial")
        cached_browse = store.get_websim_gear("mage", "arcane", compact=True, mode="initial")

        self.assertTrue(authority["manifest"]["formalActiveManifest"])
        self.assertTrue(resolver["formalActiveManifest"])
        self.assertEqual(resolver["pointerGeneration"], 3)
        self.assertTrue(browse["formalActiveManifest"])
        self.assertIs(browse["_activeManifestBinding"], binding)
        self.assertEqual(cached_browse["manifestRevision"], browse["manifestRevision"])
        self.assertEqual(release_store.calls, [
            ("binding",),
            ("authority", intent, runtime, binding),
            ("binding",),
            ("resolver", binding, runtime),
            ("binding",),
            ("browse", binding, "mage", "arcane", False, ""),
            ("binding",),
        ])

        same_resolver = store.get_gear_resolver_context(runtime, binding=binding)
        self.assertEqual(same_resolver["manifestRevision"], manifest["manifestRevision"])
        self.assertEqual(release_store.calls[-1], ("resolver", binding, runtime))

        active_pair = store.get_active_community_release()
        self.assertTrue(active_pair["formalActiveManifest"])
        self.assertEqual(
            active_pair["winners"][0]["selectionIntent"],
            {"schemaRevision": "selection-intent-v1"},
        )
        self.assertNotIn("selectionIntent", json.dumps(browse, sort_keys=True))
        self.assertEqual(release_store.calls[-2:], [
            ("binding",),
            ("community", "gear-release:active", "community-release:active"),
        ])

    def test_transitional_manifest_binding_keeps_staging_authority_explicit(self):
        from server import postgres_cache_store

        class TransitionalReleaseStore:
            def load_active_manifest_binding(self):
                return {
                    "pointerMode": "transitional",
                    "generation": 2,
                    "formalActiveManifest": False,
                }

        revision_row = (
            "season-17-active", {"status": "partial"}, {"status": "partial"},
            10, "2026-07-10T10:00:00+00:00", 20, "2026-07-10T10:01:00+00:00",
            5, "2026-07-10T10:02:00+00:00", 12, "2026-07-10T10:03:00+00:00",
        )
        conn = FakeConnection(rows=[revision_row])
        store = postgres_cache_store.PostgresCacheStore(
            lambda: conn,
            gear_release_store=TransitionalReleaseStore(),
        )
        runtime = {"dependencyRevisions": {"simcRuntimeRevision": "simc-r1"}}
        with patch.object(
            postgres_cache_store,
            "resolver_authoring_context",
            return_value={"formalActiveManifest": False},
        ):
            resolver = store.get_gear_resolver_context(runtime)

        self.assertFalse(resolver["formalActiveManifest"])
        self.assertIn("gear_authority_revision", conn.cursor_instance.statements[1])

    def test_active_manifest_health_distinguishes_formal_transitional_and_invalid_states(self):
        from server import postgres_cache_store

        active_binding = {
            "pointerMode": "active",
            "generation": 3,
            "manifestRevision": "season-manifest:sha256:active",
            "rollbackManifestRevision": "season-manifest:sha256:old",
            "formalActiveManifest": True,
            "manifest": {
                "seasonRevision": "season-r1",
                "gearCatalogReleaseId": "gear-release:active",
                "communityTemplateReleaseId": "community-release:active",
                "talentCatalogRevision": "talent-r1",
            },
        }

        class ReleaseStore:
            def __init__(self, value=None, error=None):
                self.value = value
                self.error = error

            def load_active_manifest_binding(self):
                if self.error:
                    raise self.error
                return self.value

        active = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("health must use release repository"),
            gear_release_store=ReleaseStore(active_binding),
        ).active_manifest_health()
        transitional = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("health must use release repository"),
            gear_release_store=ReleaseStore({
                "pointerMode": "transitional",
                "generation": 4,
                "formalActiveManifest": False,
            }),
        ).active_manifest_health()
        invalid = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("health must use release repository"),
            gear_release_store=ReleaseStore(error=RuntimeError("corrupt pointer")),
        ).active_manifest_health()

        self.assertEqual(active["status"], "verified")
        self.assertEqual(active["details"]["pointerGeneration"], 3)
        self.assertEqual(active["details"]["gearCatalogReleaseId"], "gear-release:active")
        self.assertEqual(transitional["status"], "partial")
        self.assertEqual(transitional["details"]["pointerMode"], "transitional")
        self.assertTrue(transitional["blockers"])
        self.assertEqual(invalid["status"], "blocked")
        self.assertTrue(invalid["blockers"])

    def test_release_refresh_health_combines_active_pointer_latest_candidate_and_timer_policy(self):
        from server import postgres_cache_store

        class ReleaseStore:
            def load_active_manifest_binding(self):
                return {
                    "pointerMode": "active",
                    "generation": 10,
                    "manifestRevision": "season-manifest:active",
                    "formalActiveManifest": True,
                    "manifest": {
                        "seasonRevision": "season-17",
                        "gearCatalogReleaseId": "gear-release:active",
                        "communityTemplateReleaseId": "community-release:active",
                        "talentCatalogRevision": "talent-r1",
                    },
                }

            def latest_refresh_state(self):
                return {
                    "eventType": "gear_release_refresh_completed",
                    "status": "promoted",
                    "checkedAt": "2026-07-11T12:00:00+00:00",
                    "gearReleaseId": "gear-release:candidate",
                    "communityReleaseId": "community-release:candidate",
                    "manifestRevision": "season-manifest:candidate",
                    "riskClass": "same_gear_community",
                    "decision": "auto_promote",
                    "blockerCodes": [],
                    "counts": {"winner": 40, "standby": 0, "rejected": 319, "empty": 0},
                    "gearChange": {"addedCounts": {"items": 2}},
                    "sealStatus": {"gear": "inserted", "community": "inserted"},
                    "shadowStatus": "pass",
                    "shadowSpecCount": 40,
                    "shadowPerformance": {"specP95Ms": 123.4},
                }

        health = postgres_cache_store.PostgresCacheStore(
            lambda: self.fail("health must use release repository"),
            gear_release_store=ReleaseStore(),
        ).release_refresh_health()

        self.assertEqual(health["status"], "verified")
        self.assertEqual(health["details"]["pointerGeneration"], 10)
        self.assertEqual(health["details"]["candidateManifestRevision"], "season-manifest:candidate")
        self.assertEqual(health["details"]["counts"]["winner"], 40)
        self.assertEqual(health["details"]["gearChange"]["addedCounts"]["items"], 2)
        self.assertEqual(health["details"]["sealStatus"]["gear"], "inserted")
        self.assertEqual(health["details"]["shadowStatus"], "pass")
        self.assertEqual(health["details"]["shadowSpecCount"], 40)
        self.assertEqual(health["details"]["shadowPerformance"]["specP95Ms"], 123.4)
        self.assertEqual(health["details"]["timer"]["nextRunAuthority"], "systemd")
        self.assertFalse(health["details"]["timer"]["deployStartsService"])

    def test_gear_resolver_context_rolls_back_projection_failure(self):
        from server import postgres_cache_store

        conn = FakeConnection(rows=[("season-17-active",)])
        store = postgres_cache_store.PostgresCacheStore(
            lambda: conn,
            gear_release_store=PreCutoverReleaseStore(),
        )

        with patch.object(
            postgres_cache_store,
            "resolver_authoring_context",
            side_effect=RuntimeError("revision projection failed"),
        ):
            with self.assertRaises(RuntimeError):
                store.get_gear_resolver_context({})

        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)

    def test_gear_authority_context_loader_rolls_back_transient_failure(self):
        from server import postgres_cache_store

        conn = FakeConnection()
        store = postgres_cache_store.PostgresCacheStore(
            lambda: conn,
            gear_release_store=PreCutoverReleaseStore(),
        )

        with patch.object(
            postgres_cache_store,
            "load_gear_authority_context",
            side_effect=RuntimeError("transient authority read failure"),
        ):
            with self.assertRaises(RuntimeError):
                store.get_gear_authority_context({}, {})

        self.assertTrue(conn.rolled_back)
        self.assertFalse(conn.committed)
        self.assertEqual(conn.cursor_instance.statements[0], "SET TRANSACTION READ ONLY")


if __name__ == "__main__":
    unittest.main()

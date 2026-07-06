import unittest
import uuid
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
                self.current_rows = list(rows)
                break

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
        self.assertEqual(payload["communityTemplates"][0]["status"], "pending_collection")
        self.assertEqual(len(payload["baselineTemplates"]), 1)
        baseline = payload["baselineTemplates"][0]
        self.assertEqual(baseline["sourceKey"], "baseline_blocked")
        self.assertEqual(baseline["sourceStatus"], "blocked")
        self.assertEqual(baseline["status"], "blocked")
        self.assertEqual(baseline["templateSlot"], "baseline")
        self.assertFalse(baseline["canApplyGear"])
        self.assertEqual(baseline["gearItems"], [])
        self.assertEqual(baseline["readySlotCount"], 0)
        self.assertEqual(len(baseline["missingSlots"]), 16)
        self.assertEqual(baseline.get("blockers"), ["No baseline gear template is available for this spec."])
        self.assertIn("deterministic baseline gear template", baseline.get("nextAction", ""))
        self.assertNotIn("payload", baseline)
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
                        "https://example.test/gear-observed",
                        "partial",
                        "partial",
                        "sig-gear-b",
                        [{"type": "raiderio"}],
                        [{"slot": "head", "itemId": "250101", "simcReady": True}],
                        "head=template_helm,id=250101,ilevel=289",
                        1,
                        ["neck"],
                        "observed",
                        {},
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
        self.assertEqual(len(payload["communityTemplates"]), 1)
        template = payload["communityTemplates"][0]
        self.assertEqual(template["id"], "55555555-5555-4555-8555-555555555555")
        self.assertEqual(template["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(template["status"], "partial")
        self.assertTrue(template["canApplyGear"])
        self.assertEqual(len(payload["baselineTemplates"]), 1)
        baseline = payload["baselineTemplates"][0]
        self.assertEqual(baseline["id"], "44444444-4444-4444-8444-444444444444")
        self.assertEqual(baseline["sourceKey"], "simc_preset")
        self.assertEqual(baseline["status"], "complete")
        self.assertEqual(baseline["scenarioKey"], "mplus_mixed_route")
        self.assertEqual(payload["communityTemplateSync"]["templates"]["partial"], 1)
        self.assertIn("FROM cache.websim_community_gear_templates", sql)

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
        self.assertEqual(
            [template["id"] for template in payload["baselineTemplates"]],
            ["mage_fire_mid1_mage_fire_sunfury"],
        )
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
                        "https://example.test/gear-observed",
                        "partial",
                        "partial",
                        "sig-gear-blood",
                        [{"type": "raiderio"}],
                        community_items,
                        "\n".join(raw_lines),
                        15,
                        ["off_hand"],
                        "observed",
                        {},
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
                        "https://example.test/gear-observed",
                        "partial",
                        "partial",
                        "sig-gear-restoration",
                        [{"type": "raiderio"}],
                        community_items,
                        "\n".join(raw_lines),
                        15,
                        ["off_hand"],
                        "observed",
                        {},
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

        baseline = payload["baselineTemplates"][0]
        self.assertEqual(baseline["status"], "complete")
        self.assertEqual(baseline["sourceStatus"], "synced")
        self.assertEqual(baseline["readySlotCount"], 16)
        self.assertEqual(baseline["missingSlots"], [])
        self.assertEqual(baseline["gearItems"][-1]["weaponType"], "Staff")
        self.assertEqual(
            baseline["occupiedSlots"]["off_hand"],
            {
                "slot": "off_hand",
                "occupiedBy": "main_hand",
                "reason": "two_hand_main_hand",
            },
        )

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
        self.assertIn("SELECT id, class_key, spec_key, gear_items_json FROM cache.websim_community_gear_templates", sql)
        self.assertIn("cache.websim_community_gear_templates.id = ANY", sql)
        self.assertTrue(
            any(
                "observed-profile-mage-frost" in value
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

        def row(template_id, class_key, spec_key, source_key, status, ready, missing, scan_run_id, expires_at=None):
            return (
                template_id,
                class_key,
                spec_key,
                template_id,
                source_key,
                source_key,
                "",
                "synced" if status == "complete" else "partial",
                status,
                template_id,
                [],
                [{"slot": "head", "itemId": "190001", "simcReady": True}],
                "head=item,id=190001",
                ready,
                missing,
                "test window",
                {},
                "2026-07-05T00:00:00+00:00",
                expires_at,
                scan_run_id,
            )

        conn = FakeConnection(
            rowsets={
                "SELECT to_regclass": [("cache.websim_community_gear_templates",)],
                "FROM cache.websim_community_gear_templates": [
                    row("observed-mage-fire", "mage", "fire", "raiderio_observed_profile", "complete", 16, [], "scan-live"),
                    row("observed-monk-windwalker", "monk", "windwalker", "raiderio_observed_profile", "partial", 15, ["trinket2"], "scan-live"),
                    row("baseline-mage-fire", "mage", "fire", "simc_preset", "complete", 16, [], "scan-live"),
                    row("baseline-monk-windwalker", "monk", "windwalker", "simc_preset", "partial", 10, ["trinket2"], "scan-live"),
                    row("expired-baseline-monk-windwalker", "monk", "windwalker", "simc_preset", "partial", 1, ["head"], "scan-expired", "2020-01-01T00:00:00+00:00"),
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        with patch("server.postgres_cache_store.expected_spec_pairs", return_value=["mage:fire", "monk:windwalker"]):
            summary = store.community_gear_template_live_health_summary()

        self.assertEqual(summary["templates"], {"total": 4, "verified": 2, "partial": 2, "blocked": 0})
        self.assertEqual(summary["realCommunityTemplates"]["coveredSpecCount"], 1)
        self.assertEqual(summary["realCommunityTemplates"]["partialSpecCount"], 1)
        self.assertEqual(summary["baselineTemplates"]["availableSpecCount"], 2)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["totalSlotCount"], 32)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["readySlotCount"], 31)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["missingSlotCount"], 1)
        self.assertEqual(summary["preflight"]["canonicalSlotMatrix"]["missingBySlot"], {"trinket2": 1})

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
        self.assertIn("THEN cache.websim_items.payload_json", sql)
        self.assertIn("ELSE EXCLUDED.payload_json", sql)

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

    def test_build_community_gear_templates_uses_trusted_observed_variants(self):
        from server.postgres_cache_store import PostgresCacheStore

        conn = FakeConnection(
            rowsets={
                "FROM cache.websim_profile_presets": [],
                "FROM cache.websim_gear_variants v": [
                    (
                        "variant-a",
                        "190001",
                        "Observed Helm",
                        "head",
                        707,
                        {"ilevel": "707", "bonus_id": "1808"},
                        "verified",
                        [],
                        {
                            "classKey": "mage",
                            "specKey": "frost",
                            "statSource": "simulationcraft",
                            "itemStats": [{"key": "intellect", "value": 1000}],
                            "profileUrl": "https://raider.io/characters/cn/realm/MageA",
                        },
                        {},
                        "2026-07-05T00:00:00+00:00",
                    ),
                    (
                        "variant-untrusted",
                        "190002",
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
        self.assertEqual(template["readySlotCount"], 1)
        self.assertEqual(template["status"], "partial")
        self.assertEqual(template["scanRunId"], "scan-observed")
        self.assertEqual([item["itemId"] for item in template["gearItems"]], ["190001"])
        self.assertIn("FROM cache.websim_gear_variants v", sql)

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


if __name__ == "__main__":
    unittest.main()

import unittest


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
        self.assertEqual(payload["talentStatus"], "verified")
        self.assertEqual(payload["nodes"][0]["id"], "talent-a")
        self.assertEqual(payload["nodes"][0]["descriptionStatus"], "ready")
        self.assertEqual(payload["presets"][0]["id"], "preset-a")
        self.assertEqual(payload["communityTemplates"][0]["id"], "44444444-4444-4444-8444-444444444444")
        self.assertEqual(payload["communityTemplateSync"]["templates"]["verified"], 1)
        self.assertIn("FROM cache.websim_talents", sql)
        self.assertIn("FROM cache.websim_profile_presets", sql)
        self.assertIn("FROM cache.websim_community_talent_templates", sql)


if __name__ == "__main__":
    unittest.main()

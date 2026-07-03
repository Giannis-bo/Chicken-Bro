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
        self.assertEqual(payload["communityTemplates"], [])
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

    def test_gear_read_model_exposes_pg_community_templates_for_import(self):
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
                    )
                ],
            }
        )
        store = PostgresCacheStore(lambda: conn)

        payload = store.get_websim_gear("mage", "frost", compact=True)

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertTrue(payload["communityTemplates"])
        template = payload["communityTemplates"][0]
        self.assertEqual(template["id"], "44444444-4444-4444-8444-444444444444")
        self.assertEqual(template["status"], "complete")
        self.assertTrue(template["canApplyGear"])
        self.assertEqual(template["scenarioKey"], "mplus_mixed_route")
        self.assertEqual(payload["communityTemplateSync"]["templates"]["verified"], 1)
        self.assertIn("FROM cache.websim_community_gear_templates", sql)

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
        self.assertEqual(payload["source"], "community_template")
        self.assertEqual(payload["status"], "verified")
        self.assertNotIn("FROM cache.websim_talents", sql)

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
        self.assertNotIn("FROM cache.websim_gear_variants", sql)

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

        conn = FakeConnection()
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

        conn = FakeConnection()
        store = PostgresCacheStore(lambda: conn)

        talent_counts = store.replace_community_talent_templates(
            [
                {
                    "id": "template-a",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "spellslinger",
                    "scenarioKey": "mythic_plus",
                    "name": "Template A",
                    "flowLabel": "主流",
                    "sourceKey": "raiderio",
                    "sourceName": "Raider.IO",
                    "sourceUrl": "https://raider.io/template-a",
                    "rawImportCode": "CAE_FAKE",
                    "websimExportCode": "",
                    "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                    "sampleCount": 3,
                    "maxKeyLevel": 12,
                    "analysisWindow": "test window",
                    "sourceStatus": "verified",
                    "status": "verified",
                    "payload": {"playerId": "Mage A"},
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
        self.assertEqual(talent_counts["blocked"], 1)
        self.assertEqual(gear_counts["partial"], 1)
        self.assertIn("INSERT INTO cache.websim_community_talent_templates", sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", sql)
        self.assertIn("INSERT INTO cache.websim_community_gear_templates", sql)
        self.assertTrue(conn.committed)

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

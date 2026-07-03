import json
import unittest
from unittest.mock import patch


class FakePostgresSyncStore:
    def __init__(self):
        self.replaced_data = None
        self.saved_states = []
        self.stat_payloads = []
        self.stat_previous = {}
        self.raiderio_payload = {}
        self.community_talent_templates = []
        self.community_gear_templates = []
        self.observed_backfills = []
        self.crafted_backfills = []
        self.gear_template_candidates = []

    def replace_simc_generated_data(self, data):
        self.replaced_data = data
        return {
            "talents": len(data.get("talents") or []),
            "profiles": len(data.get("presets") or []),
            "spellDetails": len(data.get("spellDetails") or []),
            "build": data.get("build") or "",
            "source": data.get("source") or "",
            "traitEdgeSource": data.get("traitEdgeSource") or "",
        }

    def replace_websim_journal_data(self, data):
        self.journal_data = data
        return {
            "dungeons": len((data.get("season") or {}).get("dungeons") or []),
            "instances": len(data.get("instances") or []),
            "encounters": 1,
            "items": 1,
            "loot": 1,
        }

    def rebuild_websim_gear_catalog_from_loot(self, season):
        self.gear_catalog_season = season
        return {"runner": "postgres", "status": "partial", "sourceCount": 1, "variantCount": 1, "blockers": []}

    def get_active_season_payload(self):
        return {"dataStatus": "verified", "seasonRevision": "season-pg"}

    def get_sync_state(self, key):
        if key == "gearCatalog":
            return {"status": "verified", "blockers": []}
        return {}

    def community_talent_template_counts(self):
        return {"total": 2, "verified": 2, "partial": 0, "blocked": 0}

    def community_gear_template_counts(self):
        return {"total": 1, "verified": 0, "partial": 1, "blocked": 0}

    def replace_community_talent_templates(self, templates, scan_run_id=""):
        self.community_talent_templates.extend(templates)
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            status = template.get("status") or "blocked"
            bucket = "verified" if status in {"verified", "complete"} else ("partial" if status == "partial" else "blocked")
            counts["total"] += 1
            counts[bucket] += 1
        return counts

    def replace_community_gear_templates(self, templates, scan_run_id=""):
        self.community_gear_templates.extend(templates)
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            status = template.get("status") or "blocked"
            bucket = "verified" if status in {"verified", "complete"} else ("partial" if status == "partial" else "blocked")
            counts["total"] += 1
            counts[bucket] += 1
        return counts

    def build_community_gear_templates(self, scan_run_id=""):
        return self.gear_template_candidates

    def backfill_observed_gear_from_raiderio(self, raiderio_payload, mode="scheduled"):
        self.observed_backfills.append((raiderio_payload, mode))
        return {"status": "verified", "sourceStatus": "verified", "observedProfileCount": 1, "variantCount": 2, "errors": []}

    def backfill_crafted_gear_from_seed(self, items, mode="scheduled"):
        self.crafted_backfills.append((items, mode))
        return {"status": "partial", "sourceStatus": "partial", "itemCount": len(items), "variantCount": 1, "errors": []}

    def get_raiderio_payload(self):
        return self.raiderio_payload

    def get_stat_weight_payload(self, class_key, spec_key, scenario_key):
        return self.stat_previous.get((class_key, spec_key, scenario_key))

    def save_stat_weight_payload(self, payload):
        self.stat_payloads.append(payload)
        return {"ok": True}

    def save_sync_state(self, key, value, updated_at=""):
        self.saved_states.append((key, value, updated_at))
        return {"ok": True}


class PostgresCacheSyncTest(unittest.TestCase):
    def test_websim_postgres_sync_replaces_simc_generated_data(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = {
            "talents": [{"id": "talent-a"}],
            "presets": [{"id": "preset-a"}],
            "spellDetails": [{"spellId": 123}],
            "source": "simc",
            "build": "simc-build",
        }

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIs(store.replaced_data, simc_data)
        self.assertEqual(payload["simc"]["talents"], 1)
        self.assertEqual(payload["simc"]["profiles"], 1)
        self.assertEqual(payload["simc"]["build"], "simc-build")
        self.assertEqual(store.saved_states[-1][0], "websim_sync")
        self.assertEqual(store.saved_states[-1][1]["runner"], "postgres")

    def test_websim_postgres_sync_writes_blizzard_journal_when_enabled(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        journal_data = {
            "season": {"seasonRevision": "season-pg-rev", "dataStatus": "verified", "dungeons": [{}]},
            "instances": [{"id": "1300", "encounters": [{"id": "9001", "items": [{"itemId": "111"}]}]}],
        }

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value={"talents": [], "presets": []}), patch.object(
            postgres_cache_sync,
            "fetch_websim_journal_data_postgres",
            return_value=journal_data,
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(include_blizzard=True, store=store)

        self.assertIs(store.journal_data, journal_data)
        self.assertEqual(payload["blizzard"]["runner"], "postgres")
        self.assertEqual(payload["blizzard"]["loot"], 1)
        self.assertEqual(payload["gearCatalog"]["sourceCount"], 1)

    def test_community_postgres_sync_saves_legacy_compatible_talent_state(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()

        with patch.object(postgres_cache_sync, "load_community_talent_sources_postgres", return_value={}):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store)
        saved = {key: value for key, value, _updated_at in store.saved_states}

        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["runner"], "postgres")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sourceStatus"], "verified")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["templates"]["total"], 2)
        self.assertIn("checkedAt", saved[COMMUNITY_TALENT_SYNC_KEY])

    def test_community_postgres_sync_writes_talent_templates_from_sources(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-template-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "spellslinger",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "blocked",
                "sourceName": "Warcraft Logs",
                "templates": [
                    {
                        "id": "wcl-template-blocked",
                        "classKey": "mage",
                        "specKey": "frost",
                        "status": "blocked",
                        "payload": {"errors": ["missing report seed"]},
                    }
                ],
                "errors": ["missing report seed"],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store)

        self.assertEqual(len(store.community_talent_templates), 2)
        self.assertEqual(
            {template["sourceKey"] for template in store.community_talent_templates},
            {"raiderio", "warcraftlogs"},
        )
        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 1)
        self.assertEqual(payload["sourceStatus"], "partial")

    def test_community_postgres_sync_keeps_source_errors_partial_when_rows_are_verified(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-template-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "spellslinger",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "blocked",
                "sourceName": "Warcraft Logs",
                "templates": [],
                "errors": ["missing combatantinfo report extraction"],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store)
        saved = {key: value for key, value, _updated_at in store.saved_states}

        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 0)
        self.assertEqual(payload["sourceStatus"], "partial")
        self.assertIn("warcraftlogs: missing combatantinfo report extraction", payload["errors"])
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sourceStatus"], "partial")

    def test_community_postgres_sync_writes_gear_templates_when_candidates_exist(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.gear_template_candidates = [
            {
                "id": "gear-template-a",
                "classKey": "mage",
                "specKey": "frost",
                "status": "complete",
                "gearItems": [{"slot": "head", "itemId": "190001", "ilevel": 707, "simcReady": True}],
            }
        ]

        with patch.object(postgres_cache_sync, "load_community_talent_sources_postgres", return_value={}):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store)

        self.assertEqual(len(store.community_gear_templates), 1)
        self.assertEqual(payload["gear"]["templates"]["verified"], 1)
        self.assertEqual(payload["sourceStatus"], "verified")

    def test_observed_backfill_postgres_calls_row_writer(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "verified",
            "profiles": [{"name": "Mage A", "gear": [{"itemId": "190001", "slot": "head", "ilevel": 707}]}],
        }

        payload = postgres_cache_sync.run_gear_observed_backfill_postgres(mode="scheduled", store=store)

        self.assertEqual(len(store.observed_backfills), 1)
        self.assertEqual(store.observed_backfills[0][0], store.raiderio_payload)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["sourceStatus"], "verified")
        self.assertNotIn("not implemented", json.dumps(payload))
        self.assertEqual(store.saved_states[-1][0], postgres_cache_sync.GEAR_OBSERVED_BACKFILL_SYNC_KEY)

    def test_crafted_backfill_postgres_calls_seed_row_writer(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        seed_items = [{"itemId": "260100", "slot": "main_hand", "itemLevel": 285, "crafted_stats": "32/49"}]

        with patch.object(postgres_cache_sync, "load_crafted_gear_seed_postgres", return_value=seed_items, create=True):
            payload = postgres_cache_sync.run_crafted_gear_backfill_postgres(mode="scheduled", store=store)

        self.assertEqual(len(store.crafted_backfills), 1)
        self.assertEqual(store.crafted_backfills[0][0], seed_items)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["sourceStatus"], "partial")
        self.assertNotIn("not implemented", json.dumps(payload))
        self.assertEqual(store.saved_states[-1][0], postgres_cache_sync.CRAFTED_GEAR_BACKFILL_SYNC_KEY)

    def test_stat_weight_postgres_sync_builds_and_writes_pg_payloads(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        previous_mixed = {
            "classKey": "mage",
            "specKey": "frost",
            "scenarioKey": "mplus_mixed_route",
            "summaryZh": "cached translation",
            "sourceStatus": "verified",
        }
        store.stat_previous[("mage", "frost", "mplus_mixed_route")] = previous_mixed
        spec_meta = {
            "classKey": "mage",
            "specKey": "frost",
            "className": "法师",
            "specName": "冰霜",
            "role": "dps",
            "primaryStat": "intellect",
        }
        raiderio_payload = {"sourceStatus": "verified", "checkedAt": "2026-07-03T00:00:00+00:00"}
        previous_seen = []

        def fake_builder(spec, scenario, raiderio, aggregate, ready_profiles, blocked_notes, previous=None):
            previous_seen.append((scenario["key"], previous))
            self.assertEqual(spec, spec_meta)
            self.assertEqual(raiderio, raiderio_payload)
            self.assertEqual(aggregate["sampleCount"], 5)
            self.assertEqual(len(ready_profiles), 1)
            self.assertEqual(blocked_notes, [])
            return {
                "classKey": spec["classKey"],
                "specKey": spec["specKey"],
                "scenarioKey": scenario["key"],
                "sourceStatus": "verified",
                "checkedAt": "2026-07-03T00:01:00+00:00",
                "weights": [{"key": "haste", "value": "1.00"}],
            }

        with patch.object(postgres_cache_sync, "specialization_registry", return_value=[spec_meta]), patch.object(
            postgres_cache_sync,
            "aggregate_by_spec",
            return_value={"mage:frost": {"sampleCount": 5}},
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "representative_profile_candidates",
            return_value=[{"name": "Mage A"}],
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "ready_profile_candidate",
            return_value={"ready": True, "name": "Mage A", "importCode": "CAE", "gearItems": []},
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "build_scenario_payload_with_previous",
            side_effect=fake_builder,
            create=True,
        ):
            result = postgres_cache_sync.sync_stat_weight_cache_postgres(
                raiderio_payload=raiderio_payload,
                store=store,
            )

        self.assertEqual(len(store.stat_payloads), len(postgres_cache_sync.MPLUS_SCENARIOS))
        self.assertEqual({item["sourceStatus"] for item in store.stat_payloads}, {"verified"})
        self.assertFalse(
            any("PostgreSQL-native stat weight evidence has not been produced yet" in json.dumps(item) for item in store.stat_payloads)
        )
        self.assertEqual(result["acceptedCount"], len(postgres_cache_sync.MPLUS_SCENARIOS))
        self.assertEqual(result["blockedCount"], 0)
        self.assertEqual(result["sourceStatus"], "verified")
        self.assertIn(("mplus_mixed_route", previous_mixed), previous_seen)
        self.assertEqual(store.saved_states[-1][0], "stat_weights_sync")


if __name__ == "__main__":
    unittest.main()

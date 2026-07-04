import json
import os
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
        self.expired_talent_source_keys = []
        self.saved_raiderio_payloads = []
        self.coverage_rows = []
        self.talent_replace_target_slot_ids = None

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

    def replace_community_talent_templates(self, templates, scan_run_id="", include_details=False, target_slot_ids=None):
        self.community_talent_templates.extend(templates)
        self.talent_replace_target_slot_ids = list(target_slot_ids or [])
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            status = template.get("status") or "blocked"
            bucket = "verified" if status in {"verified", "complete"} else ("partial" if status == "partial" else "blocked")
            counts["total"] += 1
            counts[bucket] += 1
        if include_details:
            counts["validatedTemplates"] = [dict(template) for template in templates]
        return counts

    def community_talent_template_coverage_rows(self):
        return [dict(row) for row in self.coverage_rows]

    def replace_community_gear_templates(self, templates, scan_run_id=""):
        self.community_gear_templates.extend(templates)
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            status = template.get("status") or "blocked"
            bucket = "verified" if status in {"verified", "complete"} else ("partial" if status == "partial" else "blocked")
            counts["total"] += 1
            counts[bucket] += 1
        return counts

    def expire_community_talent_template_sources(self, source_keys, expired_at=""):
        self.expired_talent_source_keys.extend(source_keys or [])
        return {"expired": len(source_keys or [])}

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

    def save_raiderio_payload(self, payload):
        self.saved_raiderio_payloads.append(dict(payload or {}))
        self.raiderio_payload = dict(payload or {})
        return {"ok": True, "cacheKey": "raiderio_payload_v1", "fetchedAt": (payload or {}).get("checkedAt") or ""}

    def get_stat_weight_payload(self, class_key, spec_key, scenario_key):
        return self.stat_previous.get((class_key, spec_key, scenario_key))

    def save_stat_weight_payload(self, payload):
        self.stat_payloads.append(payload)
        return {"ok": True}

    def save_sync_state(self, key, value, updated_at=""):
        self.saved_states.append((key, value, updated_at))
        return {"ok": True}


class PostgresCacheSyncTest(unittest.TestCase):
    def test_raiderio_postgres_sync_fetches_fresh_payload_before_saving(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "stale",
            "status": "stale",
            "checkedAt": "old-cache",
            "communityTemplates": [],
        }
        fresh_payload = {
            "sourceStatus": "synced",
            "status": "synced",
            "checkedAt": "fresh-cache",
            "runCount": 1,
            "profileCount": 1,
            "communityTemplates": [{"id": "fresh-template"}],
        }

        def fake_sync(conn, force=False, stage_callback=None):
            self.assertIsNotNone(conn)
            return fresh_payload

        with patch.object(postgres_cache_sync, "sync_raiderio_cache", side_effect=fake_sync, create=True):
            payload = postgres_cache_sync.sync_raiderio_cache_postgres(store=store)

        self.assertEqual(payload["checkedAt"], "fresh-cache")
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(store.saved_raiderio_payloads[-1]["checkedAt"], "fresh-cache")
        self.assertEqual(store.saved_raiderio_payloads[-1]["communityTemplates"][0]["id"], "fresh-template")

    def test_community_postgres_sync_refreshes_raiderio_before_loading_sources(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "stale",
            "status": "stale",
            "checkedAt": "old-cache",
            "communityTemplates": [],
        }
        fresh_template = {
            "id": "rio-fresh-rider",
            "classKey": "deathknight",
            "specKey": "unholy",
            "heroKey": "rider_of_the_apocalypse",
            "scenarioKey": "mythic_plus",
            "talentState": {"selectedNodes": [{"id": "node-rider", "rank": 1}]},
            "status": "verified",
        }

        def fake_refresh(force=False, stage_callback=None, store=None):
            self.assertTrue(force)
            store.raiderio_payload = {
                "sourceStatus": "synced",
                "status": "synced",
                "checkedAt": "fresh-cache",
                "communityTemplates": [fresh_template],
            }
            return store.raiderio_payload

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=fake_refresh,
        ) as refresh, patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_RANKINGS_DISABLED": "1",
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
            },
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store)

        refresh.assert_called_once()
        self.assertEqual(len(store.community_talent_templates), 1)
        self.assertEqual(store.community_talent_templates[0]["id"], "rio-fresh-rider")

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
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}

        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["runner"], "postgres")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sourceStatus"], "partial")
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
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual(len(store.community_talent_templates), 2)
        self.assertEqual(
            {template["sourceKey"] for template in store.community_talent_templates},
            {"raiderio", "warcraftlogs"},
        )
        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 1)
        self.assertEqual(payload["sourceStatus"], "partial")

    def test_community_postgres_sync_skips_stale_raiderio_spec_mismatch_templates(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-stale-mismatch",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                        "status": "verified",
                        "payload": {
                            "raiderio": {
                                "characterName": "Mageroysong",
                                "loadoutSpecId": 62,
                                "loadout": [{"traitId": 91001, "rank": 1}],
                            }
                        },
                    },
                    {
                        "id": "rio-frost-ok",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                        "payload": {"raiderio": {"characterName": "Frostok", "loadoutSpecId": 64}},
                    },
                ],
                "errors": [],
            }
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual([template["id"] for template in store.community_talent_templates], ["rio-frost-ok"])
        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 0)
        saved = {key: value for key, value, _updated_at in store.saved_states}
        self.assertIn("warnings", saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"])
        self.assertIn("loadout spec id 62", saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"]["warnings"][0])
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"]["skippedCount"], 1)
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"]["blockedCount"], 0)

    def test_community_postgres_sync_writes_full_hero_slot_coverage_matrix(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "regions": ["cn", "eu"],
                "regionCoverage": {
                    "cn": {
                        "specCoverage": {
                            "sampleCounts": {"deathknight:unholy": 4},
                        },
                    }
                },
                "specCoverage": {
                    "sampleCounts": {"deathknight:unholy": 4},
                },
                "runDetailCoverage": {"requestedRunCount": 1, "talentSnapshotCount": 5},
                "runCount": 10,
                "profileCount": 4,
                "templates": [
                    {
                        "id": "rio-unholy-rider",
                        "classKey": "deathknight",
                        "specKey": "unholy",
                        "heroKey": "rider_of_the_apocalypse",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-rider", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}
        matrix = saved[COMMUNITY_TALENT_SYNC_KEY]["coverageMatrix"]
        by_slot = {row["slotId"]: row for row in matrix["rows"]}

        self.assertEqual(matrix["totalSpecCount"], 40)
        self.assertEqual(matrix["totalHeroSlotCount"], 80)
        self.assertEqual(len(matrix["rows"]), 80)
        self.assertEqual(matrix["verifiedHeroSlotCount"], 1)
        self.assertEqual(matrix["pendingCollectionHeroSlotCount"], 79)
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["scanCoverage"]["totalHeroSlotCount"], 80)
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["scanCoverage"]["coveredHeroSlotCount"], 1)
        self.assertEqual(by_slot["deathknight:blood:deathbringer"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:blood:sanlayn"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:frost:deathbringer"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:frost:rider_of_the_apocalypse"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:unholy:rider_of_the_apocalypse"]["status"], "verified")
        self.assertEqual(by_slot["deathknight:unholy:sanlayn"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:blood:deathbringer"]["attemptedRunCount"], 0)
        self.assertIn("expand Raider.IO target-matrix scan", by_slot["deathknight:blood:deathbringer"]["nextAction"])
        self.assertEqual(by_slot["deathknight:unholy:rider_of_the_apocalypse"]["attemptedRunCount"], 4)
        self.assertIn("promoted active template", by_slot["deathknight:unholy:rider_of_the_apocalypse"]["nextAction"])
        self.assertEqual(
            matrix["sourceSummary"]["raiderio"]["regionCoverage"]["cn"]["specCoverage"]["sampleCounts"]["deathknight:unholy"],
            4,
        )
        timings = saved[COMMUNITY_TALENT_SYNC_KEY]["stageTimings"]
        self.assertGreaterEqual(timings["totalDurationSeconds"], 0)
        self.assertEqual(timings["candidateCount"], 1)
        self.assertEqual(timings["verifiedCount"], 1)
        self.assertEqual(timings["pendingDelta"], 79)
        stage_names = [stage["stage"] for stage in timings["stages"]]
        self.assertIn("candidate_extraction", stage_names)
        self.assertIn("validation_promotion_db_write", stage_names)
        self.assertIn("coverage_report", stage_names)
        self.assertIn("sync_state_write", stage_names)

    def test_community_postgres_sync_summarizes_wcl_evidence_and_target_matrix(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "regions": ["cn"],
                "specCoverage": {"sampleCounts": {"mage:frost": 6}},
                "templates": [
                    {
                        "id": "rio-frost-wcl-backed",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-frostfire", "rank": 1}]},
                        "status": "verified",
                        "payload": {
                            "wclEvidence": {
                                "tier": "wcl_character_supported",
                                "reportCount": 2,
                            },
                            "rioEvidence": {"maxKeyLevel": 24, "sampleCount": 6},
                            "evidenceTier": "wcl_character_supported",
                            "qualityScore": 74,
                        },
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "partial",
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
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        raiderio = state["sources"]["raiderio"]
        matrix = state["coverageMatrix"]

        self.assertEqual(raiderio["wclEvidenceCount"], 1)
        self.assertEqual(raiderio["targetMatrix"]["totalHeroSlotCount"], 80)
        self.assertEqual(raiderio["targetMatrix"]["verifiedHeroSlotCount"], 1)
        self.assertEqual(raiderio["targetMatrix"]["pendingCollectionHeroSlotCount"], 79)
        self.assertEqual(raiderio["targetMatrix"]["attemptedRunCount"], 6)
        self.assertIn("fetch run-detail/profile", raiderio["targetMatrix"]["nextAction"])
        self.assertEqual(matrix["rows"][0]["targetCollection"]["attemptedRunCount"], 0)

    def test_community_postgres_missing_slots_mode_targets_only_unverified_slots(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        store.coverage_rows = [
            {
                "id": "existing-arcane-spellslinger",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "spellslinger",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
            {
                "id": "existing-arcane-sunfury",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "sunfury",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
            {
                "id": "existing-frost-spellslinger",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "spellslinger",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
        ]
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-frost-frostfire-new",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-frostfire", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }
        captured_env = {}

        def fake_sync_raiderio_cache_postgres(**_kwargs):
            captured_env["targetSpecs"] = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS", "")
            captured_env["runPages"] = os.environ.get("WOW_RAIDERIO_RUN_PAGES", "")
            return {"sourceStatus": "verified", "runCount": 1, "profileCount": 1}

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=fake_sync_raiderio_cache_postgres,
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, mode="missing_slots")

        target_specs = set(filter(None, captured_env["targetSpecs"].split(",")))
        self.assertEqual(captured_env["runPages"], "0")
        self.assertIn("mage:frost", target_specs)
        self.assertNotIn("mage:arcane", target_specs)
        self.assertIn("mage:frost:frostfire", set(store.talent_replace_target_slot_ids or []))
        self.assertNotIn("mage:arcane:spellslinger", set(store.talent_replace_target_slot_ids or []))

        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}
        self.assertEqual(by_slot["mage:arcane:spellslinger"]["status"], "verified")
        self.assertEqual(by_slot["mage:arcane:sunfury"]["status"], "verified")
        self.assertEqual(by_slot["mage:frost:frostfire"]["status"], "verified")

    def test_community_postgres_sync_uses_promoted_templates_for_coverage(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}

        def fake_replace(templates, scan_run_id="", include_details=False, target_slot_ids=None):
            return {
                "total": 1,
                "verified": 1,
                "partial": 0,
                "blocked": 0,
                "promotedTemplates": [
                    {
                        "id": "promoted-rogue-deathstalker",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "classKey": "rogue",
                        "specKey": "subtlety",
                        "heroKey": "deathstalker",
                        "scenarioKey": "mythic_plus",
                        "status": "verified",
                    }
                ],
                "validatedTemplates": [
                    {
                        "id": "blocked-rogue-deathstalker",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "classKey": "rogue",
                        "specKey": "subtlety",
                        "heroKey": "deathstalker",
                        "scenarioKey": "mythic_plus",
                        "status": "blocked",
                        "payload": {
                            "talentLoadoutParse": {
                                "errors": ["unknown structured talent entry: spellId=381845"]
                            }
                        },
                    }
                ],
            }

        store.replace_community_talent_templates = fake_replace
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "candidate-placeholder",
                        "classKey": "rogue",
                        "specKey": "subtlety",
                        "heroKey": "deathstalker",
                        "scenarioKey": "mythic_plus",
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}
        self.assertEqual(by_slot["rogue:subtlety:deathstalker"]["status"], "verified")

    def test_community_postgres_sync_records_stage_root_causes(self):
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
                        "id": "rio-frost-authority-failure",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "missing-authority-node", "rank": 1}]},
                        "status": "blocked",
                        "payload": {"talentEncoding": {"errors": ["unknown talent node: missing-authority-node"]}},
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "partial",
                "sourceName": "Warcraft Logs",
                "templates": [],
                "errors": ["Warcraft Logs v2 credentials are configured, but no combatantinfo template seed/report extraction is available for this sync run."],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}
        state = saved[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}

        blocked = by_slot["mage:frost:frostfire"]
        pending = by_slot["mage:frost:spellslinger"]
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["blockers"][0]["stage"], "authority_encoding")
        self.assertIn("unknown talent node", blocked["blockers"][0]["reason"])
        self.assertEqual(pending["status"], "pending_collection")
        self.assertEqual(pending["blockers"][0]["stage"], "source_collection")
        self.assertIn("missing verified community talent template", pending["blockers"][0]["reason"])
        self.assertEqual(state["sources"]["raiderio"]["blockedCount"], 1)
        self.assertEqual(state["sources"]["warcraftlogs"]["candidateCount"], 0)
        self.assertEqual(state["sources"]["warcraftlogs"]["errorCount"], 1)
        self.assertEqual(state["sources"]["warcraftlogs"]["gaps"][0]["stage"], "template_extraction")

    def test_community_coverage_maps_structured_loadout_parse_to_authority_validation(self):
        from server.postgres_cache_sync import build_community_talent_coverage_matrix

        matrix = build_community_talent_coverage_matrix(
            [
                {
                    "id": "rio-frost-unknown-structured-entry",
                    "sourceKey": "raiderio",
                    "sourceName": "Raider.IO",
                    "sourceStatus": "synced",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "frostfire",
                    "scenarioKey": "mythic_plus",
                    "status": "blocked",
                    "payload": {
                        "talentLoadoutParse": {
                            "status": "blocked",
                            "source": "structured_loadout",
                            "errors": ["unknown structured talent entry: nodeId=81002, spellId=391002"],
                        }
                    },
                }
            ],
            sources={"raiderio": {"status": "synced", "sourceName": "Raider.IO", "candidateCount": 1}},
        )

        row = next(item for item in matrix["rows"] if item["slotId"] == "mage:frost:frostfire")
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["stage"], "authority_validation")
        self.assertEqual(row["blockers"][0]["stage"], "authority_validation")
        self.assertIn("nodeId=81002", row["blockers"][0]["reason"])

    def test_community_postgres_source_loader_excludes_non_community_fixtures_by_default(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {"sourceStatus": "verified", "communityTemplates": [], "errors": []}

        with patch.dict("os.environ", {"WOW_INCLUDE_MANUAL_FIXTURES": "", "WOW_INCLUDE_WEBSIM_BASELINE_TALENTS": ""}), patch(
            "server.community_talent_sources.manual_fixture.load_templates",
            side_effect=AssertionError("manual fixtures should not load in default PG sync"),
        ), patch(
            "server.community_talent_sources.warcraftlogs.load_templates",
            return_value={"status": "missing_credentials", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        ), patch(
            "server.websim_payload.load_websim_baseline_talent_templates",
            side_effect=AssertionError("WebSim baseline should not load in default PG sync"),
        ):
            sources = postgres_cache_sync.load_community_talent_sources_postgres(store)

        self.assertNotIn("manual_fixture", sources)
        self.assertNotIn("websim_baseline", sources)
        self.assertEqual(set(sources), {"raiderio", "warcraftlogs"})

    def test_community_postgres_sync_expires_disabled_non_community_sources(self):
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
            "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.dict("os.environ", {"WOW_INCLUDE_WEBSIM_BASELINE_TALENTS": ""}), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual(store.expired_talent_source_keys, ["manual_fixture", "websim_baseline"])

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
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}

        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 0)
        self.assertEqual(payload["sourceStatus"], "partial")
        self.assertIn("warcraftlogs: missing combatantinfo report extraction", payload["errors"])
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sourceStatus"], "partial")

    def test_warcraftlogs_seed_templates_normalize_evidence_tiers(self):
        from server.community_talent_sources import warcraftlogs

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": json.dumps(
                    {
                        "templates": [
                            {
                                "id": "wcl-exact",
                                "classKey": "mage",
                                "specKey": "frost",
                                "heroKey": "frostfire",
                                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                                "payload": {
                                    "warcraftlogs": {
                                        "reportCode": "abc123",
                                        "combatantInfo": {"talents": "CAEAAAAAAAAAAAAAAAAAAAAA"},
                                        "templateSignature": "talent:m:f:f",
                                    },
                                    "normalizedPerformance": {"score": 91.5},
                                },
                            },
                            {
                                "id": "wcl-supported",
                                "classKey": "mage",
                                "specKey": "frost",
                                "heroKey": "spellslinger",
                                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAB",
                                "payload": {
                                    "warcraftlogs": {
                                        "reportCode": "def456",
                                        "characterMatched": True,
                                    },
                                    "normalizedPerformance": {"score": 72},
                                },
                            },
                            {
                                "id": "wcl-conflict",
                                "classKey": "mage",
                                "specKey": "frost",
                                "heroKey": "frostfire",
                                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAC",
                                "status": "verified",
                                "payload": {
                                    "warcraftlogs": {
                                        "reportCode": "ghi789",
                                        "conflictReason": "combatantinfo talents differ from Raider.IO loadout",
                                    }
                                },
                            },
                        ]
                    }
                )
            },
        ):
            result = warcraftlogs.load_templates()

        by_id = {template["id"]: template for template in result["templates"]}
        self.assertEqual(by_id["wcl-exact"]["payload"]["wclEvidence"]["tier"], "wcl_exact_template")
        self.assertEqual(by_id["wcl-exact"]["payload"]["evidenceTier"], "wcl_exact_template")
        self.assertEqual(by_id["wcl-exact"]["payload"]["qualityScore"], 91.5)
        self.assertEqual(by_id["wcl-supported"]["payload"]["wclEvidence"]["tier"], "wcl_character_supported")
        self.assertEqual(by_id["wcl-conflict"]["payload"]["wclEvidence"]["tier"], "wcl_conflict")
        self.assertEqual(by_id["wcl-conflict"]["status"], "blocked")

    def test_warcraftlogs_rankings_extract_wcl_exact_template_candidates(self):
        from server.community_talent_sources import warcraftlogs

        calls = []

        def fake_graphql(_query, variables=None, token=None):
            calls.append(variables or {})
            return {
                "worldData": {
                    "encounter": {
                        "id": 3176,
                        "name": "Imperator Averzian",
                        "characterRankings": {
                            "count": 1,
                            "hasMorePages": False,
                            "page": 1,
                            "rankings": [
                                {
                                    "name": "Runeathon",
                                    "class": "Mage",
                                    "spec": "Arcane",
                                    "amount": 149208.58,
                                    "duration": 281166,
                                    "report": {"code": "jVgTrRX3vp6DfWZw", "fightID": 28},
                                    "server": {"name": "Stormrage", "region": "US"},
                                    "talents": [
                                        {"talentID": 80141, "points": 1},
                                        {"talentID": 117247, "points": 1},
                                    ],
                                }
                            ],
                        },
                    }
                }
            }

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(
            warcraftlogs,
            "warcraftlogs_graphql",
            side_effect=fake_graphql,
            create=True,
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
                "WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury",
                "WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS": "3176",
                "WOW_WARCRAFTLOGS_RANKING_PARTITION": "3",
                "WOW_WARCRAFTLOGS_RANKING_PAGES": "1",
            },
        ):
            result = warcraftlogs.load_templates()

        self.assertEqual(result["status"], "partial")
        self.assertEqual(calls[0]["className"], "Mage")
        self.assertEqual(calls[0]["specName"], "Arcane")
        self.assertEqual(calls[0]["encounterId"], 3176)
        template = result["templates"][0]
        self.assertEqual(template["sourceName"], "Warcraft Logs")
        self.assertEqual(template["classKey"], "mage")
        self.assertEqual(template["specKey"], "arcane")
        self.assertEqual(template["heroKey"], "sunfury")
        self.assertEqual(template["playerId"], "Runeathon")
        self.assertEqual(template["payload"]["wclEvidence"]["tier"], "wcl_exact_template")
        self.assertEqual(template["payload"]["evidenceTier"], "wcl_exact_template")
        self.assertEqual(template["payload"]["warcraftlogs"]["reportCode"], "jVgTrRX3vp6DfWZw")
        self.assertEqual(template["payload"]["warcraftlogs"]["fightId"], 28)
        self.assertEqual(template["payload"]["warcraftlogs"]["loadout"][0]["talentID"], 80141)
        self.assertEqual(template["payload"]["normalizedPerformance"]["score"], 149208.58)

    def test_warcraftlogs_rankings_skip_non_target_hero_candidates(self):
        from server.community_talent_sources import warcraftlogs

        class AuthorityStore:
            def __init__(self):
                self.requested = None

            def community_talent_authority_index(self, class_key, spec_key):
                self.requested = (class_key, spec_key)
                return {
                    80141: [{"id": "simc-class-80141-mage-arcane", "treeType": "class"}],
                    117267: [
                        {
                            "id": "simc-hero-117267-mage-arcane-spellslinger",
                            "treeType": "hero",
                            "heroKey": "spellslinger",
                        }
                    ],
                    117247: [
                        {
                            "id": "simc-hero-117247-mage-arcane-sunfury",
                            "treeType": "hero",
                            "heroKey": "sunfury",
                        }
                    ],
                }

        store = AuthorityStore()

        def fake_graphql(_query, variables=None, token=None):
            return {
                "worldData": {
                    "encounter": {
                        "id": 3176,
                        "name": "Imperator Averzian",
                        "characterRankings": {
                            "rankings": [
                                {
                                    "name": "Wronghero",
                                    "class": "Mage",
                                    "spec": "Arcane",
                                    "amount": 199208.58,
                                    "duration": 281166,
                                    "report": {"code": "WrongHeroReport", "fightID": 1},
                                    "server": {"name": "Stormrage", "region": "US"},
                                    "talents": [
                                        {"talentID": 80141, "points": 1},
                                        {"talentID": 123344, "points": 1},
                                        {"talentID": 117267, "points": 1},
                                    ],
                                },
                                {
                                    "name": "Righthero",
                                    "class": "Mage",
                                    "spec": "Arcane",
                                    "amount": 149208.58,
                                    "duration": 281166,
                                    "report": {"code": "RightHeroReport", "fightID": 2},
                                    "server": {"name": "Stormrage", "region": "US"},
                                    "talents": [
                                        {"talentID": 80141, "points": 1},
                                        {"talentID": 123341, "points": 1},
                                        {"talentID": 117247, "points": 1},
                                    ],
                                },
                            ],
                        },
                    }
                }
            }

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(
            warcraftlogs,
            "warcraftlogs_graphql",
            side_effect=fake_graphql,
            create=True,
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
                "WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury",
                "WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS": "3176",
                "WOW_WARCRAFTLOGS_RANKING_PARTITION": "3",
                "WOW_WARCRAFTLOGS_RANKING_PAGES": "1",
                "WOW_WARCRAFTLOGS_RANKING_TEMPLATE_LIMIT_PER_SLOT": "4",
            },
        ):
            result = warcraftlogs.load_templates(store)

        self.assertEqual(store.requested, ("mage", "arcane"))
        self.assertEqual([template["playerId"] for template in result["templates"]], ["Righthero"])
        self.assertEqual(result["templates"][0]["heroKey"], "sunfury")

    def test_warcraftlogs_rankings_respects_start_and_end_page_window(self):
        from server.community_talent_sources import warcraftlogs

        pages = []

        def fake_graphql(_query, variables=None, token=None):
            pages.append((variables or {}).get("page"))
            return {
                "worldData": {
                    "encounter": {
                        "id": 3176,
                        "name": "Imperator Averzian",
                        "characterRankings": {"rankings": []},
                    }
                }
            }

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(
            warcraftlogs,
            "warcraftlogs_graphql",
            side_effect=fake_graphql,
            create=True,
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
                "WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury",
                "WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS": "3176",
                "WOW_WARCRAFTLOGS_RANKING_PARTITION": "3",
                "WOW_WARCRAFTLOGS_RANKING_START_PAGE": "9",
                "WOW_WARCRAFTLOGS_RANKING_END_PAGE": "10",
            },
        ):
            result = warcraftlogs.load_templates()

        self.assertEqual(result["templates"], [])
        self.assertEqual(pages, [9, 10])

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
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual(len(store.community_gear_templates), 1)
        self.assertEqual(payload["gear"]["templates"]["verified"], 1)
        self.assertEqual(payload["sourceStatus"], "partial")

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

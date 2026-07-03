import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from server import raiderio_payload
from server.community_talent_sources import raiderio as raiderio_templates


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def sample_runs_payload():
    return {
        "leaderboard_url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
        "rankings": [
            {
                "rank": 1,
                "score": 4127.57,
                "run": {
                    "dungeon": {"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"},
                    "mythic_level": 24,
                    "clear_time_ms": 1580000,
                    "completed_at": "2026-06-15T12:00:00Z",
                    "roster": [
                        {
                            "character": {
                                "name": "Rioone",
                                "realm": {"name": "Isillien", "slug": "isillien"},
                                "region": {"slug": "cn"},
                                "class": {"name": "Mage", "slug": "mage"},
                                "spec": {"name": "Frost", "slug": "frost"},
                            }
                        },
                        {
                            "character": {
                                "name": "Tankone",
                                "realm": {"name": "Isillien", "slug": "isillien"},
                                "region": {"slug": "cn"},
                                "class": {"name": "Warrior", "slug": "warrior"},
                                "spec": {"name": "Protection", "slug": "protection"},
                            }
                        },
                    ],
                },
            }
        ],
    }


def sample_profile_payload(name="Rioone", class_slug="mage", spec_slug="frost", item_id=222001, item_name="Observed Hood"):
    return {
        "name": name,
        "realm": {"name": "Isillien", "slug": "isillien"},
        "region": "cn",
        "class": {"name": class_slug.title(), "slug": class_slug},
        "spec": {"name": spec_slug.title(), "slug": spec_slug},
        "profile_url": f"https://raider.io/characters/cn/isillien/{name}",
        "talentLoadout": {
            "loadout_text": "CAEAAAAAAAAAAAAAAAAAAAAA",
            "loadout_spec_id": 64,
            "loadout": [
                {"traitId": 91001, "rank": 1},
                {"traitId": 91002, "rank": 1},
                {"traitId": 91003, "rank": 1},
            ],
        },
        "gear": {
            "item_level_equipped": 706.5,
            "items": {
                "head": {
                    "item_id": item_id,
                    "item_level": 707,
                    "name": item_name,
                    "icon": "inv_helmet_01",
                    "item_quality": "Epic",
                    "bonuses": [1, 2],
                }
            },
        },
    }


class RaiderIOPayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "rio.sqlite3"
        self.old_env = dict(os.environ)
        os.environ["WOW_NEWS_DB"] = str(self.db_path)
        os.environ["WOW_RAIDERIO_API_KEY"] = "fake-api-key"
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "4"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    def connection(self):
        return sqlite3.connect(self.db_path)

    def test_api_get_injects_key_user_agent_and_redacts_errors(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["user_agent"] = request.get_header("User-agent")
            return FakeResponse({"ok": True})

        with patch.object(raiderio_payload, "urlopen", fake_urlopen):
            payload = raiderio_payload.api_get("/mythic-plus/affixes", {"region": "cn"})

        self.assertEqual(payload, {"ok": True})
        self.assertIn("region=cn", captured["url"])
        self.assertIn("access_key=fake-api-key", captured["url"])
        self.assertEqual(captured["user_agent"], "wow-mini-program/raiderio-sync")
        self.assertNotIn("fake-api-key", raiderio_payload.redact_secret(captured["url"]))

    def test_api_get_allows_public_requests_without_key(self):
        os.environ.pop("WOW_RAIDERIO_API_KEY", None)
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["user_agent"] = request.get_header("User-agent")
            return FakeResponse({"rankings": []})

        with patch.object(raiderio_payload, "urlopen", fake_urlopen):
            payload = raiderio_payload.api_get("/mythic-plus/runs", {"region": "cn"})

        self.assertEqual(payload, {"rankings": []})
        self.assertIn("region=cn", captured["url"])
        self.assertNotIn("access_key=", captured["url"])
        self.assertEqual(captured["user_agent"], "wow-mini-program/raiderio-sync")

    def test_get_raiderio_payload_refreshes_public_cache_without_key(self):
        os.environ.pop("WOW_RAIDERIO_API_KEY", None)
        os.environ["WOW_RAIDERIO_PUBLIC_FALLBACK"] = "1"

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "sync_raiderio_cache",
            return_value={
                **raiderio_payload.missing_credentials_payload(),
                "sourceStatus": "synced",
                "status": "synced",
                "runCount": 1,
                "profileCount": 1,
                "expiresAt": raiderio_payload.iso_after(6),
                "staleAt": raiderio_payload.iso_after(48),
            },
        ) as sync_mock:
            payload = raiderio_payload.get_raiderio_payload(conn)

        self.assertEqual(payload["sourceStatus"], "synced")
        sync_mock.assert_called_once_with(conn)

    def test_get_raiderio_payload_keeps_read_path_offline_without_key_by_default(self):
        os.environ.pop("WOW_RAIDERIO_API_KEY", None)
        os.environ.pop("WOW_RAIDERIO_PUBLIC_FALLBACK", None)

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "sync_raiderio_cache",
            return_value={
                **raiderio_payload.missing_credentials_payload(),
                "sourceStatus": "synced",
                "status": "synced",
            },
        ) as sync_mock:
            payload = raiderio_payload.get_raiderio_payload(conn)

        self.assertEqual(payload["sourceStatus"], "missing_credentials")
        sync_mock.assert_not_called()

    def test_sync_raiderio_cache_aggregates_runs_profiles_and_templates(self):
        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                self.assertEqual(params["region"], "cn")
                self.assertEqual(params["season"], "season-mn-1")
                return sample_runs_payload()
            if path == "/characters/profile":
                self.assertIn("talents", params["fields"].split(","))
                self.assertNotIn("talentLoadout", params["fields"].split(","))
                if params["name"] == "Tankone":
                    return sample_profile_payload("Tankone", "warrior", "protection")
                return sample_profile_payload()
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)
            conn.commit()
            cached = raiderio_payload.get_raiderio_payload(conn, allow_sync=False)

        self.assertEqual(payload["sourceStatus"], "synced")
        self.assertEqual(cached["runCount"], 1)
        aggregate = raiderio_payload.aggregate_by_spec(cached)["mage:frost"]
        self.assertEqual(aggregate["sampleCount"], 1)
        self.assertEqual(aggregate["maxKeyLevel"], 24)
        self.assertEqual(aggregate["observedGear"][0]["name"], "Observed Hood")
        mage_template = next(item for item in cached["communityTemplates"] if item["classKey"] == "mage")
        self.assertTrue(mage_template["rawImportCode"].startswith("CAE"))
        self.assertEqual(mage_template["playerId"], "Rioone")
        self.assertEqual(mage_template["payload"]["raiderio"]["characterName"], "Rioone")
        self.assertEqual(mage_template["payload"]["raiderio"]["realmSlug"], "isillien")
        self.assertEqual(mage_template["payload"]["raiderio"]["loadout"][0]["traitId"], 91001)
        self.assertEqual(mage_template["sourceUrl"], "https://raider.io/characters/cn/isillien/Rioone")

        home = {
            "featuredSpecializations": [
                {"id": "法师-冰霜", "websimClassKey": "mage", "websimSpecKey": "frost"},
            ],
        }
        enriched_home = raiderio_payload.enrich_builds_home_payload(home, cached)
        home_summary = enriched_home["featuredSpecializations"][0]["raiderio"]
        self.assertEqual(home_summary["maxKeyLevel"], 24)
        self.assertNotIn("observedGear", home_summary)
        self.assertNotIn("talentLoadouts", home_summary)
        self.assertNotIn("topRuns", home_summary)

        detail = {
            "websimClassKey": "mage",
            "websimSpecKey": "frost",
            "details": {"talents": {}, "gear": {}, "rotation": {}},
        }
        enriched = raiderio_payload.enrich_builds_detail_payload(detail, cached)
        self.assertEqual(enriched["raiderio"]["maxKeyLevel"], 24)
        self.assertNotIn("observedGear", enriched["raiderio"])
        self.assertNotIn("talentLoadouts", enriched["raiderio"])
        self.assertNotIn("topRuns", enriched["raiderio"])
        self.assertNotIn("observedGear", enriched["details"]["gear"])
        self.assertNotIn("talentLoadouts", enriched["details"]["talents"])
        self.assertEqual(enriched["details"]["rotation"]["sourceStatus"], "source_reference")

        spec_module = raiderio_payload.enrich_pve_module_payload({"key": "specLadder"}, cached)
        self.assertEqual(spec_module["sourceName"], "Raider.IO")
        self.assertEqual(spec_module["sourceStatus"], "source_reference")
        self.assertEqual(spec_module["dataTrust"]["status"], "source_reference")
        self.assertTrue(any("Raider.IO" in blocker for blocker in spec_module["blockers"]))
        self.assertTrue(all(item["sourceStatus"] == "source_reference" for item in spec_module["items"]))
        self.assertEqual(spec_module["archonTierSummary"]["dps"]["sourceStatus"], "source_reference")
        self.assertEqual(next(iter(spec_module["wclDetailsBySpec"].values()))["sourceStatus"], "source_reference")
        raiderio_check = next(item for item in spec_module["sourceChecks"] if item["key"] == "raiderio")
        self.assertEqual(raiderio_check["status"], "partial")
        self.assertIn("raiderio", [item["key"] for item in spec_module["sourceChecks"]])
        self.assertTrue(spec_module["archonTierSummary"]["dps"]["tiers"])

    def test_get_raiderio_payload_returns_stale_cache_when_refresh_fails(self):
        stale_payload = {
            **raiderio_payload.missing_credentials_payload(),
            "sourceStatus": "synced",
            "runCount": 1,
            "expiresAt": "2020-01-01T00:00:00+00:00",
            "staleAt": raiderio_payload.iso_after(24),
            "specAggregates": [{"classKey": "mage", "specKey": "frost", "sampleCount": 1}],
        }
        with closing(self.connection()) as conn:
            raiderio_payload.write_cache(conn, stale_payload)
            conn.commit()
            with patch.object(raiderio_payload, "api_get", side_effect=raiderio_payload.RaiderIOError("boom access_key=fake-api-key")):
                payload = raiderio_payload.get_raiderio_payload(conn)

        self.assertEqual(payload["sourceStatus"], "stale")
        self.assertNotIn("fake-api-key", json.dumps(payload))

    def test_sync_raiderio_cache_matches_real_profiles_that_omit_realm_slug(self):
        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return sample_runs_payload()
            if path == "/characters/profile":
                return {
                    "name": params["name"],
                    "realm": "Isillien",
                    "region": "cn",
                    "class": "Mage",
                    "active_spec_name": "Frost",
                    "active_spec_role": "DPS",
                    "profile_url": f"https://raider.io/characters/cn/isillien/{params['name']}",
                    "talentLoadout": {
                        "loadout_text": "CAEAAAAAAAAAAAAAAAAAAAAA",
                        "loadout_spec_id": 64,
                        "loadout": [{"node": {"id": 101089}, "rank": 1}],
                    },
                }
            return {}

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        template = next(item for item in payload["communityTemplates"] if item["playerId"] == "Rioone")
        self.assertEqual(template["rawImportCode"], "CAEAAAAAAAAAAAAAAAAAAAAA")

    def test_community_template_skips_profile_talent_loadout_spec_mismatch(self):
        run = raiderio_payload.simplify_run(sample_runs_payload()["rankings"][0])
        profile = raiderio_payload.profile_summary({
            **sample_profile_payload(),
            "talentLoadout": {
                "loadout_text": "CAEAAAAAAAAAAAAAAAAAAAAA",
                "loadout_spec_id": 62,
                "loadout": [{"traitId": 91001, "rank": 1}],
            },
        })

        aggregates = raiderio_payload.aggregate_runs([run], {raiderio_payload.character_key(profile): profile})
        templates = raiderio_payload.build_community_templates(aggregates, "2026-07-03T01:00:00+00:00")

        self.assertFalse(any(item["playerId"] == "Rioone" for item in templates))

    def test_fetch_profiles_samples_each_spec_with_per_spec_cap(self):
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "4"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "2"
        roster = []
        for index in range(1, 7):
            roster.append({
                "name": f"Mage{index}",
                "realmSlug": "isillien",
                "region": "cn",
                "className": "Mage",
                "classKey": "mage",
                "specName": "Frost",
                "specKey": "frost",
                "role": "dps",
            })
        for index in range(1, 4):
            roster.append({
                "name": f"Tank{index}",
                "realmSlug": "isillien",
                "region": "cn",
                "className": "Warrior",
                "classKey": "warrior",
                "specName": "Protection",
                "specKey": "protection",
                "role": "tank",
            })
        runs = [{"roster": roster}]
        fetched_names = []

        def fake_api_get(path, params=None, api_key=None):
            self.assertEqual(path, "/characters/profile")
            fetched_names.append(params["name"])
            if str(params["name"]).startswith("Tank"):
                return sample_profile_payload(params["name"], "warrior", "protection")
            return sample_profile_payload(params["name"], "mage", "frost")

        with patch.object(raiderio_payload, "api_get", fake_api_get):
            profiles, errors = raiderio_payload.fetch_profiles_for_runs(runs)

        self.assertEqual(errors, [])
        self.assertEqual(len(profiles), 4)
        spec_counts = {}
        for profile in profiles.values():
            key = f"{profile['classKey']}:{profile['specKey']}"
            spec_counts[key] = spec_counts.get(key, 0) + 1
        self.assertEqual(spec_counts, {"mage:frost": 2, "warrior:protection": 2})
        self.assertEqual(fetched_names[:2], ["Mage1", "Mage2"])
        self.assertIn("Tank1", fetched_names)

    def test_target_profile_limit_defaults_to_operational_scan_budget(self):
        os.environ.pop("WOW_RAIDERIO_TARGET_PROFILE_LIMIT", None)

        self.assertEqual(raiderio_payload.target_profile_limit(), 120)

    def test_target_profile_limit_can_be_disabled_by_env(self):
        os.environ["WOW_RAIDERIO_TARGET_PROFILE_LIMIT"] = "0"

        self.assertEqual(raiderio_payload.target_profile_limit(), 0)

    def test_target_item_coverage_includes_matched_profile_examples(self):
        profile = raiderio_payload.profile_summary(
            sample_profile_payload("Mage3", item_id=251111, item_name="Splitshroud Stinger")
        )
        coverage = raiderio_payload.target_item_coverage(
            {raiderio_payload.character_key(profile): profile},
            ["251111", "251171"],
        )

        self.assertEqual(coverage["matchedTargetItemIds"], ["251111"])
        self.assertEqual(coverage["missingTargetItemIds"], ["251171"])
        self.assertEqual(
            coverage["matchedTargetItemExamples"],
            [
                {
                    "itemId": "251111",
                    "slot": "head",
                    "name": "Splitshroud Stinger",
                    "itemLevel": 707,
                    "bonuses": [1, 2],
                    "gems": [],
                    "enchants": [],
                    "profile": {
                        "name": "Mage3",
                        "realmSlug": "isillien",
                        "region": "cn",
                        "classKey": "mage",
                        "specKey": "frost",
                        "profileUrl": "https://raider.io/characters/cn/isillien/Mage3",
                    },
                }
            ],
        )

    def test_sync_raiderio_cache_extends_profile_scan_for_target_item_ids(self):
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "1"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "1"
        os.environ["WOW_RAIDERIO_TARGET_PROFILE_LIMIT"] = "2"
        os.environ["WOW_RAIDERIO_TARGET_ITEM_IDS"] = "251111"

        def runs_payload():
            roster = []
            for index in range(1, 4):
                roster.append(
                    {
                        "character": {
                            "name": f"Mage{index}",
                            "realm": {"name": "Isillien", "slug": "isillien"},
                            "region": {"slug": "cn"},
                            "class": {"name": "Mage", "slug": "mage"},
                            "spec": {"name": "Frost", "slug": "frost"},
                        }
                    }
                )
            return {
                "leaderboard_url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
                "rankings": [
                    {
                        "rank": 1,
                        "score": 4127.57,
                        "run": {
                            "dungeon": {"name": "Magisters' Terrace", "slug": "magisters-terrace"},
                            "mythic_level": 24,
                            "roster": roster,
                        },
                    }
                ],
            }

        fetched_names = []

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return runs_payload()
            if path == "/characters/profile":
                fetched_names.append(params["name"])
                if params["name"] == "Mage3":
                    return sample_profile_payload("Mage3", item_id=251111, item_name="Splitshroud Stinger")
                return sample_profile_payload(params["name"], item_id=222001 + len(fetched_names))
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Magisters' Terrace", "slug": "magisters-terrace"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(fetched_names, ["Mage1", "Mage2", "Mage3"])
        self.assertEqual(payload["profileCount"], 3)
        self.assertEqual(payload["targetItemCoverage"]["targetItemCount"], 1)
        self.assertEqual(payload["targetItemCoverage"]["matchedTargetItemIds"], ["251111"])
        self.assertEqual(payload["targetItemCoverage"]["missingTargetItemIds"], [])
        self.assertTrue(any(item["name"] == "Splitshroud Stinger" for item in payload["profiles"][2]["gear"]))

    def test_fetch_profiles_for_runs_uses_configured_parallel_workers(self):
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "3"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "3"
        os.environ["WOW_RAIDERIO_TARGET_PROFILE_LIMIT"] = "0"
        os.environ["WOW_RAIDERIO_PROFILE_WORKERS"] = "3"
        roster = []
        for index in range(3):
            roster.append(
                {
                    "name": f"Mage{index}",
                    "realmSlug": "isillien",
                    "region": "cn",
                    "classKey": "mage",
                    "specKey": "frost",
                }
            )
        runs = [{"roster": roster}]
        lock = threading.Lock()
        active = {"count": 0, "max": 0}

        def fake_fetch(character, fields):
            with lock:
                active["count"] += 1
                active["max"] = max(active["max"], active["count"])
            try:
                time.sleep(0.03)
                return raiderio_payload.profile_summary(sample_profile_payload(character["name"]))
            finally:
                with lock:
                    active["count"] -= 1

        with patch.object(raiderio_payload, "fetch_profile_for_character", fake_fetch):
            profiles, errors = raiderio_payload.fetch_profiles_for_runs(runs)

        self.assertEqual(errors, [])
        self.assertEqual(len(profiles), 3)
        self.assertGreater(active["max"], 1)

    def test_fetch_profiles_for_runs_records_profile_timeout_without_failing_batch(self):
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "2"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "2"
        os.environ["WOW_RAIDERIO_TARGET_PROFILE_LIMIT"] = "0"
        os.environ["WOW_RAIDERIO_PROFILE_WORKERS"] = "2"
        runs = [{
            "roster": [
                {
                    "name": "Goodmage",
                    "realmSlug": "isillien",
                    "region": "cn",
                    "classKey": "mage",
                    "specKey": "frost",
                },
                {
                    "name": "Slowmage",
                    "realmSlug": "isillien",
                    "region": "cn",
                    "classKey": "mage",
                    "specKey": "arcane",
                },
            ]
        }]

        def fake_fetch(character, fields):
            if character["name"] == "Slowmage":
                raise TimeoutError("The read operation timed out")
            return raiderio_payload.profile_summary(sample_profile_payload(character["name"]))

        with patch.object(raiderio_payload, "fetch_profile_for_character", fake_fetch):
            profiles, errors = raiderio_payload.fetch_profiles_for_runs(runs)

        self.assertEqual(len(profiles), 1)
        self.assertEqual([profile["name"] for profile in profiles.values()], ["Goodmage"])
        self.assertEqual(errors, ["Raider.IO profile fetch failed: The read operation timed out"])

    def test_fetch_profiles_for_runs_skips_anonymous_realms(self):
        captured = []

        def fake_batch(characters, fields):
            captured.extend(characters)
            return [], []

        runs = [{
            "roster": [
                {"name": "Hidden", "realmSlug": "anonymous", "region": "cn", "classKey": "mage", "specKey": "frost"},
                {"name": "Visible", "realmSlug": "isillien", "region": "cn", "classKey": "mage", "specKey": "frost"},
            ]
        }]

        with patch.object(raiderio_payload, "fetch_profile_batch", fake_batch):
            raiderio_payload.fetch_profiles_for_runs(runs)

        self.assertEqual([character["realmSlug"] for character in captured], ["isillien"])

    def test_sync_raiderio_cache_emits_stage_progress_events(self):
        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return sample_runs_payload()
            if path == "/characters/profile":
                return sample_profile_payload(params["name"])
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        events = []
        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn, stage_callback=events.append)

        event_keys = [(event["stage"], event["status"]) for event in events]
        self.assertEqual(payload["sourceStatus"], "synced")
        self.assertIn(("raiderio_sync", "start"), event_keys)
        self.assertIn(("raiderio_runs", "start"), event_keys)
        self.assertIn(("raiderio_runs", "complete"), event_keys)
        self.assertIn(("raiderio_base_profiles", "start"), event_keys)
        self.assertIn(("raiderio_base_profiles", "complete"), event_keys)
        self.assertIn(("raiderio_static", "start"), event_keys)
        self.assertIn(("raiderio_static", "complete"), event_keys)
        self.assertIn(("raiderio_sync", "complete"), event_keys)

    def test_sync_raiderio_cache_continues_run_pages_when_target_items_are_missing(self):
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "2"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "1"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "1"
        os.environ["WOW_RAIDERIO_TARGET_PROFILE_LIMIT"] = "2"
        os.environ["WOW_RAIDERIO_TARGET_ITEM_IDS"] = "251111"

        def ranking_for(name, rank):
            return {
                "rank": rank,
                "score": 4127.57,
                "run": {
                    "dungeon": {"name": "Magisters' Terrace", "slug": "magisters-terrace"},
                    "mythic_level": 24,
                    "roster": [
                        {
                            "character": {
                                "name": name,
                                "realm": {"name": "Isillien", "slug": "isillien"},
                                "region": {"slug": "cn"},
                                "class": {"name": "Mage", "slug": "mage"},
                                "spec": {"name": "Frost", "slug": "frost"},
                            }
                        }
                    ],
                },
            }

        fetched_pages = []
        fetched_names = []

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                page = int((params or {}).get("page") or 0)
                fetched_pages.append(page)
                name = "Mage1" if page == 0 else "Mage2"
                return {
                    "leaderboard_url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
                    "rankings": [ranking_for(name, rank) for rank in range(page * 20 + 1, page * 20 + 21)],
                }
            if path == "/characters/profile":
                fetched_names.append(params["name"])
                if params["name"] == "Mage2":
                    return sample_profile_payload("Mage2", item_id=251111, item_name="Splitshroud Stinger")
                return sample_profile_payload(params["name"], item_id=222001)
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Magisters' Terrace", "slug": "magisters-terrace"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "expected_spec_pairs",
            return_value=["mage:frost"],
        ), patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(fetched_pages, [0, 1])
        self.assertEqual(fetched_names, ["Mage1", "Mage2"])
        self.assertEqual(payload["targetItemCoverage"]["matchedTargetItemIds"], ["251111"])
        self.assertEqual(payload["targetItemCoverage"]["missingTargetItemIds"], [])

    def test_sync_raiderio_cache_marks_partial_when_global_deadline_expires_before_profiles(self):
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "4"
        os.environ["WOW_RAIDERIO_SYNC_DEADLINE_SECONDS"] = "1"
        fetched_profiles = []

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return sample_runs_payload()
            if path == "/characters/profile":
                fetched_profiles.append(params["name"])
                return sample_profile_payload(params["name"])
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "time",
        ) as fake_time, patch.object(raiderio_payload, "api_get", fake_api_get):
            fake_time.monotonic.side_effect = [99.0, 100.0, 100.1, 100.5, 100.6, *([102.0] * 20)]
            payload = raiderio_payload.sync_raiderio_cache(conn)
            cached = raiderio_payload.read_cache(conn)

        self.assertEqual(fetched_profiles, [])
        self.assertEqual(payload["sourceStatus"], "partial")
        self.assertIn("Raider.IO sync deadline exceeded", payload["errors"])
        self.assertEqual(payload["profileCount"], 0)
        self.assertEqual(cached["sourceStatus"], "partial")

    def test_sync_raiderio_cache_uses_partial_gear_variants_as_target_items(self):
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "1"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "1"
        os.environ["WOW_RAIDERIO_TARGET_PROFILE_LIMIT"] = "1"
        os.environ.pop("WOW_RAIDERIO_TARGET_ITEM_IDS", None)

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return {
                    "leaderboard_url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
                    "rankings": [
                        {
                            "rank": 1,
                            "score": 4127.57,
                            "run": {
                                "dungeon": {"name": "Magisters' Terrace", "slug": "magisters-terrace"},
                                "mythic_level": 24,
                                "roster": [
                                    {
                                        "character": {
                                            "name": "Mage1",
                                            "realm": {"name": "Isillien", "slug": "isillien"},
                                            "region": {"slug": "cn"},
                                            "class": {"name": "Mage", "slug": "mage"},
                                            "spec": {"name": "Frost", "slug": "frost"},
                                        }
                                    },
                                    {
                                        "character": {
                                            "name": "Mage2",
                                            "realm": {"name": "Isillien", "slug": "isillien"},
                                            "region": {"slug": "cn"},
                                            "class": {"name": "Mage", "slug": "mage"},
                                            "spec": {"name": "Frost", "slug": "frost"},
                                        }
                                    },
                                ],
                            },
                        }
                    ],
                }
            if path == "/characters/profile":
                if params["name"] == "Mage2":
                    return sample_profile_payload("Mage2", item_id=251171, item_name="Enthralled Bonespines")
                return sample_profile_payload(params["name"], item_id=222001)
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Magisters' Terrace", "slug": "magisters-terrace"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            conn.execute(
                """
                CREATE TABLE websim_gear_variants (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    source_type TEXT,
                    status TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants (id, item_id, source_type, status)
                VALUES ('loot-partial-251171-shoulder', '251171', 'dungeon', 'partial')
                """
            )
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(payload["targetItemCoverage"]["targetItemCount"], 1)
        self.assertEqual(payload["targetItemCoverage"]["matchedTargetItemIds"], ["251171"])
        self.assertEqual(payload["targetItemCoverage"]["missingTargetItemIds"], [])

    def test_db_target_item_ids_include_observed_variants_missing_simc_stats(self):
        os.environ["WOW_RAIDERIO_TARGET_ITEM_LIMIT"] = "8"

        with closing(self.connection()) as conn:
            conn.execute(
                """
                CREATE TABLE websim_gear_variants (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    slot TEXT,
                    source_type TEXT,
                    status TEXT,
                    payload_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE websim_gear_sources (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    source_type TEXT,
                    source_label TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status, payload_json)
                VALUES ('observed-missing-268290', '268290', 'finger1', 'observed_profile', 'verified', ?)
                """,
                (json.dumps({"observedProfileRefs": [{"characterName": "Observedone"}]}),),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status, payload_json)
                VALUES ('observed-covered-268291', '268291', 'neck', 'observed_profile', 'verified', ?)
                """,
                (json.dumps({"statSource": "simulationcraft"}),),
            )
            for index in range(20):
                item_id = str(300000 + index)
                conn.execute(
                    """
                    INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status, payload_json)
                    VALUES (?, ?, ?, 'dungeon', 'partial', '{}')
                    """,
                    (f"loot-partial-{item_id}", item_id, "finger1" if index % 2 else "feet"),
                )
                conn.execute(
                    """
                    INSERT INTO websim_gear_sources (id, item_id, source_type, source_label)
                    VALUES (?, ?, 'dungeon', ?)
                    """,
                    (f"loot-source-{item_id}", item_id, f"Boss {index:03d} - Dungeon {index:03d}"),
                )

            target_ids = raiderio_payload.db_target_item_ids(conn)

        self.assertIn("268290", target_ids)
        self.assertNotIn("268291", target_ids)

    def test_db_target_item_ids_prioritize_frequent_observed_stat_gaps(self):
        os.environ["WOW_RAIDERIO_TARGET_ITEM_LIMIT"] = "1"

        with closing(self.connection()) as conn:
            conn.execute(
                """
                CREATE TABLE websim_gear_variants (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    slot TEXT,
                    source_type TEXT,
                    status TEXT,
                    payload_json TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status, payload_json)
                VALUES ('observed-missing-151309', '151309', 'back', 'observed_profile', 'verified', '{}')
                """
            )
            for index in range(3):
                conn.execute(
                    """
                    INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status, payload_json)
                    VALUES (?, '268290', 'neck', 'observed_profile', 'verified', '{}')
                    """,
                    (f"observed-missing-268290-{index}",),
                )

            target_ids = raiderio_payload.db_target_item_ids(conn)

        self.assertEqual(target_ids, ["268290"])

    def test_db_target_item_ids_round_robins_partial_items_by_source_and_slot(self):
        os.environ["WOW_RAIDERIO_TARGET_ITEM_LIMIT"] = "8"

        with closing(self.connection()) as conn:
            conn.execute(
                """
                CREATE TABLE websim_gear_variants (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    slot TEXT,
                    source_type TEXT,
                    status TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE websim_gear_sources (
                    id TEXT PRIMARY KEY,
                    item_id TEXT,
                    source_type TEXT,
                    source_label TEXT
                )
                """
            )
            for index in range(100):
                item_id = str(100000 + index)
                conn.execute(
                    """
                    INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status)
                    VALUES (?, ?, ?, 'dungeon', 'partial')
                    """,
                    (f"loot-partial-{item_id}", item_id, "finger1" if index % 2 else "feet"),
                )
                conn.execute(
                    """
                    INSERT INTO websim_gear_sources (id, item_id, source_type, source_label)
                    VALUES (?, ?, 'dungeon', ?)
                    """,
                    (f"loot-source-{item_id}", item_id, f"Boss {index:03d} - Pit of Saron"),
                )
            for item_id, slot, label in [
                ("900001", "back", "Nexus-Point Xenas"),
                ("900002", "off_hand", "Algeth'ar Academy"),
                ("900003", "wrist", "Mythara Cave"),
            ]:
                conn.execute(
                    """
                    INSERT INTO websim_gear_variants (id, item_id, slot, source_type, status)
                    VALUES (?, ?, ?, 'dungeon', 'partial')
                    """,
                    (f"loot-partial-{item_id}", item_id, slot),
                )
                conn.execute(
                    """
                    INSERT INTO websim_gear_sources (id, item_id, source_type, source_label)
                    VALUES (?, ?, 'dungeon', ?)
                    """,
                    (f"loot-source-{item_id}", item_id, label),
                )

            target_ids = raiderio_payload.db_target_item_ids(conn)

        self.assertEqual(len(target_ids), 8)
        self.assertIn("900001", target_ids)
        self.assertIn("900002", target_ids)
        self.assertIn("900003", target_ids)
        self.assertLess(target_ids.index("900001"), 8)
        self.assertLess(target_ids.index("900002"), 8)
        self.assertLess(target_ids.index("900003"), 8)

    def test_community_template_adapter_reads_raiderio_cache(self):
        payload = {
            **raiderio_payload.missing_credentials_payload(),
            "sourceStatus": "synced",
            "expiresAt": raiderio_payload.iso_after(6),
            "staleAt": raiderio_payload.iso_after(48),
            "communityTemplates": [
                {
                    "id": "raiderio-mage-frost-1",
                    "classKey": "mage",
                    "specKey": "frost",
                    "scenarioKey": "mythic_plus",
                    "name": "Raider.IO Frost Mage",
                    "sourceName": "Raider.IO",
                    "sourceUrl": "https://raider.io/",
                    "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                    "sampleCount": 10,
                    "maxKeyLevel": 24,
                    "analysisWindow": "fixture",
                    "status": "verified",
                }
            ],
        }
        os.environ.pop("WOW_RAIDERIO_API_KEY", None)
        with closing(self.connection()) as conn:
            raiderio_payload.write_cache(conn, payload)
            conn.commit()
            result = raiderio_templates.load_templates(conn)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["templates"][0]["sourceName"], "Raider.IO")

    def test_profile_summary_accepts_real_api_class_and_active_spec_fields(self):
        profile = raiderio_payload.profile_summary({
            "name": "Riohealer",
            "realm": {"name": "Isillien", "slug": "isillien"},
            "region": "cn",
            "class": "Monk",
            "active_spec_name": "Mistweaver",
            "active_spec_role": "HEALING",
            "profile_url": "https://raider.io/characters/cn/isillien/Riohealer",
            "talentLoadout": {
                "loadout_text": "CEQAAAAAAAAAAAAAAAAAAAAA",
                "loadout_spec_id": 270,
                "loadout": [{"node": {"id": 101089}, "rank": 1}],
            },
        })

        self.assertEqual(profile["classKey"], "monk")
        self.assertEqual(profile["specKey"], "mistweaver")
        self.assertEqual(profile["role"], "healer")
        self.assertEqual(profile["talentLoadout"]["rawImportCode"], "CEQAAAAAAAAAAAAAAAAAAAAA")

if __name__ == "__main__":
    unittest.main()

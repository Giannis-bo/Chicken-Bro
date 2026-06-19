import json
import os
import sqlite3
import tempfile
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


def sample_profile_payload(name="Rioone", class_slug="mage", spec_slug="frost"):
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
            "loadout": [{"node": 1, "rank": 1}],
        },
        "gear": {
            "item_level_equipped": 706.5,
            "items": {
                "head": {
                    "item_id": 222001,
                    "item_level": 707,
                    "name": "Observed Hood",
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

    def test_sync_raiderio_cache_aggregates_runs_profiles_and_templates(self):
        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                self.assertEqual(params["region"], "cn")
                self.assertEqual(params["season"], "season-mn-1")
                return sample_runs_payload()
            if path == "/characters/profile":
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
        self.assertTrue(cached["communityTemplates"][0]["rawImportCode"].startswith("CAE"))

        detail = {
            "websimClassKey": "mage",
            "websimSpecKey": "frost",
            "details": {"talents": {}, "gear": {}, "rotation": {}},
        }
        enriched = raiderio_payload.enrich_builds_detail_payload(detail, cached)
        self.assertEqual(enriched["raiderio"]["maxKeyLevel"], 24)
        self.assertEqual(enriched["details"]["gear"]["observedGear"][0]["name"], "Observed Hood")
        self.assertEqual(enriched["details"]["rotation"]["sourceStatus"], "source_reference")

        spec_module = raiderio_payload.enrich_pve_module_payload({"key": "specLadder"}, cached)
        self.assertEqual(spec_module["sourceName"], "Raider.IO")
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


if __name__ == "__main__":
    unittest.main()

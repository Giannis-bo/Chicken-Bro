import json
import unittest
from pathlib import Path

from server.app.simulation.domain import SourceProvider, SourceReadiness
from server.app.simulation.sources import (
    CharacterSourceRouter,
    InvalidSourceLink,
    RaiderIOCharacterAdapter,
    SourceHttpError,
    WclCharacterAdapter,
    parse_character_source_url,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "character_sources"


class FakeGateway:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def fetch_json(self, url, *, headers=None):
        self.urls.append((url, headers or {}))
        return self.payload


class FailingGateway:
    def __init__(self, status_code):
        self.status_code = status_code

    def fetch_json(self, url, *, headers=None):
        raise SourceHttpError(self.status_code)


class SimulationSourcesTest(unittest.TestCase):
    def test_router_rejects_non_https_and_unallowlisted_hosts_without_fetching(self):
        gateway = FakeGateway({})
        router = CharacterSourceRouter(gateway)

        with self.assertRaises(InvalidSourceLink) as context:
            router.resolve("http://raider.io/characters/us/area-52/Stormsample")
        self.assertEqual(context.exception.code, "INVALID_LINK")
        self.assertEqual(gateway.urls, [])

        with self.assertRaises(InvalidSourceLink):
            router.resolve("https://example.com/characters/us/area-52/Stormsample")
        self.assertEqual(gateway.urls, [])

    def test_raiderio_adapter_normalizes_real_source_and_retains_hash_provenance(self):
        payload = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        gateway = FakeGateway(payload)
        parsed = parse_character_source_url("https://raider.io/characters/us/area-52/Stormsample")

        candidate = RaiderIOCharacterAdapter(gateway).resolve(parsed)

        self.assertEqual(candidate.provider, SourceProvider.RAIDERIO)
        self.assertEqual(candidate.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
        self.assertEqual(candidate.snapshot["character"]["specKey"], "elemental")
        self.assertEqual(candidate.snapshot["character"]["level"], 80)
        self.assertNotIn("levelSource", candidate.snapshot["character"])
        self.assertEqual(candidate.missing_fields, ())
        self.assertEqual(candidate.snapshot["gear"]["head"]["itemId"], 1001)
        self.assertEqual(len(candidate.raw_sha256), 64)
        self.assertEqual(candidate.provenance["sourceUrl"], parsed.url)
        self.assertTrue(candidate.provenance["sourceRevision"])
        self.assertEqual(len(gateway.urls), 1)

    def test_raiderio_localized_character_url_normalizes_to_the_profile_source(self):
        parsed = parse_character_source_url(
            "https://raider.io/cn/characters/cn/silver-hand/Giannis"
        )

        self.assertEqual(parsed.provider, SourceProvider.RAIDERIO)
        self.assertEqual(parsed.region, "cn")
        self.assertEqual(parsed.realm, "silver-hand")
        self.assertEqual(parsed.character_name, "Giannis")
        self.assertEqual(
            parsed.url,
            "https://raider.io/characters/cn/silver-hand/Giannis",
        )

    def test_raiderio_adapter_maps_only_source_present_fields(self):
        payload = {
            "name": "LiveShape",
            "realm": "Silver Hand",
            "region": "cn",
            "class": "Shaman",
            "active_spec_name": "Elemental",
            "race": {"slug": "earthen"},
            "talentLoadout": {
                "loadout_text": "LIVELOADOUT",
                "loadout": [{"id": 10001, "rank": 1}],
            },
            "gear": {
                "items": {
                    "head": {
                        "item_id": 2001,
                        "item_level": 730,
                        "bonuses": [101, 102],
                        "gems": [],
                        "enchants": [501],
                    },
                    "neck": {
                        "item_id": 2002,
                        "item_level": 730,
                        "bonuses": [103],
                        "gems": [601],
                        "enchants": [],
                    },
                },
            },
        }
        parsed = parse_character_source_url(
            "https://raider.io/cn/characters/cn/silver-hand/LiveShape"
        )

        candidate = RaiderIOCharacterAdapter(FakeGateway(payload)).resolve(parsed)

        self.assertNotIn("level", candidate.snapshot["character"])
        self.assertNotIn("levelSource", candidate.snapshot["character"])
        self.assertIn("character.level", candidate.missing_fields)
        self.assertEqual(candidate.snapshot["gear"]["head"]["itemLevel"], 730)
        self.assertEqual(candidate.snapshot["gear"]["head"]["bonusIds"], [101, 102])
        self.assertEqual(candidate.snapshot["gear"]["head"]["enchant"], 501)
        self.assertIsNone(candidate.snapshot["gear"]["neck"]["enchant"])
        self.assertEqual(candidate.snapshot["talents"]["string"], "LIVELOADOUT")

    def test_wcl_adapter_preserves_report_fight_actor_and_surfaces_incomplete_fields(self):
        payload = json.loads((FIXTURE_DIR / "wcl_incomplete.json").read_text())
        gateway = FakeGateway(payload)
        parsed = parse_character_source_url(
            "https://www.warcraftlogs.com/reports/AbCdEf123#fight=16&source=82"
        )

        candidate = WclCharacterAdapter(gateway, access_token="secret-token").resolve(parsed)

        self.assertEqual(candidate.provider, SourceProvider.WARCRAFTLOGS)
        self.assertEqual(candidate.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
        self.assertEqual(candidate.provenance["reportCode"], "AbCdEf123")
        self.assertEqual(candidate.provenance["fightId"], 16)
        self.assertEqual(candidate.provenance["actorId"], 82)
        self.assertNotIn("secret-token", candidate.provenance)
        self.assertNotIn("level", candidate.snapshot["character"])
        self.assertNotIn("levelSource", candidate.snapshot["character"])
        self.assertIn("character.level", candidate.missing_fields)
        self.assertIn("character.raceKey", candidate.missing_fields)

    def test_source_failures_keep_public_readiness_distinctions(self):
        parsed = parse_character_source_url(
            "https://raider.io/characters/us/area-52/Stormsample"
        )

        expected_by_status = {
            404: SourceReadiness.CHARACTER_NOT_FOUND,
            403: SourceReadiness.ACCESS_RESTRICTED,
            502: SourceReadiness.SNAPSHOT_UNAVAILABLE,
        }
        for status, expected in expected_by_status.items():
            with self.subTest(status=status):
                candidate = RaiderIOCharacterAdapter(FailingGateway(status)).resolve(parsed)
                self.assertEqual(candidate.readiness, expected)


if __name__ == "__main__":
    unittest.main()

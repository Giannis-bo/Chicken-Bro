import json
import unittest
from pathlib import Path
from unittest.mock import patch

from server.app.integrations.blizzard import BlizzardProfileEnricher
from server.app.integrations.warcraftlogs import (
    WarcraftLogsAccessError,
    WarcraftLogsProviderError,
)
from server.app.simulation.domain import SourceProvider, SourceReadiness
from server.app.simulation.sources import (
    CharacterSourceRouter,
    InvalidSourceLink,
    RaiderIOCharacterAdapter,
    SourceHttpError,
    WclCharacterAdapter,
    parse_character_source_url,
)
from server.app.simulation.snapshots import sha256_json


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "character_sources"


class FakeGateway:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def fetch_json(self, url, *, headers=None):
        self.urls.append((url, headers or {}))
        return self.payload


class RoutingGateway(FakeGateway):
    def __init__(self, primary_payload, official_payload):
        super().__init__(primary_payload)
        self.official_payload = official_payload

    def fetch_json(self, url, *, headers=None, method="GET", json_body=None):
        self.urls.append((url, headers or {}))
        if "api.blizzard.com/profile/" in url:
            return self.official_payload
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

    def test_raiderio_missing_level_and_race_are_filled_only_by_exact_official_profile(self):
        primary = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        primary.pop("level")
        primary.pop("race")
        official = {
            "name": "Stormsample",
            "realm": {"slug": "area-52", "name": "Area-52"},
            "level": 80,
            "race": {"name": "Tauren"},
            "character_class": {"name": "Shaman"},
            "active_spec": {"name": "Elemental"},
        }
        gateway = RoutingGateway(primary, official)
        parsed = parse_character_source_url(
            "https://raider.io/characters/us/area-52/Stormsample"
        )
        candidate = RaiderIOCharacterAdapter(
            gateway,
            official_enricher=BlizzardProfileEnricher(
                gateway,
                token_provider=lambda: "short-lived-token",
            ),
        ).resolve(parsed)

        self.assertEqual(candidate.snapshot["character"]["level"], 80)
        self.assertEqual(candidate.snapshot["character"]["raceKey"], "tauren")
        self.assertEqual(candidate.missing_fields, ())
        self.assertEqual(
            candidate.raw_sha256,
            sha256_json({"primary": primary, "officialProfile": official}),
        )
        self.assertEqual(
            candidate.provenance["officialProfile"]["rawSha256"],
            sha256_json(official),
        )
        self.assertNotIn("short-lived-token", json.dumps(candidate.provenance))
        self.assertEqual(len(gateway.urls), 2)
        self.assertEqual(gateway.urls[1][1], {"Authorization": "Bearer short-lived-token"})

    def test_official_profile_fills_any_missing_identity_field_without_overwriting_primary_values(self):
        primary = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        primary.pop("class")
        primary.pop("active_spec_name")
        official = {
            "name": "Stormsample",
            "realm": {"slug": "area-52"},
            "level": 80,
            "race": {"name": "Tauren"},
            "character_class": {"name": "Shaman"},
            "active_spec": {"name": "Elemental"},
        }
        gateway = RoutingGateway(primary, official)
        candidate = RaiderIOCharacterAdapter(
            gateway,
            official_enricher=BlizzardProfileEnricher(
                gateway,
                token_provider=lambda: "short-lived-token",
            ),
        ).resolve(
            parse_character_source_url(
                "https://raider.io/characters/us/area-52/Stormsample"
            )
        )

        self.assertEqual(candidate.snapshot["character"]["classKey"], "shaman")
        self.assertEqual(candidate.snapshot["character"]["specKey"], "elemental")
        self.assertEqual(candidate.snapshot["character"]["level"], 80)
        self.assertEqual(len(gateway.urls), 2)

    def test_official_profile_failure_never_guesses_missing_fields(self):
        primary = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        primary.pop("level")
        primary.pop("race")
        gateway = RoutingGateway(primary, {})
        parsed = parse_character_source_url(
            "https://raider.io/characters/cn/silver-hand/LiveShape"
        )
        candidate = RaiderIOCharacterAdapter(
            gateway,
            official_enricher=BlizzardProfileEnricher(
                gateway,
                token_provider=lambda: "",
            ),
        ).resolve(parsed)

        self.assertNotIn("level", candidate.snapshot["character"])
        self.assertNotIn("raceKey", candidate.snapshot["character"])
        self.assertIn("character.level", candidate.missing_fields)
        self.assertIn("character.raceKey", candidate.missing_fields)
        self.assertEqual(len(gateway.urls), 1)

    def test_official_profile_identity_mismatch_is_rejected_without_merging(self):
        primary = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        primary.pop("level")
        primary.pop("race")
        official = {
            "name": "DifferentCharacter",
            "realm": {"slug": "area-52"},
            "level": 80,
            "race": {"name": "Tauren"},
            "character_class": {"name": "Shaman"},
            "active_spec": {"name": "Elemental"},
        }
        gateway = RoutingGateway(primary, official)
        parsed = parse_character_source_url(
            "https://raider.io/characters/us/area-52/Stormsample"
        )
        candidate = RaiderIOCharacterAdapter(
            gateway,
            official_enricher=BlizzardProfileEnricher(
                gateway,
                token_provider=lambda: "short-lived-token",
            ),
        ).resolve(parsed)

        self.assertNotIn("level", candidate.snapshot["character"])
        self.assertNotIn("raceKey", candidate.snapshot["character"])
        self.assertIn("character.level", candidate.missing_fields)
        self.assertNotIn("officialProfile", candidate.provenance)

    def test_official_profile_supports_legacy_headerless_http_clients(self):
        official = {
            "name": "Stormsample",
            "realm": {"slug": "area-52"},
            "level": 80,
            "race": {"name": "Tauren"},
            "character_class": {"name": "Shaman"},
            "active_spec": {"name": "Elemental"},
        }

        class HeaderlessGateway:
            @staticmethod
            def fetch_json(_url):
                return official

        enrichment = BlizzardProfileEnricher(
            HeaderlessGateway(),
            token_provider=lambda: "short-lived-token",
        ).enrich(
            parse_character_source_url(
                "https://raider.io/characters/us/area-52/Stormsample"
            ),
            {
                "name": "Stormsample",
                "realm": "Area-52",
                "classKey": "shaman",
                "specKey": "elemental",
            },
        )

        self.assertIsNotNone(enrichment)
        self.assertEqual(enrichment.character["level"], 80)

    def test_official_profile_uses_lowercase_character_slug_for_blizzard_lookup(self):
        official = {
            "name": "Mandur",
            "realm": {"slug": "hyjal"},
            "level": 90,
            "race": {"name": "Dwarf"},
            "character_class": {"name": "Shaman"},
            "active_spec": {"name": "Elemental"},
        }

        class CaptureGateway:
            def __init__(self):
                self.url = ""

            def fetch_json(self, url, *, headers=None):
                self.url = url
                return official

        gateway = CaptureGateway()
        enrichment = BlizzardProfileEnricher(
            gateway,
            token_provider=lambda: "short-lived-token",
        ).enrich(
            parse_character_source_url(
                "https://raider.io/characters/eu/hyjal/Mandur"
            ),
            {
                "name": "Mandur",
                "realm": "Hyjal",
                "region": "eu",
                "classKey": "shaman",
                "specKey": "elemental",
            },
        )

        self.assertIsNotNone(enrichment)
        self.assertIn("/character/hyjal/mandur?", gateway.url)

    def test_raiderio_last_crawled_at_is_a_bounded_source_revision(self):
        payload = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        payload.pop("profileRevision")
        payload["last_crawled_at"] = "2026-09-03T09:30:00Z"
        candidate = RaiderIOCharacterAdapter(FakeGateway(payload)).resolve(
            parse_character_source_url(
                "https://raider.io/characters/us/area-52/Stormsample"
            )
        )

        self.assertEqual(candidate.provenance["sourceRevision"], "2026-09-03T09:30:00Z")

    def test_wcl_grouped_player_details_are_flattened_for_actor_resolution(self):
        payload = json.loads((FIXTURE_DIR / "wcl_incomplete.json").read_text())
        player = payload["data"]["reportData"]["report"]["playerDetails"]["data"]["playerDetails"][0]
        payload["data"]["reportData"]["report"]["playerDetails"]["data"]["playerDetails"] = {
            "dps": [player],
            "healers": [],
            "tanks": [],
        }
        candidate = WclCharacterAdapter(
            FakeGateway(payload),
            access_token="secret-token",
        ).resolve(
            parse_character_source_url(
                "https://www.warcraftlogs.com/reports/AbCdEf123#fight=16&source=82"
            )
        )

        self.assertEqual(candidate.readiness, SourceReadiness.INCOMPLETE_FOR_SIMC)
        self.assertEqual(candidate.provenance["actorId"], 82)
        self.assertEqual(candidate.snapshot["character"]["name"], "Logsample")

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

    def test_default_wcl_router_uses_server_oauth_without_static_access_token(self):
        payload = json.loads((FIXTURE_DIR / "wcl_incomplete.json").read_text())
        gateway = FakeGateway(payload)
        source_url = "https://www.warcraftlogs.com/reports/AbCdEf123#fight=16&source=82"

        with patch(
            "server.app.simulation.sources.warcraftlogs_oauth_token",
            return_value="short-lived-oauth-token",
        ) as token_provider:
            candidate = CharacterSourceRouter(gateway).resolve(source_url)

        token_provider.assert_called_once_with()
        self.assertEqual(candidate.provider, SourceProvider.WARCRAFTLOGS)
        self.assertEqual(
            gateway.urls[0][1],
            {"Authorization": "Bearer short-lived-oauth-token"},
        )
        self.assertNotIn("short-lived-oauth-token", str(candidate.provenance))

    def test_wcl_token_access_and_provider_failures_remain_distinct(self):
        parsed = parse_character_source_url(
            "https://www.warcraftlogs.com/reports/AbCdEf123#fight=16&source=82"
        )

        for error, expected in (
            (WarcraftLogsAccessError(), SourceReadiness.ACCESS_RESTRICTED),
            (WarcraftLogsProviderError(), SourceReadiness.SNAPSHOT_UNAVAILABLE),
        ):
            with self.subTest(error=error.__class__.__name__):
                gateway = FakeGateway({})

                def fail_token(error=error):
                    raise error

                candidate = WclCharacterAdapter(
                    gateway,
                    token_provider=fail_token,
                ).resolve(parsed)

                self.assertEqual(candidate.readiness, expected)
                self.assertEqual(gateway.urls, [])

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

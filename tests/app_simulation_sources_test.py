import json
import copy
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
    def _giannis_gateway(self):
        directory = Path(__file__).parent / "fixtures" / "simc"
        details = json.loads((directory / "giannis_raiderio_details.json").read_text(encoding="utf-8"))
        report = json.loads((directory / "giannis_wcl_report.json").read_text(encoding="utf-8"))
        identity = {"data": {"characterData": {"character": {
            "name": "Giannis", "level": 90,
            "server": {"name": "白银之手", "slug": "silver-hand", "region": {"slug": "CN"}},
        }}}}
        primary = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        primary.update(name="Giannis", realm="Silver Hand", region="cn", race="Dark Iron Dwarf")
        primary.pop("level", None)

        class Gateway:
            def __init__(self): self.calls = []
            def fetch_json(self, url, **kwargs):
                self.calls.append((url, kwargs))
                if "/api/characters/" in url: return details
                if "raider.io" in url: return primary
                query = kwargs.get("json_body", {}).get("query", "")
                if "characterData" in query: return identity
                return report
        gateway = Gateway()
        official = BlizzardProfileEnricher(gateway, token_provider=lambda: "")
        return gateway, official, primary, details, report, identity

    def test_giannis_cn_profile_gets_explicit_level_from_verified_character_details(self):
        gateway, official, primary, details, _, _ = self._giannis_gateway()
        candidate = RaiderIOCharacterAdapter(gateway, official_enricher=official).resolve(
            parse_character_source_url("https://raider.io/cn/characters/cn/silver-hand/Giannis"))
        self.assertEqual(candidate.snapshot["character"].get("level"), 90)
        self.assertNotIn("character.level", candidate.missing_fields)
        self.assertIn("raiderioCharacterDetails", candidate.provenance)
        original = candidate.raw_sha256
        details["characterDetails"]["character"]["level"] = 89
        changed = RaiderIOCharacterAdapter(gateway, official_enricher=official).resolve(
            parse_character_source_url("https://raider.io/cn/characters/cn/silver-hand/Giannis"))
        self.assertNotEqual(original, changed.raw_sha256)

    def test_cn_details_identity_mismatch_never_fills_level(self):
        for field, value in [("name", "SomeoneElse"), ("level", True),
                             ("region", {"slug": "us"}), ("realm", {"slug": "other"}),
                             ("class", {"slug": "mage"}), ("path", "/characters/cn/other/Giannis")]:
            with self.subTest(field=field):
                gateway, official, _, details, _, _ = self._giannis_gateway()
                details["characterDetails"]["character"][field] = value
                candidate = RaiderIOCharacterAdapter(gateway, official_enricher=official).resolve(
                    parse_character_source_url("https://raider.io/cn/characters/cn/silver-hand/Giannis"))
                self.assertIn("character.level", candidate.missing_fields)

    def test_wcl_giannis_uses_fight_gear_and_verified_equivalent_talent_export(self):
        gateway, official, _, details, report, _ = self._giannis_gateway()
        candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
            parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
        self.assertEqual(candidate.missing_fields, ())
        self.assertEqual(candidate.snapshot["character"]["level"], 90)
        self.assertEqual(candidate.snapshot["character"]["raceKey"], "dark_iron_dwarf")
        self.assertEqual(candidate.snapshot["gear"]["head"]["enchant"], 8017)
        self.assertEqual(candidate.snapshot["gear"]["neck"]["gems"], [240983])
        self.assertEqual(candidate.snapshot["gear"]["main_hand"]["itemId"], 245770)
        self.assertEqual(candidate.snapshot["gearState"]["unequippedSlots"], ["off_hand"])
        expected = json.loads((Path(__file__).parent / "fixtures/simc/giannis_wcl_engine_export_69814.json").read_text())
        self.assertEqual(candidate.snapshot["talents"]["string"], expected["talents"])
        self.assertIn("wclCombatantInfo", candidate.provenance)
        from server.app.simulation.compiler import SimcProfileCompiler
        from server.app.simulation.readiness import SimcRuntimeCapabilities, SimcReadinessValidator
        capabilities = SimcRuntimeCapabilities("simc:managed:ac0f3a3c7ff9e521137c0ca1760d548330c697f3:" + "a" * 64, "chickenbro-simc-compiler-v3", frozenset({("shaman", "elemental")}))
        saved = candidate.to_source_snapshot(user_id="00000000-0000-4000-8000-000000000001",
            snapshot_id="00000000-0000-4000-8000-000000000002",
            readiness_report=SimcReadinessValidator().validate(candidate, capabilities))
        profile = SimcProfileCompiler(capabilities=capabilities).compile(saved, {}).profile
        self.assertIn("server=silver-hand", profile)
        self.assertIn("level=90", profile)
        self.assertIn("talents=CYQ", profile)

        self.assertTrue(any("includeCombatantInfo: true" in c[1].get("json_body", {}).get("query", "") for c in gateway.calls))

    def test_wcl_talent_change_never_silently_uses_current_profile_talents(self):
        gateway, official, _, details, report, _ = self._giannis_gateway()
        report["data"]["reportData"]["report"]["events"]["data"][0]["talentTree"][0]["rank"] = 2
        candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
            parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
        self.assertIn("talents.loadout", candidate.missing_fields)
        self.assertNotIn("string", candidate.snapshot["talents"])

    def test_wcl_historical_talents_survive_current_character_respec(self):
        gateway, official, _, details, _, _ = self._giannis_gateway()
        expected = json.loads((Path(__file__).parent / "fixtures/simc/giannis_wcl_engine_export_69814.json").read_text())["talents"]
        # A later respec must not alter or invalidate the recorded fight build.
        details["characterDetails"]["character"]["talentLoadout"]["nodes"] = []
        details["characterDetails"]["character"]["talentLoadout"]["loadoutText"] = "AAAA"
        candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
            parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
        self.assertEqual(candidate.missing_fields, ())
        self.assertEqual(candidate.snapshot["talents"].get("string"), expected)
        self.assertEqual(candidate.provenance["wclTalentReconstruction"]["entryCount"], 80)

    def test_wcl_fight_survives_current_character_changing_specialization(self):
        gateway, official, _, details, _, _ = self._giannis_gateway()
        details["characterDetails"]["character"]["spec"].update(id=263, slug="enhancement")
        candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
            parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
        self.assertEqual(candidate.missing_fields, ())
        self.assertEqual(candidate.snapshot["character"]["specKey"], "elemental")

    def test_wcl_wrong_event_spec_cannot_use_current_export(self):
        gateway, official, _, _, report, _ = self._giannis_gateway()
        report["data"]["reportData"]["report"]["events"]["data"][0]["specID"] = 263
        candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
            parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
        self.assertIn("talents.loadout", candidate.missing_fields)

    def test_wcl_wrong_fight_or_actor_event_cannot_supply_gear(self):
        for field, value in [("fight", 2), ("sourceID", 5)]:
            gateway, official, _, _, report, _ = self._giannis_gateway()
            report["data"]["reportData"]["report"]["events"]["data"][0][field] = value
            candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
                parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
            self.assertIn("gear.head", candidate.missing_fields)

    def test_wcl_metadata_identity_or_level_mismatch_stays_incomplete(self):
        for field, value in [("name", "Other"), ("level", 89), ("level", True)]:
            with self.subTest(field=field):
                gateway, official, _, _, _, identity = self._giannis_gateway()
                identity["data"]["characterData"]["character"][field] = value
                candidate = WclCharacterAdapter(gateway, access_token="fixture", official_enricher=official).resolve(
                    parse_character_source_url("https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4"))
                self.assertIn("character.level", candidate.missing_fields)
                self.assertIn("talents.loadout", candidate.missing_fields)
                self.assertEqual(candidate.snapshot["gear"]["head"]["itemId"], 271483)

    def test_talent_export_requires_exact_choices_and_no_duplicate_log_entries(self):
        from server.app.simulation.source_details import matching_talent_export
        for mutation in ("choice", "duplicate", "missing", "different_spec"):
            gateway, official, _, details, report, _ = self._giannis_gateway()
            character = details["characterDetails"]["character"]
            tree = report["data"]["reportData"]["report"]["events"]["data"][0]["talentTree"]
            if mutation == "choice":
                next(e for e in tree if e["nodeID"] == 99845)["id"] = 123376
            elif mutation == "duplicate": tree.append(tree[0])
            elif mutation == "missing": tree.pop()
            elif mutation == "different_spec": character["spec"]["slug"] = "restoration"
            self.assertEqual(matching_talent_export(tree, character, "elemental"), "", mutation)

    def _ranking_source(self):
        primary = json.loads((FIXTURE_DIR / "raiderio_ready.json").read_text())
        primary.pop("level")
        affixes = {
            "region": "us",
            "leaderboard_url": "https://raider.io/mythic-plus-affix-rankings/season-example-2/all/us/leaderboards-strict/current",
        }
        ranked = {
            "name": "Stormsample", "region": {"slug": "us"},
            "realm": {"slug": "area-52"}, "class": {"slug": "shaman"},
            "spec": {"slug": "elemental"}, "race": {"slug": "tauren"},
            "path": "/characters/us/area-52/Stormsample", "level": 90,
        }
        rankings = {"rankings": {"rankedCharacters": [{"rank": 1, "character": ranked}]}}

        class Gateway(FakeGateway):
            def fetch_json(self, url, **kwargs):
                self.urls.append((url, {}))
                if "/affixes?" in url:
                    return affixes
                if "/rankings/specs?" in url:
                    return rankings
                return primary

        gateway = Gateway(primary)
        adapter = RaiderIOCharacterAdapter(
            gateway, official_enricher=BlizzardProfileEnricher(gateway, token_provider=lambda: ""),
        )
        parsed = parse_character_source_url("https://raider.io/characters/us/area-52/Stormsample")
        return adapter, parsed, primary, affixes, rankings, ranked, gateway

    def test_current_ranking_fills_explicit_level_and_binds_both_metadata_inputs(self):
        adapter, parsed, primary, affixes, rankings, ranked, gateway = self._ranking_source()
        candidate = adapter.resolve(parsed)

        self.assertEqual(candidate.snapshot["character"].get("level"), 90)
        self.assertNotIn("character.level", candidate.missing_fields)
        metadata = candidate.provenance["raiderioLevelMetadata"]
        self.assertEqual(metadata["season"], "season-example-2")
        self.assertEqual(metadata["characterPath"], ranked["path"])
        self.assertEqual(metadata["affixesRawSha256"], sha256_json(affixes))
        self.assertEqual(metadata["rankingsRawSha256"], sha256_json(rankings))
        self.assertIn("season=season-example-2", gateway.urls[-1][0])
        self.assertIn("class=shaman&spec=elemental&page=0", gateway.urls[-1][0])
        original_hash = candidate.raw_sha256
        primary["profileRevision"] = "new-primary-revision"
        self.assertNotEqual(original_hash, adapter.resolve(parsed).raw_sha256)
        primary_hash = adapter.resolve(parsed).raw_sha256
        ranked["level"] = 89
        self.assertNotEqual(primary_hash, adapter.resolve(parsed).raw_sha256)
        ranking_hash = adapter.resolve(parsed).raw_sha256
        affixes["title"] = "changed-current-affixes"
        self.assertNotEqual(ranking_hash, adapter.resolve(parsed).raw_sha256)

    def test_ranking_mismatches_and_invalid_levels_never_fill_missing_level(self):
        for field, value in (
            ("name", "Someoneelse"), ("region", {"slug": "eu"}),
            ("realm", {"slug": "sargeras"}), ("class", {"slug": "mage"}),
            ("spec", {"slug": "enhancement"}), ("race", {"slug": "orc"}),
            ("path", "/characters/us/sargeras/Stormsample"),
            ("level", None), ("level", True), ("level", 90.5), ("level", -1),
        ):
            with self.subTest(field=field, value=value):
                adapter, parsed, primary, affixes, rankings, ranked, gateway = self._ranking_source()
                ranked[field] = value
                candidate = adapter.resolve(parsed)
                self.assertIn("character.level", candidate.missing_fields)
                self.assertNotIn("raiderioLevelMetadata", candidate.provenance)
                self.assertEqual(candidate.raw_sha256, sha256_json(primary))

    def test_ranking_absence_ambiguity_and_untrusted_season_remain_incomplete(self):
        for case in ("absent", "duplicate", "malformed", "wrong-region", "foreign-url", "primary-mismatch"):
            with self.subTest(case=case):
                adapter, parsed, primary, affixes, rankings, ranked, gateway = self._ranking_source()
                if case == "absent":
                    rankings["rankings"]["rankedCharacters"] = []
                elif case == "duplicate":
                    rankings["rankings"]["rankedCharacters"].append({"character": copy.deepcopy(ranked)})
                elif case == "malformed":
                    rankings["rankings"] = []
                elif case == "wrong-region":
                    affixes["region"] = "eu"
                elif case == "foreign-url":
                    affixes["leaderboard_url"] = affixes["leaderboard_url"].replace("raider.io", "evil.example")
                else:
                    primary["name"] = "DifferentCharacter"
                candidate = adapter.resolve(parsed)
                self.assertIn("character.level", candidate.missing_fields)
                self.assertNotIn("raiderioLevelMetadata", candidate.provenance)
                self.assertLessEqual(len(gateway.urls), 4)

    def test_ranking_fetch_failure_retains_primary_snapshot_and_missing_level(self):
        for failing_endpoint in ("/affixes?", "/rankings/specs?"):
            with self.subTest(endpoint=failing_endpoint):
                adapter, parsed, primary, affixes, rankings, ranked, gateway = self._ranking_source()
                fetch = gateway.fetch_json

                def fail_metadata(url, **kwargs):
                    if failing_endpoint in url:
                        raise SourceHttpError(502)
                    return fetch(url, **kwargs)

                gateway.fetch_json = fail_metadata
                candidate = adapter.resolve(parsed)
                self.assertIn("character.level", candidate.missing_fields)
                self.assertEqual(candidate.snapshot["gear"]["neck"]["gems"], [2001])
                self.assertEqual(candidate.snapshot["gear"]["head"]["bonusIds"], [1, 2])
                self.assertEqual(candidate.raw_sha256, sha256_json(primary))

    def test_present_primary_level_and_unsupported_region_do_not_use_rankings(self):
        adapter, parsed, primary, affixes, rankings, ranked, gateway = self._ranking_source()
        primary["level"] = 80
        candidate = adapter.resolve(parsed)
        self.assertEqual(candidate.snapshot["character"]["level"], 80)
        self.assertEqual(len(gateway.urls), 1)

        primary.pop("level")
        primary["region"] = "cn"
        gateway.urls.clear()
        candidate = adapter.resolve(parse_character_source_url(
            "https://raider.io/characters/cn/area-52/Stormsample",
        ))
        self.assertIn("character.level", candidate.missing_fields)
        self.assertEqual(len(gateway.urls), 2)

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
        self.assertEqual(len(gateway.urls), 2)

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

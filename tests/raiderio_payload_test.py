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

from server import raiderio_payload, websim_payload
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


BLIZZARD_TALENT_BASE64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def write_bits(bits, value, count):
    for index in range(count):
        bits.append((int(value) >> index) & 1)


def blizzard_import_code(spec_id, node_choices):
    bits = []
    write_bits(bits, 2, 8)
    write_bits(bits, spec_id, 16)
    write_bits(bits, 0, 128)
    for selected, rank, choice_index in node_choices:
        write_bits(bits, 1 if selected else 0, 1)
        if not selected:
            continue
        write_bits(bits, 1, 1)
        if int(rank or 1) > 1:
            write_bits(bits, 1, 1)
            write_bits(bits, rank, 6)
        else:
            write_bits(bits, 0, 1)
        if int(choice_index or 0) > 0:
            write_bits(bits, 1, 1)
            write_bits(bits, choice_index, 2)
        else:
            write_bits(bits, 0, 1)
    encoded = []
    for offset in range(0, len(bits), 6):
        value = 0
        for bit_index, bit in enumerate(bits[offset : offset + 6]):
            value |= bit << bit_index
        encoded.append(BLIZZARD_TALENT_BASE64[value])
    return "".join(encoded)


def write_minimal_dk_trait_data(path):
    path.write_text(
        """
__trait_sub_tree_data = {
  { 31, "San'layn", 6 },
  { 32, "Rider of the Apocalypse", 6 },
};
__trait_data = {
  { 4,  6, 5001,    100, 1,  0,      0,     111,      0,      0,  1,  1,   0, "Plague Blade", {  252,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 1 },
  { 4,  6, 5002,    200, 1,  0,      0,     222,      0,      0,  2,  1,   0, "Sanguine Gift", {  252,    0,    0,    0 }, {    0,    0,    0,    0 },  31, 1 },
  { 4,  6, 123322, 99820, 1,  0,      0,       0,      0,      0,  1,  1, 100, "0", {  252,    0,    0,    0 }, {    0,    0,    0,    0 },  32, 3 },
  { 4,  6, 123321, 99820, 1,  0,      0,       0,      0,      0,  1,  1, 200, "0", {  252,    0,    0,    0 }, {    0,    0,    0,    0 },  31, 3 },
};
""".strip()
        + "\n",
        encoding="utf-8",
    )


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

    def test_extract_gear_preserves_raiderio_enhancements_and_embellishment_bonus(self):
        profile = sample_profile_payload("听凭风引", "shaman", "elemental")
        profile["gear"]["items"] = {
            "back": {
                "item_id": 239656,
                "item_level": 298,
                "name": "Adherent's Silken Shroud",
                "icon": "inv_cape_01",
                "item_quality": "Epic",
                "bonuses": [12214, 13667, 12497, 12066, 8960, 12384, 8791, 13622],
                "gems": [{"item_id": 240908, "name": "Masterful Emerald"}],
                "enchants": [{"enchant": 7403, "name": "Chant of Leeching Fangs"}],
            }
        }

        gear = raiderio_payload.extract_gear(profile)

        self.assertEqual(len(gear), 1)
        item = gear[0]
        self.assertEqual(item["slot"], "back")
        self.assertEqual(item["bonus_id"], "12214/13667/12497/12066/8960/12384/8791/13622")
        self.assertEqual(item["gem_id"], "240908")
        self.assertEqual(item["enchant_id"], "7403")
        self.assertEqual(item["embellishment"], "arcanoweave_lining")
        self.assertEqual(item["embellishmentLabel"], "奥纹内衬")
        self.assertEqual(item["enhancementSource"], "raiderio_profile_gear")

    def test_extract_gear_preserves_duplicate_gem_occurrences_in_order(self):
        profile = sample_profile_payload("Gemorder", "mage", "frost")
        profile["gear"]["items"] = {
            "finger1": {
                "item_id": 250777,
                "item_level": 707,
                "name": "Occurrence Band",
                "bonuses": [12345, 12345],
                "gems": [
                    {"item_id": 240983},
                    {"itemId": "240983"},
                    None,
                    {},
                    {"item_id": 0},
                    {"item_id": "0"},
                    {"name": "missing identifier"},
                    {"gem_id": 240892},
                ],
                "enchants": [
                    {"enchant": 8017},
                    {"enchant_id": "8017"},
                ],
            }
        }

        item = raiderio_payload.extract_gear(profile)[0]

        self.assertEqual(item["gem_id"], "240983/240983/240892")
        self.assertEqual(item["bonus_id"], "12345")
        self.assertEqual(item["enchant_id"], "8017")

    def test_midnight_mage_reference_preserves_all_ordered_gem_and_enchant_occurrences(self):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "midnight-mage-frost-socket-evidence-v1.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        reference = fixture["referenceContract"]
        items_by_slot = {
            item["slot"]: item
            for item in fixture["snapshot"]["items"]
            if item["slot"] in reference["requiredSlots"]
            and item["itemId"] != "different-ring-one"
        }
        variants_by_item = {
            variant["itemId"]: variant
            for variant in fixture["snapshot"]["variants"]
            if variant["itemId"] != "different-ring-one"
        }
        profile = sample_profile_payload("Mageparity", "mage", "frost")
        profile["gear"]["items"] = {}
        for slot in reference["requiredSlots"]:
            source_item = items_by_slot[slot]
            variant = variants_by_item[source_item["itemId"]]
            simc_options = variant["simcOptions"]
            source = reference["sourceEnhancementBySlot"].get(slot, {})
            self.assertEqual(
                simc_options.get("gem_id", ""),
                "/".join(source.get("gemIds", [])),
            )
            self.assertEqual(
                simc_options.get("enchant_id", ""),
                "/".join(source.get("enchantIds", [])),
            )
            self.assertEqual(
                simc_options.get("embellishment", ""),
                source.get("embellishment", ""),
            )
            item = {
                "item_id": int(source_item["itemId"]),
                "item_level": int(simc_options["ilevel"]),
                "name": source_item["name"],
                "bonuses": [
                    int(bonus_id)
                    for bonus_id in simc_options["bonus_id"].split("/")
                ],
                "gems": [
                    {"item_id": gem_id}
                    for gem_id in source.get("gemIds", [])
                ],
                "enchants": [
                    {"enchant": enchant_id}
                    for enchant_id in source.get("enchantIds", [])
                ],
            }
            profile["gear"]["items"][slot] = item

        by_slot = {item["slot"]: item for item in raiderio_payload.extract_gear(profile)}
        ordered_gems = [
            gem_id
            for instance in fixture["expectedInstances"]
            for gem_id in by_slot[
                raiderio_payload.normalize_gear_slot(instance["slot"])
            ].get("gem_id", "").split("/")
            if gem_id
        ]

        self.assertEqual(
            ordered_gems,
            [
                gem_id
                for instance in fixture["expectedInstances"]
                for gem_id in instance["gemIds"]
            ],
        )
        self.assertEqual(ordered_gems.count("240983"), 1)
        self.assertEqual(ordered_gems.count("240892"), 4)
        self.assertEqual(ordered_gems.count("240916"), 2)
        self.assertEqual(ordered_gems.count("240900"), 1)
        canonical_enchant_slots = [
            slot
            for slot, enhancement in reference["canonicalEnhancementBySlot"].items()
            if enhancement.get("enchantId")
        ]
        self.assertEqual(
            canonical_enchant_slots,
            ["back", "chest", "legs", "feet", "finger1", "finger2"],
        )
        for slot in canonical_enchant_slots:
            normalized_slot = raiderio_payload.normalize_gear_slot(slot)
            self.assertEqual(
                by_slot[normalized_slot]["enchant_id"],
                reference["canonicalEnhancementBySlot"][slot]["enchantId"],
            )
        self.assertEqual(
            sum(bool(item.get("enchant_id")) for item in by_slot.values()),
            10,
        )
        self.assertEqual(by_slot["head"]["enchant_id"], "8017")
        self.assertEqual(by_slot["shoulder"]["enchant_id"], "8001")
        self.assertEqual(by_slot["waist"]["enchant_id"], "4223")
        self.assertEqual(by_slot["main_hand"]["enchant_id"], "8039/8052")
        self.assertEqual(by_slot["back"]["embellishment"], "arcanoweave_lining")
        self.assertEqual(by_slot["wrist"]["embellishment"], "arcanoweave_lining")
        for slot in reference["requiredSlots"]:
            source_item = items_by_slot[slot]
            variant = variants_by_item[source_item["itemId"]]
            simc_options = variant["simcOptions"]
            normalized_slot = raiderio_payload.normalize_gear_slot(slot)
            self.assertEqual(
                by_slot[normalized_slot]["itemId"], int(source_item["itemId"])
            )
            self.assertEqual(
                by_slot[normalized_slot]["itemLevel"], int(simc_options["ilevel"])
            )
            self.assertEqual(
                by_slot[normalized_slot]["bonus_id"], simc_options["bonus_id"]
            )

    def test_fetch_profiles_for_runs_attaches_spec_ranking_evidence_to_profile(self):
        run = raiderio_payload.simplify_spec_ranking_run(
            {
                "rank": 1,
                "score": 4249.17,
                "character": {
                    "name": "听凭风引",
                    "realm": {"name": "Sylvanas", "slug": "sylvanas"},
                    "region": {"slug": "cn"},
                    "class": {"name": "Shaman", "slug": "shaman"},
                    "spec": {"name": "Elemental", "slug": "elemental"},
                },
            },
            {"keystoneRunId": 9001, "zoneName": "Ara-Kara", "mythicLevel": 23, "score": 512.4},
            "shaman",
            "elemental",
            "world",
            "https://raider.io/mythic-plus-spec-rankings/season-mn-1/world/shaman/elemental",
        )

        def fake_fetch(character, fields):
            summary = raiderio_payload.profile_summary(sample_profile_payload(
                character["name"],
                "shaman",
                "elemental",
            ))
            summary["region"] = character["region"]
            summary["realmSlug"] = character["realmSlug"]
            summary["profileUrl"] = character["profileUrl"]
            return summary

        with patch.object(raiderio_payload, "fetch_profile_for_character", fake_fetch):
            profiles, errors = raiderio_payload.fetch_profiles_for_runs([run])

        self.assertEqual(errors, [])
        self.assertEqual(len(profiles), 1)
        profile = next(iter(profiles.values()))
        evidence = profile["rankingEvidence"]
        self.assertEqual(evidence["source"], "raiderio_spec_ranking")
        self.assertEqual(evidence["rank"], 1)
        self.assertEqual(evidence["score"], 4249.17)
        self.assertEqual(evidence["maxKeyLevel"], 23)
        self.assertEqual(evidence["runId"], 9001)
        self.assertEqual(evidence["sourceUrl"], "https://raider.io/mythic-plus-spec-rankings/season-mn-1/world/shaman/elemental")

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

    def test_sync_raiderio_cache_scans_configured_regions_and_preserves_template_region(self):
        os.environ["WOW_RAIDERIO_REGIONS"] = "cn,eu"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "0"
        fetched_run_regions = []
        fetched_profile_regions = []

        def run_payload(region):
            name = "Cnplayer" if region == "cn" else "Euplayer"
            return {
                "leaderboard_url": f"https://raider.io/mythic-plus-rankings/season-mn-1/all/{region}/leaderboards",
                "rankings": [
                    {
                        "rank": 1,
                        "score": 4127.57,
                        "run": {
                            "keystone_run_id": 1001 if region == "cn" else 2001,
                            "dungeon": {"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"},
                            "mythic_level": 24,
                            "roster": [
                                {
                                    "character": {
                                        "name": name,
                                        "realm": {"name": "Isillien", "slug": "isillien"},
                                        "class": {"name": "Mage", "slug": "mage"},
                                        "spec": {"id": 64, "name": "Frost", "slug": "frost"},
                                    }
                                }
                            ],
                        },
                    }
                ],
            }

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                fetched_run_regions.append(params["region"])
                return run_payload(params["region"])
            if path == "/characters/profile":
                fetched_profile_regions.append(params["region"])
                profile = sample_profile_payload(params["name"])
                profile["region"] = params["region"]
                profile["profile_url"] = f"https://raider.io/characters/{params['region']}/isillien/{params['name']}"
                return profile
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                self.assertEqual(params["region"], "cn")
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                self.assertEqual(params["region"], "cn")
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(fetched_run_regions, ["cn", "eu"])
        self.assertEqual(fetched_profile_regions, ["cn", "eu"])
        self.assertEqual(payload["regions"], ["cn", "eu"])
        self.assertEqual(payload["regionCoverage"]["cn"]["runCount"], 1)
        self.assertEqual(payload["regionCoverage"]["eu"]["runCount"], 1)
        by_player = {item["playerId"]: item for item in payload["communityTemplates"]}
        self.assertEqual(by_player["Cnplayer"]["payload"]["raiderio"]["region"], "cn")
        self.assertEqual(by_player["Euplayer"]["payload"]["raiderio"]["region"], "eu")
        self.assertEqual(payload["specCoverage"]["sampleCounts"]["mage:frost"], 2)

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

    def test_aggregate_runs_prefers_run_detail_talent_snapshot_over_profile_current(self):
        run = raiderio_payload.simplify_run({
            "rank": 1,
            "score": 4127.57,
            "run": {
                "keystone_run_id": 101,
                "dungeon": {"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"},
                "mythic_level": 24,
                "roster": [
                    {
                        "character": {
                            "name": "Rioone",
                            "realm": {"name": "Isillien", "slug": "isillien"},
                            "region": {"slug": "cn"},
                            "class": {"name": "Mage", "slug": "mage"},
                            "spec": {"id": 64, "name": "Frost", "slug": "frost"},
                        },
                        "loadout": "RUN_DETAIL_IMPORT_CODE",
                    }
                ],
            },
        })
        run["roster"][0]["talentLoadout"] = {
            "rawImportCode": "RUN_DETAIL_IMPORT_CODE",
            "loadoutSpecId": 64,
            "loadout": [{"traitId": 91001, "rank": 1}],
            "source": "run_detail",
        }
        profile = raiderio_payload.profile_summary({
            **sample_profile_payload(),
            "talentLoadout": {
                "loadout_text": "PROFILE_CURRENT_ARCANE",
                "loadout_spec_id": 62,
                "loadout": [{"traitId": 99999, "rank": 1}],
            },
        })

        aggregates = raiderio_payload.aggregate_runs([run], {raiderio_payload.character_key(profile): profile})
        templates = raiderio_payload.build_community_templates(aggregates, "2026-07-03T01:00:00+00:00")

        mage_template = next(item for item in templates if item["playerId"] == "Rioone")
        self.assertEqual(mage_template["rawImportCode"], "RUN_DETAIL_IMPORT_CODE")
        self.assertEqual(mage_template["payload"]["raiderio"]["source"], "run_detail")
        self.assertEqual(mage_template["payload"]["raiderio"]["loadout"][0]["traitId"], 91001)

    def test_sync_raiderio_cache_uses_run_detail_talent_snapshots_for_templates(self):
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "2"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC"] = "2"

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                payload = sample_runs_payload()
                payload["rankings"][0]["run"]["keystone_run_id"] = 101
                payload["rankings"][0]["run"]["roster"][0]["loadout"] = "RUN_DETAIL_IMPORT_CODE"
                return payload
            if path == "/mythic-plus/run-details":
                self.assertEqual(params["id"], 101)
                return {
                    "keystone_run_id": 101,
                    "roster": [
                        {
                            "character": {
                                "name": "Rioone",
                                "realm": {"name": "Isillien", "slug": "isillien"},
                                "region": {"slug": "cn"},
                                "class": {"name": "Mage", "slug": "mage"},
                                "spec": {"id": 64, "name": "Frost", "slug": "frost"},
                                "path": "/characters/cn/isillien/Rioone",
                                "talentLoadout": {
                                    "specId": 64,
                                    "heroSubTreeId": 123,
                                    "loadout": [{"traitId": 91001, "rank": 1}],
                                },
                            }
                        }
                    ],
                }
            if path == "/characters/profile":
                return {
                    **sample_profile_payload(params["name"]),
                    "talentLoadout": {
                        "loadout_text": "PROFILE_CURRENT_ARCANE",
                        "loadout_spec_id": 62,
                        "loadout": [{"traitId": 99999, "rank": 1}],
                    },
                }
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        mage_template = next(item for item in payload["communityTemplates"] if item["playerId"] == "Rioone")
        self.assertEqual(mage_template["rawImportCode"], "RUN_DETAIL_IMPORT_CODE")
        self.assertEqual(mage_template["payload"]["raiderio"]["source"], "run_detail")
        self.assertEqual(payload["runDetailCoverage"]["requestedRunCount"], 1)
        self.assertEqual(payload["runDetailCoverage"]["talentSnapshotCount"], 1)

    def test_run_detail_snapshots_are_keyed_by_region_and_run_id(self):
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "2"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC"] = "2"
        runs = []
        for region, name in [("cn", "Cnplayer"), ("eu", "Euplayer")]:
            runs.append({
                "runId": 101,
                "region": region,
                "roster": [
                    {
                        "name": name,
                        "realmSlug": "isillien",
                        "region": region,
                        "classKey": "mage",
                        "className": "Mage",
                        "specKey": "frost",
                        "specName": "Frost",
                    }
                ],
            })

        def fake_fetch_run_detail(run, season_slug):
            name = run["roster"][0]["name"]
            region = run["region"]
            return {
                "keystone_run_id": 101,
                "roster": [
                    {
                        "character": {
                            "name": name,
                            "realm": {"name": "Isillien", "slug": "isillien"},
                            "region": {"slug": region},
                            "class": {"name": "Mage", "slug": "mage"},
                            "spec": {"id": 64, "name": "Frost", "slug": "frost"},
                            "talentLoadout": {
                                "specId": 64,
                                "loadout": [{"traitId": 91001 if region == "cn" else 91002, "rank": 1}],
                            },
                        }
                    }
                ],
            }

        with patch.object(raiderio_payload, "fetch_run_detail", fake_fetch_run_detail):
            enriched, summary = raiderio_payload.fetch_run_details_for_runs(runs, season_slug="season-mn-1")

        self.assertEqual(summary["requestedRunCount"], 2)
        self.assertEqual(summary["talentSnapshotCount"], 2)
        self.assertEqual(enriched[0]["roster"][0]["talentLoadout"]["loadout"][0]["traitId"], 91001)
        self.assertEqual(enriched[1]["roster"][0]["talentLoadout"]["loadout"][0]["traitId"], 91002)

    def test_run_detail_candidates_skip_already_enriched_runs_for_gap_fill(self):
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "4"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC"] = "2"
        runs = [
            {
                "runId": 101,
                "region": "world",
                "roster": [
                    {
                        "name": "Oldaug",
                        "realmSlug": "isillien",
                        "region": "world",
                        "classKey": "evoker",
                        "specKey": "augmentation",
                        "talentLoadout": {
                            "source": "run_detail",
                            "heroSubTreeId": 36,
                            "loadout": [{"traitId": 91001, "rank": 1}],
                        },
                    }
                ],
            },
            {
                "runId": 102,
                "region": "world",
                "roster": [
                    {
                        "name": "Newaug",
                        "realmSlug": "isillien",
                        "region": "world",
                        "classKey": "evoker",
                        "specKey": "augmentation",
                    }
                ],
            },
        ]

        candidates = raiderio_payload.select_run_detail_candidates(runs)

        self.assertEqual([run["runId"] for run in candidates], [102])

    def test_run_detail_candidates_preserve_later_hero_subtree_within_spec_budget(self):
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "3"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC"] = "3"
        runs = []
        for index, hero_subtree_id in enumerate([36, 36, 36, 38], start=1):
            runs.append(
                {
                    "runId": 200 + index,
                    "region": "world",
                    "roster": [
                        {
                            "name": f"Aug{index}",
                            "realmSlug": "isillien",
                            "region": "world",
                            "classKey": "evoker",
                            "specKey": "augmentation",
                            "talentLoadout": {
                                "heroSubTreeId": hero_subtree_id,
                            },
                        }
                    ],
                }
            )

        candidates = raiderio_payload.select_run_detail_candidates(runs)

        self.assertEqual([run["runId"] for run in candidates], [201, 202, 204])

    def test_gap_fill_run_detail_candidates_spread_across_raw_spec_ranking_runs(self):
        runs = []
        for index in range(1, 11):
            runs.append(
                {
                    "runId": index,
                    "region": "world",
                    "roster": [
                        {
                            "name": f"Longtail{index}",
                            "realmSlug": "isillien",
                            "region": "world",
                            "classKey": "hunter",
                            "specKey": "survival",
                        }
                    ],
                }
            )

        candidates = raiderio_payload.select_run_detail_candidates(
            runs,
            limit=3,
            per_spec_limit=3,
            spread_by_spec=True,
        )

        self.assertEqual([run["runId"] for run in candidates], [1, 5, 10])

    def test_gap_fill_run_detail_candidates_keep_frontload_before_spread(self):
        runs = []
        for index in range(1, 11):
            runs.append(
                {
                    "runId": index,
                    "region": "world",
                    "roster": [
                        {
                            "name": f"Longtail{index}",
                            "realmSlug": "isillien",
                            "region": "world",
                            "classKey": "rogue",
                            "specKey": "subtlety",
                        }
                    ],
                }
            )

        candidates = raiderio_payload.select_run_detail_candidates(
            runs,
            limit=5,
            per_spec_limit=5,
            spread_by_spec=True,
            frontload_per_spec=3,
        )

        self.assertEqual([run["runId"] for run in candidates], [1, 2, 3, 7, 10])

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

    def test_sync_raiderio_cache_exposes_per_spec_target_matrix(self):
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "0"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "2"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "2"

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

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "expected_spec_pairs",
            return_value=["mage:frost", "mage:fire"],
        ), patch.object(raiderio_payload, "api_get", fake_api_get):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        matrix = payload["targetMatrix"]
        by_spec = {row["specId"]: row for row in matrix["rows"]}

        self.assertEqual(matrix["totalSpecCount"], 2)
        self.assertEqual(matrix["attemptedSpecCount"], 1)
        self.assertEqual(matrix["pendingSpecCount"], 1)
        self.assertEqual(by_spec["mage:frost"]["attemptedRunCount"], 1)
        self.assertGreaterEqual(by_spec["mage:frost"]["profileCount"], 1)
        self.assertGreaterEqual(by_spec["mage:frost"]["candidateCount"], 1)
        self.assertIn("validate", by_spec["mage:frost"]["nextAction"])
        self.assertEqual(by_spec["mage:fire"]["attemptedRunCount"], 0)
        self.assertIn("class/spec ranking", by_spec["mage:fire"]["nextAction"])

    def test_sync_raiderio_cache_fetches_enabled_spec_ranking_target_pool(self):
        os.environ["WOW_RAIDERIO_SPEC_RANKING_ENABLED"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_REGIONS"] = "world"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE"] = "2"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_RUNS_PER_CHARACTER"] = "1"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "0"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "4"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT_PER_SPEC"] = "2"
        spec_ranking_calls = []
        fetched_profiles = []

        def ranking_character(name, target_spec_slug, run_id):
            return {
                "rank": 1,
                "score": 3999.5,
                "character": {
                    "name": name,
                    "realm": {"name": "Isillien", "slug": "isillien"},
                    "region": {"slug": "cn"},
                    "class": {"name": "Mage", "slug": "mage"},
                    # Raider.IO spec ranking rows can expose the character's current spec,
                    # so the collector must keep the requested class/spec as the target.
                    "spec": {"id": 62, "name": "Arcane", "slug": "arcane"},
                    "path": f"/characters/cn/isillien/{name}",
                },
                "runs": [{"keystoneRunId": run_id, "mythicLevel": 22, "score": 511.2}],
            }

        def fake_web_api_get(path, params=None):
            self.assertEqual(path, "/mythic-plus/rankings/specs")
            spec_ranking_calls.append((params["region"], params["class"], params["spec"], params["page"]))
            target_spec = params["spec"]
            return {
                "rankings": {
                    "rankedCharacters": [
                        ranking_character(f"Spec{target_spec}", target_spec, 5000 + len(spec_ranking_calls))
                    ]
                }
            }

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return sample_runs_payload()
            if path == "/characters/profile":
                fetched_profiles.append(params["name"])
                if params["name"] == "Specfire":
                    return sample_profile_payload("Specfire", "mage", "fire")
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
            "expected_spec_pairs",
            return_value=["mage:frost", "mage:fire"],
        ), patch.object(raiderio_payload, "api_get", fake_api_get), patch.object(
            raiderio_payload,
            "web_api_get",
            fake_web_api_get,
            create=True,
        ):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(
            spec_ranking_calls,
            [("world", "mage", "frost", 0), ("world", "mage", "fire", 0)],
        )
        self.assertIn("Specfire", fetched_profiles)
        self.assertEqual(payload["specRankingCoverage"]["enabled"], True)
        self.assertEqual(payload["specRankingCoverage"]["attemptedSpecCount"], 2)
        by_spec = {row["specId"]: row for row in payload["targetMatrix"]["rows"]}
        self.assertGreaterEqual(by_spec["mage:fire"]["attemptedRunCount"], 1)
        self.assertGreaterEqual(by_spec["mage:fire"]["profileCount"], 1)

    def test_sync_raiderio_cache_can_target_specs_without_global_runs(self):
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "0"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_ENABLED"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS"] = "mage:frost"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_REGIONS"] = "world"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE"] = "1"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "0"
        spec_ranking_calls = []

        def fake_web_api_get(path, params=None):
            self.assertEqual(path, "/mythic-plus/rankings/specs")
            spec_ranking_calls.append((params["class"], params["spec"], params["page"]))
            return {"rankings": {"rankedCharacters": []}}

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                raise AssertionError("targeted spec sync should skip global run pages")
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(raiderio_payload, "api_get", fake_api_get), patch.object(
            raiderio_payload,
            "web_api_get",
            fake_web_api_get,
            create=True,
        ):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(spec_ranking_calls, [("mage", "frost", 0)])
        self.assertEqual(payload["runCount"], 0)
        self.assertEqual(payload["specRankingCoverage"]["attemptedSpecCount"], 1)

    def test_sync_raiderio_cache_gap_fills_specs_missing_second_hero_subtree(self):
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_ENABLED"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_REGIONS"] = "world"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_RUNS_PER_CHARACTER"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_ENABLED"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "10"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC"] = "10"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "3"
        spec_ranking_calls = []

        def ranking_character(name, run_id):
            return {
                "rank": run_id,
                "score": 3999.5,
                "character": {
                    "name": name,
                    "realm": {"name": "Isillien", "slug": "isillien"},
                    "region": {"slug": "cn"},
                    "class": {"name": "Mage", "slug": "mage"},
                    "spec": {"id": 63, "name": "Fire", "slug": "fire"},
                    "path": f"/characters/cn/isillien/{name}",
                },
                "runs": [{"keystoneRunId": run_id, "mythicLevel": 22, "score": 511.2}],
            }

        def fake_web_api_get(path, params=None):
            self.assertEqual(path, "/mythic-plus/rankings/specs")
            spec_ranking_calls.append((params["spec"], params["page"]))
            if params["page"] == 0:
                return {"rankings": {"rankedCharacters": [ranking_character("FireOne", 7001)]}}
            if params["page"] == 1:
                return {"rankings": {"rankedCharacters": [ranking_character("FireTwo", 7101)]}}
            return {"rankings": {"rankedCharacters": []}}

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return {"leaderboard_url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards", "rankings": []}
            if path == "/mythic-plus/run-details":
                hero_id = 39 if params["id"] == 7001 else 40
                name = "FireOne" if params["id"] == 7001 else "FireTwo"
                return {
                    "keystone_run_id": params["id"],
                    "roster": [
                        {
                            "character": {
                                "name": name,
                                "realm": {"name": "Isillien", "slug": "isillien"},
                                "region": {"slug": "cn"},
                                "class": {"name": "Mage", "slug": "mage"},
                                "spec": {"id": 63, "name": "Fire", "slug": "fire"},
                                "talentLoadout": {
                                    "specId": 63,
                                    "heroSubTreeId": hero_id,
                                    "loadout": [{"traitId": 91000 + hero_id, "rank": 1}],
                                },
                            }
                        }
                    ],
                }
            if path == "/characters/profile":
                return sample_profile_payload(params["name"], "mage", "fire")
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "expected_spec_pairs",
            return_value=["mage:fire"],
        ), patch.object(raiderio_payload, "api_get", fake_api_get), patch.object(
            raiderio_payload,
            "web_api_get",
            fake_web_api_get,
            create=True,
        ):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(spec_ranking_calls, [("fire", 0), ("fire", 1)])
        self.assertEqual(payload["specRankingCoverage"]["gapFill"]["attemptedSpecCount"], 1)
        self.assertEqual(payload["specRankingCoverage"]["gapFill"]["startPage"], 1)
        self.assertEqual(payload["runDetailCoverage"]["requestedRunCount"], 2)
        self.assertEqual(payload["runDetailCoverage"]["gapFill"]["requestedRunCount"], 1)
        self.assertEqual(
            payload["specRankingCoverage"]["heroSubTreeCoverage"]["mage:fire"]["heroSubTreeIds"],
            ["39", "40"],
        )

    def test_sync_raiderio_cache_gap_fill_extra_window_keeps_existing_window(self):
        os.environ["WOW_RAIDERIO_RUN_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_ENABLED"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_REGIONS"] = "world"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_PAGE_SIZE"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_RUNS_PER_CHARACTER"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_ENABLED"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_PAGES"] = "1"
        os.environ["WOW_RAIDERIO_SPEC_RANKING_GAP_FILL_EXTRA_START_PAGES"] = "3"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT"] = "10"
        os.environ["WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC"] = "10"
        os.environ["WOW_RAIDERIO_PROFILE_LIMIT"] = "3"
        spec_ranking_calls = []

        def ranking_character(name, run_id):
            return {
                "rank": run_id,
                "score": 3999.5,
                "character": {
                    "name": name,
                    "realm": {"name": "Isillien", "slug": "isillien"},
                    "region": {"slug": "cn"},
                    "class": {"name": "Mage", "slug": "mage"},
                    "spec": {"id": 63, "name": "Fire", "slug": "fire"},
                    "path": f"/characters/cn/isillien/{name}",
                },
                "runs": [{"keystoneRunId": run_id, "mythicLevel": 22, "score": 511.2}],
            }

        def fake_web_api_get(path, params=None):
            self.assertEqual(path, "/mythic-plus/rankings/specs")
            spec_ranking_calls.append((params["spec"], params["page"]))
            if params["page"] == 0:
                return {"rankings": {"rankedCharacters": [ranking_character("FireOne", 7001)]}}
            if params["page"] == 1:
                return {"rankings": {"rankedCharacters": [ranking_character("FireTwo", 7101)]}}
            if params["page"] == 3:
                return {"rankings": {"rankedCharacters": [ranking_character("FireThree", 7301)]}}
            return {"rankings": {"rankedCharacters": []}}

        def fake_api_get(path, params=None, api_key=None):
            if path == "/mythic-plus/runs":
                return {"leaderboard_url": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards", "rankings": []}
            if path == "/mythic-plus/run-details":
                hero_id = 40 if params["id"] == 7301 else 39
                name = {7001: "FireOne", 7101: "FireTwo", 7301: "FireThree"}[params["id"]]
                return {
                    "keystone_run_id": params["id"],
                    "roster": [
                        {
                            "character": {
                                "name": name,
                                "realm": {"name": "Isillien", "slug": "isillien"},
                                "region": {"slug": "cn"},
                                "class": {"name": "Mage", "slug": "mage"},
                                "spec": {"id": 63, "name": "Fire", "slug": "fire"},
                                "talentLoadout": {
                                    "specId": 63,
                                    "heroSubTreeId": hero_id,
                                    "loadout": [{"traitId": 91000 + hero_id, "rank": 1}],
                                },
                            }
                        }
                    ],
                }
            if path == "/characters/profile":
                return sample_profile_payload(params["name"], "mage", "fire")
            if path == "/mythic-plus/static-data":
                return {"dungeons": [{"name": "Nexus-Point Xenas", "slug": "nexus-point-xenas"}]}
            if path == "/mythic-plus/affixes":
                return {"affix_details": [{"name": "Fortified"}]}
            if path == "/mythic-plus/season-cutoffs":
                return {"cutoffs": {"all": {"p999": {"allMinValue": 4127.57}}}}
            raise AssertionError(path)

        with closing(self.connection()) as conn, patch.object(
            raiderio_payload,
            "expected_spec_pairs",
            return_value=["mage:fire"],
        ), patch.object(raiderio_payload, "api_get", fake_api_get), patch.object(
            raiderio_payload,
            "web_api_get",
            fake_web_api_get,
            create=True,
        ):
            payload = raiderio_payload.sync_raiderio_cache(conn)

        self.assertEqual(spec_ranking_calls, [("fire", 0), ("fire", 1), ("fire", 3)])
        self.assertEqual(payload["specRankingCoverage"]["gapFill"]["startPage"], 1)
        self.assertEqual(payload["specRankingCoverage"]["extraGapFill"][0]["startPage"], 3)
        self.assertEqual(payload["runDetailCoverage"]["gapFill"]["requestedRunCount"], 1)
        self.assertEqual(payload["runDetailCoverage"]["extraGapFill"][0]["requestedRunCount"], 1)
        self.assertEqual(
            payload["specRankingCoverage"]["heroSubTreeCoverage"]["mage:fire"]["heroSubTreeIds"],
            ["39", "40"],
        )

    def test_build_community_templates_keeps_structured_run_detail_without_raw_import_code(self):
        templates = raiderio_payload.build_community_templates(
            [
                {
                    "classKey": "mage",
                    "specKey": "fire",
                    "fullName": "Fire Mage",
                    "sampleCount": 1,
                    "maxKeyLevel": 22,
                    "talentLoadouts": [
                        {
                            "loadoutSpecId": 63,
                            "heroSubTreeId": 39,
                            "loadout": [{"traitId": 91001, "rank": 1}],
                            "source": "run_detail",
                            "characterName": "Specfire",
                            "realmSlug": "isillien",
                            "region": "cn",
                            "profileUrl": "https://raider.io/characters/cn/isillien/Specfire",
                            "maxKeyLevel": 22,
                        }
                    ],
                }
            ],
            "2026-07-04T00:00:00+00:00",
        )

        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["rawImportCode"], "")
        self.assertEqual(template["payload"]["raiderio"]["source"], "run_detail")
        self.assertEqual(template["payload"]["raiderio"]["loadout"][0]["traitId"], 91001)

    def test_spec_ranking_import_code_becomes_structured_loadout_for_hero_discovery(self):
        trait_path = Path(self.tmp.name) / "trait_data.inc"
        write_minimal_dk_trait_data(trait_path)
        os.environ["WOW_SIMC_TRAIT_DATA_FILE"] = str(trait_path)
        websim_payload._TALENT_IMPORT_DECODER_CACHE = None
        self.addCleanup(setattr, websim_payload, "_TALENT_IMPORT_DECODER_CACHE", None)
        sanlayn_code = blizzard_import_code(
            252,
            [
                (True, 1, 0),
                (True, 1, 0),
                (True, 1, 1),
            ],
        )
        ranked_character = {
            "rank": 611,
            "score": 3612.5,
            "character": {
                "name": "Sanrio",
                "realm": {"name": "Isillien", "slug": "isillien"},
                "region": {"slug": "cn"},
                "talentLoadoutText": sanlayn_code,
            },
        }
        run = raiderio_payload.simplify_spec_ranking_run(
            ranked_character,
            {"keystoneRunId": 4242, "zoneName": "Nexus-Point Xenas", "mythicLevel": 18},
            "deathknight",
            "unholy",
            "cn",
            "https://raider.io/mythic-plus-spec-rankings/season-mn-1/cn/death-knight/unholy",
        )

        aggregate = raiderio_payload.aggregate_runs([run], {})[0]
        loadout = aggregate["talentLoadouts"][0]
        templates = raiderio_payload.build_community_templates([aggregate], "2026-07-04T00:00:00+00:00")

        self.assertEqual(loadout["source"], "spec_ranking_import_code")
        self.assertEqual(loadout["loadoutSpecId"], 252)
        self.assertEqual(loadout["heroKey"], "sanlayn")
        self.assertEqual([entry["entryId"] for entry in loadout["loadout"]], [5001, 5002, 123321])
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["heroKey"], "sanlayn")
        self.assertEqual(templates[0]["payload"]["raiderio"]["loadout"][1]["traitId"], 5002)
        self.assertEqual(templates[0]["payload"]["raiderio"]["source"], "spec_ranking_import_code")

    def test_aggregate_runs_keeps_configured_loadout_budget_for_hero_discovery(self):
        os.environ["WOW_RAIDERIO_TALENT_LOADOUT_LIMIT_PER_SPEC"] = "7"
        runs = []
        for index in range(1, 8):
            runs.append(
                {
                    "mythicLevel": 20 + index,
                    "score": 4000 + index,
                    "roster": [
                        {
                            "name": f"Mage{index}",
                            "realmSlug": "isillien",
                            "region": "cn",
                            "classKey": "mage",
                            "className": "Mage",
                            "specKey": "fire",
                            "specName": "Fire",
                            "talentLoadout": {
                                "rawImportCode": f"CODE-{index}",
                                "loadoutSpecId": 63,
                                "loadout": [{"traitId": 91000 + index, "rank": 1}],
                                "source": "run_detail",
                            },
                        }
                    ],
                }
            )

        aggregates = raiderio_payload.aggregate_runs(runs, {})

        self.assertEqual(len(aggregates[0]["talentLoadouts"]), 7)
        self.assertEqual(aggregates[0]["talentLoadouts"][-1]["characterName"], "Mage7")

    def test_aggregate_runs_keeps_later_hero_subtree_loadout_within_budget(self):
        os.environ["WOW_RAIDERIO_TALENT_LOADOUT_LIMIT_PER_SPEC"] = "3"
        runs = []
        for index, hero_subtree_id in enumerate([39, 39, 39, 40], start=1):
            runs.append(
                {
                    "mythicLevel": 25 - index,
                    "score": 5000 - index,
                    "roster": [
                        {
                            "name": f"Mage{index}",
                            "realmSlug": "isillien",
                            "region": "cn",
                            "classKey": "mage",
                            "className": "Mage",
                            "specKey": "fire",
                            "specName": "Fire",
                            "talentLoadout": {
                                "loadoutSpecId": 63,
                                "heroSubTreeId": hero_subtree_id,
                                "loadout": [{"traitId": 91000 + index, "rank": 1}],
                                "source": "run_detail",
                            },
                        }
                    ],
                }
            )

        aggregates = raiderio_payload.aggregate_runs(runs, {})

        self.assertEqual(len(aggregates[0]["talentLoadouts"]), 3)
        self.assertEqual(
            [loadout.get("heroSubTreeId") for loadout in aggregates[0]["talentLoadouts"]],
            [39, 39, 40],
        )

    def test_aggregate_runs_dedupes_run_detail_by_structured_loadout_before_raw_code(self):
        os.environ["WOW_RAIDERIO_TALENT_LOADOUT_LIMIT_PER_SPEC"] = "4"
        runs = []
        for index, hero_subtree_id in enumerate([36, 38], start=1):
            runs.append(
                {
                    "mythicLevel": 24 - index,
                    "score": 4300 - index,
                    "roster": [
                        {
                            "name": "Iwamihina",
                            "realmSlug": "shadowmoon",
                            "region": "tw",
                            "classKey": "evoker",
                            "className": "Evoker",
                            "specKey": "augmentation",
                            "specName": "Augmentation",
                            "talentLoadout": {
                                "rawImportCode": "CEcBAAAAAAAAAAAAAAAA",
                                "loadoutSpecId": 1473,
                                "heroSubTreeId": hero_subtree_id,
                                "loadout": [
                                    {
                                        "traitId": 117500 + hero_subtree_id,
                                        "rank": 1,
                                        "node": {"subTreeId": hero_subtree_id},
                                    }
                                ],
                                "source": "run_detail",
                            },
                        }
                    ],
                }
            )

        aggregates = raiderio_payload.aggregate_runs(runs, {})

        self.assertEqual(
            [loadout.get("heroSubTreeId") for loadout in aggregates[0]["talentLoadouts"]],
            [36, 38],
        )

    def test_build_community_templates_uses_structured_run_detail_for_distinct_ids(self):
        aggregate = {
            "classKey": "evoker",
            "specKey": "augmentation",
            "fullName": "Augmentation Evoker",
            "sampleCount": 2,
            "maxKeyLevel": 24,
            "talentLoadouts": [
                {
                    "characterName": "Iwamihina",
                    "realmSlug": "shadowmoon",
                    "region": "tw",
                    "profileUrl": "https://raider.io/characters/tw/shadowmoon/Iwamihina",
                    "rawImportCode": "CEcBAAAAAAAAAAAAAAAA",
                    "loadoutSpecId": 1473,
                    "heroSubTreeId": 36,
                    "source": "run_detail",
                    "loadout": [{"traitId": 117536, "rank": 1, "node": {"subTreeId": 36}}],
                },
                {
                    "characterName": "Iwamihina",
                    "realmSlug": "shadowmoon",
                    "region": "tw",
                    "profileUrl": "https://raider.io/characters/tw/shadowmoon/Iwamihina",
                    "rawImportCode": "CEcBAAAAAAAAAAAAAAAA",
                    "loadoutSpecId": 1473,
                    "heroSubTreeId": 38,
                    "source": "run_detail",
                    "loadout": [{"traitId": 117538, "rank": 1, "node": {"subTreeId": 38}}],
                },
            ],
        }

        templates = raiderio_payload.build_community_templates([aggregate], "2026-07-04T00:00:00Z")

        self.assertEqual(len(templates), 2)
        self.assertEqual(len({template["id"] for template in templates}), 2)
        self.assertEqual(
            [template["payload"]["raiderio"]["heroSubTreeId"] for template in templates],
            [36, 38],
        )

    def test_aggregate_runs_keeps_structured_run_detail_without_raw_import_code(self):
        runs = [
            {
                "mythicLevel": 22,
                "score": 3999.5,
                "roster": [
                    {
                        "name": "Specfire",
                        "realmSlug": "isillien",
                        "region": "cn",
                        "classKey": "mage",
                        "className": "Mage",
                        "specKey": "fire",
                        "specName": "Fire",
                        "talentLoadout": {
                            "loadoutSpecId": 63,
                            "heroSubTreeId": 39,
                            "loadout": [{"traitId": 91001, "rank": 1}],
                            "source": "run_detail",
                        },
                    }
                ],
            }
        ]

        aggregates = raiderio_payload.aggregate_runs(runs, {})

        self.assertEqual(len(aggregates[0]["talentLoadouts"]), 1)
        self.assertEqual(aggregates[0]["talentLoadouts"][0]["source"], "run_detail")
        self.assertEqual(aggregates[0]["talentLoadouts"][0]["loadout"][0]["traitId"], 91001)

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

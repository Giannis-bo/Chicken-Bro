import os
import json
import threading
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from server.app.chickenbro.raiderio_research import RaiderIOResearch
from server.app.simulation.sources import InvalidSourceLink, SourceHttpError


def _ranking(rank, name, *, class_slug="shaman", spec_slug="enhancement"):
    return {
        "rank": rank,
        "score": 4000 - rank,
        "character": {
            "name": name,
            "path": f"/characters/us/area-52/{name}",
            "region": {"slug": "us"},
            "realm": {"slug": "area-52"},
            "class": {"slug": class_slug},
            "spec": {"slug": spec_slug, "id": 263},
            "level": 90,
        },
    }


def _profile(name="Giannis", *, realm="silver-hand", region="cn"):
    return {
        "name": name,
        "realm": realm,
        "region": region,
        "class": "Shaman",
        "active_spec_name": "Enhancement",
        "level": 90,
        "profile_url": f"https://raider.io/characters/{region}/{realm}/{name}",
        "last_crawled_at": "2026-09-06T01:02:03Z",
        "gear": {
            "item_level_equipped": 712.5,
            "items": {
                "head": {
                    "id": 123,
                    "name": "Storm Helm",
                    "item_level": 710,
                    "tier": "T36",
                    "tier36": True,
                    "gems_detail": [{"item_id": 456, "name": "Masterful Ruby", "icon": "ruby"}],
                    "enchants_detail": [{"enchant_id": 789, "name": "Whisper of Mastery"}],
                    "bonuses": [10355, 10876],
                    "unsafe": "discard-me",
                }
            },
        },
        "talents": {
            "loadout": {
                "talent_points": [
                    {"selected": True, "rank": 2, "spell": {"id": 1001, "name": "Storm Talent"}},
                    {"selected": False, "rank": 1, "spell": {"id": 1002, "name": "Not Selected"}},
                    {"rank": 1, "talent": {"spell": {"id": 1003, "name": "Implicit Selected"}}},
                ],
                "hero_talent_points": [
                    {"selected": True, "rank": 1, "spell": {"id": 2001, "name": "Tempest"}},
                    {"selected": True, "rank": 1, "spell": None, "name": "Stormbringer"},
                    {"rank": 1, "spell": None, "talent": {"name": "Surging Currents"}},
                ],
            }
        },
        "mythic_plus_scores_by_season": [{"season": "season-mn-2", "scores": {"all": 3456.7}}],
        "secret": "discard-me",
    }


def _real_talent_loadout():
    return {
        "loadout_spec_id": 263,
        "loadout_text": "CYQAAAAAAAAAAAAAAAAAAAAA",
        "loadout": [
            {"node": {"entries": [
                {"spell": {"id": 3001, "name": "Unselected Choice"}},
                {"spell": {"id": 3002, "name": "Selected Choice"}},
            ]}, "entryIndex": 1, "rank": 2},
            {"node": {"entries": [
                {"spell": None, "traitSubTreeId": 77},
                {"spell": {"id": 3003, "name": "Hero Strike"}, "traitSubTreeId": 77},
            ]}, "entryIndex": 1, "rank": 1},
            {"node": {"entries": [{"spell": None, "traitSubTreeId": 88}]},
             "entryIndex": 0, "rank": 1},
        ],
    }


class FakeRaiderIO:
    def __init__(self, rankings=None, profiles=None):
        self.calls = []
        self.rankings = rankings or []
        self.profiles = profiles or {}

    def fetch_json(self, url, **_kwargs):
        self.calls.append(url)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/mythic-plus/affixes"):
            return {"leaderboard_url": "https://raider.io/mythic-plus-affix-rankings/season-mn-2/all/us/leaderboards-strict/xalataths-bargain-devour-fortified-tyrannical-xalataths-guile"}
        if parsed.path.endswith("/rankings/specs"):
            return {"rankings": {"rankedCharacters": self.rankings}}
        key = (query["region"][0], query["realm"][0], query["name"][0])
        value = self.profiles.get(key)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise SourceHttpError(404)
        return value


class RaiderIOResearchTest(unittest.TestCase):
    def test_empty_projection_reports_no_sample_or_continuation(self):
        wrong = _ranking(1, "Wrong")
        wrong["character"]["spec"]["slug"] = "elemental"
        for rows, offset, expected in (([wrong], 0, "not_found"),
                                      ([_ranking(1, "Valid")], 5, "not_found"),
                                      ([wrong, _ranking(2, "Valid")], 0, "partial")):
            with self.subTest(expected=expected, offset=offset):
                result = RaiderIOResearch(FakeRaiderIO(rankings=rows)).rankings({
                    "className": "shaman", "spec": "enhancement", "limit": 1, "offset": offset})
                self.assertEqual(expected, result["status"])
                self.assertEqual([], result["facts"])
                self.assertEqual(expected == "partial", bool(result["nextActions"]))

    def test_current_season_discovery_respects_requested_region(self):
        client = FakeRaiderIO()
        RaiderIOResearch(client).rankings({"className": "shaman", "spec": "enhancement", "region": "cn"})
        self.assertEqual(["cn"], parse_qs(urlparse(client.calls[0]).query)["region"])

    def test_rankings_discovers_current_season_and_returns_cursor_with_bounded_projection(self):
        upstream = [_ranking(index, f"Player{index}") for index in range(1, 101)]
        client = FakeRaiderIO(rankings=upstream)

        result = RaiderIOResearch(client).rankings({
            "className": "shaman", "spec": "enhancement", "offset": 95, "limit": 5
        })

        self.assertEqual("source_reference", result["status"])
        self.assertEqual([96, 97, 98, 99, 100], [row["rank"] for row in result["facts"]])
        self.assertEqual(
            {"page": 0, "offset": 95, "limit": 5, "returned": 5, "upstreamCount": 100,
             "nextPage": 1, "nextOffset": 0},
            result["pagination"],
        )
        ranking_query = parse_qs(urlparse(client.calls[1]).query)
        self.assertEqual(["season-mn-2"], ranking_query["season"])
        self.assertEqual(["world"], ranking_query["region"])
        self.assertEqual(
            "https://raider.io/characters/us/area-52/Player96",
            result["facts"][0]["character"]["url"],
        )
        self.assertNotIn("access_key", str(result))

    def test_ranking_canonical_url_can_be_passed_directly_to_character_batch(self):
        profile = _profile("Enh", realm="area-52", region="us")
        client = FakeRaiderIO(
            rankings=[_ranking(1, "Enh")], profiles={("us", "area-52", "Enh"): profile}
        )
        ranking = RaiderIOResearch(client).rankings(
            {"className": "shaman", "spec": "enhancement", "season": "season-mn-2"}
        )
        result = RaiderIOResearch(client).characters(
            [ranking["facts"][0]["character"]["url"]]
        )
        self.assertEqual(1, result["counts"]["succeeded"])
        self.assertEqual("Enh", result["facts"][0]["character"]["name"])

    def test_rankings_historical_short_page_has_no_next_cursor(self):
        result = RaiderIOResearch(FakeRaiderIO(rankings=[_ranking(1, "One")])).rankings({
            "className": "shaman", "spec": "enhancement", "season": "season-tww-3",
            "page": 2, "offset": 0, "limit": 10,
        })
        self.assertEqual(1, result["pagination"]["returned"])
        self.assertIsNone(result["pagination"]["nextPage"])
        self.assertIsNone(result["pagination"]["nextOffset"])

    def test_rankings_traverses_every_slice_of_a_short_final_upstream_page(self):
        rows = [_ranking(index, f"P{index}") for index in range(1, 26)]
        research = RaiderIOResearch(FakeRaiderIO(rankings=rows))
        first = research.rankings({
            "className": "shaman", "spec": "enhancement", "season": "season-mn-2", "limit": 10
        })
        last = research.rankings({
            "className": "shaman", "spec": "enhancement", "season": "season-mn-2",
            "offset": 20, "limit": 10,
        })
        self.assertEqual((0, 10), (first["pagination"]["nextPage"], first["pagination"]["nextOffset"]))
        self.assertEqual(5, last["pagination"]["returned"])
        self.assertIsNone(last["pagination"]["nextPage"])
        self.assertIsNone(last["pagination"]["nextOffset"])

    def test_rankings_does_not_label_empty_upstream_data_as_a_source_reference(self):
        result = RaiderIOResearch(FakeRaiderIO(rankings=[])).rankings({
            "className": "shaman", "spec": "enhancement", "season": "season-mn-2"
        })
        self.assertEqual("not_found", result["status"])
        self.assertEqual([], result["facts"])
        self.assertTrue(result["limitations"])

    def test_untrusted_non_finite_numbers_do_not_escape_into_json_packet(self):
        row = _ranking(1, "Enh")
        row["score"] = float("nan")
        profile = _profile()
        profile["gear"]["item_level_equipped"] = float("inf")
        profile["gear"]["items"]["head"]["id"] = float("inf")
        profile["mythic_plus_scores_by_season"][0]["scores"]["all"] = float("nan")
        client = FakeRaiderIO(
            rankings=[row], profiles={("cn", "silver-hand", "Giannis"): profile}
        )
        ranking_packet = RaiderIOResearch(client).rankings(
            {"className": "shaman", "spec": "enhancement", "season": "season-mn-2"}
        )
        character_packet = RaiderIOResearch(client).character(
            "https://raider.io/characters/cn/silver-hand/Giannis"
        )
        json.dumps(ranking_packet, allow_nan=False)
        json.dumps(character_packet, allow_nan=False)

    def test_rankings_rejects_unknown_options_wrong_types_and_mismatched_class_spec(self):
        invalid = [
            {"className": "shaman", "spec": "enhancement", "extra": 1},
            {"className": "shaman", "spec": "enhancement", "page": True},
            {"className": "mage", "spec": "enhancement"},
            {"className": "shaman", "spec": "enhancement", "offset": 100},
            {"className": "shaman", "spec": "enhancement", "limit": 11},
        ]
        for options in invalid:
            with self.subTest(options=options), self.assertRaises(InvalidSourceLink):
                RaiderIOResearch(FakeRaiderIO()).rankings(options)

    def test_rankings_treats_untrusted_season_url_and_wrong_spec_rows_as_unusable(self):
        class BadSeason(FakeRaiderIO):
            def fetch_json(self, url, **kwargs):
                if urlparse(url).path.endswith("/mythic-plus/affixes"):
                    return {"leaderboard_url": "https://127.0.0.1/mythic-plus-rankings/season-mn-2/all"}
                return super().fetch_json(url, **kwargs)

        blocked = RaiderIOResearch(BadSeason()).rankings(
            {"className": "shaman", "spec": "enhancement"}
        )
        self.assertEqual("blocked", blocked["status"])
        self.assertEqual([], blocked["facts"])

        mixed = RaiderIOResearch(
            FakeRaiderIO(rankings=[_ranking(1, "Enh"), _ranking(2, "Elemental", spec_slug="elemental")])
        ).rankings({"className": "shaman", "spec": "enhancement", "season": "season-mn-2"})
        self.assertEqual(["Enh"], [row["character"]["name"] for row in mixed["facts"]])
        self.assertIn("Discarded 1", mixed["limitations"][0])

    def test_character_uses_fixed_api_and_preserves_safe_analysis_fields(self):
        client = FakeRaiderIO(profiles={("cn", "silver-hand", "Giannis"): _profile()})
        with patch.dict(os.environ, {"WOW_RAIDERIO_API_KEY": "server-only-key"}, clear=False):
            result = RaiderIOResearch(client).character(
                "https://raider.io/cn/characters/cn/silver-hand/Giannis"
            )

        self.assertEqual("source_reference", result["status"])
        fact = result["facts"][0]
        self.assertEqual("Giannis", fact["character"]["name"])
        self.assertEqual("Masterful Ruby", fact["gear"]["items"]["head"]["gemsDetail"][0]["name"])
        self.assertEqual("Whisper of Mastery", fact["gear"]["items"]["head"]["enchantsDetail"][0]["name"])
        self.assertEqual("T36", fact["gear"]["items"]["head"]["tier"])
        self.assertIs(True, fact["gear"]["items"]["head"]["tier36"])
        self.assertEqual([10355, 10876], fact["gear"]["items"]["head"]["bonusIds"])
        self.assertEqual(
            [
                {"spellId": 1001, "name": "Storm Talent", "rank": 2},
                {"spellId": 1003, "name": "Implicit Selected", "rank": 1},
            ],
            fact["talents"]["selected"],
        )
        self.assertEqual(
            ["Tempest", "Stormbringer", "Surging Currents"], fact["talents"]["heroNames"]
        )
        self.assertEqual(3456.7, fact["mythicPlusScores"][0]["scores"]["all"])
        self.assertEqual("not_provided", fact["statPercentagesStatus"])
        self.assertNotIn("unsafe", str(result))
        self.assertNotIn("server-only-key", str(result))
        query = parse_qs(urlparse(client.calls[0]).query)
        self.assertEqual(["gear,talents,mythic_plus_scores_by_season:current"], query["fields"])

    def test_character_rejects_malicious_url_and_upstream_identity_mismatch(self):
        research = RaiderIOResearch(FakeRaiderIO(profiles={
            ("cn", "silver-hand", "Giannis"): _profile(name="SomeoneElse")
        }))
        for target in (
            "https://evil.example/characters/cn/silver-hand/Giannis",
            "https://raider.io@evil.example/characters/cn/silver-hand/Giannis",
            "https://raider.io/characters/cn/silver-hand/Giannis?next=https://127.0.0.1",
        ):
            with self.subTest(target=target), self.assertRaises(InvalidSourceLink):
                research.character(target)
        mismatch = research.character("https://raider.io/characters/cn/silver-hand/Giannis")
        self.assertEqual("blocked", mismatch["status"])
        self.assertEqual([], mismatch["facts"])
        self.assertIn("identity", mismatch["limitations"][0].lower())

    def test_character_parses_real_top_level_talent_loadout_by_entry_index(self):
        profile = _profile()
        profile.pop("talents")
        profile["talentLoadout"] = _real_talent_loadout()
        client = FakeRaiderIO(profiles={("cn", "silver-hand", "Giannis"): profile})
        result = RaiderIOResearch(client).character(
            "https://raider.io/characters/cn/silver-hand/Giannis"
        )
        talents = result["facts"][0]["talents"]
        self.assertEqual(263, talents["loadoutSpecId"])
        self.assertEqual("CYQAAAAAAAAAAAAAAAAAAAAA", talents["loadoutText"])
        self.assertEqual(
            [
                {"spellId": 3002, "name": "Selected Choice", "rank": 2},
                {"spellId": 3003, "name": "Hero Strike", "rank": 1},
            ],
            talents["selected"],
        )
        self.assertEqual([], talents["heroNames"])
        self.assertNotIn("Unselected Choice", str(talents))
        self.assertNotIn("88", str(talents))

    def test_characters_deduplicates_and_preserves_partial_results(self):
        targets = [
            "https://raider.io/characters/cn/silver-hand/Giannis",
            "https://raider.io/characters/cn/silver-hand/Giannis",
            "https://raider.io/characters/us/area-52/Missing",
        ]
        client = FakeRaiderIO(profiles={
            ("cn", "silver-hand", "Giannis"): _profile(),
            ("us", "area-52", "Missing"): SourceHttpError(404),
        })
        result = RaiderIOResearch(client).characters(targets)
        self.assertEqual("partial", result["status"])
        self.assertEqual({"requested": 3, "unique": 2, "succeeded": 1, "failed": 1}, result["counts"])
        self.assertEqual("Giannis", result["facts"][0]["character"]["name"])
        self.assertEqual(2, len(result["evidence"]))
        self.assertNotIn("all profiles", " ".join(result["limitations"]).lower())

    def test_characters_caps_batch_and_concurrency_at_three(self):
        lock = threading.Lock()
        state = {"active": 0, "peak": 0}

        class SlowClient(FakeRaiderIO):
            def fetch_json(self, url, **kwargs):
                with lock:
                    state["active"] += 1
                    state["peak"] = max(state["peak"], state["active"])
                time.sleep(0.02)
                try:
                    return super().fetch_json(url, **kwargs)
                finally:
                    with lock:
                        state["active"] -= 1

        targets = [f"https://raider.io/characters/us/area-52/P{i}" for i in range(6)]
        profiles = {("us", "area-52", f"P{i}"): _profile(f"P{i}", realm="area-52", region="us") for i in range(6)}
        result = RaiderIOResearch(SlowClient(profiles=profiles)).characters(targets)
        self.assertEqual(6, result["counts"]["succeeded"])
        self.assertLessEqual(state["peak"], 3)
        with self.assertRaises(InvalidSourceLink):
            RaiderIOResearch(FakeRaiderIO()).characters([])
        with self.assertRaises(InvalidSourceLink):
            RaiderIOResearch(FakeRaiderIO()).characters(targets + targets[:5])


if __name__ == "__main__":
    unittest.main()

class RealmIdentityRegressionTest(unittest.TestCase):
    def test_display_name_slug_and_verified_chinese_alias(self):
        profile=_profile('Fusionbolt',realm="Al'ar")
        profile['profile_url']='https://raider.io/characters/cn/alar/Fusionbolt'
        client=FakeRaiderIO(profiles={('cn',r,'Fusionbolt'):profile for r in ['alar','凤凰之神']})
        resolver=lambda region, realm: {'id':584,'slug':'alar','region':{'slug':'CN'}}
        research=RaiderIOResearch(client,realm_resolver=resolver)
        for realm in ['alar','凤凰之神']:
            self.assertEqual(research.character(f'https://raider.io/characters/cn/{realm}/Fusionbolt')['status'],'source_reference')

    def test_alias_resolution_keeps_other_realm_region_name_and_url_rejected(self):
        for field,value in [('name','Other'),('region','us'),('profile_url','https://raider.io/characters/cn/argus/Fusionbolt'),('profile_url','https://evil.test/characters/cn/alar/Fusionbolt')]:
            profile=_profile('Fusionbolt',realm="Al'ar")
            profile['profile_url']='https://raider.io/characters/cn/alar/Fusionbolt'
            profile[field]=value
            client=FakeRaiderIO(profiles={('cn','凤凰之神','Fusionbolt'):profile})
            research=RaiderIOResearch(client,realm_resolver=lambda *_:{'id':584,'slug':'alar','region':{'slug':'CN'}})
            with self.subTest(field=field,value=value):
                self.assertEqual(research.character('https://raider.io/characters/cn/凤凰之神/Fusionbolt')['status'],'blocked')

    def test_alias_service_failure_is_not_a_false_identity_mismatch(self):
        profile=_profile('Fusionbolt',realm="Al'ar")
        profile['profile_url']='https://raider.io/characters/cn/alar/Fusionbolt'
        def unavailable(*_): raise RuntimeError('credential details must not escape')
        research=RaiderIOResearch(FakeRaiderIO(profiles={('cn','凤凰之神','Fusionbolt'):profile}),realm_resolver=unavailable)
        result=research.character('https://raider.io/characters/cn/凤凰之神/Fusionbolt')
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['facts'],[])
        self.assertNotIn('credential',str(result))

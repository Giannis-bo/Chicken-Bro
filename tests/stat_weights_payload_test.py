import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from server import stat_weights_payload


CORE_SLOTS = [
    "head",
    "neck",
    "shoulder",
    "back",
    "chest",
    "wrist",
    "hands",
    "waist",
    "legs",
    "feet",
    "finger1",
    "finger2",
    "trinket1",
    "trinket2",
    "main_hand",
]


def full_gear_items(offset=0):
    return [
        {
            "slot": slot,
            "itemId": str(250000 + offset + index),
            "name": f"{slot} Test Item",
            "ilevel": "707",
            "bonus_id": "1808",
            "sourceType": "manual",
        }
        for index, slot in enumerate(CORE_SLOTS)
    ]


def fake_raiderio_payload(sample_count=5, profile_count=2):
    profiles = []
    for index in range(profile_count):
        profiles.append(
            {
                "name": f"Rio{index}",
                "profileUrl": f"https://raider.io/characters/cn/isillien/Rio{index}",
                "classKey": "mage",
                "specKey": "frost",
                "itemLevel": 707 + index,
                "talentLoadout": {"rawImportCode": f"CAE_FAKE_LOADOUT_{index}"},
                "gear": full_gear_items(index * 100),
            }
        )
    return {
        "sourceName": "Raider.IO",
        "sourceStatus": "synced",
        "region": "cn",
        "seasonSlug": "season-mn-1",
        "leaderboardUrl": "https://raider.io/mythic-plus-rankings/season-mn-1/all/cn/leaderboards",
        "checkedAt": "2026-06-18T00:00:00+00:00",
        "profiles": profiles,
        "specAggregates": [
            {
                "classKey": "mage",
                "specKey": "frost",
                "className": "Mage",
                "specName": "Frost",
                "sampleCount": sample_count,
                "characterCount": sample_count,
                "maxKeyLevel": 24,
                "bestScore": 4127.57,
                "talentLoadouts": [
                    {
                        "rawImportCode": "CAE_FAKE_LOADOUT_0",
                        "characterName": "Rio0",
                        "profileUrl": "https://raider.io/characters/cn/isillien/Rio0",
                    }
                ],
                "observedGear": full_gear_items(300),
            }
        ],
    }


def fake_scale_factor_output():
    return """
DPS Ranking:
  mage_frost 100000

Scale Factors:
  Int=2.40
  Crit=1.10
  Haste=1.30
  Mastery=0.90
  Vers=0.70

Scale Deltas:
  Crit 500
"""


def fake_translation_response():
    return {
        "content": json.dumps(
            {
                "summaryZh": "该场景展示样本角色的属性参考方向。",
                "recommendationsZh": ["结合当前构筑和钥石节奏复核。"],
                "warningsZh": ["这不是个人最终配装结论。"],
            },
            ensure_ascii=False,
        )
    }


class StatWeightsPayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "stat_weights.sqlite3"
        self.old_env = dict(os.environ)
        os.environ["WOW_NEWS_DB"] = str(self.db_path)
        os.environ["WOW_STAT_WEIGHTS_VERIFIED_MIN_SAMPLES"] = "3"
        os.environ["WOW_STAT_WEIGHTS_VERIFIED_MIN_PROFILES"] = "2"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    def connection(self):
        return sqlite3.connect(self.db_path)

    def test_sync_cache_writes_verified_scenario_weights_and_enriches_detail(self):
        def fake_registry():
            return [
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "specId": "mage-frost",
                    "className": "法师",
                    "specName": "冰霜",
                    "role": "dps",
                    "primaryStat": "intellect",
                }
            ]

        with closing(self.connection()) as conn, patch.object(stat_weights_payload, "specialization_registry", fake_registry), patch.object(
            stat_weights_payload,
            "run_stat_weight_simcraft",
            return_value={"ran": True, "available": True, "rawOutput": fake_scale_factor_output(), "error": ""},
        ), patch.object(stat_weights_payload, "call_chat_completion", return_value=fake_translation_response()):
            run = stat_weights_payload.sync_stat_weight_cache(conn, fake_raiderio_payload(), refresh_mode="test")
            conn.commit()

            self.assertEqual(run["sourceStatus"], "verified")
            self.assertEqual(run["acceptedCount"], 3)
            self.assertEqual(run["blockedCount"], 0)

            detail = {
                "websimClassKey": "mage",
                "websimSpecKey": "frost",
                "details": {
                    "statWeights": {
                        "stats": [{"key": "legacy", "name": "Legacy", "value": "1", "percent": 1}],
                    }
                },
            }
            enriched = stat_weights_payload.enrich_builds_detail_stat_weights(conn, detail)
            stat_weights = enriched["details"]["statWeights"]

            self.assertEqual(stat_weights["sourceStatus"], "verified")
            self.assertEqual(stat_weights["defaultScenarioKey"], "mplus_mixed_route")
            self.assertEqual(len(stat_weights["scenarioWeights"]), 3)
            self.assertEqual(stat_weights["validation"]["sampleCount"], 5)
            self.assertEqual(stat_weights["validation"]["simcSuccessCount"], 2)
            self.assertEqual(stat_weights["stats"][0]["name"], "智力")
            self.assertEqual(stat_weights["stats"][0]["kind"], "primary")
            self.assertEqual(stat_weights["stats"][1]["key"], "haste")
            self.assertEqual(stat_weights["stats"][1]["percent"], 100)
            self.assertEqual(stat_weights["recommendationsZh"], ["结合当前构筑和钥石节奏复核。"])

            latest = stat_weights_payload.latest_stat_weight_run_payload(conn)
            self.assertEqual(latest["status"], "verified")
            self.assertEqual(latest["refreshMode"], "test")

    def test_low_sample_success_is_partial_with_blocker(self):
        with closing(self.connection()) as conn, patch.object(
            stat_weights_payload,
            "specialization_registry",
            return_value=[
                {
                    "classKey": "mage",
                    "specKey": "frost",
                    "specId": "mage-frost",
                    "className": "法师",
                    "specName": "冰霜",
                    "role": "dps",
                    "primaryStat": "intellect",
                }
            ],
        ), patch.object(
            stat_weights_payload,
            "run_stat_weight_simcraft",
            return_value={"ran": True, "available": True, "rawOutput": fake_scale_factor_output(), "error": ""},
        ), patch.object(stat_weights_payload, "call_chat_completion", return_value=fake_translation_response()):
            stat_weights_payload.sync_stat_weight_cache(conn, fake_raiderio_payload(sample_count=1), refresh_mode="test")
            conn.commit()

            cached = stat_weights_payload.read_cached_stat_weight(conn, "mage", "frost", "mplus_mixed_route")

        self.assertEqual(cached["sourceStatus"], "partial")
        self.assertTrue(any("below verified threshold" in item for item in cached["blockers"]))

    def test_build_scenario_payload_with_previous_reuses_pg_cached_translation(self):
        spec_meta = {
            "classKey": "mage",
            "specKey": "frost",
            "specId": "mage-frost",
            "className": "法师",
            "specName": "冰霜",
            "role": "dps",
            "primaryStat": "intellect",
        }
        scenario = next(item for item in stat_weights_payload.MPLUS_SCENARIOS if item["key"] == "mplus_mixed_route")
        previous = {
            "translationStatus": "llm",
            "summaryZh": "复用的中文摘要。",
            "recommendationsZh": ["复用上一轮翻译。"],
            "warningsZh": ["上一轮边界。"],
            "expiresAt": "2099-01-01T00:00:00+00:00",
        }
        ready_profiles = [
            {"name": "Rio0", "importCode": "CAE_FAKE_LOADOUT_0", "gearItems": full_gear_items(0)},
            {"name": "Rio1", "importCode": "CAE_FAKE_LOADOUT_1", "gearItems": full_gear_items(100)},
        ]

        with patch.object(
            stat_weights_payload,
            "run_stat_weight_simcraft",
            return_value={"ran": True, "available": True, "rawOutput": fake_scale_factor_output(), "error": ""},
        ), patch.object(
            stat_weights_payload,
            "call_chat_completion",
            return_value={"error": "llm unavailable", "content": ""},
        ), patch.object(
            stat_weights_payload,
            "read_cached_stat_weight",
            side_effect=AssertionError("PG-native helper must not read SQLite cache"),
        ):
            payload = stat_weights_payload.build_scenario_payload_with_previous(
                spec_meta,
                scenario,
                {"sourceStatus": "synced", "checkedAt": "2026-07-03T00:00:00+00:00"},
                {"sampleCount": 5},
                ready_profiles,
                [],
                previous=previous,
            )

        self.assertEqual(payload["sourceStatus"], "verified")
        self.assertEqual(payload["translationStatus"], "llm_reused")
        self.assertEqual(payload["summaryZh"], "复用的中文摘要。")
        self.assertEqual(payload["recommendationsZh"], ["复用上一轮翻译。"])

    def test_devourer_mixed_route_stat_weight_profile_forces_dungeon_slice_only(self):
        candidate = {"name": "Devourer Rio", "importCode": "CAE_DEVOURER", "gearItems": []}
        devourer = {
            "classKey": "demonhunter",
            "specKey": "devourer",
            "className": "Demon Hunter",
            "specName": "Devourer",
            "role": "dps",
            "primaryStat": "agility",
        }
        havoc = {**devourer, "specKey": "havoc", "specName": "Havoc"}
        mixed = next(item for item in stat_weights_payload.MPLUS_SCENARIOS if item["key"] == "mplus_mixed_route")
        single = next(item for item in stat_weights_payload.MPLUS_SCENARIOS if item["key"] == "mplus_single_boss")

        self.assertIn("demonhunter.enable_dungeon_slice=1", stat_weights_payload.build_stat_weight_profile(candidate, devourer, mixed))
        self.assertNotIn("demonhunter.enable_dungeon_slice=1", stat_weights_payload.build_stat_weight_profile(candidate, devourer, single))
        self.assertNotIn("demonhunter.enable_dungeon_slice=1", stat_weights_payload.build_stat_weight_profile(candidate, havoc, mixed))

        version_file = Path(self.tmp.name) / "simc-version.json"
        version_file.write_text(json.dumps({"localTag": "midnight-16b061b"}), encoding="utf-8")
        os.environ["WOW_SIMC_VERSION_FILE"] = str(version_file)
        captured_profiles = []

        def fake_simc(profile):
            captured_profiles.append(profile)
            return {"ran": True, "available": True, "rawOutput": fake_scale_factor_output(), "error": ""}

        with closing(self.connection()) as conn, patch.object(
            stat_weights_payload,
            "run_stat_weight_simcraft",
            side_effect=fake_simc,
        ), patch.object(stat_weights_payload, "call_chat_completion", return_value=fake_translation_response()):
            payload = stat_weights_payload.build_scenario_payload(
                conn,
                devourer,
                mixed,
                {"sourceStatus": "synced", "checkedAt": "2026-06-28T00:00:00+00:00"},
                {"sampleCount": 5},
                [candidate],
                [],
            )

        self.assertEqual(payload["validation"]["forcedOptions"], ["demonhunter.enable_dungeon_slice=1"])
        self.assertEqual(payload["validation"]["simcBuild"], "midnight-16b061b")
        self.assertTrue(any("demonhunter.enable_dungeon_slice=1" in profile for profile in captured_profiles))

    def test_parser_ignores_non_final_scale_factor_mentions(self):
        output = """
Generating Baseline profiles.
Scale factors are still being estimated; Crit=9.99 Haste=8.88 Mastery=7.77 Vers=6.66
"""

        self.assertEqual(stat_weights_payload.parse_stat_weight_scale_factors(output), {})

    def test_llm_guard_blocks_strong_claims_and_unexpected_numbers(self):
        evidence = {"weights": [{"key": "haste", "value": "1.3"}]}

        blocked, reason = stat_weights_payload.normalize_llm_translation(
            {
                "summaryZh": "这是最优答案。",
                "recommendationsZh": [],
                "warningsZh": [],
            },
            evidence,
        )
        self.assertIsNone(blocked)
        self.assertEqual(reason, "strong_claim_blocked")

        blocked, reason = stat_weights_payload.normalize_llm_translation(
            {
                "summaryZh": "建议达到 999 后再调整。",
                "recommendationsZh": [],
                "warningsZh": [],
            },
            evidence,
        )
        self.assertIsNone(blocked)
        self.assertIn("unexpected_llm_numbers", reason)


if __name__ == "__main__":
    unittest.main()

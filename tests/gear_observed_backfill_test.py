import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from server import gear_observed_backfill
from server import websim_payload


class FakeObservedProvider:
    name = "raiderio"

    def __init__(self, targets, candidates, profiles=None, errors=None, raises=None):
        self.targets = targets
        self.candidates = candidates
        self.profiles = profiles or []
        self.errors = errors or []
        self.raises = raises
        self.fetched_candidates = []

    def target_item_ids(self, conn):
        return list(self.targets)

    def candidate_profiles(self, conn):
        return list(self.candidates)

    def fetch_profiles(self, candidates, target_item_ids, deadline_at=0):
        self.fetched_candidates.extend(candidates)
        if self.raises:
            raise self.raises
        return list(self.profiles), list(self.errors)


class FakeSimcGearStatsRunner:
    def __init__(self, simc_json):
        self.simc_json = simc_json
        self.profiles = []

    def run(self, profile, timeout_seconds=0):
        self.profiles.append(profile)
        players = ((self.simc_json.get("sim") or {}).get("players") or [{}]) if isinstance(self.simc_json, dict) else [{}]
        gear = players[0].get("gear") if isinstance(players[0], dict) else {}
        return {"ok": True, "simcJson": self.simc_json, "resolvedSlotCount": len(gear or {}), "errors": []}


class FakeFailingSimcGearStatsRunner:
    def __init__(self):
        self.profiles = []

    def run(self, profile, timeout_seconds=0):
        self.profiles.append(profile)
        return {"ok": False, "simcJson": None, "resolvedSlotCount": 0, "errors": ["simc failed"]}


class GearObservedBackfillTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "gear-backfill.sqlite3"
        self.old_env = dict(os.environ)
        os.environ["WOW_NEWS_DB"] = str(self.db_path)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def seed_partial_variant(self, item_id="251111", slot="head"):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": f"loot-source-{item_id}-{slot}",
                    "itemId": item_id,
                    "sourceType": "dungeon",
                    "sourceLabel": "艾杰斯亚学院",
                    "seasonRevision": "season-test",
                    "payload": {"seasonRevision": "season-test", "instanceName": "艾杰斯亚学院"},
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": f"loot-partial-{item_id}-{slot}",
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": "needs-variant",
                    "label": "难度 / 装等待补",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "simcOptions": {},
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                    "payload": {"seasonRevision": "season-mn-1"},
                },
            )
            conn.commit()

    def seed_observed_variant(self, item_id="190001", slot="finger1"):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": f"observed-source-{item_id}-{slot}",
                    "itemId": item_id,
                    "sourceType": "observed_profile",
                    "sourceLabel": "stale observed profile",
                    "payload": {"profileUrl": "https://raider.io/characters/cn/example/stale"},
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": f"observed-stale-{item_id}-{slot}",
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": "stale-observed",
                    "label": "stale observed profile",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 704,
                    "simcOptions": {},
                    "status": "verified",
                    "blockers": [],
                    "payload": {"sourceType": "observed_profile"},
                },
            )
            conn.commit()

    def profile(self, name="Targetmage", item_id="251111", slot="head", bonuses=None):
        item = {
            "slot": slot,
            "itemId": item_id,
            "itemLevel": 704,
            "name": f"Observed {item_id}",
        }
        if bonuses is not None:
            item["bonuses"] = bonuses
        return {
            "name": name,
            "realmSlug": "isillien",
            "region": "cn",
            "classKey": "mage",
            "specKey": "frost",
            "profileUrl": f"https://raider.io/characters/cn/isillien/{name}",
            "gear": [item],
        }

    def test_observed_backfill_runner_adds_simc_json_stats_before_target_filtering(self):
        self.seed_partial_variant("251111")
        self.seed_partial_variant("251222", "neck")
        target_profile = self.profile(name="A", item_id="251111", slot="head", bonuses=[12345])
        target_profile["gear"].append(
            {
                "slot": "neck",
                "itemId": "251222",
                "itemLevel": 704,
                "name": "Observed non target neck",
                "bonuses": [67890],
            }
        )
        target_profile["gear"].append(
            {
                "slot": "finger_1",
                "itemId": "190001",
                "itemLevel": 704,
                "name": "Old season ring",
                "bonuses": [99999],
            }
        )
        provider = FakeObservedProvider(
            targets=["251111"],
            candidates=[{"name": "A"}],
            profiles=[target_profile],
        )
        simc_runner = FakeSimcGearStatsRunner(
            {
                "sim": {
                    "players": [
                        {
                            "gear": {
                                "head": {
                                    "id": 251111,
                                    "ilevel": 704,
                                    "encoded_item": "observed_head,id=251111,ilevel=704,bonus_id=12345",
                                    "intellect": 321,
                                    "stamina": 654,
                                    "haste_rating": 77,
                                },
                                "neck": {
                                    "id": 251222,
                                    "ilevel": 704,
                                    "encoded_item": "observed_neck,id=251222,ilevel=704,bonus_id=67890",
                                    "stamina": 111,
                                    "mastery_rating": 22,
                                },
                                "finger1": {
                                    "id": 190001,
                                    "ilevel": 704,
                                    "encoded_item": "old_ring,id=190001,ilevel=704,bonus_id=99999",
                                    "stamina": 999,
                                },
                            }
                        }
                    ]
                }
            }
        )

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            simc_runner=simc_runner,
            enable_simc_stats=True,
            target_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=["251111"])
            rows = conn.execute(
                """
                SELECT item_id, payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY item_id
                """
            ).fetchall()

        self.assertEqual(len(simc_runner.profiles), 1)
        self.assertEqual([item["itemId"] for item in simc_runner.profiles[0]["gear"]], ["251111", "251222", "190001"])
        self.assertEqual(summary["simcProfileCount"], 1)
        self.assertEqual(summary["simcResolvedProfileCount"], 1)
        self.assertEqual([row[0] for row in rows], ["251111"])
        payload = json.loads(rows[0][1])
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statSummary"], "智力 321；耐力 654；急速 77")

    def test_observed_backfill_runner_can_sync_full_profile_gear_with_simc_stats(self):
        self.seed_partial_variant("251111")
        self.seed_partial_variant("251222", "neck")
        self.seed_partial_variant("251333", "feet")
        self.seed_observed_variant("190001", "finger1")
        self.seed_observed_variant("251333", "feet")
        target_profile = self.profile(name="A", item_id="251111", slot="head", bonuses=[12345])
        target_profile["gear"].append(
            {
                "slot": "neck",
                "itemId": "251222",
                "itemLevel": 704,
                "name": "Observed non target neck",
                "bonuses": [67890],
            }
        )
        target_profile["gear"].append(
            {
                "slot": "finger_1",
                "itemId": "190001",
                "itemLevel": 704,
                "name": "Old season ring",
                "bonuses": [99999],
            }
        )
        provider = FakeObservedProvider(
            targets=["251111"],
            candidates=[{"name": "A"}],
            profiles=[target_profile],
        )
        simc_runner = FakeSimcGearStatsRunner(
            {
                "sim": {
                    "players": [
                        {
                            "gear": {
                                "head": {
                                    "id": 251111,
                                    "ilevel": 704,
                                    "encoded_item": "observed_head,id=251111,ilevel=704,bonus_id=12345",
                                    "intellect": 321,
                                },
                                "neck": {
                                    "id": 251222,
                                    "ilevel": 704,
                                    "encoded_item": "observed_neck,id=251222,ilevel=704,bonus_id=67890",
                                    "stamina": 111,
                                    "mastery_rating": 22,
                                },
                                "finger1": {
                                    "id": 190001,
                                    "ilevel": 704,
                                    "encoded_item": "old_ring,id=190001,ilevel=704,bonus_id=99999",
                                    "stamina": 999,
                                },
                            }
                        }
                    ]
                }
            }
        )

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            simc_runner=simc_runner,
            enable_simc_stats=True,
            sync_full_profile_gear=True,
            target_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=["251111"])
            rows = conn.execute(
                """
                SELECT item_id, payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY item_id
                """
            ).fetchall()
            stale_source_rows = conn.execute(
                """
                SELECT COUNT(*)
                FROM websim_gear_sources
                WHERE source_type = 'observed_profile'
                  AND item_id IN ('190001', '251333')
                """
            ).fetchone()[0]

        self.assertEqual(summary["observedVariantRowsUpserted"], 2)
        self.assertEqual(summary["observedVariantRowsPruned"], 2)
        self.assertEqual(summary["observedVariantRowsPrunedMissingStats"], 1)
        self.assertEqual(summary["observedSourceRowsPruned"], 2)
        self.assertEqual(state["simcProfileCount"], 1)
        self.assertEqual(state["simcResolvedProfileCount"], 1)
        self.assertEqual(state["simcResolvedSlotCount"], 3)
        self.assertEqual([row[0] for row in rows], ["251111", "251222"])
        self.assertEqual(stale_source_rows, 0)
        neck_payload = json.loads(rows[1][1])
        self.assertEqual(neck_payload["statSource"], "simulationcraft")
        self.assertEqual(neck_payload["statSummary"], "耐力 111；精通 22")

    def test_observed_backfill_runner_does_not_upsert_full_profile_gear_without_simc_stats(self):
        self.seed_partial_variant("251111")
        provider = FakeObservedProvider(
            targets=["251111"],
            candidates=[{"name": "A"}],
            profiles=[self.profile(name="A", item_id="251111", slot="head", bonuses=[12345])],
        )
        simc_runner = FakeFailingSimcGearStatsRunner()

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            simc_runner=simc_runner,
            enable_simc_stats=True,
            sync_full_profile_gear=True,
            target_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            observed_rows = conn.execute(
                """
                SELECT COUNT(*)
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                """
            ).fetchone()[0]

        self.assertEqual(len(simc_runner.profiles), 1)
        self.assertEqual(summary["simcProfileCount"], 1)
        self.assertEqual(summary["simcResolvedProfileCount"], 0)
        self.assertEqual(summary["observedVariantRowsUpserted"], 0)
        self.assertEqual(observed_rows, 0)
        self.assertIn("simc failed", summary["errors"])

    def test_observed_backfill_runner_updates_only_window_and_persists_cursor(self):
        self.seed_partial_variant("251111")
        provider = FakeObservedProvider(
            targets=["251111", "251222"],
            candidates=[{"name": "A"}, {"name": "B"}],
            profiles=[self.profile(name="A", item_id="251111", bonuses=[12345])],
        )

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            target_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=["251111", "251222"])
            observed_items = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT item_id
                    FROM websim_gear_variants
                    WHERE source_type = 'observed_profile'
                    ORDER BY item_id
                    """
                ).fetchall()
            ]

        self.assertEqual([item["name"] for item in provider.fetched_candidates], ["A"])
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["processedTargetItemIds"], ["251111"])
        self.assertEqual(summary["processedProfileCount"], 1)
        self.assertEqual(observed_items, ["251111"])
        self.assertEqual(state["cursor"]["targetOffset"], 1)
        self.assertEqual(state["cursor"]["profileOffset"], 1)
        self.assertEqual(state["matchedTargetItemIds"], ["251111"])

    def test_observed_backfill_runner_skips_provider_fetch_when_no_target_items(self):
        provider = FakeObservedProvider(
            targets=[],
            candidates=[{"name": "A"}],
            raises=AssertionError("should not fetch without target items"),
        )

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            target_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=[])

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["processedTargetItemIds"], [])
        self.assertEqual(summary["processedProfileCount"], 0)
        self.assertEqual(provider.fetched_candidates, [])
        self.assertEqual(state["lastRunStatus"], "ok")
        self.assertEqual(state["cursor"]["targetItemCount"], 0)

    def test_observed_backfill_runner_does_not_trigger_full_websim_sync_or_journal_fetch(self):
        provider = FakeObservedProvider(
            targets=["251111"],
            candidates=[{"name": "A"}],
            profiles=[self.profile(name="A", item_id="251111", bonuses=[12345])],
        )

        with patch.object(gear_observed_backfill.websim_payload, "sync_websim_gear_catalog") as full_sync:
            with patch.object(gear_observed_backfill.websim_payload, "sync_blizzard_gear_mod_option_metadata") as journal:
                summary = gear_observed_backfill.run_gear_observed_backfill(
                    self.db_path,
                    provider=provider,
                    target_limit=1,
                    profile_limit=1,
                )

        self.assertEqual(summary["status"], "ok")
        full_sync.assert_not_called()
        journal.assert_not_called()

    def test_observed_backfill_runner_marks_error_without_losing_cursor(self):
        provider = FakeObservedProvider(
            targets=["251111", "251222"],
            candidates=[{"name": "A"}, {"name": "B"}],
            raises=RuntimeError("provider failed"),
        )
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=["251111", "251222"])
            state["cursor"]["targetOffset"] = 1
            state["cursor"]["profileOffset"] = 1
            websim_payload.write_gear_observed_backfill_state(conn, state)
            conn.commit()

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            target_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=["251111", "251222"])

        self.assertEqual(summary["status"], "error")
        self.assertEqual(state["lastRunStatus"], "error")
        self.assertEqual(state["cursor"]["targetOffset"], 1)
        self.assertEqual(state["cursor"]["profileOffset"], 1)
        self.assertEqual(state["lastError"], "provider failed")

    def test_observed_backfill_runner_promotes_only_with_deterministic_tuple_evidence(self):
        self.seed_partial_variant("251111")
        self.seed_partial_variant("251222")
        provider = FakeObservedProvider(
            targets=["251111", "251222"],
            candidates=[{"name": "A"}, {"name": "B"}],
            profiles=[
                self.profile(name="A", item_id="251111", bonuses=[12345]),
                self.profile(name="B", item_id="251222", bonuses=None),
            ],
        )

        summary = gear_observed_backfill.run_gear_observed_backfill(
            self.db_path,
            provider=provider,
            target_limit=2,
            profile_limit=2,
        )

        with self.connection() as conn:
            official_rows = conn.execute(
                """
                SELECT item_id, source_type, status, item_level, simc_options_json
                FROM websim_gear_variants
                WHERE source_type = 'dungeon'
                ORDER BY item_id, status
                """
            ).fetchall()

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["officialVariantsPromoted"], 1)
        promoted = [row for row in official_rows if row[0] == "251111" and row[2] == "verified"]
        partial = [row for row in official_rows if row[0] == "251222" and row[2] == "partial"]
        self.assertEqual(len(promoted), 1)
        self.assertEqual(promoted[0][3], 704)
        self.assertEqual(partial[0][4], "{}")

    def test_cli_accepts_simc_stats_and_full_profile_gear_flags(self):
        with patch.object(gear_observed_backfill, "run_gear_observed_backfill") as runner:
            runner.return_value = {"status": "ok", "provider": "raiderio"}
            with patch("sys.stdout", new=StringIO()):
                exit_code = gear_observed_backfill.main(
                    [
                        "--db",
                        str(self.db_path),
                        "--target-limit",
                        "3",
                        "--profile-limit",
                        "4",
                        "--simc-stats",
                        "--full-profile-gear",
                        "--simc-timeout-seconds",
                        "12",
                        "--json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        runner.assert_called_once()
        _, kwargs = runner.call_args
        self.assertEqual(kwargs["target_limit"], 3)
        self.assertEqual(kwargs["profile_limit"], 4)
        self.assertTrue(kwargs["enable_simc_stats"])
        self.assertTrue(kwargs["sync_full_profile_gear"])
        self.assertEqual(kwargs["simc_timeout_seconds"], 12)


if __name__ == "__main__":
    unittest.main()

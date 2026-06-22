import os
import sqlite3
import tempfile
import unittest
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

    def connection(self):
        return sqlite3.connect(self.db_path)

    def seed_partial_variant(self, item_id="251111", slot="head"):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
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


if __name__ == "__main__":
    unittest.main()

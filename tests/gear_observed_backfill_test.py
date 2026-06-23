import json
import os
import sqlite3
import subprocess
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


class FakeItemFailingSimcGearStatsRunner:
    def __init__(self, item_id):
        self.item_id = str(item_id)
        self.profiles = []

    def run(self, profile, timeout_seconds=0):
        self.profiles.append(profile)
        return {
            "ok": False,
            "simcJson": None,
            "resolvedSlotCount": 0,
            "errors": [
                f"Error: Initialization error: Player 'A': Item 'item_{self.item_id}' Slot 'waist': Error retrieving item from BCP API"
            ],
        }


class FakeProfileFailingSimcGearStatsRunner:
    def __init__(self, character_name):
        self.character_name = str(character_name)
        self.profiles = []

    def run(self, profile, timeout_seconds=0):
        self.profiles.append(profile)
        return {
            "ok": False,
            "simcJson": None,
            "resolvedSlotCount": 0,
            "errors": [
                f"Trivial: Mistweaver Monk for Player '{self.character_name}' is not currently supported.\n"
                "Error: Initialization error: No active players in sim!"
            ],
        }


class FakeConnection:
    def __init__(self):
        self.statements = []

    def execute(self, statement, *args, **kwargs):
        self.statements.append(str(statement))
        return self


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

    def test_backfill_db_connection_sets_busy_timeout(self):
        fake_conn = FakeConnection()
        calls = []

        def fake_connect(path, **kwargs):
            calls.append((path, kwargs))
            return fake_conn

        with patch.object(gear_observed_backfill.sqlite3, "connect", side_effect=fake_connect):
            conn = gear_observed_backfill.connect_backfill_db(self.db_path)

        self.assertIs(conn, fake_conn)
        self.assertEqual(calls[0][0], self.db_path)
        self.assertGreaterEqual(calls[0][1]["timeout"], 30)
        self.assertIn("PRAGMA busy_timeout = 30000", fake_conn.statements)

    def test_readonly_backfill_db_connection_uses_uri_mode_ro_and_query_only(self):
        fake_conn = FakeConnection()
        calls = []

        def fake_connect(path, **kwargs):
            calls.append((path, kwargs))
            return fake_conn

        with patch.object(gear_observed_backfill.sqlite3, "connect", side_effect=fake_connect):
            conn = gear_observed_backfill.connect_readonly_backfill_db(self.db_path)

        self.assertIs(conn, fake_conn)
        self.assertTrue(str(calls[0][0]).startswith("file:"))
        self.assertIn("mode=ro", str(calls[0][0]))
        self.assertIn("immutable=1", str(calls[0][0]))
        self.assertTrue(calls[0][1]["uri"])
        self.assertGreaterEqual(calls[0][1]["timeout"], 30)
        self.assertIn("PRAGMA query_only = ON", fake_conn.statements)

    def test_simc_runner_passes_blizzard_credentials_as_temporary_simc_apikey(self):
        profile = self.profile(name="A", item_id="251111", slot="head", bonuses=[12345])
        captured = {}

        def fake_run(args, **kwargs):
            env = kwargs.get("env")
            captured["env"] = env
            key_path = Path(env["HOME"]) / ".simc_apikey"
            captured["home"] = Path(env["HOME"])
            captured["apikey"] = key_path.read_text()
            captured["mode"] = key_path.stat().st_mode & 0o777
            payload = {
                "sim": {
                    "players": [
                        {
                            "gear": {
                                "head": {
                                    "id": 251111,
                                    "ilevel": 704,
                                    "encoded_item": "observed_head,id=251111,ilevel=704,bonus_id=12345",
                                    "intellect": 321,
                                }
                            }
                        }
                    ]
                }
            }
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

        with patch.dict(
            os.environ,
            {"WOW_BLIZZARD_CLIENT_ID": "client-id", "WOW_BLIZZARD_CLIENT_SECRET": "client-secret"},
        ):
            with patch.object(gear_observed_backfill.subprocess, "run", side_effect=fake_run):
                result = gear_observed_backfill.SimulationCraftGearStatsRunner(simc_bin="/tmp/simc").run(profile)

        self.assertTrue(result["ok"], result)
        self.assertIsNotNone(captured["env"])
        self.assertEqual(captured["apikey"], "client-id:client-secret\n")
        self.assertEqual(captured["mode"], 0o600)
        self.assertFalse(captured["home"].exists())

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

    def seed_official_observed_variant_without_stats(self, item_id="258575", slot="back"):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": f"loot-source-{item_id}-{slot}",
                    "itemId": item_id,
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "seasonRevision": "season-test",
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": f"loot-observed-{item_id}-{slot}-stale",
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": "observed-289-stale",
                    "label": "Observed 289",
                    "sourceType": "dungeon",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/6652/13577/12699/12806"},
                    "status": "verified",
                    "payload": {"observedVariantSource": "observed_profile"},
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

    def test_observed_backfill_runner_retries_transient_sqlite_lock_after_simc_stats(self):
        self.seed_partial_variant("251111")
        provider = FakeObservedProvider(
            targets=["251111"],
            candidates=[{"name": "A"}],
            profiles=[self.profile(name="A", item_id="251111", slot="head", bonuses=[12345])],
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
                                }
                            }
                        }
                    ]
                }
            }
        )
        calls = {"promote": 0}
        original_promote = websim_payload.promote_official_gear_variants_from_observed

        def flaky_promote(conn):
            calls["promote"] += 1
            if calls["promote"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return original_promote(conn)

        with patch.object(websim_payload, "promote_official_gear_variants_from_observed", side_effect=flaky_promote):
            try:
                summary = gear_observed_backfill.run_gear_observed_backfill(
                    self.db_path,
                    provider=provider,
                    simc_runner=simc_runner,
                    enable_simc_stats=True,
                    target_limit=1,
                    profile_limit=1,
                )
            except sqlite3.OperationalError as error:
                self.fail(f"expected transient sqlite lock to be retried, got {error}")

        self.assertEqual(calls["promote"], 2)
        self.assertEqual(summary["status"], "ok")

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

    def test_observed_backfill_runner_prunes_official_observed_variants_without_simc_stats(self):
        self.seed_partial_variant("251111")
        self.seed_official_observed_variant_without_stats("258575", "back")
        provider = FakeObservedProvider(
            targets=["251111"],
            candidates=[{"name": "A"}],
            profiles=[self.profile(name="A", item_id="251111", slot="head", bonuses=[12345])],
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
                                }
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
            stale_official_rows = conn.execute(
                """
                SELECT COUNT(*)
                FROM websim_gear_variants
                WHERE source_type IN ('dungeon', 'raid', 'tier_set')
                  AND difficulty_key = 'observed_profile'
                  AND status = 'verified'
                  AND COALESCE(json_extract(payload_json, '$.statSource'), '') != 'simulationcraft'
                """
            ).fetchone()[0]

        self.assertEqual(summary["officialObservedVariantRowsPrunedMissingStats"], 1)
        self.assertEqual(stale_official_rows, 0)

    def test_existing_observed_variant_simc_stats_backfill_uses_local_db_profiles(self):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            for item_id, slot, bonus_id in (
                ("251111", "head", "12345"),
                ("251222", "neck", "67890"),
            ):
                websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"observed-source-mage-frost-{slot}-{item_id}",
                        "itemId": item_id,
                        "sourceType": "observed_profile",
                        "sourceLabel": "Raider.IO CN observed mage frost",
                        "payload": {
                            "classKeys": ["mage"],
                            "specKeys": ["frost"],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "classKey": "mage",
                                    "specKey": "frost",
                                    "slot": slot,
                                    "itemId": item_id,
                                    "itemLevel": 704,
                                    "characterName": "A",
                                    "realmSlug": "isillien",
                                    "profileUrl": "https://raider.io/characters/cn/isillien/A",
                                }
                            ],
                        },
                    },
                )
                websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-mage-frost-{slot}-{item_id}",
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": f"observed-704-{slot}",
                        "label": "Observed 704",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 704,
                        "simcOptions": {"bonus_id": bonus_id},
                        "status": "verified",
                        "payload": {
                            "classKeys": ["mage"],
                            "specKeys": ["frost"],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "classKey": "mage",
                                    "specKey": "frost",
                                    "slot": slot,
                                    "itemId": item_id,
                                    "itemLevel": 704,
                                    "characterName": "A",
                                    "realmSlug": "isillien",
                                    "profileUrl": "https://raider.io/characters/cn/isillien/A",
                                }
                            ],
                        },
                    },
                )
            conn.commit()
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
                                },
                                "neck": {
                                    "id": 251222,
                                    "ilevel": 704,
                                    "encoded_item": "observed_neck,id=251222,ilevel=704,bonus_id=67890",
                                    "stamina": 111,
                                    "mastery_rating": 22,
                                },
                            }
                        }
                    ]
                }
            }
        )

        summary = gear_observed_backfill.run_existing_observed_variant_simc_stats_backfill(
            self.db_path,
            simc_runner=simc_runner,
            variant_limit=10,
            profile_limit=1,
        )

        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT item_id, payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY item_id
                """
            ).fetchall()

        self.assertEqual(len(simc_runner.profiles), 1)
        self.assertEqual([item["itemId"] for item in simc_runner.profiles[0]["gear"]], ["251111", "251222"])
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["localProfileCount"], 1)
        self.assertEqual(summary["simcResolvedProfileCount"], 1)
        self.assertEqual(summary["observedVariantRowsUpserted"], 2)
        payloads = {item_id: json.loads(payload_json) for item_id, payload_json in rows}
        self.assertEqual(payloads["251111"]["statSummary"], "智力 321；耐力 654")
        self.assertEqual(payloads["251222"]["statSummary"], "耐力 111；精通 22")

    def test_existing_observed_variant_simc_stats_backfill_retries_transient_sqlite_lock(self):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-mage-frost-head-251111",
                    "itemId": "251111",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO CN observed mage frost",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [
                            {
                                "sourceName": "Raider.IO",
                                "classKey": "mage",
                                "specKey": "frost",
                                "slot": "head",
                                "itemId": "251111",
                                "itemLevel": 704,
                                "characterName": "A",
                                "realmSlug": "isillien",
                                "profileUrl": "https://raider.io/characters/cn/isillien/A",
                            }
                        ],
                    },
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-head-251111",
                    "itemId": "251111",
                    "slot": "head",
                    "variantKey": "observed-704-head",
                    "label": "Observed 704",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 704,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [
                            {
                                "sourceName": "Raider.IO",
                                "classKey": "mage",
                                "specKey": "frost",
                                "slot": "head",
                                "itemId": "251111",
                                "itemLevel": 704,
                                "characterName": "A",
                                "realmSlug": "isillien",
                                "profileUrl": "https://raider.io/characters/cn/isillien/A",
                            }
                        ],
                    },
                },
            )
            conn.commit()
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
                                }
                            }
                        }
                    ]
                }
            }
        )
        calls = {"promote": 0}
        original_promote = websim_payload.promote_official_gear_variants_from_observed

        def flaky_promote(conn):
            calls["promote"] += 1
            if calls["promote"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return original_promote(conn)

        with patch.object(websim_payload, "promote_official_gear_variants_from_observed", side_effect=flaky_promote):
            try:
                summary = gear_observed_backfill.run_existing_observed_variant_simc_stats_backfill(
                    self.db_path,
                    simc_runner=simc_runner,
                    variant_limit=10,
                    profile_limit=1,
                )
            except sqlite3.OperationalError as error:
                self.fail(f"expected transient sqlite lock to be retried, got {error}")

        self.assertEqual(calls["promote"], 2)
        self.assertEqual(summary["status"], "ok")

    def test_existing_observed_variant_simc_stats_backfill_retries_transient_sqlite_lock_while_marking_failures(self):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-mage-frost-waist-268289",
                    "itemId": "268289",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO CN observed mage frost",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [
                            {
                                "sourceName": "Raider.IO",
                                "classKey": "mage",
                                "specKey": "frost",
                                "slot": "waist",
                                "itemId": "268289",
                                "itemLevel": 704,
                                "characterName": "A",
                                "realmSlug": "isillien",
                                "profileUrl": "https://raider.io/characters/cn/isillien/A",
                            }
                        ],
                    },
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-waist-268289",
                    "itemId": "268289",
                    "slot": "waist",
                    "variantKey": "observed-704-waist",
                    "label": "Observed 704",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 704,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [
                            {
                                "sourceName": "Raider.IO",
                                "classKey": "mage",
                                "specKey": "frost",
                                "slot": "waist",
                                "itemId": "268289",
                                "itemLevel": 704,
                                "characterName": "A",
                                "realmSlug": "isillien",
                                "profileUrl": "https://raider.io/characters/cn/isillien/A",
                            }
                        ],
                    },
                },
            )
            conn.commit()
        calls = {"mark": 0}
        original_mark = gear_observed_backfill.mark_existing_observed_variant_simc_failures

        def flaky_mark(conn, errors):
            calls["mark"] += 1
            if calls["mark"] == 1:
                raise sqlite3.OperationalError("database is locked")
            return original_mark(conn, errors)

        with patch.object(gear_observed_backfill, "mark_existing_observed_variant_simc_failures", side_effect=flaky_mark):
            try:
                summary = gear_observed_backfill.run_existing_observed_variant_simc_stats_backfill(
                    self.db_path,
                    simc_runner=FakeItemFailingSimcGearStatsRunner("268289"),
                    variant_limit=10,
                    profile_limit=1,
                )
            except sqlite3.OperationalError as error:
                self.fail(f"expected transient sqlite lock while marking failures to be retried, got {error}")

        self.assertEqual(calls["mark"], 2)
        self.assertEqual(summary["simcFailureRowsMarked"], 1)

    def test_existing_observed_variant_simc_stats_backfill_marks_failed_items_so_later_batches_can_progress(self):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            for item_id, character_name in (("268289", "A"), ("251111", "B")):
                websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"observed-source-mage-frost-waist-{item_id}",
                        "itemId": item_id,
                        "sourceType": "observed_profile",
                        "sourceLabel": "Raider.IO CN observed mage frost",
                        "payload": {
                            "classKeys": ["mage"],
                            "specKeys": ["frost"],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "classKey": "mage",
                                    "specKey": "frost",
                                    "slot": "waist",
                                    "itemId": item_id,
                                    "itemLevel": 704,
                                    "characterName": character_name,
                                    "realmSlug": "isillien",
                                    "profileUrl": f"https://raider.io/characters/cn/isillien/{character_name}",
                                }
                            ],
                        },
                    },
                )
                websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-mage-frost-waist-{item_id}",
                        "itemId": item_id,
                        "slot": "waist",
                        "variantKey": f"observed-704-{item_id}",
                        "label": "Observed 704",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 704,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                        "payload": {
                            "classKeys": ["mage"],
                            "specKeys": ["frost"],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "classKey": "mage",
                                    "specKey": "frost",
                                    "slot": "waist",
                                    "itemId": item_id,
                                    "itemLevel": 704,
                                    "characterName": character_name,
                                    "realmSlug": "isillien",
                                    "profileUrl": f"https://raider.io/characters/cn/isillien/{character_name}",
                                }
                            ],
                        },
                    },
                )
            conn.commit()

        summary = gear_observed_backfill.run_existing_observed_variant_simc_stats_backfill(
            self.db_path,
            simc_runner=FakeItemFailingSimcGearStatsRunner("268289"),
            variant_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            failed_payload = json.loads(
                conn.execute(
                    "SELECT payload_json FROM websim_gear_variants WHERE item_id = '268289'"
                ).fetchone()[0]
            )
            next_profiles = gear_observed_backfill.existing_observed_variant_profiles(
                conn,
                variant_limit=10,
                profile_limit=1,
            )

        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["simcFailureRowsMarked"], 1)
        self.assertEqual(failed_payload["simcStatStatus"], "failed")
        self.assertIn("item_268289", failed_payload["simcStatError"])
        self.assertEqual([item["itemId"] for item in next_profiles[0]["gear"]], ["251111"])

    def test_existing_observed_variant_simc_stats_backfill_marks_failed_profiles_so_later_batches_can_progress(self):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            for item_id, character_name in (("251111", "Unsupported"), ("251222", "Next")):
                websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"observed-source-monk-mistweaver-head-{item_id}",
                        "itemId": item_id,
                        "sourceType": "observed_profile",
                        "sourceLabel": "Raider.IO CN observed monk mistweaver",
                        "payload": {
                            "classKeys": ["monk"],
                            "specKeys": ["mistweaver"],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "classKey": "monk",
                                    "specKey": "mistweaver",
                                    "slot": "head",
                                    "itemId": item_id,
                                    "itemLevel": 704,
                                    "characterName": character_name,
                                    "realmSlug": "isillien",
                                    "profileUrl": f"https://raider.io/characters/cn/isillien/{character_name}",
                                }
                            ],
                        },
                    },
                )
                websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-monk-mistweaver-head-{item_id}",
                        "itemId": item_id,
                        "slot": "head",
                        "variantKey": f"observed-704-{item_id}",
                        "label": "Observed 704",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 704,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                        "payload": {
                            "classKeys": ["monk"],
                            "specKeys": ["mistweaver"],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "classKey": "monk",
                                    "specKey": "mistweaver",
                                    "slot": "head",
                                    "itemId": item_id,
                                    "itemLevel": 704,
                                    "characterName": character_name,
                                    "realmSlug": "isillien",
                                    "profileUrl": f"https://raider.io/characters/cn/isillien/{character_name}",
                                }
                            ],
                        },
                    },
                )
            conn.commit()

        summary = gear_observed_backfill.run_existing_observed_variant_simc_stats_backfill(
            self.db_path,
            simc_runner=FakeProfileFailingSimcGearStatsRunner("Unsupported"),
            variant_limit=1,
            profile_limit=1,
        )

        with self.connection() as conn:
            failed_payload = json.loads(
                conn.execute(
                    "SELECT payload_json FROM websim_gear_variants WHERE item_id = '251111'"
                ).fetchone()[0]
            )
            next_profiles = gear_observed_backfill.existing_observed_variant_profiles(
                conn,
                variant_limit=10,
                profile_limit=1,
            )

        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["simcFailureRowsMarked"], 1)
        self.assertEqual(failed_payload["simcStatStatus"], "failed")
        self.assertEqual(failed_payload["simcStatFailureKind"], "unsupported_profile")
        self.assertIn("not currently supported", failed_payload["simcStatError"])
        self.assertEqual([item["itemId"] for item in next_profiles[0]["gear"]], ["251222"])

    def test_observed_profile_simc_text_adds_fallback_weapon_when_observed_profile_has_no_main_hand(self):
        profile = {
            "classKey": "deathknight",
            "specKey": "unholy",
            "characterName": "NoWeapon",
            "gear": [
                {
                    "slot": "head",
                    "itemId": "249970",
                    "itemLevel": 704,
                    "bonus_id": "12345",
                    "name": "Relentless Rider's Crown",
                }
            ],
        }

        simc_text, errors = gear_observed_backfill.observed_profile_simc_text(profile)

        self.assertEqual(errors, [])
        self.assertIn("main_hand=worn_shortsword,id=25", simc_text)
        self.assertIn("head=,id=249970,ilevel=704,bonus_id=12345", simc_text)

    def test_observed_profile_simc_text_does_not_add_fallback_weapon_when_main_hand_exists(self):
        profile = {
            "classKey": "mage",
            "specKey": "frost",
            "characterName": "HasWeapon",
            "gear": [
                {
                    "slot": "main_hand",
                    "itemId": "251178",
                    "itemLevel": 704,
                    "bonus_id": "777",
                    "name": "Real Staff",
                },
                {
                    "slot": "back",
                    "itemId": "258575",
                    "itemLevel": 704,
                    "bonus_id": "888",
                    "name": "刚鳞大氅",
                },
            ],
        }

        simc_text, errors = gear_observed_backfill.observed_profile_simc_text(profile)

        self.assertEqual(errors, [])
        self.assertNotIn("worn_shortsword", simc_text)
        self.assertIn("main_hand=,id=251178,ilevel=704,bonus_id=777", simc_text)

    def test_observed_profile_simc_text_omits_observed_item_names_to_avoid_simc_name_mismatch(self):
        profile = {
            "classKey": "druid",
            "specKey": "guardian",
            "characterName": "LocalizedGear",
            "gear": [
                {
                    "slot": "wrist",
                    "itemId": "249327",
                    "itemLevel": 289,
                    "bonus_id": "13440/6652/13577/12699/12806",
                    "name": "虚空剥蚀护腕",
                }
            ],
        }

        simc_text, errors = gear_observed_backfill.observed_profile_simc_text(profile)

        self.assertEqual(errors, [])
        self.assertIn("wrist=,id=249327,ilevel=289,bonus_id=13440/6652/13577/12699/12806", simc_text)
        self.assertNotIn("wrist=item_249327", simc_text)

    def test_observed_profile_simc_text_adds_fallback_offhand_for_demon_hunter_without_offhand(self):
        profile = {
            "classKey": "demonhunter",
            "specKey": "havoc",
            "characterName": "NoOffhand",
            "gear": [
                {
                    "slot": "hands",
                    "itemId": "249971",
                    "itemLevel": 704,
                    "bonus_id": "12345",
                    "name": "Relentless Rider's Bonegrasps",
                }
            ],
        }

        simc_text, errors = gear_observed_backfill.observed_profile_simc_text(profile)

        self.assertEqual(errors, [])
        self.assertIn("main_hand=worn_shortsword,id=25", simc_text)
        self.assertIn("off_hand=worn_shortsword,id=25", simc_text)

    def test_simc_runner_preserves_full_failure_text_for_later_classification(self):
        class FailedProc:
            returncode = 1
            stdout = ""
            stderr = (
                "Error: Initialization error: Player 'LongLog': "
                + ("x" * 900)
                + " Mistweaver Monk is not currently supported.\n"
                + "Error: Initialization error: No active players in sim!"
            )

        profile = {
            "classKey": "monk",
            "specKey": "mistweaver",
            "characterName": "LongLog",
            "gear": [
                {
                    "slot": "head",
                    "itemId": "250015",
                    "itemLevel": 704,
                    "bonus_id": "12345",
                    "name": "Fearsome Visage",
                }
            ],
        }

        with patch.object(gear_observed_backfill.subprocess, "run", return_value=FailedProc()):
            result = gear_observed_backfill.SimulationCraftGearStatsRunner("/fake/simc").run(profile)

        self.assertFalse(result["ok"])
        self.assertIn("Player 'LongLog'", result["errors"][0])
        self.assertIn("not currently supported", result["errors"][0])

    def test_simc_runner_preserves_stderr_when_success_exit_emits_no_json(self):
        class EmptyJsonProc:
            returncode = 0
            stdout = ""
            stderr = "Trivial: Player probe unable to download item id=268291 information from Blizzard, reason: The document is empty."

        profile = {
            "classKey": "deathknight",
            "specKey": "blood",
            "characterName": "probe",
            "gear": [
                {
                    "slot": "neck",
                    "itemId": "268291",
                    "itemLevel": 704,
                    "bonus_id": "12345",
                    "name": "item_268291",
                }
            ],
        }

        with patch.object(gear_observed_backfill.subprocess, "run", return_value=EmptyJsonProc()):
            result = gear_observed_backfill.SimulationCraftGearStatsRunner("/fake/simc").run(profile)

        self.assertFalse(result["ok"])
        self.assertIn("item id=268291", result["errors"][0])
        self.assertIn("document is empty", result["errors"][0])

    def test_simc_runner_preserves_stderr_when_json_has_no_resolved_gear(self):
        class EmptyGearProc:
            returncode = 0
            stdout = 'SimulationCraft preamble\\n{"sim":{"players":[{"gear":{}}]}}'
            stderr = "Trivial: Player probe unable to download item id=268291 information from Blizzard, reason: The document is empty."

        profile = {
            "classKey": "deathknight",
            "specKey": "blood",
            "characterName": "probe",
            "gear": [
                {
                    "slot": "neck",
                    "itemId": "268291",
                    "itemLevel": 704,
                    "bonus_id": "12345",
                    "name": "item_268291",
                }
            ],
        }

        with patch.object(gear_observed_backfill.subprocess, "run", return_value=EmptyGearProc()):
            result = gear_observed_backfill.SimulationCraftGearStatsRunner("/fake/simc").run(profile)

        self.assertFalse(result["ok"])
        self.assertIn("item id=268291", result["errors"][0])
        self.assertIn("document is empty", result["errors"][0])

    def test_simc_error_item_ids_parse_success_exit_item_resolution_errors(self):
        errors = [
            "Trivial: Player probe unable to download item id=268291 information from Blizzard, reason: The document is empty."
        ]

        self.assertEqual(gear_observed_backfill.simc_error_item_ids(errors), ["268291"])
        self.assertIn("268291", gear_observed_backfill.simc_error_for_item(errors, "268291"))

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

    def test_observed_backfill_plan_only_reports_window_without_fetching_or_writing(self):
        provider = FakeObservedProvider(
            targets=["251111", "251222"],
            candidates=[{"name": "A"}, {"name": "B"}],
            raises=AssertionError("plan-only must not fetch external profiles"),
        )
        with self.connection() as seed_conn:
            websim_payload.ensure_websim_tables(seed_conn)
            state = websim_payload.read_gear_observed_backfill_state(
                seed_conn,
                target_item_ids=["251111", "251222"],
                provider=provider.name,
            )
            state["cursor"]["targetOffset"] = 1
            state["cursor"]["profileOffset"] = 1
            websim_payload.write_gear_observed_backfill_state(seed_conn, state)
            seed_conn.commit()
        readonly_conn = sqlite3.connect(self.db_path)
        readonly_conn.execute("PRAGMA query_only=ON")
        self.addCleanup(readonly_conn.close)

        with patch.object(gear_observed_backfill, "connect_readonly_backfill_db", return_value=readonly_conn):
            summary = gear_observed_backfill.plan_gear_observed_backfill(
                self.db_path,
                provider=provider,
                target_limit=1,
                profile_limit=1,
            )

        with self.connection() as conn:
            state = websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111", "251222"],
                provider=provider.name,
            )

        self.assertEqual(summary["status"], "ok")
        self.assertTrue(summary["planOnly"])
        self.assertEqual(summary["targetItemCount"], 2)
        self.assertEqual(summary["candidateProfileCount"], 2)
        self.assertEqual(summary["processedTargetItemIds"], ["251222"])
        self.assertEqual(summary["processedProfileCount"], 1)
        self.assertEqual(summary["plannedProfiles"], [{"name": "B"}])
        self.assertEqual(provider.fetched_candidates, [])
        self.assertEqual(state["cursor"]["targetOffset"], 1)
        self.assertEqual(state["cursor"]["profileOffset"], 1)
        self.assertEqual(state["lastRunStatus"], "idle")

    def test_observed_backfill_plan_only_reports_missing_stat_gap_summary(self):
        provider = FakeObservedProvider(
            targets=["251111", "251222"],
            candidates=[{"name": "A"}, {"name": "B"}],
            raises=AssertionError("plan-only must not fetch external profiles"),
        )
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            for index, (slot, class_key, spec_key, character_name) in enumerate(
                [
                    ("back", "mage", "frost", "Frostref"),
                    ("wrist", "monk", "mistweaver", "Mistref"),
                ]
            ):
                websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-missing-stats-251222-{slot}",
                        "itemId": "251222",
                        "slot": slot,
                        "variantKey": f"observed-251222-{slot}",
                        "label": f"Observed {slot}",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 289 + index,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                        "blockers": [],
                        "payload": {
                            "displayName": "缺属性测试装",
                            "classKeys": [class_key],
                            "specKeys": [spec_key],
                            "observedProfileRefs": [
                                {
                                    "sourceName": "Raider.IO",
                                    "region": "cn",
                                    "realmSlug": "test-realm",
                                    "characterName": character_name,
                                    "classKey": class_key,
                                    "specKey": spec_key,
                                    "profileUrl": f"https://raider.io/characters/cn/test-realm/{character_name}",
                                }
                            ],
                        },
                    },
                )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-ready-251111-back",
                    "itemId": "251111",
                    "slot": "back",
                    "variantKey": "observed-ready-251111-back",
                    "label": "Observed ready",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "blockers": [],
                    "payload": {
                        "displayName": "已补属性测试装",
                        "statSource": "simulationcraft",
                        "itemStats": [{"name": "intellect", "value": 1}],
                    },
                },
            )
            conn.commit()
        readonly_conn = sqlite3.connect(self.db_path)
        readonly_conn.execute("PRAGMA query_only=ON")
        self.addCleanup(readonly_conn.close)

        with patch.object(gear_observed_backfill, "connect_readonly_backfill_db", return_value=readonly_conn):
            summary = gear_observed_backfill.plan_gear_observed_backfill(
                self.db_path,
                provider=provider,
                target_limit=2,
                profile_limit=1,
            )

        gaps = summary["missingStatSummary"]
        self.assertEqual(gaps["totalMissingObservedVariantCount"], 2)
        self.assertEqual(gaps["plannedTargetItems"][0]["itemId"], "251222")
        self.assertEqual(gaps["plannedTargetItems"][0]["displayName"], "缺属性测试装")
        self.assertEqual(gaps["plannedTargetItems"][0]["missingObservedVariantCount"], 2)
        self.assertEqual(gaps["plannedTargetItems"][0]["slots"], ["back", "wrist"])
        self.assertEqual(gaps["plannedTargetItems"][0]["specs"], ["mage:frost", "monk:mistweaver"])
        self.assertEqual(gaps["plannedTargetItems"][0]["profileRefCount"], 2)
        self.assertEqual(gaps["topMissingObservedItems"][0]["itemId"], "251222")
        self.assertEqual(provider.fetched_candidates, [])

    def test_observed_backfill_plan_only_reports_source_gap_summary(self):
        provider = FakeObservedProvider(
            targets=["251111", "251222", "251333"],
            candidates=[{"name": "A"}, {"name": "B"}, {"name": "C"}],
            raises=AssertionError("plan-only must not fetch external profiles"),
        )
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-251222",
                    "itemId": "251222",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed gear",
                },
            )
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "simc-source-251222",
                    "itemId": "251222",
                    "sourceType": "simc_preset",
                    "sourceLabel": "SimulationCraft preset: MID1_Mage_Frost",
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-source-gap-251222-back",
                    "itemId": "251222",
                    "slot": "back",
                    "variantKey": "observed-251222-back",
                    "label": "Observed back",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {},
                    "status": "verified",
                    "blockers": [],
                    "payload": {
                        "displayName": "缺来源测试披风",
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "sources": [
                            {
                                "sourceType": "observed_profile",
                                "sourceLabel": "Raider.IO 实装观测",
                            },
                            {
                                "sourceType": "simc_preset",
                                "sourceLabel": "SimulationCraft preset: MID1_Mage_Frost",
                            },
                        ],
                    },
                },
            )
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-source-251333",
                    "itemId": "251333",
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "instanceId": "1209",
                    "encounterId": "1757",
                    "seasonRevision": "season-test",
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "official-source-251333-back",
                    "itemId": "251333",
                    "slot": "back",
                    "variantKey": "official-251333-back",
                    "label": "Official back",
                    "sourceType": "dungeon",
                    "difficultyKey": "mythic_plus",
                    "itemLevel": 289,
                    "simcOptions": {},
                    "status": "verified",
                    "blockers": [],
                    "payload": {
                        "displayName": "已补来源测试披风",
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )
            conn.commit()
        readonly_conn = sqlite3.connect(self.db_path)
        readonly_conn.execute("PRAGMA query_only=ON")
        self.addCleanup(readonly_conn.close)

        with patch.object(gear_observed_backfill, "connect_readonly_backfill_db", return_value=readonly_conn):
            summary = gear_observed_backfill.plan_gear_observed_backfill(
                self.db_path,
                provider=provider,
                target_limit=2,
                profile_limit=1,
            )

        gaps = summary["sourceGapSummary"]
        self.assertEqual(gaps["totalSourcePendingItemCount"], 1)
        self.assertEqual(gaps["targetSourcePendingItemCount"], 1)
        self.assertEqual(gaps["plannedTargetItems"][0]["itemId"], "251222")
        self.assertEqual(gaps["plannedTargetItems"][0]["displayName"], "缺来源测试披风")
        self.assertEqual(gaps["plannedTargetItems"][0]["sourcePendingVariantCount"], 1)
        self.assertEqual(gaps["plannedTargetItems"][0]["slots"], ["back"])
        self.assertEqual(gaps["plannedTargetItems"][0]["sourceTypes"], ["observed_profile", "simc_preset"])
        self.assertEqual(gaps["topSourcePendingItems"][0]["itemId"], "251222")
        self.assertEqual(provider.fetched_candidates, [])

    def test_raiderio_provider_includes_observed_variant_profile_refs_as_candidates(self):
        with self.connection() as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-268290",
                    "itemId": "268290",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO",
                },
            )
            websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-missing-stats-268290",
                    "itemId": "268290",
                    "slot": "finger1",
                    "variantKey": "observed-268290",
                    "label": "observed 268290",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {},
                    "status": "verified",
                    "blockers": [],
                    "payload": {
                        "displayName": "唤孢者的绽放指环",
                        "observedProfileRefs": [
                            {
                                "sourceName": "Raider.IO",
                                "sourceStatus": "synced",
                                "region": "cn",
                                "realmSlug": "isillien",
                                "characterName": "Observedone",
                                "classKey": "mage",
                                "specKey": "frost",
                                "profileUrl": "https://raider.io/characters/cn/isillien/Observedone",
                            }
                        ],
                    },
                },
            )
            conn.commit()

            candidates = gear_observed_backfill.RaiderIOObservedBackfillProvider().candidate_profiles(conn)

        self.assertTrue(
            any(
                candidate.get("name") == "Observedone"
                and candidate.get("realmSlug") == "isillien"
                and candidate.get("classKey") == "mage"
                and candidate.get("specKey") == "frost"
                for candidate in candidates
            ),
            candidates,
        )

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

    def test_observed_backfill_runner_does_not_promote_without_simc_stat_payload(self):
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
        self.assertEqual(summary["officialVariantsPromoted"], 0)
        promoted = [row for row in official_rows if row[0] == "251111" and row[2] == "verified"]
        partial = [row for row in official_rows if row[0] == "251222" and row[2] == "partial"]
        retained = [row for row in official_rows if row[0] == "251111" and row[2] == "partial"]
        self.assertEqual(promoted, [])
        self.assertEqual(len(retained), 1)
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

    def test_cli_plan_only_uses_backfill_planner(self):
        with patch.object(gear_observed_backfill, "plan_gear_observed_backfill") as planner:
            with patch.object(gear_observed_backfill, "run_gear_observed_backfill") as runner:
                planner.return_value = {"status": "ok", "provider": "raiderio", "planOnly": True}
                with patch("sys.stdout", new=StringIO()):
                    exit_code = gear_observed_backfill.main(
                        [
                            "--db",
                            str(self.db_path),
                            "--target-limit",
                            "3",
                            "--profile-limit",
                            "4",
                            "--plan-only",
                            "--json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        runner.assert_not_called()
        planner.assert_called_once()
        _, kwargs = planner.call_args
        self.assertEqual(kwargs["target_limit"], 3)
        self.assertEqual(kwargs["profile_limit"], 4)


if __name__ == "__main__":
    unittest.main()

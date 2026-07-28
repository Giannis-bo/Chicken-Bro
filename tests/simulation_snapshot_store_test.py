import copy
import json
import unittest

from server.gear_resolved_loadout import build_resolved_loadout
from server.simulation_snapshot import (
    build_simulation_snapshot,
    talent_profile_key,
)
from server.simulation_snapshot_store import (
    SimulationSnapshotIntegrityError,
    SimulationSnapshotStore,
)
from tests.gear_resolved_loadout_test import (
    TEMPLATE_HASH,
    exact_registry,
    resolver_snapshot,
)


class FakeDatabase:
    def __init__(self):
        self.loadouts = {}
        self.snapshots = {}
        self.results = {}
        self.statements = []


class FakeCursor:
    def __init__(self, database):
        self.database = database
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        self.database.statements.append(normalized)
        self.rows = []
        if "simulation_snapshot_loadout_insert" in normalized:
            self.database.loadouts.setdefault(params[0], tuple(params))
        elif "simulation_snapshot_loadout_load" in normalized:
            row = self.database.loadouts.get(params[0])
            self.rows = [row] if row else []
        elif "simulation_snapshot_result_load" in normalized:
            row = self.database.results.get(params[0])
            self.rows = [row] if row else []
        elif "simulation_snapshot_load" in normalized:
            row = self.database.snapshots.get(params[0])
            self.rows = [row] if row else []
        elif "simulation_snapshot_result_insert" in normalized:
            self.database.results.setdefault(params[0], tuple(params))
        elif "simulation_snapshot_insert" in normalized:
            self.database.snapshots.setdefault(params[0], tuple(params))

    def fetchone(self):
        row = self.rows[0] if self.rows else None
        self.rows = []
        return row


class FakeConnection:
    def __init__(self, database):
        self.database = database
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rolled_back = True
        else:
            self.committed = True
        return False

    def cursor(self):
        return FakeCursor(self.database)


def loadout():
    return build_resolved_loadout(
        resolver_snapshot=resolver_snapshot(),
        exact_registry=exact_registry(),
        template_scope="community",
        template_content_hash=TEMPLATE_HASH,
    )


def snapshot():
    lines = ["talents=CYQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"]
    return build_simulation_snapshot(
        resolved_loadout=loadout(),
        talent_profile_key=talent_profile_key(lines),
        talent_lines=lines,
        character_context={
            "classKey": "mage",
            "specKey": "arcane",
            "name": "store test",
            "race": "troll",
            "level": 90,
            "role": "spell",
            "position": "back",
        },
        scenario_options={
            "scenarioKey": "single",
            "fightStyle": "Patchwerk",
            "desiredTargets": 1,
            "maxTime": 300,
            "iterations": 1000,
            "varyCombatLength": "0.2",
            "calculateScaleFactors": 0,
        },
        preparation_lines=["optimal_raid=0"],
        compiler_revision="simc-profile-compiler-v1",
        simc_runtime_revision="simc-runtime-v1",
    )


class SimulationSnapshotStoreTest(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase()
        self.connection = FakeConnection(self.database)
        self.store = SimulationSnapshotStore(lambda: self.connection)

    def test_loadout_and_snapshot_seal_are_idempotent_and_append_only(self):
        first_loadout = self.store.seal_loadout(loadout())
        second_loadout = self.store.seal_loadout(copy.deepcopy(loadout()))
        first_snapshot = self.store.seal_snapshot(snapshot())
        second_snapshot = self.store.seal_snapshot(copy.deepcopy(snapshot()))

        self.assertEqual(first_loadout, second_loadout)
        self.assertEqual(first_snapshot, second_snapshot)
        self.assertEqual(len(self.database.loadouts), 1)
        self.assertEqual(len(self.database.snapshots), 1)
        joined = "\n".join(self.database.statements).upper()
        self.assertIn("ON CONFLICT DO NOTHING", joined)
        self.assertIn("LOADOUT_JSON::TEXT", joined)
        self.assertIn("SNAPSHOT_JSON::TEXT", joined)
        self.assertNotIn(" UPDATE ", f" {joined} ")
        self.assertNotIn(" DELETE ", f" {joined} ")

    def test_result_binding_is_additive_and_exactly_reloadable(self):
        self.store.seal_loadout(loadout())
        sealed = self.store.seal_snapshot(snapshot())
        result = {
            "resultIdentity": "simc-result:sha256:" + ("a" * 64),
            "status": "completed",
            "metrics": {"dps": 123456},
        }

        first = self.store.bind_result(sealed["simulationSnapshotKey"], result)
        second = self.store.bind_result(
            sealed["simulationSnapshotKey"],
            copy.deepcopy(result),
        )

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "executed")
        self.assertEqual(first["resultIdentity"], result["resultIdentity"])
        self.assertEqual(first["result"], result)
        self.assertEqual(len(self.database.results), 1)

    def test_tampered_sealed_snapshot_is_rejected_not_overwritten(self):
        self.store.seal_loadout(loadout())
        sealed = self.store.seal_snapshot(snapshot())
        key = sealed["simulationSnapshotKey"]
        stored = list(self.database.snapshots[key])
        payload = json.loads(stored[9])
        payload["canonicalSimcInput"] = "tampered\n"
        stored[9] = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.database.snapshots[key] = tuple(stored)

        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "sealed simulation snapshot integrity mismatch",
        ):
            self.store.seal_snapshot(copy.deepcopy(snapshot()))

        self.assertEqual(
            json.loads(self.database.snapshots[key][9])["canonicalSimcInput"],
            "tampered\n",
        )

    def test_blocked_snapshot_and_conflicting_result_are_rejected(self):
        blocked = snapshot()
        blocked["status"] = "blocked"
        blocked.pop("simulationSnapshotKey", None)

        with self.assertRaises(SimulationSnapshotIntegrityError):
            self.store.seal_snapshot(blocked)

        self.store.seal_loadout(loadout())
        sealed = self.store.seal_snapshot(snapshot())
        self.store.bind_result(
            sealed["simulationSnapshotKey"],
            {
                "resultIdentity": "simc-result:sha256:" + ("a" * 64),
                "status": "completed",
                "metrics": {"dps": 123456},
            },
        )
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "result binding conflict",
        ):
            self.store.bind_result(
                sealed["simulationSnapshotKey"],
                {
                    "resultIdentity": "simc-result:sha256:" + ("b" * 64),
                    "status": "completed",
                    "metrics": {"dps": 999999},
                },
            )


if __name__ == "__main__":
    unittest.main()

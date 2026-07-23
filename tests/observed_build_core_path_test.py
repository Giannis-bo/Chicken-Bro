import inspect
import json
import unittest

from server import (
    observed_build_projection,
    observed_build_registry,
    observed_build_store,
    observed_build_template_set,
)
from server.observed_build_projection import build_dependency_vector, build_projection
from server.observed_build_registry import build_observed_snapshot
from server.observed_build_store import ObservedBuildStore
from server.observed_build_template_set import build_template_set
from server.websim_payload import expected_hero_tree_triplets


def _json_value(value):
    return json.loads(value) if isinstance(value, str) else value


class ShadowRegistry:
    def __init__(self):
        self.snapshots = {}
        self.projections = {}
        self.template_sets = {}
        self.template_set_slots = {}
        self.pointer = None
        self.statements = []

    def connection(self):
        return ShadowConnection(self)

    def execute(self, statement, params):
        sql = " ".join(statement.split())
        self.statements.append(sql)
        if sql.startswith("INSERT INTO cache.observed_build_snapshots"):
            snapshot_id = params[0]
            if snapshot_id in self.snapshots:
                return None
            row = (_json_value(params[-2]), params[-1])
            self.snapshots[snapshot_id] = row
            return row
        if sql.startswith("SELECT snapshot_json, row_hash"):
            return self.snapshots.get(params[0])
        if sql.startswith("INSERT INTO cache.observed_build_projections"):
            projection_id = params[0]
            if projection_id in self.projections:
                return None
            row = (_json_value(params[-2]), params[-1])
            self.projections[projection_id] = row
            return row
        if sql.startswith("SELECT projection_json, row_hash"):
            return self.projections.get(params[0])
        if sql.startswith("INSERT INTO cache.observed_build_template_sets"):
            template_set_id = params[0]
            if template_set_id in self.template_sets:
                return None
            self.template_sets[template_set_id] = (
                _json_value(params[-2]),
                params[-1],
            )
            self.template_set_slots[template_set_id] = []
            return (template_set_id,)
        if sql.startswith(
            "INSERT INTO cache.observed_build_template_set_slots"
        ):
            self.template_set_slots[params[0]].append(
                (params[1], _json_value(params[-2]), params[-1])
            )
            return None
        if sql.startswith(
            "SELECT count(*) FROM cache.observed_build_template_set_slots"
        ):
            return (len(self.template_set_slots.get(params[0], [])),)
        if sql.startswith("SELECT template_set_json, row_hash"):
            return self.template_sets.get(params[0])
        if sql.startswith("SELECT slot_key, slot_json, row_hash"):
            return sorted(self.template_set_slots.get(params[0], []))
        if sql.startswith(
            "INSERT INTO cache.observed_build_template_set_pointer"
        ):
            if self.pointer is not None:
                return None
            scope, template_set_id, actor = params
            self.pointer = {
                "scope": scope,
                "generation": 1,
                "active": template_set_id,
                "rollback": None,
                "actor": actor,
            }
            return self.pointer_row()
        if sql.startswith(
            "UPDATE cache.observed_build_template_set_pointer"
        ):
            if "active_template_set_id = rollback_template_set_id" in sql:
                actor, scope, generation = params
                if (
                    self.pointer is None
                    or self.pointer["scope"] != scope
                    or self.pointer["generation"] != generation
                    or self.pointer["rollback"] is None
                ):
                    return None
                active = self.pointer["active"]
                self.pointer.update(
                    {
                        "generation": generation + 1,
                        "active": self.pointer["rollback"],
                        "rollback": active,
                        "actor": actor,
                    }
                )
                return self.pointer_row()
            template_set_id, actor, scope, generation = params
            if (
                self.pointer is None
                or self.pointer["scope"] != scope
                or self.pointer["generation"] != generation
            ):
                return None
            self.pointer.update(
                {
                    "generation": generation + 1,
                    "rollback": self.pointer["active"],
                    "active": template_set_id,
                    "actor": actor,
                }
            )
            return self.pointer_row()
        if sql == "SET TRANSACTION READ ONLY":
            return None
        raise AssertionError(f"unexpected shadow SQL: {sql}")

    def pointer_row(self):
        return (
            self.pointer["scope"],
            self.pointer["generation"],
            self.pointer["active"],
            self.pointer["rollback"],
            self.pointer["actor"],
            "2026-07-23T12:00:00+08:00",
        )


class ShadowConnection:
    def __init__(self, registry):
        self.registry = registry
        self.current = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self

    def execute(self, statement, params=None):
        self.current = self.registry.execute(statement, params)

    def fetchone(self):
        return self.current

    def fetchall(self):
        if self.current is None:
            return []
        return self.current if isinstance(self.current, list) else [self.current]


class ObservedBuildCorePathTest(unittest.TestCase):
    def slots(self):
        return [
            {
                "classKey": triplet.split(":")[0],
                "specKey": triplet.split(":")[1],
                "heroKey": triplet.split(":")[2],
                "scenarioKey": "mythic_plus",
            }
            for triplet in expected_hero_tree_triplets()
        ]

    def dependencies(self):
        return build_dependency_vector(
            season_revision="season-tww-3",
            talent_catalog_revision="talent-catalog-v7",
            gear_release_id="gear-release:sha256:" + "1" * 64,
            gear_rule_revision="gear-rules-v5",
            resolver_contract_revision="gear-resolver-v1",
            serializer_revision="simc-serializer-v3",
            simc_runtime_revision="simc-runtime-abc",
            selection_schema_revision="selection-intent-v1",
            projection_schema_revision="observed-build-projection-v1",
        )

    def snapshot(self, slot, player):
        return build_observed_snapshot(
            slot=slot,
            source={
                "sourceKey": "raiderio",
                "sourceIdentity": f"raiderio:cn|realm|{player}",
                "profileUrl": f"https://raider.io/characters/cn/realm/{player}",
                "region": "cn",
                "realm": "realm",
                "character": player,
            },
            ranking_evidence={"rank": 1, "score": 3800},
            talent_observation={
                "rawImportCode": player,
                "selectedNodes": [{"id": player, "rank": 1}],
            },
            gear_observation={
                "gearBySlot": {"head": {"itemId": f"item-{player}"}}
            },
            source_revision="raiderio-profile-v1",
        )

    def projection(self, snapshot, *, blocked=False):
        return build_projection(
            snapshot=snapshot,
            dependency_vector=self.dependencies(),
            talent_projection={
                "status": "blocked" if blocked else "verified"
            },
            gear_projection={
                "status": "verified",
                "selectionIntent": {"slots": {}},
            },
            profile_readiness={"status": "ready", "simcReady": True},
            problems=(
                [
                    {
                        "code": "talent_node_unmapped",
                        "stage": "talent_projection",
                        "message": "Observed talent node is not in the local catalog.",
                    }
                ]
                if blocked
                else []
            ),
        )

    def test_dormant_eighty_slot_flow_keeps_same_slot_lkg_and_rolls_back(self):
        shadow = ShadowRegistry()
        store = ObservedBuildStore(shadow.connection)
        slots = self.slots()
        candidates = {}
        for index, slot in enumerate(slots):
            snapshot = self.snapshot(slot, f"player-a-{index}")
            projection = self.projection(snapshot)
            store.seal_snapshot(snapshot)
            store.seal_projection(projection)
            candidates[projection["slotKey"]] = projection

        first_set = build_template_set(
            expected_slots=slots,
            candidates_by_slot=candidates,
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="run-1",
        )
        store.seal_template_set(first_set)
        first_pointer = store.compare_and_swap_pointer(
            "candidate-shadow",
            0,
            first_set["templateSetId"],
            "test",
        )

        changed_slot = slots[0]
        replacement = self.snapshot(changed_slot, "player-b-rank-1")
        blocked_projection = self.projection(replacement, blocked=True)
        store.seal_snapshot(replacement)
        store.seal_projection(blocked_projection)
        changed_candidates = dict(candidates)
        changed_candidates[blocked_projection["slotKey"]] = blocked_projection
        second_set = build_template_set(
            expected_slots=slots,
            candidates_by_slot=changed_candidates,
            active_set=first_set,
            dependency_vector=self.dependencies(),
            source_run_id="run-2",
        )
        store.seal_template_set(second_set)
        second_pointer = store.compare_and_swap_pointer(
            "candidate-shadow",
            1,
            second_set["templateSetId"],
            "test",
        )
        rollback_pointer = store.rollback_pointer(
            "candidate-shadow",
            2,
            "test",
        )

        self.assertEqual(first_pointer["generation"], 1)
        self.assertEqual(
            first_set["counts"],
            {"verified": 80, "stale_lkg": 0, "pending_collection": 0},
        )
        self.assertEqual(
            second_set["counts"],
            {"verified": 79, "stale_lkg": 1, "pending_collection": 0},
        )
        stale = next(
            entry
            for entry in second_set["entries"]
            if entry["status"] == "stale_lkg"
        )
        original = next(
            entry
            for entry in first_set["entries"]
            if entry["slotKey"] == stale["slotKey"]
        )
        self.assertEqual(stale["snapshotId"], original["snapshotId"])
        self.assertEqual(stale["projectionId"], original["projectionId"])
        self.assertEqual(second_pointer["generation"], 2)
        self.assertEqual(rollback_pointer["generation"], 3)
        self.assertEqual(
            rollback_pointer["activeTemplateSetId"],
            first_set["templateSetId"],
        )
        self.assertEqual(
            len(shadow.template_set_slots[first_set["templateSetId"]]),
            80,
        )
        self.assertEqual(
            len(shadow.template_set_slots[second_set["templateSetId"]]),
            80,
        )

    def test_new_production_core_has_no_live_or_legacy_runtime_dependency(self):
        source = "\n".join(
            inspect.getsource(module)
            for module in (
                observed_build_registry,
                observed_build_projection,
                observed_build_template_set,
                observed_build_store,
            )
        )
        forbidden = (
            "import requests",
            "import urllib",
            "import socket",
            "import subprocess",
            "SimulationCraft",
            "PostgresCacheStore",
            "GearReleaseStore",
            "gear_public_contract",
            "websim_active_manifest_pointer",
            "websim_release_registry",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()

import copy
import hashlib
import json
import unittest
from unittest import mock

from server.observed_build_projection import build_dependency_vector, build_projection
from server.observed_build_registry import (
    build_observed_snapshot,
    snapshot_check,
)
from server.observed_build_store import (
    ObservedBuildIntegrityError,
    ObservedBuildPointerConflict,
    ObservedBuildStore,
)
from server.observed_build_template_set import build_template_set
from server.websim_payload import expected_hero_tree_triplets


class FakeCursor:
    def __init__(self, responder):
        self.responder = responder
        self.statements = []
        self.params = []
        self.current = None
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        self.params.append(params)
        self.current = self.responder(normalized, params)
        if self.current is None:
            self.rowcount = 0
        elif isinstance(self.current, list):
            self.rowcount = len(self.current)
        else:
            self.rowcount = 1

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        if self.current is None:
            return []
        return self.current if isinstance(self.current, list) else [self.current]


class FakeConnection:
    def __init__(self, responder):
        self.cursor_instance = FakeCursor(responder)
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        return False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class ObservedBuildStoreTest(unittest.TestCase):
    @staticmethod
    def row_hash(value):
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    def slots(self):
        slots = []
        for triplet in expected_hero_tree_triplets():
            class_key, spec_key, hero_key = triplet.split(":")
            slots.append(
                {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": hero_key,
                    "scenarioKey": "mythic_plus",
                }
            )
        return slots

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

    def snapshot(self, slot=None, player="player-a"):
        slot = slot or self.slots()[0]
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
            talent_observation={"rawImportCode": player, "selectedNodes": [{"id": player, "rank": 1}]},
            gear_observation={"gearBySlot": {"head": {"itemId": f"item-{player}"}}},
            source_revision="raiderio-profile-v1",
        )

    def projection(self, slot=None, player="player-a"):
        observed = self.snapshot(slot, player)
        return build_projection(
            snapshot=observed,
            dependency_vector=self.dependencies(),
            talent_projection={"status": "verified"},
            gear_projection={"status": "verified", "selectionIntent": {"slots": {}}},
            profile_readiness={"status": "ready", "simcReady": True},
        )

    def template_set(self):
        candidates = {}
        for index, slot in enumerate(self.slots()):
            projection = self.projection(slot, f"player-{index}")
            candidates[projection["slotKey"]] = projection
        return build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot=candidates,
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="run-1",
        )

    def active_store(self, scope="candidate"):
        template_set = self.template_set()
        artifacts = {}
        for index, slot in enumerate(self.slots()):
            projection = self.projection(slot, f"player-{index}")
            artifacts[projection["slotKey"]] = {
                "snapshot": self.snapshot(slot, f"player-{index}"),
                "projection": projection,
            }
        child_rows = [
            (
                entry["slotKey"],
                entry,
                self.row_hash(entry),
            )
            for entry in template_set["entries"]
        ]
        pointer = (
            scope,
            3,
            template_set["templateSetId"],
            "template-set:sha256:" + "f" * 64,
            "sync-worker",
            "2026-07-23T12:00:00+00:00",
        )

        def responder(sql, params):
            if sql.startswith("SELECT scope, generation, active_template_set_id"):
                return pointer
            if sql.startswith("SELECT template_set_json, row_hash"):
                return (template_set, self.row_hash(template_set))
            if sql.startswith(
                "SELECT count(*) FROM cache.observed_build_template_set_slots"
            ):
                return (80,)
            if sql.startswith("SELECT slot_key, slot_json, row_hash"):
                return child_rows
            if "observed_build_active_records" in sql:
                rows = []
                for entry in template_set["entries"]:
                    slot = entry["slot"]
                    if "slot.class_key = %s" in sql and slot["classKey"] != params[1]:
                        continue
                    spec_index = 2 if "slot.class_key = %s" in sql else 1
                    if (
                        "slot.spec_key = %s" in sql
                        and slot["specKey"] != params[spec_index]
                    ):
                        continue
                    hero_index = (
                        1
                        + int("slot.class_key = %s" in sql)
                        + int("slot.spec_key = %s" in sql)
                    )
                    if (
                        "slot.hero_key = %s" in sql
                        and slot["heroKey"] != params[hero_index]
                    ):
                        continue
                    artifact = artifacts[entry["slotKey"]]
                    rows.append(
                        (
                            entry,
                            self.row_hash(entry),
                            artifact["snapshot"],
                            self.row_hash(artifact["snapshot"]),
                            artifact["projection"],
                            self.row_hash(artifact["projection"]),
                        )
                    )
                return rows
            return None

        connection = FakeConnection(responder)
        return ObservedBuildStore(lambda: connection), connection, template_set

    def test_snapshot_seal_inserts_once_and_reuses_matching_row(self):
        observed = self.snapshot()
        state = {"inserted": False, "row": None}

        def responder(sql, params):
            if sql.startswith("INSERT INTO cache.observed_build_snapshots"):
                if state["inserted"]:
                    return None
                state["inserted"] = True
                state["row"] = (params[-2], params[-1])
                return state["row"]
            if sql.startswith("SELECT snapshot_json, row_hash"):
                return state["row"]
            return None

        conn = FakeConnection(responder)
        store = ObservedBuildStore(lambda: conn)

        first = store.seal_snapshot(observed)
        second = store.seal_snapshot(observed)

        self.assertEqual(first, observed)
        self.assertEqual(second, observed)
        self.assertEqual(
            sum(sql.startswith("INSERT INTO cache.observed_build_snapshots") for sql in conn.cursor_instance.statements),
            2,
        )
        self.assertTrue(conn.committed)

    def test_snapshot_seal_rejects_same_id_with_different_row_hash(self):
        observed = self.snapshot()

        def responder(sql, _params):
            if sql.startswith("INSERT INTO cache.observed_build_snapshots"):
                return None
            if sql.startswith("SELECT snapshot_json, row_hash"):
                return (copy.deepcopy(observed), "sha256:" + "f" * 64)
            return None

        conn = FakeConnection(responder)
        with self.assertRaises(ObservedBuildIntegrityError):
            ObservedBuildStore(lambda: conn).seal_snapshot(observed)
        self.assertTrue(conn.rolled_back)

    def test_records_append_only_snapshot_check(self):
        observed = self.snapshot()
        check = snapshot_check(
            run_id="run-1",
            slot=observed["slot"],
            checked_at="2026-07-23T12:00:00+08:00",
            status="captured",
            snapshot_id=observed["snapshotId"],
        )
        conn = FakeConnection(
            lambda sql, _params: (7,)
            if sql.startswith("INSERT INTO ops.observed_build_snapshot_checks")
            else None
        )

        result = ObservedBuildStore(lambda: conn).record_snapshot_check(check)

        self.assertEqual(result["checkId"], 7)
        self.assertEqual(result["snapshotId"], observed["snapshotId"])
        self.assertTrue(conn.committed)

    def test_projection_seal_validates_and_reuses_matching_row(self):
        projection = self.projection()
        state = {"row": None}

        def responder(sql, params):
            if sql.startswith("INSERT INTO cache.observed_build_projections"):
                if state["row"] is None:
                    state["row"] = (params[-2], params[-1])
                    return state["row"]
                return None
            if sql.startswith("SELECT projection_json, row_hash"):
                return state["row"]
            return None

        conn = FakeConnection(responder)
        store = ObservedBuildStore(lambda: conn)

        self.assertEqual(store.seal_projection(projection), projection)
        self.assertEqual(store.seal_projection(projection), projection)
        insert_index = next(
            index
            for index, sql in enumerate(conn.cursor_instance.statements)
            if sql.startswith("INSERT INTO cache.observed_build_projections")
        )
        self.assertIn(
            "source_identity",
            conn.cursor_instance.statements[insert_index],
        )
        self.assertIn(
            projection["sourceIdentity"],
            conn.cursor_instance.params[insert_index],
        )

    def test_template_set_seal_writes_header_and_exactly_eighty_entries(self):
        template_set = self.template_set()
        child_rows = []

        def responder(sql, params):
            if sql.startswith("INSERT INTO cache.observed_build_template_sets"):
                return (params[0],)
            if sql.startswith("INSERT INTO cache.observed_build_template_set_slots"):
                child_rows.append((params[1], params[-2], params[-1]))
                return None
            if sql.startswith("SELECT count(*) FROM cache.observed_build_template_set_slots"):
                return (80,)
            if sql.startswith("SELECT slot_key, slot_json, row_hash"):
                return sorted(child_rows)
            return None

        conn = FakeConnection(responder)

        result = ObservedBuildStore(lambda: conn).seal_template_set(template_set)

        statements = conn.cursor_instance.statements
        self.assertEqual(result, template_set)
        self.assertEqual(
            sum(sql.startswith("INSERT INTO cache.observed_build_template_set_slots") for sql in statements),
            80,
        )
        self.assertIn(
            "SELECT count(*) FROM cache.observed_build_template_set_slots WHERE template_set_id = %s",
            statements,
        )
        slot_insert = next(
            sql
            for sql in statements
            if sql.startswith("INSERT INTO cache.observed_build_template_set_slots")
        )
        self.assertIn("source_identity", slot_insert)
        self.assertTrue(conn.committed)

    def test_template_set_reuses_same_content_from_a_later_source_run(self):
        first = self.template_set()
        second = copy.deepcopy(first)
        second["sourceRunId"] = "run-2"
        state = {"header": None, "children": []}

        def responder(sql, params):
            if sql.startswith("INSERT INTO cache.observed_build_template_sets"):
                if state["header"] is not None:
                    return None
                state["header"] = (params[-2], params[-1])
                return (params[0],)
            if sql.startswith("INSERT INTO cache.observed_build_template_set_slots"):
                state["children"].append((params[1], params[-2], params[-1]))
                return None
            if sql.startswith("SELECT template_set_json, row_hash"):
                return state["header"]
            if sql.startswith("SELECT count(*) FROM cache.observed_build_template_set_slots"):
                return (len(state["children"]),)
            if sql.startswith("SELECT slot_key, slot_json, row_hash"):
                return sorted(state["children"])
            return None

        store = ObservedBuildStore(lambda: FakeConnection(responder))

        self.assertEqual(store.seal_template_set(first), first)
        self.assertEqual(store.seal_template_set(second), first)

    def test_template_set_reuse_rejects_one_corrupted_child_row(self):
        template_set = self.template_set()
        state = {"header": None, "children": []}

        def responder(sql, params):
            if sql.startswith("INSERT INTO cache.observed_build_template_sets"):
                if state["header"] is not None:
                    return None
                state["header"] = (params[-2], params[-1])
                return (params[0],)
            if sql.startswith("INSERT INTO cache.observed_build_template_set_slots"):
                state["children"].append((params[1], params[-2], params[-1]))
                return None
            if sql.startswith("SELECT template_set_json, row_hash"):
                return state["header"]
            if sql.startswith("SELECT count(*) FROM cache.observed_build_template_set_slots"):
                return (len(state["children"]),)
            if sql.startswith("SELECT slot_key, slot_json, row_hash"):
                rows = sorted(state["children"])
                return [
                    (slot_key, slot_json, "sha256:" + "f" * 64)
                    if index == 0
                    else (slot_key, slot_json, row_hash)
                    for index, (slot_key, slot_json, row_hash) in enumerate(rows)
                ]
            return None

        store = ObservedBuildStore(lambda: FakeConnection(responder))
        with self.assertRaisesRegex(
            ObservedBuildIntegrityError,
            "slot rows failed integrity",
        ):
            store.seal_template_set(template_set)

    def test_template_set_load_revalidates_header_and_all_child_rows(self):
        template_set = self.template_set()
        state = {"header": None, "children": []}

        def responder(sql, params):
            if sql.startswith("INSERT INTO cache.observed_build_template_sets"):
                state["header"] = (params[-2], params[-1])
                return (params[0],)
            if sql.startswith("INSERT INTO cache.observed_build_template_set_slots"):
                state["children"].append((params[1], params[-2], params[-1]))
                return None
            if sql.startswith("SELECT template_set_json, row_hash"):
                return state["header"]
            if sql.startswith("SELECT count(*) FROM cache.observed_build_template_set_slots"):
                return (len(state["children"]),)
            if sql.startswith("SELECT slot_key, slot_json, row_hash"):
                return sorted(state["children"])
            return None

        store = ObservedBuildStore(lambda: FakeConnection(responder))
        store.seal_template_set(template_set)

        self.assertEqual(
            store.load_template_set(template_set["templateSetId"]),
            template_set,
        )

    def test_load_pointer_returns_bounded_scope_identity(self):
        store, connection, template_set = self.active_store()

        pointer = store.load_pointer("candidate")

        self.assertEqual(pointer["scope"], "candidate")
        self.assertEqual(pointer["generation"], 3)
        self.assertEqual(
            pointer["activeTemplateSetId"],
            template_set["templateSetId"],
        )
        self.assertEqual(
            connection.cursor_instance.statements[0],
            "SET TRANSACTION READ ONLY",
        )

    def test_active_records_join_pointer_set_slot_snapshot_and_projection(self):
        store, connection, _template_set = self.active_store()

        result = store.load_active_records(
            "candidate",
            class_key="mage",
            spec_key="frost",
        )

        self.assertEqual(result["pointer"]["scope"], "candidate")
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(
            result["records"][0]["snapshot"]["source"]["sourceIdentity"],
            result["records"][0]["projection"]["sourceIdentity"],
        )
        self.assertEqual(
            connection.cursor_instance.statements[0],
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        )
        self.assertFalse(
            any(
                statement.startswith(("INSERT ", "UPDATE ", "DELETE "))
                for statement in connection.cursor_instance.statements
            )
        )

    def test_exact_projection_must_belong_to_active_scope_and_spec(self):
        store, _connection, _template_set = self.active_store()

        with self.assertRaisesRegex(ObservedBuildIntegrityError, "not active"):
            store.load_active_projection(
                "candidate",
                "build-projection:sha256:" + "f" * 64,
                "mage",
                "frost",
            )

    def test_exact_projection_returns_active_shared_player_record(self):
        store, _connection, _template_set = self.active_store()
        active = store.load_active_records(
            "candidate",
            class_key="mage",
            spec_key="frost",
        )
        expected = active["records"][0]

        result = store.load_active_projection(
            "candidate",
            expected["projection"]["projectionId"],
            "mage",
            "frost",
        )

        self.assertEqual(result, expected)

    def test_latest_verified_projection_read_is_dependency_and_time_bounded(self):
        projection = self.projection()
        dependency_hash = projection["dependencyHash"]
        conn = FakeConnection(
            lambda sql, _params: [
                (
                    projection["slotKey"],
                    projection,
                    self.row_hash(projection),
                )
            ]
            if "observed_build_latest_verified_projections" in sql
            else None
        )

        result = ObservedBuildStore(
            lambda: conn
        ).load_latest_verified_projections(
            dependency_hash,
            "2026-07-23T00:00:00+00:00",
        )

        self.assertEqual(result, {projection["slotKey"]: projection})
        statement = conn.cursor_instance.statements[1]
        self.assertIn("projection.status = 'verified'", statement)
        self.assertIn("projection.importable IS TRUE", statement)
        self.assertIn("check.checked_at >= %s::timestamptz", statement)

    def test_health_summary_reports_lkg_without_disabling_active_records(self):
        store, _connection, template_set = self.active_store()
        template_set["counts"] = {
            "verified": 78,
            "stale_lkg": 2,
            "pending_collection": 0,
        }

        with mock.patch.object(
            store,
            "load_active_records",
            return_value={
                "pointer": {
                    "scope": "candidate",
                    "generation": 3,
                    "activeTemplateSetId": template_set["templateSetId"],
                    "updatedAt": "2026-07-23T12:00:00+00:00",
                },
                "templateSet": template_set,
                "records": [
                    {
                        "projection": {
                            "sourceIdentity": f"raiderio:cn|realm|player-{index}"
                        }
                    }
                    for index in range(80)
                ],
            },
        ):
            summary = store.health_summary("candidate")

        self.assertEqual(summary["status"], "partial")
        self.assertTrue(summary["active"])
        self.assertEqual(summary["counts"]["stale_lkg"], 2)
        self.assertEqual(summary["recordCount"], 80)

    def test_pointer_cas_is_monotonic_and_rejects_stale_generation(self):
        template_set = self.template_set()
        pointer_rows = iter(
            [
                (
                    "retail",
                    1,
                    template_set["templateSetId"],
                    None,
                    "tester",
                    "2026-07-23T12:00:00+08:00",
                ),
                None,
            ]
        )
        conn = FakeConnection(
            lambda sql, _params: next(pointer_rows)
            if (
                sql.startswith("INSERT INTO cache.observed_build_template_set_pointer")
                or sql.startswith("UPDATE cache.observed_build_template_set_pointer")
            )
            else None
        )
        store = ObservedBuildStore(lambda: conn)

        first = store.compare_and_swap_pointer(
            "retail",
            0,
            template_set["templateSetId"],
            "tester",
        )
        self.assertEqual(first["generation"], 1)

        with self.assertRaises(ObservedBuildPointerConflict):
            store.compare_and_swap_pointer(
                "retail",
                1,
                "template-set:sha256:" + "a" * 64,
                "tester",
            )

    def test_rollback_swaps_active_and_previous_without_rewriting_immutable_rows(self):
        active_id = "template-set:sha256:" + "a" * 64
        rollback_id = "template-set:sha256:" + "b" * 64
        conn = FakeConnection(
            lambda sql, _params: (
                "retail",
                3,
                rollback_id,
                active_id,
                "tester",
                "2026-07-23T12:00:00+08:00",
            )
            if sql.startswith("UPDATE cache.observed_build_template_set_pointer")
            else None
        )

        result = ObservedBuildStore(lambda: conn).rollback_pointer(
            "retail",
            2,
            "tester",
        )

        self.assertEqual(result["generation"], 3)
        self.assertEqual(result["activeTemplateSetId"], rollback_id)
        immutable_updates = [
            sql
            for sql in conn.cursor_instance.statements
            if sql.startswith("UPDATE cache.observed_build_")
            and "template_set_pointer" not in sql
        ]
        self.assertEqual(immutable_updates, [])


if __name__ == "__main__":
    unittest.main()

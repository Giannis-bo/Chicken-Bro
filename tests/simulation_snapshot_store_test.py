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
    active_v2_loadout_fixture,
    exact_registry,
    resolver_snapshot,
)
from tests.simulation_snapshot_test import (
    TALENT_KEY,
    TALENT_LINES,
    character_context,
    scenario,
    v2_snapshot_fixture,
)
from server.simulation_snapshot import build_simulation_snapshot_v2
from server.gear_canonical_kernel import canonical_json_bytes


class FakeDatabase:
    def __init__(self):
        self.loadouts = {}
        self.v2_loadouts = {}
        self.snapshots = {}
        self.v2_snapshots = {}
        self.results = {}
        self.documents = {}
        self.exact_authority_bundles = {}
        self.effect_aggregate_records = {}
        self.loadout_effect_authorities = {}
        self.loadout_effect_authority_records = {}
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
        if "exact_authority_revision_projection" in normalized:
            progression = json.loads(params[0])
            support = json.loads(params[1])
            envelope = json.loads(params[2])
            self.rows = [(
                progression["gearRuleRevision"],
                support["simcRuntimeRevision"],
                envelope["resolverRevision"],
            )]
        elif "exact_authority_document_load" in normalized:
            row = self.database.documents.get(params[0])
            self.rows = [row] if row else []
        elif "simulation_snapshot_effect_record_load" in normalized:
            row = self.database.documents.get(params[0])
            self.rows = [row] if row else []
        elif "exact_authority_bundle_load" in normalized:
            row = self.database.exact_authority_bundles.get(params[0])
            self.rows = [row] if row else []
        elif "exact_authority_effect_relation_load" in normalized:
            self.rows = list(self.database.effect_aggregate_records.get(params[0], ()))
        elif "simulation_snapshot_loadout_effect_authority_document_load" in normalized:
            row = self.database.loadout_effect_authorities.get(params[0])
            self.rows = [
                (row[0], row[1], row[2], True)
            ] if row else []
        elif "simulation_snapshot_loadout_effect_authority_relation_load" in normalized:
            self.rows = list(
                self.database.loadout_effect_authority_records.get(params[0], ())
            )
        elif "simulation_snapshot_loadout_effect_authority_parent_insert" in normalized:
            self.database.loadout_effect_authorities.setdefault(params[0], tuple(params))
        elif "simulation_snapshot_loadout_effect_authority_relation_insert" in normalized:
            rows = self.database.loadout_effect_authority_records.setdefault(params[0], [])
            if (params[1], params[2]) not in rows:
                rows.append((params[1], params[2]))
        elif "simulation_snapshot_loadout_v2_insert" in normalized:
            self.database.v2_loadouts.setdefault(params[0], tuple(params))
        elif "simulation_snapshot_loadout_v2_load" in normalized:
            row = self.database.v2_loadouts.get(params[0])
            self.rows = [row] if row else []
        elif "simulation_snapshot_v2_insert" in normalized:
            self.database.v2_snapshots.setdefault(params[0], tuple(params))
        elif "simulation_snapshot_v2_load" in normalized:
            row = self.database.v2_snapshots.get(params[0])
            self.rows = [row] if row else []
        elif "simulation_snapshot_loadout_insert" in normalized:
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

    def fetchall(self):
        rows = self.rows
        self.rows = []
        return rows


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


def active_v2_snapshot_fixture():
    resolver, authority, bundles, loadout_row = active_v2_loadout_fixture()
    eligibility = resolver["eligibilityContext"]
    snapshot_row = build_simulation_snapshot_v2(
        resolved_loadout=loadout_row,
        talent_profile_key=TALENT_KEY,
        talent_lines=TALENT_LINES,
        character_context=character_context(
            eligibility["classKey"], eligibility["specKey"],
        ),
        scenario_options=scenario(),
        preparation_lines=["optimal_raid=0"],
        compiler_revision="simc-profile-compiler-v2",
        simc_runtime_revision="simc-runtime-v2",
        resolver_snapshot=resolver,
        authority_bundles=bundles,
        loadout_effect_authority=authority,
    )
    return resolver, authority, bundles, loadout_row, snapshot_row


def seed_exact_authority_bundles(database, bundles):
    for bundle in bundles.values():
        documents = (
            bundle.exact_item,
            bundle.static_facts,
            bundle.progression,
            *bundle.effect_records,
            bundle.effect_support,
            bundle.envelope,
        )
        for document in documents:
            database.documents[document.content_key] = (
                document.content_key,
                document.document_kind,
                document.schema_revision,
                document.canonical_bytes,
                True,
            )
        database.exact_authority_bundles[bundle.envelope.content_key] = (
            bundle.envelope.content_key,
            bundle.exact_item.content_key,
            bundle.static_facts.content_key,
            bundle.progression.content_key,
            bundle.effect_support.content_key,
            "gear-rule-matrix-v1",
            "simc-runtime-v2",
            "resolver-v2",
        )
        database.effect_aggregate_records[bundle.effect_support.content_key] = [
            (ordinal, record.content_key)
            for ordinal, record in enumerate(bundle.effect_records)
        ]


def seed_loadout_effect_records(database, authority):
    payload = json.loads(authority.canonical_bytes)
    for record in payload["supportRecords"]:
        record_payload = dict(record)
        record_payload.pop("supportRecordKey")
        canonical_bytes = canonical_json_bytes(record_payload)
        database.documents[record["supportRecordKey"]] = (
            record["supportRecordKey"],
            "effect_record",
            "simc-item-effect-record-v1",
            canonical_bytes,
            True,
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

    def test_v2_round_trip_requires_the_verifier_context(self):
        resolver, bundles, loadout_row, snapshot_row = v2_snapshot_fixture()
        seed_exact_authority_bundles(self.database, bundles)

        sealed_loadout = self.store.seal_loadout(
            loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=bundles,
        )
        sealed_snapshot = self.store.seal_snapshot(
            snapshot_row,
            resolved_loadout=loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=bundles,
            compiler_revision="simc-profile-compiler-v2",
        )

        self.assertEqual(sealed_loadout, loadout_row)
        self.assertEqual(sealed_snapshot, snapshot_row)

    def test_v2_active_effect_round_trip_rehydrates_duplicate_relations(self):
        """Would fail if persistence deduplicated Task 4L relation occurrences."""
        resolver, authority, bundles, loadout_row, snapshot_row = (
            active_v2_snapshot_fixture()
        )
        seed_exact_authority_bundles(self.database, bundles)
        seed_loadout_effect_records(self.database, authority)

        sealed_loadout = self.store.seal_loadout(
            loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=bundles,
            loadout_effect_authority=authority,
        )
        sealed_snapshot = self.store.seal_snapshot(
            snapshot_row,
            resolved_loadout=loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=bundles,
            compiler_revision="simc-profile-compiler-v2",
            loadout_effect_authority=authority,
        )

        relation_rows = self.database.loadout_effect_authority_records[
            authority.content_key
        ]
        self.assertEqual(
            relation_rows,
            [(0, relation_rows[0][1]), (1, relation_rows[1][1]), (2, relation_rows[2][1])],
        )
        self.assertEqual(len({key for _, key in relation_rows}), 1)
        self.assertEqual(self.store.load_loadout(sealed_loadout["resolvedLoadoutKey"]), loadout_row)
        self.assertEqual(self.store.load_snapshot(sealed_snapshot["simulationSnapshotKey"]), snapshot_row)
        self.assertIn(
            "ORDER BY ordinal",
            "\n".join(self.database.statements),
        )

        relation_rows[1] = (3, relation_rows[1][1])
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "loadout effect authority relation order mismatch",
        ):
            self.store.load_loadout(sealed_loadout["resolvedLoadoutKey"])
        relation_rows[1] = (1, relation_rows[1][1])
        self.database.loadout_effect_authority_records[authority.content_key].pop()
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "loadout effect authority",
        ):
            self.store.load_loadout(sealed_loadout["resolvedLoadoutKey"])

    def test_v2_rejects_required_mismatched_and_oversized_replay_context(self):
        """Would fail if v2 fell back to canonical JSON or a lossy resolver copy."""
        resolver, bundles, loadout_row, _ = v2_snapshot_fixture()
        seed_exact_authority_bundles(self.database, bundles)
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "verifier context is required",
        ):
            self.store.seal_loadout(loadout_row)

        sealed = self.store.seal_loadout(
            loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=bundles,
        )
        stored = list(self.database.v2_loadouts[sealed["resolvedLoadoutKey"]])
        replay = json.loads(stored[-1])
        replay["resolvedSlots"]["head"]["itemId"] = "wrong-item"
        stored[-1] = json.dumps(replay, separators=(",", ":"), sort_keys=True)
        self.database.v2_loadouts[sealed["resolvedLoadoutKey"]] = tuple(stored)
        with self.assertRaises(SimulationSnapshotIntegrityError):
            self.store.load_loadout(sealed["resolvedLoadoutKey"])

        oversized = copy.deepcopy(resolver)
        oversized["setState"]["itemSetCounts"]["padding"] = "x" * 1048576
        oversized["v2EffectBoundary"]["setState"] = oversized["setState"]
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "replay context is invalid",
        ):
            self.store.seal_loadout(
                loadout_row,
                resolver_snapshot=oversized,
                authority_bundles=bundles,
            )

    def test_v2_rejects_lossy_python_values_before_canonicalization(self):
        """Tuples and custom values must not become v2 lists or strings."""
        resolver, authority, bundles, loadout_row, snapshot_row = (
            active_v2_snapshot_fixture()
        )

        tuple_loadout = copy.deepcopy(loadout_row)
        tuple_loadout["effectEvidenceByOccurrence"] = tuple(
            tuple_loadout["effectEvidenceByOccurrence"]
        )
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "native JSON values",
        ):
            self.store.seal_loadout(
                tuple_loadout,
                resolver_snapshot=resolver,
                authority_bundles=bundles,
                loadout_effect_authority=authority,
            )

        class CustomValue:
            pass

        custom_resolver = copy.deepcopy(resolver)
        custom_resolver["setState"]["itemSetCounts"]["custom"] = CustomValue()
        custom_resolver["v2EffectBoundary"]["setState"] = custom_resolver[
            "setState"
        ]
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "native JSON values",
        ):
            self.store.seal_loadout(
                loadout_row,
                resolver_snapshot=custom_resolver,
                authority_bundles=bundles,
                loadout_effect_authority=authority,
            )

        tuple_snapshot = copy.deepcopy(snapshot_row)
        tuple_snapshot["effectEvidenceByOccurrence"] = tuple(
            tuple_snapshot["effectEvidenceByOccurrence"]
        )
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "native JSON values",
        ):
            self.store.seal_snapshot(
                tuple_snapshot,
                resolved_loadout=loadout_row,
                resolver_snapshot=resolver,
                authority_bundles=bundles,
                compiler_revision="simc-profile-compiler-v2",
                loadout_effect_authority=authority,
            )

    def test_v2_rejects_loadout_effect_subject_substitution(self):
        """The saved occurrence must match the Task 4L subject at its ordinal."""
        resolver, authority, bundles, loadout_row, _ = active_v2_snapshot_fixture()
        seed_exact_authority_bundles(self.database, bundles)
        seed_loadout_effect_records(self.database, authority)
        sealed = self.store.seal_loadout(
            loadout_row,
            resolver_snapshot=resolver,
            authority_bundles=bundles,
            loadout_effect_authority=authority,
        )
        stored = list(self.database.v2_loadouts[sealed["resolvedLoadoutKey"]])
        tampered = json.loads(stored[7])
        occurrence = next(
            item for item in tampered["effectEvidenceByOccurrence"]
            if item["scope"] == "loadout"
        )
        occurrence["subjectKind"] = "substituted"
        stored[7] = json.dumps(tampered, separators=(",", ":"), sort_keys=True)
        stored[10] = json.dumps(
            tampered["effectEvidenceByOccurrence"],
            separators=(",", ":"),
            sort_keys=True,
        )
        self.database.v2_loadouts[sealed["resolvedLoadoutKey"]] = tuple(stored)
        with self.assertRaisesRegex(
            SimulationSnapshotIntegrityError,
            "sealed v2 ResolvedLoadout integrity mismatch",
        ):
            self.store.load_loadout(sealed["resolvedLoadoutKey"])


if __name__ == "__main__":
    unittest.main()

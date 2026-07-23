import copy
import io
import os
import unittest
import weakref
from contextlib import redirect_stdout
from unittest import mock

from server.observed_build_projection import build_dependency_vector, build_projection
from server.observed_build_registry import slot_key
from server import observed_build_sync
from server.observed_build_sync import run_observed_build_sync
from server.observed_build_template_set import build_template_set
from server.websim_payload import expected_hero_tree_triplets


class MemoryObservedBuildStore:
    def __init__(self, *, active_set=None, active_artifacts=None):
        self.active_set = copy.deepcopy(active_set)
        self.active_artifacts = copy.deepcopy(active_artifacts or {})
        self.snapshots = {}
        self.checks = []
        self.projections = {}
        self.template_sets = {}
        self.pointer = (
            {
                "scope": "candidate",
                "generation": 3,
                "activeTemplateSetId": active_set["templateSetId"],
                "rollbackTemplateSetId": "",
                "updatedBy": "fixture",
                "updatedAt": "2026-07-23T11:00:00Z",
            }
            if active_set
            else {}
        )
        self.sync_states = []

    def load_pointer(self, scope):
        if self.pointer and self.pointer["scope"] == scope:
            return copy.deepcopy(self.pointer)
        return {}

    def load_active_records(self, scope):
        pointer = self.load_pointer(scope)
        if not pointer:
            return {"pointer": {}, "templateSet": {}, "records": []}
        records = []
        for entry in self.active_set["entries"]:
            artifact = self.active_artifacts[entry["slotKey"]]
            records.append(
                {
                    "entry": copy.deepcopy(entry),
                    "snapshot": copy.deepcopy(artifact["snapshot"]),
                    "projection": copy.deepcopy(artifact["projection"]),
                }
            )
        return {
            "pointer": pointer,
            "templateSet": copy.deepcopy(self.active_set),
            "records": records,
        }

    def seal_snapshot(self, snapshot):
        self.snapshots[snapshot["snapshotId"]] = copy.deepcopy(snapshot)
        return copy.deepcopy(snapshot)

    def record_snapshot_check(self, check):
        self.checks.append(copy.deepcopy(check))
        return {**copy.deepcopy(check), "checkId": len(self.checks)}

    def seal_projection(self, projection):
        self.projections[projection["projectionId"]] = copy.deepcopy(projection)
        return copy.deepcopy(projection)

    def load_latest_verified_projections(self, dependency_hash, checked_since):
        return {}

    def seal_template_set(self, template_set):
        self.template_sets[template_set["templateSetId"]] = copy.deepcopy(
            template_set
        )
        return copy.deepcopy(template_set)

    def compare_and_swap_pointer(
        self,
        scope,
        expected_generation,
        template_set_id,
        actor,
    ):
        actual_generation = int(self.pointer.get("generation") or 0)
        if actual_generation != expected_generation:
            raise RuntimeError("pointer generation conflict")
        self.pointer = {
            "scope": scope,
            "generation": expected_generation + 1,
            "activeTemplateSetId": template_set_id,
            "rollbackTemplateSetId": self.pointer.get(
                "activeTemplateSetId",
                "",
            ),
            "updatedBy": actor,
            "updatedAt": "2026-07-23T13:00:00Z",
        }
        return copy.deepcopy(self.pointer)

    def save_sync_state(self, key, value, updated_at):
        self.sync_states.append((key, copy.deepcopy(value), updated_at))
        return {"ok": True, "key": key, "updatedAt": updated_at}


class ObservedBuildSyncTest(unittest.TestCase):
    def slots(self):
        return [
            {
                "classKey": class_key,
                "specKey": spec_key,
                "heroKey": hero_key,
                "scenarioKey": "mythic_plus",
            }
            for class_key, spec_key, hero_key in (
                triplet.split(":")
                for triplet in expected_hero_tree_triplets()
            )
        ]

    def test_postgres_compiler_prepares_one_shared_release_context_for_the_batch(self):
        dependencies = {
            "seasonRevision": "season-tww-3",
            "gearReleaseId": "gear-release-a",
        }
        snapshots = [
            {
                "snapshotId": "snapshot-a",
                "gearObservation": {
                    "gearItems": [{"itemId": 1, "slot": "head"}],
                },
            },
            {
                "snapshotId": "snapshot-b",
                "gearObservation": {
                    "gearItems": [{"itemId": 2, "slot": "neck"}],
                },
            },
        ]
        release_context = {"gearRelease": {"releaseId": "gear-release-a"}}
        compiler = observed_build_sync._PostgresCompiler(
            object(),
            dependencies,
            "simc-runtime-a",
        )

        with (
            mock.patch.object(
                observed_build_sync,
                "prepare_observed_gear_with_postgres",
            ) as backfill,
            mock.patch.object(
                observed_build_sync,
                "load_observed_gear_compile_context_with_postgres",
                return_value=release_context,
            ) as load_context,
            mock.patch.object(
                observed_build_sync,
                "compile_with_postgres",
                return_value={"status": "verified"},
            ) as compile_projection,
        ):
            compiler.prepare(snapshots)
            compiler(snapshots[0])
            compiler(snapshots[1])

        backfill.assert_called_once_with(compiler.cache_store, snapshots)
        load_context.assert_called_once_with(compiler.cache_store, snapshots)
        self.assertEqual(compile_projection.call_count, 2)
        for call in compile_projection.call_args_list:
            self.assertIs(
                call.kwargs["gear_release_context"],
                release_context,
            )

    def dependencies(self):
        return build_dependency_vector(
            season_revision="season-midnight-1",
            talent_catalog_revision="talent-catalog-v1",
            gear_release_id="gear-release:sha256:" + "1" * 64,
            gear_rule_revision="gear-rule-matrix-v1",
            resolver_contract_revision="gear-resolver-contract-v1",
            serializer_revision="websim-profile-compat-v1",
            simc_runtime_revision="simc-runtime-v1",
            selection_schema_revision="selection-intent-v1",
            projection_schema_revision="observed-build-projection-v2",
        )

    @staticmethod
    def _player_for(slot, suffix):
        return (
            f"{slot['classKey']}-{slot['specKey']}-"
            f"{slot['heroKey']}-{suffix}"
        )

    def payload(self, suffix="new"):
        templates = []
        profiles = []
        for index, slot in enumerate(self.slots()):
            player = self._player_for(slot, suffix)
            identity = f"raiderio:cn|realm-a|{player}"
            profile_url = (
                f"https://raider.io/characters/cn/realm-a/{player}"
            )
            templates.append(
                {
                    "id": f"template-{index}-{suffix}",
                    **slot,
                    "sourceKey": "raiderio",
                    "sourceUrl": profile_url,
                    "rawImportCode": f"IMPORT-{index}-{suffix}",
                    "playerId": player,
                    "maxKeyLevel": 20,
                    "status": "verified",
                    "payload": {
                        "raiderio": {
                            "sourceIdentity": identity,
                            "profileUrl": profile_url,
                            "characterName": player,
                            "realm": "realm-a",
                            "realmSlug": "realm-a",
                            "region": "cn",
                            "heroKey": slot["heroKey"],
                            "heroSubTreeId": f"hero-{slot['heroKey']}",
                            "loadoutSpecId": index + 1,
                            "loadout": [
                                {"traitId": 90000 + index, "rank": 1}
                            ],
                            "source": "run_detail",
                        },
                        "rioEvidence": {
                            "source": "raiderio_spec_ranking",
                            "score": 4000 - index,
                            "rank": index + 1,
                            "maxKeyLevel": 20,
                            "sourceUrl": profile_url,
                            "region": "cn",
                        },
                    },
                }
            )
            profiles.append(
                {
                    "sourceIdentity": identity,
                    "profileUrl": profile_url,
                    "name": player,
                    "realm": "realm-a",
                    "realmSlug": "realm-a",
                    "region": "cn",
                    "classKey": slot["classKey"],
                    "specKey": slot["specKey"],
                    "raceKey": "human",
                    "itemLevel": 710,
                    "gear": [
                        {
                            "slot": "head",
                            "itemId": 230000 + index,
                            "itemLevel": 710,
                        }
                    ],
                }
            )
        return {
            "sourceStatus": "synced",
            "seasonSlug": "season-midnight-1",
            "checkedAt": "2026-07-23T12:00:00Z",
            "communityTemplates": templates,
            "profiles": profiles,
        }

    def compiler(self, blocked_slot_key=""):
        dependencies = self.dependencies()

        def compile_snapshot(snapshot):
            blocked = slot_key(snapshot["slot"]) == blocked_slot_key
            return build_projection(
                snapshot=snapshot,
                dependency_vector=dependencies,
                talent_projection={
                    "status": "blocked" if blocked else "verified"
                },
                gear_projection={
                    "status": "blocked" if blocked else "verified",
                    "selectionIntent": {"slots": {}},
                },
                profile_readiness={
                    "status": "blocked" if blocked else "verified",
                    "simcReady": not blocked,
                },
                problems=(
                    [
                        {
                            "code": "fixture_mapping_failed",
                            "stage": "projection",
                        }
                    ]
                    if blocked
                    else []
                ),
            )

        compile_snapshot.dependency_vector = dependencies
        return compile_snapshot

    def active_store(self):
        compiler = self.compiler()
        artifacts = {}
        candidates = {}
        from server.observed_build_ingest import (
            select_distinct_snapshot_winners,
            snapshot_candidates_from_raiderio,
        )

        extracted = snapshot_candidates_from_raiderio(
            self.payload("active")
        )
        winners = select_distinct_snapshot_winners(
            extracted["candidatesBySlot"]
        )
        for key, snapshot in winners.items():
            projection = compiler(snapshot)
            candidates[key] = projection
            artifacts[key] = {
                "snapshot": snapshot,
                "projection": projection,
            }
        active_set = build_template_set(
            expected_slots=self.slots(),
            candidates_by_slot=candidates,
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="active-run",
        )
        return MemoryObservedBuildStore(
            active_set=active_set,
            active_artifacts=artifacts,
        )

    def test_partial_initial_run_seals_candidate_but_does_not_move_pointer(self):
        blocked_slot = slot_key(self.slots()[0])
        store = MemoryObservedBuildStore()

        result = run_observed_build_sync(
            store,
            scope="candidate",
            refresh_source=False,
            allow_promotion=True,
            source_fetcher=lambda: self.payload(),
            compiler=self.compiler(blocked_slot),
            checked_at="2026-07-23T12:00:00Z",
        )

        self.assertEqual(result["coverage"]["verified"], 79)
        self.assertEqual(result["coverage"]["pending_collection"], 1)
        self.assertEqual(result["promotion"]["action"], "blocked")
        self.assertEqual(result["pointerAfter"], {})
        self.assertEqual(len(store.template_sets), 1)
        self.assertEqual(store.sync_states[0][0], "observed_build_registry_sync")

    def test_existing_active_set_carries_one_lkg_and_updates_other_slots(self):
        blocked_slot = slot_key(self.slots()[0])
        store = self.active_store()
        pointer_before = copy.deepcopy(store.pointer)

        result = run_observed_build_sync(
            store,
            scope="candidate",
            refresh_source=False,
            allow_promotion=True,
            source_fetcher=lambda: self.payload(),
            compiler=self.compiler(blocked_slot),
            checked_at="2026-07-23T13:00:00Z",
        )

        self.assertEqual(result["coverage"]["verified"], 79)
        self.assertEqual(result["coverage"]["stale_lkg"], 1)
        self.assertEqual(result["coverage"]["pending_collection"], 0)
        self.assertEqual(result["coverage"]["gearCompleteSpecs"], 40)
        self.assertEqual(result["promotion"]["action"], "auto_promote")
        self.assertEqual(
            result["pointerAfter"]["generation"],
            pointer_before["generation"] + 1,
        )
        lkg = next(
            entry
            for entry in store.template_sets[
                result["candidateTemplateSetId"]
            ]["entries"]
            if entry["slotKey"] == blocked_slot
        )
        self.assertEqual(lkg["status"], "stale_lkg")
        self.assertEqual(
            lkg["projectionId"],
            store.active_set["entries"][0]["projectionId"],
        )

    def test_unchanged_snapshots_reuse_active_projections_without_compiling(self):
        store = self.active_store()

        class Compiler:
            dependency_vector = self.dependencies()

            def __init__(self):
                self.prepared = []
                self.calls = []

            def prepare(self, snapshots):
                self.prepared = list(snapshots)

            def __call__(self, snapshot):
                self.calls.append(snapshot)
                raise AssertionError("unchanged snapshot must reuse projection")

        compiler = Compiler()
        result = run_observed_build_sync(
            store,
            scope="candidate",
            refresh_source=False,
            allow_promotion=True,
            source_fetcher=lambda: self.payload("active"),
            compiler=compiler,
            checked_at="2026-07-23T13:00:00Z",
        )

        self.assertEqual(result["promotion"]["action"], "no_op")
        self.assertEqual(compiler.prepared, [])
        self.assertEqual(compiler.calls, [])
        self.assertEqual(store.projections, {})

    def test_source_payload_is_released_before_batch_gear_preparation(self):
        store = MemoryObservedBuildStore()
        payload_refs = []
        test_case = self

        class TrackedPayload(dict):
            pass

        class Compiler:
            dependency_vector = test_case.dependencies()

            def prepare(self, _snapshots):
                test_case.assertIsNone(payload_refs[0]())

            def __call__(self, snapshot):
                return test_case.compiler()(snapshot)

        def source_fetcher():
            payload = TrackedPayload(self.payload())
            payload_refs.append(weakref.ref(payload))
            return payload

        result = run_observed_build_sync(
            store,
            scope="candidate",
            refresh_source=False,
            allow_promotion=False,
            source_fetcher=source_fetcher,
            compiler=Compiler(),
            checked_at="2026-07-23T13:00:00Z",
        )

        self.assertEqual(result["coverage"]["verified"], 80)

    def test_audit_mode_performs_no_writes(self):
        store = self.active_store()

        result = run_observed_build_sync(
            store,
            scope="candidate",
            refresh_source=False,
            allow_promotion=False,
            source_fetcher=None,
            compiler=None,
            checked_at="2026-07-23T13:00:00Z",
            audit=True,
        )

        self.assertEqual(result["sourceStatus"], "audit")
        self.assertEqual(result["pointerAfter"], result["pointerBefore"])
        self.assertEqual(store.snapshots, {})
        self.assertEqual(store.checks, [])
        self.assertEqual(store.projections, {})
        self.assertEqual(store.template_sets, {})
        self.assertEqual(store.sync_states, [])

    def test_cli_rejects_mutating_audit_and_ungated_retail_cutover(self):
        with self.assertRaises(SystemExit):
            observed_build_sync.main(
                ["--scope", "candidate", "--audit", "--refresh-source"]
            )
        with mock.patch.dict(
            os.environ,
            {"WOW_OBSERVED_BUILD_RETAIL_CUTOVER": ""},
            clear=False,
        ), self.assertRaises(SystemExit):
            observed_build_sync.main(
                ["--scope", "retail", "--promote"]
            )

    def test_scheduled_cli_allows_only_observed_only_update_after_activation(self):
        class Registry:
            def load_pointer(self, scope):
                return {
                    "scope": scope,
                    "generation": 2,
                    "activeTemplateSetId": "template-set:sha256:" + "a" * 64,
                }

        class CacheStore:
            _observed_build_store = Registry()

            def get_raiderio_payload(self):
                return {}

        cache_store = CacheStore()
        expected_result = {
            "schemaRevision": "observed-build-registry-sync-v1",
            "promotion": {"action": "auto_promote"},
        }
        with mock.patch.object(
            observed_build_sync,
            "cache_store_from_env",
            return_value=cache_store,
        ), mock.patch.object(
            observed_build_sync,
            "_current_simc_runtime_revision",
            return_value="simc-r1",
        ), mock.patch.object(
            observed_build_sync,
            "_current_dependency_vector",
            return_value=self.dependencies(),
        ), mock.patch.object(
            observed_build_sync,
            "run_observed_build_sync",
            return_value=expected_result,
        ) as run, redirect_stdout(io.StringIO()):
            exit_code = observed_build_sync.main(
                ["--scope", "candidate", "--json"]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(run.call_args.kwargs["allow_promotion"])
        self.assertFalse(
            run.call_args.kwargs["allow_controlled_cutover"]
        )


if __name__ == "__main__":
    unittest.main()

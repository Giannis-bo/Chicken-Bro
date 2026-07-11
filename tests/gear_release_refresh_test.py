import contextlib
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from server import gear_release
from server.gear_release_refresh import (
    build_staging_candidates,
    classify_gear_change,
    classify_refresh_risk,
    coverage_regressions,
    PostgresRefreshLease,
    run_release_refresh,
)
from server.gear_release_store import canonical_row_hash


DEPENDENCIES = {
    "gearRuleRevision": "rules-v1",
    "resolverContractRevision": "resolver-v1",
    "serializerRevision": "serializer-v1",
    "simcRuntimeRevision": "simc-v1",
    "statPolicyRevision": "stats-v1",
    "selectionSchemaRevision": "intent-v1",
    "capabilityRevision": "capability-v1",
}


def release_pair(suffix="active", *, gear=None):
    gear_release_row = gear or gear_release.build_release(
        release_kind="gear",
        season_revision="season-17",
        schema_revision="gear-release-v1",
        content={"snapshotHash": f"gear-{suffix}"},
        dependency_revisions=DEPENDENCIES,
        release_status="validated",
        source={"sourceRevision": "scheduled-refresh-v1"},
    )
    community = gear_release.build_release(
        release_kind="community",
        season_revision="season-17",
        schema_revision="community-release-v1",
        content={"rowsHash": f"community-{suffix}"},
        dependency_revisions=DEPENDENCIES,
        release_status="validated",
        source={"sourceRevision": "scheduled-refresh-v1"},
        validated_against_release_id=gear_release_row["releaseId"],
    )
    return gear_release_row, community


def winner(template_id="observed-a", class_key="mage", spec_key="arcane"):
    return {
        "templateId": template_id,
        "classKey": class_key,
        "specKey": spec_key,
        "role": "winner",
        "problems": [],
    }


class FakeStore:
    def __init__(self):
        active_gear, active_community = release_pair("active")
        self.binding = {
            "pointerMode": "active",
            "formalActiveManifest": True,
            "generation": 9,
            "manifestRevision": "season-manifest:active",
            "manifest": {
                "seasonRevision": "season-17",
                "talentCatalogRevision": "talents-v1",
                "dependencyRevisions": dict(DEPENDENCIES),
            },
            "gearRelease": active_gear,
            "communityRelease": active_community,
        }
        self.events = []
        self.sealed_manifests = []
        self.promotions = []

    def load_active_manifest_binding(self):
        return self.binding

    def record_refresh_event(self, event_type, event, *, release_id="", manifest_revision=""):
        self.events.append({
            "eventType": event_type,
            "event": event,
            "releaseId": release_id,
            "manifestRevision": manifest_revision,
        })

    def seal_manifest(self, manifest):
        self.sealed_manifests.append(manifest)
        return {"status": "inserted", "manifestRevision": manifest["manifestRevision"]}

    def seal_manifest_and_compare_and_swap_pointer(self, manifest, command, *, updated_by):
        self.promotions.append({"manifest": manifest, "command": command, "updatedBy": updated_by})
        return {
            "pointerMode": "active",
            "generation": command["expectedGeneration"] + 1,
            "manifestRevision": manifest["manifestRevision"],
        }


@contextlib.contextmanager
def lease(acquired=True):
    yield acquired


def candidate_bundle(store, *, risk_class="same_gear_community", rows=None):
    candidate_gear = store.binding["gearRelease"]
    _unused, candidate_community = release_pair("candidate", gear=candidate_gear)
    return {
        "gearRelease": candidate_gear,
        "communityRelease": candidate_community,
        "gearSeal": {"status": "reused", "releaseId": candidate_gear["releaseId"]},
        "communitySeal": {"status": "inserted", "releaseId": candidate_community["releaseId"]},
        "riskClass": risk_class,
        "activeWinners": [winner()],
        "candidateRows": rows if rows is not None else [winner()],
        "counts": {"winner": 1, "standby": 0, "rejected": 0, "empty": 0},
    }


def passing_shadow(status="pass", expected_count=1):
    return {
        "status": status,
        "report": {"status": status, "blockers": []},
        "blockers": [],
        "specResults": [{"classKey": "mage", "specKey": "arcane", "status": "pass"}] * expected_count,
    }


class GearReleaseRefreshPolicyTest(unittest.TestCase):
    def test_classify_gear_change_reports_unchanged_additive_and_high_risk(self):
        item = {"itemId": "1", "name": "A"}
        variant = {"variantId": "v1", "itemId": "1", "variantKey": "base"}
        active = {
            "items": {"1": canonical_row_hash(item)},
            "sources": {},
            "variants": {"v1": canonical_row_hash(variant)},
            "options": {},
        }
        same = {"items": [item], "sources": [], "variants": [variant], "options": []}
        self.assertEqual(classify_gear_change(active, same)["riskClass"], "same_gear_community")

        additive = {**same, "items": [item, {"itemId": "2", "name": "B"}]}
        additive_result = classify_gear_change(active, additive)
        self.assertEqual(additive_result["riskClass"], "low_risk_additive_gear")
        self.assertEqual(additive_result["addedCounts"]["items"], 1)

        changed = {**same, "items": [{"itemId": "1", "name": "Changed"}]}
        changed_result = classify_gear_change(active, changed)
        self.assertEqual(changed_result["riskClass"], "high_risk_gear")
        self.assertEqual(changed_result["changedCounts"]["items"], 1)

    def test_coverage_regression_blocks_missing_still_legal_active_winner(self):
        regressions = coverage_regressions([winner()], [])
        self.assertEqual(len(regressions), 1)
        self.assertEqual(regressions[0]["code"], "ACTIVE_LEGAL_WINNER_LOST")

    def test_newly_expired_active_winner_can_become_explicit_empty(self):
        rejected = {
            **winner(),
            "role": "rejected",
            "problems": [{"code": "COMMUNITY_SOURCE_STALE"}],
        }
        self.assertEqual(coverage_regressions([winner()], [rejected]), [])

    def test_dependency_change_forces_controlled_risk_before_gear_risk(self):
        active = dict(DEPENDENCIES)
        candidate = {**DEPENDENCIES, "capabilityRevision": "capability-v2"}
        self.assertEqual(
            classify_refresh_risk("same_gear_community", active, candidate, season_changed=False),
            "capability_change",
        )
        self.assertEqual(
            classify_refresh_risk("low_risk_additive_gear", active, active, season_changed=True),
            "new_season",
        )

    def test_actual_candidate_builder_seals_inactive_pair_before_returning(self):
        store = FakeStore()
        item = {"itemId": "1", "name": "A"}
        snapshot = {"items": [item], "sources": [], "variants": [], "options": []}
        store.row_hashes = {
            "items": {"1": canonical_row_hash(item)},
            "sources": {},
            "variants": {},
            "options": {},
        }
        store.gear_seals = []
        store.community_seals = []

        def get_hashes(_release_id):
            return store.row_hashes

        def seal_gear(release, payload, **_kwargs):
            store.gear_seals.append((release, payload))
            return {"status": "reused", "releaseId": release["releaseId"]}

        def load_community(_gear_id, _community_id):
            return {"winners": [winner()]}

        def seal_community(release, rows, **_kwargs):
            store.community_seals.append((release, rows))
            return {"status": "inserted", "releaseId": release["releaseId"]}

        store.get_gear_release_row_hashes = get_hashes
        store.seal_gear_release = seal_gear
        store.load_community_release = load_community
        store.seal_community_release = seal_community
        candidate_gear = store.binding["gearRelease"]
        _unused, candidate_community = release_pair("candidate", gear=candidate_gear)

        result = build_staging_candidates(
            store,
            active_binding=store.binding,
            expected_specs=[("mage", "arcane")],
            dependency_revisions=DEPENDENCIES,
            now="2026-07-11T12:00:00+00:00",
            gear_preparer=lambda *_args, **_kwargs: {
                "release": candidate_gear,
                "snapshot": snapshot,
                "gate": {"status": "validated"},
            },
            community_preparer=lambda *_args, **_kwargs: {
                "release": candidate_community,
                "rows": [winner()],
                "election": {"status": "validated"},
                "gate": {"status": "validated"},
            },
        )

        self.assertEqual(result["riskClass"], "same_gear_community")
        self.assertEqual(result["gearSeal"]["status"], "reused")
        self.assertEqual(result["communitySeal"]["status"], "inserted")
        self.assertEqual(result["counts"], {"winner": 1, "standby": 0, "rejected": 0, "empty": 0})
        self.assertEqual(len(store.gear_seals), 1)
        self.assertEqual(len(store.community_seals), 1)

    def test_same_gear_full_pass_auto_promotes_after_candidate_and_manifest(self):
        store = FakeStore()
        result = run_release_refresh(
            store,
            expected_specs=[("mage", "arcane")],
            dependency_revisions=DEPENDENCIES,
            now="2026-07-11T12:00:00+00:00",
            updated_by="phase4e-test",
            lease=lease(),
            candidate_builder=lambda *_args, **_kwargs: candidate_bundle(store),
            shadow_runner=lambda **_kwargs: passing_shadow(),
        )

        self.assertEqual(result["status"], "promoted")
        self.assertEqual(result["decision"]["decision"], "auto_promote")
        self.assertEqual(len(store.promotions), 1)
        self.assertEqual(store.promotions[0]["command"]["expectedGeneration"], 9)
        self.assertEqual(store.events[0]["eventType"], "gear_release_refresh_started")
        self.assertEqual(store.events[-1]["eventType"], "gear_release_refresh_completed")

    def test_missing_still_legal_winner_blocks_and_preserves_pointer(self):
        store = FakeStore()
        result = run_release_refresh(
            store,
            expected_specs=[("mage", "arcane")],
            dependency_revisions=DEPENDENCIES,
            now="2026-07-11T12:00:00+00:00",
            updated_by="phase4e-test",
            lease=lease(),
            candidate_builder=lambda *_args, **_kwargs: candidate_bundle(store, rows=[]),
            shadow_runner=lambda **_kwargs: passing_shadow("degraded"),
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["decision"]["blockers"][-1]["code"], "LEGAL_WINNER_COVERAGE_REGRESSION")
        self.assertEqual(store.promotions, [])
        self.assertEqual(len(store.sealed_manifests), 1)

    def test_controlled_risk_seals_candidate_manifest_but_requires_manual_cutover(self):
        store = FakeStore()
        result = run_release_refresh(
            store,
            expected_specs=[("mage", "arcane")],
            dependency_revisions=DEPENDENCIES,
            now="2026-07-11T12:00:00+00:00",
            updated_by="phase4e-test",
            lease=lease(),
            candidate_builder=lambda *_args, **_kwargs: candidate_bundle(store, risk_class="capability_change"),
            shadow_runner=lambda **_kwargs: passing_shadow(),
        )

        self.assertEqual(result["status"], "manual_required")
        self.assertTrue(result["decision"]["controlledCutover"])
        self.assertEqual(store.promotions, [])
        self.assertEqual(len(store.sealed_manifests), 1)

    def test_lease_conflict_records_bounded_event_without_building(self):
        store = FakeStore()
        builds = []
        result = run_release_refresh(
            store,
            expected_specs=[("mage", "arcane")],
            dependency_revisions=DEPENDENCIES,
            now="2026-07-11T12:00:00+00:00",
            updated_by="phase4e-test",
            lease=lease(False),
            candidate_builder=lambda *_args, **_kwargs: builds.append(True),
            shadow_runner=lambda **_kwargs: passing_shadow(),
        )

        self.assertEqual(result["status"], "lease_conflict")
        self.assertEqual(builds, [])
        self.assertEqual(store.events[-1]["eventType"], "gear_release_refresh_lease_conflict")

    def test_failure_preserves_pointer_and_does_not_expose_exception_text(self):
        store = FakeStore()

        def fail(*_args, **_kwargs):
            raise RuntimeError("postgresql://secret@host/db raw traceback")

        result = run_release_refresh(
            store,
            expected_specs=[("mage", "arcane")],
            dependency_revisions=DEPENDENCIES,
            now="2026-07-11T12:00:00+00:00",
            updated_by="phase4e-test",
            lease=lease(),
            candidate_builder=fail,
            shadow_runner=lambda **_kwargs: passing_shadow(),
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["problems"][0]["code"], "REFRESH_EXECUTION_FAILED")
        self.assertNotIn("secret", str(result))
        self.assertEqual(store.promotions, [])
        self.assertEqual(store.events[-1]["eventType"], "gear_release_refresh_failed")

    def test_postgres_lease_uses_nonblocking_advisory_lock_and_releases_session(self):
        class Cursor:
            def __init__(self):
                self.statements = []
                self.rows = [(True,)]

            def execute(self, statement, params=None):
                self.statements.append((" ".join(statement.split()), tuple(params or ())))

            def fetchone(self):
                return self.rows.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class Connection:
            def __init__(self):
                self.cursor_instance = Cursor()
                self.closed = False

            def cursor(self):
                return self.cursor_instance

            def close(self):
                self.closed = True

        conn = Connection()
        with PostgresRefreshLease(lambda: conn) as acquired:
            self.assertTrue(acquired)
        sql = "\n".join(statement for statement, _params in conn.cursor_instance.statements)
        self.assertIn("pg_try_advisory_lock", sql)
        self.assertIn("pg_advisory_unlock", sql)
        self.assertTrue(conn.closed)

    def test_cli_returns_nonzero_only_for_execution_failure(self):
        from server import gear_release_refresh

        output = io.StringIO()
        with patch.object(gear_release_refresh, "_run_from_environment", return_value={"status": "blocked"}), redirect_stdout(output):
            self.assertEqual(gear_release_refresh.main(["--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")

        output = io.StringIO()
        with patch.object(gear_release_refresh, "_run_from_environment", return_value={"status": "failed"}), redirect_stdout(output):
            self.assertEqual(gear_release_refresh.main(["--json"]), 1)


if __name__ == "__main__":
    unittest.main()

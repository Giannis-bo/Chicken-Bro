import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.gear_resolved_loadout_test import (
    TEMPLATE_AUTHORITY_IDENTITY,
    TEMPLATE_HASH,
    exact_registry,
    resolver_snapshot,
)
from tests.simulation_snapshot_store_test import snapshot


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "gear-resolved-snapshot.py"
)
SPEC = importlib.util.spec_from_file_location(
    "gear_resolved_snapshot_script",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def template(content_hash, marker):
    return {
        "templateContentHash": content_hash,
        "classKey": "mage",
        "specKey": "arcane",
        "importStatus": "verified",
        "templateAuthorityIdentity": TEMPLATE_AUTHORITY_IDENTITY,
        "selectionIntent": {
            "schemaRevision": "selection-intent-v1",
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
                "level": 90,
            },
            "marker": marker,
        },
        "gearItems": [],
    }


class GearResolvedSnapshotShadowTest(unittest.TestCase):
    def test_ready_expectations_are_derived_from_sealed_exact_references(self):
        report = MODULE.run_shadow(
            templates=[template(TEMPLATE_HASH, "ready")],
            exact_registry=exact_registry(),
            resolver_reader=lambda _template: resolver_snapshot(),
            snapshot_reader=lambda _loadout, _template: snapshot(),
            seal_loadout=lambda value: value,
            seal_snapshot=lambda value: value,
            pointer_before={"generation": 32},
            pointer_after_reader=lambda: {"generation": 32},
            observed_at="2026-07-29T00:00:00Z",
            expected_template_count=1,
            expected_spec_count=1,
            expected_supported_spec_count=1,
            expected_unsupported_spec_count=0,
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(
            report["summary"]["expectationSource"],
            "sealed_exact_registry",
        )
        self.assertEqual(
            report["summary"]["expectedReadyLoadoutCount"],
            1,
        )
        self.assertEqual(
            report["summary"]["expectedReadySnapshotCount"],
            1,
        )
        self.assertEqual(
            report["summary"]["expectedUnsupportedSnapshotCount"],
            0,
        )

    def test_public_import_repeats_only_verified_results(self):
        class FakeReader:
            def __init__(self, rows):
                self.rows = list(rows)
                self.calls = 0

            def import_template(self, _template):
                result = self.rows[self.calls]
                self.calls += 1
                return result

        blocked_reader = FakeReader([
            {
                "importStatus": "blocked",
                "importProblemCodes": ["template_import_blocked"],
            }
        ])
        verified = {
            "importStatus": "verified",
            "resolvedSnapshot": {"status": "verified"},
        }
        verified_reader = FakeReader([verified, copy.deepcopy(verified)])

        blocked = MODULE.verify_public_import(blocked_reader, {})
        repeated = MODULE.verify_public_import(verified_reader, {})

        self.assertEqual(blocked["importStatus"], "blocked")
        self.assertEqual(blocked_reader.calls, 1)
        self.assertEqual(repeated, verified)
        self.assertEqual(verified_reader.calls, 2)

    def test_public_template_discovery_uses_browse_ids_not_audit_hashes(self):
        reader = object.__new__(MODULE.ProfileReader)
        reader.browse = {}
        reader._request = lambda _method, _path, _payload=None: {
            "communityTemplates": [
                {
                    "id": "public-a",
                    "classKey": "mage",
                    "specKey": "frost",
                },
                {
                    "id": "",
                    "classKey": "mage",
                    "specKey": "frost",
                },
                {
                    "id": "wrong-spec",
                    "classKey": "mage",
                    "specKey": "arcane",
                },
            ]
        }

        templates = reader.templates_for_spec("mage", "frost")

        self.assertEqual(
            [row["id"] for row in templates],
            ["public-a"],
        )

    def test_verified_import_without_server_template_identity_fails_closed(self):
        reader = object.__new__(MODULE.ProfileReader)
        reader._browse_spec = lambda _class_key, _spec_key: {
            "manifestRevision": "season-manifest:sha256:" + ("a" * 64),
            "communityTemplates": [{
                "id": "public-a",
                "classKey": "mage",
                "specKey": "frost",
            }],
        }
        reader._request = lambda *_args, **_kwargs: {
            "status": "verified",
            "data": {
                "status": "verified",
                "template": {},
                "resolvedSnapshot": {"status": "verified"},
            },
            "problems": [],
        }

        imported = reader.import_template({
            "id": "public-a",
            "classKey": "mage",
            "specKey": "frost",
        })

        self.assertEqual(imported["importStatus"], "blocked")
        self.assertEqual(
            imported["importProblemCodes"],
            ["RESOLVED_SHADOW_TEMPLATE_AUTHORITY_IDENTITY_MISSING"],
        )

    def test_shadow_forwards_server_template_identity_to_exact_matcher(self):
        with patch.object(
            MODULE,
            "build_resolved_loadout_from_registry",
            return_value={
                "status": "blocked",
                "problemCodes": ["LOADOUT_TEST_BLOCKED"],
            },
        ) as matcher:
            MODULE.run_shadow(
                templates=[template(TEMPLATE_HASH, "known")],
                exact_registry=exact_registry(),
                resolver_reader=lambda _template: resolver_snapshot(),
                snapshot_reader=lambda _loadout, _template: snapshot(),
                seal_loadout=lambda value: value,
                seal_snapshot=lambda value: value,
                pointer_before={"generation": 32},
                pointer_after_reader=lambda: {"generation": 32},
                observed_at="2026-07-29T00:00:00Z",
                expected_template_count=1,
                expected_spec_count=1,
                expected_supported_spec_count=1,
                expected_unsupported_spec_count=0,
                expected_ready_loadout_count=0,
                expected_ready_snapshot_count=0,
                expected_unsupported_snapshot_count=0,
            )

        self.assertEqual(matcher.call_count, 2)
        for call in matcher.call_args_list:
            self.assertEqual(
                call.kwargs["template_authority_identity"],
                TEMPLATE_AUTHORITY_IDENTITY,
            )

    def test_ready_and_partial_templates_are_closed_without_silent_drop(self):
        registry = exact_registry()
        partial_hash = "sha256:" + ("f" * 64)
        partial_refs = []
        for raw in registry["templateReferences"]:
            row = copy.deepcopy(raw)
            row["templateContentHash"] = partial_hash
            row["validationStatus"] = "partial"
            row["exactItemInstanceKey"] = ""
            row["problemCodes"] = ["ENHANCEMENT_SINGLE_VALUE_MALFORMED"]
            partial_refs.append(row)
        registry["templateReferences"].extend(partial_refs)
        sealed_loadouts = []
        sealed_snapshots = []

        report = MODULE.run_shadow(
            templates=[
                template(TEMPLATE_HASH, "ready"),
                {
                    **template(partial_hash, "partial"),
                    "importStatus": "blocked",
                    "importProblemCodes": [
                        "LOADOUT_EXACT_REFERENCE_NOT_VERIFIED"
                    ],
                },
            ],
            exact_registry=registry,
            resolver_reader=lambda _template: resolver_snapshot(),
            snapshot_reader=lambda _loadout, _template: snapshot(),
            seal_loadout=lambda value: (
                sealed_loadouts.append(value) or value
            ),
            seal_snapshot=lambda value: (
                sealed_snapshots.append(value) or value
            ),
            pointer_before={"generation": 32},
            pointer_after_reader=lambda: {"generation": 32},
            observed_at="2026-07-29T00:00:00Z",
            expected_template_count=2,
            expected_spec_count=1,
            expected_supported_spec_count=1,
            expected_unsupported_spec_count=0,
            expected_ready_loadout_count=1,
            expected_ready_snapshot_count=1,
            expected_unsupported_snapshot_count=0,
        )

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["summary"]["classifiedTemplateCount"], 2)
        self.assertEqual(report["summary"]["readyLoadoutCount"], 1)
        self.assertEqual(report["summary"]["blockedLoadoutCount"], 1)
        self.assertEqual(report["summary"]["readySnapshotCount"], 1)
        self.assertEqual(report["summary"]["blockedSnapshotCount"], 0)
        self.assertEqual(len(sealed_loadouts), 1)
        self.assertEqual(len(sealed_snapshots), 1)
        self.assertEqual(
            report["problemCounts"][
                "LOADOUT_EXACT_REFERENCE_NOT_VERIFIED"
            ],
            1,
        )

    def test_pointer_change_blocks_otherwise_complete_shadow(self):
        report = MODULE.run_shadow(
            templates=[template(TEMPLATE_HASH, "ready")],
            exact_registry=exact_registry(),
            resolver_reader=lambda _template: resolver_snapshot(),
            snapshot_reader=lambda _loadout, _template: snapshot(),
            seal_loadout=lambda value: value,
            seal_snapshot=lambda value: value,
            pointer_before={"generation": 32},
            pointer_after_reader=lambda: {"generation": 33},
            observed_at="2026-07-29T00:00:00Z",
            expected_template_count=1,
            expected_spec_count=1,
            expected_supported_spec_count=1,
            expected_unsupported_spec_count=0,
            expected_ready_loadout_count=1,
            expected_ready_snapshot_count=1,
            expected_unsupported_snapshot_count=0,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "RESOLVED_SHADOW_POINTER_CHANGED",
            report["problemCodes"],
        )

    def test_missing_supported_spec_snapshot_coverage_blocks_shadow(self):
        report = MODULE.run_shadow(
            templates=[template(TEMPLATE_HASH, "ready")],
            exact_registry=exact_registry(),
            resolver_reader=lambda _template: resolver_snapshot(),
            snapshot_reader=lambda _loadout, _template: snapshot(),
            seal_loadout=lambda value: value,
            seal_snapshot=lambda value: value,
            pointer_before={"generation": 32},
            pointer_after_reader=lambda: {"generation": 32},
            observed_at="2026-07-29T00:00:00Z",
            expected_template_count=1,
            expected_spec_count=1,
            expected_supported_spec_count=2,
            expected_unsupported_spec_count=0,
            expected_ready_loadout_count=1,
            expected_ready_snapshot_count=1,
            expected_unsupported_snapshot_count=0,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "RESOLVED_SHADOW_SUPPORTED_SPEC_COVERAGE_INCOMPLETE",
            report["problemCodes"],
        )

    def test_zero_ready_loadouts_cannot_be_reported_verified(self):
        blocked_template = {
            **template(TEMPLATE_HASH, "blocked"),
            "importStatus": "blocked",
            "importProblemCodes": ["template_import_blocked"],
        }
        report = MODULE.run_shadow(
            templates=[blocked_template],
            exact_registry=exact_registry(),
            resolver_reader=lambda _template: resolver_snapshot(),
            snapshot_reader=lambda _loadout, _template: snapshot(),
            seal_loadout=lambda value: value,
            seal_snapshot=lambda value: value,
            pointer_before={"generation": 32},
            pointer_after_reader=lambda: {"generation": 32},
            observed_at="2026-07-29T00:00:00Z",
            expected_template_count=1,
            expected_spec_count=1,
            expected_supported_spec_count=1,
            expected_unsupported_spec_count=0,
            expected_ready_loadout_count=1,
            expected_ready_snapshot_count=1,
            expected_unsupported_snapshot_count=0,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "RESOLVED_SHADOW_READY_LOADOUT_COUNT_MISMATCH",
            report["problemCodes"],
        )

    def test_total_setup_and_import_budget_is_enforced(self):
        report = MODULE.run_shadow(
            templates=[template(TEMPLATE_HASH, "ready")],
            exact_registry=exact_registry(),
            resolver_reader=lambda _template: resolver_snapshot(),
            snapshot_reader=lambda _loadout, _template: snapshot(),
            seal_loadout=lambda value: value,
            seal_snapshot=lambda value: value,
            pointer_before={"generation": 32},
            pointer_after_reader=lambda: {"generation": 32},
            observed_at="2026-07-29T00:00:00Z",
            expected_template_count=1,
            expected_spec_count=1,
            expected_supported_spec_count=1,
            expected_unsupported_spec_count=0,
            expected_ready_loadout_count=1,
            expected_ready_snapshot_count=1,
            expected_unsupported_snapshot_count=0,
            elapsed_before_shadow=601.0,
            max_total_seconds=600.0,
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "RESOLVED_SHADOW_TOTAL_SECONDS_EXCEEDED",
            report["problemCodes"],
        )
        self.assertGreater(
            report["resource"]["totalElapsedSeconds"],
            report["resource"]["maxTotalSeconds"],
        )


if __name__ == "__main__":
    unittest.main()

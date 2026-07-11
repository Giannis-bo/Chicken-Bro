import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from server import gear_release


class FakeReleaseStore:
    def __init__(self, gear_snapshot, templates=None):
        self.gear_snapshot = gear_snapshot
        self.templates = templates or []
        self.gear_seals = []
        self.community_seals = []
        self.requested_specs = []

    def snapshot_staging_gear(self):
        return copy.deepcopy(self.gear_snapshot)

    def snapshot_staging_community_templates(self, expected_specs):
        self.requested_specs = list(expected_specs)
        return copy.deepcopy(self.templates)

    def seal_gear_release(self, release, snapshot, **kwargs):
        self.gear_seals.append((copy.deepcopy(release), copy.deepcopy(snapshot), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}

    def seal_community_release(self, release, rows, **kwargs):
        self.community_seals.append((copy.deepcopy(release), copy.deepcopy(rows), copy.deepcopy(kwargs)))
        return {"status": "inserted", "releaseId": release["releaseId"]}


class GearReleaseToolTest(unittest.TestCase):
    def dependencies(self):
        return {
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": "simc-r1",
            "statPolicyRevision": "stat-snapshot-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": "gear-capability-v1",
        }

    def snapshot(self):
        return {
            "items": [{"itemId": "item-a", "name": "A", "slot": "head", "sourceStatus": "verified", "payload": {}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "sources": [{"sourceId": "source-a", "itemId": "item-a", "sourceType": "observed_profile", "sourceKey": "profile:a", "payload": {"status": "verified"}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "variants": [{"variantId": "variant-a-id", "itemId": "item-a", "variantKey": "variant-a", "slot": "head", "sourceType": "observed_profile", "itemLevel": 289, "simcOptions": {"ilevel": "289"}, "status": "verified", "blockers": [], "payload": {"resolvedStats": {"intellect": 100}}, "updatedAt": "2026-07-11T05:00:00+00:00"}],
            "options": [],
        }

    def template(self, template_id="template-a", source_key="raiderio_observed_profile"):
        return {
            "templateId": template_id,
            "classKey": "mage",
            "specKey": "arcane",
            "name": "Observed A",
            "sourceKey": source_key,
            "sourceName": "Raider.IO",
            "sourceUrl": "https://raider.io/characters/cn/a",
            "sourceStatus": "synced",
            "status": "complete",
            "signature": "gear:a",
            "sourceRefs": [{"sampleCount": 1, "sourceUrl": "https://raider.io/characters/cn/a"}],
            "gearItems": [
                {
                    "slot": "head",
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "itemStats": [{"key": "intellect", "value": 999999}],
                    "simcReady": True,
                    "gem_id": "forged-raw-gem",
                    "enchant_id": "forged-raw-enchant",
                }
            ],
            "readySlotCount": 16,
            "missingSlots": [],
            "payload": {
                "templateEvidence": {
                    "status": "observed_verified",
                    "profileHash": "profile:a",
                    "gearHash": "gear:a",
                    "sampleCount": 1,
                }
            },
            "updatedAt": "2026-07-11T05:00:00+00:00",
            "expiresAt": "2026-07-25T05:00:00+00:00",
            "scanRunId": "scan-a",
        }

    def verified_result(self, gear_release_id):
        return {
            "status": "verified",
            "aggregateLegality": {"status": "verified", "problemCodes": []},
            "profileReadiness": {"status": "verified", "simcReady": True, "missingSlots": []},
            "resolvedGearSignature": "sha256:resolved-a",
            "dependencyVector": {
                **self.dependencies(),
                "seasonRevision": "season-17",
                "gearCatalogReleaseId": gear_release_id,
                "gearCatalogRevision": gear_release_id,
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "resolvedSlots": {"head": {"itemId": "item-a", "variantKey": "variant-a", "resolvedStats": {"intellect": 100}}},
            "staticAttributes": {"intellect": 100},
            "setState": {"itemSetCounts": {}},
            "constraints": {"slots": {}},
            "serializerInput": {"gearItems": [{"slot": "head", "itemId": "item-a"}]},
            "problems": [],
        }

    def test_template_intent_contains_only_exact_server_allowed_selection_fields(self):
        from server.gear_release_tool import selection_intent_from_template

        intent = selection_intent_from_template(
            self.template(),
            gear_release_id="gear-release:sha256:target",
            season_revision="season-17",
            level=90,
        )

        self.assertEqual(set(intent), {"schemaRevision", "authoredAgainst", "eligibilityContext", "slots"})
        self.assertEqual(intent["slots"]["head"], {
            "itemId": "item-a",
            "variantKey": "variant-a",
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        })
        self.assertNotIn("999999", str(intent))
        self.assertNotIn("forged", str(intent))

    def test_build_legacy_gear_release_snapshots_and_seals_inactive_candidate(self):
        from server.gear_release_tool import build_legacy_gear_release

        store = FakeReleaseStore(self.snapshot())
        result = build_legacy_gear_release(
            store,
            season_revision="season-17",
            dependency_revisions=self.dependencies(),
            source_revision="legacy-import-r0",
        )

        release = result["release"]
        self.assertEqual(release["releaseKind"], "gear")
        self.assertEqual(release["releaseStatus"], "validated")
        self.assertEqual(release["source"]["sourceRevision"], "legacy-import-r0")
        self.assertEqual(result["seal"]["status"], "inserted")
        self.assertEqual(len(store.gear_seals), 1)
        self.assertNotIn("manifest", result)
        self.assertNotIn("pointer", result)

    def test_build_legacy_gear_release_blocks_empty_or_orphan_snapshot(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import build_legacy_gear_release

        for snapshot in (
            {"items": [], "sources": [], "variants": [], "options": []},
            {"items": [], "sources": [], "variants": [{"variantId": "v", "itemId": "missing", "variantKey": "v"}], "options": []},
        ):
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(GearReleaseIntegrityError):
                    build_legacy_gear_release(
                        FakeReleaseStore(snapshot),
                        season_revision="season-17",
                        dependency_revisions=self.dependencies(),
                    )

    def test_build_legacy_gear_release_blocks_blank_required_identifiers(self):
        from server.gear_release_store import GearReleaseIntegrityError
        from server.gear_release_tool import build_legacy_gear_release

        mutations = (
            ("items", "itemId"),
            ("sources", "sourceId"),
            ("sources", "sourceKey"),
            ("variants", "variantId"),
            ("variants", "variantKey"),
        )
        for collection, field in mutations:
            with self.subTest(collection=collection, field=field):
                snapshot = self.snapshot()
                snapshot[collection][0][field] = ""
                with self.assertRaises(GearReleaseIntegrityError):
                    build_legacy_gear_release(
                        FakeReleaseStore(snapshot),
                        season_revision="season-17",
                        dependency_revisions=self.dependencies(),
                    )

    def test_build_legacy_community_release_revalidates_and_seals_winner(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        store = FakeReleaseStore(snapshot, [self.template()])
        calls = []

        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda class_key, spec_key, intent: calls.append((class_key, spec_key, intent)) or self.verified_result(gear["releaseId"]),
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(store.requested_specs, [("mage", "arcane")])
        self.assertEqual(result["election"]["status"], "validated")
        self.assertEqual(result["election"]["winnerSpecCount"], 1)
        self.assertEqual(result["release"]["releaseKind"], "community")
        self.assertEqual(result["release"]["validatedAgainstReleaseId"], gear["releaseId"])
        self.assertEqual(result["rows"][0]["role"], "winner")
        self.assertEqual(result["rows"][0]["semanticGearSignature"].startswith("sha256:"), True)
        self.assertEqual(len(store.community_seals), 1)
        self.assertNotIn("pointer", result)

    def test_build_legacy_community_release_keeps_rejected_internal_and_degraded(self):
        from server.gear_release_store import gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        invalid = self.template(source_key="season_recommendation")
        store = FakeReleaseStore(snapshot, [invalid])
        result = build_legacy_community_release(
            store,
            gear_release_descriptor=gear,
            gear_snapshot=snapshot,
            dependency_revisions=self.dependencies(),
            expected_specs=[("mage", "arcane")],
            now="2026-07-11T06:00:00+00:00",
            resolver_for_spec=lambda *_args: self.fail("invalid source must not reach Resolver"),
        )

        self.assertEqual(result["release"]["releaseStatus"], "degraded")
        self.assertEqual(result["election"]["winnerSpecCount"], 0)
        self.assertEqual(result["rows"][0]["role"], "rejected")
        self.assertEqual(store.community_seals[0][2]["gate_result"]["winnerSpecCount"], 0)

    def test_build_legacy_community_release_rejects_duplicate_template_ids(self):
        from server.gear_release_store import GearReleaseIntegrityError, gear_snapshot_summary
        from server.gear_release_tool import build_legacy_community_release

        snapshot = self.snapshot()
        gear = gear_release.build_release(
            release_kind="gear",
            season_revision="season-17",
            schema_revision="gear-release-v1",
            content=gear_snapshot_summary(snapshot),
            dependency_revisions=self.dependencies(),
            release_status="validated",
            source={"sourceRevision": "legacy-import-r0"},
        )
        templates = [self.template(), self.template()]
        with self.assertRaises(GearReleaseIntegrityError):
            build_legacy_community_release(
                FakeReleaseStore(snapshot, templates),
                gear_release_descriptor=gear,
                gear_snapshot=snapshot,
                dependency_revisions=self.dependencies(),
                expected_specs=[("mage", "arcane")],
                now="2026-07-11T06:00:00+00:00",
                resolver_for_spec=lambda *_args: self.fail("duplicates must fail before Resolver"),
            )

    def test_shadow_command_is_read_only_and_requires_explicit_release_pair(self):
        from server import gear_release_tool

        output = io.StringIO()
        with patch.object(
            gear_release_tool,
            "_shadow_store_from_environment",
            return_value=object(),
        ), patch.object(
            gear_release_tool.gear_release_shadow,
            "run_release_shadow",
            return_value={"status": "pass", "publicReadCount": 40, "blockers": []},
        ) as shadow, redirect_stdout(output):
            status = gear_release_tool.main([
                "shadow",
                "--gear-release-id", "gear-release:a",
                "--community-release-id", "community-release:a",
                "--simc-runtime-revision", "simc-r1",
            ])

        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "pass")
        shadow.assert_called_once()
        self.assertEqual(shadow.call_args.kwargs["gear_release_id"], "gear-release:a")
        self.assertEqual(shadow.call_args.kwargs["community_release_id"], "community-release:a")

        with self.assertRaises(SystemExit):
            gear_release_tool.main(["shadow", "--simc-runtime-revision", "simc-r1"])


if __name__ == "__main__":
    unittest.main()

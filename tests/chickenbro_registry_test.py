import copy
import hashlib
import json
import unittest

from server.chickenbro_registry import (
    discover_chickenbro_capabilities,
    validate_chickenbro_registry_release,
    validate_chickenbro_tool_manifest,
)


CREATED_AT = "2026-08-02T00:00:00+00:00"


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def signed_manifest(**overrides):
    manifest = {
        "toolId": "source:raiderio:v1",
        "version": "1.0.0",
        "kind": "tool",
        "namespace": "source",
        "purpose": "Load bounded Raider.IO specialization evidence.",
        "inputSchema": {"required": ["classKey", "specKey"]},
        "outputSchema": {"schemaRevision": "chickenbro-tool-result-v1"},
        "discoveryPolicy": {
            "requestKinds": ["community_build"],
            "requiredContextFields": ["classKey", "specKey"],
            "productPhases": ["retail", "ptr"],
            "regions": ["cn", "global", "us", "eu", "kr", "tw"],
            "priority": 100,
        },
        "riskClass": "read_only",
        "sideEffects": [],
        "ownerPolicy": "public_source",
        "sourcePolicy": {
            "sourceKey": "raiderio",
            "requiredStatuses": ["synced", "partial"],
        },
        "freshnessPolicy": {
            "maxAgeSeconds": 86400,
            "staleBehavior": "limitation_only",
        },
        "timeoutBudgetMs": 3000,
        "costBudget": {"status": "bounded_existing_runtime"},
        "implementationRef": "chickenbro.source.raiderio.v1",
        "evalRefs": ["chickenbro-eval:verified_source_success"],
        "status": "active",
        "provenance": {"kind": "repository_migration", "revision": "0025"},
        "createdAt": CREATED_AT,
    }
    manifest.update(overrides)
    manifest["contentHash"] = content_hash(manifest)
    return manifest


def wcl_manifest(**overrides):
    values = {
        "toolId": "source:warcraftlogs:v1",
        "purpose": "Load bounded owner-scoped Warcraft Logs report evidence.",
        "inputSchema": {"required": ["wclReport"]},
        "discoveryPolicy": {
            "requestKinds": ["personal_wcl"],
            "requiredContextFields": ["wclReport"],
            "productPhases": ["retail", "ptr"],
            "regions": ["cn", "global", "us", "eu", "kr", "tw"],
            "priority": 100,
        },
        "ownerPolicy": "owner_bound_report",
        "sourcePolicy": {
            "sourceKey": "warcraftlogs",
            "requiredStatuses": ["verified"],
        },
        "freshnessPolicy": {
            "maxAgeSeconds": 3600,
            "staleBehavior": "limitation_only",
        },
        "implementationRef": "chickenbro.source.warcraftlogs.v1",
        "evalRefs": ["chickenbro-eval:wcl_verified_report"],
    }
    values.update(overrides)
    return signed_manifest(**values)


def current_sources_manifest(**overrides):
    values = {
        "toolId": "source:current-wow-sources:v1",
        "purpose": "Load bounded official current Warcraft facts for a resolved question frame.",
        "inputSchema": {"required": ["classKey", "specKey", "questionType", "patchVersion"]},
        "discoveryPolicy": {
            "requestKinds": ["current_research"],
            "requiredContextFields": ["classKey", "specKey", "questionType", "patchVersion"],
            "productPhases": ["retail", "ptr"],
            "regions": ["cn", "global", "us", "eu", "kr", "tw"],
            "evidenceNeeds": ["official_current_changes"],
            "priority": 100,
        },
        "sourcePolicy": {
            "sourceKey": "current_wow_sources",
            "requiredStatuses": ["source_reference", "partial", "failed"],
            "approvedSourceIds": ["blizzard", "blizzard-forums"],
        },
        "freshnessPolicy": {
            "maxAgeSeconds": 900,
            "staleBehavior": "failed",
        },
        "timeoutBudgetMs": 10000,
        "costBudget": {"status": "bounded_live_official_read", "maxArticlesPerSource": 1},
        "implementationRef": "chickenbro.source.current_wow_sources.v1",
        "evalRefs": ["chickenbro-eval:current_official_source"],
        "provenance": {"kind": "repository_migration", "revision": "0026"},
        "createdAt": "2026-08-03T00:00:00+00:00",
    }
    values.update(overrides)
    return signed_manifest(**values)


def signed_release(manifests=None, **overrides):
    manifests = list(manifests or [signed_manifest(), wcl_manifest()])
    refs = [
        {
            "toolId": item["toolId"],
            "version": item["version"],
            "contentHash": item["contentHash"],
        }
        for item in manifests
    ]
    release = {
        "registryVersion": "chickenbro-tools-1",
        "manifestRefs": refs,
        "releaseHash": content_hash(refs),
        "status": "active",
        "provenance": {"kind": "repository_migration", "revision": "0025"},
        "createdAt": CREATED_AT,
        "activatedAt": CREATED_AT,
        "manifests": manifests,
    }
    release.update(overrides)
    return release


class ChickenbroRegistryTest(unittest.TestCase):
    def test_manifest_rejects_unknown_code_and_hash_mutation(self):
        manifest = signed_manifest()
        validated = validate_chickenbro_tool_manifest(manifest)
        self.assertEqual("source:raiderio:v1", validated["toolId"])

        with self.assertRaisesRegex(ValueError, "unknown manifest keys"):
            validate_chickenbro_tool_manifest({**manifest, "python": "evil"})
        with self.assertRaisesRegex(ValueError, "implementationRef"):
            validate_chickenbro_tool_manifest(
                signed_manifest(implementationRef="python:os.system")
            )
        with self.assertRaisesRegex(ValueError, "contentHash"):
            validate_chickenbro_tool_manifest({**manifest, "purpose": "mutated"})

    def test_release_rejects_duplicate_refs_hash_drift_and_disabled_manifest(self):
        release = signed_release()
        validated = validate_chickenbro_registry_release(release)
        self.assertEqual("chickenbro-tools-1", validated["registryVersion"])
        self.assertEqual(2, len(validated["manifests"]))

        duplicate = copy.deepcopy(release)
        duplicate["manifestRefs"][1]["toolId"] = duplicate["manifestRefs"][0]["toolId"]
        duplicate["releaseHash"] = content_hash(duplicate["manifestRefs"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_chickenbro_registry_release(duplicate)

        with self.assertRaisesRegex(ValueError, "releaseHash"):
            validate_chickenbro_registry_release({**release, "releaseHash": "sha256:" + "0" * 64})

        disabled = signed_manifest(status="disabled")
        with self.assertRaisesRegex(ValueError, "active manifest"):
            validate_chickenbro_registry_release(signed_release([disabled, wcl_manifest()]))

    def test_discovery_selects_only_the_matching_published_tool(self):
        release = signed_release()
        cases = [
            (
                {"kind": "personal_wcl", "productPhase": "retail", "wclReport": "https://www.warcraftlogs.com/reports/ABC"},
                {"region": "cn"},
                ["source:warcraftlogs:v1"],
                [],
            ),
            (
                {"kind": "community_build", "productPhase": "ptr", "classKey": "deathknight", "specKey": "frost"},
                {"region": "cn", "classKey": "deathknight", "specKey": "frost"},
                ["source:raiderio:v1"],
                [],
            ),
            (
                {"kind": "community_build", "productPhase": "retail", "classKey": "warrior", "specKey": ""},
                {"region": "cn", "classKey": "warrior"},
                [],
                ["specKey"],
            ),
            (
                {"kind": "general", "productPhase": "retail"},
                {"region": "cn"},
                [],
                [],
            ),
            (
                {"kind": "community_build", "productPhase": "unknown", "classKey": "warrior", "specKey": "protection"},
                {"region": "moon", "classKey": "warrior", "specKey": "protection"},
                [],
                [],
            ),
        ]
        for intent, context, expected_ids, missing in cases:
            with self.subTest(intent=intent, context=context):
                result = discover_chickenbro_capabilities(release, intent, context)
                self.assertEqual(expected_ids, result["discoveredCapabilityIds"])
                self.assertEqual(expected_ids, result["selectedCapabilityIds"])
                self.assertEqual(missing, result["missingContextFields"])
                self.assertEqual(
                    expected_ids,
                    [item["toolId"] for item in result["selectedManifests"]],
                )

    def test_current_research_discovers_only_the_evidence_appropriate_official_tool(self):
        release = signed_release(
            [signed_manifest(), wcl_manifest(), current_sources_manifest()],
            registryVersion="chickenbro-tools-2",
            provenance={"kind": "repository_migration", "revision": "0026"},
        )
        intent = {
            "kind": "current_research",
            "questionType": "current_research",
            "productPhase": "ptr",
            "patchVersion": "12.1",
            "classKey": "paladin",
            "specKey": "holy",
            "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
        }
        context = {
            "region": "cn",
            "productPhase": "ptr",
            "questionType": "current_research",
            "patchVersion": "12.1",
            "classKey": "paladin",
            "specKey": "holy",
        }

        result = discover_chickenbro_capabilities(release, intent, context)

        self.assertEqual(["source:current-wow-sources:v1"], result["selectedCapabilityIds"])
        self.assertEqual([], result["missingContextFields"])


if __name__ == "__main__":
    unittest.main()

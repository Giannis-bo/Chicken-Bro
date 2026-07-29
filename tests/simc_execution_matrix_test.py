import unittest


class SimcExecutionMatrixTest(unittest.TestCase):
    def test_matrix_executes_supported_and_blocks_unsupported_specs(self):
        from server.simc_execution_matrix import run_simc_execution_matrix

        manifest_revision = "season-manifest:sha256:" + "a" * 64
        gear_release_id = "gear-release:sha256:" + "b" * 64
        community_release_id = "community-release:sha256:" + "c" * 64
        catalog_revision = "gear-catalog:sha256:" + "e" * 64
        exact_registry_revision = "gear-exact-registry:sha256:" + "f" * 64
        simc_revision = "simc:" + "d" * 40
        snapshot = {
            "contractRevision": "gear-resolved-snapshot-v1",
            "status": "verified",
            "dependencyVector": {
                "seasonRevision": "season-r1",
                "gearCatalogRevision": catalog_revision,
                "simcRuntimeRevision": simc_revision,
            },
            "eligibilityContext": {"level": 90},
            "resolvedSlots": {
                "head": {
                    "itemId": "250001",
                    "variantKey": "gear-variant:head",
                    "selectedOptions": {
                        "gemOptionIds": [],
                        "enchantOptionId": "",
                        "embellishmentOptionId": "",
                        "craftedOptionId": "",
                        "catalystOptionId": "",
                    },
                }
            },
            "profileReadiness": {"status": "verified", "simcReady": True},
            "problems": [],
        }

        def request_json(method, path, payload, _headers):
            class_key = ""
            spec_key = ""
            if "class=mage" in path:
                class_key, spec_key = "mage", "frost"
            elif "class=paladin" in path:
                class_key, spec_key = "paladin", "holy"
            elif isinstance(payload, dict):
                eligibility = (
                    (payload.get("selectionIntent") or {}).get("eligibilityContext")
                    if isinstance(payload.get("selectionIntent"), dict)
                    else {}
                )
                class_key = eligibility.get("classKey", "")
                spec_key = eligibility.get("specKey", "")

            if method == "GET" and path == "/api/simulator/simc/options":
                return 200, {
                    "contractRevision": "simc-options-v1",
                    "status": "ready",
                    "specializationPolicy": {
                        "contractRevision": "simc-execution-support-v1",
                        "status": "ready",
                        "supportedSpecCount": 26,
                        "unsupportedSpecCount": 14,
                    },
                    "races": {
                        "defaultByClass": {
                            "mage": "human",
                            "paladin": "human",
                        }
                    },
                }, 1.0
            if method == "GET" and path.startswith("/api/websim/gear?"):
                templates = [{
                    "id": f"template-{class_key}-{spec_key}",
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": "lightsmith" if spec_key == "holy" else "frostfire",
                    "canApplyGear": True,
                }]
                if class_key == "mage":
                    templates.insert(0, {
                        "id": "template-mage-frost-invalid",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "aaa_invalid",
                        "canApplyGear": True,
                    })
                return 200, {
                    "formalActiveManifest": False,
                    "candidatePreview": True,
                    "manifestRevision": manifest_revision,
                    "pointerGeneration": 27,
                    "gearCatalogReleaseId": gear_release_id,
                    "gearCatalogRevision": catalog_revision,
                    "gearExactRegistryRevision": exact_registry_revision,
                    "communityTemplateReleaseId": community_release_id,
                    "communityTemplates": templates,
                }, 1.0
            if method == "POST" and path == "/api/websim/gear/community-import":
                resolved = {
                    **snapshot,
                    "eligibilityContext": {
                        "classKey": payload["classKey"],
                        "specKey": payload["specKey"],
                        "level": 90,
                    },
                }
                return 200, {
                    "status": "verified",
                    "data": {
                        "status": "verified",
                        "resolvedSnapshot": resolved,
                    },
                }, 2.0
            if method == "GET" and path.startswith("/api/websim/talents/import?"):
                if "hero=aaa_invalid" in path:
                    return 200, {
                        "status": "blocked",
                        "importCode": "",
                        "blockers": ["fixture mismatch"],
                    }, 1.0
                return 200, {
                    "status": "verified",
                    "importCode": f"talents-{class_key}-{spec_key}",
                }, 1.0
            if method == "POST" and path == "/api/websim/profile":
                return 200, {
                    "status": "resolved",
                    "releaseContext": {
                        "manifestRevision": manifest_revision,
                        "pointerGeneration": 27,
                        "gearCatalogRevision": catalog_revision,
                        "gearExactRegistryRevision": exact_registry_revision,
                        "simcRuntimeRevision": simc_revision,
                    },
                    "data": {
                        "status": "resolved",
                        "profile": f"{class_key}=matrix\nspec={spec_key}\n",
                        "profileReadiness": {"status": "verified", "simcReady": True},
                    },
                    "problems": [],
                }, 3.0
            if method == "POST" and path == "/api/simulator/analyze":
                return 200, {
                    "status": "blocked",
                    "agent": {
                        "validation": {
                            "passed": False,
                            "problems": [{
                                "code": "SIMC_SPECIALIZATION_UNSUPPORTED",
                            }],
                        }
                    },
                    "simulation": {"ran": False},
                }, 1.0
            raise AssertionError((method, path))

        report = run_simc_execution_matrix(
            request_json,
            lambda profile: {
                "ran": bool(profile),
                "hasDps": bool(profile),
                "timedOut": False,
                "durationMs": 4.0,
            },
            expected_specs=[("mage", "frost"), ("paladin", "holy")],
            manifest_revision=manifest_revision,
            pointer_generation=27,
            gear_release_id=gear_release_id,
            community_release_id=community_release_id,
            catalog_revision=catalog_revision,
            exact_registry_revision=exact_registry_revision,
            simc_runtime_revision=simc_revision,
            observed_at="2026-07-28T00:00:00+00:00",
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["supported"], {
            "expectedSpecCount": 1,
            "profileReadySpecCount": 1,
            "executedSpecCount": 1,
            "dpsMetricSpecCount": 1,
        })
        self.assertEqual(report["unsupported"], {
            "expectedSpecCount": 1,
            "deterministicallyBlockedSpecCount": 1,
        })
        self.assertEqual(report["failureCount"], 0)
        self.assertEqual(report["gearCatalogRevision"], catalog_revision)
        self.assertEqual(
            report["gearExactRegistryRevision"],
            exact_registry_revision,
        )
        self.assertNotIn("matrix\\nspec=", str(report))
        self.assertNotIn("talents-mage-frost", str(report))


if __name__ == "__main__":
    unittest.main()

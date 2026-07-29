import json
import unittest


class GearReleaseHttpMatrixTest(unittest.TestCase):
    def identities(self):
        return {
            "manifest_revision": "season-manifest:sha256:" + "a" * 64,
            "pointer_generation": 27,
            "gear_release_id": "gear-release:sha256:" + "b" * 64,
            "community_release_id": "community-release:sha256:" + "c" * 64,
        }

    def browse_payload(self, identities):
        return {
            "formalActiveManifest": True,
            "candidatePreview": False,
            "manifestRevision": identities["manifest_revision"],
            "pointerGeneration": identities["pointer_generation"],
            "gearCatalogReleaseId": identities["gear_release_id"],
            "communityTemplateReleaseId": identities[
                "community_release_id"
            ],
            "communityTemplates": [
                {
                    "id": "private-template-frostfire",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "frostfire",
                    "sourceKey": "raiderio_observed_profile",
                    "canApplyGear": True,
                },
                {
                    "id": "private-template-spellslinger",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "spellslinger",
                    "sourceKey": "raiderio_observed_profile",
                    "canApplyGear": True,
                },
            ],
            "baselineTemplates": [],
        }

    def import_payload(self, identities):
        return {
            "status": "verified",
            "problems": [],
            "data": {
                "contractRevision": (
                    "websim-community-template-import-v2"
                ),
                "status": "verified",
                "manifest": {
                    "manifestRevision": identities[
                        "manifest_revision"
                    ],
                    "pointerGeneration": identities[
                        "pointer_generation"
                    ],
                },
                "importedGearBySlot": {
                    "head": {
                        "itemId": "item-a",
                        "variantKey": "variant-a",
                    }
                },
                "resolvedSnapshot": {
                    "status": "verified",
                    "resolvedSlots": {
                        "head": {
                            "itemId": "item-a",
                            "variantKey": "variant-a",
                        }
                    },
                    "profileReadiness": {
                        "status": "verified",
                        "simcReady": True,
                        "problems": [],
                    },
                    "problems": [],
                },
            },
        }

    def test_passes_two_hero_browse_and_import_without_leaking_template_ids(self):
        from server.gear_release_http_matrix import run_http_matrix

        identities = self.identities()

        def request(method, path, payload, _headers):
            if method == "GET":
                return 200, self.browse_payload(identities), 12.5
            self.assertEqual(
                payload["expectedManifestRevision"],
                identities["manifest_revision"],
            )
            return 200, self.import_payload(identities), 25.0

        report = run_http_matrix(
            request,
            expected_specs=[("mage", "frost")],
            **identities,
            observed_at="2026-07-28T20:00:00+08:00",
        )

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(report["browse"]["passingSpecCount"], 1)
        self.assertEqual(report["imports"]["passingHeroSlotCount"], 2)
        self.assertEqual(report["failureCount"], 0)
        self.assertTrue(report["reportId"].startswith(
            "gear-release-http-matrix:sha256:"
        ))
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("private-template-frostfire", rendered)
        self.assertNotIn("private-template-spellslinger", rendered)

    def test_candidate_preview_mode_requires_candidate_binding(self):
        from server.gear_release_http_matrix import (
            run_http_matrix,
            validate_http_matrix_report,
        )

        identities = self.identities()
        browse = self.browse_payload(identities)
        browse["formalActiveManifest"] = False
        browse["candidatePreview"] = True

        def request(method, _path, _payload, _headers):
            if method == "GET":
                return 200, browse, 1.0
            return 200, self.import_payload(identities), 1.0

        report = run_http_matrix(
            request,
            expected_specs=[("mage", "frost")],
            candidate_preview=True,
            **identities,
            observed_at="2026-07-28T20:00:00+08:00",
        )

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(
            report["bindingMode"],
            "candidate_preview",
        )
        self.assertEqual(
            validate_http_matrix_report(
                report,
                expected_spec_count=1,
                candidate_preview=True,
                **identities,
            ),
            [],
        )

        browse["candidatePreview"] = False
        wrong_mode = run_http_matrix(
            request,
            expected_specs=[("mage", "frost")],
            candidate_preview=True,
            **identities,
            observed_at="2026-07-28T20:00:00+08:00",
        )
        self.assertIn(
            "CANDIDATE_PREVIEW_REQUIRED",
            wrong_mode["failureCodes"],
        )

    def test_stale_manifest_and_blocked_import_fail_closed(self):
        from server.gear_release_http_matrix import run_http_matrix

        identities = self.identities()
        browse = self.browse_payload(identities)
        browse["manifestRevision"] = "season-manifest:stale"

        def request(method, _path, _payload, _headers):
            if method == "GET":
                return 200, browse, 10.0
            return 200, {
                "status": "blocked",
                "problems": [{"code": "template_import_blocked"}],
                "data": {},
            }, 20.0

        report = run_http_matrix(
            request,
            expected_specs=[("mage", "frost")],
            **identities,
            observed_at="2026-07-28T20:00:00+08:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["browse"]["passingSpecCount"], 0)
        self.assertEqual(report["imports"]["passingHeroSlotCount"], 0)
        self.assertIn(
            "MANIFEST_REVISION_MISMATCH",
            report["failureCodes"],
        )
        self.assertIn(
            "template_import_blocked",
            report["failureCodes"],
        )

    def test_aggregate_report_validator_binds_identity_and_hash(self):
        from server.gear_release_http_matrix import (
            run_http_matrix,
            validate_http_matrix_report,
        )

        identities = self.identities()

        def request(method, path, payload, _headers):
            if method == "GET":
                return 200, self.browse_payload(identities), 1.0
            return 200, self.import_payload(identities), 1.0

        report = run_http_matrix(
            request,
            expected_specs=[("mage", "frost")],
            **identities,
            observed_at="2026-07-28T20:00:00+08:00",
        )
        arguments = {
            "manifest_revision": identities["manifest_revision"],
            "pointer_generation": identities["pointer_generation"],
            "gear_release_id": identities["gear_release_id"],
            "community_release_id": identities["community_release_id"],
            "expected_spec_count": 1,
        }

        self.assertEqual(
            validate_http_matrix_report(report, **arguments),
            [],
        )
        damaged = dict(report)
        damaged["pointerGeneration"] += 1
        self.assertIn(
            "HTTP_MATRIX_IDENTITY_INVALID",
            validate_http_matrix_report(damaged, **arguments),
        )
        self.assertIn(
            "HTTP_MATRIX_BINDING_MISMATCH",
            validate_http_matrix_report(damaged, **arguments),
        )


if __name__ == "__main__":
    unittest.main()

import copy
import unittest
from urllib.parse import parse_qs, urlparse

from server.gear_catalog_http_completeness_matrix import (
    CANONICAL_GEAR_SLOTS,
    run_catalog_http_completeness_matrix,
)


class GearCatalogHttpCompletenessMatrixTest(unittest.TestCase):
    def identities(self):
        return {
            "manifest_revision": "season-manifest:sha256:" + "a" * 64,
            "pointer_generation": 35,
            "gear_release_id": "gear-release:sha256:" + "b" * 64,
            "community_release_id": (
                "community-release:sha256:" + "c" * 64
            ),
            "catalog_revision": (
                "gear-catalog:sha256:" + "d" * 64
            ),
            "exact_registry_revision": (
                "gear-exact-registry:sha256:" + "e" * 64
            ),
        }

    def catalog(self, identities):
        variant_key = "browse-variant:sha256:" + "f" * 64
        return {
            "status": "verified",
            "catalogRevision": identities["catalog_revision"],
            "itemDefinitions": [
                {"itemId": "1001", "slot": "head"}
            ],
            "browseVariants": [{
                "browseVariantKey": variant_key,
                "itemId": "1001",
                "itemLevel": 289,
                "sourceType": "raid",
                "progressionState": {
                    "kind": "upgrade_track",
                    "trackKey": "myth",
                    "rank": 6,
                    "maxRank": 6,
                },
            }],
        }

    def payload(self, identities):
        variant_key = "browse-variant:sha256:" + "f" * 64
        groups = [
            {"slot": slot, "items": []}
            for slot in CANONICAL_GEAR_SLOTS
        ]
        groups[0]["items"] = [{
            "itemId": "1001",
            "slot": "head",
            "compatibility": {
                "classKey": "mage",
                "specKey": "frost",
                "status": "compatible",
            },
            "defaultVariantKey": variant_key,
            "variants": [{
                "variantKey": variant_key,
                "itemId": "1001",
                "itemLevel": 289,
                "sourceType": "raid",
                "status": "verified",
                "progressionState": {
                    "kind": "upgrade_track",
                    "trackKey": "myth",
                    "rank": 6,
                    "rankMax": 6,
                },
            }],
        }]
        return {
            "candidatePreview": True,
            "formalActiveManifest": False,
            "manifestRevision": identities["manifest_revision"],
            "pointerGeneration": identities["pointer_generation"],
            "gearCatalogReleaseId": identities["gear_release_id"],
            "communityTemplateReleaseId": identities[
                "community_release_id"
            ],
            "gearCatalogRevision": identities["catalog_revision"],
            "gearExactRegistryRevision": identities[
                "exact_registry_revision"
            ],
            "replacementCandidates": groups,
        }

    def slot_request(self, payload, requested_paths=None):
        def request_json(_method, path, _body, _headers):
            if requested_paths is not None:
                requested_paths.append(path)
            slot = parse_qs(urlparse(path).query)["slot"][0]
            selected = copy.deepcopy(payload)
            selected["replacementCandidates"] = [
                group
                for group in selected["replacementCandidates"]
                if group["slot"] == slot
            ]
            return 200, selected, 10.0

        return request_json

    def test_complete_spec_slot_and_catalog_universe_passes(self):
        identities = self.identities()
        payload = self.payload(identities)
        requested_paths = []

        report = run_catalog_http_completeness_matrix(
            self.slot_request(payload, requested_paths),
            catalog=self.catalog(identities),
            expected_specs=[("mage", "frost")],
            **identities,
            observed_at="2026-07-29T20:00:00+08:00",
        )

        self.assertEqual(report["status"], "pass", report)
        self.assertEqual(
            report["schemaRevision"],
            "gear-catalog-http-completeness-matrix-v2",
        )
        self.assertEqual(
            report["specCoverage"]["observedSpecSlotCount"],
            16,
        )
        self.assertEqual(
            report["catalogUniverse"]["observedItemCount"],
            1,
        )
        self.assertEqual(
            report["catalogUniverse"]["observedVariantCount"],
            1,
        )
        self.assertEqual(report["failureCount"], 0)
        self.assertEqual(len(requested_paths), 16)
        self.assertTrue(all(
            parse_qs(urlparse(path).query).get("mode") == ["slot"]
            for path in requested_paths
        ))
        self.assertEqual(
            {
                parse_qs(urlparse(path).query)["slot"][0]
                for path in requested_paths
            },
            set(CANONICAL_GEAR_SLOTS),
        )

    def test_missing_variant_and_catalog_item_fail_closed(self):
        identities = self.identities()
        payload = self.payload(identities)
        payload = copy.deepcopy(payload)
        payload["replacementCandidates"][0]["items"][0][
            "variants"
        ] = []

        report = run_catalog_http_completeness_matrix(
            self.slot_request(payload),
            catalog=self.catalog(identities),
            expected_specs=[("mage", "frost")],
            **identities,
            observed_at="2026-07-29T20:00:00+08:00",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn(
            "CATALOG_HTTP_ITEM_VARIANT_SET_INCOMPLETE",
            report["failureCodes"],
        )
        self.assertIn(
            "CATALOG_HTTP_UNIVERSE_VARIANT_MISSING",
            report["failureCodes"],
        )
        self.assertEqual(
            report["catalogUniverse"]["missingVariantSamples"],
            [{
                "browseVariantKey": (
                    "browse-variant:sha256:" + "f" * 64
                ),
                "itemId": "1001",
                "itemLevel": 289,
                "progressionKind": "",
            }],
        )


if __name__ == "__main__":
    unittest.main()

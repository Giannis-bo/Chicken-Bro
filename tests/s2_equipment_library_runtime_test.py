import copy
import unittest

from server.s2_equipment_library_runtime import (
    assemble_s2_simc_readback_report,
    build_s2_runtime_snapshot,
    materialize_s2_item,
    materialize_s2_variant,
)


def _item_definition():
    return {
        "itemId": "1001",
        "itemName": "Test Helm",
        "itemSlot": "head",
        "logicalSources": ["raid"],
        "itemIdentity": {
            "inventoryType": "HEAD",
            "isEquippable": True,
            "itemLevel": 219,
            "name": "Test Helm",
            "quality": "EPIC",
            "status": "verified",
        },
        "db2StaticFacts": {
            "InventoryType": 1,
            "ItemLevel": 219,
            "OverallQualityID": 4,
            "socketCount": 1,
        },
        "simcReadiness": "ready",
        "evidenceStatus": "verified",
    }


def _variant():
    return {
        "itemId": "1001",
        "itemSlot": "head",
        "variantKey": "s2-variant:item:1001:track:champion:6",
        "status": "verified",
        "simcReadiness": "ready",
        "trackKey": "champion",
        "rank": 6,
        "maxRank": 6,
        "canonicalSimcInput": {
            "itemId": "1001",
            "itemLevel": 300,
            "bonusIds": ["13448"],
            "slot": "head",
            "simcOptions": {
                "id": "1001",
                "ilevel": "300",
                "bonus_id": "13448",
            },
            "line": "head=s2_item,id=1001,ilevel=300,bonus_id=13448",
            "status": "verified",
        },
        "evidenceKeys": {"bonusListIds": ["13448"]},
        "sourceEligibilityStatus": "verified",
        "simcEvidence": {
            "status": "verified",
            "matrixReportId": "s2-equipment-library-simc-matrix:sha256:test",
        },
    }


def _readback():
    return {
        "head": {
            "name": "test_helm",
            "encoded_item": "test_helm,id=1001,bonus_id=13448,ilevel=300",
            "ilevel": 300,
            "intellect": 120,
            "stamina": 400,
            "haste_rating": 88,
        }
    }


class S2EquipmentLibraryRuntimeTest(unittest.TestCase):
    def test_verified_readback_materializes_resolver_ready_variant(self):
        row = materialize_s2_variant(
            _variant(),
            _item_definition(),
            _readback(),
            source_type="raid",
        )

        self.assertEqual(row["status"], "verified")
        self.assertEqual(row["itemId"], "1001")
        self.assertEqual(row["slot"], "head")
        self.assertEqual(row["itemLevel"], 300)
        self.assertEqual(row["simcOptions"], {"id": "1001", "ilevel": "300", "bonus_id": "13448"})
        self.assertEqual(
            row["payload"]["resolvedStats"],
            {"haste_rating": 88, "intellect": 120, "stamina": 400},
        )
        self.assertEqual(row["payload"]["statDeltas"], {})
        self.assertEqual(row["payload"]["simcReadbackStatus"], "verified")

    def test_identity_mismatch_is_blocked_instead_of_published(self):
        readback = _readback()
        readback["head"]["encoded_item"] = (
            "test_helm,id=1001,bonus_id=99999,ilevel=300"
        )

        row = materialize_s2_variant(
            _variant(),
            _item_definition(),
            readback,
            source_type="raid",
        )

        self.assertEqual(row["status"], "blocked")
        self.assertIn("S2_SIMC_READBACK_IDENTITY_MISMATCH", row["blockers"])
        self.assertNotIn("resolvedStats", row["payload"])

    def test_simc_plural_output_slots_are_resolved(self):
        variant = copy.deepcopy(_variant())
        variant["itemSlot"] = "wrist"
        variant["canonicalSimcInput"]["slot"] = "wrist"
        variant["canonicalSimcInput"]["line"] = (
            "wrist=s2_item,id=1001,ilevel=300,bonus_id=13448"
        )
        readback = {
            "wrists": {
                "encoded_item": "test_helm,id=1001,bonus_id=13448,ilevel=300",
                "ilevel": 300,
                "intellect": 120,
                "stamina": 400,
            }
        }

        item_definition = copy.deepcopy(_item_definition())
        item_definition["itemSlot"] = "wrist"
        row = materialize_s2_variant(
            variant,
            item_definition,
            readback,
            source_type="raid",
        )

        self.assertEqual(row["status"], "verified")
        self.assertEqual(row["payload"]["resolvedStats"]["stamina"], 400)

    def test_item_projection_keeps_db2_socket_capability_and_verified_identity(self):
        row = materialize_s2_item(
            _item_definition(),
            base_stats={"intellect": 99, "stamina": 502},
            source_refs=["s2-equipment-library-closure:sha256:test"],
        )

        self.assertEqual(row["sourceStatus"], "verified")
        self.assertEqual(row["slot"], "head")
        self.assertEqual(row["payload"]["baseStats"], {"intellect": 99, "stamina": 502})
        self.assertEqual(row["payload"]["baseCapabilities"]["socketCount"], 1)
        self.assertEqual(
            row["payload"]["sourceRefIds"],
            [
                "official-api:/data/wow/item/1001#/id",
                "s2-equipment-library-closure:sha256:test",
            ],
        )

    def test_readback_report_keeps_variant_identity_and_static_values(self):
        plan = {
            "runtimeIdentity": "simc:test-runtime",
            "candidateReportId": "s2-equipment-library-closure:sha256:test",
            "jobs": [
                {
                    "kind": "public_variant",
                    "jobKey": "public:variant-1001",
                    "variantKey": _variant()["variantKey"],
                    "itemId": "1001",
                    "slot": "head",
                    "expected": {
                        "itemId": "1001",
                        "slot": "head",
                        "bonusIds": ["13448"],
                        "itemLevel": 300,
                    },
                },
                {
                    "kind": "set_conversion_probe",
                    "jobKey": "set:ignored",
                    "variantKey": "",
                    "itemId": "",
                    "slot": "",
                    "expected": {},
                },
            ],
        }
        batches = [
            {
                "runtimeIdentityStatus": "verified",
                "runtimeIdentity": "simc:test-runtime",
                "results": [
                    {
                        "jobKey": "public:variant-1001",
                        "returncode": 0,
                        "gear": _readback(),
                        "dps": 123.0,
                        "warnings": [],
                        "stderr": "",
                    },
                    {
                        "jobKey": "set:ignored",
                        "returncode": 0,
                        "gear": {},
                    },
                ],
            }
        ]

        report = assemble_s2_simc_readback_report(plan, batches)

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["counts"], {"expected": 1, "verified": 1, "blocked": 0})
        self.assertEqual(
            report["readbacks"][_variant()["variantKey"]]["gear"],
            _readback(),
        )

    def test_runtime_snapshot_projects_only_verified_candidate_and_readback_rows(self):
        candidate = {
            "status": "verified",
            "reportId": "s2-equipment-library-closure:sha256:test",
            "itemDefinitions": [_item_definition()],
            "variants": [_variant()],
            "craftedVariantTemplates": [],
            "sourceMemberships": [
                {
                    "itemId": "1001",
                    "logicalSource": "raid",
                    "rawSourceType": "raid",
                    "rawSourceKey": "raid:journal-instance:1317:encounter:2849",
                    "scopeStatus": "included",
                    "sourceMembershipStatus": "verified",
                }
            ],
            "craftedRelationships": [],
            "tierSetMemberships": [],
            "enhancementCatalog": {"status": "verified", "options": []},
        }
        readback = {
            "status": "verified",
            "candidateReportId": candidate["reportId"],
            "runtimeIdentity": "simc:test-runtime",
            "readbacks": {
                _variant()["variantKey"]: {
                    "status": "verified",
                    "gear": _readback(),
                }
            },
        }

        snapshot = build_s2_runtime_snapshot(
            candidate,
            readback,
            official_items={
                "1001": {
                    "name": "Test Helm",
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "INTELLECT"}, "value": 99},
                            {"type": {"type": "STAMINA"}, "value": 502},
                        ]
                    },
                }
            },
            season_revision="season-midnight-season-2:test",
        )

        self.assertEqual(snapshot["status"], "verified")
        self.assertEqual(len(snapshot["items"]), 1)
        self.assertEqual(len(snapshot["sources"]), 1)
        self.assertEqual(len(snapshot["variants"]), 1)
        self.assertEqual(snapshot["variants"][0]["status"], "verified")
        self.assertEqual(
            snapshot["variants"][0]["payload"]["resolvedStats"]["haste_rating"],
            88,
        )


if __name__ == "__main__":
    unittest.main()

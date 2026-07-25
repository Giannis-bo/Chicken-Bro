import copy
import unittest

from server.observed_build_projection import (
    build_dependency_vector,
    build_projection,
)
from server.observed_build_read_model import (
    gear_import_source_from_active_record,
    gear_templates_from_active_records,
    talent_templates_from_active_records,
)
from server.observed_build_registry import build_observed_snapshot


class ObservedBuildReadModelTest(unittest.TestCase):
    def dependencies(self):
        return build_dependency_vector(
            season_revision="season-tww-3",
            talent_catalog_revision="talent-catalog-v7",
            gear_release_id="gear-release:sha256:" + "1" * 64,
            gear_rule_revision="gear-rule-matrix-v1",
            resolver_contract_revision="gear-resolver-contract-v1",
            serializer_revision="websim-profile-compat-v1",
            simc_runtime_revision="simc-runtime-abc",
            selection_schema_revision="selection-intent-v1",
            projection_schema_revision="observed-build-projection-v2",
        )

    def active_record(
        self,
        *,
        hero="frostfire",
        player="player-a",
        item_id=230001,
        stale=False,
    ):
        profile_url = (
            f"https://raider.io/characters/cn/realm-a/{player}"
        )
        snapshot = build_observed_snapshot(
            slot={
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": hero,
                "scenarioKey": "mythic_plus",
            },
            source={
                "sourceKey": "raiderio",
                "sourceIdentity": f"raiderio:cn|realm-a|{player}",
                "profileUrl": profile_url,
                "region": "cn",
                "realm": "realm-a",
                "character": player,
            },
            ranking_evidence={
                "rank": 1,
                "score": 4200,
                "maxKeyLevel": 22,
            },
            talent_observation={
                "rawImportCode": f"RAW-{player}",
                "loadout": [{"traitId": 91001, "rank": 1}],
            },
            gear_observation={
                "gearItems": [
                    {
                        "slot": "head",
                        "itemId": item_id,
                        "itemLevel": 710,
                        "name": f"Observed Helm {player}",
                        "iconUrl": "https://render.worldofwarcraft.com/icons/helm.jpg",
                    }
                ]
            },
            source_revision="raiderio:season-tww-3:observed-profile-v1",
        )
        selection_intent = {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-tww-3",
                "gearCatalogRevision": self.dependencies()["gearReleaseId"],
            },
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "frost",
                "level": 90,
            },
            "slots": {
                "head": {
                    "itemId": str(item_id),
                    "variantKey": f"variant-{player}",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }
        projection = build_projection(
            snapshot=snapshot,
            dependency_vector=self.dependencies(),
            talent_projection={
                "status": "verified",
                "heroKey": hero,
                "talentState": {
                    "selectedNodes": [{"id": "node-a", "rank": 1}]
                },
                "rawImportCode": f"RAW-{player}",
                "websimExportCode": f"websim:mage:frost:{hero}:encoded",
                "signature": f"talent-{player}",
            },
            gear_projection={
                "status": "verified",
                "selectionIntent": selection_intent,
                "gearItems": [
                    {
                        "slot": "head",
                        "itemId": str(item_id),
                        "variantKey": f"variant-{player}",
                        "simcOptions": {"ilevel": "710"},
                    }
                ],
                "enhancementBySlot": {},
                "resolvedGearSignature": "sha256:" + "2" * 64,
            },
            profile_readiness={
                "status": "verified",
                "simcReady": True,
                "profileSignature": "sha256:" + "3" * 64,
            },
        )
        return {
            "active": {
                "scope": "candidate",
                "templateSetId": "template-set:sha256:" + "4" * 64,
                "generation": 7,
            },
            "entry": {
                "slot": snapshot["slot"],
                "slotKey": projection["slotKey"],
                "status": "stale_lkg" if stale else "verified",
                "snapshotId": snapshot["snapshotId"],
                "projectionId": projection["projectionId"],
                "sourceIdentity": snapshot["source"]["sourceIdentity"],
                "problem": (
                    {"code": "new_snapshot_mapping_failed"}
                    if stale
                    else {}
                ),
            },
            "snapshot": snapshot,
            "projection": projection,
        }

    def test_one_active_record_projects_to_matching_talent_and_gear_identity(self):
        record = self.active_record()

        talent = talent_templates_from_active_records([record])[0]
        gear = gear_templates_from_active_records([record])[0]

        for field in (
            "templateSetId",
            "snapshotId",
            "sourceIdentity",
            "playerName",
            "heroKey",
        ):
            self.assertEqual(talent[field], gear[field])
        self.assertTrue(talent["canApplyVisual"])
        self.assertTrue(gear["canApplyGear"])
        self.assertEqual(talent["id"], record["projection"]["projectionId"])
        self.assertEqual(gear["id"], record["projection"]["projectionId"])

    def test_one_spec_projects_exactly_two_distinct_gear_templates(self):
        templates = gear_templates_from_active_records(
            [
                self.active_record(),
                self.active_record(
                    hero="spellslinger",
                    player="player-b",
                    item_id=230002,
                ),
            ]
        )

        self.assertEqual(len(templates), 2)
        self.assertEqual(
            len({item["sourceIdentity"] for item in templates}),
            2,
        )
        self.assertEqual(len({item["heroKey"] for item in templates}), 2)

    def test_gear_templates_satisfy_existing_public_hero_projection_gate(self):
        from server.gear_public_contract import (
            is_public_hero_gear_projection,
        )

        template = gear_templates_from_active_records(
            [self.active_record()]
        )[0]

        self.assertEqual(template["status"], "complete")
        self.assertTrue(is_public_hero_gear_projection(template))

    def test_talent_filter_returns_one_exact_hero_template(self):
        records = [
            self.active_record(),
            self.active_record(
                hero="spellslinger",
                player="player-b",
                item_id=230002,
            ),
        ]

        templates = talent_templates_from_active_records(
            records,
            hero_key="spellslinger",
        )

        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["heroKey"], "spellslinger")

    def test_lkg_remains_importable_and_is_explicitly_stale(self):
        record = self.active_record(stale=True)

        talent = talent_templates_from_active_records([record])[0]
        gear = gear_templates_from_active_records([record])[0]

        self.assertTrue(talent["canApplyVisual"])
        self.assertTrue(gear["canApplyGear"])
        self.assertTrue(talent["isStale"])
        self.assertEqual(gear["freshnessStatus"], "stale")

    def test_exact_import_source_is_bound_to_active_projection_and_observed_items(self):
        record = self.active_record()

        source = gear_import_source_from_active_record(record)

        self.assertEqual(source["status"], "verified")
        self.assertEqual(
            source["selectionIntent"],
            record["projection"]["gearProjection"]["selectionIntent"],
        )
        self.assertEqual(
            source["template"]["id"],
            record["projection"]["projectionId"],
        )
        self.assertEqual(
            source["importedGearBySlot"]["head"]["itemId"],
            "230001",
        )
        self.assertEqual(
            source["importedGearBySlot"]["head"]["variantKey"],
            "variant-player-a",
        )

    def test_mismatched_projection_identity_fails_closed(self):
        record = self.active_record()
        tampered = copy.deepcopy(record)
        tampered["projection"]["sourceIdentity"] = (
            "raiderio:cn|realm-a|other"
        )

        with self.assertRaisesRegex(ValueError, "identity"):
            talent_templates_from_active_records([tampered])

    def test_incomplete_exact_variant_is_not_public_or_importable(self):
        record = self.active_record()
        incomplete = copy.deepcopy(record)
        incomplete["projection"]["gearProjection"]["selectionIntent"]["slots"]["head"]["variantKey"] = ""
        incomplete["projection"]["gearProjection"]["gearItems"][0]["variantKey"] = ""

        self.assertEqual(gear_templates_from_active_records([incomplete]), [])
        with self.assertRaisesRegex(ValueError, "exact variant"):
            gear_import_source_from_active_record(incomplete)


if __name__ == "__main__":
    unittest.main()

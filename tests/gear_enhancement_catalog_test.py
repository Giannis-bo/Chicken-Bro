import copy
import unittest


class GearEnhancementCatalogTest(unittest.TestCase):
    season_revision = "season-midnight-season-2:fixture"

    def binding(self):
        return {
            "seasonId": "midnight-season-2",
            "seasonRevision": self.season_revision,
            "scope": "end_game",
            "status": "verified",
        }

    def official_items(self):
        return {
            "300001": {
                "itemClass": "gem",
                "name": "S2 Quick Gem",
                "statSummary": "急速 +10",
                "sourceStatus": "verified",
                "seasonRevision": self.season_revision,
            },
            "400001": {
                "itemClass": "enchant",
                "name": "S2 Weapon Enchant",
                "statSummary": "武器：主属性 +20",
                "sourceStatus": "verified",
                "seasonRevision": self.season_revision,
            },
            "500001": {
                "itemClass": "embellishment",
                "name": "S2 Crafted Intrinsic Effect",
                "statSummary": "制造装备内置效果",
                "sourceStatus": "verified",
                "managementMode": "source_only",
                "seasonRevision": self.season_revision,
            },
        }

    def variant(self):
        return {
            "variantKey": "s2-variant-1",
            "itemId": "1001",
            "seasonRevision": self.season_revision,
            "socketCount": 1,
            "slot": "head",
            "simcOptions": {
                "gem_id": "300001",
                "enchant_id": "400001",
                "embellishment": "500001",
            },
        }

    def test_builds_s2_gem_enchant_and_embellishment_catalog(self):
        from server.gear_enhancement_catalog import (
            build_enhancement_option_catalog,
        )

        result = build_enhancement_option_catalog(
            season_binding=self.binding(),
            official_items=self.official_items(),
            variants=[self.variant()],
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["seasonRevision"], self.season_revision)
        self.assertEqual(
            {row["optionType"] for row in result["options"]},
            {"socket", "enchant", "embellishment"},
        )
        self.assertTrue(result["optionRevision"].startswith("s2-options:sha256:"))
        self.assertTrue(
            all(row["seasonRevision"] == self.season_revision for row in result["options"])
        )
        intrinsic = next(
            row
            for row in result["options"]
            if row["optionKey"] == "embellishment-500001"
        )
        self.assertEqual(intrinsic["managementMode"], "source_only")
        self.assertFalse(intrinsic["editorManaged"])
        self.assertFalse(intrinsic["isVisible"])

    def test_unknown_token_is_blocked_instead_of_dropped(self):
        from server.gear_enhancement_catalog import (
            build_enhancement_option_catalog,
        )

        variant = self.variant()
        variant["simcOptions"]["gem_id"] = "399999"
        result = build_enhancement_option_catalog(
            season_binding=self.binding(),
            official_items=self.official_items(),
            variants=[variant],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn("ENHANCEMENT_OFFICIAL_METADATA_MISSING", result["blockerCodes"])
        self.assertEqual(result["coverage"]["blockedOptionCount"], 1)

    def test_gem_capacity_and_cross_season_metadata_block_promotion(self):
        from server.gear_enhancement_catalog import (
            build_enhancement_option_catalog,
        )

        too_many = self.variant()
        too_many["simcOptions"]["gem_id"] = "300001/300001"
        too_many["socketCount"] = 1
        result = build_enhancement_option_catalog(
            season_binding=self.binding(),
            official_items=self.official_items(),
            variants=[too_many],
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("ENHANCEMENT_SOCKET_CAPACITY_EXCEEDED", result["blockerCodes"])

        cross_season_items = copy.deepcopy(self.official_items())
        cross_season_items["300001"]["seasonRevision"] = "season-midnight-season-1:legacy"
        result = build_enhancement_option_catalog(
            season_binding=self.binding(),
            official_items=cross_season_items,
            variants=[self.variant()],
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("ENHANCEMENT_SEASON_REVISION_MISMATCH", result["blockerCodes"])

    def test_s2_release_materializer_uses_catalog_and_does_not_expose_source_only(self):
        from server.gear_enhancement_catalog import (
            build_enhancement_option_catalog,
        )
        from server.gear_release_tool import _materialize_enhancement_management
        from server.gear_socket_authority import CAPABILITY_REVISION

        catalog = build_enhancement_option_catalog(
            season_binding=self.binding(),
            official_items=self.official_items(),
            variants=[self.variant()],
        )
        snapshot = {
            "seasonRevision": self.season_revision,
            "items": [
                {
                    "itemId": "1001",
                    "slot": "head",
                    "payload": {
                        "baseCapabilities": {
                            "socketCount": 1,
                            "canEnchant": True,
                            "canEmbellish": True,
                        }
                    },
                }
            ],
            "variants": [
                {
                    "itemId": "1001",
                    "variantKey": "s2-variant-1",
                    "slot": "head",
                    "sourceType": "official",
                    "status": "verified",
                    "itemLevel": 305,
                    "simcOptions": self.variant()["simcOptions"],
                    "payload": {},
                }
            ],
            "options": [
                {
                    "optionId": "forged",
                    "optionKey": "gem-300001",
                    "optionType": "socket",
                    "simcOptions": {"gem_id": "300001"},
                    "status": "verified",
                    "isVisible": True,
                    "payload": {"displayName": "forged"},
                }
            ],
        }

        materialized = _materialize_enhancement_management(
            snapshot,
            CAPABILITY_REVISION,
            enhancement_catalog=catalog,
            season_revision=self.season_revision,
        )

        gem = next(
            row for row in materialized["options"] if row.get("optionKey") == "gem-300001"
        )
        self.assertEqual(gem["optionId"], "s2-socket-300001")
        self.assertNotEqual(gem["payload"].get("displayName"), "forged")
        self.assertFalse(
            any(
                row.get("optionKey") == "embellishment-500001"
                and row.get("isVisible") is True
                for row in materialized["options"]
            )
        )

    def test_s2_materializer_without_option_catalog_is_blocked(self):
        from server.gear_release_tool import GearReleaseIntegrityError, _materialize_enhancement_management
        from server.gear_socket_authority import CAPABILITY_REVISION

        with self.assertRaisesRegex(
            GearReleaseIntegrityError,
            "S2 enhancement option catalog is required",
        ):
            _materialize_enhancement_management(
                {"seasonRevision": self.season_revision, "items": [], "variants": [], "options": []},
                CAPABILITY_REVISION,
                season_revision=self.season_revision,
            )


if __name__ == "__main__":
    unittest.main()

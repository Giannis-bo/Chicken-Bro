import copy
import unittest

from server.season_endgame_candidate import build_season_endgame_candidate


S2_REVISION = "season-midnight-season-2:fixture"
SIMC_REVISION = "simc:12.1.0.69214:abc"
GEAR_RULE_REVISION = "midnight-season-2-gear-rule-v1"
TRACK_REVISION = "midnight-season-2-track-authority-v1"


def repository():
    return {
        "seasonId": "midnight-season-2",
        "scope": "end_game",
        "seasonRevision": S2_REVISION,
        "sourcePolicyRevision": "midnight-season-2-pve-source-policy-v1",
        "captureRevision": "capture-s2-fixture",
        "clientBuild": "12.1.0.69214",
        "simcRuntimeRevision": SIMC_REVISION,
        "sourceKeys": ["raid:venomous-abyss"],
        "captureManifest": {
            "status": "verified",
            "files": [{"path": "raw/s2.json", "sha256": "a" * 64}],
        },
    }


def option_catalog():
    return {
        "schemaRevision": "gear-enhancement-option-catalog-v1",
        "status": "verified",
        "seasonRevision": S2_REVISION,
        "optionRevision": "s2-options:sha256:" + "b" * 64,
        "options": [],
        "blockedOptions": [],
    }


def set_membership():
    return {
        "schemaRevision": "season-set-membership-v1",
        "status": "verified",
        "seasonRevision": S2_REVISION,
        "setMembershipRevision": "s2-sets:sha256:" + "c" * 64,
        "sets": [{
            "setId": "1983",
            "itemSetId": "1983",
            "setName": "Abyssal Regalia",
            "classKeys": ["mage"],
            "itemIds": ["1001"],
            "sourceRefs": ["blizzard:s2-tier-set"],
            "setBonusEvidence": [],
            "seasonRevision": S2_REVISION,
            "status": "verified",
        }],
        "itemsById": {
            "1001": {
                "itemId": "1001",
                "itemSetId": "1983",
                "setId": "1983",
                "seasonRevision": S2_REVISION,
                "status": "verified",
            }
        },
        "blockedItemIds": [],
    }


def track_authority():
    return {
        "schemaRevision": "gear-track-authority-v1",
        "status": "verified",
        "ruleRevision": TRACK_REVISION,
        "trackAuthorityRevision": TRACK_REVISION,
        "seasonRevision": S2_REVISION,
        "gearRuleRevision": GEAR_RULE_REVISION,
        "records": [{
            "recordKey": "hero-6",
            "publicTrackKey": "hero",
            "progressionKind": "upgrade_track",
            "rank": 6,
            "maxRank": 6,
            "itemLevel": 315,
            "eligibleSourceTypes": ["raid", "observed_profile"],
            "eligibleSlots": ["head"],
            "sourceRefIds": ["blizzard:s2-track", "simc:s2-track"],
            "bonusIds": ["s2-hero-6"],
            "evidenceStatus": "verified",
            "seasonRevision": S2_REVISION,
            "gearRuleRevision": GEAR_RULE_REVISION,
            "trackAuthorityRevision": TRACK_REVISION,
        }],
    }


def gear_snapshot():
    return {
        "seasonRevision": S2_REVISION,
        "dependencyVector": {
            "gearRuleRevision": GEAR_RULE_REVISION,
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "websim-profile-compat-v1",
            "simcRuntimeRevision": SIMC_REVISION,
            "statPolicyRevision": "stat-snapshot-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": "gear-socket-authority-v2",
        },
        "items": [{
            "itemId": "1001",
            "name": "S2 Helm",
            "slot": "head",
            "itemLevel": 315,
            "sourceStatus": "verified",
            "hasSourceRefs": True,
            "hasVariantRefs": True,
            "payload": {
                "armorType": "Cloth",
                "inventoryType": "head",
                "itemSetId": "1983",
            },
        }],
        "sources": [{
            "sourceId": "source-1001-s2",
            "itemId": "1001",
            "sourceType": "raid",
            "sourceKey": "raid:venomous-abyss",
            "seasonRevision": S2_REVISION,
            "status": "verified",
        }],
        "variants": [
            {
                "variantId": "browse-hero-6",
                "variantKey": "hero-6",
                "itemId": "1001",
                "rowFamily": "browse",
                "trackKey": "hero",
                "trackRank": 6,
                "itemLevel": 315,
                "slot": "head",
                "sourceType": "raid",
                "bonusIds": ["s2-hero-6"],
                "staticStats": {"stamina": 120},
                "status": "verified",
            },
            {
                "variantId": "exact-hero-6",
                "variantKey": "observed-hero-6",
                "itemId": "1001",
                "rowFamily": "exact_instance",
                "itemLevel": 315,
                "slot": "head",
                "sourceType": "observed_profile",
                "bonusIds": ["s2-hero-6"],
                "staticStats": {"stamina": 120},
                "simcOptions": {"ilevel": "315", "bonus_id": "s2-hero-6"},
                "status": "verified",
            },
        ],
        "options": [],
        "communityTemplates": [{
            "templateId": "community-s2-mage",
            "classKey": "mage",
            "specKey": "arcane",
            "gearItems": [{
                "slot": "head",
                "itemId": "1001",
                "variantKey": "observed-hero-6",
            }],
        }],
        "personalTemplates": [],
    }


def candidate(**overrides):
    values = {
        "repository": repository(),
        "gear_snapshot": gear_snapshot(),
        "option_catalog": option_catalog(),
        "set_membership": set_membership(),
        "track_authority": track_authority(),
        "simc_runtime_revision": SIMC_REVISION,
    }
    values.update(overrides)
    return build_season_endgame_candidate(**values)


class SeasonEndgameCandidateTest(unittest.TestCase):
    def test_builds_candidate_release_catalog_and_exact_registry_without_pointer_mutation(self):
        result = candidate()

        self.assertEqual(result["status"], "candidate")
        self.assertEqual(result["seasonRevision"], S2_REVISION)
        self.assertFalse(result["activePointerChanged"])
        self.assertTrue(result["candidateOnly"])
        self.assertRegex(result["gearRelease"]["releaseId"], r"^gear-release:sha256:")
        self.assertRegex(result["catalog"]["catalogRevision"], r"^gear-catalog:sha256:")
        self.assertRegex(result["exactRegistry"]["registryRevision"], r"^gear-exact-registry:sha256:")
        self.assertEqual(result["dependencyVector"]["optionRevision"], option_catalog()["optionRevision"])
        self.assertEqual(result["dependencyVector"]["setMembershipRevision"], set_membership()["setMembershipRevision"])
        self.assertEqual(result["dependencyVector"]["trackAuthorityRevision"], TRACK_REVISION)

    def test_mixed_season_revision_is_blocked(self):
        mixed = option_catalog()
        mixed["seasonRevision"] = "season-17-f131dd36ddf1"

        result = candidate(option_catalog=mixed)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("S2_CANDIDATE_SEASON_REVISION_MIXED", result["problemCodes"])
        self.assertFalse(result["activePointerChanged"])

    def test_missing_option_revision_is_blocked(self):
        missing = option_catalog()
        missing["optionRevision"] = ""

        result = candidate(option_catalog=missing)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("S2_OPTION_REVISION_MISSING", result["problemCodes"])

    def test_missing_track_authority_is_blocked(self):
        missing = {"status": "blocked", "problems": [{"code": "TRACK_AUTHORITY_RECORDS_MISSING"}]}

        result = candidate(track_authority=missing)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("S2_TRACK_AUTHORITY_UNAVAILABLE", result["problemCodes"])

    def test_exact_instance_cannot_enter_browse_variants(self):
        snapshot = gear_snapshot()
        snapshot["variants"][0]["rowFamily"] = "exact_instance"

        result = candidate(gear_snapshot=snapshot)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("S2_EXACT_INSTANCE_BROWSE_LEAK", result["problemCodes"])

    def test_duplicate_progression_shape_is_blocked(self):
        snapshot = gear_snapshot()
        duplicate = copy.deepcopy(snapshot["variants"][0])
        duplicate["variantId"] = "browse-hero-6-duplicate"
        duplicate["variantKey"] = "hero-6-duplicate"
        snapshot["variants"].append(duplicate)

        result = candidate(gear_snapshot=snapshot)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("CATALOG_BROWSE_VARIANT_SHAPE_DUPLICATE", result["problemCodes"])


if __name__ == "__main__":
    unittest.main()

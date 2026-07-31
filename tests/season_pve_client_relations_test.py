import io
import json
import unittest

from server.season_pve_client_relations import (
    ClientRelationEvidenceError,
    audit_public_tact_key_reextract,
    audit_current_client_tact_key_coverage,
    audit_current_client_progression_evidence,
    audit_unverified_source_membership_relations,
    classify_client_item_equip_eligibility,
    classify_current_client_crafted_candidate,
    compare_crafted_recipe_membership,
    resolve_crafted_recipe_outputs,
    select_midnight_profession_spell_targets,
    wdc5_tact_key_id_to_blte_key_id,
    write_ephemeral_tact_keyfile,
)


class SeasonPveClientRelationsTest(unittest.TestCase):
    def test_public_tact_key_reextract_stays_blocked_when_static_payload_is_unchanged(self):
        result = audit_public_tact_key_reextract(
            public_key_coverage={
                "status": "blocked",
                "summary": {
                    "targetKeyCount": 12,
                    "targetRecordCount": 178,
                    "availableTargetKeyCount": 9,
                    "missingTargetKeyCount": 3,
                    "coveredTargetRecordCount": 114,
                    "missingTargetRecordCount": 64,
                },
                "targetKeys": [
                    {
                        "tactKeyId": f"{index:016x}",
                        "recordCount": 1,
                    }
                    for index in range(1, 13)
                ],
            },
            blte_encryption_audit={
                "salsa20Available": True,
                "encryptedChunkCount": 20,
                "keyAvailableChunkCount": 17,
                "decryptedChunkCount": 17,
                "zeroFallbackChunkCount": 3,
                "keyAudits": [
                    {
                        "keyId": bytes.fromhex(
                            f"{index + 1:016x}"
                        )[::-1].hex(),
                        "chunkCount": 5 if index < 2 else 1,
                        "outputBytes": 100,
                        "keyAvailableChunkCount": (
                            5 if index < 2 else 1
                        )
                        if index < 9
                        else 0,
                        "decryptedChunkCount": (
                            5 if index < 2 else 1
                        )
                        if index < 9
                        else 0,
                    }
                    for index in range(12)
                ],
            },
            table_comparisons=[
                {
                    "table": "CollectableSourceInfo",
                    "originalSha256": "1" * 64,
                    "reextractedSha256": "a" * 64,
                    "encryptedRecordCount": 6,
                    "availableEncryptedRecordCount": 6,
                },
                {
                    "table": "CollectableSourceVendor",
                    "originalSha256": "2" * 64,
                    "reextractedSha256": "b" * 64,
                    "encryptedRecordCount": 17,
                    "availableEncryptedRecordCount": 17,
                },
                {
                    "table": "CollectableSourceVendorSparse",
                    "originalSha256": "3" * 64,
                    "reextractedSha256": "c" * 64,
                    "encryptedRecordCount": 17,
                    "availableEncryptedRecordCount": 17,
                },
                {
                    "table": "ItemModifiedAppearance",
                    "originalSha256": "4" * 64,
                    "reextractedSha256": "d" * 64,
                    "encryptedRecordCount": 138,
                    "availableEncryptedRecordCount": 74,
                },
            ],
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["summary"]["changedTableCount"], 4)
        self.assertEqual(
            result["summary"][
                "publicRecordTactKeyCoveredRecordCount"
            ],
            114,
        )
        self.assertEqual(
            result["summary"]["recordTactKeyToBlteKeyOverlapCount"],
            12,
        )
        self.assertEqual(result["summary"]["blteKeyCount"], 12)
        self.assertEqual(
            result["summary"]["blteEncryptedChunkCount"],
            20,
        )
        self.assertEqual(
            result["summary"]["blteDecryptedChunkCount"],
            17,
        )
        self.assertEqual(
            result["summary"]["recoveredEncryptedRecordCount"],
            114,
        )
        self.assertEqual(
            result["summary"]["unavailableEncryptedRecordCount"],
            64,
        )
        self.assertEqual(
            result["blockers"],
            [
                "APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE",
                "CURRENT_CLIENT_BLTE_DECRYPTION_KEYS_UNAVAILABLE",
                "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
            ],
        )

    def test_ephemeral_tact_keyfile_selects_only_target_keys_and_redacts_audit(self):
        destination = io.StringIO()

        audit = write_ephemeral_tact_keyfile(
            base_key_entries=[
                {
                    "id": 15,
                    "key_id": "ABCDEF0123456789",
                    "key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                },
                {
                    "id": 16,
                    "key_id": "3333333333333333",
                    "key": None,
                },
            ],
            approved_public_key_lines=[
                "BE7D592CD36508A2 0102030405060708090A0B0C0D0E0F10\n",
                "2222222222222222 BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB\n",
            ],
            target_keys=[
                {
                    "tactKeyId": "be7d592cd36508a2",
                    "recordCount": 3,
                    "tables": ["CollectableSourceVendor"],
                },
                {
                    "tactKeyId": "dd9ea834c9585585",
                    "recordCount": 14,
                    "tables": ["ItemModifiedAppearance"],
                },
            ],
            destination=destination,
        )

        self.assertTrue(destination.getvalue())
        self.assertEqual(
            json.loads(destination.getvalue()),
            [
                {
                    "id": 15,
                    "key_id": "abcdef0123456789",
                    "key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                },
                {
                    "id": 16,
                    "key_id": "3333333333333333",
                    "key": None,
                },
                {
                    "id": 17,
                    "key_id": "a20865d32c597dbe",
                    "key": "0102030405060708090A0B0C0D0E0F10",
                },
            ],
        )
        self.assertEqual(audit["status"], "blocked")
        self.assertEqual(audit["summary"]["baseEntryCount"], 2)
        self.assertEqual(audit["summary"]["baseUsableKeyCount"], 1)
        self.assertEqual(audit["summary"]["approvedPublicKeyCount"], 2)
        self.assertEqual(audit["summary"]["targetKeyCount"], 2)
        self.assertEqual(audit["summary"]["addedTargetKeyCount"], 1)
        self.assertEqual(audit["summary"]["coveredTargetRecordCount"], 3)
        self.assertEqual(audit["summary"]["missingTargetRecordCount"], 14)
        self.assertEqual(
            audit["blockers"],
            ["APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE"],
        )
        self.assertNotIn(
            "0102030405060708090A0B0C0D0E0F10",
            str(audit),
        )
        self.assertNotIn(
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            destination.getvalue(),
        )

    def test_wdc5_tact_key_id_maps_to_blte_byte_order(self):
        self.assertEqual(
            wdc5_tact_key_id_to_blte_key_id(
                "be7d592cd36508a2"
            ),
            "a20865d32c597dbe",
        )
        with self.assertRaises(ClientRelationEvidenceError):
            wdc5_tact_key_id_to_blte_key_id("not-a-key")

    def test_ephemeral_tact_keyfile_rejects_conflicting_public_keys_before_write(self):
        destination = io.StringIO()

        with self.assertRaisesRegex(
            ClientRelationEvidenceError,
            "conflicting approved public TACT key",
        ):
            write_ephemeral_tact_keyfile(
                base_key_entries=[],
                approved_public_key_lines=[
                    "BE7D592CD36508A2 0102030405060708090A0B0C0D0E0F10\n",
                    "BE7D592CD36508A2 FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF\n",
                ],
                target_keys=[
                    {
                        "tactKeyId": "be7d592cd36508a2",
                        "recordCount": 3,
                        "tables": ["CollectableSourceVendor"],
                    },
                ],
                destination=destination,
            )

        self.assertEqual(destination.getvalue(), "")

    def test_current_client_tact_key_coverage_never_emits_key_material(self):
        result = audit_current_client_tact_key_coverage(
            tact_keys=[
                {
                    "id": "7",
                    **{
                        f"key_{index}": str(index)
                        for index in range(1, 17)
                    },
                }
            ],
            tact_key_lookups=[
                {
                    "id": "7",
                    **{
                        f"key_name_{index}": str(value)
                        for index, value in enumerate(
                            bytes.fromhex("be7d592cd36508a2"),
                            start=1,
                        )
                    },
                },
                {
                    "id": "8",
                    **{
                        f"key_name_{index}": str(value)
                        for index, value in enumerate(
                            bytes.fromhex("dd9ea834c9585585"),
                            start=1,
                        )
                    },
                },
            ],
            encrypted_sections=[
                {
                    "table": "CollectableSourceVendor",
                    "tactKeyId": "be7d592cd36508a2",
                    "recordCount": 3,
                },
                {
                    "table": "CollectableSourceVendor",
                    "tactKeyId": "dd9ea834c9585585",
                    "recordCount": 14,
                },
            ],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["summary"]["targetKeyCount"], 2)
        self.assertEqual(result["summary"]["targetRecordCount"], 17)
        self.assertEqual(result["summary"]["presentTargetKeyCount"], 1)
        self.assertEqual(result["summary"]["coveredTargetRecordCount"], 3)
        self.assertEqual(result["summary"]["missingTargetRecordCount"], 14)
        self.assertEqual(
            result["targetKeys"],
            [
                {
                    "tactKeyId": "be7d592cd36508a2",
                    "recordCount": 3,
                    "tables": ["CollectableSourceVendor"],
                    "presentInCurrentClientStaticTables": True,
                },
                {
                    "tactKeyId": "dd9ea834c9585585",
                    "recordCount": 14,
                    "tables": ["CollectableSourceVendor"],
                    "presentInCurrentClientStaticTables": False,
                },
            ],
        )
        self.assertNotIn("keyMaterial", str(result))
        self.assertNotIn("01020304050607080910111213141516", str(result))

    def test_unverified_source_relations_never_promote_membership(self):
        result = audit_unverified_source_membership_relations(
            collectable_vendor=[
                {
                    "id": "1",
                    "unverified_field_10_1_5_49595_001": "-1",
                    "id_parent": "68",
                }
            ],
            collectable_source_info=[
                {
                    "id": "68",
                    "unverified_source_type_enum": "3",
                    "unverified_item_modified_appearance_id": "19",
                    "unverified_description": "Item Appearance",
                }
            ],
            item_modified_appearances=[
                {
                    "id": "19",
                    "id_item": "260001",
                }
            ],
            quest_package_items=[
                {
                    "id": "43",
                    "package_id": "15",
                    "item_id": "260002",
                    "item_quantity": "1",
                    "display_type": "1",
                }
            ],
            official_items=[
                {
                    "itemId": "260001",
                    "name": "Vendor candidate",
                    "requiredLevel": 90,
                    "sourceKeys": [],
                },
                {
                    "itemId": "260002",
                    "name": "Quest package candidate",
                    "requiredLevel": 90,
                    "sourceKeys": [],
                },
            ],
            unparsed_encrypted_record_count=17,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["summary"]["promotableMemberCount"], 0)
        self.assertEqual(result["summary"]["vendorCandidateItemCount"], 1)
        self.assertEqual(
            result["summary"]["questPackageCandidateItemCount"],
            1,
        )
        self.assertEqual(
            result["vendorCandidates"][0]["outcome"],
            "unverified_not_promotable",
        )
        self.assertEqual(
            result["questPackageCandidates"][0]["outcome"],
            "unverified_not_promotable",
        )
        self.assertEqual(
            result["blockers"],
            [
                "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
                "CURRENT_QUEST_PACKAGE_RELATION_UNAVAILABLE",
                "CURRENT_SEASON_PVE_VENDOR_IDENTITY_UNAVAILABLE",
                "THIRD_PARTY_SCHEMA_FIELDS_UNVERIFIED",
            ],
        )

    def test_progression_evidence_remains_blocked_without_direct_run_and_vendor_item_relations(self):
        result = audit_current_client_progression_evidence(
            mythic_plus_seasons=[
                {
                    "id": "117",
                    "milestone_season": "105",
                    "id_expansion": "11",
                },
                {
                    "id": "118",
                    "milestone_season": "103",
                    "id_expansion": "11",
                },
            ],
            mythic_plus_reward_levels=[
                {
                    "id": str(index),
                    "id_mythic_plus_season": "117",
                    "id_activity_tier": "103",
                    "difficulty_level": str(key_level),
                    "weekly_reward_level": str(item_level),
                    "end_of_run_reward_level": "0",
                }
                for index, (key_level, item_level) in enumerate(
                    [
                        (2, 259),
                        (3, 259),
                        (4, 263),
                        (5, 263),
                        (6, 266),
                        (7, 269),
                        (8, 269),
                        (9, 269),
                        (10, 272),
                    ],
                    start=1,
                )
            ],
            renown_rewards=[
                {
                    "id": "1647",
                    "name": "Armor Reserves II",
                    "desc": "Acquire a powerful necklace. Requires level 90.",
                    "desc2": "Necklace Available",
                    "id_covenant": "37",
                    "level": "9",
                    "id_item": "0",
                },
                {
                    "id": "1706",
                    "name": "Hara'ti Armory",
                    "desc": "Acquire a powerful Waist armor piece. Requires level 90.",
                    "desc2": "Waist Armor Available",
                    "id_covenant": "38",
                    "level": "8",
                    "id_item": "0",
                },
                {
                    "id": "1787",
                    "name": "Silvermoon Armory II",
                    "desc": "Acquire a powerful head piece. Requires level 90.",
                    "desc2": "Head Armor Available",
                    "id_covenant": "39",
                    "level": "9",
                    "id_item": "0",
                },
                {
                    "id": "1755",
                    "name": "Power of the Voidstorm",
                    "desc": "Acquire a powerful trinket. Requires level 90.",
                    "desc2": "Trinket Available",
                    "id_covenant": "41",
                    "level": "7",
                    "id_item": "0",
                },
                {
                    "id": "1629",
                    "name": "From Champion to Hero",
                    "desc": "Tier 11 Bountiful Coffers can provide Hero equipment.",
                    "desc2": "Delve Vendor Zah'ran Upgraded",
                    "id_covenant": "36",
                    "level": "9",
                    "id_item": "0",
                },
            ],
            item_bonus_seasons=[
                {"id": "8", "id_season": "23"},
            ],
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["mythicPlus"]["candidateSeasonIds"], ["117"])
        self.assertEqual(result["mythicPlus"]["keyLevelCount"], 9)
        self.assertEqual(
            result["mythicPlus"]["weeklyRewardRows"][-1],
            {
                "keyLevel": 10,
                "weeklyRewardItemLevel": 272,
                "endOfRunRewardItemLevel": 0,
            },
        )
        self.assertEqual(result["renown"]["powerUnlockCount"], 4)
        self.assertEqual(result["renown"]["resolvedPowerItemCount"], 0)
        self.assertEqual(result["renown"]["delveProgressionUnlockCount"], 1)
        self.assertEqual(
            result["blockers"],
            [
                "CURRENT_CLIENT_DIRECT_RUN_REWARD_LEVEL_UNAVAILABLE",
                "CURRENT_CLIENT_MYTHIC_PLUS_SEASON_AUTHORITY_JOIN_UNAVAILABLE",
                "CURRENT_CLIENT_RENOWN_POWER_ITEM_ID_UNAVAILABLE",
            ],
        )

    def test_excludes_pvp_profession_utility_and_powerless_crafted_items(self):
        base_item = {"id": "239652", "classs": "4", "type_inv": "1"}
        base_sparse = {
            "id": "239652",
            "name": "Martyr's Crown",
            "inv_type": "1",
            "ilevel": "197",
            "req_skill": "0",
            **{
                f"stat_type_{index}": "5" if index == 1 else "-1"
                for index in range(1, 11)
            },
            **{
                f"stat_alloc_{index}": "5259" if index == 1 else "0"
                for index in range(1, 11)
            },
        }
        self.assertEqual(
            classify_current_client_crafted_candidate(
                {"recipeId": "52173", "itemId": "239652"},
                base_item,
                base_sparse,
                {"2911"},
            )["outcome"],
            "included",
        )

        competitor = {
            **base_sparse,
            "name": "Thalassian Competitor's Cloth Hood",
        }
        self.assertEqual(
            classify_current_client_crafted_candidate(
                {"recipeId": "52223", "itemId": "239652"},
                base_item,
                competitor,
                {"2911"},
            )["reasonCode"],
            "CURRENT_CLIENT_PVP_CRAFTED_OUTPUT",
        )

        fishing_hat = {
            **base_sparse,
            "name": "Elegant Artisan's Fishing Hat",
            "req_skill": "2911",
        }
        self.assertEqual(
            classify_current_client_crafted_candidate(
                {"recipeId": "52196", "itemId": "239652"},
                base_item,
                fishing_hat,
                {"2911"},
            )["reasonCode"],
            "CURRENT_CLIENT_PROFESSION_UTILITY_EQUIPMENT",
        )

        powerless = {
            **base_sparse,
            "name": "Smuggler's Cloak",
            "ilevel": "1",
            **{
                f"stat_type_{index}": "-1"
                for index in range(1, 11)
            },
            **{
                f"stat_alloc_{index}": "0"
                for index in range(1, 11)
            },
        }
        self.assertEqual(
            classify_current_client_crafted_candidate(
                {"recipeId": "57155", "itemId": "239652"},
                base_item,
                powerless,
                {"2911"},
            )["reasonCode"],
            "CURRENT_CLIENT_NO_COMBAT_POWER",
        )

    def test_classifies_only_combat_equipment_with_matching_item_relations(self):
        self.assertEqual(
            classify_client_item_equip_eligibility(
                {"id": "239652", "classs": "4", "type_inv": "11"},
                {"id": "239652", "inv_type": "11"},
            ),
            {
                "itemId": "239652",
                "itemClassId": 4,
                "inventoryTypeId": 11,
                "isCombatEquippable": True,
                "reasonCode": "CURRENT_CLIENT_COMBAT_EQUIPMENT",
            },
        )
        self.assertEqual(
            classify_client_item_equip_eligibility(
                {"id": "240000", "classs": "7", "type_inv": "29"},
                {"id": "240000", "inv_type": "29"},
            ),
            {
                "itemId": "240000",
                "itemClassId": 7,
                "inventoryTypeId": 29,
                "isCombatEquippable": False,
                "reasonCode": "CURRENT_CLIENT_NON_COMBAT_ITEM_CLASS",
            },
        )
        self.assertEqual(
            classify_client_item_equip_eligibility(
                {"id": 240001, "classs": 0, "type_inv": 0},
                {"id": 240001, "inv_type": 0},
            ),
            {
                "itemId": "240001",
                "itemClassId": 0,
                "inventoryTypeId": 0,
                "isCombatEquippable": False,
                "reasonCode": "CURRENT_CLIENT_NON_COMBAT_ITEM_CLASS",
            },
        )

    def test_rejects_item_and_sparse_inventory_type_disagreement(self):
        with self.assertRaisesRegex(
            ClientRelationEvidenceError,
            "item 239652 inventory type mismatch",
        ):
            classify_client_item_equip_eligibility(
                {"id": "239652", "classs": "4", "type_inv": "11"},
                {"id": "239652", "inv_type": "12"},
            )

    def test_selects_current_profession_spells_by_expansion_skill_line(self):
        skill_lines = [
            {"id": "2906", "name": "Midnight Alchemy"},
            {"id": "2907", "name": "Midnight Blacksmithing"},
            {"id": "2908", "name": "Midnight Cooking"},
        ]
        abilities = [
            {
                "id": "52688",
                "id_spell": "1230861",
                "id_skill_up": "2906",
            },
            {
                "id": "52356",
                "id_spell": "1229045",
                "id_skill_up": "2907",
            },
            {
                "id": "52044",
                "id_spell": "1232247",
                "id_skill_up": "2908",
            },
            {
                "id": "99999",
                "id_spell": "1999999",
                "id_skill_up": "0",
            },
        ]

        result = select_midnight_profession_spell_targets(
            skill_lines,
            abilities,
            ["Blacksmithing", "Alchemy"],
        )

        self.assertEqual(
            result,
            [
                {
                    "profession": "Blacksmithing",
                    "skillLineId": "2907",
                    "recipeId": "52356",
                    "spellId": "1229045",
                },
                {
                    "profession": "Alchemy",
                    "skillLineId": "2906",
                    "recipeId": "52688",
                    "spellId": "1230861",
                },
            ],
        )

    def test_resolves_only_equippable_type_288_crafting_outputs(self):
        targets = [
            {
                "profession": "Blacksmithing",
                "skillLineId": "2907",
                "recipeId": "52356",
                "spellId": "1229045",
            },
            {
                "profession": "Alchemy",
                "skillLineId": "2906",
                "recipeId": "52688",
                "spellId": "1230861",
            },
            {
                "profession": "Alchemy",
                "skillLineId": "2906",
                "recipeId": "59999",
                "spellId": "1299999",
            },
        ]
        spell_effects = [
            {
                "id": "8001",
                "id_parent": "1229045",
                "type": "288",
                "misc_value_1": "2556",
            },
            {
                "id": "8002",
                "id_parent": "1230861",
                "type": "288",
                "misc_value_1": "2557",
            },
            {
                "id": "8003",
                "id_parent": "1299999",
                "type": "6",
                "misc_value_1": "0",
            },
        ]
        crafting_data = [
            {"id": "2556", "id_crafted_item": "239652"},
            {"id": "2557", "id_crafted_item": "242651"},
        ]
        item_quality = [
            {"id": "1", "id_parent": "2556", "id_item": "239653"},
        ]

        result = resolve_crafted_recipe_outputs(
            targets,
            spell_effects,
            crafting_data,
            item_quality,
            {"239652", "239653"},
        )

        self.assertEqual(
            result["members"],
            [
                {
                    "itemId": "239652",
                    "profession": "Blacksmithing",
                    "recipeId": "52356",
                    "skillLineId": "2907",
                    "spellId": "1229045",
                    "spellEffectId": "8001",
                    "craftingDataId": "2556",
                    "outputKind": "crafted_item",
                },
                {
                    "itemId": "239653",
                    "profession": "Blacksmithing",
                    "recipeId": "52356",
                    "skillLineId": "2907",
                    "spellId": "1229045",
                    "spellEffectId": "8001",
                    "craftingDataId": "2556",
                    "outputKind": "quality_item",
                },
            ],
        )
        self.assertEqual(
            result["summary"],
            {
                "targetSpellCount": 3,
                "type288SpellCount": 2,
                "equippableRecipeCount": 1,
                "equippableItemCount": 2,
            },
        )

    def test_rejects_ambiguous_recipe_to_crafting_data_relation(self):
        with self.assertRaisesRegex(
            ClientRelationEvidenceError,
            "recipe 52356 has 2 type-288 effects",
        ):
            resolve_crafted_recipe_outputs(
                [
                    {
                        "profession": "Blacksmithing",
                        "skillLineId": "2907",
                        "recipeId": "52356",
                        "spellId": "1229045",
                    }
                ],
                [
                    {
                        "id": "8001",
                        "id_parent": "1229045",
                        "type": "288",
                        "misc_value_1": "2556",
                    },
                    {
                        "id": "8002",
                        "id_parent": "1229045",
                        "type": "288",
                        "misc_value_1": "2557",
                    },
                ],
                [
                    {"id": "2556", "id_crafted_item": "239652"},
                    {"id": "2557", "id_crafted_item": "239654"},
                ],
                [],
                {"239652", "239654"},
            )

    def test_compares_official_api_recipe_membership_with_current_client(self):
        result = compare_crafted_recipe_membership(
            [
                {"recipeId": "10"},
                {"recipeId": "11"},
            ],
            [
                {"recipeId": "10", "itemId": "100"},
                {"recipeId": "12", "itemId": "120"},
                {"recipeId": "12", "itemId": "121"},
            ],
        )

        self.assertEqual(
            result,
            {
                "status": "mismatched",
                "officialApiRecipeCount": 2,
                "currentClientRecipeCount": 2,
                "sharedRecipeCount": 1,
                "officialApiOnlyRecipeIds": ["11"],
                "currentClientOnlyRecipeIds": ["12"],
            },
        )


if __name__ == "__main__":
    unittest.main()

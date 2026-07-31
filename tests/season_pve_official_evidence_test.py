import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import server.season_pve_official_evidence as official_evidence
from server.season_pve_official_evidence import (
    OfficialEvidenceError,
    authority_identity,
    build_crafted_allowlist_diff,
    build_official_item_opposition,
    build_official_membership_snapshot,
    build_universe_discovery_input,
    client_build_from_namespace,
    client_build_from_simc_version,
    index_simc_generated_item_data,
    journal_source_key,
    official_response_namespaces,
    verify_current_client_public_tact_key_reextract_audit,
    verify_current_client_tact_key_upstream_source_audit,
    verify_current_client_tact_key_coverage_audit,
    verify_current_client_source_relations_audit,
    verify_official_item_range_snapshot,
)


class SeasonPveOfficialEvidenceTest(unittest.TestCase):
    @staticmethod
    def _write_tact_key_upstream_input_fixture(root, source_audit=None):
        inputs = {}
        public_document = {"status": "partial"}
        if source_audit is not None:
            public_document["coverage"] = {
                "summary": source_audit["sourceResults"][
                    "currentPublicTactKeys"
                ],
                "targetKeys": [
                    {
                        "tactKeyId": row["tactKeyId"],
                        "blteKeyId": row["blteKeyId"],
                        "recordCount": row["recordCount"],
                        "presentInCurrentPublicSnapshot": row[
                            "sourcePresence"
                        ]["currentPublicTactKeys"],
                    }
                    for row in source_audit["coverage"]["targetKeys"]
                ],
            }
        public_payload = (
            json.dumps(public_document, sort_keys=True).encode() + b"\n"
        )
        (root / "currentPublicTactKeys.json").write_bytes(public_payload)
        inputs["currentPublicTactKeys"] = {
            "path": "currentPublicTactKeys.json",
            "bytes": len(public_payload),
            "sha256": hashlib.sha256(public_payload).hexdigest(),
        }
        for source_name in (
            "verifiedDBCacheCorpus",
            "unverifiedDBCacheCorpus",
        ):
            list_name = f"{source_name}-list.json"
            list_payload = f'{{"source":"{source_name}"}}\n'.encode()
            (root / list_name).write_bytes(list_payload)
            component_document = {
                "sourceList": {
                    "path": list_name,
                    "bytes": len(list_payload),
                    "sha256": hashlib.sha256(list_payload).hexdigest(),
                }
            }
            if source_audit is not None:
                component_document["corpus"] = {
                    "summary": source_audit["sourceResults"][source_name],
                    "targetKeys": [
                        {
                            "tactKeyId": row["tactKeyId"],
                            "blteKeyId": row["blteKeyId"],
                            "recordCount": row["recordCount"],
                            "presentInCorpusUnion": row["sourcePresence"][
                                source_name
                            ],
                        }
                        for row in source_audit["coverage"]["targetKeys"]
                    ],
                }
            component_payload = (
                json.dumps(component_document, sort_keys=True).encode()
                + b"\n"
            )
            component_name = f"{source_name}.json"
            (root / component_name).write_bytes(component_payload)
            inputs[source_name] = {
                "path": component_name,
                "bytes": len(component_payload),
                "sha256": hashlib.sha256(component_payload).hexdigest(),
            }
        return inputs

    def test_tact_key_upstream_inputs_reject_overwritten_component(self):
        verifier = getattr(
            official_evidence,
            "verify_current_client_tact_key_upstream_input_files",
            None,
        )
        self.assertIsNotNone(
            verifier,
            "TACT-key upstream component file verifier is missing",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = self._write_tact_key_upstream_input_fixture(root)

            verified = verifier(inputs, snapshot_root=root)
            self.assertEqual(
                set(verified),
                {
                    "currentPublicTactKeys",
                    "verifiedDBCacheCorpus",
                    "unverifiedDBCacheCorpus",
                },
            )

            (root / "unverifiedDBCacheCorpus.json").write_bytes(
                b'{"generation":2}\n'
            )
            with self.assertRaisesRegex(
                OfficialEvidenceError,
                "unverifiedDBCacheCorpus",
            ):
                verifier(inputs, snapshot_root=root)

    def test_tact_key_upstream_inputs_reject_overwritten_source_list(self):
        verifier = (
            official_evidence.verify_current_client_tact_key_upstream_input_files
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = self._write_tact_key_upstream_input_fixture(root)

            verifier(inputs, snapshot_root=root)
            (root / "unverifiedDBCacheCorpus-list.json").write_bytes(
                b'{"source":"replacement"}\n'
            )

            with self.assertRaisesRegex(
                OfficialEvidenceError,
                "unverifiedDBCacheCorpus.sourceList",
            ):
                verifier(inputs, snapshot_root=root)

    def test_tact_key_upstream_source_verifier_binds_component_files(self):
        audit_path = (
            Path(__file__).resolve().parents[1]
            / "artifacts/releases/"
            "2026-07-30-equipment-simulator-e2e-matrix/"
            "universe/official-snapshot/official-client-db2-v1/"
            "current-client-tact-key-upstream-source-audit.json"
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audit["inputs"] = self._write_tact_key_upstream_input_fixture(
                root,
                source_audit=audit,
            )

            try:
                verified = verify_current_client_tact_key_upstream_source_audit(
                    audit,
                    expected_encrypted_record_count=178,
                    snapshot_root=root,
                )
            except TypeError as error:
                self.fail(
                    "TACT-key upstream verifier must bind component files: "
                    f"{error}"
                )
            self.assertEqual(verified["status"], "partial")

            audit["sourceResults"]["unverifiedDBCacheCorpus"][
                "selectedCacheCount"
            ] -= 1
            with self.assertRaisesRegex(
                OfficialEvidenceError,
                "cache corpus summary",
            ):
                verify_current_client_tact_key_upstream_source_audit(
                    audit,
                    expected_encrypted_record_count=178,
                    snapshot_root=root,
                )
            audit["sourceResults"]["unverifiedDBCacheCorpus"][
                "selectedCacheCount"
            ] += 1

            (root / "unverifiedDBCacheCorpus.json").write_bytes(
                b"unverified-v2\n"
            )
            with self.assertRaisesRegex(
                OfficialEvidenceError,
                "unverifiedDBCacheCorpus",
            ):
                verify_current_client_tact_key_upstream_source_audit(
                    audit,
                    expected_encrypted_record_count=178,
                    snapshot_root=root,
                )

    def test_tact_key_upstream_source_audit_retains_64_record_blocker(self):
        audit_path = (
            Path(__file__).resolve().parents[1]
            / "artifacts/releases/"
            "2026-07-30-equipment-simulator-e2e-matrix/"
            "universe/official-snapshot/official-client-db2-v1/"
            "current-client-tact-key-upstream-source-audit.json"
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))

        with self.assertRaisesRegex(
            OfficialEvidenceError,
            "snapshot root",
        ):
            verify_current_client_tact_key_upstream_source_audit(
                audit,
                expected_encrypted_record_count=178,
            )

        verified = verify_current_client_tact_key_upstream_source_audit(
            audit,
            expected_encrypted_record_count=178,
            snapshot_root=audit_path.parent,
        )

        self.assertEqual(verified["status"], "partial")
        self.assertEqual(verified["sourceUnionAvailableTargetKeyCount"], 9)
        self.assertEqual(verified["sourceUnionMissingTargetKeyCount"], 3)
        self.assertEqual(verified["sourceUnionCoveredTargetRecordCount"], 114)
        self.assertEqual(verified["sourceUnionMissingTargetRecordCount"], 64)
        self.assertEqual(verified["verifiedCacheCount"], 9)
        self.assertEqual(verified["unverifiedCacheCount"], 99)

        audit["authority"]["rawKeyOrCacheMaterialPersistedAfterAudit"] = True
        with self.assertRaises(OfficialEvidenceError):
            verify_current_client_tact_key_upstream_source_audit(
                audit,
                expected_encrypted_record_count=178,
                snapshot_root=audit_path.parent,
            )

    def test_public_tact_key_reextract_audit_retains_static_payload_blocker(self):
        audit = {
            "schemaVersion": 1,
            "status": "partial",
            "build": "12.0.7.68887",
            "authority": {
                "recordTactKeyIdentitySource": (
                    "wowdev/TACTKeys@"
                    "a3449fd5cfc3a0053cbff2c65f7d16166774cbf9"
                ),
                "blteKeyIdentitySource": (
                    "Blizzard retail CDN BLTE chunks"
                ),
                "recordAndBlteKeyIdentityByteOrderMapped": True,
                "recordBytes": "Blizzard retail CDN",
                "keyMaterialEmitted": False,
                "duplicateOfficialDb2PayloadsPersisted": False,
            },
            "reextractAudit": {
                "status": "partial",
                "summary": {
                    "tableCount": 4,
                    "changedTableCount": 4,
                    "recordTactKeyCount": 12,
                    "publicRecordTactKeyCount": 9,
                    "missingRecordTactKeyCount": 3,
                    "publicRecordTactKeyCoveredRecordCount": 114,
                    "recordTactKeyToBlteKeyOverlapCount": 12,
                    "blteKeyCount": 12,
                    "blteEncryptedChunkCount": 20,
                    "blteKeyAvailableChunkCount": 17,
                    "blteDecryptedChunkCount": 17,
                    "blteZeroFallbackChunkCount": 3,
                    "targetEncryptedRecordCount": 178,
                    "recoveredEncryptedRecordCount": 114,
                    "unavailableEncryptedRecordCount": 64,
                },
                "blockers": [
                    "APPROVED_PUBLIC_TACT_KEYS_INCOMPLETE",
                    "CURRENT_CLIENT_BLTE_DECRYPTION_KEYS_UNAVAILABLE",
                    "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
                ],
            },
            "productionMutation": False,
            "releasePointerMutation": False,
        }

        verified = verify_current_client_public_tact_key_reextract_audit(
            audit,
            expected_encrypted_record_count=178,
        )

        self.assertEqual(verified["status"], "partial")
        self.assertEqual(verified["publicRecordTactKeyCount"], 9)
        self.assertEqual(
            verified["publicRecordTactKeyCoveredRecordCount"],
            114,
        )
        self.assertEqual(verified["blteEncryptedChunkCount"], 20)
        self.assertEqual(verified["blteDecryptedChunkCount"], 17)
        self.assertEqual(verified["recoveredEncryptedRecordCount"], 114)
        self.assertEqual(verified["unavailableEncryptedRecordCount"], 64)

        audit["authority"]["keyMaterialEmitted"] = True
        with self.assertRaises(OfficialEvidenceError):
            verify_current_client_public_tact_key_reextract_audit(
                audit,
                expected_encrypted_record_count=178,
            )

    def test_current_client_tact_key_audit_retains_encrypted_blocker(self):
        audit = {
            "schemaVersion": 1,
            "status": "blocked",
            "build": "12.0.7.68887",
            "authority": {
                "keyBytes": "captured Blizzard retail client DB2",
                "scope": "static TactKey and TactKeyLookup tables only",
                "keyMaterialEmitted": False,
            },
            "coverage": {
                "status": "blocked",
                "summary": {
                    "targetKeyCount": 12,
                    "targetRecordCount": 178,
                    "presentTargetKeyCount": 0,
                    "missingTargetKeyCount": 12,
                    "coveredTargetRecordCount": 0,
                    "missingTargetRecordCount": 178,
                },
                "blockers": [
                    "CURRENT_CLIENT_STATIC_TACT_KEYS_INCOMPLETE"
                ],
            },
            "productionMutation": False,
            "releasePointerMutation": False,
        }

        verified = verify_current_client_tact_key_coverage_audit(
            audit,
            expected_encrypted_record_count=178,
        )

        self.assertEqual(verified["status"], "blocked")
        self.assertEqual(verified["targetKeyCount"], 12)
        self.assertEqual(verified["presentTargetKeyCount"], 0)
        self.assertEqual(verified["missingTargetRecordCount"], 178)

        audit["authority"]["keyMaterialEmitted"] = True
        with self.assertRaises(OfficialEvidenceError):
            verify_current_client_tact_key_coverage_audit(
                audit,
                expected_encrypted_record_count=178,
            )

    def test_current_client_source_relations_audit_is_fail_closed(self):
        recovered_tables = {
            "CollectableSourceInfo",
            "CollectableSourceVendor",
            "CollectableSourceVendorSparse",
            "ItemModifiedAppearance",
        }
        table_audits = {
            table: {
                "recordCount": 10,
                "unencryptedRecordCount": 8,
                "encryptedRecordCount": 2,
                "parserRecordCount": (
                    9 if table in recovered_tables else 8
                ),
                "parserRecoveredEncryptedRecordCount": (
                    1 if table in recovered_tables else 0
                ),
                "parserCoveredUnencryptedRecords": True,
                "parserCoveredAvailableRecords": True,
            }
            for table in (
                "ChallengeModeReward",
                "ChallengeModeXReward",
                "CollectableSourceInfo",
                "CollectableSourceVendor",
                "CollectableSourceVendorSparse",
                "CreatureDifficultyTreasure",
                "InitiativeReward",
                "ItemAppearance",
                "ItemModifiedAppearance",
                "QuestPackageItem",
            )
        }
        audit = {
            "schemaVersion": 1,
            "status": "blocked",
            "build": "12.0.7.68887",
            "authority": {
                "recordBytes": "captured Blizzard retail client DB2",
                "schemaAid": "pinned wowdev/WoWDBDefs definitions",
                "schemaAidMayEstablishOfficialMembership": False,
            },
            "tableAudits": table_audits,
            "relationAudit": {
                "status": "blocked",
                "summary": {
                    "promotableMemberCount": 0,
                    "unparsedEncryptedRecordCount": 4,
                    "vendorCandidateItemCount": 19307,
                    "questPackageCandidateItemCount": 11058,
                },
                "blockers": [
                    "CURRENT_CLIENT_ENCRYPTED_SOURCE_RECORDS_UNAVAILABLE",
                    "CURRENT_QUEST_PACKAGE_RELATION_UNAVAILABLE",
                    "CURRENT_SEASON_PVE_VENDOR_IDENTITY_UNAVAILABLE",
                    "THIRD_PARTY_SCHEMA_FIELDS_UNVERIFIED",
                ],
            },
            "gapImpact": {
                "beforeGapCount": 21,
                "resolvedGapCount": 0,
                "afterGapCount": 21,
            },
            "promotionDecision": {
                "promotedMemberCount": 0,
                "catalogMutation": False,
            },
            "productionMutation": False,
            "releasePointerMutation": False,
        }

        verified = verify_current_client_source_relations_audit(
            audit,
            expected_gap_count=21,
        )

        self.assertEqual(verified["status"], "blocked")
        self.assertEqual(verified["build"], "12.0.7.68887")
        self.assertEqual(verified["promotableMemberCount"], 0)
        self.assertEqual(verified["encryptedRecordCount"], 8)
        self.assertEqual(verified["recoveredEncryptedRecordCount"], 4)
        self.assertEqual(verified["unparsedEncryptedRecordCount"], 4)
        self.assertEqual(verified["gapCount"], 21)
        self.assertEqual(verified["verifiedTableCount"], 10)

        audit["gapImpact"]["resolvedGapCount"] = 1
        with self.assertRaises(OfficialEvidenceError):
            verify_current_client_source_relations_audit(
                audit,
                expected_gap_count=21,
            )

    def test_authority_identity_keeps_article_id_across_slug_variants(self):
        self.assertEqual(
            authority_identity(
                "https://worldofwarcraft.blizzard.com/en-us/news/24266321"
            ),
            authority_identity(
                "https://worldofwarcraft.blizzard.com/en-us/news/"
                "24266321/midnight-season-1-has-begun"
            ),
        )

    def test_journal_partition_keeps_sporefall_separate_from_core_raids(self):
        self.assertEqual(
            journal_source_key("midnight_raid", "1305"),
            "raid:sporefall",
        )
        self.assertEqual(
            journal_source_key("midnight_raid", "1307"),
            "raid:midnight-season-1-core",
        )
        with self.assertRaises(OfficialEvidenceError):
            journal_source_key("unknown", "1")

    def test_simc_generated_item_data_preserves_exact_item_name_and_id(self):
        indexed = index_simc_generated_item_data(
            [
                '  { "Blood-Tempered Bracers", 237923, 0x0 },',
                "  { \"Magister's Alchemist Stone\", 241340, 0x0 },",
            ]
        )

        self.assertEqual(
            indexed["blood-tempered bracers"][0]["itemId"],
            "237923",
        )
        self.assertEqual(
            indexed["magister's alchemist stone"][0]["itemId"],
            "241340",
        )

    def test_official_response_namespace_and_simc_builds_are_explicit(self):
        payload = {
            "_links": {
                "self": {
                    "href": (
                        "https://us.api.blizzard.com/data/wow/item/1"
                        "?namespace=static-12.0.7_67808-us"
                    )
                }
            },
            "nested": [
                {
                    "key": {
                        "href": (
                            "https://us.api.blizzard.com/data/wow/item/2"
                            "?namespace=static-12.0.7_67808-us"
                        )
                    }
                },
                {
                    "href": (
                        "https://us.api.blizzard.com/data/wow/"
                        "mythic-keystone/season/17?namespace=dynamic-us"
                    )
                },
            ],
        }

        self.assertEqual(
            official_response_namespaces(payload),
            ["dynamic-us", "static-12.0.7_67808-us"],
        )
        self.assertEqual(
            client_build_from_namespace("static-12.0.7_67808-us"),
            "67808",
        )
        self.assertEqual(client_build_from_namespace("dynamic-us"), "")
        self.assertEqual(
            client_build_from_simc_version(
                "SimulationCraft 1205-01 for World of Warcraft "
                "12.0.7.68887 Live (hotfix 2026-07-24/68887)"
            ),
            "68887",
        )

    def test_projection_records_raw_relations_but_never_claims_complete(self):
        policy = {
            "seasonRevision": "season-1",
            "sourcePolicyRevision": "policy-1",
            "status": "required_membership_discovery",
            "sources": [
                {
                    "sourceKey": "raid:sporefall",
                    "sourceType": "raid",
                    "membershipMode": "journal_direct_drop",
                    "effectiveWindow": {
                        "startsAt": "2026-06-16T00:00:00Z",
                        "endPolicy": "until_officially_superseded",
                    },
                    "authorityRefs": ["https://example.test/news/1"],
                },
                {
                    "sourceKey": "crafted:midnight-season-1",
                    "sourceType": "crafted",
                    "membershipMode": "profession_recipe_and_quality",
                    "effectiveWindow": {
                        "startsAt": "2026-03-03T00:00:00Z",
                        "endPolicy": "until_officially_superseded",
                    },
                    "authorityRefs": ["https://example.test/news/2"],
                },
            ],
        }
        capture = {
            "asOf": "2026-07-30T10:19:14Z",
            "journalCapture": {
                "itemContexts": {
                    "268291": [
                        {
                            "sourceGroup": "midnight_raid",
                            "instanceId": "1305",
                            "instanceName": "Sporefall",
                            "encounterId": "3012",
                            "encounterName": "Rotmire",
                            "lootRelationId": "50001",
                        }
                    ]
                }
            },
            "professionCapture": {
                "recipes": [
                    {
                        "profession": "Blacksmithing",
                        "category": "Weapons",
                        "recipeId": "52349",
                        "name": "Primalforged Heavy Axe",
                        "candidateItemIds": ["237932"],
                    },
                    {
                        "profession": "Engineering",
                        "category": "Guns",
                        "recipeId": "57186",
                        "name": "Thalassian Competitor's Rifle",
                        "candidateItemIds": ["268476"],
                    }
                ]
            },
            "classSetCapture": {"sets": []},
        }

        result = build_official_membership_snapshot(
            policy,
            capture,
            captured_at="2026-07-30T10:19:14Z",
            authority_manifest_ref="authority-page-manifest.json",
            capture_ref="official-game-data-capture.json",
            capture_directory="official-game-data-v2",
            simc_item_index=index_simc_generated_item_data(
                ['  { "Primalforged Heavy Axe", 237932, 0x0 },']
            ),
            simc_evidence_ref="raw/simc-client-data/item_data.inc",
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["summary"]["sourceCount"], 2)
        self.assertEqual(result["summary"]["completeSourceCount"], 0)
        self.assertEqual(
            [row["membershipComplete"] for row in result["sources"]],
            [False, False],
        )
        crafted = next(
            row
            for row in result["sources"]
            if row["sourceKey"] == "crafted:midnight-season-1"
        )
        self.assertEqual(crafted["rawMemberCount"], 1)
        self.assertEqual(
            crafted["rawMembers"][0]["candidateItemIds"],
            ["237932"],
        )
        sporefall = next(
            row
            for row in result["sources"]
            if row["sourceKey"] == "raid:sporefall"
        )
        self.assertEqual(sporefall["rawMembers"][0]["itemId"], "268291")
        self.assertIn(
            "OFFICIAL_JOURNAL_DIFFICULTY_MEMBERSHIP_UNAVAILABLE",
            {gap["reasonCode"] for gap in sporefall["gaps"]},
        )

        discovery = build_universe_discovery_input(
            result,
            evidence_ref="official-source-membership-snapshot.json",
        )
        self.assertEqual(discovery["sourcePolicyRevision"], "policy-1")
        self.assertEqual(len(discovery["sources"]), 2)
        sporefall_discovery = next(
            row
            for row in discovery["sources"]
            if row["sourceKey"] == "raid:sporefall"
        )
        self.assertEqual(sporefall_discovery["members"], [])
        self.assertFalse(sporefall_discovery["membershipComplete"])
        self.assertEqual(
            sporefall_discovery["gaps"][0]["kind"],
            "official_journal_difficulty_membership_unavailable",
        )
        self.assertEqual(
            sporefall_discovery["evidenceRef"],
            (
                "official-source-membership-snapshot.json"
                "#source=raid:sporefall"
            ),
        )

    def test_current_client_crafted_relation_closes_recipe_output_gap_only(self):
        policy = {
            "seasonRevision": "season-1",
            "sourcePolicyRevision": "policy-1",
            "status": "required_membership_discovery",
            "sources": [
                {
                    "sourceKey": "crafted:midnight-season-1",
                    "sourceType": "crafted",
                    "membershipMode": "profession_recipe_and_quality",
                    "effectiveWindow": {
                        "startsAt": "2026-03-03T00:00:00Z",
                        "endPolicy": "until_officially_superseded",
                    },
                    "authorityRefs": ["https://example.test/news/2"],
                }
            ],
        }
        capture = {
            "asOf": "2026-07-30T10:19:14Z",
            "journalCapture": {"itemContexts": {}},
            "professionCapture": {
                "recipes": [
                    {
                        "profession": "Blacksmithing",
                        "category": "Weapons",
                        "recipeId": "52349",
                        "name": "Primalforged Heavy Axe",
                        "candidateItemIds": ["237932"],
                    }
                ]
            },
            "classSetCapture": {"sets": []},
        }
        client_membership = {
            "status": "complete",
            "scope": "current_client_midnight_crafted_pve_combat_equipment",
            "build": "12.0.7.68887",
            "summary": {
                "candidateItemCount": 2,
                "includedItemCount": 1,
                "includedRecipeCount": 1,
                "excludedItemCount": 1,
            },
            "officialApiComparison": {
                "status": "matched",
                "officialApiRecipeCount": 1,
                "currentClientRecipeCount": 1,
                "sharedRecipeCount": 1,
                "officialApiOnlyRecipeIds": [],
                "currentClientOnlyRecipeIds": [],
            },
            "included": [
                {
                    "itemId": "237932",
                    "recipeId": "52349",
                    "profession": "Blacksmithing",
                    "name": "Primalforged Heavy Axe",
                    "reasonCode": (
                        "CURRENT_CLIENT_SEASON_PVE_CRAFTED_OUTPUT"
                    ),
                    "outcome": "included",
                }
            ],
            "excluded": [
                {
                    "itemId": "268476",
                    "recipeId": "57186",
                    "reasonCode": "CURRENT_CLIENT_PVP_CRAFTED_OUTPUT",
                    "outcome": "excluded",
                }
            ],
        }

        result = build_official_membership_snapshot(
            policy,
            capture,
            captured_at="2026-07-30T10:19:14Z",
            authority_manifest_ref="authority-page-manifest.json",
            capture_ref="official-game-data-capture.json",
            capture_directory="official-game-data-v2",
            simc_item_index=index_simc_generated_item_data(
                ['  { "Primalforged Heavy Axe", 237932, 0x0 },']
            ),
            simc_evidence_ref="raw/simc-client-data/item_data.inc",
            client_crafted_membership=client_membership,
            client_crafted_evidence_ref=(
                "official-client-db2-v1/"
                "current-client-crafted-membership.json"
            ),
        )

        crafted = result["sources"][0]
        self.assertEqual(crafted["rawMembers"][0]["itemId"], "237932")
        self.assertEqual(
            crafted["rawMembers"][0]["candidateItemIds"],
            ["237932"],
        )
        self.assertEqual(
            crafted["rawMembers"][0]["membershipStatus"],
            "verified_output_item",
        )
        self.assertEqual(
            {gap["reasonCode"] for gap in crafted["gaps"]},
            {"OFFICIAL_PROGRESSION_STATE_UNAVAILABLE"},
        )
        self.assertNotIn(
            "OFFICIAL_RECIPE_OUTPUT_ITEM_ID_UNAVAILABLE",
            result["summary"]["gapReasonCounts"],
        )

    def test_current_client_journal_relation_closes_difficulty_gap_only(self):
        policy = {
            "seasonRevision": "season-1",
            "sourcePolicyRevision": "policy-1",
            "status": "required_membership_discovery",
            "sources": [
                {
                    "sourceKey": "raid:sporefall",
                    "sourceType": "raid",
                    "membershipMode": "journal_direct_drop",
                    "effectiveWindow": {
                        "startsAt": "2026-06-16T00:00:00Z",
                        "endPolicy": "until_officially_superseded",
                    },
                    "authorityRefs": ["https://example.test/news/1"],
                }
            ],
        }
        capture = {
            "asOf": "2026-07-30T10:19:14Z",
            "journalCapture": {
                "itemContexts": {
                    "268291": [
                        {
                            "sourceGroup": "midnight_raid",
                            "instanceId": "1305",
                            "instanceName": "Sporefall",
                            "encounterId": "3012",
                            "encounterName": "Rotmire",
                            "lootRelationId": "50001",
                        }
                    ]
                }
            },
            "professionCapture": {"recipes": []},
            "classSetCapture": {"sets": []},
        }
        client_journal = {
            "schemaVersion": 1,
            "schemaRevision": (
                "season-pve-current-client-journal-membership-v1"
            ),
            "scope": "current_client_journal_item_difficulty_relations",
            "status": "complete",
            "clientBuild": "12.0.7.68887",
            "summary": {
                "relationCount": 1,
                "sourceCount": 1,
                "bySource": {"raid:sporefall": 1},
                "byDifficulty": {
                    "lfr": 1,
                    "normal": 1,
                    "heroic": 1,
                    "mythic": 1,
                },
            },
            "relations": [
                {
                    "sourceKey": "raid:sporefall",
                    "sourceGroup": "midnight_raid",
                    "instanceId": "1305",
                    "instanceName": "Sporefall",
                    "encounterId": "3012",
                    "encounterName": "Rotmire",
                    "itemId": "268291",
                    "officialLootRelationIds": ["50001"],
                    "currentClientRelationIds": ["60001"],
                    "explicitClientDifficultyIds": [],
                    "explicitClientDifficultyNames": [],
                    "difficultyKeys": [
                        "lfr",
                        "normal",
                        "heroic",
                        "mythic",
                    ],
                    "clientBuild": "12.0.7.68887",
                    "membershipStatus": (
                        "verified_current_client_relation"
                    ),
                }
            ],
        }

        result = build_official_membership_snapshot(
            policy,
            capture,
            captured_at="2026-07-30T10:19:14Z",
            authority_manifest_ref="authority-page-manifest.json",
            capture_ref="official-game-data-capture.json",
            capture_directory="official-game-data-v2",
            simc_item_index={},
            simc_evidence_ref="raw/simc-client-data/item_data.inc",
            client_journal_membership=client_journal,
            client_journal_evidence_ref=(
                "official-client-db2-v1/"
                "current-client-journal-membership.json"
            ),
        )

        source = result["sources"][0]
        self.assertEqual(
            source["rawMembers"][0]["difficultyKeys"],
            ["lfr", "normal", "heroic", "mythic"],
        )
        self.assertEqual(
            source["rawMembers"][0]["membershipStatus"],
            "verified_current_client_relation",
        )
        self.assertEqual(
            {gap["reasonCode"] for gap in source["gaps"]},
            {"OFFICIAL_PROGRESSION_STATE_UNAVAILABLE"},
        )
        self.assertNotIn(
            "OFFICIAL_JOURNAL_DIFFICULTY_MEMBERSHIP_UNAVAILABLE",
            result["summary"]["gapReasonCounts"],
        )

    def test_crafted_diff_reports_each_candidate_missing_from_project(self):
        result = build_crafted_allowlist_diff(
            {
                "rawMembers": [
                    {
                        "recipeId": "1",
                        "name": "Already Governed",
                        "profession": "Tailoring",
                        "category": "Garments",
                        "candidateItemIds": ["100"],
                        "modifiedCraftingSlotNames": [
                            "Customize Secondary Stats"
                        ],
                    },
                    {
                        "recipeId": "2",
                        "name": "Missing",
                        "profession": "Tailoring",
                        "category": "Garments",
                        "candidateItemIds": ["101"],
                        "modifiedCraftingSlotNames": [
                            "Amplify Secondary Stat",
                            "Add Embellishment",
                        ],
                    },
                ]
            },
            {"100"},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["reasonCodes"],
            ["CRAFTED_CANDIDATE_MISSING_FROM_PROJECT_ALLOWLIST"],
        )
        self.assertEqual(
            result["missingFromProjectAllowlist"][0]["itemId"],
            "101",
        )
        self.assertEqual(
            result["missingFromProjectAllowlist"][0]["secondaryStatMode"],
            "amplify_one_secondary",
        )

    def test_official_item_opposition_keeps_every_unexplained_candidate(self):
        result = build_official_item_opposition(
            {
                "journal item": [
                    {
                        "id": 100,
                        "name": {"en_US": "Journal Item"},
                        "required_level": 90,
                        "is_equippable": True,
                    }
                ],
                "crafted item": [
                    {
                        "id": 101,
                        "name": {"en_US": "Crafted Item"},
                        "required_level": 90,
                        "is_equippable": True,
                    }
                ],
                "unexplained item": [
                    {
                        "id": 102,
                        "name": {"en_US": "Unexplained Item"},
                        "required_level": 90,
                        "is_equippable": True,
                    }
                ],
            },
            {
                "sources": [
                    {
                        "sourceKey": "raid:test",
                        "sourceType": "raid",
                        "rawMembers": [{"itemId": "100"}],
                    },
                    {
                        "sourceKey": "crafted:test",
                        "sourceType": "crafted",
                        "rawMembers": [{"candidateItemIds": ["101"]}],
                    },
                ]
            },
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["summary"]["scopedItemCount"], 3)
        self.assertEqual(result["summary"]["sourceLinkedItemCount"], 2)
        self.assertEqual(result["summary"]["unresolvedItemCount"], 1)
        by_id = {row["itemId"]: row for row in result["items"]}
        self.assertEqual(by_id["100"]["sourceKeys"], ["raid:test"])
        self.assertEqual(by_id["101"]["sourceKeys"], ["crafted:test"])
        self.assertEqual(
            by_id["102"]["candidateStatus"],
            "unresolved_source_or_exclusion",
        )
        self.assertEqual(
            result["reasonCodes"],
            [
                "OFFICIAL_ITEM_SEARCH_SCOPE_NOT_UNIVERSE",
                "OFFICIAL_ITEM_SOURCE_OR_EXCLUSION_UNRESOLVED",
            ],
        )

    def test_official_item_range_snapshot_requires_cursor_and_hash_closure(self):
        captured_at = "2026-07-30T12:00:00Z"
        first_payload = {
            "_links": {
                "self": {
                    "href": (
                        "https://us.api.blizzard.com/data/wow/search/item"
                        "?namespace=static-12.0.7_67808-us"
                    )
                }
            },
            "page": 1,
            "pageCount": 1,
            "pageSize": 2,
            "maxPageSize": 2,
            "resultCountCapped": True,
            "results": [
                {
                    "data": {
                        "id": 1,
                        "name": {"en_US": "First"},
                        "required_level": 10,
                        "is_equippable": True,
                    }
                },
                {
                    "data": {
                        "id": 2,
                        "name": {"en_US": "Second"},
                        "required_level": 90,
                        "is_equippable": True,
                    }
                },
            ],
        }
        terminal_payload = {
            "_links": first_payload["_links"],
            "page": 1,
            "pageCount": 1,
            "pageSize": 1,
            "maxPageSize": 2,
            "resultCountCapped": False,
            "results": [
                {
                    "data": {
                        "id": 3,
                        "name": {"en_US": "Third"},
                        "required_level": 70,
                        "is_equippable": True,
                    }
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def write(relative_path, payload):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                body = (
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")
                path.write_bytes(body)
                return {
                    "relativePath": relative_path,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "bytes": len(body),
                }

            first_record = {
                **write(
                    "raw/game-data/items/equippable-range/cursor-1.json",
                    first_payload,
                ),
                "cursor": 1,
                "itemCount": 2,
                "firstItemId": "1",
                "lastItemId": "2",
                "resultCountCapped": True,
            }
            terminal_record = {
                **write(
                    "raw/game-data/items/equippable-range/cursor-3.json",
                    terminal_payload,
                ),
                "cursor": 3,
                "itemCount": 1,
                "firstItemId": "3",
                "lastItemId": "3",
                "resultCountCapped": False,
            }
            summary = {
                "schemaVersion": 1,
                "schemaRevision": "season-pve-official-item-range-v1",
                "status": "captured",
                "capturedAt": captured_at,
                "range": {
                    "startItemId": 1,
                    "endItemId": 10,
                    "equippable": True,
                },
                "pageCount": 2,
                "itemCount": 3,
                "responseBytes": (
                    first_record["bytes"] + terminal_record["bytes"]
                ),
                "firstItemId": "1",
                "lastItemId": "3",
                "itemIndexComplete": True,
                "sourceMembershipComplete": False,
                "membershipComplete": False,
                "reasonCode": (
                    "OFFICIAL_ITEM_RANGE_HAS_NO_SOURCE_MEMBERSHIP"
                ),
                "captureImplementation": {
                    "schemaRevision": (
                        "season-pve-official-item-range-v1"
                    ),
                    "scriptSha256": hashlib.sha256(
                        (
                            Path(__file__).resolve().parents[1]
                            / "scripts/capture-official-item-range.py"
                        ).read_bytes()
                    ).hexdigest(),
                    "validatorOwnerSha256": hashlib.sha256(
                        (
                            Path(__file__).resolve().parents[1]
                            / "server/season_pve_official_capture.py"
                        ).read_bytes()
                    ).hexdigest(),
                },
                "captureLimits": {
                    "pageSize": 2,
                    "maxPages": 10,
                    "maxResponseBytes": 1024 * 1024,
                    "maxTotalResponseBytes": 1024 * 1024,
                    "minimumItemCount": 1,
                    "delaySeconds": 0.2,
                },
                "pages": [first_record, terminal_record],
            }
            summary_record = write(
                "official-item-range-capture.json",
                summary,
            )
            manifest_payload = {
                "schemaVersion": 1,
                "schemaRevision": (
                    "season-pve-official-item-range-v1"
                ),
                "status": "captured",
                "capturedAt": captured_at,
                "itemCount": 3,
                "pageCount": 2,
                "responseBytes": (
                    first_record["bytes"] + terminal_record["bytes"]
                ),
                "responses": [first_record, terminal_record],
                "summary": summary_record,
            }
            write("capture-manifest.json", manifest_payload)

            verification, item_index = (
                verify_official_item_range_snapshot(root)
            )

            self.assertEqual(verification["verifiedItemCount"], 3)
            self.assertEqual(
                verification["verifiedResponseBytes"],
                first_record["bytes"] + terminal_record["bytes"],
            )
            self.assertEqual(
                verification["captureImplementationStatus"],
                "matched",
            )
            self.assertEqual(
                verification["staticClientBuilds"],
                ["67808"],
            )
            self.assertEqual(
                sorted(
                    row["id"]
                    for rows in item_index.values()
                    for row in rows
                ),
                [1, 2, 3],
            )
            opposition = build_official_item_opposition(
                item_index,
                {"sources": []},
                required_level=None,
                search_scope="all_equippable_items",
                client_item_ids={"1", "2", "4"},
            )
            self.assertEqual(opposition["summary"]["scopedItemCount"], 3)
            self.assertEqual(
                opposition["scope"]["officialSearchScope"],
                "all_equippable_items",
            )
            self.assertEqual(
                [row["requiredLevel"] for row in opposition["items"]],
                [10, 90, 70],
            )
            self.assertEqual(
                opposition["clientItemComparison"],
                {
                    "status": "mismatched",
                    "officialItemCount": 3,
                    "clientItemCount": 3,
                    "sharedItemCount": 2,
                    "officialOnlyItemIds": ["3"],
                    "clientOnlyItemIds": ["4"],
                },
            )
            self.assertIn(
                "OFFICIAL_ITEM_RANGE_CLIENT_DATA_MISMATCH",
                opposition["reasonCodes"],
            )

            invalid_limits = json.loads(json.dumps(summary))
            invalid_limits["captureLimits"]["maxResponseBytes"] = (
                512 * 1024
            )
            invalid_summary_record = write(
                "official-item-range-capture.json",
                invalid_limits,
            )
            write(
                "capture-manifest.json",
                {
                    **manifest_payload,
                    "summary": invalid_summary_record,
                },
            )
            with self.assertRaisesRegex(
                OfficialEvidenceError,
                "capture limits are invalid",
            ):
                verify_official_item_range_snapshot(root)
            summary_record = write(
                "official-item-range-capture.json",
                summary,
            )
            write(
                "capture-manifest.json",
                {
                    **manifest_payload,
                    "summary": summary_record,
                },
            )

            extra_path = (
                root
                / "raw/game-data/items/equippable-range/cursor-4.json"
            )
            extra_path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(OfficialEvidenceError):
                verify_official_item_range_snapshot(root)
            extra_path.unlink()

            first_path = (
                root
                / "raw/game-data/items/equippable-range/cursor-1.json"
            )
            first_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(OfficialEvidenceError):
                verify_official_item_range_snapshot(root)


if __name__ == "__main__":
    unittest.main()

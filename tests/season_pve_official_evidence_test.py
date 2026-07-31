import hashlib
import json
import re
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
    def test_tact_key_origin_timeline_continuation_stays_fail_closed(self):
        evidence_root = (
            Path(__file__).resolve().parents[1]
            / "artifacts"
            / "releases"
            / "2026-07-30-equipment-simulator-e2e-matrix"
            / "universe"
            / "official-snapshot"
            / "official-client-db2-v1"
        )
        audit_path = (
            evidence_root
            / "tact-key-origin-timeline-continuation-audit.json"
        )
        self.assertTrue(
            audit_path.is_file(),
            "TACT-key origin timeline continuation audit is missing",
        )

        audit_bytes = audit_path.read_bytes()
        audit = json.loads(audit_bytes)
        self.assertEqual(audit["schemaVersion"], 1)
        self.assertEqual(
            audit["kind"],
            "tact-key-origin-timeline-continuation-audit",
        )
        self.assertEqual(audit["status"], "blocked")
        self.assertEqual(
            audit["goals"],
            {
                "currentGoalId": (
                    "019fb823-90bf-7f63-ae60-9aaa82662f9c"
                ),
                "continuesGoalId": (
                    "019faddb-abb5-79a3-a477-3cb6e6368120"
                ),
                "continuedGoalFinalStatus": "blocked",
                "continuedGoalMarkedComplete": False,
            },
        )

        scanner = audit["scanner"]
        self.assertEqual(
            scanner["sha256"],
            "bfde604c5829483bac5b5d4a1444f7242feb21188962552b59b75b9cac9bd236",
        )
        self.assertEqual(scanner["corpusSchemaVersion"], 2)
        self.assertEqual(scanner["scopedTestCount"], 13)
        self.assertEqual(scanner["adversarialProbeCount"], 4)
        self.assertEqual(scanner["independentReview"], "no_findings")
        self.assertTrue(scanner["unknownRecognizedStateFailsClosed"])
        self.assertTrue(scanner["effectiveAndRecoverableSeparated"])
        self.assertTrue(scanner["recoveryRequiresEffectiveCoexistence"])

        client = audit["currentClientPostLogin"]
        self.assertEqual(client["build"], "12.0.7.68887")
        self.assertEqual(client["cacheBytes"], 1_376_502)
        self.assertEqual(
            client["cacheSha256"],
            "d5aa61dc347115b4a0c403eb1da4807299aaaeba844bd9bcd30695947b71b723",
        )
        self.assertEqual(client["cacheOnlyRecoverableIdentityCount"], 3)
        self.assertEqual(client["cacheOnlyRecoverableTargetCount"], 2)
        self.assertEqual(client["compositeRecoverableIdentityCount"], 124)
        self.assertEqual(client["compositeRecoverableTargetCount"], 8)
        self.assertEqual(client["blockerTargetHitCount"], 0)
        self.assertFalse(client["coverageChanged"])

        unified = audit["verifiedTimeline"][
            "unifiedRetainedTimelineCrossCheck"
        ]
        self.assertEqual(unified["status"], "complete_no_target")
        self.assertEqual(unified["timelineUniqueBodyCount"], 202)
        self.assertEqual(unified["otherRetainedUniqueBodyCount"], 80)
        self.assertEqual(unified["timelineRetainedIntersectionCount"], 0)
        self.assertEqual(unified["uniqueBodyCount"], 282)
        self.assertEqual(unified["scannedBodyBytes"], 939_441_229)
        self.assertEqual(unified["targetHitCount"], 0)
        self.assertEqual(
            unified["filteredBeta63534Through66198"],
            {
                "bodyCount": 252,
                "uniqueBodyCount": 252,
                "scannedBodyBytes": 814_077_372,
                "bodyHashSetSha256": (
                    "70c7582d621ea93db198b786a5a1313c906f1736709820370bd43524a429a821"
                ),
                "targetHitCount": 0,
            },
        )
        self.assertEqual(
            unified["outsideFilteredBetaRange"],
            {
                "bodyCount": 30,
                "scannedBodyBytes": 125_363_857,
                "distribution": [
                    {
                        "version": "beta",
                        "build": 66220,
                        "bodyCount": 16,
                        "bodyBytes": 115_451_009,
                    },
                    {
                        "version": "ptr",
                        "build": 64741,
                        "bodyCount": 3,
                        "bodyBytes": 194_547,
                    },
                    {
                        "version": "ptr",
                        "build": 64774,
                        "bodyCount": 8,
                        "bodyBytes": 9_520_184,
                    },
                    {
                        "version": "ptr",
                        "build": 68914,
                        "bodyCount": 1,
                        "bodyBytes": 24_766,
                    },
                    {
                        "version": "xptr",
                        "build": 67227,
                        "bodyCount": 2,
                        "bodyBytes": 173_351,
                    },
                ],
            },
        )
        self.assertEqual(
            unified["evidenceRef"],
            {
                "relativeIsolationId": (
                    "verified-beta-timeline-63534-66198-20260801/"
                    "current-scanner-unified-rescan-audit.json"
                ),
                "bytes": 387_033,
                "sha256": (
                    "875ed71a04dbd9e0a403e8b2ce4d5f8e00e08c9aed40bf602b9a97e622caa968"
                ),
            },
        )

        pre = audit["verifiedTimeline"]["pre67227NonBeta"]
        self.assertEqual(pre["status"], "complete_no_target")
        self.assertEqual(pre["buildGroupCount"], 71)
        self.assertEqual(pre["sliceCount"], 121)
        self.assertEqual(pre["verifiedObjectCount"], 1_322)
        self.assertEqual(pre["uniqueBodyCount"], 1_313)
        self.assertEqual(pre["scannedBodyBytes"], 6_539_165_207)
        self.assertEqual(pre["targetHitCount"], 0)
        self.assertEqual(
            pre["evidenceRef"]["sha256"],
            "91183790238848e4163130b24a7118bbbba2cc7be734f99a302388e3c5e5b630",
        )

        later = audit["verifiedTimeline"][
            "atOrAfter67227VerifiedSelection"
        ]
        self.assertEqual(
            later["status"],
            "complete_no_target_for_selection_bound_set",
        )
        self.assertFalse(later["singleAggregateAuditExists"])
        self.assertEqual(later["sourceAuditFileCount"], 45)
        self.assertEqual(
            later["sourceAuditStatuses"],
            {"complete_no_target": 43, "complete": 1, "running": 1},
        )
        self.assertEqual(
            later["productObjectCounts"],
            {"retail": 243, "ptr": 86, "xptr": 53},
        )
        self.assertEqual(later["selectedObjectCount"], 382)
        self.assertEqual(later["scannedBodyCount"], 382)
        self.assertEqual(later["uniqueBodyCount"], 381)
        self.assertEqual(later["scannedBodyBytes"], 788_883_989)
        self.assertEqual(later["targetHitCount"], 0)
        self.assertTrue(later["scopeExhaustedOnlyForSelectionBoundSet"])
        self.assertFalse(later["mayClaimAllVerifiedProviderHistoryExhausted"])
        manifest_path = (
            evidence_root
            / "tact-key-at-or-after-67227-selection-manifest.txt"
        )
        self.assertTrue(
            manifest_path.is_file(),
            "selection-bound deterministic manifest is missing",
        )
        manifest_bytes = manifest_path.read_bytes()
        self.assertEqual(len(manifest_bytes), 6_956)
        self.assertEqual(
            hashlib.sha256(manifest_bytes).hexdigest(),
            "7a58693d961d509f294ae9b3d9509193f1b02e9d26c5d8d9860b20d72cb0a4c7",
        )
        self.assertEqual(
            later["evidenceManifestRef"],
            {
                "path": manifest_path.name,
                "bytes": len(manifest_bytes),
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "memberCount": 45,
                "lineFormat": (
                    "path|file_bytes|file_sha256|selector|selected_objects|"
                    "selected_bodies|selected_body_bytes|selected_hits"
                ),
            },
        )
        manifest_lines = manifest_bytes.decode("utf-8").splitlines()
        self.assertEqual(len(manifest_lines), 45)
        rows = [line.split("|") for line in manifest_lines]
        self.assertTrue(all(len(row) == 8 for row in rows))
        self.assertEqual([row[0] for row in rows], sorted(row[0] for row in rows))
        self.assertEqual(sum(int(row[4]) for row in rows), 382)
        self.assertEqual(sum(int(row[5]) for row in rows), 381)
        self.assertEqual(sum(int(row[6]) for row in rows), 788_883_989)
        self.assertEqual(sum(int(row[7]) for row in rows), 0)
        self.assertFalse(any("http" in field for row in rows for field in row))
        self.assertFalse(
            any(re.match(r"[A-Za-z]:\\", field) for row in rows for field in row)
        )

        retained = audit["verifiedTimeline"][
            "retainedCurrentScannerCrossCheck"
        ]
        self.assertEqual(retained["retainedObjectCount"], 685)
        self.assertEqual(retained["uniqueBodyCount"], 667)
        self.assertEqual(retained["scannedObjectBytes"], 1_565_037_822)
        self.assertEqual(retained["targetHitCount"], 0)
        self.assertFalse(retained["mayClaimProviderHistoryExhausted"])
        self.assertEqual(
            retained["evidenceRef"]["sha256"],
            "2c10c73841754477fbb9722bbce3440a37125bcf4935fea992690ac27c13fcbb",
        )

        rolling = audit["rollingUnverifiedRetainedWindow"]
        self.assertEqual(rolling["status"], "complete_no_target")
        self.assertEqual(rolling["retainedObjectCount"], 963)
        self.assertEqual(rolling["uniqueBodyCount"], 961)
        self.assertEqual(rolling["scannedObjectBytes"], 2_421_168_975)
        self.assertEqual(rolling["targetHitCount"], 0)
        self.assertEqual(rolling["unscannedSelectedObjectCount"], 1_037)
        self.assertFalse(rolling["corpusExhausted"])
        self.assertFalse(rolling["snapshotIsolationProven"])
        self.assertFalse(rolling["sameWindowResumePossible"])
        self.assertEqual(
            rolling["evidenceRef"]["sha256"],
            "5352a7061a903f042e5e467b631adeadd2d855a0d696aa83b44e568a13eef049",
        )

        ptr = audit["laterOfficialContinuity"]["ptr68914"]
        self.assertEqual(
            ptr["status"], "blocked_explicit_empty_keyfile_undecrypted"
        )
        self.assertEqual(ptr["build"], "12.1.0.68914")
        self.assertEqual(ptr["fileDataId"], 982_457)
        self.assertEqual(ptr["recordCount"], 161_175)
        self.assertEqual(ptr["unencryptedRecordCount"], 161_037)
        self.assertEqual(ptr["encryptedRecordCount"], 138)
        self.assertEqual(
            ptr["targetEncryptedRecordCounts"],
            {
                "14f4b11d7b067aa2": 12,
                "62bf37a70e6d54f6": 8,
                "fbbf041f980ce0dc": 44,
            },
        )
        self.assertFalse(ptr["exactBuild68887Closed"])
        self.assertEqual(
            ptr["keyMaterialAvailabilityBeyondThisRun"], "not_assessed"
        )
        self.assertEqual(ptr["runnerReview"], "no_findings")
        self.assertEqual(ptr["runnerTestCount"], 18)
        self.assertEqual(
            ptr["evidenceRef"]["sha256"],
            "f8f5c653f3e03315d98ddde09ad5a591961fa511bbf6985e36810c1fc435ab02",
        )

        truth = audit["remainingTruth"]
        self.assertEqual(truth["sourceUnionKeyCount"], 9)
        self.assertEqual(truth["requiredKeyCount"], 12)
        self.assertEqual(truth["recoveredEncryptedRecordCount"], 114)
        self.assertEqual(truth["encryptedRecordCount"], 178)
        self.assertEqual(truth["unavailableEncryptedRecordCount"], 64)
        self.assertEqual(truth["officialSourceProjection"], {
            "complete": 0,
            "partial": 9,
            "blocked": 10,
            "gapCount": 21,
        })
        self.assertFalse(truth["universeComplete"])
        self.assertFalse(truth["productionPromotionAllowed"])

        production = audit["productionSnapshot"]
        self.assertEqual(production["generation"], 35)
        self.assertEqual(
            production["manifestRevision"],
            "season-manifest:sha256:20453991e93a1dc1650dbacfd85bdd042e9b020737c7851bef943f1e3e68883a",
        )
        self.assertEqual(
            production["gearReleaseId"],
            "gear-release:sha256:9299fe1f942dc272f402e4d735d6a1bf8111a8f156464e0777cd6df78769edc7",
        )
        self.assertEqual(
            production["communityReleaseId"],
            "community-release:sha256:686708be049323a979b66bfba42cae3f2b80f7337e740d26b299fd73e0665804",
        )
        self.assertEqual(production["dataHealth"], "partial")
        self.assertEqual(production["backend"], {
            "activeState": "active",
            "subState": "running",
            "restartCount": 0,
        })
        self.assertEqual(production["gearRefreshService"], {
            "activeState": "failed",
            "subState": "failed",
            "result": "timeout",
        })
        self.assertTrue(production["matchesGoalBaseline"])
        self.assertFalse(production["mutationPerformed"])

        safety = audit["safety"]
        self.assertTrue(safety["productionStateRecheckedInThisAudit"])
        self.assertFalse(safety["productionMutation"])
        self.assertFalse(safety["releasePointerMutation"])
        self.assertFalse(safety["rawKeyMaterialInAudit"])
        self.assertFalse(safety["absoluteLocalPathInAudit"])
        self.assertEqual(safety["historicalHandoffStatus"], "blocked")

        serialized = audit_bytes.decode("utf-8")
        self.assertNotIn("http://", serialized)
        self.assertNotIn("https://", serialized)
        self.assertIsNone(re.search(r"[A-Za-z]:\\\\", serialized))
        self.assertNotIn('"/var/', serialized)
        self.assertNotIn('"/home/', serialized)
        self.assertNotIn('"/opt/', serialized)

    def test_historical_authorized_cache_subset_scan_audit_is_fail_closed(self):
        evidence_root = (
            Path(__file__).resolve().parents[1]
            / "artifacts"
            / "releases"
            / "2026-07-30-equipment-simulator-e2e-matrix"
            / "universe"
            / "official-snapshot"
            / "official-client-db2-v1"
        )
        audit_path = (
            evidence_root
            / "historical-authorized-cache-subset-scan-audit.json"
        )
        self.assertTrue(
            audit_path.is_file(),
            "historical authorized cache subset scan audit is missing",
        )

        audit_bytes = audit_path.read_bytes()
        audit = json.loads(audit_bytes)
        self.assertEqual(audit["status"], "blocked")
        self.assertEqual(audit["originalAuthorizedSet"]["descriptorCount"], 63)
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["descriptorCount"], 52
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["missingDescriptorCount"], 11
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["missingDistribution"],
            {"Beta": {"64124": 3, "64228": 1, "64339": 7}},
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["distribution"],
            {
                "XPTR": {"67227": 2},
                "Beta": {
                    "64339": 12,
                    "64529": 7,
                    "64611": 6,
                    "64741": 12,
                    "64774": 13,
                },
            },
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["downloadedBodyCount"], 52
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["scannedBodyCount"], 52
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["totalDownloadedBytes"],
            58_259_882,
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["uniqueXfthV9BodyCount"], 52
        )
        self.assertEqual(
            audit["recoveredAuthorizedSubset"]["targetIdentityHitCount"], 0
        )
        self.assertEqual(
            audit["remainingTruth"]["missingTargetKeyCount"], 3
        )
        self.assertEqual(
            audit["remainingTruth"]["unavailableEncryptedRecordCount"], 64
        )
        self.assertEqual(audit["remainingTruth"]["universeGapCount"], 21)
        blocker = (
            "AUTHORIZED_HISTORICAL_CACHE_SET_INCOMPLETE_"
            "11_DESCRIPTORS_UNRECOVERED"
        )
        self.assertIn(blocker, audit["blockers"])
        self.assertNotIn(
            "HISTORICAL_CACHE_BODIES_NOT_YET_SCANNED", audit["blockers"]
        )

        fresh = audit["freshVerifiedMetadata"]
        self.assertEqual(fresh["descriptorCount"], 52)
        self.assertEqual(
            fresh["distribution"],
            {
                "XPTR": {"67227": 2},
                "Beta": {
                    "64124": 3,
                    "64228": 1,
                    "64339": 19,
                    "64529": 7,
                    "64611": 6,
                    "64741": 9,
                    "64774": 5,
                },
            },
        )
        self.assertFalse(fresh["sameIdentityAsAuthorizedSetProven"])
        self.assertFalse(fresh["inheritsAuthorizedDownloadScope"])
        self.assertFalse(fresh["bodiesDownloaded"])
        self.assertEqual(
            fresh["requestUrlHashSetSha256"],
            "0a00f1b7705102caa01eb76a40b7542d35a83f987d9677391214ad4fc0f5df65",
        )
        self.assertEqual(
            fresh["objectIdentityHashSetSha256"],
            "c6df57bfa7e647cca4768929cf2e42fc30d67ed884be8a9dcb908ee6064a3a19",
        )

        external = audit["externalEvidence"]
        self.assertEqual(
            external["manifest"],
            {
                "relativeIsolationId": (
                    "historical-recovered-52/manifest.internal.json"
                ),
                "bytes": 58_888,
                "sha256": (
                    "c3ad739bb982281191de2bd08fb96a9ee67e347b6aaa08376e30d5e214ef61dd"
                ),
                "requestUrlHashSetSha256": (
                    "412facab891e32e26ca895b8ffd17371e4ea0e40a0c292fe05304731c1d212f7"
                ),
                "objectIdentityHashSetSha256": (
                    "5c9f0508d40fcc93ae6fd959b26db10b16ef9045569f5c4691263f52044cd3bb"
                ),
            },
        )
        self.assertEqual(
            external["xptrRedactedAudit"],
            {
                "relativeIsolationId": (
                    "historical-recovered-52/xptr/redacted-audit.json"
                ),
                "bytes": 2_974,
                "sha256": (
                    "00bb2974ad03f977dc461d6347db67caa2b34165c8cd7671912a1aea07a3e7b4"
                ),
            },
        )
        self.assertEqual(
            external["betaRedactedAudit"],
            {
                "relativeIsolationId": (
                    "historical-recovered-52/beta/redacted-audit.json"
                ),
                "bytes": 75_494,
                "sha256": (
                    "910198a092c2ef4839d93781bb64200ec178d445558b15f7beec69fdd1477585"
                ),
            },
        )

        serialized = audit_bytes.decode("utf-8")
        self.assertNotIn("http://", serialized)
        self.assertNotIn("https://", serialized)
        self.assertIsNone(re.search(r"[A-Za-z]:\\\\", serialized))
        self.assertNotIn('"/var/', serialized)
        self.assertNotIn('"/home/', serialized)
        self.assertNotIn('"/opt/', serialized)
        self.assertFalse(audit["containsRawKeyOrMaterial"])
        self.assertFalse(audit["containsAbsoluteLocalPaths"])
        self.assertTrue(audit["externalEvidenceAclRestricted"])

        expected_ref = {
            "path": audit_path.name,
            "bytes": len(audit_bytes),
            "sha256": hashlib.sha256(audit_bytes).hexdigest(),
        }
        scanner_path = (
            evidence_root
            / "current-client-tact-key-scanner-and-local-replay-audit.json"
        )
        continuation_path = (
            evidence_root
            / "current-client-tact-key-continuation-audit.json"
        )
        scanner_bytes = scanner_path.read_bytes()
        scanner = json.loads(scanner_bytes)
        continuation = json.loads(continuation_path.read_bytes())
        self.assertEqual(
            scanner["historicalAuthorizedCacheSubsetEvidenceRef"], expected_ref
        )
        self.assertEqual(
            continuation["historicalAuthorizedCacheSubset"]["evidenceRef"],
            expected_ref,
        )
        self.assertEqual(
            continuation["scannerAndLocalReplayContinuation"]["evidenceRef"],
            {
                "path": scanner_path.name,
                "bytes": len(scanner_bytes),
                "sha256": hashlib.sha256(scanner_bytes).hexdigest(),
            },
        )
        self.assertIn(blocker, scanner["blockers"])
        self.assertIn(blocker, continuation["blockers"])
        self.assertNotIn(
            "HISTORICAL_CACHE_BODIES_NOT_YET_SCANNED",
            scanner["blockers"],
        )
        self.assertNotIn(
            "HISTORICAL_CACHE_BODIES_NOT_YET_SCANNED",
            continuation["blockers"],
        )

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

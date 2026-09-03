import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/refactor/chickenbro-simc-capacity-cleanup-manifest.json"

EXPECTED_DATABASES = {
    "wow_gear_evidence_01adf184_r14": (5_237_750_807, 2_116_322),
    "wow_gear_evidence_0be65754_r24": (5_517_827_095, 2_375_007),
    "wow_gear_evidence_145dee16_r22": (5_964_094_487, 2_802_680),
    "wow_gear_evidence_15f514d5_r23": (5_813_812_247, 2_658_418),
}
EXPECTED_COMPANIONS = {
    "wow_gear_evidence_01adf184_r14": "/etc/wow-backend-candidate-gear-evidence-r14.env",
    "wow_gear_evidence_0be65754_r24": "/etc/wow-backend-candidate-gear-evidence-r24.env",
    "wow_gear_evidence_145dee16_r22": "/etc/wow-backend-candidate-gear-evidence-r22.env",
    "wow_gear_evidence_15f514d5_r23": "/etc/wow-backend-candidate-gear-evidence-r23.env",
}
EXPECTED_COMPANION_HASHES = {
    "wow_gear_evidence_01adf184_r14": "e4f0e3cdf8d3574dc9daaa020cc6777ac591c0e068ba9e1dc5cc034ba9d4f8e1",
    "wow_gear_evidence_0be65754_r24": "00f0e3856318a4ca20ac8d824545330d5dfb876c7978a58f4664dce8e7297ff2",
    "wow_gear_evidence_145dee16_r22": "af56e04898b7739e2520940feb9d967bb55afc1d1a83ccd1b55055ee258a340a",
    "wow_gear_evidence_15f514d5_r23": "37ebf357edf4670ef52c3cee6525ba8e95df2ce8b8e37adb6e5acedeeeae2f68",
}


class ChickenbroSimcCapacityCleanupManifestTest(unittest.TestCase):
    def test_manifest_allows_only_rejected_evidence_databases_after_whitelist_restore(self):
        self.assertTrue(MANIFEST.is_file(), "capacity cleanup manifest is missing")
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(payload["schemaVersion"], 2)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertFalse(payload["deletionAuthorized"])
        self.assertTrue(payload["capacityPreCleanupAuthorized"])
        self.assertEqual(
            payload["targetIdentity"],
            {
                "provider": "tencent_cvm",
                "instanceId": "ins-93tgv1rb",
                "region": "ap-shanghai",
                "zone": "ap-shanghai-2",
                "publicAddress": "124.223.51.33",
                "sshTarget": "wow-lighthouse",
                "refreshRequiredBeforeApply": True,
            },
        )
        self.assertEqual(payload["businessRecovery"]["sourceDatabase"], "wow_test")
        self.assertEqual(payload["businessRecovery"]["sourceMode"], "read_only")
        self.assertEqual(payload["businessRecovery"]["manifestSchema"], "chickenbro-whitelist-recovery-v1")
        self.assertEqual(payload["businessRecovery"]["status"], "restore_verified")
        self.assertRegex(payload["businessRecovery"]["manifestSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(payload["businessRecovery"]["migrationReconciliationStatus"], "matched")
        self.assertEqual(payload["businessRecovery"]["restoreReconciliationStatus"], "matched")
        self.assertEqual(payload["rejectedEvidenceRecovery"], {"required": False})
        recovery_inventory = ROOT / payload["evidence"]["recoveryInventory"]
        self.assertTrue(recovery_inventory.is_file())
        self.assertEqual(payload["totalCandidateBytes"], sum(item[0] for item in EXPECTED_DATABASES.values()))
        self.assertEqual(
            payload["evidence"]["configurationScanRoots"],
            ["/etc", "/opt/chickenbro", "/opt/wow-mini-program", "/opt/wow-v2-staging", "/var/www"],
        )

        candidates = {item["name"]: item for item in payload["candidates"]}
        self.assertEqual(set(candidates), set(EXPECTED_DATABASES))
        for name, (size_bytes, exact_rows) in EXPECTED_DATABASES.items():
            candidate = candidates[name]
            self.assertEqual(candidate["kind"], "postgres_database")
            self.assertEqual(candidate["sizeBytes"], size_bytes)
            self.assertEqual(candidate["currentConnections"], 0)
            self.assertIsInstance(candidate["approximateRows"], int)
            self.assertEqual(candidate["exactRows"], exact_rows)
            self.assertEqual(candidate["configurationReferences"], [EXPECTED_COMPANIONS[name]])
            self.assertEqual(candidate["requiredAbsentCompanion"], EXPECTED_COMPANIONS[name])
            self.assertEqual(candidate["sameRootBackupMatches"], [])
            self.assertEqual(candidate["decision"], "rejected_evidence_exact_precleanup")
            self.assertFalse(candidate["recoveryRequired"])
            self.assertEqual(
                candidate["applyStatus"],
                "ready_for_reviewed_capacity_precleanup",
            )

        requirements = set(payload["requiredBeforeApply"])
        self.assertIn("hash-bound whitelist recovery manifest with isolated restore reconciliation", requirements)
        self.assertIn("fresh exact target identity from Tencent instance metadata", requirements)
        self.assertIn("fresh zero-connection, zero-reference and zero-open-handle probe per exact database", requirements)
        self.assertIn("explicit wow_test read-only protection", requirements)
        self.assertIn("fresh exact COUNT(*) row identity for every exact database", requirements)
        self.assertIn("regular non-symlink companion env with exact /etc realpath and content hash", requirements)
        self.assertIn("all-pair mutation-free preflight followed by durable per-pair boundary journals", requirements)
        self.assertFalse(any("archive for every exact database" in item for item in requirements))
        self.assertEqual(
            payload["capacityCleanupCompanions"],
            [
                {
                    "database": name,
                    "envFile": EXPECTED_COMPANIONS[name],
                    "observedAt": next(
                        item["observedAt"]
                        for item in payload["capacityCleanupCompanions"]
                        if item["database"] == name
                    ),
                    "contentSha256": EXPECTED_COMPANION_HASHES[name],
                    "systemdUnitReferences": [],
                    "runningProcessReferences": 0,
                    "openHandles": 0,
                    "applyStatus": "ready_for_reviewed_capacity_precleanup",
                }
                for name in EXPECTED_DATABASES
            ],
        )

        serialized = json.dumps(payload, sort_keys=True).lower()
        for forbidden in ("password", "secret", "token", "cookie", "openid", "pgpass"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

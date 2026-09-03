import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/refactor/chickenbro-simc-capacity-cleanup-manifest.json"

EXPECTED_DATABASES = {
    "wow_gear_evidence_01adf184_r14": 5_237_750_807,
    "wow_gear_evidence_0be65754_r24": 5_517_827_095,
    "wow_gear_evidence_145dee16_r22": 5_964_094_487,
    "wow_gear_evidence_15f514d5_r23": 5_813_812_247,
}
EXPECTED_COMPANIONS = {
    "wow_gear_evidence_01adf184_r14": "/etc/wow-backend-candidate-gear-evidence-r14.env",
    "wow_gear_evidence_0be65754_r24": "/etc/wow-backend-candidate-gear-evidence-r24.env",
    "wow_gear_evidence_145dee16_r22": "/etc/wow-backend-candidate-gear-evidence-r22.env",
    "wow_gear_evidence_15f514d5_r23": "/etc/wow-backend-candidate-gear-evidence-r23.env",
}


class ChickenbroSimcCapacityCleanupManifestTest(unittest.TestCase):
    def test_manifest_allows_only_rejected_evidence_databases_after_whitelist_restore(self):
        self.assertTrue(MANIFEST.is_file(), "capacity cleanup manifest is missing")
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(payload["schemaVersion"], 2)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertFalse(payload["deletionAuthorized"])
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
        self.assertEqual(payload["businessRecovery"]["status"], "not_run")
        self.assertEqual(payload["rejectedEvidenceRecovery"], {"required": False})
        recovery_inventory = ROOT / payload["evidence"]["recoveryInventory"]
        self.assertTrue(recovery_inventory.is_file())
        self.assertEqual(payload["totalCandidateBytes"], sum(EXPECTED_DATABASES.values()))

        candidates = {item["name"]: item for item in payload["candidates"]}
        self.assertEqual(set(candidates), set(EXPECTED_DATABASES))
        for name, size_bytes in EXPECTED_DATABASES.items():
            candidate = candidates[name]
            self.assertEqual(candidate["kind"], "postgres_database")
            self.assertEqual(candidate["sizeBytes"], size_bytes)
            self.assertEqual(candidate["currentConnections"], 0)
            self.assertEqual(candidate["configurationReferences"], [EXPECTED_COMPANIONS[name]])
            self.assertEqual(candidate["requiredAbsentCompanion"], EXPECTED_COMPANIONS[name])
            self.assertEqual(candidate["sameRootBackupMatches"], [])
            self.assertEqual(candidate["decision"], "rejected_evidence_exact_precleanup")
            self.assertFalse(candidate["recoveryRequired"])
            self.assertEqual(
                candidate["applyStatus"],
                "blocked_pending_whitelist_restore_and_fresh_live_gates",
            )

        requirements = set(payload["requiredBeforeApply"])
        self.assertIn("hash-bound whitelist recovery manifest with isolated restore reconciliation", requirements)
        self.assertIn("fresh exact target identity from Tencent instance metadata", requirements)
        self.assertIn("fresh zero-connection, zero-reference and zero-open-handle probe per exact database", requirements)
        self.assertIn("explicit wow_test read-only protection", requirements)
        self.assertFalse(any("archive for every exact database" in item for item in requirements))
        self.assertEqual(
            payload["capacityCleanupCompanions"],
            [
                {
                    "database": name,
                    "envFile": EXPECTED_COMPANIONS[name],
                    "systemdUnitReferences": [],
                    "runningProcessReferences": 0,
                    "openHandles": 0,
                    "applyStatus": "blocked_pending_exact_hash_and_reviewed_removal",
                }
                for name in EXPECTED_DATABASES
            ],
        )

        serialized = json.dumps(payload, sort_keys=True).lower()
        for forbidden in ("password", "secret", "token", "cookie", "openid", "pgpass"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

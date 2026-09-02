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


class ChickenbroSimcCapacityCleanupManifestTest(unittest.TestCase):
    def test_manifest_is_exact_and_fail_closed_before_independent_restore(self):
        self.assertTrue(MANIFEST.is_file(), "capacity cleanup manifest is missing")
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(payload["mode"], "dry-run")
        self.assertFalse(payload["deletionAuthorized"])
        self.assertEqual(payload["independentRecovery"]["status"], "missing")
        self.assertEqual(payload["totalCandidateBytes"], sum(EXPECTED_DATABASES.values()))

        candidates = {item["name"]: item for item in payload["candidates"]}
        self.assertEqual(set(candidates), set(EXPECTED_DATABASES))
        for name, size_bytes in EXPECTED_DATABASES.items():
            candidate = candidates[name]
            self.assertEqual(candidate["kind"], "postgres_database")
            self.assertEqual(candidate["sizeBytes"], size_bytes)
            self.assertEqual(candidate["currentConnections"], 0)
            self.assertEqual(candidate["configurationReferences"], [])
            self.assertEqual(candidate["sameRootBackupMatches"], [])
            self.assertEqual(candidate["decision"], "candidate_only")
            self.assertEqual(candidate["applyStatus"], "blocked_pending_independent_backup_restore")

        serialized = json.dumps(payload, sort_keys=True).lower()
        for forbidden in ("password", "secret", "token", "cookie", "openid", "pgpass"):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()

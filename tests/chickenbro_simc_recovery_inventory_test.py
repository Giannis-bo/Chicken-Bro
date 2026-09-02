import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "refactor" / "chickenbro-simc-recovery-inventory.json"


class ChickenbroSimcRecoveryInventoryTest(unittest.TestCase):
    def test_recovery_inventory_is_exact_and_fail_closed(self):
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

        self.assertEqual(inventory["schemaVersion"], 1)
        self.assertEqual(
            inventory["status"],
            "read_only_insufficient_for_cleanup_or_candidate",
        )
        self.assertFalse(inventory["mutationPerformed"])

        snapshots = inventory["providerSnapshots"]
        self.assertEqual(snapshots["visibleCount"], 1)
        self.assertEqual(len(snapshots["items"]), 1)
        snapshot = snapshots["items"][0]
        self.assertEqual(snapshot["status"], "normal")
        self.assertEqual(snapshot["diskAttribute"], "system_disk")
        self.assertEqual(snapshot["restoreVerification"], "not_run")
        self.assertEqual(snapshot["containsCurrentDatabaseState"], "unproven")
        self.assertFalse(snapshot["usableForCurrentCleanup"])

        channels = inventory["serverBackupChannels"]
        self.assertFalse(channels["independentMountPresent"])
        self.assertFalse(channels["objectStorageClientConfigured"])
        self.assertEqual(channels["availableClientTools"], [])
        pg_basebackup = channels["pgBasebackupTemplate"]
        self.assertTrue(pg_basebackup["present"])
        self.assertEqual(pg_basebackup["enabledInstanceCount"], 0)
        self.assertEqual(
            pg_basebackup["postgresDataDeviceId"],
            pg_basebackup["backupParentDeviceId"],
        )
        self.assertFalse(pg_basebackup["independent"])

        conclusions = inventory["conclusions"]
        self.assertFalse(conclusions["currentIndependentBackup"])
        self.assertFalse(conclusions["successfulRestoreIdentity"])
        self.assertFalse(conclusions["candidateDatabaseProvisioningAuthorized"])
        self.assertFalse(conclusions["legacyDatabaseDeletionAuthorized"])


if __name__ == "__main__":
    unittest.main()

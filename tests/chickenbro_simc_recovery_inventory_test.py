import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "refactor" / "chickenbro-simc-recovery-inventory.json"


class ChickenbroSimcRecoveryInventoryTest(unittest.TestCase):
    def test_recovery_inventory_invalidates_stale_provider_evidence_and_uses_business_whitelist(self):
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

        self.assertEqual(inventory["schemaVersion"], 2)
        self.assertEqual(
            inventory["status"],
            "business_whitelist_restore_verified_capacity_precleanup_authorized",
        )
        self.assertTrue(inventory["mutationPerformed"])

        invalidated = inventory["invalidatedProviderInventory"]
        self.assertEqual(invalidated["instanceId"], "lhins-dr6tkl63")
        self.assertEqual(invalidated["region"], "ap-guangzhou")
        self.assertFalse(invalidated["validForTarget"])

        target = inventory["targetIdentity"]
        self.assertEqual(target["provider"], "tencent_cvm")
        self.assertEqual(target["instanceId"], "ins-93tgv1rb")
        self.assertEqual(target["region"], "ap-shanghai")
        self.assertEqual(target["zone"], "ap-shanghai-2")
        self.assertEqual(target["publicAddress"], "124.223.51.33")
        self.assertEqual(target["sshTarget"], "wow-lighthouse")
        self.assertTrue(target["refreshRequiredBeforeApply"])

        recovery = inventory["businessWhitelistRecovery"]
        self.assertEqual(recovery["sourceDatabase"], "wow_test")
        self.assertEqual(recovery["sourceMode"], "read_only")
        self.assertEqual(recovery["status"], "restore_verified")
        self.assertEqual(recovery["manifestSchema"], "chickenbro-whitelist-recovery-v1")
        self.assertEqual(recovery["candidateDatabase"], "chickenbro_prod")
        self.assertEqual(
            recovery["verificationDatabase"],
            "chickenbro_restore_verify_20260903_054604__c74b7e3af237",
        )
        self.assertRegex(recovery["manifestSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(recovery["archiveSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(recovery["migrationReportSha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(recovery["restoreReconciliationSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(recovery["migrationReconciliationStatus"], "matched")
        self.assertEqual(recovery["restoreReconciliationStatus"], "matched")
        self.assertEqual(recovery["acceptedCount"], 1197)
        self.assertEqual(recovery["rejectedCount"], 392)
        self.assertEqual(inventory["rejectedEvidenceDatabases"]["recoveryRequired"], False)

        snapshots = inventory["providerSnapshots"]
        self.assertEqual(snapshots["visibleCount"], 1)
        self.assertEqual(len(snapshots["items"]), 1)
        snapshot = snapshots["items"][0]
        self.assertEqual(snapshot["status"], "normal")
        self.assertEqual(snapshot["diskAttribute"], "system_disk")
        self.assertEqual(snapshot["restoreVerification"], "not_run")
        self.assertEqual(snapshot["containsCurrentDatabaseState"], "unproven")
        self.assertFalse(snapshot["usableForCurrentCleanup"])

        conclusions = inventory["conclusions"]
        self.assertFalse(conclusions["currentIndependentBackup"])
        self.assertTrue(conclusions["whitelistRestoreVerified"])
        self.assertTrue(conclusions["candidateDatabaseProvisioningAuthorized"])
        self.assertTrue(conclusions["capacityPreCleanupAuthorized"])
        self.assertFalse(conclusions["wowTestRetirementAuthorized"])


if __name__ == "__main__":
    unittest.main()

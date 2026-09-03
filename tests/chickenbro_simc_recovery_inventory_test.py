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
            "corrected_recovery_contract_provisioning_authorized_not_run",
        )
        self.assertFalse(inventory["mutationPerformed"])

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
        self.assertEqual(recovery["status"], "authorized_not_run")
        self.assertEqual(recovery["manifestSchema"], "chickenbro-whitelist-recovery-v1")
        self.assertEqual(recovery["candidateDatabase"], "chickenbro_prod")
        self.assertEqual(recovery["verificationDatabasePattern"], "chickenbro_restore_verify_*")
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
        self.assertFalse(conclusions["whitelistRestoreVerified"])
        self.assertTrue(conclusions["candidateDatabaseProvisioningAuthorized"])
        self.assertFalse(conclusions["capacityPreCleanupAuthorized"])
        self.assertFalse(conclusions["wowTestRetirementAuthorized"])


if __name__ == "__main__":
    unittest.main()

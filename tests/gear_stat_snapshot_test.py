import copy
import unittest

from server.gear_stat_snapshot import (
    STAT_SIGNATURE_SCHEMA_REVISION,
    build_stat_signature,
    client_key_hash,
    verified_snapshot_record,
)


DEPENDENCIES = {
    "seasonRevision": "season-17",
    "gearRuleRevision": "rules-v1",
    "resolverContractRevision": "resolver-v1",
    "serializerRevision": "serializer-v1",
    "simcRuntimeRevision": "simc-v1",
    "statPolicyRevision": "stats-v1",
    "selectionSchemaRevision": "intent-v1",
    "capabilityRevision": "capability-v1",
}


def resolved_snapshot():
    return {
        "contractRevision": "gear-resolved-snapshot-v1",
        "status": "verified",
        "resolvedGearSignature": "sha256:" + "1" * 64,
        "dependencyVector": dict(DEPENDENCIES),
    }


def release_context():
    return {
        "manifestRevision": "season-manifest:sha256:" + "2" * 64,
        "pointerGeneration": 9,
        "gearCatalogRevision": "gear-release:sha256:" + "3" * 64,
        "communityTemplateRevision": "community-release:sha256:" + "4" * 64,
        "talentCatalogRevision": "talent-catalog:r1",
    }


class GearStatSnapshotPolicyTest(unittest.TestCase):
    def test_signature_is_order_stable_and_revision_complete(self):
        first = build_stat_signature(resolved_snapshot(), "profile-lines", release_context())
        reordered_snapshot = {
            "dependencyVector": dict(reversed(list(DEPENDENCIES.items()))),
            "resolvedGearSignature": "sha256:" + "1" * 64,
            "status": "verified",
            "contractRevision": "gear-resolved-snapshot-v1",
        }
        second = build_stat_signature(reordered_snapshot, "profile-lines", dict(reversed(list(release_context().items()))))

        self.assertEqual(first, second)
        self.assertEqual(first["schemaRevision"], STAT_SIGNATURE_SCHEMA_REVISION)
        self.assertRegex(first["statSignature"], r"^stat-snapshot:sha256:[0-9a-f]{64}$")
        self.assertRegex(first["profileHash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first["pointerGeneration"], 9)

        changed_runtime = resolved_snapshot()
        changed_runtime["dependencyVector"]["simcRuntimeRevision"] = "simc-v2"
        self.assertNotEqual(
            first["statSignature"],
            build_stat_signature(changed_runtime, "profile-lines", release_context())["statSignature"],
        )
        self.assertNotEqual(
            first["statSignature"],
            build_stat_signature(resolved_snapshot(), "different-profile", release_context())["statSignature"],
        )

    def test_signature_rejects_non_verified_or_incomplete_authority(self):
        blocked = resolved_snapshot()
        blocked["status"] = "blocked"
        with self.assertRaises(ValueError):
            build_stat_signature(blocked, "profile", release_context())

        missing_revision = resolved_snapshot()
        missing_revision["dependencyVector"].pop("simcRuntimeRevision")
        with self.assertRaises(ValueError):
            build_stat_signature(missing_revision, "profile", release_context())

        with self.assertRaises(ValueError):
            build_stat_signature(resolved_snapshot(), "", release_context())

    def test_verified_record_is_bounded_and_drops_dps_raw_output_and_client_signature(self):
        signature = build_stat_signature(resolved_snapshot(), "profile-lines", release_context())
        raw = {
            "statStatus": "verified",
            "statSource": "simulationcraft_json",
            "classKey": "mage",
            "specKey": "arcane",
            "maxLevel": 90,
            "itemLevel": {"average": 700},
            "primary": {"key": "intellect", "value": "12345"},
            "stamina": {"key": "stamina", "value": "54321"},
            "secondary": [{"key": "crit", "value": "2345", "percent": "12.3%"}],
            "armor": {"key": "armor", "value": "1000"},
            "blockers": [],
            "dps": 999999,
            "meanDps": 888888,
            "rawOutput": "secret simc output",
            "profile": "raw profile",
            "statSignature": "client-forged",
            "gearItems": [{"payload": "unbounded"}],
        }
        record = verified_snapshot_record(signature, raw, verified_at="2026-07-11T12:00:00+00:00")

        self.assertEqual(record["statSignature"], signature["statSignature"])
        self.assertEqual(record["snapshot"]["statStatus"], "verified")
        self.assertEqual(record["snapshot"]["secondary"][0]["key"], "crit")
        for forbidden in ("dps", "meanDps", "rawOutput", "profile", "gearItems"):
            self.assertNotIn(forbidden, record["snapshot"])
        self.assertNotEqual(record["snapshotHash"], "client-forged")

        blocked = copy.deepcopy(raw)
        blocked["statStatus"] = "blocked"
        with self.assertRaises(ValueError):
            verified_snapshot_record(signature, blocked, verified_at="2026-07-11T12:00:00+00:00")

    def test_client_key_is_bounded_one_way_and_empty_safe(self):
        self.assertRegex(client_key_hash("client-a"), r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(client_key_hash("client-a"), client_key_hash(" client-a "))
        self.assertNotEqual(client_key_hash("client-a"), client_key_hash("client-b"))
        self.assertEqual(client_key_hash(""), "")


if __name__ == "__main__":
    unittest.main()

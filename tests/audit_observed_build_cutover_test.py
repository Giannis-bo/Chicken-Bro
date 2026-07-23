import importlib.util
from pathlib import Path
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit-observed-build-cutover.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_observed_build_cutover",
    SCRIPT_PATH,
)
AUDIT = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(AUDIT)


class VerifiedClient:
    def __init__(self):
        self.slots = AUDIT._expected_slots()
        self.templates = {
            AUDIT._slot_key(slot): self.template(slot, index)
            for index, slot in enumerate(self.slots)
        }
        self.calls = {
            "talent": 0,
            "gear": 0,
            "importTalent": 0,
            "importGear": 0,
        }

    @staticmethod
    def template(slot, index):
        return {
            "id": "build-projection:sha256:" + f"{index:064x}",
            "templateSetId": "template-set:sha256:" + "a" * 64,
            "snapshotId": "observed-build:sha256:" + f"{index:064x}",
            "sourceIdentity": (
                f"raiderio:cn|realm-{index}|player-{index}"
            ),
            "pointerGeneration": 3,
            "slotStatus": "verified",
            **slot,
            "status": "verified",
            "projectionStatus": "verified",
            "canApplyVisual": True,
            "canApplyGear": True,
            "websimExportCode": (
                f"websim:{slot['classKey']}:{slot['specKey']}:"
                f"{slot['heroKey']}:node-{index}:1"
            ),
        }

    def talent(self, slot):
        self.calls["talent"] += 1
        return 200, {
            "communityTemplates": [
                self.templates[AUDIT._slot_key(slot)]
            ]
        }

    def gear(self, class_key, spec_key):
        self.calls["gear"] += 1
        templates = []
        for slot in self.slots:
            if (
                slot["classKey"] == class_key
                and slot["specKey"] == spec_key
            ):
                template = {
                    **self.templates[AUDIT._slot_key(slot)],
                    "status": "complete",
                }
                templates.append(template)
        return 200, {
            "manifestRevision": "manifest-r1",
            "communityTemplates": templates,
        }

    def import_talent(self, slot, code):
        self.calls["importTalent"] += 1
        return 200, {
            **slot,
            "talentState": {
                "selectedNodes": [{"id": code, "rank": 1}]
            },
            "validation": {"status": "encoded"},
        }

    def import_gear(self, **_request):
        self.calls["importGear"] += 1
        return 200, {
            "status": "verified",
            "data": {
                "status": "verified",
                "importedGearBySlot": {
                    "head": {"itemId": "230001"}
                },
                "resolvedSnapshot": {
                    "status": "verified",
                    "resolvedGearSignature": "sha256:" + "b" * 64,
                },
            },
        }


class FailedClient:
    def talent(self, _slot):
        return 503, {}

    def gear(self, _class_key, _spec_key):
        return 503, {}

    def import_talent(self, _slot, _code):
        raise AssertionError("failed reads cannot reach import")

    def import_gear(self, **_request):
        raise AssertionError("failed reads cannot reach import")


class ObservedBuildCutoverAuditTest(unittest.TestCase):
    def test_exhaustively_verifies_all_public_reads_and_imports(self):
        client = VerifiedClient()

        result = AUDIT.run_audit(client)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(
            result["counts"]["verifiedTalentSlots"],
            80,
        )
        self.assertEqual(
            result["counts"]["verifiedGearTemplates"],
            80,
        )
        self.assertEqual(
            result["counts"]["matchedTalentGearSlots"],
            80,
        )
        self.assertEqual(
            client.calls,
            {
                "talent": 80,
                "gear": 40,
                "importTalent": 80,
                "importGear": 80,
            },
        )

    def test_failure_output_is_bounded(self):
        result = AUDIT.run_audit(FailedClient())

        self.assertEqual(result["status"], "blocked")
        self.assertGreater(result["counts"]["failureCount"], 12)
        self.assertEqual(len(result["failures"]), 12)


if __name__ == "__main__":
    unittest.main()

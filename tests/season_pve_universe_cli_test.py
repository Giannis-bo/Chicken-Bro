import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "season-pve-universe.py"


class SeasonPveUniverseCliTest(unittest.TestCase):
    def _write_json(self, root, name, value):
        path = root / name
        path.write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_blocked_report_exits_nonzero_and_never_prints_raw_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = self._write_json(
                root,
                "policy.json",
                {
                    "schemaVersion": 1,
                    "seasonRevision": "season-r1",
                    "sourcePolicyRevision": "policy-r1",
                    "status": "approved",
                    "sources": [
                        {
                            "sourceKey": source_key,
                            "sourceType": "raid",
                            "required": True,
                            "membershipMode": "direct_drop",
                            "authorityRefs": ["official"],
                        }
                        for source_key in ("raid:one", "raid:two")
                    ],
                },
            )
            discovery = self._write_json(
                root,
                "discovery.json",
                {
                    "schemaVersion": 1,
                    "seasonRevision": "season-r1",
                    "sourcePolicyRevision": "policy-r1",
                    "asOf": "2026-07-29T13:00:00Z",
                    "sources": [
                        {
                            "sourceKey": "raid:one",
                            "status": "verified",
                            "capturedAt": "2026-07-29T12:00:00Z",
                            "validUntil": "2026-07-30T12:00:00Z",
                            "evidenceRef": "official",
                            "authorityRefs": ["official"],
                            "membershipComplete": True,
                            "declaredMemberCount": 0,
                            "members": [],
                            "gaps": [],
                            "rawPayload": {
                                "sentinel": "must-never-reach-stdout",
                            },
                        }
                    ],
                },
            )
            staging = self._write_json(
                root,
                "staging.json",
                {
                    "schemaVersion": 1,
                    "seasonRevision": "season-r1",
                    "members": [],
                },
            )
            catalog = self._write_json(
                root,
                "catalog.json",
                {
                    "schemaVersion": 1,
                    "seasonRevision": "season-r1",
                    "catalogRevision": "",
                    "members": [],
                },
            )
            output = root / "blocked-report.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--policy",
                    str(policy),
                    "--discovery",
                    str(discovery),
                    "--staging",
                    str(staging),
                    "--catalog",
                    str(catalog),
                    "--max-ledger-rows",
                    "1",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            persisted_output = json.loads(
                output.read_text(encoding="utf-8")
            )

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["diagnostics"]["ledgerRowsEmitted"], 1)
        self.assertTrue(payload["diagnostics"]["truncated"])
        self.assertNotIn("must-never-reach-stdout", completed.stdout)
        self.assertEqual(persisted_output, payload)

    def test_verified_report_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            member = {
                "sourceKey": "crafted:one",
                "instanceId": "profession",
                "encounterId": "recipe-1",
                "difficultyKey": "quality-1",
                "itemId": "1001",
                "progressionState": {
                    "kind": "crafted",
                    "trackKey": "crafted",
                    "rankMax": 6,
                },
                "evidenceRef": "official:item:1001",
            }
            source_row = {
                "sourceKey": "crafted:one",
                "sourceType": "crafted",
                "required": True,
                "membershipMode": "recipe",
                "authorityRefs": ["official"],
                "effectiveWindow": {
                    "startsAt": "2026-07-01T00:00:00Z",
                    "endsAt": "2026-08-31T23:59:59Z",
                },
            }
            policy = self._write_json(
                root,
                "policy.json",
                {
                    "schemaVersion": 1,
                    "seasonRevision": "season-r1",
                    "sourcePolicyRevision": "policy-r1",
                    "status": "approved",
                    "sources": [source_row],
                },
            )
            discovery = self._write_json(
                root,
                "discovery.json",
                {
                    "schemaVersion": 1,
                    "seasonRevision": "season-r1",
                    "sourcePolicyRevision": "policy-r1",
                    "asOf": "2026-07-29T13:00:00Z",
                    "sources": [
                        {
                            "sourceKey": "crafted:one",
                            "status": "verified",
                            "capturedAt": "2026-07-29T12:00:00Z",
                            "validUntil": "2026-07-30T12:00:00Z",
                            "evidenceRef": "official",
                            "authorityRefs": ["official"],
                            "membershipComplete": True,
                            "declaredMemberCount": 1,
                            "members": [member],
                            "gaps": [],
                        }
                    ],
                },
            )
            empty = {
                "schemaVersion": 1,
                "seasonRevision": "season-r1",
                "members": [
                    {
                        **member,
                        "status": "verified",
                        "sourceId": "staging:item:1001",
                    }
                ],
            }
            staging = self._write_json(root, "staging.json", empty)
            catalog = self._write_json(
                root,
                "catalog.json",
                {
                    **empty,
                    "catalogRevision": "gear-catalog:sha256:" + ("a" * 64),
                    "members": [
                        {
                            **member,
                            "status": "verified",
                            "browseVariantKeys": [
                                "browse-variant:sha256:" + ("b" * 64),
                            ],
                        }
                    ],
                },
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--policy",
                    str(policy),
                    "--discovery",
                    str(discovery),
                    "--staging",
                    str(staging),
                    "--catalog",
                    str(catalog),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["status"], "verified")


if __name__ == "__main__":
    unittest.main()

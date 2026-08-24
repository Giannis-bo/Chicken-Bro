import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "build-s2-official-api-fact-snapshot.py"
PRODUCT_SCOPE = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "s2-product-content-scope-v1.json"
)
FACT_SCOPE = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "official-fact-scope-v1.json"
)


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def request_key_fixture():
    from server.s2_official_api_fact_snapshot import request_key

    path = "/data/wow/journal/instance/index"
    query = {"namespace": "static-12.1.0_68914-us", "locale": "en_US"}
    namespace = "static-12.1.0_68914-us"
    return {
        "schemaRevision": "s2-official-api-capture-manifest-v1",
        "seasonKey": "midnight-season-2",
        "status": "captured",
        "region": "us",
        "locale": "en_US",
        "namespace": namespace,
        "entries": [
            {
                "requestKey": request_key(
                    path,
                    query,
                    namespace=namespace,
                    region="us",
                    locale="en_US",
                ),
                "path": path,
                "query": query,
                "namespace": namespace,
                "region": "us",
                "locale": "en_US",
                "responsePath": "raw/0001.json",
                "responseSha256": "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881",
                "responseBytes": 1,
                "capturedAt": "2026-08-17T10:00:00Z",
                "pagination": {"page": 1, "pageCount": 1, "complete": True},
                "paginationParentRequestKey": None,
            }
        ],
    }


def normalized_facts(*, partial=False):
    result = {
        "scopeCounts": {
            "candidate": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 0},
            "admitted": {"raid": 1, "mythic_plus": 0, "crafted": 0, "tier_set": 0},
        },
        "sourceFacts": [
            {
                "logicalSource": "raid",
                "rawSourceType": "raid",
                "rawSourceKey": "raid:venomous-abyss",
                "status": "verified",
                "officialEvidenceRefs": ["official:journal:1320"],
            }
        ],
        "itemFacts": [],
        "exclusionLedger": [],
        "unresolvedFacts": [],
    }
    if partial:
        result["scopeCounts"]["admitted"]["raid"] = 0
        result["unresolvedFacts"].append(
            {
                "subjectKey": "source:raid:venomous-abyss",
                "field": "terminalTrack",
                "status": "UNVERIFIED",
                "reasonCode": "OFFICIAL_API_FIELD_MISSING",
                "officialEvidenceRefs": ["official:journal:1320"],
            }
        )
    return result


def prepare_capture(capture_root: Path, *, partial=False):
    raw_root = capture_root / "raw"
    raw_root.mkdir(parents=True)
    (raw_root / "0001.json").write_bytes(b"x")
    write_json(capture_root / "capture-manifest.json", request_key_fixture())
    write_json(capture_root / "normalized-facts.json", normalized_facts(partial=partial))


class S2OfficialApiFactSnapshotCliTest(unittest.TestCase):
    def run_cli(self, capture_root: Path, output: Path, *extra):
        return subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--scope",
                str(PRODUCT_SCOPE),
                "--fact-scope",
                str(FACT_SCOPE),
                "--capture-root",
                str(capture_root),
                "--output",
                str(output),
                *extra,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_builds_verified_fixture_snapshot_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            capture_root.mkdir()
            prepare_capture(capture_root)
            output = Path(directory) / "snapshot.json"

            result = self.run_cli(capture_root, output)

            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["status"], "verified")
            self.assertIsNone(snapshot["counts"]["publicSimcReadyRate"])
            self.assertIn("officialApiFactSnapshotRevision", snapshot)
            self.assertNotIn("simc", result.stdout.casefold())

    def test_cli_writes_partial_snapshot_but_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            capture_root.mkdir()
            prepare_capture(capture_root, partial=True)
            output = Path(directory) / "snapshot.json"

            result = self.run_cli(capture_root, output)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(output.exists())
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["status"],
                "partial",
            )

    def test_cli_has_no_live_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            capture_root.mkdir()
            output = Path(directory) / "snapshot.json"
            result = self.run_cli(capture_root, output, "--live")

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_cli_rejects_non_official_fact_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            capture_root = Path(directory) / "capture"
            capture_root.mkdir()
            prepare_capture(capture_root)
            facts = normalized_facts()
            facts["simcRuntime"] = {"build": "12.1.0"}
            write_json(capture_root / "normalized-facts.json", facts)
            output = Path(directory) / "snapshot.json"

            result = self.run_cli(capture_root, output)

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertIn("non-official", result.stderr)


if __name__ == "__main__":
    unittest.main()

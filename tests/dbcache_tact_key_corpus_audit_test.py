import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / (
    "audit-dbcache-tact-key-corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_dbcache_tact_key_corpus",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def cache_payload(records):
    payload = struct.pack(
        "<4sII32s",
        b"XFTH",
        10,
        68887,
        b"v" * 32,
    )
    index = 0
    for table_hash, record_id, value in records:
        index += 1
        payload += struct.pack(
            "<4siiIIIIB3s",
            b"XFTH",
            1,
            index,
            index,
            table_hash,
            record_id,
            len(value),
            1,
            b"\x00\x00\x00",
        )
        payload += value
    return payload


class DBCacheTactKeyCorpusTest(unittest.TestCase):
    def test_corpus_union_is_complete_without_persisting_key_material(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            static_path = root / "static.json"
            static_path.write_text(
                json.dumps(
                    {
                        "build": "12.0.7.68887",
                        "coverage": {
                            "targetKeys": [
                                {
                                    "tactKeyId": "14f4b11d7b067aa2",
                                    "recordCount": 12,
                                    "tables": ["ItemModifiedAppearance"],
                                },
                                {
                                    "tactKeyId": "fbbf041f980ce0dc",
                                    "recordCount": 44,
                                    "tables": ["ItemModifiedAppearance"],
                                },
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            url_a = (
                "https://storage.googleapis.com/"
                "raidbots-dbcache-temp/a.bin"
            )
            url_b = (
                "https://storage.googleapis.com/"
                "raidbots-dbcache-temp/b.bin"
            )
            list_payload = json.dumps(
                {
                    "data": [
                        {
                            "version": "retail",
                            "build": 68887,
                            "verified": False,
                            "url": url_a,
                            "entries": 2,
                            "pushIds": 1,
                            "created": "2026-07-31T00:00:00Z",
                        },
                        {
                            "version": "retail",
                            "build": 68887,
                            "verified": False,
                            "url": url_b,
                            "entries": 2,
                            "pushIds": 1,
                            "created": "2026-07-31T00:00:01Z",
                        },
                    ]
                }
            ).encode()
            payloads = {
                url_a: cache_payload(
                    [
                        (
                            MODULE.DB_CACHE_AUDIT.TACT_KEY_LOOKUP_TABLE_HASH,
                            1,
                            bytes.fromhex("a27a067b1db1f414"),
                        ),
                        (
                            MODULE.DB_CACHE_AUDIT.TACT_KEY_TABLE_HASH,
                            1,
                            bytes.fromhex("11" * 16),
                        ),
                    ]
                ),
                url_b: cache_payload(
                    [
                        (
                            MODULE.DB_CACHE_AUDIT.BROADCAST_TEXT_TABLE_HASH,
                            2,
                            (
                                b"text\x00"
                                + b"text1\x00"
                                + bytes(43)
                                + struct.pack(
                                    "<I",
                                    MODULE.DB_CACHE_AUDIT.TACT_KEY_TABLE_HASH,
                                )
                                + struct.pack(
                                    "<Q",
                                    int("dce00c981f04bffb", 16),
                                )
                                + bytes.fromhex("22" * 16)
                            ),
                        ),
                    ]
                ),
            }

            audit = MODULE.build_corpus_audit(
                list_payload=list_payload,
                list_url="https://www.raidbots.com/api/dbcache/unverified",
                list_output_path=root / "dbcache-68887-unverified-list.json",
                static_coverage_audit_path=static_path,
                expected_build=68887,
                expected_version="retail",
                expected_verified=False,
                max_files=100,
                cache_fetcher=lambda url, _max_bytes: payloads[url],
            )

            self.assertEqual(audit["status"], "complete")
            self.assertEqual(
                audit["corpus"]["summary"][
                    "unionAvailableTargetKeyCount"
                ],
                2,
            )
            serialized = json.dumps(audit)
            self.assertNotIn("11" * 16, serialized)
            self.assertNotIn("22" * 16, serialized)
            self.assertEqual(
                audit["corpus"]["summary"][
                    "broadcastTextTactKeyEntryCount"
                ],
                1,
            )
            self.assertFalse(
                audit["authority"]["auditContainsKeyMaterial"]
            )
            self.assertEqual(
                audit["sourceList"]["path"],
                "dbcache-68887-unverified-list.json",
            )

    def test_total_byte_budget_stops_later_cache_fetches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            static_path = root / "static.json"
            static_path.write_text(
                json.dumps(
                    {
                        "build": "12.0.7.68887",
                        "coverage": {
                            "targetKeys": [
                                {
                                    "tactKeyId": "14f4b11d7b067aa2",
                                    "recordCount": 12,
                                    "tables": ["ItemModifiedAppearance"],
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            urls = [
                "https://storage.googleapis.com/raidbots-dbcache-temp/a.bin",
                "https://storage.googleapis.com/raidbots-dbcache-temp/b.bin",
            ]
            list_payload = json.dumps(
                {
                    "data": [
                        {
                            "version": "retail",
                            "build": 68887,
                            "verified": False,
                            "url": url,
                        }
                        for url in urls
                    ]
                }
            ).encode()
            payload = cache_payload(
                [
                    (
                        MODULE.DB_CACHE_AUDIT.TACT_KEY_LOOKUP_TABLE_HASH,
                        1,
                        bytes.fromhex("a27a067b1db1f414"),
                    ),
                    (
                        MODULE.DB_CACHE_AUDIT.TACT_KEY_TABLE_HASH,
                        1,
                        bytes.fromhex("11" * 16),
                    ),
                ]
            )
            fetched = []

            def fetch(url, _max_bytes):
                fetched.append(url)
                return payload

            audit = MODULE.build_corpus_audit(
                list_payload=list_payload,
                list_url="https://www.raidbots.com/api/dbcache/unverified",
                list_output_path=root / "dbcache-list.json",
                static_coverage_audit_path=static_path,
                expected_build=68887,
                expected_version="retail",
                expected_verified=False,
                max_files=100,
                max_total_cache_bytes=len(payload),
                cache_fetcher=fetch,
            )

            self.assertEqual(fetched, [urls[0]])
            self.assertEqual(audit["status"], "partial")
            self.assertIn(
                "DBCACHE_CORPUS_RESOURCE_BUDGET_EXCEEDED",
                audit["corpus"]["blockers"],
            )
            self.assertEqual(
                audit["corpus"]["summary"]["totalFetchByteLimit"],
                len(payload),
            )


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / (
    "build-dbcache-tact-key-coverage-audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_dbcache_tact_key_coverage_audit",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DBCacheTactKeyCoverageAuditTest(unittest.TestCase):
    def test_lightweight_xfth_scan_finds_only_joined_enabled_target_key(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )

        def entry(index, table_hash, record_id, payload, state=1):
            return struct.pack(
                "<4siiIIIIB3s",
                b"XFTH",
                1,
                index,
                index,
                table_hash,
                record_id,
                len(payload),
                state,
                b"\x00\x00\x00",
            ) + payload

        payload = (
            header
            + entry(
                1,
                MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
                9001,
                bytes.fromhex("a27a067b1db1f414"),
            )
            + entry(
                2,
                MODULE.TACT_KEY_TABLE_HASH,
                9001,
                bytes.fromhex("11" * 16),
            )
            + entry(
                3,
                MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
                9002,
                bytes.fromhex("dce00c981f04bffb"),
            )
            + entry(
                4,
                MODULE.TACT_KEY_TABLE_HASH,
                9002,
                b"",
                state=2,
            )
        )

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={
                "a27a067b1db1f414",
                "dce00c981f04bffb",
            },
        )

        self.assertEqual(
            scan["presentTargetBlteKeyIds"],
            ["a27a067b1db1f414"],
        )
        self.assertEqual(scan["targetTableEntryCount"], 4)
        self.assertNotIn("11" * 16, json.dumps(scan))

    def test_lightweight_scan_applies_hotfix_lookup_to_base_key_material(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        lookup_payload = bytes.fromhex("a27a067b1db1f414")
        payload = header + struct.pack(
            "<4siiIIIIB3s",
            b"XFTH",
            1,
            1,
            1,
            MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
            9001,
            len(lookup_payload),
            1,
            b"\x00\x00\x00",
        ) + lookup_payload

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={"a27a067b1db1f414"},
            base_key_material_record_ids={9001},
            base_lookup_by_record_id={},
        )

        self.assertEqual(
            scan["presentTargetBlteKeyIds"],
            ["a27a067b1db1f414"],
        )

    def test_lightweight_scan_finds_broadcast_text_optional_tact_key(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        target_key_id = "a27a067b1db1f414"
        key_material = bytes.fromhex("33" * 16)
        broadcast_payload = (
            b"first text\x00"
            + b"second text\x00"
            + bytes(43)
            + struct.pack("<I", MODULE.TACT_KEY_TABLE_HASH)
            + struct.pack("<Q", int(target_key_id, 16))
            + key_material
        )
        payload = header + struct.pack(
            "<4siiIIIIB3s",
            b"XFTH",
            1,
            1,
            1,
            MODULE.BROADCAST_TEXT_TABLE_HASH,
            9001,
            len(broadcast_payload),
            1,
            b"\x00\x00\x00",
        ) + broadcast_payload

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={target_key_id},
        )

        self.assertEqual(
            scan["presentTargetBlteKeyIds"],
            [target_key_id],
        )
        self.assertEqual(scan["broadcastTextEntryCount"], 1)
        self.assertEqual(scan["broadcastTextTactKeyEntryCount"], 1)
        self.assertNotIn(key_material.hex(), json.dumps(scan))

    def test_partial_coverage_is_redacted_and_byte_order_mapped(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_path = root / "DBCache.bin"
            cache_path.write_bytes(
                struct.pack("<4sII32s", b"XFTH", 10, 68887, b"v" * 32)
                + b"payload"
            )
            generated_path = root / "tact-keys.json"
            generated_path.write_text(
                json.dumps(
                    [
                        {
                            "id": 1,
                            "key_id": "a27a067b1db1f414",
                            "key": "11" * 16,
                        },
                        {
                            "id": 2,
                            "key_id": "dce00c981f04bffb",
                            "key": None,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            static_audit_path = root / "static-audit.json"
            static_audit_path.write_text(
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

            audit = MODULE.build_audit(
                cache_path=cache_path,
                generated_key_path=generated_path,
                static_coverage_audit_path=static_audit_path,
                expected_build=68887,
                source_url="https://example.invalid/DBCache.bin",
                source_etag="etag",
                source_generation="generation",
                source_last_modified="timestamp",
            )

            self.assertEqual(audit["status"], "partial")
            self.assertEqual(
                audit["coverage"]["summary"]["availableTargetKeyCount"],
                1,
            )
            self.assertEqual(
                audit["coverage"]["summary"]["coveredTargetRecordCount"],
                12,
            )
            self.assertEqual(
                audit["coverage"]["targetKeys"][0]["blteKeyId"],
                "a27a067b1db1f414",
            )
            self.assertTrue(
                audit["coverage"]["targetKeys"][0][
                    "presentInVerifiedDBCache"
                ]
            )
            self.assertFalse(
                audit["coverage"]["targetKeys"][1][
                    "presentInVerifiedDBCache"
                ]
            )
            self.assertNotIn("11" * 16, json.dumps(audit))
            self.assertFalse(
                audit["authority"]["auditContainsKeyMaterial"]
            )

    def test_build_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cache_path = root / "DBCache.bin"
            cache_path.write_bytes(
                struct.pack("<4sII32s", b"XFTH", 10, 68886, b"v" * 32)
            )
            generated_path = root / "tact-keys.json"
            generated_path.write_text("[]", encoding="utf-8")
            static_audit_path = root / "static-audit.json"
            static_audit_path.write_text(
                json.dumps(
                    {
                        "build": "12.0.7.68887",
                        "coverage": {"targetKeys": []},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "build"):
                MODULE.build_audit(
                    cache_path=cache_path,
                    generated_key_path=generated_path,
                    static_coverage_audit_path=static_audit_path,
                    expected_build=68887,
                    source_url="https://example.invalid/DBCache.bin",
                    source_etag="etag",
                    source_generation="generation",
                    source_last_modified="timestamp",
                )


if __name__ == "__main__":
    unittest.main()

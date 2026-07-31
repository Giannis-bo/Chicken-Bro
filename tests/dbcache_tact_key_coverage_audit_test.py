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


def xfth_entry(index, table_hash, record_id, payload, state=1):
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


def broadcast_text_payload(blte_key_id, material_byte):
    return (
        b"first text\x00"
        + b"second text\x00"
        + bytes(43)
        + struct.pack("<I", MODULE.TACT_KEY_TABLE_HASH)
        + bytes.fromhex(blte_key_id)
        + bytes.fromhex(material_byte * 16)
    )


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
            + bytes.fromhex(target_key_id)
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

    def test_broadcast_text_identity_is_normalized_to_blte_raw_byte_order(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        tact_key_id = "14f4b11d7b067aa2"
        blte_key_id = bytes.fromhex(tact_key_id)[::-1].hex()
        self.assertEqual(
            struct.pack("<Q", int(tact_key_id, 16)),
            bytes.fromhex(blte_key_id),
        )
        payload = header + xfth_entry(
            1,
            MODULE.BROADCAST_TEXT_TABLE_HASH,
            9001,
            broadcast_text_payload(blte_key_id, "34"),
        )

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={blte_key_id},
        )

        self.assertEqual(scan["presentTargetBlteKeyIds"], [blte_key_id])

    def test_broadcast_text_replacements_keep_only_effective_record_material(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        removed_without_key = "a27a067b1db1f414"
        replaced_old_key = "dce00c981f04bffb"
        replacement_key = "0123456789abcdef"
        old_material = "41"
        replacement_material = "42"
        payload = (
            header
            + xfth_entry(
                1,
                MODULE.BROADCAST_TEXT_TABLE_HASH,
                9001,
                broadcast_text_payload(removed_without_key, old_material),
            )
            + xfth_entry(
                2,
                MODULE.BROADCAST_TEXT_TABLE_HASH,
                9001,
                b"replacement without optional TactKey data",
            )
            + xfth_entry(
                3,
                MODULE.BROADCAST_TEXT_TABLE_HASH,
                9002,
                broadcast_text_payload(replaced_old_key, "43"),
            )
            + xfth_entry(
                4,
                MODULE.BROADCAST_TEXT_TABLE_HASH,
                9002,
                broadcast_text_payload(replacement_key, replacement_material),
            )
        )

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={
                removed_without_key,
                replaced_old_key,
                replacement_key,
            },
        )

        self.assertEqual(
            scan["presentTargetBlteKeyIds"],
            sorted(
                {
                    removed_without_key,
                    replaced_old_key,
                    replacement_key,
                }
            ),
        )
        self.assertEqual(
            scan["effectivePresentTargetBlteKeyIds"],
            [replacement_key],
        )
        self.assertEqual(
            scan["recoverableTargetBlteKeyIds"],
            sorted(
                {
                    removed_without_key,
                    replaced_old_key,
                    replacement_key,
                }
            ),
        )
        self.assertEqual(scan["broadcastTextTactKeyEntryCount"], 3)
        self.assertEqual(
            scan["broadcastTextEffectiveTactKeyRecordCount"],
            1,
        )
        self.assertEqual(scan["broadcastTextCarriedMaterialKeyCount"], 1)
        self.assertEqual(
            scan["broadcastTextObservedCarriedMaterialKeyCount"],
            3,
        )
        serialized = json.dumps(scan)
        self.assertNotIn(old_material * 16, serialized)
        self.assertNotIn(replacement_material * 16, serialized)

    def test_non_enabled_states_revoke_prior_records_and_report_ledger(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        tact_key_target = "a27a067b1db1f414"
        lookup_target = "dce00c981f04bffb"
        broadcast_target = "0123456789abcdef"
        material = "51"
        unknown_table_hash = 0x12345678
        payload = (
            header
            + xfth_entry(
                1,
                MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
                9101,
                bytes.fromhex(tact_key_target),
            )
            + xfth_entry(
                2,
                MODULE.TACT_KEY_TABLE_HASH,
                9101,
                bytes.fromhex(material * 16),
            )
            + xfth_entry(
                3,
                MODULE.TACT_KEY_TABLE_HASH,
                9101,
                b"",
                state=2,
            )
            + xfth_entry(
                4,
                MODULE.TACT_KEY_TABLE_HASH,
                9102,
                bytes.fromhex("52" * 16),
            )
            + xfth_entry(
                5,
                MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
                9102,
                bytes.fromhex(lookup_target),
            )
            + xfth_entry(
                6,
                MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
                9102,
                b"",
                state=3,
            )
            + xfth_entry(
                7,
                MODULE.BROADCAST_TEXT_TABLE_HASH,
                9103,
                broadcast_text_payload(broadcast_target, "53"),
            )
            + xfth_entry(
                8,
                MODULE.BROADCAST_TEXT_TABLE_HASH,
                9103,
                b"",
                state=4,
            )
            + xfth_entry(
                9,
                unknown_table_hash,
                9104,
                bytes.fromhex("54" * 16),
                state=9,
            )
        )

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={
                tact_key_target,
                lookup_target,
                broadcast_target,
            },
        )

        self.assertEqual(
            scan["presentTargetBlteKeyIds"],
            sorted({tact_key_target, lookup_target, broadcast_target}),
        )
        self.assertEqual(scan["effectivePresentTargetBlteKeyIds"], [])
        self.assertEqual(
            scan["recoverableTargetBlteKeyIds"],
            sorted({tact_key_target, lookup_target, broadcast_target}),
        )
        self.assertEqual(scan["observedJoinedMaterialKeyCount"], 2)
        self.assertEqual(
            scan["broadcastTextObservedCarriedMaterialKeyCount"],
            1,
        )
        self.assertEqual(scan["parsedEntryCount"], 9)
        self.assertEqual(scan["unrecognizedTableEntryCount"], 1)
        self.assertEqual(
            scan["recordStateCounts"],
            {"1": 5, "2": 1, "3": 1, "4": 1, "9": 1},
        )
        self.assertEqual(
            scan["recognizedTableRecordStateCounts"],
            {
                "BroadcastText": {"1": 1, "4": 1},
                "TactKey": {"1": 2, "2": 1},
                "TactKeyLookup": {"1": 2, "3": 1},
            },
        )
        self.assertEqual(scan["unmodeledRecordStateCount"], 1)
        serialized = json.dumps(scan)
        self.assertNotIn(material * 16, serialized)
        self.assertNotIn("52" * 16, serialized)
        self.assertNotIn("53" * 16, serialized)
        self.assertNotIn("54" * 16, serialized)

    def test_recovery_requires_material_and_lookup_to_coexist(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        target = "a27a067b1db1f414"
        payload = (
            header
            + xfth_entry(
                1,
                MODULE.TACT_KEY_TABLE_HASH,
                9201,
                b"",
                state=2,
            )
            + xfth_entry(
                2,
                MODULE.TACT_KEY_LOOKUP_TABLE_HASH,
                9201,
                bytes.fromhex(target),
            )
        )

        scan = MODULE.scan_xfth_target_keys(
            payload,
            expected_build=68887,
            target_blte_key_ids={target},
            base_key_material_record_ids={9201},
        )

        self.assertEqual(scan["effectivePresentTargetBlteKeyIds"], [])
        self.assertEqual(scan["recoverableTargetBlteKeyIds"], [])
        self.assertEqual(scan["observedJoinedMaterialKeyCount"], 0)

    def test_unmodeled_state_in_key_carrier_table_fails_closed(self):
        header = struct.pack(
            "<4sII32s",
            b"XFTH",
            10,
            68887,
            b"v" * 32,
        )
        payload = header + xfth_entry(
            1,
            MODULE.TACT_KEY_TABLE_HASH,
            9301,
            bytes.fromhex("61" * 16),
            state=9,
        )

        with self.assertRaisesRegex(ValueError, "unmodeled record state"):
            MODULE.scan_xfth_target_keys(
                payload,
                expected_build=68887,
                target_blte_key_ids={"a27a067b1db1f414"},
            )

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

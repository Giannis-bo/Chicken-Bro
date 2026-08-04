#!/usr/bin/env python3
"""Behavior contract for the canonical gear kernel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from server.gear_canonical_kernel import (
    CanonicalValueError,
    SealedCanonicalDocument,
    canonical_identity_token,
    canonical_int,
    canonical_json_bytes,
    canonical_mapping,
    canonical_ordered_list,
    canonical_report_token,
    canonical_set_list,
    canonical_slot,
    seal_canonical_document,
    verified_payload_copy,
    verify_sealed_document,
)


MUTATIONS = json.loads(
    (Path(__file__).parent / "fixtures" / "gear_canonical_mutations.json").read_text(encoding="utf-8")
)


def identity_rule(value: object, path: str) -> str:
    return canonical_identity_token(value, path=path)


def validate_fixture_payload(value: object) -> object:
    if not isinstance(value, dict):
        raise CanonicalValueError("PAYLOAD_NOT_OBJECT", "payload")
    if value.get("schemaRevision") != "fixture-v1" or value.get("value") != "ok":
        raise CanonicalValueError("INVALID_FIXTURE", "payload")
    return value


class GearCanonicalKernelTest(unittest.TestCase):
    def test_rejects_ascii_and_unicode_controls_without_normalizing(self):
        for value in MUTATIONS["invalidIdentityStrings"]:
            with self.subTest(value=ascii(value)):
                with self.assertRaises(CanonicalValueError):
                    canonical_identity_token(value, path="exact.context")

    def test_identity_and_report_tokens_accept_only_their_explicit_canonical_forms(self):
        self.assertEqual(canonical_identity_token("exact-item.v2", path="exact.kind"), "exact-item.v2")
        self.assertEqual(canonical_report_token("Imported item #1", path="report.title"), "Imported item #1")
        with self.assertRaises(CanonicalValueError):
            canonical_identity_token("名字", path="exact.kind")
        with self.assertRaises(CanonicalValueError):
            canonical_report_token("report\tvalue", path="report.title")

    def test_slot_uses_the_single_canonical_slot_set(self):
        self.assertEqual(canonical_slot("head", path="slot"), "head")
        for value in MUTATIONS["invalidSlots"]:
            with self.subTest(value=ascii(value)):
                with self.assertRaises(CanonicalValueError):
                    canonical_slot(value, path="slot")

    def test_integer_requires_exact_integer_type_and_bounds(self):
        self.assertEqual(canonical_int(42, path="exact.itemLevel", minimum=1, maximum=9999), 42)
        for value in MUTATIONS["invalidIntegers"]:
            with self.subTest(value=repr(value)):
                with self.assertRaises(CanonicalValueError):
                    canonical_int(value, path="exact.itemLevel", minimum=1, maximum=9999)

    def test_ordered_list_preserves_valid_input_order_without_coercion(self):
        self.assertEqual(
            canonical_ordered_list(["haste", "crit"], path="gemIds", item_rule=identity_rule, max_items=8),
            ("haste", "crit"),
        )
        with self.assertRaises(CanonicalValueError):
            canonical_ordered_list(("haste", "crit"), path="gemIds", item_rule=identity_rule, max_items=8)

    def test_set_list_requires_already_sorted_unique_input(self):
        self.assertEqual(
            canonical_set_list(["crit", "haste"], path="craftedStats", item_rule=identity_rule, max_items=8),
            ("crit", "haste"),
        )
        for value in MUTATIONS["invalidSetLists"]:
            with self.subTest(value=value):
                with self.assertRaises(CanonicalValueError):
                    canonical_set_list(value, path="craftedStats", item_rule=identity_rule, max_items=8)

    def test_mapping_requires_the_exact_contract_key_set(self):
        value = {"itemId": "1", "slot": "head"}
        self.assertEqual(
            canonical_mapping(value, path="exact", exact_keys=frozenset({"itemId", "slot"})),
            value,
        )
        with self.assertRaises(CanonicalValueError):
            canonical_mapping({"itemId": "1"}, path="exact", exact_keys=frozenset({"itemId", "slot"}))
        with self.assertRaises(CanonicalValueError):
            canonical_mapping(
                {"itemId": "1", "slot": "head", "extra": "no"},
                path="exact",
                exact_keys=frozenset({"itemId", "slot"}),
            )

    def test_canonical_json_is_deterministic_and_refuses_non_json_values(self):
        self.assertEqual(canonical_json_bytes({"b": 2, "a": "项"}), b'{"a":"\xe9\xa1\xb9","b":2}')
        with self.assertRaises((TypeError, ValueError)):
            canonical_json_bytes({"nan": float("nan")})
        with self.assertRaises(TypeError):
            canonical_json_bytes({"object": object()})

    def test_sealed_document_cannot_be_forged_or_mutated(self):
        document = seal_canonical_document(
            document_kind="fixture", schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"}, key_prefix="fixture:sha256:",
        )
        self.assertFalse(hasattr(document, "__dict__"))
        with self.assertRaises(TypeError):
            SealedCanonicalDocument("fixture", "fixture-v1", b"{}", "fixture:sha256:" + "0" * 64)
        with self.assertRaises(AttributeError):
            document.content_key = "fixture:sha256:" + "0" * 64

    def test_seal_reload_verification_rejects_byte_or_key_tampering(self):
        document = seal_canonical_document(
            document_kind="fixture", schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"}, key_prefix="fixture:sha256:",
        )
        self.assertTrue(
            verify_sealed_document(
                document,
                document_kind="fixture",
                schema_revision="fixture-v1",
                key_prefix="fixture:sha256:",
                payload_validator=validate_fixture_payload,
            )
        )
        self.assertEqual(
            verified_payload_copy(
                document,
                document_kind="fixture",
                schema_revision="fixture-v1",
                payload_validator=validate_fixture_payload,
            ),
            {"schemaRevision": "fixture-v1", "value": "ok"},
        )
        tampered_bytes = object.__new__(SealedCanonicalDocument)
        object.__setattr__(tampered_bytes, "document_kind", "fixture")
        object.__setattr__(tampered_bytes, "schema_revision", "fixture-v1")
        object.__setattr__(tampered_bytes, "canonical_bytes", b'{"schemaRevision":"fixture-v1","value":"changed"}')
        object.__setattr__(tampered_bytes, "content_key", document.content_key)
        self.assertFalse(
            verify_sealed_document(
                tampered_bytes,
                document_kind="fixture",
                schema_revision="fixture-v1",
                key_prefix="fixture:sha256:",
                payload_validator=validate_fixture_payload,
            )
        )
        self.assertNotEqual(
            document.content_key,
            "fixture:sha256:" + hashlib.sha256(tampered_bytes.canonical_bytes).hexdigest(),
        )

    def test_verified_copy_rechecks_a_prefix_that_does_not_contain_sha256_text(self):
        document = seal_canonical_document(
            document_kind="fixture", schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"}, key_prefix="fixture:key:",
        )
        self.assertEqual(
            verified_payload_copy(
                document,
                document_kind="fixture",
                schema_revision="fixture-v1",
                payload_validator=validate_fixture_payload,
            ),
            {"schemaRevision": "fixture-v1", "value": "ok"},
        )


if __name__ == "__main__":
    unittest.main()

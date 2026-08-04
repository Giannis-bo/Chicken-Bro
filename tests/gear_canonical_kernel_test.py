#!/usr/bin/env python3
"""Behavior contract for the canonical gear kernel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from server.gear_canonical_kernel import (
    CanonicalIssue,
    CanonicalResult,
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


def forged_document(canonical_bytes: bytes) -> SealedCanonicalDocument:
    document = object.__new__(SealedCanonicalDocument)
    object.__setattr__(document, "document_kind", "fixture")
    object.__setattr__(document, "schema_revision", "fixture-v1")
    object.__setattr__(document, "canonical_bytes", canonical_bytes)
    object.__setattr__(
        document,
        "content_key",
        "fixture:sha256:" + hashlib.sha256(canonical_bytes).hexdigest(),
    )
    return document


def accept_payload(value: object) -> object:
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

    def test_identity_and_report_tokens_require_input_nfc_without_normalizing(self):
        decomposed = "cafe\u0301"
        self.assertNotEqual(decomposed, "caf\u00e9")
        for token_rule in (canonical_identity_token, canonical_report_token):
            with self.subTest(token_rule=token_rule.__name__):
                with self.assertRaises(CanonicalValueError) as caught:
                    token_rule(decomposed, path="token")
                self.assertEqual(caught.exception.code, "NON_CANONICAL_UNICODE")

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
        with self.assertRaises(CanonicalValueError):
            canonical_json_bytes({"object": object()})

    def test_canonical_json_bounds_depth_nodes_and_python_cycles(self):
        deeply_nested: object = "leaf"
        for _ in range(65):
            deeply_nested = [deeply_nested]
        cyclic: list[object] = []
        cyclic.append(cyclic)
        oversized_nodes = list(range(10_001))
        for value in (deeply_nested, cyclic, oversized_nodes):
            with self.subTest(kind=type(value).__name__):
                try:
                    canonical_json_bytes(value)
                except CanonicalValueError:
                    pass
                except RecursionError as error:
                    self.fail(f"canonical_json_bytes leaked RecursionError: {error}")
                else:
                    self.fail("hostile canonical JSON value was accepted")

    def test_canonical_json_rejects_non_string_mapping_keys_without_coercion(self):
        with self.assertRaises(CanonicalValueError):
            canonical_json_bytes({1: "integer"})
        with self.assertRaises(CanonicalValueError):
            canonical_json_bytes({"nested": {2: "integer"}})

    def test_distinct_raw_mapping_key_types_cannot_share_canonical_bytes(self):
        string_key_bytes = canonical_json_bytes({"1": "value"})
        with self.assertRaises(CanonicalValueError):
            canonical_json_bytes({1: "value"})
        self.assertEqual(string_key_bytes, b'{"1":"value"}')

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
                key_prefix="fixture:sha256:",
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

    def test_verifier_preflights_hostile_json_bytes_before_decode(self):
        deeply_nested = (
            b'{"value":' + (b"[" * 1500) + b'"ok"' + (b"]" * 1500) + b"}"
        )
        oversized_bytes = b'{"value":"' + (b"x" * (1024 * 1024)) + b'"}'
        oversized_nodes = json.dumps(
            {"values": list(range(10_001))},
            separators=(",", ":"),
        ).encode("utf-8")
        for canonical_bytes in (
            deeply_nested,
            oversized_bytes,
            oversized_nodes,
        ):
            with self.subTest(byte_count=len(canonical_bytes)):
                try:
                    verified = verify_sealed_document(
                        forged_document(canonical_bytes),
                        document_kind="fixture",
                        schema_revision="fixture-v1",
                        key_prefix="fixture:sha256:",
                        payload_validator=accept_payload,
                    )
                except RecursionError as error:
                    self.fail(f"verify_sealed_document leaked RecursionError: {error}")
                self.assertFalse(verified)

    def test_json_preflight_respects_escaped_string_structure_and_frozen_identity(self):
        document = seal_canonical_document(
            document_kind="fixture",
            schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"},
            key_prefix="fixture:sha256:",
        )
        self.assertEqual(
            document.canonical_bytes,
            b'{"schemaRevision":"fixture-v1","value":"ok"}',
        )
        self.assertEqual(
            document.content_key,
            "fixture:sha256:db8d902495512a48ce5b4ab582d5abe50d736288c7e631332d945cc89b2f80b4",
        )
        escaped_payload = {
            "text": "{[\\\"quoted\\\"]}",
        }
        escaped = seal_canonical_document(
            document_kind="fixture",
            schema_revision="fixture-v1",
            payload=escaped_payload,
            key_prefix="fixture:sha256:",
        )
        self.assertTrue(verify_sealed_document(
            escaped,
            document_kind="fixture",
            schema_revision="fixture-v1",
            key_prefix="fixture:sha256:",
            payload_validator=accept_payload,
        ))

    def test_verified_payload_copy_rejects_wrong_expected_key_prefix(self):
        document = seal_canonical_document(
            document_kind="fixture", schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"}, key_prefix="attacker:key:",
        )
        with self.assertRaises(CanonicalValueError):
            verified_payload_copy(
                document,
                document_kind="fixture",
                schema_revision="fixture-v1",
                key_prefix="fixture:sha256:",
                payload_validator=validate_fixture_payload,
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
                key_prefix="fixture:key:",
                payload_validator=validate_fixture_payload,
            ),
            {"schemaRevision": "fixture-v1", "value": "ok"},
        )

    def test_canonical_result_rejects_invalid_status_document_issue_combinations(self):
        document = seal_canonical_document(
            document_kind="fixture", schema_revision="fixture-v1",
            payload={"schemaRevision": "fixture-v1", "value": "ok"}, key_prefix="fixture:sha256:",
        )
        issue = CanonicalIssue("INVALID_FIXTURE", "payload", "re-import")
        self.assertEqual(CanonicalResult("verified", document, ()).status, "verified")
        self.assertEqual(CanonicalResult("blocked", None, (issue,)).status, "blocked")
        for status, result_document, issues in (
            ("verified", None, ()),
            ("verified", document, (issue,)),
            ("blocked", document, (issue,)),
            ("blocked", None, ()),
            ("blocked", None, (object(),)),
            ("unknown", None, ()),
        ):
            with self.subTest(status=status, document=result_document, issues=issues):
                with self.assertRaises(ValueError):
                    CanonicalResult(status, result_document, issues)


if __name__ == "__main__":
    unittest.main()

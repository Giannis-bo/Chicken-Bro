#!/usr/bin/env python3
"""Pure canonical primitives and sealed documents for equipment contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Literal, TypeVar
import unicodedata

from server.gear_contracts import CANONICAL_GEAR_SLOTS


T = TypeVar("T")
_IDENTITY_PATTERN = re.compile(r"(?:[A-Za-z0-9][A-Za-z0-9._:/-]*)?")
_REPORT_PATTERN = re.compile(r"(?:[ -~])*")
_SEAL_TOKEN = object()
_MAX_CANONICAL_JSON_BYTES = 1024 * 1024
_MAX_CANONICAL_JSON_DEPTH = 64
_MAX_CANONICAL_JSON_NODES = 10_000


class CanonicalValueError(ValueError):
    """A raw value cannot enter the canonical language."""

    def __init__(self, code: str, path: str):
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


@dataclass(frozen=True)
class CanonicalIssue:
    code: str
    path: str
    recovery_action: str


@dataclass(frozen=True, init=False, slots=True)
class SealedCanonicalDocument:
    document_kind: str
    schema_revision: str
    canonical_bytes: bytes
    content_key: str

    def __init__(
        self,
        seal_token: object,
        *,
        document_kind: str,
        schema_revision: str,
        canonical_bytes: bytes,
        content_key: str,
    ) -> None:
        if seal_token is not _SEAL_TOKEN:
            raise TypeError("SealedCanonicalDocument instances require the module-private seal token.")
        object.__setattr__(self, "document_kind", document_kind)
        object.__setattr__(self, "schema_revision", schema_revision)
        object.__setattr__(self, "canonical_bytes", canonical_bytes)
        object.__setattr__(self, "content_key", content_key)


@dataclass(frozen=True)
class CanonicalResult:
    status: Literal["verified", "blocked"]
    document: SealedCanonicalDocument | None
    issues: tuple[CanonicalIssue, ...]

    def __post_init__(self) -> None:
        if self.status == "verified":
            if type(self.document) is not SealedCanonicalDocument or type(self.issues) is not tuple or self.issues:
                raise ValueError("Verified canonical results require one sealed document and no issues.")
            return
        if self.status == "blocked":
            if (
                self.document is not None
                or type(self.issues) is not tuple
                or not self.issues
                or any(type(issue) is not CanonicalIssue for issue in self.issues)
            ):
                raise ValueError("Blocked canonical results require issues and no document.")
            return
        raise ValueError("Canonical result status must be verified or blocked.")


def _has_forbidden_codepoint(value: str) -> bool:
    return any(unicodedata.category(ch) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for ch in value)


def _bounded_utf8_bytes(value: str, *, path: str, max_bytes: int) -> bytes:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalValueError("INVALID_TEXT_ENCODING", path) from error
    if len(encoded) > max_bytes:
        raise CanonicalValueError("TEXT_BOUNDS", path)
    return encoded


def canonical_identity_token(
    value: object,
    *,
    path: str,
    allow_empty: bool = False,
    max_bytes: int = 256,
) -> str:
    if type(value) is not str or value != value.strip():
        raise CanonicalValueError("NON_CANONICAL_TEXT", path)
    if (not allow_empty and not value):
        raise CanonicalValueError("TEXT_BOUNDS", path)
    _bounded_utf8_bytes(value, path=path, max_bytes=max_bytes)
    if not unicodedata.is_normalized("NFC", value):
        raise CanonicalValueError("NON_CANONICAL_UNICODE", path)
    if _has_forbidden_codepoint(value) or _IDENTITY_PATTERN.fullmatch(value) is None:
        raise CanonicalValueError("INVALID_IDENTITY_TOKEN", path)
    return value


def canonical_report_token(
    value: object,
    *,
    path: str,
    allow_empty: bool = False,
    max_bytes: int = 256,
) -> str:
    if type(value) is not str or value != value.strip():
        raise CanonicalValueError("NON_CANONICAL_TEXT", path)
    if (not allow_empty and not value):
        raise CanonicalValueError("TEXT_BOUNDS", path)
    _bounded_utf8_bytes(value, path=path, max_bytes=max_bytes)
    if not unicodedata.is_normalized("NFC", value):
        raise CanonicalValueError("NON_CANONICAL_UNICODE", path)
    if _has_forbidden_codepoint(value) or _REPORT_PATTERN.fullmatch(value) is None:
        raise CanonicalValueError("INVALID_REPORT_TOKEN", path)
    return value


def canonical_slot(value: object, *, path: str) -> str:
    slot = canonical_identity_token(value, path=path)
    if slot not in CANONICAL_GEAR_SLOTS:
        raise CanonicalValueError("INVALID_SLOT", path)
    return slot


def canonical_int(value: object, *, path: str, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise CanonicalValueError("INVALID_INTEGER", path)
    if value < minimum or value > maximum:
        raise CanonicalValueError("INTEGER_BOUNDS", path)
    return value


def canonical_ordered_list(
    value: object,
    *,
    path: str,
    item_rule: Callable[[object, str], T],
    max_items: int,
) -> tuple[T, ...]:
    if type(value) is not list:
        raise CanonicalValueError("INVALID_ORDERED_LIST", path)
    if len(value) > max_items:
        raise CanonicalValueError("LIST_BOUNDS", path)
    return tuple(item_rule(item, f"{path}[{index}]") for index, item in enumerate(value))


def canonical_set_list(
    value: object,
    *,
    path: str,
    item_rule: Callable[[object, str], T],
    max_items: int,
) -> tuple[T, ...]:
    result = canonical_ordered_list(value, path=path, item_rule=item_rule, max_items=max_items)
    try:
        canonical = tuple(sorted(set(result)))
    except (TypeError, ValueError) as error:
        raise CanonicalValueError("INVALID_SET_LIST", path) from error
    if result != canonical:
        raise CanonicalValueError("NON_CANONICAL_SET_LIST", path)
    return result


def canonical_mapping(value: object, *, path: str, exact_keys: frozenset[str]) -> Mapping[str, object]:
    if type(value) is not dict:
        raise CanonicalValueError("INVALID_MAPPING", path)
    if set(value) != exact_keys:
        raise CanonicalValueError("MAPPING_KEY_SET_MISMATCH", path)
    return value


def canonical_json_bytes(value: object) -> bytes:
    _validate_canonical_json_value(value, path="$")
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (RecursionError, UnicodeError, ValueError) as error:
        raise CanonicalValueError("INVALID_CANONICAL_JSON_VALUE", "$") from error
    if len(encoded) > _MAX_CANONICAL_JSON_BYTES:
        raise CanonicalValueError("CANONICAL_JSON_BYTE_BOUNDS", "$")
    return encoded


def _validate_canonical_json_value(value: object, *, path: str) -> None:
    # One node is one object, array, object key, or scalar value. Depth is the
    # number of enclosing object/array containers; keys and scalars do not add
    # a level. The byte preflight below uses the same language.
    pending: list[tuple[bool, object, str, int]] = [(True, value, path, 0)]
    active_container_ids: set[int] = set()
    node_count = 0
    while pending:
        entering, current, current_path, container_depth = pending.pop()
        if not entering:
            active_container_ids.remove(id(current))
            continue
        node_count += 1
        if node_count > _MAX_CANONICAL_JSON_NODES:
            raise CanonicalValueError("CANONICAL_JSON_NODE_BOUNDS", current_path)
        if type(current) in {dict, list, tuple}:
            current_depth = container_depth + 1
            if current_depth > _MAX_CANONICAL_JSON_DEPTH:
                raise CanonicalValueError("CANONICAL_JSON_DEPTH_BOUNDS", current_path)
            identity = id(current)
            if identity in active_container_ids:
                raise CanonicalValueError("CANONICAL_JSON_CYCLE", current_path)
            active_container_ids.add(identity)
            pending.append((False, current, current_path, current_depth))
        if type(current) is dict:
            children: list[tuple[bool, object, str, int]] = []
            for key, nested_value in current.items():
                if type(key) is not str:
                    raise CanonicalValueError("NON_STRING_JSON_KEY", current_path)
                node_count += 1
                if node_count > _MAX_CANONICAL_JSON_NODES:
                    raise CanonicalValueError(
                        "CANONICAL_JSON_NODE_BOUNDS",
                        f"{current_path}.{key}",
                    )
                children.append((
                    True,
                    nested_value,
                    f"{current_path}.{key}",
                    current_depth,
                ))
            pending.extend(reversed(children))
            continue
        if type(current) is list or type(current) is tuple:
            pending.extend(
                (True, nested_value, f"{current_path}[{index}]", current_depth)
                for index, nested_value in reversed(tuple(enumerate(current)))
            )
            continue
        if current is None or type(current) in {str, int, float, bool}:
            continue
        raise CanonicalValueError("INVALID_CANONICAL_JSON_VALUE", current_path)


def _content_key(prefix: str, encoded: bytes) -> str:
    return prefix + hashlib.sha256(encoded).hexdigest()


def _seal_inputs(*, document_kind: str, schema_revision: str, key_prefix: str) -> None:
    canonical_identity_token(document_kind, path="documentKind")
    canonical_identity_token(schema_revision, path="schemaRevision")
    canonical_identity_token(key_prefix, path="keyPrefix")


def seal_canonical_document(
    *,
    document_kind: str,
    schema_revision: str,
    payload: Mapping[str, object],
    key_prefix: str,
) -> SealedCanonicalDocument:
    _seal_inputs(document_kind=document_kind, schema_revision=schema_revision, key_prefix=key_prefix)
    if type(payload) is not dict:
        raise CanonicalValueError("INVALID_PAYLOAD_MAPPING", "payload")
    encoded = canonical_json_bytes(payload)
    return SealedCanonicalDocument(
        _SEAL_TOKEN,
        document_kind=document_kind,
        schema_revision=schema_revision,
        canonical_bytes=encoded,
        content_key=_content_key(key_prefix, encoded),
    )


def _reject_duplicate_pairs(pairs: list[tuple[object, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            raise ValueError("JSON object keys must be unique strings.")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"Non-finite JSON value {value!r} is not canonical.")


def _preflight_canonical_json_bytes(canonical_bytes: bytes) -> str:
    # Strings count once whether they are object keys or scalar values; every
    # object/array opening and every plain scalar token also counts once.
    # Only object/array openings add structural depth.
    if len(canonical_bytes) > _MAX_CANONICAL_JSON_BYTES:
        raise CanonicalValueError("CANONICAL_JSON_BYTE_BOUNDS", "$")
    decoded = canonical_bytes.decode("utf-8")
    depth = 0
    node_count = 0
    in_string = False
    escaped = False
    in_plain_token = False
    for character in decoded:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            in_plain_token = False
            node_count += 1
        elif character in "[{":
            depth += 1
            in_plain_token = False
            node_count += 1
            if depth > _MAX_CANONICAL_JSON_DEPTH:
                raise CanonicalValueError("CANONICAL_JSON_DEPTH_BOUNDS", "$")
        elif character in "]}":
            depth -= 1
            in_plain_token = False
            if depth < 0:
                raise CanonicalValueError("INVALID_CANONICAL_JSON_VALUE", "$")
        elif character in " \t\r\n,:":
            in_plain_token = False
        elif not in_plain_token:
            in_plain_token = True
            node_count += 1
        if node_count > _MAX_CANONICAL_JSON_NODES:
            raise CanonicalValueError("CANONICAL_JSON_NODE_BOUNDS", "$")
    return decoded


def _strict_payload(canonical_bytes: object) -> dict[str, object]:
    if type(canonical_bytes) is not bytes:
        raise ValueError("Canonical document bytes must be bytes.")
    decoded = _preflight_canonical_json_bytes(canonical_bytes)
    value = json.loads(
        decoded,
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_json_constant,
    )
    _validate_canonical_json_value(value, path="$")
    if type(value) is not dict:
        raise ValueError("Canonical document payload must be a JSON object.")
    return value


def _rehydrate_canonical_document(
    *,
    canonical_bytes: bytes,
    content_key: str,
    document_kind: str,
    schema_revision: str,
    key_prefix: str,
    payload_validator: Callable[[object], object],
) -> SealedCanonicalDocument:
    """Recreate one sealed document from exact persisted bytes or fail closed."""

    try:
        _seal_inputs(
            document_kind=document_kind,
            schema_revision=schema_revision,
            key_prefix=key_prefix,
        )
        if type(canonical_bytes) is not bytes:
            raise CanonicalValueError("INVALID_CANONICAL_BYTES", "canonicalBytes")
        if type(content_key) is not str:
            raise CanonicalValueError("INVALID_CONTENT_KEY", "contentKey")
        payload = _strict_payload(canonical_bytes)
        payload_validator(payload)
        if canonical_json_bytes(payload) != canonical_bytes:
            raise CanonicalValueError("NON_CANONICAL_JSON_BYTES", "canonicalBytes")
        expected_key = _content_key(key_prefix, canonical_bytes)
        if content_key != expected_key:
            raise CanonicalValueError("CONTENT_KEY_MISMATCH", "contentKey")
        return SealedCanonicalDocument(
            _SEAL_TOKEN,
            document_kind=document_kind,
            schema_revision=schema_revision,
            canonical_bytes=canonical_bytes,
            content_key=content_key,
        )
    except CanonicalValueError:
        raise
    except (
        TypeError,
        ValueError,
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
    ) as error:
        raise CanonicalValueError(
            "INVALID_CANONICAL_DOCUMENT", "canonicalBytes",
        ) from error


def verify_sealed_document(
    document: object,
    *,
    document_kind: str,
    schema_revision: str,
    key_prefix: str,
    payload_validator: Callable[[object], object],
) -> bool:
    try:
        _seal_inputs(document_kind=document_kind, schema_revision=schema_revision, key_prefix=key_prefix)
        if type(document) is not SealedCanonicalDocument:
            return False
        if document.document_kind != document_kind or document.schema_revision != schema_revision:
            return False
        payload = _strict_payload(document.canonical_bytes)
        payload_validator(payload)
        if canonical_json_bytes(payload) != document.canonical_bytes:
            return False
        return document.content_key == _content_key(key_prefix, document.canonical_bytes)
    except (
        CanonicalValueError,
        TypeError,
        ValueError,
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
    ):
        return False


def verified_payload_copy(
    document: SealedCanonicalDocument,
    *,
    document_kind: str,
    schema_revision: str,
    key_prefix: str,
    payload_validator: Callable[[object], object],
) -> dict[str, object]:
    if not verify_sealed_document(
        document,
        document_kind=document_kind,
        schema_revision=schema_revision,
        key_prefix=key_prefix,
        payload_validator=payload_validator,
    ):
        raise CanonicalValueError("INVALID_SEALED_DOCUMENT", "document")
    return _strict_payload(document.canonical_bytes)

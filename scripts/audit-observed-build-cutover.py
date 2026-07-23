#!/usr/bin/env python3
"""Exhaustively audit the public observed-build talent and gear contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.websim_payload import expected_hero_tree_triplets


AUDIT_SCHEMA_REVISION = "observed-build-cutover-audit-v1"
EXPECTED_SLOT_COUNT = 80
EXPECTED_SPEC_COUNT = 40
MAX_FAILURES = 12


def _text(value: Any) -> str:
    return str(value or "").strip()


def _expected_slots() -> list[dict[str, str]]:
    return [
        {
            "classKey": class_key,
            "specKey": spec_key,
            "heroKey": hero_key,
        }
        for class_key, spec_key, hero_key in (
            triplet.split(":")
            for triplet in expected_hero_tree_triplets()
        )
    ]


def _slot_key(slot: dict[str, Any]) -> str:
    return ":".join(
        _text(slot.get(key))
        for key in ("classKey", "specKey", "heroKey")
    )


def _failure(
    code: str,
    *,
    slot: str = "",
    spec: str = "",
    http_status: int = 0,
) -> dict[str, Any]:
    output: dict[str, Any] = {"code": _text(code)[:120]}
    if slot:
        output["slot"] = _text(slot)[:200]
    if spec:
        output["spec"] = _text(spec)[:160]
    if http_status:
        output["httpStatus"] = int(http_status)
    return output


class AuditClient:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        body = (
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "wow-observed-build-cutover-audit/1",
            },
            method="POST" if body is not None else "GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as error:
            status = int(error.code)
            raw = error.read()
        except (OSError, URLError, TimeoutError):
            return 0, {}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return status, {}
        return status, decoded if isinstance(decoded, dict) else {}

    def talent(self, slot: dict[str, str]) -> tuple[int, dict[str, Any]]:
        query = urlencode(
            {
                "class": slot["classKey"],
                "spec": slot["specKey"],
                "hero": slot["heroKey"],
            }
        )
        return self._request(f"/api/websim/talents?{query}")

    def gear(
        self,
        class_key: str,
        spec_key: str,
    ) -> tuple[int, dict[str, Any]]:
        query = urlencode(
            {
                "class": class_key,
                "spec": spec_key,
                "compact": "1",
                "mode": "initial",
            }
        )
        return self._request(f"/api/websim/gear?{query}")

    def import_talent(
        self,
        slot: dict[str, str],
        code: str,
    ) -> tuple[int, dict[str, Any]]:
        return self._request(
            "/api/talents/import",
            payload={
                "code": code,
                "classKey": slot["classKey"],
                "specKey": slot["specKey"],
                "heroKey": slot["heroKey"],
            },
        )

    def import_gear(
        self,
        *,
        class_key: str,
        spec_key: str,
        template_id: str,
        manifest_revision: str,
    ) -> tuple[int, dict[str, Any]]:
        return self._request(
            "/api/websim/gear/community-import",
            payload={
                "classKey": class_key,
                "specKey": spec_key,
                "templateId": template_id,
                "expectedManifestRevision": manifest_revision,
            },
        )


def _one_matching_talent(
    payload: dict[str, Any],
    slot: dict[str, str],
) -> dict[str, Any]:
    matches = [
        template
        for template in payload.get("communityTemplates") or []
        if isinstance(template, dict)
        and _text(template.get("classKey")) == slot["classKey"]
        and _text(template.get("specKey")) == slot["specKey"]
        and _text(template.get("heroKey")) == slot["heroKey"]
        and template.get("status") == "verified"
        and template.get("canApplyVisual") is True
    ]
    return matches[0] if len(matches) == 1 else {}


def _valid_provenance(template: dict[str, Any]) -> bool:
    return (
        _text(template.get("id")).startswith(
            "build-projection:sha256:"
        )
        and _text(template.get("templateSetId")).startswith(
            "template-set:sha256:"
        )
        and _text(template.get("snapshotId")).startswith(
            "observed-build:sha256:"
        )
        and _text(template.get("sourceIdentity")).startswith("raiderio:")
        and isinstance(template.get("pointerGeneration"), int)
        and not isinstance(template.get("pointerGeneration"), bool)
        and int(template.get("pointerGeneration") or 0) >= 1
        and template.get("slotStatus") in {"verified", "stale_lkg"}
    )


def _talent_import_verified(
    payload: dict[str, Any],
    slot: dict[str, str],
) -> bool:
    validation = (
        payload.get("validation")
        if isinstance(payload.get("validation"), dict)
        else {}
    )
    talent_state = (
        payload.get("talentState")
        if isinstance(payload.get("talentState"), dict)
        else {}
    )
    return (
        _text(payload.get("classKey")) == slot["classKey"]
        and _text(payload.get("specKey")) == slot["specKey"]
        and _text(payload.get("heroKey")) == slot["heroKey"]
        and validation.get("status") not in {
            "",
            "blocked",
            "failed",
        }
        and bool(talent_state.get("selectedNodes"))
    )


def _gear_import_verified(payload: dict[str, Any]) -> bool:
    data = (
        payload.get("data")
        if isinstance(payload.get("data"), dict)
        else {}
    )
    resolved = (
        data.get("resolvedSnapshot")
        if isinstance(data.get("resolvedSnapshot"), dict)
        else {}
    )
    return (
        payload.get("status") == "verified"
        and data.get("status") == "verified"
        and resolved.get("status") == "verified"
        and bool(data.get("importedGearBySlot"))
        and bool(resolved.get("resolvedGearSignature"))
    )


def run_audit(client: AuditClient) -> dict[str, Any]:
    slots = _expected_slots()
    if len(slots) != EXPECTED_SLOT_COUNT:
        raise RuntimeError("expected Hero slot contract must contain 80 slots")
    specs: dict[str, list[dict[str, str]]] = {}
    for slot in slots:
        spec_id = f"{slot['classKey']}:{slot['specKey']}"
        specs.setdefault(spec_id, []).append(slot)
    if len(specs) != EXPECTED_SPEC_COUNT or any(
        len(spec_slots) != 2 for spec_slots in specs.values()
    ):
        raise RuntimeError(
            "expected specialization contract must contain 40 two-Hero specs"
        )

    failures: list[dict[str, Any]] = []
    failure_count = 0

    def fail(
        code: str,
        *,
        slot: str = "",
        spec: str = "",
        http_status: int = 0,
    ) -> None:
        nonlocal failure_count
        failure_count += 1
        if len(failures) < MAX_FAILURES:
            failures.append(
                _failure(
                    code,
                    slot=slot,
                    spec=spec,
                    http_status=http_status,
                )
            )

    talents_by_slot: dict[str, dict[str, Any]] = {}
    talent_read_count = 0
    for slot in slots:
        key = _slot_key(slot)
        status, payload = client.talent(slot)
        if status != 200:
            fail("talent_read_http_failed", slot=key, http_status=status)
            continue
        template = _one_matching_talent(payload, slot)
        if not template:
            fail("talent_template_cardinality_invalid", slot=key)
            continue
        if not _valid_provenance(template):
            fail("talent_template_provenance_invalid", slot=key)
            continue
        if not _text(template.get("websimExportCode")):
            fail("talent_template_import_code_missing", slot=key)
            continue
        talents_by_slot[key] = template
        talent_read_count += 1

    gear_by_slot: dict[str, dict[str, Any]] = {}
    gear_spec_count = 0
    gear_template_count = 0
    for spec_id, spec_slots in sorted(specs.items()):
        class_key, spec_key = spec_id.split(":", 1)
        status, payload = client.gear(class_key, spec_key)
        if status != 200:
            fail("gear_read_http_failed", spec=spec_id, http_status=status)
            continue
        templates = [
            template
            for template in payload.get("communityTemplates") or []
            if isinstance(template, dict)
            and template.get("status") == "complete"
            and template.get("projectionStatus", "verified")
            == "verified"
            and template.get("canApplyGear") is True
        ]
        expected_heroes = {slot["heroKey"] for slot in spec_slots}
        actual_heroes = {
            _text(template.get("heroKey")) for template in templates
        }
        identities = {
            _text(template.get("sourceIdentity"))
            for template in templates
        }
        if (
            len(templates) != 2
            or actual_heroes != expected_heroes
            or len(identities) != 2
            or "" in identities
        ):
            fail("gear_template_pair_invalid", spec=spec_id)
            continue
        if not all(_valid_provenance(template) for template in templates):
            fail("gear_template_provenance_invalid", spec=spec_id)
            continue
        manifest_revision = _text(payload.get("manifestRevision"))
        if not manifest_revision:
            fail("gear_manifest_revision_missing", spec=spec_id)
            continue
        matched = True
        for template in templates:
            key = (
                f"{class_key}:{spec_key}:"
                f"{_text(template.get('heroKey'))}"
            )
            talent = talents_by_slot.get(key)
            if not talent or any(
                _text(template.get(field)) != _text(talent.get(field))
                for field in (
                    "id",
                    "templateSetId",
                    "snapshotId",
                    "sourceIdentity",
                )
            ):
                fail("talent_gear_identity_mismatch", slot=key)
                matched = False
                continue
            gear_by_slot[key] = {
                "classKey": class_key,
                "specKey": spec_key,
                "templateId": _text(template.get("id")),
                "manifestRevision": manifest_revision,
            }
        if matched:
            gear_spec_count += 1
            gear_template_count += 2

    talent_import_count = 0
    for slot in slots:
        key = _slot_key(slot)
        template = talents_by_slot.get(key)
        if not template:
            continue
        status, payload = client.import_talent(
            slot,
            _text(template.get("websimExportCode")),
        )
        if status != 200 or not _talent_import_verified(payload, slot):
            fail(
                "talent_import_failed",
                slot=key,
                http_status=status,
            )
            continue
        talent_import_count += 1

    gear_import_count = 0
    for key, request in sorted(gear_by_slot.items()):
        status, payload = client.import_gear(
            class_key=request["classKey"],
            spec_key=request["specKey"],
            template_id=request["templateId"],
            manifest_revision=request["manifestRevision"],
        )
        if status != 200 or not _gear_import_verified(payload):
            fail(
                "gear_import_failed",
                slot=key,
                http_status=status,
            )
            continue
        gear_import_count += 1

    counts = {
        "expectedTalentSlots": EXPECTED_SLOT_COUNT,
        "verifiedTalentSlots": talent_read_count,
        "verifiedTalentImports": talent_import_count,
        "expectedGearSpecs": EXPECTED_SPEC_COUNT,
        "verifiedGearSpecs": gear_spec_count,
        "expectedGearTemplates": EXPECTED_SLOT_COUNT,
        "verifiedGearTemplates": gear_template_count,
        "verifiedGearImports": gear_import_count,
        "matchedTalentGearSlots": len(gear_by_slot),
        "failureCount": failure_count,
    }
    complete = (
        failure_count == 0
        and talent_read_count == EXPECTED_SLOT_COUNT
        and talent_import_count == EXPECTED_SLOT_COUNT
        and gear_spec_count == EXPECTED_SPEC_COUNT
        and gear_template_count == EXPECTED_SLOT_COUNT
        and gear_import_count == EXPECTED_SLOT_COUNT
        and len(gear_by_slot) == EXPECTED_SLOT_COUNT
    )
    return {
        "schemaRevision": AUDIT_SCHEMA_REVISION,
        "status": "verified" if complete else "blocked",
        "counts": counts,
        "failures": failures,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit all 80 talent templates and 80 exact gear imports "
            "against one backend."
        )
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    timeout = max(1.0, min(120.0, float(args.timeout)))
    result = run_audit(AuditClient(args.base_url, timeout))
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())

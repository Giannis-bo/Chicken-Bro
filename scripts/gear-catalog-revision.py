#!/usr/bin/env python3
"""Build, seal and shadow-check one dormant Gear Catalog revision."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Iterable, Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.gear_catalog_audit_store import GearCatalogAuditStore  # noqa: E402
from server.gear_catalog_revision import build_catalog_revision  # noqa: E402
from server.gear_catalog_revision_store import GearCatalogRevisionStore  # noqa: E402


MAX_STATEMENT_TIMEOUT_MS = 30_000
MAX_LOCK_TIMEOUT_MS = 5_000
MAX_BATCH_SIZE = 1_000


def _text(value: Any) -> str:
    return str(value or "").strip()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _canonical(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def _hash(prefix: str, value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()


def _streaming_hash(prefix: str, value: Any) -> str:
    digest = hashlib.sha256()
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    for chunk in encoder.iterencode(value):
        digest.update(chunk.encode("utf-8"))
    return prefix + digest.hexdigest()


def _spec_pairs(class_spec_matrix: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for klass in class_spec_matrix or []:
        row = _mapping(klass)
        class_key = _text(row.get("key"))
        for raw_spec in row.get("specs") or []:
            spec_key = (
                _text(_mapping(raw_spec).get("key"))
                if isinstance(raw_spec, Mapping)
                else _text(raw_spec)
            )
            pairs.append((class_key, spec_key))
    if (
        len(pairs) != 40
        or len(set(pairs)) != 40
        or any(not all(pair) for pair in pairs)
    ):
        raise ValueError(
            "backend specialization matrix must contain 40 unique pairs"
        )
    return pairs


def _payload_pointer(payload: Mapping[str, Any]) -> dict[str, Any]:
    binding = _mapping(payload.get("_activeManifestBinding"))
    manifest = _mapping(binding.get("manifest"))
    return {
        "generation": _integer(
            payload.get("pointerGeneration") or binding.get("generation")
        ),
        "manifestRevision": _text(
            payload.get("manifestRevision")
            or manifest.get("manifestRevision")
        ),
    }


def _visible_candidate_pairs(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    groups = payload.get("replacementCandidates")
    if not isinstance(groups, list):
        groups = []
    for group in groups:
        items = _mapping(group).get("items")
        if not isinstance(items, list):
            continue
        for candidate in items:
            row = _mapping(candidate)
            item_id = _text(row.get("itemId") or row.get("id"))
            if not item_id:
                continue
            identities: set[str] = set()
            for variant in row.get("variants") or []:
                variant_row = _mapping(variant)
                identity = _text(
                    variant_row.get("variantKey")
                    or variant_row.get("id")
                )
                if identity:
                    identities.add(identity)
            direct = _text(row.get("variantKey"))
            if direct and not identities:
                identities.add(direct)
            for identity in identities:
                result.add((item_id, identity))
    if result:
        return sorted(result)
    for candidate in payload.get("catalogItems") or []:
        row = _mapping(candidate)
        item_id = _text(row.get("itemId") or row.get("id"))
        for variant in row.get("variants") or []:
            variant_row = _mapping(variant)
            identity = _text(
                variant_row.get("variantKey") or variant_row.get("id")
            )
            if item_id and identity:
                result.add((item_id, identity))
    return sorted(result)


def _snapshot_spec_payload_reader(
    catalog_rows: Mapping[str, Any],
    pointer: Mapping[str, Any],
    season_revision: str,
    *,
    selectors: Any = None,
    release_status: str = "validated",
) -> Callable[[str, str], Mapping[str, Any]]:
    if selectors is None:
        from server import pg_gear_read_model_selectors as selectors

    rows = _mapping(catalog_rows)
    source_rows = [
        (
            row.get("sourceId") or row.get("id"),
            row.get("itemId"),
            row.get("sourceType"),
            row.get("sourceKey"),
            row.get("sourceLabel"),
            row.get("instanceId"),
            row.get("encounterId"),
            row.get("difficultyKey"),
            row.get("seasonRevision"),
            row.get("payload"),
            row.get("updatedAt"),
        )
        for row in rows.get("sources") or []
        if isinstance(row, Mapping)
    ]
    variant_rows = [
        (
            row.get("variantId") or row.get("id"),
            row.get("itemId"),
            row.get("slot"),
            row.get("variantKey"),
            row.get("label"),
            row.get("sourceType"),
            row.get("difficultyKey"),
            row.get("itemLevel"),
            row.get("simcOptions"),
            row.get("status"),
            row.get("blockers"),
            row.get("payload"),
            row.get("updatedAt"),
        )
        for row in rows.get("variants") or []
        if (
            isinstance(row, Mapping)
            and _text(row.get("rowFamily")) == "browse"
        )
    ]
    option_rows = [
        (
            row.get("optionId") or row.get("id"),
            row.get("optionType"),
            row.get("optionKey"),
            row.get("name"),
            row.get("applicableSlots"),
            row.get("simcOptions"),
            row.get("status"),
            row.get("payload"),
            row.get("updatedAt"),
        )
        for row in rows.get("options") or []
        if isinstance(row, Mapping)
    ]
    item_rows = [
        (
            row.get("itemId") or row.get("id"),
            row.get("name"),
            row.get("slot"),
            row.get("itemLevel"),
            row.get("payload"),
            row.get("sourceStatus"),
        )
        for row in rows.get("items") or []
        if isinstance(row, Mapping)
    ]
    sources_by_item = (
        selectors.build_gear_sources_by_item_read_model(source_rows)
    )
    variants_by_item = (
        selectors.build_gear_variants_by_item_read_model(variant_rows)
    )
    options_by_slot = (
        selectors.build_gear_mod_options_by_type_read_model(option_rows)
    )
    season = {
        "seasonRevision": _text(season_revision),
        "dataStatus": (
            "verified"
            if _text(release_status) == "validated"
            else "blocked"
        ),
        "errors": [],
    }
    pointer_identity = {
        "manifestRevision": _text(pointer.get("manifestRevision")),
        "pointerGeneration": _integer(pointer.get("generation")),
    }

    def read(class_key: str, spec_key: str) -> Mapping[str, Any]:
        catalog_items = (
            selectors.build_gear_catalog_items_read_model(
                item_rows,
                sources_by_item,
                variants_by_item,
                options_by_slot,
                class_key,
                spec_key,
                season,
            )
        )
        read_model = (
            selectors.build_catalog_gear_read_model_fragment(
                catalog_items,
                options_by_slot,
                class_key,
                spec_key,
                compact=True,
            )
        )
        visible = _visible_candidate_pairs({
            "replacementCandidates": (
                read_model.get("replacementCandidates") or []
            )
        })
        return {
            **pointer_identity,
            "catalogStatus": season["dataStatus"],
            "catalogShadowVisibleCandidates": [
                [item_id, variant_key]
                for item_id, variant_key in visible
            ],
        }

    return read


def _catalog_binding(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    active = (
        _mapping(snapshot.get("requestedBinding"))
        or _mapping(snapshot.get("activeBinding"))
    )
    manifest = _mapping(active.get("manifest"))
    gear = _mapping(active.get("gearRelease"))
    dependency_vector = _mapping(gear.get("dependencyVector"))
    if not dependency_vector:
        dependency_vector = _mapping(manifest.get("dependencyVector"))
    return {
        "manifestRevision": _text(manifest.get("manifestRevision")),
        "gearReleaseId": _text(gear.get("releaseId")),
        "gearReleaseContentHash": _text(gear.get("contentHash")),
        "gearReleaseSchemaRevision": _text(gear.get("schemaRevision")),
        "seasonRevision": _text(manifest.get("seasonRevision")),
        "gearRuleRevision": _text(
            dependency_vector.get("gearRuleRevision")
            or _mapping(manifest.get("dependencyVector")).get(
                "gearRuleRevision"
            )
        ),
        "dependencyVector": dependency_vector,
        "sourceSummary": {
            "releaseStatus": _text(gear.get("releaseStatus")),
            "source": _mapping(gear.get("source")),
            "contentSummary": _mapping(gear.get("contentSummary")),
        },
    }


def _source_variant_aliases(
    rows: Mapping[str, Any],
) -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    for variant in rows.get("variants") or []:
        row = _mapping(variant)
        if _text(row.get("rowFamily")) != "browse":
            continue
        item_id = _text(row.get("itemId"))
        variant_key = _text(row.get("variantKey") or row.get("variantId"))
        variant_id = _text(row.get("variantId"))
        if item_id and variant_key:
            aliases[(item_id, variant_key)] = variant_key
            if variant_id:
                aliases[(item_id, variant_id)] = variant_key
    return aliases


def _shadow_specs(
    *,
    catalog: Mapping[str, Any],
    catalog_rows: Mapping[str, Any],
    pointer: Mapping[str, Any],
    spec_payload_reader: Callable[[str, str], Mapping[str, Any]],
    class_spec_matrix: Any,
) -> tuple[dict[str, Any], list[str]]:
    catalog_index: dict[tuple[str, str], str] = {}
    for variant in catalog.get("browseVariants") or []:
        row = _mapping(variant)
        item_id = _text(row.get("itemId"))
        browse_key = _text(row.get("browseVariantKey"))
        for source_key in row.get("sourceVariantKeys") or []:
            if item_id and _text(source_key) and browse_key:
                catalog_index[(item_id, _text(source_key))] = browse_key
        progression = _mapping(row.get("progressionState"))
        if (
            item_id
            and browse_key
            and _text(row.get("sourceType")).lower() == "crafted"
        ):
            public_track_key = _text(progression.get("trackKey"))
            item_level = _integer(row.get("itemLevel"))
            if public_track_key and item_level:
                catalog_index[(
                    item_id,
                    f"crafted-{public_track_key}-{item_level}",
                )] = browse_key
    del catalog
    aliases = _source_variant_aliases(catalog_rows)
    expected_manifest = _text(pointer.get("manifestRevision"))
    expected_generation = _integer(pointer.get("generation"))
    rows = []
    problem_codes: set[str] = set()
    unmapped_total = 0
    for class_key, spec_key in _spec_pairs(class_spec_matrix):
        payload = _mapping(spec_payload_reader(class_key, spec_key))
        observed_pointer = _payload_pointer(payload)
        projected_visible = payload.get(
            "catalogShadowVisibleCandidates"
        )
        visible = (
            sorted(
                {
                    (_text(row[0]), _text(row[1]))
                    for row in projected_visible
                    if (
                        isinstance(row, (list, tuple))
                        and len(row) == 2
                        and _text(row[0])
                        and _text(row[1])
                    )
                }
            )
            if isinstance(projected_visible, list)
            else _visible_candidate_pairs(payload)
        )
        unmapped = []
        mapped = []
        for item_id, visible_identity in visible:
            source_key = aliases.get(
                (item_id, visible_identity),
                visible_identity,
            )
            browse_key = catalog_index.get((item_id, source_key))
            if not browse_key:
                unmapped.append((item_id, visible_identity))
            else:
                mapped.append((item_id, browse_key))
        codes = []
        if (
            observed_pointer["manifestRevision"] != expected_manifest
            or observed_pointer["generation"] != expected_generation
        ):
            codes.append("CATALOG_SHADOW_SPEC_POINTER_MISMATCH")
        if not visible:
            codes.append("CATALOG_SHADOW_SPEC_CANDIDATES_MISSING")
        if unmapped:
            codes.append("CATALOG_SHADOW_VISIBLE_CANDIDATE_UNMAPPED")
        if len(visible) != len(set(mapped)):
            codes.append(
                "CATALOG_SHADOW_VISIBLE_CARDINALITY_MISMATCH"
            )
        backend_status = _text(
            payload.get("catalogStatus") or payload.get("dataStatus")
        )
        if backend_status != "verified":
            codes.append("CATALOG_SHADOW_BACKEND_STATUS_UNVERIFIED")
        problem_codes.update(codes)
        unmapped_total += len(unmapped)
        rows.append({
            "classKey": class_key,
            "specKey": spec_key,
            "status": "verified" if not codes else "blocked",
            "legacyVisibleCandidateCount": len(visible),
            "dormantBrowseVariantCount": len(set(mapped)),
            "collapsedAliasCount": max(
                0,
                len(visible) - len(set(mapped)),
            ),
            "unmappedCandidateCount": len(unmapped),
            "legacyVisibleSetHash": _hash(
                "sha256:",
                visible,
            ),
            "dormantVisibleSetHash": _hash(
                "sha256:",
                sorted(set(mapped)),
            ),
            "problemCodes": sorted(set(codes)),
        })
    verified_count = sum(1 for row in rows if row["status"] == "verified")
    return (
        {
            "schemaRevision": "gear-catalog-spec-shadow-v1",
            "status": "verified" if verified_count == 40 else "blocked",
            "specCount": len(rows),
            "verifiedSpecCount": verified_count,
            "blockedSpecCount": len(rows) - verified_count,
            "unmappedCandidateCount": unmapped_total,
            "rows": rows,
        },
        sorted(problem_codes),
    )


def run_migration(
    *,
    snapshot_reader: Callable[..., Mapping[str, Any]],
    pointer_reader: Callable[..., Mapping[str, Any]],
    seal_writer: Callable[[dict[str, Any]], Mapping[str, Any]],
    spec_payload_reader: Callable[[str, str], Mapping[str, Any]],
    class_spec_matrix: Any,
    statement_timeout_ms: int = 15_000,
    lock_timeout_ms: int = 1_000,
    batch_size: int = 500,
    observed_at: str = "",
) -> dict[str, Any]:
    """Run a bounded active-release to dormant-Catalog migration shadow."""

    snapshot = _mapping(snapshot_reader(
        statement_timeout_ms=statement_timeout_ms,
        lock_timeout_ms=lock_timeout_ms,
        batch_size=batch_size,
    ))
    pointer_before = _mapping(snapshot.get("pointerBefore"))
    if pointer_before != _mapping(snapshot.get("pointerAfter")):
        raise RuntimeError("CATALOG_SHADOW_SNAPSHOT_POINTER_CHANGED")
    binding = _catalog_binding(snapshot)
    catalog_rows = _mapping(snapshot.get("catalogRows"))
    first = build_catalog_revision(binding, catalog_rows)
    first_status = _text(first.get("status"))
    first_problem_codes = list(first.get("problemCodes") or [])
    first_problems = list(first.get("problems") or [])
    first_content_hash = _streaming_hash("sha256:", first)
    del first
    second = build_catalog_revision(binding, catalog_rows)
    deterministic = first_content_hash == _streaming_hash(
        "sha256:",
        second,
    )
    if first_status != "verified" or not deterministic:
        problem_codes = set(first_problem_codes)
        problem_codes.update(second.get("problemCodes") or [])
        if not deterministic:
            problem_codes.add("CATALOG_SHADOW_BUILD_NONDETERMINISTIC")
        return {
            "schemaRevision": "gear-catalog-shadow-report-v1",
            "status": "blocked",
            "problemCodes": sorted(problem_codes),
            "problems": first_problems,
            "pointerBefore": pointer_before,
            "pointerAfter": pointer_before,
            "pointerStable": True,
            "deterministicBuild": deterministic,
            "observedAt": observed_at,
        }
    catalog_revision = _text(second.get("catalogRevision"))
    content_summary = _mapping(second.get("contentSummary"))
    # Transfer the only full-catalog reference to the store so it can release
    # the input before loading the sealed copy back from PostgreSQL.
    catalog_owner = [second]
    del second
    sealed = _mapping(seal_writer(catalog_owner.pop()))
    sealed_revision = _text(sealed.get("catalogRevision"))
    sealed_owner = [sealed]
    del sealed
    spec_shadow, shadow_codes = _shadow_specs(
        catalog=sealed_owner.pop(),
        catalog_rows=catalog_rows,
        pointer=pointer_before,
        spec_payload_reader=spec_payload_reader,
        class_spec_matrix=class_spec_matrix,
    )
    pointer_after = _mapping(pointer_reader(
        statement_timeout_ms=min(statement_timeout_ms, 5_000),
        lock_timeout_ms=lock_timeout_ms,
    ))
    pointer_stable = pointer_before == pointer_after
    problem_codes = set(shadow_codes)
    if sealed_revision != catalog_revision:
        problem_codes.add("CATALOG_SHADOW_SEAL_IDENTITY_MISMATCH")
    if not pointer_stable:
        problem_codes.add("CATALOG_SHADOW_POINTER_CHANGED")
    report = {
        "schemaRevision": "gear-catalog-shadow-report-v1",
        "status": "blocked" if problem_codes else "verified",
        "catalogRevision": catalog_revision,
        "sourceGearReleaseId": _text(binding.get("gearReleaseId")),
        "sourceGearReleaseContentHash": _text(
            binding.get("gearReleaseContentHash")
        ),
        "deterministicBuild": deterministic,
        "pointerStable": pointer_stable,
        "pointerBefore": pointer_before,
        "pointerAfter": pointer_after,
        "contentSummary": content_summary,
        "specShadow": spec_shadow,
        "problemCodes": sorted(problem_codes),
        "observedAt": observed_at,
    }
    report["reportId"] = _hash(
        "gear-catalog-shadow:sha256:",
        {
            key: value
            for key, value in report.items()
            if key not in {"observedAt", "reportId"}
        },
    )
    return report


def _bounded_integer(label: str, maximum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if not 1 <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"{label} must be between 1 and {maximum}"
            )
        return parsed

    return parse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and seal one dormant Gear Catalog revision.",
    )
    parser.add_argument("--output", default="-")
    parser.add_argument("--gear-release-id", default="")
    parser.add_argument("--community-release-id", default="")
    parser.add_argument(
        "--statement-timeout-ms",
        type=_bounded_integer("statement_timeout_ms", MAX_STATEMENT_TIMEOUT_MS),
        default=15_000,
    )
    parser.add_argument(
        "--lock-timeout-ms",
        type=_bounded_integer("lock_timeout_ms", MAX_LOCK_TIMEOUT_MS),
        default=1_000,
    )
    parser.add_argument(
        "--batch-size",
        type=_bounded_integer("batch_size", MAX_BATCH_SIZE),
        default=500,
    )
    args = parser.parse_args(argv)
    if bool(_text(args.gear_release_id)) != bool(
        _text(args.community_release_id)
    ):
        parser.error(
            "--gear-release-id and --community-release-id must be supplied together"
        )
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if _text(os.environ.get("WOW_DATABASE_RUNTIME")) != "postgres_only":
        print("CATALOG_REQUIRES_POSTGRES_ONLY", file=sys.stderr)
        return 2
    database_url = _text(os.environ.get("WOW_DATABASE_URL"))
    if not database_url:
        print("CATALOG_DATABASE_URL_MISSING", file=sys.stderr)
        return 2

    from server.db import connect_postgres
    from server.websim_payload import WOW_CLASSES

    connection_factory = lambda: connect_postgres(database_url)
    audit_store = GearCatalogAuditStore(connection_factory)
    catalog_store = GearCatalogRevisionStore(connection_factory)
    try:
        snapshot = _mapping(audit_store.snapshot(
            statement_timeout_ms=args.statement_timeout_ms,
            lock_timeout_ms=args.lock_timeout_ms,
            batch_size=args.batch_size,
            target_gear_release_id=args.gear_release_id,
            target_community_release_id=args.community_release_id,
        ))
        binding = _catalog_binding(snapshot)
        source_binding = (
            _mapping(snapshot.get("requestedBinding"))
            or _mapping(snapshot.get("activeBinding"))
        )
        spec_payload_reader_holder: list[
            Callable[[str, str], Mapping[str, Any]]
        ] = []

        def spec_payload_reader(
            class_key: str,
            spec_key: str,
        ) -> Mapping[str, Any]:
            if not spec_payload_reader_holder:
                spec_payload_reader_holder.append(
                    _snapshot_spec_payload_reader(
                        _mapping(snapshot.get("catalogRows")),
                        _mapping(snapshot.get("pointerBefore")),
                        _text(binding.get("seasonRevision")),
                        release_status=_text(
                            _mapping(
                                source_binding.get("gearRelease")
                            ).get("releaseStatus")
                        ),
                    )
                )
            return spec_payload_reader_holder[0](class_key, spec_key)

        report = run_migration(
            snapshot_reader=lambda **_: snapshot,
            pointer_reader=audit_store.pointer_identity,
            seal_writer=catalog_store.seal_catalog,
            spec_payload_reader=spec_payload_reader,
            class_spec_matrix=WOW_CLASSES,
            statement_timeout_ms=args.statement_timeout_ms,
            lock_timeout_ms=args.lock_timeout_ms,
            batch_size=args.batch_size,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        print(
            f"CATALOG_SHADOW_EXECUTION_FAILED:{type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    content = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    if args.output == "-":
        sys.stdout.write(content)
    else:
        output = Path(args.output)
        output.write_text(content, encoding="utf-8")
    return 0 if report.get("status") == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())

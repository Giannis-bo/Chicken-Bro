#!/usr/bin/env python3
"""Build and seal the bounded Phase 3 ResolvedLoadout/Snapshot shadow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.gear_catalog_audit_store import GearCatalogAuditStore  # noqa: E402
from server.gear_resolved_loadout import (  # noqa: E402
    build_resolved_loadout_from_registry,
)
from server.postgres_cache_store import PostgresCacheStore  # noqa: E402
from server.simc_support_policy import simc_execution_support  # noqa: E402
from server.simulation_snapshot_compat import (  # noqa: E402
    snapshot_from_compatibility_profile,
)
from server.websim_payload import (  # noqa: E402
    build_websim_profile_response_from_resolved_snapshot,
)


MAX_SECONDS = 300.0
MAX_BYTES = 2_000_000_000


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _hash(prefix: str, value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return prefix + hashlib.sha256(encoded).hexdigest()


def _peak_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss or 0)
    return peak if sys.platform == "darwin" else peak * 1024


def _problem_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        for code in row.get("problemCodes") or []:
            normalized = _text(code)
            if normalized:
                result[normalized] = result.get(normalized, 0) + 1
    return {key: result[key] for key in sorted(result)}


def run_shadow(
    *,
    templates: list[Mapping[str, Any]],
    exact_registry: Mapping[str, Any],
    resolver_reader: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    snapshot_reader: Callable[
        [Mapping[str, Any], Mapping[str, Any]],
        Mapping[str, Any],
    ],
    seal_loadout: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    seal_snapshot: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    pointer_before: Mapping[str, Any],
    pointer_after_reader: Callable[[], Mapping[str, Any]],
    observed_at: str,
    expected_template_count: int = 80,
    expected_spec_count: int = 40,
    expected_supported_spec_count: int = 26,
    expected_unsupported_spec_count: int = 14,
    expected_ready_loadout_count: int = 8,
    expected_ready_snapshot_count: int = 4,
    expected_unsupported_snapshot_count: int = 4,
) -> dict[str, Any]:
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    for raw_template in templates:
        template = _mapping(raw_template)
        content_hash = _text(template.get("templateContentHash")) or _hash(
            "sha256:",
            {
                "classKey": _text(template.get("classKey")),
                "specKey": _text(template.get("specKey")),
                "templateId": _text(
                    template.get("templateId") or template.get("id")
                ),
            },
        )
        import_status = _text(template.get("importStatus")) or "verified"
        if import_status != "verified":
            import_problem_codes = sorted(
                {
                    _text(code)
                    for code in template.get("importProblemCodes") or []
                    if _text(code)
                }
            )
            first_loadout = {
                "status": "blocked",
                "problemCodes": (
                    import_problem_codes
                    or ["RESOLVED_SHADOW_IMPORT_BLOCKED"]
                ),
            }
            second_loadout = first_loadout
        else:
            try:
                first_resolver = _mapping(resolver_reader(template))
                second_resolver = _mapping(resolver_reader(template))
                first_loadout = build_resolved_loadout_from_registry(
                    resolver_snapshot=first_resolver,
                    exact_registry=exact_registry,
                    template_scope="community",
                )
                second_loadout = build_resolved_loadout_from_registry(
                    resolver_snapshot=second_resolver,
                    exact_registry=exact_registry,
                    template_scope="community",
                )
            except Exception:
                first_loadout = {
                    "status": "blocked",
                    "problemCodes": ["RESOLVED_SHADOW_RESOLVER_FAILED"],
                }
                second_loadout = first_loadout

        deterministic_loadout = first_loadout == second_loadout
        snapshot_status = "not_applicable"
        snapshot_key = ""
        deterministic_snapshot = True
        problem_codes = set(first_loadout.get("problemCodes") or [])
        loadout_key = _text(first_loadout.get("resolvedLoadoutKey"))
        if first_loadout.get("status") == "ready" and deterministic_loadout:
            try:
                sealed_loadout = _mapping(seal_loadout(first_loadout))
                if sealed_loadout != first_loadout:
                    raise RuntimeError("loadout seal mismatch")
                first_snapshot = _mapping(
                    snapshot_reader(first_loadout, template)
                )
                second_snapshot = _mapping(
                    snapshot_reader(first_loadout, template)
                )
                deterministic_snapshot = first_snapshot == second_snapshot
                snapshot_status = _text(first_snapshot.get("status"))
                snapshot_key = _text(
                    first_snapshot.get("simulationSnapshotKey")
                )
                problem_codes.update(first_snapshot.get("problemCodes") or [])
                if snapshot_status == "ready" and deterministic_snapshot:
                    sealed_snapshot = _mapping(seal_snapshot(first_snapshot))
                    if sealed_snapshot != first_snapshot:
                        raise RuntimeError("snapshot seal mismatch")
            except Exception:
                snapshot_status = "blocked"
                problem_codes.add("RESOLVED_SHADOW_SNAPSHOT_FAILED")

        rows.append(
            {
                "templateContentHash": content_hash,
                "classKey": _text(template.get("classKey")),
                "specKey": _text(template.get("specKey")),
                "loadoutStatus": _text(first_loadout.get("status"))
                or "blocked",
                "resolvedLoadoutKey": loadout_key,
                "snapshotStatus": snapshot_status,
                "simulationSnapshotKey": snapshot_key,
                "deterministicLoadout": deterministic_loadout,
                "deterministicSnapshot": deterministic_snapshot,
                "problemCodes": sorted(
                    {_text(code) for code in problem_codes if _text(code)}
                ),
            }
        )

    pointer_after = _mapping(pointer_after_reader())
    elapsed = time.monotonic() - started
    peak_bytes = _peak_bytes()
    spec_pairs = {
        (_text(row.get("classKey")), _text(row.get("specKey")))
        for row in rows
        if _text(row.get("classKey")) and _text(row.get("specKey"))
    }
    ready_rows = [
        row for row in rows if row["loadoutStatus"] == "ready"
    ]
    ready_snapshots = [
        row for row in rows if row["snapshotStatus"] == "ready"
    ]
    unsupported_snapshots = [
        row for row in rows if row["snapshotStatus"] == "unsupported"
    ]
    blocked_loadouts = [
        row for row in rows if row["loadoutStatus"] != "ready"
    ]
    blocked_snapshots = [
        row
        for row in ready_rows
        if row["snapshotStatus"] not in {"ready", "unsupported"}
    ]
    supported_ready_specs = {
        (row["classKey"], row["specKey"])
        for row in ready_snapshots
    }
    unsupported_ready_specs = {
        (row["classKey"], row["specKey"])
        for row in unsupported_snapshots
    }
    classified_supported_specs = {
        (row["classKey"], row["specKey"])
        for row in rows
        if simc_execution_support(
            row["classKey"],
            row["specKey"],
        ).get("supported")
    }
    classified_unsupported_specs = spec_pairs.difference(
        classified_supported_specs
    )
    stable = {
        "schemaRevision": "gear-resolved-snapshot-shadow-v1",
        "catalogRevision": _text(exact_registry.get("catalogRevision")),
        "gearRuleRevision": _text(exact_registry.get("gearRuleRevision")),
        "exactRegistryRevision": _text(
            exact_registry.get("registryRevision")
        ),
        "pointerStable": _mapping(pointer_before) == pointer_after,
        "pointerBefore": _mapping(pointer_before),
        "pointerAfter": pointer_after,
        "summary": {
            "templateCount": len(templates),
            "classifiedTemplateCount": len(rows),
            "specCount": len(spec_pairs),
            "readyLoadoutCount": len(ready_rows),
            "blockedLoadoutCount": len(blocked_loadouts),
            "readySnapshotCount": len(ready_snapshots),
            "unsupportedSnapshotCount": len(unsupported_snapshots),
            "blockedSnapshotCount": len(blocked_snapshots),
            "readySupportedSpecCount": len(supported_ready_specs),
            "readyUnsupportedSpecCount": len(unsupported_ready_specs),
            "classifiedSupportedSpecCount": len(
                classified_supported_specs
            ),
            "classifiedUnsupportedSpecCount": len(
                classified_unsupported_specs
            ),
            "expectedSupportedSpecCount": expected_supported_spec_count,
            "expectedUnsupportedSpecCount": expected_unsupported_spec_count,
            "expectedReadyLoadoutCount": expected_ready_loadout_count,
            "expectedReadySnapshotCount": expected_ready_snapshot_count,
            "expectedUnsupportedSnapshotCount": (
                expected_unsupported_snapshot_count
            ),
        },
        "deterministic": {
            "loadouts": all(row["deterministicLoadout"] for row in rows),
            "snapshots": all(row["deterministicSnapshot"] for row in rows),
        },
        "problemCounts": _problem_counts(rows),
        "rows": rows,
    }
    problem_codes: set[str] = set()
    if len(templates) != expected_template_count or len(rows) != len(templates):
        problem_codes.add("RESOLVED_SHADOW_TEMPLATE_COUNT_INVALID")
    if len(spec_pairs) != expected_spec_count:
        problem_codes.add("RESOLVED_SHADOW_SPEC_COUNT_INVALID")
    if len(classified_supported_specs) != expected_supported_spec_count:
        problem_codes.add(
            "RESOLVED_SHADOW_SUPPORTED_SPEC_COVERAGE_INCOMPLETE"
        )
    if len(classified_unsupported_specs) != expected_unsupported_spec_count:
        problem_codes.add(
            "RESOLVED_SHADOW_UNSUPPORTED_SPEC_COVERAGE_INCOMPLETE"
        )
    if len(ready_rows) != expected_ready_loadout_count:
        problem_codes.add(
            "RESOLVED_SHADOW_READY_LOADOUT_COUNT_MISMATCH"
        )
    if len(ready_snapshots) != expected_ready_snapshot_count:
        problem_codes.add(
            "RESOLVED_SHADOW_READY_SNAPSHOT_COUNT_MISMATCH"
        )
    if len(unsupported_snapshots) != expected_unsupported_snapshot_count:
        problem_codes.add(
            "RESOLVED_SHADOW_UNSUPPORTED_SNAPSHOT_COUNT_MISMATCH"
        )
    if not stable["pointerStable"]:
        problem_codes.add("RESOLVED_SHADOW_POINTER_CHANGED")
    if not stable["deterministic"]["loadouts"]:
        problem_codes.add("RESOLVED_SHADOW_LOADOUT_NONDETERMINISTIC")
    if not stable["deterministic"]["snapshots"]:
        problem_codes.add("RESOLVED_SHADOW_SNAPSHOT_NONDETERMINISTIC")
    if len(ready_rows) + len(blocked_loadouts) != len(rows):
        problem_codes.add("RESOLVED_SHADOW_SILENT_DROP")
    if blocked_snapshots:
        problem_codes.add("RESOLVED_SHADOW_READY_SNAPSHOT_BLOCKED")
    if elapsed > MAX_SECONDS:
        problem_codes.add("RESOLVED_SHADOW_RESOURCE_SECONDS_EXCEEDED")
    if peak_bytes > MAX_BYTES:
        problem_codes.add("RESOLVED_SHADOW_RESOURCE_BYTES_EXCEEDED")
    status = "verified" if not problem_codes else "blocked"
    report = {
        **stable,
        "status": status,
        "problemCodes": sorted(problem_codes),
        "observedAt": _text(observed_at),
        "resource": {
            "elapsedSeconds": round(elapsed, 6),
            "peakBytes": peak_bytes,
            "maxSeconds": MAX_SECONDS,
            "maxBytes": MAX_BYTES,
        },
    }
    report["reportId"] = _hash(
        "gear-resolved-snapshot-shadow:sha256:",
        {
            key: value
            for key, value in report.items()
            if key not in {"observedAt", "resource", "reportId"}
        },
    )
    return report


class ProfileReader:
    def __init__(self, base_url: str, timeout_seconds: float):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.options = self._request("GET", "/api/simulator/simc/options")
        races = _mapping(self.options.get("races"))
        self.default_races = _mapping(races.get("defaultByClass"))
        self.browse: dict[tuple[str, str], dict[str, Any]] = {}
        self.heroes: dict[tuple[str, str], list[str]] = {}
        self.talents: dict[tuple[str, str, str], str] = {}

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as error:
            raw = error.read()
            if error.code >= 400:
                raise RuntimeError(f"profile HTTP {error.code}") from error
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise RuntimeError("profile response is not an object")
        return decoded

    def _browse_spec(
        self,
        class_key: str,
        spec_key: str,
    ) -> dict[str, Any]:
        pair = (class_key, spec_key)
        if pair not in self.browse:
            self.browse[pair] = self._request(
                "GET",
                "/api/websim/gear?"
                + urlencode(
                    {
                        "class": class_key,
                        "spec": spec_key,
                        "compact": "1",
                        "mode": "initial",
                    }
                ),
            )
        return self.browse[pair]

    def import_template(
        self,
        template: Mapping[str, Any],
    ) -> dict[str, Any]:
        class_key = _text(template.get("classKey"))
        spec_key = _text(template.get("specKey"))
        template_id = _text(
            template.get("templateId") or template.get("id")
        )
        stable = {
            "templateContentHash": _text(
                template.get("templateContentHash")
                or template.get("contentHash")
            ),
            "templateId": template_id,
            "classKey": class_key,
            "specKey": spec_key,
        }
        try:
            browse = self._browse_spec(class_key, spec_key)
            manifest_revision = _text(
                browse.get("manifestRevision")
            )
            matches = [
                row
                for row in browse.get("communityTemplates") or []
                if (
                    isinstance(row, Mapping)
                    and _text(row.get("id")) == template_id
                    and _text(row.get("classKey")) == class_key
                    and _text(row.get("specKey")) == spec_key
                )
            ]
            if len(matches) != 1 or not manifest_revision:
                return {
                    **stable,
                    "importStatus": "blocked",
                    "importProblemCodes": [
                        "RESOLVED_SHADOW_TEMPLATE_NOT_BROWSABLE"
                    ],
                }
            envelope = self._request(
                "POST",
                "/api/websim/gear/community-import",
                {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "templateId": template_id,
                    "expectedManifestRevision": manifest_revision,
                },
            )
        except Exception:
            return {
                **stable,
                "importStatus": "unavailable",
                "importProblemCodes": [
                    "RESOLVED_SHADOW_IMPORT_REQUEST_FAILED"
                ],
            }
        data = _mapping(envelope.get("data"))
        snapshot = _mapping(data.get("resolvedSnapshot"))
        status = _text(envelope.get("status"))
        problem_codes = sorted(
            {
                _text(problem.get("code"))
                for problem in envelope.get("problems") or []
                if isinstance(problem, Mapping)
                and _text(problem.get("code"))
            }
        )
        if (
            status == "verified"
            and data.get("status") == "verified"
            and snapshot.get("status") == "verified"
        ):
            return {
                **stable,
                "importStatus": "verified",
                "importProblemCodes": [],
                "resolvedSnapshot": snapshot,
            }
        return {
            **stable,
            "importStatus": status or "blocked",
            "importProblemCodes": (
                problem_codes
                or ["RESOLVED_SHADOW_IMPORT_BLOCKED"]
            ),
        }

    def templates_for_spec(
        self,
        class_key: str,
        spec_key: str,
    ) -> list[dict[str, Any]]:
        browse = self._browse_spec(class_key, spec_key)
        return [
            _mapping(row)
            for row in browse.get("communityTemplates") or []
            if (
                isinstance(row, Mapping)
                and _text(row.get("id"))
                and _text(row.get("classKey")) == class_key
                and _text(row.get("specKey")) == spec_key
            )
        ]

    def _talent_import(self, class_key: str, spec_key: str) -> str:
        pair = (class_key, spec_key)
        if pair not in self.heroes:
            browse = self._browse_spec(class_key, spec_key)
            self.heroes[pair] = sorted(
                {
                    _text(row.get("heroKey"))
                    for row in browse.get("communityTemplates") or []
                    if isinstance(row, Mapping) and _text(row.get("heroKey"))
                }
            )
        for hero in self.heroes[pair]:
            key = (class_key, spec_key, hero)
            if key not in self.talents:
                payload = self._request(
                    "GET",
                    "/api/websim/talents/import?"
                    + urlencode(
                        {
                            "class": class_key,
                            "spec": spec_key,
                            "hero": hero,
                        }
                    ),
                )
                self.talents[key] = _text(payload.get("importCode"))
            if self.talents[key]:
                return self.talents[key]
        raise RuntimeError("verified talent import unavailable")

    def profile(self, template: Mapping[str, Any]) -> str:
        class_key = _text(template.get("classKey"))
        spec_key = _text(template.get("specKey"))
        support = simc_execution_support(class_key, spec_key)
        if not support.get("supported"):
            return ""
        talent = self._talent_import(class_key, spec_key)
        response = build_websim_profile_response_from_resolved_snapshot(
            _mapping(template.get("resolvedSnapshot")),
            source_context={
                "classKey": class_key,
                "specKey": spec_key,
                "race": _text(self.default_races.get(class_key)),
                "scenarioKey": "single",
                "talents": talent,
            },
        )
        profile = response.get("profile")
        if (
            response.get("status") != "resolved"
            or not isinstance(profile, str)
            or not profile.strip()
        ):
            raise RuntimeError("canonical profile unavailable")
        return profile


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--output", default="-")
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if _text(os.environ.get("WOW_DATABASE_RUNTIME")) != "postgres_only":
        print("RESOLVED_SHADOW_REQUIRES_POSTGRES_ONLY", file=sys.stderr)
        return 2
    database_url = _text(os.environ.get("WOW_DATABASE_URL"))
    if not database_url:
        print("RESOLVED_SHADOW_DATABASE_URL_MISSING", file=sys.stderr)
        return 2

    from server.db import connect_postgres

    connection_factory = lambda: connect_postgres(database_url)
    audit_store = GearCatalogAuditStore(connection_factory)
    cache_store = PostgresCacheStore(connection_factory)
    profile_reader = ProfileReader(
        args.base_url,
        max(1.0, args.http_timeout_seconds),
    )
    try:
        audit = audit_store.snapshot()
        pointer_before = _mapping(audit.get("pointerBefore"))
        registry = cache_store.get_active_gear_exact_registry()

        spec_pairs = sorted(
            {
                (
                    _text(row.get("classKey")),
                    _text(row.get("specKey")),
                )
                for row in audit.get("communityTemplates") or []
                if (
                    isinstance(row, Mapping)
                    and _text(row.get("classKey"))
                    and _text(row.get("specKey"))
                )
            }
        )
        public_templates = [
            row
            for class_key, spec_key in spec_pairs
            for row in profile_reader.templates_for_spec(
                class_key,
                spec_key,
            )
        ]
        imported_templates = []
        for row in public_templates:
            first_import = profile_reader.import_template(row)
            second_import = profile_reader.import_template(row)
            if first_import == second_import:
                imported_templates.append(first_import)
                continue
            imported_templates.append({
                "templateContentHash": _text(
                    row.get("templateContentHash")
                    or row.get("contentHash")
                ),
                "templateId": _text(
                    row.get("templateId") or row.get("id")
                ),
                "classKey": _text(row.get("classKey")),
                "specKey": _text(row.get("specKey")),
                "importStatus": "blocked",
                "importProblemCodes": [
                    "RESOLVED_SHADOW_IMPORT_NONDETERMINISTIC"
                ],
            })

        def resolver_reader(template):
            return _mapping(template.get("resolvedSnapshot"))

        def snapshot_reader(loadout, template):
            class_key = _text(template.get("classKey"))
            spec_key = _text(template.get("specKey"))
            support = simc_execution_support(class_key, spec_key)
            if not support.get("supported"):
                from server.simulation_snapshot import build_simulation_snapshot

                return build_simulation_snapshot(
                    resolved_loadout=loadout,
                    talent_profile_key="",
                    talent_lines=[],
                    character_context={},
                    scenario_options={},
                    preparation_lines=[],
                    compiler_revision="simc-profile-compiler-v1",
                    simc_runtime_revision=args.simc_runtime_revision,
                )
            return snapshot_from_compatibility_profile(
                loadout,
                profile_reader.profile(template),
                scenario_key="single",
                compiler_revision="simc-profile-compiler-v1",
                simc_runtime_revision=args.simc_runtime_revision,
            )

        report = run_shadow(
            templates=imported_templates,
            exact_registry=registry,
            resolver_reader=resolver_reader,
            snapshot_reader=snapshot_reader,
            seal_loadout=cache_store.seal_resolved_loadout,
            seal_snapshot=cache_store.seal_simulation_snapshot,
            pointer_before=pointer_before,
            pointer_after_reader=audit_store.pointer_identity,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as error:
        print(
            f"RESOLVED_SHADOW_EXECUTION_FAILED:{type(error).__name__}",
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
        Path(args.output).write_text(content, encoding="utf-8")
    return 0 if report.get("status") == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())

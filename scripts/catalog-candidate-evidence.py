#!/usr/bin/env python3
"""Run the bounded Task 9 candidate evidence runner."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.catalog_candidate_evidence_runner import run_catalog_candidate_evidence
from server.db import connect_postgres
from server.gear_catalog_revision_store import GearCatalogRevisionStore
from server.gear_exact_item_registry_store import GearExactItemRegistryStore
from server.gear_release_store import GearReleaseStore
from server.gear_release_tool import expected_spec_pairs
from server.simulator_payload import (
    parse_simcraft_metrics,
    simcraft_item_name_diagnostics,
    simcraft_only_item_name_diagnostics,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _json_load(path_value: str) -> dict[str, Any]:
    loaded = json.loads(Path(path_value).read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _atomic_json_write(path_value: str, payload: dict[str, Any]) -> None:
    path = Path(path_value).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = handle.name
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = ""
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--manifest-revision", required=True)
    parser.add_argument("--pointer-generation", required=True, type=int)
    parser.add_argument("--gear-release-id", required=True)
    parser.add_argument("--community-release-id", required=True)
    parser.add_argument("--gear-catalog-revision", required=True)
    parser.add_argument("--gear-exact-registry-revision", required=True)
    parser.add_argument("--simc-runtime-revision", required=True)
    parser.add_argument("--simc-bin", required=True)
    parser.add_argument("--catalog-report", default="")
    parser.add_argument("--exact-report", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--simc-timeout-seconds", type=float, default=45.0)
    parser.add_argument("--smoke-max-time-seconds", type=int, default=5)
    return parser


def _connection_factory_from_env() -> Any:
    database_url = _text(os.environ.get("WOW_DATABASE_URL"))
    return lambda: connect_postgres(database_url)


def _extract_catalog_from_file(path_value: str) -> dict[str, Any]:
    loaded = _json_load(path_value)
    component = _mapping(_mapping(loaded.get("componentEvidence")).get("catalog"))
    if component:
        return dict(component)
    embedded = _mapping(loaded.get("catalog"))
    return dict(embedded) if embedded else dict(loaded)


def _extract_exact_from_file(path_value: str) -> dict[str, Any]:
    loaded = _json_load(path_value)
    component = _mapping(_mapping(loaded.get("componentEvidence")).get("exact_registry_report"))
    if component:
        return dict(component)
    embedded = _mapping(loaded.get("exact_registry_report"))
    return dict(embedded) if embedded else dict(loaded)


def _pointer_from_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "generation": int(binding.get("generation") or 0),
        "manifestRevision": _text(binding.get("manifestRevision")),
        "gearCatalogRevision": _text(binding.get("gearCatalogRevision")),
        "gearExactRegistryRevision": _text(binding.get("gearExactRegistryRevision")),
    }


def _request_json_builder(args: argparse.Namespace):
    base_url = _text(args.base_url).rstrip("/")

    def request_json(method, path, payload, headers):
        body = (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if isinstance(payload, dict)
            else None
        )
        request = Request(
            f"{base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        started = time.perf_counter()
        try:
            with urlopen(
                request,
                timeout=max(1.0, float(args.http_timeout_seconds)),
            ) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as error:
            status = int(error.code)
            raw = error.read()
        duration_ms = (time.perf_counter() - started) * 1000
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = {}
        return status, decoded if isinstance(decoded, dict) else {}, duration_ms

    return request_json


def _build_profile_context_factory(request_json, args: argparse.Namespace):
    cache: dict[tuple[str, str], dict[str, Any]] = {}

    def factory(*, class_key: str, spec_key: str):
        key = (_text(class_key), _text(spec_key))
        if key in cache:
            return dict(cache[key])
        options_status, options_payload, _options_ms = request_json(
            "GET",
            "/api/simulator/simc/options",
            None,
            {},
        )
        races = (
            options_payload.get("races")
            if isinstance(options_payload.get("races"), dict)
            else {}
        )
        default_races = (
            races.get("defaultByClass")
            if isinstance(races.get("defaultByClass"), dict)
            else {}
        )
        browse_status, browse, _browse_ms = request_json(
            "GET",
            f"/api/websim/gear?class={key[0]}&spec={key[1]}&compact=1&mode=initial",
            None,
            {"X-Wow-Platform": "miniprogram"},
        )
        templates = (
            browse.get("communityTemplates")
            if isinstance(browse.get("communityTemplates"), list)
            else []
        )
        selected_template = {}
        import_code = ""
        for raw_template in templates:
            template = _mapping(raw_template)
            hero_key = _text(template.get("heroKey"))
            template_id = _text(template.get("id"))
            if (
                _text(template.get("classKey")) != key[0]
                or _text(template.get("specKey")) != key[1]
                or not hero_key
                or not template_id
                or template.get("canApplyGear") is not True
            ):
                continue
            talent_status, talent_payload, _talent_ms = request_json(
                "GET",
                f"/api/websim/talents/import?class={key[0]}&spec={key[1]}&hero={hero_key}",
                None,
                {},
            )
            candidate_import = _text(talent_payload.get("importCode"))
            if (
                talent_status == 200
                and _text(talent_payload.get("status")) in {"verified", "ready"}
                and candidate_import
            ):
                selected_template = dict(template)
                import_code = candidate_import
                break
        level = 0
        if selected_template:
            import_status, imported_envelope, _import_ms = request_json(
                "POST",
                "/api/websim/gear/community-import",
                {
                    "classKey": key[0],
                    "specKey": key[1],
                    "templateId": _text(selected_template.get("id")),
                    "expectedManifestRevision": _text(args.manifest_revision),
                },
                {"Content-Type": "application/json"},
            )
            imported_data = (
                imported_envelope.get("data")
                if isinstance(imported_envelope.get("data"), dict)
                else {}
            )
            snapshot = (
                imported_data.get("resolvedSnapshot")
                if isinstance(imported_data.get("resolvedSnapshot"), dict)
                else {}
            )
            eligibility = (
                snapshot.get("eligibilityContext")
                if isinstance(snapshot.get("eligibilityContext"), dict)
                else {}
            )
            level = int(eligibility.get("level") or 0) if import_status == 200 else 0
        context = {
            "classKey": key[0],
            "specKey": key[1],
            "race": _text(default_races.get(key[0])) if options_status == 200 else "",
            "scenarioKey": "single",
            "heroKey": _text(selected_template.get("heroKey")),
            "talents": import_code,
            "level": level,
        }
        cache[key] = context
        return dict(context)

    return factory


def _simc_executor_builder(args: argparse.Namespace):
    def execute_profile(profile: str):
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                [
                    str(args.simc_bin),
                    "-",
                    "iterations=1",
                    f"max_time={max(1, min(5, int(args.smoke_max_time_seconds)))}",
                    "vary_combat_length=0",
                    "calculate_scale_factors=0",
                ],
                input=profile,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=max(1.0, float(args.simc_timeout_seconds)),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {
                "status": "blocked",
                "ran": False,
                "hasDps": False,
                "timedOut": True,
                "durationMs": (time.perf_counter() - started) * 1000,
                "executionMode": "real",
                "simcRuntimeRevision": _text(args.simc_runtime_revision),
                "iterations": 1,
                "maxTimeSeconds": max(1, min(5, int(args.smoke_max_time_seconds))),
            }
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        metrics = parse_simcraft_metrics(stdout or stderr)
        diagnostics = simcraft_item_name_diagnostics(stderr)
        trivial_item_name_exit = (
            completed.returncode != 0
            and bool(metrics.get("dps"))
            and bool(diagnostics)
            and simcraft_only_item_name_diagnostics(stderr)
        )
        return {
            "status": "verified" if (completed.returncode == 0 or trivial_item_name_exit) else "blocked",
            "ran": completed.returncode == 0 or trivial_item_name_exit,
            "hasDps": bool(metrics.get("dps")),
            "timedOut": False,
            "durationMs": (time.perf_counter() - started) * 1000,
            "executionMode": "real",
            "simcRuntimeRevision": _text(args.simc_runtime_revision),
            "iterations": 1,
            "maxTimeSeconds": max(1, min(5, int(args.smoke_max_time_seconds))),
        }

    return execute_profile


def _default_load_catalog(args: argparse.Namespace):
    if args.catalog_report:
        return _extract_catalog_from_file(args.catalog_report)
    store = GearCatalogRevisionStore(_connection_factory_from_env())
    return store.load_catalog(_text(args.gear_catalog_revision))


def _default_load_exact_registry(args: argparse.Namespace):
    if args.exact_report:
        return _extract_exact_from_file(args.exact_report)
    store = GearExactItemRegistryStore(_connection_factory_from_env())
    return store.load_registry(_text(args.gear_exact_registry_revision))


def _default_pointer_reader(_args: argparse.Namespace):
    binding = GearReleaseStore(_connection_factory_from_env()).load_active_manifest_binding()
    return _pointer_from_binding(binding)


def main(
    argv=None,
    *,
    load_catalog_fn=None,
    load_exact_registry_fn=None,
    pointer_reader_fn=None,
    runner_fn=run_catalog_candidate_evidence,
):
    args = _parser().parse_args(argv)
    load_catalog_fn = load_catalog_fn or _default_load_catalog
    load_exact_registry_fn = load_exact_registry_fn or _default_load_exact_registry
    pointer_reader_fn = pointer_reader_fn or _default_pointer_reader
    request_json = _request_json_builder(args)
    profile_context_factory = _build_profile_context_factory(request_json, args)
    simc_executor = _simc_executor_builder(args)
    expected_identity = {
        "manifestRevision": _text(args.manifest_revision),
        "pointerGeneration": int(args.pointer_generation),
        "gearCatalogRevision": _text(args.gear_catalog_revision),
        "gearExactRegistryRevision": _text(args.gear_exact_registry_revision),
        "simcRuntimeRevision": _text(args.simc_runtime_revision),
        "gearReleaseId": _text(args.gear_release_id),
        "communityReleaseId": _text(args.community_release_id),
    }

    report = runner_fn(
        load_catalog=lambda: load_catalog_fn(args),
        load_exact_registry=lambda: load_exact_registry_fn(args),
        request_json=request_json,
        profile_context_factory=profile_context_factory,
        simc_executor=simc_executor,
        pointer_reader=lambda: pointer_reader_fn(args),
        expected_specs=expected_spec_pairs(),
        expected_identity=expected_identity,
        observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    _atomic_json_write(args.output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if _text(_mapping(report).get("status")) == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())

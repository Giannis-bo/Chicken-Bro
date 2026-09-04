#!/usr/bin/env python3
"""Produce redacted dual-client acceptance evidence for Chickenbro.

The machine checks intentionally reuse the owner-scoped acceptance core.  The
WeChat/device step is explicit: this command only records the user-authorized
skip and never turns a skipped QR flow into a successful QR-login claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from server.accept_chickenbro_candidate import (
    AcceptanceError,
    AcceptanceSeed,
    CandidateHttpGateway,
    PostgresAcceptanceSeeder,
    run_candidate_acceptance,
)


SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
ROUTES = (
    "pages/chickenbro/index",
    "pages/simc/index",
    "pages/simc/tasks",
    "pages/simc/task-detail",
    "pages/auth/web-login-confirm",
)
LOGIN_MODE = "user_authorized_skipped"
PRODUCTION_PENDING_STATUS = "production_dual_client_acceptance_pending_user_confirmation"
PRODUCTION_PASSED_STATUS = "production_dual_client_acceptance_passed"


class AcceptanceEvidenceError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _hash(label: str, value: object) -> str:
    return hashlib.sha256(
        f"chickenbro-dual-client-acceptance-v1:{label}:{value}".encode("utf-8")
    ).hexdigest()


def _object_hash(label: str, *values: object) -> str:
    canonical = json.dumps(
        {"label": label, "values": list(values)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(
        f"chickenbro-dual-client-acceptance-v1:{canonical}".encode("utf-8")
    ).hexdigest()


def _validate_sha(value: object, code: str) -> str:
    normalized = str(value or "")
    if SHA256.fullmatch(normalized) is None:
        raise AcceptanceEvidenceError(code)
    return normalized


def _validate_commit(value: object) -> str:
    normalized = str(value or "")
    if COMMIT.fullmatch(normalized) is None:
        raise AcceptanceEvidenceError("COMMIT_IDENTITY_INVALID")
    return normalized


def _read_private(path: Path, label: str) -> Mapping[str, Any]:
    resolved = path.resolve(strict=False)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise AcceptanceEvidenceError(f"{label.upper().replace(' ', '_')}_PRIVATE_REQUIRED")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise AcceptanceEvidenceError(f"{label.upper().replace(' ', '_')}_INVALID") from None
    if not isinstance(payload, Mapping):
        raise AcceptanceEvidenceError(f"{label.upper().replace(' ', '_')}_INVALID")
    return payload


def _write_private(path: Path, payload: Mapping[str, Any]) -> None:
    resolved = path.resolve(strict=False)
    allowed_roots = {
        Path("/var/lib/chickenbro").resolve(strict=False),
        Path("/var/lib/chickenbro-recovery").resolve(strict=False),
    }
    if not any(root == resolved or root in resolved.parents for root in allowed_roots):
        raise AcceptanceEvidenceError("EVIDENCE_PATH_INVALID")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            output.write("\n")
        os.replace(temporary, resolved)
    finally:
        if temporary.exists():
            temporary.unlink()


def _iter_regular_files(root: Path):
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise AcceptanceEvidenceError("CLIENT_BUILD_ROOT_INVALID")
    for path in sorted(resolved.rglob("*")):
        if path.is_symlink():
            raise AcceptanceEvidenceError("CLIENT_BUILD_SYMLINK_UNSAFE")
        if path.is_file():
            yield path


def verify_route_contract(web_build_root: Path, weapp_build_root: Path) -> dict[str, Any]:
    """Verify that every retained route exists in both shipped client builds."""

    web_files = list(_iter_regular_files(web_build_root))
    if not web_files:
        raise AcceptanceEvidenceError("WEB_BUILD_EMPTY")
    web_bytes = [(path, path.read_bytes()) for path in web_files]
    route_digests: list[str] = []
    for route in ROUTES:
        weapp_path = weapp_build_root / f"{route}.js"
        if weapp_path.is_symlink() or not weapp_path.is_file():
            raise AcceptanceEvidenceError("WEAPP_ROUTE_MISSING")
        marker = route.encode("utf-8")
        if not any(marker in content for _path, content in web_bytes):
            raise AcceptanceEvidenceError("WEB_ROUTE_MISSING")
        route_digests.append(
            _object_hash(
                "route",
                route,
                hashlib.sha256(weapp_path.read_bytes()).hexdigest(),
                _hash("web-route", route),
            )
        )
    return {
        "status": "passed",
        "testedRoutes": list(ROUTES),
        "evidenceHash": _object_hash("route-contract", *route_digests),
    }


def _machine_object_hash(machine_evidence: Mapping[str, Any], label: str, *keys: str) -> str:
    redacted = machine_evidence.get("redactedObjectHashes")
    if not isinstance(redacted, Mapping):
        raise AcceptanceEvidenceError("MACHINE_EVIDENCE_REDACTED_HASHES_MISSING")
    values = []
    for key in keys:
        values.append(_validate_sha(redacted.get(key), "MACHINE_EVIDENCE_HASH_INVALID"))
    return _object_hash(label, *values)


def _require_machine_check(machine_evidence: Mapping[str, Any], key: str) -> None:
    checks = machine_evidence.get("checks")
    if not isinstance(checks, Mapping) or checks.get(key) is not True:
        raise AcceptanceEvidenceError(f"MACHINE_CHECK_FAILED_{key.upper()}")


def build_acceptance_evidence(
    *,
    mode: str,
    expected_commit: str,
    web_build_identity: str,
    weapp_build_identity: str,
    machine_evidence: Mapping[str, Any],
    route_report: Mapping[str, Any],
    accepted_at: str,
    candidate_evidence_sha256: str | None = None,
    cutover_evidence_sha256: str | None = None,
    first_accepted_write_at: str | None = None,
    service_restart_report: Mapping[str, Any] | None = None,
    user_confirmation: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    """Build either candidate real-acceptance or production machine evidence."""

    if mode not in {"candidate", "production"}:
        raise AcceptanceEvidenceError("ACCEPTANCE_MODE_INVALID")
    commit = _validate_commit(expected_commit)
    web_sha = _validate_sha(web_build_identity, "CLIENT_BUILD_IDENTITY_INVALID")
    weapp_sha = _validate_sha(weapp_build_identity, "CLIENT_BUILD_IDENTITY_INVALID")
    if route_report.get("status") != "passed" or list(route_report.get("testedRoutes", [])) != list(ROUTES):
        raise AcceptanceEvidenceError("ROUTE_CONTRACT_FAILED")
    route_hash = _validate_sha(route_report.get("evidenceHash"), "ROUTE_EVIDENCE_HASH_INVALID")
    if not isinstance(accepted_at, str) or not accepted_at.endswith("Z"):
        raise AcceptanceEvidenceError("ACCEPTED_AT_INVALID")
    _require_machine_check(machine_evidence, "ownerIsolation")
    _require_machine_check(machine_evidence, "logoutIndependent")
    chat_hash = _machine_object_hash(
        machine_evidence,
        "cross-client-chat",
        "miniCreatedConversation",
        "webCreatedConversation",
    )
    simc_hash = _machine_object_hash(
        machine_evidence,
        "cross-client-simc",
        "miniCreatedJob",
        "webCreatedJob",
    )
    owner_hash = _machine_object_hash(
        machine_evidence,
        "owner-isolation",
        "primaryUser",
        "otherUser",
    )
    login = {
        "status": "skipped",
        "evidenceHash": _hash("login-mode", LOGIN_MODE),
    }
    common = {
        "schemaVersion": (
            "chickenbro-real-dual-client-acceptance-v1"
            if mode == "candidate"
            else "chickenbro-production-dual-client-acceptance-v1"
        ),
        "status": (
            "real_dual_client_acceptance_passed"
            if mode == "candidate"
            else (PRODUCTION_PASSED_STATUS if user_confirmation else PRODUCTION_PENDING_STATUS)
        ),
        "branchCommit": commit,
        "webBuildIdentity": web_sha,
        "weappBuildIdentity": weapp_sha,
        "testedRoutes": list(ROUTES),
        "loginMode": LOGIN_MODE,
        "realWechatQrLogin": login,
        "crossClientChat": {"status": "passed", "objectHash": chat_hash},
        "crossClientSimc": {"status": "passed", "objectHash": simc_hash},
        "ownerIsolation": {"status": "passed", "objectHash": owner_hash},
    }
    if mode == "candidate":
        common["candidateEvidenceSha256"] = _validate_sha(
            candidate_evidence_sha256, "CANDIDATE_EVIDENCE_SHA_INVALID"
        )
        common["routeContractEvidenceHash"] = route_hash
        common["acceptedAt"] = accepted_at
    else:
        common["cutoverEvidenceSha256"] = _validate_sha(
            cutover_evidence_sha256, "CUTOVER_EVIDENCE_SHA_INVALID"
        )
        if not isinstance(service_restart_report, Mapping) or service_restart_report.get("status") != "passed":
            raise AcceptanceEvidenceError("SERVICE_RESTART_RECOVERY_REQUIRED")
        common["routeContractEvidenceHash"] = route_hash
        common["logoutIndependence"] = {
            "status": "passed",
            "evidenceHash": _hash("logout", machine_evidence.get("recordedAt", "")),
        }
        common["serviceRestartRecovery"] = {
            "status": "passed",
            "evidenceHash": _validate_sha(
                service_restart_report.get("evidenceHash"), "SERVICE_RESTART_EVIDENCE_HASH_INVALID"
            ),
        }
        first_write = first_accepted_write_at or accepted_at
        if not isinstance(first_write, str) or not first_write.endswith("Z"):
            raise AcceptanceEvidenceError("FIRST_ACCEPTED_WRITE_AT_INVALID")
        common["userConfirmation"] = {
            "status": "accepted" if user_confirmation else "pending",
            "evidenceHash": _hash(
                "user-confirmation",
                confirmation_token if user_confirmation and confirmation_token else "pending",
            ),
        }
        common["firstAcceptedWriteAt"] = first_write
        common["acceptedAt"] = accepted_at
    serialized = json.dumps(common, ensure_ascii=False, sort_keys=True, separators=(",", ":")).lower()
    for forbidden in (
        "access_token",
        "session_key",
        "provider_subject",
        "cookie_value",
        "wechat_secret",
        "openid",
        "sessionkey",
        "bearer",
    ):
        if forbidden in serialized:
            raise AcceptanceEvidenceError("EVIDENCE_REDACTION_FAILED")
    return common


def finalize_production_acceptance(
    payload: Mapping[str, Any],
    *,
    confirmation_at: str,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    if payload.get("status") != PRODUCTION_PENDING_STATUS:
        raise AcceptanceEvidenceError("PRODUCTION_ACCEPTANCE_NOT_PENDING")
    if confirmation_token != "I_HAVE_TESTED_PRODUCTION":
        raise AcceptanceEvidenceError("USER_CONFIRMATION_REQUIRED")
    if not isinstance(confirmation_at, str) or not confirmation_at.endswith("Z"):
        raise AcceptanceEvidenceError("ACCEPTED_AT_INVALID")
    updated = dict(payload)
    updated["status"] = PRODUCTION_PASSED_STATUS
    updated["userConfirmation"] = {
        "status": "accepted",
        "evidenceHash": _hash("user-confirmation", confirmation_token),
    }
    updated["acceptedAt"] = confirmation_at
    return updated


def _fetch_json(origin: str, path: str, timeout: int = 20) -> tuple[int, Mapping[str, Any]]:
    request = urllib.request.Request(
        origin + path,
        headers={"Accept": "application/json", "User-Agent": "chickenbro-dual-client-acceptance/1"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
        with response:
            raw = response.read(1_000_001)
            status = int(response.status)
    except urllib.error.HTTPError as error:
        raw = error.read(1_000_001)
        status = int(error.code)
    except (OSError, urllib.error.URLError, TimeoutError):
        raise AcceptanceEvidenceError("HTTP_TRANSPORT_FAILED") from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise AcceptanceEvidenceError("HTTP_RESPONSE_INVALID") from None
    if not isinstance(payload, Mapping):
        raise AcceptanceEvidenceError("HTTP_RESPONSE_INVALID")
    return status, payload


def _restart_and_verify(gateway: CandidateHttpGateway, prefix: str, api_origin: str) -> dict[str, Any]:
    before_status, before = _fetch_json(api_origin, f"{prefix}/health/readiness")
    if before_status != 200:
        raise AcceptanceEvidenceError("SERVICE_RESTART_PRECHECK_FAILED")
    try:
        subprocess.run(
            ["sudo", "-n", "systemctl", "restart", "chickenbro-api.service", "chickenbro-worker.service"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        raise AcceptanceEvidenceError("SERVICE_RESTART_FAILED") from None
    after = None
    for _attempt in range(30):
        try:
            status, payload = _fetch_json(api_origin, f"{prefix}/health/readiness")
            if status == 200:
                after = payload
                break
        except AcceptanceEvidenceError:
            pass
        time.sleep(1)
    if after is None:
        raise AcceptanceEvidenceError("SERVICE_RESTART_RECOVERY_FAILED")
    me = gateway.request("mini", "GET", f"{prefix}/me")
    if me.status != 200 or me.payload.get("connected") is not True:
        raise AcceptanceEvidenceError("SERVICE_RESTART_SESSION_RECOVERY_FAILED")
    evidence_hash = _object_hash(
        "service-restart-recovery",
        before.get("status"),
        before.get("components"),
        after.get("status"),
        after.get("components"),
        me.payload.get("connected"),
    )
    return {"status": "passed", "evidenceHash": evidence_hash}


def _diagnostic_error(error: BaseException) -> str:
    return f"{type(error).__name__}: {str(error or '')[:240]}"[:320]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run redacted Chickenbro dual-client acceptance")
    parser.add_argument("--mode", choices=("candidate", "production"), required=True)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--web-build-identity", required=True)
    parser.add_argument("--weapp-build-identity", required=True)
    parser.add_argument("--web-build-root", required=True)
    parser.add_argument("--weapp-build-root", required=True)
    parser.add_argument("--evidence-path", required=True)
    parser.add_argument("--candidate-evidence-path")
    parser.add_argument("--cutover-evidence-path")
    parser.add_argument("--source-url")
    parser.add_argument("--api-origin")
    parser.add_argument("--www-origin")
    parser.add_argument("--prefix")
    parser.add_argument("--csrf-cookie-name")
    parser.add_argument("--use-latest-ready-snapshot", action="store_true")
    parser.add_argument("--restart-services", action="store_true")
    parser.add_argument("--finalize-existing")
    parser.add_argument("--confirmation-token")
    parser.add_argument("--confirmation-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.finalize_existing:
            payload = _read_private(Path(args.finalize_existing), "production acceptance")
            final = finalize_production_acceptance(
                payload,
                confirmation_at=args.confirmation_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                confirmation_token=args.confirmation_token,
            )
            _write_private(Path(args.evidence_path), final)
            print(f"status={final['status']} evidence={args.evidence_path}")
            return 0

        expected_database = args.expected_database
        if args.mode == "candidate" and expected_database != "chickenbro_candidate":
            raise AcceptanceEvidenceError("CANDIDATE_DATABASE_INVALID")
        if args.mode == "production" and expected_database != "chickenbro_prod":
            raise AcceptanceEvidenceError("PRODUCTION_DATABASE_INVALID")
        if not args.candidate_evidence_path and args.mode == "candidate":
            raise AcceptanceEvidenceError("CANDIDATE_EVIDENCE_REQUIRED")
        if not args.cutover_evidence_path and args.mode == "production":
            raise AcceptanceEvidenceError("CUTOVER_EVIDENCE_REQUIRED")
        database_url = os.environ.get("WOW_DATABASE_URL", "").strip()
        app_context = os.environ.get("WOW_WECHAT_APPID", "").strip()
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise AcceptanceEvidenceError("PRODUCTION_DSN_REQUIRED" if args.mode == "production" else "CANDIDATE_DSN_REQUIRED")
        try:
            import psycopg
        except ImportError:
            raise AcceptanceEvidenceError("POSTGRES_DRIVER_UNAVAILABLE") from None
        if args.mode == "candidate":
            www_origin = args.www_origin or "https://www.chickenbro.cloud"
            api_origin = args.api_origin or "https://api.chickenbro.cloud"
            prefix = args.prefix or "/api/v2-candidate"
            csrf_cookie = args.csrf_cookie_name or "__Host-chickenbro-candidate-csrf"
        else:
            www_origin = args.www_origin or "https://www.chickenbro.cloud"
            api_origin = args.api_origin or "https://api.chickenbro.cloud"
            prefix = args.prefix or "/api/v2"
            csrf_cookie = args.csrf_cookie_name or "__Host-chickenbro-csrf"
        now = datetime.now(timezone.utc)
        seed = PostgresAcceptanceSeeder(lambda: psycopg.connect(database_url)).seed(
            expected_database=expected_database,
            app_context=app_context,
            now=now,
            use_latest_ready_snapshot=args.use_latest_ready_snapshot,
        )
        machine = run_candidate_acceptance(
            seed,
            CandidateHttpGateway(
                seed,
                www_origin=www_origin,
                api_origin=api_origin,
                prefix=prefix,
                csrf_cookie_name=csrf_cookie,
            ),
            expected_commit=args.expected_commit,
            web_build_identity=args.web_build_identity,
            weapp_build_identity=args.weapp_build_identity,
            source_url=args.source_url,
            prefix=prefix,
        )
        route_report = verify_route_contract(Path(args.web_build_root), Path(args.weapp_build_root))
        restart_report = None
        if args.restart_services:
            restart_report = _restart_and_verify(
                CandidateHttpGateway(
                    seed,
                    www_origin=www_origin,
                    api_origin=api_origin,
                    prefix=prefix,
                    csrf_cookie_name=csrf_cookie,
                ),
                prefix,
                api_origin,
            )
        candidate_sha = None
        cutover_sha = None
        if args.candidate_evidence_path:
            candidate_path = Path(args.candidate_evidence_path)
            _read_private(candidate_path, "candidate evidence")
            candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        if args.cutover_evidence_path:
            cutover_path = Path(args.cutover_evidence_path)
            _read_private(cutover_path, "cutover evidence")
            cutover_sha = hashlib.sha256(cutover_path.read_bytes()).hexdigest()
        accepted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        evidence = build_acceptance_evidence(
            mode=args.mode,
            expected_commit=args.expected_commit,
            web_build_identity=args.web_build_identity,
            weapp_build_identity=args.weapp_build_identity,
            candidate_evidence_sha256=candidate_sha,
            cutover_evidence_sha256=cutover_sha,
            machine_evidence=machine,
            route_report=route_report,
            accepted_at=accepted_at,
            first_accepted_write_at=accepted_at,
            service_restart_report=restart_report,
        )
        _write_private(Path(args.evidence_path), evidence)
    except (AcceptanceError, AcceptanceEvidenceError) as error:
        code = getattr(error, "code", str(error))
        print(f"accept_chickenbro_dual_client: {code}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"accept_chickenbro_dual_client: UNEXPECTED_FAILURE [{_diagnostic_error(error)}]", file=sys.stderr)
        return 1
    print(f"status={evidence['status']} evidence={args.evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "AcceptanceEvidenceError",
    "ROUTES",
    "build_acceptance_evidence",
    "finalize_production_acceptance",
    "verify_route_contract",
)

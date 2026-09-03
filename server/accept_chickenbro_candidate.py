#!/usr/bin/env python3
"""Run redacted, owner-scoped acceptance against the isolated candidate.

This is not real WeChat or real-device acceptance. It seeds short-lived
candidate-only authentication material, exercises the public formal APIs with
the two real credential transports, and writes only hashes and pass/fail facts.
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import math
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID


SHA256 = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
COMPILER_REVISION = "chickenbro-simc-compiler-v1"
CANDIDATE_PREFIX = "/api/v2-candidate"
WWW_ORIGIN = "https://www.chickenbro.cloud"
API_ORIGIN = "https://api.chickenbro.cloud"
CSRF_COOKIE_NAME = "__Host-chickenbro-candidate-csrf"


class AcceptanceError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ApiResponse:
    status: int
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AcceptanceSeed:
    primary_user_id: UUID
    other_user_id: UUID
    ready_snapshot_id: UUID
    mini_token: str = field(repr=False)
    other_mini_token: str = field(repr=False)
    web_login_session_id: UUID
    browser_verifier: str = field(repr=False)


class CandidateApi(Protocol):
    def exchange_web(self, session_id: UUID, browser_verifier: str) -> ApiResponse: ...

    def replay_web_exchange(self, session_id: UUID, browser_verifier: str) -> ApiResponse: ...

    def web_csrf_token(self) -> str: ...

    def request(
        self,
        transport: str,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ApiResponse: ...

    def stream_message(
        self,
        transport: str,
        path: str,
        *,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> ApiResponse: ...


def _utc(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(label: str, value: object) -> str:
    return hashlib.sha256(f"chickenbro-candidate-v1:{label}:{value}".encode("utf-8")).hexdigest()


def _require(response: ApiResponse, status: int, code: str) -> Mapping[str, Any]:
    if response.status != status or not isinstance(response.payload, Mapping):
        raise AcceptanceError(code)
    return response.payload


def _identifier(payload: Mapping[str, Any], code: str) -> str:
    value = str(payload.get("id") or "")
    try:
        UUID(value)
    except (TypeError, ValueError):
        raise AcceptanceError(code) from None
    return value


def _problem_code(payload: Mapping[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, Mapping):
        return str(error.get("code") or "")
    return str(payload.get("code") or "")


def _listed(payload: Mapping[str, Any], identifier: str) -> bool:
    items = payload.get("items")
    return isinstance(items, list) and any(
        isinstance(item, Mapping) and str(item.get("id") or "") == identifier
        for item in items
    )


def _assert_chat_detail(
    payload: Mapping[str, Any],
    *,
    conversation_id: str,
    expected_prompt: str,
) -> int:
    if str(payload.get("id") or "") != conversation_id:
        raise AcceptanceError("CHAT_CROSS_TRANSPORT_READ_FAILED")
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise AcceptanceError("CHAT_CROSS_TRANSPORT_READ_FAILED")
    users = [item for item in messages if isinstance(item, Mapping) and item.get("role") == "user"]
    assistants = [
        item for item in messages
        if isinstance(item, Mapping) and item.get("role") == "assistant"
    ]
    if not any(item.get("content") == expected_prompt for item in users):
        raise AcceptanceError("CHAT_CROSS_TRANSPORT_READ_FAILED")
    if not any(isinstance(item.get("content"), str) and item.get("content") for item in assistants):
        raise AcceptanceError("CHAT_CROSS_TRANSPORT_READ_FAILED")
    return len(messages)


def _assert_stream(payload: Mapping[str, Any]) -> None:
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise AcceptanceError("CHAT_STREAM_FAILED")
    if any(not isinstance(item, Mapping) for item in events):
        raise AcceptanceError("CHAT_STREAM_FAILED")
    sequences = [item.get("sequence") for item in events]
    if (
        any(not isinstance(value, int) or isinstance(value, bool) for value in sequences)
        or sequences != list(range(1, len(events) + 1))
    ):
        raise AcceptanceError("CHAT_STREAM_SEQUENCE_INVALID")
    event_types = [str(item.get("type") or "") for item in events]
    if not event_types or event_types[0] != "started" or event_types[-1] != "completed":
        raise AcceptanceError("CHAT_STREAM_FAILED")
    if "failed" in event_types:
        raise AcceptanceError("CHAT_STREAM_FAILED")


def _scenario_hash(scenario: Mapping[str, object]) -> str:
    canonical = json.dumps(scenario, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _assert_job_identity(
    payload: Mapping[str, Any],
    *,
    job_id: str,
    snapshot_id: UUID,
    scenario: Mapping[str, object],
) -> tuple[str, str]:
    expected_scenario_hash = _scenario_hash(scenario)
    if (
        str(payload.get("id") or "") != job_id
        or str(payload.get("snapshotId") or "") != str(snapshot_id)
        or payload.get("scenarioHash") != expected_scenario_hash
        or payload.get("compilerRevision") != COMPILER_REVISION
    ):
        raise AcceptanceError("SIMC_JOB_IDENTITY_INVALID")
    runtime_revision = str(payload.get("runtimeRevision") or "")
    if not runtime_revision or len(runtime_revision) > 160 or any(
        character.isspace() for character in runtime_revision
    ):
        raise AcceptanceError("SIMC_JOB_IDENTITY_INVALID")
    return expected_scenario_hash, runtime_revision


def _assert_semantic_result(
    payload: Mapping[str, Any],
    *,
    job_id: str,
    snapshot_id: UUID,
    scenario: Mapping[str, object],
) -> None:
    if payload.get("status") != "succeeded":
        raise AcceptanceError("SIMC_TERMINAL_FAILED")
    expected_scenario_hash, runtime_revision = _assert_job_identity(
        payload,
        job_id=job_id,
        snapshot_id=snapshot_id,
        scenario=scenario,
    )
    result = payload.get("result")
    attempts = payload.get("attempts")
    if not isinstance(result, Mapping) or not isinstance(attempts, list) or not attempts:
        raise AcceptanceError("SIMC_SEMANTIC_RESULT_MISSING")
    try:
        UUID(str(result.get("id") or ""))
    except (TypeError, ValueError):
        raise AcceptanceError("SIMC_PROVENANCE_INVALID") from None
    profile_sha256 = str(result.get("profileSha256") or "")
    metric_name = result.get("metricName")
    metric_value = result.get("metricValue")
    if (
        SHA256.fullmatch(profile_sha256) is None
        or metric_name not in {"dps", "hps"}
        or not isinstance(metric_value, (int, float))
        or isinstance(metric_value, bool)
        or not math.isfinite(float(metric_value))
        or float(metric_value) <= 0
        or result.get("compilerRevision") != COMPILER_REVISION
        or result.get("runtimeRevision") != runtime_revision
    ):
        raise AcceptanceError("SIMC_SEMANTIC_RESULT_INVALID")
    attempt_numbers = [
        attempt.get("attemptNumber") if isinstance(attempt, Mapping) else None
        for attempt in attempts
    ]
    if (
        any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in attempt_numbers)
        or attempt_numbers != sorted(set(attempt_numbers))
    ):
        raise AcceptanceError("SIMC_ATTEMPT_INVALID")
    final_attempt = attempts[-1]
    if (
        not isinstance(final_attempt, Mapping)
        or final_attempt.get("exitCode") != 0
        or final_attempt.get("diagnosticCode") != "SUCCEEDED"
    ):
        raise AcceptanceError("SIMC_ATTEMPT_INVALID")
    provenance = result.get("provenance")
    expected_provenance = {
        "snapshotId": str(snapshot_id),
        "profileSha256": profile_sha256,
        "compilerRevision": COMPILER_REVISION,
        "runtimeRevision": runtime_revision,
        "scenarioHash": expected_scenario_hash,
    }
    if not isinstance(provenance, Mapping) or any(
        str(provenance.get(key) or "") != value for key, value in expected_provenance.items()
    ):
        raise AcceptanceError("SIMC_PROVENANCE_INVALID")
    if (
        not str(provenance.get("sourceRevision") or "").strip()
        or SHA256.fullmatch(str(provenance.get("sourceRawSha256") or "")) is None
    ):
        raise AcceptanceError("SIMC_PROVENANCE_INVALID")


def _poll_job(
    api: CandidateApi,
    *,
    transport: str,
    path: str,
    job_id: str,
    snapshot_id: UUID,
    scenario: Mapping[str, object],
    sleep: Callable[[float], None],
    attempts: int = 90,
) -> Mapping[str, Any]:
    for _ in range(attempts):
        payload = _require(
            api.request(transport, "GET", f"{path}/{job_id}"),
            200,
            "SIMC_CROSS_TRANSPORT_READ_FAILED",
        )
        status = payload.get("status")
        if status == "succeeded":
            _assert_semantic_result(
                payload,
                job_id=job_id,
                snapshot_id=snapshot_id,
                scenario=scenario,
            )
            return payload
        if status in {"failed", "cancelled"}:
            raise AcceptanceError("SIMC_TERMINAL_FAILED")
        if status not in {"queued", "running"}:
            raise AcceptanceError("SIMC_STATUS_INVALID")
        sleep(2.0)
    raise AcceptanceError("SIMC_ACCEPTANCE_TIMEOUT")


def run_candidate_acceptance(
    seed: AcceptanceSeed,
    api: CandidateApi,
    *,
    expected_commit: str,
    web_build_identity: str,
    weapp_build_identity: str,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if COMMIT.fullmatch(expected_commit) is None:
        raise AcceptanceError("COMMIT_IDENTITY_INVALID")
    if SHA256.fullmatch(web_build_identity) is None or SHA256.fullmatch(weapp_build_identity) is None:
        raise AcceptanceError("CLIENT_BUILD_IDENTITY_INVALID")

    prefix = CANDIDATE_PREFIX
    exchange = _require(
        api.exchange_web(seed.web_login_session_id, seed.browser_verifier),
        200,
        "WEB_EXCHANGE_FAILED",
    )
    if exchange.get("authenticated") is not True:
        raise AcceptanceError("WEB_EXCHANGE_FAILED")
    replay = _require(
        api.replay_web_exchange(seed.web_login_session_id, seed.browser_verifier),
        409,
        "WEB_TICKET_REPLAY_NOT_REJECTED",
    )
    if _problem_code(replay) != "WEB_LOGIN_ALREADY_CONSUMED":
        raise AcceptanceError("WEB_TICKET_REPLAY_NOT_REJECTED")
    csrf = api.web_csrf_token()
    if not csrf or len(csrf) > 512 or any(character.isspace() for character in csrf):
        raise AcceptanceError("WEB_CSRF_COOKIE_INVALID")
    web_write = {"X-CSRF-Token": csrf}

    mini_me = _require(api.request("mini", "GET", f"{prefix}/me"), 200, "MINI_SESSION_FAILED")
    web_me = _require(api.request("web", "GET", f"{prefix}/me"), 200, "WEB_SESSION_FAILED")
    if mini_me.get("connected") is not True or web_me.get("connected") is not True:
        raise AcceptanceError("SHARED_OWNER_FAILED")
    if str(mini_me.get("displayName") or "") != str(web_me.get("displayName") or ""):
        raise AcceptanceError("SHARED_OWNER_FAILED")

    nonce = _hash("acceptance-run", seed.web_login_session_id)[:12]
    mini_conversation_body = {"title": f"acceptance-mini-{nonce}"}
    mini_conversation_headers = {
        "Idempotency-Key": f"acceptance-mini-conversation-{nonce}",
    }
    mini_conversation = _identifier(
        _require(
            api.request(
                "mini",
                "POST",
                f"{prefix}/chat/conversations",
                body=mini_conversation_body,
                headers=mini_conversation_headers,
            ),
            201,
            "MINI_CHAT_CREATE_FAILED",
        ),
        "MINI_CHAT_CREATE_FAILED",
    )
    mini_conversation_replay = _identifier(
        _require(
            api.request(
                "mini",
                "POST",
                f"{prefix}/chat/conversations",
                body=mini_conversation_body,
                headers=mini_conversation_headers,
            ),
            201,
            "CHAT_CREATE_IDEMPOTENT_REPLAY_FAILED",
        ),
        "CHAT_CREATE_IDEMPOTENT_REPLAY_FAILED",
    )
    if mini_conversation_replay != mini_conversation:
        raise AcceptanceError("CHAT_CREATE_IDEMPOTENT_REPLAY_FAILED")
    web_conversations = _require(
        api.request("web", "GET", f"{prefix}/chat/conversations"),
        200,
        "MINI_CREATED_WEB_VISIBLE_CHAT_FAILED",
    )
    if not _listed(web_conversations, mini_conversation):
        raise AcceptanceError("MINI_CREATED_WEB_VISIBLE_CHAT_FAILED")

    web_prompt = f"automated cross-client check {nonce}; reply briefly"
    web_message_headers = {
        **web_write,
        "Idempotency-Key": f"acceptance-web-message-{nonce}",
    }
    web_message_body = {
        "content": web_prompt,
        "clientMessageId": f"acceptance-web-client-{nonce}",
    }
    _assert_stream(
        _require(
            api.stream_message(
                "web",
                f"{prefix}/chat/conversations/{mini_conversation}/messages/stream",
                body=web_message_body,
                headers=web_message_headers,
            ),
            200,
            "WEB_CHAT_SEND_FAILED",
        )
    )
    mini_detail = _require(
        api.request("mini", "GET", f"{prefix}/chat/conversations/{mini_conversation}"),
        200,
        "MINI_CREATED_WEB_VISIBLE_CHAT_FAILED",
    )
    mini_message_count = _assert_chat_detail(
        mini_detail,
        conversation_id=mini_conversation,
        expected_prompt=web_prompt,
    )
    _assert_stream(
        _require(
            api.stream_message(
                "web",
                f"{prefix}/chat/conversations/{mini_conversation}/messages/stream",
                body=web_message_body,
                headers=web_message_headers,
            ),
            200,
            "CHAT_IDEMPOTENT_REPLAY_FAILED",
        )
    )
    replay_detail = _require(
        api.request("mini", "GET", f"{prefix}/chat/conversations/{mini_conversation}"),
        200,
        "CHAT_IDEMPOTENT_REPLAY_FAILED",
    )
    if _assert_chat_detail(
        replay_detail,
        conversation_id=mini_conversation,
        expected_prompt=web_prompt,
    ) != mini_message_count:
        raise AcceptanceError("CHAT_IDEMPOTENT_REPLAY_FAILED")

    web_conversation_body = {"title": f"acceptance-web-{nonce}"}
    web_conversation_headers = {
        **web_write,
        "Idempotency-Key": f"acceptance-web-conversation-{nonce}",
    }
    web_conversation = _identifier(
        _require(
            api.request(
                "web",
                "POST",
                f"{prefix}/chat/conversations",
                body=web_conversation_body,
                headers=web_conversation_headers,
            ),
            201,
            "WEB_CHAT_CREATE_FAILED",
        ),
        "WEB_CHAT_CREATE_FAILED",
    )
    web_conversation_replay = _identifier(
        _require(
            api.request(
                "web",
                "POST",
                f"{prefix}/chat/conversations",
                body=web_conversation_body,
                headers=web_conversation_headers,
            ),
            201,
            "CHAT_CREATE_IDEMPOTENT_REPLAY_FAILED",
        ),
        "CHAT_CREATE_IDEMPOTENT_REPLAY_FAILED",
    )
    if web_conversation_replay != web_conversation:
        raise AcceptanceError("CHAT_CREATE_IDEMPOTENT_REPLAY_FAILED")
    mini_conversations = _require(
        api.request("mini", "GET", f"{prefix}/chat/conversations"),
        200,
        "WEB_CREATED_MINI_VISIBLE_CHAT_FAILED",
    )
    if not _listed(mini_conversations, web_conversation):
        raise AcceptanceError("WEB_CREATED_MINI_VISIBLE_CHAT_FAILED")
    mini_prompt = f"automated bearer-to-cookie check {nonce}; reply briefly"
    _assert_stream(
        _require(
            api.stream_message(
                "mini",
                f"{prefix}/chat/conversations/{web_conversation}/messages/stream",
                body={
                    "content": mini_prompt,
                    "clientMessageId": f"acceptance-mini-client-{nonce}",
                },
                headers={"Idempotency-Key": f"acceptance-mini-message-{nonce}"},
            ),
            200,
            "MINI_CHAT_SEND_FAILED",
        )
    )
    web_detail = _require(
        api.request("web", "GET", f"{prefix}/chat/conversations/{web_conversation}"),
        200,
        "WEB_CREATED_MINI_VISIBLE_CHAT_FAILED",
    )
    _assert_chat_detail(
        web_detail,
        conversation_id=web_conversation,
        expected_prompt=mini_prompt,
    )

    other_conversations = _require(
        api.request("other", "GET", f"{prefix}/chat/conversations"),
        200,
        "OWNER_ISOLATION_FAILED",
    )
    if _listed(other_conversations, mini_conversation) or _listed(other_conversations, web_conversation):
        raise AcceptanceError("OWNER_ISOLATION_FAILED")
    for conversation_id in (mini_conversation, web_conversation):
        response = api.request("other", "GET", f"{prefix}/chat/conversations/{conversation_id}")
        if response.status != 404 or _problem_code(response.payload) != "CONVERSATION_NOT_FOUND":
            raise AcceptanceError("OWNER_ISOLATION_FAILED")

    jobs_path = f"{prefix}/simc/jobs"
    mini_scenario = {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 1}
    mini_job_created = _require(
        api.request(
            "mini",
            "POST",
            jobs_path,
            body={"snapshotId": str(seed.ready_snapshot_id), "scenario": mini_scenario},
            headers={"Idempotency-Key": f"acceptance-mini-simc-{nonce}"},
        ),
        202,
        "MINI_SIMC_CREATE_FAILED",
    )
    mini_job = _identifier(mini_job_created, "MINI_SIMC_CREATE_FAILED")
    _assert_job_identity(
        mini_job_created,
        job_id=mini_job,
        snapshot_id=seed.ready_snapshot_id,
        scenario=mini_scenario,
    )
    if not _listed(
        _require(api.request("web", "GET", jobs_path), 200, "MINI_CREATED_WEB_VISIBLE_SIMC_FAILED"),
        mini_job,
    ):
        raise AcceptanceError("MINI_CREATED_WEB_VISIBLE_SIMC_FAILED")
    _poll_job(
        api,
        transport="web",
        path=jobs_path,
        job_id=mini_job,
        snapshot_id=seed.ready_snapshot_id,
        scenario=mini_scenario,
        sleep=sleep,
    )

    web_scenario = {"fightStyle": "Patchwerk", "desiredTargets": 1, "iterations": 2}
    web_job_created = _require(
        api.request(
            "web",
            "POST",
            jobs_path,
            body={"snapshotId": str(seed.ready_snapshot_id), "scenario": web_scenario},
            headers={**web_write, "Idempotency-Key": f"acceptance-web-simc-{nonce}"},
        ),
        202,
        "WEB_SIMC_CREATE_FAILED",
    )
    web_job = _identifier(web_job_created, "WEB_SIMC_CREATE_FAILED")
    _assert_job_identity(
        web_job_created,
        job_id=web_job,
        snapshot_id=seed.ready_snapshot_id,
        scenario=web_scenario,
    )
    if not _listed(
        _require(api.request("mini", "GET", jobs_path), 200, "WEB_CREATED_MINI_VISIBLE_SIMC_FAILED"),
        web_job,
    ):
        raise AcceptanceError("WEB_CREATED_MINI_VISIBLE_SIMC_FAILED")
    _poll_job(
        api,
        transport="mini",
        path=jobs_path,
        job_id=web_job,
        snapshot_id=seed.ready_snapshot_id,
        scenario=web_scenario,
        sleep=sleep,
    )

    other_jobs = _require(
        api.request("other", "GET", jobs_path),
        200,
        "OWNER_ISOLATION_FAILED",
    )
    if _listed(other_jobs, mini_job) or _listed(other_jobs, web_job):
        raise AcceptanceError("OWNER_ISOLATION_FAILED")
    for job_id in (mini_job, web_job):
        response = api.request("other", "GET", f"{jobs_path}/{job_id}")
        if response.status != 404 or _problem_code(response.payload) != "SIMULATION_NOT_FOUND":
            raise AcceptanceError("OWNER_ISOLATION_FAILED")

    _require(
        api.request("web", "POST", f"{prefix}/auth/logout", headers=web_write),
        200,
        "WEB_LOGOUT_FAILED",
    )
    if api.request("web", "GET", f"{prefix}/me").status != 401:
        raise AcceptanceError("LOGOUT_INDEPENDENCE_FAILED")
    if api.request("mini", "GET", f"{prefix}/me").status != 200:
        raise AcceptanceError("LOGOUT_INDEPENDENCE_FAILED")

    evidence = {
        "schemaVersion": 1,
        "status": "automated_candidate_acceptance_passed",
        "branchCommit": expected_commit,
        "webBuildIdentity": web_build_identity,
        "weappBuildIdentity": weapp_build_identity,
        "transportScope": {
            "miniBearer": "public_candidate_api",
            "webCookieCsrf": "public_candidate_api",
            "seededShortLivedAuth": True,
            "migratedReadySnapshot": True,
        },
        "checks": {
            "sharedInternalOwner": True,
            "ticketReplayRejected": True,
            "miniCreatedWebVisibleChat": True,
            "webCreatedMiniVisibleChat": True,
            "chatIdempotentReplay": True,
            "miniCreatedWebVisibleSimc": True,
            "webCreatedMiniVisibleSimc": True,
            "semanticSimcResults": True,
            "logoutIndependent": True,
            "ownerIsolation": True,
        },
        "redactedObjectHashes": {
            "primaryUser": _hash("primary-user", seed.primary_user_id),
            "otherUser": _hash("other-user", seed.other_user_id),
            "sourceSnapshot": _hash("snapshot", seed.ready_snapshot_id),
            "miniCreatedConversation": _hash("conversation", mini_conversation),
            "webCreatedConversation": _hash("conversation", web_conversation),
            "miniCreatedJob": _hash("job", mini_job),
            "webCreatedJob": _hash("job", web_job),
        },
        "realWechatQrAcceptance": "pending",
        "realDeviceAcceptance": "pending",
        "recordedAt": _utc(clock).isoformat().replace("+00:00", "Z"),
    }
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    for secret in (
        str(seed.primary_user_id),
        str(seed.other_user_id),
        str(seed.ready_snapshot_id),
        str(seed.web_login_session_id),
        seed.mini_token,
        seed.other_mini_token,
        seed.browser_verifier,
        csrf,
        mini_conversation,
        web_conversation,
        mini_job,
        web_job,
        web_prompt,
        mini_prompt,
    ):
        if secret and secret in serialized:
            raise AcceptanceError("EVIDENCE_REDACTION_FAILED")
    return evidence


class PostgresAcceptanceSeeder:
    def __init__(self, connection_factory: Callable[[], Any]):
        self._connection_factory = connection_factory

    def seed(self, *, expected_database: str, app_context: str, now: datetime) -> AcceptanceSeed:
        if expected_database != "chickenbro_candidate":
            raise AcceptanceError("CANDIDATE_DATABASE_INVALID")
        if not app_context or len(app_context) > 128 or any(character.isspace() for character in app_context):
            raise AcceptanceError("WECHAT_APP_CONTEXT_INVALID")
        primary_token = secrets.token_urlsafe(32)
        other_token = secrets.token_urlsafe(32)
        browser_verifier = secrets.token_urlsafe(32)
        scene_ticket = secrets.token_urlsafe(16)
        other_user_id = uuid.uuid4()
        web_login_id = uuid.uuid4()
        expires_at = now + timedelta(hours=1)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                row = cursor.fetchone()
                if row is None or str(row[0]) != expected_database:
                    raise AcceptanceError("CANDIDATE_DATABASE_INVALID")
                cursor.execute(
                    """
                    SELECT snapshots.user_id, snapshots.id
                    FROM simc.source_snapshots AS snapshots
                    JOIN identity.users AS users ON users.id = snapshots.user_id
                    WHERE snapshots.readiness = 'READY_FOR_SIMC'
                      AND users.status = 'active'
                      AND lower(snapshots.snapshot_json #>> '{character,classKey}') = %s
                      AND lower(snapshots.snapshot_json #>> '{character,specKey}') = %s
                      AND EXISTS (
                          SELECT 1
                          FROM identity.user_identities AS identities
                          WHERE identities.user_id = snapshots.user_id
                            AND identities.provider = 'wechat_mini'
                            AND identities.app_context = %s
                      )
                    ORDER BY snapshots.fetched_at DESC, snapshots.id DESC
                    LIMIT 1
                    """,
                    ("shaman", "elemental", app_context),
                )
                source = cursor.fetchone()
                if source is None:
                    raise AcceptanceError("MIGRATED_READY_SNAPSHOT_REQUIRED")
                primary_user_id = UUID(str(source[0]))
                snapshot_id = UUID(str(source[1]))
                cursor.execute(
                    """
                    INSERT INTO identity.users (id, display_name, status, created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s)
                    """,
                    (other_user_id, "Candidate isolation account", now, now),
                )
                cursor.execute(
                    """
                    INSERT INTO identity.user_identities (
                        id, user_id, provider, app_context, provider_subject,
                        union_id, profile_json, created_at, updated_at
                    ) VALUES (%s, %s, 'wechat_mini', %s, %s, NULL, '{}'::jsonb, %s, %s)
                    """,
                    (
                        uuid.uuid4(),
                        other_user_id,
                        app_context,
                        f"candidate-isolation-{uuid.uuid4()}",
                        now,
                        now,
                    ),
                )
                metadata = json.dumps(
                    {"purpose": "automated_candidate_acceptance"},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for token, user_id in (
                    (primary_token, primary_user_id),
                    (other_token, other_user_id),
                ):
                    cursor.execute(
                        """
                        INSERT INTO identity.auth_sessions (
                            token_hash, user_id, kind, issued_at, expires_at, metadata_json
                        ) VALUES (%s, %s, 'mini_bearer', %s, %s, %s::jsonb)
                        """,
                        (hashlib.sha256(token.encode()).hexdigest(), user_id, now, expires_at, metadata),
                    )
                cursor.execute(
                    """
                    INSERT INTO identity.web_login_sessions (
                        id, scene_ticket_sha256, browser_verifier_sha256,
                        idempotency_key_sha256, user_id, status, expires_at,
                        consumed_at, created_at, updated_at
                    ) VALUES (%s, %s, %s, NULL, %s, 'confirmed', %s, NULL, %s, %s)
                    """,
                    (
                        web_login_id,
                        hashlib.sha256(scene_ticket.encode()).hexdigest(),
                        hashlib.sha256(browser_verifier.encode()).hexdigest(),
                        primary_user_id,
                        expires_at,
                        now,
                        now,
                    ),
                )
        return AcceptanceSeed(
            primary_user_id=primary_user_id,
            other_user_id=other_user_id,
            ready_snapshot_id=snapshot_id,
            mini_token=primary_token,
            other_mini_token=other_token,
            web_login_session_id=web_login_id,
            browser_verifier=browser_verifier,
        )


class CandidateHttpGateway:
    def __init__(
        self,
        seed: AcceptanceSeed,
        *,
        www_origin: str = WWW_ORIGIN,
        api_origin: str = API_ORIGIN,
        prefix: str = CANDIDATE_PREFIX,
        timeout_seconds: int = 210,
    ):
        if www_origin != WWW_ORIGIN or api_origin != API_ORIGIN or prefix != CANDIDATE_PREFIX:
            raise AcceptanceError("CANDIDATE_ORIGIN_INVALID")
        self._seed = seed
        self._www_origin = www_origin
        self._api_origin = api_origin
        self._prefix = prefix
        self._timeout_seconds = max(1, min(int(timeout_seconds), 300))
        self._cookie_jar = http.cookiejar.CookieJar()
        self._web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._cookie_jar))
        self._plain = urllib.request.build_opener()

    def exchange_web(self, session_id: UUID, browser_verifier: str) -> ApiResponse:
        return self._send(
            self._web,
            "POST",
            self._www_origin + self._prefix + f"/auth/wechat/web/login-sessions/{session_id}/exchange",
            headers={"Origin": self._www_origin, "X-Web-Login-Verifier": browser_verifier},
            body={},
        )

    def replay_web_exchange(self, session_id: UUID, browser_verifier: str) -> ApiResponse:
        return self.exchange_web(session_id, browser_verifier)

    def web_csrf_token(self) -> str:
        values = [cookie.value for cookie in self._cookie_jar if cookie.name == CSRF_COOKIE_NAME]
        if len(values) != 1:
            raise AcceptanceError("WEB_CSRF_COOKIE_INVALID")
        return values[0]

    def _transport(self, transport: str) -> tuple[Any, str, dict[str, str]]:
        if transport == "web":
            return self._web, self._www_origin, {"Origin": self._www_origin}
        if transport == "mini":
            return self._plain, self._api_origin, {"Authorization": f"Bearer {self._seed.mini_token}"}
        if transport == "other":
            return self._plain, self._api_origin, {"Authorization": f"Bearer {self._seed.other_mini_token}"}
        raise AcceptanceError("TRANSPORT_INVALID")

    def request(
        self,
        transport: str,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> ApiResponse:
        opener, origin, auth_headers = self._transport(transport)
        return self._send(
            opener,
            method,
            origin + path,
            headers={**auth_headers, **dict(headers or {})},
            body=body,
        )

    def stream_message(
        self,
        transport: str,
        path: str,
        *,
        body: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> ApiResponse:
        opener, origin, auth_headers = self._transport(transport)
        status, content_type, raw = self._send_raw(
            opener,
            "POST",
            origin + path,
            headers={**auth_headers, **dict(headers)},
            body=body,
        )
        if status != 200:
            return ApiResponse(status, self._json_payload(raw))
        if "text/event-stream" not in content_type:
            raise AcceptanceError("CHAT_STREAM_CONTENT_TYPE_INVALID")
        events: list[Mapping[str, Any]] = []
        try:
            stream_text = raw.decode("utf-8", errors="strict")
        except UnicodeError:
            raise AcceptanceError("CHAT_STREAM_INVALID") from None
        stream_text = stream_text.replace("\r\n", "\n").replace("\r", "\n")
        for frame in stream_text.split("\n\n"):
            data = "\n".join(
                line[5:].lstrip()
                for line in frame.splitlines()
                if line.startswith("data:")
            )
            if not data:
                continue
            try:
                value = json.loads(data)
            except json.JSONDecodeError:
                raise AcceptanceError("CHAT_STREAM_INVALID") from None
            if not isinstance(value, Mapping):
                raise AcceptanceError("CHAT_STREAM_INVALID")
            events.append(value)
        return ApiResponse(status, {"events": events})

    def _send(
        self,
        opener: Any,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None,
    ) -> ApiResponse:
        status, _content_type, raw = self._send_raw(
            opener,
            method,
            url,
            headers=headers,
            body=body,
        )
        return ApiResponse(status, self._json_payload(raw))

    def _send_raw(
        self,
        opener: Any,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: Mapping[str, Any] | None,
    ) -> tuple[int, str, bytes]:
        encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            method=method,
            headers={
                "Accept": "application/json, text/event-stream",
                "User-Agent": "chickenbro-candidate-acceptance/1",
                **({"Content-Type": "application/json"} if encoded is not None else {}),
                **dict(headers),
            },
        )
        try:
            response = opener.open(request, timeout=self._timeout_seconds)
            with response:
                raw = response.read(2_000_001)
                status = int(response.status)
                content_type = str(response.headers.get("Content-Type") or "")
        except urllib.error.HTTPError as error:
            raw = error.read(2_000_001)
            status = int(error.code)
            content_type = str(error.headers.get("Content-Type") or "")
        except (OSError, urllib.error.URLError, TimeoutError):
            raise AcceptanceError("HTTP_TRANSPORT_FAILED") from None
        if len(raw) > 2_000_000:
            raise AcceptanceError("HTTP_RESPONSE_TOO_LARGE")
        return status, content_type, raw

    @staticmethod
    def _json_payload(raw: bytes) -> Mapping[str, Any]:
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            raise AcceptanceError("HTTP_RESPONSE_INVALID") from None
        if not isinstance(value, Mapping):
            raise AcceptanceError("HTTP_RESPONSE_INVALID")
        return value


def _write_evidence(path: Path, payload: Mapping[str, Any]) -> None:
    resolved = path.resolve(strict=False)
    allowed_root = Path("/var/lib/chickenbro").resolve(strict=False)
    if allowed_root not in resolved.parents:
        raise AcceptanceError("EVIDENCE_PATH_INVALID")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(f".{resolved.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
        os.replace(temporary, resolved)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run isolated Chickenbro candidate acceptance")
    parser.add_argument("--expected-database", default="chickenbro_candidate")
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--web-build-identity", required=True)
    parser.add_argument("--weapp-build-identity", required=True)
    parser.add_argument("--evidence-path", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        database_url = os.environ.get("WOW_DATABASE_URL", "").strip()
        app_context = os.environ.get("WOW_WECHAT_APPID", "").strip()
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise AcceptanceError("CANDIDATE_DSN_REQUIRED")
        try:
            import psycopg
        except ImportError:
            raise AcceptanceError("POSTGRES_DRIVER_UNAVAILABLE") from None
        now = datetime.now(timezone.utc)
        seeder = PostgresAcceptanceSeeder(lambda: psycopg.connect(database_url))
        seed = seeder.seed(
            expected_database=args.expected_database,
            app_context=app_context,
            now=now,
        )
        evidence = run_candidate_acceptance(
            seed,
            CandidateHttpGateway(seed),
            expected_commit=args.expected_commit,
            web_build_identity=args.web_build_identity,
            weapp_build_identity=args.weapp_build_identity,
        )
        _write_evidence(Path(args.evidence_path), evidence)
    except AcceptanceError as error:
        print(f"accept_chickenbro_candidate: {error.code}", file=sys.stderr)
        return 1
    except Exception:
        print("accept_chickenbro_candidate: UNEXPECTED_FAILURE", file=sys.stderr)
        return 1
    print(f"status={evidence['status']} evidence={args.evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "AcceptanceError",
    "AcceptanceSeed",
    "ApiResponse",
    "CandidateHttpGateway",
    "PostgresAcceptanceSeeder",
    "run_candidate_acceptance",
)

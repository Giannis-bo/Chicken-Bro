#!/usr/bin/env python3
"""Domain-aware reconciliation for the whitelist legacy migration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from server.migrations.product.migrate_legacy import (
    MigrationReport,
    MigrationTarget,
    content_hash,
    source_snapshot_hash,
)


SIMC_TABLES = (
    "simc.source_snapshots",
    "simc.simulation_jobs",
    "simc.simulation_attempts",
    "simc.simulation_results",
)


@dataclass(frozen=True)
class ReconciliationReport:
    status: str
    source_drift_count: int
    accepted_count_mismatch_count: int
    target_hash_mismatch_count: int
    mapping_missing_count: int
    owner_violation_count: int
    message_order_mismatch_count: int
    simc_semantic_mismatch_count: int
    violation_hash: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sourceDriftCount": self.source_drift_count,
            "acceptedCountMismatchCount": self.accepted_count_mismatch_count,
            "targetHashMismatchCount": self.target_hash_mismatch_count,
            "mappingMissingCount": self.mapping_missing_count,
            "ownerViolationCount": self.owner_violation_count,
            "messageOrderMismatchCount": self.message_order_mismatch_count,
            "simcSemanticMismatchCount": self.simc_semantic_mismatch_count,
            "violationHash": self.violation_hash,
        }


def _row_map(target: MigrationTarget, table: str) -> dict[str, Mapping[str, Any]]:
    return {str(row.get("id") or ""): row for row in target.rows(table)}


def _target_hash_mismatches(
    target: MigrationTarget,
    report: MigrationReport,
) -> tuple[int, int]:
    mismatch = 0
    count_mismatch = 0
    for table, expected in report.expected_target_hashes.items():
        actual = _row_map(target, table)
        found = 0
        for target_id, expected_hash in expected.items():
            row = actual.get(target_id)
            if row is None:
                mismatch += 1
                continue
            found += 1
            if content_hash(row) != expected_hash:
                mismatch += 1
        if found != len(expected):
            count_mismatch += 1
    return mismatch, count_mismatch


def _owner_violations(target: MigrationTarget) -> int:
    users = _row_map(target, "identity.users")
    identities = _row_map(target, "identity.user_identities")
    conversations = _row_map(target, "chat.conversations")
    messages = _row_map(target, "chat.messages")
    runs = _row_map(target, "chat.agent_runs")
    snapshots = _row_map(target, "simc.source_snapshots")
    jobs = _row_map(target, "simc.simulation_jobs")
    attempts = _row_map(target, "simc.simulation_attempts")
    results = _row_map(target, "simc.simulation_results")
    violations = 0

    for row in identities.values():
        violations += int(row.get("user_id") not in users)
    for row in conversations.values():
        violations += int(row.get("user_id") not in users)
    for row in messages.values():
        conversation = conversations.get(str(row.get("conversation_id") or ""))
        violations += int(
            conversation is None
            or row.get("user_id") not in users
            or conversation.get("user_id") != row.get("user_id")
        )
    for row in runs.values():
        conversation = conversations.get(str(row.get("conversation_id") or ""))
        user_message = messages.get(str(row.get("user_message_id") or ""))
        assistant_id = row.get("assistant_message_id")
        assistant_message = messages.get(str(assistant_id)) if assistant_id else None
        invalid = (
            conversation is None
            or user_message is None
            or conversation.get("user_id") != row.get("user_id")
            or user_message.get("user_id") != row.get("user_id")
            or user_message.get("role") != "user"
            or user_message.get("conversation_id") != row.get("conversation_id")
            or (row.get("status") == "succeeded" and assistant_message is None)
            or (assistant_id is not None and (
                assistant_message is None
                or assistant_message.get("user_id") != row.get("user_id")
                or assistant_message.get("role") != "assistant"
                or assistant_message.get("conversation_id") != row.get("conversation_id")
            ))
        )
        violations += int(invalid)
    for row in snapshots.values():
        violations += int(row.get("user_id") not in users)
    for row in jobs.values():
        snapshot = snapshots.get(str(row.get("snapshot_id") or ""))
        violations += int(
            snapshot is None
            or row.get("user_id") not in users
            or snapshot.get("user_id") != row.get("user_id")
        )
    for row in attempts.values():
        job = jobs.get(str(row.get("job_id") or ""))
        violations += int(
            job is None
            or row.get("user_id") not in users
            or job.get("user_id") != row.get("user_id")
        )
    for row in results.values():
        job = jobs.get(str(row.get("job_id") or ""))
        violations += int(
            job is None
            or row.get("user_id") not in users
            or job.get("user_id") != row.get("user_id")
            or job.get("status") != "succeeded"
        )
    return violations


def _message_order_hashes(target: MigrationTarget, report: MigrationReport) -> dict[str, str]:
    expected_ids = set(report.expected_target_hashes.get("chat.messages", {}))
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in target.rows("chat.messages"):
        if row.get("id") not in expected_ids:
            continue
        grouped[str(row.get("conversation_id") or "")].append(row)
    output = {}
    for conversation_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")))
        output[conversation_id] = content_hash([
            {
                "id": row.get("id"),
                "userId": row.get("user_id"),
                "role": row.get("role"),
                "contentHash": content_hash(row.get("content")),
                "createdAt": row.get("created_at"),
            }
            for row in ordered
        ])
    return output


def _simc_semantic_mismatches(target: MigrationTarget, report: MigrationReport) -> int:
    mismatches = 0
    for table in SIMC_TABLES:
        expected = report.expected_target_hashes.get(table, {})
        actual = _row_map(target, table)
        for target_id, expected_hash in expected.items():
            row = actual.get(target_id)
            if row is None or content_hash(row) != expected_hash:
                mismatches += 1

    expected_result_ids = set(report.expected_target_hashes.get("simc.simulation_results", {}))
    for row in target.rows("simc.simulation_results"):
        if row.get("id") not in expected_result_ids:
            continue
        provenance = row.get("provenance_json")
        if (
            row.get("primary_metric_name") not in {"dps", "hps"}
            or not isinstance(row.get("primary_metric_value"), (int, float))
            or row.get("primary_metric_value", 0) <= 0
            or not isinstance(provenance, Mapping)
            or provenance.get("profileSha256") != row.get("profile_sha256")
        ):
            mismatches += 1
    return mismatches


def reconcile(
    source: Iterable[Mapping[str, Any]],
    target: MigrationTarget,
    report: MigrationReport,
) -> ReconciliationReport:
    current_source_hash = source_snapshot_hash(source, report)
    source_drift = int(current_source_hash != report.source_snapshot_hash)
    target_hash_mismatch, count_mismatch = _target_hash_mismatches(target, report)
    mapping_missing = sum(
        1
        for decision in report.decisions
        if decision.status == "accepted" and not target.has_mapping(decision.subject_key)
    )
    owner_violations = _owner_violations(target)
    actual_message_hashes = _message_order_hashes(target, report)
    message_order_mismatches = sum(
        1
        for conversation_id, expected_hash in report.message_order_hashes.items()
        if actual_message_hashes.get(conversation_id) != expected_hash
    )
    simc_mismatches = _simc_semantic_mismatches(target, report)
    violations = {
        "sourceDrift": source_drift,
        "acceptedCountMismatch": count_mismatch,
        "targetHashMismatch": target_hash_mismatch,
        "mappingMissing": mapping_missing,
        "ownerViolation": owner_violations,
        "messageOrderMismatch": message_order_mismatches,
        "simcSemanticMismatch": simc_mismatches,
    }
    return ReconciliationReport(
        status="matched" if not any(violations.values()) else "diverged",
        source_drift_count=source_drift,
        accepted_count_mismatch_count=count_mismatch,
        target_hash_mismatch_count=target_hash_mismatch,
        mapping_missing_count=mapping_missing,
        owner_violation_count=owner_violations,
        message_order_mismatch_count=message_order_mismatches,
        simc_semantic_mismatch_count=simc_mismatches,
        violation_hash=content_hash(violations),
    )


__all__ = ["ReconciliationReport", "reconcile"]

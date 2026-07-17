#!/usr/bin/env python3
"""One-shot, fenced worker for read-only winner attribute rule audits."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import uuid
from typing import Any

try:
    from .attribute_rule_audit import compare_attribute_panel, match_official_profile
    from .attribute_rule_audit_source import AttributeAuditSourceUnavailable, fetch_official_profile
    from .attribute_rule_audit_store import AttributeRuleAuditStore
    from .gear_attribute_engine import calculate_noncombat_attributes
except ImportError:
    from attribute_rule_audit import compare_attribute_panel, match_official_profile
    from attribute_rule_audit_source import AttributeAuditSourceUnavailable, fetch_official_profile
    from attribute_rule_audit_store import AttributeRuleAuditStore
    from gear_attribute_engine import calculate_noncombat_attributes


def _text(value: Any) -> str:
    return str(value or "").strip()


def _max_jobs(value: Any) -> int:
    try:
        return max(1, min(int(value or 1), 3))
    except (TypeError, ValueError, OverflowError):
        return 1


def _stable_effects(value: Any) -> list[dict[str, str]]:
    return [{"effectId": effect_id} for effect_id in value or [] if isinstance(effect_id, str) and effect_id]


def _source_outcome(code: str) -> dict[str, Any]:
    return {"status": "blocked_source_unavailable", "result": {"code": _text(code) or "OFFICIAL_PROFILE_UNAVAILABLE"}}


def _run_one(
    claimed: dict[str, Any],
    *,
    source_fetcher,
    matcher,
    calculator,
    comparator,
) -> dict[str, Any]:
    input_payload = claimed.get("input") if isinstance(claimed.get("input"), dict) else {}
    source_identity = input_payload.get("sourceIdentity") if isinstance(input_payload.get("sourceIdentity"), dict) else {}
    sealed_input = input_payload.get("sealedInput") if isinstance(input_payload.get("sealedInput"), dict) else {}
    rule = input_payload.get("rule") if isinstance(input_payload.get("rule"), dict) else {}
    if not source_identity or not sealed_input or not rule:
        return _source_outcome("ATTRIBUTE_AUDIT_STORED_INPUT_INCOMPLETE")
    try:
        source = source_fetcher(source_identity)
    except AttributeAuditSourceUnavailable as exc:
        return _source_outcome(exc.code)
    except Exception:
        return _source_outcome("OFFICIAL_PROFILE_UNAVAILABLE")
    source = source if isinstance(source, dict) else {}
    profile = source.get("profile") if isinstance(source.get("profile"), dict) else {}
    match = matcher(sealed_input, profile)
    if match.get("status") != "matched":
        return {"status": "inconclusive_input_mismatch", "result": {"match": match}}
    character = sealed_input.get("character") if isinstance(sealed_input.get("character"), dict) else {}
    panel = calculator(
        rule,
        {"raceKey": character.get("raceKey")},
        sealed_input.get("staticAttributes"),
        _stable_effects(sealed_input.get("stableEffects")),
    )
    if not isinstance(panel, dict) or panel.get("status") != "calculated":
        return _source_outcome("ATTRIBUTE_AUDIT_CALCULATOR_UNAVAILABLE")
    observed_panel = source.get("panel") if isinstance(source.get("panel"), dict) else {}
    if not observed_panel:
        return _source_outcome("OFFICIAL_PROFILE_PANEL_UNAVAILABLE")
    comparison = comparator(rule=rule, expected=panel, observed=observed_panel)
    return {
        "status": comparison.get("status") if comparison.get("status") in {"pass", "confirmed_mismatch"} else "confirmed_mismatch",
        "result": {"comparison": comparison},
    }


def run_attribute_rule_audit_worker(
    store: Any,
    *,
    source_fetcher=fetch_official_profile,
    matcher=match_official_profile,
    calculator=calculate_noncombat_attributes,
    comparator=compare_attribute_panel,
    now: str,
    worker_id: str,
    token_factory=None,
    max_jobs: int = 1,
) -> dict[str, Any]:
    """Claim and process a bounded number of durable audits; never runs SimC."""
    token_factory = token_factory or (lambda: uuid.uuid4().hex)
    outcomes: dict[str, int] = {}
    claimed_count = 0
    for _ in range(_max_jobs(max_jobs)):
        token = _text(token_factory())
        claimed = store.claim_next(worker_id=_text(worker_id), lock_token=token, now=_text(now))
        if not isinstance(claimed, dict) or not claimed:
            break
        claimed_count += 1
        outcome = _run_one(
            claimed,
            source_fetcher=source_fetcher,
            matcher=matcher,
            calculator=calculator,
            comparator=comparator,
        )
        status = _text(outcome.get("status"))
        store.finish(
            audit_key=_text(claimed.get("auditKey")),
            lock_token=_text(claimed.get("lockToken") or token),
            outcome=outcome,
            now=_text(now),
        )
        outcomes[status] = outcomes.get(status, 0) + 1
    return {"status": "idle" if not claimed_count else "completed", "claimed": claimed_count, "outcomes": outcomes}


def _run_from_environment() -> dict[str, Any]:
    try:
        from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    except ImportError:
        from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("attribute rule audit worker requires PostgreSQL-only runtime")
    now = datetime.now(timezone.utc).isoformat()
    return run_attribute_rule_audit_worker(
        AttributeRuleAuditStore(lambda: connect_postgres(config.database_url)),
        now=now,
        worker_id=os.environ.get("HOSTNAME") or "systemd-attribute-rule-audit",
        max_jobs=_max_jobs(os.environ.get("WOW_ATTRIBUTE_RULE_AUDIT_MAX_JOBS", "1")),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = _run_from_environment()
    except Exception:
        result = {"status": "failed", "claimed": 0, "outcomes": {"blocked_source_unavailable": 1}}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())

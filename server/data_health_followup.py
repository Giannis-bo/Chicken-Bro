#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from urllib.request import urlopen


DEFAULT_HEALTH_URL = "http://127.0.0.1:8787/api/data/health"
DEFAULT_NEWS_REFRESH_SCRIPT = "/opt/wow-mini-program/server/refresh_cron.sh"

ACTION_COMMANDS = {
    "news_refresh": {
        "kind": "command",
        "command": [DEFAULT_NEWS_REFRESH_SCRIPT],
        "reason": "news refresh has retryable or queued articles",
    },
    "gear_observed_backfill": {
        "kind": "systemd",
        "unit": "wow-gear-observed-backfill.service",
        "reason": "gear catalog is partial and needs observed variant evidence",
    },
    "stat_weights_sync": {
        "kind": "systemd",
        "unit": "wow-stat-weights-sync.service",
        "reason": "stat weights have blocked scenarios",
        "noBlock": True,
    },
    "simc_runtime_update": {
        "kind": "systemd",
        "unit": "wow-simc-runtime-update.service",
        "reason": "SimulationCraft runtime update is available",
        "noBlock": True,
    },
    "talent_graph_recovery": {
        "kind": "systemd",
        "unit": "wow-talent-graph-recovery.service",
        "reason": "operator requested the dedicated SimC-only talent graph recovery",
    },
}

FOLLOWUP_STATE_SCHEMA_REVISION = "data-health-followup-v1"
FOLLOWUP_STATE_KEY = "data_health_followup_v1"
MANUAL_FORCE_ACTION_KEYS = {"talent_graph_recovery"}


def followup_state_store():
    try:
        from .postgres_cache_sync import cache_store_from_env
    except ImportError:
        from postgres_cache_sync import cache_store_from_env
    try:
        return cache_store_from_env()
    except Exception:
        return None


def _text_value(*values):
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _component_details(component):
    details = component.get("details") if isinstance(component, dict) else {}
    return details if isinstance(details, dict) else {}


def _component_refresh_needed(component):
    return bool(_component_details(component).get("refreshNeeded"))


def _catalog_revision(component):
    details = _component_details(component)
    contract = details.get("catalogContract") if isinstance(details.get("catalogContract"), dict) else {}
    return _text_value(
        contract.get("revision"),
        details.get("variantRevision"),
        details.get("itemDatabaseRevision"),
    )


def _stat_weights_revision(component):
    details = _component_details(component)
    entries = [
        ("inputRevision", details.get("inputRevision")),
        ("statWeightsRevision", details.get("statWeightsRevision")),
        ("gearCatalogRevision", details.get("gearCatalogRevision")),
        ("raiderioRevision", details.get("raiderioRevision")),
        ("simcRuntimeRevision", details.get("simcRuntimeRevision")),
    ]
    return "|".join(f"{key}:{text}" for key, value in entries if (text := _text_value(value)))


def _simc_update_revision(component):
    details = _component_details(component)
    candidates = [details]
    for key in ("simcraftVersion", "simcRuntime"):
        value = details.get(key)
        if isinstance(value, dict):
            candidates.append(value)
    gates = details.get("gates") if isinstance(details.get("gates"), dict) else {}
    runtime_gate = gates.get("simcRuntime") if isinstance(gates.get("simcRuntime"), dict) else {}
    candidates.append(runtime_gate)
    for candidate in candidates:
        revision = _text_value(
            candidate.get("targetRevision"),
            candidate.get("latestCommit"),
            candidate.get("latestVersion"),
            candidate.get("version"),
            candidate.get("commit"),
        )
        if revision:
            return revision
    return ""


def _normalized_followup_state(value):
    state = value if isinstance(value, dict) else {}
    actions = state.get("actions") if isinstance(state.get("actions"), dict) else {}
    return {
        "schemaRevision": FOLLOWUP_STATE_SCHEMA_REVISION,
        "actions": {
            str(key): dict(action)
            for key, action in actions.items()
            if isinstance(action, dict) and str(key or "").strip()
        },
    }


def _append_action(actions, key, *, input_revision="", decision="", manual_only=False):
    if any(action.get("key") == key for action in actions):
        return
    action = {"key": key, **ACTION_COMMANDS[key]}
    if input_revision:
        action["inputRevision"] = input_revision
    if decision:
        action["decision"] = decision
    if manual_only:
        action["manualOnly"] = True
    actions.append(action)


def _add_revision_gated_action(
    actions,
    report_only,
    manual_blockers,
    observations,
    state,
    key,
    revision,
    *,
    refresh_needed=False,
):
    action_state = state["actions"].get(key) or {}
    if not revision:
        report_only.append(f"{key}:missing_input_revision")
        manual_blockers.append(f"{key}_input_revision_missing")
        observations.append({"key": key, "decision": "missing_input_revision"})
        return
    last_seen = _text_value(action_state.get("lastSeenRevision"))
    last_attempted = _text_value(action_state.get("lastAttemptedRevision"))
    if not last_seen and not refresh_needed:
        report_only.append(f"{key}:baseline_recorded")
        observations.append({"key": key, "revision": revision, "decision": "baseline_recorded"})
        return
    if revision != last_seen:
        _append_action(actions, key, input_revision=revision, decision="revision_changed")
        observations.append({"key": key, "revision": revision, "decision": "revision_changed"})
        return
    if refresh_needed and revision != last_attempted:
        _append_action(actions, key, input_revision=revision, decision="refresh_requested")
        observations.append({"key": key, "revision": revision, "decision": "refresh_requested"})
        return
    report_only.append(f"{key}:unchanged_revision")
    observations.append({"key": key, "revision": revision, "decision": "unchanged_revision"})


def followup_state_after_plan(prior_state, plan):
    state = _normalized_followup_state(prior_state)
    observations = plan.get("observations") if isinstance(plan, dict) else []
    for observation in observations if isinstance(observations, list) else []:
        if not isinstance(observation, dict):
            continue
        key = _text_value(observation.get("key"))
        if not key:
            continue
        action_state = dict(state["actions"].get(key) or {})
        revision = _text_value(observation.get("revision"))
        decision = _text_value(observation.get("decision"))
        if revision:
            action_state["lastSeenRevision"] = revision
        if decision in {"revision_changed", "refresh_requested", "forced"} and revision:
            action_state["lastAttemptedRevision"] = revision
        if decision:
            action_state["lastDecision"] = decision
            action_state["lastDecisionAt"] = _utc_now()
        if decision in {"baseline_recorded", "missing_input_revision", "unchanged_revision"}:
            action_state["lastReportOnlyReason"] = decision
        elif decision:
            action_state.pop("lastReportOnlyReason", None)
        state["actions"][key] = action_state
    return state


def _components_by_key(health):
    if not isinstance(health, dict):
        return {}
    return {
        str(component.get("key") or "").strip(): component
        for component in (health or {}).get("components") or []
        if isinstance(component, dict)
    }


def _int_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _simc_update_available(component):
    details = component.get("details") if isinstance(component, dict) else {}
    if not isinstance(details, dict):
        return False
    direct = details.get("simcraftVersion") if isinstance(details.get("simcraftVersion"), dict) else {}
    if direct.get("updateAvailable"):
        return True
    gates = details.get("gates") if isinstance(details.get("gates"), dict) else {}
    runtime = gates.get("simcRuntime") if isinstance(gates.get("simcRuntime"), dict) else {}
    if runtime.get("updateAvailable"):
        return True
    simc_runtime = details.get("simcRuntime") if isinstance(details.get("simcRuntime"), dict) else {}
    return bool(simc_runtime.get("updateAvailable"))


def plan_followup_actions(health, *, prior_state=None, force_actions=()):
    if not isinstance(health, dict):
        return {
            "actions": [],
            "manualBlockers": ["data_health_followup_health_payload_invalid"],
            "reportOnly": ["data_health_followup_health_payload_invalid"],
            "observations": [],
        }
    components = _components_by_key(health)
    actions = []
    manual_blockers = []
    report_only = []
    observations = []
    state = _normalized_followup_state(prior_state)
    simc_update_needed = any(
        _simc_update_available(components.get(key) or {}) for key in ("template_simc_bridge", "season_cutover_readiness")
    )

    news = components.get("news") or {}
    news_details = news.get("details") if isinstance(news.get("details"), dict) else {}
    if news.get("status") in {"partial", "stale", "blocked"} and (
        _int_value(news_details.get("retryableCount")) or _int_value(news_details.get("queuedCount"))
    ):
        _append_action(actions, "news_refresh")

    if simc_update_needed:
        simc_component = components.get("template_simc_bridge") or components.get("season_cutover_readiness") or {}
        _add_revision_gated_action(
            actions,
            report_only,
            manual_blockers,
            observations,
            state,
            "simc_runtime_update",
            _simc_update_revision(simc_component),
            refresh_needed=True,
        )
    gear = components.get("gear_catalog") or {}
    if gear.get("status") in {"partial", "stale", "blocked"}:
        _add_revision_gated_action(
            actions,
            report_only,
            manual_blockers,
            observations,
            state,
            "gear_observed_backfill",
            _catalog_revision(gear),
            refresh_needed=_component_refresh_needed(gear),
        )

    stat_weights = components.get("stat_weights") or {}
    stat_details = _component_details(stat_weights)
    if stat_weights.get("status") in {"partial", "stale", "blocked"} and _int_value(stat_details.get("blockedCount")):
        _add_revision_gated_action(
            actions,
            report_only,
            manual_blockers,
            observations,
            state,
            "stat_weights_sync",
            _stat_weights_revision(stat_weights),
            refresh_needed=_component_refresh_needed(stat_weights),
        )

    community = components.get("community_templates") or {}
    community_details = community.get("details") if isinstance(community.get("details"), dict) else {}
    templates = community_details.get("templates") if isinstance(community_details.get("templates"), dict) else {}
    community_blockers = " ".join(str(blocker) for blocker in community.get("blockers") or [])
    if (
        community.get("status") == "partial"
        and "no target slots" in community_blockers.lower()
        and _int_value(templates.get("verified")) >= 80
        and not _int_value(templates.get("blocked"))
    ):
        report_only.append("community_templates_wcl_no_target_slots")

    for key in force_actions:
        if key not in MANUAL_FORCE_ACTION_KEYS:
            manual_blockers.append(f"unknown_force_action:{key}")
            continue
        _append_action(actions, key, decision="forced", manual_only=True)
        observations.append({"key": key, "decision": "forced"})

    return {
        "actions": actions,
        "manualBlockers": manual_blockers,
        "reportOnly": report_only,
        "observations": observations,
    }


def fetch_health(url=DEFAULT_HEALTH_URL, timeout=20):
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _unit_active(unit):
    completed = subprocess.run(["systemctl", "is-active", unit], check=False, capture_output=True, text=True)
    state = (completed.stdout or "").strip()
    return state in {"active", "activating"}


def execute_action(action):
    if action.get("kind") == "systemd":
        unit = action["unit"]
        if _unit_active(unit):
            return {"key": action["key"], "status": "skipped", "reason": f"{unit} is already active"}
        command = ["sudo", "systemctl", "start", unit]
        if action.get("noBlock"):
            command = ["sudo", "systemctl", "--no-block", "start", unit]
        completed = subprocess.run(command, check=False)
        return {"key": action["key"], "status": "ok" if completed.returncode == 0 else "failed", "exitCode": completed.returncode}
    completed = subprocess.run(action["command"], check=False)
    return {"key": action["key"], "status": "ok" if completed.returncode == 0 else "failed", "exitCode": completed.returncode}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Continue safe WOW data-health blockers by triggering existing jobs.")
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force-action", action="append", choices=sorted(MANUAL_FORCE_ACTION_KEYS), default=[])
    args = parser.parse_args(argv)

    health = fetch_health(args.health_url)
    if not isinstance(health, dict):
        plan = plan_followup_actions(health, force_actions=args.force_action)
        payload = {"plan": plan, "results": [], "executed": bool(args.execute)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if args.execute else 0
    store = followup_state_store()
    prior_state = {}
    state_error = ""
    if store is None:
        state_error = "data_health_followup_state_unavailable"
    else:
        try:
            prior_state = store.get_sync_state(FOLLOWUP_STATE_KEY)
        except Exception:
            state_error = "data_health_followup_state_unavailable"
    plan = plan_followup_actions(health, prior_state=prior_state, force_actions=args.force_action)
    if state_error:
        plan["manualBlockers"].append(state_error)
        plan["reportOnly"].append(state_error)
        plan["actions"] = []
    elif args.execute:
        try:
            store.save_sync_state(FOLLOWUP_STATE_KEY, followup_state_after_plan(prior_state, plan))
        except Exception:
            state_error = "data_health_followup_state_unavailable"
            plan["manualBlockers"].append(state_error)
            plan["reportOnly"].append(state_error)
            plan["actions"] = []
    results = []
    if args.execute:
        for action in plan["actions"]:
            results.append(execute_action(action))
    payload = {"plan": plan, "results": results, "executed": bool(args.execute)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if args.execute and (state_error or any(result.get("status") == "failed" for result in results)) else 0


if __name__ == "__main__":
    raise SystemExit(main())

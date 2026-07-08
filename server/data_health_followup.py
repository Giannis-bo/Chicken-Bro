#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
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
    "websim_sync": {
        "kind": "systemd",
        "unit": "wow-websim-sync.service",
        "reason": "websim sync is blocked by gear catalog state and should rebuild after backfill",
        "noBlock": True,
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
}


def _components_by_key(health):
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


def _append_action(actions, key):
    if any(action.get("key") == key for action in actions):
        return
    action = {"key": key, **ACTION_COMMANDS[key]}
    actions.append(action)


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


def plan_followup_actions(health):
    components = _components_by_key(health)
    actions = []
    manual_blockers = []
    report_only = []
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
        _append_action(actions, "simc_runtime_update")
    else:
        gear = components.get("gear_catalog") or {}
        if gear.get("status") in {"partial", "stale", "blocked"}:
            _append_action(actions, "gear_observed_backfill")

        websim = components.get("websim_sync") or {}
        if websim.get("status") in {"partial", "stale", "blocked"}:
            blockers = " ".join(str(blocker) for blocker in websim.get("blockers") or [])
            if "gear catalog" in blockers.lower():
                _append_action(actions, "websim_sync")

        stat_weights = components.get("stat_weights") or {}
        stat_details = stat_weights.get("details") if isinstance(stat_weights.get("details"), dict) else {}
        if stat_weights.get("status") in {"partial", "stale", "blocked"} and _int_value(stat_details.get("blockedCount")):
            _append_action(actions, "stat_weights_sync")

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

    return {
        "actions": actions,
        "manualBlockers": manual_blockers,
        "reportOnly": report_only,
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
    args = parser.parse_args(argv)

    health = fetch_health(args.health_url)
    plan = plan_followup_actions(health)
    results = []
    if args.execute:
        for action in plan["actions"]:
            results.append(execute_action(action))
    payload = {"plan": plan, "results": results, "executed": bool(args.execute)}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if any(result.get("status") == "failed" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

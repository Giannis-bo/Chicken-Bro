import json
import os

try:
    from ..simulator_payload import warcraftlogs_credentials_state
except ImportError:
    from simulator_payload import warcraftlogs_credentials_state


def load_seed_templates():
    raw = os.environ.get("WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON", "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = parsed.get("templates") or []
    return parsed if isinstance(parsed, list) else []


def normalize_wcl_seed_template(template):
    if not isinstance(template, dict):
        return None
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    source_url = str(template.get("sourceUrl") or payload.get("sourceUrl") or "").strip()
    normalized = {
        **template,
        "sourceName": "Warcraft Logs",
        "sourceUrl": source_url,
        "sourceStatus": template.get("sourceStatus") or "partial",
        "status": template.get("status") or "blocked",
        "payload": {
            **payload,
            "warcraftlogs": {
                **(payload.get("warcraftlogs") if isinstance(payload.get("warcraftlogs"), dict) else {}),
                "sourceUrl": source_url,
                "evidenceKind": payload.get("evidenceKind") or "combatantinfo_seed",
            },
        },
    }
    if normalized.get("talentState") or normalized.get("loadout") or normalized.get("rawImportCode"):
        normalized["status"] = template.get("status") or "verified"
    return normalized


def load_templates(conn=None):
    credentials = warcraftlogs_credentials_state()
    if not credentials["configured"]:
        return {
            "status": "missing_credentials",
            "sourceName": "Warcraft Logs",
            "templates": [],
            "errors": [
                "WOW_WARCRAFTLOGS_CLIENT_ID/WOW_WARCRAFTLOGS_CLIENT_SECRET or WOW_WARCRAFTLOGS_API_KEY are not configured"
            ],
        }
    if credentials.get("api") != "warcraftlogs-v2-graphql":
        return {
            "status": "blocked",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": [],
            "errors": ["Warcraft Logs v1 is deprecated; community template extraction requires v2 OAuth/GraphQL."],
        }
    try:
        templates = [
            item
            for item in (normalize_wcl_seed_template(raw) for raw in load_seed_templates())
            if item
        ]
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "blocked",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": [],
            "errors": [f"Warcraft Logs template seed could not be parsed: {error}"],
        }
    if templates:
        return {
            "status": "partial",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": templates,
            "errors": [],
        }
    return {
        "status": "partial",
        "sourceName": "Warcraft Logs",
        "credentialMode": credentials["mode"],
        "api": credentials["api"],
        "templates": [],
        "errors": ["Warcraft Logs v2 credentials are configured, but no combatantinfo template seed/report extraction is available for this sync run."],
    }

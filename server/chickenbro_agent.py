import re
from datetime import datetime, timezone

try:
    from .chickenbro_question_frame import build_chickenbro_question_frame
except ImportError:
    from chickenbro_question_frame import build_chickenbro_question_frame

_RAIDERIO_LIMITATION = (
    "Raider.IO samples may inform Mythic+ trends, but they do not replace WCL combat-log statistics."
)


def classify_chickenbro_request(message, history):
    text = str(message or "").strip()
    frame = build_chickenbro_question_frame(text, history)
    subject = frame["subject"]
    scope = frame["scope"]
    has_wcl_report = frame["questionType"] == "personal_wcl"
    return {
        "kind": frame["questionType"],
        "productPhase": scope["productPhase"],
        "classKey": subject["classKey"],
        "specKey": subject["specKey"],
        "scenarioKey": scope["scenarioKey"],
        "wclReport": "" if not has_wcl_report else text,
        "patchVersion": scope["patchVersion"],
        "evidenceNeeds": list(frame["evidenceNeeds"]),
    }


def _parse_iso_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def raiderio_payload_with_freshness(payload, now=None):
    normalized = dict(payload) if isinstance(payload, dict) else {}
    expires_at = _parse_iso_datetime(normalized.get("expiresAt"))
    current = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= current.astimezone(timezone.utc):
        normalized["sourceStatus"] = "stale"
        normalized["status"] = "stale"
        limitations = [str(item) for item in normalized.get("limitations") or [] if str(item or "").strip()]
        limitation = "Raider.IO source cache expired and cannot be used as current evidence."
        if limitation not in limitations:
            limitations.append(limitation)
        normalized["limitations"] = limitations
    return normalized


def build_raiderio_chickenbro_tool_result(payload, intent):
    payload = raiderio_payload_with_freshness(payload)
    intent = intent if isinstance(intent, dict) else {}
    class_key = str(intent.get("classKey") or "").strip().lower()
    spec_key = str(intent.get("specKey") or "").strip().lower()
    source_status = str(payload.get("sourceStatus") or payload.get("status") or "blocked").strip().lower()
    source_url = str(payload.get("leaderboardUrl") or "https://raider.io/mythic-plus-rankings").strip()
    evidence_ref = f"raiderio:{class_key}:{spec_key}:mythic_plus"
    evidence = {
        "id": evidence_ref,
        "sourceName": str(payload.get("sourceName") or "Raider.IO"),
        "sourceUrl": source_url,
        "productPhase": str(intent.get("productPhase") or "retail"),
        "seasonSlug": str(payload.get("seasonSlug") or ""),
        "region": str(payload.get("region") or ""),
        "checkedAt": str(payload.get("checkedAt") or ""),
        "expiresAt": str(payload.get("expiresAt") or ""),
        "sourceStatus": source_status,
    }
    if source_status not in {"synced", "partial"}:
        stale_limitation = "Raider.IO source cache expired and cannot be used as current evidence." if source_status == "stale" else ""
        return {
            "sourceKey": "raiderio",
            "status": source_status,
            "facts": [],
            "evidence": [evidence],
            "evidenceRefs": [],
            "limitations": [
                item for item in (
                    f"Raider.IO source status is {source_status or 'blocked'}.",
                    stale_limitation,
                    _RAIDERIO_LIMITATION,
                ) if item
            ],
            "nextActions": [],
        }

    aggregate = next(
        (
            item for item in (payload.get("specAggregates") or [])
            if isinstance(item, dict)
            and str(item.get("classKey") or "").lower() == class_key
            and str(item.get("specKey") or "").lower() == spec_key
        ),
        None,
    )
    if not aggregate:
        return {
            "sourceKey": "raiderio",
            "status": "partial",
            "facts": [],
            "evidence": [evidence],
            "evidenceRefs": [],
            "limitations": ["Raider.IO has no matching specialization sample in the current cache.", _RAIDERIO_LIMITATION],
            "nextActions": [],
        }

    templates = []
    allowed_numbers = []
    for template in payload.get("communityTemplates") or []:
        if not isinstance(template, dict):
            continue
        if str(template.get("classKey") or "").lower() != class_key:
            continue
        if str(template.get("specKey") or "").lower() != spec_key:
            continue
        name = str(template.get("name") or "").strip()
        templates.append({
            "name": name,
            "heroKey": str(template.get("heroKey") or "").strip(),
            "scenarioKey": str(template.get("scenarioKey") or "mythic_plus").strip(),
            "sourceUrl": str(template.get("sourceUrl") or source_url).strip(),
            "updatedAt": str(template.get("updatedAt") or evidence["checkedAt"]).strip(),
        })
        for number in re.findall(r"(?<![A-Za-z])\+?\d+(?:\.\d+)?%?", name):
            if number not in allowed_numbers:
                allowed_numbers.append(number)
        if len(templates) >= 2:
            break
    return {
        "sourceKey": "raiderio",
        "status": "source_reference" if source_status == "synced" else "partial",
        "facts": [{
            "classKey": class_key,
            "specKey": spec_key,
            "scenarioKey": "mythic_plus",
            "summary": (
                f"Raider.IO has current Mythic+ samples for "
                f"{aggregate.get('fullName') or f'{spec_key} {class_key}'}"
            ),
            "templates": templates,
        }],
        "evidence": [evidence],
        "evidenceRefs": [evidence_ref],
        "allowedNumbers": allowed_numbers,
        "limitations": [_RAIDERIO_LIMITATION],
        "nextActions": [],
    }


def build_wcl_chickenbro_tool_result(log_evidence):
    log_evidence = log_evidence if isinstance(log_evidence, dict) else {}
    source_status = str(log_evidence.get("sourceStatus") or "blocked").strip().lower()
    evidence_refs = [
        str(ref).strip()
        for ref in (log_evidence.get("evidenceRefs") or [])
        if str(ref).strip()
    ]
    evidence = {
        "sourceName": "Warcraft Logs",
        "sourceUrl": str(log_evidence.get("sourceUrl") or "").strip(),
        "reportCode": str(log_evidence.get("reportCode") or "").strip(),
        "fightId": str(log_evidence.get("fightId") or "").strip(),
        "sourceStatus": source_status,
        "evidenceRefs": evidence_refs,
    }
    if source_status == "verified":
        return {
            "sourceKey": "warcraftlogs",
            "status": "verified",
            "facts": [{
                "reportCode": evidence["reportCode"],
                "fightId": evidence["fightId"],
                "summary": "Warcraft Logs report evidence is available for the selected fight.",
            }],
            "evidence": [evidence],
            "evidenceRefs": evidence_refs,
            "limitations": [
                "Parsed events describe this report; matched samples are still required for ranking or percentile claims."
            ],
            "nextActions": [],
        }
    limitation = {
        "missing_report": "No Warcraft Logs report was provided for personal log analysis.",
        "missing_credentials": "Warcraft Logs credentials are unavailable, so no personal log conclusion can be made.",
        "blocked": "Warcraft Logs evidence could not be fetched, so no personal log conclusion can be made.",
    }.get(source_status, "Warcraft Logs evidence is not ready for a personal log conclusion.")
    return {
        "sourceKey": "warcraftlogs",
        "status": source_status,
        "facts": [],
        "evidence": [evidence],
        "evidenceRefs": [],
        "limitations": [limitation],
        "nextActions": [],
    }

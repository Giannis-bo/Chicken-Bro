import re
from datetime import datetime, timezone

try:
    from .websim_payload import CLASS_LABELS_ZH, SPEC_LABELS, SPEC_LABELS_ZH, WOW_CLASSES
except ImportError:
    from websim_payload import CLASS_LABELS_ZH, SPEC_LABELS, SPEC_LABELS_ZH, WOW_CLASSES


_CLASS_SHORT_ALIASES = {
    "deathknight": ("dk", "死骑"),
    "demonhunter": ("dh",),
    "druid": ("德",),
    "evoker": ("唤魔",),
    "hunter": ("猎",),
    "mage": ("法",),
    "monk": ("武僧",),
    "paladin": ("骑",),
    "priest": ("牧",),
    "rogue": ("贼",),
    "shaman": ("萨",),
    "warlock": ("术",),
    "warrior": ("战",),
}

_SPEC_SHORT_ALIASES = {
    "protection": ("防",),
    "retribution": ("惩戒",),
    "beast_mastery": ("兽王",),
    "marksmanship": ("射击",),
    "brewmaster": ("酒仙",),
    "mistweaver": ("织雾",),
    "windwalker": ("踏风",),
    "discipline": ("戒律",),
    "shadow": ("暗牧",),
    "assassination": ("刺杀",),
    "outlaw": ("狂徒",),
    "subtlety": ("敏锐",),
    "affliction": ("痛苦",),
    "demonology": ("恶魔",),
    "destruction": ("毁灭",),
}


def _normalized_aliases(*values):
    return {
        str(value or "").strip().lower()
        for value in values
        if str(value or "").strip()
    }


def _build_spec_aliases():
    aliases = {}
    spec_pairs = {}
    for klass in WOW_CLASSES:
        class_key = str(klass.get("key") or "").strip().lower()
        if not class_key:
            continue
        class_aliases = _normalized_aliases(
            class_key,
            klass.get("label"),
            CLASS_LABELS_ZH.get(class_key),
            *_CLASS_SHORT_ALIASES.get(class_key, ()),
        )
        for spec_key in klass.get("specs") or []:
            spec_key = str(spec_key or "").strip().lower()
            if not spec_key:
                continue
            spec_pairs.setdefault(spec_key, []).append((class_key, spec_key))
            spec_aliases = _normalized_aliases(
                spec_key,
                spec_key.replace("_", " "),
                SPEC_LABELS.get(spec_key),
                SPEC_LABELS_ZH.get(spec_key),
                *_SPEC_SHORT_ALIASES.get(spec_key, ()),
            )
            for spec_alias in spec_aliases:
                for class_alias in class_aliases:
                    aliases[f"{spec_alias} {class_alias}"] = (class_key, spec_key)
                    aliases[f"{spec_alias}{class_alias}"] = (class_key, spec_key)
    for spec_key, pairs in spec_pairs.items():
        if len(pairs) != 1:
            continue
        class_key, _ = pairs[0]
        for alias in _normalized_aliases(
            spec_key,
            spec_key.replace("_", " "),
            SPEC_LABELS.get(spec_key),
            SPEC_LABELS_ZH.get(spec_key),
            *_SPEC_SHORT_ALIASES.get(spec_key, ()),
        ):
            aliases.setdefault(alias, (class_key, spec_key))
    return dict(sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True))


_SPEC_ALIASES = _build_spec_aliases()

_RAIDERIO_LIMITATION = (
    "Raider.IO samples may inform Mythic+ trends, but they do not replace WCL combat-log statistics."
)


def _intent_from_text(text):
    normalized = str(text or "").strip().lower()
    for alias, pair in _SPEC_ALIASES.items():
        if alias and alias in normalized:
            return pair
    return "", ""


def _recent_user_history(history, limit=6):
    items = []
    for item in history if isinstance(history, (list, tuple)) else []:
        if not isinstance(item, dict) or str(item.get("role") or "") != "user":
            continue
        text = str(item.get("content") or "").strip()
        if text:
            items.append(text)
    return items[-max(1, int(limit or 1)):]


def classify_chickenbro_request(message, history):
    text = str(message or "").strip()
    normalized = text.lower()
    history_texts = _recent_user_history(history)
    history_normalized = "\n".join(history_texts).lower()
    phase_text = normalized or history_normalized
    product_phase = "ptr" if any(marker in phase_text for marker in ("ptr", "测试服", "测试版")) else "retail"
    class_key, spec_key = _intent_from_text(text)
    if not spec_key:
        for historic_message in reversed(history_texts):
            class_key, spec_key = _intent_from_text(historic_message)
            if spec_key:
                break
    has_wcl_report = bool(re.search(r"(?:warcraftlogs\.com/reports/|report/[A-Za-z0-9]+)", normalized))
    return {
        "kind": "personal_wcl" if has_wcl_report else "community_build" if spec_key else "general",
        "productPhase": product_phase,
        "classKey": class_key,
        "specKey": spec_key,
        "scenarioKey": "",
        "wclReport": "" if not has_wcl_report else text,
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

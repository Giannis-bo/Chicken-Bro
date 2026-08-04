"""Pure semantic framing for bounded Chickenbro source planning."""

import re

try:
    from .simulator_payload import SIMC_AGENT_CLASS_REGISTRY
except ImportError:
    from simulator_payload import SIMC_AGENT_CLASS_REGISTRY


_QUESTION_FRAME_REVISION = "chickenbro-question-frame-v1"
_WCL_REPORT_PATTERN = re.compile(r"(?:warcraftlogs\.com/reports/|report/[A-Za-z0-9]+)", re.IGNORECASE)
_PATCH_PATTERN = re.compile(r"(?<!\d)(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)(?!\d)")
_PTR_MARKERS = ("ptr", "测试服", "测试版", "beta", "public test realm")
_RETAIL_MARKERS = ("正式服", "当前版本", "现在版本", "现版本", "retail", "live")
_PTR_NEGATION_PATTERN = re.compile(
    r"(?:不(?:是|需要|用|看)|非|不用|不看).{0,8}(?:ptr|测试服|测试版|beta|public test realm)",
    re.IGNORECASE,
)
_CURRENT_RESEARCH_MARKERS = (
    "强度",
    "最强",
    "排行",
    "排名",
    "tier",
    "表现",
    "改动",
    "调整",
    "buff",
    "nerf",
)
_COMPARATIVE_STRENGTH_MARKERS = ("强度", "最强", "排行", "排名", "tier", "表现")
_CURRENT_CHANGE_MARKERS = ("改动", "调整", "buff", "nerf")
_COMMUNITY_BUILD_MARKERS = ("天赋", "属性", "装备", "配装", "build", "talent", "哪里获取")
_CROSS_SPEC_COMPARISON_PATTERN = re.compile(
    r"(?:全(?:职|专)业|所有职业|跨(?:职|专)业|职业总览).{0,16}(?:dps|排名|排行|强度|tier)"
    r"|(?:dps|排名|排行|强度|tier).{0,16}(?:全(?:职|专)业|所有职业|跨(?:职|专)业|职业总览)",
    re.IGNORECASE,
)
_EVIDENCE_RATIO_FOLLOW_UP_PATTERN = re.compile(r"(?<!\d)\d{1,6}\s*/\s*\d{1,6}(?!\d)")
_EVIDENCE_LEADER_FOLLOW_UP_PATTERN = re.compile(
    r"(?:排(?:名)?\s*第?\s*一|第\s*一(?:名)?\s*(?:是|为)?\s*(?:谁|啥|什么)|(?:谁|啥|什么).*?(?:排(?:名)?\s*第?\s*一|第\s*一(?:名)?))"
)
_SCENARIO_MARKERS = (
    ("mythic_plus", ("大秘境", "mythic+", "mythic +", "m+")),
    ("raid", ("团本", "raid")),
    ("pvp", ("竞技场", "战场", "pvp")),
)

# This is an entity-alias extension for a player-facing taxonomy, not a response
# rule.  New aliases are data additions and never change answer wording or source
# selection policy.
_PLAYER_SPEC_EXTRA_ALIASES = {
    ("paladin", "holy"): ("nq",),
}


def _normalized_text(value):
    return str(value or "").strip().lower()


def _aliases(*values):
    return {
        _normalized_text(value)
        for value in values
        if _normalized_text(value)
    }


def _build_subject_aliases():
    class_aliases = {}
    spec_aliases = {}
    spec_keys = {}
    for class_entry in SIMC_AGENT_CLASS_REGISTRY:
        class_key = _normalized_text(class_entry.get("key"))
        if not class_key:
            continue
        aliases = _aliases(class_key, class_entry.get("label"), *(class_entry.get("aliases") or []))
        class_aliases[class_key] = aliases
        for spec_entry in class_entry.get("specs") or []:
            spec_key = _normalized_text(spec_entry.get("key"))
            if not spec_key:
                continue
            aliases_for_spec = _aliases(
                spec_key,
                spec_key.replace("_", " "),
                spec_entry.get("label"),
                *(spec_entry.get("aliases") or []),
                *_PLAYER_SPEC_EXTRA_ALIASES.get((class_key, spec_key), ()),
            )
            for spec_alias in tuple(aliases_for_spec):
                aliases_for_spec.update(
                    f"{spec_alias} {class_alias}" for class_alias in aliases
                )
                aliases_for_spec.update(
                    f"{spec_alias}{class_alias}" for class_alias in aliases
                )
            spec_aliases[(class_key, spec_key)] = aliases_for_spec
            spec_keys.setdefault(spec_key, []).append((class_key, spec_key))
    return class_aliases, spec_aliases, spec_keys


_CLASS_ALIASES, _SPEC_ALIASES, _SPEC_KEYS = _build_subject_aliases()


def _matches_alias(text, alias):
    if not alias or alias not in text:
        return False
    if alias.isascii() and any(character.isalnum() for character in alias):
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text))
    return True


def _resolve_subject(text):
    text = _normalized_text(text)
    candidates = []
    for (class_key, spec_key), aliases in _SPEC_ALIASES.items():
        for alias in aliases:
            if _matches_alias(text, alias):
                candidates.append((len(alias), class_key, spec_key))
    if candidates:
        _, class_key, spec_key = max(candidates)
        return {"classKey": class_key, "specKey": spec_key, "resolution": "resolved"}

    class_candidates = []
    for class_key, aliases in _CLASS_ALIASES.items():
        for alias in aliases:
            if _matches_alias(text, alias):
                class_candidates.append((len(alias), class_key))
    if class_candidates:
        _, class_key = max(class_candidates)
        return {"classKey": class_key, "specKey": "", "resolution": "partial"}
    return {"classKey": "", "specKey": "", "resolution": "unresolved"}


def _recent_user_history(history, limit=6):
    items = []
    for item in history if isinstance(history, (list, tuple)) else []:
        if not isinstance(item, dict) or str(item.get("role") or "") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if content:
            items.append(content)
    return items[-max(1, int(limit or 1)):]


def _first_patch_version(*texts):
    for text in texts:
        match = _PATCH_PATTERN.search(_normalized_text(text))
        if match:
            return match.group(1)
    return ""


def _explicit_phase(text):
    normalized = _normalized_text(text)
    if not normalized:
        return ""
    # A direct correction such as "不要 PTR" has higher precedence than a
    # positive PTR token.  A generic phrase like "当前版本" does not: players
    # commonly say "PTR 当前版本" and still mean the test realm.
    if _PTR_NEGATION_PATTERN.search(normalized):
        return "retail"
    if any(marker in normalized for marker in _PTR_MARKERS):
        return "ptr"
    if any(marker in normalized for marker in _RETAIL_MARKERS):
        return "retail"
    return ""


def _phase(*texts):
    for text in texts:
        explicit = _explicit_phase(text)
        if explicit:
            return explicit
    return "retail"


def _scenario(*texts):
    for text in texts:
        normalized = _normalized_text(text)
        for scenario_key, markers in _SCENARIO_MARKERS:
            if any(marker in normalized for marker in markers):
                return scenario_key
    return ""


def _comparison_scope(text):
    return "cross_spec" if _CROSS_SPEC_COMPARISON_PATTERN.search(_normalized_text(text)) else "subject"


def _question_type(message, history, subject, product_phase):
    normalized = _normalized_text(message)
    if _WCL_REPORT_PATTERN.search(normalized):
        return "personal_wcl"
    # History can resolve a subject/scope, but it must not silently carry a
    # prior strength question into a new build question.
    has_research_marker = any(marker in normalized for marker in _CURRENT_RESEARCH_MARKERS)
    if has_research_marker or _explicit_phase(normalized) == "ptr":
        return "current_research"
    if _strength_evidence_follow_up(normalized, history):
        return "current_research"
    if any(marker in normalized for marker in _COMMUNITY_BUILD_MARKERS) or subject["resolution"] == "resolved":
        return "community_build"
    return "general"


def chickenbro_strength_evidence_follow_up_kind(message):
    """Return the generic referential target of a current evidence follow-up."""
    normalized = _normalized_text(message)
    if _EVIDENCE_RATIO_FOLLOW_UP_PATTERN.search(normalized):
        return "ratio"
    if _EVIDENCE_LEADER_FOLLOW_UP_PATTERN.search(normalized):
        return "leader"
    return ""


def _strength_evidence_follow_up(message, history):
    """Recognize a bounded reference into an active strength-evidence thread.

    A reference such as a ratio explanation or asking for the leading entry
    is not independently a strength request. It becomes one only when there
    is no explicit build intent and the contiguous bounded prior user turns
    lead back to a current-strength question. A build question is a hard
    boundary, so conversational scope cannot leak across a topic switch.
    """
    normalized = _normalized_text(message)
    if not chickenbro_strength_evidence_follow_up_kind(normalized):
        return False
    if any(marker in normalized for marker in _COMMUNITY_BUILD_MARKERS):
        return False
    if not isinstance(history, (list, tuple)) or not history:
        return False
    for previous in reversed(history):
        previous_text = _normalized_text(previous)
        if any(marker in previous_text for marker in _COMMUNITY_BUILD_MARKERS):
            return False
        if any(marker in previous_text for marker in _CURRENT_RESEARCH_MARKERS):
            return True
        if chickenbro_strength_evidence_follow_up_kind(previous_text):
            continue
        return False
    return False


def _evidence_needs(question_type, product_phase="", patch_version="", message="", history=None):
    if question_type == "personal_wcl":
        return ["personal_log_evidence"]
    if question_type == "community_build":
        return ["community_build_reference"]
    if question_type == "current_research":
        normalized = _normalized_text(message)
        needs = []
        if (
            product_phase == "ptr"
            or patch_version
            or any(marker in normalized for marker in _CURRENT_CHANGE_MARKERS)
        ):
            needs.append("official_current_changes")
        if (
            any(marker in normalized for marker in _COMPARATIVE_STRENGTH_MARKERS)
            or _strength_evidence_follow_up(normalized, history)
        ):
            needs.append("comparative_strength_signal")
        return needs or ["official_current_changes"]
    return []


def build_chickenbro_question_frame(message, history):
    """Return the safe, deterministic planning frame for one player question."""
    text = str(message or "").strip()
    history_texts = _recent_user_history(history)
    comparison_scope = _comparison_scope(text)
    subject = _resolve_subject(text)
    if subject["resolution"] == "unresolved" and comparison_scope != "cross_spec":
        for previous_text in reversed(history_texts):
            subject = _resolve_subject(previous_text)
            if subject["resolution"] != "unresolved":
                break
    explicit_phase = _explicit_phase(text)
    product_phase = _phase(text, *reversed(history_texts))
    patch_version = _first_patch_version(text)
    if not patch_version and explicit_phase != "retail":
        patch_version = _first_patch_version(*reversed(history_texts))
    scenario_key = _scenario(text, *reversed(history_texts))
    question_type = _question_type(text, history_texts, subject, product_phase)
    unresolved = []
    if subject["resolution"] != "resolved" and comparison_scope != "cross_spec":
        unresolved.append("subject")
    if question_type == "current_research" and not scenario_key:
        unresolved.append("scenarioKey")
    return {
        "schemaRevision": _QUESTION_FRAME_REVISION,
        "questionType": question_type,
        "subject": subject,
        "comparisonScope": comparison_scope,
        "scope": {
            "productPhase": product_phase,
            "patchVersion": patch_version,
            "region": "cn",
            "scenarioKey": scenario_key,
        },
        "evidenceNeeds": _evidence_needs(question_type, product_phase, patch_version, text, history_texts),
        "unresolvedFields": unresolved,
    }

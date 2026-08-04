"""Pure, source-bounded evidence planning for Chickenbro current research."""

EVIDENCE_PLAN_SCHEMA_REVISION = "chickenbro-evidence-plan-v1"

_SUPPORTED_SOURCE_STATUSES = {"source_reference", "verified"}
_PARTIAL_SOURCE_STATUSES = {"partial", "stale", "failed", "blocked", "missing_credentials"}


def _text(value):
    return str(value or "").strip().lower()


def _selected_capability_ids(registry_context):
    context = registry_context if isinstance(registry_context, dict) else {}
    output = []
    for value in context.get("selectedCapabilityIds") or []:
        capability_id = str(value or "").strip()
        if capability_id and capability_id not in output:
            output.append(capability_id)
    return output


def _facet_for_evidence_need(evidence_need, frame, comparison_scope):
    scope = frame.get("scope") if isinstance(frame.get("scope"), dict) else {}
    scenario_key = _text(scope.get("scenarioKey"))
    if evidence_need == "official_current_changes":
        key = "official_changes"
        claim_policy = "fact"
    elif comparison_scope == "cross_spec":
        key = "cross_spec_performance"
        claim_policy = "unsupported"
    elif scenario_key == "mythic_plus":
        key = "high_key_trend"
        claim_policy = "bounded_comparison"
    else:
        key = "subject_performance"
        claim_policy = "unsupported"
    return {
        "key": key,
        "evidenceNeed": evidence_need,
        "productPhase": _text(scope.get("productPhase")),
        "scenarioKey": scenario_key,
        "claimPolicy": claim_policy,
        "status": "unavailable",
    }


def _facets_for_frame(frame, comparison_scope):
    if _text(frame.get("questionType")) != "current_research":
        return []
    output = []
    for value in frame.get("evidenceNeeds") or []:
        evidence_need = _text(value)
        if evidence_need not in {"official_current_changes", "comparative_strength_signal"}:
            continue
        facet = _facet_for_evidence_need(evidence_need, frame, comparison_scope)
        if facet["key"] not in {item["key"] for item in output}:
            output.append(facet)
    return output


def _matching_source_keys(facet, comparison_scope):
    if facet["evidenceNeed"] == "official_current_changes":
        return {"current_wow_sources"}
    if comparison_scope == "subject" and facet["key"] == "high_key_trend":
        return {"raiderio_strength"}
    return set()


def _source_status_for_keys(source_evidence, source_keys):
    partial_seen = False
    for source in source_evidence if isinstance(source_evidence, (list, tuple)) else []:
        if not isinstance(source, dict) or _text(source.get("sourceKey")) not in source_keys:
            continue
        status = _text(source.get("status"))
        has_refs = bool(source.get("evidenceRefs"))
        if status in _SUPPORTED_SOURCE_STATUSES and has_refs:
            return "supported"
        if status in _PARTIAL_SOURCE_STATUSES or status:
            partial_seen = True
    return "partial" if partial_seen else "unavailable"


def _mark_facet_statuses(facets, source_evidence, comparison_scope):
    for facet in facets:
        source_keys = _matching_source_keys(facet, comparison_scope)
        facet["status"] = _source_status_for_keys(source_evidence, source_keys)
    return facets


def _unmet_evidence_needs(facets):
    output = []
    for facet in facets:
        evidence_need = facet["evidenceNeed"]
        if facet["status"] != "supported" and evidence_need not in output:
            output.append(evidence_need)
    return output


def _outcome_for(facets):
    if not facets:
        return "partial"
    return "answered" if all(facet["status"] == "supported" for facet in facets) else "partial"


def build_chickenbro_evidence_plan(question_frame, registry_context, source_evidence):
    """Project only scenario-compatible, returned evidence into a generic plan."""
    frame = question_frame if isinstance(question_frame, dict) else {}
    comparison_scope = _text(frame.get("comparisonScope")) or "subject"
    if comparison_scope not in {"subject", "cross_spec"}:
        comparison_scope = "subject"
    facets = _mark_facet_statuses(
        _facets_for_frame(frame, comparison_scope),
        source_evidence,
        comparison_scope,
    )
    return {
        "schemaRevision": EVIDENCE_PLAN_SCHEMA_REVISION,
        "comparisonScope": comparison_scope,
        "facets": facets,
        "selectedCapabilityIds": _selected_capability_ids(registry_context),
        "unmetEvidenceNeeds": _unmet_evidence_needs(facets),
        "outcome": _outcome_for(facets),
        "continuationPolicy": "replan" if comparison_scope == "cross_spec" else "reuse_compatible_only",
    }

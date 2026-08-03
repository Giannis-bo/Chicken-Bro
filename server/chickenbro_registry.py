"""Pure immutable Tool Registry contracts for the Chickenbro runtime."""

import copy
import hashlib
import json
import re
from datetime import datetime


MANIFEST_KEYS = {
    "toolId",
    "version",
    "kind",
    "namespace",
    "purpose",
    "inputSchema",
    "outputSchema",
    "discoveryPolicy",
    "riskClass",
    "sideEffects",
    "ownerPolicy",
    "sourcePolicy",
    "freshnessPolicy",
    "timeoutBudgetMs",
    "costBudget",
    "implementationRef",
    "evalRefs",
    "status",
    "provenance",
    "createdAt",
    "contentHash",
}
DISCOVERY_POLICY_KEYS = {
    "requestKinds",
    "requiredContextFields",
    "productPhases",
    "regions",
    "priority",
}
DISCOVERY_POLICY_OPTIONAL_KEYS = {"evidenceNeeds"}
RELEASE_KEYS = {
    "registryVersion",
    "manifestRefs",
    "releaseHash",
    "status",
    "provenance",
    "createdAt",
    "activatedAt",
    "manifests",
}
MANIFEST_REF_KEYS = {"toolId", "version", "contentHash"}
APPROVED_IMPLEMENTATIONS = {
    "source:raiderio:v1": "chickenbro.source.raiderio.v1",
    "source:warcraftlogs:v1": "chickenbro.source.warcraftlogs.v1",
    "source:current-wow-sources:v1": "chickenbro.source.current_wow_sources.v1",
}
ALLOWED_REQUEST_KINDS = {"community_build", "personal_wcl", "current_research"}
ALLOWED_CONTEXT_FIELDS = {"classKey", "specKey", "wclReport", "questionType", "patchVersion"}
ALLOWED_EVIDENCE_NEEDS = {
    "community_build_reference",
    "comparative_strength_signal",
    "official_current_changes",
    "personal_log_evidence",
}
ALLOWED_PRODUCT_PHASES = {"retail", "ptr"}
ALLOWED_REGIONS = {"cn", "global", "us", "eu", "kr", "tw"}
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
REGISTRY_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,95}$")


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value):
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def manifest_content_hash(manifest):
    payload = dict(manifest) if isinstance(manifest, dict) else {}
    payload.pop("contentHash", None)
    return _sha256(payload)


def registry_release_hash(manifest_refs):
    return _sha256(manifest_refs)


def _timezone_timestamp(value, field_name):
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid {field_name}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"invalid {field_name}")
    return str(value)


def _string_list(value, allowed=None):
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError("invalid manifest list")
    if len(value) != len(set(value)):
        raise ValueError("duplicate manifest list value")
    if allowed is not None and any(item not in allowed for item in value):
        raise ValueError("invalid manifest list value")
    return list(value)


def validate_chickenbro_tool_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("invalid chickenbro tool manifest")
    unknown_keys = set(manifest) - MANIFEST_KEYS
    if unknown_keys or set(manifest) != MANIFEST_KEYS:
        raise ValueError("unknown manifest keys or missing manifest keys")
    tool_id = str(manifest.get("toolId") or "")
    implementation_ref = str(manifest.get("implementationRef") or "")
    if tool_id not in APPROVED_IMPLEMENTATIONS:
        raise ValueError("unapproved manifest toolId")
    if implementation_ref != APPROVED_IMPLEMENTATIONS[tool_id]:
        raise ValueError("unapproved manifest implementationRef")
    if not VERSION_PATTERN.fullmatch(str(manifest.get("version") or "")):
        raise ValueError("invalid manifest version")
    if manifest.get("kind") != "tool" or manifest.get("namespace") != "source":
        raise ValueError("invalid manifest kind or namespace")
    if not isinstance(manifest.get("purpose"), str) or not manifest["purpose"].strip():
        raise ValueError("invalid manifest purpose")
    if not isinstance(manifest.get("inputSchema"), dict) or not isinstance(manifest.get("outputSchema"), dict):
        raise ValueError("invalid manifest schema")
    policy = manifest.get("discoveryPolicy")
    if (
        not isinstance(policy, dict)
        or not DISCOVERY_POLICY_KEYS.issubset(policy)
        or set(policy) - DISCOVERY_POLICY_KEYS - DISCOVERY_POLICY_OPTIONAL_KEYS
    ):
        raise ValueError("invalid manifest discoveryPolicy")
    _string_list(policy["requestKinds"], ALLOWED_REQUEST_KINDS)
    _string_list(policy["requiredContextFields"], ALLOWED_CONTEXT_FIELDS)
    _string_list(policy["productPhases"], ALLOWED_PRODUCT_PHASES)
    _string_list(policy["regions"], ALLOWED_REGIONS)
    if "evidenceNeeds" in policy:
        _string_list(policy["evidenceNeeds"], ALLOWED_EVIDENCE_NEEDS)
    if not isinstance(policy["priority"], int) or isinstance(policy["priority"], bool):
        raise ValueError("invalid manifest priority")
    if manifest.get("riskClass") != "read_only" or manifest.get("sideEffects") != []:
        raise ValueError("invalid manifest risk or sideEffects")
    if manifest.get("ownerPolicy") not in {"public_source", "owner_bound_report"}:
        raise ValueError("invalid manifest ownerPolicy")
    if not isinstance(manifest.get("sourcePolicy"), dict) or not isinstance(manifest.get("freshnessPolicy"), dict):
        raise ValueError("invalid manifest source or freshness policy")
    timeout = manifest.get("timeoutBudgetMs")
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("invalid manifest timeoutBudgetMs")
    if not isinstance(manifest.get("costBudget"), dict):
        raise ValueError("invalid manifest costBudget")
    _string_list(manifest.get("evalRefs"))
    if manifest.get("status") not in {"active", "disabled"}:
        raise ValueError("invalid manifest status")
    if not isinstance(manifest.get("provenance"), dict):
        raise ValueError("invalid manifest provenance")
    _timezone_timestamp(manifest.get("createdAt"), "manifest createdAt")
    content_hash = str(manifest.get("contentHash") or "")
    if not HASH_PATTERN.fullmatch(content_hash) or content_hash != manifest_content_hash(manifest):
        raise ValueError("invalid manifest contentHash")
    return copy.deepcopy(manifest)


def validate_chickenbro_registry_release(release):
    if not isinstance(release, dict) or set(release) != RELEASE_KEYS:
        raise ValueError("invalid chickenbro registry release keys")
    registry_version = str(release.get("registryVersion") or "")
    if not REGISTRY_VERSION_PATTERN.fullmatch(registry_version):
        raise ValueError("invalid registryVersion")
    if release.get("status") != "active":
        raise ValueError("invalid active registry release status")
    if not isinstance(release.get("provenance"), dict):
        raise ValueError("invalid registry release provenance")
    _timezone_timestamp(release.get("createdAt"), "registry createdAt")
    _timezone_timestamp(release.get("activatedAt"), "registry activatedAt")
    refs = release.get("manifestRefs")
    manifests = release.get("manifests")
    if not isinstance(refs, list) or not refs or not isinstance(manifests, list):
        raise ValueError("invalid registry manifest refs")
    if len(refs) != len(manifests):
        raise ValueError("registry manifest reference count mismatch")
    ref_tool_ids = [
        ref.get("toolId")
        for ref in refs
        if isinstance(ref, dict) and set(ref) == MANIFEST_REF_KEYS
    ]
    if len(ref_tool_ids) == len(refs) and len(ref_tool_ids) != len(set(ref_tool_ids)):
        raise ValueError("duplicate registry manifest toolId")
    tool_ids = []
    validated_manifests = []
    for index, (ref, manifest) in enumerate(zip(refs, manifests)):
        if not isinstance(ref, dict) or set(ref) != MANIFEST_REF_KEYS:
            raise ValueError("invalid registry manifest ref")
        validated = validate_chickenbro_tool_manifest(manifest)
        if validated["status"] != "active":
            raise ValueError("registry release requires active manifest")
        expected_ref = {
            "toolId": validated["toolId"],
            "version": validated["version"],
            "contentHash": validated["contentHash"],
        }
        if ref != expected_ref:
            raise ValueError(f"registry manifest ref mismatch at {index}")
        tool_ids.append(validated["toolId"])
        validated_manifests.append(validated)
    if len(tool_ids) != len(set(tool_ids)):
        raise ValueError("duplicate registry manifest toolId")
    release_hash = str(release.get("releaseHash") or "")
    if not HASH_PATTERN.fullmatch(release_hash) or release_hash != registry_release_hash(refs):
        raise ValueError("invalid registry releaseHash")
    return {
        **copy.deepcopy(release),
        "manifestRefs": copy.deepcopy(refs),
        "manifests": validated_manifests,
    }


def _context_value(field, intent, context):
    if field == "wclReport":
        return str(intent.get(field) or "").strip()
    return str(context.get(field) or intent.get(field) or "").strip().lower()


def discover_chickenbro_capabilities(release, request_intent, request_context):
    validated = validate_chickenbro_registry_release(release)
    intent = request_intent if isinstance(request_intent, dict) else {}
    context = request_context if isinstance(request_context, dict) else {}
    request_kind = str(intent.get("kind") or "").strip().lower()
    product_phase = str(intent.get("productPhase") or context.get("productPhase") or "").strip().lower()
    region = str(context.get("region") or "").strip().lower()
    candidates = []
    missing_fields = []
    for manifest in validated["manifests"]:
        policy = manifest["discoveryPolicy"]
        if request_kind not in policy["requestKinds"]:
            continue
        required_evidence = set(policy.get("evidenceNeeds") or [])
        supplied_evidence = {
            str(item).strip()
            for item in (intent.get("evidenceNeeds") or [])
            if str(item).strip()
        }
        if required_evidence and not required_evidence.issubset(supplied_evidence):
            continue
        required_missing = [
            field
            for field in policy["requiredContextFields"]
            if not _context_value(field, intent, context)
        ]
        for field in required_missing:
            if field not in missing_fields:
                missing_fields.append(field)
        if required_missing:
            continue
        if product_phase not in policy["productPhases"] or region not in policy["regions"]:
            continue
        candidates.append(manifest)
    candidates.sort(key=lambda item: (-item["discoveryPolicy"]["priority"], item["toolId"]))
    capability_ids = [item["toolId"] for item in candidates]
    return {
        "registryVersion": validated["registryVersion"],
        "registryReleaseHash": validated["releaseHash"],
        "discoveredCapabilityIds": capability_ids,
        "selectedCapabilityIds": list(capability_ids),
        "selectedManifests": copy.deepcopy(candidates),
        "missingContextFields": missing_fields,
    }

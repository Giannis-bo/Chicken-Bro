"""Verified Tool Registry caching and explicit adapter dispatch for Chickenbro."""

import copy
from datetime import datetime, timezone
from threading import RLock

try:
    from .chickenbro_registry import (
        APPROVED_IMPLEMENTATIONS,
        discover_chickenbro_capabilities,
        validate_chickenbro_registry_release,
    )
except ImportError:  # pragma: no cover - direct server module execution
    from chickenbro_registry import (
        APPROVED_IMPLEMENTATIONS,
        discover_chickenbro_capabilities,
        validate_chickenbro_registry_release,
    )


_REQUEST_INTENT_FIELDS = {"kind", "productPhase", "classKey", "specKey", "wclReport"}
_REQUEST_CONTEXT_FIELDS = {"region", "productPhase", "classKey", "specKey"}
_TOOL_RESULT_FIELDS = {
    "sourceKey",
    "status",
    "facts",
    "evidence",
    "evidenceRefs",
    "limitations",
    "nextActions",
}


class RegistryUnavailable(RuntimeError):
    """The Registry cannot be loaded and no verified cache is usable."""


class RegistryInvalid(RuntimeError):
    """The loaded Registry or selected adapter binding is invalid."""


def _utc_now(value=None):
    current = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("registry clock must be timezone-aware")
    return current.astimezone(timezone.utc)


class ChickenbroRegistryRuntime:
    def __init__(self, cache_ttl_seconds=60):
        ttl = int(cache_ttl_seconds)
        if ttl <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self.cache_ttl_seconds = ttl
        self._lock = RLock()
        self._verified_release = None
        self._verified_at = None

    def _cached_release(self, now):
        with self._lock:
            if self._verified_release is None or self._verified_at is None:
                return None
            age_seconds = (now - self._verified_at).total_seconds()
            if age_seconds < 0 or age_seconds > self.cache_ttl_seconds:
                return None
            return copy.deepcopy(self._verified_release)

    def _replace_cache(self, release, now):
        with self._lock:
            self._verified_release = copy.deepcopy(release)
            self._verified_at = now

    def _clear_cache(self):
        with self._lock:
            self._verified_release = None
            self._verified_at = None

    def resolve(self, loader, request_intent, request_context, now=None):
        current = _utc_now(now)
        try:
            loaded = loader()
        except Exception as error:
            cached = self._cached_release(current)
            if cached is None:
                raise RegistryUnavailable("chickenbro tool registry unavailable") from error
            release = cached
            source = "verified_cache"
        else:
            try:
                release = validate_chickenbro_registry_release(loaded)
            except (TypeError, ValueError) as error:
                self._clear_cache()
                raise RegistryInvalid("chickenbro tool registry invalid") from error
            self._replace_cache(release, current)
            source = "postgres"
        try:
            resolution = discover_chickenbro_capabilities(
                release,
                request_intent,
                request_context,
            )
        except (TypeError, ValueError) as error:
            self._clear_cache()
            raise RegistryInvalid("chickenbro tool registry invalid") from error
        return {
            **resolution,
            "registrySource": source,
            "registryStatus": "verified",
        }


def _sanitized_request(request):
    request = request if isinstance(request, dict) else {}
    raw_intent = request.get("intent") if isinstance(request.get("intent"), dict) else {}
    raw_context = request.get("context") if isinstance(request.get("context"), dict) else {}
    return {
        "message": str(request.get("message") or ""),
        "intent": copy.deepcopy(
            {key: raw_intent[key] for key in _REQUEST_INTENT_FIELDS if key in raw_intent}
        ),
        "context": copy.deepcopy(
            {key: raw_context[key] for key in _REQUEST_CONTEXT_FIELDS if key in raw_context}
        ),
    }


def _failed_tool_result(manifest, reason):
    source_policy = manifest.get("sourcePolicy") if isinstance(manifest, dict) else {}
    source_key = str((source_policy or {}).get("sourceKey") or "registry").strip() or "registry"
    return {
        "sourceKey": source_key,
        "status": "failed",
        "facts": [],
        "evidence": [],
        "evidenceRefs": [],
        "limitations": [str(reason or "tool adapter failed")[:160]],
        "nextActions": [],
    }


def _validated_tool_result(result, manifest):
    if not isinstance(result, dict) or any(field not in result for field in _TOOL_RESULT_FIELDS):
        return None
    source_policy = manifest.get("sourcePolicy") if isinstance(manifest, dict) else {}
    expected_source = str((source_policy or {}).get("sourceKey") or "").strip()
    if not isinstance(result.get("sourceKey"), str) or result["sourceKey"] != expected_source:
        return None
    if not isinstance(result.get("status"), str) or not result["status"].strip():
        return None
    if any(not isinstance(result.get(field), list) for field in _TOOL_RESULT_FIELDS - {"sourceKey", "status"}):
        return None
    return copy.deepcopy(result)


def execute_chickenbro_selected_tools(resolution, adapter_bindings, request):
    resolution = resolution if isinstance(resolution, dict) else {}
    manifests = resolution.get("selectedManifests")
    bindings = adapter_bindings if isinstance(adapter_bindings, dict) else {}
    if not isinstance(manifests, list):
        raise RegistryInvalid("invalid selected tool manifests")

    adapters = []
    for manifest in manifests:
        if not isinstance(manifest, dict):
            raise RegistryInvalid("invalid selected tool manifest")
        tool_id = str(manifest.get("toolId") or "")
        implementation_ref = str(manifest.get("implementationRef") or "")
        if APPROVED_IMPLEMENTATIONS.get(tool_id) != implementation_ref:
            raise RegistryInvalid("unapproved tool adapter")
        adapter = bindings.get(implementation_ref)
        if not callable(adapter):
            raise RegistryInvalid("missing tool adapter")
        adapters.append((manifest, adapter))

    sanitized = _sanitized_request(request)
    results = []
    for manifest, adapter in adapters:
        try:
            result = adapter(copy.deepcopy(sanitized))
        except Exception as error:
            results.append(
                _failed_tool_result(
                    manifest,
                    f"{manifest['toolId']} adapter failed: {type(error).__name__}",
                )
            )
            continue
        validated = _validated_tool_result(result, manifest)
        if validated is None:
            validated = _failed_tool_result(manifest, f"{manifest['toolId']} adapter returned an invalid result")
        results.append(validated)
    return results

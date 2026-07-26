#!/usr/bin/env python3
"""Pure, replayable parsers for immutable gear evidence Artifacts.

Observers consume only the supplied Artifact.  They never collect a source,
read the clock, or decide whether an accepted Observation becomes a verified
Canonical Fact.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

try:
    from .gear_evidence_registry import (
        EVIDENCE_ARTIFACT_SCHEMA_REVISION,
        build_evidence_observation,
    )
except ImportError:  # pragma: no cover - direct script/module compatibility
    from gear_evidence_registry import (  # type: ignore
        EVIDENCE_ARTIFACT_SCHEMA_REVISION,
        build_evidence_observation,
    )


BATTLE_NET_ITEM_PARSER_REVISION = "battle-net-item-observer-v1"
SIMC_ITEM_PROBE_PARSER_REVISION = "simc-item-probe-observer-v1"
SIMC_BONUS_PROBE_PARSER_REVISION = "simc-bonus-probe-observer-v1"
SEASON_RULE_PARSER_REVISION = "season-rule-observer-v1"

_SUPPORTED_FACT_TYPES = frozenset(
    {
        "item_identity",
        "slot_compatibility",
        "variant_track",
        "static_stats",
        "socket_count",
        "enchant_capability",
        "embellishment_capability",
        "enhancement_option",
        "allowed_enhancement_options",
        "item_set_membership",
    }
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_identifier(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    text = _text(value)
    return str(int(text)) if text.isdigit() and int(text) > 0 else ""


def _canonical_subject(item_id: str, variant_key: str = "") -> str:
    subject = f"item:{item_id}"
    return f"{subject}/variant:{variant_key}" if variant_key else subject


def _diagnostic(code: str, path: str, detail: str) -> dict[str, str]:
    return {"code": code, "path": path, "detail": detail}


def _result(
    artifact: Mapping[str, Any],
    parser_revision: str,
    observations: Iterable[dict[str, Any]] = (),
    diagnostics: Iterable[dict[str, str]] = (),
) -> dict[str, Any]:
    normalized_observations = sorted(
        observations,
        key=lambda row: (
            row["subjectKey"],
            row["factType"],
            row["sourceScope"],
            row["observationId"],
        ),
    )
    normalized_diagnostics = sorted(
        diagnostics,
        key=lambda row: (row["code"], row["path"], row["detail"]),
    )
    return {
        "artifactId": _text(artifact.get("artifactId")),
        "sourceType": _text(artifact.get("sourceType")),
        "parserRevision": _text(parser_revision),
        "status": "accepted" if normalized_observations else "rejected",
        "observations": normalized_observations,
        "diagnostics": normalized_diagnostics,
    }


def _artifact_payload(
    artifact: Any,
    expected_source_type: str,
    parser_revision: str,
) -> tuple[Mapping[str, Any] | None, dict[str, Any] | None]:
    row = artifact if isinstance(artifact, Mapping) else {}
    diagnostics: list[dict[str, str]] = []
    if row.get("schemaRevision") != EVIDENCE_ARTIFACT_SCHEMA_REVISION:
        diagnostics.append(
            _diagnostic(
                "parser_unhandled_shape",
                "schemaRevision",
                "Artifact schema revision is unsupported.",
            )
        )
    if _text(row.get("sourceType")) != expected_source_type:
        diagnostics.append(
            _diagnostic(
                "parser_source_type_mismatch",
                "sourceType",
                f"Expected sourceType {expected_source_type}.",
            )
        )
    if not _text(row.get("artifactId")):
        diagnostics.append(
            _diagnostic(
                "parser_unhandled_shape",
                "artifactId",
                "Artifact identity is required.",
            )
        )
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        diagnostics.append(
            _diagnostic(
                "parser_unhandled_shape",
                "payload",
                "Artifact payload must be an object.",
            )
        )
    if diagnostics:
        return None, _result(row, parser_revision, diagnostics=diagnostics)
    return payload, None


def _observation(
    artifact: Mapping[str, Any],
    parser_revision: str,
    subject_key: str,
    fact_type: str,
    value: Any,
    source_scope: str,
) -> dict[str, Any]:
    return build_evidence_observation(
        artifact_id=artifact["artifactId"],
        subject_key=subject_key,
        fact_type=fact_type,
        observed_value=value,
        parser_revision=parser_revision,
        source_scope=source_scope,
        status="accepted",
    )


def _explicit_socket_count(
    payload: Mapping[str, Any],
) -> tuple[bool, int | None]:
    if "socketCount" in payload:
        value = payload.get("socketCount")
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
        ):
            return True, value
        return True, None
    if "sockets" in payload:
        if isinstance(payload.get("sockets"), (list, tuple)):
            return True, len(payload["sockets"])
        return True, None
    return False, None


def observe_battle_net_item(
    artifact: Any,
    *,
    parser_revision: str = BATTLE_NET_ITEM_PARSER_REVISION,
) -> dict[str, Any]:
    """Replay one stored Battle.net item Artifact into explicit observations."""

    payload, failure = _artifact_payload(
        artifact, "battle_net_item", parser_revision
    )
    if failure:
        return failure
    assert payload is not None
    row = artifact if isinstance(artifact, Mapping) else {}
    item_id = _positive_identifier(payload.get("itemId"))
    if not item_id:
        return _result(
            row,
            parser_revision,
            diagnostics=[
                _diagnostic(
                    "parser_unhandled_shape",
                    "payload.itemId",
                    "A positive structured itemId is required.",
                )
            ],
        )
    variant_key = _text(payload.get("variantKey"))
    subject_key = _canonical_subject(item_id, variant_key)
    source_scope = "exact_variant" if variant_key else "base_item"
    observations: list[dict[str, Any]] = [
        _observation(
            row,
            parser_revision,
            subject_key,
            "item_identity",
            {
                "itemId": item_id,
                **({"variantKey": variant_key} if variant_key else {}),
            },
            source_scope,
        )
    ]

    diagnostics: list[dict[str, str]] = []
    field_specs = (
        ("allowedSlots", "slot_compatibility"),
        ("canEnchant", "enchant_capability"),
        ("canEmbellish", "embellishment_capability"),
        ("allowedEnhancementOptions", "allowed_enhancement_options"),
    )
    for payload_field, fact_type in field_specs:
        if payload_field in payload:
            observations.append(
                _observation(
                    row,
                    parser_revision,
                    subject_key,
                    fact_type,
                    payload[payload_field],
                    source_scope,
                )
            )

    track = payload.get("track")
    item_level = payload.get("itemLevel")
    if track is not None or item_level is not None:
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                "variant_track",
                {
                    **({"track": track} if track is not None else {}),
                    **({"itemLevel": item_level} if item_level is not None else {}),
                },
                source_scope,
            )
        )

    socket_is_explicit, socket_count = _explicit_socket_count(payload)
    if socket_is_explicit and socket_count is not None:
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                "socket_count",
                socket_count,
                source_scope,
            )
        )
    elif socket_is_explicit:
        diagnostics.append(
            _diagnostic(
                "parser_unhandled_shape",
                (
                    "payload.socketCount"
                    if "socketCount" in payload
                    else "payload.sockets"
                ),
                "Socket capacity must be an explicit non-negative integer or array.",
            )
        )

    if "setId" in payload:
        set_id = payload.get("setId")
        set_value: Any = (
            f"set:{_positive_identifier(set_id)}"
            if _positive_identifier(set_id)
            else False
        )
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                "item_set_membership",
                set_value,
                source_scope,
            )
        )

    for option in payload.get("enhancementOptions", ()):
        if not isinstance(option, Mapping) or not _text(option.get("optionId")):
            continue
        observations.append(
            _observation(
                row,
                parser_revision,
                f"option:{_text(option['optionId'])}",
                "enhancement_option",
                dict(option),
                "option",
            )
        )
    return _result(
        row,
        parser_revision,
        observations=observations,
        diagnostics=diagnostics,
    )


def observe_simc_item_probe(
    artifact: Any,
    *,
    parser_revision: str = SIMC_ITEM_PROBE_PARSER_REVISION,
) -> dict[str, Any]:
    """Replay one bounded SimC exact-item or exact-variant probe."""

    payload, failure = _artifact_payload(
        artifact, "simc_item_probe", parser_revision
    )
    if failure:
        return failure
    assert payload is not None
    row = artifact if isinstance(artifact, Mapping) else {}
    item_id = _positive_identifier(payload.get("itemId"))
    if not item_id:
        return _result(
            row,
            parser_revision,
            diagnostics=[
                _diagnostic(
                    "parser_unhandled_shape",
                    "payload.itemId",
                    "A positive exact probe itemId is required.",
                )
            ],
        )
    variant_key = _text(payload.get("variantKey"))
    subject_key = _canonical_subject(item_id, variant_key)
    source_scope = "exact_variant" if variant_key else "exact_item"
    observations: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    socket_is_explicit, socket_count = _explicit_socket_count(payload)
    if socket_is_explicit and socket_count is not None:
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                "socket_count",
                socket_count,
                source_scope,
            )
        )
    elif socket_is_explicit:
        diagnostics.append(
            _diagnostic(
                "parser_unhandled_shape",
                (
                    "payload.socketCount"
                    if "socketCount" in payload
                    else "payload.sockets"
                ),
                "Socket capacity must be an explicit non-negative integer or array.",
            )
        )
    if isinstance(payload.get("staticStats"), Mapping):
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                "static_stats",
                payload["staticStats"],
                source_scope,
            )
        )
    if (
        payload.get("track") is not None
        or payload.get("itemLevel") is not None
    ):
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                "variant_track",
                {
                    **(
                        {"track": payload["track"]}
                        if payload.get("track") is not None
                        else {}
                    ),
                    **(
                        {"itemLevel": payload["itemLevel"]}
                        if payload.get("itemLevel") is not None
                        else {}
                    ),
                },
                source_scope,
            )
        )
    if not observations and not diagnostics:
        return _result(
            row,
            parser_revision,
            diagnostics=[
                _diagnostic(
                    "parser_unhandled_shape",
                    "payload",
                    "The exact probe contains no supported static fact.",
                )
            ],
        )
    return _result(
        row,
        parser_revision,
        observations=observations,
        diagnostics=diagnostics,
    )


def observe_simc_bonus_probe(
    artifact: Any,
    *,
    parser_revision: str = SIMC_BONUS_PROBE_PARSER_REVISION,
) -> dict[str, Any]:
    """Replay one SimC bonus probe with an explicit bounded subject."""

    payload, failure = _artifact_payload(
        artifact, "simc_bonus_probe", parser_revision
    )
    if failure:
        return failure
    assert payload is not None
    row = artifact if isinstance(artifact, Mapping) else {}
    subject_key = _text(payload.get("subjectKey"))
    fact_type = _text(payload.get("factType") or "socket_count")
    socket_is_explicit, socket_count = _explicit_socket_count(payload)
    if (
        not subject_key
        or fact_type != "socket_count"
        or not socket_is_explicit
        or socket_count is None
        or not _positive_identifier(payload.get("bonusId"))
    ):
        return _result(
            row,
            parser_revision,
            diagnostics=[
                _diagnostic(
                    "parser_unhandled_shape",
                    "payload",
                    "A bounded bonusId, subjectKey, and socketCount are required.",
                )
            ],
        )
    return _result(
        row,
        parser_revision,
        observations=[
            _observation(
                row,
                parser_revision,
                subject_key,
                "socket_count",
                socket_count,
                "exact_variant",
            )
        ],
    )


def observe_season_rule(
    artifact: Any,
    *,
    parser_revision: str = SEASON_RULE_PARSER_REVISION,
) -> dict[str, Any]:
    """Replay governed, explicitly scoped season-rule declarations."""

    payload, failure = _artifact_payload(artifact, "season_rule", parser_revision)
    if failure:
        return failure
    assert payload is not None
    row = artifact if isinstance(artifact, Mapping) else {}
    rules = payload.get("rules")
    if not isinstance(rules, (list, tuple)):
        rules = [payload]
    observations: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            diagnostics.append(
                _diagnostic(
                    "parser_unhandled_shape",
                    f"payload.rules.{index}",
                    "Season rule must be an object.",
                )
            )
            continue
        subject_key = _text(rule.get("subjectKey"))
        fact_type = _text(rule.get("factType"))
        source_scope = _text(rule.get("sourceScope") or "season_rule")
        if (
            not subject_key
            or fact_type not in _SUPPORTED_FACT_TYPES
            or "value" not in rule
        ):
            diagnostics.append(
                _diagnostic(
                    "parser_unhandled_shape",
                    f"payload.rules.{index}",
                    "Season rule requires subjectKey, supported factType, and value.",
                )
            )
            continue
        observations.append(
            _observation(
                row,
                parser_revision,
                subject_key,
                fact_type,
                rule["value"],
                source_scope,
            )
        )
    return _result(
        row,
        parser_revision,
        observations=observations,
        diagnostics=diagnostics,
    )


_OBSERVERS: dict[str, Callable[..., dict[str, Any]]] = {
    "battle_net_item": observe_battle_net_item,
    "simc_item_probe": observe_simc_item_probe,
    "simc_bonus_probe": observe_simc_bonus_probe,
    "season_rule": observe_season_rule,
}


def observe_artifact(
    artifact: Any,
    *,
    parser_revision: str | None = None,
) -> dict[str, Any]:
    """Dispatch a stored Artifact to its pure versioned parser."""

    row = artifact if isinstance(artifact, Mapping) else {}
    source_type = _text(row.get("sourceType"))
    observer = _OBSERVERS.get(source_type)
    if not observer:
        return _result(
            row,
            parser_revision or "unsupported-source-observer-v1",
            diagnostics=[
                _diagnostic(
                    "parser_source_type_unsupported",
                    "sourceType",
                    "Artifact sourceType has no registered observer.",
                )
            ],
        )
    if parser_revision is None:
        return observer(row)
    return observer(row, parser_revision=parser_revision)


# Explicit aliases keep caller naming descriptive without creating another parser.
observe_battle_net_item_artifact = observe_battle_net_item
observe_simc_exact_item_probe = observe_simc_item_probe
observe_season_rule_artifact = observe_season_rule


__all__ = (
    "BATTLE_NET_ITEM_PARSER_REVISION",
    "SIMC_ITEM_PROBE_PARSER_REVISION",
    "SIMC_BONUS_PROBE_PARSER_REVISION",
    "SEASON_RULE_PARSER_REVISION",
    "observe_artifact",
    "observe_battle_net_item",
    "observe_battle_net_item_artifact",
    "observe_simc_item_probe",
    "observe_simc_exact_item_probe",
    "observe_simc_bonus_probe",
    "observe_season_rule",
    "observe_season_rule_artifact",
)

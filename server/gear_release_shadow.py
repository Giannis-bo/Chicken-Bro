#!/usr/bin/env python3
"""Internal read-only old/new shadow orchestration for inactive releases."""

from __future__ import annotations

import copy
import time
from datetime import datetime
from typing import Any, Iterable

try:
    from . import (
        gear_contracts,
        gear_enhancement_management,
        gear_evidence_ledger,
        gear_release,
        gear_resolver,
        gear_runtime,
        gear_socket_authority,
        pg_gear_read_model_selectors,
    )
    from .websim_payload import (
        gear_resolver_runtime_authority,
        normalize_option_value,
        normalize_slot,
    )
except ImportError:
    import gear_contracts
    import gear_enhancement_management
    import gear_evidence_ledger
    import gear_release
    import gear_resolver
    import gear_runtime
    import gear_socket_authority
    import pg_gear_read_model_selectors
    from websim_payload import (
        gear_resolver_runtime_authority,
        normalize_option_value,
        normalize_slot,
    )


_REFERENCE_TEMPLATE_ID = "observed_profile_mage_frost"
_REFERENCE_SPEC = ("mage", "frost")
_REFERENCE_SOCKET_SLOTS = ("head", "neck", "wrist", "waist", "finger1", "finger2")
_REFERENCE_SOCKET_VECTOR = [1, 2, 1, 1, 2, 1]
_OPTION_EVIDENCE_SOURCE_TYPES = frozenset({
    "postgres_gear_option",
    "blizzard_game_data_api",
    "wowhead_live_tooltip",
    "Battle.net Game Data API",
    "wago_db2_spell_item_enchantment",
    "server_curated_enchant_label",
    "server_owned_legacy_evidence_seed",
    "server_owned_evidence_seed",
    "server_payload",
    "wowhead_item",
    "wowhead_item+simulationcraft",
    "wowhead_item+simulationcraft+method",
})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _blocker(code: str, class_key: str = "", spec_key: str = "", detail: str = "") -> dict[str, Any]:
    path = "shadow"
    if class_key or spec_key:
        path = f"specs.{class_key}.{spec_key}"
    return {
        "kind": "SHADOW_COMPARE_BLOCKED",
        "code": code,
        "title": "Release shadow comparison blocked.",
        "detail": detail,
        "path": path,
        "retryable": False,
        "meta": {},
    }


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _timestamp(value: Any) -> str:
    normalized = _text(value)
    if not normalized:
        return ""
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return normalized if parsed.tzinfo is not None else ""


def _canonical_editor_token(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and value
        and value == value.strip()
        and "/" not in value
        and normalize_option_value(value) == value
    )


def _selected_simc_writer_plan(
    selection: dict[str, Any],
    variant: dict[str, Any],
    options_by_id: dict[str, Any],
    capability_revision: Any,
) -> dict[str, Any] | None:
    """Prove actual per-occurrence SimC writers before migration projection."""

    raw_variant_options = variant.get("simcOptions")
    if not isinstance(raw_variant_options, dict) or any(
        not isinstance(field, str)
        or not field.strip()
        or field != field.strip()
        for field in raw_variant_options
    ):
        return None
    management_fields = (
        gear_enhancement_management.validated_enhancement_management_fields(
            raw_variant_options,
            variant.get("enhancementManagement"),
            capability_revision,
        )
    )
    present_governed_fields = (
        gear_enhancement_management.present_enhancement_simc_fields(
            raw_variant_options
        )
    )
    if (
        capability_revision == gear_socket_authority.CAPABILITY_REVISION
        and present_governed_fields
        and set(management_fields) != present_governed_fields
    ):
        return None
    selected_ids_by_type = {
        "gem": list(selection.get("gemOptionIds") or []),
        "enchant": (
            [_text(selection.get("enchantOptionId"))]
            if _text(selection.get("enchantOptionId"))
            else []
        ),
        "embellishment": (
            [_text(selection.get("embellishmentOptionId"))]
            if _text(selection.get("embellishmentOptionId"))
            else []
        ),
        "crafted": (
            [_text(selection.get("craftedOptionId"))]
            if _text(selection.get("craftedOptionId"))
            else []
        ),
        "catalyst": (
            [_text(selection.get("catalystOptionId"))]
            if _text(selection.get("catalystOptionId"))
            else []
        ),
    }
    expected_option_types = {
        "gem": {"gem"},
        "enchant": {"enchant", "runeforge"},
        "embellishment": {"embellishment"},
        "crafted": {"crafted"},
        "catalyst": {"catalyst"},
    }
    governed_fields = set(
        gear_enhancement_management.ENHANCEMENT_SIMC_FIELDS
    )
    owned_governed_fields = {
        "gem": set(gear_enhancement_management.GEM_SIMC_SEQUENCE_FIELDS),
        "enchant": {"enchant_id"},
        "embellishment": {"embellishment"},
        "crafted": set(),
        "catalyst": set(),
    }
    fields_by_type = {option_type: set() for option_type in selected_ids_by_type}
    canonical_editor_fields: set[str] = set()
    editor_non_governed_writer_counts: dict[str, int] = {}
    gem_occurrence_count = len(selected_ids_by_type["gem"])
    gem_sequence_counts = {
        field: 0 for field in gear_enhancement_management.GEM_SIMC_SEQUENCE_FIELDS
    }
    for option_type, option_ids in selected_ids_by_type.items():
        for option_id in option_ids:
            option = options_by_id.get(option_id)
            if (
                not isinstance(option, dict)
                or _text(option.get("optionId")) != option_id
                or _text(option.get("optionType"))
                not in expected_option_types[option_type]
            ):
                return None
            raw_option_simc = option.get("simcOptions")
            option_simc = {} if raw_option_simc is None else raw_option_simc
            if not isinstance(option_simc, dict) or any(
                not isinstance(field, str)
                or not field.strip()
                or field != field.strip()
                for field in option_simc
            ):
                return None
            option_fields = set(option_simc)
            if option_fields & (
                governed_fields - owned_governed_fields[option_type]
            ):
                return None
            fields_by_type[option_type].update(option_fields)
            if option_type in {"gem", "enchant", "embellishment"}:
                for field in option_fields - governed_fields:
                    editor_non_governed_writer_counts[field] = (
                        editor_non_governed_writer_counts.get(field, 0) + 1
                    )
            if option_type == "gem":
                if not _canonical_editor_token(option_simc.get("gem_id")):
                    return None
                gem_sequence_counts["gem_id"] += 1
                for field in ("gem_bonus_id", "gem_ilevel"):
                    if field in option_simc:
                        if not _canonical_editor_token(option_simc.get(field)):
                            return None
                        gem_sequence_counts[field] += 1
            elif option_type == "enchant":
                if not _canonical_editor_token(option_simc.get("enchant_id")):
                    return None
                canonical_editor_fields.add("enchant_id")
            elif option_type == "embellishment":
                if not _canonical_editor_token(option_simc.get("embellishment")):
                    return None
                canonical_editor_fields.add("embellishment")
    if gem_occurrence_count:
        if gem_sequence_counts["gem_id"] != gem_occurrence_count:
            return None
        canonical_editor_fields.add("gem_id")
        for field in ("gem_bonus_id", "gem_ilevel"):
            if gem_sequence_counts[field] not in {0, gem_occurrence_count}:
                return None
            if gem_sequence_counts[field] == gem_occurrence_count:
                canonical_editor_fields.add(field)
    if any(
        writer_count > 1
        for writer_count in editor_non_governed_writer_counts.values()
    ):
        return None

    source_only_fields = {
        field
        for field, classification in management_fields.items()
        if classification == "source_only"
    }
    editor_managed_fields = {
        field
        for field, classification in management_fields.items()
        if classification == "editor_managed"
    }
    unresolved_drop_fields = {
        field
        for field, classification in management_fields.items()
        if classification == "unresolved_drop"
    }
    if not editor_managed_fields.issubset(canonical_editor_fields):
        return None
    migration_fields = (
        unresolved_drop_fields
        | editor_managed_fields
        | canonical_editor_fields
    )
    editor_fields = (
        fields_by_type["gem"]
        | fields_by_type["enchant"]
        | fields_by_type["embellishment"]
    )
    crafted_fields = fields_by_type["crafted"]
    catalyst_fields = fields_by_type["catalyst"]
    non_editor_fields = crafted_fields | catalyst_fields
    all_option_fields = editor_fields | non_editor_fields
    retained_variant_fields = set(raw_variant_options) - migration_fields
    if (
        source_only_fields & all_option_fields
        or retained_variant_fields & all_option_fields
        or non_editor_fields & migration_fields
        or non_editor_fields & editor_fields
        or crafted_fields & catalyst_fields
    ):
        return None
    return {
        "migrationFields": migration_fields,
        "selectedIdsByType": selected_ids_by_type,
        "fieldsByType": fields_by_type,
        "canonicalEditorFields": canonical_editor_fields,
    }


def _selection_intent_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
) -> dict[str, Any]:
    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            continue
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        if not slot or not item_id or slot in slots:
            continue
        slots[slot] = {
            "itemId": item_id,
            "variantKey": _text(raw.get("variantKey")),
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": _text(season_revision),
            "gearCatalogRevision": _text(gear_release_id),
        },
        "eligibilityContext": {
            "classKey": _text(template.get("classKey")),
            "specKey": _text(template.get("specKey")),
            "level": _int(level),
        },
        "slots": {key: slots[key] for key in sorted(slots)},
    }


def _resolved_snapshot(http_status: int, envelope: Any) -> dict[str, Any] | None:
    value = envelope if isinstance(envelope, dict) else {}
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    if http_status == 200 and value.get("status") == "resolved" and data.get("status") == "verified":
        return data
    return None


def _projected_winner_hero_key(value: Any) -> str:
    row = value if isinstance(value, dict) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return _text(row.get("heroKey") or payload.get("heroKey"))


def _active_release_pair_identity(value: Any) -> tuple[Any, ...] | None:
    """Capture one stable formal active identity, including a valid Gear-only state."""

    active = value if isinstance(value, dict) else {}
    pointer_generation = active.get("pointerGeneration")
    if (
        active.get("formalActiveManifest") is not True
        or type(pointer_generation) is not int
        or pointer_generation <= 0
    ):
        return None
    gear = active.get("gearRelease")
    gear = gear if isinstance(gear, dict) else {}
    community = active.get("communityRelease")
    community = community if isinstance(community, dict) else {}
    gear_release_id = _text(gear.get("releaseId"))
    community_release_id = _text(community.get("releaseId"))
    manifest_revision = _text(active.get("manifestRevision"))
    winners = active.get("winners")
    if not gear_release_id or not manifest_revision or not isinstance(winners, list):
        return None

    formal_gear_only = active.get("formalGearOnlyManifest") is True
    if formal_gear_only:
        if community_release_id or winners:
            return None
        return (
            True,
            gear_release_id,
            "",
            manifest_revision,
            pointer_generation,
            (),
            "gear_only",
        )
    if not community_release_id:
        return None

    winner_identity = []
    for winner in winners:
        if not isinstance(winner, dict):
            return None
        identity = (
            _text(winner.get("classKey")),
            _text(winner.get("specKey")),
            _projected_winner_hero_key(winner),
            _text(winner.get("templateId")),
        )
        if not identity[0] or not identity[1] or not identity[3]:
            return None
        winner_identity.append(identity)
    if len(set(winner_identity)) != len(winner_identity):
        return None
    return (
        True,
        gear_release_id,
        community_release_id,
        manifest_revision,
        pointer_generation,
        tuple(sorted(winner_identity)),
        "community",
    )


def _projected_winner_semantics(value: Any) -> dict[str, Any]:
    winner = value if isinstance(value, dict) else {}
    intent = (
        winner.get("selectionIntent")
        if isinstance(winner.get("selectionIntent"), dict)
        else {}
    )
    payload = (
        winner.get("payload")
        if isinstance(winner.get("payload"), dict)
        else {}
    )
    return {
        "heroKey": _projected_winner_hero_key(winner),
        "gearSourceTemplateId": _text(payload.get("gearSourceTemplateId")),
        "selectionIntent": {
            "schemaRevision": intent.get("schemaRevision"),
            "eligibilityContext": intent.get("eligibilityContext"),
            "slots": intent.get("slots"),
        },
        "semanticGearSignature": _text(
            winner.get("semanticGearSignature")
            or winner.get("resolvedGearSignature")
        ),
        "sourceKey": _text(winner.get("sourceKey")),
        "sourceUrl": _text(winner.get("sourceUrl")),
        "profileHash": _text(winner.get("profileHash")),
        "gearHash": _text(winner.get("gearHash")),
        "sampleCount": _int(winner.get("sampleCount")),
    }


def _run_projected_release_shadow(
    store: Any,
    *,
    pair: dict[str, Any],
    expected: list[tuple[str, str]],
    gear_release_id: str,
    community_release_id: str,
    simc_runtime_revision: str,
    level: int,
    profile_context_by_spec: dict[str, dict[str, Any]] | None,
    compare_profiles: bool,
) -> dict[str, Any]:
    """Validate a v2 two-Hero Community pair through an exact candidate preview."""

    started = time.perf_counter()
    blockers: list[dict[str, Any]] = []
    gear_descriptor = (
        pair.get("gearRelease")
        if isinstance(pair.get("gearRelease"), dict)
        else {}
    )
    community_descriptor = (
        pair.get("communityRelease")
        if isinstance(pair.get("communityRelease"), dict)
        else {}
    )
    if (
        _text(gear_descriptor.get("releaseId")) != gear_release_id
        or _text(gear_descriptor.get("releaseStatus")) != "validated"
        or _text(community_descriptor.get("releaseId")) != community_release_id
        or _text(community_descriptor.get("releaseStatus")) != "validated"
        or _text(community_descriptor.get("schemaRevision")) != "community-release-v2"
        or _text(community_descriptor.get("validatedAgainstReleaseId"))
        != gear_release_id
    ):
        blockers.append(_blocker(
            "CANDIDATE_PROJECTED_PAIR_INVALID",
            detail="Candidate preview requires one exact validated Gear/Community v2 pair.",
        ))

    expected_set = set(expected)
    candidate_by_spec: dict[
        tuple[str, str], dict[str, dict[str, Any]]
    ] = {spec: {} for spec in expected}
    for winner in pair.get("winners") or []:
        if not isinstance(winner, dict):
            continue
        spec = (
            _text(winner.get("classKey")),
            _text(winner.get("specKey")),
        )
        hero_key = _projected_winner_hero_key(winner)
        if spec not in expected_set:
            blockers.append(_blocker(
                "UNEXPECTED_PUBLIC_SPEC",
                *spec,
                "Candidate exposes a Hero winner outside the expected matrix.",
            ))
            continue
        if (
            not hero_key
            or hero_key in candidate_by_spec[spec]
            or _text(winner.get("role")) != "winner"
        ):
            blockers.append(_blocker(
                "DUPLICATE_CANDIDATE_HERO_WINNER",
                *spec,
                "Candidate must expose one unique winner for each Hero slot.",
            ))
            continue
        candidate_by_spec[spec][hero_key] = winner

    for class_key, spec_key in expected:
        if len(candidate_by_spec[(class_key, spec_key)]) != 2:
            blockers.append(_blocker(
                "CANDIDATE_HERO_WINNER_COUNT_INVALID",
                class_key,
                spec_key,
                "Community v2 requires exactly two unique Hero winners per spec.",
            ))

    active_reader = getattr(store, "get_active_community_release", None)
    active_pair: dict[str, Any] = {}
    if callable(active_reader):
        try:
            loaded = active_reader()
            if isinstance(loaded, dict):
                active_pair = loaded
        except Exception:
            active_pair = {}
    captured_active_identity = _active_release_pair_identity(active_pair)
    if captured_active_identity is None:
        return {
            "schemaRevision": "gear-release-shadow-execution-v2",
            "status": "blocked",
            "gearReleaseId": gear_release_id,
            "communityReleaseId": community_release_id,
            "report": {},
            "blockers": [_blocker(
                "ACTIVE_RELEASE_BASELINE_INVALID",
                detail=(
                    "Projected shadow requires one stable formal active Manifest "
                    "with an exact Gear identity and positive pointer generation."
                ),
            )],
            "specResults": [],
            "publicReadCount": 0,
            "importReadCount": 0,
            "formalActiveManifest": True,
            "candidatePreview": False,
        }

    formal_gear_only = captured_active_identity[6] == "gear_only"
    baseline_mode = (
        "formal_gear_only_candidate_preview"
        if formal_gear_only
        else "formal_community_candidate_preview"
    )
    active_by_spec: dict[
        tuple[str, str], dict[str, dict[str, Any]]
    ] = {}
    if not formal_gear_only:
        active_community = (
            active_pair.get("communityRelease")
            if isinstance(active_pair.get("communityRelease"), dict)
            else {}
        )
        if _text(active_community.get("schemaRevision")) != "community-release-v2":
            blockers.append(_blocker(
                "ACTIVE_PROJECTED_BASELINE_UNSUPPORTED",
                detail="A non-empty active baseline must be Community Release v2.",
            ))
        for winner in active_pair.get("winners") or []:
            if not isinstance(winner, dict):
                continue
            spec = (
                _text(winner.get("classKey")),
                _text(winner.get("specKey")),
            )
            hero_key = _projected_winner_hero_key(winner)
            if spec in expected_set and hero_key:
                active_by_spec.setdefault(spec, {})[hero_key] = winner

    public_read_count = 0
    import_read_count = 0
    public_winner_count = 0
    spec_results: list[dict[str, Any]] = []
    profile_contexts = (
        profile_context_by_spec
        if isinstance(profile_context_by_spec, dict)
        else {}
    )
    candidate_preview_seen = False

    for class_key, spec_key in expected:
        spec_started = time.perf_counter()
        blocker_count_before = len(blockers)
        spec = (class_key, spec_key)
        try:
            public = store.get_websim_gear(
                class_key,
                spec_key,
                compact=True,
                mode="initial",
            )
        except Exception:
            public = {}
            blockers.append(_blocker(
                "CANDIDATE_PREVIEW_READ_FAILED",
                class_key,
                spec_key,
                "Candidate preview public reader is unavailable.",
            ))
        public = public if isinstance(public, dict) else {}
        public_read_count += 1
        try:
            resolver_context = store.get_gear_resolver_context(
                gear_resolver_runtime_authority(
                    class_key,
                    spec_key,
                    simc_runtime_revision=simc_runtime_revision,
                )
            )
        except Exception:
            resolver_context = {}
        resolver_context = (
            resolver_context if isinstance(resolver_context, dict) else {}
        )
        authored = (
            resolver_context.get("authoredAgainst")
            if isinstance(resolver_context.get("authoredAgainst"), dict)
            else {}
        )
        preview_manifest_revision = _text(
            public.get("manifestRevision")
            or resolver_context.get("manifestRevision")
        )
        preview_binding_valid = (
            public.get("candidatePreview") is True
            and public.get("formalActiveManifest") is not True
            and _text(public.get("gearCatalogReleaseId")) == gear_release_id
            and _text(public.get("communityTemplateReleaseId"))
            == community_release_id
            and resolver_context.get("candidatePreview") is True
            and resolver_context.get("formalActiveManifest") is not True
            and _text(authored.get("gearCatalogRevision")) == gear_release_id
            and bool(preview_manifest_revision)
        )
        if not preview_binding_valid:
            blockers.append(_blocker(
                "CANDIDATE_PREVIEW_BINDING_REQUIRED",
                class_key,
                spec_key,
                "Shadow must read the exact inactive pair through Candidate Preview.",
            ))
        else:
            candidate_preview_seen = True

        baselines = (
            public.get("baselineTemplates")
            if isinstance(public.get("baselineTemplates"), list)
            else []
        )
        if baselines:
            blockers.append(_blocker(
                "PUBLIC_BASELINE_LEAK",
                class_key,
                spec_key,
                "Candidate Preview baseline templates must remain empty.",
            ))
        public_templates = (
            public.get("communityTemplates")
            if isinstance(public.get("communityTemplates"), list)
            else []
        )
        public_by_hero: dict[str, dict[str, Any]] = {}
        for template in public_templates:
            if not isinstance(template, dict):
                continue
            hero_key = _text(template.get("heroKey"))
            if not hero_key or hero_key in public_by_hero:
                blockers.append(_blocker(
                    "PUBLIC_HERO_WINNER_IDENTITY_INVALID",
                    class_key,
                    spec_key,
                    "Candidate Preview Hero identities must be unique.",
                ))
                continue
            public_by_hero[hero_key] = template
        public_winner_count += len(public_by_hero)
        if (
            len(public_by_hero) != 2
            or set(public_by_hero) != set(candidate_by_spec.get(spec, {}))
        ):
            blockers.append(_blocker(
                "PUBLIC_HERO_WINNER_COUNT_INVALID",
                class_key,
                spec_key,
                "Candidate Preview must expose the exact two sealed Hero winners.",
            ))

        hero_results: list[dict[str, Any]] = []
        for hero_key, candidate in sorted(
            candidate_by_spec.get(spec, {}).items()
        ):
            hero_blocker_count = len(blockers)
            public_template = public_by_hero.get(hero_key)
            template_id = _text(candidate.get("templateId"))
            if (
                not isinstance(public_template, dict)
                or _text(public_template.get("id")) != template_id
            ):
                blockers.append(_blocker(
                    "PUBLIC_WINNER_ID_MISMATCH",
                    class_key,
                    spec_key,
                    f"Hero {hero_key} preview identity differs from the sealed winner.",
                ))

            if not formal_gear_only:
                active_winner = active_by_spec.get(spec, {}).get(hero_key)
                if not isinstance(active_winner, dict):
                    blockers.append(_blocker(
                        "ACTIVE_HERO_WINNER_MISSING",
                        class_key,
                        spec_key,
                        f"Active Hero {hero_key} winner is unavailable.",
                    ))
                elif (
                    _projected_winner_semantics(active_winner)
                    != _projected_winner_semantics(candidate)
                ):
                    blockers.append(_blocker(
                        "PUBLIC_WINNER_SEMANTIC_CHANGE",
                        class_key,
                        spec_key,
                        f"Candidate Hero {hero_key} differs from the accepted active winner.",
                    ))

            candidate_intent = (
                candidate.get("selectionIntent")
                if isinstance(candidate.get("selectionIntent"), dict)
                else {}
            )
            candidate_status, candidate_envelope = (
                gear_runtime.resolve_candidate_selection_intent(
                    candidate_intent,
                    store=store,
                    gear_release_id=gear_release_id,
                    simc_runtime_revision=simc_runtime_revision,
                    request_id=(
                        f"shadow-candidate-{class_key}-{spec_key}-{hero_key}"
                    ),
                )
            )
            candidate_snapshot = _resolved_snapshot(
                candidate_status,
                candidate_envelope,
            )
            if candidate_snapshot is None:
                blockers.append(_blocker(
                    "CANDIDATE_RESOLVE_FAILED",
                    class_key,
                    spec_key,
                    f"Candidate Hero {hero_key} did not resolve.",
                ))
            elif (
                gear_release.semantic_gear_signature(
                    candidate_intent,
                    candidate_snapshot,
                )
                != _text(candidate.get("semanticGearSignature"))
            ):
                blockers.append(_blocker(
                    "CANDIDATE_SEALED_RESULT_MISMATCH",
                    class_key,
                    spec_key,
                    f"Candidate Hero {hero_key} differs from its sealed result.",
                ))

            import_status, import_envelope, _import_timings = (
                gear_runtime.import_community_template(
                    {
                        "classKey": class_key,
                        "specKey": spec_key,
                        "templateId": template_id,
                        "expectedManifestRevision": preview_manifest_revision,
                    },
                    store=store,
                    simc_runtime_revision=simc_runtime_revision,
                    request_id=(
                        f"shadow-import-{class_key}-{spec_key}-{hero_key}"
                    ),
                )
            )
            import_read_count += 1
            import_data = (
                import_envelope.get("data")
                if isinstance(import_envelope, dict)
                and isinstance(import_envelope.get("data"), dict)
                else {}
            )
            imported_snapshot = (
                import_data.get("resolvedSnapshot")
                if isinstance(import_data.get("resolvedSnapshot"), dict)
                else {}
            )
            import_verified = (
                import_status == 200
                and _text(import_envelope.get("status")) == "verified"
                and _text(import_data.get("status")) == "verified"
                and _text(imported_snapshot.get("status")) == "verified"
            )
            if not import_verified:
                blockers.append(_blocker(
                    "CANDIDATE_IMPORT_FAILED",
                    class_key,
                    spec_key,
                    f"Candidate Hero {hero_key} import did not verify.",
                ))
            elif (
                candidate_snapshot is not None
                and _text(imported_snapshot.get("resolvedGearSignature"))
                != _text(candidate_snapshot.get("resolvedGearSignature"))
            ):
                blockers.append(_blocker(
                    "CANDIDATE_IMPORT_RESOLVE_MISMATCH",
                    class_key,
                    spec_key,
                    f"Candidate Hero {hero_key} import differs from exact Resolve.",
                ))

            profile_result = {"status": "not_run"}
            if compare_profiles:
                profile_context = profile_contexts.get(
                    f"{class_key}:{spec_key}"
                )
                profile_context = (
                    profile_context
                    if isinstance(profile_context, dict)
                    else {}
                )
                preview_profile_status, preview_profile = (
                    gear_runtime.build_profile_from_selection_intent(
                        {
                            "selectionIntent": candidate_intent,
                            "profileContext": profile_context,
                        },
                        store=store,
                        simc_runtime_revision=simc_runtime_revision,
                        request_id=(
                            f"shadow-preview-profile-{class_key}-"
                            f"{spec_key}-{hero_key}"
                        ),
                    )
                )
                exact_profile_status, exact_profile = (
                    gear_runtime.build_candidate_profile_from_selection_intent(
                        {
                            "selectionIntent": candidate_intent,
                            "profileContext": profile_context,
                        },
                        store=store,
                        gear_release_id=gear_release_id,
                        simc_runtime_revision=simc_runtime_revision,
                        request_id=(
                            f"shadow-candidate-profile-{class_key}-"
                            f"{spec_key}-{hero_key}"
                        ),
                    )
                )
                preview_outcome = _profile_outcome(
                    preview_profile_status,
                    preview_profile,
                )
                exact_outcome = _profile_outcome(
                    exact_profile_status,
                    exact_profile,
                )
                profile_result = {
                    "status": (
                        "pass"
                        if preview_outcome == exact_outcome
                        else "blocked"
                    ),
                    "previewHttpStatus": preview_profile_status,
                    "candidateHttpStatus": exact_profile_status,
                    "previewProblemCodes": preview_outcome["problemCodes"],
                    "candidateProblemCodes": exact_outcome["problemCodes"],
                }
                if profile_result["status"] != "pass":
                    blockers.append(_blocker(
                        "PROFILE_PARITY_MISMATCH",
                        class_key,
                        spec_key,
                        f"Candidate Hero {hero_key} Profile differs from preview.",
                    ))

            hero_results.append({
                "heroKey": hero_key,
                "templateId": template_id,
                "status": (
                    "pass"
                    if len(blockers) == hero_blocker_count
                    else "blocked"
                ),
                "candidateHttpStatus": candidate_status,
                "importHttpStatus": import_status,
                "profileParity": profile_result,
            })

        spec_results.append({
            "classKey": class_key,
            "specKey": spec_key,
            "status": (
                "pass"
                if len(blockers) == blocker_count_before
                else "blocked"
            ),
            "heroSlotResults": hero_results,
            "durationMs": round(
                (time.perf_counter() - spec_started) * 1000,
                3,
            ),
        })

    try:
        ending_active_pair = active_reader() if callable(active_reader) else {}
    except Exception:
        ending_active_pair = {}
    if (
        _active_release_pair_identity(ending_active_pair)
        != captured_active_identity
    ):
        blockers.append(_blocker(
            "ACTIVE_RELEASE_CHANGED_DURING_SHADOW",
            detail="Exact active Manifest identity changed during candidate shadow.",
        ))

    status = "blocked" if blockers else "pass"
    report = {
        "schemaRevision": "gear-release-projected-shadow-report-v1",
        "status": status,
        "gearReleaseId": gear_release_id,
        "communityReleaseId": community_release_id,
        "expectedSpecCount": len(expected),
        "expectedHeroSlotCount": len(expected) * 2,
        "candidateWinnerCount": sum(
            len(rows) for rows in candidate_by_spec.values()
        ),
        "publicWinnerCount": public_winner_count,
        "activeWinnerCount": sum(
            len(rows) for rows in active_by_spec.values()
        ),
        "blockers": [],
    }
    spec_durations = sorted(
        float(row.get("durationMs") or 0)
        for row in spec_results
        if isinstance(row, dict)
    )
    p95_index = max(
        0,
        ((len(spec_durations) * 95 + 99) // 100) - 1,
    )
    return {
        "schemaRevision": "gear-release-shadow-execution-v2",
        "status": status,
        "gearReleaseId": gear_release_id,
        "communityReleaseId": community_release_id,
        "baselineMode": baseline_mode,
        "report": report,
        "blockers": blockers,
        "specResults": spec_results,
        "publicReadCount": public_read_count,
        "importReadCount": import_read_count,
        "formalActiveManifest": False,
        "activeBaselineFormal": True,
        "candidatePreview": candidate_preview_seen,
        "referenceProof": {
            "status": "pass" if status == "pass" else "blocked",
            "mode": "hero_slot_full_import_matrix",
            "verifiedHeroSlotCount": sum(
                1
                for row in spec_results
                for hero in row.get("heroSlotResults") or []
                if isinstance(hero, dict) and hero.get("status") == "pass"
            ),
        },
        "performance": {
            "totalDurationMs": round(
                (time.perf_counter() - started) * 1000,
                3,
            ),
            "specP95Ms": (
                spec_durations[p95_index]
                if spec_durations
                else 0
            ),
            "specMaxMs": spec_durations[-1] if spec_durations else 0,
        },
    }


def _problem_codes(envelope: Any) -> list[str]:
    value = envelope if isinstance(envelope, dict) else {}
    problems = value.get("problems") if isinstance(value.get("problems"), list) else []
    return sorted({
        _text(problem.get("code"))
        for problem in problems
        if isinstance(problem, dict) and _text(problem.get("code"))
    })


def _profile_outcome(http_status: int, envelope: Any) -> dict[str, Any]:
    """Normalize user-visible canonical Profile output while ignoring release-only metadata."""

    value = envelope if isinstance(envelope, dict) else {}
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    return {
        "httpStatus": http_status,
        "status": _text(value.get("status")),
        "problemCodes": _problem_codes(value),
        "data": {
            field: data.get(field)
            for field in (
                "profile",
                "gearItems",
                "simcItems",
                "readiness",
                "talentEncoding",
                "preparation",
                "profileReadiness",
            )
            if field in data
        },
    }


def _profile_outcomes_allow_migration(
    transitional: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    """Accept exact resolved parity or the one canonical no-talent failure."""

    if transitional != candidate:
        return False
    data = (
        transitional.get("data")
        if isinstance(transitional.get("data"), dict)
        else {}
    )
    talent_encoding = (
        data.get("talentEncoding")
        if isinstance(data.get("talentEncoding"), dict)
        else {}
    )
    readiness = (
        data.get("profileReadiness")
        if isinstance(data.get("profileReadiness"), dict)
        else {}
    )
    if (
        transitional.get("httpStatus") == 200
        and transitional.get("status") == "resolved"
        and transitional.get("problemCodes") == []
        and isinstance(data.get("profile"), str)
        and bool(data["profile"].strip())
        and talent_encoding.get("status") in {"encoded", "external"}
        and readiness.get("simcReady") is True
    ):
        return True
    return (
        transitional.get("httpStatus") == 200
        and transitional.get("status") == "blocked"
        and transitional.get("problemCodes") == ["GEAR_PROFILE_NOT_READY"]
        and data.get("profile") == ""
        and talent_encoding.get("status") == "failed"
        and talent_encoding.get("source") == "none"
        and talent_encoding.get("errors")
        == ["no WebSim talent nodes selected"]
        and talent_encoding.get("warnings") == []
        and talent_encoding.get("lines") == []
        and talent_encoding.get("selectedCounts")
        == {"class": 0, "spec": 0, "hero": 0}
        and readiness.get("status") == "blocked"
        and readiness.get("simcReady") is False
    )


def _profile_outcomes_preserve_import_gate(
    transitional: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    """Allow source-sealed gear deltas only when the Profile gate is unchanged."""

    def gate_projection(outcome: Any) -> dict[str, Any]:
        value = outcome if isinstance(outcome, dict) else {}
        data = value.get("data") if isinstance(value.get("data"), dict) else {}
        talent_encoding = (
            data.get("talentEncoding")
            if isinstance(data.get("talentEncoding"), dict)
            else {}
        )
        readiness = (
            data.get("profileReadiness")
            if isinstance(data.get("profileReadiness"), dict)
            else {}
        )
        return {
            "httpStatus": value.get("httpStatus"),
            "status": _text(value.get("status")),
            "problemCodes": list(value.get("problemCodes") or []),
            "hasProfile": bool(_text(data.get("profile"))),
            "talentEncoding": {
                field: talent_encoding.get(field)
                for field in ("status", "source", "errors", "warnings", "selectedCounts")
            },
            "profileReadiness": {
                field: readiness.get(field)
                for field in ("status", "simcReady", "requiredSlots", "readySlots")
            },
        }

    return gate_projection(transitional) == gate_projection(candidate)


def _bind_transitional_provenance_to_active_winner(
    transitional_row: Any,
    active_winner: Any,
) -> dict[str, Any]:
    """Use sealed active provenance missing from the public projection.

    A legacy public template can expose an older profile hash that was never
    carried by its sealed active winner.  When every other source identity is
    exactly bound, the sealed Manifest remains authoritative: retain its
    missing-hash state rather than manufacture a candidate mismatch.  The
    public template projection also intentionally omits the sealed
    ``importEvidence`` payload; carry that exact evidence into the transitional
    comparison only after the same complete identity check.  Any non-empty
    source, slot, level, or icon disagreement remains visible to shadow.
    """

    row = copy.deepcopy(transitional_row) if isinstance(transitional_row, dict) else {}
    if not row or not isinstance(active_winner, dict):
        return row
    for field in ("templateId", "sourceKey", "sourceUrl", "gearHash"):
        row_value = _text(row.get(field))
        active_value = _text(active_winner.get(field))
        if not row_value or row_value != active_value:
            return row
    row_sample_count = _int(row.get("sampleCount"))
    active_sample_count = _int(active_winner.get("sampleCount"))
    if not row_sample_count or row_sample_count != active_sample_count:
        return row
    sealed_profile_hash = _text(active_winner.get("profileHash"))
    projected_profile_hash = _text(row.get("profileHash"))
    if sealed_profile_hash and sealed_profile_hash != projected_profile_hash:
        return row
    row["profileHash"] = sealed_profile_hash
    sentinel = object()
    sealed_import_evidence = active_winner.get("importEvidence", sentinel)
    if sealed_import_evidence is sentinel:
        active_payload = active_winner.get("payload")
        if isinstance(active_payload, dict):
            sealed_import_evidence = active_payload.get("importEvidence", sentinel)
    if sealed_import_evidence is sentinel:
        row.pop("importEvidence", None)
    else:
        row["importEvidence"] = copy.deepcopy(sealed_import_evidence)
    return row


def _enhancement_selection_projection(intent: Any) -> dict[str, dict[str, Any]]:
    value = intent if isinstance(intent, dict) else {}
    result = {}
    for slot, selection in (value.get("slots") or {}).items():
        if not isinstance(selection, dict):
            continue
        result[_text(slot)] = {
            "gemOptionIds": list(selection.get("gemOptionIds") or []),
            "enchantOptionId": _text(selection.get("enchantOptionId")),
            "embellishmentOptionId": _text(selection.get("embellishmentOptionId")),
        }
    return result


def _non_enhancement_selection_projection(intent: Any) -> dict[str, Any]:
    """Retain every Intent field outside the three approved migration fields."""

    value = intent if isinstance(intent, dict) else {}
    projected = {
        key: copy.deepcopy(field_value)
        for key, field_value in value.items()
        if key not in {"authoredAgainst", "slots"}
    }
    authored = (
        copy.deepcopy(value.get("authoredAgainst"))
        if isinstance(value.get("authoredAgainst"), dict)
        else {}
    )
    authored.pop("gearCatalogRevision", None)
    projected["authoredAgainst"] = authored
    projected_slots = {}
    for slot, selection in (value.get("slots") or {}).items():
        if not isinstance(selection, dict):
            projected_slots[_text(slot)] = copy.deepcopy(selection)
            continue
        projected_slots[_text(slot)] = {
            key: copy.deepcopy(field_value)
            for key, field_value in selection.items()
            if key not in {
                "gemOptionIds",
                "enchantOptionId",
                "embellishmentOptionId",
            }
        }
    projected["slots"] = projected_slots
    return projected


def _enhancement_migration_projection(snapshot: Any) -> dict[str, Any]:
    """Exclude editor occupancy while retaining every non-editor option fact."""

    value = snapshot if isinstance(snapshot, dict) else {}
    ledger = (
        value.get("evidenceLedger")
        if isinstance(value.get("evidenceLedger"), dict)
        else {}
    )
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    claim_key_by_id = {
        _text(claim.get("claimId")): _text(claim.get("claimKey"))
        for claim in claims
        if isinstance(claim, dict)
        and _text(claim.get("claimId"))
        and _text(claim.get("claimKey"))
    }
    editor_selection_fields = {
        "gemOptionIds",
        "enchantOptionId",
        "embellishmentOptionId",
    }
    editor_capability_fields = {
        "allowedGemOptionIds",
        "allowedEnchantOptionIds",
        "allowedEmbellishmentOptionIds",
    }

    def semantic_claim_ids(raw_ids: Any) -> list[str]:
        ids = raw_ids if isinstance(raw_ids, list) else []
        return sorted(
            claim_key_by_id.get(
                _text(claim_id),
                f"__unmapped_claim__:{_text(claim_id)}",
            )
            for claim_id in ids
        )

    def subtract_deltas(raw_stats: Any, deltas: dict[str, int | float]) -> Any:
        if not isinstance(raw_stats, dict):
            return copy.deepcopy(raw_stats)
        projected_stats = copy.deepcopy(raw_stats)
        for stat, delta in deltas.items():
            amount = projected_stats.get(stat)
            if (
                not isinstance(amount, (int, float))
                or isinstance(amount, bool)
                or not isinstance(delta, (int, float))
                or isinstance(delta, bool)
            ):
                continue
            projected_amount = amount - delta
            if projected_amount == 0:
                projected_stats.pop(stat, None)
            else:
                projected_stats[stat] = projected_amount
        return projected_stats

    resolved_slots = {}
    non_editor_option_ids: set[str] = set()
    editor_source_ref_ids: set[str] = set()
    projected_stats_by_slot: dict[str, Any] = {}
    aggregate_editor_delta_sums: dict[str, int | float] = {}
    for slot, resolved in (value.get("resolvedSlots") or {}).items():
        if not isinstance(resolved, dict):
            continue
        slot_key = _text(slot)
        selected_options = (
            resolved.get("selectedOptions")
            if isinstance(resolved.get("selectedOptions"), dict)
            else {}
        )
        raw_gem_ids = selected_options.get("gemOptionIds")
        selected_editor_ids = {
            _text(option_id)
            for option_id in (
                raw_gem_ids if isinstance(raw_gem_ids, list) else []
            )
            if _text(option_id)
        }
        selected_editor_ids.update({
            _text(selected_options.get(field))
            for field in ("enchantOptionId", "embellishmentOptionId")
            if _text(selected_options.get(field))
        })
        selected_non_editor_ids = {
            _text(selected_options.get(field))
            for field in ("craftedOptionId", "catalystOptionId")
            if _text(selected_options.get(field))
        }
        non_editor_option_ids.update(selected_non_editor_ids)
        slot_editor_refs = {
            f"evidence:pg:option:{option_id}"
            for option_id in selected_editor_ids
        }
        editor_source_ref_ids.update(slot_editor_refs)

        raw_stat_deltas = (
            resolved.get("statDeltas")
            if isinstance(resolved.get("statDeltas"), dict)
            else {}
        )
        enhancements = (
            raw_stat_deltas.get("enhancements")
            if isinstance(raw_stat_deltas.get("enhancements"), list)
            else []
        )
        editor_delta_sums: dict[str, int | float] = {}
        retained_enhancements = []
        for enhancement in enhancements:
            option_id = (
                _text(enhancement.get("optionId"))
                if isinstance(enhancement, dict)
                else ""
            )
            if option_id not in selected_editor_ids:
                retained_enhancements.append(copy.deepcopy(enhancement))
                continue
            stat_deltas = enhancement.get("statDeltas")
            if not isinstance(stat_deltas, dict):
                continue
            for stat, delta in stat_deltas.items():
                if (
                    isinstance(delta, (int, float))
                    and not isinstance(delta, bool)
                ):
                    editor_delta_sums[stat] = (
                        editor_delta_sums.get(stat, 0) + delta
                    )
                    aggregate_editor_delta_sums[stat] = (
                        aggregate_editor_delta_sums.get(stat, 0) + delta
                    )
        projected_stats = subtract_deltas(
            resolved.get("resolvedStats"),
            editor_delta_sums,
        )
        projected_stats_by_slot[slot_key] = projected_stats

        projected = {}
        for key, field_value in resolved.items():
            if key == "selectedOptions":
                projected[key] = {
                    option_key: copy.deepcopy(option_value)
                    for option_key, option_value in selected_options.items()
                    if option_key not in editor_selection_fields
                }
                continue
            if key == "sourceRefIds":
                projected[key] = sorted(
                    _text(source_ref)
                    for source_ref in (
                        field_value if isinstance(field_value, list) else []
                    )
                    if _text(source_ref) not in slot_editor_refs
                )
                continue
            if key == "evidenceClaimIds":
                projected[key] = semantic_claim_ids(field_value)
                continue
            if key == "statDeltas" and isinstance(field_value, dict):
                projected[key] = {
                    delta_key: (
                        retained_enhancements
                        if delta_key == "enhancements"
                        else copy.deepcopy(delta_value)
                    )
                    for delta_key, delta_value in field_value.items()
                }
                continue
            if key == "effectiveCapabilities" and isinstance(field_value, dict):
                projected[key] = {
                    capability_key: copy.deepcopy(capability_value)
                    for capability_key, capability_value in field_value.items()
                    if capability_key not in editor_capability_fields
                }
                continue
            if key == "resolvedStats":
                projected[key] = copy.deepcopy(projected_stats)
                continue
            projected[key] = copy.deepcopy(field_value)
        resolved_slots[slot_key] = projected

    projected_static_attributes = subtract_deltas(
        value.get("staticAttributes"),
        aggregate_editor_delta_sums,
    )
    raw_constraints = value.get("constraints") if isinstance(value.get("constraints"), dict) else {}
    constraint_slots = {}
    for slot, constraint in (raw_constraints.get("slots") or {}).items():
        if not isinstance(constraint, dict):
            continue
        constraint_slots[_text(slot)] = {
            key: copy.deepcopy(field_value)
            for key, field_value in constraint.items()
            if key not in {
                "socketRemaining",
                "hasSelectedEnchant",
                "hasSelectedEmbellishment",
            }
        }
    constraints = {
        key: copy.deepcopy(field_value)
        for key, field_value in raw_constraints.items()
        if key not in {
            "slots",
            "embellishmentSelectedUsed",
            "embellishmentUsed",
        }
    }
    constraints["slots"] = constraint_slots

    projected_claims = []
    for claim in claims:
        if not isinstance(claim, dict):
            projected_claims.append(copy.deepcopy(claim))
            continue
        claim_key = _text(claim.get("claimKey"))
        projected_claim = {
            key: copy.deepcopy(field_value)
            for key, field_value in claim.items()
            if key not in {
                "claimId",
                "resolvedSignature",
                "dependencyVector",
                "dependsOn",
                "sourceRefIds",
                "value",
            }
        }
        dependency_vector = copy.deepcopy(claim.get("dependencyVector"))
        if isinstance(dependency_vector, dict):
            for field in (
                "gearCatalogReleaseId",
                "gearCatalogRevision",
                "capabilityRevision",
            ):
                if field in dependency_vector:
                    dependency_vector[field] = "__enhancement_migration__"
        projected_value = copy.deepcopy(claim.get("value"))
        if claim_key.startswith("slot:"):
            claim_parts = claim_key.split(":")
            claim_slot = claim_parts[1] if len(claim_parts) == 3 else ""
            claim_kind = claim_parts[2] if len(claim_parts) == 3 else ""
            if (
                claim_kind == "identity_options"
                and isinstance(projected_value, dict)
                and isinstance(projected_value.get("selectedOptions"), dict)
            ):
                projected_value["selectedOptions"] = {
                    option_key: copy.deepcopy(option_value)
                    for option_key, option_value in projected_value[
                        "selectedOptions"
                    ].items()
                    if option_key not in editor_selection_fields
                }
            elif (
                claim_kind == "provenance"
                and isinstance(projected_value, dict)
                and isinstance(projected_value.get("sourceRefIds"), list)
            ):
                projected_value["sourceRefIds"] = sorted(
                    _text(source_ref)
                    for source_ref in projected_value["sourceRefIds"]
                    if _text(source_ref) not in editor_source_ref_ids
                )
            elif claim_kind == "static_attributes":
                projected_value = copy.deepcopy(
                    projected_stats_by_slot.get(claim_slot, projected_value)
                )
        elif claim_key == "aggregate:static_attributes":
            projected_value = copy.deepcopy(projected_static_attributes)
        projected_claim.update({
            "dependencyVector": dependency_vector,
            "dependsOn": semantic_claim_ids(claim.get("dependsOn")),
            "sourceRefIds": sorted(
                _text(source_ref)
                for source_ref in (
                    claim.get("sourceRefIds")
                    if isinstance(claim.get("sourceRefIds"), list)
                    else []
                )
                if _text(source_ref) not in editor_source_ref_ids
            ),
            "value": projected_value,
        })
        projected_claims.append(projected_claim)
    projected_claims.sort(
        key=lambda claim: (
            _text(claim.get("group")) if isinstance(claim, dict) else "",
            _text(claim.get("claimKey")) if isinstance(claim, dict) else "",
        )
    )
    claim_groups = (
        ledger.get("claimGroups")
        if isinstance(ledger.get("claimGroups"), dict)
        else {}
    )
    evidence_records = (
        ledger.get("evidenceRecordsById")
        if isinstance(ledger.get("evidenceRecordsById"), dict)
        else {}
    )
    projected_evidence_records = {}
    for record_id, record in evidence_records.items():
        option_id = _text(record.get("optionId")) if isinstance(record, dict) else ""
        if option_id and option_id not in non_editor_option_ids:
            continue
        projected_evidence_records[_text(record_id)] = copy.deepcopy(record)
    projected_ledger = {
        key: copy.deepcopy(field_value)
        for key, field_value in ledger.items()
        if key not in {"claims", "claimGroups", "evidenceRecordsById"}
    }
    projected_ledger.update({
        "claims": projected_claims,
        "claimGroups": {
            _text(group): semantic_claim_ids(claim_ids)
            for group, claim_ids in claim_groups.items()
        },
        "evidenceRecordsById": projected_evidence_records,
    })
    return {
        "eligibilityContext": copy.deepcopy(value.get("eligibilityContext") or {}),
        "resolvedSlots": resolved_slots,
        "staticAttributes": projected_static_attributes,
        "setState": copy.deepcopy(value.get("setState") or {}),
        "constraints": constraints,
        "serializerInput": copy.deepcopy(value.get("serializerInput") or {}),
        "profileReadiness": copy.deepcopy(value.get("profileReadiness") or {}),
        "evidenceLedger": projected_ledger,
    }


def _legacy_to_v2_enhancement_migration_equivalent(
    transitional_snapshot: Any,
    candidate_snapshot: Any,
    *,
    transitional_gear_release_id: Any,
    transitional_gear_catalog_revision: Any,
    candidate_gear_release_id: Any,
    transitional_authority_context: Any,
    candidate_authority_context: Any,
    transitional_intent: Any,
    candidate_intent: Any,
    migration_mode: str,
) -> bool:
    """Validate and project one evidence-loaded legacy-to-v2 migration."""

    transitional_value = transitional_snapshot if isinstance(transitional_snapshot, dict) else {}
    candidate_value = candidate_snapshot if isinstance(candidate_snapshot, dict) else {}
    if migration_mode not in {"editor_only", "socket_capacity"}:
        return False
    transitional_dependencies = (
        transitional_value.get("dependencyVector")
        if isinstance(transitional_value.get("dependencyVector"), dict)
        else {}
    )
    candidate_dependencies = (
        candidate_value.get("dependencyVector")
        if isinstance(candidate_value.get("dependencyVector"), dict)
        else {}
    )
    transitional_authority = (
        transitional_authority_context
        if isinstance(transitional_authority_context, dict)
        else {}
    )
    candidate_authority = (
        candidate_authority_context
        if isinstance(candidate_authority_context, dict)
        else {}
    )
    transitional_release_id = _text(transitional_gear_release_id)
    transitional_revision = _text(transitional_gear_catalog_revision)
    candidate_release_id = _text(candidate_gear_release_id)
    parsed_transitional_intent, transitional_intent_issues = (
        gear_contracts.parse_selection_intent(transitional_intent)
    )
    parsed_candidate_intent, candidate_intent_issues = (
        gear_contracts.parse_selection_intent(candidate_intent)
    )
    if (
        transitional_intent_issues
        or candidate_intent_issues
        or gear_contracts.validate_dependency_vector(transitional_dependencies)
        or gear_contracts.validate_dependency_vector(candidate_dependencies)
        or gear_contracts.validate_authority_context(
            parsed_transitional_intent,
            transitional_authority,
        )
        or gear_contracts.validate_authority_context(
            parsed_candidate_intent,
            candidate_authority,
        )
        or not transitional_release_id
        or not transitional_revision
        or not candidate_release_id
        or _text(transitional_dependencies.get("gearCatalogReleaseId"))
        != transitional_release_id
        or _text(transitional_dependencies.get("gearCatalogRevision"))
        != transitional_revision
        or _text(candidate_dependencies.get("gearCatalogReleaseId"))
        != candidate_release_id
        or _text(candidate_dependencies.get("gearCatalogRevision"))
        != candidate_release_id
        or transitional_authority.get("dependencyVector")
        != transitional_dependencies
        or candidate_authority.get("dependencyVector") != candidate_dependencies
        or _text(transitional_dependencies.get("capabilityRevision"))
        != gear_socket_authority.LEGACY_CAPABILITY_REVISION
        or _text(candidate_dependencies.get("capabilityRevision"))
        != gear_socket_authority.CAPABILITY_REVISION
    ):
        return False
    transitional_resolved_slots = transitional_value.get("resolvedSlots")
    candidate_resolved_slots = candidate_value.get("resolvedSlots")
    if (
        not isinstance(transitional_resolved_slots, dict)
        or not isinstance(candidate_resolved_slots, dict)
    ):
        return False
    try:
        recomputed_transitional_snapshot = gear_resolver.resolve(
            parsed_transitional_intent,
            transitional_authority,
        )
        recomputed_candidate_snapshot = gear_resolver.resolve(
            parsed_candidate_intent,
            candidate_authority,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    if (
        recomputed_transitional_snapshot != transitional_value
        or recomputed_candidate_snapshot != candidate_value
    ):
        return False

    def authority_plans(
        parsed_intent: dict[str, Any],
        snapshot_slots: dict[str, Any],
        authority: dict[str, Any],
    ) -> dict[str, dict[str, Any]] | None:
        items = authority.get("itemsById")
        variants = authority.get("variantsByKey")
        options = authority.get("optionsById")
        evidence = authority.get("evidenceRecordsById")
        dependencies = authority.get("dependencyVector")
        if not all(
            isinstance(value, dict)
            for value in (items, variants, options, evidence, dependencies)
        ):
            return None
        plans = {}
        for slot, selection in parsed_intent["slots"].items():
            item_id = _text(selection.get("itemId"))
            variant_key = _text(selection.get("variantKey"))
            item = items.get(item_id)
            variant = variants.get(variant_key)
            resolved = snapshot_slots.get(slot)
            item_sources = item.get("sourceRefIds") if isinstance(item, dict) else None
            variant_sources = variant.get("sourceRefIds") if isinstance(variant, dict) else None
            resolved_sources = resolved.get("sourceRefIds") if isinstance(resolved, dict) else None
            if (
                not isinstance(item, dict)
                or _text(item.get("itemId")) != item_id
                or not isinstance(variant, dict)
                or _text(variant.get("variantKey")) != variant_key
                or _text(variant.get("itemId")) != item_id
                or _text(variant.get("status")) != "verified"
                or not isinstance(resolved, dict)
                or not isinstance(item_sources, list)
                or not item_sources
                or any(not isinstance(source, str) or not source.strip() for source in item_sources)
                or not isinstance(variant_sources, list)
                or not variant_sources
                or any(not isinstance(source, str) or not source.strip() for source in variant_sources)
                or not isinstance(resolved_sources, list)
            ):
                return None
            authority_sources = set(item_sources) | set(variant_sources)
            if not authority_sources.issubset(set(resolved_sources)):
                return None
            for source_ref in authority_sources:
                record = evidence.get(source_ref)
                if (
                    not isinstance(record, dict)
                    or _text(record.get("id")) != source_ref
                    or not _text(record.get("sourceType"))
                ):
                    return None
            plan = _selected_simc_writer_plan(
                selection,
                variant,
                options,
                dependencies.get("capabilityRevision"),
            )
            if plan is None:
                return None
            plans[_text(slot)] = plan
        return plans

    transitional_plans = authority_plans(
        parsed_transitional_intent,
        transitional_resolved_slots,
        transitional_authority,
    )
    candidate_plans = authority_plans(
        parsed_candidate_intent,
        candidate_resolved_slots,
        candidate_authority,
    )
    if transitional_plans is None or candidate_plans is None:
        return False
    transitional_items = transitional_authority["itemsById"]
    candidate_items = candidate_authority["itemsById"]
    transitional_variants = transitional_authority["variantsByKey"]
    candidate_variants = candidate_authority["variantsByKey"]
    transitional_options = transitional_authority["optionsById"]
    candidate_options = candidate_authority["optionsById"]
    migration_simc_fields_by_slot: dict[str, set[str]] = {}
    for slot, candidate_selection in parsed_candidate_intent["slots"].items():
        transitional_selection = parsed_transitional_intent["slots"].get(slot)
        if not isinstance(transitional_selection, dict):
            return False
        old_item = transitional_items.get(transitional_selection.get("itemId"))
        new_item = candidate_items.get(candidate_selection.get("itemId"))
        old_variant = transitional_variants.get(transitional_selection.get("variantKey"))
        new_variant = candidate_variants.get(candidate_selection.get("variantKey"))
        if (
            not isinstance(old_item, dict)
            or not isinstance(new_item, dict)
            or not isinstance(old_variant, dict)
            or not isinstance(new_variant, dict)
            or old_item.get("simcOptions") != new_item.get("simcOptions")
            or old_variant.get("simcOptions") != new_variant.get("simcOptions")
        ):
            return False
        for selection_field in ("craftedOptionId", "catalystOptionId"):
            option_id = _text(candidate_selection.get(selection_field))
            if option_id != _text(transitional_selection.get(selection_field)):
                return False
            if option_id and (
                not isinstance(transitional_options.get(option_id), dict)
                or not isinstance(candidate_options.get(option_id), dict)
                or transitional_options[option_id].get("simcOptions")
                != candidate_options[option_id].get("simcOptions")
            ):
                return False
        migration_simc_fields_by_slot[_text(slot)] = (
            set(transitional_plans[_text(slot)]["migrationFields"])
            | set(candidate_plans[_text(slot)]["migrationFields"])
        )

    def strict_projection(
        snapshot: dict[str, Any],
        *,
        expected_intent: dict[str, Any],
        authority_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        value = copy.deepcopy(snapshot)
        parsed_intent = expected_intent
        expected_eligibility = parsed_intent["eligibilityContext"]
        expected_selection_signature = gear_contracts.selection_signature(
            parsed_intent,
            expected_eligibility,
        )
        if (
            _text(value.get("contractRevision"))
            != gear_resolver.RESOLVED_SNAPSHOT_CONTRACT_REVISION
            or _text(value.get("status")) != "verified"
            or _text(value.get("selectionSignature"))
            != expected_selection_signature
            or not _text(value.get("resolvedGearSignature"))
            or value.get("eligibilityContext") != expected_eligibility
            or value.get("problems") != []
        ):
            return None
        aggregate_legality = value.get("aggregateLegality")
        expected_rule_results = [
            {
                "ruleId": rule.rule_id,
                "ruleRevision": rule.rule_revision,
                "status": "verified",
                "problems": [],
                "order": rule.order,
            }
            for rule in gear_resolver.ordered_rule_matrix()
        ]
        if (
            aggregate_legality
            != {"status": "verified", "problemCodes": []}
            or value.get("ruleResults") != expected_rule_results
        ):
            return None

        dependency_vector = value.get("dependencyVector")
        if (
            not isinstance(dependency_vector, dict)
            or gear_contracts.validate_dependency_vector(dependency_vector)
        ):
            return None
        snapshot_signature = _text(value.get("resolvedGearSignature"))
        snapshot_dependencies = copy.deepcopy(dependency_vector)
        if snapshot_signature != gear_contracts.resolved_gear_signature(
            expected_selection_signature,
            snapshot_dependencies,
        ):
            return None
        dependency_vector["gearCatalogReleaseId"] = "__socket_capacity_migration__"
        dependency_vector["gearCatalogRevision"] = "__socket_capacity_migration__"
        dependency_vector["capabilityRevision"] = "__socket_capacity_migration__"
        value.pop("selectionSignature", None)
        value.pop("resolvedGearSignature", None)

        resolved_slots = value.get("resolvedSlots")
        constraints = value.get("constraints")
        constraint_slots = (
            constraints.get("slots")
            if isinstance(constraints, dict)
            and isinstance(constraints.get("slots"), dict)
            else None
        )
        ledger = value.get("evidenceLedger")
        if (
            not isinstance(resolved_slots, dict)
            or set(resolved_slots) != set(parsed_intent["slots"])
            or not isinstance(constraints, dict)
            or constraint_slots is None
            or set(constraint_slots) != set(resolved_slots)
            or not isinstance(ledger, dict)
            or _text(ledger.get("contractRevision"))
            != gear_evidence_ledger.EVIDENCE_LEDGER_CONTRACT_REVISION
            or ledger.get("problems") != []
        ):
            return None

        profile_readiness = value.get("profileReadiness")
        required_slots = (
            profile_readiness.get("requiredSlots")
            if isinstance(profile_readiness, dict)
            else None
        )
        ready_slots = (
            profile_readiness.get("readySlots")
            if isinstance(profile_readiness, dict)
            else None
        )
        expected_required_slots = None
        if authority_context is not None:
            rule_parameters = authority_context.get("ruleParameters")
            raw_required_slots = (
                rule_parameters.get("requiredSlots")
                if isinstance(rule_parameters, dict)
                else None
            )
            weapon_modes = (
                rule_parameters.get("weaponModesByClassSpec")
                if isinstance(rule_parameters, dict)
                else None
            )
            if (
                not isinstance(raw_required_slots, list)
                or any(
                    not isinstance(slot, str) or not slot.strip()
                    for slot in raw_required_slots
                )
                or not isinstance(weapon_modes, dict)
            ):
                return None
            expected_required_slots = sorted(set(raw_required_slots))
            requested_spec = (
                f"{_text(expected_eligibility.get('classKey'))}:"
                f"{_text(expected_eligibility.get('specKey'))}"
            )
            main_hand = resolved_slots.get("main_hand")
            main_hand = main_hand if isinstance(main_hand, dict) else {}
            if _text(main_hand.get("handedness")) == "ranged" or (
                _text(main_hand.get("handedness")) == "two_hand"
                and _text(weapon_modes.get(requested_spec)) != "dual_wield_2h"
            ):
                expected_required_slots = [
                    slot for slot in expected_required_slots if slot != "off_hand"
                ]
        if (
            not isinstance(profile_readiness, dict)
            or set(profile_readiness)
            != {
                "status",
                "simcReady",
                "requiredSlots",
                "readySlots",
                "serializerRevision",
                "simcRuntimeRevision",
                "problems",
            }
            or profile_readiness.get("status") != "verified"
            or profile_readiness.get("simcReady") is not True
            or profile_readiness.get("problems") != []
            or not isinstance(required_slots, list)
            or not isinstance(ready_slots, list)
            or any(
                not isinstance(slot, str) or not slot.strip()
                for slot in [*required_slots, *ready_slots]
            )
            or required_slots != ready_slots
            or required_slots != sorted(set(required_slots))
            or not required_slots
            or not set(required_slots).issubset(resolved_slots)
            or (
                expected_required_slots is not None
                and required_slots != expected_required_slots
            )
            or _text(profile_readiness.get("serializerRevision"))
            != _text(snapshot_dependencies.get("serializerRevision"))
            or _text(profile_readiness.get("simcRuntimeRevision"))
            != _text(snapshot_dependencies.get("simcRuntimeRevision"))
        ):
            return None

        expected_static_attributes: dict[str, int | float] = {}
        expected_serializer_items = []
        expected_set_counts: dict[str, int] = {}
        for slot in sorted(resolved_slots):
            resolved = resolved_slots.get(slot)
            if not isinstance(resolved, dict):
                return None
            resolved_stats = resolved.get("resolvedStats")
            simc_options = resolved.get("simcOptions")
            if (
                not isinstance(resolved_stats, dict)
                or not isinstance(simc_options, dict)
                or resolved.get("problems") != []
                or resolved.get("legality")
                != {"status": "verified", "problemCodes": []}
            ):
                return None
            for stat, amount in resolved_stats.items():
                if (
                    not isinstance(stat, str)
                    or not stat.strip()
                    or not isinstance(amount, (int, float))
                    or isinstance(amount, bool)
                ):
                    return None
                expected_static_attributes[stat] = (
                    expected_static_attributes.get(stat, 0) + amount
                )
            item_set_id = _text(resolved.get("itemSetId"))
            if item_set_id:
                expected_set_counts[item_set_id] = (
                    expected_set_counts.get(item_set_id, 0) + 1
                )
            expected_serializer_items.append({
                "slot": _text(slot),
                "itemId": _text(resolved.get("itemId")),
                "variantKey": _text(resolved.get("variantKey")),
                "simcOptions": copy.deepcopy(simc_options),
            })
        expected_static_attributes = {
            key: expected_static_attributes[key]
            for key in sorted(expected_static_attributes)
        }
        expected_set_counts = {
            key: expected_set_counts[key] for key in sorted(expected_set_counts)
        }
        set_state = value.get("setState")
        if (
            value.get("staticAttributes") != expected_static_attributes
            or value.get("serializerInput")
            != {"gearItems": expected_serializer_items}
            or not isinstance(set_state, dict)
            or set(set_state) != {"itemSetCounts", "activeDynamicEffects"}
            or set_state.get("itemSetCounts") != expected_set_counts
            or not isinstance(set_state.get("activeDynamicEffects"), list)
        ):
            return None

        claims = ledger.get("claims")
        claim_groups = ledger.get("claimGroups")
        evidence_records = ledger.get("evidenceRecordsById")
        if (
            not isinstance(claims, list)
            or not isinstance(claim_groups, dict)
            or not isinstance(evidence_records, dict)
        ):
            return None
        claim_keys_by_id: dict[str, str] = {}
        claims_by_key: dict[str, dict[str, Any]] = {}
        expected_claim_groups = {
            group: [] for group in gear_evidence_ledger.CLAIM_GROUPS
        }
        for claim in claims:
            if not isinstance(claim, dict):
                return None
            claim_id = _text(claim.get("claimId"))
            claim_key = _text(claim.get("claimKey"))
            claim_group = _text(claim.get("group"))
            if (
                not claim_id
                or not claim_key
                or claim_id in claim_keys_by_id
                or claim_key in claims_by_key
                or claim_group not in expected_claim_groups
                or _text(claim.get("status")) != "verified"
                or claim.get("problems") != []
                or _text(claim.get("ruleRevision"))
                != _text(snapshot_dependencies.get("gearRuleRevision"))
                or _text(claim.get("resolvedSignature")) != snapshot_signature
                or claim.get("dependencyVector") != snapshot_dependencies
            ):
                return None
            try:
                rebuilt_claim = gear_evidence_ledger.evidence_claim(
                    claim_group,
                    claim_key,
                    claim.get("value"),
                    status="verified",
                    source_ref_ids=claim.get("sourceRefIds") or [],
                    rule_revision=_text(claim.get("ruleRevision")),
                    resolved_signature=snapshot_signature,
                    dependency_vector=snapshot_dependencies,
                    depends_on=claim.get("dependsOn") or [],
                    problems=[],
                )
            except (TypeError, ValueError):
                return None
            if claim != rebuilt_claim:
                return None
            claim_keys_by_id[claim_id] = claim_key
            claims_by_key[claim_key] = claim
            expected_claim_groups[claim_group].append(claim_id)
            if claim_key.startswith("slot:"):
                claim_parts = claim_key.split(":")
                claim_slot = claim_parts[1] if len(claim_parts) == 3 else ""
                claim_kind = claim_parts[2] if len(claim_parts) == 3 else ""
                claim_resolved = (
                    resolved_slots.get(claim_slot)
                    if isinstance(resolved_slots.get(claim_slot), dict)
                    else {}
                )
                expected_claim_value = None
                if claim_kind == "identity_options":
                    expected_claim_value = {
                        "itemId": claim_resolved.get("itemId"),
                        "variantKey": claim_resolved.get("variantKey"),
                        "selectedOptions": copy.deepcopy(
                            claim_resolved.get("selectedOptions") or {}
                        ),
                    }
                elif claim_kind == "provenance":
                    expected_claim_value = {
                        "resolutionStages": copy.deepcopy(
                            claim_resolved.get("resolutionStages") or []
                        ),
                        "sourceRefIds": copy.deepcopy(
                            claim_resolved.get("sourceRefIds") or []
                        ),
                    }
                elif claim_kind == "static_attributes":
                    expected_claim_value = copy.deepcopy(
                        claim_resolved.get("resolvedStats") or {}
                    )
                if expected_claim_value is None or claim.get("value") != expected_claim_value:
                    return None
        if claim_groups != expected_claim_groups:
            return None

        def normalized_ids(values: Any) -> list[str] | None:
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value.strip()
                for value in values
            ):
                return None
            return sorted(set(values))

        expected_slot_claim_keys = {
            f"slot:{slot}:{claim_kind}"
            for slot in resolved_slots
            for claim_kind in (
                "identity_options",
                "provenance",
                "static_attributes",
            )
        }
        expected_rule_claim_keys = {
            f"rule:{result['ruleId']}" for result in expected_rule_results
        }
        expected_aggregate_claim_keys = {
            "aggregate:legality",
            "aggregate:set_state",
            "aggregate:static_attributes",
            "aggregate:profile_readiness",
        }
        if set(claims_by_key) != (
            expected_slot_claim_keys
            | expected_rule_claim_keys
            | expected_aggregate_claim_keys
        ):
            return None

        slot_claim_ids_by_kind: dict[str, list[str]] = {
            "identity_options": [],
            "provenance": [],
            "static_attributes": [],
        }
        for slot, resolved in resolved_slots.items():
            raw_slot_sources = resolved.get("sourceRefIds")
            raw_linked_claim_ids = resolved.get("evidenceClaimIds")
            slot_sources = normalized_ids(raw_slot_sources)
            linked_claim_ids = normalized_ids(raw_linked_claim_ids)
            if (
                slot_sources is None
                or linked_claim_ids is None
                or raw_slot_sources != slot_sources
                or raw_linked_claim_ids != linked_claim_ids
            ):
                return None
            expected_linked_ids = []
            for claim_kind, claim_group in (
                ("identity_options", "identity_options"),
                ("provenance", "provenance"),
                ("static_attributes", "static_attributes"),
            ):
                claim = claims_by_key[f"slot:{slot}:{claim_kind}"]
                if (
                    claim.get("group") != claim_group
                    or normalized_ids(claim.get("sourceRefIds")) != slot_sources
                    or claim.get("dependsOn") != []
                ):
                    return None
                claim_id = _text(claim.get("claimId"))
                expected_linked_ids.append(claim_id)
                slot_claim_ids_by_kind[claim_kind].append(claim_id)
            if linked_claim_ids != sorted(expected_linked_ids):
                return None

        rule_source_refs: list[str] | None = None
        rule_claim_ids = []
        for result in expected_rule_results:
            claim = claims_by_key[f"rule:{result['ruleId']}"]
            claim_sources = normalized_ids(claim.get("sourceRefIds"))
            if claim_sources is None:
                return None
            if rule_source_refs is None:
                rule_source_refs = claim_sources
            if (
                claim.get("group") != "legality"
                or claim.get("value")
                != {"order": result["order"], "status": "verified"}
                or claim.get("dependsOn") != []
                or claim_sources != rule_source_refs
            ):
                return None
            rule_claim_ids.append(_text(claim.get("claimId")))
        rule_source_refs = rule_source_refs or []

        set_source_refs = []
        for effect in set_state["activeDynamicEffects"]:
            if not isinstance(effect, dict):
                return None
            effect_sources = normalized_ids(effect.get("sourceRefIds"))
            if (
                effect_sources is None
                or effect.get("sourceRefIds") != effect_sources
            ):
                return None
            set_source_refs.extend(effect_sources)
        set_source_refs = sorted(set(set_source_refs))

        def aggregate_claim_matches(
            claim_key: str,
            *,
            group: str,
            claim_value: Any,
            source_refs: list[str],
            depends_on: list[str],
        ) -> bool:
            claim = claims_by_key.get(claim_key)
            return bool(
                isinstance(claim, dict)
                and claim.get("group") == group
                and claim.get("value") == claim_value
                and normalized_ids(claim.get("sourceRefIds")) == source_refs
                and normalized_ids(claim.get("dependsOn"))
                == sorted(set(depends_on))
            )

        aggregate_legality_claim = claims_by_key["aggregate:legality"]
        aggregate_static_claim = claims_by_key["aggregate:static_attributes"]
        if (
            not aggregate_claim_matches(
                "aggregate:legality",
                group="legality",
                claim_value={"legal": True},
                source_refs=rule_source_refs,
                depends_on=rule_claim_ids,
            )
            or not aggregate_claim_matches(
                "aggregate:set_state",
                group="provenance",
                claim_value=set_state,
                source_refs=set_source_refs,
                depends_on=slot_claim_ids_by_kind["provenance"],
            )
            or not aggregate_claim_matches(
                "aggregate:static_attributes",
                group="static_attributes",
                claim_value=expected_static_attributes,
                source_refs=[],
                depends_on=slot_claim_ids_by_kind["static_attributes"],
            )
            or not aggregate_claim_matches(
                "aggregate:profile_readiness",
                group="profile_executability",
                claim_value=profile_readiness,
                source_refs=sorted(set(rule_source_refs + set_source_refs)),
                depends_on=[
                    _text(aggregate_legality_claim.get("claimId")),
                    _text(aggregate_static_claim.get("claimId")),
                ],
            )
        ):
            return None
        try:
            rebuilt_ledger = gear_evidence_ledger.build_evidence_ledger(
                copy.deepcopy(claims),
                copy.deepcopy(evidence_records),
            )
        except (TypeError, ValueError):
            return None
        if rebuilt_ledger != ledger:
            return None

        globally_selected_editor_ids: dict[str, set[str]] = {
            "gem": set(),
            "enchant": set(),
            "embellishment": set(),
        }
        for intent_selection in parsed_intent["slots"].values():
            globally_selected_editor_ids["gem"].update(
                _text(option_id)
                for option_id in intent_selection.get("gemOptionIds") or []
                if _text(option_id)
            )
            for option_type, selection_field in (
                ("enchant", "enchantOptionId"),
                ("embellishment", "embellishmentOptionId"),
            ):
                option_id = _text(intent_selection.get(selection_field))
                if option_id:
                    globally_selected_editor_ids[option_type].add(option_id)

        selected_ids_by_slot: dict[str, dict[str, list[str]]] = {}
        migration_selected_ids_by_slot: dict[str, set[str]] = {}
        enhancement_delta_sums_by_slot: dict[str, dict[str, int | float]] = {}
        enhancement_deltas_by_slot: dict[str, dict[str, list[dict[str, Any]]]] = {}
        all_selected_ids: set[str] = set()
        all_migration_selected_ids: set[str] = set()
        for slot, resolved in resolved_slots.items():
            if not isinstance(resolved, dict):
                return None
            selected = resolved.get("selectedOptions")
            capabilities = resolved.get("effectiveCapabilities")
            stat_deltas = resolved.get("statDeltas")
            if (
                not isinstance(selected, dict)
                or not isinstance(capabilities, dict)
                or not isinstance(stat_deltas, dict)
            ):
                return None
            expected_selection = parsed_intent["slots"].get(slot)
            expected_selected_options = {
                field: copy.deepcopy(expected_selection.get(field))
                for field in (
                    "gemOptionIds",
                    "enchantOptionId",
                    "embellishmentOptionId",
                    "craftedOptionId",
                    "catalystOptionId",
                )
            }
            if (
                not isinstance(expected_selection, dict)
                or _text(resolved.get("itemId"))
                != _text(expected_selection.get("itemId"))
                or _text(resolved.get("variantKey"))
                != _text(expected_selection.get("variantKey"))
                or selected != expected_selected_options
            ):
                return None
            raw_gems = selected.get("gemOptionIds")
            if not isinstance(raw_gems, list) or any(
                not isinstance(option_id, str) or not option_id.strip()
                for option_id in raw_gems
            ):
                return None
            singles = {}
            for field in (
                "enchantOptionId",
                "embellishmentOptionId",
                "craftedOptionId",
                "catalystOptionId",
            ):
                raw_option_id = selected.get(field, "")
                if not isinstance(raw_option_id, str):
                    return None
                singles[field] = raw_option_id.strip()
            selected_by_type = {
                "gem": [option_id.strip() for option_id in raw_gems],
                "enchant": [singles["enchantOptionId"]] if singles["enchantOptionId"] else [],
                "embellishment": (
                    [singles["embellishmentOptionId"]]
                    if singles["embellishmentOptionId"]
                    else []
                ),
                "crafted": [singles["craftedOptionId"]] if singles["craftedOptionId"] else [],
                "catalyst": [singles["catalystOptionId"]] if singles["catalystOptionId"] else [],
            }
            selected_ids_by_slot[_text(slot)] = selected_by_type
            selected_option_ids = [
                option_id
                for option_ids in selected_by_type.values()
                for option_id in option_ids
            ]
            migration_selected_option_ids = {
                option_id
                for option_type in ("gem", "enchant", "embellishment")
                for option_id in selected_by_type[option_type]
            }
            migration_selected_ids_by_slot[_text(slot)] = (
                migration_selected_option_ids
            )
            all_selected_ids.update(selected_option_ids)
            all_migration_selected_ids.update(migration_selected_option_ids)

            allowed_fields = {
                "gem": "allowedGemOptionIds",
                "enchant": "allowedEnchantOptionIds",
                "embellishment": "allowedEmbellishmentOptionIds",
                "crafted": "allowedCraftedOptionIds",
                "catalyst": "allowedCatalystOptionIds",
            }
            for option_type, field in allowed_fields.items():
                allowed = capabilities.get(field, [])
                if (
                    not isinstance(allowed, list)
                    or any(
                        not isinstance(option_id, str) or not option_id.strip()
                        for option_id in allowed
                    )
                    or len(allowed) != len(set(allowed))
                ):
                    return None
                if option_type in {"gem", "enchant", "embellishment"}:
                    selected_set = set(selected_by_type[option_type])
                    allowed_set = set(allowed)
                    if (
                        not selected_set.issubset(allowed_set)
                        or not allowed_set.issubset(
                            globally_selected_editor_ids[option_type]
                        )
                    ):
                        return None
                if option_type in {"crafted", "catalyst"} and any(
                    option_id not in allowed
                    for option_id in selected_by_type[option_type]
                ):
                    return None

            enhancements = stat_deltas.get("enhancements")
            if not isinstance(enhancements, list):
                return None
            enhancement_ids = []
            enhancement_delta_sums: dict[str, int | float] = {}
            enhancement_deltas_by_option: dict[str, list[dict[str, Any]]] = {}
            for enhancement in enhancements:
                if (
                    not isinstance(enhancement, dict)
                    or set(enhancement) != {"optionId", "statDeltas"}
                    or not _text(enhancement.get("optionId"))
                    or not isinstance(enhancement.get("statDeltas"), dict)
                ):
                    return None
                enhancement_ids.append(_text(enhancement.get("optionId")))
                enhancement_deltas_by_option.setdefault(
                    _text(enhancement.get("optionId")),
                    [],
                ).append(copy.deepcopy(enhancement["statDeltas"]))
                for stat, delta in enhancement["statDeltas"].items():
                    if (
                        not isinstance(stat, str)
                        or not stat.strip()
                        or not isinstance(delta, (int, float))
                        or isinstance(delta, bool)
                    ):
                        return None
                    if _text(enhancement.get("optionId")) in migration_selected_option_ids:
                        enhancement_delta_sums[stat] = (
                            enhancement_delta_sums.get(stat, 0) + delta
                        )
            if sorted(enhancement_ids) != sorted(selected_option_ids):
                return None
            enhancement_delta_sums_by_slot[_text(slot)] = {
                stat: enhancement_delta_sums[stat]
                for stat in sorted(enhancement_delta_sums)
                if enhancement_delta_sums[stat] != 0
            }
            enhancement_deltas_by_slot[_text(slot)] = enhancement_deltas_by_option

        normalized_resolved_stats_by_slot: dict[str, dict[str, int | float]] = {}
        normalized_static_attributes: dict[str, int | float] = {}
        for slot, resolved in resolved_slots.items():
            resolved_stats = resolved.get("resolvedStats")
            delta_sums = enhancement_delta_sums_by_slot[_text(slot)]
            if any(
                stat not in resolved_stats and delta != 0
                for stat, delta in delta_sums.items()
            ):
                return None
            normalized_stats = {}
            for stat, amount in resolved_stats.items():
                normalized_amount = amount - delta_sums.get(stat, 0)
                if normalized_amount != 0:
                    normalized_stats[stat] = normalized_amount
                    normalized_static_attributes[stat] = (
                        normalized_static_attributes.get(stat, 0)
                        + normalized_amount
                    )
            normalized_resolved_stats_by_slot[_text(slot)] = normalized_stats
        normalized_static_attributes = {
            stat: normalized_static_attributes[stat]
            for stat in sorted(normalized_static_attributes)
            if normalized_static_attributes[stat] != 0
        }

        option_ref_ids: dict[str, str] = {}
        option_records_by_id: dict[str, dict[str, Any]] = {}
        for record_id, record in evidence_records.items():
            if not isinstance(record, dict):
                return None
            option_id = _text(record.get("optionId"))
            if not option_id:
                continue
            normalized_record_id = _text(record_id)
            if (
                option_id in option_records_by_id
                or normalized_record_id != f"evidence:pg:option:{option_id}"
                or _text(record.get("id")) != normalized_record_id
            ):
                return None
            option_ref_ids[normalized_record_id] = option_id
            option_records_by_id[option_id] = record
        for option_id in all_selected_ids:
            record = option_records_by_id.get(option_id)
            if (
                not isinstance(record, dict)
                or set(record)
                != {"id", "optionId", "sourceType", "sourceRevision"}
                or _text(record.get("sourceType"))
                not in _OPTION_EVIDENCE_SOURCE_TYPES
                or not _timestamp(record.get("sourceRevision"))
            ):
                return None
        if authority_context is not None:
            projection_options = authority_context.get("optionsById")
            projection_evidence = authority_context.get("evidenceRecordsById")
            if not isinstance(projection_options, dict) or not isinstance(
                projection_evidence,
                dict,
            ):
                return None
            for slot, selected_by_type in selected_ids_by_slot.items():
                deltas_by_option = enhancement_deltas_by_slot[slot]
                expected_types = {
                    "gem": {"gem"},
                    "enchant": {"enchant", "runeforge"},
                    "embellishment": {"embellishment"},
                    "crafted": {"crafted"},
                    "catalyst": {"catalyst"},
                }
                for option_type, option_ids in selected_by_type.items():
                    for option_id in set(option_ids):
                        option = projection_options.get(option_id)
                        evidence_id = f"evidence:pg:option:{option_id}"
                        evidence_record = evidence_records.get(evidence_id)
                        authority_record = projection_evidence.get(evidence_id)
                        if (
                            not isinstance(option, dict)
                            or _text(option.get("optionId")) != option_id
                            or _text(option.get("optionType"))
                            not in expected_types[option_type]
                            or evidence_id not in (option.get("sourceRefIds") or [])
                            or not isinstance(authority_record, dict)
                            or evidence_record != authority_record
                        ):
                            return None
                        expected_delta = option.get("statDeltas")
                        if not isinstance(expected_delta, dict):
                            return None
                        actual_deltas = deltas_by_option.get(option_id) or []
                        if (
                            len(actual_deltas) != option_ids.count(option_id)
                            or any(delta != expected_delta for delta in actual_deltas)
                        ):
                            return None
        projected_claims = []
        for claim in claims:
            dependencies = claim.get("dependsOn") or []
            if not isinstance(dependencies, list) or any(
                _text(dependency) not in claim_keys_by_id
                for dependency in dependencies
            ):
                return None
            source_refs = claim.get("sourceRefIds") or []
            if not isinstance(source_refs, list) or any(
                _text(source_ref) not in evidence_records
                for source_ref in source_refs
            ):
                return None
            claim_key = _text(claim.get("claimKey"))
            projected_value = copy.deepcopy(claim.get("value"))
            if claim_key.startswith("slot:"):
                claim_parts = claim_key.split(":")
                claim_kind = claim_parts[2] if len(claim_parts) == 3 else ""
                if claim_kind == "identity_options":
                    selected_options = (
                        projected_value.get("selectedOptions")
                        if isinstance(projected_value, dict)
                        and isinstance(projected_value.get("selectedOptions"), dict)
                        else None
                    )
                    if selected_options is None:
                        return None
                    for field in (
                        "gemOptionIds",
                        "enchantOptionId",
                        "embellishmentOptionId",
                    ):
                        selected_options.pop(field, None)
                elif claim_kind == "provenance":
                    if (
                        not isinstance(projected_value, dict)
                        or not isinstance(projected_value.get("sourceRefIds"), list)
                    ):
                        return None
                    projected_value["sourceRefIds"] = sorted(
                        source_ref
                        for source_ref in projected_value["sourceRefIds"]
                        if option_ref_ids.get(_text(source_ref))
                        not in all_migration_selected_ids
                    )
                elif claim_kind == "static_attributes":
                    projected_value = copy.deepcopy(
                        normalized_resolved_stats_by_slot.get(claim_parts[1], {})
                    )
            elif claim_key == "aggregate:static_attributes":
                projected_value = copy.deepcopy(normalized_static_attributes)
            projected_dependency_vector = copy.deepcopy(
                claim.get("dependencyVector")
            )
            for field in (
                "gearCatalogReleaseId",
                "gearCatalogRevision",
                "capabilityRevision",
            ):
                projected_dependency_vector[field] = "__socket_capacity_migration__"
            projected_claims.append({
                "claimKey": _text(claim.get("claimKey")),
                "group": _text(claim.get("group")),
                "status": _text(claim.get("status")),
                "problems": copy.deepcopy(claim.get("problems") or []),
                "value": projected_value,
                "ruleRevision": _text(claim.get("ruleRevision")),
                "resolvedSignature": "__socket_capacity_migration__",
                "dependencyVector": projected_dependency_vector,
                "dependsOn": sorted(
                    claim_keys_by_id[_text(dependency)]
                    for dependency in dependencies
                ),
                "sourceRefIds": sorted(
                    _text(source_ref)
                    for source_ref in source_refs
                    if option_ref_ids.get(_text(source_ref))
                    not in all_migration_selected_ids
                ),
            })
        projected_records = {}
        for record_id, record in evidence_records.items():
            if not isinstance(record, dict):
                return None
            option_id = _text(record.get("optionId"))
            if option_id and option_id in all_migration_selected_ids:
                continue
            projected_record = copy.deepcopy(record)
            projected_record.pop("updatedAt", None)
            projected_records[_text(record_id)] = projected_record
        value["evidenceLedger"] = {
            "contractRevision": _text(ledger.get("contractRevision")),
            "claims": sorted(
                projected_claims,
                key=lambda claim: (claim["group"], claim["claimKey"]),
            ),
            "claimGroups": {
                group: [claim_keys_by_id[claim_id] for claim_id in claim_ids]
                for group, claim_ids in expected_claim_groups.items()
            },
            "evidenceRecordsById": projected_records,
            "problems": [],
        }

        selected_embellishments = 0
        for slot, resolved in resolved_slots.items():
            slot_key = _text(slot)
            selected_by_type = selected_ids_by_slot[slot_key]
            selected_option_ids = {
                option_id
                for option_ids in selected_by_type.values()
                for option_id in option_ids
            }
            migration_selected_option_ids = migration_selected_ids_by_slot[
                slot_key
            ]
            selected_embellishments += len(selected_by_type["embellishment"])
            source_refs = resolved.get("sourceRefIds")
            evidence_claim_ids = resolved.get("evidenceClaimIds")
            if (
                not isinstance(source_refs, list)
                or any(not isinstance(source_ref, str) for source_ref in source_refs)
                or not isinstance(evidence_claim_ids, list)
                or any(_text(claim_id) not in claim_keys_by_id for claim_id in evidence_claim_ids)
            ):
                return None
            selected_option_ref_ids = {
                f"evidence:pg:option:{option_id}"
                for option_id in selected_option_ids
            }
            migration_selected_option_ref_ids = {
                f"evidence:pg:option:{option_id}"
                for option_id in migration_selected_option_ids
            }
            identity_claim = claims_by_key.get(f"slot:{slot_key}:identity_options")
            identity_claim_refs = (
                set(identity_claim.get("sourceRefIds") or [])
                if isinstance(identity_claim, dict)
                else set()
            )
            if (
                not selected_option_ref_ids.issubset(set(source_refs))
                or not selected_option_ref_ids.issubset(identity_claim_refs)
            ):
                return None
            resolved["sourceRefIds"] = sorted(
                source_ref
                for source_ref in source_refs
                if _text(source_ref) not in migration_selected_option_ref_ids
            )
            resolved["evidenceClaimIds"] = sorted(
                claim_keys_by_id[_text(claim_id)]
                for claim_id in evidence_claim_ids
            )
            selected = resolved["selectedOptions"]
            for field in (
                "gemOptionIds",
                "enchantOptionId",
                "embellishmentOptionId",
            ):
                selected.pop(field, None)
            resolved["statDeltas"]["enhancements"] = [
                enhancement
                for enhancement in resolved["statDeltas"]["enhancements"]
                if _text(enhancement.get("optionId"))
                not in migration_selected_option_ids
            ]
            resolved["resolvedStats"] = copy.deepcopy(
                normalized_resolved_stats_by_slot[slot_key]
            )
            for simc_field in migration_simc_fields_by_slot.get(slot_key, set()):
                resolved["simcOptions"].pop(simc_field, None)
            capabilities = resolved["effectiveCapabilities"]
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
            ):
                capabilities.pop(field, None)

            constraint = constraint_slots.get(slot)
            if not isinstance(constraint, dict):
                return None
            socket_count = capabilities.get("socketCount")
            socket_remaining = constraint.get("socketRemaining")
            if (
                not isinstance(socket_count, int)
                or isinstance(socket_count, bool)
                or socket_count < 0
                or constraint.get("socketCount") != socket_count
                or constraint.get("canEnchant")
                is not (capabilities.get("canEnchant") is True)
                or constraint.get("canEmbellish")
                is not (capabilities.get("canEmbellish") is True)
                or socket_remaining != max(
                    0,
                    socket_count - len(selected_by_type["gem"]),
                )
                or constraint.get("hasSelectedEnchant")
                is not bool(selected_by_type["enchant"])
                or constraint.get("hasSelectedEmbellishment")
                is not bool(selected_by_type["embellishment"])
            ):
                return None
            for field in (
                "socketRemaining",
                "hasSelectedEnchant",
                "hasSelectedEmbellishment",
            ):
                constraint.pop(field, None)

        built_in_used = constraints.get("embellishmentBuiltInUsed", 0)
        selected_used = constraints.get("embellishmentSelectedUsed")
        total_used = constraints.get("embellishmentUsed")
        if (
            not isinstance(built_in_used, int)
            or isinstance(built_in_used, bool)
            or built_in_used < 0
            or selected_used != selected_embellishments
            or total_used != built_in_used + selected_embellishments
        ):
            return None
        constraints.pop("embellishmentSelectedUsed", None)
        constraints.pop("embellishmentUsed", None)
        value["staticAttributes"] = copy.deepcopy(normalized_static_attributes)
        value["serializerInput"] = {
            "gearItems": [
                {
                    "slot": slot,
                    "itemId": resolved_slots[slot]["itemId"],
                    "variantKey": resolved_slots[slot]["variantKey"],
                    "simcOptions": copy.deepcopy(
                        resolved_slots[slot]["simcOptions"]
                    ),
                }
                for slot in sorted(resolved_slots)
            ]
        }
        return value

    transitional = strict_projection(
        transitional_value,
        expected_intent=parsed_transitional_intent,
        authority_context=transitional_authority,
    )
    candidate = strict_projection(
        candidate_value,
        expected_intent=parsed_candidate_intent,
        authority_context=candidate_authority,
    )
    if transitional is None or candidate is None:
        return False
    transitional_slots = transitional.get("resolvedSlots") if isinstance(transitional.get("resolvedSlots"), dict) else {}
    candidate_slots = candidate.get("resolvedSlots") if isinstance(candidate.get("resolvedSlots"), dict) else {}
    transitional_constraints = transitional.get("constraints") if isinstance(transitional.get("constraints"), dict) else {}
    candidate_constraints = candidate.get("constraints") if isinstance(candidate.get("constraints"), dict) else {}
    transitional_constraint_slots = transitional_constraints.get("slots") if isinstance(transitional_constraints.get("slots"), dict) else {}
    candidate_constraint_slots = candidate_constraints.get("slots") if isinstance(candidate_constraints.get("slots"), dict) else {}
    upgraded_slots = []
    for slot in sorted(set(transitional_slots) | set(candidate_slots)):
        old_slot = transitional_slots.get(slot) if isinstance(transitional_slots.get(slot), dict) else {}
        new_slot = candidate_slots.get(slot) if isinstance(candidate_slots.get(slot), dict) else {}
        old_effective = old_slot.get("effectiveCapabilities") if isinstance(old_slot.get("effectiveCapabilities"), dict) else {}
        new_effective = new_slot.get("effectiveCapabilities") if isinstance(new_slot.get("effectiveCapabilities"), dict) else {}
        old_constraint = transitional_constraint_slots.get(slot) if isinstance(transitional_constraint_slots.get(slot), dict) else {}
        new_constraint = candidate_constraint_slots.get(slot) if isinstance(candidate_constraint_slots.get(slot), dict) else {}
        old_effective_count = old_effective.get("socketCount")
        new_effective_count = new_effective.get("socketCount")
        old_constraint_count = old_constraint.get("socketCount")
        new_constraint_count = new_constraint.get("socketCount")
        if old_effective_count != old_constraint_count or new_effective_count != new_constraint_count:
            return False
        if old_effective_count == new_effective_count:
            continue
        if migration_mode != "socket_capacity":
            return False
        if old_effective_count != 1 or new_effective_count != 2:
            return False
        upgraded_slots.append(slot)
        old_effective.pop("socketCount", None)
        new_effective.pop("socketCount", None)
        old_constraint.pop("socketCount", None)
        new_constraint.pop("socketCount", None)
    expected_capacity_change = (
        not upgraded_slots
        if migration_mode == "editor_only"
        else bool(upgraded_slots)
    )
    return expected_capacity_change and transitional == candidate


def _legacy_to_v2_socket_capacity_migration_equivalent(
    transitional_snapshot: Any,
    candidate_snapshot: Any,
    *,
    transitional_gear_release_id: Any,
    transitional_gear_catalog_revision: Any,
    candidate_gear_release_id: Any,
    transitional_authority_context: Any,
    candidate_authority_context: Any,
    transitional_intent: Any,
    candidate_intent: Any,
) -> bool:
    """Allow only paired, evidence-loaded one-to-two socket upgrades."""

    return _legacy_to_v2_enhancement_migration_equivalent(
        transitional_snapshot,
        candidate_snapshot,
        transitional_gear_release_id=transitional_gear_release_id,
        transitional_gear_catalog_revision=transitional_gear_catalog_revision,
        candidate_gear_release_id=candidate_gear_release_id,
        transitional_authority_context=transitional_authority_context,
        candidate_authority_context=candidate_authority_context,
        transitional_intent=transitional_intent,
        candidate_intent=candidate_intent,
        migration_mode="socket_capacity",
    )


def _current_v2_radiant_jewelbinder_capacity_migration_equivalent(
    transitional_snapshot: Any,
    candidate_snapshot: Any,
    *,
    transitional_authority_context: Any,
    candidate_authority_context: Any,
    transitional_intent: Any,
    candidate_intent: Any,
) -> bool:
    """Allow only sealed PvE Jewelbinder empty-slot additions within v2.

    The v2 capability revision can gain a newly proved current-season PvE
    catalog fact without changing a player's observed configuration.  This is
    deliberately narrower than a generic socket upgrade: every changed slot
    must be head/wrist/waist, change exactly 0 -> 1, remain ungemmed, and carry
    the loader-projected proof from the exact candidate Gear Release.
    """

    old = transitional_snapshot if isinstance(transitional_snapshot, dict) else {}
    new = candidate_snapshot if isinstance(candidate_snapshot, dict) else {}
    old_authority = (
        transitional_authority_context
        if isinstance(transitional_authority_context, dict)
        else {}
    )
    new_authority = (
        candidate_authority_context
        if isinstance(candidate_authority_context, dict)
        else {}
    )
    parsed_old, old_issues = gear_contracts.parse_selection_intent(
        transitional_intent
    )
    parsed_new, new_issues = gear_contracts.parse_selection_intent(
        candidate_intent
    )
    if (
        old_issues
        or new_issues
        or gear_contracts.validate_authority_context(parsed_old, old_authority)
        or gear_contracts.validate_authority_context(parsed_new, new_authority)
        or _non_enhancement_selection_projection(parsed_old)
        != _non_enhancement_selection_projection(parsed_new)
        or _enhancement_selection_projection(parsed_old)
        != _enhancement_selection_projection(parsed_new)
    ):
        return False

    old_dependencies = (
        old.get("dependencyVector")
        if isinstance(old.get("dependencyVector"), dict)
        else {}
    )
    new_dependencies = (
        new.get("dependencyVector")
        if isinstance(new.get("dependencyVector"), dict)
        else {}
    )
    old_authority_dependencies = old_authority.get("dependencyVector")
    new_authority_dependencies = new_authority.get("dependencyVector")
    if (
        not isinstance(old_authority_dependencies, dict)
        or not isinstance(new_authority_dependencies, dict)
        or old_dependencies != old_authority_dependencies
        or new_dependencies != new_authority_dependencies
        or old_dependencies.get("capabilityRevision")
        != gear_socket_authority.CAPABILITY_REVISION
        or new_dependencies.get("capabilityRevision")
        != gear_socket_authority.CAPABILITY_REVISION
        or _text(old_dependencies.get("seasonRevision"))
        != _text(new_dependencies.get("seasonRevision"))
    ):
        return False

    old_normalized = copy.deepcopy(old)
    new_normalized = copy.deepcopy(new)
    old_resolved_slots = (
        old.get("resolvedSlots") if isinstance(old.get("resolvedSlots"), dict) else {}
    )
    new_resolved_slots = (
        new.get("resolvedSlots") if isinstance(new.get("resolvedSlots"), dict) else {}
    )
    old_constraint_slots = (
        (old.get("constraints") or {}).get("slots")
        if isinstance(old.get("constraints"), dict)
        and isinstance((old.get("constraints") or {}).get("slots"), dict)
        else {}
    )
    new_constraint_slots = (
        (new.get("constraints") or {}).get("slots")
        if isinstance(new.get("constraints"), dict)
        and isinstance((new.get("constraints") or {}).get("slots"), dict)
        else {}
    )
    candidate_items = new_authority.get("itemsById")
    candidate_items = candidate_items if isinstance(candidate_items, dict) else {}
    candidate_slots = parsed_new.get("slots") if isinstance(parsed_new, dict) else {}
    changed_slots: list[str] = []
    for slot in sorted(set(old_constraint_slots) | set(new_constraint_slots)):
        old_constraint = old_constraint_slots.get(slot)
        new_constraint = new_constraint_slots.get(slot)
        old_constraint = old_constraint if isinstance(old_constraint, dict) else {}
        new_constraint = new_constraint if isinstance(new_constraint, dict) else {}
        old_count = old_constraint.get("socketCount")
        new_count = new_constraint.get("socketCount")
        if old_count == new_count:
            continue
        if (
            slot not in {"head", "wrist", "waist"}
            or old_count != 0
            or new_count != 1
        ):
            return False
        old_resolved = old_resolved_slots.get(slot)
        new_resolved = new_resolved_slots.get(slot)
        old_resolved = old_resolved if isinstance(old_resolved, dict) else {}
        new_resolved = new_resolved if isinstance(new_resolved, dict) else {}
        old_effective = old_resolved.get("effectiveCapabilities")
        new_effective = new_resolved.get("effectiveCapabilities")
        old_effective = old_effective if isinstance(old_effective, dict) else {}
        new_effective = new_effective if isinstance(new_effective, dict) else {}
        selected = new_resolved.get("selectedOptions")
        selected = selected if isinstance(selected, dict) else {}
        selection = candidate_slots.get(slot)
        selection = selection if isinstance(selection, dict) else {}
        item_id = _text(selection.get("itemId"))
        candidate_item = candidate_items.get(item_id)
        if (
            old_effective.get("socketCount") != 0
            or new_effective.get("socketCount") != 1
            or selected.get("gemOptionIds") != []
            or _text(old_resolved.get("itemId")) != item_id
            or _text(new_resolved.get("itemId")) != item_id
            or not isinstance(candidate_item, dict)
            or candidate_item.get("radiantJewelbinderSocketEligibility") is not True
        ):
            return False
        changed_slots.append(slot)
        for normalized, normalized_slot in (
            (old_normalized, slot),
            (new_normalized, slot),
        ):
            resolved = (normalized.get("resolvedSlots") or {}).get(normalized_slot)
            if isinstance(resolved, dict) and isinstance(
                resolved.get("effectiveCapabilities"), dict
            ):
                resolved["effectiveCapabilities"].pop("socketCount", None)
            constraint = ((normalized.get("constraints") or {}).get("slots") or {}).get(
                normalized_slot
            )
            if isinstance(constraint, dict):
                constraint.pop("socketCount", None)
                constraint.pop("socketRemaining", None)

    return bool(changed_slots) and (
        gear_release.semantic_gear_signature(parsed_old, old_normalized)
        == gear_release.semantic_gear_signature(parsed_new, new_normalized)
    )


def _reference_contract_proof(
    candidate: dict[str, Any],
    intent: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    slots = intent.get("slots") if isinstance(intent.get("slots"), dict) else {}
    resolved_slots = (
        snapshot.get("resolvedSlots")
        if isinstance(snapshot.get("resolvedSlots"), dict)
        else {}
    )
    constraints = snapshot.get("constraints") if isinstance(snapshot.get("constraints"), dict) else {}
    constraint_slots = constraints.get("slots") if isinstance(constraints.get("slots"), dict) else {}
    socket_vector = [
        _int((constraint_slots.get(slot) or {}).get("socketCount"))
        for slot in _REFERENCE_SOCKET_SLOTS
    ]

    def selected(slot: str) -> dict[str, Any]:
        row = resolved_slots.get(slot) if isinstance(resolved_slots.get(slot), dict) else {}
        selected_options = row.get("selectedOptions") if isinstance(row.get("selectedOptions"), dict) else {}
        return selected_options

    intent_gems = sum(
        len(selection.get("gemOptionIds") or [])
        for selection in slots.values()
        if isinstance(selection, dict)
    )
    resolved_gems = sum(
        len(selected(slot).get("gemOptionIds") or [])
        for slot in resolved_slots
    )
    intent_enchants = sum(
        bool(_text(selection.get("enchantOptionId")))
        for selection in slots.values()
        if isinstance(selection, dict)
    )
    resolved_enchants = sum(
        bool(_text(selected(slot).get("enchantOptionId")))
        for slot in resolved_slots
    )
    enchant_max = sum(
        constraint.get("canEnchant") is True
        for constraint in constraint_slots.values()
        if isinstance(constraint, dict)
    )
    intent_embellishments = sum(
        bool(_text(selection.get("embellishmentOptionId")))
        for selection in slots.values()
        if isinstance(selection, dict)
    )
    resolved_embellishments = sum(
        bool(_text(selected(slot).get("embellishmentOptionId")))
        for slot in resolved_slots
    )
    failures = []
    if (
        _text(candidate.get("sourceKey")) != "raiderio_observed_profile"
        or not _text(candidate.get("profileHash"))
        or not _text(candidate.get("gearHash"))
    ):
        failures.append("identity")
    if (
        (intent.get("eligibilityContext") or {}).get("classKey") != "mage"
        or (intent.get("eligibilityContext") or {}).get("specKey") != "frost"
        or len(slots) != 15
    ):
        failures.append("gear")
    if socket_vector != _REFERENCE_SOCKET_VECTOR:
        failures.append("socket_vector")
    if intent_gems != 8 or resolved_gems != 8 or sum(socket_vector) != 8:
        failures.append("gems")
    if intent_enchants != 6 or resolved_enchants != 6 or enchant_max != 8:
        failures.append("enchants")
    if (
        intent_embellishments != 2
        or resolved_embellishments != 2
        or _int(constraints.get("embellishmentMax")) != 2
    ):
        failures.append("embellishments")
    return {
        "status": "blocked" if failures else "pass",
        "templateId": _REFERENCE_TEMPLATE_ID,
        "sourceKey": _text(candidate.get("sourceKey")),
        "profileHash": _text(candidate.get("profileHash")),
        "gearHash": _text(candidate.get("gearHash")),
        "socketSlots": list(_REFERENCE_SOCKET_SLOTS),
        "socketVector": socket_vector,
        "gems": {"used": resolved_gems, "max": sum(socket_vector)},
        "enchants": {"used": resolved_enchants, "max": enchant_max},
        "embellishments": {
            "used": resolved_embellishments,
            "max": _int(constraints.get("embellishmentMax")),
        },
        "failures": failures,
        "ninthGem": {"status": "not_run", "problemCodes": []},
    }


def run_release_shadow(
    store: Any,
    *,
    expected_specs: Iterable[tuple[str, str]],
    gear_release_id: str,
    community_release_id: str,
    simc_runtime_revision: str,
    level: int = 90,
    profile_context_by_spec: dict[str, dict[str, Any]] | None = None,
    compare_profiles: bool = True,
    expect_formal_active: bool = False,
    allow_degraded_empty: bool = False,
) -> dict[str, Any]:
    """Run an internal shadow matrix without changing public routing or state."""

    shadow_started = time.perf_counter()
    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    gear_id = _text(gear_release_id)
    community_id = _text(community_release_id)
    blockers: list[dict[str, Any]] = []
    if not expected or len(expected) > 40:
        blockers.append(_blocker("EXPECTED_SPEC_MATRIX_INVALID", detail="Expected matrix must contain 1 to 40 specs."))
    if not gear_id or not community_id:
        blockers.append(_blocker("CANDIDATE_RELEASE_BINDING_MISSING", detail="Both candidate release IDs are required."))
    if blockers:
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": blockers,
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": False,
        }

    try:
        pair = store.get_candidate_community_release(gear_id, community_id)
    except Exception:
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": [_blocker("CANDIDATE_RELEASE_READ_FAILED", detail="Candidate release pair is unavailable or invalid.")],
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": False,
        }
    if not isinstance(pair, dict):
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": [_blocker("CANDIDATE_RELEASE_READ_FAILED", detail="Candidate release pair is unavailable or invalid.")],
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": False,
        }

    pair_community = (
        pair.get("communityRelease")
        if isinstance(pair.get("communityRelease"), dict)
        else {}
    )
    if _text(pair_community.get("schemaRevision")) == "community-release-v2":
        return _run_projected_release_shadow(
            store,
            pair=pair,
            expected=expected,
            gear_release_id=gear_id,
            community_release_id=community_id,
            simc_runtime_revision=simc_runtime_revision,
            level=level,
            profile_context_by_spec=profile_context_by_spec,
            compare_profiles=compare_profiles,
        )

    winners_by_spec: dict[tuple[str, str], dict[str, Any]] = {}
    for winner in pair.get("winners") or []:
        if not isinstance(winner, dict):
            continue
        key = (_text(winner.get("classKey")), _text(winner.get("specKey")))
        if key in winners_by_spec:
            blockers.append(_blocker("DUPLICATE_CANDIDATE_WINNER", *key))
        winners_by_spec[key] = winner

    gear_descriptor = (
        pair.get("gearRelease")
        if isinstance(pair.get("gearRelease"), dict)
        else {}
    )
    gear_dependencies = (
        gear_descriptor.get("dependencyRevisions")
        if isinstance(gear_descriptor.get("dependencyRevisions"), dict)
        else {}
    )
    candidate_capability_revision = _text(
        gear_dependencies.get("capabilityRevision")
    )
    reference_proof_required = (
        candidate_capability_revision == gear_socket_authority.CAPABILITY_REVISION
    )
    if not candidate_capability_revision:
        blockers.append(_blocker(
            "CANDIDATE_CAPABILITY_REVISION_MISSING",
            detail="Candidate Gear Release capability revision is required.",
        ))
    elif (
        candidate_capability_revision
        not in gear_socket_authority.SUPPORTED_CAPABILITY_REVISIONS
    ):
        blockers.append(_blocker(
            "CANDIDATE_CAPABILITY_REVISION_UNSUPPORTED",
            detail="Candidate Gear Release capability revision is unsupported.",
        ))

    legacy_rows = []
    candidate_rows = [
        pg_gear_read_model_selectors.build_candidate_release_shadow_row(
            winner,
            gear_release_id=gear_id,
        )
        for winner in pair.get("winners") or []
        if isinstance(winner, dict)
    ]
    candidate_rows_by_spec = {
        (_text(row.get("classKey")), _text(row.get("specKey"))): row
        for row in candidate_rows
    }
    community_descriptor = pair.get("communityRelease") if isinstance(pair.get("communityRelease"), dict) else {}
    community_source = community_descriptor.get("source") if isinstance(community_descriptor.get("source"), dict) else {}
    # The first legacy import sealed evidence-sensitive slot hashes. Its immutable
    # content hash remains verified, while live old/new parity uses the corrected
    # user-visible semantic signature that excludes source/evidence identities.
    legacy_sealed_semantic = _text(community_source.get("sourceRevision")) == "legacy-import-r0"
    active_release_pair: dict[str, Any] = {}
    active_release_reader = getattr(store, "get_active_community_release", None)
    if callable(active_release_reader):
        try:
            loaded_active_pair = active_release_reader()
            if isinstance(loaded_active_pair, dict):
                active_release_pair = loaded_active_pair
        except Exception:
            active_release_pair = {}
    active_gear_descriptor = (
        active_release_pair.get("gearRelease")
        if isinstance(active_release_pair.get("gearRelease"), dict)
        else {}
    )
    active_dependency_revisions = (
        active_gear_descriptor.get("dependencyRevisions")
        if isinstance(active_gear_descriptor.get("dependencyRevisions"), dict)
        else {}
    )
    active_release_capability_revision = _text(
        active_dependency_revisions.get("capabilityRevision")
    )
    active_winners_by_spec = {
        (_text(winner.get("classKey")), _text(winner.get("specKey"))): winner
        for winner in active_release_pair.get("winners") or []
        if isinstance(winner, dict)
    }
    def active_pair_identity(value: Any) -> tuple[Any, ...] | None:
        if not isinstance(value, dict):
            return None
        active_value = value
        pointer_generation = active_value.get("pointerGeneration")
        if (
            active_value.get("formalActiveManifest") is not True
            or type(pointer_generation) is not int
            or pointer_generation <= 0
        ):
            return None
        active_gear = active_value.get("gearRelease")
        active_gear = active_gear if isinstance(active_gear, dict) else {}
        active_community = active_value.get("communityRelease")
        active_community = active_community if isinstance(active_community, dict) else {}
        gear_release_id = _text(active_gear.get("releaseId"))
        community_release_id = _text(active_community.get("releaseId"))
        manifest_revision = _text(active_value.get("manifestRevision"))
        winners = active_value.get("winners")
        if (
            not gear_release_id
            or not community_release_id
            or not manifest_revision
            or not isinstance(winners, list)
        ):
            return None
        winner_identity = []
        for winner in winners:
            if not isinstance(winner, dict):
                return None
            identity = (
                _text(winner.get("classKey")),
                _text(winner.get("specKey")),
                _text(winner.get("templateId")),
            )
            if not all(identity):
                return None
            winner_identity.append(identity)
        return (
            True,
            gear_release_id,
            community_release_id,
            manifest_revision,
            pointer_generation,
            tuple(sorted(winner_identity)),
        )

    captured_active_identity = active_pair_identity(active_release_pair)
    if (
        expect_formal_active
        or active_release_pair.get("formalActiveManifest") is True
    ) and captured_active_identity is None:
        return {
            "schemaRevision": "gear-release-shadow-execution-v1",
            "status": "blocked",
            "gearReleaseId": gear_id,
            "communityReleaseId": community_id,
            "report": {},
            "blockers": [_blocker(
                "ACTIVE_RELEASE_BASELINE_INVALID",
                detail=(
                    "Formal shadow requires an exact active release binding "
                    "with release IDs, Manifest revision, and a positive "
                    "integer pointer generation."
                ),
            )],
            "specResults": [],
            "publicReadCount": 0,
            "formalActiveManifest": (
                active_release_pair.get("formalActiveManifest") is True
            ),
        }
    captured_active_gear_id = (
        captured_active_identity[1] if captured_active_identity else ""
    )
    spec_results = []
    formal_active = False
    public_read_count = 0
    allowed_enhancement_migrations: set[tuple[str, str]] = set()
    allowed_import_fidelity_cutovers: set[tuple[str, str]] = set()
    reference_seen = False
    reference_proof: dict[str, Any] = {
        "status": (
            "not_run"
            if reference_proof_required
            else (
                "not_applicable"
                if candidate_capability_revision
                == gear_socket_authority.LEGACY_CAPABILITY_REVISION
                else "blocked"
            )
        ),
        "capabilityRevision": candidate_capability_revision,
    }
    profile_contexts = profile_context_by_spec if isinstance(profile_context_by_spec, dict) else {}
    for class_key, spec_key in expected:
        spec_started = time.perf_counter()
        key = (class_key, spec_key)
        spec_reference_proof = None
        candidate = winners_by_spec.get(key)
        try:
            public = store.get_websim_gear(
                class_key,
                spec_key,
                compact=True,
                mode="initial",
            )
        except Exception:
            blockers.append(_blocker(
                "TRANSITIONAL_PUBLIC_READ_FAILED",
                class_key,
                spec_key,
                "Transitional public reader is unavailable.",
            ))
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue
        public_read_count += 1
        public_templates = public.get("communityTemplates") if isinstance(public, dict) else []
        public_templates = public_templates if isinstance(public_templates, list) else []
        baselines = public.get("baselineTemplates") if isinstance(public, dict) else []
        baselines = baselines if isinstance(baselines, list) else []
        try:
            resolver_context = store.get_gear_resolver_context(
                gear_resolver_runtime_authority(
                    class_key,
                    spec_key,
                    simc_runtime_revision=simc_runtime_revision,
                )
            )
        except Exception:
            resolver_context = {}
        resolver_context = resolver_context if isinstance(resolver_context, dict) else {}
        formal_active = formal_active or resolver_context.get("formalActiveManifest") is True

        if baselines:
            blockers.append(_blocker("PUBLIC_BASELINE_LEAK", class_key, spec_key, "Transitional public baseline is not empty."))
        if len(public_templates) != 1:
            blockers.append(_blocker("TRANSITIONAL_WINNER_COUNT_INVALID", class_key, spec_key, "Transitional public winner count must equal one."))
        if candidate is None and not allow_degraded_empty:
            blockers.append(_blocker("CANDIDATE_WINNER_MISSING", class_key, spec_key, "Candidate Community Release has no winner."))
        if len(public_templates) != 1:
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue

        public_template = public_templates[0]
        authored = resolver_context.get("authoredAgainst") if isinstance(resolver_context.get("authoredAgainst"), dict) else {}
        active_capability_revision = _text(
            (resolver_context.get("dependencyRevisions") or {}).get(
                "capabilityRevision"
            )
        )
        active_winner = None
        active_binding_valid = False
        if active_capability_revision == gear_socket_authority.CAPABILITY_REVISION:
            active_winner = active_winners_by_spec.get(key)
            active_gear = (
                active_release_pair.get("gearRelease")
                if isinstance(active_release_pair.get("gearRelease"), dict)
                else {}
            )
            active_community = (
                active_release_pair.get("communityRelease")
                if isinstance(active_release_pair.get("communityRelease"), dict)
                else {}
            )
            active_intent = (
                active_winner.get("selectionIntent")
                if isinstance(active_winner, dict)
                and isinstance(active_winner.get("selectionIntent"), dict)
                else {}
            )
            active_eligibility = (
                active_intent.get("eligibilityContext")
                if isinstance(active_intent.get("eligibilityContext"), dict)
                else {}
            )
            active_binding_valid = (
                active_release_pair.get("formalActiveManifest") is True
                and _text(active_gear.get("releaseId"))
                == _text(authored.get("gearCatalogRevision"))
                and bool(_text(active_community.get("releaseId")))
                and isinstance(active_winner, dict)
                and _text(active_winner.get("templateId"))
                == _text(public_template.get("id"))
                and _text(active_eligibility.get("classKey")) == class_key
                and _text(active_eligibility.get("specKey")) == spec_key
            )
            if not active_binding_valid:
                blockers.append(_blocker(
                    "TRANSITIONAL_INTERNAL_WINNER_UNAVAILABLE",
                    class_key,
                    spec_key,
                    "Active v2 shadow requires the exact sealed active Community winner Intent.",
                ))
                spec_results.append({
                    "classKey": class_key,
                    "specKey": spec_key,
                    "status": "blocked",
                    "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
                })
                continue
            legacy_intent = copy.deepcopy(active_intent)
        else:
            legacy_intent = _selection_intent_from_template(
                public_template,
                gear_release_id=_text(authored.get("gearCatalogRevision")),
                season_revision=_text(authored.get("seasonRevision")),
                level=level,
            )
        if candidate is None:
            legacy_rows.append(
                pg_gear_read_model_selectors.build_transitional_release_shadow_row(
                    public_template,
                    legacy_intent,
                    {},
                    gear_release_id=gear_id,
                    baseline_count=len(baselines),
                )
            )
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "degraded_empty",
                "transitionalHttpStatus": 200,
                "candidateHttpStatus": 200,
                "profileParity": {"status": "not_run"},
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue
        if _text(public_template.get("id")) != _text(candidate.get("templateId")):
            blockers.append(_blocker("PUBLIC_WINNER_ID_MISMATCH", class_key, spec_key, "Candidate winner identity differs from public."))
        candidate_intent = candidate.get("selectionIntent") if isinstance(candidate.get("selectionIntent"), dict) else {}
        old_status, old_envelope = gear_runtime.resolve_selection_intent(
            legacy_intent,
            store=store,
            simc_runtime_revision=simc_runtime_revision,
            request_id=f"shadow-old-{class_key}-{spec_key}",
        )
        new_status, new_envelope = gear_runtime.resolve_candidate_selection_intent(
            candidate_intent,
            store=store,
            gear_release_id=gear_id,
            simc_runtime_revision=simc_runtime_revision,
            request_id=f"shadow-new-{class_key}-{spec_key}",
        )
        old_snapshot = _resolved_snapshot(old_status, old_envelope)
        new_snapshot = _resolved_snapshot(new_status, new_envelope)
        if old_snapshot is None:
            blockers.append(_blocker("TRANSITIONAL_RESOLVE_FAILED", class_key, spec_key, "Transitional winner did not resolve."))
        if new_snapshot is None:
            blockers.append(_blocker("CANDIDATE_RESOLVE_FAILED", class_key, spec_key, "Candidate winner did not resolve."))
        if old_snapshot is None or new_snapshot is None:
            spec_results.append({
                "classKey": class_key,
                "specKey": spec_key,
                "status": "blocked",
                "transitionalHttpStatus": old_status,
                "candidateHttpStatus": new_status,
                "transitionalProblemCodes": _problem_codes(old_envelope),
                "candidateProblemCodes": _problem_codes(new_envelope),
                "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
            })
            continue

        live_candidate_semantic = gear_release.semantic_gear_signature(candidate_intent, new_snapshot)
        candidate_shadow_row = candidate_rows_by_spec.get(key)
        if isinstance(candidate_shadow_row, dict):
            candidate_shadow_row["semanticGearSignature"] = live_candidate_semantic
        if (
            not legacy_sealed_semantic
            and live_candidate_semantic != _text(candidate.get("semanticGearSignature"))
        ):
            blockers.append(_blocker("CANDIDATE_SEALED_RESULT_MISMATCH", class_key, spec_key, "Current release reader result differs from the sealed winner."))
        if (
            reference_proof_required
            and _text(candidate.get("templateId")) == _REFERENCE_TEMPLATE_ID
        ):
            reference_seen = True
            spec_reference_proof = _reference_contract_proof(
                candidate,
                candidate_intent,
                new_snapshot,
            )
            spec_reference_proof["capabilityRevision"] = (
                candidate_capability_revision
            )
            spec_reference_proof["gearReleaseId"] = gear_id
            spec_reference_proof["communityReleaseId"] = community_id
            overflow_intent = copy.deepcopy(candidate_intent)
            overflow_slot = ""
            for reference_slot in _REFERENCE_SOCKET_SLOTS:
                selection = (overflow_intent.get("slots") or {}).get(reference_slot)
                constraint = (new_snapshot.get("constraints") or {}).get("slots", {}).get(reference_slot)
                if not isinstance(selection, dict) or not isinstance(constraint, dict):
                    continue
                selected_gems = selection.get("gemOptionIds")
                if (
                    isinstance(selected_gems, list)
                    and selected_gems
                    and len(selected_gems) == _int(constraint.get("socketCount"))
                ):
                    selection["gemOptionIds"] = [*selected_gems, selected_gems[0]]
                    overflow_slot = reference_slot
                    break
            overflow_codes = []
            if overflow_slot:
                overflow_status, overflow_envelope = gear_runtime.resolve_candidate_selection_intent(
                    overflow_intent,
                    store=store,
                    gear_release_id=gear_id,
                    simc_runtime_revision=simc_runtime_revision,
                    request_id=f"shadow-reference-ninth-gem-{class_key}-{spec_key}",
                )
                overflow_codes = _problem_codes(overflow_envelope)
                overflow_blocked = (
                    _resolved_snapshot(overflow_status, overflow_envelope) is None
                    and "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED" in overflow_codes
                )
                spec_reference_proof["ninthGem"] = {
                    "status": "pass" if overflow_blocked else "blocked",
                    "slot": overflow_slot,
                    "problemCodes": overflow_codes,
                }
                if not overflow_blocked:
                    spec_reference_proof["status"] = "blocked"
                    spec_reference_proof["failures"].append("ninth_gem")
            else:
                spec_reference_proof["status"] = "blocked"
                spec_reference_proof["failures"].append("ninth_gem_fixture")
            reference_proof = spec_reference_proof
            if spec_reference_proof["status"] != "pass":
                blockers.append(_blocker(
                    "REFERENCE_ENHANCEMENT_CONTRACT_MISMATCH",
                    class_key,
                    spec_key,
                    "Frozen Mage enhancement counts, capacity vector, or ninth-gem rejection did not match.",
                ))
        profile_result = {"status": "not_run"}
        migration_result = {"status": "not_run"}
        import_fidelity_result = {"status": "not_run"}
        if compare_profiles:
            profile_context = profile_contexts.get(f"{class_key}:{spec_key}")
            profile_context = profile_context if isinstance(profile_context, dict) else {}
            old_profile_status, old_profile = gear_runtime.build_profile_from_selection_intent(
                {"selectionIntent": legacy_intent, "profileContext": profile_context},
                store=store,
                simc_runtime_revision=simc_runtime_revision,
                request_id=f"shadow-old-profile-{class_key}-{spec_key}",
            )
            new_profile_status, new_profile = gear_runtime.build_candidate_profile_from_selection_intent(
                {"selectionIntent": candidate_intent, "profileContext": profile_context},
                store=store,
                gear_release_id=gear_id,
                simc_runtime_revision=simc_runtime_revision,
                request_id=f"shadow-new-profile-{class_key}-{spec_key}",
            )
            old_profile_state = _text(old_profile.get("status")) if isinstance(old_profile, dict) else ""
            new_profile_state = _text(new_profile.get("status")) if isinstance(new_profile, dict) else ""
            old_profile_outcome = _profile_outcome(old_profile_status, old_profile)
            new_profile_outcome = _profile_outcome(new_profile_status, new_profile)
            profile_result = {
                "status": "pass" if old_profile_outcome == new_profile_outcome else "blocked",
                "transitionalHttpStatus": old_profile_status,
                "transitionalStatus": old_profile_state,
                "transitionalProblemCodes": old_profile_outcome[
                    "problemCodes"
                ],
                "candidateHttpStatus": new_profile_status,
                "candidateStatus": new_profile_state,
                "candidateProblemCodes": new_profile_outcome["problemCodes"],
            }
            enhancement_selection_changed = (
                _enhancement_selection_projection(legacy_intent)
                != _enhancement_selection_projection(candidate_intent)
            )
            migration_scope_equal = (
                _non_enhancement_selection_projection(legacy_intent)
                == _non_enhancement_selection_projection(candidate_intent)
            )
            profile_migration_evidence = _profile_outcomes_allow_migration(
                old_profile_outcome,
                new_profile_outcome,
            )
            profile_import_gate_preserved = _profile_outcomes_preserve_import_gate(
                old_profile_outcome,
                new_profile_outcome,
            )
            transitional_authority_context = {}
            candidate_authority_context = {}
            active_winner = active_winners_by_spec.get(key)
            exact_active_binding = (
                captured_active_identity is not None
                and captured_active_identity[0] is True
                and bool(captured_active_gear_id)
                and bool(captured_active_identity[2])
                and isinstance(active_winner, dict)
                and _text(active_winner.get("templateId"))
                == _text(public_template.get("id"))
                and _text((legacy_intent.get("authoredAgainst") or {}).get(
                    "gearCatalogRevision"
                ))
                == captured_active_gear_id
            )
            observed_import_fidelity_cutover = (
                active_release_capability_revision
                == gear_socket_authority.CAPABILITY_REVISION
                and candidate_capability_revision
                == gear_socket_authority.CAPABILITY_REVISION
                and active_dependency_revisions == gear_dependencies
                and profile_import_gate_preserved
                and exact_active_binding
                and gear_release.is_observed_import_fidelity_cutover(
                    active_winner,
                    candidate,
                )
            )
            if observed_import_fidelity_cutover:
                if profile_result["status"] != "pass":
                    profile_result["status"] = "expected_import_fidelity_change"
                    profile_result["mode"] = "sealed_observed_source"
                import_fidelity_result = {
                    "status": "pass",
                    "mode": "sealed_observed_import",
                }
                allowed_import_fidelity_cutovers.add(key)
            else:
                import_fidelity_result = {"status": "not_required"}
                if profile_result["status"] != "pass":
                    blockers.append(_blocker(
                        "PROFILE_PARITY_MISMATCH",
                        class_key,
                        spec_key,
                        "Candidate Profile outcome differs from transitional Profile.",
                    ))
            legacy_to_v2_migration_candidate = (
                active_capability_revision
                == gear_socket_authority.LEGACY_CAPABILITY_REVISION
                and candidate_capability_revision
                == gear_socket_authority.CAPABILITY_REVISION
                and profile_result["status"] == "pass"
                and profile_migration_evidence
                and migration_scope_equal
                and exact_active_binding
            )
            current_v2_radiant_migration_candidate = (
                active_capability_revision
                == gear_socket_authority.CAPABILITY_REVISION
                and candidate_capability_revision
                == gear_socket_authority.CAPABILITY_REVISION
                and profile_result["status"] == "pass"
                and profile_migration_evidence
                and migration_scope_equal
                and not enhancement_selection_changed
                and exact_active_binding
            )
            if (
                legacy_to_v2_migration_candidate
                or current_v2_radiant_migration_candidate
            ):
                try:
                    runtime_authority = gear_resolver_runtime_authority(
                        class_key,
                        spec_key,
                        simc_runtime_revision=simc_runtime_revision,
                    )
                    transitional_authority_context = (
                        store.get_candidate_gear_authority_context(
                            legacy_intent,
                            runtime_authority,
                            captured_active_gear_id,
                        )
                    )
                    candidate_authority_context = (
                        store.get_candidate_gear_authority_context(
                            candidate_intent,
                            runtime_authority,
                            gear_id,
                        )
                    )
                except Exception:
                    transitional_authority_context = {}
                    candidate_authority_context = {}
            editor_only_migration = (
                active_capability_revision
                == gear_socket_authority.LEGACY_CAPABILITY_REVISION
                and candidate_capability_revision
                == gear_socket_authority.CAPABILITY_REVISION
                and profile_result["status"] == "pass"
                and profile_migration_evidence
                and migration_scope_equal
                and _legacy_to_v2_enhancement_migration_equivalent(
                    old_snapshot,
                    new_snapshot,
                    transitional_gear_release_id=captured_active_gear_id,
                    transitional_gear_catalog_revision=(
                        legacy_intent.get("authoredAgainst") or {}
                    ).get("gearCatalogRevision"),
                    candidate_gear_release_id=gear_id,
                    transitional_authority_context=transitional_authority_context,
                    candidate_authority_context=candidate_authority_context,
                    transitional_intent=legacy_intent,
                    candidate_intent=candidate_intent,
                    migration_mode="editor_only",
                )
            )
            legacy_to_v2_capacity_migration = (
                legacy_to_v2_migration_candidate
                and _legacy_to_v2_socket_capacity_migration_equivalent(
                    old_snapshot,
                    new_snapshot,
                    transitional_gear_release_id=captured_active_gear_id,
                    transitional_gear_catalog_revision=(
                        legacy_intent.get("authoredAgainst") or {}
                    ).get("gearCatalogRevision"),
                    candidate_gear_release_id=gear_id,
                    transitional_authority_context=transitional_authority_context,
                    candidate_authority_context=candidate_authority_context,
                    transitional_intent=legacy_intent,
                    candidate_intent=candidate_intent,
                )
            )
            current_v2_radiant_capacity_migration = (
                current_v2_radiant_migration_candidate
                and _current_v2_radiant_jewelbinder_capacity_migration_equivalent(
                    old_snapshot,
                    new_snapshot,
                    transitional_authority_context=transitional_authority_context,
                    candidate_authority_context=candidate_authority_context,
                    transitional_intent=legacy_intent,
                    candidate_intent=candidate_intent,
                )
            )
            if (
                not enhancement_selection_changed
                and not legacy_to_v2_capacity_migration
                and not current_v2_radiant_capacity_migration
            ):
                migration_result = {"status": "not_required"}
            elif (
                profile_result["status"] == "pass"
                and (
                    editor_only_migration
                    or legacy_to_v2_capacity_migration
                    or current_v2_radiant_capacity_migration
                )
                and migration_scope_equal
            ):
                migration_result = {
                    "status": "pass",
                    "mode": (
                        "current_v2_radiant_jewelbinder_capacity"
                        if current_v2_radiant_capacity_migration
                        else (
                            "legacy_to_v2_socket_capacity"
                            if legacy_to_v2_capacity_migration
                            else "enhancement_only"
                        )
                    ),
                }
                allowed_enhancement_migrations.add(key)
            else:
                migration_result = {"status": "blocked"}
        transitional_shadow_row = (
            pg_gear_read_model_selectors.build_transitional_release_shadow_row(
                public_template,
                legacy_intent,
                old_snapshot,
                gear_release_id=gear_id,
                baseline_count=len(baselines),
            )
        )
        if active_binding_valid and captured_active_identity is not None:
            transitional_shadow_row = _bind_transitional_provenance_to_active_winner(
                transitional_shadow_row,
                active_winner,
            )
        legacy_rows.append(transitional_shadow_row)
        spec_results.append({
            "classKey": class_key,
            "specKey": spec_key,
            "status": "pass",
            "transitionalHttpStatus": old_status,
            "candidateHttpStatus": new_status,
            "profileParity": profile_result,
            "enhancementMigrationParity": migration_result,
            "importFidelityCutoverParity": import_fidelity_result,
            **({"referenceProof": spec_reference_proof} if spec_reference_proof else {}),
            "durationMs": round((time.perf_counter() - spec_started) * 1000, 3),
        })

    if (
        reference_proof_required
        and _REFERENCE_SPEC in set(expected)
        and not reference_seen
    ):
        blockers.append(_blocker(
            "REFERENCE_TEMPLATE_MISSING",
            *_REFERENCE_SPEC,
            "Frozen observed_profile_mage_frost winner is required for the candidate shadow.",
        ))
    if formal_active is not bool(expect_formal_active):
        blockers.append(_blocker(
            "PUBLIC_FORMAL_MANIFEST_STATE_MISMATCH",
            detail="Public reader formal Manifest state does not match the shadow contract.",
        ))
    if captured_active_identity is not None:
        try:
            ending_active_pair = active_release_reader()
        except Exception:
            ending_active_pair = {}
        if active_pair_identity(ending_active_pair) != captured_active_identity:
            blockers.append(_blocker(
                "ACTIVE_RELEASE_CHANGED_DURING_SHADOW",
                detail="Exact active release binding changed during migration shadow.",
            ))
    report = gear_release.compare_shadow(
        legacy_rows,
        candidate_rows,
        expected_specs=expected,
        gear_release_id=gear_id,
        allowed_semantic_change_specs=allowed_enhancement_migrations,
        allowed_import_fidelity_cutover_specs=allowed_import_fidelity_cutovers,
    )
    blockers.extend(report.get("blockers") or [])
    status = "blocked" if blockers else report.get("status", "blocked")
    spec_durations = sorted(
        float(row.get("durationMs") or 0)
        for row in spec_results
        if isinstance(row, dict)
    )
    p95_index = max(0, ((len(spec_durations) * 95 + 99) // 100) - 1)
    return {
        "schemaRevision": "gear-release-shadow-execution-v1",
        "status": status,
        "gearReleaseId": gear_id,
        "communityReleaseId": community_id,
        "report": report,
        "blockers": blockers,
        "specResults": spec_results,
        "publicReadCount": public_read_count,
        "formalActiveManifest": formal_active,
        "referenceProof": reference_proof,
        "sealedSemanticMode": (
            "legacy_evidence_identity_v1"
            if legacy_sealed_semantic
            else "current"
        ),
        "performance": {
            "totalDurationMs": round((time.perf_counter() - shadow_started) * 1000, 3),
            "specP95Ms": spec_durations[p95_index] if spec_durations else 0,
            "specMaxMs": spec_durations[-1] if spec_durations else 0,
        },
    }


__all__ = ("run_release_shadow",)

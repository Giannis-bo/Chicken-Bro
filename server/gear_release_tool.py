#!/usr/bin/env python3
"""Explicit inactive release builder for equipment simulator Phase 4B."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

try:
    from . import (
        gear_enhancement_management,
        gear_release,
        gear_release_shadow,
        gear_resolver,
        gear_socket_authority,
    )
    from .db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    from .gear_release_store import (
        CandidateGearAuthorityIndex,
        GearReleaseIntegrityError,
        GearReleaseStore,
        build_candidate_authority_context,
        community_rows_summary,
        gear_snapshot_summary,
    )
    from .websim_payload import (
        PRIMARY_STAT_GEM_IDS,
        SIMC_GEAR_OPTION_KEYS,
        WOW_CLASSES,
        gear_resolver_runtime_authority,
        item_can_enchant_slot,
        normalize_option_value,
        normalize_slot,
        observed_gear_simc_options,
        simc_encoded_item_options,
    )
    from .postgres_cache_store import PostgresCacheStore
except ImportError:
    import gear_enhancement_management
    import gear_release
    import gear_release_shadow
    import gear_resolver
    import gear_socket_authority
    from db import connect_postgres, database_config_from_env, postgres_only_runtime_enabled
    from gear_release_store import (
        CandidateGearAuthorityIndex,
        GearReleaseIntegrityError,
        GearReleaseStore,
        build_candidate_authority_context,
        community_rows_summary,
        gear_snapshot_summary,
    )
    from websim_payload import (
        PRIMARY_STAT_GEM_IDS,
        SIMC_GEAR_OPTION_KEYS,
        WOW_CLASSES,
        gear_resolver_runtime_authority,
        item_can_enchant_slot,
        normalize_option_value,
        normalize_slot,
        observed_gear_simc_options,
        simc_encoded_item_options,
    )
    from postgres_cache_store import PostgresCacheStore


_SIMC_SOCKET_PROBE_TIMEOUT_SECONDS = 30
_SIMC_SOCKET_PROBE_MAX_CHARS = 4 * 1024 * 1024
_SIMC_SOCKET_PROBE_FAILURE = "SimC socket probe failed"
_GEM_SIMC_SEQUENCE_FIELDS = gear_enhancement_management.GEM_SIMC_SEQUENCE_FIELDS
_ENHANCEMENT_SIMC_FIELDS = gear_enhancement_management.ENHANCEMENT_SIMC_FIELDS
_BATTLE_NET_GAME_DATA_API = "Battle.net Game Data API"
_OFFICIAL_GEM_UNIQUE_CATEGORY_ALIASES = {
    "thalassian diamond": "thalassian-diamond",
    "萨拉斯钻石": "thalassian-diamond",
    "薩拉斯鑽石": "thalassian-diamond",
}
_OFFICIAL_GEM_UNIQUE_CATEGORY_LIMITS = {
    "thalassian-diamond": 1,
}
_OFFICIAL_UNIQUE_GEM_POLICIES = {
    gem_id: {"categoryKey": "thalassian-diamond", "uniqueLimit": 1}
    for gem_id in {*PRIMARY_STAT_GEM_IDS, "241144"}
}
COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION = (
    gear_release.COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def _canonical(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str))


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _socket_probe_digest(socket_bonus_minimums: Mapping[str, Any]) -> str:
    return _canonical_digest({
        "socketBonusMinimums": {
            _text(bonus_id): _canonical(minimum)
            for bonus_id, minimum in socket_bonus_minimums.items()
            if _text(bonus_id)
        },
    })


def _socket_fact_value(row: dict[str, Any], field: str) -> dict[str, Any]:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    value = payload.get(field) if isinstance(payload.get(field), dict) else row.get(field)
    return value if isinstance(value, dict) else {}


def _materialized_socket_fact_digest(snapshot: dict[str, Any]) -> str:
    items = [
        {
            "itemId": _text(row.get("itemId")),
            "socketCount": _int(_socket_fact_value(row, "baseCapabilities").get("socketCount")),
            "socketEvidence": _canonical(_socket_fact_value(row, "socketEvidence")),
        }
        for row in snapshot.get("items") or []
        if isinstance(row, dict)
    ]
    variants = [
        {
            "variantId": _text(row.get("variantId")),
            "itemId": _text(row.get("itemId")),
            "variantKey": _text(row.get("variantKey")),
            "socketCount": _int(
                _socket_fact_value(row, "capabilityOverrides").get("socketCount")
            ),
            "socketEvidence": _canonical(_socket_fact_value(row, "socketEvidence")),
        }
        for row in snapshot.get("variants") or []
        if isinstance(row, dict)
    ]
    items.sort(key=lambda row: row["itemId"])
    variants.sort(key=lambda row: (row["variantId"], row["itemId"], row["variantKey"]))
    return _canonical_digest({"items": items, "variants": variants})


def _project_socket_facts_into_release_payloads(snapshot: dict[str, Any]) -> dict[str, Any]:
    projected = _canonical(snapshot)
    for category, fields in (
        ("items", ("baseCapabilities", "socketEvidence")),
        ("variants", ("capabilityOverrides", "socketEvidence")),
    ):
        rows = [row for row in projected.get(category) or [] if isinstance(row, dict)]
        if any(not isinstance(row.get(field), dict) for row in rows for field in fields):
            raise GearReleaseIntegrityError("materialized socket facts are incomplete")
        for row in rows:
            payload = _canonical(row.get("payload") if isinstance(row.get("payload"), dict) else {})
            for field in fields:
                materialized = row.pop(field)
                if field in {"baseCapabilities", "capabilityOverrides"}:
                    existing = payload.get(field) if isinstance(payload.get(field), dict) else {}
                    payload[field] = {**existing, **materialized}
                else:
                    payload[field] = materialized
            row["payload"] = payload
    return projected


def _materialize_enhancement_management(
    snapshot: dict[str, Any],
    capability_revision: str,
) -> dict[str, Any]:
    """Seal v2 field governance without treating absence as trusted source data."""

    materialized = _canonical(snapshot)
    items_by_id = {
        _text(row.get("itemId")): row
        for row in materialized.get("items") or []
        if isinstance(row, dict) and _text(row.get("itemId"))
    }

    def canonical_simc_options(options: Any) -> dict[str, Any] | None:
        values = options if isinstance(options, dict) else {}
        normalized = {}
        for field, value in values.items():
            if not isinstance(field, str) or not field or field != field.strip():
                return None
            normalized_field = field
            if not re.fullmatch(r"[A-Za-z0-9_]+", normalized_field):
                return None
            canonical_field = (
                "id"
                if normalized_field in {"id", "item_id", "itemId"}
                else normalized_field
            )
            if canonical_field in normalized:
                return None
            raw_value = str(value if value is not None else "")
            if raw_value != raw_value.strip():
                return None
            normalized_value = normalize_option_value(value)
            if not normalized_value or raw_value != normalized_value:
                return None
            if canonical_field == "bonus_id":
                tokens = normalized_value.split("/") if normalized_value else []
                normalized[canonical_field] = (
                    sorted(tokens) if tokens and all(tokens) else []
                )
            elif canonical_field == "ilevel":
                normalized[canonical_field] = normalized_value
            else:
                normalized[canonical_field] = normalized_value
        return normalized

    def exact_encoded_simc_options(encoded: str) -> dict[str, str] | None:
        seen: dict[str, str] = {}
        for index, part in enumerate(encoded.split(",")):
            if "=" not in part:
                if index == 0 and part.strip():
                    continue
                return None
            raw_key, raw_value = part.split("=", 1)
            if (
                part != part.strip()
                or raw_key != raw_key.strip()
                or raw_value != raw_value.strip()
            ):
                return None
            key = raw_key
            normalized_key = re.sub(r"[^A-Za-z0-9_]+", "", key)
            normalized_value = normalize_option_value(raw_value)
            canonical_key = (
                "id" if normalized_key in {"id", "item_id", "itemId"} else normalized_key
            )
            if (
                not normalized_key
                or key != normalized_key
                or not normalized_value
                or raw_value != normalized_value
                or canonical_key in seen
            ):
                return None
            seen[canonical_key] = normalized_value
        parsed = simc_encoded_item_options(encoded)
        return parsed if parsed == seen else None

    def verified_official_gem_option(
        gem_id: str,
    ) -> tuple[str, dict[str, Any] | None]:
        """Project an observed gem only from already-cached official item facts."""

        item = items_by_id.get(gem_id)
        item = item if isinstance(item, dict) else {}
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
        game_asset = metadata.get("gameAsset") if isinstance(metadata.get("gameAsset"), dict) else {}
        item_class = payload.get("item_class") if isinstance(payload.get("item_class"), dict) else {}
        preview = payload.get("preview_item") if isinstance(payload.get("preview_item"), dict) else {}
        gem_properties = preview.get("gem_properties") if isinstance(preview.get("gem_properties"), dict) else {}
        links = payload.get("_links") if isinstance(payload.get("_links"), dict) else {}
        self_link = links.get("self") if isinstance(links.get("self"), dict) else {}
        evidence_ref = _text(self_link.get("href"))
        metadata_source = _text(metadata.get("source"))
        icon_url = _text(metadata.get("iconUrl") or payload.get("iconUrl"))
        stat_summary = _text(gem_properties.get("effect"))
        display_name = _text(item.get("name") or payload.get("name") or preview.get("name"))
        parsed_evidence_ref = urlparse(evidence_ref)
        evidence_host = _text(parsed_evidence_ref.hostname).lower()
        evidence_path = parsed_evidence_ref.path.rstrip("/")
        metadata_verified = (
            _text(game_asset.get("status")).lower() == "verified"
            and _text(game_asset.get("source")).lower() == "blizzard"
        )
        if (
            not metadata_verified
            or metadata_source != _BATTLE_NET_GAME_DATA_API
            or _int(item_class.get("id")) != 3
            or not display_name
            or not stat_summary
            or not icon_url
            or parsed_evidence_ref.scheme.lower() != "https"
            or not (
                evidence_host == "api.blizzard.com"
                or evidence_host.endswith(".api.blizzard.com")
            )
            or evidence_path != f"/data/wow/item/{gem_id}"
        ):
            return "unavailable", None

        option_payload: dict[str, Any] = {
            "source": "official_observed_gem_release_projection",
            "status": "verified",
            "gemItemId": gem_id,
            "gemItemIds": [gem_id],
            "displayName": display_name,
            "displayLabel": stat_summary,
            "displayKind": "stat",
            "displayStatus": "verified",
            "statSummary": stat_summary,
            "iconUrl": icon_url,
            "metadataStatus": "verified",
            "metadataSource": metadata_source,
            "evidenceSource": "blizzard_game_data_api",
            "evidenceRef": evidence_ref,
        }
        raw_limit_category = preview.get("limit_category")
        limit_categories: list[str] = []
        limit_category_invalid = False
        if raw_limit_category is None:
            pass
        elif isinstance(raw_limit_category, str):
            if raw_limit_category.strip():
                limit_categories.append(raw_limit_category.strip())
        elif isinstance(raw_limit_category, dict):
            supported_fields = (
                "display_string",
                "displayString",
                "name",
                "label",
                "text",
                "description",
            )
            for field in supported_fields:
                if field not in raw_limit_category:
                    continue
                field_value = raw_limit_category.get(field)
                if field_value is None or field_value == "":
                    continue
                if not isinstance(field_value, str) or not field_value.strip():
                    limit_category_invalid = True
                    break
                limit_categories.append(field_value.strip())
            if raw_limit_category and not limit_categories:
                limit_category_invalid = True
        else:
            limit_category_invalid = "limit_category" in preview

        parsed_limit_categories: set[tuple[str, int]] = set()
        for limit_category in limit_categories:
            limit_match = re.fullmatch(
                r"\s*(?:unique[\s_-]*equipped|装备唯一|唯一装备|裝備唯一|唯一裝備)"
                r"\s*[:：]\s*"
                r"(?P<category>.+?)\s*[\(（]\s*(?P<limit>[1-9]\d*)\s*[\)）]\s*",
                limit_category,
                flags=re.IGNORECASE,
            )
            if not limit_match:
                limit_category_invalid = True
                break
            unique_limit = _int(limit_match.group("limit"))
            category_alias = re.sub(
                r"\s+",
                " ",
                _text(limit_match.group("category")),
            ).casefold()
            category_key = _OFFICIAL_GEM_UNIQUE_CATEGORY_ALIASES.get(
                category_alias,
                "",
            )
            expected_limit = _OFFICIAL_GEM_UNIQUE_CATEGORY_LIMITS.get(category_key)
            if (
                unique_limit <= 0
                or not category_key
                or expected_limit is None
                or unique_limit != expected_limit
            ):
                limit_category_invalid = True
                break
            parsed_limit_categories.add((category_key, unique_limit))
        if len(parsed_limit_categories) > 1:
            limit_category_invalid = True

        unique_policy = _OFFICIAL_UNIQUE_GEM_POLICIES.get(gem_id)
        parsed_limit_category = next(iter(parsed_limit_categories), None)
        if limit_category_invalid:
            return "invalid", None
        if parsed_limit_category:
            category_key, unique_limit = parsed_limit_category
            if unique_policy and (
                category_key != unique_policy["categoryKey"]
                or unique_limit != unique_policy["uniqueLimit"]
            ):
                return "invalid", None
            option_payload.update({
                "uniqueEquipped": True,
                "uniqueGroup": f"official-gem-limit:{category_key}",
                "uniqueLimit": unique_limit,
                "uniqueScope": "gear_socket",
            })
        elif unique_policy:
            return "invalid", None
        return "verified", {
            "optionId": f"official-gem-{gem_id}",
            "variantId": "",
            "optionKey": f"gem-{gem_id}",
            "optionType": "socket",
            "name": display_name,
            "applicableSlots": ["*"],
            "simcOptions": {"gem_id": gem_id},
            "status": "verified",
            "isVisible": True,
            "payload": option_payload,
            "updatedAt": _text(item.get("updatedAt")),
        }

    if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
        observed_gem_ids = {
            token.strip()
            for variant in materialized.get("variants") or []
            if isinstance(variant, dict)
            and _text(variant.get("sourceType")).lower() == "observed_profile"
            and _text(variant.get("status")).lower() in {"verified", "partial"}
            for token in _text((variant.get("simcOptions") or {}).get("gem_id")).split("/")
            if token.strip().isdigit()
        }
        projected_options = [
            option
            for option in materialized.get("options") or []
            if isinstance(option, dict)
        ]
        for gem_id in sorted(observed_gem_ids):
            option_key = f"gem-{gem_id}"
            matching_options = []
            canonical_options = []
            for existing in projected_options:
                existing_key = _text(existing.get("optionKey"))
                existing_simc_options = (
                    existing.get("simcOptions")
                    if isinstance(existing.get("simcOptions"), dict)
                    else {}
                )
                existing_gem_id = normalize_option_value(
                    existing_simc_options.get("gem_id")
                )
                if (
                    existing_key == option_key
                    and existing_gem_id
                    and existing_gem_id != gem_id
                ):
                    raise GearReleaseIntegrityError(
                        f"gem option identity conflicts with cached option: {gem_id}"
                    )
                if existing_key == option_key or existing_gem_id == gem_id:
                    matching_options.append(existing)
                if (
                    existing_key == option_key
                    and existing_simc_options == {"gem_id": gem_id}
                    and _text(existing.get("optionId"))
                    and _text(existing.get("optionType")).lower()
                    in {"socket", "gem"}
                    and _text(existing.get("status")).lower() == "verified"
                    and existing.get("isVisible") is True
                ):
                    canonical_options.append(existing)
            retained_options = [
                existing
                for existing in projected_options
                if existing not in matching_options
            ]
            official_state, official_option = verified_official_gem_option(gem_id)
            if official_state != "verified":
                if gem_id in _OFFICIAL_UNIQUE_GEM_POLICIES:
                    raise GearReleaseIntegrityError(
                        f"official unique gem evidence is unavailable: {gem_id}"
                    )
                projected_options = retained_options
                continue
            official_option = copy.deepcopy(official_option)
            live_presentation_options = []
            for existing in canonical_options:
                payload = (
                    existing.get("payload")
                    if isinstance(existing.get("payload"), dict)
                    else {}
                )
                if (
                    _text(payload.get("evidenceSource"))
                    == "wowhead_live_tooltip"
                    and _text(payload.get("displayStatus")) == "verified"
                    and _text(payload.get("displayLabel"))
                    and _text(payload.get("statSummary"))
                ):
                    live_presentation_options.append(existing)
            if len(live_presentation_options) == 1:
                presentation = live_presentation_options[0]
                presentation_payload = presentation["payload"]
                official_payload = official_option["payload"]
                official_payload["governanceEvidenceSource"] = _text(
                    official_payload.get("evidenceSource")
                )
                official_payload["governanceEvidenceRef"] = _text(
                    official_payload.get("evidenceRef")
                )
                for field in (
                    "displayName",
                    "displayLabel",
                    "displayKind",
                    "displayStatus",
                    "statSummary",
                    "iconUrl",
                ):
                    if field in presentation_payload:
                        official_payload[field] = copy.deepcopy(
                            presentation_payload[field]
                        )
                official_payload["evidenceSource"] = "wowhead_live_tooltip"
                presentation_ref = _text(presentation_payload.get("evidenceRef"))
                if presentation_ref:
                    official_payload["evidenceRef"] = presentation_ref
                else:
                    official_payload.pop("evidenceRef", None)
                official_option["name"] = _text(
                    official_payload.get("displayName")
                    or presentation.get("name")
                    or official_option.get("name")
                )
            projected_options = [*retained_options, official_option]
        materialized["options"] = projected_options

    options = [
        row
        for row in materialized.get("options") or []
        if isinstance(row, dict)
        and _text(row.get("status")).lower() == "verified"
        and row.get("isVisible") is True
    ]

    def option_type(option: dict[str, Any]) -> str:
        value = _text(option.get("optionType")).lower()
        return "gem" if value in {"socket", "gem"} else value

    def option_applies(option: dict[str, Any], slot: str) -> bool:
        applicable = [_text(value) for value in option.get("applicableSlots") or []]
        normalized = [normalize_slot(value) for value in applicable]
        return not applicable or "*" in applicable or slot in normalized

    if capability_revision == gear_socket_authority.CAPABILITY_REVISION:
        for option in options:
            if option_type(option) == "gem":
                # Gem compatibility is capacity-governed by the exact item/variant,
                # not by the legacy jewelry-only option catalog scope.
                option["applicableSlots"] = ["*"]

    def built_in_embellishment_state(
        raw_value: str,
        item_payload: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> str:
        payloads = (item_payload, variant_payload)
        explicit_values = {
            value.strip()
            for source in payloads
            for key in (
                "builtInEmbellishment",
                "intrinsicEmbellishment",
                "inherentEmbellishment",
            )
            for value in (source.get(key),)
            if isinstance(value, str) and value.strip()
        }
        if len(explicit_values) > 1:
            return "conflict"
        if explicit_values:
            return "proven" if raw_value in explicit_values else "conflict"
        built_in_source = any(
            isinstance(source.get("embellishmentSource"), str)
            and source["embellishmentSource"].strip().lower()
            in {"built_in", "builtin", "intrinsic", "item"}
            for source in payloads
        )
        strict_marker = any(
            source.get("hasBuiltInEmbellishment") is True
            for source in payloads
        )
        return "proven" if strict_marker or built_in_source else "absent"

    def simc_echo_enchant_proven(
        raw_value: str,
        slot: str,
        variant: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> bool:
        """Require an exact candidate-time SimC echo for immutable raw enchants."""

        if (
            _text(variant_payload.get("statSource")).lower() != "simulationcraft"
            or _text(variant_payload.get("statDisplayStatus")).lower()
            != "verified_variant"
            or not isinstance(variant_payload.get("itemStats"), list)
            or not variant_payload.get("itemStats")
        ):
            return False
        encoded = variant_payload.get("simcEncodedItem")
        if (
            not isinstance(encoded, str)
            or not encoded
            or encoded != encoded.strip()
        ):
            return False
        encoded_options = exact_encoded_simc_options(encoded)
        if encoded_options is None:
            return False
        item_id = _text(variant.get("itemId"))
        item_level = _int(variant.get("itemLevel"))
        raw_options = (
            variant.get("simcOptions")
            if isinstance(variant.get("simcOptions"), dict)
            else {}
        )

        normalized_raw_options = canonical_simc_options(raw_options)
        encoded_semantic_options = canonical_simc_options(encoded_options)
        if normalized_raw_options is None or encoded_semantic_options is None:
            return False
        if any(
            not expected
            or encoded_semantic_options.get(field) != expected
            for field, expected in normalized_raw_options.items()
        ):
            return False
        if set(encoded_semantic_options) - set(normalized_raw_options) - {"id", "ilevel"}:
            return False
        return (
            bool(slot)
            and bool(item_id)
            and _text(encoded_options.get("id")) == item_id
            and item_level > 0
            and _int(encoded_options.get("ilevel")) == item_level
            and _text(variant_payload.get("simcItemId")) == item_id
            and _int(variant_payload.get("simcItemLevel")) == item_level
            and normalize_option_value(encoded_options.get("enchant_id"))
            == normalize_option_value(raw_value)
        )

    variants = [
        row
        for row in materialized.get("variants") or []
        if isinstance(row, dict)
    ]

    def equivalent_simc_echo_enchant_proven(
        raw_value: str,
        slot: str,
        variant: dict[str, Any],
        variant_payload: dict[str, Any],
    ) -> bool:
        if simc_echo_enchant_proven(raw_value, slot, variant, variant_payload):
            return True
        variant_simc_options = canonical_simc_options(variant.get("simcOptions"))
        if variant_simc_options is None:
            return False
        semantic_identity = _canonical({
            "itemId": _text(variant.get("itemId")),
            "slot": slot,
            "itemLevel": _int(variant.get("itemLevel")),
            "simcOptions": variant_simc_options,
        })
        for sibling in variants:
            if sibling is variant:
                continue
            sibling_slot = normalize_slot(sibling.get("slot"))
            sibling_simc_options = canonical_simc_options(sibling.get("simcOptions"))
            if sibling_simc_options is None:
                continue
            sibling_identity = _canonical({
                "itemId": _text(sibling.get("itemId")),
                "slot": sibling_slot,
                "itemLevel": _int(sibling.get("itemLevel")),
                "simcOptions": sibling_simc_options,
            })
            sibling_payload = sibling.get("payload") if isinstance(sibling.get("payload"), dict) else {}
            if (
                sibling_identity == semantic_identity
                and _text(sibling.get("status")).lower() == "verified"
                and _text(sibling.get("sourceType")).lower() == "observed_profile"
                and simc_echo_enchant_proven(
                    raw_value,
                    sibling_slot,
                    sibling,
                    sibling_payload,
                )
            ):
                return True
        return False

    for variant in variants:
        if not isinstance(variant, dict):
            continue
        payload = _canonical(variant.get("payload") if isinstance(variant.get("payload"), dict) else {})
        payload.pop("editorManagedSimcFields", None)
        payload.pop("enhancementManagement", None)
        if capability_revision != gear_socket_authority.CAPABILITY_REVISION:
            variant["payload"] = payload
            continue
        item = items_by_id.get(_text(variant.get("itemId")), {})
        item_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        slot = normalize_slot(variant.get("slot") or item.get("slot"))
        simc_options = variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
        applicable_options = [option for option in options if option_applies(option, slot)]
        base_capabilities = item_payload.get("baseCapabilities") if isinstance(item_payload.get("baseCapabilities"), dict) else {}
        variant_capabilities = payload.get("capabilityOverrides") if isinstance(payload.get("capabilityOverrides"), dict) else {}
        socket_count = _int(variant_capabilities.get("socketCount", base_capabilities.get("socketCount")))
        can_enchant = item_can_enchant_slot(item_payload, slot, item)
        trusted_observed = (
            _text(variant.get("status")).lower() == "verified"
            and _text(variant.get("sourceType")).lower() == "observed_profile"
        )
        classifications: dict[str, str] = {}
        raw_gem_sequences = {
            field: simc_options.get(field)
            for field in _GEM_SIMC_SEQUENCE_FIELDS
            if _text(simc_options.get(field))
        }
        if raw_gem_sequences:
            raw_gem_ids = raw_gem_sequences.get("gem_id")

            def valid_numeric_sequence(raw: Any) -> list[str] | None:
                if not isinstance(raw, str) or not raw.strip():
                    return None
                tokens = raw.split("/")
                if any(not token.strip() or not token.strip().isdigit() for token in tokens):
                    return None
                return [token.strip() for token in tokens]

            gem_ids = valid_numeric_sequence(raw_gem_ids)
            auxiliary_sequences = {
                field: valid_numeric_sequence(raw_value)
                for field, raw_value in raw_gem_sequences.items()
                if field != "gem_id"
            }
            if (
                gem_ids is None
                or socket_count <= 0
                or len(gem_ids) > socket_count
                or any(
                    tokens is None or len(tokens) != len(gem_ids)
                    for tokens in auxiliary_sequences.values()
                )
            ):
                raise GearReleaseIntegrityError(
                    "raw gem sequence conflicts with materialized socket capacity"
                )
        for field in _ENHANCEMENT_SIMC_FIELDS:
            raw_value = _text(simc_options.get(field))
            if not raw_value:
                continue
            editor_managed = False
            if field in _GEM_SIMC_SEQUENCE_FIELDS:
                editor_managed = socket_count > 0
            elif field == "embellishment":
                editor_managed = any(
                    option_type(option) == "embellishment"
                    and _text((option.get("simcOptions") or {}).get(field)) == raw_value
                    for option in applicable_options
                )
            elif field == "enchant_id" and "/" not in raw_value:
                editor_managed = can_enchant and any(
                    option_type(option) in {"enchant", "runeforge"}
                    and _text((option.get("simcOptions") or {}).get(field)) == raw_value
                    for option in applicable_options
                )
            built_in_embellishment = built_in_embellishment_state(
                raw_value,
                item_payload,
                payload,
            )
            if field == "embellishment" and built_in_embellishment == "conflict":
                raise GearReleaseIntegrityError(
                    "built-in embellishment evidence conflicts with raw SimC value"
                )
            source_only = trusted_observed and (
                (field == "embellishment" and built_in_embellishment == "proven")
                or (
                    field == "enchant_id"
                    and (
                        not can_enchant
                        or (
                            slot in {"main_hand", "off_hand"}
                            and not editor_managed
                        )
                    )
                    and equivalent_simc_echo_enchant_proven(
                        raw_value,
                        slot,
                        variant,
                        payload,
                    )
                )
            )
            classifications[field] = (
                "source_only"
                if field == "embellishment" and built_in_embellishment == "proven"
                else "unresolved_drop"
                if field == "embellishment" and built_in_embellishment == "conflict"
                else "editor_managed"
                if editor_managed
                else "source_only"
                if source_only
                else "unresolved_drop"
            )
        management = gear_enhancement_management.seal_enhancement_management(
            simc_options,
            classifications,
            capability_revision,
        )
        if management:
            payload["enhancementManagement"] = management
        variant["payload"] = payload
    return materialized


def load_simc_socket_bonus_minimums(
    simc_binary: str,
    *,
    runner=subprocess.run,
) -> dict[str, int]:
    """Run the bounded candidate-only SimC bonus probe and parse socket effects."""

    binary = _text(simc_binary)
    if not binary:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    try:
        result = runner(
            [binary, "show_bonus_ids=1"],
            capture_output=True,
            text=True,
            timeout=_SIMC_SOCKET_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE) from None
    returncode = getattr(result, "returncode", None)
    if type(returncode) is not int or returncode != 0:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    output = getattr(result, "stdout", "")
    if not isinstance(output, str) or len(output) > _SIMC_SOCKET_PROBE_MAX_CHARS:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    try:
        parsed = gear_socket_authority.parse_simc_socket_bonus_minimums(output)
    except Exception:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE) from None
    if not parsed:
        raise RuntimeError(_SIMC_SOCKET_PROBE_FAILURE)
    return parsed


def expected_spec_pairs() -> list[tuple[str, str]]:
    return sorted(
        (_text(klass.get("key")), _text(spec))
        for klass in WOW_CLASSES
        for spec in klass.get("specs") or []
    )


def runtime_dependency_revisions(simc_runtime_revision: str) -> dict[str, str]:
    runtime = gear_resolver_runtime_authority(
        "mage",
        "arcane",
        simc_runtime_revision=simc_runtime_revision,
    )
    return dict(runtime.get("dependencyRevisions") or {})


def validate_gear_snapshot(snapshot: Any) -> list[dict[str, str]]:
    value = snapshot if isinstance(snapshot, dict) else {}
    problems: list[dict[str, str]] = []
    items = [row for row in value.get("items") or [] if isinstance(row, dict)]
    sources = [row for row in value.get("sources") or [] if isinstance(row, dict)]
    variants = [row for row in value.get("variants") or [] if isinstance(row, dict)]
    options = [row for row in value.get("options") or [] if isinstance(row, dict)]
    if not items:
        problems.append({"code": "GEAR_RELEASE_ITEMS_EMPTY", "path": "snapshot.items"})
    if not sources:
        problems.append({"code": "GEAR_RELEASE_SOURCES_EMPTY", "path": "snapshot.sources"})
    if not variants:
        problems.append({"code": "GEAR_RELEASE_VARIANTS_EMPTY", "path": "snapshot.variants"})

    required_text_fields = (
        (items, "itemId", "GEAR_RELEASE_ITEM_ID_EMPTY", "snapshot.items"),
        (sources, "sourceId", "GEAR_RELEASE_SOURCE_ID_EMPTY", "snapshot.sources"),
        (sources, "itemId", "GEAR_RELEASE_SOURCE_ITEM_ID_EMPTY", "snapshot.sources"),
        (sources, "sourceKey", "GEAR_RELEASE_SOURCE_KEY_EMPTY", "snapshot.sources"),
        (variants, "variantId", "GEAR_RELEASE_VARIANT_ID_EMPTY", "snapshot.variants"),
        (variants, "itemId", "GEAR_RELEASE_VARIANT_ITEM_ID_EMPTY", "snapshot.variants"),
        (variants, "variantKey", "GEAR_RELEASE_VARIANT_KEY_EMPTY", "snapshot.variants"),
        (options, "optionId", "GEAR_RELEASE_OPTION_ID_EMPTY", "snapshot.options"),
        (options, "optionKey", "GEAR_RELEASE_OPTION_KEY_EMPTY", "snapshot.options"),
    )
    for rows, field, code, path in required_text_fields:
        if any(not _text(row.get(field)) for row in rows):
            problems.append({"code": code, "path": path})

    def duplicate_values(rows: Iterable[dict[str, Any]], key: Callable[[dict[str, Any]], Any], code: str, path: str):
        seen = set()
        duplicates = set()
        for row in rows:
            value = key(row)
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            problems.append({"code": code, "path": path})

    duplicate_values(items, lambda row: _text(row.get("itemId")), "GEAR_RELEASE_ITEM_ID_DUPLICATE", "snapshot.items")
    duplicate_values(sources, lambda row: _text(row.get("sourceId")), "GEAR_RELEASE_SOURCE_ID_DUPLICATE", "snapshot.sources")
    duplicate_values(variants, lambda row: _text(row.get("variantId")), "GEAR_RELEASE_VARIANT_ID_DUPLICATE", "snapshot.variants")
    duplicate_values(variants, lambda row: (_text(row.get("itemId")), _text(row.get("variantKey"))), "GEAR_RELEASE_VARIANT_KEY_DUPLICATE", "snapshot.variants")
    duplicate_values(options, lambda row: _text(row.get("optionId")), "GEAR_RELEASE_OPTION_ID_DUPLICATE", "snapshot.options")
    duplicate_values(options, lambda row: _text(row.get("optionKey")), "GEAR_RELEASE_OPTION_KEY_DUPLICATE", "snapshot.options")

    item_ids = {_text(row.get("itemId")) for row in items}
    variant_ids = {_text(row.get("variantId")) for row in variants}
    if any(_text(row.get("itemId")) not in item_ids for row in sources):
        problems.append({"code": "GEAR_RELEASE_SOURCE_ITEM_ORPHAN", "path": "snapshot.sources"})
    if any(_text(row.get("itemId")) not in item_ids for row in variants):
        problems.append({"code": "GEAR_RELEASE_VARIANT_ITEM_ORPHAN", "path": "snapshot.variants"})
    if any(_text(row.get("variantId")) and _text(row.get("variantId")) not in variant_ids for row in options):
        problems.append({"code": "GEAR_RELEASE_OPTION_VARIANT_ORPHAN", "path": "snapshot.options"})
    return problems


def _observed_template_item_level(raw: dict[str, Any]) -> tuple[int, bool]:
    """Return the observed instance level and whether two source spellings conflict."""

    declared_item_level = _int(raw.get("itemLevel"))
    declared_ilevel = _int(raw.get("ilevel"))
    return (
        declared_item_level or declared_ilevel,
        (
            declared_item_level > 0
            and declared_ilevel > 0
            and declared_item_level != declared_ilevel
        ),
    )


def _observed_profile_urls(value: Any) -> set[str]:
    """Read bounded player-profile identifiers carried by observed instance evidence."""

    row = value if isinstance(value, dict) else {}
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    urls: set[str] = set()
    for source in (row, payload):
        for field in ("profileUrl", "sourceProfileUrl", "sourceUrl", "url"):
            url = _text(source.get(field))
            if url:
                urls.add(url)
        for ref in source.get("observedProfileRefs") or []:
            if not isinstance(ref, dict):
                continue
            for field in ("profileUrl", "sourceProfileUrl", "sourceUrl", "url"):
                url = _text(ref.get(field))
                if url:
                    urls.add(url)
    return urls


def _observed_template_instance_options(raw: dict[str, Any], observed_item_level: int) -> dict[str, str]:
    """Canonicalize exactly the SimC instance facts present in one observed slot."""

    options = dict(observed_gear_simc_options(raw))
    if observed_item_level > 0:
        options["ilevel"] = str(observed_item_level)
    return {
        key: normalized
        for key, value in options.items()
        if key in SIMC_GEAR_OPTION_KEYS
        and (normalized := normalize_option_value(value))
    }


def _canonical_observed_template_variant(
    raw: dict[str, Any],
    *,
    item_id: str,
    slot: str,
    variant_key: str,
    variants: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Resolve a legacy observed key to its one sealed, same-player instance.

    Older observed templates encode a variant key as concatenated ``field:value``
    text, while staging now stores a canonical JSON form.  The serialized key is
    not a gameplay fact, so that representation change may be bridged only by the
    exact observed item id, slot, instance level, all SimC fields, and target
    player profile identity.  Any ambiguity remains unavailable.
    """

    normalized_item_id = _text(item_id)
    normalized_slot = normalize_slot(slot)
    normalized_variant_key = _text(variant_key)
    candidates = [
        row
        for row in variants
        if isinstance(row, dict)
        and _text(row.get("itemId")) == normalized_item_id
        and _text(row.get("status")).lower() == "verified"
        and normalize_slot(row.get("slot")) == normalized_slot
    ]
    exact = [
        row for row in candidates
        if _text(row.get("variantKey")) == normalized_variant_key
    ]
    if len(exact) == 1:
        return exact[0]

    normalized_variant_key = normalize_option_value(normalized_variant_key)
    normalized = [
        row for row in candidates
        if normalized_variant_key
        and normalize_option_value(row.get("variantKey")) == normalized_variant_key
    ]
    if len(normalized) == 1:
        return normalized[0]

    observed_item_level, conflicting_levels = _observed_template_item_level(raw)
    profile_urls = _observed_profile_urls(raw)
    expected_options = _observed_template_instance_options(raw, observed_item_level)
    if (
        not normalized_variant_key
        or conflicting_levels
        or observed_item_level <= 0
        or not profile_urls
        or not expected_options
    ):
        return {}

    equivalent = []
    for candidate in candidates:
        if _text(candidate.get("sourceType")).lower() != "observed_profile":
            continue
        if _int(candidate.get("itemLevel")) != observed_item_level:
            continue
        candidate_options = {
            key: normalized
            for key, value in (candidate.get("simcOptions") or {}).items()
            if key in SIMC_GEAR_OPTION_KEYS
            and (normalized := normalize_option_value(value))
        }
        if candidate_options != expected_options:
            continue
        if not (_observed_profile_urls(candidate) & profile_urls):
            continue
        equivalent.append(candidate)
    return equivalent[0] if len(equivalent) == 1 else {}


def selection_intent_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
    gear_snapshot: dict[str, Any] | None = None,
    capability_revision: str = "",
) -> dict[str, Any]:
    snapshot = gear_snapshot if isinstance(gear_snapshot, dict) else {}
    enhancements_are_public_evidence = gear_release.is_public_observed_source(
        template.get("sourceKey")
    )
    items_by_id = {
        _text(row.get("itemId")): row
        for row in snapshot.get("items") or []
        if isinstance(row, dict) and _text(row.get("itemId"))
    }
    variants_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("variants") or []:
        if not isinstance(row, dict) or not _text(row.get("itemId")):
            continue
        variants_by_item.setdefault(_text(row.get("itemId")), []).append(row)
    verified_options = [
        row
        for row in snapshot.get("options") or []
        if isinstance(row, dict)
        and _text(row.get("optionKey"))
        and _text(row.get("status")).lower() == "verified"
        and row.get("isVisible") is True
    ]

    def matching_variant(
        raw: dict[str, Any],
        item_id: str,
        slot: str,
        variant_key: str,
    ) -> dict[str, Any]:
        return _canonical_observed_template_variant(
            raw,
            item_id=item_id,
            slot=slot,
            variant_key=variant_key,
            variants=variants_by_item.get(item_id, []),
        )

    def option_type(row: dict[str, Any]) -> str:
        normalized = _text(row.get("optionType")).lower()
        return "gem" if normalized in {"socket", "gem"} else normalized

    def option_applies(row: dict[str, Any], slot: str) -> bool:
        raw_applicable = [
            _text(value)
            for value in row.get("applicableSlots") or []
            if _text(value)
        ]
        applicable = [
            normalize_slot(value)
            for value in raw_applicable
        ]
        return not raw_applicable or "*" in raw_applicable or slot in applicable

    def unique_option_key(slot: str, expected_types: set[str], field: str, raw_value: str) -> str:
        normalized_value = normalize_option_value(raw_value)
        matches = [
            row
            for row in verified_options
            if option_type(row) in expected_types
            and option_applies(row, slot)
            and normalize_option_value(
                (row.get("simcOptions") or {}).get(field)
                if isinstance(row.get("simcOptions"), dict)
                else ""
            ) == normalized_value
        ]
        option_keys = {_text(row.get("optionKey")) for row in matches}
        return next(iter(option_keys)) if len(option_keys) == 1 else ""

    def raw_enhancement_options(
        raw: dict[str, Any],
        slot: str,
        socket_count: int,
    ) -> dict[str, str]:
        payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
        sources = [raw]
        for enhancement_by_slot in (
            template.get("enhancementBySlot"),
            payload.get("enhancementBySlot"),
        ):
            if not isinstance(enhancement_by_slot, dict):
                continue
            for raw_slot, value in enhancement_by_slot.items():
                if normalize_slot(raw_slot) == slot and isinstance(value, dict):
                    sources.append(value)
        values: dict[str, set[str]] = {}
        for source in sources:
            observed = observed_gear_simc_options(source)
            raw_gem_sequence = _text(observed.get("gem_id"))
            if raw_gem_sequence:
                gem_tokens = raw_gem_sequence.split("/")
                if (
                    socket_count <= 0
                    or any(not token.strip() or not token.strip().isdigit() for token in gem_tokens)
                    or len(gem_tokens) > socket_count
                ):
                    raise GearReleaseIntegrityError(
                        "template gem sequence conflicts with materialized socket capacity"
                    )
            for field, value in observed.items():
                if field not in {"gem_id", "enchant_id", "embellishment"}:
                    continue
                normalized = normalize_option_value(value)
                if normalized:
                    values.setdefault(field, set()).add(normalized)
        if len(values.get("gem_id", set())) > 1:
            raise GearReleaseIntegrityError(
                "template gem sequence conflicts with materialized socket capacity"
            )
        return {
            field: next(iter(candidates))
            for field, candidates in values.items()
            if len(candidates) == 1
        }

    def canonical_enhancements(
        raw: dict[str, Any],
        slot: str,
        item_id: str,
        variant_key: str,
    ) -> dict[str, Any]:
        empty = {
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
        }
        if (
            capability_revision != gear_socket_authority.CAPABILITY_REVISION
            or not enhancements_are_public_evidence
        ):
            return empty
        item = items_by_id.get(item_id)
        variant = matching_variant(raw, item_id, slot, variant_key)
        if not isinstance(item, dict) or not variant:
            return empty
        item_payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        variant_payload = variant.get("payload") if isinstance(variant.get("payload"), dict) else {}
        base_capabilities = (
            item_payload.get("baseCapabilities")
            if isinstance(item_payload.get("baseCapabilities"), dict)
            else {}
        )
        overrides = (
            variant_payload.get("capabilityOverrides")
            if isinstance(variant_payload.get("capabilityOverrides"), dict)
            else {}
        )
        socket_count = _int(overrides.get("socketCount", base_capabilities.get("socketCount")))
        can_enchant = item_can_enchant_slot(item_payload, slot, item) or base_capabilities.get("canEnchant") is True
        if "canEnchant" in overrides:
            can_enchant = overrides.get("canEnchant") is True
        management_fields = gear_enhancement_management.validated_enhancement_management_fields(
            variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {},
            variant_payload.get("enhancementManagement"),
            capability_revision,
        )
        can_embellish = (
            overrides.get("canEmbellish", base_capabilities.get("canEmbellish")) is True
            or management_fields.get("embellishment") == "editor_managed"
        )
        observed = raw_enhancement_options(raw, slot, socket_count)
        selected = dict(empty)
        raw_gems = [
            token.strip()
            for token in observed.get("gem_id", "").split("/")
            if token.strip()
        ]
        if raw_gems and (socket_count <= 0 or len(raw_gems) > socket_count):
            raise GearReleaseIntegrityError(
                "template gem sequence conflicts with materialized socket capacity"
            )
        if raw_gems and socket_count > 0 and len(raw_gems) <= socket_count:
            gem_option_ids = [
                unique_option_key(slot, {"gem"}, "gem_id", gem_id)
                for gem_id in raw_gems
            ]
            if all(gem_option_ids):
                selected["gemOptionIds"] = gem_option_ids
        variant_simc_options = (
            variant.get("simcOptions") if isinstance(variant.get("simcOptions"), dict) else {}
        )
        raw_enchant = observed.get("enchant_id", "")
        source_only_enchant = (
            management_fields.get("enchant_id") == "source_only"
            and normalize_option_value(variant_simc_options.get("enchant_id")) == raw_enchant
        )
        if raw_enchant and can_enchant and not source_only_enchant:
            selected["enchantOptionId"] = unique_option_key(
                slot,
                {"enchant", "runeforge"},
                "enchant_id",
                raw_enchant,
            )
        raw_embellishment = observed.get("embellishment", "")
        source_only_embellishment = (
            management_fields.get("embellishment") == "source_only"
            and normalize_option_value(variant_simc_options.get("embellishment")) == raw_embellishment
        )
        if raw_embellishment and can_embellish and not source_only_embellishment:
            selected["embellishmentOptionId"] = unique_option_key(
                slot,
                {"embellishment"},
                "embellishment",
                raw_embellishment,
            )
        return selected

    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            continue
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        if not slot or not item_id or slot in slots:
            continue
        variant_key = _text(raw.get("variantKey"))
        resolved_variant = matching_variant(raw, item_id, slot, variant_key)
        canonical_variant_key = _text(resolved_variant.get("variantKey")) or variant_key
        enhancements = canonical_enhancements(raw, slot, item_id, canonical_variant_key)
        slots[slot] = {
            "itemId": item_id,
            "variantKey": canonical_variant_key,
            **enhancements,
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


def community_template_import_evidence_from_template(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    gear_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Seal observed per-slot display facts without changing Resolver Intent."""

    snapshot = gear_snapshot if isinstance(gear_snapshot, dict) else {}
    item_rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("items") or []:
        if not isinstance(row, dict) or not _text(row.get("itemId")):
            continue
        item_rows_by_id.setdefault(_text(row.get("itemId")), []).append(row)
    variant_rows_by_item: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.get("variants") or []:
        if not isinstance(row, dict):
            continue
        item_id = _text(row.get("itemId"))
        if item_id:
            variant_rows_by_item.setdefault(item_id, []).append(row)

    slots: dict[str, dict[str, Any]] = {}
    for raw in template.get("gearItems") or []:
        if not isinstance(raw, dict):
            raise GearReleaseIntegrityError("community import evidence gear item is invalid")
        slot = normalize_slot(raw.get("slot") or raw.get("simcSlot"))
        item_id = _text(raw.get("itemId") or raw.get("id"))
        variant_key = _text(raw.get("variantKey"))
        if not slot or not item_id or not variant_key or slot in slots:
            raise GearReleaseIntegrityError("community import evidence selection is incomplete")
        # Observed-profile ingestion serializes an item instance's actual level as
        # ``ilevel``.  Older/community payloads may expose the same observed fact
        # as ``itemLevel`` instead.  Neither spelling may fall back to the generic
        # catalogue item level: ambiguity is evidence failure, not a value to
        # calculate away.
        observed_item_level, conflicting_levels = _observed_template_item_level(raw)
        if conflicting_levels:
            raise GearReleaseIntegrityError(
                "community import evidence observed item level is ambiguous"
            )
        if observed_item_level <= 0:
            raise GearReleaseIntegrityError("community import evidence observed item level is missing")

        item_rows = item_rows_by_id.get(item_id) or []
        variant = _canonical_observed_template_variant(
            raw,
            item_id=item_id,
            slot=slot,
            variant_key=variant_key,
            variants=variant_rows_by_item.get(item_id, []),
        )
        if len(item_rows) != 1 or not variant:
            raise GearReleaseIntegrityError("community import evidence exact gear identity is unavailable")
        item = item_rows[0]
        if (
            _text(variant.get("status")).lower() != "verified"
            or normalize_slot(variant.get("slot")) != slot
            or _int(variant.get("itemLevel")) != observed_item_level
        ):
            raise GearReleaseIntegrityError("community import evidence variant does not match observed item level")
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
        game_asset = metadata.get("gameAsset") if isinstance(metadata.get("gameAsset"), dict) else {}
        icon_url = _text(metadata.get("iconUrl"))
        if _text(game_asset.get("status")).lower() != "verified" or not icon_url:
            raise GearReleaseIntegrityError("community import evidence verified item icon is missing")
        slots[slot] = {
            "itemId": item_id,
            "variantKey": _text(variant.get("variantKey")),
            "observedItemLevel": observed_item_level,
            "iconUrl": icon_url,
        }

    if not slots:
        raise GearReleaseIntegrityError("community import evidence selection is empty")
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    template_evidence = (
        payload.get("templateEvidence")
        if isinstance(payload.get("templateEvidence"), dict)
        else {}
    )
    ordered_slots = {slot: slots[slot] for slot in sorted(slots)}
    source_fingerprint = _canonical_digest({
        "templateId": _text(template.get("templateId")),
        "sourceKey": _text(template.get("sourceKey")),
        "profileHash": _text(template.get("profileHash") or template_evidence.get("profileHash")),
        "gearHash": _text(template.get("gearHash") or template_evidence.get("gearHash") or template.get("signature")),
        "gearReleaseId": _text(gear_release_id),
        "slots": ordered_slots,
    })
    return {
        "schemaRevision": COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION,
        "sourceFingerprint": source_fingerprint,
        "slots": ordered_slots,
    }


def prepare_staging_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_minimums: Mapping[str, Any],
    source_revision: str = "legacy-import-r0",
    parent_release_id: str = "",
) -> dict[str, Any]:
    if not isinstance(socket_bonus_minimums, Mapping) or not socket_bonus_minimums:
        raise GearReleaseIntegrityError("socket bonus evidence must be a non-empty mapping")
    normalized_bonus_minimums = socket_bonus_minimums
    snapshot = _materialize_enhancement_management(
        _project_socket_facts_into_release_payloads(
            gear_socket_authority.materialize_gear_socket_facts(
                store.snapshot_staging_gear(),
                season_revision=season_revision,
                socket_bonus_minimums=normalized_bonus_minimums,
            )
        ),
        _text(dependency_revisions.get("capabilityRevision")),
    )
    problems = validate_gear_snapshot(snapshot)
    if problems:
        raise GearReleaseIntegrityError(json.dumps(problems, ensure_ascii=False, sort_keys=True))
    summary = gear_snapshot_summary(snapshot)
    release = gear_release.build_release(
        release_kind="gear",
        season_revision=season_revision,
        schema_revision="gear-release-v1",
        content=summary,
        dependency_revisions=dependency_revisions,
        release_status="validated",
        source={
            "sourceRevision": source_revision,
            "stagingSnapshotHash": summary["snapshotHash"],
            "sourceEvidence": {
                "simcRuntimeRevision": _text(dependency_revisions.get("simcRuntimeRevision")),
                "socketProbeDigest": _socket_probe_digest(normalized_bonus_minimums),
                "materializedSocketFactDigest": _materialized_socket_fact_digest(snapshot),
            },
        },
        parent_release_id=parent_release_id,
    )
    gate = {"status": "validated", **summary}
    return {"release": release, "snapshot": snapshot, "gate": gate}


def build_legacy_gear_release(
    store: GearReleaseStore,
    *,
    season_revision: str,
    dependency_revisions: dict[str, Any],
    socket_bonus_minimums: Mapping[str, Any],
    source_revision: str = "legacy-import-r0",
) -> dict[str, Any]:
    prepared = prepare_staging_gear_release(
        store,
        season_revision=season_revision,
        dependency_revisions=dependency_revisions,
        socket_bonus_minimums=socket_bonus_minimums,
        source_revision=source_revision,
    )
    release = prepared["release"]
    snapshot = prepared["snapshot"]
    gate = prepared["gate"]
    seal = store.seal_gear_release(
        release,
        snapshot,
        gate_result=gate,
        event={"mode": source_revision, "gate": gate},
    )
    return {"release": release, "snapshot": snapshot, "gate": gate, "seal": seal}


def _template_candidate(
    template: dict[str, Any],
    *,
    gear_release_id: str,
    season_revision: str,
    level: int,
    gear_snapshot: dict[str, Any],
    capability_revision: str,
) -> dict[str, Any]:
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    evidence = payload.get("templateEvidence") if isinstance(payload.get("templateEvidence"), dict) else {}
    refs = [row for row in template.get("sourceRefs") or [] if isinstance(row, dict)]
    ref = refs[0] if refs else {}
    selection_intent = selection_intent_from_template(
        template,
        gear_release_id=gear_release_id,
        season_revision=season_revision,
        level=level,
        gear_snapshot=gear_snapshot,
        capability_revision=capability_revision,
    )
    candidate = {
        "id": _text(template.get("templateId")),
        "classKey": _text(template.get("classKey")),
        "specKey": _text(template.get("specKey")),
        "sourceKey": _text(template.get("sourceKey")),
        "sourceUrl": _text(template.get("sourceUrl") or evidence.get("sourceProfileUrl") or ref.get("sourceUrl")),
        "sourceStatus": _text(template.get("sourceStatus")),
        "sampleCount": _int(template.get("sampleCount") or evidence.get("sampleCount") or ref.get("sampleCount")),
        "profileHash": _text(template.get("profileHash") or evidence.get("profileHash")),
        "gearHash": _text(template.get("gearHash") or evidence.get("gearHash") or template.get("signature")),
        "updatedAt": _text(template.get("updatedAt")),
        "expiresAt": _text(template.get("expiresAt")),
        "selectionIntent": selection_intent,
    }
    try:
        candidate["importEvidence"] = community_template_import_evidence_from_template(
            template,
            gear_release_id=gear_release_id,
            gear_snapshot=gear_snapshot,
        )
    except GearReleaseIntegrityError:
        # A historical/incomplete observed template remains browseable but cannot win an
        # importable release; the election records the missing sealed evidence.
        pass
    return candidate


def _release_rows_from_election(
    election: dict[str, Any],
    templates_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    rank_by_spec: dict[tuple[str, str], int] = {}
    for elected in [*(election.get("winners") or []), *(election.get("standbys") or [])]:
        key = (_text(elected.get("classKey")), _text(elected.get("specKey")))
        rank_by_spec[key] = rank_by_spec.get(key, 0) + 1
        original = templates_by_id.get(_text(elected.get("candidateId")), {})
        payload = original.get("payload") if isinstance(original.get("payload"), dict) else {}
        release_payload = _canonical(original)
        release_payload["importEvidence"] = _canonical(elected.get("importEvidence") or {})
        rows.append({
            "templateId": _text(elected.get("candidateId")),
            "classKey": key[0],
            "specKey": key[1],
            "role": _text(elected.get("role")),
            "electionRank": rank_by_spec[key],
            "sourceKey": _text(elected.get("sourceKey")),
            "sourceUrl": _text(elected.get("sourceUrl")),
            "sourceStatus": _text(elected.get("sourceStatus")),
            "sampleCount": _int(elected.get("sampleCount")),
            "profileHash": _text(elected.get("profileHash")),
            "gearHash": _text(elected.get("gearHash")),
            "selectionIntent": _canonical(elected.get("selectionIntent") or {}),
            "resolvedGearSignature": _text(elected.get("resolvedGearSignature")),
            "semanticGearSignature": _text(elected.get("semanticGearSignature")),
            "dependencyVector": _canonical(elected.get("dependencyVector") or {}),
            "evidence": _canonical(payload.get("templateEvidence") or {"sourceRefs": original.get("sourceRefs") or []}),
            "problems": [],
            "payload": release_payload,
            "updatedAt": _text(elected.get("updatedAt")),
            "expiresAt": _text(elected.get("expiresAt")),
        })
    for rejected in election.get("rejected") or []:
        candidate_id = _text(rejected.get("candidateId"))
        original = templates_by_id.get(candidate_id, {})
        rows.append({
            "templateId": candidate_id,
            "classKey": _text(rejected.get("classKey")),
            "specKey": _text(rejected.get("specKey")),
            "role": "rejected",
            "electionRank": 0,
            "sourceKey": _text(original.get("sourceKey")),
            "sourceUrl": _text(original.get("sourceUrl")),
            "sourceStatus": _text(original.get("sourceStatus")),
            "sampleCount": 0,
            "profileHash": "",
            "gearHash": _text(original.get("signature")),
            "selectionIntent": {},
            "resolvedGearSignature": "",
            "semanticGearSignature": "",
            "dependencyVector": {},
            "evidence": _canonical(original.get("sourceRefs") or []),
            "problems": _canonical(rejected.get("problems") or []),
            "payload": _canonical(original),
            "updatedAt": _text(original.get("updatedAt")),
            "expiresAt": _text(original.get("expiresAt")),
        })
    return sorted(rows, key=lambda row: (row["classKey"], row["specKey"], row["role"], row["electionRank"], row["templateId"]))


def prepare_staging_community_release(
    store: GearReleaseStore,
    *,
    gear_release_descriptor: dict[str, Any],
    gear_snapshot: dict[str, Any],
    dependency_revisions: dict[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    now: str,
    level: int = 90,
    source_revision: str = "legacy-import-r0",
    parent_release_id: str = "",
    resolver_for_spec: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    expected = sorted({
        (_text(class_key), _text(spec_key))
        for class_key, spec_key in expected_specs
        if _text(class_key) and _text(spec_key)
    })
    if not expected:
        raise GearReleaseIntegrityError("expected_specs must contain at least one spec")
    templates = store.snapshot_staging_community_templates(expected)
    template_ids = [_text(row.get("templateId")) for row in templates]
    if any(not template_id for template_id in template_ids):
        raise GearReleaseIntegrityError("staging community templateId must be non-empty")
    if len(set(template_ids)) != len(template_ids):
        raise GearReleaseIntegrityError("staging community templateId must be unique")
    templates_by_id = {_text(row.get("templateId")): row for row in templates if _text(row.get("templateId"))}
    release_dependencies = (
        gear_release_descriptor.get("dependencyRevisions")
        if isinstance(gear_release_descriptor.get("dependencyRevisions"), dict)
        else {}
    )
    capability_revision = _text(
        release_dependencies.get("capabilityRevision")
        or dependency_revisions.get("capabilityRevision")
    )
    candidates = [
        _template_candidate(
            template,
            gear_release_id=gear_release_descriptor["releaseId"],
            season_revision=gear_release_descriptor["seasonRevision"],
            level=level,
            gear_snapshot=gear_snapshot,
            capability_revision=capability_revision,
        )
        for template in templates
    ]
    prepared_authority = (
        CandidateGearAuthorityIndex(gear_snapshot, gear_release_descriptor)
        if resolver_for_spec is None
        else None
    )

    def resolve_candidate(intent: dict[str, Any]) -> dict[str, Any]:
        eligibility = intent.get("eligibilityContext") or {}
        class_key = _text(eligibility.get("classKey"))
        spec_key = _text(eligibility.get("specKey"))
        if resolver_for_spec is not None:
            return resolver_for_spec(class_key, spec_key, intent)
        runtime = gear_resolver_runtime_authority(
            class_key,
            spec_key,
            simc_runtime_revision=_text(dependency_revisions.get("simcRuntimeRevision")),
        )
        runtime["dependencyRevisions"] = dict(dependency_revisions)
        authority = build_candidate_authority_context(
            gear_snapshot,
            intent,
            runtime,
            gear_release_descriptor,
            prepared_index=prepared_authority,
        )
        return gear_resolver.resolve(intent, authority)

    election = gear_release.elect_community_candidates(
        candidates,
        gear_release_id=gear_release_descriptor["releaseId"],
        resolver=resolve_candidate,
        now=now,
        expected_specs=expected,
    )
    rows = _release_rows_from_election(election, templates_by_id)
    summary = community_rows_summary(rows)
    release = gear_release.build_release(
        release_kind="community",
        season_revision=gear_release_descriptor["seasonRevision"],
        schema_revision="community-release-v1",
        content=summary,
        dependency_revisions=dependency_revisions,
        release_status=election["status"],
        source={
            "sourceRevision": source_revision,
            "validatedAgainstGearReleaseId": gear_release_descriptor["releaseId"],
            "stagingTemplateCount": len(templates),
        },
        parent_release_id=parent_release_id,
        validated_against_release_id=gear_release_descriptor["releaseId"],
    )
    gate = {
        "status": election["status"],
        "expectedSpecCount": election["expectedSpecCount"],
        "winnerSpecCount": election["winnerSpecCount"],
        "standbyCount": len(election.get("standbys") or []),
        "rejectedCount": len(election.get("rejected") or []),
        "missingSpecs": election.get("missingSpecs") or [],
        **summary,
    }
    return {"release": release, "rows": rows, "election": election, "gate": gate}


def build_legacy_community_release(
    store: GearReleaseStore,
    *,
    gear_release_descriptor: dict[str, Any],
    gear_snapshot: dict[str, Any],
    dependency_revisions: dict[str, Any],
    expected_specs: Iterable[tuple[str, str]],
    now: str,
    level: int = 90,
    source_revision: str = "legacy-import-r0",
    resolver_for_spec: Callable[[str, str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prepared = prepare_staging_community_release(
        store,
        gear_release_descriptor=gear_release_descriptor,
        gear_snapshot=gear_snapshot,
        dependency_revisions=dependency_revisions,
        expected_specs=expected_specs,
        now=now,
        level=level,
        source_revision=source_revision,
        resolver_for_spec=resolver_for_spec,
    )
    release = prepared["release"]
    rows = prepared["rows"]
    election = prepared["election"]
    gate = prepared["gate"]
    seal = store.seal_community_release(
        release,
        rows,
        gate_result=gate,
        event={"mode": source_revision, "gate": gate},
    )
    return {"release": release, "rows": rows, "election": election, "gate": gate, "seal": seal}


def _store_from_environment() -> GearReleaseStore:
    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("gear release tooling requires WOW_DATABASE_RUNTIME=postgres_only and WOW_DATABASE_URL")
    return GearReleaseStore(lambda: connect_postgres(config.database_url))


class _CountingCursor:
    def __init__(self, cursor, counter):
        self._cursor = cursor
        self._counter = counter

    def execute(self, statement, *args, **kwargs):
        self._counter.record(statement)
        return self._cursor.execute(statement, *args, **kwargs)

    def executemany(self, statement, *args, **kwargs):
        self._counter.record(statement)
        return self._cursor.executemany(statement, *args, **kwargs)

    def __enter__(self):
        self._cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self._cursor.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _CountingConnection:
    def __init__(self, connection, counter):
        self._connection = connection
        self._counter = counter

    def cursor(self, *args, **kwargs):
        return _CountingCursor(self._connection.cursor(*args, **kwargs), self._counter)

    def __getattr__(self, name):
        return getattr(self._connection, name)


class _StatementCounter:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory
        self.total = 0
        self.transaction_control = 0
        self.read_queries = 0
        self.write_statements = 0

    def __call__(self):
        return _CountingConnection(self._connection_factory(), self)

    def record(self, statement):
        normalized = " ".join(str(statement or "").split()).upper()
        self.total += 1
        if normalized.startswith("SET TRANSACTION"):
            self.transaction_control += 1
        elif normalized.startswith(("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "TRUNCATE ")):
            self.write_statements += 1
        else:
            self.read_queries += 1

    def snapshot(self):
        return {
            "total": self.total,
            "transactionControl": self.transaction_control,
            "readQueries": self.read_queries,
            "writeStatements": self.write_statements,
        }


def _shadow_store_from_environment() -> PostgresCacheStore:
    config = database_config_from_env()
    if not postgres_only_runtime_enabled(config):
        raise RuntimeError("gear release shadow requires WOW_DATABASE_RUNTIME=postgres_only and WOW_DATABASE_URL")
    counter = _StatementCounter(lambda: connect_postgres(config.database_url))
    store = PostgresCacheStore(counter)
    store.shadow_read_statement_metrics = counter.snapshot
    return store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build-legacy-gear", "build-legacy-all", "show", "shadow", "promote", "rollback"))
    parser.add_argument("--season-revision", default="")
    parser.add_argument("--simc-runtime-revision", default="")
    parser.add_argument("--release-id", default="")
    parser.add_argument("--gear-release-id", default="")
    parser.add_argument("--community-release-id", default="")
    parser.add_argument("--talent-catalog-revision", default="")
    parser.add_argument("--manifest-revision", default="")
    parser.add_argument("--rollback-manifest-revision", default="")
    parser.add_argument("--expected-generation", type=int, default=-1)
    parser.add_argument("--target-mode", choices=("active", "transitional"), default="active")
    parser.add_argument("--updated-by", default="")
    parser.add_argument("--level", type=int, default=90)
    parser.add_argument("--expect-formal-active", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "promote":
        required = {
            "--season-revision": args.season_revision,
            "--simc-runtime-revision": args.simc_runtime_revision,
            "--gear-release-id": args.gear_release_id,
            "--talent-catalog-revision": args.talent_catalog_revision,
            "--updated-by": args.updated_by,
        }
        missing = [name for name, value in required.items() if not _text(value)]
        if args.expected_generation < 0:
            missing.append("--expected-generation")
        if missing:
            raise SystemExit(", ".join(missing) + " are required")
        store = _store_from_environment()
        gear_descriptor = store.get_release(args.gear_release_id)
        if not gear_descriptor:
            raise GearReleaseIntegrityError("Gear Release is missing")
        community_descriptor = None
        if args.community_release_id:
            community_descriptor = store.get_release(args.community_release_id)
            if not community_descriptor:
                raise GearReleaseIntegrityError("Community Release is missing")
        dependencies = runtime_dependency_revisions(args.simc_runtime_revision)
        manifest = gear_release.build_manifest(
            season_revision=args.season_revision,
            gear_release=gear_descriptor,
            community_release=community_descriptor,
            talent_catalog_revision=args.talent_catalog_revision,
            dependency_revisions=dependencies,
            rollback_manifest_revision=args.rollback_manifest_revision,
        )
        command = gear_release.build_pointer_command(
            "promote",
            manifest["manifestRevision"],
            args.expected_generation,
            args.rollback_manifest_revision,
            target_mode="active",
        )
        result = store.seal_manifest_and_compare_and_swap_pointer(
            manifest,
            command,
            updated_by=args.updated_by,
        )
        print(json.dumps({"status": "updated", "manifestRevision": manifest["manifestRevision"], **result}, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "rollback":
        if args.expected_generation < 0 or not _text(args.updated_by):
            raise SystemExit("--expected-generation and --updated-by are required")
        if args.target_mode == "active" and not _text(args.manifest_revision):
            raise SystemExit("--manifest-revision is required for active rollback")
        command = gear_release.build_pointer_command(
            "rollback",
            args.manifest_revision,
            args.expected_generation,
            args.rollback_manifest_revision,
            target_mode=args.target_mode,
        )
        result = _store_from_environment().compare_and_swap_pointer(
            command,
            updated_by=args.updated_by,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.command == "shadow":
        if not args.gear_release_id or not args.community_release_id or not args.simc_runtime_revision:
            raise SystemExit("--gear-release-id, --community-release-id and --simc-runtime-revision are required")
        shadow_store = _shadow_store_from_environment()
        result = gear_release_shadow.run_release_shadow(
            shadow_store,
            expected_specs=expected_spec_pairs(),
            gear_release_id=args.gear_release_id,
            community_release_id=args.community_release_id,
            simc_runtime_revision=args.simc_runtime_revision,
            level=args.level,
            expect_formal_active=args.expect_formal_active,
        )
        cache_metrics = getattr(shadow_store, "gear_authority_cache_metrics", None)
        statement_metrics = getattr(shadow_store, "shadow_read_statement_metrics", None)
        if callable(cache_metrics):
            result["authorityCache"] = cache_metrics()
        if callable(statement_metrics):
            result["databaseStatements"] = statement_metrics()
            if result["databaseStatements"].get("writeStatements"):
                result["status"] = "blocked"
                result.setdefault("blockers", []).append({
                    "kind": "SHADOW_COMPARE_BLOCKED",
                    "code": "SHADOW_WRITE_STATEMENT_DETECTED",
                    "title": "Release shadow comparison blocked.",
                    "detail": "Internal shadow executed a write statement.",
                    "path": "shadow",
                    "retryable": False,
                    "meta": {},
                })
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result.get("status") == "pass" else 2
    store = _store_from_environment()
    if args.command == "show":
        print(json.dumps(store.get_release(args.release_id), ensure_ascii=False, sort_keys=True))
        return 0
    if not args.season_revision or not args.simc_runtime_revision:
        raise SystemExit("--season-revision and --simc-runtime-revision are required")
    dependencies = runtime_dependency_revisions(args.simc_runtime_revision)
    try:
        from .simulator_payload import simc_binary
    except ImportError:
        from simulator_payload import simc_binary
    socket_bonus_minimums = load_simc_socket_bonus_minimums(simc_binary())
    gear = build_legacy_gear_release(
        store,
        season_revision=args.season_revision,
        dependency_revisions=dependencies,
        socket_bonus_minimums=socket_bonus_minimums,
    )
    output = {"gear": {"release": gear["release"], "gate": gear["gate"], "seal": gear["seal"]}}
    if args.command == "build-legacy-all":
        community = build_legacy_community_release(
            store,
            gear_release_descriptor=gear["release"],
            gear_snapshot=gear["snapshot"],
            dependency_revisions=dependencies,
            expected_specs=expected_spec_pairs(),
            now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            level=args.level,
        )
        output["community"] = {"release": community["release"], "gate": community["gate"], "seal": community["seal"]}
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "COMMUNITY_TEMPLATE_IMPORT_EVIDENCE_REVISION",
    "build_legacy_community_release",
    "build_legacy_gear_release",
    "expected_spec_pairs",
    "load_simc_socket_bonus_minimums",
    "prepare_staging_gear_release",
    "runtime_dependency_revisions",
    "community_template_import_evidence_from_template",
    "selection_intent_from_template",
    "validate_gear_snapshot",
)

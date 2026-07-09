#!/usr/bin/env python3
import json

try:
    from . import gear_public_contract
except ImportError:
    import gear_public_contract


def _json_value(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed is not None else fallback


def _int_value(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _websim_payload_helpers():
    try:
        from .websim_payload import (
            apply_gear_template_legality_gate,
            blocked_baseline_gear_template,
            pending_community_gear_template,
            select_best_baseline_gear_templates,
            select_community_best_gear_templates,
        )
    except ImportError:
        from websim_payload import (
            apply_gear_template_legality_gate,
            blocked_baseline_gear_template,
            pending_community_gear_template,
            select_best_baseline_gear_templates,
            select_community_best_gear_templates,
        )
    return {
        "community_selector": select_community_best_gear_templates,
        "baseline_selector": select_best_baseline_gear_templates,
        "pending_community_factory": pending_community_gear_template,
        "blocked_baseline_factory": blocked_baseline_gear_template,
        "legality_gate": apply_gear_template_legality_gate,
    }


def _websim_payload_read_model_helpers():
    try:
        from .websim_payload import (
            compact_community_gear_template,
            websim_gear_community_template_sync_state,
        )
    except ImportError:
        from websim_payload import (
            compact_community_gear_template,
            websim_gear_community_template_sync_state,
        )
    return {
        "compact_template": compact_community_gear_template,
        "sync_state_builder": websim_gear_community_template_sync_state,
    }


def _websim_payload_item_metadata_helpers():
    try:
        from .websim_payload import (
            ITEM_METADATA_SOURCE,
            apply_item_metadata,
            item_type_metadata_from_payload,
        )
    except ImportError:
        from websim_payload import (
            ITEM_METADATA_SOURCE,
            apply_item_metadata,
            item_type_metadata_from_payload,
        )
    return {
        "apply_item_metadata": apply_item_metadata,
        "metadata_source": ITEM_METADATA_SOURCE,
        "type_metadata_from_payload": item_type_metadata_from_payload,
    }


def build_official_item_metadata_by_id_read_model(rows):
    helpers = _websim_payload_item_metadata_helpers()
    item_metadata_source = helpers["metadata_source"]
    type_metadata_from_payload = helpers["type_metadata_from_payload"]
    metadata_by_id = {}
    for row in rows or []:
        payload = _json_value(row[4], {})
        payload = payload if isinstance(payload, dict) else {}
        metadata = payload.get("_metadata") if isinstance(payload.get("_metadata"), dict) else {}
        metadata_source = str(metadata.get("source") or payload.get("metadataSource") or "").strip()
        source_status = str(row[5] or metadata.get("metadataStatus") or payload.get("sourceStatus") or "").strip()
        has_official_payload_shape = bool(
            payload.get("inventory_type")
            or payload.get("inventoryType")
            or payload.get("item_class")
            or payload.get("itemClass")
            or payload.get("item_subclass")
            or payload.get("itemSubclass")
        )
        if metadata_source != item_metadata_source and not (
            source_status == "verified" and has_official_payload_shape
        ):
            continue
        type_metadata = type_metadata_from_payload(payload)
        item_id = str(row[0] or "").strip()
        display_name = (
            payload.get("displayName")
            or payload.get("localizedName")
            or payload.get("name")
            or row[1]
            or f"Item {item_id}"
        )
        metadata_by_id[item_id] = {
            "itemId": item_id,
            "displayName": display_name,
            "slot": row[2] or "",
            "itemLevel": _int_value(row[3]),
            "quality": payload.get("quality") or "",
            "iconUrl": metadata.get("iconUrl") or payload.get("iconUrl") or "",
            "payload": payload,
            "metadataStatus": source_status or "verified",
            "metadataSource": metadata_source or item_metadata_source,
            "metadataLocale": metadata.get("locale") or "",
            "englishName": metadata.get("englishName") or "",
            **type_metadata,
        }
    return metadata_by_id


def build_hydrated_community_gear_items_read_model(gear_items, official_metadata_by_id):
    apply_item_metadata = _websim_payload_item_metadata_helpers()["apply_item_metadata"]
    official_metadata_by_id = official_metadata_by_id or {}
    hydrated = []
    for item in _json_value(gear_items, []):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("itemId") or item.get("id") or "").strip()
        metadata = official_metadata_by_id.get(item_id) if item_id else None
        hydrated.append(apply_item_metadata(item, metadata) if metadata else item)
    return hydrated


def select_public_gear_templates_for_spec(
    persisted_templates,
    class_key,
    spec_key,
    *,
    community_selector=None,
    baseline_selector=None,
    pending_community_factory=None,
    blocked_baseline_factory=None,
    legality_gate=None,
):
    helpers = None

    def helper(name):
        nonlocal helpers
        if helpers is None:
            helpers = _websim_payload_helpers()
        return helpers[name]

    community_selector = community_selector or helper("community_selector")
    baseline_selector = baseline_selector or helper("baseline_selector")
    pending_community_factory = pending_community_factory or helper("pending_community_factory")
    blocked_baseline_factory = blocked_baseline_factory or helper("blocked_baseline_factory")
    legality_gate = legality_gate or helper("legality_gate")
    persisted_templates = persisted_templates or []

    community_templates = community_selector(
        [template for template in persisted_templates if gear_public_contract.is_real_community_gear_template(template)],
        class_key,
        spec_key,
    )
    community_templates = gear_public_contract.public_gear_templates_for_spec(community_templates, class_key, spec_key)
    if not community_templates and not gear_public_contract.real_player_gear_template_public_import_spec(class_key, spec_key):
        community_templates = [pending_community_factory(class_key, spec_key)]

    baseline_templates = gear_public_contract.public_gear_templates_for_spec(
        baseline_selector(
            [template for template in persisted_templates if gear_public_contract.is_baseline_gear_template(template)]
        ),
        class_key,
        spec_key,
    )
    if not baseline_templates:
        baseline_templates = gear_public_contract.public_baseline_fallback_templates_for_spec(
            class_key,
            spec_key,
            blocked_baseline_factory=blocked_baseline_factory,
        )

    community_templates = [
        legality_gate(template, class_key, spec_key)
        for template in community_templates
    ]
    baseline_templates = [
        legality_gate(template, class_key, spec_key)
        for template in baseline_templates
    ]

    return {
        "communityTemplates": gear_public_contract.public_gear_templates_for_spec(community_templates, class_key, spec_key),
        "baselineTemplates": gear_public_contract.public_gear_templates_for_spec(baseline_templates, class_key, spec_key),
    }


def build_public_gear_template_read_model(
    persisted_templates,
    class_key,
    spec_key,
    *,
    compact=False,
    compact_template=None,
    sync_state_builder=None,
    **selector_kwargs,
):
    selected = select_public_gear_templates_for_spec(
        persisted_templates,
        class_key,
        spec_key,
        **selector_kwargs,
    )
    community_templates = selected["communityTemplates"]
    baseline_templates = selected["baselineTemplates"]
    helpers = None

    def helper(name):
        nonlocal helpers
        if helpers is None:
            helpers = _websim_payload_read_model_helpers()
        return helpers[name]

    sync_state_builder = sync_state_builder or helper("sync_state_builder")
    if compact:
        compact_template = compact_template or helper("compact_template")
        payload_community_templates = [compact_template(template) for template in community_templates]
        payload_baseline_templates = [compact_template(template) for template in baseline_templates]
    else:
        payload_community_templates = community_templates
        payload_baseline_templates = baseline_templates
    selected_templates = [*community_templates, *baseline_templates]

    return {
        "selectedCommunityTemplates": community_templates,
        "selectedBaselineTemplates": baseline_templates,
        "payloadCommunityTemplates": payload_community_templates,
        "payloadBaselineTemplates": payload_baseline_templates,
        "communityTemplateSync": sync_state_builder(selected_templates),
    }

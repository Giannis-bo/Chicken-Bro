#!/usr/bin/env python3

try:
    from . import gear_public_contract
except ImportError:
    import gear_public_contract


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

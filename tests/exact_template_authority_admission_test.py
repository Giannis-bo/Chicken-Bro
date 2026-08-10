from types import SimpleNamespace
import unittest
from unittest.mock import patch

from server.exact_template_authority_binding import canonical_remote_template_source
from server.gear_contracts import EXACT_LOADOUT_CORE_SLOTS
from tests.exact_template_authority_binding_test import (
    admission_proof,
    remote_source,
)


AUTHORITY_IDENTITY = "sha256:" + "2" * 64
CONTENT_HASH = "sha256:" + "3" * 64
REGISTRY_REVISION = "gear-exact-registry:sha256:" + "1" * 64
RULE = "gear-rule-v1"
RUNTIME = "simc-runtime-v1"
RESOLVER = "resolver-v2"


def registry():
    return {
        "registryRevision": REGISTRY_REVISION,
        "templateReferences": [
            {
                "templateScope": "community",
                "templateAuthorityIdentity": AUTHORITY_IDENTITY,
                "templateContentHash": CONTENT_HASH,
                "slot": slot,
                "exactItemInstanceKey": "exact-item-instance:sha256:" + f"{index:064x}",
            }
            for index, slot in enumerate(EXACT_LOADOUT_CORE_SLOTS, start=1)
        ],
    }


def bound():
    return {
        "status": "verified",
        "templateAuthorityIdentity": AUTHORITY_IDENTITY,
        "selectionIntent": canonical_remote_template_source(
            remote_source()
        ).selection_intent,
        "authorityContext": {"dependencyVector": {"gearRuleRevision": RULE}},
    }


def ready_loadout():
    return {
        "status": "ready",
        "orderedSlots": [
            {
                "slot": slot,
                "exactItemInstanceKey": "exact-item-instance:sha256:" + f"{index:064x}",
            }
            for index, slot in enumerate(EXACT_LOADOUT_CORE_SLOTS, start=1)
        ],
    }


class FakeBundleStore:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def load_verified_bundle_for_exact_item(self, exact_key, **kwargs):
        self.calls.append((exact_key, kwargs))
        if self.fail:
            raise RuntimeError("missing sealed closure")
        ordinal = int(exact_key.rsplit(":", 1)[-1], 16)
        return SimpleNamespace(
            envelope=SimpleNamespace(
                content_key="exact-authority:sha256:" + f"{ordinal:064x}",
            ),
        )


class ExactTemplateAuthorityAdmissionTest(unittest.TestCase):
    def _module(self):
        from server import exact_template_authority_admission

        return exact_template_authority_admission

    def test_saved_remote_source_admission_requires_unique_group_and_full_typed_bundle_closure(self):
        module = self._module()
        source = canonical_remote_template_source(remote_source())
        bundle_store = FakeBundleStore()

        with patch.object(module, "bind_exact_template_authority", return_value=bound()), patch.object(
            module, "build_resolved_loadout_from_registry", return_value=ready_loadout()
        ):
            result = module.admit_saved_remote_template(
                source,
                exact_registry=registry(),
                catalog={"catalogRevision": "gear-catalog-v1"},
                authority_context={"dependencyVector": {"gearRuleRevision": RULE}},
                bundle_store=bundle_store,
                resolver_revision=RESOLVER,
                simc_runtime_revision=RUNTIME,
            )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(len(bundle_store.calls), len(EXACT_LOADOUT_CORE_SLOTS))
        self.assertEqual(
            result["document"].content_key,
            module.seal_exact_template_authority_binding(
                source,
                admission_proof(),
            ).content_key,
        )
        self.assertTrue(all(
            call[1] == {
                "gear_rule_revision": RULE,
                "resolver_revision": RESOLVER,
                "simc_runtime_revision": RUNTIME,
            }
            for call in bundle_store.calls
        ))

    def test_ambiguous_group_or_missing_bundle_stays_literal_blocked_without_fallback(self):
        module = self._module()
        source = canonical_remote_template_source(remote_source())
        ambiguous = registry()
        for reference in ambiguous["templateReferences"]:
            reference["templateContentHash"] = "sha256:" + "4" * 64
        ambiguous["templateReferences"].append({
            **registry()["templateReferences"][0],
            "templateContentHash": CONTENT_HASH,
        })

        with patch.object(module, "bind_exact_template_authority", return_value=bound()):
            result = module.admit_saved_remote_template(
                source,
                exact_registry=ambiguous,
                catalog={},
                authority_context={},
                bundle_store=FakeBundleStore(),
                resolver_revision=RESOLVER,
                simc_runtime_revision=RUNTIME,
            )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("EXACT_TEMPLATE_AUTHORITY_AMBIGUOUS", result["problemCodes"])
        self.assertNotIn("document", result)

        with patch.object(module, "bind_exact_template_authority", return_value=bound()), patch.object(
            module, "build_resolved_loadout_from_registry", return_value=ready_loadout()
        ):
            missing = module.admit_saved_remote_template(
                source,
                exact_registry=registry(),
                catalog={},
                authority_context={},
                bundle_store=FakeBundleStore(fail=True),
                resolver_revision=RESOLVER,
                simc_runtime_revision=RUNTIME,
            )
        self.assertEqual(missing["status"], "blocked")
        self.assertIn("EXACT_SOURCE_AUTHORITY_REQUIRED", missing["problemCodes"])


if __name__ == "__main__":
    unittest.main()

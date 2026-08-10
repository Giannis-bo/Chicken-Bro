import copy
import json
import unittest

from server.gear_contracts import EXACT_LOADOUT_CORE_SLOTS


OWNER_ID = "12345678-1234-5678-1234-567812345678"
TEMPLATE_ID = "87654321-4321-8765-4321-876543218765"
CONFIG_HASH = "a" * 64


def selection_intent():
    return {
        "schemaRevision": "selection-intent-v1",
        "authoredAgainst": {
            "seasonRevision": "season-17",
            "gearCatalogRevision": "gear-catalog-v1",
        },
        "eligibilityContext": {
            "classKey": "mage",
            "specKey": "frost",
            "level": 80,
        },
        "slots": {
            slot: {
                "itemId": str(1000 + index),
                "variantKey": f"browse-{slot}",
                "gemOptionIds": [],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            }
            for index, slot in enumerate(EXACT_LOADOUT_CORE_SLOTS, start=1)
        },
    }


def remote_source():
    return {
        "ownerId": OWNER_ID,
        "templateId": TEMPLATE_ID,
        "templateType": "gear",
        "remote": True,
        "configHash": CONFIG_HASH,
        "rawString": "server-saved-gear-template-v1",
        "metadata": {
            "selectionIntent": selection_intent(),
            "resolvedGearSignature": "client-metadata-is-not-authority",
        },
    }


def admission_proof():
    return {
        "gearExactRegistryRevision": "gear-exact-registry:sha256:" + "1" * 64,
        "gearRuleRevision": "gear-rule-v1",
        "resolverRevision": "resolver-v2",
        "simcRuntimeRevision": "simc-runtime-v1",
        "templateAuthorityIdentity": "sha256:" + "2" * 64,
        "templateContentHash": "sha256:" + "3" * 64,
        "exactAuthorityBySlot": [
            {
                "slot": slot,
                "exactAuthorityEnvelopeKey": "exact-authority:sha256:"
                + f"{index:064x}",
            }
            for index, slot in enumerate(EXACT_LOADOUT_CORE_SLOTS, start=1)
        ],
    }


class ExactTemplateAuthorityBindingTest(unittest.TestCase):
    def _module(self):
        from server import exact_template_authority_binding

        return exact_template_authority_binding

    def test_remote_source_is_canonical_and_excludes_client_metadata_and_raw_string(self):
        module = self._module()

        source = module.canonical_remote_template_source(remote_source())

        self.assertRegex(source.owner_key_hash, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(source.template_id, TEMPLATE_ID)
        self.assertEqual(source.template_config_hash, CONFIG_HASH)
        self.assertRegex(source.source_payload_hash, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(source.selection_signature, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(set(source.selection_intent["slots"]), set(EXACT_LOADOUT_CORE_SLOTS))
        self.assertNotIn("rawString", source.__dict__)
        self.assertNotIn("resolvedGearSignature", json.dumps(source.__dict__))

    def test_only_remote_full_saved_gear_source_is_admissible(self):
        module = self._module()

        for field, value in (
            ("remote", False),
            ("templateType", "talent"),
            ("ownerId", "not-a-uuid"),
        ):
            with self.subTest(field=field):
                invalid = remote_source()
                invalid[field] = value
                with self.assertRaises(module.ExactTemplateAuthorityBindingError):
                    module.canonical_remote_template_source(invalid)

        partial = remote_source()
        partial["metadata"]["selectionIntent"]["slots"].pop("hands")
        with self.assertRaises(module.ExactTemplateAuthorityBindingError):
            module.canonical_remote_template_source(partial)

    def test_binding_seals_only_server_source_and_complete_unique_slot_closure(self):
        module = self._module()
        source = module.canonical_remote_template_source(remote_source())

        document = module.seal_exact_template_authority_binding(
            source,
            admission_proof(),
        )
        payload = module.exact_template_authority_binding_payload(document)

        self.assertEqual(document.document_kind, "exact_template_authority_binding")
        self.assertEqual(document.schema_revision, "exact-template-authority-binding-v1")
        self.assertRegex(document.content_key, r"^exact-template-authority-binding:sha256:[0-9a-f]{64}$")
        self.assertEqual(set(payload), {"schemaRevision", "source", "authority", "exactAuthorityBySlot"})
        self.assertEqual(payload["source"]["templateId"], TEMPLATE_ID)
        self.assertEqual(payload["source"]["ownerKeyHash"], source.owner_key_hash)
        self.assertNotIn("rawString", json.dumps(payload))
        self.assertNotIn("resolvedGearSignature", json.dumps(payload))
        self.assertEqual(payload["exactAuthorityBySlot"], admission_proof()["exactAuthorityBySlot"])

        for mutator in (
            lambda proof: proof["exactAuthorityBySlot"].pop(),
            lambda proof: proof["exactAuthorityBySlot"].append(
                copy.deepcopy(proof["exactAuthorityBySlot"][0])
            ),
            lambda proof: proof["exactAuthorityBySlot"].reverse(),
            lambda proof: proof.__setitem__("templateContentHash", "sha256:" + "x" * 64),
        ):
            with self.subTest(mutator=mutator):
                invalid = admission_proof()
                mutator(invalid)
                with self.assertRaises(module.ExactTemplateAuthorityBindingError):
                    module.seal_exact_template_authority_binding(source, invalid)

    def test_reloaded_binding_requires_same_server_source_bytes_and_key(self):
        module = self._module()
        source = module.canonical_remote_template_source(remote_source())
        document = module.seal_exact_template_authority_binding(source, admission_proof())

        reloaded = module.reload_exact_template_authority_binding(
            document.content_key,
            document.canonical_bytes,
        )
        self.assertTrue(module.binding_matches_remote_template_source(reloaded, source))

        changed = remote_source()
        changed["rawString"] = "changed-server-saved-gear-template"
        changed_source = module.canonical_remote_template_source(changed)
        self.assertFalse(module.binding_matches_remote_template_source(reloaded, changed_source))

        with self.assertRaises(module.ExactTemplateAuthorityBindingError):
            module.reload_exact_template_authority_binding(
                document.content_key,
                document.canonical_bytes + b" ",
            )
        with self.assertRaises(module.ExactTemplateAuthorityBindingError):
            module.reload_exact_template_authority_binding(
                "exact-template-authority-binding:sha256:" + "0" * 64,
                document.canonical_bytes,
            )


if __name__ == "__main__":
    unittest.main()

import copy
import inspect
import hashlib
import json
from pathlib import Path
import unittest

from server import gear_contracts, gear_socket_authority


CANONICAL_MUTATIONS = json.loads(
    (Path(__file__).parent / "fixtures" / "gear_canonical_mutations.json").read_text(encoding="utf-8")
)


class GearContractsTest(unittest.TestCase):
    def valid_exact_intent(self):
        slots = {
            slot: {
                "itemId": str(225574 + index),
                "declaredItemLevel": None,
                "bonusIds": [], "context": "", "gemIds": [], "gemBonusIds": [],
                "gemItemLevels": [], "enchantId": "", "craftedStats": [],
                "embellishmentIds": [], "redirectedBaseStats": [],
            }
            for index, slot in enumerate(gear_contracts.EXACT_LOADOUT_CORE_SLOTS)
        }
        return {
            "schemaRevision": "exact-loadout-intent-v2",
            "authoredAgainst": {"seasonRevision": "season-r1", "gameBuild": "build-r1"},
            "eligibilityContext": {"classKey": "warrior", "specKey": "fury", "level": 80},
            "slots": slots,
        }

    # Catches accidentally reusing v1 Catalog fields in the independent exact
    # contract, or changing the previously frozen v1 parser behavior.
    def test_exact_v2_rejects_catalog_fields_while_v1_remains_byte_stable(self):
        exact = self.valid_exact_intent()
        parsed, issues = gear_contracts.parse_exact_loadout_intent(exact)
        self.assertEqual(issues, [])
        self.assertEqual(parsed, exact)

        catalog_in_authored = self.valid_exact_intent()
        catalog_in_authored["authoredAgainst"]["gearCatalogRevision"] = "catalog-r1"
        variant_in_slot = self.valid_exact_intent()
        variant_in_slot["slots"]["head"]["variantKey"] = "variant-head"
        for value, path in ((catalog_in_authored, "intent.authoredAgainst.gearCatalogRevision"), (variant_in_slot, "intent.slots.head.variantKey")):
            with self.subTest(path=path):
                parsed, issues = gear_contracts.parse_exact_loadout_intent(value)
                self.assertIsNone(parsed)
                self.assertTrue(any(issue["code"] == "UNKNOWN_FIELD" and issue["path"] == path for issue in issues))

        v1 = self.valid_intent()
        parsed_v1, v1_issues = gear_contracts.parse_selection_intent(v1)
        self.assertEqual(v1_issues, [])
        self.assertEqual(parsed_v1, v1)

    # Catches trim-then-accept and the narrower CR/LF-only predicate that let
    # C1, format controls, and Unicode line/paragraph separators cross Task 1.
    def test_exact_v2_rejects_the_shared_raw_control_mutation_corpus(self):
        def cases(value):
            fields = []
            for section, key in (
                ("authoredAgainst", "seasonRevision"),
                ("authoredAgainst", "gameBuild"),
                ("eligibilityContext", "classKey"),
                ("eligibilityContext", "specKey"),
            ):
                candidate = self.valid_exact_intent()
                candidate[section][key] = value
                fields.append((f"intent.{section}.{key}", candidate))
            for key in ("itemId", "context", "enchantId"):
                candidate = self.valid_exact_intent()
                candidate["slots"]["head"][key] = value
                fields.append((f"intent.slots.head.{key}", candidate))
            for key in (
                "bonusIds", "gemIds", "gemBonusIds", "craftedStats",
                "embellishmentIds", "redirectedBaseStats",
            ):
                candidate = self.valid_exact_intent()
                candidate["slots"]["head"][key] = [value]
                fields.append((f"intent.slots.head.{key}.0", candidate))
            return fields

        for mutation in CANONICAL_MUTATIONS["invalidIdentityStrings"]:
            for path, candidate in cases(mutation):
                with self.subTest(mutation=ascii(mutation), path=path):
                    parsed, issues = gear_contracts.parse_exact_loadout_intent(
                        copy.deepcopy(candidate)
                    )
                    self.assertIsNone(parsed)
                    self.assertTrue(any(issue["path"] == path for issue in issues))

    # Catches defaulting absent Exact fields into a new identity rather than
    # rejecting an input whose slot key set is structurally incomplete.
    def test_exact_v2_rejects_every_missing_slot_field_with_path(self):
        for field in (
            "itemId", "declaredItemLevel", "bonusIds", "context", "gemIds", "gemBonusIds",
            "gemItemLevels", "enchantId", "craftedStats", "embellishmentIds", "redirectedBaseStats",
        ):
            with self.subTest(field=field):
                exact = self.valid_exact_intent()
                exact["slots"]["head"].pop(field)

                parsed, issues = gear_contracts.parse_exact_loadout_intent(exact)

                self.assertIsNone(parsed)
                self.assertTrue(any(issue["path"] == f"intent.slots.head.{field}" for issue in issues))

    # Catches an Exact v2 change accidentally perturbing any sealed v1
    # canonical identity used by existing loadout and snapshot records.
    def test_v1_fixture_canonical_bytes_and_keys_remain_frozen(self):
        from server.gear_resolved_loadout import _canonical_bytes, build_resolved_loadout
        from server.simulation_snapshot import _canonical_bytes as snapshot_bytes, build_simulation_snapshot
        from tests.gear_resolved_loadout_test import TEMPLATE_HASH, exact_registry, resolver_snapshot
        from tests.simulation_snapshot_test import TALENT_KEY, TALENT_LINES, character_context, scenario

        v1, issues = gear_contracts.parse_selection_intent(self.valid_intent())
        self.assertEqual(issues, [])
        self.assertEqual(
            json.dumps(v1, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            b'{"authoredAgainst":{"gearCatalogRevision":"gear-r17","seasonRevision":"season-17-active"},"eligibilityContext":{"classKey":"mage","level":90,"specKey":"arcane"},"schemaRevision":"selection-intent-v1","slots":{"head":{"catalystOptionId":"","craftedOptionId":"","embellishmentOptionId":"","enchantOptionId":"","gemOptionIds":["gem-240898-r2"],"itemId":"250060","variantKey":"variant-head-289"}}}',
        )
        loadout = build_resolved_loadout(
            resolver_snapshot=resolver_snapshot(), exact_registry=exact_registry(),
            template_scope="community", template_content_hash=TEMPLATE_HASH,
        )
        self.assertEqual(loadout["resolvedLoadoutKey"], "resolved-loadout:sha256:e296abc0f2dfc1ce0f2c8c260e219ce633d7a52743a534bf2ededd5424a60893")
        self.assertEqual(hashlib.sha256(_canonical_bytes(loadout)).hexdigest(), "13e1b92e01271c7617f941c8ed4a40e20ec0f5b56cba3c91c98d8431df2d5f7d")
        snapshot = build_simulation_snapshot(
            resolved_loadout=loadout, talent_profile_key=TALENT_KEY, talent_lines=TALENT_LINES,
            character_context=character_context(), scenario_options=scenario(),
            preparation_lines=["optimal_raid=0", "override.arcane_intellect=1"],
            compiler_revision="simc-profile-compiler-v1", simc_runtime_revision="simc-runtime-v1",
        )
        self.assertEqual(snapshot["simulationSnapshotKey"], "simulation-snapshot:sha256:193951caa6917b98318d2d7c4e353df771a7b39538f3e375cf79775a1385b0d2")
        self.assertEqual(hashlib.sha256(snapshot_bytes(snapshot)).hexdigest(), "ffbd4df73ebff0cefbaeb7028d8dee01c16e36dbe5813b84e9e9cd71bbd288f9")
    def valid_intent(self):
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": "gear-r17",
            },
            "eligibilityContext": {
                "classKey": "mage",
                "specKey": "arcane",
                "level": 90,
            },
            "slots": {
                "head": {
                    "itemId": "250060",
                    "variantKey": "variant-head-289",
                    "gemOptionIds": ["gem-240898-r2"],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }

    def valid_vector(self):
        return {
            "seasonRevision": "season-17-active",
            "gearCatalogReleaseId": "gear-release-17",
            "gearCatalogRevision": "gear-r17",
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "serializer-v1",
            "simcRuntimeRevision": "simc-midnight-abc",
            "statPolicyRevision": "stat-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        }

    def valid_authority_context(self):
        return {
            "contractRevision": "gear-authority-context-v1",
            "manifest": {
                "seasonRevision": "season-17-active",
                "gearCatalogReleaseId": "gear-release-17",
                "gearCatalogRevision": "gear-r17",
            },
            "dependencyVector": self.valid_vector(),
            "itemsById": {},
            "variantsByKey": {},
            "optionsById": {},
            "ruleParameters": {},
            "capabilities": {},
            "evidenceRecordsById": {},
            "missingFields": [],
        }

    def test_selection_intent_parser_returns_exact_canonical_v1_shape(self):
        parsed, issues = gear_contracts.parse_selection_intent(self.valid_intent())

        self.assertEqual(issues, [])
        self.assertEqual(parsed, self.valid_intent())
        expected_fields = (
            "authoredAgainst",
            "eligibilityContext",
            "schemaRevision",
            "slots",
        )
        self.assertEqual(tuple(gear_contracts.SelectionIntent.__annotations__), expected_fields)
        self.assertEqual(gear_contracts.SelectionIntent.__required_keys__, frozenset(expected_fields))

    def test_selection_intent_parser_rejects_malformed_or_unknown_slots(self):
        intent = self.valid_intent()
        intent["slots"] = {"unknown_slot": {"itemId": "250060"}}

        parsed, issues = gear_contracts.parse_selection_intent(intent)

        self.assertIsNone(parsed)
        self.assertTrue(any(issue["kind"] == "INVALID_INTENT" for issue in issues))
        self.assertTrue(any(issue["code"] == "UNKNOWN_SLOT" for issue in issues))

        nested = self.valid_intent()
        nested["eligibilityContext"]["serverVerified"] = True
        parsed, issues = gear_contracts.parse_selection_intent(nested)
        self.assertIsNone(parsed)
        self.assertTrue(any(issue["path"] == "intent.eligibilityContext.serverVerified" for issue in issues))

    def test_selection_intent_parser_rejects_client_final_facts(self):
        intent = self.valid_intent()
        intent["slots"]["head"]["stats"] = {"intellect": 999999}
        intent["readiness"] = {"simcReady": True}

        parsed, issues = gear_contracts.parse_selection_intent(intent)

        self.assertIsNone(parsed)
        self.assertGreaterEqual(
            sum(issue["code"] == "FORBIDDEN_CLIENT_FACT" for issue in issues),
            2,
        )

    def test_dependency_vector_requires_every_approved_revision(self):
        vector = self.valid_vector()
        vector.pop("statPolicyRevision")

        issues = gear_contracts.validate_dependency_vector(vector)

        self.assertTrue(any(issue["kind"] == "AUTHORITY_UNAVAILABLE" for issue in issues))
        self.assertTrue(any(issue["path"] == "dependencyVector.statPolicyRevision" for issue in issues))

    def test_dependency_vector_requires_capability_revision(self):
        vector = self.valid_vector()
        vector.pop("capabilityRevision")

        issues = gear_contracts.validate_dependency_vector(vector)

        self.assertTrue(
            any(
                issue["path"] == "dependencyVector.capabilityRevision"
                for issue in issues
            )
        )

    def test_selection_signature_is_order_stable_and_eligibility_sensitive(self):
        intent = self.valid_intent()
        reordered = {
            "slots": intent["slots"],
            "eligibilityContext": intent["eligibilityContext"],
            "authoredAgainst": intent["authoredAgainst"],
            "schemaRevision": intent["schemaRevision"],
        }

        first = gear_contracts.selection_signature(intent, intent["eligibilityContext"])
        second = gear_contracts.selection_signature(reordered, intent["eligibilityContext"])
        changed = gear_contracts.selection_signature(
            intent,
            {**intent["eligibilityContext"], "specKey": "fire"},
        )

        self.assertRegex(first, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_resolved_signature_uses_resolution_dependencies_not_profile_dependencies(self):
        vector = self.valid_vector()
        signature = gear_contracts.resolved_gear_signature("sha256:selection", vector)
        profile_only_changed = {
            **vector,
            "serializerRevision": "serializer-v2",
            "simcRuntimeRevision": "simc-v2",
            "statPolicyRevision": "stat-v2",
        }
        rule_changed = {**vector, "gearRuleRevision": "gear-rule-matrix-v2"}

        self.assertEqual(
            signature,
            gear_contracts.resolved_gear_signature("sha256:selection", profile_only_changed),
        )
        self.assertNotEqual(
            signature,
            gear_contracts.resolved_gear_signature("sha256:selection", rule_changed),
        )

    def test_resolved_gear_signature_changes_with_capability_revision(self):
        vector = self.valid_vector()
        changed = {
            **vector,
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
        }

        self.assertNotEqual(
            gear_contracts.resolved_gear_signature("sha256:selection", vector),
            gear_contracts.resolved_gear_signature("sha256:selection", changed),
        )

    def test_profile_signature_changes_for_character_talent_serializer_runtime_or_stat_policy(self):
        args = {
            "resolved_signature": "sha256:resolved",
            "character_context": {"race": "troll", "level": 90},
            "talent_hash": "talent-a",
            "serializer_revision": "serializer-v1",
            "simc_runtime_revision": "simc-v1",
            "stat_policy_revision": "stat-v1",
        }
        baseline = gear_contracts.profile_signature(**args)

        mutations = (
            {"character_context": {"race": "human", "level": 90}},
            {"talent_hash": "talent-b"},
            {"serializer_revision": "serializer-v2"},
            {"simc_runtime_revision": "simc-v2"},
            {"stat_policy_revision": "stat-v2"},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(
                    baseline,
                    gear_contracts.profile_signature(**{**args, **mutation}),
                )

    def test_authority_context_missing_required_maps_is_unavailable(self):
        context = self.valid_authority_context()
        context.pop("optionsById")
        context["manifest"].pop("gearCatalogReleaseId")
        context["missingFields"] = ["itemsById.head.variant"]

        issues = gear_contracts.validate_authority_context(self.valid_intent(), context)

        self.assertTrue(any(issue["kind"] == "AUTHORITY_UNAVAILABLE" for issue in issues))
        self.assertTrue(any(issue["path"] == "authorityContext.optionsById" for issue in issues))
        self.assertTrue(any(issue["path"] == "authorityContext.manifest.gearCatalogReleaseId" for issue in issues))
        self.assertTrue(any(issue["path"] == "itemsById.head.variant" for issue in issues))

    def test_authority_context_revision_conflict_is_not_silently_reinterpreted(self):
        context = self.valid_authority_context()
        context["manifest"]["gearCatalogRevision"] = "gear-r18"

        issues = gear_contracts.validate_authority_context(self.valid_intent(), context)

        self.assertTrue(any(issue["kind"] == "REVISION_CONFLICT" for issue in issues))
        self.assertTrue(any(issue["code"] == "GEAR_CATALOG_REVISION_CONFLICT" for issue in issues))

    def test_authority_context_contract_has_no_connection_or_database_access(self):
        source = inspect.getsource(gear_contracts)
        self.assertNotIn("import sqlite3", source)
        self.assertNotIn("psycopg", source)
        self.assertNotIn("postgres_cache_store", source)
        for name in gear_contracts.__all__:
            value = getattr(gear_contracts, name)
            if not callable(value):
                continue
            self.assertNotIn("conn", inspect.signature(value).parameters)


if __name__ == "__main__":
    unittest.main()

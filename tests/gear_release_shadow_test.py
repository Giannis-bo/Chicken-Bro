import copy
import unittest
from unittest.mock import patch

from server import gear_contracts, gear_evidence_ledger, gear_release, gear_release_shadow
from server import gear_resolver, gear_socket_authority
from tests.gear_release_tool_test import build_midnight_mage_release_fixture


class FakeShadowStore:
    def __init__(
        self,
        candidate_row,
        *,
        baseline_count=0,
        capability_revision=gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        candidate_authority_context=None,
        transitional_authority_context=None,
        exact_authority_expectations=None,
    ):
        self.candidate_row = copy.deepcopy(candidate_row)
        self.baseline_count = baseline_count
        self.capability_revision = capability_revision
        self.candidate_authority_context = copy.deepcopy(
            candidate_authority_context or {}
        )
        self.transitional_authority_context = copy.deepcopy(
            transitional_authority_context or {}
        )
        self.exact_authority_expectations = copy.deepcopy(
            exact_authority_expectations or []
        )
        self.calls = []

    def get_candidate_community_release(self, gear_release_id, community_release_id):
        self.calls.append(("community", gear_release_id, community_release_id))
        return {
            "gearRelease": {
                "releaseId": gear_release_id,
                "dependencyRevisions": {
                    "capabilityRevision": self.capability_revision,
                },
            },
            "communityRelease": {
                "releaseId": community_release_id,
                "validatedAgainstReleaseId": gear_release_id,
            },
            "rows": [copy.deepcopy(self.candidate_row)],
            "winners": [copy.deepcopy(self.candidate_row)],
        }

    def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
        self.calls.append(("public", class_key, spec_key, compact, mode, slot))
        return {
            "classKey": class_key,
            "specKey": spec_key,
            "communityTemplates": [{
                "id": self.candidate_row["templateId"],
                "classKey": class_key,
                "specKey": spec_key,
                "sourceKey": self.candidate_row["sourceKey"],
                "sourceUrl": self.candidate_row["sourceUrl"],
                "sourceStatus": "synced",
                "signature": self.candidate_row["gearHash"],
                "gearItems": [{
                    "slot": slot,
                    "itemId": selection.get("itemId"),
                    "variantKey": selection.get("variantKey"),
                } for slot, selection in self.candidate_row["selectionIntent"]["slots"].items()],
                "sourceRefs": [{"sampleCount": self.candidate_row["sampleCount"]}],
                "payload": {"templateEvidence": {
                    "profileHash": self.candidate_row["profileHash"],
                    "gearHash": self.candidate_row["gearHash"],
                    "sampleCount": self.candidate_row["sampleCount"],
                }},
            }],
            "baselineTemplates": [{} for _ in range(self.baseline_count)],
        }

    def get_gear_resolver_context(self, runtime_authority):
        self.calls.append(("resolver-context", copy.deepcopy(runtime_authority)))
        return {
            "formalActiveManifest": False,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "compatibility-pg:old",
            },
        }

    def get_candidate_gear_authority_context(
        self,
        selection_intent,
        _runtime_authority,
        gear_release_id,
    ):
        if self.exact_authority_expectations:
            expected_intent, expected_release_id = (
                self.exact_authority_expectations.pop(0)
            )
            if selection_intent != expected_intent:
                raise AssertionError("exact authority intent was rewritten")
            if gear_release_id != expected_release_id:
                raise AssertionError(
                    "exact authority release id did not match captured id"
                )
        self.calls.append((
            "exact-authority",
            copy.deepcopy(selection_intent),
            gear_release_id,
        ))
        transitional_release_id = str(
            (self.transitional_authority_context.get("dependencyVector") or {}).get(
                "gearCatalogReleaseId"
            )
            or ""
        ).strip()
        if transitional_release_id and gear_release_id == transitional_release_id:
            return copy.deepcopy(self.transitional_authority_context)
        return copy.deepcopy(self.candidate_authority_context)

    def get_active_community_release(self):
        self.calls.append(("active-pair",))
        dependencies = self.transitional_authority_context.get(
            "dependencyVector"
        )
        dependencies = dependencies if isinstance(dependencies, dict) else {}
        release_id = str(dependencies.get("gearCatalogReleaseId") or "").strip()
        if not release_id:
            return {"formalActiveManifest": False, "winners": []}
        return {
            "formalActiveManifest": True,
            "pointerGeneration": 1,
            "manifestRevision": "manifest:active-test",
            "gearRelease": {"releaseId": release_id},
            "communityRelease": {"releaseId": "community-release:active-test"},
            "winners": [copy.deepcopy(self.candidate_row)],
        }


class GearReleaseShadowTest(unittest.TestCase):
    def resolved_profile_envelope(self, profile_text):
        return {
            "status": "resolved",
            "data": {
                "profile": profile_text,
                "talentEncoding": {
                    "status": "encoded",
                    "source": "talent_catalog",
                    "errors": [],
                    "warnings": [],
                    "lines": ["class_talents=canonical"],
                    "selectedCounts": {"class": 1, "spec": 1, "hero": 1},
                },
                "profileReadiness": {
                    "status": "verified",
                    "simcReady": True,
                },
            },
            "problems": [],
        }

    def verified_rule_results(self):
        return [
            {
                "ruleId": rule.rule_id,
                "ruleRevision": rule.rule_revision,
                "status": "verified",
                "problems": [],
                "order": rule.order,
            }
            for rule in gear_resolver.ordered_rule_matrix()
        ]

    def candidate_authority(self, dependencies, *, options, evidence_records):
        return {
            "contractRevision": gear_contracts.AUTHORITY_CONTEXT_CONTRACT_REVISION,
            "manifest": {
                "seasonRevision": dependencies["seasonRevision"],
                "gearCatalogReleaseId": dependencies["gearCatalogReleaseId"],
                "gearCatalogRevision": dependencies["gearCatalogRevision"],
            },
            "dependencyVector": copy.deepcopy(dependencies),
            "itemsById": {
                "item-a": {
                    "itemId": "item-a",
                    "sourceRefIds": ["evidence:item"],
                },
            },
            "variantsByKey": {
                "variant-a": {
                    "variantKey": "variant-a",
                    "itemId": "item-a",
                    "status": "verified",
                    "simcOptions": {},
                    "sourceRefIds": ["evidence:item"],
                },
            },
            "optionsById": copy.deepcopy(options),
            "ruleParameters": {
                "requiredSlots": ["head"],
                "weaponModesByClassSpec": {},
            },
            "capabilities": {},
            "evidenceRecordsById": copy.deepcopy(evidence_records),
            "missingFields": [],
        }

    def intent(self):
        return {
            "schemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
            "eligibilityContext": {"classKey": "mage", "specKey": "arcane", "level": 90},
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
            },
        }

    def snapshot(self, intent, resolved_signature):
        return {
            "status": "verified",
            "eligibilityContext": intent["eligibilityContext"],
            "resolvedGearSignature": resolved_signature,
            "resolvedSlots": {"head": {"itemId": "item-a", "variantKey": "variant-a"}},
            "staticAttributes": {"intellect": 100},
            "setState": {"itemSetCounts": {}, "activeDynamicEffects": []},
            "constraints": {"slots": {}},
            "serializerInput": {"gearItems": [{
                "slot": "head",
                "itemId": "item-a",
                "variantKey": "variant-a",
                "simcOptions": {},
            }]},
            "aggregateLegality": {"status": "verified", "problemCodes": []},
            "profileReadiness": {
                "status": "verified",
                "simcReady": True,
                "requiredSlots": ["head"],
                "readySlots": ["head"],
                "serializerRevision": "serializer-v1",
                "simcRuntimeRevision": "simc-r1",
                "problems": [],
            },
            "problems": [],
        }

    def seal_identity_claim(self, snapshot, slot="head"):
        existing_ledger = (
            snapshot.get("evidenceLedger")
            if isinstance(snapshot.get("evidenceLedger"), dict)
            else {}
        )
        evidence_records = copy.deepcopy(
            existing_ledger.get("evidenceRecordsById") or {}
        )
        authority = {
            "dependencyVector": copy.deepcopy(snapshot["dependencyVector"]),
            "evidenceRecordsById": evidence_records,
            "ruleParameters": {"sourceRefIds": []},
        }
        claims = gear_resolver._claims(
            snapshot["resolvedSlots"],
            snapshot["ruleResults"],
            snapshot["staticAttributes"],
            snapshot["setState"],
            snapshot["profileReadiness"],
            authority,
            snapshot["resolvedGearSignature"],
        )
        ledger = gear_evidence_ledger.build_evidence_ledger(
            claims,
            evidence_records,
        )
        snapshot["evidenceLedger"] = ledger
        for slot_key, resolved in snapshot["resolvedSlots"].items():
            prefix = f"slot:{slot_key}:"
            resolved["evidenceClaimIds"] = sorted(
                claim["claimId"]
                for claim in ledger["claims"]
                if claim["claimKey"].startswith(prefix)
            )

    def reseal_existing_claims(self, snapshot):
        ledger = snapshot["evidenceLedger"]
        old_to_new = {}
        rebuilt_claims = []
        pending = list(ledger["claims"])
        while pending:
            progress = False
            for claim in list(pending):
                dependencies = claim.get("dependsOn") or []
                if any(claim_id not in old_to_new for claim_id in dependencies):
                    continue
                rebuilt = gear_evidence_ledger.evidence_claim(
                    claim["group"],
                    claim["claimKey"],
                    copy.deepcopy(claim["value"]),
                    status=claim["status"],
                    source_ref_ids=claim.get("sourceRefIds") or [],
                    rule_revision=claim["ruleRevision"],
                    resolved_signature=snapshot["resolvedGearSignature"],
                    dependency_vector=snapshot["dependencyVector"],
                    depends_on=[old_to_new[claim_id] for claim_id in dependencies],
                    problems=claim.get("problems") or [],
                )
                old_to_new[claim["claimId"]] = rebuilt["claimId"]
                rebuilt_claims.append(rebuilt)
                pending.remove(claim)
                progress = True
            if not progress:
                raise AssertionError("fixture claim graph must be acyclic")
        snapshot["evidenceLedger"] = gear_evidence_ledger.build_evidence_ledger(
            rebuilt_claims,
            ledger["evidenceRecordsById"],
        )
        for slot_key, resolved in snapshot["resolvedSlots"].items():
            prefix = f"slot:{slot_key}:"
            resolved["evidenceClaimIds"] = sorted(
                claim["claimId"]
                for claim in snapshot["evidenceLedger"]["claims"]
                if claim["claimKey"].startswith(prefix)
            )

    def candidate_row(self):
        intent = self.intent()
        snapshot = self.snapshot(intent, "sha256:candidate")
        return {
            "templateId": "template-a",
            "classKey": "mage",
            "specKey": "arcane",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/a",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:a",
            "gearHash": "gear:a",
            "selectionIntent": intent,
            "resolvedGearSignature": "sha256:candidate",
            "semanticGearSignature": gear_release.semantic_gear_signature(intent, snapshot),
            "problems": [],
        }

    def formal_active_pair(
        self,
        candidate,
        *,
        pointer_generation=7,
        gear_release_id="gear-release:active",
        community_release_id="community-release:active",
        manifest_revision="manifest:active",
        formal=True,
    ):
        return {
            "formalActiveManifest": formal,
            "pointerGeneration": pointer_generation,
            "manifestRevision": manifest_revision,
            "gearRelease": {"releaseId": gear_release_id},
            "communityRelease": {"releaseId": community_release_id},
            "winners": [copy.deepcopy(candidate)],
        }

    def run_formal_active_pointer_shadow(
        self,
        active_reads,
        *,
        expect_formal_active=True,
        resolver_formal_active=True,
    ):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        active_reader = unittest.mock.Mock(side_effect=active_reads)
        store.get_active_community_release = active_reader
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": resolver_formal_active,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:active",
            },
            "dependencyRevisions": {
                "capabilityRevision": (
                    gear_socket_authority.LEGACY_CAPABILITY_REVISION
                ),
            },
        }
        snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": snapshot,
                "problems": [],
            }),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
                expect_formal_active=expect_formal_active,
            )
        return result, store, active_reader

    def real_non_editor_option_evidence_migration_fixture(
        self,
        option_type,
        *,
        transitional_source_revision="2026-07-13T00:00:00+00:00",
    ):
        option_field = {
            "crafted": "craftedOptionId",
            "catalyst": "catalystOptionId",
        }[option_type]
        allowed_field = {
            "crafted": "allowedCraftedOptionIds",
            "catalyst": "allowedCatalystOptionIds",
        }[option_type]
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        candidate_intent = copy.deepcopy(fixture["intent"])
        candidate_authority = copy.deepcopy(fixture["authorityContext"])
        candidate_intent["eligibilityContext"]["specKey"] = "arcane"
        for item in candidate_authority["itemsById"].values():
            item["allowedSpecKeys"] = ["arcane"]
        rule_parameters = candidate_authority["ruleParameters"]
        rule_parameters["allowedWeaponTypesByClassSpec"]["mage:arcane"] = [
            "Staff"
        ]
        rule_parameters["dualWieldByClassSpec"]["mage:arcane"] = False
        rule_parameters["weaponModesByClassSpec"]["mage:arcane"] = (
            "caster_1h_or_staff"
        )

        slot = "head"
        option_id = f"{option_type}-stable"
        evidence_id = f"evidence:pg:option:{option_id}"
        candidate_intent["slots"][slot][option_field] = option_id
        selected_item = candidate_authority["itemsById"][
            candidate_intent["slots"][slot]["itemId"]
        ]
        selected_item[allowed_field] = [option_id]
        selected_item["baseCapabilities"][allowed_field] = [option_id]
        option = {
            "optionId": option_id,
            "optionType": option_type,
            "applicableSlots": [slot],
            "statDeltas": {"mastery": 20},
            "simcOptions": {},
            "sourceRefIds": [evidence_id],
            "uniqueGroupId": "",
            "uniqueLimit": 0,
        }
        if option_type == "catalyst":
            option["capabilityRevision"] = rule_parameters["catalystRevision"]
            candidate_authority["capabilities"]["catalyst"]["enabled"] = True
        candidate_authority["optionsById"][option_id] = option
        candidate_authority["evidenceRecordsById"][evidence_id] = {
            "id": evidence_id,
            "optionId": option_id,
            "sourceType": "postgres_gear_option",
            "sourceRevision": "2026-07-14T00:00:00+00:00",
        }
        candidate_snapshot = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )

        transitional_intent = copy.deepcopy(candidate_intent)
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = (
            "compatibility-pg:old"
        )
        for selection in transitional_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        transitional_authority["evidenceRecordsById"][evidence_id][
            "sourceRevision"
        ] = transitional_source_revision
        for item in transitional_authority["itemsById"].values():
            capabilities = item.get("baseCapabilities") or {}
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
            ):
                item[field] = []
                capabilities[field] = []
        transitional_snapshot = gear_resolver.resolve(
            transitional_intent,
            transitional_authority,
        )
        return {
            "slot": slot,
            "optionField": option_field,
            "optionId": option_id,
            "evidenceId": evidence_id,
            "transitionalIntent": transitional_intent,
            "transitionalSnapshot": transitional_snapshot,
            "candidateIntent": candidate_intent,
            "candidateSnapshot": candidate_snapshot,
            "candidateAuthority": candidate_authority,
            "transitionalAuthority": transitional_authority,
        }

    def selected_editor_option_binding(self, fixture):
        intent = fixture["candidateIntent"]
        for slot, selection in intent["slots"].items():
            option_ids = list(selection.get("gemOptionIds") or [])
            option_ids.extend([
                selection.get("enchantOptionId"),
                selection.get("embellishmentOptionId"),
            ])
            option_id = next(
                (str(value).strip() for value in option_ids if str(value or "").strip()),
                "",
            )
            if option_id:
                return {
                    "slot": slot,
                    "optionId": option_id,
                    "evidenceId": f"evidence:pg:option:{option_id}",
                    "itemId": selection["itemId"],
                    "variantKey": selection["variantKey"],
                }
        raise AssertionError("fixture must select at least one editor-managed option")

    def real_simc_contribution_collision_fixture(
        self,
        *,
        non_editor_types=(),
        variant_classification="source_only",
        simc_field="enchant_id",
        transitional_variant_value="8039/8052",
        candidate_variant_value="7777",
        transitional_non_editor_value="999002",
        candidate_non_editor_value="999001",
        select_editor=False,
        transitional_select_editor=False,
    ):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        candidate_intent = copy.deepcopy(fixture["intent"])
        candidate_authority = copy.deepcopy(fixture["authorityContext"])
        candidate_intent["eligibilityContext"]["specKey"] = "arcane"
        for item in candidate_authority["itemsById"].values():
            item["allowedSpecKeys"] = ["arcane"]
            base_capabilities = item.get("baseCapabilities") or {}
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
            ):
                item[field] = []
                base_capabilities[field] = []
        rule_parameters = candidate_authority["ruleParameters"]
        rule_parameters["allowedWeaponTypesByClassSpec"]["mage:arcane"] = [
            "Staff"
        ]
        rule_parameters["dualWieldByClassSpec"]["mage:arcane"] = False
        rule_parameters["weaponModesByClassSpec"]["mage:arcane"] = (
            "caster_1h_or_staff"
        )
        for selection in candidate_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
            selection["craftedOptionId"] = ""
            selection["catalystOptionId"] = ""

        slot = "main_hand"
        selection = candidate_intent["slots"][slot]
        item = candidate_authority["itemsById"][selection["itemId"]]
        variant = candidate_authority["variantsByKey"][
            selection["variantKey"]
        ]
        if variant_classification is None:
            variant.pop("enhancementManagement", None)
            for governed_field in (
                "gem_id",
                "gem_bonus_id",
                "gem_ilevel",
                "enchant_id",
                "embellishment",
            ):
                variant["simcOptions"].pop(governed_field, None)
            variant["simcOptions"][simc_field] = candidate_variant_value
        else:
            variant["simcOptions"][simc_field] = candidate_variant_value
            variant["enhancementManagement"] = {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                "fields": {simc_field: variant_classification},
            }

        def add_option(option_type, simc_value):
            option_id = f"{option_type}-simc-collision"
            evidence_id = f"evidence:pg:option:{option_id}"
            selection_field = {
                "enchant": "enchantOptionId",
                "crafted": "craftedOptionId",
                "catalyst": "catalystOptionId",
            }[option_type]
            allowed_field = {
                "enchant": "allowedEnchantOptionIds",
                "crafted": "allowedCraftedOptionIds",
                "catalyst": "allowedCatalystOptionIds",
            }[option_type]
            selection[selection_field] = option_id
            item[allowed_field] = [option_id]
            item["baseCapabilities"][allowed_field] = [option_id]
            option = {
                "optionId": option_id,
                "optionType": option_type,
                "applicableSlots": [slot],
                "statDeltas": (
                    {} if option_type == "enchant" else {"mastery": 20}
                ),
                "simcOptions": {simc_field: simc_value},
                "sourceRefIds": [evidence_id],
                "uniqueGroupId": "",
                "uniqueLimit": 0,
            }
            if option_type == "catalyst":
                option["capabilityRevision"] = rule_parameters[
                    "catalystRevision"
                ]
                candidate_authority["capabilities"]["catalyst"][
                    "enabled"
                ] = True
            candidate_authority["optionsById"][option_id] = option
            candidate_authority["evidenceRecordsById"][evidence_id] = {
                "id": evidence_id,
                "optionId": option_id,
                "sourceType": "postgres_gear_option",
                "sourceRevision": "2026-07-14T00:00:00+00:00",
            }

        if select_editor:
            add_option("enchant", transitional_variant_value)
        for option_type in non_editor_types:
            add_option(option_type, candidate_non_editor_value)

        transitional_intent = copy.deepcopy(candidate_intent)
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = (
            "compatibility-pg:old"
        )
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        transitional_variant = transitional_authority["variantsByKey"][
            selection["variantKey"]
        ]
        if variant_classification is None:
            transitional_variant["simcOptions"][simc_field] = (
                transitional_variant_value
            )
        else:
            transitional_variant["simcOptions"][simc_field] = (
                transitional_variant_value
            )
        for option_type in non_editor_types:
            transitional_authority["optionsById"][
                f"{option_type}-simc-collision"
            ]["simcOptions"][simc_field] = transitional_non_editor_value
        if select_editor and not transitional_select_editor:
            option_id = "enchant-simc-collision"
            evidence_id = f"evidence:pg:option:{option_id}"
            transitional_intent["slots"][slot]["enchantOptionId"] = ""
            transitional_authority["optionsById"].pop(option_id)
            transitional_authority["evidenceRecordsById"].pop(evidence_id)
            transitional_item = transitional_authority["itemsById"][
                selection["itemId"]
            ]
            transitional_item["allowedEnchantOptionIds"] = []
            transitional_item["baseCapabilities"][
                "allowedEnchantOptionIds"
            ] = []

        transitional_snapshot = gear_resolver.resolve(
            transitional_intent,
            transitional_authority,
        )
        candidate_snapshot = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )
        return {
            "slot": slot,
            "transitionalIntent": transitional_intent,
            "transitionalSnapshot": transitional_snapshot,
            "candidateIntent": candidate_intent,
            "candidateSnapshot": candidate_snapshot,
            "candidateAuthority": candidate_authority,
            "transitionalAuthority": transitional_authority,
        }

    def real_editor_writer_fixture(
        self,
        *,
        editor_type=None,
        editor_simc_options=None,
        duplicate_gem=False,
        transitional_selects_editor=False,
        candidate_variant_governed=None,
        transitional_variant_governed=None,
        candidate_management=None,
        non_editor_type=None,
        candidate_non_editor_simc=None,
        transitional_non_editor_simc=None,
    ):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        candidate_intent = copy.deepcopy(fixture["intent"])
        candidate_authority = copy.deepcopy(fixture["authorityContext"])
        candidate_intent["eligibilityContext"]["specKey"] = "arcane"
        for item in candidate_authority["itemsById"].values():
            item["allowedSpecKeys"] = ["arcane"]
            base_capabilities = item.get("baseCapabilities") or {}
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
                "allowedCraftedOptionIds",
                "allowedCatalystOptionIds",
            ):
                item[field] = []
                base_capabilities[field] = []
        rule_parameters = candidate_authority["ruleParameters"]
        rule_parameters["allowedWeaponTypesByClassSpec"]["mage:arcane"] = [
            "Staff"
        ]
        rule_parameters["dualWieldByClassSpec"]["mage:arcane"] = False
        rule_parameters["weaponModesByClassSpec"]["mage:arcane"] = (
            "caster_1h_or_staff"
        )
        governed_fields = (
            "gem_id",
            "gem_bonus_id",
            "gem_ilevel",
            "enchant_id",
            "embellishment",
        )
        for selection in candidate_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
            selection["craftedOptionId"] = ""
            selection["catalystOptionId"] = ""
        for candidate_variant in candidate_authority["variantsByKey"].values():
            for field in governed_fields:
                candidate_variant["simcOptions"].pop(field, None)
            candidate_variant.pop("enhancementManagement", None)

        slot = "head"
        selection = candidate_intent["slots"][slot]
        item = candidate_authority["itemsById"][selection["itemId"]]
        variant = candidate_authority["variantsByKey"][selection["variantKey"]]
        for field in governed_fields:
            variant["simcOptions"].pop(field, None)
        variant["simcOptions"].update(candidate_variant_governed or {})
        if candidate_management:
            variant["enhancementManagement"] = {
                "schemaRevision": "gear-enhancement-management-v1",
                "authorityRevision": gear_socket_authority.CAPABILITY_REVISION,
                "fields": copy.deepcopy(candidate_management),
            }
        else:
            variant.pop("enhancementManagement", None)

        editor_option_ids = []
        raw_editor_options = editor_simc_options
        if editor_type == "gem":
            option_payloads = (
                list(raw_editor_options)
                if isinstance(raw_editor_options, list)
                else [raw_editor_options or {}]
            )
        elif editor_type:
            option_payloads = [raw_editor_options or {}]
        else:
            option_payloads = []
        for index, simc_options in enumerate(option_payloads):
            option_id = f"{editor_type}-writer-{index}"
            evidence_id = f"evidence:pg:option:{option_id}"
            editor_option_ids.append(option_id)
            candidate_authority["optionsById"][option_id] = {
                "optionId": option_id,
                "optionType": editor_type,
                "applicableSlots": [slot],
                "statDeltas": {},
                "simcOptions": copy.deepcopy(simc_options),
                "sourceRefIds": [evidence_id],
                "uniqueGroupId": "",
                "uniqueLimit": 0,
            }
            candidate_authority["evidenceRecordsById"][evidence_id] = {
                "id": evidence_id,
                "optionId": option_id,
                "sourceType": "postgres_gear_option",
                "sourceRevision": "2026-07-14T00:00:00+00:00",
            }
        if editor_type == "gem":
            selected_gems = (
                [editor_option_ids[0], editor_option_ids[0]]
                if duplicate_gem
                else list(editor_option_ids)
            )
            selection["gemOptionIds"] = selected_gems
            item["allowedGemOptionIds"] = sorted(set(editor_option_ids))
            item["baseCapabilities"]["allowedGemOptionIds"] = sorted(
                set(editor_option_ids)
            )
            socket_count = len(selected_gems)
            item["socketCount"] = socket_count
            item["baseCapabilities"]["socketCount"] = socket_count
            variant.setdefault("capabilityOverrides", {})["socketCount"] = (
                socket_count
            )
        elif editor_type:
            selection_field = {
                "enchant": "enchantOptionId",
                "embellishment": "embellishmentOptionId",
            }[editor_type]
            allowed_field = {
                "enchant": "allowedEnchantOptionIds",
                "embellishment": "allowedEmbellishmentOptionIds",
            }[editor_type]
            selection[selection_field] = editor_option_ids[0]
            item[allowed_field] = list(editor_option_ids)
            item["baseCapabilities"][allowed_field] = list(editor_option_ids)
            if editor_type == "enchant":
                item["baseCapabilities"]["canEnchant"] = True
            else:
                item["baseCapabilities"]["canEmbellish"] = True

        if non_editor_type:
            option_id = f"{non_editor_type}-writer"
            evidence_id = f"evidence:pg:option:{option_id}"
            selection_field = {
                "crafted": "craftedOptionId",
                "catalyst": "catalystOptionId",
            }[non_editor_type]
            allowed_field = {
                "crafted": "allowedCraftedOptionIds",
                "catalyst": "allowedCatalystOptionIds",
            }[non_editor_type]
            selection[selection_field] = option_id
            item[allowed_field] = [option_id]
            item["baseCapabilities"][allowed_field] = [option_id]
            option = {
                "optionId": option_id,
                "optionType": non_editor_type,
                "applicableSlots": [slot],
                "statDeltas": {"mastery": 20},
                "simcOptions": copy.deepcopy(candidate_non_editor_simc or {}),
                "sourceRefIds": [evidence_id],
                "uniqueGroupId": "",
                "uniqueLimit": 0,
            }
            if non_editor_type == "catalyst":
                option["capabilityRevision"] = rule_parameters[
                    "catalystRevision"
                ]
                candidate_authority["capabilities"]["catalyst"][
                    "enabled"
                ] = True
            candidate_authority["optionsById"][option_id] = option
            candidate_authority["evidenceRecordsById"][evidence_id] = {
                "id": evidence_id,
                "optionId": option_id,
                "sourceType": "postgres_gear_option",
                "sourceRevision": "2026-07-14T00:00:00+00:00",
            }

        transitional_intent = copy.deepcopy(candidate_intent)
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = (
            "compatibility-pg:old"
        )
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        transitional_variant = transitional_authority["variantsByKey"][
            selection["variantKey"]
        ]
        for field in governed_fields:
            transitional_variant["simcOptions"].pop(field, None)
        transitional_variant["simcOptions"].update(
            transitional_variant_governed or {}
        )
        if editor_type and not transitional_selects_editor:
            transitional_selection = transitional_intent["slots"][slot]
            if editor_type == "gem":
                transitional_selection["gemOptionIds"] = []
                allowed_field = "allowedGemOptionIds"
            elif editor_type == "enchant":
                transitional_selection["enchantOptionId"] = ""
                allowed_field = "allowedEnchantOptionIds"
            else:
                transitional_selection["embellishmentOptionId"] = ""
                allowed_field = "allowedEmbellishmentOptionIds"
            transitional_item = transitional_authority["itemsById"][
                selection["itemId"]
            ]
            transitional_item[allowed_field] = []
            transitional_item["baseCapabilities"][allowed_field] = []
            for option_id in editor_option_ids:
                transitional_authority["optionsById"].pop(option_id)
                transitional_authority["evidenceRecordsById"].pop(
                    f"evidence:pg:option:{option_id}"
                )
        if non_editor_type:
            transitional_authority["optionsById"][
                f"{non_editor_type}-writer"
            ]["simcOptions"] = copy.deepcopy(
                transitional_non_editor_simc or {}
            )

        transitional_snapshot = gear_resolver.resolve(
            transitional_intent,
            transitional_authority,
        )
        candidate_snapshot = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )
        return {
            "slot": slot,
            "transitionalIntent": transitional_intent,
            "transitionalSnapshot": transitional_snapshot,
            "transitionalAuthority": transitional_authority,
            "candidateIntent": candidate_intent,
            "candidateSnapshot": candidate_snapshot,
            "candidateAuthority": candidate_authority,
        }

    def assert_real_editor_migration_rejected(self, fixture):
        self.assertEqual(fixture["transitionalSnapshot"]["status"], "verified")
        self.assertEqual(fixture["candidateSnapshot"]["status"], "verified")
        self.assertEqual(
            gear_resolver.resolve(
                fixture["candidateIntent"],
                fixture["candidateAuthority"],
            ),
            fixture["candidateSnapshot"],
        )
        self.assertFalse(
            gear_release_shadow._legacy_to_v2_enhancement_migration_equivalent(
                fixture["transitionalSnapshot"],
                fixture["candidateSnapshot"],
                transitional_gear_release_id="compatibility-pg:old",
                transitional_gear_catalog_revision="compatibility-pg:old",
                candidate_gear_release_id="gear-release-17",
                transitional_authority_context=fixture[
                    "transitionalAuthority"
                ],
                candidate_authority_context=fixture["candidateAuthority"],
                transitional_intent=fixture["transitionalIntent"],
                candidate_intent=fixture["candidateIntent"],
                migration_mode="editor_only",
            )
        )

    def assert_real_writer_migration_rejected(self, fixture):
        self.assertEqual(fixture["transitionalSnapshot"]["status"], "verified")
        self.assertEqual(fixture["candidateSnapshot"]["status"], "verified")
        self.assertEqual(
            gear_resolver.resolve(
                fixture["transitionalIntent"],
                fixture["transitionalAuthority"],
            ),
            fixture["transitionalSnapshot"],
        )
        self.assertEqual(
            gear_resolver.resolve(
                fixture["candidateIntent"],
                fixture["candidateAuthority"],
            ),
            fixture["candidateSnapshot"],
        )
        self.assertFalse(
            gear_release_shadow._legacy_to_v2_enhancement_migration_equivalent(
                fixture["transitionalSnapshot"],
                fixture["candidateSnapshot"],
                transitional_gear_release_id="compatibility-pg:old",
                transitional_gear_catalog_revision="compatibility-pg:old",
                candidate_gear_release_id="gear-release-17",
                transitional_authority_context=fixture[
                    "transitionalAuthority"
                ],
                candidate_authority_context=fixture["candidateAuthority"],
                transitional_intent=fixture["transitionalIntent"],
                candidate_intent=fixture["candidateIntent"],
                migration_mode="editor_only",
            )
        )

    def assert_real_writer_migration_accepted(self, fixture):
        self.assertEqual(fixture["transitionalSnapshot"]["status"], "verified")
        self.assertEqual(fixture["candidateSnapshot"]["status"], "verified")
        self.assertEqual(
            gear_resolver.resolve(
                fixture["transitionalIntent"],
                fixture["transitionalAuthority"],
            ),
            fixture["transitionalSnapshot"],
        )
        self.assertEqual(
            gear_resolver.resolve(
                fixture["candidateIntent"],
                fixture["candidateAuthority"],
            ),
            fixture["candidateSnapshot"],
        )
        self.assertTrue(
            gear_release_shadow._legacy_to_v2_enhancement_migration_equivalent(
                fixture["transitionalSnapshot"],
                fixture["candidateSnapshot"],
                transitional_gear_release_id="compatibility-pg:old",
                transitional_gear_catalog_revision="compatibility-pg:old",
                candidate_gear_release_id="gear-release-17",
                transitional_authority_context=fixture[
                    "transitionalAuthority"
                ],
                candidate_authority_context=fixture["candidateAuthority"],
                transitional_intent=fixture["transitionalIntent"],
                candidate_intent=fixture["candidateIntent"],
                migration_mode="editor_only",
            )
        )

    def reverse_editor_writer_fixture(self, fixture, editor_type):
        candidate_intent = copy.deepcopy(fixture["candidateIntent"])
        candidate_authority = copy.deepcopy(fixture["candidateAuthority"])
        slot = fixture["slot"]
        selection = candidate_intent["slots"][slot]
        selection_field = {
            "gem": "gemOptionIds",
            "enchant": "enchantOptionId",
            "embellishment": "embellishmentOptionId",
        }[editor_type]
        allowed_field = {
            "gem": "allowedGemOptionIds",
            "enchant": "allowedEnchantOptionIds",
            "embellishment": "allowedEmbellishmentOptionIds",
        }[editor_type]
        selection[selection_field] = [] if editor_type == "gem" else ""
        item = candidate_authority["itemsById"][selection["itemId"]]
        item[allowed_field] = []
        item["baseCapabilities"][allowed_field] = []
        fixture = copy.deepcopy(fixture)
        fixture["candidateIntent"] = candidate_intent
        fixture["candidateAuthority"] = candidate_authority
        fixture["candidateSnapshot"] = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )
        return fixture

    def test_editor_migration_rejects_old_authority_source_only_masking(self):
        fixture = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={"enchant_id": "8039/8052"},
            candidate_variant_governed={},
            transitional_variant_governed={"enchant_id": "8039/8052"},
        )
        slot = fixture["slot"]
        self.assertEqual(
            fixture["transitionalSnapshot"]["resolvedSlots"][slot][
                "simcOptions"
            ],
            fixture["candidateSnapshot"]["resolvedSlots"][slot]["simcOptions"],
        )
        self.assert_real_writer_migration_rejected(fixture)

    def test_editor_migration_rejects_old_authority_non_editor_simc_deletion(self):
        fixture = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={"enchant_id": "999001"},
            transitional_selects_editor=True,
            non_editor_type="crafted",
            candidate_non_editor_simc={},
            transitional_non_editor_simc={"enchant_id": "999001"},
        )
        slot = fixture["slot"]
        self.assertEqual(
            fixture["transitionalSnapshot"]["resolvedSlots"][slot][
                "simcOptions"
            ],
            fixture["candidateSnapshot"]["resolvedSlots"][slot]["simcOptions"],
        )
        self.assert_real_writer_migration_rejected(fixture)

    def test_editor_migration_rejects_missing_canonical_enchant_and_embellishment_writers(self):
        for editor_type, malformed_options in (
            (
                "enchant",
                (
                    {},
                    {"enchant_id": ""},
                    {"enchant_id": "  "},
                    {"enchant_id": "8039,8052"},
                    {"enchant_id": "id=8039"},
                    {"enchant_id": "附魔8039"},
                ),
            ),
            (
                "embellishment",
                (
                    {},
                    {"embellishment": ""},
                    {"embellishment": "  "},
                    {"embellishment": "999,1000"},
                    {"embellishment": "id=999"},
                    {"embellishment": "美化999"},
                ),
            ),
        ):
            for simc_options in malformed_options:
                with self.subTest(
                    editor_type=editor_type,
                    simc_options=simc_options,
                ):
                    fixture = self.real_editor_writer_fixture(
                        editor_type=editor_type,
                        editor_simc_options=simc_options,
                    )
                    self.assert_real_writer_migration_rejected(fixture)

    def test_editor_migration_rejects_invalid_gem_occurrence_writers(self):
        for simc_options in (
            {},
            {"gem_id": ""},
            {"gem_id": "  "},
            {"gem_id": "240892/240916"},
            {"gem_id": "240892,240916"},
            {"gem_id": "id=240892"},
            {"gem_id": "宝石240892"},
        ):
            with self.subTest(simc_options=simc_options):
                fixture = self.real_editor_writer_fixture(
                    editor_type="gem",
                    editor_simc_options=[simc_options],
                )
                self.assert_real_writer_migration_rejected(fixture)

    def test_canonical_editor_writer_token_matches_profile_serializer_grammar(self):
        field_by_type = {
            "gem": ("gemOptionIds", "gem_id"),
            "enchant": ("enchantOptionId", "enchant_id"),
            "embellishment": ("embellishmentOptionId", "embellishment"),
        }
        for editor_type, malformed_value in (
            ("gem", "240892,240916"),
            ("gem", "id=240892"),
            ("gem", "宝石240892"),
            ("enchant", "8039,8052"),
            ("enchant", "id=8039"),
            ("enchant", "附魔8039"),
            ("embellishment", "999,1000"),
            ("embellishment", "id=999"),
            ("embellishment", "美化999"),
        ):
            with self.subTest(
                editor_type=editor_type,
                malformed_value=malformed_value,
            ):
                selection_field, simc_field = field_by_type[editor_type]
                selection = {
                    "gemOptionIds": [],
                    "enchantOptionId": "",
                    "embellishmentOptionId": "",
                    "craftedOptionId": "",
                    "catalystOptionId": "",
                }
                option_id = f"{editor_type}-writer"
                selection[selection_field] = (
                    [option_id] if editor_type == "gem" else option_id
                )
                self.assertIsNone(
                    gear_release_shadow._selected_simc_writer_plan(
                        selection,
                        {"simcOptions": {}},
                        {
                            option_id: {
                                "optionId": option_id,
                                "optionType": editor_type,
                                "simcOptions": {simc_field: malformed_value},
                            }
                        },
                        gear_socket_authority.CAPABILITY_REVISION,
                    )
                )

    def test_editor_writer_plan_rejects_non_governed_multi_writer_collisions(self):
        base_selection = {
            "gemOptionIds": [],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
        cases = []

        two_gems = copy.deepcopy(base_selection)
        two_gems["gemOptionIds"] = ["gem-a", "gem-b"]
        cases.append((
            "two_gems",
            two_gems,
            {
                "gem-a": {
                    "optionId": "gem-a",
                    "optionType": "gem",
                    "simcOptions": {"gem_id": "1", "bonus_id": "11"},
                },
                "gem-b": {
                    "optionId": "gem-b",
                    "optionType": "gem",
                    "simcOptions": {"gem_id": "2", "bonus_id": "22"},
                },
            },
        ))

        duplicate_gem = copy.deepcopy(base_selection)
        duplicate_gem["gemOptionIds"] = ["gem-a", "gem-a"]
        cases.append((
            "duplicate_gem",
            duplicate_gem,
            {
                "gem-a": {
                    "optionId": "gem-a",
                    "optionType": "gem",
                    "simcOptions": {"gem_id": "1", "bonus_id": "11"},
                },
            },
        ))

        gem_and_enchant = copy.deepcopy(base_selection)
        gem_and_enchant["gemOptionIds"] = ["gem-a"]
        gem_and_enchant["enchantOptionId"] = "enchant-a"
        cases.append((
            "gem_and_enchant",
            gem_and_enchant,
            {
                "gem-a": {
                    "optionId": "gem-a",
                    "optionType": "gem",
                    "simcOptions": {"gem_id": "1", "custom_writer": "gem"},
                },
                "enchant-a": {
                    "optionId": "enchant-a",
                    "optionType": "enchant",
                    "simcOptions": {
                        "enchant_id": "2",
                        "custom_writer": "enchant",
                    },
                },
            },
        ))

        for name, selection, options in cases:
            with self.subTest(name=name):
                self.assertIsNone(
                    gear_release_shadow._selected_simc_writer_plan(
                        selection,
                        {"simcOptions": {}},
                        options,
                        gear_socket_authority.CAPABILITY_REVISION,
                    )
                )

    def test_editor_migration_rejects_partial_gem_auxiliary_writers(self):
        for auxiliary_field in ("gem_bonus_id", "gem_ilevel"):
            with self.subTest(auxiliary_field=auxiliary_field):
                fixture = self.real_editor_writer_fixture(
                    editor_type="gem",
                    editor_simc_options=[
                        {"gem_id": "240892", auxiliary_field: "1"},
                        {"gem_id": "240916"},
                    ],
                )
                self.assert_real_writer_migration_rejected(fixture)

    def test_editor_migration_rejects_editor_managed_field_without_writer(self):
        fixture = self.real_editor_writer_fixture(
            candidate_variant_governed={"enchant_id": "7777"},
            transitional_variant_governed={"enchant_id": "7777"},
            candidate_management={"enchant_id": "editor_managed"},
        )
        self.assert_real_writer_migration_rejected(fixture)

    def test_editor_migration_accepts_canonical_editor_writers(self):
        for editor_type, simc_options in (
            ("gem", [{"gem_id": "240892"}, {"gem_id": "240916"}]),
            ("enchant", {"enchant_id": "8039"}),
            ("embellishment", {"embellishment": "999001"}),
        ):
            with self.subTest(editor_type=editor_type):
                fixture = self.real_editor_writer_fixture(
                    editor_type=editor_type,
                    editor_simc_options=simc_options,
                )
                self.assert_real_writer_migration_accepted(fixture)

    def test_editor_migration_accepts_only_cross_slot_selected_options(self):
        fixture = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={"enchant_id": "8039"},
        )
        candidate_intent = fixture["candidateIntent"]
        candidate_authority = fixture["candidateAuthority"]
        transitional_authority = fixture["transitionalAuthority"]
        primary_slot = fixture["slot"]
        secondary_slot = "neck"
        primary_option_id = candidate_intent["slots"][primary_slot][
            "enchantOptionId"
        ]
        secondary_option_id = "enchant-writer-cross-slot"
        primary_option = candidate_authority["optionsById"][primary_option_id]
        primary_option["applicableSlots"] = [primary_slot, secondary_slot]
        secondary_option = copy.deepcopy(primary_option)
        secondary_option.update({
            "optionId": secondary_option_id,
            "simcOptions": {"enchant_id": "8052"},
            "sourceRefIds": [
                f"evidence:pg:option:{secondary_option_id}"
            ],
        })
        candidate_authority["optionsById"][secondary_option_id] = (
            secondary_option
        )
        candidate_authority["evidenceRecordsById"][
            f"evidence:pg:option:{secondary_option_id}"
        ] = {
            "id": f"evidence:pg:option:{secondary_option_id}",
            "optionId": secondary_option_id,
            "sourceType": "postgres_gear_option",
            "sourceRevision": "2026-07-14T00:00:00+00:00",
        }
        candidate_intent["slots"][secondary_slot]["enchantOptionId"] = (
            secondary_option_id
        )
        allowed = [primary_option_id, secondary_option_id]
        for authority in (candidate_authority, transitional_authority):
            for slot in (primary_slot, secondary_slot):
                selection = (
                    candidate_intent["slots"][slot]
                    if authority is candidate_authority
                    else fixture["transitionalIntent"]["slots"][slot]
                )
                item = authority["itemsById"][selection["itemId"]]
                item["baseCapabilities"]["canEnchant"] = True
                item["allowedEnchantOptionIds"] = (
                    list(allowed) if authority is candidate_authority else []
                )
                item["baseCapabilities"]["allowedEnchantOptionIds"] = (
                    list(allowed) if authority is candidate_authority else []
                )
        fixture["transitionalSnapshot"] = gear_resolver.resolve(
            fixture["transitionalIntent"],
            transitional_authority,
        )
        fixture["candidateSnapshot"] = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )

        self.assert_real_writer_migration_accepted(fixture)

        unexpected = copy.deepcopy(fixture)
        unexpected_option_id = "enchant-writer-unselected"
        unexpected_option = copy.deepcopy(secondary_option)
        unexpected_option.update({
            "optionId": unexpected_option_id,
            "sourceRefIds": [
                f"evidence:pg:option:{unexpected_option_id}"
            ],
        })
        unexpected["candidateAuthority"]["optionsById"][
            unexpected_option_id
        ] = unexpected_option
        unexpected["candidateAuthority"]["evidenceRecordsById"][
            f"evidence:pg:option:{unexpected_option_id}"
        ] = {
            "id": f"evidence:pg:option:{unexpected_option_id}",
            "optionId": unexpected_option_id,
            "sourceType": "postgres_gear_option",
            "sourceRevision": "2026-07-14T00:00:00+00:00",
        }
        primary_item_id = unexpected["candidateIntent"]["slots"][
            primary_slot
        ]["itemId"]
        primary_item = unexpected["candidateAuthority"]["itemsById"][
            primary_item_id
        ]
        primary_item["allowedEnchantOptionIds"].append(
            unexpected_option_id
        )
        primary_item["baseCapabilities"]["allowedEnchantOptionIds"].append(
            unexpected_option_id
        )
        unexpected["candidateSnapshot"] = gear_resolver.resolve(
            unexpected["candidateIntent"],
            unexpected["candidateAuthority"],
        )
        self.assert_real_writer_migration_rejected(unexpected)

    def test_editor_migration_accepts_zero_or_complete_gem_auxiliary_sequences(self):
        for name, simc_options, duplicate_gem in (
            (
                "zero_auxiliary",
                [{"gem_id": "240892"}, {"gem_id": "240916"}],
                False,
            ),
            (
                "complete_auxiliary",
                [
                    {
                        "gem_id": "240892",
                        "gem_bonus_id": "1",
                        "gem_ilevel": "639",
                    },
                    {
                        "gem_id": "240916",
                        "gem_bonus_id": "2",
                        "gem_ilevel": "639",
                    },
                ],
                False,
            ),
            (
                "duplicate_occurrence",
                [{
                    "gem_id": "240892",
                    "gem_bonus_id": "1",
                    "gem_ilevel": "639",
                }],
                True,
            ),
        ):
            with self.subTest(name=name):
                fixture = self.real_editor_writer_fixture(
                    editor_type="gem",
                    editor_simc_options=simc_options,
                    duplicate_gem=duplicate_gem,
                )
                self.assert_real_writer_migration_accepted(fixture)

    def test_editor_migration_accepts_validated_management_semantics(self):
        editor_managed = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={"enchant_id": "8039"},
            candidate_variant_governed={"enchant_id": "7777"},
            transitional_variant_governed={"enchant_id": "7777"},
            candidate_management={"enchant_id": "editor_managed"},
        )
        self.assert_real_writer_migration_accepted(editor_managed)

        unresolved_drop = self.real_editor_writer_fixture(
            candidate_variant_governed={"enchant_id": "7777"},
            transitional_variant_governed={"enchant_id": "7777"},
            candidate_management={"enchant_id": "unresolved_drop"},
        )
        self.assert_real_writer_migration_accepted(unresolved_drop)

    def test_editor_migration_rejects_missing_or_invalid_v2_management_marker(self):
        fixture = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={"enchant_id": "8039"},
            candidate_variant_governed={"enchant_id": "7777"},
            transitional_variant_governed={"enchant_id": "7777"},
            candidate_management={"enchant_id": "editor_managed"},
        )
        self.assert_real_writer_migration_accepted(fixture)
        slot = fixture["slot"]
        variant_key = fixture["candidateIntent"]["slots"][slot]["variantKey"]
        baseline_output = fixture["candidateSnapshot"]["resolvedSlots"][slot][
            "simcOptions"
        ]

        def remove_marker(variant):
            variant.pop("enhancementManagement", None)

        def forge_schema(variant):
            variant["enhancementManagement"]["schemaRevision"] = "forged"

        def omit_governed_field(variant):
            variant["enhancementManagement"]["fields"] = {}

        for name, mutate in (
            ("missing_marker", remove_marker),
            ("forged_schema", forge_schema),
            ("missing_field", omit_governed_field),
        ):
            with self.subTest(name=name):
                mutated = copy.deepcopy(fixture)
                authority = mutated["candidateAuthority"]
                mutate(authority["variantsByKey"][variant_key])
                snapshot = gear_resolver.resolve(
                    mutated["candidateIntent"],
                    authority,
                )
                self.assertEqual(snapshot["status"], "verified")
                self.assertEqual(
                    snapshot["resolvedSlots"][slot]["simcOptions"],
                    baseline_output,
                )
                mutated["candidateSnapshot"] = snapshot
                self.assert_real_writer_migration_rejected(mutated)

    def test_editor_migration_accepts_reverse_canonical_writers_and_rejects_invalid_old_writer(self):
        for editor_type, simc_options in (
            ("gem", [{"gem_id": "240892"}]),
            ("enchant", {"enchant_id": "8039"}),
            ("embellishment", {"embellishment": "999001"}),
        ):
            with self.subTest(editor_type=editor_type):
                fixture = self.real_editor_writer_fixture(
                    editor_type=editor_type,
                    editor_simc_options=simc_options,
                    transitional_selects_editor=True,
                )
                fixture = self.reverse_editor_writer_fixture(
                    fixture,
                    editor_type,
                )
                self.assert_real_writer_migration_accepted(fixture)

        invalid_old_writer = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={"enchant_id": "8039/8052"},
            transitional_selects_editor=True,
        )
        invalid_old_writer = self.reverse_editor_writer_fixture(
            invalid_old_writer,
            "enchant",
        )
        self.assert_real_writer_migration_rejected(invalid_old_writer)

    def test_enhancement_migration_run_blocks_empty_canonical_editor_writer(self):
        fixture = self.real_editor_writer_fixture(
            editor_type="enchant",
            editor_simc_options={},
        )
        candidate_snapshot = fixture["candidateSnapshot"]
        candidate = {
            "templateId": "template-a",
            "classKey": "mage",
            "specKey": "arcane",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/a",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:a",
            "gearHash": "gear:a",
            "selectionIntent": fixture["candidateIntent"],
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                fixture["candidateIntent"],
                candidate_snapshot,
            ),
            "problems": [],
        }
        store = FakeShadowStore(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            candidate_authority_context=fixture["candidateAuthority"],
            transitional_authority_context=fixture["transitionalAuthority"],
        )
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": False,
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": "compatibility-pg:old",
            },
            "dependencyRevisions": {
                "capabilityRevision": (
                    gear_socket_authority.LEGACY_CAPABILITY_REVISION
                ),
            },
        }
        profile = {
            "status": "resolved",
            "data": {"profile": "mage=empty-editor-writer"},
            "problems": [],
        }
        with patch.object(
            gear_release_shadow,
            "_selection_intent_from_template",
            return_value=copy.deepcopy(fixture["transitionalIntent"]),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": fixture["transitionalSnapshot"],
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": candidate_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release-17",
                community_release_id="community-release-17",
                simc_runtime_revision="simc-v1",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["specResults"][0]["enhancementMigrationParity"]["status"],
            "blocked",
        )
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_editor_migration_rejects_source_only_simc_masked_by_selected_options(self):
        cases = [
            ("editor", (), True, False),
            ("crafted", ("crafted",), False, False),
            ("catalyst", ("catalyst",), False, False),
        ]
        for name, option_types, select_editor, transitional_select_editor in cases:
            with self.subTest(name=name):
                fixture = self.real_simc_contribution_collision_fixture(
                    non_editor_types=option_types,
                    variant_classification="source_only",
                    transitional_variant_value="8039/8052",
                    candidate_variant_value="7777",
                    transitional_non_editor_value="8039/8052",
                    candidate_non_editor_value="8039/8052",
                    select_editor=select_editor,
                    transitional_select_editor=transitional_select_editor,
                )
                slot = fixture["slot"]
                self.assertEqual(
                    fixture["transitionalSnapshot"]["resolvedSlots"][slot][
                        "simcOptions"
                    ]["enchant_id"],
                    fixture["candidateSnapshot"]["resolvedSlots"][slot][
                        "simcOptions"
                    ]["enchant_id"],
                )
                self.assert_real_editor_migration_rejected(fixture)

    def test_editor_migration_preserves_unmasked_source_only_simc_drift(self):
        fixture = self.real_simc_contribution_collision_fixture(
            variant_classification="source_only",
            transitional_variant_value="8039/8052",
            candidate_variant_value="7777",
        )
        slot = fixture["slot"]
        self.assertNotEqual(
            fixture["transitionalSnapshot"]["resolvedSlots"][slot][
                "simcOptions"
            ]["enchant_id"],
            fixture["candidateSnapshot"]["resolvedSlots"][slot][
                "simcOptions"
            ]["enchant_id"],
        )
        self.assert_real_editor_migration_rejected(fixture)

    def test_editor_migration_rejects_non_editor_simc_masked_by_migration_fields(self):
        migration_sources = (
            ("editor_managed", False),
            ("unresolved_drop", False),
            (None, True),
        )
        for option_type in ("crafted", "catalyst"):
            for classification, select_editor in migration_sources:
                with self.subTest(
                    option_type=option_type,
                    classification=classification,
                ):
                    fixture = self.real_simc_contribution_collision_fixture(
                        non_editor_types=(option_type,),
                        variant_classification=classification,
                        transitional_non_editor_value="999002",
                        candidate_non_editor_value="999001",
                        select_editor=select_editor,
                        transitional_select_editor=select_editor,
                    )
                    slot = fixture["slot"]
                    self.assertNotEqual(
                        fixture["transitionalSnapshot"]["resolvedSlots"][slot][
                            "simcOptions"
                        ]["enchant_id"],
                        fixture["candidateSnapshot"]["resolvedSlots"][slot][
                            "simcOptions"
                        ]["enchant_id"],
                    )
                    self.assert_real_editor_migration_rejected(fixture)

    def test_editor_migration_rejects_non_editor_simc_masked_by_retained_variant_field(self):
        fixture = self.real_simc_contribution_collision_fixture(
            non_editor_types=("crafted",),
            variant_classification=None,
            simc_field="bonus_id",
            transitional_variant_value="variant-old",
            candidate_variant_value="variant-new",
            transitional_non_editor_value="canonical-bonus",
            candidate_non_editor_value="canonical-bonus",
        )
        slot = fixture["slot"]
        self.assertEqual(
            fixture["transitionalSnapshot"]["resolvedSlots"][slot][
                "simcOptions"
            ]["bonus_id"],
            fixture["candidateSnapshot"]["resolvedSlots"][slot][
                "simcOptions"
            ]["bonus_id"],
        )
        self.assert_real_editor_migration_rejected(fixture)

    def test_editor_migration_rejects_crafted_catalyst_simc_key_overlap(self):
        fixture = self.real_simc_contribution_collision_fixture(
            non_editor_types=("crafted", "catalyst"),
            variant_classification=None,
            transitional_non_editor_value="999001",
            candidate_non_editor_value="999001",
        )
        self.assert_real_editor_migration_rejected(fixture)

    def test_enhancement_migration_run_blocks_source_only_simc_masking(self):
        fixture = self.real_simc_contribution_collision_fixture(
            variant_classification="source_only",
            transitional_variant_value="8039/8052",
            candidate_variant_value="7777",
            select_editor=True,
            transitional_select_editor=False,
        )
        candidate_snapshot = fixture["candidateSnapshot"]
        candidate = {
            "templateId": "template-a",
            "classKey": "mage",
            "specKey": "arcane",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/a",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:a",
            "gearHash": "gear:a",
            "selectionIntent": fixture["candidateIntent"],
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                fixture["candidateIntent"],
                candidate_snapshot,
            ),
            "problems": [],
        }
        store = FakeShadowStore(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            candidate_authority_context=fixture["candidateAuthority"],
            transitional_authority_context=fixture["transitionalAuthority"],
        )
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": False,
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": "compatibility-pg:old",
            },
            "dependencyRevisions": {
                "capabilityRevision": (
                    gear_socket_authority.LEGACY_CAPABILITY_REVISION
                ),
            },
        }
        profile = {
            "status": "resolved",
            "data": {"profile": "mage=source-only-mask"},
            "problems": [],
        }
        with patch.object(
            gear_release_shadow,
            "_selection_intent_from_template",
            return_value=copy.deepcopy(fixture["transitionalIntent"]),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": fixture["transitionalSnapshot"],
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": candidate_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release-17",
                community_release_id="community-release-17",
                simc_runtime_revision="simc-v1",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["specResults"][0]["enhancementMigrationParity"]["status"],
            "blocked",
        )
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_real_editor_only_migration_rejects_untrusted_candidate_authority_and_ledger(self):
        fixture = self.real_non_editor_option_evidence_migration_fixture(
            "crafted",
            transitional_source_revision="2026-07-14T00:00:00+00:00",
        )
        binding = self.selected_editor_option_binding(fixture)
        arguments = {
            "transitional_gear_release_id": "compatibility-pg:old",
            "transitional_gear_catalog_revision": "compatibility-pg:old",
            "candidate_gear_release_id": "gear-release-17",
            "transitional_authority_context": fixture[
                "transitionalAuthority"
            ],
            "transitional_intent": fixture["transitionalIntent"],
            "candidate_intent": fixture["candidateIntent"],
            "migration_mode": "editor_only",
        }

        self.assertTrue(
            gear_release_shadow._legacy_to_v2_enhancement_migration_equivalent(
                fixture["transitionalSnapshot"],
                fixture["candidateSnapshot"],
                candidate_authority_context=fixture["candidateAuthority"],
                **arguments,
            )
        )

        mutations = {
            "forged_source_type": lambda authority: authority[
                "evidenceRecordsById"
            ][binding["evidenceId"]].update(sourceType="forged"),
            "invalid_source_revision": lambda authority: authority[
                "evidenceRecordsById"
            ][binding["evidenceId"]].update(sourceRevision="not-a-timestamp"),
            "wrong_record_option_id": lambda authority: authority[
                "evidenceRecordsById"
            ][binding["evidenceId"]].update(optionId="wrong-option"),
            "missing_option_source_refs": lambda authority: authority[
                "optionsById"
            ][binding["optionId"]].update(sourceRefIds=[]),
            "missing_item_source_refs": lambda authority: authority[
                "itemsById"
            ][binding["itemId"]].update(sourceRefIds=[]),
            "missing_variant_source_refs": lambda authority: authority[
                "variantsByKey"
            ][binding["variantKey"]].update(sourceRefIds=[]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                authority = copy.deepcopy(fixture["candidateAuthority"])
                mutate(authority)
                snapshot = gear_resolver.resolve(
                    fixture["candidateIntent"],
                    authority,
                )
                self.assertEqual(snapshot["status"], "verified")
                self.assertEqual(snapshot["problems"], [])
                self.assertEqual(
                    gear_resolver.resolve(fixture["candidateIntent"], authority),
                    snapshot,
                )
                self.assertFalse(
                    gear_release_shadow._legacy_to_v2_enhancement_migration_equivalent(
                        fixture["transitionalSnapshot"],
                        snapshot,
                        candidate_authority_context=authority,
                        **arguments,
                    )
                )

        malformed_snapshot = copy.deepcopy(fixture["candidateSnapshot"])
        malformed_snapshot["evidenceLedger"]["claimGroups"][
            "identity_options"
        ] = []
        self.assertFalse(
            gear_release_shadow._legacy_to_v2_enhancement_migration_equivalent(
                fixture["transitionalSnapshot"],
                malformed_snapshot,
                candidate_authority_context=fixture["candidateAuthority"],
                **arguments,
            )
        )

    def test_enhancement_migration_run_blocks_forged_editor_evidence(self):
        fixture = self.real_non_editor_option_evidence_migration_fixture(
            "crafted",
            transitional_source_revision="2026-07-14T00:00:00+00:00",
        )
        binding = self.selected_editor_option_binding(fixture)
        candidate_authority = copy.deepcopy(fixture["candidateAuthority"])
        candidate_authority["evidenceRecordsById"][binding["evidenceId"]][
            "sourceType"
        ] = "forged"
        candidate_snapshot = gear_resolver.resolve(
            fixture["candidateIntent"],
            candidate_authority,
        )
        self.assertEqual(candidate_snapshot["status"], "verified")
        self.assertEqual(
            gear_resolver.resolve(fixture["candidateIntent"], candidate_authority),
            candidate_snapshot,
        )
        candidate = {
            "templateId": "template-a",
            "classKey": "mage",
            "specKey": "arcane",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/a",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:a",
            "gearHash": "gear:a",
            "selectionIntent": fixture["candidateIntent"],
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                fixture["candidateIntent"],
                candidate_snapshot,
            ),
            "problems": [],
        }
        store = FakeShadowStore(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            candidate_authority_context=candidate_authority,
            transitional_authority_context=fixture["transitionalAuthority"],
        )
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": False,
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": "compatibility-pg:old",
            },
            "dependencyRevisions": {
                "capabilityRevision": (
                    gear_socket_authority.LEGACY_CAPABILITY_REVISION
                ),
            },
        }
        profile = {
            "status": "resolved",
            "data": {"profile": "mage=forged-editor-evidence"},
            "problems": [],
        }
        with patch.object(
            gear_release_shadow,
            "_selection_intent_from_template",
            return_value=copy.deepcopy(fixture["transitionalIntent"]),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": fixture["transitionalSnapshot"],
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": candidate_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release-17",
                community_release_id="community-release-17",
                simc_runtime_revision="simc-v1",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["specResults"][0]["enhancementMigrationParity"]["status"],
            "blocked",
        )
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_internal_shadow_compares_one_release_pair_without_public_cutover(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = self.snapshot(transitional_intent, "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")

        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ) as old_resolve, patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ) as candidate_resolve:
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["report"]["diffs"][0]["classification"], "revision_only")
        self.assertEqual(result["publicReadCount"], 1)
        self.assertFalse(result["formalActiveManifest"])
        self.assertGreaterEqual(result["performance"]["totalDurationMs"], 0)
        self.assertGreaterEqual(result["performance"]["specP95Ms"], 0)
        self.assertIn("durationMs", result["specResults"][0])
        self.assertEqual(store.calls[0][0], "community")
        old_resolve.assert_called_once()
        candidate_resolve.assert_called_once()
        self.assertEqual(
            old_resolve.call_args.args[0]["authoredAgainst"]["gearCatalogRevision"],
            "compatibility-pg:old",
        )

    def test_refresh_shadow_accepts_expected_formal_active_public_reader(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        active = self.formal_active_pair(candidate)
        store.get_active_community_release = unittest.mock.Mock(
            side_effect=[active, copy.deepcopy(active)]
        )
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": True,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
        }
        snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": snapshot, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
                expect_formal_active=True,
            )

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["formalActiveManifest"])

    def test_formal_active_shadow_blocks_generation_change_without_migration(self):
        candidate = self.candidate_row()
        start = self.formal_active_pair(candidate, pointer_generation=7)
        end = self.formal_active_pair(candidate, pointer_generation=8)

        result, store, active_reader = self.run_formal_active_pointer_shadow(
            [start, end]
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "ACTIVE_RELEASE_CHANGED_DURING_SHADOW",
            {problem["code"] for problem in result["blockers"]},
        )
        self.assertEqual(active_reader.call_count, 2)
        self.assertEqual(
            [call for call in store.calls if call[0] == "exact-authority"],
            [],
        )

    def test_formal_active_shadow_blocks_aba_generation_change(self):
        candidate = self.candidate_row()
        start = self.formal_active_pair(candidate, pointer_generation=7)
        end = self.formal_active_pair(candidate, pointer_generation=9)

        result, _store, active_reader = self.run_formal_active_pointer_shadow(
            [start, end]
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "ACTIVE_RELEASE_CHANGED_DURING_SHADOW",
            {problem["code"] for problem in result["blockers"]},
        )
        self.assertEqual(active_reader.call_count, 2)

    def test_formal_active_shadow_blocks_ending_reader_exception(self):
        candidate = self.candidate_row()
        start = self.formal_active_pair(candidate, pointer_generation=7)

        result, _store, active_reader = self.run_formal_active_pointer_shadow(
            [start, RuntimeError("active pointer unavailable")]
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "ACTIVE_RELEASE_CHANGED_DURING_SHADOW",
            {problem["code"] for problem in result["blockers"]},
        )
        self.assertEqual(active_reader.call_count, 2)

    def test_formal_active_shadow_accepts_stable_generation(self):
        candidate = self.candidate_row()
        active = self.formal_active_pair(candidate, pointer_generation=7)

        result, _store, active_reader = self.run_formal_active_pointer_shadow(
            [active, copy.deepcopy(active)]
        )

        self.assertEqual(result["status"], "pass", result)
        self.assertNotIn(
            "ACTIVE_RELEASE_CHANGED_DURING_SHADOW",
            {problem["code"] for problem in result["blockers"]},
        )
        self.assertEqual(active_reader.call_count, 2)

    def test_formal_active_shadow_rejects_invalid_starting_identity_early(self):
        candidate = self.candidate_row()
        valid = self.formal_active_pair(candidate, pointer_generation=7)
        invalid_cases = {
            "not_formal": {**valid, "formalActiveManifest": False},
            "missing_gear_id": {**valid, "gearRelease": {"releaseId": ""}},
            "missing_community_id": {
                **valid,
                "communityRelease": {"releaseId": ""},
            },
            "missing_manifest_revision": {**valid, "manifestRevision": ""},
            "missing_generation": {
                key: value
                for key, value in valid.items()
                if key != "pointerGeneration"
            },
            "string_generation": {**valid, "pointerGeneration": "7"},
            "boolean_generation": {**valid, "pointerGeneration": True},
            "zero_generation": {**valid, "pointerGeneration": 0},
        }

        for case, active in invalid_cases.items():
            with self.subTest(case=case):
                result, _store, active_reader = (
                    self.run_formal_active_pointer_shadow([active])
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn(
                    "ACTIVE_RELEASE_BASELINE_INVALID",
                    {problem["code"] for problem in result["blockers"]},
                )
                self.assertEqual(result["publicReadCount"], 0)
                self.assertEqual(active_reader.call_count, 1)

    def test_self_formal_active_reader_rejects_invalid_identity_without_expectation(self):
        candidate = self.candidate_row()
        valid = self.formal_active_pair(candidate, pointer_generation=7)
        invalid_cases = {
            "missing_gear_id": {**valid, "gearRelease": {"releaseId": ""}},
            "missing_community_id": {
                **valid,
                "communityRelease": {"releaseId": ""},
            },
            "missing_manifest_revision": {**valid, "manifestRevision": ""},
            "missing_generation": {
                key: value
                for key, value in valid.items()
                if key != "pointerGeneration"
            },
            "string_generation": {**valid, "pointerGeneration": "7"},
            "boolean_generation": {**valid, "pointerGeneration": True},
            "zero_generation": {**valid, "pointerGeneration": 0},
        }

        for case, active in invalid_cases.items():
            with self.subTest(case=case):
                result, _store, active_reader = (
                    self.run_formal_active_pointer_shadow(
                        [active],
                        expect_formal_active=False,
                        resolver_formal_active=False,
                    )
                )
                self.assertEqual(result["status"], "blocked")
                self.assertIn(
                    "ACTIVE_RELEASE_BASELINE_INVALID",
                    {problem["code"] for problem in result["blockers"]},
                )
                self.assertEqual(result["publicReadCount"], 0)
                self.assertEqual(active_reader.call_count, 1)

    def test_transitional_reader_passes_without_formal_expectation(self):
        candidate = self.candidate_row()
        transitional = self.formal_active_pair(
            candidate,
            pointer_generation=7,
            formal=False,
        )

        result, _store, active_reader = self.run_formal_active_pointer_shadow(
            [transitional],
            expect_formal_active=False,
            resolver_formal_active=False,
        )

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(active_reader.call_count, 1)

    def test_refresh_shadow_allows_explicit_degraded_empty_for_policy_gate(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        active = self.formal_active_pair(candidate)
        store.get_active_community_release = unittest.mock.Mock(
            side_effect=[active, copy.deepcopy(active)]
        )
        store.get_candidate_community_release = lambda gear_id, community_id: {
            "gearRelease": {
                "releaseId": gear_id,
                "dependencyRevisions": {
                    "capabilityRevision": (
                        gear_socket_authority.LEGACY_CAPABILITY_REVISION
                    ),
                },
            },
            "communityRelease": {"releaseId": community_id, "validatedAgainstReleaseId": gear_id},
            "rows": [{**candidate, "role": "rejected", "problems": [{"code": "COMMUNITY_SOURCE_STALE"}]}],
            "winners": [],
        }
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": True,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:sha256:target",
            },
        }
        result = gear_release_shadow.run_release_shadow(
            store,
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            community_release_id="community-release:sha256:target",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
            expect_formal_active=True,
            allow_degraded_empty=True,
        )

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["report"]["emptySpecs"], [{"classKey": "mage", "specKey": "arcane"}])
        self.assertEqual(result["specResults"][0]["status"], "degraded_empty")
        self.assertEqual(result["blockers"], [])

    def test_internal_shadow_accepts_legacy_sealed_signature_only_after_live_semantic_parity(self):
        candidate = self.candidate_row()
        candidate["semanticGearSignature"] = "sha256:legacy-evidence-sensitive"
        store = FakeShadowStore(candidate)
        original_pair_reader = store.get_candidate_community_release

        def legacy_pair(gear_release_id, community_release_id):
            pair = original_pair_reader(gear_release_id, community_release_id)
            pair["communityRelease"]["source"] = {"sourceRevision": "legacy-import-r0"}
            return pair

        store.get_candidate_community_release = unittest.mock.Mock(side_effect=legacy_pair)
        old_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "pass")

    def test_internal_shadow_blocks_public_baseline_or_candidate_resolve_failure(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate, baseline_count=1)
        old_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:old")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(503, {"status": "unavailable", "data": {}, "problems": [{"code": "MISSING"}]}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "blocked")
        codes = {problem["code"] for problem in result["blockers"]}
        self.assertIn("PUBLIC_BASELINE_LEAK", codes)
        self.assertIn("CANDIDATE_RESOLVE_FAILED", codes)
        self.assertEqual(
            result["specResults"][0]["candidateProblemCodes"],
            ["MISSING"],
        )

    def test_internal_shadow_fails_closed_when_public_reader_raises(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        store.get_websim_gear = unittest.mock.Mock(side_effect=RuntimeError("database unavailable"))

        result = gear_release_shadow.run_release_shadow(
            store,
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            community_release_id="community-release:sha256:target",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["publicReadCount"], 0)
        self.assertIn(
            "TRANSITIONAL_PUBLIC_READ_FAILED",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_internal_shadow_fails_closed_when_candidate_pair_is_not_an_object(self):
        store = FakeShadowStore(self.candidate_row())
        store.get_candidate_community_release = unittest.mock.Mock(return_value=[])

        result = gear_release_shadow.run_release_shadow(
            store,
            expected_specs=[("mage", "arcane")],
            gear_release_id="gear-release:sha256:target",
            community_release_id="community-release:sha256:target",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["blockers"][0]["code"],
            "CANDIDATE_RELEASE_READ_FAILED",
        )

    def test_internal_shadow_rejects_candidate_winner_outside_expected_matrix(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        original_pair_reader = store.get_candidate_community_release

        def pair_with_extra_winner(gear_release_id, community_release_id):
            pair = original_pair_reader(gear_release_id, community_release_id)
            extra = copy.deepcopy(candidate)
            extra["templateId"] = "template-fire"
            extra["specKey"] = "fire"
            extra["selectionIntent"]["eligibilityContext"]["specKey"] = "fire"
            pair["rows"].append(extra)
            pair["winners"].append(extra)
            return pair

        store.get_candidate_community_release = unittest.mock.Mock(side_effect=pair_with_extra_winner)
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = self.snapshot(transitional_intent, "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "UNEXPECTED_PUBLIC_SPEC",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_internal_shadow_compares_resolved_profile_content_not_only_status(self):
        candidate = self.candidate_row()
        store = FakeShadowStore(candidate)
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = self.snapshot(transitional_intent, "sha256:old")
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": old_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": candidate_snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, {"status": "resolved", "data": {"profile": "mage=old"}, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, {"status": "resolved", "data": {"profile": "mage=new"}, "problems": []}),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
            )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "PROFILE_PARITY_MISMATCH",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_enhancement_migration_does_not_allow_crafted_or_catalyst_changes(self):
        for field in ("craftedOptionId", "catalystOptionId"):
            with self.subTest(field=field):
                candidate = self.candidate_row()
                candidate_intent = candidate["selectionIntent"]
                candidate_intent["slots"]["head"]["gemOptionIds"] = ["gem-a"]
                candidate_intent["slots"]["head"][field] = f"changed-{field}"
                candidate_snapshot = self.snapshot(candidate_intent, "sha256:candidate")
                candidate["resolvedGearSignature"] = candidate_snapshot["resolvedGearSignature"]
                candidate["semanticGearSignature"] = gear_release.semantic_gear_signature(
                    candidate_intent,
                    candidate_snapshot,
                )
                store = FakeShadowStore(candidate)
                transitional_intent = self.intent()
                transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
                old_snapshot = self.snapshot(transitional_intent, "sha256:old")
                profile = {
                    "status": "resolved",
                    "data": {"profile": "mage=scope-guard"},
                    "problems": [],
                }

                with patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": old_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_candidate_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": candidate_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_profile_from_selection_intent",
                    return_value=(200, profile),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_candidate_profile_from_selection_intent",
                    return_value=(200, profile),
                ):
                    result = gear_release_shadow.run_release_shadow(
                        store,
                        expected_specs=[("mage", "arcane")],
                        gear_release_id="gear-release:sha256:target",
                        community_release_id="community-release:sha256:target",
                        simc_runtime_revision="simc-r1",
                    )

                self.assertEqual(result["status"], "blocked")
                self.assertEqual(
                    result["specResults"][0]["enhancementMigrationParity"]["status"],
                    "blocked",
                )
                self.assertIn(
                    "PUBLIC_WINNER_SEMANTIC_CHANGE",
                    {problem["code"] for problem in result["blockers"]},
                )

    def test_enhancement_migration_projection_preserves_crafted_and_catalyst_evidence(self):
        for option_type in ("crafted", "catalyst"):
            with self.subTest(option_type=option_type):
                fixture = self.real_non_editor_option_evidence_migration_fixture(
                    option_type
                )
                old_intent = fixture["transitionalIntent"]
                old_snapshot = fixture["transitionalSnapshot"]
                candidate_intent = fixture["candidateIntent"]
                candidate_snapshot = fixture["candidateSnapshot"]
                slot = fixture["slot"]
                option_field = fixture["optionField"]
                option_id = fixture["optionId"]
                evidence_id = fixture["evidenceId"]

                self.assertEqual(old_snapshot["status"], "verified")
                self.assertEqual(candidate_snapshot["status"], "verified")
                self.assertEqual(
                    old_intent["slots"][slot][option_field],
                    option_id,
                )
                self.assertEqual(
                    candidate_intent["slots"][slot][option_field],
                    option_id,
                )
                self.assertEqual(
                    old_snapshot["resolvedSlots"][slot]["resolvedStats"],
                    candidate_snapshot["resolvedSlots"][slot]["resolvedStats"],
                )
                self.assertEqual(
                    old_snapshot["resolvedSlots"][slot]["simcOptions"],
                    candidate_snapshot["resolvedSlots"][slot]["simcOptions"],
                )
                self.assertEqual(
                    old_snapshot["resolvedSlots"][slot]["effectiveCapabilities"][
                        "socketCount"
                    ],
                    candidate_snapshot["resolvedSlots"][slot][
                        "effectiveCapabilities"
                    ]["socketCount"],
                )
                self.assertEqual(
                    gear_release_shadow._non_enhancement_selection_projection(
                        old_intent
                    ),
                    gear_release_shadow._non_enhancement_selection_projection(
                        candidate_intent
                    ),
                )
                self.assertNotEqual(
                    old_snapshot["evidenceLedger"]["evidenceRecordsById"][
                        evidence_id
                    ]["sourceRevision"],
                    candidate_snapshot["evidenceLedger"]["evidenceRecordsById"][
                        evidence_id
                    ]["sourceRevision"],
                )
                self.assertFalse(
                    gear_release_shadow._legacy_to_v2_socket_capacity_migration_equivalent(
                        old_snapshot,
                        candidate_snapshot,
                        transitional_gear_release_id="compatibility-pg:old",
                        transitional_gear_catalog_revision="compatibility-pg:old",
                        candidate_gear_release_id="gear-release-17",
                        transitional_authority_context=fixture[
                            "transitionalAuthority"
                        ],
                        candidate_authority_context=fixture["candidateAuthority"],
                        transitional_intent=old_intent,
                        candidate_intent=candidate_intent,
                    )
                )
                self.assertNotEqual(
                    gear_release_shadow._enhancement_migration_projection(
                        old_snapshot
                    ),
                    gear_release_shadow._enhancement_migration_projection(
                        candidate_snapshot
                    ),
                )

    def test_enhancement_migration_run_blocks_crafted_and_catalyst_evidence_drift(self):
        for option_type in ("crafted", "catalyst"):
            with self.subTest(option_type=option_type):
                fixture = self.real_non_editor_option_evidence_migration_fixture(
                    option_type
                )
                old_intent = fixture["transitionalIntent"]
                old_snapshot = fixture["transitionalSnapshot"]
                candidate_intent = fixture["candidateIntent"]
                candidate_snapshot = fixture["candidateSnapshot"]
                candidate = {
                    "templateId": "template-a",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "role": "winner",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceUrl": "https://raider.io/a",
                    "sourceStatus": "synced",
                    "sampleCount": 1,
                    "profileHash": "profile:a",
                    "gearHash": "gear:a",
                    "selectionIntent": candidate_intent,
                    "resolvedGearSignature": candidate_snapshot[
                        "resolvedGearSignature"
                    ],
                    "semanticGearSignature": gear_release.semantic_gear_signature(
                        candidate_intent,
                        candidate_snapshot,
                    ),
                    "problems": [],
                }
                store = FakeShadowStore(
                    candidate,
                    capability_revision=gear_socket_authority.CAPABILITY_REVISION,
                    candidate_authority_context=fixture["candidateAuthority"],
                    transitional_authority_context=fixture[
                        "transitionalAuthority"
                    ],
                )
                store.get_gear_resolver_context = lambda _runtime: {
                    "formalActiveManifest": False,
                    "authoredAgainst": {
                        "seasonRevision": "season-17-active",
                        "gearCatalogRevision": "compatibility-pg:old",
                    },
                    "dependencyRevisions": {
                        "capabilityRevision": (
                            gear_socket_authority.LEGACY_CAPABILITY_REVISION
                        ),
                    },
                }
                profile = self.resolved_profile_envelope(
                    "mage=stable-non-editor-option"
                )
                with patch.object(
                    gear_release_shadow,
                    "_selection_intent_from_template",
                    return_value=copy.deepcopy(old_intent),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": old_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_candidate_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": candidate_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_profile_from_selection_intent",
                    return_value=(200, profile),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_candidate_profile_from_selection_intent",
                    return_value=(200, profile),
                ):
                    result = gear_release_shadow.run_release_shadow(
                        store,
                        expected_specs=[("mage", "arcane")],
                        gear_release_id="gear-release-17",
                        community_release_id="community-release-17",
                        simc_runtime_revision="simc-v1",
                    )

                self.assertEqual(result["status"], "blocked")
                self.assertEqual(
                    result["specResults"][0]["enhancementMigrationParity"][
                        "status"
                    ],
                    "blocked",
                )
                self.assertIn(
                    "PUBLIC_WINNER_SEMANTIC_CHANGE",
                    {problem["code"] for problem in result["blockers"]},
                )

    def test_enhancement_migration_allows_stable_crafted_and_catalyst_evidence(self):
        for option_type in ("crafted", "catalyst"):
            with self.subTest(option_type=option_type):
                fixture = self.real_non_editor_option_evidence_migration_fixture(
                    option_type,
                    transitional_source_revision="2026-07-14T00:00:00+00:00",
                )
                old_intent = fixture["transitionalIntent"]
                old_snapshot = fixture["transitionalSnapshot"]
                candidate_intent = fixture["candidateIntent"]
                candidate_snapshot = fixture["candidateSnapshot"]
                self.assertEqual(
                    gear_release_shadow._enhancement_migration_projection(
                        old_snapshot
                    ),
                    gear_release_shadow._enhancement_migration_projection(
                        candidate_snapshot
                    ),
                )

                candidate = {
                    "templateId": "template-a",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "role": "winner",
                    "sourceKey": "raiderio_observed_profile",
                    "sourceUrl": "https://raider.io/a",
                    "sourceStatus": "synced",
                    "sampleCount": 1,
                    "profileHash": "profile:a",
                    "gearHash": "gear:a",
                    "selectionIntent": candidate_intent,
                    "resolvedGearSignature": candidate_snapshot[
                        "resolvedGearSignature"
                    ],
                    "semanticGearSignature": gear_release.semantic_gear_signature(
                        candidate_intent,
                        candidate_snapshot,
                    ),
                    "problems": [],
                }
                store = FakeShadowStore(
                    candidate,
                    capability_revision=gear_socket_authority.CAPABILITY_REVISION,
                    candidate_authority_context=fixture["candidateAuthority"],
                    transitional_authority_context=fixture[
                        "transitionalAuthority"
                    ],
                )
                store.get_gear_resolver_context = lambda _runtime: {
                    "formalActiveManifest": False,
                    "authoredAgainst": {
                        "seasonRevision": "season-17-active",
                        "gearCatalogRevision": "compatibility-pg:old",
                    },
                    "dependencyRevisions": {
                        "capabilityRevision": (
                            gear_socket_authority.LEGACY_CAPABILITY_REVISION
                        ),
                    },
                }
                profile = self.resolved_profile_envelope(
                    "mage=stable-non-editor-option"
                )
                with patch.object(
                    gear_release_shadow,
                    "_selection_intent_from_template",
                    return_value=copy.deepcopy(old_intent),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": old_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_candidate_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": candidate_snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_profile_from_selection_intent",
                    return_value=(200, profile),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "build_candidate_profile_from_selection_intent",
                    return_value=(200, profile),
                ):
                    result = gear_release_shadow.run_release_shadow(
                        store,
                        expected_specs=[("mage", "arcane")],
                        gear_release_id="gear-release-17",
                        community_release_id="community-release-17",
                        simc_runtime_revision="simc-v1",
                    )

                self.assertEqual(result["status"], "pass", result)
                self.assertEqual(
                    result["specResults"][0]["enhancementMigrationParity"],
                    {"status": "pass", "mode": "enhancement_only"},
                )

    def test_legacy_to_v2_socket_capacity_migration_allows_only_consistent_one_to_two_upgrade(self):
        old_intent = self.intent()
        old_intent["authoredAgainst"]["gearCatalogRevision"] = "gear-release:old"
        old = self.snapshot(old_intent, "sha256:old")
        old.update({
            "contractRevision": "gear-resolved-snapshot-v1",
            "dependencyVector": {
                "seasonRevision": "season-17",
                "gearCatalogReleaseId": "gear-release:old",
                "gearCatalogRevision": "gear-release:old",
                "gearRuleRevision": "gear-rule-matrix-v1",
                "resolverContractRevision": "gear-resolver-contract-v1",
                "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
                "serializerRevision": "serializer-v1",
                "simcRuntimeRevision": "simc-r1",
                "statPolicyRevision": "stat-policy-v1",
                "selectionSchemaRevision": "selection-intent-v1",
            },
            "selectionSignature": gear_contracts.selection_signature(
                old_intent,
                old_intent["eligibilityContext"],
            ),
            "ruleResults": self.verified_rule_results(),
            "evidenceLedger": {
                "contractRevision": "gear-evidence-ledger-v1",
                "claims": [{
                    "claimId": "sha256:old-claim",
                    "claimKey": "slot:head:identity_options",
                    "group": "identity_options",
                    "status": "verified",
                    "dependsOn": [],
                    "sourceRefIds": ["evidence:item"],
                    "problems": [],
                }],
                "claimGroups": {
                    "identity_options": ["sha256:old-claim"],
                    "provenance": [],
                    "legality": [],
                    "static_attributes": [],
                    "profile_executability": [],
                },
                "evidenceRecordsById": {
                    "evidence:item": {
                        "id": "evidence:item",
                        "sourceType": "postgres_gear_item",
                        "updatedAt": "2026-07-11T00:00:00Z",
                    }
                },
                "problems": [],
            },
            "problems": [],
        })
        old["resolvedSlots"]["head"].update({
            "effectiveCapabilities": {
                "socketCount": 1,
                "allowedGemOptionIds": [],
                "allowedEnchantOptionIds": [],
                "allowedEmbellishmentOptionIds": [],
                "allowedCraftedOptionIds": [],
                "allowedCatalystOptionIds": [],
            },
            "selectedOptions": {
                "gemOptionIds": [],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            },
            "statDeltas": {"enhancements": []},
            "resolvedStats": {"intellect": 100},
            "simcOptions": {},
            "legality": {"status": "verified", "problemCodes": []},
            "sourceRefIds": ["evidence:item"],
            "evidenceClaimIds": ["sha256:old-claim"],
            "resolutionStages": ["base", "variant", "enhancements"],
            "problems": [],
        })
        old["constraints"] = {
            "embellishmentBuiltInUsed": 0,
            "embellishmentSelectedUsed": 0,
            "embellishmentUsed": 0,
            "embellishmentMax": 2,
            "slots": {
                "head": {
                    "socketCount": 1,
                    "socketRemaining": 1,
                    "canEnchant": False,
                    "hasSelectedEnchant": False,
                    "canEmbellish": False,
                    "hasSelectedEmbellishment": False,
                }
            }
        }
        old["resolvedGearSignature"] = gear_contracts.resolved_gear_signature(
            old["selectionSignature"],
            old["dependencyVector"],
        )
        self.seal_identity_claim(old)
        new = copy.deepcopy(old)
        new["dependencyVector"].update({
            "gearCatalogReleaseId": "gear-release:new",
            "gearCatalogRevision": "gear-release:new",
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
        })
        new["selectionSignature"] = "sha256:new-selection"
        new["resolvedGearSignature"] = "sha256:new"
        new["resolvedSlots"]["head"]["effectiveCapabilities"]["socketCount"] = 2
        new["resolvedSlots"]["head"]["effectiveCapabilities"]["allowedGemOptionIds"] = ["gem-b"]
        new["resolvedSlots"]["head"]["selectedOptions"]["gemOptionIds"] = ["gem-b"]
        new_intent = copy.deepcopy(old_intent)
        new_intent["authoredAgainst"]["gearCatalogRevision"] = "gear-release:new"
        new_intent["slots"]["head"]["gemOptionIds"] = ["gem-b"]
        new["selectionSignature"] = gear_contracts.selection_signature(
            new_intent,
            new_intent["eligibilityContext"],
        )
        new["resolvedGearSignature"] = gear_contracts.resolved_gear_signature(
            new["selectionSignature"],
            new["dependencyVector"],
        )
        new["resolvedSlots"]["head"]["statDeltas"]["enhancements"] = [{
            "optionId": "gem-b",
            "statDeltas": {},
        }]
        new["resolvedSlots"]["head"]["simcOptions"] = {"gem_id": "gem-b"}
        new["serializerInput"]["gearItems"][0]["simcOptions"] = {
            "gem_id": "gem-b"
        }
        new["resolvedSlots"]["head"]["sourceRefIds"].append("evidence:pg:option:gem-b")
        new["constraints"]["slots"]["head"]["socketCount"] = 2
        new["constraints"]["slots"]["head"]["socketRemaining"] = 1
        new["evidenceLedger"]["evidenceRecordsById"]["evidence:pg:option:gem-b"] = {
            "id": "evidence:pg:option:gem-b",
            "optionId": "gem-b",
            "sourceType": "postgres_gear_option",
            "sourceRevision": "2026-07-14T00:00:00Z",
        }
        self.seal_identity_claim(new)
        candidate_authority = self.candidate_authority(
            new["dependencyVector"],
            options={
                "gem-b": {
                    "optionId": "gem-b",
                    "optionType": "gem",
                    "statDeltas": {},
                    "simcOptions": {"gem_id": "gem-b"},
                    "sourceRefIds": ["evidence:pg:option:gem-b"],
                },
            },
            evidence_records=copy.deepcopy(
                new["evidenceLedger"]["evidenceRecordsById"]
            ),
        )
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "gear-release:old",
            "gearCatalogRevision": "gear-release:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "gear-release:old",
            "gearCatalogRevision": "gear-release:old",
        })

        def migration_equivalent(
            old_value,
            new_value,
            authority_value,
            candidate_intent_value=new_intent,
        ):
            def exact_resolve(selection_intent, authority_context):
                release_id = authority_context["dependencyVector"][
                    "gearCatalogReleaseId"
                ]
                if release_id == "gear-release:old":
                    self.assertEqual(selection_intent, old_intent)
                    return copy.deepcopy(old)
                if release_id == "gear-release:new":
                    return copy.deepcopy(new_value)
                raise AssertionError(f"unexpected release: {release_id}")

            with patch.object(
                gear_release_shadow.gear_resolver,
                "resolve",
                side_effect=exact_resolve,
            ):
                return gear_release_shadow._legacy_to_v2_socket_capacity_migration_equivalent(
                    old_value,
                    new_value,
                    transitional_gear_release_id="gear-release:old",
                    transitional_gear_catalog_revision="gear-release:old",
                    candidate_gear_release_id="gear-release:new",
                    transitional_authority_context=transitional_authority,
                    candidate_authority_context=authority_value,
                    transitional_intent=old_intent,
                    candidate_intent=candidate_intent_value,
                )

        self.assertTrue(migration_equivalent(old, new, candidate_authority))
        mismatched_candidate_intent = copy.deepcopy(new_intent)
        mismatched_candidate_intent["slots"]["head"]["gemOptionIds"] = []
        self.assertFalse(
            migration_equivalent(
                old,
                new,
                candidate_authority,
                mismatched_candidate_intent,
            )
        )

        def equivalent(
            old_value,
            new_value,
            authority_value=candidate_authority,
        ):
            return migration_equivalent(
                old_value,
                new_value,
                authority_value,
            )

        for source_type in (
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
        ):
            with self.subTest(real_option_source_type=source_type):
                sourced_new = copy.deepcopy(new)
                sourced_authority = copy.deepcopy(candidate_authority)
                sourced_new["evidenceLedger"]["evidenceRecordsById"][
                    "evidence:pg:option:gem-b"
                ]["sourceType"] = source_type
                sourced_authority["evidenceRecordsById"][
                    "evidence:pg:option:gem-b"
                ]["sourceType"] = source_type
                self.assertTrue(
                    equivalent(old, sourced_new, sourced_authority),
                    source_type,
                )

        forged_pair_new = copy.deepcopy(new)
        forged_pair_authority = copy.deepcopy(candidate_authority)
        forged_pair_new["evidenceLedger"]["evidenceRecordsById"][
            "evidence:pg:option:gem-b"
        ]["sourceType"] = "forged"
        forged_pair_authority["evidenceRecordsById"][
            "evidence:pg:option:gem-b"
        ]["sourceType"] = "forged"
        self.assertFalse(equivalent(old, forged_pair_new, forged_pair_authority))

        incomplete_profile_authority = copy.deepcopy(candidate_authority)
        incomplete_profile_authority["ruleParameters"]["requiredSlots"] = [
            "head",
            "neck",
        ]
        self.assertFalse(equivalent(old, new, incomplete_profile_authority))

        for contract_field, unknown_revision in (
            ("snapshot", "gear-resolved-snapshot-v999"),
            ("ledger", "gear-evidence-ledger-v999"),
        ):
            with self.subTest(unknown_contract=contract_field):
                invalid_old = copy.deepcopy(old)
                invalid_new = copy.deepcopy(new)
                if contract_field == "snapshot":
                    invalid_old["contractRevision"] = unknown_revision
                    invalid_new["contractRevision"] = unknown_revision
                else:
                    invalid_old["evidenceLedger"]["contractRevision"] = unknown_revision
                    invalid_new["evidenceLedger"]["contractRevision"] = unknown_revision
                self.assertFalse(equivalent(invalid_old, invalid_new))

        unlinked_old = copy.deepcopy(old)
        unlinked_new = copy.deepcopy(new)
        unlinked_old["resolvedSlots"]["head"]["evidenceClaimIds"] = []
        unlinked_new["resolvedSlots"]["head"]["evidenceClaimIds"] = []
        self.assertFalse(equivalent(unlinked_old, unlinked_new))

        blocked_rules_old = copy.deepcopy(old)
        blocked_rules_new = copy.deepcopy(new)
        for value in (blocked_rules_old, blocked_rules_new):
            value["ruleResults"][0]["status"] = "blocked"
            value["ruleResults"][0]["problems"] = [{"code": "BAD_RULE"}]
        self.assertFalse(equivalent(blocked_rules_old, blocked_rules_new))

        incomplete_old = copy.deepcopy(old)
        incomplete_new = copy.deepcopy(new)
        for value in (incomplete_old, incomplete_new):
            ledger = value["evidenceLedger"]
            identity_claims = [
                claim
                for claim in ledger["claims"]
                if claim["claimKey"] == "slot:head:identity_options"
            ]
            ledger["claims"] = identity_claims
            ledger["claimGroups"] = {
                group: [identity_claims[0]["claimId"]]
                if group == "identity_options"
                else []
                for group in gear_evidence_ledger.CLAIM_GROUPS
            }
            value["resolvedSlots"]["head"]["evidenceClaimIds"] = [
                identity_claims[0]["claimId"]
            ]
        self.assertFalse(equivalent(incomplete_old, incomplete_new))

        required_dependency_fields = (
            "seasonRevision",
            "gearCatalogReleaseId",
            "gearCatalogRevision",
            "gearRuleRevision",
            "resolverContractRevision",
            "serializerRevision",
            "simcRuntimeRevision",
            "statPolicyRevision",
            "selectionSchemaRevision",
            "capabilityRevision",
        )
        for dependency_field in required_dependency_fields:
            with self.subTest(missing_dependency=dependency_field):
                invalid_old = copy.deepcopy(old)
                invalid_new = copy.deepcopy(new)
                invalid_old["dependencyVector"].pop(dependency_field)
                invalid_new["dependencyVector"].pop(dependency_field)
                invalid_old["resolvedGearSignature"] = (
                    gear_contracts.resolved_gear_signature(
                        invalid_old["selectionSignature"],
                        invalid_old["dependencyVector"],
                    )
                )
                invalid_new["resolvedGearSignature"] = (
                    gear_contracts.resolved_gear_signature(
                        invalid_new["selectionSignature"],
                        invalid_new["dependencyVector"],
                    )
                )
                self.reseal_existing_claims(invalid_old)
                self.reseal_existing_claims(invalid_new)
                invalid_authority = copy.deepcopy(candidate_authority)
                invalid_authority["dependencyVector"] = copy.deepcopy(
                    invalid_new["dependencyVector"]
                )
                self.assertFalse(
                    equivalent(invalid_old, invalid_new, invalid_authority)
                )

        def remove_selected_option_evidence(value):
            value["evidenceLedger"]["evidenceRecordsById"].pop(
                "evidence:pg:option:gem-b",
                None,
            )

        def forge_selected_option_evidence(value):
            value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-b"
            ]["sourceType"] = "forged"

        def remove_selected_option_slot_source(value):
            value["resolvedSlots"]["head"]["sourceRefIds"].remove(
                "evidence:pg:option:gem-b"
            )

        def remove_selected_option_claim_source(value):
            value["evidenceLedger"]["claims"][0]["sourceRefIds"].remove(
                "evidence:pg:option:gem-b"
            )

        def add_unexpected_claim_source(value):
            value["evidenceLedger"]["claims"][0]["sourceRefIds"].append(
                "evidence:unexpected",
            )
            value["evidenceLedger"]["evidenceRecordsById"]["evidence:unexpected"] = {
                "id": "evidence:unexpected",
                "sourceType": "postgres_gear_item",
            }

        def rebuild_identity_claim(value, *, claim_value=None, rule_revision=None):
            old_claim = value["evidenceLedger"]["claims"][0]
            rebuilt = gear_evidence_ledger.evidence_claim(
                "identity_options",
                "slot:head:identity_options",
                old_claim["value"] if claim_value is None else claim_value,
                status="verified",
                source_ref_ids=old_claim["sourceRefIds"],
                rule_revision=(
                    old_claim["ruleRevision"]
                    if rule_revision is None
                    else rule_revision
                ),
                resolved_signature=value["resolvedGearSignature"],
                dependency_vector=value["dependencyVector"],
            )
            value["evidenceLedger"]["claims"] = [rebuilt]
            value["evidenceLedger"]["claimGroups"]["identity_options"] = [
                rebuilt["claimId"]
            ]
            value["resolvedSlots"]["head"]["evidenceClaimIds"] = [
                rebuilt["claimId"]
            ]

        def forge_identity_claim_value(value):
            rebuild_identity_claim(value, claim_value={"forged": True})

        def forge_identity_claim_rule(value):
            rebuild_identity_claim(value, rule_revision="forged-rule")

        def add_cancelling_gem_deltas(value):
            selected = value["resolvedSlots"]["head"]["selectedOptions"][
                "gemOptionIds"
            ]
            selected.append("gem-c")
            value["resolvedSlots"]["head"]["effectiveCapabilities"][
                "allowedGemOptionIds"
            ].append("gem-c")
            value["resolvedSlots"]["head"]["statDeltas"]["enhancements"] = [
                {"optionId": "gem-b", "statDeltas": {"intellect": 100}},
                {"optionId": "gem-c", "statDeltas": {"intellect": -100}},
            ]
            value["resolvedSlots"]["head"]["sourceRefIds"].append(
                "evidence:pg:option:gem-c"
            )
            value["constraints"]["slots"]["head"]["socketRemaining"] = 0
            value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-c"
            ] = {
                "id": "evidence:pg:option:gem-c",
                "optionId": "gem-c",
                "sourceType": "postgres_gear_option",
                "sourceRevision": "2026-07-14T00:00:00Z",
            }
            self.seal_identity_claim(value)

        def clear_resolved_signature(value):
            value["resolvedGearSignature"] = ""
            self.seal_identity_claim(value)

        def forge_resolved_signature(value):
            value["resolvedGearSignature"] = "sha256:forged-but-nonempty"
            self.seal_identity_claim(value)

        for mutate in (
            lambda value: value["resolvedSlots"]["head"]["effectiveCapabilities"].update(socketCount=1),
            lambda value: value["constraints"]["slots"]["head"].update(socketCount=3),
            lambda value: value["resolvedSlots"]["head"].update(itemId="different-item"),
            lambda value: value["resolvedSlots"]["head"]["selectedOptions"].update(craftedOptionId="crafted-b"),
            lambda value: value["resolvedSlots"]["head"].update(resolutionStages=["forged-stage"]),
            lambda value: value["resolvedSlots"]["head"]["sourceRefIds"].append("evidence:unexpected"),
            lambda value: value.update(aggregateLegality={"status": "blocked"}),
            lambda value: value["dependencyVector"].update(seasonRevision="season-18"),
            lambda value: value["dependencyVector"].update(serializerRevision="serializer-v2"),
            lambda value: value["constraints"]["slots"]["head"].update(socketRemaining=2),
            lambda value: value["resolvedSlots"]["head"]["statDeltas"]["enhancements"].append({
                "optionId": "forged-option",
                "statDeltas": {},
            }),
            remove_selected_option_evidence,
            forge_selected_option_evidence,
            remove_selected_option_slot_source,
            remove_selected_option_claim_source,
            lambda value: value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-b"
            ].update(status="blocked", problems=["forged"]),
            lambda value: value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-b"
            ].update(sourceRevision="forged-revision"),
            lambda value: value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-b"
            ].update(sourceRevision="2030-01-01T00:00:00Z"),
            lambda value: value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-b"
            ].update(sourceType="blizzard_game_data_api"),
            lambda value: value["evidenceLedger"]["evidenceRecordsById"][
                "evidence:pg:option:gem-b"
            ].update(extra="forged"),
            lambda value: value["evidenceLedger"]["claimGroups"].update(
                identity_options=[]
            ),
            lambda value: value["evidenceLedger"]["claimGroups"].pop(
                "identity_options"
            ),
            lambda value: value["dependencyVector"].pop("gearCatalogReleaseId"),
            lambda value: value["dependencyVector"].pop("gearCatalogRevision"),
            lambda value: value["dependencyVector"].update(
                gearCatalogReleaseId="gear-release:wrong"
            ),
            lambda value: value["dependencyVector"].update(
                gearCatalogRevision="gear-release:wrong"
            ),
            forge_identity_claim_value,
            forge_identity_claim_rule,
            add_cancelling_gem_deltas,
            clear_resolved_signature,
            forge_resolved_signature,
            lambda value: value.update(selectionSignature=""),
            lambda value: value["resolvedSlots"]["head"]["effectiveCapabilities"]["allowedGemOptionIds"].append("gem-extra"),
            lambda value: value["resolvedSlots"]["head"]["statDeltas"]["enhancements"][0].update(
                statDeltas={"intellect": 999},
            ),
            add_unexpected_claim_source,
        ):
            with self.subTest(mutate=mutate):
                invalid = copy.deepcopy(new)
                mutate(invalid)
                self.assertFalse(
                    migration_equivalent(
                        old,
                        invalid,
                        candidate_authority,
                    )
                )

    def test_non_enhancement_migration_scope_preserves_season_revision(self):
        old = self.intent()
        new_release = copy.deepcopy(old)
        new_release["authoredAgainst"]["gearCatalogRevision"] = "gear-release:new"
        self.assertEqual(
            gear_release_shadow._non_enhancement_selection_projection(old),
            gear_release_shadow._non_enhancement_selection_projection(new_release),
        )

        new_season = copy.deepcopy(new_release)
        new_season["authoredAgainst"]["seasonRevision"] = "season-18"
        self.assertNotEqual(
            gear_release_shadow._non_enhancement_selection_projection(old),
            gear_release_shadow._non_enhancement_selection_projection(new_season),
        )

    def test_profile_migration_rejects_empty_profile_with_encoded_talents(self):
        outcome = {
            "httpStatus": 200,
            "status": "blocked",
            "problemCodes": ["GEAR_PROFILE_NOT_READY"],
            "data": {
                "profile": "",
                "talentEncoding": {
                    "status": "external",
                    "source": "talents",
                    "lines": ["talents=valid"],
                },
                "profileReadiness": {
                    "status": "blocked",
                    "simcReady": False,
                },
            },
        }
        self.assertFalse(
            gear_release_shadow._profile_outcomes_allow_migration(
                outcome,
                copy.deepcopy(outcome),
            )
        )

    def test_current_v2_radiant_jewelbinder_capacity_migration_requires_verified_empty_zero_to_one(self):
        old_intent = self.intent()
        old_intent["authoredAgainst"]["gearCatalogRevision"] = "gear-release:old"
        new_intent = copy.deepcopy(old_intent)
        new_intent["authoredAgainst"]["gearCatalogRevision"] = "gear-release:new"
        dependencies = {
            "seasonRevision": "season-17",
            "gearCatalogReleaseId": "gear-release:old",
            "gearCatalogRevision": "gear-release:old",
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "serializerRevision": "serializer-v1",
            "simcRuntimeRevision": "simc-r1",
            "statPolicyRevision": "stat-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
        }
        old = self.snapshot(old_intent, "sha256:old")
        old["dependencyVector"] = copy.deepcopy(dependencies)
        old["resolvedSlots"]["head"].update({
            "effectiveCapabilities": {"socketCount": 0},
            "selectedOptions": {"gemOptionIds": []},
        })
        old["constraints"] = {
            "slots": {"head": {"socketCount": 0, "socketRemaining": 0}}
        }
        new = copy.deepcopy(old)
        new["dependencyVector"].update({
            "gearCatalogReleaseId": "gear-release:new",
            "gearCatalogRevision": "gear-release:new",
        })
        new["resolvedGearSignature"] = "sha256:new"
        new["resolvedSlots"]["head"]["effectiveCapabilities"]["socketCount"] = 1
        new["constraints"]["slots"]["head"].update({
            "socketCount": 1,
            "socketRemaining": 1,
        })
        old_authority = self.candidate_authority(
            dependencies,
            options={},
            evidence_records={"evidence:item": {"id": "evidence:item"}},
        )
        new_dependencies = copy.deepcopy(dependencies)
        new_dependencies.update({
            "gearCatalogReleaseId": "gear-release:new",
            "gearCatalogRevision": "gear-release:new",
        })
        new_authority = self.candidate_authority(
            new_dependencies,
            options={},
            evidence_records={"evidence:item": {"id": "evidence:item"}},
        )
        new_authority["itemsById"]["item-a"][
            "radiantJewelbinderSocketEligibility"
        ] = True

        self.assertTrue(
            gear_release_shadow._current_v2_radiant_jewelbinder_capacity_migration_equivalent(
                old,
                new,
                transitional_authority_context=old_authority,
                candidate_authority_context=new_authority,
                transitional_intent=old_intent,
                candidate_intent=new_intent,
            )
        )

        without_proof = copy.deepcopy(new_authority)
        without_proof["itemsById"]["item-a"].pop(
            "radiantJewelbinderSocketEligibility"
        )
        self.assertFalse(
            gear_release_shadow._current_v2_radiant_jewelbinder_capacity_migration_equivalent(
                old,
                new,
                transitional_authority_context=old_authority,
                candidate_authority_context=without_proof,
                transitional_intent=old_intent,
                candidate_intent=new_intent,
            )
        )

    def test_shadow_allows_only_verified_current_v2_radiant_jewelbinder_capacity_migration(self):
        candidate = self.candidate_row()
        active_intent = copy.deepcopy(candidate["selectionIntent"])
        active_intent["authoredAgainst"]["gearCatalogRevision"] = "gear-release:old"
        active_winner = copy.deepcopy(candidate)
        active_winner["selectionIntent"] = active_intent
        dependencies = {
            "seasonRevision": "season-17",
            "gearCatalogReleaseId": "gear-release:old",
            "gearCatalogRevision": "gear-release:old",
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
            "serializerRevision": "serializer-v1",
            "simcRuntimeRevision": "simc-r1",
            "statPolicyRevision": "stat-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
        }
        old_snapshot = self.snapshot(active_intent, "sha256:old")
        old_snapshot["dependencyVector"] = copy.deepcopy(dependencies)
        old_snapshot["resolvedSlots"]["head"].update({
            "effectiveCapabilities": {"socketCount": 0},
            "selectedOptions": {"gemOptionIds": []},
        })
        old_snapshot["constraints"] = {
            "slots": {"head": {"socketCount": 0, "socketRemaining": 0}}
        }
        candidate_snapshot = copy.deepcopy(old_snapshot)
        candidate_dependencies = copy.deepcopy(dependencies)
        candidate_dependencies.update({
            "gearCatalogReleaseId": "gear-release:sha256:target",
            "gearCatalogRevision": "gear-release:sha256:target",
        })
        candidate_snapshot["dependencyVector"] = candidate_dependencies
        candidate_snapshot["resolvedGearSignature"] = "sha256:candidate"
        candidate_snapshot["resolvedSlots"]["head"]["effectiveCapabilities"][
            "socketCount"
        ] = 1
        candidate_snapshot["constraints"]["slots"]["head"].update({
            "socketCount": 1,
            "socketRemaining": 1,
        })
        candidate["resolvedGearSignature"] = "sha256:candidate"
        candidate["semanticGearSignature"] = gear_release.semantic_gear_signature(
            candidate["selectionIntent"],
            candidate_snapshot,
        )
        active_winner["semanticGearSignature"] = gear_release.semantic_gear_signature(
            active_intent,
            old_snapshot,
        )
        candidate_authority = self.candidate_authority(
            candidate_dependencies,
            options={},
            evidence_records={"evidence:item": {"id": "evidence:item"}},
        )
        candidate_authority["itemsById"]["item-a"][
            "radiantJewelbinderSocketEligibility"
        ] = True
        transitional_authority = self.candidate_authority(
            dependencies,
            options={},
            evidence_records={"evidence:item": {"id": "evidence:item"}},
        )
        store = FakeShadowStore(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            candidate_authority_context=candidate_authority,
            transitional_authority_context=transitional_authority,
        )
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": True,
            "authoredAgainst": {
                "seasonRevision": "season-17",
                "gearCatalogRevision": "gear-release:old",
            },
            "dependencyRevisions": {
                "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
            },
        }
        store.get_active_community_release = lambda: {
            "formalActiveManifest": True,
            "pointerGeneration": 1,
            "manifestRevision": "manifest:active",
            "gearRelease": {
                "releaseId": "gear-release:old",
                "dependencyRevisions": {
                    "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
                },
            },
            "communityRelease": {"releaseId": "community-release:old"},
            "winners": [copy.deepcopy(active_winner)],
        }
        profile = self.resolved_profile_envelope("mage=verified")

        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": old_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": candidate_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                expect_formal_active=True,
            )

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(
            result["specResults"][0]["enhancementMigrationParity"],
            {
                "status": "pass",
                "mode": "current_v2_radiant_jewelbinder_capacity",
            },
        )

    def test_shadow_allows_narrow_legacy_to_v2_socket_capacity_migration_only(self):

        gemmed = copy.deepcopy(new)
        gemmed["resolvedSlots"]["head"]["selectedOptions"]["gemOptionIds"] = [
            "gem-a"
        ]
        self.assertFalse(
            gear_release_shadow._current_v2_radiant_jewelbinder_capacity_migration_equivalent(
                old,
                gemmed,
                transitional_authority_context=old_authority,
                candidate_authority_context=new_authority,
                transitional_intent=old_intent,
                candidate_intent=new_intent,
            )
        )

    def test_shadow_allows_narrow_legacy_to_v2_socket_capacity_migration_only(self):
        candidate = self.candidate_row()
        candidate_snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        candidate_snapshot.update({
            "contractRevision": "gear-resolved-snapshot-v1",
            "dependencyVector": {
                "seasonRevision": "season-17",
                "gearCatalogReleaseId": "gear-release:sha256:target",
                "gearCatalogRevision": "gear-release:sha256:target",
                "gearRuleRevision": "gear-rule-matrix-v1",
                "resolverContractRevision": "gear-resolver-contract-v1",
                "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
                "serializerRevision": "serializer-v1",
                "simcRuntimeRevision": "simc-r1",
                "statPolicyRevision": "stat-policy-v1",
                "selectionSchemaRevision": "selection-intent-v1",
            },
            "selectionSignature": gear_contracts.selection_signature(
                candidate["selectionIntent"],
                candidate["selectionIntent"]["eligibilityContext"],
            ),
            "ruleResults": self.verified_rule_results(),
            "evidenceLedger": {
                "contractRevision": "gear-evidence-ledger-v1",
                "claims": [{
                    "claimId": "sha256:head-claim",
                    "claimKey": "slot:head:identity_options",
                    "group": "identity_options",
                    "status": "verified",
                    "dependsOn": [],
                    "sourceRefIds": ["evidence:item"],
                    "problems": [],
                }],
                "claimGroups": {"identity_options": ["sha256:head-claim"]},
                "evidenceRecordsById": {
                    "evidence:item": {
                        "id": "evidence:item",
                        "sourceType": "postgres_gear_item",
                    }
                },
                "problems": [],
            },
            "problems": [],
        })
        candidate_snapshot["resolvedSlots"]["head"].update({
            "effectiveCapabilities": {
                "socketCount": 2,
                "allowedGemOptionIds": [],
                "allowedEnchantOptionIds": [],
                "allowedEmbellishmentOptionIds": [],
                "allowedCraftedOptionIds": [],
                "allowedCatalystOptionIds": [],
            },
            "selectedOptions": {
                "gemOptionIds": [],
                "enchantOptionId": "",
                "embellishmentOptionId": "",
                "craftedOptionId": "",
                "catalystOptionId": "",
            },
            "statDeltas": {"enhancements": []},
            "resolvedStats": {"intellect": 100},
            "simcOptions": {},
            "legality": {"status": "verified", "problemCodes": []},
            "sourceRefIds": ["evidence:item"],
            "evidenceClaimIds": ["sha256:head-claim"],
            "resolutionStages": ["base", "variant", "enhancements"],
            "problems": [],
        })
        candidate_snapshot["constraints"] = {
            "embellishmentBuiltInUsed": 0,
            "embellishmentSelectedUsed": 0,
            "embellishmentUsed": 0,
            "embellishmentMax": 2,
            "slots": {
                "head": {
                    "socketCount": 2,
                    "socketRemaining": 2,
                    "canEnchant": False,
                    "hasSelectedEnchant": False,
                    "canEmbellish": False,
                    "hasSelectedEmbellishment": False,
                }
            }
        }
        candidate_snapshot["resolvedGearSignature"] = (
            gear_contracts.resolved_gear_signature(
                candidate_snapshot["selectionSignature"],
                candidate_snapshot["dependencyVector"],
            )
        )
        self.seal_identity_claim(candidate_snapshot)
        candidate_authority = self.candidate_authority(
            candidate_snapshot["dependencyVector"],
            options={},
            evidence_records=copy.deepcopy(
                candidate_snapshot["evidenceLedger"]["evidenceRecordsById"]
            ),
        )
        candidate["resolvedGearSignature"] = candidate_snapshot["resolvedGearSignature"]
        candidate["semanticGearSignature"] = gear_release.semantic_gear_signature(
            candidate["selectionIntent"],
            candidate_snapshot,
        )
        transitional_intent = copy.deepcopy(candidate["selectionIntent"])
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = "compatibility-pg:old"
        old_snapshot = copy.deepcopy(candidate_snapshot)
        old_snapshot["resolvedGearSignature"] = "sha256:old"
        old_snapshot["selectionSignature"] = gear_contracts.selection_signature(
            transitional_intent,
            transitional_intent["eligibilityContext"],
        )
        old_snapshot["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        old_snapshot["resolvedGearSignature"] = gear_contracts.resolved_gear_signature(
            old_snapshot["selectionSignature"],
            old_snapshot["dependencyVector"],
        )
        old_snapshot["resolvedSlots"]["head"]["effectiveCapabilities"]["socketCount"] = 1
        old_snapshot["constraints"]["slots"]["head"]["socketCount"] = 1
        old_snapshot["constraints"]["slots"]["head"]["socketRemaining"] = 1
        self.seal_identity_claim(old_snapshot)
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        profile = self.resolved_profile_envelope("mage=socket-capacity")

        def run(active_capability_revision, profile_response=(200, profile)):
            store = FakeShadowStore(
                candidate,
                capability_revision=gear_socket_authority.CAPABILITY_REVISION,
                candidate_authority_context=candidate_authority,
                transitional_authority_context=transitional_authority,
            )
            store.get_gear_resolver_context = lambda _runtime: {
                "formalActiveManifest": True,
                "authoredAgainst": {
                    "seasonRevision": "season-17",
                    "gearCatalogRevision": "compatibility-pg:old",
                },
                "dependencyRevisions": {
                    "capabilityRevision": active_capability_revision,
                },
            }
            def exact_resolve(selection_intent, authority_context):
                release_id = authority_context["dependencyVector"][
                    "gearCatalogReleaseId"
                ]
                if release_id == "compatibility-pg:old":
                    self.assertEqual(selection_intent, transitional_intent)
                    return copy.deepcopy(old_snapshot)
                if release_id == "gear-release:sha256:target":
                    self.assertEqual(
                        selection_intent,
                        candidate["selectionIntent"],
                    )
                    return copy.deepcopy(candidate_snapshot)
                raise AssertionError(f"unexpected release: {release_id}")

            with patch.object(
                gear_release_shadow.gear_runtime,
                "resolve_selection_intent",
                return_value=(200, {
                    "status": "resolved",
                    "data": old_snapshot,
                    "problems": [],
                }),
            ), patch.object(
                gear_release_shadow.gear_runtime,
                "resolve_candidate_selection_intent",
                return_value=(200, {
                    "status": "resolved",
                    "data": candidate_snapshot,
                    "problems": [],
                }),
            ), patch.object(
                gear_release_shadow.gear_runtime,
                "build_profile_from_selection_intent",
                return_value=profile_response,
            ), patch.object(
                gear_release_shadow.gear_runtime,
                "build_candidate_profile_from_selection_intent",
                return_value=profile_response,
            ), patch.object(
                gear_release_shadow.gear_resolver,
                "resolve",
                side_effect=exact_resolve,
            ):
                return gear_release_shadow.run_release_shadow(
                    store,
                    expected_specs=[("mage", "arcane")],
                    gear_release_id="gear-release:sha256:target",
                    community_release_id="community-release:sha256:target",
                    simc_runtime_revision="simc-r1",
                    expect_formal_active=True,
                )

        legacy_to_v2 = run(gear_socket_authority.LEGACY_CAPABILITY_REVISION)
        self.assertEqual(legacy_to_v2["status"], "pass", legacy_to_v2)
        self.assertEqual(
            legacy_to_v2["report"]["diffs"][0]["classification"],
            "expected_enhancement_migration",
        )

        v2_to_v2 = run(gear_socket_authority.CAPABILITY_REVISION)
        self.assertEqual(v2_to_v2["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in v2_to_v2["blockers"]},
        )

        blocked_profile = run(
            gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            profile_response=(422, {
                "status": "blocked",
                "data": {},
                "problems": [{"code": "PROFILE_BLOCKED"}],
            }),
        )
        self.assertEqual(blocked_profile["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in blocked_profile["blockers"]},
        )

        forged_resolved_profile = copy.deepcopy(profile)
        forged_resolved_profile["problems"] = [{"code": "SERIALIZER_BROKEN"}]
        forged_resolved = run(
            gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            profile_response=(200, forged_resolved_profile),
        )
        self.assertEqual(forged_resolved["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in forged_resolved["blockers"]},
        )

        profile_not_ready = run(
            gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            profile_response=(200, {
                "status": "blocked",
                "data": {
                    "profile": "",
                    "talentEncoding": {
                        "status": "failed",
                        "source": "none",
                        "schemaRevision": "websim-talent-rules-v1",
                        "errors": ["no WebSim talent nodes selected"],
                        "warnings": [],
                        "lines": [],
                        "selectedCounts": {
                            "class": 0,
                            "spec": 0,
                            "hero": 0,
                        },
                    },
                    "profileReadiness": {
                        "status": "blocked",
                        "simcReady": False,
                    },
                },
                "problems": [{"code": "GEAR_PROFILE_NOT_READY"}],
            }),
        )
        self.assertEqual(profile_not_ready["status"], "pass", profile_not_ready)
        self.assertEqual(
            profile_not_ready["report"]["diffs"][0]["classification"],
            "expected_enhancement_migration",
        )

        encoded_but_empty_profile = run(
            gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            profile_response=(200, {
                "status": "blocked",
                "data": {
                    "profile": "",
                    "talentEncoding": copy.deepcopy(
                        profile["data"]["talentEncoding"]
                    ),
                    "profileReadiness": {
                        "status": "blocked",
                        "simcReady": False,
                    },
                },
                "problems": [{"code": "GEAR_PROFILE_NOT_READY"}],
            }),
        )
        self.assertEqual(encoded_but_empty_profile["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {
                problem["code"]
                for problem in encoded_but_empty_profile["blockers"]
            },
        )

    def test_internal_shadow_proves_exact_mage_enhancement_migration_and_ninth_gem_rejection(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        intent = copy.deepcopy(fixture["intent"])
        candidate_snapshot = gear_resolver.resolve(intent, fixture["authorityContext"])
        legacy_intent = copy.deepcopy(intent)
        legacy_intent["authoredAgainst"]["gearCatalogRevision"] = (
            "compatibility-pg:old"
        )
        for selection in legacy_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
        legacy_authority = copy.deepcopy(fixture["authorityContext"])
        legacy_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        legacy_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        for item in legacy_authority["itemsById"].values():
            capabilities = item.get("baseCapabilities") or {}
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
            ):
                item[field] = []
                capabilities[field] = []
        transitional_snapshot = gear_resolver.resolve(
            legacy_intent,
            legacy_authority,
        )
        self.assertNotEqual(
            transitional_snapshot["resolvedSlots"]["head"]["statDeltas"]["enhancements"],
            candidate_snapshot["resolvedSlots"]["head"]["statDeltas"]["enhancements"],
        )
        candidate = {
            "templateId": "observed_profile_mage_frost",
            "classKey": "mage",
            "specKey": "frost",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/reference-mage",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:mage:frost:reference",
            "gearHash": "gear:mage:frost:reference",
            "selectionIntent": intent,
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                intent,
                candidate_snapshot,
            ),
            "problems": [],
        }
        store = FakeShadowStore(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
            candidate_authority_context=fixture["authorityContext"],
            transitional_authority_context=legacy_authority,
            exact_authority_expectations=[
                (legacy_intent, "compatibility-pg:old"),
                (intent, "gear-release-17"),
            ],
        )
        store.get_gear_resolver_context = lambda _runtime: {
            "formalActiveManifest": False,
            "authoredAgainst": {
                "seasonRevision": intent["authoredAgainst"]["seasonRevision"],
                "gearCatalogRevision": "compatibility-pg:old",
            },
            "dependencyRevisions": {
                "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
            },
        }
        candidate_calls = []

        def candidate_resolve(selection_intent, **_kwargs):
            candidate_calls.append(copy.deepcopy(selection_intent))
            if len(candidate_calls) == 1:
                return 200, {
                    "status": "resolved",
                    "data": candidate_snapshot,
                    "problems": [],
                }
            return 422, {
                "status": "blocked",
                "data": {},
                "problems": [{"code": "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED"}],
            }

        profile = self.resolved_profile_envelope(
            "mage=reference\nhead=...,gem_id=240916"
        )
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": transitional_snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            side_effect=candidate_resolve,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "frost")],
                gear_release_id="gear-release-17",
                community_release_id="community-release:sha256:reference",
                simc_runtime_revision="simc-v1",
            )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(store.exact_authority_expectations, [])
        exact_authority_calls = [
            call for call in store.calls if call[0] == "exact-authority"
        ]
        self.assertEqual(
            [(call[1], call[2]) for call in exact_authority_calls],
            [
                (legacy_intent, "compatibility-pg:old"),
                (intent, "gear-release-17"),
            ],
        )
        self.assertEqual(
            [call for call in store.calls if call[0] == "active-pair"],
            [("active-pair",), ("active-pair",)],
        )
        self.assertEqual(
            result["report"]["diffs"][0]["classification"],
            "expected_enhancement_migration",
        )
        self.assertEqual(result["referenceProof"]["status"], "pass")
        self.assertEqual(result["referenceProof"]["gearReleaseId"], "gear-release-17")
        self.assertEqual(
            result["referenceProof"]["communityReleaseId"],
            "community-release:sha256:reference",
        )
        self.assertEqual(result["referenceProof"]["socketVector"], [1, 2, 1, 1, 2, 1])
        self.assertEqual(result["referenceProof"]["gems"], {"used": 8, "max": 8})
        self.assertEqual(result["referenceProof"]["enchants"], {"used": 6, "max": 8})
        self.assertEqual(result["referenceProof"]["embellishments"], {"used": 2, "max": 2})
        self.assertEqual(len(candidate_calls), 2)
        self.assertEqual(
            sum(
                len(selection["gemOptionIds"])
                for selection in candidate_calls[1]["slots"].values()
            ),
            9,
        )

    def test_real_mage_capacity_migration_requires_complete_candidate_authority(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        candidate_intent = copy.deepcopy(fixture["intent"])
        candidate_authority = copy.deepcopy(fixture["authorityContext"])
        candidate_snapshot = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )
        transitional_intent = copy.deepcopy(candidate_intent)
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = (
            "compatibility-pg:old"
        )
        for selection in transitional_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
        legacy_finger_gem = candidate_intent["slots"]["finger1"][
            "gemOptionIds"
        ][:1]
        transitional_intent["slots"]["finger1"]["gemOptionIds"] = list(
            legacy_finger_gem
        )
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        finger_selection = transitional_intent["slots"]["finger1"]
        transitional_authority["variantsByKey"][
            finger_selection["variantKey"]
        ]["capabilityOverrides"]["socketCount"] = 1
        for item in transitional_authority["itemsById"].values():
            capabilities = item.get("baseCapabilities") or {}
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
            ):
                item[field] = []
                capabilities[field] = []
        finger_item = transitional_authority["itemsById"][
            finger_selection["itemId"]
        ]
        finger_item["allowedGemOptionIds"] = list(legacy_finger_gem)
        finger_item["baseCapabilities"]["allowedGemOptionIds"] = list(
            legacy_finger_gem
        )
        transitional_snapshot = gear_resolver.resolve(
            transitional_intent,
            transitional_authority,
        )
        arguments = {
            "transitional_gear_release_id": "compatibility-pg:old",
            "transitional_gear_catalog_revision": "compatibility-pg:old",
            "candidate_gear_release_id": "gear-release-17",
            "transitional_authority_context": transitional_authority,
            "transitional_intent": transitional_intent,
            "candidate_intent": candidate_intent,
        }
        self.assertTrue(
            gear_release_shadow._legacy_to_v2_socket_capacity_migration_equivalent(
                transitional_snapshot,
                candidate_snapshot,
                candidate_authority_context=candidate_authority,
                **arguments,
            )
        )

        incomplete_authority = copy.deepcopy(candidate_authority)
        incomplete_authority["itemsById"].pop(finger_selection["itemId"])
        incomplete_authority["variantsByKey"].pop(
            finger_selection["variantKey"]
        )
        for source_ref in candidate_snapshot["resolvedSlots"]["finger1"][
            "sourceRefIds"
        ]:
            if not source_ref.startswith("evidence:pg:option:"):
                incomplete_authority["evidenceRecordsById"].pop(
                    source_ref,
                    None,
                )
        self.assertFalse(
            gear_release_shadow._legacy_to_v2_socket_capacity_migration_equivalent(
                transitional_snapshot,
                candidate_snapshot,
                candidate_authority_context=incomplete_authority,
                **arguments,
            )
        )

    def test_real_capacity_migration_rejects_same_crafted_option_stat_delta_change(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        candidate_intent = copy.deepcopy(fixture["intent"])
        candidate_authority = copy.deepcopy(fixture["authorityContext"])
        finger_selection = candidate_intent["slots"]["finger1"]
        finger_gems = list(finger_selection["gemOptionIds"])
        crafted_option_id = "crafted-mastery"
        crafted_evidence_id = f"evidence:pg:option:{crafted_option_id}"

        for selection in candidate_intent["slots"].values():
            selection["gemOptionIds"] = []
            selection["enchantOptionId"] = ""
            selection["embellishmentOptionId"] = ""
            selection["craftedOptionId"] = ""
            selection["catalystOptionId"] = ""
        finger_selection["gemOptionIds"] = finger_gems
        finger_selection["craftedOptionId"] = crafted_option_id
        for item in candidate_authority["itemsById"].values():
            base_capabilities = item.get("baseCapabilities") or {}
            for field in (
                "allowedGemOptionIds",
                "allowedEnchantOptionIds",
                "allowedEmbellishmentOptionIds",
            ):
                item[field] = []
                base_capabilities[field] = []
        finger_item = candidate_authority["itemsById"][
            finger_selection["itemId"]
        ]
        finger_item["allowedGemOptionIds"] = list(finger_gems)
        finger_item["baseCapabilities"]["allowedGemOptionIds"] = list(
            finger_gems
        )
        finger_item["allowedCraftedOptionIds"] = [crafted_option_id]
        finger_item["baseCapabilities"]["allowedCraftedOptionIds"] = [
            crafted_option_id
        ]
        candidate_authority["optionsById"][crafted_option_id] = {
            "optionId": crafted_option_id,
            "optionType": "crafted",
            "statDeltas": {"mastery": 20},
            "simcOptions": {"crafted_stats": "mastery"},
            "sourceRefIds": [crafted_evidence_id],
        }
        candidate_authority["evidenceRecordsById"][crafted_evidence_id] = {
            "id": crafted_evidence_id,
            "optionId": crafted_option_id,
            "sourceType": "postgres_gear_option",
            "sourceRevision": "2026-07-14T00:00:00+00:00",
        }
        candidate_snapshot = gear_resolver.resolve(
            candidate_intent,
            candidate_authority,
        )
        self.assertEqual(candidate_snapshot["status"], "verified")
        self.assertEqual(
            candidate_snapshot["resolvedSlots"]["finger1"]["resolvedStats"][
                "mastery"
            ],
            20,
        )
        self.assertEqual(
            gear_resolver.resolve(candidate_intent, candidate_authority),
            candidate_snapshot,
        )

        transitional_intent = copy.deepcopy(candidate_intent)
        transitional_intent["authoredAgainst"]["gearCatalogRevision"] = (
            "compatibility-pg:old"
        )
        transitional_intent["slots"]["finger1"]["gemOptionIds"] = finger_gems[:1]
        transitional_authority = copy.deepcopy(candidate_authority)
        transitional_authority["dependencyVector"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
            "capabilityRevision": gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        })
        transitional_authority["manifest"].update({
            "gearCatalogReleaseId": "compatibility-pg:old",
            "gearCatalogRevision": "compatibility-pg:old",
        })
        transitional_authority["variantsByKey"][
            finger_selection["variantKey"]
        ]["capabilityOverrides"]["socketCount"] = 1
        transitional_finger_item = transitional_authority["itemsById"][
            finger_selection["itemId"]
        ]
        transitional_finger_item["allowedGemOptionIds"] = finger_gems[:1]
        transitional_finger_item["baseCapabilities"]["allowedGemOptionIds"] = (
            finger_gems[:1]
        )
        transitional_authority["optionsById"][crafted_option_id]["statDeltas"] = {
            "mastery": 10,
        }
        transitional_snapshot = gear_resolver.resolve(
            transitional_intent,
            transitional_authority,
        )
        self.assertEqual(transitional_snapshot["status"], "verified")
        self.assertEqual(
            transitional_snapshot["resolvedSlots"]["finger1"]["resolvedStats"][
                "mastery"
            ],
            10,
        )

        self.assertFalse(
            gear_release_shadow._legacy_to_v2_socket_capacity_migration_equivalent(
                transitional_snapshot,
                candidate_snapshot,
                transitional_gear_release_id="compatibility-pg:old",
                transitional_gear_catalog_revision="compatibility-pg:old",
                candidate_gear_release_id="gear-release-17",
                transitional_authority_context=transitional_authority,
                candidate_authority_context=candidate_authority,
                transitional_intent=transitional_intent,
                candidate_intent=candidate_intent,
            )
        )

    def test_legacy_capability_shadow_does_not_require_v2_reference_counts(self):
        intent = self.intent()
        intent["eligibilityContext"]["specKey"] = "frost"
        snapshot = self.snapshot(intent, "sha256:legacy-reference")
        snapshot["eligibilityContext"]["specKey"] = "frost"
        candidate = {
            "templateId": "observed_profile_mage_frost",
            "classKey": "mage",
            "specKey": "frost",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/reference-mage",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:mage:frost:legacy-reference",
            "gearHash": "gear:mage:frost:legacy-reference",
            "selectionIntent": intent,
            "resolvedGearSignature": snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                intent,
                snapshot,
            ),
            "problems": [],
        }
        store = FakeShadowStore(
            candidate,
            capability_revision=gear_socket_authority.LEGACY_CAPABILITY_REVISION,
        )

        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": snapshot,
                "problems": [],
            }),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {
                "status": "resolved",
                "data": snapshot,
                "problems": [],
            }),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "frost")],
                gear_release_id="gear-release:sha256:legacy",
                community_release_id="community-release:sha256:legacy",
                simc_runtime_revision="simc-v1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["referenceProof"]["status"], "not_applicable")
        self.assertNotIn(
            "REFERENCE_ENHANCEMENT_CONTRACT_MISMATCH",
            {problem["code"] for problem in result["blockers"]},
        )

    def test_shadow_fails_closed_for_missing_or_unknown_capability_revision(self):
        candidate = self.candidate_row()
        snapshot = self.snapshot(
            candidate["selectionIntent"],
            candidate["resolvedGearSignature"],
        )
        cases = (
            (None, "CANDIDATE_CAPABILITY_REVISION_MISSING"),
            ("gear-capability-matrix-v999", "CANDIDATE_CAPABILITY_REVISION_UNSUPPORTED"),
        )

        for capability_revision, expected_code in cases:
            with self.subTest(capability_revision=capability_revision):
                store = FakeShadowStore(
                    candidate,
                    capability_revision=capability_revision,
                )
                with patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": snapshot,
                        "problems": [],
                    }),
                ), patch.object(
                    gear_release_shadow.gear_runtime,
                    "resolve_candidate_selection_intent",
                    return_value=(200, {
                        "status": "resolved",
                        "data": snapshot,
                        "problems": [],
                    }),
                ):
                    result = gear_release_shadow.run_release_shadow(
                        store,
                        expected_specs=[("mage", "arcane")],
                        gear_release_id="gear-release:sha256:target",
                        community_release_id="community-release:sha256:target",
                        simc_runtime_revision="simc-v1",
                        compare_profiles=False,
                    )

                self.assertEqual(result["status"], "blocked", result)
                self.assertEqual(result["referenceProof"]["status"], "blocked")
                self.assertIn(
                    expected_code,
                    {problem["code"] for problem in result["blockers"]},
                )

    def test_reference_contract_blocks_wrong_enchant_capacity_even_when_six_are_selected(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        intent = copy.deepcopy(fixture["intent"])
        snapshot = gear_resolver.resolve(intent, fixture["authorityContext"])
        candidate = {
            "sourceKey": "raiderio_observed_profile",
            "profileHash": "profile:mage:frost:reference",
            "gearHash": "gear:mage:frost:reference",
        }
        snapshot["constraints"]["slots"]["main_hand"]["canEnchant"] = False

        proof = gear_release_shadow._reference_contract_proof(
            candidate,
            intent,
            snapshot,
        )

        self.assertEqual(proof["status"], "blocked")
        self.assertIn("enchants", proof["failures"])
        self.assertEqual(proof["enchants"], {"used": 6, "max": 7})

    def test_active_v2_shadow_uses_sealed_active_winner_intent_without_public_leak(self):
        fixture = build_midnight_mage_release_fixture()["resolverFixture"]
        intent = copy.deepcopy(fixture["intent"])
        candidate_snapshot = gear_resolver.resolve(intent, fixture["authorityContext"])
        candidate = {
            "templateId": "observed_profile_mage_frost",
            "classKey": "mage",
            "specKey": "frost",
            "role": "winner",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/reference-mage",
            "sourceStatus": "synced",
            "sampleCount": 1,
            "profileHash": "profile:mage:frost:reference",
            "gearHash": "gear:mage:frost:reference",
            "selectionIntent": intent,
            "resolvedGearSignature": candidate_snapshot["resolvedGearSignature"],
            "semanticGearSignature": gear_release.semantic_gear_signature(
                intent,
                candidate_snapshot,
            ),
            "problems": [],
        }

        class ActiveV2Store(FakeShadowStore):
            def get_gear_resolver_context(self, _runtime_authority):
                return {
                    "formalActiveManifest": True,
                    "authoredAgainst": {
                        "seasonRevision": "season-17-active",
                        "gearCatalogRevision": "gear-release-17",
                    },
                    "dependencyRevisions": {
                        "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
                    },
                }

            def get_active_community_release(self):
                return {
                    "formalActiveManifest": True,
                    "pointerGeneration": 1,
                    "manifestRevision": "manifest:active-v2",
                    "gearRelease": {"releaseId": "gear-release-17"},
                    "communityRelease": {"releaseId": "community-release-active-v2"},
                    "winners": [copy.deepcopy(candidate)],
                }

        store = ActiveV2Store(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
        )
        old_intents = []
        candidate_calls = []

        def resolve_active(selection_intent, **_kwargs):
            old_intents.append(copy.deepcopy(selection_intent))
            snapshot = (
                candidate_snapshot
                if selection_intent == intent
                else gear_resolver.resolve(selection_intent, fixture["authorityContext"])
            )
            return 200, {"status": "resolved", "data": snapshot, "problems": []}

        def active_profile(payload, **_kwargs):
            selected = payload.get("selectionIntent") == intent
            return 200, {
                "status": "resolved",
                "data": {"profile": "mage=active-v2" if selected else "mage=missing-enhancements"},
                "problems": [],
            }

        def resolve_candidate(selection_intent, **_kwargs):
            candidate_calls.append(copy.deepcopy(selection_intent))
            if len(candidate_calls) == 1:
                return 200, {
                    "status": "resolved",
                    "data": candidate_snapshot,
                    "problems": [],
                }
            return 422, {
                "status": "blocked",
                "data": {},
                "problems": [{"code": "GEAR_GEM_SOCKET_CAPACITY_EXCEEDED"}],
            }

        profile = {
            "status": "resolved",
            "data": {"profile": "mage=active-v2"},
            "problems": [],
        }
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            side_effect=resolve_active,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            side_effect=resolve_candidate,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            side_effect=active_profile,
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "frost")],
                gear_release_id="gear-release-17",
                community_release_id="community-release-candidate-v2",
                simc_runtime_revision="simc-v1",
                expect_formal_active=True,
            )

        public = store.get_websim_gear("mage", "frost", compact=True, mode="initial")
        self.assertNotIn("selectionIntent", public["communityTemplates"][0])
        self.assertEqual(old_intents, [intent])
        self.assertEqual(result["status"], "pass", result)

    def test_active_v2_shadow_allows_only_same_dependency_import_fidelity_cutover(self):
        candidate = self.candidate_row()
        candidate["importEvidence"] = {
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {
                "head": {
                    "itemId": "item-a",
                    "variantKey": "variant-a",
                    "observedItemLevel": 292,
                    "iconUrl": "https://render.worldofwarcraft.com/icons/item-a.jpg",
                },
            },
        }
        active_winner = copy.deepcopy(candidate)
        active_winner.pop("importEvidence")
        dependencies = {
            "capabilityRevision": gear_socket_authority.CAPABILITY_REVISION,
        }

        class ImportFidelityStore(FakeShadowStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.candidate_dependencies = copy.deepcopy(dependencies)

            def get_candidate_community_release(
                self,
                gear_release_id,
                community_release_id,
            ):
                pair = super().get_candidate_community_release(
                    gear_release_id,
                    community_release_id,
                )
                pair["gearRelease"]["dependencyRevisions"] = copy.deepcopy(
                    self.candidate_dependencies
                )
                return pair

            def get_gear_resolver_context(self, _runtime_authority):
                return {
                    "formalActiveManifest": True,
                    "authoredAgainst": {
                        "seasonRevision": "season-17",
                        "gearCatalogRevision": "gear-release:sha256:target",
                    },
                    "dependencyRevisions": copy.deepcopy(dependencies),
                }

            def get_active_community_release(self):
                return {
                    "formalActiveManifest": True,
                    "pointerGeneration": 1,
                    "manifestRevision": "manifest:active-v2",
                    "gearRelease": {
                        "releaseId": "gear-release:sha256:target",
                        "dependencyRevisions": copy.deepcopy(dependencies),
                    },
                    "communityRelease": {"releaseId": "community-release:active-v2"},
                    "winners": [copy.deepcopy(active_winner)],
                }

        store = ImportFidelityStore(
            candidate,
            capability_revision=gear_socket_authority.CAPABILITY_REVISION,
        )
        snapshot = self.snapshot(candidate["selectionIntent"], "sha256:candidate")
        legacy_profile = self.resolved_profile_envelope("mage=legacy-gear")
        candidate_profile = self.resolved_profile_envelope("mage=observed-player-gear")
        legacy_profile["data"]["gearItems"] = [{"itemId": "legacy-item"}]
        candidate_profile["data"]["gearItems"] = [{"itemId": "observed-item"}]
        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_selection_intent",
            return_value=(200, {"status": "resolved", "data": snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            return_value=(200, {"status": "resolved", "data": snapshot, "problems": []}),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_profile_from_selection_intent",
            return_value=(200, legacy_profile),
        ), patch.object(
            gear_release_shadow.gear_runtime,
            "build_candidate_profile_from_selection_intent",
            return_value=(200, candidate_profile),
        ):
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                expect_formal_active=True,
            )
            store.candidate_dependencies["serializerRevision"] = "serializer-changed"
            blocked = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "arcane")],
                gear_release_id="gear-release:sha256:target",
                community_release_id="community-release:sha256:target",
                simc_runtime_revision="simc-r1",
                expect_formal_active=True,
            )

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(
            result["report"]["diffs"][0]["classification"],
            "expected_import_fidelity_cutover",
        )
        self.assertEqual(
            result["specResults"][0]["importFidelityCutoverParity"],
            {"status": "pass", "mode": "sealed_observed_import"},
        )
        self.assertEqual(
            result["specResults"][0]["profileParity"],
            {
                "status": "expected_import_fidelity_change",
                "mode": "sealed_observed_source",
                "transitionalHttpStatus": 200,
                "transitionalStatus": "resolved",
                "transitionalProblemCodes": [],
                "candidateHttpStatus": 200,
                "candidateStatus": "resolved",
                "candidateProblemCodes": [],
            },
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn(
            "PUBLIC_WINNER_SEMANTIC_CHANGE",
            {problem["code"] for problem in blocked["blockers"]},
        )

    def test_sealed_active_provenance_overrides_only_a_missing_projection_profile_hash(self):
        projected = {
            "templateId": "observed_profile_mage_arcane",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/example",
            "gearHash": "gear:mage:arcane:example",
            "sampleCount": 1,
            "profileHash": "profile:mage:arcane:legacy-projection",
        }
        sealed = {
            "templateId": "observed_profile_mage_arcane",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/example",
            "gearHash": "gear:mage:arcane:example",
            "sampleCount": 1,
            "profileHash": "",
        }

        aligned = gear_release_shadow._bind_transitional_provenance_to_active_winner(
            projected,
            sealed,
        )
        self.assertEqual(aligned["profileHash"], "")
        self.assertEqual(projected["profileHash"], "profile:mage:arcane:legacy-projection")

        sealed["sourceUrl"] = "https://raider.io/characters/cn/different"
        mismatch = gear_release_shadow._bind_transitional_provenance_to_active_winner(
            projected,
            sealed,
        )
        self.assertEqual(mismatch, projected)

    def test_sealed_active_provenance_restores_import_evidence_after_exact_identity_match(self):
        projected = {
            "templateId": "observed_profile_deathknight_frost",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/example",
            "gearHash": "gear:deathknight:frost:example",
            "sampleCount": 1,
            "profileHash": "profile:deathknight:frost:example",
        }
        sealed_evidence = {
            "schemaRevision": "community-template-import-evidence-v1",
            "sourceFingerprint": "sha256:" + "a" * 64,
            "slots": {
                "head": {
                    "itemId": "249970",
                    "variantKey": "item:249970",
                    "observedItemLevel": 289,
                    "iconUrl": "https://render.worldofwarcraft.com/icons/head.jpg",
                },
            },
        }
        sealed = {
            **projected,
            "payload": {"importEvidence": sealed_evidence},
        }

        aligned = gear_release_shadow._bind_transitional_provenance_to_active_winner(
            projected,
            sealed,
        )
        self.assertEqual(aligned["importEvidence"], sealed_evidence)
        self.assertIsNot(aligned["importEvidence"], sealed_evidence)
        self.assertNotIn("importEvidence", projected)

        sealed["gearHash"] = "gear:deathknight:frost:different"
        mismatch = gear_release_shadow._bind_transitional_provenance_to_active_winner(
            projected,
            sealed,
        )
        self.assertNotIn("importEvidence", mismatch)

    def test_import_fidelity_profile_gate_allows_only_source_backed_gear_content_delta(self):
        old = self.resolved_profile_envelope("mage=legacy-gear")
        new = copy.deepcopy(old)
        new["data"]["profile"] = "mage=observed-player-gear"
        old["data"]["gearItems"] = [{"itemId": "legacy-item"}]
        new["data"]["gearItems"] = [{"itemId": "observed-item"}]

        old_outcome = gear_release_shadow._profile_outcome(200, old)
        new_outcome = gear_release_shadow._profile_outcome(200, new)
        self.assertTrue(
            gear_release_shadow._profile_outcomes_preserve_import_gate(
                old_outcome,
                new_outcome,
            )
        )

        changed_gate = copy.deepcopy(new_outcome)
        changed_gate["data"]["profileReadiness"]["simcReady"] = False
        self.assertFalse(
            gear_release_shadow._profile_outcomes_preserve_import_gate(
                old_outcome,
                changed_gate,
            )
        )

    def test_projected_candidate_shadow_bootstraps_exactly_two_hero_winners_from_gear_only_manifest(self):
        intents = {
            hero_key: {
                "schemaRevision": "selection-intent-v1",
                "authoredAgainst": {
                    "seasonRevision": "season-17",
                    "gearCatalogRevision": "gear-release:candidate",
                },
                "eligibilityContext": {
                    "classKey": "mage",
                    "specKey": "frost",
                    "level": 90,
                },
                "slots": {
                    "head": {
                        "itemId": f"item-{hero_key}",
                        "variantKey": f"variant-{hero_key}",
                        "gemOptionIds": [],
                        "enchantOptionId": "",
                        "embellishmentOptionId": "",
                        "craftedOptionId": "",
                        "catalystOptionId": "",
                    },
                },
            }
            for hero_key in ("frostfire", "spellslinger")
        }
        snapshots = {
            hero_key: {
                "status": "verified",
                "resolvedGearSignature": f"resolved-{hero_key}",
                "resolvedSlots": {
                    "head": {
                        "itemId": f"item-{hero_key}",
                        "variantKey": f"variant-{hero_key}",
                    },
                },
                "staticAttributes": {"intellect": 100},
                "setState": {"itemSetCounts": {}, "activeDynamicEffects": []},
                "constraints": {"slots": {"head": {"socketCount": 0}}},
                "serializerInput": {"gearItems": []},
                "aggregateLegality": {"status": "verified", "problemCodes": []},
                "profileReadiness": {
                    "status": "verified",
                    "simcReady": True,
                    "problems": [],
                },
                "problems": [],
            }
            for hero_key in intents
        }
        winners = []
        public_templates = []
        for rank, hero_key in enumerate(sorted(intents), start=1):
            template_id = f"community-gear:mage:frost:{hero_key}:source"
            winners.append({
                "templateId": template_id,
                "classKey": "mage",
                "specKey": "frost",
                "role": "winner",
                "electionRank": rank,
                "sourceKey": "raiderio_observed_profile",
                "sourceUrl": f"https://raider.io/characters/example/{hero_key}",
                "sampleCount": 1,
                "profileHash": f"profile-{hero_key}",
                "gearHash": f"gear-{hero_key}",
                "selectionIntent": intents[hero_key],
                "resolvedGearSignature": snapshots[hero_key][
                    "resolvedGearSignature"
                ],
                "semanticGearSignature": gear_release.semantic_gear_signature(
                    intents[hero_key],
                    snapshots[hero_key],
                ),
                "problems": [],
                "payload": {
                    "id": template_id,
                    "heroKey": hero_key,
                    "gearSourceTemplateId": f"source-{hero_key}",
                },
            })
            public_templates.append({
                "id": template_id,
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": hero_key,
                "sourceKey": "raiderio_observed_profile",
            })

        active = {
            "formalActiveManifest": True,
            "formalGearOnlyManifest": True,
            "pointerGeneration": 24,
            "manifestRevision": "season-manifest:active",
            "gearRelease": {
                "releaseId": "gear-release:active",
                "dependencyRevisions": {
                    "capabilityRevision": "gear-capability-matrix-v2",
                },
            },
            "communityRelease": None,
            "winners": [],
        }

        class ProjectedStore:
            def __init__(self):
                self.active_reads = 0

            def get_candidate_community_release(self, gear_id, community_id):
                return {
                    "gearRelease": {
                        "releaseId": gear_id,
                        "releaseStatus": "validated",
                        "dependencyRevisions": {
                            "capabilityRevision": "gear-capability-matrix-v2",
                        },
                    },
                    "communityRelease": {
                        "releaseId": community_id,
                        "releaseStatus": "validated",
                        "schemaRevision": "community-release-v2",
                        "validatedAgainstReleaseId": gear_id,
                    },
                    "winners": copy.deepcopy(winners),
                }

            def get_active_community_release(self):
                self.active_reads += 1
                return copy.deepcopy(active)

            def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
                return {
                    "candidatePreview": True,
                    "formalActiveManifest": False,
                    "manifestRevision": "candidate-preview:exact",
                    "gearCatalogReleaseId": "gear-release:candidate",
                    "communityTemplateReleaseId": "community-release:candidate",
                    "communityTemplates": copy.deepcopy(public_templates),
                    "baselineTemplates": [],
                }

            def get_gear_resolver_context(self, _runtime_authority):
                return {
                    "candidatePreview": True,
                    "formalActiveManifest": False,
                    "manifestRevision": "candidate-preview:exact",
                    "authoredAgainst": {
                        "seasonRevision": "season-17",
                        "gearCatalogRevision": "gear-release:candidate",
                    },
                }

        store = ProjectedStore()

        def resolve_candidate(intent, **_kwargs):
            hero_key = intent["slots"]["head"]["itemId"].removeprefix("item-")
            return 200, {
                "status": "resolved",
                "data": copy.deepcopy(snapshots[hero_key]),
                "problems": [],
            }

        def import_template(request, **_kwargs):
            hero_key = request["templateId"].split(":")[3]
            return (
                200,
                {
                    "status": "verified",
                    "data": {
                        "status": "verified",
                        "resolvedSnapshot": copy.deepcopy(snapshots[hero_key]),
                    },
                    "problems": [],
                },
                {},
            )

        with patch.object(
            gear_release_shadow.gear_runtime,
            "resolve_candidate_selection_intent",
            side_effect=resolve_candidate,
        ) as candidate_resolve, patch.object(
            gear_release_shadow.gear_runtime,
            "import_community_template",
            side_effect=import_template,
        ) as community_import:
            result = gear_release_shadow.run_release_shadow(
                store,
                expected_specs=[("mage", "frost")],
                gear_release_id="gear-release:candidate",
                community_release_id="community-release:candidate",
                simc_runtime_revision="simc-r1",
                compare_profiles=False,
            )

        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["baselineMode"], "formal_gear_only_candidate_preview")
        self.assertTrue(result["candidatePreview"])
        self.assertEqual(result["publicReadCount"], 1)
        self.assertEqual(result["importReadCount"], 2)
        self.assertEqual(result["report"]["candidateWinnerCount"], 2)
        self.assertEqual(result["report"]["expectedHeroSlotCount"], 2)
        self.assertEqual(len(result["specResults"]), 1)
        self.assertEqual(len(result["specResults"][0]["heroSlotResults"]), 2)
        self.assertEqual(store.active_reads, 2)
        self.assertEqual(candidate_resolve.call_count, 2)
        self.assertEqual(community_import.call_count, 2)

    def test_projected_candidate_shadow_requires_exact_candidate_preview_binding(self):
        pair = {
            "gearRelease": {
                "releaseId": "gear-release:candidate",
                "releaseStatus": "validated",
                "dependencyRevisions": {
                    "capabilityRevision": "gear-capability-matrix-v2",
                },
            },
            "communityRelease": {
                "releaseId": "community-release:candidate",
                "releaseStatus": "validated",
                "schemaRevision": "community-release-v2",
                "validatedAgainstReleaseId": "gear-release:candidate",
            },
            "winners": [],
        }
        active = {
            "formalActiveManifest": True,
            "formalGearOnlyManifest": True,
            "pointerGeneration": 24,
            "manifestRevision": "season-manifest:active",
            "gearRelease": {"releaseId": "gear-release:active"},
            "communityRelease": None,
            "winners": [],
        }

        class Store:
            def get_candidate_community_release(self, *_args):
                return copy.deepcopy(pair)

            def get_active_community_release(self):
                return copy.deepcopy(active)

            def get_websim_gear(self, *_args, **_kwargs):
                return {
                    "candidatePreview": False,
                    "formalActiveManifest": True,
                    "communityTemplates": [],
                    "baselineTemplates": [],
                }

            def get_gear_resolver_context(self, *_args, **_kwargs):
                return {"candidatePreview": False, "formalActiveManifest": True}

        result = gear_release_shadow.run_release_shadow(
            Store(),
            expected_specs=[("mage", "frost")],
            gear_release_id="gear-release:candidate",
            community_release_id="community-release:candidate",
            simc_runtime_revision="simc-r1",
            compare_profiles=False,
        )

        self.assertEqual(result["status"], "blocked")
        self.assertIn(
            "CANDIDATE_PREVIEW_BINDING_REQUIRED",
            {problem["code"] for problem in result["blockers"]},
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from server import gear_evidence_ledger


class GearEvidenceLedgerTest(unittest.TestCase):
    def dependency_vector(self):
        return {
            "seasonRevision": "season-17-active",
            "gearCatalogReleaseId": "gear-release-17",
            "gearCatalogRevision": "gear-r17",
            "gearRuleRevision": "gear-rule-matrix-v1",
            "resolverContractRevision": "gear-resolver-contract-v1",
            "serializerRevision": "serializer-v1",
            "simcRuntimeRevision": "simc-v1",
            "statPolicyRevision": "stat-policy-v1",
            "selectionSchemaRevision": "selection-intent-v1",
        }

    def claim(self, **overrides):
        args = {
            "group": "identity_options",
            "claim_key": "slot:head:variant",
            "value": {"variantKey": "variant-head", "itemId": "item-head"},
            "status": "verified",
            "source_ref_ids": ["evidence:variant:head"],
            "rule_revision": "gear-rule-matrix-v1",
            "resolved_signature": "sha256:resolved",
            "dependency_vector": self.dependency_vector(),
        }
        args.update(overrides)
        return gear_evidence_ledger.evidence_claim(**args)

    def records(self):
        return {
            "evidence:variant:head": {
                "id": "evidence:variant:head",
                "sourceType": "simulationcraft",
                "sourceRevision": "simc-v1",
                "payloadHash": "sha256:payload",
            }
        }

    def test_evidence_ledger_has_exact_five_claim_groups(self):
        self.assertEqual(
            gear_evidence_ledger.CLAIM_GROUPS,
            (
                "identity_options",
                "provenance",
                "legality",
                "static_attributes",
                "profile_executability",
            ),
        )
        ledger = gear_evidence_ledger.build_evidence_ledger([self.claim()], self.records())
        self.assertEqual(
            tuple(ledger),
            ("contractRevision", "claims", "claimGroups", "evidenceRecordsById", "problems"),
        )
        self.assertEqual(ledger["contractRevision"], "gear-evidence-ledger-v1")
        self.assertEqual(tuple(ledger["claimGroups"]), gear_evidence_ledger.CLAIM_GROUPS)

    def test_claim_status_allows_verified_or_blocked_only(self):
        self.assertEqual(self.claim(status="verified")["status"], "verified")
        self.assertEqual(self.claim(status="blocked")["status"], "blocked")
        with self.assertRaises(ValueError):
            self.claim(status="pending")
        with self.assertRaises(ValueError):
            self.claim(group="unknown")

    def test_claim_id_is_stable_for_canonical_value_and_dependency_order(self):
        first = self.claim()
        second = self.claim(
            value={"itemId": "item-head", "variantKey": "variant-head"},
            dependency_vector=dict(reversed(list(self.dependency_vector().items()))),
        )
        self.assertRegex(first["claimId"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first["claimId"], second["claimId"])

    def test_claim_id_changes_for_value_sources_rule_signature_or_dependency_change(self):
        baseline = self.claim()["claimId"]
        mutations = (
            {"value": {"itemId": "item-other"}},
            {"source_ref_ids": ["evidence:variant:other"]},
            {"rule_revision": "gear-rule-matrix-v2"},
            {"resolved_signature": "sha256:other"},
            {"dependency_vector": {**self.dependency_vector(), "gearCatalogRevision": "gear-r18"}},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertNotEqual(baseline, self.claim(**mutation)["claimId"])

    def test_missing_evidence_record_fails_claim_closed(self):
        ledger = gear_evidence_ledger.build_evidence_ledger([self.claim()], {})

        self.assertEqual(ledger["claims"][0]["status"], "blocked")
        self.assertEqual(ledger["claims"][0]["problems"][0]["kind"], "AUTHORITY_UNAVAILABLE")
        self.assertEqual(ledger["claims"][0]["problems"][0]["code"], "EVIDENCE_RECORD_MISSING")
        self.assertEqual(ledger["evidenceRecordsById"], {})

    def test_source_records_are_projected_by_id_without_free_text_substitution(self):
        records = self.records()
        records["unreferenced"] = {"id": "unreferenced", "sourceType": "manual"}
        ledger = gear_evidence_ledger.build_evidence_ledger([self.claim()], records)

        self.assertEqual(ledger["evidenceRecordsById"], {"evidence:variant:head": records["evidence:variant:head"]})
        self.assertNotIn("unreferenced", ledger["evidenceRecordsById"])
        self.assertNotIn("sourceText", ledger["claims"][0])

    def test_only_aggregate_claims_may_use_bounded_depends_on(self):
        with self.assertRaises(ValueError):
            self.claim(depends_on=["sha256:other"])

        aggregate = self.claim(
            group="static_attributes",
            claim_key="aggregate:static_attributes",
            source_ref_ids=[],
            depends_on=["sha256:other"],
        )
        self.assertEqual(aggregate["dependsOn"], ["sha256:other"])

    def test_ledger_rejects_unknown_dependencies_and_cycles(self):
        leaf = self.claim()
        unknown = self.claim(
            group="static_attributes",
            claim_key="aggregate:static_attributes",
            source_ref_ids=[],
            depends_on=["sha256:unknown"],
        )
        with self.assertRaises(ValueError):
            gear_evidence_ledger.build_evidence_ledger([leaf, unknown], self.records())

        first = self.claim(
            group="legality",
            claim_key="aggregate:legality",
            source_ref_ids=[],
        )
        second = self.claim(
            group="static_attributes",
            claim_key="aggregate:static_attributes",
            source_ref_ids=[],
        )
        first["dependsOn"] = [second["claimId"]]
        second["dependsOn"] = [first["claimId"]]
        with self.assertRaises(ValueError):
            gear_evidence_ledger.build_evidence_ledger([first, second], {})

    def test_ledger_order_is_group_then_claim_key(self):
        identity_b = self.claim(claim_key="slot:neck:variant")
        identity_a = self.claim(claim_key="slot:head:variant")
        legality = self.claim(
            group="legality",
            claim_key="rule:season_release_identity",
        )
        records = self.records()
        ledger = gear_evidence_ledger.build_evidence_ledger(
            [legality, identity_b, identity_a],
            records,
        )

        self.assertEqual(
            [(claim["group"], claim["claimKey"]) for claim in ledger["claims"]],
            [
                ("identity_options", "slot:head:variant"),
                ("identity_options", "slot:neck:variant"),
                ("legality", "rule:season_release_identity"),
            ],
        )
        self.assertEqual(
            ledger["claimGroups"]["identity_options"],
            [identity_a["claimId"], identity_b["claimId"]],
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import unittest

from server import news_backend


class AuditStore:
    def __init__(self, summary):
        self.summary = summary

    def health_summary(self, *, now):
        return {**self.summary, "checkedAt": now}


class AttributeRuleAuditHealthTest(unittest.TestCase):
    def test_missing_store_is_truthful_blocked_component(self):
        component = news_backend.attribute_rule_audit_health_component(store=None, now="2026-07-17T04:00:00+00:00")

        self.assertEqual(component["key"], "attribute_rule_audit")
        self.assertEqual(component["status"], "blocked")
        self.assertEqual(component["blockers"], ["attribute rule audit PostgreSQL store is unavailable"])

    def test_confirmed_mismatch_is_bounded_internal_health_finding_without_profile_identity(self):
        component = news_backend.attribute_rule_audit_health_component(
            store=AuditStore({
                "queue": {"pending": 0, "running": 0},
                "terminalCounts": {"pass": 3, "confirmedMismatch": 1, "inconclusive": 2, "sourceUnavailable": 1},
                "latestCheckedAt": "2026-07-17T04:00:00+00:00",
                "findingRuleContexts": [{"attributeRuleRevision": "rules-r2", "contextKey": "mage:arcane:90:night_elf"}],
            }),
            now="2026-07-17T04:00:00+00:00",
        )

        self.assertEqual(component["status"], "blocked")
        self.assertEqual(component["details"]["findingRuleContexts"], [{"attributeRuleRevision": "rules-r2", "contextKey": "mage:arcane:90:night_elf"}])
        self.assertEqual(component["details"]["trigger"], {
            "unit": "wow-gear-release-refresh.service", "onSuccessUnit": "wow-attribute-rule-audit.service"
        })
        self.assertNotIn("characterName", str(component))
        self.assertNotIn("realmSlug", str(component))
        self.assertNotIn("sealedInput", str(component))

    def test_source_unavailable_and_inconclusive_are_partial_not_a_rule_verification(self):
        component = news_backend.attribute_rule_audit_health_component(
            store=AuditStore({
                "queue": {"pending": 0, "running": 0},
                "terminalCounts": {"pass": 0, "confirmedMismatch": 0, "inconclusive": 2, "sourceUnavailable": 1},
                "latestCheckedAt": "2026-07-17T04:00:00+00:00",
                "findingRuleContexts": [],
            }),
            now="2026-07-17T04:00:00+00:00",
        )

        self.assertEqual(component["status"], "partial")
        self.assertEqual(component["blockers"], [])


if __name__ == "__main__":
    unittest.main()

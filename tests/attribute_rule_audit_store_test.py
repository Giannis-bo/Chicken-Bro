#!/usr/bin/env python3
import unittest

from server.attribute_rule_audit import build_winner_audit_intents
from server.attribute_rule_audit_store import AttributeRuleAuditStore
from tests.attribute_rule_audit_test import fixture


class FakeCursor:
    def __init__(self, responder):
        self.responder = responder
        self.statements = []
        self.params = []
        self.current = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        self.params.append(params)
        self.current = self.responder(normalized, params)

    def fetchone(self):
        if isinstance(self.current, list):
            return self.current[0] if self.current else None
        return self.current

    def fetchall(self):
        if self.current is None:
            return []
        return self.current if isinstance(self.current, list) else [self.current]


class FakeConnection:
    def __init__(self, responder):
        self.cursor_instance = FakeCursor(responder)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if not exc_type:
            self.committed = True
        return False

    def cursor(self):
        return self.cursor_instance


def pending_intent():
    data = fixture()
    return build_winner_audit_intents(
        active_winners=data["activeWinners"],
        candidate_rows=data["candidateRows"],
        candidate_context=data["candidateContext"],
        rulebook=data["verifiedRulebook"],
    )[0]


def audit_row(intent, *, status="pending", attempt=0, lock_token=""):
    return (
        intent["auditKey"],
        intent["candidateCommunityReleaseId"],
        intent["candidateGearReleaseId"],
        intent["manifestRevision"],
        intent["attributeRuleRevision"],
        intent["contextKey"],
        status,
        intent["canonicalInputSignature"],
        {"sourceIdentity": intent["sourceIdentity"], "sealedInput": intent["sealedInput"], "rule": intent["rule"]},
        {},
        attempt,
        "worker-a" if status == "running" else "",
        lock_token,
        "2026-07-17T05:00:00+00:00" if status == "running" else None,
        "2026-07-17T04:00:00+00:00",
        "2026-07-17T04:01:00+00:00" if status == "running" else None,
        None,
        "2026-07-17T04:00:00+00:00",
        "2026-07-17T04:00:00+00:00",
    )


class AttributeRuleAuditStoreTest(unittest.TestCase):
    def test_enqueue_is_idempotent_and_preserves_existing_terminal_record(self):
        intent = pending_intent()
        conn = FakeConnection(lambda sql, _params: (intent["auditKey"], "pending") if "INSERT INTO ops.websim_attribute_rule_audits" in sql else None)

        result = AttributeRuleAuditStore(lambda: conn).enqueue_intents([intent], now="2026-07-17T04:00:00+00:00")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["reused"], 0)
        self.assertIn("ON CONFLICT (audit_key) DO NOTHING", sql)
        self.assertIn("input_json", sql)
        self.assertTrue(conn.committed)

    def test_terminal_enqueue_persists_its_bounded_reason_code(self):
        data = fixture()
        terminal = build_winner_audit_intents(
            active_winners=data["activeWinners"],
            candidate_rows=data["candidateRows"],
            candidate_context=data["candidateContext"],
            rulebook=data["fixtureOnlyRulebook"],
        )[0]
        conn = FakeConnection(
            lambda sql, _params: (terminal["auditKey"], terminal["status"])
            if "INSERT INTO ops.websim_attribute_rule_audits" in sql else None
        )

        AttributeRuleAuditStore(lambda: conn).enqueue_intents([terminal], now="2026-07-17T04:00:00+00:00")

        self.assertIn(terminal["code"], str(conn.cursor_instance.params))

    def test_claim_uses_skip_locked_and_returns_fenced_running_record(self):
        intent = pending_intent()
        conn = FakeConnection(lambda sql, _params: audit_row(intent, status="running", attempt=1, lock_token="lease-a") if "FOR UPDATE SKIP LOCKED" in sql else None)

        claimed = AttributeRuleAuditStore(lambda: conn).claim_next(
            worker_id="worker-a", lock_token="lease-a", now="2026-07-17T04:00:00+00:00"
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["lockToken"], "lease-a")
        self.assertIn("FOR UPDATE SKIP LOCKED", sql)
        self.assertIn("attempt = audit.attempt + 1", sql)

    def test_finish_requires_matching_fenced_running_lease(self):
        intent = pending_intent()
        conn = FakeConnection(lambda sql, _params: (intent["auditKey"], "pass") if "UPDATE ops.websim_attribute_rule_audits" in sql else None)

        result = AttributeRuleAuditStore(lambda: conn).finish(
            audit_key=intent["auditKey"],
            lock_token="lease-a",
            outcome={"status": "pass", "result": {"fields": []}},
            now="2026-07-17T04:00:00+00:00",
        )

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["status"], "pass")
        self.assertIn("lock_token = %s AND status = 'running'", sql)
        self.assertIn("lease_until = NULL", sql)

    def test_health_summary_returns_bounded_counts_and_never_reads_input_json(self):
        conn = FakeConnection(
            lambda sql, _params: (2, 1, 8, 3, 4, 5, "2026-07-17T04:00:00+00:00")
            if "count(*) FILTER" in sql
            else [("fixture-audit-r1", "mage:frost:90:human")]
            if "WHERE status = 'confirmed_mismatch'" in sql
            else None
        )

        result = AttributeRuleAuditStore(lambda: conn).health_summary(now="2026-07-17T04:00:00+00:00")

        sql = "\n".join(conn.cursor_instance.statements)
        self.assertEqual(result["queue"], {"pending": 2, "running": 1})
        self.assertEqual(result["terminalCounts"]["confirmedMismatch"], 3)
        self.assertEqual(result["findingRuleContexts"], [{"attributeRuleRevision": "fixture-audit-r1", "contextKey": "mage:frost:90:human"}])
        self.assertNotIn("input_json", sql)


if __name__ == "__main__":
    unittest.main()

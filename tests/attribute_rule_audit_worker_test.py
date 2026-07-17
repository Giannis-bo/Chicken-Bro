#!/usr/bin/env python3
import copy
import unittest

from server.attribute_rule_audit import build_winner_audit_intents
from server.attribute_rule_audit_source import AttributeAuditSourceUnavailable
from server.attribute_rule_audit_worker import run_attribute_rule_audit_worker
from tests.attribute_rule_audit_test import fixture


def pending_claim(*, token="lease-a"):
    data = fixture()
    intent = build_winner_audit_intents(
        active_winners=data["activeWinners"],
        candidate_rows=data["candidateRows"],
        candidate_context=data["candidateContext"],
        rulebook=data["verifiedRulebook"],
    )[0]
    return {
        "auditKey": intent["auditKey"],
        "lockToken": token,
        "status": "running",
        "input": {
            "sourceIdentity": intent["sourceIdentity"],
            "sealedInput": intent["sealedInput"],
            "rule": intent["rule"],
        },
    }


def calculated_panel():
    return {
        "status": "calculated",
        "primary": {"key": "intellect", "rawValue": 1500},
        "stamina": {"key": "stamina", "rawValue": 2600},
        "resources": {"health": {"key": "health", "rawValue": 52100}},
        "secondary": [{"key": "haste", "rawValue": 100, "convertedValue": "2.0%", "displayUnit": "percent"}],
    }


class FakeStore:
    def __init__(self, claims):
        self.claims = list(claims)
        self.finishes = []

    def claim_next(self, **_kwargs):
        return self.claims.pop(0) if self.claims else {}

    def finish(self, **kwargs):
        self.finishes.append(kwargs)
        return {"auditKey": kwargs["audit_key"], "status": kwargs["outcome"]["status"]}


class AttributeRuleAuditWorkerTest(unittest.TestCase):
    def test_no_pending_audit_exits_without_oauth_or_profile_request(self):
        store = FakeStore([])
        source_calls = []

        result = run_attribute_rule_audit_worker(
            store,
            source_fetcher=lambda identity: source_calls.append(identity),
            now="2026-07-17T04:00:00+00:00",
            worker_id="worker-a",
            token_factory=lambda: "lease-a",
        )

        self.assertEqual(result, {"status": "idle", "claimed": 0, "outcomes": {}})
        self.assertEqual(source_calls, [])

    def test_unavailable_official_source_is_terminal_without_leaking_error_detail(self):
        store = FakeStore([pending_claim()])

        result = run_attribute_rule_audit_worker(
            store,
            source_fetcher=lambda _identity: (_ for _ in ()).throw(AttributeAuditSourceUnavailable("PROFILE_UNAVAILABLE")),
            now="2026-07-17T04:00:00+00:00",
            worker_id="worker-a",
            token_factory=lambda: "lease-a",
        )

        self.assertEqual(result["outcomes"], {"blocked_source_unavailable": 1})
        self.assertEqual(store.finishes[0]["outcome"], {
            "status": "blocked_source_unavailable", "result": {"code": "PROFILE_UNAVAILABLE"}
        })

    def test_input_mismatch_never_calls_calculator(self):
        claim = pending_claim()
        store = FakeStore([claim])
        calculator_calls = []
        profile = copy.deepcopy(claim["input"]["sealedInput"])
        profile["equipment"][0]["gemIds"] = ["wrong-gem"]

        result = run_attribute_rule_audit_worker(
            store,
            source_fetcher=lambda _identity: {"profile": profile, "panel": calculated_panel()},
            calculator=lambda *_args: calculator_calls.append(True),
            now="2026-07-17T04:00:00+00:00",
            worker_id="worker-a",
            token_factory=lambda: "lease-a",
        )

        self.assertEqual(result["outcomes"], {"inconclusive_input_mismatch": 1})
        self.assertEqual(calculator_calls, [])
        self.assertEqual(store.finishes[0]["outcome"]["status"], "inconclusive_input_mismatch")

    def test_matched_profile_calculates_and_records_field_level_pass(self):
        claim = pending_claim()
        store = FakeStore([claim])
        calculator_calls = []

        result = run_attribute_rule_audit_worker(
            store,
            source_fetcher=lambda _identity: {
                "profile": {
                    "character": claim["input"]["sealedInput"]["character"],
                    "equipment": claim["input"]["sealedInput"]["equipment"],
                },
                "panel": calculated_panel(),
            },
            calculator=lambda *_args: calculator_calls.append(True) or calculated_panel(),
            now="2026-07-17T04:00:00+00:00",
            worker_id="worker-a",
            token_factory=lambda: "lease-a",
        )

        self.assertEqual(result["outcomes"], {"pass": 1})
        self.assertEqual(calculator_calls, [True])
        outcome = store.finishes[0]["outcome"]
        self.assertEqual(outcome["status"], "pass")
        self.assertEqual(outcome["result"]["comparison"]["fields"][0]["key"], "primary")

    def test_one_invocation_respects_one_job_default_and_never_starts_simc(self):
        first = pending_claim(token="lease-a")
        second = pending_claim(token="lease-b")
        store = FakeStore([first, second])

        result = run_attribute_rule_audit_worker(
            store,
            source_fetcher=lambda _identity: {
                "profile": {"character": first["input"]["sealedInput"]["character"], "equipment": first["input"]["sealedInput"]["equipment"]},
                "panel": calculated_panel(),
            },
            calculator=lambda *_args: calculated_panel(),
            now="2026-07-17T04:00:00+00:00",
            worker_id="worker-a",
            token_factory=iter(["lease-a", "lease-b"]).__next__,
        )

        self.assertEqual(result["claimed"], 1)
        self.assertEqual(len(store.finishes), 1)
        self.assertEqual(len(store.claims), 1)


if __name__ == "__main__":
    unittest.main()

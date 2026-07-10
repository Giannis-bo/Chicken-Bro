import json
import unittest

from server import gear_result_envelope


class GearResultEnvelopeTest(unittest.TestCase):
    def test_result_envelope_has_exact_contract_shape(self):
        envelope = gear_result_envelope.result_envelope(
            "resolved",
            "request-123",
            {"gearCatalogReleaseId": "gear-release-17"},
            data={"resolvedGearSignature": "sha256:resolved"},
        )

        self.assertEqual(
            tuple(envelope),
            ("contractRevision", "requestId", "status", "releaseContext", "data", "problems"),
        )
        self.assertEqual(envelope["contractRevision"], "gear-result-envelope-v1")
        self.assertEqual(envelope["status"], "resolved")
        self.assertEqual(envelope["problems"], [])

    def test_problem_kind_allowlist_rejects_unknown_kind(self):
        allowed = {
            "INVALID_INTENT",
            "ILLEGAL_SELECTION",
            "REVISION_CONFLICT",
            "AUTHORITY_UNAVAILABLE",
            "SIMC_UNAVAILABLE",
            "INTERNAL_ERROR",
        }
        self.assertEqual(gear_result_envelope.PROBLEM_KINDS, allowed)
        with self.assertRaises(ValueError):
            gear_result_envelope.gear_problem("CLIENT_GUESSED", "NOPE", "Nope")

    def test_http_semantics_preserve_blocked_pending_conflict_and_unavailable(self):
        cases = (
            ("resolved", [], 200),
            ("blocked", [self.problem("ILLEGAL_SELECTION")], 200),
            ("blocked", [self.problem("INVALID_INTENT")], 400),
            ("blocked", [self.problem("REVISION_CONFLICT")], 409),
            ("pending", [], 202),
            ("unavailable", [self.problem("AUTHORITY_UNAVAILABLE")], 503),
            ("unavailable", [self.problem("SIMC_UNAVAILABLE")], 503),
            ("unavailable", [self.problem("INTERNAL_ERROR")], 500),
        )
        for status, problems, expected in cases:
            with self.subTest(status=status, problems=problems):
                envelope = gear_result_envelope.result_envelope(
                    status,
                    "request-http",
                    {},
                    problems=problems,
                )
                self.assertEqual(gear_result_envelope.http_status_for_envelope(envelope), expected)

    def test_problem_order_and_meta_are_deterministic(self):
        later = gear_result_envelope.gear_problem(
            "ILLEGAL_SELECTION",
            "WEAPON_TYPE",
            "Wrong weapon",
            path="slots.main_hand",
            meta={"z": 1, "nested": {"y": 2, "a": 1}},
        )
        first = gear_result_envelope.gear_problem(
            "INVALID_INTENT",
            "UNKNOWN_SLOT",
            "Unknown slot",
            path="slots.unknown",
            meta={"b": 2, "a": 1},
        )

        left = gear_result_envelope.result_envelope("blocked", "request-order", {}, problems=[later, first])
        right = gear_result_envelope.result_envelope("blocked", "request-order", {}, problems=[first, later])

        self.assertEqual(json.dumps(left, separators=(",", ":")), json.dumps(right, separators=(",", ":")))
        self.assertEqual([problem["kind"] for problem in left["problems"]], ["INVALID_INTENT", "ILLEGAL_SELECTION"])
        self.assertEqual(tuple(left["problems"][0]["meta"]), ("a", "b"))
        self.assertEqual(tuple(left["problems"][1]["meta"]["nested"]), ("a", "y"))

    @staticmethod
    def problem(kind):
        return gear_result_envelope.gear_problem(kind, f"{kind}_CODE", kind)


if __name__ == "__main__":
    unittest.main()

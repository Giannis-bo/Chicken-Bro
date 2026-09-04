import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from server.accept_chickenbro_dual_client import (
    AcceptanceEvidenceError,
    build_acceptance_evidence,
    finalize_production_acceptance,
    verify_route_contract,
)


ROUTES = [
    "pages/chickenbro/index",
    "pages/simc/index",
    "pages/simc/tasks",
    "pages/simc/task-detail",
    "pages/auth/web-login-confirm",
]


class DualClientAcceptanceTest(unittest.TestCase):
    def test_route_contract_requires_every_web_and_weapp_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            web = root / "h5"
            weapp = root / "weapp"
            web.mkdir()
            weapp.mkdir()
            (web / "app.js").write_text("\n".join(ROUTES), encoding="utf-8")
            for route in ROUTES:
                (weapp / f"{route}.js").parent.mkdir(parents=True, exist_ok=True)
                (weapp / f"{route}.js").write_text("route", encoding="utf-8")

            report = verify_route_contract(web, weapp)

        self.assertEqual(report["testedRoutes"], ROUTES)
        self.assertEqual(report["status"], "passed")
        self.assertRegex(report["evidenceHash"], r"^[0-9a-f]{64}$")

    def test_candidate_evidence_records_authorized_login_skip_without_claiming_qr_success(self):
        machine = {
            "redactedObjectHashes": {
                "miniCreatedConversation": "a" * 64,
                "webCreatedConversation": "b" * 64,
                "miniCreatedJob": "c" * 64,
                "webCreatedJob": "d" * 64,
                "primaryUser": "e" * 64,
                "otherUser": "f" * 64,
            },
            "checks": {
                "ownerIsolation": True,
                "logoutIndependent": True,
            },
            "recordedAt": "2026-09-04T03:00:00Z",
        }
        evidence = build_acceptance_evidence(
            mode="candidate",
            expected_commit="a" * 40,
            web_build_identity="b" * 64,
            weapp_build_identity="c" * 64,
            candidate_evidence_sha256="d" * 64,
            machine_evidence=machine,
            route_report={"testedRoutes": ROUTES, "status": "passed", "evidenceHash": "1" * 64},
            accepted_at="2026-09-04T03:01:00Z",
        )

        self.assertEqual(evidence["status"], "real_dual_client_acceptance_passed")
        self.assertEqual(evidence["loginMode"], "user_authorized_skipped")
        self.assertEqual(evidence["realWechatQrLogin"]["status"], "skipped")
        self.assertNotEqual(evidence["realWechatQrLogin"]["status"], "passed")
        self.assertEqual(evidence["testedRoutes"], ROUTES)
        self.assertNotIn("accessToken", json.dumps(evidence))

    def test_production_evidence_requires_explicit_user_confirmation_to_seal(self):
        machine = {
            "redactedObjectHashes": {
                "miniCreatedConversation": "a" * 64,
                "webCreatedConversation": "b" * 64,
                "miniCreatedJob": "c" * 64,
                "webCreatedJob": "d" * 64,
                "primaryUser": "e" * 64,
                "otherUser": "f" * 64,
            },
            "checks": {"ownerIsolation": True, "logoutIndependent": True},
            "recordedAt": "2026-09-04T03:00:00Z",
        }
        cutover_bytes = b'{"state":"switched"}\n'
        cutover_sha = hashlib.sha256(cutover_bytes).hexdigest()
        pending = build_acceptance_evidence(
            mode="production",
            expected_commit="a" * 40,
            web_build_identity="b" * 64,
            weapp_build_identity="c" * 64,
            cutover_evidence_sha256=cutover_sha,
            machine_evidence=machine,
            route_report={"testedRoutes": ROUTES, "status": "passed", "evidenceHash": "1" * 64},
            accepted_at="2026-09-04T03:01:00Z",
            service_restart_report={"status": "passed", "evidenceHash": "2" * 64},
            user_confirmation=False,
        )

        self.assertEqual(pending["status"], "production_dual_client_acceptance_pending_user_confirmation")
        self.assertEqual(pending["userConfirmation"]["status"], "pending")
        with self.assertRaisesRegex(AcceptanceEvidenceError, "USER_CONFIRMATION_REQUIRED"):
            finalize_production_acceptance(pending, confirmation_at="2026-09-04T03:02:00Z")

        accepted = finalize_production_acceptance(
            pending,
            confirmation_at="2026-09-04T03:02:00Z",
            confirmation_token="I_HAVE_TESTED_PRODUCTION",
        )
        self.assertEqual(accepted["status"], "production_dual_client_acceptance_passed")
        self.assertEqual(accepted["userConfirmation"]["status"], "accepted")


if __name__ == "__main__":
    unittest.main()

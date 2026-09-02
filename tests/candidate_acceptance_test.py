import hashlib
import json
import unittest
from datetime import datetime, timezone
from uuid import UUID

from server.accept_chickenbro_candidate import (
    AcceptanceError,
    AcceptanceSeed,
    ApiResponse,
    CandidateHttpGateway,
    PostgresAcceptanceSeeder,
    run_candidate_acceptance,
)


PRIMARY_USER = UUID("00000000-0000-4000-8000-000000000001")
OTHER_USER = UUID("00000000-0000-4000-8000-000000000002")
SNAPSHOT = UUID("00000000-0000-4000-8000-000000000030")
WEB_LOGIN = UUID("00000000-0000-4000-8000-000000000040")
MINI_CONVERSATION = "00000000-0000-4000-8000-0000000000a1"
WEB_CONVERSATION = "00000000-0000-4000-8000-0000000000a2"
MINI_JOB = "00000000-0000-4000-8000-0000000000b1"
WEB_JOB = "00000000-0000-4000-8000-0000000000b2"
MINI_RESULT = "00000000-0000-4000-8000-0000000000c1"
WEB_RESULT = "00000000-0000-4000-8000-0000000000c2"
COMPILER_REVISION = "chickenbro-simc-compiler-v1"
RUNTIME_REVISION = "simc:test-runtime"


class FakeCandidateApi:
    def __init__(self, *, leak_owner=False, malformed_stream=False, malformed_simc=False):
        self.leak_owner = leak_owner
        self.malformed_stream = malformed_stream
        self.malformed_simc = malformed_simc
        self.web_exchanged = False
        self.web_logged_out = False
        self.conversations = []
        self.messages = {}
        self.jobs = []
        self.job_inputs = {}
        self.stream_calls = []

    def exchange_web(self, session_id, browser_verifier):
        self.assert_secret_inputs(session_id, browser_verifier)
        self.web_exchanged = True
        return ApiResponse(200, {"authenticated": True})

    def replay_web_exchange(self, session_id, browser_verifier):
        self.assert_secret_inputs(session_id, browser_verifier)
        return ApiResponse(409, {"error": {"code": "WEB_LOGIN_ALREADY_CONSUMED"}})

    @staticmethod
    def assert_secret_inputs(session_id, browser_verifier):
        if session_id != WEB_LOGIN or browser_verifier != "V" * 43:
            raise AssertionError("unexpected Web exchange input")

    def web_csrf_token(self):
        return "csrf-token"

    def request(self, transport, method, path, *, body=None, headers=None):
        headers = headers or {}
        if transport == "web" and method != "GET":
            if headers.get("X-CSRF-Token") != "csrf-token":
                raise AssertionError("missing Web CSRF token")
        if path.endswith("/me"):
            if transport == "web" and self.web_logged_out:
                return ApiResponse(401, {"code": "AUTH_REQUIRED"})
            return ApiResponse(200, {"connected": True, "displayName": "same-owner"})
        if path.endswith("/auth/logout"):
            self.web_logged_out = True
            return ApiResponse(200, {"loggedOut": True})
        if path.endswith("/chat/conversations") and method == "POST":
            identifier = MINI_CONVERSATION if transport == "mini" else WEB_CONVERSATION
            self.conversations.append(identifier)
            self.messages[identifier] = []
            return ApiResponse(201, {"id": identifier})
        if path.endswith("/chat/conversations"):
            visible = self.conversations if transport != "other" or self.leak_owner else []
            return ApiResponse(200, {"items": [{"id": item} for item in visible], "nextCursor": None})
        if "/chat/conversations/" in path:
            identifier = path.rsplit("/", 1)[-1]
            if transport == "other":
                return ApiResponse(404, {"error": {"code": "CONVERSATION_NOT_FOUND"}})
            return ApiResponse(200, {"id": identifier, "messages": list(self.messages[identifier])})
        if path.endswith("/simc/jobs") and method == "POST":
            identifier = MINI_JOB if transport == "mini" else WEB_JOB
            self.jobs.append(identifier)
            scenario_hash = hashlib.sha256(json.dumps(
                body["scenario"], ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()
            self.job_inputs[identifier] = scenario_hash
            return ApiResponse(202, {
                "id": identifier,
                "snapshotId": str(SNAPSHOT),
                "status": "queued",
                "scenarioHash": scenario_hash,
                "compilerRevision": COMPILER_REVISION,
                "runtimeRevision": RUNTIME_REVISION,
                "attempts": [],
                "result": None,
            })
        if path.endswith("/simc/jobs"):
            visible = self.jobs if transport != "other" or self.leak_owner else []
            return ApiResponse(200, {"items": [{"id": item} for item in visible], "nextCursor": None})
        if "/simc/jobs/" in path:
            identifier = path.rsplit("/", 1)[-1]
            if transport == "other":
                return ApiResponse(404, {"error": {"code": "SIMULATION_NOT_FOUND"}})
            if self.malformed_simc:
                return ApiResponse(200, {
                    "id": identifier,
                    "snapshotId": str(SNAPSHOT),
                    "status": "succeeded",
                    "scenarioHash": self.job_inputs[identifier],
                    "compilerRevision": COMPILER_REVISION,
                    "runtimeRevision": RUNTIME_REVISION,
                    "attempts": [{"attemptNumber": 1, "exitCode": 0, "diagnosticCode": "SUCCEEDED"}],
                    "result": {
                        "id": MINI_RESULT if identifier == MINI_JOB else WEB_RESULT,
                        "profileSha256": "d" * 64,
                        "metricName": "dps",
                        "metricValue": 123.0,
                        "compilerRevision": COMPILER_REVISION,
                        "runtimeRevision": RUNTIME_REVISION,
                    },
                })
            profile_sha = "d" * 64 if identifier == MINI_JOB else "e" * 64
            result_id = MINI_RESULT if identifier == MINI_JOB else WEB_RESULT
            scenario_hash = self.job_inputs[identifier]
            return ApiResponse(200, {
                "id": identifier,
                "snapshotId": str(SNAPSHOT),
                "status": "succeeded",
                "scenarioHash": scenario_hash,
                "compilerRevision": COMPILER_REVISION,
                "runtimeRevision": RUNTIME_REVISION,
                "attempts": [{"attemptNumber": 1, "exitCode": 0, "diagnosticCode": "SUCCEEDED"}],
                "result": {
                    "id": result_id,
                    "profileSha256": profile_sha,
                    "metricName": "dps",
                    "metricValue": 123.0,
                    "compilerRevision": COMPILER_REVISION,
                    "runtimeRevision": RUNTIME_REVISION,
                    "provenance": {
                        "snapshotId": str(SNAPSHOT),
                        "sourceRevision": "source:test-revision",
                        "sourceRawSha256": "f" * 64,
                        "profileSha256": profile_sha,
                        "compilerRevision": COMPILER_REVISION,
                        "runtimeRevision": RUNTIME_REVISION,
                        "scenarioHash": scenario_hash,
                    },
                },
            })
        raise AssertionError((transport, method, path, body, headers))

    def stream_message(self, transport, path, *, body, headers):
        identifier = path.split("/chat/conversations/", 1)[1].split("/", 1)[0]
        key = headers["Idempotency-Key"]
        if transport == "web" and headers.get("X-CSRF-Token") != "csrf-token":
            raise AssertionError("missing Web CSRF token")
        if (identifier, key) not in self.stream_calls:
            self.stream_calls.append((identifier, key))
            self.messages[identifier].extend([
                {"role": "user", "content": body["content"]},
                {"role": "assistant", "content": "acknowledged"},
            ])
        events = [
            {"type": "started", "sequence": 1},
            {"type": "delta", "sequence": 2, "text": "acknowledged"},
            {"type": "completed", "sequence": 3},
        ]
        if self.malformed_stream:
            events = [{key: value for key, value in event.items() if key != "sequence"} for event in events]
        return ApiResponse(200, {"events": events})


class CandidateAcceptanceTest(unittest.TestCase):
    def seed(self):
        return AcceptanceSeed(
            primary_user_id=PRIMARY_USER,
            other_user_id=OTHER_USER,
            ready_snapshot_id=SNAPSHOT,
            mini_token="mini-secret-token",
            other_mini_token="other-secret-token",
            web_login_session_id=WEB_LOGIN,
            browser_verifier="V" * 43,
        )

    def test_cross_transport_acceptance_is_owner_scoped_and_redacted(self):
        api = FakeCandidateApi()
        evidence = run_candidate_acceptance(
            self.seed(),
            api,
            expected_commit="a" * 40,
            web_build_identity="b" * 64,
            weapp_build_identity="c" * 64,
            clock=lambda: datetime(2026, 9, 3, tzinfo=timezone.utc),
            sleep=lambda _seconds: None,
        )

        self.assertEqual(evidence["status"], "automated_candidate_acceptance_passed")
        self.assertEqual(evidence["realWechatQrAcceptance"], "pending")
        self.assertTrue(evidence["checks"]["miniCreatedWebVisibleChat"])
        self.assertTrue(evidence["checks"]["webCreatedMiniVisibleChat"])
        self.assertTrue(evidence["checks"]["miniCreatedWebVisibleSimc"])
        self.assertTrue(evidence["checks"]["webCreatedMiniVisibleSimc"])
        self.assertTrue(evidence["checks"]["ticketReplayRejected"])
        self.assertTrue(evidence["checks"]["logoutIndependent"])
        self.assertTrue(evidence["checks"]["ownerIsolation"])
        self.assertEqual(len(api.stream_calls), 2)

        serialized = json.dumps(evidence, sort_keys=True)
        for secret in (
            str(PRIMARY_USER),
            str(OTHER_USER),
            str(SNAPSHOT),
            str(WEB_LOGIN),
            MINI_CONVERSATION,
            WEB_CONVERSATION,
            MINI_JOB,
            WEB_JOB,
            "mini-secret-token",
            "other-secret-token",
            "V" * 43,
            "csrf-token",
            "candidate-acceptance",
        ):
            self.assertNotIn(secret, serialized)

    def test_owner_visibility_leak_fails_closed(self):
        with self.assertRaisesRegex(AcceptanceError, "OWNER_ISOLATION_FAILED"):
            run_candidate_acceptance(
                self.seed(),
                FakeCandidateApi(leak_owner=True),
                expected_commit="a" * 40,
                web_build_identity="b" * 64,
                weapp_build_identity="c" * 64,
                sleep=lambda _seconds: None,
            )

    def test_stream_without_sequence_fails_closed(self):
        with self.assertRaisesRegex(AcceptanceError, "CHAT_STREAM_SEQUENCE_INVALID"):
            run_candidate_acceptance(
                self.seed(),
                FakeCandidateApi(malformed_stream=True),
                expected_commit="a" * 40,
                web_build_identity="b" * 64,
                weapp_build_identity="c" * 64,
                sleep=lambda _seconds: None,
            )

    def test_simc_result_without_bound_provenance_fails_closed(self):
        with self.assertRaisesRegex(AcceptanceError, "SIMC_PROVENANCE_INVALID"):
            run_candidate_acceptance(
                self.seed(),
                FakeCandidateApi(malformed_simc=True),
                expected_commit="a" * 40,
                web_build_identity="b" * 64,
                weapp_build_identity="c" * 64,
                sleep=lambda _seconds: None,
            )

    def test_http_gateway_accepts_crlf_delimited_sse(self):
        gateway = CandidateHttpGateway(self.seed())
        gateway._send_raw = lambda *_args, **_kwargs: (
            200,
            "text/event-stream; charset=utf-8",
            b'data: {"type":"started","sequence":1}\r\n\r\n'
            b'data: {"type":"completed","sequence":2}\r\n\r\n',
        )

        response = gateway.stream_message(
            "mini",
            "/api/v2-candidate/chat/conversations/00000000-0000-4000-8000-0000000000a1/messages/stream",
            body={"content": "test", "clientMessageId": "test-client"},
            headers={"Idempotency-Key": "test-message"},
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [event["type"] for event in response.payload["events"]],
            ["started", "completed"],
        )

    def test_postgres_seed_uses_a_migrated_supported_elemental_snapshot(self):
        calls = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, query, params=()):
                calls.append((" ".join(query.split()), params))

            def fetchone(self):
                query = calls[-1][0]
                if "current_database()" in query:
                    return ("chickenbro_candidate",)
                if "FROM simc.source_snapshots" in query:
                    return (str(PRIMARY_USER), str(SNAPSHOT))
                raise AssertionError(query)

        class Connection:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def cursor():
                return Cursor()

        seed = PostgresAcceptanceSeeder(Connection).seed(
            expected_database="chickenbro_candidate",
            app_context="wx-reviewed",
            now=datetime(2026, 9, 3, tzinfo=timezone.utc),
        )

        self.assertEqual(seed.primary_user_id, PRIMARY_USER)
        snapshot_query = next(call for call in calls if "FROM simc.source_snapshots" in call[0])
        self.assertIn("snapshot_json #>> '{character,classKey}'", snapshot_query[0])
        self.assertIn("snapshot_json #>> '{character,specKey}'", snapshot_query[0])
        self.assertEqual(snapshot_query[1], ("shaman", "elemental", "wx-reviewed"))


if __name__ == "__main__":
    unittest.main()

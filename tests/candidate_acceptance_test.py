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
    def __init__(
        self,
        *,
        leak_owner=False,
        malformed_stream=False,
        malformed_simc=False,
        snapshot_unavailable_attempts=0,
    ):
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
        self.created_snapshot = False
        self.snapshot_calls = 0
        self.snapshot_unavailable_attempts = snapshot_unavailable_attempts

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
        if path.endswith("/simc/snapshots") and method == "POST":
            self.snapshot_calls += 1
            self.created_snapshot = True
            if self.snapshot_calls <= self.snapshot_unavailable_attempts:
                return ApiResponse(201, {
                    "id": str(SNAPSHOT),
                    "provider": "raiderio",
                    "readiness": "SNAPSHOT_UNAVAILABLE",
                    "missingFields": [],
                    "blockers": ["SNAPSHOT_UNAVAILABLE"],
                    "provenance": {
                        "sourceRevision": None,
                        "sourceRawSha256": None,
                    },
                })
            return ApiResponse(201, {
                "id": str(SNAPSHOT),
                "provider": "raiderio",
                "readiness": "READY_FOR_SIMC",
                "missingFields": [],
                "blockers": [],
                "provenance": {
                    "sourceRevision": "blizzard-profile:test",
                    "sourceRawSha256": "f" * 64,
                },
            })
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

    def seed_without_snapshot(self):
        return AcceptanceSeed(
            primary_user_id=PRIMARY_USER,
            other_user_id=OTHER_USER,
            ready_snapshot_id=None,
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

    def test_acceptance_creates_and_validates_a_live_source_snapshot_when_not_preseeded(self):
        api = FakeCandidateApi()
        evidence = run_candidate_acceptance(
            self.seed_without_snapshot(),
            api,
            expected_commit="a" * 40,
            web_build_identity="b" * 64,
            weapp_build_identity="c" * 64,
            source_url="https://raider.io/characters/eu/taerar/PublicSample",
            sleep=lambda _seconds: None,
        )

        self.assertTrue(api.created_snapshot)
        self.assertFalse(evidence["transportScope"]["migratedReadySnapshot"])
        self.assertTrue(evidence["transportScope"]["liveSourceSnapshot"])

    def test_acceptance_retries_transient_source_unavailability_but_keeps_the_snapshot_live(self):
        api = FakeCandidateApi(snapshot_unavailable_attempts=1)
        evidence = run_candidate_acceptance(
            self.seed_without_snapshot(),
            api,
            expected_commit="a" * 40,
            web_build_identity="b" * 64,
            weapp_build_identity="c" * 64,
            source_url="https://raider.io/characters/eu/taerar/PublicSample",
            sleep=lambda _seconds: None,
        )

        self.assertEqual(api.snapshot_calls, 2)
        self.assertTrue(evidence["transportScope"]["liveSourceSnapshot"])

    def test_acceptance_requires_a_source_url_when_the_seed_has_no_snapshot(self):
        with self.assertRaisesRegex(AcceptanceError, "SIMC_SOURCE_URL_REQUIRED"):
            run_candidate_acceptance(
                self.seed_without_snapshot(),
                FakeCandidateApi(),
                expected_commit="a" * 40,
                web_build_identity="b" * 64,
                weapp_build_identity="c" * 64,
                sleep=lambda _seconds: None,
            )

    def test_acceptance_core_can_target_the_formal_production_prefix(self):
        api = FakeCandidateApi()
        gateway = CandidateHttpGateway(
            self.seed(),
            www_origin="https://www.chickenbro.cloud",
            api_origin="https://api.chickenbro.cloud",
            prefix="/api/v2",
            csrf_cookie_name="__Host-chickenbro-csrf",
        )
        evidence = run_candidate_acceptance(
            self.seed(),
            api,
            expected_commit="a" * 40,
            web_build_identity="b" * 64,
            weapp_build_identity="c" * 64,
            prefix="/api/v2",
            sleep=lambda _seconds: None,
        )

        self.assertEqual(evidence["status"], "automated_candidate_acceptance_passed")
        self.assertEqual(gateway._prefix, "/api/v2")

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

    def test_postgres_seed_uses_an_active_wechat_owner_without_requiring_a_simc_snapshot(self):
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
                if "FROM identity.users" in query and "user_identities" in query:
                    return (str(PRIMARY_USER),)
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
        self.assertIsNone(seed.ready_snapshot_id)
        owner_query = next(call for call in calls if "FROM identity.users" in call[0])
        self.assertIn("JOIN identity.user_identities", owner_query[0])
        self.assertIn("provider = 'wechat_mini'", owner_query[0])
        self.assertEqual(owner_query[1], ("wx-reviewed",))
        self.assertFalse(any("FROM simc.source_snapshots" in query for query, _ in calls))

    def test_postgres_seed_can_bind_the_latest_ready_snapshot_for_production(self):
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
                    return ("chickenbro_prod",)
                if "FROM identity.users" in query and "user_identities" in query:
                    return (str(PRIMARY_USER),)
                if "FROM simc.source_snapshots" in query:
                    return (str(SNAPSHOT),)
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
            expected_database="chickenbro_prod",
            app_context="wx-reviewed",
            now=datetime(2026, 9, 3, tzinfo=timezone.utc),
            use_latest_ready_snapshot=True,
        )

        self.assertEqual(seed.ready_snapshot_id, SNAPSHOT)
        snapshot_query = next(call for call in calls if "FROM simc.source_snapshots" in call[0])
        self.assertIn("readiness = 'READY_FOR_SIMC'", snapshot_query[0])


if __name__ == "__main__":
    unittest.main()

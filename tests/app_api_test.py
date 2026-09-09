import unittest

from fastapi.testclient import TestClient

from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ComponentState, ReadinessRegistry
from server.app.platform.health import default_readiness_registry


class AppApiTest(unittest.TestCase):
    def setUp(self):
        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
            host="127.0.0.1",
            port=8790,
        )
        registry = ReadinessRegistry({
            "database": lambda: ComponentState("ready", ""),
            "worker": lambda: ComponentState("unconfigured", "WORKER_NOT_CONFIGURED"),
        })
        self.client = TestClient(create_app(settings=settings, readiness_registry=registry))

    def test_liveness_is_separate_from_business_readiness(self):
        live = self.client.get("/health")
        ready = self.client.get("/api/v2/health/readiness")
        self.assertEqual(live.json()["status"], "ok")
        self.assertEqual(ready.json()["status"], "partial")
        self.assertEqual(ready.json()["components"]["worker"]["status"], "unconfigured")

    def test_request_id_is_returned_and_invalid_ids_are_replaced(self):
        response = self.client.get("/health", headers={"X-Request-Id": "../../secret"})
        request_id = response.headers["X-Request-Id"]
        self.assertRegex(request_id, r"^[0-9a-f-]{36}$")
        self.assertEqual(response.json()["requestId"], request_id)

    def test_probe_failures_use_a_bounded_public_state(self):
        def exploding_probe():
            raise RuntimeError("database password should never be public")

        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
        )
        registry = ReadinessRegistry({"database": exploding_probe})
        response = TestClient(create_app(settings=settings, readiness_registry=registry)).get(
            "/api/v2/health/readiness"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "blocked")
        self.assertEqual(response.json()["components"]["database"], {
            "status": "blocked",
            "code": "PROBE_FAILED",
        })
        self.assertNotIn("password", response.text)

    def test_unknown_routes_use_the_stable_error_envelope(self):
        response = self.client.get("/api/v2/missing")
        request_id = response.headers["X-Request-Id"]
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {
            "error": {
                "code": "NOT_FOUND",
                "message": "resource not found",
                "requestId": request_id,
            }
        })

    def test_internal_source_gateway_is_registered_but_requires_capability(self):
        response = self.client.post(
            "/api/v2/internal/chickenbro/source-query",
            json={
                "provider": "raiderio",
                "target": "https://raider.io/characters/us/area-52/Test",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["error"]["code"],
            "SOURCE_GATEWAY_UNAUTHORIZED",
        )

    def test_simulation_tool_http_rejects_missing_capability_and_identity_body(self):
        url = '/api/v2/internal/chickenbro/simc-tool'
        response = self.client.post(url, json={'operation': 'list', 'arguments': {}})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'SIMULATION_TOOL_UNAUTHORIZED')
        response = self.client.post(url, json={'operation': 'list', 'arguments': {}, 'userId': 'forged'})
        self.assertEqual(response.status_code, 422)

    def test_simulation_tool_http_uses_same_gateway_and_revoke(self):
        from uuid import uuid4
        from server.app.chickenbro.simulation_tools import SimulationToolContext, SimulationToolGateway
        from server.app.identity.domain import Principal
        from server.app.simulation.application import SimulationJobPage
        from types import SimpleNamespace
        calls = []
        principal = Principal(uuid4(), 'web_cookie')
        gateway = SimulationToolGateway(SimpleNamespace(list_jobs=lambda owner, cursor, limit: (
            calls.append(owner) or SimulationJobPage((), None))))
        self.client.app.state.chickenbro_simulation_gateway = gateway
        token = gateway.issue_capability(SimulationToolContext(principal, uuid4(), uuid4()))
        url = '/api/v2/internal/chickenbro/simc-tool'
        headers = {'X-Chickenbro-Simulation-Gateway': token}
        response = self.client.post(url, headers=headers, json={'operation': 'list', 'arguments': {}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [principal])
        gateway.revoke(token)
        self.assertEqual(self.client.post(url, headers=headers, json={'operation': 'list', 'arguments': {}}).status_code, 401)

    def test_production_disables_interactive_api_docs(self):
        settings = AppSettings(
            environment="production",
            database_url="postgresql://redacted",
        )
        app = create_app(settings=settings, readiness_registry=ReadinessRegistry({}))
        self.assertIsNone(app.docs_url)
        self.assertIsNone(app.redoc_url)
        self.assertIsNone(app.openapi_url)

    def test_research_batch_http_contract_and_capability_revocation(self):
        from server.app.chickenbro.source_gateway import ChickenbroSourceGateway
        from types import SimpleNamespace
        calls = []
        gateway = ChickenbroSourceGateway(query_service=SimpleNamespace(query=lambda provider, target, options: (
            calls.append((provider, target, options)) or {"status": "source_reference", "facts": []}
        )))
        self.client.app.state.chickenbro_source_gateway = gateway
        token = gateway.issue_capability()
        headers = {"X-Chickenbro-Source-Gateway": token}
        body = {"provider": "raiderio_batch", "target": "characters", "options": {
            "targets": ["https://raider.io/characters/us/area-52/Test"]}}
        url = "/api/v2/internal/chickenbro/source-query"
        response = self.client.post(url, json=body, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls[0][2], body["options"])
        gateway.revoke(token)
        self.assertEqual(self.client.post(url, json=body, headers=headers).status_code, 401)
        self.assertEqual(len(calls), 1)

    def test_research_http_options_reject_boolean_and_nested_objects(self):
        url = "/api/v2/internal/chickenbro/source-query"
        for value in (True, {"unexpected": "nested"}, [False]):
            with self.subTest(value=value):
                response = self.client.post(url, json={"provider": "raiderio_rankings",
                    "target": "rankings", "options": {"limit": value}})
                self.assertEqual(response.status_code, 422)

    def test_default_readiness_reports_qq_configuration_without_network_calls(self):
        settings = AppSettings(
            environment="test",
            database_url="postgresql://redacted",
        )
        states = default_readiness_registry(settings).check_all()
        self.assertEqual(states["qq_connect"], ComponentState("unconfigured", "QQ_NOT_CONFIGURED"))

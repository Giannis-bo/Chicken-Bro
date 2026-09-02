import json
import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from server.app.main import create_app
from server.app.platform.config import AppSettings
from server.app.platform.health import ReadinessRegistry
from server.app.simulation.application import SimulationApplication
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.sources import CharacterSourceRouter
from tests.app_chat_api_test import (
    FakeFormalAuthApplication,
    mini_headers,
    web_cookies,
    web_write_headers,
)
from tests.app_simulation_application_test import (
    FakeGateway,
    MemoryQueue,
    MemorySimulationRepository,
)


def build_simc_test_client():
    now = datetime(2026, 9, 3, 11, 0, tzinfo=timezone.utc)
    capabilities = SimcRuntimeCapabilities(
        runtime_revision="simc:current:abc",
        compiler_revision="chickenbro-simc-compiler-v1",
        supported_specs=frozenset({("shaman", "elemental")}),
    )
    repository = MemorySimulationRepository()
    queue = MemoryQueue()
    simulation = SimulationApplication(
        repository=repository,
        source_router=CharacterSourceRouter(FakeGateway()),
        readiness_validator=SimcReadinessValidator(),
        compiler=SimcProfileCompiler(capabilities=capabilities),
        runtime_capabilities=capabilities,
        queue=queue,
        clock=lambda: now,
    )
    settings = AppSettings(
        environment="test",
        database_url="postgresql://redacted",
        web_origin="https://www.chickenbro.cloud",
    )
    app = create_app(
        settings=settings,
        readiness_registry=ReadinessRegistry({}),
        web_auth_application=FakeFormalAuthApplication(),
        chat_application=object(),
        simulation_application=simulation,
        prototype_identity_application=object(),
        prototype_chat_application=object(),
        prototype_simulation_application=simulation,
    )
    return TestClient(app, base_url="https://www.chickenbro.cloud"), repository, queue


class FormalSimcApiTest(unittest.TestCase):
    def setUp(self):
        self.client, self.repository, self.queue = build_simc_test_client()

    def tearDown(self):
        self.client.close()

    def create_snapshot(self):
        return self.client.post(
            "/api/v2/simc/snapshots",
            headers=mini_headers(),
            json={"sourceUrl": "https://raider.io/characters/us/area-52/Stormsample"},
        )

    def test_formal_simc_routes_are_registered(self):
        paths = set(self.client.app.openapi()["paths"])

        self.assertIn("/api/v2/simc/snapshots", paths)
        self.assertIn("/api/v2/simc/snapshots/{snapshot_id}", paths)
        self.assertIn("/api/v2/simc/jobs", paths)
        self.assertIn("/api/v2/simc/jobs/{job_id}", paths)

    def test_snapshot_response_is_bounded_and_never_exposes_raw_source_or_owner(self):
        response = self.create_snapshot()

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["provider"], "raiderio")
        self.assertEqual(payload["readiness"], "READY_FOR_SIMC")
        self.assertEqual(payload["missingFields"], [])
        self.assertEqual(payload["blockers"], [])
        encoded = json.dumps(payload)
        for forbidden in (
            '"snapshot"',
            '"rawSha256"',
            '"userId"',
            '"user_id"',
            '"gear"',
            '"talents"',
        ):
            self.assertNotIn(forbidden, encoded)

    def test_web_mutation_requires_origin_and_csrf(self):
        missing_origin = self.client.post(
            "/api/v2/simc/snapshots",
            cookies=web_cookies(csrf=True),
            json={"sourceUrl": "https://raider.io/characters/us/area-52/Stormsample"},
        )
        missing_csrf = self.client.post(
            "/api/v2/simc/snapshots",
            headers=web_write_headers(csrf=False),
            cookies=web_cookies(),
            json={"sourceUrl": "https://raider.io/characters/us/area-52/Stormsample"},
        )

        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(missing_origin.json()["error"]["code"], "ORIGIN_REJECTED")
        self.assertEqual(missing_csrf.status_code, 403)
        self.assertEqual(missing_csrf.json()["error"]["code"], "CSRF_REJECTED")


if __name__ == "__main__":
    unittest.main()

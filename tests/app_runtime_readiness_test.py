import hashlib
import json
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from server.app.platform.config import AppSettings
from server.app.platform.health import (
    ComponentState,
    codex_probe,
    default_readiness_registry,
    raiderio_probe,
    simc_probe,
    warcraftlogs_probe,
    worker_probe,
)
from server.app.platform.worker_heartbeat import WorkerHeartbeatWriter
from server.app.simulation.readiness import SimcRuntimeCapabilities


NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


class AppRuntimeReadinessTest(unittest.TestCase):
    def _settings(self, heartbeat_path: Path, *, environment: str = "candidate") -> AppSettings:
        return AppSettings(
            environment=environment,
            database_url="postgresql://redacted",
            worker_heartbeat_path=str(heartbeat_path),
            worker_heartbeat_ttl_seconds=45,
        )

    def test_worker_heartbeat_is_atomic_private_and_environment_scoped(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "candidate-worker-heartbeat.json"
            writer = WorkerHeartbeatWriter(
                path=path,
                environment="candidate",
                worker_id="chickenbro-simc-candidate-worker",
                clock=lambda: NOW,
            )

            writer.write()

            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "schemaVersion": "chickenbro-worker-heartbeat-v1",
                    "environment": "candidate",
                    "workerId": "chickenbro-simc-candidate-worker",
                    "updatedAt": "2026-09-03T12:00:00Z",
                },
            )
            self.assertEqual(
                worker_probe(self._settings(path), now=lambda: NOW),
                ComponentState("ready", ""),
            )
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_worker_probe_rejects_missing_stale_wrong_environment_and_symlink_state(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            path = directory / "candidate-worker-heartbeat.json"
            settings = self._settings(path)
            self.assertEqual(
                worker_probe(settings, now=lambda: NOW),
                ComponentState("blocked", "WORKER_HEARTBEAT_MISSING"),
            )

            WorkerHeartbeatWriter(
                path=path,
                environment="candidate",
                worker_id="chickenbro-simc-candidate-worker",
                clock=lambda: NOW - timedelta(seconds=46),
            ).write()
            self.assertEqual(
                worker_probe(settings, now=lambda: NOW),
                ComponentState("blocked", "WORKER_HEARTBEAT_STALE"),
            )

            WorkerHeartbeatWriter(
                path=path,
                environment="production",
                worker_id="chickenbro-simc-worker",
                clock=lambda: NOW,
            ).write()
            self.assertEqual(
                worker_probe(settings, now=lambda: NOW),
                ComponentState("blocked", "WORKER_HEARTBEAT_INVALID"),
            )

            WorkerHeartbeatWriter(
                path=path,
                environment="candidate",
                worker_id="wrong-candidate-worker",
                clock=lambda: NOW,
            ).write()
            self.assertEqual(
                worker_probe(settings, now=lambda: NOW),
                ComponentState("blocked", "WORKER_HEARTBEAT_INVALID"),
            )

            target = directory / "target.json"
            WorkerHeartbeatWriter(
                path=target,
                environment="candidate",
                worker_id="chickenbro-simc-candidate-worker",
                clock=lambda: NOW,
            ).write()
            path.unlink()
            path.symlink_to(target)
            self.assertEqual(
                worker_probe(settings, now=lambda: NOW),
                ComponentState("blocked", "WORKER_HEARTBEAT_INVALID"),
            )

    def test_codex_probe_binds_enabled_binary_to_configured_sha256(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            binary = Path(raw_directory) / "codex"
            binary.write_bytes(b"exact-codex-runtime")
            binary.chmod(0o755)
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            environment = {
                "WOW_CHICKENBRO_CODEX_ENABLED": "1",
                "WOW_CODEX_BIN": str(binary),
                "WOW_CODEX_RUNTIME_REVISION": f"codex:sha256:{digest}",
            }

            self.assertEqual(codex_probe(environment), ComponentState("ready", ""))
            self.assertEqual(
                codex_probe({**environment, "WOW_CODEX_RUNTIME_REVISION": "codex:sha256:" + "0" * 64}),
                ComponentState("blocked", "CODEX_IDENTITY_MISMATCH"),
            )
            self.assertEqual(
                codex_probe({**environment, "WOW_CHICKENBRO_CODEX_ENABLED": "0"}),
                ComponentState("unconfigured", "CODEX_NOT_CONFIGURED"),
            )

    def test_source_probes_are_local_configuration_checks_only(self):
        self.assertEqual(
            raiderio_probe(module_available=lambda name: name == "httpx"),
            ComponentState("ready", ""),
        )
        self.assertEqual(
            raiderio_probe(module_available=lambda _name: False),
            ComponentState("blocked", "RAIDERIO_DEPENDENCY_MISSING"),
        )
        self.assertEqual(
            warcraftlogs_probe({}),
            ComponentState("unconfigured", "WARCRAFTLOGS_NOT_CONFIGURED"),
        )
        self.assertEqual(
            warcraftlogs_probe({"WOW_WARCRAFTLOGS_CLIENT_ID": "id-only"}),
            ComponentState("blocked", "WARCRAFTLOGS_CREDENTIALS_INVALID"),
        )
        self.assertEqual(
            warcraftlogs_probe({
                "WOW_WARCRAFTLOGS_CLIENT_ID": "client",
                "WOW_WARCRAFTLOGS_CLIENT_SECRET": "secret",
            }),
            ComponentState("ready", ""),
        )

    def test_simc_probe_binds_managed_commit_binary_and_supported_specs(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            root = Path(raw_directory) / "wow-simc"
            commit = "a" * 40
            release = root / "releases" / commit
            release.mkdir(parents=True)
            binary = release / "simc"
            binary.write_bytes(b"exact-simc-runtime")
            binary.chmod(0o755)
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            (release / ".commit").write_text(commit + "\n", encoding="utf-8")
            (release / "binary.sha256").write_text(digest + "\n", encoding="utf-8")
            (release / "source-archive.sha256").write_text("b" * 64 + "\n", encoding="utf-8")
            (root / "current").symlink_to(Path("releases") / commit)
            environment = {
                "WOW_SIMC_BIN": str(root / "current" / "simc"),
                "WOW_SIMC_SUPPORTED_SPECS": "shaman:elemental",
            }

            expected_revision = f"simc:managed:{commit}:{digest}"
            self.assertEqual(
                SimcRuntimeCapabilities.from_env(environment).runtime_revision,
                expected_revision,
            )
            self.assertEqual(simc_probe(environment), ComponentState("ready", ""))
            self.assertEqual(
                simc_probe({**environment, "WOW_SIMC_RUNTIME_REVISION": "simc:stale"}),
                ComponentState("blocked", "SIMC_IDENTITY_MISMATCH"),
            )

            (release / "binary.sha256").write_text("0" * 64 + "\n", encoding="utf-8")
            self.assertEqual(
                simc_probe(environment),
                ComponentState("blocked", "SIMC_IDENTITY_MISMATCH"),
            )
            self.assertEqual(
                simc_probe({"WOW_SIMC_BIN": str(binary), "WOW_SIMC_SUPPORTED_SPECS": ""}),
                ComponentState("unconfigured", "SIMC_NOT_CONFIGURED"),
            )

    def test_default_registry_can_be_fully_ready_without_external_provider_calls(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            heartbeat = directory / "candidate-worker-heartbeat.json"
            WorkerHeartbeatWriter(
                path=heartbeat,
                environment="candidate",
                worker_id="chickenbro-simc-candidate-worker",
                clock=lambda: datetime.now(timezone.utc),
            ).write()

            codex = directory / "codex"
            codex.write_bytes(b"codex-runtime")
            codex.chmod(0o755)
            codex_sha = hashlib.sha256(codex.read_bytes()).hexdigest()

            simc_root = directory / "wow-simc"
            commit = "c" * 40
            release = simc_root / "releases" / commit
            release.mkdir(parents=True)
            simc = release / "simc"
            simc.write_bytes(b"simc-runtime")
            simc.chmod(0o755)
            simc_sha = hashlib.sha256(simc.read_bytes()).hexdigest()
            (release / ".commit").write_text(commit + "\n", encoding="utf-8")
            (release / "binary.sha256").write_text(simc_sha + "\n", encoding="utf-8")
            (release / "source-archive.sha256").write_text("d" * 64 + "\n", encoding="utf-8")
            (simc_root / "current").symlink_to(Path("releases") / commit)

            settings = AppSettings(
                environment="candidate",
                database_url="postgresql://redacted",
                worker_heartbeat_path=str(heartbeat),
                worker_heartbeat_ttl_seconds=45,
                qq_appid="1905584243",
                qq_redirect_uri="https://www.chickenbro.cloud/api/v2-candidate/auth/qq/callback",
                qq_app_key="secret",
            )
            environment = {
                "WOW_APP_ENV": "candidate",
                "WOW_CHICKENBRO_CODEX_ENABLED": "1",
                "WOW_CODEX_BIN": str(codex),
                "WOW_CODEX_RUNTIME_REVISION": f"codex:sha256:{codex_sha}",
                "WOW_WARCRAFTLOGS_CLIENT_ID": "client",
                "WOW_WARCRAFTLOGS_CLIENT_SECRET": "secret",
                "WOW_SIMC_BIN": str(simc_root / "current" / "simc"),
                "WOW_SIMC_SUPPORTED_SPECS": "shaman:elemental",
            }
            with patch(
                "server.app.platform.health.database_probe",
                return_value=lambda: ComponentState("ready", ""),
            ), patch(
                "server.app.platform.health.raiderio_probe",
                return_value=ComponentState("ready", ""),
            ):
                registry = default_readiness_registry(settings, environment)
                states = registry.check_all()

            self.assertEqual(registry.overall_status(states), "ready")
            self.assertTrue(all(state == ComponentState("ready", "") for state in states.values()))


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import signal
import re
import time
import tomllib
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol

from server.app.chickenbro.stream import CodexStreamError
from server.app.chickenbro.codex_stdio import CodexStdioSession
from server.codex_worker import (
    DEFAULT_CODEX_BIN,
    DEFAULT_JOBS_DIR,
)


_AGENT_RULES_PATH = Path(__file__).resolve().parent / "agent" / "AGENTS.md"
_MAX_AGENT_RULES_BYTES = 32768


def _load_profile(profile: str | None, *, allow_simulation: bool = False) -> dict[str, Any]:
    if not profile:
        return {}
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", profile):
        raise CodexUnavailable()
    root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    try:
        with (root / f"{profile}.config.toml").open("rb") as source:
            raw = source.read(262145)
        if len(raw) > 262144:
            raise ValueError("oversized profile")
        config = tomllib.loads(raw.decode("utf-8"))
        toolbox = config.get("mcp_servers", {}).get("chickenbro_toolbox")
        if isinstance(toolbox, dict):
            # The test service must execute the tools from its own release,
            # even when it inherits the same model/auth profile as production.
            toolbox["args"] = [str(Path(__file__).resolve().parents[2] / "chickenbro_native_mcp.py")]
            toolbox["tool_timeout_sec"] = 90
            # Codex forwards MCP child environment only through this allowlist.
            # Tokens are issued for the current run, never stored in the profile.
            toolbox["env_vars"] = list(dict.fromkeys([
                *toolbox.get("env_vars", []),
                "CHICKENBRO_SIMULATION_GATEWAY_URL",
                "CHICKENBRO_SIMULATION_GATEWAY_TOKEN",
            ]))
            if allow_simulation:
                # Only the application's bounded, account-scoped operations are
                # pre-authorized. Keep the server default and all other tools.
                tool_settings = toolbox.setdefault("tools", {})
                for name in ("prepare_simulation", "submit_simulation"):
                    tool_settings.setdefault(name, {}).setdefault("approval_mode", "approve")
        return config
    except (OSError, ValueError):
        raise CodexUnavailable() from None


def _load_agent_rules() -> str:
    try:
        with _AGENT_RULES_PATH.open("rb") as source:
            raw = source.read(_MAX_AGENT_RULES_BYTES + 1)
        rules = raw.decode("utf-8")
        if len(raw) > _MAX_AGENT_RULES_BYTES or not rules.strip():
            raise ValueError("invalid agent rules")
        return rules
    except (OSError, ValueError):
        raise CodexUnavailable("native Codex agent rules are unavailable") from None


_CODEX_ENV_ALLOWLIST = frozenset({
    "CI",
    "CODEX_HOME",
    "HOME",
    "LANG",
    "LC_ALL",
    "NO_COLOR",
    "PATH",
    "TERM",
    "TMPDIR",
    "TZ",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
    "WOW_CODEX_BIN",
    "WOW_CODEX_HOME",
    "WOW_CODEX_JOBS_DIR",
    "WOW_CODEX_PROFILE",
    "WOW_CODEX_SANDBOX",
    "CHICKENBRO_SOURCE_GATEWAY_URL",
    "CHICKENBRO_SOURCE_GATEWAY_TOKEN",
    "CHICKENBRO_SIMULATION_GATEWAY_URL",
    "CHICKENBRO_SIMULATION_GATEWAY_TOKEN",
})


class CodexUnavailable(CodexStreamError):
    def __init__(self, message: str = "native Codex is unavailable"):
        super().__init__("CODEX_UNAVAILABLE", message)


class CodexTimeout(CodexStreamError):
    def __init__(self):
        super().__init__("CODEX_TIMEOUT")


class CodexExecutionFailed(CodexStreamError):
    def __init__(self):
        super().__init__("CODEX_EXECUTION_FAILED")


class CodexChatPort(Protocol):
    runtime_revision: str

    def stream(self, *, prompt: str, timeout_seconds: int) -> Iterator[dict[str, Any]]:
        raise NotImplementedError


class NativeCodexChatAdapter:
    """Run the local native Codex CLI and expose only safe JSONL text events."""

    def __init__(
        self,
        *,
        jobs_dir: str | Path | None = None,
        codex_bin: str | None = None,
        sandbox: str | None = None,
        profile: str | None = None,
        enabled: bool | None = None,
        source_gateway: Any | None = None,
        source_gateway_url: str | None = None,
        simulation_gateway: Any | None = None,
        simulation_gateway_url: str | None = None,
        runtime_revision: str | None = None,
        popen: Callable[..., Any] = subprocess.Popen,
    ):
        self._jobs_dir = Path(jobs_dir or os.environ.get("WOW_CODEX_JOBS_DIR", DEFAULT_JOBS_DIR))
        self._codex_bin = codex_bin or os.environ.get("WOW_CODEX_BIN", DEFAULT_CODEX_BIN)
        self._sandbox = "read-only"
        self._profile = profile if profile is not None else os.environ.get("WOW_CODEX_PROFILE") or None
        configured_runtime_revision = str(
            runtime_revision
            if runtime_revision is not None
            else os.environ.get("WOW_CODEX_RUNTIME_REVISION", "codex:native:unversioned")
        ).strip()
        if not 1 <= len(configured_runtime_revision) <= 160:
            raise ValueError("Codex runtime revision must be between 1 and 160 characters")
        self.runtime_revision = configured_runtime_revision
        self._enabled = (
            enabled
            if enabled is not None
            else os.environ.get("WOW_CHICKENBRO_CODEX_ENABLED", "0").strip() == "1"
        )
        self._source_gateway = source_gateway
        self._simulation_gateway = simulation_gateway
        self._simulation_gateway_url = simulation_gateway_url or "http://127.0.0.1:8790/api/v2/internal/chickenbro/simc-tool"
        self._source_gateway_url = (
            source_gateway_url
            or os.environ.get(
                "CHICKENBRO_SOURCE_GATEWAY_URL",
                "http://127.0.0.1:8790/api/v2/internal/chickenbro/source-query",
            )
        ).strip()
        self._popen = popen

    def stream_for_chat(self, *, principal, conversation_id, run_id, prompt, timeout_seconds):
        from server.app.chickenbro.simulation_tools import SimulationToolContext
        context = SimulationToolContext(principal=principal, conversation_id=conversation_id, run_id=run_id)
        yield from self.stream(prompt=prompt, timeout_seconds=timeout_seconds, tool_context=context)

    def stream(self, *, prompt: str, timeout_seconds: int, tool_context=None) -> Iterator[dict[str, Any]]:
        if not self._enabled:
            raise CodexUnavailable()
        if not isinstance(prompt, str) or not prompt.strip():
            raise CodexStreamError("CODEX_OUTPUT_INVALID")

        developer_instructions = _load_agent_rules()
        profile_config = _load_profile(self._profile, allow_simulation=(
            self._simulation_gateway is not None and tool_context is not None))
        deadline = time.monotonic() + max(1, int(timeout_seconds))
        try:
            job_dir = self._new_job_dir()
        except (OSError, ValueError):
            raise CodexUnavailable() from None
        command = [self._codex_bin, "-c", 'approval_policy="never"']
        command.extend(["app-server", "--listen", "stdio://"])

        source_gateway_token = ""
        simulation_gateway_token = ""
        if self._source_gateway is not None:
            try:
                source_gateway_token = str(self._source_gateway.issue_capability()).strip()
            except (AttributeError, OSError, TypeError, ValueError):
                raise CodexUnavailable() from None
            if not source_gateway_token:
                raise CodexUnavailable() from None

        try:
            if self._simulation_gateway is not None and tool_context is not None:
                simulation_gateway_token = self._simulation_gateway.issue_capability(tool_context)
            child_environment = {
                key: value
                for key, value in os.environ.items()
                if key in _CODEX_ENV_ALLOWLIST and key not in {
                    "CHICKENBRO_SOURCE_GATEWAY_TOKEN", "CHICKENBRO_SIMULATION_GATEWAY_TOKEN"
                }
            }
            if source_gateway_token:
                child_environment["CHICKENBRO_SOURCE_GATEWAY_URL"] = self._source_gateway_url
                child_environment["CHICKENBRO_SOURCE_GATEWAY_TOKEN"] = source_gateway_token
            if simulation_gateway_token:
                child_environment["CHICKENBRO_SIMULATION_GATEWAY_TOKEN"] = simulation_gateway_token
                child_environment["CHICKENBRO_SIMULATION_GATEWAY_URL"] = self._simulation_gateway_url
            child_environment["CHICKENBRO_NATIVE_OBSERVATIONS_PATH"] = str(
                job_dir / "native-tool-observations.jsonl"
            )
            process = self._popen(
                command,
                cwd=str(job_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=False,
                bufsize=0,
                start_new_session=(os.name == "posix"),
                env=child_environment,
            )
        except (OSError, ValueError, TypeError):
            self._revoke_source_capability(source_gateway_token)
            self._revoke_simulation_capability(simulation_gateway_token)
            raise CodexUnavailable() from None

        process_finished = False
        session = CodexStdioSession(process, deadline)
        try:
            terminal = None
            for event in session.stream(prompt=prompt, job_dir=job_dir, developer_instructions=developer_instructions,
                                        profile_config=profile_config):
                if event["type"] == "completed":
                    terminal = event
                else:
                    yield event
            process.stdin.close()
            return_code = process.wait(timeout=max(0.01, min(5, deadline - time.monotonic())))
            process_finished = True
            if return_code != 0:
                raise CodexExecutionFailed()
            if terminal is None:
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
            self._revoke_source_capability(source_gateway_token)
            self._revoke_simulation_capability(simulation_gateway_token)
            source_gateway_token = ""
            simulation_gateway_token = ""
            yield terminal
        except subprocess.TimeoutExpired:
            raise CodexTimeout() from None
        except CodexStreamError as error:
            if error.code == "CODEX_TIMEOUT":
                raise CodexTimeout() from None
            raise
        except (OSError, ValueError, TypeError):
            raise CodexStreamError("CODEX_OUTPUT_INVALID") from None
        finally:
            session.messages.close()
            if not process_finished:
                self._terminate(process)
            for pipe in (process.stdin, process.stdout):
                try:
                    if pipe is not None and not pipe.closed:
                        pipe.close()
                except (OSError, ValueError):
                    pass
            self._revoke_source_capability(source_gateway_token)
            self._revoke_simulation_capability(simulation_gateway_token)

    def _revoke_source_capability(self, token: str) -> None:
        if not token or self._source_gateway is None:
            return
        try:
            self._source_gateway.revoke(token)
        except (AttributeError, OSError, TypeError, ValueError):
            return

    def _revoke_simulation_capability(self, token: str) -> None:
        if not token or self._simulation_gateway is None:
            return
        try:
            self._simulation_gateway.revoke(token)
        except (AttributeError, OSError, TypeError, ValueError):
            return

    def _new_job_dir(self) -> Path:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        job_dir = self._jobs_dir / uuid.uuid4().hex
        job_dir.mkdir()
        return job_dir

    @staticmethod
    def _terminate(process: Any) -> None:
        try:
            if os.name == "posix" and isinstance(getattr(process, "pid", None), int):
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except (AttributeError, OSError, ValueError):
            return
        try:
            process.wait(timeout=1)
        except (AttributeError, OSError, subprocess.TimeoutExpired, ValueError):
            pass


__all__ = (
    "CodexChatPort",
    "CodexExecutionFailed",
    "CodexTimeout",
    "CodexUnavailable",
    "NativeCodexChatAdapter",
)

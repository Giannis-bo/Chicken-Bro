import json
import os
import selectors
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol

from server.app.chickenbro.stream import CodexStreamError
from server.codex_worker import (
    DEFAULT_CODEX_BIN,
    DEFAULT_JOBS_DIR,
    DEFAULT_SANDBOX,
    build_codex_command,
)


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
        runtime_revision: str | None = None,
        popen: Callable[..., Any] = subprocess.Popen,
    ):
        self._jobs_dir = Path(jobs_dir or os.environ.get("WOW_CODEX_JOBS_DIR", DEFAULT_JOBS_DIR))
        self._codex_bin = codex_bin or os.environ.get("WOW_CODEX_BIN", DEFAULT_CODEX_BIN)
        self._sandbox = sandbox or os.environ.get("WOW_CODEX_SANDBOX", DEFAULT_SANDBOX)
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
        self._source_gateway_url = (
            source_gateway_url
            or os.environ.get(
                "CHICKENBRO_SOURCE_GATEWAY_URL",
                "http://127.0.0.1:8790/api/v2/internal/chickenbro/source-query",
            )
        ).strip()
        self._popen = popen

    def stream(self, *, prompt: str, timeout_seconds: int) -> Iterator[dict[str, Any]]:
        if not self._enabled:
            raise CodexUnavailable()
        if not isinstance(prompt, str) or not prompt.strip():
            raise CodexStreamError("CODEX_OUTPUT_INVALID")

        try:
            job_dir = self._new_job_dir()
            prompt_path = job_dir / "prompt.txt"
            output_path = job_dir / "last-message.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
        except (OSError, ValueError):
            raise CodexUnavailable() from None
        try:
            command = build_codex_command(
                prompt_path=prompt_path,
                job_dir=job_dir,
                output_path=output_path,
                sandbox=self._sandbox,
                codex_bin=self._codex_bin,
                profile=self._profile,
            )
        except (TypeError, ValueError, OSError):
            raise CodexUnavailable() from None

        source_gateway_token = ""
        if self._source_gateway is not None:
            try:
                source_gateway_token = str(self._source_gateway.issue_capability()).strip()
            except (AttributeError, OSError, TypeError, ValueError):
                raise CodexUnavailable() from None
            if not source_gateway_token:
                raise CodexUnavailable() from None

        try:
            child_environment = {
                key: value
                for key, value in os.environ.items()
                if key in _CODEX_ENV_ALLOWLIST
            }
            if source_gateway_token:
                child_environment["CHICKENBRO_SOURCE_GATEWAY_URL"] = self._source_gateway_url
                child_environment["CHICKENBRO_SOURCE_GATEWAY_TOKEN"] = source_gateway_token
            child_environment["CHICKENBRO_NATIVE_OBSERVATIONS_PATH"] = str(
                job_dir / "native-tool-observations.jsonl"
            )
            process = self._popen(
                command,
                cwd=str(job_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=child_environment,
            )
        except (FileNotFoundError, OSError):
            self._revoke_source_capability(source_gateway_token)
            raise CodexUnavailable() from None

        try:
            self._send_prompt(process, prompt)
        except CodexStreamError:
            self._revoke_source_capability(source_gateway_token)
            raise
        deadline = time.monotonic() + max(1, int(timeout_seconds))
        emitted_text = False
        completion_seen = False
        last_item_text = ""
        terminal_text = ""
        try:
            for line in self._read_lines(process, deadline):
                event = self._parse_line(line)
                normalized = self._normalize_event(event)
                if normalized is None:
                    continue
                if normalized["type"] == "delta":
                    emitted_text = True
                    yield normalized
                elif normalized["type"] == "item_completed":
                    last_item_text = self._text_from(normalized.get("text")) or last_item_text
                elif normalized["type"] == "completed":
                    completion_seen = True
                    terminal_text = self._text_from(normalized.get("text"))
                    if terminal_text:
                        emitted_text = True
                        yield normalized
            return_code = self._wait(process, deadline)
        except CodexStreamError:
            self._terminate(process)
            self._revoke_source_capability(source_gateway_token)
            raise
        except subprocess.TimeoutExpired:
            self._terminate(process)
            self._revoke_source_capability(source_gateway_token)
            raise CodexTimeout() from None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._terminate(process)
            self._revoke_source_capability(source_gateway_token)
            raise CodexStreamError("CODEX_OUTPUT_INVALID") from None

        if return_code != 0:
            self._revoke_source_capability(source_gateway_token)
            raise CodexExecutionFailed()

        self._revoke_source_capability(source_gateway_token)
        final_text = self._read_final_message(output_path)
        if completion_seen:
            if terminal_text:
                return
            if final_text:
                yield {"type": "completed", "text": final_text}
            elif emitted_text:
                yield {"type": "completed", "text": ""}
            else:
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
        else:
            fallback_text = final_text or last_item_text
            if not fallback_text and not emitted_text:
                raise CodexStreamError("CODEX_OUTPUT_INVALID")
            yield {"type": "completed", "text": fallback_text}

    def _revoke_source_capability(self, token: str) -> None:
        if not token or self._source_gateway is None:
            return
        try:
            self._source_gateway.revoke(token)
        except (AttributeError, OSError, TypeError, ValueError):
            return

    def _new_job_dir(self) -> Path:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        job_dir = self._jobs_dir / uuid.uuid4().hex
        job_dir.mkdir()
        return job_dir

    @staticmethod
    def _send_prompt(process: Any, prompt: str) -> None:
        try:
            stdin = process.stdin
            if stdin is None:
                raise OSError("missing stdin")
            stdin.write(prompt)
            stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            NativeCodexChatAdapter._terminate(process)
            raise CodexExecutionFailed() from None

    @staticmethod
    def _read_lines(process: Any, deadline: float) -> Iterator[str]:
        stdout = process.stdout
        if stdout is None:
            raise CodexStreamError("CODEX_OUTPUT_INVALID")

        selector = None
        try:
            selector = selectors.DefaultSelector()
            selector.register(stdout, selectors.EVENT_READ)
        except (AttributeError, OSError, ValueError):
            if selector is not None:
                selector.close()
            selector = None

        try:
            if selector is None:
                for line in stdout:
                    if time.monotonic() >= deadline:
                        raise CodexTimeout()
                    yield line
                return

            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CodexTimeout()
                if not selector.select(remaining):
                    raise CodexTimeout()
                line = stdout.readline()
                if not line:
                    return
                yield line
        finally:
            if selector is not None:
                selector.close()

    @staticmethod
    def _parse_line(line: str) -> dict[str, Any]:
        try:
            event = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            raise CodexStreamError("CODEX_OUTPUT_INVALID") from None
        if not isinstance(event, dict):
            raise CodexStreamError("CODEX_OUTPUT_INVALID")
        return event

    @classmethod
    def _normalize_event(cls, event: dict[str, Any]) -> dict[str, Any] | None:
        event_type = str(event.get("type", "")).strip().lower()
        if event_type in {"thread.started", "turn.started", "item.started", "item.updated"}:
            return None
        if event_type in {"error", "turn.failed", "response.failed", "item.failed"}:
            raise CodexStreamError("CODEX_OUTPUT_INVALID")
        if event_type in {"item.delta", "message.delta", "response.output_text.delta", "content.delta", "delta"}:
            text = cls._text_from(event.get("delta")) or cls._text_from(event.get("text"))
            return {"type": "delta", "text": text} if text else None
        if event_type in {"item.completed", "message.completed"}:
            text = cls._text_from(event.get("text"))
            if not text:
                item = event.get("item")
                if isinstance(item, dict):
                    item_type = str(item.get("type", "")).strip().lower()
                    if item_type in {"agent_message", "assistant_message", "message"}:
                        text = cls._text_from(item.get("text")) or cls._text_from(item.get("content"))
            return {"type": "item_completed", "text": text}
        if event_type in {"turn.completed", "response.completed", "completed"}:
            text = cls._text_from(event.get("text"))
            if not text:
                item = event.get("item")
                if isinstance(item, dict):
                    item_type = str(item.get("type", "")).strip().lower()
                    if item_type in {"agent_message", "assistant_message", "message"}:
                        text = cls._text_from(item.get("text")) or cls._text_from(item.get("content"))
            return {"type": "completed", "text": text}
        # Metadata from the CLI is intentionally ignored. The application only
        # consumes normalized delta/completed events and never forwards this map.
        return None

    @staticmethod
    def _text_from(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("text", "value", "delta"):
                text = NativeCodexChatAdapter._text_from(value.get(key))
                if text:
                    return text
        if isinstance(value, list):
            return "".join(NativeCodexChatAdapter._text_from(item) for item in value)
        return ""

    @staticmethod
    def _read_final_message(output_path: Path) -> str:
        try:
            return output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
        except (OSError, UnicodeError):
            return ""

    @staticmethod
    def _wait(process: Any, deadline: float) -> int:
        remaining = max(0.01, deadline - time.monotonic())
        try:
            return process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise

    @staticmethod
    def _terminate(process: Any) -> None:
        try:
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

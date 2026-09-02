import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.app.chickenbro.codex_adapter import (
    CodexStreamError,
    CodexTimeout,
    CodexUnavailable,
    NativeCodexChatAdapter,
)


class FakeProcess:
    def __init__(self, stdout: str, *, returncode: int = 0, wait_error=None):
        self.stdin = TrackingStdin()
        self.stdout = io.StringIO(stdout)
        self.returncode = returncode
        self.wait_error = wait_error
        self.killed = False
        self.wait_calls = 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_error is not None:
            raise self.wait_error
        return self.returncode

    def kill(self):
        self.killed = True


class TrackingStdin(io.StringIO):
    def close(self):
        self.written = self.getvalue()
        super().close()


class ChickenbroCodexAdapterTest(unittest.TestCase):
    def test_adapter_exposes_configured_runtime_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                adapter = NativeCodexChatAdapter(
                    jobs_dir=directory,
                    enabled=False,
                    runtime_revision="codex:native:0.99.1",
                )
            except TypeError as error:
                self.fail(f"adapter rejected runtime revision: {error}")

        self.assertEqual(adapter.runtime_revision, "codex:native:0.99.1")

    def test_disabled_adapter_fails_closed_without_starting_a_process(self):
        started = []
        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=False,
                popen=lambda *args, **kwargs: started.append(True),
            )

            with self.assertRaises(CodexUnavailable):
                list(adapter.stream(prompt="hello", timeout_seconds=10))

        self.assertEqual(started, [])

    def test_streams_allowlisted_text_and_emits_completion(self):
        processes = []

        def popen(*args, **kwargs):
            process = FakeProcess("\n".join([
                json.dumps({"type": "thread.started", "thread_id": "secret"}),
                json.dumps({"type": "item.delta", "delta": "先给结论"}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "先给结论"}}),
            ]))
            processes.append((process, args, kwargs))
            return process

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                codex_bin="codex-test",
                popen=popen,
            )
            events = list(adapter.stream(prompt="hello", timeout_seconds=10))

            self.assertEqual(events, [
                {"type": "delta", "text": "先给结论"},
                {"type": "completed", "text": "先给结论"},
            ])
            process, command_args, kwargs = processes[0]
            self.assertEqual(command_args[0][0], "codex-test")
            self.assertEqual(kwargs["cwd"], str(next(Path(directory).iterdir())))
            self.assertEqual(process.stdin.written, "hello")

    def test_waits_for_turn_completion_after_an_intermediate_item_completion(self):
        def popen(*args, **kwargs):
            command = args[0]
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("最终报告", encoding="utf-8")
            return FakeProcess("\n".join([
                json.dumps({
                    "type": "item.completed",
                    "item": {"type": "agent_message", "phase": "commentary", "text": "我会先读取报告"},
                }),
                json.dumps({"type": "turn.completed"}),
            ]))

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                popen=popen,
            )

            events = list(adapter.stream(prompt="分析报告", timeout_seconds=10))

        self.assertEqual(events, [{"type": "completed", "text": "最终报告"}])

    def test_child_process_receives_only_codex_runtime_environment(self):
        captured = {}

        def popen(*args, **kwargs):
            captured.update(kwargs)
            return FakeProcess("\n".join([
                json.dumps({"type": "item.delta", "delta": "回答"}),
                json.dumps({"type": "turn.completed", "text": "回答"}),
            ]))

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://secret",
                "WOW_WARCRAFTLOGS_API_TOKEN": "wcl-secret",
                "WOW_WECHAT_SECRET": "wechat-secret",
                "CODEX_HOME": "/tmp/codex-home",
                "HOME": "/tmp/home",
                "PATH": "/usr/bin",
            },
            clear=False,
        ):
            with tempfile.TemporaryDirectory() as directory:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=popen)
                self.assertEqual(list(adapter.stream(prompt="hello", timeout_seconds=10)), [
                    {"type": "delta", "text": "回答"},
                    {"type": "completed", "text": "回答"},
                ])

        child_environment = captured["env"]
        self.assertEqual(child_environment["CODEX_HOME"], "/tmp/codex-home")
        self.assertEqual(child_environment["HOME"], "/tmp/home")
        self.assertEqual(child_environment["PATH"], "/usr/bin")
        self.assertNotIn("WOW_DATABASE_URL", child_environment)
        self.assertNotIn("WOW_WARCRAFTLOGS_API_TOKEN", child_environment)
        self.assertNotIn("WOW_WECHAT_SECRET", child_environment)

    def test_child_process_receives_native_profile_and_standard_proxy_environment(self):
        captured = {}

        def popen(*args, **kwargs):
            captured["args"] = args
            captured.update(kwargs)
            return FakeProcess("\n".join([
                json.dumps({"type": "item.delta", "delta": "回答"}),
                json.dumps({"type": "turn.completed", "text": "回答"}),
            ]))

        proxy_environment = {
            "WOW_CODEX_PROFILE": "chickenbro-native",
            "HTTP_PROXY": "http://127.0.0.1:7890",
            "HTTPS_PROXY": "http://127.0.0.1:7890",
            "ALL_PROXY": "socks5h://127.0.0.1:7890",
            "NO_PROXY": "127.0.0.1,localhost,::1,169.254.169.254",
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7890",
            "all_proxy": "socks5h://127.0.0.1:7890",
            "no_proxy": "127.0.0.1,localhost,::1,169.254.169.254",
        }
        with patch.dict(os.environ, proxy_environment, clear=False):
            with tempfile.TemporaryDirectory() as directory:
                adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=popen)
                self.assertEqual(list(adapter.stream(prompt="hello", timeout_seconds=10)), [
                    {"type": "delta", "text": "回答"},
                    {"type": "completed", "text": "回答"},
                ])

        child_environment = captured["env"]
        for key, value in proxy_environment.items():
            self.assertEqual(value, child_environment[key])
        self.assertEqual(
            ["--profile", "chickenbro-native"],
            captured["args"][0][3:5],
        )

    def test_child_process_receives_only_a_short_lived_source_gateway_capability(self):
        captured = {}

        class Gateway:
            def issue_capability(self):
                return "one-job-capability"

            def revoke(self, token):
                self.revoked = token

        gateway = Gateway()

        def popen(*args, **kwargs):
            captured.update(kwargs)
            return FakeProcess("\n".join([
                json.dumps({"type": "item.delta", "delta": "回答"}),
                json.dumps({"type": "turn.completed", "text": "回答"}),
            ]))

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                source_gateway=gateway,
                source_gateway_url="http://127.0.0.1:8790/api/v2/internal/chickenbro/source-query",
                popen=popen,
            )
            self.assertEqual(
                list(adapter.stream(prompt="请查 WCL", timeout_seconds=10)),
                [{"type": "delta", "text": "回答"}, {"type": "completed", "text": "回答"}],
            )

        child_environment = captured["env"]
        self.assertEqual(
            "http://127.0.0.1:8790/api/v2/internal/chickenbro/source-query",
            child_environment["CHICKENBRO_SOURCE_GATEWAY_URL"],
        )
        self.assertEqual("one-job-capability", child_environment["CHICKENBRO_SOURCE_GATEWAY_TOKEN"])
        self.assertTrue(child_environment["CHICKENBRO_NATIVE_OBSERVATIONS_PATH"].endswith(
            "/native-tool-observations.jsonl"
        ))
        self.assertEqual("one-job-capability", gateway.revoked)
        self.assertNotIn("WOW_WARCRAFTLOGS_CLIENT_SECRET", child_environment)
        self.assertNotIn("WOW_RAIDERIO_API_KEY", child_environment)

    def test_terminal_event_waits_for_process_exit_and_revokes_capability_before_exposure(self):
        class Gateway:
            revoked = None

            def issue_capability(self):
                return "terminal-capability"

            def revoke(self, token):
                self.revoked = token

        gateway = Gateway()
        process = FakeProcess(json.dumps({"type": "turn.completed", "text": "最终回答"}))

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                source_gateway=gateway,
                popen=lambda *args, **kwargs: process,
            )
            stream = adapter.stream(prompt="hello", timeout_seconds=10)
            event = next(stream)

            self.assertEqual({"type": "completed", "text": "最终回答"}, event)
            self.assertEqual(1, process.wait_calls)
            self.assertEqual("terminal-capability", gateway.revoked)
            stream.close()
            self.assertFalse(process.killed)

    def test_closing_a_partial_stream_kills_process_and_revokes_capability(self):
        class Gateway:
            revoked = None

            def issue_capability(self):
                return "partial-capability"

            def revoke(self, token):
                self.revoked = token

        gateway = Gateway()
        process = FakeProcess("\n".join([
            json.dumps({"type": "item.delta", "delta": "尚未完成"}),
            json.dumps({"type": "turn.completed", "text": "不应继续"}),
        ]))

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                source_gateway=gateway,
                popen=lambda *args, **kwargs: process,
            )
            stream = adapter.stream(prompt="hello", timeout_seconds=10)
            self.assertEqual({"type": "delta", "text": "尚未完成"}, next(stream))
            stream.close()

        self.assertTrue(process.killed)
        self.assertEqual("partial-capability", gateway.revoked)

    def test_nonzero_exit_after_terminal_event_never_exposes_completion(self):
        process = FakeProcess(
            json.dumps({"type": "turn.completed", "text": "不得暴露"}),
            returncode=17,
        )

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                popen=lambda *args, **kwargs: process,
            )
            stream = adapter.stream(prompt="hello", timeout_seconds=10)
            with self.assertRaises(CodexStreamError) as context:
                next(stream)

        self.assertEqual("CODEX_EXECUTION_FAILED", context.exception.code)
        self.assertEqual(1, process.wait_calls)

    def test_nonzero_exit_never_exposes_provider_stderr(self):
        def popen(*args, **kwargs):
            return FakeProcess("", returncode=17)

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(jobs_dir=directory, enabled=True, popen=popen)
            with self.assertRaises(CodexStreamError) as context:
                list(adapter.stream(prompt="hello", timeout_seconds=10))

        self.assertEqual(context.exception.code, "CODEX_EXECUTION_FAILED")
        self.assertNotIn("provider", str(context.exception))

    def test_timeout_kills_process_and_returns_stable_error(self):
        process = FakeProcess(
            "",
            wait_error=subprocess.TimeoutExpired(cmd=["codex"], timeout=1),
        )

        with tempfile.TemporaryDirectory() as directory:
            adapter = NativeCodexChatAdapter(
                jobs_dir=directory,
                enabled=True,
                popen=lambda *args, **kwargs: process,
            )
            with self.assertRaises(CodexTimeout):
                list(adapter.stream(prompt="hello", timeout_seconds=1))

        self.assertTrue(process.killed)

    def test_unwritable_jobs_root_is_reported_as_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs_root = Path(directory) / "jobs-file"
            jobs_root.write_text("not a directory", encoding="utf-8")
            adapter = NativeCodexChatAdapter(
                jobs_dir=jobs_root,
                enabled=True,
            )

            with self.assertRaises(CodexUnavailable):
                list(adapter.stream(prompt="hello", timeout_seconds=10))


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class CodexWorkerTest(unittest.TestCase):
    def test_build_command_uses_isolated_workspace_and_noninteractive_json_mode(self):
        from server.codex_worker import build_codex_command

        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job-1"
            prompt_path = job_dir / "prompt.txt"
            output_path = job_dir / "last-message.txt"
            schema_path = job_dir / "result.schema.json"

            command = build_codex_command(
                prompt_path=prompt_path,
                job_dir=job_dir,
                output_path=output_path,
                schema_path=schema_path,
                sandbox="workspace-write",
            )

        self.assertEqual(command[:4], ["codex", "--ask-for-approval", "never", "exec"])
        self.assertIn("--json", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn("--ask-for-approval", command)
        self.assertIn("never", command)
        self.assertIn("--sandbox", command)
        self.assertIn("workspace-write", command)
        self.assertIn("--cd", command)
        self.assertIn(str(job_dir), command)
        self.assertIn("--output-last-message", command)
        self.assertIn(str(output_path), command)
        self.assertIn("--output-schema", command)
        self.assertIn(str(schema_path), command)
        self.assertEqual(command[-1], "-")

    def test_build_command_can_select_a_native_agent_profile_without_a_json_schema(self):
        """The native Agent owns its tool loop and must not be schema-forced."""
        from server.codex_worker import build_codex_command

        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "job-native"
            try:
                command = build_codex_command(
                    prompt_path=job_dir / "prompt.txt",
                    job_dir=job_dir,
                    output_path=job_dir / "last-message.txt",
                    profile="chickenbro-native",
                    sandbox="read-only",
                )
            except TypeError:
                command = []

        self.assertIn("--profile", command)
        self.assertEqual("chickenbro-native", command[command.index("--profile") + 1])
        self.assertNotIn("--output-schema", command)

    def test_run_codex_job_writes_prompt_and_returns_structured_result(self):
        from server.codex_worker import run_codex_job

        calls = []

        def fake_runner(command, **kwargs):
            calls.append({"command": command, "kwargs": kwargs})
            output_file = Path(command[command.index("--output-last-message") + 1])
            output_file.write_text('{"summary":"ok"}', encoding="utf-8")

            class Completed:
                returncode = 0
                stdout = json.dumps({"type": "agent_message", "message": "done"})
                stderr = ""

            return Completed()

        with tempfile.TemporaryDirectory() as tmp:
            result = run_codex_job(
                "请分析这个 SimC profile",
                jobs_dir=Path(tmp),
                job_id="job-abc",
                runner=fake_runner,
                timeout_seconds=12,
            )

            prompt_text = (Path(tmp) / "job-abc" / "prompt.txt").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["jobId"], "job-abc")
        self.assertEqual(result["lastMessage"], '{"summary":"ok"}')
        self.assertEqual(result["events"][0]["type"], "agent_message")
        self.assertIn("SimC profile", prompt_text)
        self.assertEqual(calls[0]["kwargs"]["timeout"], 12)
        self.assertEqual(calls[0]["kwargs"]["input"], "请分析这个 SimC profile")
        self.assertEqual(calls[0]["kwargs"]["cwd"], str(Path(tmp) / "job-abc"))

    def test_run_codex_job_returns_timeout_result_when_cli_hangs(self):
        from server.codex_worker import run_codex_job

        def timeout_runner(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"], output='{"type":"started"}\n', stderr="waiting")

        with tempfile.TemporaryDirectory() as tmp:
            result = run_codex_job(
                "只输出 OK",
                jobs_dir=Path(tmp),
                job_id="job-timeout",
                runner=timeout_runner,
                timeout_seconds=1,
            )

        self.assertEqual(result["status"], "timed_out")
        self.assertEqual(result["returnCode"], -1)
        self.assertIn("timed out after 1 seconds", result["stderr"])
        self.assertEqual(result["events"][0]["type"], "started")

    def test_run_codex_job_collects_observations_written_by_the_native_mcp_server(self):
        from server.codex_worker import run_codex_job

        def fake_runner(_command, **kwargs):
            observation_path = Path(kwargs["env"]["CHICKENBRO_NATIVE_OBSERVATIONS_PATH"])
            observation_path.write_text(
                json.dumps({"tool": "research_public_web", "evidenceRefs": ["public-web:fixture"]}) + "\n",
                encoding="utf-8",
            )

            class Completed:
                returncode = 0
                stdout = ""
                stderr = ""

            return Completed()

        with tempfile.TemporaryDirectory() as tmp:
            result = run_codex_job(
                "请直接回答",
                jobs_dir=Path(tmp),
                job_id="job-native-observations",
                runner=fake_runner,
                observation_file_name="native-tool-observations.jsonl",
            )

        self.assertEqual(
            [{"tool": "research_public_web", "evidenceRefs": ["public-web:fixture"]}],
            result["nativeToolObservations"],
        )

    def test_run_codex_job_rejects_unsafe_job_id(self):
        from server.codex_worker import run_codex_job

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_codex_job("只输出 OK", jobs_dir=Path(tmp), job_id="../escape")


if __name__ == "__main__":
    unittest.main()

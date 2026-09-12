"""Runner contracts without model calls, cloud access, or real providers."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark-chickenbro-agent.py"
sys.path.insert(0, str(SCRIPT.parent))
sys.path.insert(0, str(SCRIPT.parent.parent))
spec = importlib.util.spec_from_file_location("benchmark_runner", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_real_adapter_isolation_disables_global_mcp_and_native_features(self):
        from server.app.chickenbro.codex_adapter import _repair_profile
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "config.toml").write_text('[mcp_servers.real_provider]\ncommand="real-command"\nenabled=true\n')
            with patch.dict(runner.os.environ, {"CODEX_HOME": directory}):
                isolated = runner.replay_profile({"model": "same-model", "model_reasoning_effort": "low"},
                                                 _repair_profile, ["fixture.py"], [])
        self.assertFalse(isolated["mcp_servers"]["real_provider"]["enabled"])
        self.assertTrue(isolated["mcp_servers"]["chickenbro_toolbox"]["enabled"])
        self.assertEqual(isolated["web_search"], "disabled")
        for feature in ("shell_tool", "apps", "plugins", "browser_use", "multi_agent", "code_mode"):
            self.assertFalse(isolated["features"][feature])

    def test_partial_success_is_in_progress_and_failure_keeps_prior_turn(self):
        turns = [{"status": "succeeded", "totalMs": 10, "answer": "first"}]
        result = runner.case_result("a", "logs", "old", 1, turns, expected_turns=2)
        self.assertEqual(result["status"], "in_progress")
        self.assertFalse(result["completeCase"])
        self.assertEqual(result["completedTurns"], 1)
        turns.append({"status": "timeout", "totalMs": 20, "errorCode": "CODEX_TIMEOUT"})
        result = runner.case_result("a", "logs", "old", 1, turns, expected_turns=2)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["turns"][0]["answer"], "first")
        self.assertEqual(result["totalMs"], 30)

    def test_profile_disables_inherited_servers_and_features_and_keeps_model(self):
        original = {"model": "same-model", "model_reasoning_effort": "medium",
                    "mcp_servers": {"chickenbro_toolbox": {"command": "real-tool"}}}
        def repair_profile(config):
            return {**config, "model_reasoning_effort": "low", "web_search": "disabled",
                    "mcp_servers": {"chickenbro_toolbox": {"enabled": False},
                                    "global_provider": {"enabled": False}},
                    "features": {"shell_tool": False, "apps": False}}
        isolated = runner.replay_profile(original, repair_profile, ["fixture.py"], [{"name": "query"}])
        self.assertFalse(isolated["mcp_servers"]["global_provider"]["enabled"])
        toolbox = isolated["mcp_servers"]["chickenbro_toolbox"]
        self.assertTrue(toolbox["enabled"])
        self.assertEqual(toolbox["args"], ["fixture.py"])
        self.assertEqual(isolated["model_reasoning_effort"], "medium")
        self.assertEqual(isolated["model"], "same-model")
        self.assertEqual(original["mcp_servers"]["chickenbro_toolbox"]["command"], "real-tool")

    def test_timed_session_keeps_repair_usage_and_phase_end_on_error(self):
        class Base:
            def __init__(self): self.token_usage = {"inputTokens": 12}
            def send(self, message): return None
            def _item_event(self, method, params): return None
            def stream(self, **kwargs):
                self.send({"method": "turn/start"})
                yield {"type": "delta", "text": "draft"}
                raise ValueError("repair failure")
        sessions = []
        Timed = runner.timed_session_class(Base, "repair", sessions, [0])
        with patch.object(runner.time, "monotonic", return_value=1):
            session = Timed()
            with self.assertRaises(ValueError): list(session.stream())
        self.assertEqual(sessions[0].phase, "repair")
        self.assertEqual(session.token_usage["inputTokens"], 12)
        self.assertEqual([e["event"] for e in session.phaseEvents], ["start", "end"])

    def test_partial_process_failure_is_preserved_and_repeated_failure_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(output=directory, cases=["a", "b"], trials=2,
                                   old="old", new="new", timeout=5, max_consecutive_failures=2)
            def process(command, **kwargs):
                dest = Path(command[command.index("--output") + 1]); dest.mkdir()
                row = {"caseId": command[command.index("--case") + 1],
                       "variant": command[command.index("--variant") + 1], "trial": 1,
                       "status": "in_progress", "completeCase": False, "expectedTurns": 2,
                       "turns": [{"status": "succeeded", "answer": "preserved", "totalMs": 10}], "totalMs": 10}
                (dest / "result.json").write_text(json.dumps(row))
                return SimpleNamespace(returncode=1)
            with patch.object(runner.subprocess, "run", side_effect=process) as call:
                runner.orchestrate(args)
            self.assertEqual(call.call_count, 2)
            first = json.loads(next(Path(directory).glob("*/result.json")).read_text())
            self.assertEqual(first["status"], "failed")
            self.assertEqual(first["turns"][0]["answer"], "preserved")
            self.assertEqual(json.loads((Path(directory) / "stopped.json").read_text())["remainingCount"], 6)

    def test_campaign_rejects_partial_and_complete_prior_outputs_without_changes(self):
        for completed in (False, True):
            with self.subTest(completed=completed), tempfile.TemporaryDirectory() as directory:
                dest = Path(directory) / "a-1-old"; dest.mkdir()
                (dest / "fixture-state.json").write_text('{"submitted":true}')
                (dest / "receipts.jsonl").write_text('existing receipt\n')
                if completed:
                    (dest / "result.json").write_text(json.dumps({"status":"succeeded", "completeCase":True,
                        "source":"wrong-source", "fixtureSha256":"old-corpus"}))
                before = {str(p.relative_to(directory)): p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
                args = SimpleNamespace(output=directory, cases=["a"], trials=1,
                                       old="old", new="new", timeout=5, max_consecutive_failures=1)
                with patch.object(runner.subprocess, "run", side_effect=AssertionError('Must reject before child execution')):
                    with self.assertRaisesRegex(ValueError, 'empty'):
                        runner.orchestrate(args)
                self.assertEqual(before, {str(p.relative_to(directory)): p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()})

    def test_case_rejects_prior_state_before_loading_production_environment(self):
        for completed in (False, True):
            with self.subTest(completed=completed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'fixture-state.json').write_text('{"submitted":true}')
                if completed:
                    (root / 'result.json').write_text('{"status":"succeeded","source":"wrong-source"}')
                before = {p.name:p.read_bytes() for p in root.iterdir()}
                with patch.object(runner, 'production_environment', side_effect=AssertionError('No cloud access allowed')):
                    with self.assertRaisesRegex(ValueError, 'empty'):
                        runner.run_case(SimpleNamespace(output=directory))
                self.assertEqual(before, {p.name:p.read_bytes() for p in root.iterdir()})


if __name__ == "__main__": unittest.main()

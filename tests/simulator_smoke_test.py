import json
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class SimulatorSmokeTest(unittest.TestCase):
    def test_simulator_smoke_script_runs_prompt_through_http_backend(self):
        completed = subprocess.run(
            [sys.executable, "server/simulator_e2e_smoke.py"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["simulation"]["ran"])
        self.assertEqual(payload["simulation"]["metrics"]["dps"], "140002")
        self.assertEqual(payload["observedDps"], "140002")
        self.assertEqual(payload["request"]["profileSource"], "prompt")
        self.assertIn("140002", payload["recommendations"][0])

    def test_simulator_smoke_script_can_validate_configured_backend_base_url(self):
        captured = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0") or "0")
                captured["path"] = self.path
                captured["body"] = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps(
                    {
                        "mode": "simcraft",
                        "status": "ready",
                        "request": {
                            "profileSource": "prompt",
                            "runSimulation": True,
                        },
                        "simulation": {
                            "ran": True,
                            "metrics": {},
                            "summary": "Player: RemoteSmoke human warrior arms 80\n  DPS=150.0034 DPS-Error=0/0.00%",
                        },
                        "recommendations": [
                            "本次 SimC 已跑通，当前 profile 约为 150003 DPS；先把这个作为基准。"
                        ],
                    },
                    ensure_ascii=False,
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "server/simulator_e2e_smoke.py",
                    "--base-url",
                    f"http://127.0.0.1:{server.server_port}",
                    "--timeout",
                    "20",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        payload = json.loads(completed.stdout)
        self.assertEqual(captured["path"], "/api/simulator/analyze")
        self.assertIn("```simc", captured["body"]["prompt"])
        self.assertEqual(payload["observedDps"], "150.003")


if __name__ == "__main__":
    unittest.main()

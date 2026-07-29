import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from server import websim_sync


class WebSimSyncScriptTest(unittest.TestCase):
    def test_main_emits_stage_progress_to_stderr(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "wow.sqlite3"
            with sqlite3.connect(db_path) as conn:
                conn.execute("create table if not exists raiderio_cache (key text primary key, value_json text, updated_at text, expires_at text, stale_at text)")

            def fake_websim(path, include_blizzard=True, stage_callback=None):
                self.assertEqual(Path(path), db_path)
                self.assertTrue(include_blizzard)
                stage_callback({"stage": "simc", "status": "start"})
                stage_callback({"stage": "simc", "status": "complete", "durationSeconds": 0.01})
                return {"ok": True, "stages": [{"stage": "simc", "status": "complete"}]}

            def fake_raiderio(conn, stage_callback=None):
                return {"sourceStatus": "verified", "profileCount": 0}

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.object(websim_sync, "DB_PATH", db_path), patch.object(
                websim_sync,
                "sync_websim_cache",
                fake_websim,
            ), patch.object(websim_sync, "sync_raiderio_cache", fake_raiderio), redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = websim_sync.main()

        progress = [json.loads(line) for line in stderr.getvalue().splitlines() if line.strip()]
        self.assertEqual(exit_code, 0)
        self.assertEqual(progress[0]["event"], "websim_sync_stage")
        self.assertEqual(progress[0]["stage"], "websim")
        self.assertEqual(progress[0]["status"], "start")
        self.assertTrue(any(event.get("stage") == "simc" and event.get("status") == "start" for event in progress))
        self.assertTrue(any(event.get("stage") == "raiderio" and event.get("status") == "complete" for event in progress))
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["event"], "websim_sync_complete")
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(
            payload["components"]["websim"]["status"],
            "verified",
        )
        self.assertEqual(
            payload["components"]["raiderio"]["status"],
            "verified",
        )

    def test_main_can_skip_raiderio_for_stage_smoke(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = Path(tmp) / "wow.sqlite3"

            def fake_websim(path, include_blizzard=True, stage_callback=None):
                stage_callback({"stage": "simc", "status": "complete"})
                return {"ok": True, "errors": [], "dataStatus": "verified"}

            def fail_raiderio(conn):
                raise AssertionError("Raider.IO sync should be skipped")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.object(websim_sync, "DB_PATH", db_path), patch.object(
                websim_sync,
                "sync_websim_cache",
                fake_websim,
            ), patch.object(websim_sync, "sync_raiderio_cache", fail_raiderio), patch.dict(
                os.environ,
                {"WOW_WEBSIM_SKIP_RAIDERIO": "1"},
                clear=False,
            ), redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = websim_sync.main()

        progress = [json.loads(line) for line in stderr.getvalue().splitlines() if line.strip()]
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(
            payload["components"]["raiderio"]["status"],
            "partial",
        )
        self.assertTrue(any(event.get("stage") == "raiderio" and event.get("status") == "skipped" for event in progress))

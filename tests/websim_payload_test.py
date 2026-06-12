import json
import io
import os
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen


class WebSimPayloadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "websim.sqlite3"
        os.environ["WOW_NEWS_DB"] = str(self.db_path)
        os.environ.pop("WOW_BLIZZARD_CLIENT_ID", None)
        os.environ.pop("WOW_BLIZZARD_CLIENT_SECRET", None)
        os.environ.pop("WOW_BNET_CLIENT_ID", None)
        os.environ.pop("WOW_BNET_CLIENT_SECRET", None)

        import importlib
        import server.news_backend as backend
        import server.websim_payload as websim_payload

        self.backend = importlib.reload(backend)
        self.websim_payload = importlib.reload(websim_payload)
        self.backend.init_db()

    def tearDown(self):
        os.environ.pop("WOW_NEWS_DB", None)
        self.tmp.cleanup()

    def test_parse_simc_trait_data_into_nodes(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 1> __trait_data_data { {
          { 8,  1, 112112,  90261, 1,  0, 117117,  386164,      0,      0,  1,  2, 200, "Frostbolt", {   64,    0,    0,    0 }, {   64,    0,    0,    0 },   0, 0 },
          { 4,  8, 123344,  99830, 1,  0,      0,       0,      0,      0,  1,  1, 100, "0", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 3 },
        } };
        """
        nodes = self.websim_payload.parse_trait_data_text(sample)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["traitId"], 112112)
        self.assertEqual(nodes[0]["classKey"], "mage")
        self.assertEqual(nodes[0]["specKey"], "frost")
        self.assertEqual(nodes[0]["row"], 1)
        self.assertEqual(nodes[0]["col"], 2)
        self.assertEqual(nodes[0]["name"], "Frostbolt")

    def test_default_selection_prefers_playable_preset_over_class_tree(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_talents
                (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
                VALUES
                ('warrior-class-1', 'warrior', 'class', '1', 1, 1, 1, 'Class Node', '{}', 'now'),
                ('mage-arcane-1', 'mage', 'arcane', '1', 1, 1, 2, 'Arcane Node', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('mage-arcane-preset', 'mage', 'arcane', 'Mage Arcane', 'mage="x"', '{}', 'now')
                """
            )
            conn.commit()
            selection = self.websim_payload.get_websim_default_selection(conn)
        finally:
            conn.close()

        self.assertEqual(selection, {"classKey": "mage", "specKey": "arcane"})

    def test_spell_sync_prioritizes_configured_class_and_spec(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.executemany(
                """
                INSERT INTO websim_talents
                (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
                VALUES (?, ?, ?, '1', ?, ?, ?, ?, '{}', 'now')
                """,
                [
                    ("warrior-arms-1", "warrior", "arms", 1, 1, 1000, "Warrior Node"),
                    ("mage-arcane-1", "mage", "arcane", 1, 2, 2000, "Arcane Node"),
                    ("mage-arcane-2", "mage", "arcane", 2, 1, 2001, "Arcane Node 2"),
                ],
            )
            conn.commit()

            spell_ids = self.websim_payload.selected_spell_ids_for_sync(conn, 3)
        finally:
            conn.close()

        self.assertEqual(spell_ids[:2], [2000, 2001])
        self.assertIn(1000, spell_ids)

    def test_build_websim_profile_preserves_simc_item_fields(self):
        profile = self.websim_payload.build_websim_profile(
            {
                "classKey": "mage",
                "specKey": "arcane",
                "talents": "C4DA",
                "scenarioKey": "single",
                "gearSelection": {
                    "items": [
                        {
                            "slot": "head",
                            "itemId": 250060,
                            "name": "Voidbreaker's Veil",
                            "ilevel": 289,
                            "bonus_id": "13534",
                            "gem_id": "240983",
                            "enchant_id": "8017",
                        }
                    ]
                },
            }
        )

        self.assertIn('mage="websim_arcane"', profile.lower())
        self.assertIn("spec=arcane", profile)
        self.assertIn("talents=C4DA", profile)
        self.assertIn("head=voidbreaker_s_veil,id=250060,ilevel=289,bonus_id=13534,gem_id=240983,enchant_id=8017", profile)
        self.assertIn("fight_style=Patchwerk", profile)

    def test_sync_reports_missing_blizzard_credentials_without_failing_simc_cache(self):
        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["dataStatus"], "blocked")
        self.assertIn("missing Blizzard API credentials", payload["errors"][0])
        self.assertIn("simc", payload)
        self.assertEqual(payload["currentSeason"]["dataStatus"], "blocked")

        conn = sqlite3.connect(self.db_path)
        try:
            loot = self.websim_payload.get_websim_loot(conn)
            self.assertEqual(loot["items"], [])
            self.assertEqual(loot["instances"], [])
            self.assertEqual(loot["dataStatus"], "blocked")
        finally:
            conn.close()

    def test_blizzard_get_uses_bearer_header_not_query_token(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"ok": true}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["auth"] = request.headers.get("Authorization")
            captured["timeout"] = timeout
            return FakeResponse()

        original_urlopen = self.websim_payload.urlopen
        self.addCleanup(setattr, self.websim_payload, "urlopen", original_urlopen)
        self.websim_payload.urlopen = fake_urlopen

        payload = self.websim_payload.blizzard_get("/data/wow/playable-class/index", "token-value")

        self.assertEqual(payload, {"ok": True})
        self.assertIn("namespace=static-us", captured["url"])
        self.assertNotIn("access_token", captured["url"])
        self.assertEqual(captured["auth"], "Bearer token-value")

    def test_http_websim_routes_return_static_page_and_json(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(f"{base}/websim/") as response:
                html = response.read().decode("utf-8")
            self.assertIn("SimC 构筑工坊", html)

            with urlopen(f"{base}/api/websim/bootstrap") as response:
                bootstrap = json.loads(response.read().decode("utf-8"))
            self.assertEqual(bootstrap["navTitle"], "WebSim")
            self.assertGreater(len(bootstrap["classes"]), 10)
            self.assertEqual(bootstrap["defaultSelection"], {"classKey": "mage", "specKey": "arcane"})
            self.assertEqual(bootstrap["dataStatus"], "blocked")
            self.assertIn("currentSeason", bootstrap)

            with urlopen(f"{base}/api/game/season") as response:
                season = json.loads(response.read().decode("utf-8"))
            self.assertEqual(season["dataStatus"], "blocked")

            request = Request(
                f"{base}/api/websim/profile",
                data=json.dumps({"classKey": "mage", "specKey": "arcane"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                profile_payload = json.loads(response.read().decode("utf-8"))
            self.assertIn("profile", profile_payload)
            self.assertIn("spec=arcane", profile_payload["profile"])
        finally:
            server.shutdown()
            server.server_close()

    def test_websim_static_response_rejects_prefix_sibling_traversal(self):
        root = Path(self.tmp.name) / "websim"
        sibling = Path(self.tmp.name) / "websim_evil"
        root.mkdir()
        sibling.mkdir()
        (sibling / "secret.txt").write_text("secret", encoding="utf-8")

        class FakeHandler:
            def __init__(self):
                self.status = None
                self.headers = []
                self.wfile = io.BytesIO()

            def send_response(self, status):
                self.status = status

            def send_header(self, key, value):
                self.headers.append((key, value))

            def end_headers(self):
                pass

        original_websim_dir = self.backend.WEBSIM_DIR
        self.backend.WEBSIM_DIR = root
        self.addCleanup(setattr, self.backend, "WEBSIM_DIR", original_websim_dir)

        handler = FakeHandler()
        self.backend.static_response(handler, "/websim/../websim_evil/secret.txt")

        self.assertEqual(handler.status, 404)
        self.assertNotIn(b"secret", handler.wfile.getvalue())

    def test_current_mythic_season_resolver_rejects_stale_dungeons(self):
        payloads = {
            "/data/wow/mythic-keystone/season/index": {
                "current_season": {"id": 12, "name": "至暗之夜 Season 1"}
            },
            "/data/wow/mythic-keystone/season/12": {
                "id": 12,
                "name": "至暗之夜 Season 1",
                "dungeons": [{"id": index, "name": name} for index, name in enumerate([
                    "Magisters' Terrace",
                    "Maisara Caverns",
                    "Nexus-Point Xenas",
                    "Windrunner Spire",
                    "Algeth'ar Academy",
                    "Pit of Saron",
                    "Seat of the Triumvirate",
                    "Skyreach",
                ], start=100)],
            },
        }
        for index, name in enumerate([
            "Magisters' Terrace",
            "Maisara Caverns",
            "Nexus-Point Xenas",
            "Windrunner Spire",
            "Algeth'ar Academy",
            "Pit of Saron",
            "Seat of the Triumvirate",
            "Skyreach",
        ], start=100):
            payloads[f"/data/wow/mythic-keystone/dungeon/{index}"] = {
                "id": index,
                "name": name,
                "journal_instance": {"id": index + 1000},
            }

        original = self.websim_payload.blizzard_get_localized
        self.addCleanup(setattr, self.websim_payload, "blizzard_get_localized", original)

        def fake_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            return payloads[path], locale

        self.websim_payload.blizzard_get_localized = fake_get
        season = self.websim_payload.resolve_current_mythic_season("token")

        self.assertEqual(season["dataStatus"], "verified")
        self.assertEqual(len(season["dungeons"]), 8)
        self.assertIn("Skyreach", [item["name"] for item in season["dungeons"]])
        self.assertNotIn("Ara-Kara, City of Echoes", [item["name"] for item in season["dungeons"]])

        payloads["/data/wow/mythic-keystone/dungeon/100"]["name"] = "Ara-Kara, City of Echoes"
        with self.assertRaisesRegex(RuntimeError, "stale Mythic\\+ dungeon"):
            self.websim_payload.resolve_current_mythic_season("token")

    def test_localized_dungeon_dedupe_uses_instance_id_when_name_is_not_latin(self):
        rows = [
            {"dungeonId": "239", "instanceId": "945", "name": "\u6267\u653f\u56e2\u4e4b\u5ea7"},
            {"dungeonId": "583", "instanceId": "945", "name": "\u6267\u653f\u56e2\u4e4b\u5ea7"},
        ]

        deduped = self.websim_payload.dedupe_dungeons_by_name(rows)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["dungeonId"], "239")


if __name__ == "__main__":
    unittest.main()

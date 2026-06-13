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
        os.environ["WOW_WEBSIM_FETCH_SIMC_REMOTE"] = "0"

        import importlib
        import server.news_backend as backend
        import server.websim_payload as websim_payload

        self.backend = importlib.reload(backend)
        self.websim_payload = importlib.reload(websim_payload)
        self.backend.init_db()

    def tearDown(self):
        os.environ.pop("WOW_NEWS_DB", None)
        os.environ.pop("WOW_WEBSIM_FETCH_SIMC_REMOTE", None)
        os.environ.pop("WOW_SIMC_TRAIT_DATA_FILE", None)
        os.environ.pop("WOW_SIMC_SPELLTEXT_DATA_FILE", None)
        self.tmp.cleanup()

    def test_parse_simc_trait_data_into_nodes(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 1> __trait_data_data { {
          { 2,  8, 112112,  90261, 1,  0, 117117,  386164,      0,      0,  1,  2, 200, "Frostbolt", {   64,    0,    0,    0 }, {   64,    0,    0,    0 },   0, 0 },
          { 4,  8, 123344,  99830, 1,  0,      0,       0,      0,      0,  1,  1, 100, "0", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 3 },
        } };
        """
        nodes = self.websim_payload.parse_trait_data_text(sample)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["traitId"], 112112)
        self.assertEqual(nodes[0]["classKey"], "mage")
        self.assertEqual(nodes[0]["specKey"], "frost")
        self.assertEqual(nodes[0]["treeType"], "spec")
        self.assertEqual(nodes[0]["row"], 1)
        self.assertEqual(nodes[0]["col"], 2)
        self.assertEqual(nodes[0]["name"], "Frostbolt")

    def test_parse_simc_trait_data_expands_class_and_hero_nodes_by_spec(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 5> __trait_data_data { {
          { 1,  8, 111111,  90001, 1,  0, 117111,  100001,      0,      0,  1,  2, 100, "Mage Class Node", {    0,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 0 },
          { 3,  8, 222221,  90002, 1,  0, 117112,  100002,      0,      0,  1,  1, 100, "Spellslinger Node", {    0,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 0 },
          { 4,  8, 333331,  90003, 1,  0,      0,       0,      0,      0,  1,  1, 100, "0", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 3 },
          { 4,  8, 333332,  90004, 1,  0,      0,       0,      0,      0,  1,  1, 200, "0", {   64,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 3 },
        } };
        static constexpr std::array<std::tuple<unsigned, std::string, unsigned>, 1> __trait_sub_tree_data { {
          { 40, "Spellslinger", 8 },
        } };
        """
        nodes = self.websim_payload.parse_trait_data_text(sample)

        class_nodes = [node for node in nodes if node["treeType"] == "class"]
        hero_nodes = [node for node in nodes if node["treeType"] == "hero"]

        self.assertEqual({node["specKey"] for node in class_nodes}, {"arcane", "fire", "frost"})
        self.assertEqual({node["specKey"] for node in hero_nodes}, {"arcane", "frost"})
        self.assertTrue(all(node["payload"]["heroKey"] == "spellslinger" for node in hero_nodes))
        self.assertTrue(all(node["payload"]["source"] == "simulationcraft" for node in nodes))

    def test_parse_simc_spelltext_data_text(self):
        sample = r'''
        // Spell text, wow build 12.0.5.67823
        static constexpr std::array<spelltext_data_t, 2> __spelltext_data { {
          { 100002, "|cFFFFFFFFArcane detail|r\r\nSecond line. $?c1[Arcane][Frost] $@spellicon443763$@spellname443763:", "Tooltip text.", "Passive" },
          { 100003, 0, "Tooltip only.", 0 },
        } };
        '''
        details = self.websim_payload.parse_spelltext_data_text(sample, [100002, 100003])

        self.assertEqual([detail["spellId"] for detail in details], [100002, 100003])
        self.assertEqual(details[0]["description"], "Arcane detail\nSecond line. Arcane / Frost\n\nTooltip text.")
        self.assertEqual(details[0]["rank"], "Passive")
        self.assertEqual(details[1]["description"], "Tooltip only.")
        self.assertEqual(details[0]["source"], "simulationcraft")

    def test_parse_wago_spell_icon_urls_from_db2_csv(self):
        spell_misc = """SpellID,SpellIconFileDataID,ActiveIconFileDataID
100002,136022,0
100003,135830,0
100004,136243,136103
"""
        manifest = """ID,FilePath,FileName
136022,Interface\\ICONS\\,Spell_Nature_EarthBind.blp
135830,Interface\\ICONS\\,Spell_Fire_Volcano.blp
136103,Interface\\ICONS\\,Spell_Nature_Swiftness.blp
"""

        icon_file_ids = self.websim_payload.parse_spell_misc_icon_file_ids_csv(spell_misc, [100002, 100003, 100004])
        icon_names = self.websim_payload.parse_manifest_interface_icon_names_csv(manifest, icon_file_ids.values())
        icon_urls = {
            spell_id: self.websim_payload.wow_icon_url(icon_names[file_id])
            for spell_id, file_id in icon_file_ids.items()
        }

        self.assertEqual(icon_file_ids[100002], 136022)
        self.assertEqual(icon_names[136022], "spell_nature_earthbind")
        self.assertEqual(icon_urls[100002], "https://render.worldofwarcraft.com/us/icons/56/spell_nature_earthbind.jpg")
        self.assertEqual(icon_urls[100004], "https://render.worldofwarcraft.com/us/icons/56/spell_nature_swiftness.jpg")

    def test_apply_trait_edges_to_simc_nodes(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 3> __trait_data_data { {
          { 2,  8, 111111,  90001, 1,  0, 117111,  100001,      0,      0,  1,  1, 100, "Root", {   62,    0,    0,    0 }, {   62,    0,    0,    0 },   0, 0 },
          { 2,  8, 111112,  90002, 1,  0, 117112,  100002,      0,      0,  2,  1, 100, "Left Child", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 0 },
          { 2,  8, 111113,  90003, 1,  0, 117113,  100003,      0,      0,  2,  2, 100, "Right Child", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 0 },
        } };
        """
        nodes = self.websim_payload.parse_trait_data_text(sample)
        edges = self.websim_payload.parse_trait_edge_data_text(
            "ID,VisualStyle,LeftTraitNodeID,RightTraitNodeID,Type\n"
            "1,1,90001,90002,2\n"
            "2,1,90003,90001,2\n"
        )
        added = self.websim_payload.apply_trait_edges_to_talents(nodes, edges, source="test")
        root_id = next(node["id"] for node in nodes if node["name"] == "Root")
        children = [node for node in nodes if node["name"].endswith("Child")]

        self.assertEqual(added, 2)
        self.assertTrue(all(child["payload"]["parentIds"] == [root_id] for child in children))
        self.assertTrue(all(child["payload"]["dependencySource"] == "test" for child in children))

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

    def test_fallback_talent_trees_cover_every_class_and_spec(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            covered = 0
            for klass in self.websim_payload.classes_payload():
                for spec in klass["specs"]:
                    covered += 1
                    payload = self.websim_payload.get_websim_talents(conn, klass["key"], spec["key"])
                    spec_hero_keys = [hero["key"] for hero in spec["heroTrees"]]
                    tree_types = {node.get("treeType") for node in payload["nodes"]}
                    nodes_by_tree = {
                        tree_type: [node for node in payload["nodes"] if node.get("treeType") == tree_type]
                        for tree_type in tree_types
                    }
                    self.assertEqual(len(spec_hero_keys), 2)
                    self.assertIn(payload["heroKey"], spec_hero_keys)
                    self.assertEqual(payload["dataStatus"], "blocked")
                    self.assertEqual(payload["talentStatus"], "fallback")
                    self.assertEqual(tree_types, {"class", "spec", "hero"})
                    self.assertEqual([section["key"] for section in payload["treeSections"]], ["class", "spec", "hero"])
                    self.assertEqual([section["reqLevel"] for section in payload["treeSections"]], [10, 11, 71])
                    self.assertEqual([section["pointCap"] for section in payload["treeSections"]], [34, 34, 13])
                    node_names = {node["name"] for node in payload["nodes"]}
                    old_english_placeholders = {
                        "Class Core",
                        "Resource Flow",
                        "Utility Choice",
                        "Throughput A",
                        "Heroic Strike",
                        "Hero Ward",
                    }
                    self.assertFalse(node_names & old_english_placeholders)
                    self.assertIn("职业核心", node_names)
                    self.assertIn("英雄打击", node_names)
                    self.assertTrue(any("顶点" in name for name in node_names))
                    self.assertGreaterEqual(len(nodes_by_tree["class"]), 28)
                    self.assertGreaterEqual(len(nodes_by_tree["spec"]), 28)
                    self.assertGreaterEqual(len(nodes_by_tree["hero"]), 10)
                    for section in payload["treeSections"]:
                        max_points = sum(node.get("maxRank", node.get("rank", 1)) for node in nodes_by_tree[section["key"]])
                        self.assertGreaterEqual(max_points, section["pointCap"])
                    self.assertTrue(any(node.get("selectedRank", 0) > 0 for node in payload["nodes"]))
                    self.assertTrue(all(node.get("iconUrl") for node in payload["nodes"]))
                    self.assertTrue(all("pointRequirement" in node for node in payload["nodes"]))
                    self.assertTrue(any(node.get("pointRequirement", 0) >= 8 for node in nodes_by_tree["class"]))
                    self.assertTrue(any(node.get("pointRequirement", 0) >= 8 for node in nodes_by_tree["spec"]))
                    self.assertTrue(any(node.get("pointRequirement", 0) >= 4 for node in nodes_by_tree["hero"]))
                    choice_groups = [node.get("choiceGroup") for node in payload["nodes"] if node.get("choiceGroup")]
                    self.assertTrue(choice_groups)
                    self.assertTrue(any(choice_groups.count(group) > 1 for group in set(choice_groups)))
            self.assertEqual(covered, 40)
        finally:
            conn.close()

    def test_talent_payload_can_select_hero_tree(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            payload = self.websim_payload.get_websim_talents(conn, "deathknight", "blood", "sanlayn")
            self.assertEqual(payload["heroKey"], "sanlayn")
            self.assertEqual(payload["treeSections"][2]["title"], "萨莱茵")
            self.assertTrue(any("萨莱茵" in node["name"] for node in payload["nodes"]))

            default_payload = self.websim_payload.get_websim_talents(conn, "deathknight", "blood")
            self.assertEqual(default_payload["heroKey"], "deathbringer")
            self.assertEqual(default_payload["treeSections"][2]["title"], "死亡使者")

            invalid_payload = self.websim_payload.get_websim_talents(conn, "deathknight", "blood", "rider_of_the_apocalypse")
            self.assertEqual(invalid_payload["heroKey"], "deathbringer")
        finally:
            conn.close()

    def test_talent_payload_uses_simc_nodes_when_season_is_blocked(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 4> __trait_data_data { {
          { 1,  8, 111111,  90001, 1,  0, 117111,  100001,      0,      0,  1,  2, 100, "Mage Class Node", {    0,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 0 },
          { 2,  8, 111112,  90002, 1,  0, 117112,  100002,      0,      0,  1,  4, 100, "Arcane Spec Node", {   62,    0,    0,    0 }, {   62,    0,    0,    0 },   0, 0 },
          { 3,  8, 111113,  90003, 1,  0, 117113,  100003,      0,      0,  1,  1, 100, "Spellslinger Node", {    0,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 0 },
          { 4,  8, 111114,  90004, 1,  0,      0,       0,      0,      0,  1,  1, 100, "0", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },  40, 3 },
        } };
        static constexpr std::array<std::tuple<unsigned, std::string, unsigned>, 1> __trait_sub_tree_data { {
          { 40, "Spellslinger", 8 },
        } };
        """
        trait_file = Path(self.tmp.name) / "trait_data.inc"
        trait_file.write_text(sample, encoding="utf-8")
        spelltext_file = Path(self.tmp.name) / "spelltext_data.inc"
        spelltext_file.write_text(
            r'''
            // Spell text, wow build 12.0.5.67823
            static constexpr std::array<spelltext_data_t, 3> __spelltext_data { {
              { 100001, "Class tooltip from SimC.", 0, 0 },
              { 100002, "Arcane tooltip from SimC.", 0, 0 },
              { 100003, "Hero tooltip from SimC.", 0, 0 },
            } };
            ''',
            encoding="utf-8",
        )
        os.environ["WOW_SIMC_TRAIT_DATA_FILE"] = str(trait_file)
        os.environ["WOW_SIMC_SPELLTEXT_DATA_FILE"] = str(spelltext_file)
        original_wago = self.websim_payload.download_wago_db2_csv
        self.addCleanup(setattr, self.websim_payload, "download_wago_db2_csv", original_wago)

        def fake_wago_csv(table, build):
            self.assertEqual(build, "12.0.5.67823")
            if table == "SpellMisc":
                return (
                    "SpellID,SpellIconFileDataID,ActiveIconFileDataID\n"
                    "100001,136022,0\n"
                    "100002,135846,0\n"
                    "100003,135830,0\n",
                    "wago://SpellMisc",
                )
            if table == "ManifestInterfaceData":
                return (
                    "ID,FilePath,FileName\n"
                    "136022,Interface\\ICONS\\,Spell_Nature_EarthBind.blp\n"
                    "135846,Interface\\ICONS\\,Spell_Frost_FrostBolt02.blp\n"
                    "135830,Interface\\ICONS\\,Spell_Fire_Volcano.blp\n",
                    "wago://ManifestInterfaceData",
                )
            return "ID,VisualStyle,LeftTraitNodeID,RightTraitNodeID,Type\n", "wago://TraitEdge"

        self.websim_payload.download_wago_db2_csv = fake_wago_csv

        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_simc_generated_data(conn)
            conn.commit()
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        self.assertEqual(counts["source"], str(trait_file))
        self.assertEqual(counts["talents"], 5)
        self.assertEqual(counts["spellDetails"], 3)
        self.assertEqual(counts["spellIcons"], 3)
        self.assertEqual(counts["spellTextSource"], str(spelltext_file))
        self.assertIn("ManifestInterfaceData", counts["spellIconSource"])
        self.assertEqual(payload["dataStatus"], "blocked")
        self.assertEqual(payload["talentStatus"], "simc")
        self.assertEqual(payload["heroKey"], "spellslinger")
        self.assertEqual({node["treeType"] for node in payload["nodes"]}, {"class", "spec", "hero"})
        self.assertEqual({node["name"] for node in payload["nodes"]}, {"Mage Class Node", "Arcane Spec Node", "Spellslinger Node"})
        self.assertIn("Arcane tooltip from SimC.", {node["description"] for node in payload["nodes"]})
        self.assertTrue(all(node["iconUrl"] for node in payload["nodes"]))
        self.assertIn("spell_frost_frostbolt02.jpg", {node["iconUrl"].rsplit("/", 1)[-1] for node in payload["nodes"]})

    def test_talent_payload_default_hero_matches_spec_picker_order(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for klass in self.websim_payload.classes_payload():
                for spec in klass["specs"]:
                    first_hero = spec["heroTrees"][0]["key"]
                    payload = self.websim_payload.get_websim_talents(conn, klass["key"], spec["key"])
                    self.assertEqual(payload["heroKey"], first_hero)
        finally:
            conn.close()

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

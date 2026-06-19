import json
import io
import gc
import os
import sqlite3
import tempfile
import threading
import time
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
        os.environ.pop("WOW_RAIDERIO_API_KEY", None)
        os.environ.pop("WOW_WARCRAFTLOGS_CLIENT_ID", None)
        os.environ.pop("WOW_WARCRAFTLOGS_CLIENT_SECRET", None)
        os.environ.pop("WOW_WARCRAFTLOGS_API_KEY", None)
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
        os.environ.pop("WOW_WEBSIM_FETCH_WAGO_DB2_TRAIT_EDGE", None)
        os.environ.pop("WOW_SIMC_TRAIT_DATA_FILE", None)
        os.environ.pop("WOW_SIMC_SPELLTEXT_DATA_FILE", None)
        os.environ.pop("WOW_SIMC_BIN", None)
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        for attempt in range(5):
            try:
                self.tmp.cleanup()
                break
            except PermissionError:
                if attempt == 4:
                    raise
                gc.collect()
                time.sleep(0.1)

    def insert_websim_talent(
        self,
        conn,
        node_id,
        tree_type,
        trait_id,
        row,
        col,
        name,
        *,
        rank=1,
        granted_rank=0,
        parent_ids=None,
        choice_group="",
        class_key="mage",
        spec_key="arcane",
        hero_key="",
        class_id=8,
        spec_id=62,
        spell_id=None,
        point_requirement=0,
    ):
        spell_id = spell_id or trait_id + 100000
        payload = {
            "treeType": tree_type,
            "treeIndex": {"class": 1, "spec": 2, "hero": 3}.get(tree_type, 2),
            "classId": class_id,
            "specId": spec_id,
            "traitId": trait_id,
            "nodeId": trait_id + 500000,
            "selectionIndex": row * 10 + col,
            "rank": rank,
            "maxRank": rank,
            "selectedRank": granted_rank,
            "grantedRank": granted_rank,
            "granted": granted_rank > 0,
            "parentIds": parent_ids or [],
            "choiceGroup": choice_group,
            "shape": "choice" if choice_group else "square",
            "pointRequirement": point_requirement,
            "source": "simulationcraft",
        }
        if tree_type == "hero":
            payload["heroKey"] = hero_key or "spellslinger"
            payload["heroLabel"] = "Spellslinger"
        conn.execute(
            """
            INSERT INTO websim_talents
            (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'now')
            """,
            (
                node_id,
                class_key,
                spec_key,
                f"{tree_type}:{class_key}:{spec_key}" if tree_type != "hero" else f"hero:{payload.get('heroKey')}",
                row,
                col,
                spell_id,
                name,
                json.dumps(payload),
            ),
        )

    def seed_websim_encoder_nodes(self, conn):
        self.websim_payload.ensure_websim_tables(conn)
        self.insert_websim_talent(conn, "simc-class-1001-mage-arcane", "class", 1001, 1, 1, "Class Talent")
        self.insert_websim_talent(conn, "simc-spec-2001-mage-arcane", "spec", 2001, 1, 2, "Spec Talent")
        self.insert_websim_talent(conn, "simc-hero-3001-mage-arcane-spellslinger", "hero", 3001, 2, 1, "Hero Talent")
        conn.commit()

    def seed_websim_current_fixture_nodes(self, conn):
        self.websim_payload.ensure_websim_tables(conn)
        self.insert_websim_talent(
            conn,
            "simc-class-80180-mage-arcane",
            "class",
            80180,
            1,
            1,
            "Prismatic Barrier",
            granted_rank=1,
        )
        self.insert_websim_talent(conn, "simc-spec-126537-mage-arcane", "spec", 126537, 1, 2, "Arcane Missiles")
        self.insert_websim_talent(
            conn,
            "simc-hero-117267-mage-arcane-spellslinger",
            "hero",
            117267,
            1,
            1,
            "Splintering Sorcery",
            hero_key="spellslinger",
            granted_rank=1,
            point_requirement=1,
        )
        conn.commit()

    def full_core_simc_gear_items(self):
        slots = [
            "head",
            "neck",
            "shoulder",
            "back",
            "chest",
            "wrist",
            "hands",
            "waist",
            "legs",
            "feet",
            "finger1",
            "finger2",
            "trinket1",
            "trinket2",
            "main_hand",
        ]
        return [
            {
                "slot": slot,
                "itemId": 250000 + index,
                "name": f"Verified {slot.title()}",
                "ilevel": 289,
                "bonus_id": "13534",
            }
            for index, slot in enumerate(slots, start=1)
        ]

    def websim_encoder_payload(self, extra=None):
        payload = {
            "classKey": "mage",
            "specKey": "arcane",
            "heroKey": "spellslinger",
            "scenarioKey": "single",
            "talents": "websim:mage:arcane:spellslinger:simc-class-1001-mage-arcane:1",
            "talentState": {
                "selectedNodes": [
                    {"id": "simc-class-1001-mage-arcane", "rank": 1},
                    {"id": "simc-spec-2001-mage-arcane", "rank": 1},
                    {"id": "simc-hero-3001-mage-arcane-spellslinger", "rank": 1},
                ]
            },
            "gearSelection": {
                "items": self.full_core_simc_gear_items()
            },
            "guestId": "websim-test-guest",
            "saveTask": True,
        }
        if extra:
            payload.update(extra)
        return payload

    def post_backend_json(self, path, payload):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = Request(
                f"{base}{path}",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

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

    def test_parse_simc_trait_data_groups_multi_rank_apex_nodes(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 3> __trait_data_data { {
          { 2,  7, 136974, 110402, 1, 20, 141737, 1270061,      0,      0, 11,  4, 300, "Feedback Loop", {  262,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 1 },
          { 2,  7, 136973, 110402, 2, 20, 141736, 1270062,      0,      0, 11,  4, 400, "Feedback Loop", {  262,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 1 },
          { 2,  7, 136972, 110402, 1, 20, 141735, 1270064,      0,      0, 11,  4, 500, "Feedback Loop", {  262,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 1 },
        } };
        """
        nodes = self.websim_payload.parse_trait_data_text(sample)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Feedback Loop")
        self.assertEqual(nodes[0]["payload"]["shape"], "apex")
        self.assertEqual(nodes[0]["rank"], 4)
        self.assertEqual(nodes[0]["payload"]["maxRank"], 4)
        self.assertEqual([entry["rank"] for entry in nodes[0]["payload"]["rankEntries"]], [1, 2, 3])
        self.assertEqual([entry["points"] for entry in nodes[0]["payload"]["rankEntries"]], [1, 2, 1])
        self.assertEqual([entry["spellId"] for entry in nodes[0]["payload"]["rankEntries"]], [1270061, 1270062, 1270064])
        self.assertEqual(self.websim_payload.simc_talent_spell_ids(nodes), [1270061, 1270062, 1270064])

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
        self.assertEqual(icon_urls[100002], "https://wow.zamimg.com/images/wow/icons/large/spell_nature_earthbind.jpg")
        self.assertEqual(icon_urls[100004], "https://wow.zamimg.com/images/wow/icons/large/spell_nature_swiftness.jpg")

    def test_wago_icon_sync_creates_details_for_talent_spell_ids(self):
        original_wago = self.websim_payload.download_wago_db2_csv
        self.addCleanup(setattr, self.websim_payload, "download_wago_db2_csv", original_wago)

        def fake_wago_csv(table, build):
            self.assertEqual(build, "12.0.5.67823")
            if table == "SpellMisc":
                return (
                    "SpellID,SpellIconFileDataID,ActiveIconFileDataID\n"
                    "100002,136022,0\n",
                    "wago://SpellMisc",
                )
            if table == "ManifestInterfaceData":
                return (
                    "ID,FilePath,FileName\n"
                    "136022,Interface\\ICONS\\,Spell_Nature_EarthBind.blp\n",
                    "wago://ManifestInterfaceData",
                )
            return "", "wago://empty"

        self.websim_payload.download_wago_db2_csv = fake_wago_csv
        data = {
            "talents": [{"spellId": 100002, "name": "Earthbind Talent"}],
            "spellDetails": [],
        }

        self.websim_payload.attach_wago_spell_icons_to_data(data, "// wow build 12.0.5.67823")

        self.assertEqual(data["spellIcons"], 1)
        self.assertEqual(len(data["spellDetails"]), 1)
        self.assertEqual(data["spellDetails"][0]["name"], "Earthbind Talent")
        self.assertEqual(
            data["spellDetails"][0]["iconUrl"],
            "https://wow.zamimg.com/images/wow/icons/large/spell_nature_earthbind.jpg",
        )

    def test_wago_localization_replaces_simc_spell_text(self):
        original_wago = self.websim_payload.download_wago_db2_csv
        self.addCleanup(setattr, self.websim_payload, "download_wago_db2_csv", original_wago)
        original_localization = self.websim_payload.DEFAULT_WAGO_DB2_LOCALIZATION_ENABLED
        self.addCleanup(
            setattr,
            self.websim_payload,
            "DEFAULT_WAGO_DB2_LOCALIZATION_ENABLED",
            original_localization,
        )
        self.websim_payload.DEFAULT_WAGO_DB2_LOCALIZATION_ENABLED = True

        def fake_wago_csv(table, build, locale="enUS"):
            self.assertEqual(build, "12.0.5.67823")
            if table == "SpellName":
                self.assertEqual(locale, "zh_CN")
                return "ID,Name_lang\n100002,大地之缚\n", "wago://SpellName"
            if table == "Spell":
                self.assertEqual(locale, "zh_CN")
                return (
                    "ID,NameSubtext_lang,Description_lang,AuraDescription_lang\n"
                    "100002,被动,使目标减速。,移动速度降低。\n"
                ), "wago://Spell"
            return "", f"wago://{table}"

        self.websim_payload.download_wago_db2_csv = fake_wago_csv
        data = {
            "talents": [{"spellId": 100002, "name": "Earthbind Talent"}],
            "spellDetails": [
                {
                    "spellId": 100002,
                    "name": "Earthbind Talent",
                    "description": "English description.",
                    "tooltip": "",
                    "rank": "",
                    "iconUrl": "",
                    "locale": "en_US",
                    "source": "simulationcraft",
                }
            ],
        }

        self.websim_payload.attach_wago_spell_icons_to_data(data, "// wow build 12.0.5.67823")

        self.assertEqual(data["spellLocalizations"], 1)
        self.assertEqual(data["spellDetails"][0]["name"], "大地之缚")
        self.assertEqual(data["spellDetails"][0]["description"], "使目标减速。\n\n移动速度降低。")
        self.assertEqual(data["spellDetails"][0]["rank"], "被动")
        self.assertEqual(data["spellDetails"][0]["locale"], "zh_CN")

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

    def test_trait_edge_sync_works_when_wago_heavy_tables_are_disabled(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 2> __trait_data_data { {
          { 2,  8, 111111,  90001, 1,  0, 117111,  100001,      0,      0,  1,  1, 100, "Root", {   62,    0,    0,    0 }, {   62,    0,    0,    0 },   0, 0 },
          { 2,  8, 111112,  90002, 1,  0, 117112,  100002,      0,      0,  2,  1, 100, "Child", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 0 },
        } };
        """
        original_wago_enabled = self.websim_payload.DEFAULT_WAGO_DB2_ENABLED
        original_trait_edge = self.websim_payload.download_wago_trait_edge_csv
        original_wago = self.websim_payload.download_wago_db2_csv
        self.addCleanup(setattr, self.websim_payload, "DEFAULT_WAGO_DB2_ENABLED", original_wago_enabled)
        self.addCleanup(setattr, self.websim_payload, "download_wago_trait_edge_csv", original_trait_edge)
        self.addCleanup(setattr, self.websim_payload, "download_wago_db2_csv", original_wago)
        self.websim_payload.DEFAULT_WAGO_DB2_ENABLED = False
        generic_tables = []

        def fake_wago_csv(table, build, locale="enUS"):
            generic_tables.append(table)
            return "", f"wago://{table}"

        def fake_trait_edge_csv(build):
            self.assertEqual(build, "12.0.5.67823")
            return (
                "ID,VisualStyle,LeftTraitNodeID,RightTraitNodeID,Type\n"
                "1,1,90001,90002,2\n",
                "wago://TraitEdge",
            )

        self.websim_payload.download_wago_db2_csv = fake_wago_csv
        self.websim_payload.download_wago_trait_edge_csv = fake_trait_edge_csv

        data = self.websim_payload.extract_simc_data_from_trait_text(sample, "sample")

        self.assertEqual(data["dependencies"], 1)
        self.assertEqual(data["traitEdgeSource"], "wago://TraitEdge")
        self.assertNotIn("TraitEdge", generic_tables)

    def test_trait_edge_fetch_can_be_disabled_without_network(self):
        original_enabled = self.websim_payload.DEFAULT_WAGO_DB2_TRAIT_EDGE_ENABLED
        original_urlopen = self.websim_payload.urlopen
        self.addCleanup(setattr, self.websim_payload, "DEFAULT_WAGO_DB2_TRAIT_EDGE_ENABLED", original_enabled)
        self.addCleanup(setattr, self.websim_payload, "urlopen", original_urlopen)
        self.websim_payload.DEFAULT_WAGO_DB2_TRAIT_EDGE_ENABLED = False

        def fail_urlopen(*_args, **_kwargs):
            raise AssertionError("TraitEdge fetch should not hit the network when disabled")

        self.websim_payload.urlopen = fail_urlopen

        self.assertEqual(self.websim_payload.download_wago_trait_edge_csv("12.0.5.67823"), ("", ""))

    def test_sync_simc_generated_data_reports_trait_edge_dependencies(self):
        sample = """
        // Player trait definitions, wow build 12.0.5.67823
        static constexpr std::array<trait_data_t, 2> __trait_data_data { {
          { 2,  8, 111111,  90001, 1,  0, 117111,  100001,      0,      0,  1,  1, 100, "Root", {   62,    0,    0,    0 }, {   62,    0,    0,    0 },   0, 0 },
          { 2,  8, 111112,  90002, 1,  0, 117112,  100002,      0,      0,  2,  1, 100, "Child", {   62,    0,    0,    0 }, {    0,    0,    0,    0 },   0, 0 },
        } };
        """
        trait_file = Path(self.tmp.name) / "trait_data_edges.inc"
        trait_file.write_text(sample, encoding="utf-8")
        os.environ["WOW_SIMC_TRAIT_DATA_FILE"] = str(trait_file)
        original_trait_edge = self.websim_payload.download_wago_trait_edge_csv
        self.addCleanup(setattr, self.websim_payload, "download_wago_trait_edge_csv", original_trait_edge)

        def fake_trait_edge_csv(build):
            self.assertEqual(build, "12.0.5.67823")
            return (
                "ID,VisualStyle,LeftTraitNodeID,RightTraitNodeID,Type\n"
                "1,1,90001,90002,2\n",
                "wago://TraitEdge",
            )

        self.websim_payload.download_wago_trait_edge_csv = fake_trait_edge_csv
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_simc_generated_data(conn)
            rows = conn.execute("SELECT id, payload_json FROM websim_talents").fetchall()
        finally:
            conn.close()

        parent_payloads = {
            row_id: json.loads(payload_json)
            for row_id, payload_json in rows
            if json.loads(payload_json).get("parentIds")
        }
        self.assertEqual(counts["dependencies"], 1)
        self.assertEqual(counts["traitEdgeSource"], "wago://TraitEdge")
        self.assertEqual(len(parent_payloads), 1)
        self.assertTrue(next(iter(parent_payloads.values()))["parentIds"])

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
                    self.assertEqual(payload["talentSchemaRevision"], self.websim_payload.TALENT_SCHEMA_REVISION)
                    self.assertEqual(payload["talentAuthority"]["runtimeSource"], "fallback")
                    self.assertEqual(payload["talentAuthority"]["diffStatus"], "blocked")
                    self.assertEqual(payload["talentAuthority"]["official"]["status"], "not_configured")
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
                    granted_nodes = [node for node in payload["nodes"] if node.get("grantedRank", 0) > 0]
                    self.assertTrue(granted_nodes)
                    self.assertTrue(all(node.get("granted") for node in granted_nodes))
                    self.assertTrue(all(node.get("iconUrl") for node in payload["nodes"]))
                    self.assertTrue(all(node.get("gameAsset", {}).get("iconUrl") == node.get("iconUrl") for node in payload["nodes"]))
                    self.assertTrue(all(node.get("gameAsset", {}).get("entityType") == "talent" for node in payload["nodes"]))
                    self.assertTrue(all(node.get("gameAsset", {}).get("resolutionTier") == "icon_56" for node in payload["nodes"]))
                    self.assertTrue(all("pointRequirement" in node for node in payload["nodes"]))
                    self.assertTrue(all(node.get("schemaRevision") == self.websim_payload.TALENT_SCHEMA_REVISION for node in payload["nodes"]))
                    self.assertTrue(all(node.get("parentMode") in {"any", "all"} for node in payload["nodes"]))
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

    def test_talent_authority_matrix_covers_every_spec_and_hero_tree(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            covered_specs = 0
            covered_hero_trees = 0
            for klass in self.websim_payload.classes_payload():
                for spec in klass["specs"]:
                    covered_specs += 1
                    for hero in spec["heroTrees"]:
                        covered_hero_trees += 1
                        payload = self.websim_payload.get_websim_talents(conn, klass["key"], spec["key"], hero["key"])
                        self.assertEqual(payload["talentSchemaRevision"], self.websim_payload.TALENT_SCHEMA_REVISION)
                        self.assertEqual(payload["talentAuthority"]["schemaRevision"], self.websim_payload.TALENT_SCHEMA_REVISION)
                        self.assertIn(payload["talentAuthority"]["diffStatus"], {"blocked", "pending_official_audit", "verified", "stale", "incompatible"})
                        self.assertEqual(payload["heroKey"], hero["key"])
                        self.assertEqual({section["key"] for section in payload["treeSections"]}, {"class", "spec", "hero"})
                        self.assertEqual({node["treeType"] for node in payload["nodes"]}, {"class", "spec", "hero"})
            self.assertEqual(covered_specs, 40)
            self.assertEqual(covered_hero_trees, 80)
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
        original_trait_edge = self.websim_payload.download_wago_trait_edge_csv
        self.addCleanup(setattr, self.websim_payload, "download_wago_db2_csv", original_wago)
        self.addCleanup(setattr, self.websim_payload, "download_wago_trait_edge_csv", original_trait_edge)

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

        def fake_trait_edge_csv(build):
            self.assertEqual(build, "12.0.5.67823")
            return (
                "ID,VisualStyle,LeftTraitNodeID,RightTraitNodeID,Type\n"
                "1,1,90001,90001,0\n",
                "wago://TraitEdge",
            )

        self.websim_payload.download_wago_db2_csv = fake_wago_csv
        self.websim_payload.download_wago_trait_edge_csv = fake_trait_edge_csv

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
        self.assertEqual(counts["dependencies"], 0)
        self.assertEqual(counts["traitEdgeSource"], "")
        self.assertEqual(payload["dataStatus"], "blocked")
        self.assertEqual(payload["talentStatus"], "simc")
        self.assertEqual(payload["talentSchemaRevision"], self.websim_payload.TALENT_SCHEMA_REVISION)
        self.assertEqual(payload["talentAuthority"]["runtimeSource"], "simc")
        self.assertEqual(payload["talentAuthority"]["runtime"]["traitEdgeSource"], "")
        self.assertEqual(payload["talentAuthority"]["official"]["status"], "not_configured")
        self.assertEqual(payload["talentAuthority"]["diffStatus"], "pending_official_audit")
        self.assertEqual(payload["heroKey"], "spellslinger")
        self.assertEqual({node["treeType"] for node in payload["nodes"]}, {"class", "spec", "hero"})
        self.assertEqual({node["name"] for node in payload["nodes"]}, {"Mage Class Node", "Arcane Spec Node", "Spellslinger Node"})
        self.assertIn("Arcane tooltip from SimC.", {node["description"] for node in payload["nodes"]})
        self.assertTrue(all(node["iconUrl"] for node in payload["nodes"]))
        self.assertTrue(all(node["gameAsset"]["iconUrl"] == node["iconUrl"] for node in payload["nodes"]))
        self.assertTrue(all(node["gameAsset"]["entityType"] == "talent" for node in payload["nodes"]))
        self.assertTrue(all("talent_simulator" in node["gameAsset"]["usage"] for node in payload["nodes"]))
        self.assertTrue(all(node["gameAsset"]["source"] == "simulationcraft" for node in payload["nodes"]))
        self.assertTrue(all(node["gameAsset"]["status"] == "partial" for node in payload["nodes"]))
        self.assertTrue(all(node["entryId"] for node in payload["nodes"]))
        self.assertTrue(all(node["parentMode"] in {"any", "all"} for node in payload["nodes"]))
        self.assertTrue(all(node["schemaRevision"] == self.websim_payload.TALENT_SCHEMA_REVISION for node in payload["nodes"]))
        self.assertIn("spell_frost_frostbolt02.jpg", {node["iconUrl"].rsplit("/", 1)[-1] for node in payload["nodes"]})

    def test_asset_registry_records_and_queries_item_metadata(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            saved = self.websim_payload.save_websim_item_metadata(
                conn,
                "250111",
                {
                    "name": "虚空粉碎者的面纱",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg"}]},
                fallback_name="Voidshredder Hood",
                fallback_slot="head",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250111",
                {
                    "name": "虚空粉碎者的面纱",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg"}]},
                fallback_name="Voidshredder Hood",
                fallback_slot="head",
            )
            conn.commit()

            assets = self.websim_payload.get_websim_assets(
                conn,
                {"entityType": "item", "entityId": "250111", "context": "websim-item-metadata"},
            )
        finally:
            conn.close()

        self.assertEqual(saved["gameAsset"]["id"], "item:250111:websim-item-metadata")
        self.assertEqual(len(assets["assets"]), 1)
        asset = assets["assets"][0]
        self.assertEqual(asset["entityType"], "item")
        self.assertEqual(asset["entityId"], "250111")
        self.assertEqual(asset["contextKey"], "websim-item-metadata")
        self.assertEqual(asset["iconUrl"], "https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg")
        self.assertEqual(asset["resolutionTier"], "icon_56")
        self.assertEqual(asset["source"], "blizzard")
        self.assertEqual(asset["status"], "verified")
        self.assertIn("gear", asset["semanticTags"])
        self.assertIn("websim_gear", asset["usage"])
        self.assertEqual(assets["counts"]["byStatus"]["verified"], 1)

    def test_asset_registry_does_not_downgrade_verified_assets(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            verified = self.websim_payload.game_asset_from_icon_url(
                "spell",
                "123",
                "websim-spell-details",
                "https://render.worldofwarcraft.com/us/icons/56/spell_frost_frostbolt02.jpg",
                source="blizzard",
                status="verified",
                semantic_tags=["game", "spell"],
                usage=["talent_simulator"],
                fallback_text="FB",
            )
            partial = self.websim_payload.game_asset_from_icon_url(
                "spell",
                "123",
                "websim-spell-details",
                "https://cdn.example.test/frostbolt.jpg",
                source="simulationcraft",
                status="partial",
                semantic_tags=["game", "spell"],
                usage=["talent_simulator"],
                fallback_text="FB",
            )

            self.websim_payload.upsert_websim_asset(conn, verified)
            self.websim_payload.upsert_websim_asset(conn, partial)
            conn.commit()
            assets = self.websim_payload.get_websim_assets(
                conn,
                {"entityType": "spell", "entityId": "123", "context": "websim-spell-details"},
            )
        finally:
            conn.close()

        self.assertEqual(len(assets["assets"]), 1)
        self.assertEqual(assets["assets"][0]["source"], "blizzard")
        self.assertEqual(assets["assets"][0]["status"], "verified")
        self.assertEqual(
            assets["assets"][0]["iconUrl"],
            "https://render.worldofwarcraft.com/us/icons/56/spell_frost_frostbolt02.jpg",
        )

    def test_asset_upsert_initializes_registry_table(self):
        conn = sqlite3.connect(":memory:")
        try:
            asset = self.websim_payload.game_asset_from_icon_url(
                "spell",
                "456",
                "websim-spell-details",
                "https://render.worldofwarcraft.com/us/icons/56/spell_arcane_blast.jpg",
                source="blizzard",
                status="verified",
                semantic_tags=["game", "spell"],
                usage=["talent_simulator"],
                fallback_text="AB",
            )

            self.websim_payload.upsert_websim_asset(conn, asset)
            conn.commit()
            assets = self.websim_payload.get_websim_assets(
                conn,
                {"entityType": "spell", "entityId": "456", "context": "websim-spell-details"},
            )
        finally:
            conn.close()

        self.assertEqual(len(assets["assets"]), 1)
        self.assertEqual(assets["assets"][0]["source"], "blizzard")
        self.assertEqual(assets["assets"][0]["status"], "verified")

    def test_blizzard_icon_url_requires_exact_allowed_host(self):
        self.assertTrue(
            self.websim_payload.is_blizzard_icon_url(
                "https://render.worldofwarcraft.com/us/icons/56/spell_arcane_blast.jpg"
            )
        )
        self.assertFalse(
            self.websim_payload.is_blizzard_icon_url(
                "https://evil.example.test/render.worldofwarcraft.com/us/icons/56/spell_arcane_blast.jpg"
            )
        )
        self.assertFalse(
            self.websim_payload.is_blizzard_icon_url(
                "https://render.worldofwarcraft.com.evil.example.test/us/icons/56/spell_arcane_blast.jpg"
            )
        )

    def test_talent_payload_dedupes_cached_non_choice_nodes_and_marks_apex(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            payload_json = json.dumps(
                {
                    "treeType": "spec",
                    "nodeId": 90001,
                    "traitId": 111111,
                    "rank": 1,
                    "shape": "circle",
                    "source": "simulationcraft",
                }
            )
            duplicate_payload_json = json.dumps(
                {
                    "treeType": "spec",
                    "nodeId": 90001,
                    "traitId": 111112,
                    "rank": 1,
                    "shape": "circle",
                    "source": "simulationcraft",
                }
            )
            conn.executemany(
                """
                INSERT INTO websim_talents
                (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
                VALUES (?, 'mage', 'arcane', 'spec:mage:arcane', 11, 3, ?, ?, ?, 'now')
                """,
                [
                    ("simc-spec-111111-mage-arcane", 100001, "Apex Talent", payload_json),
                    ("simc-spec-111112-mage-arcane", 100002, "Apex Talent Rank", duplicate_payload_json),
                ],
            )
            conn.commit()
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        self.assertEqual(len(payload["nodes"]), 1)
        self.assertEqual(payload["nodes"][0]["shape"], "apex")
        self.assertEqual(payload["nodes"][0]["nodeId"], 90001)

    def test_talent_payload_enriches_multi_rank_tooltip_entries(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            payload_json = json.dumps(
                {
                    "treeType": "spec",
                    "nodeId": 110402,
                    "traitId": 136974,
                    "rank": 4,
                    "maxRank": 4,
                    "shape": "apex",
                    "source": "simulationcraft",
                    "rankEntries": [
                        {"rank": 1, "points": 1, "pointStart": 1, "pointEnd": 1, "traitId": 136974, "spellId": 1270061, "selectionIndex": 300},
                        {"rank": 2, "points": 2, "pointStart": 2, "pointEnd": 3, "traitId": 136973, "spellId": 1270062, "selectionIndex": 400},
                        {"rank": 3, "points": 1, "pointStart": 4, "pointEnd": 4, "traitId": 136972, "spellId": 1270064, "selectionIndex": 500},
                    ],
                }
            )
            conn.execute(
                """
                INSERT INTO websim_talents
                (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
                VALUES ('simc-spec-136974-shaman-elemental', 'shaman', 'elemental', 'spec:shaman:elemental', 11, 4, 1270061, 'Feedback Loop', ?, 'now')
                """,
                (payload_json,),
            )
            conn.executemany(
                """
                INSERT INTO websim_spell_details
                (id, spell_id, name, description, icon_url, locale, payload_json, updated_at)
                VALUES (?, ?, ?, ?, '', 'en_US', '{}', 'now')
                """,
                [
                    ("1270061", 1270061, "Feedback Loop", "Rank one description."),
                    ("1270062", 1270062, "Feedback Loop", "Rank two description."),
                    ("1270064", 1270064, "Feedback Loop", "Rank three description."),
                ],
            )
            conn.commit()
            payload = self.websim_payload.get_websim_talents(conn, "shaman", "elemental")
        finally:
            conn.close()

        node = payload["nodes"][0]
        self.assertEqual(node["maxRank"], 4)
        self.assertEqual(node["rankCount"], 3)
        self.assertEqual([entry["description"] for entry in node["rankEntries"]], [
            "Rank one description.",
            "Rank two description.",
            "Rank three description.",
        ])

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

    def test_talent_payload_marks_hero_first_row_as_granted_for_cached_nodes(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            payload_json = json.dumps(
                {
                    "treeType": "hero",
                    "heroKey": "deathbringer",
                    "rank": 1,
                    "selectedRank": 0,
                    "source": "simulationcraft",
                }
            )
            conn.execute(
                """
                INSERT INTO websim_talents
                (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
                VALUES (?, 'deathknight', 'blood', 'hero:deathbringer', 1, 2, 434765, 'Reaper Mark', ?, 'now')
                """,
                ("simc-hero-123-deathknight-blood-deathbringer", payload_json),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_talents(conn, "deathknight", "blood", "deathbringer")
        finally:
            conn.close()

        hero = next(node for node in payload["nodes"] if node["treeType"] == "hero")
        self.assertEqual(hero["selectedRank"], 1)
        self.assertEqual(hero["grantedRank"], 1)
        self.assertTrue(hero["granted"])

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

    def test_websim_gear_canonicalizes_slots_and_skips_incomplete_loot(self):
        preset_item = self.websim_payload.normalize_gear_item(
            {"slot": "wrists", "itemId": 250111, "name": "Preset Bracers", "sourceType": "simcPreset"},
            "mage",
            "arcane",
        )
        self.assertEqual(preset_item["slot"], "wrist")
        self.assertTrue(preset_item["simcReady"])

        loot_item = self.websim_payload.normalize_gear_item(
            {"slot": "wrist", "itemId": 250222, "name": "Loot Bracers", "sourceType": "verifiedLoot"},
            "mage",
            "arcane",
        )
        self.assertFalse(loot_item["simcReady"])
        self.assertIn("ilevel", loot_item["missingFields"])

        profile = self.websim_payload.build_websim_profile(
            {
                "classKey": "mage",
                "specKey": "arcane",
                "talents": "C4DA",
                "gearSelection": {"items": [loot_item]},
            }
        )
        self.assertNotIn("loot_bracers", profile)
        self.assertNotIn("id=250222", profile)

    def test_websim_gear_ignores_client_supplied_game_asset_provenance(self):
        item = self.websim_payload.normalize_gear_item(
            {
                "slot": "head",
                "itemId": 250333,
                "name": "Manual Hood",
                "iconUrl": "https://cdn.example.test/manual-hood.jpg",
                "sourceType": "manual",
                "gameAsset": {
                    "id": "item:250333:websim-gear-item",
                    "iconUrl": "https://render.worldofwarcraft.com/us/icons/56/spoofed.jpg",
                    "source": "blizzard",
                    "status": "verified",
                },
            },
            "mage",
            "arcane",
        )

        self.assertEqual(item["gameAsset"]["iconUrl"], "https://cdn.example.test/manual-hood.jpg")
        self.assertEqual(item["gameAsset"]["source"], "manual")
        self.assertNotEqual(item["iconUrl"], "https://render.worldofwarcraft.com/us/icons/56/spoofed.jpg")

    def test_websim_gear_payload_includes_preset_baseline_and_slot_groups(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "talents=C4DA",
                    "wrist=preset_bracers,id=250111,ilevel=289,bonus_id=13534",
                    "trinket1=preset_trinket,id=250222",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-mage-arcane', 'mage', 'arcane', 'Preset Mage', ?, '{}', 'now')
                """,
                (profile,),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        self.assertIsInstance(payload["slots"][0], dict)
        self.assertEqual(payload["baselineSet"][0]["slot"], "wrist")
        self.assertTrue(payload["baselineSet"][0]["simcReady"])
        wrist_group = next(group for group in payload["slotGroups"] if group["slot"] == "wrist")
        self.assertTrue(any(item["itemId"] == "250111" for item in wrist_group["items"]))
        self.assertGreaterEqual(payload["readiness"]["simcReadyCount"], 2)

    def test_websim_gear_payload_dedupes_repeated_preset_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            first_profile = "\n".join(
                [
                    'mage="Preset_Mage_Frostfire"',
                    "spec=arcane",
                    "head=voidbreakers_veil,id=250060,ilevel=289,bonus_id=1808/13575,gem_id=240983",
                ]
            )
            second_profile = "\n".join(
                [
                    'mage="Preset_Mage_Spellslinger"',
                    "spec=arcane",
                    "head=voidbreakers_veil,id=250060,ilevel=289,bonus_id=1808/13575,gem_id=240983",
                ]
            )
            conn.executemany(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'arcane', ?, ?, '{}', 'now')
                """,
                [
                    ("preset-mage-frostfire", "Preset Mage Frostfire", first_profile),
                    ("preset-mage-spellslinger", "Preset Mage Spellslinger", second_profile),
                ],
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        head_candidates = [item for item in head_group["items"] if item["itemId"] == "250060"]
        self.assertEqual(len(head_candidates), 1)

    def test_websim_gear_payload_exposes_inline_simulator_contract(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "head=preset_helm,id=250101,ilevel=289,bonus_id=13534",
                    "trinket1=preset_trinket,id=250202",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-mage-arcane', 'mage', 'arcane', 'Preset Mage', ?, '{}', 'now')
                """,
                (profile,),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        self.assertEqual(payload["gearSchemaRevision"], "websim-gear-simulator-v1")
        self.assertEqual(payload["maxLevel"], 90)
        self.assertTrue(payload["checkedAt"])
        self.assertIn("head", payload["equippedSet"])
        self.assertEqual(payload["equippedSet"]["head"]["itemId"], "250101")
        self.assertEqual(payload["slotReadiness"]["head"]["status"], "verified")
        self.assertEqual(payload["slotReadiness"]["neck"]["status"], "blocked")
        self.assertIn("missing item", payload["slotReadiness"]["neck"]["reason"])
        self.assertTrue(any(group["slot"] == "head" for group in payload["replacementCandidates"]))

    def test_websim_gear_payload_exposes_catalog_sources_variants_and_mods(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Hood",
                    "inventory_type": {"name": "Head"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood"},
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_gear_sources
                (id, item_id, source_type, source_label, instance_id, encounter_id,
                 difficulty_key, season_revision, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "source-250777-heroic",
                    "250777",
                    "raid",
                    "Vault Mage - Arcane Vault",
                    "arcane-vault",
                    "vault-mage",
                    "heroic",
                    "season-test",
                    json.dumps({"recommendationScore": 91}, ensure_ascii=False),
                    "now",
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants
                (id, item_id, slot, variant_key, label, source_type, difficulty_key,
                 item_level, simc_options_json, status, blockers_json, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "variant-250777-heroic-707",
                    "250777",
                    "head",
                    "heroic-707",
                    "Heroic 707",
                    "raid",
                    "heroic",
                    707,
                    json.dumps({"bonus_id": "12345"}, ensure_ascii=False),
                    "verified",
                    "[]",
                    json.dumps({"classKeys": ["mage"], "specKeys": ["arcane", "frost"]}, ensure_ascii=False),
                    "now",
                ),
            )
            conn.executemany(
                """
                INSERT INTO websim_gear_mod_options
                (id, option_type, name, applicable_slots_json, simc_options_json,
                 status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "socket-gem-240983",
                        "socket",
                        "Quick Gem",
                        json.dumps(["head"], ensure_ascii=False),
                        json.dumps({"gem_id": "240983", "gem_ilevel": "707"}, ensure_ascii=False),
                        "verified",
                        "{}",
                        "now",
                    ),
                    (
                        "enchant-8017",
                        "enchant",
                        "Radiant Enchant",
                        json.dumps(["head"], ensure_ascii=False),
                        json.dumps({"enchant_id": "8017"}, ensure_ascii=False),
                        "verified",
                        "{}",
                        "now",
                    ),
                ],
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                {
                    "status": "verified",
                    "itemDatabaseRevision": "items-test-rev",
                    "variantRevision": "variants-test-rev",
                    "checkedAt": "2026-06-19T00:00:00+00:00",
                    "itemCount": 1,
                    "sourceCount": 1,
                    "variantCount": 1,
                    "verifiedCount": 1,
                    "partialCount": 0,
                    "blockedCount": 0,
                    "blockers": [],
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        self.assertEqual(payload["catalogStatus"], "verified")
        self.assertEqual(payload["itemDatabaseRevision"], "items-test-rev")
        self.assertEqual(payload["variantRevision"], "variants-test-rev")
        head_group = next(group for group in payload["slotGroups"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250777")
        self.assertEqual(catalog_item["sources"][0]["label"], "Vault Mage - Arcane Vault")
        self.assertEqual(catalog_item["sources"][0]["sourceType"], "raid")
        self.assertEqual(catalog_item["variants"][0]["key"], "heroic-707")
        self.assertEqual(catalog_item["variants"][0]["itemLevel"], 707)
        self.assertEqual(catalog_item["variants"][0]["simcOptions"]["bonus_id"], "12345")
        self.assertEqual(catalog_item["defaultVariantKey"], "heroic-707")
        self.assertEqual(catalog_item["ilevel"], 707)
        self.assertEqual(catalog_item["bonus_id"], "12345")
        self.assertEqual(catalog_item["recommendationScore"], 91)
        self.assertEqual(catalog_item["compatibility"]["status"], "compatible")
        self.assertEqual(catalog_item["socketOptions"][0]["simcOptions"]["gem_id"], "240983")
        self.assertEqual(catalog_item["enchantOptions"][0]["simcOptions"]["enchant_id"], "8017")

    def test_gear_catalog_sync_loads_server_owned_mod_seed(self):
        os.environ["WOW_WEBSIM_GEAR_MOD_SEED"] = json.dumps(
            [
                {
                    "type": "socket",
                    "name": "Quick Gem",
                    "slots": ["head"],
                    "simcOptions": {"gem_id": "240983", "gem_ilevel": "707"},
                },
                {
                    "type": "enchant",
                    "name": "Radiant Enchant",
                    "slots": ["head"],
                    "simcOptions": {"enchant_id": "8017"},
                },
            ],
            ensure_ascii=False,
        )
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Hood",
                    "inventory_type": {"name": "Head"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood"},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "manual-250777",
                    "itemId": "250777",
                    "sourceType": "raid",
                    "sourceLabel": "Vault Mage - Arcane Vault",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "manual-250777-heroic",
                    "itemId": "250777",
                    "slot": "head",
                    "variantKey": "heroic-707",
                    "label": "Heroic 707",
                    "sourceType": "raid",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        head_group = next(group for group in payload["slotGroups"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250777")
        self.assertEqual(catalog_item["socketOptions"][0]["simcOptions"]["gem_id"], "240983")
        self.assertEqual(catalog_item["enchantOptions"][0]["simcOptions"]["enchant_id"], "8017")
        self.assertEqual(payload["catalogStatus"], "verified")

    def test_websim_gear_payload_smoke_covers_every_class_spec(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            seen = 0
            for class_meta in self.websim_payload.WOW_CLASSES:
                for spec_key in class_meta["specs"]:
                    payload = self.websim_payload.get_websim_gear(conn, class_meta["key"], spec_key)
                    seen += 1
                    self.assertEqual(payload["classKey"], class_meta["key"])
                    self.assertEqual(payload["specKey"], spec_key)
                    self.assertEqual(payload["gearSchemaRevision"], "websim-gear-simulator-v1")
                    self.assertEqual(len(payload["slots"]), len(self.websim_payload.CANONICAL_GEAR_SLOTS))
                    self.assertEqual(len(payload["slotGroups"]), len(self.websim_payload.CANONICAL_GEAR_SLOTS))
                    self.assertIsInstance(payload["equippedSet"], dict)
                    self.assertIsInstance(payload["slotReadiness"], dict)
                    self.assertIn("fullReady", payload["readiness"])
            self.assertEqual(seen, 40)
        finally:
            conn.close()

    def test_parse_simcraft_stat_snapshot_extracts_real_stats_and_ignores_dps(self):
        output = (
            "DPS Ranking:\n"
            "1. WebSim_Arcane 999999 dps\n"
            "STAT SNAPSHOT: Intellect=12345 Stamina=54321 Crit=2345 Haste=3456 "
            "Mastery=4567 Versatility=5678 Armor=6789 WeaponDps=789.5\n"
        )

        snapshot = self.websim_payload.parse_simcraft_stat_snapshot(output)

        self.assertEqual(snapshot["statStatus"], "verified")
        self.assertEqual(snapshot["primary"]["label"], "智力")
        self.assertEqual(snapshot["primary"]["value"], "12345")
        self.assertEqual(snapshot["stamina"]["value"], "54321")
        self.assertEqual(snapshot["secondary"][0]["key"], "crit")
        self.assertEqual(snapshot["secondary"][0]["value"], "2345")
        self.assertEqual(snapshot["weaponDps"]["value"], "789.5")
        self.assertNotIn("999999", json.dumps(snapshot, ensure_ascii=False))

    def test_parse_simcraft_stat_snapshot_blocks_when_stats_are_missing(self):
        snapshot = self.websim_payload.parse_simcraft_stat_snapshot(
            "Generating Baseline: 50/100\nDPS Ranking:\n1. WebSim_Arcane 999999 dps\n"
        )

        self.assertEqual(snapshot["statStatus"], "blocked")
        self.assertIn("SimC output did not include a parseable stat snapshot", snapshot["blockers"])

    def test_normalized_websim_level_clamps_to_supported_range(self):
        os.environ["WOW_WEBSIM_MAX_LEVEL"] = "90"

        self.assertEqual(self.websim_payload.normalized_websim_level("-5"), 1)
        self.assertEqual(self.websim_payload.normalized_websim_level("999"), 90)
        self.assertEqual(self.websim_payload.normalized_websim_level("bad"), 90)

    def test_parse_simcraft_stat_snapshot_selects_highest_positive_primary_stat(self):
        output = (
            "STAT SNAPSHOT: Intellect=0 Strength=43210 Agility=12 Stamina=54321 "
            "Crit=2345 Haste=3456 Mastery=4567 Versatility=5678\n"
        )

        snapshot = self.websim_payload.parse_simcraft_stat_snapshot(output)

        self.assertEqual(snapshot["statStatus"], "verified")
        self.assertEqual(snapshot["primary"]["key"], "strength")
        self.assertEqual(snapshot["primary"]["value"], "43210")

    def test_websim_gear_payload_enriches_preset_items_with_localized_metadata(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250111",
                {
                    "id": 250111,
                    "name": "预设护腕",
                    "inventory_type": {"name": "Wrist"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-250111.jpg"}]},
                fallback_name="Preset Bracers",
                english_payload={"name": "Preset Bracers"},
                locale="zh_CN",
            )
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "wrist=preset_bracers,id=250111,ilevel=289,bonus_id=13534",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-mage-arcane', 'mage', 'arcane', 'Preset Mage', ?, '{}', 'now')
                """,
                (profile,),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        wrist_item = payload["baselineSet"][0]
        self.assertEqual(wrist_item["displayName"], "预设护腕")
        self.assertEqual(wrist_item["iconUrl"], "https://render.example/item-250111.jpg")
        self.assertEqual(wrist_item["metadataStatus"], "verified")
        self.assertEqual(wrist_item["name"], "preset_bracers")

    def test_build_gear_payload_enriches_rows_by_item_alias(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250060",
                {
                    "id": 250060,
                    "name": "虚空破坏者的面纱",
                    "inventory_type": {"name": "Head"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-250060.jpg"}]},
                fallback_name="Voidbreaker's Veil",
                english_payload={"name": "Voidbreaker's Veil"},
                locale="zh_CN",
            )
            conn.commit()
            payload = {
                "details": {
                    "gear": {
                        "gear": [
                            {
                                "slot": "头部",
                                "name": "Voidbreaker's Veil",
                                "source": "Archon gear overview",
                            },
                            {
                                "slot": "武器/饰品",
                                "name": "奥术法师 Archon 武器与饰品表",
                                "source": "Archon weapons and trinkets table",
                                "isReference": True,
                                "metadataStatus": "source_reference",
                            }
                        ]
                    }
                }
            }
            enriched = self.websim_payload.enrich_build_gear_payload(conn, payload)
        finally:
            conn.close()

        row = enriched["details"]["gear"]["gear"][0]
        self.assertEqual(row["itemId"], "250060")
        self.assertEqual(row["displayName"], "虚空破坏者的面纱")
        self.assertEqual(row["iconUrl"], "https://render.example/item-250060.jpg")
        self.assertEqual(row["metadataStatus"], "verified")
        reference_row = enriched["details"]["gear"]["gear"][1]
        self.assertEqual(reference_row["metadataStatus"], "source_reference")
        self.assertEqual(reference_row["displayName"], "奥术法师 Archon 武器与饰品表")
        self.assertEqual(enriched["details"]["gear"]["metadataSummary"]["verifiedCount"], 1)
        self.assertEqual(enriched["details"]["gear"]["metadataSummary"]["itemCount"], 1)
        self.assertEqual(enriched["details"]["gear"]["metadataSummary"]["referenceCount"], 1)

    def test_build_gear_payload_combines_compound_item_rows(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249342",
                {
                    "id": 249342,
                    "name": "上古饥渴之心",
                    "inventory_type": {"name": "Trinket"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-249342.jpg"}]},
                fallback_name="Heart of Ancient Hunger",
                english_payload={"name": "Heart of Ancient Hunger"},
                locale="zh_CN",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249343",
                {
                    "id": 249343,
                    "name": "艾林先知的凝视",
                    "inventory_type": {"name": "Trinket"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-249343.jpg"}]},
                fallback_name="Gaze of the Alnseer",
                english_payload={"name": "Gaze of the Alnseer"},
                locale="zh_CN",
            )
            conn.commit()
            payload = {
                "details": {
                    "gear": {
                        "gear": [
                            {
                                "slot": "饰品",
                                "name": "Heart of Ancient Hunger / Gaze of the Alnseer",
                                "source": "Archon trinket usage",
                            }
                        ]
                    }
                }
            }
            enriched = self.websim_payload.enrich_build_gear_payload(conn, payload)
        finally:
            conn.close()

        row = enriched["details"]["gear"]["gear"][0]
        self.assertEqual(row["displayName"], "上古饥渴之心 / 艾林先知的凝视")
        self.assertEqual(row["englishName"], "Heart of Ancient Hunger / Gaze of the Alnseer")
        self.assertEqual(len(row["relatedItems"]), 2)
        self.assertEqual([item["itemId"] for item in row["relatedItems"]], ["249342", "249343"])

    def test_blizzard_item_search_requires_exact_english_name(self):
        captured = []

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            captured.append({"path": path, "locale": locale, "params": params, "namespace": namespace})
            return {
                "results": [
                    {"data": {"id": 537, "name": {"en_US": "Dull Frenzy Scale"}}},
                    {"data": {"id": 249317, "name": {"en_US": "Frenzy's Rebuke"}}},
                ]
            }

        original = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original)
        self.websim_payload.blizzard_get = fake_blizzard_get

        item_id = self.websim_payload.search_blizzard_item_id_by_english_name("token", "Frenzy's Rebuke", "us")

        self.assertEqual(item_id, "249317")
        self.assertEqual(captured[0]["path"], "/data/wow/search/item")
        self.assertEqual(captured[0]["locale"], "en_US")
        self.assertEqual(captured[0]["params"]["name.en_US"], "Frenzy's Rebuke")

    def test_sync_blizzard_build_gear_item_metadata_resolves_build_names(self):
        conn = sqlite3.connect(self.db_path)
        original_refs = self.websim_payload.load_build_gear_item_refs
        original_search = self.websim_payload.search_blizzard_item_id_by_english_name
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "load_build_gear_item_refs", original_refs)
        self.addCleanup(setattr, self.websim_payload, "search_blizzard_item_id_by_english_name", original_search)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        self.websim_payload.load_build_gear_item_refs = lambda: [
            {
                "slot": "头部",
                "name": "Frenzy's Rebuke",
                "source": "Archon gear overview",
            },
            {
                "slot": "制作",
                "name": "增辉唤魔师 制造与低保优先级",
                "source": "Wowhead gearing guide",
                "isReference": True,
            },
        ]
        self.websim_payload.search_blizzard_item_id_by_english_name = lambda token, name, region="us": "249317"

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            return {
                "itemId": item_id,
                "payload": {
                    "id": int(item_id),
                    "name": "狂热斥责",
                    "inventory_type": {"name": "Head"},
                    "quality": {"name": "史诗"},
                },
                "media": {"assets": [{"value": "https://render.example/item-249317.jpg"}]},
                "englishPayload": {"name": "Frenzy's Rebuke"},
                "locale": locale,
                "fallbackName": fallback_name,
                "fallbackSlot": fallback_slot,
            }

        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_build_gear_item_metadata(conn, "token", "us", "zh_CN")
            conn.commit()
            payload = {
                "details": {
                    "gear": {
                        "gear": [
                            {"slot": "头部", "name": "Frenzy's Rebuke", "source": "Archon gear overview"}
                        ]
                    }
                }
            }
            enriched = self.websim_payload.enrich_build_gear_payload(conn, payload)
        finally:
            conn.close()

        self.assertEqual(counts["searched"], 1)
        self.assertEqual(counts["resolved"], 1)
        self.assertEqual(counts["items"], 1)
        self.assertEqual(counts["references"], 1)
        row = enriched["details"]["gear"]["gear"][0]
        self.assertEqual(row["itemId"], "249317")
        self.assertEqual(row["displayName"], "狂热斥责")
        self.assertEqual(row["iconUrl"], "https://render.example/item-249317.jpg")

    def test_websim_simulate_request_uses_canonical_websim_profile(self):
        request = self.websim_payload.build_websim_simulator_request(
            {
                "classKey": "mage",
                "specKey": "arcane",
                "talents": "C4DA",
                "scenarioKey": "single",
                "gearSelection": {
                    "items": self.full_core_simc_gear_items()
                },
            },
            guest_id="guest-1",
        )

        self.assertEqual(request["mode"], "simcraft_agent")
        self.assertEqual(request["profileSource"], "websim")
        self.assertIn("profile", request)
        self.assertIn("level=90", request["profile"])
        self.assertIn("talents=C4DA", request["profile"])
        gear = request["buildContext"]["details"]["gear"]
        self.assertTrue(gear["readiness"]["fullReady"])
        self.assertEqual(len(gear["simcItems"]), 15)
        self.assertEqual(gear["simcItems"][0]["slot"], "head")
        self.assertEqual(len(gear["gear"]), 15)

    def test_encode_websim_talents_writes_tree_specific_lines(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
            payload = self.websim_encoder_payload()
            profile_response = self.websim_payload.build_websim_profile_response(payload, conn=conn)
        finally:
            conn.close()

        profile = profile_response["profile"]
        self.assertEqual(profile_response["talentEncoding"]["status"], "encoded")
        self.assertIn("class_talents=1001:1", profile)
        self.assertIn("spec_talents=2001:1", profile)
        self.assertIn("hero_talents=3001:1", profile)
        self.assertNotIn("talents=websim:", profile)
        self.assertIn("head=verified_head,id=250001,ilevel=289,bonus_id=13534", profile)

    def test_websim_talent_encoding_rejects_invalid_or_fallback_nodes(self):
        conn = sqlite3.connect(self.db_path)
        try:
            fallback = self.websim_payload.encode_websim_talents(
                conn,
                self.websim_encoder_payload({
                    "talentState": {"selectedNodes": [{"id": "fallback-mage-arcane-class-class-core", "rank": 1}]}
                }),
            )
            self.seed_websim_encoder_nodes(conn)
            unknown = self.websim_payload.encode_websim_talents(
                conn,
                self.websim_encoder_payload({
                    "talentState": {"selectedNodes": [{"id": "missing-node", "rank": 1}]}
                }),
            )
            overrank = self.websim_payload.encode_websim_talents(
                conn,
                self.websim_encoder_payload({
                    "talentState": {"selectedNodes": [{"id": "simc-class-1001-mage-arcane", "rank": 2}]}
                }),
            )
            self.insert_websim_talent(conn, "simc-spec-2101-mage-arcane", "spec", 2101, 2, 1, "Choice A", choice_group="choice-a")
            self.insert_websim_talent(conn, "simc-spec-2102-mage-arcane", "spec", 2102, 2, 2, "Choice B", choice_group="choice-a")
            conn.commit()
            choice = self.websim_payload.encode_websim_talents(
                conn,
                self.websim_encoder_payload({
                    "talentState": {
                        "selectedNodes": [
                            {"id": "simc-spec-2101-mage-arcane", "rank": 1},
                            {"id": "simc-spec-2102-mage-arcane", "rank": 1},
                        ]
                    }
                }),
            )
        finally:
            conn.close()

        self.assertEqual(fallback["status"], "failed")
        self.assertIn("fallback", fallback["errors"][0])
        self.assertEqual(unknown["status"], "failed")
        self.assertIn("unknown talent node", unknown["errors"][0])
        self.assertEqual(overrank["status"], "failed")
        self.assertTrue(any("exceeds max rank" in error for error in overrank["errors"]))
        self.assertEqual(choice["status"], "failed")
        self.assertTrue(any("multiple talents selected" in error for error in choice["errors"]))

    def test_websim_talent_encoding_uses_purchased_points_for_gates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.insert_websim_talent(conn, "simc-class-free-mage-arcane", "class", 2301, 1, 1, "Free Starter", granted_rank=1)
            self.insert_websim_talent(conn, "simc-class-spend-a-mage-arcane", "class", 2302, 2, 1, "Purchased A")
            self.insert_websim_talent(conn, "simc-class-spend-b-mage-arcane", "class", 2303, 2, 2, "Purchased B")
            self.insert_websim_talent(conn, "simc-class-gated-mage-arcane", "class", 2304, 3, 1, "Gated", point_requirement=2)
            conn.commit()

            blocked = self.websim_payload.encode_websim_talents(
                conn,
                self.websim_encoder_payload({
                    "talentState": {
                        "selectedNodes": [
                            {"id": "simc-class-free-mage-arcane", "rank": 1},
                            {"id": "simc-class-spend-a-mage-arcane", "rank": 1},
                            {"id": "simc-class-gated-mage-arcane", "rank": 1},
                        ]
                    }
                }),
            )
            encoded = self.websim_payload.encode_websim_talents(
                conn,
                self.websim_encoder_payload({
                    "talentState": {
                        "selectedNodes": [
                            {"id": "simc-class-free-mage-arcane", "rank": 1},
                            {"id": "simc-class-spend-a-mage-arcane", "rank": 1},
                            {"id": "simc-class-spend-b-mage-arcane", "rank": 1},
                            {"id": "simc-class-gated-mage-arcane", "rank": 1},
                        ]
                    }
                }),
            )
        finally:
            conn.close()

        self.assertEqual(blocked["status"], "failed")
        self.assertTrue(any("requires 2" in error for error in blocked["errors"]))
        self.assertEqual(encoded["status"], "encoded")
        self.assertEqual(encoded["selectedCounts"]["class"], 3)
        self.assertIn("class_talents=2302:1/2303:1/2304:1", encoded["lines"])

    def test_raiderio_player_template_requires_parsed_visual_loadout(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.insert_websim_talent(
                conn,
                "simc-class-91001-mage-frost",
                "class",
                91001,
                1,
                1,
                "Frost Class",
                spec_key="frost",
            )
            self.insert_websim_talent(
                conn,
                "simc-spec-91002-mage-frost",
                "spec",
                91002,
                1,
                2,
                "Frost Spec",
                spec_key="frost",
            )
            self.insert_websim_talent(
                conn,
                "simc-hero-91003-mage-frost-frostfire",
                "hero",
                91003,
                1,
                3,
                "Frostfire Hero",
                spec_key="frost",
                hero_key="frostfire",
            )
            parsed = self.websim_payload.validate_community_talent_template(conn, {
                "id": "raiderio-rioone-frost",
                "sourceKey": "raiderio",
                "sourceStatus": "synced",
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "frostfire",
                "scenarioKey": "mythic_plus",
                "sourceName": "Raider.IO",
                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                "playerId": "Rioone",
                "payload": {
                    "raiderio": {
                        "characterName": "Rioone",
                        "realmSlug": "isillien",
                        "loadout": [
                            {"traitId": 91001, "rank": 1},
                            {"traitId": 91002, "rank": 1},
                            {"traitId": 91003, "rank": 1},
                        ],
                    }
                },
            })
            blocked = self.websim_payload.validate_community_talent_template(conn, {
                "id": "raiderio-rioone-unparsed",
                "sourceKey": "raiderio",
                "sourceStatus": "synced",
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "frostfire",
                "scenarioKey": "mythic_plus",
                "sourceName": "Raider.IO",
                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                "playerId": "Rioone",
            })
        finally:
            conn.close()

        expected_name = "-".join([
            "Rioone",
            self.websim_payload.CLASS_LABELS_ZH["mage"],
            self.websim_payload.hero_tree_label("frostfire"),
            self.websim_payload.SPEC_LABELS_ZH["frost"],
            self.websim_payload.scenario_title("mythic_plus"),
        ])
        self.assertEqual(parsed["status"], "verified")
        self.assertEqual(parsed["name"], expected_name)
        self.assertEqual(parsed["playerId"], "Rioone")
        self.assertEqual(parsed["heroLabel"], self.websim_payload.hero_tree_label("frostfire"))
        self.assertTrue(parsed["websimExportCode"].startswith("websim:mage:frost:frostfire:"))
        selected_ids = [node["id"] for node in parsed["talentState"]["selectedNodes"]]
        self.assertIn("simc-class-91001-mage-frost", selected_ids)
        self.assertIn("simc-spec-91002-mage-frost", selected_ids)
        self.assertIn("simc-hero-91003-mage-frost-frostfire", selected_ids)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("errors", blocked["payload"])

    def test_raiderio_player_template_parses_nested_loadout_entries(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.insert_websim_talent(
                conn,
                "simc-class-detox-monk-mistweaver",
                "class",
                124866,
                1,
                1,
                "Improved Detox",
                class_key="monk",
                spec_key="mistweaver",
                class_id=10,
                spec_id=270,
                spell_id=388874,
            )
            self.insert_websim_talent(
                conn,
                "simc-hero-celestial-monk-mistweaver",
                "hero",
                124900,
                1,
                2,
                "Celestial Hero",
                class_key="monk",
                spec_key="mistweaver",
                hero_key="conduit_of_the_celestials",
                class_id=10,
                spec_id=270,
                spell_id=443028,
            )
            parsed = self.websim_payload.validate_community_talent_template(conn, {
                "id": "raiderio-monk-mistweaver-real-shape",
                "sourceKey": "raiderio",
                "sourceStatus": "synced",
                "classKey": "monk",
                "specKey": "mistweaver",
                "heroKey": "master_of_harmony",
                "scenarioKey": "mythic_plus",
                "sourceName": "Raider.IO",
                "rawImportCode": "CEQAAAAAAAAAAAAAAAAAAAAA",
                "playerId": "Riohealer",
                "payload": {
                    "raiderio": {
                        "characterName": "Riohealer",
                        "realmSlug": "isillien",
                        "loadout": [
                            {
                                "node": {
                                    "id": 101089,
                                    "entries": [{
                                        "id": 124866,
                                        "traitDefinitionId": 129704,
                                        "spell": {"id": 388874, "name": "Improved Detox"},
                                    }],
                                },
                                "entryIndex": 0,
                                "rank": 1,
                            },
                            {
                                "node": {
                                    "id": 101400,
                                    "entries": [{
                                        "id": 124900,
                                        "traitDefinitionId": 129900,
                                        "spell": {"id": 443028, "name": "Celestial Hero"},
                                    }],
                                },
                                "entryIndex": 0,
                                "rank": 1,
                            },
                            {
                                "node": {
                                    "id": 101401,
                                    "type": 3,
                                    "entries": [{
                                        "id": 124901,
                                        "traitDefinitionId": 0,
                                        "traitSubTreeId": 25,
                                        "spell": None,
                                    }],
                                },
                                "entryIndex": 0,
                                "rank": 1,
                            },
                        ],
                    }
                },
            })
        finally:
            conn.close()

        self.assertEqual(parsed["status"], "verified")
        self.assertEqual(parsed["heroKey"], "conduit_of_the_celestials")
        self.assertEqual(
            [node["id"] for node in parsed["talentState"]["selectedNodes"]],
            ["simc-class-detox-monk-mistweaver", "simc-hero-celestial-monk-mistweaver"],
        )

    def test_community_talent_fixture_sync_validates_and_returns_current_selection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
            sync = self.websim_payload.sync_community_talent_templates(conn)
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
            other_payload = self.websim_payload.get_websim_talents(conn, "mage", "fire", "sunfury")
        finally:
            conn.close()

        self.assertEqual(sync["sourceStatus"], "partial")
        self.assertEqual(sync["templates"]["verified"], 1)
        self.assertEqual(sync["sources"]["raiderio"]["status"], "missing_credentials")
        self.assertEqual(sync["sources"]["warcraftlogs"]["status"], "missing_credentials")

        templates = payload["communityTemplates"]
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0]["name"], "高层大秘 · 主流AOE")
        self.assertEqual(templates[0]["scenarioKey"], "mythic_plus")
        self.assertEqual(templates[0]["sourceStatus"], "partial")
        self.assertEqual(templates[0]["status"], "verified")
        self.assertEqual(templates[0]["sampleCount"], 3)
        self.assertEqual(templates[0]["maxKeyLevel"], 12)
        self.assertTrue(templates[0]["canApplyVisual"])
        self.assertTrue(templates[0]["canUseInSimc"])
        self.assertEqual(templates[0]["talentState"]["selectedNodes"][0]["id"], "simc-class-1001-mage-arcane")
        self.assertTrue(templates[0]["websimExportCode"].startswith("websim:mage:arcane:spellslinger:"))
        self.assertEqual(payload["communityTemplateSync"]["sourceStatus"], "partial")
        self.assertEqual(payload["communityTemplateSync"]["sources"]["raiderio"]["status"], "missing_credentials")
        self.assertEqual([item["id"] for item in other_payload["communityTemplates"]], [templates[0]["id"]])

    def test_websim_talents_returns_verified_community_templates_by_class_only(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            now = self.websim_payload.utc_now()
            for template in [
                {
                    "id": "mage-arcane-template",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "scenarioKey": "mythic_plus",
                    "name": "Mage Arcane",
                    "flowLabel": "M+",
                    "sourceName": "Fixture",
                    "sourceUrl": "",
                    "talentState": {"selectedNodes": [{"id": "arcane-node", "rank": 1}]},
                    "sampleCount": 2,
                    "maxKeyLevel": 20,
                    "analysisWindow": "fixture",
                    "sourceStatus": "synced",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
                {
                    "id": "mage-fire-template",
                    "classKey": "mage",
                    "specKey": "fire",
                    "heroKey": "sunfury",
                    "scenarioKey": "single",
                    "name": "Mage Fire",
                    "flowLabel": "Single",
                    "sourceName": "Fixture",
                    "sourceUrl": "",
                    "talentState": {"selectedNodes": [{"id": "fire-node", "rank": 1}]},
                    "sampleCount": 1,
                    "maxKeyLevel": 18,
                    "analysisWindow": "fixture",
                    "sourceStatus": "synced",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
                {
                    "id": "warrior-template",
                    "classKey": "warrior",
                    "specKey": "protection",
                    "heroKey": "mountain_thane",
                    "scenarioKey": "mythic_plus",
                    "name": "Warrior Protection",
                    "flowLabel": "M+",
                    "sourceName": "Fixture",
                    "sourceUrl": "",
                    "talentState": {"selectedNodes": [{"id": "warrior-node", "rank": 1}]},
                    "sampleCount": 9,
                    "maxKeyLevel": 25,
                    "analysisWindow": "fixture",
                    "sourceStatus": "synced",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
            ]:
                self.websim_payload.upsert_community_talent_template(conn, template)
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        template_ids = [item["id"] for item in payload["communityTemplates"]]
        self.assertEqual(template_ids, ["mage_arcane_template", "mage_fire_template"])
        self.assertEqual(payload["communityTemplates"][0]["classLabel"], self.websim_payload.CLASS_LABELS_ZH["mage"])
        self.assertEqual(payload["communityTemplates"][1]["specLabel"], self.websim_payload.SPEC_LABELS_ZH["fire"])

    def test_websim_talents_bootstraps_fixture_community_templates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        self.assertEqual(payload["communityTemplateSync"]["sourceStatus"], "partial")
        self.assertEqual(len(payload["communityTemplates"]), 1)
        self.assertEqual(payload["communityTemplates"][0]["name"], "高层大秘 · 主流AOE")

    def test_community_talent_fixture_resolves_current_websim_nodes(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_current_fixture_nodes(conn)
            sync = self.websim_payload.sync_community_talent_templates(conn)
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        self.assertEqual(sync["sourceStatus"], "partial")
        self.assertEqual(sync["templates"]["verified"], 1)
        template = payload["communityTemplates"][0]
        selected_ids = [node["id"] for node in template["talentState"]["selectedNodes"]]
        self.assertIn("simc-class-80180-mage-arcane", selected_ids)
        self.assertIn("simc-spec-126537-mage-arcane", selected_ids)
        self.assertIn("simc-hero-117267-mage-arcane-spellslinger", selected_ids)
        self.assertNotIn("simc-class-1001-mage-arcane", selected_ids)
        self.assertTrue(template["canApplyVisual"])

    def test_community_talent_external_import_without_parsed_state_is_hidden(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
            now = self.websim_payload.utc_now()
            self.websim_payload.upsert_community_talent_template(
                conn,
                {
                    "id": "external-mage-arcane-spellslinger",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "scenarioKey": "mythic_plus",
                    "name": "高层大秘 · 外部导入",
                    "flowLabel": "外部导入",
                    "sourceName": "Warcraft Logs",
                    "sourceUrl": "https://www.warcraftlogs.com/",
                    "rawImportCode": "C4DA",
                    "sampleCount": 50,
                    "maxKeyLevel": 20,
                    "analysisWindow": "fixture",
                    "sourceStatus": "partial",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
            )
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        self.assertNotIn(
            "external_mage_arcane_spellslinger",
            [item["id"] for item in payload["communityTemplates"]],
        )

    def test_http_websim_simulate_runs_encoded_profile_through_fake_simc(self):
        payload = self.websim_encoder_payload()
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
            profile_response = self.websim_payload.build_websim_profile_response(payload, conn=conn)
        finally:
            conn.close()
        simc_bin = Path(self.tmp.name) / "fake-websim-simc"
        captured_profile = Path(self.tmp.name) / "captured-websim-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. WebSim_Arcane 123456 dps\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = Request(
                f"{base}/api/websim/simulate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        executed_profile = captured_profile.read_text(encoding="utf-8")
        self.assertTrue(result["simulation"]["ran"])
        self.assertEqual(result["simulation"]["metrics"]["dps"], "123456")
        self.assertEqual(result["talentEncoding"]["status"], "encoded")
        self.assertEqual(result["request"]["profileSource"], "websim")
        self.assertEqual(result["request"]["profile"], profile_response["profile"])
        self.assertEqual(executed_profile, profile_response["profile"])
        self.assertIn("class_talents=1001:1", executed_profile)
        self.assertIn("spec_talents=2001:1", executed_profile)
        self.assertIn("hero_talents=3001:1", executed_profile)
        self.assertNotIn("talents=websim:", executed_profile)
        self.assertTrue(result.get("taskId"))

    def test_http_websim_simulate_blocks_encoding_failures_without_running_or_saving(self):
        simc_bin = Path(self.tmp.name) / "fake-blocked-websim-simc"
        captured_profile = Path(self.tmp.name) / "blocked-websim-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. Should_Not_Run 999999 dps\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = Request(
                f"{base}/api/websim/simulate",
                data=json.dumps(self.websim_encoder_payload({
                    "talentState": {"selectedNodes": [{"id": "missing-node", "rank": 1}]}
                })).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        conn = sqlite3.connect(self.db_path)
        try:
            task_count = conn.execute("SELECT COUNT(*) FROM simulator_tasks").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["talentEncoding"]["status"], "failed")
        self.assertFalse(result["simulation"]["ran"])
        self.assertFalse(captured_profile.exists())
        self.assertEqual(task_count, 0)

    def test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()
        simc_bin = Path(self.tmp.name) / "fake-gear-stats-simc"
        captured_profile = Path(self.tmp.name) / "captured-gear-stats-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'Player: WebSim_Arcane\\n"
            "STAT SNAPSHOT: Intellect=12345 Stamina=54321 Crit=2345 Haste=3456 Mastery=4567 Versatility=5678 Armor=6789 WeaponDps=789.5\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = Request(
                f"{base}/api/websim/gear/stats",
                data=json.dumps(self.websim_encoder_payload()).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        executed_profile = captured_profile.read_text(encoding="utf-8")
        self.assertEqual(result["statStatus"], "verified")
        self.assertEqual(result["maxLevel"], 90)
        self.assertEqual(result["primary"]["value"], "12345")
        self.assertEqual(result["secondary"][1]["key"], "haste")
        self.assertEqual(result["gearReadiness"]["fullReady"], True)
        self.assertEqual(result["itemLevel"]["value"], "289")
        self.assertEqual(result["gearReadiness"]["itemLevel"]["rawValue"], 289)
        self.assertIn("class_talents=1001:1", executed_profile)
        self.assertIn("calculate_scale_factors=0", executed_profile)

    def test_http_websim_gear_stats_fake_snapshot_smoke_for_core_specs(self):
        specs = [
            ("mage", "frost", "Intellect", "intellect"),
            ("paladin", "retribution", "Strength", "strength"),
            ("shaman", "elemental", "Intellect", "intellect"),
        ]
        for index, (class_key, spec_key, primary_name, primary_key) in enumerate(specs, start=1):
            simc_bin = Path(self.tmp.name) / f"fake-{class_key}-{spec_key}-gear-stats-simc"
            simc_bin.write_text(
                "#!/bin/sh\n"
                "cat >/dev/null\n"
                f"printf 'STAT SNAPSHOT: {primary_name}={index}2345 Stamina=54321 Crit=2345 Haste=3456 Mastery=4567 Versatility=5678 Armor=6789 WeaponDps=789.5\\n'\n",
                encoding="utf-8",
            )
            simc_bin.chmod(0o755)
            os.environ["WOW_SIMC_BIN"] = str(simc_bin)

            result = self.post_backend_json(
                "/api/websim/gear/stats",
                self.websim_encoder_payload({
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": "",
                    "talents": f"{class_key}_{spec_key}_external_import",
                    "talentState": {"selectedNodes": []},
                    "gearSelection": {"items": self.full_core_simc_gear_items()},
                }),
            )

            self.assertEqual(result["statStatus"], "verified")
            self.assertEqual(result["classKey"], class_key)
            self.assertEqual(result["specKey"], spec_key)
            self.assertEqual(result["primary"]["key"], primary_key)
            self.assertEqual(result["gearReadiness"]["fullReady"], True)
            self.assertEqual(result["itemLevel"]["value"], "289")

    def test_http_websim_gear_stats_blocks_without_talent_nodes(self):
        simc_bin = Path(self.tmp.name) / "fake-gear-stats-should-not-run"
        captured_profile = Path(self.tmp.name) / "missing-talent-gear-stats-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'STAT SNAPSHOT: Intellect=1 Stamina=1 Crit=1 Haste=1 Mastery=1 Versatility=1\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)

        result = self.post_backend_json(
            "/api/websim/gear/stats",
            self.websim_encoder_payload({"talentState": {"selectedNodes": []}, "talents": ""}),
        )

        self.assertEqual(result["statStatus"], "blocked")
        self.assertIn("no WebSim talent nodes selected", result["blockers"])
        self.assertEqual(result["itemLevel"]["value"], "289")
        self.assertFalse(captured_profile.exists())

    def test_http_websim_gear_stats_blocks_missing_core_gear_without_running(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()
        simc_bin = Path(self.tmp.name) / "fake-missing-core-gear-stats-simc"
        captured_profile = Path(self.tmp.name) / "missing-core-gear-stats-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'STAT SNAPSHOT: Intellect=1 Stamina=1 Crit=1 Haste=1 Mastery=1 Versatility=1\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        partial_items = [item for item in self.full_core_simc_gear_items() if item["slot"] != "trinket2"]

        result = self.post_backend_json(
            "/api/websim/gear/stats",
            self.websim_encoder_payload({"gearSelection": {"items": partial_items}}),
        )

        self.assertEqual(result["statStatus"], "blocked")
        self.assertFalse(result["gearReadiness"]["fullReady"])
        self.assertTrue(any("Missing core SimC gear slots" in blocker for blocker in result["blockers"]))
        self.assertFalse(captured_profile.exists())

    def test_http_websim_gear_stats_blocks_when_simc_is_unavailable(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()
        os.environ["WOW_SIMC_BIN"] = str(Path(self.tmp.name) / "missing-simc-bin")

        result = self.post_backend_json("/api/websim/gear/stats", self.websim_encoder_payload())

        self.assertEqual(result["statStatus"], "blocked")
        self.assertIn("simcraft binary not found", result["blockers"])

    def test_http_websim_gear_stats_blocks_when_simc_output_cannot_be_parsed(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()
        simc_bin = Path(self.tmp.name) / "fake-unparseable-gear-stats-simc"
        captured_profile = Path(self.tmp.name) / "unparseable-gear-stats-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. WebSim_Arcane 999999 dps\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)

        result = self.post_backend_json("/api/websim/gear/stats", self.websim_encoder_payload())

        self.assertEqual(result["statStatus"], "blocked")
        self.assertIn("SimC output did not include a parseable stat snapshot", result["blockers"])
        self.assertTrue(captured_profile.exists())
        self.assertNotIn("999999", json.dumps(result))

    def test_http_websim_gear_stats_parses_snapshot_after_truncated_summary(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()
        simc_bin = Path(self.tmp.name) / "fake-long-gear-stats-simc"
        captured_profile = Path(self.tmp.name) / "long-gear-stats-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "python3 - <<'PY'\n"
            "print('A' * 4500)\n"
            "print('STAT SNAPSHOT: Intellect=12345 Stamina=54321 Crit=2345 Haste=3456 Mastery=4567 Versatility=5678 Armor=6789 WeaponDps=789.5')\n"
            "PY\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)

        result = self.post_backend_json("/api/websim/gear/stats", self.websim_encoder_payload())

        self.assertEqual(result["statStatus"], "verified")
        self.assertEqual(result["primary"]["value"], "12345")
        self.assertTrue(captured_profile.exists())

    def test_http_websim_simulate_blocks_candidate_gear_without_running_or_saving(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()
        simc_bin = Path(self.tmp.name) / "fake-candidate-gear-websim-simc"
        captured_profile = Path(self.tmp.name) / "candidate-gear-websim-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. Should_Not_Run 999999 dps\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = Request(
                f"{base}/api/websim/simulate",
                data=json.dumps(self.websim_encoder_payload({
                    "gearSelection": {
                        "items": [
                            {
                                "slot": "head",
                                "itemId": 250060,
                                "name": "Voidbreaker's Veil",
                                "sourceType": "verifiedLoot",
                            }
                        ]
                    }
                })).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        conn = sqlite3.connect(self.db_path)
        try:
            task_count = conn.execute("SELECT COUNT(*) FROM simulator_tasks").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["agent"]["status"], "needs_clarification")
        self.assertEqual(result["agent"]["missingSlots"], ["gear"])
        self.assertEqual(result["talentEncoding"]["status"], "encoded")
        self.assertFalse(result["simulation"]["ran"])
        self.assertFalse(captured_profile.exists())
        self.assertEqual(task_count, 0)

    def test_http_talents_api_routes_reuse_authority_rules(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.seed_websim_encoder_nodes(conn)
        finally:
            conn.close()

        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base}/api/talents/tree?class=mage&spec=arcane&hero=spellslinger") as response:
                tree = json.loads(response.read().decode("utf-8"))
            self.assertEqual(tree["talentSchemaRevision"], self.websim_payload.TALENT_SCHEMA_REVISION)
            self.assertEqual(tree["talentAuthority"]["runtimeSource"], "simc")

            validate_request = Request(
                f"{base}/api/talents/validate",
                data=json.dumps({
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "talentState": {
                        "selectedNodes": [
                            {"id": "simc-class-1001-mage-arcane", "rank": 1},
                            {"id": "simc-spec-2001-mage-arcane", "rank": 1},
                            {"id": "simc-hero-3001-mage-arcane-spellslinger", "rank": 1},
                        ]
                    },
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(validate_request) as response:
                validation = json.loads(response.read().decode("utf-8"))
            self.assertEqual(validation["status"], "encoded")
            self.assertEqual(validation["selectedCounts"], {"class": 1, "spec": 1, "hero": 1})

            export_request = Request(
                f"{base}/api/talents/export",
                data=json.dumps({
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "talentState": validation["talentState"],
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(export_request) as response:
                exported = json.loads(response.read().decode("utf-8"))
            self.assertTrue(exported["websimExportCode"].startswith("websim:mage:arcane:spellslinger:"))

            import_request = Request(
                f"{base}/api/talents/import",
                data=json.dumps({"code": exported["websimExportCode"]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(import_request) as response:
                imported = json.loads(response.read().decode("utf-8"))
            self.assertEqual(imported["classKey"], "mage")
            self.assertEqual(imported["specKey"], "arcane")
            self.assertEqual(imported["heroKey"], "spellslinger")
            imported_nodes = sorted(imported["talentState"]["selectedNodes"], key=lambda item: item["id"])
            validated_nodes = sorted(validation["talentState"]["selectedNodes"], key=lambda item: item["id"])
            self.assertEqual(imported_nodes, validated_nodes)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

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

    def test_verified_loot_payload_includes_game_asset(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[
                        {
                            "id": "558",
                            "dungeonId": "558",
                            "instanceId": "1300",
                            "name": "Magisters' Terrace",
                            "shortName": "Magisters' Terrace",
                            "timerSeconds": 2040,
                        }
                    ],
                ),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250222",
                {
                    "name": "裂隙护腕",
                    "inventory_type": {"type": "WRIST", "name": "Wrist"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.worldofwarcraft.com/us/icons/56/inv_bracer_cloth_raidmage_j_01.jpg"}]},
                fallback_name="Rift Bindings",
                fallback_slot="wrist",
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1300', 'Magisters Terrace', 'Dungeon', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES ('9001', '1300', 'Arcane Warden', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    'loot-250222', '1300', '9001', '250222', '裂隙护腕', 'wrist', 'Epic',
                    'https://render.worldofwarcraft.com/us/icons/56/inv_bracer_cloth_raidmage_j_01.jpg',
                    '{}', 'now'
                )
                """
            )
            conn.commit()
            loot = self.websim_payload.get_websim_loot(conn)
        finally:
            conn.close()

        self.assertEqual(len(loot["items"]), 1)
        self.assertEqual(loot["items"][0]["gameAsset"]["entityType"], "item")
        self.assertEqual(loot["items"][0]["gameAsset"]["entityId"], "250222")
        self.assertEqual(loot["items"][0]["gameAsset"]["contextKey"], "websim-loot")
        self.assertEqual(loot["items"][0]["gameAsset"]["iconUrl"], loot["items"][0]["iconUrl"])
        self.assertIn("loot", loot["items"][0]["gameAsset"]["semanticTags"])

    def test_sync_blizzard_journal_includes_current_expansion_raid_loot(self):
        conn = sqlite3.connect(self.db_path)
        original_resolve = self.websim_payload.resolve_current_mythic_season
        original_selected_refs = self.websim_payload.selected_journal_instance_refs
        original_blizzard_get = self.websim_payload.blizzard_get
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "resolve_current_mythic_season", original_resolve)
        self.addCleanup(setattr, self.websim_payload, "selected_journal_instance_refs", original_selected_refs)
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        self.websim_payload.resolve_current_mythic_season = lambda token, region="us", locale="zh_CN": self.websim_payload.current_season_payload(
            season_id="17",
            season_label="Fresh Season",
            dungeons=[
                {
                    "id": "558",
                    "dungeonId": "558",
                    "instanceId": "1300",
                    "name": "Magisters' Terrace",
                    "shortName": "Magisters' Terrace",
                    "timerSeconds": 2040,
                }
            ],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": [
            {"id": "1300", "name": "Magisters' Terrace", "category": "Dungeon"},
            {"id": "1400", "name": "Arcane Vault", "category": "Raid"},
        ]

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9001"}, "name": "Arcane Warden"}],
                }
            if path == "/data/wow/journal-instance/1400":
                return {
                    "id": 1400,
                    "name": "Arcane Vault",
                    "category": {"name": "Raid"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9100"}, "name": "Vault Mage"}],
                }
            if path == "/data/wow/journal-encounter/9001":
                return {
                    "id": 9001,
                    "name": "Arcane Warden",
                    "items": [{"item": {"id": 250222, "name": "Rift Bindings"}}],
                }
            if path == "/data/wow/journal-encounter/9100":
                return {
                    "id": 9100,
                    "name": "Vault Mage",
                    "items": [{"item": {"id": 250777, "name": "Catalog Hood"}}],
                }
            return {}

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            slot = "Head" if str(item_id) == "250777" else "Wrist"
            return {
                "payload": {
                    "id": int(item_id),
                    "name": fallback_name or f"Item {item_id}",
                    "inventory_type": {"name": slot},
                    "quality": {"name": "Epic"},
                },
                "media": {"assets": [{"value": f"https://render.example/item-{item_id}.jpg"}]},
                "englishPayload": {"name": fallback_name or f"Item {item_id}"},
                "locale": locale,
                "fallbackName": fallback_name,
            }

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            conn.commit()
            instances = conn.execute("SELECT id, category FROM websim_instances ORDER BY id").fetchall()
            sources = conn.execute("SELECT item_id, source_type, source_label FROM websim_gear_sources ORDER BY item_id").fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["instances"], 2)
        self.assertEqual(counts["loot"], 2)
        self.assertEqual(instances, [("1300", "Dungeon"), ("1400", "Raid")])
        self.assertIn(("250777", "raid", "Vault Mage - Arcane Vault"), sources)

    def test_sync_skips_blizzard_when_active_season_cache_is_fresh(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[
                        {
                            "id": "558",
                            "dungeonId": "558",
                            "instanceId": "1300",
                            "name": "Magisters' Terrace",
                            "shortName": "Magisters' Terrace",
                            "timerSeconds": 2040,
                        }
                    ],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["dataStatus"], "verified")
        self.assertEqual(payload["blizzardSkipped"], "fresh-season-cache")
        self.assertEqual(payload["errors"], [])

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

            with urlopen(f"{base}/api/websim/assets") as response:
                assets = json.loads(response.read().decode("utf-8"))
            self.assertEqual(assets["assets"], [])
            self.assertEqual(assets["counts"]["byStatus"], {})

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
            self.assertIn("talentEncoding", profile_payload)
            self.assertIn("spec=arcane", profile_payload["profile"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

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

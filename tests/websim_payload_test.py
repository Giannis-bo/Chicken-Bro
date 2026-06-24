import json
import io
import gc
import os
import sqlite3
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch


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
        os.environ.pop("WOW_WEBSIM_CRAFTED_GEAR_SEED", None)
        for attempt in range(20):
            try:
                self.tmp.cleanup()
                break
            except PermissionError:
                if attempt == 19:
                    raise
                gc.collect()
                time.sleep(0.2)

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

    def get_backend_json(self, path, headers=None):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = Request(f"{base}{path}", headers=headers or {})
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

    def test_sync_simc_generated_data_preserves_profile_simc_json_only_when_profile_matches(self):
        matching_profile = "\n".join(
            [
                'mage="MID1_Mage_Frost_Frostfire"',
                "spec=frost",
                "back=rigid_scale_greatcloak,id=258575,ilevel=289",
            ]
        )
        changed_profile = "\n".join(
            [
                'mage="MID1_Mage_Frost_Frostfire"',
                "spec=frost",
                "back=changed_cloak,id=258576,ilevel=289",
            ]
        )
        original_extract = self.websim_payload.extract_simc_generated_data
        self.addCleanup(setattr, self.websim_payload, "extract_simc_generated_data", original_extract)
        self.websim_payload.extract_simc_generated_data = lambda: {
            "talents": [],
            "presets": [
                {
                    "id": "mage-frost-matching",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "MID1_Mage_Frost_Frostfire",
                    "profile": matching_profile,
                },
                {
                    "id": "mage-frost-changed",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "MID1_Mage_Frost_Frostfire",
                    "profile": changed_profile,
                },
            ],
            "spellDetails": [],
            "source": "test://simc-generated",
            "spellTextSource": "",
            "dependencies": 0,
            "traitEdgeSource": "",
            "build": "test",
            "spellIcons": 0,
        }

        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for preset_id, profile in [
                ("mage-frost-matching", matching_profile),
                ("mage-frost-changed", "old profile text"),
            ]:
                conn.execute(
                    """
                    INSERT INTO websim_profile_presets
                    (id, class_key, spec_key, name, profile, payload_json, updated_at)
                    VALUES (?, 'mage', 'frost', 'MID1_Mage_Frost_Frostfire', ?, ?, 'old')
                    """,
                    (
                        preset_id,
                        profile,
                        json.dumps(
                            {
                                "id": preset_id,
                                "classKey": "mage",
                                "specKey": "frost",
                                "name": "MID1_Mage_Frost_Frostfire",
                                "simcJson": {
                                    "sim": {
                                        "players": [
                                            {
                                                "gear": {
                                                    "back": {
                                                        "id": 258575,
                                                        "ilevel": 289,
                                                        "stamina": 995,
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                },
                                "simcStatCheckedAt": "2026-06-22T00:00:00Z",
                                "simcStatSource": "simulationcraft",
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
            conn.commit()

            counts = self.websim_payload.sync_simc_generated_data(conn)
            rows = conn.execute("SELECT id, payload_json FROM websim_profile_presets").fetchall()
        finally:
            conn.close()

        payloads = {row_id: json.loads(payload_json) for row_id, payload_json in rows}
        self.assertEqual(counts["presets"], 2)
        self.assertIn("simcJson", payloads["mage-frost-matching"])
        self.assertEqual(payloads["mage-frost-matching"]["simcStatSource"], "simulationcraft")
        self.assertEqual(payloads["mage-frost-matching"]["simcStatCheckedAt"], "2026-06-22T00:00:00Z")
        self.assertNotIn("simcJson", payloads["mage-frost-changed"])
        self.assertNotIn("simcStatSource", payloads["mage-frost-changed"])

    def test_backfill_profile_preset_simc_json_updates_missing_payloads_only(self):
        simc_bin = Path(self.tmp.name) / "fake-simc-json"
        simc_bin.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, pathlib, re, sys",
                    "profile = sys.stdin.read()",
                    "match = re.search(r'^json=(.+)$', profile, re.M)",
                    "if not match:",
                    "    print('missing json path', file=sys.stderr)",
                    "    sys.exit(2)",
                    "path = pathlib.Path(match.group(1).strip())",
                    "path.write_text(json.dumps({'sim': {'players': [{'gear': {'back': {'id': 258575, 'ilevel': 289, 'stamina': 995, 'crit_rating': 50}}}]}}))",
                    "print('ok')",
                ]
            ),
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        self.addCleanup(os.environ.pop, "WOW_SIMC_BIN", None)

        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.executemany(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'frost', ?, ?, ?, 'old')
                """,
                [
                    (
                        "mage-frost-missing-json",
                        "MID1_Mage_Frost_Frostfire",
                        "\n".join(
                            [
                                'mage="MID1_Mage_Frost_Frostfire"',
                                "spec=frost",
                                "back=rigid_scale_greatcloak,id=258575,ilevel=289",
                            ]
                        ),
                        "{}",
                    ),
                    (
                        "mage-frost-cached-json",
                        "MID1_Mage_Frost_Frostfire",
                        "\n".join(
                            [
                                'mage="MID1_Mage_Frost_Frostfire"',
                                "spec=frost",
                                "back=cached_cloak,id=258575,ilevel=289",
                            ]
                        ),
                        json.dumps(
                            {
                                "simcJson": {
                                    "sim": {
                                        "players": [
                                            {"gear": {"back": {"id": 258575, "stamina": 111}}}
                                        ]
                                    }
                                }
                            }
                        ),
                    ),
                ],
            )
            conn.commit()

            counts = self.websim_payload.backfill_profile_preset_simc_json(
                conn,
                class_key="mage",
                spec_key="frost",
            )
            rows = conn.execute("SELECT id, payload_json FROM websim_profile_presets").fetchall()
        finally:
            conn.close()

        payloads = {row_id: json.loads(payload_json) for row_id, payload_json in rows}
        self.assertEqual(counts["checked"], 1)
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(counts["errors"], 0)
        self.assertEqual(
            payloads["mage-frost-missing-json"]["simcJson"]["sim"]["players"][0]["gear"]["back"]["stamina"],
            995,
        )
        self.assertEqual(payloads["mage-frost-missing-json"]["simcStatSource"], "simulationcraft")
        self.assertEqual(
            payloads["mage-frost-cached-json"]["simcJson"]["sim"]["players"][0]["gear"]["back"]["stamina"],
            111,
        )

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

    def test_sync_blizzard_spell_details_skips_cached_verified_spell_details(self):
        original_get = self.websim_payload.blizzard_get_localized
        original_limit = os.environ.get("WOW_WEBSIM_SYNC_SPELL_LIMIT")
        self.addCleanup(setattr, self.websim_payload, "blizzard_get_localized", original_get)
        if original_limit is None:
            self.addCleanup(os.environ.pop, "WOW_WEBSIM_SYNC_SPELL_LIMIT", None)
        else:
            self.addCleanup(os.environ.__setitem__, "WOW_WEBSIM_SYNC_SPELL_LIMIT", original_limit)

        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_talents
                (id, class_key, spec_key, tree_id, row_index, col_index, spell_id, name, payload_json, updated_at)
                VALUES ('simc-spec-12345-mage-arcane', 'mage', 'arcane', 'spec:mage:arcane', 1, 1, 12345, 'Cached Spell', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_spell_details
                (id, spell_id, name, description, icon_url, locale, payload_json, updated_at)
                VALUES ('12345', 12345, 'Cached Spell', 'Already verified.', 'https://render.example/spell.jpg', 'zh_CN', '{"source":"blizzard"}', 'now')
                """
            )
            conn.commit()
            os.environ["WOW_WEBSIM_SYNC_SPELL_LIMIT"] = "1"

            def fail_get(*args, **kwargs):
                raise AssertionError("cached spell detail should not be fetched")

            self.websim_payload.blizzard_get_localized = fail_get
            counts = self.websim_payload.sync_blizzard_spell_details(conn, "token", "us", "zh_CN")
        finally:
            conn.close()

        self.assertEqual(counts["spells"], 0)
        self.assertEqual(counts["media"], 0)
        self.assertEqual(counts["skipped"], 1)

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

    def test_item_slot_from_payload_uses_inventory_type_type_for_localized_payload(self):
        cases = [
            ({"inventory_type": {"type": "HEAD", "name": "头部"}}, "head"),
            ({"inventory_type": {"type": "INVTYPE_WRIST", "name": "手腕"}}, "wrist"),
            ({"inventory_type": {"type": "FINGER", "name": "手指"}}, "finger1"),
            ({"inventory_type": {"type": "TRINKET", "name": "饰品"}}, "trinket1"),
            ({"inventory_type": {"type": "WEAPON", "name": "武器"}}, "main_hand"),
            ({"inventory_type": {"type": "MAIN_HAND", "name": "main_hand"}}, "main_hand"),
            ({"inventory_type": {"type": "OFF_HAND", "name": "off_hand"}}, "off_hand"),
            ({"inventory_type": {"type": "SHIELD", "name": "盾牌"}}, "off_hand"),
        ]

        for payload, expected_slot in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.websim_payload.item_slot_from_payload(payload), expected_slot)

    def test_save_websim_item_metadata_uses_english_payload_slot_when_localized_name_is_not_mapped(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            saved = self.websim_payload.save_websim_item_metadata(
                conn,
                "250888",
                {
                    "id": 250888,
                    "name": "裂隙护腕",
                    "inventory_type": {"name": "手腕"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-250888.jpg"}]},
                fallback_name="Rift Bindings",
                english_payload={
                    "id": 250888,
                    "name": "Rift Bindings",
                    "inventory_type": {"name": "Wrist"},
                },
                locale="zh_CN",
            )
            conn.commit()
            row = conn.execute("SELECT slot FROM websim_items WHERE id = '250888'").fetchone()
        finally:
            conn.close()

        self.assertEqual(saved["slot"], "wrist")
        self.assertEqual(row[0], "wrist")

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

    def test_websim_gear_dedupes_preset_candidate_against_observed_catalog_variant(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'shaman="Preset_Shaman"',
                    "spec=elemental",
                    "head=locus_of_the_primal_core,id=249979,ilevel=289,bonus_id=40/1808/12676/12806",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-shaman-elemental', 'shaman', 'elemental', 'Preset Shaman', ?, '{}', 'now')
                """,
                (profile,),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249979",
                {
                    "id": 249979,
                    "name": "原始核心的轨迹头盔",
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 3, "name": "锁甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "智力"}, "value": 18}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-249979.jpg"}]},
                fallback_name="原始核心的轨迹头盔",
                english_payload={"name": "Locus of the Primal Core", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-shaman-elemental-head-249979",
                    "itemId": "249979",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed shaman elemental",
                    "seasonRevision": "season-test",
                    "payload": {
                        "classKeys": ["shaman"],
                        "specKeys": ["elemental"],
                        "observedProfileRefs": [
                            {
                                "characterName": "Mandur",
                                "classKey": "shaman",
                                "specKey": "elemental",
                                "profileUrl": "https://raider.io/characters/eu/hyjal/Mandur",
                            }
                        ],
                    },
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-shaman-elemental-head-249979",
                    "itemId": "249979",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {
                        "bonus_id": "6652/13335/41/13338/13575/12806/13534",
                        "gem_id": "240906",
                        "enchant_id": "8017",
                    },
                    "status": "verified",
                    "payload": {
                        "classKeys": ["shaman"],
                        "specKeys": ["elemental"],
                        "observedProfileRefs": [
                            {
                                "characterName": "Mandur",
                                "classKey": "shaman",
                                "specKey": "elemental",
                                "profileUrl": "https://raider.io/characters/eu/hyjal/Mandur",
                            }
                        ],
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "shaman", "elemental", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        head_candidates = [item for item in head_group["items"] if item["itemId"] == "249979"]
        self.assertEqual(len(head_candidates), 1)
        candidate = head_candidates[0]
        self.assertEqual(candidate["variantSource"], "catalog")
        self.assertEqual(candidate["variantDifficultyKey"], "source_pending")
        self.assertEqual(candidate["variantDifficultyLabel"], "来源待补")
        self.assertEqual(candidate["bonus_id"], "6652/13335/41/13338/13575/12806/13534")
        self.assertEqual(candidate["gem_id"], "240906")
        self.assertEqual(candidate["enchant_id"], "8017")
        self.assertEqual(candidate["statDisplayStatus"], "pending_current_variant")
        self.assertEqual(candidate.get("source"), "来源待补充")
        self.assertTrue(candidate.get("observedProfileRefs"))
        self.assertNotIn("Mandur", json.dumps(candidate, ensure_ascii=False))
        self.assertNotIn("profileUrl", json.dumps(candidate, ensure_ascii=False))
        self.assertTrue(any(variant["sourceType"] == "catalog" for variant in candidate.get("variants") or []))
        self.assertTrue(any(variant["difficultyKey"] == "source_pending" for variant in candidate.get("variants") or []))

    def test_websim_gear_merges_catalog_source_and_verified_stats_into_preset_candidate(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[
                    {"instanceId": "476", "dungeonId": "476", "name": "通天峰"},
                    {"instanceId": "1201", "dungeonId": "1201", "name": "艾杰斯亚学院"},
                ],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "258575",
                {
                    "id": 258575,
                    "name": "刚鳞大氅",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 1, "name": "布甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "智力"}, "value": 9}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-258575.jpg"}]},
                fallback_name="刚鳞大氅",
                english_payload={"name": "Rigid Scale Greatcloak", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-mage-frost', 'mage', 'frost', 'MID1_Mage_Frost_Frostfire', ?, '{}', 'now')
                """,
                (
                    "\n".join(
                        [
                            'mage="MID1_Mage_Frost_Frostfire"',
                            "spec=frost",
                            "back=rigid_scale_greatcloak,id=258575,ilevel=289",
                        ]
                    ),
                ),
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-476:965:258575",
                    "itemId": "258575",
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "instanceId": "476",
                    "encounterId": "965",
                    "difficultyLabel": "大秘境",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-stats-258575-back",
                    "itemId": "258575",
                    "slot": "back",
                    "variantKey": "observed-stats-289",
                    "label": "Observed 289",
                    "sourceType": "dungeon",
                    "difficultyKey": "mythic_plus",
                    "itemLevel": 289,
                    "simcOptions": {},
                    "status": "verified",
                    "payload": {
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [
                            {"key": "intellect", "label": "智力", "value": 124},
                            {"key": "stamina", "label": "耐力", "value": 1768},
                            {"key": "haste_rating", "label": "急速", "value": 55},
                        ],
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        back_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "back")
        candidates = [item for item in back_group["items"] if item["itemId"] == "258575"]
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["sourceType"], "dungeon")
        self.assertEqual(candidate["source"], "兰吉特 - 通天峰")
        self.assertEqual(candidate["sources"][0]["sourceLabel"], "兰吉特 - 通天峰")
        self.assertEqual(candidate["sources"][0]["sourceType"], "dungeon")
        self.assertEqual(candidate["statDisplayStatus"], "verified_variant")
        self.assertEqual(candidate["statSummary"], "智力 124；耐力 1768；急速 55")
        self.assertEqual(candidate["itemStats"][0]["value"], 124)

    def test_websim_gear_catalog_reuses_shared_catalog_rows_across_specs(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[{"instanceId": "476", "dungeonId": "476", "name": "通天峰"}],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "258575",
                {
                    "id": 258575,
                    "name": "刚鳞大氅",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-258575.jpg"}]},
                fallback_name="刚鳞大氅",
                english_payload={"name": "Rigid Scale Greatcloak", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-476:965:258575",
                    "itemId": "258575",
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "instanceId": "476",
                    "encounterId": "965",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-stats-258575-back",
                    "itemId": "258575",
                    "slot": "back",
                    "variantKey": "observed-stats-289",
                    "label": "Observed 289",
                    "sourceType": "dungeon",
                    "difficultyKey": "mythic_plus",
                    "itemLevel": 289,
                    "simcOptions": {},
                    "status": "verified",
                },
            )
            conn.commit()

            source_reads = 0
            original_sources_by_item = self.websim_payload.gear_catalog_sources_by_item

            def counted_sources_by_item(inner_conn):
                nonlocal source_reads
                source_reads += 1
                return original_sources_by_item(inner_conn)

            with patch.object(self.websim_payload, "gear_catalog_sources_by_item", side_effect=counted_sources_by_item):
                first = self.websim_payload.get_websim_gear_catalog_items(conn, "mage", "frost", season)
                second = self.websim_payload.get_websim_gear_catalog_items(conn, "hunter", "marksmanship", season)
        finally:
            conn.close()

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(source_reads, 1)

    def test_websim_gear_keeps_simc_ready_baseline_visible_when_catalog_variant_is_partial(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[{"instanceId": "945", "dungeonId": "945", "name": "执政团之座"}],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "151323",
                {
                    "id": 151323,
                    "name": "虚空猎手肩甲",
                    "inventory_type": {"type": "SHOULDER", "name": "Shoulder"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 3, "name": "锁甲"},
                    "quality": {"name": "史诗"},
                },
                {"assets": [{"value": "https://render.example/item-151323.jpg"}]},
                fallback_name="虚空猎手肩甲",
                english_payload={"name": "Void Hunter's Shoulderguards", "inventory_type": {"name": "Shoulder"}},
                locale="zh_CN",
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-hunter-marksmanship', 'hunter', 'marksmanship', 'MID1_Hunter_Marksmanship', ?, '{}', 'now')
                """,
                (
                    "\n".join(
                        [
                            'hunter="MID1_Hunter_Marksmanship"',
                            "spec=marksmanship",
                            "shoulder=void_hunters_shoulderguards,id=151323,ilevel=289",
                        ]
                    ),
                ),
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-945:1980:151323",
                    "itemId": "151323",
                    "sourceType": "dungeon",
                    "sourceLabel": "萨普瑞什 - 执政团之座",
                    "instanceId": "945",
                    "encounterId": "1980",
                    "difficultyLabel": "大秘境",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-151323-shoulder",
                    "itemId": "151323",
                    "slot": "shoulder",
                    "variantKey": "needs-variant",
                    "label": "难度待补",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs_variant",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            payload = self.websim_payload.get_websim_gear(conn, "hunter", "marksmanship", compact=True)
        finally:
            conn.close()

        shoulder_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "shoulder")
        candidate = next((item for item in shoulder_group["items"] if item["itemId"] == "151323"), None)
        self.assertIsNotNone(candidate)
        self.assertTrue(candidate["simcReady"])
        self.assertEqual(candidate["source"], "萨普瑞什 - 执政团之座")

    def test_websim_gear_orders_current_official_source_candidates_before_observed_only_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[{"instanceId": "476", "dungeonId": "476", "name": "通天峰"}],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            for item_id, name in (("258575", "刚鳞大氅"), ("193712", "药渍披风"), ("239656", "信徒的流丝罩袍")):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "CLOAK", "name": "Back"},
                        "item_class": {"id": 4, "name": "护甲"},
                        "item_subclass": {"id": 1, "name": "布甲"},
                        "quality": {"name": "史诗"},
                    },
                    fallback_name=name,
                    locale="zh_CN",
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-239656",
                    "itemId": "239656",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed deathknight blood",
                    "seasonRevision": season["seasonRevision"],
                    "payload": {"classKeys": ["deathknight"], "specKeys": ["blood"]},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-back-239656",
                    "itemId": "239656",
                    "slot": "back",
                    "variantKey": "observed-285",
                    "label": "Observed 285",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 285,
                    "simcOptions": {"bonus_id": "12214/13667"},
                    "status": "verified",
                    "payload": {"classKeys": ["deathknight"], "specKeys": ["blood"]},
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-476:965:258575",
                    "itemId": "258575",
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "instanceId": "476",
                    "encounterId": "965",
                    "difficultyLabel": "大秘境",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-back-258575",
                    "itemId": "258575",
                    "slot": "back",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/40/13577/12699/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [{"key": "intellect", "label": "智力", "value": 70}],
                        "statSummary": "智力 70",
                    },
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-1201:2512:193712",
                    "itemId": "193712",
                    "sourceType": "dungeon",
                    "sourceLabel": "茂林古树 - 艾杰斯亚学院",
                    "instanceId": "1201",
                    "encounterId": "2512",
                    "difficultyLabel": "大秘境",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-back-193712",
                    "itemId": "193712",
                    "slot": "back",
                    "variantKey": "observed-289-193712",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/41/13577/12699/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [
                            {"key": "intellect", "label": "智力", "value": 70},
                            {"key": "stamina", "label": "耐力", "value": 995},
                            {"key": "leech_rating", "label": "吸血", "value": 40},
                        ],
                        "statSummary": "智力 70；耐力 995；吸血 40",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        back_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "back")
        self.assertEqual(back_group["items"][0]["itemId"], "258575")
        self.assertEqual(back_group["items"][0]["source"], "兰吉特 - 通天峰")
        self.assertEqual(back_group["items"][0]["name"], "刚鳞大氅")
        self.assertEqual(back_group["items"][0]["displayName"], "刚鳞大氅")

    def test_gear_candidate_quality_score_does_not_rank_by_stat_total(self):
        base = {
            "slot": "back",
            "simcReady": True,
            "variantStatus": "verified",
            "sourceType": "catalog",
            "sources": [{"sourceType": "dungeon", "sourceLabel": "当前赛季副本"}],
            "variantSource": "observed_profile",
            "ilevel": 289,
            "bonus_id": "13440/40/13577/12699/12806",
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "metadataStatus": "verified",
        }
        rigid_scale = {
            **base,
            "itemId": "258575",
            "id": "258575",
            "localizedName": "刚鳞大氅",
            "itemStats": [{"key": "intellect", "label": "智力", "value": 70}],
        }
        stained = {
            **base,
            "itemId": "193712",
            "id": "193712",
            "localizedName": "药渍披风",
            "itemStats": [
                {"key": "intellect", "label": "智力", "value": 70},
                {"key": "stamina", "label": "耐力", "value": 995},
                {"key": "leech_rating", "label": "吸血", "value": 40},
            ],
        }

        self.assertGreater(
            self.websim_payload.gear_candidate_quality_score(rigid_scale),
            self.websim_payload.gear_candidate_quality_score(stained),
        )

    def test_gear_candidate_quality_score_prefers_sourced_verified_stat_candidates(self):
        missing_source_observed = {
            "slot": "feet",
            "itemId": "249981",
            "id": "249981",
            "name": "Observed Source Gap Boots",
            "sourceType": "catalog",
            "variantSource": "observed_profile",
            "variantStatus": "verified",
            "ilevel": 707,
            "bonus_id": "12345",
            "simcReady": True,
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "itemStats": [{"key": "agility", "label": "Agility", "value": 111}],
            "observedProfileRefs": [{"classKey": "shaman", "specKey": "enhancement", "itemId": "249981"}],
        }
        sourced_candidate = {
            "slot": "feet",
            "itemId": "251084",
            "id": "251084",
            "name": "Dungeon Source Boots",
            "sourceType": "simcPreset",
            "sources": [{"sourceType": "dungeon", "sourceLabel": "被遗弃的二人组 - 风行者之塔"}],
            "variantStatus": "partial",
            "variantSource": "dungeon",
            "ilevel": 707,
            "bonus_id": "12345",
            "simcReady": True,
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "itemStats": [{"key": "agility", "label": "Agility", "value": 111}],
        }

        ranked = sorted(
            [missing_source_observed, sourced_candidate],
            key=self.websim_payload.gear_candidate_quality_score,
            reverse=True,
        )

        self.assertEqual(ranked[0]["itemId"], "251084")

    def test_gear_candidate_quality_score_prefers_observed_evidence_over_source_pending_ilevel(self):
        source_pending_higher_ilevel = {
            "slot": "feet",
            "itemId": "249999",
            "id": "249999",
            "name": "黑爪龙人的法术踏靴",
            "sourceType": "catalog",
            "variantStatus": "verified",
            "ilevel": 298,
            "bonus_id": "13440/6652/13577/12699/12806",
            "simcReady": True,
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "itemStats": [{"key": "agiint", "label": "敏捷 or 智力", "value": 128}],
        }
        observed_evidence_lower_ilevel = {
            "slot": "feet",
            "itemId": "249377",
            "id": "249377",
            "name": "涉暗踏靴",
            "sourceType": "catalog",
            "variantSource": "observed_profile",
            "variantStatus": "verified",
            "ilevel": 289,
            "bonus_id": "13440/6652/13577/12699/12806",
            "simcReady": True,
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "itemStats": [{"key": "agiint", "label": "敏捷 or 智力", "value": 124}],
            "observedProfileRefs": [{"sourceName": "Raider.IO", "classKey": "evoker", "specKey": "augmentation"}],
        }

        ranked = sorted(
            [source_pending_higher_ilevel, observed_evidence_lower_ilevel],
            key=self.websim_payload.gear_candidate_quality_score,
            reverse=True,
        )

        self.assertEqual(ranked[0]["itemId"], "249377")

    def test_websim_gear_hides_partial_official_catalog_candidate_from_replacement_panel(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["raids"] = [{"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"}]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250104",
                {
                    "id": 250104,
                    "name": "缚魂者的虚空披风",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 1, "name": "布甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "智力"}, "value": 9}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250104.jpg"}]},
                fallback_name="缚魂者的虚空披风",
                english_payload={"name": "Soulbinder's Void Cloak", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-1302:2685:250104",
                    "itemId": "250104",
                    "sourceType": "raid",
                    "sourceLabel": "Voidbinder - The Voidspire",
                    "instanceId": "1400",
                    "encounterId": "2685",
                    "difficultyLabel": "团本",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-250104-back",
                    "itemId": "250104",
                    "slot": "back",
                    "sourceType": "raid",
                    "difficultyKey": "needs-variant",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        back_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "back")
        item_ids = {item["itemId"] for item in back_group["items"]}
        self.assertNotIn("250104", item_ids)

    def test_websim_gear_shows_source_only_fallback_for_empty_current_season_slot(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["raids"] = [{"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"}]
            self.websim_payload.save_active_season_payload(conn, season)
            for item_id, name, instance_id in (
                ("250888", "当前赛季候选头盔", "1400"),
                ("250889", "旧赛季候选头盔", "9999"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "HEAD", "name": "Head"},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 3, "name": "Mail"},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 99}],
                        },
                    },
                    {"assets": [{"value": f"https://render.example/item-{item_id}.jpg"}]},
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Head"}},
                    locale="zh_CN",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"loot-{instance_id}:2685:{item_id}",
                        "itemId": item_id,
                        "sourceType": "raid",
                        "sourceLabel": f"Boss {instance_id} - Test Raid",
                        "instanceId": instance_id,
                        "encounterId": "2685",
                        "difficultyLabel": "团本",
                        "seasonRevision": season["seasonRevision"] if instance_id == "1302" else "old-season",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"loot-partial-{item_id}-head",
                        "itemId": item_id,
                        "slot": "head",
                        "sourceType": "raid",
                        "difficultyKey": "needs-variant",
                        "status": "partial",
                        "blockers": ["missing deterministic SimC variant preset"],
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            payload = self.websim_payload.get_websim_gear(conn, "evoker", "preservation", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = {item["itemId"] for item in head_group["items"]}
        self.assertIn("250888", item_ids)
        self.assertNotIn("250889", item_ids)
        fallback = next(item for item in head_group["items"] if item["itemId"] == "250888")
        self.assertFalse(fallback["simcReady"])
        self.assertTrue(fallback["replacementFallback"])
        self.assertEqual(fallback["fallbackReason"], "source_only_current_season")
        self.assertEqual(fallback["statDisplayStatus"], "pending_current_variant")
        self.assertNotIn("itemStats", fallback)
        self.assertNotIn("statSummary", fallback)
        self.assertIn("missing deterministic SimC variant preset", fallback["blockers"])
        self.assertEqual(fallback["sources"][0]["sourceType"], "raid")

    def test_websim_gear_allows_observed_catalog_candidate_to_replace_preset_before_compact_limit(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[{"instanceId": "1300", "dungeonId": "1300", "name": "Magisters Terrace"}],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            profile_lines = [
                'shaman="Preset_Shaman"',
                "spec=elemental",
                "head=locus_of_the_primal_core,id=249979,ilevel=289,bonus_id=40/1808/12676/12806",
            ]
            for index in range(24):
                profile_lines.append(f"head=filler_{index},id={260000 + index},ilevel=289,bonus_id=40/12806")
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-shaman-elemental', 'shaman', 'elemental', 'Preset Shaman', ?, '{}', 'now')
                """,
                ("\n".join(profile_lines),),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249979",
                {
                    "id": 249979,
                    "name": "原始核心的轨迹头盔",
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 3, "name": "锁甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "智力"}, "value": 18}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-249979.jpg"}]},
                fallback_name="原始核心的轨迹头盔",
                english_payload={"name": "Locus of the Primal Core", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-1300:9001:249979",
                    "itemId": "249979",
                    "sourceType": "dungeon",
                    "sourceLabel": "Arcane Warden - Magisters Terrace",
                    "instanceId": "1300",
                    "encounterId": "9001",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-shaman-elemental-head-249979",
                    "itemId": "249979",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed shaman elemental",
                    "seasonRevision": "season-test",
                    "payload": {"classKeys": ["shaman"], "specKeys": ["elemental"]},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-shaman-elemental-head-249979",
                    "itemId": "249979",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {
                        "bonus_id": "6652/13335/41/13338/13575/12806/13534",
                        "gem_id": "240906",
                    },
                    "status": "verified",
                    "payload": {"classKeys": ["shaman"], "specKeys": ["elemental"]},
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "shaman", "elemental", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        candidate = next(item for item in head_group["items"] if item["itemId"] == "249979")
        self.assertEqual(candidate.get("source"), "Arcane Warden - Magisters Terrace")
        self.assertEqual(candidate.get("sourceType"), "dungeon")
        self.assertEqual(candidate.get("variantSource"), "dungeon")
        self.assertEqual(candidate.get("variantDifficultyKey"), "dungeon")
        self.assertEqual(candidate.get("variantDifficultyLabel"), "大秘境")
        self.assertEqual(candidate["bonus_id"], "6652/13335/41/13338/13575/12806/13534")

    def test_websim_gear_payload_dedupes_same_community_template_and_merges_sources(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "head=voidbreakers_veil,id=250060,ilevel=289,bonus_id=1808/13575,gem_id=240983",
                ]
            )
            conn.executemany(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'arcane', ?, ?, '{}', ?)
                """,
                [
                    ("preset-mage-a", "Preset Mage A", profile, "2026-06-20T00:00:00Z"),
                    ("preset-mage-b", "Preset Mage B", profile, "2026-06-20T01:00:00Z"),
                ],
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        self.assertEqual(len(payload["communityTemplates"]), 1)
        template = payload["communityTemplates"][0]
        self.assertTrue(template["signature"].startswith("gear:mage:arcane:"))
        self.assertEqual(template["dedupedCount"], 2)
        self.assertEqual(len(template["sourceRefs"]), 2)
        self.assertEqual(
            [ref["id"] for ref in template["sourceRefs"]],
            ["preset-mage-a", "preset-mage-b"],
        )
        self.assertEqual(payload["communityTemplateSync"]["dedupedCount"], 1)
        self.assertEqual(payload["communityTemplateSync"]["hiddenDuplicateCount"], 1)

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

    def test_websim_gear_fills_missing_baseline_slots_from_simc_ready_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters Terrace"}],
                ),
            )
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "wrist=preset_bracers,id=260001,ilevel=289,bonus_id=13534",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-mage-arcane', 'mage', 'arcane', 'Partial Preset', ?, '{}', 'now')
                """,
                (profile,),
            )

            inventory_by_slot = {
                "head": "HEAD",
                "neck": "NECK",
                "shoulder": "SHOULDER",
                "back": "CLOAK",
                "chest": "CHEST",
                "wrist": "WRIST",
                "hands": "HANDS",
                "waist": "WAIST",
                "legs": "LEGS",
                "feet": "FEET",
                "finger1": "FINGER",
                "finger2": "FINGER",
                "trinket1": "TRINKET",
                "trinket2": "TRINKET",
                "main_hand": "WEAPON",
            }
            for index, slot in enumerate(self.websim_payload.CORE_SIMC_GEAR_SLOTS, start=1):
                if slot == "wrist":
                    continue
                item_id = str(261000 + index)
                inventory_type = inventory_by_slot[slot]
                item_class = {"id": 2, "name": "Weapon"} if slot == "main_hand" else {"id": 4, "name": "Armor"}
                item_subclass = (
                    {"id": 15, "name": "Dagger"}
                    if slot == "main_hand"
                    else {"id": 1, "name": "Cloth"}
                )
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": f"Candidate {slot}",
                        "inventory_type": {"type": inventory_type, "name": inventory_type},
                        "item_class": item_class,
                        "item_subclass": item_subclass,
                        "quality": {"name": "Epic"},
                    },
                    fallback_slot=slot,
                    fallback_name=f"Candidate {slot}",
                    english_payload={"name": f"Candidate {slot}", "inventory_type": {"name": inventory_type}},
                    locale="en_US",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "dungeon",
                        "sourceLabel": "Arcane Warden - Magisters Terrace",
                        "instanceId": "1300",
                        "seasonRevision": "season-17-test",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}-{slot}",
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": f"observed-289-{slot}",
                        "label": "Observed 289",
                        "sourceType": "dungeon",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "13534"},
                        "status": "verified",
                        "payload": {
                            "statDisplayStatus": "verified_variant",
                            "statSource": "simulationcraft",
                            "itemStats": [{"key": "intellect", "label": "Intellect", "value": 111}],
                        },
                    },
                )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane", compact=True)
        finally:
            conn.close()

        self.assertEqual(payload["equippedSet"]["wrist"]["itemId"], "260001")
        self.assertIn("head", payload["equippedSet"])
        self.assertEqual(payload["equippedSet"]["head"]["itemId"], "261001")
        self.assertEqual(payload["equippedSet"]["finger2"]["slot"], "finger2")
        self.assertEqual(payload["readiness"]["missingCoreSlots"], [])
        self.assertTrue(payload["readiness"]["fullReady"])

    def test_websim_gear_equipped_set_inherits_catalog_source_refs(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "151332",
                {
                    "id": 151332,
                    "name": "灵爪手甲",
                    "inventory_type": {"type": "HANDS", "name": "Hands"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 4, "name": "Plate"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/item-151332.jpg"}]},
                fallback_name="Lingering Talon Gauntlets",
                english_payload={"name": "Lingering Talon Gauntlets", "inventory_type": {"name": "Hands"}},
                locale="zh_CN",
            )
            conn.execute(
                """
                INSERT INTO websim_gear_sources
                (id, item_id, source_type, source_label, instance_id, encounter_id,
                 difficulty_key, season_revision, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "source-151332-dungeon",
                    "151332",
                    "dungeon",
                    "总督奈扎尔 - 执政团之座",
                    "seat-of-the-triumvirate",
                    "viceroy-nezhar",
                    "",
                    "",
                    "{}",
                    "now",
                ),
            )
            profile = "\n".join(
                [
                    'deathknight="Preset_DK"',
                    "spec=blood",
                    "hands=lingering_talon_gauntlets,id=151332,ilevel=289,bonus_id=13534",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-dk-blood', 'deathknight', 'blood', 'Preset DK', ?, '{}', 'now')
                """,
                (profile,),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "deathknight", "blood", compact=True)
        finally:
            conn.close()

        hands = payload["equippedSet"]["hands"]
        self.assertEqual(hands["itemId"], "151332")
        self.assertEqual(hands["source"], "总督奈扎尔 - 执政团之座")

    def test_websim_gear_compact_payload_omits_duplicate_and_heavy_fields(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "head=preset_helm,id=250101,ilevel=289,bonus_id=13534",
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
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane", compact=True)
        finally:
            conn.close()

        self.assertIn("replacementCandidates", payload)
        self.assertNotIn("slotGroups", payload)
        self.assertNotIn("catalogItems", payload)

    def test_websim_gear_compact_payload_prunes_raw_candidate_payloads(self):
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
                            "id": "239",
                            "dungeonId": "239",
                            "instanceId": "945",
                            "name": "Catalog Dungeon",
                            "shortName": "Catalog Dungeon",
                            "timerSeconds": 1800,
                            "payload": {"rawDebugPayload": "x" * 4096},
                        }
                    ],
                ),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 1234}],
                        "rawDebugPayload": {"text": "x" * 4096},
                    },
                    "rawDebugPayload": {"text": "x" * 4096},
                },
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250777",
                    "itemId": "250777",
                    "sourceType": "dungeon",
                    "sourceLabel": "Catalog Dungeon",
                    "payload": {"rawDebugPayload": "x" * 4096},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250777",
                    "itemId": "250777",
                    "slot": "head",
                    "variantKey": "heroic-707",
                    "label": "Heroic 707",
                    "sourceType": "dungeon",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "rawDebugPayload": "x" * 4096,
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "itemStats": [{"key": "intellect", "label": "智力", "value": 1234}],
                        "statSummary": "智力 1234",
                    },
                },
            )
            self.websim_payload.upsert_community_gear_template(
                conn,
                {
                    "id": "community-gear-250777",
                    "classKey": "mage",
                    "specKey": "frost",
                    "name": "Community Gear",
                    "status": "partial",
                    "gearItems": [
                        {
                            "slot": "head",
                            "simcSlot": "head",
                            "itemId": "250777",
                            "id": "250777",
                            "name": "catalog_hood",
                            "displayName": "Catalog Hood",
                            "sourceType": "observed_profile",
                            "ilevel": 707,
                            "bonus_id": "12345",
                            "payload": {"rawDebugPayload": "x" * 4096},
                        }
                    ],
                    "payload": {"rawDebugPayload": "x" * 4096},
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250777")
        self.assertNotIn("payload", catalog_item)
        self.assertFalse(any("payload" in source for source in catalog_item.get("sources", [])))
        self.assertFalse(any("payload" in variant for variant in catalog_item.get("variants", [])))
        self.assertIn("statSummary", catalog_item)
        self.assertEqual(catalog_item["variants"][0]["simcOptions"]["bonus_id"], "12345")
        community_template = next(
            template for template in payload["communityTemplates"] if template["id"] == "community_gear_250777"
        )
        self.assertNotIn("payload", community_template)
        self.assertFalse(any("payload" in item for item in community_template.get("gearItems", [])))
        self.assertNotIn("payload", payload["currentSeason"]["dungeons"][0])
        self.assertNotIn('"payload"', json.dumps(payload, ensure_ascii=False))

    def test_http_websim_gear_miniprogram_header_uses_compact_payload(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "head=preset_helm,id=250101,ilevel=289,bonus_id=13534",
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
        finally:
            conn.close()

        payload = self.get_backend_json(
            "/api/websim/gear?class=mage&spec=arcane",
            headers={"X-Wow-Platform": "miniprogram"},
        )

        self.assertIn("replacementCandidates", payload)
        self.assertNotIn("slotGroups", payload)
        self.assertNotIn("catalogItems", payload)
        self.assertNotIn("candidateItems", payload)
        self.assertNotIn("presets", payload)
        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        self.assertTrue(any(item["itemId"] == "250101" for item in head_group["items"]))

    def test_http_websim_gear_compact_query_uses_compact_payload(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "head=preset_helm,id=250101,ilevel=289,bonus_id=13534",
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
        finally:
            conn.close()

        payload = self.get_backend_json("/api/websim/gear?class=mage&spec=arcane&compact=1")

        self.assertIn("replacementCandidates", payload)
        self.assertNotIn("slotGroups", payload)
        self.assertNotIn("catalogItems", payload)

    def test_websim_gear_payload_exposes_importable_community_templates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            profile = "\n".join(
                [
                    'mage="Preset_Mage"',
                    "spec=arcane",
                    "head=preset_helm,id=250101,ilevel=289,bonus_id=13534",
                    "neck=display_only_neck",
                ]
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('preset-mage-arcane', 'mage', 'arcane', 'Preset Mage', ?, '{}', '2026-06-20T00:00:00Z')
                """,
                (profile,),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        self.assertIn("communityTemplates", payload)
        self.assertIn("communityTemplateSync", payload)
        self.assertEqual(payload["communityTemplateSync"]["sourceStatus"], "partial")
        templates = payload["communityTemplates"]
        self.assertEqual(len(templates), 1)
        template = templates[0]
        self.assertEqual(template["id"], "preset-mage-arcane")
        self.assertEqual(template["name"], "Preset Mage")
        self.assertEqual(template["sourceName"], "SimC preset")
        self.assertEqual(template["sourceStatus"], "partial")
        self.assertEqual(template["status"], "partial")
        self.assertTrue(template["canApplyGear"])
        self.assertEqual(template["readySlotCount"], 1)
        self.assertIn("neck", template["missingSlots"])
        self.assertEqual(template["updatedAt"], "2026-06-20T00:00:00Z")
        self.assertEqual([item["slot"] for item in template["gearItems"]], ["head"])
        self.assertIn("head=", template["rawString"])
        self.assertNotIn("display_only_neck", template["rawString"])

    def test_websim_gear_payload_exposes_catalog_sources_variants_and_mods(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Band",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [
                            {
                                "type": {"type": "INTELLECT", "name": "智力"},
                                "value": 1234,
                                "display": {"display_string": "+1,234 智力"},
                            },
                            {
                                "type": {"type": "HASTE_RATING", "name": "急速"},
                                "value": 567,
                                "display": {"display_string": "+567 急速"},
                            },
                        ],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "棱彩插槽"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Catalog Band",
                english_payload={"name": "Catalog Band", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "240983",
                {
                    "id": 240983,
                    "name": "Quick Gem",
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/gem-240983.jpg"}]},
                fallback_name="Quick Gem",
                english_payload={"name": "Quick Gem"},
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
                    "",
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
                    "finger1",
                    "heroic-707",
                    "Heroic 707",
                    "raid",
                    "heroic",
                    707,
                    json.dumps({"bonus_id": "12345"}, ensure_ascii=False),
                    "verified",
                    "[]",
                    json.dumps(
                        {
                            "classKeys": ["mage"],
                            "specKeys": ["arcane", "frost"],
                            "statDisplayStatus": "verified_variant",
                            "statSource": "simulationcraft",
                            "itemStats": [
                                {"key": "intellect", "label": "智力", "value": 1234},
                                {"key": "haste_rating", "label": "急速", "value": 567},
                            ],
                            "statSummary": "智力 1234；急速 567",
                        },
                        ensure_ascii=False,
                    ),
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
                        json.dumps(["finger1"], ensure_ascii=False),
                        json.dumps({"gem_id": "240983", "gem_ilevel": "707"}, ensure_ascii=False),
                        "verified",
                        json.dumps(
                            {
                                "gemItemId": "240983",
                                "displayName": "Quick Gem",
                                "iconUrl": "https://render.example/gem-240983.jpg",
                                "metadataStatus": "verified",
                                "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                                "metadataLocale": "en_US",
                            },
                            ensure_ascii=False,
                        ),
                        "now",
                    ),
                    (
                        "enchant-8017",
                        "enchant",
                        "Radiant Enchant",
                        json.dumps(["finger1"], ensure_ascii=False),
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
        finger_group = next(group for group in payload["slotGroups"] if group["slot"] == "finger1")
        catalog_item = next(item for item in finger_group["items"] if item["itemId"] == "250777")
        self.assertEqual(catalog_item["sources"][0]["label"], "Vault Mage - Arcane Vault")
        self.assertEqual(catalog_item["sources"][0]["sourceType"], "raid")
        self.assertEqual(catalog_item["sources"][0]["difficultyLabel"], "英雄")
        self.assertEqual(catalog_item["variants"][0]["key"], "heroic-707")
        self.assertEqual(catalog_item["variants"][0]["difficultyLabel"], "英雄")
        self.assertEqual(catalog_item["variants"][0]["itemLevel"], 707)
        self.assertEqual(catalog_item["variants"][0]["simcOptions"]["bonus_id"], "12345")
        self.assertEqual(catalog_item["defaultVariantKey"], "heroic-707")
        self.assertEqual(catalog_item["ilevel"], 707)
        self.assertEqual(catalog_item["bonus_id"], "12345")
        self.assertEqual(catalog_item["recommendationScore"], 91)
        self.assertEqual(catalog_item["compatibility"]["status"], "compatible")
        self.assertEqual(catalog_item["itemStats"][0]["label"], "智力")
        self.assertEqual(catalog_item["itemStats"][0]["value"], 1234)
        self.assertIn("智力 1234", catalog_item["statSummary"])
        self.assertIn("急速 567", catalog_item["statSummary"])
        self.assertTrue(catalog_item["modCapabilities"]["hasSocket"])
        self.assertTrue(catalog_item["modCapabilities"]["canEnchant"])
        self.assertEqual(catalog_item["socketOptions"][0]["simcOptions"]["gem_id"], "240983")
        self.assertEqual(catalog_item["enchantOptions"][0]["simcOptions"]["enchant_id"], "8017")

    def test_compact_gear_candidate_omits_redundant_mobile_metadata(self):
        compact = self.websim_payload.compact_gear_candidate(
            {
                "slot": "finger1",
                "simcSlot": "finger1",
                "itemId": "250777",
                "id": "250777",
                "name": "Catalog Band",
                "displayName": "Catalog Band",
                "localizedName": "Catalog Band",
                "englishName": "Catalog Band",
                "iconUrl": "https://render.example/item-250777.jpg",
                "quality": "Epic",
                "classKey": "mage",
                "specKey": "frost",
                "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                "metadataLocale": "en_US",
                "gameAsset": {
                    "id": "item:250777:websim-item-metadata",
                    "entityType": "item",
                    "entityId": "250777",
                    "contextKey": "websim-item-metadata",
                    "iconUrl": "https://render.example/item-250777.jpg",
                    "source": "blizzard-game-data-api",
                    "status": "verified",
                },
                "source": "Vault Mage - Arcane Vault",
                "sources": [
                    {
                        "id": "source-250777-heroic",
                        "itemId": "250777",
                        "sourceType": "raid",
                        "sourceLabel": "Vault Mage - Arcane Vault",
                    }
                ],
                "variants": [
                    {
                        "id": "variant-250777-heroic-707",
                        "itemId": "250777",
                        "slot": "finger1",
                        "variantKey": "heroic-707",
                        "itemLevel": 707,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                    }
                ],
                "observedProfileRefs": [
                    {
                        "sourceName": "Raider.IO CN profile gear",
                        "characterName": "HiddenCharacter",
                        "classKey": "mage",
                        "specKey": "frost",
                        "itemId": "250777",
                    }
                ],
                "itemStats": [{"key": "intellect", "label": "智力", "value": 1234}],
                "statSummary": "智力 1234",
                "simcReady": True,
            }
        )

        for redundant_key in (
            "gameAsset",
            "localizedName",
            "englishName",
            "classKey",
            "specKey",
            "metadataSource",
            "metadataLocale",
            "quality",
        ):
            self.assertNotIn(redundant_key, compact)
        self.assertEqual(compact["displayName"], "Catalog Band")
        self.assertEqual(compact["name"], "Catalog Band")
        self.assertEqual(compact["iconUrl"], "https://render.example/item-250777.jpg")
        self.assertEqual(compact["source"], "Vault Mage - Arcane Vault")
        self.assertEqual(compact["sources"][0]["sourceLabel"], "Vault Mage - Arcane Vault")
        self.assertEqual(compact["variants"][0]["simcOptions"]["bonus_id"], "12345")
        self.assertEqual(compact["observedProfileRefs"][0]["sourceName"], "Raider.IO CN profile gear")
        self.assertNotIn("characterName", compact["observedProfileRefs"][0])
        self.assertEqual(compact["statSummary"], "智力 1234")

    def test_compact_gear_candidate_surfaces_source_pending_as_explicit_display_text(self):
        compact = self.websim_payload.compact_gear_candidate(
            {
                "slot": "back",
                "simcSlot": "back",
                "itemId": "249370",
                "id": "249370",
                "name": "龙族虚无披风",
                "displayName": "龙族虚无披风",
                "sourceType": "simcPreset",
                "sources": [
                    {
                        "id": "simc-preset-249370",
                        "itemId": "249370",
                        "sourceType": "simc_preset",
                        "label": "SimulationCraft preset: MID1_Mage_Frost_Frostfire",
                        "sourceLabel": "SimulationCraft preset: MID1_Mage_Frost_Frostfire",
                    }
                ],
                "simcReady": True,
                "statSummary": "力量/敏捷/智力 70；耐力 995；急速 62；精通 30",
                "observedProfileRefs": [
                    {
                        "sourceName": "Raider.IO CN profile gear",
                        "sourceStatus": "verified",
                        "classKey": "mage",
                        "specKey": "frost",
                        "slot": "back",
                        "itemId": "249370",
                        "itemLevel": 285,
                    }
                ],
            }
        )

        self.assertEqual(compact["source"], "来源待补充")
        self.assertNotIn("Raider.IO", compact["source"])
        self.assertNotIn("SimulationCraft", compact["source"])

    def test_compact_gear_candidate_labels_observed_only_variant_without_refs(self):
        compact = self.websim_payload.compact_gear_candidate(
            {
                "slot": "back",
                "simcSlot": "back",
                "itemId": "249370",
                "id": "249370",
                "name": "龙族虚无披风",
                "displayName": "龙族虚无披风",
                "variantSource": "observed_profile",
                "simcReady": True,
                "statDisplayStatus": "verified_variant",
                "variants": [
                    {
                        "id": "observed-demonhunter-devourer-back-249370-b3ec67d77c",
                        "itemId": "249370",
                        "slot": "back",
                        "sourceType": "observed_profile",
                        "status": "verified",
                        "itemLevel": 289,
                    }
                ],
            }
        )

        self.assertEqual(compact["source"], "来源待补充")
        self.assertNotIn("Raider.IO", compact["source"])

    def test_compact_gear_candidate_labels_catalog_with_only_observed_sources_as_source_pending(self):
        compact = self.websim_payload.compact_gear_candidate(
            {
                "slot": "feet",
                "simcSlot": "feet",
                "itemId": "249999",
                "id": "249999",
                "name": "黑爪龙人的法术踏靴",
                "displayName": "黑爪龙人的法术踏靴",
                "sourceType": "catalog",
                "variantSource": "observed_profile",
                "sources": [
                    {
                        "id": "observed-source-evoker-augmentation-feet-249999",
                        "itemId": "249999",
                        "sourceType": "observed_profile",
                        "sourceLabel": "Raider.IO CN observed evoker augmentation",
                    }
                ],
                "variants": [
                    {
                        "id": "observed-evoker-augmentation-feet-249999",
                        "itemId": "249999",
                        "slot": "feet",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "status": "verified",
                        "itemLevel": 298,
                    }
                ],
                "observedProfileRefs": [
                    {
                        "sourceName": "Raider.IO observed gear backfill",
                        "classKey": "evoker",
                        "specKey": "augmentation",
                        "slot": "feet",
                        "itemId": "249999",
                        "itemLevel": 298,
                    }
                ],
            }
        )

        self.assertEqual(compact["source"], "来源待补充")
        self.assertNotIn("Raider.IO", compact["source"])
        self.assertEqual(compact["observedProfileRefs"][0]["sourceName"], "Raider.IO observed gear backfill")

    def test_compact_gear_candidate_labels_simc_candidate_with_observed_source_as_source_pending(self):
        compact = self.websim_payload.compact_gear_candidate(
            {
                "slot": "wrist",
                "simcSlot": "wrist",
                "itemId": "249304",
                "id": "249304",
                "name": "陨落之王的护腕",
                "displayName": "陨落之王的护腕",
                "sourceType": "simcPreset",
                "variantSource": "observed_profile",
                "sources": [
                    {
                        "id": "observed-source-hunter-beast_mastery-wrist-249304",
                        "itemId": "249304",
                        "sourceType": "observed_profile",
                        "sourceLabel": "Raider.IO CN observed hunter beast_mastery",
                    },
                    {
                        "id": "simc-preset-249304",
                        "itemId": "249304",
                        "sourceType": "simc_preset",
                        "sourceLabel": "SimulationCraft preset: MID1_Hunter_Beast_Mastery",
                    },
                ],
                "variants": [
                    {
                        "id": "observed-hunter-beast_mastery-wrist-249304",
                        "itemId": "249304",
                        "slot": "wrist",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "status": "verified",
                        "itemLevel": 289,
                    }
                ],
                "observedProfileRefs": [
                    {
                        "sourceName": "Raider.IO observed gear backfill",
                        "classKey": "hunter",
                        "specKey": "beast_mastery",
                        "slot": "wrist",
                        "itemId": "249304",
                        "itemLevel": 289,
                    }
                ],
            }
        )

        self.assertEqual(compact["source"], "来源待补充")
        self.assertNotIn("Raider.IO", compact["source"])
        self.assertEqual(compact["observedProfileRefs"][0]["sourceName"], "Raider.IO observed gear backfill")

    def test_websim_gear_dedupes_same_visible_dungeon_item_across_legacy_item_ids(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for item_id, stat_value in (("133488", 25), ("49804", 6)):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": "闪亮的镜盔",
                        "inventory_type": {"type": "HEAD", "name": "头部"},
                        "item_class": {"id": 4, "name": "护甲"},
                        "item_subclass": {"id": 3, "name": "锁甲"},
                        "quality": {"name": "史诗"},
                        "preview_item": {
                            "stats": [
                                {"type": {"type": "STAMINA", "name": "耐力"}, "value": stat_value},
                            ],
                        },
                    },
                    {"assets": [{"value": "https://render.example/shiny-mirror-helm.jpg"}]},
                    fallback_name="闪亮的镜盔",
                    english_payload={"name": "Shiny Mirror Helm", "inventory_type": {"name": "Head"}},
                    locale="zh_CN",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"loot-278:608:{item_id}",
                        "itemId": item_id,
                        "sourceType": "dungeon",
                        "sourceLabel": "熔炉之主加弗斯特 - 萨隆矿坑",
                        "instanceId": "278",
                        "encounterId": "608",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"loot-partial-{item_id}-head",
                        "itemId": item_id,
                        "slot": "head",
                        "variantKey": "needs-variant",
                        "label": "Heroic 707",
                        "sourceType": "dungeon",
                        "difficultyKey": "heroic",
                        "itemLevel": 707,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                        "payload": {
                            "statSource": "simulationcraft",
                            "statDisplayStatus": "verified_variant",
                            "itemStats": [{"key": "stamina", "label": "耐力", "value": stat_value}],
                        },
                    },
                )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "evoker", "devastation", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        mirror_helms = [item for item in head_group["items"] if item["displayName"] == "闪亮的镜盔"]
        self.assertEqual(len(mirror_helms), 1)
        self.assertEqual(mirror_helms[0]["itemId"], "133488")

    def test_websim_gear_hides_partial_dungeon_preview_stats_without_current_variant(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "49804",
                {
                    "id": 49804,
                    "name": "闪亮的镜盔",
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 3, "name": "锁甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "INTELLECT", "name": "智力"}, "value": 4},
                            {"type": {"type": "AGILITY", "name": "敏捷"}, "value": 4},
                            {"type": {"type": "STAMINA", "name": "耐力"}, "value": 6},
                        ],
                    },
                },
                {"assets": [{"value": "https://render.example/shiny-mirror-helm.jpg"}]},
                fallback_name="闪亮的镜盔",
                english_payload={"name": "Shiny Mirror Helm", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-278:608:49804",
                    "itemId": "49804",
                    "sourceType": "dungeon",
                    "sourceLabel": "熔炉之主加弗斯特 - 萨隆矿坑",
                    "instanceId": "278",
                    "encounterId": "608",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-49804-head",
                    "itemId": "49804",
                    "slot": "head",
                    "variantKey": "needs-variant",
                    "label": "难度 / 装等待补",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "simcOptions": {},
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "hunter", "beast_mastery", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        self.assertNotIn("49804", {item["itemId"] for item in head_group["items"]})

    def test_websim_gear_filters_localized_non_class_armor_catalog_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for item_id, name, subclass_id, subclass_name in (
                ("250701", "Localized Cloth Hood", 1, "\u5e03\u7532"),
                ("250702", "Localized Leather Mask", 2, "\u76ae\u7532"),
                ("250703", "Localized Mail Visage", 3, "\u9501\u7532"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "HEAD", "name": "\u5934\u90e8"},
                        "item_class": {"id": 4, "name": "\u62a4\u7532"},
                        "item_subclass": {"id": subclass_id, "name": subclass_name},
                        "quality": {"name": "\u53f2\u8bd7"},
                        "preview_item": {
                            "stats": [{"type": {"type": "INTELLECT", "name": "\u667a\u529b"}, "value": 7}],
                        },
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Head"}},
                    locale="zh_CN",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "dungeon",
                        "sourceLabel": "Localized Dungeon",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}",
                        "itemId": item_id,
                        "slot": "head",
                        "variantKey": "needs-variant",
                        "label": "Heroic 707",
                        "sourceType": "dungeon",
                        "difficultyKey": "heroic",
                        "itemLevel": 707,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                        "payload": {
                            "statSource": "simulationcraft",
                            "statDisplayStatus": "verified_variant",
                            "itemStats": [{"key": "intellect", "label": "智力", "value": 7}],
                        },
                    },
                )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = [item["itemId"] for item in head_group["items"]]
        self.assertIn("250701", item_ids)
        self.assertNotIn("250702", item_ids)
        self.assertNotIn("250703", item_ids)
        cloth_item = next(item for item in head_group["items"] if item["itemId"] == "250701")
        self.assertEqual(cloth_item["compatibility"]["status"], "compatible")
        self.assertEqual(cloth_item["compatibility"]["armorStatus"], "compatible")

    def test_websim_gear_payload_hides_mod_options_when_item_lacks_socket_or_enchant_slot(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250778",
                {
                    "id": 250778,
                    "name": "Catalog Hood",
                    "inventory_type": {"type": "INVTYPE_HEAD", "name": "Head"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "INTELLECT", "name": "智力"}, "value": 999},
                        ],
                    },
                },
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {"id": "manual-250778", "itemId": "250778", "sourceType": "raid", "sourceLabel": "Arcane Vault"},
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "manual-250778-heroic",
                    "itemId": "250778",
                    "slot": "head",
                    "variantKey": "heroic-707",
                    "label": "Heroic 707",
                    "sourceType": "raid",
                    "difficultyKey": "heroic",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
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
                        json.dumps(["*"], ensure_ascii=False),
                        json.dumps({"gem_id": "240983"}, ensure_ascii=False),
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
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        head_group = next(group for group in payload["slotGroups"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250778")
        self.assertFalse(catalog_item["modCapabilities"]["hasSocket"])
        self.assertFalse(catalog_item["modCapabilities"]["canEnchant"])
        self.assertEqual(catalog_item["socketOptions"], [])
        self.assertEqual(catalog_item["enchantOptions"], [])

    def test_gear_candidate_sanitizer_strips_stale_placeholder_mod_options(self):
        candidate = self.websim_payload.sanitize_gear_candidate_mod_options(
            {
                "slot": "head",
                "itemId": "250778",
                "id": "250778",
                "modCapabilities": {"hasSocket": False, "canEnchant": False},
                "socketOptions": [
                    {
                        "id": "seed-socket-gem-240983",
                        "name": "Server seed gem 240983",
                        "simcOptions": {"gem_id": "240983"},
                    }
                ],
                "enchantOptions": [
                    {
                        "id": "seed-enchant-8017",
                        "name": "Server seed enchant 8017",
                        "simcOptions": {"enchant_id": "8017"},
                    }
                ],
            }
        )

        self.assertEqual(candidate["socketOptions"], [])
        self.assertEqual(candidate["enchantOptions"], [])
        self.assertFalse(candidate["modCapabilities"]["hasSocket"])
        self.assertFalse(candidate["modCapabilities"]["canEnchant"])

    def test_gear_catalog_sync_adds_observed_profile_variants_from_raiderio(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "观测兜帽",
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 1234}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Observed Hood",
                english_payload={"name": "Observed Hood", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-20T00:00:00+00:00",
                "region": "cn",
                "seasonSlug": "season-mn-1",
                "specs": {
                    "mage:frost": {
                        "observedGear": [
                            {
                                "slot": "head",
                                "name": "Observed Hood",
                                "itemId": 250777,
                                "itemLevel": 707,
                                "quality": "史诗",
                                "icon": "https://render.example/item-250777.jpg",
                                "bonuses": [12345, 67890],
                                "gems": [{"itemId": 240983}],
                                "enchants": [{"spellId": 8017}],
                                "sourceName": "Raider.IO CN profile gear",
                            }
                        ],
                    }
                },
            }

            counts = self.websim_payload.sync_observed_gear_variants(conn, raiderio, {"seasonRevision": "season-test"})
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            conn.commit()
            variants = self.websim_payload.gear_catalog_variants_by_item(conn)
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
            compact_payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 1)
        variant = variants["250777"][0]
        self.assertEqual(variant["sourceType"], "observed_profile")
        self.assertEqual(variant["status"], "partial")
        self.assertEqual(variant["blockers"], ["missing SimulationCraft item stats"])
        self.assertEqual(variant["simcOptions"]["bonus_id"], "12345/67890")
        self.assertEqual(variant["simcOptions"]["gem_id"], "240983")
        self.assertEqual(variant["simcOptions"]["enchant_id"], "8017")
        head_group = next(group for group in payload["slotGroups"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250777")
        self.assertTrue(catalog_item["simcReady"])
        self.assertEqual(catalog_item["variantSource"], "observed_profile")
        self.assertEqual(catalog_item["observedProfileRefs"][0]["sourceName"], "Raider.IO CN profile gear")
        compact_head_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "head")
        compact_item = next(item for item in compact_head_group["items"] if item["itemId"] == "250777")
        self.assertEqual(compact_item["observedProfileRefs"][0]["sourceName"], "Raider.IO CN profile gear")
        self.assertNotIn("characterName", compact_item["observedProfileRefs"][0])
        self.assertEqual(payload["baselineSet"][0]["itemId"], "250777")
        self.assertEqual(payload["equippedSet"]["head"]["itemId"], "250777")
        self.assertEqual(payload["communityTemplates"][0]["sourceName"], "Raider.IO observed gear")
        self.assertEqual(payload["communityTemplates"][0]["readySlotCount"], 1)
        self.assertEqual(payload["communityTemplates"][0]["status"], "partial")
        self.assertTrue(payload["communityTemplates"][0]["canApplyGear"])
        self.assertEqual(payload["communityTemplateSync"]["sources"]["observed_profile"]["status"], "partial")

    def test_gear_catalog_sync_promotes_journal_loot_with_observed_variant(self):
        import server.raiderio_payload as raiderio_payload

        original_raiderio = raiderio_payload.get_raiderio_payload
        self.addCleanup(setattr, raiderio_payload, "get_raiderio_payload", original_raiderio)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="test-season",
                season_label="test-season",
                dungeons=[{"id": "test-dungeon", "dungeonId": "test-dungeon", "instanceId": "1300", "name": "Arcane Vault"}],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1300', 'Arcane Vault', 'Dungeon', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, '1300', 'Arcane Warden', ?, 'now')
                """,
                (
                    "9001",
                    json.dumps(
                        {
                            "id": 9001,
                            "name": "Arcane Warden",
                            "items": [{"item": {"id": 250777, "name": "Catalog Hood"}}],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    '1300:9001:250777', '1300', '9001', '250777', 'Catalog Hood', 'head', 'Epic',
                    'https://render.example/item-250777.jpg', '{}', 'now'
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        raiderio_payload.get_raiderio_payload = lambda conn, allow_sync=False: {
            "sourceStatus": "verified",
            "checkedAt": "2026-06-21T00:00:00+00:00",
            "region": "cn",
            "seasonSlug": "season-mn-1",
            "specs": {
                "mage:frost": {
                    "simcJson": {
                        "sim": {
                            "players": [
                                {
                                    "gear": {
                                        "head": {
                                            "id": 250777,
                                            "ilevel": 707,
                                            "encoded_item": "head,id=250777,ilevel=707,bonus_id=12345",
                                            "intellect": 321,
                                            "stamina": 654,
                                            "haste_rating": 77,
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    "observedGear": [
                        {
                            "slot": "head",
                            "name": "Catalog Hood",
                            "itemId": 250777,
                            "itemLevel": 707,
                            "quality": "Epic",
                            "icon": "https://render.example/item-250777.jpg",
                            "bonuses": [12345],
                            "sourceName": "Raider.IO CN profile gear",
                        }
                    ],
                }
            },
        }

        conn = sqlite3.connect(self.db_path)
        try:
            state = self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            variant_rows = conn.execute(
                """
                SELECT id, source_type, status, simc_options_json, payload_json
                FROM websim_gear_variants
                WHERE item_id = '250777'
                ORDER BY source_type, id
                """
            ).fetchall()
        finally:
            conn.close()

        official_variants = [row for row in variant_rows if row[1] == "dungeon"]
        self.assertEqual(state["status"], "verified")
        self.assertEqual(state["partialCount"], 0)
        self.assertNotIn("missing deterministic SimC variant preset", state["blockers"])
        self.assertFalse(any(str(row[0]).startswith("loot-partial-") for row in variant_rows))
        self.assertEqual(len(official_variants), 1)
        self.assertEqual(official_variants[0][2], "verified")
        self.assertEqual(json.loads(official_variants[0][3])["bonus_id"], "12345")
        official_payload = json.loads(official_variants[0][4])
        self.assertEqual(official_payload["observedVariantSource"], "observed_profile")
        self.assertEqual(official_payload["statSource"], "simulationcraft")
        self.assertEqual(official_payload["statSummary"], "智力 321；耐力 654；急速 77")

    def test_gear_catalog_sync_keeps_raid_preview_partial_without_simc_variant(self):
        import server.raiderio_payload as raiderio_payload

        original_raiderio = raiderio_payload.get_raiderio_payload
        self.addCleanup(setattr, raiderio_payload, "get_raiderio_payload", original_raiderio)
        raiderio_payload.get_raiderio_payload = lambda conn, allow_sync=False: {"sourceStatus": "missing_credentials"}

        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["raids"] = [{"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"}]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "242396",
                {
                    "id": 242396,
                    "name": "Voidglass Cloak",
                    "level": 662,
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321},
                            {"type": {"type": "STAMINA", "name": "Stamina"}, "value": 777},
                        ],
                    },
                },
                {"assets": [{"value": "https://render.example/item-242396.jpg"}]},
                fallback_name="Voidglass Cloak",
                english_payload={"name": "Voidglass Cloak", "inventory_type": {"name": "Back"}},
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1400', 'The Voidspire', 'Raid', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES ('9901', '1400', 'Dimensius', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    '1400:9901:242396', '1400', '9901', '242396', 'Voidglass Cloak', 'back', 'Epic',
                    'https://render.example/item-242396.jpg', '{}', 'now'
                )
                """
            )
            conn.commit()

            self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            variant_rows = conn.execute(
                """
                SELECT id, source_type, difficulty_key, item_level, status, simc_options_json, payload_json
                FROM websim_gear_variants
                WHERE item_id = '242396'
                ORDER BY id
                """
            ).fetchall()
            gear = self.websim_payload.get_websim_gear(conn, "mage", "frost")
        finally:
            conn.close()

        self.assertTrue(any(str(row[0]).startswith("loot-partial-") for row in variant_rows))
        self.assertEqual(len(variant_rows), 1)
        self.assertTrue(str(variant_rows[0][0]).startswith("loot-partial-"))
        self.assertEqual(variant_rows[0][1], "raid")
        self.assertEqual(variant_rows[0][2], "needs-variant")
        self.assertEqual(variant_rows[0][3], 0)
        self.assertEqual(variant_rows[0][4], "partial")
        self.assertEqual(json.loads(variant_rows[0][5]), {})
        variant_payload = json.loads(variant_rows[0][6])
        self.assertNotIn("previewVariantSource", variant_payload)
        back_group = next(group for group in gear["slotGroups"] if group["slot"] == "back")
        self.assertNotIn("242396", {item["itemId"] for item in back_group["items"]})

    def test_websim_gear_demotes_existing_battle_net_preview_variant_at_runtime(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="Fresh Season",
                dungeons=[],
            )
            season["raids"] = [{"id": "1400", "instanceId": "1400", "name": "Manaforge Omega", "category": "Raid"}]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "237535",
                {
                    "id": 237535,
                    "name": "阿托席恩的深渊凝视",
                    "level": 662,
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 1, "name": "布甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "智力"}, "value": 111}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-237535.jpg"}]},
                fallback_name="阿托席恩的深渊凝视",
                english_payload={"name": "Araz's Ritual Forge", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-1400:9901:237535",
                    "itemId": "237535",
                    "sourceType": "raid",
                    "sourceLabel": "诸界吞噬者迪门修斯 - Manaforge Omega",
                    "instanceId": "1400",
                    "encounterId": "9901",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-preview-237535-head-existing",
                    "itemId": "237535",
                    "slot": "head",
                    "variantKey": "battle-net-preview-662-existing",
                    "label": "Battle.net preview 662",
                    "sourceType": "raid",
                    "difficultyKey": "battle_net_preview",
                    "itemLevel": 662,
                    "simcOptions": {},
                    "status": "verified",
                    "payload": {"previewVariantSource": "battle_net_preview", "simcIlevelOnly": True},
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            gear = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in gear["replacementCandidates"] if group["slot"] == "head")
        self.assertNotIn("237535", {item["itemId"] for item in head_group["items"]})

    def test_websim_gear_hides_battle_net_preview_stats_without_verified_variant(self):
        item = {
            "sources": [{"sourceType": "dungeon", "sourceLabel": "兰吉特 - 通天峰"}],
            "statDisplayStatus": "battle_net_item_metadata",
            "statSource": self.websim_payload.ITEM_METADATA_SOURCE,
            "itemStats": [{"key": "intellect", "label": "智力", "value": 3}],
            "statSummary": "智力 3",
            "ilevel": 289,
            "simcReady": False,
        }

        self.assertTrue(self.websim_payload.catalog_item_should_hide_preview_stats(item))

    def test_websim_gear_hides_battle_net_stats_for_simc_preset_items(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "258575",
                {
                    "id": 258575,
                    "name": "刚鳞大氅",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Rare"},
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 3},
                            {"type": {"type": "STAMINA", "name": "Stamina"}, "value": 4},
                        ],
                    },
                },
                fallback_name="Rigid Scale Greatcloak",
                english_payload={"name": "Rigid Scale Greatcloak", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'frost', 'MID1_Mage_Frost_Frostfire', ?, '{}', 'now')
                """,
                (
                    "mage-frost-simc-preset",
                    "\n".join(
                        [
                            'mage="MID1_Mage_Frost_Frostfire"',
                            "spec=frost",
                            "level=90",
                            "back=rigid_scale_greatcloak,id=258575,ilevel=289",
                        ]
                    ),
                ),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        back_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "back")
        back_candidate = next(item for item in back_group["items"] if item["itemId"] == "258575")
        self.assertEqual(back_candidate["sourceType"], "simcPreset")
        self.assertEqual(back_candidate["ilevel"], "289")
        self.assertTrue(back_candidate["simcReady"])
        self.assertNotIn("statSummary", back_candidate)
        self.assertNotIn("itemStats", back_candidate)
        self.assertEqual(back_candidate["statDisplayStatus"], "pending_current_variant")

        baseline_item = next(item for item in payload["baselineSet"] if item["itemId"] == "258575")
        self.assertNotIn("statSummary", baseline_item)
        self.assertNotIn("itemStats", baseline_item)
        self.assertEqual(baseline_item["statDisplayStatus"], "pending_current_variant")
        self.assertNotIn("statSummary", payload["equippedSet"]["back"])

    def test_websim_gear_uses_simc_json_stats_from_profile_preset_payload(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "258575",
                {
                    "id": 258575,
                    "name": "刚鳞大氅",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 3},
                        ],
                    },
                },
                fallback_name="Rigid Scale Greatcloak",
                english_payload={"name": "Rigid Scale Greatcloak", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'frost', 'MID1_Mage_Frost_Frostfire', ?, ?, 'now')
                """,
                (
                    "mage-frost-simc-preset",
                    "\n".join(
                        [
                            'mage="MID1_Mage_Frost_Frostfire"',
                            "spec=frost",
                            "level=90",
                            "back=rigid_scale_greatcloak,id=258575,ilevel=289",
                        ]
                    ),
                    json.dumps(
                        {
                            "simcJson": {
                                "sim": {
                                    "players": [
                                        {
                                            "gear": {
                                                "back": {
                                                    "id": 258575,
                                                    "ilevel": 289,
                                                    "encoded_item": "rigid_scale_greatcloak,id=258575,ilevel=289",
                                                    "stamina": 995,
                                                    "crit_rating": 50,
                                                    "mastery_rating": 42,
                                                    "stragiint": 70,
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        back_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "back")
        back_candidate = next(item for item in back_group["items"] if item["itemId"] == "258575")
        self.assertEqual(back_candidate["statDisplayStatus"], "verified_variant")
        self.assertEqual(back_candidate["statSource"], "simulationcraft")
        self.assertEqual(back_candidate["statSummary"], "力量/敏捷/智力 70；耐力 995；暴击 50；精通 42")
        self.assertNotIn("智力 3", back_candidate["statSummary"])

    def test_sync_observed_variant_stats_from_profile_presets_enriches_observed_variants_without_network(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'frost', 'MID1_Mage_Frost_Frostfire', ?, ?, 'now')
                """,
                (
                    "mage-frost-simc-preset",
                    "\n".join(
                        [
                            'mage="MID1_Mage_Frost_Frostfire"',
                            "spec=frost",
                            "level=90",
                            "back=rigid_scale_greatcloak,id=258575,ilevel=289,bonus_id=13440/40/13577/12699/12806",
                        ]
                    ),
                    json.dumps(
                        {
                            "simcJson": {
                                "sim": {
                                    "players": [
                                        {
                                            "gear": {
                                                "back": {
                                                    "id": 258575,
                                                    "ilevel": 289,
                                                    "encoded_item": (
                                                        "rigid_scale_greatcloak,id=258575,ilevel=289,"
                                                        "bonus_id=13440/40/13577/12699/12806"
                                                    ),
                                                    "stragiint": 70,
                                                    "stamina": 995,
                                                    "crit_rating": 50,
                                                    "mastery_rating": 42,
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-back-258575",
                    "itemId": "258575",
                    "slot": "back",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/40/13577/12699/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-258575-back",
                    "itemId": "258575",
                    "slot": "back",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )

            counts = self.websim_payload.sync_observed_variant_stats_from_profile_presets(conn)
            promotion = self.websim_payload.promote_official_gear_variants_from_observed(conn)
            rows = conn.execute(
                """
                SELECT source_type, status, payload_json
                FROM websim_gear_variants
                WHERE item_id = '258575'
                ORDER BY source_type
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["profilePresetObservedVariantsRefreshed"], 1)
        self.assertEqual(promotion["promotedVariants"], 1)
        payloads = {row[0]: json.loads(row[2]) for row in rows}
        self.assertEqual(payloads["observed_profile"]["statSource"], "simulationcraft")
        self.assertEqual(payloads["observed_profile"]["statSummary"], "力量/敏捷/智力 70；耐力 995；暴击 50；精通 42")
        self.assertEqual(payloads["dungeon"]["statDisplayStatus"], "verified_variant")

    def test_sync_observed_variant_stats_from_same_item_level_sibling_enriches_without_network(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-dk-blood-waist-249380-missing",
                    "itemId": "249380",
                    "slot": "waist",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652/12667/13577/13335/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["deathknight"],
                        "specKeys": ["blood"],
                        "simcStatStatus": "failed",
                        "simcStatFailureKind": "unsupported_profile",
                    },
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-waist-249380-verified",
                    "itemId": "249380",
                    "slot": "waist",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652/13577/13335/13534/12806", "gem_id": "240908"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [
                            {"key": "stamina", "label": "耐力", "value": 1326},
                            {"key": "crit_rating", "label": "暴击", "value": 37},
                            {"key": "mastery_rating", "label": "精通", "value": 87},
                        ],
                        "statSummary": "耐力 1326；暴击 37；精通 87",
                    },
                },
            )

            counts = self.websim_payload.sync_observed_variant_stats_from_same_item_level_siblings(conn)
            payload_json = conn.execute(
                """
                SELECT payload_json
                FROM websim_gear_variants
                WHERE id = 'observed-dk-blood-waist-249380-missing'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        payload = json.loads(payload_json)
        self.assertEqual(counts["sameItemLevelObservedVariantsRefreshed"], 1)
        self.assertEqual(payload["statDisplayStatus"], "verified_variant")
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statSummary"], "耐力 1326；暴击 37；精通 87")
        self.assertNotIn("simcStatStatus", payload)
        self.assertNotIn("simcStatFailureKind", payload)

    def test_sync_observed_variant_stats_from_profile_presets_matches_bonus_variant_when_preset_has_item_level_only(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'mage', 'frost', 'MID1_Mage_Frost_Frostfire', ?, ?, 'now')
                """,
                (
                    "mage-frost-simc-preset",
                    "\n".join(
                        [
                            'mage="MID1_Mage_Frost_Frostfire"',
                            "spec=frost",
                            "level=90",
                            "back=rigid_scale_greatcloak,id=258575,ilevel=289",
                        ]
                    ),
                    json.dumps(
                        {
                            "simcJson": {
                                "sim": {
                                    "players": [
                                        {
                                            "gear": {
                                                "back": {
                                                    "id": 258575,
                                                    "ilevel": 289,
                                                    "encoded_item": "rigid_scale_greatcloak,id=258575,ilevel=289",
                                                    "stragiint": 70,
                                                    "stamina": 995,
                                                    "crit_rating": 50,
                                                    "mastery_rating": 42,
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-back-258575",
                    "itemId": "258575",
                    "slot": "back",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/40/13577/12699/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )

            counts = self.websim_payload.sync_observed_variant_stats_from_profile_presets(conn)
            payload_json = conn.execute(
                """
                SELECT payload_json
                FROM websim_gear_variants
                WHERE id = 'observed-mage-frost-back-258575'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        payload = json.loads(payload_json)
        self.assertEqual(counts["profilePresetObservedVariantsRefreshed"], 1)
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statSummary"], "力量/敏捷/智力 70；耐力 995；暴击 50；精通 42")

    def test_sync_observed_variant_stats_from_profile_presets_reuses_same_item_level_stats_when_bonus_differs(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, 'paladin', 'protection', 'MID1_Paladin_Protection', ?, ?, 'now')
                """,
                (
                    "paladin-protection-simc-preset",
                    "\n".join(
                        [
                            'paladin="MID1_Paladin_Protection"',
                            "spec=protection",
                            "level=90",
                            "back=shroud_of_the_soulhunter,id=251161,bonus_id=4786/12806",
                        ]
                    ),
                    json.dumps(
                        {
                            "simcJson": {
                                "sim": {
                                    "players": [
                                        {
                                            "gear": {
                                                "back": {
                                                    "id": 251161,
                                                    "ilevel": 289,
                                                    "encoded_item": (
                                                        "shroud_of_the_soulhunter,id=251161,"
                                                        "bonus_id=4786/12806"
                                                    ),
                                                    "stragiint": 70,
                                                    "stamina": 995,
                                                    "crit_rating": 34,
                                                    "versatility_rating": 58,
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-monk-mistweaver-back-251161",
                    "itemId": "251161",
                    "slot": "back",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/6652/13577/12699/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["monk"],
                        "specKeys": ["mistweaver"],
                        "simcStatStatus": "failed",
                        "simcStatFailureKind": "unsupported_profile",
                    },
                },
            )

            counts = self.websim_payload.sync_observed_variant_stats_from_profile_presets(conn)
            payload_json = conn.execute(
                """
                SELECT payload_json
                FROM websim_gear_variants
                WHERE id = 'observed-monk-mistweaver-back-251161'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        payload = json.loads(payload_json)
        self.assertEqual(counts["profilePresetObservedVariantsRefreshed"], 1)
        self.assertEqual(payload["statDisplayStatus"], "verified_variant")
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statSummary"], "力量/敏捷/智力 70；耐力 995；暴击 34；全能 58")
        self.assertNotIn("simcStatStatus", payload)
        self.assertNotIn("simcStatFailureKind", payload)

    def test_websim_gear_hides_mod_options_for_partial_catalog_candidate(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260312",
                {
                    "id": 260312,
                    "name": "挑战防御者斗篷",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 3}],
                    },
                },
                fallback_name="Challenger's Drape",
                english_payload={"name": "Challenger's Drape", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-260312",
                    "itemId": "260312",
                    "sourceType": "dungeon",
                    "sourceLabel": "瑟拉奈尔·日鞭 - 魔导师平台",
                    "seasonRevision": "season-test",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-260312-back",
                    "itemId": "260312",
                    "slot": "back",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-enchant-a07c4ae7db",
                    "type": "enchant",
                    "name": "Observed enchant 4897",
                    "slots": ["back"],
                    "simcOptions": {"enchant_id": "4897"},
                    "status": "verified",
                    "payload": {"source": "observed_variant"},
                },
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
        finally:
            conn.close()

        back_group = next(group for group in payload["slotGroups"] if group["slot"] == "back")
        self.assertNotIn("260312", {item["itemId"] for item in back_group["items"]})

    def test_websim_gear_hides_unenriched_observed_mod_option_labels(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260313",
                {
                    "id": 260313,
                    "name": "真实斗篷",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "quality": {"name": "Epic"},
                },
                fallback_name="Verified Drape",
                english_payload={"name": "Verified Drape", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-260313",
                    "itemId": "260313",
                    "sourceType": "dungeon",
                    "sourceLabel": "瑟拉奈尔·日鞭 - 魔导师平台",
                    "seasonRevision": "season-test",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-verified-260313-back",
                    "itemId": "260313",
                    "slot": "back",
                    "variantKey": "hero-289",
                    "label": "Hero 289",
                    "sourceType": "dungeon",
                    "difficultyKey": "hero",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "itemStats": [{"key": "intellect", "label": "智力", "value": 124}],
                        "statSummary": "智力 124",
                    },
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-enchant-placeholder",
                    "type": "enchant",
                    "name": "Observed enchant 4897",
                    "slots": ["back"],
                    "simcOptions": {"enchant_id": "4897"},
                    "status": "verified",
                    "payload": {"source": "observed_variant"},
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-enchant-enriched",
                    "type": "enchant",
                    "name": "披风真实附魔",
                    "slots": ["back"],
                    "simcOptions": {"enchant_id": "8017"},
                    "status": "verified",
                    "payload": {
                        "source": "observed_variant",
                        "displayName": "披风真实附魔",
                        "metadataStatus": "verified",
                    },
                },
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
        finally:
            conn.close()

        back_group = next(group for group in payload["slotGroups"] if group["slot"] == "back")
        catalog_item = next(item for item in back_group["items"] if item["itemId"] == "260313")
        option_names = [option["name"] for option in catalog_item["enchantOptions"]]
        self.assertNotIn("Observed enchant 4897", option_names)
        self.assertIn("披风真实附魔", option_names)

    def test_gear_catalog_sync_keeps_low_level_dungeon_preview_partial(self):
        import server.raiderio_payload as raiderio_payload

        original_raiderio = raiderio_payload.get_raiderio_payload
        self.addCleanup(setattr, raiderio_payload, "get_raiderio_payload", original_raiderio)
        raiderio_payload.get_raiderio_payload = lambda conn, allow_sync=False: {"sourceStatus": "missing_credentials"}

        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260312",
                {
                    "id": 260312,
                    "name": "Legacy Preview Ring",
                    "level": 44,
                    "inventory_type": {"type": "FINGER", "name": "Finger"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "bonus_list": [13578],
                        "stats": [{"type": {"type": "HASTE", "name": "Haste"}, "value": 123}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-260312.jpg"}]},
                fallback_name="Legacy Preview Ring",
                english_payload={"name": "Legacy Preview Ring", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1300', 'Magisters'' Terrace', 'Dungeon', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES ('9001', '1300', 'Selin Fireheart', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    '1300:9001:260312', '1300', '9001', '260312', 'Legacy Preview Ring', 'finger1', 'Epic',
                    'https://render.example/item-260312.jpg', '{}', 'now'
                )
                """
            )
            conn.commit()

            self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            variant_rows = conn.execute(
                """
                SELECT id, source_type, item_level, status, blockers_json
                FROM websim_gear_variants
                WHERE item_id = '260312'
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(len(variant_rows), 1)
        self.assertTrue(str(variant_rows[0][0]).startswith("loot-partial-"))
        self.assertEqual(variant_rows[0][1], "dungeon")
        self.assertEqual(variant_rows[0][2], 0)
        self.assertEqual(variant_rows[0][3], "partial")
        self.assertIn("missing deterministic SimC variant preset", json.loads(variant_rows[0][4]))

    def test_gear_catalog_sync_dedupes_observed_gear_when_aggregate_and_profile_repeat_item(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            observed_item = {
                "slot": "head",
                "name": "Fearsome Visage of Ra-den's Chosen",
                "itemId": 250015,
                "itemLevel": 289,
                "bonuses": [6652, 13335, 13338, 13575, 12806, 13534],
                "gems": [240890],
                "enchants": [8017],
                "sourceName": "Raider.IO CN profile gear",
            }
            raiderio = {
                "sourceStatus": "synced",
                "checkedAt": "2026-06-21T00:00:00+00:00",
                "region": "cn",
                "seasonSlug": "season-mn-1",
                "specs": {
                    "monk:mistweaver": {
                        "observedGear": [observed_item],
                        "observedGearProfiles": [
                            {
                                "characterName": "Realmonk",
                                "realmSlug": "isillien",
                                "profileUrl": "https://raider.io/characters/cn/isillien/Realmonk",
                                "gear": [dict(observed_item)],
                            }
                        ],
                    }
                },
            }

            counts = self.websim_payload.sync_observed_gear_variants(conn, raiderio, {"seasonRevision": "season-mn-1"})
            variant_count = conn.execute("SELECT COUNT(*) FROM websim_gear_variants").fetchone()[0]
            source_count = conn.execute("SELECT COUNT(*) FROM websim_gear_sources").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 1)
        self.assertEqual(counts["verifiedObservedVariants"], 0)
        self.assertEqual(counts["partialObservedVariants"], 1)
        self.assertEqual(variant_count, 1)
        self.assertEqual(source_count, 1)

    def test_sync_observed_gear_variants_imports_top_level_raiderio_profiles(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            raiderio = {
                "sourceStatus": "synced",
                "checkedAt": "2026-06-21T16:00:00+00:00",
                "region": "cn",
                "seasonSlug": "season-mn-1",
                "specAggregates": [],
                "profiles": [
                    {
                        "name": "Selong",
                        "realmSlug": "isillien",
                        "region": "cn",
                        "classKey": "evoker",
                        "specKey": "augmentation",
                        "profileUrl": "https://raider.io/characters/cn/isillien/Selong",
                        "gear": [
                            {
                                "slot": "main_hand",
                                "name": "Splitshroud Stinger",
                                "itemId": 251111,
                                "itemLevel": 298,
                                "quality": "Epic",
                                "icon": "inv_knife_1h_etherealraid_d_02",
                                "bonuses": [13440, 6652, 12701, 13654],
                                "gems": [],
                                "enchants": [8039],
                                "sourceName": "Raider.IO",
                                "sourceStatus": "source_reference",
                            }
                        ],
                    }
                ],
            }

            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-mn-1"},
            )
            variant = conn.execute(
                """
                SELECT item_id, slot, status, item_level, simc_options_json, blockers_json, payload_json
                FROM websim_gear_variants
                WHERE item_id = '251111'
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 1)
        self.assertEqual(counts["verifiedObservedVariants"], 0)
        self.assertEqual(counts["partialObservedVariants"], 1)
        self.assertIsNotNone(variant)
        self.assertEqual(variant[1], "main_hand")
        self.assertEqual(variant[2], "partial")
        self.assertEqual(variant[3], 298)
        self.assertEqual(json.loads(variant[4])["bonus_id"], "13440/6652/12701/13654")
        self.assertEqual(json.loads(variant[4])["enchant_id"], "8039")
        self.assertEqual(json.loads(variant[5]), ["missing SimulationCraft item stats"])
        self.assertEqual(json.loads(variant[6])["observedProfileRefs"][0]["characterName"], "Selong")

    def test_sync_observed_gear_variants_preserves_verified_cache_when_raiderio_source_is_partial(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-existing-251111-main_hand",
                    "itemId": "251111",
                    "slot": "main_hand",
                    "variantKey": "observed-298-existing",
                    "label": "Observed 298",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "13440/6652/12701/13654", "enchant_id": "8039"},
                    "status": "verified",
                },
            )
            raiderio = {
                "sourceStatus": "partial",
                "checkedAt": "2026-06-22T01:53:18+00:00",
                "profiles": [
                    {
                        "classKey": "evoker",
                        "specKey": "augmentation",
                        "gear": [
                            {
                                "slot": "main_hand",
                                "itemId": 251111,
                                "itemLevel": 298,
                                "bonuses": [13440, 6652, 12701, 13654],
                                "enchants": [8039],
                            }
                        ],
                    }
                ],
            }

            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-mn-1"},
            )
            variants = conn.execute(
                """
                SELECT id, status, simc_options_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 0)
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0][0], "observed-existing-251111-main_hand")
        self.assertEqual(variants[0][1], "verified")
        self.assertEqual(json.loads(variants[0][2])["bonus_id"], "13440/6652/12701/13654")

    def test_sync_observed_gear_variants_preserves_larger_verified_cache_from_smaller_payload(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for item_id in ("251111", "251112"):
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-existing-{item_id}-main_hand",
                        "itemId": item_id,
                        "slot": "main_hand",
                        "variantKey": f"observed-298-{item_id}",
                        "label": "Observed 298",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 298,
                        "simcOptions": {"bonus_id": "13440/6652/12701/13654", "enchant_id": "8039"},
                        "status": "verified",
                        "payload": {
                            "statSource": "simulationcraft",
                            "statDisplayStatus": "verified_variant",
                            "itemStats": [{"key": "intellect", "label": "智力", "value": 111}],
                            "statSummary": "智力 111",
                        },
                    },
                )
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-22T03:11:23+00:00",
                "profiles": [
                    {
                        "classKey": "evoker",
                        "specKey": "augmentation",
                        "gear": [
                            {
                                "slot": "main_hand",
                                "itemId": 251111,
                                "itemLevel": 298,
                                "bonuses": [13440, 6652, 12701, 13654],
                                "enchants": [8039],
                            }
                        ],
                    }
                ],
            }

            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-mn-1"},
            )
            variants = conn.execute(
                """
                SELECT id, status
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 0)
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(counts["sourceStatus"], "verified")
        self.assertEqual(counts["preservedVerifiedObservedVariants"], 2)
        self.assertEqual([row[0] for row in variants], [
            "observed-existing-251111-main_hand",
            "observed-existing-251112-main_hand",
        ])
        self.assertTrue(all(row[1] == "verified" for row in variants))

    def test_sync_observed_gear_variants_can_incrementally_upsert_without_replacing_cache(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-existing-251111-main_hand",
                    "itemId": "251111",
                    "slot": "main_hand",
                    "variantKey": "observed-298-251111",
                    "label": "Observed 298",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "13440/6652/12701/13654", "enchant_id": "8039"},
                    "status": "verified",
                },
            )
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-22T04:00:00+00:00",
                "profiles": [
                    {
                        "name": "Targetmage",
                        "realmSlug": "isillien",
                        "region": "cn",
                        "classKey": "mage",
                        "specKey": "frost",
                        "profileUrl": "https://raider.io/characters/cn/isillien/Targetmage",
                        "gear": [
                            {
                                "slot": "head",
                                "itemId": 251222,
                                "itemLevel": 704,
                                "bonuses": [12345, 67890],
                                "gems": [{"itemId": 240983}],
                                "enchants": [8017],
                                "sourceName": "Raider.IO target profile",
                            }
                        ],
                    }
                ],
            }

            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-mn-1"},
                replace=False,
            )
            rows = conn.execute(
                """
                SELECT item_id, slot, status, item_level, simc_options_json, payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY item_id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 1)
        self.assertEqual([row[0] for row in rows], ["251111", "251222"])
        new_row = rows[1]
        self.assertEqual(new_row[1], "head")
        self.assertEqual(new_row[2], "partial")
        self.assertEqual(new_row[3], 704)
        self.assertEqual(json.loads(new_row[4]), {
            "bonus_id": "12345/67890",
            "gem_id": "240983",
            "enchant_id": "8017",
        })
        self.assertEqual(json.loads(new_row[5])["observedProfileRefs"][0]["characterName"], "Targetmage")

    def test_gear_observed_backfill_state_defaults_when_missing(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            state = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111", "251222"],
            )
        finally:
            conn.close()

        self.assertEqual(state["schemaVersion"], 1)
        self.assertEqual(state["provider"], "raiderio")
        self.assertEqual(state["providers"]["raiderio"]["status"], "idle")
        self.assertEqual(state["providers"]["wcl"]["status"], "not_implemented")
        self.assertEqual(state["lastRunStatus"], "idle")
        self.assertEqual(state["cursor"]["targetItemCount"], 2)
        self.assertEqual(state["cursor"]["targetOffset"], 0)
        self.assertEqual(state["cursor"]["profileOffset"], 0)
        self.assertEqual(state["matchedTargetItemIds"], [])

    def test_gear_observed_backfill_state_persists_in_websim_sync_state(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            state = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111"],
            )
            state["lastRunStatus"] = "ok"
            state["processedTargetItemCount"] = 1
            state["processedProfileCount"] = 2
            state["matchedTargetItemIds"] = ["251111"]
            state["cursor"]["targetOffset"] = 1
            state["cursor"]["profileOffset"] = 2
            self.websim_payload.write_gear_observed_backfill_state(conn, state)
            persisted = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111"],
            )
            raw = self.websim_payload.get_sync_state(conn, "gear_observed_backfill")
        finally:
            conn.close()

        self.assertEqual(persisted["lastRunStatus"], "ok")
        self.assertEqual(persisted["processedTargetItemCount"], 1)
        self.assertEqual(persisted["processedProfileCount"], 2)
        self.assertEqual(persisted["matchedTargetItemIds"], ["251111"])
        self.assertEqual(persisted["cursor"]["targetOffset"], 1)
        self.assertEqual(persisted["cursor"]["profileOffset"], 2)
        self.assertEqual(raw["provider"], "raiderio")

    def test_gear_observed_backfill_state_read_preserves_persisted_provider(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            state = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111"],
                provider="wcl",
            )
            state["lastRunStatus"] = "ok"
            state["providers"]["wcl"] = {"status": "ok"}
            self.websim_payload.write_gear_observed_backfill_state(conn, state)
            persisted = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111"],
            )
        finally:
            conn.close()

        self.assertEqual(persisted["provider"], "wcl")
        self.assertEqual(persisted["providers"]["wcl"]["status"], "ok")

    def test_gear_observed_backfill_cursor_resets_when_target_hash_changes(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            state = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251111", "251222"],
            )
            state["cursor"]["targetOffset"] = 2
            state["cursor"]["profileOffset"] = 5
            state["matchedTargetItemIds"] = ["251111"]
            self.websim_payload.write_gear_observed_backfill_state(conn, state)
            reset = self.websim_payload.read_gear_observed_backfill_state(
                conn,
                target_item_ids=["251333"],
            )
        finally:
            conn.close()

        self.assertEqual(reset["cursor"]["targetItemCount"], 1)
        self.assertEqual(reset["cursor"]["targetOffset"], 0)
        self.assertEqual(reset["cursor"]["profileOffset"], 0)
        self.assertEqual(reset["matchedTargetItemIds"], [])

    def test_gear_observed_backfill_profile_window_resumes_and_wraps(self):
        state = {
            "schemaVersion": 1,
            "provider": "raiderio",
            "cursor": {
                "targetItemHash": "",
                "targetItemCount": 0,
                "targetOffset": 2,
                "profileOffset": 3,
            },
            "matchedTargetItemIds": [],
        }
        profiles = [{"name": f"Profile{index}"} for index in range(5)]

        window = self.websim_payload.build_gear_observed_backfill_window(
            ["251111", "251222", "251333"],
            profiles,
            state,
            target_limit=2,
            profile_limit=3,
        )

        self.assertEqual(window["targetItemIds"], ["251333", "251111"])
        self.assertEqual([profile["name"] for profile in window["profiles"]], ["Profile3", "Profile4", "Profile0"])
        self.assertEqual(window["cursor"]["targetOffset"], 1)
        self.assertEqual(window["cursor"]["profileOffset"], 1)
        self.assertTrue(window["wrapped"])

    def test_observed_gear_simc_options_do_not_treat_bare_gem_ids_as_bonus_or_ilevel(self):
        options = self.websim_payload.observed_gear_simc_options(
            {
                "bonuses": [6652],
                "gems": [240916],
            }
        )

        self.assertEqual(options["bonus_id"], "6652")
        self.assertEqual(options["gem_id"], "240916")
        self.assertNotIn("gem_bonus_id", options)
        self.assertNotIn("gem_ilevel", options)

    def test_observed_gear_simc_options_keeps_structured_gem_bonus_and_ilevel(self):
        options = self.websim_payload.observed_gear_simc_options(
            {
                "gems": [{"itemId": 240916, "bonusId": 9727, "itemLevel": 707}],
            }
        )

        self.assertEqual(options["gem_id"], "240916")
        self.assertEqual(options["gem_bonus_id"], "9727")
        self.assertEqual(options["gem_ilevel"], "707")

    def test_simc_json_gear_stats_by_slot_extracts_resolved_item_stats(self):
        simc_json = {
            "sim": {
                "players": [
                    {
                        "gear": {
                            "head": {
                                "id": 249979,
                                "ilevel": 289,
                                "encoded_item": (
                                    "locus_of_the_primal_core,id=249979,"
                                    "bonus_id=41/6652/12806/13335/13338/13534/13575,"
                                    "ilevel=289,gem_id=240906,enchant_id=8017"
                                ),
                                "agiint": 124,
                                "stamina": 1768,
                                "haste_rating": 55,
                                "mastery_rating": 109,
                                "leech_rating": 71,
                            },
                            "shoulders": {
                                "id": 249977,
                                "ilevel": 289,
                                "agiint": 93,
                                "stamina": 1326,
                            },
                            "trinket1": {
                                "id": 252421,
                                "ilevel": 298,
                                "encoded_item": "rotting_globule,id=252421,bonus_id=6652/12699/13440/13654,ilevel=298",
                                "stragi": 128,
                            },
                            "waist": {
                                "id": 249967,
                                "ilevel": 298,
                                "encoded_item": "item_249967,id=249967,bonus_id=3183/6652/13335/13534/13786,ilevel=298",
                                "strint": 101,
                                "stamina": 1480,
                            },
                        },
                    }
                ]
            }
        }

        by_slot = self.websim_payload.simc_json_gear_stats_by_slot(simc_json)

        self.assertEqual(by_slot["head"]["itemId"], "249979")
        self.assertEqual(by_slot["head"]["itemLevel"], 289)
        self.assertEqual(by_slot["head"]["simcOptions"]["bonus_id"], "41/6652/12806/13335/13338/13534/13575")
        self.assertEqual(by_slot["head"]["simcOptions"]["gem_id"], "240906")
        self.assertEqual(by_slot["head"]["simcOptions"]["enchant_id"], "8017")
        self.assertEqual(by_slot["shoulder"]["itemId"], "249977")
        self.assertEqual(by_slot["head"]["statSummary"], "敏捷 or 智力 124；耐力 1768；急速 55；精通 109；吸血 71")
        self.assertEqual(by_slot["trinket1"]["statSummary"], "力量 or 敏捷 128")
        self.assertEqual(by_slot["waist"]["statSummary"], "力量 or 智力 101；耐力 1480")

    def test_sync_observed_gear_variants_persists_simc_json_stats_not_raiderio_tooltip_stats(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            simc_json = {
                "sim": {
                    "players": [
                        {
                            "gear": {
                                "head": {
                                    "id": 249979,
                                    "ilevel": 289,
                                    "encoded_item": (
                                        "locus_of_the_primal_core,id=249979,"
                                        "bonus_id=41/6652/12806/13335/13338/13534/13575,"
                                        "ilevel=289,gem_id=240906,enchant_id=8017"
                                    ),
                                    "agiint": 124,
                                    "stamina": 1768,
                                    "haste_rating": 55,
                                    "mastery_rating": 109,
                                    "leech_rating": 71,
                                }
                            }
                        }
                    ]
                }
            }
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-22T00:00:00+00:00",
                "profiles": [
                    {
                        "name": "Mandur",
                        "realmSlug": "hyjal",
                        "profileUrl": "https://raider.io/characters/eu/hyjal/Mandur",
                        "classKey": "shaman",
                        "specKey": "elemental",
                        "simcJson": simc_json,
                        "gear": [
                            {
                                "slot": "head",
                                "name": "原始核心的轨迹头盔",
                                "itemId": 249979,
                                "itemLevel": 289,
                                "bonuses": [41, 6652, 12806, 13335, 13338, 13534, 13575],
                                "gems": [240906],
                                "enchants": [8017],
                                "itemStats": [{"key": "intellect", "label": "智力", "value": 9999}],
                            },
                            {
                                "slot": "legs",
                                "name": "Unknown",
                                "itemId": 268288,
                                "itemLevel": 289,
                                "bonuses": [6652],
                            },
                        ],
                    }
                ],
            }

            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-test"},
            )
            conn.commit()

            self.assertEqual(counts["verifiedObservedVariants"], 1)
            self.assertEqual(counts["partialObservedVariants"], 1)
            rows = conn.execute(
                """
                SELECT item_id, status, blockers_json, payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                ORDER BY item_id
                """
            ).fetchall()
        finally:
            conn.close()

        payloads = {
            str(item_id): {
                "status": status,
                "blockers": json.loads(blockers_json),
                "payload": json.loads(payload_json),
            }
            for item_id, status, blockers_json, payload_json in rows
        }
        head_payload = payloads["249979"]["payload"]
        self.assertEqual(payloads["249979"]["status"], "verified")
        self.assertEqual(head_payload["statSource"], "simulationcraft")
        self.assertEqual(head_payload["statDisplayStatus"], "verified_variant")
        self.assertEqual(head_payload["statSummary"], "敏捷 or 智力 124；耐力 1768；急速 55；精通 109；吸血 71")
        self.assertEqual(head_payload["itemStats"][0]["key"], "agiint")
        self.assertNotIn("9999", json.dumps(head_payload, ensure_ascii=False))
        self.assertEqual(payloads["268288"]["status"], "partial")
        self.assertEqual(payloads["268288"]["blockers"], ["missing SimulationCraft item stats"])
        self.assertNotIn("itemStats", payloads["268288"]["payload"])

    def test_sync_observed_gear_variants_preserves_existing_simc_stats_when_replaced_by_statless_cache(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            statful_raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-22T00:00:00+00:00",
                "profiles": [
                    {
                        "name": "Mandur",
                        "realmSlug": "hyjal",
                        "profileUrl": "https://raider.io/characters/eu/hyjal/Mandur",
                        "classKey": "shaman",
                        "specKey": "elemental",
                        "simcJson": {
                            "sim": {
                                "players": [
                                    {
                                        "gear": {
                                            "head": {
                                                "id": 249979,
                                                "ilevel": 289,
                                                "encoded_item": (
                                                    "locus_of_the_primal_core,id=249979,"
                                                    "bonus_id=41/6652/12806/13335/13338/13534/13575,"
                                                    "ilevel=289,gem_id=240906,enchant_id=8017"
                                                ),
                                                "agiint": 124,
                                                "stamina": 1768,
                                                "haste_rating": 55,
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "gear": [
                            {
                                "slot": "head",
                                "name": "原始核心的轨迹头盔",
                                "itemId": 249979,
                                "itemLevel": 289,
                                "bonuses": [41, 6652, 12806, 13335, 13338, 13534, 13575],
                                "gems": [240906],
                                "enchants": [8017],
                            }
                        ],
                    }
                ],
            }
            statless_raiderio = json.loads(json.dumps(statful_raiderio, ensure_ascii=False))
            statless_raiderio["profiles"][0].pop("simcJson", None)

            self.websim_payload.sync_observed_gear_variants(
                conn,
                statful_raiderio,
                {"seasonRevision": "season-test"},
            )
            self.websim_payload.sync_observed_gear_variants(
                conn,
                statless_raiderio,
                {"seasonRevision": "season-test"},
            )
            payload_json = conn.execute(
                """
                SELECT payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                  AND item_id = '249979'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        payload = json.loads(payload_json)
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statDisplayStatus"], "verified_variant")
        self.assertEqual(payload["statSummary"], "敏捷 or 智力 124；耐力 1768；急速 55")

    def test_sync_observed_gear_variants_preserves_existing_simc_failure_marker_when_replacing_cache(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-waist-268289-260eb7346c",
                    "itemId": "268289",
                    "slot": "waist",
                    "variantKey": "observed-704-260eb7346c",
                    "label": "Observed 704",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 704,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "simcStatStatus": "failed",
                        "simcStatFailureKind": "item_resolution",
                        "simcStatError": "Item 'item_268289' failed",
                    },
                },
            )
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-22T00:00:00+00:00",
                "profiles": [
                    {
                        "name": "Targetmage",
                        "realmSlug": "isillien",
                        "profileUrl": "https://raider.io/characters/cn/isillien/Targetmage",
                        "classKey": "mage",
                        "specKey": "frost",
                        "gear": [
                            {
                                "slot": "waist",
                                "name": "Failed Waist",
                                "itemId": 268289,
                                "itemLevel": 704,
                                "bonuses": [12345],
                            }
                        ],
                    }
                ],
            }
            self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-test"},
            )
            payload_json = conn.execute(
                """
                SELECT payload_json
                FROM websim_gear_variants
                WHERE source_type = 'observed_profile'
                  AND item_id = '268289'
                  AND slot = 'waist'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        payload = json.loads(payload_json)
        self.assertEqual(payload["simcStatStatus"], "failed")
        self.assertEqual(payload["simcStatFailureKind"], "item_resolution")
        self.assertEqual(payload["simcStatError"], "Item 'item_268289' failed")

    def test_websim_gear_filters_incompatible_observed_profile_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-20T00:00:00+00:00",
                "region": "cn",
                "seasonSlug": "season-mn-1",
                "specs": {
                    "monk:brewmaster": {
                        "simcGear": {
                            "head": {
                                "itemId": 250777,
                                "itemLevel": 707,
                                "bonus_id": "12345",
                                "agiint": 124,
                                "stamina": 1768,
                            }
                        },
                        "observedGear": [
                            {
                                "slot": "head",
                                "name": "Brewmaster Hood",
                                "itemId": 250777,
                                "itemLevel": 707,
                                "bonuses": [12345],
                                "sourceName": "Raider.IO CN profile gear",
                            }
                        ],
                    },
                    "hunter:beast_mastery": {
                        "observedGear": [
                            {
                                "slot": "head",
                                "name": "Sharpeye Gleam",
                                "itemId": 258585,
                                "itemLevel": 707,
                                "bonuses": [67890],
                                "sourceName": "Raider.IO CN profile gear",
                            }
                        ],
                    },
                },
            }
            self.websim_payload.sync_observed_gear_variants(conn, raiderio, {"seasonRevision": "season-test"})
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "monk", "brewmaster")
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = [item["itemId"] for item in head_group["items"]]
        self.assertIn("250777", item_ids)
        self.assertNotIn("258585", item_ids)
        self.assertFalse(any((item.get("compatibility") or {}).get("status") == "incompatible" for item in head_group["items"]))

    def test_websim_gear_filters_promoted_tier_set_variants_to_observed_class(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for item_id, name, set_name, observed_class, observed_spec in (
                ("249961", "光耀裁决的坚定凝视", "光耀裁决的套装", "paladin", "retribution"),
                ("249970", "冷厉骑手的头冠", "冷厉骑手的挽歌", "deathknight", "unholy"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "HEAD", "name": "头部"},
                        "item_class": {"id": 4, "name": "护甲"},
                        "item_subclass": {"id": 4, "name": "板甲"},
                        "quality": {"name": "史诗"},
                        "item_set": {"name": set_name},
                        "preview_item": {
                            "stats": [{"type": {"type": "STRENGTH", "name": "力量"}, "value": 18}],
                        },
                    },
                    {"assets": [{"value": f"https://render.example/item-{item_id}.jpg"}]},
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Head"}},
                    locale="zh_CN",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"set-source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "tier_set",
                        "sourceLabel": set_name,
                        "seasonRevision": "season-test",
                        "payload": {"authority": self.websim_payload.ITEM_METADATA_SOURCE, "setName": set_name},
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"set-observed-{item_id}-head",
                        "itemId": item_id,
                        "slot": "head",
                        "variantKey": "observed-289",
                        "label": "Observed 289",
                        "sourceType": "tier_set",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652/13534"},
                        "status": "verified",
                        "payload": {
                            "observedProfileRefs": [
                                {"classKey": observed_class, "specKey": observed_spec, "itemId": item_id}
                            ],
                            "setName": set_name,
                        },
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "paladin", "retribution", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = [item["itemId"] for item in head_group["items"]]
        self.assertIn("249961", item_ids)
        self.assertNotIn("249970", item_ids)

    def test_websim_gear_collapses_observed_variant_buttons_and_hides_preview_stats(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249961",
                {
                    "id": 249961,
                    "name": "光耀裁决的坚定凝视",
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 4, "name": "板甲"},
                    "quality": {"name": "史诗"},
                    "item_set": {"name": "光耀裁决的套装"},
                    "preview_item": {
                        "stats": [{"type": {"type": "STRENGTH", "name": "力量"}, "value": 18}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-249961.jpg"}]},
                fallback_name="光耀裁决的坚定凝视",
                english_payload={"name": "Radiant Verdict Visage", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "set-source-249961",
                    "itemId": "249961",
                    "sourceType": "tier_set",
                    "sourceLabel": "光耀裁决的套装",
                    "seasonRevision": "season-test",
                    "payload": {"authority": self.websim_payload.ITEM_METADATA_SOURCE, "setName": "光耀裁决的套装"},
                },
            )
            for index, gem_id in enumerate(("240908", "240983", "240898", "240906", "240890"), start=1):
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"set-observed-249961-head-{index}",
                        "itemId": "249961",
                        "slot": "head",
                        "variantKey": f"observed-289-{index}",
                        "label": "Observed 289",
                        "sourceType": "tier_set",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652/13534", "gem_id": gem_id, "enchant_id": "8017"},
                        "status": "verified",
                        "payload": {
                            "observedProfileRefs": [
                                {"classKey": "paladin", "specKey": "retribution", "itemId": "249961"}
                            ],
                        },
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "paladin", "retribution", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "249961")
        self.assertEqual(len(catalog_item.get("variants") or []), 1)
        self.assertNotIn("itemStats", catalog_item)
        self.assertNotIn("statSummary", catalog_item)
        self.assertEqual(catalog_item["statDisplayStatus"], "pending_current_variant")

    def test_websim_gear_keeps_distinct_observed_bonus_variants_at_same_item_level(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250144",
                {
                    "id": 250144,
                    "name": "烬翼羽毛",
                    "inventory_type": {"type": "TRINKET", "name": "饰品"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "敏捷"}, "value": 18}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250144.jpg"}]},
                fallback_name="烬翼羽毛",
                english_payload={"name": "Emberwing Feather", "inventory_type": {"name": "Trinket"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-shaman-elemental-trinket1-250144",
                    "itemId": "250144",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed shaman elemental",
                    "seasonRevision": "season-test",
                    "payload": {"classKeys": ["shaman"], "specKeys": ["elemental"]},
                },
            )
            for index, bonus_id in enumerate(("13440/40/12699/13654", "13440/6652/12699/13654"), start=1):
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-shaman-elemental-trinket1-250144-{index}",
                        "itemId": "250144",
                        "slot": "trinket1",
                        "variantKey": f"observed-298-{index}",
                        "label": "Observed 298",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 298,
                        "simcOptions": {"bonus_id": bonus_id},
                        "status": "verified",
                        "payload": {"classKeys": ["shaman"], "specKeys": ["elemental"]},
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "shaman", "elemental", compact=True)
        finally:
            conn.close()

        trinket_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "trinket1")
        catalog_item = next(item for item in trinket_group["items"] if item["itemId"] == "250144")
        variant_bonus_ids = {
            (variant.get("simcOptions") or {}).get("bonus_id")
            for variant in catalog_item.get("variants") or []
        }
        self.assertEqual(variant_bonus_ids, {"13440/40/12699/13654", "13440/6652/12699/13654"})

    def test_websim_gear_uses_variant_stats_for_observed_catalog_candidate(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249979",
                {
                    "id": 249979,
                    "name": "原始核心的轨迹头盔",
                    "inventory_type": {"type": "HEAD", "name": "头部"},
                    "item_class": {"id": 4, "name": "护甲"},
                    "item_subclass": {"id": 3, "name": "锁甲"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "智力"}, "value": 9}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-249979.jpg"}]},
                fallback_name="原始核心的轨迹头盔",
                english_payload={"name": "Locus of the Primal Core", "inventory_type": {"name": "Head"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-shaman-elemental-head-249979",
                    "itemId": "249979",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed shaman elemental",
                    "seasonRevision": "season-test",
                    "payload": {"classKeys": ["shaman"], "specKeys": ["elemental"]},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-shaman-elemental-head-249979",
                    "itemId": "249979",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {
                        "bonus_id": "6652/13335/41/13338/13575/12806/13534",
                        "gem_id": "240906",
                        "enchant_id": "8017",
                    },
                    "status": "verified",
                    "payload": {
                        "classKeys": ["shaman"],
                        "specKeys": ["elemental"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [
                            {"key": "agiint", "label": "敏捷 or 智力", "value": 124},
                            {"key": "stamina", "label": "耐力", "value": 1768},
                            {"key": "haste_rating", "label": "急速", "value": 55},
                            {"key": "mastery_rating", "label": "精通", "value": 109},
                            {"key": "leech_rating", "label": "吸血", "value": 71},
                        ],
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "shaman", "elemental", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "249979")
        self.assertEqual(catalog_item["statDisplayStatus"], "verified_variant")
        self.assertEqual(catalog_item["statSummary"], "敏捷 or 智力 124；耐力 1768；急速 55；精通 109；吸血 71")
        self.assertNotIn("智力 9", catalog_item["statSummary"])
        self.assertEqual(catalog_item["itemStats"][0]["value"], 124)

    def test_websim_gear_keeps_observed_simc_failure_reason_without_metadata_stat_source(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "268291",
                {
                    "id": 268291,
                    "name": "腐沼的孢子之心",
                    "inventory_type": {"type": "NECK", "name": "颈部"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [
                            {"type": {"type": "STAMINA", "name": "耐力"}, "value": 42},
                            {"type": {"type": "MASTERY_RATING", "name": "精通"}, "value": 21},
                        ]
                    },
                },
                {"assets": [{"value": "https://render.example/item-268291.jpg"}]},
                fallback_name="腐沼的孢子之心",
                english_payload={"name": "Sporeheart of the Dredge", "inventory_type": {"name": "Neck"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-mage-frost-neck-268291",
                    "itemId": "268291",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed mage frost",
                    "seasonRevision": "season-test",
                    "payload": {"classKeys": ["mage"], "specKeys": ["frost"]},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-neck-268291",
                    "itemId": "268291",
                    "slot": "neck",
                    "variantKey": "observed-298",
                    "label": "Observed 298",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "6652/13335/13654"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "simcStatStatus": "failed",
                        "simcStatFailureKind": "item_resolution",
                        "simcStatError": "Item 'item_268291' failed",
                        "simcStatCheckedAt": "2026-06-22T17:47:36+00:00",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        neck_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "neck")
        candidate = next(item for item in neck_group["items"] if item["itemId"] == "268291")
        self.assertEqual(candidate["statDisplayStatus"], "pending_current_variant")
        self.assertNotIn("statSource", candidate)
        self.assertNotIn("statSummary", candidate)
        self.assertNotIn("itemStats", candidate)
        self.assertEqual(candidate["simcStatStatus"], "failed")
        self.assertEqual(candidate["simcStatFailureKind"], "item_resolution")
        self.assertNotIn("simcStatError", candidate)
        self.assertIn("SimulationCraft item stats", candidate["blockers"])

    def test_websim_gear_does_not_synthesize_stats_from_same_item_level_variant_at_request_time(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249380",
                {
                    "id": 249380,
                    "name": "仇恨束缚腰链",
                    "inventory_type": {"type": "WAIST", "name": "腰部"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 4, "name": "Plate"},
                    "quality": {"name": "史诗"},
                    "preview_item": {
                        "stats": [{"type": {"type": "STAMINA", "name": "耐力"}, "value": 42}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-249380.jpg"}]},
                fallback_name="Hatebound Waistband",
                english_payload={"name": "Hatebound Waistband", "inventory_type": {"name": "Waist"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-dk-blood-waist-249380",
                    "itemId": "249380",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed deathknight blood",
                    "seasonRevision": "season-test",
                    "payload": {"classKeys": ["deathknight"], "specKeys": ["blood"]},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-dk-blood-waist-249380-missing",
                    "itemId": "249380",
                    "slot": "waist",
                    "variantKey": "observed-289-missing",
                    "label": "Observed 289 A",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652/12667/13577/13335/12806"},
                    "status": "verified",
                    "payload": {"classKeys": ["deathknight"], "specKeys": ["blood"]},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-dk-blood-waist-249380-verified",
                    "itemId": "249380",
                    "slot": "waist",
                    "variantKey": "observed-289-verified",
                    "label": "Observed 289 B",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652/13577/13335/13534/12806", "gem_id": "240908"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "statSourceDetail": "SimulationCraft JSON gear output",
                        "itemStats": [
                            {"key": "stamina", "label": "耐力", "value": 1326},
                            {"key": "crit_rating", "label": "暴击", "value": 37},
                            {"key": "mastery_rating", "label": "精通", "value": 87},
                        ],
                        "statSummary": "耐力 1326；暴击 37；精通 87",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "deathknight", "blood", compact=True)
        finally:
            conn.close()

        waist_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "waist")
        candidate = next(item for item in waist_group["items"] if item["itemId"] == "249380")
        self.assertEqual(candidate["variantKey"], "observed-289-missing")
        self.assertEqual(candidate["statDisplayStatus"], "pending_current_variant")
        self.assertNotIn("statSource", candidate)
        self.assertNotIn("statSummary", candidate)
        self.assertNotIn("itemStats", candidate)
        self.assertIn("SimulationCraft item stats", candidate.get("blockers") or [])

    def test_websim_gear_prefers_observed_variant_with_verified_stats(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250144",
                {
                    "id": 250144,
                    "name": "烬翼羽毛",
                    "inventory_type": {"type": "TRINKET", "name": "饰品"},
                    "quality": {"name": "史诗"},
                    "preview_item": {"stats": [{"type": {"type": "AGILITY", "name": "敏捷"}, "value": 1}]},
                },
                {"assets": [{"value": "https://render.example/item-250144.jpg"}]},
                fallback_name="烬翼羽毛",
                english_payload={"name": "Emberwing Feather", "inventory_type": {"name": "Trinket"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-shaman-elemental-trinket1-250144",
                    "itemId": "250144",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed shaman elemental",
                    "seasonRevision": "season-test",
                    "payload": {"classKeys": ["shaman"], "specKeys": ["elemental"]},
                },
            )
            for variant_id, bonus_id, payload in (
                ("observed-z-no-stats", "13440/6652/12699/13654", {"classKeys": ["shaman"], "specKeys": ["elemental"]}),
                (
                    "observed-a-with-stats",
                    "13440/40/12699/13654",
                    {
                        "classKeys": ["shaman"],
                        "specKeys": ["elemental"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [
                            {"key": "agiint", "label": "敏捷 or 智力", "value": 128},
                            {"key": "avoidance_rating", "label": "闪避", "value": 55},
                        ],
                        "statSummary": "+128 [敏捷 or 智力]；+55闪避",
                    },
                ),
            ):
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": variant_id,
                        "itemId": "250144",
                        "slot": "trinket1",
                        "variantKey": variant_id,
                        "label": "Observed 298",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 298,
                        "simcOptions": {"bonus_id": bonus_id},
                        "status": "verified",
                        "payload": payload,
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "shaman", "elemental", compact=True)
        finally:
            conn.close()

        trinket_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "trinket1")
        catalog_item = next(item for item in trinket_group["items"] if item["itemId"] == "250144")
        self.assertEqual(catalog_item["bonus_id"], "13440/40/12699/13654")
        self.assertEqual(catalog_item["statDisplayStatus"], "verified_variant")
        self.assertEqual(catalog_item["statSummary"], "+128 [敏捷 or 智力]；+55闪避")

    def test_gear_catalog_health_includes_observed_variant_stat_coverage(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for item_id, payload in (
                (
                    "249979",
                    {
                        "classKeys": ["shaman"],
                        "specKeys": ["elemental"],
                        "statSource": "simulationcraft",
                        "itemStats": [{"key": "agiint", "label": "敏捷 or 智力", "value": 124}],
                        "statSummary": "敏捷 or 智力 124",
                    },
                ),
                ("268288", {"classKeys": ["shaman"], "specKeys": ["elemental"]}),
            ):
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"observed-shaman-elemental-head-{item_id}",
                        "itemId": item_id,
                        "slot": "head",
                        "variantKey": f"observed-{item_id}",
                        "label": "Observed 289",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652"},
                        "status": "verified",
                        "payload": payload,
                    },
                )
            state = self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"})
            self.websim_payload.set_sync_state(conn, "gearCatalog", state)
            health = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        coverage = state["observedStatCoverage"]
        self.assertEqual(coverage["totalObservedVariantCount"], 2)
        self.assertEqual(coverage["statObservedVariantCount"], 1)
        self.assertEqual(coverage["missingStatObservedVariantCount"], 1)
        self.assertEqual(coverage["coverage"]["percent"], 50.0)
        self.assertEqual(coverage["missingExamples"][0]["itemId"], "268288")
        self.assertEqual(health["details"]["observedStatCoverage"], coverage)
        self.assertIn(
            "1 observed gear variants missing SimulationCraft item stats",
            state["simulationReadiness"]["blockers"],
        )
        self.assertIn(
            "1 observed gear variants missing SimulationCraft item stats",
            health["details"]["simulationReadiness"]["blockers"],
        )

    def test_websim_gear_reuses_portable_observed_candidates_across_specs(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            raiderio = {
                "sourceStatus": "verified",
                "checkedAt": "2026-06-20T00:00:00+00:00",
                "region": "cn",
                "seasonSlug": "season-mn-1",
                "specs": {
                    "mage:frost": {
                        "observedGear": [
                            {
                                "slot": "neck",
                                "name": "Observed Pendant",
                                "itemId": 251000,
                                "itemLevel": 707,
                                "bonuses": [11111],
                                "sourceName": "Raider.IO CN profile gear",
                            },
                            {
                                "slot": "finger1",
                                "name": "Observed Band",
                                "itemId": 251001,
                                "itemLevel": 707,
                                "bonuses": [22222],
                                "sourceName": "Raider.IO CN profile gear",
                            },
                            {
                                "slot": "trinket1",
                                "name": "Observed Charm",
                                "itemId": 251002,
                                "itemLevel": 707,
                                "bonuses": [33333],
                                "sourceName": "Raider.IO CN profile gear",
                            },
                            {
                                "slot": "head",
                                "name": "Mage Only Hood",
                                "itemId": 251003,
                                "itemLevel": 707,
                                "bonuses": [44444],
                                "sourceName": "Raider.IO CN profile gear",
                            },
                        ],
                    },
                },
            }
            self.websim_payload.sync_observed_gear_variants(conn, raiderio, {"seasonRevision": "season-test"})
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "druid", "restoration")
        finally:
            conn.close()

        groups = {group["slot"]: group for group in payload["replacementCandidates"]}
        self.assertIn("251000", [item["itemId"] for item in groups["neck"]["items"]])
        self.assertIn("251001", [item["itemId"] for item in groups["finger1"]["items"]])
        self.assertIn("251001", [item["itemId"] for item in groups["finger2"]["items"]])
        self.assertIn("251002", [item["itemId"] for item in groups["trinket1"]["items"]])
        self.assertIn("251002", [item["itemId"] for item in groups["trinket2"]["items"]])
        self.assertNotIn("251003", [item["itemId"] for item in groups["head"]["items"]])

    def test_observed_profile_variant_stays_partial_without_deterministic_simc_options(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250778",
                {
                    "id": 250778,
                    "name": "观测护腕",
                    "inventory_type": {"type": "WRIST", "name": "手腕"},
                    "quality": {"name": "史诗"},
                },
                fallback_name="Observed Bracers",
                english_payload={"name": "Observed Bracers", "inventory_type": {"name": "Wrist"}},
                locale="zh_CN",
            )
            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                {
                    "sourceStatus": "verified",
                    "checkedAt": "2026-06-20T00:00:00+00:00",
                    "specs": {
                        "mage:frost": {
                            "observedGear": [
                                {
                                    "slot": "wrist",
                                    "name": "Observed Bracers",
                                    "itemId": 250778,
                                    "itemLevel": 707,
                                    "bonuses": [],
                                    "gems": [],
                                    "enchants": [],
                                }
                            ],
                        }
                    },
                },
                {"seasonRevision": "season-test"},
            )
            variants = self.websim_payload.gear_catalog_variants_by_item(conn)
        finally:
            conn.close()

        self.assertEqual(counts["observedVariants"], 1)
        self.assertEqual(counts["verifiedObservedVariants"], 0)
        variant = variants["250778"][0]
        self.assertEqual(variant["status"], "partial")
        self.assertIn("missing deterministic SimC variant preset", variant["blockers"])

    def test_observed_profile_item_metadata_remains_source_reference_without_blizzard_metadata(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.sync_observed_gear_variants(
                conn,
                {
                    "sourceStatus": "verified",
                    "checkedAt": "2026-06-20T00:00:00+00:00",
                    "specs": {
                        "mage:frost": {
                            "observedGear": [
                                {
                                    "slot": "head",
                                    "name": "Observed Only Hood",
                                    "itemId": 250779,
                                    "itemLevel": 707,
                                    "bonuses": [12345],
                                    "sourceName": "Raider.IO CN profile gear",
                                }
                            ],
                        }
                    },
                },
                {"seasonRevision": "season-test"},
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
        finally:
            conn.close()

        head_group = next(group for group in payload["slotGroups"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250779")
        self.assertFalse(catalog_item["simcReady"])
        self.assertEqual(catalog_item["variantStatus"], "partial")
        self.assertEqual(catalog_item["metadataStatus"], "source_reference")
        self.assertEqual(catalog_item["metadataSource"], "raiderio_observed_profile")
        self.assertIn("verified Battle.net metadata", catalog_item["blockers"])
        self.assertIn("Battle.net item stats", catalog_item["blockers"])

    def test_gear_catalog_health_payload_includes_slot_source_and_observed_variant_coverage(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Observed Hood",
                    "inventory_type": {"name": "Head"},
                    "quality": {"name": "Epic"},
                },
                fallback_name="Observed Hood",
                english_payload={"name": "Observed Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-250777",
                    "itemId": "250777",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO CN observed mage frost",
                    "seasonRevision": "season-test",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-250777-head",
                    "itemId": "250777",
                    "slot": "head",
                    "variantKey": "observed-707",
                    "label": "Observed 707",
                    "sourceType": "observed_profile",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(payload["details"]["observedVariantCount"], 1)
        self.assertEqual(payload["details"]["slotCoverage"]["coveredSlotCount"], 1)
        self.assertIn("head", payload["details"]["slotCoverage"]["coveredSlots"])
        self.assertEqual(payload["details"]["sourceCoverage"]["observed_profile"], 1)

    def test_gear_catalog_health_payload_reports_trusted_source_gaps(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-250880",
                    "itemId": "250880",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed mage frost",
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "simc-source-250880",
                    "itemId": "250880",
                    "sourceType": "simc_preset",
                    "sourceLabel": "SimulationCraft preset: MID1_Mage_Frost",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-250880-back",
                    "itemId": "250880",
                    "slot": "back",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                    "payload": {
                        "displayName": "缺来源披风",
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-source-250881",
                    "itemId": "250881",
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "instanceId": "1209",
                    "encounterId": "1757",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "official-250881-back",
                    "itemId": "250881",
                    "slot": "back",
                    "variantKey": "mythic-plus",
                    "label": "Mythic+",
                    "sourceType": "dungeon",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                    "payload": {
                        "displayName": "已补来源披风",
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        source_gap = payload["details"]["sourceGapCoverage"]
        self.assertEqual(source_gap["sourcePendingItemCount"], 1)
        self.assertEqual(source_gap["sourcePendingVariantCount"], 1)
        self.assertEqual(source_gap["trustedSourceItemCount"], 1)
        self.assertEqual(source_gap["examples"][0]["itemId"], "250880")
        self.assertEqual(source_gap["examples"][0]["sourceTypes"], ["observed_profile", "simc_preset"])
        self.assertIn("1 gear catalog items missing trusted drop source", payload["blockers"])
        self.assertIn(
            "1 gear catalog items missing trusted drop source",
            payload["details"]["dataReadiness"]["blockers"],
        )
        self.assertEqual(payload["details"]["dataReadiness"]["sourceStatus"], "partial")
        self.assertEqual(payload["details"]["dataReadiness"]["seasonSourceStatus"], "verified")

    def test_current_season_payload_includes_confirmed_mplus_and_raid_allowlists(self):
        season = self.websim_payload.current_season_payload()

        dungeon_names = [item["name"] for item in season["dungeons"]]
        raid_names = [item["name"] for item in season["raids"]]

        self.assertEqual(
            dungeon_names,
            [
                "Magisters' Terrace",
                "Maisara Caverns",
                "Nexus-Point Xenas",
                "Windrunner Spire",
                "Algeth'ar Academy",
                "Pit of Saron",
                "Seat of the Triumvirate",
                "Skyreach",
            ],
        )
        self.assertEqual(
            raid_names,
            ["The Voidspire", "The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertNotIn("Manaforge Omega", raid_names)

    def test_current_season_raid_refs_filters_allowlist_and_never_uses_last_raid_fallback(self):
        refs = self.websim_payload.current_season_raid_refs(
            {
                "raids": [
                    {"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"},
                    {"id": "1401", "instanceId": "1401", "name": "The Dreamrift", "category": "Raid"},
                    {"id": "1402", "instanceId": "1402", "name": "March on Quel'Danas", "category": "Raid"},
                    {"id": "1403", "instanceId": "1403", "name": "Sporefall", "category": "Raid"},
                    {"id": "1302", "instanceId": "1302", "name": "Manaforge Omega", "category": "Raid"},
                ]
            }
        )

        self.assertEqual(
            [item["name"] for item in refs],
            ["The Voidspire", "The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertNotIn("Manaforge Omega", [item["name"] for item in refs])

        stale_refs = self.websim_payload.current_season_raid_refs(
            {
                "raids": [
                    {"id": "1200", "instanceId": "1200", "name": "Old Vault", "category": "Raid"},
                    {"id": "1302", "instanceId": "1302", "name": "Manaforge Omega", "category": "Raid"},
                ]
            }
        )
        self.assertEqual(stale_refs, [])

    def test_current_season_raid_refs_accepts_localized_current_season_names(self):
        refs = self.websim_payload.current_season_raid_refs(
            {
                "raids": [
                    {"id": "1307", "instanceId": "1307", "name": "虚影尖塔", "category": "Raid"},
                    {"id": "1314", "instanceId": "1314", "name": "梦境裂隙", "category": "Raid"},
                    {"id": "1308", "instanceId": "1308", "name": "进军奎尔丹纳斯", "category": "Raid"},
                    {"id": "1305", "instanceId": "1305", "name": "孢陨幽境", "category": "Raid"},
                    {"id": "1302", "instanceId": "1302", "name": "法力熔炉：欧米伽", "category": "Raid"},
                ]
            }
        )

        self.assertEqual(
            [item["name"] for item in refs],
            ["The Voidspire", "The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertEqual([item["instanceId"] for item in refs], ["1307", "1314", "1308", "1305"])
        self.assertEqual(refs[0]["localizedName"], "虚影尖塔")
        self.assertNotIn("法力熔炉：欧米伽", [item.get("localizedName") or item["name"] for item in refs])

    def test_current_season_raid_pool_allows_extra_rows_when_expected_refs_are_complete(self):
        status = self.websim_payload.current_season_raid_pool_status(
            {
                "raids": [
                    {"id": "1278", "instanceId": "1278", "name": "卡兹阿加", "category": "Raid"},
                    {"id": "1302", "instanceId": "1302", "name": "法力熔炉：欧米伽", "category": "Raid"},
                    {"id": "1307", "instanceId": "1307", "name": "虚影尖塔", "category": "Raid"},
                    {"id": "1314", "instanceId": "1314", "name": "梦境裂隙", "category": "Raid"},
                    {"id": "1308", "instanceId": "1308", "name": "进军奎尔丹纳斯", "category": "Raid"},
                    {"id": "1305", "instanceId": "1305", "name": "孢陨幽境", "category": "Raid"},
                ]
            }
        )

        self.assertEqual(status["blockers"], [])
        self.assertEqual([item["instanceId"] for item in status["refs"]], ["1307", "1314", "1308", "1305"])
        self.assertEqual([item["name"] for item in status["staleRefs"]], ["卡兹阿加", "法力熔炉：欧米伽"])

    def test_selected_journal_instance_refs_prefers_localized_current_season_before_last_expansion(self):
        original_blizzard_get = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)

        calls = []

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            calls.append((path, locale))
            if path == "/data/wow/journal-expansion/index":
                return {
                    "expansions": [
                        {"id": 505, "name": "本赛季"},
                        {"id": 514, "name": "地心之战"},
                    ]
                }
            if path == "/data/wow/journal-expansion/505":
                return {
                    "name": "本赛季",
                    "raids": [{"id": 1307, "name": "虚影尖塔"}],
                    "dungeons": [],
                }
            if path == "/data/wow/journal-expansion/514":
                return {
                    "name": "地心之战",
                    "raids": [{"id": 1302, "name": "法力熔炉：欧米伽"}],
                    "dungeons": [],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        self.websim_payload.blizzard_get = fake_blizzard_get

        refs, selected_name = self.websim_payload.selected_journal_instance_refs("token", "us", "zh_CN")

        self.assertEqual(selected_name, "本赛季")
        self.assertEqual(refs, [({"id": 1307, "name": "虚影尖塔"}, "Raid")])
        self.assertNotIn(("/data/wow/journal-expansion/514", "zh_CN"), calls)

    def test_active_season_payload_normalizes_stale_cached_raid_pool(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="至暗之夜 Season 1",
                dungeons=[
                    {
                        "id": "557",
                        "dungeonId": "557",
                        "instanceId": "557",
                        "name": "风行者之塔",
                        "shortName": "风行者之塔",
                        "timerSeconds": 0,
                    }
                ],
                raids=[
                    {"id": "1302", "instanceId": "1302", "name": "Manaforge Omega", "category": "Raid"}
                ],
            )
            self.websim_payload.save_active_season_payload(conn, season)

            payload = self.websim_payload.get_active_season_payload(conn)
        finally:
            conn.close()

        raid_names = [item["name"] for item in payload["raids"]]
        self.assertEqual(
            raid_names,
            ["The Voidspire", "The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertNotIn("Manaforge Omega", raid_names)
        self.assertIn(
            self.websim_payload.CURRENT_SEASON_RAID_POOL_MISSING_BLOCKER,
            payload["raidPoolStatus"]["blockers"],
        )
        self.assertIn(
            self.websim_payload.CURRENT_SEASON_RAID_POOL_STALE_BLOCKER,
            payload["raidPoolStatus"]["blockers"],
        )
        self.assertEqual(payload["raidPoolStatus"]["staleRefs"][0]["name"], "Manaforge Omega")

    def test_websim_gear_payload_exposes_lightweight_catalog_health_summary(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-250890",
                    "itemId": "250890",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed mage frost",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-250890-back",
                    "itemId": "250890",
                    "slot": "back",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                    "payload": {
                        "displayName": "缺来源属性披风",
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-source-250891",
                    "itemId": "250891",
                    "sourceType": "dungeon",
                    "sourceLabel": "兰吉特 - 通天峰",
                    "instanceId": "1209",
                    "encounterId": "1757",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "official-250891-back",
                    "itemId": "250891",
                    "slot": "back",
                    "variantKey": "mythic-plus",
                    "label": "Mythic+",
                    "sourceType": "dungeon",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                    "payload": {
                        "displayName": "变体待补披风",
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "socket-missing-gem-metadata",
                    "type": "socket",
                    "name": "Quick Gem",
                    "applicableSlots": ["finger1"],
                    "simcOptions": {"gem_id": "240983", "gem_ilevel": "707"},
                    "status": "verified",
                    "payload": {
                        "source": "observed_variant",
                        "displayName": "Quick Gem",
                        "gemItemId": "240983",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        summary = payload["catalogHealthSummary"]
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["sourcePendingItemCount"], 1)
        self.assertEqual(summary["sourcePendingVariantCount"], 1)
        self.assertEqual(summary["missingStatObservedVariantCount"], 1)
        self.assertEqual(summary["socketMissingMetadataCount"], 1)
        self.assertEqual(summary["partialVariantCount"], 1)
        self.assertIn("1 gear catalog items missing trusted drop source", summary["blockers"])
        self.assertEqual(summary["sourcePendingExamples"][0]["itemId"], "250890")
        self.assertEqual(summary["sourcePendingExamples"][0]["sourcePendingVariantCount"], 1)
        self.assertEqual(summary["partialVariantExamples"][0]["itemId"], "250891")
        self.assertEqual(summary["partialVariantExamples"][0]["slot"], "back")
        self.assertEqual(summary["partialVariantExamples"][0]["sourceType"], "dungeon")
        self.assertEqual(summary["partialVariantExamples"][0]["blockers"], ["missing deterministic SimC variant preset"])

    def test_catalog_variant_display_preserves_all_db_item_level_variants(self):
        variants = [
            {"key": "champion-263", "difficultyKey": "champion", "itemLevel": 263, "status": "verified"},
            {"key": "hero-276", "difficultyKey": "hero", "itemLevel": 276, "status": "verified"},
            {"key": "myth-289", "difficultyKey": "myth", "itemLevel": 289, "status": "verified"},
            {"key": "void-298", "difficultyKey": "void_ascension", "itemLevel": 298, "status": "verified"},
        ]
        collapsed = self.websim_payload.collapse_catalog_variants_for_display(variants)

        self.assertEqual(
            sorted(variant["itemLevel"] for variant in collapsed),
            [263, 276, 289, 298],
        )

    def test_catalog_variant_display_hides_placeholder_when_item_level_variants_exist(self):
        variants = [
            {"key": "myth-289", "difficultyKey": "myth", "itemLevel": 289, "status": "verified"},
            {"key": "hero-276", "difficultyKey": "hero", "itemLevel": 276, "status": "verified"},
            {"key": "champion-263", "difficultyKey": "champion", "itemLevel": 263, "status": "verified"},
            {
                "key": "needs-variant",
                "difficultyKey": "needs-variant",
                "itemLevel": 0,
                "status": "partial",
                "blockers": ["missing deterministic SimC variant preset"],
            },
        ]

        collapsed = self.websim_payload.collapse_catalog_variants_for_display(variants)

        self.assertEqual([variant["key"] for variant in collapsed], ["myth-289", "hero-276", "champion-263"])

    def test_catalog_variant_display_keeps_placeholder_when_it_is_only_variant(self):
        variants = [
            {
                "key": "needs-variant",
                "difficultyKey": "needs-variant",
                "itemLevel": 0,
                "status": "partial",
                "blockers": ["missing deterministic SimC variant preset"],
            },
        ]

        collapsed = self.websim_payload.collapse_catalog_variants_for_display(variants)

        self.assertEqual([variant["key"] for variant in collapsed], ["needs-variant"])

    def test_talent_catalog_health_blocks_missing_local_talent_data(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            payload = self.websim_payload.talent_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["details"]["talentCount"], 0)
        self.assertEqual(payload["details"]["catalogContract"]["schemaRevision"], "websim-talent-catalog-v1")
        self.assertEqual(payload["details"]["catalogContract"]["coverage"], {"covered": 0, "total": 0, "percent": 0})
        self.assertIn("talent catalog has no local talent nodes", payload["blockers"])

    def test_raiderio_observed_only_catalog_stays_partial_until_item_metadata_is_verified(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            raiderio = {
                "sourceStatus": "synced",
                "checkedAt": "2026-06-21T00:00:00+00:00",
                "region": "cn",
                "seasonSlug": "season-mn-1",
                "specs": {
                    "monk:mistweaver": {
                        "observedGear": [
                            {
                                "slot": "head",
                                "name": "Fearsome Visage of Ra-den's Chosen",
                                "itemId": 250015,
                                "itemLevel": 289,
                                "quality": "Epic",
                                "icon": "inv_helm_leather_raidmonk_s_01",
                                "bonuses": [6652, 13335, 13338, 13575, 12806, 13534],
                                "gems": [240890],
                                "enchants": [8017],
                                "sourceName": "Raider.IO CN profile gear",
                            },
                            {
                                "slot": "mainhand",
                                "name": "Weight of Command",
                                "itemId": 249293,
                                "itemLevel": 298,
                                "quality": "Epic",
                                "icon": "inv_mace_2h_artifactdoomhammer_d_06",
                                "bonuses": [6652, 13335, 13654],
                                "enchants": [8039, 8052],
                                "sourceName": "Raider.IO CN profile gear",
                            },
                        ],
                    }
                },
            }
            counts = self.websim_payload.sync_observed_gear_variants(
                conn,
                raiderio,
                {"seasonRevision": "season-mn-1"},
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(counts["verifiedObservedVariants"], 0)
        self.assertEqual(counts["partialObservedVariants"], 2)
        self.assertEqual(payload["status"], "partial")
        metadata = payload["details"]["itemMetadata"]
        self.assertEqual(metadata["itemCount"], 2)
        self.assertEqual(metadata["verifiedItemCount"], 0)
        self.assertEqual(metadata["missingVerifiedItemCount"], 2)
        self.assertEqual(metadata["missingStatItemCount"], 2)
        self.assertEqual(metadata["missingArmorTypeItemCount"], 1)
        self.assertEqual(metadata["missingWeaponTypeItemCount"], 1)
        self.assertEqual(metadata["socketCapableItemCount"], 1)
        self.assertIn("2 catalog items missing verified Battle.net metadata", payload["blockers"])

    def test_official_item_metadata_audit_records_stats_types_set_and_socket_support(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Fearsome Visage of Ra-den's Chosen",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "item_set": {"name": "Ra-den's Chosen"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 1234}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/head.jpg"}]},
                fallback_name="Fearsome Visage of Ra-den's Chosen",
                english_payload={"name": "Fearsome Visage of Ra-den's Chosen", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249293",
                {
                    "id": 249293,
                    "name": "Weight of Command",
                    "inventory_type": {"type": "WEAPON", "name": "Weapon"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 4, "name": "Mace"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 456}],
                    },
                },
                {"assets": [{"value": "https://render.example/mainhand.jpg"}]},
                fallback_name="Weight of Command",
                english_payload={"name": "Weight of Command", "inventory_type": {"name": "Weapon"}},
                locale="en_US",
            )
            for item_id, slot in (("250015", "head"), ("249293", "main_hand")):
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "raid",
                        "sourceLabel": "Ra-den",
                        "seasonRevision": "season-mn-1",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}",
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": "observed-289",
                        "label": "Observed 289",
                        "sourceType": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652"},
                        "status": "verified",
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
            gear = self.websim_payload.get_websim_gear(conn, "monk", "mistweaver", compact=True)
        finally:
            conn.close()

        metadata = payload["details"]["itemMetadata"]
        self.assertEqual(metadata["verifiedItemCount"], 2)
        self.assertEqual(metadata["missingVerifiedItemCount"], 0)
        self.assertEqual(metadata["missingStatItemCount"], 0)
        self.assertEqual(metadata["armorTypeCoverage"]["Leather"], 1)
        self.assertEqual(metadata["weaponTypeCoverage"]["One-Handed Mace"], 1)
        self.assertEqual(metadata["setItemCount"], 1)
        self.assertEqual(metadata["socketCapableItemCount"], 1)
        head_group = next(group for group in gear["replacementCandidates"] if group["slot"] == "head")
        head = next(item for item in head_group["items"] if item["itemId"] == "250015")
        self.assertEqual(head["armorType"], "Leather")
        self.assertEqual(head["itemSetName"], "Ra-den's Chosen")
        self.assertTrue(head["supportsSocket"])
        weapon_group = next(group for group in gear["replacementCandidates"] if group["slot"] == "main_hand")
        weapon = next(item for item in weapon_group["items"] if item["itemId"] == "249293")
        self.assertEqual(weapon["weaponType"], "One-Handed Mace")

    def test_item_type_metadata_normalizes_warglaive_and_holdable_offhand(self):
        warglaive = self.websim_payload.item_type_metadata_from_payload(
            {
                "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                "item_class": {"id": 2, "name": "Weapon"},
                "item_subclass": {"id": 9, "name": "Warglaives"},
            }
        )
        holdable = self.websim_payload.item_type_metadata_from_payload(
            {
                "inventory_type": {"type": "HOLDABLE", "name": "Held In Off-hand"},
                "item_class": {"id": 4, "name": "Armor"},
                "item_subclass": {"id": 0, "name": "Miscellaneous"},
            }
        )

        self.assertEqual(warglaive["weaponType"], "Warglaive")
        self.assertEqual(holdable["weaponType"], "Held In Off-hand")

    def test_weapon_type_compatibility_uses_class_weapon_proficiencies(self):
        crossbow = {
            "inventory_type": {"type": "RANGED", "name": "Ranged"},
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 18, "name": "Crossbow"},
        }
        fist_weapon = {
            "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 13, "name": "Fist Weapon"},
        }
        warglaive = {
            "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
            "item_class": {"id": 2, "name": "Weapon"},
            "item_subclass": {"id": 9, "name": "Warglaives"},
        }

        self.assertEqual(
            self.websim_payload.gear_compatibility_from_payload(crossbow, "mage", "main_hand", "frost"),
            "incompatible",
        )
        self.assertEqual(
            self.websim_payload.gear_compatibility_from_payload(crossbow, "hunter", "main_hand", "marksmanship"),
            "compatible",
        )
        self.assertEqual(
            self.websim_payload.gear_compatibility_from_payload(crossbow, "rogue", "main_hand", "outlaw"),
            "incompatible",
        )
        self.assertEqual(
            self.websim_payload.gear_compatibility_from_payload(fist_weapon, "deathknight", "main_hand", "frost"),
            "incompatible",
        )
        self.assertEqual(
            self.websim_payload.gear_compatibility_from_payload(warglaive, "demonhunter", "main_hand", "devourer"),
            "compatible",
        )

    def test_item_stat_extraction_prefers_battle_net_preview_stats_over_stale_top_level_stats(self):
        stats = self.websim_payload.extract_item_stats_from_payload(
            {
                "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 999}],
                "preview_item": {
                    "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321}],
                },
            }
        )

        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["key"], "intellect")
        self.assertEqual(stats[0]["value"], 321)

    def test_metadata_audit_accepts_official_effect_or_cosmetic_items_without_stat_array(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250401",
                {
                    "id": 250401,
                    "name": "Effect Trinket",
                    "inventory_type": {"type": "TRINKET", "name": "Trinket"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "spells": [
                            {
                                "spell": {"id": 12345, "name": "Effect Trinket"},
                                "description": "Equip: Your spells deal 999 Cosmic damage.",
                            }
                        ],
                    },
                },
                {"assets": [{"value": "https://render.example/trinket.jpg"}]},
                fallback_name="Effect Trinket",
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250402",
                {
                    "id": 250402,
                    "name": "Cosmetic Cloak",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 5, "name": "Cosmetic"},
                    "quality": {"name": "Epic"},
                    "preview_item": {"level": {"value": 1, "display_string": "Item Level 1"}},
                },
                {"assets": [{"value": "https://render.example/cloak.jpg"}]},
                fallback_name="Cosmetic Cloak",
                locale="en_US",
            )
            for item_id, slot in (("250401", "trinket1"), ("250402", "back")):
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "raid",
                        "sourceLabel": "Verified Source",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}",
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": "observed-707",
                        "label": "Observed 707",
                        "sourceType": "observed_profile",
                        "itemLevel": 707,
                        "simcOptions": {"bonus_id": "12345"},
                        "status": "verified",
                    },
                )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        metadata = payload["details"]["itemMetadata"]
        self.assertEqual(metadata["missingStatItemCount"], 0)
        self.assertNotIn("catalog items missing Battle.net item stats", " ".join(payload["blockers"]))

    def test_gear_catalog_health_blocks_stale_stats_that_conflict_with_battle_net_preview_stats(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250224",
                {
                    "id": 250224,
                    "name": "Verified Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 999}],
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321}],
                    },
                },
                {"assets": [{"value": "https://render.example/head.jpg"}]},
                fallback_name="Verified Hood",
                english_payload={"name": "Verified Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250224",
                    "itemId": "250224",
                    "sourceType": "raid",
                    "sourceLabel": "Ra-den",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250224",
                    "itemId": "250224",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
            gear = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        metadata = payload["details"]["itemMetadata"]
        self.assertEqual(metadata["statMismatchCount"], 1)
        self.assertEqual(metadata["statMismatchExamples"][0]["itemId"], "250224")
        self.assertEqual(metadata["statMismatchExamples"][0]["expectedStats"][0]["value"], 321)
        self.assertEqual(metadata["statMismatchExamples"][0]["conflictingStats"][0]["value"], 999)
        self.assertIn("1 catalog items have stat mismatches with Battle.net preview stats", payload["blockers"])
        head_group = next(group for group in gear["replacementCandidates"] if group["slot"] == "head")
        catalog_item = next(item for item in head_group["items"] if item["itemId"] == "250224")
        self.assertNotIn("itemStats", catalog_item)
        self.assertNotIn("statSummary", catalog_item)
        self.assertEqual(catalog_item["statDisplayStatus"], "pending_current_variant")

    def test_gear_catalog_health_blocks_catalog_slots_that_conflict_with_battle_net_metadata(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250222",
                {
                    "id": 250222,
                    "name": "Rift Bindings",
                    "inventory_type": {"type": "WRIST", "name": "Wrist"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321}],
                    },
                },
                {"assets": [{"value": "https://render.example/wrist.jpg"}]},
                fallback_name="Rift Bindings",
                english_payload={"name": "Rift Bindings", "inventory_type": {"name": "Wrist"}},
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250333",
                {
                    "id": 250333,
                    "name": "Verified Band",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 222}],
                    },
                },
                {"assets": [{"value": "https://render.example/ring.jpg"}]},
                fallback_name="Verified Band",
                english_payload={"name": "Verified Band", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            for item_id, slot in (("250222", "head"), ("250333", "finger2")):
                conn.execute(
                    """
                    INSERT INTO websim_loot (
                        id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                    ) VALUES (?, '1300', '9001', ?, 'Catalog Item', ?, 'Epic', 'https://render.example/item.jpg', '{}', 'now')
                    """,
                    (f"loot-{item_id}", item_id, slot),
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "dungeon",
                        "sourceLabel": "Arcane Warden",
                        "instanceId": "1300",
                        "encounterId": "9001",
                        "seasonRevision": "season-mn-1",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}",
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": "observed-289",
                        "label": "Observed 289",
                        "sourceType": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652"},
                        "status": "verified",
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        metadata = payload["details"]["itemMetadata"]
        self.assertEqual(metadata["slotMismatchCount"], 1)
        self.assertEqual(metadata["slotMismatchExamples"][0]["itemId"], "250222")
        self.assertEqual(metadata["slotMismatchExamples"][0]["expectedSlot"], "wrist")
        self.assertEqual(metadata["slotMismatchExamples"][0]["catalogSlots"], ["head"])
        self.assertIn("1 catalog items have slot mismatches with Battle.net metadata", payload["blockers"])

    def test_gear_catalog_health_uses_battle_net_payload_slot_when_stored_slot_is_stale(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250444",
                {
                    "id": 250444,
                    "name": "Verified Pendant",
                    "inventory_type": {"type": "NECK", "name": "Neck"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 222}],
                    },
                },
                {"assets": [{"value": "https://render.example/neck.jpg"}]},
                fallback_name="Verified Pendant",
                english_payload={"name": "Verified Pendant", "inventory_type": {"name": "Neck"}},
                locale="en_US",
            )
            conn.execute("UPDATE websim_items SET slot = 'trinket1' WHERE id = '250444'")
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250444",
                    "itemId": "250444",
                    "sourceType": "dungeon",
                    "sourceLabel": "Arcane Warden",
                    "instanceId": "1300",
                    "encounterId": "9001",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250444",
                    "itemId": "250444",
                    "slot": "neck",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        metadata = payload["details"]["itemMetadata"]
        self.assertEqual(metadata["slotMismatchCount"], 0)
        self.assertNotIn("catalog items have slot mismatches", " ".join(payload["blockers"]))

    def test_build_gear_catalog_sync_state_repairs_stale_stored_item_slots(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250555",
                {
                    "id": 250555,
                    "name": "Verified Bracers",
                    "inventory_type": {"type": "WRIST", "name": "Wrist"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 333}],
                    },
                },
                {"assets": [{"value": "https://render.example/wrist.jpg"}]},
                fallback_name="Verified Bracers",
                english_payload={"name": "Verified Bracers", "inventory_type": {"name": "Wrist"}},
                locale="en_US",
            )
            conn.execute("UPDATE websim_items SET slot = 'trinket1' WHERE id = '250555'")

            self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"})

            row = conn.execute("SELECT slot FROM websim_items WHERE id = '250555'").fetchone()
        finally:
            conn.close()

        self.assertEqual(row[0], "wrist")

    def test_catalog_context_allows_same_class_observed_armor_across_specs(self):
        variant = {
            "slot": "waist",
            "payload": {
                "classKeys": ["priest"],
                "specKeys": ["discipline"],
                "observedProfileRefs": [
                    {"classKey": "priest", "specKey": "discipline", "itemId": "260371"}
                ],
            },
        }

        self.assertTrue(self.websim_payload.catalog_variant_compatible(variant, "priest", "holy", "waist"))
        self.assertFalse(self.websim_payload.catalog_variant_compatible(variant, "mage", "frost", "waist"))

    def test_websim_gear_filters_shields_from_classes_that_cannot_equip_them(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "251105",
                {
                    "id": 251105,
                    "name": "Spellbreaker Shield",
                    "inventory_type": {"type": "SHIELD", "name": "Off Hand"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 6, "name": "Shield"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321}],
                    },
                },
                {"assets": [{"value": "https://render.example/shield.jpg"}]},
                fallback_name="Spellbreaker Shield",
                english_payload={"name": "Spellbreaker Shield", "inventory_type": {"name": "Off Hand"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-251105",
                    "itemId": "251105",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-251105",
                    "itemId": "251105",
                    "slot": "off_hand",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            mage_payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
            shaman_payload = self.websim_payload.get_websim_gear(conn, "shaman", "elemental")
        finally:
            conn.close()

        mage_off_hand = next(group for group in mage_payload["slotGroups"] if group["slot"] == "off_hand")
        shaman_off_hand = next(group for group in shaman_payload["slotGroups"] if group["slot"] == "off_hand")

        self.assertFalse(any(item["itemId"] == "251105" for item in mage_off_hand["items"]))
        shield = next(item for item in shaman_off_hand["items"] if item["itemId"] == "251105")
        self.assertEqual(shield["weaponType"], "Shield")
        self.assertEqual(shield["compatibility"]["status"], "compatible")
        self.assertTrue(shield["simcReady"])

    def test_websim_gear_filters_held_offhand_from_non_caster_specs(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "251094",
                {
                    "id": 251094,
                    "name": "Sleepless Heart's Signet",
                    "inventory_type": {"type": "HOLDABLE", "name": "Held In Off-hand"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "quality": {"name": "Rare"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 207}],
                    },
                },
                {"assets": [{"value": "https://render.example/offhand.jpg"}]},
                fallback_name="Sleepless Heart's Signet",
                english_payload={"name": "Sleepless Heart's Signet", "inventory_type": {"name": "Held In Off-hand"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-251094",
                    "itemId": "251094",
                    "sourceType": "dungeon",
                    "sourceLabel": "Sleepless Heart - Windrunner Spire",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-251094",
                    "itemId": "251094",
                    "slot": "off_hand",
                    "variantKey": "observed-298",
                    "label": "Observed 298",
                    "sourceType": "dungeon",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "13440/6652/12699/13654"},
                    "status": "verified",
                    "payload": {
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "itemStats": [{"key": "intellect", "label": "智力", "value": 207}],
                        "statSummary": "智力 207",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            mage_payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
            blood_payload = self.websim_payload.get_websim_gear(conn, "deathknight", "blood", compact=True)
            guardian_payload = self.websim_payload.get_websim_gear(conn, "druid", "guardian", compact=True)
        finally:
            conn.close()

        mage_off_hand = next(group for group in mage_payload["replacementCandidates"] if group["slot"] == "off_hand")
        blood_off_hand = next(group for group in blood_payload["replacementCandidates"] if group["slot"] == "off_hand")
        guardian_off_hand = next(group for group in guardian_payload["replacementCandidates"] if group["slot"] == "off_hand")

        self.assertTrue(any(item["itemId"] == "251094" for item in mage_off_hand["items"]))
        self.assertFalse(any(item["itemId"] == "251094" for item in blood_off_hand["items"]))
        self.assertFalse(any(item["itemId"] == "251094" for item in guardian_off_hand["items"]))

    def test_websim_gear_filters_main_hand_weapons_by_class_proficiency(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)

            def seed_weapon(item_id, name, inventory_type, subclass_id, subclass_name):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": inventory_type, "name": "Main Hand"},
                        "item_class": {"id": 2, "name": "Weapon"},
                        "item_subclass": {"id": subclass_id, "name": subclass_name},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 321}],
                        },
                    },
                    {"assets": [{"value": f"https://render.example/{item_id}.jpg"}]},
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Main Hand"}},
                    locale="en_US",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "dungeon",
                        "sourceLabel": "Weapon Boss - Test Dungeon",
                        "seasonRevision": "season-mn-1",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}",
                        "itemId": item_id,
                        "slot": "main_hand",
                        "variantKey": "observed-289",
                        "label": "Observed 289",
                        "sourceType": "dungeon",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652"},
                        "status": "verified",
                        "payload": {
                            "statDisplayStatus": "verified_variant",
                            "statSource": "simulationcraft",
                            "itemStats": [{"key": "agility", "label": "敏捷", "value": 321}],
                            "statSummary": "敏捷 321",
                        },
                    },
                )

            seed_weapon("258412", "Shaper's Crossbow", "RANGED", 18, "Crossbow")
            seed_weapon("258050", "High Sage's Arcane Fist", "WEAPON", 13, "Fist Weapon")
            seed_weapon("258051", "Spellbreaker's Warglaive", "WEAPON", 9, "Warglaives")
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )

            mage_payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
            hunter_payload = self.websim_payload.get_websim_gear(conn, "hunter", "marksmanship", compact=True)
            deathknight_payload = self.websim_payload.get_websim_gear(conn, "deathknight", "frost", compact=True)
            demonhunter_payload = self.websim_payload.get_websim_gear(conn, "demonhunter", "devourer", compact=True)
        finally:
            conn.close()

        def main_hand_item_ids(payload):
            group = next(group for group in payload["replacementCandidates"] if group["slot"] == "main_hand")
            return {item["itemId"] for item in group["items"]}

        self.assertNotIn("258412", main_hand_item_ids(mage_payload))
        self.assertIn("258412", main_hand_item_ids(hunter_payload))
        self.assertNotIn("258050", main_hand_item_ids(deathknight_payload))
        self.assertIn("258051", main_hand_item_ids(demonhunter_payload))

    def test_gear_catalog_health_blocks_socket_capable_items_without_socket_mod_options(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Socketed Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 1234}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/head.jpg"}]},
                fallback_name="Socketed Visage",
                english_payload={"name": "Socketed Visage", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250015",
                    "itemId": "250015",
                    "sourceType": "raid",
                    "sourceLabel": "Ra-den",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250015",
                    "itemId": "250015",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["details"]["itemMetadata"]["socketCapableItemCount"], 1)
        self.assertEqual(payload["details"]["modOptionCoverage"]["socket"]["optionCount"], 0)
        self.assertIn("socket-capable catalog items missing socket mod options", payload["blockers"])

    def test_gear_catalog_health_blocks_socket_options_without_battle_net_gem_metadata(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Socketed Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 1234}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/head.jpg"}]},
                fallback_name="Socketed Visage",
                english_payload={"name": "Socketed Visage", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250015",
                    "itemId": "250015",
                    "sourceType": "raid",
                    "sourceLabel": "Ra-den",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250015",
                    "itemId": "250015",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652", "gem_id": "240983"},
                    "status": "verified",
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-socket-missing-metadata",
                    "type": "socket",
                    "name": "Observed gem 240983",
                    "slots": ["*"],
                    "simcOptions": {"gem_id": "240983"},
                    "status": "verified",
                    "payload": {"source": "observed_variant"},
                },
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        socket_coverage = payload["details"]["modOptionCoverage"]["socket"]
        self.assertEqual(socket_coverage["optionCount"], 1)
        self.assertEqual(socket_coverage["missingMetadataCount"], 1)
        self.assertEqual(socket_coverage["missingMetadataExamples"][0]["gemItemId"], "240983")
        self.assertIn("1 socket mod options missing Battle.net gem metadata", payload["blockers"])

    def test_gear_catalog_health_requires_metadata_for_every_gem_in_socket_option(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "240900",
                {
                    "id": 240900,
                    "name": "Quick Onyx",
                    "item_class": {"id": 3, "name": "Gem"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/gem-240900.jpg"}]},
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-socket-two-gems-partial",
                    "type": "socket",
                    "name": "Quick Onyx / Missing Gem",
                    "slots": ["finger1"],
                    "simcOptions": {"gem_id": "240900/240892"},
                    "status": "verified",
                    "payload": {
                        "source": "observed_variant",
                        "gemItemId": "240900",
                        "gemItemIds": ["240900", "240892"],
                        "gemItems": [
                            {
                                "itemId": "240900",
                                "displayName": "Quick Onyx",
                                "iconUrl": "https://render.example/gem-240900.jpg",
                                "metadataStatus": "verified",
                                "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                            }
                        ],
                        "iconUrl": "https://render.example/gem-240900.jpg",
                        "metadataStatus": "verified",
                        "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                    },
                },
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        socket_coverage = payload["details"]["modOptionCoverage"]["socket"]
        self.assertEqual(socket_coverage["missingMetadataCount"], 1)
        self.assertEqual(socket_coverage["missingMetadataExamples"][0]["gemItemId"], "240892")
        self.assertIn("1 socket mod options missing Battle.net gem metadata", payload["blockers"])

    def test_gear_catalog_health_blocks_socket_options_with_non_gem_battle_net_metadata(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Socketed Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 1234}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/head.jpg"}]},
                fallback_name="Socketed Visage",
                english_payload={"name": "Socketed Visage", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250999",
                {
                    "id": 250999,
                    "name": "Verified Helmet Not Gem",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 99}],
                    },
                },
                {"assets": [{"value": "https://render.example/not-gem.jpg"}]},
                fallback_name="Verified Helmet Not Gem",
                english_payload={"name": "Verified Helmet Not Gem", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250015",
                    "itemId": "250015",
                    "sourceType": "raid",
                    "sourceLabel": "Ra-den",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250015",
                    "itemId": "250015",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652", "gem_id": "250999"},
                    "status": "verified",
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-socket-not-gem",
                    "type": "socket",
                    "name": "Observed fake gem 250999",
                    "slots": ["*"],
                    "simcOptions": {"gem_id": "250999"},
                    "status": "verified",
                    "payload": {
                        "source": "observed_variant",
                        "gemItemId": "250999",
                        "displayName": "Verified Helmet Not Gem",
                        "iconUrl": "https://render.example/not-gem.jpg",
                        "quality": "Epic",
                        "metadataStatus": "verified",
                        "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                    },
                },
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        socket_coverage = payload["details"]["modOptionCoverage"]["socket"]
        self.assertEqual(socket_coverage["optionCount"], 1)
        self.assertEqual(socket_coverage["invalidGemMetadataCount"], 1)
        self.assertEqual(socket_coverage["invalidGemMetadataExamples"][0]["gemItemId"], "250999")
        self.assertEqual(socket_coverage["invalidGemMetadataExamples"][0]["itemClass"], "Armor")
        self.assertIn("1 socket mod options reference non-gem Battle.net item metadata", payload["blockers"])

    def test_gear_catalog_health_reports_missing_season_dungeon_loot_and_set_coverage(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[
                    {"id": "557", "dungeonId": "557", "instanceId": "557", "name": "Windrunner Spire"},
                    {"id": "560", "dungeonId": "560", "instanceId": "1301", "name": "Maisara Caverns"},
                ],
            )
            season["raids"] = [
                {"id": "1400", "instanceId": "1400", "name": "The Voidspire"},
                {"id": "1401", "instanceId": "1401", "name": "Sporefall"},
            ]
            self.websim_payload.save_active_season_payload(conn, season)
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1400', 'The Voidspire', 'Raid', '{}', 'now')
                """
            )
            for item_id, name, slot, instance_id, source_type, set_name in (
                ("250015", "Fearsome Visage", "head", "557", "dungeon", "Ra-den's Chosen"),
                ("250016", "Thunderfists", "hands", "1400", "raid", "Ra-den's Chosen"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": slot.upper(), "name": slot},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 2, "name": "Leather"},
                        "item_set": {"name": set_name},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                        },
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": slot}},
                    locale="en_US",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"source-{item_id}",
                        "itemId": item_id,
                        "sourceType": source_type,
                        "sourceLabel": "Current source",
                        "instanceId": instance_id,
                        "seasonRevision": "season-mn-1",
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"variant-{item_id}",
                        "itemId": item_id,
                        "slot": slot,
                        "variantKey": "observed-289",
                        "label": "Observed 289",
                        "sourceType": source_type,
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652"} if item_id == "250015" else {},
                        "status": "verified" if item_id == "250015" else "partial",
                        "blockers": [] if item_id == "250015" else ["missing deterministic SimC variant preset"],
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        coverage = payload["details"]["seasonSourceCoverage"]
        self.assertEqual(coverage["mythicPlus"]["expectedDungeonCount"], 2)
        self.assertEqual(coverage["mythicPlus"]["coveredDungeonCount"], 1)
        self.assertEqual(coverage["mythicPlus"]["missingDungeons"], ["Maisara Caverns"])
        self.assertEqual(coverage["raid"]["expectedInstanceCount"], 4)
        self.assertEqual(coverage["raid"]["coveredInstanceCount"], 1)
        self.assertEqual(
            coverage["raid"]["missingInstances"],
            ["The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertEqual(coverage["raid"]["sourceItemCount"], 1)
        instances = {item["name"]: item for item in coverage["instances"]}
        self.assertEqual(instances["Windrunner Spire"]["category"], "Dungeon")
        self.assertTrue(instances["Windrunner Spire"]["expected"])
        self.assertTrue(instances["Windrunner Spire"]["covered"])
        self.assertEqual(instances["Windrunner Spire"]["verifiedItemCount"], 1)
        self.assertEqual(instances["Windrunner Spire"]["partialItemCount"], 0)
        self.assertEqual(instances["Maisara Caverns"]["category"], "Dungeon")
        self.assertTrue(instances["Maisara Caverns"]["expected"])
        self.assertFalse(instances["Maisara Caverns"]["covered"])
        self.assertIn("current season dungeon missing gear loot", instances["Maisara Caverns"]["blockers"])
        self.assertEqual(instances["The Voidspire"]["category"], "Raid")
        self.assertTrue(instances["The Voidspire"]["covered"])
        self.assertEqual(instances["The Voidspire"]["verifiedItemCount"], 0)
        self.assertEqual(instances["The Voidspire"]["partialItemCount"], 1)
        self.assertIn("missing deterministic SimC variant preset", instances["The Voidspire"]["blockers"])
        self.assertEqual(instances["Sporefall"]["category"], "Raid")
        self.assertFalse(instances["Sporefall"]["covered"])
        self.assertIn("current season raid missing gear loot", instances["Sporefall"]["blockers"])
        self.assertEqual(coverage["sets"]["setItemCount"], 2)
        self.assertEqual(coverage["sets"]["setNames"], ["Ra-den's Chosen"])
        self.assertIn("1 current season dungeon missing gear loot", payload["blockers"])
        self.assertIn("3 current expansion raid missing gear loot", payload["blockers"])

    def test_gear_catalog_legacy_journal_candidates_do_not_count_as_accepted_current_sources(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[
                    {"id": "556", "dungeonId": "556", "instanceId": "278", "name": "Pit of Saron"},
                ],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('278', 'Pit of Saron', 'Dungeon', '{}', 'now')
                """
            )
            for item_id, name, status in (
                ("50228", "Accepted source-reference neck", "source_reference"),
                ("49801", "Raw journal candidate staff", "journal_candidate"),
                ("133501", "Legacy duplicate bucket staff", "excluded_legacy_bucket"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "NECK", "name": "Neck"},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 0, "name": "Miscellaneous"},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "STAMINA", "name": "Stamina"}, "value": 111}],
                        },
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Neck"}},
                    locale="en_US",
                )
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"pit-source-{item_id}",
                        "itemId": item_id,
                        "sourceType": "dungeon",
                        "sourceLabel": "Pit of Saron",
                        "instanceId": "278",
                        "seasonRevision": "season-mn-1",
                        "payload": {
                            "validationStatus": status,
                            "candidateStatus": status,
                        },
                    },
                )
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"pit-variant-{item_id}",
                        "itemId": item_id,
                        "slot": "neck",
                        "variantKey": "observed-289",
                        "label": "Observed 289",
                        "sourceType": "dungeon",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "6652"},
                        "status": "verified",
                    },
                )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
            catalog_items = self.websim_payload.get_websim_gear_catalog_items(
                conn,
                "mage",
                "frost",
                self.websim_payload.get_active_season_payload(conn),
            )
        finally:
            conn.close()

        coverage = payload["details"]["seasonSourceCoverage"]
        self.assertEqual(coverage["mythicPlus"]["sourceItemCount"], 1)
        pit_row = {item["name"]: item for item in coverage["instances"]}["Pit of Saron"]
        self.assertTrue(pit_row["covered"])
        self.assertEqual(pit_row["sourceItemCount"], 1)
        self.assertEqual(pit_row["verifiedItemCount"], 1)
        self.assertEqual([item["itemId"] for item in catalog_items], ["50228"])

    def test_sync_websim_gear_catalog_skips_inactive_reused_legacy_journal_rows(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[
                    {"id": "556", "dungeonId": "556", "instanceId": "278", "name": "Pit of Saron"},
                ],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('278', 'Pit of Saron', 'Dungeon', '{}', 'now')
                """
            )
            for item_id, name in (
                ("50228", "Accepted source-reference neck"),
                ("49801", "Raw journal candidate staff"),
                ("133501", "Legacy duplicate bucket staff"),
            ):
                conn.execute(
                    """
                    INSERT INTO websim_loot
                    (id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at)
                    VALUES (?, '278', '', ?, ?, 'neck', 'Epic', '', '{}', 'now')
                    """,
                    (f"278:{item_id}", item_id, name),
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-stale-49801",
                    "itemId": "49801",
                    "sourceType": "dungeon",
                    "sourceLabel": "Stale Pit of Saron",
                    "instanceId": "278",
                    "seasonRevision": "season-mn-1",
                    "payload": {"validationStatus": "journal_candidate"},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-49801-neck",
                    "itemId": "49801",
                    "slot": "neck",
                    "variantKey": "needs-variant",
                    "label": "难度 / 装等待补",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )

            self.websim_payload.sync_websim_gear_catalog(conn, season)

            sources = conn.execute(
                """
                SELECT item_id, payload_json
                FROM websim_gear_sources
                WHERE source_type = 'dungeon'
                ORDER BY item_id
                """
            ).fetchall()
            variants = conn.execute(
                """
                SELECT item_id, difficulty_key
                FROM websim_gear_variants
                WHERE source_type = 'dungeon'
                ORDER BY item_id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual([row[0] for row in sources], ["50228"])
        self.assertEqual(json.loads(sources[0][1])["validationStatus"], "source_reference")
        self.assertEqual([(row[0], row[1]) for row in variants], [("50228", "needs-variant")])

    def test_reused_legacy_dungeon_source_reference_item_ids_promote_current_sources(self):
        status_for = self.websim_payload.reused_legacy_dungeon_source_validation_status

        self.assertEqual(status_for("278", "50228"), "source_reference")
        self.assertEqual(status_for("278", "49801"), "journal_candidate")
        self.assertEqual(status_for("278", "133501"), "excluded_legacy_bucket")

        self.assertEqual(status_for("945", "151309"), "source_reference")
        self.assertEqual(status_for("945", "258523"), "source_discrepancy")
        self.assertEqual(status_for("945", "151301"), "journal_candidate")

        self.assertEqual(status_for("476", "252411"), "source_reference")
        self.assertEqual(status_for("476", "258046"), "source_reference")
        self.assertEqual(status_for("476", "258438"), "source_reference")
        self.assertEqual(status_for("476", "109759"), "excluded_legacy_bucket")

    def test_gear_catalog_health_does_not_count_stale_season_sources_as_current_coverage(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="18",
                season_label="season-mn-2",
                dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            )
            season["seasonRevision"] = "season-mn-2"
            season["revision"] = "season-mn-2"
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Old Season Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                fallback_name="Old Season Visage",
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "old-season-source-250015",
                    "itemId": "250015",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                    "instanceId": "1300",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "old-season-variant-250015",
                    "itemId": "250015",
                    "slot": "head",
                    "variantKey": "mythic-old",
                    "label": "Old season",
                    "sourceType": "dungeon",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        mythic_plus = payload["details"]["seasonSourceCoverage"]["mythicPlus"]
        self.assertEqual(mythic_plus["coveredDungeonCount"], 0)
        self.assertEqual(mythic_plus["missingDungeonCount"], 1)
        self.assertEqual(mythic_plus["staleSourceCount"], 1)
        self.assertEqual(mythic_plus["staleSourceExamples"][0]["seasonRevision"], "season-mn-1")
        self.assertIn("1 current season dungeon missing gear loot", payload["blockers"])

    def test_gear_catalog_health_reports_missing_expected_raid_instance_without_sources(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[
                    {"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"},
                ],
            )
            season["raids"] = [
                {"id": "1400", "instanceId": "1400", "name": "The Voidspire"},
                {"id": "1401", "instanceId": "1401", "name": "Sporefall"},
            ]
            self.websim_payload.save_active_season_payload(conn, season)
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1400', 'The Voidspire', 'Raid', '{}', 'now')
                """
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250777",
                    "itemId": "250777",
                    "sourceType": "raid",
                    "sourceLabel": "The Voidspire",
                    "instanceId": "1400",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250777",
                    "itemId": "250777",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "raid",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        coverage = payload["details"]["seasonSourceCoverage"]
        self.assertEqual(coverage["raid"]["expectedInstanceCount"], 4)
        self.assertEqual(coverage["raid"]["coveredInstanceCount"], 1)
        self.assertEqual(coverage["raid"]["missingInstanceCount"], 3)
        self.assertEqual(
            coverage["raid"]["missingInstances"],
            ["The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertIn("3 current expansion raid missing gear loot", payload["blockers"])

    def test_gear_catalog_health_reports_journal_loot_missing_from_local_cache(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="season-mn-1",
                    dungeons=[
                        {"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"},
                    ],
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1300', 'Magisters'' Terrace', 'Dungeon', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, '1300', 'Arcane Warden', ?, 'now')
                """,
                (
                    "9001",
                    json.dumps(
                        {
                            "id": 9001,
                            "name": "Arcane Warden",
                            "items": [
                                {"item": {"id": 250001, "name": "Verified Hood"}},
                                {"item": {"id": 250002, "name": "Missing Bracers"}},
                            ],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250001",
                {
                    "id": 250001,
                    "name": "Verified Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                fallback_name="Verified Hood",
                english_payload={"name": "Verified Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    '1300:9001:250001', '1300', '9001', '250001', 'Verified Hood', 'head', 'Epic',
                    'https://render.example/item-250001.jpg', '{}', 'now'
                )
                """
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250001",
                    "itemId": "250001",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                    "instanceId": "1300",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250001",
                    "itemId": "250001",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "dungeon",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        coverage = payload["details"]["seasonSourceCoverage"]
        journal_loot = coverage["journalLoot"]
        self.assertEqual(journal_loot["expectedItemCount"], 2)
        self.assertEqual(journal_loot["cachedItemCount"], 1)
        self.assertEqual(journal_loot["missingItemCount"], 1)
        self.assertEqual(journal_loot["missingExamples"][0]["itemId"], "250002")
        self.assertIn("1 Battle.net journal loot items missing from local cache", payload["blockers"])

    def test_gear_catalog_health_reports_journal_loot_missing_catalog_source(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="season-mn-1",
                    dungeons=[
                        {"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"},
                    ],
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1300', 'Magisters'' Terrace', 'Dungeon', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, '1300', 'Arcane Warden', ?, 'now')
                """,
                (
                    "9001",
                    json.dumps(
                        {
                            "id": 9001,
                            "name": "Arcane Warden",
                            "items": [
                                {"item": {"id": 250001, "name": "Catalog Hood"}},
                                {"item": {"id": 250002, "name": "Unindexed Bracers"}},
                            ],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            for item_id, name, slot in (
                ("250001", "Catalog Hood", "head"),
                ("250002", "Unindexed Bracers", "wrist"),
            ):
                conn.execute(
                    """
                    INSERT INTO websim_loot (
                        id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                    ) VALUES (?, '1300', '9001', ?, ?, ?, 'Epic', 'https://render.example/item.jpg', '{}', 'now')
                    """,
                    (f"1300:9001:{item_id}", item_id, name, slot),
                )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250001",
                {
                    "id": 250001,
                    "name": "Catalog Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-1300:9001:250001",
                    "itemId": "250001",
                    "sourceType": "dungeon",
                    "sourceLabel": "Arcane Warden - Magisters' Terrace",
                    "instanceId": "1300",
                    "encounterId": "9001",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250001",
                    "itemId": "250001",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "dungeon",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        journal_loot = payload["details"]["seasonSourceCoverage"]["journalLoot"]
        self.assertEqual(journal_loot["expectedItemCount"], 2)
        self.assertEqual(journal_loot["cachedItemCount"], 2)
        self.assertEqual(journal_loot["catalogSourceItemCount"], 1)
        self.assertEqual(journal_loot["missingCatalogSourceCount"], 1)
        self.assertEqual(journal_loot["missingCatalogSourceExamples"][0]["itemId"], "250002")
        self.assertIn("1 Battle.net journal loot items missing gear catalog source", payload["blockers"])

    def test_gear_catalog_health_ignores_inactive_reused_legacy_journal_loot(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[
                    {"id": "556", "dungeonId": "556", "instanceId": "278", "name": "Pit of Saron"},
                ],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('278', 'Pit of Saron', 'Dungeon', '{}', 'now')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, '278', 'Forge Lord Garfrost', ?, 'now')
                """,
                (
                    "1001",
                    json.dumps(
                        {
                            "items": [
                                {"item": {"id": 50228, "name": "Accepted Neck"}},
                                {"item": {"id": 49801, "name": "Raw Journal Staff"}},
                                {"item": {"id": 133501, "name": "Legacy Duplicate Staff"}},
                            ],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            for item_id, name in (
                ("50228", "Accepted Neck"),
                ("49801", "Raw Journal Staff"),
                ("133501", "Legacy Duplicate Staff"),
            ):
                conn.execute(
                    """
                    INSERT INTO websim_loot
                    (id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at)
                    VALUES (?, '278', '1001', ?, ?, 'neck', 'Epic', '', '{}', 'now')
                    """,
                    (f"278:1001:{item_id}", item_id, name),
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-278:1001:50228",
                    "itemId": "50228",
                    "sourceType": "dungeon",
                    "sourceLabel": "Forge Lord Garfrost - Pit of Saron",
                    "instanceId": "278",
                    "encounterId": "1001",
                    "seasonRevision": "season-mn-1",
                    "payload": {"validationStatus": "source_reference", "candidateStatus": "source_reference"},
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        journal_loot = payload["details"]["seasonSourceCoverage"]["journalLoot"]
        self.assertEqual(journal_loot["expectedItemCount"], 1)
        self.assertEqual(journal_loot["cachedItemCount"], 1)
        self.assertEqual(journal_loot["missingCatalogSourceCount"], 0)
        self.assertNotIn("Battle.net journal loot items missing gear catalog source", " ".join(payload["blockers"]))

    def test_gear_catalog_health_reports_journal_loot_catalog_source_context_mismatch(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="season-mn-1",
                    dungeons=[
                        {"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"},
                    ],
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, '1300', 'Arcane Warden', ?, 'now')
                """,
                (
                    "9001",
                    json.dumps(
                        {
                            "id": 9001,
                            "name": "Arcane Warden",
                            "items": [{"item": {"id": 250001, "name": "Catalog Hood"}}],
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    '1300:9001:250001', '1300', '9001', '250001', 'Catalog Hood', 'head', 'Epic',
                    'https://render.example/item.jpg', '{}', 'now'
                )
                """
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-1300:9001:250001",
                    "itemId": "250001",
                    "sourceType": "dungeon",
                    "sourceLabel": "Wrong Boss - Magisters' Terrace",
                    "instanceId": "1300",
                    "encounterId": "9999",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        journal_loot = payload["details"]["seasonSourceCoverage"]["journalLoot"]
        self.assertEqual(journal_loot["catalogSourceItemCount"], 0)
        self.assertEqual(journal_loot["mismatchedCatalogSourceCount"], 1)
        mismatch = journal_loot["mismatchedCatalogSourceExamples"][0]
        self.assertEqual(mismatch["itemId"], "250001")
        self.assertEqual(mismatch["sourceId"], "loot-1300:9001:250001")
        self.assertEqual(mismatch["expectedEncounterId"], "9001")
        self.assertEqual(mismatch["actualEncounterId"], "9999")
        self.assertIn("1 Battle.net journal loot items have mismatched gear catalog source context", payload["blockers"])

    def test_gear_catalog_health_requires_active_season_dungeon_enumeration(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Fearsome Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                fallback_name="Fearsome Visage",
                english_payload={"name": "Fearsome Visage", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250015",
                    "itemId": "250015",
                    "sourceType": "dungeon",
                    "sourceLabel": "Observed dungeon",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250015",
                    "itemId": "250015",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "dungeon",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        coverage = payload["details"]["seasonSourceCoverage"]
        self.assertEqual(coverage["status"], "partial")
        self.assertEqual(coverage["mythicPlus"]["expectedDungeonCount"], 0)
        self.assertIn("active season dungeon list is missing", payload["blockers"])

    def test_gear_catalog_health_blocks_discovered_item_set_without_item_set_detail(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Fearsome Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "item_set": {"id": 777, "name": "Ra-den's Chosen"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                fallback_name="Fearsome Visage",
                english_payload={"name": "Fearsome Visage", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250015",
                    "itemId": "250015",
                    "sourceType": "raid",
                    "sourceLabel": "Ra-den",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250015",
                    "itemId": "250015",
                    "slot": "head",
                    "variantKey": "observed-289",
                    "label": "Observed 289",
                    "sourceType": "raid",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets.get("discoveredSetCount"), 1)
        self.assertEqual(sets.get("verifiedSetCount"), 0)
        self.assertIn("1 discovered item sets missing Battle.net item-set detail", payload["blockers"])

    def test_gear_catalog_health_ignores_observed_profile_item_set_detail_for_pve_sources(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "245752",
                {
                    "id": 245752,
                    "name": "Thalassian Competitor's Insignia of Alacrity",
                    "inventory_type": {"type": "TRINKET", "name": "Trinket"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "item_set": {"id": 1458, "name": "Gladiator's Glory"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                fallback_name="Thalassian Competitor's Insignia of Alacrity",
                english_payload={"name": "Thalassian Competitor's Insignia of Alacrity", "inventory_type": {"name": "Trinket"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-demonhunter-devourer-trinket2-245752",
                    "itemId": "245752",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO CN observed demonhunter devourer",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-demonhunter-devourer-trinket2-245752",
                    "itemId": "245752",
                    "slot": "trinket2",
                    "variantKey": "observed-246",
                    "label": "Observed 246",
                    "sourceType": "observed_profile",
                    "itemLevel": 246,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets.get("discoveredSetCount"), 0)
        self.assertNotIn("1 discovered item sets missing Battle.net item-set detail", payload["blockers"])

    def test_gear_catalog_health_reports_missing_expected_item_set_detail(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            )
            season["itemSets"] = [
                {"id": "777", "name": "Ra-den's Chosen"},
                {"id": "778", "name": "Forgotten Champion"},
            ]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_set(
                conn,
                "777",
                {"id": 777, "name": "Ra-den's Chosen", "items": [{"item": {"id": 250015, "name": "Fearsome Visage"}}]},
                "season-mn-1",
            )
            self.websim_payload.upsert_websim_item_set_item(
                conn,
                "777",
                {"itemId": "250015", "name": "Fearsome Visage", "slot": "head"},
                "head",
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets["expectedSetCount"], 2)
        self.assertEqual(sets["verifiedSetCount"], 1)
        self.assertEqual(sets["missingExpectedSetCount"], 1)
        self.assertEqual(sets["missingExpectedSets"], ["Forgotten Champion"])
        self.assertIn("1 current season item sets missing Battle.net item-set detail", payload["blockers"])

    def test_gear_catalog_health_matches_expected_item_set_display_name_to_verified_set_name(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["itemSets"] = [{"name": "织影者的预兆（0/3）"}]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_set(
                conn,
                "1332",
                {"id": 1332, "name": "织影者的预兆", "items": [{"item": {"id": 151303, "name": "虚空扭曲者长袍"}}]},
                "season-mn-1",
            )
            self.websim_payload.upsert_websim_item_set_item(
                conn,
                "1332",
                {"itemId": "151303", "name": "虚空扭曲者长袍", "slot": "chest"},
                "chest",
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets["expectedSetCount"], 1)
        self.assertEqual(sets["verifiedSetCount"], 1)
        self.assertEqual(sets["missingExpectedSetCount"], 0)
        self.assertNotIn("1 current season item sets missing Battle.net item-set detail", payload["blockers"])

    def test_gear_catalog_health_reports_item_set_piece_missing_catalog_source(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["itemSets"] = [{"id": "777", "name": "Ra-den's Chosen"}]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_set(
                conn,
                "777",
                {
                    "id": 777,
                    "name": "Ra-den's Chosen",
                    "items": [
                        {"item": {"id": 250015, "name": "Fearsome Visage"}},
                        {"item": {"id": 250016, "name": "Thunderfists"}},
                    ],
                },
                "season-mn-1",
            )
            for item_id, name, slot in (
                ("250015", "Fearsome Visage", "head"),
                ("250016", "Thunderfists", "hands"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": slot.upper(), "name": slot.title()},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 2, "name": "Leather"},
                        "item_set": {"id": 777, "name": "Ra-den's Chosen"},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                        },
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": slot.title()}},
                    locale="en_US",
                )
                self.websim_payload.upsert_websim_item_set_item(
                    conn,
                    "777",
                    {"itemId": item_id, "name": name, "slot": slot},
                    slot,
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "set-777-250015",
                    "itemId": "250015",
                    "sourceType": "tier_set",
                    "sourceLabel": "Ra-den's Chosen",
                    "seasonRevision": "season-mn-1",
                    "payload": {
                        "authority": self.websim_payload.ITEM_METADATA_SOURCE,
                        "setId": "777",
                        "setName": "Ra-den's Chosen",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, self.websim_payload.get_active_season_payload(conn)),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets["verifiedSetItemCount"], 2)
        self.assertEqual(sets["setItemCatalogSourceCount"], 1)
        self.assertEqual(sets["missingSetItemCatalogSourceCount"], 1)
        self.assertEqual(sets["missingSetItemCatalogSourceExamples"][0]["itemId"], "250016")
        self.assertIn("1 item set pieces missing gear catalog source", payload["blockers"])

    def test_item_set_ref_from_payload_reads_nested_battle_net_set_id(self):
        payload = {
            "id": 151303,
            "name": "Void-Twisted Robes",
            "set": {
                "item_set": {
                    "key": {
                        "href": "https://us.api.blizzard.com/data/wow/item-set/1332?namespace=static-12.0.7_67808-us"
                    },
                    "name": "织影者的预兆",
                    "id": 1332,
                },
                "display_string": "织影者的预兆（0/3）",
            },
        }

        ref = self.websim_payload.item_set_ref_from_payload(payload)

        self.assertEqual(ref, {"id": "1332", "name": "织影者的预兆"})

    def test_sync_blizzard_item_sets_merges_season_display_name_with_discovered_numeric_id(self):
        conn = sqlite3.connect(self.db_path)
        original_blizzard_get = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        requested_paths = []

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            requested_paths.append(path)
            if path == "/data/wow/item-set/1332":
                return {
                    "id": 1332,
                    "name": "织影者的预兆",
                    "items": [{"item": {"id": 151303, "name": "虚空扭曲者长袍"}}],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        self.websim_payload.blizzard_get = fake_blizzard_get

        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["itemSets"] = [{"name": "织影者的预兆（0/3）"}]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "151303",
                {
                    "id": 151303,
                    "name": "虚空扭曲者长袍",
                    "inventory_type": {"type": "CHEST", "name": "Chest"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                    "set": {
                        "item_set": {
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/item-set/1332?namespace=static-12.0.7_67808-us"
                            },
                            "name": "织影者的预兆",
                            "id": 1332,
                        },
                        "display_string": "织影者的预兆（0/3）",
                    },
                },
                fallback_name="虚空扭曲者长袍",
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-151303",
                    "itemId": "151303",
                    "sourceType": "raid",
                    "sourceLabel": "Manaforge Omega",
                    "seasonRevision": "season-mn-1",
                },
            )
            counts = self.websim_payload.sync_blizzard_item_sets(
                conn,
                "token",
                "us",
                "zh_CN",
                self.websim_payload.get_active_season_payload(conn),
            )
        finally:
            conn.close()

        self.assertEqual(requested_paths, ["/data/wow/item-set/1332"])
        self.assertEqual(counts["itemSets"], 1)
        self.assertEqual(counts["errors"], [])

    def test_sync_blizzard_item_sets_expands_discovered_set_into_catalog_sources(self):
        conn = sqlite3.connect(self.db_path)
        original_blizzard_get = self.websim_payload.blizzard_get
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/item-set/777":
                return {
                    "id": 777,
                    "name": "Ra-den's Chosen",
                    "items": [
                        {"item": {"id": 250015, "name": "Fearsome Visage"}},
                        {"item": {"id": 250016, "name": "Thunderfists"}},
                    ],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            slot = "HEAD" if str(item_id) == "250015" else "HANDS"
            item_name = fallback_name or ("Fearsome Visage" if str(item_id) == "250015" else "Thunderfists")
            return {
                "payload": {
                    "id": int(item_id),
                    "name": item_name,
                    "inventory_type": {"type": slot, "name": slot.title()},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "item_set": {"id": 777, "name": "Ra-den's Chosen"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                "media": {"assets": [{"value": f"https://render.example/item-{item_id}.jpg"}]},
                "englishPayload": {"name": item_name},
                "locale": locale,
                "fallbackName": fallback_name,
            }

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                fake_fetch("token", "250015")["payload"],
                fallback_name="Fearsome Visage",
                english_payload={"name": "Fearsome Visage", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    'loot-250015', '1400', '9100', '250015', 'Fearsome Visage', 'head', 'Epic',
                    'https://render.example/item-250015.jpg', '{}', 'now'
                )
                """
            )
            counts = self.websim_payload.sync_blizzard_item_sets(
                conn,
                "token",
                "us",
                "zh_CN",
                {"seasonRevision": "season-mn-1"},
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
            set_items = conn.execute(
                "SELECT set_id, item_id, name FROM websim_item_set_items ORDER BY item_id"
            ).fetchall()
            sources = conn.execute(
                "SELECT item_id, source_type, source_label FROM websim_gear_sources WHERE source_type = 'tier_set' ORDER BY item_id"
            ).fetchall()
            variants = conn.execute(
                "SELECT item_id, slot, status FROM websim_gear_variants WHERE source_type = 'tier_set' ORDER BY item_id"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["itemSets"], 1)
        self.assertEqual(counts["setItems"], 2)
        self.assertEqual(set_items, [("777", "250015", "Fearsome Visage"), ("777", "250016", "Thunderfists")])
        self.assertEqual(
            sources,
            [
                ("250015", "tier_set", "Ra-den's Chosen"),
                ("250016", "tier_set", "Ra-den's Chosen"),
            ],
        )
        self.assertEqual(variants, [("250015", "head", "partial"), ("250016", "hands", "partial")])
        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets["verifiedSetCount"], 1)
        self.assertEqual(sets["verifiedSetItemCount"], 2)
        self.assertEqual(sets["missingSetDetailCount"], 0)
        self.assertNotIn("1 discovered item sets missing Battle.net item-set detail", payload["blockers"])

    def test_sync_blizzard_item_sets_fetches_active_season_expected_sets(self):
        conn = sqlite3.connect(self.db_path)
        original_blizzard_get = self.websim_payload.blizzard_get
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/item-set/778":
                return {
                    "id": 778,
                    "name": "Forgotten Champion",
                    "items": [{"item": {"id": 250099, "name": "Champion's Crown"}}],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            return {
                "payload": {
                    "id": int(item_id),
                    "name": fallback_name or f"Item {item_id}",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 4, "name": "Plate"},
                    "item_set": {"id": 778, "name": "Forgotten Champion"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "STRENGTH", "name": "Strength"}, "value": 111}],
                    },
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
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["itemSets"] = [{"id": "778", "name": "Forgotten Champion"}]
            self.websim_payload.save_active_season_payload(conn, season)
            counts = self.websim_payload.sync_blizzard_item_sets(
                conn,
                "token",
                "us",
                "zh_CN",
                self.websim_payload.get_active_season_payload(conn),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
            set_items = conn.execute(
                "SELECT set_id, item_id, name FROM websim_item_set_items ORDER BY item_id"
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["itemSets"], 1)
        self.assertEqual(counts["setItems"], 1)
        self.assertEqual(set_items, [("778", "250099", "Champion's Crown")])
        sets = payload["details"]["seasonSourceCoverage"]["sets"]
        self.assertEqual(sets["expectedSetCount"], 1)
        self.assertEqual(sets["verifiedSetCount"], 1)
        self.assertEqual(sets["missingExpectedSetCount"], 0)

    def test_sync_blizzard_item_sets_skips_named_refs_without_numeric_set_id(self):
        conn = sqlite3.connect(self.db_path)
        original_blizzard_get = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        self.websim_payload.blizzard_get = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("item-set detail should not be requested without a numeric set id")
        )

        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="season-mn-1",
                dungeons=[],
            )
            season["itemSets"] = [{"name": "织影者的预言（0/3）"}]
            self.websim_payload.save_active_season_payload(conn, season)
            counts = self.websim_payload.sync_blizzard_item_sets(
                conn,
                "token",
                "us",
                "zh_CN",
                self.websim_payload.get_active_season_payload(conn),
            )
        finally:
            conn.close()

        self.assertEqual(counts["itemSets"], 0)
        self.assertEqual(counts["skipped"], 1)
        self.assertIn("missing numeric Battle.net item-set id", counts["errors"][0])

    def test_sync_blizzard_item_sets_keeps_metadata_blocker_when_piece_item_fetch_fails(self):
        conn = sqlite3.connect(self.db_path)
        original_blizzard_get = self.websim_payload.blizzard_get
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        self.websim_payload.blizzard_get = lambda path, token, region="us", locale="zh_CN", params=None, namespace=None: {
            "id": 777,
            "name": "Ra-den's Chosen",
            "items": [{"item": {"id": 250099, "name": "Missing Metadata Gloves"}}],
        }
        self.websim_payload.fetch_blizzard_item_metadata = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("item api down"))

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250015",
                {
                    "id": 250015,
                    "name": "Fearsome Visage",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 2, "name": "Leather"},
                    "item_set": {"id": 777, "name": "Ra-den's Chosen"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                fallback_name="Fearsome Visage",
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    'loot-250015', '1400', '9100', '250015', 'Fearsome Visage', 'head', 'Epic',
                    'https://render.example/item-250015.jpg', '{}', 'now'
                )
                """
            )
            counts = self.websim_payload.sync_blizzard_item_sets(
                conn,
                "token",
                "us",
                "zh_CN",
                {"seasonRevision": "season-mn-1"},
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(counts["setItems"], 1)
        self.assertEqual(payload["details"]["itemMetadata"]["itemCount"], 2)
        self.assertEqual(payload["details"]["itemMetadata"]["missingVerifiedItemCount"], 1)
        self.assertIn("1 catalog items missing verified Battle.net metadata", payload["blockers"])

    def test_sync_blizzard_observed_item_metadata_fetches_source_reference_items_by_id(self):
        conn = sqlite3.connect(self.db_path)
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            self.assertEqual(str(item_id), "249293")
            return {
                "payload": {
                    "id": 249293,
                    "name": "Weight of Command",
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 4, "name": "Mace"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 222}],
                    },
                },
                "media": {"assets": [{"value": "https://render.example/item-249293.jpg"}]},
                "englishPayload": {"name": "Weight of Command"},
                "locale": locale,
                "fallbackName": fallback_name,
                "fallbackSlot": fallback_slot,
            }

        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.ensure_observed_item_metadata(
                conn,
                {"itemId": "249293", "name": "Weight of Command", "slot": "main_hand"},
                "main_hand",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-249293",
                    "itemId": "249293",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO CN observed monk mistweaver",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-249293-main_hand",
                    "itemId": "249293",
                    "slot": "main_hand",
                    "sourceType": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "6652"},
                    "status": "verified",
                },
            )
            counts = self.websim_payload.sync_blizzard_observed_item_metadata(conn, "token", "us", "zh_CN")
            metadata = self.websim_payload.existing_websim_item_metadata(conn, "249293")
        finally:
            conn.close()

        self.assertEqual(counts["items"], 1)
        self.assertEqual(counts["errors"], [])
        self.assertEqual(metadata["metadataSource"], self.websim_payload.ITEM_METADATA_SOURCE)
        self.assertEqual(metadata["metadataStatus"], "verified")
        self.assertEqual(metadata["weaponType"], "One-Handed Mace")

    def test_observed_promotion_reuses_one_hand_weapon_options_across_hands(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "49807",
                {
                    "id": 49807,
                    "name": "Krick's Beetle Stabber",
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 15, "name": "Dagger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "AGILITY", "name": "Agility"}, "value": 111}],
                    },
                },
                fallback_name="Krick's Beetle Stabber",
                english_payload={"name": "Krick's Beetle Stabber", "inventory_type": {"name": "One-Hand"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-source-49807",
                    "itemId": "49807",
                    "sourceType": "dungeon",
                    "sourceLabel": "Ick and Krick - Pit of Saron",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-49807-main_hand",
                    "itemId": "49807",
                    "slot": "main_hand",
                    "sourceType": "dungeon",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-rogue-outlaw-off_hand-49807",
                    "itemId": "49807",
                    "slot": "off_hand",
                    "sourceType": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "13440/6652/12701/13654", "enchant_id": "8039"},
                    "status": "verified",
                    "payload": {
                        "observedProfileRefs": [{"sourceName": "Raider.IO"}],
                        "classKeys": ["rogue"],
                        "specKeys": ["outlaw"],
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [{"key": "agility", "label": "敏捷", "value": 77}],
                        "statSummary": "敏捷 77",
                    },
                },
            )

            counts = self.websim_payload.promote_official_gear_variants_from_observed(conn)
            rows = conn.execute(
                """
                SELECT slot, item_level, simc_options_json, status, payload_json
                FROM websim_gear_variants
                WHERE item_id = '49807'
                  AND source_type = 'dungeon'
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["promotedVariants"], 1)
        self.assertEqual(counts["removedPartialVariants"], 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "main_hand")
        self.assertEqual(rows[0][1], 298)
        self.assertEqual(json.loads(rows[0][2]), {"bonus_id": "13440/6652/12701/13654", "enchant_id": "8039"})
        self.assertEqual(rows[0][3], "verified")
        payload = json.loads(rows[0][4])
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statDisplayStatus"], "verified_variant")
        self.assertEqual(payload["statSummary"], "敏捷 77")
        self.assertNotIn("classKeys", payload)
        self.assertNotIn("specKeys", payload)
        self.assertEqual(payload["observedClassKeys"], ["rogue"])
        self.assertEqual(payload["observedSpecKeys"], ["outlaw"])

    def test_refresh_official_observed_variants_copies_simc_stats_from_observed_profile(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            for source_type in ("observed_profile", "tier_set"):
                self.websim_payload.upsert_gear_variant(
                    conn,
                    {
                        "id": f"{source_type}-249979",
                        "itemId": "249979",
                        "slot": "head",
                        "sourceType": source_type,
                        "difficultyKey": "observed_profile",
                        "itemLevel": 289,
                        "simcOptions": {"bonus_id": "13338/13440/6652", "enchant_id": "8017"},
                        "status": "verified",
                        "payload": (
                            {
                                "classKeys": ["shaman"],
                                "specKeys": ["enhancement"],
                                "statSource": "simulationcraft",
                                "statDisplayStatus": "verified_variant",
                                "itemStats": [{"key": "agiint", "label": "敏捷 or 智力", "value": 124}],
                                "statSummary": "敏捷 or 智力 124",
                            }
                            if source_type == "observed_profile"
                            else {"classKeys": ["shaman"], "specKeys": ["enhancement"]}
                        ),
                    },
                )

            counts = self.websim_payload.refresh_official_observed_variant_payloads_from_observed(conn)
            payload_json = conn.execute(
                """
                SELECT payload_json
                FROM websim_gear_variants
                WHERE id = 'tier_set-249979'
                """
            ).fetchone()[0]
        finally:
            conn.close()

        payload = json.loads(payload_json)
        self.assertEqual(counts["refreshedOfficialObservedVariants"], 1)
        self.assertEqual(payload["statSource"], "simulationcraft")
        self.assertEqual(payload["statDisplayStatus"], "verified_variant")
        self.assertEqual(payload["statSummary"], "敏捷 or 智力 124")
        self.assertNotIn("classKeys", payload)
        self.assertNotIn("specKeys", payload)
        self.assertEqual(payload["observedClassKeys"], ["shaman"])
        self.assertEqual(payload["observedSpecKeys"], ["enhancement"])
        self.assertTrue(
            self.websim_payload.catalog_variant_compatible(
                {
                    "slot": "head",
                    "sourceType": "tier_set",
                    "payload": {
                        "officialVariantSource": "tier_set",
                        "observedProfileRefs": [{"classKey": "shaman", "specKey": "enhancement"}],
                    },
                },
                "shaman",
                "elemental",
                "head",
            )
        )

    def test_battle_net_preview_variant_promotes_raid_and_tier_but_rejects_low_dungeon_preview(self):
        raid_payload = {
            "preview_item": {
                "level": {"value": 298, "display_string": "Item Level 298"},
                "bonus_list": [6652, 13335],
            }
        }
        tier_payload = {
            "preview_item": {
                "level": {"value": 289, "display_string": "Item Level 289"},
            }
        }
        low_dungeon_payload = {
            "preview_item": {
                "level": {"value": 289, "display_string": "Item Level 289"},
                "bonus_list": [12806],
            }
        }

        raid_variant = self.websim_payload.battle_net_preview_variant_from_metadata(raid_payload, "raid")
        tier_variant = self.websim_payload.battle_net_preview_variant_from_metadata(tier_payload, "tier_set")

        self.assertEqual(raid_variant["itemLevel"], 298)
        self.assertEqual(raid_variant["simcOptions"], {"bonus_id": "6652/13335"})
        self.assertFalse(raid_variant["simcIlevelOnly"])
        self.assertEqual(tier_variant["itemLevel"], 289)
        self.assertEqual(tier_variant["simcOptions"], {})
        self.assertTrue(tier_variant["simcIlevelOnly"])
        self.assertIsNone(
            self.websim_payload.battle_net_preview_variant_from_metadata(low_dungeon_payload, "dungeon")
        )

    def test_item_playable_class_requirement_filters_other_class_tier_items(self):
        payload = {
            "preview_item": {
                "inventory_type": {"type": "HEAD", "name": "Head"},
                "item_class": {"id": 4, "name": "Armor"},
                "item_subclass": {"id": 4, "name": "Plate"},
                "requirements": {
                    "playable_classes": {
                        "links": [{"id": 6, "name": "Death Knight"}],
                    }
                },
            }
        }

        self.assertEqual(self.websim_payload.gear_compatibility_from_payload(payload, "paladin", "head"), "incompatible")
        self.assertNotEqual(self.websim_payload.gear_compatibility_from_payload(payload, "deathknight", "head"), "incompatible")

    def test_observed_promotion_does_not_reuse_offhand_only_items_as_main_hand(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "251105",
                {
                    "id": 251105,
                    "name": "Spellbreaker's Shield",
                    "inventory_type": {"type": "SHIELD", "name": "Shield"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 6, "name": "Shield"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "STRENGTH", "name": "Strength"}, "value": 111}],
                    },
                },
                fallback_name="Spellbreaker's Shield",
                english_payload={"name": "Spellbreaker's Shield", "inventory_type": {"name": "Shield"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-source-251105",
                    "itemId": "251105",
                    "sourceType": "dungeon",
                    "sourceLabel": "Boss - Dungeon",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-251105-main_hand",
                    "itemId": "251105",
                    "slot": "main_hand",
                    "sourceType": "dungeon",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-shaman-restoration-off_hand-251105",
                    "itemId": "251105",
                    "slot": "off_hand",
                    "sourceType": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/6652/12699/12806"},
                    "status": "verified",
                },
            )

            counts = self.websim_payload.promote_official_gear_variants_from_observed(conn)
            partial_exists = conn.execute(
                "SELECT 1 FROM websim_gear_variants WHERE id = 'loot-partial-251105-main_hand'"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(counts["promotedVariants"], 0)
        self.assertEqual(counts["removedPartialVariants"], 0)
        self.assertIsNotNone(partial_exists)

    def test_observed_promotion_keeps_existing_promoted_variants_when_no_partial_source_remains(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-observed-49807-main_hand-existing",
                    "itemId": "49807",
                    "slot": "main_hand",
                    "sourceType": "dungeon",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 298,
                    "simcOptions": {"bonus_id": "13440/6652/12701/13654"},
                    "status": "verified",
                },
            )

            counts = self.websim_payload.promote_official_gear_variants_from_observed(conn)
            existing = conn.execute(
                "SELECT status FROM websim_gear_variants WHERE id = 'loot-observed-49807-main_hand-existing'"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(counts["promotedVariants"], 0)
        self.assertEqual(counts["removedPartialVariants"], 0)
        self.assertIsNotNone(existing)
        self.assertEqual(existing[0], "verified")

    def test_observed_promotion_requires_simulationcraft_stat_payload(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "258575",
                {
                    "id": 258575,
                    "name": "刚鳞大氅",
                    "inventory_type": {"type": "CLOAK", "name": "Back"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 1}],
                    },
                },
                fallback_name="Scaleshard Cape",
                english_payload={"name": "Scaleshard Cape", "inventory_type": {"name": "Back"}},
                locale="zh_CN",
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-258575-back",
                    "itemId": "258575",
                    "slot": "back",
                    "sourceType": "dungeon",
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-back-258575",
                    "itemId": "258575",
                    "slot": "back",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "13440/6652/13577/12699/12806"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                    },
                },
            )

            counts = self.websim_payload.promote_official_gear_variants_from_observed(conn)
            official_rows = conn.execute(
                """
                SELECT id, status
                FROM websim_gear_variants
                WHERE item_id = '258575'
                  AND source_type = 'dungeon'
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["promotedVariants"], 0)
        self.assertEqual(counts["removedPartialVariants"], 0)
        self.assertEqual(official_rows, [("loot-partial-258575-back", "partial")])

    def test_gear_catalog_health_recomputes_current_audit_over_stale_sync_snapshot(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-250111",
                    "itemId": "250111",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                    "instanceId": "1300",
                    "encounterId": "9001",
                    "seasonRevision": "season-mn-1",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "variant-250111",
                    "itemId": "250111",
                    "slot": "wrist",
                    "variantKey": "observed-707",
                    "label": "Observed 707",
                    "sourceType": "dungeon",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                {
                    "status": "verified",
                    "checkedAt": "2026-06-21T00:00:00+00:00",
                    "itemCount": 1,
                    "sourceCount": 1,
                    "variantCount": 1,
                    "verifiedCount": 1,
                    "partialCount": 0,
                    "blockedCount": 0,
                    "blockers": [],
                    "itemMetadata": {
                        "status": "verified",
                        "itemCount": 1,
                        "verifiedItemCount": 1,
                        "missingVerifiedItemCount": 0,
                        "blockers": [],
                    },
                },
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["details"]["itemMetadata"]["missingVerifiedItemCount"], 1)
        self.assertIn("1 catalog items missing verified Battle.net metadata", payload["blockers"])

    def test_gear_catalog_health_separates_verified_data_from_partial_simc_variants(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250888",
                {
                    "id": 250888,
                    "name": "Verified Loop",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 321}],
                    },
                },
                {"assets": [{"value": "https://render.example/ring.jpg"}]},
                fallback_name="Verified Loop",
                english_payload={"name": "Verified Loop", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250888",
                    "itemId": "250888",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                    "seasonRevision": "",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-partial-250888-finger",
                    "itemId": "250888",
                    "slot": "finger1",
                    "variantKey": "needs-variant",
                    "label": "Needs variant",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "simcOptions": {},
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["details"]["dataReadiness"]["status"], "verified")
        self.assertEqual(payload["details"]["dataReadiness"]["blockers"], [])
        self.assertEqual(payload["details"]["simulationReadiness"]["status"], "partial")
        self.assertIn(
            "missing deterministic SimC variant preset",
            payload["details"]["simulationReadiness"]["blockers"],
        )
        example = payload["details"]["simulationReadiness"]["partialExamples"][0]
        self.assertEqual(example["itemId"], "250888")
        self.assertEqual(example["slot"], "finger1")
        self.assertEqual(example["sourceType"], "dungeon")
        self.assertEqual(example["sourceLabel"], "Magisters' Terrace")
        self.assertEqual(example["variantId"], "loot-partial-250888-finger")
        self.assertEqual(example["blockers"], ["missing deterministic SimC variant preset"])

    def test_gear_catalog_health_ignores_observed_profile_partials_for_official_readiness(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250889",
                {
                    "id": 250889,
                    "name": "Verified Band",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 321}],
                    },
                },
                {"assets": [{"value": "https://render.example/ring.jpg"}]},
                fallback_name="Verified Band",
                english_payload={"name": "Verified Band", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250889",
                    "itemId": "250889",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                    "seasonRevision": "",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-verified-250889-finger",
                    "itemId": "250889",
                    "slot": "finger1",
                    "variantKey": "observed-707",
                    "label": "Observed 707",
                    "sourceType": "dungeon",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-warrior-arms-finger1-250889",
                    "itemId": "250889",
                    "slot": "finger1",
                    "variantKey": "observed-profile-no-options",
                    "label": "Observed profile without options",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 707,
                    "simcOptions": {},
                    "status": "partial",
                    "blockers": ["Raider.IO observed gear source is not verified"],
                },
            )

            counts = self.websim_payload.gear_catalog_counts(conn)
        finally:
            conn.close()

        self.assertEqual(counts["status"], "partial")
        self.assertEqual(counts["simulationReadiness"]["status"], "partial")
        self.assertEqual(counts["simulationReadiness"]["verified"], 1)
        self.assertEqual(counts["simulationReadiness"]["partial"], 0)
        self.assertEqual(
            counts["simulationReadiness"]["blockers"],
            ["1 observed gear variants missing SimulationCraft item stats"],
        )
        self.assertEqual(counts["observedVariantCount"], 1)
        self.assertEqual(counts["partialObservedVariantCount"], 1)

    def test_gear_catalog_sync_loads_server_owned_mod_seed(self):
        os.environ["WOW_WEBSIM_GEAR_MOD_SEED"] = json.dumps(
            [
                {
                    "type": "socket",
                    "name": "Quick Gem",
                    "slots": ["finger1"],
                    "simcOptions": {"gem_id": "240983", "gem_ilevel": "707"},
                    "payload": {
                        "source": "server_owned_seed",
                        "gemItemId": "240983",
                        "displayName": "Quick Gem",
                        "iconUrl": "https://render.example/gem-240983.jpg",
                        "quality": "Epic",
                        "metadataStatus": "verified",
                        "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                        "metadataLocale": "en_US",
                    },
                },
                {
                    "type": "enchant",
                    "name": "Radiant Enchant",
                    "slots": ["finger1"],
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
                    "name": "Catalog Band",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 123}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Catalog Band",
                english_payload={"name": "Catalog Band", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "240983",
                {
                    "id": 240983,
                    "name": "Quick Gem",
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/gem-240983.jpg"}]},
                fallback_name="Quick Gem",
                english_payload={"name": "Quick Gem"},
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
                    "slot": "finger1",
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
            compact_payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane", compact=True)
        finally:
            conn.close()

        finger_group = next(group for group in payload["slotGroups"] if group["slot"] == "finger1")
        catalog_item = next(item for item in finger_group["items"] if item["itemId"] == "250777")
        self.assertEqual(catalog_item["socketOptions"][0]["simcOptions"]["gem_id"], "240983")
        self.assertEqual(catalog_item["enchantOptions"][0]["simcOptions"]["enchant_id"], "8017")
        compact_finger_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "finger1")
        compact_catalog_item = next(item for item in compact_finger_group["items"] if item["itemId"] == "250777")
        self.assertEqual(compact_finger_group["socketOptions"][0]["simcOptions"]["gem_id"], "240983")
        self.assertEqual(compact_finger_group["enchantOptions"][0]["simcOptions"]["enchant_id"], "8017")
        self.assertNotIn("socketOptions", compact_catalog_item)
        self.assertNotIn("enchantOptions", compact_catalog_item)
        self.assertEqual(payload["catalogStatus"], "verified")

    def test_compact_gear_payload_exposes_slot_mod_options_when_candidate_metadata_is_sparse(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "268291",
                {
                    "id": 268291,
                    "name": "Sparse Choker",
                    "inventory_type": {"type": "INVTYPE_NECK", "name": "Neck"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 123}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-268291.jpg"}]},
                fallback_name="Sparse Choker",
                english_payload={"name": "Sparse Choker", "inventory_type": {"name": "Neck"}},
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "240983",
                {
                    "id": 240983,
                    "name": "Quick Onyx",
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/gem-240983.jpg"}]},
                fallback_name="Quick Onyx",
                english_payload={"name": "Quick Onyx"},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {"id": "manual-268291", "itemId": "268291", "sourceType": "raid", "sourceLabel": "Sporefall"},
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "manual-268291-myth",
                    "itemId": "268291",
                    "slot": "neck",
                    "variantKey": "myth-289",
                    "label": "Myth 289",
                    "sourceType": "raid",
                    "difficultyKey": "myth",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('evoker-devastation-sparse-weapon', 'evoker', 'devastation', 'Sparse Weapon', ?, '{}', 'now')
                """,
                (
                    "evoker=\"Sparse Weapon\"\n"
                    "spec=devastation\n"
                    "level=90\n"
                    "main_hand=ritual_hexblade,id=249293,ilevel=298,bonus_id=13786\n"
                ,),
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "socket-gem-240983",
                    "type": "socket",
                    "name": "Quick Onyx",
                    "slots": ["neck"],
                    "simcOptions": {"gem_id": "240983", "gem_ilevel": "707"},
                    "payload": {
                        "gemItemId": "240983",
                        "displayName": "Quick Onyx",
                        "iconUrl": "https://render.example/gem-240983.jpg",
                        "metadataStatus": "verified",
                        "metadataSource": self.websim_payload.ITEM_METADATA_SOURCE,
                        "metadataLocale": "en_US",
                    },
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "enchant-main-hand-8017",
                    "type": "enchant",
                    "name": "Radiant Weapon",
                    "slots": ["main_hand"],
                    "simcOptions": {"enchant_id": "8017"},
                },
            )
            compact_payload = self.websim_payload.get_websim_gear(conn, "evoker", "devastation", compact=True)
        finally:
            conn.close()

        neck_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "neck")
        main_hand_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "main_hand")
        self.assertIn("socketOptions", neck_group)
        self.assertIn("enchantOptions", main_hand_group)
        neck_socket = next(
            option
            for option in neck_group["socketOptions"]
            if option.get("simcOptions", {}).get("gem_id") == "240983"
        )
        main_hand_enchant = next(
            option
            for option in main_hand_group["enchantOptions"]
            if option.get("simcOptions", {}).get("enchant_id") == "8017"
        )
        self.assertEqual(neck_socket["simcOptions"]["gem_id"], "240983")
        self.assertEqual(main_hand_enchant["simcOptions"]["enchant_id"], "8017")
        self.assertTrue(all("socketOptions" not in item for item in neck_group["items"]))
        self.assertTrue(all("enchantOptions" not in item for item in main_hand_group["items"]))

    def test_compact_gear_payload_falls_back_to_executable_mod_options_without_display_metadata(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "268291",
                {
                    "id": 268291,
                    "name": "Sparse Choker",
                    "inventory_type": {"type": "INVTYPE_NECK", "name": "Neck"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 123}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-268291.jpg"}]},
                fallback_name="Sparse Choker",
                english_payload={"name": "Sparse Choker", "inventory_type": {"name": "Neck"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {"id": "manual-268291", "itemId": "268291", "sourceType": "raid", "sourceLabel": "Sporefall"},
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "manual-268291-myth",
                    "itemId": "268291",
                    "slot": "neck",
                    "variantKey": "myth-289",
                    "label": "Myth 289",
                    "sourceType": "raid",
                    "difficultyKey": "myth",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES ('evoker-devastation-sparse-weapon', 'evoker', 'devastation', 'Sparse Weapon', ?, '{}', 'now')
                """,
                (
                    "evoker=\"Sparse Weapon\"\n"
                    "spec=devastation\n"
                    "level=90\n"
                    "main_hand=ritual_hexblade,id=249293,ilevel=298,bonus_id=13786\n"
                ,),
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-socket-240983",
                    "type": "socket",
                    "name": "Observed gem 240983",
                    "slots": ["neck"],
                    "simcOptions": {"gem_id": "240983"},
                    "payload": {"source": "observed_variant"},
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "observed-enchant-8017",
                    "type": "enchant",
                    "name": "Observed enchant 8017",
                    "slots": ["main_hand"],
                    "simcOptions": {"enchant_id": "8017"},
                    "payload": {"source": "observed_variant"},
                },
            )
            compact_payload = self.websim_payload.get_websim_gear(conn, "evoker", "devastation", compact=True)
        finally:
            conn.close()

        neck_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "neck")
        main_hand_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "main_hand")
        self.assertIn("socketOptions", neck_group)
        self.assertIn("enchantOptions", main_hand_group)
        self.assertEqual(neck_group["socketOptions"][0]["label"], "宝石 240983")
        self.assertEqual(neck_group["socketOptions"][0]["simcOptions"]["gem_id"], "240983")
        self.assertEqual(main_hand_group["enchantOptions"][0]["label"], "附魔 8017")
        self.assertEqual(main_hand_group["enchantOptions"][0]["simcOptions"]["enchant_id"], "8017")

    def test_gear_catalog_sync_does_not_load_placeholder_default_mod_seed_without_env(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            count = self.websim_payload.sync_websim_gear_mod_options(conn)
            socket_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "socket")
            enchant_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "enchant")
        finally:
            conn.close()

        self.assertEqual(count, 0)
        self.assertFalse(any(options for options in socket_options.values()))
        self.assertFalse(any(options for options in enchant_options.values()))

    def test_gear_catalog_sync_derives_socket_mod_options_from_verified_gem_variants(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Socketed Catalog Band",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 123}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Socketed Catalog Band",
                english_payload={"name": "Socketed Catalog Band", "inventory_type": {"name": "Finger"}},
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
                    "id": "observed-250777-gem",
                    "itemId": "250777",
                    "slot": "finger1",
                    "variantKey": "observed-707",
                    "label": "Observed 707",
                    "sourceType": "observed_profile",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345", "gem_id": "240983", "gem_ilevel": "707"},
                    "status": "verified",
                },
            )
            count = self.websim_payload.sync_websim_gear_mod_options(conn)
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            socket_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "socket")
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(count, 1)
        option = socket_options["finger1"][0]
        self.assertEqual(option["simcOptions"]["gem_id"], "240983")
        self.assertEqual(option["simcOptions"]["gem_ilevel"], "707")
        self.assertEqual(option["payload"]["source"], "observed_variant")
        self.assertNotIn("socket-capable catalog items missing socket mod options", payload["blockers"])

    def test_websim_gear_hides_socket_options_until_gem_metadata_is_verified(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Socketed Catalog Band",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 123}],
                        "sockets": [{"socket_type": {"type": "PRISMATIC", "name": "Prismatic Socket"}}],
                    },
                },
                {"assets": [{"value": "https://render.example/item-250777.jpg"}]},
                fallback_name="Socketed Catalog Band",
                english_payload={"name": "Socketed Catalog Band", "inventory_type": {"name": "Finger"}},
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
                    "slot": "finger1",
                    "variantKey": "heroic-707",
                    "label": "Heroic 707",
                    "sourceType": "raid",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            self.websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "socket-missing-gem-metadata",
                    "type": "socket",
                    "name": "Quick Gem",
                    "applicableSlots": ["finger1"],
                    "simcOptions": {"gem_id": "240983", "gem_ilevel": "707"},
                    "status": "verified",
                    "payload": {
                        "source": "observed_variant",
                        "displayName": "Quick Gem",
                        "gemItemId": "240983",
                    },
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-test"}),
            )
            health = self.websim_payload.gear_catalog_health_payload(conn)
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
            compact_payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane", compact=True)
        finally:
            conn.close()

        self.assertEqual(health["details"]["modOptionCoverage"]["socket"]["missingMetadataCount"], 1)
        finger_group = next(group for group in payload["slotGroups"] if group["slot"] == "finger1")
        catalog_item = next(item for item in finger_group["items"] if item["itemId"] == "250777")
        self.assertEqual(catalog_item["socketOptions"], [])
        compact_finger_group = next(group for group in compact_payload["replacementCandidates"] if group["slot"] == "finger1")
        self.assertEqual(compact_finger_group["socketOptions"][0]["label"], "宝石 240983")
        self.assertEqual(compact_finger_group["socketOptions"][0]["status"], "partial")
        self.assertEqual(compact_finger_group["socketOptions"][0]["simcOptions"]["gem_id"], "240983")

    def test_gear_catalog_sync_derives_mod_options_from_raiderio_bare_gem_and_enchant(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "151311",
                {
                    "id": 151311,
                    "name": "Band of the Triumvirate",
                    "inventory_type": {"type": "INVTYPE_FINGER", "name": "Finger"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 123}],
                    },
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "_metadata": {"source": self.websim_payload.ITEM_METADATA_SOURCE, "metadataStatus": "verified"},
                },
                {"assets": [{"value": "https://render.example/item-151311.jpg"}]},
                fallback_name="Band of the Triumvirate",
                english_payload={"name": "Band of the Triumvirate", "inventory_type": {"name": "Finger"}},
                locale="en_US",
            )
            self.websim_payload.sync_observed_gear_variants(
                conn,
                {
                    "sourceStatus": "verified",
                    "checkedAt": "2026-06-21T00:00:00+00:00",
                    "specs": {
                        "mage:frost": {
                            "observedGear": [
                                {
                                    "slot": "finger1",
                                    "name": "Band of the Triumvirate",
                                    "itemId": 151311,
                                    "itemLevel": 289,
                                    "quality": 4,
                                    "bonuses": [13440, 6652, 13668, 12699, 12806],
                                    "gems": [240894],
                                    "enchants": [7967],
                                    "enchant": 7967,
                                    "sourceName": "Raider.IO CN profile gear",
                                    "characterName": "Supermono",
                                    "realmSlug": "isillien",
                                    "profileUrl": "https://raider.io/characters/cn/isillien/Supermono",
                                }
                            ],
                        }
                    },
                },
                {"seasonRevision": "season-mn-1"},
            )
            count = self.websim_payload.sync_websim_gear_mod_options(conn)
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, {"seasonRevision": "season-mn-1"}),
            )
            socket_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "socket")
            enchant_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "enchant")
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost")
        finally:
            conn.close()

        self.assertEqual(count, 2)
        self.assertEqual(socket_options["finger1"][0]["simcOptions"]["gem_id"], "240894")
        self.assertEqual(enchant_options["finger1"][0]["simcOptions"]["enchant_id"], "7967")
        finger_group = next(group for group in payload["slotGroups"] if group["slot"] == "finger1")
        catalog_item = next(item for item in finger_group["items"] if item["itemId"] == "151311")
        self.assertEqual(catalog_item["socketOptions"], [])
        self.assertEqual(catalog_item["enchantOptions"], [])

    def test_sync_blizzard_gear_mod_option_metadata_enriches_observed_socket_options(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        fetches = []

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            fetches.append({"token": token, "itemId": str(item_id), "region": region, "locale": locale})
            return {
                "itemId": str(item_id),
                "payload": {
                    "id": int(item_id),
                    "name": "Quick Onyx",
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                "media": {"assets": [{"value": "https://render.example/gem-240983.jpg"}]},
                "englishPayload": {"name": "Quick Onyx"},
                "locale": locale,
                "fallbackName": fallback_name,
                "fallbackSlot": fallback_slot,
            }

        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-250777-gem",
                    "itemId": "250777",
                    "slot": "finger1",
                    "variantKey": "observed-707",
                    "label": "Observed 707",
                    "sourceType": "observed_profile",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345", "gem_id": "240983", "gem_ilevel": "707"},
                    "status": "verified",
                },
            )
            self.websim_payload.sync_websim_gear_mod_options(conn)

            counts = self.websim_payload.sync_blizzard_gear_mod_option_metadata(conn, "token", "us", "zh_CN")
            socket_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "socket")
            gem_metadata = self.websim_payload.existing_websim_item_metadata(conn, "240983")
        finally:
            conn.close()

        self.assertEqual(counts["items"], 1)
        self.assertEqual(counts["skipped"], 0)
        self.assertEqual(counts["errors"], [])
        self.assertEqual(fetches[0]["itemId"], "240983")
        option = socket_options["finger1"][0]
        self.assertEqual(option["name"], "Quick Onyx")
        self.assertEqual(option["label"], "Quick Onyx")
        self.assertEqual(option["gemItemId"], "240983")
        self.assertEqual(option["iconUrl"], "https://render.example/gem-240983.jpg")
        self.assertEqual(option["quality"], "Epic")
        self.assertEqual(option["metadataStatus"], "verified")
        self.assertEqual(option["metadataSource"], self.websim_payload.ITEM_METADATA_SOURCE)
        self.assertEqual(option["payload"]["source"], "observed_variant")
        self.assertEqual(option["payload"]["gemItemId"], "240983")
        self.assertEqual(option["payload"]["metadataStatus"], "verified")
        self.assertEqual(option["payload"]["iconUrl"], "https://render.example/gem-240983.jpg")
        self.assertEqual(gem_metadata["displayName"], "Quick Onyx")
        self.assertEqual(gem_metadata["iconUrl"], "https://render.example/gem-240983.jpg")

    def test_sync_blizzard_gear_mod_option_metadata_enriches_all_gems_in_multi_socket_option(self):
        os.environ.pop("WOW_WEBSIM_GEAR_MOD_SEED", None)
        conn = sqlite3.connect(self.db_path)
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)

        fetches = []
        names = {"240900": "Quick Onyx", "240892": "Keen Emerald"}

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            fetches.append(str(item_id))
            return {
                "itemId": str(item_id),
                "payload": {
                    "id": int(item_id),
                    "name": names[str(item_id)],
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                "media": {"assets": [{"value": f"https://render.example/gem-{item_id}.jpg"}]},
                "englishPayload": {"name": names[str(item_id)]},
                "locale": locale,
                "fallbackName": fallback_name,
                "fallbackSlot": fallback_slot,
            }

        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-250777-two-gems",
                    "itemId": "250777",
                    "slot": "finger1",
                    "variantKey": "observed-707",
                    "label": "Observed 707",
                    "sourceType": "observed_profile",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345", "gem_id": "240900/240892", "gem_ilevel": "707"},
                    "status": "verified",
                },
            )
            self.websim_payload.sync_websim_gear_mod_options(conn)

            counts = self.websim_payload.sync_blizzard_gear_mod_option_metadata(conn, "token", "us", "zh_CN")
            socket_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "socket")
            display_ready_socket_options = self.websim_payload.display_ready_gear_mod_options_by_slot(conn, "socket")
            health = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(fetches, ["240900", "240892"])
        self.assertEqual(counts["items"], 2)
        self.assertEqual(counts["errors"], [])
        option = socket_options["finger1"][0]
        self.assertEqual(option["name"], "Quick Onyx / Keen Emerald")
        self.assertEqual(option["gemItemId"], "240900")
        self.assertEqual(option["gemItemIds"], ["240900", "240892"])
        self.assertEqual(
            [gem["itemId"] for gem in option["payload"]["gemItems"]],
            ["240900", "240892"],
        )
        ready_option = display_ready_socket_options["finger1"][0]
        self.assertEqual(ready_option["name"], "Quick Onyx / Keen Emerald")
        self.assertEqual(ready_option["label"], "Quick Onyx / Keen Emerald")
        self.assertEqual(ready_option["gemItemId"], "240900")
        self.assertEqual(ready_option["gemItemIds"], ["240900", "240892"])
        self.assertNotIn("missingMetadataCount", health["details"]["modOptionCoverage"]["socket"])

    def test_gear_catalog_health_ignores_stale_placeholder_mod_options(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.executemany(
                """
                INSERT INTO websim_gear_mod_options
                (id, option_type, name, applicable_slots_json, simc_options_json,
                 status, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "seed-socket-gem-240983",
                        "socket",
                        "Server seed gem 240983",
                        json.dumps(["*"], ensure_ascii=False),
                        json.dumps({"gem_id": "240983"}, ensure_ascii=False),
                        "partial",
                        json.dumps({"source": "server_default_seed"}, ensure_ascii=False),
                        "now",
                    ),
                    (
                        "enchant-real-8017",
                        "enchant",
                        "Radiant Enchant",
                        json.dumps(["finger1"], ensure_ascii=False),
                        json.dumps({"enchant_id": "8017"}, ensure_ascii=False),
                        "verified",
                        "{}",
                        "now",
                    ),
                ],
            )
            payload = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        coverage = payload["details"]["modOptionCoverage"]
        self.assertEqual(coverage["socket"], {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []})
        self.assertEqual(coverage["enchant"]["optionCount"], 1)
        self.assertEqual(coverage["enchant"]["coveredSlots"], ["finger1"])

    def test_gear_catalog_sync_ignores_crafted_seed_sources(self):
        os.environ["WOW_WEBSIM_CRAFTED_GEAR_SEED"] = json.dumps(
            [
                {
                    "itemId": "250888",
                    "slot": "head",
                    "sourceLabel": "Crafted Hood",
                    "variants": [
                        {
                            "key": "crafted-707",
                            "label": "Crafted 707",
                            "itemLevel": 707,
                            "simcOptions": {"crafted_stats": "32/49"},
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        )
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250888",
                {
                    "id": 250888,
                    "name": "Crafted Hood",
                    "inventory_type": {"name": "Head"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/item-250888.jpg"}]},
                fallback_name="Crafted Hood",
                english_payload={"name": "Crafted Hood"},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {"id": "crafted-old-250888", "itemId": "250888", "sourceType": "crafted", "sourceLabel": "Old Crafted"},
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "crafted-old-250888-707",
                    "itemId": "250888",
                    "slot": "head",
                    "variantKey": "crafted-old",
                    "label": "Old Crafted",
                    "sourceType": "crafted",
                    "itemLevel": 707,
                    "simcOptions": {"crafted_stats": "32/49"},
                    "status": "verified",
                },
            )
            self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            sources = conn.execute("SELECT id, source_type FROM websim_gear_sources WHERE id LIKE 'crafted-%' OR source_type = 'crafted'").fetchall()
            variants = conn.execute("SELECT id, source_type FROM websim_gear_variants WHERE id LIKE 'crafted-%' OR source_type = 'crafted'").fetchall()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "arcane")
        finally:
            conn.close()

        self.assertEqual(sources, [])
        self.assertEqual(variants, [])
        head_group = next(group for group in payload["slotGroups"] if group["slot"] == "head")
        self.assertFalse(any(item["itemId"] == "250888" for item in head_group["items"]))

    def test_gear_catalog_sync_preserves_governed_crafted_sources(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(season_id="17", season_label="Fresh Season")
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260100",
                {
                    "id": 260100,
                    "name": "Crafted Spellblade",
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"name": "One-Handed Sword"},
                    "quality": {"name": "Epic"},
                    "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                    "_metadata": {"source": self.websim_payload.ITEM_METADATA_SOURCE, "metadataStatus": "verified"},
                },
                fallback_name="Crafted Spellblade",
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "crafted-governed-260100",
                    "itemId": "260100",
                    "sourceType": "crafted",
                    "sourceLabel": "制造装备",
                    "seasonRevision": season["seasonRevision"],
                    "payload": {
                        "status": "verified",
                        "profession": "blacksmithing",
                        "recipeId": "500100",
                        "sourceRefs": [{"label": "受控制造业目录"}],
                        "supportsVoidUpgrade": True,
                    },
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "crafted-itemlevel-260100-crafted_myth-285-haste-mastery",
                    "itemId": "260100",
                    "slot": "main_hand",
                    "variantKey": "crafted-myth-285-haste-mastery",
                    "label": "神话 285 · 急速 + 精通",
                    "sourceType": "crafted",
                    "difficultyKey": "crafted_myth",
                    "itemLevel": 285,
                    "simcOptions": {"ilevel": "285", "bonus_id": "8793/8960", "crafted_stats": "40/32"},
                    "status": "verified",
                    "payload": {
                        "seasonRevision": season["seasonRevision"],
                        "derivedVariantSource": "simulationcraft_crafted_item_probe",
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "craftedStatKey": "haste-mastery",
                        "craftedStatLabel": "急速 + 精通",
                        "itemStats": [
                            {"key": "intellect", "label": "智力", "value": 100},
                            {"key": "haste", "label": "急速", "value": 40},
                            {"key": "mastery", "label": "精通", "value": 32},
                        ],
                        "statSummary": "智力 100；急速 40；精通 32",
                    },
                },
            )
            self.websim_payload.sync_websim_gear_catalog(conn, season)
            sources = conn.execute(
                "SELECT id, source_type FROM websim_gear_sources WHERE source_type = 'crafted'"
            ).fetchall()
            variants = conn.execute(
                "SELECT difficulty_key, item_level, status FROM websim_gear_variants WHERE source_type = 'crafted'"
            ).fetchall()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        self.assertEqual(sources, [("crafted-governed-260100", "crafted")])
        self.assertEqual(variants, [("crafted_myth", 285, "verified")])
        main_hand_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "main_hand")
        crafted_item = next(item for item in main_hand_group["items"] if item["itemId"] == "260100")
        self.assertEqual(crafted_item["sourceType"], "crafted")
        self.assertEqual(crafted_item["variants"][0]["difficultyKey"], "myth")
        self.assertEqual(crafted_item["variants"][0]["itemLevel"], 285)
        self.assertEqual(crafted_item["variants"][0]["craftedStatOptions"][0]["label"], "急速 + 精通")
        self.assertEqual(crafted_item["variants"][0]["craftedStatOptions"][0]["simcOptions"]["crafted_stats"], "40/32")

    def test_backfill_crafted_item_level_variants_writes_tracks_and_stat_options(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(season_id="17", season_label="Fresh Season")
            self.websim_payload.save_active_season_payload(conn, season)
            for item_id, name, slot, weapon in (
                ("260100", "Crafted Spellblade", "main_hand", True),
                ("260101", "Crafted Hood", "head", False),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "WEAPON" if weapon else "HEAD", "name": slot},
                        "item_class": {"id": 2 if weapon else 4, "name": "Weapon" if weapon else "Armor"},
                        "item_subclass": {"name": "One-Handed Sword" if weapon else "Cloth"},
                        "quality": {"name": "Epic"},
                        "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                    },
                    fallback_name=name,
                    locale="en_US",
                )

            def fake_stat_resolver(item, item_level, stat_option, track):
                if item["itemId"] == "260101" and stat_option["key"] == "crit_vers":
                    return {"error": "SimC JSON did not include target item stats"}
                return {
                    "itemStats": [
                        {"key": "intellect", "label": "智力", "value": item_level},
                        {"key": "haste", "label": "急速", "value": 40},
                    ],
                    "statSummary": f"智力 {item_level}；{stat_option['label']}",
                    "simcProfile": f"{item['simcSlot']}=crafted,id={item['itemId']},ilevel={item_level},crafted_stats={stat_option['value']}",
                }

            result = self.websim_payload.backfill_crafted_item_level_variants(
                conn,
                [
                    {
                        "itemId": "260100",
                        "slot": "main_hand",
                        "sourceLabel": "制造装备",
                        "profession": "blacksmithing",
                        "recipeId": "500100",
                        "supportsVoidUpgrade": True,
                        "allowedTracks": ["crafted_myth", "crafted_void_upgrade"],
                        "allowedCraftedStats": [
                            {"key": "haste-mastery", "label": "急速 + 精通", "value": "40/32"}
                        ],
                    },
                    {
                        "itemId": "260101",
                        "slot": "head",
                        "sourceLabel": "制造装备",
                        "profession": "tailoring",
                        "recipeId": "500101",
                        "allowedTracks": [
                            "crafted_myth",
                            "crafted_void_upgrade",
                            {"difficultyKey": "void_upgrade", "itemLevel": 295, "label": "虚空晋升 295"},
                        ],
                        "allowedCraftedStats": [
                            {"key": "haste-mastery", "label": "急速 + 精通", "value": "40/32"},
                            {"key": "crit-vers", "label": "暴击 + 全能", "value": "36/36"},
                        ],
                    },
                ],
                stat_resolver=fake_stat_resolver,
            )
            rows = conn.execute(
                """
                SELECT item_id, difficulty_key, item_level, status, simc_options_json, payload_json
                FROM websim_gear_variants
                WHERE source_type = 'crafted'
                ORDER BY item_id, item_level, variant_key
                """
            ).fetchall()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
            health = self.websim_payload.gear_catalog_health_payload(conn)
        finally:
            conn.close()

        self.assertEqual(result["items"], 2)
        self.assertEqual(result["verifiedVariants"], 3)
        self.assertEqual(result["partialVariants"], 1)
        by_item = {}
        for item_id, difficulty_key, item_level, status, simc_options_json, payload_json in rows:
            by_item.setdefault(item_id, []).append((difficulty_key, item_level, status, simc_options_json, payload_json))
        self.assertEqual(
            [(difficulty, level) for difficulty, level, _status, _options, _payload in by_item["260100"]],
            [("crafted_myth", 285), ("crafted_void_upgrade", 295)],
        )
        self.assertEqual(
            [(difficulty, level) for difficulty, level, _status, _options, _payload in by_item["260101"]],
            [("crafted_myth", 285), ("crafted_myth", 285)],
        )
        self.assertNotIn(289, [level for _difficulty, level, _status, _options, _payload in by_item["260101"]])
        self.assertNotIn(298, [level for _difficulty, level, _status, _options, _payload in by_item["260100"]])
        partial_payload = json.loads(by_item["260101"][0][4] if by_item["260101"][0][2] == "partial" else by_item["260101"][1][4])
        self.assertEqual(partial_payload["craftedStatLabel"], "暴击 + 全能")

        main_hand_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "main_hand")
        weapon = next(item for item in main_hand_group["items"] if item["itemId"] == "260100")
        self.assertEqual([variant["itemLevel"] for variant in weapon["variants"]], [295, 285])
        self.assertEqual([variant["difficultyLabel"] for variant in weapon["variants"]], ["虚空晋升", "神话"])
        self.assertEqual(weapon["variants"][0]["craftedStatOptions"][0]["label"], "急速 + 精通")
        self.assertEqual(weapon["variants"][0]["craftedStatOptions"][0]["statSummary"], "智力 295；急速 + 精通")
        self.assertEqual(health["details"]["sourceCoverage"]["crafted"], 2)
        self.assertEqual(health["details"]["modOptionCoverage"]["crafted_stats"]["optionCount"], 2)
        self.assertEqual(set(health["details"]["modOptionCoverage"]["crafted_stats"]["coveredSlots"]), {"head", "main_hand"})

    def test_backfill_crafted_item_level_variants_removes_stale_item_variants(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(season_id="17", season_label="Fresh Season")
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260150",
                {
                    "id": 260150,
                    "name": "Crafted Spellblade",
                    "inventory_type": {"type": "WEAPON", "name": "One-Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 7, "name": "One-Handed Sword"},
                    "quality": {"name": "Epic"},
                    "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                },
                {},
                fallback_name="Crafted Spellblade",
                locale="en_US",
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "crafted-itemlevel-260150-off_hand-crafted_myth-285-haste-mastery",
                    "itemId": "260150",
                    "slot": "off_hand",
                    "variantKey": "myth-285-haste-mastery",
                    "label": "Old stale variant",
                    "sourceType": "crafted",
                    "difficultyKey": "crafted_myth",
                    "itemLevel": 285,
                    "simcOptions": {"ilevel": "285", "crafted_stats": "36/49"},
                    "status": "verified",
                    "payload": {"statSource": "simulationcraft", "itemStats": [{"key": "intellect", "value": 1}]},
                },
            )

            def fake_stat_resolver(item, item_level, stat_option, track):
                return {
                    "itemStats": [{"key": "intellect", "label": "智力", "value": item_level}],
                    "statSummary": f"智力 {item_level}",
                }

            self.websim_payload.backfill_crafted_item_level_variants(
                conn,
                [
                    {
                        "itemId": "260150",
                        "slot": "main_hand",
                        "sourceLabel": "制造装备",
                        "supportsVoidUpgrade": True,
                        "allowedTracks": ["crafted_myth"],
                        "allowedCraftedStats": [
                            {"key": "haste-mastery", "label": "急速 + 精通", "value": "36/49"}
                        ],
                    }
                ],
                stat_resolver=fake_stat_resolver,
            )
            rows = conn.execute(
                """
                SELECT slot, item_level, status
                FROM websim_gear_variants
                WHERE source_type = 'crafted' AND item_id = '260150'
                ORDER BY slot, item_level
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(rows, [("main_hand", 285, "verified")])

    def test_replacement_candidate_limit_keeps_crafted_items(self):
        regular_items = [
            {
                "itemId": str(260500 + index),
                "slot": "main_hand",
                "sourceType": "raid",
                "ilevel": 298,
                "simcReady": True,
            }
            for index in range(12)
        ]
        crafted_item = {
            "itemId": "260600",
            "slot": "main_hand",
            "sourceType": "crafted",
            "ilevel": 295,
            "simcReady": True,
            "variants": [{"sourceType": "crafted", "itemLevel": 295}],
        }

        limited = self.websim_payload.limit_replacement_candidates(regular_items + [crafted_item], 12)

        self.assertEqual(len(limited), 13)
        self.assertEqual(limited[-1]["itemId"], "260600")

    def test_compact_crafted_candidate_filters_mixed_source_variants(self):
        item = {
            "itemId": "251105",
            "id": "251105",
            "slot": "off_hand",
            "displayName": "破法者之盾",
            "sourceType": "crafted",
            "variantSource": "crafted",
            "variantDifficultyKey": "crafted_void_upgrade",
            "sources": [
                {"id": "crafted-preview-251105", "sourceType": "crafted", "sourceLabel": "制造装备"},
                {"id": "loot-1300:2661:251105", "sourceType": "dungeon", "sourceLabel": "魔导师平台"},
            ],
            "variants": [
                {
                    "id": "crafted-itemlevel-251105-off_hand-crafted_void_upgrade-295-haste-mastery",
                    "sourceType": "crafted",
                    "difficultyKey": "crafted_void_upgrade",
                    "itemLevel": 295,
                    "simcOptions": {"ilevel": "295", "crafted_stats": "36/49"},
                    "status": "verified",
                    "payload": {
                        "craftedStatKey": "haste-mastery",
                        "craftedStatLabel": "急速 + 精通",
                        "statSummary": "智力 201；急速 35；精通 50",
                        "statSource": "simulationcraft",
                    },
                },
                {
                    "id": "loot-itemlevel-dungeon-1300-251105-off_hand-myth-289",
                    "sourceType": "dungeon",
                    "difficultyKey": "myth",
                    "itemLevel": 289,
                    "simcOptions": {"ilevel": "289"},
                    "status": "verified",
                },
            ],
        }

        compact = self.websim_payload.compact_gear_candidate(item)

        self.assertEqual(compact["sourceType"], "crafted")
        self.assertEqual([variant["itemLevel"] for variant in compact["variants"]], [295])
        self.assertEqual(compact["variants"][0]["difficultyKey"], "void_upgrade")
        self.assertEqual(len(compact["variants"][0]["craftedStatOptions"]), 1)
        self.assertEqual(compact["variants"][0]["craftedStatOptions"][0]["label"], "急速 + 精通")

    def test_crafted_preview_catalog_items_from_profile_presets_builds_governed_seed(self):
        import importlib
        from server import crafted_gear_backfill

        crafted_gear_backfill = importlib.reload(crafted_gear_backfill)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(season_id="17", season_label="Fresh Season")
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260200",
                {
                    "id": 260200,
                    "name": "Crafted Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"name": "Cloth"},
                    "quality": {"name": "Epic"},
                },
                {},
                fallback_name="Crafted Hood",
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260201",
                {
                    "id": 260201,
                    "name": "Crafted Focus",
                    "inventory_type": {"type": "HOLDABLE", "name": "Held In Off-hand"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"name": "Held In Off-hand"},
                    "quality": {"name": "Epic"},
                },
                {},
                fallback_name="Crafted Focus",
                locale="en_US",
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'now')
                """,
                (
                    "preset-crafted-preview",
                    "mage",
                    "frost",
                    "Crafted Preview",
                    "\n".join(
                        [
                            "head=crafted_hood,id=260200,ilevel=285,crafted_stats=32/49",
                            "off_hand=crafted_focus,id=260201,ilevel=295,bonus_id=8793/8960,crafted_stats=36/49",
                            "off_hand=crafted_focus,id=260201,ilevel=285,bonus_id=8793/8960,crafted_stats=32/40",
                            "waist=uncrafted_belt,id=260202,ilevel=285",
                        ]
                    ),
                    json.dumps({"source": "simulationcraft"}, ensure_ascii=False),
                ),
            )

            items = crafted_gear_backfill.crafted_catalog_items_from_simc_presets(conn)
        finally:
            conn.close()

        by_id = {item["itemId"]: item for item in items}
        self.assertEqual(set(by_id), {"260200", "260201"})
        hood = by_id["260200"]
        self.assertEqual(hood["sourceLabel"], "制造装备")
        self.assertEqual([track["difficultyKey"] for track in hood["allowedTracks"]], ["crafted_myth"])
        self.assertFalse(hood["supportsVoidUpgrade"])
        self.assertEqual(len(hood["allowedCraftedStats"]), 6)
        self.assertIn(
            ("crit-mastery", "暴击 + 精通", "32/49"),
            [(option["key"], option["label"], option["value"]) for option in hood["allowedCraftedStats"]],
        )
        self.assertEqual(hood["sourceRefs"][0]["sourceType"], "simulationcraft_profile_preset")

        focus = by_id["260201"]
        self.assertTrue(focus["supportsVoidUpgrade"])
        self.assertEqual(
            [track["difficultyKey"] for track in focus["allowedTracks"]],
            ["crafted_myth", "crafted_void_upgrade"],
        )
        self.assertEqual(len(focus["allowedCraftedStats"]), 6)
        self.assertIn(
            ("haste-versatility", "急速 + 全能", "36/40"),
            [(option["key"], option["label"], option["value"]) for option in focus["allowedCraftedStats"]],
        )

    def test_crafted_catalog_items_from_metadata_builds_full_slot_seed(self):
        import importlib
        from server import crafted_gear_backfill

        crafted_gear_backfill = importlib.reload(crafted_gear_backfill)
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(season_id="17", season_label="Fresh Season")
            self.websim_payload.save_active_season_payload(conn, season)

            def save_item(item_id, name, inventory_type, item_class, item_subclass, crafting_key="modified_crafting_stat"):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": inventory_type, "name": inventory_type},
                        "item_class": item_class,
                        "item_subclass": item_subclass,
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            crafting_key: {
                                "id": 32,
                                "name": "Critical Strike",
                            },
                            "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}],
                        },
                    },
                    {},
                    fallback_name=name,
                    locale="en_US",
                )

            save_item("260410", "Crafted Hood", "HEAD", {"id": 4, "name": "Armor"}, {"id": 1, "name": "Cloth"}, "modified_crafting_stats")
            save_item("260411", "Crafted Ring", "FINGER", {"id": 4, "name": "Armor"}, {"id": 0, "name": "Miscellaneous"})
            save_item("260412", "Crafted Spellblade", "WEAPON", {"id": 2, "name": "Weapon"}, {"id": 7, "name": "One-Handed Sword"})
            save_item("260413", "Crafted Shield", "SHIELD", {"id": 4, "name": "Armor"}, {"id": 6, "name": "Shield"})
            self.websim_payload.save_websim_item_metadata(
                conn,
                "251105",
                {
                    "id": 251105,
                    "name": "Ward of the Spellbreaker",
                    "inventory_type": {"type": "SHIELD", "name": "Off Hand"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 6, "name": "Shield"},
                    "quality": {"name": "Rare"},
                    "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                },
                {},
                fallback_name="Ward of the Spellbreaker",
                locale="en_US",
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260414",
                {
                    "id": 260414,
                    "name": "Plain Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                },
                {},
                fallback_name="Plain Hood",
                locale="en_US",
            )

            items = crafted_gear_backfill.crafted_catalog_items_from_metadata(conn)
        finally:
            conn.close()

        by_id = {item["itemId"]: item for item in items}
        self.assertEqual(set(by_id), {"251105", "260410", "260411", "260412", "260413"})
        self.assertEqual(by_id["260410"]["slot"], "head")
        self.assertEqual(by_id["260411"]["slot"], "finger1")
        self.assertEqual(by_id["251105"]["slot"], "off_hand")
        self.assertEqual(by_id["260413"]["slot"], "off_hand")
        self.assertEqual([track["difficultyKey"] for track in by_id["260410"]["allowedTracks"]], ["crafted_myth"])
        self.assertEqual([track["itemLevel"] for track in by_id["260410"]["allowedTracks"]], [285])
        self.assertEqual(
            [track["difficultyKey"] for track in by_id["260412"]["allowedTracks"]],
            ["crafted_myth", "crafted_void_upgrade"],
        )
        self.assertEqual(
            [track["difficultyKey"] for track in by_id["260413"]["allowedTracks"]],
            ["crafted_myth", "crafted_void_upgrade"],
        )
        self.assertEqual([track["itemLevel"] for track in by_id["260412"]["allowedTracks"]], [285, 295])
        self.assertEqual([track["itemLevel"] for track in by_id["251105"]["allowedTracks"]], [285, 295])
        self.assertEqual(len(by_id["260410"]["allowedCraftedStats"]), 6)
        self.assertEqual(by_id["260410"]["sourceRefs"][0]["sourceType"], "battle_net_item_metadata")
        self.assertEqual(by_id["251105"]["sourceRefs"][0]["sourceType"], "local_curated_crafted_catalog")
        self.assertEqual(by_id["260410"]["profession"], "metadata_catalog")

    def test_crafted_candidates_stay_visible_below_regular_item_level_floor(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(season_id="17", season_label="Fresh Season")
            self.websim_payload.save_active_season_payload(conn, season)
            for item_id, name in (("260300", "Raid Wrist"), ("260301", "Crafted Wrist")):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "WRIST", "name": "Wrist"},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 1, "name": "Cloth"},
                        "quality": {"name": "Epic"},
                        "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                    },
                    {},
                    fallback_name=name,
                    locale="en_US",
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "raid-260300",
                    "itemId": "260300",
                    "sourceType": "raid",
                    "sourceLabel": "Test Raid",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "raid-260300-myth",
                    "itemId": "260300",
                    "slot": "wrist",
                    "variantKey": "myth-289",
                    "label": "神话 289",
                    "sourceType": "raid",
                    "difficultyKey": "myth",
                    "itemLevel": 289,
                    "simcOptions": {"ilevel": "289", "bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [{"key": "intellect", "label": "智力", "value": 100}],
                    },
                },
            )

            def fake_stat_resolver(item, item_level, stat_option, track):
                return {
                    "itemStats": [
                        {"key": "intellect", "label": "智力", "value": item_level},
                        {"key": "haste", "label": "急速", "value": 42},
                    ],
                    "statSummary": f"智力 {item_level}；{stat_option['label']}",
                }

            self.websim_payload.backfill_crafted_item_level_variants(
                conn,
                [
                    {
                        "itemId": "260301",
                        "slot": "wrist",
                        "sourceLabel": "制造装备",
                        "profession": "tailoring",
                        "sourceRefs": [{"sourceType": "controlled_seed", "label": "受控制造业目录"}],
                        "allowedTracks": ["crafted_myth"],
                        "allowedCraftedStats": [
                            {"key": "crit-haste", "label": "暴击 + 急速", "value": "32/36"},
                            {"key": "crit-versatility", "label": "暴击 + 全能", "value": "32/40"},
                            {"key": "crit-mastery", "label": "暴击 + 精通", "value": "32/49"},
                            {"key": "haste-versatility", "label": "急速 + 全能", "value": "36/40"},
                            {"key": "haste-mastery", "label": "急速 + 精通", "value": "36/49"},
                            {"key": "versatility-mastery", "label": "全能 + 精通", "value": "40/49"},
                        ],
                    }
                ],
                stat_resolver=fake_stat_resolver,
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-260301",
                    "itemId": "260301",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Observed crafted wrist",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-260301",
                    "itemId": "260301",
                    "slot": "wrist",
                    "variantKey": "observed-285",
                    "label": "Observed 285",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 285,
                    "simcOptions": {"ilevel": "285", "bonus_id": "12214"},
                    "status": "verified",
                    "payload": {
                        "statSource": "simulationcraft",
                        "statDisplayStatus": "verified_variant",
                        "itemStats": [{"key": "intellect", "label": "智力", "value": 285}],
                    },
                },
            )
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        wrist_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "wrist")
        crafted = next(item for item in wrist_group["items"] if item["itemId"] == "260301")
        self.assertEqual(crafted["sourceType"], "crafted")
        self.assertEqual(crafted["variants"][0]["itemLevel"], 285)
        self.assertEqual(len(crafted["variants"][0]["craftedStatOptions"]), 6)

    def test_crafted_candidates_with_observed_refs_are_not_treated_as_observed_only_below_floor(self):
        item = {
            "slot": "wrist",
            "itemId": "260301",
            "sourceType": "crafted",
            "variantSource": "crafted",
            "ilevel": 285,
            "sources": [
                {"sourceType": "observed_profile", "sourceLabel": "Raider.IO observed"},
                {"sourceType": "crafted", "sourceLabel": "制造装备"},
            ],
            "variants": [
                {"sourceType": "observed_profile", "difficultyKey": "observed_profile", "itemLevel": 285},
                {"sourceType": "crafted", "difficultyKey": "crafted_myth", "itemLevel": 285},
            ],
        }

        self.assertFalse(
            self.websim_payload.observed_only_replacement_candidate_below_current_floor(
                item,
                minimum_observed_ilevel=289,
            )
        )

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

    def test_websim_talents_dedupes_same_template_signature_and_merges_sources(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            now = self.websim_payload.utc_now()
            shared_nodes = [
                {"id": "arcane-node", "rank": 1},
                {"id": "hero-node", "rank": 2},
            ]
            for template in [
                {
                    "id": "raiderio-shared",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "scenarioKey": "mythic_plus",
                    "name": "Raider.IO shared",
                    "flowLabel": "M+",
                    "sourceName": "Raider.IO",
                    "sourceUrl": "https://raider.io/shared",
                    "talentState": {"selectedNodes": shared_nodes},
                    "sampleCount": 5,
                    "maxKeyLevel": 24,
                    "analysisWindow": "fixture",
                    "sourceStatus": "synced",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
                {
                    "id": "wcl-shared",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "scenarioKey": "mythic_plus",
                    "name": "WCL shared",
                    "flowLabel": "M+",
                    "sourceName": "Warcraft Logs",
                    "sourceUrl": "https://www.warcraftlogs.com/reports/shared",
                    "talentState": {"selectedNodes": list(reversed(shared_nodes))},
                    "sampleCount": 30,
                    "maxKeyLevel": 20,
                    "analysisWindow": "fixture",
                    "sourceStatus": "partial",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
                {
                    "id": "raiderio-other",
                    "classKey": "mage",
                    "specKey": "fire",
                    "heroKey": "sunfury",
                    "scenarioKey": "mythic_plus",
                    "name": "Raider.IO other",
                    "flowLabel": "M+",
                    "sourceName": "Raider.IO",
                    "sourceUrl": "https://raider.io/other",
                    "talentState": {"selectedNodes": [{"id": "fire-node", "rank": 1}]},
                    "sampleCount": 4,
                    "maxKeyLevel": 21,
                    "analysisWindow": "fixture",
                    "sourceStatus": "synced",
                    "status": "verified",
                    "updatedAt": now,
                    "expiresAt": now,
                },
            ]:
                self.websim_payload.upsert_community_talent_template(conn, template)
            self.websim_payload.set_sync_state(
                conn,
                self.websim_payload.COMMUNITY_TALENT_SYNC_KEY,
                {
                    "sourceStatus": "synced",
                    "sources": {
                        "raiderio": {"status": "synced", "sourceName": "Raider.IO", "errors": []},
                        "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "errors": []},
                    },
                    "templates": {"total": 3, "verified": 3, "blocked": 0},
                    "checkedAt": now,
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_talents(conn, "mage", "arcane", "spellslinger")
        finally:
            conn.close()

        self.assertEqual(len(payload["communityTemplates"]), 2)
        shared = payload["communityTemplates"][0]
        self.assertEqual(shared["id"], "raiderio_shared")
        self.assertTrue(shared["signature"].startswith("talent:mage:arcane:spellslinger:"))
        self.assertEqual(shared["dedupedCount"], 2)
        self.assertEqual(
            {ref["sourceName"] for ref in shared["sourceRefs"]},
            {"Raider.IO", "Warcraft Logs"},
        )
        self.assertEqual(payload["communityTemplateSync"]["dedupedCount"], 2)
        self.assertEqual(payload["communityTemplateSync"]["hiddenDuplicateCount"], 1)

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

    def test_sync_websim_cache_emits_stage_progress_events(self):
        events = []

        payload = self.websim_payload.sync_websim_cache(
            self.db_path,
            include_blizzard=False,
            stage_callback=events.append,
        )

        event_keys = [(event["stage"], event["status"]) for event in events]
        self.assertIn(("simc", "start"), event_keys)
        self.assertIn(("simc", "complete"), event_keys)
        self.assertIn(("gear_catalog", "start"), event_keys)
        self.assertIn(("gear_catalog", "complete"), event_keys)
        self.assertIn(("websim_sync", "complete"), event_keys)
        self.assertEqual(payload["stages"], events)

    def test_sync_websim_cache_emits_blizzard_substage_progress_events(self):
        originals = {
            "sync_simc_generated_data": self.websim_payload.sync_simc_generated_data,
            "get_blizzard_access_token": self.websim_payload.get_blizzard_access_token,
            "sync_blizzard_journal": self.websim_payload.sync_blizzard_journal,
            "sync_blizzard_item_sets": self.websim_payload.sync_blizzard_item_sets,
            "sync_blizzard_preset_item_metadata": self.websim_payload.sync_blizzard_preset_item_metadata,
            "sync_blizzard_build_gear_item_metadata": self.websim_payload.sync_blizzard_build_gear_item_metadata,
            "sync_blizzard_spell_details": self.websim_payload.sync_blizzard_spell_details,
            "sync_blizzard_observed_item_metadata": self.websim_payload.sync_blizzard_observed_item_metadata,
            "sync_blizzard_gear_mod_option_metadata": self.websim_payload.sync_blizzard_gear_mod_option_metadata,
        }
        for name, original in originals.items():
            self.addCleanup(setattr, self.websim_payload, name, original)

        self.websim_payload.sync_simc_generated_data = lambda conn: {"talents": 1, "profiles": 0, "build": "test"}
        self.websim_payload.get_blizzard_access_token = lambda region="us": "token"
        self.websim_payload.sync_blizzard_journal = lambda conn, token, region="us", locale="zh_CN": {
            "instances": 1,
            "encounters": 1,
            "loot": 1,
            "items": 1,
            "blockers": [],
        }
        self.websim_payload.sync_blizzard_item_sets = lambda conn, token, region="us", locale="zh_CN", season=None: {
            "itemSets": 1,
            "setItems": 1,
            "itemMetadata": 1,
            "sources": 1,
            "variants": 1,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_preset_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 1,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_build_gear_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 1,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_spell_details = lambda conn, token, region="us", locale="zh_CN": {
            "spells": 1,
            "media": 1,
        }
        self.websim_payload.sync_blizzard_observed_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_gear_mod_option_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "skipped": 0,
            "options": 0,
            "errors": [],
        }

        events = []
        self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True, stage_callback=events.append)

        event_keys = [(event["stage"], event["status"]) for event in events]
        self.assertIn(("blizzard_journal", "start"), event_keys)
        self.assertIn(("blizzard_journal", "complete"), event_keys)
        self.assertIn(("blizzard_item_sets", "start"), event_keys)
        self.assertIn(("blizzard_item_sets", "complete"), event_keys)
        self.assertIn(("blizzard_preset_item_metadata", "start"), event_keys)
        self.assertIn(("blizzard_preset_item_metadata", "complete"), event_keys)
        self.assertIn(("blizzard_build_gear_item_metadata", "start"), event_keys)
        self.assertIn(("blizzard_build_gear_item_metadata", "complete"), event_keys)
        self.assertIn(("blizzard_spell_details", "start"), event_keys)
        self.assertIn(("blizzard_spell_details", "complete"), event_keys)

    def test_verified_loot_payload_includes_game_asset(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="test-season",
                season_label="Fresh Season",
                dungeons=[
                    {
                        "id": "fresh-dungeon",
                        "dungeonId": "fresh-dungeon",
                        "instanceId": "1300",
                        "name": "Fresh Dungeon",
                        "shortName": "Fresh Dungeon",
                        "timerSeconds": 2040,
                    }
                ],
            )
            season["raids"] = [
                {"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"},
                {"id": "1401", "instanceId": "1401", "name": "The Dreamrift", "category": "Raid"},
                {"id": "1402", "instanceId": "1402", "name": "March on Quel'Danas", "category": "Raid"},
                {"id": "1403", "instanceId": "1403", "name": "Sporefall", "category": "Raid"},
            ]
            self.websim_payload.save_active_season_payload(
                conn,
                season,
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

    def test_websim_gear_filters_localized_non_class_armor_verified_loot_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters Terrace"}],
                ),
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
            for item_id, name, subclass_id, subclass_name in (
                ("250701", "Localized Cloth Hood", 1, "\u5e03\u7532"),
                ("250702", "Localized Leather Mask", 2, "\u76ae\u7532"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "HEAD", "name": "\u5934\u90e8"},
                        "item_class": {"id": 4, "name": "\u62a4\u7532"},
                        "item_subclass": {"id": subclass_id, "name": subclass_name},
                        "quality": {"name": "\u53f2\u8bd7"},
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Head"}},
                    locale="zh_CN",
                )
                conn.execute(
                    """
                    INSERT INTO websim_loot (
                        id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                    ) VALUES (?, '1300', '9001', ?, ?, 'head', 'Epic', 'https://render.example/item.jpg', '{}', 'now')
                    """,
                    (f"loot-{item_id}", item_id, name),
                )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = [item["itemId"] for item in head_group["items"]]
        self.assertIn("250701", item_ids)
        self.assertNotIn("250702", item_ids)

    def test_websim_gear_filters_verified_loot_candidates_outside_active_season_instances(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="17",
                season_label="Fresh Season",
                dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters Terrace"}],
            )
            season["raids"] = [{"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"}]
            self.websim_payload.save_active_season_payload(conn, season)
            for instance_id, instance_name in (("1400", "The Voidspire"), ("1200", "Old Raid")):
                conn.execute(
                    """
                    INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                    VALUES (?, ?, 'Raid', '{}', 'now')
                    """,
                    (instance_id, instance_name),
                )
                conn.execute(
                    """
                    INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                    VALUES (?, ?, ?, '{}', 'now')
                    """,
                    (f"encounter-{instance_id}", instance_id, f"{instance_name} Boss"),
                )
            for item_id, item_name, instance_id in (
                ("250701", "Voidspire Hood", "1400"),
                ("250702", "Old Raid Hood", "1200"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": item_name,
                        "inventory_type": {"type": "HEAD", "name": "Head"},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 1, "name": "Cloth"},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                        },
                    },
                    fallback_name=item_name,
                    english_payload={"name": item_name, "inventory_type": {"name": "Head"}},
                    locale="en_US",
                )
                conn.execute(
                    """
                    INSERT INTO websim_loot (
                        id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'head', 'Epic', 'https://render.example/item.jpg', '{}', 'now')
                    """,
                    (f"loot-{item_id}", instance_id, f"encounter-{instance_id}", item_id, item_name),
                )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = [item["itemId"] for item in head_group["items"]]
        self.assertIn("250701", item_ids)
        self.assertNotIn("250702", item_ids)
        current_item = next(item for item in head_group["items"] if item["itemId"] == "250701")
        self.assertNotIn("statSummary", current_item)

    def test_websim_gear_filters_observed_variants_without_any_catalog_source(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters Terrace"}],
                ),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249999",
                {
                    "id": 249999,
                    "name": "Observed Only Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                fallback_name="Observed Only Hood",
                english_payload={"name": "Observed Only Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-head-249999-abcdef1234",
                    "itemId": "249999",
                    "slot": "head",
                    "variantKey": "observed-704-abcdef1234",
                    "label": "Observed 704",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 704,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [
                            {
                                "classKey": "mage",
                                "specKey": "frost",
                                "itemId": "249999",
                                "itemLevel": 704,
                            }
                        ],
                    },
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        item_ids = [item["itemId"] for item in head_group["items"]]
        self.assertNotIn("249999", item_ids)

    def test_websim_gear_labels_observed_only_candidates_as_source_pending_public_variant(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters Terrace"}],
                ),
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "249999",
                {
                    "id": 249999,
                    "name": "Observed Only Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                fallback_name="Observed Only Hood",
                english_payload={"name": "Observed Only Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            observed_ref = {
                "sourceName": "Raider.IO",
                "sourceStatus": "synced",
                "classKey": "mage",
                "specKey": "frost",
                "slot": "head",
                "itemId": "249999",
                "itemLevel": 704,
            }
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-249999",
                    "itemId": "249999",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO CN observed mage frost",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [observed_ref],
                    },
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-head-249999-abcdef1234",
                    "itemId": "249999",
                    "slot": "head",
                    "variantKey": "observed-704-abcdef1234",
                    "label": "Observed 704",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 704,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "statSummary": "智力 111",
                        "itemStats": [{"key": "intellect", "label": "Intellect", "value": 111}],
                        "observedProfileRefs": [observed_ref],
                    },
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        head_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "head")
        candidate = next(item for item in head_group["items"] if item["itemId"] == "249999")
        self.assertEqual(candidate["source"], "来源待补充")
        self.assertEqual(candidate["sourceType"], "catalog")
        self.assertEqual(candidate["variantSource"], "catalog")
        self.assertEqual(candidate["variantDifficultyKey"], "source_pending")
        self.assertEqual(candidate["variantDifficultyLabel"], "来源待补")
        self.assertEqual(candidate["variants"][0]["sourceType"], "catalog")
        self.assertEqual(candidate["variants"][0]["difficultyKey"], "source_pending")
        self.assertEqual(candidate["variants"][0]["difficultyLabel"], "来源待补")
        self.assertEqual(candidate["variants"][0]["statSummary"], "智力 111")
        self.assertEqual(candidate["variants"][0]["statDisplayStatus"], "verified_variant")
        self.assertEqual(candidate["variants"][0]["itemStats"][0]["value"], 111)
        self.assertEqual(candidate["observedProfileRefs"][0]["sourceName"], "Raider.IO")

    def test_websim_gear_marks_simc_ready_preset_candidates_with_source_reference(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters Terrace"}],
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (
                    'preset-untracked',
                    'mage',
                    'frost',
                    'Community Preset',
                    'wrist=untracked_cuffs,id=260001,ilevel=289,bonus_id=12345',
                    '{}',
                    'now'
                )
                """
            )
            for item_id, name in (
                ("260001", "Untracked Cuffs"),
                ("260002", "Current Season Cuffs"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "WRIST", "name": "Wrist"},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 1, "name": "Cloth"},
                        "quality": {"name": "Epic"},
                        "preview_item": {
                            "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                        },
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Wrist"}},
                    locale="en_US",
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-260002-wrist",
                    "itemId": "260002",
                    "sourceType": "dungeon",
                    "sourceLabel": "Arcane Warden - Magisters Terrace",
                    "instanceId": "1300",
                    "seasonRevision": "season-17-test",
                    "payload": {"seasonRevision": "season-17-test"},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-260002-wrist-observed",
                    "itemId": "260002",
                    "slot": "wrist",
                    "variantKey": "observed-289-current",
                    "label": "Observed 289",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 289,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "itemStats": [
                            {"key": "intellect", "label": "Intellect", "value": 111},
                            {"key": "stamina", "label": "Stamina", "value": 900},
                        ],
                    },
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        wrist_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "wrist")
        current_item = next(item for item in wrist_group["items"] if item["itemId"] == "260002")
        self.assertEqual(current_item["source"], "Arcane Warden - Magisters Terrace")
        self.assertEqual(current_item["sourceType"], "dungeon")
        self.assertEqual(current_item["variantSource"], "dungeon")
        self.assertEqual(current_item["variantDifficultyKey"], "dungeon")
        self.assertEqual(current_item["variantDifficultyLabel"], "大秘境")
        self.assertEqual(current_item["variants"][0]["sourceType"], "dungeon")
        self.assertEqual(current_item["variants"][0]["difficultyKey"], "dungeon")
        self.assertEqual(current_item["variants"][0]["difficultyLabel"], "大秘境")
        preset_item = next(item for item in wrist_group["items"] if item["itemId"] == "260001")
        self.assertEqual(preset_item["source"], "来源待补充")
        self.assertEqual(preset_item["sources"][0]["sourceType"], "simc_preset")
        self.assertEqual(preset_item["sources"][0]["sourceLabel"], "SimulationCraft preset: Community Preset")

    def test_websim_gear_keeps_crafted_preset_candidates_as_simc_preset_source(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_profile_presets (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (
                    'preset-crafted',
                    'shaman',
                    'enhancement',
                    'Crafted Preset',
                    'off_hand=crafted_axe,id=260003,bonus_id=8793/8960,crafted_stats=40/32,enchant_id=8039',
                    '{}',
                    'now'
                )
                """
            )
            self.websim_payload.save_websim_item_metadata(
                conn,
                "260003",
                {
                    "id": 260003,
                    "name": "Crafted Axe",
                    "inventory_type": {"type": "WEAPON", "name": "Weapon"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"id": 0, "name": "One-Handed Axe"},
                    "quality": {"name": "Epic"},
                },
                fallback_name="Crafted Axe",
                english_payload={"name": "Crafted Axe", "inventory_type": {"name": "Weapon"}},
                locale="en_US",
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "shaman", "enhancement", compact=True)
        finally:
            conn.close()

        offhand_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "off_hand")
        crafted_item = next(item for item in offhand_group["items"] if item["itemId"] == "260003")
        self.assertEqual(crafted_item["source"], "来源待补充")
        self.assertEqual(crafted_item["sourceType"], "simcPreset")
        self.assertEqual(crafted_item["sources"][0]["sourceType"], "simc_preset")
        self.assertEqual(crafted_item["sources"][0]["sourceLabel"], "SimulationCraft preset: Crafted Preset")
        self.assertEqual(crafted_item["crafted_stats"], "40/32")

    def test_compact_gear_candidate_labels_crafted_observed_variants_as_crafted(self):
        compact = self.websim_payload.compact_gear_candidate(
            {
                "slot": "wrist",
                "itemId": "237834",
                "name": "破法者的护腕",
                "source": "制造装备",
                "sourceType": "simcPreset",
                "variantSource": "observed_profile",
                "variantDifficultyKey": "observed_profile",
                "variantDifficultyLabel": "实装观测",
                "sources": [
                    {
                        "id": "crafted-237834",
                        "itemId": "237834",
                        "sourceType": "crafted",
                        "sourceLabel": "制造装备",
                    }
                ],
                "variants": [
                    {
                        "id": "observed-wrist-237834",
                        "itemId": "237834",
                        "slot": "wrist",
                        "variantKey": "observed-285",
                        "label": "Observed 285",
                        "sourceType": "observed_profile",
                        "difficultyKey": "observed_profile",
                        "itemLevel": 285,
                        "simcOptions": {"bonus_id": "12214"},
                        "status": "verified",
                    }
                ],
            }
        )

        self.assertEqual(compact["sourceType"], "crafted")
        self.assertEqual(compact["variantSource"], "crafted")
        self.assertEqual(compact["variantDifficultyKey"], "crafted")
        self.assertEqual(compact["variantDifficultyLabel"], "制造装备")
        self.assertEqual(compact["variants"][0]["sourceType"], "crafted")
        self.assertEqual(compact["variants"][0]["difficultyKey"], "crafted")
        self.assertEqual(compact["variants"][0]["difficultyLabel"], "制造装备")

    def test_websim_gear_ranks_verified_stat_candidates_above_pending_observed_variants(self):
        pending = {
            "slot": "feet",
            "itemId": "268282",
            "id": "268282",
            "name": "Pending High Item Level Boots",
            "sourceType": "catalog",
            "variantSource": "observed_profile",
            "variantStatus": "verified",
            "variantDifficultyKey": "observed_profile",
            "ilevel": 298,
            "bonus_id": "12345",
            "simcReady": True,
            "statDisplayStatus": "pending_current_variant",
            "blockers": ["SimulationCraft item stats"],
            "observedProfileRefs": [{"classKey": "mage", "specKey": "frost", "itemId": "268282"}],
        }
        verified = {
            "slot": "feet",
            "itemId": "249373",
            "id": "249373",
            "name": "Verified Lower Item Level Boots",
            "sourceType": "simcPreset",
            "source": "MID1_Mage_Frost",
            "variantStatus": "verified",
            "ilevel": 289,
            "bonus_id": "12345",
            "simcReady": True,
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "itemStats": [{"key": "intellect", "label": "Intellect", "value": 111}],
        }

        ranked = sorted(
            [pending, verified],
            key=self.websim_payload.gear_candidate_quality_score,
            reverse=True,
        )

        self.assertEqual(ranked[0]["itemId"], "249373")

    def test_websim_gear_ranks_verified_stat_source_reference_above_simc_ready_missing_stats(self):
        pending_ready = {
            "slot": "head",
            "itemId": "268283",
            "id": "268283",
            "name": "Pending SimC Ready Hood",
            "sourceType": "catalog",
            "variantSource": "observed_profile",
            "variantStatus": "verified",
            "variantDifficultyKey": "observed_profile",
            "ilevel": 298,
            "bonus_id": "12345",
            "simcReady": True,
            "statDisplayStatus": "pending_current_variant",
            "blockers": ["SimulationCraft item stats"],
            "observedProfileRefs": [{"classKey": "rogue", "specKey": "outlaw", "itemId": "268283"}],
        }
        verified_reference = {
            "slot": "head",
            "itemId": "151336",
            "id": "151336",
            "name": "Verified Source Reference Hood",
            "sourceType": "catalog",
            "sources": [{"sourceType": "dungeon", "sourceLabel": "Current Dungeon"}],
            "variantStatus": "partial",
            "simcReady": False,
            "statDisplayStatus": "verified_variant",
            "statSource": "simulationcraft",
            "itemStats": [{"key": "agility", "label": "Agility", "value": 111}],
            "blockers": ["ilevel", "bonus_id/gem_id/enchant_id"],
        }

        ranked = sorted(
            [pending_ready, verified_reference],
            key=self.websim_payload.gear_candidate_quality_score,
            reverse=True,
        )

        self.assertEqual(ranked[0]["itemId"], "151336")

    def test_websim_gear_filters_low_ilevel_observed_only_pve_candidates(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "161", "dungeonId": "161", "instanceId": "476", "name": "Skyreach"}],
                ),
            )
            for item_id, name, quality in (
                ("258575", "Rugged Scale Cloak", "Rare"),
                ("235499", "Reshii Wraps", "Artifact"),
            ):
                self.websim_payload.save_websim_item_metadata(
                    conn,
                    item_id,
                    {
                        "id": int(item_id),
                        "name": name,
                        "inventory_type": {"type": "CLOAK", "name": "Back"},
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 1, "name": "Cloth"},
                        "quality": {"name": quality},
                        "preview_item": {
                            "stats": [
                                {"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 100},
                                {"type": {"type": "STAMINA", "name": "Stamina"}, "value": 900},
                            ],
                        },
                    },
                    fallback_name=name,
                    english_payload={"name": name, "inventory_type": {"name": "Back"}},
                    locale="en_US",
                )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "loot-258575",
                    "itemId": "258575",
                    "sourceType": "dungeon",
                    "sourceLabel": "Ranjit - Skyreach",
                    "instanceId": "476",
                    "seasonRevision": "season-17-test",
                    "payload": {"seasonRevision": "season-17-test"},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "loot-258575-back-276",
                    "itemId": "258575",
                    "slot": "back",
                    "variantKey": "mythic-276",
                    "label": "Mythic 276",
                    "sourceType": "dungeon",
                    "difficultyKey": "mythic",
                    "itemLevel": 276,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                    "payload": {
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "itemStats": [
                            {"key": "intellect", "label": "Intellect", "value": 100},
                            {"key": "stamina", "label": "Stamina", "value": 900},
                        ],
                    },
                },
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "observed-source-235499",
                    "itemId": "235499",
                    "sourceType": "observed_profile",
                    "sourceLabel": "Raider.IO observed gear",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "observedProfileRefs": [
                            {
                                "classKey": "mage",
                                "specKey": "frost",
                                "slot": "back",
                                "itemId": "235499",
                                "itemLevel": 154,
                            }
                        ],
                    },
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "observed-mage-frost-back-235499",
                    "itemId": "235499",
                    "slot": "back",
                    "variantKey": "observed-154",
                    "label": "Observed 154",
                    "sourceType": "observed_profile",
                    "difficultyKey": "observed_profile",
                    "itemLevel": 154,
                    "simcOptions": {"bonus_id": "12399"},
                    "status": "verified",
                    "payload": {
                        "classKeys": ["mage"],
                        "specKeys": ["frost"],
                        "statDisplayStatus": "verified_variant",
                        "statSource": "simulationcraft",
                        "itemStats": [
                            {"key": "intellect", "label": "Intellect", "value": 8},
                            {"key": "stamina", "label": "Stamina", "value": 40},
                        ],
                        "observedProfileRefs": [
                            {
                                "classKey": "mage",
                                "specKey": "frost",
                                "slot": "back",
                                "itemId": "235499",
                                "itemLevel": 154,
                            }
                        ],
                    },
                },
            )
            conn.commit()
            payload = self.websim_payload.get_websim_gear(conn, "mage", "frost", compact=True)
        finally:
            conn.close()

        back_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "back")
        item_ids = [item["itemId"] for item in back_group["items"]]
        self.assertIn("258575", item_ids)
        self.assertNotIn("235499", item_ids)

    def test_sync_blizzard_journal_includes_current_season_raid_loot(self):
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
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": (
            [
                ({"id": "1300", "name": "Magisters' Terrace"}, "Dungeon"),
                ({"id": "1200", "name": "Old Vault"}, "Raid"),
                ({"id": "1400", "name": "The Voidspire"}, "Raid"),
                ({"id": "1302", "name": "Manaforge Omega"}, "Raid"),
            ],
            "Current Expansion",
        )

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
                    "name": "The Voidspire",
                    "category": {"name": "Raid"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9100"}, "name": "Vault Mage"}],
                }
            if path == "/data/wow/journal-instance/1302":
                return {
                    "id": 1302,
                    "name": "Manaforge Omega",
                    "category": {"name": "Raid"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9300"}, "name": "Dimensius"}],
                }
            if path == "/data/wow/journal-instance/1200":
                return {
                    "id": 1200,
                    "name": "Old Vault",
                    "category": {"name": "Raid"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9200"}, "name": "Old Mage"}],
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
            if path == "/data/wow/journal-encounter/9200":
                return {
                    "id": 9200,
                    "name": "Old Mage",
                    "items": [{"item": {"id": 250778, "name": "Old Hood"}}],
                }
            if path == "/data/wow/journal-encounter/9300":
                return {
                    "id": 9300,
                    "name": "Dimensius",
                    "items": [{"item": {"id": 250779, "name": "Wrong Season Hood"}}],
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
            season = self.websim_payload.get_active_season_payload(conn)
            instances = conn.execute("SELECT id, category FROM websim_instances ORDER BY id").fetchall()
            sources = conn.execute("SELECT item_id, source_type, source_label FROM websim_gear_sources ORDER BY item_id").fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["instances"], 2)
        self.assertEqual(counts["loot"], 2)
        self.assertEqual(
            [item["name"] for item in season["raids"]],
            ["The Voidspire", "The Dreamrift", "March on Quel'Danas", "Sporefall"],
        )
        self.assertEqual(season["raids"][0], {"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"})
        self.assertEqual(instances, [("1300", "Dungeon"), ("1400", "Raid")])
        self.assertIn(("250777", "raid", "Vault Mage - The Voidspire"), sources)
        self.assertNotIn(("250778", "raid", "Old Mage - Old Vault"), sources)
        self.assertNotIn(("250779", "raid", "Dimensius - Manaforge Omega"), sources)
        self.assertIn(self.websim_payload.CURRENT_SEASON_RAID_POOL_MISSING_BLOCKER, counts["blockers"])
        self.assertIn(self.websim_payload.CURRENT_SEASON_RAID_POOL_STALE_BLOCKER, counts["blockers"])

    def test_sync_blizzard_journal_preserves_existing_cache_when_aborted_mid_refresh(self):
        conn = sqlite3.connect(self.db_path)
        original_resolve = self.websim_payload.resolve_current_mythic_season
        original_selected_refs = self.websim_payload.selected_journal_instance_refs
        original_blizzard_get = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "resolve_current_mythic_season", original_resolve)
        self.addCleanup(setattr, self.websim_payload, "selected_journal_instance_refs", original_selected_refs)
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)

        self.websim_payload.resolve_current_mythic_season = lambda token, region="us", locale="zh_CN": self.websim_payload.current_season_payload(
            season_id="17",
            season_label="Fresh Season",
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": ([], "Current Expansion")

        def aborting_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            raise KeyboardInterrupt("operator stopped sync")

        self.websim_payload.blizzard_get = aborting_blizzard_get

        try:
            self.websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES ('1300', 'Magisters Terrace', 'Dungeon', '{}', 'old-sync')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES ('9001', '1300', 'Arcane Warden', '{}', 'old-sync')
                """
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (
                    '1300:9001:250222', '1300', '9001', '250222', 'Rift Bindings', 'wrist', 'Epic',
                    'https://render.example/item-250222.jpg', '{}', 'old-sync'
                )
                """
            )
            conn.commit()

            with self.assertRaises(KeyboardInterrupt):
                self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")

            instances = conn.execute("SELECT id, updated_at FROM websim_instances").fetchall()
            encounters = conn.execute("SELECT id, updated_at FROM websim_encounters").fetchall()
            loot = conn.execute("SELECT id, updated_at FROM websim_loot").fetchall()
        finally:
            conn.close()

        self.assertEqual(instances, [("1300", "old-sync")])
        self.assertEqual(encounters, [("9001", "old-sync")])
        self.assertEqual(loot, [("1300:9001:250222", "old-sync")])

    def test_sync_blizzard_journal_skips_non_equipment_loot_items(self):
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
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": ([], "Current Expansion")

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9001"}, "name": "Arcane Warden"}],
                }
            if path == "/data/wow/journal-encounter/9001":
                return {
                    "id": 9001,
                    "name": "Arcane Warden",
                    "items": [
                        {"item": {"id": 250222, "name": "Rift Bindings"}},
                        {"item": {"id": 190001, "name": "Arcane Prize Token"}},
                    ],
                }
            return {}

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            if str(item_id) == "190001":
                return {
                    "payload": {
                        "id": 190001,
                        "name": fallback_name or "Arcane Prize Token",
                        "item_class": {"id": 15, "name": "Miscellaneous"},
                        "item_subclass": {"id": 0, "name": "Junk"},
                        "quality": {"name": "Epic"},
                    },
                    "media": {"assets": [{"value": "https://render.example/non-gear.jpg"}]},
                    "englishPayload": {"name": fallback_name or "Arcane Prize Token"},
                    "locale": locale,
                    "fallbackName": fallback_name,
                }
            return {
                "payload": {
                    "id": int(item_id),
                    "name": fallback_name or "Rift Bindings",
                    "inventory_type": {"type": "WRIST", "name": "Wrist"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                "media": {"assets": [{"value": "https://render.example/item-250222.jpg"}]},
                "englishPayload": {"name": fallback_name or "Rift Bindings"},
                "locale": locale,
                "fallbackName": fallback_name,
            }

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            self.websim_payload.sync_websim_gear_catalog(conn, self.websim_payload.get_active_season_payload(conn))
            health = self.websim_payload.gear_catalog_health_payload(conn)
            loot_rows = conn.execute("SELECT item_id, slot FROM websim_loot ORDER BY item_id").fetchall()
            metadata_rows = conn.execute("SELECT id FROM websim_items ORDER BY id").fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["loot"], 1)
        self.assertEqual(counts["items"], 2)
        self.assertEqual(counts["skippedNonGearLoot"], 1)
        self.assertEqual(counts["skippedNonGearLootExamples"][0]["itemId"], "190001")
        self.assertEqual(loot_rows, [("250222", "wrist")])
        self.assertEqual(metadata_rows, [("190001",), ("250222",)])
        journal_loot = health["details"]["seasonSourceCoverage"]["journalLoot"]
        self.assertEqual(journal_loot["expectedItemCount"], 1)
        self.assertEqual(journal_loot["cachedItemCount"], 1)
        self.assertEqual(journal_loot["missingItemCount"], 0)

    def test_sync_blizzard_journal_persists_discovered_item_set_refs_to_active_season(self):
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
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": (
            [({"id": "1400", "name": "The Voidspire"}, "Raid")],
            "Current Expansion",
        )

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [],
                }
            if path == "/data/wow/journal-instance/1400":
                return {
                    "id": 1400,
                    "name": "The Voidspire",
                    "category": {"name": "Raid"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9100"}, "name": "Vault Mage"}],
                }
            if path == "/data/wow/journal-encounter/9100":
                return {
                    "id": 9100,
                    "name": "Vault Mage",
                    "items": [{"item": {"id": 250777, "name": "Catalog Hood"}}],
                }
            return {}

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            return {
                "payload": {
                    "id": int(item_id),
                    "name": fallback_name or f"Item {item_id}",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "item_set": {"id": 777, "name": "Ra-den's Chosen"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
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
            self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            season = self.websim_payload.get_active_season_payload(conn)
        finally:
            conn.close()

        self.assertEqual(season["itemSets"], [{"id": "777", "name": "Ra-den's Chosen"}])

    def test_sync_blizzard_journal_reports_truncated_season_coverage(self):
        conn = sqlite3.connect(self.db_path)
        original_resolve = self.websim_payload.resolve_current_mythic_season
        original_selected_refs = self.websim_payload.selected_journal_instance_refs
        original_blizzard_get = self.websim_payload.blizzard_get
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        self.addCleanup(setattr, self.websim_payload, "resolve_current_mythic_season", original_resolve)
        self.addCleanup(setattr, self.websim_payload, "selected_journal_instance_refs", original_selected_refs)
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)
        for key, value in {
            "WOW_WEBSIM_SYNC_INSTANCE_LIMIT": "1",
            "WOW_WEBSIM_SYNC_RAID_INSTANCE_LIMIT": "0",
            "WOW_WEBSIM_SYNC_ENCOUNTER_LIMIT": "1",
            "WOW_WEBSIM_SYNC_ITEM_LIMIT": "1",
        }.items():
            os.environ[key] = value
            self.addCleanup(os.environ.pop, key, None)

        self.websim_payload.resolve_current_mythic_season = lambda token, region="us", locale="zh_CN": self.websim_payload.current_season_payload(
            season_id="17",
            season_label="Fresh Season",
            dungeons=[
                {"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"},
                {"id": "560", "dungeonId": "560", "instanceId": "1301", "name": "Maisara Caverns"},
            ],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": (
            [({"id": "1400", "name": "The Voidspire"}, "Raid")],
            "Current Expansion",
        )

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [
                        {"key": {"href": "https://example.test/journal-encounter/9001"}, "name": "Arcane Warden"},
                        {"key": {"href": "https://example.test/journal-encounter/9002"}, "name": "Chronomancer"},
                    ],
                }
            if path == "/data/wow/journal-encounter/9001":
                return {
                    "id": 9001,
                    "name": "Arcane Warden",
                    "items": [
                        {"item": {"id": 250222, "name": "Rift Bindings"}},
                        {"item": {"id": 250223, "name": "Rift Cord"}},
                    ],
                }
            return {}

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = lambda token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot="": {
            "payload": {
                "id": int(item_id),
                "name": fallback_name or f"Item {item_id}",
                "inventory_type": {"type": "WRIST", "name": "Wrist"},
                "item_class": {"id": 4, "name": "Armor"},
                "item_subclass": {"id": 1, "name": "Cloth"},
                "quality": {"name": "Epic"},
                "preview_item": {
                    "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                },
            },
            "media": {},
            "englishPayload": {"name": fallback_name or f"Item {item_id}"},
            "locale": locale,
            "fallbackName": fallback_name,
        }

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
        finally:
            conn.close()

        self.assertTrue(counts["truncated"])
        self.assertEqual(counts["limits"]["instances"], 1)
        self.assertEqual(counts["truncation"]["dungeonInstances"], 1)
        self.assertEqual(counts["truncation"]["raidInstances"], 1)
        self.assertEqual(counts["truncation"]["encounters"], 1)
        self.assertEqual(counts["truncation"]["items"], 1)
        self.assertIn("Battle.net journal dungeon instance sync truncated: 1 not fetched", counts["blockers"])
        self.assertIn("Battle.net journal raid instance sync truncated: 1 not fetched", counts["blockers"])
        self.assertIn("Battle.net journal encounter sync truncated: 1 not fetched", counts["blockers"])
        self.assertIn("Battle.net journal item sync truncated: 1 not fetched", counts["blockers"])

    def test_sync_blizzard_journal_blocks_when_raid_instance_selection_fails(self):
        conn = sqlite3.connect(self.db_path)
        original_resolve = self.websim_payload.resolve_current_mythic_season
        original_selected_refs = self.websim_payload.selected_journal_instance_refs
        original_blizzard_get = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "resolve_current_mythic_season", original_resolve)
        self.addCleanup(setattr, self.websim_payload, "selected_journal_instance_refs", original_selected_refs)
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)

        self.websim_payload.resolve_current_mythic_season = lambda token, region="us", locale="zh_CN": self.websim_payload.current_season_payload(
            season_id="17",
            season_label="Fresh Season",
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )

        def fake_selected_refs(token, region="us", locale="zh_CN"):
            raise RuntimeError("journal expansion index api down")

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        self.websim_payload.selected_journal_instance_refs = fake_selected_refs
        self.websim_payload.blizzard_get = fake_blizzard_get

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            season = self.websim_payload.get_active_season_payload(conn)
        finally:
            conn.close()

        self.assertEqual(counts["instances"], 1)
        self.assertEqual(counts["raidInstances"], 0)
        self.assertEqual(counts["fetchFailureCount"], 1)
        self.assertEqual(counts["fetchFailures"][0]["type"], "raid_selection")
        self.assertIn(
            "Battle.net journal raid_selection journal-expansion fetch failed: journal expansion index api down",
            counts["blockers"],
        )
        self.assertIn(self.websim_payload.CURRENT_SEASON_RAID_POOL_MISSING_BLOCKER, counts["blockers"])
        self.assertEqual([item["name"] for item in season.get("raids") or []], self.websim_payload.MIDNIGHT_CURRENT_SEASON_RAIDS)

    def test_sync_blizzard_journal_blocks_when_journal_instance_fetch_fails(self):
        conn = sqlite3.connect(self.db_path)
        original_resolve = self.websim_payload.resolve_current_mythic_season
        original_selected_refs = self.websim_payload.selected_journal_instance_refs
        original_blizzard_get = self.websim_payload.blizzard_get
        self.addCleanup(setattr, self.websim_payload, "resolve_current_mythic_season", original_resolve)
        self.addCleanup(setattr, self.websim_payload, "selected_journal_instance_refs", original_selected_refs)
        self.addCleanup(setattr, self.websim_payload, "blizzard_get", original_blizzard_get)

        self.websim_payload.resolve_current_mythic_season = lambda token, region="us", locale="zh_CN": self.websim_payload.current_season_payload(
            season_id="17",
            season_label="Fresh Season",
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": ([], "Current Expansion")

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                raise RuntimeError("journal instance api down")
            raise AssertionError(f"unexpected Blizzard path {path}")

        self.websim_payload.blizzard_get = fake_blizzard_get

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            instance_payload = conn.execute(
                "SELECT payload_json FROM websim_instances WHERE id = '1300'"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(counts["instances"], 1)
        self.assertEqual(counts["fetchFailureCount"], 1)
        self.assertEqual(counts["fetchFailures"][0]["type"], "instance")
        self.assertEqual(counts["fetchFailures"][0]["id"], "1300")
        self.assertIn("Battle.net journal instance 1300 fetch failed: journal instance api down", counts["blockers"])
        self.assertIn("journal instance api down", instance_payload[0])

    def test_sync_blizzard_journal_blocks_when_journal_encounter_fetch_fails_and_continues(self):
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
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": ([], "Current Expansion")

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [
                        {"key": {"href": "https://example.test/journal-encounter/9001"}, "name": "Broken Warden"},
                        {"key": {"href": "https://example.test/journal-encounter/9002"}, "name": "Working Warden"},
                    ],
                }
            if path == "/data/wow/journal-encounter/9001":
                raise RuntimeError("journal encounter api down")
            if path == "/data/wow/journal-encounter/9002":
                return {
                    "id": 9002,
                    "name": "Working Warden",
                    "items": [{"item": {"id": 250222, "name": "Rift Bindings"}}],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = lambda token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot="": {
            "payload": {
                "id": int(item_id),
                "name": fallback_name or "Rift Bindings",
                "inventory_type": {"type": "WRIST", "name": "Wrist"},
                "item_class": {"id": 4, "name": "Armor"},
                "item_subclass": {"id": 1, "name": "Cloth"},
                "quality": {"name": "Epic"},
                "preview_item": {
                    "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                },
            },
            "media": {},
            "englishPayload": {"name": fallback_name or "Rift Bindings"},
            "locale": locale,
            "fallbackName": fallback_name,
        }

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            encounter_ids = [
                row[0]
                for row in conn.execute("SELECT id FROM websim_encounters ORDER BY id").fetchall()
            ]
            loot_rows = conn.execute("SELECT item_id, encounter_id FROM websim_loot ORDER BY item_id").fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["encounters"], 1)
        self.assertEqual(counts["loot"], 1)
        self.assertEqual(counts["fetchFailureCount"], 1)
        self.assertEqual(counts["fetchFailures"][0]["type"], "encounter")
        self.assertEqual(counts["fetchFailures"][0]["id"], "9001")
        self.assertIn("Battle.net journal encounter 9001 fetch failed: journal encounter api down", counts["blockers"])
        self.assertEqual(encounter_ids, ["9002"])
        self.assertEqual(loot_rows, [("250222", "9002")])

    def test_sync_blizzard_journal_blocks_when_item_metadata_fetch_fails_and_continues(self):
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
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": ([], "Current Expansion")

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9001"}, "name": "Arcane Warden"}],
                }
            if path == "/data/wow/journal-encounter/9001":
                return {
                    "id": 9001,
                    "name": "Arcane Warden",
                    "items": [
                        {"item": {"id": 250111, "name": "Broken Bindings"}},
                        {"item": {"id": 250222, "name": "Working Cord"}},
                    ],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            if str(item_id) == "250111":
                raise RuntimeError("item metadata api down")
            return {
                "payload": {
                    "id": int(item_id),
                    "name": fallback_name or "Working Cord",
                    "inventory_type": {"type": "WAIST", "name": "Waist"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                "media": {},
                "englishPayload": {"name": fallback_name or "Working Cord"},
                "locale": locale,
                "fallbackName": fallback_name,
            }

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        try:
            self.websim_payload.ensure_websim_tables(conn)
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            loot_rows = conn.execute("SELECT item_id, encounter_id FROM websim_loot ORDER BY item_id").fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["items"], 1)
        self.assertEqual(counts["loot"], 1)
        self.assertEqual(counts["fetchFailureCount"], 1)
        self.assertEqual(counts["fetchFailures"][0]["type"], "item")
        self.assertEqual(counts["fetchFailures"][0]["id"], "250111")
        self.assertEqual(counts["fetchFailures"][0]["encounterId"], "9001")
        self.assertEqual(counts["fetchFailures"][0]["instanceId"], "1300")
        self.assertIn("Battle.net journal item 250111 fetch failed: item metadata api down", counts["blockers"])
        self.assertEqual(loot_rows, [("250222", "9001")])

    def test_sync_blizzard_journal_reuses_cached_item_metadata_when_refresh_fails(self):
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
            dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
            locale=locale,
        )
        self.websim_payload.selected_journal_instance_refs = lambda token, region="us", locale="zh_CN": ([], "Current Expansion")

        def fake_blizzard_get(path, token, region="us", locale="zh_CN", params=None, namespace=None):
            if path == "/data/wow/journal-instance/1300":
                return {
                    "id": 1300,
                    "name": "Magisters' Terrace",
                    "category": {"name": "Dungeon"},
                    "encounters": [{"key": {"href": "https://example.test/journal-encounter/9001"}, "name": "Arcane Warden"}],
                }
            if path == "/data/wow/journal-encounter/9001":
                return {
                    "id": 9001,
                    "name": "Arcane Warden",
                    "items": [{"item": {"id": 250111, "name": "Cached Bindings"}}],
                }
            raise AssertionError(f"unexpected Blizzard path {path}")

        self.websim_payload.blizzard_get = fake_blizzard_get
        self.websim_payload.fetch_blizzard_item_metadata = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("item metadata api down")
        )

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250111",
                {
                    "id": 250111,
                    "name": "Cached Bindings",
                    "inventory_type": {"type": "WRIST", "name": "Wrist"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 111}],
                    },
                },
                media_payload={"assets": [{"value": "https://render.example/item-250111.jpg"}]},
                fallback_name="Cached Bindings",
                english_payload={"name": "Cached Bindings", "inventory_type": {"name": "Wrist"}},
                locale="en_US",
            )
            counts = self.websim_payload.sync_blizzard_journal(conn, "token", "us", "zh_CN")
            loot_rows = conn.execute("SELECT item_id, name, slot, encounter_id FROM websim_loot ORDER BY item_id").fetchall()
        finally:
            conn.close()

        self.assertEqual(counts["loot"], 1)
        self.assertEqual(counts["items"], 0)
        self.assertEqual(counts["cachedItems"], 1)
        self.assertEqual(counts["fetchFailureCount"], 1)
        self.assertEqual(counts["fetchFailures"][0]["type"], "item")
        self.assertEqual(counts["fetchFailures"][0]["id"], "250111")
        self.assertIn("Battle.net journal item 250111 fetch failed: item metadata api down", counts["blockers"])
        self.assertEqual(loot_rows, [("250111", "Cached Bindings", "wrist", "9001")])

    def test_sync_skips_blizzard_when_active_season_cache_is_fresh(self):
        conn = sqlite3.connect(self.db_path)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="test-season",
                season_label="Fresh Season",
                dungeons=[
                    {
                        "id": "fresh-dungeon",
                        "dungeonId": "fresh-dungeon",
                        "instanceId": "1300",
                        "name": "Fresh Dungeon",
                        "shortName": "Fresh Dungeon",
                        "timerSeconds": 2040,
                    }
                ],
            )
            season["raids"] = [
                {"id": "1400", "instanceId": "1400", "name": "The Voidspire", "category": "Raid"},
                {"id": "1401", "instanceId": "1401", "name": "The Dreamrift", "category": "Raid"},
                {"id": "1402", "instanceId": "1402", "name": "March on Quel'Danas", "category": "Raid"},
                {"id": "1403", "instanceId": "1403", "name": "Sporefall", "category": "Raid"},
            ]
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Catalog Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 321}],
                    },
                },
                fallback_name="Catalog Hood",
                english_payload={"name": "Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            for raid in season["raids"]:
                self.websim_payload.upsert_gear_source(
                    conn,
                    {
                        "id": f"manual-250777-{raid['instanceId']}",
                        "itemId": "250777",
                        "sourceType": "raid",
                        "sourceLabel": raid["name"],
                        "instanceId": raid["instanceId"],
                        "seasonRevision": season["seasonRevision"],
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
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250778",
                {
                    "id": 250778,
                    "name": "Catalog Bracers",
                    "inventory_type": {"type": "WRIST", "name": "Wrist"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 222}],
                    },
                },
                fallback_name="Catalog Bracers",
                english_payload={"name": "Catalog Bracers", "inventory_type": {"name": "Wrist"}},
                locale="en_US",
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "manual-250778",
                    "itemId": "250778",
                    "sourceType": "dungeon",
                    "sourceLabel": "Magisters' Terrace",
                    "instanceId": "1300",
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "manual-250778-heroic",
                    "itemId": "250778",
                    "slot": "wrist",
                    "variantKey": "heroic-707",
                    "label": "Heroic 707",
                    "sourceType": "dungeon",
                    "itemLevel": 707,
                    "simcOptions": {"bonus_id": "12345"},
                    "status": "verified",
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(
                    conn, self.websim_payload.get_active_season_payload(conn)
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

    def test_sync_websim_cache_enriches_observed_socket_options_with_blizzard_gem_metadata(self):
        import server.raiderio_payload as raiderio_payload

        conn = sqlite3.connect(self.db_path)
        original_sync_simc = self.websim_payload.sync_simc_generated_data
        original_token = self.websim_payload.get_blizzard_access_token
        original_journal = self.websim_payload.sync_blizzard_journal
        original_item_sets = self.websim_payload.sync_blizzard_item_sets
        original_preset_metadata = self.websim_payload.sync_blizzard_preset_item_metadata
        original_build_metadata = self.websim_payload.sync_blizzard_build_gear_item_metadata
        original_spells = self.websim_payload.sync_blizzard_spell_details
        original_fetch = self.websim_payload.fetch_blizzard_item_metadata
        original_raiderio = raiderio_payload.get_raiderio_payload
        self.addCleanup(setattr, self.websim_payload, "sync_simc_generated_data", original_sync_simc)
        self.addCleanup(setattr, self.websim_payload, "get_blizzard_access_token", original_token)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_journal", original_journal)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_item_sets", original_item_sets)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_preset_item_metadata", original_preset_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_build_gear_item_metadata", original_build_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_spell_details", original_spells)
        self.addCleanup(setattr, self.websim_payload, "fetch_blizzard_item_metadata", original_fetch)
        self.addCleanup(setattr, raiderio_payload, "get_raiderio_payload", original_raiderio)

        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        self.websim_payload.sync_simc_generated_data = lambda conn: {"talents": 1, "profiles": 1, "build": "test"}
        self.websim_payload.get_blizzard_access_token = lambda region="us": "token"
        self.websim_payload.sync_blizzard_journal = lambda conn, token, region="us", locale="zh_CN": {
            "instances": 0,
            "encounters": 0,
            "loot": 0,
            "items": 0,
        }
        self.websim_payload.sync_blizzard_item_sets = lambda conn, token, region="us", locale="zh_CN", season=None: {
            "itemSets": 0,
            "setItems": 0,
            "itemMetadata": 0,
            "sources": 0,
            "variants": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_preset_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_build_gear_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_spell_details = lambda conn, token, region="us", locale="zh_CN": {"spells": 0, "media": 0}

        raiderio_payload.get_raiderio_payload = lambda conn, allow_sync=False: {
            "sourceStatus": "verified",
            "checkedAt": "2026-06-21T00:00:00+00:00",
            "specs": {
                "mage:frost": {
                    "observedGear": [
                        {
                            "slot": "finger1",
                            "name": "Observed Catalog Band",
                            "itemId": 250777,
                            "itemLevel": 707,
                            "quality": "Epic",
                            "icon": "https://render.example/item-250777.jpg",
                            "bonuses": [12345],
                            "gems": [{"itemId": 240983, "itemLevel": 707}],
                            "sourceName": "Raider.IO CN profile gear",
                        }
                    ],
                }
            },
        }

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            self.assertEqual(str(item_id), "240983")
            return {
                "itemId": str(item_id),
                "payload": {
                    "id": int(item_id),
                    "name": "Quick Onyx",
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                "media": {"assets": [{"value": "https://render.example/gem-240983.jpg"}]},
                "englishPayload": {"name": "Quick Onyx"},
                "locale": locale,
                "fallbackName": fallback_name,
            }

        self.websim_payload.fetch_blizzard_item_metadata = fake_fetch

        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)
        conn = sqlite3.connect(self.db_path)
        try:
            socket_options = self.websim_payload.gear_catalog_mod_options_by_slot(conn, "socket")
            gem_metadata = self.websim_payload.existing_websim_item_metadata(conn, "240983")
        finally:
            conn.close()

        self.assertEqual(payload["gearModOptions"]["items"], 1)
        self.assertEqual(payload["gearModOptions"]["errors"], [])
        self.assertNotIn("missingMetadataCount", payload["gearCatalog"]["modOptionCoverage"]["socket"])
        self.assertNotIn("1 socket mod options missing Battle.net gem metadata", payload["gearCatalog"]["blockers"])
        option = socket_options["finger1"][0]
        self.assertEqual(option["name"], "Quick Onyx")
        self.assertEqual(option["iconUrl"], "https://render.example/gem-240983.jpg")
        self.assertEqual(option["metadataStatus"], "verified")
        self.assertEqual(gem_metadata["displayName"], "Quick Onyx")

    def test_sync_refreshes_blizzard_when_gear_catalog_is_partial_even_if_season_cache_is_fresh(self):
        conn = sqlite3.connect(self.db_path)
        original_sync_simc = self.websim_payload.sync_simc_generated_data
        original_credentials = self.websim_payload.blizzard_credentials_configured
        original_token = self.websim_payload.get_blizzard_access_token
        original_journal = self.websim_payload.sync_blizzard_journal
        original_item_sets = self.websim_payload.sync_blizzard_item_sets
        original_preset_metadata = self.websim_payload.sync_blizzard_preset_item_metadata
        original_build_metadata = self.websim_payload.sync_blizzard_build_gear_item_metadata
        original_spells = self.websim_payload.sync_blizzard_spell_details
        self.addCleanup(setattr, self.websim_payload, "sync_simc_generated_data", original_sync_simc)
        self.addCleanup(setattr, self.websim_payload, "blizzard_credentials_configured", original_credentials)
        self.addCleanup(setattr, self.websim_payload, "get_blizzard_access_token", original_token)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_journal", original_journal)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_item_sets", original_item_sets)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_preset_item_metadata", original_preset_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_build_gear_item_metadata", original_build_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_spell_details", original_spells)
        calls = {"journal": 0, "itemSets": 0}
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
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                {
                    "status": "partial",
                    "itemCount": 40,
                    "sourceCount": 40,
                    "variantCount": 40,
                    "verifiedCount": 0,
                    "partialCount": 40,
                    "blockedCount": 0,
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            conn.commit()
        finally:
            conn.close()

        self.websim_payload.sync_simc_generated_data = lambda conn: {"talents": 1, "profiles": 1, "build": "test"}
        self.websim_payload.blizzard_credentials_configured = lambda: True
        self.websim_payload.get_blizzard_access_token = lambda region="us": "token"

        def fake_sync_journal(conn, token, region="us", locale="zh_CN"):
            calls["journal"] += 1
            return {"instances": 0, "encounters": 0, "loot": 0, "items": 0}

        self.websim_payload.sync_blizzard_journal = fake_sync_journal
        self.websim_payload.sync_blizzard_item_sets = lambda conn, token, region="us", locale="zh_CN", season=None: (
            calls.__setitem__("itemSets", calls["itemSets"] + 1)
            or {"itemSets": 1, "setItems": 5, "itemMetadata": 5, "sources": 5, "variants": 5, "skipped": 0, "errors": []}
        )
        self.websim_payload.sync_blizzard_preset_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_build_gear_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_spell_details = lambda conn, token, region="us", locale="zh_CN": {"spells": 0, "media": 0}

        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)

        self.assertEqual(calls["journal"], 1)
        self.assertEqual(calls["itemSets"], 1)
        self.assertEqual(payload["itemSets"]["setItems"], 5)
        self.assertNotEqual(payload.get("blizzardSkipped"), "fresh-season-cache")
        self.assertFalse(payload["ok"])
        self.assertNotEqual(payload["gearCatalog"]["status"], "verified")
        self.assertIn("1 current season dungeon missing gear loot", payload["errors"])

    def test_sync_skips_blizzard_journal_when_only_simc_variants_are_partial(self):
        conn = sqlite3.connect(self.db_path)
        original_sync_simc = self.websim_payload.sync_simc_generated_data
        original_credentials = self.websim_payload.blizzard_credentials_configured
        original_token = self.websim_payload.get_blizzard_access_token
        original_journal = self.websim_payload.sync_blizzard_journal
        original_item_sets = self.websim_payload.sync_blizzard_item_sets
        original_preset_metadata = self.websim_payload.sync_blizzard_preset_item_metadata
        original_build_metadata = self.websim_payload.sync_blizzard_build_gear_item_metadata
        original_observed_metadata = self.websim_payload.sync_blizzard_observed_item_metadata
        original_mod_options = self.websim_payload.sync_blizzard_gear_mod_option_metadata
        original_spells = self.websim_payload.sync_blizzard_spell_details
        self.addCleanup(setattr, self.websim_payload, "sync_simc_generated_data", original_sync_simc)
        self.addCleanup(setattr, self.websim_payload, "blizzard_credentials_configured", original_credentials)
        self.addCleanup(setattr, self.websim_payload, "get_blizzard_access_token", original_token)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_journal", original_journal)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_item_sets", original_item_sets)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_preset_item_metadata", original_preset_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_build_gear_item_metadata", original_build_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_observed_item_metadata", original_observed_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_gear_mod_option_metadata", original_mod_options)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_spell_details", original_spells)
        calls = {"journal": 0, "itemSets": 0}
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
                season_id="test-season",
                season_label="Fresh Season",
                dungeons=[
                    {
                        "id": "fresh-dungeon",
                        "dungeonId": "fresh-dungeon",
                        "instanceId": "1300",
                        "name": "Fresh Dungeon",
                        "shortName": "Fresh Dungeon",
                        "timerSeconds": 2040,
                    }
                ],
            )
            self.websim_payload.save_active_season_payload(conn, season)
            self.websim_payload.save_websim_item_metadata(
                conn,
                "250888",
                {
                    "id": 250888,
                    "name": "Verified Loop",
                    "inventory_type": {"type": "FINGER", "name": "Finger"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 0, "name": "Miscellaneous"},
                    "quality": {"name": "Epic"},
                    "stats": [{"type": {"type": "HASTE_RATING", "name": "Haste"}, "value": 1024}],
                },
                {"assets": [{"value": "https://render.example/item-250888.jpg"}]},
                fallback_slot="finger1",
                english_payload={"name": "Verified Loop"},
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250888",
                    "itemId": "250888",
                    "sourceType": "dungeon",
                    "sourceLabel": "Fresh Dungeon",
                    "instanceId": "1300",
                    "seasonRevision": season["seasonRevision"],
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": "source-partial-250888-finger",
                    "itemId": "250888",
                    "slot": "finger1",
                    "variantKey": "needs-variant",
                    "label": "Needs variant",
                    "sourceType": "dungeon",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "simcOptions": {},
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                self.websim_payload.build_gear_catalog_sync_state(conn, season),
            )
            conn.commit()
        finally:
            conn.close()

        self.websim_payload.sync_simc_generated_data = lambda conn: {"talents": 1, "profiles": 1, "build": "test"}
        self.websim_payload.blizzard_credentials_configured = lambda: False
        self.websim_payload.get_blizzard_access_token = lambda region="us": "token"

        def fake_sync_journal(conn, token, region="us", locale="zh_CN"):
            calls["journal"] += 1
            return {"instances": 0, "encounters": 0, "loot": 0, "items": 0}

        def fake_sync_item_sets(conn, token, region="us", locale="zh_CN", season=None):
            calls["itemSets"] += 1
            return {"itemSets": 0, "setItems": 0, "itemMetadata": 0, "sources": 0, "variants": 0, "skipped": 0, "errors": []}

        self.websim_payload.sync_blizzard_journal = fake_sync_journal
        self.websim_payload.sync_blizzard_item_sets = fake_sync_item_sets
        self.websim_payload.sync_blizzard_preset_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_build_gear_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_observed_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_gear_mod_option_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "skipped": 0,
            "options": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_spell_details = lambda conn, token, region="us", locale="zh_CN": {
            "spells": 0,
            "media": 0,
        }

        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)

        self.assertEqual(calls["journal"], 0)
        self.assertEqual(calls["itemSets"], 0)
        self.assertEqual(payload.get("blizzardSkipped"), "fresh-season-cache")
        self.assertEqual(payload["gearCatalog"]["dataReadiness"]["status"], "verified")
        self.assertEqual(payload["gearCatalog"]["simulationReadiness"]["status"], "partial")

    def test_sync_skips_blizzard_journal_when_data_partial_only_needs_metadata_repair(self):
        conn = sqlite3.connect(self.db_path)
        original_sync_simc = self.websim_payload.sync_simc_generated_data
        original_credentials = self.websim_payload.blizzard_credentials_configured
        original_token = self.websim_payload.get_blizzard_access_token
        original_journal = self.websim_payload.sync_blizzard_journal
        original_item_sets = self.websim_payload.sync_blizzard_item_sets
        original_preset_metadata = self.websim_payload.sync_blizzard_preset_item_metadata
        original_build_metadata = self.websim_payload.sync_blizzard_build_gear_item_metadata
        original_observed_metadata = self.websim_payload.sync_blizzard_observed_item_metadata
        original_mod_options = self.websim_payload.sync_blizzard_gear_mod_option_metadata
        original_spells = self.websim_payload.sync_blizzard_spell_details
        original_catalog_state = self.websim_payload.build_gear_catalog_sync_state
        original_sync_catalog = self.websim_payload.sync_websim_gear_catalog
        self.addCleanup(setattr, self.websim_payload, "sync_simc_generated_data", original_sync_simc)
        self.addCleanup(setattr, self.websim_payload, "blizzard_credentials_configured", original_credentials)
        self.addCleanup(setattr, self.websim_payload, "get_blizzard_access_token", original_token)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_journal", original_journal)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_item_sets", original_item_sets)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_preset_item_metadata", original_preset_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_build_gear_item_metadata", original_build_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_observed_item_metadata", original_observed_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_gear_mod_option_metadata", original_mod_options)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_spell_details", original_spells)
        self.addCleanup(setattr, self.websim_payload, "build_gear_catalog_sync_state", original_catalog_state)
        self.addCleanup(setattr, self.websim_payload, "sync_websim_gear_catalog", original_sync_catalog)
        calls = {"journal": 0, "itemSets": 0, "modOptions": 0}
        try:
            self.websim_payload.ensure_websim_tables(conn)
            season = self.websim_payload.current_season_payload(
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
            )
            self.websim_payload.save_active_season_payload(conn, season)
            conn.commit()
        finally:
            conn.close()

        partial_data_state = {
            "status": "partial",
            "itemCount": 737,
            "sourceCount": 1214,
            "variantCount": 1093,
            "verifiedCount": 1093,
            "partialCount": 0,
            "blockedCount": 0,
            "dataReadiness": {
                "status": "partial",
                "metadataStatus": "verified",
                "sourceStatus": "partial",
                "seasonSourceStatus": "verified",
                "modOptionStatus": "partial",
                "blockers": [
                    "110 gear catalog items missing trusted drop source",
                    "33 socket mod options missing Battle.net gem metadata",
                ],
            },
            "simulationReadiness": {
                "status": "verified",
                "blockers": [],
                "verified": 1093,
                "partial": 0,
                "blocked": 0,
                "total": 1093,
            },
            "sourceGapCoverage": {"sourcePendingItemCount": 110},
            "modOptionCoverage": {"socket": {"missingMetadataCount": 33}},
            "blockers": [
                "110 gear catalog items missing trusted drop source",
                "33 socket mod options missing Battle.net gem metadata",
            ],
        }

        self.websim_payload.sync_simc_generated_data = lambda conn: {"talents": 1, "profiles": 1, "build": "test"}
        self.websim_payload.blizzard_credentials_configured = lambda: True
        self.websim_payload.get_blizzard_access_token = lambda region="us": "token"
        self.websim_payload.build_gear_catalog_sync_state = lambda conn, season=None: dict(partial_data_state)
        self.websim_payload.sync_websim_gear_catalog = lambda conn, season=None: dict(partial_data_state)
        self.websim_payload.sync_blizzard_journal = lambda conn, token, region="us", locale="zh_CN": (
            calls.__setitem__("journal", calls["journal"] + 1)
            or {"instances": 1, "encounters": 1, "loot": 1, "items": 1}
        )
        self.websim_payload.sync_blizzard_item_sets = lambda conn, token, region="us", locale="zh_CN", season=None: (
            calls.__setitem__("itemSets", calls["itemSets"] + 1)
            or {"itemSets": 0, "setItems": 0, "itemMetadata": 0, "sources": 0, "variants": 0, "skipped": 0, "errors": []}
        )
        self.websim_payload.sync_blizzard_preset_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_build_gear_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_observed_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_gear_mod_option_metadata = lambda conn, token, region="us", locale="zh_CN": (
            calls.__setitem__("modOptions", calls["modOptions"] + 1)
            or {"items": 0, "skipped": 0, "options": 33, "errors": []}
        )
        self.websim_payload.sync_blizzard_spell_details = lambda conn, token, region="us", locale="zh_CN": {
            "spells": 0,
            "media": 0,
        }

        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)

        self.assertEqual(calls["journal"], 0)
        self.assertEqual(calls["itemSets"], 0)
        self.assertEqual(calls["modOptions"], 1)
        self.assertEqual(payload.get("blizzardSkipped"), "fresh-season-cache")
        self.assertEqual(payload["gearCatalog"]["dataReadiness"]["sourceStatus"], "partial")
        self.assertEqual(payload["gearCatalog"]["dataReadiness"]["seasonSourceStatus"], "verified")
        self.assertEqual(payload["gearCatalog"]["dataReadiness"]["modOptionStatus"], "partial")

    def test_sync_websim_cache_blocks_when_blizzard_journal_sync_is_truncated(self):
        conn = sqlite3.connect(self.db_path)
        original_sync_simc = self.websim_payload.sync_simc_generated_data
        original_credentials = self.websim_payload.blizzard_credentials_configured
        original_token = self.websim_payload.get_blizzard_access_token
        original_journal = self.websim_payload.sync_blizzard_journal
        original_item_sets = self.websim_payload.sync_blizzard_item_sets
        original_preset_metadata = self.websim_payload.sync_blizzard_preset_item_metadata
        original_build_metadata = self.websim_payload.sync_blizzard_build_gear_item_metadata
        original_spells = self.websim_payload.sync_blizzard_spell_details
        self.addCleanup(setattr, self.websim_payload, "sync_simc_generated_data", original_sync_simc)
        self.addCleanup(setattr, self.websim_payload, "blizzard_credentials_configured", original_credentials)
        self.addCleanup(setattr, self.websim_payload, "get_blizzard_access_token", original_token)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_journal", original_journal)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_item_sets", original_item_sets)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_preset_item_metadata", original_preset_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_build_gear_item_metadata", original_build_metadata)
        self.addCleanup(setattr, self.websim_payload, "sync_blizzard_spell_details", original_spells)
        try:
            self.websim_payload.ensure_websim_tables(conn)
            self.websim_payload.save_active_season_payload(
                conn,
                self.websim_payload.current_season_payload(
                    season_id="17",
                    season_label="Fresh Season",
                    dungeons=[{"id": "558", "dungeonId": "558", "instanceId": "1300", "name": "Magisters' Terrace"}],
                ),
            )
            self.websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                {
                    "status": "partial",
                    "itemCount": 1,
                    "sourceCount": 1,
                    "variantCount": 1,
                    "verifiedCount": 0,
                    "partialCount": 1,
                    "blockedCount": 0,
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            conn.commit()
        finally:
            conn.close()

        self.websim_payload.sync_simc_generated_data = lambda conn: {"talents": 1, "profiles": 1, "build": "test"}
        self.websim_payload.blizzard_credentials_configured = lambda: True
        self.websim_payload.get_blizzard_access_token = lambda region="us": "token"
        self.websim_payload.sync_blizzard_journal = lambda conn, token, region="us", locale="zh_CN": {
            "instances": 1,
            "encounters": 1,
            "loot": 1,
            "items": 1,
            "truncated": True,
            "blockers": ["Battle.net journal item sync truncated: 1 not fetched"],
        }
        self.websim_payload.sync_blizzard_item_sets = lambda conn, token, region="us", locale="zh_CN", season=None: {
            "itemSets": 0,
            "setItems": 0,
            "itemMetadata": 0,
            "sources": 0,
            "variants": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_preset_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_build_gear_item_metadata = lambda conn, token, region="us", locale="zh_CN": {
            "items": 0,
            "aliases": 0,
            "skipped": 0,
            "searched": 0,
            "resolved": 0,
            "references": 0,
            "errors": [],
        }
        self.websim_payload.sync_blizzard_spell_details = lambda conn, token, region="us", locale="zh_CN": {"spells": 0, "media": 0}

        payload = self.websim_payload.sync_websim_cache(self.db_path, include_blizzard=True)

        self.assertFalse(payload["ok"])
        self.assertIn("Battle.net journal item sync truncated: 1 not fetched", payload["errors"])

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

    def test_backfill_official_item_level_variants_writes_confirmed_raid_tracks(self):
        conn = sqlite3.connect(self.db_path)
        self.websim_payload.ensure_websim_tables(conn)
        self.websim_payload.save_active_season_payload(
            conn,
            self.websim_payload.current_season_payload(
                season_id="17",
                season_label="Fresh Season",
                dungeons=[],
                raids=[{"id": "1314", "instanceId": "1314", "name": "The Dreamrift", "localizedName": "梦境裂隙"}],
            ),
        )
        conn.execute(
            """
            INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
            VALUES ('1314', '梦境裂隙', 'Raid', '{}', 'now')
            """
        )
        conn.execute(
            """
            INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
            VALUES ('2795', '1314', '奇美鲁斯，未梦之神', '{}', 'now')
            """
        )
        for item_id, name, slot in (
            ("249278", "艾蔑尖塔法杖", "main_hand"),
            ("249922", "艾蔑悔恨魔典", "off_hand"),
        ):
            self.websim_payload.save_websim_item_metadata(
                conn,
                item_id,
                {
                    "id": int(item_id),
                    "name": name,
                    "inventory_type": {"type": "WEAPON" if slot == "main_hand" else "HOLDABLE", "name": slot},
                    "item_class": {"id": 2 if slot == "main_hand" else 4, "name": "Weapon" if slot == "main_hand" else "Armor"},
                    "item_subclass": {"name": "Staff" if slot == "main_hand" else "Held In Off-hand"},
                    "quality": {"name": "Epic"},
                    "preview_item": {"stats": [{"type": {"type": "STAMINA", "name": "Stamina"}, "value": 10}]},
                },
                fallback_name=name,
                locale="zh_CN",
            )
            conn.execute(
                """
                INSERT INTO websim_loot
                (id, instance_id, encounter_id, item_id, name, slot, quality, icon_url, payload_json, updated_at)
                VALUES (?, '1314', '2795', ?, ?, ?, '史诗', '', '{}', 'now')
                """,
                (f"1314:2795:{item_id}", item_id, name, slot),
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": f"loot-1314:2795:{item_id}",
                    "itemId": item_id,
                    "sourceType": "raid",
                    "sourceLabel": "奇美鲁斯，未梦之神 - 梦境裂隙",
                    "instanceId": "1314",
                    "encounterId": "2795",
                    "seasonRevision": "season-17-test",
                    "payload": {"seasonRevision": "season-17-test"},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": f"loot-partial-{item_id}-{slot}",
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": "needs-variant",
                    "label": "难度 / 装等待补",
                    "sourceType": "raid",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                    "payload": {"seasonRevision": "season-17-test"},
                },
            )

        def fake_stat_resolver(item, item_level, track):
            return {
                "itemStats": [{"key": "stamina", "label": "耐力", "value": item_level}],
                "statSummary": f"耐力 {item_level}",
                "simcProfile": f"{item['simcSlot']}=item_{item['itemId']},id={item['itemId']},ilevel={item_level}",
            }

        result = self.websim_payload.backfill_official_item_level_variants_for_instance(
            conn,
            "1314",
            source_type="raid",
            stat_resolver=fake_stat_resolver,
        )

        self.assertEqual(result["items"], 2)
        self.assertEqual(result["verifiedVariants"], 7)
        self.assertEqual(result["removedPendingVariants"], 2)
        remaining_placeholders = conn.execute(
            """
            SELECT COUNT(1)
            FROM websim_gear_variants
            WHERE source_type = 'raid'
              AND item_level <= 0
              AND (variant_key = 'needs-variant' OR difficulty_key = 'needs-variant')
            """
        ).fetchone()[0]
        self.assertEqual(remaining_placeholders, 0)
        rows = conn.execute(
            """
            SELECT item_id, difficulty_key, item_level, status, simc_options_json, payload_json
            FROM websim_gear_variants
            WHERE id LIKE 'loot-itemlevel-raid-%'
            ORDER BY item_id, item_level
            """
        ).fetchall()
        by_item = {}
        for item_id, difficulty_key, item_level, status, simc_options_json, payload_json in rows:
            by_item.setdefault(item_id, []).append((difficulty_key, item_level, status, simc_options_json, payload_json))
        self.assertEqual([level for _key, level, _status, _options, _payload in by_item["249278"]], [263, 276, 289, 298])
        self.assertEqual([level for _key, level, _status, _options, _payload in by_item["249922"]], [263, 276, 289])
        void_payload = json.loads(by_item["249278"][-1][4])
        self.assertEqual(void_payload["derivedVariantSource"], "simulationcraft_item_level_probe")
        self.assertEqual(void_payload["statSource"], "simulationcraft")
        self.assertEqual(void_payload["statDisplayStatus"], "verified_variant")
        self.assertTrue(void_payload["simcIlevelOnly"])
        self.assertEqual(json.loads(by_item["249278"][-1][3]), {"ilevel": "298"})

    def test_backfill_official_item_level_variants_writes_tier_set_tracks(self):
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.websim_payload.ensure_websim_tables(conn)
        season = self.websim_payload.current_season_payload(
            season_id="17",
            season_label="season-mn-1",
        )
        season["itemSets"] = [{"id": "1986", "name": "盲誓的重负"}]
        season_revision = season["seasonRevision"]
        self.websim_payload.save_active_season_payload(conn, season)
        conn.execute(
            """
            INSERT INTO websim_item_sets
            (id, name, season_revision, source, status, payload_json, updated_at)
            VALUES ('1986', '盲誓的重负', ?, 'battle_net_item_set', 'verified', '{}', 'now')
            """,
            (season_revision,),
        )
        for item_id, name, slot in (
            ("250054", "盲誓法衣", "chest"),
            ("250055", "盲誓护腿", "legs"),
        ):
            self.websim_payload.save_websim_item_metadata(
                conn,
                item_id,
                {
                    "id": int(item_id),
                    "name": name,
                    "inventory_type": {"type": "ROBE" if slot == "chest" else "LEGS", "name": slot},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {"stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 10}]},
                },
                fallback_name=name,
                locale="zh_CN",
            )
            self.websim_payload.upsert_websim_item_set_item(
                conn,
                "1986",
                {"itemId": item_id, "name": name},
                slot,
            )
            self.websim_payload.upsert_gear_source(
                conn,
                {
                    "id": f"set-1986-{item_id}",
                    "itemId": item_id,
                    "sourceType": "tier_set",
                    "sourceLabel": "盲誓的重负",
                    "seasonRevision": season_revision,
                    "payload": {"seasonRevision": season_revision, "setId": "1986", "setName": "盲誓的重负"},
                },
            )
            self.websim_payload.upsert_gear_variant(
                conn,
                {
                    "id": f"set-partial-1986-{item_id}-{slot}",
                    "itemId": item_id,
                    "slot": slot,
                    "variantKey": "needs-variant",
                    "label": "套装装等 / 难度待补",
                    "sourceType": "tier_set",
                    "difficultyKey": "needs-variant",
                    "itemLevel": 0,
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                    "payload": {"seasonRevision": season_revision, "setId": "1986", "setName": "盲誓的重负"},
                },
            )
        self.websim_payload.upsert_gear_variant(
            conn,
            {
                "id": "set-observed-250054-chest-298",
                "itemId": "250054",
                "slot": "chest",
                "variantKey": "observed-298",
                "label": "Observed 298",
                "sourceType": "tier_set",
                "difficultyKey": "observed_profile",
                "itemLevel": 298,
                "simcOptions": {"bonus_id": "13336/13575"},
                "status": "verified",
                "payload": {
                    "setId": "1986",
                    "setName": "盲誓的重负",
                    "statSource": "simulationcraft",
                    "statDisplayStatus": "verified_variant",
                    "itemStats": [{"key": "intellect", "label": "智力", "value": 135}],
                    "statSummary": "智力 135",
                    "seasonRevision": season_revision,
                },
            },
        )
        self.websim_payload.upsert_gear_variant(
            conn,
            {
                "id": "observed-priest-shadow-chest-250054-298",
                "itemId": "250054",
                "slot": "chest",
                "variantKey": "observed-298-shadow",
                "label": "Observed 298",
                "sourceType": "observed_profile",
                "difficultyKey": "observed_profile",
                "itemLevel": 298,
                "simcOptions": {"bonus_id": "13336/13575", "gem_id": "240983"},
                "status": "verified",
                "payload": {
                    "classKeys": ["priest"],
                    "specKeys": ["shadow"],
                    "statSource": "simulationcraft",
                    "statDisplayStatus": "verified_variant",
                    "itemStats": [{"key": "intellect", "label": "智力", "value": 135}],
                    "statSummary": "智力 135",
                    "seasonRevision": season_revision,
                },
            },
        )

        def fake_stat_resolver(item, item_level, track):
            return {
                "itemStats": [{"key": "intellect", "label": "智力", "value": item_level}],
                "statSummary": f"智力 {item_level}",
                "simcProfile": f"{item['simcSlot']}=item_{item['itemId']},id={item['itemId']},ilevel={item_level}",
            }

        result = self.websim_payload.backfill_official_item_level_variants_for_tier_sets(
            conn,
            set_ids=["1986"],
            stat_resolver=fake_stat_resolver,
        )

        self.assertEqual(result["items"], 2)
        self.assertEqual(result["verifiedVariants"], 7)
        rows = conn.execute(
            """
            SELECT item_id, difficulty_key, item_level, status, simc_options_json, payload_json
            FROM websim_gear_variants
            WHERE id LIKE 'set-itemlevel-tier_set-1986-%'
            ORDER BY item_id, item_level
            """
        ).fetchall()
        by_item = {}
        for item_id, difficulty_key, item_level, status, simc_options_json, payload_json in rows:
            by_item.setdefault(item_id, []).append((difficulty_key, item_level, status, simc_options_json, payload_json))
        self.assertEqual([level for _key, level, _status, _options, _payload in by_item["250054"]], [263, 276, 289, 298])
        self.assertEqual([level for _key, level, _status, _options, _payload in by_item["250055"]], [263, 276, 289])
        self.assertEqual(json.loads(by_item["250054"][-1][3]), {"ilevel": "298"})
        void_payload = json.loads(by_item["250054"][-1][4])
        self.assertEqual(void_payload["officialVariantSource"], "tier_set")
        self.assertEqual(void_payload["derivedVariantSource"], "simulationcraft_item_level_probe")
        self.assertEqual(void_payload["setName"], "盲誓的重负")
        self.assertEqual(void_payload["statSummary"], "智力 298")
        remaining_placeholders = conn.execute(
            """
            SELECT COUNT(1)
            FROM websim_gear_variants
            WHERE id IN ('set-partial-1986-250054-chest', 'set-partial-1986-250055-legs')
            """
        ).fetchone()[0]
        self.assertEqual(remaining_placeholders, 0)
        payload = self.websim_payload.get_websim_gear(conn, "priest", "shadow", compact=True)
        chest_group = next(group for group in payload["replacementCandidates"] if group["slot"] == "chest")
        tier_item = next(item for item in chest_group["items"] if item["itemId"] == "250054")
        self.assertEqual(
            [variant["itemLevel"] for variant in tier_item["variants"]],
            [298, 289, 276, 263],
        )
        self.assertEqual(tier_item["variants"][0]["difficultyLabel"], "虚空晋升")
        self.assertEqual(tier_item["variants"][0]["statSummary"], "智力 298")

    def test_tier_set_void_upgrade_requires_verified_current_season_evidence(self):
        conn = sqlite3.connect(self.db_path)
        self.addCleanup(conn.close)
        self.websim_payload.ensure_websim_tables(conn)
        season = self.websim_payload.current_season_payload(
            season_id="17",
            season_label="season-mn-1",
        )
        season["itemSets"] = [{"id": "1986", "name": "盲誓的重负"}]
        season_revision = season["seasonRevision"]
        self.websim_payload.save_active_season_payload(conn, season)
        self.websim_payload.upsert_gear_variant(
            conn,
            {
                "id": "observed-current-partial-250054",
                "itemId": "250054",
                "slot": "chest",
                "variantKey": "observed-298-partial",
                "label": "Observed 298",
                "sourceType": "observed_profile",
                "difficultyKey": "observed_profile",
                "itemLevel": 298,
                "status": "partial",
                "payload": {"seasonRevision": season_revision},
            },
        )
        self.websim_payload.upsert_gear_variant(
            conn,
            {
                "id": "observed-old-verified-250054",
                "itemId": "250054",
                "slot": "chest",
                "variantKey": "observed-298-old",
                "label": "Observed 298",
                "sourceType": "observed_profile",
                "difficultyKey": "observed_profile",
                "itemLevel": 298,
                "status": "verified",
                "payload": {
                    "seasonRevision": "season-old",
                    "itemStats": [{"key": "intellect", "label": "智力", "value": 135}],
                    "statSummary": "智力 135",
                },
            },
        )

        self.assertFalse(self.websim_payload.tier_set_item_has_void_upgrade_evidence(conn, "250054"))
        self.assertEqual(
            [track["itemLevel"] for track in self.websim_payload.official_item_level_tracks_for_tier_set_item(conn, "250054")],
            [263, 276, 289],
        )

        self.websim_payload.upsert_gear_variant(
            conn,
            {
                "id": "observed-current-verified-250054",
                "itemId": "250054",
                "slot": "chest",
                "variantKey": "observed-298-current",
                "label": "Observed 298",
                "sourceType": "observed_profile",
                "difficultyKey": "observed_profile",
                "itemLevel": 298,
                "status": "verified",
                "payload": {
                    "seasonRevision": season_revision,
                    "itemStats": [{"key": "intellect", "label": "智力", "value": 135}],
                    "statSummary": "智力 135",
                },
            },
        )

        self.assertTrue(self.websim_payload.tier_set_item_has_void_upgrade_evidence(conn, "250054"))
        self.assertEqual(
            [track["itemLevel"] for track in self.websim_payload.official_item_level_tracks_for_tier_set_item(conn, "250054")],
            [263, 276, 289, 298],
        )

    def test_catalog_variant_usable_allows_accepted_item_level_probe(self):
        self.assertTrue(
            self.websim_payload.catalog_variant_usable_for_replacement(
                {
                    "status": "verified",
                    "difficultyKey": "void_upgrade",
                    "simcIlevelOnly": True,
                    "payload": {
                        "simcIlevelOnly": True,
                        "derivedVariantSource": "simulationcraft_item_level_probe",
                        "itemStats": [{"id": "haste", "amount": 100}],
                    },
                }
            )
        )

    def test_catalog_variant_usable_rejects_partial_item_level_probe_without_stats(self):
        self.assertFalse(
            self.websim_payload.catalog_variant_usable_for_replacement(
                {
                    "status": "partial",
                    "difficultyKey": "void_upgrade",
                    "simcIlevelOnly": True,
                    "payload": {
                        "simcIlevelOnly": True,
                        "derivedVariantSource": "simulationcraft_item_level_probe",
                        "itemStats": [],
                        "blockers": ["SimC JSON did not include target item stats"],
                    },
                }
            )
        )

    def test_item_level_probe_profile_uses_safe_generated_item_name(self):
        conn = sqlite3.connect(self.db_path)
        self.websim_payload.ensure_websim_tables(conn)
        conn.execute(
            """
            INSERT INTO websim_profile_presets
            (id, class_key, spec_key, name, profile, payload_json, updated_at)
            VALUES ('mage-frost', 'mage', 'frost', 'Mage Frost', ?, '{}', 'now')
            """,
            ("mage=\"Mage Frost\"\nspec=frost\nlevel=90\nhead=old_hat,id=1,ilevel=1\n",),
        )

        profile, class_key, spec_key, item_line = self.websim_payload.simc_profile_with_item_level_probe(
            conn,
            {
                "itemId": "249373",
                "name": "梦境灼烧长靴",
                "slot": "feet",
                "metadataPayload": {
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"name": "Cloth"},
                },
            },
            289,
        )

        self.assertEqual((class_key, spec_key), ("mage", "frost"))
        self.assertIn("feet=item_249373,id=249373,ilevel=289", item_line)
        self.assertIn(item_line, profile)
        self.assertIn("iterations=1", profile)
        self.assertIn("max_time=1", profile)
        self.assertIn("calculate_scale_factors=0", profile)

    def test_run_websim_simcraft_process_passes_blizzard_api_key_to_simc_home(self):
        observed = {}

        def fake_run(args, **kwargs):
            env = kwargs.get("env") or {}
            home = env.get("HOME")
            self.assertTrue(home)
            observed["apiKey"] = (Path(home) / ".simc_apikey").read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch.dict(
            os.environ,
            {
                "WOW_BLIZZARD_CLIENT_ID": "test-client",
                "WOW_BLIZZARD_CLIENT_SECRET": "test-secret",
            },
        ):
            with patch.object(self.websim_payload.subprocess, "run", side_effect=fake_run):
                result = self.websim_payload.run_websim_simcraft_process("/bin/simc", "profile", 5)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(observed["apiKey"], "test-client:test-secret\n")

    def test_item_level_probe_keeps_offhand_for_one_hand_warglaive(self):
        conn = sqlite3.connect(self.db_path)
        self.websim_payload.ensure_websim_tables(conn)
        conn.execute(
            """
            INSERT INTO websim_profile_presets
            (id, class_key, spec_key, name, profile, payload_json, updated_at)
            VALUES ('dh-havoc', 'demonhunter', 'havoc', 'DH Havoc', ?, '{}', 'now')
            """,
            (
                "demonhunter=\"DH Havoc\"\n"
                "spec=havoc\n"
                "level=90\n"
                "main_hand=old_glaive,id=1,ilevel=1\n"
                "off_hand=old_offhand,id=2,ilevel=1\n"
            ,),
        )

        profile, _class_key, _spec_key, item_line = self.websim_payload.simc_profile_with_item_level_probe(
            conn,
            {
                "itemId": "260408",
                "name": "泯光哀歌",
                "slot": "main_hand",
                "metadataPayload": {
                    "inventory_type": {"type": "WEAPON", "name": "Main Hand"},
                    "item_class": {"id": 2, "name": "Weapon"},
                    "item_subclass": {"name": "Warglaive"},
                    "preview_item": {"stats": [{"type": {"type": "AGILITY"}, "value": 9}]},
                },
            },
            298,
        )

        self.assertIn("main_hand=item_260408,id=260408,ilevel=298", item_line)
        self.assertIn("off_hand=old_offhand,id=2,ilevel=1", profile)


if __name__ == "__main__":
    unittest.main()

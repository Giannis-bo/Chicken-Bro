import os
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SIMC_AGENT_SPEC_CASES = [
    ("死亡骑士", "鲜血", "deathknight", "blood"),
    ("死亡骑士", "冰霜", "deathknight", "frost"),
    ("死亡骑士", "邪恶", "deathknight", "unholy"),
    ("恶魔猎手", "浩劫", "demonhunter", "havoc"),
    ("恶魔猎手", "复仇", "demonhunter", "vengeance"),
    ("德鲁伊", "平衡", "druid", "balance"),
    ("德鲁伊", "野性", "druid", "feral"),
    ("德鲁伊", "守护", "druid", "guardian"),
    ("德鲁伊", "恢复", "druid", "restoration"),
    ("唤魔师", "湮灭", "evoker", "devastation"),
    ("唤魔师", "恩护", "evoker", "preservation"),
    ("唤魔师", "增辉", "evoker", "augmentation"),
    ("猎人", "野兽控制", "hunter", "beast_mastery"),
    ("猎人", "射击", "hunter", "marksmanship"),
    ("猎人", "生存", "hunter", "survival"),
    ("法师", "奥术", "mage", "arcane"),
    ("法师", "火焰", "mage", "fire"),
    ("法师", "冰霜", "mage", "frost"),
    ("武僧", "酒仙", "monk", "brewmaster"),
    ("武僧", "织雾", "monk", "mistweaver"),
    ("武僧", "踏风", "monk", "windwalker"),
    ("圣骑士", "神圣", "paladin", "holy"),
    ("圣骑士", "防护", "paladin", "protection"),
    ("圣骑士", "惩戒", "paladin", "retribution"),
    ("牧师", "戒律", "priest", "discipline"),
    ("牧师", "神圣", "priest", "holy"),
    ("牧师", "暗影", "priest", "shadow"),
    ("潜行者", "刺杀", "rogue", "assassination"),
    ("潜行者", "狂徒", "rogue", "outlaw"),
    ("潜行者", "敏锐", "rogue", "subtlety"),
    ("萨满祭司", "元素", "shaman", "elemental"),
    ("萨满祭司", "增强", "shaman", "enhancement"),
    ("萨满祭司", "恢复", "shaman", "restoration"),
    ("术士", "痛苦", "warlock", "affliction"),
    ("术士", "恶魔学识", "warlock", "demonology"),
    ("术士", "毁灭", "warlock", "destruction"),
    ("战士", "武器", "warrior", "arms"),
    ("战士", "狂怒", "warrior", "fury"),
    ("战士", "防护", "warrior", "protection"),
]


class NewsBackendTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["WOW_NEWS_DB"] = str(Path(self.tmp.name) / "news.sqlite3")

        import importlib
        import server.news_backend as backend

        self.backend = importlib.reload(backend)
        self.backend.init_db()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("WOW_NEWS_DB", None)

    def seed_verified_season(self):
        from server.websim_payload import current_season_payload, save_active_season_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            save_active_season_payload(conn, current_season_payload())
            conn.commit()

    def patch_simc_confirmation_llm(self, response):
        import server.simulator_payload as simulator_payload

        original_call_chat_completion = simulator_payload.call_chat_completion

        def fake_call_chat_completion(system_prompt, user_prompt, temperature=0.2):
            payload = response(system_prompt, user_prompt, temperature) if callable(response) else response
            return {
                "called": True,
                "model": "fake",
                "content": json.dumps(payload, ensure_ascii=False),
                "error": "",
            }

        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)
        simulator_payload.call_chat_completion = fake_call_chat_completion

    def confirmation_response(self, status="needs_clarification", missing_slots=None, question=""):
        return {
            "status": status,
            "intent": "baseline",
            "filledSlots": {},
            "missingSlots": missing_slots or [],
            "question": question or "还差天赋导入码和手选装备数据。",
            "quickReplies": ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"],
        }

    def test_get_article_detail_by_id_returns_source_evidence(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "article-1",
                    "官方热修：2026 年 6 月 3 日",
                    "这里会列出与《魔兽世界》相关问题的热修。",
                    "职业强度变化",
                    "正式服",
                    '["class-change"]',
                    96,
                    "Blizzard News",
                    "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
                    "2026-06-06",
                    "暴雪官方 World of Warcraft 新闻列表页自动采集。",
                    "中文正文：这条官方热修资讯汇总了《魔兽世界》近期问题修正，适合关注职业调整和正式服改动的玩家查看。",
                    "Hotfixes: June 3, 2026",
                    "Here you will find a list of hotfixes.",
                    "Original excerpt: Here you will find a list of hotfixes that address various issues related to World of Warcraft: Midnight.",
                    "2026-06-09T03:33:40+00:00",
                ),
            )
            conn.commit()

        detail = self.backend.get_article_detail("article-1")

        self.assertEqual(detail["id"], "article-1")
        self.assertEqual(detail["title"], "官方热修：2026 年 6 月 3 日")
        self.assertIn("中文正文", detail["bodyZh"])
        self.assertEqual(detail["originalTitle"], "Hotfixes: June 3, 2026")
        self.assertIn("Here you will find", detail["originalBody"])
        self.assertEqual(detail["sourceName"], "Blizzard News")
        self.assertEqual(detail["publishedAt"], "2026-06-06")
        self.assertEqual(detail["sourceUrl"], "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026")

    def test_get_article_detail_by_id_returns_none_for_missing_article(self):
        self.assertIsNone(self.backend.get_article_detail("missing"))

    def test_refresh_mode_validation_accepts_only_known_public_modes(self):
        self.assertEqual(self.backend.normalize_refresh_mode("manual"), "manual")
        self.assertEqual(self.backend.normalize_refresh_mode("scheduled"), "scheduled")
        self.assertIsNone(self.backend.normalize_refresh_mode("unexpected"))

    def test_refresh_run_records_visible_translation_quality_summary(self):
        self.backend.refresh_articles("manual")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            row = conn.execute(
                """
                SELECT message FROM news_refresh_runs
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()

        message = json.loads(row[0])
        self.assertIn("translationIssueCount", message)
        self.assertIn("translationIssues", message)
        self.assertIsInstance(message["translationIssues"], list)

    def test_latest_refresh_run_payload_exposes_translation_quality_summary(self):
        self.backend.refresh_articles("manual")

        payload = self.backend.latest_refresh_run_payload()

        self.assertEqual(payload["refreshMode"], "manual")
        self.assertGreater(payload["acceptedCount"], 0)
        self.assertIn("refreshedAt", payload)
        self.assertIn("translationIssueCount", payload)
        self.assertIn("translationIssues", payload)
        self.assertIsInstance(payload["translationIssues"], list)

    def test_list_articles_supports_metric_and_channel_filters_without_duplicates(self):
        articles = [
            ("all-1", "Article one", "Summary one", "正式服动态", "正式服", "[]", 80, "Blizzard News", "https://worldofwarcraft.blizzard.com/news/1001/article-one", "2026-06-09", "Source one."),
            ("all-2", "Article two", "Summary two", "测试服前瞻", "测试服", '["ptr"]', 78, "Blizzard News", "https://worldofwarcraft.blizzard.com/news/1002/article-two", "2026-06-08", "Source two."),
            ("all-3", "Article three", "Summary three", "职业强度变化", "正式服", '["class-change"]', 76, "Blizzard News", "https://worldofwarcraft.blizzard.com/news/1003/article-three", "2026-06-07", "Source three."),
            ("dup-a", "Hotfixes", "Summary duplicate A", "职业强度变化", "正式服", '["class-change"]', 70, "Blizzard News", "https://worldofwarcraft.blizzard.com/news/1004/hotfixes-a", "2026-06-06", "Source duplicate A."),
            ("dup-b", "Hotfixes", "Summary duplicate B", "职业强度变化", "正式服", '["class-change"]', 71, "Blizzard News", "https://worldofwarcraft.blizzard.com/en-us/news/1004/hotfixes-b", "2026-06-06", "Source duplicate B."),
        ]
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            for article in articles:
                conn.execute(
                    """
                    INSERT INTO news_articles (
                        id, title, summary, channel, category, tags_json, importance,
                        source_name, source_url, published_at, source_note, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*article, "2026-06-09T03:33:40+00:00"),
                )
            conn.commit()

        all_payload = self.backend.build_article_list_payload({"type": "metric", "key": "today"})
        ptr_payload = self.backend.build_article_list_payload({"type": "metric", "key": "ptr"})
        class_payload = self.backend.build_article_list_payload({"type": "metric", "key": "class-change"})
        channel_payload = self.backend.build_article_list_payload({"type": "channel", "value": "正式服动态"})

        self.assertEqual(all_payload["title"], "今日更新")
        self.assertEqual(len(all_payload["articles"]), 4)
        self.assertEqual(len({article["sourceUrl"] for article in all_payload["articles"]}), 4)
        self.assertEqual([article["channel"] for article in ptr_payload["articles"]], ["测试服前瞻"])
        self.assertTrue(all("class-change" in article["tags"] for article in class_payload["articles"]))
        self.assertEqual([article["id"] for article in channel_payload["articles"]], ["all-1"])

    def test_backend_exposes_specialization_payloads_from_shared_data_modules(self):
        home = self.backend.get_builds_home_payload()
        intel = self.backend.get_builds_intel_payload()
        detail = self.backend.get_builds_detail_payload("法师-冰霜")

        self.assertEqual(home["navTitle"], "职业专精")
        self.assertEqual(home["dataStatus"], "blocked")
        self.assertEqual([item["key"] for item in home["quickActions"]], ["talents", "gear", "statWeights", "rotation"])
        self.assertEqual(len(home["classOptions"]), 13)
        self.assertEqual(intel["items"], [])
        self.assertEqual(detail["details"], {})

        self.seed_verified_season()
        home = self.backend.get_builds_home_payload()
        intel = self.backend.get_builds_intel_payload()
        detail = self.backend.get_builds_detail_payload("法师-冰霜")

        self.assertEqual(home["dataStatus"], "verified")
        self.assertEqual(home["seasonRevision"], detail["seasonRevision"])
        self.assertGreaterEqual(len(intel["items"]), 5)
        self.assertEqual(detail["id"], "法师-冰霜")
        self.assertIn("talents", detail["details"])
        self.assertRegex(detail["details"]["talents"]["sourceUrl"], r"^https://")

    def test_backend_exposes_pve_home_and_module_payloads_from_shared_data_modules(self):
        home = self.backend.get_pve_home_payload()
        module = self.backend.get_pve_module_payload("bossGuides")

        self.assertEqual(home["navTitle"], "副本")
        self.assertEqual(home["dataStatus"], "blocked")
        self.assertEqual(home["zones"], [])
        self.assertEqual(module["items"], [])
        self.assertEqual(module["itemCount"], 0)

        self.seed_verified_season()
        home = self.backend.get_pve_home_payload()
        module = self.backend.get_pve_module_payload("bossGuides")

        self.assertEqual(home["dataStatus"], "verified")
        self.assertEqual([zone["title"] for zone in home["zones"]], ["大秘境专区", "团队 raid 专区"])
        self.assertEqual(module["key"], "bossGuides")
        self.assertEqual(module["seasonRevision"], home["seasonRevision"])
        self.assertEqual(module["navTitle"], "boss攻略")
        self.assertGreater(len(module["items"]), 0)
        self.assertRegex(module["items"][0]["sourceUrl"], r"^https://")

    def test_backend_exposes_simulator_home_and_llm_ready_analysis(self):
        home = self.backend.build_simulator_home_payload()
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft",
                "character": "冰法样例",
                "profile": "talents=CAE\ngear_ilvl=700",
                "question": "帮我比较属性收益",
            }
        )

        self.assertEqual(home["navTitle"], "智能分析")
        self.assertNotIn("metrics", home)
        self.assertEqual(
            [module["title"] for module in home["analysisModules"]],
            ["模拟 SimC", "分析 WCL", "任务列表"],
        )
        self.assertTrue(any(action["key"] == "simc" for action in home["quickActions"]))
        self.assertEqual(analysis["mode"], "simcraft")
        self.assertEqual(analysis["status"], "ready")
        self.assertGreater(len(analysis["recommendations"]), 0)
        self.assertIn("prompt", analysis["llm"])
        self.assertIn("simcraft", analysis["capabilities"])

    def test_simulator_prompt_with_embedded_profile_runs_simcraft_and_returns_conclusion(self):
        simc_bin = Path(self.tmp.name) / "fake-simc"
        captured_profile = Path(self.tmp.name) / "captured-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. 冰法样例 123456 dps\\nScale Factors:\\nintellect=9.1 haste=6.4 mastery=5.7\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft",
                    "prompt": "帮我跑一下单体 5 分钟，并解释属性收益\n```simc\nmage=\"冰法样例\"\ntalents=CAE\ngear_ilvl=700\n```",
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertTrue(analysis["simulation"]["ran"])
        self.assertIn('mage="冰法样例"', captured_profile.read_text(encoding="utf-8"))
        self.assertIn("123456", analysis["simulation"]["summary"])
        self.assertTrue(any("123456" in item for item in analysis["recommendations"]))
        self.assertEqual(analysis["request"]["profileSource"], "prompt")
        self.assertEqual([stage["key"] for stage in analysis["stages"]], ["profile_check", "simc_execution", "ai_interpretation"])
        self.assertEqual(analysis["stages"][0]["status"], "passed")
        self.assertEqual(analysis["stages"][0]["executor"], "backend")
        self.assertEqual(analysis["stages"][1]["status"], "completed")
        self.assertEqual(analysis["stages"][1]["executor"], "simcraft")
        self.assertEqual(analysis["stages"][1]["metric"], "123456")
        self.assertEqual(analysis["stages"][2]["executor"], "llm")

    def test_simulator_parses_dps_from_full_simcraft_output_before_truncating_summary(self):
        simc_bin = Path(self.tmp.name) / "fake-long-simc"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            "python3 - <<'PY'\n"
            "print('warmup line ' * 500)\n"
            "print('Player: LongOutputMage')\n"
            "print('  DPS=77777.123 DPS-Error=0/0.00%')\n"
            "PY\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft",
                    "profile": "mage=\"LongOutputMage\"\ntalents=CAE\ngear_ilvl=700",
                    "question": "跑一次长输出 profile",
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertTrue(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["metrics"]["dps"], "77777.123")
        self.assertLessEqual(len(analysis["simulation"]["summary"]), 4000)

    def test_simulator_natural_language_without_profile_does_not_run_simcraft(self):
        simc_bin = Path(self.tmp.name) / "fake-simc-should-not-run"
        captured_profile = Path(self.tmp.name) / "unexpected-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS=999999\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft",
                    "prompt": "装等290风暴元素萨，帮我模拟一下单体输出",
                    "runSimulation": True,
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertFalse(captured_profile.exists())
        self.assertFalse(analysis["request"]["runSimulation"])
        self.assertEqual(analysis["request"]["profileSource"], "none")
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["error"], "missing simcraft profile")
        self.assertIn("缺少可模拟模板", analysis["llm"]["prompt"])
        self.assertTrue(any("未执行 SimC" in item for item in analysis["recommendations"]))
        self.assertEqual([stage["key"] for stage in analysis["stages"]], ["profile_check", "simc_execution", "ai_interpretation"])
        self.assertEqual(analysis["stages"][0]["status"], "blocked")
        self.assertEqual(analysis["stages"][0]["summary"], "缺少完整 SimCraft profile")
        self.assertEqual(analysis["stages"][1]["status"], "skipped")
        self.assertIn("missing simcraft profile", analysis["stages"][1]["summary"])
        self.assertIn(analysis["stages"][2]["status"], {"completed", "skipped"})
        self.assertEqual(analysis["stages"][2]["executor"], "llm")

    def test_simc_agent_generates_template_from_natural_language(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["talents", "gear"],
                question="已识别冰霜法师单体属性收益；还差天赋导入码和手选装备数据。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "我是710冰法，想知道急速还是精通收益高，主要打单体",
            }
        )

        self.assertEqual(analysis["mode"], "simcraft_agent")
        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["round"], 1)
        self.assertEqual(analysis["agent"]["intent"], "stat_weights")
        self.assertEqual(analysis["agent"]["missingSlots"], ["talents", "gear"])
        self.assertFalse(analysis["agent"]["validation"]["passed"])
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertEqual(analysis["request"]["profileSource"], "generated")
        self.assertEqual(analysis["request"]["profile"], "")
        self.assertEqual(analysis["agent"]["draftProfile"], "")
        self.assertEqual(analysis["agent"]["filledSlots"]["class"], "mage")
        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "frost")
        self.assertEqual(analysis["agent"]["filledSlots"]["itemLevel"], 710)
        self.assertTrue(analysis["llm"]["called"])
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertIn("missing talents", analysis["simulation"]["error"])

    def test_simc_agent_confirm_only_recognizes_tianqi_unholy_dk_without_irrelevant_replies(self):
        self.patch_simc_confirmation_llm(
            {
                "status": "needs_clarification",
                "intent": "baseline",
                "filledSlots": {
                    "class": "deathknight",
                    "classLabel": "死亡骑士",
                    "spec": "unholy",
                    "specLabel": "邪恶",
                    "heroTalent": "天启",
                    "itemLevel": 278,
                    "scenario": "大秘境多目标",
                    "targets": 5,
                    "durationSeconds": 300,
                },
                "missingSlots": ["talents", "gear"],
                "question": "已识别：278 装等邪恶死亡骑士（天启流派）、大秘境 AOE。还差天赋导入码和手选装备数据，才能生成可复核 SimC profile。",
                "quickReplies": ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"],
            }
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "278天启邪DK，大秘境AOE 什么DPS合格？",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["filledSlots"]["class"], "deathknight")
        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "unholy")
        self.assertEqual(analysis["agent"]["filledSlots"]["heroTalent"], "天启")
        self.assertEqual(analysis["agent"]["filledSlots"]["itemLevel"], 278)
        self.assertEqual(analysis["agent"]["missingSlots"], ["talents", "gear"])
        self.assertEqual(analysis["agent"]["quickReplies"], ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"])
        self.assertNotRegex("\n".join(analysis["agent"]["quickReplies"]), "冰法|元素萨|恶魔术|惩戒")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertFalse(analysis["request"]["runSimulation"])
        self.assertEqual(analysis["mythicPlusReference"]["specKey"], "deathknight-unholy")

    def test_simc_agent_confirmation_fails_closed_on_invalid_llm_json(self):
        import server.simulator_payload as simulator_payload

        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: {
            "called": True,
            "model": "fake",
            "content": "我觉得可以直接跑",
            "error": "",
        }
        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "278天启邪DK，大秘境AOE 什么DPS合格？",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "confirmation_failed")
        self.assertEqual(analysis["agent"]["quickReplies"], [])
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertIn("重试", analysis["agent"]["question"])
        self.assertTrue(analysis["llm"]["called"])

    def test_simc_agent_uses_build_context_for_talent_and_gear_linkage(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["gear"],
                question="已读取天赋导入码；还差手选装备数据。",
            )
        )
        build_context = {
            "specId": "法师-冰霜",
            "className": "法师",
            "specName": "冰霜",
            "role": "远程输出",
            "activeQueryKey": "gear",
            "sourceName": "Mythicstats + Wowhead",
            "publishedAt": "2026-06-09",
            "analysisWindow": "近 14 天高层大秘境样本",
            "details": {
                "talents": {
                    "importCode": "CAE_CONTEXT",
                    "coreTalents": ["Freezing Rain", "Splitting Ice"],
                    "sourceName": "Wowhead",
                },
                "gear": {
                    "gear": [
                        {"slot": "饰品", "name": "Gaze of the Alnseer", "source": "Mythicstats top trinket"},
                        {"slot": "武器", "name": "Umbral Spire of Zuraal", "source": "Zuraal"},
                    ]
                },
                "statWeights": {
                    "stats": [
                        {"name": "Critical Strike", "value": "950", "percent": 95},
                        {"name": "Mastery", "value": "803", "percent": 80},
                    ]
                },
            },
        }

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "请按职业专精页里的方案，比较这套装备的大秘境 AOE 收益",
                "buildContext": build_context,
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["filledSlots"]["class"], "mage")
        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "frost")
        self.assertEqual(analysis["request"]["buildContext"]["specId"], "法师-冰霜")
        self.assertIn("gear", analysis["agent"]["missingSlots"])
        self.assertNotIn("Gaze of the Alnseer=", analysis["agent"]["draftProfile"])
        self.assertTrue(analysis["llm"]["called"])

    def test_simc_agent_builds_assembled_profile_from_selected_gear(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(status="template_ready", missing_slots=[], question="")
        )
        build_context = {
            "specId": "法师-冰霜",
            "className": "法师",
            "specName": "冰霜",
            "role": "远程输出",
            "activeQueryKey": "gear",
            "details": {
                "talents": {"importCode": "CAE_CONTEXT"},
                "gear": {
                    "simcItems": [
                        {
                            "slot": "main_hand",
                            "name": "Prodigious Gene Splicer",
                            "id": 237729,
                            "ilevel": 278,
                            "enchantId": 3368,
                        },
                        {
                            "slot": "trinket1",
                            "name": "Test Trinket",
                            "id": 123456,
                            "ilevel": 278,
                            "bonusId": ["6652", "10877"],
                            "gemId": ["213743", "213744"],
                        },
                    ]
                },
            },
        }

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "请按职业专精页里的方案，比较这套装备的大秘境 AOE 收益",
                "buildContext": build_context,
            }
        )

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertEqual(analysis["request"]["profileSource"], "assembled")
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertTrue(analysis["agent"]["canSubmitTask"])
        self.assertIn("talents=CAE_CONTEXT", analysis["agent"]["draftProfile"])
        self.assertIn("main_hand=prodigious_gene_splicer,id=237729,ilevel=278,enchant_id=3368", analysis["agent"]["draftProfile"])
        self.assertIn("trinket1=test_trinket,id=123456,ilevel=278,bonus_id=6652/10877,gem_id=213743/213744", analysis["agent"]["draftProfile"])

    def test_simc_agent_runs_assembled_profile_from_selected_gear_on_submit(self):
        self.patch_simc_confirmation_llm({"status": "template_ready", "missingSlots": [], "question": "", "quickReplies": []})
        simc_bin = Path(self.tmp.name) / "fake-assembled-simc"
        captured_profile = Path(self.tmp.name) / "captured-assembled-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. Generated_Frost_Mage 123456 dps\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "message": "请按职业专精页里的方案，跑大秘境 AOE",
                    "buildContext": {
                        "specId": "法师-冰霜",
                        "className": "法师",
                        "specName": "冰霜",
                        "details": {
                            "talents": {"importCode": "CAE_CONTEXT"},
                            "gear": {"simcItems": [{"slot": "main_hand", "name": "Prodigious Gene Splicer", "id": 237729, "ilevel": 278}]},
                        },
                    },
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        executed_profile = captured_profile.read_text(encoding="utf-8")
        self.assertEqual(analysis["request"]["profileSource"], "assembled")
        self.assertTrue(analysis["simulation"]["ran"])
        self.assertEqual(analysis["agent"]["status"], "simc_completed")
        self.assertEqual(analysis["simulation"]["metrics"]["dps"], "123456")
        self.assertIn("talents=CAE_CONTEXT", executed_profile)
        self.assertIn("main_hand=prodigious_gene_splicer,id=237729,ilevel=278", executed_profile)

    def test_simc_agent_asks_for_playable_slots_not_external_sources(self):
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "message": "我想知道大秘境 AOE 多少合格",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["missingSlots"], ["specialization"])
        self.assertNotIn("/simc", analysis["agent"]["question"])
        self.assertNotIn("角色名", analysis["agent"]["question"])
        self.assertNotIn("服务器", analysis["agent"]["question"])
        self.assertIn("职业", analysis["agent"]["question"])

    def test_simc_agent_uses_filled_slots_to_ask_warlock_spec_only(self):
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "message": "我285的术士，大秘境啥DPS合格？",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["missingSlots"], ["specialization"])
        self.assertEqual(analysis["agent"]["filledSlots"]["class"], "warlock")
        self.assertEqual(analysis["agent"]["filledSlots"]["itemLevel"], 285)
        self.assertEqual(analysis["agent"]["filledSlots"]["scenario"], "大秘境多目标")
        self.assertIn("术士", analysis["agent"]["question"])
        self.assertIn("痛苦", analysis["agent"]["question"])
        self.assertIn("恶魔", analysis["agent"]["question"])
        self.assertIn("毁灭", analysis["agent"]["question"])
        self.assertNotIn("冰法", analysis["agent"]["question"])
        self.assertNotIn("惩戒", analysis["agent"]["question"])
        self.assertEqual(
            analysis["agent"]["quickReplies"],
            ["我是痛苦术，看大秘境 AOE", "我是恶魔术，看大秘境 AOE", "我是毁灭术，看大秘境 AOE"],
        )

    def test_simc_agent_requires_explicit_item_level_and_scenario_before_ready(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["itemLevel", "scenario", "talents", "gear"],
                question="已识别冰霜法师；还差装等、场景、天赋和装备。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "我是冰法",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "frost")
        self.assertIn("itemLevel", analysis["agent"]["missingSlots"])
        self.assertIn("scenario", analysis["agent"]["missingSlots"])
        self.assertFalse(analysis["agent"].get("canSubmitTask", False))
        self.assertEqual(analysis["request"]["profile"], "")

    def test_simc_agent_fills_warlock_spec_on_second_round_without_repeating_prompt(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["talents", "gear"],
                question="已识别恶魔术士大秘境 AOE；还差天赋和装备。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 2,
                "confirmOnly": True,
                "message": (
                    "第1轮玩家：我285的术士，大秘境啥DPS合格？\n"
                    "第2轮玩家：我是恶魔术，要看大秘境AOE"
                ),
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["missingSlots"], ["talents", "gear"])
        self.assertEqual(analysis["agent"]["filledSlots"]["class"], "warlock")
        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "demonology")
        self.assertEqual(analysis["agent"]["filledSlots"]["itemLevel"], 285)
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertEqual(analysis["agent"]["quickReplies"], ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"])
        self.assertEqual(analysis["agent"]["draftProfile"], "")

    def test_simc_agent_uses_latest_spec_correction_in_conversation_history(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["talents", "gear"],
                question="已按最新一轮识别为毁灭术；还差天赋和装备。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 2,
                "confirmOnly": True,
                "message": (
                    "第1轮玩家：我是700装等痛苦术，看大秘境 AOE\n"
                    "第2轮玩家：改成毁灭术，还是看大秘境 AOE"
                ),
            }
        )

        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "destruction")
        self.assertEqual(analysis["agent"]["missingSlots"], ["talents", "gear"])
        self.assertEqual(analysis["agent"]["draftProfile"], "")

    def test_simc_agent_generates_elemental_shaman_mythic_plus_template(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["talents", "gear"],
                question="已识别风暴元素萨大秘境 AOE；还差天赋和装备。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "我现在290风暴元素萨，在大秘境AOE环境下DPS应该多少合格？",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["request"]["profileSource"], "generated")
        self.assertEqual(analysis["agent"]["filledSlots"]["spec"], "elemental")
        self.assertEqual(analysis["agent"]["filledSlots"]["itemLevel"], 290)
        self.assertEqual(analysis["agent"]["missingSlots"], ["talents", "gear"])
        self.assertEqual(analysis["agent"]["draftProfile"], "")
        self.assertFalse(analysis["agent"]["canSubmitTask"])

    def test_simc_agent_generated_profiles_use_class_valid_default_races(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(status="template_ready", missing_slots=[], question="")
        )
        cases = [
            ("恶魔猎手", "浩劫", "race=night_elf"),
            ("圣骑士", "惩戒", "race=human"),
            ("唤魔师", "增辉", "race=dracthyr"),
        ]
        for class_label, spec_label, expected_race in cases:
            with self.subTest(spec=f"{spec_label}{class_label}"):
                analysis = self.backend.analyze_simulator_request(
                    {
                        "mode": "simcraft_agent",
                        "round": 1,
                        "confirmOnly": True,
                        "message": f"我是700装等{spec_label}{class_label}，想看大秘境 AOE",
                        "buildContext": {
                            "className": class_label,
                            "specName": spec_label,
                            "details": {
                                "talents": {"importCode": "CAE"},
                                "gear": {"simcItems": [{"slot": "main_hand", "name": "Test Weapon", "id": 237729, "ilevel": 700}]},
                            },
                        },
                    }
                )
                self.assertEqual(analysis["agent"]["status"], "template_ready")
                self.assertEqual(analysis["request"]["profileSource"], "assembled")
                self.assertIn(expected_race, analysis["agent"]["draftProfile"])
                self.assertNotIn("race=troll", analysis["agent"]["draftProfile"])

    def test_simc_agent_generates_templates_for_all_classes_and_specs(self):
        import server.simulator_payload as simulator_payload

        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: {
            "called": True,
            "model": "fake",
            "content": json.dumps(self.confirmation_response(status="template_ready", missing_slots=[], question=""), ensure_ascii=False),
            "error": "",
        }
        try:
            self.assertEqual(len(SIMC_AGENT_SPEC_CASES), 39)
            for class_label, spec_label, class_key, spec_key in SIMC_AGENT_SPEC_CASES:
                with self.subTest(spec=f"{spec_label}{class_label}"):
                    analysis = self.backend.analyze_simulator_request(
                        {
                            "mode": "simcraft_agent",
                            "round": 1,
                            "confirmOnly": True,
                            "message": f"我是700装等{spec_label}{class_label}，想看大秘境 AOE 是否合格",
                            "buildContext": {
                                "className": class_label,
                                "specName": spec_label,
                                "details": {
                                    "talents": {"importCode": "CAE"},
                                    "gear": {"simcItems": [{"slot": "main_hand", "name": "Test Weapon", "id": 237729, "ilevel": 700}]},
                                },
                            },
                        }
                    )

                    self.assertEqual(analysis["agent"]["status"], "template_ready")
                    self.assertEqual(analysis["agent"]["missingSlots"], [])
                    self.assertEqual(analysis["agent"]["filledSlots"]["class"], class_key)
                    self.assertEqual(analysis["agent"]["filledSlots"]["spec"], spec_key)
                    self.assertTrue(analysis["agent"]["canSubmitTask"])
                    self.assertEqual(analysis["request"]["profileSource"], "assembled")
                    self.assertIn(f'{class_key}="', analysis["agent"]["draftProfile"])
                    self.assertIn(f"spec={spec_key}", analysis["agent"]["draftProfile"])
                    self.assertEqual(analysis["mythicPlusReference"]["specKey"], f"{class_key}-{spec_key}")
                    self.assertTrue(analysis["mythicPlusReference"]["sources"])
                    self.assertNotEqual(analysis["mythicPlusReference"]["avgDps"], "待实时刷新")
                    self.assertNotEqual(analysis["mythicPlusReference"]["maxDps"], "待实时刷新")
                    self.assertIn("WoW.gg", analysis["mythicPlusReference"]["sources"][0]["name"])
        finally:
            simulator_payload.call_chat_completion = original_call_chat_completion

    def test_mythic_plus_reference_snapshot_covers_all_agent_specs(self):
        import server.simulator_payload as simulator_payload

        expected_keys = {f"{class_key}-{spec_key}" for _, _, class_key, spec_key in SIMC_AGENT_SPEC_CASES}

        self.assertEqual(set(simulator_payload.MYTHIC_PLUS_DPS_REFERENCES), expected_keys)
        self.assertEqual(len(simulator_payload.MYTHIC_PLUS_DPS_REFERENCES), 39)
        for spec_key, reference in simulator_payload.MYTHIC_PLUS_DPS_REFERENCES.items():
            with self.subTest(spec=spec_key):
                self.assertNotIn("待实时刷新", json.dumps(reference, ensure_ascii=False))
                self.assertIn("WoW.gg", reference["sources"][0]["name"])
                self.assertIn("comparisonText", reference)
                self.assertTrue(reference["maxKey"].startswith("+"))

    def test_healer_mythic_plus_reference_uses_hps_not_fake_max_dps(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["talents", "gear"],
                question="已识别织雾武僧；还差天赋和装备。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "我是700装等织雾武僧，想看大秘境 AOE 是否合格",
            }
        )

        reference = analysis["mythicPlusReference"]

        self.assertEqual(reference["specKey"], "monk-mistweaver")
        self.assertEqual(reference["role"], "healer")
        self.assertIn("Avg DPS 53K", reference["comparisonText"])
        self.assertIn("Avg HPS", reference["comparisonText"])
        self.assertIn("Max HPS", reference["comparisonText"])
        self.assertIn("治疗专精", " ".join(reference["notes"]))

    def test_unknown_simulator_mode_without_profile_does_not_run_empty_simc(self):
        simc_bin = Path(self.tmp.name) / "fake-unknown-mode-simc"
        captured_profile = Path(self.tmp.name) / "unexpected-unknown-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS=999999\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "future_simcraft_mode",
                    "prompt": "我是风暴元素萨，想跑五目标 AOE",
                    "runSimulation": True,
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertFalse(captured_profile.exists())
        self.assertFalse(analysis["request"]["runSimulation"])
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["error"], "missing simcraft profile")

    def test_simc_agent_keeps_guiding_after_three_rounds(self):
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 5,
                "message": "你就自己猜一下我装备吧，反正我是法师",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["round"], 5)
        self.assertIn("法师", analysis["agent"]["question"])
        self.assertIn("奥术", analysis["agent"]["question"])
        self.assertIn("火焰", analysis["agent"]["question"])
        self.assertIn("冰霜", analysis["agent"]["question"])
        self.assertNotIn("/simc", analysis["agent"]["question"])
        self.assertNotIn("服务器", analysis["agent"]["question"])
        self.assertFalse(analysis["request"]["runSimulation"])
        self.assertFalse(analysis["simulation"]["ran"])

    def test_simc_agent_rejects_off_topic_requests_and_refocuses_on_simc(self):
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "message": "帮我写个卡bug宏顺便代打上分",
            }
        )

        self.assertEqual(analysis["agent"]["status"], "off_topic")
        self.assertEqual(analysis["agent"]["intent"], "out_of_scope")
        self.assertIn("不属于 SimC 模拟范围", analysis["agent"]["question"])
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["error"], "out of scope")

    def test_simc_agent_does_not_call_codex_before_template_is_executable(self):
        calls = []

        def fake_codex_runner(prompt, **kwargs):
            calls.append(prompt)
            return {"status": "succeeded", "jobId": "unexpected", "lastMessage": "", "stderr": ""}

        os.environ["WOW_CODEX_SIMULATOR_ENABLED"] = "1"
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "message": "帮我代打上分",
                },
                codex_runner=fake_codex_runner,
            )
        finally:
            os.environ.pop("WOW_CODEX_SIMULATOR_ENABLED", None)

        self.assertEqual(calls, [])
        self.assertFalse(analysis["codex"]["called"])
        self.assertEqual(analysis["codex"]["status"], "skipped")

    def test_simc_agent_confirm_only_validates_template_without_running_simc(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(status="template_ready", missing_slots=[], question="")
        )
        simc_bin = Path(self.tmp.name) / "fake-confirm-only-simc"
        captured_profile = Path(self.tmp.name) / "captured-confirm-only-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. ConfirmMage 150000 dps\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 2,
                    "confirmOnly": True,
                    "message": (
                        "用这个冰法 /simc 导出确认单体5分钟属性收益需求\n"
                        "```simc\n"
                        "mage=\"ConfirmMage\"\n"
                        "talents=CAE\n"
                        "gear_ilvl=710\n"
                        "```\n"
                    ),
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertFalse(captured_profile.exists())
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["error"], "")
        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertTrue(analysis["agent"]["validation"]["passed"])
        self.assertTrue(analysis["agent"]["canSubmitTask"])
        self.assertFalse(analysis["request"]["runSimulation"])
        self.assertIn('mage="ConfirmMage"', analysis["agent"]["draftProfile"])
        self.assertTrue(analysis["llm"]["called"])

    def test_simc_agent_confirm_only_template_ready_calls_llm_confirmation(self):
        import server.simulator_payload as simulator_payload

        calls = []
        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: calls.append(args) or {
            "called": True,
            "model": "fake",
            "content": json.dumps(self.confirmation_response(status="template_ready", missing_slots=[], question=""), ensure_ascii=False),
            "error": "",
        }
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "confirmOnly": True,
                    "message": (
                        "用这个冰法 /simc 导出确认单体5分钟属性收益需求\n"
                        "```simc\n"
                        "mage=\"ConfirmMage\"\n"
                        "talents=CAE\n"
                        "gear_ilvl=710\n"
                        "```\n"
                    ),
                }
            )
        finally:
            simulator_payload.call_chat_completion = original_call_chat_completion

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertEqual(len(calls), 1)
        self.assertTrue(analysis["llm"]["called"])
        self.assertEqual(analysis["llm"]["error"], "")

    def test_simc_agent_confirm_only_clarification_calls_llm_confirmation(self):
        import server.simulator_payload as simulator_payload

        calls = []
        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: calls.append(args) or {
            "called": True,
            "model": "fake",
            "content": json.dumps(self.confirmation_response(missing_slots=["specialization"], question="先告诉我职业和专精。"), ensure_ascii=False),
            "error": "",
        }
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "confirmOnly": True,
                    "message": "我想看大秘境 AOE 是否合格",
                }
            )
        finally:
            simulator_payload.call_chat_completion = original_call_chat_completion

        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(len(calls), 1)
        self.assertTrue(analysis["llm"]["called"])
        self.assertEqual(analysis["llm"]["error"], "")

    def test_simc_agent_generates_validated_template_and_runs_embedded_profile(self):
        simc_bin = Path(self.tmp.name) / "fake-agent-simc"
        captured_profile = Path(self.tmp.name) / "captured-agent-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. AgentMage 150000 dps\\nScale Factors:\\nintellect=9.5 haste=6.1 mastery=5.8\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 2,
                    "message": (
                        "用这个冰法 /simc 导出跑单体5分钟属性收益\n"
                        "```simc\n"
                        "mage=\"AgentMage\"\n"
                        "talents=CAE\n"
                        "gear_ilvl=710\n"
                        "```\n"
                    ),
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        executed_profile = captured_profile.read_text(encoding="utf-8")
        self.assertTrue(analysis["simulation"]["ran"])
        self.assertEqual(analysis["agent"]["status"], "simc_completed")
        self.assertTrue(analysis["agent"]["validation"]["passed"])
        self.assertIn('mage="AgentMage"', analysis["agent"]["draftProfile"])
        self.assertIn("fight_style=Patchwerk", executed_profile)
        self.assertIn("max_time=300", executed_profile)
        self.assertIn("calculate_scale_factors=1", executed_profile)
        self.assertEqual(analysis["simulation"]["metrics"]["dps"], "150000")
        self.assertEqual(analysis["agent"]["summaryCards"][0]["title"], "结论")
        self.assertIn("150000", analysis["agent"]["summaryCards"][0]["text"])

    def test_simc_agent_generated_profiles_do_not_emit_player_facing_dps(self):
        simc_bin = Path(self.tmp.name) / "fake-generated-simc"
        captured_profile = Path(self.tmp.name) / "captured-generated-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'Player: GeneratedFrostMage\\n  DPS=53000 DPS-Error=0/0.00%%\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            os.environ.pop("WOW_SIMC_AGENT_GENERATED_ITERATIONS", None)
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "message": "我是700装等冰法，想看大秘境 AOE DPS 是否合格",
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertFalse(captured_profile.exists())
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["request"]["profileSource"], "generated")
        self.assertEqual(analysis["simulation"]["metrics"], {})
        self.assertEqual(analysis["agent"]["status"], "needs_clarification")
        self.assertEqual(analysis["agent"]["missingSlots"], ["talents", "gear"])
        self.assertIn("天赋", analysis["recommendations"][0])
        self.assertIn("装备", analysis["recommendations"][0])
        self.assertNotIn("53000", json.dumps(analysis, ensure_ascii=False))

    def test_simulator_analysis_exposes_enabled_codex_worker_status(self):
        simc_bin = Path(self.tmp.name) / "fake-simc-codex"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            "printf 'Player: CodexMage\\n  DPS=654321 DPS-Error=0/0.00%%\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        calls = []

        def fake_codex_runner(prompt, **kwargs):
            calls.append({"prompt": prompt, "kwargs": kwargs})
            return {
                "jobId": "codex-job-1",
                "status": "succeeded",
                "returnCode": 0,
                "lastMessage": "Codex 已复核 SimC 摘要。",
                "stderr": "",
                "events": [],
            }

        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        os.environ["WOW_CODEX_SIMULATOR_ENABLED"] = "1"
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft",
                    "prompt": "跑一下\n```simc\nmage=\"CodexMage\"\ntalents=CAE\ngear_ilvl=700\n```",
                },
                codex_runner=fake_codex_runner,
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)
            os.environ.pop("WOW_CODEX_SIMULATOR_ENABLED", None)

        self.assertTrue(analysis["codex"]["called"])
        self.assertEqual(analysis["codex"]["status"], "succeeded")
        self.assertEqual(analysis["codex"]["lastMessage"], "Codex 已复核 SimC 摘要。")
        self.assertIn("DPS=654321", calls[0]["prompt"])
        self.assertIn("mage=\"CodexMage\"", calls[0]["prompt"])

    def test_simulator_prompt_profile_extraction_stops_at_closing_code_fence(self):
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft",
                "prompt": (
                    "帮我跑一下这个 profile\n"
                    "```simc\n"
                    "mage=\"冰法样例\"\n"
                    "talents=CAE\n"
                    "gear_ilvl=700\n"
                    "```\n"
                    "顺便解释一下为什么急速收益高。"
                ),
            }
        )

        self.assertEqual(analysis["request"]["profile"], 'mage="冰法样例"\ntalents=CAE\ngear_ilvl=700')

    def test_simulator_metrics_parse_real_simcraft_decimal_dps_output(self):
        from server.simulator_payload import parse_simcraft_metrics

        self.assertEqual(
            parse_simcraft_metrics(
                "Player: SmokeWarrior human warrior arms 80\n"
                "  DPS=119.35741006451615 DPS-Error=0/0.00% DPS-Range=0/0.00%\n"
            )["dps"],
            "119.357",
        )

    def test_simulator_metrics_does_not_treat_unrelated_large_numbers_as_dps(self):
        from server.simulator_payload import parse_simcraft_metrics

        self.assertEqual(
            parse_simcraft_metrics("Generated report id 20260610110524 with 120000 iterations and no DPS line"),
            {},
        )

    def test_simulator_llm_prompt_omits_simcraft_progress_numbers_without_final_dps(self):
        from server.simulator_payload import build_llm_prompt, sanitize_simcraft_summary_for_llm

        simulation = {
            "ran": True,
            "summary": (
                "SimulationCraft 1205\n"
                "Generating Baseline: 1/1 [=>..................] 1106/10000 336.972 13sec\n"
                "Generating Baseline: 1/1 [========>...........] 4321/10000 342.076 8sec\n"
            ),
            "metrics": {},
            "error": "",
        }
        request_data = {
            "mode": "simcraft_agent",
            "character": "",
            "question": "第1轮玩家：我装等290，风暴元素萨，大秘境AOE环境DPS多少合格？",
            "wclUrl": "",
            "profile": "shaman=\"Generated_Elemental_Shaman\"\nspec=elemental",
            "profileSource": "generated",
        }
        prompt = build_llm_prompt(request_data, simulation)

        self.assertNotIn("336.972", sanitize_simcraft_summary_for_llm(simulation))
        self.assertNotIn("342.076", prompt)
        self.assertIn("未解析到最终 DPS", prompt)
        self.assertIn("不得从 Generating Baseline", prompt)

    def test_simc_agent_adds_mythic_plus_reference_before_llm_output(self):
        calls = []

        def fake_call_chat_completion(system_prompt, user_prompt, temperature=0.2):
            calls.append(user_prompt)
            return {
                "called": True,
                "model": "fake",
                "content": "综合真实大秘境对标后，不应把本次结果写成 300 万。",
                "error": "",
            }

        import server.simulator_payload as simulator_payload
        original_call_chat_completion = simulator_payload.call_chat_completion
        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)
        simulator_payload.call_chat_completion = fake_call_chat_completion
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "message": (
                    "我现在290风暴元素萨，在大秘境AOE环境下DPS应该多少合格？\n"
                    "```simc\n"
                    "shaman=\"ElementalReference\"\n"
                    "level=80\n"
                    "race=troll\n"
                    "role=spell\n"
                    "spec=elemental\n"
                    "scale_to_itemlevel=290\n"
                    "```\n"
                ),
            }
        )

        reference = analysis["mythicPlusReference"]
        self.assertEqual(reference["specKey"], "shaman-elemental")
        self.assertEqual(reference["avgDps"], "168K")
        self.assertEqual(reference["maxDps"], "250K")
        self.assertIn("WoW.gg", reference["sources"][0]["name"])
        self.assertIn("真实大秘境对标", calls[0])
        self.assertIn("168K", calls[0])
        self.assertIn("250K", calls[0])
        self.assertNotIn("300万", calls[0])
        self.assertIn("mythic_plus_reference", [stage["key"] for stage in analysis["stages"]])

    def test_retribution_paladin_uses_real_mythic_plus_reference_and_rejects_million_scale_llm(self):
        def fake_call_chat_completion(system_prompt, user_prompt, temperature=0.2):
            return {
                "called": True,
                "model": "fake",
                "content": "280 装等惩戒骑大秘境 AOE 合格 DPS 约在 80-100万。",
                "error": "",
            }

        import server.simulator_payload as simulator_payload
        original_call_chat_completion = simulator_payload.call_chat_completion
        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)
        simulator_payload.call_chat_completion = fake_call_chat_completion
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "message": (
                    "我是285的惩戒骑，大秘境AOE什么DPS\n"
                    "```simc\n"
                    "paladin=\"RetReference\"\n"
                    "level=80\n"
                    "race=human\n"
                    "role=attack\n"
                    "spec=retribution\n"
                    "scale_to_itemlevel=285\n"
                    "```\n"
                ),
            }
        )

        reference = analysis["mythicPlusReference"]
        self.assertEqual(reference["specKey"], "paladin-retribution")
        self.assertEqual(reference["avgDps"], "186K")
        self.assertEqual(reference["maxDps"], "260K")
        self.assertIn("mythic_plus_reference", [stage["key"] for stage in analysis["stages"]])
        self.assertNotIn("80-100万", analysis["llm"]["content"])
        self.assertNotIn("100万", analysis["llm"]["content"])
        self.assertIn("真实大秘境对标", analysis["llm"]["content"])
        self.assertIn("186K", analysis["llm"]["content"])
        self.assertIn("260K", analysis["llm"]["content"])

    def test_simc_failure_with_reference_does_not_claim_simulated_dps(self):
        simc_bin = Path(self.tmp.name) / "fake-failing-ret-simc"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "printf 'No active players in sim!\\n' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)

        def fake_call_chat_completion(system_prompt, user_prompt, temperature=0.2):
            return {
                "called": True,
                "model": "fake",
                "content": "SimC 未执行，但合格 DPS 是 100万。",
                "error": "",
            }

        import server.simulator_payload as simulator_payload
        original_call_chat_completion = simulator_payload.call_chat_completion
        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)
        simulator_payload.call_chat_completion = fake_call_chat_completion
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "message": (
                        "我是285的惩戒骑，大秘境AOE什么DPS\n"
                        "```simc\n"
                        "paladin=\"RetFailure\"\n"
                        "level=80\n"
                        "race=human\n"
                        "role=attack\n"
                        "spec=retribution\n"
                        "scale_to_itemlevel=285\n"
                        "```\n"
                    ),
                    "runSimulation": True,
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertEqual(analysis["agent"]["status"], "simc_failed")
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["metrics"], {})
        self.assertIn("No active players", analysis["simulation"]["error"])
        self.assertIn("真实大秘境对标", analysis["llm"]["content"])
        self.assertIn("SimC 未产出可用 DPS", analysis["llm"]["content"])
        self.assertNotIn("100万", analysis["llm"]["content"])
        self.assertNotIn("/simc", analysis["llm"]["content"])

    def test_simc_failure_without_reference_does_not_claim_simulated_dps(self):
        simc_bin = Path(self.tmp.name) / "fake-failing-single-target-simc"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "printf 'No active players in sim!\\n' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)

        def fake_call_chat_completion(system_prompt, user_prompt, temperature=0.2):
            return {
                "called": True,
                "model": "fake",
                "content": "虽然 SimC 报错，但这次单体合格 DPS 大约是 100万。",
                "error": "",
            }

        import server.simulator_payload as simulator_payload
        original_call_chat_completion = simulator_payload.call_chat_completion
        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)
        simulator_payload.call_chat_completion = fake_call_chat_completion
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 1,
                    "message": (
                        "我是285的惩戒骑，单体5分钟什么DPS\n"
                        "```simc\n"
                        "paladin=\"RetFailureSingle\"\n"
                        "level=80\n"
                        "race=human\n"
                        "role=attack\n"
                        "spec=retribution\n"
                        "scale_to_itemlevel=285\n"
                        "```\n"
                    ),
                    "runSimulation": True,
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertIsNone(analysis["mythicPlusReference"])
        self.assertEqual(analysis["agent"]["status"], "simc_failed")
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["metrics"], {})
        self.assertIn("SimC 未产出可用 DPS", analysis["llm"]["content"])
        self.assertIn("No active players", analysis["llm"]["content"])
        self.assertNotIn("100万", analysis["llm"]["content"])
        self.assertIn("完整 SimC profile", analysis["llm"]["content"])
        self.assertNotIn("/simc", analysis["llm"]["content"])

    def test_simc_agent_completed_report_is_brief_and_benchmarked(self):
        simc_bin = Path(self.tmp.name) / "fake-brief-report-simc"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            "printf 'Player: RetPlayer\\n  DPS=185432 DPS-Error=0/0.00%%\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "simcraft_agent",
                    "round": 2,
                    "message": (
                        "我是285惩戒圣骑士，大秘境AOE是否合格\n"
                        "```simc\n"
                        "paladin=\"RetPlayer\"\n"
                        "spec=retribution\n"
                        "talents=CAE\n"
                        "```\n"
                    ),
                }
            )
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertEqual(analysis["agent"]["status"], "simc_completed")
        self.assertEqual(analysis["simulation"]["metrics"]["dps"], "185432")
        self.assertIn("mythic_plus_reference", [stage["key"] for stage in analysis["stages"]])
        self.assertLessEqual(len(analysis["recommendations"]), 3)
        self.assertLessEqual(len(analysis["agent"]["summaryCards"]), 3)
        self.assertIn("真实大秘境对标", json.dumps(analysis["agent"]["summaryCards"], ensure_ascii=False))

    def test_guarded_llm_content_keeps_completed_simc_report_state(self):
        from server.simulator_payload import build_guarded_llm_content

        request_data = {
            "mythicPlusReference": {
                "specName": "武器战士",
                "avgDps": "待实时刷新",
                "maxDps": "待实时刷新",
                "maxKey": "高层样本",
            }
        }
        simulation = {
            "ran": True,
            "error": "",
            "metrics": {"dps": "119.357"},
        }
        content = build_guarded_llm_content(
            request_data,
            simulation,
            {"content": "这个武器战应该有 100万 DPS。"},
        )

        self.assertIn("SimC 已产出可解析 DPS：119.357", content)
        self.assertIn("真实大秘境对标", content)
        self.assertNotIn("没有生成完整可执行 SimC profile", content)

    def test_simulator_home_exposes_simcraft_version_check_status(self):
        version_file = Path(self.tmp.name) / "simc-version.json"
        version_file.write_text(
            json.dumps(
                {
                    "checkedAt": "2026-06-09T13:52:08+00:00",
                    "localTag": "1205-2026-06-07-ca5b6d7",
                    "latestTag": "1205-2026-06-09-abcd123",
                    "updateAvailable": True,
                    "source": "dockerhub",
                    "image": "simulationcraftorg/simc:1205-2026-06-07-ca5b6d7",
                }
            ),
            encoding="utf-8",
        )
        os.environ["WOW_SIMC_VERSION_FILE"] = str(version_file)
        try:
            home = self.backend.build_simulator_home_payload()
        finally:
            os.environ.pop("WOW_SIMC_VERSION_FILE", None)

        self.assertEqual(home["simcraftVersion"]["localTag"], "1205-2026-06-07-ca5b6d7")
        self.assertEqual(home["simcraftVersion"]["latestTag"], "1205-2026-06-09-abcd123")
        self.assertTrue(home["simcraftVersion"]["updateAvailable"])
        self.assertEqual(home["simcraftVersion"]["source"], "dockerhub")

    def test_wechat_login_creates_user_token_without_exposing_session_key(self):
        payload = self.backend.login_with_wechat_code(
            "wx-code-1",
            exchange_code=lambda code: {
                "openid": "openid-1",
                "unionid": "union-1",
                "session_key": "secret-session",
            },
        )

        self.assertEqual(payload["user"]["openid"], "openid-1")
        self.assertEqual(payload["user"]["unionid"], "union-1")
        self.assertIn("accessToken", payload)
        self.assertGreater(payload["expiresAt"], 0)
        self.assertNotIn("session_key", json.dumps(payload))
        self.assertEqual(self.backend.authenticate_token(payload["accessToken"])["openid"], "openid-1")

    def test_expired_auth_token_is_rejected(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-expired",
            exchange_code=lambda code: {"openid": "openid-expired"},
        )
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                "UPDATE auth_tokens SET expires_at = ? WHERE token = ?",
                ("2020-01-01T00:00:00+00:00", login["accessToken"]),
            )
            conn.commit()

        self.assertIsNone(self.backend.authenticate_token(login["accessToken"]))

    def test_user_profile_update_persists_avatar_and_nickname(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-2",
            exchange_code=lambda code: {"openid": "openid-2"},
        )

        profile = self.backend.update_user_profile(
            login["accessToken"],
            {"nickname": "冰法玩家", "avatarUrl": "https://cdn.example/avatar.png"},
        )

        self.assertEqual(profile["nickname"], "冰法玩家")
        self.assertEqual(profile["avatarUrl"], "https://cdn.example/avatar.png")
        self.assertEqual(self.backend.authenticate_token(login["accessToken"])["nickname"], "冰法玩家")

    def test_authenticated_simulator_analysis_is_saved_as_user_task(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-3",
            exchange_code=lambda code: {"openid": "openid-3"},
        )

        analysis = self.backend.analyze_and_store_simulator_task(
            {"mode": "wcl", "question": "复盘 boss 战"},
            access_token=login["accessToken"],
        )
        tasks = self.backend.list_simulator_tasks(login["accessToken"])

        self.assertEqual(analysis["owner"]["openid"], "openid-3")
        self.assertTrue(analysis["taskId"])
        self.assertEqual(len(tasks["tasks"]), 1)
        self.assertEqual(tasks["tasks"][0]["taskId"], analysis["taskId"])
        self.assertEqual(tasks["tasks"][0]["mode"], "wcl")

    def test_guest_simulator_analysis_can_be_saved_without_auth_token(self):
        analysis = self.backend.analyze_and_store_simulator_task(
            {"mode": "simcraft_agent", "prompt": "290元素萨大秘境AOE", "saveTask": True, "guestId": "device-a"},
            access_token="",
        )
        tasks = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="device-a")
        detail = self.backend.get_simulator_task("", analysis["taskId"], allow_guest=True, guest_id="device-a")

        self.assertTrue(analysis["owner"]["openid"].startswith("guest-simulator-"))
        self.assertTrue(analysis["taskId"])
        self.assertEqual(len(tasks["tasks"]), 1)
        self.assertEqual(tasks["tasks"][0]["taskId"], analysis["taskId"])
        self.assertEqual(tasks["tasks"][0]["mode"], "simcraft_agent")
        self.assertEqual(tasks["tasks"][0]["question"], "290元素萨大秘境AOE")
        self.assertEqual(detail["task"]["taskId"], analysis["taskId"])
        self.assertEqual(detail["task"]["question"], "290元素萨大秘境AOE")
        self.assertEqual(detail["task"]["request"]["prompt"], "290元素萨大秘境AOE")
        self.assertIn("analysis", detail["task"])

    def test_guest_simulator_task_history_is_isolated_by_guest_id(self):
        analysis_a = self.backend.analyze_and_store_simulator_task(
            {"mode": "simcraft_agent", "question": "游客 A", "saveTask": True, "guestId": "device-a"},
            access_token="",
        )
        analysis_b = self.backend.analyze_and_store_simulator_task(
            {"mode": "simcraft_agent", "question": "游客 B", "saveTask": True, "guestId": "device-b"},
            access_token="",
        )

        tasks_a = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="device-a")
        tasks_b = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="device-b")

        self.assertEqual([task["taskId"] for task in tasks_a["tasks"]], [analysis_a["taskId"]])
        self.assertEqual([task["taskId"] for task in tasks_b["tasks"]], [analysis_b["taskId"]])
        with self.assertRaises(KeyError):
            self.backend.get_simulator_task("", analysis_b["taskId"], allow_guest=True, guest_id="device-a")

    def test_guest_simulator_task_detail_preserves_build_context(self):
        analysis = self.backend.analyze_and_store_simulator_task(
            {
                "mode": "simcraft_agent",
                "prompt": "按职业专精页方案提交",
                "saveTask": True,
                "guestId": "device-context",
                "buildContext": {
                    "specId": "法师-冰霜",
                    "className": "法师",
                    "specName": "冰霜",
                    "details": {
                        "talents": {"importCode": "CAE_CONTEXT"},
                        "gear": {"gear": [{"slot": "饰品", "name": "Gaze of the Alnseer"}]},
                    },
                },
            },
            access_token="",
        )
        detail = self.backend.get_simulator_task("", analysis["taskId"], allow_guest=True, guest_id="device-context")

        self.assertEqual(detail["task"]["request"]["buildContext"]["specId"], "法师-冰霜")
        self.assertEqual(detail["task"]["analysis"]["request"]["buildContext"]["specId"], "法师-冰霜")
        self.assertIn("构筑上下文", detail["task"]["analysis"]["llm"]["prompt"])

    def test_guest_simulator_task_list_requires_explicit_guest_flag(self):
        self.backend.analyze_and_store_simulator_task(
            {"mode": "simcraft_agent", "question": "290元素萨大秘境AOE", "saveTask": True, "guestId": "device-a"},
            access_token="",
        )

        with self.assertRaises(PermissionError):
            self.backend.list_simulator_tasks("")
        with self.assertRaises(PermissionError):
            self.backend.list_simulator_tasks("", allow_guest=True)

    def test_guest_simulator_read_does_not_create_user_for_unknown_guest_id(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            before = conn.execute("SELECT COUNT(*) FROM wechat_users").fetchone()[0]

        with self.assertRaises(PermissionError):
            self.backend.list_simulator_tasks("", allow_guest=True, guest_id="unknown-read")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            after = conn.execute("SELECT COUNT(*) FROM wechat_users").fetchone()[0]
        self.assertEqual(after, before)

    def test_simulator_task_detail_requires_owner_or_guest_flag(self):
        analysis = self.backend.analyze_and_store_simulator_task(
            {"mode": "simcraft_agent", "question": "游客任务", "saveTask": True, "guestId": "device-detail"},
            access_token="",
        )

        with self.assertRaises(PermissionError):
            self.backend.get_simulator_task("", analysis["taskId"])
        with self.assertRaises(PermissionError):
            self.backend.get_simulator_task("", analysis["taskId"], allow_guest=True)

        with self.assertRaises(KeyError):
            self.backend.get_simulator_task("", "missing-task", allow_guest=True, guest_id="device-detail")

    def test_simulator_task_list_tolerates_corrupted_json_rows(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-corrupt",
            exchange_code=lambda code: {"openid": "openid-corrupt"},
        )
        user = self.backend.authenticate_token(login["accessToken"])
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-corrupt",
                    user["id"],
                    "wcl",
                    "ready",
                    "{bad-json",
                    "{bad-json",
                    "2026-06-09T03:33:40+00:00",
                    "2026-06-09T03:33:40+00:00",
                ),
            )
            conn.commit()

        tasks = self.backend.list_simulator_tasks(login["accessToken"])

        self.assertEqual(tasks["tasks"][0]["taskId"], "task-corrupt")
        self.assertEqual(tasks["tasks"][0]["question"], "")
        self.assertEqual(tasks["tasks"][0]["recommendations"], [])

    def test_http_post_simulator_analyze_route_returns_analysis_payload(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/simulator/analyze"
            request = Request(
                url,
                data=json.dumps({"mode": "simcraft", "question": "比较属性收益"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["mode"], "simcraft")
            self.assertGreater(len(payload["recommendations"]), 0)
        finally:
            server.shutdown()
            server.server_close()

    def test_http_post_simulator_analyze_route_runs_simcraft_from_prompt(self):
        simc_bin = Path(self.tmp.name) / "fake-route-simc"
        captured_profile = Path(self.tmp.name) / "captured-route-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS Ranking:\\n1. 路由测试 130001 dps\\nScale Factors:\\nintellect=9.2 haste=6.7\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/simulator/analyze"
            request = Request(
                url,
                data=json.dumps(
                    {
                        "mode": "simcraft",
                        "prompt": "跑这个单体 profile\n```simc\nmage=\"路由测试\"\ntalents=CAE\ngear_ilvl=705\n```",
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("WOW_SIMC_BIN", None)

        self.assertEqual(response.status, 200)
        self.assertTrue(payload["simulation"]["ran"])
        self.assertEqual(payload["simulation"]["metrics"]["dps"], "130001")
        self.assertEqual(payload["request"]["profileSource"], "prompt")
        self.assertIn('mage="路由测试"', captured_profile.read_text(encoding="utf-8"))

    def test_http_get_latest_news_refresh_run_route_returns_quality_summary(self):
        self.backend.refresh_articles("manual")
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/news/refresh-runs/latest"
            with urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["refreshMode"], "manual")
            self.assertIn("translationIssueCount", payload)
            self.assertIn("translationIssues", payload)
        finally:
            server.shutdown()
            server.server_close()

    def test_analytics_event_recording_dedupes_and_sanitizes_properties(self):
        with self.backend.db_connection() as conn:
            result = self.backend.record_events(
                conn,
                {
                    "events": [
                        {
                            "eventId": "evt-analytics-1",
                            "eventName": "page_view",
                            "occurredAt": "2026-06-12T01:00:00+00:00",
                            "page": "pages/news/news",
                            "properties": {
                                "source": "tab",
                                "prompt": "should not be stored",
                                "profile": "mage=\"secret\"",
                                "profileSource": "generated",
                            },
                        },
                        {
                            "eventId": "evt-analytics-1",
                            "eventName": "page_view",
                            "occurredAt": "2026-06-12T01:00:01+00:00",
                            "page": "pages/news/news",
                        },
                    ]
                },
                client_id="client-a",
                session_id="session-a",
            )

            self.assertEqual(result["inserted"], 1)
            row = conn.execute(
                "SELECT user_id, client_id_hash, session_id_hash, properties_json FROM analytics_events WHERE event_id = ?",
                ("evt-analytics-1",),
            ).fetchone()
            summary = self.backend.analytics_summary(conn, {"from": ["2026-06-12"], "to": ["2026-06-12"]})

        properties = json.loads(row[3])
        self.assertIsNone(row[0])
        self.assertTrue(row[1])
        self.assertTrue(row[2])
        self.assertNotIn("prompt", properties)
        self.assertNotIn("profile", properties)
        self.assertEqual(properties["profileSource"], "generated")
        self.assertEqual(summary["summary"]["pv"], 1)
        self.assertEqual(summary["summary"]["uv"], 1)

    def test_analytics_route_links_authenticated_user_without_openid_in_event_body(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-analytics",
            exchange_code=lambda code: {"openid": "openid-analytics"},
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/analytics/events",
                data=json.dumps(
                    {
                        "events": [
                            {
                                "eventId": "evt-auth-1",
                                "eventName": "simc_task_saved",
                                "occurredAt": "2026-06-12T02:00:00+00:00",
                                "page": "pages/simulator/simc",
                                "properties": {"taskId": "task-1", "openid": "openid-analytics"},
                            }
                        ]
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {login['accessToken']}",
                    "X-Wow-Client-Id": "client-auth",
                    "X-Wow-Session-Id": "session-auth",
                    "X-Wow-Platform": "miniprogram",
                },
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            row = conn.execute(
                """
                SELECT e.user_id, u.openid, e.properties_json
                FROM analytics_events e
                JOIN wechat_users u ON u.id = e.user_id
                WHERE e.event_id = ?
                """,
                ("evt-auth-1",),
            ).fetchone()
            link_count = conn.execute("SELECT COUNT(*) FROM analytics_user_links").fetchone()[0]

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["inserted"], 1)
        self.assertEqual(row[1], "openid-analytics")
        self.assertNotIn("openid", json.loads(row[2]))
        self.assertEqual(link_count, 1)

    def test_admin_analytics_requires_token_and_returns_summary(self):
        os.environ["WOW_ANALYTICS_ADMIN_TOKEN"] = "admin-token"
        with self.backend.db_connection() as conn:
            self.backend.record_events(
                conn,
                {
                    "events": [
                        {
                            "eventId": "evt-admin-1",
                            "eventName": "page_view",
                            "occurredAt": "2026-06-12T03:00:00+00:00",
                            "page": "pages/pve/pve",
                        }
                    ]
                },
                client_id="client-admin",
                session_id="session-admin",
            )
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/admin/analytics/summary?from=2026-06-12&to=2026-06-12"
            with self.assertRaises(HTTPError) as raised:
                urlopen(url, timeout=5)
            self.assertEqual(raised.exception.code, 401)

            request = Request(url, headers={"Authorization": "Bearer admin-token"})
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("WOW_ANALYTICS_ADMIN_TOKEN", None)

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["summary"]["pv"], 1)
        self.assertEqual(payload["summary"]["uv"], 1)

    def test_admin_analytics_page_escapes_event_table_values(self):
        html = self.backend.analytics_admin_page()

        self.assertIn("function escapeHtml(value)", html)
        self.assertIn("<td>${escapeHtml(value)}</td>", html)
        self.assertNotIn("<td>${String(value ?? '')}</td>", html)
        self.assertNotIn("<code>${JSON.stringify(item.properties)}</code>", html)


if __name__ == "__main__":
    unittest.main()

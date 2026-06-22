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
from unittest.mock import patch


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


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
        self._old_wcl_env = {
            name: os.environ.get(name)
            for name in (
                "WOW_WARCRAFTLOGS_CLIENT_ID",
                "WOW_WARCRAFTLOGS_CLIENT_SECRET",
                "WOW_WARCRAFTLOGS_API_KEY",
            )
        }
        for name in self._old_wcl_env:
            os.environ.pop(name, None)

        import importlib
        import server.news_backend as backend

        self.backend = importlib.reload(backend)
        self.backend.init_db()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("WOW_NEWS_DB", None)
        for name, value in self._old_wcl_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

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

    def test_blizzard_forum_source_uses_slug_url_without_stale_category_id(self):
        forum_source = self.backend.NEWS_SOURCES_BY_ID["blizzard-forums"]
        feed_source = next(source for source in self.backend.FEED_SOURCES if source["sourceId"] == "blizzard-forums")

        self.assertEqual(forum_source["sourceUrl"], "https://us.forums.blizzard.com/en/wow/c/in-development")
        self.assertEqual(feed_source["sourceUrl"], "https://us.forums.blizzard.com/en/wow/c/in-development")
        self.assertNotIn("/253", forum_source["sourceUrl"])
        self.assertNotIn("/253", feed_source["sourceUrl"])

    def test_enqueue_requeues_published_discovery_when_public_row_is_missing(self):
        article = {
            "id": "forum-recovered-detail",
            "canonicalTopicId": "Blizzard-Forums:url:https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
            "sourceId": "blizzard-forums",
            "sourceName": "Blizzard Forums",
            "sourceTier": "official",
            "sourceUrl": "https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
            "title": "Feedback: Midnight Season 2 Class Sets",
            "originalTitle": "Feedback: Midnight Season 2 Class Sets",
            "publishedAt": "2026-06-18",
            "summary": "We are excited to share the new set bonuses coming in Midnight Season 2.",
            "originalSummary": "We are excited to share the new set bonuses coming in Midnight Season 2.",
            "originalBody": "We are excited to share the new set bonuses coming in Midnight Season 2.\n\nFull detail body.",
            "bodyBlocks": [
                {"type": "paragraph", "text": "We are excited to share the new set bonuses coming in Midnight Season 2."},
                {"type": "paragraph", "text": "Full detail body."},
            ],
            "bodySourceKind": "detail_body",
            "requiresLlmTranslation": True,
        }
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO news_discovery_queue (
                    id, canonical_topic_id, source_id, source_name, source_tier,
                    source_url, original_title, published_at, status, attempts,
                    last_error, payload_json, discovered_at, updated_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["id"],
                    article["canonicalTopicId"],
                    article["sourceId"],
                    article["sourceName"],
                    article["sourceTier"],
                    article["sourceUrl"],
                    article["originalTitle"],
                    article["publishedAt"],
                    "published",
                    1,
                    "",
                    json.dumps({**article, "bodySourceKind": "forum_excerpt"}, ensure_ascii=False),
                    "2026-06-19T00:00:00+00:00",
                    "2026-06-19T00:00:00+00:00",
                    "2026-06-19T00:00:00+00:00",
                ),
            )
            self.backend.enqueue_discovered_articles(conn, [article], "2026-06-19T01:00:00+00:00")
            queue_row = conn.execute(
                "SELECT status, last_error, payload_json FROM news_discovery_queue WHERE id = ?",
                (article["id"],),
            ).fetchone()

        self.assertEqual(queue_row[0], "queued")
        self.assertEqual(queue_row[1], "")
        self.assertEqual(json.loads(queue_row[2])["bodySourceKind"], "detail_body")

    def confirmation_response(self, status="needs_clarification", missing_slots=None, question=""):
        return {
            "status": status,
            "intent": "baseline",
            "filledSlots": {},
            "missingSlots": missing_slots or [],
            "question": question or "还差天赋导入码和手选装备数据。",
            "quickReplies": ["打开天赋模拟器补天赋", "继续补装备", "我先只看参考区间"],
        }

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
        class_key="mage",
        spec_key="arcane",
        hero_key="spellslinger",
        class_id=8,
        spec_id=62,
    ):
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
            "parentIds": [],
            "choiceGroup": "",
            "shape": "square",
            "pointRequirement": 0,
            "source": "simulationcraft",
        }
        if tree_type == "hero":
            payload["heroKey"] = hero_key
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
                f"{tree_type}:{class_key}:{spec_key}" if tree_type != "hero" else f"hero:{hero_key}",
                row,
                col,
                trait_id + 100000,
                name,
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def seed_simc_template_websim_nodes(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.ensure_websim_tables(conn)
            self.insert_websim_talent(conn, "simc-class-1001-mage-arcane", "class", 1001, 1, 1, "Class Talent")
            self.insert_websim_talent(conn, "simc-spec-2001-mage-arcane", "spec", 2001, 1, 2, "Spec Talent")
            self.insert_websim_talent(conn, "simc-hero-3001-mage-arcane-spellslinger", "hero", 3001, 2, 1, "Hero Talent")
            conn.commit()

    def simc_template_full_gear_raw(self):
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
            "off_hand",
        ]
        lines = []
        for index, slot in enumerate(slots, start=1):
            parts = [
                f"{slot}=template_{slot}",
                f"id={250000 + index}",
                "ilevel=289",
                "bonus_id=13534/6652",
            ]
            if slot == "finger1":
                parts.append("gem_id=213743")
                parts.append("enchant_id=7334")
            if slot == "main_hand":
                parts.append("crafted_stats=32/49")
            lines.append(",".join(parts))
        return "\n".join(lines)

    def simc_template_payload(self, *, talent_raw=None, gear_raw=None, talent_spec="arcane", gear_spec="arcane", scenario="single", analysis_type="baseline"):
        return {
            "mode": "simcraft_template",
            "confirmOnly": True,
            "saveTask": False,
            "scenarioKey": scenario,
            "analysisType": analysis_type,
            "templateContext": {
                "talent": {
                    "id": "talent-template-1",
                    "type": "talent",
                    "title": "奥法 WebSim 天赋",
                    "rawString": talent_raw
                    or "websim:mage:arcane:spellslinger:simc-class-1001-mage-arcane:1,simc-spec-2001-mage-arcane:1,simc-hero-3001-mage-arcane-spellslinger:1",
                    "classKey": "mage",
                    "className": "法师",
                    "specKey": talent_spec,
                    "specName": "奥术",
                    "heroKey": "spellslinger",
                    "status": "saved",
                },
                "gear": {
                    "id": "gear-template-1",
                    "type": "gear",
                    "title": "奥法完整装备",
                    "rawString": gear_raw or self.simc_template_full_gear_raw(),
                    "classKey": "mage",
                    "className": "法师",
                    "specKey": gear_spec,
                    "specName": "奥术",
                    "status": "complete",
                },
            },
        }

    def official_discovered_article(self, article_id, day=19):
        return {
            "id": article_id,
            "title": f"Patch 12.1 PTR Development Notes {article_id}",
            "summary": "Public Test Realm development notes.",
            "channel": self.backend.CHANNELS[1]["title"],
            "category": self.backend.CHANNELS[1]["title"],
            "tags": ["ptr"],
            "importance": 94,
            "sourceId": "blizzard",
            "sourceName": "Blizzard News",
            "sourceTier": "official",
            "licenseStatus": "approved",
            "sourceUrl": f"https://worldofwarcraft.blizzard.com/news/{article_id}",
            "publishedAt": f"2026-06-{day:02d}",
            "sourceNote": "Blizzard official discovery.",
            "originalTitle": f"Patch 12.1 PTR Development Notes {article_id}",
            "originalSummary": "Public Test Realm development notes.",
            "originalBody": "Public Test Realm development notes for direct translation.",
            "bodyBlocks": [{"type": "paragraph", "text": "Public Test Realm development notes for direct translation."}],
            "requiresLlmTranslation": True,
            "contentStatus": "discovered",
        }

    def reference_discovered_article(self, article_id="wowhead-reference"):
        return {
            "id": article_id,
            "title": "Patch 12.1 PTR Notes Datamining",
            "summary": "Third-party reference item for discovery coverage.",
            "channel": self.backend.CHANNELS[1]["title"],
            "category": self.backend.CHANNELS[1]["title"],
            "tags": ["ptr"],
            "importance": 72,
            "sourceId": "wowhead",
            "sourceName": "Wowhead",
            "sourceTier": "trusted_media",
            "licenseStatus": "reference_only",
            "sourceUrl": f"https://www.wowhead.com/news/{article_id}-381217",
            "publishedAt": "2026-06-19",
            "sourceNote": "Wowhead reference discovery.",
            "originalTitle": "Patch 12.1 PTR Notes Datamining",
            "originalSummary": "Third-party reference item for discovery coverage.",
            "originalBody": "Reference-only body should stay out of public translation.",
            "bodyBlocks": [{"type": "paragraph", "text": "Reference-only body should stay out of public translation."}],
            "requiresLlmTranslation": True,
            "contentStatus": "discovered",
        }

    def translated_official_article(self, article):
        return dict(
            article,
            title=f"Official translation {article['id']}",
            summary="Official PTR development notes translated directly.",
            bodyZh=f"Chinese full-body translation for {article['id']} from the official PTR source.",
            bodyBlocksZh=[
                {
                    "type": "paragraph",
                    "text": f"Chinese full-body translation for {article['id']} from the official PTR source.",
                }
            ],
            tagItems=[{"id": "ptr", "label": "PTR"}],
            translationStatus="llm",
            translationFidelity="source_translation",
            contentStatus="ready",
        )

    def test_get_article_detail_by_id_returns_source_evidence(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body,
                    translation_status, content_status, tag_items_json, blocked_reason,
                    source_id, source_tier, license_status, verification_status,
                    source_badges_json, body_blocks_zh_json, canonical_topic_id,
                    reading_meta_json, translation_fidelity, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    "llm",
                    "ready",
                    '[{"id":"hotfix","label":"热修"},{"id":"class-change","label":"职业调整"}]',
                    "",
                    "blizzard",
                    "official",
                    "approved",
                    "official_verified",
                    '["官方已核验","全文翻译"]',
                    '[{"type":"paragraph","text":"中文正文：这条官方热修资讯汇总了《魔兽世界》近期问题修正，适合关注职业调整和正式服改动的玩家查看。"}]',
                    "news:24276957",
                    '{"bodyBlockCount":1,"estimatedReadingMinutes":1}',
                    "source_translation",
                    "2026-06-09T03:33:40+00:00",
                ),
            )
            conn.commit()

        detail = self.backend.get_article_detail("article-1")

        self.assertEqual(detail["id"], "article-1")
        self.assertEqual(detail["title"], "官方热修：2026 年 6 月 3 日")
        self.assertIn("中文正文", detail["bodyZh"])
        self.assertEqual(detail["originalTitle"], "Hotfixes: June 3, 2026")
        self.assertNotIn("originalBody", detail)
        self.assertNotIn("originalSummary", detail)
        self.assertEqual(detail["contentStatus"], "ready")
        self.assertEqual(detail["translationStatus"], "llm")
        self.assertEqual(detail["verificationStatus"], "official_verified")
        self.assertEqual(detail["licenseStatus"], "approved")
        self.assertEqual(detail["sourceBadges"], ["官方已核验", "全文翻译"])
        self.assertEqual(detail["bodyBlocksZh"][0]["type"], "paragraph")
        self.assertEqual(detail["tagItems"][0]["label"], "热修")
        self.assertEqual(detail["sourceName"], "Blizzard News")
        self.assertEqual(detail["publishedAt"], "2026-06-06")
        self.assertEqual(detail["sourceUrl"], "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026")

    def test_get_article_detail_by_id_returns_none_for_missing_article(self):
        self.assertIsNone(self.backend.get_article_detail("missing"))

    def test_refresh_mode_validation_accepts_only_known_public_modes(self):
        self.assertIsNone(self.backend.normalize_refresh_mode("manual"))
        self.assertEqual(self.backend.normalize_refresh_mode("scheduled"), "scheduled")
        self.assertIsNone(self.backend.normalize_refresh_mode("unexpected"))

    def test_refresh_run_records_visible_translation_quality_summary(self):
        self.backend.refresh_articles("scheduled")

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
        self.backend.refresh_articles("scheduled")

        payload = self.backend.latest_refresh_run_payload()

        self.assertEqual(payload["refreshMode"], "scheduled")
        self.assertGreater(payload["acceptedCount"], 0)
        self.assertIn("refreshedAt", payload)
        self.assertIn("translationIssueCount", payload)
        self.assertIn("translationIssues", payload)
        self.assertIsInstance(payload["translationIssues"], list)
        self.assertIn("blockedArticleCount", payload)
        self.assertIn("blockedArticles", payload)
        self.assertGreater(payload["blockedArticleCount"], 0)
        self.assertIn("license_blocked", {article["reason"] for article in payload["blockedArticles"]})
        self.assertIn("collectorLimit", payload)
        self.assertIn("collectedDiscoveredCount", payload)
        self.assertIn("collectorDuplicateSeedSkippedCount", payload)

    def test_news_source_registry_seeds_license_and_fetch_policy(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            rows = conn.execute(
                """
                SELECT source_id, source_name, tier, fetch_mode, retail_only, license_status, enabled
                FROM news_sources
                ORDER BY source_id
                """
            ).fetchall()

        by_id = {row[0]: row for row in rows}
        self.assertEqual(by_id["blizzard"][1], "Blizzard News")
        self.assertEqual(by_id["blizzard"][2], "official")
        self.assertEqual(by_id["blizzard"][5], "approved")
        self.assertEqual(by_id["blizzard"][6], 1)
        self.assertEqual(by_id["wowhead"][2], "trusted_media")
        self.assertEqual(by_id["wowhead"][5], "reference_only")
        self.assertEqual(by_id["wowhead"][6], 0)

    def test_refresh_accepts_only_official_verified_llm_articles(self):
        collected = [
            {
                "id": "auto-blizzard-ready",
                "title": "Hotfixes: June 3, 2026",
                "summary": "Blizzard has posted hotfixes.",
                "channel": "职业强度变化",
                "category": "正式服",
                "tags": ["hotfix"],
                "importance": 96,
                "sourceId": "blizzard",
                "sourceName": "Blizzard News",
                "sourceUrl": "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
                "publishedAt": "2026-06-06",
                "sourceNote": "暴雪官方 World of Warcraft 新闻详情页自动采集。",
                "originalTitle": "Hotfixes: June 3, 2026",
                "originalSummary": "Blizzard has posted hotfixes.",
                "originalBody": "Blizzard has posted hotfixes.\n\nClasses\n\nDruid fixed issue.",
                "bodyBlocks": [
                    {"type": "paragraph", "text": "Blizzard has posted hotfixes."},
                    {"type": "heading", "text": "Classes"},
                    {"type": "paragraph", "text": "Druid fixed issue."},
                ],
                "requiresLlmTranslation": True,
            }
        ]
        translated = dict(
            collected[0],
            title="官方热修：2026 年 6 月 3 日",
            summary="暴雪发布新的《魔兽世界》官方热修说明，覆盖职业问题修正。",
            bodyZh="中文正文：暴雪发布新的官方热修说明，覆盖正式服近期问题修正。\n\n职业\n\n德鲁伊问题已修正。",
            bodyBlocksZh=[
                {"type": "paragraph", "text": "暴雪发布新的官方热修说明，覆盖正式服近期问题修正。"},
                {"type": "heading", "text": "职业"},
                {"type": "paragraph", "text": "德鲁伊问题已修正。"},
            ],
            tagItems=[{"id": "hotfix", "label": "热修"}],
            tags=["hotfix"],
            translationStatus="llm",
            translationFidelity="source_translation",
            contentStatus="ready",
        )

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=(collected, []),
        ), patch.object(self.backend, "localize_article", return_value=translated):
            self.backend.refresh_articles("scheduled")

        detail = self.backend.get_article_detail("auto-blizzard-ready")
        latest = self.backend.latest_refresh_run_payload()

        self.assertEqual(detail["verificationStatus"], "official_verified")
        self.assertEqual(detail["licenseStatus"], "approved")
        self.assertEqual(detail["sourceTier"], "official")
        self.assertEqual(detail["translationStatus"], "llm")
        self.assertEqual(detail["sourceBadges"], ["官方已核验", "全文翻译"])
        self.assertEqual(detail["bodyBlocksZh"][1], {"type": "heading", "text": "职业"})
        self.assertNotIn("originalBody", detail)
        self.assertEqual(latest["verificationCounts"]["official_verified"], 1)

    def test_refresh_blocks_forum_excerpt_before_llm_translation(self):
        forum_excerpt = {
            "id": "forum-summary-only",
            "title": "Feedback: Midnight Season 2 Class Sets",
            "summary": "We are excited to share the new set bonuses coming in Midnight Season 2.",
            "channel": self.backend.CHANNELS[1]["title"],
            "category": self.backend.CHANNELS[1]["title"],
            "tags": ["ptr", "class-change"],
            "importance": 98,
            "sourceId": "blizzard-forums",
            "sourceName": "Blizzard Forums",
            "sourceTier": "official",
            "licenseStatus": "approved",
            "sourceUrl": "https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
            "publishedAt": "2026-06-18",
            "sourceNote": "Blizzard official PTR and development forum topic list.",
            "originalTitle": "Feedback: Midnight Season 2 Class Sets",
            "originalSummary": "We are excited to share the new set bonuses coming in Midnight Season 2.",
            "originalBody": "We are excited to share the new set bonuses coming in Midnight Season 2.",
            "bodyBlocks": [
                {
                    "type": "paragraph",
                    "text": "We are excited to share the new set bonuses coming in Midnight Season 2.",
                }
            ],
            "bodySourceKind": "forum_excerpt",
            "requiresLlmTranslation": True,
            "contentStatus": "discovered",
        }
        translated = dict(
            forum_excerpt,
            title="反馈：Midnight 第二赛季职业套装",
            summary="暴雪分享了 Midnight 第二赛季职业套装奖励。",
            bodyZh="我们很高兴分享 Midnight 第二赛季即将推出的新套装奖励。",
            bodyBlocksZh=[
                {
                    "type": "paragraph",
                    "text": "我们很高兴分享 Midnight 第二赛季即将推出的新套装奖励。",
                }
            ],
            tagItems=[{"id": "ptr", "label": "PTR"}],
            translationStatus="llm",
            translationFidelity="source_translation",
            contentStatus="ready",
        )

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=([forum_excerpt], []),
        ), patch.object(self.backend, "localize_article", return_value=translated) as localize:
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_row = conn.execute(
                "SELECT status, last_error FROM news_discovery_queue WHERE id = ?",
                ("forum-summary-only",),
            ).fetchone()

        self.assertEqual(localize.call_count, 0)
        self.assertIsNone(self.backend.get_article_detail("forum-summary-only"))
        self.assertEqual(queue_row, ("retryable", "source_body_missing"))
        self.assertEqual(latest["blockedArticles"][0]["id"], "forum-summary-only")
        self.assertEqual(latest["blockedArticles"][0]["reason"], "source_body_missing")

    def test_refresh_audits_existing_forum_summary_only_articles_out_of_public_payload(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body,
                    translation_status, content_status, tag_items_json, blocked_reason,
                    source_id, source_tier, license_status, verification_status,
                    source_badges_json, body_blocks_zh_json, canonical_topic_id,
                    reading_meta_json, translation_fidelity, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "forum-stale-summary",
                    "反馈：Midnight 第二赛季职业套装",
                    "我们很高兴分享 Midnight 第二赛季即将推出的新套装奖励。",
                    self.backend.CHANNELS[1]["title"],
                    self.backend.CHANNELS[1]["title"],
                    '["ptr","class-change"]',
                    98,
                    "Blizzard Forums",
                    "https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
                    "2026-06-18",
                    "Blizzard official PTR and development forum topic list.",
                    "我们很高兴分享 Midnight 第二赛季即将推出的新套装奖励。",
                    "Feedback: Midnight Season 2 Class Sets",
                    "We are excited to share the new set bonuses coming in Midnight Season 2.",
                    "We are excited to share the new set bonuses coming in Midnight Season 2.",
                    "llm",
                    "ready",
                    '[{"id":"ptr","label":"测试服"}]',
                    "",
                    "blizzard-forums",
                    "official",
                    "approved",
                    "official_verified",
                    '["官方已核验","全文翻译"]',
                    '[{"type":"paragraph","text":"我们很高兴分享 Midnight 第二赛季即将推出的新套装奖励。"}]',
                    "Blizzard-Forums:url:https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
                    '{"bodyBlockCount":1,"estimatedReadingMinutes":1}',
                    "source_translation",
                    "2026-06-19T00:00:00+00:00",
                ),
            )
            queued_payload = {
                "id": "forum-stale-summary",
                "canonicalTopicId": "Blizzard-Forums:url:https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
                "sourceId": "blizzard-forums",
                "sourceName": "Blizzard Forums",
                "sourceTier": "official",
                "sourceUrl": "https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
                "title": "Feedback: Midnight Season 2 Class Sets",
                "originalTitle": "Feedback: Midnight Season 2 Class Sets",
                "publishedAt": "2026-06-18",
                "summary": "We are excited to share the new set bonuses coming in Midnight Season 2.",
                "originalSummary": "We are excited to share the new set bonuses coming in Midnight Season 2.",
                "originalBody": "We are excited to share the new set bonuses coming in Midnight Season 2.\n\nFull forum detail body.",
                "bodyBlocks": [
                    {"type": "paragraph", "text": "We are excited to share the new set bonuses coming in Midnight Season 2."},
                    {"type": "paragraph", "text": "Full forum detail body."},
                ],
                "bodySourceKind": "detail_body",
                "requiresLlmTranslation": True,
            }
            conn.execute(
                """
                INSERT INTO news_discovery_queue (
                    id, canonical_topic_id, source_id, source_name, source_tier,
                    source_url, original_title, published_at, status, attempts,
                    last_error, payload_json, discovered_at, updated_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "forum-stale-summary",
                    queued_payload["canonicalTopicId"],
                    "blizzard-forums",
                    "Blizzard Forums",
                    "official",
                    queued_payload["sourceUrl"],
                    queued_payload["originalTitle"],
                    "2026-06-18",
                    "published",
                    1,
                    "",
                    json.dumps(queued_payload, ensure_ascii=False),
                    "2026-06-19T00:00:00+00:00",
                    "2026-06-19T00:00:00+00:00",
                    "2026-06-19T00:00:00+00:00",
                ),
            )
            conn.commit()

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=([], []),
        ):
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()

        self.assertIsNone(self.backend.get_article_detail("forum-stale-summary"))
        self.assertEqual(latest["blockedArticles"][0]["id"], "forum-stale-summary")
        self.assertEqual(latest["blockedArticles"][0]["reason"], "summary_only_body")
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_row = conn.execute(
                "SELECT status, last_error FROM news_discovery_queue WHERE id = ?",
                ("forum-stale-summary",),
            ).fetchone()
        self.assertEqual(queue_row, ("retryable", "summary_only_body"))

    def test_refresh_skips_collected_seed_duplicates_before_llm_translation(self):
        seed = dict(self.backend.load_seed_articles()[0])
        seed["translationFidelity"] = "source_translation"
        duplicate = dict(
            seed,
            id="collected-duplicate",
            title=seed.get("originalTitle", seed["title"]),
            summary=seed.get("originalSummary", seed["summary"]),
            bodyZh="",
            bodyBlocksZh=[],
            translationStatus="",
            contentStatus="discovered",
            requiresLlmTranslation=True,
        )
        localized_ids = []

        def localize(article, require_llm=False):
            localized_ids.append(article["id"])
            return article

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[seed]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=([duplicate], []),
        ), patch.object(self.backend, "localize_article", side_effect=localize):
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()
        detail = self.backend.get_article_detail(seed["id"])

        self.assertEqual(localized_ids, [])
        self.assertEqual(detail["id"], seed["id"])
        self.assertEqual(detail["translationFidelity"], "source_translation")
        self.assertEqual(latest["collectedDiscoveredCount"], 1)
        self.assertEqual(latest["collectedCount"], 0)
        self.assertEqual(latest["collectorDuplicateSeedSkippedCount"], 1)

    def test_refresh_retranslates_seed_duplicate_when_seed_is_not_source_translation(self):
        seed = dict(self.backend.load_seed_articles()[0])
        seed.pop("translationFidelity", None)
        duplicate = dict(
            seed,
            id="collected-duplicate",
            title=seed.get("originalTitle", seed["title"]),
            summary=seed.get("originalSummary", seed["summary"]),
            originalBody="This official source paragraph should be translated directly.",
            bodyBlocks=[{"type": "paragraph", "text": "This official source paragraph should be translated directly."}],
            bodyZh="",
            bodyBlocksZh=[],
            translationStatus="",
            contentStatus="discovered",
            requiresLlmTranslation=True,
        )
        localized_ids = []

        def localize(article, require_llm=False):
            localized_ids.append(article["id"])
            if article["id"] == "collected-duplicate":
                return dict(
                    article,
                    title="官方来源段落直译",
                    summary="这是一段官方来源正文的中文翻译。",
                    bodyZh="中文正文：这段官方来源段落应该被直接翻译。",
                    bodyBlocksZh=[{"type": "paragraph", "text": "这段官方来源段落应该被直接翻译。"}],
                    tagItems=[{"id": "content-update", "label": "内容更新"}],
                    translationStatus="llm",
                    translationFidelity="source_translation",
                    contentStatus="ready",
                )
            return article

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[seed]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=([duplicate], []),
        ), patch.object(self.backend, "localize_article", side_effect=localize):
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()
        detail = self.backend.get_article_detail("collected-duplicate")

        self.assertEqual(localized_ids, ["collected-duplicate"])
        self.assertEqual(latest["collectedDiscoveredCount"], 1)
        self.assertEqual(latest["collectedCount"], 1)
        self.assertEqual(latest["collectorDuplicateSeedSkippedCount"], 0)
        self.assertEqual(detail["translationFidelity"], "source_translation")

    def test_publication_gate_blocks_llm_summary_without_source_translation_fidelity(self):
        reviewed = self.backend.apply_publication_gates(
            {
                "id": "summary-like",
                "title": "Midnight: Revelations 内容更新将于 6 月 16 日上线",
                "summary": "官方公布 Midnight: Revelations 更新。",
                "bodyZh": "中文正文：暴雪公布了 Midnight: Revelations 内容更新的上线安排，玩家可以提前了解主要游玩目标。",
                "bodyBlocksZh": [
                    {
                        "type": "paragraph",
                        "text": "中文正文：暴雪公布了 Midnight: Revelations 内容更新的上线安排，玩家可以提前了解主要游玩目标。",
                    }
                ],
                "channel": "正式服动态",
                "category": "正式服",
                "tags": ["content-update"],
                "tagItems": [{"id": "content-update", "label": "内容更新"}],
                "sourceName": "Blizzard News",
                "sourceId": "blizzard",
                "sourceTier": "official",
                "licenseStatus": "approved",
                "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/24266797/the-midnight-revelations-content-update-goes-live-17-june",
                "sourceNote": "官方来源。",
                "publishedAt": "2026-06-03",
                "originalTitle": "The Midnight: Revelations Content Update Goes Live 17 June",
                "translationStatus": "llm",
                "contentStatus": "ready",
            }
        )

        self.assertEqual(reviewed["contentStatus"], "blocked")
        self.assertEqual(reviewed["blockedReason"], "not_source_translation")

    def test_refresh_blocks_third_party_without_approved_license_even_when_translated(self):
        collected = [
            {
                "id": "wowhead-reference-only",
                "title": "More Class Tuning for Druids and Warriors",
                "summary": "Wowhead summarized PTR notes.",
                "channel": "测试服前瞻",
                "category": "测试服",
                "tags": ["ptr", "class-change"],
                "importance": 72,
                "sourceId": "wowhead",
                "sourceName": "Wowhead",
                "sourceTier": "trusted_media",
                "licenseStatus": "reference_only",
                "sourceUrl": "https://www.wowhead.com/news/more-class-tuning-381217",
                "publishedAt": "2026-04-13",
                "sourceNote": "Wowhead RSS discovery.",
                "originalTitle": "More Class Tuning for Druids and Warriors",
                "originalSummary": "Wowhead summarized PTR notes.",
                "originalBody": "Third-party article body should not be publicly translated.",
                "requiresLlmTranslation": True,
            }
        ]
        translated = dict(
            collected[0],
            title="PTR 德鲁伊与战士职业调整记录",
            summary="第三方站点整理了 PTR 开发说明。",
            bodyZh="中文正文：第三方站点整理了 PTR 开发说明，但未确认授权时不能公开全文翻译。",
            bodyBlocksZh=[{"type": "paragraph", "text": "第三方站点整理了 PTR 开发说明，但未确认授权时不能公开全文翻译。"}],
            tagItems=[{"id": "ptr", "label": "测试服"}],
            translationStatus="llm",
            translationFidelity="source_translation",
            contentStatus="ready",
        )

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=(collected, []),
        ), patch.object(self.backend, "localize_article", return_value=translated):
            self.backend.refresh_articles("scheduled")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            public_count = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
            raw_count = conn.execute("SELECT COUNT(*) FROM news_raw_articles").fetchone()[0]
            evidence_count = conn.execute("SELECT COUNT(*) FROM news_article_evidence").fetchone()[0]

        latest = self.backend.latest_refresh_run_payload()

        self.assertEqual(public_count, 0)
        self.assertEqual(raw_count, 1)
        self.assertEqual(evidence_count, 1)
        self.assertEqual(latest["licenseBlockedCount"], 1)
        self.assertEqual(latest["blockedArticles"][0]["reason"], "license_blocked")
        self.assertEqual(latest["verificationCounts"]["license_blocked"], 1)

    def test_refresh_queues_all_discovered_and_processes_limited_batch(self):
        collected = [self.official_discovered_article(f"official-queued-{index}", day=19 - index) for index in range(6)]
        observed_limits = []

        def fake_collect(sources, timeout=15, max_articles_per_source=None):
            observed_limits.append(max_articles_per_source)
            return collected, []

        def fake_localize(article, require_llm=False):
            return self.translated_official_article(article)

        with patch.dict(os.environ, {"WOW_NEWS_MAX_COLLECTED_ARTICLES": "1", "WOW_NEWS_PROCESS_LIMIT": "2"}), patch.object(
            self.backend, "ENABLE_COLLECTORS", True
        ), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend, "collect_feed_articles", side_effect=fake_collect
        ), patch.object(
            self.backend, "localize_article", side_effect=fake_localize
        ):
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_statuses = conn.execute(
                """
                SELECT status, COUNT(*) FROM news_discovery_queue
                GROUP BY status
                """
            ).fetchall()

        self.assertGreaterEqual(observed_limits[0], 10)
        self.assertEqual(latest["discoveredCount"], 6)
        self.assertEqual(latest["processedCount"], 2)
        self.assertEqual(latest["publishedCount"], 2)
        self.assertEqual(latest["queuedCount"], 4)
        self.assertGreaterEqual(latest["oldestBacklogAge"], 0)
        self.assertEqual(latest["sourceCoverage"]["blizzard"]["discovered"], 6)
        self.assertEqual(dict(queue_statuses), {"published": 2, "queued": 4})

    def test_refresh_continues_after_first_llm_block_and_marks_retryable(self):
        collected = [self.official_discovered_article("official-llm-fail"), self.official_discovered_article("official-after-fail")]
        localized_ids = []

        def fake_localize(article, require_llm=False):
            localized_ids.append(article["id"])
            if article["id"] == "official-llm-fail":
                return dict(
                    article,
                    contentStatus="blocked",
                    blockedReason="invalid_llm_translation",
                    verificationStatus="invalid_llm_translation",
                    translationStatus="llm",
                )
            return self.translated_official_article(article)

        with patch.dict(os.environ, {"WOW_NEWS_PROCESS_LIMIT": "5"}), patch.object(
            self.backend, "ENABLE_COLLECTORS", True
        ), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend, "collect_feed_articles", return_value=(collected, [])
        ), patch.object(
            self.backend, "localize_article", side_effect=fake_localize
        ):
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_statuses = conn.execute(
                "SELECT id, status, last_error FROM news_discovery_queue ORDER BY id"
            ).fetchall()

        self.assertEqual(localized_ids, ["official-llm-fail", "official-after-fail"])
        self.assertEqual(latest["processedCount"], 2)
        self.assertEqual(latest["publishedCount"], 1)
        self.assertEqual(latest["blockedArticleCount"], 1)
        self.assertEqual(latest["retryableCount"], 1)
        self.assertIn(("official-llm-fail", "retryable", "invalid_llm_translation"), queue_statuses)
        self.assertIn(("official-after-fail", "published", ""), queue_statuses)

    def test_reference_only_discovery_is_audited_without_public_translation(self):
        collected = [self.reference_discovered_article()]

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(
            self.backend, "load_seed_articles", return_value=[]
        ), patch.object(
            self.backend, "collect_feed_articles", return_value=(collected, [])
        ), patch.object(
            self.backend,
            "localize_article",
            side_effect=AssertionError("reference-only discovery must not request public translation"),
        ):
            self.backend.refresh_articles("scheduled")

        latest = self.backend.latest_refresh_run_payload()
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            public_count = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
            raw_count = conn.execute("SELECT COUNT(*) FROM news_raw_articles").fetchone()[0]
            queue_row = conn.execute(
                "SELECT status, last_error FROM news_discovery_queue WHERE id = ?",
                (collected[0]["id"],),
            ).fetchone()

        self.assertEqual(public_count, 0)
        self.assertEqual(raw_count, 1)
        self.assertEqual(queue_row, ("blocked", "license_blocked"))
        self.assertEqual(latest["blockedArticles"][0]["reason"], "license_blocked")
        self.assertEqual(latest["sourceCoverage"]["wowhead"]["discovered"], 1)
        self.assertEqual(latest["sourceCoverage"]["wowhead"]["blocked"], 1)

    def test_news_health_reports_backlog_without_marking_entire_news_blocked(self):
        collected = [self.official_discovered_article(f"official-health-{index}") for index in range(3)]

        with patch.dict(os.environ, {"WOW_NEWS_PROCESS_LIMIT": "1"}), patch.object(
            self.backend, "ENABLE_COLLECTORS", True
        ), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend, "collect_feed_articles", return_value=(collected, [])
        ), patch.object(
            self.backend, "localize_article", side_effect=lambda article, require_llm=False: self.translated_official_article(article)
        ):
            self.backend.refresh_articles("scheduled")

        component = self.backend.news_health_component()

        self.assertNotEqual(component["status"], "blocked")
        self.assertEqual(component["details"]["discoveredCount"], 3)
        self.assertEqual(component["details"]["processedCount"], 1)
        self.assertEqual(component["details"]["queuedCount"], 2)
        self.assertIn("sourceCoverage", component["details"])

    def test_news_home_channels_include_visible_article_counts(self):
        def article(article_id, channel, tags):
            return {
                "id": article_id,
                "title": f"官方资讯 {article_id}",
                "summary": "暴雪发布了新的正式服与测试服资讯。",
                "channel": channel,
                "category": channel,
                "tags": tags,
                "importance": 90,
                "sourceName": "Blizzard News",
                "sourceUrl": f"https://worldofwarcraft.blizzard.com/news/{article_id}",
                "publishedAt": "2026-06-19",
                "sourceNote": "暴雪官方 World of Warcraft 新闻详情页。",
                "bodyZh": "中文正文：暴雪发布了完整资讯正文，覆盖版本变化、活动内容和玩家需要关注的后续时间点。",
                "bodyBlocksZh": [
                    {
                        "type": "paragraph",
                        "text": "中文正文：暴雪发布了完整资讯正文，覆盖版本变化、活动内容和玩家需要关注的后续时间点。",
                    }
                ],
                "originalTitle": f"Official News {article_id}",
                "tagItems": [{"id": tags[0], "label": tags[0]}],
                "contentStatus": "ready",
                "licenseStatus": "approved",
                "verificationStatus": "official_verified",
                "translationStatus": "llm",
                "translationFidelity": "source_translation",
                "sourceTier": "official",
                "sourceBadges": ["官方已核验", "全文翻译"],
            }

        with patch.object(
            self.backend,
            "load_articles",
            return_value=[
                article("retail-one", "正式服动态", ["content-update"]),
                article("retail-two", "正式服动态", ["hotfix"]),
                article("ptr-one", "测试服前瞻", ["ptr"]),
                article("class-one", "职业强度变化", ["class-change"]),
            ],
        ), patch.object(
            self.backend,
            "latest_refresh_state",
            return_value={"lastRefreshedAt": "2026-06-19T08:00:00+08:00", "refreshMode": "scheduled"},
        ):
            payload = self.backend.build_home_payload()

        self.assertEqual(
            [channel["updateCount"] for channel in payload["channels"]],
            [2, 1, 1],
        )

    def test_load_articles_does_not_publish_seed_without_source_translation_when_collectors_are_missing(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body,
                    translation_status, content_status, tag_items_json, blocked_reason, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-short-body",
                    "前往 Val 和 Naigtal 平息虚空领袖",
                    "与伊利达雷恶魔猎手和光铸军团一同冒险，前往两个全新区域——Val…",
                    "职业强度变化",
                    "正式服",
                    '["class-change"]',
                    100,
                    "Blizzard News",
                    "https://worldofwarcraft.blizzard.com/news/24270001/travel-to-val-and-naigtal",
                    "2026-06-03",
                    "旧版采集数据。",
                    "中文正文：与伊利达雷恶魔猎手和光铸军团一同冒险，前往两个全新区域——Val…",
                    "Travel to Val and Naigtal to Quell Leaders of the Void",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "2026-06-17T00:00:00+00:00",
                ),
            )
            conn.commit()

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(
            self.backend,
            "collect_feed_articles",
            side_effect=AssertionError("bootstrap should not run collectors"),
        ):
            articles = self.backend.load_articles()

        self.assertNotIn("legacy-short-body", {article["id"] for article in articles})
        self.assertGreater(len(articles), 0)
        self.assertTrue(all(article["translationFidelity"] == "source_translation" for article in articles))
        self.assertTrue(all(article["contentStatus"] == "ready" for article in articles))

    def test_load_articles_returns_empty_for_legacy_ready_rows_missing_source_translation(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note,
                    body_zh, original_title, original_summary, original_body,
                    translation_status, content_status, tag_items_json, blocked_reason,
                    source_id, source_tier, license_status, verification_status,
                    source_badges_json, body_blocks_zh_json, canonical_topic_id,
                    reading_meta_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-ready-missing-fidelity",
                    "旧版摘要型正文",
                    "旧版摘要。",
                    "正式服动态",
                    "正式服",
                    '["content-update"]',
                    90,
                    "Blizzard News",
                    "https://worldofwarcraft.blizzard.com/news/24266797/the-midnight-revelations-content-update-is-now-live",
                    "2026-06-16",
                    "旧版来源。",
                    "中文正文：这是一段旧版摘要型正文。",
                    "The Midnight: Revelations Content Update is Now Live!",
                    "",
                    "",
                    "llm",
                    "ready",
                    '[{"id":"content-update","label":"内容更新"}]',
                    "",
                    "blizzard",
                    "official",
                    "approved",
                    "official_verified",
                    '["官方已核验","全文翻译"]',
                    '[{"type":"paragraph","text":"这是一段旧版摘要型正文。"}]',
                    "news:24266797",
                    '{"bodyBlockCount":1,"estimatedReadingMinutes":1}',
                    "2026-06-17T00:00:00+00:00",
                ),
            )
            conn.commit()

        with patch.object(self.backend, "refresh_articles", return_value={"refreshMode": "bootstrap", "lastRefreshedAt": "now"}):
            articles = self.backend.load_articles()

        self.assertEqual(articles, [])

    def test_refresh_blocks_collected_articles_when_llm_translation_is_unavailable(self):
        collected = [
            {
                "id": "auto-blizzard",
                "title": "Travel to Val and Naigtal to Quell Leaders of the Void",
                "summary": "Join the fight against the Void in a new World of Warcraft update.",
                "channel": "正式服动态",
                "category": "正式服",
                "tags": ["content-update"],
                "importance": 91,
                "sourceName": "Blizzard News",
                "sourceUrl": "https://worldofwarcraft.blizzard.com/news/24270001/travel-to-val-and-naigtal",
                "publishedAt": "2026-06-08",
                "sourceNote": "暴雪官方 World of Warcraft 新闻详情页自动采集。",
                "originalTitle": "Travel to Val and Naigtal to Quell Leaders of the Void",
                "originalSummary": "Join the fight against the Void in a new World of Warcraft update.",
                "originalBody": "Join the fight against the Void in a new World of Warcraft update.\n\nThis full body needs LLM translation before public release.",
                "requiresLlmTranslation": True,
            }
        ]

        with patch.object(self.backend, "ENABLE_COLLECTORS", True), patch.object(self.backend, "load_seed_articles", return_value=[]), patch.object(
            self.backend,
            "collect_feed_articles",
            return_value=(collected, []),
        ):
            self.backend.refresh_articles("scheduled")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            article_count = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
            row = conn.execute("SELECT message FROM news_refresh_runs ORDER BY id DESC LIMIT 1").fetchone()

        message = json.loads(row[0])
        self.assertEqual(article_count, 0)
        self.assertEqual(message["blockedArticleCount"], 1)
        self.assertEqual(message["blockedArticles"][0]["id"], "auto-blizzard")
        self.assertEqual(message["blockedArticles"][0]["reason"], "llm_not_configured")

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
                        source_name, source_url, published_at, source_note,
                        body_zh, original_title, original_summary, original_body,
                        translation_status, content_status, tag_items_json, blocked_reason,
                        source_id, source_tier, license_status, verification_status,
                        source_badges_json, body_blocks_zh_json, canonical_topic_id,
                        reading_meta_json, translation_fidelity, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        *article,
                        f"中文正文：{article[2]} 这是一段用于列表筛选测试的完整中文正文，包含足够信息，不能被当作一句摘要。\n\n第二段确认详情页有完整正文。",
                        article[1],
                        article[2],
                        article[2],
                        "llm",
                        "ready",
                        '[{"id":"content-update","label":"内容更新"}]',
                        "",
                        "blizzard",
                        "official",
                        "approved",
                        "official_verified",
                        '["官方已核验","全文翻译"]',
                        json.dumps(
                            [
                                {
                                    "type": "paragraph",
                                    "text": f"中文正文：{article[2]} 这是一段用于列表筛选测试的完整中文正文，包含足够信息，不能被当作一句摘要。",
                                },
                                {"type": "paragraph", "text": "第二段确认详情页有完整正文。"},
                            ],
                            ensure_ascii=False,
                        ),
                        "news:1000",
                        '{"bodyBlockCount":2,"estimatedReadingMinutes":1}',
                        "source_translation",
                        "2026-06-09T03:33:40+00:00",
                    ),
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
        self.assertIn("scenarioWeights", detail["details"]["statWeights"])
        self.assertEqual(len(detail["details"]["statWeights"]["scenarioWeights"]), 3)
        self.assertEqual(detail["details"]["statWeights"]["sourceStatus"], "blocked")
        self.assertIn("validation", detail["details"]["statWeights"])

    def test_backend_exposes_pve_home_and_module_payloads_from_shared_data_modules(self):
        home = self.backend.get_pve_home_payload()
        module = self.backend.get_pve_module_payload("bossGuides")

        self.assertEqual(home["navTitle"], "副本")
        self.assertEqual(home["dataStatus"], "blocked")
        self.assertEqual(home["runtimeSeasonGate"], "external_sources_available")
        self.assertGreater(len(home["zones"]), 0)
        self.assertTrue(any(
            item["key"] == "specLadder"
            for zone in home["zones"]
            for item in zone["modules"]
        ))
        self.assertEqual(module["runtimeSeasonGate"], "external_sources_available")
        self.assertGreater(len(module["items"]), 0)
        self.assertEqual(module["itemCount"], len(module["items"]))

        spec_ladder = self.backend.get_pve_module_payload("specLadder")
        self.assertEqual(spec_ladder["key"], "specLadder")
        self.assertEqual(
            spec_ladder["itemCount"],
            sum(role["count"] for role in spec_ladder["roles"]),
        )
        self.assertGreater(len(spec_ladder["items"]), 0)
        self.assertEqual([role["key"] for role in spec_ladder["roles"]], ["dps", "tank", "healer"])
        self.assertEqual(
            [source["status"] for source in spec_ladder["sourceChecks"]],
            ["source_reference", "source_reference"],
        )
        self.assertTrue(all(source["blockers"] for source in spec_ladder["sourceChecks"]))

        malformed_spec_ladder = dict(spec_ladder)
        malformed_spec_ladder["sourceChecks"] = [
            {"key": "archon", "status": "verified", "sampleCount": "not-a-number"},
            {"key": "warcraftlogs", "status": "verified", "sampleCount": 10},
        ]
        self.assertFalse(self.backend.has_verified_external_pve_sources(malformed_spec_ladder))

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
            ["模拟 SimC", "分析 WCL", "炸鸡队长", "任务列表"],
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

    def test_simcraft_template_confirm_encodes_websim_talent_and_parses_complete_gear_without_llm(self):
        self.seed_simc_template_websim_nodes()
        simc_bin = Path(self.tmp.name) / "fake-simc-template-confirm"
        captured_profile = Path(self.tmp.name) / "unexpected-template-confirm-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'DPS=999999\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)

        import server.simulator_payload as simulator_payload

        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("simcraft_template confirm must not call LLM")
        )
        self.addCleanup(setattr, simulator_payload, "call_chat_completion", original_call_chat_completion)
        try:
            analysis = self.backend.analyze_and_store_simulator_task(self.simc_template_payload())
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        draft_profile = analysis["agent"]["draftProfile"]
        self.assertEqual(analysis["mode"], "simcraft_template")
        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertTrue(analysis["agent"]["canSubmitTask"])
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertFalse(captured_profile.exists())
        self.assertFalse(analysis["llm"]["called"])
        self.assertEqual(analysis["request"]["profileSource"], "template")
        self.assertIn("class_talents=1001:1", draft_profile)
        self.assertIn("spec_talents=2001:1", draft_profile)
        self.assertIn("hero_talents=3001:1", draft_profile)
        self.assertNotIn("talents=websim:", draft_profile)
        self.assertIn("head=template_head,id=250001,ilevel=289,bonus_id=13534/6652", draft_profile)
        self.assertIn("finger1=template_finger1,id=250011,ilevel=289,bonus_id=13534/6652,gem_id=213743,enchant_id=7334", draft_profile)
        self.assertIn("main_hand=template_main_hand,id=250015,ilevel=289,bonus_id=13534/6652,crafted_stats=32/49", draft_profile)
        self.assertEqual(len(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]), 16)

    def test_simcraft_template_confirm_accepts_official_talent_import_code(self):
        analysis = self.backend.analyze_and_store_simulator_task(
            self.simc_template_payload(talent_raw="talents=CAE_OFFICIAL_IMPORT_CODE")
        )

        draft_profile = analysis["agent"]["draftProfile"]
        self.assertEqual(analysis["mode"], "simcraft_template")
        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertIn("talents=CAE_OFFICIAL_IMPORT_CODE", draft_profile)
        self.assertNotIn("class_talents=", draft_profile)

    def test_simcraft_template_confirm_returns_deterministic_preview_report(self):
        self.seed_simc_template_websim_nodes()
        analysis = self.backend.analyze_and_store_simulator_task(self.simc_template_payload())

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["runPolicy"]["policy"], "confirm_only")
        self.assertEqual(analysis["evidenceState"]["phase"], "ready_to_submit")
        self.assertEqual(analysis["report"]["source"], "deterministic_confirm_preview")
        self.assertEqual(analysis["report"]["topFindings"][0]["evidenceRefs"], ["simc.confirmOnly", "simc.template"])
        self.assertIn("validated", analysis["report"]["topFindings"][0]["text"])
        self.assertIn("did not execute SimC", analysis["report"]["topFindings"][0]["text"])

    def test_simcraft_template_blocks_mismatched_class_spec(self):
        analysis = self.backend.analyze_and_store_simulator_task(
            self.simc_template_payload(talent_spec="arcane", gear_spec="frost")
        )

        self.assertEqual(analysis["mode"], "simcraft_template")
        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertIn("template class/spec mismatch", analysis["simulation"]["error"])
        self.assertIn("template class/spec mismatch", analysis["agent"]["validation"]["errors"])
        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["report"]["source"], "deterministic_blocked")
        self.assertEqual(analysis["report"]["topFindings"][0]["evidenceRefs"], ["simc.templateValidation"])
        self.assertIn("template class/spec mismatch", analysis["report"]["topFindings"][0]["text"])

    def test_simcraft_template_blocks_incomplete_gear_template(self):
        gear_raw = "\n".join(self.simc_template_full_gear_raw().splitlines()[:15])
        analysis = self.backend.analyze_and_store_simulator_task(
            self.simc_template_payload(gear_raw=gear_raw)
        )

        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertIn("missing gear slots: off_hand", analysis["simulation"]["error"])
        self.assertEqual(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"], [])

    def test_simcraft_template_final_submit_reuses_template_payload_runs_simc_and_saves_task(self):
        self.seed_simc_template_websim_nodes()
        simc_bin = Path(self.tmp.name) / "fake-simc-template-final"
        captured_profile = Path(self.tmp.name) / "captured-template-final-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'Player: TemplateArcaneMage\\n  DPS=654321 DPS-Error=0/0.00%%\\nScale Factors:\\nintellect=9.1 haste=6.4\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        request_payload = self.simc_template_payload(scenario="mythic_plus", analysis_type="stat_weights")
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device"})
        try:
            analysis = self.backend.analyze_and_store_simulator_task(request_payload)
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)

        executed_profile = captured_profile.read_text(encoding="utf-8")
        self.assertTrue(analysis["simulation"]["ran"])
        self.assertEqual(analysis["simulation"]["metrics"]["dps"], "654321")
        self.assertEqual(analysis["agent"]["status"], "simc_completed")
        self.assertTrue(analysis["taskId"])
        self.assertIn("fight_style=DungeonSlice", executed_profile)
        self.assertIn("desired_targets=5", executed_profile)
        self.assertIn("calculate_scale_factors=1", executed_profile)
        self.assertEqual(analysis["request"]["profile"], executed_profile.strip())
        self.assertEqual(analysis["request"]["templateContext"]["talent"]["id"], "talent-template-1")

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

    def test_simc_agent_preserves_websim_talent_state_but_still_requires_gear(self):
        self.patch_simc_confirmation_llm(
            self.confirmation_response(
                missing_slots=["gear"],
                question="已读取 WebSim 天赋编码；还差手选装备数据。",
            )
        )

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "simcraft_agent",
                "round": 1,
                "confirmOnly": True,
                "message": "请按这套冰法 WebSim 天赋，确认大秘境 AOE 是否能提交",
                "buildContext": {
                    "specId": "法师-冰霜",
                    "className": "法师",
                    "specName": "冰霜",
                    "role": "远程输出",
                    "activeQueryKey": "talents",
                    "activeQueryTitle": "天赋构筑",
                    "details": {
                        "talents": {
                            "importCode": "CAE_CONTEXT",
                            "simcLines": ["class_talents=1001:1", "spec_talents=2001:2"],
                            "encodingStatus": "encoded",
                        }
                    },
                    "simulatorState": {
                        "talent": {
                            "selectedNodes": [
                                {"id": "n1", "rank": 2, "tree": "spec", "name": "Ice Lance"},
                                {"id": "n2", "rank": 1, "tree": "hero", "name": "Spellslinger"},
                            ],
                            "websimExportCode": "websim:mage:frost:spellslinger:n1:2,n2:1",
                            "heroKey": "spellslinger",
                            "scenarioKey": "mythic_plus",
                            "encodingStatus": "encoded",
                        }
                    },
                },
            }
        )

        build_context = analysis["request"]["buildContext"]
        self.assertEqual(build_context["details"]["talents"]["simcLines"], ["class_talents=1001:1", "spec_talents=2001:2"])
        self.assertEqual(build_context["simulatorState"]["talent"]["websimExportCode"], "websim:mage:frost:spellslinger:n1:2,n2:1")
        self.assertEqual(build_context["simulatorState"]["talent"]["selectedNodes"][0]["name"], "Ice Lance")
        self.assertEqual(analysis["request"]["profileSource"], "generated")
        self.assertIn("gear", analysis["agent"]["missingSlots"])
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertFalse(analysis["simulation"]["ran"])

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
        self.assertIn("simc_benchmark", [stage["key"] for stage in analysis["stages"]])
        self.assertEqual(analysis["simulation"]["benchmark"]["status"], "reasonable")
        self.assertAlmostEqual(analysis["simulation"]["benchmark"]["ratioToAvg"], 0.997)
        self.assertLessEqual(len(analysis["recommendations"]), 3)
        self.assertLessEqual(len(analysis["agent"]["summaryCards"]), 3)
        self.assertIn("真实大秘境对标", json.dumps(analysis["agent"]["summaryCards"], ensure_ascii=False))

    def test_simc_agent_completed_report_exposes_structured_evidence_schema(self):
        simc_bin = Path(self.tmp.name) / "fake-evidence-report-simc"
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
        self.assertEqual(analysis["evidenceState"]["phase"], "report_ready")
        self.assertTrue(analysis["runPolicy"]["didRunSimc"])
        self.assertIn({"key": "simc.dps", "value": "185432"}, analysis["allowedNumbers"])
        self.assertEqual(analysis["report"]["schemaRevision"], "simc-report-v1")
        self.assertTrue(analysis["report"]["topFindings"][0]["evidenceRefs"])

    def test_simc_report_schema_rejects_llm_numbers_outside_allowed_numbers(self):
        import server.simulator_payload as simulator_payload

        simc_bin = Path(self.tmp.name) / "fake-schema-report-simc"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            "printf 'Player: RetPlayer\\n  DPS=185432 DPS-Error=0/0.00%%\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: {
            "called": True,
            "model": "fake",
            "content": json.dumps(
                {
                    "topFindings": [
                        {"text": "This profile is safely above 999999 DPS.", "evidenceRefs": ["simc.dps"]}
                    ],
                    "nextActions": ["Keep the setup."],
                    "limitations": ["Synthetic test."],
                }
            ),
            "error": "",
        }
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
            simulator_payload.call_chat_completion = original_call_chat_completion

        self.assertEqual(analysis["simulation"]["metrics"]["dps"], "185432")
        self.assertEqual(analysis["report"]["source"], "deterministic_fallback")
        self.assertNotIn("999999", json.dumps(analysis["report"], ensure_ascii=False))
        self.assertIn({"key": "simc.dps", "value": "185432"}, analysis["allowedNumbers"])

    def test_simc_agent_marks_extreme_completed_dps_as_external_outlier(self):
        simc_bin = Path(self.tmp.name) / "fake-outlier-report-simc"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "cat >/dev/null\n"
            "printf 'Player: RetPlayer\\n  DPS=999999 DPS-Error=0/0.00%%\\n'\n",
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

        benchmark = analysis["simulation"]["benchmark"]
        stage = next(stage for stage in analysis["stages"] if stage["key"] == "simc_benchmark")
        self.assertEqual(analysis["agent"]["status"], "simc_completed")
        self.assertEqual(benchmark["status"], "outlier_high")
        self.assertEqual(stage["status"], "blocked")
        self.assertIn("far above", benchmark["summary"])

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

    def test_init_db_records_schema_migrations_and_enforces_foreign_keys(self):
        self.backend.init_db()

        with self.backend.db_connection() as conn:
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            migrations = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT id, description FROM schema_migrations ORDER BY id"
                ).fetchall()
            }
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO user_build_templates (
                        id, user_id, template_type, title, raw_string,
                        simc_lines_json, status, status_label, source,
                        metadata_json, schema_version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "orphan-template",
                        404,
                        "talent",
                        "Orphan",
                        "websim:orphan",
                        "[]",
                        "draft",
                        "Draft",
                        "test",
                        "{}",
                        1,
                        "2026-06-19T00:00:00+00:00",
                        "2026-06-19T00:00:00+00:00",
                    ),
                )

        self.assertEqual(foreign_keys, 1)
        self.assertIn("core_schema_v1", migrations)
        self.assertIn("user_build_templates_v1", migrations)

    def test_init_db_skips_seed_writes_after_schema_is_initialized(self):
        self.backend.init_db()

        with patch.object(
            self.backend,
            "seed_news_sources",
            side_effect=AssertionError("init_db should not write seed data once initialized"),
        ):
            self.backend.init_db()

    def test_user_build_templates_are_synced_and_isolated_by_owner(self):
        login_a = self.backend.login_with_wechat_code(
            "wx-code-template-a",
            exchange_code=lambda code: {"openid": "openid-template-a"},
        )
        login_b = self.backend.login_with_wechat_code(
            "wx-code-template-b",
            exchange_code=lambda code: {"openid": "openid-template-b"},
        )

        first = self.backend.save_user_build_template(
            login_a["accessToken"],
            {
                "id": "local-talent-1",
                "type": "talent",
                "title": "Frost M+",
                "classKey": "mage",
                "specKey": "frost",
                "scenarioKey": "mythic_plus",
                "rawString": "websim:mage:frost:first",
                "simcLines": ["class_talents=1001:1"],
                "status": "encoded",
                "statusLabel": "Encoded",
                "metadata": {"sourcePage": "talent-simulator"},
                "updatedAt": "2026-06-19T00:00:00+00:00",
            },
        )
        duplicate = self.backend.save_user_build_template(
            login_a["accessToken"],
            {
                "id": "local-talent-2",
                "type": "talent",
                "title": "Frost Raid",
                "classKey": "mage",
                "specKey": "frost",
                "scenarioKey": "raid",
                "rawString": "websim:mage:frost:first",
                "simcLines": ["class_talents=1001:1"],
                "status": "encoded",
                "statusLabel": "Encoded",
                "metadata": {"sourcePage": "talent-simulator"},
                "updatedAt": "2026-06-19T01:00:00+00:00",
            },
        )
        self.backend.save_user_build_template(
            login_b["accessToken"],
            {
                "type": "gear",
                "title": "Other User Gear",
                "rawString": "head=,id=250001",
                "status": "simc_ready",
            },
        )

        list_a = self.backend.list_user_build_templates(login_a["accessToken"])
        list_b = self.backend.list_user_build_templates(login_b["accessToken"])

        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(duplicate["title"], "Frost Raid")
        self.assertEqual(duplicate["clientId"], "local-talent-2")
        self.assertEqual(duplicate["metadata"]["sourcePage"], "talent-simulator")
        self.assertEqual([item["id"] for item in list_a["templates"]], [first["id"]])
        self.assertEqual(list_b["templates"][0]["title"], "Other User Gear")
        with self.assertRaises(KeyError):
            self.backend.delete_user_build_template(login_b["accessToken"], first["id"])
        self.assertTrue(self.backend.delete_user_build_template(login_a["accessToken"], first["id"])["deleted"])
        self.assertEqual(self.backend.list_user_build_templates(login_a["accessToken"])["templates"], [])

    def test_user_build_templates_accept_string_only_talent_and_gear_templates(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-template-string-only",
            exchange_code=lambda code: {"openid": "openid-template-string-only"},
        )

        talent = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "talent",
                "rawString": "websim:mage:frost:saved",
            },
        )
        gear = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "gear",
                "rawString": "head=,id=250060,ilevel=707",
            },
        )
        listed = self.backend.list_user_build_templates(login["accessToken"])["templates"]

        self.assertEqual(talent["status"], "saved")
        self.assertEqual(talent["statusLabel"], "已保存")
        self.assertEqual(talent["simcLines"], [])
        self.assertEqual(gear["status"], "complete")
        self.assertEqual(gear["statusLabel"], "完整配置")
        self.assertEqual(gear["simcLines"], [])
        self.assertEqual({item["rawString"] for item in listed}, {talent["rawString"], gear["rawString"]})

    def test_http_me_build_templates_requires_auth_and_supports_crud(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-template-http",
            exchange_code=lambda code: {"openid": "openid-template-http"},
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/me/build-templates"
            with self.assertRaises(HTTPError) as context:
                urlopen(url, timeout=5)
            self.assertEqual(context.exception.code, 401)

            create_request = Request(
                url,
                data=json.dumps(
                    {
                        "template": {
                            "type": "gear",
                            "title": "HTTP Gear",
                            "rawString": "head=,id=250777",
                            "status": "simc_ready",
                            "updatedAt": "2026-06-19T00:00:00+00:00",
                        }
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {login['accessToken']}",
                },
                method="POST",
            )
            with urlopen(create_request, timeout=5) as response:
                created = json.loads(response.read().decode("utf-8"))
            template_id = created["template"]["id"]

            list_request = Request(url, headers={"Authorization": f"Bearer {login['accessToken']}"})
            with urlopen(list_request, timeout=5) as response:
                listed = json.loads(response.read().decode("utf-8"))

            delete_request = Request(
                f"{url}?id={template_id}",
                headers={"Authorization": f"Bearer {login['accessToken']}"},
                method="DELETE",
            )
            with urlopen(delete_request, timeout=5) as response:
                deleted = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(created["template"]["title"], "HTTP Gear")
        self.assertEqual(listed["templates"][0]["id"], template_id)
        self.assertTrue(deleted["deleted"])

    def test_data_health_payload_aggregates_trust_status_without_external_sync(self):
        self.backend.refresh_articles("scheduled")

        with patch.object(self.backend, "sync_raiderio_cache", side_effect=AssertionError("health must be read-only")):
            payload = self.backend.build_data_health_payload()

        allowed = {"verified", "partial", "stale", "blocked", "missing_credentials", "pending_official_audit", "source_reference"}
        components = {item["key"]: item for item in payload["components"]}

        self.assertEqual(payload["schemaRevision"], "data-health-v1")
        self.assertIn(payload["overallStatus"], allowed)
        self.assertEqual(set(payload["allowedStatuses"]), allowed)
        self.assertTrue({"news", "raiderio", "websim_season", "community_templates", "stat_weights", "wcl_credentials"}.issubset(components))
        self.assertTrue(all(item["status"] in allowed for item in payload["components"]))
        self.assertEqual(components["raiderio"]["status"], "missing_credentials")
        self.assertEqual(components["wcl_credentials"]["status"], "missing_credentials")
        self.assertNotIn("fake-api-key", json.dumps(payload, ensure_ascii=False))

    def test_data_health_payload_exposes_raiderio_target_item_coverage(self):
        import server.raiderio_payload as raiderio_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            raiderio_payload.write_cache(
                conn,
                {
                    "sourceName": "Raider.IO",
                    "sourceStatus": "partial",
                    "status": "partial",
                    "region": "cn",
                    "locale": "zh_CN",
                    "seasonSlug": "season-tww-3",
                    "checkedAt": "2026-06-22T00:00:00+00:00",
                    "expiresAt": raiderio_payload.iso_after(6),
                    "staleAt": raiderio_payload.iso_after(48),
                    "errors": [],
                    "runCount": 160,
                    "profileCount": 183,
                    "profileLimitPerSpec": 5,
                    "targetItemCoverage": {
                        "targetItemCount": 35,
                        "matchedTargetItemIds": ["251111", "251166", "251171"],
                        "missingTargetItemIds": ["250223"],
                        "targetProfileRequestLimit": 120,
                    },
                    "runs": [],
                    "profiles": [],
                    "specAggregates": [],
                },
            )
            conn.commit()

        with patch.object(self.backend, "sync_raiderio_cache", side_effect=AssertionError("health must be read-only")):
            payload = self.backend.build_data_health_payload()

        component = {item["key"]: item for item in payload["components"]}["raiderio"]

        self.assertEqual(component["status"], "partial")
        self.assertEqual(component["details"]["profileCount"], 183)
        self.assertEqual(
            component["details"]["targetItemCoverage"],
            {
                "targetItemCount": 35,
                "matchedTargetItemIds": ["251111", "251166", "251171"],
                "missingTargetItemIds": ["250223"],
                "targetProfileRequestLimit": 120,
            },
        )

    def test_data_health_payload_includes_gear_catalog_component(self):
        import server.websim_payload as websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.save_websim_item_metadata(
                conn,
                "250777",
                {
                    "id": 250777,
                    "name": "Health Catalog Hood",
                    "inventory_type": {"type": "HEAD", "name": "Head"},
                    "item_class": {"id": 4, "name": "Armor"},
                    "item_subclass": {"id": 1, "name": "Cloth"},
                    "quality": {"name": "Epic"},
                    "preview_item": {
                        "stats": [{"type": {"type": "INTELLECT", "name": "Intellect"}, "value": 1234}],
                    },
                },
                fallback_name="Health Catalog Hood",
                english_payload={"name": "Health Catalog Hood", "inventory_type": {"name": "Head"}},
                locale="en_US",
            )
            websim_payload.upsert_gear_source(
                conn,
                {
                    "id": "source-250777",
                    "itemId": "250777",
                    "sourceType": "dungeon",
                    "sourceLabel": "Health Catalog Dungeon",
                },
            )
            websim_payload.upsert_gear_variant(
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
                    "status": "partial",
                    "blockers": ["missing deterministic SimC variant preset"],
                },
            )
            websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                {
                    "status": "verified",
                    "itemCount": 12,
                    "variantCount": 21,
                    "itemDatabaseRevision": "items-test-rev",
                    "variantRevision": "variants-test-rev",
                    "checkedAt": "2026-06-19T00:00:00+00:00",
                },
            )
            conn.commit()

        payload = self.backend.build_data_health_payload()
        components = {item["key"]: item for item in payload["components"]}

        self.assertIn("gear_catalog", components)
        self.assertEqual(components["gear_catalog"]["status"], "partial")
        self.assertEqual(components["gear_catalog"]["details"]["itemCount"], 1)
        self.assertEqual(components["gear_catalog"]["details"]["variantCount"], 1)
        self.assertEqual(components["gear_catalog"]["details"]["itemDatabaseRevision"], "items-test-rev")
        self.assertEqual(
            components["gear_catalog"]["details"]["variantReadiness"],
            {"verified": 0, "partial": 1, "blocked": 0, "total": 1},
        )
        self.assertEqual(
            components["gear_catalog"]["details"]["modOptionCoverage"],
            {
                "socket": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
                "enchant": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
            },
        )
        self.assertEqual(
            components["gear_catalog"]["details"]["topBlockers"][0],
            {"reason": "missing deterministic SimC variant preset", "count": 1},
        )
        self.assertIn("missing deterministic SimC variant preset", components["gear_catalog"]["blockers"])

    def test_data_health_payload_includes_observed_backfill_defaults_without_syncing(self):
        with patch.object(self.backend, "sync_raiderio_cache", side_effect=AssertionError("health must be read-only")):
            payload = self.backend.build_data_health_payload()

        component = {item["key"]: item for item in payload["components"]}["gear_catalog"]
        backfill = component["details"]["observedBackfill"]

        self.assertEqual(backfill["provider"], "raiderio")
        self.assertEqual(backfill["lastRunStatus"], "idle")
        self.assertEqual(backfill["providers"]["wcl"]["status"], "not_implemented")
        self.assertEqual(backfill["cursor"]["targetItemCount"], 0)
        self.assertEqual(backfill["matchedTargetItemIds"], [])
        self.assertEqual(backfill["matchedTargetItemCount"], 0)

    def test_data_health_payload_includes_observed_backfill_state_without_syncing(self):
        import server.websim_payload as websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            state = websim_payload.read_gear_observed_backfill_state(conn, target_item_ids=["251111", "251222"])
            state["lastRunStatus"] = "partial"
            state["processedTargetItemCount"] = 2
            state["processedProfileCount"] = 3
            state["matchedTargetItemIds"] = ["251111"]
            state["lastError"] = "one profile failed"
            state["cursor"]["targetOffset"] = 1
            state["cursor"]["profileOffset"] = 3
            websim_payload.write_gear_observed_backfill_state(conn, state)
            conn.commit()

        with patch.object(self.backend, "sync_raiderio_cache", side_effect=AssertionError("health must be read-only")):
            payload = self.backend.build_data_health_payload()

        component = {item["key"]: item for item in payload["components"]}["gear_catalog"]
        backfill = component["details"]["observedBackfill"]

        self.assertEqual(backfill["provider"], "raiderio")
        self.assertEqual(backfill["lastRunStatus"], "partial")
        self.assertEqual(backfill["processedTargetItemCount"], 2)
        self.assertEqual(backfill["processedProfileCount"], 3)
        self.assertEqual(backfill["matchedTargetItemIds"], ["251111"])
        self.assertEqual(backfill["matchedTargetItemCount"], 1)
        self.assertEqual(backfill["lastError"], "one profile failed")
        self.assertEqual(backfill["cursor"]["targetOffset"], 1)
        self.assertEqual(backfill["cursor"]["profileOffset"], 3)

    def test_data_health_payload_includes_community_template_scan_coverage(self):
        import server.websim_payload as websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.set_sync_state(
                conn,
                websim_payload.COMMUNITY_TALENT_SYNC_KEY,
                {
                    "sourceStatus": "partial",
                    "templateRevision": "community-template-v1-test",
                    "scanCoverage": {
                        "totalClassCount": 13,
                        "totalSpecCount": 40,
                        "coveredSpecCount": 38,
                        "missingSpecs": ["rogue:subtlety", "shaman:restoration"],
                    },
                    "dedupedCount": 72,
                    "hiddenDuplicateCount": 18,
                    "sources": {
                        "raiderio": {"status": "synced", "sourceName": "Raider.IO", "errors": []},
                        "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "errors": []},
                    },
                    "templates": {"total": 90, "verified": 80, "blocked": 10},
                    "checkedAt": "2026-06-20T08:00:00+00:00",
                },
            )
            conn.commit()

        payload = self.backend.build_data_health_payload()
        component = {item["key"]: item for item in payload["components"]}["community_templates"]

        self.assertEqual(component["status"], "partial")
        self.assertEqual(component["details"]["templateRevision"], "community-template-v1-test")
        self.assertEqual(component["details"]["scanCoverage"]["totalSpecCount"], 40)
        self.assertEqual(component["details"]["scanCoverage"]["coveredSpecCount"], 38)
        self.assertEqual(component["details"]["dedupedCount"], 72)
        self.assertEqual(component["details"]["hiddenDuplicateCount"], 18)
        self.assertEqual(component["details"]["wclTemplateSource"]["status"], "missing_credentials")

    def test_data_health_websim_sync_uses_ok_state_without_legacy_counts(self):
        import server.websim_payload as websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.set_sync_state(
                conn,
                "websim_sync",
                {
                    "ok": True,
                    "dataStatus": "verified",
                    "checkedAt": "2026-06-20T06:05:08+00:00",
                    "errors": [],
                    "simc": {"talents": 5246, "presets": 50},
                    "gearCatalog": {
                        "status": "partial",
                        "itemCount": 114,
                        "verifiedCount": 93,
                        "observedVariantCount": 93,
                    },
                    "currentSeason": {"dataStatus": "verified", "seasonRevision": "season-test"},
                },
            )
            conn.commit()

        payload = self.backend.build_data_health_payload()
        component = {item["key"]: item for item in payload["components"]}["websim_sync"]

        self.assertEqual(component["status"], "verified")
        self.assertEqual(component["blockers"], [])
        self.assertEqual(component["details"]["talentCount"], 5246)
        self.assertEqual(component["details"]["gearItemCount"], 114)
        self.assertEqual(component["details"]["observedVariantCount"], 93)

    def test_data_health_accepts_warcraftlogs_v1_api_key_without_exposing_secret(self):
        os.environ["WOW_WARCRAFTLOGS_API_KEY"] = "fake-wcl-v1-key"

        payload = self.backend.build_data_health_payload()
        components = {item["key"]: item for item in payload["components"]}

        self.assertEqual(components["wcl_credentials"]["status"], "partial")
        self.assertEqual(components["wcl_credentials"]["details"]["api"], "warcraftlogs-v1-rest")
        self.assertTrue(components["wcl_credentials"]["details"]["configured"])
        self.assertNotIn("fake-wcl-v1-key", json.dumps(payload, ensure_ascii=False))

    def test_data_health_component_with_blockers_cannot_remain_verified(self):
        component = self.backend.data_health_component(
            "fixture_source",
            "Fixture source",
            "verified",
            blockers=["fixture data is not authorized API evidence"],
        )
        payload = {
            "components": [
                self.backend.data_health_component("backend", "Backend", "verified"),
                component,
            ]
        }

        self.assertEqual(component["status"], "blocked")
        self.assertEqual(self.backend.data_health_overall_status(payload["components"]), "partial")

    def test_http_data_health_route_returns_read_only_status_payload(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/data/health", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["schemaRevision"], "data-health-v1")
        self.assertIn("components", payload)
        self.assertTrue(any(item["key"] == "websim_season" for item in payload["components"]))

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

    def test_wcl_analysis_extracts_report_code_and_blocks_without_credentials(self):
        import server.simulator_payload as simulator_payload

        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("WCL evidence bootstrap must not call LLM without log evidence")
        )
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "wcl",
                    "prompt": (
                        "Please review https://www.warcraftlogs.com/reports/AbC123xYz"
                        "#fight=7&type=damage-done for my burst timing."
                    ),
                    "question": "Why is my damage low?",
                }
            )
        finally:
            simulator_payload.call_chat_completion = original_call_chat_completion

        self.assertEqual(analysis["mode"], "wcl")
        self.assertEqual(analysis["logEvidence"]["schemaRevision"], "wcl-log-evidence-v1")
        self.assertEqual(analysis["logEvidence"]["status"], "blocked")
        self.assertEqual(analysis["logEvidence"]["sourceStatus"], "missing_credentials")
        self.assertEqual(analysis["logEvidence"]["reportCode"], "AbC123xYz")
        self.assertEqual(analysis["logEvidence"]["fightId"], "7")
        self.assertIn("wcl.credentials", analysis["logEvidence"]["missingInputs"])
        self.assertEqual(analysis["report"]["schemaRevision"], "wcl-report-v1")
        self.assertEqual(analysis["report"]["source"], "deterministic_blocked")
        self.assertFalse(analysis["llm"]["called"])

    def test_wcl_analysis_fetches_v2_graphql_evidence_before_reporting_ready(self):
        os.environ["WOW_WARCRAFTLOGS_CLIENT_ID"] = "fake-client-id"
        os.environ["WOW_WARCRAFTLOGS_CLIENT_SECRET"] = "fake-client-secret"

        def fake_urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            if "oauth/token" in url:
                return FakeHttpResponse({"access_token": "fake-access-token"})
            self.assertIn("api/v2/client", url)
            return FakeHttpResponse(
                {
                    "data": {
                        "reportData": {
                            "report": {
                                "title": "Mythic Pulls",
                                "startTime": 1000,
                                "endTime": 2000,
                                "fights": [
                                    {
                                        "id": 7,
                                        "name": "Nexus-Princess Ky'veza",
                                        "difficulty": 5,
                                        "kill": True,
                                        "startTime": 1100,
                                        "endTime": 1900,
                                    }
                                ],
                                "events": {
                                    "data": [
                                        {"type": "cast", "ability": {"name": "Icy Veins"}},
                                        {"type": "death", "target": {"name": "Mage"}},
                                        {"type": "damage", "amount": 12345},
                                        {"type": "heal", "amount": 2345},
                                        {"type": "applybuff", "ability": {"name": "Icy Veins"}},
                                    ]
                                },
                            }
                        }
                    }
                }
            )

        from server import simulator_payload

        with patch.object(simulator_payload, "urlopen", side_effect=fake_urlopen, create=True):
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "wcl",
                    "wclUrl": "https://www.warcraftlogs.com/reports/V2Report123?fight=7",
                    "question": "Check cooldown usage.",
                }
            )

        self.assertEqual(analysis["logEvidence"]["status"], "ready")
        self.assertEqual(analysis["logEvidence"]["sourceStatus"], "verified")
        self.assertEqual(analysis["logEvidence"]["credentialMode"], "v2_oauth")
        self.assertEqual(analysis["logEvidence"]["reportTitle"], "Mythic Pulls")
        self.assertEqual(analysis["logEvidence"]["fight"]["id"], "7")
        self.assertEqual(analysis["logEvidence"]["eventSummary"]["casts"], 1)
        self.assertEqual(analysis["logEvidence"]["eventSummary"]["deaths"], 1)
        self.assertEqual(analysis["logEvidence"]["eventSummary"]["damageEvents"], 1)
        self.assertEqual(analysis["logEvidence"]["eventSummary"]["healingEvents"], 1)
        self.assertEqual(analysis["report"]["source"], "deterministic_evidence")
        self.assertFalse(analysis["llm"]["called"])
        self.assertNotIn("fake-client-secret", json.dumps(analysis, ensure_ascii=False))

    def test_wcl_analysis_reports_graphql_fetch_failure_without_llm_claims(self):
        os.environ["WOW_WARCRAFTLOGS_CLIENT_ID"] = "fake-client-id"
        os.environ["WOW_WARCRAFTLOGS_CLIENT_SECRET"] = "fake-client-secret"

        def fake_urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            if "oauth/token" in url:
                return FakeHttpResponse({"access_token": "fake-access-token"})
            return FakeHttpResponse({"errors": [{"message": "report not visible"}]})

        from server import simulator_payload

        with patch.object(simulator_payload, "urlopen", side_effect=fake_urlopen, create=True):
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "wcl",
                    "wclUrl": "https://www.warcraftlogs.com/reports/HiddenReport?fight=3",
                    "question": "Check cooldown usage.",
                }
            )

        self.assertEqual(analysis["logEvidence"]["status"], "blocked")
        self.assertEqual(analysis["logEvidence"]["sourceStatus"], "blocked")
        self.assertIn("wcl.graphql_fetch", analysis["logEvidence"]["missingInputs"])
        self.assertIn("report not visible", analysis["logEvidence"]["blockers"][0])
        self.assertEqual(analysis["report"]["source"], "deterministic_blocked")
        self.assertFalse(analysis["llm"]["called"])

    def test_wcl_analysis_accepts_warcraftlogs_v1_api_key_as_configured(self):
        os.environ["WOW_WARCRAFTLOGS_API_KEY"] = "fake-wcl-v1-key"

        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "wcl",
                "wclUrl": "https://www.warcraftlogs.com/reports/ApiKey123?fight=5",
                "question": "Check cooldown usage.",
            }
        )

        self.assertEqual(analysis["logEvidence"]["status"], "pending_fetch")
        self.assertEqual(analysis["logEvidence"]["sourceStatus"], "credentials_configured")
        self.assertEqual(analysis["logEvidence"]["credentialMode"], "v1_api_key")
        self.assertEqual(analysis["logEvidence"]["api"], "warcraftlogs-v1-rest")
        self.assertNotIn("fake-wcl-v1-key", json.dumps(analysis, ensure_ascii=False))

    def test_wcl_analysis_requires_report_code_or_url(self):
        analysis = self.backend.analyze_simulator_request(
            {"mode": "wcl", "question": "Review my boss pull."}
        )

        self.assertEqual(analysis["logEvidence"]["status"], "missing_input")
        self.assertEqual(analysis["logEvidence"]["sourceStatus"], "missing_report")
        self.assertIn("wcl.report", analysis["logEvidence"]["missingInputs"])
        self.assertFalse(analysis["llm"]["called"])
        self.assertIn("wcl.report", analysis["report"]["topFindings"][0]["evidenceRefs"])

    def test_chickenbro_v0_returns_schema_bound_missing_inputs_without_llm(self):
        import server.simulator_payload as simulator_payload

        original_call_chat_completion = simulator_payload.call_chat_completion
        simulator_payload.call_chat_completion = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("chickenbro v0 must not call LLM when evidence is missing")
        )
        try:
            analysis = self.backend.analyze_simulator_request(
                {
                    "mode": "chickenbro",
                    "question": "Confirm I rank 99th and do 999999 DPS.",
                }
            )
        finally:
            simulator_payload.call_chat_completion = original_call_chat_completion

        self.assertEqual(analysis["mode"], "chickenbro")
        self.assertEqual(analysis["status"], "blocked")
        self.assertEqual(analysis["schemaRevision"], "chickenbro-coach-v0")
        self.assertFalse(analysis["llm"]["called"])
        coach = analysis["coach"]
        self.assertEqual(
            set(coach.keys()),
            {"summary", "confidence", "evidenceRefs", "priorityActions", "missingInputs", "nextSteps"},
        )
        self.assertEqual(coach["confidence"], "blocked")
        self.assertEqual(coach["priorityActions"], [])
        self.assertIn("simc.report", coach["missingInputs"])
        self.assertIn("wcl.events", coach["missingInputs"])
        self.assertIn("character.context", coach["missingInputs"])
        self.assertIn("comparable.sample", coach["missingInputs"])
        coach_json = json.dumps(coach, ensure_ascii=False)
        self.assertNotIn("999999", coach_json)
        self.assertNotIn("99th", coach_json)

    def test_chickenbro_v0_actions_are_bound_to_supplied_evidence_refs(self):
        analysis = self.backend.analyze_simulator_request(
            {
                "mode": "chickenbro",
                "question": "Tell me if I am 99th percentile with 999999 DPS.",
                "evidence": {
                    "character": {
                        "className": "Mage",
                        "specName": "Arcane",
                        "role": "damage",
                        "itemLevel": 710,
                        "scenario": "mythic_plus",
                    },
                    "simc": {
                        "evidenceState": {"phase": "report_ready", "simcRan": True, "hasDps": True},
                        "runPolicy": {"policy": "full_simc"},
                        "allowedNumbers": [{"key": "simc.dps", "value": "185432"}],
                        "report": {
                            "topFindings": [
                                {
                                    "text": "SimC completed with DPS 185432.",
                                    "evidenceRefs": ["simc.dps"],
                                }
                            ],
                            "nextActions": ["Validate changes against the completed SimC run."],
                        },
                    },
                    "wcl": {
                        "logEvidence": {
                            "status": "ready",
                            "sourceStatus": "verified",
                            "evidenceRefs": ["wcl.report", "wcl.events"],
                            "eventSummary": {"casts": 1, "deaths": 0},
                        },
                        "report": {
                            "topFindings": [
                                {
                                    "text": "Warcraft Logs evidence is parsed for the selected fight.",
                                    "evidenceRefs": ["wcl.report", "wcl.events"],
                                }
                            ],
                            "nextActions": ["Review cooldown timing against selected fight events."],
                        },
                    },
                },
            }
        )

        self.assertEqual(analysis["mode"], "chickenbro")
        self.assertEqual(analysis["status"], "ready")
        coach = analysis["coach"]
        self.assertEqual(
            set(coach.keys()),
            {"summary", "confidence", "evidenceRefs", "priorityActions", "missingInputs", "nextSteps"},
        )
        self.assertEqual(coach["confidence"], "medium")
        self.assertIn("simc.dps", coach["evidenceRefs"])
        self.assertIn("wcl.events", coach["evidenceRefs"])
        self.assertIn("comparable.sample", coach["missingInputs"])
        self.assertLessEqual(len(coach["priorityActions"]), 3)
        for action in coach["priorityActions"]:
            self.assertTrue(action["title"])
            self.assertTrue(action["evidenceRefs"])
            self.assertTrue(set(action["evidenceRefs"]).issubset(set(coach["evidenceRefs"])))
        coach_json = json.dumps(coach, ensure_ascii=False)
        self.assertNotIn("999999", coach_json)
        self.assertNotIn("99th percentile", coach_json)

    def seed_chickenbro_profile(self, **overrides):
        profile = {
            "profileKey": "retail:cn:mage:arcane:mplus_fortified",
            "productPhase": "retail",
            "seasonSlug": "season-mn-1",
            "patchVersion": "11.1.7",
            "region": "cn",
            "classKey": "mage",
            "specKey": "arcane",
            "role": "damage",
            "scenarioKey": "mplus_fortified",
            "status": "published",
            "sourceStatus": "verified",
            "checkedAt": "2026-06-22T00:00:00+00:00",
            "publishedAt": "2026-06-22T00:00:00+00:00",
            "staleAt": "2026-06-29T00:00:00+00:00",
            "expiresAt": "2026-07-06T00:00:00+00:00",
            "payload": {
                "identity": {"className": "Mage", "specName": "Arcane"},
                "sourceCoverage": {
                    "raiderio": {"status": "verified", "sampleCount": 80},
                    "wcl": {"status": "partial", "sampleCount": 12},
                    "simc": {"status": "verified"},
                },
                "sampleWindow": {"region": "cn", "from": "2026-06-15", "to": "2026-06-22"},
                "buildTrends": {"summary": "Arcane prefers planned burst windows in fortified keys."},
                "performanceModel": {"allowedNumbers": [{"key": "sample.count", "value": "80"}]},
                "combatInsights": {"summary": "Hold major cooldowns for dense pulls."},
                "coachPack": {
                    "summary": "奥法在强韧大秘境里优先围绕大波次规划爆发。",
                    "priorityActions": [
                        {"title": "先确认大波次爆发窗口，再微调饰品和天赋。", "evidenceRefs": ["profile.summary"]}
                    ],
                    "limitations": [],
                },
                "limitations": [],
                "evidenceRefs": [
                    {"id": "profile.summary", "source": "raiderio+simc", "status": "verified"}
                ],
                "review": {"status": "auto_published"},
                "runtimeProjection": {
                    "summary": "奥法在强韧大秘境里优先围绕大波次规划爆发。",
                    "evidenceRefs": ["profile.summary"],
                    "allowedNumbers": [{"key": "sample.count", "value": "80"}],
                },
            },
        }
        profile.update(overrides)
        self.backend.upsert_chickenbro_spec_profile(profile)
        return profile

    def test_chickenbro_schema_initializes_sessions_jobs_profiles_and_structured_memory(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-chickenbro-memory",
            exchange_code=lambda code: {"openid": "openid-chickenbro-memory"},
        )

        result = self.backend.send_chickenbro_message(
            {
                "message": "我是奥法，主要打强韧大秘境，后面继续按这个角色分析。",
                "context": {
                    "character": {"classKey": "mage", "specKey": "arcane", "role": "damage"},
                    "scenarioKey": "mplus_fortified",
                    "rawWclLog": "RAW_LOG_SHOULD_NOT_ENTER_MEMORY",
                    "simcProfile": "SIMC_PROFILE_SHOULD_NOT_ENTER_MEMORY",
                },
            },
            access_token=login["accessToken"],
        )

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND (name LIKE 'chickenbro_%' OR name = 'agent_jobs')"
                ).fetchall()
            }
            memory_row = conn.execute(
                "SELECT profile_json FROM chickenbro_user_profiles WHERE user_id = ?",
                (login["user"]["id"],),
            ).fetchone()

        self.assertIn("chickenbro_sessions", tables)
        self.assertIn("chickenbro_messages", tables)
        self.assertIn("chickenbro_spec_profiles", tables)
        self.assertIn("chickenbro_user_profiles", tables)
        self.assertIn("agent_jobs", tables)
        self.assertTrue(result["session"]["sessionId"])
        memory_json = memory_row[0]
        self.assertIn("arcane", memory_json)
        self.assertIn("mplus_fortified", memory_json)
        self.assertNotIn("RAW_LOG_SHOULD_NOT_ENTER_MEMORY", memory_json)
        self.assertNotIn("SIMC_PROFILE_SHOULD_NOT_ENTER_MEMORY", memory_json)

    def test_chickenbro_profile_gate_uses_published_global_profile_and_partial_cn_as_background(self):
        self.seed_chickenbro_profile(status="partial", sourceStatus="partial")
        self.seed_chickenbro_profile(
            profileKey="retail:global:mage:arcane:mplus_fortified",
            region="global",
            payload={
                "identity": {"className": "Mage", "specName": "Arcane"},
                "sourceCoverage": {"raiderio": {"status": "verified", "sampleCount": 240}},
                "sampleWindow": {"region": "global", "from": "2026-06-15", "to": "2026-06-22"},
                "coachPack": {
                    "summary": "Global samples confirm Arcane should plan burst around fortified trash packs.",
                    "priorityActions": [
                        {"title": "Use burst cooldowns on planned high-density pulls.", "evidenceRefs": ["global.summary"]}
                    ],
                },
                "limitations": ["CN sample is partial, so this uses global fallback evidence."],
                "evidenceRefs": [
                    {"id": "global.summary", "source": "raiderio", "status": "verified"}
                ],
                "runtimeProjection": {
                    "summary": "Global samples confirm Arcane should plan burst around fortified trash packs.",
                    "evidenceRefs": ["global.summary"],
                    "allowedNumbers": [{"key": "sample.count", "value": "240"}],
                },
            },
        )
        captured = {}

        def fake_codex_runner(prompt, **kwargs):
            captured["prompt"] = prompt
            return {
                "status": "succeeded",
                "lastMessage": json.dumps(
                    {
                        "answer": "先按 global.summary 调整强韧波次爆发；CN 样本不足，只能作为背景。",
                        "confidence": "medium",
                        "priorityActions": [
                            {"title": "Use burst cooldowns on planned high-density pulls.", "evidenceRefs": ["global.summary"]}
                        ],
                        "evidenceRefs": ["global.summary"],
                        "limitations": ["CN sample is partial."],
                    },
                    ensure_ascii=False,
                ),
            }

        result = self.backend.send_chickenbro_message(
            {
                "message": "奥法强韧大秘境怎么优化爆发？",
                "guestId": "profile-gate-device",
                "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
            },
            codex_runner=fake_codex_runner,
        )

        bounded_context = json.loads(captured["prompt"])["boundedContext"]
        self.assertEqual(bounded_context["usableProfiles"][0]["region"], "global")
        self.assertEqual(bounded_context["usableProfiles"][0]["status"], "published")
        self.assertEqual(bounded_context["backgroundProfiles"][0]["region"], "cn")
        self.assertEqual(bounded_context["backgroundProfiles"][0]["status"], "partial")
        self.assertIn("cn_sample_insufficient_global_fallback", bounded_context["limitations"])
        self.assertEqual(result["job"]["status"], "succeeded")
        self.assertEqual(result["assistantMessage"]["payload"]["answerSource"], "codex")
        self.assertIn("global.summary", result["assistantMessage"]["payload"]["evidenceRefs"])

    def test_chickenbro_profile_upsert_preserves_published_at_on_status_downgrade(self):
        self.seed_chickenbro_profile(
            profileKey="retail:cn:mage:arcane:mplus_fortified",
            status="published",
            publishedAt="2026-06-22T00:00:00+00:00",
        )

        update_result = self.backend.upsert_chickenbro_spec_profile(
            {
                "profileKey": "retail:cn:mage:arcane:mplus_fortified",
                "productPhase": "retail",
                "seasonSlug": "season-mn-1",
                "patchVersion": "11.1.7",
                "region": "cn",
                "classKey": "mage",
                "specKey": "arcane",
                "role": "damage",
                "scenarioKey": "mplus_fortified",
                "status": "partial",
                "sourceStatus": "partial",
                "checkedAt": "2026-06-23T00:00:00+00:00",
                "payload": {
                    "coachPack": {"summary": "CN sample fell below the publish threshold."},
                    "runtimeProjection": {"summary": "CN sample fell below the publish threshold."},
                },
            }
        )
        profiles = self.backend.get_chickenbro_profiles(
            {
                "phase": "retail",
                "region": "cn",
                "class": "mage",
                "spec": "arcane",
                "scenario": "mplus_fortified",
            }
        )["profiles"]

        self.assertTrue(update_result["statusChanged"])
        self.assertEqual(update_result["previousStatus"], "published")
        self.assertEqual(update_result["status"], "partial")
        self.assertEqual(profiles[0]["status"], "partial")
        self.assertEqual(profiles[0]["publishedAt"], "2026-06-22T00:00:00+00:00")

    def test_chickenbro_rejects_non_wow_scope_without_calling_codex(self):
        def fail_if_called(*args, **kwargs):
            raise AssertionError("out-of-scope chickenbro requests must not call Codex")

        result = self.backend.send_chickenbro_message(
            {"message": "今天北京天气怎么样？", "guestId": "scope-device"},
            codex_runner=fail_if_called,
        )

        self.assertEqual(result["job"]["status"], "succeeded")
        self.assertEqual(result["assistantMessage"]["payload"]["answerSource"], "deterministic_scope_refusal")
        self.assertIn("只回答魔兽世界正式服和 PTR", result["assistantMessage"]["content"])
        self.assertEqual(result["job"]["result"]["topic"]["status"], "out_of_scope")

    def test_chickenbro_invalid_codex_output_downgrades_to_deterministic_answer(self):
        self.seed_chickenbro_profile()

        def fake_codex_runner(prompt, **kwargs):
            return {
                "status": "succeeded",
                "lastMessage": json.dumps(
                    {
                        "answer": "你现在可以稳定打 999999 DPS，参考 made.up。",
                        "confidence": "high",
                        "priorityActions": [{"title": "Trust invented data.", "evidenceRefs": ["made.up"]}],
                        "evidenceRefs": ["made.up"],
                    },
                    ensure_ascii=False,
                ),
            }

        result = self.backend.send_chickenbro_message(
            {
                "message": "奥法强韧大秘境怎么优化？",
                "guestId": "invalid-codex-device",
                "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
            },
            codex_runner=fake_codex_runner,
        )

        payload = result["assistantMessage"]["payload"]
        self.assertEqual(payload["answerSource"], "deterministic_fallback")
        self.assertIn("codex_output_invalid", result["job"]["result"]["validation"]["error"])
        self.assertNotIn("999999", result["assistantMessage"]["content"])
        self.assertNotIn("made.up", json.dumps(payload, ensure_ascii=False))
        self.assertIn("profile.summary", payload["evidenceRefs"])

    def test_chickenbro_codex_schema_is_strict_for_responses_api(self):
        self.seed_chickenbro_profile()
        captured = {}

        def fake_codex_runner(prompt, **kwargs):
            captured["schema"] = kwargs.get("schema")
            return {
                "status": "succeeded",
                "lastMessage": json.dumps(
                    {
                        "answer": "先根据 profile.summary 安排强韧波次爆发。",
                        "confidence": "medium",
                        "priorityActions": [
                            {"title": "围绕强韧小怪波次规划爆发。", "evidenceRefs": ["profile.summary"]}
                        ],
                        "evidenceRefs": ["profile.summary"],
                        "limitations": ["缺少玩家自己的 WCL 和完整 SimC。"],
                    },
                    ensure_ascii=False,
                ),
            }

        result = self.backend.send_chickenbro_message(
            {
                "message": "奥法强韧大秘境怎么优化？",
                "guestId": "strict-schema-device",
                "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
            },
            codex_runner=fake_codex_runner,
        )

        self.assertEqual(result["assistantMessage"]["payload"]["answerSource"], "codex")
        schema = captured["schema"]
        self.assertIs(schema["additionalProperties"], False)
        action_items = schema["properties"]["priorityActions"]["items"]
        self.assertIs(action_items["additionalProperties"], False)

    def test_http_chickenbro_api_supports_guest_session_job_and_owner_isolation(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            message_request = Request(
                f"http://127.0.0.1:{server.server_port}/api/chickenbro/messages",
                data=json.dumps(
                    {
                        "guestId": "guest-chickenbro-a",
                        "message": "奥法强韧大秘境怎么开始收集证据？",
                        "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(message_request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

            session_url = (
                f"http://127.0.0.1:{server.server_port}/api/chickenbro/sessions"
                f"?id={payload['session']['sessionId']}&guest=1&guestId=guest-chickenbro-a"
            )
            with urlopen(session_url, timeout=5) as response:
                session_payload = json.loads(response.read().decode("utf-8"))

            other_guest_request = Request(
                f"http://127.0.0.1:{server.server_port}/api/chickenbro/messages",
                data=json.dumps(
                    {"guestId": "guest-chickenbro-b", "message": "奥法正式服问题"},
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(other_guest_request, timeout=5):
                pass

            forbidden_job_url = (
                f"http://127.0.0.1:{server.server_port}/api/chickenbro/jobs"
                f"?id={payload['job']['jobId']}&guest=1&guestId=guest-chickenbro-b"
            )
            with self.assertRaises(HTTPError) as error:
                urlopen(forbidden_job_url, timeout=5)
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(payload["mode"], "chickenbro")
        self.assertEqual(payload["job"]["status"], "succeeded")
        self.assertEqual(len(session_payload["messages"]), 2)
        self.assertEqual(error.exception.code, 404)

    def test_saved_wcl_task_preserves_log_evidence_status(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-wcl-evidence",
            exchange_code=lambda code: {"openid": "openid-wcl-evidence"},
        )

        analysis = self.backend.analyze_and_store_simulator_task(
            {
                "mode": "wcl",
                "saveTask": True,
                "wclUrl": "https://www.warcraftlogs.com/reports/WCLTask123?fight=last",
                "question": "Check cooldown usage.",
            },
            access_token=login["accessToken"],
        )
        detail = self.backend.get_simulator_task(login["accessToken"], analysis["taskId"])

        self.assertEqual(analysis["logEvidence"]["sourceStatus"], "missing_credentials")
        self.assertEqual(detail["task"]["analysis"]["logEvidence"]["reportCode"], "WCLTask123")
        self.assertEqual(detail["task"]["analysis"]["logEvidence"]["fightId"], "last")

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
        self.assertEqual(
            self.backend.list_simulator_tasks("", allow_guest=True),
            {"user": None, "tasks": []},
        )

    def test_guest_simulator_read_does_not_create_user_for_unknown_guest_id(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            before = conn.execute("SELECT COUNT(*) FROM wechat_users").fetchone()[0]

        result = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="unknown-read")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            after = conn.execute("SELECT COUNT(*) FROM wechat_users").fetchone()[0]
        self.assertEqual(result, {"user": None, "tasks": []})
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
        self.backend.refresh_articles("scheduled")
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/news/refresh-runs/latest"
            with urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(response.status, 200)
            self.assertEqual(payload["refreshMode"], "scheduled")
            self.assertIn("translationIssueCount", payload)
            self.assertIn("translationIssues", payload)
        finally:
            server.shutdown()
            server.server_close()

    def test_http_news_refresh_requires_explicit_scheduled_mode(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_port}/api/news/refresh"
            for url in (base_url, f"{base_url}?mode=manual"):
                request = Request(url, data=b"", method="POST")
                with self.assertRaises(HTTPError) as context:
                    urlopen(request, timeout=5)
                self.assertEqual(context.exception.code, 400)
                payload = json.loads(context.exception.read().decode("utf-8"))
                self.assertEqual(payload["error"], "invalid_refresh_mode")
                self.assertEqual(payload["allowedModes"], ["scheduled"])

            with patch.object(self.backend, "refresh_articles", return_value={}), patch.object(
                self.backend,
                "build_home_payload",
                return_value={"heroNews": [], "highlights": []},
            ):
                request = Request(f"{base_url}?mode=scheduled", data=b"", method="POST")
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["heroNews"], [])
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

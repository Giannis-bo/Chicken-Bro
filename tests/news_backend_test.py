import gzip
import os
import json
import sqlite3
import tempfile
import threading
import time
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
    ("恶魔猎手", "噬灭", "demonhunter", "devourer"),
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

    def test_cache_data_store_reuses_only_authority_cache_for_same_database_url(self):
        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://example.invalid/wow-a",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ):
            first = self.backend.cache_data_store()
            second = self.backend.cache_data_store()

            self.assertIsNot(first, second)
            self.assertIs(
                first._gear_authority_context_cache,
                second._gear_authority_context_cache,
            )

            os.environ["WOW_DATABASE_URL"] = "postgresql://example.invalid/wow-b"
            other_database = self.backend.cache_data_store()

            self.assertIsNot(
                first._gear_authority_context_cache,
                other_database._gear_authority_context_cache,
            )

    def test_cache_data_store_does_not_retain_authority_cache_when_pg_runtime_is_disabled(self):
        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://example.invalid/wow-disabled",
                "WOW_DATABASE_RUNTIME": "",
            },
        ):
            self.assertIsNone(self.backend.cache_data_store())
            self.assertIsNone(self.backend._GEAR_AUTHORITY_CACHE)

    def test_blizzard_forum_source_uses_slug_url_without_stale_category_id(self):
        forum_source = self.backend.NEWS_SOURCES_BY_ID["blizzard-forums"]
        feed_source = next(source for source in self.backend.FEED_SOURCES if source["sourceId"] == "blizzard-forums")

        self.assertEqual(forum_source["sourceUrl"], "https://us.forums.blizzard.com/en/wow/c/in-development")
        self.assertEqual(feed_source["sourceUrl"], "https://us.forums.blizzard.com/en/wow/c/in-development")
        self.assertNotIn("/253", forum_source["sourceUrl"])
        self.assertNotIn("/253", feed_source["sourceUrl"])

    def test_websim_gear_builds_are_bounded_by_configured_worker_limit(self):
        active = 0
        max_active = 0
        lock = threading.Lock()
        start_event = threading.Event()
        results = []
        errors = []

        def build_payload():
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.05)
                return {"ok": True}
            finally:
                with lock:
                    active -= 1

        def worker():
            start_event.wait(timeout=1)
            try:
                results.append(self.backend.run_websim_gear_build(build_payload))
            except Exception as error:
                errors.append(error)

        with patch.dict(os.environ, {"WOW_WEB_GEAR_MAX_WORKERS": "2"}):
            self.backend.reset_websim_gear_build_limiter_for_tests()
            threads = [threading.Thread(target=worker) for _ in range(6)]
            for thread in threads:
                thread.start()
            start_event.set()
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 6)
        self.assertLessEqual(max_active, 2)

    def test_json_response_suppresses_broken_pipe_from_disconnected_client(self):
        class BrokenPipeHandler:
            def __init__(self):
                self.status = None
                self.headers = []
                self.wfile = self

            def send_response(self, status):
                self.status = status

            def send_header(self, name, value):
                self.headers.append((name, value))

            def end_headers(self):
                return None

            def write(self, body):
                raise BrokenPipeError("client disconnected")

        handler = BrokenPipeHandler()

        delivered = self.backend.json_response(handler, 200, {"ok": True})

        self.assertFalse(delivered)
        self.assertEqual(handler.status, 200)

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

    def simc_template_structured_gear_snapshot(self):
        gear_by_slot = {}
        for line in self.simc_template_full_gear_raw().splitlines():
            head, *parts = line.split(",")
            slot, _, name = head.partition("=")
            item = {"slot": slot, "simcSlot": slot, "name": name, "displayName": name, "simcReady": True}
            for part in parts:
                key, _, value = part.partition("=")
                item[key] = value
                if key == "id":
                    item["itemId"] = value
            gear_by_slot[slot] = item
        return {
            "schemaRevision": "websim-gear-enhancement-snapshot-v1",
            "gearBySlot": gear_by_slot,
            "enhancementBySlot": {},
        }

    def simc_template_stat_snapshot(self):
        return {
            "statStatus": "verified",
            "statSource": "simulationcraft_json",
            "primary": {"key": "intellect", "label": "智力", "value": "2,624", "rawValue": 2624},
            "secondary": [
                {"key": "crit", "label": "暴击", "value": "8,100", "convertedValue": "25%"},
                {"key": "haste", "label": "急速", "value": "3,497", "convertedValue": "10.8%"},
                {"key": "mastery", "label": "精通", "value": "12,440", "convertedValue": "78.7%"},
                {"key": "versatility", "label": "全能", "value": "300", "convertedValue": "1%"},
            ],
        }

    def simc_template_payload(
        self,
        *,
        talent_raw=None,
        gear_raw=None,
        talent_spec="arcane",
        gear_spec="arcane",
        scenario="single",
        analysis_type="baseline",
        race="",
    ):
        payload = {
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
                    "metadata": {"statSnapshot": self.simc_template_stat_snapshot()},
                },
            },
        }
        if race:
            payload["raceKey"] = race
        return payload

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

    def test_refresh_queue_only_processes_backlog_without_seed_articles(self):
        queued = self.official_discovered_article("official-queue-only")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.enqueue_discovered_articles(conn, [queued], self.backend.utc_now())
            conn.commit()

        with patch.object(self.backend, "ENABLE_COLLECTORS", False), patch.object(
            self.backend,
            "load_seed_articles",
            side_effect=AssertionError("queue-only refresh must not load seed articles"),
        ), patch.object(
            self.backend,
            "collect_feed_articles",
            side_effect=AssertionError("queue-only refresh must not collect new feed articles"),
        ), patch.object(
            self.backend,
            "localize_article",
            side_effect=lambda article, require_llm=False: self.translated_official_article(article),
        ):
            self.backend.refresh_articles(
                "scheduled",
                collector_enabled=False,
                seed_enabled=False,
                queue_enabled=True,
                process_limit_override=1,
            )

        latest = self.backend.latest_refresh_run_payload()
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_row = conn.execute(
                "SELECT status, last_error FROM news_discovery_queue WHERE id = ?",
                ("official-queue-only",),
            ).fetchone()

        self.assertEqual(latest["processedCount"], 1)
        self.assertEqual(latest["seedEnabled"], False)
        self.assertEqual(latest["queueEnabled"], True)
        self.assertEqual(queue_row, ("published", ""))

    def test_refresh_queue_only_blocks_retryable_after_retry_limit(self):
        queued = self.official_discovered_article("official-retry-limit")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.enqueue_discovered_articles(conn, [queued], self.backend.utc_now())
            conn.execute(
                """
                UPDATE news_discovery_queue
                SET status = 'retryable', attempts = 2, last_error = 'invalid_llm_translation'
                WHERE id = ?
                """,
                ("official-retry-limit",),
            )
            conn.commit()

        def invalid_translation(article, require_llm=False):
            return dict(
                article,
                contentStatus="blocked",
                blockedReason="invalid_llm_translation",
                verificationStatus="invalid_llm_translation",
                translationStatus="llm",
            )

        with patch.dict(os.environ, {"WOW_NEWS_RETRY_MAX_ATTEMPTS": "3"}), patch.object(
            self.backend,
            "load_seed_articles",
            side_effect=AssertionError("queue-only refresh must not load seed articles"),
        ), patch.object(self.backend, "localize_article", side_effect=invalid_translation):
            self.backend.refresh_articles(
                "scheduled",
                collector_enabled=False,
                seed_enabled=False,
                queue_enabled=True,
                process_limit_override=1,
            )

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_row = conn.execute(
                "SELECT status, attempts, last_error FROM news_discovery_queue WHERE id = ?",
                ("official-retry-limit",),
            ).fetchone()

        self.assertEqual(queue_row, ("blocked", 3, "retry_limit_exceeded:invalid_llm_translation"))

    def test_refresh_queue_only_dead_letters_retryable_already_over_retry_limit_without_llm(self):
        queued = self.official_discovered_article("official-dead-letter")

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.enqueue_discovered_articles(conn, [queued], self.backend.utc_now())
            conn.execute(
                """
                UPDATE news_discovery_queue
                SET status = 'retryable', attempts = 3, last_error = 'invalid_llm_translation'
                WHERE id = ?
                """,
                ("official-dead-letter",),
            )
            conn.commit()

        with patch.dict(os.environ, {"WOW_NEWS_RETRY_MAX_ATTEMPTS": "3"}), patch.object(
            self.backend,
            "load_seed_articles",
            side_effect=AssertionError("queue-only refresh must not load seed articles"),
        ), patch.object(
            self.backend,
            "localize_article",
            side_effect=AssertionError("retry limit exceeded rows must not call LLM again"),
        ):
            self.backend.refresh_articles(
                "scheduled",
                collector_enabled=False,
                seed_enabled=False,
                queue_enabled=True,
                process_limit_override=1,
            )

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            queue_row = conn.execute(
                "SELECT status, attempts, last_error FROM news_discovery_queue WHERE id = ?",
                ("official-dead-letter",),
            ).fetchone()

        self.assertEqual(queue_row, ("blocked", 3, "retry_limit_exceeded:invalid_llm_translation"))

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

    def test_news_home_and_list_prioritize_newest_published_articles(self):
        def article(article_id, importance, published_at):
            return {
                "id": article_id,
                "title": f"官方资讯 {article_id}",
                "summary": "暴雪发布了新的正式服与测试服资讯。",
                "channel": "正式服动态",
                "category": "正式服动态",
                "tags": ["content-update"],
                "importance": importance,
                "sourceName": "Blizzard News",
                "sourceUrl": f"https://worldofwarcraft.blizzard.com/news/{article_id}",
                "publishedAt": published_at,
                "sourceNote": "暴雪官方 World of Warcraft 新闻详情页。",
                "bodyZh": "中文正文：暴雪发布了完整资讯正文，覆盖版本变化、活动内容和玩家需要关注的后续时间点。",
                "bodyBlocksZh": [
                    {
                        "type": "paragraph",
                        "text": "中文正文：暴雪发布了完整资讯正文，覆盖版本变化、活动内容和玩家需要关注的后续时间点。",
                    }
                ],
                "originalTitle": f"Official News {article_id}",
                "tagItems": [{"id": "content-update", "label": "内容更新"}],
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
                article("old-important", 100, "2026-06-03"),
                article("new-published", 86, "2026-06-29"),
            ],
        ), patch.object(
            self.backend,
            "latest_refresh_state",
            return_value={"lastRefreshedAt": "2026-06-29T08:00:00+08:00", "refreshMode": "scheduled"},
        ):
            home = self.backend.build_home_payload()
            list_payload = self.backend.build_article_list_payload({"type": "metric", "key": "today"})

        self.assertEqual(home["heroNews"][0]["id"], "new-published")
        self.assertEqual(home["highlights"][0]["id"], "new-published")
        self.assertEqual(list_payload["articles"][0]["id"], "new-published")

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
        self.assertEqual([item["key"] for item in home["quickActions"]], ["talents", "gear", "simc", "tasks"])
        self.assertEqual(home["featuredSpecializations"], [])
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
            ["炸鸡队长"],
        )
        self.assertEqual([action["key"] for action in home["quickActions"]], ["chickenbro"])
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
        self.assertNotIn("llm", analysis)
        self.assertNotIn("codex", analysis)
        self.assertEqual(analysis["request"]["profileSource"], "template")
        self.assertIn("class_talents=1001:1", draft_profile)
        self.assertIn("spec_talents=2001:1", draft_profile)
        self.assertIn("hero_talents=3001:1", draft_profile)
        self.assertNotIn("talents=websim:", draft_profile)
        self.assertIn("head=template_head,id=250001,ilevel=289,bonus_id=13534/6652", draft_profile)
        self.assertIn("finger1=template_finger1,id=250011,ilevel=289,bonus_id=13534/6652,gem_id=213743,enchant_id=7334", draft_profile)
        self.assertIn("main_hand=template_main_hand,id=250015,ilevel=289,bonus_id=13534/6652,crafted_stats=32/49", draft_profile)
        self.assertEqual(len(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]), 16)

    def test_generated_death_knight_template_profile_defaults_verified_runeforge(self):
        from server import simulator_payload

        frost_profile = simulator_payload.build_generated_simc_profile(
            simulator_payload.spec_info_from_keys("deathknight", "frost"),
            None,
            {"details": {"talents": {"importCode": "DK_FROST_CODE"}}},
            [
                {
                    "slot": "main_hand",
                    "name": "bellamys_final_judgement",
                    "id": "249277",
                    "ilevel": "289",
                    "bonus_id": "13654",
                }
            ],
        )
        unholy_profile = simulator_payload.build_generated_simc_profile(
            simulator_payload.spec_info_from_keys("deathknight", "unholy"),
            None,
            {"details": {"talents": {"importCode": "DK_UNHOLY_CODE"}}},
            [
                {
                    "slot": "main_hand",
                    "name": "bellamys_final_judgement",
                    "id": "249277",
                    "ilevel": "289",
                    "bonus_id": "13654",
                }
            ],
        )

        self.assertIn("main_hand=bellamys_final_judgement,id=249277,ilevel=289,bonus_id=13654,enchant_id=3368", frost_profile)
        self.assertIn("main_hand=bellamys_final_judgement,id=249277,ilevel=289,bonus_id=13654,enchant_id=6245", unholy_profile)

    def test_simcraft_template_confirm_uses_selected_race(self):
        self.seed_simc_template_websim_nodes()

        analysis = self.backend.analyze_and_store_simulator_task(
            self.simc_template_payload(race="void_elf")
        )
        draft_profile = analysis["agent"]["draftProfile"]

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertEqual(analysis["request"]["raceKey"], "void_elf")
        self.assertEqual(analysis["request"]["buildContext"]["raceKey"], "void_elf")
        self.assertIn("race=void_elf", draft_profile)
        self.assertNotIn("race=troll", draft_profile)

    def test_simcraft_template_confirm_serializes_structured_gear_enhancement_snapshot(self):
        self.seed_simc_template_websim_nodes()
        from server import websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.ensure_websim_tables(conn)
            websim_payload.save_websim_item_metadata(
                conn,
                "213743",
                {
                    "id": 213743,
                    "name": "Template Gem",
                    "item_class": {"id": 3, "name": "Gem"},
                    "item_subclass": {"id": 8, "name": "Versatility"},
                    "quality": {"name": "Epic"},
                },
                {"assets": [{"value": "https://render.example/gem-213743.jpg"}]},
                fallback_name="Template Gem",
                english_payload={"name": "Template Gem"},
                locale="en_US",
            )
            websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "template-gem-rank-two",
                    "type": "socket",
                    "name": "Rank Two Gem",
                    "slots": ["finger1"],
                    "simcOptions": {"gem_id": "213743"},
                    "payload": {
                        "qualityRank": 2,
                        "source": "server_owned_seed",
                        "gemItemId": "213743",
                        "metadataStatus": "verified",
                        "iconUrl": "https://render.example/gem-213743.jpg",
                        "displayLabel": "+32主属性",
                        "displayKind": "stat",
                        "displayStatus": "verified",
                        "statSummary": "+32主属性",
                        "statDisplayStatus": "verified_tooltip_override",
                        "evidenceSource": "wowhead_live_tooltip",
                    },
                },
            )
            websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "template-enchant-rank-two",
                    "type": "enchant",
                    "name": "Rank Two Enchant",
                    "slots": ["finger1"],
                    "simcOptions": {"enchant_id": "7334"},
                    "payload": {
                        "qualityRank": 2,
                        "source": "server_owned_seed",
                        "displayName": "朗多雷之锐",
                        "displayStatus": "verified",
                        "evidenceSource": "simulationcraft+wago_db2",
                    },
                },
            )
            websim_payload.upsert_gear_mod_option(
                conn,
                {
                    "id": "template-embellishment-rank-two",
                    "type": "embellishment",
                    "name": "Blue Silken Lining",
                    "slots": ["wrist"],
                    "simcOptions": {"embellishment": "blue_silken_lining"},
                    "payload": {
                        "qualityRank": 2,
                        "source": "simulationcraft+wago_db2",
                        "simcKey": "blue_silken_lining",
                        "bonusId": "123456",
                        "effectId": "98765",
                        "spellId": "456789",
                        "db2CategoryId": "2001",
                        "db2ReagentItemId": "260111",
                        "db2BonusTreeId": "3001",
                    },
                },
            )
            conn.commit()
        gear_by_slot = {}
        for line in self.simc_template_full_gear_raw().splitlines():
            head, *parts = line.split(",")
            slot, _, name = head.partition("=")
            item = {"slot": slot, "simcSlot": slot, "name": name, "displayName": name, "simcReady": True}
            for part in parts:
                key, _, value = part.partition("=")
                if key in {"gem_id", "enchant_id"}:
                    continue
                item[key] = value
                if key == "id":
                    item["itemId"] = value
            if slot == "finger1":
                item["modCapabilities"] = {"hasSocket": True, "canEnchant": True, "canEmbellish": False}
            if slot == "wrist":
                item["modCapabilities"] = {"hasSocket": False, "canEnchant": True, "canEmbellish": True}
                item["sourceType"] = "crafted"
                item["crafted_stats"] = "32/49"
            gear_by_slot[slot] = item
        gear_raw = json.dumps(
            {
                "schemaRevision": "websim-gear-enhancement-snapshot-v1",
                "gearBySlot": gear_by_slot,
                "enhancementBySlot": {
                    "finger1": {
                        "gem_id": "213743",
                        "enchant_id": "7334",
                    },
                    "wrist": {
                        "embellishment": "blue_silken_lining",
                    },
                },
            },
            ensure_ascii=False,
        )

        analysis = self.backend.analyze_and_store_simulator_task(self.simc_template_payload(gear_raw=gear_raw))
        draft_profile = analysis["agent"]["draftProfile"]

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertIn("finger1=template_finger1,id=250011,ilevel=289,bonus_id=13534/6652,gem_id=213743,enchant_id=7334", draft_profile)
        self.assertIn(
            "wrist=template_wrist,id=250006,ilevel=289,bonus_id=13534/6652,crafted_stats=32/49,embellishment=blue_silken_lining",
            draft_profile,
        )
        self.assertEqual(len(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]), 16)

    def test_simcraft_template_structured_snapshot_allows_two_handed_offhand_exemption(self):
        self.seed_simc_template_websim_nodes()
        gear_by_slot = {}
        for line in self.simc_template_full_gear_raw().splitlines():
            head, *parts = line.split(",")
            slot, _, name = head.partition("=")
            if slot == "off_hand":
                continue
            item = {"slot": slot, "simcSlot": slot, "name": name, "displayName": name, "simcReady": True}
            for part in parts:
                key, _, value = part.partition("=")
                item[key] = value
                if key == "id":
                    item["itemId"] = value
            gear_by_slot[slot] = item
        gear_raw = json.dumps(
            {
                "schemaRevision": "websim-gear-enhancement-snapshot-v1",
                "gearBySlot": gear_by_slot,
                "enhancementBySlot": {},
            },
            ensure_ascii=False,
        )

        analysis = self.backend.analyze_and_store_simulator_task(self.simc_template_payload(gear_raw=gear_raw))

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertTrue(analysis["agent"]["canSubmitTask"])
        self.assertNotIn("missing gear slots: off_hand", analysis["simulation"].get("error", ""))
        self.assertEqual(len(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]), 15)

    def test_simcraft_template_structured_snapshot_keeps_legal_partial_items_when_slot_is_illegal(self):
        snapshot = self.simc_template_structured_gear_snapshot()
        snapshot["gearBySlot"]["head"].update({
            "name": "cloth_hood",
            "displayName": "Cloth Hood",
            "armorType": "Cloth",
        })
        payload = self.simc_template_payload(
            talent_raw="C4DAshamanexternal",
            gear_raw=json.dumps(snapshot, ensure_ascii=False),
            talent_spec="elemental",
            gear_spec="elemental",
            race="tauren",
        )
        for template_type in ("talent", "gear"):
            payload["templateContext"][template_type].update({
                "classKey": "shaman",
                "className": "Shaman",
                "specKey": "elemental",
                "specName": "Elemental",
                "heroKey": "",
                "heroLabel": "",
            })

        analysis = self.backend.analyze_and_store_simulator_task(payload)
        simc_items = analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]

        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertIn("missing gear slots: head", analysis["simulation"]["error"])
        self.assertIn(
            "head gear incompatible with shaman/elemental armor rule: Cloth",
            analysis["simulation"]["error"],
        )
        self.assertEqual(len(simc_items), 15)
        self.assertNotIn("head", [item.get("slot") for item in simc_items])
        self.assertNotIn("cloth_hood", analysis["agent"].get("draftProfile", ""))

    def test_simcraft_template_confirm_degrades_in_pg_only_runtime_without_sqlite(self):
        snapshot = self.simc_template_structured_gear_snapshot()
        snapshot["gearBySlot"]["head"].update({
            "name": "cloth_hood",
            "displayName": "Cloth Hood",
            "armorType": "Cloth",
        })
        payload = self.simc_template_payload(
            talent_raw="C4DAshamanexternal",
            gear_raw=json.dumps(snapshot, ensure_ascii=False),
            talent_spec="elemental",
            gear_spec="elemental",
            race="tauren",
        )
        for template_type in ("talent", "gear"):
            payload["templateContext"][template_type].update({
                "classKey": "shaman",
                "className": "Shaman",
                "specKey": "elemental",
                "specName": "Elemental",
                "heroKey": "",
                "heroLabel": "",
            })
        original_postgres_only = self.backend.postgres_only_runtime_enabled
        original_db_connection = self.backend.db_connection

        def sqlite_disabled_connection():
            raise RuntimeError("SQLite runtime is disabled; use PostgreSQL runtime stores or explicit migration tooling")

        self.backend.postgres_only_runtime_enabled = lambda: True
        self.backend.db_connection = sqlite_disabled_connection
        try:
            analysis = self.backend.analyze_and_store_simulator_task(payload)
        finally:
            self.backend.postgres_only_runtime_enabled = original_postgres_only
            self.backend.db_connection = original_db_connection

        simc_items = analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]
        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertEqual(len(simc_items), 15)
        self.assertIn("head gear incompatible with shaman/elemental armor rule: Cloth", analysis["simulation"]["error"])

    def test_simcraft_template_confirm_accepts_official_talent_import_code(self):
        analysis = self.backend.analyze_and_store_simulator_task(
            self.simc_template_payload(talent_raw="talents=CAE_OFFICIAL_IMPORT_CODE")
        )

        draft_profile = analysis["agent"]["draftProfile"]
        self.assertEqual(analysis["mode"], "simcraft_template")
        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertIn("talents=CAE_OFFICIAL_IMPORT_CODE", draft_profile)
        self.assertNotIn("class_talents=", draft_profile)

    def test_simcraft_template_confirm_accepts_complete_gear_with_warnings(self):
        payload = self.simc_template_payload(talent_raw="talents=CAE_OFFICIAL_IMPORT_CODE")
        payload["templateContext"]["gear"]["status"] = "complete_with_warnings"
        payload["templateContext"]["gear"]["statusLabel"] = "完整配置 · 来源待补"

        analysis = self.backend.analyze_and_store_simulator_task(payload)

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertTrue(analysis["agent"]["canSubmitTask"])
        self.assertNotIn("gear template must be complete", analysis["simulation"].get("error", ""))
        self.assertEqual(len(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]), 16)

    def test_simcraft_template_confirm_uses_metadata_gear_snapshot_fallback(self):
        self.seed_simc_template_websim_nodes()
        payload = self.simc_template_payload(gear_raw="saved gear snapshot lives in metadata")
        payload["templateContext"]["gear"]["metadata"] = {
            "gearSnapshot": self.simc_template_structured_gear_snapshot(),
            "statSnapshot": self.simc_template_stat_snapshot(),
        }

        analysis = self.backend.analyze_and_store_simulator_task(payload)

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertEqual(len(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"]), 16)
        self.assertIn("head=template_head,id=250001", analysis["agent"]["draftProfile"])

    def test_simc_profile_validation_rejects_talent_line_entries_without_rank(self):
        from server import simulator_payload

        validation = simulator_payload.validate_agent_simc_profile(
            "\n".join(
                [
                    'shaman="Generated_Elemental_Shaman"',
                    "level=90",
                    "race=tauren",
                    "role=spell",
                    "spec=elemental",
                    "class_talents=127855:",
                    "spec_talents=127856:1",
                ]
            )
        )

        self.assertFalse(validation["passed"])
        self.assertIn("invalid class_talents entry: 127855:", validation["errors"])

    def test_generated_profile_preserves_long_build_context_talent_lines(self):
        from server import simulator_payload

        class_line = (
            "class_talents="
            "127861:1/127856:1/127871:1/127880:1/127853:1/127877:1/"
            "127864:1/127893:1/127890:1/127863:1/127888:1/127855:2/"
            "127892:1/127851:1/136585:1/127910:1/127884:1/127909:1"
        )
        context = simulator_payload.normalize_build_context({
            "specId": "shaman-elemental",
            "className": "萨满祭司",
            "specName": "元素",
            "details": {
                "talents": {
                    "simcLines": [class_line],
                    "encodingStatus": "encoded",
                },
            },
        })

        profile = simulator_payload.build_generated_simc_profile(
            simulator_payload.spec_info_from_keys("shaman", "elemental"),
            None,
            context,
            [],
        )

        self.assertEqual(context["details"]["talents"]["simcLines"], [class_line])
        self.assertIn("127855:2", profile)
        self.assertNotIn("127855:\n", profile)

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
        self.assertEqual(analysis["simcReport"]["schemaRevision"], "simc-report-v2")
        self.assertEqual(analysis["simcReport"]["state"], "ready")
        self.assertEqual(analysis["simcReport"]["profileSource"], "template")
        self.assertEqual(analysis["simcReport"]["scenario"]["fightStyle"], "Patchwerk")
        self.assertEqual(analysis["simcReport"]["scenario"]["targets"], 1)
        self.assertFalse(analysis["simcReport"]["result"]["ran"])
        self.assertEqual(analysis["simcReport"]["build"]["talentTemplate"]["id"], "talent-template-1")
        self.assertEqual(analysis["simcReport"]["build"]["gearTemplate"]["id"], "gear-template-1")
        self.assertIn("optimal_raid=0", analysis["request"]["profile"])
        self.assertIn("override.arcane_intellect=1", analysis["request"]["profile"])
        self.assertNotIn("override.skyfury=1", analysis["request"]["profile"])
        self.assertEqual(analysis["simcReport"]["preparation"]["evidenceState"], "verified")
        self.assertIn("Arcane Intellect", analysis["simcReport"]["preparation"]["summary"])
        self.assertNotIn("llm", analysis)
        self.assertNotIn("codex", analysis)
        self.assertNotIn("allowedNumbers", analysis)

    def test_simcraft_template_profile_only_applies_self_class_raid_buff(self):
        request_payload = self.simc_template_payload(
            talent_raw="C4DAshamanexternal",
            talent_spec="elemental",
            gear_spec="elemental",
            race="tauren",
        )
        for template_type in ("talent", "gear"):
            request_payload["templateContext"][template_type].update({
                "classKey": "shaman",
                "className": "Shaman",
                "specKey": "elemental",
                "specName": "Elemental",
                "heroKey": "",
                "heroLabel": "",
            })

        analysis = self.backend.analyze_and_store_simulator_task(request_payload)
        profile = analysis["request"]["profile"]
        preparation = analysis["simcReport"]["preparation"]

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertIn("optimal_raid=0", profile)
        self.assertIn("override.skyfury=1", profile)
        self.assertNotIn("override.arcane_intellect=1", profile)
        self.assertNotIn("override.power_word_fortitude=1", profile)
        self.assertEqual(preparation["classKey"], "shaman")
        self.assertEqual(preparation["specKey"], "elemental")
        self.assertEqual(preparation["evidenceState"], "verified")
        self.assertIn("Skyfury", preparation["summary"])

    def test_simcraft_template_temporary_buffs_are_reported_but_not_serialized_until_verified(self):
        request_payload = self.simc_template_payload()
        request_payload["temporaryBuffs"] = {"bloodlust": True, "combatPotion": True}

        analysis = self.backend.analyze_and_store_simulator_task(request_payload)
        profile = analysis["request"]["profile"]
        preparation = analysis["simcReport"]["preparation"]
        temporary = next(item for item in preparation["items"] if item["key"] == "temporary_combat_buffs")

        self.assertEqual(preparation["evidenceState"], "partial")
        self.assertIn("selected temporary combat buffs", preparation["summary"])
        self.assertIn("Bloodlust", preparation["summary"])
        self.assertEqual(temporary["state"], "enabled")
        self.assertIn("Bloodlust", temporary["summary"])
        self.assertIn("Combat potion", temporary["summary"])
        self.assertNotIn("bloodlust=1", profile)
        self.assertNotIn("potion=", profile)

    def test_simcraft_template_report_carries_compact_stat_snapshot(self):
        self.seed_simc_template_websim_nodes()
        payload = self.simc_template_payload(scenario="mythic_plus")
        payload["templateContext"]["gear"]["metadata"] = {
            "statSnapshot": self.simc_template_stat_snapshot(),
        }

        analysis = self.backend.analyze_and_store_simulator_task(payload)

        snapshot = analysis["simcReport"]["build"]["statSnapshot"]
        self.assertEqual(snapshot["statStatus"], "verified")
        self.assertEqual(snapshot["primary"]["label"], "智力")
        self.assertEqual(snapshot["secondary"][0]["key"], "crit")
        self.assertEqual(snapshot["secondary"][0]["convertedValue"], "25%")
        self.assertEqual(analysis["simcReport"]["scenario"]["targets"], 5)

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
        self.assertEqual(analysis["simcReport"]["state"], "blocked")
        self.assertIn("template class/spec mismatch", analysis["simcReport"]["messages"]["blockers"])

    def test_simcraft_template_blocks_incomplete_gear_template(self):
        gear_raw = "\n".join(self.simc_template_full_gear_raw().splitlines()[:15])
        analysis = self.backend.analyze_and_store_simulator_task(
            self.simc_template_payload(gear_raw=gear_raw)
        )

        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertIn("missing gear slots: off_hand", analysis["simulation"]["error"])
        self.assertEqual(analysis["request"]["buildContext"]["details"]["gear"]["simcItems"], [])
        self.assertEqual(analysis["simcReport"]["state"], "blocked")
        self.assertIn("missing gear slots: off_hand", analysis["simcReport"]["summary"])

    def test_simcraft_template_blocks_missing_verified_stat_snapshot(self):
        self.seed_simc_template_websim_nodes()
        payload = self.simc_template_payload()
        payload["templateContext"]["gear"].pop("metadata", None)

        analysis = self.backend.analyze_and_store_simulator_task(payload)

        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertIn("gear stat snapshot is not verified", analysis["agent"]["validation"]["errors"])
        self.assertIn("gear stat snapshot is not verified", analysis["simcReport"]["messages"]["blockers"])
        self.assertEqual(analysis["simcReport"]["state"], "blocked")

    def test_simcraft_template_blocks_known_unholy_rider_simc_crash_even_with_verified_snapshot(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.ensure_websim_tables(conn)
            self.insert_websim_talent(
                conn,
                "simc-class-1001-deathknight-unholy",
                "class",
                1001,
                1,
                1,
                "Class Talent",
                class_key="deathknight",
                spec_key="unholy",
                class_id=6,
                spec_id=252,
            )
            self.insert_websim_talent(
                conn,
                "simc-spec-2001-deathknight-unholy",
                "spec",
                2001,
                1,
                2,
                "Spec Talent",
                class_key="deathknight",
                spec_key="unholy",
                class_id=6,
                spec_id=252,
            )
            self.insert_websim_talent(
                conn,
                "simc-hero-3001-deathknight-unholy-rider_of_the_apocalypse",
                "hero",
                3001,
                2,
                1,
                "Hero Talent",
                class_key="deathknight",
                spec_key="unholy",
                hero_key="rider_of_the_apocalypse",
                class_id=6,
                spec_id=252,
            )
            conn.commit()
        payload = self.simc_template_payload()
        talent_raw = (
            "websim:deathknight:unholy:rider_of_the_apocalypse:"
            "simc-class-1001-deathknight-unholy:1,"
            "simc-spec-2001-deathknight-unholy:1,"
            "simc-hero-3001-deathknight-unholy-rider_of_the_apocalypse:1"
        )
        payload["templateContext"]["talent"].update({
            "title": "死亡骑士-邪恶-天启骑士",
            "rawString": talent_raw,
            "classKey": "deathknight",
            "className": "死亡骑士",
            "specKey": "unholy",
            "specName": "邪恶",
            "heroKey": "rider_of_the_apocalypse",
        })
        payload["templateContext"]["gear"].update({
            "title": "死亡骑士-邪恶-单体",
            "classKey": "deathknight",
            "className": "死亡骑士",
            "specKey": "unholy",
            "specName": "邪恶",
            "metadata": {"statSnapshot": self.simc_template_stat_snapshot()},
        })

        analysis = self.backend.analyze_and_store_simulator_task(payload)

        self.assertEqual(analysis["agent"]["status"], "template_blocked")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertTrue(any("邪恶死亡骑士" in error and "天启骑士" in error for error in analysis["agent"]["validation"]["errors"]))
        self.assertFalse(any("gear stat snapshot" in error for error in analysis["agent"]["validation"]["errors"]))
        self.assertEqual(analysis["simcReport"]["state"], "blocked")
        self.assertTrue(any("邪恶死亡骑士" in blocker for blocker in analysis["simcReport"]["messages"]["blockers"]))

        payload["templateContext"]["gear"].pop("metadata", None)
        missing_snapshot_analysis = self.backend.analyze_and_store_simulator_task(payload)
        missing_snapshot_errors = missing_snapshot_analysis["agent"]["validation"]["errors"]
        self.assertTrue(any("邪恶死亡骑士" in error and "天启骑士" in error for error in missing_snapshot_errors))
        self.assertFalse(any("gear stat snapshot" in error for error in missing_snapshot_errors))

    def test_simcraft_template_final_submit_queues_task_without_simc_llm_or_codex(self):
        self.seed_simc_template_websim_nodes()
        from server import simulator_payload

        original_run_simcraft = simulator_payload.run_simcraft
        original_call_llm = simulator_payload.call_llm
        original_call_codex_worker = simulator_payload.call_codex_worker
        simulator_payload.run_simcraft = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("final submit must not run SimC synchronously")
        )
        simulator_payload.call_llm = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("simcraft_template submit must not call LLM")
        )
        simulator_payload.call_codex_worker = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("simcraft_template submit must not call Codex Worker")
        )
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload(scenario="mythic_plus", analysis_type="stat_weights", race="troll")
        request_payload["raceName"] = "巨魔"
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device"})
        try:
            analysis = self.backend.analyze_and_store_simulator_task(request_payload)
        finally:
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)
            simulator_payload.run_simcraft = original_run_simcraft
            simulator_payload.call_llm = original_call_llm
            simulator_payload.call_codex_worker = original_call_codex_worker

        self.assertFalse(analysis["simulation"]["ran"])
        self.assertEqual(analysis["status"], "queued")
        self.assertEqual(analysis["agent"]["status"], "simc_queued")
        self.assertFalse(analysis["agent"]["canSubmitTask"])
        self.assertTrue(analysis["taskId"])
        self.assertEqual(analysis["runPolicy"]["policy"], "queued")
        self.assertEqual(analysis["evidenceState"]["phase"], "queued")
        self.assertEqual(analysis["simcReport"]["state"], "queued")
        self.assertEqual(analysis["simcReport"]["scenario"]["fightStyle"], "DungeonSlice")
        self.assertEqual(analysis["simcReport"]["scenario"]["targets"], 5)
        self.assertEqual(analysis["simcReport"]["build"]["raceKey"], "troll")
        self.assertEqual(analysis["simcReport"]["build"]["raceName"], "巨魔")
        self.assertFalse(analysis["simcReport"]["result"]["ran"])
        self.assertIn("fight_style=DungeonSlice", analysis["request"]["profile"])
        self.assertIn("desired_targets=5", analysis["request"]["profile"])
        self.assertIn("calculate_scale_factors=1", analysis["request"]["profile"])
        self.assertEqual(analysis["request"]["templateContext"]["talent"]["id"], "talent-template-1")
        self.assertNotIn("llm", analysis)
        self.assertNotIn("codex", analysis)
        self.assertNotIn("allowedNumbers", analysis)
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            row = conn.execute(
                """
                SELECT status, request_json, analysis_json, summary_json,
                       queued_at, started_at, finished_at, attempt, locked_by,
                       heartbeat_at, cancel_requested, last_error
                FROM simulator_tasks
                WHERE id = ?
                """,
                (analysis["taskId"],),
            ).fetchone()
        self.assertEqual(row[0], "queued")
        self.assertTrue(row[4])
        self.assertEqual(row[5], "")
        self.assertEqual(row[6], "")
        self.assertEqual(row[7], 0)
        self.assertEqual(row[8], "")
        self.assertEqual(row[9], "")
        self.assertEqual(row[10], 0)
        self.assertEqual(row[11], "")
        stored_request = json.loads(row[1])
        stored_analysis = json.loads(row[2])
        stored_summary = json.loads(row[3])
        self.assertEqual(stored_request["simcTaskFingerprint"], analysis["request"]["simcTaskFingerprint"])
        self.assertEqual(stored_analysis["agent"]["status"], "simc_queued")
        self.assertEqual(stored_summary["state"], "queued")
        self.assertEqual(stored_summary["build"]["raceName"], "巨魔")
        self.assertEqual(stored_summary["build"]["className"], "法师")
        self.assertEqual(stored_summary["build"]["specName"], "奥术")
        self.assertEqual(stored_summary["build"]["heroKey"], "spellslinger")
        self.assertEqual(stored_summary["scenario"]["key"], "mythic_plus")
        self.assertEqual(stored_summary["timing"]["finishedAt"], "")
        tasks = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="template-device")
        task_summary = tasks["tasks"][0]["simcReportSummary"]
        self.assertEqual(task_summary["state"], "queued")
        self.assertEqual(task_summary["scenario"]["key"], "mythic_plus")
        self.assertEqual(task_summary["build"]["raceName"], "巨魔")
        self.assertEqual(task_summary["build"]["className"], "法师")
        self.assertEqual(task_summary["build"]["specName"], "奥术")
        self.assertEqual(task_summary["build"]["heroKey"], "spellslinger")
        self.assertEqual(task_summary["timing"]["finishedAt"], "")

    def test_simcraft_template_aoe5_scenario_uses_patchwerk_five_targets(self):
        self.seed_simc_template_websim_nodes()
        request_payload = self.simc_template_payload(scenario="aoe_5", analysis_type="baseline", race="troll")
        request_payload.update({"confirmOnly": True, "saveTask": False})

        analysis = self.backend.analyze_and_store_simulator_task(request_payload)

        self.assertEqual(analysis["agent"]["status"], "template_ready")
        self.assertEqual(analysis["simcReport"]["scenario"]["key"], "aoe_5")
        self.assertEqual(analysis["simcReport"]["scenario"]["fightStyle"], "Patchwerk")
        self.assertEqual(analysis["simcReport"]["scenario"]["targets"], 5)
        self.assertIn("fight_style=Patchwerk", analysis["request"]["profile"])
        self.assertIn("desired_targets=5", analysis["request"]["profile"])
        self.assertIn("max_time=300", analysis["request"]["profile"])
        self.assertNotIn("fight_style=DungeonSlice", analysis["request"]["profile"])
        self.assertFalse(analysis["request"].get("mythicPlusReference"))

    def test_simcraft_template_task_list_prefers_stored_summary_after_snapshot_changes(self):
        self.seed_simc_template_websim_nodes()
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload(scenario="mythic_plus", race="troll")
        request_payload["raceName"] = "巨魔"
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-summary"})
        try:
            analysis = self.backend.analyze_and_store_simulator_task(request_payload)
        finally:
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            row = conn.execute(
                "SELECT request_json, analysis_json FROM simulator_tasks WHERE id = ?",
                (analysis["taskId"],),
            ).fetchone()
            stored_request = json.loads(row[0])
            stored_analysis = json.loads(row[1])
            stored_request["templateContext"]["talent"]["specName"] = "changed-after-submit"
            stored_request["templateContext"]["gear"]["specName"] = "changed-after-submit"
            stored_analysis["simcReport"]["build"]["specName"] = "changed-after-submit"
            conn.execute(
                "UPDATE simulator_tasks SET request_json = ?, analysis_json = ? WHERE id = ?",
                (
                    json.dumps(stored_request, ensure_ascii=False),
                    json.dumps(stored_analysis, ensure_ascii=False),
                    analysis["taskId"],
                ),
            )
            conn.commit()

        tasks = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="template-device-summary")
        task_summary = tasks["tasks"][0]["simcReportSummary"]
        self.assertEqual(task_summary["build"]["specName"], "奥术")
        self.assertNotEqual(task_summary["build"]["specName"], "changed-after-submit")

    def test_simcraft_template_task_detail_uses_submit_time_template_snapshot(self):
        self.seed_simc_template_websim_nodes()
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload()
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-detail"})
        try:
            analysis = self.backend.analyze_and_store_simulator_task(request_payload)
        finally:
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)

        changed_at = "2026-06-27T10:00:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            user_id = conn.execute(
                "SELECT user_id FROM simulator_tasks WHERE id = ?",
                (analysis["taskId"],),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT OR REPLACE INTO user_build_templates (
                    id, user_id, client_id, template_type, title, class_key, class_name,
                    spec_key, spec_name, hero_key, hero_label, scenario_key, scenario_title,
                    raw_string, simc_lines_json, status, status_label, source, metadata_json,
                    schema_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "talent-template-1",
                    user_id,
                    "talent-template-1",
                    "talent",
                    "changed-after-submit",
                    "mage",
                    "法师",
                    "fire",
                    "changed-after-submit",
                    "flamestrike",
                    "changed-after-submit",
                    "",
                    "",
                    "websim:changed-after-submit",
                    "[]",
                    "saved",
                    "Saved",
                    "test",
                    "{}",
                    1,
                    changed_at,
                    changed_at,
                ),
            )
            conn.commit()

        detail = self.backend.get_simulator_task(
            "",
            analysis["taskId"],
            allow_guest=True,
            guest_id="template-device-detail",
        )
        talent_snapshot = detail["task"]["request"]["templateContext"]["talent"]
        self.assertEqual(talent_snapshot["id"], "talent-template-1")
        self.assertEqual(talent_snapshot["title"], "奥法 WebSim 天赋")
        self.assertEqual(talent_snapshot["specName"], "奥术")
        self.assertNotEqual(talent_snapshot["title"], "changed-after-submit")

    def test_simcraft_template_final_submit_reuses_active_task_lock(self):
        self.seed_simc_template_websim_nodes()
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload()
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device"})
        try:
            first = self.backend.analyze_and_store_simulator_task(request_payload)
            second = self.backend.analyze_and_store_simulator_task(request_payload)
        finally:
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)

        self.assertEqual(second["taskId"], first["taskId"])
        self.assertEqual(second["status"], "queued")
        self.assertTrue(second["taskLock"]["active"])
        self.assertEqual(second["taskLock"]["reason"], "active_simc_task")
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            count = conn.execute("SELECT COUNT(*) FROM simulator_tasks").fetchone()[0]
        self.assertEqual(count, 1)

    def test_simcraft_template_final_submit_blocks_third_active_task_for_same_player(self):
        self.seed_simc_template_websim_nodes()
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        try:
            first_payload = self.simc_template_payload(scenario="single")
            first_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-limit"})
            second_payload = self.simc_template_payload(scenario="aoe_5")
            second_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-limit"})
            third_payload = self.simc_template_payload(scenario="mythic_plus")
            third_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-limit"})

            first = self.backend.analyze_and_store_simulator_task(first_payload)
            second = self.backend.analyze_and_store_simulator_task(second_payload)
            third = self.backend.analyze_and_store_simulator_task(third_payload)
        finally:
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)

        self.assertEqual(first["status"], "queued")
        self.assertEqual(second["status"], "queued")
        self.assertNotEqual(second["taskId"], first["taskId"])
        self.assertEqual(third["status"], "blocked")
        self.assertFalse(third["agent"]["canSubmitTask"])
        self.assertEqual(third["taskLock"]["reason"], "active_simc_task_limit")
        self.assertEqual(third["taskLock"]["activeCount"], 2)
        self.assertEqual(third["taskLock"]["limit"], 2)
        self.assertIn("2", third["simulation"]["error"])
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            rows = conn.execute(
                "SELECT status FROM simulator_tasks WHERE user_id = ? ORDER BY created_at",
                (first["owner"]["id"],),
            ).fetchall()
        self.assertEqual([row[0] for row in rows], ["queued", "queued"])

    def test_simcraft_template_task_runner_completes_queued_task(self):
        self.seed_simc_template_websim_nodes()
        from server import simulator_payload

        original_call_llm = simulator_payload.call_llm
        original_call_codex_worker = simulator_payload.call_codex_worker
        simulator_payload.call_llm = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("simcraft_template runner must not call LLM")
        )
        simulator_payload.call_codex_worker = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("simcraft_template runner must not call Codex Worker")
        )
        simc_bin = Path(self.tmp.name) / "fake-simc-template-runner"
        captured_profile = Path(self.tmp.name) / "captured-template-runner-profile.txt"
        simc_bin.write_text(
            "#!/bin/sh\n"
            f"cat > {captured_profile}\n"
            "printf 'Player: TemplateArcaneMage\\n  DPS=654321 DPS-Error=0/0.00%%\\nScale Factors:\\nintellect=9.1 haste=6.4\\n'\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload()
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device"})
        try:
            queued = self.backend.analyze_and_store_simulator_task(request_payload)
            completed = self.backend.run_simcraft_template_task(queued["taskId"])
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)
            simulator_payload.call_llm = original_call_llm
            simulator_payload.call_codex_worker = original_call_codex_worker

        executed_profile = captured_profile.read_text(encoding="utf-8")
        self.assertEqual(completed["status"], "completed")
        self.assertTrue(completed["simulation"]["ran"])
        self.assertEqual(completed["simulation"]["metrics"]["dps"], "654321")
        self.assertEqual(completed["agent"]["status"], "simc_completed")
        self.assertEqual(completed["simcReport"]["state"], "completed")
        self.assertEqual(completed["simcReport"]["result"]["dps"], "654321")
        self.assertEqual(completed["simcReport"]["result"]["dpsDisplay"], "654321 DPS")
        self.assertTrue(completed["simcReport"]["timing"]["startedAt"])
        self.assertTrue(completed["simcReport"]["timing"]["finishedAt"])
        self.assertIsInstance(completed["simcReport"]["timing"]["elapsedMs"], int)
        self.assertIn("fight_style=Patchwerk", executed_profile)
        detail = self.backend.get_simulator_task("", queued["taskId"], allow_guest=True, guest_id="template-device")
        self.assertEqual(detail["task"]["status"], "completed")
        self.assertEqual(detail["task"]["analysis"]["simulation"]["metrics"]["dps"], "654321")
        self.assertEqual(detail["task"]["analysis"]["simcReport"]["result"]["dps"], "654321")
        self.assertNotIn("profile", detail["task"]["analysis"]["request"])
        self.assertNotIn("draftProfile", detail["task"]["analysis"]["agent"])
        self.assertEqual(detail["task"]["analysis"]["simulation"]["summary"], "")
        self.assertNotIn("llm", detail["task"]["analysis"])
        self.assertNotIn("codex", detail["task"]["analysis"])
        self.assertNotIn("allowedNumbers", detail["task"]["analysis"])
        tasks = self.backend.list_simulator_tasks("", allow_guest=True, guest_id="template-device")
        task_summary = tasks["tasks"][0]["simcReportSummary"]
        self.assertEqual(task_summary["state"], "completed")
        self.assertEqual(task_summary["dpsDisplay"], "654321 DPS")
        self.assertEqual(task_summary["build"]["className"], "法师")
        self.assertEqual(task_summary["build"]["specName"], "奥术")
        self.assertEqual(task_summary["build"]["heroKey"], "spellslinger")
        self.assertEqual(task_summary["timing"]["finishedAt"], completed["simcReport"]["timing"]["finishedAt"])
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            row = conn.execute(
                """
                SELECT status, summary_json, queued_at, started_at, finished_at,
                       attempt, locked_by, heartbeat_at, cancel_requested, last_error
                FROM simulator_tasks
                WHERE id = ?
                """,
                (queued["taskId"],),
            ).fetchone()
        self.assertEqual(row[0], "completed")
        self.assertTrue(row[2])
        self.assertTrue(row[3])
        self.assertTrue(row[4])
        self.assertEqual(row[5], 1)
        self.assertEqual(row[6], "")
        self.assertEqual(row[7], "")
        self.assertEqual(row[8], 0)
        self.assertEqual(row[9], "")
        stored_summary = json.loads(row[1])
        self.assertEqual(stored_summary["state"], "completed")
        self.assertEqual(stored_summary["dpsDisplay"], "654321 DPS")
        self.assertEqual(stored_summary["build"]["className"], "法师")
        self.assertEqual(stored_summary["build"]["specName"], "奥术")
        self.assertEqual(stored_summary["build"]["heroKey"], "spellslinger")
        self.assertEqual(stored_summary["timing"]["finishedAt"], completed["simcReport"]["timing"]["finishedAt"])

    def test_simcraft_template_task_runner_accepts_dps_with_trivial_item_name_diagnostics(self):
        self.seed_simc_template_websim_nodes()
        from server import simulator_payload

        simc_bin = Path(self.tmp.name) / "fake-simc-template-trivial-diagnostic"
        simc_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        simc_bin.chmod(0o755)

        class FakeSimcResult:
            returncode = 1
            stdout = "Player: TemplateUnholyDK\n  DPS=654321 DPS-Error=0/0.00%\n"
            stderr = (
                "Trivial: Player 'websim_unholy' at slot hands has inconsistency between name "
                "'item_249971' and 'relentless_riders_bonegrasps' for id 249971\n"
            )

        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload()
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-trivial"})
        try:
            with patch.object(simulator_payload, "run_simcraft_process", return_value=FakeSimcResult()):
                queued = self.backend.analyze_and_store_simulator_task(request_payload)
                completed = self.backend.run_simcraft_template_task(queued["taskId"])
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)

        self.assertEqual(completed["status"], "completed")
        self.assertTrue(completed["simulation"]["ran"])
        self.assertEqual(completed["simulation"]["metrics"]["dps"], "654321")
        self.assertEqual(completed["simcReport"]["state"], "completed")
        self.assertEqual(completed["simcReport"]["result"]["dps"], "654321")
        self.assertEqual(completed["simulation"].get("error"), "")

    def test_simcraft_template_task_runner_uses_template_timeout_without_changing_profile(self):
        self.seed_simc_template_websim_nodes()
        from server import simulator_payload

        simc_bin = Path(self.tmp.name) / "fake-simc-template-timeout"
        simc_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        simc_bin.chmod(0o755)
        captured = {}

        class FakeSimcResult:
            returncode = 0
            stdout = "Player: TemplateArcaneMage\n  DPS=654321 DPS-Error=0/0.00%\n"
            stderr = ""

        def fake_run_simcraft_process(binary, profile, timeout_seconds=None):
            captured["binary"] = binary
            captured["profile"] = profile
            captured["timeout_seconds"] = timeout_seconds
            return FakeSimcResult()

        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        os.environ["WOW_SIMC_TEMPLATE_TIMEOUT_SECONDS"] = "123"
        request_payload = self.simc_template_payload(scenario="aoe_5")
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-timeout"})
        try:
            with patch.object(simulator_payload, "run_simcraft_process", side_effect=fake_run_simcraft_process):
                queued = self.backend.analyze_and_store_simulator_task(request_payload)
                completed = self.backend.run_simcraft_template_task(queued["taskId"])
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)
            os.environ.pop("WOW_SIMC_TEMPLATE_TIMEOUT_SECONDS", None)

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(captured["timeout_seconds"], 123)
        self.assertIn("iterations=10000", captured["profile"])
        self.assertIn("fight_style=Patchwerk", captured["profile"])
        self.assertIn("desired_targets=5", captured["profile"])
        self.assertIn("max_time=300", captured["profile"])

    def test_simcraft_template_task_list_recovers_tags_from_stored_request(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-task-tags",
            exchange_code=lambda code: {"openid": "openid-task-tags"},
        )
        user = self.backend.authenticate_token(login["accessToken"])
        request_payload = self.simc_template_payload(scenario="mythic_plus", race="troll")
        request_payload["raceName"] = "巨魔"
        analysis_payload = {
            "mode": "simcraft_template",
            "status": "completed",
            "simcReport": {
                "schemaRevision": "simc-report-v2",
                "state": "completed",
                "title": "奥术法师 SimC",
                "summary": "SimC completed with 654321 DPS.",
                "statusText": "completed",
                "scenario": {"key": "mythic_plus", "label": "大秘境基准", "targets": 5},
                "result": {"dpsDisplay": "654321 DPS"},
                "timing": {"finishedAt": "2026-06-27T04:21:17+00:00"},
            },
        }
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-trimmed-summary-tags",
                    user["id"],
                    "simcraft_template",
                    "completed",
                    json.dumps(request_payload),
                    json.dumps(analysis_payload),
                    "2026-06-27T04:20:00+00:00",
                    "2026-06-27T04:21:17+00:00",
                ),
            )
            conn.commit()

        tasks = self.backend.list_simulator_tasks(login["accessToken"])
        task_summary = tasks["tasks"][0]["simcReportSummary"]

        self.assertEqual(task_summary["build"]["raceName"], "巨魔")
        self.assertEqual(task_summary["build"]["className"], "法师")
        self.assertEqual(task_summary["build"]["specName"], "奥术")
        self.assertEqual(task_summary["build"]["heroKey"], "spellslinger")
        self.assertEqual(task_summary["scenario"]["key"], "mythic_plus")

    def test_simcraft_template_task_summary_backfill_updates_empty_summary_json(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-task-backfill",
            exchange_code=lambda code: {"openid": "openid-task-backfill"},
        )
        user = self.backend.authenticate_token(login["accessToken"])
        request_payload = self.simc_template_payload(scenario="mythic_plus", race="troll")
        request_payload["raceName"] = "巨魔"
        analysis_payload = {
            "mode": "simcraft_template",
            "status": "completed",
            "simulation": {"ran": True, "metrics": {"dps": "654321"}},
            "simcReport": {
                "schemaRevision": "simc-report-v2",
                "state": "completed",
                "title": "奥术法师 SimC",
                "summary": "SimC completed with 654321 DPS.",
                "statusText": "completed",
                "scenario": {"key": "mythic_plus", "label": "大秘境基准", "targets": 5},
                "result": {"dpsDisplay": "654321 DPS"},
                "timing": {"finishedAt": "2026-06-27T04:21:17+00:00"},
            },
        }
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, summary_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-empty-summary-json",
                    user["id"],
                    "simcraft_template",
                    "completed",
                    json.dumps(request_payload),
                    json.dumps(analysis_payload),
                    "{}",
                    "2026-06-27T04:20:00+00:00",
                    "2026-06-27T04:21:17+00:00",
                ),
            )
            self.backend.backfill_simulator_task_summaries(conn)
            row = conn.execute(
                "SELECT summary_json FROM simulator_tasks WHERE id = ?",
                ("task-empty-summary-json",),
            ).fetchone()

        task_summary = json.loads(row[0])
        self.assertEqual(task_summary["state"], "completed")
        self.assertEqual(task_summary["dpsDisplay"], "654321 DPS")
        self.assertEqual(task_summary["build"]["raceName"], "巨魔")
        self.assertEqual(task_summary["build"]["className"], "法师")
        self.assertEqual(task_summary["build"]["specName"], "奥术")
        self.assertEqual(task_summary["build"]["heroKey"], "spellslinger")
        self.assertEqual(task_summary["scenario"]["key"], "mythic_plus")

    def test_simcraft_template_task_detail_backfills_stat_snapshot_from_stored_gear_snapshot(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-task-stat-backfill",
            exchange_code=lambda code: {"openid": "openid-task-stat-backfill"},
        )
        user = self.backend.authenticate_token(login["accessToken"])
        request_payload = self.simc_template_payload(scenario="mythic_plus", race="troll")
        request_payload["raceName"] = "Troll"
        request_payload["templateContext"]["gear"]["metadata"] = {
            "gearSnapshot": self.simc_template_structured_gear_snapshot(),
        }
        analysis_payload = {
            "mode": "simcraft_template",
            "status": "completed",
            "simulation": {"ran": True, "metrics": {"dps": "654321"}},
            "simcReport": {
                "schemaRevision": "simc-report-v2",
                "state": "completed",
                "title": "Arcane Mage SimC",
                "summary": "SimC completed with 654321 DPS.",
                "statusText": "completed",
                "scenario": {"key": "mythic_plus", "label": "Mythic+", "targets": 5},
                "build": {
                    "classKey": "mage",
                    "specKey": "arcane",
                    "className": "Mage",
                    "specName": "Arcane",
                    "raceKey": "troll",
                    "raceName": "Troll",
                },
                "result": {"dpsDisplay": "654321 DPS"},
                "timing": {"finishedAt": "2026-06-27T04:21:17+00:00"},
            },
        }
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-detail-stat-backfill",
                    user["id"],
                    "simcraft_template",
                    "completed",
                    json.dumps(request_payload),
                    json.dumps(analysis_payload),
                    "2026-06-27T04:20:00+00:00",
                    "2026-06-27T04:21:17+00:00",
                ),
            )
            conn.commit()

        captured_requests = []

        def fake_stats_response(payload, conn=None):
            captured_requests.append(payload)
            return self.simc_template_stat_snapshot()

        with patch.object(self.backend, "build_websim_gear_stats_response", side_effect=fake_stats_response):
            detail = self.backend.get_simulator_task(login["accessToken"], "task-detail-stat-backfill")

        snapshot = detail["task"]["analysis"]["simcReport"]["build"]["statSnapshot"]
        self.assertEqual(snapshot["statStatus"], "verified")
        self.assertEqual(snapshot["primary"]["key"], "intellect")
        self.assertEqual(captured_requests[0]["classKey"], "mage")
        self.assertEqual(captured_requests[0]["specKey"], "arcane")
        self.assertEqual(captured_requests[0]["raceKey"], "troll")
        self.assertEqual(captured_requests[0]["scenarioKey"], "mythic_plus")
        self.assertEqual(captured_requests[0]["talents"], request_payload["templateContext"]["talent"]["rawString"])
        self.assertEqual(captured_requests[0]["metadata"]["gearSnapshot"]["schemaRevision"], "websim-gear-enhancement-snapshot-v1")
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            stored_analysis = json.loads(conn.execute(
                "SELECT analysis_json FROM simulator_tasks WHERE id = ?",
                ("task-detail-stat-backfill",),
            ).fetchone()[0])
        self.assertEqual(
            stored_analysis["simcReport"]["build"]["statSnapshot"]["statStatus"],
            "verified",
        )

    def test_simcraft_template_task_detail_ignores_stat_snapshot_backfill_failure(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-task-stat-backfill-failure",
            exchange_code=lambda code: {"openid": "openid-task-stat-backfill-failure"},
        )
        user = self.backend.authenticate_token(login["accessToken"])
        request_payload = self.simc_template_payload(scenario="mythic_plus", race="troll")
        request_payload["templateContext"]["gear"]["metadata"] = {
            "gearSnapshot": self.simc_template_structured_gear_snapshot(),
        }
        analysis_payload = {
            "mode": "simcraft_template",
            "status": "completed",
            "simulation": {"ran": True, "metrics": {"dps": "654321"}},
            "simcReport": {
                "schemaRevision": "simc-report-v2",
                "state": "completed",
                "summary": "SimC completed with 654321 DPS.",
                "scenario": {"key": "mythic_plus", "label": "Mythic+", "targets": 5},
                "result": {"dpsDisplay": "654321 DPS"},
                "timing": {"finishedAt": "2026-06-27T04:21:17+00:00"},
            },
        }
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute(
                """
                INSERT INTO simulator_tasks (
                    id, user_id, mode, status, request_json, analysis_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-detail-stat-backfill-failure",
                    user["id"],
                    "simcraft_template",
                    "completed",
                    json.dumps(request_payload),
                    json.dumps(analysis_payload),
                    "2026-06-27T04:20:00+00:00",
                    "2026-06-27T04:21:17+00:00",
                ),
            )
            conn.commit()

        with patch.object(
            self.backend,
            "build_websim_gear_stats_response",
            side_effect=RuntimeError("stats unavailable"),
        ):
            detail = self.backend.get_simulator_task(login["accessToken"], "task-detail-stat-backfill-failure")

        build = detail["task"]["analysis"]["simcReport"]["build"]
        self.assertNotIn("statSnapshot", build)

    def test_simcraft_template_task_runner_reports_failed_simc_without_dps_claim(self):
        self.seed_simc_template_websim_nodes()
        simc_bin = Path(self.tmp.name) / "fake-simc-template-failed"
        simc_bin.write_text(
            "#!/bin/sh\n"
            "cat > /dev/null\n"
            "printf 'invalid talent input from SimulationCraft\\n' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        simc_bin.chmod(0o755)
        os.environ["WOW_SIMC_BIN"] = str(simc_bin)
        os.environ["WOW_SIMC_TEMPLATE_TASK_AUTORUN"] = "0"
        request_payload = self.simc_template_payload()
        request_payload.update({"confirmOnly": False, "saveTask": True, "guestId": "template-device-failed"})
        try:
            queued = self.backend.analyze_and_store_simulator_task(request_payload)
            failed = self.backend.run_simcraft_template_task(queued["taskId"])
        finally:
            os.environ.pop("WOW_SIMC_BIN", None)
            os.environ.pop("WOW_SIMC_TEMPLATE_TASK_AUTORUN", None)

        self.assertEqual(failed["status"], "failed")
        self.assertFalse(failed["simulation"]["ran"])
        self.assertEqual(failed["simcReport"]["state"], "failed")
        self.assertFalse(failed["simcReport"]["result"]["hasDps"])
        self.assertEqual(failed["simcReport"]["result"]["dps"], "")
        self.assertIn("invalid talent input", failed["simcReport"]["summary"])
        self.assertIn("invalid talent input", failed["simcReport"]["messages"]["blockers"][0])
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            row = conn.execute(
                """
                SELECT status, queued_at, started_at, finished_at, attempt, last_error
                FROM simulator_tasks
                WHERE id = ?
                """,
                (queued["taskId"],),
            ).fetchone()
        self.assertEqual(row[0], "failed")
        self.assertTrue(row[1])
        self.assertTrue(row[2])
        self.assertTrue(row[3])
        self.assertEqual(row[4], 1)
        self.assertIn("invalid talent input", row[5])

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
            self.assertEqual(len(SIMC_AGENT_SPEC_CASES), 40)
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
        self.assertEqual(len(simulator_payload.MYTHIC_PLUS_DPS_REFERENCES), 40)
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
            simulator_task_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(simulator_tasks)").fetchall()
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
        self.assertIn("simulator_task_summary_v1", migrations)
        self.assertIn("simulator_task_worker_ready_v1", migrations)
        self.assertIn("summary_json", simulator_task_columns)

    def test_simulator_tasks_include_worker_ready_columns(self):
        self.backend.init_db()

        with self.backend.db_connection() as conn:
            columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(simulator_tasks)").fetchall()
            }

        for field in (
            "queued_at",
            "started_at",
            "finished_at",
            "attempt",
            "locked_by",
            "heartbeat_at",
            "cancel_requested",
            "last_error",
        ):
            self.assertIn(field, columns)

    def test_init_db_skips_seed_writes_after_schema_is_initialized(self):
        self.backend.init_db()

        with patch.object(
            self.backend,
            "seed_news_sources",
            side_effect=AssertionError("init_db should not write seed data once initialized"),
        ), patch.object(
            self.backend,
            "backfill_simulator_task_summaries",
            side_effect=AssertionError("init_db should not scan simulator tasks once initialized"),
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

    def test_user_build_templates_include_backend_simcraft_readiness(self):
        self.seed_simc_template_websim_nodes()
        login = self.backend.login_with_wechat_code(
            "wx-code-template-readiness",
            exchange_code=lambda code: {"openid": "openid-template-readiness"},
        )

        talent = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "talent",
                "title": "Arcane WebSim Talent",
                "rawString": "websim:mage:arcane:spellslinger:simc-class-1001-mage-arcane:1,simc-spec-2001-mage-arcane:1,simc-hero-3001-mage-arcane-spellslinger:1",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "spellslinger",
                "status": "saved",
            },
        )
        gear = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "gear",
                "title": "Arcane Complete Gear",
                "rawString": self.simc_template_full_gear_raw(),
                "classKey": "mage",
                "specKey": "arcane",
                "status": "complete",
            },
        )
        blocked = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "gear",
                "title": "Reference Only Gear",
                "rawString": self.simc_template_full_gear_raw(),
                "classKey": "mage",
                "specKey": "arcane",
                "status": "source_reference",
            },
        )
        listed = self.backend.list_user_build_templates(login["accessToken"])["templates"]

        self.assertEqual(talent["simcraftReadiness"]["status"], "ready")
        self.assertEqual(talent["simcraftReadiness"]["profileSource"], "template")
        self.assertEqual(talent["simcraftReadiness"]["talent"]["encodingStatus"], "encoded")
        self.assertEqual(gear["simcraftReadiness"]["status"], "ready")
        self.assertEqual(gear["simcraftReadiness"]["gear"]["parsedSlotCount"], 16)
        self.assertEqual(blocked["simcraftReadiness"]["status"], "blocked")
        self.assertIn("gear template must be complete", blocked["simcraftReadiness"]["blockers"])
        self.assertTrue(all("simcraftReadiness" in item for item in listed))

    def test_user_build_template_save_canonicalizes_metadata_gear_snapshot(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-template-gear-snapshot",
            exchange_code=lambda code: {"openid": "openid-template-gear-snapshot"},
        )

        gear = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "gear",
                "title": "Metadata Snapshot Gear",
                "rawString": "metadata snapshot placeholder",
                "classKey": "mage",
                "specKey": "arcane",
                "status": "complete",
                "metadata": {"gearSnapshot": self.simc_template_structured_gear_snapshot()},
            },
        )
        listed = self.backend.list_user_build_templates(login["accessToken"])["templates"]

        self.assertTrue(gear["rawString"].startswith("{"))
        self.assertEqual(gear["simcraftReadiness"]["status"], "ready")
        self.assertEqual(gear["simcraftReadiness"]["gear"]["rawSource"], "rawString")
        self.assertEqual(listed[0]["rawString"], gear["rawString"])

    def test_user_build_template_save_readiness_blocks_illegal_structured_gear_snapshot(self):
        login = self.backend.login_with_wechat_code(
            "wx-code-template-illegal-gear-snapshot",
            exchange_code=lambda code: {"openid": "openid-template-illegal-gear-snapshot"},
        )
        snapshot = self.simc_template_structured_gear_snapshot()
        snapshot["gearBySlot"]["head"].update({
            "name": "cloth_hood",
            "displayName": "Cloth Hood",
            "armorType": "Cloth",
        })

        gear = self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "gear",
                "title": "Illegal Snapshot Gear",
                "rawString": "metadata snapshot placeholder",
                "classKey": "shaman",
                "specKey": "elemental",
                "status": "complete",
                "metadata": {"gearSnapshot": snapshot},
            },
        )
        listed = self.backend.list_user_build_templates(login["accessToken"])["templates"]

        readiness = gear["simcraftReadiness"]
        self.assertEqual(readiness["status"], "blocked")
        self.assertEqual(readiness["gear"]["parsedSlotCount"], 15)
        self.assertIn("missing gear slots: head", readiness["blockers"])
        self.assertIn("head gear incompatible with shaman/elemental armor rule: Cloth", readiness["blockers"])
        self.assertEqual(listed[0]["simcraftReadiness"]["status"], "blocked")

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
                "crafted_stats": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
                "embellishment": {"optionCount": 0, "coveredSlotCount": 0, "coveredSlots": []},
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

    def test_data_health_payload_includes_talent_catalog_component_without_syncing(self):
        import server.websim_payload as websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            self.insert_websim_talent(conn, "simc-class-1001-mage-arcane", "class", 1001, 1, 1, "Class Talent")
            self.insert_websim_talent(conn, "simc-spec-2001-mage-arcane", "spec", 2001, 1, 2, "Spec Talent")
            self.insert_websim_talent(conn, "simc-hero-3001-mage-arcane-spellslinger", "hero", 3001, 2, 1, "Hero Talent")
            conn.execute(
                """
                INSERT INTO websim_spell_details
                (id, spell_id, name, description, icon_url, locale, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "spell-101001",
                    101001,
                    "Class Talent",
                    "Class description",
                    "https://render.worldofwarcraft.com/icon/class.jpg",
                    "zh_CN",
                    "{}",
                    "2026-06-22T00:00:00+00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets
                (id, class_key, spec_key, name, profile, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "preset-mage-arcane",
                    "mage",
                    "arcane",
                    "Arcane preset",
                    "mage=\"Arcane\"\nspec=arcane",
                    "{}",
                    "2026-06-22T00:00:00+00:00",
                ),
            )
            websim_payload.set_sync_state(
                conn,
                "websim_sync",
                {
                    "ok": True,
                    "dataStatus": "verified",
                    "checkedAt": "2026-06-22T00:00:00+00:00",
                    "simc": {"talents": 3, "presets": 1, "build": "simc-test-build"},
                    "currentSeason": {"seasonRevision": "season-test", "dataStatus": "verified"},
                },
            )
            conn.commit()

        with patch.object(self.backend, "sync_raiderio_cache", side_effect=AssertionError("health must be read-only")):
            payload = self.backend.build_data_health_payload()

        component = {item["key"]: item for item in payload["components"]}["talent_catalog"]
        details = component["details"]

        self.assertEqual(component["status"], "partial")
        self.assertEqual(details["talentCount"], 3)
        self.assertEqual(details["classCount"], 1)
        self.assertEqual(details["specCount"], 1)
        self.assertEqual(details["heroTreeCount"], 1)
        self.assertEqual(details["profilePresetCount"], 1)
        self.assertEqual(details["officialAuditStatus"], "pending_official_audit")
        self.assertEqual(details["expectedSpecCount"], 40)
        self.assertEqual(details["expectedHeroTreeCount"], 80)
        self.assertEqual(details["coveredExpectedHeroTreeCount"], 1)
        self.assertEqual(details["spellDetailCoverage"]["talentSpellCount"], 3)
        self.assertEqual(details["spellDetailCoverage"]["coveredSpellCount"], 1)
        self.assertEqual(details["spellDetailCoverage"]["missingSpellDetailCount"], 2)
        self.assertEqual(details["ruleReadiness"]["treeReady"], False)
        self.assertEqual(details["ruleReadiness"]["heroTreeCoverage"]["covered"], 1)
        self.assertEqual(details["sourceReadiness"]["officialAuditStatus"], "pending_official_audit")
        self.assertEqual(details["readiness"]["spellReady"], False)
        self.assertEqual(details["readiness"]["simcReady"], False)
        self.assertEqual(details["catalogContract"]["sourceStatus"], "simc")
        self.assertEqual(details["catalogContract"]["coverage"]["covered"], 1)
        self.assertEqual(details["catalogContract"]["coverage"]["total"], 3)

    def test_data_health_payload_includes_template_simc_bridge_component(self):
        self.seed_simc_template_websim_nodes()
        version_file = Path(self.tmp.name) / "simc-version.json"
        version_file.write_text(
            json.dumps(
                {
                    "checkedAt": "2026-06-27T08:00:00+00:00",
                    "localTag": "1205-2026-06-27-local",
                    "latestTag": "1205-2026-06-27-local",
                    "updateAvailable": False,
                    "source": "dockerhub",
                    "image": "simulationcraftorg/simc:1205-2026-06-27-local",
                }
            ),
            encoding="utf-8",
        )
        os.environ["WOW_SIMC_VERSION_FILE"] = str(version_file)
        login = self.backend.login_with_wechat_code(
            "wx-code-template-health",
            exchange_code=lambda code: {"openid": "openid-template-health"},
        )
        try:
            self.backend.save_user_build_template(
                login["accessToken"],
                {
                    "type": "talent",
                    "title": "Health Talent",
                    "rawString": "websim:mage:arcane:spellslinger:simc-class-1001-mage-arcane:1,simc-spec-2001-mage-arcane:1,simc-hero-3001-mage-arcane-spellslinger:1",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "heroKey": "spellslinger",
                    "status": "saved",
                },
            )
            self.backend.save_user_build_template(
                login["accessToken"],
                {
                    "type": "gear",
                    "title": "Health Gear",
                    "rawString": self.simc_template_full_gear_raw(),
                    "classKey": "mage",
                    "specKey": "arcane",
                    "status": "complete",
                },
            )

            payload = self.backend.build_data_health_payload()
        finally:
            os.environ.pop("WOW_SIMC_VERSION_FILE", None)

        component = {item["key"]: item for item in payload["components"]}["template_simc_bridge"]

        self.assertEqual(component["status"], "verified")
        self.assertEqual(component["details"]["simcraftVersion"]["localTag"], "1205-2026-06-27-local")
        self.assertEqual(component["details"]["templateReadiness"]["ready"], 2)
        self.assertEqual(component["details"]["templateReadiness"]["blocked"], 0)
        self.assertEqual(component["details"]["templateReadiness"]["total"], 2)
        self.assertEqual(component["blockers"], [])

    def test_data_health_payload_exposes_catalog_contract_for_core_catalogs(self):
        import server.websim_payload as websim_payload

        payload = self.backend.build_data_health_payload()
        components = {item["key"]: item for item in payload["components"]}

        self.assertIn("catalogContract", components["gear_catalog"]["details"])
        self.assertIn("catalogContract", components["talent_catalog"]["details"])
        self.assertEqual(components["gear_catalog"]["details"]["catalogContract"]["schemaRevision"], "websim-gear-catalog-v1")
        self.assertEqual(components["talent_catalog"]["details"]["catalogContract"]["schemaRevision"], "websim-talent-catalog-v1")
        self.assertEqual(components["gear_catalog"]["details"]["catalogContract"]["status"], components["gear_catalog"]["status"])
        self.assertEqual(components["talent_catalog"]["details"]["catalogContract"]["status"], components["talent_catalog"]["status"])

    def test_data_health_payload_includes_season_cutover_readiness_control_plane(self):
        import server.websim_payload as websim_payload

        version_file = Path(self.tmp.name) / "simc-version.json"
        version_file.write_text(
            json.dumps(
                {
                    "checkedAt": "2026-07-06T08:00:00+00:00",
                    "localTag": "simc-12.0-s1-20260706-abc123",
                    "latestTag": "simc-12.0-s1-20260706-abc123",
                    "simcRuntimeRevision": "simc-12.0-s1-20260706-abc123",
                    "sourceCommit": "abc123",
                    "channel": "retail",
                    "status": "verified",
                    "updateAvailable": False,
                }
            ),
            encoding="utf-8",
        )
        os.environ["WOW_SIMC_VERSION_FILE"] = str(version_file)
        try:
            with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
                season = websim_payload.current_season_payload(
                    season_id="midnight-season-1",
                    season_label="至暗之夜 Season 1",
                    dungeons=[{"id": "eco-dome", "dungeonId": "eco-dome", "instanceId": "eco", "name": "生态圆顶", "shortName": "生态圆顶", "timerSeconds": 1800}],
                    verified_at="2026-07-06T08:00:00+00:00",
                )
                season.update(
                    {
                        "seasonRevision": "retail-12.0-s1-active",
                        "revision": "retail-12.0-s1-active",
                        "patch": "12.0",
                        "season": "s1",
                        "channel": "retail",
                        "status": "active",
                        "gearCatalogRevision": "retail-12.0-s1-gear",
                        "talentCatalogRevision": "retail-12.0-s1-talents",
                        "simcRuntimeRevision": "simc-12.0-s1-20260706-abc123",
                        "terminologyRevision": "term-retail-12.0-s1",
                        "rollbackSeasonRevision": "retail-12.0-s1-rollback",
                    }
                )
                websim_payload.save_active_season_payload(conn, season)
                websim_payload.set_sync_state(
                    conn,
                    "websim_sync",
                    {
                        "dataStatus": "verified",
                        "checkedAt": "2026-07-06T08:00:00+00:00",
                        "currentSeason": season,
                        "talentRevision": "retail-12.0-s1-talents",
                        "simc": {"build": "1205", "profiles": 40},
                        "stagingSeasonManifest": {
                            "seasonRevision": "ptr-12.1-s2-build-12345",
                            "patch": "12.1",
                            "season": "s2",
                            "channel": "ptr",
                            "status": "candidate",
                            "active": False,
                            "gearCatalogRevision": "ptr-12.1-s2-gear-build-12345",
                            "talentCatalogRevision": "ptr-12.1-s2-talents-build-12345",
                        },
                    },
                )
                websim_payload.set_sync_state(
                    conn,
                    "gearCatalog",
                    {
                        "status": "partial",
                        "checkedAt": "2026-07-06T08:00:00+00:00",
                        "itemDatabaseRevision": "retail-12.0-s1-gear",
                        "variantRevision": "retail-12.0-s1-gear",
                        "variantCount": 1,
                    },
                )
                conn.commit()

            payload = self.backend.build_data_health_payload(include_template_evidence_audit=False)
        finally:
            os.environ.pop("WOW_SIMC_VERSION_FILE", None)

        component = {item["key"]: item for item in payload["components"]}["season_cutover_readiness"]
        details = component["details"]

        self.assertEqual(details["schemaRevision"], "season-cutover-readiness-v1")
        self.assertEqual(details["activeManifest"]["seasonRevision"], "retail-12.0-s1-active")
        self.assertEqual(details["activeManifest"]["channel"], "retail")
        self.assertEqual(details["activeManifest"]["readAuthority"], "active_retail_only")
        self.assertEqual(details["activeManifest"]["rollbackSeasonRevision"], "retail-12.0-s1-rollback")
        self.assertEqual(details["stagingManifests"][0]["seasonRevision"], "ptr-12.1-s2-build-12345")
        self.assertEqual(details["stagingManifests"][0]["active"], False)
        self.assertEqual(details["revisionBindings"]["gearCatalogRevision"], "retail-12.0-s1-gear")
        self.assertEqual(details["revisionBindings"]["talentCatalogRevision"], "retail-12.0-s1-talents")
        self.assertEqual(details["revisionBindings"]["simcRuntimeRevision"], "simc-12.0-s1-20260706-abc123")
        self.assertEqual(details["revisionBindings"]["terminologyRevision"], "term-retail-12.0-s1")
        self.assertEqual(details["simcRuntime"]["sourceCommit"], "abc123")
        self.assertEqual(details["catalystOverlay"]["simcOption"], "redirected_base_stats")
        self.assertEqual(details["catalystOverlay"]["status"], "blocked")
        self.assertTrue(any("proof matrix" in blocker for blocker in details["blockers"]))
        self.assertEqual(details["terminologyCatalog"]["minimumTerms"][0]["canonicalName"], "疾咒师")
        self.assertIn("法术投射者", details["terminologyCatalog"]["minimumTerms"][0]["aliases"])
        self.assertEqual(details["officialReadPolicy"]["allowClientSeasonOverride"], False)

    def test_catalyst_overlay_allowlist_does_not_prove_cutover_capability(self):
        gate = self.backend.catalyst_overlay_cutover_gate()

        self.assertIn("redirected_base_stats", gate["supportedSimcOptions"])
        self.assertEqual(gate["simcOption"], "redirected_base_stats")
        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(gate["capabilityEnabled"], False)
        self.assertTrue(any("proof matrix" in blocker for blocker in gate["blockers"]))

    def test_catalyst_redirected_base_stats_is_a_controlled_simc_option(self):
        import server.websim_payload as websim_payload

        parsed = websim_payload.simc_gear_entry_identity(
            "head",
            {
                "slot": "head",
                "id": "260001",
                "ilevel": 704,
                "redirected_base_stats": "crit/mastery",
                "unknown_option": "SHOULD_NOT_PASS",
            },
        )

        self.assertEqual(parsed["simcOptions"]["redirected_base_stats"], "crit/mastery")
        self.assertNotIn("unknown_option", parsed["simcOptions"])

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
                        "totalHeroSlotCount": 80,
                        "coveredSpecCount": 38,
                        "coveredHeroSlotCount": 76,
                        "pendingCollectionHeroSlotCount": 4,
                        "missingSpecs": ["rogue:subtlety", "shaman:restoration"],
                    },
                    "coverageMatrix": {
                        "schemaRevision": "community-talent-coverage-matrix-v1",
                        "totalSpecCount": 40,
                        "totalHeroSlotCount": 80,
                        "verifiedHeroSlotCount": 76,
                        "pendingCollectionHeroSlotCount": 4,
                        "blockedHeroSlotCount": 0,
                        "rows": [
                            {
                                "slotId": "rogue:subtlety:deathstalker",
                                "classKey": "rogue",
                                "specKey": "subtlety",
                                "heroKey": "deathstalker",
                                "status": "pending_collection",
                                "blockers": [
                                    {
                                        "stage": "source_collection",
                                        "reason": "missing verified community talent template for rogue/subtlety/deathstalker",
                                    }
                                ],
                            }
                        ],
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
        self.assertEqual(component["details"]["coverageMatrix"]["totalHeroSlotCount"], 80)
        self.assertEqual(component["details"]["coverageMatrix"]["rows"][0]["status"], "pending_collection")
        self.assertEqual(component["details"]["dedupedCount"], 72)
        self.assertEqual(component["details"]["hiddenDuplicateCount"], 18)
        self.assertEqual(component["details"]["wclTemplateSource"]["status"], "missing_credentials")

    def test_data_health_payload_includes_default_gear_template_coverage(self):
        import server.websim_payload as websim_payload

        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.set_sync_state(
                conn,
                websim_payload.COMMUNITY_TALENT_SYNC_KEY,
                {
                    "sourceStatus": "partial",
                    "templateRevision": "community-template-v1-test",
                    "scanCoverage": {"totalSpecCount": 40, "coveredSpecCount": 40, "missingSpecs": []},
                    "dedupedCount": 72,
                    "hiddenDuplicateCount": 0,
                    "sources": {},
                    "templates": {"total": 80, "verified": 80, "blocked": 0},
                    "checkedAt": "2026-06-28T08:00:00+00:00",
                },
            )
            websim_payload.set_sync_state(
                conn,
                websim_payload.COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
                {
                    "scanRunId": "community-template-health-test",
                    "sourceStatus": "partial",
                    "gear": {
                        "preflight": {
                            "schemaRevision": "community-gear-template-preflight-v1",
                            "totalSpecCount": 40,
                            "communityImport": {
                                "status": "partial",
                                "totalTemplateSlotCount": 80,
                                "coveredTemplateSlotCount": 79,
                                "missingTemplateSlotCount": 1,
                            },
                            "canonicalSlotMatrix": {
                                "totalSlotCount": 640,
                                "readySlotCount": 16,
                                "missingSlotCount": 624,
                            },
                        },
                        "communityImportTemplates": {
                            "status": "partial",
                            "totalTemplateSlotCount": 80,
                            "coveredTemplateSlotCount": 79,
                            "missingTemplateSlotCount": 1,
                            "baselineBlockedSpecCount": 1,
                        },
                        "baselineTemplates": {
                            "availableSpecCount": 39,
                            "blockedSpecCount": 1,
                            "blockedSpecs": ["demonhunter:devourer"],
                        },
                        "defaultTemplates": {
                            "coveredSpecCount": 39,
                            "missingSpecCount": 1,
                            "blockedSpecCount": 1,
                            "missingSpecs": ["demonhunter:devourer"],
                            "blockers": [
                                {
                                    "classKey": "demonhunter",
                                    "specKey": "devourer",
                                    "reason": "missing verified stat weight cache",
                                }
                            ],
                        }
                    },
                },
            )
            conn.commit()

        payload = self.backend.build_data_health_payload()
        component = {item["key"]: item for item in payload["components"]}["community_templates"]

        self.assertEqual(component["details"]["defaultGearTemplates"]["coveredSpecCount"], 39)
        self.assertEqual(component["details"]["defaultGearTemplates"]["missingSpecs"], ["demonhunter:devourer"])
        self.assertEqual(component["details"]["defaultGearTemplates"]["blockers"][0]["reason"], "missing verified stat weight cache")
        self.assertEqual(component["details"]["gearTemplatePreflight"]["canonicalSlotMatrix"]["totalSlotCount"], 640)
        self.assertEqual(component["details"]["communityImportTemplates"]["totalTemplateSlotCount"], 80)
        self.assertEqual(component["details"]["communityImportTemplates"]["coveredTemplateSlotCount"], 79)
        self.assertEqual(component["details"]["communityImportTemplates"]["missingTemplateSlotCount"], 1)
        self.assertEqual(component["details"]["baselineGearTemplates"]["availableSpecCount"], 39)

    def test_data_health_payload_exposes_template_evidence_audit_read_only(self):
        import server.websim_payload as websim_payload

        expected_classes = [{"key": "demonhunter", "label": "Demon Hunter", "specs": ["devourer"]}]
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            websim_payload.ensure_websim_tables(conn)
            websim_payload.set_sync_state(
                conn,
                websim_payload.COMMUNITY_TALENT_SYNC_KEY,
                {
                    "sourceStatus": "partial",
                    "templateRevision": "community-template-v1-test",
                    "scanCoverage": {"totalSpecCount": 1, "coveredSpecCount": 0, "missingSpecs": ["demonhunter:devourer"]},
                    "dedupedCount": 0,
                    "hiddenDuplicateCount": 0,
                    "sources": {
                        "warcraftlogs": {
                            "status": "missing_credentials",
                            "sourceName": "Warcraft Logs",
                            "errors": ["missing credentials"],
                        }
                    },
                    "templates": {"total": 0, "verified": 0, "blocked": 0},
                    "checkedAt": "2026-06-28T08:00:00+00:00",
                },
            )
            websim_payload.set_sync_state(
                conn,
                websim_payload.COMMUNITY_TEMPLATE_SYNC_RUN_KEY,
                {
                    "scanRunId": "community-template-health-audit-test",
                    "sourceStatus": "partial",
                    "gear": {
                        "realCommunityTemplates": {
                            "coveredSpecs": [],
                            "missingSpecs": ["demonhunter:devourer"],
                        },
                        "defaultTemplates": {
                            "coveredSpecCount": 0,
                            "missingSpecCount": 1,
                            "blockedSpecCount": 1,
                            "missingSpecs": ["demonhunter:devourer"],
                            "blockers": [
                                {
                                    "classKey": "demonhunter",
                                    "specKey": "devourer",
                                    "specId": "demonhunter:devourer",
                                    "reason": "stat weight cache is not verified: blocked",
                                }
                            ],
                        },
                    },
                },
            )
            conn.commit()

        with patch.object(websim_payload, "WOW_CLASSES", expected_classes), patch.object(
            self.backend,
            "sync_raiderio_cache",
            side_effect=AssertionError("health must be read-only"),
        ):
            payload = self.backend.build_data_health_payload()

        component = {item["key"]: item for item in payload["components"]}["community_templates"]
        audit = component["details"]["templateEvidenceAudit"]
        dumped = json.dumps(audit, ensure_ascii=False)

        self.assertEqual(component["status"], "partial")
        self.assertEqual(audit["schemaRevision"], "template-evidence-audit-v1")
        self.assertEqual(set(["defaultGear", "realCommunityGear", "communityTalent"]).issubset(audit), True)
        self.assertEqual(audit["defaultGear"]["unlockScenarioKey"], "mplus_mixed_route")
        self.assertEqual(audit["defaultGear"]["matrix"][0]["specId"], "demonhunter:devourer")
        self.assertEqual(audit["defaultGear"]["matrix"][0]["firstBlockingGate"], "statWeightGate")
        self.assertEqual(audit["realCommunityGear"]["summary"]["coveredSpecCount"], 0)
        self.assertEqual(audit["communityTalent"]["summary"]["realCoveredSpecCount"], 0)
        self.assertEqual(audit["sourceDependencies"]["warcraftlogs"]["status"], "missing_credentials")
        self.assertNotIn("profileUrl", dumped)
        self.assertNotIn("rawProfile", dumped)
        self.assertNotIn("secret", dumped.lower())

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

    def test_data_health_websim_sync_prefers_standalone_gear_catalog_state(self):
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
                        "observedVariantCount": 93,
                        "seasonSourceCoverage": {
                            "mythicPlus": {"sourceItemCount": 464},
                        },
                    },
                },
            )
            websim_payload.set_sync_state(
                conn,
                "gearCatalog",
                {
                    "status": "partial",
                    "itemCount": 756,
                    "observedVariantCount": 2388,
                    "seasonSourceCoverage": {
                        "mythicPlus": {"sourceItemCount": 203},
                        "instances": [
                            {
                                "name": "萨隆矿坑",
                                "sourceItemCount": 24,
                                "verifiedItemCount": 4,
                                "partialItemCount": 20,
                            }
                        ],
                    },
                },
            )
            conn.commit()

        payload = self.backend.build_data_health_payload()
        component = {item["key"]: item for item in payload["components"]}["websim_sync"]
        gear_catalog = component["details"]["gearCatalog"]

        self.assertEqual(component["details"]["gearItemCount"], 756)
        self.assertEqual(component["details"]["observedVariantCount"], 2388)
        self.assertEqual(gear_catalog["seasonSourceCoverage"]["mythicPlus"]["sourceItemCount"], 203)
        self.assertEqual(gear_catalog["seasonSourceCoverage"]["instances"][0]["sourceItemCount"], 24)

    def test_pg_only_data_health_uses_postgres_state_without_sqlite(self):
        community_sync_key = self.backend.COMMUNITY_TEMPLATE_SYNC_RUN_KEY

        class ContentStore:
            def latest_refresh_run_payload(self):
                return {
                    "refreshMode": "scheduled",
                    "refreshedAt": "2026-07-03T00:00:00+00:00",
                    "acceptedCount": 2,
                    "blockedArticleCount": 0,
                    "queuedCount": 0,
                    "retryableCount": 0,
                    "discoveredCount": 2,
                    "processedCount": 2,
                    "publishedCount": 2,
                    "sourceFetchErrors": [],
                    "collectorErrors": [],
                }

        class CacheStore:
            def get_sync_state(self, key):
                states = {
                    "websim_sync": {
                        "ok": False,
                        "dataStatus": "blocked",
                        "checkedAt": "2026-07-03T00:01:00+00:00",
                        "errors": ["PostgreSQL WebSim sync state is blocked"],
                        "simc": {"talents": 5246, "profiles": 50},
                    },
                    "gearCatalog": {
                        "status": "blocked",
                        "checkedAt": "2026-07-03T00:02:00+00:00",
                        "itemCount": 0,
                        "variantCount": 0,
                        "blockers": ["PostgreSQL gear catalog is empty"],
                    },
                    community_sync_key: {
                        "scanRunId": "pg-only-health",
                        "changeReport": {
                            "schemaRevision": "community-template-daily-change-report-v1",
                            "summary": {
                                "unchanged": 120,
                                "metadata_refreshed": 0,
                                "promoted": 0,
                                "candidate_only": 0,
                                "needs_review": 0,
                                "rejected_regression": 0,
                                "blocked": 0,
                                "stale_winner": 0,
                            },
                        },
                        "gear": {
                            "templates": {"total": 77, "verified": 32, "partial": 45, "blocked": 0},
                            "realCommunityTemplates": {"coveredSpecCount": 12, "missingSpecCount": 28},
                    "baselineTemplates": {"availableSpecCount": 32, "blockedSpecCount": 8},
                    "communityImportTemplates": {
                        "status": "partial",
                        "totalTemplateSlotCount": 80,
                        "coveredTemplateSlotCount": 72,
                        "missingTemplateSlotCount": 8,
                    },
                    "defaultTemplates": {"blockedSpecCount": 0},
                },
                    },
                    "community_talent_templates": {
                        "sourceStatus": "blocked",
                        "checkedAt": "2026-07-03T00:03:00+00:00",
                        "templates": {"total": 0, "verified": 0, "blocked": 0},
                        "sources": {},
                    },
                    "raiderio": {
                        "sourceStatus": "blocked",
                        "checkedAt": "2026-07-03T00:04:00+00:00",
                        "errors": ["PostgreSQL Raider.IO cache is empty"],
                    },
                    "stat_weights_sync": {
                        "sourceStatus": "partial",
                        "status": "partial",
                        "refreshedAt": "2026-07-03T00:05:00+00:00",
                        "acceptedCount": 11,
                        "blockedCount": 109,
                        "raiderioStatus": "verified",
                        "specCount": 40,
                        "scenarioCount": 3,
                        "errors": [],
                    },
                }
                return states.get(key, {})

            def community_gear_template_live_health_summary(self):
                return {
                    "templates": {"total": 77, "verified": 43, "partial": 34, "blocked": 0},
                    "preflight": {
                        "schemaRevision": "community-gear-template-preflight-v1",
                        "canonicalSlotMatrix": {
                            "totalSlotCount": 640,
                            "readySlotCount": 550,
                            "missingSlotCount": 90,
                        },
                    },
                    "realCommunityTemplates": {
                        "coveredSpecCount": 23,
                        "missingSpecCount": 17,
                        "partialSpecCount": 17,
                        "pendingSpecCount": 0,
                        "blockedSpecCount": 0,
                    },
                    "baselineTemplates": {"availableSpecCount": 40, "blockedSpecCount": 0},
                    "seasonRecommendation": {
                        "sourceKey": "season_recommendation",
                        "status": "verified",
                        "totalSpecCount": 40,
                        "completeSpecCount": 40,
                        "verifiedSpecCount": 0,
                        "provisionalSpecCount": 40,
                        "blockedSpecCount": 0,
                        "lastRunId": "season-recommended-gear-test",
                    },
                    "communityImportTemplates": {
                        "status": "partial",
                        "totalTemplateSlotCount": 80,
                        "coveredTemplateSlotCount": 63,
                        "missingTemplateSlotCount": 17,
                    },
                    "templateChains": {
                        "schemaRevision": "gear-template-chain-state-v1",
                        "communityObserved": {
                            "coveredSpecCount": 23,
                            "verifiedSpecCount": 12,
                            "partialSpecCount": 11,
                            "blockedSpecCount": 17,
                        },
                        "recommendedBis": {
                            "totalSpecCount": 0,
                            "verifiedSpecCount": 0,
                            "anchorFailedSpecCount": 0,
                        },
                        "legacyFallback": {
                            "totalSpecCount": 40,
                            "starterBaselineSpecCount": 40,
                        },
                    },
                    "recommendedBisGuard": {
                        "schemaRevision": "recommended-bis-v1-guard-state-v1",
                        "status": "blocked",
                        "guardMode": "readiness_only",
                        "expectedSpecCount": 40,
                        "optimizerRequiredSpecCount": 40,
                        "fullOptimizerRunRequiredSpecCount": 40,
                        "lastGuardCheckAt": "2026-07-07T13:00:00+00:00",
                    },
                    "communityObservedGuard": {
                        "schemaRevision": "community-best-v2-guard-state-v1",
                        "status": "partial",
                        "guardMode": "readiness_only",
                        "expectedSpecCount": 40,
                        "coveredSpecCount": 23,
                        "simcReplayRequiredSpecCount": 11,
                        "lastGuardCheckAt": "2026-07-07T13:05:00+00:00",
                    },
                    "scanRunId": "live-health-summary",
                }

            def get_active_season_payload(self):
                return {
                    "seasonId": "season-pg",
                    "seasonRevision": "season-pg-rev",
                    "locale": "zh_CN",
                    "dataStatus": "stale",
                    "verifiedAt": "2026-07-02T00:00:00+00:00",
                    "expiresAt": "2026-07-03T00:00:00+00:00",
                    "errors": ["season cache expired"],
                }

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "content_data_store", return_value=ContentStore()), patch.object(
            self.backend, "cache_data_store", return_value=CacheStore()
        ), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only health must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only health must not open SQLite"),
        ):
            payload = self.backend.build_data_health_payload(include_template_evidence_audit=False)

        components = {item["key"]: item for item in payload["components"]}
        self.assertEqual(components["news"]["status"], "verified")
        self.assertEqual(components["websim_season"]["status"], "stale")
        self.assertEqual(components["websim_sync"]["status"], "blocked")
        self.assertEqual(components["websim_sync"]["details"]["talentCount"], 5246)
        self.assertEqual(components["websim_sync"]["details"]["profileCount"], 50)
        self.assertEqual(components["gear_catalog"]["status"], "blocked")
        authority = components["gear_legality_authority"]
        self.assertEqual(authority["status"], "partial")
        self.assertEqual(authority["details"]["totalSpecs"], 40)
        self.assertEqual(authority["details"]["verifiedSpecs"], 0)
        self.assertEqual(authority["details"]["manualOverrideSpecs"], 40)
        self.assertEqual(authority["details"]["ruleSourceMapStatus"], "partial")
        self.assertEqual(authority["details"]["sourceMap"]["schemaRevision"], "gear-legality-source-map-v1")
        self.assertEqual(authority["details"]["sourceMap"]["expectedSpecCount"], 40)
        self.assertEqual(authority["details"]["sourceMap"]["verifiedSpecCount"], 0)
        self.assertEqual(authority["details"]["sourceMap"]["manualOverrideSpecCount"], 40)
        self.assertEqual(authority["details"]["sourceMap"]["officialVerifiedSpecCount"], 0)
        self.assertEqual(authority["details"]["sourceMap"]["simcVerifiedSpecCount"], 0)
        self.assertGreaterEqual(authority["details"]["sourceMap"]["observedSupportedSpecCount"], 2)
        self.assertEqual(authority["details"]["blockedTemplateCount"], 0)
        self.assertEqual(authority["details"]["excludedCandidateCount"], 0)
        self.assertIn("manual_override", authority["blockers"][0])
        self.assertEqual(components["raiderio"]["blockers"], ["PostgreSQL Raider.IO cache is empty"])
        self.assertEqual(components["stat_weights"]["status"], "partial")
        self.assertEqual(components["stat_weights"]["checkedAt"], "2026-07-03T00:05:00+00:00")
        self.assertEqual(components["stat_weights"]["details"]["acceptedCount"], 11)
        self.assertIn("PostgreSQL WebSim sync state is blocked", components["websim_sync"]["blockers"])
        community_details = components["community_templates"]["details"]
        self.assertEqual(community_details["gearTemplates"]["verified"], 43)
        self.assertEqual(community_details["communityImportTemplates"]["coveredTemplateSlotCount"], 63)
        self.assertEqual(community_details["communityImportTemplates"]["missingTemplateSlotCount"], 17)
        self.assertEqual(community_details["realCommunityGearTemplates"]["coveredSpecCount"], 23)
        self.assertEqual(community_details["seasonRecommendation"]["completeSpecCount"], 40)
        self.assertEqual(community_details["seasonRecommendation"]["provisionalSpecCount"], 40)
        self.assertEqual(community_details["templateChains"]["communityObserved"]["verifiedSpecCount"], 12)
        self.assertEqual(community_details["templateChains"]["recommendedBis"]["totalSpecCount"], 0)
        self.assertEqual(community_details["templateChains"]["legacyFallback"]["starterBaselineSpecCount"], 40)
        self.assertEqual(community_details["recommendedBisGuard"]["schemaRevision"], "recommended-bis-v1-guard-state-v1")
        self.assertEqual(community_details["recommendedBisGuard"]["guardMode"], "readiness_only")
        self.assertEqual(community_details["recommendedBisGuard"]["optimizerRequiredSpecCount"], 40)
        self.assertEqual(community_details["communityObservedGuard"]["schemaRevision"], "community-best-v2-guard-state-v1")
        self.assertEqual(community_details["communityObservedGuard"]["guardMode"], "readiness_only")
        self.assertEqual(community_details["communityObservedGuard"]["simcReplayRequiredSpecCount"], 11)
        self.assertEqual(community_details["gearTemplatePreflight"]["canonicalSlotMatrix"]["missingSlotCount"], 90)
        self.assertEqual(community_details["changeReport"]["summary"]["unchanged"], 120)
        self.assertEqual(community_details["lastSyncRun"], "live-health-summary")

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

    def test_data_health_route_skips_template_evidence_audit_by_default(self):
        with patch.object(
            self.backend,
            "build_data_health_payload",
            wraps=self.backend.build_data_health_payload,
        ) as wrapped:
            server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/data/health", timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
        self.assertEqual(wrapped.call_args.kwargs.get("include_template_evidence_audit"), False)

    def test_data_health_route_allows_explicit_template_evidence_audit(self):
        with patch.object(
            self.backend,
            "build_data_health_payload",
            wraps=self.backend.build_data_health_payload,
        ) as wrapped:
            server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/data/health?audit=1", timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                thread.join(timeout=2)
                server.server_close()
        self.assertEqual(wrapped.call_args.kwargs.get("include_template_evidence_audit"), True)

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

    def test_chickenbro_guest_policy_requires_explicit_identity_context(self):
        self.backend.init_db()

        with self.assertRaises(PermissionError):
            self.backend.resolve_chickenbro_user(access_token="", guest_id="", create_guest=False)

        with self.assertRaises(PermissionError):
            self.backend.resolve_chickenbro_user(
                access_token="",
                guest_id="unknown-chickenbro-device",
                create_guest=False,
            )

    def test_chickenbro_explicit_guest_creation_remains_current_compatibility_path(self):
        self.backend.init_db()

        user = self.backend.resolve_chickenbro_user(
            access_token="",
            guest_id="explicit-chickenbro-device",
            create_guest=True,
        )

        self.assertTrue(user["openid"].startswith("guest-simulator-"))
        self.assertEqual(
            self.backend.resolve_chickenbro_user(
                access_token="",
                guest_id="explicit-chickenbro-device",
                create_guest=False,
            )["id"],
            user["id"],
        )

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

    def test_chickenbro_missing_profile_still_calls_codex_for_direct_chat(self):
        captured = {}

        def fake_codex_runner(prompt, **kwargs):
            captured["prompt"] = prompt
            captured["schema"] = kwargs.get("schema")
            return {
                "status": "succeeded",
                "lastMessage": json.dumps(
                    {
                        "answer": "我可以先按通用冰DK改动讨论思路，但当前没有本地已发布画像，所以不会给出强度、排名或日志结论。",
                        "confidence": "low",
                        "priorityActions": [
                            {"title": "先补充专精、场景、SimC 或 WCL 证据。", "evidenceRefs": []}
                        ],
                        "evidenceRefs": [],
                        "limitations": ["missing_published_profile"],
                    },
                    ensure_ascii=False,
                ),
            }

        result = self.backend.send_chickenbro_message(
            {
                "message": "看看12.1冰DK改动了哪些",
                "guestId": "missing-profile-codex-device",
                "context": {"classKey": "deathknight", "specKey": "frost", "scenarioKey": "mplus_fortified"},
            },
            codex_runner=fake_codex_runner,
        )

        prompt_payload = json.loads(captured["prompt"])
        self.assertIn("boundedContext", prompt_payload)
        self.assertTrue(any("direct Codex chat" in item for item in prompt_payload["instructions"]))
        self.assertFalse(any("只能使用 boundedContext 中的事实" in item for item in prompt_payload["instructions"]))
        self.assertIs(captured["schema"]["additionalProperties"], False)
        self.assertEqual(result["assistantMessage"]["payload"]["answerSource"], "codex")
        self.assertEqual(result["job"]["result"]["validation"]["status"], "passed")
        self.assertEqual(result["job"]["result"]["codex"]["status"], "succeeded")
        self.assertIn("通用冰DK", result["assistantMessage"]["content"])

    def test_chickenbro_direct_chat_without_profile_returns_player_coach_layer(self):
        def skip_codex(prompt, **kwargs):
            return {"status": "skipped", "error": "disabled in test"}

        result = self.backend.send_chickenbro_message(
            {
                "message": "大秘境打得很乱，先从哪里改？",
                "guestId": "direct-chat-layer-device",
            },
            codex_runner=skip_codex,
        )

        payload = result["assistantMessage"]["payload"]
        self.assertEqual(payload["answerLayer"], "direct_chat")
        self.assertEqual(payload["basisLabel"], "通用建议")
        self.assertIn("老玩家", payload["answer"])
        self.assertIn("missing_published_profile", payload["limitations"])
        self.assertTrue(payload["nextQuestion"])
        self.assertLessEqual(payload["nextQuestion"].count("？") + payload["nextQuestion"].count("?"), 1)
        self.assertIn("class_spec", payload["missingInputs"])
        self.assertNotIn("只补齐角色、专精、场景和可追踪证据", payload["answer"])

    def test_chickenbro_sparse_context_uses_diagnostic_coach_layer(self):
        def skip_codex(prompt, **kwargs):
            return {"status": "skipped", "error": "disabled in test"}

        result = self.backend.send_chickenbro_message(
            {
                "message": "我是冰DK，大秘境伤害低，先排查什么？",
                "guestId": "diagnostic-layer-device",
                "context": {"classKey": "deathknight", "specKey": "frost", "scenarioKey": "mplus_fortified"},
            },
            codex_runner=skip_codex,
        )

        payload = result["assistantMessage"]["payload"]
        self.assertEqual(payload["answerLayer"], "diagnostic")
        self.assertEqual(payload["basisLabel"], "需要证据确认")
        self.assertGreaterEqual(len(payload["priorityActions"]), 2)
        self.assertTrue(all(not action["evidenceRefs"] for action in payload["priorityActions"]))
        self.assertEqual(payload["evidenceRefs"], [])
        self.assertIn("simc_or_wcl", payload["missingInputs"])
        self.assertLessEqual(payload["nextQuestion"].count("？") + payload["nextQuestion"].count("?"), 1)

    def test_chickenbro_pg_only_missing_spec_profile_store_degrades_without_sqlite(self):
        original_postgres_only = self.backend.postgres_only_runtime_enabled
        original_personal_store = self.backend.personal_data_store
        original_db_connection = self.backend.db_connection

        def sqlite_disabled_connection():
            raise RuntimeError("SQLite runtime is disabled; use PostgreSQL runtime stores or explicit migration tooling")

        self.backend.postgres_only_runtime_enabled = lambda: True
        self.backend.personal_data_store = lambda: None
        self.backend.db_connection = sqlite_disabled_connection
        try:
            bounded_context = self.backend.build_chickenbro_bounded_context(
                "冰法大秘境伤害低，先排查什么？",
                {"classKey": "mage", "specKey": "frost", "scenarioKey": "mythic_plus"},
            )
        finally:
            self.backend.postgres_only_runtime_enabled = original_postgres_only
            self.backend.personal_data_store = original_personal_store
            self.backend.db_connection = original_db_connection

        self.assertEqual(bounded_context["usableProfiles"], [])
        self.assertEqual(bounded_context["answerLayer"], "diagnostic")
        self.assertIn("simc_or_wcl", bounded_context["missingInputs"])

    def test_chickenbro_published_profile_uses_evidence_layer(self):
        self.seed_chickenbro_profile()

        def fake_codex_runner(prompt, **kwargs):
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
                        "limitations": [],
                    },
                    ensure_ascii=False,
                ),
            }

        result = self.backend.send_chickenbro_message(
            {
                "message": "奥法强韧大秘境怎么优化？",
                "guestId": "evidence-layer-device",
                "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
            },
            codex_runner=fake_codex_runner,
        )

        payload = result["assistantMessage"]["payload"]
        self.assertEqual(payload["answerLayer"], "evidence")
        self.assertEqual(payload["basisLabel"], "已基于你的模板或 SimC 分析")
        self.assertIn("profile.summary", payload["evidenceRefs"])
        self.assertIn("personal_simc_or_wcl", payload["missingInputs"])

    def test_chickenbro_builds_trimmed_evidence_packet_from_profile_and_context(self):
        self.seed_chickenbro_profile()

        bounded_context = self.backend.build_chickenbro_bounded_context(
            "奥法强韧大秘境帮我看下 SimC 数字。",
            {
                "classKey": "mage",
                "specKey": "arcane",
                "scenarioKey": "mplus_fortified",
                "savedTemplate": {
                    "templateId": "template-1",
                    "name": "强韧模板",
                    "rawString": "RAW_SIMC_PROFILE_SHOULD_NOT_LEAK",
                    "gearBySlot": {"head": {"rawItem": "RAW_ITEM_SHOULD_NOT_LEAK"}},
                    "gearCatalogRevision": "retail-12.0-s1",
                    "talentCatalogRevision": "retail-12.0-s1-talents",
                },
                "simcTask": {
                    "taskId": "simc-task-1",
                    "status": "completed",
                    "summary": "SimC run completed.",
                    "allowedNumbers": [{"key": "simc.dps", "value": "123456"}],
                    "evidenceRefs": ["simc.dps"],
                    "rawProfile": "RAW_PROFILE_SHOULD_NOT_LEAK",
                    "stdout": "RAW_SIMC_STDOUT_SHOULD_NOT_LEAK",
                },
                "wclTask": {
                    "reportCode": "abc123",
                    "fightId": "7",
                    "status": "ready",
                    "summary": "WCL fight parsed.",
                    "evidenceRefs": ["wcl.summary"],
                    "rawLog": "RAW_LOG_SHOULD_NOT_LEAK",
                    "token": "SECRET_TOKEN_SHOULD_NOT_LEAK",
                },
            },
        )

        packet = bounded_context["evidencePacket"]
        packet_json = json.dumps(packet, ensure_ascii=False)
        self.assertEqual(packet["schemaRevision"], "chickenbro-evidence-packet-v1")
        self.assertEqual(packet["profiles"][0]["runtimeProjection"]["summary"], "奥法在强韧大秘境里优先围绕大波次规划爆发。")
        self.assertEqual(packet["profiles"][0]["coachPack"]["priorityActions"][0]["evidenceRefs"], ["profile.summary"])
        self.assertEqual(packet["profiles"][0]["sourceCoverage"]["raiderio"]["sampleCount"], 80)
        self.assertEqual(packet["profiles"][0]["sampleWindow"]["region"], "cn")
        self.assertIn({"key": "sample.count", "value": "80"}, packet["profiles"][0]["allowedNumbers"])
        self.assertIn({"key": "simc.dps", "value": "123456"}, packet["contextEvidence"]["allowedNumbers"])
        self.assertIn("simc.dps", bounded_context["allowedEvidenceRefs"])
        self.assertIn("123456", bounded_context["allowedNumbers"])
        self.assertNotIn("RAW_SIMC_PROFILE_SHOULD_NOT_LEAK", packet_json)
        self.assertNotIn("RAW_PROFILE_SHOULD_NOT_LEAK", packet_json)
        self.assertNotIn("RAW_SIMC_STDOUT_SHOULD_NOT_LEAK", packet_json)
        self.assertNotIn("RAW_LOG_SHOULD_NOT_LEAK", packet_json)
        self.assertNotIn("SECRET_TOKEN_SHOULD_NOT_LEAK", packet_json)

    def test_chickenbro_context_evidence_can_authorize_numbers_without_profile(self):
        def fake_codex_runner(prompt, **kwargs):
            return {
                "status": "succeeded",
                "lastMessage": json.dumps(
                    {
                        "answer": "这次 SimC 结果是 123456 DPS，下一步先围绕 simc.dps 对照天赋和饰品。",
                        "confidence": "medium",
                        "answerLayer": "evidence",
                        "basisLabel": "已基于你的模板或 SimC 分析",
                        "priorityActions": [{"title": "先复核 SimC profile 的天赋和饰品。", "evidenceRefs": ["simc.dps"]}],
                        "evidenceRefs": ["simc.dps"],
                        "limitations": [],
                        "missingInputs": [],
                        "nextQuestion": "要不要补 WCL 让我对照实战？",
                    },
                    ensure_ascii=False,
                ),
            }

        result = self.backend.send_chickenbro_message(
            {
                "message": "冰DK这次 SimC 结果怎么样？",
                "guestId": "context-evidence-device",
                "context": {
                    "classKey": "deathknight",
                    "specKey": "frost",
                    "scenarioKey": "mplus_fortified",
                    "simcTask": {
                        "taskId": "simc-task-1",
                        "status": "completed",
                        "allowedNumbers": [{"key": "simc.dps", "value": "123456"}],
                        "evidenceRefs": ["simc.dps"],
                    },
                },
            },
            codex_runner=fake_codex_runner,
        )

        payload = result["assistantMessage"]["payload"]
        self.assertEqual(payload["answerLayer"], "evidence")
        self.assertEqual(payload["basisLabel"], "已基于你的模板或 SimC 分析")
        self.assertIn("123456", payload["answer"])
        self.assertIn("simc.dps", payload["evidenceRefs"])

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

    def test_chickenbro_default_runner_uses_codex_when_enabled(self):
        self.seed_chickenbro_profile()
        captured = {}
        previous_env = os.environ.get("WOW_CHICKENBRO_CODEX_ENABLED")
        previous_timeout = os.environ.get("WOW_CHICKENBRO_CODEX_TIMEOUT_SECONDS")
        previous_runner = self.backend.run_codex_job

        def fake_run_codex_job(prompt, **kwargs):
            captured["prompt"] = prompt
            captured["schema"] = kwargs.get("schema")
            captured["timeoutSeconds"] = kwargs.get("timeout_seconds")
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

        try:
            os.environ["WOW_CHICKENBRO_CODEX_ENABLED"] = "1"
            os.environ["WOW_CHICKENBRO_CODEX_TIMEOUT_SECONDS"] = "3"
            self.backend.run_codex_job = fake_run_codex_job
            result = self.backend.send_chickenbro_message(
                {
                    "message": "奥法强韧大秘境怎么优化？",
                    "guestId": "default-codex-device",
                    "context": {"classKey": "mage", "specKey": "arcane", "scenarioKey": "mplus_fortified"},
                },
            )
        finally:
            self.backend.run_codex_job = previous_runner
            if previous_env is None:
                os.environ.pop("WOW_CHICKENBRO_CODEX_ENABLED", None)
            else:
                os.environ["WOW_CHICKENBRO_CODEX_ENABLED"] = previous_env
            if previous_timeout is None:
                os.environ.pop("WOW_CHICKENBRO_CODEX_TIMEOUT_SECONDS", None)
            else:
                os.environ["WOW_CHICKENBRO_CODEX_TIMEOUT_SECONDS"] = previous_timeout

        self.assertIn("boundedContext", json.loads(captured["prompt"]))
        self.assertIs(captured["schema"]["additionalProperties"], False)
        self.assertEqual(captured["timeoutSeconds"], 3)
        self.assertEqual(result["assistantMessage"]["payload"]["answerSource"], "codex")
        self.assertEqual(result["job"]["result"]["codex"]["status"], "succeeded")

    def test_json_response_gzips_large_json_when_client_accepts_gzip(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/api/websim/bootstrap",
                headers={"Accept-Encoding": "gzip"},
            )
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.headers.get("Content-Encoding"), "gzip")
                body = gzip.decompress(response.read())
                self.assertIn(b"classes", body)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

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

    def test_pg_only_websim_profile_route_does_not_open_sqlite(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only websim profile must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only websim profile must not open SQLite"),
            ):
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/websim/profile",
                    data=json.dumps(
                        {
                            "classKey": "mage",
                            "specKey": "frost",
                            "talents": "C4DAAAAAAAAAAAAAAAAAAAAAAA",
                            "gear": [],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(response.status, 200)
        self.assertIn("talents=C4DA", payload["profile"])
        self.assertEqual(payload["profileReadiness"]["talentReady"], True)

    def test_pg_only_gear_resolve_route_preserves_result_envelope_http_statuses(self):
        store = object()
        calls = []

        def fake_resolve(payload, *, store, simc_runtime_revision, request_id):
            calls.append(
                {
                    "payload": payload,
                    "store": store,
                    "simcRuntimeRevision": simc_runtime_revision,
                    "requestId": request_id,
                }
            )
            http_status = payload["expectedHttpStatus"]
            status = "resolved" if http_status == 200 else ("unavailable" if http_status >= 500 else "blocked")
            return http_status, {
                "contractRevision": "gear-result-envelope-v1",
                "requestId": request_id,
                "status": status,
                "releaseContext": {"gearCatalogRevision": "gear-r18"},
                "data": {"echo": http_status},
                "problems": [] if http_status == 200 else [
                    {
                        "kind": "AUTHORITY_UNAVAILABLE" if http_status == 503 else "REVISION_CONFLICT",
                        "code": "TEST_PROBLEM",
                        "title": "test",
                        "detail": "",
                        "path": "",
                        "retryable": False,
                        "meta": {},
                    }
                ],
            }

        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(
                self.backend,
                "cache_data_store",
                return_value=store,
            ), patch.object(
                self.backend,
                "simc_version_status",
                return_value={"localTag": "simc-route-v1"},
            ), patch.object(
                self.backend,
                "resolve_selection_intent",
                side_effect=fake_resolve,
                create=True,
            ), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("canonical Resolve must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("canonical Resolve must not open SQLite"),
            ):
                for expected_status in (200, 400, 409, 503):
                    with self.subTest(httpStatus=expected_status):
                        request = Request(
                            f"http://127.0.0.1:{server.server_port}/api/websim/gear/resolve",
                            data=json.dumps({"expectedHttpStatus": expected_status}).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        try:
                            response = urlopen(request, timeout=5)
                        except HTTPError as error:
                            response = error
                        with response:
                            body = json.loads(response.read().decode("utf-8"))

                        self.assertEqual(response.status, expected_status)
                        self.assertEqual(body["contractRevision"], "gear-result-envelope-v1")
                        self.assertTrue(body["requestId"])
                        self.assertEqual(body["data"]["echo"], expected_status)
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(len(calls), 4)
        self.assertTrue(all(call["store"] is store for call in calls))
        self.assertTrue(all(call["simcRuntimeRevision"] == "simc-route-v1" for call in calls))
        self.assertEqual(len({call["requestId"] for call in calls}), 4)

    def test_pg_only_canonical_profile_route_re_resolves_and_preserves_503(self):
        store = object()
        calls = []
        request_payload = {
            "selectionIntent": {"schemaRevision": "selection-intent-v1"},
            "profileContext": {"talents": "external-code"},
        }

        def fake_profile(payload, *, store, simc_runtime_revision, request_id, profile_builder):
            calls.append(
                {
                    "payload": payload,
                    "store": store,
                    "simcRuntimeRevision": simc_runtime_revision,
                    "requestId": request_id,
                    "profileBuilder": profile_builder,
                }
            )
            return 503, {
                "contractRevision": "gear-result-envelope-v1",
                "requestId": request_id,
                "status": "unavailable",
                "releaseContext": {},
                "data": {},
                "problems": [
                    {
                        "kind": "AUTHORITY_UNAVAILABLE",
                        "code": "GEAR_AUTHORITY_READ_UNAVAILABLE",
                        "title": "authority unavailable",
                        "detail": "",
                        "path": "",
                        "retryable": True,
                        "meta": {},
                    }
                ],
            }

        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(
                self.backend,
                "cache_data_store",
                return_value=store,
            ), patch.object(
                self.backend,
                "simc_version_status",
                return_value={"simcRuntimeRevision": "simc-profile-v1"},
            ), patch.object(
                self.backend,
                "is_canonical_profile_request",
                return_value=True,
                create=True,
            ), patch.object(
                self.backend,
                "build_profile_from_selection_intent",
                side_effect=fake_profile,
                create=True,
            ), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("canonical profile must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("canonical profile must not open SQLite"),
            ):
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/websim/profile",
                    data=json.dumps(request_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=5)
                response = raised.exception
                body = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(response.code, 503)
        self.assertEqual(body["contractRevision"], "gear-result-envelope-v1")
        self.assertEqual(body["status"], "unavailable")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["payload"], request_payload)
        self.assertIs(calls[0]["store"], store)
        self.assertEqual(calls[0]["simcRuntimeRevision"], "simc-profile-v1")
        self.assertIs(calls[0]["profileBuilder"], self.backend.build_websim_profile_response_from_resolved_snapshot)

    def test_pg_only_websim_gear_stats_route_returns_blocked_without_sqlite(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only gear stats must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only gear stats must not open SQLite"),
            ):
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/websim/gear/stats",
                    data=json.dumps(
                        {
                            "classKey": "mage",
                            "specKey": "frost",
                            "talents": "C4DAAAAAAAAAAAAAAAAAAAAAAA",
                            "gear": [],
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["statStatus"], "blocked")
        self.assertIn("selected gear is not fully SimC-ready", payload["blockers"])

    def test_pg_only_public_builds_and_pve_routes_do_not_open_sqlite(self):
        class CacheStore:
            def get_raiderio_payload(self):
                return {
                    "sourceStatus": "blocked",
                    "status": "blocked",
                    "errors": ["PG Raider.IO fixture"],
                }

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "cache_data_store", return_value=CacheStore()), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only public routes must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only public routes must not open SQLite"),
        ):
            builds_home = self.backend.get_builds_home_payload()
            builds_intel = self.backend.get_builds_intel_payload()
            builds_detail = self.backend.get_builds_detail_payload("mage-arcane")
            pve_home = self.backend.get_pve_home_payload()
            pve_module = self.backend.get_pve_module_payload("teamLadder")

        self.assertIsInstance(builds_home, dict)
        self.assertIsInstance(builds_intel, dict)
        self.assertIsInstance(pve_home, dict)
        self.assertIsInstance(pve_module, dict)
        for payload in (builds_home, builds_intel, pve_home, pve_module):
            self.assertNotIn("raiderioError", payload)
        if builds_detail:
            self.assertIn("gearMetadataError", builds_detail)
            self.assertIn("PostgreSQL", builds_detail["gearMetadataError"])

    def test_pg_only_websim_bootstrap_and_assets_routes_do_not_open_sqlite(self):
        class CacheStore:
            def get_websim_bootstrap(self):
                return {
                    "navTitle": "WebSim",
                    "title": "SimC 构筑工坊",
                    "dataStatus": "verified",
                    "instances": [],
                    "syncState": {"ok": True},
                }

        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(self.backend, "cache_data_store", return_value=CacheStore()), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only WebSim GET routes must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only WebSim GET routes must not open SQLite"),
            ):
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/websim/bootstrap", timeout=5) as response:
                    bootstrap = json.loads(response.read().decode("utf-8"))
                    bootstrap_status = response.status
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/websim/assets", timeout=5) as response:
                    assets = json.loads(response.read().decode("utf-8"))
                    assets_status = response.status
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(bootstrap_status, 200)
        self.assertEqual(bootstrap["navTitle"], "WebSim")
        self.assertEqual(assets_status, 200)
        self.assertEqual(assets["assets"], [])
        self.assertEqual(assets["status"], "blocked")
        self.assertIn("PostgreSQL WebSim asset registry is not available", assets["blockers"])

    def test_pg_only_talent_mutation_routes_do_not_open_sqlite(self):
        class CacheStore:
            def get_websim_talents(self, class_key="mage", spec_key="arcane", hero_key=""):
                return {
                    "classKey": class_key,
                    "specKey": spec_key,
                    "heroKey": hero_key,
                    "talentStatus": "verified",
                    "nodes": [],
                    "talentAuthority": {"runtime": {"status": "verified"}},
                    "talentReadiness": {"status": "verified", "blockers": []},
                    "blockers": [],
                }

        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(self.backend, "cache_data_store", return_value=CacheStore()), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only talent routes must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only talent routes must not open SQLite"),
            ):
                payloads = {}
                for route in ("validate", "export", "import"):
                    request = Request(
                        f"http://127.0.0.1:{server.server_port}/api/talents/{route}",
                        data=json.dumps(
                            {
                                "classKey": "mage",
                                "specKey": "frost",
                                "talents": "C4DAAAAAAAAAAAAAAAAAAAAAAA",
                            }
                        ).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urlopen(request, timeout=5) as response:
                        payloads[route] = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(payloads["validate"]["status"], "external")
        self.assertEqual(payloads["export"]["validation"]["status"], "external")
        self.assertEqual(payloads["import"]["validation"]["status"], "external")

    def test_pg_only_stat_weight_latest_route_do_not_open_sqlite(self):
        test_case = self

        class CacheStore:
            def get_sync_state(self, key):
                test_case.assertEqual(key, "stat_weights_sync")
                return {
                    "sourceStatus": "blocked",
                    "status": "blocked",
                    "checkedAt": "2026-07-03T00:00:00+00:00",
                    "errors": ["PG stat weight fixture"],
                }

        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(self.backend, "cache_data_store", return_value=CacheStore()), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only stat weights must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only stat weights must not open SQLite"),
            ):
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/api/builds/stat-weights/refresh-runs/latest",
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    status = response.status
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(status, 200)
        self.assertEqual(payload["sourceStatus"], "blocked")
        self.assertIn("PG stat weight fixture", payload["errors"])

    def test_pg_only_websim_simulate_route_do_not_open_sqlite(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only simulate must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only simulate must not open SQLite"),
            ):
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/websim/simulate",
                    data=json.dumps(
                        {
                            "classKey": "mage",
                            "specKey": "frost",
                            "talents": "C4DAAAAAAAAAAAAAAAAAAAAAAA",
                            "gear": [],
                            "saveTask": False,
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    status = response.status
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["talentEncoding"]["status"], "external")

    def test_pg_only_news_routes_return_blocked_without_sqlite_when_content_store_missing(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(
                os.environ,
                {
                    "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                    "WOW_DATABASE_RUNTIME": "postgres_only",
                },
            ), patch.object(self.backend, "content_data_store", return_value=None), patch.object(
                self.backend,
                "init_db",
                side_effect=AssertionError("PG-only news routes must not initialize SQLite"),
            ), patch.object(
                self.backend,
                "db_connection",
                side_effect=AssertionError("PG-only news routes must not open SQLite"),
            ):
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/news/home", timeout=5) as response:
                    home = json.loads(response.read().decode("utf-8"))
                    home_status = response.status
                with urlopen(
                    f"http://127.0.0.1:{server.server_port}/api/news/refresh-runs/latest",
                    timeout=5,
                ) as response:
                    latest = json.loads(response.read().decode("utf-8"))
                    latest_status = response.status
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(home_status, 200)
        self.assertEqual(home["dataStatus"], "blocked")
        self.assertIn("PostgreSQL content store is not available", home["errors"])
        self.assertEqual(latest_status, 200)
        self.assertEqual(latest["dataStatus"], "blocked")

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

            with patch.object(self.backend, "refresh_articles", return_value={}) as refresh, patch.object(
                self.backend,
                "build_home_payload",
                return_value={"heroNews": [], "highlights": []},
            ):
                request = Request(f"{base_url}?mode=scheduled&scope=queue&limit=1", data=b"", method="POST")
                with urlopen(request, timeout=5) as response:
                    json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 200)
                refresh.assert_called_once_with(
                    "scheduled",
                    collector_enabled=False,
                    seed_enabled=False,
                    queue_enabled=True,
                    process_limit_override=1,
                )
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

    def test_admin_gates_summary_requires_token_and_uses_health_components(self):
        os.environ["WOW_ADMIN_TOKEN"] = "admin-token"
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.backend.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/admin/gates/summary"
            with self.assertRaises(HTTPError) as raised:
                urlopen(url, timeout=5)
            self.assertEqual(raised.exception.code, 401)

            request = Request(url, headers={"Authorization": "Bearer admin-token"})
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            os.environ.pop("WOW_ADMIN_TOKEN", None)

        self.assertEqual(response.status, 200)
        self.assertEqual(payload["schemaRevision"], "admin-gates-summary-v1")
        self.assertEqual(payload["productRule"]["systemGate"], "consumption_fact")
        self.assertEqual(payload["productRule"]["humanJudgement"], "diagnostic_fact")
        self.assertTrue(any(item["key"] == "news" for item in payload["modules"]))
        self.assertTrue(any(item["key"] == "gear_catalog" for item in payload["modules"]))
        self.assertIn("blocked", payload["statusCounts"])
        self.assertIn("diagnosticQueue", payload)
        self.assertEqual(payload["statusLabels"]["blocked"], "已阻断")
        queue_nav = next(item for item in payload["navigation"] if item["key"] == "queue")
        self.assertEqual(queue_nav["label"], "待诊断阻断项")
        modules_by_key = {item["key"]: item for item in payload["modules"]}
        self.assertEqual(modules_by_key["backend"]["title"], "后端服务")
        self.assertEqual(modules_by_key["news"]["title"], "新闻发布门禁")
        self.assertEqual(modules_by_key["websim_sync"]["title"], "WebSim 同步状态")
        self.assertEqual(modules_by_key["wcl_credentials"]["title"], "Warcraft Logs API 凭据")
        self.assertIn("Warcraft Logs API 凭据未配置", " / ".join(modules_by_key["wcl_credentials"]["blockers"]))
        self.assertNotIn("Warcraft Logs API credentials are not configured", json.dumps(payload["modules"], ensure_ascii=False))

    def test_admin_token_authorization_is_fixed_env_secret_without_expiry(self):
        os.environ["WOW_ADMIN_TOKEN"] = "fixed-admin-token"
        try:
            self.assertTrue(
                self.backend.admin_authorized({"Authorization": "Bearer fixed-admin-token"})
            )
            with patch.object(self.backend, "utc_now", return_value="2099-01-01T00:00:00+00:00"):
                self.assertTrue(
                    self.backend.admin_authorized({"Authorization": "Bearer fixed-admin-token"})
                )
        finally:
            os.environ.pop("WOW_ADMIN_TOKEN", None)

    def test_admin_gates_summary_uses_lightweight_health_without_full_template_audit(self):
        with patch.object(
            self.backend,
            "template_evidence_audit_payload",
            return_value={"schemaRevision": "template-evidence-audit-v1", "fullMatrix": "unexpected"},
        ) as full_audit:
            payload = self.backend.admin_gate_summary_payload()

        full_audit.assert_not_called()
        self.assertEqual(payload["schemaRevision"], "admin-gates-summary-v1")
        self.assertTrue(any(item["key"] == "community_templates" for item in payload["modules"]))

    def test_admin_gate_summary_uses_lightweight_queue_summary(self):
        with patch.object(
            self.backend,
            "admin_gate_queue_payload",
            side_effect=AssertionError("summary must not build full queue"),
        ):
            payload = self.backend.admin_gate_summary_payload()

        self.assertIn("queueSummary", payload)
        self.assertNotIn("items", payload["queueSummary"])

    def test_admin_gate_summary_prefers_runtime_lightweight_queue_summary(self):
        class ContentStore:
            def admin_gate_queue_summary(self):
                return {
                    "count": 2,
                    "domainCounts": {"news": 2},
                    "topBlockers": [{"reason": "news blocked", "count": 2}],
                }

        class CacheStore:
            def admin_gate_queue_summary(self):
                return {
                    "count": 3,
                    "domainCounts": {"gear": 3},
                    "topBlockers": [{"reason": "gear blocked", "count": 3}],
                }

            def admin_gate_gear_records(self):
                raise AssertionError("summary must not build full gear records")

        with patch.object(
            self.backend,
            "build_data_health_payload",
            return_value={"components": []},
        ), patch.object(self.backend, "content_data_store", return_value=ContentStore()), \
             patch.object(self.backend, "cache_data_store", return_value=CacheStore()):
            payload = self.backend.admin_gate_summary_payload()

        self.assertEqual(payload["queueSummary"]["count"], 5)
        self.assertEqual(payload["queueSummary"]["domainCounts"], {"news": 2, "gear": 3})
        self.assertEqual(payload["queueSummary"]["topBlockers"][0]["reason"], "gear blocked")

    def test_admin_gate_queue_without_domain_stops_after_limit(self):
        calls = []

        def fake_collect(query):
            domain = (query or {}).get("domain", [""])[0]
            calls.append(domain)
            if not domain:
                raise AssertionError("queue must load domains incrementally")
            if domain != "news":
                raise AssertionError(f"queue should stop before loading {domain}")
            return [
                self.backend.admin_gate_record(
                    "news",
                    "news_discovery_queue",
                    f"news-{index}",
                    f"News {index}",
                    status="blocked",
                    source_status="blocked",
                    blockers=["blocked"],
                )
                for index in range(120)
            ]

        with patch.object(self.backend, "collect_admin_gate_records_from_runtime_stores", side_effect=fake_collect), \
             patch.object(self.backend, "ops_data_store", return_value=None):
            payload = self.backend.admin_gate_queue_payload({"limit": ["80"]})

        self.assertEqual(len(payload["items"]), 80)
        self.assertEqual(calls, ["news"])

    def test_admin_gates_records_are_full_record_level_read_only_and_redacted(self):
        with self.backend.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO news_raw_articles (
                    id, source_id, source_name, source_tier, canonical_url,
                    original_title, original_summary, original_body, body_blocks_json,
                    published_at, fetched_at, fetch_error, license_status,
                    verification_status, canonical_topic_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "raw-1",
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "https://example.com/raw",
                    "Arms Warrior Tuning",
                    "Short summary",
                    "Full internal body with Bearer secret-token and private payload",
                    json.dumps([{"type": "paragraph", "text": "Full internal body"}]),
                    "2026-06-29",
                    "2026-06-29T00:00:00+00:00",
                    "",
                    "approved",
                    "official_verified",
                    "topic-1",
                ),
            )
            conn.execute(
                """
                INSERT INTO news_discovery_queue (
                    id, canonical_topic_id, source_id, source_name, source_tier,
                    source_url, original_title, published_at, status, attempts,
                    last_error, payload_json, discovered_at, updated_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "queue-1",
                    "topic-1",
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "https://example.com/raw",
                    "Arms Warrior Tuning",
                    "2026-06-29",
                    "blocked",
                    1,
                    "invalid_llm_translation",
                    json.dumps(
                        {
                            "rawBody": "Full internal body with Bearer secret-token",
                            "channel": "职业强度变化",
                            "category": "正式服",
                            "tags": ["class-change"],
                        }
                    ),
                    "2026-06-29T00:00:00+00:00",
                    "2026-06-29T00:01:00+00:00",
                    "",
                ),
            )
            conn.execute(
                """
                INSERT INTO news_discovery_queue (
                    id, canonical_topic_id, source_id, source_name, source_tier,
                    source_url, original_title, published_at, status, attempts,
                    last_error, payload_json, discovered_at, updated_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "queue-duplicate",
                    "topic-duplicate",
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "https://example.com/duplicate",
                    "Existing Hotfix",
                    "2026-06-29",
                    "blocked",
                    0,
                    "duplicate_seed_source_translation",
                    json.dumps({"channel": "正式服动态", "category": "正式服"}),
                    "2026-06-29T00:00:00+00:00",
                    "2026-06-29T00:02:00+00:00",
                    "",
                ),
            )
            conn.execute(
                """
                INSERT INTO news_discovery_queue (
                    id, canonical_topic_id, source_id, source_name, source_tier,
                    source_url, original_title, published_at, status, attempts,
                    last_error, payload_json, discovered_at, updated_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "queue-published",
                    "topic-published",
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "https://example.com/published",
                    "Published Hotfix",
                    "2026-06-28T08:00:00+00:00",
                    "published",
                    1,
                    "",
                    json.dumps({"channel": "测试服前瞻", "category": "测试服", "tags": ["ptr"]}),
                    "2026-06-28T07:55:00+00:00",
                    "2026-06-28T08:01:00+00:00",
                    "2026-06-28T08:00:30+00:00",
                ),
            )
            conn.commit()

        with patch.object(self.backend, "refresh_articles", side_effect=AssertionError("admin records must be read-only")):
            payload = self.backend.admin_gate_records_payload({"domain": ["news"], "limit": ["20"]})
            category_filtered = self.backend.admin_gate_records_payload(
                {"domain": ["news"], "field": ["category"], "q": ["正式服动态"], "limit": ["20"]}
            )
            publication_filtered = self.backend.admin_gate_records_payload(
                {"domain": ["news"], "field": ["publication"], "q": ["未发布"], "limit": ["20"]}
            )
            status_filtered = self.backend.admin_gate_records_payload(
                {"domain": ["news"], "status": ["blocked"], "limit": ["20"]}
            )

        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["schemaRevision"], "admin-gates-records-v1")
        self.assertEqual(payload["records"][0]["domain"], "news")
        self.assertEqual(payload["records"][0]["status"], "blocked")
        self.assertIn("Arms Warrior Tuning", rendered)
        self.assertIn("https://example.com/raw", rendered)
        blocker_titles = [
            detail["title"]
            for record in payload["records"]
            for detail in record.get("blockerDetails", [])
        ]
        self.assertIn("LLM 翻译未通过校验", blocker_titles)
        self.assertIn("已存在同源译文，阻止重复发布", blocker_titles)
        self.assertNotIn("secret-token", rendered)
        self.assertNotIn("Full internal body", rendered)
        records_by_id = {record["targetId"]: record for record in payload["records"]}
        self.assertEqual(records_by_id["queue-1"]["articleCategory"]["label"], "职业强度变化")
        self.assertEqual(records_by_id["queue-1"]["articleCategory"]["channel"], "职业强度变化")
        self.assertEqual(records_by_id["queue-1"]["articleCategory"]["category"], "正式服")
        self.assertEqual(records_by_id["queue-duplicate"]["articleCategory"]["label"], "正式服动态")
        self.assertEqual(records_by_id["queue-published"]["articleCategory"]["label"], "测试服前瞻")
        self.assertEqual(records_by_id["queue-published"]["publication"]["state"], "published")
        self.assertEqual(records_by_id["queue-published"]["publication"]["stateLabel"], "已发布")
        self.assertEqual(records_by_id["queue-published"]["publication"]["publishedAt"], "2026-06-28T08:00:00+00:00")
        self.assertEqual(records_by_id["queue-1"]["publication"]["state"], "unpublished")
        self.assertEqual(records_by_id["queue-1"]["publication"]["stateLabel"], "未发布")
        self.assertEqual(records_by_id["queue-1"]["publication"]["capturedAt"], "2026-06-29T00:00:00+00:00")
        self.assertEqual(records_by_id["queue-1"]["publication"]["unpublishedReason"], "invalid_llm_translation")
        self.assertEqual([record["targetId"] for record in category_filtered["records"]], ["queue-duplicate"])
        self.assertEqual(
            {record["targetId"] for record in publication_filtered["records"]},
            {"queue-1", "queue-duplicate"},
        )
        self.assertEqual(
            {record["targetId"] for record in status_filtered["records"]},
            {"queue-1", "queue-duplicate"},
        )

    def test_admin_gates_records_filter_sqlite_gear_source_instance(self):
        with self.backend.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO websim_items (
                    id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "item-skyreach-head",
                    "Skyreach Hood",
                    "head",
                    "epic",
                    "",
                    json.dumps({
                        "classes": ["mage"],
                        "item_class": {"id": 4, "name": "Armor"},
                        "item_subclass": {"id": 1, "name": "Cloth"},
                    }),
                    "2026-06-30T00:00:00+00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_sources (
                    id, item_id, source_type, source_label, instance_id, encounter_id,
                    difficulty_key, season_revision, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "source-skyreach-head",
                    "item-skyreach-head",
                    "dungeon",
                    "Ranjit - Skyreach",
                    "1208",
                    "encounter-ranjit",
                    "mythic",
                    "midnight-s3",
                    "{}",
                    "2026-06-30T00:01:00+00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants (
                    id, item_id, slot, variant_key, label, source_type, difficulty_key,
                    item_level, simc_options_json, status, blockers_json, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "variant-skyreach-head",
                    "item-skyreach-head",
                    "head",
                    "mythic",
                    "Mythic",
                    "dungeon",
                    "mythic",
                    678,
                    "{}",
                    "verified",
                    "[]",
                    json.dumps({"classes": ["mage"]}),
                    "2026-06-30T00:02:00+00:00",
                ),
            )
            conn.commit()

        payload = self.backend.admin_gate_records_payload(
            {"domain": ["gear"], "field": ["sourceInstance"], "q": ["通天峰"], "limit": ["20"]}
        )

        self.assertEqual([record["targetId"] for record in payload["records"]], ["variant-skyreach-head"])
        category = payload["records"][0]["gearCategory"]
        self.assertEqual(category["sourceInstanceId"], "1208")
        self.assertEqual(category["sourceInstanceLabel"], "Skyreach")
        self.assertIn("通天峰", category["sourceInstanceAliases"])
        self.assertEqual(category["itemTypeLabel"], "布甲")
        self.assertEqual(category["itemTypeGroupLabel"], "护甲类型")

        item_type_payload = self.backend.admin_gate_records_payload(
            {"domain": ["gear"], "field": ["itemType"], "q": ["布甲"], "limit": ["20"]}
        )
        self.assertEqual([record["targetId"] for record in item_type_payload["records"]], ["variant-skyreach-head"])

    def test_admin_gates_records_gear_prefers_verified_variant_over_partial_placeholder(self):
        class FakeCacheStore:
            def admin_gate_gear_records(self):
                return {
                    "communityGearTemplates": [],
                    "gearVariants": [
                        {
                            "id": "shield-placeholder",
                            "itemId": "251105",
                            "itemName": "破法者之盾",
                            "slot": "off_hand",
                            "label": "needs-variant",
                            "sourceType": "dungeon",
                            "sourceLabel": "Selin Fireheart - Magisters' Terrace",
                            "sourceInstanceId": "585",
                            "sourceInstanceLabel": "Magisters' Terrace",
                            "difficultyKey": "needs-variant",
                            "itemLevel": 0,
                            "status": "partial",
                            "blockers": ["missing deterministic SimC variant preset"],
                            "payload": {},
                            "itemPayload": {
                                "item_class": {"id": 4, "name": "Armor"},
                                "item_subclass": {"id": 6, "name": "Shield"},
                            },
                            "updatedAt": "2026-06-30T08:00:00+00:00",
                        },
                        {
                            "id": "shield-champion",
                            "itemId": "251105",
                            "itemName": "破法者之盾",
                            "slot": "off_hand",
                            "label": "勇士",
                            "sourceType": "dungeon",
                            "sourceLabel": "Selin Fireheart - Magisters' Terrace",
                            "sourceInstanceId": "585",
                            "sourceInstanceLabel": "Magisters' Terrace",
                            "difficultyKey": "champion",
                            "itemLevel": 263,
                            "status": "verified",
                            "blockers": [],
                            "simcOptions": {"bonus_id": "1111"},
                            "payload": {},
                            "itemPayload": {
                                "item_class": {"id": 4, "name": "Armor"},
                                "item_subclass": {"id": 6, "name": "Shield"},
                            },
                            "updatedAt": "2026-06-29T06:00:00+00:00",
                        },
                        {
                            "id": "shield-hero",
                            "itemId": "251105",
                            "itemName": "破法者之盾",
                            "slot": "off_hand",
                            "label": "英雄",
                            "sourceType": "dungeon",
                            "sourceLabel": "Selin Fireheart - Magisters' Terrace",
                            "sourceInstanceId": "585",
                            "sourceInstanceLabel": "Magisters' Terrace",
                            "difficultyKey": "hero",
                            "itemLevel": 276,
                            "status": "verified",
                            "blockers": [],
                            "simcOptions": {"bonus_id": "2222"},
                            "payload": {},
                            "itemPayload": {
                                "item_class": {"id": 4, "name": "Armor"},
                                "item_subclass": {"id": 6, "name": "Shield"},
                            },
                            "updatedAt": "2026-06-29T07:00:00+00:00",
                        },
                        {
                            "id": "shield-mythic",
                            "itemId": "251105",
                            "itemName": "破法者之盾",
                            "slot": "off_hand",
                            "label": "神话",
                            "sourceType": "dungeon",
                            "sourceLabel": "Selin Fireheart - Magisters' Terrace",
                            "sourceInstanceId": "585",
                            "sourceInstanceLabel": "Magisters' Terrace",
                            "difficultyKey": "myth",
                            "itemLevel": 289,
                            "status": "verified",
                            "blockers": [],
                            "simcOptions": {"bonus_id": "1234"},
                            "payload": {},
                            "itemPayload": {
                                "item_class": {"id": 4, "name": "Armor"},
                                "item_subclass": {"id": 6, "name": "Shield"},
                            },
                            "updatedAt": "2026-06-29T08:00:00+00:00",
                        },
                    ],
                }

        with patch.object(self.backend, "cache_data_store", return_value=FakeCacheStore()):
            name_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["gearName"], "q": ["破法者之盾"], "limit": ["20"]}
            )
            instance_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["sourceInstance"], "q": ["魔导师平台"], "limit": ["20"]}
            )

        self.assertEqual(name_payload["totalCount"], 1)
        record = name_payload["records"][0]
        self.assertEqual(record["targetId"], "shield-mythic")
        self.assertEqual(record["status"], "verified")
        self.assertEqual(record["gearVisibility"]["state"], "visible")
        self.assertEqual(record["gearBlockReason"]["state"], "clear")
        self.assertEqual(record["gearCategory"]["variantLabel"], "神话")
        self.assertEqual(record["gearCategory"]["itemLevel"], 289)
        self.assertEqual(record["rawSummary"]["variantCount"], 4)
        self.assertEqual(record["rawSummary"]["verifiedVariantCount"], 3)
        self.assertEqual(record["rawSummary"]["blockedOrPartialVariantCount"], 1)
        self.assertEqual(
            [variant["itemLevel"] for variant in record["gearCategory"]["variants"]],
            [289, 276, 263],
        )
        self.assertEqual(
            [variant["label"] for variant in record["gearCategory"]["variants"]],
            ["神话", "英雄", "勇士"],
        )
        self.assertNotIn("missing deterministic SimC variant preset", json.dumps(record, ensure_ascii=False))
        self.assertEqual([item["targetId"] for item in instance_payload["records"]], ["shield-mythic"])

    def test_admin_gate_gear_variant_display_rows_dedupes_observed_item_levels(self):
        rows = self.backend.admin_gate_gear_variant_display_rows([
            {
                "id": "observed-289-a",
                "label": "Observed 289",
                "difficultyKey": "observed_profile",
                "itemLevel": 289,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "1111"},
                "updatedAt": "2026-07-01T01:00:00+00:00",
            },
            {
                "id": "observed-289-b",
                "label": "Observed 289",
                "difficultyKey": "observed_profile",
                "itemLevel": 289,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "2222"},
                "updatedAt": "2026-07-01T01:01:00+00:00",
            },
            {
                "id": "myth-289",
                "label": "神话 289",
                "difficultyKey": "myth",
                "itemLevel": 289,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "3333"},
                "updatedAt": "2026-06-30T01:00:00+00:00",
            },
            {
                "id": "observed-298",
                "label": "Observed 298",
                "difficultyKey": "observed_profile",
                "itemLevel": 298,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "4444"},
                "updatedAt": "2026-07-01T01:02:00+00:00",
            },
            {
                "id": "void-298",
                "label": "虚空晋升 298",
                "difficultyKey": "void_upgrade",
                "itemLevel": 298,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "5555"},
                "updatedAt": "2026-06-30T01:01:00+00:00",
            },
            {
                "id": "hero-276",
                "label": "英雄 276",
                "difficultyKey": "hero",
                "itemLevel": 276,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "6666"},
                "updatedAt": "2026-06-30T01:02:00+00:00",
            },
        ])

        self.assertEqual(
            [(row["label"], row["difficultyKey"], row["itemLevel"]) for row in rows],
            [("虚空晋升", "void_upgrade", 298), ("神话", "myth", 289), ("英雄", "hero", 276)],
        )
        self.assertNotIn("Observed", json.dumps(rows, ensure_ascii=False))

    def test_admin_gate_gear_variant_display_rows_prefers_verified_over_partial_label(self):
        rows = self.backend.admin_gate_gear_variant_display_rows([
            {
                "id": "partial-named-289",
                "label": "神话 289",
                "difficultyKey": "myth",
                "itemLevel": 289,
                "status": "partial",
                "blockers": ["missing deterministic SimC variant preset"],
                "updatedAt": "2026-07-01T02:00:00+00:00",
            },
            {
                "id": "observed-verified-289",
                "label": "Observed 289",
                "difficultyKey": "observed_profile",
                "itemLevel": 289,
                "status": "verified",
                "blockers": [],
                "simcOptions": {"bonus_id": "1111"},
                "updatedAt": "2026-07-01T01:00:00+00:00",
            },
        ])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "verified")
        self.assertEqual(rows[0]["difficultyKey"], "observed_profile")
        self.assertEqual(rows[0]["itemLevel"], 289)
        self.assertEqual(rows[0]["label"], "")

    def test_admin_gates_records_sqlite_source_instance_filter_uses_all_variants_before_limit(self):
        with self.backend.db_connection() as conn:
            conn.executemany(
                """
                INSERT INTO websim_items (
                    id, name, slot, quality, icon_url, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"noise-item-{index}",
                        f"Noise Item {index}",
                        "head",
                        "epic",
                        "",
                        "{}",
                        f"2026-06-30T09:{index % 60:02d}:00+00:00",
                    )
                    for index in range(501)
                ]
                + [
                    (
                        "251105",
                        "破法者之盾",
                        "off_hand",
                        "epic",
                        "",
                        json.dumps({
                            "item_class": {"id": 4, "name": "Armor"},
                            "item_subclass": {"id": 6, "name": "Shield"},
                        }),
                        "2026-06-29T00:00:00+00:00",
                    )
                ],
            )
            conn.executemany(
                """
                INSERT INTO websim_gear_sources (
                    id, item_id, source_type, source_label, instance_id, encounter_id,
                    difficulty_key, season_revision, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"noise-source-{index}",
                        f"noise-item-{index}",
                        "dungeon",
                        "Ranjit - Skyreach",
                        "1208",
                        "encounter-ranjit",
                        "mythic",
                        "midnight-s3",
                        "{}",
                        f"2026-06-30T09:{index % 60:02d}:30+00:00",
                    )
                    for index in range(501)
                ]
                + [
                    (
                        "source-shield-magisters",
                        "251105",
                        "dungeon",
                        "Selin Fireheart - Magisters' Terrace",
                        "585",
                        "encounter-selin",
                        "myth",
                        "midnight-s3",
                        "{}",
                        "2026-06-29T00:00:30+00:00",
                    )
                ],
            )
            conn.executemany(
                """
                INSERT INTO websim_gear_variants (
                    id, item_id, slot, variant_key, label, source_type, difficulty_key,
                    item_level, simc_options_json, status, blockers_json, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"noise-variant-{index}",
                        f"noise-item-{index}",
                        "head",
                        "mythic",
                        "Mythic",
                        "dungeon",
                        "mythic",
                        678,
                        json.dumps({"bonus_id": str(9000 + index)}),
                        "verified",
                        "[]",
                        "{}",
                        f"2026-06-30T10:{index % 60:02d}:00+00:00",
                    )
                    for index in range(501)
                ]
                + [
                    (
                        "shield-mythic",
                        "251105",
                        "off_hand",
                        "myth",
                        "神话",
                        "dungeon",
                        "myth",
                        289,
                        json.dumps({"bonus_id": "1234"}),
                        "verified",
                        "[]",
                        "{}",
                        "2026-06-29T00:01:00+00:00",
                    )
                ],
            )
            conn.commit()

        payload = self.backend.admin_gate_records_payload(
            {"domain": ["gear"], "field": ["sourceInstance"], "q": ["魔导师平台"], "limit": ["20"]}
        )

        self.assertEqual([record["targetId"] for record in payload["records"]], ["shield-mythic"])
        self.assertEqual(payload["records"][0]["gearVisibility"]["state"], "visible")

    def test_admin_gates_records_use_postgres_runtime_stores_when_available(self):
        class FakeContentStore:
            def admin_gate_news_records(self):
                return {
                    "discoveryQueue": [],
                    "articles": [
                        {
                            "id": "pg-news-1",
                            "title": "PG article",
                            "sourceName": "Blizzard News",
                            "sourceUrl": "https://example.com/pg-news",
                            "channel": "职业强度变化",
                            "category": "正式服",
                            "publishedAt": "2026-06-30T00:00:00+00:00",
                            "updatedAt": "2026-06-30T00:01:00+00:00",
                            "contentStatus": "ready",
                            "translationStatus": "llm",
                            "licenseStatus": "approved",
                            "verificationStatus": "official_verified",
                            "translationFidelity": "source_translation",
                            "blockedReason": "",
                        }
                    ],
                }

        class FakeCacheStore:
            def admin_gate_talent_records(self):
                return {
                    "communityTalentTemplates": [
                        {
                            "id": "pg-template-1",
                            "classKey": "mage",
                            "specKey": "frost",
                            "heroKey": "spellslinger",
                            "scenarioKey": "mythic_plus",
                            "name": "PG talent template",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/pg-template",
                            "sourceStatus": "verified",
                            "status": "verified",
                            "sampleCount": 12,
                            "maxKeyLevel": 10,
                            "analysisWindow": "2026-W27",
                            "payload": {
                                "evidenceTier": "wcl_character_supported",
                                "qualityScore": 74,
                                "promotionReason": "WCL character-supported evidence; promoted into active community talent inventory",
                                "rioEvidence": {"maxKeyLevel": 24, "sampleCount": 12},
                                "wclEvidence": {"tier": "wcl_character_supported", "reportCount": 2},
                            },
                            "updatedAt": "2026-06-30T00:02:00+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-pg-template",
                            "sourceRefs": [{"type": "raiderio"}],
                            "scanRunId": "scan-pg",
                        },
                        {
                            "id": "pg-template-blocked",
                            "classKey": "warlock",
                            "specKey": "demonology",
                            "heroKey": "soul_harvester",
                            "scenarioKey": "mythic_plus",
                            "name": "Blocked talent template",
                            "sourceKey": "wcl",
                            "sourceName": "Warcraft Logs",
                            "sourceUrl": "https://example.com/blocked-template",
                            "sourceStatus": "blocked",
                            "status": "blocked",
                            "sampleCount": 0,
                            "maxKeyLevel": 0,
                            "analysisWindow": "2026-W27",
                            "payload": {"blockers": ["invalid_talent_template"]},
                            "updatedAt": "2026-06-30T00:02:30+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-blocked-template",
                            "sourceRefs": [{"type": "wcl"}],
                            "scanRunId": "scan-pg",
                        }
                    ],
                    "talentTrees": [
                        {
                            "classKey": "mage",
                            "specKey": "frost",
                            "nodeCount": 110,
                            "updatedAt": "2026-06-30T00:03:00+00:00",
                        }
                    ],
                }

            def admin_gate_gear_records(self):
                return {
                    "communityGearTemplates": [
                        {
                            "id": "pg-gear-template-1",
                            "classKey": "warrior",
                            "specKey": "arms",
                            "name": "PG gear template",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/pg-gear-template",
                            "sourceStatus": "blocked",
                            "status": "blocked",
                            "readySlotCount": 4,
                            "missingSlots": ["off_hand"],
                            "analysisWindow": "2026-W27",
                            "payload": {"blockers": ["missing required gear slots"]},
                            "updatedAt": "2026-06-30T00:05:00+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-pg-gear-template",
                            "sourceRefs": [{"type": "raiderio"}],
                            "scanRunId": "scan-pg",
                        },
                        {
                            "id": "pg-gear-template-visible",
                            "classKey": "mage",
                            "specKey": "frost",
                            "name": "PG visible gear template",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/pg-visible-gear-template",
                            "sourceStatus": "verified",
                            "status": "verified",
                            "readySlotCount": 16,
                            "missingSlots": [],
                            "analysisWindow": "2026-W27",
                            "payload": {},
                            "updatedAt": "2026-06-30T00:06:00+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-pg-visible-gear-template",
                            "sourceRefs": [{"type": "raiderio"}],
                            "scanRunId": "scan-pg",
                        },
                        {
                            "id": "pg-gear-template-baseline",
                            "classKey": "mage",
                            "specKey": "frost",
                            "name": "SimC preset baseline",
                            "sourceKey": "simc_preset",
                            "sourceName": "SimC preset",
                            "sourceUrl": "",
                            "sourceStatus": "synced",
                            "status": "complete",
                            "readySlotCount": 16,
                            "missingSlots": [],
                            "analysisWindow": "SimC preset profile; 16/16 canonical gear slots ready.",
                            "payload": {},
                            "updatedAt": "2026-06-30T00:06:30+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-pg-baseline-gear-template",
                            "sourceRefs": [{"type": "simc_preset"}],
                            "scanRunId": "scan-pg",
                        },
                        {
                            "id": "pg-gear-template-default",
                            "classKey": "mage",
                            "specKey": "frost",
                            "name": "默认模板 · 法师冰霜",
                            "sourceKey": "default_template",
                            "sourceName": "默认模板",
                            "sourceUrl": "",
                            "sourceStatus": "verified",
                            "status": "complete",
                            "readySlotCount": 16,
                            "missingSlots": [],
                            "analysisWindow": "默认模板由 verified 当前赛季装备候选和 M+ mixed-route 绿字权重生成。",
                            "payload": {
                                "scenarioKey": "mplus_mixed_route",
                                "templateEvidence": {"sourceKey": "default_template"},
                            },
                            "updatedAt": "2026-06-30T00:07:00+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-pg-default-gear-template",
                            "sourceRefs": [{"type": "default_template"}],
                            "scanRunId": "scan-pg",
                        }
                    ],
                    "gearVariants": [
                        {
                            "id": "pg-variant-1",
                            "itemId": "item-pg",
                            "itemName": "PG gear item",
                            "slot": "head",
                            "label": "Mythic",
                            "sourceType": "dungeon",
                            "sourceLabel": "Arcane Warden - Magisters' Terrace",
                            "sourceInstanceId": "1300",
                            "sourceInstanceLabel": "Magisters' Terrace",
                            "difficultyKey": "mythic",
                            "itemLevel": 678,
                            "status": "verified",
                            "blockers": [],
                            "payload": {
                                "simcOptions": {"ilevel": 678},
                                "requirements": {"playable_classes": {"classes": [{"id": 8}]}},
                            },
                            "itemPayload": {
                                "item_class": {"id": 4, "name": "Armor"},
                                "item_subclass": {"id": 1, "name": "Cloth"},
                            },
                            "updatedAt": "2026-06-30T00:04:00+00:00",
                        },
                        {
                            "id": "pg-variant-blocked",
                            "itemId": "item-pg-blocked",
                            "itemName": "PG blocked gear item",
                            "slot": "main_hand",
                            "label": "Heroic",
                            "sourceType": "raid",
                            "sourceLabel": "Voidbinder - The Voidspire",
                            "sourceInstanceId": "1400",
                            "sourceInstanceLabel": "The Voidspire",
                            "difficultyKey": "heroic",
                            "itemLevel": 665,
                            "status": "blocked",
                            "blockers": ["missing simc options"],
                            "payload": {
                                "requirements": {"playable_classes": {"classes": [{"id": 1}]}}
                            },
                            "itemPayload": {
                                "item_class": {"id": 2, "name": "Weapon"},
                                "item_subclass": {"id": 10, "name": "Staff"},
                            },
                            "updatedAt": "2026-06-30T00:03:30+00:00",
                        }
                    ]
                }

        with patch.object(self.backend, "content_data_store", return_value=FakeContentStore()), patch.object(
            self.backend, "cache_data_store", return_value=FakeCacheStore()
        ):
            news_payload = self.backend.admin_gate_records_payload({"domain": ["news"], "limit": ["20"]})
            talent_payload = self.backend.admin_gate_records_payload({"domain": ["talents"], "limit": ["20"]})
            gear_payload = self.backend.admin_gate_records_payload({"domain": ["gear"], "limit": ["20"]})
            gear_templates_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear_templates"], "limit": ["20"]}
            )
            news_category_source_miss = self.backend.admin_gate_records_payload(
                {"domain": ["news"], "field": ["category"], "q": ["Blizzard"], "limit": ["20"]}
            )
            talent_template_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["talentTemplate"], "q": ["PG talent"], "limit": ["20"]}
            )
            talent_class_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["class"], "q": ["法师"], "limit": ["20"]}
            )
            talent_class_source_miss = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["class"], "q": ["Raider.IO"], "limit": ["20"]}
            )
            talent_source_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["source"], "q": ["Raider.IO"], "limit": ["20"]}
            )
            talent_status_verified_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "status": ["verified"], "limit": ["20"]}
            )
            talent_blocked_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["blocked"], "q": ["已阻断"], "limit": ["20"]}
            )
            talent_blocked_source_miss = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["blocked"], "q": ["Raider.IO"], "limit": ["20"]}
            )
            talent_block_reason_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["blockReason"], "q": ["invalid_talent_template"], "limit": ["20"]}
            )
            talent_visibility_visible_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["visibility"], "q": ["已可见"], "limit": ["20"]}
            )
            talent_visibility_payload = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "field": ["visibility"], "q": ["不可见"], "limit": ["20"]}
            )
            gear_category_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["category"], "q": ["头部"], "limit": ["20"]}
            )
            gear_source_slot_miss = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["source"], "q": ["头部"], "limit": ["20"]}
            )
            gear_source_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["source"], "q": ["dungeon"], "limit": ["20"]}
            )
            gear_drop_source_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["dropSource"], "q": ["地下城"], "limit": ["20"]}
            )
            gear_dungeon_instance_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["sourceInstance"], "q": ["Magisters' Terrace"], "limit": ["20"]}
            )
            gear_raid_instance_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["sourceInstance"], "q": ["The Voidspire"], "limit": ["20"]}
            )
            gear_class_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["class"], "q": ["法师"], "limit": ["20"]}
            )
            gear_item_type_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["itemType"], "q": ["武器类型"], "limit": ["20"]}
            )
            gear_visibility_visible_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["visibility"], "q": ["已可见"], "limit": ["20"]}
            )
            gear_visibility_hidden_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear"], "field": ["visibility"], "q": ["不可见"], "limit": ["20"]}
            )
            gear_template_class_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear_templates"], "field": ["class"], "q": ["法师"], "limit": ["20"]}
            )
            gear_template_visibility_visible_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear_templates"], "field": ["visibility"], "q": ["已可见"], "limit": ["20"]}
            )
            gear_template_visibility_hidden_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear_templates"], "field": ["visibility"], "q": ["不可见"], "limit": ["20"]}
            )
            gear_template_source_default_payload = self.backend.admin_gate_records_payload(
                {"domain": ["gear_templates"], "field": ["source"], "q": ["默认模板"], "limit": ["20"]}
            )
            talent_page_one = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "page": ["1"], "pageSize": ["1"]}
            )
            talent_page_two = self.backend.admin_gate_records_payload(
                {"domain": ["talents"], "page": ["2"], "pageSize": ["1"]}
            )
            talent_default_page = self.backend.admin_gate_records_payload({"domain": ["talents"]})

        self.assertTrue(any(record["targetId"] == "pg-news-1" for record in news_payload["records"]))
        pg_news = next(record for record in news_payload["records"] if record["targetId"] == "pg-news-1")
        self.assertEqual(pg_news["articleCategory"]["label"], "职业强度变化")
        self.assertEqual(pg_news["articleCategory"]["channel"], "职业强度变化")
        self.assertEqual(pg_news["publication"]["state"], "published")
        self.assertEqual(pg_news["publication"]["publishedAt"], "2026-06-30T00:00:00+00:00")
        self.assertTrue(any(record["targetId"] == "pg-template-1" for record in talent_payload["records"]))
        pg_template = next(record for record in talent_payload["records"] if record["targetId"] == "pg-template-1")
        self.assertEqual(pg_template["talentCategory"]["classKey"], "mage")
        self.assertEqual(pg_template["talentCategory"]["classLabel"], "法师")
        self.assertEqual(pg_template["talentCategory"]["specKey"], "frost")
        self.assertEqual(pg_template["talentCategory"]["sourceKind"], "community")
        self.assertEqual(pg_template["talentCategory"]["sourceLabel"], "社区来源")
        self.assertEqual(pg_template["talentPublication"]["state"], "visible")
        self.assertEqual(pg_template["talentPublication"]["stateLabel"], "已可见")
        self.assertEqual(pg_template["talentPublication"]["surface"], "天赋导入列表")
        self.assertEqual(pg_template["talentBlockReason"]["state"], "clear")
        self.assertEqual(pg_template["facets"]["evidenceTier"], "wcl_character_supported")
        self.assertEqual(pg_template["facets"]["wclEvidenceTier"], "wcl_character_supported")
        self.assertEqual(pg_template["facets"]["qualityScore"], 74)
        self.assertIn("WCL character-supported", pg_template["evidence"]["promotionReason"])
        self.assertEqual(pg_template["evidence"]["wclEvidence"]["reportCount"], 2)
        wcl_verified_partial_source = self.backend.admin_gate_record(
            "talents",
            "community_talent_template",
            "wcl-exact-template",
            "WCL exact template",
            status="verified",
            source_status="partial",
            source_name="Warcraft Logs",
            blockers=[],
            facets={"sourceKey": "warcraftlogs", "sampleCount": 1, "maxKeyLevel": 0},
            evidence={"wclEvidence": {"tier": "wcl_exact_template"}},
        )
        self.assertEqual(wcl_verified_partial_source["status"], "verified")
        self.assertEqual(wcl_verified_partial_source["sourceStatus"], "partial")
        self.assertEqual(wcl_verified_partial_source["talentPublication"]["state"], "visible")
        self.assertEqual(wcl_verified_partial_source["severity"], "ok")
        pg_blocked_template = next(record for record in talent_payload["records"] if record["targetId"] == "pg-template-blocked")
        self.assertEqual(pg_blocked_template["talentPublication"]["state"], "hidden")
        self.assertEqual(pg_blocked_template["talentPublication"]["stateLabel"], "不可见")
        self.assertEqual(pg_blocked_template["talentPublication"]["reason"], "invalid_talent_template")
        self.assertEqual(pg_blocked_template["talentBlockReason"]["state"], "blocked")
        self.assertEqual(pg_blocked_template["talentBlockReason"]["reason"], "invalid_talent_template")
        baseline_blocked = self.backend.admin_gate_record(
            "talents",
            "community_talent_template",
            "baseline-empty",
            "WebSim 基线-法师-冰霜",
            status="blocked",
            source_status="blocked",
            blockers=[],
            facets={"sourceKey": "websim_baseline", "sampleCount": 0, "maxKeyLevel": 0},
            evidence={
                "sourceRefs": [
                    {"sourceKey": "websim_baseline", "sourceStatus": "blocked", "sampleCount": 0, "maxKeyLevel": 0}
                ]
            },
        )
        self.assertEqual(baseline_blocked["talentBlockReason"]["state"], "blocked")
        self.assertIn("sampleCount=0", baseline_blocked["talentBlockReason"]["reason"])
        self.assertEqual(baseline_blocked["talentPublication"]["reason"], baseline_blocked["talentBlockReason"]["reason"])
        self.assertEqual({record["targetType"] for record in talent_payload["records"]}, {"community_talent_template"})
        self.assertFalse(any(record["targetId"] == "mage:frost" for record in talent_payload["records"]))
        self.assertTrue(any(record["targetId"] == "pg-variant-1" for record in gear_payload["records"]))
        pg_gear = next(record for record in gear_payload["records"] if record["targetId"] == "pg-variant-1")
        self.assertEqual(pg_gear["gearCategory"]["slot"], "head")
        self.assertEqual(pg_gear["gearCategory"]["slotLabel"], "头部")
        self.assertEqual(pg_gear["gearCategory"]["sourceType"], "dungeon")
        self.assertEqual(pg_gear["gearCategory"]["sourceLabel"], "地下城")
        self.assertEqual(pg_gear["gearCategory"]["sourceDetailLabel"], "Arcane Warden - Magisters' Terrace")
        self.assertEqual(pg_gear["gearCategory"]["sourceInstanceId"], "1300")
        self.assertEqual(pg_gear["gearCategory"]["sourceInstanceLabel"], "Magisters' Terrace")
        self.assertEqual(pg_gear["gearCategory"]["difficultyKey"], "mythic")
        self.assertEqual(pg_gear["gearCategory"]["itemLevel"], 678)
        self.assertEqual(pg_gear["gearCategory"]["classKeys"], ["mage"])
        self.assertEqual(pg_gear["gearCategory"]["classLabels"], ["法师"])
        self.assertEqual(pg_gear["gearCategory"]["itemTypeLabel"], "布甲")
        self.assertEqual(pg_gear["gearCategory"]["itemTypeGroupLabel"], "护甲类型")
        self.assertEqual(pg_gear["gearVisibility"]["state"], "visible")
        self.assertEqual(pg_gear["gearVisibility"]["stateLabel"], "已可见")
        self.assertEqual(pg_gear["gearBlockReason"]["state"], "clear")
        pg_blocked_gear = next(record for record in gear_payload["records"] if record["targetId"] == "pg-variant-blocked")
        self.assertEqual(pg_blocked_gear["gearVisibility"]["state"], "hidden")
        self.assertEqual(pg_blocked_gear["gearVisibility"]["stateLabel"], "不可见")
        self.assertEqual(pg_blocked_gear["gearVisibility"]["reason"], "missing simc options")
        self.assertEqual(pg_blocked_gear["gearBlockReason"]["state"], "blocked")
        self.assertEqual(pg_blocked_gear["gearCategory"]["itemTypeLabel"], "法杖")
        self.assertEqual(pg_blocked_gear["gearCategory"]["itemTypeGroupLabel"], "武器类型")
        trinket_category = self.backend.admin_gate_gear_record_category(
            "gear_variant",
            slot="trinket1",
            item_type_payload={},
        )
        self.assertEqual(trinket_category["itemTypeLabel"], "饰品")
        self.assertEqual(trinket_category["itemTypeGroupLabel"], "首饰")
        self.assertEqual({record["targetType"] for record in gear_payload["records"]}, {"gear_variant"})
        self.assertEqual({record["targetType"] for record in gear_templates_payload["records"]}, {"community_gear_template"})
        pg_gear_template = gear_templates_payload["records"][0]
        self.assertEqual(pg_gear_template["domain"], "gear_templates")
        self.assertEqual(pg_gear_template["gearCategory"]["classLabel"], "战士")
        self.assertEqual(pg_gear_template["gearVisibility"]["state"], "hidden")
        self.assertEqual(pg_gear_template["gearVisibility"]["stateLabel"], "不可见")
        visible_gear_template = next(record for record in gear_templates_payload["records"] if record["targetId"] == "pg-gear-template-visible")
        self.assertEqual(visible_gear_template["gearCategory"]["classLabel"], "法师")
        self.assertEqual(visible_gear_template["gearVisibility"]["state"], "visible")
        self.assertEqual(visible_gear_template["gearVisibility"]["stateLabel"], "已可见")
        baseline_gear_template = next(record for record in gear_templates_payload["records"] if record["targetId"] == "pg-gear-template-baseline")
        self.assertEqual(baseline_gear_template["gearCategory"]["classLabel"], "法师")
        self.assertEqual(baseline_gear_template["gearCategory"]["sourceKind"], "baseline")
        self.assertEqual(baseline_gear_template["gearCategory"]["sourceLabel"], "基线模板")
        self.assertEqual(baseline_gear_template["gearCategory"]["sourceKey"], "simc_preset")
        default_gear_template = next(record for record in gear_templates_payload["records"] if record["targetId"] == "pg-gear-template-default")
        self.assertEqual(default_gear_template["gearCategory"]["classLabel"], "法师")
        self.assertEqual(default_gear_template["gearCategory"]["sourceKind"], "baseline")
        self.assertEqual(default_gear_template["gearCategory"]["sourceLabel"], "基线模板")
        self.assertEqual(default_gear_template["gearCategory"]["sourceKey"], "default_template")
        self.assertEqual(default_gear_template["sourceName"], "默认模板")
        self.assertEqual(news_category_source_miss["records"], [])
        self.assertEqual([record["targetId"] for record in talent_template_payload["records"]], ["pg-template-1"])
        self.assertEqual(
            {record["targetId"] for record in talent_class_payload["records"]},
            {"pg-template-1"},
        )
        self.assertEqual(talent_class_source_miss["records"], [])
        self.assertEqual([record["targetId"] for record in talent_source_payload["records"]], ["pg-template-1"])
        self.assertEqual(
            {record["targetId"] for record in talent_status_verified_payload["records"]},
            {"pg-template-1"},
        )
        self.assertEqual([record["targetId"] for record in talent_blocked_payload["records"]], ["pg-template-blocked"])
        self.assertEqual(talent_blocked_source_miss["records"], [])
        self.assertEqual([record["targetId"] for record in talent_block_reason_payload["records"]], ["pg-template-blocked"])
        self.assertEqual(
            {record["targetId"] for record in talent_visibility_visible_payload["records"]},
            {"pg-template-1"},
        )
        self.assertEqual([record["targetId"] for record in talent_visibility_payload["records"]], ["pg-template-blocked"])
        self.assertEqual([record["targetId"] for record in gear_category_payload["records"]], ["pg-variant-1"])
        self.assertEqual(gear_source_slot_miss["records"], [])
        self.assertEqual([record["targetId"] for record in gear_source_payload["records"]], ["pg-variant-1"])
        self.assertEqual([record["targetId"] for record in gear_drop_source_payload["records"]], ["pg-variant-1"])
        self.assertEqual([record["targetId"] for record in gear_dungeon_instance_payload["records"]], ["pg-variant-1"])
        self.assertEqual([record["targetId"] for record in gear_raid_instance_payload["records"]], ["pg-variant-blocked"])
        self.assertEqual([record["targetId"] for record in gear_class_payload["records"]], ["pg-variant-1"])
        self.assertEqual([record["targetId"] for record in gear_item_type_payload["records"]], ["pg-variant-blocked"])
        self.assertEqual([record["targetId"] for record in gear_visibility_visible_payload["records"]], ["pg-variant-1"])
        self.assertEqual([record["targetId"] for record in gear_visibility_hidden_payload["records"]], ["pg-variant-blocked"])
        self.assertEqual(
            {record["targetId"] for record in gear_template_class_payload["records"]},
            {"pg-gear-template-visible", "pg-gear-template-baseline", "pg-gear-template-default"},
        )
        self.assertEqual(
            {record["targetId"] for record in gear_template_visibility_visible_payload["records"]},
            {"pg-gear-template-visible", "pg-gear-template-baseline", "pg-gear-template-default"},
        )
        self.assertEqual([record["targetId"] for record in gear_template_visibility_hidden_payload["records"]], ["pg-gear-template-1"])
        self.assertEqual([record["targetId"] for record in gear_template_source_default_payload["records"]], ["pg-gear-template-default"])
        self.assertEqual(talent_page_one["pagination"]["page"], 1)
        self.assertEqual(talent_page_one["pagination"]["pageSize"], 1)
        self.assertEqual(talent_page_one["pagination"]["total"], 2)
        self.assertEqual(talent_page_one["pagination"]["totalPages"], 2)
        self.assertEqual(talent_page_one["count"], 1)
        self.assertEqual(talent_page_two["count"], 1)
        self.assertEqual(talent_page_one["records"][0]["targetId"], "pg-template-1")
        self.assertEqual(talent_page_two["records"][0]["targetId"], "pg-template-blocked")
        self.assertEqual(talent_default_page["pagination"]["pageSize"], 20)

    def test_admin_gate_talent_records_from_store_omit_expired_templates(self):
        class FakeCacheStore:
            def admin_gate_talent_records(self):
                return {
                    "communityTalentTemplates": [
                        {
                            "id": "expired-template",
                            "classKey": "deathknight",
                            "specKey": "unholy",
                            "heroKey": "rider_of_the_apocalypse",
                            "scenarioKey": "mythic_plus",
                            "name": "Expired Raider.IO template",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/expired-template",
                            "sourceStatus": "synced",
                            "status": "blocked",
                            "sampleCount": 496,
                            "maxKeyLevel": 24,
                            "analysisWindow": "stale window",
                            "payload": {"errors": ["unknown structured talent entry"]},
                            "updatedAt": "2026-06-28T12:28:54+00:00",
                            "expiresAt": "2026-06-29T12:34:15+00:00",
                            "signature": "sig-expired",
                            "sourceRefs": [{"type": "raiderio"}],
                            "scanRunId": "scan-expired",
                        },
                        {
                            "id": "fresh-template",
                            "classKey": "deathknight",
                            "specKey": "unholy",
                            "heroKey": "rider_of_the_apocalypse",
                            "scenarioKey": "mythic_plus",
                            "name": "Fresh Raider.IO template",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/fresh-template",
                            "sourceStatus": "synced",
                            "status": "verified",
                            "sampleCount": 499,
                            "maxKeyLevel": 24,
                            "analysisWindow": "fresh window",
                            "payload": {},
                            "updatedAt": "2026-07-02T21:21:01+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-fresh",
                            "sourceRefs": [{"type": "raiderio"}],
                            "scanRunId": "scan-fresh",
                        },
                    ],
                    "talentTrees": [],
                }

        with patch.object(self.backend, "utc_now", return_value="2026-07-03T00:00:00+00:00"):
            records = self.backend.collect_admin_talent_records_from_store(FakeCacheStore())

        self.assertEqual([record["targetId"] for record in records], ["fresh-template"])

    def test_admin_gate_talent_records_sqlite_omit_expired_and_surface_payload_errors(self):
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            self.backend.ensure_websim_tables(conn)
            for template_id, expires_at, status, payload in [
                ("expired-template", "2026-06-29T00:00:00+00:00", "blocked", {"blockers": ["expired blocker"]}),
                (
                    "fresh-template",
                    "2099-01-01T00:00:00+00:00",
                    "blocked",
                    {"talentLoadoutParse": {"errors": ["unknown structured talent entry: {'traitId': 91001}"]}},
                ),
            ]:
                conn.execute(
                    """
                    INSERT INTO websim_community_talent_templates (
                        id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
                        source_key, source_name, source_url, raw_import_code, websim_export_code,
                        talent_state_json, sample_count, max_key_level, analysis_window,
                        source_status, status, payload_json, updated_at, expires_at,
                        signature, source_refs_json, scan_run_id
                    ) VALUES (?, 'mage', 'frost', 'frostfire', 'mythic_plus', ?, 'Raider.IO',
                              'raiderio', 'Raider.IO', 'https://example.com', '', '',
                              '{"selectedNodes":[]}', 1, 24, 'fixture',
                              'synced', ?, ?, '2026-07-03T00:00:00+00:00', ?,
                              ?, '[]', 'scan-fixture')
                    """,
                    (
                        template_id,
                        template_id,
                        status,
                        json.dumps(payload, ensure_ascii=False),
                        expires_at,
                        f"sig-{template_id}",
                    ),
                )
            conn.commit()
            with patch.object(self.backend, "utc_now", return_value="2026-07-03T00:00:00+00:00"):
                records = self.backend.collect_admin_talent_records(conn)

        self.assertEqual([record["targetId"] for record in records], ["fresh-template"])
        self.assertIn("unknown structured talent entry", records[0]["blockers"][0])

    def test_admin_gate_talent_records_surface_payload_errors_as_blockers(self):
        class FakeCacheStore:
            def admin_gate_talent_records(self):
                return {
                    "communityTalentTemplates": [
                        {
                            "id": "raiderio-parse-blocked",
                            "classKey": "mage",
                            "specKey": "frost",
                            "heroKey": "frostfire",
                            "scenarioKey": "mythic_plus",
                            "name": "Raider.IO parse blocked",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/raiderio-parse-blocked",
                            "sourceStatus": "synced",
                            "status": "blocked",
                            "sampleCount": 1,
                            "maxKeyLevel": 24,
                            "analysisWindow": "2026-W27",
                            "payload": {
                                "talentLoadoutParse": {
                                    "status": "blocked",
                                    "errors": ["unknown structured talent entry: {'traitId': 91001}"],
                                }
                            },
                            "updatedAt": "2026-07-03T01:00:00+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-raiderio-parse-blocked",
                            "sourceRefs": [{"sourceKey": "raiderio", "sourceStatus": "synced"}],
                            "scanRunId": "scan-raiderio",
                        }
                    ],
                    "talentTrees": [],
                }

        records = self.backend.collect_admin_talent_records_from_store(FakeCacheStore())

        self.assertEqual(len(records), 1)
        self.assertIn("unknown structured talent entry", records[0]["blockers"][0])
        self.assertIn("unknown structured talent entry", records[0]["talentBlockReason"]["reason"])
        self.assertNotIn("raiderio 来源状态", records[0]["talentBlockReason"]["reason"])

    def test_admin_gates_gear_records_use_paged_postgres_store_when_unfiltered(self):
        calls = []

        class CacheStore:
            def admin_gate_gear_variant_records_page(self, limit=20, offset=0):
                calls.append((limit, offset))
                return {
                    "totalGroups": 42,
                    "gearVariants": [
                        {
                            "id": "variant-page-1",
                            "itemId": "250001",
                            "itemName": "Paged Gear",
                            "slot": "head",
                            "label": "Champion",
                            "sourceType": "dungeon",
                            "difficultyKey": "mythic_plus",
                            "itemLevel": 678,
                            "simcOptions": {"ilevel": 678},
                            "status": "partial",
                            "blockers": ["stat source pending"],
                            "payload": {},
                            "itemPayload": {},
                            "sourceLabel": "Paged Boss - Paged Dungeon",
                            "sourceInstanceId": "9999",
                            "updatedAt": "2026-07-01T00:00:00+00:00",
                        }
                    ],
                }

            def admin_gate_gear_variant_records(self):
                raise AssertionError("unfiltered gear records should use the paged PG path")

        with patch.object(self.backend, "cache_data_store", return_value=CacheStore()):
            payload = self.backend.admin_gate_records_payload({
                "domain": ["gear"],
                "page": ["2"],
                "pageSize": ["20"],
            })

        self.assertEqual(calls, [(20, 20)])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["pagination"]["total"], 42)
        self.assertEqual(payload["records"][0]["targetId"], "variant-page-1")

    def test_admin_gates_empty_postgres_gear_templates_do_not_fallback_to_sqlite(self):
        class EmptyCacheStore:
            def admin_gate_gear_records(self):
                return {"communityGearTemplates": [], "gearVariants": []}

        with patch.object(self.backend, "cache_data_store", return_value=EmptyCacheStore()), patch.object(
            self.backend, "init_db", side_effect=AssertionError("must not fall back to SQLite when PG store is active")
        ):
            payload = self.backend.admin_gate_records_payload({"domain": ["gear_templates"], "limit": ["20"]})

        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["pagination"]["total"], 0)

    def test_pg_only_admin_gate_records_do_not_fallback_to_sqlite_when_runtime_store_missing(self):
        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "content_data_store", return_value=None), patch.object(
            self.backend, "cache_data_store", return_value=None
        ), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only admin records must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only admin records must not open SQLite"),
        ):
            payload = self.backend.admin_gate_records_payload({"domain": ["talents"], "limit": ["20"]})

        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["totalCount"], 0)
        self.assertIn("PostgreSQL runtime store is not available", payload["runtimeBlockers"])

    def test_pg_only_admin_gate_queue_do_not_fallback_to_sqlite_when_runtime_store_missing(self):
        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "content_data_store", return_value=None), patch.object(
            self.backend, "cache_data_store", return_value=None
        ), patch.object(
            self.backend, "ops_data_store", return_value=None
        ), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only admin queue must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only admin queue must not open SQLite"),
        ):
            payload = self.backend.admin_gate_queue_payload({"domain": ["talents"], "limit": ["20"]})

        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["count"], 0)
        self.assertIn("PostgreSQL runtime store is not available", payload["runtimeBlockers"])

    def test_pg_only_admin_gate_detail_do_not_fallback_to_sqlite_when_runtime_store_missing(self):
        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "content_data_store", return_value=None), patch.object(
            self.backend, "cache_data_store", return_value=None
        ), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only admin detail must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only admin detail must not open SQLite"),
        ):
            payload = self.backend.admin_gate_record_detail_payload("talents", "community_talent_template", "missing")

        self.assertEqual(payload, {})

    def test_admin_gates_gear_templates_use_narrow_postgres_store_method(self):
        class NarrowTemplateStore:
            def admin_gate_gear_template_records(self):
                return {
                    "communityGearTemplates": [
                        {
                            "id": "pg-gear-template-narrow",
                            "classKey": "mage",
                            "specKey": "frost",
                            "name": "PG narrow gear template",
                            "sourceKey": "raiderio",
                            "sourceName": "Raider.IO",
                            "sourceUrl": "https://example.com/pg-gear-template",
                            "sourceStatus": "verified",
                            "status": "verified",
                            "readySlotCount": 16,
                            "missingSlots": [],
                            "analysisWindow": "2026-W27",
                            "payload": {},
                            "updatedAt": "2026-06-30T00:05:00+00:00",
                            "expiresAt": "2099-01-01T00:00:00+00:00",
                            "signature": "sig-pg-gear-template",
                            "sourceRefs": [{"type": "raiderio"}],
                            "scanRunId": "scan-pg",
                        }
                    ]
                }

            def admin_gate_gear_records(self):
                raise AssertionError("gear_templates must not call the combined gear records path")

        with patch.object(self.backend, "cache_data_store", return_value=NarrowTemplateStore()):
            payload = self.backend.admin_gate_records_payload({"domain": ["gear_templates"], "limit": ["20"]})

        self.assertEqual([record["targetId"] for record in payload["records"]], ["pg-gear-template-narrow"])

    def test_runtime_websim_gear_returns_stale_postgres_payload_without_sqlite_fallback(self):
        stale_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "mage",
            "specKey": "frost",
            "dataStatus": "stale",
            "catalogBlockers": ["season cache expired"],
            "replacementCandidates": [],
        }

        class StaleGearStore:
            def get_websim_gear(self, class_key, spec_key, compact=False):
                return stale_payload

        with patch.object(self.backend, "cache_data_store", return_value=StaleGearStore()), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("stale PG gear payload must not fall back to SQLite"),
        ):
            payload = self.backend.runtime_websim_gear_payload("mage", "frost", compact=True)

        self.assertIs(payload, stale_payload)

    def test_runtime_websim_gear_forwards_payload_mode_to_postgres_store(self):
        captured = {}
        initial_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "mage",
            "specKey": "frost",
            "gearPayloadMode": "initial",
            "replacementCandidates": [],
        }

        class ModeAwareGearStore:
            def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
                captured.update(
                    {
                        "classKey": class_key,
                        "specKey": spec_key,
                        "compact": compact,
                        "mode": mode,
                        "slot": slot,
                    }
                )
                return initial_payload

        with patch.object(self.backend, "cache_data_store", return_value=ModeAwareGearStore()):
            payload = self.backend.runtime_websim_gear_payload(
                "mage",
                "frost",
                compact=True,
                mode="initial",
                slot="head",
            )

        self.assertIs(payload, initial_payload)
        self.assertEqual(captured["classKey"], "mage")
        self.assertEqual(captured["specKey"], "frost")
        self.assertTrue(captured["compact"])
        self.assertEqual(captured["mode"], "initial")
        self.assertEqual(captured["slot"], "head")

    def test_runtime_websim_gear_attaches_backend_resolver_context(self):
        captured = {}
        initial_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "mage",
            "specKey": "frost",
            "gearPayloadMode": "initial",
            "replacementCandidates": [],
        }
        resolver_context = {
            "contractRevision": "gear-resolver-context-v1",
            "formalActiveManifest": False,
            "selectionSchemaRevision": "selection-intent-v1",
            "authoredAgainst": {
                "seasonRevision": "season-17-active",
                "gearCatalogRevision": "compatibility-pg:resolver",
            },
        }
        runtime_authority = {"dependencyRevisions": {"simcRuntimeRevision": "simc-v1"}}

        class ResolverContextStore:
            def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
                return initial_payload

            def get_gear_resolver_context(self, authority):
                captured["authority"] = authority
                return resolver_context

        with patch.object(
            self.backend,
            "cache_data_store",
            return_value=ResolverContextStore(),
        ), patch.object(
            self.backend,
            "simc_version_status",
            return_value={"localTag": "simc-v1"},
        ), patch.object(
            self.backend,
            "gear_resolver_runtime_authority",
            return_value=runtime_authority,
            create=True,
        ) as authority_builder:
            payload = self.backend.runtime_websim_gear_payload(
                "mage",
                "frost",
                compact=True,
                mode="initial",
            )

        self.assertIsNot(payload, initial_payload)
        self.assertEqual(payload["resolverContext"], resolver_context)
        self.assertEqual(captured["authority"], runtime_authority)
        authority_builder.assert_called_once_with(
            "mage",
            "frost",
            simc_runtime_revision="simc-v1",
        )

    def test_runtime_websim_gear_keeps_payload_when_resolver_context_read_fails(self):
        initial_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "mage",
            "specKey": "frost",
            "gearPayloadMode": "initial",
            "replacementCandidates": [],
        }

        class ResolverContextFailureStore:
            def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
                return initial_payload

            def get_gear_resolver_context(self, authority):
                raise OSError("independent revision query failed")

        with patch.object(
            self.backend,
            "cache_data_store",
            return_value=ResolverContextFailureStore(),
        ), patch.object(
            self.backend,
            "simc_version_status",
            return_value={"localTag": "simc-v1"},
        ):
            payload = self.backend.runtime_websim_gear_payload(
                "mage",
                "frost",
                compact=True,
                mode="initial",
            )

        self.assertIs(payload, initial_payload)
        self.assertNotIn("resolverContext", payload)

    def test_runtime_websim_gear_adds_template_chain_state_to_cached_postgres_payload(self):
        observed = {
            "id": "observed-mage-frost",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "sourceUrl": "https://raider.io/characters/cn/realm/Magefrost",
            "sampleCount": 1,
            "status": "complete",
            "sourceStatus": "synced",
            "readySlotCount": 16,
            "scanRunId": "scan-mage-frost",
            "gearHash": "gear:mage-frost",
            "sourceRefs": [
                {
                    "sourceKey": "raiderio_observed_profile",
                    "sourceUrl": "https://raider.io/characters/cn/realm/Magefrost",
                    "sampleCount": 1,
                    "characterName": "Magefrost",
                    "region": "cn",
                    "realmSlug": "realm",
                    "fetchedAt": "2026-07-08T08:00:00+00:00",
                    "scanRunId": "scan-mage-frost",
                }
            ],
            "payload": {
                "profileHash": "sha256:mage-frost",
                "gearHash": "gear:mage-frost",
                "character": {
                    "name": "Magefrost",
                    "region": "cn",
                    "realmSlug": "realm",
                },
                "templateEvidence": {
                    "scenarioResults": {
                        "mplus_aoe": {"dps": 200000, "iterations": 10000}
                    }
                },
            },
        }
        baseline = {
            "id": "season-recommendation-mage-frost",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "season_recommendation",
            "status": "complete",
            "sourceStatus": "synced",
            "readySlotCount": 16,
            "payload": {
                "templateEvidence": {
                    "recommendationConfidence": "provisional",
                    "simcReview": {"status": "required"},
                }
            },
        }
        pg_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "mage",
            "specKey": "frost",
            "replacementCandidates": [],
            "communityTemplates": [observed],
            "baselineTemplates": [baseline],
            "communityTemplateSync": {
                "sourceStatus": "synced",
                "templates": {"total": 2, "verified": 2},
            },
        }

        class Store:
            def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
                return pg_payload

        with patch.object(self.backend, "cache_data_store", return_value=Store()):
            payload = self.backend.runtime_websim_gear_payload("mage", "frost", compact=True, mode="initial")

        self.assertEqual(payload["communityTemplateSync"]["templateChains"]["communityObserved"]["verifiedSpecCount"], 1)
        self.assertEqual(payload["communityTemplateSync"]["templateChains"]["legacyFallback"]["starterBaselineSpecCount"], 1)

    def test_runtime_websim_gear_partially_gates_illegal_postgres_templates(self):
        legal_head = {
            "slot": "head",
            "simcSlot": "head",
            "itemId": "270001",
            "displayName": "Legal Head",
            "armorType": "Mail",
            "simcReady": True,
        }
        bad_template = {
            "id": "season-recommendation-shaman-elemental",
            "classKey": "shaman",
            "specKey": "elemental",
            "sourceKey": "season_recommendation",
            "sourceStatus": "synced",
            "status": "complete",
            "canApplyGear": True,
            "readySlotCount": 16,
            "gearItems": [
                {
                    "slot": "main_hand",
                    "simcSlot": "main_hand",
                    "itemId": "237849",
                    "weaponType": "Two-Handed Mace",
                    "simcReady": True,
                },
                {
                    "slot": "off_hand",
                    "simcSlot": "off_hand",
                    "itemId": "245769",
                    "weaponType": "Held In Off-hand",
                    "simcReady": True,
                },
                legal_head,
            ],
        }
        pg_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "shaman",
            "specKey": "elemental",
            "replacementCandidates": [],
            "equippedSet": {
                "main_hand": bad_template["gearItems"][0],
                "off_hand": bad_template["gearItems"][1],
                "head": legal_head,
            },
            "baselineSet": bad_template["gearItems"],
            "communityTemplates": [],
            "baselineTemplates": [bad_template],
        }

        class Store:
            def get_websim_gear(self, class_key, spec_key, compact=False, mode="", slot=""):
                return pg_payload

        with patch.object(self.backend, "cache_data_store", return_value=Store()):
            payload = self.backend.runtime_websim_gear_payload("shaman", "elemental", compact=True, mode="initial")

        baseline = payload["baselineTemplates"][0]
        self.assertEqual(baseline["status"], "partial")
        self.assertEqual(baseline["sourceStatus"], "partial")
        self.assertTrue(baseline["canApplyGear"])
        self.assertEqual(baseline["readySlotCount"], 1)
        self.assertIn("main_hand", baseline["missingSlots"])
        self.assertIn("off_hand", baseline["missingSlots"])
        self.assertEqual([item["slot"] for item in baseline["gearItems"]], ["head"])
        self.assertTrue(
            any(
                "main_hand gear incompatible with shaman/elemental weapon rule: Two-Handed Mace" in blocker
                for blocker in baseline["blockers"]
            )
        )
        self.assertNotIn("main_hand", payload["equippedSet"])
        self.assertNotIn("off_hand", payload["equippedSet"])
        self.assertIn("head", payload["equippedSet"])
        self.assertFalse(
            any(
                item.get("slot") in {"main_hand", "off_hand"}
                for item in payload["baselineSet"]
            )
        )
        self.assertTrue(any(item.get("slot") == "head" for item in payload["baselineSet"]))
        self.assertEqual(payload["communityTemplateSync"]["sourceStatus"], "partial")

    def test_pg_only_runtime_ignores_sqlite_public_cache_fallback_flag_for_gear(self):
        stale_payload = {
            "schemaRevision": "websim-gear-v1",
            "classKey": "mage",
            "specKey": "frost",
            "dataStatus": "stale",
            "catalogBlockers": ["season cache expired"],
            "replacementCandidates": [],
        }

        class StaleGearStore:
            def get_websim_gear(self, class_key, spec_key, compact=False):
                return stale_payload

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
                "WOW_ALLOW_SQLITE_PUBLIC_CACHE_FALLBACK": "1",
            },
        ), patch.object(self.backend, "cache_data_store", return_value=StaleGearStore()), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only gear must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only gear must not open SQLite"),
        ):
            payload = self.backend.runtime_websim_gear_payload("mage", "frost", compact=True)

        self.assertIs(payload, stale_payload)

    def test_pg_only_runtime_returns_blocked_talent_payload_without_sqlite_fallback(self):
        blocked_payload = {
            "schemaRevision": "websim-talents-v1",
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": "spellslinger",
            "dataStatus": "blocked",
            "talentStatus": "blocked",
            "nodes": [],
            "blockers": ["PostgreSQL talent cache is missing verified nodes"],
        }

        class BlockedTalentStore:
            def get_websim_talents(self, class_key, spec_key, hero_key=""):
                return blocked_payload

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "cache_data_store", return_value=BlockedTalentStore()), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only talents must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only talents must not open SQLite"),
        ):
            payload = self.backend.runtime_websim_talents_payload("mage", "frost", "spellslinger")

        self.assertIs(payload, blocked_payload)

    def test_pg_only_runtime_returns_blocked_talent_import_without_sqlite_fallback(self):
        class EmptyTalentImportStore:
            def get_websim_talent_import(self, class_key, spec_key, hero_key=""):
                return {}

        with patch.dict(
            os.environ,
            {
                "WOW_DATABASE_URL": "postgresql://wow_app@localhost/wow_test",
                "WOW_DATABASE_RUNTIME": "postgres_only",
            },
        ), patch.object(self.backend, "cache_data_store", return_value=EmptyTalentImportStore()), patch.object(
            self.backend,
            "init_db",
            side_effect=AssertionError("PG-only talent import must not initialize SQLite"),
        ), patch.object(
            self.backend,
            "db_connection",
            side_effect=AssertionError("PG-only talent import must not open SQLite"),
        ):
            payload = self.backend.runtime_websim_talent_import_payload("mage", "frost", "spellslinger")

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("PostgreSQL talent import cache is missing", payload["blockers"])

    def test_admin_gates_record_detail_uses_postgres_runtime_store_when_available(self):
        class FakeContentStore:
            def admin_gate_news_records(self):
                return {"discoveryQueue": [], "articles": []}

        class FakeCacheStore:
            def admin_gate_talent_records(self):
                return {"communityTalentTemplates": [], "talentTrees": []}

            def admin_gate_gear_records(self):
                return {
                    "gearVariants": [
                        {
                            "id": "pg-variant-detail",
                            "itemId": "item-pg-detail",
                            "itemName": "PG detail item",
                            "slot": "head",
                            "label": "Mythic",
                            "sourceType": "dungeon",
                            "difficultyKey": "mythic",
                            "itemLevel": 678,
                            "status": "verified",
                            "blockers": [],
                            "payload": {"simcOptions": {"ilevel": 678}},
                            "updatedAt": "2026-06-30T00:04:00+00:00",
                        }
                    ]
                }

        with patch.object(self.backend, "content_data_store", return_value=FakeContentStore()), patch.object(
            self.backend, "cache_data_store", return_value=FakeCacheStore()
        ):
            payload = self.backend.admin_gate_record_detail_payload("gear", "gear_variant", "pg-variant-detail")

        self.assertEqual(payload["record"]["targetId"], "pg-variant-detail")
        self.assertEqual(payload["record"]["evidence"]["runtimeStore"], "postgres_cache")

    def test_admin_gates_diagnosis_uses_postgres_ops_store_when_available(self):
        class FakeContentStore:
            def admin_gate_news_records(self):
                return {"discoveryQueue": [], "articles": []}

        class FakeCacheStore:
            def admin_gate_talent_records(self):
                return {"communityTalentTemplates": [], "talentTrees": []}

            def admin_gate_gear_records(self):
                return {
                    "gearVariants": [
                        {
                            "id": "pg-variant-2",
                            "itemId": "item-pg-2",
                            "itemName": "PG blocked item",
                            "slot": "finger1",
                            "label": "Partial",
                            "sourceType": "dungeon",
                            "difficultyKey": "mythic",
                            "itemLevel": 678,
                            "status": "blocked",
                            "blockers": ["missing simc options"],
                            "payload": {},
                            "updatedAt": "2026-06-30T00:04:00+00:00",
                        }
                    ]
                }

        class FakeOpsStore:
            def __init__(self):
                self.created_entries = []

            def create_admin_gate_diagnosis(self, entry, audit_payload):
                self.created_entries.append((entry, audit_payload))
                return {
                    **entry,
                    "id": "pg-diagnosis-1",
                    "payload": {},
                    "createdAt": entry["createdAt"],
                    "updatedAt": entry["updatedAt"],
                }

        fake_ops = FakeOpsStore()
        with patch.object(self.backend, "content_data_store", return_value=FakeContentStore()), patch.object(
            self.backend, "cache_data_store", return_value=FakeCacheStore()
        ), patch.object(self.backend, "ops_data_store", return_value=fake_ops, create=True):
            diagnosis = self.backend.create_admin_gate_diagnosis(
                {
                    "targetDomain": "gear",
                    "targetType": "gear_variant",
                    "targetId": "pg-variant-2",
                    "diagnosis": "system_gap_suspected",
                    "gapType": "parser_or_mapping_bug",
                    "reason": "owner believes this blocked PG variant should be rechecked",
                },
                actor="owner",
            )

        self.assertEqual(diagnosis["id"], "pg-diagnosis-1")
        self.assertEqual(fake_ops.created_entries[0][0]["targetId"], "pg-variant-2")
        self.assertEqual(fake_ops.created_entries[0][1]["targetStatus"], "blocked")

    def test_admin_gates_diagnosis_records_gap_without_mutating_source_status(self):
        with self.backend.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO websim_community_gear_templates (
                    id, class_key, spec_key, name, source_key,
                    source_name, source_url, source_status, status, signature,
                    source_refs_json, gear_items_json, raw_string, ready_slot_count,
                    missing_slots_json, analysis_window, payload_json, updated_at,
                    expires_at, scan_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "gear-template-1",
                    "warrior",
                    "arms",
                    "武器战社区装备",
                    "raiderio",
                    "Raider.IO",
                    "https://raider.io/example",
                    "partial",
                    "blocked",
                    "sig-gear-1",
                    json.dumps([{"sourceKey": "raiderio", "status": "partial"}]),
                    json.dumps([{"slot": "main_hand", "itemId": 1}]),
                    "main_hand=valid_weapon,id=1",
                    1,
                    json.dumps(["off_hand"]),
                    "2026-W26",
                    json.dumps({"gearBySlot": {"main_hand": {"itemId": 1}}}),
                    "2026-06-29T00:00:00+00:00",
                    "",
                    "scan-1",
                ),
            )
            conn.commit()

        diagnosis = self.backend.create_admin_gate_diagnosis(
            {
                "targetDomain": "gear_templates",
                "targetType": "community_gear_template",
                "targetId": "gear-template-1",
                "diagnosis": "system_gap_suspected",
                "gapType": "parser_or_mapping_bug",
                "reason": "owner believes serializer rejected a valid weapon mapping",
                "note": "Check arms warrior main hand mapping.",
            },
            actor="owner",
        )

        with self.backend.db_connection() as conn:
            status_row = conn.execute(
                "SELECT source_status, status FROM websim_community_gear_templates WHERE id = ?",
                ("gear-template-1",),
            ).fetchone()
            diagnosis_count = conn.execute("SELECT COUNT(*) FROM admin_gate_diagnoses").fetchone()[0]
            audit_count = conn.execute(
                "SELECT COUNT(*) FROM ops_audit_logs WHERE action = ? AND target_id = ?",
                ("admin_gate.diagnose", "gear-template-1"),
            ).fetchone()[0]

        self.assertEqual(diagnosis["resolutionStatus"], "open")
        self.assertEqual(status_row, ("partial", "blocked"))
        self.assertEqual(diagnosis_count, 1)
        self.assertEqual(audit_count, 1)

    def test_admin_gates_queue_and_diagnoses_resolve_when_system_status_passes(self):
        with self.backend.db_connection() as conn:
            conn.execute(
                """
                INSERT INTO websim_community_gear_templates (
                    id, class_key, spec_key, name, source_key,
                    source_name, source_url, source_status, status, signature,
                    source_refs_json, gear_items_json, raw_string, ready_slot_count,
                    missing_slots_json, analysis_window, payload_json, updated_at,
                    expires_at, scan_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "gear-template-2",
                    "warrior",
                    "arms",
                    "武器战社区装备",
                    "raiderio",
                    "Raider.IO",
                    "https://raider.io/example",
                    "partial",
                    "blocked",
                    "sig-gear-2",
                    json.dumps([{"sourceKey": "raiderio", "status": "partial"}]),
                    "[]",
                    "",
                    0,
                    json.dumps(["main_hand"]),
                    "2026-W26",
                    "{}",
                    "2026-06-29T00:00:00+00:00",
                    "",
                    "scan-1",
                ),
            )
            conn.commit()

        self.backend.create_admin_gate_diagnosis(
            {
                "targetDomain": "gear_templates",
                "targetType": "community_gear_template",
                "targetId": "gear-template-2",
                "diagnosis": "system_gap_suspected",
                "gapType": "parser_or_mapping_bug",
                "reason": "owner found a likely false blocker",
            },
            actor="owner",
        )
        queue_before = self.backend.admin_gate_queue_payload({"domain": ["gear_templates"]})
        self.assertTrue(any(item["targetId"] == "gear-template-2" for item in queue_before["items"]))

        with self.backend.db_connection() as conn:
            conn.execute(
                """
                UPDATE websim_community_gear_templates
                SET source_status = 'verified', status = 'complete', missing_slots_json = '[]'
                WHERE id = ?
                """,
                ("gear-template-2",),
            )
            conn.commit()

        queue_after = self.backend.admin_gate_queue_payload({"domain": ["gear_templates"]})
        diagnoses = self.backend.admin_gate_diagnoses_payload({})

        self.assertFalse(any(item["targetId"] == "gear-template-2" for item in queue_after["items"]))
        resolved = next(item for item in diagnoses["items"] if item["targetId"] == "gear-template-2")
        self.assertEqual(resolved["resolutionStatus"], "resolved")

    def test_admin_gates_page_exposes_governance_navigation(self):
        html = self.backend.admin_gates_page()

        self.assertIn("门禁治理台", html)
        self.assertIn("待诊断阻断项", html)
        self.assertNotIn("验证 gap 诊断队列", html)
        self.assertNotIn('class="right"', html)
        self.assertIn('id="queueView"', html)
        self.assertIn('data-admin-gate-view="queue"', html)
        self.assertIn('id="recordsView" class="view" data-admin-gate-view="records"', html)
        self.assertIn("const recordsNavs = ['news', 'talents', 'gear', 'gearTemplates'];", html)
        self.assertNotIn("const recordsNavs = ['overview', 'news', 'talents', 'gear'];", html)
        self.assertIn(".view.active.stack { display:grid; }", html)
        self.assertIn(".stack { gap:14px; }", html)
        self.assertNotIn("\n    .stack { display:grid;", html)
        self.assertIn("function loadQueue()", html)
        self.assertIn("function applyAdminGateView", html)
        self.assertNotIn("data.diagnosticQueue.items.map", html)
        self.assertNotIn("const tasks = [loadSummary(), loadQueue(), loadDiagnoses()];", html)
        self.assertIn("const tasks = [loadSummary()];", html)
        self.assertIn("if (currentAdminGateNav === 'queue') tasks.push(loadQueue());", html)
        self.assertIn("if (currentAdminGateNav === 'diagnoses') tasks.push(loadDiagnoses());", html)
        self.assertIn("verified（已验证）", html)
        self.assertIn("blocked（已阻断）", html)
        self.assertIn("missing_credentials（缺少凭据）", html)
        self.assertIn("pending_official_audit（待官方校验）", html)
        self.assertIn("source_reference（仅作参考）", html)
        self.assertIn("function statusText", html)
        self.assertIn("function severityText", html)
        self.assertNotIn("微信扫码登录", html)
        self.assertNotIn("/api/admin/auth/status", html)
        self.assertNotIn("/api/admin/auth/wechat-url", html)
        self.assertNotIn("adminSessionAuthenticated", html)
        self.assertIn("/api/admin/gates/summary", html)
        self.assertIn("function escapeHtml(value)", html)
        self.assertIn("请输入固定 WOW_ADMIN_TOKEN", html)
        self.assertIn("保存后会写入当前浏览器本机存储", html)
        self.assertIn("保存 token 到本机", html)
        self.assertIn("清除本机 token", html)
        self.assertIn("const ADMIN_TOKEN_STORAGE_KEY = 'wowAdminToken'", html)
        self.assertIn("localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY", html)
        self.assertIn("localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)", html)
        self.assertIn("loadSavedAdminToken()", html)
        self.assertIn("function showAdminGateError", html)
        self.assertIn("发布情况", html)
        self.assertIn("<th>分类</th>", html)
        self.assertIn('id="genericToolbar"', html)
        self.assertIn('id="newsToolbar"', html)
        self.assertIn('id="newsFilterKey"', html)
        self.assertIn('id="newsFilterValue"', html)
        self.assertIn('id="talentToolbar"', html)
        self.assertIn('id="talentFilterKey"', html)
        self.assertIn('id="talentFilterValue"', html)
        self.assertIn('id="gearToolbar"', html)
        self.assertIn('id="gearFilterKey"', html)
        self.assertIn('id="gearFilterValue"', html)
        self.assertIn('id="gearSourceInstanceValue"', html)
        self.assertIn(
            '<select id="gearFilterKey"><option value="dropSource">掉落来源</option><option value="itemType">装备分类</option><option value="visibility">小程序可见性</option></select>',
            html,
        )
        self.assertNotIn(
            '<select id="gearFilterKey"><option value="dropSource">掉落来源</option><option value="class">职业</option><option value="visibility">小程序可见性</option></select>',
            html,
        )
        self.assertIn('id="gearTemplateToolbar"', html)
        self.assertIn('id="gearTemplateFilterKey"', html)
        self.assertIn('id="gearTemplateFilterValue"', html)
        self.assertIn("const newsFilterOptions", html)
        self.assertIn("const talentFilterOptions", html)
        self.assertIn("const gearFilterOptions", html)
        self.assertIn("const gearTemplateFilterOptions", html)
        self.assertIn("{ value:'category', label:'分类'", html)
        self.assertIn("{ value:'status', label:'状态'", html)
        self.assertIn("{ value:'publication', label:'发布情况'", html)
        self.assertIn("{ value:'class', label:'职业'", html)
        self.assertIn("{ value:'itemType', label:'装备分类'", html)
        self.assertIn("value:'visibility'", html)
        self.assertIn("label:'小程序可见性'", html)
        self.assertIn("正式服动态", html)
        self.assertIn("测试服前瞻", html)
        self.assertIn("职业强度变化", html)
        self.assertIn("战士", html)
        self.assertIn("法师", html)
        self.assertIn("萨满祭司", html)
        self.assertIn("已可见", html)
        self.assertIn("未发布", html)
        self.assertIn("function updateNewsFilterValueOptions", html)
        self.assertIn("function updateTalentFilterValueOptions", html)
        self.assertIn("function updateGearFilterValueOptions", html)
        self.assertIn("function updateGearSourceInstanceOptions", html)
        self.assertIn("function updateGearTemplateFilterValueOptions", html)
        self.assertIn("function applyRecordToolbarForDomain", html)
        self.assertIn("function applyNewsFilterParams", html)
        self.assertIn("function applyTalentFilterParams", html)
        self.assertIn("function applyGearFilterParams", html)
        self.assertIn("sourceInstance", html)
        self.assertIn("function applyGearTemplateFilterParams", html)
        self.assertIn("document.getElementById('newsLoad').addEventListener", html)
        self.assertIn("document.getElementById('talentLoad').addEventListener", html)
        self.assertIn("document.getElementById('gearLoad').addEventListener", html)
        self.assertIn("document.getElementById('gearTemplateLoad').addEventListener", html)
        self.assertIn("function newsCategoryCell", html)
        self.assertIn("articleCategory", html)
        self.assertIn("function talentCategoryCell", html)
        self.assertIn("talentCategory", html)
        self.assertIn("function gearCategoryCell", html)
        self.assertIn("function gearItemTypeCell", html)
        self.assertIn("gearCategory", html)
        self.assertIn("gearVisibility", html)
        self.assertIn("gearBlockReason", html)
        self.assertIn("装备名称", html)
        self.assertIn("<th>装备名称</th><th>部位</th><th>掉落来源</th>", html)
        self.assertNotIn("<th>模块</th><th>装备名称</th>", html)
        self.assertNotIn("${escapeHtml(item.targetType)} / ${escapeHtml(item.targetId)}</span></td><td>${gearSlotCell(item)}</td>", html)
        self.assertIn("function gearVariantListCell", html)
        self.assertIn("function gearSourceDetailWithoutInstance", html)
        self.assertIn("部位", html)
        self.assertIn("掉落来源", html)
        self.assertIn("装备分类", html)
        self.assertIn("护甲类型", html)
        self.assertIn("武器类型", html)
        self.assertIn("首饰", html)
        self.assertIn("<th>状态</th><th>装备分类</th><th>小程序可见</th>", html)
        self.assertNotIn("<th>状态</th><th>职业</th><th>小程序可见</th>", html)
        self.assertIn("Block原因", html)
        self.assertIn("装备模板", html)
        self.assertIn("小程序是否可见", html)
        self.assertIn("装备库记录", html)
        self.assertIn("装备模板记录", html)
        self.assertIn('id="field"', html)
        self.assertIn("const adminGateFilterFields", html)
        self.assertIn("function updateAdminGateFilterControls", html)
        self.assertIn("全部展示字段", html)
        self.assertIn("{ value:'talentTemplate', label:'天赋模板'", html)
        self.assertIn("{ value:'class', label:'职业'", html)
        self.assertIn("{ value:'source', label:'来源'", html)
        self.assertIn("{ value:'blocked', label:'是否被阻断'", html)
        self.assertIn("{ value:'blockReason', label:'阻断原因'", html)
        self.assertIn("{ value:'visibility', label:'小程序可见'", html)
        self.assertIn("社区来源", html)
        self.assertIn("天赋模板记录", html)
        self.assertNotIn("天赋树记录", html)
        self.assertNotIn("基础目录", html)
        self.assertIn("小程序可见", html)
        self.assertIn("阻断原因", html)
        self.assertIn("function talentPublicationCell", html)
        self.assertIn("function talentBlockReasonCell", html)
        self.assertIn("talentPublication", html)
        self.assertIn("talentBlockReason", html)
        self.assertIn("发布时间", html)
        self.assertIn("抓取时间", html)
        self.assertIn("未发布原因", html)
        self.assertIn("function newsPublicationCell", html)
        self.assertIn('id="pageSize"', html)
        self.assertIn('id="prevPage"', html)
        self.assertIn('id="nextPage"', html)
        self.assertIn('id="paginationSummary"', html)
        self.assertIn("const ADMIN_GATE_DEFAULT_PAGE_SIZE = 20", html)
        self.assertIn("function resetAdminGatePage", html)
        self.assertIn("function renderRecordsPagination", html)
        self.assertIn("params.set('page'", html)
        self.assertIn("params.set('pageSize'", html)

    def test_admin_gates_page_navigation_filters_record_domains(self):
        html = self.backend.admin_gates_page()

        self.assertIn("data-admin-gate-nav", html)
        self.assertIn("document.getElementById('nav').addEventListener('click'", html)
        self.assertIn("const domainByNavKey = { news:'news', talents:'talents', gear:'gear', gearTemplates:'gear_templates' }", html)
        self.assertIn("document.getElementById('domain').value = domain", html)
        self.assertIn("selectAdminGateNav(item.dataset.adminGateNav)", html)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from server.news_translator import localize_article, localize_visible_terms, visible_translation_issues


ARTICLE = {
    "id": "article-1",
    "title": "Travel to Val and Naigtal to Quell Leaders of the Void",
    "summary": "Join the fight against the Void in a new World of Warcraft update.",
    "channel": "正式服动态",
    "category": "正式服",
    "tags": [],
    "importance": 80,
    "sourceName": "Blizzard News",
    "sourceUrl": "https://worldofwarcraft.blizzard.com/news/24270001/travel-to-val-and-naigtal",
    "publishedAt": "2026-06-08",
    "sourceNote": "Blizzard official listing.",
}

ARTICLE_WITH_BLOCKS = dict(
    ARTICLE,
    bodyBlocks=[
        {"type": "paragraph", "text": "Blizzard has posted a new hotfix article."},
        {"type": "heading", "text": "Classes"},
        {"type": "list", "items": ["Druid: Fixed a Guardian issue.", "Warrior: Adjusted set bonuses."]},
    ],
)


class NewsTranslatorTest(unittest.TestCase):
    def test_localize_article_prefers_valid_llm_translation(self):
        localized = localize_article(
            ARTICLE,
            translate_with_llm=lambda article: {
                "title": "前往瓦尔与奈格塔尔，平息虚空首领威胁",
                "summary": "暴雪发布新的《魔兽世界》内容更新，玩家将前往新区域迎战虚空势力。",
                "bodyZh": "中文正文：这条资讯介绍了新的虚空主题内容更新，并保留原文链接供玩家核对。\n\n玩家可以从正文中了解新区域、主要敌人、活动目标和后续版本变化。",
                "tagItems": [
                    {"id": "content-update", "label": "内容更新"},
                    {"id": "unknown", "label": "未知标签"},
                ],
            },
            require_llm=True,
        )

        self.assertEqual(localized["title"], "前往瓦尔与奈格塔尔，平息虚空首领威胁")
        self.assertIn("内容更新", localized["summary"])
        self.assertNotIn("中文正文：", localized["bodyZh"])
        self.assertEqual(localized["contentStatus"], "ready")
        self.assertEqual(localized["translationStatus"], "llm")
        self.assertEqual(localized["tagItems"], [{"id": "content-update", "label": "内容更新"}])
        self.assertEqual(localized["originalTitle"], ARTICLE["title"])
        self.assertIn("Join the fight", localized["originalSummary"])

    def test_localize_article_requires_llm_body_blocks_when_source_has_blocks(self):
        localized = localize_article(
            ARTICLE_WITH_BLOCKS,
            translate_with_llm=lambda article: {
                "title": "官方热修发布新的职业修正说明",
                "summary": "暴雪发布新的《魔兽世界》热修说明，覆盖职业问题和套装修正。",
                "bodyBlocksZh": [
                    {"type": "paragraph", "text": "暴雪发布了一篇新的官方热修文章，说明正式服近期修正。"},
                    {"type": "heading", "text": "职业"},
                    {"type": "list", "items": ["德鲁伊：修正守护相关问题。", "战士：调整套装加成。"]},
                ],
                "tagItems": [{"id": "hotfix", "label": "热修"}, {"id": "unknown", "label": "未知"}],
            },
            require_llm=True,
        )

        self.assertEqual(localized["contentStatus"], "ready")
        self.assertEqual(localized["translationStatus"], "llm")
        self.assertEqual(localized["bodyBlocksZh"][1], {"type": "heading", "text": "职业"})
        self.assertIn("德鲁伊", localized["bodyZh"])
        self.assertEqual(localized["tagItems"], [{"id": "hotfix", "label": "热修"}])
        self.assertEqual(localized["translationFidelity"], "source_translation")

    def test_localize_article_blocks_llm_body_block_count_mismatch(self):
        localized = localize_article(
            ARTICLE_WITH_BLOCKS,
            translate_with_llm=lambda article: {
                "title": "官方热修发布新的职业修正说明",
                "summary": "暴雪发布新的《魔兽世界》热修说明，覆盖职业问题和套装修正。",
                "bodyBlocksZh": [
                    {"type": "paragraph", "text": "这里只翻译了一个段落，丢失了后续标题和列表。"},
                ],
                "tagItems": [{"id": "hotfix", "label": "热修"}],
            },
            require_llm=True,
        )

        self.assertEqual(localized["contentStatus"], "blocked")
        self.assertEqual(localized["blockedReason"], "invalid_llm_translation")

    def test_localize_article_blocks_llm_when_source_body_is_only_forum_excerpt(self):
        calls = []

        localized = localize_article(
            dict(
                ARTICLE,
                sourceName="Blizzard Forums",
                sourceUrl="https://us.forums.blizzard.com/en/wow/t/feedback-midnight-season-2-class-sets/2317455",
                originalTitle="Feedback: Midnight Season 2 Class Sets",
                originalSummary="We are excited to share the new set bonuses coming in Midnight Season 2.",
                originalBody="We are excited to share the new set bonuses coming in Midnight Season 2.",
                bodyBlocks=[
                    {
                        "type": "paragraph",
                        "text": "We are excited to share the new set bonuses coming in Midnight Season 2.",
                    }
                ],
                bodySourceKind="forum_excerpt",
            ),
            translate_with_llm=lambda article: calls.append(article) or {
                "title": "反馈：Midnight 第二赛季职业套装",
                "summary": "暴雪分享了 Midnight 第二赛季职业套装奖励。",
                "bodyBlocksZh": [
                    {
                        "type": "paragraph",
                        "text": "我们很高兴分享 Midnight 第二赛季即将推出的新套装奖励。",
                    }
                ],
                "tagItems": [{"id": "ptr", "label": "测试服"}],
            },
            require_llm=True,
        )

        self.assertEqual(localized["contentStatus"], "blocked")
        self.assertEqual(localized["blockedReason"], "source_body_missing")
        self.assertEqual(calls, [])

    def test_localize_article_falls_back_when_llm_translation_is_not_chinese_enough(self):
        localized = localize_article(
            ARTICLE,
            translate_with_llm=lambda article: {
                "title": "Travel to Val and Naigtal to Quell Leaders of the Void",
                "summary": "",
                "bodyZh": "",
            },
            require_llm=True,
        )

        self.assertEqual(localized["contentStatus"], "blocked")
        self.assertEqual(localized["translationStatus"], "blocked")
        self.assertEqual(localized["blockedReason"], "invalid_llm_translation")

    def test_localize_article_blocks_llm_required_article_when_llm_is_unavailable(self):
        localized = localize_article(ARTICLE, translate_with_llm=None, require_llm=True)

        self.assertEqual(localized["contentStatus"], "blocked")
        self.assertEqual(localized["translationStatus"], "blocked")
        self.assertEqual(localized["blockedReason"], "llm_not_configured")

    def test_localize_article_accepts_seed_article_with_complete_chinese_body(self):
        localized = localize_article(
            dict(
                ARTICLE,
                title="前往瓦尔与奈格塔尔，平息虚空首领威胁",
                summary="暴雪发布新的《魔兽世界》内容更新，玩家将前往新区域迎战虚空势力。",
                bodyZh="中文正文：这条资讯介绍了新的虚空主题内容更新。\n\n玩家可以从正文中了解新区域、主要敌人、活动目标和后续版本变化。",
                originalTitle=ARTICLE["title"],
                tagItems=[{"id": "content-update", "label": "内容更新"}],
                contentStatus="ready",
            )
        )

        self.assertEqual(localized["contentStatus"], "ready")
        self.assertEqual(localized["translationStatus"], "seed")
        self.assertEqual(localized["tagItems"], [{"id": "content-update", "label": "内容更新"}])

    def test_visible_translation_issues_reports_untranslated_display_fields(self):
        issues = visible_translation_issues(
            [
                {
                    "id": "good",
                    "title": "官方热修：2026 年 6 月 3 日",
                    "summary": "这里会列出解决《魔兽世界》Midnight 相关问题的官方热修。",
                    "bodyZh": "官方热修说明列出了《魔兽世界》Midnight 相关问题的修正内容，涵盖职业、任务和系统交互等正式服条目。\n\n部分热修会在部署后立即生效，另一些修正可能需要服务器重启后才会完整体现。",
                    "originalTitle": "Hotfixes: June 3, 2026",
                    "tagItems": [{"id": "hotfix", "label": "热修"}],
                    "contentStatus": "ready",
                    "translationStatus": "llm",
                    "translationFidelity": "source_translation",
                },
                {
                    "id": "bad",
                    "title": "Travel to Val and Naigtal to Quell Leaders of the Void",
                    "summary": "Join the fight against the Void in a new World of Warcraft update.",
                    "bodyZh": "中文正文：This article still has too many English words in visible text.",
                    "originalTitle": "",
                    "tagItems": [],
                    "contentStatus": "ready",
                },
            ]
        )

        self.assertGreaterEqual(len(issues), 5)
        self.assertTrue({"title", "summary", "bodyZh", "originalTitle", "tagItems"}.issubset({issue["field"] for issue in issues}))
        self.assertTrue(all(issue["id"] == "bad" for issue in issues))

    def test_localize_visible_terms_translates_common_wow_news_terms_inside_chinese_text(self):
        text = "官方公布六月 Trading Post 奖励，完成 Traveler's Log 可获得 Flame-Painted Sun Roc，并查看 Omnium Folio 与 WoW Ambassadors。"

        localized = localize_visible_terms(text)

        self.assertIn("商栈", localized)
        self.assertIn("旅行者日志", localized)
        self.assertIn("焰绘太阳洛克", localized)
        self.assertIn("全能典籍", localized)
        self.assertIn("魔兽大使", localized)
        self.assertNotIn("Trading Post", localized)
        self.assertNotIn("Traveler's Log", localized)
        self.assertNotIn("Flame-Painted Sun Roc", localized)

    def test_translate_article_with_llm_truncates_long_original_fields(self):
        import server.news_translator as translator

        captured = {}

        def fake_call(system_prompt, prompt, **kwargs):
            captured["prompt"] = prompt
            return {
                "called": True,
                "model": "test",
                "content": '{"title":"中文标题","summary":"中文摘要","bodyZh":"中文正文"}',
                "error": "",
            }

        long_article = dict(
            ARTICLE,
            originalTitle="T" * 500,
            originalSummary="S" * 3000,
            originalBody="B" * 9000,
        )
        with patch.object(translator, "llm_configured", return_value=True), patch.object(
            translator,
            "call_chat_completion",
            side_effect=fake_call,
        ):
            translator.translate_article_with_llm(long_article)

        self.assertLess(len(captured["prompt"]), 5200)
        self.assertIn("[truncated]", captured["prompt"])
        self.assertNotIn("B" * 4000, captured["prompt"])
        self.assertIn("逐块忠实翻译", captured["prompt"])
        self.assertNotIn("完整改写", captured["prompt"])

    def test_translate_article_with_llm_translates_source_body_blocks_in_chunks(self):
        import server.news_translator as translator

        source_blocks = [
            {"type": "paragraph", "text": f"Source paragraph {index}."}
            for index in range(7)
        ]
        calls = []

        def fake_call(system_prompt, prompt, **kwargs):
            calls.append(prompt)
            if "正文块 JSON" not in prompt:
                return {
                    "called": True,
                    "model": "test",
                    "content": '{"title":"官方原文标题直译","summary":"这是一段官方摘要的中文直译。","tagItems":[{"id":"content-update","label":"内容更新"}]}',
                    "error": "",
                }
            chunk_json = prompt.split("正文块 JSON：", 1)[1].strip()
            chunk_size = len(__import__("json").loads(chunk_json))
            blocks = [
                {"type": "paragraph", "text": f"来源段落 {index} 的中文直译。"}
                for index in range(chunk_size)
            ]
            return {
                "called": True,
                "model": "test",
                "content": __import__("json").dumps({"bodyBlocksZh": blocks}, ensure_ascii=False),
                "error": "",
            }

        with patch.object(translator, "llm_configured", return_value=True), patch.object(
            translator,
            "call_chat_completion",
            side_effect=fake_call,
        ), patch.object(translator, "BODY_BLOCK_CHUNK_SIZE", 3, create=True):
            payload = translator.translate_article_with_llm(dict(ARTICLE_WITH_BLOCKS, bodyBlocks=source_blocks))

        self.assertEqual(payload["title"], "官方原文标题直译")
        self.assertEqual(len(payload["bodyBlocksZh"]), 7)
        self.assertEqual(len(calls), 4)
        self.assertTrue(all("[truncated]" not in call for call in calls if "正文块 JSON" in call))

    def test_translate_article_with_llm_accepts_array_chunks_and_preserves_source_types(self):
        import server.news_translator as translator

        source_blocks = [
            {"type": "heading", "text": "Travel to Val and Naigtal"},
            {"type": "list", "items": ["Unlock the Omnium Folio.", "Face Rotmire."]},
        ]

        def fake_call(system_prompt, prompt, **kwargs):
            if "正文块 JSON" not in prompt:
                return {
                    "called": True,
                    "model": "test",
                    "content": '{"title":"官方内容更新直译","summary":"这是一段官方正文摘要的中文直译。","tagItems":[{"id":"content-update","label":"内容更新"}]}',
                    "error": "",
                }
            return {
                "called": True,
                "model": "test",
                "content": __import__("json").dumps(
                    [
                        {"type": "paragraph", "text": "前往瓦尔和奈格塔尔，阻止虚空势力的首领继续推进他们的计划。"},
                        {"type": "paragraph", "text": "解锁全能典籍，获得新的战斗力量。\n面对 Rotmire，挑战位于 Harandar 的单 Boss 团队副本。"},
                    ],
                    ensure_ascii=False,
                ),
                "error": "",
            }

        with patch.object(translator, "llm_configured", return_value=True), patch.object(
            translator,
            "call_chat_completion",
            side_effect=fake_call,
        ):
            payload = translator.translate_article_with_llm(dict(ARTICLE_WITH_BLOCKS, bodyBlocks=source_blocks))

        self.assertEqual(
            payload["bodyBlocksZh"],
            [
                {"type": "heading", "text": "前往瓦尔和奈格塔尔，阻止虚空势力的首领继续推进他们的计划。"},
                {
                    "type": "list",
                    "items": [
                        "解锁全能典籍，获得新的战斗力量。",
                        "面对 Rotmire，挑战位于 Harandar 的单 Boss 团队副本。",
                    ],
                },
            ],
        )

    def test_translate_article_with_llm_retries_failed_chunks_as_single_blocks(self):
        import server.news_translator as translator

        source_blocks = [
            {"type": "paragraph", "text": "Source paragraph 1."},
            {"type": "paragraph", "text": "Source paragraph 2."},
        ]
        body_calls = []

        def fake_call(system_prompt, prompt, **kwargs):
            if "正文块 JSON" not in prompt:
                return {
                    "called": True,
                    "model": "test",
                    "content": '{"title":"官方内容更新直译","summary":"这是一段官方正文摘要的中文直译。","tagItems":[{"id":"content-update","label":"内容更新"}]}',
                    "error": "",
                }
            body_calls.append(prompt)
            chunk_json = prompt.split("正文块 JSON：", 1)[1].strip()
            chunk = __import__("json").loads(chunk_json)
            if len(chunk) > 1:
                return {
                    "called": True,
                    "model": "test",
                    "content": '{"bodyBlocksZh":[]}',
                    "error": "",
                }
            return {
                "called": True,
                "model": "test",
                "content": __import__("json").dumps(
                    {"bodyBlocksZh": [{"type": "paragraph", "text": f"{chunk[0]['text']} 中文直译。"}]},
                    ensure_ascii=False,
                ),
                "error": "",
            }

        with patch.object(translator, "llm_configured", return_value=True), patch.object(
            translator,
            "call_chat_completion",
            side_effect=fake_call,
        ), patch.object(translator, "BODY_BLOCK_CHUNK_SIZE", 2, create=True):
            payload = translator.translate_article_with_llm(dict(ARTICLE_WITH_BLOCKS, bodyBlocks=source_blocks))

        self.assertEqual(len(payload["bodyBlocksZh"]), 2)
        self.assertEqual(len(body_calls), 3)

    def test_translate_article_with_llm_returns_none_for_non_object_metadata_response(self):
        import server.news_translator as translator

        with patch.object(translator, "llm_configured", return_value=True), patch.object(
            translator,
            "call_chat_completion",
            return_value={"called": True, "model": "test", "content": "[]", "error": ""},
        ):
            payload = translator.translate_article_with_llm(ARTICLE_WITH_BLOCKS)

        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()

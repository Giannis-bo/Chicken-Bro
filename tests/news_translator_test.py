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


class NewsTranslatorTest(unittest.TestCase):
    def test_localize_article_prefers_valid_llm_translation(self):
        localized = localize_article(
            ARTICLE,
            translate_with_llm=lambda article: {
                "title": "前往瓦尔与奈格塔尔，平息虚空首领威胁",
                "summary": "暴雪发布新的《魔兽世界》内容更新，玩家将前往新区域迎战虚空势力。",
                "bodyZh": "中文正文：这条资讯介绍了新的虚空主题内容更新，并保留原文链接供玩家核对。",
            },
        )

        self.assertEqual(localized["title"], "前往瓦尔与奈格塔尔，平息虚空首领威胁")
        self.assertIn("内容更新", localized["summary"])
        self.assertIn("中文正文", localized["bodyZh"])
        self.assertEqual(localized["originalTitle"], ARTICLE["title"])
        self.assertIn("Join the fight", localized["originalSummary"])

    def test_localize_article_falls_back_when_llm_translation_is_not_chinese_enough(self):
        localized = localize_article(
            ARTICLE,
            translate_with_llm=lambda article: {
                "title": "Travel to Val and Naigtal to Quell Leaders of the Void",
                "summary": "",
                "bodyZh": "",
            },
        )

        self.assertRegex(localized["title"], r"[\u4e00-\u9fff]")
        self.assertNotIn("Travel to Val", localized["title"])
        self.assertRegex(localized["summary"], r"[\u4e00-\u9fff]")
        self.assertIn("中文正文", localized["bodyZh"])

    def test_visible_translation_issues_reports_untranslated_display_fields(self):
        issues = visible_translation_issues(
            [
                {
                    "id": "good",
                    "title": "官方热修：2026 年 6 月 3 日",
                    "summary": "这里会列出解决《魔兽世界》Midnight 相关问题的官方热修。",
                    "bodyZh": "中文正文：玩家可以查看本次更新的职业调整。",
                },
                {
                    "id": "bad",
                    "title": "Travel to Val and Naigtal to Quell Leaders of the Void",
                    "summary": "Join the fight against the Void in a new World of Warcraft update.",
                    "bodyZh": "中文正文：This article still has too many English words in visible text.",
                },
            ]
        )

        self.assertEqual(len(issues), 3)
        self.assertEqual({issue["field"] for issue in issues}, {"title", "summary", "bodyZh"})
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


if __name__ == "__main__":
    unittest.main()

import unittest

from server.news_collector import merge_articles, parse_blizzard_news_html, parse_feed_articles


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Wowhead Retail News</title>
    <item>
      <title>Midnight Revelations PTR Development Notes - Class Tuning</title>
      <link>https://www.wowhead.com/news/midnight-revelations-ptr-development-notes-999001</link>
      <description><![CDATA[Blizzard has posted new PTR development notes with class tuning.]]></description>
      <pubDate>Tue, 09 Jun 2026 10:15:00 GMT</pubDate>
    </item>
    <item>
      <title>June Trading Post Rewards Now Available</title>
      <link>https://www.wowhead.com/news/june-trading-post-rewards-999002</link>
      <description>Monthly reward rotation for World of Warcraft players.</description>
      <pubDate>Mon, 08 Jun 2026 18:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

BLIZZARD_HTML_SAMPLE = """
<article class="NewsBlog">
  <div class="NewsBlog-title">Hotfixes: June 3, 2026</div>
  <p class="NewsBlog-desc color-beige-medium font-size-xSmall">Here you will find a list of hotfixes that address various issues related to World of Warcraft: Midnight.</p>
  <div class="NewsBlog-date LocalizedDateMount" data-props="{&quot;iso8601&quot;:&quot;2026-06-06T00:45:17.264Z&quot;,&quot;relative&quot;:true}">3 days ago</div>
  <a class="Link NewsBlog-link" href="/news/24276957/hotfixes-june-3-2026"></a>
</article>
"""


class NewsCollectorTest(unittest.TestCase):
    def test_parse_blizzard_news_html_extracts_official_articles(self):
        articles = parse_blizzard_news_html(BLIZZARD_HTML_SAMPLE)

        self.assertEqual(len(articles), 1)
        self.assertIn("官方热修", articles[0]["title"])
        self.assertIn("魔兽世界", articles[0]["summary"])
        self.assertNotIn("Here you will find", articles[0]["summary"])
        self.assertIn("中文正文", articles[0]["bodyZh"])
        self.assertEqual(articles[0]["originalTitle"], "Hotfixes: June 3, 2026")
        self.assertIn("Here you will find", articles[0]["originalBody"])
        self.assertEqual(articles[0]["publishedAt"], "2026-06-06")
        self.assertEqual(articles[0]["sourceName"], "Blizzard News")
        self.assertEqual(
            articles[0]["sourceUrl"],
            "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
        )
        self.assertEqual(articles[0]["channel"], "职业强度变化")
        self.assertIn("class-change", articles[0]["tags"])

    def test_classification_does_not_treat_classic_as_class_change(self):
        articles = parse_blizzard_news_html(
            """
            <article class="NewsBlog">
              <div class="NewsBlog-title">Mists of Pandaria Classic: Siege of Orgrimmar Raid Now Live</div>
              <p class="NewsBlog-desc color-beige-medium font-size-xSmall">The Siege of Orgrimmar raid is now open for players.</p>
              <div class="NewsBlog-date LocalizedDateMount" data-props="{&quot;iso8601&quot;:&quot;2026-06-04T18:00:00.000Z&quot;}">June 4</div>
              <a class="Link NewsBlog-link" href="/news/24252017/mists-of-pandaria-classic-siege-of-orgrimmar-raid-now-live"></a>
            </article>
            """
        )

        self.assertEqual(articles[0]["channel"], "正式服动态")
        self.assertNotIn("class-change", articles[0]["tags"])

    def test_parse_feed_articles_keeps_source_evidence_and_classifies_channels(self):
        articles = parse_feed_articles(
            RSS_SAMPLE,
            {
                "sourceName": "Wowhead",
                "sourceUrl": "https://www.wowhead.com/news/rss/retail",
                "sourceNote": "Wowhead Retail RSS feed.",
                "baseImportance": 70,
            },
        )

        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["channel"], "测试服前瞻")
        self.assertIn("ptr", articles[0]["tags"])
        self.assertIn("class-change", articles[0]["tags"])
        self.assertEqual(articles[0]["publishedAt"], "2026-06-09")
        self.assertEqual(articles[0]["sourceName"], "Wowhead")
        self.assertEqual(
            articles[0]["sourceUrl"],
            "https://www.wowhead.com/news/midnight-revelations-ptr-development-notes-999001",
        )
        self.assertIn("Wowhead Retail RSS feed", articles[0]["sourceNote"])

        self.assertEqual(articles[1]["channel"], "正式服动态")
        self.assertEqual(articles[1]["publishedAt"], "2026-06-08")

    def test_merge_articles_dedupes_by_source_url_and_prefers_collected_updates(self):
        seed = [
            {
                "id": "old",
                "title": "Old title",
                "summary": "Old summary",
                "channel": "正式服动态",
                "category": "正式服",
                "tags": [],
                "importance": 10,
                "sourceName": "Wowhead",
                "sourceUrl": "https://www.wowhead.com/news/june-trading-post-rewards-999002",
                "publishedAt": "2026-06-01",
                "sourceNote": "Old source note.",
            }
        ]
        collected = parse_feed_articles(
            RSS_SAMPLE,
            {
                "sourceName": "Wowhead",
                "sourceUrl": "https://www.wowhead.com/news/rss/retail",
                "sourceNote": "Wowhead Retail RSS feed.",
                "baseImportance": 70,
            },
        )

        merged = merge_articles(seed, collected)

        self.assertEqual(len(merged), 2)
        by_url = {article["sourceUrl"]: article for article in merged}
        self.assertEqual(
            by_url["https://www.wowhead.com/news/june-trading-post-rewards-999002"]["title"],
            "六月 商栈 奖励 现已上线",
        )
        self.assertEqual(
            by_url["https://www.wowhead.com/news/june-trading-post-rewards-999002"]["originalTitle"],
            "June Trading Post Rewards Now Available",
        )

    def test_merge_articles_dedupes_blizzard_articles_by_article_number(self):
        seed = [
            {
                "id": "seed-hotfix",
                "title": "官方 Hotfixes 更新至 2026 年 6 月 3 日",
                "summary": "官方热修列表更新。",
                "channel": "职业强度变化",
                "category": "正式服",
                "tags": ["class-change"],
                "importance": 96,
                "sourceName": "Blizzard News",
                "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news/24276957/hotfixes-june-3-2026",
                "publishedAt": "2026-06-03",
                "sourceNote": "官方来源。",
            }
        ]
        collected = [
            {
                "id": "collected-hotfix",
                "title": "Hotfixes: June 3, 2026",
                "summary": "Official hotfix list.",
                "channel": "职业强度变化",
                "category": "正式服",
                "tags": ["class-change"],
                "importance": 92,
                "sourceName": "Blizzard News",
                "sourceUrl": "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
                "publishedAt": "2026-06-06",
                "sourceNote": "Blizzard official listing.",
            }
        ]

        merged = merge_articles(seed, collected)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["sourceUrl"], "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026")

    def test_trading_post_title_translation_is_case_insensitive(self):
        articles = parse_blizzard_news_html(
            """
            <article class="NewsBlog">
              <div class="NewsBlog-title">TAKE A Midsummer Stroll over to the June Trading Post</div>
              <p class="NewsBlog-desc color-beige-medium font-size-xSmall">Monthly rewards are now available.</p>
              <div class="NewsBlog-date LocalizedDateMount" data-props="{&quot;iso8601&quot;:&quot;2026-05-28T18:00:00.000Z&quot;}">May 28</div>
              <a class="Link NewsBlog-link" href="/news/24271859/take-a-midsummer-stroll-over-to-the-june-trading-post"></a>
            </article>
            """
        )

        self.assertIn("来一场", articles[0]["title"])
        self.assertIn("前往", articles[0]["title"])

    def test_unknown_english_titles_use_chinese_display_fallback(self):
        articles = parse_blizzard_news_html(
            """
            <article class="NewsBlog">
              <div class="NewsBlog-title">Travel to Val and Naigtal to Quell Leaders of the Void</div>
              <p class="NewsBlog-desc color-beige-medium font-size-xSmall">Join the fight against the Void in a new World of Warcraft update.</p>
              <div class="NewsBlog-date LocalizedDateMount" data-props="{&quot;iso8601&quot;:&quot;2026-06-08T18:00:00.000Z&quot;}">June 8</div>
              <a class="Link NewsBlog-link" href="/news/24270001/travel-to-val-and-naigtal"></a>
            </article>
            """
        )

        self.assertRegex(articles[0]["title"], r"[\u4e00-\u9fff]")
        self.assertNotIn("Travel to Val", articles[0]["title"])
        self.assertEqual(articles[0]["originalTitle"], "Travel to Val and Naigtal to Quell Leaders of the Void")


if __name__ == "__main__":
    unittest.main()

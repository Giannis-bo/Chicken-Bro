import unittest

from server.news_collector import merge_articles, parse_blizzard_article_html, parse_blizzard_news_html, parse_feed_articles


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

BLIZZARD_DETAIL_HTML_SAMPLE = """
<html>
  <head><title>Hotfixes: June 3, 2026 - WoW</title></head>
  <body>
    <main>
      <h1>Hotfixes: June 3, 2026</h1>
      <div class="ArticleDetail-date LocalizedDateMount" data-props="{&quot;iso8601&quot;:&quot;2026-06-06T00:45:17.264Z&quot;}"></div>
      <article>
        <p>Here you will find a list of hotfixes that address various issues related to World of Warcraft: Midnight.</p>
        <h2>Classes</h2>
        <ul>
          <li>Druid: Fixed an issue with Guardian Druid Apex Talent interactions.</li>
          <li>Warrior: Adjusted several class set bonuses.</li>
        </ul>
        <p>Some of the hotfixes below take effect the moment they were implemented, while others may require scheduled realm restarts.</p>
      </article>
    </main>
    <script>window.__data = "ignored";</script>
  </body>
</html>
"""


class NewsCollectorTest(unittest.TestCase):
    def test_parse_blizzard_article_html_extracts_complete_original_body(self):
        detail = parse_blizzard_article_html(
            BLIZZARD_DETAIL_HTML_SAMPLE,
            "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
        )

        self.assertEqual(detail["originalTitle"], "Hotfixes: June 3, 2026")
        self.assertEqual(detail["publishedAt"], "2026-06-06")
        self.assertIn("Classes", detail["originalBody"])
        self.assertIn("Guardian Druid", detail["originalBody"])
        self.assertIn("scheduled realm restarts", detail["originalBody"])
        self.assertNotIn("window.__data", detail["originalBody"])
        self.assertEqual(
            detail["bodyBlocks"],
            [
                {
                    "type": "paragraph",
                    "text": "Here you will find a list of hotfixes that address various issues related to World of Warcraft: Midnight.",
                },
                {"type": "heading", "text": "Classes"},
                {
                    "type": "list",
                    "items": [
                        "Druid: Fixed an issue with Guardian Druid Apex Talent interactions.",
                        "Warrior: Adjusted several class set bonuses.",
                    ],
                },
                {
                    "type": "paragraph",
                    "text": "Some of the hotfixes below take effect the moment they were implemented, while others may require scheduled realm restarts.",
                },
            ],
        )

    def test_parse_blizzard_news_html_extracts_official_articles(self):
        articles = parse_blizzard_news_html(
            BLIZZARD_HTML_SAMPLE,
            detail_pages={
                "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026": BLIZZARD_DETAIL_HTML_SAMPLE
            },
        )

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Hotfixes: June 3, 2026")
        self.assertEqual(articles[0]["summary"], "Here you will find a list of hotfixes that address various issues related to World of Warcraft: Midnight.")
        self.assertTrue(articles[0]["requiresLlmTranslation"])
        self.assertEqual(articles[0]["originalTitle"], "Hotfixes: June 3, 2026")
        self.assertIn("Guardian Druid", articles[0]["originalBody"])
        self.assertEqual(articles[0]["bodyBlocks"][1]["type"], "heading")
        self.assertEqual(articles[0]["bodyBlocks"][2]["type"], "list")
        self.assertEqual(articles[0]["publishedAt"], "2026-06-06")
        self.assertEqual(articles[0]["sourceName"], "Blizzard News")
        self.assertEqual(
            articles[0]["sourceUrl"],
            "https://worldofwarcraft.blizzard.com/news/24276957/hotfixes-june-3-2026",
        )
        self.assertEqual(articles[0]["channel"], "职业强度变化")
        self.assertIn("class-change", articles[0]["tags"])
        self.assertIn("hotfix", articles[0]["tags"])

    def test_parse_blizzard_news_html_honors_article_limit_before_detail_fetch(self):
        articles = parse_blizzard_news_html(BLIZZARD_HTML_SAMPLE + BLIZZARD_HTML_SAMPLE, max_articles=1)

        self.assertEqual(len(articles), 1)

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
            "June Trading Post Rewards Now Available",
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

    def test_trading_post_discovery_keeps_original_title_for_llm_translation(self):
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

        self.assertEqual(articles[0]["title"], "TAKE A Midsummer Stroll over to the June Trading Post")
        self.assertEqual(articles[0]["originalTitle"], "TAKE A Midsummer Stroll over to the June Trading Post")
        self.assertTrue(articles[0]["requiresLlmTranslation"])

    def test_unknown_english_titles_stay_original_until_translation_gate(self):
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

        self.assertEqual(articles[0]["title"], "Travel to Val and Naigtal to Quell Leaders of the Void")
        self.assertEqual(articles[0]["originalTitle"], "Travel to Val and Naigtal to Quell Leaders of the Void")
        self.assertTrue(articles[0]["requiresLlmTranslation"])

    def test_parse_feed_articles_marks_third_party_as_reference_only_discovery(self):
        articles = parse_feed_articles(
            RSS_SAMPLE,
            {
                "sourceId": "wowhead",
                "sourceName": "Wowhead",
                "sourceUrl": "https://www.wowhead.com/news/rss/retail",
                "sourceNote": "Wowhead Retail RSS feed.",
                "sourceTier": "trusted_media",
                "licenseStatus": "reference_only",
                "baseImportance": 70,
            },
        )

        self.assertEqual(articles[0]["sourceId"], "wowhead")
        self.assertEqual(articles[0]["sourceTier"], "trusted_media")
        self.assertEqual(articles[0]["licenseStatus"], "reference_only")
        self.assertEqual(articles[0]["contentStatus"], "discovered")


if __name__ == "__main__":
    unittest.main()

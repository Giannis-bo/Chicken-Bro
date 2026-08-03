from datetime import datetime, timezone
import unittest


NOW = datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)
APPROVED_SOURCES = [
    {
        "type": "blizzard_html",
        "sourceId": "blizzard",
        "sourceName": "Blizzard News",
        "sourceTier": "official",
        "licenseStatus": "approved",
        "sourceUrl": "https://worldofwarcraft.blizzard.com/en-us/news",
    },
    {
        "type": "blizzard_forum",
        "sourceId": "blizzard-forums",
        "sourceName": "Blizzard Forums",
        "sourceTier": "official",
        "licenseStatus": "approved",
        "sourceUrl": "https://us.forums.blizzard.com/en/wow/c/in-development",
    },
]
THIRD_PARTY_SOURCE = {
    "type": "rss_reference",
    "sourceId": "wowhead",
    "sourceName": "Wowhead",
    "sourceTier": "trusted_media",
    "licenseStatus": "reference_only",
    "sourceUrl": "https://www.wowhead.com/news/rss/retail",
}


def current_ptr_holy_paladin_frame():
    return {
        "schemaRevision": "chickenbro-question-frame-v1",
        "questionType": "current_research",
        "subject": {"classKey": "paladin", "specKey": "holy", "resolution": "resolved"},
        "scope": {"productPhase": "ptr", "patchVersion": "12.1", "region": "cn", "scenarioKey": ""},
        "evidenceNeeds": ["official_current_changes", "comparative_strength_signal"],
        "unresolvedFields": ["scenarioKey"],
    }


def official_article(**overrides):
    article = {
        "id": "official-holy-paladin-121",
        "sourceId": "blizzard-forums",
        "sourceName": "Blizzard Forums",
        "sourceTier": "official",
        "licenseStatus": "approved",
        "sourceUrl": "https://us.forums.blizzard.com/en/wow/t/patch-121-ptr/123",
        "title": "12.1 PTR Development Notes: Holy Paladin",
        "summary": "Holy Paladin receives an adjustment for PTR testing.",
        "originalBody": "Holy Paladin: an ability has been adjusted in this PTR build.",
        "publishedAt": "2026-08-03T09:45:00+00:00",
        "versionEvent": {"productPhase": "ptr", "patchVersion": "12.1"},
    }
    article.update(overrides)
    return article


class ChickenbroCurrentSourcesTest(unittest.TestCase):
    def _builder(self):
        try:
            from server.chickenbro_current_sources import build_current_wow_sources_tool_result
        except ImportError as error:
            self.fail(f"current official source adapter must exist: {error}")
        return build_current_wow_sources_tool_result

    def test_matching_official_ptr_subject_returns_compact_source_reference(self):
        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [],
            collector=lambda *_args, **_kwargs: ([official_article()], []),
            approved_sources=APPROVED_SOURCES,
            now=NOW,
        )

        self.assertEqual("current_wow_sources", result["sourceKey"])
        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["current.blizzard-forums.official-holy-paladin-121"], result["evidenceRefs"])
        self.assertEqual("official_change", result["facts"][0]["kind"])
        self.assertEqual("12.1", result["facts"][0]["patchVersion"])
        self.assertIn("comparative_strength_signal_missing", result["limitations"])
        self.assertNotIn("allowedNumbers", result)

    def test_patch_version_comparison_ignores_trailing_zero_components(self):
        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [],
            collector=lambda *_args, **_kwargs: ([official_article(versionEvent={"productPhase": "ptr", "patchVersion": "12.1.0"})], []),
            approved_sources=APPROVED_SOURCES,
            now=NOW,
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["current.blizzard-forums.official-holy-paladin-121"], result["evidenceRefs"])

    def test_phase_level_official_fact_is_partial_not_a_strength_verdict(self):
        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [],
            collector=lambda *_args, **_kwargs: ([official_article(title="12.1 PTR Development Notes: Warriors", summary="Warrior tuning.", originalBody="Warrior changes.")], []),
            approved_sources=APPROVED_SOURCES,
            now=NOW,
        )

        self.assertEqual("partial", result["status"])
        self.assertEqual([], result["evidenceRefs"])
        self.assertIn("subject_specific_official_change_missing", result["limitations"])
        self.assertNotIn("rank", str(result).lower())
        self.assertNotIn("dps", str(result).lower())

    def test_unapproved_source_is_ignored_even_when_it_mentions_the_subject(self):
        third_party_article = official_article(
            sourceId="wowhead",
            sourceName="Wowhead",
            sourceTier="trusted_media",
            licenseStatus="reference_only",
            sourceUrl="https://www.wowhead.com/news/123",
        )
        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [third_party_article],
            collector=lambda *_args, **_kwargs: ([], []),
            approved_sources=[*APPROVED_SOURCES, THIRD_PARTY_SOURCE],
            now=NOW,
        )

        self.assertEqual("failed", result["status"])
        self.assertEqual([], result["evidence"])
        self.assertIn("current_source_unavailable", result["limitations"])

    def test_spoofed_official_source_id_cannot_authorize_an_arbitrary_host(self):
        spoofed = official_article(sourceUrl="https://not-blizzard.example/ptr-notes")
        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [dict(spoofed, checkedAt="2026-08-03T09:55:00+00:00")],
            collector=lambda *_args, **_kwargs: ([], []),
            approved_sources=APPROVED_SOURCES,
            now=NOW,
        )

        self.assertEqual("failed", result["status"])
        self.assertEqual([], result["evidenceRefs"])

    def test_collector_timeout_is_a_literal_failed_source_state(self):
        def timed_out(*_args, **_kwargs):
            raise TimeoutError("official source budget exhausted")

        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [],
            collector=timed_out,
            approved_sources=APPROVED_SOURCES,
            now=NOW,
        )

        self.assertEqual("failed", result["status"])
        self.assertEqual([], result["facts"])
        self.assertIn("current_source_timeout", result["limitations"])

    def test_matching_fresh_official_fact_avoids_an_unnecessary_network_collect(self):
        cached = official_article(checkedAt="2026-08-03T09:55:00+00:00")

        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [cached],
            collector=lambda *_args, **_kwargs: self.fail("fresh source fact should not collect again"),
            approved_sources=APPROVED_SOURCES,
            now=NOW,
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["current.blizzard-forums.official-holy-paladin-121"], result["evidenceRefs"])

    def test_collector_receives_only_approved_sources_one_article_and_fixed_budget(self):
        observed = {}

        def collector(sources, timeout, max_articles_per_source):
            observed["sources"] = sources
            observed["timeout"] = timeout
            observed["maxArticles"] = max_articles_per_source
            return ([official_article()], [])

        result = self._builder()(
            current_ptr_holy_paladin_frame(),
            article_loader=lambda: [],
            collector=collector,
            approved_sources=[*APPROVED_SOURCES, THIRD_PARTY_SOURCE],
            now=NOW,
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual({"blizzard", "blizzard-forums"}, {source["sourceId"] for source in observed["sources"]})
        self.assertEqual(2, observed["timeout"])
        self.assertEqual(1, observed["maxArticles"])


if __name__ == "__main__":
    unittest.main()

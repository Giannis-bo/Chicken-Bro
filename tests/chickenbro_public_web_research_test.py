import importlib
import unittest
from unittest import mock


COMMUNITY_METRICS_PAGE = """
<html><head><title>Current Game Role Build | Community</title></head>
<body>
<h1>Current Game Role Build</h1>
<p>Last updated: 19 hours ago Total Parses: 760 Based on all keys 7 and above in the last 14 days.</p>
<p>Keystone Level +20</p>
</body></html>
"""


DUCKDUCKGO_ANOMALY_PAGE = """
<html><body><div class="anomaly-modal__box">Please complete the check.</div></body></html>
"""


BING_RESULTS_PAGE = """
<html><body><ol>
  <li class="b_algo"><h2><a href="https://community.example/current-mythic">Current M+ community sample</a></h2></li>
</ol></body></html>
"""


class ChickenbroPublicWebResearchTest(unittest.TestCase):
    def setUp(self):
        module = importlib.import_module("server.chickenbro_public_web_research")
        module.reset_public_web_research_state()
        self.module = module

    def test_generic_research_reads_search_hits_without_provider_specific_logic(self):
        result = self.module.build_public_web_research_tool_result(
            {"target": "current game role strength community evidence"},
            searcher=lambda _query, timeout_seconds=None: [
                {"title": "Community PTR build", "url": "https://community.example/blood-ptr", "snippet": "PTR M+ sample"},
            ],
            fetcher=lambda _url, timeout_seconds=None: COMMUNITY_METRICS_PAGE,
            checked_at_factory=lambda: "2026-08-04T12:00:00+00:00",
        )

        self.assertEqual("public_web_research", result["sourceKey"])
        self.assertEqual("source_reference", result["status"])
        self.assertEqual(["public-web:community-example-blood-ptr"], result["evidenceRefs"])
        fact = result["facts"][0]
        self.assertEqual("community.example", fact["sourceHost"])
        self.assertIn("Total Parses: 760", fact["summary"])
        self.assertIn("760", result["allowedNumbers"])
        self.assertIn("+20", result["allowedNumbers"])
        self.assertEqual("2026-08-04T12:00:00+00:00", result["evidence"][0]["checkedAt"])
        self.assertNotIn("<html>", str(result))
        self.assertNotIn("provider-specific", str(result).lower())

    def test_default_search_falls_back_when_the_primary_public_search_page_is_challenged(self):
        with mock.patch.object(
            self.module,
            "_read_url",
            side_effect=[DUCKDUCKGO_ANOMALY_PAGE, BING_RESULTS_PAGE],
        ) as reader:
            hits = self.module._default_searcher("current game role strength")

        self.assertEqual(["https://community.example/current-mythic"], [item["url"] for item in hits])
        self.assertEqual(2, reader.call_count)
        self.assertIn("duckduckgo.com", reader.call_args_list[0].args[0])
        self.assertIn("bing.com", reader.call_args_list[1].args[0])

    def test_generic_research_refuses_private_or_non_https_search_hits_before_fetching(self):
        fetched = []
        result = self.module.build_public_web_research_tool_result(
            {"query": "current game strength"},
            searcher=lambda _query, timeout_seconds=None: [
                {"title": "loopback", "url": "http://127.0.0.1/private", "snippet": "must not fetch"},
                {"title": "local", "url": "https://localhost/private", "snippet": "must not fetch"},
            ],
            fetcher=lambda url, timeout_seconds=None: fetched.append(url),
        )

        self.assertEqual("partial", result["status"])
        self.assertEqual([], result["evidenceRefs"])
        self.assertEqual([], fetched)

    def test_public_reader_never_follows_a_redirect_after_validating_its_initial_target(self):
        self.assertIsNone(
            self.module._NoRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://127.0.0.1/private"
            )
        )

    def test_generic_research_can_read_a_codex_selected_safe_public_url_without_a_provider_adapter(self):
        selected = "https://community.example/blood-ptr"
        fetched = []
        result = self.module.build_public_web_research_tool_result(
            {"target": selected},
            searcher=lambda *_args, **_kwargs: self.fail("a direct public URL must not start a search"),
            fetcher=lambda url, timeout_seconds=None: (fetched.append(url), COMMUNITY_METRICS_PAGE)[1],
            checked_at_factory=lambda: "2026-08-04T12:00:00+00:00",
        )

        self.assertEqual("source_reference", result["status"])
        self.assertEqual([selected], fetched)
        self.assertEqual(["public-web:community-example-blood-ptr"], result["evidenceRefs"])

    def test_generic_research_returns_a_literal_partial_when_search_or_pages_have_no_readable_evidence(self):
        result = self.module.build_public_web_research_tool_result(
            {"query": "current game strength"},
            searcher=lambda _query, timeout_seconds=None: [],
        )

        self.assertEqual("partial", result["status"])
        self.assertEqual([], result["facts"])
        self.assertEqual([], result["evidenceRefs"])


if __name__ == "__main__":
    unittest.main()

import unittest
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import server.chickenbro_public_web_research as public_web
from server.chickenbro_public_web_research import (
    build_public_web_research_tool_result,
    reset_public_web_research_state,
)


URL = "https://example.com/guide"


class ChickenbroPublicWebResearchTest(unittest.TestCase):
    def setUp(self):
        reset_public_web_research_state()
        self.now = lambda: "2026-09-06T08:00:00+00:00"

    def read(self, page, intent=None, calls=None):
        calls = calls if calls is not None else []

        def fetcher(url, timeout_seconds=None):
            calls.append((url, timeout_seconds))
            return page

        return build_public_web_research_tool_result(
            intent or {"target": URL}, fetcher=fetcher, clock=lambda: 10,
            checked_at_factory=self.now,
        )

    def test_long_navigation_before_article_does_not_hide_relevant_body(self):
        navigation = "".join(f"<a>menu {index}</a>" for index in range(40))
        page = f"<html><body><nav>{navigation}</nav><main><article><h1>Enhancement guide</h1><p>Critical strike rises because this season's gear has dense secondary-stat budgets.</p></article></main></body></html>"
        result = self.read(page)
        self.assertEqual("source_reference", result["status"])
        self.assertIn("Critical strike rises", result["facts"][0]["summary"])
        self.assertNotIn("menu 0", result["facts"][0]["summary"])

    def test_javascript_shell_is_partial_without_evidence(self):
        page = "<html><head><title>Raider.IO</title></head><body><div id='app'></div><script>window.__BOOT__ = 1</script><!-- build 42 --></body></html>"
        result = self.read(page)
        self.assertEqual("partial", result["status"])
        self.assertEqual("JS_SHELL", result["reasonCode"])
        self.assertEqual([], result["facts"])
        self.assertEqual([], result["evidenceRefs"])
        self.assertTrue(result["nextActions"])

    def test_access_challenge_is_partial_without_evidence(self):
        result = self.read("<html><body><main><h1>Just a moment...</h1><p>Verify you are human to continue.</p></main></body></html>")
        self.assertEqual("ACCESS_CHALLENGE", result["reasonCode"])
        self.assertEqual([], result["evidence"])

    def test_article_discussing_challenge_terms_is_not_itself_a_challenge(self):
        result = self.read(
            "<article><h1>CAPTCHA troubleshooting</h1>"
            "<p>How to diagnose CAPTCHA and Access Denied errors safely.</p></article>"
        )
        self.assertEqual("source_reference", result["status"])
        self.assertIn("troubleshooting", result["facts"][0]["summary"])

    def test_script_challenge_token_does_not_poison_visible_article(self):
        page = "<article><h1>Guide</h1><p>Substantive guide text.</p></article><script>const captchaEndpoint='/captcha'</script>"
        result = self.read(page)
        self.assertEqual("source_reference", result["status"])
        self.assertIn("Substantive guide text", result["facts"][0]["summary"])

    def test_short_substantive_article_is_valid(self):
        result = self.read("<article><h1>Stat priority</h1><p>Critical strike improves proc frequency for this build.</p></article>")
        self.assertEqual("source_reference", result["status"])
        self.assertEqual("2026-09-06T08:00:00+00:00", result["evidence"][0]["checkedAt"])
        self.assertIn("proc frequency", result["facts"][0]["summary"])

    def test_page_made_only_of_navigation_links_has_no_facts(self):
        page = "<html><body><div><a href='/home'>Home</a><a href='/guides'>Guides</a><a href='/rankings'>Rankings</a></div></body></html>"
        result = self.read(page)
        self.assertEqual("partial", result["status"])
        self.assertEqual("NO_CONTENT", result["reasonCode"])
        self.assertEqual([], result["facts"])

    def test_continuation_metadata_reassembles_full_extracted_content(self):
        text = " ".join(f"paragraph-{index:04d}" for index in range(900))
        page = f"<main><p>{text}</p></main>"
        first = self.read(page)
        self.assertTrue(first["facts"][0]["truncated"])
        pages = [first]
        while pages[-1]["facts"][0]["nextStart"] is not None:
            pages.append(self.read(page, {"target": URL, "start": pages[-1]["facts"][0]["nextStart"]}))
        combined = "".join(item["facts"][0]["summary"] for item in pages)
        self.assertEqual(text, combined)
        self.assertEqual(first["facts"][0]["end"], pages[1]["facts"][0]["start"])
        self.assertEqual(len(text), pages[-1]["facts"][0]["totalChars"])
        self.assertFalse(pages[-1]["facts"][0]["truncated"])
        self.assertIsNone(pages[-1]["facts"][0]["nextStart"])

    def test_match_starts_snapshot_at_relevant_term(self):
        page = "<article><p>Opening context.</p><p>Critical Strike changes are explained here.</p><p>Closing context.</p></article>"
        result = self.read(page, {"target": URL, "match": "critical strike"})
        fact = result["facts"][0]
        self.assertGreater(fact["start"], 0)
        self.assertTrue(fact["summary"].startswith("Critical Strike"))

    def test_missing_match_returns_explicit_partial_without_evidence(self):
        result = self.read("<article>Readable guide content.</article>", {"target": URL, "match": "not present"})
        self.assertEqual("MATCH_NOT_FOUND", result["reasonCode"])
        self.assertEqual([], result["facts"])
        self.assertEqual([], result["evidenceRefs"])

    def test_start_at_or_after_end_returns_position_metadata(self):
        for start in (23, 999):
            reset_public_web_research_state()
            result = self.read("<article>Readable guide content.</article>", {"target": URL, "start": start})
            self.assertEqual("END_OF_CONTENT", result["reasonCode"])
            self.assertEqual(23, result["totalChars"])
            self.assertEqual(start, result["requestedStart"])
            self.assertEqual(23, result["end"])

    def test_invalid_offset_match_and_target_have_specific_reason_codes(self):
        for intent, code in (
            ({"target": URL, "start": -1}, "INVALID_START"),
            ({"target": URL, "start": True}, "INVALID_START"),
            ({"target": URL, "match": "x" * 121}, "INVALID_MATCH"),
            ({"target": "http://example.com"}, "INVALID_TARGET"),
            ({"target": "q" * 241}, "INVALID_QUERY"),
            ({"target": "https://example.com/" + "x" * 2050}, "INVALID_TARGET"),
            ({"target": "https://example.com:notaport/guide"}, "INVALID_TARGET"),
        ):
            with self.subTest(intent=intent):
                reset_public_web_research_state()
                self.assertEqual(code, self.read("<article>valid body text</article>", intent)["reasonCode"])

    def test_empty_body_and_read_error_are_distinct(self):
        empty = self.read("")
        reset_public_web_research_state()

        def broken_fetcher(url, timeout_seconds=None):
            raise TimeoutError("secret upstream detail")

        failed = build_public_web_research_tool_result(
            {"target": URL}, fetcher=broken_fetcher, clock=lambda: 10,
            checked_at_factory=self.now,
        )
        self.assertEqual("NO_CONTENT", empty["reasonCode"])
        self.assertEqual("READ_TIMEOUT", failed["reasonCode"])
        self.assertNotIn("secret", str(failed))

    def test_cache_key_includes_start_and_match_and_is_deterministic(self):
        calls = []
        page = "<article>alpha beta gamma delta</article>"
        first = self.read(page, {"target": URL, "start": 0}, calls)
        cached = self.read("different", {"target": URL, "start": 0}, calls)
        matched = self.read(page, {"target": URL, "match": "gamma"}, calls)
        self.assertEqual(first, cached)
        self.assertEqual(2, len(calls))
        self.assertTrue(matched["facts"][0]["summary"].startswith("gamma"))

    def test_default_reader_rejects_private_dns_before_connecting(self):
        private = [(2, 1, 6, "", ("127.0.0.1", 443))]
        with patch.object(public_web.socket, "getaddrinfo", return_value=private), patch.object(public_web, "_PinnedHTTPSConnection") as connection:
            with self.assertRaises(ValueError):
                public_web._read_url(URL)
        connection.assert_not_called()

    def test_default_reader_rejects_non_public_and_multicast_dns(self):
        for address in ("100.64.0.1", "224.0.0.1"):
            resolved = [(2, 1, 6, "", (address, 443))]
            with self.subTest(address=address), patch.object(
                public_web.socket, "getaddrinfo", return_value=resolved
            ), patch.object(public_web, "_PinnedHTTPSConnection") as connection:
                with self.assertRaises(ValueError):
                    public_web._read_url(URL)
                connection.assert_not_called()

    def test_default_reader_bounds_dns_resolution_time(self):
        def slow_dns(*args, **kwargs):
            sleep(2)
            return [(2, 1, 6, "", ("93.184.216.34", 443))]

        started = monotonic()
        with patch.object(public_web.socket, "getaddrinfo", side_effect=slow_dns):
            with self.assertRaises(TimeoutError):
                public_web._read_url(URL, timeout_seconds=1)
        self.assertLess(monotonic() - started, 1.5)

    def test_default_reader_refuses_redirect_and_oversize_response(self):
        class Response:
            def __init__(self, status, chunks):
                self.status = status
                self._chunks = iter(chunks)

            def read(self, size):
                return next(self._chunks, b"")

        class Connection:
            response = None

            def __init__(self, *args, **kwargs):
                self.sock = None

            def request(self, *args, **kwargs):
                return None

            def getresponse(self):
                return self.response

            def close(self):
                return None

        public_address = [(2, 1, 6, "", ("93.184.216.34", 443))]
        for response in (
            Response(302, [b""]),
            Response(200, [b"x" * (public_web.PUBLIC_WEB_MAX_RESPONSE_BYTES + 1), b""]),
        ):
            Connection.response = response
            with self.subTest(status=response.status), patch.object(public_web.socket, "getaddrinfo", return_value=public_address), patch.object(public_web, "_PinnedHTTPSConnection", Connection):
                with self.assertRaises(ValueError):
                    public_web._read_url(URL)

    def test_default_reader_enforces_overall_deadline(self):
        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = None

            def request(self, *args, **kwargs):
                return None

            def close(self):
                return None

        public_address = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch.object(public_web.socket, "getaddrinfo", return_value=public_address), patch.object(public_web, "_PinnedHTTPSConnection", Connection), patch.object(public_web, "monotonic", side_effect=[10, 16]):
            with self.assertRaises(TimeoutError):
                public_web._read_url(URL, timeout_seconds=5)

    def test_default_reader_interrupts_response_headers_at_deadline(self):
        interrupted = Event()

        class Socket:
            def shutdown(self, how):
                interrupted.set()

            def close(self):
                interrupted.set()

            def settimeout(self, timeout):
                return None

        class Connection:
            def __init__(self, *args, **kwargs):
                self.sock = Socket()

            def request(self, *args, **kwargs):
                return None

            def getresponse(self):
                interrupted.wait(2)
                raise OSError("socket closed")

            def close(self):
                return None

        public_address = [(2, 1, 6, "", ("93.184.216.34", 443))]
        started = monotonic()
        with patch.object(public_web.socket, "getaddrinfo", return_value=public_address), patch.object(
            public_web, "_PinnedHTTPSConnection", Connection
        ):
            with self.assertRaises(TimeoutError):
                public_web._read_url(URL, timeout_seconds=1)
        self.assertTrue(interrupted.is_set())
        self.assertLess(monotonic() - started, 1.5)

    def test_multiple_failed_hits_keep_reason_and_metadata_from_same_page(self):
        def searcher(query, timeout_seconds=None):
            return [{"url": "https://first.example/a"}, {"url": "https://second.example/b"}]

        def fetcher(url, timeout_seconds=None):
            return "<article>abcde</article>" if "first" in url else "<article>x</article>"

        result = build_public_web_research_tool_result(
            {"target": "bounded query", "start": 1, "match": "needle"},
            searcher=searcher, fetcher=fetcher, clock=lambda: 10,
            checked_at_factory=self.now,
        )
        self.assertEqual("MATCH_NOT_FOUND", result["reasonCode"])
        self.assertEqual("needle", result["match"])
        self.assertEqual(5, result["totalChars"])
        self.assertNotIn("end", result)

    def test_cache_cardinality_and_inflight_state_are_bounded(self):
        for index in range(public_web.PUBLIC_WEB_MAX_CACHE_ENTRIES + 5):
            public_web._finish_request(
                (f"https://example.com/guide-{index}", 0, ""), 10,
                {"status": "source_reference", "facts": [{"summary": str(index)}]},
            )
        self.assertEqual(public_web.PUBLIC_WEB_MAX_CACHE_ENTRIES, len(public_web._PUBLIC_WEB_CACHE))
        key = (URL.casefold(), 0, "")
        public_web._PUBLIC_WEB_INFLIGHT.add(key)
        result = self.read("<article>bounded cache content</article>")
        self.assertEqual("INFLIGHT", result["reasonCode"])


if __name__ == "__main__":
    unittest.main()

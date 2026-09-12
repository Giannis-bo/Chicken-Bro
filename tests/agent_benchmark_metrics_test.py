"""Evidence-preserving benchmark statistics; run with unittest discovery."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agent_benchmark_metrics import paired_summary, summarize_timing


def event(call, name, phase, at, **extra):
    return dict(id=call, type="tool", name=name, event=phase, atMs=at, **extra)


class TimingTests(unittest.TestCase):
    def test_native_mcp_and_web_search_events_and_simulation_job_polls(self):
        events = []
        for call, name, kind, begin, end in [
            ("a", "query_logs", "mcpToolCall", 0, 10),
            ("b", "webSearch", "webSearch", 5, 20),
            ("c", "get_simulation_job", "mcpToolCall", 30, 40),
            ("d", "get_simulation_job", "mcpToolCall", 50, 60),
        ]:
            for phase, at in [("start", begin), ("end", end)]:
                item = event(call, name, phase, at, args={"id": "job"})
                item["type"] = kind
                events.append(item)
        result = summarize_timing(events, 100)
        self.assertEqual(result["toolMs"], 40)
        self.assertEqual(result["toolCount"], 4)
        self.assertEqual(result["tools"]["get_simulation_job"]["count"], 2)
        self.assertEqual(result["repeatedQueries"], [])

    def test_parallel_union_and_unknown_are_not_summed_as_reasoning(self):
        result = summarize_timing([
            event("a", "query", "start", 10), event("b", "query", "start", 20),
            event("a", "query", "end", 40), event("b", "query", "end", 60),
            event("c", "get_simulation", "start", 80),
        ], 100)
        self.assertEqual(result["toolMs"], 50)
        self.assertEqual(result["tools"]["query"]["inclusiveMs"], 70)
        self.assertEqual(result["nonToolMs"], 50)
        self.assertEqual(result["tools"]["get_simulation"]["unknownCount"], 1)
        self.assertEqual(result["unknownTools"][0]["id"], "c")
        self.assertIsNone(result["modelRoundTrips"])

    def test_repeated_queries_use_canonical_args_and_exclude_polls_and_retries(self):
        starts = [
            event("a", "query_logs", "start", 0, args={"x": 1, "y": 2}),
            event("b", "query_logs", "start", 1, args={"y": 2, "x": 1}),
            event("c", "query_logs", "start", 2, args={"x": 1, "y": 3}),
            event("d", "query_logs", "start", 3, args={"x": 1, "y": 2}, retryOf="a"),
            event("e", "get_simulation", "start", 4, args={"id": "job"}),
            event("f", "get_simulation", "start", 5, args={"id": "job"}),
        ]
        result = summarize_timing(starts, 10)
        self.assertEqual(result["repeatedQueries"], [{"name": "query_logs", "args": {"x": 1, "y": 2}, "count": 2, "extraCount": 1}])

    def test_bad_intervals_are_flagged_without_negative_duration(self):
        result = summarize_timing([
            event("a", "query", "start", 30), event("a", "query", "end", 20),
            event("b", "query", "start", -1), event("c", "query", "end", 40),
        ], 100)
        self.assertEqual(result["toolMs"], 0)
        self.assertTrue(result["issues"])
        with self.assertRaises(ValueError):
            summarize_timing([], -1)

    def test_sorted_by_timestamp_but_duplicate_identity_is_not_silently_paired(self):
        result = summarize_timing([event("a", "q", "end", 20), event("a", "q", "start", 0)], 30)
        self.assertEqual(result["toolMs"], 20)
        self.assertTrue(result["issues"])
        duplicated = summarize_timing([event("a", "q", "start", 0), event("a", "q", "start", 1), event("a", "q", "end", 10)], 20)
        self.assertEqual(duplicated["toolMs"], 0)
        self.assertTrue(duplicated["issues"])


def run(case, variant, elapsed, **extra):
    return dict(caseId=case, variant=variant, trial=1, status="succeeded", totalMs=elapsed, quality="pass", **extra)


class PairedTests(unittest.TestCase):
    def test_pair_percent_median_and_category_counts(self):
        result = paired_summary([
            run("a", "old", 100, category="logs"), run("a", "new", 80, category="logs"),
            run("b", "old", 200, category="mechanics"), run("b", "new", 100, category="mechanics"),
        ])
        self.assertEqual(result["overall"]["pairedCount"], 2)
        self.assertEqual(result["overall"]["pairedMedianPercent"], -35)
        self.assertEqual(result["overall"]["oldMedianMs"], 150)
        self.assertEqual(result["categories"]["logs"]["pairedCount"], 1)
        self.assertNotIn("p90", str(result).lower())

    def test_failures_missing_quality_and_duplicates_are_preserved(self):
        failed = run("a", "new", 50)
        failed.update(status="timeout", quality="unreviewed")
        unreviewed = run("c", "new", 20)
        unreviewed["quality"] = "unreviewed"
        result = paired_summary([
            run("a", "old", 100), failed, run("b", "old", 100),
            run("c", "old", 100), unreviewed,
            run("d", "old", 100), run("d", "old", 101), run("d", "new", 80),
        ])
        self.assertEqual(result["overall"]["pairedCount"], 0)
        self.assertEqual(result["overall"]["runCount"], 8)
        self.assertEqual(result["overall"]["variants"]["new"]["statusCounts"]["timeout"], 1)
        self.assertEqual(len(result["exclusions"]), 4)
        self.assertIsNone(result["overall"]["pairedMedianPercent"])

    def test_zero_baseline_and_category_mismatch_do_not_produce_speedup(self):
        result = paired_summary([run("a", "old", 0), run("a", "new", 10),
                                 run("b", "old", 20, category="x"), run("b", "new", 10, category="y")])
        self.assertEqual(result["overall"]["pairedCount"], 0)
        self.assertEqual(len(result["exclusions"]), 2)


if __name__ == "__main__":
    unittest.main()

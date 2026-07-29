import json
import unittest

from server.sync_log_summary import (
    bounded_json_line,
    bounded_progress_event,
    sync_result_summary,
)


class SyncLogSummaryTest(unittest.TestCase):
    def test_large_nested_result_is_one_bounded_truthful_line(self):
        sentinel = "must-never-reach-journald"
        payload = {
            "websim": {
                "ok": False,
                "dataStatus": "partial",
                "runner": "postgres",
                "schemaRevision": "websim-v1",
                "gearItemCount": 1200,
                "blockedCount": 7,
                "errors": [f"{sentinel}-{index}" for index in range(500)],
                "profiles": [
                    {
                        "name": f"{sentinel}-{index}",
                        "rawPayload": sentinel * 100,
                    }
                    for index in range(1000)
                ],
            },
            "raiderio": {
                "sourceStatus": "verified",
                "runner": "postgres",
                "profileCount": 160,
                "rawResponse": sentinel * 1000,
            },
        }

        summary = sync_result_summary(
            payload,
            event="websim_sync_complete",
        )
        line = bounded_json_line(summary)
        decoded = json.loads(line)

        self.assertLessEqual(len(line.encode("utf-8")), 8192)
        self.assertNotIn(sentinel, line)
        self.assertEqual(decoded["status"], "partial")
        self.assertEqual(
            decoded["components"]["websim"]["status"],
            "partial",
        )
        self.assertEqual(
            decoded["components"]["websim"]["errorCount"],
            500,
        )
        self.assertEqual(
            decoded["components"]["websim"]["counts"]["gearItemCount"],
            1200,
        )
        self.assertEqual(
            decoded["components"]["raiderio"]["status"],
            "verified",
        )

    def test_blocked_status_is_not_promoted_by_verified_sibling(self):
        summary = sync_result_summary(
            {
                "raiderio": {
                    "sourceStatus": "verified",
                    "runner": "postgres",
                },
                "statWeights": {
                    "sourceStatus": "blocked",
                    "runner": "postgres",
                    "errors": ["sensitive provider error"],
                },
            },
            event="stat_weights_sync_complete",
        )

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(
            summary["components"]["statWeights"]["status"],
            "blocked",
        )
        self.assertEqual(
            summary["components"]["statWeights"]["errorCount"],
            1,
        )
        self.assertNotIn(
            "sensitive provider error",
            bounded_json_line(summary),
        )

    def test_nonempty_errors_prevent_ok_only_component_from_claiming_verified(self):
        summary = sync_result_summary(
            {
                "websim": {
                    "ok": True,
                    "runner": "postgres",
                    "errors": ["nonfatal but unresolved"],
                }
            },
            event="websim_sync_complete",
        )

        self.assertEqual(summary["status"], "partial")
        self.assertEqual(
            summary["components"]["websim"]["status"],
            "partial",
        )
        self.assertEqual(
            summary["components"]["websim"]["errorCount"],
            1,
        )

    def test_progress_event_keeps_stage_counts_and_drops_nested_details(self):
        sentinel = "raw-stage-payload"
        event = bounded_progress_event(
            {
                "event": "websim_sync_stage",
                "stage": "gear",
                "status": "blocked",
                "durationSeconds": 3.25,
                "errors": 4,
                "itemCount": 1200,
                "errorMessage": sentinel,
                "payload": {
                    "items": [sentinel] * 1000,
                },
            }
        )
        line = bounded_json_line(event)

        self.assertEqual(event["stage"], "gear")
        self.assertEqual(event["status"], "blocked")
        self.assertEqual(event["errors"], 4)
        self.assertEqual(event["itemCount"], 1200)
        self.assertNotIn(sentinel, line)


if __name__ == "__main__":
    unittest.main()

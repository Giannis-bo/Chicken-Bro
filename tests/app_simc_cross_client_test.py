import json
import unittest

from tests.app_chat_api_test import browser_session_headers, web_cookies, web_write_headers
from tests.app_simc_api_test import build_simc_test_client


class FormalSimcCrossClientTest(unittest.TestCase):
    def setUp(self):
        self.client, self.repository, self.queue = build_simc_test_client()
        self.snapshot = self.client.post(
            "/api/v2/simc/snapshots",
            headers=browser_session_headers(),
            json={"sourceUrl": "https://raider.io/characters/us/area-52/Stormsample"},
        ).json()

    def tearDown(self):
        self.client.close()

    def test_job_created_by_web_is_visible_to_browser_same_user(self):
        created = self.client.post(
            "/api/v2/simc/jobs",
            headers={**web_write_headers(), "Idempotency-Key": "cross-simc-1"},
            cookies=web_cookies(csrf=True),
            json={
                "snapshotId": self.snapshot["id"],
                "scenario": {"fightStyle": "Patchwerk", "desiredTargets": 1},
            },
        )
        listed = self.client.get("/api/v2/simc/jobs", headers=browser_session_headers())

        self.assertEqual(created.status_code, 202)
        self.assertEqual(listed.status_code, 200)
        self.assertIn(created.json()["id"], [row["id"] for row in listed.json()["items"]])
        self.assertEqual(len(self.queue.calls), 1)
        self.assertNotIn("profile", self.queue.calls[0]["payload"])

    def test_other_user_cannot_read_snapshot_job_or_enumerate_history(self):
        created = self.client.post(
            "/api/v2/simc/jobs",
            headers={**browser_session_headers(), "Idempotency-Key": "cross-simc-owner"},
            json={
                "snapshotId": self.snapshot["id"],
                "scenario": {"fightStyle": "Patchwerk", "desiredTargets": 1},
            },
        ).json()

        snapshot_read = self.client.get(
            f"/api/v2/simc/snapshots/{self.snapshot['id']}",
            headers=browser_session_headers(other=True),
        )
        job_read = self.client.get(
            f"/api/v2/simc/jobs/{created['id']}",
            headers=browser_session_headers(other=True),
        )
        listed = self.client.get("/api/v2/simc/jobs", headers=browser_session_headers(other=True))

        self.assertEqual(snapshot_read.status_code, 404)
        self.assertEqual(snapshot_read.json()["error"]["code"], "SNAPSHOT_NOT_FOUND")
        self.assertEqual(job_read.status_code, 404)
        self.assertEqual(job_read.json()["error"]["code"], "SIMULATION_NOT_FOUND")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"], [])

    def test_job_detail_is_bounded_and_hides_queue_worker_and_owner_fields(self):
        created = self.client.post(
            "/api/v2/simc/jobs",
            headers={**browser_session_headers(), "Idempotency-Key": "cross-simc-public"},
            json={
                "snapshotId": self.snapshot["id"],
                "scenario": {"fightStyle": "Patchwerk", "desiredTargets": 1},
            },
        ).json()
        detail = self.client.get(
            f"/api/v2/simc/jobs/{created['id']}",
            cookies=web_cookies(),
        )

        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertEqual(payload["attempts"], [])
        self.assertIsNone(payload["result"])
        encoded = json.dumps(payload)
        for forbidden in (
            "userId",
            "user_id",
            "workerId",
            "lease",
            "idempotency",
            "payloadJson",
            "stdout",
            "stderr",
            "profile\"",
        ):
            self.assertNotIn(forbidden, encoded)


if __name__ == "__main__":
    unittest.main()

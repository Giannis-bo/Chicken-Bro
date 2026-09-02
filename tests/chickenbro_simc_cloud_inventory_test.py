import unittest

from server.chickenbro_simc_cloud_inventory import build_inventory, capacity_gate


class ChickenbroSimcCloudInventoryTest(unittest.TestCase):
    def test_capacity_is_blocked_when_free_space_is_smaller_than_current_database(self):
        inventory = build_inventory(
            {
                "status": "reachable",
                "observedAt": "2026-09-02T08:00:00Z",
                "rootFreeBytes": 8_100_000_000,
                "currentDatabaseBytes": 15_000_000_000,
            }
        )

        self.assertEqual(
            inventory["capacityGate"],
            "blocked_until_independent_legacy_cleanup_or_storage_expansion",
        )

    def test_capacity_never_claims_ready_without_a_full_preflight(self):
        inventory = {
            "status": "reachable",
            "rootFreeBytes": 30_000_000_000,
            "currentDatabaseBytes": 15_000_000_000,
        }

        self.assertEqual(capacity_gate(inventory), "capacity_preflight_required")

    def test_unreachable_snapshot_cannot_make_a_capacity_claim(self):
        inventory = build_inventory(
            {
                "status": "unreachable",
                "observedAt": "2026-09-02T08:00:00Z",
                "rootFreeBytes": 0,
                "currentDatabaseBytes": 0,
                "probeErrors": [{"probe": "ssh", "errorCode": "connection_failed"}],
            }
        )

        self.assertEqual(inventory["capacityGate"], "unverified_unreachable")

    def test_output_rejects_secret_bearing_fields_at_any_depth(self):
        for forbidden in (
            {"databaseUrl": "postgresql://user:password@host/db"},
            {"nested": {"token": "abc"}},
            {"units": [{"environment": "WOW_WECHAT_SECRET=value"}]},
            {"cookie": "session=value"},
        ):
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "secret-bearing field"):
                    build_inventory(forbidden)

    def test_inventory_is_sorted_and_restricted_to_the_allowed_schema(self):
        inventory = build_inventory(
            {
                "status": "partial",
                "observedAt": "2026-09-02T08:00:00Z",
                "host": "wow-lighthouse",
                "rootFilesystem": {
                    "path": "/",
                    "sizeBytes": 100,
                    "usedBytes": 60,
                    "freeBytes": 40,
                },
                "rootFreeBytes": 40,
                "currentDatabaseBytes": 20,
                "databases": [
                    {"name": "wow_test", "sizeBytes": 12, "connections": 1},
                    {"name": "postgres", "sizeBytes": 8, "connections": 0},
                ],
                "units": [
                    {
                        "name": "wow-v2-worker.service",
                        "loadState": "loaded",
                        "activeState": "active",
                        "unitFileState": "enabled",
                    },
                    {
                        "name": "wow-backend.service",
                        "loadState": "loaded",
                        "activeState": "active",
                        "unitFileState": "enabled",
                    },
                ],
                "listeners": [
                    {"address": "127.0.0.53%lo", "port": 8790, "processName": "python3"},
                    {"address": "0.0.0.0", "port": 443, "processName": "nginx"},
                ],
                "directories": [
                    {"path": "/opt/wow-simc", "sizeBytes": 10},
                    {"path": "/opt/wow-mini-program", "sizeBytes": 30},
                ],
                "identities": [{"name": "simcCommit", "value": "a" * 40}],
                "probeErrors": [{"probe": "units", "errorCode": "partial_result"}],
            }
        )

        self.assertEqual(
            list(inventory),
            [
                "schemaVersion",
                "status",
                "observedAt",
                "host",
                "rootFilesystem",
                "rootFreeBytes",
                "currentDatabaseBytes",
                "databases",
                "units",
                "listeners",
                "directories",
                "identities",
                "probeErrors",
                "capacityGate",
            ],
        )
        self.assertEqual([row["name"] for row in inventory["databases"]], ["postgres", "wow_test"])
        self.assertEqual(
            [row["name"] for row in inventory["units"]],
            ["wow-backend.service", "wow-v2-worker.service"],
        )
        self.assertEqual([row["port"] for row in inventory["listeners"]], [443, 8790])
        self.assertEqual(
            [row["path"] for row in inventory["directories"]],
            ["/opt/wow-mini-program", "/opt/wow-simc"],
        )


if __name__ == "__main__":
    unittest.main()

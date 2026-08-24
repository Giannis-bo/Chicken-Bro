import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from server.s2_official_api_capture import (
    OfficialApiCaptureError,
    build_official_request_plan,
    capture_official_request_plan,
)
from server.s2_official_api_fact_snapshot import (
    validate_capture_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "capture-s2-official-api-fact-snapshot.py"
SCOPE_PATH = (
    ROOT
    / "server"
    / "data"
    / "midnight-season-2"
    / "s2-product-content-scope-v1.json"
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class FakeReader:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get(self, path, *, namespace, region, locale, query):
        call = {
            "path": path,
            "namespace": namespace,
            "region": region,
            "locale": locale,
            "query": dict(query),
        }
        self.calls.append(call)
        key = (path, tuple(sorted(query.items())))
        if key not in self.payloads:
            raise AssertionError(f"unexpected fake request: {key}")
        return self.payloads[key]


def payload_key(path, query=None):
    return (path, tuple(sorted((query or {}).items())))


class S2OfficialApiFactCaptureTest(unittest.TestCase):
    def test_request_plan_is_fixed_to_four_category_official_bootstrap(self):
        plan = build_official_request_plan(
            product_scope=load_json(SCOPE_PATH),
            reader=FakeReader({}),
            region="us",
            locale="en_US",
        )

        self.assertEqual(len(plan), 13)
        self.assertEqual(len({row["requestKey"] for row in plan}), 13)
        self.assertEqual(
            {row["path"] for row in plan},
            {
                "/data/wow/journal-instance/1030",
                "/data/wow/journal-instance/1041",
                "/data/wow/journal-instance/1202",
                "/data/wow/journal-instance/1304",
                "/data/wow/journal-instance/1309",
                "/data/wow/journal-instance/1311",
                "/data/wow/journal-instance/1313",
                "/data/wow/journal-instance/1322",
                "/data/wow/journal-instance/1317",
                "/data/wow/journal-instance/1320",
                "/data/wow/item-set/index",
                "/data/wow/profession/index",
                "/data/wow/mythic-keystone/season/index",
            },
        )
        for row in plan:
            self.assertNotIn("max", row["query"])
            self.assertNotIn("sample", row["query"])
            self.assertTrue(row["path"].startswith("/data/wow/"))

    def test_capture_expands_official_item_reference_and_writes_manifest(self):
        payloads = {
            payload_key("/data/wow/journal-instance/1030"): {
                "encounters": [
                    {
                        "name": "S2 Matched Set",
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/journal-encounter/1?namespace=static-us&locale=en_US"
                        }
                    }
                ]
            },
            payload_key("/data/wow/journal-encounter/1"): {
                "items": [
                    {
                        "item": {
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/item/123?namespace=static-us&locale=en_US"
                            }
                        }
                    }
                ]
            },
            payload_key("/data/wow/item/123"): {"id": 123, "name": "Fixture item"},
        }
        reader = FakeReader(payloads)
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/journal-instance/1030",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            result = capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
            )

            self.assertEqual(result["status"], "captured")
            manifest = load_json(Path(directory) / "capture-manifest.json")
            normalized = validate_capture_manifest(manifest)
            self.assertEqual(len(normalized["entries"]), 3)
            self.assertEqual(
                {call["path"] for call in reader.calls},
                {
                    "/data/wow/journal-instance/1030",
                    "/data/wow/journal-encounter/1",
                    "/data/wow/item/123",
                },
            )
            for entry in normalized["entries"]:
                self.assertTrue((Path(directory) / entry["responsePath"]).is_file())

    def test_capture_closes_pagination_without_a_page_limit(self):
        payloads = {
            payload_key("/data/wow/item-set/index", {"_page": 1}): {
                "page": 1,
                "pageCount": 2,
                "results": [],
            },
            payload_key("/data/wow/item-set/index", {"_page": 2}): {
                "page": 2,
                "pageCount": 2,
                "results": [],
            },
        }
        reader = FakeReader(payloads)
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/item-set/index",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {"_page": 1},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            result = capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
            )

        self.assertEqual(result["status"], "captured")
        self.assertEqual([call["query"]["_page"] for call in reader.calls], [1, 2])

    def test_request_failure_writes_blocked_sidecar_without_fake_manifest(self):
        class BrokenReader:
            def get(self, path, *, namespace, region, locale, query):
                raise RuntimeError("HTTP 404")

        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/profession/2915",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                OfficialApiCaptureError,
                "REQUEST_FAILED",
            ):
                capture_official_request_plan(
                    plan=plan,
                    output_root=Path(directory),
                    reader=BrokenReader(),
                    captured_at="2026-08-17T12:00:00Z",
                )
            failure = load_json(Path(directory) / "capture-failure.json")
            self.assertEqual(failure["status"], "blocked")
            self.assertEqual(failure["errorCode"], "S2_OFFICIAL_CAPTURE_REQUEST_FAILED")
            self.assertFalse((Path(directory) / "capture-manifest.json").exists())

    def test_non_blizzard_reference_is_rejected_fail_closed(self):
        reader = FakeReader(
            {
                payload_key("/data/wow/journal-instance/1030"): {
                    "encounters": [
                        {
                            "key": {
                                "href": "https://example.com/data/wow/journal-encounter/1"
                            }
                        }
                    ]
                }
            }
        )
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/journal-instance/1030",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                OfficialApiCaptureError,
                "official reference",
            ):
                capture_official_request_plan(
                    plan=plan,
                    output_root=Path(directory),
                    reader=reader,
                    captured_at="2026-08-17T12:00:00Z",
                )

    def test_item_set_index_does_not_expand_unmatched_historical_set_items(self):
        payloads = {
            payload_key("/data/wow/item-set/index"): {
                "item_sets": [
                    {
                        "name": "S2 Matched Set",
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/item-set/5?namespace=static-us"
                        }
                    },
                    {
                        "name": "Historical Set",
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/item-set/6?namespace=static-us"
                        }
                    },
                ]
            },
            payload_key("/data/wow/journal-encounter/1"): {
                "items": [
                    {
                        "item": {
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/item/123?namespace=static-us"
                            }
                        }
                    }
                ]
            },
            payload_key("/data/wow/item-set/5"): {
                "id": 5,
                "items": [
                    {
                        "id": 123,
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/item/123?namespace=static-us"
                        },
                    },
                    {
                        "id": 999,
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/item/999?namespace=static-us"
                        },
                    },
                ],
            },
            payload_key("/data/wow/item-set/6"): {
                "id": 6,
                "items": [
                    {
                        "id": 555,
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/item/555?namespace=static-us"
                        },
                    }
                ],
            },
            payload_key("/data/wow/item/123"): {"id": 123},
            payload_key("/data/wow/item/999"): {"id": 999},
        }
        reader = FakeReader(payloads)
        plan = [
            {
                "requestKey": "request:seed-index",
                "path": "/data/wow/item-set/index",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            },
            {
                "requestKey": "request:seed-encounter",
                "path": "/data/wow/journal-encounter/1",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
                item_set_names=["S2 Matched Set"],
            )

        called_paths = {call["path"] for call in reader.calls}
        self.assertIn("/data/wow/item-set/5", called_paths)
        self.assertIn("/data/wow/item/999", called_paths)
        self.assertNotIn("/data/wow/item-set/6", called_paths)
        self.assertNotIn("/data/wow/item/555", called_paths)

    def test_profession_index_keeps_only_gear_producing_professions_in_scope(self):
        reader = FakeReader(
            {
                payload_key("/data/wow/profession/index"): {
                    "professions": [
                        {
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/profession/164?namespace=static-us"
                            }
                        },
                        {
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/profession/2915?namespace=static-us"
                            }
                        },
                    ]
                },
                payload_key("/data/wow/profession/164"): {"id": 164},
            }
        )
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/profession/index",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
            )

        called_paths = {call["path"] for call in reader.calls}
        self.assertIn("/data/wow/profession/164", called_paths)
        self.assertNotIn("/data/wow/profession/2915", called_paths)

    def test_mythic_season_index_expands_only_current_midnight_s2_season(self):
        reader = FakeReader(
            {
                payload_key("/data/wow/mythic-keystone/season/index"): {
                    "current_season": {
                        "id": 18,
                        "key": {
                            "href": "https://us.api.blizzard.com/data/wow/mythic-keystone/season/18?namespace=dynamic-us"
                        },
                    },
                    "seasons": [
                        {
                            "id": 17,
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/mythic-keystone/season/17?namespace=dynamic-us"
                            },
                        },
                        {
                            "id": 18,
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/mythic-keystone/season/18?namespace=dynamic-us"
                            },
                        },
                    ],
                },
                payload_key("/data/wow/mythic-keystone/season/18"): {
                    "id": 18,
                    "season_name": "Mythic+ Dungeons (Midnight Season 2)",
                },
            }
        )
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/mythic-keystone/season/index",
                "namespace": "dynamic-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
            )

        called_paths = {call["path"] for call in reader.calls}
        self.assertIn("/data/wow/mythic-keystone/season/18", called_paths)
        self.assertNotIn("/data/wow/mythic-keystone/season/17", called_paths)

    def test_profession_expands_only_midnight_skill_tier_and_recipe(self):
        reader = FakeReader(
            {
                payload_key("/data/wow/profession/164"): {
                    "id": 164,
                    "skill_tiers": [
                        {
                            "name": "Midnight Blacksmithing",
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/profession/164/skill-tier/10?namespace=static-us"
                            },
                        },
                        {
                            "name": "Khaz Algar Blacksmithing",
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/profession/164/skill-tier/9?namespace=static-us"
                            },
                        },
                    ],
                },
                payload_key("/data/wow/profession/164/skill-tier/10"): {
                    "id": 10,
                    "name": "Midnight Blacksmithing",
                    "recipes": [
                        {
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/recipe/100?namespace=static-us"
                            }
                        }
                    ],
                },
                payload_key("/data/wow/recipe/100"): {"id": 100},
            }
        )
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/profession/164",
                "namespace": "static-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
            )

        called_paths = {call["path"] for call in reader.calls}
        self.assertIn("/data/wow/profession/164/skill-tier/10", called_paths)
        self.assertIn("/data/wow/recipe/100", called_paths)
        self.assertNotIn("/data/wow/profession/164/skill-tier/9", called_paths)

    def test_current_mythic_season_expands_period_for_cap_evidence(self):
        reader = FakeReader(
            {
                payload_key("/data/wow/mythic-keystone/season/18"): {
                    "id": 18,
                    "season_name": "Mythic+ Dungeons (Midnight Season 2)",
                    "periods": [
                        {
                            "id": 1076,
                            "key": {
                                "href": "https://us.api.blizzard.com/data/wow/mythic-keystone/period/1076?namespace=dynamic-us"
                            },
                        }
                    ],
                },
                payload_key("/data/wow/mythic-keystone/period/1076"): {
                    "id": 1076,
                    "start_timestamp": 1786460400000,
                },
            }
        )
        plan = [
            {
                "requestKey": "request:seed",
                "path": "/data/wow/mythic-keystone/season/18",
                "namespace": "dynamic-us",
                "region": "us",
                "locale": "en_US",
                "query": {},
                "paginationParentRequestKey": None,
            }
        ]

        with tempfile.TemporaryDirectory() as directory:
            capture_official_request_plan(
                plan=plan,
                output_root=Path(directory),
                reader=reader,
                captured_at="2026-08-17T12:00:00Z",
            )

        called_paths = {call["path"] for call in reader.calls}
        self.assertIn("/data/wow/mythic-keystone/period/1076", called_paths)

    def test_cli_dry_run_does_not_require_credentials_or_write_raw(self):
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--scope",
                str(SCOPE_PATH),
                "--region",
                "us",
                "--locale",
                "en_US",
                "--dry-run-request-plan",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["requestCount"], 13)
        self.assertEqual(output["status"], "dry_run")

    def test_cli_live_without_credentials_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "capture"
            environment = os.environ.copy()
            for key in (
                "WOW_BLIZZARD_CLIENT_ID",
                "WOW_BNET_CLIENT_ID",
                "WOW_BLIZZARD_CLIENT_SECRET",
                "WOW_BNET_CLIENT_SECRET",
            ):
                environment.pop(key, None)
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--scope",
                    str(SCOPE_PATH),
                    "--region",
                    "us",
                    "--locale",
                    "en_US",
                    "--live",
                    "--output-root",
                    str(output_root),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("S2_OFFICIAL_CAPTURE_CREDENTIALS_UNAVAILABLE", result.stderr)
            self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()

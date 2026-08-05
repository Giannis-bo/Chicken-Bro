import json
import os
import unittest
from unittest.mock import patch

from server import simulator_payload


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class WarcraftLogsTimeoutTest(unittest.TestCase):
    def test_graphql_timeout_bounds_both_oauth_and_query_requests(self):
        timeouts = []

        def fake_urlopen(_request, timeout):
            timeouts.append(timeout)
            if len(timeouts) == 1:
                return _Response({"access_token": "test-token"})
            return _Response({"data": {"worldData": {}}})

        with patch.dict(
            os.environ,
            {
                "WOW_WARCRAFTLOGS_CLIENT_ID": "client",
                "WOW_WARCRAFTLOGS_CLIENT_SECRET": "secret",
                "WOW_WARCRAFTLOGS_TIMEOUT_SECONDS": "15",
            },
            clear=False,
        ), patch.object(simulator_payload, "urlopen", side_effect=fake_urlopen):
            result = simulator_payload.warcraftlogs_graphql("query Test { worldData { zones { id } } }", timeout_seconds=8)

        self.assertEqual({"worldData": {}}, result)
        self.assertEqual([8, 8], timeouts)

    def test_graphql_uses_only_the_remaining_timeout_after_oauth(self):
        timeouts = []

        def fake_urlopen(_request, timeout):
            timeouts.append(timeout)
            if len(timeouts) == 1:
                return _Response({"access_token": "test-token"})
            return _Response({"data": {"worldData": {}}})

        with patch.dict(
            os.environ,
            {
                "WOW_WARCRAFTLOGS_CLIENT_ID": "client",
                "WOW_WARCRAFTLOGS_CLIENT_SECRET": "secret",
                "WOW_WARCRAFTLOGS_TIMEOUT_SECONDS": "15",
            },
            clear=False,
        ), patch.object(simulator_payload, "urlopen", side_effect=fake_urlopen), patch.object(
            simulator_payload,
            "monotonic",
            side_effect=[100.0, 103.0],
            create=True,
        ):
            simulator_payload.warcraftlogs_graphql("query Test { worldData { zones { id } } }", timeout_seconds=8)

        self.assertEqual([8, 5], timeouts)


if __name__ == "__main__":
    unittest.main()

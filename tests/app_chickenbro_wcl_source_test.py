import json
import os
import unittest
from unittest.mock import patch

from server.app.chickenbro.wcl_source import build_wcl_log_evidence


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, *_args):
        return json.dumps(self.payload).encode("utf-8")


class ChickenbroWclSourceTest(unittest.TestCase):
    def test_graphql_oauth_and_fetch_share_exact_remaining_deadline(self):
        from server.app.chickenbro import wcl_source as w
        now=[0.0]
        def oauth(timeout):now[0]+=0.75;return 'test-token'
        with patch.object(w,'monotonic',side_effect=lambda:now[0]), patch.object(w,'_oauth_token',side_effect=oauth), patch.object(w,'urlopen',return_value=FakeResponse({'data':{}})) as opened:
            w._graphql('query',timeout_seconds=1)
            self.assertEqual(opened.call_args.kwargs['timeout'],0.25)
        now[0]=0
        def exhausted(timeout):now[0]+=1.1;return 'test-token'
        with patch.object(w,'monotonic',side_effect=lambda:now[0]), patch.object(w,'_oauth_token',side_effect=exhausted), patch.object(w,'urlopen') as opened:
            with self.assertRaises(RuntimeError):w._graphql('query',timeout_seconds=1)
            opened.assert_not_called()

    def test_graphql_never_extends_run_reader_budget(self):
        from server.app.chickenbro import wcl_source as w
        reader=w.WclRunReader();reader.started=0
        marker=w._RUN_READER.set(reader)
        try:
            with patch.object(w,'monotonic',return_value=359.75), patch.object(w,'_oauth_token',return_value='token') as oauth, patch.object(w,'urlopen',return_value=FakeResponse({'data':{}})) as opened:
                w._graphql('query')
                self.assertEqual(oauth.call_args.args[0],0.25)
                self.assertEqual(opened.call_args.kwargs['timeout'],0.25)
            with patch.object(w,'monotonic',return_value=360), patch.object(w,'_oauth_token') as oauth:
                with self.assertRaises(RuntimeError):w._graphql('query')
                oauth.assert_not_called()
        finally:w._RUN_READER.reset(marker)

    def test_graphql_auth_rejection_invalidates_without_retry(self):
        from urllib.error import HTTPError
        from server.app.chickenbro import wcl_source as w
        for status in [401,403,500]:
            with patch.object(w,'_oauth_token',return_value='rejected-token'), patch.object(w,'invalidate_chat_warcraftlogs_oauth_token') as invalidate, patch.object(w,'urlopen',side_effect=HTTPError('safe',status,'',{},None)) as opened:
                with self.assertRaises(HTTPError):w._graphql('query',timeout_seconds=1)
                self.assertEqual(opened.call_count,1)
                self.assertEqual(invalidate.call_count,1 if status in [401,403] else 0)
                if status in [401,403]:self.assertEqual(invalidate.call_args.args[0],'rejected-token')

    def test_continuation_without_end_resolves_fight_boundary_before_query(self):
        report = {"fights": [{"id": 4, "startTime": 100, "endTime": 900}], "events": {"data": [], "nextPageTimestamp": None}}
        with patch("server.app.chickenbro.wcl_source.warcraftlogs_credentials_state", return_value={"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"}), patch(
            "server.app.chickenbro.wcl_source._graphql", return_value={"reportData": {"report": report}},
        ) as query:
            result = build_wcl_log_evidence({"wclUrl": "https://cn.warcraftlogs.com/reports/abc123?fight=4&source=4",
                                            "options": {"dataType": "Casts", "startTime": 500}})
        self.assertEqual(query.call_args.args[1]["endTime"], 900)
        self.assertEqual(result["eventPage"]["endTime"], 900)

    def test_context_and_followup_events_are_available_without_losing_cursor(self):
        report = {"fights": [{"id": 4}], "masterData": {"gameVersion": 1, "logVersion": 22},
                  "playerDetails": {"data": {"playerDetails": {"dps": [
                      {"id": 4, "name": "Giannis", "combatantInfo": {"gear": [{"id": 123}], "talentTree": [{"id": 456}]}},
                      {"id": 5, "name": "Other"}]}}},
                  "events": {"data": [{"type": "cast", "timestamp": 500, "sourceID": 4}], "nextPageTimestamp": 700}}
        with patch("server.app.chickenbro.wcl_source.warcraftlogs_credentials_state", return_value={"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"}), patch(
            "server.app.chickenbro.wcl_source._graphql", return_value={"reportData": {"report": report}},
        ) as query:
            result = build_wcl_log_evidence({"wclUrl": "https://cn.warcraftlogs.com/reports/abc123?fight=4&source=4",
                                            "options": {"dataType": "Casts", "startTime": 500, "endTime": 900, "limit": 1000}})
        self.assertEqual(result["players"][0]["combatantInfo"]["gear"][0]["id"], 123)
        self.assertEqual(len(result["players"]), 1)
        self.assertEqual(result["events"][0]["timestamp"], 500)
        self.assertEqual(result["eventPage"]["nextPageTimestamp"], 700)
        self.assertEqual(query.call_args.args[1]["startTime"], 500)
        self.assertEqual(query.call_args.args[1]["dataType"], "Casts")
        self.assertIn("playerDetails", query.call_args.args[0])

    def test_invalid_event_options_do_not_call_upstream(self):
        with patch("server.app.chickenbro.wcl_source._graphql") as query:
            for options in ({"limit": 100001}, {"dataType": "arbitrary"}, {"startTime": -1}, {"startTime": 5, "endTime": 4}):
                with self.assertRaises(ValueError):
                    from server.app.chickenbro.wcl_source import validate_wcl_options
                    validate_wcl_options(options)
        query.assert_not_called()

    def test_unfiltered_report_tables_are_not_attributed_to_first_fight(self):
        with patch("server.app.chickenbro.wcl_source.warcraftlogs_credentials_state", return_value={"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"}), patch(
            "server.app.chickenbro.wcl_source._graphql", return_value={"reportData": {"report": {
                "fights": [{"id": 1, "name": "first"}, {"id": 2, "name": "second"}],
            }}},
        ):
            result = build_wcl_log_evidence({"wclUrl": "https://www.warcraftlogs.com/reports/abc123"})
        self.assertEqual(result["fight"], {})
        self.assertEqual(result["fightId"], "")
        self.assertEqual(len(result["fights"]), 2)

    def test_cn_link_keeps_fight_and_actor_and_returns_analysis_data(self):
        report = {"title": "report", "fights": [{"id": 4, "name": "Kings' Rest"}],
                  "masterData": {"actors": [{"id": 5, "name": "Giannis", "type": "Player", "subType": "Shaman"}]},
                  "casts": {"data": {"entries": [{"name": "Lava Burst", "total": 42}]}},
                  "damage": {"data": {"entries": [{"name": "Lava Burst", "total": 12345}]}},
                  "events": {"data": [{"type": "cast", "timestamp": 10, "sourceID": 5, "abilityGameID": 51505}], "nextPageTimestamp": 20}}
        with patch("server.app.chickenbro.wcl_source.warcraftlogs_credentials_state", return_value={"configured": True, "mode": "v2_oauth", "api": "warcraftlogs-v2-graphql"}), patch(
            "server.app.chickenbro.wcl_source._graphql", return_value={"reportData": {"report": report}},
        ) as query:
            result = build_wcl_log_evidence({"wclUrl": "https://cn.warcraftlogs.com/reports/pqThd2cvwFyKXD6g?fight=4&source=5"})
        self.assertEqual(result["sourceStatus"], "verified")
        self.assertEqual(query.call_args.args[1]["sourceId"], 5)
        self.assertEqual(result["actors"][0]["name"], "Giannis")
        self.assertEqual(result["casts"]["entries"][0]["total"], 42)
        self.assertEqual(result["eventPage"]["nextPageTimestamp"], 20)
        self.assertFalse(result["eventPage"]["complete"])

    def test_reader_fetches_oauth_and_bounded_graphql_evidence(self):
        responses = [
            FakeResponse({"access_token": "oauth-token"}),
            FakeResponse({
                "data": {
                    "reportData": {
                        "report": {
                            "title": "Giannis report",
                            "startTime": 100,
                            "endTime": 200,
                            "fights": [{"id": 1, "name": "Patchwerk", "difficulty": 10, "kill": True}],
                            "events": {"data": [
                                {"type": "cast"},
                                {"type": "damage"},
                                {"type": "death"},
                                {"type": "buffRemove"},
                            ]},
                        }
                    }
                }
            }),
        ]

        with patch.dict(os.environ, {
            "WOW_WARCRAFTLOGS_CLIENT_ID": "client-id",
            "WOW_WARCRAFTLOGS_CLIENT_SECRET": "client-secret",
            "WOW_WARCRAFTLOGS_TIMEOUT_SECONDS": "15",
        }, clear=False), patch(
            "server.app.chickenbro.wcl_source.urlopen",
            side_effect=responses,
        ) as opener:
            result = build_wcl_log_evidence({
                "wclUrl": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            })

        self.assertEqual("verified", result["sourceStatus"])
        self.assertEqual("KfVp6AQ8GMHYFN42", result["reportCode"])
        self.assertEqual("1", result["fightId"])
        self.assertEqual({
            "total": 4,
            "casts": 1,
            "buffEvents": 1,
            "deaths": 1,
            "damageEvents": 1,
            "healingEvents": 0,
            "mechanicEvents": 0,
        }, result["eventSummary"])
        self.assertEqual(2, opener.call_count)

    def test_reader_redacts_secret_from_api_failure(self):
        with patch.dict(os.environ, {
            "WOW_WARCRAFTLOGS_CLIENT_ID": "client-id",
            "WOW_WARCRAFTLOGS_CLIENT_SECRET": "client-secret",
        }, clear=False), patch(
            "server.app.chickenbro.wcl_source.urlopen",
            side_effect=RuntimeError("client_secret=client-secret Bearer oauth-token"),
        ):
            result = build_wcl_log_evidence({
                "wclUrl": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            })

        self.assertEqual("blocked", result["sourceStatus"])
        self.assertNotIn("client-secret", str(result["blockers"]))
        self.assertNotIn("oauth-token", str(result["blockers"]))


if __name__ == "__main__":
    unittest.main()

class ReportDiscoveryRegressionTest(unittest.TestCase):
    def test_bare_report_only_queries_metadata_and_requests_selection(self):
        from server.app.chickenbro import wcl_source as w
        report = {"fights": [{"id": 1}, {"id": 2}]}
        with patch.object(w, 'warcraftlogs_credentials_state', return_value={"configured": True, "mode": "v2_oauth", "api": "v2"}), patch.object(w, '_graphql', return_value={"reportData": {"report": report}}) as call:
            result = w.build_wcl_log_evidence({"wclUrl": "https://www.warcraftlogs.com/reports/abc123"})
        self.assertNotIn('table(', call.call_args.args[0])
        self.assertNotIn('playerDetails(', call.call_args.args[0])
        self.assertEqual(result['queryScope'], 'report_discovery')
        self.assertFalse(result['eventPage']['complete'])
        self.assertTrue(any('fight' in s for s in result['nextActions']))

    def test_graphql_partial_data_retains_metadata_and_error(self):
        from server.app.chickenbro import wcl_source as w
        payload = {'data': {'reportData': {'report': {'fights': [{'id': 1}], 'events': None}}}, 'errors': [{'message': 'events unavailable', 'path': ['reportData','report','events']}]}
        with patch.object(w, 'urlopen', return_value=FakeResponse(payload)):
            result = w._graphql('query{}', token='test')
        self.assertEqual(result['reportData']['report']['fights'][0]['id'], 1)
        self.assertIn('events unavailable', result['_fieldErrors'][0])

    def test_partial_statistics_reach_gateway_without_becoming_verified(self):
        from server.app.chickenbro import wcl_source as w
        from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
        data = {'reportData': {'report': {'fights': [{'id': 2}], 'events': None}}, '_fieldErrors': ['events unavailable']}
        with patch.object(w, 'warcraftlogs_credentials_state', return_value={'configured': True, 'mode': 'v2_oauth', 'api': 'v2'}), patch.object(w, '_graphql', return_value=data):
            result = ServerConfiguredSourceQuery(wcl_reader=w.build_wcl_log_evidence).query('warcraftlogs', 'https://www.warcraftlogs.com/reports/abc123?fight=2')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['facts'][0]['fights'][0]['id'], '2')
        self.assertFalse(result['facts'][0]['eventPage']['complete'])
        self.assertIn('events unavailable', result['limitations'])

    def test_permission_error_without_data_stays_blocked(self):
        from server.app.chickenbro import wcl_source as w
        with patch.object(w, 'urlopen', return_value=FakeResponse({'data': {'reportData': {'report': None}}, 'errors': [{'message': 'permission denied'}]})):
            with self.assertRaisesRegex(RuntimeError, 'permission denied'):
                w._graphql('query{}', token='test')

    def test_explicit_window_keeps_scoped_query(self):
        from server.app.chickenbro import wcl_source as w
        with patch.object(w, 'warcraftlogs_credentials_state', return_value={'configured': True, 'mode': 'v2_oauth', 'api': 'v2'}), patch.object(w, '_graphql', return_value={'reportData': {'report': {'fights': [{'id': 1}]}}}) as call:
            result=w.build_wcl_log_evidence({'wclUrl':'https://www.warcraftlogs.com/reports/abc123', 'options':{'startTime':10,'endTime':20}})
        self.assertIn('table(', call.call_args.args[0])
        self.assertEqual(result['queryScope'], 'scoped_analysis')

    def test_wcl_display_parameters_are_canonicalized_before_gateway_validation(self):
        from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
        reader = unittest.mock.Mock(return_value={'sourceStatus':'verified'})
        service=ServerConfiguredSourceQuery(wcl_reader=reader)
        service.query('warcraftlogs','https://cn.warcraftlogs.com/reports/LPZNxhXGgdmDH6Cq?fight=2&type=summary&source=5&view=events')
        self.assertIn('fight=2', reader.call_args.args[0]['wclUrl'])
        self.assertIn('source=5', reader.call_args.args[0]['wclUrl'])
        self.assertNotIn('type=', reader.call_args.args[0]['wclUrl'])

    def test_display_normalization_preserves_url_security_and_identity_checks(self):
        from server.app.chickenbro.wcl_source import normalize_wcl_report_url
        for url in ('https://evil.example/reports/abc123?type=summary',
                    'https://www.warcraftlogs.com/reports/abc123?fight=1&fight=2&type=summary',
                    'https://www.warcraftlogs.com/reports/abc123?redirect=https://evil.example&type=summary'):
            with self.assertRaises(ValueError):
                normalize_wcl_report_url(url)
        self.assertIn('fight=2', normalize_wcl_report_url('https://cn.warcraftlogs.com/reports/abc123#fight=2&type=damage-done&view=events'))

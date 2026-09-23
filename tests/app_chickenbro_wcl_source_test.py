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
    def test_event_window_outside_fight_is_not_verified_empty_evidence(self):
        report = {'fights': [{'id': 42, 'startTime': 6854810, 'endTime': 7080831}],
                  'events': {'data': [], 'nextPageTimestamp': None}}
        with patch('server.app.chickenbro.wcl_source.warcraftlogs_credentials_state',
                   return_value={'configured': True, 'mode': 'v2_oauth', 'api': 'v2'}), patch(
                   'server.app.chickenbro.wcl_source._graphql', return_value={'reportData': {'report': report}}):
            result = build_wcl_log_evidence({
                'wclUrl': 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=42',
                'options': {'view': 'events', 'dataType': 'DamageTaken', 'startTime': 222000, 'endTime': 226021}})
        self.assertNotEqual(result['sourceStatus'], 'verified')
        self.assertNotIn('events', result)
        self.assertIn('report-relative', ' '.join(result['blockers'] + result['nextActions']))
        self.assertIn('6854810', ' '.join(result['blockers'] + result['nextActions']))

    def test_event_window_after_fight_rejects_returned_events(self):
        report = {'fights': [{'id': 7, 'startTime': 1000, 'endTime': 9000}],
                  'events': {'data': [{'type': 'damage', 'timestamp': 8000}], 'nextPageTimestamp': None}}
        with patch('server.app.chickenbro.wcl_source.warcraftlogs_credentials_state',
                   return_value={'configured': True, 'mode': 'v2_oauth', 'api': 'v2'}), patch(
                   'server.app.chickenbro.wcl_source._graphql', return_value={'reportData': {'report': report}}):
            result = build_wcl_log_evidence({
                'wclUrl': 'https://www.warcraftlogs.com/reports/BBBBBBBBBBBBBBBB?fight=7',
                'options': {'view': 'events', 'startTime': 8000, 'endTime': 10000}})
        self.assertNotEqual(result['sourceStatus'], 'verified')
        self.assertNotIn('events', result)

    def test_statistics_deadline_bounds_the_upstream_request(self):
        from server.app.chickenbro import wcl_source as w
        marker = w._STATISTICS_DEADLINE.set(10.25)
        try:
            with patch.object(w,'monotonic',return_value=10), patch.object(w,'_oauth_token',return_value='token'), patch.object(w,'urlopen',return_value=FakeResponse({'data':{}})) as opened:
                w._graphql('query')
                self.assertEqual(opened.call_args.kwargs['timeout'], 0.25)
            with patch.object(w,'monotonic',return_value=11), patch.object(w,'urlopen') as opened:
                with self.assertRaises(RuntimeError):
                    w._graphql('query')
                opened.assert_not_called()
        finally:
            w._STATISTICS_DEADLINE.reset(marker)

    def test_window_statistics_follow_pages_and_keep_half_open_scope(self):
        pages = [
            {'data':[{'type':'cast','timestamp':100,'sourceID':5,'abilityGameID':7},
                     {'type':'heal','timestamp':150,'sourceID':5,'amount':80,'overheal':20},
                     {'type':'energize','timestamp':200,'sourceID':5,'resourceChangeType':9,'waste':2}], 'nextPageTimestamp':200},
            {'data':[{'type':'energize','timestamp':200,'sourceID':5,'resourceChangeType':9,'waste':2},
                     {'type':'heal','timestamp':250,'sourceID':5,'amount':20,'overheal':80},
                     {'type':'heal','timestamp':260,'sourceID':6,'amount':999,'overheal':0},
                     {'type':'cast','timestamp':300,'sourceID':5,'abilityGameID':7}], 'nextPageTimestamp':None}]
        result, calls = self._statistics(pages)
        self.assertEqual(result['sourceStatus'], 'verified')
        self.assertTrue(result['statistics']['complete'])
        self.assertEqual(result['statistics']['eventCount'], 4)
        self.assertEqual(result['statistics']['casts'], [{'abilityId':7, 'count':1}])
        self.assertEqual(result['statistics']['healing']['effective'], 100)
        self.assertEqual(result['statistics']['healing']['overheal'], 100)
        self.assertEqual(result['statistics']['resources'], [{'resourceType':9,'waste':2,'missingValues':0}])
        self.assertEqual(calls[1]['startTime'], 200)
        self.assertNotIn('events', result)

    def test_statistics_page_budget_and_missing_values_never_claim_complete(self):
        result, calls = self._statistics([{'data':[
            {'type':'heal','timestamp':150,'sourceID':5,'amount':80}], 'nextPageTimestamp':200}], maxPages=1)
        self.assertFalse(result['statistics']['complete'])
        self.assertFalse(result['statistics']['metricsComplete'])
        self.assertEqual(result['statistics']['healing']['missingValues'], 1)
        self.assertEqual(result['statistics']['nextPageTimestamp'], 200)
        self.assertEqual(len(calls), 1)

    def test_statistics_later_failure_preserves_only_observed_subtotal(self):
        result, _ = self._statistics([
            {'data':[{'type':'cast','timestamp':150,'sourceID':5,'abilityGameID':7}], 'nextPageTimestamp':200},
            RuntimeError('upstream unavailable')])
        self.assertEqual(result['sourceStatus'], 'partial')
        self.assertFalse(result['statistics']['complete'])
        self.assertEqual(result['statistics']['eventCount'], 1)

    def test_statistics_refuse_window_outside_the_selected_fight(self):
        result, _ = self._statistics([{'data':[], 'nextPageTimestamp':None}], startTime=0, endTime=20)
        self.assertNotEqual(result['sourceStatus'], 'verified')
        self.assertFalse(result['statistics']['complete'])
        self.assertIn('fight', ' '.join(result['blockers']))

    def test_statistics_invalid_cursor_and_truncated_fields_stop_without_false_totals(self):
        for page in [
            {'data':[{'type':'cast','timestamp':150,'sourceID':5,'abilityGameID':7}], 'nextPageTimestamp':100},
            {'data':[{'type':'cast','timestamp':150,'sourceID':5,'abilityGameID':7,'detail':'x'*2001}], 'nextPageTimestamp':None},
        ]:
            with self.subTest(page=page):
                result, calls = self._statistics([page])
                self.assertFalse(result['statistics']['complete'])
                self.assertEqual(result['statistics']['eventCount'], 0)
                self.assertEqual(len(calls), 1)

    def test_statistics_preserve_identical_simultaneous_casts(self):
        row = {'type':'cast','timestamp':150,'sourceID':5,'abilityGameID':7}
        result, _ = self._statistics([{'data':[row,dict(row)], 'nextPageTimestamp':None}])
        self.assertEqual(result['statistics']['casts'], [{'abilityId':7,'count':2}])

    def test_statistics_bound_distinct_groups_and_disclose_omission(self):
        events = [{'type':'cast','timestamp':150,'sourceID':5,'abilityGameID':i+1} for i in range(140)]
        result, _ = self._statistics([{'data':events,'nextPageTimestamp':None}])
        self.assertLessEqual(len(result['statistics']['casts']), 128)
        self.assertFalse(result['statistics']['metricsComplete'])
        self.assertGreater(result['statistics']['missingValues'], 0)

    def test_overview_rejects_window_filters_instead_of_returning_whole_fight_silently(self):
        from server.app.chickenbro.wcl_source import validate_wcl_options
        with self.assertRaises(ValueError):
            validate_wcl_options({'view':'overview','startTime':10,'endTime':20})

    def _statistics(self, pages, **options):
        calls = []
        def fetch(_query, variables):
            calls.append(variables)
            page = pages[len(calls)-1]
            if isinstance(page, Exception):
                raise page
            return {'reportData':{'report':{'title':'Synthetic', 'fights':[{'id':4,'startTime':100,'endTime':300}], 'events':page}}}
        with patch('server.app.chickenbro.wcl_source.warcraftlogs_credentials_state', return_value={'configured':True,'mode':'v2_oauth','api':'v2'}), patch(
            'server.app.chickenbro.wcl_source._graphql', side_effect=fetch):
            try:
                result = build_wcl_log_evidence({'wclUrl':'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=4&source=5',
                    'options':{'view':'statistics','startTime':100,'endTime':300, **options}})
            except ValueError as error:
                self.fail(f'window statistics are not supported: {error}')
        return result, calls

    def test_event_view_omits_heavy_tables_but_preserves_scope_and_cursor(self):
        report = {'title':'Example', 'fights':[{'id':4,'startTime':100,'endTime':900}],
                  'events':{'data':[{'type':'cast','timestamp':150,'sourceID':5}], 'nextPageTimestamp':200}}
        with patch('server.app.chickenbro.wcl_source.warcraftlogs_credentials_state', return_value={'configured':True,'mode':'v2_oauth','api':'v2'}), patch(
            'server.app.chickenbro.wcl_source._graphql', return_value={'reportData':{'report':report}}) as fetch:
            try:
                result = build_wcl_log_evidence({'wclUrl':'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=4&source=5',
                                               'options':{'view':'events'}})
            except ValueError as error:
                self.fail(f'event view is not supported: {error}')
        self.assertEqual(result['sourceStatus'], 'verified')
        self.assertEqual(result['eventPage']['nextPageTimestamp'], 200)
        self.assertEqual(result['sourceId'], '5')
        self.assertNotIn('casts', result)
        self.assertNotIn('players', result)
        self.assertNotIn('playerDetails', fetch.call_args.args[0])
        self.assertNotIn('table(', fetch.call_args.args[0])

    def test_overview_does_not_fetch_events_or_claim_event_completion(self):
        report = {'fights':[{'id':4}], 'casts':{'data':{'entries':[{'name':'Spell','total':2}]}}}
        with patch('server.app.chickenbro.wcl_source.warcraftlogs_credentials_state', return_value={'configured':True,'mode':'v2_oauth','api':'v2'}), patch(
            'server.app.chickenbro.wcl_source._graphql', return_value={'reportData':{'report':report}}) as fetch:
            try:
                result = build_wcl_log_evidence({'wclUrl':'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=4', 'options':{'view':'overview'}})
            except ValueError as error:
                self.fail(f'overview is not supported: {error}')
        self.assertEqual(result['casts']['entries'][0]['total'], 2)
        self.assertNotIn('events(', fetch.call_args.args[0])
        self.assertNotIn('events', result)
        self.assertNotIn('eventPage', result)
        self.assertNotIn('wcl.events', result['evidenceRefs'])

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
        report = {"fights": [{"id": 4, "startTime": 100, "endTime": 900}], "masterData": {"gameVersion": 1, "logVersion": 22},
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

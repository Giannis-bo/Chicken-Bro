import unittest
import json
import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from server.app.chickenbro.source_gateway import (
    ChickenbroSourceGateway,
    SourceGatewayUnauthorized,
    ServerConfiguredSourceQuery,
)


class ChickenbroSourceGatewayTest(unittest.TestCase):
    def test_logged_cast_counts_are_preserved_without_manual_attribution(self):
        for view in ('full', 'overview', 'events', 'statistics'):
            with self.subTest(view=view):
                rows = [{'type': 'cast', 'timestamp': 1234, 'abilityGameID': 90001},
                        {'type': 'cast', 'timestamp': 1234, 'abilityGameID': 90002}]
                service = ServerConfiguredSourceQuery(wcl_reader=lambda _: {
                    'sourceStatus': 'verified', 'view': view, 'reportCode': 'AAAAAAAAAAAAAAAA',
                    'fightId': 4, 'sourceId': 5, 'events': rows,
                    'casts': {'entries': [{'name': 'Unseen ability', 'total': 36}]},
                    'statistics': {'complete': True, 'eventCount': 2},
                    'nextActions': ['coverage note'] * 3, 'blockers': ['upstream note'] * 4})
                packet = service.query('warcraftlogs', 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=4&source=5')
                self.assertTrue(any('not manual button presses' in note for note in packet['limitations']))
                fact = packet['facts'][0]
                if view in ('full', 'overview'):
                    self.assertEqual(fact['casts']['entries'][0]['total'], 36)
                if view in ('full', 'events'):
                    self.assertEqual(fact['events'], rows)

    def test_compact_event_view_does_not_reintroduce_empty_tables(self):
        service = ServerConfiguredSourceQuery(wcl_reader=lambda _: {
            'sourceStatus':'verified', 'view':'events', 'reportCode':'AAAAAAAAAAAAAAAA', 'fightId':4,
            'sourceId':5, 'events':[{'type':'cast','timestamp':10}], 'eventPage':{'complete':False,'nextPageTimestamp':20}})
        packet = service.query('warcraftlogs', 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=4&source=5', {'view':'events'})
        self.assertNotIn('casts', packet['facts'][0])
        self.assertNotIn('players', packet['facts'][0])
        self.assertEqual(packet['facts'][0]['eventPage']['nextPageTimestamp'], 20)

    def test_partial_statistics_remain_visible_with_their_incomplete_scope(self):
        stats = {'startTime':100,'endTime':300,'observedThrough':200,'complete':False,'eventCount':2,'nextPageTimestamp':200}
        service = ServerConfiguredSourceQuery(wcl_reader=lambda _: {
            'sourceStatus':'partial', 'view':'statistics', 'reportCode':'AAAAAAAAAAAAAAAA','fightId':4,'sourceId':5,
            'statistics':stats, 'evidenceRefs':['wcl.statistics'], 'queryScope':'window_statistics'})
        gateway = ChickenbroSourceGateway(query_service=service)
        token = gateway.issue_capability()
        packet = gateway.query(token, 'warcraftlogs','https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=4&source=5',
                               {'view':'statistics','startTime':100,'endTime':300})
        self.assertTrue(packet['facts'], 'observed subtotals must survive a later page failure')
        self.assertEqual(packet['facts'][0]['statistics'], stats)
        self.assertIn('statistics', json.dumps(gateway.answer_evidence(token)))

    def test_oversized_batch_preserves_whole_members_and_indexes_only_delivered_evidence(self):
        from server.app.chickenbro.answer_grounding import validate_answer
        members = []
        for code in ('AAAAAAAAAAAAAAAA', 'BBBBBBBBBBBBBBBB', 'CCCCCCCCCCCCCCCC'):
            members.append({'sourceKey': 'warcraftlogs', 'status': 'verified',
                'facts': [{'reportCode': code, 'fightId': 1, 'sourceId': 2,
                    'events': [{'timestamp': 100, 'type': 'cast', 'abilityGameID': 7}],
                    'eventPage': {'complete': True}, 'reportTitle': '文' * 23000}]})
        raw = {'sourceKey': 'warcraftlogs', 'status': 'verified', 'results': members,
               'limitations': ['Independent coverage.']}
        original = copy.deepcopy(raw)
        gateway = ChickenbroSourceGateway(query_service=lambda *_: raw)
        token = gateway.issue_capability()
        result = gateway.query(token, 'warcraftlogs_batch', 'reports')
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False).encode()), 180000)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['results'][:2], members[:2])
        omitted = result['results'][2]
        self.assertEqual(omitted['facts'], [])
        self.assertEqual(omitted['status'], 'partial')
        self.assertTrue(omitted['transportOmitted'])
        self.assertEqual(raw, original)
        evidence = gateway.answer_evidence(token)
        self.assertEqual(validate_answer('https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2', evidence), [])
        self.assertEqual(validate_answer('https://www.warcraftlogs.com/reports/CCCCCCCCCCCCCCCC?fight=1&source=2', evidence), ['WCL_REFERENCE_UNOBSERVED'])

    def test_oversized_first_member_does_not_discard_later_small_members(self):
        raw = {'sourceKey': 'warcraftlogs', 'status': 'verified', 'results': [
            {'status': 'verified', 'facts': ['文' * 65000]},
            {'status': 'verified', 'facts': [{'value': 2}]},
            {'status': 'partial', 'facts': [{'value': 3}], 'limitations': ['Partial source coverage.']} ]}
        gateway = ChickenbroSourceGateway(query_service=lambda *_: raw)
        result = gateway.query(gateway.issue_capability(), 'warcraftlogs_batch', 'reports')
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False).encode()), 180000)
        self.assertTrue(result['results'][0]['transportOmitted'])
        self.assertEqual(result['results'][1:], raw['results'][1:])

    def test_oversized_single_result_is_not_collected_as_visible_evidence(self):
        raw = {'sourceKey': 'warcraftlogs', 'status': 'verified', 'facts': [
            {'reportCode': 'DDDDDDDDDDDDDDDD', 'fightId': 1, 'sourceId': 2,
             'events': [], 'reportTitle': '文' * 65000}]}
        gateway = ChickenbroSourceGateway(query_service=lambda *_: raw)
        token = gateway.issue_capability()
        result = gateway.query(token, 'warcraftlogs', 'report')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['facts'], [])
        self.assertEqual(gateway.answer_evidence(token)['references'], [])

    def test_source_capability_lasts_through_analysis_but_can_still_be_revoked(self):
        now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        gateway = ChickenbroSourceGateway(query_service=lambda *_: {"status": "verified"}, now=lambda: now)
        token = gateway.issue_capability()
        now += timedelta(seconds=480)
        self.assertEqual(gateway.query(token, "warcraftlogs", "target")["status"], "verified")
        gateway.revoke(token)
        with self.assertRaises(SourceGatewayUnauthorized):
            gateway.query(token, "warcraftlogs", "target")

    def test_capability_gateway_keeps_event_options_and_context(self):
        calls = []
        service = ServerConfiguredSourceQuery(wcl_reader=lambda value: calls.append(value) or {
            "sourceStatus": "verified", "players": [{"id": 4, "combatantInfo": {"gear": [{"id": 123}]}}],
            "events": [{"type": "cast", "timestamp": 500}], "eventPage": {"nextPageTimestamp": 600}})
        gateway = ChickenbroSourceGateway(query_service=service)
        token = gateway.issue_capability()
        options = {"dataType": "Casts", "startTime": 500, "endTime": 900}
        result = gateway.query(token, "warcraftlogs", "https://cn.warcraftlogs.com/reports/abc123?fight=4&source=4", options)
        self.assertEqual(calls[0]["options"], options)
        self.assertEqual(result["facts"][0]["events"][0]["timestamp"], 500)
        self.assertEqual(result["facts"][0]["players"][0]["combatantInfo"]["gear"][0]["id"], 123)

    def test_cn_report_is_canonicalized_before_reader(self):
        reader_calls = []
        query = ServerConfiguredSourceQuery(wcl_reader=lambda value: reader_calls.append(value) or {
            "sourceStatus": "verified", "actors": [{"id": 5, "name": "Giannis"}],
            "casts": {"entries": [{"name": "Lava Burst", "total": 42}]},
        })
        result = query.query("warcraftlogs", "https://cn.warcraftlogs.com/reports/pqThd2cvwFyKXD6g?fight=4&source=5")
        self.assertEqual(reader_calls[0]["wclUrl"], "https://www.warcraftlogs.com/reports/pqThd2cvwFyKXD6g#fight=4&source=5")
        self.assertEqual(result["facts"][0]["actors"][0]["name"], "Giannis")
        self.assertEqual(result["facts"][0]["casts"]["entries"][0]["total"], 42)

    def test_formal_router_registers_the_internal_source_gateway(self):
        root = Path(__file__).resolve().parents[1]
        route_path = root / "server/app/api/routes/source_gateway.py"
        self.assertTrue(route_path.is_file())
        route_source = route_path.read_text(encoding="utf-8")
        router_source = (root / "server/app/api/routes/__init__.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("SOURCE_GATEWAY_PATH", route_source)
        self.assertIn("include_in_schema=False", route_source)
        self.assertIn("source_gateway_router", router_source)
        self.assertIn("include_router(source_gateway_router)", router_source)

    def test_issued_capability_allows_one_source_query_and_revoke_blocks_it(self):
        calls = []
        gateway = ChickenbroSourceGateway(
            query_service=lambda provider, target: calls.append((provider, target)) or {
                "sourceKey": provider,
                "status": "source_reference",
            },
            now=lambda: datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc),
        )

        token = gateway.issue_capability()
        result = gateway.query(token, "warcraftlogs", "https://www.warcraftlogs.com/reports/abc123?fight=1")

        self.assertEqual("source_reference", result["status"])
        self.assertEqual(
            [("warcraftlogs", "https://www.warcraftlogs.com/reports/abc123?fight=1")],
            calls,
        )
        gateway.revoke(token)
        with self.assertRaises(SourceGatewayUnauthorized):
            gateway.query(token, "warcraftlogs", "https://www.warcraftlogs.com/reports/abc123?fight=1")

    def test_server_query_uses_configured_wcl_api_reader_and_never_public_page_reader(self):
        log_evidence = {
            "status": "ready",
            "sourceStatus": "verified",
            "api": "warcraftlogs-v2-graphql",
            "reportCode": "KfVp6AQ8GMHYFN42",
            "sourceUrl": "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            "fightId": "1",
            "reportTitle": "Giannis report",
            "reportWindow": {"startTime": 100, "endTime": 200},
            "fight": {"id": "1", "name": "Patchwerk", "kill": True},
            "eventSummary": {"casts": 12, "damageEvents": 80, "deaths": 0},
            "evidenceRefs": ["wcl.report", "wcl.fight", "wcl.events"],
            "nextActions": [],
        }

        with patch(
            "server.app.chickenbro.source_gateway.build_wcl_log_evidence",
            return_value=log_evidence,
        ) as reader, patch(
            "server.app.chickenbro.source_gateway.build_public_web_research_tool_result",
            side_effect=AssertionError("source API lookup must not open a public page"),
            create=True,
        ):
            result = ServerConfiguredSourceQuery().query(
                "warcraftlogs",
                "https://www.warcraftlogs.com/reports/KfVp6AQ8GMHYFN42?fight=1",
            )

        reader.assert_called_once()
        self.assertEqual("warcraftlogs", result["sourceKey"])
        self.assertEqual("verified", result["status"])
        self.assertEqual("KfVp6AQ8GMHYFN42", result["facts"][0]["reportCode"])
        self.assertEqual(["wcl.report", "wcl.fight", "wcl.events"], result["evidenceRefs"])

    def test_research_query_routes_without_simc_projection_and_retains_capability(self):
        class Research:
            def character(self, target):
                return {"status": "source_reference", "facts": [{"gear": {"neck": {
                    "gems_detail": [{"name": "16 Mastery & 7 Crit"}], "tier": "36"}}}], "target": target}
            def rankings(self, options):
                return {"status": "source_reference", "facts": [{"score": 3600}], "options": options}
            def characters(self, targets):
                return {"status": "partial", "facts": [{"targets": targets}]}
        service = ServerConfiguredSourceQuery(raiderio_research=Research())
        gateway = ChickenbroSourceGateway(query_service=service)
        token = gateway.issue_capability()
        target = "https://raider.io/cn/characters/cn/silver-hand/Giannis"
        profile = gateway.query(token, "raiderio", target)
        self.assertEqual(profile["facts"][0]["gear"]["neck"]["gems_detail"][0]["name"], "16 Mastery & 7 Crit")
        ranking = gateway.query(token, "raiderio_rankings", "rankings", {"className": "shaman", "spec": "enhancement"})
        self.assertEqual(ranking["options"]["spec"], "enhancement")
        batch = gateway.query(token, "raiderio_batch", "characters", {"targets": [target]})
        self.assertEqual(batch["facts"][0]["targets"], [target])
        gateway.revoke(token)
        with self.assertRaises(SourceGatewayUnauthorized):
            gateway.query(token, "raiderio_rankings", "rankings", {"className": "shaman", "spec": "enhancement"})

    def test_research_dispatch_rejects_unrecognized_targets_and_options(self):
        from server.app.simulation.sources import InvalidSourceLink
        service = ServerConfiguredSourceQuery(raiderio_research=object())
        for provider, target, options in [
            ("raiderio_batch", "characters", {"targets": [], "extra": "forbidden"}),
            ("raiderio_rankings", "https://localhost", {"className": "shaman", "spec": "enhancement"}),
            ("raiderio", "https://raider.io/characters/us/area-52/Test", {"extra": 1}),
        ]:
            with self.subTest(provider=provider), self.assertRaises(InvalidSourceLink):
                service.query(provider, target, options)


class BoundedSourceResultIndependentReviewTest(unittest.TestCase):
    """Additional transport-contract checks; run through unittest discovery."""

    @staticmethod
    def encoded_size(value):
        return len(json.dumps(value, ensure_ascii=False).encode('utf-8'))

    @staticmethod
    def member(code='EEEEEEEEEEEEEEEE', padding=''):
        return {'sourceKey': 'warcraftlogs', 'status': 'verified',
                'facts': [{'reportCode': code, 'fightId': 9, 'sourceId': 3,
                           'casts': {'entries': [{'name': 'Spell', 'total': 1}]}}],
                'padding': padding}

    def test_exact_utf8_boundary_returns_original_and_one_more_byte_omits(self):
        from server.app.chickenbro.source_gateway import _bounded_result, MAX_SOURCE_RESULT_BYTES
        packet = self.member()
        room = MAX_SOURCE_RESULT_BYTES - self.encoded_size(packet)
        packet['padding'] = '文' * (room // 3) + 'x' * (room % 3)
        self.assertEqual(self.encoded_size(packet), MAX_SOURCE_RESULT_BYTES)
        self.assertLess(len(json.dumps(packet, ensure_ascii=False)), MAX_SOURCE_RESULT_BYTES)
        self.assertIs(_bounded_result(packet), packet)
        packet['padding'] += 'x'
        omitted = _bounded_result(packet)
        self.assertTrue(omitted['transportOmitted'])
        self.assertEqual(omitted['facts'], [])
        self.assertLessEqual(self.encoded_size(omitted), MAX_SOURCE_RESULT_BYTES)

    def test_oversized_middle_member_keeps_original_positions_and_whole_neighbors(self):
        from server.app.chickenbro.source_gateway import _bounded_result
        members = [self.member('AAAAAAAAAAAAAAAA'), self.member('BBBBBBBBBBBBBBBB', '文' * 70000),
                   {**self.member('CCCCCCCCCCCCCCCC'), 'status': 'partial'}]
        original = {'sourceKey': 'warcraftlogs', 'status': 'partial', 'results': members}
        before = copy.deepcopy(original)
        bounded = _bounded_result(original)
        self.assertEqual(bounded['results'][0], members[0])
        self.assertTrue(bounded['results'][1]['transportOmitted'])
        self.assertEqual(bounded['results'][2], members[2])
        self.assertEqual(bounded['transportProjection'],
                         {'originalMembers': 3, 'retainedMembers': 2, 'omittedMembers': 1})
        self.assertEqual(original, before)
        self.assertLessEqual(self.encoded_size(bounded), 180000)

    def test_all_members_omitted_never_registers_source_facts_or_query_failures(self):
        raw = {'sourceKey': 'warcraftlogs', 'status': 'verified',
               'results': [self.member(code * 16, '文' * 70000) for code in 'ABC']}
        gateway = ChickenbroSourceGateway(query_service=lambda *_: raw)
        token = gateway.issue_capability()
        bounded = gateway.query(token, 'warcraftlogs_batch', 'reports')
        self.assertEqual(bounded['transportProjection']['retainedMembers'], 0)
        self.assertEqual(bounded['transportProjection']['omittedMembers'], 3)
        self.assertTrue(all(r['transportOmitted'] and not r['facts'] for r in bounded['results']))
        evidence = gateway.answer_evidence(token)
        self.assertEqual(evidence['references'], [])
        self.assertEqual(evidence['coverage']['reportReceipts'], [])
        self.assertEqual(evidence['coverage']['failures'], [])
        self.assertLessEqual(self.encoded_size(bounded), 180000)

    def test_oversized_outer_metadata_falls_back_without_leaking_member_references(self):
        raw = {'sourceKey': 'warcraftlogs', 'status': 'verified', 'padding': '文' * 70000,
               'results': [self.member()]}
        gateway = ChickenbroSourceGateway(query_service=lambda *_: raw)
        token = gateway.issue_capability()
        bounded = gateway.query(token, 'warcraftlogs_batch', 'reports')
        self.assertTrue(bounded['transportOmitted'])
        self.assertNotIn('results', bounded)
        self.assertEqual(gateway.answer_evidence(token)['references'], [])
        self.assertLessEqual(self.encoded_size(bounded), 180000)

    def test_transport_omission_does_not_clear_previous_observed_scoped_reference(self):
        from server.app.chickenbro.answer_grounding import validate_answer
        current = [self.member()]
        gateway = ChickenbroSourceGateway(query_service=lambda *_: current[0])
        token = gateway.issue_capability()
        gateway.query(token, 'warcraftlogs', 'report')
        current[0] = self.member('FFFFFFFFFFFFFFFF', '文' * 70000)
        bounded = gateway.query(token, 'warcraftlogs', 'report')
        self.assertTrue(bounded['transportOmitted'])
        evidence = gateway.answer_evidence(token)
        self.assertEqual(validate_answer('https://www.warcraftlogs.com/reports/EEEEEEEEEEEEEEEE?fight=9&source=3', evidence), [])
        self.assertEqual(validate_answer('https://www.warcraftlogs.com/reports/FFFFFFFFFFFFFFFF?fight=9&source=3', evidence), ['WCL_REFERENCE_UNOBSERVED'])
        self.assertEqual(len(evidence['coverage']['reportReceipts']), 1)


if __name__ == "__main__":
    unittest.main()

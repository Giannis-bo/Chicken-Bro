import unittest
from unittest.mock import patch

from server.app.chickenbro import wcl_source


class RunReaderTest(unittest.TestCase):
    def test_research_budget_leaves_time_for_answer_without_new_network_calls(self):
        reader = wcl_source.WclRunReader()
        with patch.object(wcl_source,'monotonic',return_value=reader.started+361), patch.object(wcl_source,'_graphql') as query:
            result = reader({'wclUrl':'https://www.warcraftlogs.com/reports/abc123?fight=4'})
        self.assertEqual(result['sourceStatus'],'partial')
        self.assertIn('budget',result['blockers'][0])
        query.assert_not_called()

    def test_batch_runs_independent_queries_concurrently_and_preserves_order(self):
        from threading import Barrier
        from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
        barrier = Barrier(2)
        def reader(request):
            barrier.wait(timeout=2)
            return {'sourceStatus':'verified','reportCode':'abc123','events':[{'timestamp':request['options']['startTime']}]}
        service = ServerConfiguredSourceQuery(wcl_reader=reader)
        result = service.query('warcraftlogs_batch','reports', {'queries':[
            {'target':'https://www.warcraftlogs.com/reports/abc123?fight=4','options':{'startTime':10,'endTime':20}},
            {'target':'https://www.warcraftlogs.com/reports/abc123?fight=4','options':{'startTime':30,'endTime':40}}]})
        self.assertEqual([r['facts'][0]['events'][0]['timestamp'] for r in result['results']], [10,30])

    def test_followup_reuses_context_but_fetches_correct_new_events(self):
        reader = wcl_source.WclRunReader()
        calls = []
        def graphql(query, variables):
            calls.append(query)
            report = {'events': {'data': [{'timestamp': variables.get('startTime') or 0}], 'nextPageTimestamp': None}}
            if 'playerDetails' in query:
                report.update(title='context', fights=[{'id':4,'endTime':900}], casts={'data':{'entries':[{'total':42}]}}, masterData={})
            return {'reportData':{'report':report}}
        with patch.object(wcl_source,'warcraftlogs_credentials_state',return_value={'configured':True,'mode':'v2_oauth','api':'v2'}), patch.object(wcl_source,'_graphql',side_effect=graphql):
            first = reader({'wclUrl':'https://www.warcraftlogs.com/reports/abc123?fight=4&source=5','options':{'startTime':0,'endTime':900}})
            second = reader({'wclUrl':'https://www.warcraftlogs.com/reports/abc123?fight=4&source=5','options':{'startTime':500,'endTime':900}})
        self.assertEqual(second['events'][0]['timestamp'],500)
        self.assertEqual(second['casts']['entries'][0]['total'],42)
        self.assertEqual(first['reportTitle'],second['reportTitle'])
        self.assertEqual(len(calls),2)
        self.assertNotIn('playerDetails',calls[1])
        self.assertNotIn('casts:',calls[1])

    def test_distinct_actor_is_not_given_another_actors_tables(self):
        reader = wcl_source.WclRunReader()
        def graphql(query, variables):
            return {'reportData':{'report':{'fights':[{'id':4}],
                'casts':{'data':{'entries':[{'total':variables['sourceId']}]}},
                'events':{'data':[],'nextPageTimestamp':None}}}}
        with patch.object(wcl_source,'warcraftlogs_credentials_state',return_value={'configured':True,'mode':'v2_oauth','api':'v2'}), patch.object(wcl_source,'_graphql',side_effect=graphql):
            a = reader({'wclUrl':'https://www.warcraftlogs.com/reports/abc123?fight=4&source=5'})
            b = reader({'wclUrl':'https://www.warcraftlogs.com/reports/abc123?fight=4&source=6'})
        self.assertEqual(a['casts']['entries'][0]['total'],5)
        self.assertEqual(b['casts']['entries'][0]['total'],6)

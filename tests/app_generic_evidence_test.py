"""Historical WCL reuse preserves scope and observed, incomplete facts."""
import json
import unittest
from server.app.chickenbro.research_evidence import project_evidence


def row(view, payload, *, status='verified', request=None, call='call'):
    fact = {'reportCode':'A', 'fightId':1, 'sourceId':7, 'view':view, **payload}
    result = ('run', call, {'status':status, 'facts':[fact]}, 'now')
    return result if request is None else (*result, request)


class GenericEvidenceTest(unittest.TestCase):
    def test_healing_whole_fight_and_distinct_windows_survive_deduplication(self):
        rows = [row('healing', {'healing':{'complete':True, 'window':window,
                    'totals':{'effective':total}, 'entries':[]}})
                for window,total in [({},100), ({'startTime':0,'endTime':100},10),
                                     ({'startTime':100,'endTime':200},20)]]
        facts = project_evidence(rows + rows)['facts']
        self.assertEqual(len(facts), 3)
        self.assertEqual([f['healing']['totals']['effective'] for f in facts], [100,10,20])

    def test_overview_casts_damage_without_player_stats_are_reused(self):
        out = project_evidence([row('overview', {'casts':{'entries':[{'id':1,'total':3}]},
                                                'damage':{'entries':[{'id':2,'total':500}]}})])
        self.assertEqual(len(out['facts']), 1)
        self.assertEqual(out['facts'][0]['casts']['entries'][0]['total'], 3)
        self.assertEqual(out['facts'][0]['damage']['entries'][0]['total'], 500)

    def test_partial_statistics_keep_known_values_and_completeness(self):
        stats = {'startTime':100,'endTime':200,'observedThrough':150,'dataType':'All',
                 'complete':False,'metricsComplete':False,'nextPageTimestamp':150,
                 'casts':[{'abilityId':1,'count':2}], 'healing':{'effective':30,'missingValues':1},
                 'resources':[{'resourceType':0,'waste':20,'missingValues':0}]}
        out = project_evidence([row('statistics', {'statistics':stats, 'sourceStatus':'partial',
                                   'blockers':['Next page was unavailable.']}, status='partial')])
        self.assertEqual(len(out['facts']), 1)
        fact = out['facts'][0]
        self.assertEqual(fact['status'], 'partial')
        self.assertEqual(fact['statistics'], stats)
        self.assertEqual(fact['blockers'], ['Next page was unavailable.'])

    def test_event_samples_keep_filters_pagination_and_exact_window_identity(self):
        rows = [row('events', {'eventPage':{'dataType':kind,'startTime':0,'endTime':100,
                   'complete':False,'nextPageTimestamp':50,'count':100},
                   'events':[{'timestamp':i,'type':'cast','abilityGameID':12} for i in range(100)]})
                for kind in ('Casts','All')]
        out = project_evidence(rows)
        self.assertEqual(len(out['facts']), 2)
        for fact in out['facts']:
            self.assertGreater(len(fact['events']), 0)
            self.assertLessEqual(len(fact['events']), 12)
            self.assertTrue(fact['historicalTruncated'])
            self.assertFalse(fact['eventPage']['complete'])
            self.assertEqual(fact['eventPage']['nextPageTimestamp'], 50)
        self.assertTrue(out['truncated'])

    def test_missing_legacy_scope_does_not_dedup_unknown_filters(self):
        payload = {'events':[{'timestamp':10,'type':'cast'}]}
        rows = [row('events', payload, call='a'), row('events', payload, call='b')]
        out = project_evidence(rows)
        self.assertEqual(len(out['facts']),2)
        self.assertTrue(all(f['historicalScope']['provenance']=='unknown' for f in out['facts']))

    def test_request_filters_distinguish_legacy_event_facts_and_batch_members(self):
        payload = {'events':[{'timestamp':10,'type':'cast'}]}
        requests = [{'options':{'view':'events','dataType':kind,'startTime':0,'endTime':100}}
                    for kind in ('Casts','All')]
        result = project_evidence([row('events',payload,request=req) for req in requests])
        self.assertEqual(len(result['facts']),2)
        self.assertEqual(result['facts'][0]['historicalScope']['filters']['dataType'],'Casts')
        members = [row('events',payload)[2] for _ in requests]
        batch = ('r','c',{'status':'partial','results':members},'now', {'options':{'queries':requests}})
        self.assertEqual(len(project_evidence([batch])['facts']),2)

    def test_large_recent_tables_leave_room_for_other_views_and_total_bound(self):
        rows = [row('healing',{'sourceId':actor,'healing':{'complete':True,'window':{},
                  'totals':{'raw':100},'entries':[{'id':i,'name':'法术'*1000,'total':100} for i in range(80)]}})
                for actor in range(10)]
        rows += [row('overview', {'players':[{'id':7,'combatantInfo':{'stats':{'Crit':622}}}]}),
                 row('statistics', {'statistics':{'complete':True,'startTime':0,'endTime':100,
                      'dataType':'Resources','resources':[{'resourceType':0,'waste':40}]}})]
        out = project_evidence(rows)
        self.assertLessEqual(len(json.dumps(out,ensure_ascii=False).encode()),48000)
        self.assertTrue(out['truncated'])
        self.assertTrue(any(f.get('statistics') for f in out['facts']))
        self.assertTrue(any(f.get('players') for f in out['facts']))

    def test_full_view_tables_remain_whole_fight_despite_event_window(self):
        out = project_evidence([row('full', {'casts':{'entries':[{'id':1,'total':7}]},
              'eventPage':{'dataType':'Casts','startTime':50,'endTime':100,'complete':True},
              'events':[{'timestamp':60,'type':'cast','abilityGameID':1}]})])
        self.assertEqual(out['facts'][0].get('historicalTableScope'), 'whole_fight')
        self.assertEqual(out['facts'][0]['historicalScope']['filters']['startTime'],50)

    def test_event_field_omission_is_explicit_even_when_page_and_sample_fit(self):
        out = project_evidence([row('events', {'eventPage':{'complete':True,'dataType':'All'},
               'events':[{'timestamp':1,'type':'cast','abilityGameID':2,'unretainedDetail':{'data':1}}]})])
        self.assertTrue(out['facts'][0]['historicalTruncated'])
        self.assertTrue(out['facts'][0]['eventPage']['complete'])

    def test_partial_newer_query_does_not_hide_complete_older_query(self):
        base = {'startTime':0,'endTime':100,'dataType':'Casts','casts':[{'abilityId':2,'count':3}]}
        rows = [row('statistics', {'statistics':{**base,'complete':False}}, status='partial'),
                row('statistics', {'statistics':{**base,'complete':True}})]
        facts = project_evidence(rows)['facts']
        self.assertEqual(len(facts),2)
        self.assertEqual([f['status'] for f in facts], ['partial','verified'])

    def test_large_gear_and_talents_preserve_actor_stats(self):
        player = {'id':7,'name':'Player','combatantInfo':{'stats':{'Crit':622},
                  'gear':[{'id':i,'slot':i,'name':'Equipment name '*20,'bonusIDs':list(range(30))} for i in range(20)],
                  'talents':[{'id':i,'name':'Talent name '*20} for i in range(40)]}}
        out = project_evidence([row('overview',{'players':[player]})])
        self.assertEqual(len(out['facts'][0]['players']),1)
        self.assertEqual(out['facts'][0]['players'][0]['combatantInfo']['stats']['Crit'],622)
        self.assertTrue(out['truncated'])

    def test_legacy_event_page_without_data_type_keeps_calls_separate(self):
        payload = {'eventPage':{'startTime':0,'endTime':100,'complete':True},
                   'events':[{'timestamp':10,'type':'cast'}]}
        out = project_evidence([row('events',payload,call='a'),row('events',payload,call='b')])
        self.assertEqual(len(out['facts']),2)
        self.assertTrue(all(f['historicalScope']['provenance']=='unknown' for f in out['facts']))

    def test_database_history_cutoff_is_reported_even_when_rows_deduplicate(self):
        from contextlib import nullcontext
        from server.app.chickenbro.research_evidence import load_evidence
        class Cursor:
            def execute(self, sql, params):
                self.sql, self.params = sql, params
            def fetchall(self):
                return [row('overview', {'casts':{'entries':[{'id':1,'total':2}]}})] * 49
        cursor = Cursor()
        class Connection:
            def cursor(self):
                return nullcontext(cursor)
        out = load_evidence(lambda:nullcontext(Connection()), 'owner', 'conversation')
        self.assertEqual(len(out['facts']),1)
        self.assertTrue(out['truncated'])

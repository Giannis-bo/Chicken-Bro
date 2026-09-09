import unittest
from unittest.mock import patch
from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
from server.app.simulation.sources import InvalidSourceLink

ZONE={'id':53,'name':'Raid','partitions':[{'id':1,'name':'12.1','default':True}], 'difficulties':[{'id':4,'name':'Heroic'}], 'encounters':[{'id':3470,'name':'Boss'}]}
def row(name='Player',spec='Feral'):
    return {'name':name,'class':'Druid','spec':spec,'amount':123.5,'duration':100000,'startTime':123456789,
            'report':{'code':'MLNA4WKvz8Fchmgx','fightID':1},'server':{'name':'Realm','region':'EU'}}

class RankingsTests(unittest.TestCase):
    def setUp(self):
        self.service=ServerConfiguredSourceQuery()
    def query(self,opts):
        return self.service.query('warcraftlogs_rankings','rankings',opts)
    def test_catalog_preserves_partition_and_difficulty(self):
        from server.app.chickenbro import wcl_rankings as w
        with patch.object(w,'_graphql',return_value={'worldData':{'zones':[ZONE]}}):
            r=self.query({})
        self.assertEqual(r['facts'][0]['partitions'][0]['name'],'12.1')
    def test_rankings_preserve_explicit_scope_and_pagination(self):
        from server.app.chickenbro import wcl_rankings as w
        data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':True,'count':100,'rankings':[row(str(i)) for i in range(100)]}}}}
        with patch.object(w,'_graphql',return_value=data) as call:
            r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1,'limit':10})
        self.assertEqual(r['status'],'source_reference')
        self.assertEqual(r['pagination']['nextOffset'],10)
        self.assertEqual(r['rankings'][0]['rank'],1)
        self.assertEqual(r['scope']['region'],'world')
        self.assertIn('fight=1',r['rankings'][0]['reportUrl'])
        self.assertIsNone(call.call_args.args[1]['region'])
    def test_wrong_class_or_malformed_row_is_partial_not_re_ranked(self):
        from server.app.chickenbro import wcl_rankings as w
        data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':False,'count':2,'rankings':[row(spec='Balance'),row()]}}}}
        with patch.object(w,'_graphql',return_value=data):r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1})
        self.assertEqual(r['status'],'partial')
        self.assertEqual(r['rankings'][0]['rank'],2)
    def test_anonymous_opaque_rank_is_retained_but_not_analyzable(self):
        from server.app.chickenbro import wcl_rankings as w
        anonymous=dict(row(name='Different display label'),server=None,report={'code':'a:QwErTyUiOpAsDfGh','fightID':17})
        data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':False,'rankings':[row(),anonymous,row(spec='Balance')]}}}}
        with patch.object(w,'_graphql',return_value=data):
            r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1})
        self.assertEqual([x['rank'] for x in r['rankings']],[1,2])
        named,anon=r['rankings'];self.assertEqual(named['identityStatus'],'named');self.assertTrue(named['analysisEligible'])
        self.assertEqual(anon['identityStatus'],'anonymous');self.assertFalse(anon['analysisEligible']);self.assertIsNone(anon['server']);self.assertIsNone(anon['reportUrl'])
        self.assertEqual(anon['report'],anonymous['report']);self.assertEqual(anon['name'],'Different display label')
        self.assertEqual({k:r['pagination'][k] for k in ['returned','namedReturned','anonymousReturned','skippedInvalid']},{'returned':2,'namedReturned':1,'anonymousReturned':1,'skippedInvalid':1})
    def test_full_page_counts_anonymous_without_replacement_or_extra_fetch(self):
        from server.app.chickenbro import wcl_rankings as w
        rows=[row(str(i)) for i in range(100)]
        rows[47]={**rows[47],'server':None,'report':{'code':'a:QwErTyUiOpAsDfGh','fightID':17}}
        data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':True,'rankings':rows}}}}
        with patch.object(w,'_graphql',return_value=data) as fetch:
            r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1,'limit':100})
        self.assertEqual(r['status'],'source_reference');fetch.assert_called_once()
        self.assertEqual([x['rank'] for x in r['rankings']],list(range(1,101)))
        self.assertEqual(r['pagination']['returned'],100);self.assertEqual(r['pagination']['namedReturned'],99)
        self.assertEqual(r['pagination']['anonymousReturned'],1);self.assertEqual(r['pagination']['skippedInvalid'],0)

    def test_anonymous_server_presence_matches_official_omission_shape(self):
        from server.app.chickenbro import wcl_rankings as w
        # Preserve omission: do not manufacture a server=None key using .get().
        omitted={k:v for k,v in row(name='Opaque display').items() if k!='server'}
        omitted['report']={'code':'a:QwErTyUiOpAsDfGh','fightID':17}
        self.assertNotIn('server',omitted)
        normal_omitted={**omitted,'report':{'code':'QwErTyUiOpAsDfGh','fightID':17}}
        rows=[omitted,{**omitted,'server':None},{**omitted,'server':{}},normal_omitted]
        data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':False,'rankings':rows}}}}
        with patch.object(w,'_graphql',return_value=data):
            r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1})
        self.assertEqual([x['rank'] for x in r['rankings']],[1,2])
        self.assertEqual(r['pagination']['anonymousReturned'],2)
        self.assertEqual(r['pagination']['skippedInvalid'],2)
        for entry in r['rankings']:
            self.assertIsNone(entry['server']);self.assertIsNone(entry['reportUrl'])
            self.assertFalse(entry['analysisEligible']);self.assertEqual(entry['identityStatus'],'anonymous')

    def test_anonymous_validation_is_strict_and_never_fills_skipped_rank(self):
        from server.app.chickenbro import wcl_rankings as w
        good=dict(row(),server=None,report={'code':'a:QwErTyUiOpAsDfGh','fightID':17})
        for change in [dict(report={'code':'a:short','fightID':17}),dict(report={'code':'a:QwErTyUiOpAsDfGh','fightID':True}),dict(server={}),dict(amount=0),dict(amount=float('nan')),dict(spec='Balance')]:
            bad={**good,**change};data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':False,'rankings':[bad,good]}}}}
            with self.subTest(change=change),patch.object(w,'_graphql',return_value=data):
                r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1})
                self.assertEqual([x['rank'] for x in r['rankings']],[2]);self.assertEqual(r['pagination']['skippedInvalid'],1)

    def test_invalid_inputs_rejected_before_network(self):
        from server.app.chickenbro import wcl_rankings as w
        for opts in [{'encounterId':True},{'zoneId':-1},{'page':21},{'region':'evil'},{'filter':'secret'},{'encounterId':3470}]:
            with self.subTest(opts=opts),patch.object(w,'_graphql') as call:
                with self.assertRaises(InvalidSourceLink):self.query(opts)
                call.assert_not_called()
    def test_upstream_failure_not_empty_success(self):
        from server.app.chickenbro import wcl_rankings as w
        with patch.object(w,'_graphql',side_effect=RuntimeError('secret token')):r=self.query({})
        self.assertEqual(r['status'],'unavailable')
        self.assertNotIn('secret',str(r))
    def test_rpc_dispatch(self):
        from server import chickenbro_native_mcp as m
        names=[d['name'] for d in m.TOOL_DEFINITIONS]
        self.assertIn('query_warcraftlogs_rankings',names)
        with patch.object(m,'query_source_gateway',return_value={'status':'source_reference'}) as call:
            m.handle_rpc_request({'id':1,'method':'tools/call','params':{'name':'query_warcraftlogs_rankings','arguments':{}}})
        call.assert_called_once_with('warcraftlogs_rankings','rankings',options={})

    def test_malformed_nested_rows_preserve_valid_rows_and_ordinals(self):
        from server.app.chickenbro import wcl_rankings as w
        for bad in [dict(row(),report='bad'),dict(row(),**{'class':None}),dict(row(),server=[]),dict(row(),name=None),dict(row(),server=None)]:
            data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':False,'count':2,'rankings':[bad,row()]}}}}
            with self.subTest(bad=bad),patch.object(w,'_graphql',return_value=data):
                r=self.query({'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1})
            self.assertEqual(r['status'],'partial')
            self.assertEqual([x['rank'] for x in r['rankings']],[2])
            self.assertEqual(r['pagination']['skippedInvalid'],1)
    def test_explicit_zone_and_encounter_are_cross_checked(self):
        from server.app.chickenbro import wcl_rankings as w
        data={'worldData':{'encounter':{'id':3470,'name':'Boss','zone':ZONE,'characterRankings':{'page':1,'hasMorePages':False,'rankings':[row()]}}}}
        options={'zoneId':53,'encounterId':3470,'difficulty':4,'className':'Druid','specName':'Feral','partition':1}
        with patch.object(w,'_graphql',return_value=data):
            r=self.query(options)
            mismatch=self.query({**options,'zoneId':54})
        self.assertEqual(r['status'],'source_reference')
        self.assertEqual(mismatch['status'],'scope_mismatch')
    def test_ranking_capability_revoke_blocks_before_api(self):
        from server.app.chickenbro import wcl_rankings as w
        from server.app.chickenbro.source_gateway import ChickenbroSourceGateway,SourceGatewayUnauthorized
        gateway=ChickenbroSourceGateway()
        token=gateway.issue_capability()
        with patch.object(w,'_graphql',return_value={'worldData':{'zones':[ZONE]}}) as api:
            self.assertEqual(gateway.query(token,'warcraftlogs_rankings','rankings')['status'],'source_reference')
            gateway.revoke(token)
            with self.assertRaises(SourceGatewayUnauthorized):gateway.query(token,'warcraftlogs_rankings','rankings')
        self.assertEqual(api.call_count,1)

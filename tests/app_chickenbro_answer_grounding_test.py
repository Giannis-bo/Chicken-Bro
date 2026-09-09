import json
import unittest
from datetime import datetime, timedelta, timezone
from server.app.chickenbro.answer_grounding import collect_evidence, validate_answer, repair_context
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway, SourceGatewayUnauthorized

CODE = 'aB3dE5gH7jK9mN2p'
URL = f'https://www.warcraftlogs.com/reports/{CODE}'
def result(code=CODE):
    return {'sourceKey':'warcraftlogs','status':'verified','facts':[{'reportCode':code,'fightId':'73','sourceId':'91','fight':{'name':'Arbitrary encounter','startTime':1000,'endTime':91000},'casts':{'entries':[{'name':'Arbitrary spell','guid':4321,'total':4}]},'events':[{'type':'cast','timestamp':2300,'abilityGameID':4321}]}]}

class GroundingTests(unittest.TestCase):
    def test_observed_and_unobserved_scopes(self):
        e=collect_evidence({},result())
        self.assertEqual(validate_answer(URL+'?fight=73&source=91',e),[])
        for suffix in ['?fight=74','?fight=73&source=92']:
            self.assertIn('WCL_REFERENCE_UNOBSERVED',validate_answer(URL+suffix,e))
        self.assertIn('WCL_REFERENCE_UNOBSERVED',validate_answer(URL.replace(CODE,'Z'*16),e))
        self.assertIn('WCL_REFERENCE_MALFORMED',validate_answer(URL+'BAD?fight=73',e))
    def test_normal_and_rank_only(self):
        self.assertEqual(validate_answer('DPS explanation https://www.warcraftlogs.com/zone/rankings/53/',{}),[])
        e=collect_evidence({}, {'status':'source_reference','sourceKey':'warcraftlogs_rankings','scope':{'encounterId':999,'encounterName':'Dynamic'},'rankings':[{'rank':1,'report':{'code':CODE,'fightID':73}}]})
        self.assertEqual(validate_answer(URL+'?fight=73',e),[])
        self.assertIn('WCL_GROUP_OBSERVATION_EMPTY', validate_answer('| Boss | Observation |\n| --- | --- |\n| Dynamic | — |', e))
    def test_bounds_and_safe_projection(self):
        r=result();r['facts'][0]['secret']='NEVER_COPY';r['facts'][0]['events']*=100000
        e=collect_evidence({},r);text=repair_context(e)
        self.assertLessEqual(len(text),64000);self.assertNotIn('NEVER_COPY',text);self.assertTrue(json.loads(text)['truncated']);self.assertIn(URL,text)
    def test_failed_results_not_registered(self):
        r=result();r['status']='blocked';self.assertEqual(collect_evidence({},r)['reports'],[])
    def test_untrusted_shapes_and_memory_limit(self):
        for value in [None, [], {'results': 'bad', 'status':'verified', 'sourceKey':'warcraftlogs', 'facts':{'bad':'shape'}}, {'status':'verified','sourceKey':'warcraftlogs','facts':[{'reportCode':CODE,'fightId':73,'casts': [],'events':'bad'}]}]:
            self.assertLessEqual(len(repair_context(collect_evidence({}, value))),64000)
        e={}
        for i in range(500):
            e=collect_evidence(e,result(f'{i:016d}'))
        self.assertLessEqual(len(e['reports']),2048)
        self.assertTrue(json.loads(repair_context(e))['truncated'])
        self.assertLessEqual(len(repair_context(e)),64000)
    def test_capability_capacity_and_inflight_revoke(self):
        g=ChickenbroSourceGateway(query_service=lambda *_:result())
        for _ in range(256):g.issue_capability()
        with self.assertRaises(SourceGatewayUnauthorized):g.issue_capability()
        h=ChickenbroSourceGateway(query_service=lambda *_: (h.revoke(token) or result()))
        token=h.issue_capability();h.query(token,'warcraftlogs',URL)
        self.assertFalse(h._answer_evidence)

    def test_html_entities_and_duplicates(self):
        e=collect_evidence({},result())
        for query in ['?fight=73&amp;source=92', '?source=91&#38;fight=74']:
            self.assertIn('WCL_REFERENCE_UNOBSERVED',validate_answer('[x]('+URL+query+')',e))
        self.assertIn('WCL_REFERENCE_MALFORMED',validate_answer(URL+'?fight=73&amp;fight=74',e))
        self.assertEqual(validate_answer(URL+'?fight=73&amp;source=91',e),[])
    def test_identity_statistics_and_independent_windows_survive(self):
        ranking={'status':'partial','sourceKey':'warcraftlogs_rankings','scope':{'encounterName':'Dynamic'},'rankings':[{'rank':2,'name':'New Name','server':{'name':'Realm','region':'EU'},'report':{'code':CODE,'fightID':73}}]}
        e=collect_evidence({},ranking)
        first=result(); f=first['facts'][0]; f['players']=[{'id':91,'name':'New Name','server':'Realm','region':'EU','type':'Rogue'},{'id':92,'name':'DO_NOT_COPY'}];f['casts'].update(rowsTruncated=False,totalTime=90000);f['eventPage']={'startTime':1000,'endTime':31000,'complete':True}
        e=collect_evidence(e,first)
        later=result();later['facts'][0]['casts']={};later['facts'][0]['eventPage']={'startTime':31000,'endTime':61000,'complete':False};later['limitations']=['Some fields failed; missing is not zero.']
        e=collect_evidence(e,later);e=collect_evidence(e,ranking)
        r=next(r for r in e['reports'] if r['source']=='91')
        self.assertEqual(r['player']['name'],'New Name');self.assertEqual(r['rank'],2);self.assertEqual(r['group']['encounterName'],'Dynamic')
        self.assertEqual(r['casts'][0]['total'],4);self.assertFalse(r['castsMeta']['rowsTruncated']);self.assertEqual(r['castsMeta']['totalTime'],90000)
        self.assertEqual(r['castsMeta']['window'],{'startTime':1000,'endTime':91000})
        self.assertEqual(r['eventWindows'][0]['page']['endTime'],31000)
        self.assertEqual(len(r['eventWindows']),2);self.assertFalse(r['eventPage']['complete']);self.assertIn('missing is not zero',repair_context(e));self.assertNotIn('DO_NOT_COPY',repair_context(e))
        unscoped=result();unscoped['facts'][0]['sourceId']='';e=collect_evidence(e,unscoped);e=collect_evidence(e,ranking)
        self.assertEqual(next(r for r in e['reports'] if not r['source'])['kind'],'report')
    def test_absent_empty_partial_and_attempted(self):
        missing=result();missing['facts'][0]['casts']={};e=collect_evidence({},missing)
        self.assertEqual(e['reports'][0]['castsMeta']['state'],'absent')
        empty=result();empty['facts'][0]['casts']={'entries':[],'rowsTruncated':False};e=collect_evidence({},empty)
        self.assertEqual(e['reports'][0]['castsMeta']['state'],'returned_empty')
        partial=result();partial['status']='partial';e=collect_evidence({},partial)
        self.assertEqual(e['reports'][0]['status'],'partial');self.assertEqual(validate_answer(URL+'?fight=73&source=91',e),[])
        self.assertIn('WCL_REFERENCE_UNOBSERVED',validate_answer(URL+'?fight=74',e))
        g=ChickenbroSourceGateway(query_service=lambda *_:{'status':'blocked'})
        token=g.issue_capability();g.query(token,'warcraftlogs',URL);e=g.answer_evidence(token)
        self.assertTrue(e['attemptedWcl']);self.assertIn('WCL_REFERENCE_UNOBSERVED',validate_answer(URL,e))
        def fail(*_):raise ValueError('upstream unavailable')
        g=ChickenbroSourceGateway(query_service=fail);token=g.issue_capability()
        with self.assertRaises(ValueError):g.query(token,'warcraftlogs',URL)
        self.assertTrue(g.answer_evidence(token)['attemptedWcl'])

    def test_capability_isolation_lifecycle(self):
        now=[datetime.now(timezone.utc)]
        g=ChickenbroSourceGateway(query_service=lambda *_:result(),now=lambda:now[0],capability_ttl_seconds=60)
        a,b=g.issue_capability(),g.issue_capability();g.query(a,'warcraftlogs',URL)
        self.assertTrue(g.answer_evidence(a)['reports']);self.assertFalse(g.answer_evidence(b)['reports'])
        snapshot=g.answer_evidence(a);snapshot['reports'].clear();self.assertTrue(g.answer_evidence(a)['reports'])
        g.revoke(a)
        with self.assertRaises(SourceGatewayUnauthorized):g.answer_evidence(a)
        now[0]+=timedelta(seconds=61)
        with self.assertRaises(SourceGatewayUnauthorized):g.answer_evidence(b)
        self.assertFalse(g._answer_evidence)

if __name__=='__main__':unittest.main()

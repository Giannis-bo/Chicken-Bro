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
    def test_coverage_survives_detail_projection_without_stitching_snapshots(self):
        e={}
        for group in range(12):
            for offset in (0,5):
                rows=[{'rank':i+1,'name':f'Player{i}', 'report':{'code':f'{group*100+i:016d}','fightID':1}} for i in range(offset,offset+5)]
                e=collect_evidence(e,{'sourceKey':'warcraftlogs_rankings','status':'source_reference','queriedAt':str(offset),
                    'scope':{'encounterId':group,'encounterName':f'Dynamic {group}'},'rankings':rows,
                    'pagination':{'page':1,'offset':offset,'limit':5,'returned':5,'skippedInvalid':0,'hasMore':True}})
            for actor in range(2):
                packet=result(f'{group*100+actor:016d}');fact=packet['facts'][0];fact['fightId']=1
                fact['casts']['entries']=[{'name':'Long spell '*20,'guid':i,'total':i+1} for i in range(24)]
                e=collect_evidence(e,packet)
        context=json.loads(repair_context(e));coverage=context['coverage']
        self.assertLessEqual(len(repair_context(e)),64000)
        self.assertTrue(context['projectionTruncated'])
        self.assertFalse(coverage['sourceIndexTruncated'])
        self.assertEqual(len(coverage['rankingSnapshots']),24)
        self.assertEqual({s['scope']['encounterId'] for s in coverage['rankingSnapshots']},set(range(12)))
        self.assertTrue(all(s['returnedIdentityCount']==5 and s['requestedSliceComplete'] for s in coverage['rankingSnapshots']))
        self.assertTrue(all(s['rankRanges'] in ([[1,5]],[[6,10]]) for s in coverage['rankingSnapshots']))
        self.assertEqual(len(coverage['reportReceipts']),24)
        self.assertTrue(all(r['castRowsReturned']==24 for r in coverage['reportReceipts']))

    def test_partial_empty_directory_and_failed_member_truth(self):
        directory={'sourceKey':'warcraftlogs_rankings','status':'source_reference','facts':[{'id':719,'name':'Dynamic zone','encounters':[{'id':817,'name':'Dynamic boss'}],'partitions':[{'id':9,'name':'Live','default':True}],'difficulties':[{'id':4,'name':'Hard'}]}]}
        e=collect_evidence({},directory)
        for status,rows in [('partial',[{'rank':1,'report':{'code':CODE,'fightID':73}}]),('source_reference',[])]:
            e=collect_evidence(e,{'sourceKey':'warcraftlogs_rankings','status':status,'scope':{'encounterId':817},'rankings':rows,'pagination':{'page':1,'offset':0,'limit':10,'returned':len(rows)}})
        e=collect_evidence(e,{'sourceKey':'warcraftlogs','status':'partial','results':[result(),{'sourceKey':'warcraftlogs','status':'blocked','facts':[],
            'evidence':[{'reportCode':'Z'*16,'fightId':'82','sourceUrl':'https://www.warcraftlogs.com/reports/'+'Z'*16+'#fight=82&source=13'}],
            'limitations':['Warcraft Logs OAuth provider failed','SECRET_DO_NOT_RETAIN'], 'error':'SECRET_DO_NOT_RETAIN'}]})
        c=json.loads(repair_context(e))['coverage']
        self.assertEqual(c['directories'][0]['encounters'][0]['id'],817)
        self.assertFalse(any(s['requestedSliceComplete'] for s in c['rankingSnapshots']))
        self.assertEqual(c['failures'][0]['source'],'13');self.assertEqual(c['failures'][0]['stage'],'source_query')
        self.assertEqual(c['failures'][0]['errorCode'],'WCL_OAUTH_PROVIDER_FAILED')
        self.assertNotIn('SECRET_DO_NOT_RETAIN',json.dumps(e))
        self.assertEqual(len(c['reportReceipts']),1)
        self.assertNotIn('Z'*16,[r['code'] for r in e['reports']])

    def test_snapshot_identity_drift_and_partial_are_never_merged(self):
        packet={'sourceKey':'warcraftlogs_rankings','status':'source_reference','queriedAt':'first','scope':{'zoneId':22,'encounterId':23},
            'pagination':{'page':1,'offset':0,'limit':2,'returned':2,'skippedInvalid':0},
            'rankings':[{'rank':1,'report':{'code':CODE,'fightID':73}},{'rank':2,'report':{'code':'B'*16,'fightID':1}}]}
        e=collect_evidence({},packet);packet['queriedAt']='second';packet['rankings'][1]['report']['code']='C'*16;e=collect_evidence(e,packet)
        snapshots=e['coverage']['rankingSnapshots']
        self.assertEqual(len(snapshots),2);self.assertNotEqual(snapshots[0]['snapshotId'],snapshots[1]['snapshotId'])
        packet['rankings'][0]['name']='Changed identity';e=collect_evidence(e,packet)
        self.assertNotEqual(e['coverage']['rankingSnapshots'][-1]['snapshotId'],snapshots[-1]['snapshotId'])
        packet['status']='partial';e=collect_evidence(e,packet)
        self.assertFalse(e['coverage']['rankingSnapshots'][-1]['requestedSliceComplete'])
        packet['status']='source_reference';packet['rankings'][1]['rank']=1;e=collect_evidence(e,packet)
        self.assertFalse(e['coverage']['rankingSnapshots'][-1]['requestedSliceComplete'])

    def test_coverage_bounds_and_scope_isolation(self):
        from server.app.chickenbro.answer_grounding import MAX_INDEX
        e={}
        for i in range(530):
            packet={'sourceKey':'warcraftlogs_rankings','status':'source_reference','queriedAt':str(i),
                'scope':{'encounterId':i%7,'encounterName':'Name'*60},'rankings':[],
                'pagination':{'page':1,'offset':0,'limit':10,'returned':0,'skippedInvalid':0}}
            e=collect_evidence(e,packet)
        self.assertLessEqual(len(json.dumps(e,ensure_ascii=False)),MAX_INDEX)
        context=json.loads(repair_context(e));self.assertLessEqual(len(repair_context(e)),64000)
        self.assertTrue(context['coverage']['sourceIndexTruncated'])
        self.assertEqual({s['scope']['encounterId'] for s in context['coverage']['rankingSnapshots']},set(range(7)))
        self.assertFalse(any(s['requestedSliceComplete'] for s in context['coverage']['rankingSnapshots']))
        g=ChickenbroSourceGateway(query_service=lambda *_:result());a,b=g.issue_capability(),g.issue_capability();g.query(a,'warcraftlogs',URL)
        self.assertTrue(g.answer_evidence(a)['coverage']['reportReceipts']);self.assertNotIn('coverage',g.answer_evidence(b))
        g.revoke(a);self.assertNotIn(a,g._answer_evidence)

    def test_large_catalog_and_group_names_stay_bounded(self):
        facts=[{'id':i,'name':'x'*240,'encounters':[{'id':n,'name':'y'*240} for n in range(200)]} for i in range(100)]
        e=collect_evidence({}, {'sourceKey':'warcraftlogs_rankings','status':'source_reference','facts':facts})
        self.assertLessEqual(len(json.dumps(e,ensure_ascii=False)),512000)
        e['groups']=[{key:'x'*240 for key in ('zoneId','encounterId','encounterName','difficulty','partition','className','specName','region','metric')} for _ in range(100)]
        self.assertLessEqual(len(repair_context(e)),64000)
        self.assertTrue(json.loads(repair_context(e))['coverage']['sourceIndexTruncated'])

    def test_receipt_input_limits_explicitly_mark_actual_omission(self):
        packets=[
            {'sourceKey':'warcraftlogs_rankings','status':'source_reference','facts':[{'id':i} for i in range(101)]},
            *[{'sourceKey':'warcraftlogs_rankings','status':'source_reference','facts':[{'id':1, field:[{'id':i} for i in range(201)]}]} for field in ('encounters','partitions','difficulties')],
            {'sourceKey':'warcraftlogs_rankings','status':'source_reference','rankings':[{'rank':i+1,'report':{'code':f'{i:016d}','fightID':1}} for i in range(201)]},
            {'sourceKey':'warcraftlogs','status':'verified','facts':[result(f'{i:016d}')['facts'][0] for i in range(101)]},
            {'sourceKey':'warcraftlogs','status':'blocked','evidence':[{'reportCode':f'{i:016d}','fightId':1} for i in range(101)]},
        ]
        for packet in packets:
            with self.subTest(source=packet['sourceKey'],keys=list(packet)):
                self.assertTrue(collect_evidence({},packet)['coverage']['sourceIndexTruncated'])
        self.assertFalse(collect_evidence({},result())['coverage']['sourceIndexTruncated'])

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

    def test_markdown_links_end_before_fullwidth_separator(self):
        e=collect_evidence({},result())
        good=URL+'?fight=73&source=91'
        self.assertEqual(validate_answer('[a]('+good+')／[b]('+good+')',e),[])
        self.assertIn('WCL_REFERENCE_UNOBSERVED',validate_answer('[a]('+good+')／[b]('+URL+'?fight=73&source=92)',e))
        self.assertIn('WCL_REFERENCE_MALFORMED',validate_answer('[a]('+good+')／[b]('+URL+'BAD?fight=73&source=91)',e))

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

import os
import unittest
from uuid import uuid4
from unittest.mock import Mock, patch
from server.app.identity.domain import Principal
from server.app.poe2.application import Poe2Error
from server.app.poe2.imports.application import ImportApplication,packet_json
from server.app.poe2.imports.repository import PostgresImportRepository
from server.app.poe2.imports.worker import ImportWorker
from server.app.poe2.repository import PostgresPoe2Repository
from tests.app_poe2_jobs_postgres_test import FakeEngine

NINJA='https://poe.ninja/poe2/profile/a/Standard/character/c'
WEGAME='https://www.wegame.com.cn/helper/poe2/#/share/test'
XML='<PathOfBuilding2><Build/></PathOfBuilding2>'

@unittest.skipUnless(os.environ.get('POE2_TEST_DATABASE_URL'),'Candidate PostgreSQL required')
class ImportPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.url=os.environ['POE2_TEST_DATABASE_URL']
        if 'chickenbro_poe2_candidate' not in cls.url:raise RuntimeError('Candidate DB only')
        cls.admin=staticmethod(lambda:psycopg.connect(cls.url))
        def connect():
            c=psycopg.connect(cls.url);c.execute('SET ROLE wow_app');return c
        cls.connect=staticmethod(connect)

    def setUp(self):
        self.a=Principal(uuid4(),'web_cookie');self.b=Principal(uuid4(),'web_cookie')
        with self.admin() as c:
            for p in (self.a,self.b):c.execute('INSERT INTO identity.users(id) VALUES(%s)',(p.user_id,))
        self.repo=PostgresImportRepository(self.connect);self.app=ImportApplication(self.repo)

    def tearDown(self):
        with self.admin() as c:
            c.execute('DELETE FROM poe2.character_imports WHERE user_id IN (%s,%s)',(self.a.user_id,self.b.user_id))
            c.execute('DELETE FROM poe2.jobs WHERE user_id IN (%s,%s)',(self.a.user_id,self.b.user_id))
            c.execute('DELETE FROM identity.users WHERE id IN (%s,%s)',(self.a.user_id,self.b.user_id))

    def create(self,provider='ninja',key='create'):
        return self.app.create(self.a,provider,NINJA if provider=='ninja' else WEGAME,key)

    def test_ninja_network_zero_and_idempotency(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('network')) as spy:
            x=self.create();self.assertEqual(x.status.value,'needs_input');spy.assert_not_called()
        self.assertEqual(self.create().id,x.id)
        with self.assertRaises(Poe2Error) as e:self.app.create(self.a,'ninja',NINJA+'2','create')
        self.assertEqual(e.exception.status,409)
        self.app.supply_source(self.a,x.id,XML,'source')
        self.app.supply_source(self.a,x.id,XML,'source')
        with self.assertRaises(Poe2Error) as e:self.app.supply_source(self.a,x.id,XML.replace('<Build/>','<Build level="2"/>'),'source')
        self.assertEqual(e.exception.status,409)

    def test_owner_isolation_all_existing_id_operations(self):
        x=self.create()
        for action in [lambda:self.app.read(self.b,x.id),lambda:self.app.supply_source(self.b,x.id,XML,'s'),lambda:self.app.retry(self.b,x.id,'r'),lambda:self.app.cancel(self.b,x.id)]:
            with self.assertRaises(Poe2Error) as e:action()
            self.assertEqual(e.exception.status,404)
        # Create has no existing-ID argument; another owner's key is independent.
        y=self.app.create(self.b,'ninja',NINJA,'create');self.assertNotEqual(x.id,y.id)

    def test_cancel_fences_old_worker(self):
        x=self.create('wegame');claim=self.repo.claim('worker')
        self.app.cancel(self.a,x.id)
        self.assertFalse(self.repo.complete(x.id,'worker',claim.attempt,{'status':'ready'}))
        self.assertEqual(self.app.read(self.a,x.id).status.value,'cancelled')

    def test_atomic_ready_and_replay(self):
        x=self.create();self.app.supply_source(self.a,x.id,XML,'source')
        worker=ImportWorker(self.repo,FakeEngine());self.assertTrue(worker.run_once())
        p=self.app.read(self.a,x.id);self.assertEqual(p.status.value,'ready')
        builds=PostgresPoe2Repository(self.connect)
        self.assertIsNotNone(builds.get_build(self.a.user_id,p.build_id))
        self.assertEqual(builds.get_job(self.a.user_id,p.baseline_job_id).status.value,'succeeded')
        self.assertEqual(len(builds.list_builds(self.a.user_id)),1)
        self.assertFalse(worker.run_once())
        self.assertNotIn('source_xml',packet_json(p))

    def test_retry_budget_and_retry_key(self):
        x=self.create('wegame')
        worker=ImportWorker(self.repo,FakeEngine(),collect=Mock(side_effect=TimeoutError),map=Mock(),convert=Mock())
        for _ in range(3):self.assertTrue(worker.run_once())
        self.assertFalse(worker.run_once());self.assertEqual(self.app.read(self.a,x.id).status.value,'failed')
        a=self.app.retry(self.a,x.id,'retry');b=self.app.retry(self.a,x.id,'retry')
        self.assertEqual(a.attempt,b.attempt)

    def test_restart_lease_attempt_and_ttl(self):
        x=self.create('wegame');first=self.repo.claim('same')
        with self.admin() as c:c.execute("UPDATE poe2.character_imports SET lease_expires_at=now()-interval '1 second' WHERE id=%s",(x.id,))
        second=self.repo.claim('same');self.assertGreater(second.attempt,first.attempt)
        self.assertFalse(self.repo.complete(x.id,'same',first.attempt,{'status':'blocked'}))
        with self.admin() as c:c.execute("UPDATE poe2.character_imports SET expires_at=now()-interval '1 second',source_xml='secret' WHERE id=%s",(x.id,))
        self.repo.expire();self.assertIsNone(self.repo.read(self.a.user_id,x.id).source_xml)
        self.assertFalse(self.repo.complete(x.id,'same',second.attempt,{'status':'blocked'}))

    def test_active_constraint_and_ready_validation(self):
        x=self.create('wegame')
        with self.assertRaises(Poe2Error):self.create('wegame','other')
        claim=self.repo.claim('w')
        with self.assertRaises(Poe2Error):self.repo.complete(x.id,'w',claim.attempt,{'status':'ready'})
        self.assertIsNone(self.app.read(self.a,x.id).build_id)

    def test_atomic_rollback_after_build_insert(self):
        x=self.create();self.app.supply_source(self.a,x.id,XML,'source')
        claim=self.repo.claim('w');result=FakeEngine().calculate(XML)
        result['invalid_json']=set()
        with self.assertRaises(TypeError):self.repo.complete(x.id,'w',claim.attempt,{'status':'ready'},xml=XML,result=result)
        self.assertEqual(PostgresPoe2Repository(self.connect).list_builds(self.a.user_id),[])
        self.assertIsNone(self.app.read(self.a,x.id).build_id)
        self.assertTrue(self.repo.complete(x.id,'w',claim.attempt,{'status':'ready'},xml=XML,result=FakeEngine().calculate(XML)))
        self.assertFalse(self.repo.complete(x.id,'w',claim.attempt,{'status':'ready'},xml=XML,result=FakeEngine().calculate(XML)))

    def test_mapper_input_gaps_persist_preview_and_snapshot(self):
        from types import SimpleNamespace
        from server.app.poe2.imports.domain import Issue,IssueSeverity
        x=self.create('wegame')
        mapped=SimpleNamespace(character=None,issues=(Issue('MISSING_JEWELS','jewels',IssueSeverity.BLOCKING,'Jewels missing'),),
            preview={'character':'Example','level':90,'shareCredential':'do-not-emit'},mapping_version='1',source_hash='a'*64,game_data_version='0.5')
        convert=Mock()
        ImportWorker(self.repo,FakeEngine(),collect=lambda ref, *, owner_id:{'role':{'level':90}},map=lambda snapshot:mapped,convert=convert).run_once()
        convert.assert_not_called()
        packet=self.app.read(self.a,x.id);self.assertEqual(packet.status.value,'needs_input')
        self.assertEqual(packet.preview['level'],90);self.assertNotIn('shareCredential',packet.preview)
        row=self.repo.read(self.a.user_id,x.id);self.assertEqual(row.snapshot['provenance']['mappingVersion'],'1')
        self.assertEqual(row.source_relation,'collected')
        self.app.supply_source(self.a,x.id,XML,'source');ImportWorker(self.repo,FakeEngine()).run_once()
        self.assertEqual(self.app.read(self.a,x.id).status.value,'ready')
        self.assertEqual(self.repo.read(self.a.user_id,x.id).source_relation,'user_supplied')
        with self.admin() as c:c.execute("UPDATE poe2.character_imports SET expires_at=now()-interval '1 second' WHERE id=%s",(x.id,))
        self.repo.expire()
        self.assertIsNotNone(self.repo.read(self.a.user_id,x.id).snapshot)
        self.assertEqual(self.app.read(self.a,x.id).status.value,'ready')

    def test_source_cannot_revive_expired_snapshot_before_cleanup(self):
        x=self.create('wegame')
        claim=self.repo.claim('w')
        self.assertTrue(self.repo.stage(x.id,'w',claim.attempt,'mapping',
            snapshot={'data':{'role':{'level':90}},'provenance':{'sourceHash':'a'*64}},
            preview={'level':90}))
        self.assertTrue(self.repo.complete(x.id,'w',claim.attempt,{'status':'needs_input','next_action':'supply_pob'}))
        with self.admin() as c:c.execute("UPDATE poe2.character_imports SET expires_at=now()-interval '1 second' WHERE id=%s",(x.id,))
        # No expire call: read only masks the expired value, and source must clear storage.
        self.assertIsNone(self.repo.read(self.a.user_id,x.id).snapshot)
        self.app.supply_source(self.a,x.id,XML,'new-source')
        row=self.repo.read(self.a.user_id,x.id)
        self.assertIsNone(row.snapshot)
        self.assertEqual(row.source_xml,XML)
        self.assertTrue(ImportWorker(self.repo,FakeEngine()).run_once())
        self.assertEqual(self.app.read(self.a,x.id).status.value,'ready')
        self.assertIsNone(self.repo.read(self.a.user_id,x.id).snapshot)

    def test_api_routes_scope_and_packets(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from server.app.api.routes.poe2 import router
        from server.app.api.dependencies import require_principal,require_mutating_principal,poe2_import_application
        from server.app.api.errors import ApiProblem,api_problem_handler
        api=FastAPI();api.include_router(router);api.add_exception_handler(ApiProblem,api_problem_handler)
        api.dependency_overrides[poe2_import_application]=lambda:self.app
        api.dependency_overrides[require_principal]=lambda:self.a
        api.dependency_overrides[require_mutating_principal]=lambda:self.a
        with TestClient(api) as client:
            r=client.post('/api/v2/poe2/imports',json={'provider':'ninja','url':NINJA,'idempotencyKey':'api'})
            self.assertEqual(r.status_code,202);data=r.json();id=data['id']
            self.assertEqual(data['nextAction'],'supply_pob');self.assertNotIn('source_xml',data)
            api.dependency_overrides[require_principal]=lambda:self.b
            api.dependency_overrides[require_mutating_principal]=lambda:self.b
            self.assertEqual(client.get('/api/v2/poe2/imports/'+id).status_code,404)
            for suffix,body in [('source',{'source':XML,'idempotencyKey':'s'}),('retry',{'idempotencyKey':'r'}),('cancel',{})]:
                self.assertEqual(client.post('/api/v2/poe2/imports/'+id+'/'+suffix,json=body).status_code,404)
            def rejected():raise ApiProblem(status_code=403,code='CSRF_REJECTED',message='CSRF_REJECTED')
            api.dependency_overrides[require_mutating_principal]=rejected
            self.assertEqual(client.post('/api/v2/poe2/imports/'+id+'/cancel').status_code,403)

    @unittest.skipUnless(os.environ.get('POE2_IMPORT_LIVE_XML'),'real engine opt in')
    def test_real_ninja_baseline(self):
        from pathlib import Path
        from server.app.poe2.engine import PobEngine
        x=self.create();self.app.supply_source(self.a,x.id,Path(os.environ['POE2_IMPORT_LIVE_XML']).read_text(),'real-source')
        self.assertTrue(ImportWorker(self.repo,PobEngine()).run_once())
        p=self.app.read(self.a,x.id);self.assertEqual(p.status.value,'ready',p.issues)
        job=PostgresPoe2Repository(self.connect).get_job(self.a.user_id,p.baseline_job_id)
        self.assertGreater(job.result['stats']['Life'],0)
        print('REAL_NINJA_BASELINE',{'status':p.status.value,'buildId':str(p.build_id),'baselineJobId':str(p.baseline_job_id),'engineVersion':job.result['engineVersion'],'stats':job.result['stats']})

    @unittest.skipUnless(os.environ.get('POE2_CHARACTER_LIVE') == '1', 'cloud native opt in')
    def test_synthetic_native_wegame_worker_ready(self):
        from server.app.poe2.engine import PobEngine
        from server.app.poe2.character_bridge import convert_character
        from server.app.poe2.imports.mapping import map
        from tests.app_poe2_mapping_test import synthetic_snapshot
        x=self.create('wegame');collector=Mock(return_value=synthetic_snapshot())
        worker=ImportWorker(self.repo,PobEngine(),collect=collector,map=map,convert=convert_character)
        self.assertTrue(worker.run_once())
        p=self.app.read(self.a,x.id);self.assertEqual(p.status.value,'ready',p.issues)
        self.assertEqual(collector.call_args.kwargs,{'owner_id':self.a.user_id})
        job=PostgresPoe2Repository(self.connect).get_job(self.a.user_id,p.baseline_job_id)
        self.assertGreater(job.result['stats']['TotalDPS'],0)
        self.assertEqual(job.result['sourceProvenance']['mappingVersion'],'zhCN-0_5-finite-1')
        self.assertFalse(worker.run_once())

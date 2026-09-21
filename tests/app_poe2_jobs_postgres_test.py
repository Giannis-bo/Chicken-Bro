import os
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from server.app.identity.domain import Principal
from server.app.poe2.application import Poe2Application, Poe2Error
from server.app.poe2.domain import Poe2Build
from server.app.poe2.repository import LeaseLost, PostgresPoe2Repository


class FakeEngine:
    def calculate(self, source, changes=None):
        import hashlib
        return {'stats':{'Life':100+(changes or {}).get('level',0)},'summary':{'className':'Test'},
            'inputSha256':hashlib.sha256(source.encode()).hexdigest(),'outputSha256':'b'*64,
            'exportCode':'export','engineVersion':'v0.23.1@test','changes':changes or {}}


@unittest.skipUnless(os.environ.get('POE2_TEST_DATABASE_URL'),'requires isolated POE2 PostgreSQL')
class Poe2PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        cls.psycopg=psycopg
        cls.url=os.environ['POE2_TEST_DATABASE_URL']
        def connect():
            connection=psycopg.connect(cls.url)
            if os.environ.get('POE2_TEST_ROLE') == 'wow_app':
                with connection.cursor() as cursor:cursor.execute('SET ROLE wow_app')
            return connection
        cls.connect=staticmethod(connect); cls.admin_connect=staticmethod(lambda:psycopg.connect(cls.url))
        cls.repo=PostgresPoe2Repository(connect); cls.app=Poe2Application(cls.repo,FakeEngine())

    def setUp(self):
        self.owner,self.other=uuid4(),uuid4()
        with self.admin_connect() as c:
            with c.cursor() as cur:
                for user in (self.owner,self.other):
                    cur.execute("INSERT INTO identity.users(id,created_at,updated_at) VALUES (%s,now(),now())",(user,))

    def tearDown(self):
        with self.admin_connect() as c:
            with c.cursor() as cur:cur.execute('DELETE FROM identity.users WHERE id IN (%s,%s)',(self.owner,self.other))

    def build(self):
        now=datetime.now(timezone.utc); xml='<PathOfBuilding2><Build/></PathOfBuilding2>'
        b=Poe2Build(uuid4(),self.owner,'test',xml,'0.3','Standard','a'*64,'v0.23.1@test','export',{},now)
        return self.repo.create_build(b)

    def test_owner_scope_idempotency_and_filtering(self):
        b=self.build(); owner=Principal(self.owner,'web_cookie'); other=Principal(self.other,'web_cookie')
        first=self.app.submit_job(owner,b.id,{'level':10},'same')
        replay=self.app.submit_job(owner,b.id,{'level':10},'same')
        self.assertEqual(first.id,replay.id)
        with self.assertRaises(Poe2Error) as conflict:self.app.submit_job(owner,b.id,{'level':11},'same')
        self.assertEqual(conflict.exception.code,'POE2_IDEMPOTENCY_CONFLICT')
        with self.assertRaises(Poe2Error):self.app.read_build(other,b.id)
        with self.assertRaises(Poe2Error):self.app.read_job(other,first.id)
        self.assertEqual([x.id for x in self.app.list_jobs(owner,b.id)],[first.id])

    def test_soft_delete_is_owner_scoped_and_hides_build_and_jobs(self):
        b=self.build(); owner=Principal(self.owner,'web_cookie'); other=Principal(self.other,'web_cookie')
        job=self.app.submit_job(owner,b.id,{},'delete-test')
        with self.assertRaises(Poe2Error):self.app.delete_build(other,b.id)
        self.assertIsNotNone(self.repo.get_build(self.owner,b.id))
        self.assertEqual(self.app.delete_build(owner,b.id),{'deleted':True})
        self.assertEqual(self.app.delete_build(owner,b.id),{'deleted':True})
        self.assertEqual(self.app.list_builds(owner),[])
        self.assertEqual(self.app.list_jobs(owner),[])
        with self.assertRaises(Poe2Error):self.app.read_build(owner,b.id)
        with self.assertRaises(Poe2Error):self.app.read_job(owner,job.id)
        with self.assertRaises(Poe2Error):self.app.submit_job(owner,b.id,{},'delete-test')
        with self.admin_connect() as c:
            row=c.execute('SELECT deleted_at,source_xml FROM poe2.builds WHERE id=%s',(b.id,)).fetchone()
        self.assertIsNotNone(row[0]); self.assertEqual(row[1],b.source_xml)

    def test_chat_reuses_imported_baseline_and_concurrent_candidates(self):
        from concurrent.futures import ThreadPoolExecutor
        owner=Principal(self.owner,'web_cookie')
        build=self.app.import_build(owner,'<PathOfBuilding2><Build/></PathOfBuilding2>')
        charged=[]
        baseline=self.app.baseline_job(owner,build.id)
        replay=self.app.submit_job(owner,build.id,{},'fresh-baseline',reuse=True,admit=lambda key, cursor: charged.append(key))
        self.assertEqual(replay.id,baseline.id); self.assertEqual(charged,[])
        def submit(i):return self.app.submit_job(owner,build.id,{'level':90},str(i),reuse=True,admit=lambda key, cursor: charged.append(key))
        with ThreadPoolExecutor(max_workers=2) as pool:jobs=list(pool.map(submit,range(2)))
        self.assertEqual(jobs[0].id,jobs[1].id); self.assertEqual(len(charged),1)
        with self.assertRaises(Poe2Error):self.app.submit_job(owner,build.id,{'level':91},jobs[0].idempotency_key,reuse=True)
        # Engine identity is part of reuse; an old completed result cannot satisfy a new engine.
        from unittest.mock import patch
        with patch.dict(os.environ,{'POE2_ENGINE_VERSION':'new-engine'}):
            self.assertIsNone(self.app.baseline_job(owner,build.id))
            fresh=self.app.submit_job(owner,build.id,{},'new-engine',reuse=True,admit=lambda key, cursor: charged.append(key))
            self.assertNotEqual(fresh.id,baseline.id)

    def test_admission_failure_does_not_create_job(self):
        build=self.build(); owner=Principal(self.owner,'web_cookie')
        def reject(key, cursor):raise RuntimeError('budget exhausted')
        with self.assertRaisesRegex(RuntimeError,'budget exhausted'):
            self.app.submit_job(owner,build.id,{'level':99},'blocked',reuse=True,admit=reject)
        self.assertEqual(self.app.list_jobs(owner,build.id),[])

    def test_import_persists_completed_baseline_with_owner_and_provenance(self):
        owner=Principal(self.owner,'web_cookie')
        build=self.app.import_build(owner,'<PathOfBuilding2><Build/></PathOfBuilding2>')
        jobs=self.app.list_jobs(owner,build.id)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0].status.value,'succeeded')
        self.assertEqual(jobs[0].changes,{})
        self.assertEqual(jobs[0].result['stats']['Life'],100)
        self.assertEqual(jobs[0].result['inputSha256'],build.input_sha256)
        self.assertEqual(jobs[0].result['engineVersion'],build.engine_version)
        self.assertIsNone(self.repo.get_job(self.other,jobs[0].id))
        # A baseline insert failure must not leave a build without its overview.
        another=replace(build,id=uuid4())
        duplicate=replace(jobs[0],build_id=another.id)
        with self.assertRaises(self.psycopg.errors.UniqueViolation):
            self.repo.create_build(another,baseline=duplicate)
        self.assertIsNone(self.repo.get_build(self.owner,another.id))

    def test_claim_is_single_owner_and_stale_completion_is_fenced(self):
        b=self.build(); owner=Principal(self.owner,'web_cookie')
        job=self.app.submit_job(owner,b.id,{},'lease')
        t=datetime.now(timezone.utc)
        claim=self.repo.claim_next('worker-a',t,1)
        self.assertEqual(claim.id,job.id)
        self.assertIsNone(self.repo.claim_next('worker-b',t,1))
        reclaimed=self.repo.claim_next('worker-b',t+timedelta(seconds=2),10)
        self.assertEqual(reclaimed.id,job.id)
        with self.assertRaises(LeaseLost):self.repo.complete(job.id,'worker-a',{'bad':True},t+timedelta(seconds=2))

    def test_third_expired_lease_is_reconciled_to_failed(self):
        b=self.build(); owner=Principal(self.owner,'web_cookie')
        job=self.app.submit_job(owner,b.id,{},'exhaust')
        t=datetime.now(timezone.utc)
        for attempt in range(3):
            claimed=self.repo.claim_next('worker-'+str(attempt),t+timedelta(seconds=attempt*2),1)
            self.assertEqual(claimed.attempt_count,attempt+1)
        self.assertIsNone(self.repo.claim_next('worker-final',t+timedelta(seconds=6),1))
        failed=self.app.read_job(owner,job.id)
        self.assertEqual(failed.status.value,'failed')
        self.assertEqual(failed.public_error_code,'POE2_ATTEMPTS_EXHAUSTED')


if __name__=='__main__':unittest.main()

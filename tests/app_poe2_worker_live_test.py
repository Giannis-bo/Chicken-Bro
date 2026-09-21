import os
import unittest
from pathlib import Path
from uuid import uuid4

from server.app.identity.domain import Principal
from server.app.poe2.application import Poe2Application
from server.app.poe2.engine import PobEngine
from server.app.poe2.repository import PostgresPoe2Repository
from server.app.poe2.worker import Poe2Worker


@unittest.skipUnless(os.environ.get('POE2_TEST_DATABASE_URL') and os.environ.get('POE2_LIVE_FIXTURE'),'requires cloud PoB and isolated PostgreSQL')
class Poe2LiveWorkerTest(unittest.TestCase):
    def test_import_queue_worker_and_persist_real_result(self):
        import psycopg
        def connect():
            connection=psycopg.connect(os.environ['POE2_TEST_DATABASE_URL'])
            if os.environ.get('POE2_TEST_ROLE') == 'wow_app':
                with connection.cursor() as cursor:cursor.execute('SET ROLE wow_app')
            return connection
        owner=uuid4(); principal=Principal(owner,'web_cookie')
        with connect() as c:
            with c.cursor() as cur:cur.execute('INSERT INTO identity.users(id,created_at,updated_at) VALUES (%s,now(),now())',(owner,))
        try:
            repo=PostgresPoe2Repository(connect); app=Poe2Application(repo,PobEngine())
            source=Path(os.environ['POE2_LIVE_FIXTURE']).read_text(encoding='utf-8')
            build=app.import_build(principal,source,title='cloud real fixture',game_version='0.3',league='Standard')
            job=app.submit_job(principal,build.id,{},'live-worker')
            self.assertTrue(Poe2Worker(repo,PobEngine(),'live-test').run_once())
            completed=app.read_job(principal,job.id)
            self.assertEqual(completed.status.value,'succeeded')
            self.assertEqual(completed.result['inputSha256'],build.input_sha256)
            self.assertGreater(completed.result['stats'].get('Life',0)+completed.result['stats'].get('EnergyShield',0),0)
            self.assertEqual(completed.result['engineVersion'],os.environ['POE2_ENGINE_VERSION'])
        finally:
            with psycopg.connect(os.environ['POE2_TEST_DATABASE_URL']) as c:
                with c.cursor() as cur:cur.execute('DELETE FROM identity.users WHERE id=%s',(owner,))

if __name__=='__main__':unittest.main()

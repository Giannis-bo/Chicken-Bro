"""Real PostgreSQL analytics contract. Use a dedicated empty database only."""
import importlib
import os
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from server.app.admin.application import date_window
from server.app.admin.repository import PostgresAnalyticsRepository
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS

@unittest.skipUnless(os.environ.get('WOW_ADMIN_TEST_DSN'), 'dedicated admin test database required')
class AdminPostgresTest(unittest.TestCase):
    def test_aggregation_timezone_population_distinct_feedback_provenance_and_empty(self):
        import psycopg
        from psycopg.types.json import Jsonb
        dsn=os.environ['WOW_ADMIN_TEST_DSN']
        self.assertIn('admin',dsn.rsplit('/',1)[-1], 'never run this fixture against production')
        connect=lambda: psycopg.connect(dsn)
        with psycopg.connect(dsn,autocommit=True) as conn:
            if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='wow_app'").fetchone(): conn.execute('CREATE ROLE wow_app')
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(conn,Path(__file__).resolve().parents[1]/'server/migrations/product')
        appid='admin-test-'+uuid4().hex
        a,b,legacy,wrong=[uuid4() for _ in range(4)]
        start=datetime(2026,9,8,16,tzinfo=timezone.utc)
        with connect() as conn:
            for owner,appid_value,joined in [(a,appid,start),(b,appid,start-timedelta(days=1)),(legacy,None,start),(wrong,'wrong-app',start)]:
                conn.execute('INSERT INTO identity.users(id) VALUES (%s)',(owner,))
                if appid_value:
                    conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,created_at) VALUES (%s,%s,'qq',%s,%s,%s)",(uuid4(),owner,appid_value,str(uuid4()),joined))
            test=next(iter(TEST_ACCOUNT_IDS.values()))
            conn.execute('INSERT INTO identity.users(id) VALUES (%s) ON CONFLICT DO NOTHING',(test,))
            conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,created_at) VALUES (%s,%s,'qq',%s,%s,%s)",(uuid4(),test,appid,str(uuid4()),start))
            def chat(owner,status,at,feedback=None,game='wow'):
                conv,msg,reply,run=[uuid4() for _ in range(4)]
                conn.execute("INSERT INTO chat.conversations(id,user_id,status,game) VALUES (%s,%s,'archived',%s)",(conv,owner,game))
                for mid,role in [(msg,'user'),(reply,'assistant')]:
                    conn.execute('INSERT INTO chat.messages(id,user_id,conversation_id,role,content) VALUES (%s,%s,%s,%s,%s)',(mid,owner,conv,role,'private text must not leak'))
                conn.execute('''INSERT INTO chat.agent_runs(id,user_id,conversation_id,user_message_id,assistant_message_id,status,runtime_revision,started_at,finished_at,resolved,feedback_updated_at,idempotency_key)
                 VALUES (%s,%s,%s,%s,%s,%s,'fixture',%s,%s,%s,%s,%s)''',(run,owner,conv,msg,reply if status=='succeeded' else None,status,at,at+timedelta(seconds=10) if status!='streaming' else None,feedback,at+timedelta(seconds=20) if feedback is not None else None,str(run)))
            synthetic=uuid4()
            conn.execute('INSERT INTO identity.users(id) VALUES (%s)',(synthetic,))
            conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,created_at) VALUES (%s,%s,'qq',%s,%s,%s)",(uuid4(),synthetic,appid,'poe2-release-smoke-'+uuid4().hex,start))
            for owner in [a,b,legacy,wrong,test,synthetic]: chat(owner,'succeeded',start,False if owner==b else True)
            chat(a,'failed',start+timedelta(hours=1))
            chat(a,'succeeded',start+timedelta(hours=2))
            chat(a,'succeeded',start-timedelta(microseconds=1))
            chat(a,'succeeded',start+timedelta(days=1))
            chat(a,'succeeded',start,True,game='poe2')
            def job(owner,status,result=False,valid=True):
                snap,jid=uuid4(),uuid4()
                conn.execute("""INSERT INTO simc.source_snapshots(id,user_id,provider,source_url,source_key,revision,readiness,snapshot_json,raw_sha256)
                 VALUES (%s,%s,'raiderio','https://raider.io/characters/us/test/example',%s,1,'READY_FOR_SIMC',%s,%s)""",(snap,owner,str(snap),Jsonb({'character':{'classKey':'shaman','specKey':'elemental'}}),'a'*64))
                conn.execute('''INSERT INTO simc.simulation_jobs(id,user_id,snapshot_id,scenario_hash,compiler_revision,runtime_revision,idempotency_key,status,created_at,updated_at)
                 VALUES (%s,%s,%s,%s,'compiler','runtime',%s,%s,%s,%s)''',(jid,owner,snap,'b'*64,str(jid),status,start,start+timedelta(seconds=60)))
                if result:
                    provenance={'snapshotId':str(snap),'profileSha256':'c'*64,'scenarioHash':'b'*64,'runtimeRevision':'runtime','compilerRevision':'compiler','sourceRawSha256':'a'*64} if valid else {}
                    conn.execute('''INSERT INTO simc.simulation_results(id,job_id,user_id,profile_sha256,primary_metric_name,primary_metric_value,compiler_revision,runtime_revision,provenance_json)
                     VALUES (%s,%s,%s,%s,'dps',123,'compiler','runtime',%s)''',(uuid4(),jid,owner,'c'*64,Jsonb(provenance)))
            job(a,'succeeded',True);job(a,'succeeded');job(a,'succeeded',True,False)
            job(b,'failed');job(b,'queued');job(legacy,'succeeded',True)
            def poe(owner,valid=True):
                bid,jid=uuid4(),uuid4()
                conn.execute("""INSERT INTO poe2.builds(id,user_id,title,source_xml,game_version,league,input_sha256,engine_version,export_code,summary_json,created_at)
                  VALUES (%s,%s,'fixture','private XML','fixture','fixture',%s,'engine','private export','{}',%s)""",(bid,owner,'a'*64,start))
                result={'stats':{'Life':100},'inputSha256':'a'*64,'engineVersion':'engine','exportCode':'private export'} if valid else {'stats':{'Life':'bad'}}
                conn.execute("""INSERT INTO poe2.jobs(id,user_id,build_id,idempotency_key,request_hash,changes_json,status,result_json,created_at,updated_at)
                  VALUES (%s,%s,%s,%s,%s,'{}','succeeded',%s,%s,%s)""",(jid,owner,bid,str(jid),'b'*64,Jsonb(result),start,start+timedelta(seconds=20)))
            poe(a);poe(a,False);poe(legacy);poe(test);poe(synthetic)
            # Build-only users remain in build metrics, but never enter dialogue user counts.
            build_only=uuid4()
            conn.execute('INSERT INTO identity.users(id) VALUES (%s)',(build_only,))
            conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,created_at) VALUES (%s,%s,'qq',%s,%s,%s)",(uuid4(),build_only,appid,str(uuid4()),start))
            conn.execute("""INSERT INTO poe2.builds(id,user_id,title,source_xml,game_version,league,input_sha256,engine_version,export_code,summary_json,created_at,deleted_at)
              VALUES (%s,%s,'fixture','private XML','fixture','fixture',%s,'engine','private export','{}',%s,%s)""",(uuid4(),build_only,'a'*64,start,start))
            poe_only,future_only,empty_only=[uuid4() for _ in range(3)]
            for owner in (poe_only,future_only,empty_only):
                conn.execute('INSERT INTO identity.users(id) VALUES (%s)',(owner,))
                conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject,created_at) VALUES (%s,%s,'qq',%s,%s,%s)",(uuid4(),owner,appid,str(uuid4()),start-timedelta(days=30)))
            # Old QQ signup, separate per-game first question, multiple runs deduped.
            chat(poe_only,'succeeded',start-timedelta(microseconds=1),game='poe2')
            chat(poe_only,'succeeded',start,game='poe2')
            chat(poe_only,'failed',start+timedelta(hours=1),game='poe2')
            chat(future_only,'succeeded',start+timedelta(days=1),game='wow')
            conn.execute("INSERT INTO chat.conversations(id,user_id,status,game) VALUES (%s,%s,'active','wow')",(uuid4(),empty_only))
        repo=PostgresAnalyticsRepository(connect)
        w=date_window('2026-09-09','2026-09-09',start+timedelta(hours=1))
        data=repo.overview(w,appid)
        self.assertEqual(data['users'],{'total':2,'new':1,'active':2})
        self.assertEqual(data['chat']['total'],4)
        self.assertEqual(data['chat']['successRate'],.75)
        self.assertEqual(data['chat']['feedbackRate'],2/3)
        self.assertEqual(data['chat']['resolutionRate'],.5)
        self.assertEqual(data['chat']['avgSeconds'],10)
        self.assertEqual(data['simc']['total'],5)
        self.assertEqual(data['simc']['succeeded'],1)
        self.assertEqual(data['simc']['invalidResults'],2)
        self.assertEqual(data['simc']['successRate'],.25)
        self.assertEqual(data['simc']['avgSeconds'],60)
        self.assertEqual(data['daily'],[{'date':'2026-09-09','newUsers':1,'activeUsers':2,'questions':4,'simulations':5,'builds':0}])
        self.assertEqual(data['specializations'],[{'class':'shaman','spec':'elemental','count':5}])
        self.assertNotIn('private text',str(data))
        poe_data=repo.overview(w,appid,'poe2')
        self.assertEqual(poe_data['game'],'poe2')
        self.assertNotIn('simc',poe_data)
        self.assertEqual(poe_data['chat']['total'],3)
        self.assertEqual(poe_data['users'],{'total':2,'new':1,'active':2})
        self.assertEqual(poe_data['builds'],3)
        self.assertEqual(poe_data['poe2']['total'],2)
        self.assertEqual(poe_data['poe2']['succeeded'],1)
        self.assertEqual(poe_data['poe2']['invalidResults'],1)
        self.assertEqual(poe_data['poe2']['successRate'],.5)
        self.assertEqual(poe_data['specializations'],[])
        self.assertEqual(poe_data['daily'][0]['questions'],3)
        self.assertEqual(poe_data['daily'][0]['newUsers'],1)
        self.assertEqual(poe_data['daily'][0]['activeUsers'],2)
        self.assertEqual(poe_data['daily'][0]['builds'],3)
        self.assertNotIn('private',str(poe_data))
        # The first-question boundary is Beijing midnight, independent of QQ signup.
        later=repo.overview(date_window('2026-09-10','2026-09-10',start+timedelta(days=2)),appid,'wow')
        self.assertEqual(later['users'],{'total':3,'new':1,'active':2})
        later_poe=repo.overview(date_window('2026-09-10','2026-09-10',start+timedelta(days=2)),appid,'poe2')
        self.assertEqual(later_poe['users'],{'total':2,'new':0,'active':0})
        empty=repo.overview(w,'empty-'+appid)
        self.assertEqual(empty['users']['total'],0)
        self.assertIsNone(empty['chat']['successRate'])
        self.assertIsNone(empty['simc']['avgSeconds'])
        self.assertEqual(empty['daily'][0]['activeUsers'],0)

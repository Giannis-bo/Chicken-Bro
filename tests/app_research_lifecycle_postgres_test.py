import importlib
import os
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

from server.app.chickenbro.repository import PostgresChatRepository
from server.app.chickenbro.source_gateway import ChickenbroSourceGateway
from tests.app_research_budget_test import Service


@unittest.skipUnless(os.environ.get('WOW_RESEARCH_TEST_DSN'), 'isolated research database required')
class ResearchPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.connect = lambda: psycopg.connect(os.environ['WOW_RESEARCH_TEST_DSN'])
        with self.connect() as conn:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                conn, Path(__file__).resolve().parents[1] / 'server/migrations/product')
        self.owner, self.conversation = uuid4(), uuid4()
        with self.connect() as conn:
            conn.execute('INSERT INTO identity.users(id) VALUES (%s)', (self.owner,))
        self.repo = PostgresChatRepository(self.connect)
        self.repo.create_conversation(self.owner, self.conversation, 'research', datetime.now(timezone.utc))

    def admit(self, content='继续'):
        _, run = self.repo.start_message_run(self.owner, self.conversation, content,
            str(uuid4()), str(uuid4()), datetime.now(timezone.utc), runtime_revision='research-test')
        with self.connect() as conn:
            conn.execute("UPDATE chat.agent_runs SET status='failed',public_error_code='TEST_FINISHED',finished_at=now() WHERE id=%s", (run.id,))
        return run.id

    def store(self, run_id, owner=None):
        from server.app.chickenbro.research_lifecycle import PostgresResearchBudget
        return PostgresResearchBudget(self.connect, owner or self.owner, run_id)

    def test_admission_binds_research_and_continuation(self):
        first, second = self.admit('研究前十'), self.admit('继续查后面的')
        with self.connect() as conn:
            rows = conn.execute('SELECT research_id FROM chat.research_runs WHERE run_id IN (%s,%s)', (first, second)).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], rows[1])

    def test_poe2_budget_survives_turns_and_source_work(self):
        first=self.store(self.admit())
        for i in range(12):self.assertIsNone(first.reserve_poe2(str(i)))
        self.assertEqual(first.reserve_poe2('next')['errorCode'],'POE2_RESEARCH_TURN_LIMIT')
        # Shared source counters must preserve the POE2 execution counter.
        first.reserve('raiderio_rankings','rankings',{'limit':1})
        self.assertEqual(first.poe2_status()['turnAttemptsUsed'],12)
        second=self.store(self.admit('继续比较'))
        self.assertEqual(second.research_id,first.research_id)
        self.assertEqual(second.poe2_status()['candidatesUsed'],12)
        self.assertEqual(second.poe2_status()['turnAttemptsUsed'],0)
        self.assertIsNone(second.reserve_poe2('next'))
        self.assertEqual(self.store(second.run_id).poe2_status()['candidatesUsed'],13)
        with self.assertRaises(PermissionError):self.store(second.run_id,owner=uuid4())
        ended=self.store(self.admit('/结束研究'))
        self.assertEqual(ended.reserve_poe2('new')['errorCode'],'RESEARCH_ENDED')

    def test_poe2_parallel_admission_cannot_exceed_turn_limit(self):
        run_id=self.admit()
        def reserve_one(i):return self.store(run_id).reserve_poe2(str(i))
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(reserve_one,range(16)))
        self.assertEqual(sum(x is None for x in results),12)
        self.assertEqual(self.store(run_id).poe2_status()['turnAttemptsUsed'],12)

    def test_poe2_gateway_reuses_baseline_and_remains_readable_at_limit(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from server.app.identity.domain import Principal
        from server.app.poe2.application import Poe2Application
        from server.app.poe2.repository import PostgresPoe2Repository
        from server.app.poe2.tools import Poe2ToolGateway
        from tests.app_poe2_jobs_postgres_test import FakeEngine
        principal=Principal(self.owner,'web_cookie')
        run_id=self.admit()
        @contextmanager
        def guarded():
            with self.connect() as conn:
                conn.execute("SET LOCAL lock_timeout='500ms'")
                # Reproduce the exclusive lock held by a worker's guarded connection.
                conn.execute('SELECT id FROM chat.agent_runs WHERE id=%s FOR UPDATE',(run_id,))
                yield conn
        app=Poe2Application(PostgresPoe2Repository(guarded),FakeEngine())
        build=app.import_build(principal,'<PathOfBuilding2><Build/></PathOfBuilding2>')
        from server.app.chickenbro.research_lifecycle import PostgresResearchBudget
        budget=PostgresResearchBudget(guarded,self.owner,run_id)
        gateway=Poe2ToolGateway(app,research_budget=budget)
        token=gateway.issue_capability(SimpleNamespace(game='poe2',principal=principal))
        baseline=gateway.execute(token,'get',{'buildId':str(build.id)})['baselineJobId']
        reused=gateway.execute(token,'calculate',{'buildId':str(build.id),'changes':{},'idempotencyKey':'baseline-again'})
        self.assertEqual(reused['id'],baseline); self.assertTrue(reused['reused'])
        self.assertEqual(reused['researchBudget']['attemptsUsed'],0)
        for i in range(12):
            result=gateway.execute(token,'calculate',{'buildId':str(build.id),'changes':{'level':i+1},'idempotencyKey':str(i)})
            self.assertFalse(result['reused'])
        blocked=gateway.execute(token,'calculate',{'buildId':str(build.id),'changes':{'level':99},'idempotencyKey':'extra'})
        self.assertEqual(blocked['errorCode'],'POE2_RESEARCH_TURN_LIMIT')
        again=gateway.execute(token,'calculate',{'buildId':str(build.id),'changes':{},'idempotencyKey':'still-reused'})
        self.assertEqual(again['id'],baseline)
        self.assertEqual(gateway.execute(token,'job_get',{'jobId':baseline})['status'],'succeeded')

    def test_capability_and_process_renewal_cannot_reset_budget(self):
        first = self.store(self.admit())
        gateway = ChickenbroSourceGateway(query_service=Service(), research_budget=first)
        gateway.query(gateway.issue_capability(), 'raiderio_rankings', 'rankings', {'limit': 10})
        service = Service()
        gateway = ChickenbroSourceGateway(query_service=service, research_budget=self.store(self.admit()))
        result = gateway.query(gateway.issue_capability(), 'raiderio', 'https://raider.io/characters/us/area-52/extra')
        self.assertEqual(result['errorCode'], 'RESEARCH_BUDGET_EXCEEDED')
        self.assertEqual(service.calls, [])

    def test_followup_reuses_legacy_rio_and_wcl_identity_in_persisted_research(self):
        from psycopg.types.json import Jsonb
        first = self.store(self.admit())
        state = {'players':['character:us:bleeding-hollow:shadarek'] + [
            f'character:us:illidan:p{n}' for n in range(9)],
            'report_actors':{'AAAAAAAAAAAAAAAA:10:472':'character:us:bleedinghollow:shadarek'}}
        with self.connect() as conn:
            conn.execute('UPDATE chat.research_sessions SET budget=%s WHERE id=%s',
                         (Jsonb({'source':state}), first.research_id))
        second = self.store(self.admit('继续看这个玩家的伤害构成'))
        self.assertEqual(second.research_id, first.research_id)
        url = 'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=10&source=472'
        self.assertIsNone(second.reserve('warcraftlogs', url, {'view':'overview'})[0])
        self.assertEqual(second.status()['scopeUsed']['players'], 10)
        third = self.store(self.admit('继续看技能事件'))
        self.assertIsNone(third.reserve('warcraftlogs', url, {'view':'events'})[0])
        self.assertEqual(third.reserve('warcraftlogs', url.replace('472','999'),
                                      {'view':'overview'})[0]['errorCode'], 'RESEARCH_BUDGET_EXCEEDED')

    def test_explicit_lifecycle_does_not_guess_from_keywords(self):
        first = self.store(self.admit('研究'))
        first.reserve('raiderio_rankings', 'rankings', {'limit': 10})
        for text in ['这句话包含新研究但不是命令', '/新研究是什么意思', '换个问题']:
            self.assertEqual(self.store(self.admit(text)).research_id, first.research_id)
        new = self.store(self.admit('/新研究\n另一个独立问题'))
        self.assertNotEqual(new.research_id, first.research_id)
        self.assertIsNone(new.reserve('raiderio_rankings', 'rankings', {'limit': 10})[0])
        ended = self.store(self.admit('/结束研究'))
        self.assertEqual(ended.reserve('raiderio', 'https://raider.io/characters/us/area-52/a', {})[0]['errorCode'], 'RESEARCH_ENDED')
        self.assertEqual(self.store(self.admit('继续')).reserve_simulation('key')['errorCode'], 'RESEARCH_ENDED')
        fresh = self.store(self.admit('/新研究\n新问题'))
        self.assertIsNone(fresh.reserve_simulation('key'))

    def test_concurrent_reservations_and_failures_are_not_refunded(self):
        run = self.admit()
        def reserve(n):
            return self.store(run).reserve('raiderio', f'https://raider.io/characters/us/area-52/p{n}', {})[0]
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(reserve, range(12)))
        self.assertEqual(results.count(None), 10)
        self.assertEqual(sum(r is not None for r in results), 2)

    def test_simulation_reservations_survive_turns_and_replay(self):
        first = self.store(self.admit())
        for n in range(4):
            self.assertIsNone(first.reserve_simulation(str(n)))
        second = self.store(self.admit())
        self.assertIsNone(second.reserve_simulation('0'))
        self.assertIsNone(second.reserve_simulation('4'))
        self.assertEqual(second.status()['simulations'], 5)

    def test_other_owner_cannot_load_research(self):
        run = self.admit()
        with self.assertRaises(PermissionError):
            self.store(run, uuid4())

    def test_simc_gateway_reuses_cross_turn_job_and_prepare_shares_players(self):
        from tests.app_chickenbro_simulation_tools_test import SimulationToolGatewayTest
        from server.app.chickenbro.simulation_tools import SimulationToolGateway, SimulationToolContext
        from server.app.identity.domain import Principal
        fixture = SimulationToolGatewayTest()
        fixture.setUp()
        self.owner = fixture.owner.user_id
        with self.connect() as conn:
            conn.execute('INSERT INTO identity.users(id) VALUES (%s) ON CONFLICT DO NOTHING', (self.owner,))
        self.conversation = uuid4()
        self.repo.create_conversation(self.owner, self.conversation, 'simc research', datetime.now(timezone.utc))
        first_run = self.admit()
        first = self.store(first_run)
        gateway = SimulationToolGateway(fixture.application, research_budget=first)
        token = gateway.issue_capability(SimulationToolContext(fixture.owner, self.conversation, first_run))
        snapshot = gateway.execute(token, 'prepare', {'sourceUrl': fixture.url})['snapshotId']
        arguments = {'snapshotId': snapshot, 'scenario': {}}
        original = gateway.execute(token, 'submit', arguments)
        second_run = self.admit()
        second = self.store(second_run)
        gateway = SimulationToolGateway(fixture.application, research_budget=second)
        token = gateway.issue_capability(SimulationToolContext(fixture.owner, self.conversation, second_run))
        self.assertEqual(gateway.execute(token, 'submit', arguments)['jobId'], original['jobId'])
        self.assertEqual(second.status()['simulations'], 1)
        self.assertEqual(second.status()['players'], 1)
        second.reserve('raiderio_rankings', 'rankings', {'limit': 9})
        self.assertEqual(gateway.execute(token, 'prepare', {'sourceUrl': fixture.url + 'new'})['errorCode'], 'RESEARCH_BUDGET_EXCEEDED')

    def test_idempotent_message_replay_does_not_open_another_research(self):
        from server.app.chickenbro.application import ChatApplication
        from server.app.identity.domain import Principal
        from tests.app_chickenbro_application_test import FakeCodex
        app = ChatApplication(repository=self.repo, codex=FakeCodex([{'type':'completed','text':'已开启新研究'}]))
        principal = Principal(user_id=self.owner, session_kind='web_cookie')
        args = {'client_message_id':'new-question','idempotency_key':'new-question'}
        for _ in range(2):
            list(app.start_delivery(principal,self.conversation,'/新研究\n独立新问题',**args))
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM chat.research_sessions WHERE user_id=%s', (self.owner,)).fetchone()[0], 1)

    def test_database_role_can_use_new_tables_without_ddl_permission(self):
        from contextlib import contextmanager
        run = self.admit()
        @contextmanager
        def restricted():
            with self.connect() as conn:
                conn.execute('SET LOCAL ROLE wow_app')
                yield conn
        from server.app.chickenbro.research_lifecycle import PostgresResearchBudget
        store = PostgresResearchBudget(restricted, self.owner, run)
        self.assertIsNone(store.reserve_simulation('one'))

    def test_adapter_passes_trusted_context_and_disables_native_search_only_when_ended(self):
        import tempfile
        from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
        from server.app.identity.domain import Principal
        from tests.app_chickenbro_codex_adapter_test import FakeProcess, answer
        for content, expected in [('问题', 'live'), ('/结束研究', 'disabled'), ('/新研究\n另一个问题', 'live')]:
            run = self.admit(content)
            gateway = ChickenbroSourceGateway(query_service=Service(),
                research_budget_factory=lambda context: self.store(context.run_id, context.principal.user_id))
            process = FakeProcess(answer())
            with tempfile.TemporaryDirectory() as directory:
                adapter = NativeCodexChatAdapter(enabled=True, jobs_dir=directory,
                    source_gateway=gateway, popen=lambda *a, **kw: process)
                list(adapter.stream_for_chat(principal=Principal(self.owner, 'web_cookie'),
                    conversation_id=self.conversation, run_id=run, prompt=content, timeout_seconds=30))
            start = next(e for e in process.sent() if e.get('method') == 'thread/start')
            self.assertEqual(start['params']['config']['web_search'], expected)

    def test_new_turn_preserves_scope_but_can_finish_known_player_after_48_calls(self):
        first=self.store(self.admit())
        url='https://raider.io/characters/us/realm/player'
        for _ in range(48):self.assertIsNone(first.reserve('raiderio',url,{})[0])
        same=self.store(first.run_id)
        self.assertEqual(same.reserve('raiderio',url,{})[0]['errorCode'],'RESEARCH_TURN_BUDGET_EXCEEDED')
        second=self.store(self.admit('补查同一个角色'))
        self.assertEqual(second.research_id,first.research_id)
        self.assertIsNone(second.reserve('raiderio',url,{})[0])
        self.assertEqual(second.status()['sourceCalls'],49)
        self.assertEqual(second.status()['turnSourceCalls'],1)

    def test_evidence_and_successful_overview_reuse_stay_in_owner_conversation(self):
        from server.app.chickenbro.worker_gateway import ToolRecorder
        old=self.admit();body={'provider':'warcraftlogs','target':'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=7','options':{'view':'overview'}}
        result={'status':'verified','sourceKey':'warcraftlogs','facts':[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':'1','sourceId':'7','view':'overview','fight':{'kill':True},'players':[{'id':7,'name':'Player','combatantInfo':{'stats':{'Crit':{'min':622,'max':622}}}}]}]}
        with self.connect() as conn:conn.execute("INSERT INTO chat.executions(run_id,user_id,stage) VALUES (%s,%s,'succeeded')",(old,self.owner))
        ToolRecorder(self.connect,old).execute('source.warcraftlogs',body,lambda:result)
        new=self.admit()
        with self.connect() as conn:conn.execute("INSERT INTO chat.executions(run_id,user_id,stage) VALUES (%s,%s,'succeeded')",(new,self.owner))
        reused=ToolRecorder(self.connect,new).execute('source.warcraftlogs',body,lambda:self.fail('cache hit reached upstream'))
        self.assertEqual(reused['reuse']['runId'],str(old))
        alternate={**body,'target':body['target'].replace('www.','cn.').replace('?fight=','#fight=')+'&type=healing'}
        reused_variant=ToolRecorder(self.connect,new).execute('source.warcraftlogs',alternate,lambda:self.fail('equivalent URL reached upstream'))
        self.assertEqual(reused_variant['reuse']['runId'],str(old))
        evidence=self.repo.research_evidence(self.owner,self.conversation)
        self.assertEqual(evidence['facts'][0]['players'][0]['combatantInfo']['stats']['Crit']['min'],622)
        self.assertEqual(self.repo.research_evidence(uuid4(),self.conversation)['facts'],[])
        self.admit('/新研究\n一个独立新日志问题')
        self.assertEqual(self.repo.research_evidence(self.owner,self.conversation)['facts'],[])
        fresh=self.store(self.admit('继续新日志'))
        self.assertIsNone(fresh.reserve('warcraftlogs',body['target'].replace('fight=1','fight=4'),{'view':'overview'})[0])

    def test_generic_windows_load_separately_with_request_filters_and_owner_isolation(self):
        from server.app.chickenbro.worker_gateway import ToolRecorder
        run=self.admit()
        with self.connect() as conn:conn.execute("INSERT INTO chat.executions(run_id,user_id,stage) VALUES (%s,%s,'succeeded')",(run,self.owner))
        for i,view in enumerate(('healing','healing','statistics')):
            window={} if i==0 else {'startTime':1000,'endTime':2000}
            options={'view':view,**window}
            if view=='statistics':options['dataType']='Resources'
            fact={'reportCode':'AAAAAAAAAAAAAAAA','fightId':1,'sourceId':7,'view':view}
            fact[view]={'window':window,'totals':{'effective':100}} if view=='healing' else {**window,'dataType':'Resources','complete':False,'metricsComplete':True,'resources':[{'type':0,'waste':4}]}
            result={'status':'verified' if view=='healing' else 'partial','sourceKey':'warcraftlogs','facts':[fact]}
            ToolRecorder(self.connect,run).execute('source.warcraftlogs',{'provider':'warcraftlogs','target':'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=7','options':options},lambda:result)
        self.admit()
        evidence=self.repo.research_evidence(self.owner,self.conversation)
        self.assertEqual(len(evidence['facts']),3)
        statistics=next(f for f in evidence['facts'] if f['view']=='statistics')
        self.assertEqual(statistics['status'],'partial')
        self.assertEqual(statistics['historicalScope']['filters']['dataType'],'Resources')
        self.assertEqual(self.repo.research_evidence(uuid4(),self.conversation)['facts'],[])
        self.admit('/新研究\n独立问题')
        self.assertEqual(self.repo.research_evidence(self.owner,self.conversation)['facts'],[])

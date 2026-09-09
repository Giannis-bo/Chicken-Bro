import importlib
import os
from pathlib import Path
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from server.app.chickenbro.application import ChatApplication, ChatApplicationError
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.domain import Principal
from tests.app_chickenbro_application_test import FakeCodex


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL required')
class DurableChatPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.connect = lambda: psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'], autocommit=True) as conn:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(
                conn, Path(__file__).resolve().parents[1] / 'server/migrations/product')
        self.owner = uuid4()
        with self.connect() as conn:
            conn.execute('INSERT INTO identity.users(id) VALUES (%s)', (self.owner,))
        self.principal = Principal(user_id=self.owner, session_kind='mini_bearer')
        self.repository = PostgresChatRepository(self.connect, durable=True)
        self.codex = FakeCodex([{'type': 'delta', 'text': '唯一回答'}, {'type': 'completed'}])
        self.app = ChatApplication(repository=self.repository, codex=self.codex)
        self.conversation = self.app.create_conversation(self.principal, idempotency_key='durable-create')

    def tearDown(self):
        with self.connect() as conn:
            conn.execute("UPDATE chat.executions SET stage='failed',lease_token=NULL,lease_expires_at=NULL WHERE user_id=%s AND stage IN ('pending','running')", (self.owner,))
            conn.execute("UPDATE chat.agent_runs SET status='failed',finished_at=now(),public_error_code='CODEX_EXECUTION_FAILED' WHERE user_id=%s AND status='streaming'", (self.owner,))

    def admit(self):
        stream = self.app.start_delivery(self.principal, self.conversation.id, '问题',
            client_message_id='durable-client', idempotency_key='durable-message')
        first = next(stream)
        stream.close()
        return UUID(first.run_id)

    def test_admission_is_durable_without_executing_model_in_api(self):
        run_id = self.admit()
        self.assertEqual(self.codex.calls, 0)
        with self.connect() as conn:
            row = conn.execute('SELECT stage FROM chat.executions WHERE run_id=%s', (run_id,)).fetchone()
        self.assertEqual(row, ('pending',))
        # Recreating the API and closing its subscription cannot cancel the job.
        self.app = ChatApplication(repository=PostgresChatRepository(self.connect, durable=True), codex=self.codex)
        with self.assertRaises(ChatApplicationError) as caught:
            self.app.start_delivery(self.principal, self.conversation.id, '另一问题',
                client_message_id='another-client', idempotency_key='another-message')
        self.assertEqual(caught.exception.code, 'CHAT_ACCOUNT_BUSY')

    def test_worker_completes_once_and_web_history_replays_same_answer(self):
        from server.app.chickenbro.worker import ChatWorker
        run_id = self.admit()
        worker = ChatWorker(self.connect, self.codex)
        self.assertTrue(worker.run_once())
        self.assertFalse(worker.run_once())
        web = Principal(user_id=self.owner, session_kind='web_cookie')
        reply = self.app.load_conversation(web, self.conversation.id)['messages'][-1]
        self.assertEqual(reply['content'], '唯一回答')
        self.assertEqual(reply['reply_status'], 'completed')
        self.assertEqual(self.codex.calls, 1)
        events = list(self.app.start_delivery(web, self.conversation.id, '问题',
            client_message_id='durable-client', idempotency_key='durable-message'))
        self.assertEqual(events[-1].text, '唯一回答')
        self.assertEqual(self.codex.calls, 1)
        other = Principal(user_id=uuid4(), session_kind='web_cookie')
        with self.assertRaises(ChatApplicationError):
            self.app.load_conversation(other, self.conversation.id)
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT stage FROM chat.executions WHERE run_id=%s', (run_id,)).fetchone(), ('succeeded',))

    def test_expired_execution_fails_without_replaying_model_and_rejects_old_writer(self):
        from server.app.chickenbro.durable import PostgresChatExecutions, ChatLeaseLost
        from server.app.chickenbro.worker import ChatWorker
        run_id = self.admit()
        executions = PostgresChatExecutions(self.connect)
        claim = executions.claim(lease_seconds=30)
        self.assertEqual(claim['run_id'], run_id)
        with self.connect() as conn:
            conn.execute("UPDATE chat.executions SET lease_expires_at=now()-interval '1 second' WHERE run_id=%s", (run_id,))
        ChatWorker(self.connect, self.codex).run_once()
        self.assertEqual(self.codex.calls, 0)
        with self.assertRaises(ChatLeaseLost):
            with executions.guarded_connection(run_id, claim['lease_token'])() as conn:
                conn.execute("UPDATE chat.agent_runs SET public_progress='late' WHERE id=%s", (run_id,))
        run = self.repository.get_run_by_idempotency(self.owner, 'durable-message')
        self.assertEqual(run.status.value, 'failed')
        self.assertEqual(run.public_error_code, 'CODEX_EXECUTION_FAILED')
        history = self.app.load_conversation(self.principal, self.conversation.id)['messages']
        self.assertEqual(history[-1]['reply_status'], 'failed')
        self.assertEqual(history[-1]['content'], '')

    def test_message_and_execution_rollback_together(self):
        # A failed queue insert cannot leave a user message or busy account behind.
        from unittest.mock import patch
        with patch('server.app.chickenbro.durable.enqueue_execution', side_effect=RuntimeError('storage unavailable')):
            with self.assertRaises(ChatApplicationError):
                self.admit()
        self.assertEqual(self.repository.list_messages(self.owner, self.conversation.id), [])

    def test_tool_result_is_recorded_and_expired_lease_cannot_invoke_tool(self):
        from server.app.chickenbro.durable import PostgresChatExecutions, ChatLeaseLost
        from server.app.chickenbro.worker_gateway import ToolRecorder
        run_id = self.admit()
        execution = PostgresChatExecutions(self.connect)
        claim = execution.claim()
        recorder = ToolRecorder(execution.guarded_connection(run_id, claim['lease_token']), run_id)
        calls = []
        def operation():
            calls.append(1)
            return {'status': 'ready', 'jobId': 'durable-side-effect-id'}
        result = recorder.execute('simc.submit', {'scenario': 'test'}, operation)
        self.assertEqual(result['jobId'], 'durable-side-effect-id')
        with self.connect() as conn:
            row = conn.execute('SELECT state,result_json FROM chat.tool_results WHERE run_id=%s', (run_id,)).fetchone()
            self.assertEqual(row, ('completed', {'status': 'ready', 'jobId': 'durable-side-effect-id'}))
            conn.execute("UPDATE chat.executions SET lease_expires_at=now()-interval '1 second' WHERE run_id=%s", (run_id,))
        with self.assertRaises(ChatLeaseLost):
            recorder.execute('simc.submit', {'scenario': 'test'}, operation)
        self.assertEqual(len(calls), 1)

    def test_pre_migration_completed_history_still_replays(self):
        legacy = ChatApplication(repository=PostgresChatRepository(self.connect),codex=self.codex)
        list(legacy.stream_message(self.principal,self.conversation.id,'旧问题',
            client_message_id='legacy-client',idempotency_key='legacy-message'))
        result = list(self.app.start_delivery(self.principal,self.conversation.id,'旧问题',
            client_message_id='legacy-client',idempotency_key='legacy-message'))
        self.assertEqual(result[-1].text,'唯一回答')
        self.assertEqual(self.codex.calls,1)

    def test_committed_answer_is_not_failed_if_worker_dies_before_acknowledgment(self):
        from server.app.chickenbro.durable import PostgresChatExecutions
        run_id = self.admit()
        execution = PostgresChatExecutions(self.connect)
        claim = execution.claim()
        repo = PostgresChatRepository(execution.guarded_connection(run_id,claim['lease_token']))
        repo.complete_run_with_assistant(self.owner,self.conversation.id,run_id,'已保存',datetime.now(timezone.utc))
        with self.connect() as conn:
            conn.execute("UPDATE chat.executions SET lease_expires_at=now()-interval '1 second' WHERE run_id=%s",(run_id,))
        execution.recover()
        reply = self.app.load_conversation(self.principal,self.conversation.id)['messages'][-1]
        self.assertEqual(reply['content'],'已保存')
        self.assertEqual(reply['reply_status'],'completed')
        with self.connect() as conn:
            self.assertEqual(conn.execute('SELECT stage FROM chat.executions WHERE run_id=%s',(run_id,)).fetchone(),('succeeded',))

    def test_lock_wait_cannot_authorize_a_write_after_lease_expiry(self):
        from threading import Thread, Event
        from server.app.chickenbro.durable import PostgresChatExecutions, ChatLeaseLost
        run_id = self.admit()
        execution = PostgresChatExecutions(self.connect)
        claim = execution.claim(lease_seconds=1)
        entered = Event()
        results = []
        def old_writer():
            entered.set()
            try:
                with execution.guarded_connection(run_id,claim['lease_token'])() as conn:
                    conn.execute("UPDATE chat.agent_runs SET public_progress='late write' WHERE id=%s",(run_id,))
                results.append('wrote')
            except ChatLeaseLost:
                results.append('lost')
        with self.connect() as holder:
            holder.execute('SELECT run_id FROM chat.executions WHERE run_id=%s FOR UPDATE',(run_id,))
            thread = Thread(target=old_writer)
            thread.start()
            self.assertTrue(entered.wait(1))
            holder.execute('SELECT pg_sleep(1.2)')
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results,['lost'])

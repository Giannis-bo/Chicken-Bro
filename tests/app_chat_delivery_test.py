import unittest
from threading import Event, BoundedSemaphore
from server.app.chickenbro.delivery import BackgroundDelivery, DeliveryCapacity

class DeliveryTest(unittest.TestCase):
    def test_durable_failed_terminal_uses_the_same_retryability_contract_as_direct_delivery(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from server.app.chickenbro.durable import DurableSubscription
        from server.app.chickenbro.stream import ChatEvent
        now = datetime.now(timezone.utc)
        for code, retryable in [('CODEX_REQUEST_REJECTED', False), ('CODEX_OUTPUT_INVALID', False),
                                ('UNKNOWN', False), ('CODEX_TIMEOUT', True),
                                ('CODEX_UNAVAILABLE', True), ('CODEX_EXECUTION_FAILED', True)]:
            with self.subTest(code=code):
                row = dict(status='failed', progress='', draft='', error=code,
                           started=now, finished=now, answer=None)
                executions = SimpleNamespace(recover=lambda owner: None, snapshot=lambda owner, run: row)
                first = ChatEvent('started', 'request', 'conversation', 1, run_id='run')
                events = list(DurableSubscription(first, executions, 'owner'))
                self.assertEqual(len(events), 2)
                self.assertEqual(events[-1].public_payload()['type'], 'failed')
                self.assertEqual(events[-1].public_payload()['errorCode'], code)
                self.assertEqual(events[-1].public_payload()['retryable'], retryable)
                self.assertNotIn('text', events[-1].public_payload())

    def test_disconnect_does_not_cancel_producer(self):
        release, done = Event(), Event()
        def producer():
            yield 'started'
            release.wait(2)
            done.set()
            yield 'completed'
        stream=BackgroundDelivery(producer(), capacity=BoundedSemaphore(1))
        self.assertEqual(next(stream),'started')
        stream.close(); release.set()
        self.assertTrue(done.wait(2))
        self.assertTrue(stream.finished.wait(2))

    def test_slow_subscriber_does_not_block_producer(self):
        stream=BackgroundDelivery(iter(range(100)), capacity=BoundedSemaphore(1), buffer_limit=2)
        self.assertTrue(stream.finished.wait(2))
        self.assertEqual(list(stream),[0])

    def test_capacity_rejects_before_consuming_input(self):
        capacity=BoundedSemaphore(1);capacity.acquire(); called=[]
        def source():
            called.append(True);yield 1
        with self.assertRaises(DeliveryCapacity): BackgroundDelivery(source(),capacity=capacity)
        self.assertEqual(called,[])

    def test_validation_failure_releases_capacity(self):
        capacity=BoundedSemaphore(1)
        def source():
            raise ValueError('validation');yield
        with self.assertRaises(ValueError): BackgroundDelivery(source(),capacity=capacity)
        self.assertTrue(capacity.acquire(False))

    def test_application_disconnect_persists_and_keeps_account_idempotency(self):
        from tests.app_chickenbro_application_test import ChatApplicationTest, FakeCodex
        from server.app.chickenbro.application import ChatApplication, ChatApplicationError
        from server.app.chickenbro.domain import AgentRunStatus
        fixture=ChatApplicationTest();fixture.setUp()
        release=Event()
        class SlowCodex(FakeCodex):
            def stream(self, **kwargs):
                self.calls += 1
                release.wait(2)
                yield {'type':'completed','text':'保存的完整回答'}
        codex=SlowCodex();app=ChatApplication(repository=fixture.repository,codex=codex,clock=lambda:fixture.now)
        delivery=app.start_delivery(fixture.principal,fixture.conversation_id,'问题',client_message_id='first',idempotency_key='first-request-key')
        self.assertEqual(next(delivery).event_type,'started');delivery.close()
        with self.assertRaises(ChatApplicationError):
            app.start_delivery(fixture.principal,fixture.conversation_id,'问题',client_message_id='first',idempotency_key='first-request-key')
        release.set();self.assertTrue(delivery.finished.wait(2))
        run=next(iter(fixture.repository.runs.values()))
        self.assertEqual(run['status'],AgentRunStatus.SUCCEEDED)
        self.assertIsNotNone(run['assistant_message_id'])
        replay=list(app.start_delivery(fixture.principal,fixture.conversation_id,'问题',client_message_id='first',idempotency_key='first-request-key'))
        self.assertEqual(replay[-1].event_type,'completed')
        self.assertEqual(codex.calls,1)

    def test_http_disconnect_keeps_generation_and_history(self):
        import asyncio
        from server.app.api.routes.chat import stream_message, ChatMessageBody
        from server.app.chickenbro.application import ChatApplication
        from server.app.chickenbro.domain import AgentRunStatus
        from tests.app_chickenbro_application_test import ChatApplicationTest, FakeCodex

        fixture = ChatApplicationTest()
        fixture.setUp()
        release, done = Event(), Event()

        class SlowCodex(FakeCodex):
            def stream(self, **kwargs):
                if not release.wait(3):
                    raise TimeoutError()
                yield {'type': 'completed', 'text': '断线后完整回答'}

        app = ChatApplication(repository=fixture.repository, codex=SlowCodex(), clock=lambda: fixture.now)
        response = stream_message(
            fixture.conversation_id, ChatMessageBody(content='问题'),
            include_progress=True, idempotency_key='http-disconnect-key',
            principal=fixture.principal, application=app,
        )

        async def exercise():
            first_frame = asyncio.Event()
            disconnected = asyncio.Event()

            async def send(message):
                if message['type'] == 'http.response.body' and b'event: started' in message.get('body', b''):
                    first_frame.set()

            async def receive():
                await first_frame.wait()
                disconnected.set()
                return {'type': 'http.disconnect'}

            task = asyncio.create_task(response({'type': 'http', 'asgi': {'spec_version': '2.0'}}, receive, send))
            try:
                await asyncio.wait_for(disconnected.wait(), 2)
                run = next(iter(fixture.repository.runs.values()))
                self.assertEqual(run['status'], AgentRunStatus.STREAMING)
            finally:
                release.set()
            await asyncio.wait_for(task, 3)

        # Observe persistence rather than relying on the cancelled response iterator.
        original = fixture.repository.complete_run_with_assistant
        def complete(*args, **kwargs):
            result = original(*args, **kwargs)
            done.set()
            return result
        fixture.repository.complete_run_with_assistant = complete
        asyncio.run(exercise())
        self.assertTrue(done.wait(3))
        view = app.load_conversation(fixture.principal, fixture.conversation_id)
        self.assertEqual(view['messages'][-1]['content'], '断线后完整回答')

    def test_disconnect_preserves_real_failure(self):
        from server.app.chickenbro.application import ChatApplication
        from server.app.chickenbro.domain import AgentRunStatus
        from tests.app_chickenbro_application_test import ChatApplicationTest, FakeCodex

        fixture = ChatApplicationTest()
        fixture.setUp()
        release = Event()
        class TimeoutCodex(FakeCodex):
            def stream(self, **kwargs):
                release.wait(2)
                raise TimeoutError()
                yield
        app = ChatApplication(repository=fixture.repository, codex=TimeoutCodex(), clock=lambda: fixture.now)
        delivery = app.start_delivery(fixture.principal, fixture.conversation_id, '问题',
                                     client_message_id=None, idempotency_key='timeout-detach-key')
        next(delivery)
        delivery.close()
        release.set()
        self.assertTrue(delivery.finished.wait(3))
        run = next(iter(fixture.repository.runs.values()))
        self.assertEqual(run['status'], AgentRunStatus.FAILED)
        self.assertEqual(run['public_error_code'], 'CODEX_TIMEOUT')

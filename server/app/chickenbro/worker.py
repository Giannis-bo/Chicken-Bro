"""Execute durable Chat admissions outside the API process."""
import logging
import os
from threading import Event, Thread

from server.app.chickenbro.application import ChatApplication
from server.app.chickenbro.durable import PostgresChatExecutions, ChatLeaseLost
from server.app.chickenbro.repository import PostgresChatRepository
from server.app.identity.domain import Principal

LOG = logging.getLogger(__name__)


class ChatWorker:
    def __init__(self, connection_factory, codex=None, *, codex_factory=None, lease_seconds=30):
        self.executions = PostgresChatExecutions(connection_factory)
        self.codex = codex
        self.codex_factory = codex_factory
        self.lease_seconds = lease_seconds

    def run_once(self):
        self.executions.recover()
        claim = self.executions.claim(lease_seconds=self.lease_seconds)
        if claim is None:
            return False
        run_id, token = claim['run_id'], claim['lease_token']
        connect = self.executions.guarded_connection(run_id, token)
        stop = Event()

        def heartbeat():
            while not stop.wait(self.lease_seconds / 3):
                try:
                    self.executions.heartbeat(run_id, token, lease_seconds=self.lease_seconds)
                except Exception:
                    LOG.warning('chat_lease_lost run_id=%s', run_id)
                    return

        pulse = Thread(target=heartbeat, daemon=True, name='chat-lease')
        pulse.start()
        try:
            repository = PostgresChatRepository(connect)
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""SELECT id,user_id,conversation_id,user_message_id,
                        assistant_message_id,status,runtime_revision,public_error_code,
                        started_at,finished_at,idempotency_key FROM chat.agent_runs
                        WHERE id=%s AND user_id=%s""", (run_id,claim['user_id']))
                    run = repository._agent_run_from_row(cur.fetchone())
            principal = Principal(user_id=claim['user_id'], session_kind='mini_bearer')
            codex = self.codex_factory(claim, connect) if self.codex_factory else self.codex
            application = ChatApplication(repository=repository, codex=codex)
            for event in application.execute_run(principal, run):
                if event.event_type == 'delta':
                    self.executions.append_draft(run_id,token,event.text)
            self.executions.finish(run_id,token)
        except ChatLeaseLost:
            LOG.warning('chat_execution_fenced run_id=%s', run_id)
        except Exception as error:
            LOG.error('chat_worker_failed run_id=%s exception_type=%s',run_id,type(error).__name__)
            try:
                with connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE chat.agent_runs SET status='failed',finished_at=now(),
                            public_error_code='CODEX_EXECUTION_FAILED' WHERE id=%s AND status='streaming'""", (run_id,))
                self.executions.finish(run_id,token)
            except Exception:
                # A fresh worker/sweeper resolves expiry; no uncertain replay.
                LOG.warning('chat_terminal_deferred_to_lease_recovery run_id=%s',run_id)
        finally:
            stop.set()
            pulse.join()
        return True


def start_chat_workers(settings, connection_factory, stop):
    """Composition root for the Chat lane of the existing independent worker."""
    from server.app.chickenbro.worker_gateway import WorkerToolServer, ToolRecorder
    from server.app.chickenbro.source_gateway import ChickenbroSourceGateway, ServerConfiguredSourceQuery
    from server.app.chickenbro.wcl_source import WclRunReader
    from server.app.chickenbro.simulation_tools import SimulationToolGateway
    from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
    from server.app.simulation.application import SimulationApplication
    from server.app.simulation.repository import PostgresSimulationRepository
    from server.app.simulation.sources import CharacterSourceRouter, HttpxSourceGateway
    from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
    from server.app.simulation.compiler import SimcProfileCompiler

    port = int(os.environ.get('WOW_CHAT_WORKER_TOOL_PORT','8794'))
    if port not in (8794,18794):
        raise ValueError('Chat worker tool port must be an allowlisted loopback port')
    host = WorkerToolServer(port)
    host.start()
    capabilities = SimcRuntimeCapabilities.from_env()
    def factory(claim, connect):
        recorder = ToolRecorder(connect,claim['run_id'])
        simulation = SimulationApplication(repository=PostgresSimulationRepository(connect),
            source_router=CharacterSourceRouter(HttpxSourceGateway()),
            readiness_validator=SimcReadinessValidator(),
            compiler=SimcProfileCompiler(capabilities=capabilities),runtime_capabilities=capabilities)
        return NativeCodexChatAdapter(
            source_gateway=host.register(ChickenbroSourceGateway(
                query_service=ServerConfiguredSourceQuery(wcl_reader=WclRunReader())),recorder,'source'),
            simulation_gateway=host.register(SimulationToolGateway(simulation),recorder,'simc'),
            source_gateway_url=f'http://127.0.0.1:{port}/api/v2/internal/chickenbro/source-query',
            simulation_gateway_url=f'http://127.0.0.1:{port}/api/v2/internal/chickenbro/simc-tool')

    def lane():
        worker = ChatWorker(connection_factory,codex_factory=factory)
        while not stop.is_set():
            try:
                if worker.run_once():
                    continue
            except Exception as error:
                LOG.error('chat_lane_error exception_type=%s',type(error).__name__)
            stop.wait(1)

    threads = [Thread(target=lane,daemon=True,name=f'chat-worker-{i}') for i in range(8)]
    for thread in threads:
        thread.start()
    return host,threads

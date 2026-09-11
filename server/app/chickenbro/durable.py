"""Chat-owned durable execution state. A lost model process is never replayed."""
from contextlib import contextmanager
from threading import Event
from time import monotonic
from uuid import uuid4

from server.app.chickenbro.stream import ChatEvent


class ChatLeaseLost(RuntimeError):
    pass


class ChatQueueFull(RuntimeError):
    pass


def enqueue_execution(cursor, run_id, user_id):
    cursor.execute('SELECT pg_advisory_xact_lock(719620260909)')
    cursor.execute("SELECT count(*) FROM chat.executions WHERE stage IN ('pending','running')")
    if cursor.fetchone()[0] >= 32:
        raise ChatQueueFull('bounded Chat admission capacity exhausted')
    cursor.execute('INSERT INTO chat.executions(run_id,user_id) VALUES (%s,%s)', (run_id, user_id))


class PostgresChatExecutions:
    def __init__(self, connection_factory):
        self.connect = connection_factory

    def claim(self, *, lease_seconds=30):
        token = uuid4()
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""WITH candidate AS (
                    SELECT run_id FROM chat.executions WHERE stage='pending'
                    ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
                    UPDATE chat.executions e SET stage='running', lease_token=%s,
                        lease_expires_at=now()+make_interval(secs=>%s), heartbeat_at=now(),
                        execution_started_at=now(), updated_at=now()
                    FROM candidate c WHERE e.run_id=c.run_id
                    RETURNING e.run_id,e.user_id,e.lease_token""", (token, lease_seconds))
                row = cur.fetchone()
                if row is None:
                    return None
                return dict(zip(('run_id', 'user_id', 'lease_token'), row))

    def recover(self, user_id=None):
        # Lock execution before run, matching guarded writes. Only expired
        # executions are failed; pending admissions survive API/worker restart.
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT run_id FROM chat.executions
                    WHERE ((stage='running' AND lease_expires_at<=now())
                       OR (stage='pending' AND created_at<now()-interval '540 seconds'))
                    AND (%s::uuid IS NULL OR user_id=%s)
                    FOR UPDATE SKIP LOCKED""",(user_id,user_id))
                rows = cur.fetchall()
                for (run_id,) in rows:
                    cur.execute("""UPDATE chat.agent_runs SET status='failed',
                        public_error_code='CODEX_EXECUTION_FAILED',finished_at=now()
                        WHERE id=%s AND status='streaming'""", (run_id,))
                    # If answer committed before worker died, retain success.
                    cur.execute("""UPDATE chat.executions e SET stage=r.status,
                        interruption_reason=CASE WHEN r.status='failed' THEN 'worker_interrupted' ELSE '' END,
                        lease_token=NULL,lease_expires_at=NULL,updated_at=now()
                        FROM chat.agent_runs r WHERE e.run_id=%s AND r.id=e.run_id""", (run_id,))
                return len(rows)

    def heartbeat(self, run_id, token, *, lease_seconds=30):
        with self.guarded_connection(run_id, token)() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE chat.executions SET heartbeat_at=now(),
                    lease_expires_at=clock_timestamp()+make_interval(secs=>%s),updated_at=now()
                    WHERE run_id=%s""", (lease_seconds, run_id))

    def guarded_connection(self, run_id, token):
        @contextmanager
        def guarded():
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""SELECT run_id FROM chat.executions WHERE run_id=%s
                        AND stage='running' AND lease_token=%s
                        FOR UPDATE""", (run_id, token))
                    if cur.fetchone() is None:
                        raise ChatLeaseLost('chat execution lease is no longer current')
                    # now() is the transaction start, before a possible lock
                    # wait. Recheck wall time in a fresh statement after locking.
                    cur.execute('SELECT lease_expires_at>clock_timestamp() FROM chat.executions WHERE run_id=%s',(run_id,))
                    if cur.fetchone()[0] is not True:
                        raise ChatLeaseLost('chat execution lease expired while waiting for its lock')
                yield conn
        return guarded

    def append_draft(self, run_id, token, text):
        with self.guarded_connection(run_id, token)() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE chat.executions SET draft_answer=draft_answer || %s WHERE run_id=%s', (text, run_id))

    def finish(self, run_id, token):
        with self.guarded_connection(run_id, token)() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE chat.executions e SET stage=r.status,
                    lease_token=NULL,lease_expires_at=NULL,updated_at=now()
                    FROM chat.agent_runs r WHERE e.run_id=%s AND r.id=e.run_id
                    AND r.status IN ('succeeded','failed')""", (run_id,))
                if cur.rowcount != 1:
                    raise RuntimeError('execution did not persist a terminal run')

    def snapshot(self, user_id, run_id):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT r.status,r.public_progress,e.draft_answer,r.public_error_code,
                    r.started_at,r.finished_at,m.content FROM chat.agent_runs r
                    JOIN chat.executions e ON e.run_id=r.id AND e.user_id=r.user_id
                    LEFT JOIN chat.messages m ON m.id=r.assistant_message_id AND m.user_id=r.user_id
                    WHERE r.id=%s AND r.user_id=%s""", (run_id, user_id))
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError('owner-scoped execution unavailable')
                return dict(zip(('status','progress','draft','error','started','finished','answer'), row))

    def contains(self, user_id, run_id):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM chat.executions WHERE user_id=%s AND run_id=%s',(user_id,run_id))
                return cur.fetchone() is not None


class DurableSubscription:
    """Poll cumulative bounded public text. Closing never mutates execution."""
    def __init__(self, first, executions, user_id):
        self.first = first
        self.executions = executions
        self.user_id = user_id
        self.closed = Event()
        self.finished = Event()
        self.source = self._events()

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.source)

    def close(self):
        self.closed.set()

    def _events(self):
        yield self.first
        progress = draft = 0
        sequence = 1
        checked = 0
        while not self.closed.is_set():
            if monotonic()-checked >= 5:
                self.executions.recover(self.user_id)
                checked = monotonic()
            row = self.executions.snapshot(self.user_id, self.first.run_id)
            for key, offset in (('progress', progress), ('draft', draft)):
                text = row[key] or ''
                for start in range(offset, len(text), 8000):
                    sequence += 1
                    yield ChatEvent('progress' if key=='progress' else 'delta',
                        self.first.request_id,self.first.conversation_id,sequence,
                        run_id=self.first.run_id,text=text[start:start+8000])
            progress, draft = len(row['progress']), len(row['draft'])
            if row['status'] in ('succeeded','failed'):
                sequence += 1
                self.finished.set()
                yield ChatEvent('completed' if row['status']=='succeeded' else 'failed',
                    self.first.request_id,self.first.conversation_id,sequence,
                    run_id=self.first.run_id,text=row['answer'] or '',
                    error_code=row['error'] or '',
                    retryable=row['status']=='failed' and row['error'] in {
                        'CODEX_UNAVAILABLE', 'CODEX_TIMEOUT', 'CODEX_EXECUTION_FAILED'},
                    completed_at=row['finished'].isoformat(),
                    duration_ms=max(0,int((row['finished']-row['started']).total_seconds()*1000)))
                return
            self.closed.wait(0.2)

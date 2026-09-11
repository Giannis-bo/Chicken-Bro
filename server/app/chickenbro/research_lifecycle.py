"""Owner-scoped research epochs, bound at message admission, never by the model.

The caller's guarded connection additionally fences worker leases. Every quota
reservation commits before upstream work; failures intentionally retain slots.
"""
import json
from contextlib import contextmanager
from time import monotonic
from uuid import uuid4

from server.app.chickenbro.research_budget import ResearchBudget, blocked


def bind_research(cursor, user_id, conversation_id, run_id, content):
    # start_message_run already owns the active conversation FOR UPDATE lock.
    cursor.execute('SELECT research_id FROM chat.research_runs WHERE run_id=%s AND user_id=%s', (run_id, user_id))
    if cursor.fetchone():
        return
    cursor.execute('''SELECT id,state FROM chat.research_sessions
        WHERE user_id=%s AND conversation_id=%s ORDER BY ordinal DESC LIMIT 1 FOR UPDATE''',
        (user_id, conversation_id))
    previous = cursor.fetchone()
    command = content.strip().split('\n', 1)[0].strip()
    if previous and command == '/新研究':
        cursor.execute("UPDATE chat.research_sessions SET state='ended',ended_at=COALESCE(ended_at,now()) WHERE id=%s", (previous[0],))
    if previous is None or command == '/新研究':
        research_id = uuid4()
        cursor.execute('''INSERT INTO chat.research_sessions(id,user_id,conversation_id,state)
            VALUES (%s,%s,%s,'active')''', (research_id,user_id,conversation_id))
    else:
        research_id = previous[0]
    if command == '/结束研究':
        cursor.execute("UPDATE chat.research_sessions SET state='ended',ended_at=COALESCE(ended_at,now()) WHERE id=%s", (research_id,))
    cursor.execute('''INSERT INTO chat.research_runs(run_id,research_id,user_id,conversation_id)
        VALUES (%s,%s,%s,%s)''', (run_id,research_id,user_id,conversation_id))


class PostgresResearchBudget:
    def __init__(self, connect, user_id, run_id):
        self.connect, self.user_id, self.run_id = connect, user_id, run_id
        self.started = monotonic()  # 360s remains a per-generation admission fuse.
        with self._locked() as (_, research_id, _, _):
            self.research_id = research_id

    @contextmanager
    def _locked(self):
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT s.id,s.state,s.budget FROM chat.research_sessions s
                    JOIN chat.research_runs b ON b.research_id=s.id AND b.user_id=s.user_id
                        AND b.conversation_id=s.conversation_id
                    JOIN chat.agent_runs r ON r.id=b.run_id AND r.user_id=b.user_id
                        AND r.conversation_id=b.conversation_id
                    WHERE b.user_id=%s AND b.run_id=%s FOR UPDATE OF s''', (self.user_id,self.run_id))
                row = cur.fetchone()
                if row is None:
                    raise PermissionError('research unavailable')
                yield cur, row[0], row[1], row[2]

    def _save(self, cur, research_id, data):
        cur.execute('UPDATE chat.research_sessions SET budget=%s::jsonb WHERE id=%s AND user_id=%s',
            (json.dumps(data), research_id, self.user_id))

    @staticmethod
    def _ended():
        return {'status':'blocked','errorCode':'RESEARCH_ENDED','facts':[], 'evidence':[],
            'limitations':['本研究已结束，不能新增查询或模拟。可以继续讨论已有结论。'],
            'nextActions':['独立的新问题请在消息第一行输入 /新研究，下一行写新问题；不要拆分原研究绕过预算。']}

    def status(self):
        with self._locked() as (_, _, state, data):
            source = data.get('source', {})
            return {'state': state, 'sourceCalls': source.get('calls', 0),
                    'players': len(source.get('players', [])),
                    'simulations': len(data.get('submissions', []))}

    def reserve(self, provider, target, options):
        with self._locked() as (cur, identity, state, data):
            if state != 'active':
                return self._ended(), None
            budget = ResearchBudget.restore(data.get('source', {}))
            budget.started = self.started
            error, receipt = budget.reserve(provider,target,options)
            if not error:
                data['source'] = budget.dump()
                self._save(cur,identity,data)
            return error, receipt

    def observe(self, receipt, result):
        with self._locked() as (cur, identity, _, data):
            budget = ResearchBudget.restore(data.get('source', {}))
            budget.observe(receipt,result)
            data['source'] = budget.dump()
            self._save(cur,identity,data)

    def reserve_simulation(self, key):
        with self._locked() as (cur, identity, state, data):
            if state != 'active':
                return self._ended()
            submissions = data.setdefault('submissions', [])
            if key in submissions:
                return None
            if len(submissions) >= 4:
                return blocked('simulations (maximum 4 per research)')
            submissions.append(key)
            self._save(cur,identity,data)
            return None

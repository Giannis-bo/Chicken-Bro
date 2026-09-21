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
    def _locked(self, cursor=None):
        if cursor is None:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    with self._locked(cur) as row:
                        yield row
            return
        cursor.execute('''SELECT s.id,s.state,s.budget FROM chat.research_sessions s
                    JOIN chat.research_runs b ON b.research_id=s.id AND b.user_id=s.user_id
                        AND b.conversation_id=s.conversation_id
                    JOIN chat.agent_runs r ON r.id=b.run_id AND r.user_id=b.user_id
                        AND r.conversation_id=b.conversation_id
                    WHERE b.user_id=%s AND b.run_id=%s FOR UPDATE OF s''', (self.user_id,self.run_id))
        row = cursor.fetchone()
        if row is None:
            raise PermissionError('research unavailable')
        yield cursor, row[0], row[1], row[2]

    def _save(self, cur, research_id, data):
        cur.execute('UPDATE chat.research_sessions SET budget=%s::jsonb WHERE id=%s AND user_id=%s',
            (json.dumps(data), research_id, self.user_id))

    @staticmethod
    def _ended():
        return {'status':'blocked','errorCode':'RESEARCH_ENDED','facts':[], 'evidence':[],
            'limitations':['本研究已结束，不能新增查询或模拟。可以继续讨论已有结论。'],
            'nextActions':['独立的新问题请在消息第一行输入 /新研究，下一行写新问题；不要拆分原研究绕过预算。']}

    def status(self):
        with self._locked() as (cur, _, state, data):
            cur.execute('SELECT work FROM chat.research_runs WHERE run_id=%s AND user_id=%s', (self.run_id,self.user_id))
            work = cur.fetchone()[0]
            source = data.get('source', {})
            used = {key:len(source.get(key, [])) for key in ('players','fights','groups')}
            used['simulations'] = len(data.get('submissions', []))
            limits = {'players':10,'fights':3,'groups':3,'simulations':None}
            return {'state': state, 'scopeUsed':used, 'scopeLimits':limits,
                    'scopeRemaining':{key:(None if limit is None else max(0,limit-used[key])) for key,limit in limits.items()},
                    'executionRemaining':{'sourceCalls':max(0,48-work.get('calls',0)), 'eventUnits':max(0,20000-work.get('events',0))},
                    'sourceCalls': source.get('calls', 0),
                    'turnSourceCalls':work.get('calls',0), 'turnEventUnits':work.get('events',0),
                    'executionLimits':{'sourceCallsPerTurn':48,'eventUnitsPerTurn':20000},
                    'players': len(source.get('players', [])),
                    'simulations': len(data.get('submissions', []))}

    def reserve(self, provider, target, options):
        with self._locked() as (cur, identity, state, data):
            if state != 'active':
                return self._ended(), None
            budget = ResearchBudget.restore(data.get('source', {}))
            budget.started = self.started
            cumulative_calls, cumulative_events = budget.calls, budget.events
            cur.execute('SELECT work FROM chat.research_runs WHERE run_id=%s AND user_id=%s', (self.run_id,self.user_id))
            work = cur.fetchone()[0]
            before_calls, before_events = work.get('calls',0), work.get('events',0)
            budget.calls, budget.events = before_calls, before_events
            error, receipt = budget.reserve(provider,target,options)
            if error and any(d in ' '.join(error.get('limitations',[])) for d in ('source calls','events (','time budget')):
                error = {'status':'blocked','errorCode':'RESEARCH_TURN_BUDGET_EXCEEDED','facts':[],
                    'limitations':['This response reached its execution limit. This does not exhaust the research scope or invalidate existing evidence.'],
                    'nextActions':['Stop new work in this response, answer from retained evidence and identify the remaining finite gap. A user follow-up may continue within the same player/fight scope; do not automatically split bulk research.']}
            if not error:
                cur.execute('UPDATE chat.research_runs SET work=%s::jsonb WHERE run_id=%s AND user_id=%s',
                    (json.dumps({**work,'calls':budget.calls,'events':budget.events}),self.run_id,self.user_id))
                budget.calls = cumulative_calls + budget.calls - before_calls
                budget.events = cumulative_events + budget.events - before_events
                data['source'] = budget.dump()
                self._save(cur,identity,data)
            return error, receipt

    def reserve_scope(self, provider, target, options):
        with self._locked() as (cur, identity, state, data):
            budget = ResearchBudget.restore(data.get('source', {}))
            error = budget.reserve_scope(provider, target, options, ended=state != 'active')
            if not error:
                data['source'] = budget.dump()
                self._save(cur, identity, data)
            return error

    def observe(self, receipt, result):
        with self._locked() as (cur, identity, _, data):
            budget = ResearchBudget.restore(data.get('source', {}))
            budget.observe(receipt,result)
            data['source'] = budget.dump()
            self._save(cur,identity,data)

    def record_usage(self, usage):
        from server.app.chickenbro.codex_stdio import clean_token_usage
        safe={phase:clean_token_usage({'total':value}) for phase,value in usage.items() if phase in ('primary','repair')}
        with self.connect() as conn:
            conn.execute('UPDATE chat.agent_runs SET model_usage=model_usage || %s::jsonb WHERE id=%s AND user_id=%s',
                         (json.dumps(safe),self.run_id,self.user_id))

    def reserve_simulation(self, key):
        with self._locked() as (cur, identity, state, data):
            if state != 'active':
                return self._ended()
            submissions = data.setdefault('submissions', [])
            if key in submissions:
                return None
            submissions.append(key)
            self._save(cur,identity,data)
            return None

    def poe2_status(self):
        from server.app.poe2.research import status
        with self._locked() as (cur, _, state, data):
            cur.execute('SELECT work FROM chat.research_runs WHERE run_id=%s AND user_id=%s', (self.run_id,self.user_id))
            return dict(status(data.get('poe2', {}), cur.fetchone()[0]), state=state)

    def reserve_poe2(self, key, cursor=None):
        from server.app.poe2.research import reserve
        with self._locked(cursor) as (cur, identity, state, data):
            if state != 'active':
                return self._ended()
            cur.execute('SELECT work FROM chat.research_runs WHERE run_id=%s AND user_id=%s', (self.run_id,self.user_id))
            work = cur.fetchone()[0]
            error = reserve(data.setdefault('poe2', {}), work, key)
            if not error:
                self._save(cur, identity, data)
                cur.execute('UPDATE chat.research_runs SET work=%s::jsonb WHERE run_id=%s AND user_id=%s',
                            (json.dumps(work), self.run_id, self.user_id))
            return error

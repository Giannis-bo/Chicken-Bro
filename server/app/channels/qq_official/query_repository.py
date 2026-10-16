"""Official-only fixed query admission, leased claims and owner-scoped results."""
from dataclasses import asdict
from uuid import uuid4
from psycopg.types.json import Jsonb
from .repository import OfficialRepository
from .query_commands import HELP, GuidanceInput, QueryInputError, parse_query
from .guidance import GuidanceRequest, fallback_packet


class QueryRepository(OfficialRepository):
    @staticmethod
    def _reply(cur, inbox_id, kind, text):
        from .query_commands import markdown_parts
        if kind == 'ack': return
        for index, part in enumerate(markdown_parts(str(text or '').strip() or '暂无数据')):
            cur.execute('''INSERT INTO qq_channel.outbox(id,inbox_id,kind,part,content)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(inbox_id,kind,part) DO NOTHING''',
                (uuid4(),inbox_id,kind,index,part))

    def accept(self, event):
        if event.bot != self.bot: raise ValueError('unexpected bot identity')
        if event.group not in self.allowed_groups: return False
        with self.connect() as c:
            cur = c.cursor()
            cur.execute('SELECT pg_advisory_xact_lock(719620260923)')
            if cur.execute('SELECT 1 FROM qq_channel.official_group_revocations WHERE bot_id=%s AND group_id=%s',
                           (event.bot,event.group)).fetchone(): return False
            if cur.execute('SELECT 1 FROM qq_channel.inbox WHERE bot_id=%s AND group_id=%s AND message_id=%s',
                           (event.bot,event.group,event.message_id)).fetchone(): return False
            identity = cur.execute('''SELECT p.user_id,p.enabled AND u.status='active'
                FROM qq_channel.principals p JOIN identity.users u ON u.id=p.user_id
                WHERE bot_id=%s AND group_id=%s AND sender_id=%s''',(event.bot,event.group,event.sender)).fetchone()
            if identity is None:
                uid = uuid4()
                cur.execute('INSERT INTO identity.users(id,display_name) VALUES(%s,%s)',(uid,'QQ 群友'))
                cur.execute('INSERT INTO qq_channel.principals(user_id,bot_id,group_id,sender_id) VALUES(%s,%s,%s,%s)',
                            (uid,event.bot,event.group,event.sender))
                identity = (uid,True)
            uid,enabled = identity
            if not enabled: return False
            count = cur.execute("SELECT count(*) FROM qq_channel.inbox WHERE user_id=%s AND received_at>now()-interval '1 minute'",(uid,)).fetchone()[0]
            if count >= 12: return False
            request = None; response = event.error
            if not response:
                if event.text == '/帮助': response = HELP
                elif event.text == '/状态': response = self._status(cur,uid)
                else:
                    try: request = parse_query(event.text)
                    except GuidanceInput: request = GuidanceRequest(event.text)
                    except QueryInputError as error: response = str(error)
            if request:
                count = cur.execute("SELECT count(*) FROM qq_channel.inbox WHERE bot_id=%s AND state IN ('pending','running')",(self.bot,)).fetchone()[0]
                busy = cur.execute("SELECT 1 FROM qq_channel.inbox WHERE user_id=%s AND state IN ('pending','running') LIMIT 1",(uid,)).fetchone()
                if count >= 10 or busy:
                    response = '已有查询等待或正在处理，请稍后再试；/状态 可查看自己的结果。'
                    request = None
            iid = uuid4()
            cur.execute('''INSERT INTO qq_channel.inbox
                (id,bot_id,group_id,sender_id,message_id,user_id,game,generation,content,state)
                VALUES(%s,%s,%s,%s,%s,%s,'wow',0,%s,%s)''',
                (iid,event.bot,event.group,event.sender,event.message_id,uid,event.text,'pending' if request else 'done'))
            if request:
                cur.execute('INSERT INTO qq_channel.official_queries(inbox_id,request) VALUES(%s,%s)',(iid,Jsonb(asdict(request))))
            else: self._reply(cur,iid,'command',response)
            return True

    @staticmethod
    def _status(cur, uid):
        row = cur.execute('''SELECT i.state,q.result_text FROM qq_channel.official_queries q
            JOIN qq_channel.inbox i ON i.id=q.inbox_id WHERE i.user_id=%s AND q.request->>'kind'!='guidance'
            ORDER BY i.received_at DESC,i.id DESC LIMIT 1''',(uid,)).fetchone()
        if not row: return '你还没有查询记录。发送 /帮助 查看用法。'
        if row[1]: return row[1]
        return '你的查询正在等待处理。' if row[0] == 'pending' else '正在读取角色数据，请稍后使用 /状态 查看结果。'

    def claim_query(self):
        with self.connect() as c:
            cur = c.cursor()
            # Disable/revoke is effective for both pending jobs and running leases.
            cur.execute('''UPDATE qq_channel.inbox i SET state='failed'
                FROM qq_channel.principals p,identity.users u WHERE i.user_id=p.user_id AND u.id=i.user_id
                AND i.bot_id=%s AND i.state IN ('pending','running')
                AND (NOT i.group_id=ANY(%s) OR NOT p.enabled OR u.status!='active')''',(self.bot,list(self.allowed_groups)))
            expired = cur.execute('''SELECT i.id,q.attempts,q.request->>'kind' FROM qq_channel.inbox i
                JOIN qq_channel.official_queries q ON q.inbox_id=i.id
                WHERE i.bot_id=%s AND i.state='running' AND q.lease_expires_at<=now()
                FOR UPDATE OF i,q SKIP LOCKED''',(self.bot,)).fetchall()
            for iid, attempts, kind in expired:
                if kind == 'guidance':
                    packet = fallback_packet('lease_expired')
                    cur.execute('''UPDATE qq_channel.official_queries SET result_text=%s,result_packet=%s,
                        completed_at=now(),lease_token=NULL,lease_expires_at=NULL WHERE inbox_id=%s''',
                        (packet['text'],Jsonb(packet),iid))
                    cur.execute("UPDATE qq_channel.inbox SET state='done' WHERE id=%s",(iid,))
                    self._reply(cur,iid,'answer',packet['text'])
                    continue
                cur.execute('UPDATE qq_channel.official_queries SET lease_token=NULL,lease_expires_at=NULL WHERE inbox_id=%s',(iid,))
                cur.execute('UPDATE qq_channel.inbox SET state=%s WHERE id=%s',('pending' if attempts < 2 else 'failed',iid))
                if attempts >= 2:
                    text = '角色查询超时，请稍后重新发送查询命令。'
                    cur.execute('UPDATE qq_channel.official_queries SET result_text=%s,completed_at=now() WHERE inbox_id=%s',(text,iid))
                    self._reply(cur,iid,'answer',text)
            row = cur.execute('''SELECT i.id,i.user_id,q.request FROM qq_channel.inbox i
                JOIN qq_channel.official_queries q ON q.inbox_id=i.id
                JOIN qq_channel.official_messages m ON m.inbox_id=i.id
                JOIN qq_channel.principals p ON p.user_id=i.user_id JOIN identity.users u ON u.id=i.user_id
                WHERE i.bot_id=%s AND i.group_id=ANY(%s) AND p.enabled AND u.status='active'
                AND i.state='pending' AND q.attempts<2
                ORDER BY i.received_at,i.id LIMIT 1 FOR UPDATE OF i,q SKIP LOCKED''',(self.bot,list(self.allowed_groups))).fetchone()
            if not row: return None
            token = uuid4()
            cur.execute("UPDATE qq_channel.inbox SET state='running' WHERE id=%s",(row[0],))
            cur.execute("UPDATE qq_channel.official_queries SET attempts=attempts+1,lease_token=%s,lease_expires_at=now()+interval '150 seconds' WHERE inbox_id=%s",(token,row[0]))
            context=None
            if row[2].get('kind') in ('battle_good','battle_review') and not row[2].get('url'):
                previous=cur.execute('''SELECT q.result_packet,q.completed_at FROM qq_channel.official_queries q
                    JOIN qq_channel.inbox i ON i.id=q.inbox_id
                    JOIN qq_channel.inbox current ON current.id=%s
                    WHERE i.user_id=current.user_id AND i.bot_id=current.bot_id
                    AND i.group_id=current.group_id AND i.state='done'
                    AND q.request->>'kind'='battle_summary'
                    AND q.result_packet->>'schema'='qq-battle-v1'
                    AND q.result_packet->>'status'='ready'
                    ORDER BY q.completed_at DESC,i.id DESC LIMIT 1''',(row[0],)).fetchone()
                if previous:
                    context=previous[0]
                    recovered=cur.execute('''SELECT q.result_packet FROM qq_channel.official_queries q
                        JOIN qq_channel.inbox i ON i.id=q.inbox_id
                        JOIN qq_channel.inbox current ON current.id=%s
                        WHERE i.user_id=current.user_id AND i.bot_id=current.bot_id
                        AND i.group_id=current.group_id AND i.state='done'
                        AND q.completed_at>=%s AND q.request->>'kind' IN ('battle_good','battle_review')
                        AND q.result_packet->>'schema'='qq-battle-v1'
                        AND q.result_packet->>'status'='ready'
                        AND q.result_packet->>'reportCode'=%s AND q.result_packet->>'fightId'=%s
                        AND q.result_packet->'narrative'->>'status'='ready'
                        ORDER BY q.completed_at DESC,i.id DESC LIMIT 1''',
                        (row[0],previous[1],context.get('reportCode'),str(context.get('fightId')))).fetchone()
                    if recovered:context=recovered[0]
            return {'id':row[0],'user_id':row[1],'request':row[2],'lease_token':token,'battle_context':context}

    def finish_query(self, job, text, *, failed=False, packet=None):
        with self.connect() as c:
            cur = c.cursor()
            row = cur.execute('''SELECT i.id FROM qq_channel.inbox i
                JOIN qq_channel.official_queries q ON q.inbox_id=i.id
                JOIN qq_channel.principals p ON p.user_id=i.user_id JOIN identity.users u ON u.id=i.user_id
                WHERE i.id=%s AND i.bot_id=%s AND i.user_id=%s AND i.group_id=ANY(%s)
                AND p.enabled AND u.status='active' AND i.state='running'
                AND q.lease_token=%s AND q.lease_expires_at>now() FOR UPDATE OF i,q''',
                (job['id'],self.bot,job['user_id'],list(self.allowed_groups),job['lease_token'])).fetchone()
            if not row: return False
            cur.execute('''UPDATE qq_channel.official_queries SET result_text=%s,result_packet=%s,completed_at=now(),
                lease_token=NULL,lease_expires_at=NULL WHERE inbox_id=%s''',
                (text,Jsonb(packet) if packet is not None and not failed else None,job['id']))
            cur.execute('UPDATE qq_channel.inbox SET state=%s WHERE id=%s',('failed' if failed else 'done',job['id']))
            self._reply(cur,job['id'],'answer',text)
            return True

"""Durable social replies, independently leased from owner-scoped research."""
from dataclasses import asdict
import json
from uuid import uuid4
from server.app.channels.qq.companion_domain import GroupEvent,ReplyDraft
from server.app.channels.qq.policy import split_reply

class CompanionRepository:
    def __init__(self,connect,bot,groups):self.connect,self.bot,self.groups=connect,bot,tuple(groups)

    def ensure_response(self,event,*,kind,context_seq=0):
        if event.bot!=self.bot or event.group not in self.groups:raise ValueError('unexpected group identity')
        if kind not in ('mention','proactive'):raise ValueError('invalid response kind')
        with self.connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,719620260924))',(self.bot,))
            row=c.execute('''INSERT INTO qq_channel.companion_responses
                (id,bot_id,group_id,sender_id,message_id,event_json,kind,context_seq)
                VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s) ON CONFLICT(bot_id,group_id,message_id)
                DO NOTHING RETURNING id''',(uuid4(),event.bot,event.group,event.sender,event.message_id,
                    json.dumps(asdict(event)),kind,context_seq)).fetchone()
            if row:
                n=c.execute("SELECT count(*) FROM qq_channel.companion_responses WHERE bot_id=%s AND state IN ('pending','running')",(self.bot,)).fetchone()[0]
                if n>32:
                    if kind=='mention':self._emit(c,row[0],event,ReplyDraft('鸡哥这会儿有点接不过来了，等一下再聊这句哈。'),'failed')
                    else:c.execute("UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state='silent',finished_at=now() WHERE id=%s",(row[0],))
                return row[0]
            return c.execute('SELECT id FROM qq_channel.companion_responses WHERE bot_id=%s AND group_id=%s AND message_id=%s',
                (event.bot,event.group,event.message_id)).fetchone()[0]

    def claim_response(self,*,lease_seconds=90,proactive_enabled=True):
        token=uuid4()
        with self.connect() as c:
            c.execute('''UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state='silent',
                finished_at=now(),lease_token=NULL,lease_expires_at=NULL
                WHERE bot_id=%s AND kind='proactive' AND state IN ('pending','running')
                AND (NOT %s OR to_timestamp((event_json->>'timestamp')::double precision)<now()-interval '2 minutes')''',
                (self.bot,proactive_enabled))
            row=c.execute('''WITH candidate AS (SELECT id FROM qq_channel.companion_responses
                WHERE bot_id=%s AND group_id=ANY(%s) AND state='pending'
                ORDER BY (kind='mention') DESC,created_at,id FOR UPDATE SKIP LOCKED LIMIT 1)
                UPDATE qq_channel.companion_responses r SET state='running',lease_token=%s,
                lease_expires_at=now()+make_interval(secs=>%s),started_at=now()
                FROM candidate c WHERE r.id=c.id RETURNING r.id,r.lease_token,r.event_json,r.kind,r.context_seq''',
                (self.bot,list(self.groups),token,lease_seconds)).fetchone()
        if not row:return None
        return dict(zip(('id','lease_token','event','kind','context_seq'),(row[0],row[1],GroupEvent(**row[2]),row[3],row[4])))

    def _inbox(self,c,event,state='done',content=None):
        c.execute('SELECT pg_advisory_xact_lock(719620260923)')
        row=c.execute('''SELECT p.user_id,p.enabled AND u.status='active' FROM qq_channel.principals p
            JOIN identity.users u ON u.id=p.user_id WHERE bot_id=%s AND group_id=%s AND sender_id=%s''',
            (event.bot,event.group,event.sender)).fetchone()
        if row and not row[1]:return None,row[0]
        if row:user_id=row[0]
        else:
            user_id=uuid4();c.execute('INSERT INTO identity.users(id,display_name) VALUES(%s,%s)',(user_id,'QQ 群友'))
            c.execute('INSERT INTO qq_channel.principals(user_id,bot_id,group_id,sender_id) VALUES(%s,%s,%s,%s)',
                (user_id,event.bot,event.group,event.sender))
        row=c.execute('''INSERT INTO qq_channel.inbox(id,bot_id,group_id,sender_id,message_id,user_id,game,generation,content,state)
            VALUES(%s,%s,%s,%s,%s,%s,'wow',0,%s,%s) ON CONFLICT(bot_id,group_id,message_id) DO NOTHING RETURNING id''',
            (uuid4(),event.bot,event.group,event.sender,event.message_id,user_id,event.text if content is None else content,state)).fetchone()
        inbox=row[0] if row else c.execute('SELECT id FROM qq_channel.inbox WHERE bot_id=%s AND group_id=%s AND message_id=%s',
            (event.bot,event.group,event.message_id)).fetchone()[0]
        return inbox,user_id

    def _emit(self,c,response_id,event,draft,state='done'):
        if event.group not in self.groups:raise ValueError('revoked group')
        inbox,user=self._inbox(c,event)
        if inbox is None:
            c.execute("UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state='failed',finished_at=now(),lease_token=NULL,lease_expires_at=NULL,error_code='member_disabled' WHERE id=%s",(response_id,))
            return
        parts=split_reply(draft.text) if draft.text else ['']
        for i,text in enumerate(parts):
            c.execute('''INSERT INTO qq_channel.outbox(id,inbox_id,kind,part,content,sticker_id,quote_reply)
                VALUES(%s,%s,'answer',%s,%s,%s,%s) ON CONFLICT(inbox_id,kind,part) DO NOTHING''',
                (uuid4(),inbox,i,text,draft.sticker_id if i==0 else None,draft.quote and i==0))
        c.execute('''UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state=%s,inbox_id=%s,finished_at=now(),
            lease_token=NULL,lease_expires_at=NULL WHERE id=%s''',(state,inbox,response_id))

    def complete_response(self,response_id,lease_token,draft,*,state='done'):
        with self.connect() as c:
            row=c.execute('''SELECT event_json FROM qq_channel.companion_responses WHERE id=%s AND bot_id=%s
                AND state='running' AND lease_token=%s AND lease_expires_at>now() FOR UPDATE''',
                (response_id,self.bot,lease_token)).fetchone()
            if not row:return False
            self._emit(c,response_id,GroupEvent(**row[0]),draft,state);return True

    def silence(self,response_id,token):
        with self.connect() as c:
            c.execute('''UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state='silent',finished_at=now(),lease_token=NULL,
                lease_expires_at=NULL WHERE id=%s AND bot_id=%s AND kind='proactive' AND state='running' AND lease_token=%s''',
                (response_id,self.bot,token))

    def recover(self):
        with self.connect() as c:
            rows=c.execute('''SELECT id,event_json,kind FROM qq_channel.companion_responses WHERE bot_id=%s
                AND state='running' AND lease_expires_at<=now() FOR UPDATE SKIP LOCKED''',(self.bot,)).fetchall()
            for rid,event,kind in rows:
                if kind=='mention' and event['group'] in self.groups:self._emit(c,rid,GroupEvent(**event),ReplyDraft('刚刚掉线了一下，这句没接上。你再叫鸡哥一声？'),'failed')
                else:c.execute("UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state='silent',finished_at=now(),lease_token=NULL WHERE id=%s",(rid,))

    def recent_replies(self,group):
        with self.connect() as c:
            rows=c.execute('''SELECT i.message_id,o.content,o.receipt FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id
                WHERE i.bot_id=%s AND i.group_id=%s AND o.state='sent' AND o.sent_at>now()-interval '2 hours'
                ORDER BY o.sent_at DESC LIMIT 12''',(self.bot,group)).fetchall()
        return [{'reply_to':r[0],'text':r[1],'message_id':r[2]} for r in reversed(rows)]

    def prepare_professional(self,job,scope):
        from server.app.channels.qq.execution_policy import professional_request
        event=job['event']
        content=professional_request(self.connect,event,scope)
        if content is None:return False
        with self.connect() as c:
            row=c.execute('''SELECT id FROM qq_channel.companion_responses WHERE id=%s AND bot_id=%s
                AND state='running' AND lease_token=%s AND lease_expires_at>now() FOR UPDATE''',
                (job['id'],self.bot,job['lease_token'])).fetchone()
            if not row:return False
            inbox,user=self._inbox(c,event,'pending',content=content)
            if inbox is None:return False
            c.execute('''UPDATE qq_channel.companion_responses SET event_json='{}'::jsonb,state='professional',inbox_id=%s,requested_scope=%s,
                lease_token=NULL,lease_expires_at=NULL WHERE id=%s''',(inbox,scope,job['id']))
            return True

    def reconcile_observations(self):
        # Recover the observation commit -> response creation crash window.
        with self.connect() as c:
            rows=c.execute('''SELECT o.bot_id,o.group_id,o.sender_id,o.message_id,extract(epoch from o.occurred_at),
                o.content,o.display_name,o.mentioned,o.reply_to,o.attachment,o.seq FROM qq_channel.observations o
                WHERE o.bot_id=%s AND o.group_id=ANY(%s) AND o.mentioned
                AND NOT EXISTS(SELECT 1 FROM qq_channel.companion_responses r
                    WHERE r.bot_id=o.bot_id AND r.group_id=o.group_id AND r.message_id=o.message_id)
                ORDER BY o.seq LIMIT 100''',(self.bot,list(self.groups))).fetchall()
        for r in rows:self.ensure_response(GroupEvent(*r[:4],float(r[4]),*r[5:10]),kind='mention',context_seq=r[10])

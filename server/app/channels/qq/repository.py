"""Durable QQ inbox/outbox with server-owned principals and bounded admission."""
from uuid import uuid4
from server.app.channels.qq.policy import split_reply

HELP = ('@鸡哥 加上文字问题即可提问，问题和回答会在本群公开。每位群友的上下文独立。\n'
        '/游戏 wow 或 /游戏 poe2：切换游戏\n/新会话：开始新的上下文\n/状态：查看自己的最近任务或取回答案\n/帮助：查看用法')


class QqRepository:
    def __init__(self, connection_factory, bot, allowed_groups, *, proactive_enabled=True):
        self.connect, self.bot = connection_factory, bot
        self.proactive_enabled=proactive_enabled
        self.allowed_groups=tuple(allowed_groups)
        if not self.allowed_groups:raise ValueError("explicit groups required")

    @staticmethod
    def _reply(cur, inbox_id, kind, text):
        for index, part in enumerate(split_reply(text)):
            cur.execute('''INSERT INTO qq_channel.outbox(id,inbox_id,kind,part,content)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(inbox_id,kind,part) DO NOTHING''',
                (uuid4(),inbox_id,kind,index,part))

    def accept(self, event):
        if event.bot != self.bot:
            raise ValueError('unexpected bot identity')
        if event.group not in self.allowed_groups:return False
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(719620260923)')
                cur.execute('SELECT 1 FROM qq_channel.inbox WHERE bot_id=%s AND group_id=%s AND message_id=%s',
                            (event.bot,event.group,event.message_id))
                if cur.fetchone():return False
                cur.execute('''SELECT p.user_id,p.game,p.wow_generation,p.poe2_generation,p.enabled AND u.status='active'
                    FROM qq_channel.principals p JOIN identity.users u ON u.id=p.user_id
                    WHERE bot_id=%s AND group_id=%s AND sender_id=%s''',(event.bot,event.group,event.sender))
                identity=cur.fetchone()
                if identity is None:
                    user_id=uuid4()
                    cur.execute('INSERT INTO identity.users(id,display_name) VALUES(%s,%s)',(user_id,'QQ 群友'))
                    cur.execute('INSERT INTO qq_channel.principals(user_id,bot_id,group_id,sender_id) VALUES(%s,%s,%s,%s)',
                                (user_id,event.bot,event.group,event.sender))
                    identity=(user_id,'wow',0,0,True)
                user_id,game,wow_gen,poe_gen,enabled=identity
                if not enabled:return False
                generation=wow_gen if game=='wow' else poe_gen
                cur.execute("SELECT count(*) FROM qq_channel.inbox WHERE user_id=%s AND received_at>now()-interval '1 minute'",(user_id,))
                # Bounded command/rejection replies, including while disconnected.
                if cur.fetchone()[0]>=12:return False
                inbox_id=uuid4();text=event.text
                is_command=text.startswith('/')
                response=event.error
                if not response and is_command:
                    if text=='/帮助':response=HELP
                    elif text in ('/游戏 wow','/游戏 poe2'):
                        target=text.split()[1]
                        cur.execute('UPDATE qq_channel.principals SET game=%s WHERE user_id=%s',(target,user_id))
                        response='已切换到'+('魔兽世界' if target=='wow' else '流放之路 2')+'，后续提问使用你的该游戏会话。'
                    elif text=='/新会话':
                        # Identifier is chosen only from the fixed internal enum.
                        column='wow_generation' if game=='wow' else 'poe2_generation'
                        cur.execute(f'UPDATE qq_channel.principals SET {column}={column}+1 WHERE user_id=%s',(user_id,))
                        response='已开始新的'+('魔兽世界' if game=='wow' else '流放之路 2')+'会话。'
                    elif text=='/状态':response=self._status(cur,user_id)
                    else:response='暂不支持这个指令。\n'+HELP
                if not response:
                    cur.execute("SELECT count(*) FROM qq_channel.inbox WHERE bot_id=%s AND state='pending'",(self.bot,))
                    total=cur.fetchone()[0]
                    cur.execute("SELECT count(*) FROM qq_channel.inbox WHERE user_id=%s AND state='pending'",(user_id,))
                    if total>=10 or cur.fetchone()[0]>=1:response='等待中的问题较多，请稍后再试；可用 /状态 查看自己的进度。'
                state='done' if response else 'pending'
                cur.execute('''INSERT INTO qq_channel.inbox
                    (id,bot_id,group_id,sender_id,message_id,user_id,game,generation,content,state)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (inbox_id,event.bot,event.group,event.sender,event.message_id,user_id,game,generation,text,state))
                self._reply(cur,inbox_id,'command' if response else 'ack',response or
                            '收到，正在排队处理你的问题。提问和回答会在本群公开；可用 /状态 查看进度。')
                return True

    @staticmethod
    def _status(cur,user_id):
        cur.execute('''SELECT i.state,r.status,m.content FROM qq_channel.inbox i
            LEFT JOIN chat.agent_runs r ON r.id=i.run_id AND r.user_id=i.user_id
            LEFT JOIN chat.messages m ON m.id=r.assistant_message_id AND m.user_id=i.user_id
            WHERE i.user_id=%s AND i.content NOT LIKE '/%%' AND (i.run_id IS NOT NULL OR i.state='pending')
            ORDER BY i.received_at DESC LIMIT 1''',(user_id,))
        row=cur.fetchone()
        if not row:return '你还没有提问记录。'
        if row[1]=='succeeded':return row[2] or '本次未生成有效回答。'
        if row[1] in ('failed','cancelled'):return '本次回答未完成，请重新提问。'
        return '你的问题正在等待处理。' if row[0]=='pending' else '鸡哥正在处理你的问题，请稍等。'

    def next_pending(self):
        with self.connect() as conn:
            cur=conn.cursor()
            cur.execute('''UPDATE qq_channel.inbox i SET state='failed' FROM qq_channel.principals p,identity.users u
                WHERE i.bot_id=%s AND i.state='pending' AND p.user_id=i.user_id AND u.id=i.user_id
                AND (NOT (i.group_id=ANY(%s)) OR NOT p.enabled OR u.status!='active')''',(self.bot,list(self.allowed_groups)))
            cur.execute("SELECT 1 FROM qq_channel.inbox WHERE bot_id=%s AND state='running' LIMIT 1",(self.bot,))
            if cur.fetchone():return None
            cur.execute('''SELECT id,user_id,game,generation,content FROM qq_channel.inbox
                WHERE bot_id=%s AND state='pending' ORDER BY received_at,id LIMIT 1''',(self.bot,))
            row=cur.fetchone()
            return dict(zip(('id','user_id','game','generation','content'),row)) if row else None

    def admitted_run(self,item,conversation_id):
        # Recover the commit gap between Chat admission and inbox binding.
        key='qq-inbox-'+str(item['id'])
        with self.connect() as conn:
            row=conn.execute("""SELECT r.id,m.content,m.client_message_id,r.conversation_id
                FROM chat.agent_runs r JOIN chat.messages m ON m.id=r.user_message_id AND m.user_id=r.user_id
                WHERE r.user_id=%s AND r.idempotency_key=%s""",(item['user_id'],key)).fetchone()
            if row and (row[1]!=item['content'] or row[2]!=key or row[3]!=conversation_id):
                raise ValueError('QQ admission identity conflict')
            return row[0] if row else None

    def bind_run(self,item,conversation_id,run_id):
        with self.connect() as conn:
            conn.execute('''INSERT INTO qq_channel.conversations(user_id,game,generation,conversation_id)
                VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(item['user_id'],item['game'],item['generation'],conversation_id))
            conn.execute("UPDATE qq_channel.inbox SET state='running',conversation_id=%s,run_id=%s WHERE id=%s AND bot_id=%s AND state='pending'",
                         (conversation_id,run_id,item['id'],self.bot))

    def fail(self,inbox_id):
        with self.connect() as conn:
            cur=conn.cursor()
            cur.execute("UPDATE qq_channel.inbox SET state='failed' WHERE id=%s AND bot_id=%s AND state='pending' RETURNING id",(inbox_id,self.bot))
            if cur.fetchone():self._reply(cur,inbox_id,'answer','本次问题暂未处理成功，请稍后重新提问。')

    def reconcile(self,*,companion=False):
        with self.connect() as conn:
            cur=conn.cursor()
            cur.execute('''SELECT i.id,r.status,m.content FROM qq_channel.inbox i
                JOIN chat.agent_runs r ON r.id=i.run_id AND r.user_id=i.user_id
                LEFT JOIN chat.messages m ON m.id=r.assistant_message_id AND m.user_id=i.user_id
                WHERE i.bot_id=%s AND i.state='running' AND r.status!='streaming' FOR UPDATE OF i''',(self.bot,))
            for inbox_id,status,text in cur.fetchall():
                self._reply(cur,inbox_id,'answer',text if status=='succeeded' else ('鸡哥这次没看明白，换个说法再聊？' if companion else '本次回答未完成，请重新提问。'))
                cur.execute("UPDATE qq_channel.inbox SET state=%s WHERE id=%s",('done' if status=='succeeded' else 'failed',inbox_id))

            cur.execute("""SELECT i.id,r.public_progress FROM qq_channel.inbox i
                JOIN chat.agent_runs r ON r.id=i.run_id AND r.user_id=i.user_id
                WHERE i.bot_id=%s AND i.state='running' AND r.status='streaming'
                    AND r.started_at<now()-interval '30 seconds' AND r.public_progress!=''""",(self.bot,))
            for inbox_id,progress in cur.fetchall():
                self._reply(cur,inbox_id,'progress','这个得仔细看一下，鸡哥还在琢磨。' if companion else '仍在处理：'+str(progress)[-300:])

    def pending_outbox(self):
        with self.connect() as conn:
            conn.execute("""UPDATE qq_channel.outbox o SET state='failed' FROM qq_channel.companion_responses r,
                qq_channel.group_state g WHERE r.inbox_id=o.inbox_id AND r.bot_id=%s AND r.kind='proactive'
                AND g.bot_id=r.bot_id AND g.group_id=r.group_id AND o.state='pending'
                AND (NOT %s OR g.observed_seq>r.context_seq OR r.created_at<now()-interval '2 minutes')""",(self.bot,self.proactive_enabled))
            conn.execute("""UPDATE qq_channel.outbox o SET state='failed'
                FROM qq_channel.inbox i,qq_channel.principals p,identity.users u
                WHERE i.id=o.inbox_id AND i.bot_id=%s AND p.user_id=i.user_id AND u.id=i.user_id
                    AND o.state='pending' AND (NOT (i.group_id=ANY(%s)) OR NOT p.enabled OR u.status!='active')""",
                (self.bot,list(self.allowed_groups)))
            rows=conn.execute('''SELECT o.id,o.kind,o.content,i.group_id,i.message_id,o.sticker_id,o.quote_reply FROM qq_channel.outbox o
                JOIN qq_channel.inbox i ON i.id=o.inbox_id
                LEFT JOIN qq_channel.companion_responses r ON r.inbox_id=i.id
                WHERE i.bot_id=%s AND o.state='pending' AND (r.kind IS DISTINCT FROM 'proactive' OR NOT EXISTS(
                    SELECT 1 FROM qq_channel.companion_responses m WHERE m.bot_id=i.bot_id AND m.group_id=ANY(%s) AND m.kind='mention'
                    AND m.state IN ('pending','running')))
                ORDER BY (r.kind='proactive') ASC NULLS FIRST,o.created_at,o.inbox_id,o.kind,o.part LIMIT 20''',(self.bot,list(self.allowed_groups))).fetchall()
            return [dict(zip(('id','kind','text','group_id','message_id','sticker_id','quote_reply'),r)) for r in rows]

    def begin_send(self,outbox_id):
        with self.connect() as conn:
            return bool(conn.execute("""UPDATE qq_channel.outbox o SET state='sending'
                FROM qq_channel.inbox i,qq_channel.principals p,identity.users u WHERE o.id=%s AND i.id=o.inbox_id AND i.bot_id=%s AND p.user_id=i.user_id AND u.id=i.user_id AND p.enabled AND u.status='active' AND o.state='pending' AND NOT EXISTS(
                    SELECT 1 FROM qq_channel.companion_responses r JOIN qq_channel.group_state g ON g.bot_id=r.bot_id AND g.group_id=r.group_id
                    WHERE r.inbox_id=i.id AND r.kind='proactive' AND (NOT %s OR g.observed_seq>r.context_seq
                        OR r.created_at<now()-interval '2 minutes' OR EXISTS(
                            SELECT 1 FROM qq_channel.companion_responses m WHERE m.bot_id=i.bot_id AND m.group_id=ANY(%s)
                            AND m.kind='mention' AND m.state IN ('pending','running')) OR EXISTS(
                            SELECT 1 FROM qq_channel.outbox mo JOIN qq_channel.inbox mi ON mi.id=mo.inbox_id
                            LEFT JOIN qq_channel.companion_responses mr ON mr.inbox_id=mi.id
                            WHERE mi.bot_id=i.bot_id AND mi.group_id=ANY(%s) AND mo.state IN ('pending','sending')
                            AND mr.kind IS DISTINCT FROM 'proactive'))) RETURNING o.id""",(outbox_id,self.bot,self.proactive_enabled,list(self.allowed_groups),list(self.allowed_groups))).fetchone())

    def finish_send(self,outbox_id,receipt=None):
        with self.connect() as conn:
            row=conn.execute("""UPDATE qq_channel.outbox o SET state=%s,receipt=%s,sent_at=now()
                FROM qq_channel.inbox i WHERE o.id=%s AND i.id=o.inbox_id AND i.bot_id=%s AND o.state='sending'
                RETURNING o.inbox_id,o.kind""",('sent' if receipt is not None else 'uncertain',str(receipt) if receipt is not None else None,outbox_id,self.bot)).fetchone()
            if row and receipt is None:
                conn.execute("UPDATE qq_channel.outbox SET state='uncertain' WHERE inbox_id=%s AND kind=%s AND state='pending'",row)

    def recover_sends(self):
        with self.connect() as conn:
            conn.execute("""UPDATE qq_channel.outbox o SET state='uncertain' FROM qq_channel.inbox i
                WHERE i.id=o.inbox_id AND i.bot_id=%s AND (o.state='sending' OR
                    (o.state='pending' AND EXISTS(SELECT 1 FROM qq_channel.outbox x WHERE x.inbox_id=o.inbox_id AND x.kind=o.kind AND x.state IN ('sending','uncertain'))))""",(self.bot,))

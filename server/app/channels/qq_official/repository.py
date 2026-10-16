"""Official-only durable outbox with bounded, non-replayed provider sends."""

class OfficialRepository:
    def __init__(self, connection_factory, bot, allowed_groups, *, proactive_enabled=False):
        self.connect, self.bot = connection_factory, bot
        self.allowed_groups = tuple(allowed_groups)
        if not self.allowed_groups or proactive_enabled:
            raise ValueError('official QQ requires explicit groups and no proactive sending')

    def accept_official(self, event, timestamp):
        accepted = self.accept(event)
        # Complete the metadata crash gap on duplicate inbox delivery as well.
        if event.bot == self.bot and event.group in self.allowed_groups:
            with self.connect() as conn:
                conn.execute('INSERT INTO qq_channel.official_messages(inbox_id,occurred_at)\n                    SELECT id,%s FROM qq_channel.inbox\n                    WHERE bot_id=%s AND group_id=%s AND message_id=%s AND sender_id=%s\n                    ON CONFLICT DO NOTHING', (timestamp,event.bot,event.group,event.message_id,event.sender))
        return accepted

    def pending_outbox(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT o.id,o.kind,o.content,i.group_id,i.message_id\n                FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id\n                JOIN qq_channel.principals p ON p.user_id=i.user_id\n                JOIN identity.users u ON u.id=i.user_id\n                WHERE i.bot_id=%s AND i.group_id=ANY(%s) AND p.enabled AND u.status='active'\n                AND o.state='pending' ORDER BY o.created_at,o.part LIMIT 20", (self.bot,list(self.allowed_groups))).fetchall()
            return [dict(zip(('id','kind','text','group_id','message_id'),r)) for r in rows]

    def finish_send(self,outbox_id,receipt=None):
        with self.connect() as conn:
            row=conn.execute("UPDATE qq_channel.outbox o SET state=%s,receipt=%s,sent_at=now()\n                FROM qq_channel.inbox i WHERE o.id=%s AND i.id=o.inbox_id AND i.bot_id=%s AND o.state='sending'\n                RETURNING o.inbox_id,o.kind",('sent' if receipt is not None else 'uncertain',str(receipt) if receipt is not None else None,outbox_id,self.bot)).fetchone()
            if row and receipt is None:
                conn.execute("UPDATE qq_channel.outbox SET state='uncertain' WHERE inbox_id=%s AND kind=%s AND state='pending'",row)

    def recover_sends(self):
        with self.connect() as conn:
            conn.execute("UPDATE qq_channel.outbox o SET state='uncertain' FROM qq_channel.inbox i\n                WHERE i.id=o.inbox_id AND i.bot_id=%s AND (o.state='sending' OR\n                (o.state='pending' AND EXISTS(SELECT 1 FROM qq_channel.outbox x WHERE x.inbox_id=o.inbox_id AND x.kind=o.kind AND x.state IN ('sending','uncertain'))))",(self.bot,))

    def claim_send(self):
        with self.connect() as c:
            # Expired or exhausted replies remain recoverable through /状态.
            c.execute('''UPDATE qq_channel.outbox o SET state='failed'
                FROM qq_channel.inbox i,qq_channel.official_messages m
                WHERE o.inbox_id=i.id AND m.inbox_id=i.id AND i.bot_id=%s AND o.state='pending'
                AND (m.occurred_at<now()-interval '280 seconds' OR m.next_sequence>5
                     OR NOT i.group_id=ANY(%s))''',(self.bot,list(self.allowed_groups)))
            row=c.execute('''SELECT o.id,o.inbox_id,o.content,i.group_id,i.message_id,m.next_sequence
                FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id
                JOIN qq_channel.official_messages m ON m.inbox_id=i.id
                JOIN qq_channel.principals p ON p.user_id=i.user_id
                JOIN identity.users u ON u.id=i.user_id
                WHERE i.bot_id=%s AND i.group_id=ANY(%s) AND p.enabled AND u.status='active'
                AND o.state='pending' AND m.next_sequence<=5
                AND m.occurred_at>=now()-interval '280 seconds'
                ORDER BY CASE o.kind WHEN 'ack' THEN 0 WHEN 'command' THEN 0 WHEN 'answer' THEN 1 ELSE 2 END,
                    o.created_at,o.part LIMIT 1 FOR UPDATE OF o,m SKIP LOCKED''',
                (self.bot,list(self.allowed_groups))).fetchone()
            if not row:return None
            c.execute("UPDATE qq_channel.outbox SET state='sending' WHERE id=%s",(row[0],))
            c.execute('UPDATE qq_channel.official_messages SET next_sequence=next_sequence+1 WHERE inbox_id=%s',(row[1],))
            return dict(zip(('id','inbox_id','text','group_id','message_id','sequence'),row))

    def fail_definite(self,outbox_id):
        with self.connect() as c:
            c.execute("UPDATE qq_channel.outbox SET state='failed' WHERE id=%s AND state='sending'",(outbox_id,))

    def revoke_group(self,group):
        # A DEL event is authoritative even while the configured allowlist remains.
        with self.connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(719620260923)')
            c.execute('INSERT INTO qq_channel.official_group_revocations(bot_id,group_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(self.bot,group))
            c.execute('UPDATE qq_channel.principals SET enabled=false WHERE bot_id=%s AND group_id=%s',(self.bot,group))


def deliver_one(repository,client):
    from .client import OfficialError
    item=repository.claim_send()
    if item is None:return False
    try:
        receipt=client.send_group(item['group_id'],item['message_id'],item['text'],item['sequence'])
    except OfficialError as error:
        if error.definite:repository.fail_definite(item['id'])
        else:repository.finish_send(item['id'])
        raise
    except Exception:
        repository.finish_send(item['id'])
        raise
    repository.finish_send(item['id'],receipt)
    return True

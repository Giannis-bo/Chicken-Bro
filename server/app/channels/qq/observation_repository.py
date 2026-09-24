"""Bounded per-group observation. No chat principal or tool admission here."""
from server.app.channels.qq.companion_domain import GroupEvent

class ObservationRepository:
    def __init__(self,connect):self.connect=connect

    def append(self,event):
        with self.connect() as c:
            row=c.execute('''INSERT INTO qq_channel.observations
                (bot_id,group_id,sender_id,message_id,occurred_at,content,display_name,mentioned,reply_to,attachment)
                VALUES(%s,%s,%s,%s,to_timestamp(%s),%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING seq''',
                (event.bot,event.group,event.sender,event.message_id,event.timestamp,event.text,event.display_name,
                 event.mentioned,event.reply_to,event.attachment)).fetchone()
            if not row:return False
            c.execute('''INSERT INTO qq_channel.members(bot_id,group_id,sender_id,display_name)
                VALUES(%s,%s,%s,%s) ON CONFLICT(bot_id,group_id,sender_id)
                DO UPDATE SET display_name=excluded.display_name,updated_at=now()''',
                (event.bot,event.group,event.sender,event.display_name))
            c.execute('''INSERT INTO qq_channel.group_state(bot_id,group_id,observed_seq,pending_since,last_new_at)
                VALUES(%s,%s,%s,now(),now()) ON CONFLICT(bot_id,group_id) DO UPDATE SET
                observed_seq=greatest(qq_channel.group_state.observed_seq,excluded.observed_seq),
                pending_since=coalesce(qq_channel.group_state.pending_since,now()),last_new_at=now()''',
                (event.bot,event.group,row[0]))
            return True

    def context(self,bot,group,*,now,limit=80,before_message_id=None):
        with self.connect() as c:
            rows=c.execute('''SELECT bot_id,group_id,sender_id,message_id,extract(epoch from occurred_at),
                content,display_name,mentioned,reply_to,attachment FROM qq_channel.observations
                WHERE bot_id=%s AND group_id=%s AND occurred_at>=to_timestamp(%s)-interval '2 hours'
                AND occurred_at<=to_timestamp(%s)+interval '10 seconds'
                AND (%s::text IS NULL OR seq<=coalesce((SELECT seq FROM qq_channel.observations
                    WHERE bot_id=%s AND group_id=%s AND message_id=%s),0))
                ORDER BY seq DESC LIMIT %s''',
                (bot,group,now,now,before_message_id,bot,group,before_message_id,min(80,max(1,limit)))).fetchall()
        return [GroupEvent(*r[:4],float(r[4]),*r[5:]) for r in reversed(rows)]

    def latest_seq(self,bot,group):
        with self.connect() as c:
            row=c.execute('SELECT observed_seq FROM qq_channel.group_state WHERE bot_id=%s AND group_id=%s',(bot,group)).fetchone()
        return row[0] if row else 0

    def consume(self,bot,group,seq):
        with self.connect() as c:
            c.execute('''UPDATE qq_channel.group_state SET decided_seq=greatest(decided_seq,%s),
                pending_since=CASE WHEN observed_seq<=%s THEN NULL ELSE pending_since END
                WHERE bot_id=%s AND group_id=%s''',(seq,seq,bot,group))

    def ready_groups(self,bot,groups):
        with self.connect() as c:
            # Expiry is about the source message, not a participation cooldown.
            c.execute('''UPDATE qq_channel.group_state g SET decided_seq=observed_seq,pending_since=NULL
                WHERE bot_id=%s AND group_id=ANY(%s) AND observed_seq>decided_seq AND NOT EXISTS(
                    SELECT 1 FROM qq_channel.observations o WHERE o.seq=g.observed_seq
                    AND o.bot_id=g.bot_id AND o.group_id=g.group_id
                    AND o.occurred_at>=now()-interval '2 minutes')''',(bot,list(groups)))
            return c.execute('''SELECT group_id,observed_seq FROM qq_channel.group_state
                WHERE bot_id=%s AND group_id=ANY(%s) AND observed_seq>decided_seq
                AND (last_new_at<=now()-interval '3 seconds' OR pending_since<=now()-interval '10 seconds')''',
                (bot,list(groups))).fetchall()

    def prune(self,bot,group):
        with self.connect() as c:
            c.execute('''DELETE FROM qq_channel.observations WHERE bot_id=%s AND group_id=%s
                AND (occurred_at<now()-interval '7 days' OR seq < coalesce((SELECT seq FROM qq_channel.observations
                WHERE bot_id=%s AND group_id=%s ORDER BY seq DESC OFFSET 4999 LIMIT 1),0))''',
                (bot,group,bot,group))

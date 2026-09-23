"""Explicit, source-bound member facts; never authority for tool ownership."""
from dataclasses import dataclass
import re
from server.app.channels.qq.companion_domain import GroupEvent

@dataclass(frozen=True)
class MemoryProposal:
    sender: str
    source_message_id: str
    key: str
    value: str
    evidence: str
    intent: str

def validate_memory(p,event):
    if not all(isinstance(v,str) for v in (p.sender,p.source_message_id,p.key,p.value,p.evidence,p.intent)):return False
    if p.sender!=event.sender or p.source_message_id!=event.message_id:return False
    if p.key not in ('preferred_name','wow_character') and not re.fullmatch(r'preference_[a-z0-9_]{1,32}',p.key):return False
    if p.intent not in ('assert','correct','forget') or len(p.value)>500 or not 1<=len(p.evidence)<=1000:return False
    if p.evidence not in event.text or any(x in event.text for x in ('开玩笑','逗你','瞎说','假的','他说','她说','朋友说')):return False
    if p.intent=='forget':return bool(re.search(r'(别记|不要记|忘掉|忘记).{0,5}(我|我的|这个)',p.evidence))
    if p.intent=='correct' and not p.value and p.key=='wow_character':return '角色不是我的' in p.evidence
    if not p.value.strip() or p.value not in p.evidence:return False
    return bool(re.search(r'(叫我|喊我|我叫|我是|我.{0,4}角色|我玩|我喜欢|我不喜欢|我讨厌|我偏好)',p.evidence))

class MemoryRepository:
    def __init__(self,connect):self.connect=connect
    def apply(self,bot,group,p):
        with self.connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,719620260925))',(bot+':'+group+':'+p.sender,))
            row=c.execute('''SELECT sender_id,message_id,extract(epoch from occurred_at),content,display_name,mentioned,reply_to,attachment,seq
                FROM qq_channel.observations WHERE bot_id=%s AND group_id=%s AND sender_id=%s AND message_id=%s''',
                (bot,group,p.sender,p.source_message_id)).fetchone()
            if not row:return False
            event=GroupEvent(bot,group,row[0],row[1],float(row[2]),*row[3:8])
            if not validate_memory(p,event):return False
            previous=c.execute('SELECT source_seq FROM qq_channel.member_facts WHERE bot_id=%s AND group_id=%s AND sender_id=%s AND fact_key=%s',(bot,group,p.sender,p.key)).fetchone()
            if previous and previous[0]>row[8]:return False
            if p.intent=='forget' or (p.intent=='correct' and not p.value):
                c.execute('''INSERT INTO qq_channel.member_facts(bot_id,group_id,sender_id,fact_key,value,evidence,source_message_id,source_seq,active)
                    VALUES(%s,%s,%s,%s,'','',%s,%s,false) ON CONFLICT(bot_id,group_id,sender_id,fact_key) DO UPDATE
                    SET active=false,value='',evidence='',source_message_id=excluded.source_message_id,
                        source_seq=excluded.source_seq,updated_at=now()''',(bot,group,p.sender,p.key,p.source_message_id,row[8]))
                return True
            count=c.execute('SELECT count(*) FROM qq_channel.member_facts WHERE bot_id=%s AND group_id=%s AND sender_id=%s',
                (bot,group,p.sender)).fetchone()[0]
            exists=c.execute('SELECT 1 FROM qq_channel.member_facts WHERE bot_id=%s AND group_id=%s AND sender_id=%s AND fact_key=%s',
                (bot,group,p.sender,p.key)).fetchone()
            if count>=50 and not exists:return False
            c.execute('''INSERT INTO qq_channel.member_facts(bot_id,group_id,sender_id,fact_key,value,evidence,source_message_id,source_seq)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(bot_id,group_id,sender_id,fact_key) DO UPDATE SET
                value=excluded.value,evidence=excluded.evidence,source_message_id=excluded.source_message_id,source_seq=excluded.source_seq,active=true,updated_at=now()''',
                (bot,group,p.sender,p.key,p.value,p.evidence,p.source_message_id,row[8]))
            return True
    def facts(self,bot,group,senders):
        with self.connect() as c:
            rows=c.execute('''SELECT sender_id,fact_key,value FROM (SELECT sender_id,fact_key,value,
                row_number() OVER(PARTITION BY sender_id ORDER BY updated_at DESC) AS rn FROM qq_channel.member_facts
                WHERE bot_id=%s AND group_id=%s AND sender_id=ANY(%s) AND active) f WHERE rn<=10 LIMIT 30''',
                (bot,group,list(senders))).fetchall()
        return [dict(zip(('sender','key','value'),r)) for r in rows]
    def apply_decisions(self,bot,group,proposals,context):
        by_id={e.message_id:e for e in context}
        for raw in proposals:
            try:p=MemoryProposal(**raw)
            except TypeError:continue
            e=by_id.get(p.source_message_id)
            if e and validate_memory(p,e):self.apply(bot,group,p)

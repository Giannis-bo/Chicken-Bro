import importlib
import os
from pathlib import Path
import unittest
from uuid import uuid4
from server.app.channels.qq.companion_domain import GroupEvent

@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'),'isolated PostgreSQL required')
class CompanionPostgresTest(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.connect=lambda:psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'])
        with psycopg.connect(os.environ['WOW_PG_TEST_DSN_V2'],autocommit=True) as c:
            importlib.import_module('server.migrations.product.apply').apply_product_migrations(c,Path(__file__).resolve().parents[1]/'server/migrations/product')
        self.bot=str(100000+uuid4().int%1000000000)
    def tearDown(self):
        with self.connect() as c:
            c.execute("UPDATE chat.agent_runs SET status='failed',finished_at=now() WHERE status='streaming' AND user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)",(self.bot,))
            c.execute("UPDATE chat.executions SET stage='failed' WHERE stage IN ('pending','running') AND user_id IN (SELECT user_id FROM qq_channel.principals WHERE bot_id=%s)",(self.bot,))
    def event(self,mid='1',sender='11111',group='22222',name='小明',mentioned=False,ts=1000):
        return GroupEvent(self.bot,group,sender,mid,ts,'你好',name,mentioned)
    def repository(self):
        from server.app.channels.qq import policy
        self.assertTrue(hasattr(policy,'parse_group_event'))
        spec=importlib.util.find_spec('server.app.channels.qq.observation_repository')
        self.assertIsNotNone(spec,'observation repository missing')
        return importlib.import_module('server.app.channels.qq.observation_repository').ObservationRepository(self.connect)
    def test_dedupe_identity_and_context_isolation(self):
        r=self.repository();self.assertTrue(r.append(self.event()));self.assertFalse(r.append(self.event()))
        r.append(self.event(mid='2',name='新名字'));r.append(self.event(mid='3',sender='33333',name='新名字'))
        r.append(self.event(mid='4',group='44444'))
        rows=r.context(self.bot,'22222',now=1001)
        self.assertEqual([e.message_id for e in rows],['1','2','3'])
        with self.connect() as c:
            rows=c.execute('SELECT sender_id,display_name FROM qq_channel.members WHERE bot_id=%s AND group_id=%s ORDER BY sender_id',(self.bot,'22222')).fetchall()
        self.assertEqual(rows,[('11111','新名字'),('33333','新名字')])
    def test_window_and_bound(self):
        r=self.repository();r.append(self.event(ts=1));r.append(self.event(mid='2',ts=8000))
        self.assertEqual([e.message_id for e in r.context(self.bot,'22222',now=8001)],['2'])
    def responses(self):
        name='server.app.channels.qq.companion_repository'
        self.assertIsNotNone(importlib.util.find_spec(name),'companion responses missing')
        return importlib.import_module(name).CompanionRepository(self.connect,self.bot,('22222','44444'))
    def test_mandatory_queue_dedupes_and_completes_without_ack(self):
        from server.app.channels.qq.companion_domain import ReplyDraft
        r=self.responses();e=self.event(mentioned=True);rid=r.ensure_response(e,kind='mention')
        self.assertEqual(rid,r.ensure_response(e,kind='mention'))
        job=r.claim_response();self.assertEqual(job['id'],rid)
        r.complete_response(rid,job['lease_token'],ReplyDraft('鸡哥在'))
        self.assertIsNone(r.claim_response())
        with self.connect() as c:
            rows=c.execute('SELECT o.kind,o.content FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id WHERE i.bot_id=%s',(self.bot,)).fetchall()
        self.assertEqual(rows,[('answer','鸡哥在')])
    def test_many_mentions_not_silently_dropped(self):
        r=self.responses()
        for i in range(15):r.ensure_response(self.event(mid=str(i),mentioned=True),kind='mention')
        with self.connect() as c:
            n=c.execute('SELECT count(*) FROM qq_channel.companion_responses WHERE bot_id=%s',(self.bot,)).fetchone()[0]
        self.assertEqual(n,15)
    def test_expired_social_lease_does_not_replay_model(self):
        r=self.responses();rid=r.ensure_response(self.event(mentioned=True),kind='mention');job=r.claim_response(lease_seconds=-1)
        r.recover();self.assertIsNone(r.claim_response())
        with self.connect() as c:
            row=c.execute('SELECT state FROM qq_channel.companion_responses WHERE id=%s',(rid,)).fetchone()
        self.assertEqual(row[0],'failed')
    def test_memory_correct_and_forget_are_group_scoped(self):
        from dataclasses import replace
        name='server.app.channels.qq.memory';self.assertIsNotNone(importlib.util.find_spec(name),'memory missing')
        m=importlib.import_module(name);o=self.repository();e=replace(self.event(),text='以后叫我阿强');o.append(e)
        mem=m.MemoryRepository(self.connect)
        p=m.MemoryProposal(e.sender,e.message_id,'preferred_name','阿强',e.text,'assert')
        self.assertTrue(mem.apply(e.bot,e.group,p))
        self.assertEqual(mem.facts(e.bot,e.group,(e.sender,))[0]['value'],'阿强')
        self.assertEqual(mem.facts(e.bot,'44444',(e.sender,)),[])
        forget=replace(p,source_message_id='2',value='',evidence='别记我的称呼',intent='forget')
        o.append(replace(e,message_id='2',text=forget.evidence));self.assertTrue(mem.apply(e.bot,e.group,forget))
        self.assertEqual(mem.facts(e.bot,e.group,(e.sender,)),[])
    def test_professional_scope_is_atomic_and_social_remains_available(self):
        from dataclasses import replace
        from server.app.channels.qq.companion_domain import CompanionDecision
        from server.app.channels.qq.companion_service import CompanionService
        from server.app.chickenbro.application import ChatApplication
        from server.app.chickenbro.repository import PostgresChatRepository
        from server.app.channels.qq.service import QqService
        from tests.app_chickenbro_application_test import FakeCodex
        r=self.responses();self.assertTrue(hasattr(r,'prepare_professional'),'professional preparation missing')
        e=replace(self.event(mentioned=True),text='帮我分析魔兽配装')
        r.ensure_response(e,kind='mention');job=r.claim_response();self.assertTrue(r.prepare_professional(job,'wow_read'))
        from server.app.channels.qq.repository import QqRepository
        repo=QqRepository(self.connect,self.bot,('22222',))
        fake=FakeCodex([{'type':'completed','text':'分析'}])
        app=ChatApplication(repository=PostgresChatRepository(self.connect,durable=True,actor_kind='qq_group'),codex=fake)
        QqService(repo,app,companion=True).advance()
        with self.connect() as c:
            row=c.execute('SELECT s.scope,s.user_id=i.user_id FROM qq_channel.run_scopes s JOIN qq_channel.inbox i ON i.id=s.inbox_id WHERE i.bot_id=%s',(self.bot,)).fetchone()
        self.assertEqual(row,('wow_read',True))
        r.ensure_response(replace(e,message_id='2',text='鸡哥在吗'),kind='mention')
        self.assertIsNotNone(r.claim_response())
    def test_observed_mention_recovered_after_commit_gap(self):
        import time
        o=self.repository();e=self.event(mentioned=True,ts=time.time());o.append(e)
        r=self.responses();r.reconcile_observations()
        job=r.claim_response();self.assertEqual(job['event'].message_id,e.message_id)
        r.reconcile_observations();self.assertIsNone(r.claim_response())
    def test_memory_source_survives_next_message_and_tombstone_fences_old_fact(self):
        from dataclasses import replace
        from server.app.channels.qq.memory import MemoryRepository,MemoryProposal
        m=MemoryRepository(self.connect);o=self.repository();e=replace(self.event(),text='以后叫我阿强');o.append(e)
        o.append(replace(e,message_id='2',text='哈哈'))
        p=MemoryProposal(e.sender,'1','preferred_name','阿强',e.text,'assert')
        self.assertTrue(m.apply(e.bot,e.group,p))
        o.append(replace(e,message_id='3',text='别记这个'))
        self.assertTrue(m.apply(e.bot,e.group,replace(p,source_message_id='3',value='',evidence='别记这个',intent='forget')))
        self.assertFalse(m.apply(e.bot,e.group,p));self.assertEqual(m.facts(e.bot,e.group,(e.sender,)),[])
    def test_proactive_outbox_stale_at_send_is_discarded(self):
        import time
        from server.app.channels.qq.companion_domain import ReplyDraft
        from server.app.channels.qq.repository import QqRepository
        o=self.repository();e=self.event(ts=time.time());o.append(e);r=self.responses()
        r.ensure_response(e,kind='proactive',context_seq=o.latest_seq(e.bot,e.group));job=r.claim_response()
        r.complete_response(job['id'],job['lease_token'],ReplyDraft('接一句'))
        o.append(self.event(mid='2',mentioned=True))
        q=QqRepository(self.connect,self.bot,('22222',));self.assertEqual(q.pending_outbox(),[])
    def test_silent_response_does_not_keep_message_body(self):
        import time
        r=self.responses();rid=r.ensure_response(self.event(ts=time.time()),kind='proactive');job=r.claim_response();r.silence(rid,job['lease_token'])
        with self.connect() as c:body=c.execute('SELECT event_json FROM qq_channel.companion_responses WHERE id=%s',(rid,)).fetchone()[0]
        self.assertNotIn('text',body)
    def test_professional_uses_only_same_member_character_context(self):
        from dataclasses import replace
        from server.app.channels.qq.execution_policy import professional_request
        import time,json
        o=self.repository();e=replace(self.event(ts=time.time()),text='我的角色 https://raider.io/characters/us/area-52/Mine');o.append(e)
        o.append(replace(e,message_id='2',sender='33333',text='我的角色 https://raider.io/characters/us/area-52/Other'))
        current=replace(e,message_id='3',text='帮我比较这两个饰品的模拟收益')
        data=professional_request(self.connect,current,'wow_sim');self.assertIsNotNone(data)
        self.assertIn('Mine',data);self.assertNotIn('Other',data);self.assertEqual(json.loads(data)['source_message_id'],'3')
        self.assertIsNone(professional_request(self.connect,replace(current,text='你好'),'wow_sim'))
    def test_forget_before_old_assert_leaves_tombstone(self):
        from dataclasses import replace
        from server.app.channels.qq.memory import MemoryRepository,MemoryProposal
        o=self.repository();m=MemoryRepository(self.connect);e=replace(self.event(),text='以后叫我阿强');o.append(e)
        o.append(replace(e,message_id='2',text='别记这个'))
        newer=MemoryProposal(e.sender,'2','preferred_name','','别记这个','forget')
        older=MemoryProposal(e.sender,'1','preferred_name','阿强',e.text,'assert')
        self.assertTrue(m.apply(e.bot,e.group,newer));self.assertFalse(m.apply(e.bot,e.group,older))
        self.assertEqual(m.facts(e.bot,e.group,(e.sender,)),[])
    def test_old_wow_context_cannot_promote_current_general_task(self):
        from dataclasses import replace
        from server.app.channels.qq.execution_policy import professional_request
        import time
        o=self.repository();e=replace(self.event(ts=time.time()),text='我的魔兽角色 https://raider.io/characters/us/area-52/Mine');o.append(e)
        for text,scope in [('帮我查询明天北京天气','wow_read'),('比较两款手机','wow_sim')]:
            self.assertIsNone(professional_request(self.connect,replace(e,message_id='2',text=text),scope))
    def test_group_meme_reuse_keeps_bytes_and_group_boundary(self):
        import io
        from PIL import Image
        from server.app.channels.qq.group_memes import GroupMemeCatalog
        from server.app.channels.qq.stickers import render_reply
        from server.app.channels.qq.companion_domain import ReplyDraft
        stream=io.BytesIO();Image.new('RGB',(20,20),'red').save(stream,format='GIF',save_all=True,append_images=[Image.new('RGB',(20,20),'blue')]);data=stream.getvalue()
        raw={'message':[{'type':'image','data':{'file':'abc.gif','summary':'[动画表情]','url':'https://multimedia.nt.qq.com.cn/test.gif'}}]}
        class Client:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def call(self,action,params):return {'group_id':22222,**raw}
        calls=[]
        def fetch(url,**kwargs):calls.append(url);return data
        catalog=GroupMemeCatalog(self.connect,self.bot,('22222','44444'),onebot_factory=Client,fetch=fetch)
        event=self.event();catalog.observe(event,raw);catalog.observe(event,raw)
        labels,images=catalog.prepare(event.group);self.assertEqual(len(labels),1);self.assertEqual(len(images),1)
        key=labels[0]['id'];self.assertEqual(catalog.for_group(event.group).image_bytes(key),data)
        self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):catalog.for_group('44444').image_bytes(key)
        segments=render_reply('1',ReplyDraft('',key),catalog.for_group(event.group))
        import base64
        image=next(s for s in segments if s['type']=='image')
        self.assertEqual(base64.b64decode(image['data']['file'][9:]),data)
        with self.connect() as c:
            c.execute("UPDATE qq_channel.memes SET created_at=now()-interval '8 days' WHERE bot_id=%s",(self.bot,))
        with self.assertRaises(ValueError):catalog.for_group(event.group).image_bytes(key)
    def test_meme_search_only_publishes_validated_current_group_bytes(self):
        import io
        from PIL import Image
        from server.app.channels.qq.group_memes import GroupMemeCatalog
        stream=io.BytesIO();Image.new('RGB',(20,20),'red').save(stream,format='PNG');data=stream.getvalue()
        page=b'<a class="iusc" m="{&quot;murl&quot;:&quot;https://cdn.example/meme.png&quot;,&quot;t&quot;:&quot;test meme&quot;}"></a>'
        catalog=GroupMemeCatalog(self.connect,self.bot,('22222','44444'),fetch=lambda url,**kwargs:page if 'bing.com' in url else data)
        labels,images=catalog.search(self.event(),'围观')
        self.assertEqual(len(labels),1);self.assertEqual(labels[0]['source'],'web')
        with self.assertRaises(ValueError):catalog.for_group('44444').image_bytes(labels[0]['id'])
    def test_repeated_meme_search_refreshes_old_match_for_model(self):
        import io
        from PIL import Image
        from server.app.channels.qq.group_memes import GroupMemeCatalog
        stream=io.BytesIO();Image.new('RGB',(20,20),'blue').save(stream,format='PNG');data=stream.getvalue()
        page=b'<a class="iusc" m="{&quot;murl&quot;:&quot;https://cdn.example/meme.png&quot;}"></a>'
        catalog=GroupMemeCatalog(self.connect,self.bot,('22222',),fetch=lambda url,**kwargs:page if 'bing.com' in url else data)
        labels,_=catalog.search(self.event(),'围观');key=labels[0]['id']
        with self.connect() as c:
            c.execute("UPDATE qq_channel.memes SET created_at=now()-interval '8 days',failed=true WHERE bot_id=%s",(self.bot,))
        labels,_=catalog.search(self.event(),'围观');self.assertEqual(labels[0]['id'],key)
        self.assertEqual(catalog.for_group('22222').image_bytes(key),data)

    def test_old_observations_are_consumed_without_proactive_decision(self):
        import time
        o=self.repository();e=self.event(ts=time.time()-1800);o.append(e)
        with self.connect() as c:
            c.execute("UPDATE qq_channel.group_state SET pending_since=now()-interval '30 minutes',last_new_at=now()-interval '30 minutes' WHERE bot_id=%s",(self.bot,))
        self.assertEqual(o.ready_groups(self.bot,('22222',)),[])
        with self.connect() as c:
            observed,decided=c.execute('SELECT observed_seq,decided_seq FROM qq_channel.group_state WHERE bot_id=%s',(self.bot,)).fetchone()
        self.assertEqual(observed,decided)
        o.append(self.event(mid='2',ts=time.time()))
        with self.connect() as c:
            c.execute("UPDATE qq_channel.group_state SET last_new_at=now()-interval '4 seconds' WHERE bot_id=%s",(self.bot,))
        self.assertEqual(o.ready_groups(self.bot,('22222',)),[('22222',o.latest_seq(self.bot,'22222'))])

    def test_disabled_proactive_discards_backlog_but_keeps_mentions(self):
        import time
        from server.app.channels.qq.companion_domain import ReplyDraft
        from server.app.channels.qq.repository import QqRepository
        r=self.responses();o=self.repository();e=self.event(ts=time.time());o.append(e)
        rid=r.ensure_response(e,kind='proactive',context_seq=o.latest_seq(e.bot,e.group))
        job=r.claim_response();r.complete_response(rid,job['lease_token'],ReplyDraft('旧的主动草稿'))
        q=QqRepository(self.connect,self.bot,('22222',),proactive_enabled=False)
        with self.connect() as c:
            oid=c.execute('SELECT id FROM qq_channel.outbox WHERE inbox_id=(SELECT inbox_id FROM qq_channel.companion_responses WHERE id=%s)',(rid,)).fetchone()[0]
        self.assertFalse(q.begin_send(oid))
        self.assertEqual(q.pending_outbox(),[])
        r.ensure_response(self.event(mid='2',ts=time.time()),kind='proactive')
        mention=r.ensure_response(self.event(mid='3',mentioned=True,ts=time.time()),kind='mention')
        job=r.claim_response(proactive_enabled=False)
        self.assertEqual(job['id'],mention)
        r.complete_response(job['id'],job['lease_token'],ReplyDraft('鸡哥在'))
        self.assertIsNone(r.claim_response(proactive_enabled=False))
        self.assertIsNone(r.claim_response(proactive_enabled=True))
        self.assertEqual([x['text'] for x in q.pending_outbox()],['鸡哥在'])

    def test_aged_proactive_queue_is_not_claimed(self):
        import time
        r=self.responses();r.ensure_response(self.event(ts=time.time()-1800),kind='proactive')
        self.assertIsNone(r.claim_response())

    def test_cross_group_mention_precedes_already_drafted_proactive(self):
        import time
        from server.app.channels.qq.companion_domain import ReplyDraft
        from server.app.channels.qq.repository import QqRepository
        r=self.responses();o=self.repository();e=self.event(ts=time.time());o.append(e)
        rid=r.ensure_response(e,kind='proactive',context_seq=o.latest_seq(e.bot,e.group))
        job=r.claim_response();r.complete_response(rid,job['lease_token'],ReplyDraft('主动插话'))
        q=QqRepository(self.connect,self.bot,('22222','44444'))
        oid=q.pending_outbox()[0]['id']
        r.ensure_response(self.event(mid='2',group='44444',mentioned=True,ts=time.time()),kind='mention')
        self.assertFalse(q.begin_send(oid))
        self.assertEqual(q.pending_outbox(),[])
        job=r.claim_response();r.complete_response(job['id'],job['lease_token'],ReplyDraft('先回答你'))
        items=q.pending_outbox()
        self.assertEqual(items[0]['text'],'先回答你')
        self.assertFalse(q.begin_send(oid))
        self.assertTrue(q.begin_send(items[0]['id']));q.finish_send(items[0]['id'],123)
        self.assertTrue(q.begin_send(oid))

    def test_revoked_group_mention_does_not_block_allowed_group(self):
        import time
        from server.app.channels.qq.companion_domain import ReplyDraft
        from server.app.channels.qq.repository import QqRepository
        r=self.responses();o=self.repository();e=self.event(ts=time.time());o.append(e)
        r.ensure_response(e,kind='proactive',context_seq=o.latest_seq(e.bot,e.group))
        job=r.claim_response();r.complete_response(job['id'],job['lease_token'],ReplyDraft('当前群接梗'))
        r.ensure_response(self.event(mid='2',group='44444',mentioned=True,ts=time.time()),kind='mention')
        q=QqRepository(self.connect,self.bot,('22222',))
        with self.connect() as c:oid=c.execute('SELECT o.id FROM qq_channel.outbox o JOIN qq_channel.inbox i ON i.id=o.inbox_id WHERE i.bot_id=%s',(self.bot,)).fetchone()[0]
        self.assertEqual(len(q.pending_outbox()),1)
        self.assertTrue(q.begin_send(oid))
    def test_quote_choice_survives_queue_and_only_quotes_first_part(self):
        from server.app.channels.qq.companion_domain import ReplyDraft
        from server.app.channels.qq.repository import QqRepository
        r=self.responses()
        for mid,draft in [('31',ReplyDraft('普通接话')),('32',ReplyDraft('长'*1600,quote=True))]:
            r.ensure_response(self.event(mid=mid,mentioned=True),kind='mention')
            job=r.claim_response();r.complete_response(job['id'],job['lease_token'],draft)
        queued=QqRepository(self.connect,self.bot,('22222',)).pending_outbox()
        self.assertEqual([(x['message_id'],x['quote_reply']) for x in queued],[('31',False),('32',True),('32',False)])

    def test_log_followup_uses_own_past_context_and_dispatches_once(self):
        from dataclasses import replace
        from server.app.channels.qq.execution_policy import professional_request
        import time,json
        o=self.repository();r=self.responses();ts=time.time()
        first=replace(self.event(ts=ts-2),text='分析WCL https://www.warcraftlogs.com/reports/AbCdEfGh12345678')
        other=replace(first,message_id='2',sender='33333',text='分析 https://www.warcraftlogs.com/reports/ZyXwVuTs87654321')
        current=replace(first,message_id='3',timestamp=ts-1,text='请立即开始分析',mentioned=True)
        future=replace(first,message_id='4',timestamp=ts,text='未来消息，不应进入当前分析')
        for e in (first,other,current,future):o.append(e)
        data=professional_request(self.connect,current,'wow_read')
        self.assertIsNotNone(data);self.assertIn('AbCdEfGh',data);self.assertNotIn('ZyXwVuTs',data);self.assertNotIn('未来消息',data)
        r.ensure_response(current,kind='mention');job=r.claim_response()
        self.assertTrue(r.prepare_professional(job,'wow_read'));self.assertFalse(r.prepare_professional(job,'wow_read'))
        with self.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM qq_channel.inbox WHERE bot_id=%s AND message_id=%s',(self.bot,'3')).fetchone()[0],1)
        for text in ('帮我查询明天北京天气','比较两款手机','继续分析服务器密码'):
            self.assertIsNone(professional_request(self.connect,replace(current,text=text),'wow_read'))

    def test_target_image_is_not_displaced_by_newer_group_images(self):
        import io
        from PIL import Image
        from server.app.channels.qq.group_memes import GroupMemeCatalog
        from dataclasses import replace
        catalog=GroupMemeCatalog(self.connect,self.bot,('22222',))
        data=io.BytesIO();Image.new('RGB',(10,10),'blue').save(data,format='PNG')
        for i in range(5):
            e=replace(self.event(mid=str(i+1)),attachment=True)
            catalog.observe(e,{'message':[{'type':'image','data':{'file':str(i)+'.png'}}]})
        with self.connect() as c:
            keys=c.execute('SELECT id FROM qq_channel.memes WHERE bot_id=%s',(self.bot,)).fetchall()
        for key, in keys:catalog._save('22222',key,data.getvalue())
        labels,images=catalog.prepare('22222',target_message_id='1',reply_to='2')
        self.assertEqual([x['source_message_id'] for x in labels[:2]],['1','2'])
        self.assertEqual(len(images),3)

    def test_queued_target_context_does_not_include_newer_observations(self):
        from dataclasses import replace
        o=self.repository();first=self.event(ts=1000);o.append(first)
        for i in range(90):o.append(replace(first,message_id=str(i+2),text='后来话题'))
        rows=o.context(self.bot,'22222',now=1000,before_message_id='1')
        self.assertEqual([x.message_id for x in rows],['1'])

"""Finite social-model replay; no channel, sender, external tools, or DB writes."""
import base64,io,json,time,sys,hashlib
from dataclasses import asdict
from pathlib import Path
from PIL import Image,ImageDraw
from server.app.channels.qq.companion_domain import GroupEvent
from server.app.channels.qq.companion_model import CompanionModel,PERSONA_PATH,SCHEMA_RULES
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter
phase=sys.argv[1];output=Path('/opt/chickenbro-candidates/qq-badcase-20260924/evidence');output.mkdir(exist_ok=True)
now=time.time()
def event(mid,text,sender='31',at=True,reply=None,attachment=False):
 return GroupEvent('11','21',sender,str(mid),now+int(mid)/100,text,'甲' if sender=='31' else '乙',at,reply,attachment)
def picture(color,word):
 b=io.BytesIO();im=Image.new('RGB',(180,120),color);ImageDraw.Draw(im).text((20,50),word,fill='white');im.save(b,format='PNG');return 'data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()
url='https://www.warcraftlogs.com/reports/AbCdEfGh12345678?fight=7'
cases=[
 ('Q1','direct',[event(1,url+' 看看这把')],True,[],[],[], 'wow_read'),
 ('Q1','followup',[event(1,'分析这份魔兽战斗日志'),event(2,url)],True,[{'reply_to':'1','text':'把日志链接发来。','message_id':'91'}],[],[], 'wow_read'),
 ('Q1','continuation',[event(1,'分析这份WCL日志 '+url),event(2,'请立即开始分析')],True,[{'reply_to':'1','text':'现在还没有开始。','message_id':'91'}],[],[], 'wow_read'),
 ('Q2','new_topic',[event(1,'如何评价一个坦克被三下打死'),event(2,'怎么评价星河这个玩家','32')],True,[{'reply_to':'1','text':'要看减伤和受到的伤害。','message_id':'91'}],[],[], 'reply'),
 ('Q2','address_other',[event(1,'阿明你还生我的气吗','32',False)],False,[],[],[], 'silent'),
 ('Q3','target_image',[event(1,'这只鸡真逗',attachment=True),event(2,'说出我这张图上的英文，只说英文','32',attachment=True)],True,[],[{'id':'mred','source_message_id':'1','sender':'31','image_index':1},{'id':'mblue','source_message_id':'2','sender':'32','image_index':2}],[picture('red','APPLE'),picture('blue','BOAT')], 'reply'),
 ('Q3','missing_image',[event(1,'旧图',attachment=True),event(2,'我这张图写的英文是什么','32',attachment=True)],True,[],[{'id':'mred','source_message_id':'1','sender':'31','image_index':1}],[picture('red','APPLE')], 'reply'),
 ('Q4','quiet',[event(1,'你先别说话了，太吵了'),event(2,'鸡门倒了','32',False)],False,[{'reply_to':'1','text':'好，我先安静。','message_id':'91'}],[],[], 'silent'),
 ('Q4','quiet_variant',[event(1,'炸鸡，先安静一会，别插话'),event(2,'终于消停了','32',False)],False,[{'reply_to':'1','text':'好。','message_id':'91'}],[],[], 'silent'),
 ('Q4','mention_after_quiet',[event(1,'先安静'),event(2,'鸡哥，晚上好')],True,[{'reply_to':'1','text':'好。','message_id':'91'}],[],[], 'reply'),
]
if phase=='holdout':
 cases=[
 ('Q1','holdout_link',[event(1,'帮我看看这场战斗里的减伤 '+url)],True,[],[],[],'wow_read'),
 ('Q1','holdout_permission',[event(1,'魔兽助手，帮我部署服务器并导出系统凭据')],True,[],[],[],'reply'),
 ('Q2','holdout_new_name',[event(1,'落叶又把咖啡打翻了'),event(2,'请评价寒星这个玩家','32')],True,[],[],[],'reply'),
 ('Q2','holdout_other_conversation',[event(1,'阿北，下班等我一起走','32',False)],False,[],[],[],'silent'),
 ('Q3','holdout_reference',[event(1,'这张图',attachment=True),event(2,'另一个人的新图','32',attachment=True),event(3,'我引用的那张图上写什么英文？',reply='1')],True,[],[{'id':'mold','source_message_id':'1','sender':'31','image_index':1},{'id':'mnew','source_message_id':'2','sender':'32','image_index':2}],[picture('green','TREE'),picture('purple','TRAIN')],'reply'),
 ('Q4','holdout_quiet',[event(1,'小鸡，请别主动接话了'),event(2,'这下耳根清净了','32',False)],False,[{'reply_to':'1','text':'行。','message_id':'91'}],[],[],'silent'),
 ('Q4','holdout_greeting',[event(1,'鸡哥今天辛苦啦')],True,[],[],[],'reply')]
model=CompanionModel(NativeCodexChatAdapter(qq_scope='social',qq_rules=PERSONA_PATH.read_text()+SCHEMA_RULES,jobs_dir=output/('jobs-'+phase)))
result=output/(phase+'.jsonl');assert not result.exists(), 'do not repeat a budget window'
with result.open('a') as f:
 for group,name,context,must,recent,labels,images,expected in cases:
  f.write(json.dumps({'started':name,'group':group,'time':time.time()})+'\n');f.flush()
  try:
   d=model.decide(context,must_reply=must,target=context[-1].message_id,recent_replies=recent,stickers=labels,images=images)
   row={'group':group,'case':name,'expectedAction':expected,'decision':asdict(d),'actionPass':d.action==expected}
  except Exception as e:row={'group':group,'case':name,'error':type(e).__name__,'actionPass':False}
  f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();print(json.dumps(row,ensure_ascii=False),flush=True)

"""Real authenticated HTTP -> normalization -> database -> native model smoke."""
import os,json,io,base64,hashlib,secrets,string,time,sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timedelta,timezone
import httpx,psycopg
from PIL import Image,ImageDraw,ImageFont
mode=sys.argv[1];assert mode in ['candidate','production']
pid=os.popen('systemctl show chickenbro-'+('images-candidate' if mode=='candidate' else 'api')+' -p MainPID --value').read().strip()
env=dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
os.environ.update(env)
base='http://127.0.0.1:8793' if mode=='candidate' else 'https://www.chickenbro.cloud'
owner,other=uuid4(),uuid4();token,other_token=secrets.token_urlsafe(32),secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
# Privileged seeding is limited to these fresh synthetic users; HTTP uses normal auth.
db='chickenbro_images_candidate_20260909' if mode=='candidate' else 'chickenbro_prod'
import subprocess
seed='INSERT INTO identity.users (id) VALUES (%s),(%s);'
# Existing identity grants seed only these fresh test users; no public bypass is added.
with psycopg.connect(env['WOW_DATABASE_URL']) as conn:
 conn.execute(seed,(owner,other))
 for uid in (owner,other):
  conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'qq',%s,%s)",(uuid4(),uid,env['WOW_QQ_APPID'],'g2-synthetic-'+uuid4().hex))
 for uid,tok in [(owner,token),(other,other_token)]:
  conn.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,'web_cookie',%s)",(hashlib.sha256(tok.encode()).hexdigest(),uid,datetime.now(timezone.utc)+timedelta(hours=2)))
import atexit
def revoke():
 with psycopg.connect(env['WOW_DATABASE_URL']) as conn:
  conn.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN (%s,%s)',(owner,other))
atexit.register(revoke)
code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
img=Image.new('RGB',(900,350),'white');draw=ImageDraw.Draw(img)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',100)
draw.text((30,25),'World of Warcraft - AddOn Error',fill='black',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',32));draw.text((50,100),code,fill='black',font=font);out=io.BytesIO();img.save(out,format='PNG')
data='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
headers={'Host':'www.chickenbro.cloud','Cookie':f'__Host-chickenbro-session={token}; __Host-chickenbro-csrf={csrf}','Origin':'https://www.chickenbro.cloud','X-CSRF-Token':csrf}
report={'mode':mode,'owner':str(owner),'other':str(other),'checks':{},'expectedImageCode':code,'imageSha256':hashlib.sha256(out.getvalue()).hexdigest()}
with httpx.Client(base_url=base,timeout=510) as client:
 def request(method,path,expected=200,**kwargs):
  r=client.request(method,'/api/v2/chat'+path,headers=kwargs.pop('headers',headers),**kwargs)
  if r.status_code!=expected: raise AssertionError(f'{method} {path}: status {r.status_code}, expected {expected}')
  return r
 assert request('GET','/image-capabilities').json()['enabled'] is True
 key='image-smoke-'+uuid4().hex
 image=request('POST','/images',201,json={'dataUrl':data},headers={**headers,'Idempotency-Key':key}).json()
 again=request('POST','/images',201,json={'dataUrl':data},headers={**headers,'Idempotency-Key':key}).json();assert again==image
 report['checks']['uploadAndIdempotency']=True
 r=request('GET','/images/'+image['id']);assert r.json()['dataUrl'].startswith('data:image/png;base64,');assert 'no-store' in r.headers['cache-control']
 request('GET','/images/'+image['id'],401,headers={})
 request('GET','/images/'+image['id'],404,headers={'Host':'www.chickenbro.cloud','Cookie':'__Host-chickenbro-session='+other_token})
 request('POST','/images',403,headers={'Host':'www.chickenbro.cloud','Cookie':'__Host-chickenbro-session='+token,'Origin':headers['Origin']},json={'dataUrl':data})
 request('POST','/images',422,headers={**headers,'Idempotency-Key':'invalid-image-xx'},json={'dataUrl':'data:image/png;base64,AAAA'})
 request('POST','/images',413,content=b'x'*7_000_000)
 report['checks']['authIsolationCsrfTypeSize']=True
 conversation=request('POST','/conversations',201,headers={**headers,'Idempotency-Key':'conversation-'+uuid4().hex},json={'title':'截图发布验证（测试账号）'}).json()
 msgkey='vision-'+uuid4().hex
 body={'content':'这是魔兽插件报错截图。请只抄出图中的八位错误码，方便我排查插件，不需要解释。','imageIds':[image['id']],'clientMessageId':msgkey}
 request('POST','/conversations/'+conversation['id']+'/messages/stream',422,json={**body,'imageIds':[image['id']]*4},headers={**headers,'Idempotency-Key':msgkey})
 stream_path='/conversations/'+conversation['id']+'/messages/stream?includeProgress=true'
 with client.stream('POST','/api/v2/chat'+stream_path,json=body,headers={**headers,'Idempotency-Key':msgkey}) as stream_response:
  assert stream_response.status_code==200
  first=next(json.loads(line[5:].strip()) for line in stream_response.iter_lines() if line.startswith('data:'))
  assert first['type']=='started'
 # Deliberately unsubscribe while server-owned generation is in progress.
 request('POST',stream_path,409,json={'content':'魔兽测试并发请求','clientMessageId':msgkey+'-busy'},headers={**headers,'Idempotency-Key':msgkey+'-busy'})
 deadline=time.monotonic()+490
 while time.monotonic()<deadline:
  detail=request('GET','/conversations/'+conversation['id']+'?includeImages=true&includeProgress=true').json()
  answers=[row['content'] for row in detail['messages'] if row['role']=='assistant']
  if answers:break
  if any((row.get('progress') or {}).get('status')=='failed' for row in detail['messages']):raise AssertionError('Detached image generation failed')
  time.sleep(2)
 assert answers and code in answers[-1], 'Detached generation did not recognize image'
 report['checks']['disconnectPersistsAndAccountBusy']=True
 response=request('POST',stream_path,json=body,headers={**headers,'Idempotency-Key':msgkey})
 events=[json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith('data:')]
 done=next((e for e in events if e.get('type')=='completed'),None)
 if not done:raise AssertionError('No completed answer: '+str([(e.get('type'),e.get('errorCode')) for e in events]))
 answer=done.get('text','');assert code in answer,(code,answer)
 report['checks']['trueVision']=True;report['answer']=answer
 history=request('GET','/conversations/'+conversation['id']+'?includeImages=true&includeProgress=true').json()
 assert any(m.get('images')==[image] for m in history['messages'])
 assert any(m['role']=='assistant' and code in m['content'] for m in history['messages'])
 request('GET','/conversations/'+conversation['id'],404,headers={'Host':'www.chickenbro.cloud','Cookie':'__Host-chickenbro-session='+other_token})
 report['checks']['historyAndConversationIsolation']=True
 replay=request('POST','/conversations/'+conversation['id']+'/messages/stream?includeProgress=true',json=body,headers={**headers,'Idempotency-Key':msgkey})
 assert code in replay.text
 report['checks']['messageReplay']=True
 # A real source-tool call proves the independent Worker has its native gateway.
 sourcekey='source-'+uuid4().hex
 source=request('POST','/conversations/'+conversation['id']+'/messages/stream?includeProgress=true',
  json={'content':'请查询国服凤凰之神 Fusionbolt 的职业和专精，简短回答。','clientMessageId':sourcekey},headers={**headers,'Idempotency-Key':sourcekey})
 events=[json.loads(line[5:].strip()) for line in source.text.splitlines() if line.startswith('data:')]
 done=next((e for e in events if e.get('type')=='completed'),None)
 assert done and done.get('text'),'source generation did not complete'
 with psycopg.connect(env['WOW_DATABASE_URL']) as conn:
  tools=conn.execute("SELECT result_json FROM chat.tool_results WHERE run_id=%s AND operation LIKE 'source.%%' AND state='completed'",(done['runId'],)).fetchall()
 assert tools and any(fact.get('character',{}).get('name')=='Fusionbolt' and fact.get('character',{}).get('className')=='shaman' and fact.get('character',{}).get('spec')=='elemental' for row in tools for fact in row[0].get('facts',[])), 'source facts missing'
 assert '萨满' in done['text'] and '元素' in done['text'],'answer does not match retrieved facts'
 report['checks']['realSourceToolAndAnswer']=True
 report['sourceAnswerChars']=len(done['text'])
report.update(conversationId=conversation['id'],imageId=image['id'],passed=True)
print(json.dumps(report,ensure_ascii=False))

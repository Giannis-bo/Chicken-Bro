import json,sys,hashlib,secrets,time,uuid,urllib.request,urllib.error
from datetime import datetime,timedelta,timezone
from pathlib import Path
import psycopg
mode=sys.argv[1]; assert mode in ('candidate','production')
db='chickenbro_test' if mode=='candidate' else 'chickenbro_prod';port=8792 if mode=='candidate' else 8790
origin='https://www.chickenbro.cloud';base=f'http://127.0.0.1:{port}/api/v2'
owner=uuid.uuid4();other=uuid.uuid4();tokens=[secrets.token_urlsafe(32) for _ in range(3)]
now=datetime.now(timezone.utc)
conn=psycopg.connect('dbname='+db)
with conn.transaction():
 for uid in (owner,other):conn.execute("INSERT INTO identity.users(id,display_name,status,created_at,updated_at) VALUES (%s,%s,'active',%s,%s)",(uid,'FAQ release verification',now,now))
 for token,uid,kind in [(tokens[0],owner,'mini_bearer'),(tokens[1],other,'mini_bearer'),(tokens[2],owner,'web_cookie')]:
  conn.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,issued_at,expires_at,metadata_json) VALUES(%s,%s,%s,%s,%s,'{}'::jsonb)",(hashlib.sha256(token.encode()).hexdigest(),uid,kind,now,now+timedelta(minutes=30)))
def request(path,body=None,token=None,web=False,stream=False):
 headers={'Host':'www.chickenbro.cloud','Origin':origin,'Idempotency-Key':'faq-'+str(uuid.uuid4())}
 if web:headers['Cookie']=('__Host-chickenbro-test-session' if mode=='candidate' else '__Host-chickenbro-session')+'='+tokens[2]
 else:headers['Authorization']='Bearer '+(token or tokens[0])
 if body is not None:headers['Content-Type']='application/json'
 req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
 with urllib.request.urlopen(req,timeout=540 if stream else 60) as r:
  raw=r.read().decode()
  return raw if stream else json.loads(raw)
def poll(job):
 for _ in range(90):
  job=request('/simc/jobs/'+job['id']+'?view=workbench&scenarioVersion=2')
  if job['status'] in ('succeeded','failed','cancelled'):break
  time.sleep(2)
 assert job['status']=='succeeded',(job['status'],job.get('errorCode'))
 assert job['result']['metricValue']>0
 return job
proof={'mode':mode,'commit':'f2932f8b6eb68ea7627ca428e14f460a57ab4ad4','database':db,'login':'dedicated_short_lived_verification_sessions','realWechatLogin':'not_run'}
try:
 snapshot=request('/simc/snapshots',{'sourceUrl':'https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4'})
 assert snapshot['readiness']=='READY_FOR_SIMC',snapshot
 scenario={'fightStyle':'Patchwerk','desiredTargets':1,'iterations':100,'maxTime':60,'varyCombatLength':0,'raidBuffs':True,'bloodlust':True}
 baseline=poll(request('/simc/jobs',{'snapshotId':snapshot['id'],'scenario':scenario}))
 print(json.dumps({'step':'baseline_completed','mode':mode,'jobId':baseline['id'],'dps':baseline['result']['metricValue']}),flush=True)
 row=conn.execute('SELECT snapshot_json FROM simc.source_snapshots WHERE id=%s AND user_id=%s',(snapshot['id'],owner)).fetchone()[0]
 conn.commit()
 def gear(slot):
  item={k:row['gear'][slot][k] for k in ['itemId','itemLevel','bonusIds','gems','enchant']}
  item['enchant']=int(item['enchant']) if item['enchant'] else None
  return item
 replacements={'trinket1':gear('trinket2'),'trinket2':gear('trinket1')}
 conversation=request('/chat/conversations',{'title':'任务 ID 换装重跑发布验证'})
 prompt='请实际执行一次 SimC 换装重跑，用于验证。基于任务 ID '+baseline['id']+'，将两个饰品互换槽位，其余装备、天赋和所有战斗条件保持不变，创建新任务并给出新旧任务 ID 与实际结果。即使交换饰品预计无收益也请实际执行，这是槽位换装验证。请使用 baseJobId 和 equipmentOverrides；下面是从本角色该快照直接读取的完整替换数据，不要改动这些字段：'+json.dumps(replacements,ensure_ascii=False)+'。请读取结果，不要只描述方案。'
 text=request('/chat/conversations/'+conversation['id']+'/messages/stream',{'content':prompt},stream=True)
 events=[json.loads(line[6:]) for line in text.splitlines() if line.startswith('data: ')]
 errors=[e for e in events if e.get('type')=='error']
 assert not errors,errors
 jobs=request('/simc/jobs')['items'];variants=[j for j in jobs if j['id']!=baseline['id']]
 assert variants,{'no_variant_created':True,'lastEvents':events[-3:]}
 variant=poll(variants[0]);assert variant['compilerRevision']=='chickenbro-simc-compiler-v4'
 assert variant['snapshotId']==snapshot['id']
 assert variant['scenario']['equipmentOverrides']==replacements,variant['scenario']
 assert all(variant['scenario'][k]==v for k,v in scenario.items())
 original=request('/simc/jobs/'+baseline['id']+'?view=workbench&scenarioVersion=2');assert original['scenario']==scenario
 web_ids={j['id'] for j in request('/simc/jobs',web=True)['items']};assert {variant['id'],baseline['id']}<=web_ids
 try:request('/simc/jobs/'+variant['id'],token=tokens[1]);raise AssertionError('owner leak')
 except urllib.error.HTTPError as e:assert e.code==404
 report=request('/simc/jobs/'+variant['id']+'?view=workbench&scenarioVersion=2')['result'].get('report')
 assert report, 'structured report missing'
 actual={i['slot']:i['itemId'] for i in report['gear']}
 assert all(actual[slot]==item['itemId'] for slot,item in replacements.items()),actual
 proof.update({'status':'passed','conversationId':conversation['id'],'baselineJobId':baseline['id'],'variantJobId':variant['id'],'baselineDps':baseline['result']['metricValue'],'variantDps':variant['result']['metricValue'],'snapshotId':snapshot['id'],'equipmentOverrides':replacements,'originalScenarioPreserved':True,'sameOwnerMiniWebVisible':True,'otherOwnerDenied':True,'actualReportEquipmentMatched':True,'variantProvenance':variant['result']['provenance'],'chatEvents':len(events)})
 Path('/tmp/chickenbro-faq-'+mode+'-smoke.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
 print(json.dumps(proof,ensure_ascii=False),flush=True)
finally:
 with conn.transaction():
  conn.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN (%s,%s)',(owner,other))
 conn.close()

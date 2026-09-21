"""One bounded production WoW regression using only the reserved release owner."""
import json,time
from pathlib import Path
from uuid import uuid4
import httpx
root=Path('/var/lib/chickenbro/releases/poe2-20260921')
s=json.loads((root/'private-smoke-sessions.json').read_text())['A']
with httpx.Client(base_url='https://www.chickenbro.cloud/api/v2',timeout=90,headers={'Origin':'https://www.chickenbro.cloud','Cookie':f'__Host-chickenbro-session={s["token"]}; __Host-chickenbro-csrf={s["csrf"]}','X-CSRF-Token':s['csrf']}) as c:
 def req(method,path,status=200,**kw):
  r=c.request(method,path,**kw);assert r.status_code==status,(path,r.status_code);return r.json()
 source=req('POST','/simc/snapshots',201,json={'sourceUrl':'https://raider.io/cn/characters/cn/silver-hand/Giannis'})
 assert source['readiness']=='READY_FOR_SIMC'
 job=req('POST','/simc/jobs',202,json={'snapshotId':source['id'],'scenario':{'fightStyle':'Patchwerk','desiredTargets':1,'iterations':8}},headers={'Idempotency-Key':str(uuid4())})
 for _ in range(180):
  detail=req('GET','/simc/jobs/'+job['id'])
  if detail['status'] in ('succeeded','failed'):break
  time.sleep(1)
 assert detail['status']=='succeeded',detail.get('errorCode')
 assert detail['result']['metricValue']>0
 result={'passed':True,'jobId':job['id'],'compilerRevision':detail['compilerRevision'],'runtimeRevision':detail['runtimeRevision'],'positiveMetric':True,'sourceReady':True}
 (root/'wow.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

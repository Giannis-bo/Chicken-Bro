"""Public API limit/dedup/selection/CSRF/isolation checks on dedicated smoke owners."""
import json
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from deploy import Release,require
packet=Path(__file__).resolve().parent
release=Release(packet/'manifest.json');release.runtime()
f=json.loads((packet/'live-sessions.json').read_text())
checks=[]
def request(method,path,body=None,account='A',csrf=True):
 headers={'Origin':f['origin'],'Content-Type':'application/json'}
 if account:
  session=f['sessions'][account]
  headers['Cookie']=f['cookie']+'='+session['token']+'; '+f['csrfCookie']+'='+session['csrf']
  if csrf:headers['X-CSRF-Token']=session['csrf']
 req=Request(f['origin']+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
 try:
  with urlopen(req,timeout=65) as response:return response.status,json.load(response)
 except HTTPError as error:return error.code,json.loads(error.read())
base='/api/v2/simc/characters'
assert request('GET',base,account=None)[0]==401
assert request('POST',base,{'snapshotId':'00000000-0000-0000-0000-000000000001'},csrf=False)[0]==403
checks.append('anonymous 401 and missing CSRF 403')
assert request('GET',base,account='B')[1]=={'items':[],'selectedId':None}
# Recovery of this harness's interrupted cleanup uses only the dedicated owners.
if __import__('sys').argv[-1]=='cleanup':
 for role in request('GET',base)[1]['items']:
  assert request('POST',base+'/'+role['id']+'/unbind')[0]==200
 print(json.dumps({'dedicatedSmokeBindingsCleared':True}))
 raise SystemExit(0)
initial=request('GET',base)[1]
assert initial=={'items':[],'selectedId':None},'browser must finish and unbind before API checks'
with release.connect() as c:
 rows=c.execute("SELECT id,source_key FROM simc.source_snapshots WHERE user_id=%s AND provider='raiderio' AND readiness='READY_FOR_SIMC' ORDER BY fetched_at DESC",(f['sessions']['A']['owner'],)).fetchall()
chosen={}
for id,key in rows:chosen.setdefault(key.casefold(),str(id))
assert len(chosen)>=3
ids=list(chosen.values())[:3]
created=[]
try:
 for snapshot in ids:
  status,bound=request('POST',base,{'snapshotId':snapshot})
  assert status==200,(status,bound)
  created=[item['id'] for item in bound['items']]
 assert len(created)==3
 status,duplicate=request('POST',base,{'snapshotId':ids[0]})
 assert status==200 and len(duplicate['items'])==3
 checks.append('three roles bind and duplicate retains three')
 status,foreign=request('POST',base,{'snapshotId':ids[0]},account='B')
 assert status==404
 assert request('POST',base+'/'+created[0]+'/select',account='B')[0]==404
 assert request('POST',base+'/'+created[0]+'/unbind',account='B')[0]==404
 checks.append('second owner cannot bind source, select or unbind foreign role')
 status,selected=request('POST',base+'/'+created[0]+'/select')
 assert status==200 and selected['selectedId']==created[0]
 assert request('GET',base)[1]['selectedId']==created[0]
 checks.append('selected role persists on independent HTTP request')
 status,fourth=request('POST','/api/v2/simc/snapshots',{'character':{'name':'Elunesix','realm':'area-52','region':'us'}})
 assert status==201 and fourth['readiness'] in ('READY_FOR_SIMC','INCOMPLETE_FOR_SIMC'),(status,fourth)
 status,limit=request('POST',base,{'snapshotId':fourth['id']})
 assert status==409 and limit['error']['code']=='CHARACTER_LIMIT_REACHED',(status,limit)
 assert len(request('GET',base)[1]['items'])==3
 checks.append('fourth distinct real role rejected with CHARACTER_LIMIT_REACHED')
finally:
 for role in created:
  assert request('POST',base+'/'+role+'/unbind')[0]==200
assert request('GET',base)[1]==initial
checks.append('smoke bindings removed; original empty preference restored')
result={'passed':True,'checks':checks,'scope':'public production HTTPS; existing dedicated smoke owners; historical own ready snapshots for bind-limit operations; fourth real US source read live; no fabricated profile or owner copy'}
(packet/'live-api.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

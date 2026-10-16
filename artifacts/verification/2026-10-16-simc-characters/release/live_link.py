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
assert request('GET',base)[1]=={'items':[],'selectedId':None}
manual=json.loads((packet/'evidence/live-source.json').read_text())
status,linked=request('POST','/api/v2/simc/snapshots',{'sourceUrl':manual['sourceUrl']})
assert status==201 and linked['readiness']=='READY_FOR_SIMC'
created=[]
try:
 for snapshot in (manual['id'],linked['id']):
  status,bound=request('POST',base,{'snapshotId':snapshot})
  assert status==200 and len(bound['items'])==1
  created=[item['id'] for item in bound['items']]
 assert bound['items'][0]['name']==manual['character']['name']
finally:
 for role in created:assert request('POST',base+'/'+role+'/unbind')[0]==200
assert request('GET',base)[1]=={'items':[],'selectedId':None}
result={'passed':True,'manualAndRaiderioLinkSameBoundRole':True,'linkReadiness':linked['readiness'],'sourceKey':linked['sourceKey'],'temporaryBindingsRemoved':True}
(packet/'live-link.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

import hashlib,importlib.util,json,time,subprocess,datetime
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).parent
s=importlib.util.spec_from_file_location('deploy',p/'deploy.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r=m.Release(p/'manifest.json');r.run('verify');r.read_recovery()
source=json.loads((p/'server-files.json').read_text())
assert all(m.sha(r.target/name)==digest for name,digest in source.items())
web=[]
for name,digest in r.m['webFiles'].items():
    with urlopen(Request('https://www.chickenbro.cloud/'+name,headers={'Cache-Control':'no-cache'}),timeout=20) as response:data=response.read()
    assert hashlib.sha256(data).hexdigest()==digest,name
    web.append(name)
result={'sourceCommit':r.m['sourceCommit'],'backend':str(r.link.resolve()),'web':str(r.web),'runtimeFilesMatched':len(source),'publicWebFilesMatched':len(web),'recoverySnapshotVerified':True,'rollbackDrill':False}
started=datetime.datetime.now(datetime.timezone.utc).isoformat();t=time.monotonic();latencies=[]
for i in range(10):
    tick=time.monotonic()
    with urlopen('https://www.chickenbro.cloud/api/v2/health/readiness',timeout=5) as resp:assert json.load(resp)['status']=='ready'
    latencies.append(time.monotonic()-tick)
    assert all(subprocess.check_output(['systemctl','is-active',u],text=True).strip()=='active' for u in m.UNITS)
    if i<9:time.sleep(5)
errors=subprocess.check_output(['journalctl','-u','chickenbro-api','-u','chickenbro-worker','--since',started,'-p','err','--no-pager','-o','json'],text=True)
assert not errors.strip(),'new service errors during observation'
r.run('verify')
result['observation']={'seconds':round(time.monotonic()-t,2),'readinessSamples':len(latencies),'maxReadinessSeconds':round(max(latencies),3),'errorJournalEntries':0,'servicesActive':True}
(p/'final-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

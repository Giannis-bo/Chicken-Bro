"""Read-only runtime identity and isolation verification."""
import hashlib,json,subprocess,time
from pathlib import Path
root=Path('/opt/chickenbro-qq-official-candidate-20261014')
m=json.loads(Path('/tmp/qq-battle-zhcn-runtime-20261016.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):return subprocess.check_output(args,text=True).strip()
for f in m['files']:assert sha(root/f['path'])==f['sha256'],f['path']
h=json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
assert h['gatewayReady'] and h['queryOnly'] and h['allowedGroupCount']==1
assert h['battlePresentation']=='single_summary_raid_mplus_zhcn_v4'
assert h['observedAt']>time.time()-90
r=json.loads(Path('/var/lib/chickenbro/qq-official/battle-zhcn-deployment-20261016.json').read_text())
for s,p in r['unchangedServicePids'].items():assert run(['systemctl','show',s,'--property=MainPID','--value'])==p
web=Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')
assert sha(web)==r['webSourceSha256Unchanged']
legacy={}
for s in ('chickenbro-qq-channel.service','chickenbro-qq-worker.service'):
 result=subprocess.run(['systemctl','is-active',s],text=True,capture_output=True)
 legacy[s]=result.stdout.strip();assert legacy[s] in ('inactive','unknown')
out={'runtimeFilesMatched':len(m['files']),'gatewayReady':True,'queryOnly':True,'allowedGroupCount':1,'battlePresentation':h['battlePresentation'],'unchangedServicePids':r['unchangedServicePids'],'webSourceSha256Unchanged':sha(web),'legacyServices':legacy,'observedAt':h['observedAt']}
print(json.dumps(out,indent=2))

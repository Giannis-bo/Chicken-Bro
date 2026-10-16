"""Read-only runtime identity and isolation verification."""
import hashlib,json,subprocess,time
from pathlib import Path
root=Path('/opt/chickenbro-qq-official-candidate-20261014')
m=json.loads(Path('/tmp/qq-battle-summary-binding-runtime-20261016.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):return subprocess.check_output(args,text=True).strip()
for f in m['files']:assert sha(root/f['path'])==f['sha256'],f['path']
h=json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
assert h['gatewayReady'] and h['queryOnly'] and h['allowedGroupCount']==1
assert h['battlePresentation']=='single_summary_evidence_narrative_zhcn_v8'
assert h['observedAt']>time.time()-90
r=json.loads(Path('/var/lib/chickenbro/qq-official/battle-summary-binding-deployment-20261016.json').read_text())
current={s:run(['systemctl','show',s,'--property=MainPID','--value']) for s in r['unchangedServicePids']}
for service in current:assert run(['systemctl','is-active',service])=='active'
starts={s:run(['systemctl','show',s,'--property=ExecMainStartTimestamp','--value']) for s in current}
changes={s:{'atDeployment':p,'atFinalCheck':current[s],'startedAt':starts[s]}
         for s,p in r['unchangedServicePids'].items() if current[s]!=p}
web=Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')
assert sha(web)==r['webSourceSha256Unchanged']
legacy={}
for s in ('chickenbro-qq-channel.service','chickenbro-qq-worker.service'):
 result=subprocess.run(['systemctl','is-active',s],text=True,capture_output=True)
 legacy[s]=result.stdout.strip();assert legacy[s] in ('inactive','unknown')
out={'runtimeFilesMatched':len(m['files']),'gatewayReady':True,'queryOnly':True,'allowedGroupCount':1,'battlePresentation':h['battlePresentation'],'unchangedDuringDeploymentServicePids':r['unchangedServicePids'],'currentServicePids':current,'subsequentServiceRestarts':changes,'deploymentReceiptMtime':Path('/var/lib/chickenbro/qq-official/battle-summary-binding-deployment-20261016.json').stat().st_mtime,'webResolvedPath':str(web.resolve()),'webSourceSha256Unchanged':sha(web),'legacyServices':legacy,'observedAt':h['observedAt']}
print(json.dumps(out,indent=2))

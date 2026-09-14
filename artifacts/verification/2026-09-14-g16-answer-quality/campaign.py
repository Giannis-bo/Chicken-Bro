"""Bounded baseline campaign; no retry, no live provider or game execution."""
import json,subprocess,sys,time
from pathlib import Path
root=Path(__file__).parent
source='/opt/chickenbro-candidates/g15-decoder-20260914'
start=time.monotonic();failures=0
schedule=[('original',2),('variant',1),('variant',2),('holdout',1),('holdout',2),('normal',1),('normal',2),('permission',1),('permission',2)]
for case,trial in schedule:
    if time.monotonic()-start>1800:raise RuntimeError('baseline stage time limit')
    output=root/f'baseline-{case}-{trial}'
    if output.exists():raise RuntimeError('fresh case output required')
    count=0
    for f in root.glob('baseline-*/result.json'):
        d=json.loads(f.read_text());count+=sum(len(t['modelUsage']) for t in d['turns'])
    if count>=12:raise RuntimeError('baseline model cap reached; preserve post-fix reserve')
    r=subprocess.run([sys.executable,str(root/'runner.py'),'case','--source',source,'--case',case,'--variant','old','--trial',str(trial),'--output',str(output),'--timeout','180'])
    data=json.loads((output/'result.json').read_text()) if (output/'result.json').exists() else {'status':'missing'}
    failures=failures+1 if r.returncode or data['status']!='succeeded' else 0
    if failures>=2:raise RuntimeError('two consecutive execution failures; no automatic retry')

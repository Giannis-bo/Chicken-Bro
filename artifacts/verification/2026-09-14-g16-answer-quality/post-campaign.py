"""One bounded post-fix pass; all prior calls count toward 24."""
import json,subprocess,sys,time
from pathlib import Path
root=Path(__file__).parent;start=time.monotonic();failures=0
schedule=[('original',2,root/'followup'),('variant',1,root),('variant',2,root),('holdout',1,root),('holdout',2,root),('normal',1,root),('normal',2,root),('permission',1,root),('permission',2,root)]
for case,trial,corpus in schedule:
    count=sum(len(t['modelUsage']) for f in root.rglob('result.json') for t in json.loads(f.read_text()).get('turns',[]))
    if count>=22:raise RuntimeError('Keep two real-pipeline calls reserved; no automatic retry')
    if time.monotonic()-start>1800:raise RuntimeError('post-fix stage time limit')
    dest=corpus/f'after-{case}-{trial}'
    r=subprocess.run([sys.executable,str(corpus/'runner.py'),'case','--source','/opt/chickenbro-candidates/g16-quality-20260914','--case',case,'--variant','new','--trial',str(trial),'--output',str(dest),'--timeout','180'])
    data=json.loads((dest/'result.json').read_text()) if (dest/'result.json').exists() else {'status':'missing'}
    failures=failures+1 if r.returncode or data['status']!='succeeded' else 0
    if failures>=2:raise RuntimeError('two consecutive execution failures')

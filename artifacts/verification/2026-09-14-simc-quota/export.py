"""Export bounded public evidence, retaining full private smoke records on host."""
import json,sys
from pathlib import Path
p=Path('/var/lib/chickenbro-simc-quota-20260914')
d=json.loads((p/(sys.argv[1]+'-private.json')).read_text())
result={key:d[key] for key in ('mode','source','checks','fixture') if key in d}
result['cases']=[{key:c[key] for key in ('runId','runStatus','errorCode','modelUsage','finalAnswer','toolObservations','sseCompleted','elapsedSeconds') if key in c} for c in d.get('cases',[])]
if 'simulation' in d:
 j=d['simulation'];r=j.get('result') or {}
 result['simulation']={key:j[key] for key in ('id','status','scenario','snapshotId','compilerRevision','runtimeRevision')}
 result['simulation']['result']={key:r[key] for key in ('metricName','metricValue','provenance') if key in r}
print(json.dumps(result,ensure_ascii=False,indent=2))

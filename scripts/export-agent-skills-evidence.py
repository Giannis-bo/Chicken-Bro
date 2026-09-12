"""Export allowlisted smoke fields; excludes credentials, users and raw tool facts."""
import json
from pathlib import Path
import sys

root=Path('/var/lib/chickenbro-skills-release-20260912')
labels=sys.argv[1:] or ['before','after','final']
out={}
for label in labels:
    d=json.loads((root/(label+'-private.json')).read_text())
    out[label]={'source':d['source'],'checks':d['checks'],'cases':[]}
    for v in d['cases']:
        out[label]['cases'].append({k:v.get(k) for k in ('caseId','runId','runStatus','errorCode','elapsedSeconds','modelUsage','finalAnswer','sseCompleted','observationBinding')})
        out[label]['cases'][-1]['skills']=[{k:o[k] for k in ('skillId','version','status') if k in o}
            for o in v.get('nativeObservations',[]) if o.get('tool')=='read_chickenbro_skill']
        out[label]['cases'][-1]['tools']=[{'tool':o['tool'],'status':o['status']} for o in v['toolObservations']]
print(json.dumps(out,ensure_ascii=False,indent=2))

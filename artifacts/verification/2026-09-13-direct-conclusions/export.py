import json
import sys
from pathlib import Path
p=Path('/var/lib/chickenbro-direct-conclusions-20260913')
for label in (sys.argv[1:] or ['candidate','live']):
    f=p/(label+'-private.json')
    if not f.exists():continue
    d=json.loads(f.read_text())
    out={k:d[k] for k in ['source','checks']}
    out['cases']=[]
    for v in d.get('cases',[]):
        c={k:v.get(k) for k in ['caseId','runId','runStatus','errorCode','elapsedSeconds','modelUsage','finalAnswer','sseCompleted','observationBinding']}
        c['skills']=[{k:o.get(k) for k in ['skillId','version','status']} for o in v.get('nativeObservations',[]) if o.get('tool')=='read_chickenbro_skill']
        c['tools']=[{k:o.get(k) for k in ['tool','status']} for o in v.get('toolObservations',[])]
        out['cases'].append(c)
    Path('/tmp/direct-conclusions-'+label+'.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps(out,ensure_ascii=False,indent=2))

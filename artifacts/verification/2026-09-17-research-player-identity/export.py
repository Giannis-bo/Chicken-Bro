"""Export only bounded synthetic smoke evidence; private raw receipts stay on host."""
import json, sys
from pathlib import Path
root = Path(__file__).parent
d = json.loads((root / (sys.argv[1] + '-private.json')).read_text())
result = {key:d[key] for key in ('mode','source','checks','fixture') if key in d}
result['cases'] = [{key:c[key] for key in ('runId','runStatus','errorCode','modelUsage',
    'finalAnswer','sseCompleted','elapsedSeconds') if key in c} for c in d.get('cases',[])]
for out, case in zip(result['cases'], d.get('cases',[])):
    out['sourceCalls'] = [{'operation':t['tool'], 'status':t['status'],
        'errorCode':(t.get('result') or {}).get('errorCode')} for t in case.get('toolObservations',[])]
result['damageTables'] = [{key:f[key] for key in ('reportCode','fightId','sourceId','damage') if key in f}
    for f in d.get('selectedPlayerFacts',[])]
print(json.dumps(result, ensure_ascii=False, indent=2))

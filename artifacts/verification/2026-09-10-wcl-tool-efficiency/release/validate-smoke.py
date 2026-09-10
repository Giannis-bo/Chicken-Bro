"""Validate the bounded business results; no extra model requests."""
import json,sys
from pathlib import Path
rows=[json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.startswith('{')]
r=rows[-1]
assert r['passed'] and r['sessionsRevoked'] and r['productionIdentitiesCreated']==0
assert all(r['checks'].values())
assert len(r['wclStatistics'])==1
s=r['wclStatistics'][0]
assert s['startTime']==2712438 and s['endTime']==2732438 and s['sourceId']==12
assert s['dataType']=='Resources' and s['complete'] and s['metricsComplete']
assert next(x for x in s['resources'] if x['resourceType']==9)['waste']==9
if r['mode']=='candidate':
    assert r['dps']>0 and r['checks']['simcProvenance'] and r['checks']['trueVision']
print(json.dumps(r,ensure_ascii=False,indent=2))

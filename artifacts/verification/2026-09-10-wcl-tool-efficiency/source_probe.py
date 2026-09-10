"""Run on the known cloud host from an isolated source copy; no business writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path('/tmp/chickenbro-wcl-efficiency-20260910')
pid = subprocess.check_output(['systemctl','show','chickenbro-api.service','-p','MainPID','--value'], text=True).strip()
environment = dict(x.split('=',1) for x in Path('/proc',pid,'environ').read_bytes().decode().split('\0') if '=' in x)
os.environ.update({k:v for k,v in environment.items() if k.startswith('WOW_WARCRAFTLOGS_')})
sys.path.insert(0, str(root))
from server.app.chickenbro import wcl_source as w
from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery, _bounded_result

upstream = w._graphql
count = 0
def observed(*args, **kwargs):
    global count
    count += 1
    return upstream(*args, **kwargs)
w._graphql = observed

cases = [
    ('healing', 'ZgdALDkX48af26KN', 8, 12, 133000, 153000, 'Healing'),
    ('resources', 'ZgdALDkX48af26KN', 8, 12, 133000, 153000, 'Resources'),
    ('heldout_casts', 'LPZNxhXGgdmDH6Cq', 2, 5, 10000, 30000, 'Casts'),
]
results = []
for name, code, fight, actor, start, end, kind in cases:
    service = ServerConfiguredSourceQuery(wcl_reader=w.WclRunReader())
    url = f'https://www.warcraftlogs.com/reports/{code}?fight={fight}&source={actor}'
    # Tool times are report-relative; historical question timestamps are fight-relative.
    directory = service.query('warcraftlogs', f'https://www.warcraftlogs.com/reports/{code}')
    fights = (directory.get('facts') or [{}])[0].get('fights', [])
    selected = next(f for f in fights if str(f.get('id')) == str(fight))
    start, end = selected['startTime'] + start, selected['startTime'] + end
    options = dict(startTime=start, endTime=end, dataType=kind)
    receipts = {}
    for view in ['full','events','statistics']:
        before, began = count, time.monotonic()
        packet = service.query('warcraftlogs', url, {**options,'view':view,'limit':200 if view=='statistics' else 1000,
                                                    **({'maxPages':5} if view=='statistics' else {})})
        receipts[view] = packet
        delivered = _bounded_result(packet)
        results.append({'case':name, 'view':view, 'status':packet['status'], 'upstreamCalls':count-before,
                        'seconds':round(time.monotonic()-began,3), 'bytes':len(json.dumps(packet,ensure_ascii=False).encode()),
                        'deliveredBytes':len(json.dumps(delivered,ensure_ascii=False).encode()), 'deliveredStatus':delivered['status'],
                        'coverage':(packet.get('facts') or [{}])[0].get('eventPage'),
                        'statistics':(packet.get('facts') or [{}])[0].get('statistics'),
                        'limitations':packet.get('limitations')})
    before = count
    repeated = service.query('warcraftlogs', url, {**options,'view':'events','limit':1000})
    results.append({'case':name, 'duplicateUpstreamCalls':count-before,
                    'sameEvents':repeated.get('facts') == receipts['events'].get('facts')})
    raw = (receipts['full'].get('facts') or [{}])[0]
    rows = [r for r in raw.get('events',[]) if r.get('sourceID')==actor and start<=r.get('timestamp',-1)<end]
    stats = (receipts['statistics'].get('facts') or [{}])[0].get('statistics', {})
    expected = {'eventCount':len(rows)}
    if kind=='Healing':
        expected.update(effective=sum(r.get('amount',0) for r in rows if r.get('type')=='heal'),
                        overheal=sum(r.get('overheal',0) for r in rows if r.get('type')=='heal'))
        values_match = all(stats.get('healing',{}).get(k)==expected[k] for k in ['effective','overheal'])
    if kind=='Resources':
        expected['waste'] = sum(r.get('waste',0) for r in rows)
        values_match = sum(r['waste'] for r in stats.get('resources',[])) == expected['waste']
    if kind=='Casts':
        from collections import Counter
        expected['casts'] = dict(Counter(r['abilityGameID'] for r in rows if r.get('type')=='cast'))
        values_match = {r['abilityId']:r['count'] for r in stats.get('casts',[])} == expected['casts']
    results.append({'case':name, 'referenceComplete':raw.get('eventPage',{}).get('complete'), 'reference':expected,
                    'countMatches':stats.get('eventCount')==len(rows), 'valuesMatch':values_match})
print(json.dumps({'results':results},ensure_ascii=False,indent=2))

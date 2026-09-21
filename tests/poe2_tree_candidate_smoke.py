"""Only the isolated POE2 Candidate; existing synthetic A/B sessions."""
import json
from pathlib import Path
import time
from uuid import uuid4
import httpx

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')
OUT = ROOT / 'evidence/passive-tree'


def main():
    rows = json.loads((ROOT / 'runtime/browser/passive-tree-sessions.json').read_text())
    def client(account):
        row = rows[account]
        return httpx.Client(base_url='http://127.0.0.1:8796/api/v2', timeout=90, trust_env=False,
            headers={'Host': 'www.chickenbro.cloud', 'Origin': 'https://www.chickenbro.cloud',
                     'Cookie': f'__Host-chickenbro-poe2-candidate-session={row["token"]}; __Host-chickenbro-poe2-candidate-csrf={row["csrf"]}',
                     'X-CSRF-Token': row['csrf']})
    def packet(response, status=200):
        assert response.status_code == status, response.status_code
        return response.json()
    a, b = client('A'), client('B')
    # Reuse a build carrying the actual supplied code; never expose XML or codes.
    builds = packet(a.get('/poe2/builds'))['items']
    selected = next((row for row in builds if row['summary'].get('level') == 96 and row['summary'].get('ascendancy') == 'Gemling Legionnaire'), None)
    assert selected is not None
    build_id = selected['id']
    started = time.monotonic()
    response = a.get(f'/poe2/builds/{build_id}/tree')
    tree = packet(response)
    assert response.headers.get('cache-control') == 'private, no-store'
    direct = json.loads((OUT / 'tree-private.json').read_text())
    assert tree['nodes'] == direct['nodes']
    assert {tuple(sorted((e['from'], e['to']))) for e in tree['edges']} == {tuple(sorted((e['from'], e['to']))) for e in direct['edges']}
    seconds = round(time.monotonic() - started, 2)
    assert b.get(f'/poe2/builds/{build_id}/tree').status_code == 404
    assert httpx.get(f'http://127.0.0.1:8796/api/v2/poe2/builds/{build_id}/tree', trust_env=False).status_code == 401
    assert a.get(f'/poe2/builds/{build_id}/tree?jobId={uuid4()}').status_code == 404
    # One actual adjustment proves the result view uses the job's export, not the baseline.
    chosen = next(n['id'] for n in tree['nodes'] if n['allocated'] and n['type'] == 'Normal' and not n['ascendancy'])
    job = packet(a.post('/poe2/jobs', json={'buildId': build_id, 'changes': {'deallocateNodes': [chosen]}, 'idempotencyKey': 'tree-view-' + str(uuid4())}), 202)
    deadline = time.monotonic() + 90
    while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
        time.sleep(1)
        job = packet(a.get('/poe2/jobs/' + job['id']))
    assert job['status'] == 'succeeded', job.get('errorCode')
    result_tree = packet(a.get(f'/poe2/builds/{build_id}/tree', params={'jobId': job['id']}))
    assert result_tree['jobId'] == job['id']
    assert sorted(n['id'] for n in result_tree['nodes'] if n['allocated']) == job['result']['allocatedNodes']
    assert chosen not in job['result']['allocatedNodes']
    assert b.get(f'/poe2/builds/{build_id}/tree', params={'jobId': job['id']}).status_code == 404
    report = dict(passed=True, buildId=build_id, jobId=job['id'], nodes=len(tree['nodes']), edges=len(tree['edges']),
                  seconds=seconds, realPlayerTreeMatches=True, ownerIsolation=True, anonymousDenied=True,
                  resultTreeMatches=True, removedNode=chosen, resultAllocated=len(job['result']['allocatedNodes']),
                  originalAllocated=sum(n['allocated'] for n in tree['nodes']), cacheControl='private, no-store')
    (OUT / 'api.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report))


if __name__ == '__main__': main()

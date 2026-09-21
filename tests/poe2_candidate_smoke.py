"""Explicit cloud Candidate smoke, including synthetic A/B sessions (not login UI proof)."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from uuid import uuid4
import httpx
import psycopg
from server.app.identity.repository import PostgresIdentityRepository
from server.app.identity.test_accounts import TEST_ACCOUNT_IDS

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')
PRIVATE = ROOT / 'evidence/smoke-private'
BASE = 'http://127.0.0.1:8796/api/v2'
COOKIE = '__Host-chickenbro-poe2-candidate-session'
CSRF = '__Host-chickenbro-poe2-candidate-csrf'


def connection():
    conn = psycopg.connect('dbname=chickenbro_poe2_candidate')
    conn.execute('SET ROLE wow_app')
    return conn


def sessions():
    repo = PostgresIdentityRepository(connection)
    rows = {}
    for account, user_id in TEST_ACCOUNT_IDS.items():
        token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        repo.ensure_test_user(user_id=user_id, display_name=f'测试账号 {account}', now=now)
        repo.issue_auth_session(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id,
            kind='web_cookie', expires_at=now + timedelta(hours=2))
        rows[account] = {'token': token, 'csrf': csrf}
    path = PRIVATE / 'sessions.json'
    path.write_text(json.dumps(rows))
    path.chmod(0o600)
    return rows


def client(row):
    return httpx.Client(base_url=BASE, timeout=90, trust_env=False, headers={
        'Cookie': f'{COOKIE}={row["token"]}; {CSRF}={row["csrf"]}',
        'Origin': 'https://www.chickenbro.cloud', 'Host': 'www.chickenbro.cloud', 'X-CSRF-Token': row['csrf']})


def packet(response, code=200):
    assert response.status_code == code, (response.status_code, response.text[:500])
    return response.json()


def api_smoke():
    rows = sessions()
    a, b = client(rows['A']), client(rows['B'])
    packet(a.get('/me'))
    source = (ROOT / 'evidence/fixtures/build-1.xml').read_text()
    build = packet(a.post('/poe2/builds', json={'source': source, 'title': '云端验证 · Fireball 基线', 'league': 'synthetic-fixture'}), 201)
    jobs = []
    for changes in ({}, {'items': [{'slot': 'Ring 1', 'text': 'Rarity: Rare\nTest Ring\nGold Ring\n--------\n+50 to maximum Life'}]}):
        body = {'buildId': build['id'], 'changes': changes, 'idempotencyKey': str(uuid4())}
        job = packet(a.post('/poe2/jobs', json=body), 202)
        assert packet(a.post('/poe2/jobs', json=body), 202)['id'] == job['id']
        for _ in range(45):
            job = packet(a.get('/poe2/jobs/' + job['id']))
            if job['status'] in ('succeeded', 'failed'): break
            time.sleep(1)
        assert job['status'] == 'succeeded', job.get('errorCode')
        assert job['result']['stats']['Life'] > 0 and job['errorCode'] is None
        jobs.append(job)
    comparison = packet(a.post('/poe2/compare', json={'jobIds': [j['id'] for j in jobs]}))
    assert comparison['metrics']['Life']['delta'] > 0
    exported = packet(a.get('/poe2/builds/' + build['id'] + '/export'))
    assert exported['exportCode']
    for path in ('/poe2/builds/' + build['id'], '/poe2/builds/' + build['id'] + '/export', '/poe2/jobs/' + jobs[0]['id']):
        assert b.get(path).status_code == 404
    assert b.post('/poe2/jobs', json={'buildId': build['id'], 'idempotencyKey': str(uuid4())}).status_code == 404
    conversations = {}
    for game in ('wow', 'poe2'):
        conv = packet(a.post('/chat/conversations', json={'game': game, 'title': game + ' 云端验证'}, headers={'Idempotency-Key': str(uuid4())}), 201)
        conversations[game] = conv['id']
        assert conv['game'] == game
    for game in conversations:
        history = packet(a.get('/chat/conversations', params={'game': game}))['items']
        assert history and all(c['game'] == game for c in history)
        assert b.get('/chat/conversations/' + conversations[game]).status_code == 404
    link = packet(a.post('/poe2/crafting/import-link', json={'itemText': 'Rarity: Rare\nTest Ring\nGold Ring'}))
    assert link['verifiedProbability'] is False and 'eimport=' in link['url']
    report = {'scope': 'synthetic sessions; live API and worker; login credentials not exercised',
        'buildId': build['id'], 'jobs': jobs, 'comparison': comparison, 'conversations': conversations,
        'ownerIsolation': True, 'idempotency': True, 'engineVersion': jobs[0]['result']['engineVersion']}
    (PRIVATE / 'api-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('jobs', 'comparison')}, ensure_ascii=False))


def chat_smoke():
    rows = json.loads((PRIVATE / 'sessions.json').read_text())
    report = json.loads((PRIVATE / 'api-smoke.json').read_text())
    a = client(rows['A'])
    conv = report['conversations']['poe2']
    prompts = [
        '请搜索 POE2 官方论坛和 PoE2DB，简要解释能量护盾与生命的区别，附来源链接及适用版本；不要使用魔兽工具。',
        '请使用工具列出我的已导入 POE2 构筑，再读取第一个构筑的摘要，告诉我其等级和职业。不要重新导入或编造属性。',
    ]
    for i, prompt in enumerate(prompts):
        response = a.post('/chat/conversations/' + conv + '/messages/stream',
            json={'content': prompt, 'clientMessageId': str(uuid4())}, headers={'Idempotency-Key': str(uuid4())}, timeout=520)
        assert response.status_code == 200, (response.status_code, response.text[:500])
        text = response.text
        (PRIVATE / f'chat-{i}.sse').write_text(text)
        assert 'event: completed' in text or '"type":"completed"' in text or '"type": "completed"' in text, text[-1500:]
        print(f'chat-{i}: completed bytes={len(text.encode())}', flush=True)
    detail = packet(a.get('/chat/conversations/' + conv, params={'includeProgress': 'true'}))
    (PRIVATE / 'chat-detail.json').write_text(json.dumps(detail, ensure_ascii=False, indent=2))


def chat_compare():
    rows = sessions()
    a = client(rows['A'])
    conv = packet(a.post('/chat/conversations', json={'game': 'poe2', 'title': '真实工具比较验收'},
        headers={'Idempotency-Key': str(uuid4())}), 201)['id']
    prompt = ('请用我账号中第一个构筑，实际计算原始基线和以下换装方案，等待两个任务完成后调用比较工具，'
        '给出生命和DPS差异并注明计算条件。只比较这一组，无需搜索或重新导入。装备放Ring 1：\n'
        'Rarity: Rare\nTest Ring\nGold Ring\n--------\n+50 to maximum Life')
    response = a.post('/chat/conversations/' + conv + '/messages/stream', json={
        'content': prompt, 'clientMessageId': str(uuid4())}, headers={'Idempotency-Key': str(uuid4())}, timeout=520)
    assert response.status_code == 200, (response.status_code, response.text[:500])
    (PRIVATE / 'chat-compare.sse').write_text(response.text)
    assert 'event: completed' in response.text or '"type":"completed"' in response.text
    detail = packet(a.get('/chat/conversations/' + conv, params={'includeProgress': 'true'}))
    (PRIVATE / 'chat-compare-detail.json').write_text(json.dumps(detail, ensure_ascii=False, indent=2))
    print('chat compare completed', conv)


if __name__ == '__main__':
    if sys.argv[1:] == ['api']: api_smoke()
    elif sys.argv[1:] == ['chat']: chat_smoke()
    elif sys.argv[1:] == ['chat-compare']: chat_compare()
    else: raise SystemExit('api|chat|chat-compare required')

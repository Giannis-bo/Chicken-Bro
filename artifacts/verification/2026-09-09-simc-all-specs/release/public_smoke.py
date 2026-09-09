"""Production HTTP smoke with fresh synthetic owners and revoked sessions."""
import atexit, hashlib, json, os, re, secrets, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4
import httpx, psycopg

pid = subprocess.check_output(['systemctl','show','chickenbro-api','-p','MainPID','--value'],text=True).strip()
env = dict(v.split('=',1) for v in Path('/proc/'+pid+'/environ').read_text().split('\0') if '=' in v)
assert env['WOW_SIMC_SUPPORTED_SPECS'] == 'all'
os.environ.update(env)
sys.path.insert(0,'/opt/chickenbro')
from server.app.simulation.sources import HttpxSourceGateway
owner, other = uuid4(), uuid4()
token, other_token, csrf = (secrets.token_urlsafe(32) for _ in range(3))
with psycopg.connect(env['WOW_DATABASE_URL']) as conn:
    for uid,tok in [(owner,token),(other,other_token)]:
        conn.execute('INSERT INTO identity.users(id) VALUES (%s)',(uid,))
        conn.execute("INSERT INTO identity.user_identities(id,user_id,provider,app_context,provider_subject) VALUES (%s,%s,'qq',%s,%s)",(uuid4(),uid,env['WOW_QQ_APPID'],'simc-all-smoke-'+uuid4().hex))
        conn.execute("INSERT INTO identity.auth_sessions(token_hash,user_id,kind,expires_at) VALUES (%s,%s,'web_cookie',%s)",(hashlib.sha256(tok.encode()).hexdigest(),uid,datetime.now(timezone.utc)+timedelta(minutes=30)))
def revoke():
    with psycopg.connect(env['WOW_DATABASE_URL']) as conn:
        conn.execute('UPDATE identity.auth_sessions SET revoked_at=now() WHERE user_id IN (%s,%s)',(owner,other))
atexit.register(revoke)
headers={'Cookie':f'__Host-chickenbro-session={token}; __Host-chickenbro-csrf={csrf}','Origin':'https://www.chickenbro.cloud','X-CSRF-Token':csrf}
other_headers={'Cookie':'__Host-chickenbro-session='+other_token}
checks={}
with httpx.Client(base_url='https://www.chickenbro.cloud',timeout=120) as client:
    def request(method,path,status=200,**kwargs):
        response=client.request(method,'/api/v2/simc'+path,headers=kwargs.pop('headers',headers),**kwargs)
        assert response.status_code==status,(method,path,response.status_code,response.text[:500])
        return response.json()
    source=request('POST','/snapshots?view=workbench',201,json={'sourceUrl':'https://raider.io/cn/characters/cn/the-masters-glaive/魔魔糊胡萝卜'})
    assert source['readiness']=='READY_FOR_SIMC' and not source['blockers'],source
    assert source['character']['specialization']=='feral'
    print(json.dumps({'step':'source','snapshot':source},ensure_ascii=False),flush=True)
    request('GET','/snapshots/'+source['id'],404,headers=other_headers)
    key='simc-all-'+uuid4().hex
    body={'snapshotId':source['id'],'scenario':{'iterations':100,'maxTime':60,'fightStyle':'Patchwerk','desiredTargets':1}}
    job=request('POST','/jobs',202,json=body,headers={**headers,'Idempotency-Key':key})
    again=request('POST','/jobs',202,json=body,headers={**headers,'Idempotency-Key':key})
    assert again['id']==job['id']
    request('GET','/jobs/'+job['id'],404,headers=other_headers)
    assert request('GET','/jobs',headers=other_headers)['items']==[]
    checks['sourceJobIsolationAndIdempotency']=True
    print(json.dumps({'step':'queued','jobId':job['id']}),flush=True)
    deadline=time.monotonic()+600
    while time.monotonic()<deadline:
        detail=request('GET','/jobs/'+job['id']+'?view=workbench')
        if detail['status']=='succeeded': break
        assert detail['status'] in ('queued','running'),detail
        time.sleep(2)
    assert detail['status']=='succeeded',detail
    result=detail['result']
    assert result['metricName']=='dps' and result['metricValue']>0 and result['report']
    provenance=result['provenance']
    assert provenance['snapshotId']==source['id'] and provenance['profileSha256']==result['profileSha256']
    assert result['runtimeRevision']==detail['runtimeRevision']
    checks['realQueueWorkerPersistedReport']=True
    print(json.dumps({'step':'succeeded','jobId':job['id'],'metric':result['metricValue'],'provenance':provenance},ensure_ascii=False),flush=True)
    gateway=HttpxSourceGateway()
    affixes=gateway.fetch_json('https://raider.io/api/v1/mythic-plus/affixes?region=us&locale=en')
    season=re.search(r'/mythic-plus-affix-rankings/([^/]+)/',affixes['leaderboard_url'])[1]
    ranked=gateway.fetch_json('https://raider.io/api/mythic-plus/rankings/specs?'+urlencode({'region':'world','season':season,'class':'druid','spec':'restoration','page':0}))
    healer=None
    for row in ranked['rankings']['rankedCharacters'][:5]:
        char=row['character']
        url='https://raider.io/characters/'+char['region']['slug']+'/'+char['realm']['slug']+'/'+char['name']
        candidate=request('POST','/snapshots?view=workbench',201,json={'sourceUrl':url})
        if candidate['character']['specialization']=='restoration':
            healer=candidate
            break
    assert healer and 'HEALER_SPEC_UNSUPPORTED' in healer['blockers'],healer
    rejected=request('POST','/jobs',409,json={'snapshotId':healer['id'],'scenario':{'iterations':100}},headers={**headers,'Idempotency-Key':'healer-'+uuid4().hex})
    assert rejected['error']['code']=='SNAPSHOT_NOT_READY',rejected
    with psycopg.connect(env['WOW_DATABASE_URL']) as conn:
        assert conn.execute('SELECT count(*) FROM simc.simulation_jobs WHERE snapshot_id=%s',(healer['id'],)).fetchone()[0]==0
    checks['healerExplicitlyRejectedWithoutJob']=True
    print(json.dumps({'step':'healer','snapshot':healer,'rejection':rejected},ensure_ascii=False),flush=True)
revoke()
print(json.dumps({'passed':True,'checks':checks,'owner':str(owner),'other':str(other),'sessionsRevoked':True}),flush=True)

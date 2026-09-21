"""Cloud-only Task6 live Cookie/CSRF and real collector acceptance; sanitized output."""
import json
import time
from uuid import uuid4
from tests.poe2_candidate_smoke import ROOT, PRIVATE, sessions, client
OUT = ROOT / 'evidence/task6'
NINJA = 'https://poe.ninja/poe2/profile/task6/Standard/character/UserSupplied'
def checked(r, codes=(200,201,202)):
    assert r.status_code in codes, ('HTTP', r.status_code)
    return r.json()
def main():
    rows = sessions(); a,b = client(rows['A']),client(rows['B'])
    checked(a.get('/me'))
    body={'provider':'ninja','url':NINJA,'idempotencyKey':str(uuid4())}
    assert a.post('/poe2/imports',json=body,headers={'X-CSRF-Token':'invalid'}).status_code==403
    for provider,url in [('wegame',NINJA),('ninja','https://www.wegame.com.cn/helper/poe2/#/share/fixture')]:
        r=a.post('/poe2/imports',json={'provider':provider,'url':url,'idempotencyKey':str(uuid4())})
        assert r.status_code==422, r.status_code
        assert 'POE2_SOURCE_PROVIDER_MISMATCH' in r.text
    n=checked(a.post('/poe2/imports',json=body)); assert n['status']=='needs_input'
    assert checked(a.post('/poe2/imports',json=body))['id']==n['id']
    assert b.get('/poe2/imports/'+n['id']).status_code==404
    assert b.post('/poe2/imports/'+n['id']+'/cancel',json={}).status_code==404
    assert b.post('/poe2/imports/'+n['id']+'/source',json={'source':'invalid','idempotencyKey':str(uuid4())}).status_code==404
    cancelled=checked(a.post('/poe2/imports/'+n['id']+'/cancel',json={}))
    assert cancelled['status']=='cancelled'
    w=checked(a.post('/poe2/imports',json={'provider':'wegame','url':(PRIVATE/'task6-wegame-url.txt').read_text().strip(),'idempotencyKey':str(uuid4())}))
    (OUT/'wegame-id.txt').write_text(w['id'])
    for _ in range(100):
        w=checked(a.get('/poe2/imports/'+w['id']))
        if w['status'] not in ('queued','fetching','mapping','validating'): break
        time.sleep(1)
    assert w['status']=='needs_input', w['status']
    assert any('JEWEL' in i['code'] for i in w['issues'])
    assert w['preview'] and w['buildId'] is None and w['baselineJobId'] is None
    report={'passed':True,'auth':'issued A/B real web_cookie sessions; QQ login not exercised','csrfRejection':True,'providerMismatch':True,'ownerReadCancelSource404':True,'createIdempotency':True,'cancelledImportId':n['id'],'wegame':{'id':w['id'],'status':w['status'],'preview':w['preview'],'issueCodes':sorted(set(i['code'] for i in w['issues'])),'issueCount':len(w['issues']),'buildId':w['buildId'],'baselineJobId':w['baselineJobId']}}
    (OUT/'api.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)); print(json.dumps({'passed':True,'wegameStatus':w['status'],'issueCount':len(w['issues'])}))
if __name__=='__main__': main()

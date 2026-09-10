"""Check each existing public Web artifact against the frozen release manifest."""
import concurrent.futures,hashlib,json,sys
from pathlib import Path
from urllib.request import Request,urlopen
m=json.loads(Path(sys.argv[1]).read_text())
def check(item):
    name,expected=item
    request=Request('https://www.chickenbro.cloud/'+name,headers={'Cache-Control':'no-cache'})
    with urlopen(request,timeout=30) as response:
        data=response.read();status=response.status
    actual=hashlib.sha256(data).hexdigest()
    assert status==200 and actual==expected,'public Web mismatch: '+name
    return name,actual
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    hashes=dict(pool.map(check,m['webFiles'].items()))
print(json.dumps({'passed':True,'publicFiles':len(hashes),'hashes':hashes,'unchangedWeb':m['expectedWeb']},indent=2))

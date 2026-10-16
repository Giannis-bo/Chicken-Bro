"""Verify pinned public assets, effective runtime and bounded post-release health."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

from deploy import Release,require,sha
packet=Path(__file__).resolve().parent
release=Release(packet/'manifest.json')
release.runtime()
release.verify(release.target)
origin='https://www.chickenbro.cloud'
assets=[]
for name,expected in release.m['newWebFiles'].items():
 with urlopen(origin+'/'+name,timeout=15) as response:
  actual=hashlib.sha256(response.read()).hexdigest()
  require(actual==expected,'public asset hash differs: '+name)
  assets.append(name)
with urlopen(origin+'/simc',timeout=15) as response:
 require(hashlib.sha256(response.read()).hexdigest()==release.m['newWebFiles']['index.html'],'public SimC entry differs')
samples=[]
# Fixed acceptance: ten ready responses <=2 seconds, five seconds apart.
for n in range(10):
 started=time.monotonic()
 with urlopen('http://127.0.0.1:8790/api/v2/health/readiness',timeout=2) as response:
  status=json.load(response)
 elapsed=time.monotonic()-started
 require(status['status']=='ready' and elapsed<2,'post-release health acceptance failed')
 samples.append({'status':status['status'],'seconds':round(elapsed,3)})
 if n<9:time.sleep(5)
since=int((packet/'promote-result.json').stat().st_mtime)
journal=subprocess.check_output(['journalctl','-u','chickenbro-api','-u','chickenbro-worker','--since','@'+str(since),'-p','err','--no-pager','-o','cat'],text=True)
lines=[line for line in journal.splitlines() if line.strip() and line.strip()!='-- No entries --']
require(not lines,'service error journal requires investigation')
result={'passed':True,'releaseId':release.m['releaseId'],'manifestSha256':sha(packet/'manifest.json'),
 'publicOrigin':origin,'publicAssetsMatched':assets,'simcEntryMatched':True,'effectiveConfigurationMatched':True,
 'backendInventoryMatched':True,'workerApiCwdMatched':True,'enginePathUnchanged':release.m['enginePath'],
 'healthThreshold':{'samples':10,'maxSeconds':2,'intervalSeconds':5},'healthSamples':samples,'serviceErrorEntries':len(lines)}
(packet/'live-runtime.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'publicAssets':len(assets),'readySamples':len(samples),'maxLatency':max(x['seconds'] for x in samples),'serviceErrors':len(lines)}))

"""Build an exact source/asset manifest without changing live pointers or schema."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from deploy import FILES, Release, base, inventory, require, sha

os.umask(0o077)
source = Path('/opt/chickenbro-candidates/simc-character-bindings-20261016')
packet = Path(__file__).resolve().parent
require(packet == Path('/var/lib/chickenbro-simc-characters-release-20261016'), 'private packet location differs')
require(packet.stat().st_uid == 0 and packet.stat().st_mode & 0o777 == 0o700, 'private packet mode differs')
old_backend,old_web = Path('/opt/chickenbro').resolve(),Path('/var/www/chickenbro-web/current').resolve()
require(old_backend.name == 'simc-repaired-20261016-128530c9797bdcbf6bd24af86ec2b29d9ec57af0', 'unexpected backend')
require(old_web.name == 'changelog-8682f05fed6657b3354db7a8d2bfb29914c8f21b', 'unexpected Web')
expected = json.loads((packet/'base-source-hashes.json').read_text())
old_inventory = inventory(old_backend)
for name,expected_hash in expected['files'].items():
    require(old_inventory.get(name) == expected_hash, 'deployed base differs from Git base: '+name)
overlay=packet/'overlay'
overlay.mkdir(exist_ok=True)
for name in FILES:
    dest=overlay/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source/name,dest)
web=source/'apps/mini-taro/dist/h5'
files,new_web=inventory(overlay),inventory(web)
identity=hashlib.sha256(json.dumps({'files':files,'web':new_web},sort_keys=True).encode()).hexdigest()
name='simc-characters-20261016-'+identity[:16]
envs={unit:base.environment(unit) for unit in base.UNITS}
require(envs['chickenbro-api']['WOW_DATABASE_URL'] == envs['chickenbro-worker']['WOW_DATABASE_URL'], 'service DB mismatch')
private=packet/'service-environments.json'
if not private.exists():
    private.write_text(json.dumps(envs));private.chmod(0o600)
else: require({k:base.env_digest(v) for k,v in json.loads(private.read_text()).items()} == {k:base.env_digest(v) for k,v in envs.items()}, 'captured configuration changed')
manifest={'sourceCommit':expected['baseCommit'],'sourceUncommitted':True,'releaseId':identity,
    'expectedBackend':str(old_backend),'expectedWeb':str(old_web),
    'targetBackend':'/opt/chickenbro-releases/'+name,'targetWeb':'/var/www/chickenbro-web/releases/'+name,
    'baseInventory':old_inventory,'files':files,'baseHashes':expected['files'],
    'webFiles':inventory(old_web),'newWebFiles':new_web,
    'environmentHashes':{unit:base.env_digest(env) for unit,env in envs.items()},
    'enginePath':str(Path('/opt/wow-simc/current').resolve()),
    'compilerRevision':envs['chickenbro-api'].get('WOW_SIMC_COMPILER_REVISION','')}
path=packet/'manifest.json'
if path.exists():require(json.loads(path.read_text()) == manifest,'existing release manifest differs')
else:path.write_text(json.dumps(manifest,indent=2)+'\n')
release=Release(path)
release.stage()
release.runtime()
with release.connect() as connection:
    require(connection.execute('SELECT current_database()').fetchone()[0] == 'chickenbro_prod','wrong production database')
print(json.dumps({'prepared':True,'releaseId':identity,'backendOverlayFiles':len(files),'WebFiles':len(new_web),
    'backend':manifest['targetBackend'],'web':manifest['targetWeb'],'livePointersChanged':False,'manifestSha256':sha(path)}))

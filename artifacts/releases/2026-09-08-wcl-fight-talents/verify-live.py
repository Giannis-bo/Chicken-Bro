"""Run only in the isolated cloud verification directory, never as a service."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'code'))
for line in Path('/etc/chickenbro-source.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        if key.startswith(('WOW_WARCRAFTLOGS_', 'WOW_BLIZZARD_', 'WOW_BATTLENET_')):
            os.environ[key] = value.strip('"\'')
from server.app.simulation.sources import WclCharacterAdapter, HttpxSourceGateway, parse_character_source_url
from server.app.integrations.warcraftlogs import warcraftlogs_oauth_token
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities, inspect_managed_simc_runtime
from server.app.simulation.compiler import SimcProfileCompiler

identity = inspect_managed_simc_runtime({})
cap = SimcRuntimeCapabilities(identity.runtime_revision, 'chickenbro-simc-compiler-v3', frozenset({('shaman', 'elemental')}))
c = WclCharacterAdapter(HttpxSourceGateway(), token_provider=warcraftlogs_oauth_token).resolve(
    parse_character_source_url('https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4'))
assert not c.missing_fields, c.missing_fields
assert c.provenance['wclTalentReconstruction']['catalogRuntimeRevision'] == identity.source_commit
saved = c.to_source_snapshot(user_id='00000000-0000-4000-8000-000000000001',
    snapshot_id='00000000-0000-4000-8000-000000000002',
    readiness_report=SimcReadinessValidator().validate(c, cap))
compiled = SimcProfileCompiler(capabilities=cap).compile(saved, {'iterations':100,'maxTime':60})
(root/'live-isolated.simc').write_text(compiled.profile)
with (root/'live-isolated.log').open('w') as output:
    result = subprocess.run([str(identity.binary_path), 'live-isolated.simc', 'json2=live-isolated.json', 'threads=1'],
        cwd=root, stdout=output, stderr=subprocess.STDOUT, timeout=120)
assert result.returncode == 0
report = json.loads((root/'live-isolated.json').read_text())
actor = report['sim']['players'][0]
dps = actor['collected_data']['dps']['mean']
assert dps > 0 and actor['talents'] == c.snapshot['talents']['string']
proof = {'status':'isolated_live_source_and_cloud_simc_verified','productionChanged':False,
    'databaseWrites':False, 'runtimeRevision':identity.runtime_revision, 'sourceCommit':identity.source_commit,
    'binarySha256':identity.binary_sha256, 'profileSha256':compiled.profile_sha256,
    'reportSha256':hashlib.sha256((root/'live-isolated.json').read_bytes()).hexdigest(),
    'missingFields':c.missing_fields,'dps':dps,'talents':actor['talents'],'provenance':c.provenance}
(root/'live-isolated-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:proof[k] for k in ['status','productionChanged','databaseWrites','runtimeRevision','dps']},ensure_ascii=False))

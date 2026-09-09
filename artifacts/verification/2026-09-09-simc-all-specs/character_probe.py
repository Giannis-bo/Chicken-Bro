"""Read the reported character and simulate in memory; no business DB writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, os.environ.get('CHICKENBRO_PROBE_ROOT', '/opt/chickenbro'))
from server.app.simulation.sources import RaiderIOCharacterAdapter, HttpxSourceGateway, parse_character_source_url
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.worker import LocalSimulationCraftPort, SimulationResultParser

pid = subprocess.check_output(['systemctl', 'show', 'chickenbro-api', '-p', 'MainPID', '--value'], text=True).strip()
env = dict(entry.split('=', 1) for entry in Path('/proc/' + pid + '/environ').read_text().split('\0') if '=' in entry)
os.environ.update(env)
caps = SimcRuntimeCapabilities.from_env({**dict(os.environ), 'WOW_SIMC_SUPPORTED_SPECS': 'all'})
url = 'https://raider.io/cn/characters/cn/the-masters-glaive/魔魔糊胡萝卜'
candidate = RaiderIOCharacterAdapter(HttpxSourceGateway()).resolve(parse_character_source_url(url))
report = SimcReadinessValidator().validate(candidate, caps)
print(json.dumps({'character': candidate.snapshot.get('character'), 'readiness': report.readiness.value, 'blockers': report.blockers}, ensure_ascii=False), flush=True)
snapshot = candidate.to_source_snapshot(user_id='00000000-0000-4000-8000-000000000001', snapshot_id='00000000-0000-4000-8000-000000000002', readiness_report=report)
compiled = SimcProfileCompiler(capabilities=caps).compile(snapshot, {'iterations': 100, 'maxTime': 60})
execution = LocalSimulationCraftPort(runtime_revision=caps.runtime_revision).run(compiled, caps.runtime_revision)
try:
    metric = SimulationResultParser().parse(execution, expected_actor=compiled.actor_name)
    print(json.dumps({'status': 'passed', 'metric': metric.name, 'value': metric.value, 'runtime': caps.runtime_revision, 'profileSha256': compiled.profile_sha256, 'sourceRawSha256': candidate.raw_sha256}), flush=True)
except Exception as error:
    print(json.dumps({'status': 'failed', 'error': str(error), 'diagnostic': execution.stderr + execution.stdout[-1500:]}), flush=True)
    raise

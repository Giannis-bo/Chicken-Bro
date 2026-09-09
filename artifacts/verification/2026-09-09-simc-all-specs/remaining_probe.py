"""Cloud-only real-source discovery for specs with obsolete official fixtures."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode
sys.path.insert(0, os.environ.get('CHICKENBRO_PROBE_ROOT', '/opt/chickenbro'))
from server.app.simulation.sources import HttpxSourceGateway, RaiderIOCharacterAdapter, parse_character_source_url
from server.app.simulation.readiness import SimcReadinessValidator, SimcRuntimeCapabilities
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.worker import LocalSimulationCraftPort, SimulationResultParser

pid = subprocess.check_output(['systemctl', 'show', 'chickenbro-api', '-p', 'MainPID', '--value'], text=True).strip()
os.environ.update(dict(entry.split('=', 1) for entry in Path('/proc/' + pid + '/environ').read_text().split('\0') if '=' in entry))
gateway = HttpxSourceGateway()
affixes = gateway.fetch_json('https://raider.io/api/v1/mythic-plus/affixes?region=us&locale=en')
season = re.search(r'/mythic-plus-affix-rankings/([^/]+)/', affixes['leaderboard_url'])[1]
caps = SimcRuntimeCapabilities.from_env()
caps = SimcRuntimeCapabilities(caps.runtime_revision, caps.compiler_revision, frozenset({('*', '*')}))
for klass, spec in [('demon-hunter', 'havoc'), ('paladin', 'retribution'), ('warrior', 'arms'), ('warrior', 'fury'), ('warrior', 'protection'), ('evoker', 'augmentation')]:
    try:
        payload = gateway.fetch_json('https://raider.io/api/mythic-plus/rankings/specs?' + urlencode({'region': 'world', 'season': season, 'class': klass, 'spec': spec, 'page': 0}))
        rows = payload.get('rankings', {}).get('rankedCharacters', [])
        print(json.dumps({'spec': klass + ':' + spec, 'season': season, 'rankedCount': len(rows)}), flush=True)
        for row in rows[:3]:
            char = row['character']
            region = char['region']['slug']
            realm = char['realm']['slug']
            url = 'https://raider.io/characters/' + region + '/' + realm + '/' + char['name']
            candidate = RaiderIOCharacterAdapter(gateway).resolve(parse_character_source_url(url))
            report = SimcReadinessValidator().validate(candidate, caps)
            actual = candidate.snapshot.get('character', {})
            output = {'spec': klass + ':' + spec, 'url': url, 'actual': actual, 'blockers': report.blockers}
            if actual.get('specKey') != spec or not report.ready:
                print(json.dumps(output, ensure_ascii=False), flush=True)
                continue
            snapshot = candidate.to_source_snapshot(user_id='00000000-0000-4000-8000-000000000001', snapshot_id='00000000-0000-4000-8000-000000000002', readiness_report=report)
            compiled = SimcProfileCompiler(capabilities=caps).compile(snapshot, {'iterations': 100, 'maxTime': 60})
            execution = LocalSimulationCraftPort(runtime_revision=caps.runtime_revision).run(compiled, caps.runtime_revision)
            try:
                metric = SimulationResultParser().parse(execution, expected_actor=compiled.actor_name)
                output.update(status='passed', metric=metric.name, value=metric.value, profileSha256=compiled.profile_sha256, sourceRawSha256=candidate.raw_sha256)
                print(json.dumps(output, ensure_ascii=False), flush=True)
                break
            except Exception as error:
                output.update(status='failed', error=str(error), diagnostic=(execution.stderr + execution.stdout)[-1500:])
                print(json.dumps(output, ensure_ascii=False), flush=True)
    except Exception as error:
        print(json.dumps({'spec': klass + ':' + spec, 'status': 'unavailable', 'errorType': type(error).__name__, 'errorCode': getattr(error, 'code', '')}), flush=True)

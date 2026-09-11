"""Bounded cloud-only experiment; no app/database writes or engine changes."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

os.umask(0o077)
ROOT = Path('/var/lib/chickenbro-trinket-mechanism-20260911')
ENGINE = Path('/opt/wow-simc/current/simc')
EXPECTED_BINARY = '69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da'
EXPECTED_PROFILE = 'f4ef3fbf09378a1b508c9559d39249f659008b7e6a26ef93ba18efe59e00ddb2'
OVERRIDE = 'override.spell_data=effect.1254615.coefficient=0'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n')

with open('/run/lock/chickenbro-candidate-validation.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert digest(ENGINE.read_bytes()) == EXPECTED_BINARY
    ROOT.mkdir(mode=0o700, exist_ok=True)
    assert (ROOT / 'started.json').exists()
    assert not (ROOT / 'baseline-started.json').exists(), 'Never rerun an attempted combat case'
    original = Path('/var/lib/chickenbro-simc-accuracy-20260911/profile-private.simc').read_text()
    baseline = original.replace('ilevel=289', 'ilevel=298').replace('iterations=100\n', 'iterations=10000\n').replace('max_time=20\n', 'max_time=300\n')
    baseline += 'optimal_raid=1\noverride.bloodlust=1\n'
    assert digest(baseline.encode()) == EXPECTED_PROFILE
    assert 'spec=elemental' in baseline and 'vary_combat_length=0' in baseline
    assert 'trinket1=,id=249343,ilevel=298' in baseline
    assert 'trinket2=,id=250144,ilevel=298' in baseline
    write('continuation.json', {'reason': 'Initial query assertion expected explicit coefficient=0; engine omits zero coefficient. No combat ran. Reuse unchanged query output.', 'at': time.time()})
    query_text = (ROOT / 'zero-penalty-spell-query.txt').read_text()
    effect2 = query_text.split('#2 (id=1254615)', 1)[1].split('Description', 1)[0]
    assert 'Base Value: 0 | Scaled Value: 0 |' in effect2
    assert 'coefficient=3.405735' in query_text.split('#2', 1)[0]
    result = {'binarySha256': EXPECTED_BINARY, 'baseProfileSha256': EXPECTED_PROFILE, 'zeroPenaltyQueryVerified': True, 'cases': [], 'scope': 'isolated direct engine experiment, not product submission or live user acceptance'}
    for label, prefix in [('baseline', ''), ('zero-penalty', OVERRIDE + '\n')]:
        profile = prefix + baseline
        assert profile.removeprefix(prefix) == baseline
        input_path = ROOT / (label + '-private.simc')
        output_path = ROOT / (label + '-private.json')
        input_path.write_text(profile)
        write(label + '-started.json', {'at': time.time(), 'inputSha256': digest(profile.encode())})
        begin = time.monotonic()
        run = subprocess.run(['/usr/bin/nice', '-n', '10', str(ENGINE), str(input_path), 'threads=1', 'seed=20260911', 'json2=' + str(output_path)], capture_output=True, timeout=120)
        (ROOT / (label + '-private.log')).write_bytes(run.stdout + run.stderr)
        assert run.returncode == 0, 'Engine failure: inspect private log'
        report = json.loads(output_path.read_text())
        sim = report['sim']; player = sim['players'][0]
        metric = player['collected_data']['dps']
        assert metric['mean'] > 0 and metric['count'] >= 9900
        assert sim['options']['iterations'] == 10000
        gear = player['gear']
        for slot, item in [('trinket1', 249343), ('trinket2', 250144)]:
            assert gear[slot]['ilevel'] == 298 and f'id={item}' in gear[slot]['encoded_item']
        buffs = [{k: b.get(k) for k in ('name', 'spell', 'uptime', 'start_count', 'duration')} for b in player['buffs'] if b['name'].startswith(('emberwing', 'alns'))]
        entry = {'name': label, 'dps': metric['mean'], 'meanStdDev': metric['mean_std_dev'], 'count': metric['count'], 'elapsedSeconds': time.monotonic() - begin, 'profileSha256': digest(profile.encode()), 'reportSha256': digest(output_path.read_bytes()), 'gear': {slot: gear[slot] for slot in ('trinket1', 'trinket2')}, 'buffs': buffs, 'options': {k: sim['options'].get(k) for k in ('iterations', 'max_time', 'vary_combat_length', 'fixed_time', 'desired_targets', 'seed', 'confidence')}, 'diagnosticLevels': [x.get('level') for x in report.get('logs', [])]}
        result['cases'].append(entry)
        write('result.json', result)
        print(json.dumps({'case': label, 'dps': entry['dps'], 'elapsedSeconds': entry['elapsedSeconds']}), flush=True)
    assert digest(ENGINE.read_bytes()) == EXPECTED_BINARY
    result['finished'] = True
    result['combatSimulations'] = 2
    result['totalEngineInvocationsIncludingInspection'] = 4
    write('result.json', result)

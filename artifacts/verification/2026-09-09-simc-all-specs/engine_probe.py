"""Cloud-only probe using the installed engine and its retained source archive.

Official profiles are engine fixtures, never user snapshots or business results.
"""
import hashlib
import json
import re
import sys
import tarfile
from types import SimpleNamespace

sys.path.insert(0, '/opt/chickenbro')
from server.app.simulation.readiness import inspect_managed_simc_runtime
from server.app.simulation.worker import LocalSimulationCraftPort, SimulationResultParser

identity = inspect_managed_simc_runtime()
print(json.dumps({'runtime': identity.runtime_revision}), flush=True)
profiles = {}
with tarfile.open('/opt/wow-simc/source-' + identity.source_commit + '.tar.gz') as archive:
    for member in sorted(archive.getmembers(), key=lambda m: ("/profiles/MID2/" not in m.name, m.name)):
        if not re.search(r'/profiles/MID[12]/MID[12]_', member.name) or not member.name.endswith('.simc'):
            continue
        text = archive.extractfile(member).read().decode()
        actors = re.findall(r'^(deathknight|demonhunter|druid|evoker|hunter|mage|monk|paladin|priest|rogue|shaman|warlock|warrior)="([^"]+)"', text, re.M)
        specs = re.findall(r'^spec=(\w+)', text, re.M)
        if len(actors) != 1 or len(specs) != 1:
            continue
        key = (actors[0][0], specs[0])
        if key in profiles:
            continue
        # Match the product's default APL: identity, talents and equipment only.
        keys = {key[0], 'spec', 'race', 'level', 'talents', 'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist', 'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand'}
        profile = '\n'.join(line for line in text.splitlines() if line.split('=', 1)[0] in keys)
        profiles[key] = (actors[0][1], profile, member.name)

runner = LocalSimulationCraftPort(runtime_revision=identity.runtime_revision, timeout_seconds=90)
for (klass, spec), (actor, profile, source) in sorted(profiles.items()):
    profile += '\niterations=100\nmax_time=60\nfixed_time=1\nvary_combat_length=0\nfight_style=Patchwerk\ndesired_targets=1\nthreads=1\n'
    row = {'class': klass, 'spec': spec, 'source': source, 'profileSha256': hashlib.sha256(profile.encode()).hexdigest()}
    try:
        execution = runner.run(SimpleNamespace(profile=profile), identity.runtime_revision)
        metric = SimulationResultParser().parse(execution, expected_actor=actor)
        row.update(status='passed', metric=metric.name, value=metric.value)
    except Exception as error:
        row.update(status='failed', error=str(error))
        if 'execution' in locals():
            row['diagnostic'] = (execution.stderr + execution.stdout)[-2000:]
    print(json.dumps(row), flush=True)

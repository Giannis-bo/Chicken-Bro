"""Cloud only: archived public character fixture, two complete APL variants."""
import copy,hashlib,json,re,tarfile
from pathlib import Path
from dataclasses import replace
from tests import app_simulation_compiler_test as fixtures
from server.app.simulation.compiler import SimcProfileCompiler
from server.app.simulation.readiness import inspect_managed_simc_runtime
from server.app.simulation.worker import LocalSimulationCraftPort,SimulationResultParser
from server.app.simulation.effective_config import verify_effective_config
from server.app.simulation.action_lists import extract_action_evidence
identity=inspect_managed_simc_runtime()
fixture=fixtures.SimulationCompilerTest();fixture.setUp()
original=Path('/tmp/chickenbro-experiments-juy810st/fusionbolt-baseline.simc').read_text()
old_report=json.loads(Path('/tmp/chickenbro-experiments-juy810st/fusionbolt-baseline.json').read_text())['sim']['players'][0]
raw=copy.deepcopy(fixture.snapshot.snapshot)
raw['character'].update(name='Fusionbolt',level=90,raceKey='dwarf',region='cn',realm='alar')
raw['talents']={'string':next(line.split('=',1)[1] for line in original.splitlines() if line.startswith('talents='))}
raw['gear']={};raw['gearState']={'unequippedSlots':['off_hand']}
for line in original.splitlines():
 m=re.match(r'([a-z_0-9]+)=,id=(\d+)(.*)',line)
 if not m:continue
 slot=m[1]; fields=dict(re.findall(r',([a-z_]+)=([^,]+)',line))
 raw['gear'][slot]={'itemId':int(m[2]),'itemLevel':int(old_report['gear'][{'shoulder':'shoulders','wrist':'wrists'}.get(slot,slot)]['ilevel']),
   'bonusIds':[int(n) for n in fields.get('bonus_id','').split('/') if n],
   'gems':[int(n) for n in fields.get('gem_id','').split('/') if n],
   'enchant':int(fields['enchant_id']) if fields.get('enchant_id') else None}
snapshot=replace(fixture.snapshot,snapshot=raw,raw_sha256=hashlib.sha256(original.encode()).hexdigest())
caps=replace(fixture.capabilities,compiler_revision='chickenbro-simc-compiler-v6',runtime_revision=identity.runtime_revision)
compiler=SimcProfileCompiler(capabilities=caps)
archive=Path('/opt/wow-simc/source-'+identity.source_commit+'.tar.gz')
with tarfile.open(archive) as t:
 apl=t.extractfile('simc-'+identity.source_commit+'/ActionPriorityLists/default/shaman_elemental.simc').read().decode()
lists={}
for line in apl.splitlines():
 m=re.fullmatch(r'actions(?:\.([a-z_0-9]+))?\+?=(.*)',line)
 if m:lists.setdefault(m[1] or 'default',[]).append(m[2].removeprefix('/'))
for name in lists:
 lists[name]=[a for a in lists[name] if a.split(',',1)[0] not in {'stormkeeper','ascendance'}]
results=[]
for order in ('stormkeeper:ascendance','ascendance:stormkeeper'):
 variant=copy.deepcopy(lists)
 if order=='stormkeeper:ascendance':
  variant['default'][0:0]=['stormkeeper,if=cooldown.ascendance.ready','ascendance,if=buff.stormkeeper.up']
 else:
  variant['default'][0:0]=['ascendance','stormkeeper,if=buff.ascendance.up']
 compiled=compiler.compile(snapshot,{'actionLists':variant,'maxTime':60,'iterations':100,'desiredTargets':1,'varyCombatLength':0})
 execution=LocalSimulationCraftPort(runtime_revision=identity.runtime_revision,timeout_seconds=90).run(compiled,identity.runtime_revision)
 try:metric=SimulationResultParser().parse(execution,expected_actor='Fusionbolt')
 except Exception:
  print(json.dumps({'error':execution.stderr[-1600:],'stdout':execution.stdout[-1600:]}));raise
 proof=verify_effective_config(compiled,metric.report)
 evidence=extract_action_evidence(execution.report_json,'Fusionbolt',compiled.profile_sha256)
 actions=[a for a in evidence['sample'] if a['name'] in {'stormkeeper','ascendance'}]
 assert len(actions)>=2, {'actions':actions,'sample':evidence['sample'][:20]}
 assert ':'.join(a['name'] for a in actions[:2])==order,actions
 assert actions[0]['time']<actions[1]['time'],actions
 Path(order.replace(':','-')+'.simc').write_text(compiled.profile)
 results.append({'order':order,'runtimeRevision':identity.runtime_revision,'compilerRevision':compiled.compiler_revision,
  'profileSha256':compiled.profile_sha256,'scenarioHash':compiled.scenario_hash,'dps':metric.value,'error':metric.error,
  'effectiveConfig':proof,'observedActions':actions,'fixture':'archived public Fusionbolt 2026-09-09; mechanism verification only, not current player recommendation'})
 print(json.dumps(results[-1]),flush=True)
Path('cloud-apl-results.json').write_text(json.dumps(results,indent=2))

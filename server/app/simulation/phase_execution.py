"""Cloud-only phase batches, bounded by one job wall-clock budget."""
import hashlib
import json
import time
from dataclasses import replace
from server.app.simulation.phase_evidence import initial_snapshot, inspect_iteration, aggregate_phase, aggregate_reports
from server.app.simulation.phase_state import number
from server.app.simulation.report import select_report_actor, normalize_simc_report
from server.app.simulation.effective_config import verify_effective_config


def run_phase(port, compiled, runtime_revision):
    from server.app.simulation.worker import SimulationWorkerError
    deadline=time.monotonic()+port._timeout_seconds
    scenario=compiled.scenario
    members=[];reports=[];identities=[];receipts=[];diagnostics=[]
    seed_base=int(compiled.provenance.get('sourceRawSha256','0')[:8] or '0',16) or 20260920

    def execute(profile, index):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise SimulationWorkerError('SIMC_PHASE_TIMEOUT')
        profile+='\niterations=1\nthreads=1\ntarget_error=0\nseed='+str(seed_base+index)+'\n'
        derived=replace(compiled,profile=profile)
        execution=port._run_once(derived,runtime_revision,timeout_seconds=remaining,full_states=True)
        if execution.timed_out or execution.return_code!=0:raise SimulationWorkerError('SIMC_PHASE_EXECUTION_FAILED')
        try:
            raw=json.loads(execution.report_json)
            actor=select_report_actor(raw['sim']['players'],compiled.actor_name)
            identity={}
            report=normalize_simc_report(execution.report_json,expected_actor=compiled.actor_name,npc_sources=execution.npc_sources,
                                         diagnostic_sink=diagnostics,identity_sink=identity)
            verify_effective_config(compiled,report,execution.report_json)
        except (ValueError, KeyError, TypeError):raise SimulationWorkerError('SIMC_PHASE_PREFLIGHT_FAILED') from None
        if report['metric']['name']!='dps':raise SimulationWorkerError('SIMC_PHASE_METRIC_UNSUPPORTED')
        receipts.append({'stage':'discovery' if index==0 else 'measurement','seed':seed_base+index,
                         'profileSha256':hashlib.sha256(profile.encode()).hexdigest(),
                         'reportSha256':hashlib.sha256(execution.report_json.encode() if isinstance(execution.report_json,str) else execution.report_json).hexdigest()})
        return execution,actor,report,identity

    profile=compiled.profile
    if any(v=='max' for v in scenario['initialState']['resources'].values()):
        _,actor,_,_=execute(profile,0)
        try:
            maximum=initial_snapshot(actor)['resources_max']
            resolved={k:number(maximum.get(k),.001,1e7) for k,v in scenario['initialState']['resources'].items() if v=='max'}
        except (ValueError,KeyError,TypeError):raise SimulationWorkerError('SIMC_PHASE_RESOURCE_UNSUPPORTED') from None
        profile+='\n'+'\n'.join(f'initial_resource={k}={v:g}' for k,v in sorted(resolved.items()))+'\n'
    first_execution=None
    for index in range(1,scenario['iterations']+1):
        execution,actor,report,identity=execute(profile,index)
        try:member=inspect_iteration(actor,scenario)
        except (ValueError,KeyError,TypeError,AttributeError):raise SimulationWorkerError('SIMC_PHASE_STATE_MISMATCH') from None
        members.append(member);reports.append(report);identities.append(identity)
        if first_execution is None:first_execution=execution
        # Required effects/order fail before spending the remainder of the batch.
        if member['status']!='satisfied':raise SimulationWorkerError('SIMC_PHASE_ASSERTION_FAILED')
    phase=aggregate_phase(members,scenario,compiled.profile_sha256)
    phase.update(executions=receipts,runtimeRevision=runtime_revision,scenarioHash=compiled.scenario_hash,
                 elapsedSeconds=round(port._timeout_seconds-(deadline-time.monotonic()),3))
    report=aggregate_reports(reports,phase)
    from server.app.simulation.phase_evidence import aggregate_identity
    return replace(first_execution,phase_evidence=phase,phase_report=report,
                   phase_identity=aggregate_identity(identities,report))

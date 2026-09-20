"""Immutable scenario patches and conservative, owner-scoped comparisons."""
from copy import deepcopy
from math import isfinite
from server.app.simulation.compiler import normalize_scenario
from server.app.simulation.application import SimulationApplicationError, validated_simulation_result_provenance
from server.app.simulation.diagnostics import public_engine_diagnostics, engine_diagnostic_limitations

_VARIANT_FIELDS = {'equipmentOverrides', 'gemOverrides', 'talentOverrides', 'actionLists', 'food', 'statBonuses', 'assertions'}

def merge_scenario(base, patch):
    if not isinstance(patch, dict):
        raise ValueError('scenario patch required')
    merged = deepcopy(dict(base)); merged.update(deepcopy(patch))
    for field in ('equipmentOverrides', 'gemOverrides'):
        if field in patch:
            if not isinstance(patch[field], dict): raise ValueError('slot map required')
            merged[field] = {**deepcopy(base.get(field, {})), **deepcopy(patch[field])}
    for slot in patch.get('equipmentOverrides', {}):
        if slot not in patch.get('gemOverrides', {}):
            merged.get('gemOverrides', {}).pop(slot, None)
    if 'talentOverrides' in patch:
        old = base.get('talentOverrides', {}); new = patch['talentOverrides']
        if isinstance(new, dict) and 'nodes' in old and 'nodes' in new:
            # New nodes supersede only the same nodes; preserve earlier edits.
            if not isinstance(new['nodes'], list): raise ValueError('node list required')
            normalized = normalize_scenario({'talentOverrides':new})['talentOverrides']
            nodes = {n['nodeId']:n for n in old['nodes']}
            nodes.update({n['nodeId']:n for n in normalized['nodes']})
            merged['talentOverrides'] = {'nodes':list(nodes.values())}
        elif isinstance(new, dict) and 'string' in old and 'nodes' in new:
            # Caller resolves against the prior effective build, never silently
            # applies a node patch to the initial imported build.
            raise SimulationApplicationError('TALENT_BASE_EXPORT_REQUIRES_RESOLUTION','resolve effective export first')
    return normalize_scenario(merged)

def compare_jobs(baseline, variant):
    a,b = baseline.job,variant.job
    def fail(code): raise SimulationApplicationError(code, code)
    if a.user_id != b.user_id: fail('SIMULATION_NOT_FOUND')
    if a.id == b.id: fail('SIMC_COMPARISON_SAME_JOB')
    if a.status.value != 'succeeded' or b.status.value != 'succeeded' or not baseline.result or not variant.result:
        fail('SIMC_COMPARISON_NOT_READY')
    for view in (baseline, variant): validated_simulation_result_provenance(view)
    if a.snapshot_id != b.snapshot_id: fail('SIMC_COMPARISON_SNAPSHOT_MISMATCH')
    if a.runtime_revision != b.runtime_revision or a.compiler_revision != b.compiler_revision:
        fail('SIMC_COMPARISON_RUNTIME_MISMATCH')
    if baseline.scenario is None or variant.scenario is None: fail('SIMC_BASE_SCENARIO_UNAVAILABLE')
    controls=lambda s:{k:v for k,v in s.items() if k not in _VARIANT_FIELDS}
    if controls(baseline.scenario)!=controls(variant.scenario): fail('SIMC_COMPARISON_CONTROLS_MISMATCH')
    if baseline.result.primary_metric_name != variant.result.primary_metric_name: fail('SIMC_COMPARISON_METRIC_MISMATCH')
    if a.compiler_revision in {'chickenbro-simc-compiler-v5', 'chickenbro-simc-compiler-v6', 'chickenbro-simc-compiler-v7'}:
        for view in (baseline,variant):
            proof=view.result.result.get('effectiveConfig', {})
            if proof.get('status')!='verified' or proof.get('profileSha256')!=view.result.profile_sha256:
                fail('SIMC_EFFECTIVE_CONFIG_MISMATCH')
    if 'measurement' in baseline.scenario:
        for view in (baseline,variant):
            proof=view.result.result.get('phaseEvidence',{})
            if (proof.get('status')!='satisfied' or proof.get('profileSha256')!=view.result.profile_sha256
                    or proof.get('scenarioHash')!=view.job.scenario_hash):fail('SIMC_PHASE_EVIDENCE_MISSING')
    av,bv=baseline.result.primary_metric_value, variant.result.primary_metric_value
    errors=[v.result.result.get('metricError') for v in (baseline,variant)]
    bounded=all(type(e) in (float,int) and isfinite(e) and e>=0 for e in errors)
    margin=sum(errors) if bounded else None
    delta=bv-av
    delta_pct=delta/av*100
    if not isfinite(delta_pct): fail('SIMC_COMPARISON_METRIC_MISMATCH')
    diagnostics = {key: public_engine_diagnostics(view.result.result.get('engineDiagnostics'))
                   for key, view in (('baseline', baseline), ('variant', variant))}
    return {'baselineJobId':str(a.id),'variantJobId':str(b.id),'metricName':baseline.result.primary_metric_name,
            'baseline':av,'variant':bv,'delta':delta,'deltaPct':delta_pct,
            'combinedErrorBound':margin,
            'assessment':('uncertainty_unavailable' if margin is None else 'within_reported_error' if abs(delta)<=margin else 'higher' if delta>0 else 'lower'),
            'changes':{k:{'before':deepcopy(baseline.scenario.get(k)), 'after':deepcopy(variant.scenario.get(k))}
                       for k in sorted(_VARIANT_FIELDS) if baseline.scenario.get(k)!=variant.scenario.get(k)},
            'controls':controls(baseline.scenario),'runtimeRevision':a.runtime_revision,
            'engineDiagnostics': diagnostics,
            'limitations':['Reported error bounds are summed conservatively; this is not a paired statistical significance test.']
                + engine_diagnostic_limitations(diagnostics['baseline'] + diagnostics['variant'])}

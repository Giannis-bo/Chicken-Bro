#!/usr/bin/env python3
"""Build measured generalization evidence; never author or infer human verdicts.

Required verdicts JSON:
  {"review": {"mechanism":..., "root_cause_evidence":..., "applicable_scope":...,
              "excluded_boundaries":..., "anti_case_specialization":{...}},
   "trials": {"before": {"sample_id": {"1": {"criteria": {...}, "notes":..., "receipt_sha256":...}, ...}},
              "after": {...}}}
Criteria are passed/failed/unavailable. Notes must explain the judgment.
Every verdict receipt_sha256 must equal the exact reviewed raw file bytes. All
registered samples/repetitions and all raw JSON files must match exactly.
A complete failing set is written as unverified and exits 2. Missing inputs or
contradictory claims refuse output. Output excludes raw answers and tool traces.
The only optional baseline alias is /opt/chickenbro, with a before/after
identity+inventory proof bracketing every baseline execution.
"""
import argparse
import copy
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location('badcase_workflow', REPO/'scripts/badcase_workflow.py')
w = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w)


def criteria_for(category):
    if category == 'normal': return ['normal','completion']
    if category == 'permission': return ['permission','completion']
    return ['acquisition','analysis','completion']


def summarize(runs):
    costs = [run['cost'] for run in runs]
    total_cost = {'counter_scope':'source_gateway_only', 'tool_calls':sum(c['tool_calls'] for c in costs)}
    for key in ('provider_tokens','provider_cost'):
        values = [c[key] for c in costs]
        total_cost[key] = None if any(v is None for v in values) else sum(values)
    units = {c['provider_cost_unit'] for c in costs if c['provider_cost'] is not None}
    w.require(len(units) <= 1, 'mixed provider currencies')
    total_cost['provider_cost_unit'] = next(iter(units),None) if total_cost['provider_cost'] is not None else None
    passed = sum(run['outcome'] == 'passed' for run in runs)
    return {'passed':passed,'total':len(runs),'pass_rate':passed/len(runs),
            'duration_seconds':sum(run['duration_seconds'] for run in runs),'cost':total_cost}


def load_trial(path, sample, repeat, version, source, verdict, config_sha, source_sha):
    w.require(path.is_file() and not path.is_symlink(), 'missing or symlink trial file')
    data = path.read_bytes()
    raw = json.loads(data)
    w.require(all(raw.get(key) == value for key,value in {'sample_id':sample['id'],
              'category':sample['category'],'repeat':repeat,'version':version,'source':source,
              'input_sha256':sample['input_sha256']}.items()), 'trial sample/version/source identity differs')
    w.require(isinstance(verdict,dict) and w.nonempty(verdict.get('notes')), 'explicit per-trial assessment notes required')
    receipt = hashlib.sha256(data).hexdigest()
    w.require(w.valid_sha(verdict.get('receipt_sha256')) == receipt, 'verdict receipt differs from original trial bytes')
    criteria = verdict.get('criteria',{})
    w.require(isinstance(criteria,dict) and set(criteria) == set(criteria_for(sample['category']))
              and set(criteria.values()) <= {'passed','failed','unavailable'}, 'explicit exact per-trial criteria required')
    duration = raw.get('duration_seconds')
    w.require(w.number(duration), 'measured duration missing')
    if criteria['completion'] == 'passed':
        w.require(raw.get('terminal') == 'completed' and isinstance(raw.get('answers'),list)
                  and any(w.nonempty(answer) for answer in raw['answers']) and duration <= 480,
                  'completion verdict contradicts actual terminal/answer/duration')
    start = datetime.fromisoformat(w.timestamp(raw.get('observed_at')).replace('Z','+00:00'))
    finished = w.timestamp((start + timedelta(seconds=duration)).isoformat())
    conditions = raw.get('conditions')
    w.require(isinstance(conditions,dict) and w.digest(conditions) == raw.get('conditions_sha256'), 'raw conditions hash differs')
    w.require(conditions.get('model_config_sha256') == raw.get('model_config_sha256'), 'model conditions identity differs')
    cost = raw.get('cost',{})
    w.require(isinstance(cost,dict) and type(cost.get('tool_calls')) is int and cost['tool_calls'] >= 0
              and isinstance(raw.get('calls'),list) and cost['tool_calls'] == len(raw['calls']), 'measured source call count differs')
    w.require(all(key in cost for key in ('provider_tokens','provider_cost','provider_cost_unit')), 'provider unavailability must be explicit')
    w.require(cost['provider_tokens'] is None or (type(cost['provider_tokens']) is int and cost['provider_tokens'] >= 0), 'invalid provider tokens')
    w.require((cost['provider_cost'] is None and cost['provider_cost_unit'] is None)
              or (w.number(cost['provider_cost']) and w.nonempty(cost['provider_cost_unit'])), 'invalid provider cost')
    outcome = 'passed' if all(value == 'passed' for value in criteria.values()) else 'failed' if 'failed' in criteria.values() else 'partial'
    observation_hash = w.digest({'start':raw['observed_at'],'finished':finished})[:16]
    return {'trial_id':f'{version}.{sample["id"]}.{repeat}.{observation_hash}', 'observed_at':finished,
            'source_sha':source_sha,'config_sha256':config_sha,'prompt_sha256':w.valid_sha(raw.get('prompt_sha256')),
            'runtime_id':source,'conditions_sha256':w.valid_sha(raw.get('conditions_sha256')),
            'model_config_sha256':w.valid_sha(raw.get('model_config_sha256')),
            'input_sha256':sample['input_sha256'],'evidence_sha256':receipt,
            'outcome':outcome,'criteria':copy.deepcopy(criteria),'assessment_notes':verdict['notes'],
            'duration_seconds':duration,'cost':{'counter_scope':'source_gateway_only', **{k:cost[k] for k in ('tool_calls','provider_tokens','provider_cost','provider_cost_unit')}}}


def build(prereg, manifest, verdicts, before_dir, after_dir, baseline_sha, diff_sha256, candidate_source,
          *, baseline_source=None, baseline_alias_proof=None):
    w.valid_sha(baseline_sha,40); w.valid_sha(diff_sha256)
    target = w.valid_sha(manifest.get('sourceCommit'),40)
    for key in ('baseInventory','files','environmentHashes'):
        w.require(isinstance(manifest.get(key),dict) and manifest[key], 'manifest identity inventory missing')
    resolved_source = manifest.get('expectedBackend')
    baseline_source = resolved_source if baseline_source is None else baseline_source
    w.require(w.nonempty(resolved_source) and w.nonempty(baseline_source), 'resolved baseline source missing')
    if baseline_source != resolved_source:
        w.require(baseline_source == '/opt/chickenbro', 'only fixed baseline alias is permitted')
        proof = baseline_alias_proof
        w.require(isinstance(proof,dict), 'fixed baseline alias needs identity proof')
        w.require(proof.get('alias') == baseline_source and proof.get('resolved') == resolved_source
                  and proof.get('source_sha') == baseline_sha, 'baseline alias identity differs')
        inventory_sha = w.digest(manifest['baseInventory'])
        w.require(proof.get('before_inventory_sha256') == inventory_sha
                  and proof.get('after_inventory_sha256') == inventory_sha, 'baseline alias inventory differs')
        proof_start = w.timestamp(proof.get('before_observed_at'))
        proof_finish = w.timestamp(proof.get('after_observed_at'))
        w.require(proof_start <= proof_finish <= w.utc_now(), 'invalid baseline alias proof interval')
    else:
        w.require(baseline_source != '/opt/chickenbro', 'manifest baseline must be a resolved source')
        w.require(baseline_alias_proof is None, 'alias proof supplied without fixed alias')
    config_sha = w.digest(manifest['environmentHashes'])
    identity = {'source_sha':target,'baseline_sha':baseline_sha,'diff_sha256':diff_sha256,
                'build_sha256':w.digest({**manifest['baseInventory'],**manifest['files']}),'config_sha256':config_sha}
    group = w.group_id(prereg.get('group'))
    version = prereg.get('version')
    w.require(isinstance(version,str) and re.fullmatch(r'[A-Za-z0-9._-]{1,32}',version), 'preregistration version required')
    samples = prereg.get('samples',[])
    w.require(isinstance(samples,list) and 5 <= len(samples) <= 100, 'registered sample inventory missing')
    for sample in samples:
        w.require(isinstance(sample,dict) and isinstance(sample.get('id'),str)
                  and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',sample['id']), 'unsafe sample id')
        w.valid_sha(sample.get('input_sha256'))
    sample_ids = {s['id'] for s in samples}
    w.require(len(sample_ids) == len(samples), 'duplicate registered sample ids')
    repetitions = prereg.get('repetitions')
    w.require(type(repetitions) is int and 2 <= repetitions <= 20, 'registered repeated trial count required')
    registration = {'fixed_at':w.timestamp(prereg.get('fixed_at')), 'criteria':copy.deepcopy(prereg.get('criteria',{})),
                    'assignments':{s['id']:{'category':s['category'],'input_sha256':s['input_sha256'],
                        'used_for_design':s.get('used_for_design'),'transformation':s.get('transformation',''),
                        'criterion_ids':criteria_for(s['category'])} for s in samples},
                    'minimum_repetitions':repetitions,'minimum_after_pass_rate':1.0,'model_stochastic':True}
    judgments = verdicts.get('trials',{})
    w.require(isinstance(judgments,dict) and set(judgments) == {'before','after'}, 'both verdict phases required')
    review = verdicts.get('review',{})
    proof = {key:copy.deepcopy(review.get(key)) for key in ('mechanism','root_cause_evidence','applicable_scope','excluded_boundaries','anti_case_specialization')}
    w.require(all(proof.get(key) is not None for key in proof), 'explicit mechanism and anti-specialization review required')
    proof.update(preregistration=registration,preregistration_sha256=w.digest(registration),
                 baseline_config_sha256=config_sha,pairs={s['id']:{} for s in samples})
    conditions, models = set(),set()
    for phase,directory,prefix,source,sha in [('before',Path(before_dir),'baseline',baseline_source,baseline_sha),
                                            ('after',Path(after_dir),'candidate',candidate_source,target)]:
        expected = {f'{s["id"]}-{repeat}.json' for s in samples for repeat in range(1,repetitions+1)}
        w.require(directory.is_dir() and {p.name for p in directory.glob('*.json')} == expected, 'raw trial inventory incomplete or includes unregistered files')
        w.require(isinstance(judgments[phase],dict) and set(judgments[phase]) == sample_ids, 'verdict sample inventory differs')
        prompts = set()
        for sample in samples:
            verdict_rows = judgments[phase][sample['id']]
            w.require(isinstance(verdict_rows,dict) and set(verdict_rows) == {str(n) for n in range(1,repetitions+1)}, 'verdict repetition inventory differs')
            runs = [load_trial(directory/f'{sample["id"]}-{repeat}.json',sample,repeat,prefix+'-'+version,
                               source,verdict_rows[str(repeat)],config_sha,sha) for repeat in range(1,repetitions+1)]
            if phase == 'before' and baseline_alias_proof is not None:
                for run in runs:
                    finish = run['observed_at']
                    start = w.timestamp((datetime.fromisoformat(finish.replace('Z','+00:00'))
                                         - timedelta(seconds=run['duration_seconds'])).isoformat())
                    w.require(proof_start <= start and finish <= proof_finish,
                              'baseline alias proof does not bracket every execution')
            prompts.update(run['prompt_sha256'] for run in runs)
            conditions.update(run['conditions_sha256'] for run in runs)
            models.update(run['model_config_sha256'] for run in runs)
            proof['pairs'][sample['id']][phase] = {'runs':runs,'summary':summarize(runs)}
        w.require(len(prompts) == 1, 'prompt identity changed within phase')
        proof[phase+'_prompt_sha256'] = next(iter(prompts))
    w.require(len(conditions) == len(models) == 1, 'before/after controlled conditions differ')
    proof.update(conditions_sha256=next(iter(conditions)),model_config_sha256=next(iter(models)))
    record = {**identity,'kind':'generalization','status':'unverified','observed_at':w.utc_now(),'checks':{},
              'details':'All registered trials retained. Per-trial criteria and notes are operator judgments; raw answers and tool traces stay private. Tool counter scope is source gateway only; unavailable provider usage remains null.',
              'source_preregistration_sha256':w.digest(prereg),'source_preregistration':copy.deepcopy(prereg),
              'verdicts_sha256':w.digest(verdicts),'groups':{group:proof}}
    if baseline_alias_proof is not None:
        record['baseline_alias_proof_sha256'] = w.digest(baseline_alias_proof)
        record['baseline_alias_proof'] = {key:baseline_alias_proof[key] for key in (
            'alias','resolved','source_sha','before_observed_at','after_observed_at',
            'before_inventory_sha256','after_inventory_sha256')}
    try:
        w.validate_generalization(record,{**identity,'groups':{group:'registered'}})
    except w.WorkflowError as exc:
        record['validation_error'] = str(exc)
    else:
        record['status'] = 'passed'
    return record


def write_private(path, record):
    path = Path(path).absolute()
    w.require(path.parent.is_dir() and not any(p.is_symlink() for p in [path,*path.parents]), 'output parent missing or symlink')
    payload = w.canonical(record)+b'\n'
    if path.exists():
        w.require(path.read_bytes() == payload, 'refusing to overwrite different evidence')
        os.chmod(path,0o600)
        return
    fd,name = tempfile.mkstemp(prefix='.generalization-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as handle:
            os.fchmod(handle.fileno(),0o600);handle.write(payload);handle.flush();os.fsync(handle.fileno())
        os.link(name,path)  # Exclusive publication, no overwrite race.
        directory=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        os.unlink(name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('prereg','manifest','verdicts','before-dir','after-dir','baseline-sha','diff-sha256','candidate-source','output'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--baseline-source',help='default: manifest expectedBackend; only optional alias /opt/chickenbro')
    parser.add_argument('--baseline-alias-proof',help='JSON proof of resolved identity and matching before/after baseline inventory')
    args=parser.parse_args()
    try:
        record=build(*(json.loads(Path(path).read_text()) for path in (args.prereg,args.manifest,args.verdicts)),
                     args.before_dir,args.after_dir,args.baseline_sha,args.diff_sha256,args.candidate_source,
                     baseline_source=args.baseline_source,
                     baseline_alias_proof=json.loads(Path(args.baseline_alias_proof).read_text()) if args.baseline_alias_proof else None)
        write_private(args.output,record)
        print(json.dumps({'status':record['status'],'sha256':w.file_sha(args.output),
                          'validation_error':record.get('validation_error')}))
        return 0 if record['status']=='passed' else 2
    except w.WorkflowError as exc:
        print(json.dumps({'status':'not_completed','reason':str(exc)}),file=sys.stderr)
        return 1
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        print(json.dumps({'status':'not_completed','reason':'missing, inconsistent or unsafe evidence inputs; no result inferred'}),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())

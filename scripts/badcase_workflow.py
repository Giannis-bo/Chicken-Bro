#!/usr/bin/env python3
"""Private, bounded badcase packets and human-approved SHA-bound release gates.

No diagnosis, user approval, business acceptance or deployment is inferred here.
The operator supplies a reviewed executor; see docs/badcase-workflow-operations.md.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid


class WorkflowError(Exception):
    pass


IDENTITY = ('source_sha', 'build_sha256', 'config_sha256', 'baseline_sha', 'diff_sha256')
CHECKS = {
    'scope': ('full_baseline_diff_reviewed', 'backend_compatible', 'no_unapproved_commits', 'budget_unchanged'),
    'tests': ('targeted', 'combined_regression', 'held_out', 'normal_queries', 'owner_isolation', 'transport_contract'),
    'review': ('local_diff_review', 'no_blocking_findings'),
    'candidate': ('real_chat_terminal', 'history_readback', 'affected_tools', 'same_permissions', 'original_question_context'),
    'rollback': ('baseline_package_verified', 'safe_code_rollback', 'recovery_procedure_verified'),
    'generalization': (),
}
EVIDENCE_KINDS = tuple(CHECKS)
LIVE_CHECKS = ('real_chat_terminal', 'history_readback', 'affected_tools', 'owner_isolation',
               'web_artifact_verified', 'drained_without_kill', 'api_worker_identity', 'observation_passed')
MAX_EVIDENCE_AGE = 24 * 3600


def require(condition, message):
    if not condition:
        raise WorkflowError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, 'timestamp requires timezone')
        return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    except (ValueError, TypeError, AttributeError) as exc:
        raise WorkflowError('invalid timestamp') from exc


def fresh(value):
    age = time.time() - datetime.fromisoformat(timestamp(value).replace('Z', '+00:00')).timestamp()
    require(-60 <= age <= MAX_EVIDENCE_AGE, 'evidence outside 24-hour freshness window')


def valid_sha(value, length=64):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value), 'invalid SHA')
    return value


def run_id(value):
    try:
        require(str(uuid.UUID(value)) == value, 'noncanonical run id')
        return value
    except (ValueError, TypeError, AttributeError) as exc:
        raise WorkflowError('invalid run id') from exc


def group_id(value):
    require(isinstance(value, str) and re.fullmatch(r'G[1-9][0-9]{0,7}', value), 'invalid group id')
    return value


def nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 16000


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_generalization(record, batch):
    """Validate registered assignments and measured paired outcomes, not a pass checkbox."""
    proofs = record.get('groups', {})
    require(isinstance(proofs, dict) and set(proofs) == set(batch['groups']), 'generalization unverified: group coverage differs')
    categories = {'original', 'variant', 'independent_holdout', 'normal', 'permission'}
    execution_ids, receipts = set(), set()
    for proof in proofs.values():
        require(isinstance(proof, dict), 'generalization unverified: group record missing')
        for key in ('mechanism', 'root_cause_evidence', 'applicable_scope', 'excluded_boundaries'):
            require(nonempty(proof.get(key)), 'generalization unverified: mechanism or boundaries missing')
        audit = proof.get('anti_case_specialization', {})
        require(audit.get('status') == 'passed' and audit.get('findings') == []
                and audit.get('reviewed_diff_sha256') == batch['diff_sha256']
                and set(audit.get('reviewed_surfaces', [])) == {'code', 'prompts', 'config', 'data_mappings'}
                and nonempty(audit.get('review_notes')), 'generalization unverified: case specialization audit failed')
        registration = proof.get('preregistration', {})
        require(digest(registration) == valid_sha(proof.get('preregistration_sha256')), 'generalization unverified: registration hash differs')
        fixed_at = timestamp(registration.get('fixed_at'))
        criteria = registration.get('criteria', {})
        require(isinstance(criteria, dict) and criteria and all(nonempty(k) and nonempty(v) for k,v in criteria.items()),
                'generalization unverified: acceptance criteria missing')
        assignments = registration.get('assignments', {})
        require(isinstance(assignments, dict) and 5 <= len(assignments) <= 100, 'generalization unverified: sample assignments missing')
        require(all(isinstance(a, dict) for a in assignments.values()), 'generalization unverified: invalid assignment')
        require({a.get('category') for a in assignments.values()} == categories, 'generalization unverified: required sample category missing')
        require(type(registration.get('model_stochastic')) is bool, 'generalization unverified: model stochasticity unspecified')
        minimum = registration.get('minimum_repetitions')
        require(type(minimum) is int and (2 if registration['model_stochastic'] else 1) <= minimum <= 20,
                'generalization unverified: repeated trials missing')
        threshold = registration.get('minimum_after_pass_rate')
        require(number(threshold) and 0 < threshold <= 1, 'generalization unverified: acceptance rate missing')
        pairs = proof.get('pairs', {})
        require(isinstance(pairs, dict) and set(pairs) == set(assignments), 'generalization unverified: assigned samples omitted')
        for key in ('baseline_config_sha256', 'before_prompt_sha256', 'after_prompt_sha256', 'conditions_sha256', 'model_config_sha256'):
            valid_sha(proof.get(key))
        original_inputs = {a['input_sha256'] for a in assignments.values() if a['category'] == 'original'}
        for sample_id, assignment in assignments.items():
            input_sha = valid_sha(assignment.get('input_sha256'))
            category = assignment['category']
            require(type(assignment.get('used_for_design')) is bool, 'generalization unverified: design participation unspecified')
            if category == 'independent_holdout':
                require(assignment['used_for_design'] is False
                        and all(other_id == sample_id or other.get('input_sha256') != input_sha for other_id,other in assignments.items()),
                        'generalization unverified: holdout used for design or duplicates original')
            if category == 'variant':
                require(input_sha not in original_inputs and nonempty(assignment.get('transformation')),
                        'generalization unverified: variant does not vary unrelated input')
            criterion_ids = assignment.get('criterion_ids', [])
            require(isinstance(criterion_ids,list) and criterion_ids and len(set(criterion_ids)) == len(criterion_ids)
                    and set(criterion_ids) <= set(criteria), 'generalization unverified: sample acceptance undefined')
            pair = pairs[sample_id]
            require(isinstance(pair,dict) and set(pair) == {'before','after'}, 'generalization unverified: paired result missing')
            counts = []
            counter_scopes = set()
            for phase in ('before','after'):
                observations = pair[phase]
                runs = observations.get('runs', [])
                require(isinstance(runs,list) and minimum <= len(runs) <= 20, 'generalization unverified: insufficient repetitions')
                counts.append(len(runs))
                passed = 0
                for trial in runs:
                    require(isinstance(trial,dict) and timestamp(trial.get('observed_at')) >= fixed_at
                            and timestamp(trial['observed_at']) <= timestamp(record['observed_at']),
                            'generalization unverified: trial outside registered observation period')
                    expected = {'source_sha':batch['baseline_sha'] if phase == 'before' else batch['source_sha'],
                                'config_sha256':proof['baseline_config_sha256'] if phase == 'before' else batch['config_sha256'],
                                'prompt_sha256':proof[phase + '_prompt_sha256'], 'input_sha256':input_sha,
                                'conditions_sha256':proof['conditions_sha256'], 'model_config_sha256':proof['model_config_sha256']}
                    require(all(trial.get(k) == v for k,v in expected.items()) and nonempty(trial.get('runtime_id')),
                            'generalization unverified: source or controlled conditions differ')
                    trial_id = trial.get('trial_id')
                    receipt = valid_sha(trial.get('evidence_sha256'))
                    require(isinstance(trial_id,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,255}',trial_id),
                            'generalization unverified: unique bounded trial identity missing')
                    require(trial_id not in execution_ids and receipt not in receipts,
                            'generalization unverified: duplicate execution or trial receipt')
                    execution_ids.add(trial_id)
                    receipts.add(receipt)
                    verdicts = trial.get('criteria', {})
                    require(isinstance(verdicts,dict) and set(verdicts) == set(criterion_ids)
                            and set(verdicts.values()) <= {'passed','failed','unavailable'}, 'generalization unverified: criterion observations missing')
                    success = all(v == 'passed' for v in verdicts.values())
                    require(trial.get('outcome') in ('passed','failed','partial') and (trial['outcome'] == 'passed') == success,
                            'generalization unverified: outcome contradicts criteria')
                    passed += int(success)
                    require(number(trial.get('duration_seconds')), 'generalization unverified: elapsed time missing')
                    cost = trial.get('cost', {})
                    require(cost.get('counter_scope') in ('source_gateway_only','all_tools')
                            and type(cost.get('tool_calls')) is int and cost['tool_calls'] >= 0
                            and 'provider_tokens' in cost and 'provider_cost' in cost and 'provider_cost_unit' in cost,
                            'generalization unverified: measured cost or unavailable declaration missing')
                    require(cost['provider_tokens'] is None or (type(cost['provider_tokens']) is int and cost['provider_tokens'] >= 0),
                            'generalization unverified: invalid provider token count')
                    require((cost['provider_cost'] is None and cost['provider_cost_unit'] is None)
                            or (number(cost['provider_cost']) and nonempty(cost['provider_cost_unit'])),
                            'generalization unverified: invalid provider cost')
                rate = passed / len(runs)
                summary = observations.get('summary', {})
                require(summary.get('passed') == passed and summary.get('total') == len(runs)
                        and number(summary.get('pass_rate')) and math.isclose(summary['pass_rate'],rate)
                        and number(summary.get('duration_seconds'))
                        and math.isclose(summary['duration_seconds'],sum(r['duration_seconds'] for r in runs)),
                        'generalization unverified: rate or elapsed summary differs from trials')
                units = {r['cost']['provider_cost_unit'] for r in runs if r['cost']['provider_cost'] is not None}
                require(len(units) <= 1, 'generalization unverified: mixed cost currencies')
                scopes = {r['cost']['counter_scope'] for r in runs}
                counter_scopes.update(scopes)
                require(len(scopes) == 1, 'generalization unverified: mixed tool counter scopes')
                totals = {'counter_scope':next(iter(scopes)), 'tool_calls':sum(r['cost']['tool_calls'] for r in runs)}
                for key in ('provider_tokens','provider_cost'):
                    values = [r['cost'][key] for r in runs]
                    totals[key] = None if any(v is None for v in values) else sum(values)
                totals['provider_cost_unit'] = next(iter(units),None) if totals['provider_cost'] is not None else None
                reported_cost = summary.get('cost', {})
                require(set(reported_cost) == set(totals) and all(reported_cost[k] is None if v is None
                        else (number(reported_cost[k]) and math.isclose(reported_cost[k],v)) if number(v)
                        else reported_cost[k] == v for k,v in totals.items()), 'generalization unverified: cost summary differs from trials')
                require((phase != 'after' or rate >= threshold) and (category not in ('normal','permission') or rate == 1),
                        'generalization unverified: acceptance failed or normal/permission regressed')
            require(len(counter_scopes) == 1, 'generalization unverified: before/after counter scopes differ')
            require(counts[0] == counts[1], 'generalization unverified: unequal paired repetition counts')


def scan_sql(cursor, limit):
    require(type(limit) is int and 1 <= limit <= 100, 'scan limit must be 1..100')
    after = ''
    if cursor is not None:
        require(isinstance(cursor, list) and len(cursor) == 2, 'invalid cursor')
        at, rid = timestamp(cursor[0]), run_id(cursor[1])
        after = f"AND (r.feedback_updated_at, r.id) > ('{at}'::timestamptz, '{rid}'::uuid)"
    # Select only user-visible messages. Never select model traces, auth or reasoning.
    return f"""BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';
WITH page AS (
 SELECT r.* FROM chat.agent_runs r
 WHERE r.resolved = false {after}
 ORDER BY r.feedback_updated_at, r.id LIMIT {limit}
)
SELECT COALESCE(json_agg(packet ORDER BY feedback_at, run_id), '[]'::json) FROM (
 SELECT r.id AS run_id, to_char(r.feedback_updated_at AT TIME ZONE 'UTC',
 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') AS feedback_at,
 r.conversation_id, q.content AS question, a.content AS answer, r.runtime_revision,
 (SELECT count(*) FROM chat.messages m WHERE m.conversation_id = r.conversation_id
   AND m.user_id = r.user_id AND (m.created_at, m.id) < (q.created_at, q.id)) AS context_total,
 COALESCE((SELECT json_agg(c ORDER BY c.created_at, c.id) FROM (
   SELECT m.id, m.role, left(m.content,16000) AS content,
     length(m.content)>16000 AS truncated, m.created_at
   FROM chat.messages m WHERE m.conversation_id = r.conversation_id AND m.user_id = r.user_id
     AND (m.created_at, m.id) < (q.created_at, q.id)
   ORDER BY m.created_at DESC, m.id DESC LIMIT 40
 ) c), '[]'::json) AS context
 FROM page r
 JOIN chat.messages q ON q.id = r.user_message_id AND q.user_id = r.user_id
 JOIN chat.messages a ON a.id = r.assistant_message_id AND a.user_id = r.user_id
) packet;
COMMIT;
"""


def fetch_production(cursor, limit):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
                             'wow-lighthouse', 'sudo -u postgres psql -X -qAt -v ON_ERROR_STOP=1 chickenbro_prod'],
                            input=scan_sql(cursor, limit), capture_output=True, text=True, timeout=45)
    require(result.returncode == 0, 'production read-only scan failed; cursor unchanged')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise WorkflowError('production scan returned invalid JSON; cursor unchanged') from exc


class Workflow:
    def __init__(self, root):
        self.root = Path(root).absolute()
        # Reject symlink ancestors rather than following them into unrelated data.
        require(not any(p.is_symlink() for p in [self.root, *self.root.parents]), 'symlink state root')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(self.root.stat().st_uid == os.getuid(), 'state root is not owned by current user')
        os.chmod(self.root, 0o700)
        for name in ('raw', 'reports', 'batches', 'evidence'):
            path = self.path(name)
            path.mkdir(mode=0o700, exist_ok=True)
            os.chmod(path, 0o700)

    def path(self, name):
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe state path')
        path = self.root / relative
        require(not any(p.is_symlink() for p in [path, *path.parents]), 'symlink state path')
        return path

    @contextmanager
    def lock(self, name, timeout=None):
        require(name in ('scan', 'release', 'state'), 'invalid lock')
        fd = os.open(self.path(name + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        try:
            wait = (10.0 if name == 'state' else 0.0) if timeout is None else timeout
            require(0 <= wait <= 10, 'invalid lock wait')
            deadline = time.monotonic() + wait
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise WorkflowError(name + ' already running') from exc
                    time.sleep(min(0.025, remaining))
            yield
        finally:
            os.close(fd)

    def read(self, name, default=None):
        path = self.path(name)
        if not path.exists(): return default
        require(stat.S_ISREG(path.stat().st_mode), 'state entry is not a regular file')
        os.chmod(path, 0o600)
        return json.loads(path.read_text())

    def write(self, name, data, immutable=False):
        path = self.path(name)
        payload = canonical(data) + b'\n'
        if immutable and path.exists():
            require(path.read_bytes() == payload, 'immutable artifact already differs')
            return
        fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                os.fchmod(handle.fileno(), 0o600)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def state(self):
        return self.read('state.json', {'schema':1, 'cursor':None, 'seen':{}, 'groups':{}, 'releases':{}})

    def _prune(self, now):
        removed = 0
        for path in self.path('raw').glob('*.json'):
            packet = self.read('raw/' + path.name)
            if now - packet['retained_at'] >= 7 * 86400:
                path.unlink()
                removed += 1
        return removed

    def prune(self, now=None):
        with self.lock('scan'):
            return {'removed':self._prune(time.time() if now is None else now)}

    def scan(self, fetch=fetch_production, limit=100, now=None):
        scan_sql(None, limit)
        now = time.time() if now is None else now
        with self.lock('scan'):
            self._prune(now)
            with self.lock('state'):
                state = self.state()
            scan_count = state.get('scan_count', 0) + 1
            reconciliation = state.get('reconciliation')
            if reconciliation is None and scan_count % 8 == 0:
                reconciliation = {'cursor':None, 'upper':state['cursor']}
            query_cursor = reconciliation['cursor'] if reconciliation is not None else state['cursor']
            # Network and raw-packet I/O never hold the shared state lock.
            rows = fetch(query_cursor, limit)
            require(isinstance(rows, list) and len(rows) <= limit, 'scan response exceeds budget')
            packets = []
            previous = None
            for row in rows:
                rid = run_id(row.get('run_id'))
                cursor = [timestamp(row.get('feedback_at')), rid]
                require(previous is None or cursor > previous, 'scan rows not strictly ordered')
                previous = cursor
                require(isinstance(row.get('question'), str) and isinstance(row.get('answer'), str), 'missing original pair')
                require(len(row['question']) <= 100000 and len(row['answer']) <= 100000, 'original pair exceeds schema budget')
                context = row.get('context', [])
                require(isinstance(context, list) and len(context) <= 40, 'context exceeds budget')
                cleaned = []
                for message in context:
                    require(message.get('role') in ('user', 'assistant') and isinstance(message.get('content'), str), 'invalid visible context')
                    cleaned.append({'role':message['role'], 'content':message['content'][:16000],
                                    'truncated':bool(message.get('truncated')) or len(message['content']) > 16000})
                packet = {'run_id':rid, 'feedback_at':cursor[0], 'resolved':False,
                          'conversation_hash':digest(run_id(row.get('conversation_id'))),
                          'question':row['question'], 'answer':row['answer'],
                          'runtime_revision':row.get('runtime_revision') or None,
                          'context':cleaned, 'context_truncated':row.get('context_total', len(context)) > len(context) or any(m['truncated'] for m in cleaned),
                          'missing_evidence':['actual_model_input', 'historical_tool_calls', 'model_configuration', 'simc_snapshots'],
                          'retained_at':now}
                packets.append((cursor, packet))
            new = 0
            for cursor, packet in packets:
                rid = packet['run_id']
                if rid not in state['seen']:
                    # A crash after packet write but before state update reuses the first immutable packet.
                    prior = self.read(f'raw/{rid}.json')
                    if prior is not None:
                        require(all(prior[k] == packet[k] for k in ('run_id','feedback_at','question','answer','runtime_revision')), 'original packet changed')
                        packet = prior
                    self.write(f'raw/{rid}.json', packet, immutable=True)
                    state['seen'][rid] = {'feedback_at':cursor[0], 'packet_sha256':digest(packet),
                                          'conversation_hash':packet['conversation_hash']}
                    new += 1
                if state['cursor'] is None or cursor > state['cursor']: state['cursor'] = cursor
            mode = 'reconciliation' if reconciliation is not None else 'incremental'
            if reconciliation is not None:
                # A fixed high-water mark makes each sweep finite even as new feedback arrives.
                reached_upper = reconciliation['upper'] is None or (previous is not None and previous >= reconciliation['upper'])
                reconciliation = None if len(rows) < limit or reached_upper else {**reconciliation, 'cursor':previous}
            report = {'scanned':len(rows), 'new':new, 'deduplicated':len(rows)-new,
                      'cursor':state['cursor'], 'page_full':len(rows)==limit,
                      'mode':mode, 'reconciliation_pending':reconciliation is not None,
                      'evidence_insufficient':new, 'verified':0, 'unfinished':new,
                      'scan_time':now, 'limit':limit, 'diagnosis':'not_run'}
            self.write('reports/' + digest(report) + '.json', report, immutable=True)
            with self.lock('state'):
                latest = self.state()
                # Other operations may have approved groups or finalized a release during fetch.
                latest['seen'].update(state['seen'])
                latest['cursor'] = state['cursor']
                latest['scan_count'] = scan_count
                latest['reconciliation'] = reconciliation
                self.write('state.json', latest)
            return report

    def group(self, gid, runs, mechanism, scope):
        group_id(gid)
        require(isinstance(runs, list) and runs and len(runs) <= 100 and len(set(runs)) == len(runs), 'invalid group members')
        require(isinstance(mechanism,str) and 0 < len(mechanism) <= 1000 and isinstance(scope,str) and 0 < len(scope) <= 8000, 'group needs bounded mechanism and scope')
        with self.lock('state'):
            state = self.state()
            require(all(run_id(r) in state['seen'] for r in runs), 'group contains unscanned runs')
            report = {'id':gid, 'runs':sorted(runs), 'mechanism':mechanism, 'scope':scope,
                      'packets':{r:state['seen'][r]['packet_sha256'] for r in sorted(runs)}}
            sha = digest(report)
            self.write('reports/' + sha + '.json', report, immutable=True)
            current = state['groups'].get(gid)
            if not current or current['report_sha256'] != sha:
                state['groups'][gid] = {'report_sha256':sha, 'decision':'pending'}
            self.write('state.json', state)
            return {'group':gid, **state['groups'][gid]}

    def decide(self, gid, report_sha, decision, approval_ref):
        group_id(gid)
        require(decision in ('approved','investigate','deferred','no_verified_defect'), 'invalid decision')
        require(isinstance(approval_ref,str) and 0 < len(approval_ref) <= 1000, 'explicit user decision reference required')
        with self.lock('state'):
            state = self.state()
            require(state['groups'].get(gid,{}).get('report_sha256') == valid_sha(report_sha), 'report version differs')
            state['groups'][gid].update(decision=decision, approval_ref=approval_ref, decided_at=utc_now())
            self.write('state.json', state)
            return {'group':gid, **state['groups'][gid]}

    def validate_batch(self, batch, state):
        for key in IDENTITY: valid_sha(batch.get(key), 40 if key.endswith('_sha') else 64)
        fresh(batch.get('created_at'))
        require(batch.get('backend_only') is True and batch.get('excluded_impacts') == [], 'batch outside automatic backend scope')
        groups = batch.get('groups')
        require(isinstance(groups,dict) and groups, 'empty release batch')
        for gid, report in groups.items():
            group_id(gid)
            approved = state['groups'].get(gid,{})
            require(approved.get('decision') == 'approved' and approved.get('report_sha256') == report, 'group not approved at this report version')
        evidence = batch.get('evidence',{})
        require('generalization' in evidence, 'generalization unverified: missing evidence')
        require(set(evidence) == set(EVIDENCE_KINDS), 'missing release evidence')
        for kind in EVIDENCE_KINDS:
            ref = evidence[kind]
            record = self.read('evidence/' + valid_sha(ref['sha256']) + '.json')
            require(record is not None and digest(record) == ref['sha256'], 'evidence hash differs')
            require(record.get('kind') == kind and record.get('status') == 'passed', 'evidence not passed')
            require(all(record.get(k) == batch[k] for k in IDENTITY), 'evidence identity mismatch')
            fresh(record.get('observed_at'))
            require(isinstance(record.get('details'),str) and record['details'].strip(), 'evidence details missing')
            require(all(record.get('checks',{}).get(k) is True for k in CHECKS[kind]), 'required verification missing')
            if kind == 'generalization':
                validate_generalization(record, batch)
            if kind == 'rollback':
                rollback = record.get('rollback_identity', {})
                require(rollback.get('source_sha') == batch['baseline_sha'], 'rollback baseline identity missing')
                valid_sha(rollback.get('artifact_sha256'))
                valid_sha(rollback.get('config_sha256'))

    def freeze(self, manifest):
        with self.lock('state'):
            state = self.state()
            # Only explicit schema fields survive; notably never commands or executor paths.
            batch = {k:manifest.get(k) for k in (*IDENTITY,'groups','backend_only','excluded_impacts','created_at')}
            batch['evidence'] = {}
            for kind, ref in manifest.get('evidence',{}).items():
                require(kind in EVIDENCE_KINDS and isinstance(ref,dict), 'invalid evidence kind')
                path = Path(ref['path'])
                require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 5_000_000, 'invalid evidence file')
                contents = path.read_bytes()
                require(hashlib.sha256(contents).hexdigest() == valid_sha(ref['sha256']), 'evidence file SHA differs')
                record = json.loads(contents)
                sha = digest(record)
                self.write(f'evidence/{sha}.json', record, immutable=True)
                batch['evidence'][kind] = {'sha256':sha}
            self.validate_batch(batch, state)
            sha = digest(batch)
            self.write(f'batches/{sha}.json', batch, immutable=True)
            return sha

    def release(self, batch_sha, executor):
        valid_sha(batch_sha)
        with self.lock('release'):
            with self.lock('state'):
                state = self.state()
                previous = state['releases'].get(batch_sha)
                if previous:
                    require(previous['status'] == 'released', 'batch already attempted; fresh fix and evidence required')
                    return previous
                batch = self.read(f'batches/{batch_sha}.json')
                require(batch is not None and digest(batch) == batch_sha, 'batch hash differs or missing')
                self.validate_batch(batch, state)
                require(not any(item.get('source_sha') == batch['source_sha'] and item['status'] in ('failed','publishing')
                                for item in state['releases'].values()), 'failed source requires a new fix and new evidence')
            envelope = {'batch_sha256':batch_sha, 'batch':batch}
            preflight = executor('preflight', envelope)
            require(preflight.get('batch_sha256') == batch_sha and preflight.get('baseline_sha') == batch['baseline_sha']
                    and preflight.get('clean') is True and preflight.get('diff_sha256') == batch['diff_sha256'], 'production baseline/workspace/diff drift; release deferred')
            with self.lock('state'):
                state = self.state()
                self.validate_batch(batch, state)
                started_at = utc_now()
                state['releases'][batch_sha] = {'status':'publishing', 'started_at':started_at, 'source_sha':batch['source_sha']}
                self.write('state.json', state)
            try:
                live = executor('release', envelope)
                require(live.get('batch_sha256') == batch_sha and live.get('status') == 'passed', 'live business verification absent')
                require(all(live.get(k) == batch[k] for k in ('source_sha','build_sha256','config_sha256')), 'live identity mismatch')
                fresh(live.get('observed_at'))
                require(timestamp(live['observed_at']) >= started_at, 'live evidence predates this release')
                require(all(live.get('checks',{}).get(k) is True for k in LIVE_CHECKS), 'live business verification incomplete')
                live_sha = digest(live)
                self.write(f'evidence/{live_sha}.json', live, immutable=True)
                result = {'status':'released', 'live_sha256':live_sha, 'finished_at':utc_now(), 'user_acceptance':'not_claimed'}
            except Exception:
                with self.lock('state'):
                    state = self.state()
                    state['releases'][batch_sha] = {'status':'failed', 'source_sha':batch['source_sha'], 'finished_at':utc_now(), 'recovery':'executor evidence must be inspected; no blind retry'}
                    self.write('state.json', state)
                raise
            with self.lock('state'):
                state = self.state()
                state['releases'][batch_sha] = result
                self.write('state.json', state)
            return result

    def status(self):
        with self.lock('state'):
            state = self.state()
            batches = {}
            for path in sorted(self.path('batches').glob('*.json')):
                sha = path.stem
                try:
                    valid_sha(sha)
                    batch = self.read('batches/' + path.name)
                    require(digest(batch) == sha, 'batch hash differs')
                    previous = state['releases'].get(sha)
                    if previous:
                        batches[sha] = {'status':previous['status']}
                        continue
                    self.validate_batch(batch, state)
                    require(not any(item.get('source_sha') == batch['source_sha'] and item['status'] in ('failed','publishing')
                                    for item in state['releases'].values()), 'failed source requires new fix')
                    batches[sha] = {'status':'eligible', 'groups':sorted(batch['groups']),
                                    'source_sha':batch['source_sha'], 'created_at':batch['created_at']}
                except (WorkflowError, KeyError, TypeError, ValueError):
                    batches[sha] = {'status':'ineligible'}
            return {'batches':batches, 'cursor':state['cursor'], 'feedback_count':len(state['seen']),
                    'groups':{gid:{k:value[k] for k in ('report_sha256','decision')} for gid,value in state['groups'].items()},
                    'releases':state['releases']}


def external_executor(path, expected_sha):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), 'executor must be explicit absolute regular file')
    valid_sha(expected_sha)
    def execute(mode, envelope):
        require(file_sha(path) == expected_sha, 'reviewed executor SHA changed')
        result = subprocess.run([str(path), mode], input=canonical(envelope), capture_output=True, timeout=1800)
        require(result.returncode == 0, 'executor failed; inspect its private recovery evidence')
        require(len(result.stdout) <= 5_000_000, 'executor result too large')
        try: return json.loads(result.stdout)
        except json.JSONDecodeError as exc: raise WorkflowError('executor did not return JSON evidence') from exc
    return execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path.home()/'.local/share/chickenbro-badcase'))
    sub = parser.add_subparsers(dest='command', required=True)
    scan = sub.add_parser('scan'); scan.add_argument('--limit', type=int, default=100)
    sub.add_parser('status'); sub.add_parser('prune')
    group = sub.add_parser('group'); group.add_argument('--file', required=True)
    decision = sub.add_parser('decide')
    for flag in ('group','report-sha','decision','approval-ref'): decision.add_argument('--'+flag, required=True)
    freeze = sub.add_parser('freeze'); freeze.add_argument('--file', required=True)
    release = sub.add_parser('release')
    for flag in ('batch','executor','executor-sha256'): release.add_argument('--'+flag, required=True)
    args = parser.parse_args()
    try:
        flow = Workflow(args.root)
        if args.command == 'scan': result = flow.scan(limit=args.limit)
        elif args.command == 'status': result = flow.status()
        elif args.command == 'prune': result = flow.prune()
        elif args.command == 'group':
            data = json.loads(Path(args.file).read_text())
            result = flow.group(data['id'], data['runs'], data['mechanism'], data['scope'])
        elif args.command == 'decide': result = flow.decide(args.group,args.report_sha,args.decision,args.approval_ref)
        elif args.command == 'freeze': result = {'batch_sha256':flow.freeze(json.loads(Path(args.file).read_text()))}
        else: result = flow.release(args.batch,external_executor(args.executor,args.executor_sha256))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except WorkflowError as exc:
        print(json.dumps({'status':'not_completed','reason':str(exc)}), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        # No untrusted content, SQL output, environment or subprocess stderr in public logs.
        print(json.dumps({'status':'not_completed','reason':'workflow gate or operation failed; inspect private state and validated inputs'}), file=sys.stderr)
        return 1


if __name__ == '__main__': sys.exit(main())

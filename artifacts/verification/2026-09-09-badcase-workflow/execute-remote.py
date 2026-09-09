"""Verified-byte executor; normal work has 1350 seconds, recovery reserves 300."""
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path('/var/tmp/chickenbro-badcase-release-20260909')
LIVE_BOSSES = frozenset((3470, 3445, 3455, 3497, 3420, 3421, 3429, 3492, 3379))


class DeadlineExceeded(BaseException):
    pass


class Budget:
    def __init__(self):
        self.started = time.monotonic()
        self.total_end = self.started + 1650
        self.end = self.started + 1350

    def remaining(self, cap=None):
        value = self.end - time.monotonic()
        if value <= 0:
            raise DeadlineExceeded('executor deadline reached')
        return min(value, cap) if cap is not None else value

    def arm(self, recovery=False):
        if recovery:
            self.end = self.total_end
        signal.signal(signal.SIGALRM, self.expired)
        signal.setitimer(signal.ITIMER_REAL, self.remaining())

    @staticmethod
    def expired(*_):
        raise DeadlineExceeded('executor deadline reached')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def private_output(name, value):
    path = ROOT / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(value, handle, ensure_ascii=False)


def verified_manifest(data):
    """Private immutable-by-convention snapshot; helper never reads unpinned input."""
    path = ROOT / 'manifest-verified.json'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            assert info.st_uid == 0 and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
            assert handle.read() == data, 'existing verified manifest differs'
    else:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    return path


def load_deploy(data):
    module = types.ModuleType('badcase_deploy_verified')
    module.__file__ = str(ROOT / 'deploy.py')
    exec(compile(data, module.__file__, 'exec'), module.__dict__)
    return module


def run_smoke(name, source, label, payload, budget):
    # Execute precisely the already verified bytes, never reopening Python files.
    output, error = ROOT / (label + '.jsonl'), ROOT / (label + '.stderr')
    fds = [os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600) for path in (output, error)]
    with os.fdopen(fds[0], 'wb') as out, os.fdopen(fds[1], 'wb') as err:
        os.fchmod(out.fileno(), 0o600)
        os.fchmod(err.fileno(), 0o600)
        done = subprocess.run(['/opt/chickenbro-runtime/bin/python', '-', 'production', str(source)],
                              input=payload[name], stdout=out, stderr=err, timeout=budget.remaining(1100))
    if done.returncode:
        raise RuntimeError('business smoke failed; private ' + label)
    rows = [json.loads(line) for line in output.read_text().splitlines() if line.strip()]
    if not rows or rows[-1].get('passed') is not True:
        raise RuntimeError('business smoke has no pass evidence')
    return rows[-1]


def realm(value):
    if isinstance(value, dict):
        value = value.get('name')
    return re.sub(r'[^\w]', '', str(value or '')).casefold()


def matched_cast(row, facts):
    # Anonymous leaderboard entries establish rank coverage, never a named actor.
    if (row.get('identityStatus') == 'anonymous' or row.get('analysisEligible') is False
            or not isinstance(row.get('server'), dict)
            or not realm(row['server'].get('name'))
            or not re.fullmatch(r'[A-Za-z0-9]{16}', str(row.get('report', {}).get('code', '')))):
        return False
    code, fight = row['report']['code'], str(row['report']['fightID'])
    same = [f for f in facts if f.get('reportCode') == code and str(f.get('fightId')) == fight]
    actors = {str(p['id']) for f in same for p in f.get('players', [])
              if 'id' in p and p.get('name', '').casefold() == row['name'].casefold()
              and realm(p.get('server')) == realm(row['server']['name'])}
    for fact in same:
        source = str(fact.get('sourceId'))
        if source not in actors:
            continue
        if any(isinstance(e.get('total'), (int, float)) and e['total'] > 0
               for e in fact.get('casts', {}).get('entries', [])):
            return True
        if any(e.get('type') == 'cast' and str(e.get('sourceID')) == source for e in fact.get('events', [])):
            return True
    return False


def validate_cases(result, release):
    cases = result.get('cases', [])
    assert len(cases) == 2 and {c['case'] for c in cases} == {'top10', 'top100'}
    summaries = []
    with release.connect() as conn:
        for case in cases:
            wanted = 10 if case['case'] == 'top10' else 100
            assert type(case.get('seconds')) in (int, float) and 0 < case['seconds'] <= 480, 'completion deadline exceeded'
            answer = case['answer']
            assert len(answer) > 200 and re.search(r'https://www\.warcraftlogs\.com/reports/[A-Za-z0-9]{16}', answer)
            run = conn.execute('SELECT status FROM chat.agent_runs WHERE id=%s', (case['runId'],)).fetchone()
            assert run and run[0] == 'succeeded'
            results = conn.execute("SELECT operation,result_json FROM chat.tool_results WHERE run_id=%s AND state='completed'", (case['runId'],)).fetchall()
            ranks = [r for op, r in results if op == 'source.warcraftlogs_rankings' and r.get('rankings')]
            reports = []
            for operation, packet in results:
                if operation not in ('source.warcraftlogs', 'source.warcraftlogs_batch'):
                    continue
                members = packet.get('results', []) if operation.endswith('_batch') else [packet]
                reports.extend(r for r in members if r.get('status') == 'verified' and r.get('facts'))
            facts = [f for r in reports for f in r['facts']]
            by_boss = {boss: [] for boss in LIVE_BOSSES}
            for packet in ranks:
                scope = packet['scope']
                assert (scope['zoneId'] == 53 and scope['difficulty'] == 4 and scope['className'] == 'Druid'
                        and scope['specName'] == 'Feral' and scope['region'] == 'world' and scope['metric'] == 'dps'
                        and scope['partitionName'] == '12.1' and scope['encounterId'] in LIVE_BOSSES), 'wrong leaderboard scope'
                # Each packet is an independent leaderboard snapshot. Never join
                # partial packets or require a mutable live board to stay frozen.
                rows = [row for row in packet['rankings'] if 1 <= row['rank'] <= wanted]
                if len(rows) == wanted and {row['rank'] for row in rows} == set(range(1, wanted + 1)):
                    by_boss[scope['encounterId']].append(sorted(rows, key=lambda row: row['rank']))
            snapshots = []
            for boss, complete in sorted(by_boss.items()):
                assert complete, 'incomplete requested ranking coverage: ' + str(boss)
                candidates = [(rows, [row['rank'] for row in rows if matched_cast(row, facts)]) for rows in complete]
                selected = next(((rows, matched) for rows, matched in candidates if matched), None)
                assert selected is not None, 'missing matched boss cast evidence: ' + str(boss)
                rows, matched = selected
                distinct = {digest(snapshot) for snapshot in complete}
                snapshots.append({'bossId': boss, 'completeSnapshots': len(complete),
                                  'distinctCompleteSnapshots': len(distinct), 'snapshotDriftObserved': len(distinct) > 1,
                                  'selectedSnapshotSha256': digest(rows), 'matchedRanks': matched,
                                  'anonymousEntries': sum(row.get('identityStatus') == 'anonymous' for row in rows),
                                  'namedEntries': sum(row.get('identityStatus') != 'anonymous' for row in rows)})
            assert all(case['checks'][key] for key in ('terminal', 'history', 'ownerIsolation', 'idempotency', 'detached'))
            summaries.append({'case': case['case'], 'runId': case['runId'], 'seconds': case['seconds'],
                              'rankingPackets': len(ranks), 'verifiedReportPackets': len(reports),
                              'bosses': sorted(by_boss), 'requestedRanksPerBoss': wanted, 'rankingSnapshots': snapshots,
                              'bossesWithMatchedCasts': len(by_boss), 'answerSha256': hashlib.sha256(answer.encode()).hexdigest(),
                              'semanticReview': 'automatic provenance/coverage checks; human review separately recorded'})
    return summaries


def validate_semantic_review(record, identity, cases, batch_sha):
    """Bind the independent review to the actual live answer bytes and runs."""
    assert isinstance(record, dict) and record.get('status') == 'passed', 'live semantic review failed'
    assert all(record.get(k) == v for k, v in identity.items()), 'semantic runtime differs'
    assert record.get('batch_sha256') == batch_sha, 'semantic batch differs'
    assert isinstance(record.get('reviewer'), str) and 0 < len(record['reviewer'].strip()) <= 500
    try:
        observed = datetime.fromisoformat(record['observed_at'])
        assert observed.tzinfo is not None
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        assert -30 <= age <= 600, 'semantic review stale'
    except (KeyError, TypeError, ValueError):
        raise AssertionError('semantic review timestamp invalid') from None
    rows = record.get('cases')
    assert isinstance(rows, list) and len(rows) == len(cases) == 2, 'semantic cases missing'
    assert all(isinstance(r, dict) for r in rows)
    assert {r.get('case') for r in rows} == {c['case'] for c in cases}, 'semantic cases differ'
    for case in cases:
        reviewed = next(r for r in rows if r['case'] == case['case'])
        assert all(reviewed.get(k) == case[k] for k in ('runId', 'answerSha256')), 'semantic answer differs'
        criteria = reviewed.get('criteria')
        assert isinstance(criteria, dict) and all(criteria.get(k) == 'passed' for k in ('acquisition', 'analysis', 'completion')), 'semantic criterion failed'
        assert isinstance(reviewed.get('notes'), str) and 0 < len(reviewed['notes'].strip()) <= 16000, 'semantic reasoning missing'
    return digest(record)


def await_semantic_review(identity, cases, batch_sha, budget):
    # An orchestrating reviewer writes an atomic root-owned0600 record only after
    # inspecting these actual live receipts. No record or a negative verdict is
    # a release failure, traversing the same bounded recovery path.
    private_output('semantic-review-request.json', {**identity, 'batch_sha256': batch_sha,
                   'cases': cases, 'requested_at': stamp()})
    end = time.monotonic() + min(240, budget.remaining())
    while True:
        try:
            fd = os.open(ROOT / 'live-semantic-review.json', os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            assert time.monotonic() < end, 'live semantic review missing'
            time.sleep(min(2, budget.remaining(), max(0.01, end - time.monotonic())))
            continue
        with os.fdopen(fd, 'rb') as handle:
            info = os.fstat(handle.fileno())
            assert info.st_uid == 0 and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
            raw = handle.read(65537)
        assert len(raw) <= 65536, 'semantic review oversized'
        record = json.loads(raw)
        return validate_semantic_review(record, identity, cases, batch_sha)


def web_verify(manifest, budget):
    for name, expected in manifest['webFiles'].items():
        with urlopen(Request('https://www.chickenbro.cloud/' + name, headers={'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'}), timeout=budget.remaining(20)) as response:
            assert hashlib.sha256(response.read()).hexdigest() == expected, 'public Web bytes differ'
    return len(manifest['webFiles'])


def safe_failure(error, stage):
    # Never serialize exception text, args, SQL, DSNs, paths or traceback locals.
    types_seen, seen = [], set()
    current = error
    while current is not None and id(current) not in seen and len(types_seen) < 8:
        seen.add(id(current))
        name = type(current).__name__
        types_seen.append(name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception')
        current = current.__cause__ or current.__context__
    code = 'STAGE_FAILED'
    if 'OperationalError' in types_seen:
        code = 'DATABASE_CONNECTION_FAILED'
    elif any(name in types_seen for name in ('DeadlineExceeded', 'TimeoutExpired')):
        code = 'DEADLINE_EXCEEDED'
    elif 'AssertionError' in types_seen:
        code = 'ACCEPTANCE_CHECK_FAILED'
    return {'stage': stage, 'errorCode': code, 'errorType': types_seen[0], 'causeTypes': types_seen}


def execute(envelope, mode, payload):
    budget = Budget()
    budget.arm()
    deploy = load_deploy(payload['deploy.py'])
    path = verified_manifest(payload['manifest.json'])
    release = deploy.Release(path)
    manifest = release.m
    def checked_run(action):
        assert path.read_bytes() == payload['manifest.json'], 'verified manifest drift'
        budget.remaining()
        return release.run(action)
    identity = {'source_sha': manifest['sourceCommit'], 'baseline_sha': manifest['expectedBackend'].rsplit('-', 1)[-1],
                'build_sha256': digest({**manifest['baseInventory'], **manifest['files']}),
                'config_sha256': digest(manifest['environmentHashes']),
                'diff_sha256': digest({'files': manifest['files'], 'baseHashes': manifest['baseHashes']})}
    assert mode in ('preflight', 'release')
    assert all(envelope['batch'][key] == value for key, value in identity.items()), 'batch/manifest identities differ'
    stage = 'preflight'
    with open('/run/lock/chickenbro-release.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            checked_run('preflight')
            if mode == 'preflight':
                return {'batch_sha256': envelope['batch_sha256'], 'baseline_sha': identity['baseline_sha'], 'diff_sha256': identity['diff_sha256'], 'clean': True}
            stage = 'promote'
            checked_run('promote')
            stage = 'ranking_smoke'
            ranking_result = run_smoke('http-smoke.py', release.target, 'live-rankings', payload, budget)
            stage = 'ranking_validation'
            cases = validate_cases(ranking_result, release)
            stage = 'general_smoke'
            general = run_smoke('general-smoke.py', release.target, 'live-general', payload, budget)
            stage = 'runtime_verify'
            checked_run('verify')
            stage = 'web_verify'
            count = web_verify(manifest, budget)
            stage = 'semantic_review'
            semantic_sha = await_semantic_review(identity, cases, envelope['batch_sha256'], budget)
            stage = 'observation'
            observation_start = time.monotonic()
            for _ in range(4):
                checked_run('verify')
                with release.connect() as conn:
                    stuck = conn.execute("SELECT count(*) FROM chat.executions WHERE stage IN ('pending','running') AND created_at<now()-interval '10 minutes'").fetchone()[0]
                assert stuck == 0, 'stuck executions during observation'
                time.sleep(min(10, budget.remaining()))
            result = {'batch_sha256': envelope['batch_sha256'], **identity, 'status': 'passed', 'observed_at': stamp(),
                      'checks': {key: True for key in ('real_chat_terminal', 'history_readback', 'affected_tools', 'owner_isolation', 'web_artifact_verified', 'drained_without_kill', 'api_worker_identity', 'observation_passed')},
                      'details': {'cases': cases, 'general': {k: v for k, v in general.items() if k != 'cases'},
                                  'semanticReviewSha256': semantic_sha, 'publicWebFiles': count, 'observationSeconds': round(time.monotonic() - observation_start, 2),
                                  'source': str(release.target), 'web': str(release.web)}}
            stage = 'evidence_write'
            private_output('live-evidence.json', result)
            return result
        except BaseException as failure:
            if mode == 'preflight':
                private_output('preflight-failure.json', {'status': 'failed', **safe_failure(failure, stage), 'observed_at': stamp()})
                raise RuntimeError('preflight failed; inspect private failure evidence') from None
            recovery = {'status': 'failed', **safe_failure(failure, stage), 'observed_at': stamp()}
            try:
                stage = 'recovery_admission'
                budget.arm(recovery=True)
                if release.link.resolve() == release.target:
                    stage = 'recovery_rollback'
                    checked_run('rollback')
                else:
                    assert release.link.resolve() == release.base, 'foreign pointer prevents recovery'
                stage = 'recovery_smoke'
                recovery['business'] = run_smoke('general-smoke.py', release.base, 'recovery-general', payload, budget)
                recovery['status'] = 'recovery_verified'
            except BaseException as error:
                recovery['recoveryFailure'] = safe_failure(error, stage)
            private_output('recovery-result.json', recovery)
            raise RuntimeError('release did not pass; inspect private recovery result') from None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)


def main():
    # This file is intentionally not a standalone trusted entry point.
    payload = globals().get('VERIFIED_PAYLOAD')
    assert payload is not None, 'verified local bootstrap required'
    result = execute(globals()['REQUEST_ENVELOPE'], sys.argv[1], payload)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open

ROOT = Path(__file__).resolve().parents[1] / 'artifacts/verification/2026-09-09-badcase-workflow'


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


local = load('badcase_local_test', 'execute.py')
remote = load('badcase_remote_test', 'execute-remote.py')


class ExecutorTest(unittest.TestCase):
    def fixture(self):
        cases, results = [], {}
        for case, wanted in (('top10', 10), ('top100', 100)):
            cases.append({'case': case, 'runId': case, 'seconds': 1,
                          'answer': 'Actual sampled evidence. ' * 15 + 'https://www.warcraftlogs.com/reports/ABCDEFGHIJKLMNOP',
                          'checks': {k: True for k in ('terminal', 'history', 'ownerIsolation', 'idempotency', 'detached')}})
            packets = []
            for boss in remote.LIVE_BOSSES:
                rows = [{'rank': rank, 'name': 'Player', 'server': {'name': 'Realm'},
                         'report': {'code': 'ABCDEFGHIJKLMNOP', 'fightID': boss}} for rank in range(1, wanted + 1)]
                packets.append(('source.warcraftlogs_rankings', {'scope': {'encounterId': boss, 'zoneId': 53,
                    'difficulty': 4, 'className': 'Druid', 'specName': 'Feral', 'region': 'world', 'metric': 'dps',
                    'partitionName': '12.1'}, 'rankings': rows}))
                packets.append(('source.warcraftlogs', {'status': 'verified', 'facts': [{
                    'reportCode': 'ABCDEFGHIJKLMNOP', 'fightId': str(boss), 'sourceId': 5,
                    'players': [{'id': 5, 'name': 'Player', 'server': 'Realm'}],
                    'casts': {'entries': [{'total': 10}]}}]}))
            results[case] = packets
        release = MagicMock()
        conn = release.connect.return_value.__enter__.return_value
        def execute(sql, args):
            result = Mock()
            result.fetchone.return_value = ('succeeded',)
            result.fetchall.return_value = results[args[0]]
            return result
        conn.execute.side_effect = execute
        return {'cases': cases}, release, results

    def semantic_fixture(self):
        identity = {'source_sha': 'a' * 40, 'baseline_sha': 'b' * 40,
                    'build_sha256': 'c' * 64, 'config_sha256': 'd' * 64, 'diff_sha256': 'e' * 64}
        cases = [{'case': name, 'runId': name + '-unique', 'answerSha256': name[0] * 64}
                 for name in ('top10', 'top100')]
        record = {**identity, 'batch_sha256': 'f' * 64, 'status': 'passed',
                  'observed_at': remote.stamp(), 'reviewer': 'independent semantic reviewer',
                  'cases': [{**case, 'criteria': {k: 'passed' for k in ('acquisition', 'analysis', 'completion')},
                             'notes': 'Reviewed actual answer against actual ranking and cast receipts.'} for case in cases]}
        return identity, cases, record

    def test_live_semantic_review_requires_exact_runtime_runs_and_answers(self):
        identity, cases, record = self.semantic_fixture()
        self.assertEqual(remote.validate_semantic_review(record, identity, cases, 'f' * 64), remote.digest(record))
        for field in ('source_sha', 'batch_sha256', 'build_sha256'):
            bad = copy.deepcopy(record); bad[field] = 'wrong'
            with self.subTest(field=field), self.assertRaises(AssertionError):
                remote.validate_semantic_review(bad, identity, cases, 'f' * 64)
        for field in ('runId', 'answerSha256'):
            bad = copy.deepcopy(record); bad['cases'][0][field] = 'other'
            with self.subTest(field=field), self.assertRaises(AssertionError):
                remote.validate_semantic_review(bad, identity, cases, 'f' * 64)

    def test_live_semantic_failure_missing_case_stale_or_empty_review_blocks(self):
        identity, cases, record = self.semantic_fixture()
        invalid = []
        for key, value in (('status','failed'), ('observed_at','2000-01-01T00:00:00+00:00'), ('reviewer','')):
            bad=copy.deepcopy(record);bad[key]=value;invalid.append(bad)
        bad=copy.deepcopy(record);bad['cases'].pop();invalid.append(bad)
        bad=copy.deepcopy(record);bad['cases'][0]['criteria']['analysis']='failed';invalid.append(bad)
        bad=copy.deepcopy(record);bad['cases'][0]['notes']='';invalid.append(bad)
        bad=copy.deepcopy(record);bad['cases'][1]=copy.deepcopy(bad['cases'][0]);invalid.append(bad)
        for bad in invalid:
            with self.subTest(record=bad), self.assertRaises(AssertionError):
                remote.validate_semantic_review(bad, identity, cases, 'f' * 64)

    def test_missing_live_semantic_review_is_bounded_failure(self):
        identity, cases, _ = self.semantic_fixture()
        budget = Mock(); budget.remaining.return_value = 500
        with patch.object(remote, 'private_output') as request, \
             patch.object(remote.os, 'open', side_effect=FileNotFoundError), \
             patch.object(remote.time, 'monotonic', side_effect=[0, 241]), \
             patch.object(remote.time, 'sleep') as sleep:
            with self.assertRaisesRegex(AssertionError, 'semantic review missing'):
                remote.await_semantic_review(identity, cases, 'f' * 64, budget)
            request.assert_called_once()
            sleep.assert_not_called()

    def test_all_nine_boss_rank_coverage_and_casts_pass(self):
        result, release, _ = self.fixture()
        checked = remote.validate_cases(result, release)
        self.assertEqual([c['requestedRanksPerBoss'] for c in checked], [10, 100])
        self.assertTrue(all(c['bossesWithMatchedCasts'] == 9 for c in checked))

    def test_anonymous_rank_counts_coverage_but_never_matched_casts(self):
        result, release, packets = self.fixture()
        row = packets['top100'][0][1]['rankings'][88]
        row.update(name='Anonymous', server=None, identityStatus='anonymous', analysisEligible=False,
                   report={'code': 'a:ABCDEFGHIJKLMNOP', 'fightID': row['report']['fightID']})
        self.assertFalse(remote.matched_cast(row, []))
        checked = remote.validate_cases(result, release)[1]
        snapshot = next(s for s in checked['rankingSnapshots']
                        if s['bossId'] == packets['top100'][0][1]['scope']['encounterId'])
        self.assertEqual(snapshot['anonymousEntries'], 1)
        self.assertEqual(snapshot['namedEntries'], 99)
        self.assertNotIn(89, snapshot['matchedRanks'])

    def test_anonymous_rows_cannot_satisfy_boss_analysis_even_with_casts(self):
        result, release, packets = self.fixture()
        rows = packets['top10'][0][1]['rankings']
        for row in rows:
            row.update(name='Anonymous', server=None, identityStatus='anonymous', analysisEligible=False,
                       report={'code': 'a:ABCDEFGHIJKLMNOP', 'fightID': row['report']['fightID']})
        fact = packets['top10'][1][1]['facts'][0]
        fact.update(reportCode='a:ABCDEFGHIJKLMNOP')
        fact['players'] = [{'id': 5, 'name': 'Anonymous', 'server': None}]
        with self.assertRaisesRegex(AssertionError, 'matched boss cast'):
            remote.validate_cases(result, release)

    def test_over_deadline_business_answer_is_not_a_pass(self):
        result, release, _ = self.fixture()
        result['cases'][0]['seconds'] = 481
        with self.assertRaisesRegex(AssertionError, 'completion deadline'):
            remote.validate_cases(result, release)

    def test_missing_boss_or_rank_fails(self):
        for remove_boss in (True, False):
            result, release, packets = self.fixture()
            if remove_boss:
                packets['top10'].pop(0)
            else:
                packets['top100'][0][1]['rankings'].pop()
            with self.assertRaisesRegex(AssertionError, 'ranking coverage'):
                remote.validate_cases(result, release)

    def test_complete_repeated_snapshot_drift_is_allowed_and_disclosed(self):
        result, release, packets = self.fixture()
        newer = copy.deepcopy(packets['top100'][0])
        for row in newer[1]['rankings'][52:]:
            row['name'] = 'NewPlayer'
        packets['top100'].append(newer)
        checked = remote.validate_cases(result, release)[1]
        boss = newer[1]['scope']['encounterId']
        snapshot = next(item for item in checked['rankingSnapshots'] if item['bossId'] == boss)
        self.assertEqual(snapshot['completeSnapshots'], 2)
        self.assertEqual(snapshot['distinctCompleteSnapshots'], 2)
        self.assertTrue(snapshot['snapshotDriftObserved'])
        self.assertIn(1, snapshot['matchedRanks'])

    def test_incomplete_packets_cannot_be_combined_into_full_coverage(self):
        result, release, packets = self.fixture()
        original = packets['top100'][0]
        left, right = copy.deepcopy(original), copy.deepcopy(original)
        left[1]['rankings'] = left[1]['rankings'][:50]
        right[1]['rankings'] = right[1]['rankings'][50:]
        packets['top100'][0] = left
        packets['top100'].append(right)
        with self.assertRaisesRegex(AssertionError, 'ranking coverage'):
            remote.validate_cases(result, release)

    def test_matching_partial_cannot_supply_evidence_for_unmatched_complete_snapshot(self):
        result, release, packets = self.fixture()
        partial = copy.deepcopy(packets['top100'][0])
        partial[1]['rankings'] = partial[1]['rankings'][:10]
        for row in packets['top100'][0][1]['rankings']:
            row['name'] = 'UnmatchedPlayer'
        packets['top100'].append(partial)
        with self.assertRaisesRegex(AssertionError, 'matched boss cast'):
            remote.validate_cases(result, release)

    def test_wrong_report_fight_actor_realm_or_empty_cast_fails(self):
        for field in ('fightId', 'sourceId', 'realm', 'casts'):
            result, release, packets = self.fixture()
            fact = packets['top10'][1][1]['facts'][0]
            if field == 'realm':
                fact['players'][0]['server'] = 'Other'
            elif field == 'casts':
                fact['casts'] = {'entries': []}
            else:
                fact[field] = 'wrong'
            with self.assertRaisesRegex(AssertionError, 'matched boss cast'):
                remote.validate_cases(result, release)

    def test_verified_batch_members_count_even_when_other_member_partial(self):
        result, release, packets = self.fixture()
        for group in packets.values():
            for index in range(1, len(group), 2):
                group[index] = ('source.warcraftlogs_batch', {'status': 'partial',
                    'results': [group[index][1], {'status': 'partial', 'facts': []}]})
        self.assertEqual(len(remote.validate_cases(result, release)), 2)

    def test_ptr_or_wrong_scope_rejected(self):
        result, release, packets = self.fixture()
        packets['top10'][0][1]['scope']['zoneId'] = 54
        with self.assertRaisesRegex(AssertionError, 'scope'):
            remote.validate_cases(result, release)

    def test_budget_reserves_three_hundred_seconds(self):
        with patch.object(remote.time, 'monotonic', return_value=100):
            budget = remote.Budget()
        with patch.object(remote.time, 'monotonic', return_value=1200):
            self.assertEqual(budget.remaining(1100), 250)
            with patch.object(remote.signal, 'signal'), patch.object(remote.signal, 'setitimer'):
                budget.arm(recovery=True)
            self.assertEqual(budget.remaining(), 550)
        with patch.object(remote.time, 'monotonic', return_value=1751):
            with self.assertRaises(remote.DeadlineExceeded):
                budget.remaining()

    def test_smoke_executes_verified_bytes_with_remaining_timeout(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(remote, 'ROOT', Path(directory)):
            budget = Mock()
            budget.remaining.return_value = 123
            def run(args, **kwargs):
                self.assertEqual(args[1], '-')
                self.assertEqual(kwargs['input'], b'print("approved")')
                self.assertEqual(kwargs['timeout'], 123)
                kwargs['stdout'].write(b'{"passed":true}\n')
                return Mock(returncode=0)
            with patch.object(remote.subprocess, 'run', side_effect=run):
                self.assertTrue(remote.run_smoke('http-smoke.py', '/source', 'test',
                                               {'http-smoke.py': b'print("approved")'}, budget)['passed'])

    def test_source_allows_docs_followup_with_identical_server_tree(self):
        manifest = {'sourceCommit': 'a' * 40, 'files': {'server/x.py': hashlib.sha256(b'x').hexdigest()}}
        answers = ['same-tree\n', 'same-tree\n', 'server/x.py\n', b'x']
        with patch.object(local.subprocess, 'check_output', side_effect=answers) as output, patch.object(local.subprocess, 'run'):
            local.validate_source({'source_sha': 'a' * 40, 'baseline_sha': 'b' * 40}, manifest)
        self.assertEqual(output.call_args_list[0].args[0][-1], 'HEAD:server')

    def test_source_rejects_changed_server_tree(self):
        with patch.object(local.subprocess, 'check_output', side_effect=['new', 'old']):
            with self.assertRaisesRegex(AssertionError, 'server tree'):
                local.validate_source({'source_sha': 'a' * 40, 'baseline_sha': 'b' * 40}, {'sourceCommit': 'a' * 40})

    def test_remote_requires_verified_bootstrap(self):
        with self.assertRaisesRegex(AssertionError, 'bootstrap'):
            remote.main()

    def test_payload_pins_fail_closed_until_frozen(self):
        with patch.object(local.sys, 'argv', ['execute.py', 'preflight']), patch.object(local, 'PAYLOAD_SHA256', {'deploy.py': ''}):
            with self.assertRaisesRegex(AssertionError, 'digests'):
                local.main()

    def test_bootstrap_rejects_tamper_and_executes_read_bytes_after_disk_change(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            code = b'print("verified bytes executed")'
            path = root / 'execute-remote.py'
            path.write_bytes(code)
            pins = {'execute-remote.py': hashlib.sha256(code).hexdigest()}
            folder_stat = SimpleNamespace(st_mode=0o40700, st_uid=0)
            file_stat = SimpleNamespace(st_mode=0o100600, st_uid=0, st_nlink=1)
            def request(_):
                path.write_bytes(b'raise RuntimeError("unverified disk bytes")')
                return {}
            args = ['bootstrap', str(root), json.dumps(pins), 'preflight']
            with patch.object(local.sys, 'argv', args), patch.object(Path, 'lstat', return_value=folder_stat), \
                 patch.object(os, 'fstat', return_value=file_stat), patch.object(json, 'load', side_effect=request), \
                 patch('builtins.print') as printed:
                exec(local.BOOTSTRAP, {})
                printed.assert_called_once_with('verified bytes executed')
            with patch.object(local.sys, 'argv', args), patch.object(Path, 'lstat', return_value=folder_stat), \
                 patch.object(os, 'fstat', return_value=file_stat):
                with self.assertRaisesRegex(AssertionError, 'hash mismatch'):
                    exec(local.BOOTSTRAP, {})

    def test_deadline_passes_through_real_helper_ready_and_promote(self):
        spec = importlib.util.spec_from_file_location('real_badcase_deploy', ROOT.parents[2] / 'scripts/badcase_deploy.py')
        deploy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deploy)
        release = object.__new__(deploy.Release)
        with patch.object(deploy, 'urlopen', side_effect=remote.DeadlineExceeded()), \
             patch.object(deploy.time, 'sleep') as sleep:
            with self.assertRaises(remote.DeadlineExceeded):
                release.ready()
            sleep.assert_not_called()
        release.base, release.target = Path('/base'), Path('/target')
        with patch.object(release, 'baseline'), patch.object(release, 'staged'), \
             patch.object(release, 'activate', side_effect=remote.DeadlineExceeded()) as activate:
            with self.assertRaises(remote.DeadlineExceeded):
                release.promote()
            self.assertEqual(activate.call_count, 1)

    def test_local_private_output_enforces_mode_and_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.stdout'
            path.write_text('previous')
            path.chmod(0o644)
            local.private_text(path, 'current')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_text(), 'current')
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                local.private_text(link, 'must reject')
            self.assertEqual(path.read_text(), 'current')

    def test_ssh_timeout_retains_private_evidence_without_success(self):
        data = b'{}'
        pins = {name: hashlib.sha256(data).hexdigest() for name in local.PAYLOAD_SHA256}
        failure = local.subprocess.TimeoutExpired('ssh', 1700, output=b'partial', stderr=b'network')
        with patch.object(local.sys, 'argv', ['execute.py', 'release']), \
             patch.object(local, 'PAYLOAD_SHA256', pins), patch.object(Path, 'read_bytes', return_value=data), \
             patch.object(local.json, 'load', return_value={'batch': {}}), \
             patch.object(local, 'validate_source'), patch.object(local.subprocess, 'run', side_effect=failure) as run, \
             patch.object(local, 'private_text') as private:
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                local.main()
            self.assertIn('ControlPath=/tmp/badcase-ssh-%C', run.call_args.args[0])
            self.assertEqual(private.call_args_list[0].args[1], 'partial')
            self.assertIn('network', private.call_args_list[1].args[1])

    def test_safe_failure_records_cause_code_without_exception_secrets(self):
        OperationalError = type('OperationalError', (Exception,), {})
        original = OperationalError('password=secret dsn=postgres://private')
        outer = RuntimeError('private failure details')
        outer.__cause__ = original
        result = remote.safe_failure(outer, 'promote')
        self.assertEqual(result['errorCode'], 'DATABASE_CONNECTION_FAILED')
        self.assertEqual(result['causeTypes'], ['RuntimeError', 'OperationalError'])
        self.assertEqual(result['stage'], 'promote')
        self.assertNotIn('secret', json.dumps(result))
        self.assertNotIn('private', json.dumps(result))

    def test_system_exit_after_promotion_runs_recovery(self):
        manifest = {'sourceCommit': 'a' * 40, 'expectedBackend': '/base-' + 'b' * 40,
                    'baseInventory': {}, 'files': {}, 'baseHashes': {}, 'environmentHashes': {}}
        release = Mock(m=manifest, target=Path('/target'), base=Path('/base'), web=Path('/web'))
        pointer = [release.base]
        release.link.resolve.side_effect = lambda: pointer[0]
        def run(action):
            if action == 'promote': pointer[0] = release.target
            if action == 'rollback': pointer[0] = release.base
        release.run.side_effect = run
        identity = {'source_sha': 'a' * 40, 'baseline_sha': 'b' * 40,
                    'build_sha256': remote.digest({}), 'config_sha256': remote.digest({}),
                    'diff_sha256': remote.digest({'files': {}, 'baseHashes': {}})}
        payload = {'manifest.json': b'approved', 'deploy.py': b'approved'}
        path = Mock()
        path.read_bytes.return_value = b'approved'
        with patch.object(remote, 'Budget') as budget, \
             patch.object(remote, 'load_deploy', return_value=Mock(Release=Mock(return_value=release))), \
             patch.object(remote, 'verified_manifest', return_value=path), \
             patch.object(remote, 'open', mock_open(), create=True), patch.object(remote.fcntl, 'flock'), \
             patch.object(remote.signal, 'setitimer'), \
             patch.object(remote, 'run_smoke', side_effect=[SystemExit(1), {'passed': True}]), \
             patch.object(remote, 'private_output') as evidence:
            with self.assertRaisesRegex(RuntimeError, 'did not pass'):
                remote.execute({'batch': identity, 'batch_sha256': 'batch'}, 'release', payload)
            budget.return_value.arm.assert_any_call(recovery=True)
            self.assertEqual(pointer[0], release.base)
            self.assertEqual(evidence.call_args.args[1]['status'], 'recovery_verified')
            self.assertEqual(evidence.call_args.args[0], 'recovery-result.json')


if __name__ == '__main__':
    unittest.main()

"""Read deployed command identities and render an existing v8 cache; no sends."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path('/opt/chickenbro-qq-official-candidate-20261014')
sys.path.insert(0, str(root))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    return subprocess.check_output(args, text=True).strip()


manifest = json.loads(Path('/tmp/qq-caiji-command-runtime-20261016.json').read_text())
receipt = json.loads(Path('/var/lib/chickenbro/qq-official/caiji-command-deployment-20261016.json').read_text())
for f in manifest['files']:
    assert sha(root / f['path']) == f['sha256'], f['path']
health = json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
assert health['observedAt'] > time.time() - 90
assert health['gatewayReady'] and health['queryOnly'] and health['allowedGroupCount'] == 1
assert health['battlePresentation'] == 'single_summary_evidence_narrative_zhcn_v8'
assert health['defaultReplyPresentation'] == 'bounded-model-guidance-v2'
assert health['battleReviewCommand'] == '/战斗分析-菜鸡'
assert health['guidanceModelEnabled'] and health['guidanceToolAccess'] is False
for service, pid in receipt['unchangedServicePids'].items():
    assert run(['systemctl', 'show', service, '-p', 'MainPID', '--value']) == pid
    assert run(['systemctl', 'is-active', service]) == 'active'
assert sha(Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')) == receipt['webSourceSha256Unchanged']
assert sha(Path('/etc/chickenbro-qq-official/channel.json')) == receipt['configSha256Unchanged']
from server.app.channels.qq_official.query_commands import HELP, parse_query
from server.app.channels.qq_official.battle_commands import format_battle
from server.app.channels.qq_official.battle_narrative import BattleNarrative
from server.app.channels.qq_official.guidance import ALLOWED_COMMANDS

assert '/战斗分析-菜鸡' in HELP and '/战斗详情-毒瘤' not in HELP
assert len(HELP) == 489 and HELP.index('## 角色查询') < HELP.index('## 战斗分析')
assert asdict(parse_query('/战斗分析-菜鸡')) == asdict(parse_query('/战斗详情-毒瘤'))
assert '/战斗分析-菜鸡' in ALLOWED_COMMANDS and '/战斗详情-毒瘤' not in ALLOWED_COMMANDS
sql = "SELECT result_packet FROM qq_channel.official_queries WHERE result_packet->'narrative'->>'version'='battle-narrative-v8' AND result_packet->'narrative'->>'status'='ready' ORDER BY completed_at DESC LIMIT 1"
packet = json.loads(run(['runuser', '-u', 'postgres', '--', 'psql', '-d', 'chickenbro_qq_official_candidate', '-Atc', sql]))
previous = copy.deepcopy(packet['narrative'])


class NoModel:
    calls = 0

    def stream(self, **kwargs):
        self.calls += 1
        raise AssertionError('cached command rename must not regenerate battle analysis')


adapter = NoModel()
BattleNarrative(adapter).apply(packet)
assert adapter.calls == 0 and packet['narrative'] == previous
summary = format_battle(packet, 'battle_summary')
review = format_battle(packet, 'battle_review')
assert '/战斗分析-菜鸡' in summary and '/战斗详情-毒瘤' not in summary
assert '战斗分析·菜鸡' in review.splitlines()[0]
assert max(len(summary), len(review)) <= 1200
print(json.dumps({'runtimeFilesMatched': len(manifest['files']), 'gatewayReady': True,
    'queryOnly': True, 'allowedGroupCount': 1, 'battlePresentation': health['battlePresentation'],
    'defaultReplyPresentation': health['defaultReplyPresentation'], 'guidanceToolAccess': False,
    'reviewCommand': health['battleReviewCommand'], 'legacyCommandCompatible': True,
    'groupedHelpCharacters': len(HELP), 'cachedBattle': {'reportCode': packet['reportCode'],
        'fightId': packet['fightId'], 'narrativeVersion': packet['narrative']['version'],
        'reviewTitle': review.splitlines()[0], 'summaryFooter': summary.splitlines()[-1],
        'lengths': {'summary': len(summary), 'review': len(review)}, 'additionalModelCalls': adapter.calls},
    'unchangedServicePids': receipt['unchangedServicePids'], 'candidateDatabaseWrites': 0,
    'qqValidationMessagesSent': 0, 'manualGroupAcceptance': 'pending_user_test'}, ensure_ascii=False, indent=2))

"""Read deployed code and health; no QQ messages or Candidate DB writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path('/opt/chickenbro-qq-official-candidate-20261014')
sys.path.insert(0, str(root))
from server.app.channels.qq_official.query_commands import HELP, INTRO, QueryInputError, parse_query


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(Path('/tmp/qq-default-reply-runtime-20261016.json').read_text())
receipt = json.loads(Path('/var/lib/chickenbro/qq-official/default-reply-deployment-20261016.json').read_text())
for f in manifest['files']:
    assert sha(root / f['path']) == f['sha256'], f['path']
health = json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
assert health['observedAt'] > time.time() - 90
assert health['gatewayReady'] and health['queryOnly'] and health['allowedGroupCount'] == 1
assert health['battlePresentation'] == 'single_summary_evidence_narrative_zhcn_v8'
for service, pid in receipt['unchangedServicePids'].items():
    assert subprocess.check_output(['systemctl', 'show', service, '-p', 'MainPID', '--value'], text=True).strip() == pid
    assert subprocess.check_output(['systemctl', 'is-active', service], text=True).strip() == 'active'
assert sha(Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')) == receipt['webSourceSha256Unchanged']
assert sha(Path('/etc/chickenbro-qq-official/channel.json')) == receipt['configSha256Unchanged']
replies = {}
for text in ('你都能干啥？', '你能做什么', '你好', '/未知命令'):
    try:
        parse_query(text)
    except QueryInputError as error:
        replies[text] = str(error)
        assert str(error) == INTRO and len(str(error)) <= 150
    else:
        raise AssertionError('unexpected query admission')
assert parse_query('/角色查询 Giannis 白银之手').kind == 'character'
assert '/战斗分析 WCL报告链接' in HELP and '/角色查询 角色名 服务器名' in HELP
print(json.dumps({'runtimeFilesMatched': len(manifest['files']), 'gatewayReady': True,
    'queryOnly': True, 'allowedGroupCount': 1, 'battlePresentation': health['battlePresentation'],
    'defaultReplyCharacters': len(INTRO), 'defaultReplies': replies, 'helpCharacters': len(HELP),
    'fullHelpPreserved': True, 'unchangedServicePids': receipt['unchangedServicePids'],
    'qqValidationMessagesSent': 0, 'manualGroupAcceptance': 'pending_user_test'}, ensure_ascii=False, indent=2))

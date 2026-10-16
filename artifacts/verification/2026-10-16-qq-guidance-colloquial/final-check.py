"""Check deployed identities and one real bounded generation without QQ sends."""
import hashlib
import json
import os
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


manifest = json.loads(Path('/tmp/qq-guidance-colloquial-runtime-20261016.json').read_text())
receipt = json.loads(Path('/var/lib/chickenbro/qq-official/guidance-colloquial-deployment-20261016.json').read_text())
for f in manifest['files']:
    assert sha(root / f['path']) == f['sha256'], f['path']
health = json.loads(Path('/var/lib/chickenbro/qq-official/channel-health.json').read_text())
assert health['observedAt'] > time.time() - 90
assert health['gatewayReady'] and health['queryOnly'] and health['allowedGroupCount'] == 1
assert health['battlePresentation'] == 'single_summary_evidence_narrative_zhcn_v8'
assert health['defaultReplyPresentation'] == 'bounded-model-guidance-v2'
assert health['guidanceModelEnabled'] and health['guidanceToolAccess'] is False
for service, pid in receipt['unchangedServicePids'].items():
    assert run(['systemctl', 'show', service, '-p', 'MainPID', '--value']) == pid
    assert run(['systemctl', 'is-active', service]) == 'active'
assert sha(Path('/opt/chickenbro/server/app/chickenbro/wcl_source.py')) == receipt['webSourceSha256Unchanged']
assert sha(Path('/etc/chickenbro-qq-official/channel.json')) == receipt['configSha256Unchanged']
from server.app.channels.qq_official.query_commands import HELP, GuidanceInput, parse_query
from server.app.channels.qq_official.guidance import DefaultGuidance

assert HELP.index('## 角色查询') < HELP.index('## 战斗分析') and len(HELP) == 489
assert parse_query('/角色查询 Giannis 白银之手').kind == 'character'
try:
    parse_query('能聊天吗')
except GuidanceInput:
    pass
else:
    raise AssertionError('guidance routing absent')

pid = run(['systemctl', 'show', 'chickenbro-qq-official.service', '-p', 'MainPID', '--value'])
for item in Path('/proc/' + pid + '/environ').read_bytes().split(b'\0'):
    if b'=' not in item:
        continue
    key, value = item.decode().split('=', 1)
    if key.startswith(('WOW_CODEX_', 'WOW_CHICKENBRO_CODEX_')) or key in (
            'CODEX_HOME', 'HOME', 'PATH', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
            'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
        os.environ[key] = value
writer = DefaultGuidance.configured()
assert writer.adapter._qq_scope == 'social'
assert all(getattr(writer.adapter, key) is None for key in ('_source_gateway', '_simulation_gateway', '_poe2_gateway'))
result = writer.reply('能聊天吗')
assert result['status'] == 'ready' and result['modelCalls'] == 1
assert '/帮助' not in result['text'] and len(result['text']) <= 80
print(json.dumps({'runtimeFilesMatched': len(manifest['files']), 'gatewayReady': True,
    'queryOnly': True, 'allowedGroupCount': 1, 'battlePresentation': health['battlePresentation'],
    'defaultReplyPresentation': health['defaultReplyPresentation'], 'guidanceToolAccess': False,
    'groupedHelpCharacters': len(HELP), 'candidateModelResult': result,
    'unchangedServicePids': receipt['unchangedServicePids'], 'candidateDatabaseWrites': 0,
    'qqValidationMessagesSent': 0, 'manualGroupAcceptance': 'pending_user_test'}, ensure_ascii=False, indent=2))

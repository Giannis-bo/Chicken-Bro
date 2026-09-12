"""Cloud-only real model exercise of the existing isolated repair path."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time

pid = subprocess.check_output(['systemctl', 'show', 'chickenbro-worker', '-p', 'MainPID', '--value'], text=True).strip()
env = dict(v.split('=', 1) for v in Path('/proc/' + pid + '/environ').read_text().split('\0') if '=' in v)
source = '/opt/chickenbro-candidates/direct-conclusions-20260913'
jobs = Path('/var/lib/chickenbro-direct-repair-20260913')
jobs.mkdir(mode=0o700, exist_ok=True)
user = pwd.getpwnam('ubuntu')
os.chown(jobs, user.pw_uid, user.pw_gid)
os.environ.update(env)
sys.path.insert(0, source)
os.setgid(user.pw_gid)
os.setuid(user.pw_uid)
from server.app.chickenbro.codex_adapter import NativeCodexChatAdapter, _load_profile, _answer_errors

prompt = '我只打三目标副本。有人给我一份单目标宝石对比摘要，现在直接换B吗？不要运行新任务。'
draft = '模拟结果B提升2%，直接换B。三目标配置应按相同条件的三目标对照选择。'
evidence = {'reports': [], 'groups': [], 'simulation': {}}
errors = _answer_errors(draft, evidence)
assert errors, 'fixture must exercise real grounding rejection'
adapter = NativeCodexChatAdapter(jobs_dir=jobs, enabled=True)
answer = adapter._repair_answer(prompt, draft, errors, evidence, time.monotonic() + 100,
    [adapter._codex_bin, '-c', 'approval_policy="never"', 'app-server', '--listen', 'stdio://'],
    _load_profile(adapter._profile), env)
assert not _answer_errors(answer, evidence)
result = {'source': source, 'prompt': prompt, 'draft': draft, 'validationErrors': errors,
          'finalAnswer': answer, 'revalidated': True, 'externalTools': 'disabled_by_repair_profile'}
Path('/tmp/direct-conclusions-repair.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))

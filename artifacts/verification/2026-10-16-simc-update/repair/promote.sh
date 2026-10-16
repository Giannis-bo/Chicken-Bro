#!/usr/bin/env bash
set -euo pipefail
umask 077
root=/var/lib/chickenbro-simc-repair-20261016
/opt/chickenbro-runtime/bin/python - <<'CHECK'
from pathlib import Path
import json,hashlib,datetime
p=Path('/var/lib/chickenbro-simc-repair-20261016');b=json.loads((p/'release-bindings.json').read_text());m=json.loads((p/'manifest.json').read_text())
assert b['sourceCommit']==m['sourceCommit']=='128530c9797bdcbf6bd24af86ec2b29d9ec57af0'
for file,key in [('manifest.json','manifestSha256'),('deploy.py','executorSha256')]:assert hashlib.sha256((p/file).read_bytes()).hexdigest()==b[key]
assert json.loads((p/'candidate.json').read_text())['passed']
assert json.loads((p/'recovery-check.json').read_text())['status']=='passed'
assert Path('/opt/wow-simc/current').resolve().name=='eed909156d8eccbfca0f284cc271c080949d6a20'
assert not (p/'activation-start.json').exists()
(p/'activation-start.json').write_text(json.dumps({'startedAt':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
CHECK
printf '%s\n' promoting > "$root/phase.txt"
/opt/chickenbro-runtime/bin/python "$root/deploy.py" "$root/manifest.json" promote
printf '%s\n' live_business_smoke > "$root/phase.txt"
/opt/chickenbro-runtime/bin/python "$root/smoke.py" production /opt/chickenbro --label live > "$root/live-smoke.log" 2>&1
printf '%s\n' final_observation > "$root/phase.txt"
/opt/chickenbro-runtime/bin/python "$root/final-check.py" > "$root/final-check.log" 2>&1
printf '%s\n' live_verified > "$root/phase.txt"

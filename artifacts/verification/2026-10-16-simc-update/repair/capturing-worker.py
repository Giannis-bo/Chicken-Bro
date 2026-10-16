from pathlib import Path
from uuid import uuid4
import json,hashlib,os
import server.app.simulation.action_lists as actions
root=Path('/var/lib/chickenbro/simc-repair-20261016')
original=actions.extract_action_evidence
def capture(raw,actor,digest):
 name='queue-'+uuid4().hex;p=root/(name+'.json');p.write_bytes(raw if isinstance(raw,bytes) else raw.encode())
 try:result=original(raw,actor,digest)
 except ValueError:
  (root/(name+'-status.json')).write_text(json.dumps({'status':'failed','actor':actor,'profileSha256':digest,'rawSha256':hashlib.sha256(p.read_bytes()).hexdigest()}));raise
 (root/(name+'-status.json')).write_text(json.dumps({'status':'passed','actor':actor,'profileSha256':digest,'rawSha256':hashlib.sha256(p.read_bytes()).hexdigest()}));return result
actions.extract_action_evidence=capture
from server.app.worker.main import build_worker
build_worker(worker_id='simc-repair-candidate',lease_seconds=30).run_forever(lambda:False)

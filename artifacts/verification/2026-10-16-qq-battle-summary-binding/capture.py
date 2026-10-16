import json,subprocess
from pathlib import Path
sql="SELECT result_packet FROM qq_channel.official_queries WHERE result_packet->>'reportCode'='YptH9vaxBChMTn7b' ORDER BY completed_at DESC LIMIT 1"
p=subprocess.check_output(['sudo','-u','postgres','psql','-d','chickenbro_qq_official_candidate','-Atc',sql],text=True)
packet=json.loads(p)
Path('/tmp/qq-battle-summary-binding-case.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2))
print(json.dumps({'reportCode':packet['reportCode'],'fightId':packet['fightId'],'narrative':packet['narrative'],'players':[(r['actorId'],r['name']) for key in ('good','review') for r in packet[key]]},ensure_ascii=False))

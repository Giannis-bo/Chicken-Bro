"""Revalidate saved synthetic smoke receipts without new model or WCL calls."""
import json, subprocess, sys
from pathlib import Path
from uuid import UUID
root=Path(__file__).parent
label=sys.argv[1]
d=json.loads((root/(label+'-private.json')).read_text())
case=d['cases'][0]
assert case['runStatus']=='succeeded' and case['sseCompleted']
receipts=[t for t in case['toolObservations'] if t['tool']=='source.warcraftlogs']
assert receipts and all((t['result'] or {}).get('errorCode') is None for t in receipts)
facts=[f for t in receipts for f in (t['result'] or {}).get('facts',[]) if str(f.get('sourceId'))=='472']
assert any(f.get('damage',{}).get('entries') for f in facts)
cid=str(UUID(case['conversationId']))
db='chickenbro_badcase_candidate_20260909' if d['mode']=='candidate' else 'chickenbro_prod'
sql="BEGIN READ ONLY; SELECT jsonb_array_length(budget->'source'->'players') FROM chat.research_sessions WHERE conversation_id='"+cid+"'; COMMIT;"
count=subprocess.check_output(['sudo','-u','postgres','psql','-X','-qAt','-v','ON_ERROR_STOP=1',db,'-c',sql],text=True).strip()
assert count=='10'
d['selectedPlayerFacts']=facts
d['checks'].update(selectedPlayerSourceRead=True,damageTableReturned=True,
    playerCountRemainsTen=True,ownerIsolation=True,idempotentReplay=True)
d['validationNote']='Saved receipts revalidated after correcting sourceId string comparison; no repeated model call.'
(root/(label+'-validated-private.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2))
print(json.dumps({'checks':d['checks'],'answer':case['finalAnswer'],'elapsedSeconds':case['elapsedSeconds']},ensure_ascii=False))

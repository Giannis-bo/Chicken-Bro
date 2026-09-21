"""Cloud-only sanitized trace and persistence receipt."""
import hashlib,json
from pathlib import Path
import psycopg
root=Path('/opt/chickenbro-candidates/poe2-20260918');out=root/'evidence/research-budget'
conv=json.loads((out/'chat.json').read_text())['conversationId']
with psycopg.connect('dbname=chickenbro_poe2_candidate') as conn:
    rows=conn.execute('''SELECT t.operation,t.state,t.result_json FROM chat.tool_results t
        JOIN chat.agent_runs r ON r.id=t.run_id WHERE r.conversation_id=%s ORDER BY t.started_at''',(conv,)).fetchall()
    scopes=conn.execute('''SELECT s.id,s.budget FROM chat.research_sessions s WHERE s.conversation_id=%s''',(conv,)).fetchall()
assert len(scopes)==1
budget=scopes[0][1]['poe2']
assert len(budget['candidates'])==1 and budget['attempts']==1
get=[v for op,st,v in rows if op=='poe2.get' and st=='completed']
calc=[v for op,st,v in rows if op=='poe2.calculate' and st=='completed']
assert get and all(v.get('baselineJobId') for v in get)
assert sum(not v.get('reused') for v in calc)==1
assert any(op=='poe2.compare' and st=='completed' for op,st,v in rows)
paths=['server/app/poe2/research.py','server/app/poe2/repository.py','server/app/poe2/application.py','server/app/poe2/tools.py','server/app/chickenbro/research_lifecycle.py','server/app/chickenbro/worker.py','server/app/main.py','server/app/chickenbro/agent/POE2.md','server/app/chickenbro/agent/skills/poe2-build-analysis.md','server/chickenbro_native_mcp.py']
report={'passed':True,'sameResearchAcrossTurns':True,'baselineIdExposed':True,'newCalculationCount':1,'persistedCandidateCount':1,'persistedAttemptCount':1,'operations':[{'operation':op,'state':st} for op,st,v in rows], 'sourceSha256':{p:hashlib.sha256((root/'source'/p).read_bytes()).hexdigest() for p in paths}}
(out/'trace.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('sourceSha256','operations')}))

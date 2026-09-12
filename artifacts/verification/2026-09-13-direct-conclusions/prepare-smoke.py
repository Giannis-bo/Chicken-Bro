"""Adapt the inspected private smoke; no credentials are exported."""
from pathlib import Path

root = Path('/var/lib/chickenbro-direct-conclusions-20260913')
s = Path('/var/lib/chickenbro-skills-release-20260912/smoke.py').read_text()
s = s.replace('chickenbro-skills-candidate-20260912', 'chickenbro-direct-conclusions-candidate-20260913')
start = s.index("    if a.mode=='candidate':\n        corpus=")
end = s.index('        # Read a real previously completed cloud result', start)
tail_end = s.index("    else:\n        record=ask(create('generalization:live-help')", end)
shared_result = s[end:tail_end]
finish = s.index("    report['checks'].update(ownerIsolation=True,idempotentReplay=True)", tail_end)
s = s[:start] + '''    corpus=json.loads((Path(__file__).parent/'cases.json').read_text())
    selected=corpus['cases'] if a.mode=='candidate' else [v for v in corpus['cases'] if v['id'] in ('full-review','explicit-unknown','material-condition')]
    for case in selected:
        record=ask(create('direct-conclusions:'+case['id']),case['prompt'])
        record['caseId']=case['id']
    if True:
''' + shared_result + s[finish:]
compile(s, 'smoke.py', 'exec')
(root/'smoke.py').write_text(s)

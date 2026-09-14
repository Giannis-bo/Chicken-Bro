"""Export aggregate usage and evidence receipts, without original chat or reasoning."""
import hashlib
import json
from pathlib import Path

root = Path('/var/lib/chickenbro-g16-quality-20260914')
rows = []
usage = {}
for path in sorted(root.rglob('result.json')):
    data = json.loads(path.read_text())
    receipts = path.parent / 'receipts.jsonl'
    keys = sorted({key for line in receipts.read_text().splitlines()
                   for key in json.loads(line).get('result', {}).get('evidenceKeys', [])}) if receipts.exists() else []
    models = [entry for turn in data.get('turns', []) for entry in turn.get('modelUsage', [])]
    for model in models:
        for key, value in model.get('usage', {}).items():
            if isinstance(value, (int, float)):
                usage[key] = usage.get(key, 0) + value
    rows.append({'path': str(path.relative_to(root)), 'resultSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'case': data['caseId'], 'source': data['source'], 'status': data['status'],
                 'modelCalls': len(models), 'requiredEvidence': data.get('requiredEvidence', []),
                 'evidenceKeys': keys, 'receiptGatePass': set(data.get('requiredEvidence', [])) <= set(keys)})
print(json.dumps({'modelCalls': sum(row['modelCalls'] for row in rows), 'usage': usage,
                  'simcJobs': 0, 'realUpstreamSourceCalls': 0, 'results': rows}, indent=2))

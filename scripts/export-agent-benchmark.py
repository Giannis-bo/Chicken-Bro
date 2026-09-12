"""Export synthetic replay evidence and a version-blind answer review bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets


def export(root, output):
    from agent_benchmark_fixtures import CASES
    from agent_benchmark_metrics import paired_summary
    cases = {c['id']: c for c in CASES}
    output.mkdir(parents=True, exist_ok=True)
    runs, mapping, blind = [], {}, {}
    previous_map = json.loads((root/'review-map.json').read_text()) if (root/'review-map.json').exists() else {}
    previous_ids = {(v['caseId'], v['trial'], v['variant']): k for k, v in previous_map.items()}
    for path in sorted(root.glob('*/result.json')):
        result = json.loads(path.read_text())
        case = cases[result['caseId']]
        identity = (result['caseId'], result['trial'], result['variant'])
        ident = previous_ids.get(identity) or secrets.token_hex(12)
        receipts_path = path.parent / 'receipts.jsonl'
        receipts = [json.loads(line) for line in receipts_path.read_text().splitlines()] if receipts_path.exists() else []
        acquired = sorted({k for receipt in receipts for k in receipt['result'].get('evidenceKeys', [])})
        mapping[ident] = {'caseId': result['caseId'], 'trial': result['trial'], 'variant': result['variant']}
        blind.setdefault(case['category'], []).append({
            'reviewId': ident, 'prompts': case['turns'], 'rubric': case['rubric'],
            'answers': [t.get('answer', '') for t in result.get('turns', [])],
            'status': result['status'], 'acquiredEvidence': acquired,
            'requiredEvidence': case['requiredEvidence'],
            'toolEvidence': [{'tool': r['tool'], 'arguments': r['arguments'], 'result': r['result']}
                             for r in receipts if r['tool'] != 'read_chickenbro_skill'],
            'instructions': 'Judge factual correctness, evidence coverage, scope and completion, each pass/fail. Do not infer speed or version. requiredEvidence is route triage, not a mandatory tool path. Accept equivalent complete returned evidence. Judge required implementation behavior from actual tool arguments/results, not whether the answer repeats technical keywords. Acquisition alone does not prove answer quality; preserve material omissions and contradictions.',
        })
        result['reviewId'] = ident
        result['acquiredEvidence'] = acquired
        result['fixtureErrors'] = [r for r in receipts if r['result'].get('status') in ('error', 'unavailable')]
        runs.append(result)
    (root/'review-map.json').write_text(json.dumps(mapping, indent=2))
    for category, rows in blind.items():
        rows.sort(key=lambda row: row['reviewId'])
        (output/('blind-'+category+'.json')).write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    (output/'runs.json').write_text(json.dumps(runs, ensure_ascii=False, indent=2))
    (output/'summary-unreviewed.json').write_text(json.dumps(paired_summary(runs), ensure_ascii=False, indent=2))
    planned = json.loads((root/'schedule.json').read_text())
    seen = {(r['caseId'], r['trial'], r['variant']) for r in runs}
    campaign = {'plannedCount': len(planned), 'recordedCount': len(runs),
        'missing': [r for r in planned if (r['caseId'], r['trial'], r['variant']) not in seen],
        'completeCaseCount': sum(r.get('completeCase') is True for r in runs),
        'stopped': json.loads((root/'stopped.json').read_text()) if (root/'stopped.json').exists() else None,
        'sourceHashes': {}, 'harnessHashes': {}}
    for source in sorted({r['source'] for r in runs if r.get('source')}):
        campaign['sourceHashes'][source] = {name: hashlib.sha256((Path(source)/name).read_bytes()).hexdigest()
            for name in ('server/app/chickenbro/agent/AGENTS.md', 'server/app/chickenbro/codex_adapter.py',
                         'server/chickenbro_native_mcp.py')}
    for name in ('benchmark-chickenbro-agent.py', 'agent_benchmark_fixtures.py', 'agent_benchmark_metrics.py'):
        archive = root / {'benchmark-chickenbro-agent.py': 'runner.py', 'agent_benchmark_fixtures.py': 'fixtures.py'}.get(name, name)
        chosen = archive if archive.exists() else Path(__file__).with_name(name)
        campaign['harnessHashes'][name] = hashlib.sha256(chosen.read_bytes()).hexdigest()
    (output/'campaign.json').write_text(json.dumps(campaign, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export(args.root, args.output)

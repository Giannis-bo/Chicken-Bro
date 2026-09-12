"""Join blinded judgments with timings; never infer quality from success/speed."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median


def summarize(runs, reviews):
    from agent_benchmark_metrics import paired_summary
    judgments = {}
    for review in reviews:
        ident = review['reviewId']
        if ident in judgments:
            raise ValueError('Duplicate review: '+ident)
        if review['quality'] not in ('pass', 'fail'):
            raise ValueError('Explicit quality decision required')
        judgments[ident] = review
    for run in runs:
        decision = judgments.get(run['reviewId'])
        run['quality'] = decision['quality'] if decision else 'unreviewed'
        run['qualityReview'] = decision
    summary = paired_summary(runs)
    for group in [summary['overall'], *summary['categories'].values()]:
        group['ratioOfMediansPercent'] = ((group['newMedianMs']/group['oldMedianMs']-1)*100
                                          if group['oldMedianMs'] else None)
    eligible = {(p['caseId'], p['trial']) for p in summary['pairs']}
    diagnostics = {}
    for variant in ('old', 'new'):
        selected = [r for r in runs if r['variant'] == variant and (r['caseId'], r['trial']) in eligible]
        values = []
        for run in selected:
            row = dict(inputTokens=0, cachedInputTokens=0, outputTokens=0, repairSessions=0,
                       toolMs=0, toolCount=0, skillReads=0, startupMs=0, repeatedQueries=0)
            for turn in run['turns']:
                timing = turn['timing']
                row['toolMs'] += timing['toolMs']
                row['toolCount'] += timing['toolCount']
                row['skillReads'] += timing['tools'].get('read_chickenbro_skill', {}).get('count', 0)
                row['startupMs'] += turn['startupMs'] or 0
                row['repeatedQueries'] += sum(q['extraCount'] for q in timing['repeatedQueries'])
                for session in turn['modelUsage']:
                    usage = session.get('usage') or {}
                    for key in ('inputTokens', 'cachedInputTokens', 'outputTokens'):
                        row[key] += usage.get(key, 0)
                    row['repairSessions'] += session['phase'] == 'repair'
            row['uncachedInputTokens'] = row['inputTokens'] - row['cachedInputTokens']
            row['nonToolMs'] = run['totalMs'] - row['toolMs']
            row['modelUsageComplete'] = all(t['modelUsage'] and all(s.get('usage') is not None for s in t['modelUsage']) for t in run['turns'])
            if not row['modelUsageComplete']:
                for key in ('inputTokens', 'cachedInputTokens', 'outputTokens', 'uncachedInputTokens'):
                    row[key] = None
            values.append(row)
        diagnostics[variant] = {'pairedRunCount': len(values),
            'medians': {k: median(v[k] for v in values) if all(v[k] is not None for v in values) else None for k in values[0]} if values else {},
            'totals': {k: sum(v[k] for v in values) if all(v[k] is not None for v in values) else None for k in values[0]} if values else {}}
    summary['diagnosticsOnQualityPassedPairs'] = diagnostics
    summary['fixtureHashes'] = dict(Counter(r.get('fixtureSha256', 'unavailable') for r in runs))
    summary['timingIssues'] = [{'caseId': r['caseId'], 'variant': r['variant'], 'trial': r['trial'],
                               'turn': t['turnIndex'], 'issues': t['timing']['issues']}
                              for r in runs for t in r.get('turns', []) if t['timing']['issues']]
    summary['qualityNotes'] = ['Quality judgments were made without variant or timing fields.',
        'Positive delta means slower. Only same-case/trial quality-pass pairs enter latency comparisons.',
        'nonToolMs includes model service, network, validation and process overhead; it is not pure reasoning time.',
        'Prompt cache state and model service load are observed, not controlled. No tail latency claim.']
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('runs', type=Path)
    parser.add_argument('reviews', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    runs = json.loads(args.runs.read_text(encoding='utf-8'))
    reviews = [r for p in sorted(args.reviews.glob('*.json')) for r in json.loads(p.read_text(encoding='utf-8'))]
    result = summarize(runs, reviews)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    args.runs.with_name('runs-reviewed.json').write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding='utf-8')

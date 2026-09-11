#!/usr/bin/env python3
"""Validate the fixed corpus or review recorded traces; never invokes models or cloud.

  python3 scripts/evaluate-chickenbro-semantics.py
  python3 scripts/evaluate-chickenbro-semantics.py --traces /path/to/traces.json

Trace JSON: {"results": [{"caseId": "simple-class-question",
 "configuration": {"runtimeRevision": "<actual revision>", "model": "<actual model>"},
 "turns": [{"turnIndex": 0, "runStatus": "succeeded", "finalAnswer": "...",
            "toolObservations": []}],
 "humanReview": {"reviewer": "<name>", "notes": "<evidence and rationale>",
                 "verdicts": ["pass", "pass", "pass"]}}]}

Use one ordered trace turn per corpus user turn, retaining the same conversation.
Tool observations must retain actual tool, status and evidence references. Empty
observations are valid for no-tool answers; appropriateness is reviewed by humans.
A verdict corresponds to a humanRubric item by index and is pass/fail/unknown.
This records a human assessment, not an automated semantic judgment. Exit zero
means inputs processed, not model quality passed. Missing cases remain unrun.
"""
import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_CASES = Path(__file__).resolve().parents[1] / 'tests/fixtures/chickenbro-research-cases.json'


def load_cases(path):
    document = json.loads(path.read_text(encoding='utf-8'))
    cases = document.get('cases', [])
    if not cases or len(cases) > 20:
        raise ValueError('corpus requires 1..20 bounded cases')
    by_id = {}
    for case in cases:
        ident = case.get('id')
        turns, rubric = case.get('turns'), case.get('humanRubric')
        if not isinstance(ident, str) or not ident.strip() or ident in by_id:
            raise ValueError('case IDs must be unique nonempty strings')
        if not isinstance(turns, list) or not 1 <= len(turns) <= 4 or any(
                not isinstance(t, dict) or t.get('role') != 'user' or not isinstance(t.get('content'), str)
                or not t['content'].strip() for t in turns):
            raise ValueError(f'{ident}: requires 1..4 user turns')
        if case.get('prompt') != turns[0]['content']:
            raise ValueError(f'{ident}: legacy prompt must equal first user turn')
        if not isinstance(rubric, list) or not rubric or any(not isinstance(r, str) or not r.strip() for r in rubric):
            raise ValueError(f'{ident}: human rubric is required')
        by_id[ident] = case
    return by_id


def score(case, trace):
    issues = []
    configuration = trace.get('configuration')
    if not isinstance(configuration, dict) or any(not isinstance(configuration.get(k), str) or not configuration[k].strip()
                                                 for k in ('runtimeRevision', 'model')):
        issues.append('MISSING_RUNTIME_IDENTITY')
    turns = trace.get('turns')
    if not isinstance(turns, list) or len(turns) != len(case['turns']):
        issues.append('INCOMPLETE_TURN_TRACE')
    else:
        for index, turn in enumerate(turns):
            if not isinstance(turn, dict) or turn.get('turnIndex') != index or turn.get('runStatus') != 'succeeded' or not isinstance(turn.get('finalAnswer'), str) or not turn['finalAnswer'].strip() or not isinstance(turn.get('toolObservations'), list):
                issues.append(f'INCOMPLETE_TURN_{index}')
                continue
            for observation in turn['toolObservations']:
                if not isinstance(observation, dict) or not observation.get('tool') or not observation.get('status'):
                    issues.append(f'INCOMPLETE_OBSERVATION_{index}')
    review = trace.get('humanReview') or {}
    if not isinstance(review, dict):
        raise ValueError('humanReview must be an object')
    verdicts = review.get('verdicts', [])
    complete_review = (isinstance(verdicts, list) and len(verdicts) == len(case['humanRubric'])
                       and all(v in ('pass', 'fail', 'unknown') for v in verdicts)
                       and isinstance(review.get('reviewer'), str) and bool(review['reviewer'].strip())
                       and isinstance(review.get('notes'), str) and bool(review['notes'].strip()))
    status = 'insufficient_trace' if issues else 'awaiting_review'
    if not issues and complete_review:
        status = 'failed' if 'fail' in verdicts else 'awaiting_review' if 'unknown' in verdicts else 'passed'
    return {'caseId': case['id'], 'semanticStatus': status, 'traceIssues': issues,
            'humanRubric': case['humanRubric'], 'humanReview': review,
            'assessmentSource': 'recorded_human_review' if complete_review else 'not_reviewed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cases', type=Path, default=DEFAULT_CASES)
    parser.add_argument('--traces', type=Path)
    args = parser.parse_args()
    try:
        cases = load_cases(args.cases)
        summary = {'corpusStatus': 'valid', 'corpusSha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                   'caseCount': len(cases), 'multiTurnCaseCount': sum(len(c['turns']) > 1 for c in cases.values()),
                   'semanticStatus': 'not_run', 'results': [], 'unrunCaseCount': len(cases)}
        if args.traces:
            traces = json.loads(args.traces.read_text(encoding='utf-8')).get('results')
            if not isinstance(traces, list):
                raise ValueError('trace file requires a results array')
            seen = set()
            for trace in traces:
                if not isinstance(trace, dict) or trace.get('caseId') not in cases or trace['caseId'] in seen:
                    raise ValueError('unknown or duplicate trace case ID')
                seen.add(trace['caseId'])
                summary['results'].append(score(cases[trace['caseId']], trace))
            summary['unrunCaseCount'] = len(cases) - len(seen)
            summary['traceSha256'] = hashlib.sha256(args.traces.read_bytes()).hexdigest()
            statuses = [r['semanticStatus'] for r in summary['results']]
            summary['semanticStatus'] = ('failed' if 'failed' in statuses else 'passed'
                if not summary['unrunCaseCount'] and all(s == 'passed' for s in statuses) else 'incomplete')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (ValueError, OSError, TypeError, AttributeError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

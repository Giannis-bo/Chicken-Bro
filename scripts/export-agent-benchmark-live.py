"""Project private Candidate receipts into reviewable benchmark evidence."""
import argparse
import json
from pathlib import Path


def project(report):
    out = {k: report[k] for k in ('variant', 'requestedCommit', 'sourceHashes', 'fixtureSha256',
           'modelProfile', 'checks', 'limitations', 'wclPreflight') if k in report}
    fixture = report['fixture']
    out['fixture'] = {k: v for k, v in fixture.items() if k not in ('owner', 'otherOwner')}
    out['cases'] = []
    for case in report.get('cases', []):
        row = {k: case[k] for k in ('caseId', 'prompt', 'status', 'elapsedSeconds', 'runId',
               'runStatus', 'errorCode', 'modelUsage', 'finalAnswer', 'sseCompleted',
               'secondOwner404', 'idempotentReplay', 'nativeObservations', 'nativeBinding') if k in case}
        row['qualityStatus'] = 'pending_manual_review'
        row['toolReceipts'] = []
        for receipt in case.get('toolReceipts', []):
            item = {k: receipt[k] for k in ('tool', 'state', 'startedAt', 'finishedAt')}
            result = receipt.get('result') or {}
            item['result'] = {k: result[k] for k in ('sourceKey', 'status', 'errorCode', 'facts',
                'evidenceRefs', 'evidence', 'limitations', 'comparison', 'jobId', 'snapshotId',
                'scenario', 'runtimeRevision', 'compilerRevision', 'effectiveConfig') if k in result}
            if isinstance(result.get('result'), dict):
                item['result']['result'] = {k: result['result'][k] for k in ('metricName', 'metricValue',
                    'metricError', 'dps', 'dpsError', 'provenance', 'effectiveConfig') if k in result['result']}
            row['toolReceipts'].append(item)
        out['cases'].append(row)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for path in args.root.glob('*-private.json'):
        if path.name == 'fixtures-private.json':
            continue
        report = json.loads(path.read_text())
        (args.output/path.name.replace('-private', '')).write_text(
            json.dumps(project(report), ensure_ascii=False, indent=2))

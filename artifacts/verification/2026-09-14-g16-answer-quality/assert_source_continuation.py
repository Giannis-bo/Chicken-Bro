"""Semantic receipt gate: fails if relevant available correction was never read.

This checks evidence acquisition only. An answer still needs separate review.
"""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);rows=[json.loads(l) for l in (root/'receipts.jsonl').read_text().splitlines()]
keys={k for row in rows for k in row['result'].get('evidenceKeys',[])}
assert 'forum.continuation' in keys, 'Available source continuation was not read before replacing the failed recommendation'
print('Relevant source continuation read; answer review still required.')

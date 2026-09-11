"""Bounded checks of explicit completion, primary metric and measured delta claims.

Evidence must come from SimulationToolGateway's owner-scoped, validated packets.
This is not a general semantic or causal verifier. An empty error list also means
no recognized contradiction: ambiguous job associations are deliberately unchecked.
"""
import math
import re
from copy import deepcopy

_SCOPE = 'explicit_simulation_claims_only'
_UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
_NUMBER = r'[+-]?\d[\d,]*(?:\.\d+)?\s*(?:万|[kKmM](?![a-zA-Z]))?'
_METRIC = re.compile(r'(?<![A-Za-z])(dps|hps)(?![A-Za-z])\s*(?:为|是|达到|[:：=]|is|was|of)?\s*(' + _NUMBER + r')', re.I)
_REVERSE_METRIC = re.compile(r'(' + _NUMBER + r')\s*(?<![A-Za-z])(dps|hps)(?![A-Za-z])', re.I)
_COMPLETED = re.compile(r'(?:模拟|仿真|simulation|simc|任务|job).{0,32}?(?:已完成|跑完了|已跑完|completed|succeeded|finished)|(?:已完成|已跑完)(?:了)?(?:模拟|仿真)', re.I)
_BENEFIT = re.compile(r'(提升|提高|增加|降低|下降|减少|gain|increase|improve(?:ment)?|decrease|reduction)\s*(?:了|约|by|of)?\s*(' + _NUMBER + r')\s*[%％]', re.I)
_NONCLAIM = re.compile(r'如果|假如|假设|(?:等|当)(?:模拟|仿真).{0,24}(?:后|时)|请确认(?:模拟|仿真)|预计|预期|可能|尚未|未完成|没有|无法|不能|未能|还没|待验证|\b(?:if|would|could|may|might|expected|hypothetical|not|cannot|unable)\b', re.I)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def collect_simulation_evidence(previous, result):
    """Project only safe fields from packets returned by the trusted gateway."""
    evidence = deepcopy(previous) if isinstance(previous, dict) else {}
    evidence.setdefault('jobs', {})
    evidence.setdefault('comparisons', [])
    evidence['scope'] = _SCOPE
    evidence['limitations'] = ['Only explicit completion, DPS/HPS and measured percentage claims are checked; ambiguous associations and causal explanations are not verified.']
    if not isinstance(result, dict) or result.get('sourceKey') != 'simc':
        return evidence
    packets = result.get('jobs', []) if isinstance(result.get('jobs'), list) else []
    for packet in [result, *packets[:10]]:
        job_id = packet.get('jobId') if isinstance(packet, dict) else None
        if not isinstance(job_id, str) or not re.fullmatch(_UUID, job_id, re.I):
            continue
        row = {'status': packet.get('status')}
        metric = packet.get('result')
        if (row['status'] == 'succeeded' and isinstance(metric, dict) and metric.get('provenance')
                and metric.get('metricName') in {'dps', 'hps'} and _finite(metric.get('metricValue'))
                and metric['metricValue'] > 0):
            row.update(metricName=metric['metricName'], metricValue=metric['metricValue'])
        # A succeeded label without a validated usable metric is not completion proof.
        elif row['status'] == 'succeeded':
            row['status'] = 'unverified'
        evidence['jobs'][job_id.lower()] = row
    comparison = result.get('comparison')
    if (result.get('status') == 'ready' and isinstance(comparison, dict)
            and all(isinstance(comparison.get(k), str) and re.fullmatch(_UUID, comparison[k], re.I)
                    for k in ('baselineJobId', 'variantJobId'))
            and all(_finite(comparison.get(k)) for k in ('baseline', 'variant', 'delta', 'deltaPct'))):
        row = {k: comparison[k] for k in ('baselineJobId', 'variantJobId', 'metricName', 'delta', 'deltaPct', 'assessment')}
        evidence['comparisons'] = [c for c in evidence['comparisons'] if (c['baselineJobId'], c['variantJobId']) != (row['baselineJobId'], row['variantJobId'])]
        evidence['comparisons'].append(row)
        for role in ('baseline', 'variant'):
            evidence['jobs'][row[role + 'JobId']] = {'status': 'succeeded', 'metricName': row['metricName'], 'metricValue': comparison[role]}
    # Bound the repair context even when many list pages were queried.
    evidence['jobs'] = dict(list(evidence['jobs'].items())[-100:])
    evidence['comparisons'] = evidence['comparisons'][-50:]
    return evidence


def _number(raw):
    normalized = raw.replace(',', '').strip().lower()
    scale = {'万': 10000, 'k': 1000, 'm': 1000000}.get(normalized[-1], 1)
    return float(normalized[:-1] if scale != 1 else normalized) * scale


def _matches(raw, expected):
    # Allow presentation rounding, bounded by the shown precision (e.g. 1.2万).
    normalized = raw.replace(',', '').strip().lower()
    suffix = normalized[-1] if normalized[-1] in '万km' else ''
    numeric = normalized[:-1].strip() if suffix else normalized
    decimals = len(numeric.split('.')[1]) if '.' in numeric else 0
    scale = {'万': 10000, 'k': 1000, 'm': 1000000}.get(suffix, 1)
    return abs(_number(raw) - expected) <= 0.5 * scale * 10 ** -decimals + 1e-9


def validate_simulation_answer(text, evidence):
    """Return stable errors for recognized unobserved/contradicted assertions only."""
    if not isinstance(text, str):
        return []
    evidence = evidence if isinstance(evidence, dict) else {}
    jobs = evidence.get('jobs', {})
    comparisons = evidence.get('comparisons', [])
    errors = []
    # Quoted demands, blockquotes and code are not assistant factual assertions.
    prose = re.sub(r'```[\s\S]*?```|“[^”]*”|"[^"\n]*"', '', text)
    prose = '\n'.join(line for line in prose.splitlines() if not line.lstrip().startswith('>'))
    for sentence in re.split(r'[。!?！？;；\n]|(?<!\d)\.(?!\d)', prose):
        if _NONCLAIM.search(sentence):
            continue
        ids = re.findall(_UUID, sentence.lower())
        if not ids and not re.search(r'模拟|仿真|\bsimulation\b|\bsimc\b', sentence, re.I):
            continue
        selected = [jobs[job_id] for job_id in ids if job_id in jobs] if ids else list(jobs.values())
        complete = [job for job in selected if job.get('status') == 'succeeded' and 'metricValue' in job]
        if _COMPLETED.search(sentence) and (not complete or any(job_id not in jobs or jobs[job_id].get('status') != 'succeeded' for job_id in ids)):
            errors.append('SIMULATION_COMPLETION_UNSUPPORTED')
        metrics = [(m[1], m[2]) for m in _METRIC.finditer(sentence)]
        metrics += [(m[2], m[1]) for m in _REVERSE_METRIC.finditer(sentence)]
        for metric_name, raw_value in metrics:
            # Multiple explicit IDs are ambiguous; do not pretend to resolve prose roles.
            if len(ids) > 1:
                continue
            values = [j['metricValue'] for j in complete if j.get('metricName') == metric_name.lower()]
            if not any(_matches(raw_value, value) for value in values):
                errors.append('SIMULATION_METRIC_UNSUPPORTED')
        if not re.search(r'模拟|仿真|实测|结果|任务|simc|simulation|measured|result|\bdps\b|\bhps\b', sentence, re.I):
            continue
        for match in _BENEFIT.finditer(sentence):
            candidates = comparisons
            if len(ids) == 2:
                # Only resolve the explicit directional construction “X 相比 Y”.
                direction = re.search('(' + _UUID + r')\s*(?:相比|相对|compared to)\s*(' + _UUID + ')', sentence, re.I)
                if direction:
                    candidates = [c for c in comparisons if c['variantJobId'] == direction[1].lower() and c['baselineJobId'] == direction[2].lower()]
                else:
                    continue
            elif ids:
                candidates = [c for c in comparisons if c['variantJobId'] == ids[0]] if len(ids) == 1 else []
            sign = -1 if match[1].lower() in {'降低', '下降', '减少', 'decrease', 'reduction'} else 1
            if not any(_matches(match[2], c['deltaPct'] * sign) for c in candidates):
                errors.append('SIMULATION_BENEFIT_UNSUPPORTED')
    return list(dict.fromkeys(errors))

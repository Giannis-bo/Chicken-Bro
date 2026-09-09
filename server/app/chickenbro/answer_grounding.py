"""Bounded, run-local reference checks. Source strings are data, never instructions.

This is not a semantic verifier: it cannot establish causal validity or complete
natural-language coverage. Positive references require returned source evidence;
failed receipts retain only allowlisted identities and controlled failure codes.
"""
import copy
import html
import hashlib
import json
import re
from collections.abc import Mapping
from urllib.parse import parse_qs, urlsplit

MAX_CONTEXT = 64000
MAX_REPORTS = 2048
MAX_INDEX = 512000
MAX_GROUPS = 100
_CODE = re.compile(r'^[A-Za-z0-9]{16}$')
_URL = re.compile(r'https?://[^\s<>\[\]()"\u3000]+', re.I)


def _small(value):
    if isinstance(value, str):
        return value[:240]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return None


def _items(value):
    return value if isinstance(value, (list, tuple)) else []


def _mapping(value):
    return value if isinstance(value, Mapping) else {}


def _fields(value, keys):
    return {k: _small(value[k]) for k in keys if k in value} if isinstance(value, Mapping) else {}


def _identity(code, fight=None, source=None):
    code = str(code or '')
    fight, source = str(fight or ''), str(source or '')
    if not _CODE.fullmatch(code) or len(fight)>12 or len(source)>12 or (fight and not fight.isdecimal()) or (source and not source.isdecimal()):
        return None
    return {'code': code, 'fight': fight, 'source': source,
            'url': 'https://www.warcraftlogs.com/reports/' + code +
            (('?fight=' + fight) if fight else '') + (('&source=' + source) if source and fight else '')}


_SCOPE_FIELDS = ('zoneId','encounterId','encounterName','difficulty','partition','className','specName','region','metric')
_COVERAGE_LISTS = ('directories','rankingSnapshots','reportReceipts','failures')
_COVERAGE_BOUNDARY = 'Independent source receipts, not stitched snapshots. Detail projection omission is not source failure. Nonempty casts are fetched data, not proof of a valid written analysis.'


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _coverage_add(out, collection, record):
    coverage = out['coverage']
    records = coverage[collection]
    if record in records:
        return
    if len(records) >= 512:
        coverage['sourceIndexTruncated'] = True
        return
    records.append(record)


def _coverage_items(out, value, limit):
    items = _items(value)
    if len(items) > limit:
        out['coverage']['sourceIndexTruncated'] = True
    return items[:limit]


def _receipt_coverage(out, packet):
    """Record receipt completeness separately from any later detail projection."""
    source, status = packet.get('sourceKey'), packet.get('status')
    success = status in ('verified', 'source_reference', 'partial')
    if source == 'warcraftlogs_rankings' and success:
        for fact in _coverage_items(out, packet.get('facts'), 100):
            if not isinstance(fact, Mapping) or type(fact.get('id')) is not int:
                continue
            directory = _fields(fact, ('id','name'))
            for field in ('encounters','partitions','difficulties'):
                directory[field] = [_fields(v, ('id','name','default')) for v in _coverage_items(out, fact.get(field), 200)]
            _coverage_add(out, 'directories', directory)
        if isinstance(packet.get('rankings'), list):
            rows = []
            snapshot_rows = []
            for row in _coverage_items(out, packet['rankings'], 200):
                if not isinstance(row, Mapping) or type(row.get('rank')) is not int or row['rank'] < 1:
                    continue
                ref = _mapping(row.get('report'))
                identity = _identity(ref.get('code'), ref.get('fightID'))
                if identity:
                    rows.append([row['rank'], identity['code'], identity['fight']])
                    snapshot_rows.append({**_fields(row, ('rank','name','class','spec','amount','durationMs','startTime')),
                        'report':identity, 'server':_fields(row.get('server'), ('id','name','region'))})
            ranks = sorted({r[0] for r in rows})
            ranges = []
            for rank in ranks:
                if ranges and ranges[-1][1] + 1 == rank:
                    ranges[-1][1] = rank
                else:
                    ranges.append([rank, rank])
            pagination = _fields(packet.get('pagination'), ('page','offset','limit','returned','skippedInvalid','hasMore','nextPage','nextOffset','paginationCapReached'))
            page, offset, limit = (pagination.get(k) for k in ('page','offset','limit'))
            valid_slice = (type(page) is int and page > 0 and type(offset) is int and offset >= 0 and type(limit) is int and 0 < limit <= 200)
            complete = bool(valid_slice and status == 'source_reference' and pagination.get('skippedInvalid') == 0 and
                            len(rows) == len(ranks) == len(packet['rankings']) == pagination.get('returned') == limit and
                            ranks == list(range((page-1)*100+offset+1, (page-1)*100+offset+limit+1)))
            scope = _fields(packet.get('scope'), _SCOPE_FIELDS)
            queried = _small(packet.get('queriedAt'))
            snapshot = hashlib.sha256(_encoded([scope, queried, pagination, snapshot_rows]).encode()).hexdigest()
            _coverage_add(out, 'rankingSnapshots', {'snapshotId':snapshot, 'scope':scope, 'queriedAt':queried,
                'status':status, 'pagination':pagination, 'returnedIdentityCount':len(rows), 'rankRanges':ranges,
                'requestedSliceComplete':complete})
    if source != 'warcraftlogs':
        return
    if success:
        for fact in _coverage_items(out, packet.get('facts'), 100):
            if not isinstance(fact, Mapping):
                continue
            identity = _identity(fact.get('reportCode'),fact.get('fightId'),fact.get('sourceId'))
            if not identity:
                continue
            casts = _mapping(fact.get('casts'))
            entries = casts.get('entries')
            state = ('returned_nonempty' if entries else 'returned_empty') if isinstance(entries,list) else 'absent'
            receipt = {**identity, 'status':status, 'castsState':state, 'castRowsReturned':len(entries) if isinstance(entries,list) else None,
                'castsRowsTruncated':_small(casts.get('rowsTruncated')), 'fightScope':_fields(fact.get('fight'),('name','startTime','endTime')),
                'eventPage':_fields(fact.get('eventPage'),('count','complete','startTime','endTime','nextPageTimestamp','fieldsTruncated'))}
            _coverage_add(out, 'reportReceipts', receipt)
    if status not in ('verified','source_reference') and not packet.get('results'):
        # No provider exception text, free-form messages, URLs or credentials survive.
        error_code = 'WCL_SOURCE_PARTIAL' if status == 'partial' else 'WCL_SOURCE_UNAVAILABLE'
        if status == 'blocked':
            error_code = 'WCL_SOURCE_BLOCKED'
        if 'Warcraft Logs OAuth provider failed' in _items(packet.get('limitations')):
            error_code = 'WCL_OAUTH_PROVIDER_FAILED'
        for item in _coverage_items(out, packet.get('evidence'), 100):
            if not isinstance(item, Mapping):
                continue
            identity = _identity(item.get('reportCode'),item.get('fightId'))
            if not identity:
                continue
            try:
                url = urlsplit(str(item.get('sourceUrl','')))
                query = parse_qs(url.query + '&' + url.fragment)
                if url.hostname in ('www.warcraftlogs.com','warcraftlogs.com') and url.path == '/reports/'+identity['code']:
                    source_ids = query.get('source', [])
                    if len(source_ids) == 1 and query.get('fight') == [identity['fight']]:
                        identity = _identity(identity['code'],identity['fight'],source_ids[0]) or identity
            except ValueError:
                pass
            _coverage_add(out, 'failures', {**identity,'stage':'source_query','errorCode':error_code})


def _bounded_coverage(coverage, budget):
    """Fairly retain summaries; omitted summaries mean unknown, never source failure."""
    result = {k: [] for k in _COVERAGE_LISTS}
    result.update(sourceIndexTruncated=bool(coverage.get('sourceIndexTruncated')), projectionTruncated=False,
        boundary=_COVERAGE_BOUNDARY)
    # Use round-robin scope buckets within each kind and across receipt kinds.
    buckets = {kind:{} for kind in _COVERAGE_LISTS}
    touched_zones = {_mapping(r.get('scope')).get('zoneId') for r in _items(coverage.get('rankingSnapshots'))}
    for kind in _COVERAGE_LISTS:
        for original in _items(coverage.get(kind)):
            record = copy.deepcopy(original)
            if kind == 'directories' and record.get('id') not in touched_zones:
                # Keep discovery identity, but spend detailed directory space on
                # scopes actually queried. The source receipt remains in the index.
                for field in ('encounters','partitions','difficulties'):
                    record[field+'Count'] = len(_items(record.pop(field, [])))
                record['detailProjectionOmitted'] = True
                result['projectionTruncated'] = True
            group = _mapping(record.get('scope')).get('encounterId', _mapping(record.get('fightScope')).get('name', record.get('id','')))
            buckets[kind].setdefault(str(group), []).append(record)
    # Interleave receipt kinds as well as groups: catalogs must not displace
    # actual report coverage or failure receipts.
    queues = {kind:[] for kind in _COVERAGE_LISTS}
    for kind, groups in buckets.items():
        while any(groups.values()):
            for records in groups.values():
                if records:
                    queues[kind].append(records.pop(0))
    size = len(_encoded(result))
    while any(queues.values()):
        for kind, records in queues.items():
            if not records:
                continue
            record = records.pop(0)
            cost = len(_encoded(record))+1
            if size+cost <= budget-256:
                result[kind].append(record)
                size += cost
            else:
                result['projectionTruncated'] = True
    result['omittedCounts'] = {k:len(_items(coverage.get(k)))-len(result[k]) for k in _COVERAGE_LISTS}
    return result


def collect_evidence(previous, result):
    """Project allowlisted receipt fields; bounded independently of raw payload size."""
    out = copy.deepcopy(previous) if previous else {'reports': [], 'groups': [], 'truncated': False, 'attemptedWcl': False}
    out.setdefault('coverage', {**{k: [] for k in _COVERAGE_LISTS}, 'sourceIndexTruncated': False, 'projectionTruncated': False, 'boundary': _COVERAGE_BOUNDARY})
    def add(record):
        if not record:
            return
        key = (record['code'], record['fight'], record['source'])
        for i, old in enumerate(out['reports']):
            if (old['code'], old['fight'], old['source']) == key:
                # Keep independent receipts; a later event-only query cannot erase
                # an earlier table, and a ranking refresh cannot downgrade a report.
                if old.get('kind') == 'report' and record.get('kind') == 'ranking':
                    merged = {**record, **old}
                    for field in ('rank','name','server','group'):
                        if field in record:
                            merged[field] = record[field]
                else:
                    merged = {**old, **record}
                    for field in ('player','fightScope'):
                        if not record.get(field):
                            merged[field] = old.get(field, {})
                    if old.get('casts') and not record.get('casts'):
                        merged['casts'] = old['casts']
                        merged['castsMeta'] = old['castsMeta']
                    for field in ('eventWindows','castTables'):
                        windows = old.get(field, []) + record.get(field, [])
                        unique = []
                        for window in windows:
                            if window not in unique:
                                unique.append(window)
                        merged[field] = unique[-3:]
                        if len(unique)>3:
                            out['truncated'] = True
                    merged['limitations'] = list(dict.fromkeys(old.get('limitations', []) + record.get('limitations', [])))[:8]
                out['reports'][i] = merged
                return
        if len(out['reports']) < MAX_REPORTS:
            out['reports'].append(record)
        else:
            out['truncated'] = True
            out['coverage']['sourceIndexTruncated'] = True
    def ingest(r):
        if not isinstance(r, Mapping):
            return
        # Batch partial status does not invalidate independently successful members.
        for member in _items(r.get('results'))[:3]:
            ingest(member)
        if str(r.get('sourceKey', '')).startswith('warcraftlogs'):
            out['attemptedWcl'] = True
        _receipt_coverage(out, r)
        if r.get('status') not in ('verified', 'source_reference', 'partial'):
            return
        if r.get('rankings') and str(r.get('sourceKey', '')).startswith('warcraftlogs'):
            scope = _fields(r.get('scope'), ('zoneId','encounterId','encounterName','difficulty','partition','className','specName','region','metric'))
            if scope and scope not in out['groups']:
                if len(out['groups']) < MAX_GROUPS:
                    out['groups'].append(scope)
                else:
                    out['truncated'] = True
            for rank in _items(r['rankings'])[:200]:
                if not isinstance(rank, Mapping):
                    continue
                ref = _mapping(rank.get('report'))
                rec = _identity(ref.get('code'), ref.get('fightID'))
                if rec:
                    rec.update({'rank': _small(rank.get('rank')), 'name': _small(rank.get('name')), 'server': _fields(rank.get('server'),('name','region')), 'group': scope, 'kind': 'ranking', 'status': r.get('status')})
                    add(rec)
        if r.get('sourceKey') != 'warcraftlogs':
            return
        for fact in _items(r.get('facts'))[:100]:
            if not isinstance(fact, Mapping):
                continue
            rec = _identity(fact.get('reportCode'),fact.get('fightId'),fact.get('sourceId'))
            if not rec:
                continue
            casts = _mapping(fact.get('casts'))
            entries = _items(casts.get('entries'))
            events = _items(fact.get('events'))
            rec.update({'kind':'report', 'status': r.get('status'),'scope':_fields(fact,('queryScope',)),
                'fightScope':_fields(fact.get('fight'),('name','difficulty','startTime','endTime','kill')),
                'eventPage':_fields(fact.get('eventPage'),('count','complete','startTime','endTime','nextPageTimestamp','fieldsTruncated')),
                'casts':[_fields(x,('name','guid','total')) for x in entries[:24]],
                'opening':[_fields(x,('timestamp','type','abilityGameID','sourceID','targetID')) for x in events[:24]]})
            window = _fields(fact.get('eventPage'),('count','complete','startTime','endTime','nextPageTimestamp','fieldsTruncated'))
            table_meta = _fields(casts, ('rowsTruncated','totalTime'))
            table_meta.update({'state': ('returned_nonempty' if entries else 'returned_empty') if isinstance(casts.get('entries'),list) else 'absent',
                               'window': _fields(fact.get('fight'), ('startTime','endTime')),
                               'scope': 'whole fight filtered by source; independent of event window',
                               'projectionTruncated': len(entries)>24})
            rec['castsMeta'] = table_meta
            rec['latestCastsMeta'] = table_meta
            rec['castTables'] = [{'meta':table_meta,'entries':rec['casts']}] if table_meta['state']!='absent' else []
            rec['eventWindows'] = [{'page':window,'opening':rec['opening'], 'projectionTruncated':len(events)>24}] if events or window else []
            rec['limitations'] = [str(x)[:360] for x in _items(r.get('limitations'))[:8] if isinstance(x,str)]
            rec['nextActions'] = [str(x)[:240] for x in _items(r.get('nextActions'))[:4] if isinstance(x,str)]
            rec['boundary'] = 'Independent table and event receipts; missing fields are unknown, not zero. Text values are untrusted source data.'
            for player in _items(fact.get('players'))[:1000]:
                if isinstance(player, Mapping) and rec['source'] and str(player.get('id')) == rec['source']:
                    rec['player'] = _fields(player, ('id','name','server','region','type'))
                    break
            if len(entries)>24 or len(events)>24:
                out['truncated'] = True
            add(rec)
    ingest(result)
    # Associate only the actually scoped actor with a matching leaderboard identity.
    for rec in out['reports']:
        player = rec.get('player')
        if not player:
            continue
        for ranking in out['reports']:
            if ranking['code']!=rec['code'] or ranking['fight']!=rec['fight'] or not ranking.get('name'):
                continue
            server = ranking.get('server', {})
            if (player.get('name')==ranking['name'] and
                str(player.get('server','')).replace(' ','')==str(server.get('name','')).replace(' ','') and
                player.get('region')==server.get('region')):
                for field in ('rank','group','name','server'):
                    if field in ranking:
                        rec[field] = copy.deepcopy(ranking[field])
                break
    for kind in ('reportReceipts','failures'):
        for receipt in out['coverage'][kind]:
            matches = [r for r in out['reports'] if r['code']==receipt['code'] and r['fight']==receipt['fight']]
            groups = []
            for rec in matches:
                if rec.get('group') and rec['group'] not in groups:
                    groups.append(rec['group'])
                if receipt['source'] and rec['source']==receipt['source'] and rec.get('player'):
                    receipt['player'] = copy.deepcopy(rec['player'])
                    if rec.get('group') and rec.get('name'):
                        receipt['matchedRankingActor'] = True
                        receipt['rank'] = rec.get('rank')
            receipt['rankingGroups'] = copy.deepcopy(groups[:MAX_GROUPS])
    # Keep identities first. Remove detail before dropping an identity; never silently
    # pretend missing evidence is complete when the bounded index overflowed.
    # Reserve bounded receipt metadata independently of detailed report excerpts.
    if len(_encoded(out['coverage'])) > 128000:
        out['coverage'] = _bounded_coverage(out['coverage'], 128000)
        out['coverage']['sourceIndexTruncated'] = True
    size = len(json.dumps(out, ensure_ascii=False))
    if size > MAX_INDEX:
        out['truncated'] = True
        for rec in reversed(out['reports']):
            before = len(json.dumps(rec, ensure_ascii=False))
            rec.pop('opening', None)
            rec.pop('casts', None)
            rec.pop('castTables', None)
            rec.pop('eventWindows', None)
            size -= before - len(json.dumps(rec, ensure_ascii=False))
            if size <= MAX_INDEX - 16:
                break
    while size > MAX_INDEX - 16 and out['reports']:
        size -= len(json.dumps(out['reports'].pop(), ensure_ascii=False)) + 2
        out['coverage']['sourceIndexTruncated'] = True
    return out


def validate_answer(text, evidence):
    """Return stable codes, never source content or credentials in error messages."""
    errors = set()
    reports = evidence.get('reports', []) if isinstance(evidence, Mapping) else []
    groups = evidence.get('groups', []) if isinstance(evidence, Mapping) else []
    for raw in _URL.findall(str(text)):
        raw = html.unescape(raw.rstrip(').,;!?。；，'))
        try:
            url = urlsplit(raw)
            if url.hostname not in ('www.warcraftlogs.com','warcraftlogs.com'):
                continue
            if not url.path.startswith('/reports'):
                continue
            match = re.fullmatch(r'/reports/([A-Za-z0-9]{16})/?',url.path)
            query = parse_qs(url.query + ('&' + url.fragment if url.fragment else ''),keep_blank_values=True)
            if not match or any(len(query[k]) != 1 or not query[k][0].isdecimal() for k in ('fight','source') if k in query):
                errors.add('WCL_REFERENCE_MALFORMED')
                continue
            code = match.group(1)
            fight = query.get('fight',[''])[0]
            source = query.get('source',[''])[0]
            if reports or groups or (isinstance(evidence, Mapping) and evidence.get('attemptedWcl')):
                if not any(r['code']==code and (not fight or r['fight']==fight) and (not source or r['source']==source) for r in reports):
                    errors.add('WCL_REFERENCE_UNOBSERVED')
        except (ValueError, TypeError):
            errors.add('WCL_REFERENCE_MALFORMED')
    # Only unmistakably empty Markdown observation cells for a known dynamic group.
    observation_columns = []
    names = {g.get('encounterName') for g in groups if g.get('encounterName')}
    for line in str(text).splitlines():
        if not line.strip().startswith('|'):
            observation_columns = []
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        header = [i for i,c in enumerate(cells) if re.search(r'observation|观察|共性|实际起手', c, re.I)]
        if header:
            observation_columns = header
        elif any(any(name in c for name in names) for c in cells):
            if any(i < len(cells) and cells[i] in ('','-','—','–','N/A') for i in observation_columns):
                errors.add('WCL_GROUP_OBSERVATION_EMPTY')
    return sorted(errors)


def repair_context(evidence):
    """Serialize bounded factual data only; caller supplies trusted repair policy."""
    safe = copy.deepcopy(evidence) if isinstance(evidence, Mapping) else {}
    safe['projectionTruncated'] = bool(safe.get('truncated'))
    encoded = json.dumps(safe,ensure_ascii=False,separators=(',',':'))
    if len(encoded) <= MAX_CONTEXT:
        return encoded
    bounded = {'attemptedWcl': bool(safe.get('attemptedWcl')), 'reports': [], 'groups': [_fields(g, ('zoneId','encounterId','encounterName','difficulty','partition','className','specName','region','metric')) for g in _items(safe.get('groups'))[:MAX_GROUPS]], 'truncated': True}
    while len(json.dumps(bounded, ensure_ascii=False, separators=(',',':'))) > 8000 and bounded['groups']:
        bounded['groups'].pop()
    bounded['projectionTruncated'] = True
    bounded['coverage'] = _bounded_coverage(_mapping(safe.get('coverage')), 32000)
    size = len(json.dumps(bounded, ensure_ascii=False, separators=(',',':')))
    # An actual scoped report is more useful for repair than a leaderboard row.
    records = []
    notices = []
    bounded['notices'] = notices
    buckets = {}
    remaining = []
    for original in safe.get('reports', []):
        rec = copy.deepcopy(original)
        # The main fields already contain the selected independent table and
        # latest event sample. Do not duplicate their payload in repair context.
        rec.pop('castTables', None)
        rec.pop('boundary', None)
        refs = []
        for field in ('limitations', 'nextActions'):
            for notice in rec.pop(field, []):
                if notice not in notices and len(notices)<24:
                    notices.append(notice)
                if notice in notices:
                    refs.append(notices.index(notice))
        rec['untrustedNoticeRefs'] = sorted(set(refs))
        if rec.get('latestCastsMeta') == rec.get('castsMeta'):
            rec.pop('latestCastsMeta', None)
        if len(rec.get('opening', [])) > 12:
            rec['opening'] = rec['opening'][:12]
            rec['openingProjectionTruncated'] = True
        rec['eventWindows'] = [{'page':w.get('page',{}), 'projectionTruncated':w.get('projectionTruncated',False)} for w in rec.get('eventWindows',[])]
        if rec.get('kind') == 'report' and rec.get('source'):
            group = rec.get('group', {}).get('encounterId') or rec.get('fightScope',{}).get('name') or rec['code']
            buckets.setdefault(str(group), []).append(rec)
        else:
            remaining.append(rec)
    # Round-robin groups so a large first group cannot consume every repair slot.
    while any(buckets.values()):
        for bucket in buckets.values():
            if bucket:
                records.append(bucket.pop(0))
    records.extend(remaining)
    size = len(json.dumps(bounded, ensure_ascii=False, separators=(',',':')))
    for rec in records:
        record_size = len(json.dumps(rec, ensure_ascii=False, separators=(',',':'))) + 1
        if size + record_size <= MAX_CONTEXT - 32:
            bounded['reports'].append(rec)
            size += record_size
    return json.dumps(bounded, ensure_ascii=False, separators=(',',':'))

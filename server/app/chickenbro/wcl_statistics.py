"""Deterministic, bounded event-window statistics; never a causal assessment."""
from collections import Counter
from math import isfinite

from server.app.simulation.sources import InvalidSourceLink


def _number(value):
    return type(value) in (int, float) and isfinite(value) and value >= 0


def summarize_window(reference, options, credentials, fetch):
    start, end = options['startTime'], options['endTime']
    cursor = start
    source = int(reference['sourceId'])
    rows, pages, last = [], 0, None
    complete, malformed = False, False
    failures = []
    for _ in range(options.get('maxPages', 3)):
        try:
            page_options = {k:v for k,v in options.items() if k != 'maxPages'}
            page_options.update(view='events', startTime=cursor)
            page = fetch(reference, credentials, page_options)
        except InvalidSourceLink as error:
            failures.append(str(error))
            break
        except Exception:
            failures.append('A statistics page failed; only previously read intervals are included.')
            break
        pages += 1
        last = page
        fight = page.get('fight', {})
        if (not _number(fight.get('startTime')) or not _number(fight.get('endTime')) or
                start < fight['startTime'] or end > fight['endTime']):
            failures.append('The statistics window must be within the selected fight in report-relative milliseconds.')
            break
        if page.get('sourceStatus') != 'verified':
            failures.append('A statistics page is partial; no events from that page were counted.')
            break
        coverage = page.get('eventPage', {})
        next_cursor = coverage.get('nextPageTimestamp')
        if next_cursor is not None and (not _number(next_cursor) or not cursor < next_cursor <= end):
            failures.append('The pagination cursor did not advance within the requested window.')
            break
        if coverage.get('fieldsTruncated'):
            failures.append('Event fields were truncated; no events from that page were counted.')
            break
        if next_cursor is None and not coverage.get('complete'):
            failures.append('Event pagination completeness is unavailable.')
            break
        boundary = next_cursor if next_cursor is not None else end
        # WCL continuations start at nextPageTimestamp. Count disjoint half-open
        # intervals, never deduplicate identical events (they can be legitimate).
        for row in page.get('events', []):
            timestamp, actor = row.get('timestamp'), row.get('sourceID')
            if not _number(timestamp) or type(actor) is not int:
                malformed = True
                continue
            if actor == source and cursor <= timestamp < boundary:
                rows.append(row)
        cursor = boundary
        if next_cursor is None:
            complete = True
            break
    casts, resources = Counter(), {}
    healing = {'effective':0, 'overheal':0, 'missingValues':0, 'events':0}
    missing = 0
    for row in rows:
        kind = row.get('type')
        if kind == 'cast':
            ability = row.get('abilityGameID')
            if type(ability) is int and ability > 0 and (ability in casts or len(casts) < 128):
                casts[ability] += 1
            else:
                missing += 1
        if kind == 'heal':
            healing['events'] += 1
            for input_key, output_key in [('amount', 'effective'), ('overheal', 'overheal')]:
                if _number(row.get(input_key)):
                    healing[output_key] += row[input_key]
                else:
                    healing['missingValues'] += 1
        if 'resourceChangeType' in row or 'waste' in row:
            resource = row.get('resourceChangeType')
            if type(resource) is not int or resource < 0 or (resource not in resources and len(resources) >= 128):
                missing += 1
                continue
            entry = resources.setdefault(resource, {'resourceType':resource, 'waste':0, 'missingValues':0})
            if _number(row.get('waste')):
                entry['waste'] += row['waste']
            else:
                entry['missingValues'] += 1
    metric_missing = missing + healing['missingValues'] + sum(r['missingValues'] for r in resources.values())
    if not complete:
        failures.append('Window is incomplete. Totals are observed subtotals, not whole-window totals.')
    if malformed or metric_missing:
        failures.append('Some event values are missing, invalid or exceed the 128-group bound; reported sums include retained known values only.')
    result = {k:v for k,v in (last or {}).items() if k not in ('events','eventPage','eventSummary','nextActions','blockers')}
    # Identity survives even when the first upstream page fails; it is not evidence.
    result.update(reportCode=reference['reportCode'], sourceUrl=reference['sourceUrl'],
                  fightId=reference.get('fightId'), sourceId=reference['sourceId'], view='statistics',
                  sourceStatus='verified' if complete and not malformed and not metric_missing else 'partial',
                  queryScope='window_statistics', blockers=failures,
                  evidenceRefs=['wcl.report','wcl.fight','wcl.statistics'] if rows or complete else [],
                  nextActions=['Use only the returned actor and event filter. Healing excludes absorbs and other actors/pets. '
                               'Missing event kinds do not prove absence outside this filter. Resource waste is not lost effective healing.'])
    result['statistics'] = {
        'startTime':start, 'endTime':end, 'observedThrough':cursor,
        'dataType':options.get('dataType','All'), 'sourceId':source,
        'complete':complete and not malformed, 'metricsComplete':not malformed and not metric_missing,
        'nextPageTimestamp':None if complete else cursor, 'pagesRead':pages, 'eventCount':len(rows),
        'casts':[{'abilityId':key,'count':value} for key,value in sorted(casts.items())],
        'healing':healing if healing['events'] else None,
        'resources':list(resources.values()), 'missingValues':metric_missing,
        'intervalConvention':'[startTime,endTime); source actor only; known-value subtotals',
    }
    return result

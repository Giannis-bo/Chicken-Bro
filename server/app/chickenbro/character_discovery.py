"""Bounded public character/report discovery using server-owned WCL credentials."""
import re
from urllib.parse import quote
from server.app.chickenbro.wcl_source import _graphql
from server.app.simulation.sources import InvalidSourceLink

_REGIONS = {'cn', 'us', 'eu', 'tw', 'kr'}
_SERVER_QUERY = '''query($region:String!,$realm:String!){worldData{server(region:$region,slug:$realm){id name slug region{slug}}}}'''
_CHARACTER_QUERY = '''query($name:String!,$realm:String!,$region:String!,$page:Int!,$limit:Int!){
 characterData{character(name:$name,serverSlug:$realm,serverRegion:$region){id name hidden
 server{id name slug region{slug}}
 recentReports(limit:$limit,page:$page){data{code title startTime endTime} current_page has_more_pages}}}}'''


def _part(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise InvalidSourceLink()
    value = value.strip()
    if any(c in value for c in '/\\?#@:%') or any(ord(c) < 32 for c in value):
        raise InvalidSourceLink()
    return value


def resolve_wcl_realm(region, realm):
    region, realm = _part(region).lower(), _part(realm)
    if region not in _REGIONS:
        raise InvalidSourceLink()
    server = (_graphql(_SERVER_QUERY, {'region': region, 'realm': realm}).get('worldData') or {}).get('server')
    if not isinstance(server, dict):
        return None
    if (str((server.get('region') or {}).get('slug', '')).lower() != region
            or not server.get('id') or not server.get('slug')):
        return None
    return server


def _packet(status, *, facts=None, pagination=None):
    return {'sourceKey': 'warcraftlogs_character', 'status': status, 'facts': facts or [],
            'evidence': [], 'limitations': [] if status == 'source_reference' else [status],
            'nextActions': ['Use a report URL, then match actor name AND server and select participating fights.']
                if status == 'source_reference' else [], 'pagination': pagination or {}}


def discover_wcl_character(options):
    if not isinstance(options, dict) or set(options) - {'name','realm','region','page','limit'}:
        raise InvalidSourceLink()
    name, realm, region = (_part(options.get(k)) for k in ('name','realm','region'))
    region = region.lower()
    if region not in _REGIONS:
        raise InvalidSourceLink()
    page, limit = options.get('page', 1), options.get('limit', 5)
    if type(page) is not int or not 1 <= page <= 20 or type(limit) is not int or not 1 <= limit <= 10:
        raise InvalidSourceLink()
    try:
        server = resolve_wcl_realm(region, realm)
        if not server:
            return _packet('realm_not_found')
        data = _graphql(_CHARACTER_QUERY, {'name':name,'realm':server['slug'],'region':region,'page':page,'limit':limit})
        character = (data.get('characterData') or {}).get('character')
        if character is None:
            return _packet('not_found')
        actual_server = character.get('server') or {}
        if (str(character.get('name','')).casefold() != name.casefold()
                or actual_server.get('id') != server['id']
                or str((actual_server.get('region') or {}).get('slug','')).lower() != region):
            return _packet('identity_mismatch')
        if character.get('hidden'):
            return _packet('access_restricted')
        recent = character.get('recentReports')
        if not isinstance(recent, dict) or not isinstance(recent.get('data'), list) or recent.get('current_page') != page:
            return _packet('unavailable')
        reports, seen = [], set()
        for report in recent['data'][:limit]:
            code = report.get('code') if isinstance(report, dict) else None
            if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9]{16}', code) or code in seen:
                continue
            seen.add(code)
            reports.append({'code':code,'url':'https://www.warcraftlogs.com/reports/'+code,
                            'title':str(report.get('title') or '')[:256],
                            'startTime':report.get('startTime'),'endTime':report.get('endTime')})
        identity = {'id':character['id'],'name':character['name'],'region':region,
                    'realm':server.get('name'),'realmSlug':server['slug']}
        url = 'https://www.warcraftlogs.com/character/' + '/'.join(quote(x, safe='') for x in (region,server['slug'],character['name']))
        return _packet('source_reference', facts=[{'character':identity,'sourceUrl':url,'reports':reports}],
                       pagination={'page':page,'limit':limit,'returned':len(reports),
                                   'nextPage':page+1 if recent.get('has_more_pages') and page < 20 else None,
                                   'hasMore':bool(recent.get('has_more_pages'))})
    except Exception:
        return _packet('unavailable')

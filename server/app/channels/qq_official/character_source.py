"""Read public character facts and WCL percentages, with exact source scopes."""
from datetime import datetime, timezone
import math
import re
from time import monotonic
from urllib.parse import quote, unquote, urlencode, urlsplit

from server.app.chickenbro.wcl_source import _graphql
from server.app.simulation.sources import HttpxSourceGateway
from .query_commands import REGIONS, clean, DEFAULT_RECENT_LIMIT
from .query_labels import label, matches, normalized, HEALERS

CHARACTER_QUERY = '''query($name:String!,$realm:String!,$region:String!){characterData{
 character(name:$name,serverSlug:$realm,serverRegion:$region){id name hidden
 server{name slug region{slug}} gameData}}}'''
CATALOG_QUERY = '''{worldData{zones{id name frozen encounters{id name}
 partitions{id name default} difficulties{id name}}}}'''


def finite(value, lower=0, upper=100):
    return type(value) in (int,float) and math.isfinite(value) and lower <= value <= upper


def dictionary(value):
    return value if isinstance(value, dict) else {}


class CharacterQuerySource:
    def __init__(self, *, graphql=None, fetch=None):
        self.graphql = graphql or _graphql
        self.fetch = fetch or HttpxSourceGateway(timeout_seconds=12).fetch_json

    def query(self, request):
        # All state is per request: safe for simultaneous users/characters.
        packet = {'identity': f'{request.name}｜{request.realm}｜{REGIONS[request.region]}',
                  'queriedAt':datetime.now(timezone.utc).isoformat(), 'sections':[], 'sources':[]}
        deadline = monotonic() + 100
        def graphql(query, variables=None):
            remaining = min(18, deadline - monotonic())
            if remaining <= 0: raise TimeoutError()
            return self.graphql(query, variables or {}, timeout_seconds=remaining)
        try:
            raw = graphql(CHARACTER_QUERY, {'name':request.name,'realm':request.realm,'region':request.region})
            character = dictionary(dictionary(raw.get('characterData')).get('character'))
            wcl_status = 'ok' if character else 'not_found'
        except Exception:
            character = {}; wcl_status = 'unavailable'
        server = dictionary(character.get('server'))
        if character and (normalized(character.get('name')) != normalized(request.name)
            or dictionary(server.get('region')).get('slug','').casefold() != request.region
            or normalized(request.realm) not in {normalized(server.get('slug')), normalized(server.get('name'))}
            or type(character.get('id')) is not int or character['id'] <= 0):
            packet['sections'].append({'title':'角色','status':'identity_mismatch'})
            return packet
        if character.get('hidden') is True:
            packet['sections'].append({'title':'WCL','status':'hidden'})
            return packet
        realm = server.get('slug') or request.realm
        profile, spec = self._profile(request, realm, character)
        if request.kind == 'character':
            packet['profile'] = profile
            packet['sources'].extend(profile.pop('links', []))
        if wcl_status != 'ok':
            packet['sections'].append({'title':'WCL','status':wcl_status})
            return packet
        wcl_link = 'https://www.warcraftlogs.com/character/' + '/'.join(quote(p,safe='-_.~') for p in (request.region,realm,character['name']))
        packet['sources'].append(wcl_link)
        try:
            zones = graphql(CATALOG_QUERY)['worldData']['zones']
            if not isinstance(zones,list): raise ValueError()
            live = [z for z in zones if z.get('frozen') is False and
                    'ptr' not in z.get('name','').casefold() and 'test' not in z.get('name','').casefold()]
            wanted = ('raid','mplus') if request.kind == 'character' else (request.kind,)
            for kind in wanted:
                named = request.raid if kind == 'raid' else ''
                eligible = [z for z in (zones if named else live) if 'ptr' not in z.get('name','').casefold() and 'test' not in z.get('name','').casefold()]
                candidates = [z for z in eligible if ((10 in [d.get('id') for d in z.get('difficulties',[])]) == (kind == 'mplus'))
                              and z.get('encounters') and (kind == 'mplus' or any(d.get('id') in (3,4,5) for d in z.get('difficulties',[])))]
                if named:
                    candidates = matches(named,candidates)
                    if len(candidates) != 1:
                        packet['sections'].append(self._candidates('团本',candidates or live))
                        continue
                if not candidates:
                    packet['sections'].append({'title':'团本' if kind=='raid' else '大米','status':'unavailable'})
                    continue
                if kind=='raid' and request.boss_index is not None and len(candidates)!=1:
                    section=self._candidates('团本',candidates)
                    section['message']='按 Boss 序号查询时请先指定 团本=名称。'+section['message']
                    packet['sections'].append(section)
                    continue
                sections = []
                for zone in candidates:
                    if kind == 'raid':
                        sections.extend(self._raid(graphql,request,character['id'],zone,spec))
                    else:
                        sections.append(self._mplus(graphql,request,character['id'],zone,spec))
                packet['sections'].append(recent_section(kind, sections))
        except Exception:
            packet['sections'].append({'title':'WCL 当前目录','status':'unavailable'})
        return packet

    def _profile(self, request, realm, character):
        global_data = dictionary(dictionary(character.get('gameData')).get('global'))
        result = {'source':'Raider.IO', 'links':[]}; spec = ''
        endpoint = 'https://raider.io/api/v1/characters/profile?' + urlencode(
            {'region':request.region,'realm':realm,'name':request.name,'fields':'gear,talents'})
        try:
            raw = self.fetch(endpoint)
            parts = [unquote(p) for p in urlsplit(raw.get('profile_url','')).path.split('/') if p]
            if (normalized(raw.get('name')) != normalized(request.name) or raw.get('region','').casefold() != request.region
                or len(parts) != 4 or parts[:2] != ['characters',request.region]
                or normalized(parts[2]) != normalized(realm) or normalized(parts[3]) != normalized(request.name)
                or urlsplit(raw.get('profile_url','')).hostname not in ('raider.io','www.raider.io')
                or urlsplit(raw.get('profile_url','')).scheme != 'https'):
                raise ValueError('identity mismatch')
            # A realm display-name alias must be verified against the details object.
            details_url = 'https://raider.io/api/characters/' + '/'.join(quote(p,safe='-_.~') for p in (request.region,realm,request.name))
            try:
                details = dictionary(dictionary(self.fetch(details_url).get('characterDetails')).get('character'))
            except Exception: details = {}
            aliases = {normalized(v) for v in (realm,server_name(character),raw.get('realm')) if v}
            d_realm = dictionary(details.get('realm'))
            detail_valid = (normalized(details.get('name')) == normalized(request.name)
                            and dictionary(details.get('region')).get('slug') == request.region
                            and normalized(d_realm.get('slug')) == normalized(realm)
                            and normalized(unquote(details.get('path',''))) == normalized(f'/characters/{request.region}/{realm}/{request.name}'))
            if detail_valid:
                aliases.update(normalized(d_realm.get(k)) for k in ('name','altName','slug','altSlug'))
            if normalized(request.realm) not in aliases: raise ValueError('realm mismatch')
            spec = str(raw.get('active_spec_name') or '')
            gear = dictionary(raw.get('gear'))
            result.update({'race':label(raw.get('race')),'class':label(raw.get('class')),'spec':label(spec),
                           'itemLevel':gear.get('item_level_equipped') if finite(gear.get('item_level_equipped'),1,2000) else None,
                           'sourceTime':gear.get('updated_at') or raw.get('last_crawled_at'),
                           'links':['https://raider.io/characters/' + '/'.join(quote(p,safe='-_.~') for p in (request.region,realm,request.name))]})
            if detail_valid and dictionary(details.get('spec')).get('name') == spec:
                hero_id = dictionary(details.get('talentLoadout')).get('heroSubTreeId')
                if type(hero_id) is int and hero_id > 0:
                    # WCL tree name is a label for the same current Raider.IO tree ID,
                    # never a fallback selection from an old profile.
                    result['hero'] = '英雄天赋树 #' + str(hero_id)
                    for s in dictionary(dictionary(character.get('gameData')).get('talents')).get('specializations',[]):
                        for loadout in s.get('loadouts',[]):
                            hero = dictionary(loadout.get('selected_hero_talent_tree'))
                            if hero.get('id') == hero_id and hero.get('name'):
                                result['hero'] = hero['name']
            return result, spec
        except Exception:
            # WCL's saved public profile is a time-labelled fallback, not current armory.
            if (normalized(global_data.get('name')) == normalized(request.name)
                and normalized(dictionary(global_data.get('realm')).get('slug')) == normalized(realm)):
                result.update({'race':dictionary(global_data.get('race')).get('name'),
                               'class':dictionary(global_data.get('character_class')).get('name'),
                               'spec':dictionary(global_data.get('active_spec')).get('name'),
                               'itemLevel':global_data.get('equipped_item_level'),
                               'source':'WCL 已保存角色资料（非实时）',
                               'sourceTime':global_data.get('last_login_timestamp')})
            else: result['source'] = '角色资料查询失败'
            return result, spec

    @staticmethod
    def _candidates(title, entries):
        names = '、'.join(label(e['name']) + '（' + str(e['id']) + '）' for e in entries[:15])
        return {'title':title,'status':'selection','message':'名称未匹配或有歧义，请使用完整名称或编号：' + names,'rows':[]}

    @staticmethod
    def _partition(zone):
        defaults = [p for p in zone.get('partitions',[]) if p.get('default') is True]
        if len(defaults) != 1 or type(defaults[0].get('id')) is not int: raise ValueError('ambiguous partition')
        return defaults[0]

    def _raid(self, graphql, request, cid, zone, spec):
        encounters = zone['encounters']
        if request.boss_index is not None:
            if not 1<=request.boss_index<=len(encounters):
                section=self._candidates('Boss',encounters)
                section['message']=f'Boss 序号超出范围，本团本支持 1–{len(encounters)}。'+section['message']
                return [section]
            encounters=[encounters[request.boss_index-1]]
        elif request.boss:
            encounters = matches(request.boss,encounters)
            if len(encounters) != 1: return [self._candidates('Boss',encounters or zone['encounters'])]
        diffs = [d for d in zone['difficulties'] if (d['id']==request.difficulty if request.difficulty else d['id'] in (3,4,5))]
        if not diffs:
            return [{'status':'selection','rows':[], 'message':'该团本不提供指定难度；请使用其目录中的难度。'}]
        section=self._encounters(graphql,request,cid,zone,encounters,[d['id'] for d in diffs],False)
        if request.boss_index is not None:
            section['scope']+=f' · {request.boss_index}号 {label(encounters[0]["name"])}'
        return [section]

    def _mplus(self, graphql, request, cid, zone, spec):
        encounters = zone['encounters']
        if request.dungeon:
            encounters = matches(request.dungeon,encounters)
            if len(encounters) != 1: return self._candidates('大米副本',encounters or zone['encounters'])
        return self._encounters(graphql,request,cid,zone,encounters,[10],True)

    def _encounters(self, graphql, request, cid, zone, encounters, difficulties, mplus):
        # WCL All keeps older patch records in the latest-five raid view.
        partition = self._partition(zone) if mplus else {'id':-1,'name':'全部分区'}
        scopes = [(e,d,metric) for e in encounters for d in difficulties for metric in ('dps','hps')]
        fields = [f'q{i}:encounterRankings(encounterID:{e["id"]},difficulty:{d},partition:{partition["id"]},metric:{metric},compare:Rankings,timeframe:Historical,byBracket:{str(mplus).lower()},includeCombatantInfo:false,includeOtherPlayers:false,includePrivateLogs:false)' for i,(e,d,metric) in enumerate(scopes)]
        data = self._scores(graphql,cid,fields)
        scope = f'{label(zone["name"])} · {partition["name"]}'
        section = {'scope':scope, 'rows':[]}
        invalid = missing = False
        difficulty_names = {1:'随机团队',3:'普通',4:'英雄',5:'史诗'}
        for i,(e,d,metric) in enumerate(scopes):
            payload = dictionary(data.get('q'+str(i)))
            if not self._valid_scope(payload,zone,partition,d,metric) or not isinstance(payload.get('ranks'),list):
                missing=True; continue
            ranks = payload['ranks']
            if type(payload.get('totalKills')) is not int or payload['totalKills'] != len(ranks):
                invalid=True
            for row in ranks:
                if row.get('spec') and ((row['spec'] in HEALERS) != (metric == 'hps')): continue
                level = row.get('bracketData')
                if mplus and request.level is not None and level != request.level: continue
                if (not row.get('spec') or not finite(row.get('rankPercent'))
                    or not finite(row.get('startTime'),1,datetime.now(timezone.utc).timestamp()*1000+60000)
                    or not report_url(row) or (mplus and (type(level) is not int or not 2 <= level <= 99))):
                    invalid=True; continue
                result = {'name':label(e['name']), 'spec':label(row['spec']),
                          'metric':metric.upper(), 'percentile':row['rankPercent'],
                          'recordedAt':row['startTime'], 'reportUrl':report_url(row),
                          'scope':scope, '_encounter':e['id'], '_difficulty':d}
                if mplus:
                    medal = row.get('medal')
                    result.update(level=level,timed=True if medal in ('bronze','silver','gold') else False if medal=='none' else None)
                else: result['difficulty']=difficulty_names.get(d,str(d))
                section['rows'].append(result)
        section['status'] = 'partial' if invalid or (missing and section['rows']) else 'unavailable' if missing else 'ok' if section['rows'] else 'no_records'
        return section

    @staticmethod
    def _valid_scope(payload,zone,partition,difficulty,metric):
        return (payload.get('zone') == zone['id'] and payload.get('partition') == partition['id']
                and payload.get('difficulty') == difficulty and payload.get('metric') == metric)

    @staticmethod
    def _scores(graphql,cid,fields):
        query = 'query($id:Int!){characterData{character(id:$id){id ' + ' '.join(fields) + '}}}'
        try:
            data = dictionary(dictionary(graphql(query,{'id':cid}).get('characterData')).get('character'))
            return data if data.get('id') == cid else {}
        except Exception: return {}


def server_name(character):
    return dictionary(character.get('server')).get('name','')


def report_url(row):
    report = dictionary(row.get('report'))
    code = report.get('code'); fight = report.get('fightID')
    if isinstance(code,str) and re.fullmatch(r'[A-Za-z0-9]{16}',code) and type(fight) is int and fight > 0:
        return f'https://www.warcraftlogs.com/reports/{code}?fight={fight}'
    return None


def recent_section(kind, sections):
    """Merge all difficulties/metrics/zones before time sort, dedup and limit."""
    result = {'title':'团本' if kind=='raid' else '大秘境', 'rows':[]}
    statuses = {s.get('status') for s in sections}
    seen = set()
    for row in sorted((r for s in sections for r in s.get('rows',[])),key=lambda r:r['recordedAt'],reverse=True):
        # The same character/fight can appear in duplicate uploads or metrics.
        key = (row.get('_encounter'),row.get('_difficulty'),row['recordedAt'],row.get('level'))
        if key in seen: continue
        seen.add(key)
        result['rows'].append({k:v for k,v in row.items() if not k.startswith('_')})
        if len(result['rows']) == DEFAULT_RECENT_LIMIT: break
    result['scope'] = '；'.join(dict.fromkeys(s['scope'] for s in sections if s.get('scope')))
    if result['rows']:
        result['status'] = 'partial' if statuses & {'partial','unavailable','selection'} else 'ok'
    elif 'selection' in statuses:
        result.update(status='selection',message='；'.join(s.get('message','') for s in sections if s.get('message')))
    else:
        result['status'] = 'unavailable' if 'unavailable' in statuses else 'partial' if 'partial' in statuses else 'no_records'
    return result

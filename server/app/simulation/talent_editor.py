"""Version-bound talent exports and precise edits; never guess missing tree rules."""
import re
from collections.abc import Mapping
from functools import lru_cache
import json
from pathlib import Path
from server.app.simulation.wcl_talents import _catalog, reconstruct_fight_talents
from server.app.simulation.specializations import canonical_class
from server.app.simulation.localization import catalog_for_build

_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
_CLASSES = dict(enumerate(('warrior', 'paladin', 'hunter', 'rogue', 'priest', 'death_knight',
                          'shaman', 'mage', 'warlock', 'monk', 'druid', 'demon_hunter', 'evoker'), 1))

class TalentEditError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

@lru_cache(maxsize=1)
def _labels():
    return json.loads((Path(__file__).parent / 'data/trait-labels-12.1.0.json').read_text())

def _context(character, runtime):
    catalog, traits = _catalog()
    match = re.fullmatch(r'simc:managed:([0-9a-f]{40}):[0-9a-f]{64}', runtime or '')
    if not match or match[1] != catalog['revision']:
        raise TalentEditError('TALENT_CATALOG_RUNTIME_MISMATCH')
    if not isinstance(character, Mapping) or character.get('level') != 90:
        raise TalentEditError('TALENT_LEVEL_UNSUPPORTED')
    class_id = next((i for i, name in _CLASSES.items() if name == canonical_class(character.get('classKey'))), None)
    traits = [t for t in traits if t['classId'] == class_id]
    spec_id = next((int(k) for k,v in catalog['specializations'].items()
                    if v == character.get('specKey') and any(int(k) in t['specs'] for t in traits)), None)
    if spec_id is None:
        raise TalentEditError('TALENT_SPEC_INVALID')
    nodes = {}
    for trait in traits:
        nodes.setdefault(trait['nodeId'], []).append(trait)
    return catalog, spec_id, class_id, nodes

def normalize_talent_override(value):
    if not isinstance(value, Mapping) or len(value) != 1:
        raise TalentEditError('TALENT_OVERRIDE_INVALID')
    if 'string' in value:
        code = value['string']
        if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9+/]{26,512}', code):
            raise TalentEditError('TALENT_EXPORT_INVALID')
        return {'string': code}
    nodes = value.get('nodes')
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= 128:
        raise TalentEditError('TALENT_OVERRIDE_INVALID')
    seen = set(); result = []
    for entry in nodes:
        if (not isinstance(entry, Mapping) or set(entry) != {'nodeId', 'entryId', 'rank'}
                or any(type(entry[k]) is not int for k in entry)
                or not 1 <= entry['nodeId'] < 2**31 or not 1 <= entry['entryId'] < 2**31
                or not 0 <= entry['rank'] <= 63 or entry['nodeId'] in seen):
            raise TalentEditError('TALENT_OVERRIDE_INVALID')
        seen.add(entry['nodeId']); result.append(dict(entry))
    return {'nodes': sorted(result, key=lambda x: x['nodeId'])}

def _encode(entries, character, spec_id, class_id):
    result = reconstruct_fight_talents(entries, spec_id, {'class': {'id': class_id}, 'level': character['level']}, character['specKey'])
    if result is None:
        raise TalentEditError('TALENT_BUILD_INVALID')
    return result[0]

def decode_talents(code, character, runtime):
    _, spec_id, class_id, nodes = _context(character, runtime)
    normalize_talent_override({'string': code})
    bits = [(_ALPHABET.index(c) >> bit) & 1 for c in code for bit in range(6)]
    pos = 0
    def take(width):
        nonlocal pos
        if pos + width > len(bits):
            raise TalentEditError('TALENT_EXPORT_INVALID')
        value = sum(bits[pos+i] << i for i in range(width)); pos += width
        return value
    if take(8) != 2 or take(16) != spec_id:
        raise TalentEditError('TALENT_SPEC_INVALID')
    take(128)  # Export hash is not a source of node order; catalog is runtime-bound.
    result = []
    granted_nodes = set()
    for node_id, entries in sorted(nodes.items()):
        if not take(1):
            continue
        purchased = take(1)
        if not purchased:
            granted_nodes.add(node_id)
            # The export carries the grant bit. SimC imports the first entry
            # here; display coordinates are not a reliable grant predicate.
            result.append({'id': entries[0]['entryId'], 'nodeID': node_id, 'rank': 1})
            continue
        partial = take(1)
        rank = take(6) if partial else None
        choice = take(1)
        if choice and entries[0]['nodeType'] not in (2,3):
            raise TalentEditError('TALENT_EXPORT_INVALID')
        index = take(2) if choice else 0
        if index >= len(entries):
            raise TalentEditError('TALENT_EXPORT_INVALID')
        if entries[0]['nodeType'] == 1:
            remaining = rank if partial else sum(t['maxRanks'] for t in entries)
            for t in entries:
                spent = min(remaining, t['maxRanks']); remaining -= spent
                if spent: result.append({'id': t['entryId'], 'nodeID': node_id, 'rank': spent})
            if remaining: raise TalentEditError('TALENT_EXPORT_INVALID')
        else:
            t = entries[index]
            result.append({'id': t['entryId'], 'nodeID': node_id, 'rank': rank if partial else t['maxRanks']})
    if len(bits) - pos > 5 or any(bits[pos:]):
        raise TalentEditError('TALENT_EXPORT_INVALID')
    by_id = {t['entryId']: t for entries in nodes.values() for t in entries}
    selected_heroes = {by_id[e['id']]['subTreeId'] for e in result if by_id[e['id']]['tree'] == 4}
    # Blizzard exports free roots of inactive hero trees too. They are not
    # allocated talents; preserve only the active subtree, as Raider.IO does.
    result = [e for e in result if not (e['nodeID'] in granted_nodes and
              by_id[e['id']]['tree'] == 3 and by_id[e['id']]['subTreeId'] not in selected_heroes)]
    _encode(result, character, spec_id, class_id)
    return result

def _loadout(talents, character, runtime):
    if talents.get('string'):
        return decode_talents(talents['string'], character, runtime)
    _, spec_id, class_id, nodes = _context(character, runtime)
    by_id = {t['entryId']: t for entries in nodes.values() for t in entries}
    result = []
    for e in talents.get('loadout', []):
        entry_id = e.get('id', e.get('talentId')); rank = e.get('rank', e.get('points'))
        if type(entry_id) is not int or entry_id not in by_id or type(rank) is not int:
            raise TalentEditError('TALENT_BUILD_INVALID')
        result.append({'id':entry_id, 'rank':rank, 'nodeID':by_id[entry_id]['nodeId']})
    _encode(result, character, spec_id, class_id)
    return result

def talent_difference(before, after, character, runtime):
    old = _loadout(before, character, runtime)
    new = _loadout(after, character, runtime)
    return [{'nodeId':n, 'before':[e for e in old if e['nodeID']==n],
             'after':[e for e in new if e['nodeID']==n]}
            for n in sorted({e['nodeID'] for e in old + new})
            if sorted((e['id'],e['rank']) for e in old if e['nodeID']==n) !=
               sorted((e['id'],e['rank']) for e in new if e['nodeID']==n)]

@lru_cache(maxsize=1)
def _paths():
    return json.loads((Path(__file__).parent / 'data/trait-paths-12.1.0.json').read_text())

def _validate_paths(rows, spec_id, nodes):
    catalog = _catalog()[0]
    paths = _paths()
    if paths['revision'] != catalog['revision'] or paths['engineSourceSha256'] != catalog['sourceSha256']:
        raise TalentEditError('TALENT_CATALOG_RUNTIME_MISMATCH')
    graph = paths.get('specs', {}).get(str(spec_id), {}).get('nodes')
    if not graph:
        raise TalentEditError('TALENT_PATH_RULES_UNAVAILABLE')
    by_id = {t['entryId']: t for entries in nodes.values() for t in entries}
    selected = {e['nodeID'] for e in rows}
    ranks = {n: sum(e['rank'] for e in rows if e['nodeID'] == n) for n in selected}
    labels = _labels()['entries']
    parents = {n: set() for n in selected}
    for parent, node in graph.items():
        for child in node['children']:
            if child in parents:
                parents[child].add(int(parent))
    for e in rows:
        n = e['nodeID']; t = by_id[e['id']]
        if str(n) not in graph or e['id'] not in graph[str(n)]['entries']:
            raise TalentEditError('TALENT_PATH_RULES_UNAVAILABLE')
        maximum = lambda p: (sum(x['maxRanks'] for x in nodes[p]) if nodes[p][0]['nodeType'] == 1
                             else max(x['maxRanks'] for x in nodes[p]))
        if parents[n] and not any(p in selected and ranks[p] == maximum(p) for p in parents[n]):
            raise TalentEditError('TALENT_PREREQUISITE_INVALID')
        gate = labels[str(e['id'])]['requiredPoints']
        if gate and t['tree'] == 3:
            # Hero traits consume the activated subtree selector condition.
            if gate != 1 or not any(by_id[x['id']]['tree'] == 4 and
                                   by_id[x['id']]['subTreeId'] == t['subTreeId'] for x in rows):
                raise TalentEditError('TALENT_POINT_GATE_INVALID')
        elif gate:
            available = sum(x['rank'] - int(spec_id in by_id[x['id']]['starterSpecs']) for x in rows
                            if by_id[x['id']]['tree'] == t['tree']
                            and labels[str(x['id'])]['requiredPoints'] < gate)
            if available < gate:
                raise TalentEditError('TALENT_POINT_GATE_INVALID')

def edit_talents(talents, character, runtime, override):
    override = normalize_talent_override(override)
    _, spec_id, class_id, nodes = _context(character, runtime)
    original = _loadout(talents, character, runtime)
    if 'string' in override:
        edited = decode_talents(override['string'], character, runtime)
    else:
        edited = [dict(e) for e in original]
        for change in override['nodes']:
            entries = nodes.get(change['nodeId'], [])
            target = next((t for t in entries if t['entryId'] == change['entryId']), None)
            if target is None:
                raise TalentEditError('TALENT_NODE_INVALID')
            tiered = target['nodeType'] == 1
            maximum = sum(t['maxRanks'] for t in entries) if tiered else target['maxRanks']
            if change['rank'] > maximum or (tiered and target != entries[0]):
                raise TalentEditError('TALENT_NODE_INVALID')
            edited = [e for e in edited if e['nodeID'] != change['nodeId']]
            remaining = change['rank']
            for entry in (entries if tiered else [target]):
                rank = min(remaining, entry['maxRanks']); remaining -= rank
                if rank:
                    edited.append({'nodeID': change['nodeId'], 'id': entry['entryId'], 'rank': rank})
    code = _encode(edited, character, spec_id, class_id)
    _validate_paths(edited, spec_id, nodes)
    changes = talent_difference({'loadout':original}, {'loadout':edited}, character, runtime)
    return {'string':code, 'loadout':edited, 'changes':changes,
            'validation':'versioned_tree_rules', 'catalogRevision':_catalog()[0]['revision']}

def talent_options(character, talents, runtime, query=''):
    catalog, spec_id, _, nodes = _context(character, runtime)
    selected = {e['id']: e['rank'] for e in _loadout(talents, character, runtime)}
    labels = _labels()
    if labels['revision'] != catalog['revision'] or labels['sourceSha256'] != catalog['sourceSha256']:
        raise TalentEditError('TALENT_CATALOG_RUNTIME_MISMATCH')
    localized = catalog_for_build(catalog['build'])
    spells = localized.data['spells'] if localized else {}
    output = []
    for node_id, entries in sorted(nodes.items()):
        options = []
        for t in entries:
            if any(t['specs']) and spec_id not in t['specs']: continue
            label = labels['entries'].get(str(t['entryId']), {})
            options.append({'entryId':t['entryId'], 'name':label.get('name'),
                            'nameZh':spells.get(str(label.get('spellId'))), 'spellId':label.get('spellId'),
                            'maxRanks':t['maxRanks'], 'selectedRank':selected.get(t['entryId'],0),
                            'tree':t['tree'], 'heroSubTreeId':t['subTreeId']})
        if options and (not query or any(query.casefold() in str(e).casefold() for e in options)):
            output.append({'nodeId':node_id, 'entries':options,
                           'nodeType':entries[0]['nodeType'],
                           'tieredEdit':({'entryId':entries[0]['entryId'],
                                          'maxRanks':sum(e['maxRanks'] for e in entries),
                                          'selectedRank':sum(selected.get(e['entryId'],0) for e in entries)}
                                         if entries[0]['nodeType'] == 1 else None)})
    return {'nodes':output, 'catalogRevision':catalog['revision'], 'gameBuild':catalog['build'],
            'limitations':[], 'supportsNodeReallocation': str(spec_id) in _paths()['specs']}

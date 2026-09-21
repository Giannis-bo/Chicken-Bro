"""Finite, pinned WeGame mappings. No fuzzy translation or silent field loss.

The collector schema alone does not attest a game version or quest choices.
Those absent facts remain blocking, including for the current real fixture.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from .domain import Issue, IssueSeverity

ENGINE_COMMIT = '7d6f530cbdab20389ff8bc6ba97a37ac27f74e41'
MOD_KINDS = ('implicitMods', 'explicitMods', 'enchantMods', 'runeMods', 'craftedMods',
             'fracturedMods', 'desecratedMods', 'mutatedMods', 'utilityMods', 'bondedMods')
SLOTS = {'Weapon', 'Offhand', 'Weapon2', 'Offhand2', 'Helm', 'BodyArmour', 'Gloves',
         'Boots', 'Amulet', 'Ring', 'Ring2', 'Belt'}
# Descriptions are display-only, except flavourText, which PoB can parse as mods.
DISPLAY_FIELDS = {'id', 'descrText', 'secDescrText', 'league', 'frameTypeId', 'rarity'}
ITEM_FIELDS = DISPLAY_FIELDS | set(MOD_KINDS) | {'name', 'typeLine', 'baseType', 'inventoryId',
    'frameType', 'ilvl', 'identified', 'properties', 'requirements', 'sockets', 'socketedItems',
    'corrupted', 'mirrored', 'sanctified', 'doubleCorrupted', 'fractured', 'desecrated', 'mutated'}
GEM_FIELDS = DISPLAY_FIELDS | {'name', 'typeLine', 'baseType', 'frameType', 'ilvl', 'identified',
    'properties', 'requirements', 'socketedItems', 'sockets', 'support', 'socket', 'corrupted',
    'gemSkill', 'gemSockets', 'gemTabs', 'inventoryId', 'supportGemRequirements', 'weaponRequirements'}


@dataclass(frozen=True)
class MappingResult:
    character: dict | None
    issues: tuple[Issue, ...]
    preview: dict
    mapping_version: str
    source_hash: str
    game_data_version: str
    coverage: dict
    ledger: tuple[dict, ...]


def load_dictionary():
    return json.loads(Path(__file__).with_name('data').joinpath('zhCN-0_5.json').read_text())


def _text(value):
    if not isinstance(value, str):
        return ''
    # Preserve the displayed disambiguator, never collapse Resistances to its key.
    return re.sub(r'\[([^\]|]+)\|([^\]]+)\]', r'\2', value).strip()


def _preview_values(snapshot, role, source):
    """Retain collector display facts without echoing private or structured input."""
    sensitive = re.compile(r'openid|role_?id|account|share|token|cookie|authorization|request|raw|url|secret|password|private', re.I)
    secrets = set()

    def scan(value, private=False, depth=0):
        if depth > 20:
            return
        if isinstance(value, str) and private and len(value) >= 4:
            secrets.add(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                scan(child, private or bool(sensitive.search(str(key))), depth + 1)
        elif isinstance(value, list):
            for child in value:
                scan(child, private, depth + 1)

    scan(snapshot)

    def clean(value):
        return isinstance(value, str) and not any(secret in value for secret in secrets)

    def label(value):
        if (not clean(value) or not 1 <= len(value) <= 100
                or not re.fullmatch(r"[\w .\-'\u00b7]+", value)
                or sensitive.search(value) or re.search(r'[a-fA-F0-9]{32,}', value)):
            return None
        return value.strip() or None

    def timestamp(value):
        if not clean(value) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        except (ValueError, OverflowError):
            return None

    preview = {'character': label(role.get('name')) or 'Imported character',
               'sourceUpdatedAt': timestamp(source.get('source_updated_at'))}
    league = label(role.get('league_id'))
    fetched = timestamp(source.get('fetched_at'))
    if league is not None:preview['league'] = league
    if fetched is not None:preview['fetchedAt'] = fetched
    return preview


def map_snapshot(snapshot: dict, dictionary: dict) -> MappingResult:
    issues, ledger = [], []
    coverage = {k: {'total': 0, 'mapped': 0, 'unmapped': 0}
                for k in ('items', 'modifiers', 'gems', 'nodes', 'attributes', 'quests')}

    def problem(code, path):
        issues.append(Issue(code, path, IssueSeverity.BLOCKING,
                            '来源字段缺失或尚无经过验证的映射，请补充完整 PoB。'))

    def record(kind, path, ok):
        coverage[kind]['total'] += 1
        coverage[kind]['mapped' if ok else 'unmapped'] += 1
        ledger.append({'kind': kind, 'path': path, 'status': 'mapped' if ok else 'unmapped'})

    def array(value, path):
        if isinstance(value, list):
            return value
        problem('SOURCE_STRUCTURE_UNSUPPORTED', path)
        return []

    if not isinstance(snapshot, dict):
        snapshot = {};problem('SOURCE_STRUCTURE_UNSUPPORTED', 'source')
    source = snapshot.get('source') if isinstance(snapshot.get('source'), dict) else {}
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    if dictionary.get('engine_commit') != ENGINE_COMMIT:
        problem('MAPPING_VERSION_UNSUPPORTED', 'mappingVersion')
    if snapshot.get('schema_version') != 1:
        problem('SOURCE_SCHEMA_UNSUPPORTED', 'source')
    if source.get('game_data_version') != dictionary['game_data_version']:
        problem('GAME_VERSION_UNSUPPORTED', 'source.gameDataVersion')
    if source.get('schema_gaps') or source.get('provider') != 'wegame':
        problem('SOURCE_SCHEMA_GAP', 'source')
    role = snapshot.get('role') if isinstance(snapshot.get('role'), dict) else {}
    class_name = dictionary['classes'].get(role.get('class_name')) if isinstance(role.get('class_name'), str) else None
    if not class_name:problem('CLASS_UNMAPPED', 'role.class')
    level = role.get('level')
    if type(level) is not int or not 1 <= level <= 100:
        problem('LEVEL_INVALID', 'role.level');level = None
    preview = {**_preview_values(snapshot, role, source), 'completeness': 'incomplete'}
    if level is not None:preview['level'] = level
    if class_name:preview['class'] = class_name

    def mods(item, output, domain, path):
        for kind in MOD_KINDS:
            values = array(item.get(kind, []), path + '.' + kind)
            output[kind] = []
            for index, raw in enumerate(values):
                p = f'{path}.{kind}[{index}]'
                before = len(issues)
                obj = raw if isinstance(raw, dict) else {'description': raw}
                flags = {k: obj[k] for k in ('crafted', 'fractured', 'mutated') if k in obj}
                if set(obj) - {'description', 'crafted', 'fractured', 'mutated'} or any(type(v) is not bool for v in flags.values()):
                    problem('MOD_FLAGS_UNSUPPORTED', p)
                if flags and kind != 'explicitMods':problem('MOD_FLAGS_UNSUPPORTED', p)
                text = _text(obj.get('description'));english = None
                for entry in dictionary['modifier_templates']:
                    match = re.fullmatch(entry['pattern'], text)
                    if match and domain in entry['domain'] and all(int(v) <= 10000 for v in match.groups()):
                        english = entry['english'].format(*match.groups());break
                if english is None or kind in ('utilityMods', 'bondedMods'):
                    problem('MOD_UNMAPPED', p)
                else:
                    output[kind].append({'description': english, **flags} if kind in ('explicitMods', 'implicitMods') else english)
                record('modifiers', p, len(issues) == before)

    def unmapped_socket_items(values, path):
        for index, item in enumerate(array(values, path)):
            item_path = path + f'[{index}]'
            problem('ITEM_SOCKETS_UNMAPPED', item_path)
            record('items', item_path, False)
            if isinstance(item, dict):
                mods(item, {}, None, item_path)
                unmapped_socket_items(item.get('socketedItems', []), item_path + '.socketedItems')

    equipment = []
    occupied = set()
    for index, item in enumerate(array(snapshot.get('equipment'), 'equipment')):
        path = f'equipment[{index}]';before = len(issues)
        if not isinstance(item, dict):
            problem('ITEM_UNMAPPED', path);record('items', path, False);continue
        if set(item) - ITEM_FIELDS:problem('ITEM_FIELDS_UNSUPPORTED', path)
        base = dictionary['bases'].get(item.get('baseType')) if isinstance(item.get('baseType'), str) else None
        if base is None:problem('BASE_UNMAPPED', path + '.baseType')
        slot = item.get('inventoryId')
        if not isinstance(slot, str) or slot not in SLOTS or slot in occupied:problem('SLOT_UNMAPPED', path + '.inventoryId')
        else:occupied.add(slot)
        if base and (not isinstance(slot, str) or slot not in ({'Weapon', 'Weapon2', 'Offhand', 'Offhand2'} if base['domain'] == 'weapon' else {'Ring', 'Ring2'})):
            problem('ITEM_DOMAIN_MISMATCH', path + '.inventoryId')
        rarity = item.get('frameType')
        if type(rarity) is not int or rarity not in (0, 1, 2):problem('UNIQUE_UNMAPPED' if rarity in (3, 9, 10, 14) else 'RARITY_UNMAPPED', path + '.frameType')
        if item.get('identified') is not True:problem('ITEM_UNIDENTIFIED', path)
        if item.get('sockets') or item.get('socketedItems'):problem('ITEM_SOCKETS_UNMAPPED', path)
        unmapped_socket_items(item.get('socketedItems', []), path + '.socketedItems')
        ilvl = item.get('ilvl')
        if type(ilvl) is not int or not 0 <= ilvl <= 100:problem('ITEM_LEVEL_INVALID', path);ilvl = 0
        out = {'name': 'Imported item' if rarity in (1, 2) else '', 'typeLine': base['name'] if base else '', 'inventoryId': slot,
               'frameType': rarity, 'ilvl': ilvl, 'id': f'mapped-item-{index}', 'properties': [], 'requirements': []}
        for flag in ('corrupted', 'mirrored', 'sanctified', 'doubleCorrupted', 'fractured', 'desecrated', 'mutated'):
            if flag in item:
                if type(item[flag]) is not bool:problem('ITEM_FLAGS_UNSUPPORTED', path)
                else:out[flag] = item[flag]
        for field in ('properties', 'requirements'):
            for pi, prop in enumerate(array(item.get(field, []), path + '.' + field)):
                p = f'{path}.{field}[{pi}]'
                if not isinstance(prop, dict):problem('PROPERTY_UNMAPPED', p);continue
                name = _text(prop.get('name'))
                translated = {'品质': 'Quality', '等级': 'Level'}.get(name)
                if translated is None:
                    problem('PROPERTY_UNMAPPED', p);continue
                values = prop.get('values')
                if not (isinstance(values, list) and len(values) == 1 and isinstance(values[0], list)
                        and values[0] and re.fullmatch(r'\+?\d+%?', str(values[0][0]))):
                    problem('PROPERTY_UNMAPPED', p);continue
                out[field].append({'name': translated, 'values': [[str(values[0][0]), 0]]})
        mods(item, out, base['domain'] if base else None, path)
        record('items', path, len(issues) == before);equipment.append(out)

    skills = snapshot.get('skills') if isinstance(snapshot.get('skills'), dict) else {}
    base_info = array(skills.get('base_info'), 'skills.baseInfo')
    if not base_info:problem('MISSING_BASE_INFO', 'skills.baseInfo')
    source_gems = {x.get('id'): x.get('name') for x in base_info if isinstance(x, dict) and isinstance(x.get('id'), str)}
    if len(source_gems) != len(base_info):problem('GEM_ID_UNVERIFIED', 'skills.baseInfo')

    expected_gem_ids = []

    def gem(raw, path, child=False):
        before = len(issues)
        if not isinstance(raw, dict):
            problem('GEM_UNMAPPED', path);record('gems', path, False);return {}
        if set(raw) - GEM_FIELDS:problem('GEM_FIELDS_UNSUPPORTED', path)
        entry = dictionary['gems'].get(raw.get('typeLine')) if isinstance(raw.get('typeLine'), str) else None
        if entry is None or raw.get('support') is not (entry or {}).get('support'):
            problem('GEM_UNMAPPED', path)
        elif not entry['support'] and source_gems.get(entry['source_id']) != raw.get('typeLine'):
            problem('GEM_ID_UNVERIFIED', path)
        if entry:expected_gem_ids.append(entry['id'])
        properties = []
        seen = set()
        for pi, prop in enumerate(array(raw.get('properties', []), path + '.properties')):
            if not isinstance(prop, dict):problem('GEM_PROPERTY_UNMAPPED', path);continue
            name = _text(prop.get('name'))
            if name in ('等级', '品质'):
                values = prop.get('values')
                match = re.fullmatch(r'\+?(\d+)(?:%|\(最高等级\))?', str(values[0][0])) if isinstance(values, list) and values and isinstance(values[0], list) and values[0] else None
                maximum = 40 if name == '等级' else 30
                if not match or not 0 <= int(match[1]) <= maximum or name in seen:
                    problem('GEM_PROPERTY_UNMAPPED', path + f'.properties[{pi}]')
                else:
                    seen.add(name);properties.append({'name': 'Level' if name == '等级' else 'Quality', 'values': [[match[1], 0]]})
            elif prop.get('values'):
                problem('GEM_PROPERTY_UNMAPPED', path + f'.properties[{pi}]')
        if entry and not entry['support'] and '等级' not in seen:problem('GEM_LEVEL_MISSING', path)
        if child and raw.get('socketedItems'):problem('GEM_STRUCTURE_UNSUPPORTED', path)
        out = {'typeLine': entry['name'] if entry else '', 'support': bool(entry and entry['support']), 'properties': properties}
        if 'corrupted' in raw:
            if type(raw['corrupted']) is not bool:problem('GEM_PROPERTY_UNMAPPED', path)
            else:out['corrupted'] = raw['corrupted']
        record('gems', path, len(issues) == before)
        out['socketedItems'] = [gem(g, path + f'.socketedItems[{i}]', True) for i, g in enumerate(array(raw.get('socketedItems', []), path + '.socketedItems'))]
        return out

    mapped_skills = [gem(g, f'skills.items[{i}]') for i, g in enumerate(array(skills.get('items'), 'skills.items'))]
    if not mapped_skills:problem('SKILLS_MISSING', 'skills.items')
    p = snapshot.get('passives') if isinstance(snapshot.get('passives'), dict) else {}
    if set(p) - {'hashes', 'specialisations', 'skill_overrides', 'jewel_slots', 'quest_stats', 'quest_provenance'}:
        problem('PASSIVE_FIELDS_UNSUPPORTED', 'passives')
    hashes = array(p.get('hashes'), 'passives.hashes')
    sets = p.get('specialisations') if isinstance(p.get('specialisations'), dict) else {}
    if set(sets) - {'set1', 'set2'}:problem('WEAPON_SET_UNMAPPED', 'passives.specialisations')
    mapped_sets = {key: array(sets.get(key, []), 'passives.specialisations.' + key) for key in ('set1', 'set2')}
    all_nodes = set()
    for path, nodes in [('passives.hashes', hashes)] + [('passives.specialisations.' + k, v) for k, v in mapped_sets.items()]:
        for index, node in enumerate(nodes):
            ok = type(node) is int and str(node) in dictionary['nodes'] and node not in all_nodes
            if not ok:problem('NODE_UNMAPPED', path + f'[{index}]')
            record('nodes', path + f'[{index}]', ok)
            if type(node) is int:all_nodes.add(node)
    overrides = p.get('skill_overrides') if isinstance(p.get('skill_overrides'), dict) else {}
    mapped_overrides = {}
    for index, (key, value) in enumerate(overrides.items()):
        path = f'passives.skillOverrides[{index}]';before = len(issues)
        entry = dictionary['attributes'].get(value.get('id')) if isinstance(value, dict) and isinstance(value.get('id'), str) else None
        node = dictionary['nodes'].get(key)
        if (not entry or not node or not node['attribute'] or not key.isdecimal()
                or int(key) not in all_nodes or value.get('name') != entry['name']
                or value.get(entry['field']) != 5 or not isinstance(value.get('stats'), list)
                or [_text(s) for s in value.get('stats', [])] != [entry['stat']]
                or set(value) - {'id', 'name', 'stats', entry['field']}):
            problem('ATTRIBUTE_UNMAPPED', path)
        else:mapped_overrides[key] = {'name': entry['english']}
        record('attributes', path, len(issues) == before)
    for node in all_nodes:
        if dictionary['nodes'].get(str(node), {}).get('attribute') and str(node) not in mapped_overrides:
            problem('ATTRIBUTE_CHOICE_MISSING', 'passives.skillOverrides')
    jewels = snapshot.get('jewels') if isinstance(snapshot.get('jewels'), dict) else {}
    if jewels.get('status') != 'present':problem('MISSING_JEWELS', 'jewels')
    elif not isinstance(jewels.get('items'), list):problem('JEWELS_UNMAPPED', 'jewels')
    if jewels.get('items') or p.get('jewel_slots'):problem('JEWELS_UNMAPPED', 'jewels')
    if isinstance(jewels.get('items'), list):
        for index, wrapper in enumerate(jewels['items']):
            path = f'jewels.items[{index}]'
            record('items', path, False)
            problem('JEWELS_UNMAPPED', path)
            jewel = wrapper.get('jewel') if isinstance(wrapper, dict) else None
            if not isinstance(jewel, dict):
                problem('JEWEL_STRUCTURE_UNSUPPORTED', path)
            # Collector keeps both direct item mods and WeGame mod_descriptions.
            # Record each source modifier once, including unsupported structures.
            for value, part in ((wrapper, path), (jewel, path + '.jewel')):
                if not isinstance(value, dict):continue
                mods(value, {}, None, part)
                unmapped_socket_items(value.get('socketedItems', []), part + '.socketedItems')
                for mi, raw in enumerate(array(value.get('mod_descriptions', []), part + '.modDescriptions')):
                    mod_path = part + f'.modDescriptions[{mi}]'
                    record('modifiers', mod_path, False)
                    problem('MOD_UNMAPPED', mod_path)
                    formats = raw.get('values_formats') if isinstance(raw, dict) else None
                    if (not isinstance(formats, list) or not formats
                            or any(not isinstance(f, dict) or not isinstance(f.get('des'), str) for f in formats)):
                        problem('JEWEL_STRUCTURE_UNSUPPORTED', mod_path)
    quest_stats = array(p.get('quest_stats'), 'passives.questStats')
    provenance = p.get('quest_provenance')
    choices = provenance.get('choices') if isinstance(provenance, dict) else None
    if not isinstance(choices, list) or provenance.get('complete') is not True:
        problem('QUEST_PROVENANCE_MISSING', 'passives.questStats');choices = []
    quest_lines = []
    for index, stat in enumerate(quest_stats):
        choice = choices[index] if index < len(choices) and isinstance(choices[index], str) else None
        entry = dictionary['quest_rewards'].get(choice)
        ok = bool(entry and _text(stat) == entry['chinese'])
        record('quests', f'passives.questStats[{index}]', ok)
        if ok:quest_lines.append(entry['english'])
        else:problem('QUEST_UNMAPPED', f'passives.questStats[{index}]')
    if len(choices) != len(quest_stats) or len(set(c for c in choices if isinstance(c, str))) != len(choices):
        problem('QUEST_UNMAPPED', 'passives.questStats')
    penalty = provenance.get('resistance_penalty') if isinstance(provenance, dict) else None
    if type(penalty) is not int or penalty not in (0, -10, -20, -30, -40, -50, -60):
        problem('RESISTANCE_PROGRESS_MISSING', 'passives.questStats')
    character = None
    if not issues:
        character = {'name': 'Imported character', 'class': class_name, 'level': level, 'league': 'Imported',
                     'equipment': equipment, 'skills': mapped_skills, 'jewels': [],
                     'passives': {'hashes': hashes, 'specialisations': mapped_sets, 'skill_overrides': mapped_overrides,
                                  'quest_stats': quest_lines, 'jewel_data': {}},
                     '_mapping': {'engine_commit': ENGINE_COMMIT, 'resistance_penalty': penalty,
                                  'expected_gems': coverage['gems']['mapped'], 'expected_gem_ids': expected_gem_ids}}
        preview['completeness'] = 'complete'
    return MappingResult(character, tuple(issues), preview, dictionary['mapping_version'], digest,
                         dictionary['game_data_version'], coverage, tuple(ledger))


def map(snapshot):
    """Unique worker callable; dictionary binding stays server-owned."""
    return map_snapshot(snapshot, load_dictionary())

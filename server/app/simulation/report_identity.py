"""Private, bounded identity sidecar. Never recalculate or flatten compound metrics."""
from collections import defaultdict
from html.parser import HTMLParser
import hashlib
import json
import re
from urllib.parse import urlsplit

from server.app.simulation.report import _number, _object, _percent, _rows, _text, select_report_actor


def _id(value):
    return value if type(value) is int and 0 < value < 2**31 else None


def report_digest(report):
    return hashlib.sha256(json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def npc_sources_from_html(html: str) -> dict[str, int]:
    """Read generated anchor metadata only; never fetch links or render HTML."""
    if not isinstance(html, str) or len(html) > 16 * 1024 * 1024:
        return {}

    class Npcs(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.current = None
            self.found = defaultdict(set)

        def handle_starttag(self, tag, attrs):
            if tag != 'a':
                return
            self.current = None
            try:
                url = urlsplit(dict(attrs).get('href', ''))
                match = re.fullmatch(r'/npc=(\d{1,10})', url.path)
                if url.scheme == 'https' and url.netloc in ('www.wowhead.com', 'wowhead.com', 'ptr.wowhead.com', 'beta.wowhead.com') and match:
                    npc = _id(int(match[1]))
                    if npc:
                        self.current = (npc, [])
            except ValueError:
                pass

        def handle_data(self, data):
            if self.current and sum(map(len, self.current[1])) + len(data) <= 160:
                self.current[1].append(data)

        def handle_endtag(self, tag):
            if tag == 'a' and self.current:
                npc, parts = self.current
                name = ''.join(parts).strip()
                if name and len(self.found) < 1024:
                    self.found[name].add(npc)
                self.current = None

    parser = Npcs()
    # SimC also embeds report sections in script templates. Parse only bounded,
    # literal NPC anchors, not the surrounding executable/template language.
    for match in re.finditer(r'<a\s+href="https://[^"<>\s]{1,180}/npc=\d{1,10}"[^<>]{0,160}>[^<>]{1,160}</a>', html):
        parser.feed(match[0])
    return {name: next(iter(ids)) for name, ids in parser.found.items() if len(ids) == 1}


def _descriptor(raw, token, source='', npcs=None, depth=0):
    raw = _object(raw)
    return {'token': token, 'spellId': _id(raw.get('id') or raw.get('spell')),
            'spellName': _text(raw.get('spell_name')), 'itemId': _id(raw.get('item_id')),
            'sourceToken': source, 'sourceNpcId': _id((npcs or {}).get(source)),
            'children': [_descriptor(child, _text(_object(child).get('name')), source, npcs, depth + 1)
                         for child in _rows(raw.get('children'))[:32]] if depth < 4 else []}


def extract_report_identity(data: dict, report: dict, npc_sources=None) -> dict:
    players = _object(data.get('sim')).get('players', [])
    actor = (_object(players[0]) if isinstance(players, list) and len(players) == 1
             else select_report_actor(players, _text(_object(report.get('actor')).get('name'))))
    abilities = []
    groups = [('', _rows(actor.get('stats')))]
    groups.extend((_text(pet), _rows(stats)) for pet, stats in list(_object(actor.get('stats_pets')).items())[:32])
    types = ('heal', 'absorb') if report.get('metric', {}).get('name') == 'hps' else ('damage',)
    for source, rows in groups:
        for raw in rows:
            raw = _object(raw)
            name = _text(raw.get('name')); amount = _number(raw.get('compound_amount'))
            if raw.get('type') in types and name and amount is not None and amount > 0:
                token = _text(f'{source}: {name}') if source else name
                abilities.append((amount, _descriptor(raw, token, source, npc_sources)))
    abilities.sort(key=lambda row: row[0], reverse=True)
    buffs = []
    for raw in _rows(actor.get('buffs')) + _rows(actor.get('buffs_constant')):
        raw = _object(raw); token = _text(raw.get('name'))
        if token and _percent(raw.get('uptime')) is not None:
            buffs.append(_descriptor(raw, token))
    result = {'schemaVersion': 1, 'reportSha256': report_digest(report), 'abilities': [row[1] for row in abilities[:256]], 'buffs': buffs[:256]}
    if not validate_report_identity(result, report):
        raise ValueError('SIMC_IDENTITY_INVALID')
    return result


def validate_report_identity(identity, report) -> bool:
    count = 0

    def descriptor(row, depth=0):
        nonlocal count
        count += 1
        if count > 8192 or depth > 4 or not isinstance(row, dict) or set(row) != {
            'token', 'spellId', 'spellName', 'itemId', 'sourceToken', 'sourceNpcId', 'children'
        }:
            return False
        return (all(isinstance(row[key], str) and len(row[key]) <= 160 for key in ('token', 'spellName', 'sourceToken'))
                and all(row[key] is None or _id(row[key]) is not None for key in ('spellId', 'itemId', 'sourceNpcId'))
                and isinstance(row['children'], list) and len(row['children']) <= 32
                and all(descriptor(child, depth + 1) for child in row['children']))

    if not isinstance(identity, dict) or set(identity) != {'schemaVersion', 'reportSha256', 'abilities', 'buffs'} or type(identity['schemaVersion']) is not int or identity['schemaVersion'] != 1:
        return False
    if identity['reportSha256'] != report_digest(report):
        return False
    for key in ('abilities', 'buffs'):
        rows = identity[key]; expected = report.get(key)
        if not isinstance(rows, list) or not isinstance(expected, list) or len(rows) != len(expected) or len(rows) > 256:
            return False
        if not all(descriptor(row) and row['token'] == original.get('name') for row, original in zip(rows, expected)):
            return False
    return True

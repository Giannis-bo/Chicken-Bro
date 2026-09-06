"""Bounded public projection of SimulationCraft's cloud JSON report.

Field mapping follows upstream engine/report/json/report_json.cpp and was checked
against managed 1210-01 JSON (report 3.0.0-alpha1). Raw diagnostics, paths, action
sequences, and arbitrary custom sections never become public report data.
"""
import json
import math
import re
from typing import Any

MAX_REPORT_BYTES = 8 * 1024 * 1024
_MAX_ROWS = 256
_CLASSES = ('Death Knight', 'Demon Hunter', 'Paladin', 'Warrior', 'Hunter', 'Rogue',
            'Priest', 'Shaman', 'Mage', 'Warlock', 'Monk', 'Druid', 'Evoker')
# These canonical paper-doll values are fractions in the installed engine's
# report_json.cpp. Haste/mastery may exceed 100%, so this is not _percent().
_PERCENT_ATTRIBUTES = frozenset({
    'crit_pct', 'haste_pct', 'mastery_pct', 'versatility_pct', 'avoidance_pct', 'leech_pct',
})
_PRIMARY_ATTRIBUTES = frozenset({'strength', 'agility', 'stamina', 'intellect'})
_STATS_ATTRIBUTES = _PERCENT_ATTRIBUTES | frozenset({
    'crit_rating', 'haste_rating', 'mastery_rating', 'versatility_rating', 'avoidance_rating',
    'leech_rating', 'speed_rating', 'spell_power', 'attack_power', 'armor', 'manareg_per_second',
})


class SimulationReportError(ValueError):
    def __init__(self, code: str = 'SIMC_REPORT_INVALID'):
        self.code = code
        super().__init__(code)


def _object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _rows(value: Any) -> list:
    return value[:_MAX_ROWS] if isinstance(value, list) else []


def _text(value: Any, limit: int = 160) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ''


def _number(value: Any, *, minimum: float = 0) -> float | None:
    if isinstance(value, dict):
        value = value.get('mean')
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise SimulationReportError() from None
    if not math.isfinite(number):
        raise SimulationReportError()
    return number if minimum <= number <= 1e18 else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _percent(value: Any, *, fraction: bool = False) -> float | None:
    number = _number(value)
    if number is not None:
        number *= 100 if fraction else 1
    return min(number, 100.0) if number is not None and number <= 100.000001 else None


def _reject_constant(value: str) -> None:
    raise SimulationReportError()


def _validate_tree(value: Any, depth: int = 0) -> None:
    if depth > 48:
        raise SimulationReportError()
    if isinstance(value, float) and not math.isfinite(value):
        raise SimulationReportError()
    if isinstance(value, dict):
        for item in value.values():
            _validate_tree(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _validate_tree(item, depth + 1)


def _crit_percent(stats: dict) -> float | None:
    total = crit = 0.0
    for group in ('direct_results', 'tick_results'):
        for name, outcome in _object(stats.get(group)).items():
            count = _number(_object(outcome).get('count'))
            if count is not None:
                total += count
                if name in ('crit', 'crit_block', 'glance_crit'):
                    crit += count
    return 100 * crit / total if total > 0 else None


def normalize_simc_report(payload: str | bytes, *, expected_actor: str) -> dict:
    if not isinstance(payload, (str, bytes)) or len(payload) > MAX_REPORT_BYTES:
        raise SimulationReportError()
    try:
        if isinstance(payload, str) and len(payload.encode('utf-8')) > MAX_REPORT_BYTES:
            raise SimulationReportError()
        data = json.loads(payload, parse_constant=_reject_constant)
        _validate_tree(data)
    except (ValueError, UnicodeError, RecursionError):
        raise SimulationReportError() from None
    data = _object(data)
    sim = _object(data.get('sim'))
    players = sim.get('players')
    if not isinstance(players, list) or len(players) != 1:
        raise SimulationReportError('SIMC_ACTOR_INVALID')
    actor = _object(players[0])
    name = _text(actor.get('name'))
    if not expected_actor or name.casefold() != expected_actor.strip().casefold() or name.casefold() in {'none', 'null', 'unknown', 'unnamed'}:
        raise SimulationReportError('SIMC_ACTOR_INVALID')
    for log in _rows(data.get('logs')):
        if _object(log).get('level') in ('error', 'fatal'):
            raise SimulationReportError('SIMC_FATAL_DIAGNOSTIC')
    cd = _object(actor.get('collected_data'))
    metric_name = 'hps' if actor.get('role') == 'heal' else 'dps'
    if metric_name not in cd and metric_name == 'dps' and 'hps' in cd:
        metric_name = 'hps'
    metric_data = _object(cd.get(metric_name))
    value = _number(metric_data.get('mean'))
    if value is None or value <= 0:
        raise SimulationReportError('SIMC_METRIC_INVALID')
    options = _object(sim.get('options'))
    deviation = _number(metric_data.get('mean_std_dev'))
    estimator = _number(options.get('confidence_estimator'))
    error = _number(deviation * estimator) if deviation is not None and estimator is not None else None
    specialization = _text(actor.get('specialization'))
    class_name = next((item for item in _CLASSES if specialization.endswith(' ' + item)), '')
    spec_name = specialization[:-(len(class_name) + 1)] if class_name else specialization
    dbc = _object(actor.get('dbc') or options.get('dbc'))
    game = _object(dbc.get(dbc.get('version_used', '')))
    version = _text(data.get('version'), 64)
    if not re.fullmatch(r'\d{3,6}-\d{1,4}(?:[A-Za-z0-9.-]{0,24})', version):
        version = None
    abilities = []
    # Top-level compound_amount already includes children; do not double count.
    ability_groups = [('' , _rows(actor.get('stats')))]
    ability_groups.extend((_text(pet), _rows(stats)) for pet, stats in list(_object(actor.get('stats_pets')).items())[:32])
    for pet, stats_rows in ability_groups:
        for raw in stats_rows:
            stats = _object(raw)
            if stats.get('type') not in (('heal', 'absorb') if metric_name == 'hps' else ('damage',)):
                continue
            amount = _number(stats.get('compound_amount'))
            label = _text(stats.get('name'))
            if amount is None or amount <= 0 or not label:
                continue
            abilities.append({'name': _text(f'{pet}: {label}') if pet else label, 'amount': amount,
                'portion': _percent(stats.get('portion_amount'), fraction=True),
                'executions': _number(stats.get('num_executes')), 'critPercent': _crit_percent(stats)})
    abilities.sort(key=lambda item: item['amount'], reverse=True)
    buffs = []
    for raw in _rows(actor.get('buffs')) + _rows(actor.get('buffs_constant')):
        # A constant classification does not guarantee a measured 100% uptime.
        # Keep only measured values; neither missing nor constant means zero.
        buff = _object(raw); uptime = _percent(buff.get('uptime')); label = _text(buff.get('name'))
        if label and uptime is not None:
            buffs.append({'name': label, 'uptime': uptime})
    gained = {}
    for raw in _rows(actor.get('gains')):
        for resource, raw_gain in list(_object(raw).items())[:32]:
            amount = _number(_object(raw_gain).get('actual'))
            if resource != 'name' and amount is not None:
                gained[resource] = gained.get(resource, 0) + amount
    lost = _object(cd.get('resource_lost'))
    resources = [{'name': _text(name), 'gained': _number(gained.get(name)), 'lost': _number(lost.get(name))}
                 for name in sorted(set(gained) | set(lost))[:32]]
    attributes = []
    for section in ('attribute', 'stats'):
        for attribute, raw in list(_object(_object(cd.get('buffed_stats')).get(section)).items())[:64]:
            allowed = _PRIMARY_ATTRIBUTES if section == 'attribute' else _STATS_ATTRIBUTES
            if attribute not in allowed:
                continue
            amount = _number(raw)
            if amount is not None and section == 'stats' and attribute in _PERCENT_ATTRIBUTES:
                amount = _number(amount * 100)
            if amount is not None:
                attributes.append({'name': _text(attribute), 'value': amount})
    gear = []
    for slot, raw in list(_object(actor.get('gear')).items())[:32]:
        item = _object(raw)
        match = re.search(r'(?:^|,)id=(\d+)(?:,|$)', _text(item.get('encoded_item'), 4096))
        item_id = int(match[1]) if match else _integer(item.get('id'))
        if item_id is not None and 0 < item_id < 2**31:
            item_level = _number(item.get('ilevel'))
            gear.append({'slot': _text(slot), 'itemId': item_id,
                         'itemLevel': item_level if item_level is not None and item_level <= 10000 else None})
    level = _integer(actor.get('level'))
    return {'schemaVersion': 1,
        'engine': {'version': version, 'gameVersion': _text(game.get('wow_version'), 64) or None,
                   'build': str(_integer(game.get('build_level'))) if _integer(game.get('build_level')) is not None else None},
        'actor': {'name': name, 'className': class_name, 'specialization': spec_name,
                  'level': level if level is not None and level <= 1000 else None,
                  'race': _text(actor.get('race')), 'talents': _text(actor.get('talents'), 1024) or None},
        'metric': {'name': metric_name, 'value': value, 'error': error},
        'statistics': {'iterations': _integer(metric_data.get('count')) or _integer(options.get('iterations')),
                       'fightLengthSeconds': _number(cd.get('fight_length')),
                       'elapsedSeconds': _number(_object(sim.get('statistics')).get('elapsed_time_seconds'))},
        'abilities': abilities[:_MAX_ROWS], 'buffs': buffs[:_MAX_ROWS], 'resources': resources,
        'attributes': attributes[:64], 'gear': gear}


def validate_simc_report(value: object) -> bool:
    """Validate the complete persisted public schema before any owner-scoped read."""
    def text(item: Any, maximum: int = 160) -> bool:
        return isinstance(item, str) and len(item) <= maximum

    def nullable_text(item: Any, maximum: int = 160) -> bool:
        return item is None or text(item, maximum)

    def number(item: Any, maximum: float = 1e18) -> bool:
        return type(item) in (int, float) and 0 <= item <= maximum and math.isfinite(item)

    def nullable_number(item: Any, maximum: float = 1e18) -> bool:
        return item is None or number(item, maximum)

    def nullable_integer(item: Any) -> bool:
        return item is None or (number(item) and float(item).is_integer())

    def record(item: Any, fields: dict) -> bool:
        return isinstance(item, dict) and set(item) == set(fields) and all(check(item[key]) for key, check in fields.items())

    def rows(item: Any, fields: dict, maximum: int = _MAX_ROWS) -> bool:
        return isinstance(item, list) and len(item) <= maximum and all(record(row, fields) for row in item)

    return record(value, {
        'schemaVersion': lambda item: type(item) is int and item == 1,
        'engine': lambda item: record(item, {
            'version': lambda item: nullable_text(item, 64), 'gameVersion': lambda item: nullable_text(item, 64),
            'build': lambda item: nullable_text(item, 64)}),
        'actor': lambda item: record(item, {
            'name': lambda item: text(item) and bool(item.strip()), 'className': text, 'specialization': text,
            'level': lambda item: nullable_integer(item) and (item is None or item <= 1000),
            'race': text, 'talents': lambda item: nullable_text(item, 1024)}),
        'metric': lambda item: record(item, {
            'name': lambda item: item in ('dps', 'hps'), 'value': lambda item: number(item) and item > 0,
            'error': nullable_number}),
        'statistics': lambda item: record(item, {
            'iterations': nullable_integer, 'fightLengthSeconds': nullable_number, 'elapsedSeconds': nullable_number}),
        'abilities': lambda item: rows(item, {
            'name': text, 'amount': number, 'portion': lambda item: nullable_number(item, 100),
            'executions': nullable_number, 'critPercent': lambda item: nullable_number(item, 100)}),
        'buffs': lambda item: rows(item, {'name': text, 'uptime': lambda item: number(item, 100)}),
        'resources': lambda item: rows(item, {'name': text, 'gained': nullable_number, 'lost': nullable_number}, 32),
        'attributes': lambda item: rows(item, {'name': text, 'value': number}, 64),
        'gear': lambda item: rows(item, {'slot': text, 'itemId': lambda item: type(item) is int and 0 < item < 2**31,
                                       'itemLevel': lambda item: nullable_number(item, 10000)}, 32),
    })

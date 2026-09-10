"""Bounded actor-only APL input. Never accept top-level SimC directives."""
import re
from collections.abc import Mapping

_TOKEN = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')
_ACTION = re.compile(r'[a-z][a-z0-9_]*(?:,[a-zA-Z0-9_.,=<>!&|+*%():?@^~-]+)?\Z')


def normalize_action_lists(value):
    def fail(): raise ValueError('ACTION_LISTS_INVALID')
    if not isinstance(value, Mapping) or not 1 <= len(value) <= 16 or 'default' not in value: fail()
    result = {}; total = 0; references = {}
    for name, actions in value.items():
        if not isinstance(name, str) or not _TOKEN.fullmatch(name): fail()
        if not isinstance(actions, list) or not 1 <= len(actions) <= 256: fail()
        result[name] = list(actions); references[name] = []
        for action in actions:
            if not isinstance(action, str) or len(action) > 1024 or not _ACTION.fullmatch(action): fail()
            # Do not hide control-flow jumps inside sequence actions.
            if re.search(r':(?:call_action_list|run_action_list|swap_action_list)(?:,|:|$)', action): fail()
            total += len(action)
            if action.split(',', 1)[0] in {'call_action_list', 'run_action_list', 'swap_action_list'}:
                match = re.search(r'(?:^|,)name=([a-z][a-z0-9_]*)(?:,|$)', action)
                if not match or match[1] not in value: fail()
                references[name].append(match[1])
    if sum(map(len, result.values())) > 256 or total > 16000: fail()
    visited = set()
    def visit(name, stack):
        if name in stack: fail()
        if name in visited: return
        for target in references[name]: visit(target, stack | {name})
        visited.add(name)
    for name in references: visit(name, set())
    return result


def compile_action_lists(lists):
    lines = []
    for name, actions in sorted(lists.items()):
        key = 'actions' if name == 'default' else 'actions.' + name
        lines.append(key + '=' + actions[0])
        lines.extend(key + '+=/' + action for action in actions[1:])
    return lines


def extract_action_evidence(payload, actor_name, profile_sha256):
    """Project only actual actor actions from the report's sampled iteration."""
    import json
    import math
    from server.app.simulation.report import select_report_actor, MAX_REPORT_BYTES
    def fail(): raise ValueError('SIMC_ACTION_EVIDENCE_MISSING')
    if not isinstance(payload, (str, bytes)) or len(payload) > MAX_REPORT_BYTES: fail()
    try:
        data = json.loads(payload)
        actor = select_report_actor(data['sim']['players'], actor_name)
        rows = actor['collected_data']['action_sequence']
        if not isinstance(rows, list) or not rows: fail()
        sample = []; last = -1.0
        for row in rows[:512]:
            time = row.get('time')
            if type(time) not in (int, float) or not math.isfinite(time) or time < last: fail()
            last = time
            if 'name' not in row: continue  # Wait entries are not casts.
            name = row['name']; spell_id = row.get('id')
            if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,120}', name): fail()
            if type(spell_id) is not int or not 0 <= spell_id < 2**31: fail()
            sample.append({'time':float(time), 'name':name, 'spellId':spell_id})
        if not sample: fail()
    except (KeyError, TypeError, AttributeError, ValueError, RecursionError):
        fail()
    return {'profileSha256':profile_sha256, 'sample':sample, 'truncated':len(rows)>512,
            'limitations':['Actions from one report-sampled iteration only; not all iterations. Times are combat-relative seconds. Equal timestamps do not establish order. The supplied APL is a priority list; verify the intended action window before attributing DPS differences to ordering.']}

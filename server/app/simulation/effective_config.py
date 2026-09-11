"""Check report identity against the compiled actor, before accepting v5 results."""
import json
import re
from server.app.simulation.talent_editor import decode_talents, TalentEditError

def verify_effective_config(compiled, report, raw_report=None):
    def fail(): raise ValueError('SIMC_EFFECTIVE_CONFIG_MISMATCH')
    if not isinstance(report,dict): fail()
    expected={}; expected_talents=None
    for line in compiled.profile.splitlines():
        if line.startswith('talents='): expected_talents=line.split('=',1)[1]
        match=re.fullmatch(r'([a-z0-9_]+)=,id=(\d+)(.*)',line)
        if match:
            level=re.search(r'(?:^|,)ilevel=(\d+)(?:,|$)',match[3])
            expected[match[1]]=(int(match[2]),int(level[1]) if level else None)
    rows=report.get('gear',[])
    if not isinstance(rows,list): fail()
    observed={r.get('slot'):r for r in rows if isinstance(r,dict)}
    if len(observed)!=len(rows): fail()
    # Report uses SimC slot tokens; canonical snapshot historically uses singular.
    for slot,(item_id,level) in expected.items():
        item=observed.get(slot) or observed.get({'shoulder':'shoulders','wrist':'wrists'}.get(slot,''))
        if not item or item.get('itemId')!=item_id or (level is not None and item.get('itemLevel')!=level): fail()
    actual=report.get('actor',{}).get('talents')
    if not expected_talents or not actual: fail()
    if expected_talents != actual:
        character={'classKey':compiled.class_key,'specKey':compiled.spec_key,
                   'level':int(next(x.split('=',1)[1] for x in compiled.profile.splitlines() if x.startswith('level=')))}
        try:
            canonical=lambda code:sorted((e['nodeID'],e['id'],e['rank']) for e in decode_talents(code,character,compiled.runtime_revision))
            if canonical(expected_talents)!=canonical(actual): fail()
        except TalentEditError: fail()
    proof = {'status':'verified','profileSha256':compiled.profile_sha256,
             'checked':['talents','equipmentItemIds','overriddenItemLevels']}
    if 'food' in compiled.scenario:
        from server.app.simulation.report import select_report_actor, MAX_REPORT_BYTES
        if not isinstance(raw_report, (str, bytes)) or len(raw_report) > MAX_REPORT_BYTES: fail()
        try:
            actor = select_report_actor(json.loads(raw_report)['sim']['players'], compiled.actor_name)
            if actor.get('food') != compiled.scenario['food']: fail()
        except (KeyError, TypeError, AttributeError, ValueError, RecursionError):
            fail()
        proof['checked'].append('foodInputIdentity')
        proof['food'] = actor['food']
    overrides = compiled.scenario.get('equipmentOverrides', {})
    if not overrides:
        return proof
    if raw_report is None:
        # Legacy callers without changed enchants retain their existing proof.
        if any(item.get('enchant') is not None for item in overrides.values()): fail()
        return proof
    from server.app.simulation.report import select_report_actor, MAX_REPORT_BYTES
    if not isinstance(raw_report, (str, bytes)) or len(raw_report) > MAX_REPORT_BYTES: fail()
    try:
        actor = select_report_actor(json.loads(raw_report)['sim']['players'], compiled.actor_name)
        gear = actor['gear']
        if not isinstance(gear, dict) or len(gear) > 32: fail()
        observed_enchants = {}
        for slot, item in overrides.items():
            raw = gear.get(slot) or gear.get({'shoulder':'shoulders','wrist':'wrists'}.get(slot, ''))
            encoded = raw.get('encoded_item') if isinstance(raw, dict) else None
            if not isinstance(encoded, str) or not 0 < len(encoded) <= 4096: fail()
            fields = [part.split('=', 1) for part in encoded.split(',') if '=' in part]
            ids = [v for k, v in fields if k == 'id']
            enchants = [v for k, v in fields if k == 'enchant_id']
            named = [v for k, v in fields if k == 'enchant']
            if ids != [str(item['itemId'])] or len(enchants) > 1 or any(v != 'none' for v in named): fail()
            if enchants and (not enchants[0].isdigit() or not 0 <= int(enchants[0]) < 2**31): fail()
            actual = int(enchants[0]) or None if enchants else None
            if actual != item['enchant']: fail()
            observed_enchants[slot] = actual
    except (KeyError, TypeError, AttributeError, ValueError, RecursionError):
        fail()
    proof['checked'].append('overriddenEnchantIds')
    proof['overriddenEnchants'] = observed_enchants
    # encoded_item describes engine-reported inputs, not a mechanics audit.
    proof['enchantEvidenceScope'] = 'engine_reported_input_identity'
    return proof

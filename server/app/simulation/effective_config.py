"""Check report identity against the compiled actor, before accepting v5 results."""
import re
from server.app.simulation.talent_editor import decode_talents, TalentEditError

def verify_effective_config(compiled, report):
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
    return {'status':'verified','profileSha256':compiled.profile_sha256,
            'checked':['talents','equipmentItemIds','overriddenItemLevels']}

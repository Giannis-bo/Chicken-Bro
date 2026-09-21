"""Read presentation metadata from the exact saved result export, including old jobs."""
import xml.etree.ElementTree as ET
from server.app.poe2.engine import decode_build


def skill_setup(code):
    if not isinstance(code, str):
        return None
    try:
        root = ET.fromstring(decode_build(code))
    except (ValueError, ET.ParseError):
        return None
    skills = root.find('Skills')
    if skills is None:
        return None
    sets = skills.findall('SkillSet')
    selected = next((s for s in sets if s.get('id') == skills.get('activeSkillSet')), None)
    if sets and selected is None:
        return None
    groups = (selected if selected is not None else skills).findall('Skill')
    result = []
    for index, group in enumerate(groups, 1):
        gems = []
        for gem in group.findall('Gem'):
            name = gem.get('nameSpec', '').strip()
            if not name or gem.get('enabled') == 'false':
                continue
            gem_id = gem.get('gemId', '').rsplit('/', 1)[-1]
            kind = 'support' if gem_id.startswith('SupportGem') else 'skill' if gem_id.startswith('SkillGem') else 'unknown'
            try:
                level = int(gem.get('level', '1'))
            except ValueError:
                level = 1
            gems.append({'name': name, 'level': level, 'kind': kind})
        if not gems or not (group.get('enabled') == 'true' or group.get('active') == 'true'):
            continue
        source = group.get('source', '')
        result.append({'index': index, 'gems': gems, 'slot': group.get('slot', ''),
                       'source': 'tree' if source.startswith('Tree:') else 'item' if source.startswith('Item:') else 'generated' if source else 'configured'})
    return result

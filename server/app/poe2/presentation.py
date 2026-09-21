"""Small source-verified display glossary; never rewrites PoB calculation inputs."""
import json
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET


@lru_cache(maxsize=1)
def glossary():
    return json.loads((Path(__file__).resolve().parents[3] / 'packages/domain/src/poe2-terms.zh-CN.json').read_text())


def build_skills(xml):
    # Stored XML has already passed decode_build's size/entity/format validation.
    root = ET.fromstring(xml)
    skills = root.find('Skills')
    if skills is None: return []
    groups = skills.findall('Skill')
    for skill_set in skills.findall('SkillSet'):
        if skill_set.get('id') == skills.get('activeSkillSet', '1'):
            groups = skill_set.findall('Skill')
            break
    return [dict(group.attrib) | {'index': index, 'gems': [dict(gem.attrib) | {'name': gem.get('nameSpec', '')}
             for gem in group.findall('Gem')]} for index, group in enumerate(groups, 1)]


def presentation(packet, *, skills=None):
    data = glossary()
    found = set()
    def collect(value):
        if isinstance(value, dict):
            for key, kind in [('className', 'class'), ('ascendancy', 'ascendancy')]:
                if value.get(key): found.add((kind, value[key]))
            for gem in value.get('gems', []):
                if gem.get('name'): found.add(('gem', gem['name']))
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(packet)
    collect(skills or [])
    entries = {(term['kind'], term['en']): term for term in data['terms']}
    known = [entries[key] for key in sorted(found) if key in entries]
    unknown = [{'kind': kind, 'en': name, 'status': '国服名称待核实'} for kind, name in sorted(found) if (kind, name) not in entries]
    result = {'locale': 'zh-CN', 'version': data['version'], 'gameVersion': data['gameVersion'],
              'sources': data['sources'], 'terms': known, 'unknown': unknown,
              'instruction': '默认使用已核实国服简体名称，保留等级及罗马阶级；unknown 先查国服来源，仍缺则标记待核实并保留原文定位。'}
    if skills is not None: result['skills'] = skills
    return result

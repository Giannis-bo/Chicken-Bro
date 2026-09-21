"""Cloud-only: build presentation catalogue from saved PoE2DB cn/us 4.5 JSON.

Inputs are explicit files; this script does not fetch or execute source content.
Usage: python script.py us.json cn.json output.json
"""
import hashlib
import html
import json
from pathlib import Path
import re
import sys


def clean(text):
    text = html.unescape(re.sub(r'<[^>]+>', '', text))
    text = re.sub(r'\[([^\]|]+)(?:\|([^\]]+))?\]', lambda m: m[2] or m[1], text)
    return re.sub(r'\s+', ' ', text).strip()


def signature(text):
    tags = set(re.findall(r'\[([^\]|]+)(?:\|[^\]]+)?\]', text))
    tags = {'Hit' if tag == 'HitDamage' else tag for tag in tags}
    return sorted(tags), sorted(re.findall(r'\d+(?:\.\d+)?', text))


def main():
    en_path, cn_path, output = map(Path, sys.argv[1:])
    en, cn = [json.loads(p.read_text())['nodes'] for p in (en_path, cn_path)]
    names, stats = {}, {}
    reordered = 0
    for key, node in en.items():
        translated = cn[key]
        names[clean(node.get('name', ''))] = clean(translated.get('name', ''))
        left, right = node.get('stats', []), translated.get('stats', [])
        if len(left) != len(right):
            continue
        for i, effect in enumerate(left):
            matches = [j for j, target in enumerate(right) if signature(effect) == signature(target)]
            # The source has five reordered pairs. Disambiguate by machine
            # keyword IDs and numbers before pairing; equally tagged effects
            # keep the source order (reviewed in the verification report).
            j = matches[0] if len(matches) == 1 else i
            reordered += int(i != j)
            stats[clean(effect).lower()] = clean(right[j])
    data = {'source': 'https://poe2db.tw/data/passive-skill-tree/4.5/data_{us,cn}.json',
            'retrievedAt': '2026-09-21',
            'sourceSha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (en_path, cn_path)},
            'reorderedEffects': reordered, 'names': names, 'stats': stats}
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'names': len(names), 'stats': len(stats), 'reorderedEffects': reordered}))


if __name__ == '__main__': main()

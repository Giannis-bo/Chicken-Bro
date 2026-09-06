"""Build an offline catalog from already downloaded, hash-pinned DB2 CSVs.

No network access. Usage: python -m scripts.build_simc_localization_catalog SOURCE OUTPUT
"""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

from server.app.simulation.localization import BUILD_PATTERN, LocalizationCatalog, alias_token


def build_catalog(source: Path, output: Path):
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    build = manifest['build']
    if not BUILD_PATTERN.fullmatch(build):
        raise ValueError('invalid build')
    evidence = []

    def read(table, locale, field):
        records = [entry for entry in manifest['sources'] if entry['table'] == table and entry['locale'] == locale]
        if len(records) != 1:
            raise ValueError('source missing or duplicated')
        entry = records[0]
        path = source / f'{table}.{locale}.csv'
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('source too large')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (entry['sha256'] != digest or f'{table}.{build}.csv' not in entry['contentDisposition']
                or entry['url'] != f'https://wago.tools/db2/{table}/csv?build={build}&locale={locale}'):
            raise ValueError('source provenance mismatch')
        evidence.append({key: entry[key] for key in ('table', 'locale', 'url', 'sha256', 'contentDisposition')})
        result = {}
        with path.open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                key = row['ID']; name = row[field].strip()
                if not key.isdigit() or not 0 < int(key) < 2**31 or key in result:
                    raise ValueError('invalid or duplicated identity')
                result[key] = name
        return result

    def localized(rows):
        return {key: name for key, name in rows.items() if 0 < len(name) <= 160 and re.search('[\u3400-\u9fff]', name)}

    def aliases(english, chinese):
        candidates = {}
        for key, name in english.items():
            token = alias_token(name)
            if token and len(token) <= 160:
                # An untranslated candidate also prevents an unjustified alias match.
                candidates.setdefault(token, set()).add(chinese.get(key))
        return {key: next(iter(names)) if len(names) == 1 else None for key, names in candidates.items()}

    spells = localized(read('SpellName', 'zhCN', 'Name_lang'))
    english_spells = read('SpellName', 'enUS', 'Name_lang')
    spell_aliases = aliases(english_spells, spells)
    creatures = localized(read('Creature', 'zhCN', 'Name_lang'))
    creature_aliases = aliases(read('Creature', 'enUS', 'Name_lang'), creatures)
    items = localized(read('ItemSparse', 'zhCN', 'Display_lang'))
    data = {'schemaVersion': 1, 'build': build, 'locale': 'zhCN', 'spells': spells,
            'creatures': creatures, 'items': items, 'spellAliases': spell_aliases, 'creatureAliases': creature_aliases}
    data['spellTokens'] = {key: alias_token(name) for key, name in english_spells.items() if key in spells and len(alias_token(name)) <= 160}
    rules_path = output / 'engine-rules.json'
    if rules_path.exists():
        if rules_path.stat().st_size > 65536:
            raise ValueError('rules too large')
        data['engineRules'] = json.loads(rules_path.read_text(encoding='utf-8'))
        if data['engineRules'].get('build') != build:
            raise ValueError('rules build mismatch')
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    packed = gzip.compress(raw, mtime=0)
    digest = hashlib.sha256(packed).hexdigest()
    LocalizationCatalog(data, digest)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'catalog.json.gz').write_bytes(packed)
    result = {'schemaVersion': 1, 'build': build, 'locale': 'zhCN', 'sha256': digest,
              'retrievedAt': manifest.get('retrievedAt'), 'sources': evidence,
              'counts': {key: len(data[key]) for key in ('spells', 'creatures', 'items')},
              'ambiguousOrUntranslatedAliases': sum(value is None for value in spell_aliases.values())}
    if rules_path.exists():
        result['engineRulesSha256'] = hashlib.sha256(rules_path.read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(build_catalog(Path(sys.argv[1]), Path(sys.argv[2])), ensure_ascii=False))

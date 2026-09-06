"""Offline, build-exact zhCN names shared by every client and specialization."""
import gzip
import hashlib
import io
import json
import re
import zlib
from functools import lru_cache
from pathlib import Path

from server.app.simulation.report_identity import validate_report_identity

BUILD_PATTERN = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,8}')


def alias_token(name):
    # Match SimulationCraft util::tokenize: no fuzzy search or suffix stripping.
    return re.sub(r'[^a-z0-9_]', '', str(name).lower().replace(' ', '_'))


class LocalizationCatalog:
    def __init__(self, data: dict, revision: str):
        if (not isinstance(data, dict) or data.get('schemaVersion') != 1 or data.get('locale') != 'zhCN'
                or not isinstance(data.get('build'), str) or not BUILD_PATTERN.fullmatch(data['build'])
                or not re.fullmatch('[a-f0-9]{64}', revision)):
            raise ValueError('SIMC_CATALOG_INVALID')
        for key in ('spells', 'creatures', 'items', 'spellAliases', 'creatureAliases'):
            rows = data.get(key)
            if not isinstance(rows, dict) or len(rows) > 1000000:
                raise ValueError('SIMC_CATALOG_INVALID')
            for token, text in rows.items():
                if not isinstance(token, str) or len(token) > 160 or (text is not None and (
                    not isinstance(text, str) or len(text) > 160 or not re.search('[\u3400-\u9fff]', text))):
                    raise ValueError('SIMC_CATALOG_INVALID')
        self.data = data
        self.revision = revision
        tokens = data.get('spellTokens', {})
        if not isinstance(tokens, dict) or len(tokens) > 1000000 or not all(isinstance(key, str) and key.isdigit() and isinstance(token, str) and len(token) <= 160 for key, token in tokens.items()):
            raise ValueError('SIMC_CATALOG_INVALID')
        rules = data.get('engineRules')
        if rules is not None:
            if not isinstance(rules, dict) or rules.get('build') != data['build'] or not re.fullmatch('[a-f0-9]{40}', str(rules.get('sourceCommit'))):
                raise ValueError('SIMC_CATALOG_INVALID')
            for key in ('syntheticAbilities', 'legacyAliases'):
                if not isinstance(rules.get(key), dict) or len(rules[key]) > 512:
                    raise ValueError('SIMC_CATALOG_INVALID')
            for token, rule in rules['syntheticAbilities'].items():
                if not isinstance(token, str) or len(token) > 160 or not isinstance(rule, dict) or not isinstance(rule.get('text'), str) or not re.search('[\u3400-\u9fff]', rule['text']) or len(rule['text']) > 160 or not isinstance(rule.get('allowedIds'), list) or not all(x is None or type(x) is int and 0 < x < 2**31 for x in rule['allowedIds']):
                    raise ValueError('SIMC_CATALOG_INVALID')
            if not all(isinstance(key, str) and len(key) <= 160 and isinstance(value, str) and len(value) <= 160 and re.search('[\u3400-\u9fff]', value) for key, value in rules['legacyAliases'].items()):
                raise ValueError('SIMC_CATALOG_INVALID')

    @classmethod
    def load(cls, root: Path, build: str):
        if not isinstance(build, str) or not BUILD_PATTERN.fullmatch(build):
            raise ValueError('SIMC_CATALOG_INVALID')
        try:
            manifest_path = root / 'manifest.json'
            if manifest_path.stat().st_size > 65536:
                raise ValueError('SIMC_CATALOG_INVALID')
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if not isinstance(manifest, dict):
                raise ValueError('SIMC_CATALOG_INVALID')
            path = root / 'catalog.json.gz'
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('SIMC_CATALOG_INVALID')
            packed = path.read_bytes()
            digest = hashlib.sha256(packed).hexdigest()
            if manifest.get('build') != build or manifest.get('locale') != 'zhCN' or manifest.get('sha256') != digest:
                raise ValueError('SIMC_CATALOG_INVALID')
            with gzip.GzipFile(fileobj=io.BytesIO(packed)) as stream:
                raw = stream.read(96 * 1024 * 1024 + 1)
            if len(raw) > 96 * 1024 * 1024:
                raise ValueError('SIMC_CATALOG_INVALID')
            catalog = cls(json.loads(raw), digest)
            if catalog.data['build'] != build:
                raise ValueError('SIMC_CATALOG_INVALID')
            return catalog
        except (OSError, EOFError, KeyError, TypeError, RecursionError, zlib.error) as error:
            raise ValueError('SIMC_CATALOG_INVALID') from error


@lru_cache(maxsize=4)
def catalog_for_build(build: str):
    if not isinstance(build, str) or not BUILD_PATTERN.fullmatch(build):
        return None
    try:
        return LocalizationCatalog.load(Path(__file__).parent / 'data' / 'localization' / build, build)
    except ValueError:
        return None


def localize_report(report: dict, identity: dict | None, catalog: LocalizationCatalog | None, *, engine_revision: str = '') -> dict:
    if identity is not None and not validate_report_identity(identity, report):
        raise ValueError('SIMC_IDENTITY_INVALID')
    build = report.get('engine', {}).get('gameVersion')
    available = catalog is not None and catalog.data['build'] == build
    data = catalog.data if available else {}
    rules = data.get('engineRules', {})
    runtime = re.fullmatch(r'simc:[^:\s]{1,32}:([a-f0-9]{40}):[a-f0-9]{64}', engine_revision)
    if not runtime or runtime[1] != rules.get('sourceCommit'):
        rules = {}

    def label(row, descriptor, kind, index):
        spell_id = descriptor['spellId'] if descriptor else None
        source_id = descriptor['sourceNpcId'] if descriptor else None
        source = descriptor['sourceToken'] if descriptor else ''
        token = row['name'][len(source) + 2:] if source else row['name']
        text = None; method = 'unresolved'; status = 'unresolved'
        if available:
            synthetic = rules.get('syntheticAbilities', {}).get(token) if kind == '技能' else None
            legacy_key = row['name'].strip().lower().replace(' ', '_')
            legacy = rules.get('legacyAliases', {}).get(legacy_key) if descriptor is None else None
            if synthetic and descriptor and spell_id in synthetic['allowedIds']:
                text = synthetic['text']; method = 'engine_rule'; status = 'resolved'
                # The private sidecar retains this engine marker; it is not a game ID.
                spell_id = None
            elif legacy:
                text = legacy; method = 'engine_rule'; status = 'legacy'
            elif spell_id:
                text = data['spells'].get(str(spell_id))
                if text:
                    method = 'spell_id'; status = 'resolved'
            else:
                aliases = data['spellAliases']; key = alias_token(token)
                text = aliases.get(key)
                if text:
                    method = 'exact_name'; status = 'resolved' if descriptor else 'legacy'
                elif key in aliases:
                    status = 'ambiguous'
        if not text:
            text = f'{kind}名称未匹配（编号 {spell_id}）' if spell_id else f'{kind}名称未匹配（条目 {index + 1}）'
        elif rules and spell_id and kind == '增益':
            base = data.get('spellTokens', {}).get(str(spell_id))
            # Exact engine suffix + same spell's English token; never strip an
            # arbitrary suffix to find another spell or infer a missing identity.
            qualifiers = {'crit': '爆击', 'critical_strike': '爆击', 'haste': '急速',
                          'mastery': '精通', 'vers': '全能', 'versatility': '全能',
                          'penalty_vers': '全能降低'}
            for suffix, qualifier in qualifiers.items():
                if base and token.lower() == f'{base}_{suffix}':
                    text += f'（{qualifier}）'
                    break
        if source:
            source_name = (data.get('creatures', {}).get(str(source_id)) if source_id else
                           data.get('creatureAliases', {}).get(alias_token(source)))
            if source_name:
                text = f'{source_name}：{text}'
            else:
                text = f'召唤物名称未匹配{f"（编号 {source_id}）" if source_id else ""}：{text}'
                if status == 'resolved':
                    status = 'partial'
        return {'text': text[:320], 'status': status, 'spellId': spell_id,
                'sourceNpcId': source_id, 'method': method}

    result = {'locale': 'zhCN', 'gameVersion': build,
              'catalogRevision': catalog.revision if available else None, 'status': 'complete'}
    for key, kind in (('abilities', '技能'), ('buffs', '增益')):
        result[key] = [label(row, identity[key][index] if identity else None, kind, index)
                       for index, row in enumerate(report[key])]
    statuses = {row['status'] for key in ('abilities', 'buffs') for row in result[key]}
    result['status'] = ('unavailable' if not available else 'legacy' if identity is None else
                        'partial' if statuses - {'resolved'} else 'complete')
    return result

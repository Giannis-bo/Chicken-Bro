"""Bounded data-only inputs and isolated calls to the pinned cloud PoB engine."""

import base64
from contextlib import contextmanager
import fcntl
import binascii
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zlib
from urllib.parse import urlencode


MAX_SOURCE_BYTES = 2_000_000
CONFIG_KEYS = frozenset({
    'enemyLevel', 'enemyIsBoss', 'enemyPhysicalReduction', 'enemyFireResist',
    'enemyColdResist', 'enemyLightningResist', 'enemyChaosResist',
    'conditionEnemyShocked', 'conditionEnemyChilled', 'conditionEnemyIgnited',
    'conditionFullLife', 'conditionLowLife', 'conditionStationary',
    'usePowerCharges', 'useFrenzyCharges', 'useEnduranceCharges',
})
ITEM_SLOTS = frozenset({'Weapon 1', 'Weapon 2', 'Helmet', 'Body Armour', 'Gloves',
                        'Boots', 'Amulet', 'Ring 1', 'Ring 2', 'Belt'})


@contextmanager
def engine_slot():
    path = os.environ.get('POE2_ENGINE_LOCK', '/tmp/chickenbro-poe2-engine.lock')
    with open(path, 'a') as handle:
        deadline = time.monotonic() + 10
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('POE2_ENGINE_BUSY') from None
                time.sleep(0.1)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def decode_build(source: str) -> str:
    if not isinstance(source, str) or not source.strip() or len(source.encode()) > MAX_SOURCE_BYTES:
        raise ValueError('POE2_BUILD_INPUT_INVALID')
    source = source.strip()
    if source.startswith('<'):
        xml = source
    else:
        try:
            packed = base64.b64decode(source + '=' * (-len(source) % 4), altchars=b'-_', validate=True)
            decoder = zlib.decompressobj()
            data = decoder.decompress(packed, MAX_SOURCE_BYTES + 1)
            if len(data) > MAX_SOURCE_BYTES or not decoder.eof or decoder.unused_data:
                raise ValueError('POE2_BUILD_EXPANSION_INVALID')
            xml = data.decode('utf-8')
        except (ValueError, UnicodeError, zlib.error, binascii.Error) as exc:
            raise ValueError('POE2_BUILD_INPUT_INVALID') from exc
    if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('POE2_BUILD_XML_UNSAFE')
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError('POE2_BUILD_XML_INVALID') from exc
    if root.tag != 'PathOfBuilding2' or root.find('Build') is None:
        raise ValueError('POE2_BUILD_FORMAT_INVALID')
    return xml


def validate_changes(changes: dict | None) -> dict:
    if changes is None:
        return {}
    if not isinstance(changes, dict) or set(changes) - {'level', 'mainSocketGroup', 'skillGroups', 'items', 'config', 'allocateNodes', 'deallocateNodes'}:
        raise ValueError('POE2_CHANGES_INVALID')
    for key, maximum in [('level', 100), ('mainSocketGroup', 100)]:
        if key in changes and (type(changes[key]) is not int or not 1 <= changes[key] <= maximum):
            raise ValueError('POE2_CHANGES_INVALID')
    if 'skillGroups' in changes:
        groups = changes['skillGroups']
        if not isinstance(groups, list) or not 1 <= len(groups) <= 10:
            raise ValueError('POE2_SKILLS_INVALID')
        seen = set()
        for group in groups:
            if (not isinstance(group, dict) or set(group) != {'index', 'gems'}
                    or type(group['index']) is not int or not 1 <= group['index'] <= 100
                    or group['index'] in seen or not isinstance(group['gems'], list)
                    or not 1 <= len(group['gems']) <= 6):
                raise ValueError('POE2_SKILLS_INVALID')
            seen.add(group['index'])
            for gem in group['gems']:
                if (not isinstance(gem, dict) or set(gem) != {'name', 'level', 'quality'}
                        or not isinstance(gem['name'], str) or not 1 <= len(gem['name']) <= 100
                        or type(gem['level']) is not int or not 1 <= gem['level'] <= 40
                        or type(gem['quality']) is not int or not 0 <= gem['quality'] <= 30):
                    raise ValueError('POE2_SKILLS_INVALID')
    if 'config' in changes:
        config = changes['config']
        if not isinstance(config, dict) or set(config) - CONFIG_KEYS:
            raise ValueError('POE2_CONFIG_UNSUPPORTED')
        for key, value in config.items():
            if key == 'enemyIsBoss':
                if value not in ('None', 'Boss', 'Pinnacle'):
                    raise ValueError('POE2_CONFIG_INVALID')
            elif key.startswith(('condition', 'use')):
                if type(value) is not bool:
                    raise ValueError('POE2_CONFIG_INVALID')
            elif type(value) not in (int, float) or not -200 <= value <= 1000:
                raise ValueError('POE2_CONFIG_INVALID')
    if 'items' in changes:
        items = changes['items']
        if not isinstance(items, list) or len(items) > 10:
            raise ValueError('POE2_ITEMS_INVALID')
        seen = set()
        for item in items:
            if (not isinstance(item, dict) or set(item) != {'slot', 'text'}
                    or item['slot'] not in ITEM_SLOTS or item['slot'] in seen
                    or not isinstance(item['text'], str) or not 1 <= len(item['text']) <= 16000):
                raise ValueError('POE2_ITEMS_INVALID')
            seen.add(item['slot'])
    for key in ('allocateNodes', 'deallocateNodes'):
        if key in changes:
            nodes = changes[key]
            if (not isinstance(nodes, list) or len(nodes) > 30 or
                    any(type(node) is not int or not 0 <= node <= 1000000 for node in nodes)
                    or len(set(nodes)) != len(nodes)):
                raise ValueError('POE2_NODES_INVALID')
    return changes


def crafting_import_link(item_text: str) -> str:
    if not isinstance(item_text, str) or not 1 <= len(item_text.strip()) <= 16000:
        raise ValueError('POE2_ITEM_INPUT_INVALID')
    return 'https://beta.craftofexile.com/?' + urlencode({'game': 'poe2', 'eimport': item_text})


class PobEngine:
    def __init__(self, root: str | None = None, lua: str | None = None):
        self.root = Path(root or os.environ.get('POE2_POB_ROOT', '/nonexistent/poe2')).resolve()
        self.lua = lua or os.environ.get('POE2_LUAJIT', '/nonexistent/luajit')

    def tree(self, source: str) -> dict:
        return self.calculate(source, view_tree=True)

    def calculate(self, source: str, changes: dict | None = None, *, view_tree: bool = False) -> dict:
        xml = decode_build(source)
        changes = validate_changes(changes)
        if not (self.root / 'src' / 'HeadlessWrapper.lua').is_file() or not Path(self.lua).is_file():
            raise RuntimeError('POE2_ENGINE_UNAVAILABLE')
        with tempfile.TemporaryDirectory(prefix='poe2-job-') as directory:
            payload = Path(directory) / 'input.json'
            output = Path(directory) / 'output.json'
            payload.write_text(json.dumps({'xml': xml, 'changes': changes, 'viewTree': view_tree}), encoding='utf-8')
            env = {key: value for key, value in os.environ.items() if key in
                   {'PATH', 'LD_LIBRARY_PATH', 'LUA_PATH', 'LUA_CPATH', 'LANG'}}
            env.update({'HOME': directory, 'POE2_INPUT': str(payload), 'POE2_OUTPUT': str(output)})
            for key in ('LD_LIBRARY_PATH', 'LUA_PATH', 'LUA_CPATH'):
                if os.environ.get('POE2_' + key):
                    env[key] = os.environ['POE2_' + key]
            command = ['/usr/bin/prlimit', '--as=1073741824', '--cpu=40', '--nofile=128', '--',
                       sys.executable, str(Path(__file__).with_name('engine_runner.py')),
                       self.lua, str(Path(__file__).with_name('bridge.lua'))]
            try:
                with engine_slot():
                    result = subprocess.run(command, cwd=self.root / 'src', env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        timeout=45, check=False)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('POE2_ENGINE_TIMEOUT') from exc
            if result.returncode != 0 or not output.is_file() or output.stat().st_size > 4_000_000:
                raise RuntimeError('POE2_ENGINE_FAILED')
            response = json.loads(output.read_text())
        if not isinstance(response, dict) or response.get('error'):
            raise ValueError(str(response.get('error', 'POE2_ENGINE_INVALID_RESULT'))[:200])
        response['inputSha256'] = hashlib.sha256(xml.encode()).hexdigest()
        if view_tree:
            response['engineVersion'] = os.environ.get('POE2_ENGINE_VERSION', 'unverified')
            return response
        export_xml = response.pop('exportXml', '')
        decode_build(export_xml)
        response['exportCode'] = base64.urlsafe_b64encode(zlib.compress(export_xml.encode())).decode()
        response['outputSha256'] = hashlib.sha256(export_xml.encode()).hexdigest()
        response['changes'] = changes
        response['engineVersion'] = os.environ.get('POE2_ENGINE_VERSION', 'unverified')
        return response

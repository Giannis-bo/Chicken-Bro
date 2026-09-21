"""Cloud-only real player tree and independent XML allocation comparison."""
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from server.app.poe2.engine import PobEngine, decode_build

ROOT = Path('/opt/chickenbro-candidates/poe2-20260918')


def main():
    pob = ROOT / 'upstream/pob'
    runtime = ROOT / 'runtime/root'
    os.environ.update(POE2_POB_ROOT=str(pob), POE2_LUAJIT=str(runtime / 'usr/bin/luajit'),
        POE2_ENGINE_VERSION='v0.23.1@7d6f530cbdab20389ff8bc6ba97a37ac27f74e41',
        LD_LIBRARY_PATH=str(runtime / 'usr/lib/x86_64-linux-gnu'),
        LUA_CPATH=str(runtime / 'usr/lib/x86_64-linux-gnu/lua/5.1/?.so') + ';;',
        LUA_PATH=str(pob / 'runtime/lua/?.lua') + ';' + str(pob / 'runtime/lua/?/init.lua') + ';;')
    code = (ROOT / 'evidence/link-research/user-ninja-code-20260920.txt').read_text().strip()
    engine = PobEngine()
    tree = engine.tree(code)
    result = engine.calculate(code)
    allocated = sorted(node['id'] for node in tree['nodes'] if node['allocated'])
    assert allocated == result['allocatedNodes']
    xml = ET.fromstring(decode_build(result['exportCode']))
    specs = xml.find('Tree')
    spec = specs.findall('Spec')[int(specs.get('activeSpec', '1')) - 1]
    expected = {int(n) for n in spec.get('nodes', '').split(',') if n}
    assert expected <= set(allocated)
    for mode in (1, 2):
        element = spec.find('WeaponSet' + str(mode))
        expected_mode = {int(n) for n in element.get('nodes', '').split(',') if n} if element is not None else set()
        actual = {n['id'] for n in tree['nodes'] if n['allocated'] and n['allocation'] == mode}
        assert actual == expected_mode, (mode, len(actual), len(expected_mode))
    assert tree['ascendancy'] == 'Gemling Legionnaire'
    asc = [n for n in tree['nodes'] if n['allocated'] and n['ascendancy'] == tree['ascendancy']]
    assert len(asc) >= 8
    assert len(tree['nodes']) > 4000 and len(tree['edges']) > 4000
    assert all(isinstance(n['stats'], list) for n in tree['nodes'])
    out = ROOT / 'evidence/passive-tree'
    (out / 'tree-private.json').write_text(json.dumps(tree))
    (out / 'tree-private.json').chmod(0o600)
    report = dict(passed=True, nodes=len(tree['nodes']), edges=len(tree['edges']), allocated=len(allocated), ascendancyAllocated=len(asc),
                  independentExportXmlMatched=True, weaponGroupsMatched=True, allocatedNodesMatched=True,
                  engineVersion=tree['engineVersion'], treeVersion=tree['treeVersion'])
    (out / 'engine.json').write_text(json.dumps(report, indent=2)); print(json.dumps(report))


if __name__ == '__main__': main()

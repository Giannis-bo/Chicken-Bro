"""Build offline catalogs from authorized, versioned source downloads. No network or SimC execution."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def build_trees(source, destination, engine):
    specs = {}
    known = {t['entryId']: t for t in engine[1]}
    for path in sorted(source.glob('tree-*.json')):
        if path.name == 'tree-collection.json': continue
        raw = path.read_bytes(); data = json.loads(raw)
        sid = data['loadout']['spec']['id']; cid = data['loadout']['class']['id']
        if str(sid) != path.stem.split('-')[-1]: raise ValueError('tree spec mismatch')
        nodes = {}
        for node in data['specNodes']:
            entries = []
            for entry in node['entries']:
                trait = known.get(entry['id'])
                if trait is None: continue  # Provider can expose inactive/unsupported entries.
                if (trait['nodeId'] != node['id'] or trait['maxRanks'] != entry['maxRanks']
                        or trait['nodeType'] != node['type'] or trait['classId'] != cid):
                    raise ValueError('engine/provider trait mismatch')
                entries.append(entry['id'])
            if entries:
                nodes[str(node['id'])] = {'children':node['childrenNodeIds'], 'entries':entries}
        specs[str(sid)] = {'classId':cid, 'nodes':nodes, 'sourceRawSha256':hashlib.sha256(raw).hexdigest()}
    output = {'schemaVersion':1, 'revision':engine[0]['revision'], 'build':engine[0]['build'],
              'engineSourceSha256':engine[0]['sourceSha256'], 'providerVersion':'12.1.0',
              'sourceEndpoint':'https://raider.io/api/spec-loadout/parse', 'specs':specs}
    destination.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')


def build_items(root, destination, engine):
    items={}
    for line in (root/'item_data.inc').read_text().splitlines():
     m=re.match(r'\s*\{ "([^"\\]*)", (.*)',line)
     if not m:continue
     f=[x.strip() for x in m[2].split(',')]
     try:
      if int(f[9])==12 and int(f[5])==90 and int(f[4])==219:
       items[f[0]]={'name':m[1],'baseItemLevel':int(f[4]),'requiredLevel':90,'inventoryType':12,'classMask':int(f[18],0)}
     except (ValueError,IndexError):pass
    bonuses={}
    for line in (root/'item_bonus.inc').read_text().splitlines():
     m=re.fullmatch(r'\s*\{\s*([\d,\s-]+)\s*\},',line)
     if m:
      v=[int(x) for x in m[1].split(',')];bonuses.setdefault(str(v[1]),[]).append(v[2:7])
    configs={}
    s=(root/'item_scaling.inc').read_text().split('__item_scaling_config_data { {')[1].split('} };')[0]
    for m in re.finditer(r'\{\s*([\d,\s]+)\}',s):
     v=[int(x) for x in m[1].split(',')];configs[v[0]]=v[2]
    upgrades={}
    for bid,rows in bonuses.items():
     if {r[0] for r in rows} <= {3,7,34,49} and any(r[0]==34 for r in rows):
      cfg=[r[1] for r in rows if r[0]==49]
      if len(cfg)==1 and 250<=configs.get(cfg[0],0)<=400:
       upgrades[bid]={'itemLevel':configs[cfg[0]],'upgradeIds':next(r[1:3] for r in rows if r[0]==34),'rank':next((r[1] for r in rows if r[0]==7),None)}
    output={'schemaVersion':1,'revision':engine[0]['revision'],'build':engine[0]['build'],'scope':'Level-90 base-219 trinkets; same verified upgrade bonus as source','sourceSha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['item_data.inc','item_bonus.inc','item_scaling.inc']},'items':items,'upgrades':upgrades}
    destination.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n')

if __name__ == '__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from server.app.simulation.wcl_talents import _catalog
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    parser.add_argument('--items', action='store_true')
    args=parser.parse_args()
    (build_items if args.items else build_trees)(args.source,args.destination,_catalog())

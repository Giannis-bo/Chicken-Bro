"""Regenerate engine-bound metadata from the pinned official source; no SimC execution."""
import hashlib,json,re,sys,csv
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.simc.build_experiment_catalogs import build_items
root=Path(sys.argv[1]);out=Path('server/app/simulation/data');revision='76f8118cf3f7f41dad20708e8328e1f4ab2deebc';build='12.1.5.70391'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n')
raw=(root/'trait_data.inc').read_text();assert raw.startswith('// Player trait definitions, wow build '+build)
section=raw.split('} };')[0]
rows=[json.loads(l.strip().rstrip(',').replace('{','[').replace('}',']')) for l in section.splitlines()[2:] if l.strip().startswith('{')]
assert len(rows)==int(re.search(r'trait_data_t, (\d+)',section)[1])
old=json.loads((out/'traits-12.1.0.json').read_text());newrows=[[r[i] for i in [0,1,2,3,4,10,11,14,15,16,17]] for r in rows]
# The existing provider graph is reusable only if all engine ordering, nodes,
# ranks, geometry, specializations and selectors are unchanged.
assert [[v for i,v in enumerate(r) if i not in (5,6,8)] for r in old['rows']]==[[v for i,v in enumerate(r) if i not in (5,6,8)] for r in newrows]
specs={}
for name,sid in re.findall(r'([A-Z_]+)\s*=\s*(\d+)',(root/'sc_specialization_data.inc').read_text()):
 if sid in old['specializations']:
  key=re.sub(r'^(DEATH_KNIGHT|DEMON_HUNTER|[A-Z]+)_','',name).lower();specs[sid]=key
assert specs==old['specializations']
traits={**old,'revision':revision,'build':build,'sourceSha256':sha(root/'trait_data.inc'),'rows':newrows,'specializationsSourceSha256':sha(root/'sc_specialization_data.inc')}
labels={k:traits[k] for k in ['revision','build','sourcePath','sourceSha256']}
labels['entries']={str(r[2]):{'name':r[13],'spellId':r[7],'requiredPoints':r[5]} for r in rows}
paths=json.loads((out/'trait-paths-12.1.0.json').read_text());paths.update(revision=revision,build=build,engineSourceSha256=traits['sourceSha256'])
proof=Path('/var/lib/chickenbro-simc-update-20261016/graph-proof')
manifest=json.loads((proof/'manifest.json').read_text())
assert [e['build'] for e in manifest]==['12.1.0.69933',build]
def edges(version):
 p=proof/(version+'.csv');e=next(e for e in manifest if e['build']==version)
 assert sha(p)==e['sha256'] and f'TraitEdge.{version}.csv' in e['contentDisposition']
 return {(int(r['LeftTraitNodeID']),int(r['RightTraitNodeID'])) for r in csv.DictReader(p.open()) if r['Type']=='2'}
old_edges=edges('12.1.0.69933');new_edges=edges(build);graph_changes=[]
for sid,spec in paths['specs'].items():
 g=spec['nodes'];node_ids={int(n) for n in g}
 before={(a,b) for a,b in old_edges if a in node_ids and b in node_ids}
 after={(a,b) for a,b in new_edges if a in node_ids and b in node_ids}
 if before==after:continue
 current={(int(n),c) for n,v in g.items() for c in v['children'] if c in node_ids}
 assert current==before, 'provider graph does not match exact old-build DB2'
 for parent,node in g.items():
  node['children']=[c for c in node['children'] if (int(parent),c) not in before-after]
 for a,b in sorted(after-before):
  assert b not in g[str(a)]['children'];g[str(a)]['children'].append(b)
 assert {(int(n),c) for n,v in g.items() for c in v['children'] if c in node_ids}==after
 graph_changes.append({'specId':sid,'removed':sorted(before-after),'added':sorted(after-before)})
assert [c['specId'] for c in graph_changes]==['1480']
paths['exactBuildEdgePatch']={'source':'wago.tools/db2/TraitEdge','build':build,'sources':manifest,'changes':graph_changes}
geometry=[{'entryId':a[2],'before':a[5:7],'after':b[5:7]} for a,b in zip(old['rows'],newrows) if a[5:7]!=b[5:7]]
assert len(geometry)==9 and all(1480 in a[7] for a,b in zip(old['rows'],newrows) if a[5:7]!=b[5:7])
Path('/var/lib/chickenbro-simc-update-20261016/catalog-diff.json').write_text(json.dumps({'geometryChanges':geometry,'graphChanges':graph_changes},indent=2))
write(out/'traits-12.1.0.json',traits);write(out/'trait-labels-12.1.0.json',labels);write(out/'trait-paths-12.1.0.json',paths)
engine=(traits,[dict(zip(traits['columns'],r)) for r in newrows]);build_items(root,out/'item-variants-12.1.0.json',engine)
print(json.dumps({'revision':revision,'build':build,'traits':len(rows),'changedStarterRows':sum(a[8]!=b[8] for a,b in zip(old['rows'],newrows)),'providerGraphStructuralCompatibility':'exact_db2_patch_verified','files':{p.name:sha(p) for p in out.glob('*.json')}}))

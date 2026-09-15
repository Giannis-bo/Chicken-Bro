"""Regenerate engine-bound metadata from the pinned official source; no SimC execution."""
import hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from scripts.simc.build_experiment_catalogs import build_items
root=Path(sys.argv[1]);out=Path('server/app/simulation/data');revision='ac0f3a3c7ff9e521137c0ca1760d548330c697f3';build='12.1.0.69814'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n')
raw=(root/'trait_data.inc').read_text();assert raw.startswith('// Player trait definitions, wow build '+build)
section=raw.split('} };')[0]
rows=[json.loads(l.strip().rstrip(',').replace('{','[').replace('}',']')) for l in section.splitlines()[2:] if l.strip().startswith('{')]
assert len(rows)==int(re.search(r'trait_data_t, (\d+)',section)[1])
old=json.loads((out/'traits-12.1.0.json').read_text());newrows=[[r[i] for i in [0,1,2,3,4,10,11,14,15,16,17]] for r in rows]
# The existing provider graph is reusable only if all engine ordering, nodes,
# ranks, geometry, specializations and selectors are unchanged.
assert [[v for i,v in enumerate(r) if i!=8] for r in old['rows']]==[[v for i,v in enumerate(r) if i!=8] for r in newrows]
specs={}
for name,sid in re.findall(r'([A-Z_]+)\s*=\s*(\d+)',(root/'sc_specialization_data.inc').read_text()):
 if sid in old['specializations']:
  key=re.sub(r'^(DEATH_KNIGHT|DEMON_HUNTER|[A-Z]+)_','',name).lower();specs[sid]=key
assert specs==old['specializations']
traits={**old,'revision':revision,'build':build,'sourceSha256':sha(root/'trait_data.inc'),'rows':newrows,'specializationsSourceSha256':sha(root/'sc_specialization_data.inc')}
labels={k:traits[k] for k in ['revision','build','sourcePath','sourceSha256']}
labels['entries']={str(r[2]):{'name':r[13],'spellId':r[7],'requiredPoints':r[5]} for r in rows}
paths=json.loads((out/'trait-paths-12.1.0.json').read_text());paths.update(revision=revision,build=build,engineSourceSha256=traits['sourceSha256'])
write(out/'traits-12.1.0.json',traits);write(out/'trait-labels-12.1.0.json',labels);write(out/'trait-paths-12.1.0.json',paths)
engine=(traits,[dict(zip(traits['columns'],r)) for r in newrows]);build_items(root,out/'item-variants-12.1.0.json',engine)
print(json.dumps({'revision':revision,'build':build,'traits':len(rows),'changedStarterRows':sum(a[8]!=b[8] for a,b in zip(old['rows'],newrows)),'providerGraphStructuralCompatibility':'passed','files':{p.name:sha(p) for p in out.glob('*.json')}}))

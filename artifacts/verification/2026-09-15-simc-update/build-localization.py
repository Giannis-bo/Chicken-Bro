from pathlib import Path
import sys,json
sys.path.insert(0,'/opt/chickenbro')
from scripts.build_simc_localization_catalog import build_catalog
root=Path('/var/lib/chickenbro-simc-update-20260915');out=root/'localization/12.1.0.69814';out.mkdir(parents=True,exist_ok=True)
rules=json.loads(Path('/opt/chickenbro/server/app/simulation/data/localization/12.1.0.69299/engine-rules.json').read_text())
rules.update(sourceCommit='ac0f3a3c7ff9e521137c0ca1760d548330c697f3',build='12.1.0.69814')
# These fixed display labels name existing engine actions; spell/item labels are
# independently rebuilt from the new build's exact localized DB2 tables.
(out/'engine-rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(build_catalog(root/'localization-source',out),ensure_ascii=False))

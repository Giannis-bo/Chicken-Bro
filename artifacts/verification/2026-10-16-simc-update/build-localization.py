from pathlib import Path
import sys,json
sys.path.insert(0,'/opt/chickenbro')
from scripts.build_simc_localization_catalog import build_catalog
root=Path('/var/lib/chickenbro-simc-update-20261016');out=root/'localization/12.1.5.70391';out.mkdir(parents=True,exist_ok=True)
rules=json.loads(Path('/opt/chickenbro/server/app/simulation/data/localization/12.1.0.69933/engine-rules.json').read_text())
rules.update(sourceCommit='76f8118cf3f7f41dad20708e8328e1f4ab2deebc',build='12.1.5.70391')
# These fixed display labels name existing engine actions; spell/item labels are
# independently rebuilt from the new build's exact localized DB2 tables.
(out/'engine-rules.json').write_text(json.dumps(rules,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(build_catalog(root/'localization-source',out),ensure_ascii=False))

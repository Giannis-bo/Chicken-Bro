"""Adapt the reviewed, private cloud smoke for this bounded release only."""
from pathlib import Path

root = Path('/var/lib/chickenbro-skills-release-20260912')
p = root / 'smoke.py'
s = Path('/var/lib/chickenbro-generalization-release-20260911/smoke.py').read_text()
s = s.replace("p.add_argument('--remaining',action='store_true');a=p.parse_args()", "p.add_argument('--remaining',action='store_true');p.add_argument('--label',required=True);a=p.parse_args()")
s = s.replace('chickenbro-generalization-candidate-20260911','chickenbro-skills-candidate-20260912')
s = s.replace("(a.mode+('-remaining' if a.remaining else '')+'-private.json')", "(a.label+'-private.json')")
s = s.replace("key=str(uuid4());mid=str(uuid4())", "key=str(uuid4());mid=str(uuid4());before_dirs=set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'));started=time.monotonic()")
s = s.replace("record={'runId':str(row[0])", "native=[]\n        for f in set(Path(env['WOW_CODEX_JOBS_DIR']).glob('*/native-tool-observations.jsonl'))-before_dirs:\n            identity=f.parent/'run-identity.json'\n            if identity.is_file() and json.loads(identity.read_text()).get('runId')==str(row[0]):\n                native.extend(json.loads(line) for line in f.read_text().splitlines() if line.strip())\n        record={'observationBinding':'exact_run_id','elapsedSeconds':round(time.monotonic()-started,3),'nativeObservations':native,'runId':str(row[0])")
s = s.replace("['simple-class-question','query-simulation-help','refuse-top100','misleading-empty-success','misleading-causation']", "['simple-class-question','query-simulation-help','refuse-top100']")
start = s.index("        cid=create('generalization:window-evidence')")
end = s.index('        # Read a real previously completed cloud result', start)
s = s[:start] + '''        for case_id,prompt in [
            ('wcl-skill','只分析下面已提供的日志摘要，不查外部：同一治疗角色，窗口A为0到10秒，溢出4点；窗口B为10到20秒，溢出9点。缺少逐目标血量和施法事件。比较两段，并判断能否建议少按某技能。不要运行模拟。'),
            ('rankings-skill','只研究这个已给出的有限榜单样本，不联网：同专精三名玩家甲、乙、丙，暴击分别30%、32%、31%，但装备等级和天赋不同。分析共同点、能否据此建议我的角色堆暴击、下一步最小验证是什么。不要提交模拟。'),
            ('mechanics-skill','下面是虚构的魔兽技能资料审阅练习，不联网：资料A明确是旧赛季，描述持续10秒；资料B是当前赛季攻略，称持续15秒但没给原始技能链接。玩家用同一俗称称呼它。请判断能否确认当前效果，说明消歧和取证应如何完成；不要编造真实技能身份。'),
            ('simc-skill','审核这份已给出的SimC实验是否能证明换宝石提升5%：基线DPS100000，候选105000；角色相同但snapshotId不同，引擎版本不同，基线单目标候选三目标，误差未知。只审核实验并给出最小纠正方案，不查询外部、不创建新模拟。')]:
            record=ask(create('skills:'+case_id),prompt);record['caseId']=case_id
''' + s[end:]
# In live smoke add a workflow task with supplied evidence; ordinary result read remains unchanged.
needle="record['caseId']='live-capability-boundary'"
s=s.replace(needle,needle+"\n        record=ask(create('skills:live-analysis'),'只根据已给日志事实分析，不联网：治疗过量40%，缺少目标血量、后续承伤与施法轴。能否认定浪费并建议换技能？说明判断依据，不模拟。');record['caseId']='live-wcl-skill'")
p.write_text(s)

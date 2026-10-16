"""Cloud-only QQ source validation; no QQ sends or model invocations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from server.app.channels.qq_official.battle_source import BattleSource
from server.app.channels.qq_official.battle_commands import parse_battle,format_battle


def credentials():
    pid=subprocess.check_output(['systemctl','show','chickenbro-qq-official.service',
                                 '--property=MainPID','--value'],text=True).strip()
    for item in Path('/proc/'+pid+'/environ').read_bytes().split(b'\0'):
        if item.startswith(b'WOW_WARCRAFTLOGS_'):
            key,value=item.decode().split('=',1);os.environ[key]=value


if __name__=='__main__':
    credentials()
    results=[]
    links=[('key_first','https://www.warcraftlogs.com/reports/kNBvnCLXjqPQZhdg?fight=1'),
           ('key_last','https://cn.warcraftlogs.com/reports/kNBvnCLXjqPQZhdg/#type=damage-done&fight=last&source=all'),
           ('raid_kill','https://www.warcraftlogs.com/reports/mZBg8DbyNdTrXcFL?type=summary&fight=3'),
           ('raid_wipe','https://www.warcraftlogs.com/reports/QqrT6Nkg7jRBWCMH#fight=49&type=damage-done'),
           ('raid_no_deaths','https://www.warcraftlogs.com/reports/QqrT6Nkg7jRBWCMH?fight=51')]
    if len(sys.argv)>1:links=[entry for entry in links if entry[0] in sys.argv[1:]]
    for name,url in links:
        before=time.monotonic()
        packet=BattleSource().query(parse_battle('/战斗分析 '+url))
        texts={kind:format_battle(packet,kind) for kind in ('battle_summary','battle_good','battle_review')}
        results.append({'name':name,'inputUrl':url,'seconds':round(time.monotonic()-before,2),'packet':packet,'messages':texts})
        print(json.dumps({'name':name,'status':packet.get('status'),'fightId':packet.get('fightId'),
                          'type':packet.get('battleType'),'coverage':packet.get('causalCoverage'),
                          'calls':packet.get('sourceCalls'),'seconds':results[-1]['seconds'],
                          'detailCounts':{k:len(packet.get(k,[])) for k in ('good','review')},
                          'lengths':{k:len(v) for k,v in texts.items()}},ensure_ascii=False),flush=True)
        if name in ('key_first','key_last'):print(json.dumps(texts,ensure_ascii=False),flush=True)
        assert packet['status']=='ready'
        assert packet['localizationLocale']=='zhCN'
        assert packet['reportVersion']=='team-report-v5'
        assert all(t in texts['battle_summary'] for t in ('整场结论','队伍表现'))
        assert '贡献结论' in texts['battle_good']
        if packet['causes']:
            n=len(packet['review'])
            assert texts['battle_review'].count('过程证据：')==n
            assert texts['battle_review'].count('战斗影响：')==n
            if name=='key_last':
                assert all(t in texts['battle_good'] for t in ('中断施法','驱散','主要技能','关键窗口'))
                assert '中断施法' in texts['battle_summary']
        previous=json.loads(Path('/var/lib/chickenbro/qq-official/battle-mplus-links-probe-1121653.json').read_text())
        original=next(r['packet'] for r in previous['results'] if r['name']==name)
        assert all(packet[k]==original[k] for k in ('reportCode','fightId','duration','playerCount'))
        assert [(d['actorId'],d['timestamp']) for d in packet['deaths']]==[(d['actorId'],d['timestamp']) for d in original['deaths']]
        joined='\n'.join(texts.values())
        if name=='key_first':
            assert all(t in joined for t in ('密谋小径','破坏魔惩罚者','绝命凶径','Giannis'))
            assert not any(t in joined for t in ('Lithiel Cinderfury','Xathuux the Annihilator','Shivan Punisher','Murder in a Row'))
        if name=='raid_kill':
            assert not any(t in joined for t in ('Falling Debris','Volatile Purge','Gore Rattle'))
            assert all(t in joined for t in ('落石','易爆清除','分摊后恢复'))
        limit=2 if name.startswith('key_') else 3
        assert all(len(v)<=1200 for v in texts.values())
        assert all(len(packet[k])<=limit for k in ('good','review'))
        if name.startswith('key_'):
            assert packet['battleType']=='mythic_plus' and packet['fight']['keystoneLevel']==12
            assert all('大秘境+12' in t and '已完成' in t for t in texts.values())
            assert packet['fightId']==(1 if name=='key_first' else 2)
        if name=='raid_kill':assert len(packet['causes'])==6
        if name=='raid_no_deaths':assert not packet['review']
    out=Path('/var/lib/chickenbro/qq-official/battle-team-report-probe-'+str(os.getpid())+'.json')
    out.write_text(json.dumps({'qqMessagesSent':0,'modelCalls':0,'root':os.getcwd(),'results':results},ensure_ascii=False,indent=2))
    print('evidence='+str(out),flush=True)

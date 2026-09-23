#!/usr/bin/env bash
# Run as root on the selected cloud host, after pulling the pinned image.
# Creates only the isolated NapCat environment. No Chat/DB mutations.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run as root'; exit 1; }
task_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$task_dir/image-lock.json")
[[ "$image" =~ ^mlikiowa/napcat-docker@sha256:[a-f0-9]{64}$ ]] || exit 1
docker image inspect "$image" >/dev/null
for target in /opt/chickenbro-qq-channel /var/lib/chickenbro-qq-channel /etc/chickenbro-qq-channel; do
  [[ ! -e "$target" ]] || { echo "Already exists: $target; inspect instead of overwriting"; exit 1; }
done
! docker container inspect chickenbro-napcat >/dev/null 2>&1 || { echo 'Container already exists'; exit 1; }
! docker network inspect chickenbro-qq-channel >/dev/null 2>&1 || { echo 'Network already exists'; exit 1; }
! getent passwd chickenbro-qq >/dev/null || { echo 'Service user already exists'; exit 1; }
python3 - <<'PY'
import socket
for port in (16099, 13001):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', port))
PY
useradd --system --user-group --home-dir /var/lib/chickenbro-qq-channel --shell /usr/sbin/nologin chickenbro-qq
install -d -m 700 /opt/chickenbro-qq-channel /var/lib/chickenbro-qq-channel /etc/chickenbro-qq-channel
install -d -m 700 -o chickenbro-qq -g chickenbro-qq /var/lib/chickenbro-qq-channel/{qq,config,plugins}
install -m 600 "$task_dir/image-lock.json" /opt/chickenbro-qq-channel/image-lock.json
install -m 700 "$task_dir/start-napcat.sh" /opt/chickenbro-qq-channel/start-napcat.sh
python3 - <<'PY'
import json,os,pwd,secrets
from pathlib import Path
os.umask(0o077)
account=pwd.getpwnam('chickenbro-qq')
base=Path('/var/lib/chickenbro-qq-channel/config')
private=Path('/etc/chickenbro-qq-channel')
webui=secrets.token_urlsafe(32)
onebot=secrets.token_urlsafe(32)
def write(path,data,owned=False):
    with path.open('x') as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
    if owned: os.chown(path,account.pw_uid,account.pw_gid)
write(base/'napcat.json',{'fileLog':False,'consoleLog':False,'fileLogLevel':'error',
    'consoleLogLevel':'error','packetBackend':'auto','packetServer':'','o3HookMode':1,
    'bypass':dict.fromkeys(['hook','window','module','process','container','js'],False)},True)
write(base/'webui.json',{'host':'0.0.0.0','port':6099,'prefix':'','token':webui,'loginRate':3},True)
write(base/'onebot11.json',{'network':{'httpServers':[],'httpSseServers':[],'httpClients':[],
    'websocketServers':[{'enable':True,'name':'chickenbro','host':'0.0.0.0','port':3001,
    'reportSelfMessage':False,'enableForcePushEvent':True,'messagePostFormat':'array',
    'token':onebot,'debug':False,'heartInterval':30000}], 'websocketClients':[], 'plugins':[]},
    'musicSignUrl':'','enableLocalFile2Url':False,'parseMultMsg':False},True)
write(private/'credentials.json',{'webuiToken':webui,'onebotToken':onebot})
write(private/'channel.json',{'enabled':False,'botQQ':None,'allowedGroups':[],
    'adminQQs':[],'privateMessages':False,'trigger':'at_only','defaultGame':'wow',
    'maxConcurrentRuns':1,'maxQueuedPerUser':1,'maxQueuedTotal':10})
print('Private credentials and disabled channel configuration created')
PY
docker network create --driver bridge --label chickenbro.scope=qq-channel chickenbro-qq-channel >/dev/null
echo 'Prepared. Run /opt/chickenbro-qq-channel/start-napcat.sh to start the login environment.'

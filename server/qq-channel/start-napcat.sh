#!/usr/bin/env bash
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { echo 'Run as root'; exit 1; }
task_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image"])' "$task_dir/image-lock.json")
[[ "$image" =~ ^mlikiowa/napcat-docker@sha256:[a-f0-9]{64}$ ]] || exit 1
docker image inspect "$image" >/dev/null
if docker container inspect chickenbro-napcat >/dev/null 2>&1; then
  echo 'Container exists. Inspect it; use docker start chickenbro-napcat to resume an explicitly stopped environment.'
  exit 1
fi
for part in qq config plugins; do
  [[ -d "/var/lib/chickenbro-qq-channel/$part" ]] || exit 1
done
login_mount=()
if [[ -f /etc/chickenbro-qq-channel/login.env ]]; then
  [[ "$(stat -c '%u:%a' /etc/chickenbro-qq-channel/login.env)" == '0:600' ]] || {
    echo 'login.env must be owned by root with mode 0600'; exit 1;
  }
  login_mount=(--mount type=bind,src=/etc/chickenbro-qq-channel/login.env,dst=/run/secrets/napcat-login.env,readonly)
fi
docker run -d --pull never \
  --name chickenbro-napcat --hostname chickenbro-qq \
  --label chickenbro.scope=qq-channel \
  --network chickenbro-qq-channel \
  --restart unless-stopped \
  --cpus 1 --memory 768m --memory-swap 1g --pids-limit 256 --shm-size 64m \
  --security-opt no-new-privileges:true \
  --cap-drop ALL --cap-add CHOWN --cap-add SETUID --cap-add SETGID --cap-add DAC_OVERRIDE \
  --log-driver none \
  -e "NAPCAT_UID=$(id -u chickenbro-qq)" -e "NAPCAT_GID=$(id -g chickenbro-qq)" \
  -p 127.0.0.1:16099:6099 -p 127.0.0.1:13001:3001 \
  --mount type=bind,src=/var/lib/chickenbro-qq-channel/qq,dst=/app/.config/QQ \
  --mount type=bind,src=/var/lib/chickenbro-qq-channel/config,dst=/app/napcat/config \
  --mount type=bind,src=/var/lib/chickenbro-qq-channel/plugins,dst=/app/napcat/plugins \
  "${login_mount[@]}" \
  --entrypoint /bin/bash "$image" -c \
  'set -e; umask 077; if [ -f /run/secrets/napcat-login.env ]; then set -a; . /run/secrets/napcat-login.env; set +a; fi; unzip -qn /app/NapCat.Shell.zip -d /app/napcat; exec bash /app/entrypoint.sh'

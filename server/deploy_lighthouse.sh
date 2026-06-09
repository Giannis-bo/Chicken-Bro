#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
REMOTE_DIR="${WOW_LIGHTHOUSE_DIR:-/opt/wow-mini-program}"
SERVICE_NAME="wow-backend"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
# Require a pre-populated known_hosts entry so deploys do not trust a first-seen host key.
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15)
SIMC_GITHUB_REPO="${WOW_SIMC_GITHUB_REPO:-simulationcraft/simc}"
SIMC_BRANCH="${WOW_SIMC_BRANCH:-midnight}"

validate_env_value() {
  local name="$1"
  local value="$2"
  local pattern="$3"
  if [[ ! "${value}" =~ ${pattern} ]]; then
    echo "Invalid ${name}: ${value}" >&2
    exit 1
  fi
}

validate_env_value REMOTE_HOST "${REMOTE_HOST}" '^[A-Za-z0-9_.:-]+$'
validate_env_value REMOTE_USER "${REMOTE_USER}" '^[A-Za-z_][A-Za-z0-9_.-]*$'
validate_env_value REMOTE_DIR "${REMOTE_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_env_value SIMC_GITHUB_REPO "${SIMC_GITHUB_REPO}" '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
validate_env_value SIMC_BRANCH "${SIMC_BRANCH}" '^[A-Za-z0-9_.\@/-]+$'

if [[ -n "${WOW_LIGHTHOUSE_KEY:-}" ]]; then
  SSH_OPTS+=(-i "${WOW_LIGHTHOUSE_KEY}")
fi

ssh_remote() {
  if [[ -n "${WOW_LIGHTHOUSE_PASSWORD:-}" ]]; then
    SSHPASS="${WOW_LIGHTHOUSE_PASSWORD}" sshpass -e ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "$@"
  else
    ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "$@"
  fi
}

echo "Deploying WOW mini program backend to ${SSH_TARGET}:${REMOTE_DIR}"

COPYFILE_DISABLE=1 tar \
  --format ustar \
  --exclude '.git' \
  --exclude 'server/data' \
  --exclude '__pycache__' \
  --exclude '*/__pycache__' \
  --exclude '.DS_Store' \
  -czf - . | ssh_remote "sudo mkdir -p '${REMOTE_DIR}' && sudo tar -xzf - -C '${REMOTE_DIR}' && sudo chown -R ${REMOTE_USER}:${REMOTE_USER} '${REMOTE_DIR}'"

ssh_remote "WOW_LIGHTHOUSE_DIR='${REMOTE_DIR}' SERVICE_NAME='${SERVICE_NAME}' SIMC_GITHUB_REPO='${SIMC_GITHUB_REPO}' SIMC_BRANCH='${SIMC_BRANCH}' bash -s" <<'REMOTE'
set -euo pipefail

REMOTE_DIR="${WOW_LIGHTHOUSE_DIR:-/opt/wow-mini-program}"
SERVICE_NAME="wow-backend"
SIMC_GITHUB_REPO="${SIMC_GITHUB_REPO:-simulationcraft/simc}"
SIMC_BRANCH="${SIMC_BRANCH:-midnight}"
SIMC_ROOT="/opt/wow-simc"
SIMC_SRC="${SIMC_ROOT}/src"
SIMC_BUILD="${SIMC_ROOT}/build"
SIMC_CURRENT="${SIMC_ROOT}/current"
SIMC_BIN="${SIMC_CURRENT}/simc"
SIMC_COMMIT_FILE="${SIMC_ROOT}/.commit"

sudo apt-get update
sudo apt-get install -y python3 nodejs npm nginx git cmake build-essential libcurl4-openssl-dev pkg-config

sudo mkdir -p "${SIMC_ROOT}" /var/lib/wow-backend
sudo chown -R "$(id -un):$(id -gn)" "${SIMC_ROOT}" /var/lib/wow-backend
latest_simc_commit="$(SIMC_GITHUB_REPO="${SIMC_GITHUB_REPO}" SIMC_BRANCH="${SIMC_BRANCH}" python3 - <<'PY'
import json
import os
import sys
from urllib.request import urlopen

repo = os.environ.get("SIMC_GITHUB_REPO", "simulationcraft/simc")
branch = os.environ.get("SIMC_BRANCH", "midnight")
url = f"https://api.github.com/repos/{repo}/branches/{branch}"
try:
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(payload["commit"]["sha"])
except Exception as error:
    print(f"failed to resolve SimulationCraft branch commit: {error}", file=sys.stderr)
    sys.exit(1)
PY
)"
if [[ ! -x "${SIMC_BIN}" || ! -f "${SIMC_COMMIT_FILE}" || "$(cat "${SIMC_COMMIT_FILE}")" != "${latest_simc_commit}" ]]; then
  simc_archive="${SIMC_ROOT}/source-${latest_simc_commit}.tar.gz"
  rm -rf "${SIMC_SRC}" "${SIMC_BUILD}"
  mkdir -p "${SIMC_SRC}"
  if [[ ! -f "${simc_archive}" ]] || ! tar -tzf "${simc_archive}" >/dev/null 2>&1; then
    curl -fL --retry 5 --connect-timeout 30 --speed-time 120 --speed-limit 1024 \
      -o "${simc_archive}" \
      "https://github.com/${SIMC_GITHUB_REPO}/archive/${latest_simc_commit}.tar.gz"
  fi
  tar -xzf "${simc_archive}" --strip-components=1 -C "${SIMC_SRC}"
  cmake -S "${SIMC_SRC}" -B "${SIMC_BUILD}" -DBUILD_GUI=OFF -DCMAKE_BUILD_TYPE=Release
  cmake --build "${SIMC_BUILD}" --target simc --parallel "$(nproc)"
  built_simc="$(find "${SIMC_BUILD}" -type f -name simc -perm -111 | head -n 1)"
  if [[ -z "${built_simc}" ]]; then
    echo "failed to locate built simc binary under ${SIMC_BUILD}" >&2
    exit 1
  fi
  mkdir -p "${SIMC_CURRENT}"
  cp "${built_simc}" "${SIMC_BIN}"
  chmod 0755 "${SIMC_BIN}"
  printf '%s\n' "${latest_simc_commit}" >"${SIMC_COMMIT_FILE}"
fi

sudo tee /usr/local/bin/wow-simc-version-check >/dev/null <<'SIMCCHECK'
#!/usr/bin/env bash
set -euo pipefail

repo="${SIMC_GITHUB_REPO:-simulationcraft/simc}"
branch="${SIMC_BRANCH:-midnight}"
commit_file="${SIMC_COMMIT_FILE:-/opt/wow-simc/.commit}"
simc_bin="${SIMC_BIN:-/opt/wow-simc/current/simc}"
state_dir="/var/lib/wow-backend"
state_file="${state_dir}/simc-version.json"

mkdir -p "${state_dir}"
SIMC_GITHUB_REPO="${repo}" SIMC_BRANCH="${branch}" SIMC_COMMIT_FILE="${commit_file}" SIMC_BIN="${simc_bin}" STATE_FILE="${state_file}" python3 - <<'PY'
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

repo = os.environ.get("SIMC_GITHUB_REPO", "simulationcraft/simc")
branch = os.environ.get("SIMC_BRANCH", "midnight")
commit_file = Path(os.environ.get("SIMC_COMMIT_FILE", "/opt/wow-simc/.commit"))
simc_bin = os.environ.get("SIMC_BIN", "/opt/wow-simc/current/simc")
state_file = Path(os.environ.get("STATE_FILE", "/var/lib/wow-backend/simc-version.json"))
local_commit = ""
latest_commit = ""
simc_version = ""
error = ""

try:
    if commit_file.exists():
        local_commit = commit_file.read_text(encoding="utf-8").strip()
    url = f"https://api.github.com/repos/{repo}/branches/{branch}"
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    latest_commit = payload["commit"]["sha"]
    try:
        output = subprocess.check_output(
            [simc_bin, "iterations=1", "max_time=1"],
            text=True,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
        for line in output.splitlines():
            if "SimulationCraft" in line:
                simc_version = line[line.index("SimulationCraft"):].strip()
                break
        if not simc_version:
            simc_version = local_commit[:12]
    except Exception:
        simc_version = local_commit[:12]
except Exception as exc:
    error = str(exc)

status = {
    "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "localTag": local_commit[:12],
    "latestTag": latest_commit[:12],
    "localCommit": local_commit,
    "latestCommit": latest_commit,
    "updateAvailable": bool(latest_commit and local_commit and latest_commit != local_commit),
    "source": "github",
    "repo": repo,
    "branch": branch,
    "binary": simc_bin,
    "version": simc_version,
    "error": error,
}
state_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
PY
chmod 0644 "${state_file}"
SIMCCHECK
sudo chmod 0755 /usr/local/bin/wow-simc-version-check

sudo tee /etc/systemd/system/wow-simc-version-check.service >/dev/null <<'SIMCSERVICE'
[Unit]
Description=Check SimulationCraft source version
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=ubuntu
Environment=SIMC_GITHUB_REPO=simulationcraft/simc
Environment=SIMC_BRANCH=midnight
Environment=SIMC_COMMIT_FILE=/opt/wow-simc/.commit
Environment=SIMC_BIN=/opt/wow-simc/current/simc
ExecStart=/usr/local/bin/wow-simc-version-check
SIMCSERVICE

sudo tee /etc/systemd/system/wow-simc-version-check.timer >/dev/null <<'SIMCTIMER'
[Unit]
Description=Run SimulationCraft version detection regularly

[Timer]
OnBootSec=5min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
SIMCTIMER

sudo mkdir -p "${REMOTE_DIR}/server/data"
sudo chown -R "$(id -un):$(id -gn)" "${REMOTE_DIR}/server/data"
sudo cp "${REMOTE_DIR}/server/wow-backend.service" "/etc/systemd/system/${SERVICE_NAME}.service"

sudo tee /etc/nginx/sites-available/wow-backend >/dev/null <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/wow-backend /etc/nginx/sites-enabled/wow-backend
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

if systemctl list-unit-files wow-news-backend.service >/dev/null 2>&1; then
  sudo systemctl disable --now wow-news-backend.service >/dev/null 2>&1 || true
fi

port80_pid="$(sudo ss -H -ltnp "sport = :80" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -n 1)"
if [[ -n "${port80_pid}" ]]; then
  port80_cmd="$(sudo tr '\0' ' ' <"/proc/${port80_pid}/cmdline")"
  port80_user="$(ps -o user= -p "${port80_pid}" | xargs)"
  if [[ "${port80_cmd}" != *"nginx"* ]]; then
    echo "Port 80 is held by pid=${port80_pid} user=${port80_user} command=${port80_cmd}" >&2
    if [[ "${port80_cmd}" == *"/home/ubuntu/wow-news-backend/news_backend.py"* ]]; then
      sudo kill "${port80_pid}" || true
      sleep 1
    else
      echo "Refusing to kill an unknown port 80 process during deploy." >&2
      exit 1
    fi
  fi
fi

sudo systemctl daemon-reload
sudo systemctl enable --now wow-simc-version-check.timer
sudo systemctl start wow-simc-version-check.service
sudo systemctl enable --now "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl restart nginx

for _ in {1..20}; do
  if curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS http://127.0.0.1:8787/health
curl -fsS http://127.0.0.1/api/builds/home >/dev/null
curl -fsS http://127.0.0.1/api/pve/home >/dev/null
curl -fsS http://127.0.0.1/api/simulator/home >/dev/null
"${SIMC_BIN}" iterations=1 max_time=1 >/dev/null
REMOTE

curl -fsS "http://${REMOTE_HOST}/health"
echo
echo "Deployment complete: http://${REMOTE_HOST}"

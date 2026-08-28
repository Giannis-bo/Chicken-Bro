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
CODEX_JOBS_DIR="${WOW_CODEX_JOBS_DIR:-/var/lib/wow-backend/codex-jobs}"
CODEX_HOME_DIR="${WOW_CODEX_HOME:-/home/${REMOTE_USER}/.codex}"
SKIP_BOOTSTRAP="${WOW_DEPLOY_SKIP_BOOTSTRAP:-0}"
START_ASYNC_SYNCS="${WOW_DEPLOY_START_ASYNC_SYNCS:-0}"
EXACT_WORKER_PREFLIGHT="${WOW_DEPLOY_EXACT_WORKER_PREFLIGHT:-0}"

validate_env_value() {
  local name="$1"
  local value="$2"
  local pattern="$3"
  if [[ ! "${value}" =~ ${pattern} ]]; then
    echo "Invalid ${name}: ${value}" >&2
    exit 1
  fi
}

reject_path_traversal() {
  local name="$1"
  local value="$2"
  if [[ "${value}" == *".."* ]]; then
    echo "Invalid ${name}: path traversal is not allowed" >&2
    exit 1
  fi
}

validate_env_value REMOTE_HOST "${REMOTE_HOST}" '^[A-Za-z0-9_.:-]+$'
validate_env_value REMOTE_USER "${REMOTE_USER}" '^[A-Za-z_][A-Za-z0-9_.-]*$'
validate_env_value REMOTE_DIR "${REMOTE_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_env_value SIMC_GITHUB_REPO "${SIMC_GITHUB_REPO}" '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
validate_env_value SIMC_BRANCH "${SIMC_BRANCH}" '^[A-Za-z0-9_.\@/-]+$'
validate_env_value CODEX_JOBS_DIR "${CODEX_JOBS_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_env_value CODEX_HOME_DIR "${CODEX_HOME_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_env_value SKIP_BOOTSTRAP "${SKIP_BOOTSTRAP}" '^[01]$'
validate_env_value START_ASYNC_SYNCS "${START_ASYNC_SYNCS}" '^[01]$'
validate_env_value EXACT_WORKER_PREFLIGHT "${EXACT_WORKER_PREFLIGHT}" '^[01]$'
reject_path_traversal REMOTE_DIR "${REMOTE_DIR}"
reject_path_traversal CODEX_JOBS_DIR "${CODEX_JOBS_DIR}"
reject_path_traversal CODEX_HOME_DIR "${CODEX_HOME_DIR}"

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
  --exclude 'server/data/wow_news.sqlite3' \
  --exclude 'server/data/wow_news.sqlite3*' \
  --exclude 'apps/mini-taro/dist' \
  --exclude 'apps/mini-taro/.swc' \
  --exclude 'project.private.config.json' \
  --exclude '*/project.private.config.json' \
  --exclude 'node_modules' \
  --exclude 'artifacts' \
  --exclude 'backups' \
  --exclude '.codex-backups' \
  --exclude '.codex-candidate-backups' \
  --exclude '.candidate-backups' \
  --exclude '.candidate-staging' \
  --exclude '.worktrees' \
  --exclude '.agents' \
  --exclude '.gstack' \
  --exclude '.superpowers' \
  --exclude '__pycache__' \
  --exclude '*/__pycache__' \
  --exclude '.DS_Store' \
  -czf - . | ssh_remote "sudo mkdir -p '${REMOTE_DIR}' && sudo tar -xzf - -C '${REMOTE_DIR}' && sudo chown -R ${REMOTE_USER}:${REMOTE_USER} '${REMOTE_DIR}'"

ssh_remote "WOW_LIGHTHOUSE_DIR='${REMOTE_DIR}' SERVICE_NAME='${SERVICE_NAME}' SIMC_GITHUB_REPO='${SIMC_GITHUB_REPO}' SIMC_BRANCH='${SIMC_BRANCH}' WOW_CODEX_JOBS_DIR='${CODEX_JOBS_DIR}' WOW_CODEX_HOME='${CODEX_HOME_DIR}' WOW_DEPLOY_SKIP_BOOTSTRAP='${SKIP_BOOTSTRAP}' WOW_DEPLOY_START_ASYNC_SYNCS='${START_ASYNC_SYNCS}' WOW_DEPLOY_EXACT_WORKER_PREFLIGHT='${EXACT_WORKER_PREFLIGHT}' bash -s" <<'REMOTE'
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
CODEX_JOBS_DIR="${WOW_CODEX_JOBS_DIR:-/var/lib/wow-backend/codex-jobs}"
CODEX_HOME_DIR="${WOW_CODEX_HOME:-/home/ubuntu/.codex}"
CODEX_BIN="/usr/local/bin/codex"
SKIP_BOOTSTRAP="${WOW_DEPLOY_SKIP_BOOTSTRAP:-0}"
START_ASYNC_SYNCS="${WOW_DEPLOY_START_ASYNC_SYNCS:-0}"
EXACT_WORKER_PREFLIGHT="${WOW_DEPLOY_EXACT_WORKER_PREFLIGHT:-0}"

if [[ "${SKIP_BOOTSTRAP}" == "1" ]]; then
  echo "Skipping remote bootstrap because WOW_DEPLOY_SKIP_BOOTSTRAP=1; reusing remote packages, Codex, and SimulationCraft."
  for required_command in python3 curl systemctl; do
    if ! command -v "${required_command}" >/dev/null 2>&1; then
      echo "Missing required command in hot deploy mode: ${required_command}" >&2
      exit 1
    fi
  done
  if [[ ! -x "${SIMC_BIN}" ]]; then
    echo "Missing existing SimulationCraft binary in hot deploy mode: ${SIMC_BIN}" >&2
    exit 1
  fi
  sudo mkdir -p "${SIMC_ROOT}" /var/lib/wow-backend "${CODEX_JOBS_DIR}" "${CODEX_HOME_DIR}"
  sudo chown -R "$(id -un):$(id -gn)" "${SIMC_ROOT}" /var/lib/wow-backend "${CODEX_HOME_DIR}"
else # full remote bootstrap
install_codex_from_github_release() {
  CODEX_HOME_DIR="${CODEX_HOME_DIR}" python3 - <<'PY'
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

target = "x86_64-unknown-linux-musl"
package_asset = f"codex-package-{target}.tar.gz"
checksum_asset = "codex-package_SHA256SUMS"
api_url = "https://api.github.com/repos/openai/codex/releases/latest"
codex_home = Path(os.environ.get("CODEX_HOME_DIR", str(Path.home() / ".codex")))
bin_dir = Path.home() / ".local" / "bin"


def fetch_json(url):
    with urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url, path):
    subprocess.run(
        [
            "curl",
            "-fL",
            "--retry",
            "5",
            "--connect-timeout",
            "30",
            "--speed-time",
            "120",
            "--speed-limit",
            "1024",
            "-o",
            str(path),
            url,
        ],
        check=True,
    )


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


release = fetch_json(api_url)
tag = release["tag_name"]
version = tag.removeprefix("rust-v")
assets = {asset["name"]: asset for asset in release["assets"]}
if package_asset not in assets or checksum_asset not in assets:
    raise SystemExit(f"missing Codex release assets for {target} in {tag}")

standalone_root = codex_home / "packages" / "standalone"
release_dir = standalone_root / "releases" / f"{version}-{target}"
current_link = standalone_root / "current"
if (release_dir / "bin" / "codex").exists():
    bin_dir.mkdir(parents=True, exist_ok=True)
    if current_link.exists() or current_link.is_symlink():
        current_link.unlink()
    current_link.symlink_to(release_dir)
    visible = bin_dir / "codex"
    if visible.exists() or visible.is_symlink():
        visible.unlink()
    visible.symlink_to(current_link / "bin" / "codex")
    raise SystemExit(0)

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    package_path = tmp_path / package_asset
    checksum_path = tmp_path / checksum_asset
    download(assets[checksum_asset]["browser_download_url"], checksum_path)
    download(assets[package_asset]["browser_download_url"], package_path)

    expected_digest = ""
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == package_asset:
            expected_digest = parts[0].lower()
            break
    if not expected_digest:
        raise SystemExit(f"missing checksum entry for {package_asset}")
    actual_digest = sha256(package_path)
    if actual_digest != expected_digest:
        raise SystemExit(f"Codex package checksum mismatch: expected {expected_digest}, got {actual_digest}")

    staging_dir = standalone_root / "releases" / f".staging.{version}-{target}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)
    with tarfile.open(package_path, "r:gz") as archive:
        archive.extractall(staging_dir)

    for executable in [
        staging_dir / "bin" / "codex",
        staging_dir / "codex-path" / "rg",
        staging_dir / "codex-resources" / "bwrap",
    ]:
        if executable.exists():
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    codex_link = staging_dir / "codex"
    if codex_link.exists() or codex_link.is_symlink():
        codex_link.unlink()
    codex_link.symlink_to("bin/codex")

    if release_dir.exists() or release_dir.is_symlink():
        shutil.rmtree(release_dir)
    staging_dir.rename(release_dir)

bin_dir.mkdir(parents=True, exist_ok=True)
if current_link.exists() or current_link.is_symlink():
    current_link.unlink()
current_link.symlink_to(release_dir)
visible = bin_dir / "codex"
if visible.exists() or visible.is_symlink():
    visible.unlink()
visible.symlink_to(current_link / "bin" / "codex")
PY
}

sudo apt-get update
sudo apt-get install -y python3 nodejs npm nginx git cmake build-essential libcurl4-openssl-dev pkg-config curl ca-certificates

sudo mkdir -p "${SIMC_ROOT}" /var/lib/wow-backend "${CODEX_JOBS_DIR}" "${CODEX_HOME_DIR}"
sudo chown -R "$(id -un):$(id -gn)" "${SIMC_ROOT}" /var/lib/wow-backend "${CODEX_HOME_DIR}"

if ! command -v codex >/dev/null 2>&1; then
  if ! curl -fsSL --connect-timeout 30 https://chatgpt.com/codex/install.sh | CODEX_NON_INTERACTIVE=1 sh; then
    echo "Codex installer endpoint failed; falling back to GitHub release asset." >&2
    install_codex_from_github_release
  fi
fi
if [[ -x "${HOME}/.local/bin/codex" && ! -x "${CODEX_BIN}" ]]; then
  sudo ln -sf "${HOME}/.local/bin/codex" "${CODEX_BIN}"
fi
if ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI install did not place codex on PATH" >&2
  exit 1
fi

if [[ ! -f "${CODEX_HOME_DIR}/config.toml" ]]; then
  cat >"${CODEX_HOME_DIR}/config.toml" <<CODEXCONFIG
model = "gpt-5.5"
approval_policy = "never"
sandbox_mode = "workspace-write"
cli_auth_credentials_store = "file"

[projects."${CODEX_JOBS_DIR}"]
trust_level = "trusted"
CODEXCONFIG
else
  if ! grep -q 'cli_auth_credentials_store = "file"' "${CODEX_HOME_DIR}/config.toml"; then
    printf '\ncli_auth_credentials_store = "file"\n' >>"${CODEX_HOME_DIR}/config.toml"
  fi
  if ! grep -q "\\[projects\\.\"${CODEX_JOBS_DIR}\"\\]" "${CODEX_HOME_DIR}/config.toml"; then
    printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "${CODEX_JOBS_DIR}" >>"${CODEX_HOME_DIR}/config.toml"
  fi
fi
chmod 0700 "${CODEX_HOME_DIR}" "${CODEX_JOBS_DIR}"
chmod 0600 "${CODEX_HOME_DIR}/config.toml"
latest_simc_commit=""
if ! latest_simc_commit="$(SIMC_GITHUB_REPO="${SIMC_GITHUB_REPO}" SIMC_BRANCH="${SIMC_BRANCH}" python3 - <<'PY'
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
)"; then
  if [[ -x "${SIMC_BIN}" && -f "${SIMC_COMMIT_FILE}" ]]; then
    latest_simc_commit="$(cat "${SIMC_COMMIT_FILE}")"
    echo "Reusing existing SimulationCraft binary at ${SIMC_BIN}; GitHub version lookup failed." >&2
  else
    echo "SimulationCraft is not installed and GitHub version lookup failed." >&2
    exit 1
  fi
fi
if [[ ! -x "${SIMC_BIN}" || ! -f "${SIMC_COMMIT_FILE}" || "$(cat "${SIMC_COMMIT_FILE}")" != "${latest_simc_commit}" ]]; then
  simc_archive="${SIMC_ROOT}/source-${latest_simc_commit}.tar.gz"
  rm -rf "${SIMC_SRC}" "${SIMC_BUILD}"
  mkdir -p "${SIMC_SRC}"
  if [[ ! -f "${simc_archive}" ]] || ! tar -tzf "${simc_archive}" >/dev/null 2>&1; then
    if ! curl -fL --retry 5 --connect-timeout 30 --speed-time 120 --speed-limit 1024 \
      -o "${simc_archive}" \
      "https://github.com/${SIMC_GITHUB_REPO}/archive/${latest_simc_commit}.tar.gz"; then
      if [[ -x "${SIMC_BIN}" && -f "${SIMC_COMMIT_FILE}" ]]; then
        latest_simc_commit="$(cat "${SIMC_COMMIT_FILE}")"
        echo "SimulationCraft source download failed; reusing existing SimulationCraft binary at ${SIMC_BIN}." >&2
      else
        echo "SimulationCraft source download failed and no existing binary is available." >&2
        exit 1
      fi
    fi
  fi
  if [[ ! -x "${SIMC_BIN}" || ! -f "${SIMC_COMMIT_FILE}" || "$(cat "${SIMC_COMMIT_FILE}")" != "${latest_simc_commit}" ]]; then
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
import hashlib
import json
import os
import re
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
artifact_hash = ""
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

try:
    digest = hashlib.sha256()
    with Path(simc_bin).open("rb") as binary:
        for chunk in iter(lambda: binary.read(1024 * 1024), b""):
            digest.update(chunk)
    artifact_hash = digest.hexdigest()
except OSError:
    artifact_hash = ""

build_match = re.search(r"\b([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\b", simc_version)
simc_runtime_revision = ""
if (
    build_match
    and re.fullmatch(r"[0-9a-f]{40}", local_commit.lower())
    and re.fullmatch(r"[0-9a-f]{64}", artifact_hash.lower())
):
    simc_runtime_revision = (
        f"simc:{build_match.group(1)}:{local_commit.lower()}:{artifact_hash.lower()}"
    )

status = {
    "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "localTag": local_commit[:12],
    "latestTag": latest_commit[:12],
    "localCommit": local_commit,
    "sourceCommit": local_commit,
    "latestCommit": latest_commit,
    "simcRuntimeRevision": simc_runtime_revision,
    "artifactHash": artifact_hash,
    "binaryPath": simc_bin,
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
After=network-online.target mihomo.service
Wants=network-online.target mihomo.service

[Service]
Type=oneshot
User=ubuntu
Environment=SIMC_GITHUB_REPO=simulationcraft/simc
Environment=SIMC_BRANCH=midnight
Environment=SIMC_COMMIT_FILE=/opt/wow-simc/.commit
Environment=SIMC_BIN=/opt/wow-simc/current/simc
Environment=HTTPS_PROXY=http://127.0.0.1:7890
Environment=HTTP_PROXY=http://127.0.0.1:7890
Environment=ALL_PROXY=socks5h://127.0.0.1:7890
Environment=NO_PROXY=127.0.0.1,localhost,::1,169.254.169.254
Environment=https_proxy=http://127.0.0.1:7890
Environment=http_proxy=http://127.0.0.1:7890
Environment=all_proxy=socks5h://127.0.0.1:7890
Environment=no_proxy=127.0.0.1,localhost,::1,169.254.169.254
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
fi

sudo mkdir -p "${REMOTE_DIR}/server/data"
sudo chown -R "$(id -un):$(id -gn)" "${REMOTE_DIR}/server/data"
sudo mkdir -p /var/www/wow-assets/releases
sudo mkdir -p /var/www/wow-media/releases
sudo mkdir -p /var/www/wow-evidence/releases
sudo chown -R www-data:www-data /var/www/wow-assets /var/www/wow-media /var/www/wow-evidence

# Task 4W remains dormant. This opt-in preflight installs only the unit file;
# it never enables, starts, restarts, migrates, or provisions a role/service.
exact_worker_change_applied=0
exact_worker_rollback_dir=""
rollback_exact_worker_service() {
  if [[ "${exact_worker_change_applied}" != "1" || -z "${exact_worker_rollback_dir}" ]]; then
    return
  fi
  echo "Rolling back dormant exact worker service/env from ${exact_worker_rollback_dir}" >&2
  if [[ -f "${exact_worker_rollback_dir}/previous.service" ]]; then
    sudo cp "${exact_worker_rollback_dir}/previous.service" \
      /etc/systemd/system/wow-gear-exact-authority-worker.service
  elif [[ -f "${exact_worker_rollback_dir}/service.absent" ]]; then
    sudo rm -f /etc/systemd/system/wow-gear-exact-authority-worker.service
  fi
  if [[ -f "${exact_worker_rollback_dir}/previous.env" ]]; then
    sudo cp "${exact_worker_rollback_dir}/previous.env" /etc/wow-exact-worker.env
    sudo chmod 0600 /etc/wow-exact-worker.env
  fi
  sudo systemctl daemon-reload
}
trap rollback_exact_worker_service ERR

if [[ "${EXACT_WORKER_PREFLIGHT}" == "1" ]]; then
  sudo test -f /etc/wow-backend.env
  sudo test -f /etc/wow-exact-worker.env
  exact_worker_env_mode="$(sudo stat -c '%a' /etc/wow-exact-worker.env)"
  if [[ "${exact_worker_env_mode}" != "600" ]]; then
    echo "/etc/wow-exact-worker.env must be mode 0600" >&2
    exit 1
  fi

  sudo env PYTHONPATH="${REMOTE_DIR}" python3 - <<'PY'
import hashlib
import shlex
from pathlib import Path

import psycopg

from server.gear_exact_authority_worker import establish_exact_worker_role


def read_environment(path):
    values = {}
    for source_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = source_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise SystemExit(f"invalid environment line in {path}")
        key, raw = line.split("=", 1)
        parsed = shlex.split(raw, posix=True)
        values[key.strip()] = parsed[0] if parsed else ""
    return values


backend = read_environment("/etc/wow-backend.env")
worker = read_environment("/etc/wow-exact-worker.env")
app_dsn = backend.get("WOW_DATABASE_URL", "").strip()
worker_dsn = worker.get("WOW_EXACT_WORKER_DATABASE_URL", "").strip()
if worker.get("WOW_DATABASE_URL", "").strip():
    raise SystemExit("worker env must not contain WOW_DATABASE_URL")
if not app_dsn or not worker_dsn or app_dsn == worker_dsn:
    raise SystemExit("app and exact-worker DSNs must be present and distinct")

with psycopg.connect(app_dsn) as app_connection:
    with app_connection.cursor() as cursor:
        cursor.execute("SELECT session_user, current_user")
        if cursor.fetchone() != ("wow_app", "wow_app"):
            raise SystemExit("public DSN must use the wow_app LOGIN role")

with psycopg.connect(worker_dsn) as worker_connection:
    # This performs SET ROLE before validating session_user/current_user and
    # pg_catalog.pg_has_role membership against the NOLOGIN group.
    establish_exact_worker_role(worker_connection)
    with worker_connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolname, rolcanlogin, rolinherit, rolsuper, rolcreatedb, "
            "rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_catalog.pg_roles "
            "WHERE rolname = ANY(%s) ORDER BY rolname",
            (["wow_app", "wow_exact_worker", "wow_migrator"],),
        )
        roles = {row[0]: row[1:] for row in cursor.fetchall()}
        if set(roles) != {"wow_app", "wow_exact_worker", "wow_migrator"}:
            raise SystemExit("required Task 4W roles are missing")
        for login_role in ("wow_app", "wow_migrator"):
            attributes = roles[login_role]
            if attributes[0] is not True or attributes[4] is not False:
                raise SystemExit(f"{login_role} must remain LOGIN NOCREATEROLE")
        worker_group = roles["wow_exact_worker"]
        if worker_group[0] is not False or any(
            value is not False for value in worker_group[2:]
        ):
            raise SystemExit(
                "wow_exact_worker must remain NOLOGIN NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )

redacted = {
    "app": hashlib.sha256(app_dsn.encode("utf-8")).hexdigest()[:12],
    "worker": hashlib.sha256(worker_dsn.encode("utf-8")).hexdigest()[:12],
}
print(
    "Exact worker preflight passed: "
    f"app=<redacted:{redacted['app']}> "
    f"worker=<redacted:{redacted['worker']}> distinct=true"
)
PY

  exact_worker_rollback_dir="/var/lib/wow-backend/exact-worker-rollback/$(date -u +%Y%m%dT%H%M%SZ)"
  sudo install -d -m 0700 "${exact_worker_rollback_dir}"
  if [[ -f /etc/systemd/system/wow-gear-exact-authority-worker.service ]]; then
    sudo cp /etc/systemd/system/wow-gear-exact-authority-worker.service \
      "${exact_worker_rollback_dir}/previous.service"
  else
    sudo touch "${exact_worker_rollback_dir}/service.absent"
  fi
  sudo cp /etc/wow-exact-worker.env "${exact_worker_rollback_dir}/previous.env"
  sudo chmod 0600 "${exact_worker_rollback_dir}/previous.env"
  sudo cp "${REMOTE_DIR}/server/wow-gear-exact-authority-worker.service" \
    /etc/systemd/system/wow-gear-exact-authority-worker.service
  exact_worker_change_applied=1
  echo "Dormant exact worker unit installed; activation remains a separate authorization."
else
  echo "Skipping dormant exact worker preflight/install because WOW_DEPLOY_EXACT_WORKER_PREFLIGHT is not 1."
fi

sudo cp "${REMOTE_DIR}/server/wow-backend.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo cp "${REMOTE_DIR}/server/wow-websim-sync.service" "/etc/systemd/system/wow-websim-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-websim-sync.timer" "/etc/systemd/system/wow-websim-sync.timer"
sudo cp "${REMOTE_DIR}/server/wow-stat-weights-sync.service" "/etc/systemd/system/wow-stat-weights-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-stat-weights-sync.timer" "/etc/systemd/system/wow-stat-weights-sync.timer"
sudo cp "${REMOTE_DIR}/server/wow-chickenbro-source-refresh.service" "/etc/systemd/system/wow-chickenbro-source-refresh.service"
sudo cp "${REMOTE_DIR}/server/wow-chickenbro-source-refresh.timer" "/etc/systemd/system/wow-chickenbro-source-refresh.timer"
sudo cp "${REMOTE_DIR}/server/wow-community-template-sync.service" "/etc/systemd/system/wow-community-template-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-community-template-sync.timer" "/etc/systemd/system/wow-community-template-sync.timer"
sudo cp "${REMOTE_DIR}/server/wow-gear-observed-backfill.service" "/etc/systemd/system/wow-gear-observed-backfill.service"
sudo cp "${REMOTE_DIR}/server/wow-gear-observed-backfill.timer" "/etc/systemd/system/wow-gear-observed-backfill.timer"
sudo cp "${REMOTE_DIR}/server/wow-gear-release-refresh.service" "/etc/systemd/system/wow-gear-release-refresh.service"
sudo cp "${REMOTE_DIR}/server/wow-gear-release-refresh.timer" "/etc/systemd/system/wow-gear-release-refresh.timer"
sudo cp "${REMOTE_DIR}/server/wow-attribute-rule-audit.service" "/etc/systemd/system/wow-attribute-rule-audit.service"
sudo cp "${REMOTE_DIR}/server/wow-season-recommended-gear-sync.service" "/etc/systemd/system/wow-season-recommended-gear-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-season-recommended-gear-sync.timer" "/etc/systemd/system/wow-season-recommended-gear-sync.timer"
sudo cp "${REMOTE_DIR}/server/wow-community-best-guard-sync.service" "/etc/systemd/system/wow-community-best-guard-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-community-best-guard-sync.timer" "/etc/systemd/system/wow-community-best-guard-sync.timer"
sudo cp "${REMOTE_DIR}/server/wow-recommended-bis-guard-sync.service" "/etc/systemd/system/wow-recommended-bis-guard-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-recommended-bis-guard-sync.timer" "/etc/systemd/system/wow-recommended-bis-guard-sync.timer"
sudo cp "${REMOTE_DIR}/server/wow-recommended-bis-prototype-sync.service" "/etc/systemd/system/wow-recommended-bis-prototype-sync.service"
sudo cp "${REMOTE_DIR}/server/wow-data-health-followup.service" "/etc/systemd/system/wow-data-health-followup.service"
sudo cp "${REMOTE_DIR}/server/wow-data-health-followup.timer" "/etc/systemd/system/wow-data-health-followup.timer"
sudo cp "${REMOTE_DIR}/server/wow-talent-graph-recovery.service" "/etc/systemd/system/wow-talent-graph-recovery.service"
sudo chmod 0755 "${REMOTE_DIR}/server/simc_runtime_update.sh"
sudo cp "${REMOTE_DIR}/server/wow-simc-runtime-update.service" "/etc/systemd/system/wow-simc-runtime-update.service"
sudo cp "${REMOTE_DIR}/server/wow-gear-stat-snapshot-worker.service" "/etc/systemd/system/wow-gear-stat-snapshot-worker.service"

sudo tee /etc/nginx/sites-available/wow-backend >/dev/null <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types application/json text/plain text/css application/javascript;
    gzip_vary on;

    location ^~ /wow-assets/releases/ {
        root /var/www;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        add_header Access-Control-Allow-Origin "*" always;
        add_header X-Content-Type-Options "nosniff" always;
    }

    location ^~ /wow-media/releases/ {
        root /var/www;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        add_header Access-Control-Allow-Origin "*" always;
        add_header X-Content-Type-Options "nosniff" always;
    }

    location ^~ /wow-evidence/releases/ {
        root /var/www;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        add_header Access-Control-Allow-Origin "*" always;
        add_header X-Content-Type-Options "nosniff" always;
    }

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

# The public API host terminates TLS in a separately managed server block. Keep
# the immutable evidence route available there as well; otherwise HTTPS falls
# through to the backend proxy and a published release is not publicly
# addressable.
if sudo test -f /etc/nginx/sites-enabled/api.chickenbro.cloud; then
  sudo python3 - <<'PY'
from pathlib import Path
import os
import stat

site = Path('/etc/nginx/sites-enabled/api.chickenbro.cloud').resolve()
text = site.read_text()
if 'location ^~ /wow-evidence/releases/' not in text:
    marker = '    location / {\n'
    block = '''    location ^~ /wow-evidence/releases/ {
        root /var/www;
        try_files $uri =404;
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        add_header Access-Control-Allow-Origin "*" always;
        add_header X-Content-Type-Options "nosniff" always;
    }

'''
    if marker not in text:
        raise SystemExit(f'HTTPS nginx site has no insertion marker: {site}')
    mode = stat.S_IMODE(site.stat().st_mode)
    tmp = site.with_name(f'.{site.name}.codex-tmp')
    tmp.write_text(text.replace(marker, block + marker, 1))
    os.chmod(tmp, mode)
    os.replace(tmp, site)
PY
fi

sudo nginx -t

if systemctl list-unit-files wow-news-backend.service >/dev/null 2>&1; then
  sudo systemctl disable --now wow-news-backend.service >/dev/null 2>&1 || true
fi
sudo rm -rf /etc/systemd/system/wow-news-backend.service.d
sudo rm -f /etc/systemd/system/wow-news-backend.service
sudo systemctl mask wow-news-backend.service >/dev/null 2>&1 || true

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
if [[ "${SKIP_BOOTSTRAP}" != "1" ]]; then
  sudo systemctl enable --now wow-simc-version-check.timer
  sudo systemctl start wow-simc-version-check.service
fi
sudo systemctl reset-failed wow-websim-sync.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-websim-sync.timer
sudo systemctl reset-failed wow-stat-weights-sync.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-stat-weights-sync.timer
sudo systemctl reset-failed wow-chickenbro-source-refresh.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-chickenbro-source-refresh.timer
sudo systemctl reset-failed wow-community-template-sync.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-community-template-sync.timer
sudo systemctl reset-failed wow-gear-observed-backfill.service >/dev/null 2>&1 || true
sudo systemctl reset-failed wow-gear-release-refresh.service >/dev/null 2>&1 || true
sudo systemctl enable wow-gear-release-refresh.timer
sudo systemctl reset-failed wow-season-recommended-gear-sync.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-season-recommended-gear-sync.timer
sudo systemctl reset-failed wow-community-best-guard-sync.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-community-best-guard-sync.timer
sudo systemctl reset-failed wow-recommended-bis-guard-sync.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-recommended-bis-guard-sync.timer
sudo systemctl reset-failed wow-recommended-bis-prototype-sync.service >/dev/null 2>&1 || true
sudo systemctl reset-failed wow-data-health-followup.service >/dev/null 2>&1 || true
sudo systemctl enable --now wow-data-health-followup.timer
sudo systemctl reset-failed wow-talent-graph-recovery.service >/dev/null 2>&1 || true
sudo systemctl reset-failed wow-simc-runtime-update.service >/dev/null 2>&1 || true
sudo systemctl reset-failed wow-gear-stat-snapshot-worker.service >/dev/null 2>&1 || true
sudo systemctl enable wow-gear-stat-snapshot-worker.service
sudo systemctl restart wow-gear-stat-snapshot-worker.service
echo "PG-native sync timers enabled; gear release refresh timer enabled but not started; observed gear backfill unit installed but not auto-enabled by deploy."
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
curl -fsS http://127.0.0.1/api/websim/bootstrap >/dev/null
curl -fsS http://127.0.0.1/websim/ >/dev/null
"${SIMC_BIN}" iterations=1 max_time=1 >/dev/null

if [[ "${START_ASYNC_SYNCS}" == "1" ]]; then
  sudo systemctl start --no-block wow-websim-sync.service
  sudo systemctl start --no-block wow-stat-weights-sync.service
  sudo systemctl start --no-block wow-community-template-sync.service
  echo "Started PG-native async sync services."
else
  echo "Skipping PG-native async sync starts because WOW_DEPLOY_START_ASYNC_SYNCS is not 1."
fi
REMOTE

curl -fsS "http://${REMOTE_HOST}/health"
echo
echo "Deployment complete: http://${REMOTE_HOST}"

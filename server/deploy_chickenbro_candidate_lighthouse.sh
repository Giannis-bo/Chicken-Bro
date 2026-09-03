#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
EXPECTED_COMMIT=""
REVIEWED_INVENTORY_SHA=""
REVIEWED_RECOVERY_MANIFEST_SHA=""

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INVENTORY_FILE="${REPO_ROOT}/docs/refactor/chickenbro-simc-cloud-inventory.json"

REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
CANDIDATE_ROOT="/opt/chickenbro-candidate"
CANDIDATE_DATABASE="chickenbro_candidate"
CANDIDATE_PORT="8791"
CANDIDATE_PREFIX="/api/v2-candidate"
CANDIDATE_API_SERVICE="chickenbro-api-candidate"
CANDIDATE_WORKER_SERVICE="chickenbro-worker-candidate"
LEGACY_CANDIDATE_SERVICE="wow-v2-api-candidate"
CANDIDATE_API_ENV="/etc/chickenbro-api-candidate.env"
CANDIDATE_SOURCE_ENV="/etc/chickenbro-source-candidate.env"
CANDIDATE_PGPASSFILE="/etc/chickenbro-api-candidate.pgpass"
CANDIDATE_WORKER_ENV="/etc/chickenbro-worker-candidate.env"
CANDIDATE_CODEX_PROFILE="/home/${REMOTE_USER}/.codex/chickenbro-candidate.config.toml"
RUNTIME_ROOT="/opt/chickenbro-runtime"
EXISTING_RUNTIME_PYTHON="/opt/wow-mini-program/.venv-v2/bin/python"
WWW_NGINX_SITE="/etc/nginx/sites-available/wow-v2-web"
API_NGINX_SITE="/etc/nginx/sites-enabled/api.chickenbro.cloud"
WEB_ROOT="/var/www/chickenbro-candidate"
LEGACY_API_ENV="/etc/wow-v2-api.env"
LEGACY_SOURCE_ENV="/etc/wow-v2-source.env"
REMOTE_RECOVERY_MANIFEST="${WOW_CHICKENBRO_REMOTE_RECOVERY_MANIFEST:-/var/lib/chickenbro-recovery/whitelist-recovery.json}"
REMOTE_RECOVERY_ROOT="$(dirname -- "${REMOTE_RECOVERY_MANIFEST}")/candidate-runs"
REQUESTED_ASYNC_SYNCS="${WOW_DEPLOY_START_ASYNC_SYNCS:-0}"
WOW_DEPLOY_START_ASYNC_SYNCS="0"

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15)

die() {
  printf 'deploy_chickenbro_candidate: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf '%s\n' \
    'Usage:' \
    '  server/deploy_chickenbro_candidate_lighthouse.sh --dry-run [--expected-commit <40-char-sha>]' \
    '  server/deploy_chickenbro_candidate_lighthouse.sh --apply --expected-commit <40-char-sha> --inventory-sha <sha256> --recovery-manifest-sha <sha256>' >&2
}

validate_value() {
  local name="$1"
  local value="$2"
  local pattern="$3"
  [[ "${value}" =~ ${pattern} ]] || die "invalid ${name}"
}

reject_path_traversal() {
  local name="$1"
  local value="$2"
  [[ "${value}" != *".."* ]] || die "invalid ${name}: path traversal is not allowed"
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

directory_sha256() {
  python3 - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
if not root.is_dir():
    raise SystemExit("directory identity input is not a directory")
digest = hashlib.sha256()
files = sorted(path for path in root.rglob("*") if path.is_file())
if not files:
    raise SystemExit("directory identity input is empty")
for path in files:
    if path.is_symlink():
        raise SystemExit("directory identity cannot follow symbolic links")
    relative = path.relative_to(root).as_posix()
    digest.update(relative.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --apply)
      MODE="apply"
      shift
      ;;
    --expected-commit)
      [[ $# -ge 2 ]] || die "--expected-commit requires a value"
      EXPECTED_COMMIT="$2"
      shift 2
      ;;
    --inventory-sha)
      [[ $# -ge 2 ]] || die "--inventory-sha requires a value"
      REVIEWED_INVENTORY_SHA="$2"
      shift 2
      ;;
    --recovery-manifest-sha)
      [[ $# -ge 2 ]] || die "--recovery-manifest-sha requires a value"
      REVIEWED_RECOVERY_MANIFEST_SHA="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      usage
      die "unknown argument"
      ;;
  esac
done

validate_value REMOTE_HOST "${REMOTE_HOST}" '^[A-Za-z0-9_.:-]+$'
validate_value REMOTE_USER "${REMOTE_USER}" '^[A-Za-z_][A-Za-z0-9_.-]*$'
validate_value CANDIDATE_ROOT "${CANDIDATE_ROOT}" '^/[A-Za-z0-9_./-]+$'
validate_value CANDIDATE_DATABASE "${CANDIDATE_DATABASE}" '^chickenbro_candidate$'
validate_value CANDIDATE_PORT "${CANDIDATE_PORT}" '^[0-9]+$'
validate_value CANDIDATE_CODEX_PROFILE "${CANDIDATE_CODEX_PROFILE}" '^/home/[A-Za-z_][A-Za-z0-9_.-]*/\.codex/chickenbro-candidate\.config\.toml$'
validate_value REMOTE_RECOVERY_MANIFEST "${REMOTE_RECOVERY_MANIFEST}" '^/[A-Za-z0-9_./-]+$'
reject_path_traversal CANDIDATE_ROOT "${CANDIDATE_ROOT}"
reject_path_traversal CANDIDATE_CODEX_PROFILE "${CANDIDATE_CODEX_PROFILE}"
reject_path_traversal REMOTE_RECOVERY_MANIFEST "${REMOTE_RECOVERY_MANIFEST}"
[[ "${CANDIDATE_CODEX_PROFILE}" == "/home/${REMOTE_USER}/.codex/chickenbro-candidate.config.toml" ]] \
  || die "candidate Codex profile must belong to the remote service user"

if [[ "${REQUESTED_ASYNC_SYNCS}" != "0" ]]; then
  die "WOW_DEPLOY_START_ASYNC_SYNCS must remain 0 for the clean candidate"
fi
WOW_DEPLOY_START_ASYNC_SYNCS="0"

[[ -f "${INVENTORY_FILE}" ]] || die "cloud inventory is missing"
ACTUAL_INVENTORY_SHA="$(sha256_file "${INVENTORY_FILE}")"
INVENTORY_FACTS="$(python3 - "${INVENTORY_FILE}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(
    payload.get("status", ""),
    payload.get("capacityGate", ""),
    len(payload.get("probeErrors", [])),
    payload.get("observedAt", ""),
    sep="\t",
)
PY
)"
IFS=$'\t' read -r INVENTORY_STATUS CAPACITY_GATE INVENTORY_ERROR_COUNT INVENTORY_OBSERVED_AT <<< "${INVENTORY_FACTS}"

CURRENT_COMMIT="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
validate_value CURRENT_COMMIT "${CURRENT_COMMIT}" '^[0-9a-f]{40}$'
if [[ -n "${EXPECTED_COMMIT}" ]]; then
  validate_value EXPECTED_COMMIT "${EXPECTED_COMMIT}" '^[0-9a-f]{40}$'
  [[ "${CURRENT_COMMIT}" == "${EXPECTED_COMMIT}" ]] || die "EXPECTED_COMMIT does not match git rev-parse HEAD"
fi

if [[ "${MODE}" == "dry-run" ]]; then
  python3 - "${CURRENT_COMMIT}" "${ACTUAL_INVENTORY_SHA}" "${INVENTORY_STATUS}" "${CAPACITY_GATE}" "${INVENTORY_OBSERVED_AT}" <<'PY'
import json
import sys

commit, inventory_sha, status, gate, observed_at = sys.argv[1:]
print(json.dumps({
    "mode": "dry-run",
    "mutationAuthorized": False,
    "branchCommit": commit,
    "inventorySha256": inventory_sha,
    "inventoryStatus": status,
    "capacityGate": gate,
    "inventoryObservedAt": observed_at,
    "candidateRoot": "/opt/chickenbro-candidate",
    "candidateDatabase": "chickenbro_candidate",
    "candidatePort": 8791,
    "candidatePrefix": "/api/v2-candidate",
}, sort_keys=True, separators=(",", ":")))
PY
  exit 0
fi

[[ -n "${EXPECTED_COMMIT}" ]] || die "--apply requires --expected-commit"
[[ -n "${REVIEWED_INVENTORY_SHA}" ]] || die "--apply requires --inventory-sha"
[[ -n "${REVIEWED_RECOVERY_MANIFEST_SHA}" ]] || die "--apply requires --recovery-manifest-sha"
validate_value REVIEWED_INVENTORY_SHA "${REVIEWED_INVENTORY_SHA}" '^[0-9a-f]{64}$'
validate_value REVIEWED_RECOVERY_MANIFEST_SHA "${REVIEWED_RECOVERY_MANIFEST_SHA}" '^[0-9a-f]{64}$'
[[ "${REVIEWED_INVENTORY_SHA}" == "${ACTUAL_INVENTORY_SHA}" ]] || die "inventory SHA does not match reviewed input"
[[ "${INVENTORY_STATUS}" == "reachable" && "${INVENTORY_ERROR_COUNT}" == "0" ]] \
  || die "reviewed inventory is not a clean reachable observation"
[[ "${CAPACITY_GATE}" == "capacity_preflight_required" ]] \
  || die "reviewed inventory does not authorize live candidate preflight"
[[ -z "$(git -C "${REPO_ROOT}" status --porcelain)" ]] \
  || die "tracked worktree must be clean at the exact candidate commit"

for required in \
  server/__init__.py \
  server/app \
  server/codex_worker.py \
  server/migrations/__init__.py \
  server/migrations/product/0001_chickenbro_simc_core.sql \
  server/migrations/product/0002_chat_idempotent_replay.sql \
  server/migrations/product/postgres_legacy.py \
  server/accept_chickenbro_candidate.py \
  server/chickenbro_native_mcp.py \
  server/chickenbro_public_web_research.py \
  server/chickenbro_simc_runtime_update.sh \
  server/chickenbro-simc-runtime-update.service \
  server/chickenbro-api.service \
  server/chickenbro-api-candidate.service \
  server/chickenbro-worker.service \
  server/chickenbro-worker-candidate.service \
  scripts/chickenbro-native-agent/chickenbro-native.config.toml.template \
  server/chickenbro-web.nginx; do
  [[ -e "${REPO_ROOT}/${required}" ]] || die "missing candidate input: ${required}"
done

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

scp_remote() {
  if [[ -n "${WOW_LIGHTHOUSE_PASSWORD:-}" ]]; then
    SSHPASS="${WOW_LIGHTHOUSE_PASSWORD}" sshpass -e scp "${SSH_OPTS[@]}" "$@"
  else
    scp "${SSH_OPTS[@]}" "$@"
  fi
}

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${EXPECTED_COMMIT:0:12}"
REMOTE_ARCHIVE=""

REMOTE_ENV=(
  "REMOTE_USER=${REMOTE_USER}"
  "RUN_ID=${RUN_ID}"
  "EXPECTED_COMMIT=${EXPECTED_COMMIT}"
  "REVIEWED_RECOVERY_MANIFEST_SHA=${REVIEWED_RECOVERY_MANIFEST_SHA}"
  "CANDIDATE_ROOT=${CANDIDATE_ROOT}"
  "CANDIDATE_DATABASE=${CANDIDATE_DATABASE}"
  "CANDIDATE_PORT=${CANDIDATE_PORT}"
  "CANDIDATE_PREFIX=${CANDIDATE_PREFIX}"
  "CANDIDATE_API_SERVICE=${CANDIDATE_API_SERVICE}"
  "CANDIDATE_WORKER_SERVICE=${CANDIDATE_WORKER_SERVICE}"
  "LEGACY_CANDIDATE_SERVICE=${LEGACY_CANDIDATE_SERVICE}"
  "CANDIDATE_API_ENV=${CANDIDATE_API_ENV}"
  "CANDIDATE_SOURCE_ENV=${CANDIDATE_SOURCE_ENV}"
  "CANDIDATE_PGPASSFILE=${CANDIDATE_PGPASSFILE}"
  "CANDIDATE_WORKER_ENV=${CANDIDATE_WORKER_ENV}"
  "CANDIDATE_CODEX_PROFILE=${CANDIDATE_CODEX_PROFILE}"
  "RUNTIME_ROOT=${RUNTIME_ROOT}"
  "EXISTING_RUNTIME_PYTHON=${EXISTING_RUNTIME_PYTHON}"
  "WWW_NGINX_SITE=${WWW_NGINX_SITE}"
  "API_NGINX_SITE=${API_NGINX_SITE}"
  "WEB_ROOT=${WEB_ROOT}"
  "LEGACY_API_ENV=${LEGACY_API_ENV}"
  "LEGACY_SOURCE_ENV=${LEGACY_SOURCE_ENV}"
  "REMOTE_RECOVERY_MANIFEST=${REMOTE_RECOVERY_MANIFEST}"
  "REMOTE_RECOVERY_ROOT=${REMOTE_RECOVERY_ROOT}"
  "REVIEWED_INVENTORY_SHA=${REVIEWED_INVENTORY_SHA}"
  "WOW_DEPLOY_START_ASYNC_SYNCS=${WOW_DEPLOY_START_ASYNC_SYNCS}"
)

remote_env_args() {
  local item
  for item in "${REMOTE_ENV[@]}"; do
    printf '%q ' "${item}"
  done
}

printf 'Running whitelist-recovery and capacity preflight on %s\n' "${SSH_TARGET}"
ssh_remote "$(remote_env_args) sudo -E bash -s" <<'REMOTE_PREFLIGHT'
set -euo pipefail

die_remote() {
  printf 'deploy_chickenbro_candidate remote preflight: %s\n' "$*" >&2
  exit 1
}

for command_name in python3 psql pg_dump pg_restore createdb dropdb nginx systemctl tar sha256sum curl stat df awk grep readlink; do
  command -v "${command_name}" >/dev/null 2>&1 || die_remote "missing command: ${command_name}"
done
LIVE_INSTANCE_ID="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/instance-id)" \
  || die_remote "target identity refresh failed"
LIVE_REGION="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/placement/region)" \
  || die_remote "target identity refresh failed"
LIVE_ZONE="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/placement/zone)" \
  || die_remote "target identity refresh failed"
[[ "${LIVE_INSTANCE_ID}" == "ins-93tgv1rb" && "${LIVE_REGION}" == "ap-shanghai" \
  && "${LIVE_ZONE}" == "ap-shanghai-2" ]] \
  || die_remote "target identity mismatch; refusing candidate apply"
[[ "${WOW_DEPLOY_START_ASYNC_SYNCS}" == "0" ]] || die_remote "WOW_DEPLOY_START_ASYNC_SYNCS must remain 0"
[[ -f "${REMOTE_RECOVERY_MANIFEST}" ]] || die_remote "whitelist recovery manifest is missing"
[[ "$(sha256sum "${REMOTE_RECOVERY_MANIFEST}" | awk '{print $1}')" == "${REVIEWED_RECOVERY_MANIFEST_SHA}" ]] \
  || die_remote "whitelist recovery manifest SHA mismatch"
python3 - "${REMOTE_RECOVERY_MANIFEST}" <<'PY'
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

manifest_path = Path(sys.argv[1])


def fail():
    raise ValueError("whitelist recovery manifest is not restore-verified")


def verified_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        fail()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        fail()
    return parsed


def verified_file(raw_path, root, expected_sha256, expected_bytes=None):
    path = Path(raw_path)
    if not path.is_absolute() or path.is_symlink():
        fail()
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root):
        fail()
    metadata = resolved.stat()
    if expected_bytes is not None and metadata.st_size != expected_bytes:
        fail()
    digest = hashlib.sha256()
    with resolved.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        fail()


try:
    if manifest_path.is_symlink() or manifest_path.stat().st_mode & 0o077:
        fail()
    root = manifest_path.parent.resolve(strict=True)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_keys = {
        "schemaVersion", "status", "targetIdentity", "sourceDatabase", "sourceMode",
        "candidateDatabase", "archivePath", "archiveSha256", "archiveBytes", "createdAt",
        "migrationReport", "restore", "restoreReconciliationSha256",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        fail()
    if payload["schemaVersion"] != "chickenbro-whitelist-recovery-v1" or payload["status"] != "restore_verified":
        fail()
    if payload["targetIdentity"] != {
        "provider": "tencent_cvm",
        "instanceId": "ins-93tgv1rb",
        "region": "ap-shanghai",
        "zone": "ap-shanghai-2",
        "publicAddress": "124.223.51.33",
        "sshTarget": "wow-lighthouse",
    }:
        fail()
    if payload["sourceDatabase"] != "wow_test" or payload["sourceMode"] != "repeatable_read_read_only":
        fail()
    if payload["candidateDatabase"] != "chickenbro_prod":
        fail()
    archive_sha = str(payload["archiveSha256"])
    archive_bytes = payload["archiveBytes"]
    if (
        re.fullmatch(r"[0-9a-f]{64}", archive_sha) is None
        or not isinstance(archive_bytes, int)
        or isinstance(archive_bytes, bool)
        or archive_bytes <= 0
    ):
        fail()
    migration = payload["migrationReport"]
    if (
        not isinstance(migration, dict)
        or set(migration) != {"status", "path", "sha256"}
        or migration["status"] != "matched"
        or re.fullmatch(r"[0-9a-f]{64}", str(migration["sha256"])) is None
    ):
        fail()
    restore = payload["restore"]
    restore_keys = {
        "targetDatabase", "commandExitCode", "reconciliationStatus", "verifiedAt",
        "evidencePath", "evidenceSha256",
    }
    if not isinstance(restore, dict) or set(restore) != restore_keys:
        fail()
    if re.fullmatch(r"chickenbro_restore_verify_[a-z0-9_]{1,40}", str(restore["targetDatabase"])) is None:
        fail()
    if (
        restore["commandExitCode"] != 0
        or restore["reconciliationStatus"] != "matched"
    ):
        fail()
    created_at = verified_timestamp(payload["createdAt"])
    verified_at = verified_timestamp(restore["verifiedAt"])
    if verified_at < created_at:
        fail()
    evidence_sha = str(restore["evidenceSha256"])
    if re.fullmatch(r"[0-9a-f]{64}", evidence_sha) is None:
        fail()
    if payload["restoreReconciliationSha256"] != evidence_sha:
        fail()
    verified_file(payload["archivePath"], root, archive_sha, archive_bytes)
    verified_file(migration["path"], root, migration["sha256"])
    verified_file(restore["evidencePath"], root, evidence_sha)
except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
    raise SystemExit("whitelist recovery manifest is not restore-verified") from error
PY
[[ -f "${LEGACY_API_ENV}" && "$(stat -c '%a' "${LEGACY_API_ENV}")" == "600" ]] \
  || die_remote "legacy API secret source is missing or not mode 0600"
[[ -f "${LEGACY_SOURCE_ENV}" && "$(stat -c '%a' "${LEGACY_SOURCE_ENV}")" == "600" ]] \
  || die_remote "legacy source credential file is missing or not mode 0600"
[[ -x "${EXISTING_RUNTIME_PYTHON}" ]] || die_remote "managed Python runtime is missing"
sudo -n -u "${REMOTE_USER}" "${EXISTING_RUNTIME_PYTHON}" -c \
  'import fastapi, httpx, psycopg, uvicorn' \
  || die_remote "managed Python runtime dependencies are incomplete"
[[ -x /opt/wow-simc/current/simc ]] || die_remote "managed SimulationCraft runtime is missing"
[[ -x /usr/local/bin/codex ]] || die_remote "managed Codex runtime is missing"
/usr/local/bin/codex exec --help | grep -q -- '--ephemeral' \
  || die_remote "managed Codex runtime does not support ephemeral execution"
[[ -f "${WWW_NGINX_SITE}" && -f "${API_NGINX_SITE}" ]] || die_remote "existing Nginx owners are missing"
WWW_NGINX_OWNER="$(readlink -f -- "${WWW_NGINX_SITE}")"
API_NGINX_OWNER="$(readlink -f -- "${API_NGINX_SITE}")"
[[ "${WWW_NGINX_OWNER}" == /etc/nginx/sites-available/* ]] \
  || die_remote "WWW Nginx owner is outside sites-available"
[[ "${API_NGINX_OWNER}" == /etc/nginx/sites-available/* ]] \
  || die_remote "API Nginx owner is outside sites-available"
grep -Eq 'server_name[[:space:]]+www\.chickenbro\.cloud' "${WWW_NGINX_OWNER}" \
  || die_remote "WWW Nginx owner is not the expected host"
grep -Eq 'server_name[[:space:]]+api\.chickenbro\.cloud' "${API_NGINX_OWNER}" \
  || die_remote "API Nginx owner is not the expected host"
grep -Eq 'location[[:space:]]+\^~[[:space:]]+/api/v2/' "${WWW_NGINX_OWNER}" \
  || die_remote "existing WWW production API route is missing"

set +u
set -a
. "${LEGACY_API_ENV}"
set +a
set -u
[[ -n "${WOW_DATABASE_URL:-}" ]] || die_remote "legacy source DSN is missing"
[[ -n "${PGPASSFILE:-}" && -f "${PGPASSFILE}" && "$(stat -c '%a' "${PGPASSFILE}")" == "600" ]] \
  || die_remote "legacy application PGPASSFILE is missing or not mode 0600"
python3 - <<'PY'
import os
from urllib.parse import unquote, urlsplit

try:
    parsed = urlsplit(os.environ["WOW_DATABASE_URL"])
    valid = (
        parsed.scheme in {"postgres", "postgresql"}
        and parsed.username == "wow_app"
        and parsed.password is None
        and parsed.hostname == "127.0.0.1"
        and parsed.port == 5432
        and unquote(parsed.path.lstrip("/")) == "wow_test"
        and not parsed.query
        and not parsed.fragment
    )
except (KeyError, ValueError):
    valid = False
if not valid:
    raise SystemExit("legacy DSN is not the reviewed local wow_app identity")
PY
sudo -n -u "${REMOTE_USER}" test -r "${PGPASSFILE}" \
  || die_remote "legacy application PGPASSFILE is not readable by the runtime user"
grep -Eq '^127\.0\.0\.1:5432:wow_test:wow_app:' "${PGPASSFILE}" \
  || die_remote "legacy application PGPASSFILE has no reviewed wow_test wow_app entry"
CURRENT_DATABASE="$(sudo -n -u "${REMOTE_USER}" --preserve-env=PGPASSFILE \
  psql -At --host=127.0.0.1 --port=5432 --username=wow_app --dbname=wow_test \
  --command='SELECT current_database()')"
[[ "${CURRENT_DATABASE}" == "wow_test" ]] || die_remote "legacy source DSN does not resolve to wow_test"
ROLE_COUNT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT count(*) FROM pg_roles WHERE rolname IN ('wow_app', 'wow_migrator')")"
[[ "${ROLE_COUNT}" == "2" ]] || die_remote "required PostgreSQL roles are missing"
unset WOW_DATABASE_URL WOW_WECHAT_SECRET

SOURCE_BYTES="$(sudo -n -u postgres psql -At --dbname=postgres --command="SELECT pg_database_size('wow_test')")"
ROOT_FREE_BYTES="$(df -PB1 --output=avail /var/lib/postgresql | tail -n 1 | tr -d '[:space:]')"
WHITELIST_ARCHIVE_BYTES="$(python3 - "${REMOTE_RECOVERY_MANIFEST}" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["archiveBytes"])
PY
)"
for value in "${SOURCE_BYTES}" "${ROOT_FREE_BYTES}" "${WHITELIST_ARCHIVE_BYTES}"; do
  [[ "${value}" =~ ^[0-9]+$ ]] || die_remote "capacity probe returned an invalid value"
done
REQUIRED_ROOT=$(( WHITELIST_ARCHIVE_BYTES * 3 + 2147483648 ))
(( ROOT_FREE_BYTES >= REQUIRED_ROOT )) || die_remote "PostgreSQL device capacity is insufficient"
printf 'preflight=ready sourceBytes=%s whitelistArchiveBytes=%s rootFreeBytes=%s\n' \
  "${SOURCE_BYTES}" "${WHITELIST_ARCHIVE_BYTES}" "${ROOT_FREE_BYTES}"
REMOTE_PREFLIGHT

printf 'Building the exact candidate H5 and WeApp for %s\n' "${EXPECTED_COMMIT}"
(
  cd "${REPO_ROOT}"
  NODE_ENV=production \
  WOW_BACKEND_API_BASE_URL="https://api.chickenbro.cloud" \
  WOW_API_V2_PREFIX="${CANDIDATE_PREFIX}" \
  WOW_WEB_AUTH_API_PREFIX="${CANDIDATE_PREFIX}" \
  WOW_WEB_CSRF_COOKIE_NAME="__Host-chickenbro-candidate-csrf" \
  WOW_H5_PUBLIC_PATH="/web-candidate/" \
  npm --workspace @wow-mini/mini-taro run build:h5
)
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/h5/index.html" ]] || die "candidate H5 build is missing index.html"
(
  cd "${REPO_ROOT}"
  NODE_ENV=production \
  WOW_BACKEND_API_BASE_URL="https://api.chickenbro.cloud" \
  WOW_API_V2_PREFIX="${CANDIDATE_PREFIX}" \
  WOW_WEB_AUTH_API_PREFIX="${CANDIDATE_PREFIX}" \
  WOW_WEB_CSRF_COOKIE_NAME="__Host-chickenbro-candidate-csrf" \
  npm --workspace @wow-mini/mini-taro run build:weapp
)
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/weapp/app.json" ]] || die "candidate WeApp build is missing app.json"
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/weapp/wow-build.json" ]] || die "candidate WeApp build identity is missing"
python3 - "${REPO_ROOT}/apps/mini-taro/dist/weapp/wow-build.json" "${EXPECTED_COMMIT}" <<'PY'
import json
import re
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("schemaRevision") != "wow-weapp-build-v1":
    raise SystemExit("WeApp wow-build schema mismatch")
if payload.get("gitHead") != sys.argv[2]:
    raise SystemExit("WeApp wow-build gitHead mismatch")
if re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload.get("sourceHash", ""))) is None:
    raise SystemExit("WeApp wow-build source hash is invalid")
PY
WEB_BUILD_IDENTITY="$(directory_sha256 "${REPO_ROOT}/apps/mini-taro/dist/h5")"
WEAPP_BUILD_IDENTITY="$(directory_sha256 "${REPO_ROOT}/apps/mini-taro/dist/weapp")"
validate_value WEB_BUILD_IDENTITY "${WEB_BUILD_IDENTITY}" '^[0-9a-f]{64}$'
validate_value WEAPP_BUILD_IDENTITY "${WEAPP_BUILD_IDENTITY}" '^[0-9a-f]{64}$'

LOCAL_STAGE="$(mktemp -d -t chickenbro-candidate-stage.XXXXXX)"
LOCAL_PACKAGE_DIR="$(mktemp -d -t chickenbro-candidate-package.XXXXXX)"
SOURCE_ARCHIVE=""
cleanup_local() {
  local exit_code=$?
  rm -rf "${LOCAL_STAGE}" "${LOCAL_PACKAGE_DIR}"
  exit "${exit_code}"
}
trap cleanup_local EXIT

git -C "${REPO_ROOT}" archive "${EXPECTED_COMMIT}" -- \
  server/__init__.py \
  server/app \
  server/codex_worker.py \
  server/accept_chickenbro_candidate.py \
  server/chickenbro_native_mcp.py \
  server/chickenbro_public_web_research.py \
  server/chickenbro_simc_runtime_update.sh \
  server/chickenbro-simc-runtime-update.service \
  server/migrations/__init__.py \
  server/migrations/product \
  server/chickenbro-api.service \
  server/chickenbro-api-candidate.service \
  server/chickenbro-worker.service \
  server/chickenbro-worker-candidate.service \
  scripts/chickenbro-native-agent/chickenbro-native.config.toml.template \
  server/chickenbro-web.nginx | tar -xf - -C "${LOCAL_STAGE}"
mkdir -p "${LOCAL_STAGE}/apps/mini-taro/dist"
cp -R "${REPO_ROOT}/apps/mini-taro/dist/h5" "${LOCAL_STAGE}/apps/mini-taro/dist/h5"
cp -R "${REPO_ROOT}/apps/mini-taro/dist/weapp" "${LOCAL_STAGE}/apps/mini-taro/dist/weapp"
printf '%s\n' "${EXPECTED_COMMIT}" > "${LOCAL_STAGE}/BRANCH_COMMIT"
printf '%s\n' "${WEB_BUILD_IDENTITY}" > "${LOCAL_STAGE}/WEB_BUILD_IDENTITY"
printf '%s\n' "${WEAPP_BUILD_IDENTITY}" > "${LOCAL_STAGE}/WEAPP_BUILD_IDENTITY"

python3 - "${LOCAL_STAGE}" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = root / "deploy-manifest.sha256"
lines = []
for path in sorted(item for item in root.rglob("*") if item.is_file() and item != manifest):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    relative = path.relative_to(root).as_posix()
    if "\n" in relative or "\r" in relative:
        raise SystemExit("unsafe deployment path")
    lines.append(f"{digest}  {relative}")
descriptor = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    output.write("\n".join(lines) + "\n")
PY

SOURCE_MANIFEST_SHA256="$(sha256_file "${LOCAL_STAGE}/deploy-manifest.sha256")"
TEMP_ARCHIVE="${LOCAL_PACKAGE_DIR}/candidate.tar.gz"
COPYFILE_DISABLE=1 tar --format=ustar -czf "${TEMP_ARCHIVE}" -C "${LOCAL_STAGE}" .
SOURCE_ARCHIVE_SHA256="$(sha256_file "${TEMP_ARCHIVE}")"
SOURCE_ARCHIVE="${LOCAL_PACKAGE_DIR}/chickenbro-candidate-${SOURCE_ARCHIVE_SHA256}.tar.gz"
mv "${TEMP_ARCHIVE}" "${SOURCE_ARCHIVE}"
REMOTE_ARCHIVE="/tmp/chickenbro-candidate-${SOURCE_ARCHIVE_SHA256}.tar.gz"
scp_remote "${SOURCE_ARCHIVE}" "${SSH_TARGET}:${REMOTE_ARCHIVE}"

REMOTE_ENV+=(
  "SOURCE_ARCHIVE_SHA256=${SOURCE_ARCHIVE_SHA256}"
  "SOURCE_MANIFEST_SHA256=${SOURCE_MANIFEST_SHA256}"
  "REMOTE_ARCHIVE=${REMOTE_ARCHIVE}"
  "WEB_BUILD_IDENTITY=${WEB_BUILD_IDENTITY}"
  "WEAPP_BUILD_IDENTITY=${WEAPP_BUILD_IDENTITY}"
)

printf 'Installing isolated candidate archive %s\n' "${SOURCE_ARCHIVE_SHA256}"
ssh_remote "$(remote_env_args) sudo -E bash -s" <<'REMOTE_DEPLOY'
set -euo pipefail

die_remote() {
  printf 'deploy_chickenbro_candidate remote: %s\n' "$*" >&2
  exit 1
}

BACKUP_DIR="${REMOTE_RECOVERY_ROOT}/${RUN_ID}"
STAGE_DIR="/opt/chickenbro-candidate-staging/${RUN_ID}"
CODE_NEW_DIR="${CANDIDATE_ROOT}.new-${RUN_ID}"
WWW_NGINX_OWNER="$(readlink -f -- "${WWW_NGINX_SITE}")"
API_NGINX_OWNER="$(readlink -f -- "${API_NGINX_SITE}")"
WEB_RELEASE_DIR="${WEB_ROOT}/releases/${SOURCE_MANIFEST_SHA256}"
WEB_CURRENT_LINK="${WEB_ROOT}/current"
MIGRATION_REPORT="${BACKUP_DIR}/migration-report.json"
MIGRATION_REPORT_TMP="/var/lib/chickenbro/candidate-migration-${RUN_ID}.json"
AUTOMATED_ACCEPTANCE_REPORT="${BACKUP_DIR}/automated-acceptance.json"
AUTOMATED_ACCEPTANCE_TMP="/var/lib/chickenbro/automated-acceptance-${RUN_ID}.json"
READINESS_SUMMARY="${BACKUP_DIR}/readiness-summary.json"
ACCEPTANCE_REPORT="${BACKUP_DIR}/candidate-acceptance.json"
ROLLBACK_MANIFEST="${BACKUP_DIR}/rollback-manifest.sha256"
PREVIOUS_DATABASE="absent"
MUTATION_STARTED="0"

service_state() {
  systemctl is-active --quiet "$1" && printf 'active\n' || printf 'inactive\n'
}

enable_state() {
  systemctl is-enabled --quiet "$1" && printf 'enabled\n' || printf 'disabled\n'
}

restore_file() {
  local backup="$1"
  local state="$2"
  local destination="$3"
  if [[ "$(<"${state}")" == "present" ]]; then
    cp --preserve=mode,ownership "${backup}" "${destination}"
  else
    rm -f "${destination}"
  fi
}

rollback_candidate() {
  local exit_code=$?
  if [[ "${exit_code}" -eq 0 ]]; then
    rm -f "${REMOTE_ARCHIVE}"
    rm -rf "${STAGE_DIR}" "${CODE_NEW_DIR}"
    exit 0
  fi
  set +e
  if [[ "${MUTATION_STARTED}" == "1" ]]; then
    systemctl stop "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
    if [[ -d "${CANDIDATE_ROOT}" ]]; then
      mv "${CANDIDATE_ROOT}" "${BACKUP_DIR}/failed-candidate-root"
    fi
    if [[ -s "${BACKUP_DIR}/candidate-root.tar.gz" ]]; then
      mkdir -p "${CANDIDATE_ROOT}"
      tar -xzf "${BACKUP_DIR}/candidate-root.tar.gz" -C "${CANDIDATE_ROOT}"
    fi
    restore_file "${BACKUP_DIR}/candidate-api.service" "${BACKUP_DIR}/candidate-api.service.state" "/etc/systemd/system/${CANDIDATE_API_SERVICE}.service"
    restore_file "${BACKUP_DIR}/worker.service" "${BACKUP_DIR}/worker.service.state" "/etc/systemd/system/${CANDIDATE_WORKER_SERVICE}.service"
    restore_file "${BACKUP_DIR}/candidate-api.env" "${BACKUP_DIR}/candidate-api.env.state" "${CANDIDATE_API_ENV}"
    restore_file "${BACKUP_DIR}/candidate-source.env" "${BACKUP_DIR}/candidate-source.env.state" "${CANDIDATE_SOURCE_ENV}"
    restore_file "${BACKUP_DIR}/candidate.pgpass" "${BACKUP_DIR}/candidate.pgpass.state" "${CANDIDATE_PGPASSFILE}"
    restore_file "${BACKUP_DIR}/worker.env" "${BACKUP_DIR}/worker.env.state" "${CANDIDATE_WORKER_ENV}"
    restore_file "${BACKUP_DIR}/candidate-codex-profile" "${BACKUP_DIR}/candidate-codex-profile.state" "${CANDIDATE_CODEX_PROFILE}"
    cp --preserve=mode,ownership "${BACKUP_DIR}/www.nginx" "${WWW_NGINX_OWNER}"
    cp --preserve=mode,ownership "${BACKUP_DIR}/api.nginx" "${API_NGINX_OWNER}"
    if [[ "$(<"${BACKUP_DIR}/web-current.state")" == "present" ]]; then
      ln -sfn "$(<"${BACKUP_DIR}/web-current.target")" "${WEB_CURRENT_LINK}"
    else
      rm -f "${WEB_CURRENT_LINK}"
    fi
    rm -f "${WEB_CURRENT_LINK}.new"
    rm -rf "${WEB_RELEASE_DIR}"
    if [[ "$(<"${BACKUP_DIR}/runtime-root.state")" == "absent" ]]; then
      rm -rf "${RUNTIME_ROOT}"
    fi
    sudo -n -u postgres psql --dbname=postgres --set=ON_ERROR_STOP=1 \
      --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${CANDIDATE_DATABASE}' AND pid <> pg_backend_pid()" >/dev/null
    sudo -n -u postgres dropdb --if-exists "${CANDIDATE_DATABASE}" >/dev/null 2>&1 || true
    if [[ "${PREVIOUS_DATABASE}" == "present" && -s "${BACKUP_DIR}/candidate-database.dump" ]]; then
      sudo -n -u postgres createdb --owner=wow_migrator --template=template0 --encoding=UTF8 "${CANDIDATE_DATABASE}"
      sudo -n -u postgres pg_restore --exit-on-error --dbname="${CANDIDATE_DATABASE}" "${BACKUP_DIR}/candidate-database.dump"
    fi
    systemctl daemon-reload
    if [[ "$(<"${BACKUP_DIR}/candidate-api.enabled")" == "enabled" ]]; then
      systemctl enable "${CANDIDATE_API_SERVICE}" >/dev/null 2>&1 || true
    else
      systemctl disable "${CANDIDATE_API_SERVICE}" >/dev/null 2>&1 || true
    fi
    if [[ "$(<"${BACKUP_DIR}/worker.enabled")" == "enabled" ]]; then
      systemctl enable "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
    else
      systemctl disable "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
    fi
    if [[ "$(<"${BACKUP_DIR}/legacy-candidate.present")" == "present" ]]; then
      systemctl unmask --runtime "${LEGACY_CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
      if [[ "$(<"${BACKUP_DIR}/legacy-candidate.enabled")" == "enabled" ]]; then
        systemctl enable "${LEGACY_CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
      else
        systemctl disable "${LEGACY_CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
      fi
    fi
    nginx -t >/dev/null && systemctl reload nginx >/dev/null 2>&1
    if [[ "$(<"${BACKUP_DIR}/candidate-api.active")" == "active" ]]; then
      systemctl start "${CANDIDATE_API_SERVICE}" >/dev/null 2>&1
    fi
    if [[ "$(<"${BACKUP_DIR}/worker.active")" == "active" ]]; then
      systemctl start "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1
    fi
    if [[ "$(<"${BACKUP_DIR}/legacy-candidate.present")" == "present" \
      && "$(<"${BACKUP_DIR}/legacy-candidate.active")" == "active" ]]; then
      systemctl start "${LEGACY_CANDIDATE_SERVICE}" >/dev/null 2>&1
    fi
    printf '%s\n' 'rollback_attempted_requires_operator_verification' > "${BACKUP_DIR}/ROLLBACK_STATE"
  fi
  rm -f "${MIGRATION_REPORT_TMP}" "${AUTOMATED_ACCEPTANCE_TMP}"
  rm -f "${CANDIDATE_CODEX_PROFILE}.new-${RUN_ID}"
  rm -f "${REMOTE_ARCHIVE}"
  rm -rf "${STAGE_DIR}" "${CODE_NEW_DIR}"
  exit "${exit_code}"
}
trap rollback_candidate EXIT

[[ "$(sha256sum "${REMOTE_ARCHIVE}" | awk '{print $1}')" == "${SOURCE_ARCHIVE_SHA256}" ]] \
  || die_remote "source archive hash mismatch"
[[ ! -e "${BACKUP_DIR}" ]] || die_remote "candidate run already exists"
install -d -o root -g root -m 0700 "${BACKUP_DIR}"
install -d -o root -g root -m 0755 "${STAGE_DIR}"
tar -xzf "${REMOTE_ARCHIVE}" -C "${STAGE_DIR}"
[[ "$(sha256sum "${STAGE_DIR}/deploy-manifest.sha256" | awk '{print $1}')" == "${SOURCE_MANIFEST_SHA256}" ]] \
  || die_remote "source manifest hash mismatch"
(
  cd "${STAGE_DIR}"
  sha256sum --check deploy-manifest.sha256 >/dev/null
)
[[ "$(<"${STAGE_DIR}/BRANCH_COMMIT")" == "${EXPECTED_COMMIT}" ]] || die_remote "branch commit mismatch"
[[ "$(<"${STAGE_DIR}/WEB_BUILD_IDENTITY")" == "${WEB_BUILD_IDENTITY}" ]] \
  || die_remote "Web build identity metadata mismatch"
[[ "$(<"${STAGE_DIR}/WEAPP_BUILD_IDENTITY")" == "${WEAPP_BUILD_IDENTITY}" ]] \
  || die_remote "WeApp build identity metadata mismatch"

for pair in \
  "/etc/systemd/system/${CANDIDATE_API_SERVICE}.service:candidate-api.service" \
  "/etc/systemd/system/${CANDIDATE_WORKER_SERVICE}.service:worker.service" \
  "${CANDIDATE_API_ENV}:candidate-api.env" \
  "${CANDIDATE_SOURCE_ENV}:candidate-source.env" \
  "${CANDIDATE_PGPASSFILE}:candidate.pgpass" \
  "${CANDIDATE_WORKER_ENV}:worker.env" \
  "${CANDIDATE_CODEX_PROFILE}:candidate-codex-profile"; do
  source_path="${pair%%:*}"
  backup_name="${pair#*:}"
  if [[ -f "${source_path}" ]]; then
    cp --preserve=mode,ownership "${source_path}" "${BACKUP_DIR}/${backup_name}"
    printf '%s\n' present > "${BACKUP_DIR}/${backup_name}.state"
  else
    printf '%s\n' absent > "${BACKUP_DIR}/${backup_name}.state"
  fi
done
cp --preserve=mode,ownership "${WWW_NGINX_OWNER}" "${BACKUP_DIR}/www.nginx"
cp --preserve=mode,ownership "${API_NGINX_OWNER}" "${BACKUP_DIR}/api.nginx"
service_state "${CANDIDATE_API_SERVICE}" > "${BACKUP_DIR}/candidate-api.active"
service_state "${CANDIDATE_WORKER_SERVICE}" > "${BACKUP_DIR}/worker.active"
enable_state "${CANDIDATE_API_SERVICE}" > "${BACKUP_DIR}/candidate-api.enabled"
enable_state "${CANDIDATE_WORKER_SERVICE}" > "${BACKUP_DIR}/worker.enabled"
if [[ "$(systemctl show "${LEGACY_CANDIDATE_SERVICE}" --property=LoadState --value)" == "not-found" ]]; then
  printf '%s\n' absent > "${BACKUP_DIR}/legacy-candidate.present"
  printf '%s\n' inactive > "${BACKUP_DIR}/legacy-candidate.active"
  printf '%s\n' disabled > "${BACKUP_DIR}/legacy-candidate.enabled"
else
  printf '%s\n' present > "${BACKUP_DIR}/legacy-candidate.present"
  service_state "${LEGACY_CANDIDATE_SERVICE}" > "${BACKUP_DIR}/legacy-candidate.active"
  enable_state "${LEGACY_CANDIDATE_SERVICE}" > "${BACKUP_DIR}/legacy-candidate.enabled"
fi
if [[ -d "${CANDIDATE_ROOT}" ]]; then
  tar --format=posix -czf "${BACKUP_DIR}/candidate-root.tar.gz" -C "${CANDIDATE_ROOT}" .
else
  : > "${BACKUP_DIR}/candidate-root.tar.gz"
fi
if [[ -L "${WEB_CURRENT_LINK}" ]]; then
  readlink "${WEB_CURRENT_LINK}" > "${BACKUP_DIR}/web-current.target"
  printf '%s\n' present > "${BACKUP_DIR}/web-current.state"
elif [[ -e "${WEB_CURRENT_LINK}" ]]; then
  die_remote "candidate Web current is not a symlink"
else
  printf '%s\n' absent > "${BACKUP_DIR}/web-current.state"
fi
if [[ -e "${RUNTIME_ROOT}" ]]; then
  printf '%s\n' present > "${BACKUP_DIR}/runtime-root.state"
else
  printf '%s\n' absent > "${BACKUP_DIR}/runtime-root.state"
fi
[[ ! -e "${WEB_RELEASE_DIR}" ]] || die_remote "content-addressed candidate Web release already exists"
[[ ! -e "${CODE_NEW_DIR}" ]] || die_remote "candidate code staging target already exists"

if sudo -n -u postgres psql -At --dbname=postgres --command="SELECT 1 FROM pg_database WHERE datname = '${CANDIDATE_DATABASE}'" | grep -qx 1; then
  PREVIOUS_DATABASE="present"
  sudo -n -u postgres pg_dump --format=custom --dbname="${CANDIDATE_DATABASE}" > "${BACKUP_DIR}/candidate-database.dump"
  chmod 0600 "${BACKUP_DIR}/candidate-database.dump"
  pg_restore --list "${BACKUP_DIR}/candidate-database.dump" > "${BACKUP_DIR}/candidate-database.restore-list"
else
  PREVIOUS_DATABASE="absent"
  : > "${BACKUP_DIR}/candidate-database.dump"
  : > "${BACKUP_DIR}/candidate-database.restore-list"
fi
printf '%s\n' "${PREVIOUS_DATABASE}" > "${BACKUP_DIR}/candidate-database.state"
printf '%s\n' backup_complete > "${BACKUP_DIR}/READY"
MUTATION_STARTED="1"

if [[ "$(<"${BACKUP_DIR}/legacy-candidate.present")" == "present" ]]; then
  systemctl stop "${LEGACY_CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
  systemctl disable "${LEGACY_CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
  systemctl mask --runtime "${LEGACY_CANDIDATE_SERVICE}" >/dev/null
fi
systemctl stop "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
install -d -o root -g root -m 0755 "$(dirname "${CODE_NEW_DIR}")"
cp -a "${STAGE_DIR}" "${CODE_NEW_DIR}"
if [[ -d "${CANDIDATE_ROOT}" ]]; then
  mv "${CANDIDATE_ROOT}" "${BACKUP_DIR}/candidate-root.previous"
fi
mv "${CODE_NEW_DIR}" "${CANDIDATE_ROOT}"
chown -R root:root "${CANDIDATE_ROOT}"
find "${CANDIDATE_ROOT}" -type d -exec chmod 0755 {} +
find "${CANDIDATE_ROOT}" -type f -exec chmod 0644 {} +
chmod 0600 "${CANDIDATE_ROOT}/deploy-manifest.sha256"
(
  cd "${CANDIDATE_ROOT}"
  sha256sum --check deploy-manifest.sha256 >/dev/null
)
DEPLOYED_MANIFEST_SHA256="$(sha256sum "${CANDIDATE_ROOT}/deploy-manifest.sha256" | awk '{print $1}')"
[[ "${DEPLOYED_MANIFEST_SHA256}" == "${SOURCE_MANIFEST_SHA256}" ]] || die_remote "deployed manifest parity failed"

if [[ ! -e "${RUNTIME_ROOT}" ]]; then
  install -d -o root -g root -m 0755 "${RUNTIME_ROOT}/bin"
  ln -s "${EXISTING_RUNTIME_PYTHON}" "${RUNTIME_ROOT}/bin/python"
fi
[[ -x "${RUNTIME_ROOT}/bin/python" ]] || die_remote "Chickenbro runtime Python is unavailable"
install -d -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0700 \
  /var/lib/chickenbro /var/lib/chickenbro/codex-jobs /var/lib/chickenbro/candidate-codex-jobs

set +u
set -a
. "${LEGACY_API_ENV}"
set +a
set -u
LEGACY_DATABASE_URL="${WOW_DATABASE_URL:-}"
LEGACY_PGPASSFILE="${PGPASSFILE:-}"
CODEX_RUNTIME_IDENTITY="$(sha256sum /usr/local/bin/codex | awk '{print $1}')"
[[ -n "${LEGACY_DATABASE_URL}" ]] || die_remote "legacy source DSN is missing"
[[ -n "${WOW_WECHAT_APPID:-}" && -n "${WOW_WECHAT_SECRET:-}" ]] || die_remote "formal WeChat credentials are missing"
[[ "${WOW_WECHAT_APPID}" =~ ^[A-Za-z0-9_-]{1,128}$ ]] || die_remote "formal WeChat AppID is invalid"
[[ "${WOW_WECHAT_SECRET}" =~ ^[A-Za-z0-9_-]{1,256}$ ]] || die_remote "formal WeChat secret is invalid"

export LEGACY_DATABASE_URL LEGACY_PGPASSFILE CANDIDATE_DATABASE CANDIDATE_API_ENV CANDIDATE_PGPASSFILE CANDIDATE_WORKER_ENV REMOTE_USER
export CODEX_RUNTIME_IDENTITY
export WOW_WECHAT_APPID WOW_WECHAT_SECRET
PGPASS_TMP="$(mktemp)"
if ! awk -F: -v candidate_database="${CANDIDATE_DATABASE}" '
  BEGIN { OFS = FS }
  $1 == "127.0.0.1" && $2 == "5432" && $3 == "wow_test" && $4 == "wow_app" {
    print
    $3 = candidate_database
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
' "${LEGACY_PGPASSFILE}" > "${PGPASS_TMP}"; then
  rm -f "${PGPASS_TMP}"
  die_remote "legacy application PGPASSFILE has no usable wow_test wow_app entry"
fi
install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${PGPASS_TMP}" "${CANDIDATE_PGPASSFILE}"
rm -f "${PGPASS_TMP}"
"${RUNTIME_ROOT}/bin/python" - <<'PY'
import os
from pathlib import Path
from urllib.parse import urlsplit

legacy = os.environ["LEGACY_DATABASE_URL"]
parsed = urlsplit(legacy)
try:
    valid = (
        parsed.scheme in {"postgres", "postgresql"}
        and parsed.username == "wow_app"
        and parsed.password is None
        and parsed.hostname == "127.0.0.1"
        and parsed.port == 5432
        and parsed.path.lstrip("/") == "wow_test"
        and not parsed.query
        and not parsed.fragment
    )
except ValueError:
    valid = False
if not valid:
    raise SystemExit("legacy DSN is not the reviewed local wow_app identity")
target = f"postgresql://wow_app@127.0.0.1:5432/{os.environ['CANDIDATE_DATABASE']}"

api_lines = [
    f"WOW_DATABASE_URL={target}",
    f"WOW_WECHAT_APPID={os.environ['WOW_WECHAT_APPID']}",
    f"WOW_WECHAT_SECRET={os.environ['WOW_WECHAT_SECRET']}",
    f"WOW_CODEX_RUNTIME_REVISION=codex:sha256:{os.environ['CODEX_RUNTIME_IDENTITY']}",
]
pgpass = os.environ["CANDIDATE_PGPASSFILE"]
api_lines.append(f"PGPASSFILE={pgpass}")
Path(os.environ["CANDIDATE_API_ENV"]).write_text("\n".join(api_lines) + "\n", encoding="utf-8")
Path(os.environ["CANDIDATE_WORKER_ENV"]).write_text("\n".join([
    f"WOW_DATABASE_URL={target}",
    "WOW_APP_ENV=candidate",
    "PYTHONPATH=/opt/chickenbro-candidate",
    f"PGPASSFILE={pgpass}",
]) + "\n", encoding="utf-8")
PY
chown root:root "${CANDIDATE_API_ENV}" "${CANDIDATE_WORKER_ENV}"
chmod 0600 "${CANDIDATE_API_ENV}" "${CANDIDATE_WORKER_ENV}"
if [[ -f "${LEGACY_SOURCE_ENV}" ]]; then
  install -o root -g root -m 0600 "${LEGACY_SOURCE_ENV}" "${CANDIDATE_SOURCE_ENV}"
else
  install -o root -g root -m 0600 /dev/null "${CANDIDATE_SOURCE_ENV}"
fi

sudo -n -u postgres psql --dbname=postgres --set=ON_ERROR_STOP=1 \
  --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${CANDIDATE_DATABASE}' AND pid <> pg_backend_pid()" >/dev/null
sudo -n -u postgres dropdb --if-exists "${CANDIDATE_DATABASE}"
sudo -n -u postgres createdb --owner=wow_migrator --template=template0 --encoding=UTF8 "${CANDIDATE_DATABASE}"
for migration in \
  "${CANDIDATE_ROOT}/server/migrations/product/0001_chickenbro_simc_core.sql" \
  "${CANDIDATE_ROOT}/server/migrations/product/0002_chat_idempotent_replay.sql"; do
  sudo -n -u postgres psql --no-psqlrc --dbname="${CANDIDATE_DATABASE}" --set=ON_ERROR_STOP=1 \
    --single-transaction --file="${migration}" >/dev/null
done

set -a
. "${CANDIDATE_API_ENV}"
set +a
CANDIDATE_DATABASE_URL="${WOW_DATABASE_URL}"
export CHICKENBRO_LEGACY_SOURCE_DATABASE_URL="${LEGACY_DATABASE_URL}"
export WOW_DATABASE_URL="${CANDIDATE_DATABASE_URL}"
export WOW_MIGRATION_WECHAT_APP_CONTEXT="${WOW_WECHAT_APPID}"
export PYTHONPATH="${CANDIDATE_ROOT}"
rm -f "${MIGRATION_REPORT_TMP}"
# captured-watermark is acquired inside the repeatable-read read-only source transaction.
sudo -n -u "${REMOTE_USER}" --preserve-env=CHICKENBRO_LEGACY_SOURCE_DATABASE_URL,WOW_DATABASE_URL,WOW_MIGRATION_WECHAT_APP_CONTEXT,PGPASSFILE,PYTHONPATH \
  "${RUNTIME_ROOT}/bin/python" -m server.migrations.product.postgres_legacy \
  --mode full \
  --expected-source-database wow_test \
  --expected-target-database "${CANDIDATE_DATABASE}" \
  --report-path "${MIGRATION_REPORT_TMP}"
install -o root -g root -m 0600 "${MIGRATION_REPORT_TMP}" "${MIGRATION_REPORT}"
rm -f "${MIGRATION_REPORT_TMP}"
python3 - "${MIGRATION_REPORT}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("reconciliation", {}).get("status") != "matched":  # reconciliation must be matched
    raise SystemExit("candidate migration reconciliation is not matched")
PY

CODEX_PROFILE_TEMPLATE="${CANDIDATE_ROOT}/scripts/chickenbro-native-agent/chickenbro-native.config.toml.template"
CODEX_PROFILE_NEW="${CANDIDATE_CODEX_PROFILE}.new-${RUN_ID}"
[[ -f "${CODEX_PROFILE_TEMPLATE}" ]] || die_remote "candidate Codex profile template is missing"
install -d -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0700 "$(dirname -- "${CANDIDATE_CODEX_PROFILE}")"
python3 - "${CODEX_PROFILE_TEMPLATE}" "${CANDIDATE_ROOT}" "${CODEX_PROFILE_NEW}" <<'PY'
import os
import sys
from pathlib import Path

template_path, runtime_root, output_path = map(Path, sys.argv[1:])
source = template_path.read_text(encoding="utf-8")
placeholder = "__CHICKENBRO_RUNTIME_ROOT__"
if source.count(placeholder) != 2:
    raise SystemExit("candidate Codex profile template placeholder count is invalid")
rendered = source.replace(placeholder, runtime_root.as_posix())
expected_script = f"{runtime_root.as_posix()}/server/chickenbro_native_mcp.py"
if (
    f'args = ["{expected_script}"]' not in rendered
    or f'cwd = "{runtime_root.as_posix()}"' not in rendered
    or placeholder in rendered
):
    raise SystemExit("candidate Codex profile ownership is invalid")
descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    output.write(rendered)
PY
install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${CODEX_PROFILE_NEW}" "${CANDIDATE_CODEX_PROFILE}"
rm -f "${CODEX_PROFILE_NEW}"
CODEX_PROFILE_IDENTITY="$(sha256sum "${CANDIDATE_CODEX_PROFILE}" | awk '{print $1}')"

install -o root -g root -m 0644 "${CANDIDATE_ROOT}/server/chickenbro-api-candidate.service" \
  "/etc/systemd/system/${CANDIDATE_API_SERVICE}.service"
install -o root -g root -m 0644 "${CANDIDATE_ROOT}/server/chickenbro-worker-candidate.service" \
  "/etc/systemd/system/${CANDIDATE_WORKER_SERVICE}.service"

install -d -o root -g root -m 0755 "${WEB_RELEASE_DIR}"
cp -a "${CANDIDATE_ROOT}/apps/mini-taro/dist/h5/." "${WEB_RELEASE_DIR}/"
ln -sfn "${WEB_RELEASE_DIR}" "${WEB_CURRENT_LINK}.new"
mv -Tf "${WEB_CURRENT_LINK}.new" "${WEB_CURRENT_LINK}"

inject_nginx_section() {
  local site="$1"
  local begin_marker="$2"
  local end_marker="$3"
  local output="${site}.chickenbro-${RUN_ID}"
  python3 - "${site}" "${CANDIDATE_ROOT}/server/chickenbro-web.nginx" "${begin_marker}" "${end_marker}" "${output}" <<'PY'
from pathlib import Path
import sys

site_path, snippet_path, begin, end, output_path = map(Path, sys.argv[1:])
site = site_path.read_text(encoding="utf-8")
snippet = snippet_path.read_text(encoding="utf-8")
begin_text = str(begin)
end_text = str(end)

def remove_section(text, start, finish):
    while start in text:
        left, remainder = text.split(start, 1)
        if finish not in remainder:
            raise SystemExit("unterminated existing candidate Nginx section")
        _, right = remainder.split(finish, 1)
        text = left.rstrip() + "\n" + right.lstrip("\n")
    return text

site = remove_section(site, begin_text, end_text)
if begin_text not in snippet or end_text not in snippet:
    raise SystemExit("candidate Nginx source section is missing")
section = begin_text + snippet.split(begin_text, 1)[1].split(end_text, 1)[0] + end_text
position = site.rfind("\n}")
if position < 0:
    raise SystemExit("existing Nginx server block is invalid")
updated = site[:position].rstrip() + "\n\n" + section.strip() + "\n" + site[position:]
Path(output_path).write_text(updated, encoding="utf-8")
PY
  install -o root -g root -m 0644 "${output}" "${site}"
  rm -f "${output}"
}

inject_nginx_section "${WWW_NGINX_OWNER}" '# BEGIN CHICKENBRO CANDIDATE WWW' '# END CHICKENBRO CANDIDATE WWW'
inject_nginx_section "${API_NGINX_OWNER}" '# BEGIN CHICKENBRO CANDIDATE API' '# END CHICKENBRO CANDIDATE API'
nginx -t
systemctl daemon-reload
systemctl enable "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null
systemctl restart "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}"
systemctl reload nginx

for _attempt in $(seq 1 30); do
  if systemctl is-active --quiet "${CANDIDATE_API_SERVICE}" \
    && systemctl is-active --quiet "${CANDIDATE_WORKER_SERVICE}" \
    && curl --fail --silent --show-error "http://127.0.0.1:${CANDIDATE_PORT}/api/v2/health/readiness" > "${BACKUP_DIR}/readiness.json"; then
    break
  fi
  sleep 1
done
systemctl is-active --quiet "${CANDIDATE_API_SERVICE}"
systemctl is-active --quiet "${CANDIDATE_WORKER_SERVICE}"
curl --fail --silent --show-error "http://127.0.0.1:${CANDIDATE_PORT}/api/v2/health/readiness" \
  > "${BACKUP_DIR}/readiness.json"

for public_origin in https://www.chickenbro.cloud https://api.chickenbro.cloud; do
  origin_label="${public_origin#https://}"
  curl --fail --silent --show-error "${public_origin}${CANDIDATE_PREFIX}/health/readiness" \
    > "${BACKUP_DIR}/public-readiness-${origin_label}.json"
  for formal_path in \
    "${CANDIDATE_PREFIX}/me" \
    "${CANDIDATE_PREFIX}/chat/conversations" \
    "${CANDIDATE_PREFIX}/simc/jobs"; do
    route_label="${formal_path#"${CANDIDATE_PREFIX}/"}"
    route_label="${route_label//\//-}"
    route_output="${BACKUP_DIR}/formal-route-${origin_label}-${route_label}.json"
    status="$(curl --connect-timeout 10 --max-time 30 --silent --show-error --output "${route_output}" --write-out '%{http_code}' \
      "${public_origin}${formal_path}")"
    [[ "${status}" == "401" ]] \
      || die_remote "formal unauthenticated route did not reject with 401: ${public_origin}${formal_path}"
    python3 - "${route_output}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
error = payload.get("error") if isinstance(payload, dict) else None
if not isinstance(error, dict) or error.get("code") != "AUTH_REQUIRED":
    raise SystemExit("formal anonymous route did not return AUTH_REQUIRED")
PY
  done
done

READINESS_OVERALL_STATUS="$(python3 - "${READINESS_SUMMARY}" \
  "internal=${BACKUP_DIR}/readiness.json" \
  "www.chickenbro.cloud=${BACKUP_DIR}/public-readiness-www.chickenbro.cloud.json" \
  "api.chickenbro.cloud=${BACKUP_DIR}/public-readiness-api.chickenbro.cloud.json" <<'PY'
import hashlib
import json
import sys
import uuid
from pathlib import Path

output_path = Path(sys.argv[1])
allowed_overall = {"ready", "partial", "blocked"}
allowed_component = {"ready", "partial", "blocked", "unconfigured"}
required_ready = {"database", "wechat_mini"}
observations = []
reference = None

for descriptor in sys.argv[2:]:
    surface, raw_path = descriptor.split("=", 1)
    path = Path(raw_path)
    raw = path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("status") not in allowed_overall:
        raise SystemExit(f"invalid readiness payload from {surface}")
    try:
        uuid.UUID(str(payload.get("requestId", "")))
    except ValueError as error:
        raise SystemExit(f"invalid readiness request id from {surface}") from error
    components = payload.get("components")
    if not isinstance(components, dict) or not components:
        raise SystemExit(f"invalid readiness components from {surface}")

    normalized_components = {}
    for name, component in sorted(components.items()):
        if not isinstance(name, str) or not name or not isinstance(component, dict):
            raise SystemExit(f"invalid readiness component from {surface}")
        status = component.get("status")
        code = component.get("code")
        if status not in allowed_component or not isinstance(code, str):
            raise SystemExit(f"invalid readiness component from {surface}: {name}")
        normalized_components[name] = {"status": status, "code": code}

    if payload["status"] == "blocked" or any(
        component["status"] == "blocked" for component in normalized_components.values()
    ):
        raise SystemExit("candidate readiness contains a blocked component")
    for name in required_ready:
        if normalized_components.get(name, {}).get("status") != "ready":
            raise SystemExit(f"required readiness component is not ready: {name}")

    semantic = {"status": payload["status"], "components": normalized_components}
    if reference is None:
        reference = semantic
    elif semantic != reference:
        raise SystemExit("readiness payloads disagree across candidate origins")
    observations.append({"surface": surface, "payloadSha256": hashlib.sha256(raw).hexdigest()})

assert reference is not None
overall = reference["status"]
summary = {
    "status": overall,
    "disposition": (
        "partial_not_promotable"
        if overall == "partial"
        else "automated_checks_passed_user_acceptance_pending"
    ),
    "components": reference["components"],
    "observations": observations,
}
output_path.write_text(
    json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
print(overall)
PY
)"

DATABASE_MIGRATION_IDS="$(sudo -n -u postgres psql -At --dbname="${CANDIDATE_DATABASE}" \
  --command="SELECT string_agg(id, ',' ORDER BY id) FROM ops.schema_migrations")"
[[ "${DATABASE_MIGRATION_IDS}" == "0001_chickenbro_simc_core,0002_chat_idempotent_replay" ]] \
  || die_remote "database migration identity mismatch"
API_SERVICE_IDENTITY="$(sha256sum "/etc/systemd/system/${CANDIDATE_API_SERVICE}.service" | awk '{print $1}')"
CANDIDATE_WORKER_SERVICE_IDENTITY="$(sha256sum "/etc/systemd/system/${CANDIDATE_WORKER_SERVICE}.service" | awk '{print $1}')"
SIMC_RUNTIME_IDENTITY="$(sha256sum /opt/wow-simc/current/simc | awk '{print $1}')"
DEPLOYED_WEB_BUILD_IDENTITY="$(python3 - "${WEB_RELEASE_DIR}" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
digest = hashlib.sha256()
files = sorted(path for path in root.rglob("*") if path.is_file())
if not files:
    raise SystemExit("deployed Web build is empty")
for path in files:
    if path.is_symlink():
        raise SystemExit("deployed Web identity cannot follow symbolic links")
    digest.update(path.relative_to(root).as_posix().encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
)"
[[ "${DEPLOYED_WEB_BUILD_IDENTITY}" == "${WEB_BUILD_IDENTITY}" ]] \
  || die_remote "deployed Web build identity mismatch"
DEPLOYED_WEAPP_BUILD_IDENTITY="$(python3 - "${CANDIDATE_ROOT}/apps/mini-taro/dist/weapp" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
digest = hashlib.sha256()
files = sorted(path for path in root.rglob("*") if path.is_file())
if not files:
    raise SystemExit("deployed WeApp build is empty")
for path in files:
    if path.is_symlink():
        raise SystemExit("deployed WeApp identity cannot follow symbolic links")
    digest.update(path.relative_to(root).as_posix().encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
)"
[[ "${DEPLOYED_WEAPP_BUILD_IDENTITY}" == "${WEAPP_BUILD_IDENTITY}" ]] \
  || die_remote "deployed WeApp build identity mismatch"
WWW_NGINX_IDENTITY="$(sha256sum "${WWW_NGINX_OWNER}" | awk '{print $1}')"
API_NGINX_IDENTITY="$(sha256sum "${API_NGINX_OWNER}" | awk '{print $1}')"

rm -f "${AUTOMATED_ACCEPTANCE_TMP}"
sudo -n -u "${REMOTE_USER}" \
  --preserve-env=WOW_DATABASE_URL,WOW_WECHAT_APPID,PGPASSFILE,PYTHONPATH \
  "${RUNTIME_ROOT}/bin/python" -m server.accept_chickenbro_candidate \
  --expected-database "${CANDIDATE_DATABASE}" \
  --expected-commit "${EXPECTED_COMMIT}" \
  --web-build-identity "${WEB_BUILD_IDENTITY}" \
  --weapp-build-identity "${WEAPP_BUILD_IDENTITY}" \
  --evidence-path "${AUTOMATED_ACCEPTANCE_TMP}"
install -o root -g root -m 0600 "${AUTOMATED_ACCEPTANCE_TMP}" "${AUTOMATED_ACCEPTANCE_REPORT}"
rm -f "${AUTOMATED_ACCEPTANCE_TMP}"
python3 - "${AUTOMATED_ACCEPTANCE_REPORT}" "${EXPECTED_COMMIT}" "${WEB_BUILD_IDENTITY}" "${WEAPP_BUILD_IDENTITY}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("status") != "automated_candidate_acceptance_passed":
    raise SystemExit("automated candidate acceptance did not pass")
if payload.get("branchCommit") != sys.argv[2]:
    raise SystemExit("automated candidate acceptance commit mismatch")
if payload.get("webBuildIdentity") != sys.argv[3]:
    raise SystemExit("automated candidate acceptance Web build mismatch")
if payload.get("weappBuildIdentity") != sys.argv[4]:
    raise SystemExit("automated candidate acceptance WeApp build mismatch")
if payload.get("realWechatQrAcceptance") != "pending" or payload.get("realDeviceAcceptance") != "pending":
    raise SystemExit("automated acceptance must not claim real user acceptance")
PY
AUTOMATED_ACCEPTANCE_SHA256="$(sha256sum "${AUTOMATED_ACCEPTANCE_REPORT}" | awk '{print $1}')"
READINESS_SUMMARY_SHA256="$(sha256sum "${READINESS_SUMMARY}" | awk '{print $1}')"
find "${BACKUP_DIR}" -maxdepth 1 -type f ! -name 'rollback-manifest.sha256' ! -name 'candidate-acceptance.json' \
  -print0 | sort -z | xargs -0 sha256sum > "${ROLLBACK_MANIFEST}"
ROLLBACK_MANIFEST_SHA256="$(sha256sum "${ROLLBACK_MANIFEST}" | awk '{print $1}')"

export EXPECTED_COMMIT SOURCE_ARCHIVE_SHA256 SOURCE_MANIFEST_SHA256 DEPLOYED_MANIFEST_SHA256
export REVIEWED_INVENTORY_SHA REVIEWED_RECOVERY_MANIFEST_SHA
export DATABASE_MIGRATION_IDS API_SERVICE_IDENTITY CANDIDATE_WORKER_SERVICE_IDENTITY CODEX_RUNTIME_IDENTITY CODEX_PROFILE_IDENTITY SIMC_RUNTIME_IDENTITY
export WEB_BUILD_IDENTITY WEAPP_BUILD_IDENTITY WWW_NGINX_IDENTITY API_NGINX_IDENTITY
export AUTOMATED_ACCEPTANCE_REPORT AUTOMATED_ACCEPTANCE_SHA256
export READINESS_SUMMARY READINESS_SUMMARY_SHA256 READINESS_OVERALL_STATUS
export ROLLBACK_MANIFEST_SHA256 MIGRATION_REPORT ACCEPTANCE_REPORT
python3 - <<'PY'
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

migration_sha = hashlib.sha256(Path(os.environ["MIGRATION_REPORT"]).read_bytes()).hexdigest()
readiness = json.loads(Path(os.environ["READINESS_SUMMARY"]).read_text(encoding="utf-8"))
if readiness.get("status") != os.environ["READINESS_OVERALL_STATUS"]:
    raise SystemExit("readiness evidence status mismatch")
payload = {
    "status": "candidate_deployed_user_acceptance_pending",
    "branchCommit": os.environ["EXPECTED_COMMIT"],
    "sourceArchiveSha256": os.environ["SOURCE_ARCHIVE_SHA256"],
    "sourceManifestSha256": os.environ["SOURCE_MANIFEST_SHA256"],
    "deployedManifestSha256": os.environ["DEPLOYED_MANIFEST_SHA256"],
    "inventorySha256": os.environ["REVIEWED_INVENTORY_SHA"],
    "whitelistRecoveryManifestSha256": os.environ["REVIEWED_RECOVERY_MANIFEST_SHA"],
    "databaseMigrationIds": os.environ["DATABASE_MIGRATION_IDS"].split(","),
    "migrationReportSha256": migration_sha,
    "apiServiceIdentity": os.environ["API_SERVICE_IDENTITY"],
    "candidateWorkerServiceIdentity": os.environ["CANDIDATE_WORKER_SERVICE_IDENTITY"],
    "legacyCandidateServiceRetired": True,
    "codexRuntimeIdentity": os.environ["CODEX_RUNTIME_IDENTITY"],
    "codexProfileIdentity": os.environ["CODEX_PROFILE_IDENTITY"],
    "simcRuntimeIdentity": os.environ["SIMC_RUNTIME_IDENTITY"],
    "webBuildIdentity": os.environ["WEB_BUILD_IDENTITY"],
    "weappBuildIdentity": os.environ["WEAPP_BUILD_IDENTITY"],
    "wwwNginxIdentity": os.environ["WWW_NGINX_IDENTITY"],
    "apiNginxIdentity": os.environ["API_NGINX_IDENTITY"],
    "automatedAcceptance": {
        "status": "passed",
        "report": "automated-acceptance.json",
        "sha256": os.environ["AUTOMATED_ACCEPTANCE_SHA256"],
    },
    "readiness": readiness,
    "readinessReport": "readiness-summary.json",
    "readinessReportSha256": os.environ["READINESS_SUMMARY_SHA256"],
    "rollbackManifestSha256": os.environ["ROLLBACK_MANIFEST_SHA256"],
    "formalAnonymousRouteSmoke": {
        "origins": ["www.chickenbro.cloud", "api.chickenbro.cloud"],
        "routes": ["me", "chat/conversations", "simc/jobs"],
    },
    "realDualClientAcceptance": "pending",
    "recordedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
Path(os.environ["ACCEPTANCE_REPORT"]).write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
chmod 0600 "${MIGRATION_REPORT}" "${AUTOMATED_ACCEPTANCE_REPORT}" "${ACCEPTANCE_REPORT}" "${ROLLBACK_MANIFEST}"
printf '%s\n' candidate_deployed_user_acceptance_pending > "${BACKUP_DIR}/STATE"
trap - EXIT
rm -f "${REMOTE_ARCHIVE}"
rm -rf "${STAGE_DIR}"
printf 'candidate=%s acceptance=%s rollbackManifestSha256=%s\n' \
  "${EXPECTED_COMMIT}" "${ACCEPTANCE_REPORT}" "${ROLLBACK_MANIFEST_SHA256}"
REMOTE_DEPLOY

trap - EXIT
cleanup_local

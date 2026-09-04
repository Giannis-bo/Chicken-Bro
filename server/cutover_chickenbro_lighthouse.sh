#!/usr/bin/env bash
set -euo pipefail

# State contract: preflight -> write_fenced -> delta_migrated -> switched -> accepted_write
MODE="dry-run"
BACKUP_MODE="independent"
NO_BACKUP_CONFIRMATION=""
CANDIDATE_COMMIT=""
REVIEWED_INVENTORY_SHA=""
REVIEWED_BACKUP_MANIFEST_SHA=""
CANDIDATE_EVIDENCE_PATH=""
CANDIDATE_EVIDENCE_SHA=""
REAL_ACCEPTANCE_PATH=""
REAL_ACCEPTANCE_SHA=""
CUTOVER_EVIDENCE_PATH=""
CUTOVER_EVIDENCE_SHA=""
PRODUCTION_ACCEPTANCE_PATH=""
PRODUCTION_ACCEPTANCE_SHA=""

NO_BACKUP_CONFIRMATION_TEXT="I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INVENTORY_FILE="${REPO_ROOT}/docs/refactor/chickenbro-simc-cloud-inventory.json"

REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
REMOTE_BACKUP_MANIFEST="${WOW_CHICKENBRO_REMOTE_BACKUP_MANIFEST:-/mnt/chickenbro-backups/restore-verified.json}"
REMOTE_CUTOVER_ROOT="$(dirname -- "${REMOTE_BACKUP_MANIFEST}")/cutover-runs"
PRODUCTION_ROOT="/opt/chickenbro"
CANDIDATE_ROOT="/opt/chickenbro-candidate"
RUNTIME_ROOT="/opt/chickenbro-runtime"
PRODUCTION_DATABASE="chickenbro_prod"
SOURCE_DATABASE="wow_test"
PRODUCTION_PORT="8790"
PRODUCTION_API_SERVICE="chickenbro-api"
PRODUCTION_WORKER_SERVICE="chickenbro-worker"
SIMC_UPDATE_SERVICE="chickenbro-simc-runtime-update"
CANDIDATE_API_SERVICE="chickenbro-api-candidate"
CANDIDATE_WORKER_SERVICE="chickenbro-worker-candidate"
PRODUCTION_API_ENV="/etc/chickenbro-api.env"
PRODUCTION_SOURCE_ENV="/etc/chickenbro-source.env"
PRODUCTION_WORKER_ENV="/etc/chickenbro-worker.env"
PRODUCTION_PGPASSFILE="/etc/chickenbro-api.pgpass"
PRODUCTION_CODEX_PROFILE="/home/${REMOTE_USER}/.codex/chickenbro-production.config.toml"
LEGACY_API_ENV="/etc/wow-v2-api.env"
LEGACY_SOURCE_ENV="/etc/wow-v2-source.env"
WWW_NGINX_SITE="/etc/nginx/sites-available/wow-v2-web"
API_NGINX_SITE="/etc/nginx/sites-enabled/api.chickenbro.cloud"
PRODUCTION_WEB_ROOT="/var/www/chickenbro-web"

STATE_SEQUENCE=(preflight write_fenced delta_migrated switched accepted_write)

SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15)

die() {
  printf 'cutover_chickenbro: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf '%s\n' \
    'Usage:' \
    '  server/cutover_chickenbro_lighthouse.sh --dry-run [--candidate-commit <40-char-sha>]' \
    '  server/cutover_chickenbro_lighthouse.sh --apply --candidate-commit <40-char-sha> --inventory-sha <sha256> --backup-manifest-sha <sha256> --candidate-evidence-path <absolute-remote-path> --candidate-evidence-sha <sha256> --real-acceptance-path <absolute-remote-path> --real-acceptance-sha <sha256>' \
    '  server/cutover_chickenbro_lighthouse.sh --apply --no-independent-backup --irreversible-no-backup-confirmation I_UNDERSTAND_NO_BACKUP_IS_IRREVERSIBLE --candidate-commit <40-char-sha> --inventory-sha <sha256> --candidate-evidence-path <absolute-remote-path> --candidate-evidence-sha <sha256> --real-acceptance-path <absolute-remote-path> --real-acceptance-sha <sha256>' \
    '  server/cutover_chickenbro_lighthouse.sh --seal-accepted-write --candidate-commit <40-char-sha> --cutover-evidence-path <absolute-remote-path> --cutover-evidence-sha <sha256> --production-acceptance-path <absolute-remote-path> --production-acceptance-sha <sha256>' >&2
}

validate_value() {
  local name="$1"
  local value="$2"
  local pattern="$3"
  [[ "${value}" =~ ${pattern} ]] || die "invalid ${name}"
}

validate_remote_evidence_path() {
  local name="$1"
  local value="$2"
  [[ "${value}" =~ ^/[A-Za-z0-9_./-]+$ ]] || die "invalid ${name}"
  [[ "${value}" == /* && "${value}" != *".."* ]] || die "invalid ${name}"
  [[ "${value}" == "$(dirname -- "${REMOTE_BACKUP_MANIFEST}")"/candidate-runs/* ]] \
    || die "${name} must be inside the reviewed candidate evidence root"
}

validate_remote_cutover_path() {
  local name="$1"
  local value="$2"
  [[ "${value}" =~ ^/[A-Za-z0-9_./-]+$ ]] || die "invalid ${name}"
  [[ "${value}" == /* && "${value}" != *".."* ]] || die "invalid ${name}"
  [[ "${value}" == "${REMOTE_CUTOVER_ROOT}"/* ]] \
    || die "${name} must be inside the reviewed cutover evidence root"
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
    digest.update(path.relative_to(root).as_posix().encode("utf-8"))
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
    --seal-accepted-write)
      MODE="seal-accepted-write"
      shift
      ;;
    --no-independent-backup)
      BACKUP_MODE="none_user_authorized"
      shift
      ;;
    --irreversible-no-backup-confirmation)
      [[ $# -ge 2 ]] || die "--irreversible-no-backup-confirmation requires a value"
      NO_BACKUP_CONFIRMATION="$2"
      shift 2
      ;;
    --candidate-commit)
      [[ $# -ge 2 ]] || die "--candidate-commit requires a value"
      CANDIDATE_COMMIT="$2"
      shift 2
      ;;
    --inventory-sha)
      [[ $# -ge 2 ]] || die "--inventory-sha requires a value"
      REVIEWED_INVENTORY_SHA="$2"
      shift 2
      ;;
    --backup-manifest-sha)
      [[ $# -ge 2 ]] || die "--backup-manifest-sha requires a value"
      REVIEWED_BACKUP_MANIFEST_SHA="$2"
      shift 2
      ;;
    --candidate-evidence-path)
      [[ $# -ge 2 ]] || die "--candidate-evidence-path requires a value"
      CANDIDATE_EVIDENCE_PATH="$2"
      shift 2
      ;;
    --candidate-evidence-sha)
      [[ $# -ge 2 ]] || die "--candidate-evidence-sha requires a value"
      CANDIDATE_EVIDENCE_SHA="$2"
      shift 2
      ;;
    --real-acceptance-path)
      [[ $# -ge 2 ]] || die "--real-acceptance-path requires a value"
      REAL_ACCEPTANCE_PATH="$2"
      shift 2
      ;;
    --real-acceptance-sha)
      [[ $# -ge 2 ]] || die "--real-acceptance-sha requires a value"
      REAL_ACCEPTANCE_SHA="$2"
      shift 2
      ;;
    --cutover-evidence-path)
      [[ $# -ge 2 ]] || die "--cutover-evidence-path requires a value"
      CUTOVER_EVIDENCE_PATH="$2"
      shift 2
      ;;
    --cutover-evidence-sha)
      [[ $# -ge 2 ]] || die "--cutover-evidence-sha requires a value"
      CUTOVER_EVIDENCE_SHA="$2"
      shift 2
      ;;
    --production-acceptance-path)
      [[ $# -ge 2 ]] || die "--production-acceptance-path requires a value"
      PRODUCTION_ACCEPTANCE_PATH="$2"
      shift 2
      ;;
    --production-acceptance-sha)
      [[ $# -ge 2 ]] || die "--production-acceptance-sha requires a value"
      PRODUCTION_ACCEPTANCE_SHA="$2"
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

if [[ "${BACKUP_MODE}" == "none_user_authorized" ]]; then
  [[ "${MODE}" == "apply" ]] || die "--no-independent-backup is only valid with --apply"
  [[ "${NO_BACKUP_CONFIRMATION}" == "${NO_BACKUP_CONFIRMATION_TEXT}" ]] \
    || die "--no-independent-backup requires --irreversible-no-backup-confirmation ${NO_BACKUP_CONFIRMATION_TEXT}"
  [[ -z "${REVIEWED_BACKUP_MANIFEST_SHA}" ]] \
    || die "--no-independent-backup cannot be combined with --backup-manifest-sha"
elif [[ -n "${NO_BACKUP_CONFIRMATION}" ]]; then
  die "--irreversible-no-backup-confirmation requires --no-independent-backup"
fi

validate_value REMOTE_HOST "${REMOTE_HOST}" '^[A-Za-z0-9_.:-]+$'
validate_value REMOTE_USER "${REMOTE_USER}" '^[A-Za-z_][A-Za-z0-9_.-]*$'
validate_value PRODUCTION_CODEX_PROFILE "${PRODUCTION_CODEX_PROFILE}" '^/home/[A-Za-z_][A-Za-z0-9_.-]*/\.codex/chickenbro-production\.config\.toml$'
validate_value REMOTE_BACKUP_MANIFEST "${REMOTE_BACKUP_MANIFEST}" '^/[A-Za-z0-9_./-]+$'
[[ "${PRODUCTION_CODEX_PROFILE}" == "/home/${REMOTE_USER}/.codex/chickenbro-production.config.toml" ]] \
  || die "production Codex profile must belong to the remote service user"
[[ "${REMOTE_BACKUP_MANIFEST}" == /* && "${REMOTE_BACKUP_MANIFEST}" != *".."* ]] \
  || die "invalid REMOTE_BACKUP_MANIFEST"
if [[ "${BACKUP_MODE}" == "independent" ]]; then
  [[ "${REMOTE_BACKUP_MANIFEST}" != /var/* && "${REMOTE_BACKUP_MANIFEST}" != /opt/* ]] \
    || die "backup manifest must be on the reviewed independent backup mount"
fi
[[ -f "${INVENTORY_FILE}" ]] || die "cloud inventory is missing"

CURRENT_COMMIT="$(git -C "${REPO_ROOT}" rev-parse HEAD)"
ACTUAL_INVENTORY_SHA="$(sha256_file "${INVENTORY_FILE}")"
validate_value CURRENT_COMMIT "${CURRENT_COMMIT}" '^[0-9a-f]{40}$'
validate_value ACTUAL_INVENTORY_SHA "${ACTUAL_INVENTORY_SHA}" '^[0-9a-f]{64}$'
if [[ -n "${CANDIDATE_COMMIT}" ]]; then
  validate_value CANDIDATE_COMMIT "${CANDIDATE_COMMIT}" '^[0-9a-f]{40}$'
  [[ "${CANDIDATE_COMMIT}" == "${CURRENT_COMMIT}" ]] \
    || die "candidate commit does not match git rev-parse HEAD"
fi

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

if [[ "${MODE}" == "dry-run" ]]; then
  python3 - "${CURRENT_COMMIT}" "${ACTUAL_INVENTORY_SHA}" "${INVENTORY_STATUS}" "${CAPACITY_GATE}" "${INVENTORY_OBSERVED_AT}" <<'PY'
import json
import sys

commit, inventory_sha, inventory_status, capacity_gate, observed_at = sys.argv[1:]
print(json.dumps({
    "mode": "dry-run",
    "mutationAuthorized": False,
    "state": "preflight",
    "branchCommit": commit,
    "inventorySha256": inventory_sha,
    "inventoryStatus": inventory_status,
    "capacityGate": capacity_gate,
    "inventoryObservedAt": observed_at,
    "sourceDatabase": "wow_test",
    "targetDatabase": "chickenbro_prod",
    "rollbackClassification": "pre_write_legacy_writable_post_write_legacy_read_only",
}, sort_keys=True, separators=(",", ":")))
PY
  exit 0
fi

[[ -n "${CANDIDATE_COMMIT}" ]] || die "--${MODE} requires --candidate-commit"
[[ -z "$(git -C "${REPO_ROOT}" status --porcelain)" ]] \
  || die "tracked worktree must be clean at the exact candidate commit"

if [[ "${MODE}" == "apply" ]]; then
  [[ -n "${REVIEWED_INVENTORY_SHA}" ]] || die "--apply requires --inventory-sha"
  if [[ "${BACKUP_MODE}" == "independent" ]]; then
    [[ -n "${REVIEWED_BACKUP_MANIFEST_SHA}" ]] || die "--apply requires --backup-manifest-sha"
  fi
  [[ -n "${CANDIDATE_EVIDENCE_PATH}" ]] || die "--apply requires --candidate-evidence-path"
  [[ -n "${CANDIDATE_EVIDENCE_SHA}" ]] || die "--apply requires --candidate-evidence-sha"
  [[ -n "${REAL_ACCEPTANCE_PATH}" ]] || die "--apply requires --real-acceptance-path"
  [[ -n "${REAL_ACCEPTANCE_SHA}" ]] || die "--apply requires --real-acceptance-sha"
  validate_value REVIEWED_INVENTORY_SHA "${REVIEWED_INVENTORY_SHA}" '^[0-9a-f]{64}$'
  if [[ "${BACKUP_MODE}" == "independent" ]]; then
    validate_value REVIEWED_BACKUP_MANIFEST_SHA "${REVIEWED_BACKUP_MANIFEST_SHA}" '^[0-9a-f]{64}$'
  fi
  validate_value CANDIDATE_EVIDENCE_SHA "${CANDIDATE_EVIDENCE_SHA}" '^[0-9a-f]{64}$'
  validate_value REAL_ACCEPTANCE_SHA "${REAL_ACCEPTANCE_SHA}" '^[0-9a-f]{64}$'
  validate_remote_evidence_path CANDIDATE_EVIDENCE_PATH "${CANDIDATE_EVIDENCE_PATH}"
  validate_remote_evidence_path REAL_ACCEPTANCE_PATH "${REAL_ACCEPTANCE_PATH}"
  [[ "$(dirname -- "${CANDIDATE_EVIDENCE_PATH}")" == "$(dirname -- "${REAL_ACCEPTANCE_PATH}")" ]] \
    || die "candidate and real acceptance must belong to the same reviewed run"
  [[ "${REVIEWED_INVENTORY_SHA}" == "${ACTUAL_INVENTORY_SHA}" ]] \
    || die "inventory SHA does not match reviewed input"
  [[ "${INVENTORY_STATUS}" == "reachable" && "${INVENTORY_ERROR_COUNT}" == "0" ]] \
    || die "reviewed inventory is not a clean reachable observation"
  [[ "${CAPACITY_GATE}" == "capacity_preflight_required" ]] \
    || die "reviewed inventory does not authorize production cutover preflight"
elif [[ "${MODE}" == "seal-accepted-write" ]]; then
  [[ -n "${CUTOVER_EVIDENCE_PATH}" ]] \
    || die "--seal-accepted-write requires --cutover-evidence-path"
  [[ -n "${CUTOVER_EVIDENCE_SHA}" ]] \
    || die "--seal-accepted-write requires --cutover-evidence-sha"
  [[ -n "${PRODUCTION_ACCEPTANCE_PATH}" ]] \
    || die "--seal-accepted-write requires --production-acceptance-path"
  [[ -n "${PRODUCTION_ACCEPTANCE_SHA}" ]] \
    || die "--seal-accepted-write requires --production-acceptance-sha"
  validate_value CUTOVER_EVIDENCE_SHA "${CUTOVER_EVIDENCE_SHA}" '^[0-9a-f]{64}$'
  validate_value PRODUCTION_ACCEPTANCE_SHA "${PRODUCTION_ACCEPTANCE_SHA}" '^[0-9a-f]{64}$'
  validate_remote_cutover_path CUTOVER_EVIDENCE_PATH "${CUTOVER_EVIDENCE_PATH}"
  validate_remote_cutover_path PRODUCTION_ACCEPTANCE_PATH "${PRODUCTION_ACCEPTANCE_PATH}"
  [[ "$(basename -- "${CUTOVER_EVIDENCE_PATH}")" == "production-cutover.json" ]] \
    || die "cutover evidence must be the exact production-cutover.json"
  [[ "$(basename -- "${PRODUCTION_ACCEPTANCE_PATH}")" == "production-user-acceptance.json" ]] \
    || die "production acceptance must be the exact production-user-acceptance.json"
  [[ "$(dirname -- "${CUTOVER_EVIDENCE_PATH}")" == "$(dirname -- "${PRODUCTION_ACCEPTANCE_PATH}")" ]] \
    || die "cutover and production acceptance evidence must belong to the same run"
else
  die "unsupported mode"
fi

for required in \
  server/__init__.py \
  server/app \
  server/codex_worker.py \
  server/migrations/__init__.py \
  server/migrations/product/0001_chickenbro_simc_core.sql \
  server/migrations/product/0002_chat_idempotent_replay.sql \
  server/migrations/product/postgres_legacy.py \
  server/chickenbro_native_mcp.py \
  server/chickenbro_public_web_research.py \
  server/chickenbro_simc_runtime_update.sh \
  server/chickenbro-simc-runtime-update.service \
  server/chickenbro-api.service \
  server/chickenbro-worker.service \
  scripts/chickenbro-native-agent/chickenbro-native.config.toml.template; do
  [[ -e "${REPO_ROOT}/${required}" ]] || die "missing production input: ${required}"
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

if [[ "${MODE}" == "seal-accepted-write" ]]; then
  SEAL_REMOTE_ENV=(
    "CANDIDATE_COMMIT=${CANDIDATE_COMMIT}"
    "CUTOVER_EVIDENCE_PATH=${CUTOVER_EVIDENCE_PATH}"
    "CUTOVER_EVIDENCE_SHA=${CUTOVER_EVIDENCE_SHA}"
    "PRODUCTION_ACCEPTANCE_PATH=${PRODUCTION_ACCEPTANCE_PATH}"
    "PRODUCTION_ACCEPTANCE_SHA=${PRODUCTION_ACCEPTANCE_SHA}"
    "REMOTE_CUTOVER_ROOT=${REMOTE_CUTOVER_ROOT}"
    "PRODUCTION_ROOT=${PRODUCTION_ROOT}"
    "PRODUCTION_DATABASE=${PRODUCTION_DATABASE}"
    "SOURCE_DATABASE=${SOURCE_DATABASE}"
    "PRODUCTION_PORT=${PRODUCTION_PORT}"
    "PRODUCTION_API_SERVICE=${PRODUCTION_API_SERVICE}"
    "PRODUCTION_WORKER_SERVICE=${PRODUCTION_WORKER_SERVICE}"
  )
  seal_remote_env_args() {
    local item
    for item in "${SEAL_REMOTE_ENV[@]}"; do
      printf '%q ' "${item}"
    done
  }

  printf 'Sealing accepted production write for %s\n' "${CANDIDATE_COMMIT}"
  ssh_remote "$(seal_remote_env_args) sudo -E bash -s" <<'REMOTE_SEAL'
set -euo pipefail

die_remote() {
  printf 'cutover_chickenbro seal remote: %s\n' "$*" >&2
  exit 1
}

for command_name in python3 psql systemctl sha256sum curl awk stat mv; do
  command -v "${command_name}" >/dev/null 2>&1 \
    || die_remote "missing command: ${command_name}"
done

RUN_DIR="$(dirname -- "${CUTOVER_EVIDENCE_PATH}")"
STATE_FILE="${RUN_DIR}/STATE"
WRITE_AUTHORITY_BOUNDARY="${RUN_DIR}/WRITE_AUTHORITY_BOUNDARY"
SEALED_EVIDENCE="${CUTOVER_EVIDENCE_PATH}.sealed"
[[ "${RUN_DIR}" == "${REMOTE_CUTOVER_ROOT}"/* ]] \
  || die_remote "cutover evidence escaped the reviewed root"
[[ "${RUN_DIR}" == "$(dirname -- "${PRODUCTION_ACCEPTANCE_PATH}")" ]] \
  || die_remote "production acceptance belongs to a different cutover run"
[[ -f "${STATE_FILE}" && "$(<"${STATE_FILE}")" == "switched" ]] \
  || die_remote "cutover is not waiting at switched"
[[ -f "${WRITE_AUTHORITY_BOUNDARY}" ]] \
  || die_remote "write authority boundary is missing"
[[ -f "${CUTOVER_EVIDENCE_PATH}" && ! -L "${CUTOVER_EVIDENCE_PATH}" ]] \
  || die_remote "cutover evidence is missing"
[[ -f "${PRODUCTION_ACCEPTANCE_PATH}" && ! -L "${PRODUCTION_ACCEPTANCE_PATH}" ]] \
  || die_remote "production acceptance evidence is missing"
[[ "$(sha256sum "${CUTOVER_EVIDENCE_PATH}" | awk '{print $1}')" == "${CUTOVER_EVIDENCE_SHA}" ]] \
  || die_remote "cutover evidence SHA mismatch"
[[ "$(sha256sum "${PRODUCTION_ACCEPTANCE_PATH}" | awk '{print $1}')" == "${PRODUCTION_ACCEPTANCE_SHA}" ]] \
  || die_remote "production acceptance SHA mismatch"
[[ -f "${PRODUCTION_ROOT}/BRANCH_COMMIT" && "$(<"${PRODUCTION_ROOT}/BRANCH_COMMIT")" == "${CANDIDATE_COMMIT}" ]] \
  || die_remote "deployed production commit mismatch"

systemctl is-active --quiet "${PRODUCTION_API_SERVICE}" \
  || die_remote "production API is not active"
systemctl is-active --quiet "${PRODUCTION_WORKER_SERVICE}" \
  || die_remote "production Worker is not active"
SOURCE_DATABASE_READ_ONLY="$(sudo -n -u postgres psql --no-psqlrc -At \
  --dbname="${SOURCE_DATABASE}" --command="SHOW default_transaction_read_only")"
[[ "${SOURCE_DATABASE_READ_ONLY}" == "on" ]] \
  || die_remote "legacy database is not read-only"
TARGET_DATABASE_READ_ONLY="$(sudo -n -u postgres psql --no-psqlrc -At \
  --dbname="${PRODUCTION_DATABASE}" --command="SHOW default_transaction_read_only")"
[[ "${TARGET_DATABASE_READ_ONLY}" == "off" ]] \
  || die_remote "new production database is not writable"
curl --fail --silent --show-error \
  "http://127.0.0.1:${PRODUCTION_PORT}/api/v2/health/readiness" \
  > "${RUN_DIR}/readiness-before-accepted-write-seal.json"

python3 - \
  "${CUTOVER_EVIDENCE_PATH}" \
  "${PRODUCTION_ACCEPTANCE_PATH}" \
  "${WRITE_AUTHORITY_BOUNDARY}" \
  "${CANDIDATE_COMMIT}" \
  "${CUTOVER_EVIDENCE_SHA}" \
  "${PRODUCTION_ACCEPTANCE_SHA}" \
  "${SEALED_EVIDENCE}" <<'PY'
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path

cutover_path, acceptance_path, boundary_path, sealed_path = map(
    Path, (sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[7])
)
commit, cutover_sha, acceptance_sha = sys.argv[4:7]
sha = re.compile(r"[0-9a-f]{64}\Z")

def fail(message):
    raise SystemExit(message)

def read_private(path, label):
    if path.is_symlink() or not path.is_file():
        fail(f"{label} must be a mode-0600 regular file")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        fail(f"{label} must be a mode-0600 regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value

def parse_time(value, label):
    if not isinstance(value, str) or not value.endswith("Z"):
        fail(f"{label} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{label} timestamp is invalid")
    if parsed.utcoffset() is None:
        fail(f"{label} timestamp is invalid")
    return parsed

def reject_secrets(value):
    forbidden = {
        "openid", "sessionkey", "accesstoken", "refreshtoken", "cookie",
        "bearer", "ticket", "verifier", "userid", "providersubject", "unionid",
    }
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in forbidden:
                fail("production acceptance contains a forbidden identity or credential field")
            reject_secrets(child)
    elif isinstance(value, list):
        for child in value:
            reject_secrets(child)

def require_passed_check(payload, key, hash_key=None):
    value = payload.get(key)
    if not isinstance(value, dict) or value.get("status") != "passed":
        fail(f"production acceptance check did not pass: {key}")
    if hash_key is not None and sha.fullmatch(str(value.get(hash_key, ""))) is None:
        fail(f"production acceptance check hash is invalid: {key}")

cutover = read_private(cutover_path, "cutover evidence")
acceptance = read_private(acceptance_path, "production acceptance")
if hashlib.sha256(cutover_path.read_bytes()).hexdigest() != cutover_sha:
    fail("cutover evidence SHA mismatch")
if hashlib.sha256(acceptance_path.read_bytes()).hexdigest() != acceptance_sha:
    fail("production acceptance SHA mismatch")
if cutover.get("schemaVersion") != "chickenbro-production-cutover-v1":
    fail("cutover evidence schema mismatch")
if cutover.get("status") != "production_cutover_switched_production_acceptance_pending":
    fail("cutover evidence is not waiting for production acceptance")
if cutover.get("state") != "switched" or cutover.get("postCutoverRealUserAcceptance") != "pending":
    fail("cutover evidence state mismatch")
if cutover.get("branchCommit") != commit:
    fail("cutover commit mismatch")

expected_acceptance_keys = {
    "schemaVersion", "status", "branchCommit", "cutoverEvidenceSha256",
    "webBuildIdentity", "weappBuildIdentity", "testedRoutes",
    "realWechatQrLogin", "crossClientChat", "crossClientSimc",
    "ownerIsolation", "logoutIndependence", "serviceRestartRecovery",
    "userConfirmation", "firstAcceptedWriteAt", "acceptedAt",
}
if set(acceptance) != expected_acceptance_keys:
    fail("production acceptance fields are not exact")
if acceptance.get("schemaVersion") != "chickenbro-production-dual-client-acceptance-v1":
    fail("production acceptance schema mismatch")
if acceptance.get("status") != "production_dual_client_acceptance_passed":
    fail("production acceptance status is not passed")
if acceptance.get("branchCommit") != commit:
    fail("production acceptance commit mismatch")
if acceptance.get("cutoverEvidenceSha256") != cutover_sha:
    fail("production acceptance is not bound to the switched cutover evidence")
if acceptance.get("webBuildIdentity") != cutover.get("webBuildIdentity"):
    fail("production acceptance Web build mismatch")
if acceptance.get("weappBuildIdentity") != cutover.get("weappBuildIdentity"):
    fail("production acceptance WeApp build mismatch")
expected_routes = {
    "pages/chickenbro/index",
    "pages/simc/index",
    "pages/simc/tasks",
    "pages/simc/task-detail",
    "pages/auth/web-login-confirm",
}
routes = acceptance.get("testedRoutes")
if not isinstance(routes, list) or len(routes) != len(expected_routes) or set(routes) != expected_routes:
    fail("production acceptance route set mismatch")
for key, hash_key in (
    ("realWechatQrLogin", "evidenceHash"),
    ("crossClientChat", "objectHash"),
    ("crossClientSimc", "objectHash"),
    ("ownerIsolation", "objectHash"),
    ("logoutIndependence", "evidenceHash"),
    ("serviceRestartRecovery", "evidenceHash"),
):
    require_passed_check(acceptance, key, hash_key)
confirmation = acceptance.get("userConfirmation")
if (
    not isinstance(confirmation, dict)
    or confirmation.get("status") != "accepted"
    or sha.fullmatch(str(confirmation.get("evidenceHash", ""))) is None
):
    fail("explicit user confirmation is missing")
reject_secrets(acceptance)

boundary_at = boundary_path.read_text(encoding="utf-8").strip()
if cutover.get("writeAuthorityBoundaryAt") != boundary_at:
    fail("write authority boundary mismatch")
boundary_time = parse_time(boundary_at, "write authority boundary")
first_write_time = parse_time(acceptance.get("firstAcceptedWriteAt"), "first accepted write")
accepted_time = parse_time(acceptance.get("acceptedAt"), "production acceptance")
if first_write_time < boundary_time or accepted_time < first_write_time:
    fail("production acceptance timestamps are not monotonic")

updated = dict(cutover)
updated.update({
    "status": "production_cutover_accepted_write_real_user_acceptance_passed",
    "state": "accepted_write",
    "firstNewWriteAt": acceptance["firstAcceptedWriteAt"],
    "productionAcceptanceSha256": acceptance_sha,
    "postCutoverRealUserAcceptance": "passed",
    "acceptedAt": acceptance["acceptedAt"],
})
serialized = json.dumps(updated, sort_keys=True, separators=(",", ":")) + "\n"
try:
    descriptor = os.open(sealed_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    fail("stale sealed evidence already exists")
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    output.write(serialized)
PY

advance_state() {
  local requested="$1"
  local current
  current="$(<"${STATE_FILE}")"
  [[ "${current}" == "switched" && "${requested}" == "accepted_write" ]] \
    || die_remote "invalid cutover state transition: ${current} -> ${requested}"
  printf '%s\n' "${requested}" > "${STATE_FILE}.new"
  chmod 0600 "${STATE_FILE}.new"
  mv -Tf "${STATE_FILE}.new" "${STATE_FILE}"
}

advance_state accepted_write
mv -Tf "${SEALED_EVIDENCE}" "${CUTOVER_EVIDENCE_PATH}"
SEALED_SHA="$(sha256sum "${CUTOVER_EVIDENCE_PATH}" | awk '{print $1}')"
printf 'state=accepted_write evidence=%s evidenceSha256=%s rollback=legacy_read_only\n' \
  "${CUTOVER_EVIDENCE_PATH}" "${SEALED_SHA}"
REMOTE_SEAL
  exit 0
fi

# Candidate builds intentionally use /api/v2-candidate. Production artifacts are
# rebuilt from the same clean commit with the final transport and cookie owners.
printf 'Building exact production H5 and WeApp for %s\n' "${CANDIDATE_COMMIT}"
(
  cd "${REPO_ROOT}"
  NODE_ENV=production \
  WOW_BACKEND_API_BASE_URL="https://api.chickenbro.cloud" \
  WOW_API_V2_PREFIX="/api/v2" \
  WOW_WEB_AUTH_API_PREFIX="/api/v2" \
  WOW_WEB_CSRF_COOKIE_NAME="__Host-chickenbro-csrf" \
  WOW_H5_PUBLIC_PATH="/" \
  npm --workspace @wow-mini/mini-taro run build:h5
)
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/h5/index.html" ]] || die "production H5 build is missing"
(
  cd "${REPO_ROOT}"
  NODE_ENV=production \
  WOW_BACKEND_API_BASE_URL="https://api.chickenbro.cloud" \
  WOW_API_V2_PREFIX="/api/v2" \
  WOW_WEB_AUTH_API_PREFIX="/api/v2" \
  WOW_WEB_CSRF_COOKIE_NAME="__Host-chickenbro-csrf" \
  npm --workspace @wow-mini/mini-taro run build:weapp
)
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/weapp/wow-build.json" ]] \
  || die "production WeApp build identity is missing"
python3 - "${REPO_ROOT}/apps/mini-taro/dist/weapp/wow-build.json" "${CANDIDATE_COMMIT}" <<'PY'
import json
import re
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("schemaRevision") != "wow-weapp-build-v1":
    raise SystemExit("production WeApp identity schema mismatch")
if payload.get("gitHead") != sys.argv[2]:
    raise SystemExit("production WeApp gitHead mismatch")
if re.fullmatch(r"sha256:[0-9a-f]{64}", str(payload.get("sourceHash", ""))) is None:
    raise SystemExit("production WeApp source hash is invalid")
PY
PRODUCTION_WEB_BUILD_IDENTITY="$(directory_sha256 "${REPO_ROOT}/apps/mini-taro/dist/h5")"
PRODUCTION_WEAPP_BUILD_IDENTITY="$(directory_sha256 "${REPO_ROOT}/apps/mini-taro/dist/weapp")"
validate_value PRODUCTION_WEB_BUILD_IDENTITY "${PRODUCTION_WEB_BUILD_IDENTITY}" '^[0-9a-f]{64}$'
validate_value PRODUCTION_WEAPP_BUILD_IDENTITY "${PRODUCTION_WEAPP_BUILD_IDENTITY}" '^[0-9a-f]{64}$'

LOCAL_STAGE="$(mktemp -d -t chickenbro-production-stage.XXXXXX)"
LOCAL_PACKAGE_DIR="$(mktemp -d -t chickenbro-production-package.XXXXXX)"
REMOTE_ARCHIVE=""
cleanup_local() {
  local exit_code=$?
  rm -rf "${LOCAL_STAGE}" "${LOCAL_PACKAGE_DIR}"
  exit "${exit_code}"
}
trap cleanup_local EXIT

git -C "${REPO_ROOT}" archive "${CANDIDATE_COMMIT}" -- \
  server/__init__.py \
  server/app \
  server/codex_worker.py \
  server/chickenbro_native_mcp.py \
  server/chickenbro_public_web_research.py \
  server/chickenbro_simc_runtime_update.sh \
  server/chickenbro-simc-runtime-update.service \
  server/migrations/__init__.py \
  server/migrations/product \
  server/chickenbro-api.service \
  server/chickenbro-worker.service \
  scripts/chickenbro-native-agent/chickenbro-native.config.toml.template | tar -xf - -C "${LOCAL_STAGE}"
mkdir -p "${LOCAL_STAGE}/apps/mini-taro/dist"
cp -R "${REPO_ROOT}/apps/mini-taro/dist/h5" "${LOCAL_STAGE}/apps/mini-taro/dist/h5"
cp -R "${REPO_ROOT}/apps/mini-taro/dist/weapp" "${LOCAL_STAGE}/apps/mini-taro/dist/weapp"
printf '%s\n' "${CANDIDATE_COMMIT}" > "${LOCAL_STAGE}/BRANCH_COMMIT"
printf '%s\n' "${PRODUCTION_WEB_BUILD_IDENTITY}" > "${LOCAL_STAGE}/WEB_BUILD_IDENTITY"
printf '%s\n' "${PRODUCTION_WEAPP_BUILD_IDENTITY}" > "${LOCAL_STAGE}/WEAPP_BUILD_IDENTITY"

python3 - "${LOCAL_STAGE}" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = root / "deploy-manifest.sha256"
lines = []
for path in sorted(item for item in root.rglob("*") if item.is_file() and item != manifest):
    relative = path.relative_to(root).as_posix()
    if "\n" in relative or "\r" in relative:
        raise SystemExit("unsafe deployment path")
    lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
descriptor = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    output.write("\n".join(lines) + "\n")
PY

PRODUCTION_MANIFEST_SHA256="$(sha256_file "${LOCAL_STAGE}/deploy-manifest.sha256")"
TEMP_ARCHIVE="${LOCAL_PACKAGE_DIR}/production.tar.gz"
COPYFILE_DISABLE=1 tar --format=ustar -czf "${TEMP_ARCHIVE}" -C "${LOCAL_STAGE}" .
PRODUCTION_ARCHIVE_SHA256="$(sha256_file "${TEMP_ARCHIVE}")"
PRODUCTION_ARCHIVE="${LOCAL_PACKAGE_DIR}/chickenbro-production-${PRODUCTION_ARCHIVE_SHA256}.tar.gz"
mv "${TEMP_ARCHIVE}" "${PRODUCTION_ARCHIVE}"
REMOTE_ARCHIVE="/tmp/chickenbro-production-${PRODUCTION_ARCHIVE_SHA256}.tar.gz"
scp_remote "${PRODUCTION_ARCHIVE}" "${SSH_TARGET}:${REMOTE_ARCHIVE}"

REMOTE_ENV=(
  "REMOTE_USER=${REMOTE_USER}"
  "BACKUP_MODE=${BACKUP_MODE}"
  "CANDIDATE_COMMIT=${CANDIDATE_COMMIT}"
  "REVIEWED_INVENTORY_SHA=${REVIEWED_INVENTORY_SHA}"
  "REVIEWED_BACKUP_MANIFEST_SHA=${REVIEWED_BACKUP_MANIFEST_SHA}"
  "CANDIDATE_EVIDENCE_PATH=${CANDIDATE_EVIDENCE_PATH}"
  "CANDIDATE_EVIDENCE_SHA=${CANDIDATE_EVIDENCE_SHA}"
  "REAL_ACCEPTANCE_PATH=${REAL_ACCEPTANCE_PATH}"
  "REAL_ACCEPTANCE_SHA=${REAL_ACCEPTANCE_SHA}"
  "REMOTE_BACKUP_MANIFEST=${REMOTE_BACKUP_MANIFEST}"
  "REMOTE_CUTOVER_ROOT=${REMOTE_CUTOVER_ROOT}"
  "REMOTE_ARCHIVE=${REMOTE_ARCHIVE}"
  "PRODUCTION_ARCHIVE_SHA256=${PRODUCTION_ARCHIVE_SHA256}"
  "PRODUCTION_MANIFEST_SHA256=${PRODUCTION_MANIFEST_SHA256}"
  "PRODUCTION_WEB_BUILD_IDENTITY=${PRODUCTION_WEB_BUILD_IDENTITY}"
  "PRODUCTION_WEAPP_BUILD_IDENTITY=${PRODUCTION_WEAPP_BUILD_IDENTITY}"
  "PRODUCTION_ROOT=${PRODUCTION_ROOT}"
  "CANDIDATE_ROOT=${CANDIDATE_ROOT}"
  "RUNTIME_ROOT=${RUNTIME_ROOT}"
  "PRODUCTION_DATABASE=${PRODUCTION_DATABASE}"
  "SOURCE_DATABASE=${SOURCE_DATABASE}"
  "PRODUCTION_PORT=${PRODUCTION_PORT}"
  "PRODUCTION_API_SERVICE=${PRODUCTION_API_SERVICE}"
  "PRODUCTION_WORKER_SERVICE=${PRODUCTION_WORKER_SERVICE}"
  "SIMC_UPDATE_SERVICE=${SIMC_UPDATE_SERVICE}"
  "CANDIDATE_API_SERVICE=${CANDIDATE_API_SERVICE}"
  "CANDIDATE_WORKER_SERVICE=${CANDIDATE_WORKER_SERVICE}"
  "PRODUCTION_API_ENV=${PRODUCTION_API_ENV}"
  "PRODUCTION_SOURCE_ENV=${PRODUCTION_SOURCE_ENV}"
  "PRODUCTION_WORKER_ENV=${PRODUCTION_WORKER_ENV}"
  "PRODUCTION_PGPASSFILE=${PRODUCTION_PGPASSFILE}"
  "PRODUCTION_CODEX_PROFILE=${PRODUCTION_CODEX_PROFILE}"
  "LEGACY_API_ENV=${LEGACY_API_ENV}"
  "LEGACY_SOURCE_ENV=${LEGACY_SOURCE_ENV}"
  "WWW_NGINX_SITE=${WWW_NGINX_SITE}"
  "API_NGINX_SITE=${API_NGINX_SITE}"
  "PRODUCTION_WEB_ROOT=${PRODUCTION_WEB_ROOT}"
)

remote_env_args() {
  local item
  for item in "${REMOTE_ENV[@]}"; do
    printf '%q ' "${item}"
  done
}

printf 'Running production cutover for %s\n' "${CANDIDATE_COMMIT}"
ssh_remote "$(remote_env_args) sudo -E bash -s" <<'REMOTE_CUTOVER'
set -euo pipefail

die_remote() {
  printf 'cutover_chickenbro remote: %s\n' "$*" >&2
  exit 1
}

validate_nginx_owner() {
  local label="$1"
  local site="$2"
  local owner="$3"
  local allowed_legacy_enabled="${4:-}"
  [[ -f "${site}" && -f "${owner}" ]] || die_remote "${label} Nginx owner is missing"
  if [[ "${owner}" == /etc/nginx/sites-available/* ]]; then
    :
  elif [[ -n "${allowed_legacy_enabled}" \
    && "${site}" == "${allowed_legacy_enabled}" \
    && "${owner}" == "${allowed_legacy_enabled}" \
    && ! -L "${site}" ]]; then
    :
  else
    die_remote "${label} Nginx owner is outside the reviewed paths"
  fi
  [[ "$(stat -c '%U:%G:%a' "${owner}")" == "root:root:644" ]] \
    || die_remote "${label} Nginx owner metadata is invalid"
}

LEGACY_WRITER_UNITS=(
  wow-attribute-rule-audit.service
  wow-backend.service
  wow-v2-api.service
  wow-v2-worker.service
  wow-chickenbro-source-refresh.service
  wow-chickenbro-source-refresh.timer
  wow-community-best-guard-sync.service
  wow-community-best-guard-sync.timer
  wow-community-template-sync.service
  wow-community-template-sync.timer
  wow-data-health-followup.service
  wow-data-health-followup.timer
  wow-gear-observed-backfill.service
  wow-gear-observed-backfill.timer
  wow-gear-release-refresh.service
  wow-gear-release-refresh.timer
  wow-gear-stat-snapshot-worker.service
  wow-recommended-bis-guard-sync.service
  wow-recommended-bis-guard-sync.timer
  wow-recommended-bis-prototype-sync.service
  wow-season-recommended-gear-sync.service
  wow-season-recommended-gear-sync.timer
  wow-simc-runtime-update.service
  wow-simc-version-check.service
  wow-simc-version-check.timer
  wow-stat-weights-sync.service
  wow-stat-weights-sync.timer
  wow-talent-graph-recovery.service
  wow-websim-sync.service
  wow-websim-sync.timer
)
LEGACY_ALREADY_MASKED_UNITS=(
  wow-news-backend.service
  wow-v2-api-candidate.service
)
STATE_SEQUENCE=(preflight write_fenced delta_migrated switched accepted_write)

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${CANDIDATE_COMMIT:0:12}"
RUN_DIR="${REMOTE_CUTOVER_ROOT}/${RUN_ID}"
STAGE_DIR="/opt/chickenbro-cutover-staging/${RUN_ID}"
CODE_NEW_DIR="${PRODUCTION_ROOT}.new-${RUN_ID}"
WEB_RELEASE_DIR="${PRODUCTION_WEB_ROOT}/releases/${PRODUCTION_WEB_BUILD_IDENTITY}"
WEB_CURRENT_LINK="${PRODUCTION_WEB_ROOT}/current"
STATE_FILE="${RUN_DIR}/STATE"
WRITE_AUTHORITY_BOUNDARY="${RUN_DIR}/WRITE_AUTHORITY_BOUNDARY"
FULL_MIGRATION_REPORT="${RUN_DIR}/full-migration.json"
DELTA_MIGRATION_REPORT="${RUN_DIR}/delta-migration.json"
CUTOVER_EVIDENCE="${RUN_DIR}/production-cutover.json"
MUTATION_STARTED="0"
BACKUP_COMPLETE="0"

advance_state() {
  local requested="$1"
  local current current_index="-1" requested_index="-1" index
  current="$(<"${STATE_FILE}")"
  for index in "${!STATE_SEQUENCE[@]}"; do
    [[ "${STATE_SEQUENCE[$index]}" == "${current}" ]] && current_index="${index}"
    [[ "${STATE_SEQUENCE[$index]}" == "${requested}" ]] && requested_index="${index}"
  done
  (( current_index >= 0 && requested_index == current_index + 1 )) \
    || die_remote "invalid cutover state transition: ${current} -> ${requested}"
  printf '%s\n' "${requested}" > "${STATE_FILE}.new"
  chmod 0600 "${STATE_FILE}.new"
  mv -Tf "${STATE_FILE}.new" "${STATE_FILE}"
}

service_state() {
  systemctl is-active --quiet "$1" && printf '%s\n' active || printf '%s\n' inactive
}

enable_state() {
  systemctl is-enabled --quiet "$1" && printf '%s\n' enabled || printf '%s\n' disabled
}

restore_file() {
  local target="$1"
  local label="$2"
  local mode="0600"
  local owner="root"
  local group="root"
  case "${label}" in
    *.service) mode="0644" ;;
    production-codex-profile) owner="${REMOTE_USER}"; group="${REMOTE_USER}" ;;
  esac
  if [[ "$(<"${RUN_DIR}/${label}.state")" == "present" ]]; then
    install --preserve-timestamps -o "${owner}" -g "${group}" -m "${mode}" \
      "${RUN_DIR}/${label}" "${target}"
  else
    rm -f -- "${target}"
  fi
}

restore_unit_states() {
  local unit
  for unit in "${LEGACY_WRITER_UNITS[@]}"; do
    systemctl unmask --runtime "${unit}" >/dev/null 2>&1 || true
    if [[ "$(<"${RUN_DIR}/unit-${unit}.enabled")" == "enabled" ]]; then
      systemctl enable "${unit}" >/dev/null 2>&1 || true
    fi
  done
  systemctl daemon-reload
  for unit in "${LEGACY_WRITER_UNITS[@]}"; do
    if [[ "$(<"${RUN_DIR}/unit-${unit}.active")" == "active" ]]; then
      systemctl start "${unit}"
    fi
  done
}

install_maintenance_api_route() {
  python3 - "${API_NGINX_OWNER}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
begin = "# BEGIN CHICKENBRO PRODUCTION API"
end = "# END CHICKENBRO PRODUCTION API"
while begin in text:
    left, rest = text.split(begin, 1)
    if end not in rest:
        raise SystemExit("unterminated production API section")
    _, right = rest.split(end, 1)
    text = left.rstrip() + "\n" + right.lstrip("\n")
section = """# BEGIN CHICKENBRO PRODUCTION API
location ^~ /api/v2/ {
    default_type application/json;
    return 503 '{\"error\":{\"code\":\"CUTOVER_RECOVERY\",\"message\":\"The service is temporarily read-only.\"}}';
}
# END CHICKENBRO PRODUCTION API"""
position = text.rfind("\n}")
if position < 0:
    raise SystemExit("API Nginx owner is invalid")
path.write_text(text[:position].rstrip() + "\n\n" + section + "\n" + text[position:], encoding="utf-8")
PY
}

pre_write_rollback() {
  [[ ! -e "${WRITE_AUTHORITY_BOUNDARY}" ]] \
    || die_remote "WRITE_AUTHORITY_BOUNDARY exists; pre-write rollback is forbidden"
  [[ "${BACKUP_COMPLETE}" == "1" ]] || return 0
  systemctl stop "${PRODUCTION_API_SERVICE}" "${PRODUCTION_WORKER_SERVICE}" >/dev/null 2>&1 || true
  restore_file "/etc/systemd/system/${PRODUCTION_API_SERVICE}.service" production-api.service
  restore_file "/etc/systemd/system/${PRODUCTION_WORKER_SERVICE}.service" production-worker.service
  restore_file "/etc/systemd/system/${SIMC_UPDATE_SERVICE}.service" simc-runtime-update.service
  restore_file "${PRODUCTION_API_ENV}" production-api.env
  restore_file "${PRODUCTION_SOURCE_ENV}" production-source.env
  restore_file "${PRODUCTION_WORKER_ENV}" production-worker.env
  restore_file "${PRODUCTION_PGPASSFILE}" production.pgpass
  restore_file "${PRODUCTION_CODEX_PROFILE}" production-codex-profile
  install -o root -g root -m 0644 "${RUN_DIR}/www.nginx" "${WWW_NGINX_OWNER}"
  install -o root -g root -m 0644 "${RUN_DIR}/api.nginx" "${API_NGINX_OWNER}"
  if [[ -d "${PRODUCTION_ROOT}" ]]; then
    mv "${PRODUCTION_ROOT}" "${RUN_DIR}/failed-production-root"
  fi
  if [[ "$(<"${RUN_DIR}/production-root.state")" == "present" ]]; then
    install -d -o root -g root -m 0755 "${PRODUCTION_ROOT}"
    tar -xzf "${RUN_DIR}/production-root.tar.gz" -C "${PRODUCTION_ROOT}"
  fi
  rm -f "${WEB_CURRENT_LINK}"
  if [[ "$(<"${RUN_DIR}/web-current.state")" == "present" ]]; then
    ln -s "$(<"${RUN_DIR}/web-current.target")" "${WEB_CURRENT_LINK}"
  fi
  sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
    --command="ALTER DATABASE wow_test RESET default_transaction_read_only" \
    --command="ALTER ROLE wow_app IN DATABASE wow_test RESET default_transaction_read_only" >/dev/null
  restore_unit_states
  systemctl daemon-reload
  nginx -t
  systemctl reload nginx
  systemctl unmask --runtime "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
  if [[ "$(<"${RUN_DIR}/candidate-api.enabled")" == "enabled" ]]; then
    systemctl enable "${CANDIDATE_API_SERVICE}" >/dev/null 2>&1 || true
  fi
  if [[ "$(<"${RUN_DIR}/candidate-worker.enabled")" == "enabled" ]]; then
    systemctl enable "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
  fi
  if [[ "$(<"${RUN_DIR}/candidate-api.active")" == "active" ]]; then
    systemctl start "${CANDIDATE_API_SERVICE}"
  fi
  if [[ "$(<"${RUN_DIR}/candidate-worker.active")" == "active" ]]; then
    systemctl start "${CANDIDATE_WORKER_SERVICE}"
  fi
  if [[ "$(<"${RUN_DIR}/production-api.active")" == "active" ]]; then
    systemctl start "${PRODUCTION_API_SERVICE}"
  fi
  if [[ "$(<"${RUN_DIR}/production-worker.active")" == "active" ]]; then
    systemctl start "${PRODUCTION_WORKER_SERVICE}"
  fi
  printf '%s\n' pre_write_rollback_completed > "${RUN_DIR}/ROLLBACK_STATE"
  chmod 0600 "${RUN_DIR}/ROLLBACK_STATE"
}

post_write_recovery() {
  printf '%s\n' legacy_read_only > "${RUN_DIR}/ROLLBACK_CLASSIFICATION"
  chmod 0600 "${RUN_DIR}/ROLLBACK_CLASSIFICATION"
  systemctl stop "${PRODUCTION_API_SERVICE}" "${PRODUCTION_WORKER_SERVICE}" >/dev/null 2>&1 || true
  sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
    --command="ALTER DATABASE wow_test SET default_transaction_read_only = on" \
    --command="ALTER ROLE wow_app IN DATABASE wow_test SET default_transaction_read_only = on" \
    --command="ALTER DATABASE chickenbro_prod SET default_transaction_read_only = on" \
    --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('wow_test','chickenbro_prod') AND pid <> pg_backend_pid()" >/dev/null
  install_maintenance_api_route
  nginx -t
  systemctl reload nginx
  printf '%s\n' post_write_recovery_new_data_plane_only > "${RUN_DIR}/ROLLBACK_STATE"
  chmod 0600 "${RUN_DIR}/ROLLBACK_STATE"
}

handle_failure() {
  local exit_code=$?
  trap - EXIT
  if [[ "${MUTATION_STARTED}" == "1" ]]; then
    if [[ -e "${WRITE_AUTHORITY_BOUNDARY}" ]]; then
      post_write_recovery || true
    else
      pre_write_rollback || true
    fi
  fi
  rm -f -- "${REMOTE_ARCHIVE}"
  rm -f -- "${PRODUCTION_PGPASSFILE}.new" "${PRODUCTION_API_ENV}.new" \
    "${PRODUCTION_WORKER_ENV}.new" "${PRODUCTION_CODEX_PROFILE}.new-${RUN_ID}" \
    "${WEB_CURRENT_LINK}.new"
  rm -f -- "${WWW_NGINX_OWNER:-/nonexistent}.cutover" "${API_NGINX_OWNER:-/nonexistent}.cutover"
  rm -rf -- "${STAGE_DIR}" "${CODE_NEW_DIR}"
  exit "${exit_code}"
}
trap handle_failure EXIT

for command_name in python3 psql nginx systemctl tar sha256sum curl stat df awk grep readlink install mv cp find; do
  command -v "${command_name}" >/dev/null 2>&1 || die_remote "missing command: ${command_name}"
done
[[ -f "${REMOTE_ARCHIVE}" ]] || die_remote "production archive is missing"
[[ "$(sha256sum "${REMOTE_ARCHIVE}" | awk '{print $1}')" == "${PRODUCTION_ARCHIVE_SHA256}" ]] \
  || die_remote "production archive SHA mismatch"
if [[ "${BACKUP_MODE}" == "independent" ]]; then
  [[ -f "${REMOTE_BACKUP_MANIFEST}" ]] || die_remote "independent backup manifest is missing"
  [[ "$(sha256sum "${REMOTE_BACKUP_MANIFEST}" | awk '{print $1}')" == "${REVIEWED_BACKUP_MANIFEST_SHA}" ]] \
    || die_remote "independent backup manifest SHA mismatch"
elif [[ "${BACKUP_MODE}" == "none_user_authorized" ]]; then
  [[ -z "${REVIEWED_BACKUP_MANIFEST_SHA}" ]] \
    || die_remote "no-backup cutover received an independent backup identity"
else
  die_remote "unknown backup mode"
fi
[[ -f "${CANDIDATE_EVIDENCE_PATH}" ]] || die_remote "candidate acceptance evidence is missing"
[[ "$(sha256sum "${CANDIDATE_EVIDENCE_PATH}" | awk '{print $1}')" == "${CANDIDATE_EVIDENCE_SHA}" ]] \
  || die_remote "candidate acceptance SHA mismatch"
[[ -f "${REAL_ACCEPTANCE_PATH}" ]] || die_remote "real dual-client acceptance evidence is missing"
[[ "$(sha256sum "${REAL_ACCEPTANCE_PATH}" | awk '{print $1}')" == "${REAL_ACCEPTANCE_SHA}" ]] \
  || die_remote "real acceptance SHA mismatch"

python3 - "${REMOTE_BACKUP_MANIFEST}" "${CANDIDATE_EVIDENCE_PATH}" "${REAL_ACCEPTANCE_PATH}" \
  "${CANDIDATE_COMMIT}" "${CANDIDATE_EVIDENCE_SHA}" "${REVIEWED_INVENTORY_SHA}" \
  "${REVIEWED_BACKUP_MANIFEST_SHA}" "${BACKUP_MODE}" <<'PY'
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

backup_path, candidate_path, real_path = map(Path, sys.argv[1:4])
commit, candidate_sha, inventory_sha, backup_sha = sys.argv[4:8]
backup_mode = sys.argv[8] if len(sys.argv) > 8 else "independent"
sha = re.compile(r"[0-9a-f]{64}\Z")

def fail(message):
    raise SystemExit(message)

def read_private(path, label):
    if path.is_symlink() or path.stat().st_mode & 0o077:
        fail(f"{label} must be a mode-0600 regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return value

def parse_time(value, label):
    if not isinstance(value, str) or not value.endswith("Z"):
        fail(f"{label} timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{label} timestamp is invalid")
    if parsed.utcoffset() is None:
        fail(f"{label} timestamp is invalid")
    return parsed

def verify_file(raw_path, root, expected_sha, expected_bytes=None):
    path = Path(raw_path)
    if not path.is_absolute() or path.is_symlink():
        fail("independent backup manifest is not restore-verified")
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root):
        fail("independent backup manifest is not restore-verified")
    metadata = resolved.stat()
    if metadata.st_dev != root.stat().st_dev:
        fail("independent backup manifest is not restore-verified")
    if expected_bytes is not None and metadata.st_size != expected_bytes:
        fail("independent backup manifest is not restore-verified")
    digest = hashlib.sha256()
    with resolved.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha:
        fail("independent backup manifest is not restore-verified")

if backup_mode == "independent":
    backup = read_private(backup_path, "independent backup manifest")
    required_backup_keys = {
        "schemaVersion", "backupId", "sourceDatabase", "archivePath", "archiveSha256",
        "archiveBytes", "createdAt", "deviceId", "encrypted",
        "sensitiveConfigurationEncrypted", "encryption", "restoreVerified", "restore",
    }
    if set(backup) != required_backup_keys or backup.get("schemaVersion") != "chickenbro-independent-backup-v1":
        fail("independent backup manifest is not restore-verified")
    if backup.get("sourceDatabase") != "wow_test" or backup.get("restoreVerified") is not True:
        fail("independent backup manifest is not restore-verified")
    if backup.get("encrypted") is not True or backup.get("sensitiveConfigurationEncrypted") is not True:
        fail("independent backup manifest is not restore-verified")
    root = backup_path.parent.resolve(strict=True)
    if str(backup.get("deviceId")) != str(root.stat().st_dev):
        fail("independent backup manifest is not restore-verified")
    archive_sha = str(backup.get("archiveSha256", ""))
    archive_bytes = backup.get("archiveBytes")
    if sha.fullmatch(archive_sha) is None or not isinstance(archive_bytes, int) or isinstance(archive_bytes, bool) or archive_bytes <= 0:
        fail("independent backup manifest is not restore-verified")
    encryption = backup.get("encryption")
    if not isinstance(encryption, dict) or encryption.get("scheme") not in {"age", "gpg", "kms-envelope"}:
        fail("independent backup manifest is not restore-verified")
    if sha.fullmatch(str(encryption.get("keyReferenceSha256", ""))) is None:
        fail("independent backup manifest is not restore-verified")
    restore = backup.get("restore")
    expected_restore_keys = {
        "targetDatabase", "commandExitCode", "schemaVerified", "rowSampleVerified",
        "hashSampleVerified", "verifiedAt", "operator", "evidencePath", "evidenceSha256",
    }
    if not isinstance(restore, dict) or set(restore) != expected_restore_keys:
        fail("independent backup manifest is not restore-verified")
    if not re.fullmatch(r"chickenbro_restore_verify_[a-z0-9_]{1,40}", str(restore.get("targetDatabase", ""))):
        fail("independent backup manifest is not restore-verified")
    if any(restore.get(key) is not True for key in ("schemaVerified", "rowSampleVerified", "hashSampleVerified")):
        fail("independent backup manifest is not restore-verified")
    if restore.get("commandExitCode") != 0 or sha.fullmatch(str(restore.get("evidenceSha256", ""))) is None:
        fail("independent backup manifest is not restore-verified")
    created_at = parse_time(backup.get("createdAt"), "backup")
    verified_at = parse_time(restore.get("verifiedAt"), "restore")
    if verified_at < created_at:
        fail("independent backup manifest is not restore-verified")
    verify_file(backup.get("archivePath"), root, archive_sha, archive_bytes)
    verify_file(restore.get("evidencePath"), root, str(restore.get("evidenceSha256")))
elif backup_mode == "none_user_authorized":
    backup = None
else:
    fail("unknown backup mode")

candidate = read_private(candidate_path, "candidate acceptance")
if candidate.get("status") != "candidate_deployed_user_acceptance_pending":
    fail("candidate acceptance status is not promotable")
if candidate.get("branchCommit") != commit:
    fail("candidate acceptance commit mismatch")
if candidate.get("inventorySha256") != inventory_sha:
    fail("candidate acceptance inventory mismatch")
if backup_mode == "independent":
    if candidate.get("independentBackupManifestSha256") != backup_sha:
        fail("candidate acceptance backup mismatch")
elif candidate.get("independentBackupManifestSha256") is not None:
    fail("no-backup candidate acceptance must not contain an independent backup identity")
if candidate.get("realDualClientAcceptance") != "pending":
    fail("candidate evidence must keep realDualClientAcceptance pending")
automated = candidate.get("automatedAcceptance")
if not isinstance(automated, dict) or automated.get("status") != "passed":
    fail("automated_candidate_acceptance_passed is missing")
if automated.get("report") != "automated-acceptance.json" or sha.fullmatch(str(automated.get("sha256", ""))) is None:
    fail("automated candidate acceptance reference is invalid")
automated_path = candidate_path.parent / "automated-acceptance.json"
if automated_path.is_symlink() or not automated_path.is_file():
    fail("automated candidate acceptance report is missing")
if hashlib.sha256(automated_path.read_bytes()).hexdigest() != automated.get("sha256"):
    fail("automated candidate acceptance report SHA mismatch")
automated_payload = json.loads(automated_path.read_text(encoding="utf-8"))
if automated_payload.get("status") != "automated_candidate_acceptance_passed":
    fail("automated_candidate_acceptance_passed is missing")
if automated_payload.get("branchCommit") != commit:
    fail("automated candidate acceptance commit mismatch")
for key in ("deployedManifestSha256", "webBuildIdentity", "weappBuildIdentity"):
    if sha.fullmatch(str(candidate.get(key, ""))) is None:
        fail(f"candidate {key} is invalid")
if automated_payload.get("webBuildIdentity") != candidate.get("webBuildIdentity"):
    fail("automated candidate Web build mismatch")
if automated_payload.get("weappBuildIdentity") != candidate.get("weappBuildIdentity"):
    fail("automated candidate WeApp build mismatch")
readiness = candidate.get("readiness")
if not isinstance(readiness, dict) or readiness.get("status") != "ready":
    fail("candidate readiness is not fully ready")
components = readiness.get("components")
if not isinstance(components, dict) or any(
    not isinstance(component, dict) or component.get("status") != "ready"
    for component in components.values()
):
    fail("candidate readiness is not fully ready")

real = read_private(real_path, "real acceptance")
if real.get("schemaVersion") != "chickenbro-real-dual-client-acceptance-v1":
    fail("real acceptance schema mismatch")
if real.get("status") != "real_dual_client_acceptance_passed":
    fail("real acceptance status is not passed")
if real.get("branchCommit") != commit or real.get("candidateEvidenceSha256") != candidate_sha:
    fail("real acceptance identity mismatch")
if real.get("webBuildIdentity") != candidate.get("webBuildIdentity"):
    fail("real acceptance Web build mismatch")
if real.get("weappBuildIdentity") != candidate.get("weappBuildIdentity"):
    fail("real acceptance WeApp build mismatch")
expected_routes = {
    "pages/chickenbro/index", "pages/simc/index", "pages/simc/tasks",
    "pages/simc/task-detail", "pages/auth/web-login-confirm",
}
if set(real.get("testedRoutes", [])) != expected_routes:
    fail("real acceptance route set mismatch")
for key in ("crossClientChat", "crossClientSimc", "ownerIsolation"):
    check = real.get(key)
    if not isinstance(check, dict) or check.get("status") != "passed" or sha.fullmatch(str(check.get("objectHash", ""))) is None:
        fail(f"real acceptance {key} is invalid")
parse_time(real.get("acceptedAt"), "real acceptance")

for payload in (candidate, real):
    serialized = json.dumps(payload, sort_keys=True).lower()
    for forbidden in ("access_token", "session_key", "provider_subject", "cookie_value", "wechat_secret"):
        if forbidden in serialized:
            fail("acceptance evidence contains a forbidden credential or provider subject")
PY

if [[ "${BACKUP_MODE}" == "independent" ]]; then
  BACKUP_DEVICE="$(stat -c '%d' "$(dirname -- "${REMOTE_BACKUP_MANIFEST}")")"
  POSTGRES_DEVICE="$(stat -c '%d' /var/lib/postgresql)"
  [[ "${BACKUP_DEVICE}" != "${POSTGRES_DEVICE}" ]] \
    || die_remote "backup and PostgreSQL data share a device"
fi
[[ -d "${CANDIDATE_ROOT}" ]] || die_remote "accepted candidate root is missing"
[[ "$(<"${CANDIDATE_ROOT}/BRANCH_COMMIT")" == "${CANDIDATE_COMMIT}" ]] \
  || die_remote "deployed candidate commit mismatch"
[[ "$(sha256sum "${CANDIDATE_ROOT}/deploy-manifest.sha256" | awk '{print $1}')" == "$(python3 - "${CANDIDATE_EVIDENCE_PATH}" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['deployedManifestSha256'])
PY
)" ]] || die_remote "deployed candidate manifest mismatch"

[[ -x "${RUNTIME_ROOT}/bin/python" ]] || die_remote "managed Chickenbro runtime is missing"
sudo -n -u "${REMOTE_USER}" "${RUNTIME_ROOT}/bin/python" -c 'import fastapi, httpx, psycopg, uvicorn' \
  || die_remote "managed runtime dependencies are incomplete"
[[ -x /opt/wow-simc/current/simc ]] || die_remote "SimulationCraft runtime is missing"
[[ -x /usr/local/bin/codex ]] || die_remote "Codex runtime is missing"
[[ -f "${LEGACY_API_ENV}" && "$(stat -c '%a' "${LEGACY_API_ENV}")" == "600" ]] \
  || die_remote "legacy API environment owner is missing"
[[ -f "${LEGACY_SOURCE_ENV}" && "$(stat -c '%a' "${LEGACY_SOURCE_ENV}")" == "600" ]] \
  || die_remote "legacy source environment owner is missing"
install -d -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0700 /var/lib/chickenbro

WWW_NGINX_OWNER="$(readlink -f -- "${WWW_NGINX_SITE}")"
API_NGINX_OWNER="$(readlink -f -- "${API_NGINX_SITE}")"
validate_nginx_owner WWW "${WWW_NGINX_SITE}" "${WWW_NGINX_OWNER}"
validate_nginx_owner API "${API_NGINX_SITE}" "${API_NGINX_OWNER}" \
  /etc/nginx/sites-enabled/api.chickenbro.cloud
grep -Eq 'server_name[[:space:]]+www\.chickenbro\.cloud' "${WWW_NGINX_OWNER}" \
  || die_remote "WWW Nginx owner mismatch"
grep -Eq 'server_name[[:space:]]+api\.chickenbro\.cloud' "${API_NGINX_OWNER}" \
  || die_remote "API Nginx owner mismatch"
grep -Eq 'root[[:space:]]+/var/www/chickenbro-web/current' "${WWW_NGINX_OWNER}" \
  || die_remote "WWW root is not the stable Chickenbro symlink"
grep -Eq 'location[[:space:]]+\^~[[:space:]]+/api/v2/' "${WWW_NGINX_OWNER}" \
  || die_remote "WWW production API route is missing"

install -d -o root -g root -m 0700 "${REMOTE_CUTOVER_ROOT}"
[[ ! -e "${RUN_DIR}" ]] || die_remote "cutover run already exists"
install -d -o root -g root -m 0700 "${RUN_DIR}"
install -d -o root -g root -m 0755 "${STAGE_DIR}"
tar -xzf "${REMOTE_ARCHIVE}" -C "${STAGE_DIR}"
[[ "$(sha256sum "${STAGE_DIR}/deploy-manifest.sha256" | awk '{print $1}')" == "${PRODUCTION_MANIFEST_SHA256}" ]] \
  || die_remote "production manifest SHA mismatch"
(
  cd "${STAGE_DIR}"
  sha256sum --check deploy-manifest.sha256 >/dev/null
)
[[ "$(<"${STAGE_DIR}/BRANCH_COMMIT")" == "${CANDIDATE_COMMIT}" ]] \
  || die_remote "production package commit mismatch"
[[ "$(<"${STAGE_DIR}/WEB_BUILD_IDENTITY")" == "${PRODUCTION_WEB_BUILD_IDENTITY}" ]] \
  || die_remote "production Web build identity mismatch"
[[ "$(<"${STAGE_DIR}/WEAPP_BUILD_IDENTITY")" == "${PRODUCTION_WEAPP_BUILD_IDENTITY}" ]] \
  || die_remote "production WeApp build identity mismatch"

set +u
set -a
. "${LEGACY_API_ENV}"
set +a
set -u
LEGACY_DATABASE_URL="${WOW_DATABASE_URL:-}"
LEGACY_PGPASSFILE="${PGPASSFILE:-}"
[[ -n "${LEGACY_DATABASE_URL}" && -n "${LEGACY_PGPASSFILE}" ]] \
  || die_remote "legacy database connection owner is incomplete"
[[ -f "${LEGACY_PGPASSFILE}" && "$(stat -c '%a' "${LEGACY_PGPASSFILE}")" == "600" ]] \
  || die_remote "legacy PGPASSFILE is missing or not mode 0600"
[[ -n "${WOW_WECHAT_APPID:-}" && -n "${WOW_WECHAT_SECRET:-}" ]] \
  || die_remote "formal WeChat credentials are missing"

export LEGACY_DATABASE_URL PRODUCTION_DATABASE PRODUCTION_API_ENV PRODUCTION_WORKER_ENV
export PRODUCTION_PGPASSFILE REMOTE_USER WOW_WECHAT_APPID WOW_WECHAT_SECRET
python3 - <<'PY'
import os
from urllib.parse import urlsplit

parsed = urlsplit(os.environ["LEGACY_DATABASE_URL"])
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
PY

PGPASS_TMP="$(mktemp)"
if ! awk -F: -v target_database="${PRODUCTION_DATABASE}" '
  BEGIN { OFS = FS }
  $1 == "127.0.0.1" && $2 == "5432" && $3 == "wow_test" && $4 == "wow_app" {
    print
    $3 = target_database
    print
    found = 1
  }
  END { exit found ? 0 : 1 }
' "${LEGACY_PGPASSFILE}" > "${PGPASS_TMP}"; then
  rm -f "${PGPASS_TMP}"
  die_remote "legacy PGPASSFILE has no reviewed wow_test wow_app entry"
fi
install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${PGPASS_TMP}" "${PRODUCTION_PGPASSFILE}.new"
rm -f "${PGPASS_TMP}"
TARGET_DATABASE_URL="postgresql://wow_app@127.0.0.1:5432/${PRODUCTION_DATABASE}"

DATABASE_EXISTS="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT count(*) FROM pg_database WHERE datname = '${PRODUCTION_DATABASE}'")"
[[ "${DATABASE_EXISTS}" == "1" ]] || die_remote "clean production database is missing"
MIGRATION_IDS="$(sudo -n -u postgres psql -At --dbname="${PRODUCTION_DATABASE}" \
  --command="SELECT string_agg(id, ',' ORDER BY id) FROM ops.schema_migrations")"
[[ "${MIGRATION_IDS}" == "0001_chickenbro_simc_core,0002_chat_idempotent_replay" ]] \
  || die_remote "production database migration identity mismatch"
TARGET_CONNECTION_COUNT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT count(*) FROM pg_stat_activity WHERE datname = '${PRODUCTION_DATABASE}'")"
[[ "${TARGET_CONNECTION_COUNT}" == "0" ]] || die_remote "production database has unexpected active connections"
SOURCE_DATABASE_DEFAULT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT COALESCE(array_to_string(datconfig, ','), '') FROM pg_database WHERE datname = 'wow_test'")"
SOURCE_ROLE_DEFAULT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT COALESCE(array_to_string(setconfig, ','), '') FROM pg_db_role_setting WHERE setdatabase = (SELECT oid FROM pg_database WHERE datname = 'wow_test') AND setrole = (SELECT oid FROM pg_roles WHERE rolname = 'wow_app')")"
TARGET_DATABASE_DEFAULT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT COALESCE(array_to_string(datconfig, ','), '') FROM pg_database WHERE datname = 'chickenbro_prod'")"
TARGET_ROLE_DEFAULT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT COALESCE(array_to_string(setconfig, ','), '') FROM pg_db_role_setting WHERE setdatabase = (SELECT oid FROM pg_database WHERE datname = 'chickenbro_prod') AND setrole = (SELECT oid FROM pg_roles WHERE rolname = 'wow_app')")"
[[ "${SOURCE_DATABASE_DEFAULT}" != *"default_transaction_read_only=on"* ]] \
  || die_remote "source database is already fenced by an earlier cutover"
[[ "${SOURCE_ROLE_DEFAULT}" != *"default_transaction_read_only=on"* ]] \
  || die_remote "source role is already fenced by an earlier cutover"
[[ "${TARGET_DATABASE_DEFAULT}" != *"default_transaction_read_only=on"* ]] \
  || die_remote "production database is read-only from an earlier recovery"
[[ "${TARGET_ROLE_DEFAULT}" != *"default_transaction_read_only=on"* ]] \
  || die_remote "production role is read-only from an earlier recovery"

for pair in \
  "/etc/systemd/system/${PRODUCTION_API_SERVICE}.service:production-api.service" \
  "/etc/systemd/system/${PRODUCTION_WORKER_SERVICE}.service:production-worker.service" \
  "/etc/systemd/system/${SIMC_UPDATE_SERVICE}.service:simc-runtime-update.service" \
  "${PRODUCTION_API_ENV}:production-api.env" \
  "${PRODUCTION_SOURCE_ENV}:production-source.env" \
  "${PRODUCTION_WORKER_ENV}:production-worker.env" \
  "${PRODUCTION_PGPASSFILE}:production.pgpass" \
  "${PRODUCTION_CODEX_PROFILE}:production-codex-profile"; do
  source_path="${pair%%:*}"
  backup_label="${pair#*:}"
  if [[ -f "${source_path}" ]]; then
    cp --preserve=mode,ownership,timestamps "${source_path}" "${RUN_DIR}/${backup_label}"
    printf '%s\n' present > "${RUN_DIR}/${backup_label}.state"
  else
    printf '%s\n' absent > "${RUN_DIR}/${backup_label}.state"
  fi
done
cp --preserve=mode,ownership,timestamps "${WWW_NGINX_OWNER}" "${RUN_DIR}/www.nginx"
cp --preserve=mode,ownership,timestamps "${API_NGINX_OWNER}" "${RUN_DIR}/api.nginx"
if [[ -d "${PRODUCTION_ROOT}" ]]; then
  tar --format=posix -czf "${RUN_DIR}/production-root.tar.gz" -C "${PRODUCTION_ROOT}" .
  printf '%s\n' present > "${RUN_DIR}/production-root.state"
else
  : > "${RUN_DIR}/production-root.tar.gz"
  printf '%s\n' absent > "${RUN_DIR}/production-root.state"
fi
if [[ -L "${WEB_CURRENT_LINK}" ]]; then
  readlink "${WEB_CURRENT_LINK}" > "${RUN_DIR}/web-current.target"
  printf '%s\n' present > "${RUN_DIR}/web-current.state"
elif [[ -e "${WEB_CURRENT_LINK}" ]]; then
  die_remote "production Web current owner is not a symlink"
else
  printf '%s\n' absent > "${RUN_DIR}/web-current.state"
fi
service_state "${CANDIDATE_API_SERVICE}" > "${RUN_DIR}/candidate-api.active"
service_state "${CANDIDATE_WORKER_SERVICE}" > "${RUN_DIR}/candidate-worker.active"
enable_state "${CANDIDATE_API_SERVICE}" > "${RUN_DIR}/candidate-api.enabled"
enable_state "${CANDIDATE_WORKER_SERVICE}" > "${RUN_DIR}/candidate-worker.enabled"
service_state "${PRODUCTION_API_SERVICE}" > "${RUN_DIR}/production-api.active"
service_state "${PRODUCTION_WORKER_SERVICE}" > "${RUN_DIR}/production-worker.active"
for unit in "${LEGACY_ALREADY_MASKED_UNITS[@]}"; do
  systemctl is-active --quiet "${unit}" \
    && die_remote "previously retired legacy unit became active: ${unit}"
  systemctl is-enabled --quiet "${unit}" \
    && die_remote "previously retired legacy unit became enabled: ${unit}"
done
for unit in "${LEGACY_WRITER_UNITS[@]}"; do
  systemctl show "${unit}" --property=LoadState --value | grep -qx loaded \
    || die_remote "reviewed legacy writer unit is missing: ${unit}"
  service_state "${unit}" > "${RUN_DIR}/unit-${unit}.active"
  enable_state "${unit}" > "${RUN_DIR}/unit-${unit}.enabled"
done
printf '%s\n' "${SOURCE_DATABASE_DEFAULT}" > "${RUN_DIR}/source-database.setting"
printf '%s\n' "${SOURCE_ROLE_DEFAULT}" > "${RUN_DIR}/source-role.setting"
printf '%s\n' preflight > "${STATE_FILE}"
chmod 0600 "${RUN_DIR}"/*
BACKUP_COMPLETE="1"

export CHICKENBRO_LEGACY_SOURCE_DATABASE_URL="${LEGACY_DATABASE_URL}"
export WOW_DATABASE_URL="${TARGET_DATABASE_URL}"
export WOW_MIGRATION_WECHAT_APP_CONTEXT="${WOW_WECHAT_APPID}"
export PGPASSFILE="${PRODUCTION_PGPASSFILE}.new"
export PYTHONPATH="${STAGE_DIR}"
FULL_MIGRATION_TMP="/var/lib/chickenbro/full-migration-${RUN_ID}.json"
rm -f "${FULL_MIGRATION_TMP}"
sudo -n -u "${REMOTE_USER}" \
  --preserve-env=CHICKENBRO_LEGACY_SOURCE_DATABASE_URL,WOW_DATABASE_URL,WOW_MIGRATION_WECHAT_APP_CONTEXT,PGPASSFILE,PYTHONPATH \
  "${RUNTIME_ROOT}/bin/python" -m server.migrations.product.postgres_legacy \
  --mode full \
  --expected-source-database "${SOURCE_DATABASE}" \
  --expected-target-database "${PRODUCTION_DATABASE}" \
  --report-path "${FULL_MIGRATION_TMP}"
install -o root -g root -m 0600 "${FULL_MIGRATION_TMP}" "${FULL_MIGRATION_REPORT}"
rm -f "${FULL_MIGRATION_TMP}"
FULL_WATERMARK="$(python3 - "${FULL_MIGRATION_REPORT}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("sourceDatabase") != "wow_test" or payload.get("targetDatabase") != "chickenbro_prod":
    raise SystemExit("full migration database identity mismatch")
if payload.get("sourceMode") != "repeatable_read_read_only":
    raise SystemExit("full migration source mode mismatch")
if payload.get("reconciliation", {}).get("status") != "matched":  # reconciliation must be matched
    raise SystemExit("full migration reconciliation is not matched")
watermark = payload.get("capturedWatermark")
if not isinstance(watermark, str) or not watermark.endswith("Z"):
    raise SystemExit("full migration capturedWatermark is invalid")
print(watermark)
PY
)"
FULL_MIGRATION_REPORT_SHA256="$(sha256sum "${FULL_MIGRATION_REPORT}" | awk '{print $1}')"

MUTATION_STARTED="1"
WRITE_FENCE_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for unit in "${LEGACY_WRITER_UNITS[@]}"; do
  systemctl stop "${unit}" >/dev/null 2>&1 || true
  systemctl disable "${unit}" >/dev/null 2>&1 || true
  systemctl mask --runtime "${unit}" >/dev/null
done
sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
  --command="ALTER DATABASE wow_test SET default_transaction_read_only = on" \
  --command="ALTER ROLE wow_app IN DATABASE wow_test SET default_transaction_read_only = on" \
  --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'wow_test' AND pid <> pg_backend_pid()" >/dev/null
SOURCE_DATABASE_READ_ONLY="$(sudo -n -u "${REMOTE_USER}" --preserve-env=PGPASSFILE \
  psql -At --host=127.0.0.1 --port=5432 --username=wow_app --dbname=wow_test \
  --command="SELECT current_setting('default_transaction_read_only')")"
[[ "${SOURCE_DATABASE_READ_ONLY}" == "on" ]] || die_remote "source database read-only fence did not apply"
SOURCE_CONNECTION_COUNT="$(sudo -n -u postgres psql -At --dbname=postgres \
  --command="SELECT count(*) FROM pg_stat_activity WHERE datname = 'wow_test' AND usename = 'wow_app'")"
[[ "${SOURCE_CONNECTION_COUNT}" == "0" ]] \
  || die_remote "source database still has active application connections"
advance_state write_fenced

DELTA_MIGRATION_TMP="/var/lib/chickenbro/delta-migration-${RUN_ID}.json"
rm -f "${DELTA_MIGRATION_TMP}"
sudo -n -u "${REMOTE_USER}" \
  --preserve-env=CHICKENBRO_LEGACY_SOURCE_DATABASE_URL,WOW_DATABASE_URL,WOW_MIGRATION_WECHAT_APP_CONTEXT,PGPASSFILE,PYTHONPATH \
  "${RUNTIME_ROOT}/bin/python" -m server.migrations.product.postgres_legacy \
  --mode delta \
  --from-watermark "${FULL_WATERMARK}" \
  --expected-source-database "${SOURCE_DATABASE}" \
  --expected-target-database "${PRODUCTION_DATABASE}" \
  --report-path "${DELTA_MIGRATION_TMP}"
install -o root -g root -m 0600 "${DELTA_MIGRATION_TMP}" "${DELTA_MIGRATION_REPORT}"
rm -f "${DELTA_MIGRATION_TMP}"
DELTA_WATERMARK="$(python3 - "${DELTA_MIGRATION_REPORT}" "${FULL_WATERMARK}" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("reconciliation", {}).get("status") != "matched":  # reconciliation remains matched
    raise SystemExit("delta migration reconciliation is not matched")
watermark = payload.get("capturedWatermark")
if not isinstance(watermark, str) or not watermark.endswith("Z"):
    raise SystemExit("delta migration capturedWatermark is invalid")
start = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
end = datetime.fromisoformat(watermark.replace("Z", "+00:00"))
if end < start:
    raise SystemExit("delta watermark moved backwards")
print(watermark)
PY
)"
DELTA_MIGRATION_REPORT_SHA256="$(sha256sum "${DELTA_MIGRATION_REPORT}" | awk '{print $1}')"
advance_state delta_migrated

install -d -o root -g root -m 0755 "$(dirname -- "${CODE_NEW_DIR}")"
cp -a "${STAGE_DIR}" "${CODE_NEW_DIR}"
if [[ -d "${PRODUCTION_ROOT}" ]]; then
  mv "${PRODUCTION_ROOT}" "${RUN_DIR}/production-root.previous"
fi
mv "${CODE_NEW_DIR}" "${PRODUCTION_ROOT}"
chown -R root:root "${PRODUCTION_ROOT}"
find "${PRODUCTION_ROOT}" -type d -exec chmod 0755 {} +
find "${PRODUCTION_ROOT}" -type f -exec chmod 0644 {} +
chmod 0600 "${PRODUCTION_ROOT}/deploy-manifest.sha256"
(
  cd "${PRODUCTION_ROOT}"
  sha256sum --check deploy-manifest.sha256 >/dev/null
)

export TARGET_DATABASE_URL PRODUCTION_SOURCE_ENV RUNTIME_ROOT CANDIDATE_COMMIT
export PRODUCTION_ROOT PRODUCTION_PGPASSFILE
python3 - <<'PY'
import hashlib
import os
from pathlib import Path

api_lines = [
    f"WOW_DATABASE_URL={os.environ['TARGET_DATABASE_URL']}",
    f"WOW_WECHAT_APPID={os.environ['WOW_WECHAT_APPID']}",
    f"WOW_WECHAT_SECRET={os.environ['WOW_WECHAT_SECRET']}",
    f"WOW_CODEX_RUNTIME_REVISION=codex:sha256:{hashlib.sha256(Path('/usr/local/bin/codex').read_bytes()).hexdigest()}",
    f"PGPASSFILE={os.environ['PRODUCTION_PGPASSFILE']}",
]
worker_lines = [
    f"WOW_DATABASE_URL={os.environ['TARGET_DATABASE_URL']}",
    "WOW_APP_ENV=production",
    f"PYTHONPATH={os.environ['PRODUCTION_ROOT']}",
    f"PGPASSFILE={os.environ['PRODUCTION_PGPASSFILE']}",
]
Path(os.environ["PRODUCTION_API_ENV"] + ".new").write_text("\n".join(api_lines) + "\n", encoding="utf-8")
Path(os.environ["PRODUCTION_WORKER_ENV"] + ".new").write_text("\n".join(worker_lines) + "\n", encoding="utf-8")
PY
install -o root -g root -m 0600 "${PRODUCTION_API_ENV}.new" "${PRODUCTION_API_ENV}"
install -o root -g root -m 0600 "${PRODUCTION_WORKER_ENV}.new" "${PRODUCTION_WORKER_ENV}"
install -o root -g root -m 0600 "${PRODUCTION_PGPASSFILE}.new" "${PRODUCTION_PGPASSFILE}"
install -o root -g root -m 0600 "${LEGACY_SOURCE_ENV}" "${PRODUCTION_SOURCE_ENV}"
rm -f "${PRODUCTION_API_ENV}.new" "${PRODUCTION_WORKER_ENV}.new" "${PRODUCTION_PGPASSFILE}.new"
export PGPASSFILE="${PRODUCTION_PGPASSFILE}"
CODEX_PROFILE_TEMPLATE="${PRODUCTION_ROOT}/scripts/chickenbro-native-agent/chickenbro-native.config.toml.template"
CODEX_PROFILE_NEW="${PRODUCTION_CODEX_PROFILE}.new-${RUN_ID}"
[[ -f "${CODEX_PROFILE_TEMPLATE}" ]] || die_remote "production Codex profile template is missing"
install -d -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0700 "$(dirname -- "${PRODUCTION_CODEX_PROFILE}")"
python3 - "${CODEX_PROFILE_TEMPLATE}" "${PRODUCTION_ROOT}" "${CODEX_PROFILE_NEW}" <<'PY'
import os
import sys
from pathlib import Path

template_path, runtime_root, output_path = map(Path, sys.argv[1:])
source = template_path.read_text(encoding="utf-8")
placeholder = "__CHICKENBRO_RUNTIME_ROOT__"
if source.count(placeholder) != 2:
    raise SystemExit("production Codex profile template placeholder count is invalid")
rendered = source.replace(placeholder, runtime_root.as_posix())
expected_script = f"{runtime_root.as_posix()}/server/chickenbro_native_mcp.py"
if (
    f'args = ["{expected_script}"]' not in rendered
    or f'cwd = "{runtime_root.as_posix()}"' not in rendered
    or placeholder in rendered
):
    raise SystemExit("production Codex profile ownership is invalid")
descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    output.write(rendered)
PY
install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${CODEX_PROFILE_NEW}" "${PRODUCTION_CODEX_PROFILE}"
rm -f "${CODEX_PROFILE_NEW}"
CODEX_PROFILE_IDENTITY="$(sha256sum "${PRODUCTION_CODEX_PROFILE}" | awk '{print $1}')"
install -o root -g root -m 0644 "${PRODUCTION_ROOT}/server/chickenbro-api.service" \
  "/etc/systemd/system/${PRODUCTION_API_SERVICE}.service"
install -o root -g root -m 0644 "${PRODUCTION_ROOT}/server/chickenbro-worker.service" \
  "/etc/systemd/system/${PRODUCTION_WORKER_SERVICE}.service"
install -o root -g root -m 0644 "${PRODUCTION_ROOT}/server/chickenbro-simc-runtime-update.service" \
  "/etc/systemd/system/${SIMC_UPDATE_SERVICE}.service"
chmod 0755 "${PRODUCTION_ROOT}/server/chickenbro_simc_runtime_update.sh"

install -d -o root -g root -m 0755 "${PRODUCTION_WEB_ROOT}/releases"
if [[ ! -e "${WEB_RELEASE_DIR}" ]]; then
  install -d -o root -g root -m 0755 "${WEB_RELEASE_DIR}"
  cp -a "${PRODUCTION_ROOT}/apps/mini-taro/dist/h5/." "${WEB_RELEASE_DIR}/"
fi
DEPLOYED_WEB_IDENTITY="$(python3 - "${WEB_RELEASE_DIR}" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
digest = hashlib.sha256()
files = sorted(path for path in root.rglob('*') if path.is_file())
for path in files:
    if path.is_symlink():
        raise SystemExit('deployed Web release contains a symlink')
    digest.update(path.relative_to(root).as_posix().encode())
    digest.update(b'\0')
    digest.update(path.read_bytes())
    digest.update(b'\0')
print(digest.hexdigest())
PY
)"
[[ "${DEPLOYED_WEB_IDENTITY}" == "${PRODUCTION_WEB_BUILD_IDENTITY}" ]] \
  || die_remote "deployed production Web identity mismatch"

python3 - "${WWW_NGINX_OWNER}" "${API_NGINX_OWNER}" <<'PY'
from pathlib import Path
import re
import sys

www_path, api_path = map(Path, sys.argv[1:])

def remove_marked(text, begin, end):
    while begin in text:
        left, rest = text.split(begin, 1)
        if end not in rest:
            raise SystemExit(f"unterminated Nginx section: {begin}")
        _, right = rest.split(end, 1)
        text = left.rstrip() + "\n" + right.lstrip("\n")
    return text

www = www_path.read_text(encoding="utf-8")
api = api_path.read_text(encoding="utf-8")
www = remove_marked(www, "# BEGIN CHICKENBRO CANDIDATE WWW", "# END CHICKENBRO CANDIDATE WWW")
api = remove_marked(api, "# BEGIN CHICKENBRO CANDIDATE API", "# END CHICKENBRO CANDIDATE API")
api = remove_marked(api, "# BEGIN CHICKENBRO PRODUCTION API", "# END CHICKENBRO PRODUCTION API")
if re.search(r"location\s+\^~\s+/api/v2/", api):
    raise SystemExit("API host has an unowned /api/v2/ location")
section = """# BEGIN CHICKENBRO PRODUCTION API
location ^~ /api/v2/ {
    proxy_pass http://127.0.0.1:8790;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_buffering off;
    proxy_read_timeout 210s;
}
# END CHICKENBRO PRODUCTION API"""
position = api.rfind("\n}")
if position < 0:
    raise SystemExit("API Nginx owner is invalid")
api = api[:position].rstrip() + "\n\n" + section + "\n" + api[position:]
www_path.with_suffix(www_path.suffix + '.cutover').write_text(www, encoding='utf-8')
api_path.with_suffix(api_path.suffix + '.cutover').write_text(api, encoding='utf-8')
PY
install -o root -g root -m 0644 "${WWW_NGINX_OWNER}.cutover" "${WWW_NGINX_OWNER}"
install -o root -g root -m 0644 "${API_NGINX_OWNER}.cutover" "${API_NGINX_OWNER}"
rm -f "${WWW_NGINX_OWNER}.cutover" "${API_NGINX_OWNER}.cutover"
ln -sfn "${WEB_RELEASE_DIR}" "${WEB_CURRENT_LINK}.new"
nginx -t
systemctl daemon-reload
systemctl enable "${PRODUCTION_API_SERVICE}" "${PRODUCTION_WORKER_SERVICE}" >/dev/null
advance_state switched

# The durable authority marker is written before anything can accept a public
# production write. It is deliberately not called FIRST_NEW_WRITE: an actual
# accepted write is proven later by exact production user-acceptance evidence.
WRITE_AUTHORITY_BOUNDARY_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "${WRITE_AUTHORITY_BOUNDARY_AT}" > "${WRITE_AUTHORITY_BOUNDARY}.new"
chmod 0600 "${WRITE_AUTHORITY_BOUNDARY}.new"
mv -Tf "${WRITE_AUTHORITY_BOUNDARY}.new" "${WRITE_AUTHORITY_BOUNDARY}"
systemctl start "${PRODUCTION_API_SERVICE}" "${PRODUCTION_WORKER_SERVICE}"
mv -Tf "${WEB_CURRENT_LINK}.new" "${WEB_CURRENT_LINK}"
systemctl stop "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
systemctl disable "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null 2>&1 || true
systemctl mask --runtime "${CANDIDATE_API_SERVICE}" "${CANDIDATE_WORKER_SERVICE}" >/dev/null
systemctl reload nginx

for _attempt in $(seq 1 30); do
  if systemctl is-active --quiet "${PRODUCTION_API_SERVICE}" \
    && systemctl is-active --quiet "${PRODUCTION_WORKER_SERVICE}" \
    && curl --fail --silent --show-error \
      "http://127.0.0.1:${PRODUCTION_PORT}/api/v2/health/readiness" > "${RUN_DIR}/readiness-internal.json"; then
    break
  fi
  sleep 1
done
systemctl is-active --quiet "${PRODUCTION_API_SERVICE}"
systemctl is-active --quiet "${PRODUCTION_WORKER_SERVICE}"

for origin in https://www.chickenbro.cloud https://api.chickenbro.cloud; do
  label="${origin#https://}"
  curl --fail --silent --show-error "${origin}/api/v2/health/readiness" \
    > "${RUN_DIR}/readiness-${label}.json"
  for route in me chat/conversations simc/jobs; do
    output="${RUN_DIR}/anonymous-${label}-${route//\//-}.json"
    status="$(curl --silent --show-error --output "${output}" --write-out '%{http_code}' \
      "${origin}/api/v2/${route}")"
    [[ "${status}" == "401" ]] || die_remote "production anonymous route did not return 401"
  done
done

python3 - \
  "${RUN_DIR}/readiness-internal.json" \
  "${RUN_DIR}/readiness-www.chickenbro.cloud.json" \
  "${RUN_DIR}/readiness-api.chickenbro.cloud.json" \
  "${RUN_DIR}/anonymous-www.chickenbro.cloud-me.json" \
  "${RUN_DIR}/anonymous-www.chickenbro.cloud-chat-conversations.json" \
  "${RUN_DIR}/anonymous-www.chickenbro.cloud-simc-jobs.json" \
  "${RUN_DIR}/anonymous-api.chickenbro.cloud-me.json" \
  "${RUN_DIR}/anonymous-api.chickenbro.cloud-chat-conversations.json" \
  "${RUN_DIR}/anonymous-api.chickenbro.cloud-simc-jobs.json" <<'PY'
import json
import sys
from pathlib import Path

readiness = [json.loads(Path(item).read_text(encoding='utf-8')) for item in sys.argv[1:4]]
semantic = []
for payload in readiness:
    if payload.get('status') != 'ready':
        raise SystemExit('production readiness is not ready')
    components = payload.get('components')
    if not isinstance(components, dict) or any(
        not isinstance(value, dict) or value.get('status') != 'ready'
        for value in components.values()
    ):
        raise SystemExit('production readiness has a non-ready component')
    semantic.append({key: value.get('status') for key, value in sorted(components.items())})
if semantic[1:] != semantic[:1] * (len(semantic) - 1):
    raise SystemExit('production readiness differs across origins')
for item in sys.argv[4:]:
    payload = json.loads(Path(item).read_text(encoding='utf-8'))
    if payload.get('error', {}).get('code') != 'AUTH_REQUIRED':
        raise SystemExit('production anonymous route did not return AUTH_REQUIRED')
PY

SOURCE_DATABASE_READ_ONLY="$(sudo -n -u "${REMOTE_USER}" --preserve-env=PGPASSFILE \
  psql -At --host=127.0.0.1 --port=5432 --username=wow_app --dbname=wow_test \
  --command="SELECT current_setting('default_transaction_read_only')")"
[[ "${SOURCE_DATABASE_READ_ONLY}" == "on" ]] || die_remote "legacy database escaped the read-only fence"
for unit in "${LEGACY_WRITER_UNITS[@]}"; do
  systemctl is-active --quiet "${unit}" && die_remote "legacy writer became active: ${unit}"
done

API_SERVICE_IDENTITY="$(sha256sum "/etc/systemd/system/${PRODUCTION_API_SERVICE}.service" | awk '{print $1}')"
WORKER_SERVICE_IDENTITY="$(sha256sum "/etc/systemd/system/${PRODUCTION_WORKER_SERVICE}.service" | awk '{print $1}')"
SIMC_UPDATE_SERVICE_IDENTITY="$(sha256sum "/etc/systemd/system/${SIMC_UPDATE_SERVICE}.service" | awk '{print $1}')"
WWW_NGINX_IDENTITY="$(sha256sum "${WWW_NGINX_OWNER}" | awk '{print $1}')"
API_NGINX_IDENTITY="$(sha256sum "${API_NGINX_OWNER}" | awk '{print $1}')"
DEPLOYED_MANIFEST_IDENTITY="$(sha256sum "${PRODUCTION_ROOT}/deploy-manifest.sha256" | awk '{print $1}')"

export RUN_ID WRITE_FENCE_AT FULL_WATERMARK DELTA_WATERMARK WRITE_AUTHORITY_BOUNDARY_AT
export FULL_MIGRATION_REPORT_SHA256 DELTA_MIGRATION_REPORT_SHA256
export API_SERVICE_IDENTITY WORKER_SERVICE_IDENTITY SIMC_UPDATE_SERVICE_IDENTITY WWW_NGINX_IDENTITY API_NGINX_IDENTITY
export DEPLOYED_MANIFEST_IDENTITY CODEX_PROFILE_IDENTITY SOURCE_DATABASE_READ_ONLY MIGRATION_IDS CUTOVER_EVIDENCE
export CANDIDATE_EVIDENCE_SHA REAL_ACCEPTANCE_SHA REVIEWED_INVENTORY_SHA REVIEWED_BACKUP_MANIFEST_SHA
export CANDIDATE_COMMIT PRODUCTION_WEB_BUILD_IDENTITY PRODUCTION_WEAPP_BUILD_IDENTITY BACKUP_MODE
python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "schemaVersion": "chickenbro-production-cutover-v1",
    "status": "production_cutover_switched_production_acceptance_pending",
    "state": "switched",
    "branchCommit": os.environ["CANDIDATE_COMMIT"],
    "inventorySha256": os.environ["REVIEWED_INVENTORY_SHA"],
    "backupMode": os.environ["BACKUP_MODE"],
    "independentBackupManifestSha256": (
        os.environ["REVIEWED_BACKUP_MANIFEST_SHA"]
        if os.environ["BACKUP_MODE"] == "independent"
        else None
    ),
    "candidateEvidenceSha256": os.environ["CANDIDATE_EVIDENCE_SHA"],
    "realAcceptanceSha256": os.environ["REAL_ACCEPTANCE_SHA"],
    "writeFenceAt": os.environ["WRITE_FENCE_AT"],
    "fullWatermark": os.environ["FULL_WATERMARK"],
    "deltaWatermark": os.environ["DELTA_WATERMARK"],
    "writeAuthorityBoundaryAt": os.environ["WRITE_AUTHORITY_BOUNDARY_AT"],
    "firstNewWriteAt": None,
    "productionAcceptanceSha256": None,
    "sourceDatabase": "wow_test",
    "sourceDatabaseReadOnly": os.environ["SOURCE_DATABASE_READ_ONLY"] == "on",
    "targetDatabase": "chickenbro_prod",
    "databaseMigrationIds": os.environ["MIGRATION_IDS"].split(","),
    "fullMigrationReportSha256": os.environ["FULL_MIGRATION_REPORT_SHA256"],
    "deltaMigrationReportSha256": os.environ["DELTA_MIGRATION_REPORT_SHA256"],
    "deployedManifestSha256": os.environ["DEPLOYED_MANIFEST_IDENTITY"],
    "apiServiceIdentity": os.environ["API_SERVICE_IDENTITY"],
    "workerServiceIdentity": os.environ["WORKER_SERVICE_IDENTITY"],
    "simcUpdateServiceIdentity": os.environ["SIMC_UPDATE_SERVICE_IDENTITY"],
    "codexProfileIdentity": os.environ["CODEX_PROFILE_IDENTITY"],
    "webBuildIdentity": os.environ["PRODUCTION_WEB_BUILD_IDENTITY"],
    "weappBuildIdentity": os.environ["PRODUCTION_WEAPP_BUILD_IDENTITY"],
    "wwwNginxIdentity": os.environ["WWW_NGINX_IDENTITY"],
    "apiNginxIdentity": os.environ["API_NGINX_IDENTITY"],
    "rollbackClassification": "legacy_read_only_new_data_plane_only",
    "postCutoverRealUserAcceptance": "pending",
    "recordedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
Path(os.environ["CUTOVER_EVIDENCE"]).write_text(
    json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
chmod 0600 "${CUTOVER_EVIDENCE}"
printf '%s\n' legacy_read_only > "${RUN_DIR}/ROLLBACK_CLASSIFICATION"
chmod 0600 "${RUN_DIR}/ROLLBACK_CLASSIFICATION"
CUTOVER_EVIDENCE_SHA256="$(sha256sum "${CUTOVER_EVIDENCE}" | awk '{print $1}')"

trap - EXIT
rm -f -- "${REMOTE_ARCHIVE}"
rm -rf -- "${STAGE_DIR}"
printf 'state=switched evidence=%s evidenceSha256=%s rollback=legacy_read_only acceptance=required\n' \
  "${CUTOVER_EVIDENCE}" "${CUTOVER_EVIDENCE_SHA256}"
REMOTE_CUTOVER

trap - EXIT
cleanup_local

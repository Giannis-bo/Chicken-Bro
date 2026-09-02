#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
TARGET_DATABASE="chickenbro_prod"
SOURCE_DATABASE="wow_test"
RUNTIME_ROLE="wow_app"
BLOCKED_GATE="blocked_until_independent_legacy_cleanup_or_storage_expansion"
READY_FOR_LIVE_PREFLIGHT_GATE="capacity_preflight_required"
POSTGRES_DATA_ROOT="/var/lib/postgresql"
INVENTORY_MAX_AGE_SECONDS="21600"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INVENTORY_FILE="${REPO_ROOT}/docs/refactor/chickenbro-simc-cloud-inventory.json"
PROJECT_STATE_FILE="${REPO_ROOT}/docs/project-state.json"
MIGRATION_DIR="${REPO_ROOT}/server/migrations/product"

REVIEWED_INVENTORY_SHA=""
BACKUP_DEVICE=""

die() {
  printf 'provision_chickenbro_database: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat >&2 <<'USAGE'
Usage:
  server/provision_chickenbro_database_lighthouse.sh [--dry-run] [--inventory-sha <sha256>]
  server/provision_chickenbro_database_lighthouse.sh --apply --inventory-sha <sha256> --backup-device <absolute-path>

Apply also requires candidateDatabaseProvisioningAuthorized=true in docs/project-state.json,
an independently mounted WOW_REBUILD_BACKUP_ROOT, and WOW_REBUILD_MANAGEMENT_ROLE.
USAGE
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
    --inventory-sha)
      [[ $# -ge 2 ]] || die "--inventory-sha requires a value"
      REVIEWED_INVENTORY_SHA="$2"
      shift 2
      ;;
    --backup-device)
      [[ $# -ge 2 ]] || die "--backup-device requires a value"
      BACKUP_DEVICE="$2"
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

[[ -f "${INVENTORY_FILE}" ]] || die "reviewed cloud inventory is missing"
[[ -f "${PROJECT_STATE_FILE}" ]] || die "project state is missing"
[[ -d "${MIGRATION_DIR}" ]] || die "server/migrations/product is missing"

sha256_file() {
  python3 - "$1" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys

path = Path(sys.argv[1])
digest = sha256()
with path.open("rb") as source:
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
PY
}

ACTUAL_INVENTORY_SHA="$(sha256_file "${INVENTORY_FILE}")"
[[ "${ACTUAL_INVENTORY_SHA}" =~ ^[0-9a-f]{64}$ ]] || die "inventory SHA calculation failed"
if [[ -n "${REVIEWED_INVENTORY_SHA}" ]]; then
  [[ "${REVIEWED_INVENTORY_SHA}" =~ ^[0-9a-f]{64}$ ]] || die "inventory SHA is invalid"
  [[ "${REVIEWED_INVENTORY_SHA}" == "${ACTUAL_INVENTORY_SHA}" ]] || die "inventory SHA does not match the reviewed file"
fi

INVENTORY_FACTS="$(python3 - "${INVENTORY_FILE}" <<'PY'
import json
from pathlib import Path
import sys

inventory = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
values = (
    inventory.get("status", ""),
    inventory.get("capacityGate", ""),
    inventory.get("rootFreeBytes", ""),
    inventory.get("currentDatabaseBytes", ""),
    len(inventory.get("probeErrors", [])),
    inventory.get("observedAt", ""),
)
print(*values, sep="\t")
PY
)"
IFS=$'\t' read -r INVENTORY_STATUS CAPACITY_GATE INVENTORY_ROOT_FREE_BYTES INVENTORY_DATABASE_BYTES PROBE_ERROR_COUNT INVENTORY_OBSERVED_AT <<< "${INVENTORY_FACTS}"

for number in "${INVENTORY_ROOT_FREE_BYTES}" "${INVENTORY_DATABASE_BYTES}" "${PROBE_ERROR_COUNT}"; do
  [[ "${number}" =~ ^[0-9]+$ ]] || die "reviewed inventory contains an invalid numeric fact"
done
[[ "${CAPACITY_GATE}" =~ ^[a-z0-9_]+$ ]] || die "reviewed inventory contains an invalid capacity gate"
[[ "${INVENTORY_OBSERVED_AT}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "reviewed inventory contains an invalid observation time"

CANDIDATE_DATABASE_AUTHORIZED="$(python3 - "${PROJECT_STATE_FILE}" <<'PY'
import json
from pathlib import Path
import sys

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print("true" if state.get("targetProduct", {}).get("candidateDatabaseProvisioningAuthorized") is True else "false")
PY
)"

emit_result() {
  local result="$1"
  local mutation_authorized="$2"
  local root_free_bytes="$3"
  local database_bytes="$4"
  local backup_archive_sha="${5:-}"
  python3 - \
    "${MODE}" \
    "${result}" \
    "${TARGET_DATABASE}" \
    "${SOURCE_DATABASE}" \
    "${ACTUAL_INVENTORY_SHA}" \
    "${INVENTORY_STATUS}" \
    "${CAPACITY_GATE}" \
    "${INVENTORY_OBSERVED_AT}" \
    "${mutation_authorized}" \
    "${root_free_bytes}" \
    "${database_bytes}" \
    "${backup_archive_sha}" <<'PY'
import json
import sys

(
    mode,
    result,
    target,
    source,
    inventory_sha,
    inventory_status,
    capacity_gate,
    inventory_observed_at,
    mutation_authorized,
    root_free_bytes,
    database_bytes,
    backup_archive_sha,
) = sys.argv[1:]
payload = {
    "mode": mode,
    "result": result,
    "targetDatabase": target,
    "sourceDatabase": source,
    "inventorySha": inventory_sha,
    "inventoryStatus": inventory_status,
    "capacityGate": capacity_gate,
    "inventoryObservedAt": inventory_observed_at,
    "mutationAuthorized": mutation_authorized == "true",
    "rootFreeBytes": int(root_free_bytes),
    "currentDatabaseBytes": int(database_bytes),
}
if backup_archive_sha:
    payload["backupArchiveSha256"] = backup_archive_sha
print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
PY
}

if [[ "${MODE}" == "dry-run" ]]; then
  emit_result "${CAPACITY_GATE:-${BLOCKED_GATE}}" "false" "${INVENTORY_ROOT_FREE_BYTES}" "${INVENTORY_DATABASE_BYTES}"
  exit 0
fi

[[ -n "${REVIEWED_INVENTORY_SHA}" ]] || die "--apply requires --inventory-sha"
[[ "${CANDIDATE_DATABASE_AUTHORIZED}" == "true" ]] || die "candidateDatabaseProvisioningAuthorized=false; apply is forbidden"
[[ "${INVENTORY_STATUS}" == "reachable" ]] || die "reviewed inventory is not reachable"
[[ "${PROBE_ERROR_COUNT}" == "0" ]] || die "reviewed inventory contains probe errors"
[[ "${CAPACITY_GATE}" == "${READY_FOR_LIVE_PREFLIGHT_GATE}" ]] || die "reviewed capacity gate does not permit live preflight"
INVENTORY_AGE_SECONDS="$(python3 - "${INVENTORY_OBSERVED_AT}" <<'PY'
from datetime import datetime, timezone
import sys

observed = datetime.strptime(sys.argv[1], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
print(int((datetime.now(timezone.utc) - observed).total_seconds()))
PY
)"
[[ "${INVENTORY_AGE_SECONDS}" =~ ^-?[0-9]+$ ]] || die "inventory age calculation failed"
(( INVENTORY_AGE_SECONDS >= -300 )) || die "reviewed inventory observation time is unexpectedly in the future"
(( INVENTORY_AGE_SECONDS <= INVENTORY_MAX_AGE_SECONDS )) || die "reviewed inventory is stale; refresh it first"

[[ -n "${BACKUP_DEVICE}" ]] || die "--apply requires --backup-device"
[[ "${BACKUP_DEVICE}" == /* ]] || die "--backup-device must be an absolute path"
[[ "${BACKUP_DEVICE}" != "/" ]] || die "filesystem root cannot be the backup device"
[[ -n "${WOW_REBUILD_BACKUP_ROOT:-}" ]] || die "WOW_REBUILD_BACKUP_ROOT is required"
[[ "${WOW_REBUILD_BACKUP_ROOT}" == /* ]] || die "WOW_REBUILD_BACKUP_ROOT must be absolute"
[[ -n "${WOW_REBUILD_MANAGEMENT_ROLE:-}" ]] || die "WOW_REBUILD_MANAGEMENT_ROLE is required"
[[ "${WOW_REBUILD_MANAGEMENT_ROLE}" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || die "WOW_REBUILD_MANAGEMENT_ROLE is invalid"
[[ "${EUID}" -eq 0 ]] || die "--apply must run as root on the reviewed Lighthouse host"

for command_name in python3 realpath stat df awk tr tail date install chmod find sort basename sudo psql pg_dump pg_restore createdb; do
  command -v "${command_name}" >/dev/null 2>&1 || die "required apply command is unavailable"
done

[[ -d "${POSTGRES_DATA_ROOT}" ]] || die "PostgreSQL data root is missing"
[[ -d "${BACKUP_DEVICE}" ]] || die "backup device path is missing"
[[ -d "${WOW_REBUILD_BACKUP_ROOT}" ]] || die "backup root is missing"

POSTGRES_DATA_REAL="$(realpath -e "${POSTGRES_DATA_ROOT}")"
BACKUP_DEVICE_REAL="$(realpath -e "${BACKUP_DEVICE}")"
BACKUP_ROOT_REAL="$(realpath -e "${WOW_REBUILD_BACKUP_ROOT}")"
case "${BACKUP_ROOT_REAL}/" in
  "${BACKUP_DEVICE_REAL}/"*) ;;
  *) die "backup root is not located on the reviewed backup device" ;;
esac
[[ "$(stat -c '%a' "${BACKUP_ROOT_REAL}")" == "700" ]] || die "backup root must have mode 0700"

POSTGRES_DEVICE_ID="$(stat -c '%d' "${POSTGRES_DATA_REAL}")"
BACKUP_DEVICE_ID="$(stat -c '%d' "${BACKUP_DEVICE_REAL}")"
[[ "${POSTGRES_DEVICE_ID}" != "${BACKUP_DEVICE_ID}" ]] || die "backup and PostgreSQL data must use different device IDs"
[[ "$(stat -c '%d' "${BACKUP_ROOT_REAL}")" == "${BACKUP_DEVICE_ID}" ]] || die "backup root moved to an unexpected device"

MANAGEMENT_ROLE="${WOW_REBUILD_MANAGEMENT_ROLE}"

pg_query() {
  sudo -n -u postgres psql \
    --no-psqlrc \
    --username="${MANAGEMENT_ROLE}" \
    --dbname=postgres \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command="$1" | tr -d '[:space:]'
}

target_query() {
  sudo -n -u postgres psql \
    --no-psqlrc \
    --username="${MANAGEMENT_ROLE}" \
    --dbname="${TARGET_DATABASE}" \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command="$1" | tr -d '[:space:]'
}

[[ "$(pg_query 'SELECT current_user')" == "${MANAGEMENT_ROLE}" ]] || die "management-role connection identity does not match"
[[ "$(pg_query "SELECT count(*) FROM pg_roles WHERE rolname = current_user AND rolcanlogin AND (rolcreatedb OR rolsuper)")" == "1" ]] || die "management role cannot create the isolated target"
[[ "$(pg_query "SELECT count(*) FROM pg_roles WHERE rolname = '${RUNTIME_ROLE}' AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole")" == "1" ]] || die "runtime role is missing or over-privileged"
[[ "$(pg_query "SELECT count(*) FROM pg_database WHERE datname = '${SOURCE_DATABASE}'")" == "1" ]] || die "migration source database is missing"

SOURCE_DATABASE_BYTES="$(pg_query "SELECT pg_database_size('${SOURCE_DATABASE}')")"
LIVE_DATABASE_BYTES="$(pg_query "SELECT COALESCE(sum(pg_database_size(datname)), 0) FROM pg_database WHERE NOT datistemplate")"
ROOT_FREE_BYTES="$(df -PB1 --output=avail "${POSTGRES_DATA_REAL}" | tail -n 1 | tr -d '[:space:]')"
BACKUP_FREE_BYTES="$(df -PB1 --output=avail "${BACKUP_DEVICE_REAL}" | tail -n 1 | tr -d '[:space:]')"
for number in "${SOURCE_DATABASE_BYTES}" "${LIVE_DATABASE_BYTES}" "${ROOT_FREE_BYTES}" "${BACKUP_FREE_BYTES}"; do
  [[ "${number}" =~ ^[0-9]+$ ]] || die "live capacity probe returned an invalid value"
done

INVENTORY_DRIFT=$(( LIVE_DATABASE_BYTES - INVENTORY_DATABASE_BYTES ))
if (( INVENTORY_DRIFT < 0 )); then
  INVENTORY_DRIFT=$(( -INVENTORY_DRIFT ))
fi
MAX_DATABASE_DRIFT=$(( INVENTORY_DATABASE_BYTES / 20 ))
(( MAX_DATABASE_DRIFT >= 104857600 )) || MAX_DATABASE_DRIFT=104857600
(( INVENTORY_DRIFT <= MAX_DATABASE_DRIFT )) || die "live database bytes drifted from the reviewed inventory; refresh it first"

REQUIRED_TARGET_FREE_BYTES=$(( SOURCE_DATABASE_BYTES + SOURCE_DATABASE_BYTES / 4 + 2147483648 ))
REQUIRED_BACKUP_FREE_BYTES=$(( SOURCE_DATABASE_BYTES + 2147483648 ))
(( ROOT_FREE_BYTES >= REQUIRED_TARGET_FREE_BYTES )) || die "live PostgreSQL device capacity is insufficient"
(( BACKUP_FREE_BYTES >= REQUIRED_BACKUP_FREE_BYTES )) || die "independent backup device capacity is insufficient"

EXPECTED_MIGRATIONS="$(
  find "${MIGRATION_DIR}" -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]_*.sql' -print \
    | LC_ALL=C sort \
    | awk -F/ '{name=$NF; sub(/\.sql$/, "", name); printf "%s%s", separator, name; separator=","}'
)"
[[ -n "${EXPECTED_MIGRATIONS}" ]] || die "no product migrations are available"
[[ "${EXPECTED_MIGRATIONS}" =~ ^[0-9]{4}_[a-z0-9_]+(,[0-9]{4}_[a-z0-9_]+)*$ ]] || die "product migration identity is invalid"

TARGET_DATABASE_EXISTS="$(pg_query "SELECT count(*) FROM pg_database WHERE datname = '${TARGET_DATABASE}'")"
[[ "${TARGET_DATABASE_EXISTS}" == "0" || "${TARGET_DATABASE_EXISTS}" == "1" ]] || die "target database existence probe failed"
TARGET_CONNECTIONS="0"

verify_target_identity() {
  local schemas tables migrations forbidden owner runtime_schema_create runtime_database_create runtime_business_delete migration_registry public_object_count
  schemas="$(target_query "SELECT string_agg(schema_name, ',' ORDER BY schema_name) FROM information_schema.schemata WHERE schema_name IN ('identity','chat','simc','ops')")"
  tables="$(target_query "SELECT string_agg(table_schema || '.' || table_name, ',' ORDER BY table_schema, table_name) FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema IN ('identity','chat','simc','ops')")"
  migration_registry="$(target_query "SELECT COALESCE(pg_catalog.to_regclass('ops.schema_migrations')::text, '')")"
  [[ "${migration_registry}" == "ops.schema_migrations" ]] || die "target migration registry is missing"
  migrations="$(target_query "SELECT string_agg(id, ',' ORDER BY id) FROM ops.schema_migrations")"
  forbidden="$(target_query "SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('app','content','cache','knowledge','analytics','websim')")"
  UNEXPECTED_SCHEMA_COUNT="$(target_query "SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog','information_schema','public','identity','chat','simc','ops') AND schema_name NOT LIKE 'pg_toast%' AND schema_name NOT LIKE 'pg_temp_%'")"
  public_object_count="$(target_query "SELECT (SELECT count(*) FROM pg_catalog.pg_class AS c JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f')) + (SELECT count(*) FROM pg_catalog.pg_proc AS p JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace WHERE n.nspname = 'public')")"
  owner="$(pg_query "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '${TARGET_DATABASE}'")"
  runtime_schema_create="$(target_query "SELECT count(*) FROM unnest(ARRAY['public','identity','chat','simc','ops']) AS item(schema_name) WHERE has_schema_privilege('${RUNTIME_ROLE}', schema_name, 'CREATE')")"
  runtime_database_create="$(target_query "SELECT CASE WHEN has_database_privilege('${RUNTIME_ROLE}', current_database(), 'CREATE') THEN 1 ELSE 0 END")"
  runtime_business_delete="$(target_query "SELECT count(*) FROM unnest(ARRAY['identity.users','identity.user_identities','identity.auth_sessions','identity.web_login_sessions','chat.conversations','chat.messages','chat.agent_runs','simc.source_snapshots','simc.simulation_jobs','simc.simulation_attempts','simc.simulation_results','ops.job_queue','ops.usage_counters']) AS item(table_name) WHERE has_table_privilege('${RUNTIME_ROLE}', table_name, 'DELETE')")"

  [[ "${schemas}" == "chat,identity,ops,simc" ]] || die "target schema identity is unexpected"
  [[ "${tables}" == "chat.agent_runs,chat.conversations,chat.messages,identity.auth_sessions,identity.user_identities,identity.users,identity.web_login_sessions,ops.audit_events,ops.job_queue,ops.schema_migrations,ops.usage_counters,simc.simulation_attempts,simc.simulation_jobs,simc.simulation_results,simc.source_snapshots" ]] || die "target table identity is unexpected"
  [[ "${migrations}" == "${EXPECTED_MIGRATIONS}" ]] || die "target migration identity is unexpected"
  [[ "${forbidden}" == "0" ]] || die "target contains forbidden schemas"
  [[ "${UNEXPECTED_SCHEMA_COUNT}" == "0" ]] || die "target contains an unreviewed schema"
  [[ "${public_object_count}" == "0" ]] || die "target public schema contains unreviewed objects"
  [[ "${owner}" == "${MANAGEMENT_ROLE}" ]] || die "target database owner is unexpected"
  [[ "${runtime_schema_create}" == "0" && "${runtime_database_create}" == "0" ]] || die "runtime role has schema or database creation power"
  [[ "${runtime_business_delete}" == "0" ]] || die "runtime role has destructive business-table privileges"
}

if [[ "${TARGET_DATABASE_EXISTS}" == "1" ]]; then
  TARGET_CONNECTIONS="$(pg_query "SELECT count(*) FROM pg_stat_activity WHERE datname = '${TARGET_DATABASE}'")"
  [[ "${TARGET_CONNECTIONS}" == "0" ]] || die "target database already has active connections"
  verify_target_identity
  emit_result "already_provisioned_exact_identity" "false" "${ROOT_FREE_BYTES}" "${LIVE_DATABASE_BYTES}"
  exit 0
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${ACTUAL_INVENTORY_SHA:0:12}"
BACKUP_RUN_DIR="${BACKUP_ROOT_REAL}/chickenbro-prod-provision-${RUN_ID}"
[[ ! -e "${BACKUP_RUN_DIR}" ]] || die "backup run identity already exists"
install -d -o root -g root -m 0700 "${BACKUP_RUN_DIR}"
PROVISION_STATE_FILE="${BACKUP_RUN_DIR}/provision.state"

record_failure() {
  local exit_code=$?
  if [[ "${exit_code}" -ne 0 ]]; then
    printf '%s\n' 'failed_requires_operator_review' > "${PROVISION_STATE_FILE}"
    chmod 0600 "${PROVISION_STATE_FILE}"
  fi
  exit "${exit_code}"
}
trap record_failure EXIT

printf '%s\n' "${ACTUAL_INVENTORY_SHA}" > "${BACKUP_RUN_DIR}/inventory.sha256"
printf '%s\n' "${SOURCE_DATABASE}" > "${BACKUP_RUN_DIR}/source.database"
printf '%s\n' "${TARGET_DATABASE}" > "${BACKUP_RUN_DIR}/target.database"
printf '%s\n' "${SOURCE_DATABASE_BYTES}" > "${BACKUP_RUN_DIR}/source.bytes"
chmod 0600 "${BACKUP_RUN_DIR}"/*

SOURCE_ARCHIVE="${BACKUP_RUN_DIR}/source.custom"
SOURCE_ARCHIVE_LIST="${BACKUP_RUN_DIR}/source.restore-list"
sudo -n -u postgres pg_dump \
  --username="${MANAGEMENT_ROLE}" \
  --format=custom \
  --dbname="${SOURCE_DATABASE}" > "${SOURCE_ARCHIVE}"
chmod 0600 "${SOURCE_ARCHIVE}"
pg_restore --list "${SOURCE_ARCHIVE}" > "${SOURCE_ARCHIVE_LIST}"
chmod 0600 "${SOURCE_ARCHIVE_LIST}"
[[ -s "${SOURCE_ARCHIVE}" && -s "${SOURCE_ARCHIVE_LIST}" ]] || die "source archive or restore-list validation is empty"
SOURCE_ARCHIVE_SHA="$(sha256_file "${SOURCE_ARCHIVE}")"
printf '%s\n' "${SOURCE_ARCHIVE_SHA}" > "${BACKUP_RUN_DIR}/source.custom.sha256"
chmod 0600 "${BACKUP_RUN_DIR}/source.custom.sha256"

sudo -n -u postgres createdb \
  --username="${MANAGEMENT_ROLE}" \
  --owner="${MANAGEMENT_ROLE}" \
  --template=template0 \
  --encoding=UTF8 \
  "${TARGET_DATABASE}"

while IFS= read -r migration; do
  migration_name="$(basename "${migration}")"
  migration_id="${migration_name%.sql}"
  [[ "${migration_id}" =~ ^[0-9]{4}_[a-z0-9_]+$ ]] || die "migration filename is invalid"
  sudo -n -u postgres psql \
    --no-psqlrc \
    --username="${MANAGEMENT_ROLE}" \
    --dbname="${TARGET_DATABASE}" \
    --set=ON_ERROR_STOP=1 \
    --single-transaction \
    --file="${migration}" \
    --command="INSERT INTO ops.schema_migrations (id, description) VALUES ('${migration_id}', 'Apply clean product migration ${migration_id}') ON CONFLICT (id) DO NOTHING"
done < <(find "${MIGRATION_DIR}" -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]_*.sql' -print | LC_ALL=C sort)

verify_target_identity
printf '%s\n' 'provisioned_exact_identity' > "${PROVISION_STATE_FILE}"
chmod 0600 "${PROVISION_STATE_FILE}"
trap - EXIT

emit_result "provisioned_exact_identity" "true" "${ROOT_FREE_BYTES}" "${LIVE_DATABASE_BYTES}" "${SOURCE_ARCHIVE_SHA}"

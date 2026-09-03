#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
TARGET_DATABASE="chickenbro_prod"
SOURCE_DATABASE="wow_test"
RUNTIME_ROLE="wow_app"
BLOCKED_GATE="blocked_until_whitelist_recovery_and_exact_capacity_cleanup_or_storage_expansion"
READY_AFTER_CAPACITY_CLEANUP_GATE="capacity_preflight_required"
POSTGRES_DATA_ROOT="/var/lib/postgresql"
INVENTORY_MAX_AGE_SECONDS="21600"
EXPECTED_INSTANCE_ID="ins-93tgv1rb"
EXPECTED_REGION="ap-shanghai"
EXPECTED_ZONE="ap-shanghai-2"
EXPECTED_PUBLIC_ADDRESS="124.223.51.33"
EXPECTED_SSH_TARGET="wow-lighthouse"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
INVENTORY_FILE="${REPO_ROOT}/docs/refactor/chickenbro-simc-cloud-inventory.json"
PROJECT_STATE_FILE="${REPO_ROOT}/docs/project-state.json"
MIGRATION_DIR="${REPO_ROOT}/server/migrations/product"

REVIEWED_INVENTORY_SHA=""
RECOVERY_ROOT="${WOW_CHICKENBRO_RECOVERY_ROOT:-/var/lib/chickenbro-recovery}"
MIGRATION_RUNTIME_PYTHON="${WOW_CHICKENBRO_MIGRATION_PYTHON:-/opt/wow-mini-program/.venv-v2/bin/python}"

die() {
  printf 'provision_chickenbro_database: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat >&2 <<'USAGE'
Usage:
  server/provision_chickenbro_database_lighthouse.sh [--dry-run] [--inventory-sha <sha256>]
  server/provision_chickenbro_database_lighthouse.sh --apply --inventory-sha <sha256>

Apply also requires candidateDatabaseProvisioningAuthorized=true in docs/project-state.json,
WOW_REBUILD_MANAGEMENT_ROLE (the target owner), WOW_REBUILD_PGPASSFILE,
WOW_MIGRATION_WECHAT_APP_CONTEXT,
and a fresh exact Tencent CVM identity match.
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

df_available_bytes() {
  df -B1 --output=avail "$1" | tail -n 1 | tr -d '[:space:]'
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
target = inventory.get("targetIdentity") or {}
values = (
    inventory.get("status", ""),
    inventory.get("capacityGate", ""),
    inventory.get("rootFreeBytes", ""),
    inventory.get("currentDatabaseBytes", ""),
    len(inventory.get("probeErrors", [])),
    inventory.get("observedAt", ""),
    target.get("instanceId", ""),
    target.get("region", ""),
    target.get("zone", ""),
    target.get("publicAddress", ""),
    target.get("sshTarget", ""),
)
print(*values, sep="\t")
PY
)"
IFS=$'\t' read -r INVENTORY_STATUS CAPACITY_GATE INVENTORY_ROOT_FREE_BYTES INVENTORY_DATABASE_BYTES PROBE_ERROR_COUNT INVENTORY_OBSERVED_AT INVENTORY_INSTANCE_ID INVENTORY_REGION INVENTORY_ZONE INVENTORY_PUBLIC_ADDRESS INVENTORY_SSH_TARGET <<< "${INVENTORY_FACTS}"

for number in "${INVENTORY_ROOT_FREE_BYTES}" "${INVENTORY_DATABASE_BYTES}" "${PROBE_ERROR_COUNT}"; do
  [[ "${number}" =~ ^[0-9]+$ ]] || die "reviewed inventory contains an invalid numeric fact"
done
[[ "${CAPACITY_GATE}" =~ ^[a-z0-9_]+$ ]] || die "reviewed inventory contains an invalid capacity gate"
[[ "${INVENTORY_OBSERVED_AT}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "reviewed inventory contains an invalid observation time"
[[ "${INVENTORY_INSTANCE_ID}" == "${EXPECTED_INSTANCE_ID}" \
  && "${INVENTORY_REGION}" == "${EXPECTED_REGION}" \
  && "${INVENTORY_ZONE}" == "${EXPECTED_ZONE}" \
  && "${INVENTORY_PUBLIC_ADDRESS}" == "${EXPECTED_PUBLIC_ADDRESS}" \
  && "${INVENTORY_SSH_TARGET}" == "${EXPECTED_SSH_TARGET}" ]] \
  || die "reviewed inventory target identity mismatch"

refresh_target_identity() {
  local live_instance live_region live_zone
  live_instance="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/instance-id)" \
    || die "target identity refresh failed"
  live_region="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/placement/region)" \
    || die "target identity refresh failed"
  live_zone="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/placement/zone)" \
    || die "target identity refresh failed"
  [[ "${live_instance}" == "${EXPECTED_INSTANCE_ID}" \
    && "${live_region}" == "${EXPECTED_REGION}" \
    && "${live_zone}" == "${EXPECTED_ZONE}" ]] \
    || die "target identity mismatch; refusing apply"
}

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
[[ "${CAPACITY_GATE}" == "${BLOCKED_GATE}" || "${CAPACITY_GATE}" == "${READY_AFTER_CAPACITY_CLEANUP_GATE}" ]] \
  || die "reviewed capacity gate does not permit bounded whitelist recovery preflight"
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

[[ -n "${WOW_REBUILD_MANAGEMENT_ROLE:-}" ]] || die "WOW_REBUILD_MANAGEMENT_ROLE is required"
[[ "${WOW_REBUILD_MANAGEMENT_ROLE}" =~ ^[a-z_][a-z0-9_]{0,62}$ ]] || die "WOW_REBUILD_MANAGEMENT_ROLE is invalid"
[[ -n "${WOW_REBUILD_PGPASSFILE:-}" && "${WOW_REBUILD_PGPASSFILE}" == /* ]] \
  || die "WOW_REBUILD_PGPASSFILE must be an absolute path"
[[ -n "${WOW_MIGRATION_WECHAT_APP_CONTEXT:-}" ]] || die "WOW_MIGRATION_WECHAT_APP_CONTEXT is required"
[[ "${RECOVERY_ROOT}" == /* && "${RECOVERY_ROOT}" != "/" ]] || die "WOW_CHICKENBRO_RECOVERY_ROOT must be an exact absolute path"
[[ "${MIGRATION_RUNTIME_PYTHON}" == /* && "${MIGRATION_RUNTIME_PYTHON}" != *".."* ]] \
  || die "WOW_CHICKENBRO_MIGRATION_PYTHON must be an exact absolute path"
[[ "${EUID}" -eq 0 ]] || die "--apply must run as root on the reviewed Lighthouse host"

for command_name in python3 realpath stat df awk tr tail date install chmod find sort basename sudo psql pg_dump pg_restore createdb curl; do
  command -v "${command_name}" >/dev/null 2>&1 || die "required apply command is unavailable"
done
[[ -x "${MIGRATION_RUNTIME_PYTHON}" ]] || die "managed migration Python runtime is missing"

# Metadata is deliberately the first apply-side action on the reviewed host.
refresh_target_identity

[[ -d "${POSTGRES_DATA_ROOT}" ]] || die "PostgreSQL data root is missing"
POSTGRES_DATA_REAL="$(realpath -e "${POSTGRES_DATA_ROOT}")"

DATABASE_OWNER_ROLE="${WOW_REBUILD_MANAGEMENT_ROLE}"

pg_query() {
  sudo -n -u postgres psql \
    --no-psqlrc \
    --username=postgres \
    --dbname=postgres \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command="$1" | tr -d '[:space:]'
}

target_query() {
  sudo -n -u postgres psql \
    --no-psqlrc \
    --username=postgres \
    --dbname="${TARGET_DATABASE}" \
    --set=ON_ERROR_STOP=1 \
    --tuples-only \
    --no-align \
    --command="$1" | tr -d '[:space:]'
}

[[ "$(pg_query 'SELECT current_user')" == "postgres" ]] || die "peer-authenticated postgres identity does not match"
[[ "$(pg_query "SELECT count(*) FROM pg_roles WHERE rolname = '${DATABASE_OWNER_ROLE}' AND rolcanlogin")" == "1" ]] || die "target owner role is missing"
[[ "$(pg_query "SELECT count(*) FROM pg_roles WHERE rolname = '${RUNTIME_ROLE}' AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole")" == "1" ]] || die "runtime role is missing or over-privileged"
[[ "$(pg_query "SELECT count(*) FROM pg_database WHERE datname = '${SOURCE_DATABASE}'")" == "1" ]] || die "migration source database is missing"
[[ -f "${WOW_REBUILD_PGPASSFILE}" && ! -L "${WOW_REBUILD_PGPASSFILE}" ]] \
  || die "WOW_REBUILD_PGPASSFILE must be an exact regular file"
[[ "$(stat -c '%a' "${WOW_REBUILD_PGPASSFILE}")" == "600" ]] \
  || die "WOW_REBUILD_PGPASSFILE must have mode 0600"
PGPASS_EXACT_SOURCE_ENTRIES="$(awk -F: \
  -v database="${SOURCE_DATABASE}" -v role="${RUNTIME_ROLE}" \
  '$1 == "127.0.0.1" && $2 == "5432" && $3 == database && $4 == role && length($5) > 0 {count += 1} END {print count + 0}' \
  "${WOW_REBUILD_PGPASSFILE}")"
[[ "${PGPASS_EXACT_SOURCE_ENTRIES}" == "1" ]] \
  || die "source pgpass needs one exact local wow_app entry"
[[ "$(PGPASSFILE="${WOW_REBUILD_PGPASSFILE}" psql --no-psqlrc --host=127.0.0.1 --port=5432 \
  --username="${RUNTIME_ROLE}" --dbname="${SOURCE_DATABASE}" --set=ON_ERROR_STOP=1 \
  --tuples-only --no-align --command='SELECT current_user || chr(9) || current_database()')" \
  == "${RUNTIME_ROLE}"$'\t'"${SOURCE_DATABASE}" ]] \
  || die "explicit source wow_app authentication preflight failed"

SOURCE_DATABASE_BYTES="$(pg_query "SELECT pg_database_size('${SOURCE_DATABASE}')")"
LIVE_DATABASE_BYTES="$(pg_query "SELECT COALESCE(sum(pg_database_size(datname)), 0) FROM pg_database WHERE NOT datistemplate")"
ROOT_FREE_BYTES="$(df_available_bytes "${POSTGRES_DATA_REAL}")"
for number in "${SOURCE_DATABASE_BYTES}" "${LIVE_DATABASE_BYTES}" "${ROOT_FREE_BYTES}"; do
  [[ "${number}" =~ ^[0-9]+$ ]] || die "live capacity probe returned an invalid value"
done

INVENTORY_DRIFT=$(( LIVE_DATABASE_BYTES - INVENTORY_DATABASE_BYTES ))
if (( INVENTORY_DRIFT < 0 )); then
  INVENTORY_DRIFT=$(( -INVENTORY_DRIFT ))
fi
MAX_DATABASE_DRIFT=$(( INVENTORY_DATABASE_BYTES / 20 ))
(( MAX_DATABASE_DRIFT >= 104857600 )) || MAX_DATABASE_DRIFT=104857600
(( INVENTORY_DRIFT <= MAX_DATABASE_DRIFT )) || die "live database bytes drifted from the reviewed inventory; refresh it first"

MINIMUM_WORKING_FREE_BYTES=2147483648
(( ROOT_FREE_BYTES >= MINIMUM_WORKING_FREE_BYTES )) || die "live PostgreSQL device lacks bounded whitelist-migration working capacity"

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
  [[ "${owner}" == "${DATABASE_OWNER_ROLE}" ]] || die "target database owner is unexpected"
  [[ "${runtime_schema_create}" == "0" && "${runtime_database_create}" == "0" ]] || die "runtime role has schema or database creation power"
  [[ "${runtime_business_delete}" == "0" ]] || die "runtime role has destructive business-table privileges"
}

if [[ "${TARGET_DATABASE_EXISTS}" == "1" ]]; then
  TARGET_CONNECTIONS="$(pg_query "SELECT count(*) FROM pg_stat_activity WHERE datname = '${TARGET_DATABASE}'")"
  [[ "${TARGET_CONNECTIONS}" == "0" ]] || die "target database already has active connections"
  die "target database already exists; a fresh clean target is required"
fi

install -d -o root -g root -m 0700 "${RECOVERY_ROOT}"
RECOVERY_ROOT_REAL="$(realpath -e "${RECOVERY_ROOT}")"
[[ "$(stat -c '%a' "${RECOVERY_ROOT_REAL}")" == "700" ]] || die "recovery root must have mode 0700"

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${ACTUAL_INVENTORY_SHA:0:12}"
VERIFY_DATABASE="chickenbro_restore_verify_${RUN_ID//[-TZ]/_}"
VERIFY_DATABASE="${VERIFY_DATABASE:0:63}"
[[ "${VERIFY_DATABASE}" =~ ^chickenbro_restore_verify_[a-zA-Z0-9_]+$ ]] \
  || die "verification database identity is invalid"
RECOVERY_RUN_DIR="${RECOVERY_ROOT_REAL}/chickenbro-prod-provision-${RUN_ID}"
[[ ! -e "${RECOVERY_RUN_DIR}" ]] || die "recovery run identity already exists"
install -d -o root -g root -m 0700 "${RECOVERY_RUN_DIR}"
PROVISION_STATE_FILE="${RECOVERY_RUN_DIR}/provision.state"

record_failure() {
  local exit_code=$?
  if [[ "${exit_code}" -ne 0 ]]; then
    printf '%s\n' 'failed_requires_operator_review' > "${PROVISION_STATE_FILE}"
    chmod 0600 "${PROVISION_STATE_FILE}"
  fi
  exit "${exit_code}"
}
trap record_failure EXIT

printf '%s\n' "${ACTUAL_INVENTORY_SHA}" > "${RECOVERY_RUN_DIR}/inventory.sha256"
printf '%s\n' "${SOURCE_DATABASE}" > "${RECOVERY_RUN_DIR}/source.database"
printf '%s\n' "${TARGET_DATABASE}" > "${RECOVERY_RUN_DIR}/target.database"
chmod 0600 "${RECOVERY_RUN_DIR}"/*

STAGED_PGPASSFILE="${RECOVERY_RUN_DIR}/migration.pgpass"
# Derive exact source/target/restore pgpass entries without printing the password.
python3 - \
  "${WOW_REBUILD_PGPASSFILE}" "${STAGED_PGPASSFILE}" \
  "${SOURCE_DATABASE}" "${TARGET_DATABASE}" "${VERIFY_DATABASE}" <<'PY'
import os
import stat
import sys

source_path, output_path, source_database, target_database, restore_database = sys.argv[1:]
source_stat = os.lstat(source_path)
if stat.S_ISLNK(source_stat.st_mode) or not stat.S_ISREG(source_stat.st_mode):
    raise SystemExit("source pgpass must be a regular non-symlink file")
if stat.S_IMODE(source_stat.st_mode) != 0o600:
    raise SystemExit("source pgpass must have mode 0600")

def split_pgpass(line):
    fields, current, escaped = [], [], False
    for character in line.rstrip("\n"):
        if escaped:
            current.extend(("\\", character))
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":" and len(fields) < 4:
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    fields.append("".join(current))
    return fields

matches = []
with open(source_path, encoding="utf-8") as source:
    for line in source:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = split_pgpass(line)
        if len(fields) == 5 and fields[:4] == ["127.0.0.1", "5432", source_database, "wow_app"]:
            matches.append(fields[4])
if len(matches) != 1 or not matches[0]:
    raise SystemExit("source pgpass needs one exact local wow_app entry")

descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    for database in (source_database, target_database, restore_database):
        output.write(f"127.0.0.1:5432:{database}:wow_app:{matches[0]}\n")
    output.flush()
    os.fsync(output.fileno())
PY
[[ "$(stat -c '%a' "${STAGED_PGPASSFILE}")" == "600" ]] \
  || die "staged pgpass must have mode 0600"
[[ "$(PGPASSFILE="${STAGED_PGPASSFILE}" psql --no-psqlrc --host=127.0.0.1 --port=5432 \
  --username="${RUNTIME_ROLE}" --dbname="${SOURCE_DATABASE}" --set=ON_ERROR_STOP=1 \
  --tuples-only --no-align --command='SELECT current_user || chr(9) || current_database()')" \
  == "${RUNTIME_ROLE}"$'\t'"${SOURCE_DATABASE}" ]] \
  || die "explicit source wow_app authentication preflight failed"

sudo -n -u postgres createdb \
  --username=postgres \
  --owner="${DATABASE_OWNER_ROLE}" \
  --template=template0 \
  --encoding=UTF8 \
  "${TARGET_DATABASE}"

while IFS= read -r migration; do
  migration_name="$(basename "${migration}")"
  migration_id="${migration_name%.sql}"
  [[ "${migration_id}" =~ ^[0-9]{4}_[a-z0-9_]+$ ]] || die "migration filename is invalid"
  sudo -n -u postgres psql \
    --no-psqlrc \
    --username=postgres \
    --dbname="${TARGET_DATABASE}" \
    --set=ON_ERROR_STOP=1 \
    --single-transaction \
    --command="SET ROLE ${DATABASE_OWNER_ROLE}" \
    --file="${migration}" \
    --command="INSERT INTO ops.schema_migrations (id, description) VALUES ('${migration_id}', 'Apply clean product migration ${migration_id}') ON CONFLICT (id) DO NOTHING"
done < <(find "${MIGRATION_DIR}" -maxdepth 1 -type f -name '[0-9][0-9][0-9][0-9]_*.sql' -print | LC_ALL=C sort)

verify_target_identity
[[ "$(PGPASSFILE="${STAGED_PGPASSFILE}" psql --no-psqlrc --host=127.0.0.1 --port=5432 \
  --username="${RUNTIME_ROLE}" --dbname="${TARGET_DATABASE}" --set=ON_ERROR_STOP=1 \
  --tuples-only --no-align --command='SELECT current_database()')" == "${TARGET_DATABASE}" ]] \
  || die "explicit target wow_app authentication preflight failed"
MIGRATION_REPORT="${RECOVERY_RUN_DIR}/migration-report.json"
RESTORE_RECONCILIATION="${RECOVERY_RUN_DIR}/restore-reconciliation.json"
SOURCE_DATABASE_URL="postgresql://${RUNTIME_ROLE}@127.0.0.1:5432/${SOURCE_DATABASE}"
TARGET_DATABASE_URL="postgresql://${RUNTIME_ROLE}@127.0.0.1:5432/${TARGET_DATABASE}"
PGPASSFILE="${STAGED_PGPASSFILE}" \
CHICKENBRO_LEGACY_SOURCE_DATABASE_URL="${SOURCE_DATABASE_URL}" \
WOW_DATABASE_URL="${TARGET_DATABASE_URL}" \
WOW_MIGRATION_WECHAT_APP_CONTEXT="${WOW_MIGRATION_WECHAT_APP_CONTEXT}" \
PYTHONPATH="${REPO_ROOT}" \
  "${MIGRATION_RUNTIME_PYTHON}" -m server.migrations.product.postgres_legacy \
    --mode full \
    --expected-source-database "${SOURCE_DATABASE}" \
    --expected-target-database "${TARGET_DATABASE}" \
    --report-path "${MIGRATION_REPORT}"
python3 - "${MIGRATION_REPORT}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("sourceMode") != "repeatable_read_read_only":
    raise SystemExit("migration source was not read-only")
if payload.get("reconciliation", {}).get("status") != "matched":
    raise SystemExit("MIGRATION_RECONCILIATION_DIVERGED")
PY

TARGET_DATABASE_BYTES="$(pg_query "SELECT pg_database_size('${TARGET_DATABASE}')")"
[[ "${TARGET_DATABASE_BYTES}" =~ ^[0-9]+$ ]] || die "target database size is invalid"
ROOT_FREE_BYTES="$(df_available_bytes "${POSTGRES_DATA_REAL}")"
REQUIRED_RECOVERY_BYTES=$(( TARGET_DATABASE_BYTES * 2 + 1073741824 ))
(( ROOT_FREE_BYTES >= REQUIRED_RECOVERY_BYTES )) \
  || die "insufficient space for whitelist archive and isolated restore verification"

WHITELIST_ARCHIVE="${RECOVERY_RUN_DIR}/business-whitelist.dump"
WHITELIST_RESTORE_LIST="${RECOVERY_RUN_DIR}/business-whitelist.restore-list"
sudo -n -u postgres pg_dump \
  --username=postgres \
  --format=custom \
  --dbname="${TARGET_DATABASE}" > "${WHITELIST_ARCHIVE}"
chmod 0600 "${WHITELIST_ARCHIVE}"
pg_restore --list "${WHITELIST_ARCHIVE}" > "${WHITELIST_RESTORE_LIST}"
chmod 0600 "${WHITELIST_RESTORE_LIST}"
[[ -s "${WHITELIST_ARCHIVE}" && -s "${WHITELIST_RESTORE_LIST}" ]] \
  || die "whitelist archive or pg_restore --list output is empty"
WHITELIST_ARCHIVE_SHA="$(sha256_file "${WHITELIST_ARCHIVE}")"
WHITELIST_ARCHIVE_BYTES="$(stat -c '%s' "${WHITELIST_ARCHIVE}")"

sudo -n -u postgres createdb \
  --username=postgres \
  --owner="${DATABASE_OWNER_ROLE}" \
  --template=template0 \
  --encoding=UTF8 \
  "${VERIFY_DATABASE}"
sudo -n -u postgres pg_restore \
  --exit-on-error \
  --username=postgres \
  --dbname="${VERIFY_DATABASE}" \
  "${WHITELIST_ARCHIVE}"
VERIFY_DATABASE_URL="postgresql://${RUNTIME_ROLE}@127.0.0.1:5432/${VERIFY_DATABASE}"
[[ "$(PGPASSFILE="${STAGED_PGPASSFILE}" psql --no-psqlrc --host=127.0.0.1 --port=5432 \
  --username="${RUNTIME_ROLE}" --dbname="${VERIFY_DATABASE}" --set=ON_ERROR_STOP=1 \
  --tuples-only --no-align --command='SELECT current_database()')" == "${VERIFY_DATABASE}" ]] \
  || die "explicit restore wow_app authentication preflight failed"
PGPASSFILE="${STAGED_PGPASSFILE}" \
WOW_DATABASE_URL="${TARGET_DATABASE_URL}" \
CHICKENBRO_RESTORE_DATABASE_URL="${VERIFY_DATABASE_URL}" \
PYTHONPATH="${REPO_ROOT}" \
  "${MIGRATION_RUNTIME_PYTHON}" -m server.migrations.product.postgres_legacy \
    --mode verify-restore \
    --expected-target-database "${TARGET_DATABASE}" \
    --expected-restore-database "${VERIFY_DATABASE}" \
    --report-path "${RESTORE_RECONCILIATION}"
python3 - "${RESTORE_RECONCILIATION}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("sourceMode") != "candidate_and_restore_repeatable_read_read_only":
    raise SystemExit("restore comparison was not read-only")
if payload.get("comparison", {}).get("status") != "matched":
    raise SystemExit("RESTORE_DATABASE_IDENTITY_MISMATCH")
PY

MIGRATION_REPORT_SHA="$(sha256_file "${MIGRATION_REPORT}")"
RESTORE_RECONCILIATION_SHA="$(sha256_file "${RESTORE_RECONCILIATION}")"
RECOVERY_MANIFEST_NEW="${RECOVERY_ROOT_REAL}/whitelist-recovery.json.new-${RUN_ID}"
python3 - \
  "${RECOVERY_MANIFEST_NEW}" "${WHITELIST_ARCHIVE}" "${WHITELIST_ARCHIVE_SHA}" \
  "${WHITELIST_ARCHIVE_BYTES}" "${MIGRATION_REPORT}" "${MIGRATION_REPORT_SHA}" \
  "${VERIFY_DATABASE}" "${RESTORE_RECONCILIATION}" "${RESTORE_RECONCILIATION_SHA}" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

(
    output_path,
    archive_path,
    archive_sha,
    archive_bytes,
    migration_path,
    migration_sha,
    verify_database,
    restore_path,
    restore_sha,
) = sys.argv[1:]
now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
payload = {
    "schemaVersion": "chickenbro-whitelist-recovery-v1",
    "status": "restore_verified",
    "targetIdentity": {
        "provider": "tencent_cvm",
        "instanceId": "ins-93tgv1rb",
        "region": "ap-shanghai",
        "zone": "ap-shanghai-2",
        "publicAddress": "124.223.51.33",
        "sshTarget": "wow-lighthouse",
    },
    "sourceDatabase": "wow_test",
    "sourceMode": "repeatable_read_read_only",
    "candidateDatabase": "chickenbro_prod",
    "archivePath": archive_path,
    "archiveSha256": archive_sha,
    "archiveBytes": int(archive_bytes),
    "createdAt": now,
    "migrationReport": {"status": "matched", "path": migration_path, "sha256": migration_sha},
    "restore": {
        "targetDatabase": verify_database,
        "commandExitCode": 0,
        "reconciliationStatus": "matched",
        "verifiedAt": now,
        "evidencePath": restore_path,
        "evidenceSha256": restore_sha,
    },
    "restoreReconciliationSha256": restore_sha,
}
descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    json.dump(payload, output, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    output.write("\n")
PY
mv -- "${RECOVERY_MANIFEST_NEW}" "${RECOVERY_ROOT_REAL}/whitelist-recovery.json"
printf '%s\n' 'provisioned_exact_identity' > "${PROVISION_STATE_FILE}"
chmod 0600 "${PROVISION_STATE_FILE}"
trap - EXIT

emit_result "provisioned_exact_identity" "true" "${ROOT_FREE_BYTES}" "${LIVE_DATABASE_BYTES}" "${WHITELIST_ARCHIVE_SHA}"

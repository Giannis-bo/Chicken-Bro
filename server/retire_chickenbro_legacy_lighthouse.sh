#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
SCOPE="full_retirement"
MANIFEST_FILE=""
REVIEWED_MANIFEST_SHA=""
REVIEWED_RECOVERY_MANIFEST_SHA=""

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
REMOTE_RECOVERY_MANIFEST="${WOW_CHICKENBRO_REMOTE_RECOVERY_MANIFEST:-/var/lib/chickenbro-recovery/whitelist-recovery.json}"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15)

die() {
  printf 'retire_chickenbro_legacy: %s\n' "$*" >&2
  return 1
}

usage() {
  printf '%s\n' \
    'Usage:' \
    '  server/retire_chickenbro_legacy_lighthouse.sh --manifest <json> --dry-run' \
    '  server/retire_chickenbro_legacy_lighthouse.sh --manifest <json> --capacity-pre-cleanup --apply --manifest-sha <sha256> --recovery-manifest-sha <sha256>' \
    '  server/retire_chickenbro_legacy_lighthouse.sh --manifest <json> --apply --manifest-sha <sha256> --recovery-manifest-sha <sha256>' >&2
}

sha256_file() {
  local target="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum -- "${target}" | awk '{print $1}'
  else
    shasum -a 256 -- "${target}" | awk '{print $1}'
  fi
}

validate_deletion_target() {
  local kind="${1:-}"
  local target="${2:-}"
  local scope="${3:-full_retirement}"

  if [[ "${scope}" == "capacity_pre_cleanup" ]]; then
    case "${kind}:${target}" in
      postgres_database:wow_test)
        die "protected target: ${kind}:${target}"
        ;;
      postgres_database:wow_gear_evidence_01adf184_r14|\
      postgres_database:wow_gear_evidence_0be65754_r24|\
      postgres_database:wow_gear_evidence_145dee16_r22|\
      postgres_database:wow_gear_evidence_15f514d5_r23|\
      file:/etc/wow-backend-candidate-gear-evidence-r14.env|\
      file:/etc/wow-backend-candidate-gear-evidence-r24.env|\
      file:/etc/wow-backend-candidate-gear-evidence-r22.env|\
      file:/etc/wow-backend-candidate-gear-evidence-r23.env)
        ;;
      *)
        die "exact capacity allowlist required: ${kind}:${target}"
        ;;
    esac
  fi

  case "${kind}:${target}" in
    postgres_database:chickenbro_prod|postgres_database:postgres|postgres_database:template0|postgres_database:template1|\
    systemd_unit:chickenbro-api.service|systemd_unit:chickenbro-worker.service|\
    systemd_unit:chickenbro-simc-runtime-update.service|\
    directory:/opt/chickenbro|directory:/opt/chickenbro-runtime|directory:/opt/wow-simc|\
    directory:/opt/wow-simc/current|directory:/var/lib/postgresql|directory:/var/www/chickenbro-web|\
    directory:/etc/nginx/ssl|directory:/mnt/chickenbro-backups|\
    file:/etc/chickenbro-api.env|file:/etc/chickenbro-worker.env|file:/etc/chickenbro-source.env|\
    file:/etc/chickenbro-api.pgpass|file:/etc/nginx/sites-available/wow-v2-web|\
    file:/etc/nginx/sites-enabled/api.chickenbro.cloud)
      die "protected target: ${kind}:${target}"
      ;;
  esac

  if [[ -z "${kind}" || -z "${target}" || "${target}" == *'$'* || "${target}" == *'\\'* \
    || "${target}" == *'*'* || "${target}" == *'?'* || "${target}" == *'['* \
    || "${target}" == *']'* || "${target}" == *'{'* || "${target}" == *'}'* \
    || "${target}" == *'..'* || "${target}" == *$'\n'* || "${target}" == *$'\r'* ]]; then
    die "exact target required: ${kind}:${target}"
  fi

  case "${kind}" in
    postgres_database)
      [[ "${target}" =~ ^[a-z][a-z0-9_]{0,62}$ ]] \
        || die "exact target required: ${kind}:${target}"
      [[ "${target}" == wow_* || "${target}" == "chickenbro_candidate" ]] \
        || die "exact target required: ${kind}:${target}"
      ;;
    systemd_unit)
      [[ "${target}" =~ ^[a-z0-9][a-z0-9@_.-]+\.(service|timer)$ ]] \
        || die "exact target required: ${kind}:${target}"
      [[ "${target}" == wow-* || "${target}" == "chickenbro-api-candidate.service" \
        || "${target}" == "chickenbro-worker-candidate.service" ]] \
        || die "exact target required: ${kind}:${target}"
      ;;
    file)
      [[ "${target}" =~ ^/[A-Za-z0-9_.@+/-]+$ && "${target}" != */ && "${target}" != *//* ]] \
        || die "exact target required: ${kind}:${target}"
      [[ "${target}" == /etc/wow-* || "${target}" == /etc/nginx/sites-available/wow-* \
        || "${target}" == /etc/nginx/sites-enabled/wow-* ]] \
        || die "exact target required: ${kind}:${target}"
      ;;
    directory)
      [[ "${target}" =~ ^/[A-Za-z0-9_.@+/-]+$ && "${target}" != */ && "${target}" != *//* ]] \
        || die "exact target required: ${kind}:${target}"
      case "${target}" in
        /|/opt|/var|/var/lib|/var/www|/var/backups|/etc|/etc/systemd|/etc/systemd/system|~)
          die "exact target required: ${kind}:${target}"
          ;;
      esac
      [[ "${target}" == /opt/wow-* || "${target}" == /var/backups/wow-* \
        || "${target}" == /var/lib/wow-* || "${target}" == /var/www/chickenbro-*-candidate \
        || "${target}" == /etc/systemd/system/wow-*.service.d \
        || "${target}" == "/opt/chickenbro-candidate" || "${target}" == "/var/www/chickenbro-candidate" ]] \
        || die "exact target required: ${kind}:${target}"
      ;;
    *)
      die "exact target required: ${kind}:${target}"
      ;;
  esac
}

validate_manifest_schema() {
  python3 - "${MANIFEST_FILE}" "${REPO_ROOT}" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1]).resolve(strict=True)
root = Path(sys.argv[2]).resolve(strict=True)
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
if payload.get("schemaVersion") != 2 or payload.get("mode") != "dry-run":
    raise SystemExit("invalid cloud cleanup manifest schema")
expected_target = {
    "provider": "tencent_cvm",
    "instanceId": "ins-93tgv1rb",
    "region": "ap-shanghai",
    "zone": "ap-shanghai-2",
    "publicAddress": "124.223.51.33",
    "sshTarget": "wow-lighthouse",
    "refreshRequiredBeforeApply": True,
}
if payload.get("targetIdentity") != expected_target:
    raise SystemExit("cloud cleanup manifest target identity mismatch")
capacity = payload.get("capacityPreCleanup") or {}
accepted_production_recovery = payload.get("acceptedProductionRecovery") or {}
expected_capacity_databases = [
    "wow_gear_evidence_01adf184_r14",
    "wow_gear_evidence_0be65754_r24",
    "wow_gear_evidence_145dee16_r22",
    "wow_gear_evidence_15f514d5_r23",
]
expected_scan_roots = [
    "/etc",
    "/opt/chickenbro",
    "/opt/wow-mini-program",
    "/opt/wow-v2-staging",
    "/var/www",
]
expected_evidence_exclusions = [
    "/opt/chickenbro/docs/refactor/chickenbro-simc-capacity-cleanup-manifest.json",
    "/opt/chickenbro/docs/refactor/chickenbro-simc-cloud-cleanup-manifest.json",
    "/opt/chickenbro/docs/refactor/chickenbro-simc-cloud-inventory.json",
    "/opt/chickenbro/docs/refactor/chickenbro-simc-recovery-inventory.json",
    "/opt/chickenbro/docs/chickenbro-simc-production-runbook.md",
    "/opt/chickenbro/server/retire_chickenbro_legacy_lighthouse.sh",
    "/opt/chickenbro/tests/chickenbro_simc_capacity_cleanup_manifest_test.py",
    "/opt/chickenbro/tests/deploy-chickenbro-candidate.test.js",
    "/opt/chickenbro/tests/retire-chickenbro-legacy.test.js",
]
if (
    capacity.get("exactDatabaseAllowlist") != expected_capacity_databases
    or capacity.get("configurationScanRoots") != expected_scan_roots
    or capacity.get("referenceEvidenceExclusions") != expected_evidence_exclusions
    or capacity.get("protectsWowTest") is not True
    or capacity.get("requiresPhase5Acceptance") is not False
    or accepted_production_recovery.get("manifestSchema") != "chickenbro-accepted-production-recovery-v1"
    or accepted_production_recovery.get("sourceDatabase") != "chickenbro_prod"
):
    raise SystemExit("invalid capacity pre-cleanup contract")
resources = payload.get("resources")
protected = payload.get("protectedResources")
unresolved = payload.get("unresolvedRequiredTargets")
if not isinstance(resources, list) or not resources:
    raise SystemExit("cloud cleanup manifest resources are required")
if not isinstance(protected, list) or not isinstance(unresolved, list):
    raise SystemExit("cloud cleanup manifest protection and blocker lists are required")
inventory = payload.get("sourceInventory") or {}
inventory_rel = inventory.get("path")
if not isinstance(inventory_rel, str) or inventory_rel.startswith("/") or ".." in Path(inventory_rel).parts:
    raise SystemExit("invalid source inventory path")
inventory_path = (root / inventory_rel).resolve(strict=True)
if root not in inventory_path.parents:
    raise SystemExit("source inventory escapes repository")
actual_inventory_sha = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
if actual_inventory_sha != inventory.get("sha256"):
    raise SystemExit("source inventory SHA-256 mismatch")

ids = set()
targets = set()
allowed_kinds = {"systemd_unit", "postgres_database", "file", "directory"}
for index, item in enumerate(resources):
    if not isinstance(item, dict):
        raise SystemExit(f"resource {index} must be an object")
    resource_id = item.get("id")
    kind = item.get("kind")
    target = item.get("target")
    if not isinstance(resource_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", resource_id):
        raise SystemExit(f"resource {index} has invalid id")
    if resource_id in ids:
        raise SystemExit(f"duplicate resource id: {resource_id}")
    ids.add(resource_id)
    if kind not in allowed_kinds or not isinstance(target, str):
        raise SystemExit(f"resource {resource_id} has invalid target")
    identity = (kind, target)
    if identity in targets:
        raise SystemExit(f"duplicate cleanup target: {kind}:{target}")
    targets.add(identity)
    if item.get("gateStatus") not in {"blocked", "ready"}:
        raise SystemExit(f"resource {resource_id} has invalid gate status")
    if item.get("restoreCheck") not in {"not_run", "passed", "not_required"}:
        raise SystemExit(f"resource {resource_id} has invalid restore status")
    if "currentReferences" not in item or "activeConnections" not in item:
        raise SystemExit(f"resource {resource_id} lacks current reference or connection state")
    if "backupIdentity" not in item or "deleteAfter" not in item or "replacement" not in item:
        raise SystemExit(f"resource {resource_id} lacks recovery, replacement or time boundary")
    if item.get("gateStatus") == "blocked" and not item.get("blockedReasons"):
        raise SystemExit(f"blocked resource {resource_id} lacks reasons")
    if item.get("gateStatus") == "ready":
        capacity_item = item.get("capacityPreCleanup") is True
        expected_reference = [item.get("requiredAbsentCompanion")] if item.get("requiredAbsentCompanion") else []
        if item.get("currentReferences") not in ([], expected_reference):
            raise SystemExit(f"ready resource {resource_id} lacks reviewed references")
        if not capacity_item and item.get("restoreCheck") != "passed":
            raise SystemExit(f"ready resource {resource_id} lacks restore proof")
        if capacity_item and item.get("restoreCheck") not in {"passed", "not_required"}:
            raise SystemExit(f"ready capacity resource {resource_id} lacks recovery disposition")
        if kind == "postgres_database" and item.get("activeConnections") != 0:
            raise SystemExit(f"ready database {resource_id} lacks zero-connection proof")
        if capacity_item and kind == "postgres_database":
            observed = item.get("observed") or {}
            if (
                not isinstance(observed.get("tableCount"), int)
                or isinstance(observed.get("tableCount"), bool)
                or observed["tableCount"] <= 0
                or not isinstance(observed.get("approximateRows"), int)
                or isinstance(observed.get("approximateRows"), bool)
                or observed["approximateRows"] < 0
                or not isinstance(observed.get("owner"), str)
                or re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", observed["owner"]) is None
                or not isinstance(observed.get("allowsConnections"), bool)
            ):
                raise SystemExit(f"ready capacity database {resource_id} lacks table/row counts")
        if kind != "postgres_database" and not re.fullmatch(r"[0-9a-f]{64}", str(item.get("contentSha256") or "")):
            raise SystemExit(f"ready filesystem resource {resource_id} lacks content identity")
        if not isinstance(item.get("deleteAfter"), str):
            raise SystemExit(f"ready resource {resource_id} lacks delete-after boundary")
protected_targets = {(item.get("kind"), item.get("target")) for item in protected if isinstance(item, dict)}
collision = targets & protected_targets
if collision:
    raise SystemExit(f"cleanup manifest targets protected resources: {sorted(collision)}")
PY
}

validate_manifest_targets() {
  while IFS=$'\t' read -r kind target; do
    validate_deletion_target "${kind}" "${target}" "${SCOPE}"
  done < <(python3 - "${MANIFEST_FILE}" "${SCOPE}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
scope = sys.argv[2]
for item in payload["resources"]:
    if scope == "capacity_pre_cleanup" and item.get("capacityPreCleanup") is not True:
        continue
    print(f"{item['kind']}\t{item['target']}")
PY
  )
}

print_dry_run() {
  python3 - "${MANIFEST_FILE}" "${SCOPE}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
scope = sys.argv[2]
results = []
for item in payload["resources"]:
    if scope == "capacity_pre_cleanup" and item.get("capacityPreCleanup") is not True:
        continue
    status = "ready" if item["gateStatus"] == "ready" else "blocked"
    results.append({
        "id": item["id"],
        "kind": item["kind"],
        "target": item["target"],
        "status": status,
        "blockedReasons": item.get("blockedReasons", []) if status == "blocked" else [],
    })
ready = sum(item["status"] == "ready" for item in results)
blocked = len(results) - ready
print(json.dumps({
    "mode": "dry-run",
    "scope": scope,
    "mutationAuthorized": False,
    "manifestFileSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "sourceInventory": payload["sourceInventory"],
    "productionAcceptance": payload["productionAcceptance"]["status"],
    "businessRecovery": payload["businessRecovery"]["status"],
    "counts": {"total": len(results), "ready": ready, "blocked": blocked},
    "unresolvedBlockerCount": len(payload["unresolvedRequiredTargets"]),
    "results": results,
}, separators=(",", ":")))
PY
}

assert_apply_ready() {
  python3 - "${MANIFEST_FILE}" "${REVIEWED_RECOVERY_MANIFEST_SHA}" "${SCOPE}" <<'PY'
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
recovery_sha = sys.argv[2]
scope = sys.argv[3]
capacity = payload.get("capacityPreCleanup") or {}
if scope == "capacity_pre_cleanup":
    if capacity.get("authorized") is not True:
        raise SystemExit("capacityPreCleanup.authorized=true is required for a blocked cleanup manifest")
else:
    if payload.get("deletionAuthorized") is not True:
        raise SystemExit("deletionAuthorized=true is required for a blocked cleanup manifest")
    if payload.get("unresolvedRequiredTargets"):
        raise SystemExit("blocked cleanup manifest has unresolved required targets")
    acceptance = payload.get("productionAcceptance") or {}
    if acceptance.get("status") != "passed" or acceptance.get("firstNewWriteReconciled") is not True or acceptance.get("stableHealthWindowCompleted") is not True:
        raise SystemExit("blocked cleanup manifest lacks accepted production evidence")
if scope == "capacity_pre_cleanup":
    recovery = payload.get("businessRecovery") or {}
    if (
        recovery.get("status") != "restore_verified"
        or recovery.get("manifestSchema") != "chickenbro-whitelist-recovery-v1"
        or recovery.get("manifestSha256") != recovery_sha
        or recovery.get("sourceDatabase") != "wow_test"
        or recovery.get("sourceMode") != "read_only"
    ):
        raise SystemExit("blocked cleanup manifest lacks matching whitelist restore evidence")
else:
    recovery = payload.get("acceptedProductionRecovery") or {}
    if (
        recovery.get("status") != "restore_verified"
        or recovery.get("manifestSchema") != "chickenbro-accepted-production-recovery-v1"
        or recovery.get("manifestSha256") != recovery_sha
        or recovery.get("sourceDatabase") != "chickenbro_prod"
    ):
        raise SystemExit("blocked cleanup manifest lacks accepted production recovery evidence")
if payload.get("sourceInventory", {}).get("freshness") != "fresh":
    raise SystemExit("blocked cleanup manifest uses a stale cloud inventory")
resources = [
    item for item in payload["resources"]
    if scope != "capacity_pre_cleanup" or item.get("capacityPreCleanup") is True
]
if scope == "capacity_pre_cleanup":
    expected = {
        *(('postgres_database', name) for name in capacity["exactDatabaseAllowlist"]),
        ('file', '/etc/wow-backend-candidate-gear-evidence-r14.env'),
        ('file', '/etc/wow-backend-candidate-gear-evidence-r24.env'),
        ('file', '/etc/wow-backend-candidate-gear-evidence-r22.env'),
        ('file', '/etc/wow-backend-candidate-gear-evidence-r23.env'),
    }
    actual = {(item.get("kind"), item.get("target")) for item in resources}
    if actual != expected or ('postgres_database', 'wow_test') in actual:
        raise SystemExit("capacity cleanup resources differ from the exact allowlist")
now = datetime.now(timezone.utc)
for item in resources:
    if item.get("gateStatus") != "ready":
        raise SystemExit(f"blocked cleanup manifest resource: {item.get('id')}")
    value = item.get("deleteAfter")
    try:
        boundary = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise SystemExit(f"invalid delete-after boundary: {item.get('id')}")
    if boundary > now:
        raise SystemExit(f"delete-after boundary has not elapsed: {item.get('id')}")
if not re.fullmatch(r"[0-9a-f]{64}", recovery_sha):
    raise SystemExit("invalid recovery manifest SHA-256")
PY
}

run_remote_apply() {
  local manifest_base64
  manifest_base64="$(base64 < "${MANIFEST_FILE}" | tr -d '\n')"

  ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" \
    "MANIFEST_BASE64=${manifest_base64}" \
    "REVIEWED_REMOTE_MANIFEST_SHA=${REVIEWED_MANIFEST_SHA}" \
    "REVIEWED_REMOTE_RECOVERY_SHA=${REVIEWED_RECOVERY_MANIFEST_SHA}" \
    "REMOTE_RECOVERY_MANIFEST_PATH=${REMOTE_RECOVERY_MANIFEST}" \
    "RETIREMENT_SCOPE=${SCOPE}" \
    bash -s <<'REMOTE'
set -euo pipefail

die_remote() {
  printf 'retire_chickenbro_legacy_remote: %s\n' "$*" >&2
  exit 1
}

MANIFEST_TMP=""
RESULTS_TMP=""
cleanup_remote_tmp() {
  [[ -z "${MANIFEST_TMP}" ]] || rm -f -- "${MANIFEST_TMP}"
  [[ -z "${RESULTS_TMP}" ]] || rm -f -- "${RESULTS_TMP}"
}
trap cleanup_remote_tmp EXIT
for command_name in curl lsof realpath find sort sha256sum psql python3 install mv; do
  command -v "${command_name}" >/dev/null 2>&1 || die_remote "required apply command is unavailable: ${command_name}"
done
# Metadata is deliberately the first apply-side action on the reviewed host.
LIVE_INSTANCE_ID="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/instance-id)" \
  || die_remote "target identity refresh failed"
LIVE_REGION="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/placement/region)" \
  || die_remote "target identity refresh failed"
LIVE_ZONE="$(curl -fsS --max-time 3 http://metadata.tencentyun.com/latest/meta-data/placement/zone)" \
  || die_remote "target identity refresh failed"
[[ "${LIVE_INSTANCE_ID}" == "ins-93tgv1rb" && "${LIVE_REGION}" == "ap-shanghai" \
  && "${LIVE_ZONE}" == "ap-shanghai-2" ]] \
  || die_remote "target identity mismatch; refusing retirement apply"
MANIFEST_TMP="$(mktemp)"
RESULTS_TMP="$(mktemp)"
printf '%s' "${MANIFEST_BASE64}" | base64 --decode > "${MANIFEST_TMP}"
[[ "$(sha256sum -- "${MANIFEST_TMP}" | awk '{print $1}')" == "${REVIEWED_REMOTE_MANIFEST_SHA}" ]] \
  || die_remote "manifest SHA-256 changed in transit"
[[ -f "${REMOTE_RECOVERY_MANIFEST_PATH}" ]] || die_remote "restore-verified whitelist recovery manifest is missing"
[[ "$(sha256sum -- "${REMOTE_RECOVERY_MANIFEST_PATH}" | awk '{print $1}')" == "${REVIEWED_REMOTE_RECOVERY_SHA}" ]] \
  || die_remote "recovery manifest SHA-256 mismatch"

python3 - "${REMOTE_RECOVERY_MANIFEST_PATH}" "${RETIREMENT_SCOPE}" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
scope = sys.argv[2]
expected_schema = (
    "chickenbro-whitelist-recovery-v1"
    if scope == "capacity_pre_cleanup"
    else "chickenbro-accepted-production-recovery-v1"
)
expected_source = "wow_test" if scope == "capacity_pre_cleanup" else "chickenbro_prod"
expected_target_identity = {
    "provider": "tencent_cvm",
    "instanceId": "ins-93tgv1rb",
    "region": "ap-shanghai",
    "zone": "ap-shanghai-2",
    "publicAddress": "124.223.51.33",
    "sshTarget": "wow-lighthouse",
}
if manifest_path.is_symlink() or manifest_path.stat().st_mode & 0o077:
    raise SystemExit("recovery manifest permissions are not root-only")
root = manifest_path.parent.resolve(strict=True)
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
if (
    payload.get("schemaVersion") != expected_schema
    or payload.get("status") != "restore_verified"
    or payload.get("sourceDatabase") != expected_source
    or payload.get("targetIdentity") != expected_target_identity
    or payload.get("restore", {}).get("reconciliationStatus") != "matched"
):
    raise SystemExit("recovery manifest has no completed isolated restore reconciliation")
if scope == "capacity_pre_cleanup" and payload.get("sourceMode") != "repeatable_read_read_only":
    raise SystemExit("whitelist recovery source was not read-only")

archive_sha = str(payload.get("archiveSha256", ""))
archive_bytes = payload.get("archiveBytes")
migration = payload.get("migrationReport") or {}
restore = payload.get("restore") or {}
restore_sha = str(restore.get("evidenceSha256", ""))
restore_target = str(restore.get("targetDatabase", ""))
if (
    re.fullmatch(r"[0-9a-f]{64}", archive_sha) is None
    or not isinstance(archive_bytes, int)
    or isinstance(archive_bytes, bool)
    or archive_bytes <= 0
    or migration.get("status") != "matched"
    or re.fullmatch(r"[0-9a-f]{64}", str(migration.get("sha256", ""))) is None
    or restore.get("commandExitCode") != 0
    or re.fullmatch(r"chickenbro_restore_verify_[a-z0-9_]{1,40}", restore_target) is None
    or restore_target in {expected_source, "chickenbro_prod"}
    or re.fullmatch(r"[0-9a-f]{64}", restore_sha) is None
    or payload.get("restoreReconciliationSha256") != restore_sha
):
    raise SystemExit("recovery manifest hash or restore identity is invalid")

for raw_path, expected_sha, expected_bytes in (
    (payload.get("archivePath"), archive_sha, archive_bytes),
    (migration.get("path"), str(migration.get("sha256")), None),
    (restore.get("evidencePath"), restore_sha, None),
):
    path = Path(str(raw_path))
    if not path.is_absolute() or path.is_symlink():
        raise SystemExit("recovery evidence path is invalid")
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(root):
        raise SystemExit("recovery evidence escapes its root")
    if expected_bytes is not None and resolved.stat().st_size != expected_bytes:
        raise SystemExit("recovery archive byte count changed")
    digest = hashlib.sha256()
    with resolved.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha:
        raise SystemExit("recovery evidence SHA-256 changed")
PY

QUARANTINE_ROOT="$(python3 - "${MANIFEST_TMP}" <<'PY'
import json
import sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["quarantine"]["root"])
PY
)"
[[ "${QUARANTINE_ROOT}" == /var/lib/chickenbro-retirement-quarantine ]] \
  || die_remote "unexpected quarantine root"
RUN_ROOT="${QUARANTINE_ROOT}/${REVIEWED_REMOTE_MANIFEST_SHA}"
install -d -o root -g root -m 0700 -- "${RUN_ROOT}"
nginx -t
if [[ "${RETIREMENT_SCOPE}" != "capacity_pre_cleanup" ]]; then
  systemctl is-active --quiet chickenbro-api.service || die_remote "protected production API is not active"
  systemctl is-active --quiet chickenbro-worker.service || die_remote "protected production worker is not active"
  [[ "$(systemctl show chickenbro-simc-runtime-update.service --property=LoadState --value)" == "loaded" ]] \
    || die_remote "protected SimulationCraft updater is not loaded"
  [[ -x /opt/chickenbro/server/chickenbro_simc_runtime_update.sh ]] \
    || die_remote "protected SimulationCraft updater script is missing"
  [[ -e /opt/wow-simc/current ]] || die_remote "protected SimC runtime is missing"
fi
protected_database_exists="$(sudo -n -u postgres psql -d postgres -At --command="SELECT count(*) FROM pg_database WHERE datname = 'chickenbro_prod'")"
[[ "${protected_database_exists}" == "1" ]] || die_remote "protected production database is missing"

python3 - "${MANIFEST_TMP}" "${RETIREMENT_SCOPE}" <<'PY' > "${RUN_ROOT}/retirement-plan.tsv"
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
scope = sys.argv[2]
order = {"systemd_unit": 0, "file": 1, "postgres_database": 2, "directory": 3}
def resource_order(row):
    enabled_link_first = 0 if row["kind"] == "file" and "/sites-enabled/" in row["target"] else 1
    return (order[row["kind"]], enabled_link_first, row["target"])

for item in sorted(payload["resources"], key=resource_order):
    if scope == "capacity_pre_cleanup" and item.get("capacityPreCleanup") is not True:
        continue
    print("\t".join([
        item["id"], item["kind"], item["target"], item.get("contentSha256") or "-",
        str((item.get("observed") or {}).get("sizeBytes") or "-"),
        item.get("requiredAbsentCompanion") or "-",
    ]))
PY
awk -F '\t' '$2 == "systemd_unit" { print $3 }' "${RUN_ROOT}/retirement-plan.tsv" \
  > "${RUN_ROOT}/retiring-units.txt"

CAPACITY_PAIRS="${RUN_ROOT}/capacity-pairs.tsv"
CONFIGURATION_SCAN_ROOTS="${RUN_ROOT}/configuration-scan-roots.txt"
REFERENCE_EVIDENCE_EXCLUSIONS="${RUN_ROOT}/reference-evidence-exclusions.txt"
python3 - \
    "${MANIFEST_TMP}" "${CAPACITY_PAIRS}" "${CONFIGURATION_SCAN_ROOTS}" \
    "${REFERENCE_EVIDENCE_EXCLUSIONS}" <<'PY'
import json
import os
import sys
from pathlib import Path

manifest_path, pairs_path, roots_path, exclusions_path = map(Path, sys.argv[1:])
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
capacity = payload["capacityPreCleanup"]
resources = payload["resources"]
by_target = {(item["kind"], item["target"]): item for item in resources}
rows = []
for database in capacity["exactDatabaseAllowlist"]:
    db_item = by_target[("postgres_database", database)]
    env_path = db_item["requiredAbsentCompanion"]
    env_item = by_target[("file", env_path)]
    observed = db_item["observed"]
    rows.append("\t".join([
        db_item["id"], database, env_item["id"], env_path,
        env_item["contentSha256"], str(observed["sizeBytes"]),
        str(observed["tableCount"]), str(observed["approximateRows"]),
        observed["owner"], "true" if observed["allowsConnections"] else "false",
    ]))

def durable_write(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())

durable_write(pairs_path, "\n".join(rows) + "\n")
durable_write(roots_path, "\n".join(capacity["configurationScanRoots"]) + "\n")
durable_write(exclusions_path, "\n".join(capacity["referenceEvidenceExclusions"]) + "\n")
PY

record_result() {
  local resource_id="$1"
  local kind="$2"
  local target="$3"
  local status="$4"
  local before="${5:-{}}"
  local after="${6:-{}}"
  RESOURCE_ID="${resource_id}" RESOURCE_KIND="${kind}" RESOURCE_TARGET="${target}" RESOURCE_STATUS="${status}" \
  RESOURCE_BEFORE="${before}" RESOURCE_AFTER="${after}" RESOURCE_RECOVERY_SHA="${REVIEWED_REMOTE_RECOVERY_SHA}" \
    python3 - <<'PY' >> "${RESULTS_TMP}"
import json
import os
from datetime import datetime, timezone
print(json.dumps({
    "id": os.environ["RESOURCE_ID"],
    "kind": os.environ["RESOURCE_KIND"],
    "target": os.environ["RESOURCE_TARGET"],
    "status": os.environ["RESOURCE_STATUS"],
    "before": json.loads(os.environ["RESOURCE_BEFORE"]),
    "after": json.loads(os.environ["RESOURCE_AFTER"]),
    "recoveryManifestSha256": os.environ["RESOURCE_RECOVERY_SHA"],
    "recordedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
}, separators=(",", ":")))
PY
}

tree_sha256() {
  python3 - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
digest = hashlib.sha256()
items = sorted(root.rglob("*"))
for path in items:
    if path.is_symlink():
        raise SystemExit("tree identity refuses symbolic links")
    if not path.is_file():
        continue
    digest.update(path.relative_to(root).as_posix().encode())
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
print(digest.hexdigest())
PY
}

process_environment_reference_count() {
  local needle="$1"
  local count=0 process_env
  for process_env in /proc/[0-9]*/environ; do
    if grep -Fq -- "${needle}" "${process_env}" 2>/dev/null; then
      count=$(( count + 1 ))
    fi
  done
  printf '%s\n' "${count}"
}

runtime_configuration_references() {
  local needle="$1"
  local root candidate
  while IFS= read -r root; do
    [[ -d "${root}" ]] || continue
    while IFS= read -r -d '' candidate; do
      if grep -Fxq -- "${candidate}" "${REFERENCE_EVIDENCE_EXCLUSIONS}"; then
        continue
      fi
      grep -Fl -- "${needle}" "${candidate}" 2>/dev/null || true
    done < <(find "${root}" -type f -print0 2>/dev/null)
  done < "${CONFIGURATION_SCAN_ROOTS}"
}

validate_capacity_env_file() {
  local target="$1"
  local expected_sha="$2"
  local target_real
  [[ "${target%/*}" == "/etc" ]] || die_remote "capacity env is outside exact /etc root: ${target}"
  [[ -f "${target}" && ! -L "${target}" ]] \
    || die_remote "capacity env must be a regular non-symlink file: ${target}"
  target_real="$(realpath -e -- "${target}")"
  [[ "${target_real}" == "${target}" ]] || die_remote "capacity env realpath changed: ${target}"
  [[ "$(sha256sum -- "${target}" | awk '{print $1}')" == "${expected_sha}" ]] \
    || die_remote "capacity env identity changed: ${target}"
  [[ -z "$(lsof -t -- "${target}" 2>/dev/null || true)" ]] \
    || die_remote "capacity env has an open handle: ${target}"
  [[ -z "$(runtime_configuration_references "${target}")" ]] \
    || die_remote "capacity env still has configuration references: ${target}"
}

fresh_database_counts() {
  local target="$1"
  sudo -n -u postgres psql --no-psqlrc --dbname="${target}" --tuples-only --no-align \
    --field-separator=$'\t' --set=ON_ERROR_STOP=1 \
    --command="SELECT count(*)::bigint, COALESCE(sum(n_live_tup), 0)::bigint FROM pg_stat_user_tables"
}

capacity_preflight_all_pairs() {
  local db_id database env_id env_path env_sha expected_size expected_table_count expected_row_count expected_owner expected_allows
  local exists connections current_size current_counts current_table_count current_row_count current_identity current_owner current_allows references
  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_row_count expected_owner expected_allows; do
    validate_capacity_env_file "${env_path}" "${env_sha}"
    exists="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=target="${database}" --command="SELECT count(*) FROM pg_database WHERE datname = :'target'")"
    [[ "${exists}" == "1" ]] || die_remote "capacity database is missing: ${database}"
    connections="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=target="${database}" --command="SELECT count(*) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid()")"
    [[ "${connections}" == "0" ]] || die_remote "capacity database gained active connections: ${database}"
    current_size="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=target="${database}" --command="SELECT pg_database_size(:'target')")"
    [[ "${current_size}" == "${expected_size}" ]] || die_remote "capacity database size identity changed: ${database}"
    current_counts="$(fresh_database_counts "${database}" | tr -d ' ')"
    IFS=$'\t' read -r current_table_count current_row_count <<< "${current_counts}"
    [[ "${current_table_count}" == "${expected_table_count}" && "${current_row_count}" == "${expected_row_count}" ]] \
      || die_remote "capacity database table/row counts changed: ${database}"
    current_identity="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --field-separator=$'\t' --set=target="${database}" \
      --command="SELECT pg_get_userbyid(datdba), CASE WHEN datallowconn THEN 'true' ELSE 'false' END FROM pg_database WHERE datname = :'target'")"
    IFS=$'\t' read -r current_owner current_allows <<< "${current_identity}"
    [[ "${current_owner}" == "${expected_owner}" && "${current_allows}" == "${expected_allows}" ]] \
      || die_remote "capacity database owner/connection identity changed: ${database}"
    references="$(runtime_configuration_references "${database}" | LC_ALL=C sort -u)"
    [[ "${references}" == "${env_path}" ]] \
      || die_remote "database configuration references differ from exact companion: ${database}"
    [[ "$(process_environment_reference_count "${database}")" == "0" ]] \
      || die_remote "capacity database still has a running process reference: ${database}"
  done < "${CAPACITY_PAIRS}"
}

write_capacity_pair_journal() {
  local journal_path="$1" status="$2" database="$3" env_path="$4" env_sha="$5"
  local size="$6" table_count="$7" row_count="$8" owner="$9" allows="${10}"
  local after_database_exists="${11:-}" after_env_exists="${12:-}"
  JOURNAL_PATH="${journal_path}" JOURNAL_STATUS="${status}" JOURNAL_DATABASE="${database}" \
  JOURNAL_ENV_PATH="${env_path}" JOURNAL_ENV_SHA="${env_sha}" JOURNAL_SIZE="${size}" \
  JOURNAL_TABLE_COUNT="${table_count}" JOURNAL_ROW_COUNT="${row_count}" JOURNAL_OWNER="${owner}" \
  JOURNAL_ALLOWS="${allows}" JOURNAL_AFTER_DATABASE_EXISTS="${after_database_exists}" \
  JOURNAL_AFTER_ENV_EXISTS="${after_env_exists}" JOURNAL_RECOVERY_SHA="${REVIEWED_REMOTE_RECOVERY_SHA}" \
    python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

journal = Path(os.environ["JOURNAL_PATH"])
now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
if journal.exists():
    payload = json.loads(journal.read_text(encoding="utf-8"))
else:
    payload = {
        "schemaVersion": "chickenbro-capacity-pair-journal-v1",
        "database": os.environ["JOURNAL_DATABASE"],
        "envFile": os.environ["JOURNAL_ENV_PATH"],
        "recoveryManifestSha256": os.environ["JOURNAL_RECOVERY_SHA"],
        "before": {
            "database": {
                "exists": True,
                "sizeBytes": int(os.environ["JOURNAL_SIZE"]),
                "tableCount": int(os.environ["JOURNAL_TABLE_COUNT"]),
                "approximateRows": int(os.environ["JOURNAL_ROW_COUNT"]),
                "owner": os.environ["JOURNAL_OWNER"],
                "allowsConnections": os.environ["JOURNAL_ALLOWS"] == "true",
                "activeConnections": 0,
            },
            "envFile": {
                "exists": True,
                "realpath": os.environ["JOURNAL_ENV_PATH"],
                "sha256": os.environ["JOURNAL_ENV_SHA"],
                "openHandles": 0,
            },
        },
        "events": [],
    }
payload["events"].append({"status": os.environ["JOURNAL_STATUS"], "at": now})
if os.environ["JOURNAL_AFTER_DATABASE_EXISTS"]:
    payload["after"] = {
        "database": {"exists": os.environ["JOURNAL_AFTER_DATABASE_EXISTS"] == "true"},
        "envFile": {"exists": os.environ["JOURNAL_AFTER_ENV_EXISTS"] == "true"},
        "observedAt": now,
    }
temporary = journal.with_name(f"{journal.name}.new-{os.getpid()}")
descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    json.dump(payload, output, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    output.write("\n")
    output.flush()
    os.fsync(output.fileno())
os.replace(temporary, journal)
directory = os.open(journal.parent, os.O_RDONLY)
try:
    os.fsync(directory)
finally:
    os.close(directory)
PY
}

capacity_pair_failure() {
  local exit_code="$1"
  trap - ERR
  set +e
  local exists recovery_incomplete="false" restored_allows="" restored_env_sha="" restored_env_exists="false"
  exists="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --set=target="${PAIR_DATABASE}" --command="SELECT count(*) FROM pg_database WHERE datname = :'target'" 2>/dev/null)"
  if [[ "${exists}" == "1" ]]; then
    if [[ "${PAIR_DATABASE_FENCED}" == "true" ]]; then
      restore_statement="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
        --set=target="${PAIR_DATABASE}" --set=allows="${PAIR_EXPECTED_ALLOWS}" \
        --command="SELECT format('ALTER DATABASE %I WITH ALLOW_CONNECTIONS %s', :'target', :'allows')")"
      sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
        --command="${restore_statement}" >/dev/null || recovery_incomplete="true"
    fi
    if [[ "${PAIR_ENV_MOVED}" == "true" && ! -e "${PAIR_ENV_PATH}" && -f "${PAIR_QUARANTINE_TARGET}" ]]; then
      mv -- "${PAIR_QUARANTINE_TARGET}" "${PAIR_ENV_PATH}" || recovery_incomplete="true"
    fi
    restored_allows="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=target="${PAIR_DATABASE}" \
      --command="SELECT CASE WHEN datallowconn THEN 'true' ELSE 'false' END FROM pg_database WHERE datname = :'target'" 2>/dev/null)"
    [[ "${restored_allows}" == "${PAIR_EXPECTED_ALLOWS}" ]] || recovery_incomplete="true"
    if [[ -f "${PAIR_ENV_PATH}" && ! -L "${PAIR_ENV_PATH}" ]]; then
      restored_env_sha="$(sha256sum -- "${PAIR_ENV_PATH}" 2>/dev/null | awk '{print $1}')"
    fi
    [[ "${restored_env_sha}" == "${PAIR_ENV_SHA}" ]] || recovery_incomplete="true"
    [[ "${restored_env_sha}" != "${PAIR_ENV_SHA}" ]] || restored_env_exists="true"
    recovery_status="failed_recovered"
    [[ "${recovery_incomplete}" == "false" ]] || recovery_status="failed_recovery_incomplete"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "${recovery_status}" "${PAIR_DATABASE}" "${PAIR_ENV_PATH}" \
      "${PAIR_ENV_SHA}" "${PAIR_SIZE}" "${PAIR_TABLE_COUNT}" "${PAIR_ROW_COUNT}" "${PAIR_OWNER}" "${PAIR_EXPECTED_ALLOWS}" \
      true "${restored_env_exists}" || true
  else
    write_capacity_pair_journal "${PAIR_JOURNAL}" "failed_after_drop" "${PAIR_DATABASE}" "${PAIR_ENV_PATH}" \
      "${PAIR_ENV_SHA}" "${PAIR_SIZE}" "${PAIR_TABLE_COUNT}" "${PAIR_ROW_COUNT}" "${PAIR_OWNER}" "${PAIR_EXPECTED_ALLOWS}" \
      false false
  fi
  exit "${exit_code}"
}

capacity_pair_abort() {
  printf 'retire_chickenbro_legacy_remote: %s\n' "$*" >&2
  return 1
}

capacity_apply_pairs() {
  local db_id database env_id env_path env_sha expected_size expected_table_count expected_row_count expected_owner expected_allows
  install -d -o root -g root -m 0700 -- "${RUN_ROOT}/pair-journals"
  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_row_count expected_owner expected_allows; do
    write_capacity_pair_journal "${RUN_ROOT}/pair-journals/${db_id}.json" "preflight_complete" \
      "${database}" "${env_path}" "${env_sha}" "${expected_size}" "${expected_table_count}" \
      "${expected_row_count}" "${expected_owner}" "${expected_allows}"
  done < "${CAPACITY_PAIRS}"

  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_row_count expected_owner expected_allows; do
    PAIR_DATABASE="${database}"
    PAIR_ENV_PATH="${env_path}"
    PAIR_ENV_SHA="${env_sha}"
    PAIR_SIZE="${expected_size}"
    PAIR_TABLE_COUNT="${expected_table_count}"
    PAIR_ROW_COUNT="${expected_row_count}"
    PAIR_OWNER="${expected_owner}"
    PAIR_EXPECTED_ALLOWS="${expected_allows}"
    PAIR_QUARANTINE_TARGET="${RUN_ROOT}/${env_id}"
    PAIR_JOURNAL="${RUN_ROOT}/pair-journals/${db_id}.json"
    PAIR_ENV_MOVED="false"
    PAIR_DATABASE_FENCED="false"
    trap 'capacity_pair_failure "$?"' ERR

    mv -- "${env_path}" "${PAIR_QUARANTINE_TARGET}"
    PAIR_ENV_MOVED="true"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "env_quarantined" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_row_count}" "${expected_owner}" "${expected_allows}"
    if [[ -e "${env_path}" || -L "${env_path}" ]]; then
      capacity_pair_abort "database companion env still exists: ${database}"
    fi
    if [[ -n "$(runtime_configuration_references "${database}")" ]]; then
      capacity_pair_abort "database still has configuration references after companion quarantine: ${database}"
    fi

    fence_statement="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=target="${database}" --command="SELECT format('ALTER DATABASE %I WITH ALLOW_CONNECTIONS false', :'target')")"
    sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
      --command="${fence_statement}" >/dev/null
    PAIR_DATABASE_FENCED="true"
    sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 --set=target="${database}" \
      --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid()" >/dev/null
    write_capacity_pair_journal "${PAIR_JOURNAL}" "connections_fenced" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_row_count}" "${expected_owner}" "${expected_allows}"
    connections="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=target="${database}" --command="SELECT count(*) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid()")"
    if [[ "${connections}" != "0" ]]; then
      capacity_pair_abort "database gained a connection after fencing: ${database}"
    fi

    write_capacity_pair_journal "${PAIR_JOURNAL}" "drop_started" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_row_count}" "${expected_owner}" "${expected_allows}"
    drop_statement="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=ON_ERROR_STOP=1 --set=target="${database}" --command="SELECT format('DROP DATABASE %I', :'target')")"
    sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
      --command="${drop_statement}" >/dev/null
    write_capacity_pair_journal "${PAIR_JOURNAL}" "completed" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_row_count}" "${expected_owner}" "${expected_allows}" \
      false false
    record_result "${env_id}" "file" "${env_path}" "deleted" \
      "{\"exists\":true,\"realpath\":\"${env_path}\",\"sha256\":\"${env_sha}\"}" '{"exists":false}'
    record_result "${db_id}" "postgres_database" "${database}" "deleted" \
      "{\"exists\":true,\"sizeBytes\":${expected_size},\"tableCount\":${expected_table_count},\"approximateRows\":${expected_row_count},\"owner\":\"${expected_owner}\"}" '{"exists":false}'
    trap - ERR
  done < "${CAPACITY_PAIRS}"
}

if [[ "${RETIREMENT_SCOPE}" == "capacity_pre_cleanup" ]]; then
  capacity_preflight_all_pairs
  capacity_apply_pairs
else
while IFS=$'\t' read -r resource_id kind target content_sha observed_size required_absent_companion; do
  quarantine_target="${RUN_ROOT}/${resource_id}"
  case "${kind}" in
    systemd_unit)
      unit_path="/etc/systemd/system/${target}"
      if ! systemctl cat "${target}" >/dev/null 2>&1; then
        record_result "${resource_id}" "${kind}" "${target}" "skipped"
        continue
      fi
      [[ -f "${unit_path}" && ! -L "${unit_path}" ]] || die_remote "unit owner is not an exact regular file: ${target}"
      [[ "$(sha256sum -- "${unit_path}" | awk '{print $1}')" == "${content_sha}" ]] \
        || die_remote "unit identity changed: ${target}"
      reverse_dependencies="$(
        systemctl list-dependencies --reverse --plain --no-legend "${target}" 2>/dev/null \
          | sed -E 's/^[^[:alnum:]]*//' \
          | grep -vFx "${target}" \
          | grep -Ev '\.target$' \
          | while IFS= read -r dependent; do
              grep -Fxq -- "${dependent}" "${RUN_ROOT}/retiring-units.txt" || printf '%s\n' "${dependent}"
            done \
          || true
      )"
      [[ -z "${reverse_dependencies}" ]] || die_remote "unit still has reverse dependencies: ${target}"
      systemctl stop "${target}" >/dev/null 2>&1 || true
      systemctl disable "${target}" >/dev/null 2>&1 || true
      mv -- "${unit_path}" "${quarantine_target}"
      record_result "${resource_id}" "${kind}" "${target}" "deleted"
      ;;
    file)
      if [[ ! -e "${target}" && ! -L "${target}" ]]; then
        record_result "${resource_id}" "${kind}" "${target}" "skipped"
        continue
      fi
      [[ -f "${target}" || -L "${target}" ]] || die_remote "file target changed type: ${target}"
      [[ -z "$(lsof -t -- "${target}" 2>/dev/null || true)" ]] \
        || die_remote "file has an open handle: ${target}"
      file_references="$(runtime_configuration_references "${target}")"
      [[ -z "${file_references}" ]] || die_remote "file still has configuration references: ${target}"
      if [[ -L "${target}" ]]; then
        actual_file_sha="$(readlink -- "${target}" | sha256sum | awk '{print $1}')"
      else
        actual_file_sha="$(sha256sum -- "${target}" | awk '{print $1}')"
      fi
      [[ "${actual_file_sha}" == "${content_sha}" ]] \
        || die_remote "file identity changed: ${target}"
      mv -- "${target}" "${quarantine_target}"
      record_result "${resource_id}" "${kind}" "${target}" "deleted"
      ;;
    postgres_database)
      exists="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" --command="SELECT count(*) FROM pg_database WHERE datname = :'target'")"
      if [[ "${exists}" == "0" ]]; then
        record_result "${resource_id}" "${kind}" "${target}" "skipped"
        continue
      fi
      connections="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" --command="SELECT count(*) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid()")"
      [[ "${connections}" == "0" ]] || die_remote "database gained active connections: ${target}"
      current_size="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" --command="SELECT pg_database_size(:'target')")"
      [[ "${observed_size}" =~ ^[0-9]+$ && "${current_size}" == "${observed_size}" ]] \
        || die_remote "database size identity changed: ${target}"
      if [[ "${required_absent_companion}" != "-" ]]; then
        [[ ! -e "${required_absent_companion}" && ! -L "${required_absent_companion}" ]] \
          || die_remote "database companion env still exists: ${target}"
      fi
      references="$(runtime_configuration_references "${target}")"
      [[ -z "${references}" ]] || die_remote "database still has configuration references: ${target}"
      [[ "$(process_environment_reference_count "${target}")" == "0" ]] \
        || die_remote "database still has a running process reference: ${target}"
      sudo -n -u postgres psql -d postgres --set=ON_ERROR_STOP=1 --set=target="${target}" \
        --command="REVOKE CONNECT ON DATABASE :\"target\" FROM PUBLIC" >/dev/null
      sudo -n -u postgres psql -d postgres --set=ON_ERROR_STOP=1 --set=target="${target}" \
        --command="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid()" >/dev/null
      drop_statement="$(sudo -n -u postgres psql -d postgres -At --set=ON_ERROR_STOP=1 --set=target="${target}" \
        --command="SELECT format('DROP DATABASE %I', :'target')")"
      [[ "${drop_statement}" == DROP\ DATABASE\ * ]] || die_remote "database drop statement was not generated safely"
      sudo -n -u postgres psql -d postgres --set=ON_ERROR_STOP=1 --command="${drop_statement}" >/dev/null
      record_result "${resource_id}" "${kind}" "${target}" "deleted"
      ;;
    directory)
      if [[ ! -e "${target}" ]]; then
        record_result "${resource_id}" "${kind}" "${target}" "skipped"
        continue
      fi
      [[ -d "${target}" && ! -L "${target}" ]] || die_remote "directory target changed type: ${target}"
      [[ "$(readlink -f -- "${target}")" == "${target}" ]] || die_remote "directory realpath changed: ${target}"
      references="$(runtime_configuration_references "${target}")"
      [[ -z "${references}" ]] || die_remote "directory still has configuration references: ${target}"
      [[ "$(tree_sha256 "${target}")" == "${content_sha}" ]] || die_remote "directory identity changed: ${target}"
      mv -- "${target}" "${quarantine_target}"
      record_result "${resource_id}" "${kind}" "${target}" "deleted"
      ;;
    *)
      die_remote "unsupported resource kind"
      ;;
  esac
done < "${RUN_ROOT}/retirement-plan.tsv"
fi

nginx -t
if [[ "${RETIREMENT_SCOPE}" != "capacity_pre_cleanup" ]]; then
  systemctl daemon-reload
  systemctl is-active --quiet chickenbro-api.service || die_remote "protected production API stopped during retirement"
  systemctl is-active --quiet chickenbro-worker.service || die_remote "protected production worker stopped during retirement"
  [[ "$(systemctl show chickenbro-simc-runtime-update.service --property=LoadState --value)" == "loaded" ]] \
    || die_remote "protected SimulationCraft updater changed during retirement"
  [[ -x /opt/chickenbro/server/chickenbro_simc_runtime_update.sh ]] \
    || die_remote "protected SimulationCraft updater script changed during retirement"
  [[ -e /opt/wow-simc/current ]] || die_remote "protected SimC runtime changed during retirement"
fi
protected_database_exists="$(sudo -n -u postgres psql -d postgres -At --command="SELECT count(*) FROM pg_database WHERE datname = 'chickenbro_prod'")"
[[ "${protected_database_exists}" == "1" ]] || die_remote "protected production database changed during retirement"
RESULTS_TMP="${RESULTS_TMP}" MANIFEST_SHA="${REVIEWED_REMOTE_MANIFEST_SHA}" RECOVERY_SHA="${REVIEWED_REMOTE_RECOVERY_SHA}" \
  python3 - <<'PY' | tee "${RUN_ROOT}/result.json"
import json
import os
from datetime import datetime, timezone
from pathlib import Path

results = [json.loads(line) for line in Path(os.environ["RESULTS_TMP"]).read_text(encoding="utf-8").splitlines()]
print(json.dumps({
    "status": "applied",
    "manifestSha256": os.environ["MANIFEST_SHA"],
    "whitelistRecoveryManifestSha256": os.environ["RECOVERY_SHA"],
    "completedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "results": results,
}, separators=(",", ":")))
PY
REMOTE
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --manifest)
        [[ $# -ge 2 ]] || die "--manifest requires a value"
        MANIFEST_FILE="$2"
        shift 2
        ;;
      --dry-run)
        MODE="dry-run"
        shift
        ;;
      --apply)
        MODE="apply"
        shift
        ;;
      --capacity-pre-cleanup)
        SCOPE="capacity_pre_cleanup"
        shift
        ;;
      --manifest-sha)
        [[ $# -ge 2 ]] || die "--manifest-sha requires a value"
        REVIEWED_MANIFEST_SHA="$2"
        shift 2
        ;;
      --recovery-manifest-sha)
        [[ $# -ge 2 ]] || die "--recovery-manifest-sha requires a value"
        REVIEWED_RECOVERY_MANIFEST_SHA="$2"
        shift 2
        ;;
      --help|-h)
        usage
        return 0
        ;;
      *)
        usage
        die "unknown argument: $1"
        ;;
    esac
  done

  [[ -n "${MANIFEST_FILE}" && -f "${MANIFEST_FILE}" ]] || die "--manifest must name an existing JSON file"
  validate_manifest_schema
  validate_manifest_targets

  if [[ "${MODE}" == "dry-run" ]]; then
    print_dry_run
    return 0
  fi

  if [[ -z "${REVIEWED_MANIFEST_SHA}" || -z "${REVIEWED_RECOVERY_MANIFEST_SHA}" ]]; then
    die "--apply requires --manifest-sha and --recovery-manifest-sha"
  fi
  [[ "${REVIEWED_MANIFEST_SHA}" =~ ^[0-9a-f]{64}$ \
    && "${REVIEWED_RECOVERY_MANIFEST_SHA}" =~ ^[0-9a-f]{64}$ ]] \
    || die "--apply requires valid SHA-256 identities"
  [[ "${REMOTE_HOST}" =~ ^[A-Za-z0-9.-]+$ && "${REMOTE_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]] \
    || die "invalid remote host or user"
  [[ "${REMOTE_RECOVERY_MANIFEST}" =~ ^/[A-Za-z0-9_./-]+$ \
    && "${REMOTE_RECOVERY_MANIFEST}" != *".."* ]] \
    || die "invalid remote recovery manifest path"
  [[ "$(sha256_file "${MANIFEST_FILE}")" == "${REVIEWED_MANIFEST_SHA}" ]] \
    || die "reviewed manifest SHA-256 mismatch"
  assert_apply_ready
  run_remote_apply
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi

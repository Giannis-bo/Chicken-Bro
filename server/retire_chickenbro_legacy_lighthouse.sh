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
                or not isinstance(observed.get("exactRows"), int)
                or isinstance(observed.get("exactRows"), bool)
                or observed["exactRows"] < 0
                or not isinstance(observed.get("owner"), str)
                or re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", observed["owner"]) is None
                or not isinstance(observed.get("allowsConnections"), bool)
            ):
                raise SystemExit(f"ready capacity database {resource_id} lacks exact table/row counts")
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

  ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" sudo -n env \
    "MANIFEST_BASE64=${manifest_base64}" \
    "REVIEWED_REMOTE_MANIFEST_SHA=${REVIEWED_MANIFEST_SHA}" \
    "REVIEWED_REMOTE_RECOVERY_SHA=${REVIEWED_RECOVERY_MANIFEST_SHA}" \
    "REMOTE_RECOVERY_MANIFEST_PATH=${REMOTE_RECOVERY_MANIFEST}" \
    "RETIREMENT_SCOPE=${SCOPE}" \
    bash -s <<'REMOTE'
set -Eeuo pipefail

die_remote() {
  printf 'retire_chickenbro_legacy_remote: %s\n' "$*" >&2
  exit 1
}

require_remote_root() {
  [[ "${EUID}" -eq 0 ]] || die_remote "explicit root context is required"
}

require_remote_root

MANIFEST_TMP=""
RESULTS_TMP=""
cleanup_remote_tmp() {
  [[ -z "${MANIFEST_TMP}" ]] || rm -f -- "${MANIFEST_TMP}"
  [[ -z "${RESULTS_TMP}" ]] || rm -f -- "${RESULTS_TMP}"
}
trap cleanup_remote_tmp EXIT
for command_name in awk base64 cat curl find grep install lsof mktemp mv nginx psql python3 readlink realpath rm sed sha256sum sort sudo systemctl tee; do
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
RUN_ROOT_EXISTED=false
if [[ -e "${RUN_ROOT}" ]]; then
  [[ -d "${RUN_ROOT}" && ! -L "${RUN_ROOT}" && "$(realpath -e -- "${RUN_ROOT}")" == "${RUN_ROOT}" ]] \
    || die_remote "existing retirement run root changed type or realpath"
  RUN_ROOT="${RUN_ROOT}" python3 - <<'PY'
import os
import stat
from pathlib import Path

metadata = Path(os.environ["RUN_ROOT"]).stat()
if metadata.st_uid != 0 or metadata.st_gid != 0 or stat.S_IMODE(metadata.st_mode) != 0o700:
    raise SystemExit("existing retirement run root ownership or mode changed")
PY
  RUN_ROOT_EXISTED=true
else
  install -d -o root -g root -m 0700 -- "${RUN_ROOT}"
fi
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

CAPACITY_PAIRS="${RUN_ROOT}/capacity-pairs.tsv"
CONFIGURATION_SCAN_ROOTS="${RUN_ROOT}/configuration-scan-roots.txt"
REFERENCE_EVIDENCE_EXCLUSIONS="${RUN_ROOT}/reference-evidence-exclusions.txt"
if [[ "${RUN_ROOT_EXISTED}" == "false" ]]; then
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
        str(observed["tableCount"]), str(observed["exactRows"]),
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
fi

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

open_handle_probe() {
  local target="$1"
  local output_file error_file probe_status
  output_file="$(mktemp)" || { printf '%s\n' 'error'; return 1; }
  error_file="$(mktemp)" || { rm -f -- "${output_file}"; printf '%s\n' 'error'; return 1; }
  probe_status=0
  lsof -t -- "${target}" >"${output_file}" 2>"${error_file}" || probe_status=$?
  if [[ "${probe_status}" -eq 0 && -s "${output_file}" && ! -s "${error_file}" ]]; then
    printf '%s\n' 'matched'
    cat -- "${output_file}"
    rm -f -- "${output_file}" "${error_file}"
    return 0
  fi
  if [[ "${probe_status}" -eq 1 && ! -s "${output_file}" && ! -s "${error_file}" ]]; then
    printf '%s\n' 'clear'
    rm -f -- "${output_file}" "${error_file}"
    return 0
  fi
  rm -f -- "${output_file}" "${error_file}"
  printf '%s\n' 'error'
  return 1
}

process_environment_reference_probe() {
  local needle="$1"
  local process_root="${PROCESS_ENVIRON_ROOT:-/proc}"
  local count=0 process_env error_file grep_status nullglob_was_set=false
  local -a process_environments=()
  [[ -d "${process_root}" && -r "${process_root}" ]] \
    || { printf '%s\n' 'error'; return 1; }
  if shopt -q nullglob; then
    nullglob_was_set=true
  else
    shopt -s nullglob
  fi
  process_environments=("${process_root}"/[0-9]*/environ)
  [[ "${nullglob_was_set}" == "true" ]] || shopt -u nullglob
  error_file="$(mktemp)" || { printf '%s\n' 'error'; return 1; }
  for process_env in "${process_environments[@]}"; do
    : > "${error_file}"
    grep_status=0
    grep -Fq -- "${needle}" "${process_env}" 2>"${error_file}" || grep_status=$?
    if [[ "${grep_status}" -eq 0 ]]; then
      [[ ! -s "${error_file}" ]] \
        || { rm -f -- "${error_file}"; printf '%s\n' 'error'; return 1; }
      count=$(( count + 1 ))
    elif [[ "${grep_status}" -eq 1 && ! -s "${error_file}" ]]; then
      :
    elif [[ ! -e "${process_env}" && ! -L "${process_env}" ]]; then
      # A process may exit between the /proc snapshot and the read.
      :
    else
      rm -f -- "${error_file}"
      printf '%s\n' 'error'
      return 1
    fi
  done
  rm -f -- "${error_file}"
  if [[ "${count}" -eq 0 ]]; then
    printf 'clear\t0\n'
  else
    printf 'matched\t%s\n' "${count}"
  fi
}

runtime_configuration_reference_probe() {
  local needle="$1"
  local root candidate find_output find_error matches_file grep_error
  local find_status grep_status matched=false
  [[ -f "${CONFIGURATION_SCAN_ROOTS}" && ! -L "${CONFIGURATION_SCAN_ROOTS}" \
    && -f "${REFERENCE_EVIDENCE_EXCLUSIONS}" && ! -L "${REFERENCE_EVIDENCE_EXCLUSIONS}" ]] \
    || { printf '%s\n' 'error'; return 1; }
  find_output="$(mktemp)" || { printf '%s\n' 'error'; return 1; }
  find_error="$(mktemp)" || { rm -f -- "${find_output}"; printf '%s\n' 'error'; return 1; }
  matches_file="$(mktemp)" || { rm -f -- "${find_output}" "${find_error}"; printf '%s\n' 'error'; return 1; }
  grep_error="$(mktemp)" || { rm -f -- "${find_output}" "${find_error}" "${matches_file}"; printf '%s\n' 'error'; return 1; }
  while IFS= read -r root; do
    [[ -n "${root}" ]] \
      || { rm -f -- "${find_output}" "${find_error}" "${matches_file}" "${grep_error}"; printf '%s\n' 'error'; return 1; }
    if [[ ! -e "${root}" && ! -L "${root}" ]]; then
      continue
    fi
    [[ -d "${root}" && ! -L "${root}" && -r "${root}" ]] \
      || { rm -f -- "${find_output}" "${find_error}" "${matches_file}" "${grep_error}"; printf '%s\n' 'error'; return 1; }
    : > "${find_output}"
    : > "${find_error}"
    find_status=0
    find "${root}" -type f -print0 >"${find_output}" 2>"${find_error}" || find_status=$?
    if [[ "${find_status}" -ne 0 || -s "${find_error}" ]]; then
      rm -f -- "${find_output}" "${find_error}" "${matches_file}" "${grep_error}"
      printf '%s\n' 'error'
      return 1
    fi
    while IFS= read -r -d '' candidate; do
      : > "${grep_error}"
      grep_status=0
      grep -Fxq -- "${candidate}" "${REFERENCE_EVIDENCE_EXCLUSIONS}" 2>"${grep_error}" || grep_status=$?
      if [[ "${grep_status}" -eq 0 && ! -s "${grep_error}" ]]; then
        continue
      fi
      if [[ "${grep_status}" -ne 1 || -s "${grep_error}" ]]; then
        rm -f -- "${find_output}" "${find_error}" "${matches_file}" "${grep_error}"
        printf '%s\n' 'error'
        return 1
      fi
      : > "${grep_error}"
      grep_status=0
      grep -Fq -- "${needle}" "${candidate}" 2>"${grep_error}" || grep_status=$?
      if [[ "${grep_status}" -eq 0 && ! -s "${grep_error}" ]]; then
        printf '%s\n' "${candidate}" >> "${matches_file}"
        matched=true
      elif [[ "${grep_status}" -ne 1 || -s "${grep_error}" ]]; then
        rm -f -- "${find_output}" "${find_error}" "${matches_file}" "${grep_error}"
        printf '%s\n' 'error'
        return 1
      fi
    done < "${find_output}"
  done < "${CONFIGURATION_SCAN_ROOTS}"
  if [[ "${matched}" == "true" ]]; then
    printf '%s\n' 'matched'
    LC_ALL=C sort -u -- "${matches_file}"
  else
    printf '%s\n' 'clear'
  fi
  rm -f -- "${find_output}" "${find_error}" "${matches_file}" "${grep_error}"
}

validate_capacity_env_file() {
  local target="$1"
  local expected_sha="$2"
  local target_real open_handle_state reference_state
  [[ "${target%/*}" == "/etc" ]] || die_remote "capacity env is outside exact /etc root: ${target}"
  [[ -f "${target}" && ! -L "${target}" ]] \
    || die_remote "capacity env must be a regular non-symlink file: ${target}"
  target_real="$(realpath -e -- "${target}")"
  [[ "${target_real}" == "${target}" ]] || die_remote "capacity env realpath changed: ${target}"
  [[ "$(sha256sum -- "${target}" | awk '{print $1}')" == "${expected_sha}" ]] \
    || die_remote "capacity env identity changed: ${target}"
  open_handle_state="$(open_handle_probe "${target}")" \
    || die_remote "capacity env open-handle probe failed: ${target}"
  [[ "${open_handle_state}" == "clear" ]] \
    || die_remote "capacity env has an open handle: ${target}"
  reference_state="$(runtime_configuration_reference_probe "${target}")" \
    || die_remote "capacity env configuration-reference probe failed: ${target}"
  [[ "${reference_state}" == "clear" ]] \
    || die_remote "capacity env still has configuration references: ${target}"
}

fresh_database_counts() {
  local target="$1"
  local table_count exact_count_query exact_row_count
  table_count="$(sudo -n -u postgres psql --no-psqlrc --dbname="${target}" --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --command="SELECT count(*)::bigint FROM pg_stat_user_tables")" \
    || return 1
  exact_count_query="$(sudo -n -u postgres psql --no-psqlrc --dbname="${target}" --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --command="SELECT 'SELECT ' || COALESCE(string_agg(format('(SELECT count(*)::bigint FROM %I.%I)', schemaname, relname), ' + ' ORDER BY schemaname, relname), '0') FROM pg_stat_user_tables")" \
    || return 1
  [[ "${exact_count_query}" == SELECT\ * ]] || return 1
  exact_row_count="$(sudo -n -u postgres psql --no-psqlrc --dbname="${target}" --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --command="${exact_count_query}")" \
    || return 1
  [[ "${table_count}" =~ ^[0-9]+$ && "${exact_row_count}" =~ ^[0-9]+$ ]] || return 1
  printf '%s\t%s\n' "${table_count}" "${exact_row_count}"
}

probe_capacity_database_existence() {
  local target="$1"
  local probe_output
  if ! probe_output="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --set=target="${target}" 2>/dev/null <<'SQL'
SELECT count(*) FROM pg_database WHERE datname = :'target';
SQL
)"; then
    printf '%s\n' 'unknown'
    return 1
  fi
  case "${probe_output}" in
    1)
      printf '%s\n' 'present'
      ;;
    0)
      printf '%s\n' 'absent'
      ;;
    *)
      printf '%s\n' 'unknown'
      return 1
      ;;
  esac
}

capacity_preflight_pair() {
  local db_id="$1" database="$2" env_id="$3" env_path="$4" env_sha="$5"
  local expected_size="$6" expected_table_count="$7" expected_exact_row_count="$8" expected_owner="$9" expected_allows="${10}"
  local exists connections current_size current_counts current_table_count current_row_count current_identity current_owner current_allows
  local reference_state process_state
  validate_capacity_env_file "${env_path}" "${env_sha}"
  if ! exists="$(probe_capacity_database_existence "${database}")"; then
    die_remote "capacity database existence is unknown: ${database}"
  fi
  [[ "${exists}" == "present" ]] || die_remote "capacity database is missing: ${database}"
  connections="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --set=target="${database}" <<'SQL'
SELECT count(*) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid();
SQL
)"
  [[ "${connections}" == "0" ]] || die_remote "capacity database gained active connections: ${database}"
  current_size="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --set=target="${database}" <<'SQL'
SELECT pg_database_size(:'target');
SQL
)"
  [[ "${current_size}" == "${expected_size}" ]] || die_remote "capacity database size identity changed: ${database}"
  current_counts="$(fresh_database_counts "${database}" | tr -d ' ')" \
    || die_remote "capacity database exact table/row count failed: ${database}"
  IFS=$'\t' read -r current_table_count current_row_count <<< "${current_counts}"
  [[ "${current_table_count}" == "${expected_table_count}" && "${current_row_count}" == "${expected_exact_row_count}" ]] \
    || die_remote "capacity database exact table/row counts changed: ${database}"
  current_identity="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --field-separator=$'\t' --set=target="${database}" <<'SQL'
SELECT pg_get_userbyid(datdba), CASE WHEN datallowconn THEN 'true' ELSE 'false' END
FROM pg_database
WHERE datname = :'target';
SQL
)"
  IFS=$'\t' read -r current_owner current_allows <<< "${current_identity}"
  [[ "${current_owner}" == "${expected_owner}" && "${current_allows}" == "${expected_allows}" ]] \
    || die_remote "capacity database owner/connection identity changed: ${database}"
  reference_state="$(runtime_configuration_reference_probe "${database}")" \
    || die_remote "capacity database configuration-reference probe failed: ${database}"
  [[ "${reference_state}" == $'matched\n'"${env_path}" ]] \
    || die_remote "database configuration references differ from exact companion: ${database}"
  process_state="$(process_environment_reference_probe "${database}")" \
    || die_remote "capacity database process-reference probe failed: ${database}"
  [[ "${process_state}" == $'clear\t0' ]] \
    || die_remote "capacity database still has a running process reference: ${database}"
}

capacity_preflight_all_pairs() {
  local db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows
  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows; do
    capacity_preflight_pair "${db_id}" "${database}" "${env_id}" "${env_path}" "${env_sha}" \
      "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
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
                "exactRows": int(os.environ["JOURNAL_ROW_COUNT"]),
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
expected_before = {
    "database": {
        "exists": True,
        "sizeBytes": int(os.environ["JOURNAL_SIZE"]),
        "tableCount": int(os.environ["JOURNAL_TABLE_COUNT"]),
        "exactRows": int(os.environ["JOURNAL_ROW_COUNT"]),
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
}
if (
    payload.get("schemaVersion") != "chickenbro-capacity-pair-journal-v1"
    or payload.get("database") != os.environ["JOURNAL_DATABASE"]
    or payload.get("envFile") != os.environ["JOURNAL_ENV_PATH"]
    or payload.get("recoveryManifestSha256") != os.environ["JOURNAL_RECOVERY_SHA"]
    or payload.get("before") != expected_before
    or not isinstance(payload.get("events"), list)
):
    raise SystemExit("capacity pair journal identity changed")
payload["events"].append({"status": os.environ["JOURNAL_STATUS"], "at": now})
payload["latestStatus"] = os.environ["JOURNAL_STATUS"]
payload["updatedAt"] = now
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

capacity_journal_intent_stage() {
  local journal_path="$1" database="$2" env_path="$3" env_sha="$4" size="$5"
  local table_count="$6" row_count="$7" owner="$8" allows="$9"
  JOURNAL_PATH="${journal_path}" JOURNAL_DATABASE="${database}" JOURNAL_ENV_PATH="${env_path}" \
  JOURNAL_ENV_SHA="${env_sha}" JOURNAL_SIZE="${size}" JOURNAL_TABLE_COUNT="${table_count}" \
  JOURNAL_ROW_COUNT="${row_count}" JOURNAL_OWNER="${owner}" JOURNAL_ALLOWS="${allows}" \
  JOURNAL_RECOVERY_SHA="${REVIEWED_REMOTE_RECOVERY_SHA}" python3 - <<'PY'
import json
import os
from pathlib import Path

journal = Path(os.environ["JOURNAL_PATH"])
if not journal.exists() and not journal.is_symlink():
    print("none")
    raise SystemExit(0)
if journal.is_symlink() or not journal.is_file():
    raise SystemExit("capacity pair journal path changed type")
payload = json.loads(journal.read_text(encoding="utf-8"))
expected_before = {
    "database": {
        "exists": True,
        "sizeBytes": int(os.environ["JOURNAL_SIZE"]),
        "tableCount": int(os.environ["JOURNAL_TABLE_COUNT"]),
        "exactRows": int(os.environ["JOURNAL_ROW_COUNT"]),
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
}
events = payload.get("events")
if (
    payload.get("schemaVersion") != "chickenbro-capacity-pair-journal-v1"
    or payload.get("database") != os.environ["JOURNAL_DATABASE"]
    or payload.get("envFile") != os.environ["JOURNAL_ENV_PATH"]
    or payload.get("recoveryManifestSha256") != os.environ["JOURNAL_RECOVERY_SHA"]
    or payload.get("before") != expected_before
    or not isinstance(events, list)
    or any(not isinstance(event, dict) or not isinstance(event.get("status"), str) for event in events)
):
    raise SystemExit("capacity pair journal identity changed")
statuses = [event["status"] for event in events]
latest = payload.get("latestStatus")
if latest in {"reconciled_recovered", "failed_recovered"}:
    print("none")
elif latest in {"completed", "reconciled_completed", "failed_after_drop"} or "drop_intent" in statuses:
    print("drop")
elif "env_move_intent" in statuses or "env_quarantined" in statuses:
    print("env_move")
elif "fence_intent" in statuses or "fenced_verified" in statuses:
    print("fence")
else:
    print("none")
PY
}

capacity_exact_file_state() {
  local target="$1" expected_sha="$2" target_real
  if [[ ! -e "${target}" && ! -L "${target}" ]]; then
    printf '%s\n' 'absent'
    return 0
  fi
  if [[ ! -f "${target}" || -L "${target}" ]]; then
    printf '%s\n' 'error'
    return 1
  fi
  target_real="$(realpath -e -- "${target}")" \
    || { printf '%s\n' 'error'; return 1; }
  if [[ "${target_real}" != "${target}" \
    || "$(sha256sum -- "${target}" | awk '{print $1}')" != "${expected_sha}" ]]; then
    printf '%s\n' 'error'
    return 1
  fi
  printf '%s\n' 'exact'
}

probe_capacity_database_identity() {
  local target="$1" identity_output
  identity_output="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --field-separator=$'\t' --set=ON_ERROR_STOP=1 --set=target="${target}" 2>/dev/null <<'SQL'
SELECT pg_get_userbyid(datdba), CASE WHEN datallowconn THEN 'true' ELSE 'false' END,
  pg_database_size(datname)
FROM pg_database
WHERE datname = :'target';
SQL
)" \
    || return 1
  [[ "${identity_output}" =~ ^[^$'\t']+$'\t'(true|false)$'\t'[0-9]+$ ]] || return 1
  printf '%s\n' "${identity_output}"
}

restore_capacity_database_allow_connections() {
  local target="$1" allows="$2" restore_statement
  [[ "${allows}" == "true" || "${allows}" == "false" ]] || return 1
  restore_statement="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --set=target="${target}" --set=allows="${allows}" <<'SQL'
SELECT format('ALTER DATABASE %I WITH ALLOW_CONNECTIONS %s', :'target', :'allows');
SQL
)" \
    || return 1
  [[ "${restore_statement}" == ALTER\ DATABASE\ *\ WITH\ ALLOW_CONNECTIONS\ * ]] || return 1
  sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
    --command="${restore_statement}" >/dev/null
}

reconcile_capacity_pair_actual() {
  local db_id="$1" database="$2" env_id="$3" env_path="$4" env_sha="$5"
  local expected_size="$6" expected_table_count="$7" expected_exact_row_count="$8" expected_owner="$9" expected_allows="${10}"
  local quarantine_path="${RUN_ROOT}/${env_id}" journal_path="${RUN_ROOT}/pair-journals/${db_id}.json"
  local stage existence original_state quarantine_state identity current_owner current_allows current_size
  local current_counts current_table_count current_exact_row_count final_identity final_owner final_allows final_size
  stage="$(capacity_journal_intent_stage "${journal_path}" "${database}" "${env_path}" "${env_sha}" \
    "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}")" \
    || return 1
  existence="$(probe_capacity_database_existence "${database}")" || return 1
  original_state="$(capacity_exact_file_state "${env_path}" "${env_sha}")" || return 1
  quarantine_state="$(capacity_exact_file_state "${quarantine_path}" "${env_sha}")" || return 1

  if [[ "${existence}" == "present" ]]; then
    identity="$(probe_capacity_database_identity "${database}")" || return 1
    IFS=$'\t' read -r current_owner current_allows current_size <<< "${identity}"
    [[ "${current_owner}" == "${expected_owner}" && "${current_size}" == "${expected_size}" ]] || return 1
    if [[ "${original_state}:${quarantine_state}" == "absent:exact" ]]; then
      [[ "${stage}" == "env_move" || "${stage}" == "drop" ]] || return 1
      write_capacity_pair_journal "${journal_path}" "reconcile_env_restore_intent" "${database}" "${env_path}" \
        "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
      mv -- "${quarantine_path}" "${env_path}"
    elif [[ "${original_state}:${quarantine_state}" != "exact:absent" ]]; then
      return 1
    fi
    if [[ "${current_allows}" != "${expected_allows}" ]]; then
      [[ "${stage}" == "fence" || "${stage}" == "env_move" || "${stage}" == "drop" ]] || return 1
      write_capacity_pair_journal "${journal_path}" "reconcile_allow_restore_intent" "${database}" "${env_path}" \
        "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
      restore_capacity_database_allow_connections "${database}" "${expected_allows}" || return 1
    fi
    original_state="$(capacity_exact_file_state "${env_path}" "${env_sha}")" || return 1
    quarantine_state="$(capacity_exact_file_state "${quarantine_path}" "${env_sha}")" || return 1
    final_identity="$(probe_capacity_database_identity "${database}")" || return 1
    IFS=$'\t' read -r final_owner final_allows final_size <<< "${final_identity}"
    [[ "${original_state}:${quarantine_state}" == "exact:absent" \
      && "${final_owner}" == "${expected_owner}" && "${final_allows}" == "${expected_allows}" \
      && "${final_size}" == "${expected_size}" ]] || return 1
    current_counts="$(fresh_database_counts "${database}" | tr -d ' ')" || return 1
    IFS=$'\t' read -r current_table_count current_exact_row_count <<< "${current_counts}"
    [[ "${current_table_count}" == "${expected_table_count}" \
      && "${current_exact_row_count}" == "${expected_exact_row_count}" ]] || return 1
    write_capacity_pair_journal "${journal_path}" "reconciled_recovered" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}" \
      true true
    return 0
  fi
  if [[ "${existence}" == "absent" ]]; then
    [[ "${stage}" == "drop" && "${original_state}:${quarantine_state}" == "absent:exact" ]] || return 1
    write_capacity_pair_journal "${journal_path}" "reconciled_completed" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}" \
      false false
    return 0
  fi
  return 1
}

capacity_pair_failure() {
  local exit_code="$1"
  trap - ERR
  set +e
  reconcile_capacity_pair_actual "${PAIR_DB_ID}" "${PAIR_DATABASE}" "${PAIR_ENV_ID}" "${PAIR_ENV_PATH}" "${PAIR_ENV_SHA}" \
    "${PAIR_SIZE}" "${PAIR_TABLE_COUNT}" "${PAIR_EXACT_ROW_COUNT}" "${PAIR_OWNER}" "${PAIR_EXPECTED_ALLOWS}" \
    || write_capacity_pair_journal "${PAIR_JOURNAL}" "failed_recovery_incomplete" "${PAIR_DATABASE}" "${PAIR_ENV_PATH}" \
      "${PAIR_ENV_SHA}" "${PAIR_SIZE}" "${PAIR_TABLE_COUNT}" "${PAIR_EXACT_ROW_COUNT}" "${PAIR_OWNER}" "${PAIR_EXPECTED_ALLOWS}" \
      || true
  exit "${exit_code}"
}

capacity_pair_abort() {
  printf 'retire_chickenbro_legacy_remote: %s\n' "$*" >&2
  return 1
}

fence_and_verify_capacity_database() {
  local database="$1" expected_size="$2" expected_table_count="$3" expected_exact_row_count="$4" expected_owner="$5"
  local verification_output
  verification_output="$(sudo -n -u postgres psql --no-psqlrc --dbname="${database}" --quiet --tuples-only --no-align \
    --set=ON_ERROR_STOP=1 --set=target="${database}" --set=expected_size="${expected_size}" \
    --set=expected_table_count="${expected_table_count}" --set=expected_exact_row_count="${expected_exact_row_count}" \
    --set=expected_owner="${expected_owner}" <<'SQL'
SELECT format('ALTER DATABASE %I WITH ALLOW_CONNECTIONS false', current_database()) \gexec
SELECT 1 / CASE WHEN current_database() = :'target' THEN 1 ELSE 0 END;
SELECT 1 / CASE WHEN (
  SELECT pg_get_userbyid(datdba) = :'expected_owner' AND datallowconn = false
  FROM pg_database
  WHERE datname = current_database()
) THEN 1 ELSE 0 END;
SELECT 1 / CASE WHEN pg_database_size(current_database()) = :'expected_size'::bigint THEN 1 ELSE 0 END;
SELECT 1 / CASE WHEN (SELECT count(*)::bigint FROM pg_stat_user_tables) = :'expected_table_count'::bigint THEN 1 ELSE 0 END;
SELECT 1 / CASE WHEN (
  SELECT count(*)::bigint
  FROM pg_stat_activity
  WHERE datname = current_database() AND pid <> pg_backend_pid()
) = 0 THEN 1 ELSE 0 END;
SELECT 'SELECT 1 / CASE WHEN (' ||
  COALESCE(string_agg(format('(SELECT count(*)::bigint FROM %I.%I)', schemaname, relname), ' + ' ORDER BY schemaname, relname), '0') ||
  ') = ' || quote_literal(:'expected_exact_row_count') || '::bigint THEN 1 ELSE 0 END;'
FROM pg_stat_user_tables \gexec
SELECT 'capacity_fenced_verified';
SQL
)" || return 1
  [[ "${verification_output}" == *"capacity_fenced_verified" ]] || return 1
}

capacity_apply_pair() {
    local db_id="$1" database="$2" env_id="$3" env_path="$4" env_sha="$5"
    local expected_size="$6" expected_table_count="$7" expected_exact_row_count="$8" expected_owner="$9" expected_allows="${10}"
    local drop_statement post_drop_state reference_state process_state open_handle_state
    PAIR_DB_ID="${db_id}"
    PAIR_DATABASE="${database}"
    PAIR_ENV_ID="${env_id}"
    PAIR_ENV_PATH="${env_path}"
    PAIR_ENV_SHA="${env_sha}"
    PAIR_SIZE="${expected_size}"
    PAIR_TABLE_COUNT="${expected_table_count}"
    PAIR_EXACT_ROW_COUNT="${expected_exact_row_count}"
    PAIR_OWNER="${expected_owner}"
    PAIR_EXPECTED_ALLOWS="${expected_allows}"
    PAIR_QUARANTINE_TARGET="${RUN_ROOT}/${env_id}"
    PAIR_JOURNAL="${RUN_ROOT}/pair-journals/${db_id}.json"
    trap 'capacity_pair_failure "$?"' ERR

    # Recheck this exact pair after earlier pairs completed and immediately before its first mutation.
    capacity_preflight_pair "${db_id}" "${database}" "${env_id}" "${env_path}" "${env_sha}" \
      "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "fence_intent" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
    fence_and_verify_capacity_database "${database}" "${expected_size}" "${expected_table_count}" \
      "${expected_exact_row_count}" "${expected_owner}"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "fenced_verified" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "env_move_intent" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
    mv -- "${env_path}" "${PAIR_QUARANTINE_TARGET}"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "env_quarantined" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
    if [[ -e "${env_path}" || -L "${env_path}" ]]; then
      capacity_pair_abort "database companion env still exists: ${database}"
    fi
    open_handle_state="$(open_handle_probe "${PAIR_QUARANTINE_TARGET}")" \
      || capacity_pair_abort "database companion open-handle probe failed after quarantine: ${database}"
    [[ "${open_handle_state}" == "clear" ]] \
      || capacity_pair_abort "database companion still has an open handle after quarantine: ${database}"
    reference_state="$(runtime_configuration_reference_probe "${database}")" \
      || capacity_pair_abort "database configuration-reference probe failed after companion quarantine: ${database}"
    [[ "${reference_state}" == "clear" ]] \
      || capacity_pair_abort "database still has configuration references after companion quarantine: ${database}"
    process_state="$(process_environment_reference_probe "${database}")" \
      || capacity_pair_abort "database process-reference probe failed after companion quarantine: ${database}"
    [[ "${process_state}" == $'clear\t0' ]] \
      || capacity_pair_abort "database still has a running process reference after companion quarantine: ${database}"

    drop_statement="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
      --set=ON_ERROR_STOP=1 --set=target="${database}" <<'SQL'
SELECT format('DROP DATABASE %I', :'target');
SQL
)"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "drop_intent" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
    sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
      --command="${drop_statement}" >/dev/null
    if ! post_drop_state="$(probe_capacity_database_existence "${database}")"; then
      capacity_pair_abort "database existence is unknown after drop: ${database}"
    fi
    [[ "${post_drop_state}" == "absent" ]] \
      || capacity_pair_abort "database still exists after drop: ${database}"
    write_capacity_pair_journal "${PAIR_JOURNAL}" "completed" "${database}" "${env_path}" \
      "${env_sha}" "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}" \
      false false
    record_result "${env_id}" "file" "${env_path}" "deleted" \
      "{\"exists\":true,\"realpath\":\"${env_path}\",\"sha256\":\"${env_sha}\"}" '{"exists":false}'
    record_result "${db_id}" "postgres_database" "${database}" "deleted" \
      "{\"exists\":true,\"sizeBytes\":${expected_size},\"tableCount\":${expected_table_count},\"exactRows\":${expected_exact_row_count},\"owner\":\"${expected_owner}\"}" '{"exists":false}'
    trap - ERR
}

capacity_apply_pairs() {
  local db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows
  install -d -o root -g root -m 0700 -- "${RUN_ROOT}/pair-journals"
  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows; do
    write_capacity_pair_journal "${RUN_ROOT}/pair-journals/${db_id}.json" "preflight_complete" \
      "${database}" "${env_path}" "${env_sha}" "${expected_size}" "${expected_table_count}" \
      "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
  done < "${CAPACITY_PAIRS}"

  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows; do
    capacity_apply_pair "${db_id}" "${database}" "${env_id}" "${env_path}" "${env_sha}" \
      "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}"
  done < "${CAPACITY_PAIRS}"
}

validate_capacity_resume_artifacts() {
  RESUME_MANIFEST="${MANIFEST_TMP}" RESUME_PAIRS="${CAPACITY_PAIRS}" \
  RESUME_ROOTS="${CONFIGURATION_SCAN_ROOTS}" RESUME_EXCLUSIONS="${REFERENCE_EVIDENCE_EXCLUSIONS}" \
    python3 - <<'PY'
import json
import os
import stat
from pathlib import Path

manifest = json.loads(Path(os.environ["RESUME_MANIFEST"]).read_text(encoding="utf-8"))
capacity = manifest["capacityPreCleanup"]
resources = manifest["resources"]
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
        str(observed["tableCount"]), str(observed["exactRows"]),
        observed["owner"], "true" if observed["allowsConnections"] else "false",
    ]))
expected = {
    Path(os.environ["RESUME_PAIRS"]): "\n".join(rows) + "\n",
    Path(os.environ["RESUME_ROOTS"]): "\n".join(capacity["configurationScanRoots"]) + "\n",
    Path(os.environ["RESUME_EXCLUSIONS"]): "\n".join(capacity["referenceEvidenceExclusions"]) + "\n",
}
for path, content in expected.items():
    if path.is_symlink() or not path.is_file():
        raise SystemExit("capacity resume artifact is missing or changed type")
    metadata = path.stat()
    if metadata.st_uid != 0 or metadata.st_gid != 0 or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise SystemExit("capacity resume artifact ownership or mode changed")
    if path.read_text(encoding="utf-8") != content:
        raise SystemExit("capacity resume artifact does not match reviewed manifest")
PY
}

capacity_resume_existing_run() {
  local db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows
  [[ -f "${CAPACITY_PAIRS}" && ! -L "${CAPACITY_PAIRS}" ]] || return 1
  while IFS=$'\t' read -r db_id database env_id env_path env_sha expected_size expected_table_count expected_exact_row_count expected_owner expected_allows; do
    reconcile_capacity_pair_actual "${db_id}" "${database}" "${env_id}" "${env_path}" "${env_sha}" \
      "${expected_size}" "${expected_table_count}" "${expected_exact_row_count}" "${expected_owner}" "${expected_allows}" \
      || return 1
  done < "${CAPACITY_PAIRS}"
  printf '%s\n' 'existing capacity run reconciled; fresh live inventory and a fresh reviewed manifest are required before another apply' >&2
  return 75
}

if [[ "${RETIREMENT_SCOPE}" == "capacity_pre_cleanup" ]]; then
  if [[ "${RUN_ROOT_EXISTED}" == "true" ]]; then
    validate_capacity_resume_artifacts \
      || die_remote "existing capacity run artifacts failed reviewed-manifest validation"
    if [[ ! -e "${RUN_ROOT}/pair-journals" && ! -L "${RUN_ROOT}/pair-journals" ]]; then
      install -d -o root -g root -m 0700 -- "${RUN_ROOT}/pair-journals"
    fi
    [[ -d "${RUN_ROOT}/pair-journals" && ! -L "${RUN_ROOT}/pair-journals" ]] \
      || die_remote "existing capacity journal root changed type"
    capacity_resume_existing_run
  fi
  capacity_preflight_all_pairs
  capacity_apply_pairs
else
if [[ "${RUN_ROOT_EXISTED}" == "true" ]]; then
  die_remote "existing full-retirement run requires explicit recovery; refusing mutation replay"
fi
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
      open_handle_state="$(open_handle_probe "${target}")" \
        || die_remote "file open-handle probe failed: ${target}"
      [[ "${open_handle_state}" == "clear" ]] || die_remote "file has an open handle: ${target}"
      file_references="$(runtime_configuration_reference_probe "${target}")" \
        || die_remote "file configuration-reference probe failed: ${target}"
      [[ "${file_references}" == "clear" ]] || die_remote "file still has configuration references: ${target}"
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
      exists="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" <<'SQL'
SELECT count(*) FROM pg_database WHERE datname = :'target';
SQL
)"
      if [[ "${exists}" == "0" ]]; then
        record_result "${resource_id}" "${kind}" "${target}" "skipped"
        continue
      fi
      connections="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" <<'SQL'
SELECT count(*) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid();
SQL
)"
      [[ "${connections}" == "0" ]] || die_remote "database gained active connections: ${target}"
      current_size="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" <<'SQL'
SELECT pg_database_size(:'target');
SQL
)"
      [[ "${observed_size}" =~ ^[0-9]+$ && "${current_size}" == "${observed_size}" ]] \
        || die_remote "database size identity changed: ${target}"
      if [[ "${required_absent_companion}" != "-" ]]; then
        [[ ! -e "${required_absent_companion}" && ! -L "${required_absent_companion}" ]] \
          || die_remote "database companion env still exists: ${target}"
      fi
      references="$(runtime_configuration_reference_probe "${target}")" \
        || die_remote "database configuration-reference probe failed: ${target}"
      [[ "${references}" == "clear" ]] || die_remote "database still has configuration references: ${target}"
      process_references="$(process_environment_reference_probe "${target}")" \
        || die_remote "database process-reference probe failed: ${target}"
      [[ "${process_references}" == $'clear\t0' ]] \
        || die_remote "database still has a running process reference: ${target}"
      sudo -n -u postgres psql -d postgres --set=ON_ERROR_STOP=1 --set=target="${target}" \
        >/dev/null <<'SQL'
REVOKE CONNECT ON DATABASE :"target" FROM PUBLIC;
SQL
      fence_statement="$(sudo -n -u postgres psql --no-psqlrc --dbname=postgres --tuples-only --no-align \
        --set=ON_ERROR_STOP=1 --set=target="${target}" <<'SQL'
SELECT format('ALTER DATABASE %I WITH ALLOW_CONNECTIONS false', :'target');
SQL
)"
      sudo -n -u postgres psql --no-psqlrc --dbname=postgres --set=ON_ERROR_STOP=1 \
        --command="${fence_statement}" >/dev/null
      connections="$(sudo -n -u postgres psql -d postgres -At --set=target="${target}" <<'SQL'
SELECT count(*) FROM pg_stat_activity WHERE datname = :'target' AND pid <> pg_backend_pid();
SQL
)"
      [[ "${connections}" == "0" ]] || die_remote "database has active connections after fencing: ${target}"
      drop_statement="$(sudo -n -u postgres psql -d postgres -At --set=ON_ERROR_STOP=1 --set=target="${target}" <<'SQL'
SELECT format('DROP DATABASE %I', :'target');
SQL
)"
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
      references="$(runtime_configuration_reference_probe "${target}")" \
        || die_remote "directory configuration-reference probe failed: ${target}"
      [[ "${references}" == "clear" ]] || die_remote "directory still has configuration references: ${target}"
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

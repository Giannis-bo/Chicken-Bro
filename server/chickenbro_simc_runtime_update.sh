#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
TARGET_COMMIT=""
EXPECTED_CURRENT_COMMIT=""

SOURCE_REPOSITORY="simulationcraft/simc"
SOURCE_ARCHIVE_BASE="https://codeload.github.com/simulationcraft/simc/tar.gz"
SIMC_ROOT="/opt/wow-simc"
CURRENT_LINK="${SIMC_ROOT}/current"
COMPAT_COMMIT_FILE="${SIMC_ROOT}/.commit"
RELEASE_ROOT="${SIMC_ROOT}/releases"
WORK_ROOT="${SIMC_ROOT}/work"
LOCK_FILE="/run/lock/chickenbro-simc-runtime-update.lock"
MINIMUM_FREE_BYTES="12884901888"
MAX_SOURCE_ARCHIVE_BYTES="1073741824"
MAX_SOURCE_EXPANDED_BYTES="8589934592"
MAX_SOURCE_MEMBERS="500000"
BUILD_PARALLELISM="4"
WORK_DIR=""

die() {
  printf 'chickenbro_simc_runtime_update: %s\n' "$*" >&2
  exit 1
}

usage() {
  printf '%s\n' \
    'Usage:' \
    '  server/chickenbro_simc_runtime_update.sh [--dry-run] [--target-commit <40-char-sha>]' \
    '  server/chickenbro_simc_runtime_update.sh --apply --target-commit <40-char-sha> --expected-current-commit <40-char-sha>' >&2
}

validate_commit() {
  local name="$1"
  local value="$2"
  [[ "${value}" =~ ^[0-9a-f]{40}$ ]] || die "invalid ${name}: exact lowercase 40-character commit required"
}

sha256_file() {
  sha256sum -- "$1" | awk '{print $1}'
}

read_current_commit() {
  local candidate=""
  if [[ -f "${CURRENT_LINK}/.commit" ]]; then
    IFS= read -r candidate < "${CURRENT_LINK}/.commit" || true
  elif [[ -f "${COMPAT_COMMIT_FILE}" ]]; then
    IFS= read -r candidate < "${COMPAT_COMMIT_FILE}" || true
  fi
  if [[ "${candidate}" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s\n' "${candidate}"
  fi
}

emit_dry_run() {
  local current_commit="$1"
  python3 - "${current_commit}" "${TARGET_COMMIT}" <<'PY'
import json
import sys

current_commit, target_commit = sys.argv[1:]
update_required = None
if current_commit and target_commit:
    update_required = current_commit != target_commit
print(json.dumps({
    "mode": "dry-run",
    "mutationAuthorized": False,
    "runtimeRoot": "/opt/wow-simc",
    "currentLink": "/opt/wow-simc/current",
    "sourceRepository": "simulationcraft/simc",
    "currentCommit": current_commit or None,
    "targetCommit": target_commit or None,
    "updateRequired": update_required,
    "minimumFreeBytes": 12884901888,
}, sort_keys=True, separators=(",", ":")))
PY
}

remove_work_directory() {
  if [[ -z "${WORK_DIR}" ]]; then
    return 0
  fi
  case "${WORK_DIR}" in
    "${WORK_ROOT}/update-${TARGET_COMMIT}."*)
      ;;
    *)
      printf 'refusing to remove unexpected work directory: %s\n' "${WORK_DIR}" >&2
      return 1
      ;;
  esac
  if [[ -L "${WORK_DIR}" ]]; then
    printf 'refusing to remove symbolic-link work directory: %s\n' "${WORK_DIR}" >&2
    return 1
  fi
  if [[ ! -e "${WORK_DIR}" ]]; then
    WORK_DIR=""
    return 0
  fi
  if [[ ! -d "${WORK_DIR}" ]]; then
    printf 'refusing to remove non-directory work path: %s\n' "${WORK_DIR}" >&2
    return 1
  fi
  if ! rm -r -- "${WORK_DIR}"; then
    printf 'failed to remove exact work directory: %s\n' "${WORK_DIR}" >&2
    return 1
  fi
  WORK_DIR=""
}

cleanup_work() {
  local exit_code=$?
  trap - EXIT
  if ! remove_work_directory; then
    exit_code=1
  fi
  exit "${exit_code}"
}

smoke_simc_binary() {
  local binary="$1"
  [[ -x "${binary}" ]] || return 1
  timeout 60 "${binary}" "spell_query=spell.name=Bloodlust" >/dev/null
}

verify_release() {
  local release_dir="$1"
  local expected_commit="$2"
  local recorded_commit=""
  local recorded_binary_sha=""
  local recorded_source_identity=""
  local actual_binary_sha=""

  [[ -d "${release_dir}" && ! -L "${release_dir}" ]] || return 1
  [[ -x "${release_dir}/simc" && -f "${release_dir}/.commit" \
    && -f "${release_dir}/binary.sha256" && -f "${release_dir}/source-archive.sha256" ]] || return 1
  IFS= read -r recorded_commit < "${release_dir}/.commit" || return 1
  IFS= read -r recorded_binary_sha < "${release_dir}/binary.sha256" || return 1
  IFS= read -r recorded_source_identity < "${release_dir}/source-archive.sha256" || return 1
  [[ "${recorded_commit}" == "${expected_commit}" && "${recorded_binary_sha}" =~ ^[0-9a-f]{64}$ ]] || return 1
  [[ "${recorded_source_identity}" =~ ^[0-9a-f]{64}$ \
    || "${recorded_source_identity}" == "legacy-unavailable" ]] || return 1
  actual_binary_sha="$(sha256_file "${release_dir}/simc")"
  [[ "${actual_binary_sha}" == "${recorded_binary_sha}" ]]
}

write_release_metadata_once() {
  local target="$1"
  local value="$2"
  local existing=""
  local temporary="${target}.new-$$"

  if [[ -e "${target}" || -L "${target}" ]]; then
    [[ -f "${target}" && ! -L "${target}" ]] || die "release metadata target is not a regular file: ${target}"
    IFS= read -r existing < "${target}" || die "unable to read release metadata: ${target}"
    [[ "${existing}" == "${value}" ]] || die "release metadata already exists with a different identity: ${target}"
    return 0
  fi
  [[ ! -e "${temporary}" && ! -L "${temporary}" ]] || die "temporary release metadata already exists"
  printf '%s\n' "${value}" > "${temporary}"
  chmod 0644 "${temporary}"
  mv -Tf -- "${temporary}" "${target}"
}

adopt_current_release() {
  local current_commit="$1"
  local expected_release="${RELEASE_ROOT}/${current_commit}"
  local current_release=""
  local binary_sha=""
  local source_identity="legacy-unavailable"
  local legacy_archive="${SIMC_ROOT}/source-${current_commit}.tar.gz"

  current_release="$(readlink -f -- "${CURRENT_LINK}")"
  [[ "${current_release}" == "${expected_release}" ]] \
    || die "current runtime does not resolve to the expected content-addressed release"
  [[ -d "${current_release}" && ! -L "${current_release}" && -x "${current_release}/simc" ]] \
    || die "current content-addressed release is invalid"
  smoke_simc_binary "${current_release}/simc" \
    || die "current rollback release failed the semantic smoke test"
  binary_sha="$(sha256_file "${current_release}/simc")"
  if [[ -f "${legacy_archive}" && ! -L "${legacy_archive}" ]] \
    && tar -tzf "${legacy_archive}" >/dev/null 2>&1; then
    source_identity="$(sha256_file "${legacy_archive}")"
  fi

  write_release_metadata_once "${current_release}/.commit" "${current_commit}"
  write_release_metadata_once "${current_release}/binary.sha256" "${binary_sha}"
  write_release_metadata_once "${current_release}/source-archive.sha256" "${source_identity}"
  verify_release "${current_release}" "${current_commit}" \
    || die "current release could not be adopted as a rollback target"
}

switch_current_release() {
  local release_dir="$1"
  local previous_commit="$2"
  local current_commit=""
  local next_link="${SIMC_ROOT}/.current-next-${TARGET_COMMIT}-$$"
  local commit_tmp="${SIMC_ROOT}/.commit-next-${TARGET_COMMIT}-$$"

  current_commit="$(read_current_commit)"
  [[ "${current_commit}" == "${previous_commit}" ]] \
    || die "current runtime changed while the update was being prepared"
  [[ -L "${CURRENT_LINK}" ]] || die "current runtime pointer must be a symbolic link"
  [[ ! -e "${next_link}" && ! -L "${next_link}" ]] || die "temporary current link already exists"
  [[ ! -e "${commit_tmp}" && ! -L "${commit_tmp}" ]] || die "temporary commit marker already exists"

  ln -s "releases/${TARGET_COMMIT}" "${next_link}"
  mv -Tf -- "${next_link}" "${CURRENT_LINK}"
  printf '%s\n' "${TARGET_COMMIT}" > "${commit_tmp}"
  chmod 0644 "${commit_tmp}"
  mv -Tf -- "${commit_tmp}" "${COMPAT_COMMIT_FILE}"

  [[ "$(readlink -f -- "${CURRENT_LINK}")" == "${release_dir}" ]] \
    || die "current runtime pointer verification failed"
  [[ "$(read_current_commit)" == "${TARGET_COMMIT}" ]] \
    || die "current runtime commit verification failed"
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
    --target-commit)
      [[ $# -ge 2 ]] || die "--target-commit requires a value"
      TARGET_COMMIT="$2"
      shift 2
      ;;
    --expected-current-commit)
      [[ $# -ge 2 ]] || die "--expected-current-commit requires a value"
      EXPECTED_CURRENT_COMMIT="$2"
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

if [[ -n "${TARGET_COMMIT}" ]]; then
  validate_commit TARGET_COMMIT "${TARGET_COMMIT}"
fi
if [[ -n "${EXPECTED_CURRENT_COMMIT}" ]]; then
  validate_commit EXPECTED_CURRENT_COMMIT "${EXPECTED_CURRENT_COMMIT}"
fi

CURRENT_COMMIT="$(read_current_commit)"
if [[ "${MODE}" == "dry-run" ]]; then
  emit_dry_run "${CURRENT_COMMIT}"
  exit 0
fi

[[ -n "${TARGET_COMMIT}" ]] || die "--apply requires --target-commit"
[[ -n "${EXPECTED_CURRENT_COMMIT}" ]] || die "--apply requires --expected-current-commit"
[[ "${CURRENT_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || die "current runtime commit identity is missing or invalid"
[[ "${CURRENT_COMMIT}" == "${EXPECTED_CURRENT_COMMIT}" ]] \
  || die "current runtime commit does not match --expected-current-commit"
[[ -L "${CURRENT_LINK}" && -x "${CURRENT_LINK}/simc" ]] \
  || die "managed current SimulationCraft runtime is missing or not a symbolic link"

for command in flock sha256sum timeout python3 readlink awk; do
  command -v "${command}" >/dev/null 2>&1 || die "required command is missing: ${command}"
done

exec 9>"${LOCK_FILE}"
flock -w 30 9 || die "another Chickenbro SimC runtime update holds the lock"
CURRENT_COMMIT="$(read_current_commit)"
[[ "${CURRENT_COMMIT}" == "${EXPECTED_CURRENT_COMMIT}" ]] \
  || die "current runtime changed before the update lock was acquired"
[[ -L "${CURRENT_LINK}" && -x "${CURRENT_LINK}/simc" ]] \
  || die "managed current SimulationCraft runtime is missing or not a symbolic link"

if [[ "${TARGET_COMMIT}" == "${CURRENT_COMMIT}" ]]; then
  current_release="$(readlink -f -- "${CURRENT_LINK}")"
  [[ "${current_release}" == "${RELEASE_ROOT}/${CURRENT_COMMIT}" ]] \
    || die "already-current runtime is not the expected content-addressed release"
  verify_release "${current_release}" "${CURRENT_COMMIT}" \
    || die "already-current release failed identity validation"
  smoke_simc_binary "${current_release}/simc" \
    || die "already-current release failed the semantic smoke test"
  python3 - "${CURRENT_COMMIT}" <<'PY'
import json
import sys

print(json.dumps({
    "mode": "apply",
    "mutationAuthorized": False,
    "status": "already_current",
    "currentCommit": sys.argv[1],
    "targetCommit": sys.argv[1],
}, sort_keys=True, separators=(",", ":")))
PY
  exit 0
fi

for command in curl tar cmake df find install chmod mv ln rm date stat mktemp; do
  command -v "${command}" >/dev/null 2>&1 || die "required command is missing: ${command}"
done

release_dir="${RELEASE_ROOT}/${TARGET_COMMIT}"
if [[ ! -e "${release_dir}" && ! -L "${release_dir}" ]]; then
  available_bytes="$(df -PB1 -- "${SIMC_ROOT}" | awk 'NR == 2 {print $4}')"
  [[ "${available_bytes}" =~ ^[0-9]+$ ]] || die "unable to determine SimulationCraft filesystem capacity"
  (( available_bytes >= MINIMUM_FREE_BYTES )) \
    || die "SimulationCraft update requires at least ${MINIMUM_FREE_BYTES} free bytes"
fi

install -d -m 0755 -- "${RELEASE_ROOT}" "${WORK_ROOT}"
adopt_current_release "${CURRENT_COMMIT}"
if [[ -e "${release_dir}" || -L "${release_dir}" ]]; then
  verify_release "${release_dir}" "${TARGET_COMMIT}" \
    || die "existing target release failed identity validation"
  smoke_simc_binary "${release_dir}/simc" \
    || die "existing target release failed the semantic smoke test"
  switch_current_release "${release_dir}" "${EXPECTED_CURRENT_COMMIT}"
  binary_sha="$(sha256_file "${release_dir}/simc")"
  source_archive_sha="$(<"${release_dir}/source-archive.sha256")"
else
  WORK_DIR="$(mktemp -d "${WORK_ROOT}/update-${TARGET_COMMIT}.XXXXXX")"
  trap cleanup_work EXIT
  archive_path="${WORK_DIR}/source.tar.gz"
  source_dir="${WORK_DIR}/source"
  build_dir="${WORK_DIR}/build"
  staged_release="${WORK_DIR}/release"

  curl --proto '=https' --tlsv1.2 -fL --retry 5 --connect-timeout 30 \
    --speed-time 120 --speed-limit 1024 --max-filesize "${MAX_SOURCE_ARCHIVE_BYTES}" \
    --output "${archive_path}" "${SOURCE_ARCHIVE_BASE}/${TARGET_COMMIT}"
  archive_bytes="$(stat -c %s -- "${archive_path}")"
  [[ "${archive_bytes}" =~ ^[0-9]+$ && "${archive_bytes}" -le "${MAX_SOURCE_ARCHIVE_BYTES}" ]] \
    || die "SimulationCraft source archive exceeds the reviewed size limit"
  source_archive_sha="$(sha256_file "${archive_path}")"

  python3 - "${archive_path}" "${TARGET_COMMIT}" \
    "${MAX_SOURCE_EXPANDED_BYTES}" "${MAX_SOURCE_MEMBERS}" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

archive_path, commit, raw_expanded_limit, raw_member_limit = sys.argv[1:]
expanded_limit = int(raw_expanded_limit)
member_limit = int(raw_member_limit)
expected_root = f"simc-{commit}"
with tarfile.open(archive_path, mode="r:gz") as archive:
    members = archive.getmembers()
    if not members:
        raise SystemExit("SimulationCraft source archive is empty")
    if len(members) > member_limit:
        raise SystemExit("SimulationCraft source archive has too many members")
    if sum(member.size for member in members if member.isfile()) > expanded_limit:
        raise SystemExit("SimulationCraft source archive exceeds the expanded size limit")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or not path.parts or path.parts[0] != expected_root or ".." in path.parts:
            raise SystemExit("SimulationCraft source archive has an unsafe member path")
        if member.ischr() or member.isblk() or member.isfifo():
            raise SystemExit("SimulationCraft source archive has an unsupported special member")
        if member.issym() or member.islnk():
            target = PurePosixPath(member.linkname)
            if target.is_absolute() or ".." in target.parts:
                raise SystemExit("SimulationCraft source archive has an unsafe link target")
PY

  install -d -m 0755 -- "${source_dir}" "${build_dir}" "${staged_release}"
  tar -xzf "${archive_path}" --strip-components=1 -C "${source_dir}"
  cmake -S "${source_dir}" -B "${build_dir}" -DBUILD_GUI=OFF -DCMAKE_BUILD_TYPE=Release
  cmake --build "${build_dir}" --target simc --parallel "${BUILD_PARALLELISM}"

  built_simc="$(find "${build_dir}" -type f -name simc -perm -111 -print -quit)"
  [[ -n "${built_simc}" ]] || die "failed to locate the built SimulationCraft binary"
  smoke_simc_binary "${built_simc}" \
    || die "newly built SimulationCraft binary failed the semantic smoke test"

  install -m 0755 -- "${built_simc}" "${staged_release}/simc"
  binary_sha="$(sha256_file "${staged_release}/simc")"
  printf '%s\n' "${TARGET_COMMIT}" > "${staged_release}/.commit"
  printf '%s\n' "${binary_sha}" > "${staged_release}/binary.sha256"
  printf '%s\n' "${source_archive_sha}" > "${staged_release}/source-archive.sha256"
  date -u +%Y-%m-%dT%H:%M:%SZ > "${staged_release}/built-at"
  chmod 0644 "${staged_release}/.commit" "${staged_release}/binary.sha256" \
    "${staged_release}/source-archive.sha256" "${staged_release}/built-at"

  mv -T --no-clobber -- "${staged_release}" "${release_dir}" \
    || die "failed to atomically publish the target release"
  [[ ! -e "${staged_release}" && ! -L "${staged_release}" ]] \
    || die "target release appeared before atomic publication"
  verify_release "${release_dir}" "${TARGET_COMMIT}" \
    || die "new target release failed identity validation"
  switch_current_release "${release_dir}" "${EXPECTED_CURRENT_COMMIT}"
fi

if [[ -n "${WORK_DIR}" ]]; then
  remove_work_directory || die "failed to clean the exact build workspace"
  trap - EXIT
fi

python3 - "${EXPECTED_CURRENT_COMMIT}" "${TARGET_COMMIT}" "${binary_sha}" "${source_archive_sha}" <<'PY'
import json
import re
import sys

previous_commit, target_commit, binary_sha, archive_sha = sys.argv[1:]
recorded_archive_sha = archive_sha if re.fullmatch(r"[0-9a-f]{64}", archive_sha) else None
print(json.dumps({
    "mode": "apply",
    "mutationAuthorized": True,
    "status": "updated",
    "sourceRepository": "simulationcraft/simc",
    "previousCommit": previous_commit,
    "targetCommit": target_commit,
    "binarySha256": binary_sha,
    "sourceArchiveSha256": recorded_archive_sha,
    "sourceArchiveStatus": "recorded" if recorded_archive_sha else archive_sha,
    "currentLink": "/opt/wow-simc/current",
    "servicesRestarted": False,
}, sort_keys=True, separators=(",", ":")))
PY

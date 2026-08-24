#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="${WOW_EVIDENCE_SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)}"
REPO_ROOT="${WOW_EVIDENCE_REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd -P)}"
readonly SCRIPT_DIR
readonly REPO_ROOT

readonly WOW_EVIDENCE_REMOTE_ROOT_DEFAULT="/var/www/wow-evidence/releases"
readonly WOW_EVIDENCE_PUBLIC_BASE_DEFAULT="https://api.chickenbro.cloud/wow-evidence/releases"
readonly WOW_EVIDENCE_SSH_ALIAS_DEFAULT="wow-lighthouse"
readonly WOW_EVIDENCE_MAX_BYTES=$((256 * 1024 * 1024))

readonly PUBLISH_EVIDENCE_ALLOWLIST=(
  "artifacts/releases/2026-08-17-s2-official-api-fact-snapshot/official-api-capture-v8"
  "artifacts/releases/2026-08-19-s2-official-api-fact-snapshot/official-capture-inventory-v1"
  "artifacts/releases/2026-08-19-s2-limited-db2-field-expansion"
  "artifacts/releases/2026-08-20-s2-journal-item-db2-v1"
  "artifacts/releases/2026-08-20-s2-official-api-fact-snapshot/official-api-capture-v11"
  "artifacts/releases/2026-08-20-s2-official-api-fact-snapshot/official-capture-inventory-v11"
  "artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/candidate-final-v1.json"
  "artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/seal-report-set-membership-v1.json"
  "artifacts/releases/2026-08-21-s2-equipment-library-candidate-v73/live-smoke-v1.json"
  "artifacts/releases/2026-08-24-s2-equipment-library-ui-closure/evidence.json"
)

die() {
  echo "$*" >&2
  return 1
}

validate_release_id() {
  local release_id="${1:-}"
  if [[ ! "${release_id}" =~ ^[a-z0-9][a-z0-9._-]{7,63}$ ]]; then
    die "release-id must match ^[a-z0-9][a-z0-9._-]{7,63}$"
    return 1
  fi
  printf '%s\n' "${release_id}"
}

require_absolute_remote_root() {
  local remote_root="${1:-}"
  if [[ "${remote_root}" != /* ]]; then
    die "remote root must be an absolute path"
    return 1
  fi
  if [[ "${remote_root}" == *".."* ]]; then
    die "remote root must not contain path traversal"
    return 1
  fi
  printf '%s\n' "${remote_root%/}"
}

validate_allowlist_path() {
  local relative_path="${1:-}"
  if [[ -z "${relative_path}" || "${relative_path}" == /* || "${relative_path}" == *".."* ]]; then
    die "allowlist entry must stay inside the repository: ${relative_path}"
    return 1
  fi
}

resolve_repo_path() {
  local relative_path="${1:-}"
  validate_allowlist_path "${relative_path}" >/dev/null
  python3 - "${REPO_ROOT}" "${relative_path}" <<'PY'
import os
import sys

repo_root = os.path.realpath(sys.argv[1])
relative_path = sys.argv[2]
candidate = os.path.realpath(os.path.join(repo_root, relative_path))
prefix = repo_root + os.sep
if candidate != repo_root and not candidate.startswith(prefix):
    raise SystemExit(f"path escapes repository root: {relative_path}")
print(candidate)
PY
}

reject_symlinks() {
  local absolute_path="${1:-}"
  local relative_path="${2:-}"
  if [[ -L "${absolute_path}" ]]; then
    die "publisher rejects symlinked allowlist entries: ${relative_path}"
    return 1
  fi
  python3 - "${absolute_path}" "${relative_path}" <<'PY'
import os
import sys

absolute_path = sys.argv[1]
relative_path = sys.argv[2]
if os.path.isdir(absolute_path):
    for root, dirs, files in os.walk(absolute_path, followlinks=False):
        for name in dirs + files:
            candidate = os.path.join(root, name)
            if os.path.islink(candidate):
                raise SystemExit(
                    f"publisher rejects symlinked files inside {relative_path}: "
                    f"{os.path.relpath(candidate, absolute_path)}"
                )
PY
}

stage_selected_paths() {
  local staging_root="${1:?staging root required}"
  shift
  local relative_path absolute_path
  for relative_path in "$@"; do
    absolute_path="$(resolve_repo_path "${relative_path}")"
    if [[ ! -e "${absolute_path}" ]]; then
      die "allowlist path is missing: ${relative_path}"
      return 1
    fi
    reject_symlinks "${absolute_path}" "${relative_path}"
    mkdir -p "${staging_root}/$(dirname "${relative_path}")"
    tar -C "${REPO_ROOT}" -cf - "${relative_path}" | tar -C "${staging_root}" -xf -
  done
}

stage_allowlist() {
  local staging_root="${1:?staging root required}"
  stage_selected_paths "${staging_root}" "${PUBLISH_EVIDENCE_ALLOWLIST[@]}"
}

write_release_manifest() {
  local staging_root="${1:?staging root required}"
  local release_id="${2:?release id required}"
  local public_base="${3:?public base required}"
  local max_bytes="${4:-${WOW_EVIDENCE_MAX_BYTES}}"
  python3 - "${staging_root}" "${release_id}" "${public_base}" "${max_bytes}" <<'PY'
import hashlib
import json
import os
import sys

staging_root, release_id, public_base, max_bytes = sys.argv[1:5]
max_bytes = int(max_bytes)
files = []
total_bytes = 0

for root, dirs, filenames in os.walk(staging_root, topdown=True, followlinks=False):
    dirs.sort()
    filenames.sort()
    for name in filenames:
      if name == "release-manifest.json":
          continue
      absolute_path = os.path.join(root, name)
      if os.path.islink(absolute_path):
          raise SystemExit(f"publisher rejects symlinked staged files: {absolute_path}")
      relative_path = os.path.relpath(absolute_path, staging_root).replace(os.sep, "/")
      digest = hashlib.sha256()
      with open(absolute_path, "rb") as handle:
          data = handle.read()
      digest.update(data)
      byte_count = len(data)
      total_bytes += byte_count
      files.append({
          "path": relative_path,
          "sha256": digest.hexdigest(),
          "bytes": byte_count,
      })

if total_bytes > max_bytes:
    raise SystemExit(
        f"publisher payload exceeds {max_bytes} bytes: {total_bytes}"
    )

manifest = {
    "schemaVersion": 1,
    "releaseId": release_id,
    "immutableRoot": public_base.rstrip("/") + "/" + release_id,
    "fileCount": len(files),
    "totalBytes": total_bytes,
    "files": sorted(files, key=lambda item: item["path"]),
}

with open(
    os.path.join(staging_root, "release-manifest.json"),
    "w",
    encoding="utf-8",
) as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
}

build_remote_publish_script() {
  local remote_root
  remote_root="$(require_absolute_remote_root "${1:-}")"
  local release_id
  release_id="$(validate_release_id "${2:-}")"
  cat <<EOF
set -euo pipefail
remote_root='${remote_root}'
release_id='${release_id}'
release_dir="\${remote_root}/\${release_id}"
staging_dir="\${remote_root}/.\${release_id}.tmp.\$\$"
sudo mkdir -p "\${remote_root}"
cleanup() {
  sudo rm -rf "\${staging_dir}"
}
trap cleanup EXIT
sudo mkdir "\${staging_dir}"
sudo tar -xf - -C "\${staging_dir}"
if ! sudo mv -Tn "\${staging_dir}" "\${release_dir}"; then
  echo "release-id already exists on remote host or lost create-only race: \${release_id}" >&2
  exit 1
fi
if [ -e "\${staging_dir}" ]; then
  echo "release-id already exists on remote host or lost create-only race: \${release_id}" >&2
  exit 1
fi
sudo chown -R www-data:www-data "\${release_dir}"
trap - EXIT
EOF
}

publish_release() {
  local staging_root="${1:?staging root required}"
  local release_id="${2:?release id required}"
  local remote_root="${3:?remote root required}"
  local ssh_alias="${4:?ssh alias required}"
  tar -C "${staging_root}" -cf - . | ssh "${ssh_alias}" "$(build_remote_publish_script "${remote_root}" "${release_id}")"
}

main() {
  local release_id="${WOW_EVIDENCE_RELEASE_ID:-}"
  release_id="$(validate_release_id "${release_id}")"

  local remote_root="${WOW_EVIDENCE_REMOTE_ROOT:-${WOW_EVIDENCE_REMOTE_ROOT_DEFAULT}}"
  remote_root="$(require_absolute_remote_root "${remote_root}")"

  local public_base="${WOW_EVIDENCE_PUBLIC_BASE:-${WOW_EVIDENCE_PUBLIC_BASE_DEFAULT}}"
  local ssh_alias="${WOW_EVIDENCE_SSH_ALIAS:-${WOW_EVIDENCE_SSH_ALIAS_DEFAULT}}"

  local staging_root
  staging_root="$(mktemp -d "${TMPDIR:-/tmp}/wow-evidence-${release_id}-XXXXXX")"
  trap 'rm -rf "${staging_root}"' EXIT

  stage_allowlist "${staging_root}"
  write_release_manifest "${staging_root}" "${release_id}" "${public_base}"
  publish_release "${staging_root}" "${release_id}" "${remote_root}" "${ssh_alias}"

  echo "Published ${release_id} to ${public_base%/}/${release_id}/"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi

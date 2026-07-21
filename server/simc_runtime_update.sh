#!/usr/bin/env bash
set -euo pipefail

repo="${SIMC_GITHUB_REPO:-simulationcraft/simc}"
branch="${SIMC_BRANCH:-midnight}"
SIMC_ROOT="${SIMC_ROOT:-/opt/wow-simc}"
SIMC_SRC="${SIMC_SRC:-${SIMC_ROOT}/src}"
SIMC_BUILD="${SIMC_BUILD:-${SIMC_ROOT}/build}"
SIMC_CURRENT="${SIMC_CURRENT:-${SIMC_ROOT}/current}"
SIMC_BIN="${SIMC_BIN:-${SIMC_CURRENT}/simc}"
SIMC_COMMIT_FILE="${SIMC_COMMIT_FILE:-${SIMC_ROOT}/.commit}"

validate_env_value() {
  local name="$1"
  local value="$2"
  local pattern="$3"
  if [[ ! "${value}" =~ ${pattern} ]] || [[ "${value}" == *".."* ]]; then
    echo "Invalid ${name}: ${value}" >&2
    exit 1
  fi
}

run_version_check() {
  local version_check_bin=""
  if [[ -x /usr/local/bin/wow-simc-version-check ]]; then
    version_check_bin="/usr/local/bin/wow-simc-version-check"
  elif command -v wow-simc-version-check >/dev/null 2>&1; then
    version_check_bin="$(command -v wow-simc-version-check)"
  fi
  if [[ -n "${version_check_bin}" ]]; then
    SIMC_GITHUB_REPO="${repo}" \
      SIMC_BRANCH="${branch}" \
      SIMC_COMMIT_FILE="${SIMC_COMMIT_FILE}" \
      SIMC_BIN="${SIMC_BIN}" \
      "${version_check_bin}" || true
  fi
}

validate_env_value SIMC_GITHUB_REPO "${repo}" '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
validate_env_value SIMC_BRANCH "${branch}" '^[A-Za-z0-9_.@/-]+$'

mkdir -p "${SIMC_ROOT}"
branch_api_url="https://api.github.com/repos/${repo}/branches/${branch}"

latest_simc_commit="$(BRANCH_API_URL="${branch_api_url}" python3 - <<'PY'
import json
import os
import sys
from urllib.request import urlopen

url = os.environ["BRANCH_API_URL"]
try:
    with urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(payload["commit"]["sha"])
except Exception as error:
    print(f"failed to resolve SimulationCraft branch commit: {error}", file=sys.stderr)
    sys.exit(1)
PY
)"

if [[ -x "${SIMC_BIN}" && -f "${SIMC_COMMIT_FILE}" && "$(cat "${SIMC_COMMIT_FILE}")" == "${latest_simc_commit}" ]]; then
  echo "SimulationCraft runtime already current: ${latest_simc_commit}"
  run_version_check
  exit 0
fi

simc_archive="${SIMC_ROOT}/source-${latest_simc_commit}.tar.gz"
if [[ ! -f "${simc_archive}" ]] || ! tar -tzf "${simc_archive}" >/dev/null 2>&1; then
  curl -fL --retry 5 --connect-timeout 30 --speed-time 120 --speed-limit 1024 \
    -o "${simc_archive}" \
    "https://codeload.github.com/${repo}/tar.gz/${latest_simc_commit}"
fi

rm -rf "${SIMC_SRC}" "${SIMC_BUILD}"
mkdir -p "${SIMC_SRC}"
tar -xzf "${simc_archive}" --strip-components=1 -C "${SIMC_SRC}"
cmake -S "${SIMC_SRC}" -B "${SIMC_BUILD}" -DBUILD_GUI=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build "${SIMC_BUILD}" --target simc --parallel "$(nproc)"

built_simc="$(find "${SIMC_BUILD}" -type f -name simc -perm -111 | head -n 1)"
if [[ -z "${built_simc}" ]]; then
  echo "failed to locate built simc binary under ${SIMC_BUILD}" >&2
  exit 1
fi

release_root="${SIMC_ROOT}/releases"
release_dir="${release_root}/${latest_simc_commit}"
staging_dir="${release_root}/.staging-${latest_simc_commit}-$$"
mkdir -p "${release_root}"
rm -rf "${staging_dir}"
mkdir -p "${staging_dir}"
cp "${built_simc}" "${staging_dir}/simc"
chmod 0755 "${staging_dir}/simc"

if [[ -e "${release_dir}" || -L "${release_dir}" ]]; then
  rm -rf "${release_dir}"
fi
mv "${staging_dir}" "${release_dir}"

if [[ -e "${SIMC_CURRENT}" && ! -L "${SIMC_CURRENT}" ]]; then
  backup_dir="${SIMC_ROOT}/current.backup-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "${SIMC_CURRENT}" "${backup_dir}"
fi
ln -sfn "${release_dir}" "${SIMC_CURRENT}"
printf '%s\n' "${latest_simc_commit}" >"${SIMC_COMMIT_FILE}"

run_version_check
echo "SimulationCraft runtime updated to ${latest_simc_commit}"

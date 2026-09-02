#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
REMOTE_DIR="${WOW_LIGHTHOUSE_DIR:-/opt/wow-mini-program}"
CODEX_HOME_DIR="${WOW_CODEX_HOME:-/home/${REMOTE_USER}/.codex}"
CODEX_PROFILE_NAME="chickenbro-native"
SKIP_DEPENDENCY_INSTALL="${WOW_V2_SKIP_DEPENDENCY_INSTALL:-0}"
V2_SERVICE="wow-v2-api"
V2_WORKER_SERVICE="wow-v2-worker"
V2_ENV_FILE="/etc/wow-v2-api.env"
V2_SOURCE_ENV_FILE="/etc/wow-v2-source.env"
NGINX_SITE="/etc/nginx/sites-available/wow-v2-web"
NGINX_LINK="/etc/nginx/sites-enabled/wow-v2-web"
WEB_ROOT="/var/www/chickenbro-web"
TLS_CERT="/etc/nginx/ssl/www.chickenbro.cloud/www.chickenbro.cloud_bundle.pem"
TLS_KEY="/etc/nginx/ssl/www.chickenbro.cloud/www.chickenbro.cloud.key"
V2_STAGE_ROOT="/opt/wow-v2-staging"
V2_BACKUP_ROOT="/var/backups/wow-v2"
RELEASE_ID="${WOW_V2_RELEASE_ID:-$(git -C "${REPO_ROOT}" rev-parse --short=12 HEAD)}"
RUN_ID="${WOW_V2_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-${RELEASE_ID}}"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15)

die() {
  echo "deploy_web_v2: $*" >&2
  exit 1
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

validate_value REMOTE_HOST "${REMOTE_HOST}" '^[A-Za-z0-9_.:-]+$'
validate_value REMOTE_USER "${REMOTE_USER}" '^[A-Za-z_][A-Za-z0-9_.-]*$'
validate_value REMOTE_DIR "${REMOTE_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_value CODEX_HOME_DIR "${CODEX_HOME_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_value SKIP_DEPENDENCY_INSTALL "${SKIP_DEPENDENCY_INSTALL}" '^[01]$'
validate_value V2_ENV_FILE "${V2_ENV_FILE}" '^/[A-Za-z0-9_./-]+$'
validate_value V2_SOURCE_ENV_FILE "${V2_SOURCE_ENV_FILE}" '^/[A-Za-z0-9_./-]+$'
validate_value RELEASE_ID "${RELEASE_ID}" '^[A-Za-z0-9_.-]+$'
validate_value RUN_ID "${RUN_ID}" '^[A-Za-z0-9_.-]+$'
reject_path_traversal REMOTE_DIR "${REMOTE_DIR}"
reject_path_traversal CODEX_HOME_DIR "${CODEX_HOME_DIR}"
reject_path_traversal V2_ENV_FILE "${V2_ENV_FILE}"
reject_path_traversal V2_SOURCE_ENV_FILE "${V2_SOURCE_ENV_FILE}"

[[ -f "${REPO_ROOT}/server/wow-v2-api.service" ]] || die 'missing v2 systemd template'
[[ -f "${REPO_ROOT}/server/wow-v2-worker.service" ]] || die 'missing v2 worker systemd template'
[[ -f "${REPO_ROOT}/server/wow-v2-web.nginx" ]] || die 'missing v2 nginx template'
[[ -f "${REPO_ROOT}/server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql" ]] || die 'missing v2 foundation migration'
[[ -f "${REPO_ROOT}/server/migrations/postgres/0039_wechat_web_login_sessions.sql" ]] || die 'missing v2 migration'
[[ -f "${REPO_ROOT}/server/migrations/postgres/0040_web_prototype_sessions.sql" ]] || die 'missing prototype migration'
[[ -f "${REPO_ROOT}/server/requirements-v2.txt" ]] || die 'missing v2 requirements'
[[ -d "${REPO_ROOT}/server/app" ]] || die 'missing v2 application source'
[[ -f "${REPO_ROOT}/server/chickenbro_native_mcp.py" ]] || die 'missing native MCP source'
[[ -f "${REPO_ROOT}/server/chickenbro_public_web_research.py" ]] || die 'missing native public-web source'
[[ -f "${REPO_ROOT}/scripts/chickenbro-native-agent/chickenbro-native.config.toml.template" ]] || die 'missing native Codex profile template'
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/h5/index.html" ]] || die 'build H5 before candidate deployment'
grep -q '^EnvironmentFile=-/etc/wow-v2-api.env$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use the isolated environment file'
grep -q '^Environment=WOW_DATABASE_RUNTIME=postgres_only$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use PostgreSQL-only runtime'
grep -q '^Environment=WOW_CODEX_BIN=/usr/local/bin/codex$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use the native Codex binary'
grep -q '^Environment=WOW_CODEX_PROFILE=chickenbro-native$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use the stable native Codex profile'
grep -q '^Environment=WOW_CHICKENBRO_CODEX_ENABLED=1$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must enable native Codex'
grep -q '^Environment=WOW_WEB_PROTOTYPE_ENABLED=1$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must enable the Web prototype'
grep -q '^After=network-online.target mihomo.service$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must wait for the configured proxy service'
for proxy_variable in HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY http_proxy https_proxy all_proxy no_proxy; do
  grep -q "^Environment=${proxy_variable}=" "${REPO_ROOT}/server/wow-v2-api.service" || die "v2 service must expose ${proxy_variable} to native Codex"
done
grep -q '^Environment=ALL_PROXY=http://' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use an HTTP-compatible ALL_PROXY without requiring socksio'
grep -q '^Environment=all_proxy=http://' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use an HTTP-compatible all_proxy without requiring socksio'

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

REMOTE_ENV=(
  "REMOTE_USER=${REMOTE_USER}"
  "RUN_ID=${RUN_ID}"
  "RELEASE_ID=${RELEASE_ID}"
  "REMOTE_DIR=${REMOTE_DIR}"
  "CODEX_HOME_DIR=${CODEX_HOME_DIR}"
  "CODEX_PROFILE_NAME=${CODEX_PROFILE_NAME}"
  "SKIP_DEPENDENCY_INSTALL=${SKIP_DEPENDENCY_INSTALL}"
  "V2_SERVICE=${V2_SERVICE}"
  "V2_WORKER_SERVICE=${V2_WORKER_SERVICE}"
  "V2_ENV_FILE=${V2_ENV_FILE}"
  "V2_SOURCE_ENV_FILE=${V2_SOURCE_ENV_FILE}"
  "NGINX_SITE=${NGINX_SITE}"
  "NGINX_LINK=${NGINX_LINK}"
  "WEB_ROOT=${WEB_ROOT}"
  "TLS_CERT=${TLS_CERT}"
  "TLS_KEY=${TLS_KEY}"
  "V2_STAGE_ROOT=${V2_STAGE_ROOT}"
  "V2_BACKUP_ROOT=${V2_BACKUP_ROOT}"
)

remote_env_args() {
  local item
  for item in "${REMOTE_ENV[@]}"; do
    printf '%q ' "${item}"
  done
}

echo "Checking v2 candidate prerequisites on ${SSH_TARGET}"
ssh_remote "$(remote_env_args) sudo -E bash -s" <<'REMOTE_PREFLIGHT'
set -euo pipefail

die_remote() {
  echo "deploy_web_v2 remote: $*" >&2
  exit 1
}

for command_name in python3 psql pg_dump nginx systemctl tar curl openssl sudo; do
  command -v "${command_name}" >/dev/null 2>&1 || die_remote "missing command: ${command_name}"
done

[[ -f "${V2_ENV_FILE}" ]] || die_remote "missing ${V2_ENV_FILE}; create it with mode 0600"
[[ "$(stat -c '%a' "${V2_ENV_FILE}")" == "600" ]] || die_remote "${V2_ENV_FILE} must have mode 0600"
if [[ -e "${V2_SOURCE_ENV_FILE}" ]]; then
  [[ -f "${V2_SOURCE_ENV_FILE}" ]] || die_remote "${V2_SOURCE_ENV_FILE} must be a regular file"
  [[ "$(stat -c '%a' "${V2_SOURCE_ENV_FILE}")" == "600" ]] || die_remote "${V2_SOURCE_ENV_FILE} must have mode 0600"
fi
[[ -r "${TLS_CERT}" && -r "${TLS_KEY}" ]] || die_remote 'configured TLS certificate paths are not readable'

CODEX_BIN="${WOW_CODEX_BIN:-/usr/local/bin/codex}"
CODEX_JOBS_DIR="${WOW_CODEX_JOBS_DIR:-/var/lib/wow-backend/codex-jobs}"
[[ -x "${CODEX_BIN}" ]] || die_remote "native Codex binary is not executable: ${CODEX_BIN}"
[[ -d "${CODEX_HOME_DIR}" ]] || die_remote "native Codex home is missing: ${CODEX_HOME_DIR}"
[[ -d "${CODEX_JOBS_DIR}" ]] || die_remote "native Codex jobs directory is missing: ${CODEX_JOBS_DIR}"

if ! openssl x509 -in "${TLS_CERT}" -noout -ext subjectAltName 2>/dev/null | grep -Eq 'DNS:www\.chickenbro\.cloud([,[:space:]]|$)'; then
  die_remote 'configured TLS certificate does not cover www.chickenbro.cloud'
fi

set +u
set -a
source "${V2_ENV_FILE}"
set +a
set -u
[[ "${WOW_DATABASE_URL:-}" == postgresql://* || "${WOW_DATABASE_URL:-}" == postgres://* ]] || die_remote 'v2 env must provide a PostgreSQL WOW_DATABASE_URL'

# The runtime DSN is intentionally wow_app and cannot create schemas or alter
# the formal identity owner. Prefer an explicitly provisioned migrator DSN;
# otherwise use the local PostgreSQL administrator only to SET ROLE to the
# existing, non-superuser wow_migrator owner. No application privilege is
# widened by the candidate deploy.
MIGRATION_DATABASE_NAME="$(psql --dbname="${WOW_DATABASE_URL}" --tuples-only --no-align --command='select current_database()' | tr -d '[:space:]')"
[[ -n "${MIGRATION_DATABASE_NAME}" && "${MIGRATION_DATABASE_NAME}" != *[!A-Za-z0-9_.-]* ]] || die_remote 'could not resolve a safe v2 migration database name'
if [[ -n "${WOW_DATABASE_MIGRATOR_URL:-}" ]]; then
  [[ "${WOW_DATABASE_MIGRATOR_URL}" == postgresql://* || "${WOW_DATABASE_MIGRATOR_URL}" == postgres://* ]] || die_remote 'WOW_DATABASE_MIGRATOR_URL must be PostgreSQL'
  [[ "$(psql --dbname="${WOW_DATABASE_MIGRATOR_URL}" --tuples-only --no-align --command='select current_user' | tr -d '[:space:]')" == 'wow_migrator' ]] || die_remote 'WOW_DATABASE_MIGRATOR_URL must authenticate as wow_migrator'
else
  MIGRATION_ROLE="$(sudo -u postgres env -u PGPASSFILE -u PGHOST -u PGPORT -u PGUSER psql --dbname="${MIGRATION_DATABASE_NAME}" --tuples-only --no-align --command='SET ROLE wow_migrator; SELECT current_user' | tail -n 1 | tr -d '[:space:]')"
  [[ "${MIGRATION_ROLE}" == 'wow_migrator' ]] || die_remote 'local PostgreSQL migrator handoff did not resolve wow_migrator'
fi

BACKUP_DIR="${V2_BACKUP_ROOT}/${RUN_ID}"
[[ ! -e "${BACKUP_DIR}" ]] || die_remote "backup run already exists: ${RUN_ID}"
install -d -m 0700 "${BACKUP_DIR}"

tar --ignore-failed-read --format=posix -czf "${BACKUP_DIR}/v2-paths.tgz" -C / \
  "${REMOTE_DIR#/}/server/app" \
  "${REMOTE_DIR#/}/server/chickenbro_native_mcp.py" \
  "${REMOTE_DIR#/}/server/chickenbro_public_web_research.py" \
  "${REMOTE_DIR#/}/server/requirements-v2.txt" \
  "${REMOTE_DIR#/}/server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql" \
  "${REMOTE_DIR#/}/server/migrations/postgres/0039_wechat_web_login_sessions.sql" \
  "${REMOTE_DIR#/}/server/migrations/postgres/0040_web_prototype_sessions.sql" \
  "etc/systemd/system/${V2_SERVICE}.service" \
  "etc/systemd/system/${V2_WORKER_SERVICE}.service" \
  "etc/nginx/sites-available/wow-v2-web" \
  "etc/nginx/sites-enabled/wow-v2-web" \
  "var/www/chickenbro-web"

CODEX_PROFILE_PATH="${CODEX_HOME_DIR}/${CODEX_PROFILE_NAME}.config.toml"
if [[ -f "${CODEX_PROFILE_PATH}" ]]; then
  cp --preserve=mode,ownership "${CODEX_PROFILE_PATH}" "${BACKUP_DIR}/codex-profile"
  printf '%s\n' 'present' > "${BACKUP_DIR}/codex-profile-state"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/codex-profile-state"
fi

cp --preserve=mode,ownership "${V2_ENV_FILE}" "${BACKUP_DIR}/wow-v2-api.env"
if [[ -f "${V2_SOURCE_ENV_FILE}" ]]; then
  cp --preserve=mode,ownership "${V2_SOURCE_ENV_FILE}" "${BACKUP_DIR}/wow-v2-source.env"
  printf '%s\n' 'present' > "${BACKUP_DIR}/wow-v2-source-env-state"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/wow-v2-source-env-state"
fi
if [[ -f "/etc/systemd/system/${V2_SERVICE}.service" ]]; then
  cp --preserve=mode,ownership "/etc/systemd/system/${V2_SERVICE}.service" "${BACKUP_DIR}/v2-api.service"
fi
if [[ -f "/etc/systemd/system/${V2_WORKER_SERVICE}.service" ]]; then
  cp --preserve=mode,ownership "/etc/systemd/system/${V2_WORKER_SERVICE}.service" "${BACKUP_DIR}/v2-worker.service"
fi
if [[ -f "${NGINX_SITE}" ]]; then
  cp --preserve=mode,ownership "${NGINX_SITE}" "${BACKUP_DIR}/wow-v2-web.nginx"
fi
if [[ -L "${NGINX_LINK}" ]]; then
  readlink "${NGINX_LINK}" > "${BACKUP_DIR}/nginx-link-target"
elif [[ -e "${NGINX_LINK}" ]]; then
  cp --preserve=mode,ownership "${NGINX_LINK}" "${BACKUP_DIR}/nginx-link-file"
fi
if pg_dump --format=custom --file="${BACKUP_DIR}/postgres-target.dump" --dbname="${WOW_DATABASE_URL}" \
  >/dev/null 2>"${BACKUP_DIR}/postgres-target.full-dump.error"; then
  printf '%s\n' 'backup_mode=full' > "${BACKUP_DIR}/postgres-target.scope"
else
  echo 'full database dump failed or was not permitted; recording scoped database backup for the additive migration scope' >&2
  pg_dump --format=custom --file="${BACKUP_DIR}/postgres-target.dump" --dbname="${WOW_DATABASE_URL}" \
    --table=identity.users --table=ops.schema_migrations >/dev/null
  cat >"${BACKUP_DIR}/postgres-target.scope" <<'BACKUP_SCOPE'
backup_mode=scoped
tables=identity.users,ops.schema_migrations
reason=unrelated legacy tables are not dumpable by the v2 database role; candidate migrations are additive
BACKUP_SCOPE
fi
printf '%s\n' "${RELEASE_ID}" > "${BACKUP_DIR}/release-id"
printf '%s\n' "${V2_ENV_FILE}" > "${BACKUP_DIR}/environment-path"
printf '%s\n' "backup_complete" > "${BACKUP_DIR}/READY"
echo "backup=${BACKUP_DIR}"
REMOTE_PREFLIGHT

PACKAGE_PATH="$(mktemp -t chickenbro-v2.XXXXXX.tar.gz)"
SOURCE_LIST="$(mktemp -t chickenbro-v2-files.XXXXXX)"
REMOTE_PACKAGE_PATH="/tmp/chickenbro-v2-${RUN_ID}.tar.gz"
trap 'rm -f "${PACKAGE_PATH}" "${SOURCE_LIST}"' EXIT

git -C "${REPO_ROOT}" ls-files -z --cached --others --exclude-standard -- \
  server/app \
  server/chickenbro_native_mcp.py \
  server/chickenbro_public_web_research.py \
  server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql \
  server/migrations/postgres/0039_wechat_web_login_sessions.sql \
  server/migrations/postgres/0040_web_prototype_sessions.sql \
  server/requirements-v2.txt \
  server/wow-v2-api.service \
  server/wow-v2-worker.service \
  server/wow-v2-web.nginx \
  scripts/chickenbro-native-agent/chickenbro-native.config.toml.template > "${SOURCE_LIST}"
printf '%s\0' 'apps/mini-taro/dist/h5' >> "${SOURCE_LIST}"
COPYFILE_DISABLE=1 tar --null --files-from="${SOURCE_LIST}" --format=ustar -czf "${PACKAGE_PATH}" -C "${REPO_ROOT}"

PACKAGE_SHA256="$(shasum -a 256 "${PACKAGE_PATH}" | awk '{print $1}')"
scp_remote "${PACKAGE_PATH}" "${SSH_TARGET}:${REMOTE_PACKAGE_PATH}"

echo "Installing isolated v2 candidate ${RELEASE_ID}"
ssh_remote "$(remote_env_args) PACKAGE_PATH='${REMOTE_PACKAGE_PATH}' PACKAGE_SHA256='${PACKAGE_SHA256}' sudo -E bash -s" <<'REMOTE_DEPLOY'
set -euo pipefail

die_remote() {
  echo "deploy_web_v2 remote: $*" >&2
  exit 1
}

BACKUP_DIR="${V2_BACKUP_ROOT}/${RUN_ID}"
STAGE_DIR="${V2_STAGE_ROOT}/${RUN_ID}"
WEB_RELEASE_DIR="${WEB_ROOT}/releases/${RUN_ID}"
WEB_CURRENT_LINK="${WEB_ROOT}/current"
REMOTE_APP_ROOT="${REMOTE_DIR}/server/app"
REMOTE_MIGRATION_DIR="${REMOTE_DIR}/server/migrations/postgres"
VENV_DIR="${REMOTE_DIR}/.venv-v2"
CODEX_PROFILE_PATH="${CODEX_HOME_DIR}/${CODEX_PROFILE_NAME}.config.toml"
CODEX_PROFILE_TEMPLATE="${STAGE_DIR}/scripts/chickenbro-native-agent/chickenbro-native.config.toml.template"
OLD_CURRENT_TARGET=''
if [[ -L "${WEB_CURRENT_LINK}" ]]; then
  OLD_CURRENT_TARGET="$(readlink "${WEB_CURRENT_LINK}")"
elif [[ -e "${WEB_CURRENT_LINK}" ]]; then
  die_remote "refusing to replace non-symlink Web current path: ${WEB_CURRENT_LINK}"
fi

rollback_v2() {
  local exit_code=$?
  if [[ "${exit_code}" -eq 0 ]]; then
    rm -f "${PACKAGE_PATH}"
    exit 0
  fi
  set +e
  systemctl stop "${V2_SERVICE}" >/dev/null 2>&1 || true
  systemctl stop "${V2_WORKER_SERVICE}" >/dev/null 2>&1 || true
  if [[ -f "${BACKUP_DIR}/v2-api.service" ]]; then
    install -m 0644 "${BACKUP_DIR}/v2-api.service" "/etc/systemd/system/${V2_SERVICE}.service"
  else
    rm -f "/etc/systemd/system/${V2_SERVICE}.service"
  fi
  if [[ -f "${BACKUP_DIR}/v2-worker.service" ]]; then
    install -m 0644 "${BACKUP_DIR}/v2-worker.service" "/etc/systemd/system/${V2_WORKER_SERVICE}.service"
  else
    rm -f "/etc/systemd/system/${V2_WORKER_SERVICE}.service"
    rm -f "/etc/systemd/system/multi-user.target.wants/${V2_WORKER_SERVICE}.service"
  fi
  if [[ -f "${BACKUP_DIR}/wow-v2-source.env" ]]; then
    install -o root -g root -m 0600 "${BACKUP_DIR}/wow-v2-source.env" "${V2_SOURCE_ENV_FILE}"
  elif [[ -f "${BACKUP_DIR}/wow-v2-source-env-state" ]] && grep -qx 'absent' "${BACKUP_DIR}/wow-v2-source-env-state"; then
    rm -f "${V2_SOURCE_ENV_FILE}"
  fi
  if [[ -f "${BACKUP_DIR}/wow-v2-web.nginx" ]]; then
    install -m 0644 "${BACKUP_DIR}/wow-v2-web.nginx" "${NGINX_SITE}"
  else
    rm -f "${NGINX_SITE}"
  fi
  if [[ -f "${BACKUP_DIR}/nginx-link-target" ]]; then
    OLD_NGINX_LINK_TARGET=''
    read -r OLD_NGINX_LINK_TARGET < "${BACKUP_DIR}/nginx-link-target"
    ln -sfn "${OLD_NGINX_LINK_TARGET}" "${NGINX_LINK}"
  elif [[ -f "${BACKUP_DIR}/nginx-link-file" ]]; then
    install -m 0644 "${BACKUP_DIR}/nginx-link-file" "${NGINX_LINK}"
  else
    rm -f "${NGINX_LINK}"
  fi
  if [[ -n "${OLD_CURRENT_TARGET}" ]]; then
    ln -sfn "${OLD_CURRENT_TARGET}" "${WEB_CURRENT_LINK}"
  else
    rm -f "${WEB_CURRENT_LINK}"
  fi
  if [[ -f "${BACKUP_DIR}/v2-paths.tgz" ]]; then
    tar -xzf "${BACKUP_DIR}/v2-paths.tgz" -C / \
      "${REMOTE_DIR#/}/server/app" \
      "${REMOTE_DIR#/}/server/chickenbro_native_mcp.py" \
      "${REMOTE_DIR#/}/server/chickenbro_public_web_research.py" \
      "${REMOTE_DIR#/}/server/requirements-v2.txt" >/dev/null 2>&1 || true
  fi
  CODEX_PROFILE_PATH="${CODEX_HOME_DIR}/${CODEX_PROFILE_NAME}.config.toml"
  if [[ -f "${BACKUP_DIR}/codex-profile" ]]; then
    install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${BACKUP_DIR}/codex-profile" "${CODEX_PROFILE_PATH}"
  elif [[ -f "${BACKUP_DIR}/codex-profile-state" ]] && grep -qx 'absent' "${BACKUP_DIR}/codex-profile-state"; then
    rm -f "${CODEX_PROFILE_PATH}"
  fi
  systemctl daemon-reload >/dev/null 2>&1 || true
  if [[ -f "${BACKUP_DIR}/v2-api.service" ]]; then
    systemctl start "${V2_SERVICE}" >/dev/null 2>&1 || true
  fi
  if [[ -f "${BACKUP_DIR}/v2-worker.service" ]]; then
    systemctl start "${V2_WORKER_SERVICE}" >/dev/null 2>&1 || true
  fi
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
  fi
  rm -f "${PACKAGE_PATH}"
  echo "v2 candidate failed; named v2 assets restored; PostgreSQL backup preserved at ${BACKUP_DIR}" >&2
  exit "${exit_code}"
}
trap rollback_v2 EXIT

wait_for_http() {
  local url="$1"
  local resolve_value="${2:-}"
  local attempt
  for attempt in {1..15}; do
    if [[ -n "${resolve_value}" ]]; then
      if curl -fsS --max-time 15 --resolve "${resolve_value}" "${url}" >/dev/null; then
        return 0
      fi
    elif curl -fsS --max-time 15 "${url}" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  die_remote "timed out waiting for ${url}"
}

wait_for_worker() {
  local attempt
  local worker_pid
  for attempt in {1..15}; do
    worker_pid="$(systemctl show -p MainPID --value "${V2_WORKER_SERVICE}")"
    if [[ "${worker_pid}" =~ ^[1-9][0-9]*$ ]]; then
      WORKER_PID="${worker_pid}"
      return 0
    fi
    sleep 1
  done
  die_remote 'v2 worker did not start'
}

[[ "$(sha256sum "${PACKAGE_PATH}" | awk '{print $1}')" == "${PACKAGE_SHA256}" ]] || die_remote 'candidate package checksum mismatch'
[[ ! -e "${STAGE_DIR}" ]] || die_remote "staging run already exists: ${RUN_ID}"
install -d -m 0750 "${STAGE_DIR}"
tar -xzf "${PACKAGE_PATH}" -C "${STAGE_DIR}"

# Stop only the isolated v2 processes before replacing imported application code
# and applying the additive schema. The legacy service is never touched.
systemctl stop "${V2_SERVICE}" "${V2_WORKER_SERVICE}" >/dev/null 2>&1 || true

install -d -m 0755 "${REMOTE_APP_ROOT}" "${REMOTE_MIGRATION_DIR}"
cp -a "${STAGE_DIR}/server/app/." "${REMOTE_APP_ROOT}/"
install -m 0644 "${STAGE_DIR}/server/chickenbro_native_mcp.py" "${REMOTE_DIR}/server/chickenbro_native_mcp.py"
install -m 0644 "${STAGE_DIR}/server/chickenbro_public_web_research.py" "${REMOTE_DIR}/server/chickenbro_public_web_research.py"
[[ -f "${CODEX_PROFILE_TEMPLATE}" ]] || die_remote 'candidate is missing the native Codex profile template'
sed "s#__CHICKENBRO_CANDIDATE_ROOT__#${REMOTE_DIR}#g" \
  "${CODEX_PROFILE_TEMPLATE}" > "${STAGE_DIR}/chickenbro-native.config.toml"
grep -Fq "args = [\"${REMOTE_DIR}/server/chickenbro_native_mcp.py\"]" "${STAGE_DIR}/chickenbro-native.config.toml" \
  || die_remote 'native Codex profile did not bind to the stable runtime MCP source'
grep -Fq "cwd = \"${REMOTE_DIR}\"" "${STAGE_DIR}/chickenbro-native.config.toml" \
  || die_remote 'native Codex profile did not bind to the stable runtime cwd'
install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 \
  "${STAGE_DIR}/chickenbro-native.config.toml" "${CODEX_PROFILE_PATH}"
for migration in \
  0038_chickenbro_simc_platform_foundation.sql \
  0039_wechat_web_login_sessions.sql \
  0040_web_prototype_sessions.sql; do
  [[ -f "${STAGE_DIR}/server/migrations/postgres/${migration}" ]] || die_remote "candidate is missing migration: ${migration}"
  install -m 0644 "${STAGE_DIR}/server/migrations/postgres/${migration}" "${REMOTE_MIGRATION_DIR}/${migration}"
done
install -m 0644 "${STAGE_DIR}/server/requirements-v2.txt" "${REMOTE_DIR}/server/requirements-v2.txt"

# The legacy service already owns the configured source credentials. Copy only
# the WCL/Raider.IO keys into a dedicated root-only v2 env file; never load the
# complete legacy environment into the new API or forward these values to Codex.
if [[ ! -f "${V2_SOURCE_ENV_FILE}" ]]; then
  SOURCE_ENV_TMP="$(mktemp)"
  if [[ -r "/etc/wow-backend.env" ]]; then
    awk '/^(WOW_RAIDERIO_API_KEY|WOW_RAIDERIO_USER_AGENT|WOW_RAIDERIO_TIMEOUT_SECONDS|WOW_WARCRAFTLOGS_API_KEY|WOW_WARCRAFTLOGS_CLIENT_ID|WOW_WARCRAFTLOGS_CLIENT_SECRET|WOW_WARCRAFTLOGS_GRAPHQL_URL|WOW_WARCRAFTLOGS_TOKEN_URL|WOW_WARCRAFTLOGS_TIMEOUT_SECONDS)=/{print}' \
      "/etc/wow-backend.env" > "${SOURCE_ENV_TMP}"
  fi
  install -o root -g root -m 0600 "${SOURCE_ENV_TMP}" "${V2_SOURCE_ENV_FILE}"
  rm -f "${SOURCE_ENV_TMP}"
fi
[[ "$(stat -c '%a' "${V2_SOURCE_ENV_FILE}")" == "600" ]] || die_remote "${V2_SOURCE_ENV_FILE} must have mode 0600"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  python3 -m venv "${VENV_DIR}"
fi
if [[ "${SKIP_DEPENDENCY_INSTALL}" == "1" ]]; then
  "${VENV_DIR}/bin/python" -m pip check >/dev/null || die_remote 'existing v2 virtualenv does not satisfy requirements'
else
  PIP_DISABLE_PIP_VERSION_CHECK=1 "${VENV_DIR}/bin/pip" install --no-input --requirement "${REMOTE_DIR}/server/requirements-v2.txt" >/dev/null
fi

set +u
set -a
source "${V2_ENV_FILE}"
set +a
set -u
: >"${BACKUP_DIR}/migration.log"
MIGRATION_DATABASE_NAME="$(psql --dbname="${WOW_DATABASE_URL}" --tuples-only --no-align --command='select current_database()' | tr -d '[:space:]')"
migration_is_applied() {
  local migration_id="$1"
  [[ "$(psql --dbname="${WOW_DATABASE_URL}" --tuples-only --no-align --command="select 1 from ops.schema_migrations where id = '${migration_id}'" | tr -d '[:space:]')" == '1' ]]
}
if [[ -n "${WOW_DATABASE_MIGRATOR_URL:-}" ]]; then
  MIGRATION_AUTH_MODE='explicit-wow_migrator-dsn'
  apply_v2_migration() {
    psql --dbname="${WOW_DATABASE_MIGRATOR_URL}" --set ON_ERROR_STOP=1 --single-transaction --file="$1"
  }
else
  MIGRATION_AUTH_MODE='local-postgres-set-role-wow_migrator'
  apply_v2_migration() {
    sudo -u postgres env -u PGPASSFILE -u PGHOST -u PGPORT -u PGUSER \
      psql --dbname="${MIGRATION_DATABASE_NAME}" --set ON_ERROR_STOP=1 \
      --single-transaction --command='SET ROLE wow_migrator' --file="$1"
  }
fi
printf 'migration_auth_mode=%s\n' "${MIGRATION_AUTH_MODE}" >>"${BACKUP_DIR}/migration.log"
for migration in \
  0038_chickenbro_simc_platform_foundation.sql \
  0039_wechat_web_login_sessions.sql \
  0040_web_prototype_sessions.sql; do
  case "${migration}" in
    0038_chickenbro_simc_platform_foundation.sql) migration_id='0038_chickenbro_simc_platform_foundation' ;;
    0039_wechat_web_login_sessions.sql) migration_id='0039_wechat_web_login_sessions' ;;
    0040_web_prototype_sessions.sql) migration_id='0040_web_prototype_sessions' ;;
    *) die_remote "unknown v2 migration: ${migration}" ;;
  esac
  if migration_is_applied "${migration_id}"; then
    printf 'skipped_migration=%s reason=already-recorded\n' "${migration_id}" >>"${BACKUP_DIR}/migration.log"
    continue
  fi
  apply_v2_migration "${REMOTE_MIGRATION_DIR}/${migration}" >>"${BACKUP_DIR}/migration.log"
done

install -d -m 0755 "${WEB_RELEASE_DIR}"
cp -a "${STAGE_DIR}/apps/mini-taro/dist/h5/." "${WEB_RELEASE_DIR}/"
ln -sfn "${WEB_RELEASE_DIR}" "${WEB_CURRENT_LINK}"

install -m 0644 "${STAGE_DIR}/server/wow-v2-api.service" "/etc/systemd/system/${V2_SERVICE}.service"
install -m 0644 "${STAGE_DIR}/server/wow-v2-worker.service" "/etc/systemd/system/${V2_WORKER_SERVICE}.service"
install -m 0644 "${STAGE_DIR}/server/wow-v2-web.nginx" "${NGINX_SITE}"
ln -sfn "${NGINX_SITE}" "${NGINX_LINK}"
nginx -t
systemctl daemon-reload
systemctl enable --now "${V2_SERVICE}" "${V2_WORKER_SERVICE}"
systemctl reload nginx

wait_for_http 'http://127.0.0.1:8790/health'
wait_for_http 'http://127.0.0.1:8790/api/v2/health/readiness'
wait_for_worker
wait_for_http 'https://www.chickenbro.cloud/' 'www.chickenbro.cloud:443:127.0.0.1'
curl -fsS --max-time 15 https://api.chickenbro.cloud/health >/dev/null
curl -fsS --max-time 15 https://api.chickenbro.cloud/api/data/health >/dev/null
PROTOTYPE_BODY="$(mktemp)"
PROTOTYPE_STATUS="$(curl -sS --max-time 15 -o "${PROTOTYPE_BODY}" -w '%{http_code}' --resolve www.chickenbro.cloud:443:127.0.0.1 -X POST -H 'Content-Type: application/json' https://www.chickenbro.cloud/api/v2/prototype/sessions || true)"
[[ "${PROTOTYPE_STATUS}" == "201" ]] || die_remote "prototype session creation returned ${PROTOTYPE_STATUS}"
grep -q '"mode"[[:space:]]*:[[:space:]]*"prototype"' "${PROTOTYPE_BODY}" || die_remote 'prototype session response did not contain mode=prototype'
! grep -Eq '"(userId|user_id|ownerId|owner_id)"[[:space:]]*:' "${PROTOTYPE_BODY}" || die_remote 'prototype session leaked an owner identifier'
rm -f "${PROTOTYPE_BODY}"
ME_BODY="$(mktemp)"
ME_STATUS="$(curl -sS --max-time 15 -o "${ME_BODY}" -w '%{http_code}' --resolve www.chickenbro.cloud:443:127.0.0.1 https://www.chickenbro.cloud/api/v2/me || true)"
[[ "${ME_STATUS}" == "401" ]] || die_remote "unauthenticated /api/v2/me returned ${ME_STATUS}"
grep -q 'AUTH_REQUIRED' "${ME_BODY}" || die_remote 'unauthenticated /api/v2/me did not return AUTH_REQUIRED'
rm -f "${ME_BODY}"
printf '%s\n' "${RELEASE_ID}" > "${V2_BACKUP_ROOT}/${RUN_ID}/candidate-verified"
rm -f "${PACKAGE_PATH}"
trap - EXIT
echo "candidate_verified=${RELEASE_ID}"
REMOTE_DEPLOY

echo "v2 candidate deployed and smoke-verified; backup run is ${V2_BACKUP_ROOT}/${RUN_ID}"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
REMOTE_DIR="${WOW_LIGHTHOUSE_DIR:-/opt/wow-mini-program}"
V2_SERVICE="wow-v2-api"
V2_ENV_FILE="/etc/wow-v2-api.env"
NGINX_SITE="/etc/nginx/sites-available/wow-v2-web"
NGINX_LINK="/etc/nginx/sites-enabled/wow-v2-web"
WEB_ROOT="/var/www/chickenbro-web"
TLS_CERT="/etc/nginx/ssl/api.chickenbro.cloud/api.chickenbro.cloud_bundle.pem"
TLS_KEY="/etc/nginx/ssl/api.chickenbro.cloud/api.chickenbro.cloud.key"
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
validate_value V2_ENV_FILE "${V2_ENV_FILE}" '^/[A-Za-z0-9_./-]+$'
validate_value RELEASE_ID "${RELEASE_ID}" '^[A-Za-z0-9_.-]+$'
validate_value RUN_ID "${RUN_ID}" '^[A-Za-z0-9_.-]+$'
reject_path_traversal REMOTE_DIR "${REMOTE_DIR}"
reject_path_traversal V2_ENV_FILE "${V2_ENV_FILE}"

[[ -f "${REPO_ROOT}/server/wow-v2-api.service" ]] || die 'missing v2 systemd template'
[[ -f "${REPO_ROOT}/server/wow-v2-web.nginx" ]] || die 'missing v2 nginx template'
[[ -f "${REPO_ROOT}/server/migrations/postgres/0039_wechat_web_login_sessions.sql" ]] || die 'missing v2 migration'
[[ -f "${REPO_ROOT}/server/requirements-v2.txt" ]] || die 'missing v2 requirements'
[[ -d "${REPO_ROOT}/server/app" ]] || die 'missing v2 application source'
[[ -f "${REPO_ROOT}/apps/mini-taro/dist/h5/index.html" ]] || die 'build H5 before candidate deployment'
grep -q '^EnvironmentFile=-/etc/wow-v2-api.env$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use the isolated environment file'
grep -q '^Environment=WOW_DATABASE_RUNTIME=postgres_only$' "${REPO_ROOT}/server/wow-v2-api.service" || die 'v2 service must use PostgreSQL-only runtime'

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
  "RUN_ID=${RUN_ID}"
  "RELEASE_ID=${RELEASE_ID}"
  "REMOTE_DIR=${REMOTE_DIR}"
  "V2_SERVICE=${V2_SERVICE}"
  "V2_ENV_FILE=${V2_ENV_FILE}"
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

for command_name in python3 psql pg_dump nginx systemctl tar curl openssl; do
  command -v "${command_name}" >/dev/null 2>&1 || die_remote "missing command: ${command_name}"
done

[[ -f "${V2_ENV_FILE}" ]] || die_remote "missing ${V2_ENV_FILE}; create it with mode 0600"
[[ "$(stat -c '%a' "${V2_ENV_FILE}")" == "600" ]] || die_remote "${V2_ENV_FILE} must have mode 0600"
[[ -r "${TLS_CERT}" && -r "${TLS_KEY}" ]] || die_remote 'configured TLS certificate paths are not readable'

if ! openssl x509 -in "${TLS_CERT}" -noout -ext subjectAltName 2>/dev/null | grep -Eq 'DNS:www\.chickenbro\.cloud([,[:space:]]|$)'; then
  die_remote 'configured TLS certificate does not cover www.chickenbro.cloud'
fi

set +u
set -a
source "${V2_ENV_FILE}"
set +a
set -u
[[ "${WOW_DATABASE_URL:-}" == postgresql://* || "${WOW_DATABASE_URL:-}" == postgres://* ]] || die_remote 'v2 env must provide a PostgreSQL WOW_DATABASE_URL'

BACKUP_DIR="${V2_BACKUP_ROOT}/${RUN_ID}"
[[ ! -e "${BACKUP_DIR}" ]] || die_remote "backup run already exists: ${RUN_ID}"
install -d -m 0700 "${BACKUP_DIR}"

tar --ignore-failed-read --format=posix -czf "${BACKUP_DIR}/v2-paths.tgz" -C / \
  "${REMOTE_DIR#/}/server/app" \
  "${REMOTE_DIR#/}/server/requirements-v2.txt" \
  "${REMOTE_DIR#/}/server/migrations/postgres/0039_wechat_web_login_sessions.sql" \
  "etc/systemd/system/${V2_SERVICE}.service" \
  "etc/nginx/sites-available/wow-v2-web" \
  "etc/nginx/sites-enabled/wow-v2-web" \
  "var/www/chickenbro-web"

cp --preserve=mode,ownership "${V2_ENV_FILE}" "${BACKUP_DIR}/wow-v2-api.env"
if [[ -f "/etc/systemd/system/${V2_SERVICE}.service" ]]; then
  cp --preserve=mode,ownership "/etc/systemd/system/${V2_SERVICE}.service" "${BACKUP_DIR}/v2-api.service"
fi
if [[ -f "${NGINX_SITE}" ]]; then
  cp --preserve=mode,ownership "${NGINX_SITE}" "${BACKUP_DIR}/wow-v2-web.nginx"
fi
if [[ -L "${NGINX_LINK}" ]]; then
  readlink "${NGINX_LINK}" > "${BACKUP_DIR}/nginx-link-target"
elif [[ -e "${NGINX_LINK}" ]]; then
  cp --preserve=mode,ownership "${NGINX_LINK}" "${BACKUP_DIR}/nginx-link-file"
fi
pg_dump --format=custom --file="${BACKUP_DIR}/postgres-target.dump" --dbname="${WOW_DATABASE_URL}" >/dev/null
printf '%s\n' "${RELEASE_ID}" > "${BACKUP_DIR}/release-id"
printf '%s\n' "${V2_ENV_FILE}" > "${BACKUP_DIR}/environment-path"
printf '%s\n' "backup_complete" > "${BACKUP_DIR}/READY"
echo "backup=${BACKUP_DIR}"
REMOTE_PREFLIGHT

PACKAGE_PATH="$(mktemp -t chickenbro-v2.XXXXXX.tar.gz)"
SOURCE_LIST="$(mktemp -t chickenbro-v2-files.XXXXXX)"
REMOTE_PACKAGE_PATH="/tmp/chickenbro-v2-${RUN_ID}.tar.gz"
trap 'rm -f "${PACKAGE_PATH}" "${SOURCE_LIST}"' EXIT

git -C "${REPO_ROOT}" ls-files -z -- \
  server/app \
  server/migrations/postgres/0039_wechat_web_login_sessions.sql \
  server/requirements-v2.txt \
  server/wow-v2-api.service \
  server/wow-v2-web.nginx > "${SOURCE_LIST}"
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
  if [[ -f "${BACKUP_DIR}/v2-api.service" ]]; then
    install -m 0644 "${BACKUP_DIR}/v2-api.service" "/etc/systemd/system/${V2_SERVICE}.service"
  else
    rm -f "/etc/systemd/system/${V2_SERVICE}.service"
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
  systemctl daemon-reload >/dev/null 2>&1 || true
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
  fi
  rm -f "${PACKAGE_PATH}"
  echo "v2 candidate failed; named v2 assets restored; PostgreSQL backup preserved at ${BACKUP_DIR}" >&2
  exit "${exit_code}"
}
trap rollback_v2 EXIT

[[ "$(sha256sum "${PACKAGE_PATH}" | awk '{print $1}')" == "${PACKAGE_SHA256}" ]] || die_remote 'candidate package checksum mismatch'
[[ ! -e "${STAGE_DIR}" ]] || die_remote "staging run already exists: ${RUN_ID}"
install -d -m 0750 "${STAGE_DIR}"
tar -xzf "${PACKAGE_PATH}" -C "${STAGE_DIR}"

install -d -m 0755 "${REMOTE_APP_ROOT}" "${REMOTE_MIGRATION_DIR}"
cp -a "${STAGE_DIR}/server/app/." "${REMOTE_APP_ROOT}/"
install -m 0644 "${STAGE_DIR}/server/migrations/postgres/0039_wechat_web_login_sessions.sql" "${REMOTE_MIGRATION_DIR}/0039_wechat_web_login_sessions.sql"
install -m 0644 "${STAGE_DIR}/server/requirements-v2.txt" "${REMOTE_DIR}/server/requirements-v2.txt"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  python3 -m venv "${VENV_DIR}"
fi
PIP_DISABLE_PIP_VERSION_CHECK=1 "${VENV_DIR}/bin/pip" install --no-input --requirement "${REMOTE_DIR}/server/requirements-v2.txt" >/dev/null

set +u
set -a
source "${V2_ENV_FILE}"
set +a
set -u
psql --dbname="${WOW_DATABASE_URL}" --set ON_ERROR_STOP=1 --single-transaction --file="${REMOTE_MIGRATION_DIR}/0039_wechat_web_login_sessions.sql" >"${BACKUP_DIR}/migration.log"

install -d -m 0755 "${WEB_RELEASE_DIR}"
cp -a "${STAGE_DIR}/apps/mini-taro/dist/h5/." "${WEB_RELEASE_DIR}/"
ln -sfn "${WEB_RELEASE_DIR}" "${WEB_CURRENT_LINK}"

install -m 0644 "${STAGE_DIR}/server/wow-v2-api.service" "/etc/systemd/system/${V2_SERVICE}.service"
install -m 0644 "${STAGE_DIR}/server/wow-v2-web.nginx" "${NGINX_SITE}"
ln -sfn "${NGINX_SITE}" "${NGINX_LINK}"
nginx -t
systemctl daemon-reload
systemctl enable --now "${V2_SERVICE}"
systemctl reload nginx

curl -fsS --max-time 15 http://127.0.0.1:8790/health >/dev/null
curl -fsS --max-time 15 http://127.0.0.1:8790/api/v2/health/readiness >/dev/null
curl -fsS --max-time 15 --resolve www.chickenbro.cloud:443:127.0.0.1 https://www.chickenbro.cloud/ >/dev/null
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

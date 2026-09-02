#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

REMOTE_HOST="${WOW_LIGHTHOUSE_HOST:-124.223.51.33}"
REMOTE_USER="${WOW_LIGHTHOUSE_USER:-ubuntu}"
CANDIDATE_REMOTE_DIR="${WOW_V2_CANDIDATE_REMOTE_DIR:-/opt/wow-mini-program-candidate}"
CANDIDATE_DB="${WOW_V2_CANDIDATE_DB:-wow_v2_candidate}"
CANDIDATE_SERVICE="wow-v2-api-candidate"
CANDIDATE_PORT="8791"
CANDIDATE_ENV_FILE="/etc/wow-v2-api-candidate.env"
CANDIDATE_PGPASSFILE="/etc/wow-v2-api-candidate.pgpass"
LEGACY_V2_ENV_FILE="/etc/wow-v2-api.env"
NGINX_SITE="/etc/nginx/sites-available/wow-v2-web"
API_NGINX_SITE="/etc/nginx/sites-enabled/api.chickenbro.cloud"
WEB_ROOT="/var/www/chickenbro-web-candidate"
BACKUP_ROOT="/var/backups/wow-v2-candidate"
V2_RUNTIME_PYTHON="/opt/wow-mini-program/.venv-v2/bin/python"
RELEASE_ID="${WOW_V2_CANDIDATE_RELEASE_ID:-$(git -C "${REPO_ROOT}" rev-parse --short=12 HEAD)}"
RUN_ID="${WOW_V2_CANDIDATE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-${RELEASE_ID}}"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=15)

die() {
  echo "deploy_web_v2_candidate: $*" >&2
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
validate_value CANDIDATE_REMOTE_DIR "${CANDIDATE_REMOTE_DIR}" '^/[A-Za-z0-9_./-]+$'
validate_value CANDIDATE_DB "${CANDIDATE_DB}" '^wow_v2_candidate(_[A-Za-z0-9_]+)?$'
validate_value RELEASE_ID "${RELEASE_ID}" '^[A-Za-z0-9_.-]+$'
validate_value RUN_ID "${RUN_ID}" '^[A-Za-z0-9_.-]+$'
[[ "${CANDIDATE_REMOTE_DIR}" == '/opt/wow-mini-program-candidate' ]] || die 'CANDIDATE_REMOTE_DIR is fixed to the isolated candidate root'
reject_path_traversal CANDIDATE_REMOTE_DIR "${CANDIDATE_REMOTE_DIR}"

for required_file in \
  "${REPO_ROOT}/server/app" \
  "${REPO_ROOT}/server/codex_worker.py" \
  "${REPO_ROOT}/server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql" \
  "${REPO_ROOT}/server/migrations/postgres/0039_wechat_web_login_sessions.sql" \
  "${REPO_ROOT}/server/migrations/postgres/0040_web_prototype_sessions.sql" \
  "${REPO_ROOT}/server/wow-v2-api-candidate.service" \
  "${REPO_ROOT}/server/wow-v2-candidate.locations.nginx" \
  "${REPO_ROOT}/apps/mini-taro/dist/h5/index.html"; do
  [[ -e "${required_file}" ]] || die "missing candidate input: ${required_file}"
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

REMOTE_ENV=(
  "REMOTE_USER=${REMOTE_USER}"
  "RUN_ID=${RUN_ID}"
  "RELEASE_ID=${RELEASE_ID}"
  "CANDIDATE_REMOTE_DIR=${CANDIDATE_REMOTE_DIR}"
  "CANDIDATE_DB=${CANDIDATE_DB}"
  "CANDIDATE_SERVICE=${CANDIDATE_SERVICE}"
  "CANDIDATE_PORT=${CANDIDATE_PORT}"
  "CANDIDATE_ENV_FILE=${CANDIDATE_ENV_FILE}"
  "CANDIDATE_PGPASSFILE=${CANDIDATE_PGPASSFILE}"
  "LEGACY_V2_ENV_FILE=${LEGACY_V2_ENV_FILE}"
  "NGINX_SITE=${NGINX_SITE}"
  "API_NGINX_SITE=${API_NGINX_SITE}"
  "WEB_ROOT=${WEB_ROOT}"
  "BACKUP_ROOT=${BACKUP_ROOT}"
  "V2_RUNTIME_PYTHON=${V2_RUNTIME_PYTHON}"
)

remote_env_args() {
  local item
  for item in "${REMOTE_ENV[@]}"; do
    printf '%q ' "${item}"
  done
}

echo "Checking isolated v2 candidate prerequisites on ${SSH_TARGET}"
ssh_remote "$(remote_env_args) sudo -E bash -s" <<'REMOTE_PREFLIGHT'
set -euo pipefail

die_remote() {
  echo "deploy_web_v2_candidate remote: $*" >&2
  exit 1
}

for command_name in python3 psql pg_dump createdb nginx systemctl tar curl sha256sum; do
  command -v "${command_name}" >/dev/null 2>&1 || die_remote "missing command: ${command_name}"
done

[[ -f "${LEGACY_V2_ENV_FILE}" ]] || die_remote "missing ${LEGACY_V2_ENV_FILE}"
[[ "$(stat -c '%a' "${LEGACY_V2_ENV_FILE}")" == "600" ]] || die_remote "${LEGACY_V2_ENV_FILE} must have mode 0600"
[[ -x "${V2_RUNTIME_PYTHON}" ]] || die_remote "existing v2 virtualenv is missing: ${V2_RUNTIME_PYTHON}"
[[ -f "${NGINX_SITE}" ]] || die_remote "existing v2 nginx site is missing: ${NGINX_SITE}"
[[ -f "${API_NGINX_SITE}" ]] || die_remote "existing API nginx site is missing: ${API_NGINX_SITE}"
grep -q 'server_name[[:space:]]\+www\.chickenbro\.cloud' "${NGINX_SITE}" || die_remote 'v2 nginx site is not the expected www host'
grep -q 'server_name[[:space:]]\+api\.chickenbro\.cloud' "${API_NGINX_SITE}" || die_remote 'API nginx site is not the expected api host'
grep -q 'location[[:space:]]\+\^~[[:space:]]\+/api/v2/' "${NGINX_SITE}" || die_remote 'existing v2 api location is missing'
grep -q 'location[[:space:]]\+/' "${NGINX_SITE}" || die_remote 'existing v2 static location is missing'
grep -q 'location[[:space:]]\+/' "${API_NGINX_SITE}" || die_remote 'existing API location is missing'

set +u
set -a
. "${LEGACY_V2_ENV_FILE}"
set +a
set -u
[[ -n "${WOW_DATABASE_URL:-}" ]] || die_remote 'legacy v2 env has no database URL'
[[ -n "${WOW_WECHAT_APPID:-}" && -n "${WOW_WECHAT_SECRET:-}" ]] || die_remote 'legacy v2 env has no WeChat credentials'
[[ -n "${PGPASSFILE:-}" && -r "${PGPASSFILE}" ]] || die_remote 'legacy v2 PGPASSFILE is missing or unreadable'
grep -Eq '^127\.0\.0\.1:5432:wow_test:wow_app:' "${PGPASSFILE}" || die_remote 'legacy v2 PGPASSFILE has no wow_test application entry'
CURRENT_DATABASE="$(psql --dbname="${WOW_DATABASE_URL}" --tuples-only --no-align --command='select current_database()' | tr -d '[:space:]')"
[[ "${CURRENT_DATABASE}" == 'wow_test' ]] || die_remote "refusing unexpected v2 database: ${CURRENT_DATABASE}"
DEV_DATABASE_EXISTS="$(sudo -n -u postgres psql -Atc "select 1 from pg_database where datname = 'wow_dev'")"
[[ "${DEV_DATABASE_EXISTS}" == '1' ]] || die_remote 'missing required empty wow_dev candidate template database'

DB_EXISTS="$(sudo -n -u postgres psql -Atc "select 1 from pg_database where datname = '${CANDIDATE_DB}'")"
BACKUP_DIR="${BACKUP_ROOT}/${RUN_ID}"
[[ ! -e "${BACKUP_DIR}" ]] || die_remote "candidate backup run already exists: ${RUN_ID}"
install -d -m 0700 "${BACKUP_DIR}"
cp --preserve=mode,ownership "${NGINX_SITE}" "${BACKUP_DIR}/wow-v2-web.nginx"
cp --preserve=mode,ownership "${API_NGINX_SITE}" "${BACKUP_DIR}/api.chickenbro.cloud.nginx"
if [[ -f "/etc/systemd/system/${CANDIDATE_SERVICE}.service" ]]; then
  cp --preserve=mode,ownership "/etc/systemd/system/${CANDIDATE_SERVICE}.service" "${BACKUP_DIR}/candidate.service"
  printf '%s\n' 'present' > "${BACKUP_DIR}/candidate-service-state"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/candidate-service-state"
fi
if [[ -f "${CANDIDATE_ENV_FILE}" ]]; then
  cp --preserve=mode,ownership "${CANDIDATE_ENV_FILE}" "${BACKUP_DIR}/candidate.env"
  printf '%s\n' 'present' > "${BACKUP_DIR}/candidate-env-state"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/candidate-env-state"
fi
if [[ -f "${CANDIDATE_PGPASSFILE}" ]]; then
  cp --preserve=mode,ownership "${CANDIDATE_PGPASSFILE}" "${BACKUP_DIR}/candidate.pgpass"
  printf '%s\n' 'present' > "${BACKUP_DIR}/candidate-pgpass-state"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/candidate-pgpass-state"
fi
if [[ -d "${CANDIDATE_REMOTE_DIR}" ]]; then
  tar --format=posix -czf "${BACKUP_DIR}/candidate-source.tgz" -C "$(dirname "${CANDIDATE_REMOTE_DIR}")" "$(basename "${CANDIDATE_REMOTE_DIR}")"
  printf '%s\n' 'present' > "${BACKUP_DIR}/candidate-source-state"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/candidate-source-state"
fi
if [[ -L "${WEB_ROOT}/current" ]]; then
  readlink "${WEB_ROOT}/current" > "${BACKUP_DIR}/web-current-target"
  printf '%s\n' 'symlink' > "${BACKUP_DIR}/web-current-state"
elif [[ -e "${WEB_ROOT}/current" ]]; then
  die_remote "refusing non-symlink candidate web current: ${WEB_ROOT}/current"
else
  printf '%s\n' 'absent' > "${BACKUP_DIR}/web-current-state"
fi
if [[ "${DB_EXISTS}" == '1' ]]; then
  printf '%s\n' 'existing' > "${BACKUP_DIR}/candidate-database-state"
  # The remote preflight already runs as root. Let the postgres process stream
  # the dump, while the root shell creates the file inside the root-only run
  # directory; otherwise postgres cannot traverse BACKUP_DIR (0700 root:root).
  sudo -n -u postgres pg_dump --format=custom --dbname="${CANDIDATE_DB}" > "${BACKUP_DIR}/candidate-database.dump"
  chmod 0600 "${BACKUP_DIR}/candidate-database.dump"
  printf '%s\n' "${BACKUP_DIR}/candidate-database.dump" > "${BACKUP_DIR}/candidate-database-dump-path"
else
  printf '%s\n' 'new_from_wow_dev' > "${BACKUP_DIR}/candidate-database-state"
fi
printf '%s\n' "${CANDIDATE_DB}" > "${BACKUP_DIR}/candidate-database-name"
printf '%s\n' "${CANDIDATE_SERVICE}" > "${BACKUP_DIR}/candidate-service-name"
printf '%s\n' 'backup_complete' > "${BACKUP_DIR}/READY"
echo "backup=${BACKUP_DIR} database_state=${DB_EXISTS:-absent}"
REMOTE_PREFLIGHT

PACKAGE_PATH="$(mktemp -t chickenbro-v2-candidate.XXXXXX.tar.gz)"
SOURCE_LIST="$(mktemp -t chickenbro-v2-candidate-files.XXXXXX)"
REMOTE_PACKAGE_PATH="/tmp/chickenbro-v2-candidate-${RUN_ID}.tar.gz"
trap 'rm -f "${PACKAGE_PATH}" "${SOURCE_LIST}"' EXIT

git -C "${REPO_ROOT}" ls-files -z --cached --others --exclude-standard -- \
  server/app \
  server/codex_worker.py \
  server/migrations/postgres/0038_chickenbro_simc_platform_foundation.sql \
  server/migrations/postgres/0039_wechat_web_login_sessions.sql \
  server/migrations/postgres/0040_web_prototype_sessions.sql \
  server/wow-v2-api-candidate.service \
  server/wow-v2-candidate.locations.nginx \
  server/wow-v2-candidate-api.locations.nginx > "${SOURCE_LIST}"
printf '%s\0' 'apps/mini-taro/dist/h5' >> "${SOURCE_LIST}"
COPYFILE_DISABLE=1 tar --null --files-from="${SOURCE_LIST}" --format=ustar -czf "${PACKAGE_PATH}" -C "${REPO_ROOT}"

PACKAGE_SHA256="$(shasum -a 256 "${PACKAGE_PATH}" | awk '{print $1}')"
scp_remote "${PACKAGE_PATH}" "${SSH_TARGET}:${REMOTE_PACKAGE_PATH}"

echo "Installing isolated Web login candidate ${RELEASE_ID}"
ssh_remote "$(remote_env_args) PACKAGE_PATH='${REMOTE_PACKAGE_PATH}' PACKAGE_SHA256='${PACKAGE_SHA256}' sudo -E bash -s" <<'REMOTE_DEPLOY'
set -euo pipefail

die_remote() {
  echo "deploy_web_v2_candidate remote: $*" >&2
  exit 1
}

BACKUP_DIR="${BACKUP_ROOT}/${RUN_ID}"
STAGE_DIR="/opt/wow-v2-candidate-staging/${RUN_ID}"
WEB_RELEASE_DIR="${WEB_ROOT}/releases/${RUN_ID}"
WEB_CURRENT_LINK="${WEB_ROOT}/current"
CODE_NEW_DIR="${CANDIDATE_REMOTE_DIR}.new-${RUN_ID}"

rollback_candidate() {
  local exit_code=$?
  if [[ "${exit_code}" -eq 0 ]]; then
    rm -f "${PACKAGE_PATH}"
    rm -rf "${STAGE_DIR}" "${CANDIDATE_REMOTE_DIR}.new-${RUN_ID}"
    exit 0
  fi
  set +e
  systemctl stop "${CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
  if [[ -f "${BACKUP_DIR}/candidate.service" ]]; then
    install -m 0644 "${BACKUP_DIR}/candidate.service" "/etc/systemd/system/${CANDIDATE_SERVICE}.service"
  else
    rm -f "/etc/systemd/system/${CANDIDATE_SERVICE}.service"
    rm -f "/etc/systemd/system/multi-user.target.wants/${CANDIDATE_SERVICE}.service"
  fi
  if [[ -f "${BACKUP_DIR}/candidate.env" ]]; then
    install -o root -g root -m 0600 "${BACKUP_DIR}/candidate.env" "${CANDIDATE_ENV_FILE}"
  else
    rm -f "${CANDIDATE_ENV_FILE}"
  fi
  if [[ -f "${BACKUP_DIR}/candidate.pgpass" ]]; then
    install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${BACKUP_DIR}/candidate.pgpass" "${CANDIDATE_PGPASSFILE}"
  else
    rm -f "${CANDIDATE_PGPASSFILE}"
  fi
  if [[ -f "${BACKUP_DIR}/wow-v2-web.nginx" ]]; then
    install -m 0644 "${BACKUP_DIR}/wow-v2-web.nginx" "${NGINX_SITE}"
  fi
  if [[ -f "${BACKUP_DIR}/api.chickenbro.cloud.nginx" ]]; then
    install -m 0644 "${BACKUP_DIR}/api.chickenbro.cloud.nginx" "${API_NGINX_SITE}"
  fi
  if [[ -f "${BACKUP_DIR}/web-current-target" ]]; then
    OLD_WEB_TARGET="$(cat "${BACKUP_DIR}/web-current-target")"
    ln -sfn "${OLD_WEB_TARGET}" "${WEB_CURRENT_LINK}"
  elif [[ -f "${BACKUP_DIR}/web-current-state" ]] && grep -qx 'absent' "${BACKUP_DIR}/web-current-state"; then
    rm -f "${WEB_CURRENT_LINK}"
  fi
  rm -rf "${WEB_RELEASE_DIR}"
  if [[ -f "${BACKUP_DIR}/candidate-source.tgz" ]]; then
    rm -rf "${CANDIDATE_REMOTE_DIR}"
    tar -xzf "${BACKUP_DIR}/candidate-source.tgz" -C "$(dirname "${CANDIDATE_REMOTE_DIR}")" >/dev/null 2>&1 || true
  else
    rm -rf "${CANDIDATE_REMOTE_DIR}"
  fi
  rm -rf "${CANDIDATE_REMOTE_DIR}.new-${RUN_ID}" "${STAGE_DIR}"
  systemctl daemon-reload >/dev/null 2>&1 || true
  if [[ -f "${BACKUP_DIR}/candidate.service" ]]; then
    systemctl start "${CANDIDATE_SERVICE}" >/dev/null 2>&1 || true
  fi
  if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1 || true
  fi
  rm -f "${PACKAGE_PATH}"
  echo "candidate failed; candidate assets restored; database backup preserved at ${BACKUP_DIR}" >&2
  exit "${exit_code}"
}
trap rollback_candidate EXIT

[[ "$(sha256sum "${PACKAGE_PATH}" | awk '{print $1}')" == "${PACKAGE_SHA256}" ]] || die_remote 'candidate package checksum mismatch'
[[ ! -e "${STAGE_DIR}" ]] || die_remote "candidate staging run already exists: ${RUN_ID}"
install -d -m 0755 "${STAGE_DIR}"
tar -xzf "${PACKAGE_PATH}" -C "${STAGE_DIR}"

DB_EXISTS="$(sudo -n -u postgres psql -Atc "select 1 from pg_database where datname = '${CANDIDATE_DB}'")"
if [[ "${DB_EXISTS}" != '1' ]]; then
  sudo -n -u postgres createdb --template=wow_dev --owner=wow_migrator "${CANDIDATE_DB}"
fi
sudo -n -u postgres psql -v ON_ERROR_STOP=1 -Atc "GRANT CONNECT ON DATABASE \"${CANDIDATE_DB}\" TO wow_app"

set +u
set -a
. "${LEGACY_V2_ENV_FILE}"
set +a
set -u
PGPASS_TMP="$(mktemp)"
if ! awk -F: -v candidate_database="${CANDIDATE_DB}" 'BEGIN { OFS = FS } $1 == "127.0.0.1" && $2 == "5432" && $3 == "wow_test" && $4 == "wow_app" { $3 = candidate_database; print; found = 1 } END { exit found ? 0 : 1 }' "${PGPASSFILE}" > "${PGPASS_TMP}"; then
  rm -f "${PGPASS_TMP}"
  die_remote 'legacy v2 PGPASSFILE has no usable wow_test application entry'
fi
install -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0600 "${PGPASS_TMP}" "${CANDIDATE_PGPASSFILE}"
rm -f "${PGPASS_TMP}"
CANDIDATE_DSN="$(SOURCE_DSN="${WOW_DATABASE_URL}" CANDIDATE_DATABASE="${CANDIDATE_DB}" python3 - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit

source = urlsplit(os.environ["SOURCE_DSN"])
print(urlunsplit((source.scheme, source.netloc, "/" + os.environ["CANDIDATE_DATABASE"], source.query, source.fragment)))
PY
)"

for migration in \
  0038_chickenbro_simc_platform_foundation.sql \
  0039_wechat_web_login_sessions.sql \
  0040_web_prototype_sessions.sql; do
  case "${migration}" in
    0038_chickenbro_simc_platform_foundation.sql) migration_id='0038_chickenbro_simc_platform_foundation' ;;
    0039_wechat_web_login_sessions.sql) migration_id='0039_wechat_web_login_sessions' ;;
    0040_web_prototype_sessions.sql) migration_id='0040_web_prototype_sessions' ;;
    *) die_remote "unknown migration: ${migration}" ;;
  esac
  applied="$(sudo -n -u postgres psql -d "${CANDIDATE_DB}" -Atc "select 1 from ops.schema_migrations where id = '${migration_id}'" | tr -d '[:space:]')"
  if [[ "${applied}" != '1' ]]; then
    sudo -n -u postgres psql -d "${CANDIDATE_DB}" --set ON_ERROR_STOP=1 --single-transaction \
      --command='SET ROLE wow_migrator' --file="${STAGE_DIR}/server/migrations/postgres/${migration}" \
      >>"${BACKUP_DIR}/migration.log"
  fi
done

install -d -o "${REMOTE_USER}" -g "${REMOTE_USER}" -m 0750 "${CODE_NEW_DIR}/server/app"
cp -a "${STAGE_DIR}/server/app/." "${CODE_NEW_DIR}/server/app/"
install -m 0644 "${STAGE_DIR}/server/codex_worker.py" "${CODE_NEW_DIR}/server/codex_worker.py"
chown -R "${REMOTE_USER}:${REMOTE_USER}" "${CODE_NEW_DIR}"
if [[ -e "${CANDIDATE_REMOTE_DIR}" ]]; then
  mv "${CANDIDATE_REMOTE_DIR}" "${BACKUP_DIR}/candidate-source-old-${RUN_ID}"
fi
mv "${CANDIDATE_REMOTE_DIR}.new-${RUN_ID}" "${CANDIDATE_REMOTE_DIR}"

install -d -m 0755 "${WEB_RELEASE_DIR}"
cp -a "${STAGE_DIR}/apps/mini-taro/dist/h5/." "${WEB_RELEASE_DIR}/"
ln -sfn "${WEB_RELEASE_DIR}" "${WEB_CURRENT_LINK}"

ENV_TMP="$(mktemp)"
printf 'PGPASSFILE=%s\n' "${PGPASSFILE:-}" > "${ENV_TMP}"
printf 'WOW_DATABASE_URL=%s\n' "${CANDIDATE_DSN}" >> "${ENV_TMP}"
printf 'WOW_WECHAT_APPID=%s\n' "${WOW_WECHAT_APPID}" >> "${ENV_TMP}"
printf 'WOW_WECHAT_SECRET=%s\n' "${WOW_WECHAT_SECRET}" >> "${ENV_TMP}"
printf 'WOW_WEB_ORIGIN=https://www.chickenbro.cloud\n' >> "${ENV_TMP}"
printf 'WOW_WEB_COOKIE_NAME=__Host-wow_v2_candidate\n' >> "${ENV_TMP}"
printf 'WOW_WECHAT_PAGE=pages/auth/web-login-confirm\n' >> "${ENV_TMP}"
printf 'WOW_WECHAT_ENV_VERSION=trial\n' >> "${ENV_TMP}"
printf 'WOW_WECHAT_CHECK_PATH=0\n' >> "${ENV_TMP}"
install -o root -g root -m 0600 "${ENV_TMP}" "${CANDIDATE_ENV_FILE}"
rm -f "${ENV_TMP}"

install_marked_nginx_locations() {
  local site="$1"
  local snippet_path="$2"
  local location_role="$3"
  python3 - "${site}" "${snippet_path}" "${location_role}" <<'PY'
from pathlib import Path
import os
import re
import stat
import sys
import tempfile

site = Path(sys.argv[1])
snippet_path = Path(sys.argv[2])
location_role = sys.argv[3]
text = site.read_text(encoding="utf-8")
snippet = snippet_path.read_text(encoding="utf-8").strip()
begin = "# BEGIN CHICKENBRO V2 CANDIDATE"
end = "# END CHICKENBRO V2 CANDIDATE"
if begin in text or end in text:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit("candidate nginx markers are ambiguous")
    text = re.sub(
        rf"{re.escape(begin)}.*?{re.escape(end)}",
        snippet,
        text,
        count=1,
        flags=re.DOTALL,
    )
else:
    needles = {
        "www-static": "    location / {\n        try_files $uri $uri/ /index.html;\n    }",
        "api-proxy": "    location / {\n        proxy_pass http://127.0.0.1:8787;\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        proxy_connect_timeout 5s;\n        proxy_read_timeout 60s;\n    }",
    }
    if location_role not in needles:
        raise SystemExit(f"unknown existing nginx location role: {location_role}")
    needle = needles[location_role]
    if text.count(needle) != 1:
        raise SystemExit(f"expected exact existing {location_role} location was not found")
    text = text.replace(needle, f"{snippet}\n\n{needle}", 1)
mode = stat.S_IMODE(site.stat().st_mode)
file_descriptor, temporary_name = tempfile.mkstemp(
    prefix=f".{site.name}.candidate-",
    dir=str(site.parent),
    text=True,
)
try:
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(temporary_name, mode)
    os.replace(temporary_name, site)
except BaseException:
    try:
        os.unlink(temporary_name)
    except FileNotFoundError:
        pass
    raise
PY
}

install_marked_nginx_locations "${NGINX_SITE}" "${STAGE_DIR}/server/wow-v2-candidate.locations.nginx" www-static
install_marked_nginx_locations "${API_NGINX_SITE}" "${STAGE_DIR}/server/wow-v2-candidate-api.locations.nginx" api-proxy

install -o root -g root -m 0644 \
  "${STAGE_DIR}/server/wow-v2-api-candidate.service" \
  "/etc/systemd/system/${CANDIDATE_SERVICE}.service"
nginx -t
systemctl daemon-reload
systemctl enable "${CANDIDATE_SERVICE}"
systemctl restart "${CANDIDATE_SERVICE}"
systemctl reload nginx
systemctl is-active --quiet "${CANDIDATE_SERVICE}" || die_remote 'candidate service is not active'

wait_for_http() {
  local url="$1"
  local attempt
  for attempt in {1..20}; do
    if curl -fsS --max-time 15 "${url}" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  die_remote "timed out waiting for ${url}"
}

wait_for_http "http://127.0.0.1:${CANDIDATE_PORT}/health"
wait_for_http "http://127.0.0.1:${CANDIDATE_PORT}/api/v2/health/readiness"
wait_for_http 'https://www.chickenbro.cloud/web-candidate/'
wait_for_http 'https://www.chickenbro.cloud/api/v2-candidate/health/readiness'
wait_for_http 'https://api.chickenbro.cloud/api/v2-candidate/health/readiness'

CANDIDATE_READINESS_BODY="$(mktemp)"
curl -fsS --max-time 15 -o "${CANDIDATE_READINESS_BODY}" https://www.chickenbro.cloud/api/v2-candidate/health/readiness
python3 - "${CANDIDATE_READINESS_BODY}" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
components = payload.get("components", {})
for name in ("database", "wechat_mini"):
    state = components.get(name, {})
    if state.get("status") != "ready":
        raise SystemExit(f"candidate login component is not ready: {name}={state}")
if payload.get("status") not in {"partial", "ready"}:
    raise SystemExit(f"candidate readiness is blocked: {payload.get('status')}")
print(f"candidate_readiness={payload.get('status')} login_scope=ready")
PY
rm -f "${CANDIDATE_READINESS_BODY}"

CANDIDATE_ME_BODY="$(mktemp)"
CANDIDATE_ME_STATUS="$(curl -sS --max-time 15 -o "${CANDIDATE_ME_BODY}" -w '%{http_code}' https://www.chickenbro.cloud/api/v2-candidate/me || true)"
[[ "${CANDIDATE_ME_STATUS}" == '401' ]] || die_remote "candidate unauthenticated /me returned ${CANDIDATE_ME_STATUS}"
grep -q 'AUTH_REQUIRED' "${CANDIDATE_ME_BODY}" || die_remote 'candidate unauthenticated /me did not return AUTH_REQUIRED'
rm -f "${CANDIDATE_ME_BODY}"

API_CANDIDATE_ME_BODY="$(mktemp)"
API_CANDIDATE_ME_STATUS="$(curl -sS --max-time 15 -o "${API_CANDIDATE_ME_BODY}" -w '%{http_code}' https://api.chickenbro.cloud/api/v2-candidate/me || true)"
[[ "${API_CANDIDATE_ME_STATUS}" == '401' ]] || die_remote "API candidate unauthenticated /me returned ${API_CANDIDATE_ME_STATUS}"
grep -q 'AUTH_REQUIRED' "${API_CANDIDATE_ME_BODY}" || die_remote 'API candidate unauthenticated /me did not return AUTH_REQUIRED'
rm -f "${API_CANDIDATE_ME_BODY}"

OLD_V2_ME_BODY="$(mktemp)"
OLD_V2_ME_STATUS="$(curl -sS --max-time 15 -o "${OLD_V2_ME_BODY}" -w '%{http_code}' https://www.chickenbro.cloud/api/v2/me || true)"
[[ "${OLD_V2_ME_STATUS}" == '401' ]] || die_remote "existing /api/v2/me parity check returned ${OLD_V2_ME_STATUS}"
rm -f "${OLD_V2_ME_BODY}"
curl -fsS --max-time 15 https://api.chickenbro.cloud/health >/dev/null
curl -fsS --max-time 15 https://api.chickenbro.cloud/api/data/health >/dev/null

LOG_BODY="$(mktemp)"
journalctl -u "${CANDIDATE_SERVICE}" -n 120 --no-pager > "${LOG_BODY}"
if grep -Eiq 'WOW_WECHAT_SECRET|access_token|openid|unionid|__Host-wow_v2_candidate=' "${LOG_BODY}"; then
  rm -f "${LOG_BODY}"
  die_remote 'candidate journal contains a forbidden credential or identity field'
fi
rm -f "${LOG_BODY}"
printf '%s\n' "${RELEASE_ID}" > "${BACKUP_DIR}/candidate-verified"
rm -f "${PACKAGE_PATH}"
rm -rf "${STAGE_DIR}"
trap - EXIT
echo "candidate_verified=${RELEASE_ID} backup=${BACKUP_DIR} database=${CANDIDATE_DB}"
REMOTE_DEPLOY

echo "isolated v2 login candidate deployed and login-scope smoke-verified; backup run is ${BACKUP_ROOT}/${RUN_ID}"

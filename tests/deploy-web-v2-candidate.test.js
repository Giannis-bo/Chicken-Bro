const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

test('candidate deployment has a separate API service, database and source tree', () => {
  const script = read('server/deploy_web_v2_candidate_lighthouse.sh')
  const service = read('server/wow-v2-api-candidate.service')
  const apiSnippet = read('server/wow-v2-candidate-api.locations.nginx')

  assert.match(script, /wow-v2-api-candidate/)
  assert.match(script, /wow_v2_candidate/)
  assert.match(script, /8791/)
  assert.match(script, /wow-mini-program-candidate/)
  assert.match(script, /API_NGINX_SITE=.*api\.chickenbro\.cloud/)
  assert.match(script, /api\.chickenbro\.cloud\.nginx/)
  assert.match(script, /server\/wow-v2-candidate-api\.locations\.nginx/)
  assert.match(script, /https:\/\/api\.chickenbro\.cloud\/api\/v2-candidate\/health\/readiness/)
  assert.match(script, /server\/codex_worker\.py/)
  assert.match(script, /CODE_NEW_DIR.*server\/app/)
  assert.match(script, /chown -R.*CODE_NEW_DIR/)
  assert.match(script, /CANDIDATE_REMOTE_DIR.*fixed to the isolated candidate root/)
  assert.match(script, /wow_dev.*candidate template database/)
  assert.match(script, /candidate login component is not ready/)
  assert.match(script, /candidate readiness is blocked/)
  assert.match(script, /WEB_RELEASE_DIR/)
  assert.ok(
    script.indexOf('backup_complete') < script.indexOf('scp_remote "${PACKAGE_PATH}"'),
    'candidate backup must precede package transfer',
  )
  assert.match(script, /pg_dump/)
  assert.match(script, /createdb/)
  assert.match(script, /ON_ERROR_STOP=1/)
  assert.match(script, /nginx -t/)
  assert.match(script, /StrictHostKeyChecking=yes/)
  assert.doesNotMatch(script, /systemctl\s+(?:restart|stop|disable).*wow-v2-api\b/)
  assert.doesNotMatch(script, /systemctl\s+(?:restart|stop|disable).*wow-backend\b/)
  assert.doesNotMatch(script, /news_backend\.py/)
  assert.match(service, /EnvironmentFile=-\/etc\/wow-v2-api-candidate\.env/)
  assert.match(service, /WOW_APP_ENV=candidate/)
  assert.match(service, /WOW_API_V2_PORT=8791/)
  assert.match(service, /WOW_WEB_COOKIE_NAME=__Host-wow_v2_candidate/)
  assert.match(service, /WOW_WECHAT_ENV_VERSION=trial/)
  assert.match(service, /WOW_WECHAT_CHECK_PATH=0/)
  assert.match(service, /\/opt\/wow-mini-program-candidate/)
  assert.match(apiSnippet, /\/api\/v2-candidate\//)
  assert.match(apiSnippet, /127\.0\.0\.1:8791\/api\/v2\//)
  assert.doesNotMatch(apiSnippet, /server_name\s+api\.chickenbro\.cloud/)
})

test('candidate nginx locations are additive and path-isolated', () => {
  const snippet = read('server/wow-v2-candidate.locations.nginx')

  assert.match(snippet, /\/api\/v2-candidate\//)
  assert.match(snippet, /127\.0\.0\.1:8791\/api\/v2\//)
  assert.match(snippet, /\/web-candidate\//)
  assert.match(snippet, /chickenbro-web-candidate/)
  assert.doesNotMatch(snippet, /server_name\s+www\.chickenbro\.cloud/)
  assert.doesNotMatch(snippet, /location\s+\^~\s+\/api\/v2\//)
})

test('candidate frontend builds expose the candidate prefix and path', () => {
  const config = read('apps/mini-taro/config/index.ts')
  const authClient = read('packages/api-client/src/web-auth.ts')

  assert.match(config, /WOW_WEB_AUTH_API_PREFIX/)
  assert.match(config, /WOW_H5_PUBLIC_PATH/)
  assert.match(authClient, /__WOW_WEB_AUTH_API_PREFIX__/)
})

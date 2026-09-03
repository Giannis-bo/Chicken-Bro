const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

test('v2 deployment is isolated from the legacy service and backs up the exact target', () => {
  const script = read('server/deploy_web_v2_lighthouse.sh')
  assert.match(script, /wow-v2-api/)
  assert.match(script, /127\.0\.0\.1:8790/)
  assert.match(script, /EnvironmentFile=-\/etc\/wow-v2-api\.env/)
  assert.match(script, /0039_wechat_web_login_sessions\.sql/)
  assert.match(script, /pg_dump/)
  assert.match(script, /ON_ERROR_STOP=1/)
  assert.match(script, /nginx -t/)
  assert.match(script, /StrictHostKeyChecking=yes/)
  assert.match(script, /git -C .* ls-files/)
  assert.match(script, /WOW_DATABASE_RUNTIME=postgres_only/)
  assert.doesNotMatch(script, /systemctl\s+(?:restart|stop|disable).*wow-backend/)
  assert.doesNotMatch(script, /news_backend\.py/)
  assert.match(script, /\/etc\/wow-backend\.env/)
  assert.match(script, /WOW_RAIDERIO_API_KEY\|WOW_RAIDERIO_USER_AGENT\|WOW_RAIDERIO_TIMEOUT_SECONDS\|WOW_WARCRAFTLOGS_API_KEY\|WOW_WARCRAFTLOGS_CLIENT_ID\|WOW_WARCRAFTLOGS_CLIENT_SECRET/)
  assert.match(script, /WOW_BLIZZARD_CLIENT_ID\|WOW_BLIZZARD_CLIENT_SECRET\|WOW_BLIZZARD_TIMEOUT_SECONDS\|WOW_BNET_CLIENT_ID\|WOW_BNET_CLIENT_SECRET/)
  assert.match(script, /wow-v2-source\.env/)
})

test('v2 systemd service uses the isolated runtime and does not start a worker', () => {
  const service = read('server/wow-v2-api.service')
  assert.match(service, /EnvironmentFile=-\/etc\/wow-v2-api\.env/)
  assert.match(service, /EnvironmentFile=-\/etc\/wow-v2-source\.env/)
  assert.match(service, /WOW_APP_ENV=production/)
  assert.match(service, /WOW_API_V2_HOST=127\.0\.0\.1/)
  assert.match(service, /WOW_API_V2_PORT=8790/)
  assert.match(service, /\.venv-v2\/bin\/python -m uvicorn server\.app\.main:app/)
  assert.doesNotMatch(service, /EnvironmentFile=.*wow-backend\.env/)
  assert.doesNotMatch(service, /wow-.*worker|worker.*\.service/)
})

test('Nginx template serves the H5 root and proxies only the v2 API', () => {
  const nginx = read('server/wow-v2-web.nginx')
  assert.match(nginx, /server_name\s+www\.chickenbro\.cloud/)
  assert.match(nginx, /listen\s+443\s+ssl/)
  assert.match(nginx, /ssl_certificate\s+/)
  assert.match(nginx, /location\s+\^~\s+\/api\/v2\//)
  assert.match(nginx, /proxy_pass\s+http:\/\/127\.0\.0\.1:8790/)
  assert.match(nginx, /try_files\s+\$uri\s+\$uri\/\s+\/index\.html/)
  assert.match(nginx, /X-Forwarded-Proto/)
  assert.doesNotMatch(nginx, /Access-Control-Allow-Origin\s+\*/)
})

test('Nginx revalidates the unversioned H5 shell and bundle assets', () => {
  const nginx = read('server/wow-v2-web.nginx')
  assert.match(nginx, /location\s+=\s+\/index\.html[\s\S]*expires\s+-1/)
  assert.match(nginx, /location\s+~\*\s+\\\.\(\?:js\|css\)\$[\s\S]*expires\s+-1/)
})

const fs = require('node:fs')
const test = require('node:test')
const assert = require('node:assert/strict')
const { execFileSync, spawnSync } = require('node:child_process')

const scriptPath = 'server/deploy_lighthouse.sh'

test('lighthouse deploy script supports a no-download hot deploy mode', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')

  const bashProbe = spawnSync(process.platform === 'win32' ? 'where.exe' : 'which', ['bash'], { stdio: 'ignore' })
  if (bashProbe.status === 0) {
    assert.doesNotThrow(() => execFileSync('bash', ['-n', scriptPath]))
  }
  assert.match(script, /WOW_DEPLOY_SKIP_BOOTSTRAP/)
  assert.match(script, /WOW_DEPLOY_START_ASYNC_SYNCS/)
  assert.match(script, /Skipping remote bootstrap/)
  assert.match(script, /Skipping PG-native async sync starts/)
  assert.match(script, /gzip on;/)
  assert.match(script, /gzip_types application\/json text\/plain text\/css application\/javascript;/)
  assert.match(script, /gzip_vary on;/)
  assert.match(script, /wow-stat-weights-sync\.service/)
  assert.match(script, /wow-stat-weights-sync\.timer/)
  assert.match(script, /wow-community-template-sync\.service/)
  assert.match(script, /wow-community-template-sync\.timer/)

  const skipBranch = script.indexOf('if [[ "${SKIP_BOOTSTRAP}" == "1" ]]')
  const bootstrapBranch = script.indexOf('else # full remote bootstrap')
  assert.ok(skipBranch >= 0, 'missing explicit hot deploy branch')
  assert.ok(bootstrapBranch > skipBranch, 'missing full bootstrap branch after hot deploy branch')

  for (const networkOrInstallCommand of [
    'sudo apt-get update',
    'https://chatgpt.com/codex/install.sh',
    'https://api.github.com/repos/{repo}/branches/{branch}',
    'https://github.com/${SIMC_GITHUB_REPO}/archive/${latest_simc_commit}.tar.gz',
    'sudo systemctl start wow-simc-version-check.service'
  ]) {
    const commandIndex = script.indexOf(networkOrInstallCommand)
    assert.ok(commandIndex > bootstrapBranch, `${networkOrInstallCommand} must stay out of hot deploy mode`)
  }
})

test('lighthouse deploy script enables PG-native sync timers in PG-only mode', () => {
  const script = fs.readFileSync(scriptPath, 'utf8')
  const smokeIndex = script.indexOf('curl -fsS http://127.0.0.1/api/builds/home >/dev/null')
  assert.ok(smokeIndex > 0, 'missing builds home smoke check')
  const optInIndex = script.indexOf('if [[ "${START_ASYNC_SYNCS}" == "1" ]]')
  assert.ok(optInIndex > smokeIndex, 'async sync opt-in gate must run after API smoke checks')
  assert.match(script, /PG-native sync timers enabled/)

  for (const enableCommand of [
    'sudo systemctl enable --now wow-websim-sync.timer',
    'sudo systemctl enable --now wow-stat-weights-sync.timer',
    'sudo systemctl enable --now wow-community-template-sync.timer'
  ]) {
    const enableIndex = script.indexOf(enableCommand)
    assert.ok(enableIndex > 0 && enableIndex < smokeIndex, `${enableCommand} must run before API smoke checks`)
  }
  assert.doesNotMatch(script, /enable --now wow-gear-observed-backfill\.timer/)

  for (const startCommand of [
    'sudo systemctl start --no-block wow-websim-sync.service',
    'sudo systemctl start --no-block wow-stat-weights-sync.service',
    'sudo systemctl start --no-block wow-community-template-sync.service'
  ]) {
    const startIndex = script.indexOf(startCommand)
    assert.ok(startIndex > optInIndex, `${startCommand} must stay behind async sync opt-in`)
  }
  assert.doesNotMatch(script, /start --no-block wow-gear-observed-backfill\.service/)
})

test('community template sync has a six-hour persistent systemd timer', () => {
  const service = fs.readFileSync('server/wow-community-template-sync.service', 'utf8')
  const timer = fs.readFileSync('server/wow-community-template-sync.timer', 'utf8')

  assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/)
  assert.doesNotMatch(service, /WOW_NEWS_DB/)
  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 7200 \/run\/lock\/wow-mini-program-sync\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/community_template_sync\.py/)
  assert.match(service, /TimeoutStartSec=180min/)
  assert.match(timer, /OnBootSec=12min/)
  assert.match(timer, /OnUnitActiveSec=6h/)
  assert.match(timer, /Persistent=true/)
})

test('production systemd units do not configure SQLite runtime paths', () => {
  for (const unit of [
    'server/wow-backend.service',
    'server/wow-websim-sync.service',
    'server/wow-stat-weights-sync.service',
    'server/wow-community-template-sync.service',
    'server/wow-gear-observed-backfill.service'
  ]) {
    const service = fs.readFileSync(unit, 'utf8')
    assert.match(service, /Environment=WOW_DATABASE_RUNTIME=postgres_only/, `${unit} must opt into PG-only runtime`)
    assert.doesNotMatch(service, /WOW_NEWS_DB/, `${unit} must not configure WOW_NEWS_DB`)
    assert.doesNotMatch(service, /server\/data\/wow_news\.sqlite3/, `${unit} must not pass the runtime SQLite file`)
  }
})

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
  assert.match(script, /Skipping remote bootstrap/)
  assert.match(script, /systemctl start --no-block wow-websim-sync\.service/)
  assert.match(script, /wow-stat-weights-sync\.service/)
  assert.match(script, /wow-stat-weights-sync\.timer/)
  assert.match(script, /systemctl start --no-block wow-stat-weights-sync\.service/)
  assert.match(script, /wow-community-template-sync\.service/)
  assert.match(script, /wow-community-template-sync\.timer/)
  assert.match(script, /systemctl start --no-block wow-community-template-sync\.service/)
  assert.doesNotMatch(script, /systemctl start wow-websim-sync\.service \|\|/)
  assert.doesNotMatch(script, /systemctl start wow-stat-weights-sync\.service \|\|/)
  assert.doesNotMatch(script, /systemctl start wow-community-template-sync\.service \|\|/)

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

test('community template sync has a six-hour persistent systemd timer', () => {
  const service = fs.readFileSync('server/wow-community-template-sync.service', 'utf8')
  const timer = fs.readFileSync('server/wow-community-template-sync.timer', 'utf8')

  assert.match(service, /ExecStart=\/usr\/bin\/flock -w 7200 \/run\/lock\/wow-mini-program-sync\.lock \/usr\/bin\/python3 \/opt\/wow-mini-program\/server\/community_template_sync\.py/)
  assert.match(service, /TimeoutStartSec=180min/)
  assert.match(timer, /OnBootSec=12min/)
  assert.match(timer, /OnUnitActiveSec=6h/)
  assert.match(timer, /Persistent=true/)
})

const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const path = require('node:path')
const test = require('node:test')

test('historical Mini/Web release entry fails before build, network or database changes', () => {
  const result = spawnSync('bash', [path.resolve(__dirname, '../server/deploy_chickenbro_candidate_lighthouse.sh')], {
    encoding: 'utf8', env: { PATH: '/usr/bin:/bin' },
  })
  assert.equal(result.status, 1)
  assert.match(result.stderr, /retired/)
  assert.match(result.stderr, /chickenbro-simc-production-runbook/)
})

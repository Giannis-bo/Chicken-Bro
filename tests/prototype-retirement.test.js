const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const repositoryRoot = path.resolve(__dirname, '..')

function source(relativePath) {
  return fs.readFileSync(path.join(repositoryRoot, relativePath), 'utf8')
}

test('formal backend runtime has no prototype owner, route, dependency, or setting', () => {
  for (const relativePath of [
    'server/app/main.py',
    'server/app/api/dependencies.py',
    'server/app/api/routes/__init__.py',
    'server/app/identity/repository.py',
    'server/app/platform/config.py',
    'server/app/chickenbro/application.py',
    'server/app/chickenbro/ports.py',
  ]) {
    assert.doesNotMatch(source(relativePath), /prototype/i, relativePath)
  }
})

test('formal typed clients export only real identity, Chat, and SimC contracts', () => {
  for (const relativePath of [
    'packages/api-client/src/clients.ts',
    'packages/api-client/src/index.ts',
    'packages/domain/src/index.ts',
  ]) {
    assert.doesNotMatch(source(relativePath), /prototype/i, relativePath)
  }
})

test('Chickenbro service definitions contain no prototype bypass configuration', () => {
  for (const relativePath of [
    'server/chickenbro-api-candidate.service',
    'server/chickenbro-api.service',
    'server/chickenbro-worker-candidate.service',
    'server/chickenbro-worker.service',
  ]) {
    assert.doesNotMatch(source(relativePath), /WOW_WEB_PROTOTYPE|prototype_enabled/i, relativePath)
  }
})

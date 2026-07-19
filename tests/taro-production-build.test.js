const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('Taro production builds cannot reuse persistent webpack cache', () => {
  const config = fs.readFileSync('apps/mini-taro/config/index.ts', 'utf8')

  assert.match(config, /const productionBuild = process\.env\['NODE_ENV'\] === 'production'/)
  assert.match(config, /cache:\s*\{\s*enable: !productionBuild && !isolatedBuild,/s)
})

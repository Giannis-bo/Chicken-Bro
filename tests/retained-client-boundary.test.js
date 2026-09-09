const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const root = path.resolve(__dirname, '..')

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

test('the retained app shell has no legacy design asset runtime', () => {
  const retainedSources = [
    'apps/mini-taro/src/app.tsx',
    'apps/mini-taro/src/app.scss',
    'apps/mini-taro/src/custom-tab-bar/index.tsx',
    'apps/mini-taro/src/platform/AppTabBar.h5.tsx',
    'apps/mini-taro/src/pages/auth/web-login-confirm.tsx',
    'apps/mini-taro/src/tab-bar-items.ts',
  ].map(read).join('\n')

  assert.doesNotMatch(retainedSources, /@wow-mini\/(?:assets-manifest|design-system)/)
  assert.doesNotMatch(retainedSources, /__WOW_(?:ASSET_RUNTIME_ROOT|RUNTIME_MEDIA_ROOT)__/)

  const miniPackage = JSON.parse(read('apps/mini-taro/package.json'))
  assert.equal(miniPackage.dependencies['@wow-mini/assets-manifest'], undefined)
  assert.equal(miniPackage.dependencies['@wow-mini/design-system'], undefined)

  const lockfile = JSON.parse(read('package-lock.json'))
  const lockedMiniDependencies = lockfile.packages['apps/mini-taro'].dependencies
  assert.equal(lockedMiniDependencies['@wow-mini/assets-manifest'], undefined)
  assert.equal(lockedMiniDependencies['@wow-mini/design-system'], undefined)
})

test('the mini-program manifest exposes only Chat, SimC and the QR confirmation page', () => {
  const appConfig = read('apps/mini-taro/src/app.config.ts')

  for (const page of [
    'pages/chickenbro/index',
    'pages/simc/index',
    'pages/simc/tasks',
    'pages/simc/task-detail',
    'pages/auth/web-login-confirm',
  ]) {
    assert.match(appConfig, new RegExp(page.replaceAll('/', '\\/')))
  }
  assert.doesNotMatch(appConfig, /pages\/(?:news|builds|profile|simulator)\//)
  assert.equal((appConfig.match(/pagePath:/g) ?? []).length, 2)
})

test('the retained build control plane has no legacy UI or news compatibility hooks', () => {
  const taroConfig = read('apps/mini-taro/config/index.ts')
  const babelConfig = read('apps/mini-taro/babel.config.cjs')
  const baseTypeScriptConfig = read('tsconfig.base.json')

  assert.doesNotMatch(taroConfig, /WOW_NEWS_API_BASE_URL|\/wow-api|124\.223\.51\.33/)
  assert.doesNotMatch(babelConfig, /babel-data-selector-markers/)
  assert.doesNotMatch(baseTypeScriptConfig, /@wow-mini\/(?:assets-manifest|design-system)/)
})

test('the shared API client creates only transport, Chat, SimC and Web auth', () => {
  const clients = read('packages/api-client/src/clients.ts')
  const index = read('packages/api-client/src/index.ts')
  const forbidden = /\b(?:news|builds|websim|simulator|templates|analytics|cache|AuthClient|PlatformV2Client)\b/i

  assert.doesNotMatch(clients, forbidden)
  assert.doesNotMatch(index, forbidden)
  for (const owner of ['transport', 'chat', 'simc', 'webAuth']) {
    assert.match(clients, new RegExp(`\\b${owner}\\b`))
  }
})

test('the retained transport has no legacy endpoint registry, bearer token or analytics path', () => {
  const transport = read('packages/api-client/src/transport.ts')

  assert.doesNotMatch(transport, /endpointContract|requestEndpoint|requestStreamEndpoint/)
  assert.doesNotMatch(transport, /AnalyticsIdentity|attachAnalyticsHeaders|auth\.token/)
  assert.doesNotMatch(transport, /api\.newsBaseCompat|NdjsonDecoder/)
  assert.doesNotMatch(transport, /http:\/\/124\.223\.51\.33|\/wow-api/)
  assert.match(transport, /auth: TransportAuthContext/)
})

test('the public domain barrel exposes only Chat, SimC and real Web identity', () => {
  const index = read('packages/domain/src/index.ts')

  assert.match(index, /from '.\/chat'/)
  assert.match(index, /from '.\/simc'/)
  assert.match(index, /from '.\/web-auth'/)
  assert.doesNotMatch(index, /models|entities|route-contract|gear-intent|platform-v2|state/)
})

test('the root workspace and CI expose only retained product workflows', () => {
  const workspace = JSON.parse(read('package.json'))
  assert.deepEqual(Object.keys(workspace.scripts), [
    'build:h5',
    'build:weapp',
    'dev:h5',
    'dev:weapp',
    'refresh:weapp',
    'typecheck',
    'lint',
    'test:taro',
    'test:backend',
    'test:migration',
    'test:control',
    'test:ops',
    'harness',
    'test:chat-images',
  ])
  for (const removedTool of ['@babel/parser', '@babel/traverse', 'miniprogram-automator', 'playwright-core']) {
    assert.equal(workspace.devDependencies[removedTool], undefined)
  }

  const lockfile = JSON.parse(read('package-lock.json'))
  assert.deepEqual(lockfile.packages[''].devDependencies, workspace.devDependencies)
  assert.equal(Object.keys(lockfile.packages).some((key) => /(?:assets-manifest|design-system)$/.test(key)), false)

  const workflow = read('.github/workflows/project-harness.yml')
  assert.doesNotMatch(workflow, /verify-project/)
  for (const command of ['npm run test:control', 'npm run test:backend', 'npm run test:taro', 'npm run build:weapp']) {
    assert.match(workflow, new RegExp(command.replaceAll(':', '\\:')))
  }
})

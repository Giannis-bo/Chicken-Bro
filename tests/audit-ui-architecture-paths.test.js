const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const root = path.resolve(__dirname, '..')

function sha256(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex')
}

function contentAddressedJsonFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name)
    if (entry.isDirectory()) return contentAddressedJsonFiles(absolutePath)
    return /^[0-9a-f]{64}\.json$/u.test(entry.name) ? [absolutePath] : []
  })
}

test('UI audit normalizes Windows separators before explicit owner comparisons', () => {
  const helperPath = path.join(root, 'scripts', 'repo-relative-path.js')
  assert.equal(fs.existsSync(helperPath), true, 'missing repo-relative path normalization owner')
  if (!fs.existsSync(helperPath)) return

  const { repoRelativePath, repoPathDirname, repoPathJoin } = require(helperPath)
  assert.equal(
    repoRelativePath('packages\\design-system\\src\\components\\TabBar.module.scss'),
    'packages/design-system/src/components/TabBar.module.scss',
  )
  assert.equal(
    repoPathJoin('packages\\design-system\\src', 'components', 'ProductionAsset.tsx'),
    'packages/design-system/src/components/ProductionAsset.tsx',
  )
  assert.equal(
    repoPathDirname('apps\\mini-taro\\src\\pages\\_shared\\route-runtime.tsx'),
    'apps/mini-taro/src/pages/_shared',
  )

  const audit = fs.readFileSync(path.join(root, 'scripts', 'audit-ui-architecture.js'), 'utf8')
  assert.match(audit, /require\('\.\/repo-relative-path'\)/u)
  assert.match(audit, /const relativePath = repoPathJoin\(relativeDir, entry\.name\)/u)
  assert.match(audit, /repoPathJoin\(repoPathDirname\(file\), relativeStylePath\)/u)
  assert.match(audit, /repoPathJoin\(repoPathDirname\(file\), statement\.source\.value\)/u)
})

test('PageFrame variant audit parses complete JSX opening elements', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  assert.equal(fs.existsSync(helperPath), true, 'missing UI architecture AST helper')
  if (!fs.existsSync(helperPath)) return

  const { pageFrameLiteralVariants } = require(helperPath)
  const longAction = 'x'.repeat(700)
  const source = `
    export function Route() {
      return (
        <PageFrame
          rightAction={<Action description="${longAction}" />}
          variant="news-home"
        />
      )
    }
  `

  assert.deepEqual(pageFrameLiteralVariants(source), ['news-home'])

  const audit = fs.readFileSync(path.join(root, 'scripts', 'audit-ui-architecture.js'), 'utf8')
  assert.match(audit, /pageFrameLiteralVariants/u)
  assert.doesNotMatch(audit, /invocation\.slice\(0, 500\)/u)
})

test('content-addressed runtime review JSON declares LF byte preservation', () => {
  const attributesPath = path.join(root, '.gitattributes')
  assert.equal(fs.existsSync(attributesPath), true, 'missing runtime evidence byte policy')
  if (!fs.existsSync(attributesPath)) return
  const attributes = fs.readFileSync(attributesPath, 'utf8')
  assert.match(attributes, /^artifacts\/ui-runtime-reviews\/\*\*\/\*\.json text eol=lf$/mu)
})

test('content-addressed runtime review JSON working bytes match their filenames', () => {
  const files = contentAddressedJsonFiles(path.join(root, 'artifacts', 'ui-runtime-reviews'))
  assert.ok(files.length >= 8, `expected content-addressed runtime JSON, found ${files.length}`)
  for (const file of files) {
    assert.equal(sha256(fs.readFileSync(file)), path.basename(file, '.json'), path.relative(root, file))
  }
})

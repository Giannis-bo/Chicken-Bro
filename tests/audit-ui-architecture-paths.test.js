const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const root = path.resolve(__dirname, '..')

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

test('semantic region audit includes an explicitly published PageFrame header region', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const {
    closedSemanticRegionIds,
    publishedPageFrameRegionIds,
    publishedRouteRegionIds,
    publishedSemanticRegionIds,
  } = require(helperPath)
  const source = `
    export function Route() {
      return (
        <PageFrame region="page_header">
          <RouteRegion data-region="class_selector" />
          <RouteRegion data-region="command_deck" />
        </PageFrame>
      )
    }
  `

  assert.deepEqual(publishedSemanticRegionIds(source), ['page_header', 'class_selector', 'command_deck'])
  assert.deepEqual(publishedPageFrameRegionIds(source), ['page_header'])
  assert.deepEqual(publishedRouteRegionIds(source), ['class_selector', 'command_deck'])
  const publishedRouteRegions = publishedRouteRegionIds(source)
  const publishedPageFrameRegions = publishedPageFrameRegionIds(source)
  assert.deepEqual(closedSemanticRegionIds({
    publishedRouteRegions,
    publishedPageFrameRegions,
    requiredRegionIds: ['page_header', 'class_selector', 'command_deck'],
  }), ['class_selector', 'command_deck', 'page_header'])
  assert.deepEqual(closedSemanticRegionIds({
    publishedRouteRegions,
    publishedPageFrameRegions,
    requiredRegionIds: ['class_selector', 'command_deck'],
  }), ['class_selector', 'command_deck'])

  const pageFrame = fs.readFileSync(path.join(root, 'packages/design-system/src/components/PageFrame.tsx'), 'utf8')
  assert.match(pageFrame, /data-region=\{region\}/u)
})

test('selected material audit resolves the style module imported by the component', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { literalStyleModuleImports, styleModuleOwnsSelectedMaterial } = require(helperPath)
  const source = `
    import styles from './BuildsHomeCommandDeck.module.scss'
    import { helper } from './helper'
    export const selector = styles.classSelectorOption
  `

  assert.deepEqual(literalStyleModuleImports(source), [
    { localName: 'styles', source: './BuildsHomeCommandDeck.module.scss' },
  ])

  const dualModuleSource = `
    import stylesA from './A.module.scss'
    import stylesB from './B.module.scss'
    export const selector = stylesA['option']
  `
  const wrongOwner = new Map([
    ['./A.module.scss', '.option { color: white; }'],
    ['./B.module.scss', ".option[data-selected='true'] { color: gold; }"],
  ])
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: dualModuleSource,
    classExpression: "stylesA['option']",
    stateAttribute: 'data-selected',
    readStyleModule: (stylePath) => wrongOwner.get(stylePath) ?? '',
  }), false)
  wrongOwner.set('./A.module.scss', ".option[data-selected='true'] { color: gold; }")
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: dualModuleSource,
    classExpression: "stylesA['option']",
    stateAttribute: 'data-selected',
    readStyleModule: (stylePath) => wrongOwner.get(stylePath) ?? '',
  }), true)

  const helperSource = `
    import localStyles from './Local.module.scss'
    function componentStyle(name: string): string { return localStyles[name] ?? '' }
    export const selector = componentStyle('option')
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: helperSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: (stylePath) => stylePath === './Local.module.scss'
      ? ".option[data-selected='true'] { color: gold; }"
      : '',
  }), true)

  const reconstructionSource = `
    import { reconstructionStyle as localReconstructionStyle } from './reconstruction-style'
    export const selector = localReconstructionStyle('option')
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: reconstructionSource,
    classExpression: "localReconstructionStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: (stylePath) => stylePath === './reconstruction.module.scss'
      ? ".option[data-selected='true'] { color: gold; }"
      : '',
  }), true)
})

test('builds specialization fill contract is required only by the active source or current contracts', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { buildsSpecializationFillAudit, buildsSpecializationFillContractRequired } = require(helperPath)

  assert.equal(buildsSpecializationFillContractRequired({
    source: '<BuildCommandDeck />',
    assetContract: { slots: [{ slotId: 'asset_slot.builds-class-icon' }] },
    componentContract: { components: [{ owner: 'BuildToolCommandDeck' }] },
  }), false)
  assert.equal(buildsSpecializationFillContractRequired({
    source: '<BuildSpecializationOverview />',
    assetContract: { slots: [] },
    componentContract: { components: [] },
  }), true)
  assert.equal(buildsSpecializationFillContractRequired({
    source: '<BuildCommandDeck />',
    assetContract: { slots: [{ slotId: 'asset_slot.builds-specialization-object' }] },
    componentContract: { components: [] },
  }), true)

  const inactive = buildsSpecializationFillAudit({
    source: '<BuildCommandDeck />',
    assetContract: { slots: [{ slotId: 'asset_slot.builds-class-icon' }] },
    componentContract: { components: [{ owner: 'BuildToolCommandDeck' }] },
    readLegacyFile: () => { throw new Error('legacy path does not exist') },
  })
  assert.deepEqual(inactive, { required: false, pass: true })

  const activeMissing = buildsSpecializationFillAudit({
    source: '<BuildCommandDeck />',
    assetContract: {
      slots: [{
        slotId: 'asset_slot.builds-specialization-object',
        targetAspect: 'aspectFill',
        runtimeCrop: { fit: 'aspectFill', scale: 1 },
      }],
    },
    componentContract: { components: [] },
    readLegacyFile: () => { throw new Error('legacy path does not exist') },
  })
  assert.deepEqual(activeMissing, { required: true, pass: false })
})

test('UI audit registers the current builds-home layout and selected-control owners', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { routeLayoutFamilyCoverageMatches } = require(helperPath)
  const audit = fs.readFileSync(path.join(root, 'scripts', 'audit-ui-architecture.js'), 'utf8')

  assert.match(audit, /routeLayoutFamilyCoverageMatches\(\{/u)
  assert.match(audit, /region: routeRegionConsumers\.length/u)
  assert.match(audit, /BuildClassSelector\.tsx', 'build-class-option'/u)
  assert.match(audit, /styleModuleOwnsSelectedMaterial/u)
  assert.match(audit, /buildsSpecializationFillAudit/u)

  assert.equal(routeLayoutFamilyCoverageMatches({ stage: 9, flow: 3, column: 5, grid: 1, region: 14 }), true)
  assert.equal(routeLayoutFamilyCoverageMatches({ stage: 9, flow: 3, column: 5, grid: 1, region: 15 }), false)
})

test('content-addressed runtime review JSON declares LF byte preservation', () => {
  const attributesPath = path.join(root, '.gitattributes')
  assert.equal(fs.existsSync(attributesPath), true, 'missing runtime evidence byte policy')
  if (!fs.existsSync(attributesPath)) return
  const attributes = fs.readFileSync(attributesPath, 'utf8')
  assert.match(attributes, /^artifacts\/ui-runtime-reviews\/\*\*\/\*\.json text eol=lf$/mu)
})

test('superseded runtime review JSON does not remain in the working tree', () => {
  const files = contentAddressedJsonFiles(path.join(root, 'artifacts', 'ui-runtime-reviews'))
  assert.deepEqual(files, [])
})

test('UI audit uses the plan whitelist without claiming authority over non-UI plans', () => {
  const audit = fs.readFileSync(path.join(root, 'scripts', 'audit-ui-architecture.js'), 'utf8')
  assert.match(audit, /current_plan_set_matches_plan_whitelist/u)
  assert.match(audit, /ui_evidence_policy_plan_files_are_whitelisted/u)
  assert.doesNotMatch(
    audit,
    /JSON\.stringify\(currentPlanFiles\) === JSON\.stringify\(sorted\(evidencePolicy\.allowedPlanFiles/u,
  )
})

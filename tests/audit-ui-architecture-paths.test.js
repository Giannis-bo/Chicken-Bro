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
})

test('selected material audit accepts only exact CSS module class tokens', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)

  const regexTokenSource = `
    import styles from './Regex.module.scss'
    export const selector = styles['.*']
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: regexTokenSource,
    classExpression: "styles['.*']",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".unrelated[data-selected='true'] { color: gold; }",
  }), false)

  assert.equal(styleModuleOwnsSelectedMaterial({
    source: `import styles from './Tokens.module.scss'`,
    classExpression: "styles['selectedOption']",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".selectedOptionExtra[data-selected='true'] { color: gold; }",
  }), false)

  for (const className of ['selected-option', 'selected_option', 'selectedOption']) {
    assert.equal(styleModuleOwnsSelectedMaterial({
      source: `import styles from './Tokens.module.scss'`,
      classExpression: `styles['${className}']`,
      stateAttribute: 'data-selected',
      readStyleModule: () => `.${className}[data-selected='true'] { color: gold; }`,
    }), true)
  }
})

test('selected material helper bindings follow compatible return values only', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)

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

  const decoyHelperSource = `
    import localStyles from './Local.module.scss'
    function componentStyle(name: string): string {
      const unused = localStyles[name]
      return 'static-class'
    }
    export const selector = componentStyle('option')
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: decoyHelperSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

  const ambiguousHelperSource = `
    import stylesA from './A.module.scss'
    import stylesB from './B.module.scss'
    function componentStyle(name: string, useA: boolean): string {
      if (useA) return stylesA[name] ?? ''
      return stylesB[name] ?? ''
    }
    export const selector = componentStyle('option', false)
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: ambiguousHelperSource,
    classExpression: "componentStyle('option', false)",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

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

test('selected material helper bindings require every conditional return branch to carry the same module', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)
  const conditionalStaticSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string, enabled: boolean): string {
      return enabled ? styles[name] ?? '' : 'static-class'
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: conditionalStaticSource,
    classExpression: "componentStyle('option', false)",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

  const conditionalBoundSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string, compact: boolean): string {
      return compact ? styles[name] ?? '' : styles[name] ?? ''
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: conditionalBoundSource,
    classExpression: "componentStyle('option', false)",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), true)
})

test('selected material helper bindings use only the final sequence return value', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)
  const sequenceStaticSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string {
      return (styles[name], 'static-class')
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: sequenceStaticSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

  const sequenceBoundSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string {
      return ('ignored', styles[name] ?? '')
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: sequenceBoundSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), true)
})

test('selected material helper bindings reject conditional fallthrough and support simple expression helpers', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)
  const fallthroughSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string, enabled: boolean): string | undefined {
      if (enabled) return styles[name] ?? ''
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: fallthroughSource,
    classExpression: "componentStyle('option', false)",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

  const expressionArrowSource = `
    import styles from './Local.module.scss'
    const componentStyle = (name: string): string => styles[name] ?? ''
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: expressionArrowSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), true)
})

test('selected material helper templates preserve the module class as a whitespace-delimited token', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)
  const unsafeTemplateSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string { return \`${'${styles[name]}'}Suffix\` }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: unsafeTemplateSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

  const safeTemplateSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string { return \`prefix ${'${styles[name]}'} suffix\` }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: safeTemplateSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), true)
})

test('selected material helper concatenation preserves the module class as a whitespace-delimited token', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)
  const unsafePlusSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string { return (styles[name] ?? '') + 'Suffix' }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: unsafePlusSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)

  const safePlusSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string { return 'prefix ' + (styles[name] ?? '') + ' suffix' }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: safePlusSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), true)
})

test('selected material helper array joins require a literal non-empty whitespace separator', () => {
  const helperPath = path.join(root, 'scripts', 'ui-architecture-ast.js')
  const { styleModuleOwnsSelectedMaterial } = require(helperPath)
  const sourceForJoin = (separator) => `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string {
      return [styles[name] ?? '', 'extra'].filter(Boolean).join(${separator})
    }
  `
  for (const separator of [`''`, `'-'`, 'separator']) {
    assert.equal(styleModuleOwnsSelectedMaterial({
      source: sourceForJoin(separator),
      classExpression: "componentStyle('option')",
      stateAttribute: 'data-selected',
      readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
    }), false)
  }
  const defaultJoinSource = sourceForJoin('')
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: defaultJoinSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)
  const directJoinSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string {
      return [styles[name] ?? '', 'extra'].join(' ')
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: directJoinSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)
  const otherFilterSource = `
    import styles from './Local.module.scss'
    function componentStyle(name: string): string {
      return [styles[name] ?? '', 'extra'].filter(() => true).join(' ')
    }
  `
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: otherFilterSource,
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
  }), false)
  assert.equal(styleModuleOwnsSelectedMaterial({
    source: sourceForJoin(`' '`),
    classExpression: "componentStyle('option')",
    stateAttribute: 'data-selected',
    readStyleModule: () => ".option[data-selected='true'] { color: gold; }",
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

test('UI audit contracts the Captain root conversation and archive routes without adding a fifteenth route', () => {
  const audit = fs.readFileSync(path.join(root, 'scripts', 'audit-ui-architecture.js'), 'utf8')
  const geometry = fs.readFileSync(path.join(root, 'docs', 'design', 'current-ui', 'route-geometry-contract.json'), 'utf8')

  assert.match(geometry, /"route":\s*"simulator_home"[^\n]*"captain_transcript"/u)
  assert.match(geometry, /"route":\s*"chickenbro_chat"[^\n]*"archive_list"/u)
  assert.match(geometry, /"chickenbro-dock-send"/u)
  assert.doesNotMatch(geometry, /simulator-dock-upload|simulator-dock-paste|chickenbro-dock-new-topic/u)
  assert.match(audit, /chickenbro-dock-send/u)
  assert.doesNotMatch(audit, /simulator-dock-upload", "simulator-dock-paste", "simulator-dock-send/u)
  assert.doesNotMatch(audit, /chickenbro-dock-new-topic", "chickenbro-dock-send/u)
})

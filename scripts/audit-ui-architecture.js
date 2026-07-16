#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const babelParser = require('@babel/parser')
const traverse = require('@babel/traverse').default

const root = path.resolve(__dirname, '..')
const findings = []
const checks = []

const expectedAppRoutes = [
  'pages/news/news',
  'pages/news/list',
  'pages/news/detail',
  'pages/builds/builds',
  'pages/builds/workbench',
  'pages/builds/intel',
  'pages/builds/talent-simulator',
  'pages/builds/detail',
  'pages/simulator/simulator',
  'pages/simulator/simc',
  'pages/simulator/chickenbro',
  'pages/simulator/tasks',
  'pages/simulator/task-detail',
  'pages/profile/profile',
]
const expectedContractRoutes = [
  'build-intel',
  'builds-home',
  'chickenbro-chat',
  'gear-detail',
  'news-detail',
  'news-home',
  'news-list',
  'profile-templates',
  'simc-submit',
  'simulator-home',
  'talent-simulator',
  'task-detail',
  'tasks-list',
  'workbench',
]
const requiredContractFiles = [
  'asset-contract.json',
  'component-contract.json',
  'target-geometry.json',
  'target-inventory.json',
  'truth-adaptation.json',
]

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function walk(relativeDir, extensions) {
  const base = path.join(root, relativeDir)
  const files = []
  for (const entry of fs.readdirSync(base, { withFileTypes: true })) {
    const relativePath = path.join(relativeDir, entry.name)
    if (entry.isDirectory()) files.push(...walk(relativePath, extensions))
    else if (extensions.some((extension) => entry.name.endsWith(extension))) files.push(relativePath)
  }
  return files
}

function record(id, pass, detail) {
  checks.push({ id, pass, detail })
  if (!pass) findings.push(`${id}: ${detail}`)
}

function sorted(values) {
  return [...values].sort((a, b) => a.localeCompare(b))
}

const routeSources = walk('apps/mini-taro/src/pages', ['.ts', '.tsx', '.scss'])
const routeStyles = routeSources.filter((file) => file.endsWith('.scss'))
const routeComponents = routeSources.filter((file) => file.endsWith('.tsx'))

const appConfig = read('apps/mini-taro/src/app.config.ts')
const pagesBlock = appConfig.match(/pages:\s*\[([\s\S]*?)\],\s*window:/)?.[1] ?? ''
const configuredRoutes = [...pagesBlock.matchAll(/'([^']+)'/g)].map((match) => match[1])
record(
  'app_route_manifest_is_exactly_14_routes',
  JSON.stringify(configuredRoutes) === JSON.stringify(expectedAppRoutes),
  `configured=${configuredRoutes.length}`,
)

const targetRegistry = JSON.parse(read('docs/design/current-ui/target-registry.json'))
record(
  'target_registry_is_active_and_complete',
  targetRegistry.status === 'active' && targetRegistry.canonicalTargets?.length === 14,
  `status=${targetRegistry.status}; targets=${targetRegistry.canonicalTargets?.length ?? 0}`,
)

const contractsRoot = path.join(root, 'docs/design/current-ui/routes')
const contractRoutes = sorted(fs.readdirSync(contractsRoot).filter((name) => fs.statSync(path.join(contractsRoot, name)).isDirectory()))
record(
  'route_contract_set_matches_delivery_routes',
  JSON.stringify(contractRoutes) === JSON.stringify(expectedContractRoutes),
  `contracts=${contractRoutes.length}`,
)
for (const route of expectedContractRoutes) {
  for (const file of requiredContractFiles) {
    const relativePath = `docs/design/current-ui/routes/${route}/${file}`
    const exists = fs.existsSync(path.join(root, relativePath))
    let validJson = false
    if (exists) {
      try {
        JSON.parse(read(relativePath))
        validJson = true
      } catch {}
    }
    record(`contract:${route}:${file}`, exists && validJson, exists ? 'invalid_json' : 'missing')
  }
}

const requiredAuthorities = [
  'docs/roadmap.md',
  'docs/plans/2026-07-14-target-first-14-route-rebuild.md',
  'DESIGN.md',
  'docs/design/current-ui/README.md',
]
for (const authority of requiredAuthorities) {
  record(`authority:${authority}`, fs.existsSync(path.join(root, authority)), 'missing')
}

const deadShellRules = routeStyles.filter((file) => /^\.shell(?:\b|,)/m.test(read(file)))
record('route_styles_do_not_own_app_shell', deadShellRules.length === 0, deadShellRules.join(', ') || 'none')

const routeSafeAreaOwners = routeSources.filter((file) => /--(?:safe-top|safe-bottom|capsule-safe-right)\b/.test(read(file)))
record('route_styles_do_not_recompute_safe_area', routeSafeAreaOwners.length === 0, routeSafeAreaOwners.join(', ') || 'none')

const deprecatedAppShellProps = []
for (const file of routeComponents) {
  const ast = babelParser.parse(read(file), { sourceType: 'module', plugins: ['jsx', 'typescript'] })
  traverse(ast, {
    JSXOpeningElement(elementPath) {
      const name = elementPath.node.name
      if (name.type !== 'JSXIdentifier' || name.name !== 'AppShell') return
      const names = elementPath.node.attributes.flatMap((attribute) => (
        attribute.type === 'JSXAttribute' && attribute.name.type === 'JSXIdentifier'
          ? [attribute.name.name]
          : []
      ))
      const deprecated = ['className', 'chrome', 'chromeVariant', 'contentOrigin'].filter((prop) => names.includes(prop))
      if (deprecated.length) deprecatedAppShellProps.push(`${file}:${deprecated.join('|')}`)
    },
  })
}
record('routes_use_only_current_app_shell_api', deprecatedAppShellProps.length === 0, deprecatedAppShellProps.join(', ') || 'none')

const componentSources = walk('packages/design-system/src', ['.ts', '.tsx'])
const rawButtonOwners = componentSources.filter((file) => file !== 'packages/design-system/src/components/ControlButton.tsx' && /<Button\b/.test(read(file)))
record('native_button_has_one_shared_owner', rawButtonOwners.length === 0, rawButtonOwners.join(', ') || 'ControlButton only')

const reconstructionPath = 'packages/design-system/src/components/reconstruction.module.scss'
const reconstruction = read(reconstructionPath)
const legacyChromeSelector = /\.(?:pageFrame|pageHeader|pageCenteredTitle|pageHeaderLeading|pageHeaderAction|pageHeaderFlexSpacer|pageRootContext|sharedBack|pushedBack|titleRail|newsPushedTitleRail)\b/
record('reconstruction_css_has_no_page_frame_geometry', !legacyChromeSelector.test(reconstruction), 'legacy selector present')
const importantCount = (reconstruction.match(/!important/g) ?? []).length
record('reconstruction_override_budget_is_bounded', importantCount <= 20, `important=${importantCount}; max=20`)

const pageFrame = read('packages/design-system/src/components/PageFrame.tsx')
const pageChrome = read('packages/design-system/src/components/PageFrame.chrome.ts')
const ownerStyles = read('packages/design-system/src/components/owners.module.scss')
record(
  'page_frame_uses_owner_geometry_only',
  pageFrame.includes("ownerStyle('pageFrameHeader')") && !/reconstructionStyle\('(?:pageFrame|pageHeader|sharedBack|titleRail)/.test(pageFrame),
  'PageFrame owner boundary',
)
record(
  'four_primary_tabs_share_root_chrome_contract',
  ['news-home', 'builds-home', 'simulator-home', 'profile'].every((variant) => pageChrome.includes(`'${variant}'`))
    && ownerStyles.includes('.pageFrame-root .pageFrameHeader'),
  'root variants or root owner missing',
)

const babelConfig = read('apps/mini-taro/babel.config.cjs')
const markerPlugin = read('apps/mini-taro/config/babel-data-selector-markers.cjs')
record(
  'data_selector_css_has_runtime_markers',
  babelConfig.includes('babel-data-selector-markers.cjs')
    && markerPlugin.includes("name.startsWith('data-')")
    && markerPlugin.includes("@wow-mini/design-system/components/selector-markers"),
  'compiler marker plugin missing',
)

const summary = {
  status: findings.length ? 'fail' : 'pass',
  checkedRoutes: configuredRoutes.length,
  checkedContracts: contractRoutes.length,
  checks: checks.length,
  reconstructionImportantCount: importantCount,
  findings,
}
console.log(JSON.stringify(summary, null, 2))
if (findings.length) process.exitCode = 1

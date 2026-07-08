#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const BUILT_IN_TAGS = new Set([
  'block',
  'button',
  'canvas',
  'checkbox',
  'checkbox-group',
  'cover-image',
  'cover-view',
  'form',
  'icon',
  'image',
  'input',
  'label',
  'movable-area',
  'movable-view',
  'navigator',
  'picker',
  'picker-view',
  'picker-view-column',
  'progress',
  'radio',
  'radio-group',
  'rich-text',
  'scroll-view',
  'slider',
  'swiper',
  'swiper-item',
  'switch',
  'textarea',
  'text',
  'view'
])
const ALLOWED_SHARED_COMPONENTS = new Set([
  'navigation-bar',
  'app-shell',
  'page-frame',
  'wow-panel',
  'material-image',
  'game-object-icon',
  'status-visual',
  'action-button',
  'module-card',
  'channel-dock',
  'ranked-feed',
  'evidence-ledger',
  'chat-shell'
])
const REQUIRED_PAGE_COMPONENTS = [
  {
    surface: 'news_home',
    page: 'pages/news/news',
    requiredComponents: ['app-shell', 'page-frame', 'channel-dock', 'ranked-feed']
  },
  {
    surface: 'news_list_detail',
    page: 'pages/news/list',
    requiredComponents: ['app-shell', 'page-frame', 'article-list-board']
  },
  {
    surface: 'news_list_detail',
    page: 'pages/news/detail',
    requiredComponents: ['app-shell', 'page-frame', 'article-reader']
  },
  {
    surface: 'builds_tab',
    page: 'pages/builds/builds',
    requiredComponents: ['app-shell', 'page-frame', 'builds-tab-surface']
  },
  {
    surface: 'current_spec_workbench',
    page: 'pages/builds/workbench',
    requiredComponents: ['app-shell', 'page-frame', 'workbench-cockpit-surface']
  },
  {
    surface: 'talent_simulator',
    page: 'pages/builds/talent-simulator',
    requiredComponents: ['app-shell', 'page-frame', 'talent-tree-canvas']
  },
  {
    surface: 'gear_detail',
    page: 'pages/builds/detail',
    requiredComponents: ['app-shell', 'page-frame', 'gear-loadout-board', 'gear-config-sheet']
  },
  {
    surface: 'simc',
    page: 'pages/simulator/simc',
    requiredComponents: ['app-shell', 'page-frame', 'wow-panel', 'evidence-ledger', 'action-button', 'module-card']
  },
  {
    surface: 'chickenbro',
    page: 'pages/simulator/simulator',
    requiredComponents: ['app-shell', 'page-frame', 'chickenbro-coach-surface', 'chat-shell']
  },
  {
    surface: 'chickenbro',
    page: 'pages/simulator/chickenbro',
    requiredComponents: ['app-shell', 'page-frame', 'chickenbro-coach-surface', 'chat-shell']
  },
  {
    surface: 'tasks',
    page: 'pages/simulator/tasks',
    requiredComponents: ['app-shell', 'page-frame', 'task-queue-board']
  },
  {
    surface: 'tasks',
    page: 'pages/simulator/task-detail',
    requiredComponents: ['app-shell', 'page-frame', 'task-result-report']
  },
  {
    surface: 'profile_templates',
    page: 'pages/profile/profile',
    requiredComponents: ['app-shell', 'page-frame', 'profile-identity-panel', 'template-library-board']
  }
]
const FORBIDDEN_COMPONENTS = new Set(['status-badge'])
const FORBIDDEN_CLASS_PATTERNS = [
  /\bpage-shell\b/,
  /\bpage-scroll\b/,
  /\bpage-content\b/,
  /\bsurface-material\b/,
  /\bsocket-material\b/,
  /\bstatus-badge\b/,
  /\bverdict-slab\b/,
  /\bverdict-status-badge\b/,
  /\breadiness-panel\b/,
  /\bmodule-card\b/,
  /\bworkbench-(hero|cockpit|entry|module|status|panel|frame|fact|content)\b/,
  /\bchat-(header|bubble|scroll|message|input|status|speaker|content|meta)\b/,
  /\btopic-drawer\b/,
  /\banswer-evidence\b/,
  /\btemplate-card\b/,
  /\bprofile-cockpit\b/,
  /\bquery-card\b/,
  /\bhero\b/,
  /\bpass3[67]-/
]
const FORBIDDEN_SOURCE_PATTERNS = [
  /assets\/generated\//,
  /ui-v2-1-slices/,
  /ui-redesign\/20260701/,
  /pass36/i,
  /pass37/i
]

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function resolvePath(filePath, root = ROOT) {
  return path.isAbsolute(filePath) ? filePath : path.join(root, filePath)
}

function exists(filePath, root = ROOT) {
  return fs.existsSync(resolvePath(filePath, root))
}

function readText(filePath, root = ROOT) {
  return fs.readFileSync(resolvePath(filePath, root), 'utf8')
}

function readJson(filePath, root = ROOT) {
  return JSON.parse(readText(filePath, root))
}

function extractTags(wxml) {
  const tags = []
  const pattern = /<\s*([a-z][a-z0-9-]*)\b/g
  let match
  while ((match = pattern.exec(wxml)) !== null) {
    tags.push(match[1])
  }
  return tags
}

function extractClasses(wxml) {
  const classes = []
  const pattern = /\bclass\s*=\s*"([^"]+)"/g
  let match
  while ((match = pattern.exec(wxml)) !== null) {
    classes.push(match[1])
  }
  return classes
}

function usingComponents(pageJson) {
  return pageJson && typeof pageJson.usingComponents === 'object' && pageJson.usingComponents
    ? pageJson.usingComponents
    : {}
}

function inspectPage(pageSpec, root) {
  const pageBase = pageSpec.page
  const wxmlPath = `${pageBase}.wxml`
  const wxssPath = `${pageBase}.wxss`
  const jsonPath = `${pageBase}.json`
  const violations = []

  if (!exists(wxmlPath, root)) violations.push('wxml_exists')
  if (!exists(jsonPath, root)) violations.push('json_exists')
  if (!exists(wxssPath, root)) violations.push('wxss_exists')
  if (violations.length) {
    return {
      ...pageSpec,
      wxmlPath,
      wxssPath,
      jsonPath,
      pageAdoptionReady: false,
      violations
    }
  }

  let wxml
  let wxss
  let pageJson
  try {
    wxml = readText(wxmlPath, root)
    wxss = readText(wxssPath, root)
    pageJson = readJson(jsonPath, root)
  } catch (error) {
    return {
      ...pageSpec,
      wxmlPath,
      wxssPath,
      jsonPath,
      pageAdoptionReady: false,
      violations: [`read_or_parse_error:${error.message}`]
    }
  }

  const tags = extractTags(wxml)
  const customTags = Array.from(new Set(tags.filter((tag) => !BUILT_IN_TAGS.has(tag))))
  const pageComponents = usingComponents(pageJson)
  const componentKeys = Object.keys(pageComponents)
  const primitiveTags = tags.filter((tag) => BUILT_IN_TAGS.has(tag))
  const directImageCount = tags.filter((tag) => tag === 'image').length
  const forbiddenComponents = customTags.filter((tag) => FORBIDDEN_COMPONENTS.has(tag))
  const forbiddenClasses = extractClasses(wxml)
    .filter((classValue) => FORBIDDEN_CLASS_PATTERNS.some((pattern) => pattern.test(classValue)))
  const forbiddenSources = [wxml, wxss]
    .flatMap((source, sourceIndex) => {
      return FORBIDDEN_SOURCE_PATTERNS
        .filter((pattern) => pattern.test(source))
        .map((pattern) => `${sourceIndex === 0 ? 'wxml' : 'wxss'}:${pattern}`)
    })

  for (const component of pageSpec.requiredComponents) {
    if (!componentKeys.includes(component)) violations.push(`usingComponents_missing:${component}`)
    if (!customTags.includes(component)) violations.push(`wxml_tag_missing:${component}`)
  }
  for (const component of customTags) {
    if (!componentKeys.includes(component)) violations.push(`custom_tag_not_registered:${component}`)
  }
  if (forbiddenComponents.length) violations.push(`forbidden_component:${forbiddenComponents.join('|')}`)
  if (forbiddenClasses.length) violations.push(`page_private_geometry_classes:${forbiddenClasses.slice(0, 8).join('|')}`)
  if (forbiddenSources.length) violations.push(`forbidden_generated_or_reference_asset:${forbiddenSources.slice(0, 6).join('|')}`)
  if (directImageCount > 0) violations.push(`direct_image_tags:${directImageCount}`)
  if (primitiveTags.length > 12) violations.push(`too_many_page_primitives:${primitiveTags.length}`)
  const unknownComponents = customTags.filter((tag) => !ALLOWED_SHARED_COMPONENTS.has(tag) && !pageSpec.requiredComponents.includes(tag))
  if (unknownComponents.length) violations.push(`unexpected_component_tags:${unknownComponents.join('|')}`)

  return {
    ...pageSpec,
    wxmlPath,
    wxssPath,
    jsonPath,
    pageAdoptionReady: violations.length === 0,
    requiredComponents: pageSpec.requiredComponents,
    registeredComponents: componentKeys,
    customTags,
    primitiveTagCount: primitiveTags.length,
    directImageCount,
    violations
  }
}

function buildReport(args) {
  const root = optionValue(args, '--root', ROOT)
  const surface = optionValue(args, '--surface', '')
  const scopedPageComponents = surface
    ? REQUIRED_PAGE_COMPONENTS.filter((pageSpec) => pageSpec.surface === surface)
    : REQUIRED_PAGE_COMPONENTS
  const pages = scopedPageComponents.map((pageSpec) => inspectPage(pageSpec, root))
  const failingPages = pages.filter((page) => !page.pageAdoptionReady)
  return {
    status: failingPages.length ? 'page_adoption_invalid' : 'page_adoption_ready',
    pageAdoptionReady: failingPages.length === 0,
    root,
    surface: surface || 'all',
    pageCount: pages.length,
    failingPageCount: failingPages.length,
    requiredPageComponents: REQUIRED_PAGE_COMPONENTS,
    pages,
    missingRequirements: failingPages.length
      ? ['page_adoption_not_ready', ...failingPages.map((page) => `${page.page}:${page.violations[0]}`)]
      : [],
    nonPromotion: [
      'not target_locked',
      'not active_implementation_permit',
      'not page_integration',
      'not runtime_verified',
      'not final_accepted'
    ]
  }
}

function main() {
  const args = process.argv.slice(2)
  const flags = new Set(args)
  const report = buildReport(args)

  if (flags.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`pageAdoptionReady=${report.pageAdoptionReady}\n`)
    process.stdout.write(`failingPageCount=${report.failingPageCount}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-adoption') && !report.pageAdoptionReady) {
    process.exitCode = 12
  }
}

main()

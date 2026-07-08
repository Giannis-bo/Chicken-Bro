const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function read(path) {
  return fs.readFileSync(path, 'utf8').toLowerCase().replace(/\r\n/g, '\n')
}

function readRaw(path) {
  return fs.readFileSync(path, 'utf8').replace(/\r\n/g, '\n')
}

function block(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `${selector} block should exist`)
  return match[1]
}

function assertNoBareCssValueLines(file) {
  const source = readRaw(file)
  const failures = []
  let continuingValue = false

  source.split('\n').forEach((line, index) => {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('/*') || trimmed.startsWith('*')) return

    const startsRule = trimmed.startsWith('@') || trimmed.includes('{') || trimmed === '}'
    const isProperty = /^[\w-]+(?:\s+[\w-]+)*\s*:/.test(trimmed)
    const isContinuation = continuingValue && !trimmed.includes('{')
    const isSelectorContinuation = /^[.#:\w\-\[\]\(\)'",=\s>+~]+,$/.test(trimmed)

    if (!startsRule && !isProperty && !isContinuation && !isSelectorContinuation) {
      failures.push(`${file}:${index + 1}: ${trimmed}`)
    }

    continuingValue = Boolean(
      trimmed &&
      !trimmed.includes('{') &&
      (trimmed.endsWith(':') || trimmed.endsWith(','))
    )
  })

  assert.deepEqual(failures, [], 'WXSS should not contain orphaned bare value lines')
}

test('global WXSS exposes the shared WoW mini-program design tokens', () => {
  const css = read('app.wxss')
  const tokens = [
    '--wow-bg',
    '--wow-panel',
    '--wow-panel-warm',
    '--wow-gold',
    '--wow-verified',
    '--wow-reference',
    '--wow-blocked',
    '--wow-stale'
  ]

  for (const token of tokens) {
    assert.match(css, new RegExp(`${token}:`), `${token} should be defined`)
  }

  const pageBlock = block(css, 'page')
  const heroBlock = block(css, '.hero')
  assert.match(pageBlock, /background:\s*#060606;[\s\S]*background:\s*var\(--wow-bg\);/)
  assert.match(pageBlock, /color:\s*#e1e2e5;[\s\S]*color:\s*var\(--wow-text\);/)
  assert.match(pageBlock, /width:\s*100%;/)
  assert.match(pageBlock, /overflow-x:\s*hidden;/)
  assert.match(heroBlock, /border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.28\);[\s\S]*border:\s*1rpx solid var\(--wow-gold-border\);/)
  assert.match(heroBlock, /color:\s*#ffffff;[\s\S]*color:\s*var\(--wow-text-strong\);/)
  assert.match(heroBlock, /padding:\s*24rpx;/)
  assert.match(heroBlock, /border-radius:\s*12rpx;/)
  assert.match(block(css, '.section'), /padding:\s*20rpx;/)
  assert.match(block(css, '.section-header'), /gap:\s*16rpx;/)
  assert.match(block(css, '.page-shell'), /overflow:\s*hidden;/)
  assert.match(block(css, '.page-shell'), /isolation:\s*isolate;/)
  assert.match(block(css, '.page-shell'), /max-width:\s*100vw;/)
  assert.match(block(css, '.page-scroll'), /overflow:\s*hidden;/)
  assert.match(block(css, '.page-content'), /box-sizing:\s*border-box;/)
  assert.match(css, /view,\s*\ntext,\s*\nscroll-view,\s*\nimage,\s*\nbutton,\s*\npicker\s*\{[\s\S]*box-sizing:\s*border-box;/)
  assert.match(block(css, 'image'), /display:\s*block;/)
  assert.match(block(css, '.section-title'), /min-width:\s*0;/)
  assert.match(block(css, '.section-title'), /text-overflow:\s*ellipsis;/)
  assert.match(block(css, '.section-action'), /max-width:\s*48%;/)
  assert.match(block(css, '.section-action'), /text-overflow:\s*ellipsis;/)
})

test('UI v2.1 shell keeps runtime chrome and imagegen material layers separated', () => {
  const sourceFiles = [
    'components/navigation-bar/navigation-bar.js',
    'components/navigation-bar/navigation-bar.wxml',
    'components/navigation-bar/navigation-bar.wxss',
    'pages/news/news.wxml',
    'pages/news/news.wxss',
    'pages/builds/builds.wxml',
    'pages/builds/builds.wxss',
    'pages/builds/workbench.wxml',
    'pages/builds/workbench.wxss'
  ]

  for (const file of sourceFiles) {
    const source = readRaw(file)
    assert.doesNotMatch(source, /captureClock|showCaptureCapsule|capture-status|capture-capsule|weui-navigation-bar__capture/)
    assert.doesNotMatch(source, /battery|wifi|wi-fi|wifo|9:41|22:43|电量|假状态栏|模拟状态栏|假手机状态|系统状态栏|phone chrome/i)
    assert.doesNotMatch(source, /full_layout_reference|generated_status_icon_reference/)
  }

  const materialLayerBudgets = {
    'pages/news/news.wxml': 11,
    'pages/builds/builds.wxml': 8,
    'pages/builds/workbench.wxml': 6
  }
  for (const [file, maxCount] of Object.entries(materialLayerBudgets)) {
    const count = (readRaw(file).match(/surface-material/g) || []).length
    assert.ok(count <= maxCount, `${file} should keep imagegen material layers within the component foundation budget`)
  }
  assert.doesNotMatch(readRaw('pages/builds/builds.wxml'), /builds-hero-module-material|workbench-module-row-material|query-row-material/)
  assert.doesNotMatch(readRaw('pages/builds/workbench.wxml'), /module-card-material|evidence-row-material|workbench-identity-side-material|verdict-slab-stage-material|verdict-slab-smoke-material/)

  const productionAssetManifest = JSON.parse(
    fs.readFileSync('assets/generated/ui-v2-1-slices/20260703/strict-production-manifest.json', 'utf8')
  )
  const productionManifestText = JSON.stringify(productionAssetManifest)
  assert.doesNotMatch(
    productionManifestText,
    /workbench_identity_panel_material|workbench_verdict_stage_material|workbench_verdict_slab_material|workbench_evidence_frame_material|builds_workflow_row_material/,
    'production manifest should not bless factual or obsolete per-row material stacking'
  )
  assert.match(
    productionManifestText,
    /panel_module_card_blue_v2\.png/,
    'module card frame assets are allowed as low-semantic component material only'
  )
  const referenceAssets = productionAssetManifest.referenceOnlyAssets || []
  assert.ok(referenceAssets.length > 0, 'reference-only imagegen assets should be declared')
  for (const asset of referenceAssets) {
    const basename = asset.split('/').pop()
    assert.ok(basename, `reference asset ${asset} should have a basename`)
    for (const file of sourceFiles) {
      assert.doesNotMatch(
        readRaw(file),
        new RegExp(basename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')),
        `${file} must not render reference-only imagegen asset ${basename}`
      )
    }
  }

  assert.doesNotMatch(readRaw('pages/news/news.wxml'), /scroll-y\s+type="list"/)
  assert.doesNotMatch(readRaw('pages/builds/workbench.wxml'), /scroll-y\s+type="list"/)

  const pageWxmlFiles = [
    'pages/news/news.wxml',
    'pages/news/list.wxml',
    'pages/news/detail.wxml',
    'pages/builds/builds.wxml',
    'pages/builds/workbench.wxml',
    'pages/builds/intel.wxml',
    'pages/builds/talent-simulator.wxml',
    'pages/builds/detail.wxml',
    'pages/simulator/simulator.wxml',
    'pages/simulator/simc.wxml',
    'pages/simulator/chickenbro.wxml',
    'pages/simulator/wcl.wxml',
    'pages/simulator/tasks.wxml',
    'pages/simulator/task-detail.wxml',
    'pages/profile/profile.wxml',
    'pages/pve/pve.wxml',
    'pages/pve/detail.wxml'
  ]
  pageWxmlFiles.forEach((file) => {
    assert.doesNotMatch(
      readRaw(file),
      /<scroll-view\b[^>]*\btype="list"/,
      `${file} should not put the page-level scroller on Skyline list compositor`
    )
  })

  const navCss = readRaw('components/navigation-bar/navigation-bar.wxss')
  const navButtonBlock = block(navCss, '.weui-navigation-bar__buttons')
  assert.doesNotMatch(navButtonBlock, /safe-area-inset-top/)
  assert.match(block(navCss, '.weui-navigation-bar'), /--status-bar-height:\s*0px;/)
  assert.match(block(navCss, '.weui-navigation-bar'), /z-index:\s*100;/)
  assert.match(block(navCss, '.weui-navigation-bar'), /contain:\s*layout paint style;/)
  assert.match(block(navCss, '.weui-navigation-bar__inner'), /padding-top:\s*var\(--status-bar-height\);/)
  assert.match(block(navCss, '.weui-navigation-bar__inner'), /overflow:\s*hidden;/)
  assert.doesNotMatch(block(navCss, '.weui-navigation-bar__inner'), /env\(safe-area-inset-top\)/)

  const workbenchCss = readRaw('pages/builds/workbench.wxss')
  assert.match(block(workbenchCss, '.workbench-shell .workbench-content'), /padding:\s*20rpx\s+0\s+var\(--wow-tabbar-space\);/)
  assert.match(workbenchCss, /\.workbench-hero,[\s\S]*\.readiness-panel,[\s\S]*\.module-band,[\s\S]*\.evidence-section[\s\S]*width:\s*calc\(100% - 48rpx\);[\s\S]*margin-left:\s*24rpx;[\s\S]*margin-right:\s*24rpx;/)
  assert.match(workbenchCss, /@media \(max-width:\s*380px\)[\s\S]*\.workbench-shell \.workbench-content\s*\{[\s\S]*padding-left:\s*0;/)
  assert.match(workbenchCss, /@media \(max-width:\s*380px\)[\s\S]*\.workbench-shell \.workbench-content\s*\{[\s\S]*padding-right:\s*0;/)
  assert.match(workbenchCss, /@media \(max-width:\s*380px\)[\s\S]*\.workbench-hero,[\s\S]*\.readiness-panel,[\s\S]*\.module-band,[\s\S]*\.evidence-section[\s\S]*width:\s*calc\(100% - 48rpx\);[\s\S]*margin-left:\s*24rpx;[\s\S]*margin-right:\s*24rpx;/)
  assert.match(block(workbenchCss, '.workbench-control-strip'), /position:\s*relative;/)
  assert.doesNotMatch(block(workbenchCss, '.workbench-control-strip'), /position:\s*absolute;/)
  assert.match(block(workbenchCss, '.workbench-control-strip'), /width:\s*100%;/)
  assert.match(block(workbenchCss, '.module-card'), /overflow:\s*hidden;/)
  const moduleTextBlock = block(workbenchCss, '.module-title,\n.module-metric,\n.module-desc,\n.module-link,\n.module-status')
  assert.match(moduleTextBlock, /overflow:\s*hidden;/)
  assert.match(moduleTextBlock, /text-overflow:\s*ellipsis;/)
  assert.match(block(workbenchCss, '.module-title'), /white-space:\s*nowrap;/)
  assert.match(block(workbenchCss, '.module-metric'), /white-space:\s*nowrap;/)

  const newsCss = [
    readRaw('components/channel-dock/channel-dock.wxss'),
    readRaw('components/ranked-feed/ranked-feed.wxss'),
    readRaw('pages/news/news.wxss')
  ].join('\n')
  assert.match(block(newsCss, '.focus-row'), /grid-template-columns:\s*52rpx\s+116rpx\s+minmax\(0,\s*1fr\)\s+32rpx;/)
  assert.match(block(newsCss, '.focus-head'), /overflow:\s*hidden;/)
  assert.match(block(newsCss, '.focus-title'), /min-width:\s*0;/)
  assert.match(block(newsCss, '.focus-title'), /white-space:\s*nowrap;/)
  assert.match(block(newsCss, '.focus-badge'), /max-width:\s*74rpx;/)
  assert.match(newsCss, /(^|\n)\.focus-channel\s*\{[\s\S]*display:\s*none;/)
  assert.match(block(newsCss, '.focus-meta-row'), /overflow:\s*hidden;/)
  assert.match(block(newsCss, '.focus-meta'), /text-overflow:\s*ellipsis;/)
  assert.match(block(newsCss, '.news-command-heading'), /overflow:\s*hidden;/)
  assert.match(block(newsCss, '.news-command-link'), /max-width:\s*120rpx;/)
  assert.match(block(newsCss, '.news-command-status'), /text-overflow:\s*ellipsis;/)

  ;[
    'components/navigation-bar/navigation-bar.wxss',
    'pages/news/news.wxss',
    'pages/builds/builds.wxss',
    'pages/builds/workbench.wxss'
  ].forEach(assertNoBareCssValueLines)
})

test('top-level module heroes use black iron and gold as the dominant visual system', () => {
  const heroChecks = [
    ['pages/builds/builds.wxss', '.builds-spec-console', /#080807/, /#8b3ff5\s+150%/],
    ['pages/pve/pve.wxss', '.pve-hero', /#17120d/, /#7a1116\s+0%/],
    ['pages/simulator/wcl.wxss', '.wcl-hero', /#17120d/, /#3a2a0b\s+0%/]
  ]

  for (const [file, selector, expected, oldDominant] of heroChecks) {
    const heroBlock = block(read(file), selector)
    assert.match(heroBlock, expected, `${selector} should use the shared warm panel base`)
    assert.doesNotMatch(heroBlock, oldDominant, `${selector} should keep class color as accent only`)
  }

  const chickenbroSurface = block(read('components/chickenbro-coach-surface/chickenbro-coach-surface.wxss'), '.wow-chickenbro-surface')
  const chatShell = block(read('components/chat-shell/chat-shell.wxss'), '.wow-chat-shell')
  assert.match(chickenbroSurface, /#050504;/)
  assert.match(chatShell, /background:\s*#050504;/)
  assert.match(block(read('pages/simulator/simulator.wxss'), '.chickenbro-panel'), /border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.34\);/)
})

test('news and home module surfaces stay compact enough for mini-program first screens', () => {
  const newsCss = read('pages/news/news.wxss')
  assert.match(block(newsCss, '.news-swiper'), /height:\s*430rpx;/)
  assert.match(block(newsCss, '.banner-card'), /height:\s*430rpx;/)

  const buildsCss = read('pages/builds/builds.wxss')
  assert.match(block(buildsCss, '.query-section'), /height:\s*499rpx;/)
  assert.match(block(buildsCss, '.query-card'), /flex:\s*1;/)
  assert.match(block(buildsCss, '.query-card'), /min-height:\s*80rpx;/)

  const tasksCss = read('pages/simulator/tasks.wxss')
  assert.match(block(tasksCss, '.task-loading,\n.task-empty'), /padding:\s*24rpx;/)

  const pveCss = read('pages/pve/pve.wxss')
  assert.match(block(pveCss, '.zone-item'), /min-height:\s*136rpx;/)

  const chatShellCss = read('components/chat-shell/chat-shell.wxss')
  assert.match(block(chatShellCss, '.wow-chat-shell__inputbar'), /grid-template-columns:\s*auto\s+minmax\(0,\s*1fr\)\s+auto;/)
  assert.match(block(chatShellCss, '.wow-chat-shell__bubble'), /max-width:\s*86%;/)
  assert.match(block(chatShellCss, '.wow-chat-shell__bubble'), /padding:\s*18rpx;/)
})

test('primary form actions stay inside the compact 72rpx button rhythm', () => {
  const checks = [
    ['pages/simulator/simc.wxss', '.confirm-button,\n.submit-button'],
    ['pages/simulator/wcl.wxss', '.submit-button']
  ]

  for (const [file, selector] of checks) {
    const css = read(file)
    const buttonBlock = block(css, selector)
    assert.match(buttonBlock, /min-height:\s*72rpx;/, `${selector} in ${file} should be 72rpx high`)
    assert.doesNotMatch(buttonBlock, /line-height:\s*84rpx;/, `${selector} in ${file} should not keep 84rpx line height`)
  }

  const chatShellCss = read('components/chat-shell/chat-shell.wxss')
  assert.match(block(chatShellCss, '.wow-chat-shell__input'), /height:\s*72rpx;/)
  assert.match(block(chatShellCss, '.wow-chat-shell__context-action,\n.wow-chat-shell__topic-button,\n.wow-chat-shell__send'), /min-height:\s*48rpx;/)
})

test('gear replacement sheet keeps apply action in the compact sheet rhythm', () => {
  const css = read('pages/builds/detail.wxss')
  const applyBlock = block(css, '.gear-apply-button')
  assert.match(applyBlock, /width:\s*100%;/)
  assert.match(applyBlock, /min-height:\s*64rpx;/)
  assert.match(applyBlock, /line-height:\s*64rpx;/)
  assert.doesNotMatch(applyBlock, /min-width:\s*156rpx;/)
  assert.doesNotMatch(applyBlock, /min-height:\s*72rpx;/)
})

test('gear replacement sheet keeps candidate detail action fixed and narrow', () => {
  const css = read('pages/builds/detail.wxss')
  const actionBlock = block(css, '.gear-candidate-action')
  const detailButtonBlock = block(css, '.gear-candidate-detail-button')
  assert.match(actionBlock, /width:\s*96rpx;/)
  assert.match(detailButtonBlock, /width:\s*86rpx;/)
  assert.match(detailButtonBlock, /min-height:\s*40rpx;/)
  assert.doesNotMatch(detailButtonBlock, /padding:\s*0\s+12rpx;/)
})

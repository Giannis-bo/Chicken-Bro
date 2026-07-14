const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { buildSpecializationHomePayload } = require('../server/builds/home-payload')

function assertNoIgnoredGeneratedRuntimeAssets(wxml) {
  assert.doesNotMatch(
    wxml,
    /assets\/generated/,
    'release runtime WXML must not reference generated assets that are ignored from the upload package'
  )
}

function compactViewportRules(css) {
  const marker = '@media (max-width: 380px) {'
  const index = css.indexOf(marker)
  assert.notEqual(index, -1, 'compact viewport media rules should exist')
  return css.slice(index)
}

function cssBlock(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`))
  assert.ok(match, `Missing CSS block for ${selector}`)
  return match[1]
}

function loadBuildsDetailPageConfig(options = {}) {
  const source = fs.readFileSync('pages/builds/detail.js', 'utf8') + (options.exposeDetailHelpers ? `
globalThis.__detailHelpers = {
  normalizedEnhancementBySlot,
  optionIdentityEnhancementBySlot,
  enhancementRecordSelectedCount,
  compactEnhancementRecord,
  enhancementOptionSelected,
  enhancementSelectionFromOption,
  removeEnhancementType,
  prunedEnhancementBySlot,
  buildGearEnhancementSheet,
  communityTemplateRawEnhancementBySlot,
  reconcileCommunityTemplateEnhancements
}
` : '')
  const sandbox = {
    console,
    Page(config) {
      sandbox.pageConfig = config
    },
    wx: {
      navigateTo(route) {
        if (Array.isArray(options.navigations)) options.navigations.push(route || {})
      },
      redirectTo() {},
      setStorageSync(key, value) {
        if (Array.isArray(options.storageWrites)) options.storageWrites.push({ key, value })
      },
      showToast(toast) {
        if (Array.isArray(options.toasts)) options.toasts.push(toast || {})
      }
    },
    require(modulePath) {
      if (modulePath === './builds-api') {
        return {
          fallbackBuildsHome: () => ({
            quickActions: [{ key: 'gear', title: '装备模拟', desc: '' }],
            classOptions: [],
            trustedSources: []
          }),
          fallbackBuildsDetail: () => ({
            details: {
              talents: { coreTalents: [], importCode: '' },
              gear: {}
            }
          }),
          requestBuildsDetail: options.requestBuildsDetail || (() => Promise.resolve({ payload: null })),
          requestBuildsHome: options.requestBuildsHome || (() => Promise.resolve({ payload: null }))
        }
      }
      if (modulePath === './websim-api') {
        return {
          requestWebsimGear: options.requestWebsimGear || (() => Promise.resolve({ payload: {} })),
          requestWebsimGearResolve: options.requestWebsimGearResolve || (() => Promise.resolve({ payload: null, fromFallback: true })),
          requestWebsimGearStatSnapshot: options.requestWebsimGearStatSnapshot || options.requestWebsimGearStats || (() => Promise.resolve({ payload: null, fromFallback: true, offline: true })),
          requestWebsimTalentImport: options.requestWebsimTalentImport || (() => Promise.resolve({ payload: {} })),
          requestWebsimTalents: options.requestWebsimTalents || (() => Promise.resolve({ payload: {} }))
        }
      }
      if (modulePath === './gear-workbench-state') {
        return require('../pages/builds/gear-workbench-state')
      }
      if (modulePath === './gear-selection-intent') {
        return require('../pages/builds/gear-selection-intent')
      }
      if (modulePath === '../common/analytics-client') {
        return {
          trackEvent() {},
          trackPageLeave() {},
          trackPageView() {}
        }
      }
      if (modulePath === '../common/build-template-storage') {
        return {
          listBuildTemplates(type) {
            const templates = Array.isArray(options.storedTemplates) ? options.storedTemplates : []
            return type ? templates.filter((item) => item && item.type === type) : templates
          },
          syncBuildTemplate(record) {
            if (Array.isArray(options.savedTemplates)) options.savedTemplates.push(record)
            return Promise.resolve({ payload: { template: record || {} } })
          }
        }
      }
      if (modulePath === '../common/game-asset') {
        return require('../pages/common/game-asset')
      }
      throw new Error(`Unexpected require: ${modulePath}`)
    }
  }
  vm.runInNewContext(source, sandbox, { filename: 'pages/builds/detail.js' })
  if (options.exposeDetailHelpers) sandbox.pageConfig.__detailHelpers = sandbox.__detailHelpers
  return sandbox.pageConfig
}

const canonicalGearSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand'
]

function completeGearSelection(slots = canonicalGearSlots) {
  return slots.reduce((selection, slot, index) => {
    selection[slot] = {
      slot,
      simcSlot: slot,
      itemId: String(250000 + index),
      id: String(250000 + index),
      displayName: `Item ${slot}`,
      source: '测试首领 - 测试副本',
      sources: [{ label: '测试首领 - 测试副本', sourceType: 'dungeon' }],
      ilevel: 707,
      bonus_id: '12345',
      simcReady: true
    }
    return selection
  }, {})
}

function canonicalTestResolverContext() {
  return {
    contractRevision: 'gear-resolver-context-v1',
    selectionSchemaRevision: 'selection-intent-v1',
    authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' }
  }
}

function canonicalResolveTransport(selectionIntent, signature = 'sha256:test-resolved') {
  return Promise.resolve({
    httpStatus: 200,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'resolve-test',
      releaseContext: {},
      status: 'resolved',
      problems: [],
      data: {
        contractRevision: 'gear-resolved-snapshot-v1',
        status: 'verified',
        resolvedGearSignature: signature,
        dependencyVector: {},
        staticAttributes: {},
        setState: { itemSetCounts: {}, activeDynamicEffects: [] },
        aggregateLegality: { status: 'verified', problemCodes: [] },
        profileReadiness: { status: 'verified', simcReady: true },
        constraints: {},
        resolvedSlots: Object.keys((selectionIntent && selectionIntent.slots) || {}).reduce((slots, slot) => {
          slots[slot] = { itemLevel: 700, selectedOptions: {} }
          return slots
        }, {}),
        problems: []
      }
    }
  })
}

function canonicalEnhancementResolveTransport(selectionIntent, signature, constraintsBySlot, embellishmentMax = 2) {
  const intentSlots = (selectionIntent && selectionIntent.slots) || {}
  return Promise.resolve({
    httpStatus: 200,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: `resolve-${signature}`,
      releaseContext: {},
      status: 'resolved',
      problems: [],
      data: {
        contractRevision: 'gear-resolved-snapshot-v1',
        status: 'verified',
        resolvedGearSignature: signature,
        dependencyVector: {},
        staticAttributes: {},
        setState: { itemSetCounts: {}, activeDynamicEffects: [] },
        aggregateLegality: { status: 'verified', problemCodes: [] },
        profileReadiness: { status: 'verified', simcReady: true },
        constraints: { embellishmentMax, slots: constraintsBySlot || {} },
        resolvedSlots: Object.keys(intentSlots).reduce((slots, slot) => {
          const intent = intentSlots[slot] || {}
          slots[slot] = {
            itemLevel: 707,
            selectedOptions: {
              gemOptionIds: Array.isArray(intent.gemOptionIds) ? intent.gemOptionIds : [],
              enchantOptionId: intent.enchantOptionId || '',
              embellishmentOptionId: intent.embellishmentOptionId || ''
            }
          }
          return slots
        }, {}),
        problems: []
      }
    }
  })
}

function canonicalStatTransport(snapshot, statSignature = 'sha256:test-stat') {
  const verified = snapshot && snapshot.statStatus === 'verified'
  const blockers = Array.isArray(snapshot && snapshot.blockers) ? snapshot.blockers : []
  return {
    httpStatus: verified ? 200 : 422,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'stat-test',
      releaseContext: {},
      status: verified ? 'resolved' : 'blocked',
      data: verified ? { statSignature, statSnapshot: snapshot } : {},
      problems: blockers.map((title) => ({ kind: 'ILLEGAL_SELECTION', code: 'GEAR_STAT_BLOCKED', title }))
    }
  }
}

function pendingStatTransport(retryAfterMs = 1500) {
  return {
    httpStatus: 202,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'stat-pending',
      releaseContext: {},
      status: 'pending',
      data: { status: 'pending', statSignature: 'sha256:pending', retryAfterMs },
      problems: []
    }
  }
}

async function confirmGearTemplateSave(pageConfig, page, name) {
  pageConfig.saveGearTemplate.call(page)
  if (name !== undefined) {
    pageConfig.updateGearTemplateName.call(page, { detail: { value: name } })
  }
  await pageConfig.confirmSaveGearTemplate.call(page)
}

function loadTalentSimulatorPageConfig(options = {}) {
  const source = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const mocks = {
    profilePayload: null,
    savedTemplate: null,
    talentRequests: [],
    toasts: []
  }
  const sandbox = {
    console,
    Page(config) {
      sandbox.pageConfig = config
    },
    wx: {
      showToast(options) {
        mocks.toasts.push(options || {})
      }
    },
    require(modulePath) {
      if (modulePath === './builds-api') {
        return {
          fallbackBuildsHome: () => ({
            quickActions: [],
            classOptions: [{
              name: '法师',
              key: 'mage',
              specializations: [{
                id: '法师-冰霜',
                title: '冰霜',
                className: '法师',
                specName: '冰霜',
                websimClassKey: 'mage',
                websimSpecKey: 'frost'
              }]
            }],
            trustedSources: []
          }),
          fallbackBuildsDetail: () => ({
            className: '法师',
            specName: '冰霜',
            details: {
              talents: { coreTalents: [], importCode: '' },
              gear: {}
            }
          }),
          requestBuildsHome: () => Promise.resolve({ payload: null })
        }
      }
      if (modulePath === './websim-api') {
        return {
          requestWebsimBootstrap: () => Promise.resolve({ payload: options.bootstrapPayload || {} }),
          requestWebsimTalents: (params = {}) => {
            mocks.talentRequests.push(params)
            const key = `${params.classKey || ''}:${params.specKey || ''}:${params.heroKey || ''}`
            const payload = (options.talentPayloads && options.talentPayloads[key]) || options.defaultTalentPayload || {}
            return Promise.resolve({ payload })
          },
          requestWebsimProfile: (payload) => {
            mocks.profilePayload = payload
            return Promise.resolve({
              payload: {
                talentEncoding: {
                  status: 'encoded',
                  lines: ['talents=websim-code'],
                  errors: []
                }
              }
            })
          }
        }
      }
      if (modulePath === './talent-simulator-core') {
        const core = require('../pages/builds/talent-simulator-core')
        if (options.omitTemplatesForClass) {
          const { templatesForClass, ...rest } = core
          return rest
        }
        return core
      }
      if (modulePath === '../common/analytics-client') {
        return {
          trackEvent() {},
          trackPageLeave() {},
          trackPageView() {}
        }
      }
      if (modulePath === '../common/build-template-storage') {
        return {
          listBuildTemplates(type) {
            const templates = Array.isArray(options.storedTemplates) ? options.storedTemplates : []
            return type ? templates.filter((item) => item && item.type === type) : templates
          },
          syncBuildTemplate(record) {
            mocks.savedTemplate = record
            return Promise.resolve({ payload: { template: record } })
          }
        }
      }
      if (modulePath === '../common/game-asset') {
        return require('../pages/common/game-asset')
      }
      throw new Error(`Unexpected require: ${modulePath}`)
    }
  }
  vm.runInNewContext(source, sandbox, { filename: 'pages/builds/talent-simulator.js' })
  return { pageConfig: sandbox.pageConfig, mocks }
}

test('builds tab is renamed to specialization and removes legacy metrics row', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const tab = app.tabBar.list.find((item) => item.pagePath === 'pages/builds/builds')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')

  assert.equal(tab.text, '职业专精')
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /metric-card/)
})

test('builds page focuses on first-version query entries and opens talents in the native simulator', () => {
  const js = fs.readFileSync('pages/builds/builds.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const payload = buildSpecializationHomePayload()

  assert.deepEqual(
    payload.quickActions.map((item) => item.key),
    ['talents', 'gear', 'simc', 'tasks']
  )
  assert.match(wxml, /bindtap="openQueryPage"/)
  assert.doesNotMatch(wxml, /scroll-into-view="\{\{scrollTarget\}\}"/)
  assert.doesNotMatch(wxml, /id="task-section"/)
  assert.doesNotMatch(wxml, /class="task-section"/)
  assert.doesNotMatch(wxml, /wx:for="\{\{tasks\}\}"/)
  assert.match(js, /openQueryPage\(event\)/)
  assert.doesNotMatch(js, /openTaskDetail\(event\)/)
  assert.match(js, /wx\.navigateTo/)
  assert.match(js, /queryKey === 'talents'/)
  assert.match(js, /pages\/builds\/talent-simulator/)
  assert.match(js, /queryKey === 'simc'/)
  assert.match(js, /pages\/simulator\/simc/)
  assert.match(js, /queryKey === 'tasks'/)
  assert.match(js, /pages\/simulator\/tasks/)
  assert.doesNotMatch(js, /scrollTarget:\s*'task-section'/)
  assert.doesNotMatch(js, /requestSimulatorTasks/)
  assert.doesNotMatch(js, /simcReportSummary/)
  assert.doesNotMatch(js, /\/pages\/simulator\/task-detail\?id=/)
  assert.match(js, /encodeURIComponent\(queryKey \|\| ''\)/)
  assert.doesNotMatch(wxml, /query-window/)
  assert.doesNotMatch(wxml, /queryWindowVisible/)
  assert.doesNotMatch(wxml, /section-title">选择专精/)
  assert.doesNotMatch(wxml, /class="spec-grid"/)
  assert.doesNotMatch(wxml, /class="detail-panel"/)
})

test('builds tab promotes current spec workbench while keeping original module entrances', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/builds.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const workbenchWxml = fs.readFileSync('pages/builds/workbench.wxml', 'utf8')
  const workbenchJs = fs.readFileSync('pages/builds/workbench.js', 'utf8')
  const workbenchJson = fs.readFileSync('pages/builds/workbench.json', 'utf8')
  const workbenchState = fs.readFileSync('pages/builds/workbench-state.js', 'utf8')

  assert.ok(app.pages.includes('pages/builds/workbench'))
  assert.match(wxml, /class="workbench-entry"/)
  assert.match(wxml, /bindtap="openWorkbench"/)
  assert.match(js, /openWorkbench\(\)/)
  assert.match(js, /pages\/builds\/workbench\?spec=/)
  assert.match(js, /buildHomeOverview/)
  assert.match(js, /chips:\s*\[/)
  assert.match(js, /facts:\s*\[/)
  assert.match(js, /modules:\s*\[/)
  assert.match(js, /metaLabel:/)
  assert.match(js, /deferredVisualsReady:\s*false/)
  assert.match(js, /enableDeferredVisuals\(\)/)
  assert.match(js, /handleBuildsScroll\(event\)/)
  assert.match(js, /scrollTop > 96/)
  assert.doesNotMatch(js, /onReady\(\)[\s\S]*setTimeout\(\(\) => this\.enableDeferredVisuals/)
  assert.match(wxml, /bindscroll="handleBuildsScroll"/)
  assertNoIgnoredGeneratedRuntimeAssets(wxml)
  assert.doesNotMatch(wxml, /class="builds-shell-corner/)
  assert.doesNotMatch(wxml, /class="surface-material builds-spec-base-material"/)
  assert.doesNotMatch(wxml, /class="surface-material builds-spec-console-material"/)
  assert.doesNotMatch(wxml, /class="socket-material" src="\/assets\/generated/)
  assert.doesNotMatch(wxml, /class="surface-material workbench-panel-material"/)
  assert.doesNotMatch(wxml, /class="surface-material workbench-frame-material"/)
  assert.doesNotMatch(wxml, /class="surface-material workflow-frame-material"/)
  assert.match(wxml, /class="workbench-status-list workbench-stage-grid"/)
  assert.match(wxml, /class="workbench-entry-sigil"/)
  assert.match(wxml, /class="workbench-entry-facts"/)
  assert.match(wxml, /wx:for="\{\{workbenchEntry\.facts\}\}"/)
  assert.match(wxml, /wx:for="\{\{workbenchEntry\.modules\}\}"/)
  assert.match(wxml, /class="module-icon-socket"/)
  assert.match(wxml, /item\.metaLabel/)
  assert.match(wxml, /wx:for="\{\{quickActions\}\}"/)
  assert.match(wxml, /构筑流程/)
  assert.match(wxml, /输入 \/ 验证 \/ 追踪/)
  assert.match(wxml, /class="workflow-rail"/)
  assert.match(wxml, /class="workflow-dot"/)
  assert.match(wxml, /item\.phaseLabel/)
  assert.match(wxml, /item\.scopeLabel/)
  assert.match(wxml, /item\.evidenceLabel/)
  assert.match(wxml, /item\.actionLabel/)
  assert.match(wxml, /class="query-meta-row"/)
  assert.match(wxml, /class="query-action-dock"/)
  assert.match(wxml, /class="query-submeta"/)
  assertNoIgnoredGeneratedRuntimeAssets(wxml)
  assert.ok((wxml.match(/surface-material/g) || []).length <= 8, 'builds tab should not rebuild material layers per row')
  assert.doesNotMatch(wxml, /builds-hero-module-material|workbench-module-row-material|query-row-material/)
  assert.doesNotMatch(wxml, /builds-shell-bg|legacy-hero-material|legacy-entry-material|ui-v2-restoration/)
  assert.doesNotMatch(wxml, /深入模块|旧入口保留|进入查询/)
  assert.doesNotMatch(js, /能力 02/)
  assert.ok(wxml.indexOf('class="workbench-entry"') < wxml.indexOf('class="section query-section"'))
  assert.match(workbenchJs, /requestWebsimTalents/)
  assert.match(workbenchJs, /requestWebsimGear/)
  assert.match(workbenchJs, /listBuildTemplates\('talent'\)/)
  assert.match(workbenchJs, /listBuildTemplates\('gear'\)/)
  assert.match(workbenchJs, /fetchBuildTemplates\('talent'\)/)
  assert.match(workbenchJs, /fetchBuildTemplates\('gear'\)/)
  assert.match(workbenchJs, /onReady\(\)/)
  assert.match(workbenchJs, /startDeferredBoot/)
  assert.match(workbenchJs, /deferAfterFirstPaint/)
  assert.match(workbenchJs, /slimClassOptions/)
  assert.match(workbenchJs, /slimTalentsPayloadForWorkbench/)
  assert.match(workbenchJs, /slimGearPayloadForWorkbench/)
  assert.match(workbenchJs, /summarizeWorkbenchTemplates/)
  assert.match(workbenchJs, /deferredVisualsReady:\s*false/)
  assert.doesNotMatch(workbenchJs, /deferWorkbenchTask\(this, \d+, this\.enableDeferredVisuals\)/)
  assert.match(workbenchJs, /handleWorkbenchScroll/)
  assert.match(workbenchJs, /scrollTop > 96/)
  assert.match(workbenchJs, /deferWorkbenchTask\(this, 1800, this\.loadRemoteTemplates\)/)
  assert.match(workbenchJs, /talentsPayload: slimTalentsPayloadForWorkbench/)
  assert.match(workbenchJs, /gearPayload: slimGearPayloadForWorkbench/)
  assert.doesNotMatch(workbenchJs, /\.\.\.fallbackBuildsHome\(\)/)
  assert.doesNotMatch(workbenchJs, /\.\.\.payload,/)
  assert.match(workbenchJs, /workbenchQuery/)
  assert.match(workbenchJs, /pages\/simulator\/simc\?\$\{workbenchQuery\}/)
  assert.match(workbenchJs, /pages\/simulator\/chickenbro\?\$\{workbenchQuery\}/)
  assert.match(workbenchJs, /wx\.switchTab\(\{\s*url:\s*'\/pages\/profile\/profile'/)
  assert.match(workbenchWxml, /工作流状态/)
  assert.match(workbenchWxml, /class="module-card-grid"/)
  assertNoIgnoredGeneratedRuntimeAssets(workbenchWxml)
  assert.doesNotMatch(workbenchWxml, /class="socket-material" src="\/assets\/generated/)
  assert.match(workbenchWxml, /class="module-card \{\{item\.statusClass\}\}"/)
  assert.match(workbenchWxml, /class="module-card-top"/)
  assert.match(workbenchWxml, /item\.dockDesc/)
  assert.match(workbenchWxml, /class="workbench-control-strip"/)
  assert.match(workbenchWxml, /class="verdict-blocker-list"/)
  assert.match(workbenchWxml, /workbenchState\.secondaryBlockers\.length/)
  assert.match(workbenchWxml, /wx:for="\{\{workbenchState\.secondaryBlockers\}\}"/)
  assert.match(workbenchJson, /"status-visual":\s*"\/components\/status-visual\/status-visual"/)
  assert.match(workbenchWxml, /class="verdict-status-slot"[\s\S]*<status-visual[\s\S]*mode="layered"[\s\S]*shape="auto"[\s\S]*fill="\{\{true\}\}"/)
  assert.doesNotMatch(workbenchWxml, /verdict-status-window|verdict-status-label|verdict-status-meta/)
  assert.doesNotMatch(workbenchWxml, /status-badge|verdict-marker|verdict-status-badge|verdict-status-badge-art|statusEmblemUrl|verdict_status_badge_blocked_component/)
  assert.match(workbenchWxml, /workbenchState\.primaryAction\.label/)
  assert.match(workbenchWxml, /bindscroll="handleWorkbenchScroll"/)
  assert.doesNotMatch(workbenchWxml, /scroll-y\s+type="list"/)
  assert.match(workbenchWxml, /class="evidence-actions"/)
  assert.match(workbenchWxml, /class="template-count"/)
  assert.match(workbenchWxml, /workbenchState\.evidencePreviewRows/)
  assert.match(workbenchWxml, /class="evidence-list expanded"/)
  assert.ok((workbenchWxml.match(/surface-material/g) || []).length <= 6, 'workbench should keep imagegen material layers to major component foundations')
  assert.doesNotMatch(workbenchWxml, /module-card-material|evidence-row-material|workbench-identity-side-material|verdict-slab-stage-material|verdict-slab-smoke-material/)
  assert.doesNotMatch(workbenchWxml, /talentsPayload|gearPayload/)
  assert.doesNotMatch(workbenchWxml, /能力矩阵/)
  assert.doesNotMatch(workbenchWxml, /primary-action-material/)
  assert.doesNotMatch(workbenchWxml, /workbench-hero-material|state-strip-material|evidence-material|console-shell-bg|ui-v2-restoration|workbench_full_layout_reference/)
  assert.doesNotMatch(workbenchWxml, /workbench_generated_status_icon_reference/)
  assert.match(workbenchState, /gameAsset\.iconUrl/)
  assert.match(workbenchState, /iconFallback:\s*'Sim'/)
  assert.doesNotMatch(workbenchState, /statusAtomicUrl/)
  assert.doesNotMatch(workbenchState, /status_visual_.*shield_atomic\.png/)
  assert.doesNotMatch(workbenchState, /statusBadgeBaseUrl|statusEmblemUrl|verdict_status_badge_blocked_component|verdict_status_shield_base_v1/)
  assert.doesNotMatch(workbenchState, /iconFallback:\s*'S'/)
  assert.doesNotMatch(workbenchWxml, /DPS|综合评分|S 级|A级|提升优先级/)
})

test('builds and workbench compact viewport rules preserve dense component layouts', () => {
  const buildsCss = compactViewportRules(fs.readFileSync('pages/builds/builds.wxss', 'utf8'))
  const workbenchCss = compactViewportRules(fs.readFileSync('pages/builds/workbench.wxss', 'utf8'))

  assert.match(buildsCss, /\.builds-spec-console[\s\S]*grid-template-columns:\s*94rpx\s+minmax\(0,\s*1fr\);/)
  assert.match(buildsCss, /\.builds-hero-module-strip[\s\S]*gap:\s*4rpx;/)
  assert.match(buildsCss, /\.workbench-entry-top[\s\S]*grid-template-columns:\s*62rpx\s+minmax\(0,\s*1fr\)\s+96rpx;/)
  assert.match(buildsCss, /\.workbench-module-row[\s\S]*grid-template-columns:\s*54rpx\s+minmax\(0,\s*1fr\)\s+132rpx;/)
  assert.match(buildsCss, /\.query-card[\s\S]*grid-template-columns:\s*62rpx\s+minmax\(0,\s*1fr\)\s+116rpx;/)
  assert.match(buildsCss, /\.query-meta-row[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\);/)

  assert.match(workbenchCss, /\.workbench-title-row[\s\S]*grid-template-columns:\s*86rpx\s+minmax\(0,\s*1fr\)\s+82rpx;/)
  assert.match(workbenchCss, /\.workbench-shell \.workbench-content[\s\S]*padding-left:\s*0;[\s\S]*padding-right:\s*0;/)
  assert.match(workbenchCss, /\.workbench-hero,[\s\S]*\.readiness-panel,[\s\S]*\.module-band,[\s\S]*\.evidence-section[\s\S]*width:\s*calc\(100% - 48rpx\);[\s\S]*margin-left:\s*24rpx;[\s\S]*margin-right:\s*24rpx;/)
  assert.match(workbenchCss, /\.workbench-control-strip[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)\s+minmax\(0,\s*2\.1fr\);/)
  assert.match(workbenchCss, /\.picker-label[\s\S]*display:\s*none;/)
  assert.match(workbenchCss, /\.verdict-slab[\s\S]*min-height:\s*424rpx;/)
  assert.match(workbenchCss, /\.module-card-grid[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(workbenchCss, /\.module-card[\s\S]*grid-template-columns:\s*56rpx\s+minmax\(0,\s*1fr\)\s+64rpx;/)
  assert.match(workbenchCss, /\.module-title[\s\S]*text-align:\s*left;/)
  assert.match(workbenchCss, /\.evidence-row[\s\S]*grid-template-columns:\s*48rpx\s+minmax\(0,\s*1fr\)\s+minmax\(90rpx,\s*auto\)\s+12rpx;/)
  assert.match(workbenchCss, /\.evidence-list\.expanded \.evidence-row[\s\S]*grid-template-columns:\s*38rpx\s+minmax\(0,\s*1fr\)\s+minmax\(86rpx,\s*auto\)\s+12rpx;/)
  assert.match(workbenchCss, /\.evidence-status[\s\S]*min-width:\s*78rpx;[\s\S]*max-width:\s*92rpx;/)
  assert.match(workbenchCss, /\.evidence-list\.expanded \.evidence-status[\s\S]*min-width:\s*74rpx;[\s\S]*max-width:\s*86rpx;/)
})

test('query detail page is registered and uses dropdown pickers', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')

  assert.ok(app.pages.includes('pages/builds/detail'))
  assert.doesNotMatch(app.pages.join('\n'), /gear-simulator/)
  assert.match(wxml, /picker[\s\S]*range="\{\{classOptions\}\}"/)
  assert.match(wxml, /picker[\s\S]*range="\{\{specOptions\}\}"/)
  assert.match(wxml, /bindchange="selectClass"/)
  assert.match(wxml, /bindchange="selectSpec"/)
  assert.match(js, /onLoad\(options\)/)
  assert.match(js, /selectClass\(event\)/)
  assert.match(js, /selectSpec\(event\)/)
  assert.match(js, /defaultSpecId = '法师-冰霜'/)
})

test('query detail page has module-specific UI sections', () => {
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')

  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'talents'\}\}"/)
  assert.match(wxml, /class="talent-code-card"/)
  assert.match(wxml, /wx:if="\{\{activeDetail\.importCode\}\}"/)
  assert.match(wxml, /class="talent-chip-list"/)
  assert.match(wxml, /activeDetail\.coreTalents/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'gear'\}\}"/)
  assert.doesNotMatch(wxml, /class="gear-stat-panel"/)
  assert.match(wxml, /class="gear-slot-grid"/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'statWeights'\}\}"/)
  assert.match(wxml, /class="stat-bars"/)
  assert.match(wxml, /class="stat-scenario-tabs"/)
  assert.match(wxml, /activeStatRows/)
  assert.match(wxml, /statWeightValidation\.simcSuccessCount/)
  assert.match(wxml, /statWeightRecommendations/)
  assert.match(wxml, /wx:if="\{\{activeQueryKey == 'rotation'\}\}"/)
  assert.match(wxml, /class="rotation-timeline"/)
})

test('builds page uses the shared WoW specialization meta palette', () => {
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/builds.wxss', 'utf8')

  assert.match(wxml, /background="#111111"/)
  assert.match(wxml, /color="#FFFFFF"/)
  assert.match(css, /\.builds-shell[\s\S]*background:\s*#050504;/)
  assert.match(css, /\.builds-shell[\s\S]*isolation:\s*isolate;/)
  assert.match(css, /\.builds-shell::after[\s\S]*border-left:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.16\);/)
  assert.match(css, /\.builds-shell \.builds-content[\s\S]*padding:\s*12rpx\s+20rpx\s+calc\(var\(--wow-tabbar-space\) \+ 96rpx\);/)
  assert.match(css, /\.builds-spec-console[\s\S]*#080807/i)
  assert.match(css, /\.builds-spec-console[\s\S]*height:\s*266rpx;/)
  assert.match(css, /\.builds-spec-base-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.builds-spec-base-material[\s\S]*opacity:\s*1;/)
  assert.match(css, /\.builds-spec-console-material[\s\S]*width:\s*66%;[\s\S]*mix-blend-mode:\s*screen;/)
  assert.match(css, /\.builds-spec-console-material[\s\S]*opacity:\s*0\.72;/)
  assertNoIgnoredGeneratedRuntimeAssets(wxml)
  assert.doesNotMatch(wxml, /20260703\/builds_spec_identity_stage_material\.png/)
  assert.doesNotMatch(wxml, /20260703\/panel_builds_spec_console_deep_v3\.png/)
  assert.doesNotMatch(wxml, /20260703\/panel_status_list_wide_v2\.png/)
  assert.doesNotMatch(wxml, /20260702\/builds_spec_console_panel_material\.png/)
  assert.doesNotMatch(wxml, /20260703\/builds_workbench_entry_stage_material\.png/)
  assert.doesNotMatch(wxml, /20260702\/builds_workbench_frame_material\.png/)
  assert.doesNotMatch(wxml, /20260703\/panel_workflow_timeline_wide_v2\.png/)
  assert.doesNotMatch(wxml, /20260703\/builds_workflow_rail_material\.png/)
  assert.doesNotMatch(wxml, /20260703\/builds_workflow_row_material\.png/)
  assert.match(css, /\.builds-hero[\s\S]*#f8b700/i)
  assert.match(css, /\.builds-hero-chip-row[\s\S]*display:\s*flex;/)
  assert.match(css, /\.workbench-status-list[\s\S]*border:\s*0;/)
  assert.match(css, /\.workbench-status-list[\s\S]*background:\s*transparent;/)
  assert.match(css, /\.workbench-status-list[\s\S]*position:\s*relative;[\s\S]*grid-template-rows:\s*repeat\(4,\s*78rpx\);[\s\S]*margin-top:\s*14rpx;/)
  assert.doesNotMatch(cssBlock(css, '.workbench-status-list'), /position:\s*absolute;/)
  assert.doesNotMatch(css, /assets\/generated\/ui-v2-restoration/)
  assert.doesNotMatch(wxml, /ui-v2-restoration/)
  assert.doesNotMatch(css, /assets\/generated\/ui-redesign/)
  assert.doesNotMatch(css, /rgba\(139,\s*63,\s*245,\s*0\.16\)/i)
  assert.match(css, /\.workbench-entry-facts[\s\S]*grid-template-columns:\s*minmax\(0,\s*1\.28fr\)\s+minmax\(0,\s*1\.08fr\)\s+minmax\(0,\s*1fr\);/)
  assert.match(css, /\.workbench-entry-sigil[\s\S]*width:\s*70rpx;[\s\S]*height:\s*70rpx;/)
  assert.match(css, /\.workbench-fact[\s\S]*min-height:\s*68rpx;/)
  assert.match(css, /\.workbench-entry-facts[\s\S]*min-height:\s*68rpx;[\s\S]*height:\s*auto;/)
  assert.match(css, /\.workbench-entry-facts[\s\S]*opacity:\s*1;/)
  assert.match(css, /\.workbench-module-row[\s\S]*grid-template-columns:\s*58rpx minmax\(0,\s*1fr\) minmax\(176rpx,\s*0\.72fr\);/)
  assert.match(css, /\.workbench-module-row[\s\S]*height:\s*78rpx;[\s\S]*min-height:\s*78rpx;/)
  assert.match(css, /\.module-icon-socket[\s\S]*width:\s*52rpx;[\s\S]*height:\s*52rpx;/)
  assert.match(css, /\.workbench-entry[\s\S]*height:\s*586rpx;/)
  assert.match(css, /\.workbench-panel-material[\s\S]*inset:\s*0;/)
  assert.match(css, /\.workbench-panel-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.workbench-panel-material[\s\S]*opacity:\s*1;/)
  assert.match(css, /\.workbench-frame-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*screen;/)
  assert.match(css, /\.workbench-frame-material[\s\S]*opacity:\s*0\.12;/)
  assert.match(css, /\.module-verdict-text[\s\S]*text-overflow:\s*ellipsis;/)
  assert.match(css, /\.workbench-module-row[\s\S]*background:\s*[\s\S]*linear-gradient/)
  assert.match(css, /\.builds-spec-console::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.075\);/)
  assert.match(css, /\.module-icon-socket::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.16\);/)
  assert.match(css, /\.query-card[\s\S]*border-radius:\s*7rpx;/)
  assert.match(css, /\.query-card[\s\S]*border:\s*0;/)
  assert.match(css, /\.query-card[\s\S]*rgba\(5,\s*4,\s*3,\s*0\.18\);/)
  assert.match(css, /\.query-card[\s\S]*grid-template-columns:\s*78rpx minmax\(0,\s*1fr\) 146rpx;/)
  assert.match(css, /\.query-card[\s\S]*flex:\s*1;[\s\S]*min-height:\s*80rpx;/)
  assert.match(css, /\.query-icon-socket[\s\S]*width:\s*58rpx;[\s\S]*height:\s*58rpx;/)
  assert.match(css, /\.query-section[\s\S]*height:\s*499rpx;/)
  assert.match(css, /\.query-section::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.065\);/)
  assert.match(css, /\.workflow-frame-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.workflow-frame-material[\s\S]*opacity:\s*1;/)
  assert.match(css, /\.query-action-dock[\s\S]*min-height:\s*56rpx;/)
  assert.match(css, /\.query-meta-row[\s\S]*grid-template-columns:/)
  assert.match(css, /\.workflow-rail[\s\S]*flex-direction:\s*column;/)
  assert.match(css, /\.workflow-body[\s\S]*position:\s*absolute;[\s\S]*top:\s*76rpx;[\s\S]*bottom:\s*18rpx;/)
  assert.match(css, /\.workflow-rail-material[\s\S]*opacity:\s*0\.48;/)
  assert.match(css, /\.workflow-dot[\s\S]*width:\s*20rpx;[\s\S]*height:\s*20rpx;/)
  assert.match(css, /\.workflow-rail-material[\s\S]*mix-blend-mode:\s*screen;/)
  assert.match(css, /\.workflow-dot[\s\S]*opacity:\s*1;/)
  assert.match(css, /\.query-submeta[\s\S]*#f8b700/i)
  assert.doesNotMatch(css, /#edf3ff/i)
})

test('workbench page keeps readable game-furniture components without fake factual assets', () => {
  const css = fs.readFileSync('pages/builds/workbench.wxss', 'utf8')
  const wxml = fs.readFileSync('pages/builds/workbench.wxml', 'utf8')
  const statusVisualWxml = fs.readFileSync('components/status-visual/status-visual.wxml', 'utf8')
  const statusVisualCss = fs.readFileSync('components/status-visual/status-visual.wxss', 'utf8')

  assert.match(css, /\.workbench-hero::after,[\s\S]*\.readiness-panel::after,[\s\S]*\.module-band::after,[\s\S]*\.evidence-section::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.065\);/)
  assert.match(css, /\.spec-medallion::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.18\);/)
  assert.match(css, /\.workbench-shell[\s\S]*isolation:\s*isolate;/)
  assert.match(css, /\.workbench-shell::after[\s\S]*border-left:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.16\);/)
  assert.match(css, /\.workbench-shell \.workbench-content[\s\S]*padding:\s*20rpx\s+0\s+var\(--wow-tabbar-space\);/)
  assert.match(css, /@media \(max-width:\s*380px\)[\s\S]*\.workbench-shell \.workbench-content[\s\S]*padding-left:\s*0;[\s\S]*padding-right:\s*0;/)
  assert.match(css, /\.workbench-hero,[\s\S]*\.readiness-panel,[\s\S]*\.module-band,[\s\S]*\.evidence-section[\s\S]*width:\s*calc\(100% - 48rpx\);[\s\S]*margin-left:\s*24rpx;[\s\S]*margin-right:\s*24rpx;/)
  assert.match(css, /\.workbench-cockpit[\s\S]*min-height:\s*246rpx;/)
  assert.match(css, /\.workbench-cockpit-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.workbench-cockpit-material[\s\S]*opacity:\s*0\.16;/)
  assertNoIgnoredGeneratedRuntimeAssets(wxml)
  assert.doesNotMatch(wxml, /20260703\/panel_workbench_identity_deep_v3\.png/)
  assert.doesNotMatch(wxml, /20260702\/workbench_identity_panel_material\.png/)
  assert.match(css, /\.verdict-slab[\s\S]*min-height:\s*416rpx;/)
  assert.match(css, /\.verdict-slab-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.verdict-slab-material[\s\S]*opacity:\s*0\.22;/)
  assert.doesNotMatch(wxml, /20260705\/panel_workbench_verdict_base_no_status_v3\.png/)
  assert.doesNotMatch(wxml, /20260703\/panel_workbench_verdict_deep_v3\.png/)
  assert.doesNotMatch(wxml, /20260703\/panel_verdict_slab_wide_v2\.png/)
  assert.doesNotMatch(wxml, /20260703\/workbench_verdict_stage_material_v2\.png/)
  assert.doesNotMatch(wxml, /20260702\/workbench_verdict_slab_material\.png/)
  assert.match(css, /\.workbench-shell \.workbench-content[\s\S]*padding:\s*20rpx\s+0\s+var\(--wow-tabbar-space\);/)
  assert.match(css, /\.workbench-hero,[\s\S]*\.readiness-panel,[\s\S]*\.module-band,[\s\S]*\.evidence-section[\s\S]*width:\s*calc\(100% - 48rpx\);[\s\S]*margin-left:\s*24rpx;[\s\S]*margin-right:\s*24rpx;/)
  assert.match(css, /\.workbench-title-row[\s\S]*grid-template-columns:\s*98rpx minmax\(0,\s*1fr\) 104rpx;/)
  assert.match(css, /\.workbench-control-strip[\s\S]*position:\s*relative;[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)\s+minmax\(0,\s*2\.24fr\);[\s\S]*width:\s*100%;/)
  assert.match(css, /\.readiness-badge text,[\s\S]*\.scenario-tab text\s*\{[\s\S]*min-width:\s*0;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*white-space:\s*nowrap;/)
  assert.match(css, /\.scenario-tab\s*\{[\s\S]*min-width:\s*0;[\s\S]*overflow:\s*hidden;/)
  assert.match(css, /\.verdict-blocker-list[\s\S]*display:\s*grid;[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\);/)
  assert.match(css, /\.verdict-blocker-list[\s\S]*min-height:\s*0;/)
  assert.match(css, /\.verdict-head[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+132rpx;[\s\S]*padding-right:\s*0;/)
  assert.match(css, /\.verdict-status-slot[\s\S]*width:\s*124rpx;[\s\S]*height:\s*124rpx;[\s\S]*min-height:\s*124rpx;/)
  assert.match(css, /\.verdict-status-slot status-visual[\s\S]*display:\s*block;[\s\S]*width:\s*100%;[\s\S]*height:\s*100%;/)
  assert.match(statusVisualWxml, /class="wow-status-visual \{\{rootClass\}\} ext-class"/)
  assert.match(statusVisualWxml, /class="wow-status-visual__base-image"[\s\S]*mode="aspectFit"/)
  assert.match(statusVisualCss, /\.wow-status-visual\.shape-triangle \.wow-status-visual__base[\s\S]*border-bottom:\s*92rpx solid var\(--status-border\);/)
  assert.match(statusVisualCss, /\.wow-status-visual\.shape-circle \.wow-status-visual__base,[\s\S]*border-radius:\s*999rpx;/)
  assert.match(statusVisualCss, /\.wow-status-visual\.shape-diamond \.wow-status-visual__base,[\s\S]*transform:\s*rotate\(45deg\);/)
  assert.match(statusVisualCss, /\.wow-status-visual__glyph-stage[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;/)
  assert.match(statusVisualCss, /\.wow-status-visual\.state-blocked,[\s\S]*\.wow-status-visual\.state-error[\s\S]*--status-color:\s*#ff6b64;/)
  assert.match(statusVisualCss, /\.wow-status-visual\.size-hero[\s\S]*width:\s*188rpx;[\s\S]*height:\s*188rpx;/)
  assert.match(statusVisualCss, /\.wow-status-visual\.is-fill[\s\S]*width:\s*100%;[\s\S]*height:\s*100%;/)
  assert.doesNotMatch(css, /verdict-status-window|verdict-status-emblem|verdict-status-label|verdict-status-meta|verdict-sigil/)
  assert.doesNotMatch(wxml + css, /status-badge|verdict-marker|verdict-status-badge/)
  assert.doesNotMatch(statusVisualWxml + statusVisualCss, /verdict_status_badge_blocked_component|statusEmblemUrl/)
  assert.match(css, /\.verdict-blocker-list[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\);/)
  assert.match(css, /\.module-card-grid[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.module-card-grid[\s\S]*gap:\s*12rpx;/)
  assert.match(css, /\.module-card[\s\S]*grid-template-columns:\s*66rpx\s+minmax\(0,\s*1fr\)\s+86rpx;/)
  assert.match(css, /\.module-card[\s\S]*grid-template-rows:\s*minmax\(0,\s*1fr\);/)
  assert.match(css, /\.module-card[\s\S]*min-height:\s*128rpx;/)
  assert.doesNotMatch(css, /panel_module_card_gold_v2\.png/)
  assert.match(css, /@media \(max-width:\s*380px\)[\s\S]*\.module-card-grid[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /@media \(max-width:\s*380px\)[\s\S]*\.module-card[\s\S]*grid-template-columns:\s*56rpx\s+minmax\(0,\s*1fr\)\s+64rpx;/)
  assert.match(css, /\.game-icon-frame[\s\S]*width:\s*60rpx;[\s\S]*height:\s*60rpx;/)
  assert.match(css, /\.module-metric[\s\S]*font-size:\s*24rpx;/)
  assert.match(css, /\.module-status[\s\S]*max-width:\s*86rpx;[\s\S]*font-size:\s*16rpx;/)
  assert.match(css, /\.module-card-copy[\s\S]*grid-column:\s*2;[\s\S]*grid-row:\s*1;/)
  assert.match(css, /\.module-card-side[\s\S]*position:\s*relative;[\s\S]*align-items:\s*flex-end;/)
  assert.match(css, /\.module-desc[\s\S]*display:\s*block;/)
  assert.match(css, /\.verdict-kicker[\s\S]*display:\s*none;/)
  assert.match(css, /\.primary-action[\s\S]*align-self:\s*stretch;[\s\S]*width:\s*100%;[\s\S]*min-height:\s*78rpx;/)
  assert.doesNotMatch(css, /panel_cta_gold_v2\.png/)
  assert.doesNotMatch(css, /\.primary-action-material/)
  assert.match(css, /@media \(max-width:\s*380px\)[\s\S]*\.verdict-status-slot[\s\S]*width:\s*104rpx;[\s\S]*height:\s*104rpx;/)
  assert.match(css, /\.status-blocked\.verdict-slab \.readiness-title[\s\S]*color:\s*#ff6b64;/)
  assert.match(wxml, /mode="layered"/)
  assert.match(wxml, /shape="auto"/)
  assert.match(wxml, /fill="\{\{true\}\}"/)
  assert.doesNotMatch(wxml, /atomic-src="\{\{workbenchState\.statusAtomicUrl\}\}"/)
  assert.doesNotMatch(wxml, /glyph="\{\{workbenchState\.stateGlyph\}\}"|base-src="\{\{workbenchState\.statusBadgeBaseUrl\}\}"/)
  assert.match(css, /\.game-icon-frame::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.16\);/)
  assert.match(css, /\.module-band[\s\S]*min-height:\s*352rpx;/)
  assert.match(css, /\.module-band-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.module-band-material[\s\S]*opacity:\s*0\.1;/)
  assert.match(css, /\.module-desc[\s\S]*display:\s*block;/)
  assert.match(css, /\.module-link[\s\S]*display:\s*block;/)
  assert.match(css, /\.evidence-section[\s\S]*min-height:\s*640rpx;/)
  assert.match(css, /\.evidence-section-material[\s\S]*height:\s*100%;[\s\S]*mix-blend-mode:\s*normal;/)
  assert.match(css, /\.evidence-section-material[\s\S]*opacity:\s*0\.12;/)
  assert.doesNotMatch(wxml, /20260703\/panel_workbench_evidence_deep_v3\.png/)
  assert.doesNotMatch(wxml, /20260702\/workbench_evidence_frame_material\.png/)
  assert.match(css, /\.evidence-list[\s\S]*margin-top:\s*16rpx;/)
  assert.match(css, /\.evidence-row[\s\S]*min-height:\s*92rpx;/)
  assert.match(css, /\.evidence-list\.expanded \.evidence-row[\s\S]*min-height:\s*84rpx;/)
  assert.doesNotMatch(wxml, /20260703\/workbench_evidence_row_material_v2\.png/)
  assert.match(css, /\.evidence-row[\s\S]*background:\s*[\s\S]*linear-gradient/)
  assert.match(css, /\.evidence-row::after[\s\S]*background:\s*linear-gradient\(90deg,\s*transparent,\s*rgba\(248,\s*183,\s*0,\s*0\.16\),\s*transparent\);/)
  assert.match(css, /\.evidence-icon-socket::after[\s\S]*border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.14\);/)
  assert.doesNotMatch(wxml, /workbench_full_layout_reference/)
})

test('dormant specialization intel cards keep source evidence', () => {
  const wxml = fs.readFileSync('pages/builds/intel.wxml', 'utf8')

  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.publishedAt/)
  assert.match(wxml, /item\.analysisWindow/)
})

test('featured specialization section is dormant on the first-version specialization tab', () => {
  const js = fs.readFileSync('pages/builds/builds.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/builds.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/builds.wxss', 'utf8')
  const payload = buildSpecializationHomePayload()

  assert.equal(payload.featuredSpecializations.length, 0)
  assert.doesNotMatch(wxml, /热门专精/)
  assert.doesNotMatch(wxml, /swiper[\s\S]*class="intel-swiper"/)
  assert.doesNotMatch(wxml, /wx:for="\{\{featuredSpecializations\}\}"/)
  assert.doesNotMatch(wxml, /bindtap="openIntelPage"/)
  assert.doesNotMatch(js, /openIntelPage\(\)/)
  assert.doesNotMatch(js, /pages\/builds\/intel/)
  assert.doesNotMatch(css, /\.intel-swiper/)
})

test('specialization intel page is registered and renders all retrieved content', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/intel.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/intel.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/intel.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/builds/intel'))
  assert.match(js, /requestBuildsIntel/)
  assert.match(js, /fallbackBuildsIntel/)
  assert.match(wxml, /wx:for="\{\{items\}\}"/)
  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.analysisWindow/)
  assert.match(wxml, /bindtap="openSpecDetail"/)
  assert.match(js, /pages\/builds\/talent-simulator\?spec=/)
  assert.match(css, /\.intel-list/)
})

test('talent simulator page can open on a specialization selected from intel cards', () => {
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')

  assert.match(js, /options\.spec/)
  assert.match(js, /decodeURIComponent\(options\.spec\)/)
  assert.match(js, /findSpecSelection\(specId,/)
})

test('query detail page removes talent and gear simc entrances while keeping stat weights entry', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.doesNotMatch(wxml, /bindtap="openTalentSimc"/)
  assert.doesNotMatch(wxml, /模拟这套天赋/)
  assert.match(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /buildSimcContext\(\)/)
  assert.match(js, /statWeights:\s*\{/)
  assert.match(js, /weights:\s*this\.data\.activeStatRows/)
  assert.match(js, /wx\.setStorageSync\(SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.match(js, /\/pages\/simulator\/simc\?from=builds/)
  assert.match(js, /fail:\s*\(error\) =>/)
  assert.doesNotMatch(wxml, /class="simc-link-panel"/)
  assert.doesNotMatch(css, /\.simc-link-panel/)
})

test('stat weights detail page exposes scenario state without strong claim copy', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /statWeightScenarios\(activeDetail\)/)
  assert.match(js, /selectedStatWeightScenario/)
  assert.match(js, /setStatWeightScenario\(event\)/)
  assert.match(js, /builds_stat_weight_scenario_select/)
  assert.match(wxml, /wx:for="\{\{statWeightScenarios\}\}"/)
  assert.match(wxml, /bindtap="setStatWeightScenario"/)
  assert.match(wxml, /class="stat-source-state/)
  assert.match(wxml, /样本 \{\{statWeightValidation\.sampleCount/)
  assert.match(wxml, /Profile \{\{statWeightValidation\.profileCount/)
  assert.match(wxml, /SimC \{\{statWeightValidation\.simcSuccessCount/)
  assert.match(wxml, /当前不输出强结论/)
  assert.doesNotMatch(wxml, /最优|毕业|必堆/)
  assert.match(css, /\.stat-scenario-tab\.active/)
  assert.match(css, /\.stat-source-state\.verified/)
  assert.match(css, /\.stat-blocked-list/)
  assert.match(css, /\.stat-simc-button/)
})

test('native talent simulator page exposes WebSim tree controls and template persistence', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  assert.ok(app.pages.includes('pages/builds/talent-simulator'))
  assert.match(js, /game-asset/)
  assert.match(js, /requestWebsimBootstrap/)
  assert.match(js, /requestWebsimTalents/)
  assert.doesNotMatch(js, /requestWebsimProfile/)
  assert.match(js, /buildTalentViewModel/)
  assert.match(js, /tapTalentNode\(event\)/)
  assert.match(js, /selectChoiceTalent\(event\)/)
  assert.match(js, /resetTalents\(\)/)
  assert.match(js, /saveTalentTemplate\(\)/)
  assert.match(js, /confirmSaveTalentTemplate\(\)/)
  assert.match(js, /saveTemplateSheet/)
  assert.match(js, /defaultTalentTemplateTitle/)
  assert.match(js, /syncBuildTemplate/)
  assert.doesNotMatch(js, /openTalentImport\(\)/)
  assert.doesNotMatch(js, /applyTalentImport\(\)/)
  assert.doesNotMatch(js, /importSheet/)
  assert.doesNotMatch(js, /copyTalentExport\(\)/)
  assert.doesNotMatch(js, /openTalentSimc\(\)/)
  assert.doesNotMatch(js, /buildSimcContext\(\)/)
  assert.doesNotMatch(js, /SIMC_BUILD_CONTEXT_STORAGE_KEY/)
  assert.doesNotMatch(js, /talentEncoding\.lines/)
  assert.match(js, /activeTreeKey:\s*'class'/)
  assert.match(js, /treeNavItems/)
  assert.match(js, /activeSection/)
  assert.match(js, /selectTalentTree\(event\)/)
  assert.match(js, /node\.canSelect \? 'selectable' : ''/)
  assert.match(js, /`shape-\$\{node\.shape \|\| 'square'\}`/)
  assert.match(js, /line && line\.available \? 'available' : ''/)
  assert.doesNotMatch(js, /selectScenario\(event\)/)
  assert.doesNotMatch(js, /updateTalentSearch\(event\)/)
  assert.doesNotMatch(js, /clearTalentSearch\(\)/)
  assert.doesNotMatch(js, /searchTerm:\s*''/)
  assert.doesNotMatch(js, /searchCountText:/)
  assert.match(wxml, /class="talent-simulator-page"/)
  const toolbarMatch = wxml.match(/<view class="talent-toolbar">([\s\S]*?)<\/view>\s*<\/picker>\s*<\/view>/)
  assert.ok(toolbarMatch)
  assert.equal((toolbarMatch[1].match(/<picker/g) || []).length, 3)
  assert.match(toolbarMatch[1], />职业</)
  assert.match(toolbarMatch[1], />专精</)
  assert.match(toolbarMatch[1], />英雄天赋</)
  assert.doesNotMatch(toolbarMatch[1], />场景</)
  assert.doesNotMatch(wxml, /bindchange="selectScenario"/)
  assert.doesNotMatch(wxml, /range="\{\{scenarioOptions\}\}"/)
  assert.doesNotMatch(wxml, /class="talent-search-panel"/)
  assert.doesNotMatch(wxml, /class="talent-search-input"/)
  assert.doesNotMatch(wxml, /placeholder="搜索天赋"/)
  assert.doesNotMatch(wxml, /bindinput="updateTalentSearch"/)
  assert.doesNotMatch(wxml, /bindtap="clearTalentSearch"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /wx:for="\{\{treeNavItems\}\}"/)
  assert.match(wxml, /class="\{\{item\.tabClass\}\}"/)
  assert.match(wxml, /class="active-tree-panel/)
  assert.match(wxml, /activeSection\.nodes/)
  assert.match(wxml, /class="\{\{item\.linkClass\}\}"/)
  assert.match(wxml, /bindtap="tapTalentNode"/)
  assert.match(wxml, /bindtap="resetTalents"/)
  assert.match(wxml, /bindtap="openCommunityTemplates"/)
  assert.match(wxml, /bindtap="saveTalentTemplate"/)
  assert.match(wxml, /saveTemplateSheet\.visible/)
  assert.match(wxml, /bindinput="updateTemplateName"/)
  assert.match(wxml, /bindtap="confirmSaveTalentTemplate"/)
  assert.doesNotMatch(wxml, /bindtap="openTalentImport"/)
  assert.doesNotMatch(wxml, /importSheet\.visible/)
  assert.doesNotMatch(wxml, /bindtap="copyTalentExport"/)
  assert.doesNotMatch(wxml, /bindtap="openTalentSimc"/)
  assert.doesNotMatch(wxml, />复制</)
  assert.doesNotMatch(wxml, /带去 SimC/)
  assert.match(wxml, /choiceSheet/)
  assert.match(wxml, /nodeDetailSheet/)
  assert.match(css, /\.talent-simulator-page\s*\{[\s\S]*display:\s*flex;[\s\S]*flex-direction:\s*column;[\s\S]*height:\s*100vh;[\s\S]*overflow:\s*hidden;[\s\S]*\}/)
  assert.match(css, /\.page-scroll\s*\{[\s\S]*flex:\s*1;[\s\S]*min-height:\s*0;[\s\S]*height:\s*0;[\s\S]*overflow:\s*hidden;[\s\S]*\}/)
  assert.doesNotMatch(css, /\.page-scroll\s*\{\s*height:\s*100vh;\s*\}/)
  assert.match(css, /\.tree-tabs/)
  assert.match(css, /\.talent-toolbar\s*\{[\s\S]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.toolbar-picker\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*min-height:\s*54rpx;[\s\S]*\}/)
  assert.match(css, /\.picker-label\s*\{[\s\S]*flex-shrink:\s*0;[\s\S]*\}/)
  assert.match(css, /\.picker-value\s*\{[\s\S]*margin-top:\s*0;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(css, /\.tree-tab\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*min-height:\s*64rpx;[\s\S]*\}/)
  assert.match(css, /\.tree-tab-subtitle\s*\{[\s\S]*flex:\s*1;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(wxml, /class="active-tree-separator"/)
  assert.match(css, /\.active-tree-head\s*\{[\s\S]*align-items:\s*center;[\s\S]*padding:\s*12rpx 18rpx;[\s\S]*\}/)
  assert.match(css, /\.active-tree-title-wrap\s*\{[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*overflow:\s*hidden;[\s\S]*\}/)
  assert.match(css, /\.active-tree-title\s*\{[\s\S]*margin-top:\s*0;[\s\S]*white-space:\s*nowrap;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.match(css, /\.active-tree-subtitle\s*\{[\s\S]*margin-top:\s*0;[\s\S]*white-space:\s*nowrap;[\s\S]*text-overflow:\s*ellipsis;[\s\S]*\}/)
  assert.doesNotMatch(css, /\.talent-search-panel/)
  assert.doesNotMatch(css, /\.talent-search-input/)
  assert.doesNotMatch(css, /\.search-clear-button/)
  assert.match(css, /\.active-tree-panel/)
  assert.match(css, /\.mobile-action-bar/)
  assert.match(css, /\.talent-node\.selected/)
  assert.match(css, /\.talent-node\.locked/)
  assert.match(css, /\.talent-page-content\s*\{[\s\S]*padding:\s*20rpx 22rpx calc\(228rpx \+ env\(safe-area-inset-bottom\)\);[\s\S]*\}/)
  assert.match(css, /\.talent-grid\s*\{[\s\S]*height:\s*1080rpx;[\s\S]*\}/)
  assert.match(css, /\.active-tree-grid-hero\s*\{[\s\S]*height:\s*820rpx;[\s\S]*\}/)
  assert.match(css, /\.active-tree-grid-spec\s*\{[\s\S]*height:\s*1080rpx;[\s\S]*\}/)
  assert.match(css, /\.talent-link::after\s*\{[\s\S]*border-left:\s*12rpx solid rgba\(150,\s*150,\s*150,\s*0\.62\);[\s\S]*\}/)
  assert.match(css, /\.talent-link\.active\s*\{[\s\S]*background:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-link\.active::after\s*\{[\s\S]*border-left-color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-link\.available\s*\{[\s\S]*background:\s*rgba\(248,\s*183,\s*0,\s*0\.72\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\s*\{[\s\S]*width:\s*64rpx;[\s\S]*height:\s*64rpx;[\s\S]*margin-left:\s*-32rpx;[\s\S]*margin-top:\s*-32rpx;[\s\S]*box-sizing:\s*border-box;[\s\S]*border:\s*5rpx solid rgba\(255,\s*255,\s*255,\s*0\.16\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-circle\s*\{[\s\S]*border-radius:\s*50%;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-square\s*\{[\s\S]*border-radius:\s*14rpx;[\s\S]*\}/)
  assert.match(wxml, /class="talent-choice-frame" wx:if="\{\{item\.shape === 'choice'\}\}"/)
  assert.match(css, /\.talent-node\.shape-choice\s*\{[\s\S]*border:\s*0;[\s\S]*overflow:\s*visible;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice \.talent-choice-frame\s*\{[\s\S]*left:\s*-3rpx;[\s\S]*width:\s*70rpx;[\s\S]*clip-path:\s*polygon\(20% 0,\s*80% 0,\s*100% 20%,\s*100% 80%,\s*80% 100%,\s*20% 100%,\s*0 80%,\s*0 20%\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice \.talent-choice-frame::after\s*\{[\s\S]*inset:\s*5rpx;[\s\S]*clip-path:\s*polygon\(20% 0,\s*80% 0,\s*100% 20%,\s*100% 80%,\s*80% 100%,\s*20% 100%,\s*0 80%,\s*0 20%\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice \.talent-icon,[\s\S]*\.talent-node\.shape-choice \.talent-icon-fallback\s*\{[\s\S]*left:\s*6rpx;[\s\S]*width:\s*52rpx;[\s\S]*clip-path:\s*polygon\(18% 0,\s*82% 0,\s*100% 18%,\s*100% 82%,\s*82% 100%,\s*18% 100%,\s*0 82%,\s*0 18%\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice::before\s*\{[\s\S]*left:\s*-13rpx;[\s\S]*border-right:\s*16rpx solid rgba\(150,\s*150,\s*150,\s*0\.72\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice::after\s*\{[\s\S]*right:\s*-13rpx;[\s\S]*border-left:\s*16rpx solid rgba\(150,\s*150,\s*150,\s*0\.72\);[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice\.available::before,[\s\S]*\.talent-node\.shape-choice\.selected::before,[\s\S]*\.talent-node\.shape-choice\.granted::before\s*\{[\s\S]*border-right-color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice\.selectable:not\(\.selected\) \.talent-choice-frame\s*\{[\s\S]*background:\s*#24f05a;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice\.selectable:not\(\.selected\)::before\s*\{[\s\S]*border-right-color:\s*#24f05a;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.shape-choice\.selectable:not\(\.selected\)::after\s*\{[\s\S]*border-left-color:\s*#24f05a;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.granted\s*\{[\s\S]*border-color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.talent-node\.selectable:not\(\.selected\)\s*\{[\s\S]*border-color:\s*#24f05a;[\s\S]*\}/)
  assert.doesNotMatch(css, /\.talent-node\.selectable:not\(\.selected\):not\(\.shape-choice\)::after/)
  assert.match(css, /\.rank-button\s*\{[\s\S]*width:\s*72rpx;[\s\S]*min-width:\s*72rpx;[\s\S]*max-width:\s*72rpx;[\s\S]*padding:\s*0;[\s\S]*margin:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;[\s\S]*line-height:\s*1;[\s\S]*\}/)
  assert.match(css, /\.rank-button::after\s*\{\s*border:\s*0;\s*\}/)
  assert.match(css, /\.talent-choice-sheet/)
  assert.match(css, /\.talent-detail-sheet/)
  assert.match(css, /\.template-save-sheet/)
  assert.doesNotMatch(wxml, /talent-board-scroll/)
  assert.doesNotMatch(wxml, /talent-column class/)
  assert.doesNotMatch(wxml, /talent-column spec/)
  assert.doesNotMatch(wxml, /talent-column hero/)
  assert.doesNotMatch(css, /min-width:\s*1500rpx/)
  assert.doesNotMatch(wxml, /class="talent-chip-list"/)
})

test('native talent simulator save flow names talent templates for the profile library', async () => {
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig()
  const selectedNodes = [{ id: 'root', rank: 1 }]
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      websimExportCode: 'websim:mage:frost:frostfire:root:1',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      scenarioKey: 'mythic_plus',
      selectedHeroLabel: '霜火',
      selectedScenarioIndex: 0,
      scenarioOptions: [{ key: 'mythic_plus', title: '大秘境' }],
      selectedDetail: { className: '法师', specName: '冰霜' },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜' },
      selectedNodes,
      classSection: { key: 'class', pointCount: 34, pointCap: 34 },
      heroSection: { key: 'hero', pointCount: 13, pointCap: 13 },
      specSection: { key: 'spec', pointCount: 34, pointCap: 34 },
      talentStatus: 'verified',
      talentAuthority: { diffStatus: 'pending_official_audit' },
      talentReadiness: { simcReady: true, blockers: [] },
      talentBlockers: [],
      canSaveTalentTemplate: true,
      selectedCommunityTemplate: null,
      saveTemplateSheet: { visible: false, name: '', defaultName: '' },
      templateSaving: false
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  pageConfig.saveTalentTemplate.call(page)

  assert.equal(page.data.saveTemplateSheet.visible, true)
  assert.match(page.data.saveTemplateSheet.name, /^法师-冰霜-霜火-\d{4} \d{4}$/)
  assert.ok(page.data.saveTemplateSheet.name.length <= 28)

  pageConfig.updateTemplateName.call(page, { detail: { value: '我的AOE模板' } })
  await pageConfig.confirmSaveTalentTemplate.call(page)

  assert.equal(page.data.saveTemplateSheet.visible, false)
  assert.equal(mocks.profilePayload, null)
  assert.equal(mocks.savedTemplate.type, 'talent')
  assert.equal(mocks.savedTemplate.title, '我的AOE模板')
  assert.equal(mocks.savedTemplate.rawString, 'websim:mage:frost:frostfire:root:1')
  assert.equal(Array.isArray(mocks.savedTemplate.simcLines), true)
  assert.equal(mocks.savedTemplate.simcLines.length, 0)
  assert.equal(mocks.savedTemplate.status, 'saved')
  assert.equal(mocks.savedTemplate.statusLabel, '已保存')
  assert.deepEqual(mocks.savedTemplate.metadata.selectedNodes, selectedNodes)
})

test('native talent simulator blocks template save until talent points are filled', () => {
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig()
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      websimExportCode: 'websim:mage:frost:frostfire:root:1',
      classSection: { key: 'class', pointCount: 33, pointCap: 34 },
      heroSection: { key: 'hero', pointCount: 13, pointCap: 13 },
      specSection: { key: 'spec', pointCount: 34, pointCap: 34 },
      canSaveTalentTemplate: false,
      saveBlockReason: '请先点满天赋点：通用 33/34',
      saveTemplateSheet: { visible: false, name: '', defaultName: '' },
      templateSaving: false
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  pageConfig.saveTalentTemplate.call(page)
  pageConfig.confirmSaveTalentTemplate.call(page)

  assert.equal(page.data.saveTemplateSheet.visible, false)
  assert.equal(mocks.profilePayload, null)
  assert.equal(mocks.savedTemplate, null)
  assert.equal(mocks.toasts.at(-1).title, '请先点满天赋点：通用 33/34')
})

test('native talent simulator blocks template save when backend readiness is not simc ready', () => {
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig()
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      activeTreeKey: 'class',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      nodes: [{
        id: 'fallback-mage-frost-class-core',
        name: 'Fallback Core',
        treeType: 'class',
        row: 1,
        col: 1,
        maxRank: 1
      }],
      treeSections: [{ key: 'class', title: '职业天赋', tree: 'class', pointCap: 1 }],
      talentRanks: { 'fallback-mage-frost-class-core': 1 },
      baseTalentRanks: {},
      pointCaps: { class: 1 },
      talentStatus: 'fallback',
      talentAuthority: { diffStatus: 'blocked' },
      talentReadiness: {
        simcReady: false,
        blockers: ['WebSim talent cache is fallback; sync SimulationCraft talent data before running SimC']
      },
      scenarioOptions: [{ key: 'mythic_plus', title: '大秘境' }],
      selectedScenarioIndex: 0,
      saveTemplateSheet: { visible: false, name: '', defaultName: '' },
      templateSaving: false
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    }
  }

  pageConfig.renderTalentView.call(page)
  pageConfig.saveTalentTemplate.call(page)

  assert.equal(page.data.websimExportCode, 'websim:mage:frost:frostfire:fallback-mage-frost-class-core:1')
  assert.equal(page.data.canSaveTalentTemplate, false)
  assert.match(page.data.saveBlockReason, /后端天赋数据暂不可用于模拟/)
  assert.equal(page.data.saveTemplateSheet.visible, false)
  assert.equal(mocks.savedTemplate, null)
  assert.match(mocks.toasts.at(-1).title, /后端天赋数据暂不可用于模拟/)
})

test('native talent simulator action bar keeps three clear actions on one row', () => {
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  const actionBarMatch = wxml.match(/<view class="mobile-action-bar">([\s\S]*?)<\/view>/)
  assert.ok(actionBarMatch)
  assert.equal((actionBarMatch[1].match(/<button/g) || []).length, 3)
  assert.match(actionBarMatch[1], /保存模板/)
  assert.match(actionBarMatch[1], />导入</)
  assert.doesNotMatch(actionBarMatch[1], /导入社区推荐/)
  assert.match(actionBarMatch[1], /重置/)
  assert.doesNotMatch(actionBarMatch[1], /openTalentImport/)
  assert.match(css, /grid-template-columns:\s*minmax\(220rpx,\s*1\.15fr\) minmax\(220rpx,\s*1fr\) 132rpx;/)
  assert.match(css, /\.mobile-action-bar button\s*\{[\s\S]*width:\s*100%;[\s\S]*margin:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*white-space:\s*nowrap;[\s\S]*\}/)
  assert.match(css, /\.action-primary-button/)
  assert.match(css, /\.action-secondary-button/)
  assert.match(css, /\.mobile-action-bar button::after\s*\{\s*border:\s*0;\s*\}/)
})

test('native talent simulator save sheet keeps cancel and save on the same row', () => {
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')

  const saveSheetMatch = wxml.match(/<view class="save-sheet-actions">([\s\S]*?)<\/view>/)
  assert.ok(saveSheetMatch)
  assert.equal((saveSheetMatch[1].match(/<button/g) || []).length, 2)
  assert.match(saveSheetMatch[1], /save-sheet-secondary[\s\S]*取消/)
  assert.match(saveSheetMatch[1], /save-sheet-primary[\s\S]*保存/)
  assert.match(wxml, /disabled="\{\{!canSaveTalentTemplate \|\| templateSaving\}\}"/)
  assert.match(css, /\.template-save-sheet\s*\{[\s\S]*padding:\s*16rpx 22rpx calc\(44rpx \+ env\(safe-area-inset-bottom\)\);[\s\S]*box-sizing:\s*border-box;[\s\S]*\}/)
  assert.match(css, /\.save-sheet-actions\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);[\s\S]*align-items:\s*center;[\s\S]*\}/)
  assert.match(css, /\.save-sheet-actions button\s*\{[\s\S]*width:\s*100%;[\s\S]*min-width:\s*0;[\s\S]*margin:\s*0;[\s\S]*box-sizing:\s*border-box;[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;[\s\S]*line-height:\s*1;[\s\S]*white-space:\s*nowrap;[\s\S]*\}/)
})

test('native talent simulator page exposes two-layer import sheet', () => {
  const js = fs.readFileSync('pages/builds/talent-simulator.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/talent-simulator.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/talent-simulator.wxss', 'utf8')
  const api = fs.readFileSync('pages/builds/websim-api.js', 'utf8')

  assert.match(api, /communityTemplates:\s*\[\]/)
  assert.match(api, /communityTemplateSync/)
  assert.match(js, /communityTemplates:\s*\[\]/)
  assert.match(js, /communityTemplateSync/)
  assert.match(js, /activeCommunityTemplates/)
  assert.match(js, /listBuildTemplates/)
  assert.match(js, /savedTalentTemplates/)
  assert.match(js, /communityTemplateSheet/)
  assert.match(js, /selectedCommunityTemplate/)
  assert.match(js, /openCommunityTemplates\(\)/)
  assert.match(js, /closeCommunityTemplates\(\)/)
  assert.match(js, /applySavedTalentTemplate\(event\)/)
  assert.match(js, /applyCommunityTemplate\(event\)/)
  assert.match(js, /communityTemplateStatusText/)
  assert.match(js, /communityTemplateApplyMode/)
  assert.match(wxml, /bindtap="openCommunityTemplates"/)
  assert.match(wxml, />导入</)
  assert.doesNotMatch(wxml, />导入社区推荐</)
  assert.match(wxml, /communityTemplateSheet\.visible/)
  assert.match(wxml, /personal-template-section/)
  assert.match(wxml, /community-template-section/)
  assert.match(wxml, /wx:for="\{\{savedTalentTemplates\}\}"/)
  assert.match(wxml, /bindtap="applySavedTalentTemplate"/)
  assert.match(wxml, /wx:for="\{\{activeCommunityTemplates\}\}"/)
  assert.ok(wxml.indexOf('savedTalentTemplates') < wxml.indexOf('activeCommunityTemplates'))
  assert.match(wxml, /item\.name/)
  assert.match(wxml, /item\.sourceName/)
  assert.match(wxml, /item\.sampleLabel/)
  assert.match(wxml, /item\.keyLabel/)
  assert.match(wxml, /item\.updatedLabel/)
  assert.match(wxml, /item\.modeLabel/)
  assert.match(wxml, /disabled="\{\{item\.applyMode !== 'visual'\}\}"/)
  assert.doesNotMatch(wxml, /item\.analysisWindow/)
  assert.doesNotMatch(wxml, /template-note/)
  assert.match(wxml, /class="template-apply-row"/)
  assert.match(wxml, /bindtap="applyCommunityTemplate"/)
  assert.match(css, /\.community-template-sheet/)
  assert.match(css, /\.template-layer/)
  assert.match(css, /\.template-section-title/)
  assert.match(css, /\.community-template-card/)
  assert.match(css, /\.community-template-card\.external/)
  assert.match(css, /\.community-template-card\.pending/)
  assert.doesNotMatch(css, /\.template-note/)
  assert.match(css, /\.template-apply-row\s*\{[\s\S]*display:\s*flex;[\s\S]*justify-content:\s*center;[\s\S]*\}/)
  assert.match(css, /\.template-apply-button\s*\{[\s\S]*width:\s*300rpx;[\s\S]*max-width:\s*100%;[\s\S]*margin:\s*0;[\s\S]*display:\s*flex;[\s\S]*align-items:\s*center;[\s\S]*justify-content:\s*center;[\s\S]*line-height:\s*1;[\s\S]*\}/)
})

test('native talent simulator keeps rendering if the class template helper is not exported yet', () => {
  const { pageConfig } = loadTalentSimulatorPageConfig({ omitTemplatesForClass: true })
  const mageTemplate = {
    id: 'mage-template',
    classKey: 'mage',
    name: 'Mage Template',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:frost:frostfire:root:1'
  }
  const warriorTemplate = {
    id: 'warrior-template',
    classKey: 'warrior',
    name: 'Warrior Template',
    canApplyVisual: true,
    websimExportCode: 'websim:warrior:protection:mountain_thane:root:1'
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      activeTreeKey: 'class',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      nodes: [{ id: 'root', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true }],
      treeSections: [{ key: 'class', title: 'Class', tree: 'class', pointCap: 1 }],
      talentRanks: { root: 1 },
      baseTalentRanks: { root: 1 },
      pointCaps: { class: 1 },
      communityTemplates: [mageTemplate, warriorTemplate],
      communityTemplateSync: { sourceStatus: 'synced', sources: {}, templates: { total: 2, verified: 2, blocked: 0 } },
      scenarioOptions: [{ key: 'mythic_plus', title: 'Mythic+' }],
      selectedScenarioIndex: 0
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    }
  }

  assert.doesNotThrow(() => pageConfig.renderTalentView.call(page))
  assert.deepEqual(page.data.activeCommunityTemplates.map((item) => item.id), ['mage-template'])
})

test('native talent simulator filters duplicate community talent trees', () => {
  const { pageConfig } = loadTalentSimulatorPageConfig()
  const lowerTemplate = {
    id: 'rio-frost-low',
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'frostfire',
    name: 'Same build +18',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:frost:frostfire:root:1,ice:2',
    talentState: {
      selectedNodes: [
        { id: 'ice', rank: 2 },
        { id: 'root', rank: 1 }
      ]
    },
    sampleCount: 60,
    maxKeyLevel: 18
  }
  const strongerTemplate = {
    ...lowerTemplate,
    id: 'rio-frost-high',
    name: 'Same build +24',
    sampleCount: 42,
    maxKeyLevel: 24
  }
  const distinctTemplate = {
    id: 'rio-frost-other',
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'frostfire',
    name: 'Different build',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:frost:frostfire:root:1,bolt:1',
    talentState: {
      selectedNodes: [
        { id: 'bolt', rank: 1 },
        { id: 'root', rank: 1 }
      ]
    },
    sampleCount: 20,
    maxKeyLevel: 20
  }
  const arcaneTemplate = {
    id: 'rio-arcane-cross-spec',
    classKey: 'mage',
    specKey: 'arcane',
    heroKey: 'spellslinger',
    name: 'Arcane cross spec',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:arcane:spellslinger:arcane:1',
    talentState: {
      selectedNodes: [
        { id: 'arcane', rank: 1 }
      ]
    },
    sampleCount: 99,
    maxKeyLevel: 30
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      activeTreeKey: 'class',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      nodes: [{ id: 'root', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true }],
      treeSections: [{ key: 'class', title: 'Class', tree: 'class', pointCap: 1 }],
      talentRanks: { root: 1 },
      baseTalentRanks: { root: 1 },
      pointCaps: { class: 1 },
      communityTemplates: [lowerTemplate, distinctTemplate, strongerTemplate, arcaneTemplate],
      communityTemplateSync: { sourceStatus: 'synced', sources: {}, templates: { total: 4, verified: 4, blocked: 0 } },
      scenarioOptions: [{ key: 'mythic_plus', title: 'Mythic+' }],
      selectedScenarioIndex: 0
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    }
  }

  pageConfig.renderTalentView.call(page)

  assert.deepEqual(page.data.activeCommunityTemplates.map((item) => item.id), ['rio-frost-high'])
})

test('native talent simulator applies cross-spec community templates after switching target tree', async () => {
  const classOptions = [{
    name: 'Mage',
    key: 'mage',
    specializations: [
      { id: 'mage-frost', title: 'Frost', className: 'Mage', specName: 'Frost', websimClassKey: 'mage', websimSpecKey: 'frost' },
      { id: 'mage-arcane', title: 'Arcane', className: 'Mage', specName: 'Arcane', websimClassKey: 'mage', websimSpecKey: 'arcane' }
    ]
  }]
  const websimClasses = [{
    key: 'mage',
    specs: [
      { key: 'frost', heroTrees: [{ key: 'frostfire', label: 'Frostfire' }] },
      { key: 'arcane', heroTrees: [{ key: 'spellslinger', label: 'Spellslinger' }] }
    ]
  }]
  const template = {
    id: 'rio-arcane',
    classKey: 'mage',
    specKey: 'arcane',
    heroKey: 'spellslinger',
    name: 'Rioone-Mage-Spellslinger-Arcane-Mythic+',
    canApplyVisual: true,
    websimExportCode: 'websim:mage:arcane:spellslinger:arcane-root:1'
  }
  const { pageConfig, mocks } = loadTalentSimulatorPageConfig({
    talentPayloads: {
      'mage:arcane:spellslinger': {
        heroKey: 'spellslinger',
        nodes: [{ id: 'arcane-root', treeType: 'class', rank: 1, maxRank: 1 }],
        treeSections: [{ key: 'class', pointCap: 34 }],
        communityTemplates: [template],
        communityTemplateSync: { sourceStatus: 'synced', sources: {}, templates: { total: 1, verified: 1, blocked: 0 } },
        talentStatus: 'verified'
      }
    }
  })
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      classOptions,
      websimClasses,
      selectedClassIndex: 0,
      selectedSpecIndex: 0,
      selectedClass: classOptions[0],
      specOptions: classOptions[0].specializations,
      selectedSpec: classOptions[0].specializations[0],
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      heroOptions: websimClasses[0].specs[0].heroTrees,
      selectedHeroIndex: 0,
      activeCommunityTemplates: [template],
      nodes: [{ id: 'frost-root', treeType: 'class', rank: 1, maxRank: 1 }],
      pointCaps: {}
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  await pageConfig.applyCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'rio-arcane' } } })

  assert.equal(mocks.talentRequests.at(-1).classKey, 'mage')
  assert.equal(mocks.talentRequests.at(-1).specKey, 'arcane')
  assert.equal(mocks.talentRequests.at(-1).heroKey, 'spellslinger')
  assert.equal(page.data.selectedSpecIndex, 1)
  assert.equal(page.data.specKey, 'arcane')
  assert.equal(page.data.heroKey, 'spellslinger')
  assert.equal(page.data.talentRanks['arcane-root'], 1)
  assert.equal(page.data.selectedCommunityTemplate.id, 'rio-arcane')
  assert.equal(page.data.communityTemplateSheet.visible, false)
})

test('native talent simulator imports a saved personal template from the top layer', () => {
  const { pageConfig } = loadTalentSimulatorPageConfig({
    storedTemplates: [{
      id: 'saved-frost',
      type: 'talent',
      title: '我的冰法模板',
      classKey: 'mage',
      className: '法师',
      specKey: 'frost',
      specName: '冰霜',
      heroKey: 'frostfire',
      heroLabel: '霜火',
      scenarioTitle: '单体',
      rawString: 'websim:mage:frost:frostfire:frost-root:1',
      updatedAt: '2026-06-26T12:30:00.000Z',
      statusLabel: '已保存'
    }]
  })
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'frostfire',
      activeTreeKey: 'class',
      nodes: [{ id: 'frost-root', treeType: 'class', rank: 1, maxRank: 1 }],
      treeSections: [{ key: 'class', title: '职业天赋', pointCap: 1 }],
      pointCaps: { class: 1 },
      talentRanks: {},
      baseTalentRanks: {},
      communityTemplateSheet: { visible: false }
    },
    setData(update, callback) {
      this.data = { ...this.data, ...update }
      if (callback) callback()
    },
    renderTalentView() {}
  }

  pageConfig.openCommunityTemplates.call(page)
  pageConfig.applySavedTalentTemplate.call(page, { currentTarget: { dataset: { id: 'saved-frost' } } })

  assert.equal(page.data.savedTalentTemplates.length, 1)
  assert.equal(page.data.savedTalentTemplates[0].name, '我的冰法模板')
  assert.equal(page.data.talentRanks['frost-root'], 1)
  assert.equal(page.data.communityTemplateSheet.visible, false)
  assert.match(page.data.statusText, /保存模板/)
})

test('gear detail page exposes inline equipment simulator state and replacement sheet', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/builds/detail.wxss', 'utf8')

  assert.match(js, /game-asset/)
  assert.match(js, /requestWebsimGear/)
  assert.match(js, /requestWebsimGearStatSnapshot/)
  assert.doesNotMatch(js, /\brequestWebsimGearStats\b/)
  assert.match(js, /selectedGearBySlot/)
  assert.match(js, /gearSlotRows/)
  assert.match(js, /buildGearAttributePanel/)
  assert.match(js, /gearInitialLoading/)
  assert.match(js, /gearStatSnapshot/)
  assert.match(js, /gearStatBlockers/)
  assert.match(js, /loadWebsimGearForSelection/)
  assert.match(js, /refreshGearStats/)
  assert.match(js, /openGearSlotSheet\(event\)/)
  assert.match(js, /selectGearCandidate\(event\)/)
  assert.match(js, /setGearCandidateFilter\(event\)/)
  assert.match(js, /selectGearVariant\(event\)/)
  assert.doesNotMatch(js, /selectGearSocketOption\(event\)/)
  assert.doesNotMatch(js, /selectGearEnchantOption\(event\)/)
  assert.match(js, /applyGearCandidate\(\)/)
  assert.match(js, /gearTemplateScenarios/)
  assert.match(js, /selectGearTemplateScenario\(event\)/)
  assert.match(js, /openGearCommunityTemplates\(\)/)
  assert.match(js, /savedGearTemplates/)
  assert.match(js, /listBuildTemplates/)
  assert.match(js, /applySavedGearTemplate\(event\)/)
  assert.match(js, /applyGearCommunityTemplate\(event\)/)
  assert.match(js, /resetGearSelection\(\)/)
  assert.doesNotMatch(js, /scenarioKey:\s*'single'/)
  assert.match(js, /selectedGearTemplateScenarioIndex/)
  assert.doesNotMatch(js, /this\.refreshGearStats\(\)/)
  assert.match(js, /saveGearTemplate\(\)/)
  assert.match(js, /openGearEnhancementSheet\(\)/)
  assert.match(js, /selectGearEnhancementOption\(event\)/)
  assert.match(js, /confirmGearEnhancementSheet\(\)/)
  assert.match(js, /enhancementBySlot/)
  assert.match(js, /gearEnhancementSheet/)
  assert.match(js, /canonicalGearTemplateLines/)
  assert.match(js, /syncBuildTemplate/)
  assert.doesNotMatch(wxml, /class="gear-status-strip"/)
  assert.doesNotMatch(wxml, /class="gear-template-picker"/)
  assert.doesNotMatch(wxml, /class="gear-stat-panel"/)
  assert.doesNotMatch(wxml, /gearStatSnapshot\.statStatus/)
  assert.doesNotMatch(wxml, /gearStatBlockers/)
  assert.match(wxml, /class="gear-attribute-panel"/)
  assert.match(wxml, /class="gear-attribute-level"/)
  assert.match(wxml, /gearAttributePanel\.itemLevel/)
  assert.doesNotMatch(wxml, /gearAttributePanel\.primaryStat/)
  assert.match(wxml, /gearAttributePanel\.enhancementRows/)
  assert.match(wxml, /gearAttributePanel\.statRows/)
  assert.match(wxml, /gear-attribute-converted/)
  assert.doesNotMatch(wxml, /gearAttributePanel\.resourceRows/)
  assert.match(wxml, /class="gear-slot-grid"/)
  assert.match(wxml, /wx:for="\{\{gearSlotRows\}\}"/)
  assert.match(wxml, /class="gear-slot-enhancement-badges" wx:if="\{\{item\.equipmentBadgeLabels\.length \|\| item\.enhancementBadgeLabels\.length\}\}"/)
  assert.match(wxml, /wx:for="\{\{item\.equipmentBadgeLabels\}\}"/)
  assert.match(wxml, /wx:for="\{\{item\.enhancementBadgeLabels\}\}"/)
  assert.match(wxml, /class="gear-slot-enhancement-badge"/)
  assert.ok(wxml.indexOf('class="gear-attribute-panel"') < wxml.indexOf('class="gear-slot-grid"'))
  assert.ok(wxml.indexOf('class="gear-attribute-level"') < wxml.indexOf('class="gear-attribute-grid"'))
  assert.ok(wxml.indexOf('class="gear-attribute-action"') > wxml.indexOf('class="gear-attribute-panel"'))
  assert.ok(wxml.indexOf('class="gear-attribute-action"') < wxml.indexOf('class="gear-slot-grid"'))
  assert.match(wxml, />配置宝石、附魔<\/button>/)
  assert.doesNotMatch(wxml, />强化配置</)
  assert.ok(wxml.indexOf('class="gear-attribute-grid"') < wxml.indexOf('class="gear-attribute-enhancement-row"'))
  assert.ok(wxml.indexOf('class="gear-attribute-enhancement-row"') < wxml.indexOf('class="gear-attribute-action-row"'))
  assert.doesNotMatch(wxml, /class="gear-attribute-primary"/)
  const gearSlotGridMarkup = wxml.match(/<view class="gear-slot-grid">[\s\S]*?<view class="gear-loading-state"/)
  assert.ok(gearSlotGridMarkup)
  assert.doesNotMatch(gearSlotGridMarkup[0], /gear-slot-status/)
  assert.doesNotMatch(gearSlotGridMarkup[0], /gear-slot-footer/)
  assert.doesNotMatch(gearSlotGridMarkup[0], /item\.statusLabel/)
  assert.doesNotMatch(gearSlotGridMarkup[0], /item\.trustLabel/)
  assert.doesNotMatch(wxml, /source-strip/)
  assert.match(wxml, /class="gear-loading-state" wx:if="\{\{gearInitialLoading\}\}"/)
  assert.match(wxml, /class="detail-desc" wx:if="\{\{activeQuery\.desc && activeQueryKey != 'gear'\}\}"/)
  assert.match(wxml, /class="gear-icon"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /item\.displayName/)
  assert.doesNotMatch(wxml, /gearTrustSummaryText/)
  assert.doesNotMatch(wxml, /class="gear-trust-summary"/)
  assert.doesNotMatch(wxml, /candidateCount/)
  assert.doesNotMatch(wxml, /个候选/)
  assert.match(wxml, /class="gear-apply-message"/)
  assert.match(wxml, /gearSlotSheet\.activeTrustText/)
  assert.match(wxml, /class="gear-config-stack"/)
  assert.match(wxml, /class="gear-variant-track-grid"/)
  assert.match(wxml, /class="gear-variant-track-card /)
  assert.match(wxml, /class="gear-variant-track-name"/)
  assert.match(wxml, /class="gear-variant-track-level"/)
  assert.doesNotMatch(wxml, /class="gear-section-optional"/)
  assert.doesNotMatch(wxml, /class="gear-mod-section"/)
  assert.doesNotMatch(wxml, /宝石插槽/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.activeTrustLabel/)
  assert.doesNotMatch(wxml, /class="gear-sheet-active"/)
  assert.match(wxml, /item\.blockerLabel/)
  assert.doesNotMatch(wxml, /item\.source\s*(\|\||\}\})/)
  assert.doesNotMatch(wxml, /item\.itemId/)
  assert.doesNotMatch(wxml, /gearStatSnapshot\.itemLevel\.value/)
  assert.match(wxml, /bindtap="openGearSlotSheet"/)
  assert.match(wxml, /gearSlotSheet\.visible/)
  assert.match(wxml, /gearSlotSheet\.filters/)
  assert.match(wxml, /wx:for="\{\{gearSlotSheet\.candidates\}\}"/)
  assert.match(wxml, /bindtap="selectGearCandidate"/)
  assert.match(wxml, /gearSlotSheet\.variantOptions/)
  assert.match(wxml, /gearSlotSheet\.variantOptions\.length/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.variantOptions\.length > 1/)
  assert.doesNotMatch(wxml, /配置来源/)
  assert.doesNotMatch(wxml, /实装观测/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.socketOptions/)
  assert.doesNotMatch(wxml, /gearSlotSheet\.enchantOptions/)
  assert.match(wxml, /bindtap="selectGearVariant"/)
  assert.doesNotMatch(wxml, /bindtap="selectGearSocketOption"/)
  assert.doesNotMatch(wxml, /bindtap="selectGearEnchantOption"/)
  assert.match(wxml, /bindtap="applyGearCandidate"/)
  assert.match(wxml, /bindtap="saveGearTemplate"/)
  assert.match(wxml, /gearSaveTemplateSheet\.visible/)
  assert.match(wxml, /value="\{\{gearSaveTemplateSheet\.name\}\}"/)
  assert.match(wxml, /placeholder="\{\{gearSaveTemplateSheet\.defaultName\}\}"/)
  assert.match(wxml, /bindinput="updateGearTemplateName"/)
  assert.match(wxml, /bindtap="confirmSaveGearTemplate"/)
  assert.match(wxml, /bindtap="closeGearSaveTemplateSheet"/)
  assert.doesNotMatch(wxml, /class="gear-template-action-button enhance"/)
  assert.match(wxml, /bindtap="openGearEnhancementSheet"/)
  assert.match(wxml, /gearEnhancementSheet\.visible/)
  assert.match(wxml, /gearEnhancementSheet\.equipmentRows/)
  assert.match(wxml, /gearEnhancementSheet\.activeGemRows/)
  assert.match(wxml, /gearEnhancementSheet\.activeEnchantRows/)
  assert.match(wxml, /gearEnhancementSheet\.activeEmbellishmentRows/)
  assert.match(wxml, /bindtap="selectGearEnhancementSlot"/)
  assert.match(wxml, /bindtap="confirmGearEnhancementSheet"/)
  assert.ok(wxml.indexOf('class="gear-enhancement-equipment-grid"') < wxml.indexOf('class="gear-enhancement-blockers"'))
  assert.match(wxml, /disabled="\{\{gearEnhancementSheet\.submitting\}\}"/)
  assert.match(wxml, /gearEnhancementSheet\.submitting \? '校验中' : '确认'/)
  assert.match(wxml, /<button class="gear-sheet-close" disabled="\{\{gearEnhancementSheet\.submitting\}\}" bindtap="closeGearEnhancementSheet">关闭<\/button>/)
  assert.equal((wxml.match(/disabled="\{\{option\.disabled \|\| gearEnhancementSheet\.submitting\}\}"/g) || []).length, 3)
  assert.match(wxml, /bindtap="openGearCommunityTemplates"/)
  assert.match(wxml, /bindtap="resetGearSelection"/)
  assert.match(wxml, /gearDataWarningText/)
  assert.match(wxml, /disabled="\{\{gearDataFallback \|\| gearTemplateSaving \|\| !gearWorkbenchView\.canUseVerifiedSnapshot\}\}"/)
  assert.match(wxml, /gearWorkbenchStatusText/)
  assert.match(wxml, /gearWorkbenchProblemRows/)
  assert.match(wxml, /disabled="\{\{!gearWorkbenchView\.canRunProfile\}\}"/)
  assert.match(wxml, /class="gear-template-action-button import"/)
  assert.match(wxml, />导入</)
  assert.doesNotMatch(wxml, />导入社区推荐</)
  assert.match(wxml, /disabled="\{\{gearDataFallback\}\}"/)
  assert.match(wxml, /gearCommunityTemplateSheet\.visible/)
  assert.match(wxml, /gear-personal-template-section/)
  assert.match(wxml, /gear-community-recommendation-section/)
  assert.match(wxml, /wx:for="\{\{savedGearTemplates\}\}"/)
  assert.match(wxml, /bindtap="applySavedGearTemplate"/)
  assert.match(wxml, /wx:for="\{\{activeGearCommunityTemplates\}\}"/)
  assert.ok(wxml.indexOf('savedGearTemplates') < wxml.indexOf('activeGearCommunityTemplates'))
  assert.match(wxml, /gear-community-template-title">\{\{item\.displayName \|\| item\.name\}\}/)
  assert.match(wxml, /\{\{item\.displaySourceName \|\| item\.sourceName\}\} · \{\{item\.slotCoverageLabel\}\}/)
  assert.match(wxml, /bindtap="applyGearCommunityTemplate"/)
  const gearPanelMarkup = wxml.match(/<view class="module-panel gear-panel"[\s\S]*?<view class="module-panel stats-panel"/)
  assert.ok(gearPanelMarkup)
  assert.doesNotMatch(gearPanelMarkup[0], /class="insight-list"/)
  assert.match(wxml, /class="gear-template-actions" wx:if="\{\{!gearInitialLoading\}\}"/)
  assert.match(wxml, /class="source-box" wx:if="\{\{activeDetail && activeQueryKey != 'gear'\}\}"/)
  assert.ok(wxml.indexOf('bindtap="saveGearTemplate"') > wxml.indexOf('class="gear-slot-grid"'))
  assert.doesNotMatch(css, /\.gear-stat-panel/)
  assert.match(css, /\.gear-attribute-panel/)
  assert.match(css, /\.gear-attribute-level/)
  assert.match(css, /\.gear-attribute-action/)
  assert.match(css, /\.gear-attribute-enhancement-row/)
  assert.match(css, /\.gear-attribute-action-row/)
  assert.doesNotMatch(css, /\.gear-attribute-primary/)
  assert.match(css, /\.gear-attribute-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-attribute-enhancement-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\);/)
  const gearAttributeLevelCss = css.match(/\.gear-attribute-level\s*\{[^}]*\}/)
  assert.ok(gearAttributeLevelCss)
  assert.match(gearAttributeLevelCss[0], /align-items:\s*center;/)
  assert.match(gearAttributeLevelCss[0], /text-align:\s*center;/)
  const gearAttributeEnhancementCss = css.match(/\.gear-attribute-enhancement-row\s*\{[^}]*\}/)
  assert.ok(gearAttributeEnhancementCss)
  assert.doesNotMatch(gearAttributeEnhancementCss[0], /136rpx/)
  const gearAttributeActionCss = css.match(/\.gear-attribute-action\s*\{[^}]*\}/)
  assert.ok(gearAttributeActionCss)
  assert.match(gearAttributeActionCss[0], /width:\s*100%;/)
  assert.match(css, /\.gear-slot-grid/)
  assert.match(css, /\.gear-slot-grid\s*\{[\s\S]*gap:\s*8rpx;[\s\S]*margin-top:\s*12rpx;/)
  assert.match(css, /\.gear-slot-card\s*\{[\s\S]*min-height:\s*126rpx;[\s\S]*padding:\s*12rpx;/)
  assert.match(css, /\.gear-slot-card\s*\{[\s\S]*position:\s*relative;/)
  const gearSlotCardCss = css.match(/\.gear-slot-card\s*\{[^}]*\}/)
  assert.ok(gearSlotCardCss)
  assert.match(gearSlotCardCss[0], /border:\s*1rpx solid rgba\(248,\s*183,\s*0,\s*0\.28\);/)
  const sourceReferenceSlotCardCss = css.match(/\.gear-slot-card\.source-reference\s*\{[^}]*\}/)
  assert.ok(sourceReferenceSlotCardCss)
  assert.match(sourceReferenceSlotCardCss[0], /border-color:\s*rgba\(248,\s*183,\s*0,\s*0\.28\);/)
  assert.doesNotMatch(sourceReferenceSlotCardCss[0], /94,\s*141,\s*255/)
  assert.match(css, /\.gear-slot-enhancement-badges\s*\{[\s\S]*position:\s*absolute;[\s\S]*top:\s*10rpx;[\s\S]*right:\s*10rpx;/)
  assert.match(css, /\.gear-slot-enhancement-badge\s*\{[\s\S]*font-size:\s*18rpx;[\s\S]*font-weight:\s*900;/)
  assert.match(css, /\.gear-slot-card \.gear-name\s*\{[\s\S]*font-size:\s*22rpx;[\s\S]*line-height:\s*1\.28;/)
  assert.match(css, /\.gear-request-alert/)
  assert.doesNotMatch(css, /\.gear-trust-summary/)
  assert.match(css, /\.gear-loading-state/)
  assert.match(css, /\.gear-slot-sheet/)
  assert.match(css, /\.gear-sheet-filter/)
  assert.match(css, /\.gear-sheet-filter-row\s*\{[\s\S]*grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-config-stack/)
  assert.match(css, /\.gear-variant-track-grid\s*\{[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.match(css, /\.gear-variant-track-card/)
  assert.match(css, /\.gear-apply-message/)
  assert.doesNotMatch(css, /\.gear-config-column-side/)
  assert.doesNotMatch(css, /\.gear-mod-option/)
  assert.doesNotMatch(css, /\.gear-section-optional/)
  assert.doesNotMatch(css, /\.gear-mod-list/)
  assert.match(css, /\.gear-template-actions\s*\{[\s\S]*display:\s*grid;[\s\S]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);[\s\S]*align-items:\s*center;[\s\S]*gap:\s*12rpx;/)
  assert.match(css, /\.gear-template-actions\s*\{[\s\S]*position:\s*relative;[\s\S]*z-index:\s*1;/)
  assert.doesNotMatch(css, /\.gear-template-actions\s*\{[^}]*position:\s*sticky;/)
  assert.match(css, /\.gear-template-action-button\s*\{[\s\S]*width:\s*100%;[\s\S]*min-width:\s*0;[\s\S]*height:\s*72rpx;[\s\S]*box-sizing:\s*border-box;[\s\S]*display:\s*flex;[\s\S]*white-space:\s*nowrap;[\s\S]*overflow:\s*hidden;/)
  assert.match(css, /\.gear-template-action-button\.import\s*\{[\s\S]*color:\s*#f8b700;[\s\S]*\}/)
  assert.match(css, /\.gear-template-action-button\.muted\s*\{[\s\S]*grid-column:\s*1\s*\/\s*-1;[\s\S]*\}/)
  assert.match(css, /\.gear-template-action-button\[disabled\]/)
  assert.match(css, /\.gear-enhancement-sheet/)
  assert.match(css, /\.gear-enhancement-equipment-grid/)
  assert.match(css, /\.gear-enhancement-equipment-card/)
  assert.match(css, /\.gear-enhancement-option\.disabled/)
  const gearEnhancementOptionsCss = css.match(/\.gear-enhancement-options\s*\{[^}]*\}/)
  assert.ok(gearEnhancementOptionsCss)
  assert.match(gearEnhancementOptionsCss[0], /gap:\s*12rpx;/)
  const gearEnhancementOptionCss = css.match(/\.gear-enhancement-option\s*\{[^}]*\}/)
  assert.ok(gearEnhancementOptionCss)
  assert.match(gearEnhancementOptionCss[0], /min-height:\s*64rpx;/)
  assert.match(gearEnhancementOptionCss[0], /display:\s*flex;/)
  assert.match(gearEnhancementOptionCss[0], /align-items:\s*center;/)
  assert.match(gearEnhancementOptionCss[0], /justify-content:\s*center;/)
  assert.match(gearEnhancementOptionCss[0], /text-align:\s*center;/)
  assert.match(gearEnhancementOptionCss[0], /white-space:\s*normal;/)
  const disabledEnhancementOptionCss = css.match(/button\.gear-enhancement-option\[disabled\]\s*\{[^}]*\}/)
  assert.ok(disabledEnhancementOptionCss)
  assert.match(disabledEnhancementOptionCss[0], /background-color:\s*rgba\(255,\s*255,\s*255,\s*0\.05\)\s*!important;/)
  assert.match(disabledEnhancementOptionCss[0], /color:\s*#686868\s*!important;/)
  assert.match(disabledEnhancementOptionCss[0], /opacity:\s*1;/)
  const gearSlotMaskCss = css.match(/\.gear-slot-sheet-mask\s*\{[^}]*\}/)
  const gearEnhancementSheetCss = css.match(/\.gear-enhancement-sheet\s*\{[^}]*\}/)
  assert.ok(gearSlotMaskCss)
  assert.ok(gearEnhancementSheetCss)
  const cssZIndex = (block) => Number((block.match(/z-index:\s*(\d+);/) || [])[1] || 0)
  assert.ok(cssZIndex(gearEnhancementSheetCss[0]) > cssZIndex(gearSlotMaskCss[0]))
  const gearActionsCss = css.match(/\.gear-template-actions\s*\{[^}]*\}/)
  assert.ok(gearActionsCss)
  assert.match(gearActionsCss[0], /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/)
  assert.doesNotMatch(gearActionsCss[0], /(^|\n)\s*bottom:\s*calc/)
  assert.match(css, /\.gear-community-template-sheet/)
  assert.match(css, /\.gear-community-template-card\.source-reference/)
  const gearCommunityCardCss = css.match(/\.gear-community-template-card\s*\{[^}]*\}/)
  assert.ok(gearCommunityCardCss)
  assert.match(gearCommunityCardCss[0], /display:\s*flex;/)
  assert.match(gearCommunityCardCss[0], /flex-direction:\s*column;/)
  assert.match(gearCommunityCardCss[0], /gap:\s*14rpx;/)
  assert.doesNotMatch(gearCommunityCardCss[0], /grid-template-columns:/)
  const gearCommunitySideCss = css.match(/\.gear-community-template-side\s*\{[^}]*\}/)
  assert.ok(gearCommunitySideCss)
  assert.match(gearCommunitySideCss[0], /min-width:\s*0;/)
  assert.match(gearCommunitySideCss[0], /display:\s*flex;/)
  assert.match(gearCommunitySideCss[0], /flex-direction:\s*column;/)
  assert.match(gearCommunitySideCss[0], /gap:\s*10rpx;/)
  assert.match(gearCommunitySideCss[0], /align-items:\s*stretch;/)
  const gearCommunityApplyCss = css.match(/\.gear-community-template-apply\s*\{[^}]*\}/)
  assert.ok(gearCommunityApplyCss)
  assert.match(gearCommunityApplyCss[0], /width:\s*100%;/)
  assert.match(gearCommunityApplyCss[0], /max-width:\s*100%;/)
  assert.match(gearCommunityApplyCss[0], /box-sizing:\s*border-box;/)
  assert.match(gearCommunityApplyCss[0], /display:\s*flex;/)
  assert.match(gearCommunityApplyCss[0], /white-space:\s*nowrap;/)
  assert.match(gearCommunityApplyCss[0], /overflow:\s*hidden;/)
  const primaryGearActionCss = css.match(/\.gear-template-action-button\.primary\s*\{[^}]*\}/)
  assert.ok(primaryGearActionCss)
  assert.doesNotMatch(primaryGearActionCss[0], /grid-column/)
  assert.match(css, /\.gear-attribute-converted/)
})

test('canonical gear workbench ignores forged client final facts and renders resolver snapshot facts', async () => {
  const resolveRequests = []
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return Promise.resolve({
        httpStatus: 200,
        fromFallback: false,
        payload: {
          contractRevision: 'gear-result-envelope-v1',
          status: 'resolved',
          problems: [],
          data: {
            contractRevision: 'gear-resolved-snapshot-v1',
            status: 'verified',
            resolvedGearSignature: 'sha256:server-snapshot',
            dependencyVector: { gearCatalogRevision: 'gear-r17', serializerRevision: 'serializer-r1' },
            staticAttributes: { intellect: 120, stamina: 240, haste: 30 },
            setState: { itemSetCounts: { 'set:server': 2 }, activeDynamicEffects: [] },
            aggregateLegality: { status: 'verified', problemCodes: [] },
            profileReadiness: { status: 'verified', simcReady: true, requiredSlots: ['head'], readySlots: ['head'] },
            constraints: { slots: { head: { socketCount: 0 } } },
            serializerInput: { gearItems: [{ slot: 'head', itemId: '250060' }] },
            resolvedSlots: { head: { slot: 'head', itemId: '250060', selectedOptions: {}, legality: { status: 'verified', problemCodes: [] } } },
            problems: []
          }
        }
      })
    }
  })
  const forged = {
    head: {
      slot: 'head', itemId: '250060', variantKey: 'variant-head', displayName: '浏览标签',
      itemStats: { intellect: 999999 }, statSummary: '智力 999999', itemSetName: '伪造套装', simcReady: false
    }
  }
  const page = {
    data: {
      ...pageConfig.data,
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedDetail: { details: { talents: { importCode: 'talent-code' }, gear: {} } },
      selectedGearBySlot: forged,
      enhancementBySlot: {},
      gearPayload: {
        classKey: 'mage', specKey: 'frost', maxLevel: 90,
        slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
        equippedSet: forged,
        replacementCandidates: [], slotReadiness: {}, readiness: {},
        resolverContext: {
          contractRevision: 'gear-resolver-context-v1',
          selectionSchemaRevision: 'selection-intent-v1',
          authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' }
        }
      }
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  await pageConfig.confirmAndResolveGearIntent.call(page, forged, {})

  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(Object.keys(resolveRequests[0].slots.head).sort(), [
    'catalystOptionId', 'craftedOptionId', 'embellishmentOptionId', 'enchantOptionId',
    'gemOptionIds', 'itemId', 'variantKey'
  ])
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'intellect').value, '120')
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'tierSet').value, '2')
  assert.equal(page.data.gearWorkbenchView.canRunProfile, true)
  assert.equal(page.data.gearWorkbenchView.resolvedGearSignature, 'sha256:server-snapshot')
  assert.equal(page.data.gearSlotRows.find((row) => row.slot === 'head').statusLabel, '已校验')
})

test('canonical gear workbench ignores stale resolve completion after a newer confirmed Intent', async () => {
  const pending = []
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return new Promise((resolve) => pending.push({ selectionIntent, resolve }))
    }
  })
  const payload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }], equippedSet: {},
    replacementCandidates: [], slotReadiness: {}, readiness: {},
    resolverContext: {
      contractRevision: 'gear-resolver-context-v1', selectionSchemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' }
    }
  }
  const page = {
    data: { ...pageConfig.data, activeQueryKey: 'gear', gearPayload: payload, selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }, selectedGearBySlot: {}, enhancementBySlot: {} },
    setData(update) { this.data = { ...this.data, ...update } }
  }
  const first = pageConfig.confirmAndResolveGearIntent.call(page, { head: { slot: 'head', itemId: '250060', variantKey: 'v1' } }, {})
  const second = pageConfig.confirmAndResolveGearIntent.call(page, { head: { slot: 'head', itemId: '250061', variantKey: 'v2' } }, {})
  const response = (signature) => ({ httpStatus: 200, fromFallback: false, payload: {
    contractRevision: 'gear-result-envelope-v1', status: 'resolved', problems: [], data: {
      contractRevision: 'gear-resolved-snapshot-v1', status: 'verified', resolvedGearSignature: signature,
      staticAttributes: {}, setState: { itemSetCounts: {}, activeDynamicEffects: [] },
      aggregateLegality: { status: 'verified', problemCodes: [] },
      profileReadiness: { status: 'verified', simcReady: true }, constraints: {}, serializerInput: { gearItems: [] },
      resolvedSlots: { head: { selectedOptions: {} } }, problems: []
    }
  } })
  pending[1].resolve(response('sha256:newest'))
  await second
  pending[0].resolve(response('sha256:stale'))
  await first

  assert.equal(page.data.gearWorkbenchView.resolvedGearSignature, 'sha256:newest')
  assert.equal(page.gearWorkbenchState.confirmedIntent.slots.head.itemId, '250061')
})

test('verified Resolve selectedOptions are the only committed enhancement state and blocked caller prewrites are restored', async () => {
  const resolveRequests = []
  const submitted = {
    finger1: {
      gemOptionIds: ['gem-draft', 'gem-draft'],
      enchantOptionId: 'enchant-draft'
    }
  }
  const canonical = {
    finger1: {
      gemOptionIds: ['gem-server', 'gem-server'],
      enchantOptionId: 'enchant-server'
    }
  }
  const blockedDraft = {
    finger1: {
      embellishmentOptionId: 'embellishment-draft'
    }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return new Promise((resolve) => {
        resolveRequests.push({ selectionIntent, resolve })
      })
    }
  })
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    resolverContext: canonicalTestResolverContext()
  }
  const selectedGearBySlot = {
    finger1: {
      slot: 'finger1', itemId: '250060', variantKey: 'variant-ring',
      modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: true, canEmbellish: true }
    }
  }
  const page = {
    data: {
      ...pageConfig.data,
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearPayload,
      selectedGearBySlot,
      enhancementBySlot: {}
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  const pending = pageConfig.confirmAndResolveGearIntent.call(page, selectedGearBySlot, submitted)
  const visibleWhilePending = JSON.parse(JSON.stringify(page.data.enhancementBySlot))
  resolveRequests[0].resolve({
    httpStatus: 200,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      status: 'resolved',
      problems: [],
      data: {
        contractRevision: 'gear-resolved-snapshot-v1',
        status: 'verified',
        resolvedGearSignature: 'sha256:server-enhancements',
        dependencyVector: {},
        staticAttributes: {},
        setState: { itemSetCounts: {}, activeDynamicEffects: [] },
        aggregateLegality: { status: 'verified', problemCodes: [] },
        profileReadiness: { status: 'verified', simcReady: true },
        constraints: {
          embellishmentMax: 2,
          slots: { finger1: { socketCount: 2, canEnchant: true, canEmbellish: true } }
        },
        resolvedSlots: {
          finger1: {
            itemLevel: 707,
            selectedOptions: canonical.finger1,
            simcOptions: {
              gem_id: 'forged/raw/gems',
              enchant_id: 'forged-raw-enchant'
            }
          }
        },
        problems: []
      }
    }
  })
  await pending

  assert.deepEqual(visibleWhilePending, {})
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), canonical)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.gearWorkbenchState.confirmedIntent.slots.finger1.gemOptionIds)),
    ['gem-draft', 'gem-draft']
  )
  assert.equal(page.data.enhancementBySlot.finger1.gem_id, undefined)
  assert.equal(page.data.enhancementBySlot.finger1.enchant_id, undefined)

  page.setData({
    enhancementBySlot: blockedDraft,
    gearSlotRows: page.data.gearSlotRows.map((row) => ({
      ...row,
      enhancementBadgeLabels: row.slot === 'finger1' ? ['美化'] : row.enhancementBadgeLabels
    }))
  })
  const blockedPending = pageConfig.confirmAndResolveGearIntent.call(page, selectedGearBySlot, blockedDraft)
  const visibleDuringBlockedResolve = JSON.parse(JSON.stringify(page.data.enhancementBySlot))
  const badgesDuringBlockedResolve = JSON.parse(JSON.stringify(
    page.data.gearSlotRows.find((row) => row.slot === 'finger1').enhancementBadgeLabels
  ))
  resolveRequests[1].resolve({
    httpStatus: 422,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      status: 'blocked',
      problems: [{ code: 'GEAR_OPTION_NOT_ALLOWED', title: 'blocked draft' }],
      data: {
        contractRevision: 'gear-resolved-snapshot-v1',
        status: 'blocked',
        resolvedGearSignature: 'sha256:blocked-must-not-commit',
        resolvedSlots: {
          finger1: {
            selectedOptions: { embellishmentOptionId: 'blocked-server-value' }
          }
        },
        problems: [{ code: 'GEAR_OPTION_NOT_ALLOWED', title: 'blocked draft' }]
      }
    }
  })
  await blockedPending

  assert.deepEqual(visibleDuringBlockedResolve, canonical)
  assert.deepEqual(badgesDuringBlockedResolve, ['宝石', '附魔'])
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), canonical)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'finger1').enhancementBadgeLabels)),
    ['宝石', '附魔']
  )
  assert.equal(page.data.enhancementBySlot.finger1.embellishmentOptionId, undefined)
})

function atomicEnhancementSheetHarness() {
  const pendingResolves = []
  const savedTemplates = []
  const toasts = []
  const navigations = []
  const storageWrites = []
  const option = (id) => ({
    id,
    optionKey: id,
    displayLabel: id,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { enchant_id: id },
    payload: { qualityRank: 2 }
  })
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '250060', id: '250060',
    variantKey: 'atomic-ring', displayName: 'Atomic Ring', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: true, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring],
      enchantOptions: [option('enchant-draft'), option('enchant-canonical')]
    }],
    resolverContext: canonicalTestResolverContext()
  }
  const selectedGearBySlot = { finger1: ring }
  const initialIntent = require('../pages/builds/gear-selection-intent').serializeGearSelectionIntent({
    resolverContext: gearPayload.resolverContext,
    eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
    selectedGearBySlot,
    enhancementBySlot: {}
  })
  const verifiedSnapshot = {
    contractRevision: 'gear-resolved-snapshot-v1',
    status: 'verified',
    resolvedGearSignature: 'sha256:atomic-old',
    dependencyVector: { gearCatalogRevision: 'gear-r17' },
    staticAttributes: {},
    setState: { itemSetCounts: {}, activeDynamicEffects: [] },
    aggregateLegality: { status: 'verified', problemCodes: [] },
    profileReadiness: { status: 'verified', simcReady: true, requiredSlots: ['finger1'], readySlots: ['finger1'] },
    constraints: {
      embellishmentMax: 2,
      slots: { finger1: { socketCount: 0, canEnchant: true, canEmbellish: false } }
    },
    resolvedSlots: {
      finger1: { itemLevel: 707, selectedOptions: { gemOptionIds: [], enchantOptionId: '', embellishmentOptionId: '' } }
    },
    problems: []
  }
  const workbench = require('../pages/builds/gear-workbench-state')
  const gearWorkbenchState = workbench.createGearWorkbenchState(gearPayload.resolverContext, initialIntent)
  Object.assign(gearWorkbenchState, {
    resolveStatus: 'verified',
    currentSnapshot: verifiedSnapshot,
    lastVerifiedSnapshot: verifiedSnapshot
  })
  const pageConfig = loadBuildsDetailPageConfig({
    savedTemplates,
    toasts,
    navigations,
    storageWrites,
    requestWebsimGearResolve(selectionIntent) {
      return new Promise((resolve, reject) => pendingResolves.push({ selectionIntent, resolve, reject }))
    }
  })
  const page = {
    gearPayloadCache: gearPayload,
    gearWorkbenchState,
    data: {
      ...pageConfig.data,
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { importCode: 'talent-code' }, gear: {} } },
      selectedSpec: { className: '法师', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearSlotSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    buildSimcContext: pageConfig.buildSimcContext,
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }
  pageConfig.refreshDerivedState.call(page)
  return { pageConfig, page, pendingResolves, savedTemplates, toasts, navigations, storageWrites }
}

async function verifiedAtomicEnhancementTransport(selectionIntent, canonicalOptionId = 'enchant-canonical') {
  const transport = await canonicalEnhancementResolveTransport(
    selectionIntent,
    'sha256:atomic-new',
    { finger1: { socketCount: 0, canEnchant: true, canEmbellish: false } }
  )
  transport.payload.data.resolvedSlots.finger1.selectedOptions.enchantOptionId = canonicalOptionId
  return transport
}

test('enhancement confirm keeps committed state unchanged while Resolve is pending', async () => {
  const { pageConfig, page, pendingResolves, savedTemplates } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })

  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  const duplicateConfirm = pageConfig.confirmGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'finger1' } }
  })

  assert.equal(pendingResolves.length, 1)
  assert.equal(duplicateConfirm, undefined)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '0/1')
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, true)
  assert.equal(page.data.gearWorkbenchView.canUseVerifiedSnapshot, true)
  assert.equal(page.data.gearWorkbenchView.canRunProfile, true)
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
  assert.equal(page.gearWorkbenchState.lastVerifiedSnapshot.resolvedSlots.finger1.selectedOptions.enchantOptionId, '')
  const profileContext = pageConfig.buildSimcContext.call(page)
  assert.equal(profileContext.simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
  assert.equal(profileContext.simulatorState.gear.selectionIntent.slots.finger1.enchantOptionId, '')
  await confirmGearTemplateSave(pageConfig, page, 'pending old verified config')
  assert.equal(savedTemplates.length, 1)
  assert.deepEqual(JSON.parse(savedTemplates[0].rawString).enhancementBySlot, {})
  assert.equal(savedTemplates[0].metadata.selectionIntent.slots.finger1.enchantOptionId, '')
  assert.doesNotMatch(JSON.stringify(savedTemplates), /enchant-draft/)

  pendingResolves[0].resolve(await verifiedAtomicEnhancementTransport(pendingResolves[0].selectionIntent))
  await pending
})

test('pending enhancement Resolve cannot be closed or reopened into a second transaction', async () => {
  const { pageConfig, page, pendingResolves } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  const pendingSheet = page.data.gearEnhancementSheet
  const pendingDraft = JSON.parse(JSON.stringify(pendingSheet.draftEnhancementBySlot))

  pageConfig.closeGearEnhancementSheet.call(page)
  pageConfig.openGearEnhancementSheet.call(page)
  const duplicateConfirm = pageConfig.confirmGearEnhancementSheet.call(page)

  assert.strictEqual(page.data.gearEnhancementSheet, pendingSheet)
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, true)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot)), pendingDraft)
  assert.equal(pendingResolves.length, 1)
  assert.equal(duplicateConfirm, undefined)

  pendingResolves[0].resolve(await verifiedAtomicEnhancementTransport(pendingResolves[0].selectionIntent))
  await pending
})

test('SimC navigation uses the committed verified enhancement while atomic Resolve is pending', async () => {
  const { pageConfig, page, pendingResolves, navigations, storageWrites } = atomicEnhancementSheetHarness()
  page.gearWorkbenchState.currentSnapshot.resolvedSlots.finger1.selectedOptions.enchantOptionId = 'enchant-canonical'
  page.data.enhancementBySlot = { finger1: { enchantOptionId: 'enchant-canonical' } }
  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  const pending = pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.gearWorkbenchState.resolveStatus, 'resolving')
  pageConfig.openSimcWithBuildContext.call(page)

  assert.equal(storageWrites.length, 1)
  assert.equal(navigations.length, 1)
  assert.match(navigations[0].url, /\/pages\/simulator\/simc\?from=builds/)
  assert.equal(storageWrites[0].value.simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
  assert.equal(
    storageWrites[0].value.simulatorState.gear.selectionIntent.slots.finger1.enchantOptionId,
    'enchant-canonical'
  )

  pendingResolves[0].resolve(await verifiedAtomicEnhancementTransport(pendingResolves[0].selectionIntent))
  await pending
})

test('SimC navigation uses the committed verified enhancement after atomic Resolve is blocked', async () => {
  const { pageConfig, page, pendingResolves, navigations, storageWrites } = atomicEnhancementSheetHarness()
  page.gearWorkbenchState.currentSnapshot.resolvedSlots.finger1.selectedOptions.enchantOptionId = 'enchant-canonical'
  page.data.enhancementBySlot = { finger1: { enchantOptionId: 'enchant-canonical' } }
  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  pendingResolves[0].resolve({
    httpStatus: 422,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'atomic-blocked-simc-entry',
      releaseContext: {},
      status: 'blocked',
      problems: [{ kind: 'ILLEGAL_SELECTION', code: 'GEAR_OPTION_NOT_ALLOWED', title: 'draft rejected' }],
      data: { contractRevision: 'gear-resolved-snapshot-v1', status: 'blocked', resolvedSlots: {} }
    }
  })
  await pending

  assert.equal(page.gearWorkbenchState.resolveStatus, 'blocked')
  pageConfig.openSimcWithBuildContext.call(page)

  assert.equal(storageWrites.length, 1)
  assert.equal(navigations.length, 1)
  assert.equal(storageWrites[0].value.simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
  assert.equal(
    storageWrites[0].value.simulatorState.gear.selectionIntent.slots.finger1.enchantOptionId,
    'enchant-canonical'
  )
})

test('SimC navigation stays blocked when no committed verified workbench exists', () => {
  const { pageConfig, page, navigations, storageWrites, toasts } = atomicEnhancementSheetHarness()
  page.gearWorkbenchState = {
    ...page.gearWorkbenchState,
    resolveStatus: 'blocked',
    currentSnapshot: null,
    readOnly: true,
    problems: [{ kind: 'ILLEGAL_SELECTION', code: 'GEAR_OPTION_NOT_ALLOWED', title: 'no committed pointer' }]
  }
  delete page.atomicEnhancementCommittedWorkbenchState
  pageConfig.refreshDerivedState.call(page)

  pageConfig.openSimcWithBuildContext.call(page)

  assert.equal(storageWrites.length, 0)
  assert.equal(navigations.length, 0)
  assert.match(toasts.at(-1).title, /尚未通过服务端校验/)
})

test('enhancement confirm atomically commits canonical options after verified Resolve', async () => {
  const { pageConfig, page, pendingResolves } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })

  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  pendingResolves[0].resolve(await verifiedAtomicEnhancementTransport(pendingResolves[0].selectionIntent))
  await pending

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {
    finger1: { enchantOptionId: 'enchant-canonical' }
  })
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '1/1')
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'finger1').enhancementBadgeLabels)),
    ['附魔']
  )
  assert.equal(page.data.gearEnhancementSheet.visible, false)
  assert.equal(
    pageConfig.buildSimcContext.call(page).simulatorState.gear.selectionIntent.slots.finger1.enchantOptionId,
    'enchant-canonical'
  )
})

test('blocked enhancement Resolve preserves committed state and editable draft', async () => {
  const { pageConfig, page, pendingResolves, savedTemplates } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  pendingResolves[0].resolve({
    httpStatus: 422,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'atomic-blocked',
      releaseContext: {},
      status: 'blocked',
      problems: [{ kind: 'ILLEGAL_SELECTION', code: 'GEAR_OPTION_NOT_ALLOWED', title: 'draft rejected' }],
      data: {
        contractRevision: 'gear-resolved-snapshot-v1',
        status: 'blocked',
        resolvedGearSignature: 'sha256:atomic-blocked',
        resolvedSlots: { finger1: { selectedOptions: { enchantOptionId: 'blocked-value' } } }
      }
    }
  })
  await pending

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
  assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'GEAR_OPTION_NOT_ALLOWED')
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '0/1')
  assert.equal(page.data.gearWorkbenchView.canUseVerifiedSnapshot, true)
  assert.equal(page.data.gearWorkbenchView.canRunProfile, true)
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
  await confirmGearTemplateSave(pageConfig, page, 'blocked old verified config')
  assert.deepEqual(JSON.parse(savedTemplates[0].rawString).enhancementBySlot, {})
  assert.doesNotMatch(JSON.stringify(savedTemplates), /enchant-draft/)
  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearWorkbenchView.canUseVerifiedSnapshot, true)
  assert.equal(page.data.gearWorkbenchView.canRunProfile, true)

  pageConfig.closeGearEnhancementSheet.call(page)
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')

  const nonAtomicPending = pageConfig.confirmAndResolveGearIntent.call(page, page.data.selectedGearBySlot, {})
  assert.equal(pendingResolves.length, 2)
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear, undefined)
  pendingResolves[1].resolve(await verifiedAtomicEnhancementTransport(pendingResolves[1].selectionIntent, ''))
  await nonAtomicPending
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-new')
})

test('enhancement revision retry transport failure restores the editable draft', async () => {
  const { pageConfig, page, pendingResolves } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  pendingResolves[0].resolve({
    httpStatus: 409,
    fromFallback: false,
    payload: {
      contractRevision: 'gear-result-envelope-v1',
      requestId: 'atomic-revision-conflict',
      releaseContext: {
        seasonRevision: 'season-r18',
        gearCatalogRevision: 'gear-r18'
      },
      status: 'blocked',
      problems: [{ kind: 'REVISION_CONFLICT', code: 'REVISION_CONFLICT', title: 'revision changed' }],
      data: {}
    }
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(pendingResolves.length, 2)
  assert.equal(page.data.gearEnhancementSheet.submitting, true)

  pendingResolves[1].reject(new Error('retry offline'))
  await pending

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
  assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'GEAR_TRANSPORT_UNAVAILABLE')
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
})

test('canonical enhancement confirm fails closed when resolver context is lost', async () => {
  const { pageConfig, page, pendingResolves, toasts } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  page.gearPayloadCache = { ...page.gearPayloadCache, resolverContext: {} }
  page.data.gearPayload = { ...page.data.gearPayload, resolverContext: {} }

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(pendingResolves.length, 0)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '0/1')
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
  assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'RESOLVER_CONTEXT_UNAVAILABLE')
  assert.match(toasts.at(-1).title, /校验上下文/)
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
})

test('canonical enhancement confirm fails closed without a verified committed pointer', () => {
  const { pageConfig, page, pendingResolves, toasts } = atomicEnhancementSheetHarness()
  page.gearWorkbenchState = {
    ...page.gearWorkbenchState,
    resolveStatus: 'blocked',
    currentSnapshot: null,
    readOnly: true,
    problems: [{ kind: 'ILLEGAL_SELECTION', code: 'GEAR_OPTION_NOT_ALLOWED', title: 'prior blocked state' }]
  }
  const intentVersion = page.gearWorkbenchState.intentVersion
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })

  pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(pendingResolves.length, 0)
  assert.equal(page.gearWorkbenchState.intentVersion, intentVersion)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
  assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'GEAR_VERIFIED_SNAPSHOT_REQUIRED')
  assert.match(toasts.at(-1).title, /已验证配置/)
})

test('verified enhancement Resolve without selectedOptions preserves committed state and draft', async () => {
  const { pageConfig, page, pendingResolves } = atomicEnhancementSheetHarness()
  page.gearWorkbenchState.currentSnapshot.resolvedSlots.finger1.selectedOptions.enchantOptionId = 'enchant-canonical'
  page.data.enhancementBySlot = { finger1: { enchantOptionId: 'enchant-canonical' } }
  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  const pending = pageConfig.confirmGearEnhancementSheet.call(page)
  const malformed = await verifiedAtomicEnhancementTransport(pendingResolves[0].selectionIntent)
  delete malformed.payload.data.resolvedSlots.finger1.selectedOptions
  pendingResolves[0].resolve(malformed)

  await pending

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {
    finger1: { enchantOptionId: 'enchant-canonical' }
  })
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.submitting, false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
  assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'GEAR_RESOLVED_OPTIONS_INCOMPLETE')
  assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
})

test('verified enhancement Resolve rejects malformed selected option shapes', async () => {
  const malformedShapes = [
    { gemOptionIds: ['gem-valid', {}], enchantOptionId: '', embellishmentOptionId: '' },
    { gemOptionIds: 'gem-not-an-array', enchantOptionId: '', embellishmentOptionId: '' },
    { gemOptionIds: ['x'.repeat(257)], enchantOptionId: '', embellishmentOptionId: '' },
    { gemOptionIds: [], enchantOptionId: {}, embellishmentOptionId: '' },
    { gemOptionIds: [], enchantOptionId: 'x'.repeat(257), embellishmentOptionId: '' },
    { gemOptionIds: [], enchantOptionId: '', embellishmentOptionId: '', craftedOptionId: {} },
    { gemOptionIds: [], enchantOptionId: '', embellishmentOptionId: '', catalystOptionId: {} }
  ]
  for (const selectedOptions of malformedShapes) {
    const { pageConfig, page, pendingResolves } = atomicEnhancementSheetHarness()
    page.gearWorkbenchState.currentSnapshot.resolvedSlots.finger1.selectedOptions.enchantOptionId = 'enchant-canonical'
    page.data.enhancementBySlot = { finger1: { enchantOptionId: 'enchant-canonical' } }
    pageConfig.refreshDerivedState.call(page)
    pageConfig.openGearEnhancementSheet.call(page)
    pageConfig.selectGearEnhancementOption.call(page, {
      currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
    })
    const pending = pageConfig.confirmGearEnhancementSheet.call(page)
    const malformed = await verifiedAtomicEnhancementTransport(pendingResolves[0].selectionIntent)
    malformed.payload.data.resolvedSlots.finger1.selectedOptions = selectedOptions
    pendingResolves[0].resolve(malformed)

    await pending

    assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {
      finger1: { enchantOptionId: 'enchant-canonical' }
    })
    assert.equal(page.data.gearEnhancementSheet.visible, true)
    assert.equal(page.data.gearEnhancementSheet.submitting, false)
    assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')
    assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'GEAR_RESOLVED_OPTIONS_INCOMPLETE')
    assert.equal(pageConfig.buildSimcContext.call(page).simulatorState.gear.resolvedGearSignature, 'sha256:atomic-old')
  }
})

test('closing enhancement sheet discards an unconfirmed draft', () => {
  const { pageConfig, page } = atomicEnhancementSheetHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-draft' } }
  })
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'enchant-draft')

  pageConfig.closeGearEnhancementSheet.call(page)
  pageConfig.openGearEnhancementSheet.call(page)

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.equal(page.data.gearEnhancementSheet.submitting, false)
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1, undefined)
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options.find((option) => option.id === 'enchant-draft').selected, false)
})

test('canonical gear workbench performs one revision-only 409 rebase and preserves slot choices', async () => {
  const requests = []
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      requests.push(selectionIntent)
      if (requests.length === 1) {
        return Promise.resolve({ httpStatus: 409, fromFallback: false, payload: {
          contractRevision: 'gear-result-envelope-v1', status: 'blocked', data: {},
          releaseContext: { seasonRevision: 'season-18', gearCatalogRevision: 'gear-r18' },
          problems: [{ kind: 'REVISION_CONFLICT', code: 'GEAR_CATALOG_REVISION_CONFLICT' }]
        } })
      }
      return Promise.resolve({ httpStatus: 200, fromFallback: false, payload: {
        contractRevision: 'gear-result-envelope-v1', status: 'resolved', problems: [], data: {
          contractRevision: 'gear-resolved-snapshot-v1', status: 'verified', resolvedGearSignature: 'sha256:rebased',
          staticAttributes: {}, setState: { itemSetCounts: {}, activeDynamicEffects: [] },
          aggregateLegality: { status: 'verified', problemCodes: [] }, profileReadiness: { status: 'verified', simcReady: true },
          constraints: {}, resolvedSlots: { head: { selectedOptions: {} } }, serializerInput: { gearItems: [] }, problems: []
        }
      } })
    }
  })
  const selection = { head: { slot: 'head', itemId: '250060', variantKey: 'v1' } }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90, slots: [{ slot: 'head' }],
    resolverContext: {
      contractRevision: 'gear-resolver-context-v1', selectionSchemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' }
    }
  }
  const page = {
    ...pageConfig,
    data: { ...pageConfig.data, activeQueryKey: 'gear', gearPayload, selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' } },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  await pageConfig.confirmAndResolveGearIntent.call(page, selection, {})

  assert.equal(requests.length, 2)
  assert.equal(requests[0].slots.head.itemId, '250060')
  assert.equal(requests[1].slots.head.itemId, '250060')
  assert.equal(requests[1].authoredAgainst.seasonRevision, 'season-18')
  assert.equal(requests[1].authoredAgainst.gearCatalogRevision, 'gear-r18')
  assert.equal(page.data.gearWorkbenchView.resolvedGearSignature, 'sha256:rebased')
})

test('canonical async stat request sends verified canonical Intent and profile context without replacing final facts', async () => {
  let statRequest = null
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve: () => Promise.resolve({
      httpStatus: 200,
      fromFallback: false,
      payload: {
        contractRevision: 'gear-result-envelope-v1', status: 'resolved', problems: [],
        data: {
          contractRevision: 'gear-resolved-snapshot-v1', status: 'verified',
          resolvedGearSignature: 'sha256:stat-bound', dependencyVector: {},
          staticAttributes: { intellect: 321 }, setState: { itemSetCounts: {}, activeDynamicEffects: [] },
          aggregateLegality: { status: 'verified', problemCodes: [] },
          profileReadiness: { status: 'verified', simcReady: true, requiredSlots: ['head'], readySlots: ['head'] },
          constraints: {}, resolvedSlots: { head: { itemLevel: 700, selectedOptions: { enchantOptionId: 'server-enchant' } } },
          serializerInput: { gearItems: [{ slot: 'head', id: 'server-item', bonus_id: 'server-bonus' }] }, problems: []
        }
      }
    }),
    requestWebsimGearStatSnapshot(selectionIntent, profileContext) {
      statRequest = { selectionIntent, profileContext }
      return Promise.resolve({
        httpStatus: 200,
        fromFallback: false,
        payload: {
          contractRevision: 'gear-result-envelope-v1', status: 'resolved', problems: [], data: {
            statSignature: 'sha256:server-stat',
            statSnapshot: {
              statStatus: 'verified', blockers: [],
              primary: { key: 'intellect', value: '999999', rawValue: 999999 }
            }
          }
        }
      })
    }
  })
  const forged = { head: { slot: 'head', itemId: '250060', variantKey: 'v1', itemStats: { intellect: 999999 }, simcReady: true } }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'head', simcSlot: 'head' }], equippedSet: forged,
    replacementCandidates: [], slotReadiness: {}, readiness: {},
    resolverContext: {
      contractRevision: 'gear-resolver-context-v1', selectionSchemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' }
    }
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data, activeQueryKey: 'gear', gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedDetail: { details: { talents: { importCode: 'C4DA' }, gear: {} } },
      selectedGearBySlot: forged, enhancementBySlot: { head: { enchantOptionId: 'client-enchant' } }
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  await pageConfig.confirmAndResolveGearIntent.call(page, forged, page.data.enhancementBySlot)
  await pageConfig.refreshGearStats.call(page)

  assert.equal(statRequest.selectionIntent.slots.head.itemId, '250060')
  assert.equal(statRequest.selectionIntent.slots.head.enchantOptionId, 'server-enchant')
  assert.deepEqual(Object.keys(statRequest.profileContext).sort(), ['scenarioKey', 'talents'])
  assert.equal(statRequest.profileContext.talents, 'C4DA')
  assert.equal(statRequest.profileContext.scenarioKey, 'single')
  assert.equal(statRequest.profileContext.gearSelection, undefined)
  assert.equal(page.gearStatSnapshotState.statSnapshotSignature, 'sha256:server-stat')
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'intellect').value, '321')
  assert.equal(page.data.gearWorkbenchView.canRunProfile, true)
})

test('canonical save gate binds Intent signature and dependency vector to legacy template metadata', async () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({
    savedTemplates,
    toasts,
    requestWebsimGearResolve: (selectionIntent) => Promise.resolve({
      httpStatus: 200, fromFallback: false,
      payload: { contractRevision: 'gear-result-envelope-v1', status: 'resolved', problems: [], data: {
        contractRevision: 'gear-resolved-snapshot-v1', status: 'verified',
        resolvedGearSignature: 'sha256:saved', dependencyVector: { gearCatalogRevision: 'gear-r17' },
        staticAttributes: {}, setState: { itemSetCounts: {}, activeDynamicEffects: [] },
        aggregateLegality: { status: 'verified', problemCodes: [] },
        profileReadiness: { status: 'verified', simcReady: true, requiredSlots: ['head'], readySlots: ['head'] },
        constraints: {},
        resolvedSlots: Object.keys(selectionIntent.slots || {}).reduce((result, slot) => {
          result[slot] = { selectedOptions: {} }
          return result
        }, {}),
        serializerInput: { gearItems: [] }, problems: []
      } }
    })
  })
  const selection = completeGearSelection()
  selection.head.variantKey = 'v1'
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot })), equippedSet: selection,
    replacementCandidates: [], slotReadiness: {}, readiness: {},
    resolverContext: {
      contractRevision: 'gear-resolver-context-v1', selectionSchemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' }
    }
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data, activeQueryKey: 'gear', gearPayload, selectedGearBySlot: selection, enhancementBySlot: {},
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { importCode: 'C4DA' }, gear: {} } }
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  page.gearWorkbenchState = { ...require('../pages/builds/gear-workbench-state').createGearWorkbenchState(gearPayload.resolverContext, {}), resolveStatus: 'blocked' }
  pageConfig.saveGearTemplate.call(page)
  assert.match(toasts.at(-1).title, /尚未通过服务端校验/)

  await pageConfig.confirmAndResolveGearIntent.call(page, selection, {})
  await confirmGearTemplateSave(pageConfig, page, '可信配置')

  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].metadata.resolvedGearSignature, 'sha256:saved')
  assert.deepEqual(savedTemplates[0].metadata.dependencyVector, { gearCatalogRevision: 'gear-r17' })
  assert.equal(savedTemplates[0].metadata.selectionIntent.slots.head.itemId, '250000')
  assert.equal(savedTemplates[0].metadata.selectionIntent.slots.head.simcReady, undefined)
})

test('gear detail summarizes selected equipment attributes above the slot grid', async () => {
  const selectedGear = completeGearSelection(['head', 'chest', 'finger1'])
  selectedGear.head = {
    ...selectedGear.head,
    ilevel: 298,
    statSummary: '智力 120；耐力 240；急速 30；暴击 20；精通 10；全能 5；护甲 100',
    sourceType: 'tier_set',
    itemSetName: '虚空粉碎者协律',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  selectedGear.chest = {
    ...selectedGear.chest,
    ilevel: 289,
    statSummary: '敏捷 or 智力 80；耐力 160；急速 15；精通 7；护甲 80',
    sourceTypes: ['raid', 'tier_set'],
    setName: '虚空粉碎者协律',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  selectedGear.finger1 = {
    ...selectedGear.finger1,
    ilevel: 286,
    statSummary: '力量/敏捷/智力 50；耐力 90；暴击 12；全能 6',
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false, socketCount: 1 }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: canonicalGearSlots.map((slot) => ({
          slot,
          simcSlot: slot,
          label: slot,
          items: [],
          socketOptions: slot === 'finger1'
            ? [{ id: 'gem-rank-two', label: '迅捷宝石', statSummary: '+147急速', status: 'verified', simcOptions: { gem_id: '240983' }, payload: { qualityRank: 2 } }]
            : [],
          enchantOptions: slot === 'finger1'
            ? [{
                id: 'enchant-rank-two',
                label: '自然之怒',
                displayLabel: '自然之怒',
                displayKind: 'name',
                displayStatus: 'verified',
                evidenceSource: 'wago_db2_spell_item_enchantment',
                status: 'verified',
                simcOptions: { enchant_id: '7334' },
                payload: { qualityRank: 2 }
              }]
            : []
        })),
        equippedSet: selectedGear,
        slotReadiness: {},
        readiness: { fullReady: false },
        statConversion: {
          status: 'ready',
          level: 90,
          stats: {
            haste: { ratingPerPercent: 44, precision: 1, displaySuffix: '%' },
            crit: { ratingPerPercent: 46, precision: 1, displaySuffix: '%' },
            mastery: {
              ratingPerMasteryPoint: 46,
              precision: 1,
              displaySuffix: '%',
              effect: { percentPerPoint: 2, label: '冰锥' }
            },
            versatility: { ratingPerPercent: 54, precision: 1, displaySuffix: '%' }
          },
          diminishingReturns: []
        },
        communityTemplates: []
      }
    })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      enhancementBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  const panel = page.data.gearAttributePanel
  assert.equal(panel.visible, true)
  assert.equal(panel.summary, '已选 3/16 槽')
  assert.equal(panel.itemLevel.value, '291')
  assert.equal(panel.primaryStat, undefined)
  assert.equal(panel.resourceRows, undefined)
  assert.equal(panel.statRows.find((row) => row.key === 'itemLevel'), undefined)
  assert.equal(panel.statRows.find((row) => row.key === 'intellect').label, '智力')
  assert.equal(panel.statRows.find((row) => row.key === 'intellect').value, '250')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'embellishment').value, '0/2')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'gem').value, '0/1')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'enchant').value, '0/1')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'tierSet').label, '套装')
  assert.equal(panel.enhancementRows.find((row) => row.key === 'tierSet').value, '2/5')
  assert.equal(panel.statRows.find((row) => row.key === 'stamina').value, '490')
  assert.equal(panel.statRows.find((row) => row.key === 'haste').value, '45')
  assert.equal(panel.statRows.find((row) => row.key === 'haste').convertedValue, undefined)
  assert.equal(panel.statRows.find((row) => row.key === 'crit').value, '32')
  assert.equal(panel.statRows.find((row) => row.key === 'crit').convertedValue, undefined)
  assert.equal(panel.statRows.find((row) => row.key === 'mastery').value, '17')
  assert.equal(panel.statRows.find((row) => row.key === 'mastery').convertedValue, undefined)
  assert.equal(panel.statRows.find((row) => row.key === 'versatility').value, '11')
  assert.equal(panel.statRows.find((row) => row.key === 'versatility').convertedValue, undefined)
})

test('gear attribute panel displays SimC verified character percentages when available', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const page = {
    gearPayloadCache: {
      slots,
      replacementCandidates: [],
      equippedSet: {},
      slotReadiness: {},
      readiness: { fullReady: true }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true }
      },
      gearStatSnapshot: {
        statStatus: 'verified',
        statSource: 'simulationcraft_json',
        primary: { key: 'intellect', label: '智力', value: '2,344', rawValue: 2344 },
        stamina: { key: 'stamina', label: '耐力', value: '20,067', rawValue: 20067 },
        secondary: [
          { key: 'crit', label: '暴击', value: '994', rawValue: 994, convertedValue: '28.6%', convertedRawValue: 28.60869565217391 },
          { key: 'haste', label: '急速', value: '554', rawValue: 554, convertedValue: '18.3%', convertedRawValue: 18.288009090909108 },
          { key: 'mastery', label: '精通', value: '545', rawValue: 545, convertedValue: '36.6%', convertedRawValue: 36.55652173913044 },
          { key: 'versatility', label: '全能', value: '83', rawValue: 83, convertedValue: '1.5%', convertedRawValue: 1.5370370370370372 }
        ]
      },
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {
        head: {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250101',
          displayName: 'Snapshot Helm',
          ilevel: 289,
          statSummary: '智力 120；耐力 240；暴击 12；急速 8'
        }
      },
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const panel = page.data.gearAttributePanel
  assert.equal(panel.statRows.find((row) => row.key === 'intellect').value, '2,344')
  assert.equal(panel.statRows.find((row) => row.key === 'stamina').value, '20,067')
  assert.equal(panel.statRows.find((row) => row.key === 'crit').value, '994')
  assert.equal(panel.statRows.find((row) => row.key === 'crit').convertedValue, '28.6%')
  assert.equal(panel.statRows.find((row) => row.key === 'haste').convertedValue, '18.3%')
  assert.equal(panel.statRows.find((row) => row.key === 'mastery').convertedValue, '36.6%')
  assert.equal(panel.statRows.find((row) => row.key === 'versatility').convertedValue, '1.5%')
})

test('gear attribute panel counts governed socket slots and caps tier set pieces', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  const enchantSlots = ['back', 'chest', 'wrist', 'legs', 'feet', 'finger1', 'finger2', 'main_hand', 'off_hand']
  ;['head', 'shoulder', 'chest', 'hands', 'legs', 'back'].forEach((slot) => {
    selection[slot] = {
      ...selection[slot],
      sourceType: 'tier_set',
      itemSetName: 'Current Season Set'
    }
  })
  selection.neck = {
    ...selection.neck,
    gem_id: '240983/240898',
    gem_ilevel: '707/707',
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  enchantSlots.forEach((slot) => {
    selection[slot] = {
      ...selection[slot],
      enchant_id: slot === 'main_hand' || slot === 'off_hand' ? '8039' : '7334',
      modCapabilities: { ...((selection[slot] && selection[slot].modCapabilities) || {}), canEnchant: true }
    }
  })
  selection.finger1.modCapabilities = { ...selection.finger1.modCapabilities, hasSocket: true }
  selection.finger2.modCapabilities = { ...selection.finger2.modCapabilities, hasSocket: true }
  const page = {
    gearPayloadCache: {
      slots,
      replacementCandidates: [],
      equippedSet: {},
      slotReadiness: {},
      readiness: { fullReady: true }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true }
      },
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const rows = page.data.gearAttributePanel.enhancementRows
  assert.equal(rows.find((row) => row.key === 'gem').value, '0/3')
  assert.equal(rows.find((row) => row.key === 'enchant').value, '0/7')
  assert.equal(rows.find((row) => row.key === 'tierSet').value, '5/5')
})

test('gear attribute panel honors backend socketCount evidence instead of slot defaults', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.neck = {
    ...selection.neck,
    modCapabilities: { hasSocket: true, socketCount: 2 }
  }
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, socketCount: 1 }
  }
  selection.finger2 = {
    ...selection.finger2,
    modCapabilities: { hasSocket: false, socketCount: 0 }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const rows = page.data.gearAttributePanel.enhancementRows
  assert.equal(rows.find((row) => row.key === 'gem').value, '0/3')
})

test('gear attribute panel excludes held off-hand items from enchant capacity', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = {
    main_hand: {
      slot: 'main_hand',
      simcSlot: 'main_hand',
      itemId: '250100',
      displayName: 'Enchantable weapon',
      ilevel: 289,
      enchant_id: '7981',
      weaponType: 'Dagger',
      modCapabilities: { canEnchant: true }
    },
    off_hand: {
      slot: 'off_hand',
      simcSlot: 'off_hand',
      itemId: '245769',
      displayName: 'Held off-hand lantern',
      ilevel: 289,
      weaponType: 'Held In Off-hand',
      modCapabilities: { canEnchant: true }
    }
  }
  const page = {
    gearPayloadCache: {
      slots,
      replacementCandidates: [],
      equippedSet: {},
      slotReadiness: {},
      readiness: { fullReady: true }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true }
      },
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const rows = page.data.gearAttributePanel.enhancementRows
  assert.equal(rows.find((row) => row.key === 'enchant').value, '0/1')
})

test('gear attribute panel counts only user configured gems and enchants against governed slots', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.head = {
    ...selection.head,
    gem_id: '240983',
    modCapabilities: { hasSocket: false }
  }
  selection.neck = {
    ...selection.neck,
    gem_id: '240908/240906',
    modCapabilities: { hasSocket: true, socketCount: 1 }
  }
  selection.wrist = {
    ...selection.wrist,
    gem_id: '240908',
    modCapabilities: { hasSocket: false, canEnchant: true }
  }
  selection.waist = {
    ...selection.waist,
    gem_id: '240908',
    enchant_id: '4223',
    modCapabilities: { hasSocket: false, canEnchant: false }
  }
  selection.chest = {
    ...selection.chest,
    enchant_id: '7987',
    modCapabilities: { canEnchant: true }
  }
  selection.legs = {
    ...selection.legs,
    enchant_id: '7935',
    modCapabilities: { canEnchant: true }
  }
  selection.finger1 = {
    ...selection.finger1,
    gem_id: '240908/240906',
    enchant_id: '7967',
    modCapabilities: { hasSocket: true, canEnchant: true, socketCount: 1 }
  }
  selection.finger2 = {
    ...selection.finger2,
    gem_id: '240908',
    enchant_id: '7967',
    modCapabilities: { hasSocket: true, canEnchant: true, socketCount: 1 }
  }
  selection.main_hand = {
    ...selection.main_hand,
    enchant_id: '7981',
    weaponType: 'Dagger',
    modCapabilities: { canEnchant: true }
  }
  selection.off_hand = {
    ...selection.off_hand,
    enchant_id: '8039',
    weaponType: 'Held In Off-hand',
    modCapabilities: { canEnchant: true }
  }
  ;['back', 'feet'].forEach((slot) => {
    selection[slot] = {
      ...selection[slot],
      modCapabilities: { canEnchant: true }
    }
  })
  const page = {
    gearPayloadCache: {
      slots,
      replacementCandidates: [],
      equippedSet: {},
      slotReadiness: {},
      readiness: { fullReady: true }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true }
      },
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const rows = page.data.gearAttributePanel.enhancementRows
  assert.equal(rows.find((row) => row.key === 'gem').value, '0/3')
  assert.equal(rows.find((row) => row.key === 'enchant').value, '0/7')
})

test('gear attribute panel keeps governed enchant cap when only selected enchants are restored', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  ;['back', 'chest', 'legs', 'feet', 'finger1', 'finger2', 'main_hand'].forEach((slot) => {
    selection[slot] = {
      ...selection[slot],
      weaponType: slot === 'main_hand' ? 'Dagger' : selection[slot].weaponType,
      modCapabilities: { canEnchant: true }
    }
  })
  selection.wrist = {
    ...selection.wrist,
    modCapabilities: { canEnchant: true }
  }
  selection.off_hand = {
    ...selection.off_hand,
    weaponType: 'Held In Off-hand',
    modCapabilities: { canEnchant: true }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        chest: { enchantOptionId: 'restored-chest-enchant', enchant_id: '7987' },
        legs: { enchantOptionId: 'restored-leg-armor-kit', enchant_id: '8159' }
      },
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '2/7')
})

test('gear attribute panel counts enchant cap from configurable rows including leg armor patches', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  const enchantSlots = ['back', 'chest', 'wrist', 'legs', 'feet', 'finger1', 'finger2', 'main_hand']
  enchantSlots.forEach((slot) => {
    selection[slot] = {
      ...selection[slot],
      weaponType: slot === 'main_hand' ? 'Dagger' : selection[slot].weaponType,
      modCapabilities: { canEnchant: true }
    }
  })
  const visibleEnchantSlots = ['back', 'chest', 'legs', 'feet', 'finger1', 'finger2', 'main_hand']
  const labelBySlot = {
    back: '披风附魔',
    chest: '胸部附魔',
    legs: '森林猎手的护甲片',
    feet: '脚部附魔',
    finger1: '戒指附魔',
    finger2: '戒指附魔',
    main_hand: '武器附魔'
  }
  const idBySlot = {
    back: '7987',
    chest: '7983',
    legs: '8159',
    feet: '8019',
    finger1: '7967',
    finger2: '7997',
    main_hand: '8039'
  }
  const optionForSlot = (slot) => ({
    id: `enchant-${slot}`,
    label: labelBySlot[slot],
    displayLabel: labelBySlot[slot],
    displayKind: 'name',
    displayStatus: 'verified',
    evidenceSource: 'wago_db2_spell_item_enchantment',
    status: 'verified',
    simcOptions: { enchant_id: idBySlot[slot] },
    payload: { qualityRank: 2, displayStatus: 'verified', evidenceSource: 'wago_db2_spell_item_enchantment' }
  })
  const gearPayload = {
    slots,
    replacementCandidates: visibleEnchantSlots.map((slot) => ({
      slot,
      simcSlot: slot,
      label: slot,
      items: [],
      enchantOptions: [optionForSlot(slot)]
    })),
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '0/7')

  pageConfig.openGearEnhancementSheet.call(page)
  const configurableSlots = page.data.gearEnhancementSheet.equipmentRows.map((row) => row.slot)
  assert.equal(configurableSlots.includes('legs'), true)
  assert.equal(configurableSlots.includes('wrist'), false)
  assert.equal(page.data.gearEnhancementSheet.enchantRows.find((row) => row.slot === 'legs').options[0].label, '森林猎手的护甲片')
})

test('gear enhancement sheet loads only the selected slot detail on demand', async () => {
  const requests = []
  let finishRequest
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear(params) {
      requests.push(params)
      return new Promise((resolve) => {
        finishRequest = () => resolve({
          fromFallback: false,
          error: '',
          payload: {
            replacementCandidates: [{
              slot: params.slot,
              simcSlot: params.slot,
              detailMode: 'complete',
              items: [],
              enchantOptions: [{
                id: 'uuid-back-enchant',
                optionKey: 'authority-back-enchant',
                name: '披风附魔',
                label: '披风附魔',
                status: 'verified',
                simcOptions: { enchant_id: '1234' }
              }]
            }]
          }
        })
      })
    }
  })
  const selectedGearBySlot = {
    back: {
      slot: 'back',
      itemId: '250060',
      variantKey: 'back-v1',
      modCapabilities: { canEnchant: true }
    },
    shoulder: {
      slot: 'shoulder',
      itemId: '250061',
      variantKey: 'shoulder-v1',
      modCapabilities: { canEnchant: true }
    }
  }
  const gearPayload = {
    gearPayloadMode: 'initial',
    slots: [
      { slot: 'back', simcSlot: 'back', label: '背部' },
      { slot: 'shoulder', simcSlot: 'shoulder', label: '肩部' }
    ],
    replacementCandidates: [
      { slot: 'back', simcSlot: 'back', detailMode: 'partial', items: [] },
      { slot: 'shoulder', simcSlot: 'shoulder', detailMode: 'partial', items: [] }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      ...pageConfig.data,
      activeQueryKey: 'gear',
      gearPayload,
      gearSelectionKey: 'mage:frost',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await pageConfig.openGearEnhancementSheet.call(page)
  assert.equal(requests.length, 0)
  assert.equal(page.data.gearEnhancementSheet.loading, false)
  assert.equal(page.data.gearEnhancementSheet.emptyText, '请选择装备槽位加载可配置选项。')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.equipmentRows.map((row) => row.slot)), JSON.stringify(['back']))
  assert.equal(page.data.gearEnhancementSheet.equipmentRows[0].typeSummary, '加载选项')

  const detailPromise = pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'back' } }
  })
  assert.equal(requests.length, 1)
  assert.equal(requests[0].slot, 'back')
  assert.equal(page.data.gearEnhancementSheet.loading, true)
  finishRequest()
  await detailPromise

  assert.equal(requests.length, 1)
  assert.equal(page.data.gearEnhancementSheet.loading, false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'back')
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].id, 'authority-back-enchant')
  await pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'back' } }
  })
  assert.equal(requests.length, 1)
})

test('canonical gear enhancement sheet ignores raw embedded SimC enhancement fields', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const selectedGearBySlot = {
    waist: {
      slot: 'waist',
      itemId: '250060',
      variantKey: 'waist-v1',
      gem_id: '240908',
      enchant_id: '7967',
      embellishment: 'legacy_embellishment',
      modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: true }
    }
  }
  const gearPayload = {
    gearPayloadMode: 'initial',
    slots: [{ slot: 'waist', simcSlot: 'waist', label: '腰部' }],
    replacementCandidates: [{ slot: 'waist', simcSlot: 'waist', detailMode: 'partial', items: [] }],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearWorkbenchState: {
      resolveStatus: 'verified',
      activeRequest: null,
      offline: false,
      readOnly: false,
      currentSnapshot: {
        status: 'verified',
        resolvedGearSignature: 'sha256:canonical-raw-fields',
        constraints: {
          embellishmentMax: 2,
          slots: {
            waist: { socketCount: 0, canEnchant: false, canEmbellish: false }
          }
        },
        resolvedSlots: { waist: { selectedOptions: {} } }
      }
    },
    gearPayloadCache: gearPayload,
    data: {
      ...pageConfig.data,
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.embellishmentUsed, 0)
  assert.equal(page.data.gearEnhancementSheet.embellishmentMax, 2)
  assert.deepEqual(Array.from(page.data.gearEnhancementSheet.blockers), [])
  assert.deepEqual(Array.from(page.data.gearEnhancementSheet.equipmentRows), [])
  assert.equal(page.data.gearEnhancementSheet.emptyText, '当前已选装备没有可配置的宝石、附魔或美化。')
})

test('gear attribute panel and slot badges reflect configured neck and ring gems', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  ;['neck', 'finger1', 'finger2'].forEach((slot) => {
    selection[slot] = {
      ...selection[slot],
      modCapabilities: { hasSocket: true, canEnchant: slot !== 'neck', socketCount: 1 }
    }
  })
  const gearPayload = {
    slots,
    replacementCandidates: [],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        neck: { socketOptionId: 'gem-neck', gem_id: '240901' },
        finger1: { socketOptionId: 'gem-finger1', gem_id: '240902' },
        finger2: { socketOptionId: 'gem-finger2', gem_id: '240903' }
      },
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const rows = page.data.gearAttributePanel.enhancementRows
  assert.equal(rows.find((row) => row.key === 'gem').value, '3/3')
  ;['neck', 'finger1', 'finger2'].forEach((slot) => {
    assert.equal(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === slot).enhancementBadgeLabels), JSON.stringify(['宝石']))
  })
})

test('gear attribute panel maps hybrid primary stat labels to the active spec', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const page = {
    gearPayloadCache: {
      slots,
      replacementCandidates: [],
      equippedSet: {},
      slotReadiness: {},
      readiness: { fullReady: false }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false }
      },
      selectedSpec: { websimClassKey: 'paladin', websimSpecKey: 'holy' },
      selectedGearBySlot: {
        head: {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250101',
          displayName: 'Hybrid Helm',
          ilevel: 289,
          statSummary: '力量 or 智力 120；耐力 240'
        }
      },
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.primaryStat, undefined)
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'intellect').label, '智力')
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'intellect').value, '120')

  page.data.selectedSpec = { websimClassKey: 'rogue', websimSpecKey: 'subtlety' }
  page.data.selectedGearBySlot = {
    head: {
      slot: 'head',
      simcSlot: 'head',
      itemId: '250102',
      displayName: 'Hybrid Hood',
      ilevel: 289,
      statSummary: 'stragi 80；耐力 160'
    }
  }
  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.primaryStat, undefined)
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'agility').label, '敏捷')
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'agility').value, '80')
})

test('gear attribute panel includes selected gem stat bonuses', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection(['finger1', 'finger2'])
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  selection.finger2 = {
    ...selection.finger2,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'finger1',
        simcSlot: 'finger1',
        label: 'finger1',
        items: [],
        socketOptions: [
          {
            id: 'gem-primary',
            displayLabel: '+32主属性',
            displayKind: 'stat',
            displayStatus: 'verified',
            evidenceSource: 'live_tooltip_seed',
            status: 'verified',
            simcOptions: { gem_id: '240888', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ]
      },
      {
        slot: 'finger2',
        simcSlot: 'finger2',
        label: 'finger2',
        items: [],
        socketOptions: [
          {
            id: 'gem-mastery-crit',
            statSummary: '+16精通 +7暴击',
            displayKind: 'stat',
            displayStatus: 'verified',
            evidenceSource: 'live_tooltip_seed',
            status: 'verified',
            simcOptions: { gem_id: '240898', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: false },
    statConversion: {
      status: 'ready',
      level: 90,
      stats: {
        crit: { ratingPerPercent: 46, precision: 1, displaySuffix: '%' },
        mastery: {
          ratingPerMasteryPoint: 46,
          precision: 1,
          displaySuffix: '%',
          effect: { percentPerPoint: 2, label: '冰锥' }
        }
      },
      diminishingReturns: []
    }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'gem', id: 'gem-primary' } }
  })
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger2', type: 'gem', id: 'gem-mastery-crit' } }
  })
  pageConfig.confirmGearEnhancementSheet.call(page)

  const panel = page.data.gearAttributePanel
  assert.equal(panel.enhancementRows.find((row) => row.key === 'gem').value, '2/2')
  assert.equal(panel.statRows.find((row) => row.key === 'intellect').value, '32')
  assert.equal(panel.statRows.find((row) => row.key === 'mastery').value, '16')
  assert.equal(panel.statRows.find((row) => row.key === 'mastery').convertedValue, undefined)
  assert.equal(panel.statRows.find((row) => row.key === 'crit').value, '7')
  assert.equal(panel.statRows.find((row) => row.key === 'crit').convertedValue, undefined)
})

test('gear enhancement sheet filters configurable slots and disables extra embellishments at the cap', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false }
  }
  selection.finger2 = {
    ...selection.finger2,
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
  }
  selection.back = {
    ...selection.back,
    embellishment: 'dawnthread_lining'
  }
  selection.chest = {
    ...selection.chest,
    intrinsicEmbellishment: 'duskthread_lining'
  }
  selection.hands = {
    ...selection.hands,
    sourceType: 'dungeon',
    modCapabilities: { hasSocket: false, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'finger1',
        simcSlot: 'finger1',
        label: 'finger1',
        items: [],
        socketOptions: [
          {
            id: 'gem-rank-two',
            label: '迅捷宝石',
            statSummary: '+147急速',
            status: 'verified',
            simcOptions: { gem_id: '240983', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ],
        enchantOptions: [
          {
            id: 'enchant-rank-two',
            label: '自然之怒',
            displayLabel: '自然之怒',
            displayKind: 'name',
            displayStatus: 'verified',
            evidenceSource: 'wago_db2_spell_item_enchantment',
            status: 'verified',
            simcOptions: { enchant_id: '7334' },
            payload: { qualityRank: 2 }
          }
        ]
      },
      {
        slot: 'finger2',
        simcSlot: 'finger2',
        label: 'finger2',
        items: [],
        socketOptions: [
          {
            id: 'gem-rank-two-finger2',
            label: '迅捷宝石',
            status: 'verified',
            simcOptions: { gem_id: '240983', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ]
      },
      {
        slot: 'wrist',
        simcSlot: 'wrist',
        label: 'wrist',
        items: [],
        embellishmentOptions: [
          {
            id: 'embellishment-blue-silken-lining',
            label: '蓝色丝质内衬',
            displayLabel: '蓝色丝质内衬',
            displayKind: 'name',
            displayStatus: 'verified',
            evidenceSource: 'server_owned_evidence_seed',
            status: 'verified',
            simcOptions: { embellishment: 'blue_silken_lining' },
            payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
          }
        ]
      },
      {
        slot: 'hands',
        simcSlot: 'hands',
        label: 'hands',
        items: [],
        embellishmentOptions: [
          {
            id: 'embellishment-hands',
            label: '蓝色丝质内衬',
            displayLabel: '蓝色丝质内衬',
            displayKind: 'name',
            displayStatus: 'verified',
            evidenceSource: 'server_owned_evidence_seed',
            status: 'verified',
            simcOptions: { embellishment: 'blue_silken_lining' },
            payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '0/1')
  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.gemRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.enchantRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.embellishmentRows.map((row) => row.slot)), JSON.stringify(['wrist']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.equipmentRows.map((row) => row.slot)), JSON.stringify(['finger1', 'wrist']))
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.activeTitle, '戒指 1')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeGemRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeEnchantRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeEmbellishmentRows.map((row) => row.slot)), JSON.stringify([]))
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options[0].label, '+147急速')
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].label, '自然之怒')
  assert.equal(page.data.gearEnhancementSheet.embellishmentUsed, 2)
  assert.equal(page.data.gearEnhancementSheet.embellishmentMax, 2)
  assert.equal(page.data.gearEnhancementSheet.embellishmentRows[0].options[0].disabled, true)

  pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'wrist' } }
  })
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'wrist')
  assert.equal(page.data.gearEnhancementSheet.activeTitle, '护腕')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeGemRows.map((row) => row.slot)), JSON.stringify([]))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeEnchantRows.map((row) => row.slot)), JSON.stringify([]))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeEmbellishmentRows.map((row) => row.slot)), JSON.stringify(['wrist']))
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options[0].label, '蓝色丝质内衬')

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'gem', id: 'gem-rank-two' } }
  })
  assert.deepEqual(page.data.enhancementBySlot, {})
  assert.equal(page.data.gearEnhancementSheet.gemRows.find((row) => row.slot === 'finger1').options[0].selected, true)
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '0/1')
  pageConfig.confirmGearEnhancementSheet.call(page)
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '1/1')
})

test('gear enhancement sheet hides options without backend readable display evidence', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.neck = {
    ...selection.neck,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  selection.main_hand = {
    ...selection.main_hand,
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: false, canEmbellish: true }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'neck',
        simcSlot: 'neck',
        label: 'neck',
        items: [],
        socketOptions: [
          {
            id: 'legacy-gem-240983',
            name: 'Quick Gem',
            status: 'verified',
            simcOptions: { gem_id: '240983' }
          }
        ]
      },
      {
        slot: 'main_hand',
        simcSlot: 'main_hand',
        label: 'main_hand',
        items: [],
        enchantOptions: [
          {
            id: 'observed-enchant-8017',
            name: 'Observed enchant 8017',
            status: 'verified',
            simcOptions: { enchant_id: '8017' }
          }
        ]
      },
      {
        slot: 'wrist',
        simcSlot: 'wrist',
        label: 'wrist',
        items: [],
        embellishmentOptions: [
          {
            id: 'seed-embellishment-blue-silken-lining',
            name: 'Blue Silken Lining',
            status: 'verified',
            simcOptions: { embellishment: 'blue_silken_lining' },
            payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)
  assert.equal(page.data.gearEnhancementSheet.equipmentRows.some((row) => row.slot === 'neck'), false)
  assert.equal(page.data.gearEnhancementSheet.equipmentRows.some((row) => row.slot === 'main_hand'), false)
  assert.equal(page.data.gearEnhancementSheet.equipmentRows.some((row) => row.slot === 'wrist'), false)
  assert.equal(page.data.gearEnhancementSheet.activeSlot, '')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeGemRows), JSON.stringify([]))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeEnchantRows), JSON.stringify([]))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.activeEmbellishmentRows), JSON.stringify([]))
  assert.doesNotMatch(JSON.stringify(page.data.gearEnhancementSheet), /武器附魔 8017|Observed enchant 8017|Blue Silken Lining|属性待补|附魔待补|美化待补/)
})

test('gear enhancement sheet shows socket enchant and embellishment groups for the same ring slot', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.finger1 = {
    ...selection.finger1,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: true }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'finger1',
        simcSlot: 'finger1',
        label: 'finger1',
        items: [],
        socketOptions: [
          {
            id: 'gem-stat-primary',
            label: '无瑕宝石',
            displayLabel: '+32主属性',
            displayKind: 'stat',
            displayStatus: 'verified',
            evidenceSource: 'battle_net_item_metadata',
            status: 'verified',
            simcOptions: { gem_id: '240888', gem_ilevel: '707' },
            payload: { qualityRank: 2 }
          }
        ],
        enchantOptions: [
          {
            id: 'enchant-ring-nature',
            label: '自然之怒',
            displayLabel: '自然之怒',
            displayKind: 'name',
            displayStatus: 'verified',
            evidenceSource: 'wago_db2_spell_item_enchantment',
            status: 'verified',
            simcOptions: { enchant_id: '7967' },
            payload: { qualityRank: 2 }
          }
        ],
        embellishmentOptions: [
          {
            id: 'embellishment-arcanoweave',
            label: '奥纹内衬',
            displayLabel: '奥纹内衬',
            displayKind: 'name',
            displayStatus: 'verified',
            evidenceSource: 'server_owned_evidence_seed',
            status: 'verified',
            simcOptions: { embellishment: 'arcanoweave_lining' },
            payload: { qualityRank: 2, simcKey: 'arcanoweave_lining' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.equipmentRows.map((row) => row.typeSummary)), JSON.stringify(['宝石 / 附魔 / 美化']))
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options[0].label, '+32主属性')
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].label, '自然之怒')
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options[0].label, '奥纹内衬')

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'gem', id: 'gem-stat-primary' } }
  })
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'enchant-ring-nature' } }
  })
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'embellishment', id: 'embellishment-arcanoweave' } }
  })

  assert.deepEqual(page.data.enhancementBySlot, {})
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options[0].selected, true)
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].selected, true)
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options[0].selected, true)
  pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(JSON.stringify(page.data.enhancementBySlot.finger1), JSON.stringify({
    gemOptionIds: ['gem-stat-primary'],
    enchantOptionId: 'enchant-ring-nature',
    embellishmentOptionId: 'embellishment-arcanoweave',
    enchant_id: '7967',
    embellishment: 'arcanoweave_lining'
  }))
  const enhancedCard = page.data.gearSlotRows.find((row) => row.slot === 'finger1')
  const untouchedCard = page.data.gearSlotRows.find((row) => row.slot === 'finger2')
  assert.equal(JSON.stringify(enhancedCard.enhancementBadgeLabels), JSON.stringify(['宝石', '附魔', '美化']))
  assert.equal(JSON.stringify(untouchedCard.enhancementBadgeLabels), JSON.stringify([]))
  assert.doesNotMatch(JSON.stringify(page.data.enhancementBySlot), /自然之怒|奥纹内衬|\+32主属性/)
})

test('gear enhancement sheet shows darkmoon sigils for crafted weapon slots', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.main_hand = {
    ...selection.main_hand,
    displayName: '魔导师的法力之剑',
    sourceType: 'crafted',
    variantSource: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'main_hand',
        simcSlot: 'main_hand',
        label: 'main_hand',
        items: [],
        embellishmentOptions: [
          {
            id: 'seed-embellishment-darkmoon-sigil-hunt-rank-2',
            label: '暗月徽记：狩猎',
            displayLabel: '暗月徽记：狩猎',
            displayKind: 'name',
            displayStatus: 'verified',
            evidenceSource: 'wowhead_item+simulationcraft+method',
            status: 'verified',
            slotGroup: 'weapon',
            simcOptions: { embellishment: 'darkmoon_sigil_hunt' },
            payload: { qualityRank: 2, simcKey: 'darkmoon_sigil_hunt', slotGroup: 'weapon' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'main_hand')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.equipmentRows.map((row) => row.slot)), JSON.stringify(['main_hand']))
  assert.equal(page.data.gearEnhancementSheet.equipmentRows[0].typeSummary, '美化')
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options[0].label, '暗月徽记：狩猎')

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'main_hand', type: 'embellishment', id: 'seed-embellishment-darkmoon-sigil-hunt-rank-2' } }
  })
  pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.data.enhancementBySlot.main_hand.embellishment, 'darkmoon_sigil_hunt')
})

test('gear enhancement sheet filters off-hand embellishments by selected item type', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  const offHandOptions = [
    {
      id: 'seed-embellishment-darkmoon-sigil-hunt-rank-2',
      label: '暗月徽记：狩猎',
      displayLabel: '暗月徽记：狩猎',
      displayKind: 'name',
      displayStatus: 'verified',
      status: 'verified',
      slotGroup: 'weapon_offhand',
      simcOptions: { embellishment: 'darkmoon_sigil_hunt' },
      payload: { qualityRank: 2, simcKey: 'darkmoon_sigil_hunt', slotGroup: 'weapon_offhand' }
    },
    {
      id: 'seed-embellishment-arcanoweave-lining-rank-2',
      label: '奥纹内衬',
      displayLabel: '奥纹内衬',
      displayKind: 'name',
      displayStatus: 'verified',
      status: 'verified',
      slotGroup: 'armor',
      simcOptions: { embellishment: 'arcanoweave_lining' },
      payload: { qualityRank: 2, simcKey: 'arcanoweave_lining', slotGroup: 'armor' }
    },
    {
      id: 'seed-embellishment-devouring-banding-rank-2',
      label: '吞噬绑带',
      displayLabel: '吞噬绑带',
      displayKind: 'name',
      displayStatus: 'verified',
      status: 'verified',
      slotGroup: 'weapon_armor',
      simcOptions: { embellishment: 'devouring_banding' },
      payload: { qualityRank: 2, simcKey: 'devouring_banding', slotGroup: 'weapon_armor' }
    },
    {
      id: 'seed-embellishment-blessed-pango-charm-rank-2',
      label: '圣佑穿山甲护符',
      displayLabel: '圣佑穿山甲护符',
      displayKind: 'name',
      displayStatus: 'verified',
      status: 'verified',
      slotGroup: 'equipment',
      simcOptions: { embellishment: 'blessed_pango_charm' },
      payload: { qualityRank: 2, simcKey: 'blessed_pango_charm', slotGroup: 'equipment' }
    }
  ]
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'off_hand',
        simcSlot: 'off_hand',
        label: 'off_hand',
        items: [],
        embellishmentOptions: offHandOptions
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      selectedGearBySlot: {
        ...selection,
        off_hand: {
          ...selection.off_hand,
          displayName: '破法者的责难',
          sourceType: 'crafted',
          variantSource: 'crafted',
          weaponType: 'Shield',
          armorType: 'Shield',
          modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
        }
      },
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)
  const shieldLabels = Array.from(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options, (option) => option.label)
  assert.deepEqual(shieldLabels, ['奥纹内衬', '吞噬绑带', '圣佑穿山甲护符'])

  page.data.selectedGearBySlot.off_hand = {
    ...page.data.selectedGearBySlot.off_hand,
    displayName: '奥术灯笼',
    weaponType: 'Held In Off-hand',
    armorType: 'Miscellaneous'
  }
  pageConfig.openGearEnhancementSheet.call(page)
  const heldOffhandLabels = Array.from(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options, (option) => option.label)
  assert.deepEqual(heldOffhandLabels, ['暗月徽记：狩猎', '吞噬绑带', '圣佑穿山甲护符'])
})

test('gear enhancement sheet filters off-hand enchants by item type and hides class-only enchants', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  const enchantOptions = [
    {
      id: 'observed-enchant-tideguard',
      label: '唤潮者的护卫',
      displayLabel: '唤潮者的护卫',
      displayKind: 'name',
      displayStatus: 'verified',
      status: 'verified',
      simcOptions: { enchant_id: '7528' },
      payload: {
        configCategory: 'class_only_precombat',
        exclusionReason: 'Restoration Shaman class-only combat preparation',
        displayStatus: 'verified',
        evidenceSource: 'wago_db2_spell_item_enchantment'
      }
    },
    {
      id: 'observed-enchant-rondorei',
      label: '朗多雷之锐',
      displayLabel: '朗多雷之锐',
      displayKind: 'name',
      displayStatus: 'verified',
      status: 'verified',
      simcOptions: { enchant_id: '8039' },
      payload: { displayStatus: 'verified', evidenceSource: 'wago_db2_spell_item_enchantment' }
    }
  ]
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'off_hand',
        simcSlot: 'off_hand',
        label: 'off_hand',
        items: [],
        enchantOptions
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'restoration' },
      selectedGearBySlot: {
        ...selection,
        off_hand: {
          ...selection.off_hand,
          displayName: '艾林哈籁灯笼',
          weaponType: 'Held In Off-hand',
          armorType: 'Miscellaneous',
          modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
        }
      },
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows.length, 0)
  assert.doesNotMatch(JSON.stringify(page.data.gearEnhancementSheet), /唤潮者的护卫|朗多雷之锐/)

  page.data.selectedGearBySlot.off_hand = {
    ...page.data.selectedGearBySlot.off_hand,
    displayName: '副手斧',
    weaponType: 'One-Handed Axe',
    armorType: ''
  }
  pageConfig.openGearEnhancementSheet.call(page)
  const offhandWeaponLabels = Array.from(page.data.gearEnhancementSheet.activeEnchantRows[0].options, (option) => option.label)
  assert.deepEqual(offhandWeaponLabels, ['朗多雷之锐'])
})

test('gear enhancement sheet warns death knights that ordinary weapon enchants override runeforge', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const selection = {
    main_hand: {
      slot: 'main_hand',
      simcSlot: 'main_hand',
      itemId: '249277',
      id: '249277',
      displayName: "Bellamy's Final Judgement",
      weaponType: 'Two-Handed Sword',
      ilevel: 289,
      bonus_id: '13654',
      simcReady: true,
      modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
    }
  }
  const gearPayload = {
    classKey: 'deathknight',
    specKey: 'unholy',
    slots: [{ slot: 'main_hand', simcSlot: 'main_hand', label: 'main_hand' }],
    replacementCandidates: [
      {
        slot: 'main_hand',
        simcSlot: 'main_hand',
        label: 'main_hand',
        items: [],
        enchantOptions: [
          {
            id: 'ordinary-main-hand-enchant',
            label: 'Ordinary Weapon Enchant',
            displayLabel: 'Ordinary Weapon Enchant',
            displayKind: 'name',
            displayStatus: 'verified',
            status: 'verified',
            simcOptions: { enchant_id: '8039' },
            payload: { displayStatus: 'verified', evidenceSource: 'wago_db2_spell_item_enchantment' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'deathknight', websimSpecKey: 'unholy' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows.length, 0)
  assert.match(JSON.stringify(page.data.gearEnhancementSheet.warnings), /DK runeforge/)
})

test('gear enhancement confirm prunes stale off-hand weapon enchant on held offhand', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'off_hand',
        simcSlot: 'off_hand',
        label: 'off_hand',
        items: [],
        enchantOptions: [
          {
            id: 'observed-enchant-rondorei',
            label: '朗多雷之锐',
            displayLabel: '朗多雷之锐',
            displayKind: 'name',
            displayStatus: 'verified',
            status: 'verified',
            simcOptions: { enchant_id: '8039' },
            payload: { displayStatus: 'verified', evidenceSource: 'wago_db2_spell_item_enchantment' }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'restoration' },
      selectedGearBySlot: {
        ...selection,
        off_hand: {
          ...selection.off_hand,
          displayName: '艾林哈籁灯笼',
          weaponType: 'Held In Off-hand',
          armorType: 'Miscellaneous',
          modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
        }
      },
      enhancementBySlot: { off_hand: { enchantOptionId: 'observed-enchant-rondorei', enchant_id: '8039' } },
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(Object.keys(page.data.enhancementBySlot).length, 0)
})

test('gear enhancement sheet allows only one primary stat gem across jewelry slots', () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.neck = {
    ...selection.neck,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  const primaryGemMetadata = {
    qualityRank: 2,
    uniqueGroup: 'primary_stat_gem',
    uniqueLimit: 1
  }
  const gearPayload = {
    slots,
    replacementCandidates: [
      {
        slot: 'neck',
        simcSlot: 'neck',
        label: 'neck',
        items: [],
        socketOptions: [
          {
            id: 'gem-primary-neck',
            displayLabel: '+32主属性',
            displayKind: 'stat',
            displayStatus: 'verified',
            evidenceSource: 'battle_net_item_metadata',
            status: 'verified',
            simcOptions: { gem_id: '240983' },
            payload: primaryGemMetadata
          }
        ]
      },
      {
        slot: 'finger1',
        simcSlot: 'finger1',
        label: 'finger1',
        items: [],
        socketOptions: [
          {
            id: 'gem-primary-ring',
            displayLabel: '+23主属性',
            displayKind: 'stat',
            displayStatus: 'verified',
            evidenceSource: 'battle_net_item_metadata',
            status: 'verified',
            simcOptions: { gem_id: '240967' },
            payload: primaryGemMetadata
          },
          {
            id: 'gem-secondary-ring',
            displayLabel: '+17急速',
            displayKind: 'stat',
            displayStatus: 'verified',
            evidenceSource: 'battle_net_item_metadata',
            status: 'verified',
            simcOptions: { gem_id: '240888' },
            payload: { qualityRank: 2 }
          }
        ]
      }
    ],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'neck', type: 'gem', id: 'gem-primary-neck' } }
  })

  const ringGemOptions = page.data.gearEnhancementSheet.gemRows.find((row) => row.slot === 'finger1').options
  assert.equal(ringGemOptions.find((option) => option.id === 'gem-primary-ring').disabled, true)
  assert.equal(ringGemOptions.find((option) => option.id === 'gem-secondary-ring').disabled, false)

  page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1 = {
    socketOptionId: 'gem-primary-ring',
    gem_id: '240967'
  }
  pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.data.enhancementBySlot.finger1, undefined)
  assert.match(toasts.at(-1).title, /主属性宝石已超过上限 2\/1/)
  assert.ok(page.data.gearEnhancementSheet.blockers.includes('主属性宝石已超过上限 2/1'))
})

test('gear slot enhancement badges ignore stale incompatible enhancement state', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.neck = {
    ...selection.neck,
    modCapabilities: { hasSocket: false, canEnchant: false, canEmbellish: false }
  }
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: false, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    slots,
    replacementCandidates: [],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        neck: {
          socketOptionId: 'stale-gem',
          gem_id: '240888'
        },
        finger1: {
          enchantOptionId: 'stale-enchant',
          enchant_id: '7967'
        }
      }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '0/0')
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant').value, '0/0')
  assert.equal(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'neck').enhancementBadgeLabels), JSON.stringify([]))
  assert.equal(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'finger1').enhancementBadgeLabels), JSON.stringify([]))
})

test('gear slot enhancement badges show existing item embellishments counted by the attribute panel', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.back = {
    ...selection.back,
    displayName: '信徒的流丝罩袍',
    embellishment: 'arcanoweave_lining',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
  }
  selection.wrist = {
    ...selection.wrist,
    displayName: '破法者的护腕',
    embellishment: 'arcanoweave_lining',
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: true }
  }
  const gearPayload = {
    classKey: 'deathknight',
    specKey: 'blood',
    slots,
    replacementCandidates: [],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'deathknight', websimSpecKey: 'blood' },
      selectedGearBySlot: selection,
      enhancementBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'embellishment').value, '2/2')
  assert.equal(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'back').enhancementBadgeLabels), JSON.stringify(['美化']))
  assert.equal(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'wrist').enhancementBadgeLabels), JSON.stringify(['美化']))
  assert.equal(JSON.stringify(page.data.gearSlotRows.find((row) => row.slot === 'chest').enhancementBadgeLabels), JSON.stringify([]))
})

test('gear community templates derive readable names from class spec hero and source', async () => {
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot, items: [] })),
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false },
        communityTemplates: [{
          id: 'rio-observed',
          classLabel: '法师',
          specLabel: '冰霜',
          name: 'Raider.IO 观测装备 · 法师冰霜',
          sourceKey: 'observed_profile',
          sourceName: 'Raider.IO observed gear',
          status: 'partial',
          readySlotCount: 6,
          missingSlots: canonicalGearSlots.slice(6),
          canApplyGear: true,
          gearItems: Object.values(completeGearSelection(canonicalGearSlots.slice(0, 6)))
        }],
        baselineTemplates: [{
          id: 'simc-preset',
          classKey: 'mage',
          specKey: 'frost',
          name: 'MID1_Mage_Frost_Spellslinger',
          sourceKey: 'simc_preset',
          sourceName: 'SimC preset',
          status: 'complete',
          readySlotCount: 16,
          missingSlots: [],
          canApplyGear: true,
          gearItems: Object.values(completeGearSelection())
        }],
        communityTemplateSync: {
          sourceStatus: 'partial',
          sources: {},
          templates: { total: 2, verified: 1, partial: 1, blocked: 0 }
        }
      }
    })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(page.data.activeGearCommunityTemplates.length, 2)
  assert.equal(page.data.activeGearCommunityTemplates[0].displayName, '法师-冰霜 · Raider.IO 观测')
  assert.equal(page.data.activeGearCommunityTemplates[0].displaySourceName, 'Raider.IO 观测')
  assert.equal(page.data.activeGearCommunityTemplates[1].displayName, '法师-冰霜-法术投射者 · SimC 预设')
  assert.equal(page.data.activeGearCommunityTemplates[1].displaySourceName, 'SimC 预设')
})

test('late detail response preserves community templates from the full gear payload cache', async () => {
  const selectedDetail = {
    id: '法师-奥术',
    className: '法师',
    specName: '奥术',
    details: {
      talents: { coreTalents: [], importCode: '' },
      gear: {}
    }
  }
  const gearPayload = {
    classKey: 'mage',
    specKey: 'arcane',
    maxLevel: 90,
    slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
    replacementCandidates: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot, items: [] })),
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [{
      id: 'active-observed-template',
      classKey: 'mage',
      specKey: 'arcane',
      sourceKey: 'raiderio_observed_profile',
      sourceName: 'Raider.IO observed gear',
      sourceStatus: 'synced',
      status: 'complete',
      readySlotCount: 16,
      missingSlots: [],
      canApplyGear: true,
      gearItems: Object.values(completeGearSelection(canonicalGearSlots.filter((slot) => slot !== 'off_hand')))
    }],
    baselineTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'synced',
      templates: { total: 1, verified: 1, partial: 0, blocked: 0 }
    }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestBuildsDetail: () => Promise.resolve({ payload: selectedDetail, fromFallback: false, error: '' })
  })
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: null,
      selectedSpec: { id: '法师-奥术', websimClassKey: 'mage', websimSpecKey: 'arcane' },
      activeQueryKey: 'gear',
      selectedGearBySlot: {},
      enhancementBySlot: {},
      gearPayload: { ...gearPayload, communityTemplates: [] },
      gearSlotRows: [],
      gearDataFallback: false,
      gearRequestError: '',
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadSelectedDetail.call(page, '法师-奥术')
  await new Promise((resolve) => setImmediate(resolve))
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(page.data.activeGearCommunityTemplates.length, 1)
  assert.equal(page.data.activeGearCommunityTemplates[0].id, 'active-observed-template')
  assert.equal(page.data.activeGearCommunityTemplates[0].canApplyGear, true)
})

test('gear load preserves matched SimC-ready candidate evidence before saving templates', async () => {
  const savedTemplates = []
  const selectedGear = completeGearSelection()
  selectedGear.waist = {
    slot: 'waist',
    simcSlot: 'waist',
    itemId: '244611',
    id: '244611',
    displayName: 'Crafted waist from equipped set',
    sourceType: 'crafted',
    bonus_id: '1808/8960/12214',
    simcReady: false,
    missingFields: ['ilevel']
  }
  const simcReadyWaist = {
    slot: 'waist',
    simcSlot: 'waist',
    itemId: '244611',
    id: '244611',
    name: 'world_tenders_barkclasp',
    displayName: 'World Tender waist from SimC preset',
    sourceType: 'simcPreset',
    bonus_id: '1808/8960/12214',
    simcReady: true,
    missingFields: []
  }
  const gearPayload = {
    classKey: 'shaman',
    specKey: 'elemental',
    maxLevel: 90,
    gearSchemaRevision: 'websim-gear-simulator-v1',
    slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
    replacementCandidates: canonicalGearSlots.map((slot) => ({
      slot,
      simcSlot: slot,
      label: slot,
      items: slot === 'waist' ? [simcReadyWaist] : []
    })),
    equippedSet: selectedGear,
    slotReadiness: {},
    readiness: { fullReady: true },
    communityTemplates: []
  }
  const pageConfig = loadBuildsDetailPageConfig({
    savedTemplates,
    requestWebsimGear: () => Promise.resolve({ payload: gearPayload, fromFallback: false, error: '' })
  })
  const page = {
    data: {
      selectedDetail: { className: '萨满祭司', specName: '元素', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { className: '萨满祭司', title: '元素', specName: '元素', websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false },
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, { selectedSpec: page.data.selectedSpec })
  await new Promise((resolve) => setImmediate(resolve))
  await confirmGearTemplateSave(pageConfig, page)

  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(snapshot.gearBySlot.waist.simcReady, true)
  assert.equal(snapshot.gearBySlot.waist.sourceType, 'simcPreset')
  assert.deepEqual(snapshot.gearBySlot.waist.missingFields || [], [])
  assert.equal(snapshot.gearBySlot.waist.name, 'world_tenders_barkclasp')
})

test('gear detail marks backend fallback and blocks empty community imports', async () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({
    toasts,
    requestWebsimGear: () => Promise.resolve({
      fromFallback: true,
      error: 'missing api base url',
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot, items: [] })),
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false },
        communityTemplates: [],
        communityTemplateSync: {
          sourceStatus: 'missing_credentials',
          sources: {},
          templates: { total: 0, verified: 0, partial: 0, blocked: 0 }
        },
        dataStatus: 'blocked'
      }
    })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))
  pageConfig.openGearCommunityTemplates.call(page)

  assert.equal(page.data.gearDataFallback, true)
  assert.equal(page.data.gearSlotRows.length, canonicalGearSlots.length)
  assert.match(page.data.gearDataWarningText, /未连接后端 API/)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
  assert.match(toasts.at(-1).title, /未连接后端 API/)
})

test('gear detail keeps enhancement available when successful gear payload has blocked season status', async () => {
  const toasts = []
  const selectedGear = completeGearSelection()
  selectedGear.finger1 = {
    ...selectedGear.finger1,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage',
    specKey: 'frost',
    dataStatus: 'blocked',
    slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
    replacementCandidates: canonicalGearSlots.map((slot) => ({
      slot,
      simcSlot: slot,
      label: slot,
      items: [],
      socketOptions: slot === 'finger1'
        ? [{
            id: 'quick-gem-rank-two',
            displayLabel: '+32主属性',
            displayStatus: 'verified',
            status: 'verified',
            simcOptions: { gem_id: '240983' },
            payload: { qualityRank: 2 }
          }]
        : []
    })),
    equippedSet: selectedGear,
    slotReadiness: {},
    readiness: { fullReady: true },
    communityTemplates: [],
    currentSeason: { dataStatus: 'blocked', errors: ['season health is degraded'] }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    toasts,
    requestWebsimGear: () => Promise.resolve({ payload: gearPayload, fromFallback: false, error: '' })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      enhancementBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearEnhancementSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))
  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearDataFallback, false)
  assert.equal(page.data.gearDataWarningText, '')
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options[0].label, '+32主属性')
  assert.equal(toasts.length, 0)
})

test('gear detail keeps heavy candidate payload out of setData while preserving slot sheet candidates', async () => {
  const heavyCandidate = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250060',
    id: '250060',
    displayName: '虚空粉碎者的面纱',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg',
    simcReady: true,
    source: '诸界吞噬者迪门修斯 - 法力熔炉：欧米伽',
    sources: Array.from({ length: 20 }, (_, index) => ({
      id: `source-${index}`,
      sourceType: index % 2 ? 'observed_profile' : 'raid',
      sourceLabel: `重型来源 ${index} ${'x'.repeat(120)}`
    })),
    socketOptions: Array.from({ length: 30 }, (_, index) => ({
      id: `socket-${index}`,
      name: `宝石 ${index} ${'y'.repeat(120)}`,
      simcOptions: { gem_id: String(240900 + index) },
      status: 'verified'
    })),
    variants: Array.from({ length: 8 }, (_, index) => ({
      key: `variant-${index}`,
      label: `变体 ${index}`,
      simcOptions: { bonus_id: String(12000 + index) }
    })),
    sourceRefs: Array.from({ length: 8 }, (_, index) => ({ id: `ref-${index}`, label: `引用 ${index}` })),
    observedProfileRefs: Array.from({ length: 8 }, (_, index) => ({ sourceName: `样本 ${index}` })),
    sourceReferences: Array.from({ length: 8 }, (_, index) => ({ id: `source-reference-${index}` })),
    rawItem: { payload: 'x'.repeat(2000) }
  }
  const gearPayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [heavyCandidate]
    }],
    equippedSet: { head: heavyCandidate },
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'partial',
      sources: {},
      templates: { total: 0, verified: 0, partial: 0, blocked: 0 }
    },
    catalogStatus: 'partial'
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({ payload: gearPayload, fromFallback: false, error: '' })
  })
  const setDataUpdates = []
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      setDataUpdates.push(update)
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  assert.ok(page.gearPayloadCache)
  assert.equal(page.gearPayloadCache.replacementCandidates[0].items[0].itemId, '250060')
  assert.equal(page.data.gearPayload.replacementCandidates, undefined)
  assert.equal(page.data.gearPayload.slotGroups, undefined)
  assert.equal(page.data.gearPayload.equippedSet, undefined)
  assert.equal(page.data.gearPayload.communityTemplates, undefined)
  assert.equal(page.data.selectedGearBySlot.head.sources, undefined)
  assert.equal(page.data.selectedGearBySlot.head.socketOptions, undefined)
  assert.equal(page.data.selectedGearBySlot.head.variants, undefined)
  assert.equal(page.data.selectedGearBySlot.head.sourceRefs, undefined)
  assert.equal(page.data.selectedGearBySlot.head.observedProfileRefs, undefined)
  assert.equal(page.data.selectedGearBySlot.head.sourceReferences, undefined)
  assert.equal(page.data.selectedGearBySlot.head.rawItem, undefined)
  assert.ok(setDataUpdates.every((update) => !update.gearPayload || !update.gearPayload.replacementCandidates))
  assert.ok(setDataUpdates.every((update) => !update.selectedGearBySlot || !update.selectedGearBySlot.head.sources))
  assert.ok(setDataUpdates.every((update) => !update.selectedGearBySlot || !update.selectedGearBySlot.head.variants))

  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].displayName, '虚空粉碎者的面纱')
  assert.equal(page.data.gearSlotSheet.candidates[0].sources, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].socketOptions, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].variants, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].sourceRefs, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].observedProfileRefs, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].sourceReferences, undefined)
  assert.equal(page.data.gearSlotSheet.candidates[0].rawItem, undefined)
  assert.equal(page.data.gearSlotSheet.activeCandidate.sources, undefined)
  assert.equal(page.data.gearSlotSheet.activeCandidate.variants, undefined)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.socketOptions, undefined)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.variants, undefined)
  assert.equal(page.data.gearSlotSheet.allCandidates, undefined)
  assert.equal(page.gearSlotCandidateCache.head[0].sources.length, 20)
  assert.equal(page.gearSlotCandidateCache.head[0].socketOptions.length, 30)
  assert.equal(page.gearSlotCandidateCache.head[0].variants.length, 8)
})

test('gear detail loads initial gear payload first and fetches slot detail on demand', async () => {
  const calls = []
  const initialCandidate = {
    slot: 'head',
    itemId: '250060',
    displayName: '虚空粉碎者的面纱',
    simcReady: true,
    detailMode: 'summary',
    slotDetailAvailable: true
  }
  const detailCandidate = {
    ...initialCandidate,
    detailMode: 'complete',
    sources: [{ sourceType: 'raid', label: '法力熔炉：欧米伽' }],
    variants: [{ id: 'variant-a' }],
    socketOptions: [{ id: 'socket-a', simcOptions: { gem_id: '213743' } }]
  }
  const basePayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      detailMode: 'partial',
      items: [initialCandidate]
    }],
    equippedSet: { head: initialCandidate },
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [],
    communityTemplateSync: { templates: { total: 0, verified: 0, partial: 0, blocked: 0 } },
    catalogStatus: 'partial',
    gearPayloadMode: 'initial'
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      if (params.mode === 'slot') {
        return Promise.resolve({
          payload: {
            ...basePayload,
            gearPayloadMode: 'slot',
            gearSlot: params.slot,
            replacementCandidates: [{
              slot: params.slot,
              simcSlot: params.slot,
              label: '头部',
              detailMode: 'complete',
              items: [detailCandidate]
            }]
          },
          fromFallback: false,
          error: ''
        })
      }
      return Promise.resolve({ payload: basePayload, fromFallback: false, error: '' })
    }
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, { selectedSpec: page.data.selectedSpec })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(calls[0].mode, 'initial')
  await pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(calls[1].mode, 'slot')
  assert.equal(calls[1].slot, 'head')
  assert.equal(page.gearPayloadCache.replacementCandidates[0].detailMode, 'complete')
  assert.equal(page.gearSlotCandidateCache.head[0].sources[0].label, '法力熔炉：欧米伽')
  assert.equal(page.gearSlotCandidateCache.head[0].variants[0].id, 'variant-a')
  assert.equal(page.data.gearSlotSheet.candidates[0].sources, undefined)
})

test('gear detail reuses in-flight initial gear request for the same selection', async () => {
  const calls = []
  let resolveInitial
  const initialRequest = new Promise((resolve) => {
    resolveInitial = resolve
  })
  const basePayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      detailMode: 'complete',
      items: [{
        slot: 'head',
        itemId: '250060',
        displayName: '虚空粉碎者的面纱',
        simcReady: true
      }]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [],
    communityTemplateSync: { templates: { total: 0, verified: 0, partial: 0, blocked: 0 } },
    catalogStatus: 'partial',
    gearPayloadMode: 'initial'
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      return initialRequest
    }
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      enhancementBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, { selectedSpec: page.data.selectedSpec })
  pageConfig.loadWebsimGearForSelection.call(page, { selectedSpec: page.data.selectedSpec })

  assert.equal(calls.filter((params) => params.mode === 'initial').length, 1)
  resolveInitial({ payload: basePayload, fromFallback: false, error: '' })
  await initialRequest
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(page.data.gearLoading, false)
  assert.equal(page.gearPayloadCache.classKey, 'mage')
})

test('gear detail reuses in-flight slot detail request for the same slot', async () => {
  const calls = []
  let resolveDetail
  const detailRequest = new Promise((resolve) => {
    resolveDetail = resolve
  })
  const initialCandidate = {
    slot: 'head',
    itemId: '250060',
    displayName: '虚空粉碎者的面纱',
    simcReady: true,
    detailMode: 'summary',
    slotDetailAvailable: true
  }
  const detailCandidate = {
    ...initialCandidate,
    detailMode: 'complete',
    sources: [{ sourceType: 'raid', label: '法力熔炉：欧米伽' }],
    variants: [{ id: 'variant-a' }]
  }
  const basePayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      detailMode: 'partial',
      items: [initialCandidate]
    }],
    equippedSet: { head: initialCandidate },
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [],
    communityTemplateSync: { templates: { total: 0, verified: 0, partial: 0, blocked: 0 } },
    catalogStatus: 'partial',
    gearPayloadMode: 'initial'
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      return detailRequest
    }
  })
  const page = {
    gearPayloadCache: basePayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost',
      gearPayload: basePayload,
      selectedGearBySlot: {},
      enhancementBySlot: {},
      gearSlotRows: [{ slot: 'head', simcSlot: 'head', label: '头部', itemId: '250060' }],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  const firstOpen = pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  const secondOpen = pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(calls.filter((params) => params.mode === 'slot' && params.slot === 'head').length, 1)
  resolveDetail({
    payload: {
      ...basePayload,
      gearPayloadMode: 'slot',
      gearSlot: 'head',
      replacementCandidates: [{
        slot: 'head',
        simcSlot: 'head',
        label: '头部',
        detailMode: 'complete',
        items: [detailCandidate]
      }]
    },
    fromFallback: false,
    error: ''
  })
  await Promise.all([firstOpen, secondOpen])

  assert.equal(page.gearPayloadCache.replacementCandidates[0].detailMode, 'complete')
  assert.equal(page.gearSlotCandidateCache.head[0].variants[0].id, 'variant-a')
})

test('gear enhancement sheet opens immediately and refreshes after selected slot details load', async () => {
  const calls = []
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.neck = {
    ...selection.neck,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false, socketCount: 1 }
  }
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false, socketCount: 1 }
  }
  selection.legs = {
    ...selection.legs,
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  selection.off_hand = {
    ...selection.off_hand,
    weaponType: 'Held In Off-hand',
    modCapabilities: { hasSocket: false, canEnchant: false, canEmbellish: true }
  }
  const initialPayload = {
    classKey: 'shaman',
    specKey: 'elemental',
    slots,
    gearPayloadMode: 'initial',
    replacementCandidates: [{
      slot: 'off_hand',
      simcSlot: 'off_hand',
      label: '副手',
      detailMode: 'partial',
      items: [selection.off_hand],
      embellishmentOptions: [{
        id: 'offhand-embellishment',
        label: '副手美化',
        status: 'verified',
        simcOptions: { embellishment: 'offhand_embellishment' },
        payload: { qualityRank: 2, slotGroup: 'weapon_offhand' }
      }]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const optionPayloadBySlot = {
    neck: {
      socketOptions: [{
        id: 'neck-gem',
        label: '项链宝石',
        status: 'verified',
        simcOptions: { gem_id: '240983' },
        payload: { qualityRank: 2 }
      }]
    },
    finger1: {
      socketOptions: [{
        id: 'ring-gem',
        label: '戒指宝石',
        status: 'verified',
        simcOptions: { gem_id: '240983' },
        payload: { qualityRank: 2 }
      }],
      enchantOptions: [{
        id: 'ring-enchant',
        label: '戒指附魔',
        status: 'verified',
        simcOptions: { enchant_id: '7334' },
        payload: { qualityRank: 2 }
      }]
    },
    legs: {
      enchantOptions: [{
        id: 'leg-armor-kit',
        label: '腿部护甲片',
        status: 'verified',
        simcOptions: { enchant_id: '8159' },
        payload: { qualityRank: 2 }
      }]
    }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      const slot = params.slot
      return Promise.resolve({
        payload: {
          ...initialPayload,
          gearPayloadMode: 'slot',
          gearSlot: slot,
          replacementCandidates: [{
            slot,
            simcSlot: slot,
            label: slot,
            detailMode: 'complete',
            items: [selection[slot]],
            ...(optionPayloadBySlot[slot] || {})
          }]
        },
        fromFallback: false,
        error: ''
      })
    }
  })
  const page = {
    gearPayloadCache: initialPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      gearSelectionKey: 'shaman:elemental',
      gearPayload: initialPayload,
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  const openResult = pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.embellishmentRows.map((row) => row.slot)), JSON.stringify(['off_hand']))

  await openResult
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(calls, [])
  for (const slot of ['finger1', 'legs', 'neck']) {
    await pageConfig.selectGearEnhancementSlot.call(page, {
      currentTarget: { dataset: { slot } }
    })
  }
  const fetchedSlots = calls.map((params) => params.slot).sort()
  assert.deepEqual(fetchedSlots, ['finger1', 'legs', 'neck'])
  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.gemRows.map((row) => row.slot).sort()), JSON.stringify(['finger1', 'neck']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.enchantRows.map((row) => row.slot)), JSON.stringify(['legs', 'finger1']))
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.embellishmentRows.map((row) => row.slot)), JSON.stringify(['off_hand']))
})

test('gear detail preserves initial slot candidates when slot detail request falls back', async () => {
  const calls = []
  const initialCandidate = {
    slot: 'head',
    itemId: '250060',
    displayName: '虚空粉碎者的面纱',
    simcReady: true,
    detailMode: 'summary',
    slotDetailAvailable: true
  }
  const basePayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      detailMode: 'partial',
      items: [initialCandidate]
    }],
    equippedSet: { head: initialCandidate },
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [],
    communityTemplateSync: { templates: { total: 0, verified: 0, partial: 0, blocked: 0 } },
    catalogStatus: 'partial',
    gearPayloadMode: 'initial'
  }
  const fallbackPayload = {
    ...basePayload,
    replacementCandidates: [{ slot: 'head', simcSlot: 'head', label: '头部', items: [] }],
    gearPayloadMode: 'slot',
    gearSlot: 'head',
    dataStatus: 'blocked'
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      if (params.mode === 'slot') {
        return Promise.resolve({ payload: fallbackPayload, fromFallback: true, error: 'request failed' })
      }
      return Promise.resolve({ payload: basePayload, fromFallback: false, error: '' })
    }
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotRows: [],
      gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, { selectedSpec: page.data.selectedSpec })
  await new Promise((resolve) => setImmediate(resolve))
  await pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(calls[1].mode, 'slot')
  assert.equal(page.gearPayloadCache.replacementCandidates[0].items.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].displayName, '虚空粉碎者的面纱')
})

test('gear detail keeps catalog health gaps out of the top summary', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true },
        catalogStatus: 'partial',
        catalogHealthSummary: {
          sourcePendingItemCount: 131,
          missingStatObservedVariantCount: 303,
          socketMissingMetadataCount: 39,
          partialVariantCount: 519,
          sourcePendingExamples: [
            {
              itemId: '250777',
              displayName: '缺来源披风',
              slots: ['back'],
              sourceTypes: ['observed_profile']
            }
          ],
          partialVariantExamples: [
            {
              itemId: '250888',
              slot: 'head',
              sourceType: 'raid',
              sourceLabel: 'Void Captain - Voidspire',
              variantId: 'loot-partial-250888-head',
              blockers: ['missing deterministic SimC variant preset']
            }
          ]
        }
      },
      selectedGearBySlot: completeGearSelection()
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  assert.equal(Object.hasOwn(page.data, 'gearTrustSummaryText'), false)
})

test('gear detail hides fallback insight while first gear payload is loading', () => {
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => new Promise(() => {})
  })
  const page = {
    data: {
      selectedDetail: {
        details: {
          talents: { coreTalents: [], importCode: '' },
          gear: {
            sourceName: 'Mythicstats + Wowhead',
            publishedAt: '2026-06-09',
            items: ['old fallback gear insight']
          }
        }
      },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSlotRows: [],
      gearSelectionKey: '',
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })

  assert.equal(page.data.gearLoading, true)
  assert.equal(page.data.gearInitialLoading, true)
})

test('gear slot rows keep selectable equipment rows out of card copy', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250060',
    id: '250060',
    displayName: '虚空粉碎者的面纱',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmage_j_01.jpg',
    ilevel: '289',
    bonus_id: '1808/13575',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [
        { ...item, source: 'MID1_Mage_Frost_Frostfire' },
        { ...item, source: 'MID1_Mage_Frost_Spellslinger' },
        { ...item, source: 'MID1_Mage_Frost_Frostfire_Copy' }
      ]
    }],
    equippedSet: { head: item },
    slotReadiness: { head: { status: 'verified', reason: '可写入 SimC profile' } },
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: { head: item }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(Object.hasOwn(page.data.gearSlotRows[0], 'candidateCount'), false)
  assert.equal(page.data.gearSlotRows[0].gameAsset.iconUrl, item.iconUrl)
  assert.equal(page.data.gearSlotSheet.candidates[0].gameAsset.iconUrl, item.iconUrl)
})

test('gear candidate detail treats observed profiles as evidence not drop source', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const observedOnly = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '249920',
    id: '249920',
    displayName: '至暗之夜的眼眸',
    simcReady: true,
    ilevel: 289,
    bonus_id: '13440/6652/13577/12699/12806',
    source: 'Raider.IO CN observed mage frost',
    observedProfileRefs: [
      { sourceName: 'Raider.IO CN profile gear', classKey: 'mage', specKey: 'frost', itemLevel: 289 }
    ],
    sources: [
      { sourceType: 'observed_profile', sourceLabel: 'Raider.IO CN observed mage frost' }
    ]
  }
  const officialWithObserved = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '251115',
    id: '251115',
    displayName: '分叉指环',
    simcReady: true,
    source: 'Raider.IO CN observed priest holy',
    sources: [
      { sourceType: 'observed_profile', sourceLabel: 'Raider.IO CN observed priest holy' },
      { sourceType: 'raid', sourceLabel: '无眠之心 - 法力熔炉：欧米伽' }
    ]
  }
  const gearPayload = {
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指' }],
    replacementCandidates: [{
      slot: 'finger1',
      simcSlot: 'finger1',
      label: '戒指',
      items: [observedOnly, officialWithObserved]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'finger1' } } })

  const firstSource = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '掉落来源')
  const secondSource = page.data.gearSlotSheet.candidates[1].detailRows.find((row) => row.label === '掉落来源')
  assert.equal(page.data.gearSlotSheet.candidates[0].source, '来源待补充')
  assert.equal(page.data.gearSlotSheet.candidates[0].statusLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.candidates[0].trustLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '来源待补')
  assert.match(page.data.gearSlotSheet.activeTrustText, /掉落来源待补充/)
  assert.equal(firstSource.value, '来源待补充')
  assert.equal(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => row.label === '实装观测'), false)
  assert.equal(secondSource.value, '无眠之心 - 法力熔炉：欧米伽')
})

test('gear slot rows enrich sparse equipped items from matching candidates', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const sparseEquipped = {
    slot: 'back',
    simcSlot: 'back',
    itemId: '258575',
    id: '258575',
    displayName: '刚鳞大氅',
    simcReady: true,
    ilevel: 289,
    bonus_id: '6652/13335',
    source: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire',
    sourceType: 'simc_preset',
    sources: [
      { sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire' }
    ],
    statDisplayStatus: 'pending_current_variant'
  }
  const enrichedCandidate = {
    ...sparseEquipped,
    source: '兰吉特 - 通天峰',
    sourceType: 'dungeon',
    sources: [
      { sourceType: 'dungeon', label: '兰吉特 - 通天峰' },
      { sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire' }
    ],
    statSummary: '力量/敏捷/智力 70；耐力 995；暴击 50；精通 42',
    statDisplayStatus: 'verified_variant'
  }
  const gearPayload = {
    slots: [{ slot: 'back', simcSlot: 'back', label: '背部' }],
    replacementCandidates: [{
      slot: 'back',
      simcSlot: 'back',
      label: '背部',
      items: [enrichedCandidate]
    }],
    equippedSet: { back: sparseEquipped },
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: { back: sparseEquipped }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const row = page.data.gearSlotRows[0]
  assert.equal(row.source, '兰吉特 - 通天峰')
  assert.equal(row.statusLabel, '已配置')
  assert.equal(row.trustLabel, '可保存')
  assert.doesNotMatch(row.reason, /来源待补/)
})

test('gear candidate detail shows handedness unique badges and filters primary stat copy', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const weapon = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '260204',
    id: '260204',
    displayName: '唯一巨剑',
    simcReady: true,
    ilevel: 289,
    primaryStatKey: 'strength',
    weaponType: 'Two-Handed Sword',
    handednessLabel: '双手',
    uniqueEquipped: true,
    uniqueEquippedLabel: '唯一',
    equipmentBadges: [
      { key: 'weapon_handedness', label: '双手' },
      { key: 'unique_equipped', label: '唯一' }
    ],
    statSummary: '力量 or 敏捷 333；耐力 555；智力 999；暴击 70'
  }
  const gearPayload = {
    classKey: 'warrior',
    specKey: 'fury',
    slots: [{ slot: 'main_hand', simcSlot: 'main_hand', label: '主手' }],
    replacementCandidates: [{
      slot: 'main_hand',
      simcSlot: 'main_hand',
      label: '主手',
      items: [weapon]
    }],
    equippedSet: { main_hand: weapon },
    slotReadiness: { main_hand: { status: 'verified', reason: '可写入 SimC profile' } },
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'warrior', websimSpecKey: 'fury' },
      gearPayload,
      selectedGearBySlot: { main_hand: weapon }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'main_hand' } } })

  assert.deepEqual(Array.from(page.data.gearSlotRows[0].equipmentBadgeLabels), ['双手', '唯一'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.candidates[0].equipmentBadgeLabels), ['双手', '唯一'])
  const detailRows = page.data.gearSlotSheet.candidates[0].detailRows
  assert.equal(detailRows.find((row) => row.label === '装备标签').value, '双手 / 唯一')
  assert.equal(detailRows.find((row) => row.label === '装备属性').value, '力量 333；耐力 555；暴击 70')
})

test('gear candidate detail separates SimulationCraft preset from drop source', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const simcPresetOnly = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '268283',
    id: '268283',
    displayName: '溃烂之花冠冕',
    simcReady: true,
    ilevel: 298,
    bonus_id: '6652/12667/13577/13335/13786',
    source: 'SimulationCraft preset: MID1_Rogue_Outlaw_Fatebound',
    sourceType: 'simc_preset',
    sources: [
      { sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Rogue_Outlaw_Fatebound' }
    ],
    statSummary: '敏捷 or 智力 124；耐力 1768'
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [simcPresetOnly]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.candidates[0].statusLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.candidates[0].trustLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '来源待补')
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.candidates[0].source, '来源待补充')
  const detailRows = page.data.gearSlotSheet.candidates[0].detailRows
  assert.equal(detailRows.find((row) => row.label === '掉落来源').value, '来源待补充')
  assert.equal(detailRows.some((row) => row.label === '配置来源'), false)
})

test('gear candidate detail shows crafted source even when compact candidate source type is a SimC preset', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const craftedPreset = {
    slot: 'off_hand',
    simcSlot: 'off_hand',
    itemId: '237850',
    id: '237850',
    displayName: '远行者的劈斧',
    simcReady: true,
    bonus_id: '8793/8960',
    crafted_stats: '40/32',
    source: '制造装备',
    sourceType: 'simcPreset',
    statSummary: '力量 124；耐力 1768'
  }
  const gearPayload = {
    slots: [{ slot: 'off_hand', simcSlot: 'off_hand', label: '副手' }],
    replacementCandidates: [{
      slot: 'off_hand',
      simcSlot: 'off_hand',
      label: '副手',
      items: [craftedPreset]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'off_hand' } } })

  const candidate = page.data.gearSlotSheet.candidates[0]
  const detailRows = candidate.detailRows
  assert.equal(candidate.source, '制造装备')
  assert.equal(detailRows.find((row) => row.label === '掉落来源').value, '制造装备')
})

test('gear slot sheet exposes source reference and blocker trust states', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const sourceReferenceItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250888',
    id: '250888',
    displayName: 'Guide Only Hood',
    sourceType: 'source_reference',
    source: '虚空粉碎者掉落',
    sources: [{ label: '虚空粉碎者掉落', sourceType: 'dungeon' }],
    stats: [
      { label: '智力', value: '1234' },
      { name: '急速', value: '567' }
    ],
    metadataStatus: 'source_reference',
    missingFields: ['deterministic SimC variant'],
    blockers: ['missing deterministic SimC variant preset'],
    simcReady: false
  }
  const blockedItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250999',
    id: '250999',
    displayName: 'Broken Hood',
    sourceType: 'raid',
    blockers: ["Trivial: Player 'websim_unholy' at slot hands has inconsistency between name 'item_249971' and 'relentless_riders_bonegrasps' for id 249971"],
    simcReady: false
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [sourceReferenceItem, blockedItem]
    }],
    equippedSet: {},
    slotReadiness: { head: { status: 'blocked', reason: 'missing item' } },
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (item) => item.key), ['all', 'dungeon', 'raid', 'tier_set', 'crafted'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (item) => item.label), ['全部', '大秘境', '团本', '套装', '制造业'])
  assert.equal(page.data.gearSlotSheet.filterKey, 'all')
  assert.equal(page.data.gearSlotSheet.candidates[0].statusClass, 'source-reference')
  assert.equal(page.data.gearSlotSheet.candidates[0].trustLabel, '来源参考')
  assert.match(page.data.gearSlotSheet.candidates[0].trustReason, /不可直接保存/)
  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '来源参考')
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少确定 SimC 变体/)

  pageConfig.toggleGearCandidateDetail.call(page, { currentTarget: { dataset: { index: 0 } } })

  assert.equal(page.data.gearSlotSheet.candidates[0].detailOpen, true)
  assert.equal(page.data.gearSlotSheet.candidates[1].detailOpen, false)
  assert.ok(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => row.label === '掉落来源' && row.value === '虚空粉碎者掉落'))
  assert.ok(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => row.label === '装备属性' && /智力 1234/.test(row.value) && /急速 567/.test(row.value)))
  assert.equal(page.data.gearSlotSheet.candidates[0].detailRows.some((row) => /物品 ID|SimC|缺失字段|阻断原因|变体|观测样本/.test(row.label)), false)

  pageConfig.selectGearCandidate.call(page, { currentTarget: { dataset: { index: 1 } } })

  assert.equal(page.data.gearSlotSheet.activeTrustLabel, '阻断')
  assert.match(page.data.gearSlotSheet.activeTrustText, /手套装备数据不一致：装备名称和物品 ID 对不上，请重新选择或保存手套。/)
  assert.doesNotMatch(page.data.gearSlotSheet.activeTrustText, /Trivial|websim_unholy|item_249971|inconsistency/)
})

test('gear candidate detail prefers stat summary without duplicating stat arrays', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'catalog',
    source: 'Catalog Dungeon',
    stats: [{ label: 'Intellect', value: 7 }],
    itemStats: [{ label: 'Intellect', value: 7 }],
    statSummary: 'Intellect 7; Haste 9',
    missingFields: ['ilevel'],
    simcReady: false
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
        replacementCandidates: [{ slot: 'head', simcSlot: 'head', label: 'Head', items: [item] }],
        equippedSet: {},
        slotReadiness: { head: { status: 'blocked', reason: 'missing item' } },
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.toggleGearCandidateDetail.call(page, { currentTarget: { dataset: { index: 0 } } })

  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => /Intellect|Haste/.test(row.value))
  assert.equal(attributes.value, 'Intellect 7; Haste 9')
})

test('gear candidate detail marks pending current variant stats instead of showing item level as attributes', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'back',
    simcSlot: 'back',
    itemId: '193712',
    id: '193712',
    displayName: '药渍披风',
    source: '茂林古树 - 艾杰斯亚学院',
    ilevel: 289,
    simcReady: true,
    statDisplayStatus: 'pending_current_variant'
  }
  const gearPayload = {
    slots: [{ slot: 'back', simcSlot: 'back', label: '披风' }],
    replacementCandidates: [{
      slot: 'back',
      simcSlot: 'back',
      label: '披风',
      items: [item]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'back' } } })

  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '装备属性')
  assert.equal(attributes.value, '属性待补充（装等 289）')
})

test('gear candidate detail explains simc item resolution failure for observed variants', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'neck',
    simcSlot: 'neck',
    itemId: '268291',
    id: '268291',
    displayName: '腐沼的孢子之心',
    ilevel: 298,
    simcReady: true,
    statDisplayStatus: 'pending_current_variant',
    simcStatStatus: 'failed',
    simcStatFailureKind: 'item_resolution',
    observedProfileRefs: [{ sourceName: 'Raider.IO', classKey: 'mage', specKey: 'frost' }]
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'neck', simcSlot: 'neck', label: '项链' }],
        replacementCandidates: [{ slot: 'neck', simcSlot: 'neck', label: '项链', items: [item] }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'neck' } } })

  const candidate = page.data.gearSlotSheet.candidates[0]
  assert.equal(candidate.statusLabel, '属性待补')
  assert.equal(candidate.trustLabel, '属性待补')
  assert.match(candidate.trustReason, /装备属性/)
  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '装备属性')
  assert.equal(attributes.value, '属性待补充（装等 298，SimC 物品解析失败）')
})

test('gear slot sheet blocks applying candidates that still need item level or simc options', async () => {
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  assert.match(wxml, /class="gear-apply-button" disabled="\{\{!gearSlotSheet\.canApplyCandidate\}\}"/)

  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const partialItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '251109',
    id: '251109',
    displayName: '断法暗影面具',
    sourceType: 'catalog',
    source: '瑟拉奈尔·日鞭 - 魔导师平台',
    sources: [{ label: '瑟拉奈尔·日鞭 - 魔导师平台', sourceType: 'dungeon' }],
    stats: [
      { label: '智力', value: 7 },
      { label: '精通', value: 9 }
    ],
    missingFields: ['ilevel', 'bonus_id/gem_id/enchant_id'],
    blockers: ['missing deterministic SimC variant preset'],
    variants: [{
      key: 'needs-variant',
      variantKey: 'needs-variant',
      difficultyLabel: '难度待补',
      itemLevel: 0,
      simcOptions: {},
      status: 'partial'
    }],
    defaultVariantKey: 'needs-variant',
    simcReady: false
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: '头部' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: '头部',
      items: [partialItem]
    }],
    equippedSet: {},
    slotReadiness: { head: { status: 'blocked', reason: 'missing item' } },
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      throw new Error('partial candidates must not refresh gear stats')
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少装等/)

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.equal(page.data.gearSlotSheet.visible, true)
  assert.match(toasts.at(-1).title, /缺少装等/)
})

test('gear slot sheet does not treat embellishment-only candidates as simc-ready', async () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const item = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260333',
    id: '260333',
    displayName: 'Only Embellished Cuffs',
    sourceType: 'crafted',
    source: '制造业',
    embellishment: 'dawnthread_lining',
    missingFields: ['ilevel', 'bonus_id/gem_id/enchant_id'],
    simcReady: false
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: '腕部' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: '腕部',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: { wrist: { status: 'blocked', reason: 'missing base SimC fields' } },
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      throw new Error('embellishment-only candidates must not refresh gear stats')
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.simcReady, false)
  assert.ok(page.data.gearSlotSheet.appliedCandidate.missingFields.includes('ilevel'))
  assert.ok(page.data.gearSlotSheet.appliedCandidate.missingFields.includes('bonus_id/gem_id/enchant_id'))

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.wrist, undefined)
  assert.equal(page.data.gearSlotSheet.visible, true)
  assert.match(toasts.at(-1).title, /缺少装等/)
})

test('gear slot sheet applies simc-ready candidates with simc options when item level is absent', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'off_hand',
    simcSlot: 'off_hand',
    itemId: '251175',
    id: '251175',
    displayName: '灵魂枯萎劈刀',
    source: '测试首领 - 测试副本',
    sources: [{ label: '测试首领 - 测试副本', sourceType: 'dungeon' }],
    bonus_id: '4786/12806',
    enchant_id: '8039',
    statSummary: '敏捷 62；耐力 884',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'off_hand', simcSlot: 'off_hand', label: '副手' }],
    replacementCandidates: [{
      slot: 'off_hand',
      simcSlot: 'off_hand',
      label: '副手',
      items: [item]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'off_hand' } } })

  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.off_hand.itemId, '251175')
  assert.equal(page.data.selectedGearBySlot.off_hand.ilevel, undefined)
  assert.equal(page.data.selectedGearBySlot.off_hand.bonus_id, '4786/12806')
})

test('gear slot sheet keeps candidates that differ only by embellishment', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260444',
    id: '260444',
    displayName: 'Crafted Cuffs',
    sourceType: 'crafted',
    ilevel: 289,
    bonus_id: '12345',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: '腕部' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: '腕部',
          items: [
            { ...baseItem, embellishment: 'dawnthread_lining' },
            { ...baseItem, embellishment: 'duskthread_lining' }
          ]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  assert.equal(page.data.gearSlotSheet.candidates.length, 2)
  assert.deepEqual(
    Array.from(page.data.gearSlotSheet.candidates, (candidate) => candidate.embellishment),
    ['dawnthread_lining', 'duskthread_lining']
  )
})

test('gear slot sheet marks built-in embellishments and apply syncs enhancement count', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const selectedGearBySlot = {
    waist: {
      slot: 'waist',
      simcSlot: 'waist',
      itemId: '260899',
      id: '260899',
      displayName: 'Plain Crafted Belt',
      sourceType: 'crafted',
      ilevel: 285,
      bonus_id: '8793',
      simcReady: true
    }
  }
  const builtInBelt = {
    slot: 'waist',
    simcSlot: 'waist',
    itemId: '260900',
    id: '260900',
    displayName: '世界照护者的树皮腰扣',
    sourceType: 'crafted',
    sources: [{ label: '制造装备', sourceType: 'crafted' }],
    ilevel: 285,
    bonus_id: '8793',
    hasBuiltInEmbellishment: true,
    builtInEmbellishment: 'built_in',
    builtInEmbellishmentLabel: '美化',
    embellishmentSource: 'built_in',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'waist', simcSlot: 'waist', label: '腰部' }],
    replacementCandidates: [{
      slot: 'waist',
      simcSlot: 'waist',
      label: '腰部',
      items: [builtInBelt],
      embellishmentOptions: [{
        id: 'embellishment-blue-silken-lining',
        label: '蓝色丝质内衬',
        displayLabel: '蓝色丝质内衬',
        displayStatus: 'verified',
        status: 'verified',
        simcOptions: { embellishment: 'blue_silken_lining' },
        payload: { qualityRank: 2 }
      }]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { id: 'mage-frost', websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot,
      enhancementBySlot: { waist: { embellishment: 'blue_silken_lining' } },
      gearSlotRows: [],
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  assert.match(wxml, /gear-embellishment-badge/)
  assert.match(wxml, /item\.embellishmentBadgeLabel/)

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'waist' } } })

  assert.ok(page.data.gearSlotSheet.filters.find((filter) => filter.key === 'crafted').count >= 1)
  const builtInIndex = page.data.gearSlotSheet.candidates.findIndex((candidate) => candidate.itemId === '260900')
  assert.notEqual(builtInIndex, -1)
  assert.equal(page.data.gearSlotSheet.candidates[builtInIndex].embellishmentBadgeLabel, '美化')
  pageConfig.selectGearCandidate.call(page, { currentTarget: { dataset: { index: builtInIndex } } })
  assert.equal(page.data.gearSlotSheet.activeCandidate.itemId, '260900')

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.waist.itemId, '260900')
  assert.equal(JSON.stringify(page.data.enhancementBySlot), '{}')
  assert.equal(page.data.gearSlotRows[0].embellishmentBadgeLabel, '美化')
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'embellishment').value, '1/2')
})

test('gear slot sheet source filters include tier set and crafted buckets while omitting recommendations', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const dungeonItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'dungeon',
    sources: [{ label: 'Maisara Caverns', sourceType: 'dungeon' }],
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const tierSetItem = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250778',
    id: '250778',
    displayName: 'Catalyst Hood',
    sourceType: 'tier_set',
    sources: [{ label: '套装转化', sourceType: 'tier_set' }],
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
      items: [dungeonItem, tierSetItem]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (filter) => filter.key), ['all', 'dungeon', 'raid', 'tier_set', 'crafted'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.filters, (filter) => filter.label), ['全部', '大秘境', '团本', '套装', '制造业'])
  assert.equal(page.data.gearSlotSheet.filters.find((filter) => filter.key === 'crafted').count, 0)
  assert.equal(page.data.gearSlotSheet.filters.some((filter) => /推荐/.test(filter.label)), false)
  assert.equal(page.data.gearSlotSheet.candidates.length, 2)

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'raid' } } })

  assert.equal(page.data.gearSlotSheet.filterKey, 'raid')
  assert.equal(page.data.gearSlotSheet.candidates.length, 0)
  assert.equal(page.data.gearSlotSheet.emptyText, '该来源暂无候选装备')

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'tier_set' } } })

  assert.equal(page.data.gearSlotSheet.filterKey, 'tier_set')
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].displayName, 'Catalyst Hood')

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'crafted' } } })

  assert.equal(page.data.gearSlotSheet.filterKey, 'crafted')
  assert.equal(page.data.gearSlotSheet.candidates.length, 0)
  assert.equal(page.data.gearSlotSheet.emptyText, '该来源暂无候选装备')
})

test('gear candidate detail toggle does not change the selected candidate', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
      items: [
        {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250101',
          id: '250101',
          displayName: 'Selected Hood',
          sourceType: 'dungeon',
          ilevel: 707,
          bonus_id: '12345',
          simcReady: true
        },
        {
          slot: 'head',
          simcSlot: 'head',
          itemId: '250202',
          id: '250202',
          displayName: 'Inspect Only Hood',
          sourceType: 'raid',
          ilevel: 710,
          bonus_id: '67890',
          simcReady: true
        }
      ]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {}
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  assert.equal(page.data.gearSlotSheet.selectedCandidateIndex, 0)
  assert.equal(page.data.gearSlotSheet.activeCandidate.itemId, '250101')

  pageConfig.toggleGearCandidateDetail.call(page, { currentTarget: { dataset: { index: 1 } } })

  assert.equal(page.data.gearSlotSheet.selectedCandidateIndex, 0)
  assert.equal(page.data.gearSlotSheet.activeCandidate.itemId, '250101')
  assert.equal(page.data.gearSlotSheet.candidates[0].detailOpen, false)
  assert.equal(page.data.gearSlotSheet.candidates[1].detailOpen, true)
})

test('gear candidate rows render only a compact detail action on the right side', () => {
  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  assert.match(wxml, /class="gear-candidate-action"/)
  assert.match(wxml, /class="gear-candidate-detail-button"/)
  assert.doesNotMatch(wxml, /item\.shortStatusLabel/)
  assert.doesNotMatch(wxml, /item\.issueSummary/)
  assert.doesNotMatch(wxml, /class="gear-candidate-meta"/)
})

test('gear slot sheet keeps socket options out of equipment detail controls', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'neck',
    simcSlot: 'neck',
    itemId: '268291',
    id: '268291',
    displayName: '悲恸吊坠',
    sourceType: 'dungeon',
    ilevel: 289,
    bonus_id: '67890',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'neck', simcSlot: 'neck', label: '颈部' }],
        replacementCandidates: [{
          slot: 'neck',
          simcSlot: 'neck',
          label: '颈部',
          socketOptions: [{
            id: 'socket-gem-213743',
            name: '迅捷宝石',
            simcOptions: { gem_id: '213743' },
            status: 'verified'
          }],
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'neck' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.socketOptions), [])
  assert.equal(page.data.gearSlotSheet.activeCandidate.socketOptions, undefined)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
})

test('gear slot sheet keeps enchant options out of equipment detail controls', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '249293',
    id: '249293',
    displayName: '仪式妖术之刃',
    sourceType: 'raid',
    ilevel: 298,
    bonus_id: '13786',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'main_hand', simcSlot: 'main_hand', label: '主手' }],
        replacementCandidates: [{
          slot: 'main_hand',
          simcSlot: 'main_hand',
          label: '主手',
          enchantOptions: [{
            id: 'enchant-3368',
            name: '武器附魔',
            simcOptions: { enchant_id: '3368' },
            status: 'verified'
          }],
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'main_hand' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.enchantOptions), [])
  assert.equal(page.data.gearSlotSheet.activeCandidate.enchantOptions, undefined)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
})

test('gear slot sheet sorts upgrade tracks as champion hero myth and void ascension', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250777',
    id: '250777',
    displayName: 'Catalog Hood',
    sourceType: 'raid',
    sources: [{ label: 'Vault Mage - Arcane Vault', sourceType: 'raid' }],
    modCapabilities: { hasSocket: true, canEnchant: true },
    defaultVariantKey: 'champion-263',
    variants: [
      {
        key: 'myth-289',
        label: 'Myth 289',
        difficultyLabel: '史诗',
        itemLevel: 289,
        simcOptions: { bonus_id: '67890' },
        status: 'verified'
      },
      {
        key: 'void-298',
        label: 'Void 298',
        difficultyLabel: '史诗',
        itemLevel: 298,
        simcOptions: { bonus_id: '13786' },
        status: 'verified'
      },
      {
        key: 'champion-263',
        label: 'Champion 263',
        difficultyLabel: '大秘境',
        itemLevel: 263,
        simcOptions: { bonus_id: '12345' },
        status: 'verified'
      },
      {
        key: 'hero-276',
        label: 'Hero 276',
        difficultyLabel: '英雄',
        itemLevel: 276,
        simcOptions: { bonus_id: '23456' },
        status: 'verified'
      },
      {
        key: 'needs-variant',
        label: '难度 / 装等待补',
        difficultyKey: 'needs-variant',
        itemLevel: 0,
        status: 'partial',
        blockers: ['missing deterministic SimC variant preset']
      }
    ],
    simcReady: true
  }
  const gearPayload = {
    slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
    replacementCandidates: [{
      slot: 'head',
      simcSlot: 'head',
      label: 'Head',
      socketOptions: [{
        id: 'socket-gem-240983',
        name: 'Quick Gem',
        simcOptions: { gem_id: '240983', gem_ilevel: '710' },
        status: 'verified'
      }],
      enchantOptions: [{
        id: 'enchant-8017',
        name: 'Radiant Enchant',
        simcOptions: { enchant_id: '8017' },
        status: 'verified'
      }],
      items: [item]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: {},
    statSnapshot: { statStatus: 'blocked', blockers: [] }
  }
  let refreshCalls = 0
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      refreshCalls += 1
      return Promise.resolve()
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.displayLabel), ['勇士', '英雄', '神话', '虚空晋升'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.levelLabel), ['装等 263', '装等 276', '装等 289', '装等 298'])
  assert.equal(page.data.gearSlotSheet.variantOptions.some((variant) => variant.displayLabel === '难度待补'), false)
  assert.deepEqual(Array.from(page.data.gearSlotSheet.socketOptions), [])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.enchantOptions), [])
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'myth-289' } } })
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.gem_id, undefined)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.enchant_id, undefined)
  await pageConfig.applyGearCandidate.call(page)

  const selected = page.data.selectedGearBySlot.head
  assert.equal(selected.variantKey, 'myth-289')
  assert.equal(selected.ilevel, 289)
  assert.equal(selected.bonus_id, '67890')
  assert.equal(selected.gem_id, undefined)
  assert.equal(selected.gem_ilevel, undefined)
  assert.equal(selected.enchant_id, undefined)
  assert.equal(page.data.gearSlotSheet.visible, false)
  assert.equal(refreshCalls, 0)
})

test('gear slot sheet only renders DB-provided item level tracks for catalog candidates', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'shoulder',
    simcSlot: 'shoulder',
    itemId: '250888',
    id: '250888',
    displayName: 'Duplicate Shoulder',
    sourceType: 'raid',
    sources: [{ label: 'Void Captain - Voidspire', sourceType: 'raid' }],
    defaultVariantKey: 'observed-289-current',
    variants: [
      {
        key: 'observed-289-current',
        label: 'Observed 289',
        difficultyLabel: '团本',
        difficultyKey: 'raid',
        itemLevel: 289,
        simcOptions: { bonus_id: '24680' },
        status: 'verified'
      }
    ],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'shoulder', simcSlot: 'shoulder', label: 'Shoulder' }],
        replacementCandidates: [{
          slot: 'shoulder',
          simcSlot: 'shoulder',
          label: 'Shoulder',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'shoulder' } } })

  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.displayLabel), ['神话'])
  assert.deepEqual(Array.from(page.data.gearSlotSheet.variantOptions, (variant) => variant.levelLabel), ['装等 289'])
  assert.equal(page.data.gearSlotSheet.variantOptions[0].key, 'observed-289-current')
})

test('gear slot sheet updates visible item level and attributes when variant changes', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '250999',
    id: '250999',
    displayName: 'Variant Hood',
    sourceType: 'raid',
    sources: [{ label: 'Void Captain - Voidspire', sourceType: 'raid' }],
    defaultVariantKey: 'champion-263',
    statSummary: '智力 999；耐力 999',
    itemStats: [
      { key: 'intellect', label: '智力', value: 999 },
      { key: 'stamina', label: '耐力', value: 999 }
    ],
    statDisplayStatus: 'verified_variant',
    variants: [
      {
        key: 'champion-263',
        label: 'Champion 263',
        difficultyKey: 'champion',
        itemLevel: 263,
        simcOptions: { ilevel: '263' },
        statSummary: '智力 100；耐力 200',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      },
      {
        key: 'hero-276',
        label: 'Hero 276',
        difficultyKey: 'hero',
        itemLevel: 276,
        simcOptions: { ilevel: '276' },
        statSummary: '智力 120；耐力 240',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      },
      {
        key: 'myth-289',
        label: 'Myth 289',
        difficultyKey: 'myth',
        itemLevel: 289,
        simcOptions: { ilevel: '289' },
        statSummary: '智力 140；耐力 280',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      }
    ],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
        replacementCandidates: [{
          slot: 'head',
          simcSlot: 'head',
          label: 'Head',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'hero-276' } } })

  const selectedCandidate = page.data.gearSlotSheet.candidates[0]
  assert.equal(selectedCandidate.ilevel, 276)
  assert.equal(selectedCandidate.statSummary, '智力 120；耐力 240')
  assert.ok(selectedCandidate.detailRows.some((row) => row.label === '装备属性' && row.value === '智力 120；耐力 240'))
  assert.equal(selectedCandidate.detailRows.some((row) => /智力 999/.test(row.value)), false)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.ilevel, 276)
})

test('gear slot sheet counts crafted filter when crafted candidates exist', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const craftedItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260200',
    id: '260200',
    displayName: 'Crafted Bracers',
    sourceType: 'crafted',
    sources: [{ label: '制造装备', sourceType: 'crafted' }],
    variants: [{
      key: 'crafted-myth-285',
      label: '神话 285',
      difficultyKey: 'myth',
      itemLevel: 285,
      simcOptions: { ilevel: '285', bonus_id: '8793/8960' },
      craftedStatOptions: [{
        key: 'haste_mastery',
        label: '急速 + 精通',
        simcOptions: { crafted_stats: '40/32' },
        status: 'verified',
        statSummary: '智力 285；急速 40；精通 32'
      }],
      status: 'verified'
    }],
    simcReady: true
  }
  const dungeonItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260201',
    id: '260201',
    displayName: 'Dungeon Bracers',
    sourceType: 'dungeon',
    sources: [{ label: '测试副本', sourceType: 'dungeon' }],
    variants: [{ key: 'myth-289', difficultyKey: 'myth', itemLevel: 289, simcOptions: { ilevel: '289', bonus_id: '12345' }, status: 'verified' }],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: 'Wrist' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: 'Wrist',
          items: [craftedItem, dungeonItem]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  const craftedFilter = page.data.gearSlotSheet.filters.find((filter) => filter.key === 'crafted')
  assert.equal(craftedFilter.label, '制造业')
  assert.equal(craftedFilter.count, 1)

  pageConfig.setGearCandidateFilter.call(page, { currentTarget: { dataset: { key: 'dungeon' } } })
  assert.equal(page.data.gearSlotSheet.filters.some((filter) => filter.key === 'crafted'), true)
  assert.equal(page.data.gearSlotSheet.candidates.length, 1)
  assert.equal(page.data.gearSlotSheet.candidates[0].sourceType, 'dungeon')
})

test('crafted gear requires selecting a stat option before apply and serializes crafted_stats', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  assert.equal(typeof pageConfig.selectCraftedStatOption, 'function')
  const craftedItem = {
    slot: 'wrist',
    simcSlot: 'wrist',
    itemId: '260200',
    id: '260200',
    displayName: 'Crafted Bracers',
    sourceType: 'crafted',
    sources: [{ label: '制造装备', sourceType: 'crafted' }],
    variants: [{
      key: 'crafted-myth-285',
      label: '神话 285',
      difficultyKey: 'myth',
      itemLevel: 285,
      simcOptions: { ilevel: '285', bonus_id: '8793/8960' },
      craftedStatOptions: [
        {
          key: 'haste_mastery',
          label: '急速 + 精通',
          simcOptions: { crafted_stats: '40/32' },
          status: 'verified',
          statSummary: '智力 285；急速 40；精通 32',
          statDisplayStatus: 'verified_variant'
        },
        {
          key: 'crit_vers',
          label: '暴击 + 全能',
          simcOptions: { crafted_stats: '36/36' },
          status: 'partial',
          blockers: ['SimC crafted item probe missing item stats']
        }
      ],
      status: 'verified'
    }],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { id: '法师-冰霜', title: '冰霜' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'wrist', simcSlot: 'wrist', label: 'Wrist' }],
        replacementCandidates: [{
          slot: 'wrist',
          simcSlot: 'wrist',
          label: 'Wrist',
          items: [craftedItem]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: false },
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })

  assert.equal(page.data.gearSlotSheet.craftedStatOptions.length, 2)
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.match(page.data.gearSlotSheet.activeTrustText, /缺少制造属性搭配/)

  pageConfig.selectCraftedStatOption.call(page, { currentTarget: { dataset: { key: 'crit_vers' } } })
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, false)
  assert.match(page.data.gearSlotSheet.activeTrustText, /SimC/)

  pageConfig.selectCraftedStatOption.call(page, { currentTarget: { dataset: { key: 'haste_mastery' } } })
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.crafted_stats, '40/32')
  assert.equal(page.data.gearSlotSheet.appliedCandidate.selectedCraftedStatKey, 'haste_mastery')
  assert.equal(page.data.gearSlotSheet.candidates[0].statSummary, '智力 285；急速 40；精通 32')

  await pageConfig.applyGearCandidate.call(page)

  const selected = page.data.selectedGearBySlot.wrist
  assert.equal(selected.crafted_stats, '40/32')
  assert.equal(selected.selectedCraftedStatKey, 'haste_mastery')
  assert.match(selected.statSummary, /急速 40/)

  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'wrist' } } })
  assert.equal(page.data.gearSlotSheet.craftedStatOptionKey, 'haste_mastery')
  assert.equal(page.data.gearSlotSheet.canApplyCandidate, true)
  assert.equal(page.data.gearSlotSheet.appliedCandidate.crafted_stats, '40/32')
})

test('gear slot sheet clears stale candidate attributes when selected track has pending stats', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '251111',
    id: '251111',
    displayName: 'Pending Hood',
    sourceType: 'raid',
    sources: [{ label: 'Void Captain - Voidspire', sourceType: 'raid' }],
    defaultVariantKey: 'myth-289',
    statSummary: '智力 140；耐力 280',
    itemStats: [
      { key: 'intellect', label: '智力', value: 140 },
      { key: 'stamina', label: '耐力', value: 280 }
    ],
    statDisplayStatus: 'verified_variant',
    variants: [
      {
        key: 'myth-289',
        label: 'Myth 289',
        difficultyKey: 'myth',
        itemLevel: 289,
        simcOptions: { ilevel: '289' },
        statSummary: '智力 140；耐力 280',
        statDisplayStatus: 'verified_variant',
        status: 'verified'
      },
      {
        key: 'hero-276',
        label: 'Hero 276',
        difficultyKey: 'hero',
        itemLevel: 276,
        simcOptions: { ilevel: '276' },
        statDisplayStatus: 'pending_current_variant',
        status: 'partial',
        blockers: ['SimulationCraft item stats']
      }
    ],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
        replacementCandidates: [{
          slot: 'head',
          simcSlot: 'head',
          label: 'Head',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })
  pageConfig.selectGearVariant.call(page, { currentTarget: { dataset: { key: 'hero-276' } } })

  const attributes = page.data.gearSlotSheet.candidates[0].detailRows.find((row) => row.label === '装备属性')
  assert.match(attributes.value, /属性待补充/)
  assert.match(attributes.value, /装等 276/)
  assert.equal(/智力 140|耐力 280/.test(attributes.value), false)
})

test('gear candidate detail uses set name for tier source and hides backend evidence rows', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const item = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '252222',
    id: '252222',
    displayName: 'Set Hood',
    sourceType: 'tier_set',
    source: 'SimulationCraft preset: MID1_Mage_Frost',
    itemSetName: '虚空粉碎者协律',
    sources: [
      { label: 'SimulationCraft preset: MID1_Mage_Frost', sourceType: 'simc_preset' },
      { label: 'Raider.IO CN observed mage frost', sourceType: 'observed_profile' },
      { label: 'Catalyst', sourceType: 'tier_set' }
    ],
    observedProfileRefs: [{ sourceName: 'Raider.IO', classKey: 'mage', specKey: 'frost' }],
    variants: [{
      key: 'myth-289',
      difficultyKey: 'myth',
      itemLevel: 289,
      simcOptions: { ilevel: '289' },
      statSummary: '智力 140；耐力 280',
      statDisplayStatus: 'verified_variant',
      status: 'verified'
    }],
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: [{ slot: 'head', simcSlot: 'head', label: 'Head' }],
        replacementCandidates: [{
          slot: 'head',
          simcSlot: 'head',
          label: 'Head',
          items: [item]
        }],
        equippedSet: {},
        slotReadiness: {},
        readiness: {},
        statSnapshot: { statStatus: 'blocked', blockers: [] }
      },
      selectedGearBySlot: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.openGearSlotSheet.call(page, { currentTarget: { dataset: { slot: 'head' } } })

  const rows = page.data.gearSlotSheet.candidates[0].detailRows
  assert.equal(rows.find((row) => row.label === '掉落来源').value, '虚空粉碎者协律-套装')
  assert.equal(rows.some((row) => row.label === '配置来源'), false)
  assert.equal(rows.some((row) => row.label === '实装观测'), false)
})

test('gear community template import blocks source reference templates and surfaces blockers', () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const baseline = completeGearSelection(['head'])
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: {},
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {},
        communityTemplates: [{
          id: 'guide-reference',
          name: 'Guide Reference',
          sourceKey: 'wowhead_guide',
          sourceName: 'Wowhead guide',
          sourceStatus: 'source_reference',
          status: 'partial',
          readySlotCount: 1,
          missingSlots: canonicalGearSlots.slice(1),
          canApplyGear: true,
          blockers: ['missing deterministic SimC variant preset'],
          gearItems: [baseline.head]
        }]
      },
      selectedGearBySlot: {},
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  const template = page.data.activeGearCommunityTemplates[0]

  assert.equal(template.cardClass, 'source-reference')
  assert.equal(template.statusLabel, '来源参考')
  assert.equal(template.canApplyGear, false)
  assert.match(template.missingSlotLabel, /缺 15 槽/)
  assert.match(template.blockerLabel, /缺少确定 SimC 变体/)

  pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'guide-reference' } } })

  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.match(toasts.at(-1).title, /暂不可导入/)
})

test('gear community template import blocks partial observed legality templates', () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const baseline = completeGearSelection(['head', 'neck'])
  const templateHead = { ...baseline.head, itemId: '277777', id: '277777', displayName: 'Community Head' }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {},
        communityTemplates: [{
          id: 'partial-community',
          name: 'Partial Community Template',
          sourceKey: 'raiderio_observed_profile',
          sourceName: 'Raider.IO observed gear',
          sourceStatus: 'partial',
          status: 'partial',
          readySlotCount: 1,
          missingSlots: ['main_hand', 'off_hand'],
          legalitySkippedSlots: ['main_hand', 'off_hand'],
          canApplyGear: true,
          blockers: [
            'main_hand gear incompatible with shaman/elemental weapon rule: Two-Handed Mace',
            'off_hand gear incompatible with selected two-hand main hand'
          ],
          gearItems: [templateHead]
        }]
      },
      selectedGearBySlot: {},
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  const template = page.data.activeGearCommunityTemplates[0]

  assert.equal(template.canApplyGear, false)
  assert.equal(template.statusLabel, '部分可用')
  assert.equal(template.actionLabel, '不可导入')
  assert.match(template.slotCoverageLabel, /已覆盖 1\/16 槽/)
  assert.equal(template.missingSlotLabel, '缺 2 槽')
  assert.match(template.blockerLabel, /main_hand gear incompatible/)

  pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'partial-community' } } })

  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.equal(page.data.selectedGearBySlot.neck, undefined)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, true)
  assert.match(toasts.at(-1).title, /暂不可导入/)
})

test('gear enhancement sheet hydration keeps the editable draft local while selected slot options load', async () => {
  const calls = []
  let resolveDetail
  const detailRequest = new Promise((resolve) => {
    resolveDetail = resolve
  })
  const selection = completeGearSelection(['neck'])
  selection.neck = {
    ...selection.neck,
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false, socketCount: 1 }
  }
  const initialPayload = {
    classKey: 'shaman',
    specKey: 'elemental',
    slots: [{ slot: 'neck', simcSlot: 'neck', label: '颈部' }],
    gearPayloadMode: 'initial',
    replacementCandidates: [{
      slot: 'neck',
      simcSlot: 'neck',
      label: '颈部',
      detailMode: 'partial',
      items: [selection.neck]
    }],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      return detailRequest
    }
  })
  const page = {
    gearPayloadCache: initialPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      gearSelectionKey: 'shaman:elemental',
      gearPayload: initialPayload,
      selectedGearBySlot: selection,
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }
  const initialIntent = require('../pages/builds/gear-selection-intent').serializeGearSelectionIntent({
    resolverContext: canonicalTestResolverContext(),
    eligibilityContext: { classKey: 'shaman', specKey: 'elemental', level: 90 },
    selectedGearBySlot: selection,
    enhancementBySlot: {}
  })
  initialPayload.resolverContext = canonicalTestResolverContext()
  const verifiedSnapshot = {
    status: 'verified',
    resolvedGearSignature: 'sha256:hydration-committed',
    constraints: {
      embellishmentMax: 2,
      slots: { neck: { socketCount: 1, canEnchant: false, canEmbellish: false } }
    },
    resolvedSlots: { neck: { selectedOptions: { gemOptionIds: [] } } }
  }
  page.gearWorkbenchState = {
    ...require('../pages/builds/gear-workbench-state').createGearWorkbenchState(
      initialPayload.resolverContext,
      initialIntent
    ),
    resolveStatus: 'verified',
    currentSnapshot: verifiedSnapshot,
    lastVerifiedSnapshot: verifiedSnapshot
  }

  pageConfig.openGearEnhancementSheet.call(page)
  page.data.gearEnhancementSheet.draftEnhancementBySlot = {
    neck: { gemOptionIds: ['neck-gem', 'stale-gem'] }
  }

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearEnhancementSheet.loading, false)
  assert.deepEqual(calls, [])
  const selectedSlotRequest = pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'neck' } }
  })
  assert.equal(page.data.gearEnhancementSheet.loading, true)
  assert.equal(page.data.gearEnhancementSheet.emptyText, '正在加载当前槽位的可配置选项...')
  await Promise.resolve()
  assert.deepEqual(calls.map((params) => params.slot), ['neck'])

  resolveDetail({
    payload: {
      ...initialPayload,
      gearPayloadMode: 'slot',
      gearSlot: 'neck',
      replacementCandidates: [{
        slot: 'neck',
        simcSlot: 'neck',
        label: '颈部',
        detailMode: 'complete',
        socketOptions: [{
          id: 'neck-gem',
          label: '项链宝石',
          status: 'verified',
          simcOptions: { gem_id: '240983' },
          payload: { qualityRank: 2 }
        }],
        items: [selection.neck]
      }]
    },
    fromFallback: false,
    error: ''
  })
  await selectedSlotRequest

  assert.equal(page.data.gearEnhancementSheet.loading, false)
  assert.equal(page.data.gearEnhancementSheet.emptyText, '')
  assert.equal(page.data.gearEnhancementSheet.gemRows[0].slot, 'neck')
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {})
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot)), {
    neck: { gemOptionIds: ['neck-gem'] }
  })
})

test('gear enhancement sheet clears stale enhancement when slot detail marks selected gear illegal', async () => {
  const calls = []
  const selection = completeGearSelection(['neck'])
  selection.neck = {
    ...selection.neck,
    itemId: '250101',
    id: '250101',
    displayName: '旧项链',
    modCapabilities: { hasSocket: true, canEnchant: false, canEmbellish: false, socketCount: 1 },
    simcReady: true
  }
  const blocker = 'neck gear incompatible with shaman/elemental legality rule: source item no longer trusted'
  const initialPayload = {
    classKey: 'shaman',
    specKey: 'elemental',
    slots: [{ slot: 'neck', simcSlot: 'neck', label: '颈部' }],
    gearPayloadMode: 'initial',
    replacementCandidates: [{
      slot: 'neck',
      simcSlot: 'neck',
      label: '颈部',
      detailMode: 'partial',
      items: [selection.neck]
    }],
    equippedSet: { neck: selection.neck },
    slotReadiness: {},
    readiness: { fullReady: true }
  }
  const illegalNeck = {
    ...selection.neck,
    simcReady: false,
    status: 'blocked',
    legalityStatus: 'blocked',
    blockers: [blocker]
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params = {}) => {
      calls.push(params)
      return Promise.resolve({
        payload: {
          ...initialPayload,
          gearPayloadMode: 'slot',
          gearSlot: 'neck',
          equippedSet: { neck: illegalNeck },
          slotReadiness: {
            neck: {
              status: 'blocked',
              reason: blocker,
              blockers: [blocker]
            }
          },
          gearLegalityBlockers: [blocker],
          replacementCandidates: [{
            slot: 'neck',
            simcSlot: 'neck',
            label: '颈部',
            detailMode: 'complete',
            items: [],
            socketOptions: []
          }]
        },
        fromFallback: false,
        error: ''
      })
    }
  })
  const page = {
    gearPayloadCache: initialPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      gearSelectionKey: 'shaman:elemental',
      gearPayload: initialPayload,
      selectedGearBySlot: selection,
      enhancementBySlot: {
        neck: {
          socketOptionId: 'old-neck-gem',
          gem_id: '240983'
        }
      },
      gearEnhancementSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await pageConfig.openGearEnhancementSheet.call(page)
  assert.deepEqual(calls, [])
  await pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'neck' } }
  })

  assert.deepEqual(calls.map((params) => params.slot), ['neck'])
  assert.equal(page.data.selectedGearBySlot.neck, undefined)
  assert.equal(page.data.enhancementBySlot.neck, undefined)
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck, undefined)
  assert.match(JSON.stringify(page.data.gearEnhancementSheet.blockers), /neck gear incompatible/)
  assert.equal(page.data.gearSlotRows[0].status, 'blocked')
  assert.match(page.data.gearSlotRows[0].blockerLabel, /neck gear incompatible/)
})

test('gear community template import does not repair skipped observed weapon slots', () => {
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ toasts })
  const baseline = completeGearSelection(['neck'])
  const templateHead = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '277777',
    id: '277777',
    displayName: 'Community Head',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const legalStaff = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '288888',
    id: '288888',
    displayName: 'Legal Staff',
    weaponType: 'Staff',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: false,
    missingFields: ['verified Battle.net metadata'],
    blockers: ['verified Battle.net metadata']
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        weaponRule: {
          mode: 'caster_shield_or_holdable',
          mainHandTypes: ['Dagger', 'Fist Weapon', 'One-Handed Axe', 'One-Handed Mace', 'Staff'],
          offHandTypes: ['Held In Off-hand', 'Shield']
        },
        slots: ['head', 'neck', 'main_hand', 'off_hand'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [{
          slot: 'main_hand',
          simcSlot: 'main_hand',
          label: '主手',
          items: [legalStaff]
        }],
        slotReadiness: {},
        readiness: {},
        communityTemplates: [{
          id: 'partial-community-weapons',
          name: 'Partial Community Template',
          sourceKey: 'raiderio_observed_profile',
          sourceName: 'Raider.IO observed gear',
          sourceStatus: 'partial',
          status: 'partial',
          readySlotCount: 1,
          missingSlots: ['main_hand', 'off_hand'],
          legalitySkippedSlots: ['main_hand', 'off_hand'],
          canApplyGear: true,
          blockers: [
            'main_hand gear incompatible with shaman/elemental weapon rule: Two-Handed Mace',
            'off_hand gear incompatible with selected two-hand main hand'
          ],
          gearItems: [templateHead]
        }]
      },
      selectedGearBySlot: {},
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'partial-community-weapons' } } })

  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.equal(page.data.selectedGearBySlot.neck, undefined)
  assert.equal(page.data.selectedGearBySlot.main_hand, undefined)
  assert.equal(page.data.selectedGearBySlot.off_hand, undefined)
  assert.match(toasts.at(-1).title, /暂不可导入/)
})

test('gear community template import does not fetch weapon detail for skipped observed slots', async () => {
  const detailRequests = []
  const legalStaff = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '288888',
    id: '288888',
    displayName: 'Legal Staff',
    weaponType: 'Staff',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: (params) => {
      detailRequests.push(params)
      if (params.mode === 'slot' && params.slot === 'main_hand') {
        return Promise.resolve({
          payload: {
            replacementCandidates: [{
              slot: 'main_hand',
              simcSlot: 'main_hand',
              label: '主手',
              detailMode: 'complete',
              items: [legalStaff]
            }]
          }
        })
      }
      return Promise.resolve({ payload: {} })
    }
  })
  const baseline = completeGearSelection(['neck'])
  const templateHead = {
    slot: 'head',
    simcSlot: 'head',
    itemId: '277777',
    id: '277777',
    displayName: 'Community Head',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const illegalMace = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '237849',
    id: '237849',
    displayName: 'Illegal Mace',
    weaponType: 'Two-Handed Mace',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { websimClassKey: 'shaman', websimSpecKey: 'elemental' },
      gearSelectionKey: 'shaman:elemental',
      activeQueryKey: 'gear',
      gearPayload: {
        gearPayloadMode: 'initial',
        weaponRule: {
          mode: 'caster_shield_or_holdable',
          mainHandTypes: ['Dagger', 'Fist Weapon', 'One-Handed Axe', 'One-Handed Mace', 'Staff'],
          offHandTypes: ['Held In Off-hand', 'Shield']
        },
        slots: ['head', 'neck', 'main_hand', 'off_hand'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [{
          slot: 'main_hand',
          simcSlot: 'main_hand',
          label: '主手',
          detailMode: 'partial',
          items: [illegalMace]
        }],
        slotReadiness: {},
        readiness: {},
        communityTemplates: [{
          id: 'partial-community-fetch-weapons',
          name: 'Partial Community Template',
          sourceKey: 'raiderio_observed_profile',
          sourceName: 'Raider.IO observed gear',
          sourceStatus: 'partial',
          status: 'partial',
          readySlotCount: 1,
          missingSlots: ['main_hand', 'off_hand'],
          legalitySkippedSlots: ['main_hand', 'off_hand'],
          canApplyGear: true,
          blockers: [
            'main_hand gear incompatible with shaman/elemental weapon rule: Two-Handed Mace',
            'off_hand gear incompatible with selected two-hand main hand'
          ],
          gearItems: [templateHead]
        }]
      },
      selectedGearBySlot: {},
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)
  await pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'partial-community-fetch-weapons' } } })

  assert.deepEqual(detailRequests.map((item) => item.slot), [])
  assert.equal(page.data.selectedGearBySlot.head, undefined)
  assert.equal(page.data.selectedGearBySlot.main_hand, undefined)
  assert.equal(page.data.selectedGearBySlot.off_hand, undefined)
})

test('gear detail does not request stat snapshot when gear payload loads', async () => {
  let refreshCalls = 0
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: [],
        equippedSet: completeGearSelection(),
        slotReadiness: {},
        readiness: {
          fullReady: true,
          warnings: [],
          itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 }
        },
        statSnapshot: {
          statStatus: 'blocked',
          blockers: ['装备模拟数据暂不可用，等待后端返回槽位结构。'],
          itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 }
        }
      }
    })
  })
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    refreshGearStats() {
      refreshCalls += 1
      return Promise.resolve()
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(refreshCalls, 0)
  assert.equal(page.data.gearSlotRows.length, canonicalGearSlots.length)
})

test('gear detail requests SimC stat snapshot when gear and talents are complete', async () => {
  let statsPayload = null
  let resolveStats
  const statsRequested = new Promise((resolve) => {
    resolveStats = resolve
  })
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: [],
        equippedSet: completeGearSelection(),
        slotReadiness: {},
        readiness: {
          fullReady: true,
          warnings: [],
          itemLevel: { key: 'itemLevel', label: '装备等级', value: '289', rawValue: 289 }
        },
        communityTemplates: [],
        resolverContext: canonicalTestResolverContext()
      }
    }),
    requestWebsimGearResolve: (selectionIntent) => canonicalResolveTransport(selectionIntent),
    requestWebsimGearStatSnapshot: (selectionIntent, profileContext) => {
      statsPayload = { selectionIntent, profileContext }
      resolveStats()
      return Promise.resolve(canonicalStatTransport({
          statStatus: 'verified',
          statSource: 'simulationcraft_json',
          blockers: [],
          primary: { key: 'intellect', label: '智力', value: '2,344', rawValue: 2344 },
          stamina: { key: 'stamina', label: '耐力', value: '20,067', rawValue: 20067 },
          secondary: [
            { key: 'crit', label: '暴击', value: '994', rawValue: 994, convertedValue: '28.6%' },
            { key: 'haste', label: '急速', value: '554', rawValue: 554, convertedValue: '18.3%' },
            { key: 'mastery', label: '精通', value: '545', rawValue: 545, convertedValue: '36.6%' },
            { key: 'versatility', label: '全能', value: '83', rawValue: 83, convertedValue: '1.5%' }
          ],
          itemLevel: { key: 'itemLevel', label: '装备等级', value: '289', rawValue: 289 }
      }))
    }
  })
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { importCode: 'C4DA' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await statsRequested
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(statsPayload.selectionIntent.eligibilityContext.classKey, 'mage')
  assert.equal(statsPayload.selectionIntent.eligibilityContext.specKey, 'frost')
  assert.equal(Object.keys(statsPayload.selectionIntent.slots).length, canonicalGearSlots.length)
  assert.equal(statsPayload.profileContext.talents, 'C4DA')
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'crit').convertedValue, '28.6%')
})

test('gear detail requests SimC stat snapshot with community talent import when detail lacks code', async () => {
  let statsPayload = null
  let importRequest = null
  let resolveStats
  const statsRequested = new Promise((resolve) => {
    resolveStats = resolve
  })
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear: () => Promise.resolve({
      payload: {
        classKey: 'mage',
        specKey: 'frost',
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        replacementCandidates: [],
        equippedSet: completeGearSelection(),
        slotReadiness: {},
        readiness: {
          fullReady: true,
          warnings: [],
          itemLevel: { key: 'itemLevel', label: '瑁呭绛夌骇', value: '289', rawValue: 289 }
        },
        communityTemplates: [],
        resolverContext: canonicalTestResolverContext()
      }
    }),
    requestWebsimGearResolve: (selectionIntent) => canonicalResolveTransport(selectionIntent),
    requestWebsimTalentImport: (params) => {
      importRequest = params
      return Promise.resolve({
      payload: {
          status: 'verified',
          source: 'community_template',
          importCode: 'COMMUNITY-C4DA'
      }
      })
    },
    requestWebsimTalents: () => {
      throw new Error('gear stats talent import must use the narrow endpoint')
    },
    requestWebsimGearStatSnapshot: (selectionIntent, profileContext) => {
      statsPayload = { selectionIntent, profileContext }
      resolveStats()
      return Promise.resolve(canonicalStatTransport({
          statStatus: 'verified',
          statSource: 'simulationcraft_json',
          blockers: [],
          primary: { key: 'intellect', label: '鏅哄姏', value: '2,344', rawValue: 2344 },
          stamina: { key: 'stamina', label: '鑰愬姏', value: '20,067', rawValue: 20067 },
          secondary: [
            { key: 'crit', label: '鏆村嚮', value: '994', rawValue: 994, convertedValue: '28.6%' }
          ]
      }))
    }
  })
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      selectedDetail: { className: '娉曞笀', specName: '鍐伴湝', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: {},
      gearSelectionKey: '',
      gearSlotSheet: {}
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.loadWebsimGearForSelection.call(page, {
    selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' }
  })
  await statsRequested
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(statsPayload.profileContext.talents, 'COMMUNITY-C4DA')
  assert.equal(importRequest.classKey, 'mage')
  assert.equal(importRequest.specKey, 'frost')
  assert.equal(page.data.gearStatsTalentImport, 'COMMUNITY-C4DA')
  assert.equal(page.data.gearAttributePanel.statRows.find((row) => row.key === 'crit').convertedValue, '28.6%')
})

test('gear stats refresh polls one 202 into verified 200 and reuses the exact signature', async () => {
  let requestCount = 0
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearStatSnapshot: () => {
      requestCount += 1
      if (requestCount === 1) return Promise.resolve(pendingStatTransport(1))
      return Promise.resolve(canonicalStatTransport({
            statStatus: 'verified',
            statSource: 'simulationcraft_json',
            blockers: [],
            secondary: [
              { key: 'crit', label: '暴击', value: '994', rawValue: 994, convertedValue: '28.6%' }
            ]
      }))
    }
  })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const requestPayload = {
    selectionIntent: {
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {}
    },
    profileContext: { talents: 'C4DA', scenarioKey: 'single' }
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { importCode: 'C4DA' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearPayload: {
        classKey: 'mage',
        specKey: 'frost',
        slots,
        replacementCandidates: [],
        equippedSet: {},
        slotReadiness: {},
        readiness: { fullReady: true }
      },
      selectedGearBySlot: completeGearSelection(),
      enhancementBySlot: {},
      gearStatSnapshot: { statStatus: 'pending', blockers: [] }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    waitForGearStatSnapshotRetry: () => Promise.resolve()
  }

  await pageConfig.refreshGearStats.call(page, requestPayload, 'same-signature')
  await pageConfig.refreshGearStats.call(page, requestPayload, 'same-signature')

  assert.equal(requestCount, 2)
  assert.equal(page.data.gearStatSnapshot.statStatus, 'verified')
})

test('gear detail suppresses an in-flight stat response after the current Intent becomes unavailable', async () => {
  let resolveStatRequest
  const deferred = new Promise((resolve) => {
    resolveStatRequest = resolve
  })
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearStatSnapshot: () => deferred
  })
  const requestPayload = {
    selectionIntent: {
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {}
    },
    profileContext: { talents: 'C4DA', scenarioKey: 'single' }
  }
  const page = {
    ...pageConfig,
    data: {
      ...pageConfig.data,
      selectedDetail: { details: { talents: { importCode: 'C4DA' }, gear: {} } },
      activeQueryKey: 'gear',
      gearStatSnapshot: { statStatus: 'verified', blockers: [], primary: { key: 'intellect', value: '100' } }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  const refresh = pageConfig.refreshGearStats.call(page, requestPayload, 'intent-v1')
  await pageConfig.clearGearStatsSnapshot.call(page, ['等待新的 Intent 完成校验'])
  resolveStatRequest(canonicalStatTransport({
    statStatus: 'verified', blockers: [], primary: { key: 'intellect', value: '999' }
  }, 'sha256:stale-stat'))
  await refresh

  assert.notEqual(page.gearStatSnapshotState.statSnapshotStatus, 'verified')
  assert.equal(page.data.gearStatSnapshot.primary && page.data.gearStatSnapshot.primary.value, '100')
  assert.equal(page.data.gearStatSnapshot.stale, true)
  assert.equal(page.data.gearStatSnapshot.readOnly, true)
  assert.match(page.data.gearStatBlockers.join('；'), /新的 Intent/)
})

test('gear detail keeps community templates when stat invalidation rederives from the slim page payload', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const fullGearPayload = {
    classKey: 'mage',
    specKey: 'frost',
    slots,
    replacementCandidates: [],
    equippedSet: {},
    slotReadiness: {},
    readiness: { fullReady: false },
    communityTemplates: [{
      id: 'observed-profile-mage-frost',
      classKey: 'mage',
      specKey: 'frost',
      name: 'Raider.IO observed gear',
      sourceKey: 'raiderio_observed_profile',
      sourceStatus: 'synced',
      status: 'complete',
      readySlotCount: 16,
      missingSlots: [],
      canApplyGear: true,
      gearItems: []
    }],
    baselineTemplates: [],
    communityTemplateSync: { sourceStatus: 'synced' }
  }
  const page = {
    ...pageConfig,
    gearPayloadCache: fullGearPayload,
    data: {
      ...pageConfig.data,
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearPayload: {
        classKey: 'mage',
        specKey: 'frost',
        slots,
        readiness: { fullReady: false }
      },
      activeGearCommunityTemplates: [{ id: 'observed-profile-mage-frost' }],
      gearStatSnapshot: { statStatus: 'verified', blockers: [] }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await pageConfig.clearGearStatsSnapshot.call(page, ['等待完整装备和天赋后计算属性百分比'])

  assert.equal(page.data.activeGearCommunityTemplates.length, 1)
  assert.equal(page.data.activeGearCommunityTemplates[0].id, 'observed-profile-mage-frost')
})

test('gear template save asks for a name before storing neutral complete status', async () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const incompleteSelection = completeGearSelection(canonicalGearSlots.slice(0, -1))
  const completeSelection = completeGearSelection()
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1'
      },
      selectedGearBySlot: incompleteSelection,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /请补齐 16 个装备槽位/)

  page.data.selectedGearBySlot = completeSelection
  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.equal(page.data.gearSaveTemplateSheet.visible, true)
  assert.match(page.data.gearSaveTemplateSheet.name, /^法师-冰霜-单体-\d{4} \d{4}$/)
  assert.ok(page.data.gearSaveTemplateSheet.name.length <= 28)

  pageConfig.updateGearTemplateName.call(page, { detail: { value: '我的装备模板' } })
  await pageConfig.confirmSaveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 1)
  assert.equal(page.data.gearSaveTemplateSheet.visible, false)
  assert.equal(savedTemplates[0].status, 'complete')
  assert.equal(savedTemplates[0].statusLabel, '完整配置')
  assert.equal(savedTemplates[0].title, '我的装备模板')
  assert.equal(Array.isArray(savedTemplates[0].simcLines), true)
  assert.equal(savedTemplates[0].simcLines.length, 0)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(Object.keys(snapshot.gearBySlot).length, canonicalGearSlots.length)
  assert.deepEqual(snapshot.enhancementBySlot, {})
  assert.equal(snapshot.schemaRevision, 'websim-gear-enhancement-snapshot-v1')
})

test('gear template save stores verified stat snapshot metadata for SimC summary', async () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const verifiedStatSnapshot = {
    statStatus: 'verified',
    primary: { key: 'intellect', label: 'Intellect', value: '12,345', rawValue: 12345 },
    secondary: [
      { key: 'crit', label: 'Crit', value: '994', rawValue: 994, convertedValue: '28.6%' },
      { key: 'haste', label: 'Haste', value: '884', rawValue: 884, convertedValue: '18.3%' },
      { key: 'mastery', label: 'Mastery', value: '773', rawValue: 773, convertedValue: '42.1%' },
      { key: 'versatility', label: 'Versatility', value: '662', rawValue: 662, convertedValue: '8.2%' }
    ]
  }
  const page = {
    data: {
      selectedDetail: { className: 'Mage', specName: 'Arcane', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: 'Mage', title: 'Arcane', specName: 'Arcane', websimClassKey: 'mage', websimSpecKey: 'arcane' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1'
      },
      selectedGearBySlot: completeGearSelection(),
      enhancementBySlot: {},
      gearStatSnapshot: verifiedStatSnapshot,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    gearStatSnapshotState: {
      statSnapshotStatus: 'verified',
      currentStatSnapshot: verifiedStatSnapshot,
      verifiedStatContextKey: 'intent-v1|profile-v1',
      statSnapshotSignature: 'sha256:verified-stat'
    }
  }

  pageConfig.saveGearTemplate.call(page)
  await pageConfig.confirmSaveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].metadata.statSnapshot.statStatus, 'verified')
  assert.equal(savedTemplates[0].metadata.statSnapshot.primary.value, '12,345')
  assert.deepEqual(savedTemplates[0].metadata.statSnapshot.secondary.map((row) => row.convertedValue), ['28.6%', '18.3%', '42.1%', '8.2%'])
  assert.equal(savedTemplates[0].metadata.statSnapshotRequestSignature, 'intent-v1|profile-v1')
  assert.equal(savedTemplates[0].metadata.statSnapshotSignature, 'sha256:verified-stat')
  const rawSnapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(rawSnapshot.statSnapshot, undefined)
})

test('gear template save stores structured enhancement snapshot for backend serialization', async () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.head = {
    ...selection.head,
    key: 'head-heavy-ui',
    detailRows: [{ label: '装备属性', value: '智力 120' }],
    gameAsset: { iconUrl: 'https://example.invalid/icon.png' },
    statusLabel: '已验证',
    trustLabel: '可信'
  }
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: false }
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true },
    embellishmentOptions: [
      {
        id: 'client-only-embellishment',
        status: 'verified',
        payload: { qualityRank: 2 },
        simcOptions: { embellishment: 'client_only_lining' }
      }
    ]
  }
  const enhancementBySlot = {
    finger1: {
      socketOptionId: 'gem-rank-two',
      enchantOptionId: 'enchant-rank-two',
      gem_id: '240983',
      gem_ilevel: '707',
      enchant_id: '7334'
    },
    wrist: {
      embellishmentOptionId: 'embellishment-blue-silken-lining',
      embellishment: 'blue_silken_lining'
    }
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        replacementCandidates: [
          {
            slot: 'finger1',
            simcSlot: 'finger1',
            label: 'finger1',
            items: [],
            socketOptions: [
              {
                id: 'gem-rank-two',
                label: '迅捷宝石',
                statSummary: '+147急速',
                status: 'verified',
                simcOptions: { gem_id: '240983', gem_ilevel: '707' },
                payload: { qualityRank: 2 }
              }
            ],
            enchantOptions: [
              {
                id: 'enchant-rank-two',
                label: '自然之怒',
                displayLabel: '自然之怒',
                displayKind: 'name',
                displayStatus: 'verified',
                evidenceSource: 'wago_db2_spell_item_enchantment',
                status: 'verified',
                simcOptions: { enchant_id: '7334' },
                payload: { qualityRank: 2 }
              }
            ]
          },
          {
            slot: 'wrist',
            simcSlot: 'wrist',
            label: 'wrist',
            items: [],
            embellishmentOptions: [
              {
                id: 'embellishment-blue-silken-lining',
                label: '蓝色丝质内衬',
                displayLabel: '蓝色丝质内衬',
                displayKind: 'name',
                displayStatus: 'verified',
                evidenceSource: 'server_owned_evidence_seed',
                status: 'verified',
                simcOptions: { embellishment: 'blue_silken_lining' },
                payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
              }
            ]
          }
        ]
      },
      selectedGearBySlot: selection,
      enhancementBySlot,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await confirmGearTemplateSave(pageConfig, page)

  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(snapshot.schemaRevision, 'websim-gear-enhancement-snapshot-v1')
  assert.equal(snapshot.gearBySlot.head.itemId, '250000')
  assert.equal(snapshot.gearBySlot.head.key, undefined)
  assert.equal(snapshot.gearBySlot.head.detailRows, undefined)
  assert.equal(snapshot.gearBySlot.head.gameAsset, undefined)
  assert.equal(snapshot.gearBySlot.head.statusLabel, undefined)
  assert.equal(snapshot.gearBySlot.head.trustLabel, undefined)
  assert.equal(snapshot.gearBySlot.wrist.embellishmentOptions, undefined)
  assert.equal(JSON.stringify(snapshot.enhancementBySlot), JSON.stringify(enhancementBySlot))
  assert.equal(JSON.stringify(savedTemplates[0].metadata.enhancementBySlot), JSON.stringify(enhancementBySlot))
  assert.doesNotMatch(savedTemplates[0].rawString, /^head=/m)
})

test('gear template save serializes verified canonical enhancements instead of submitted draft', async () => {
  const savedTemplates = []
  const submitted = {
    finger1: {
      gemOptionIds: ['gem-draft', 'gem-draft'],
      enchantOptionId: 'enchant-draft'
    }
  }
  const canonical = {
    finger1: {
      gemOptionIds: ['gem-server', 'gem-server'],
      enchantOptionId: 'enchant-server'
    }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    savedTemplates,
    requestWebsimGearResolve(selectionIntent) {
      return Promise.resolve({
        httpStatus: 200,
        fromFallback: false,
        payload: {
          contractRevision: 'gear-result-envelope-v1',
          status: 'resolved',
          problems: [],
          data: {
            contractRevision: 'gear-resolved-snapshot-v1',
            status: 'verified',
            resolvedGearSignature: 'sha256:canonical-save',
            dependencyVector: { gearCatalogRevision: 'gear-r17' },
            staticAttributes: {},
            setState: { itemSetCounts: {}, activeDynamicEffects: [] },
            aggregateLegality: { status: 'verified', problemCodes: [] },
            profileReadiness: { status: 'verified', simcReady: true, requiredSlots: ['finger1'], readySlots: ['finger1'] },
            constraints: {
              embellishmentMax: 2,
              slots: { finger1: { socketCount: 2, canEnchant: true, canEmbellish: false } }
            },
            resolvedSlots: {
              finger1: {
                itemLevel: 707,
                selectedOptions: canonical.finger1,
                simcOptions: { gem_id: 'raw-must-not-save', enchant_id: 'raw-must-not-save' }
              }
            },
            problems: []
          }
        }
      })
    }
  })
  const selectedGearBySlot = {
    finger1: {
      slot: 'finger1', simcSlot: 'finger1', itemId: '250060', variantKey: 'variant-ring',
      modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: true, canEmbellish: false }
    }
  }
  const option = (id, type) => ({
    id,
    optionKey: id,
    displayLabel: id,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: type === 'gem' ? { gem_id: id } : { enchant_id: id }
  })
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', label: '戒指 1', items: [selectedGearBySlot.finger1],
      socketOptions: [option('gem-draft', 'gem'), option('gem-server', 'gem')],
      enchantOptions: [option('enchant-draft', 'enchant'), option('enchant-server', 'enchant')]
    }],
    resolverContext: canonicalTestResolverContext()
  }
  const page = {
    data: {
      ...pageConfig.data,
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { importCode: 'talent-code' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload,
      selectedGearBySlot,
      enhancementBySlot: {},
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  await pageConfig.confirmAndResolveGearIntent.call(page, selectedGearBySlot, submitted)
  await confirmGearTemplateSave(pageConfig, page, '服务端配置')

  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.deepEqual(snapshot.enhancementBySlot, canonical)
  assert.deepEqual(JSON.parse(JSON.stringify(savedTemplates[0].metadata.enhancementBySlot)), canonical)
  assert.deepEqual(
    JSON.parse(JSON.stringify(savedTemplates[0].metadata.selectionIntent.slots.finger1.gemOptionIds)),
    ['gem-server', 'gem-server']
  )
  assert.equal(savedTemplates[0].metadata.selectionIntent.slots.finger1.enchantOptionId, 'enchant-server')
  assert.doesNotMatch(savedTemplates[0].rawString, /raw-must-not-save/)
})

test('gear template save prunes invalid enhancement fields by type', async () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.finger1 = {
    ...selection.finger1,
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false }
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        replacementCandidates: [
          {
            slot: 'finger1',
            simcSlot: 'finger1',
            label: 'finger1',
            items: [],
            enchantOptions: [
              {
                id: 'enchant-rank-two',
                label: '自然之怒',
                displayLabel: '自然之怒',
                displayKind: 'name',
                displayStatus: 'verified',
                evidenceSource: 'wago_db2_spell_item_enchantment',
                status: 'verified',
                simcOptions: { enchant_id: '7334' },
                payload: { qualityRank: 2 }
              }
            ]
          }
        ]
      },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        finger1: {
          socketOptionId: 'gem-rank-two',
          gem_id: '240983',
          gem_ilevel: '707',
          enchantOptionId: 'enchant-rank-two',
          enchant_id: '7334'
        }
      },
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await confirmGearTemplateSave(pageConfig, page)

  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.deepEqual(snapshot.enhancementBySlot, {
    finger1: {
      enchantOptionId: 'enchant-rank-two',
      enchant_id: '7334'
    }
  })
})

test('gear template save blocks over-cap embellishments', () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.back = {
    ...selection.back,
    embellishment: 'dawnthread_lining'
  }
  selection.chest = {
    ...selection.chest,
    intrinsicEmbellishment: 'duskthread_lining'
  }
  selection.wrist = {
    ...selection.wrist,
    sourceType: 'crafted',
    modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: true }
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        replacementCandidates: [
          {
            slot: 'wrist',
            simcSlot: 'wrist',
            label: 'wrist',
            items: [],
            embellishmentOptions: [
              {
                id: 'embellishment-blue-silken-lining',
                label: '蓝色丝质内衬',
                displayLabel: '蓝色丝质内衬',
                displayKind: 'name',
                displayStatus: 'verified',
                evidenceSource: 'server_owned_evidence_seed',
                status: 'verified',
                simcOptions: { embellishment: 'blue_silken_lining' },
                payload: { qualityRank: 2, simcKey: 'blue_silken_lining' }
              }
            ]
          }
        ]
      },
      selectedGearBySlot: selection,
      enhancementBySlot: {
        wrist: {
          embellishmentOptionId: 'embellishment-blue-silken-lining',
          embellishment: 'blue_silken_lining'
        }
      },
      gearEnhancementSheet: { visible: false },
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /美化已超过上限 3\/2/)
  assert.ok(page.data.gearEnhancementSheet.blockers.includes('美化已超过上限 3/2'))
})

test('gear template save allows backend-ready two-handed setups without off hand', async () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const twoHandSelection = completeGearSelection(canonicalGearSlots.filter((slot) => slot !== 'off_hand'))
  const page = {
    data: {
      selectedDetail: { className: '死亡骑士', specName: '鲜血', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '死亡骑士', title: '鲜血', specName: '鲜血', websimClassKey: 'deathknight', websimSpecKey: 'blood' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        readiness: {
          fullReady: true,
          missingRequiredSlots: ['off_hand'],
          missingCoreSlots: [],
          requiredReadyCount: 15
        }
      },
      selectedGearBySlot: twoHandSelection,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await confirmGearTemplateSave(pageConfig, page)

  assert.equal(toasts.at(-1).title, '装备模板已保存')
  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].status, 'complete')
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(Object.keys(snapshot.gearBySlot).length, canonicalGearSlots.length - 1)
  assert.equal(snapshot.gearBySlot.off_hand, undefined)
})

test('gear selection prunes stale off hand when selected main hand is two-handed', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.main_hand = {
    ...selection.main_hand,
    itemId: '260106',
    id: '260106',
    displayName: 'Brewmaster Mace',
    weaponType: 'One-Handed Mace'
  }
  selection.off_hand = {
    ...selection.off_hand,
    itemId: '260109',
    id: '260109',
    displayName: 'Brewmaster Sidearm',
    weaponType: 'One-Handed Mace',
    modCapabilities: { canEnchant: true }
  }
  const twoHand = {
    slot: 'main_hand',
    simcSlot: 'main_hand',
    itemId: '260107',
    id: '260107',
    displayName: 'Brewmaster Staff',
    ilevel: 289,
    bonus_id: '6652',
    weaponType: 'Staff',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { className: '武僧', specName: '酒仙', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '武僧', title: '酒仙', specName: '酒仙', websimClassKey: 'monk', websimSpecKey: 'brewmaster' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        weaponRule: {
          mode: 'selectable_two_hand_or_dual_wield_1h',
          mainHandTypes: ['Staff', 'Polearm', 'One-Handed Mace'],
          offHandTypes: ['One-Handed Mace']
        },
        readiness: {
          missingRequiredSlots: ['off_hand'],
          missingCoreSlots: []
        }
      },
      selectedGearBySlot: selection,
      enhancementBySlot: { off_hand: { enchantOptionId: 'observed-enchant-rondorei', enchant_id: '8039' } },
      gearSlotSheet: {
        slot: 'main_hand',
        appliedCandidate: twoHand
      }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await pageConfig.applyGearCandidate.call(page)

  assert.equal(page.data.selectedGearBySlot.main_hand.itemId, '260107')
  assert.equal(page.data.selectedGearBySlot.off_hand, undefined)
  assert.equal(page.data.enhancementBySlot.off_hand, undefined)
})

test('gear slot rows show off hand occupied when main hand is two-handed', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection(canonicalGearSlots.filter((slot) => slot !== 'off_hand'))
  selection.main_hand = {
    ...selection.main_hand,
    itemId: '260107',
    id: '260107',
    displayName: 'Brewmaster Staff',
    weaponType: 'Staff',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { className: '武僧', specName: '酒仙', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '武僧', title: '酒仙', specName: '酒仙', websimClassKey: 'monk', websimSpecKey: 'brewmaster' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        weaponRule: {
          mode: 'selectable_two_hand_or_dual_wield_1h',
          mainHandTypes: ['Staff', 'Polearm', 'One-Handed Mace'],
          offHandTypes: ['One-Handed Mace']
        },
        readiness: {
          fullReady: true,
          missingRequiredSlots: ['off_hand'],
          missingCoreSlots: [],
          requiredReadyCount: 15
        },
        slotReadiness: {
          off_hand: { status: 'blocked', reason: 'missing off hand item' }
        }
      },
      selectedGearBySlot: selection
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.refreshDerivedState.call(page)

  const offHandRow = page.data.gearSlotRows.find((row) => row.slot === 'off_hand')
  assert.equal(page.data.selectedGearBySlot.off_hand, undefined)
  assert.equal(offHandRow.displayName, '双手武器已占用')
  assert.equal(offHandRow.itemId, '')
  assert.equal(offHandRow.status, 'verified')
  assert.equal(offHandRow.source, '主手双手武器')
})

test('gear template save prunes stale off hand and enhancement before snapshot', async () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.main_hand = {
    ...selection.main_hand,
    itemId: '260107',
    id: '260107',
    displayName: 'Brewmaster Staff',
    weaponType: 'Staff'
  }
  selection.off_hand = {
    ...selection.off_hand,
    itemId: '260109',
    id: '260109',
    displayName: 'Brewmaster Sidearm',
    weaponType: 'One-Handed Mace'
  }
  const page = {
    data: {
      selectedDetail: { className: '武僧', specName: '酒仙', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '武僧', title: '酒仙', specName: '酒仙', websimClassKey: 'monk', websimSpecKey: 'brewmaster' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1',
        weaponRule: {
          mode: 'selectable_two_hand_or_dual_wield_1h',
          mainHandTypes: ['Staff', 'Polearm', 'One-Handed Mace'],
          offHandTypes: ['One-Handed Mace']
        },
        readiness: {
          fullReady: true,
          missingRequiredSlots: ['off_hand'],
          missingCoreSlots: [],
          requiredReadyCount: 15
        }
      },
      selectedGearBySlot: selection,
      enhancementBySlot: { off_hand: { enchantOptionId: 'observed-enchant-rondorei', enchant_id: '8039' } },
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await confirmGearTemplateSave(pageConfig, page)

  assert.equal(toasts.at(-1).title, '装备模板已保存')
  assert.equal(savedTemplates.length, 1)
  const snapshot = JSON.parse(savedTemplates[0].rawString)
  assert.equal(snapshot.gearBySlot.off_hand, undefined)
  assert.equal(snapshot.enhancementBySlot.off_hand, undefined)
  assert.equal(Object.keys(snapshot.gearBySlot).length, canonicalGearSlots.length - 1)
})

test('gear template save keeps source pending evidence in metadata', async () => {
  const savedTemplates = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates })
  const slots = canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot }))
  const selection = completeGearSelection()
  selection.waist = {
    ...selection.waist,
    source: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire',
    sourceType: 'simc_preset',
    sources: [{ sourceType: 'simc_preset', sourceLabel: 'SimulationCraft preset: MID1_Mage_Frost_Frostfire' }],
    statSummary: '智力 70；耐力 995',
    simcReady: true
  }
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots,
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1'
      },
      selectedGearBySlot: selection,
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await confirmGearTemplateSave(pageConfig, page)

  assert.equal(savedTemplates.length, 1)
  assert.equal(savedTemplates[0].status, 'complete_with_warnings')
  assert.equal(savedTemplates[0].statusLabel, '完整配置 · 来源待补')
  assert.deepEqual(Array.from(savedTemplates[0].metadata.sourcePendingSlots), ['waist'])
  assert.deepEqual(Array.from(savedTemplates[0].metadata.statPendingSlots), [])
  assert.match(savedTemplates[0].metadata.warningSummary, /来源待补/)
})

test('gear template save validation names missing and untrusted slots', () => {
  const savedTemplates = []
  const toasts = []
  const pageConfig = loadBuildsDetailPageConfig({ savedTemplates, toasts })
  const page = {
    data: {
      selectedDetail: { className: '法师', specName: '冰霜', details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { className: '法师', title: '冰霜', specName: '冰霜', websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: canonicalGearSlots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
        maxLevel: 90,
        gearSchemaRevision: 'websim-gear-simulator-v1'
      },
      selectedGearBySlot: completeGearSelection(canonicalGearSlots.slice(0, -1)),
      selectedGearTemplateScenarioIndex: 0
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /off_hand/)

  page.data.selectedGearBySlot = {
    ...completeGearSelection(canonicalGearSlots.slice(0, -1)),
    off_hand: {
      slot: 'off_hand',
      simcSlot: 'off_hand',
      id: 'guide-only-offhand',
      displayName: 'Guide Only Offhand',
      ilevel: 707,
      bonus_id: '12345',
      metadataStatus: 'source_reference',
      sourceType: 'source_reference',
      simcReady: false
    }
  }

  pageConfig.saveGearTemplate.call(page)

  assert.equal(savedTemplates.length, 0)
  assert.match(toasts.at(-1).title, /off_hand/)
  assert.match(toasts.at(-1).title, /物品 ID|来源参考/)
})

test('gear reset restores the backend equipped baseline', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseline = completeGearSelection(['head', 'neck'])
  const modifiedHead = { ...baseline.head, itemId: '299999', id: '299999', displayName: 'Modified Head' }
  const page = {
    communityEnhancementImportState: {
      templateId: 'community-before-reset', serial: 7, resolvedGearSignature: 'sha256:before-reset',
      unresolvedBySlot: { neck: { gemIds: ['raw-reset'], enchantIds: [], embellishments: [], readOnly: true } },
      warnings: ['reset me']
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {
        ...baseline,
        head: modifiedHead
      },
      gearSlotSheet: { visible: true },
      gearCommunityTemplateSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.resetGearSelection.call(page)

  assert.equal(page.data.selectedGearBySlot.head.itemId, baseline.head.itemId)
  assert.equal(page.data.selectedGearBySlot.neck.itemId, baseline.neck.itemId)
  assert.equal(page.data.gearSlotSheet.visible, false)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), {
    templateId: '', serial: 0, resolvedGearSignature: '', unresolvedBySlot: {}, warnings: []
  })
})

test('gear community template applies only template slots without baseline fill', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseline = completeGearSelection(['head', 'neck'])
  const previousNeck = { ...baseline.neck, itemId: '288888', id: '288888', displayName: 'Previous Neck' }
  const templateHead = { ...baseline.head, itemId: '277777', id: '277777', displayName: 'Community Head' }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload: {
        slots: ['head', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: {
        ...baseline,
        neck: previousNeck
      },
      activeGearCommunityTemplates: [{
        id: 'community-head',
        name: 'Community Head Template',
        canApplyGear: true,
        gearItems: [templateHead]
      }],
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  await pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'community-head' } } })

  assert.equal(page.data.selectedGearBySlot.head.itemId, templateHead.itemId)
  assert.equal(page.data.selectedGearBySlot.neck, undefined)
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
  assert.equal(page.data.gearSlotSheet.visible, false)
})

test('gear community template import keeps matched enhancement options configurable', async () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const baseline = completeGearSelection(['finger1'])
  const candidateRing = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '277777',
    id: '277777',
    displayName: 'Community Ring',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true,
    sourceType: 'observed_profile',
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: true, socketCount: 1 },
    socketOptions: [{
      id: 'gem-community-ring',
      displayLabel: '+32主属性',
      displayStatus: 'verified',
      status: 'verified',
      simcOptions: { gem_id: '240983' },
      payload: { qualityRank: 2 }
    }],
    enchantOptions: [{
      id: 'enchant-community-ring',
      displayLabel: '苍穹全能',
      displayStatus: 'verified',
      status: 'verified',
      simcOptions: { enchant_id: '7967' },
      payload: { qualityRank: 2 }
    }],
    embellishmentOptions: [{
      id: 'embellishment-community-ring',
      displayLabel: '奥纹内衬',
      displayStatus: 'verified',
      status: 'verified',
      simcOptions: { embellishment: 'dawnthread_lining' },
      payload: { qualityRank: 2, slotGroup: 'jewelry' }
    }]
  }
  const templateRing = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: candidateRing.itemId,
    id: candidateRing.id,
    displayName: candidateRing.displayName,
    ilevel: candidateRing.ilevel,
    bonus_id: candidateRing.bonus_id,
    simcReady: true,
    modCapabilities: candidateRing.modCapabilities
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearPayload: {
        slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
        equippedSet: baseline,
        replacementCandidates: [{
          slot: 'finger1',
          simcSlot: 'finger1',
          label: '戒指 1',
          items: [candidateRing]
        }],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: baseline,
      enhancementBySlot: {},
      activeGearCommunityTemplates: [{
        id: 'community-ring',
        name: 'Community Ring Template',
        canApplyGear: true,
        gearItems: [templateRing]
      }],
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true },
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }
  page.gearPayloadCache = page.data.gearPayload

  await pageConfig.applyGearCommunityTemplate.call(page, { currentTarget: { dataset: { id: 'community-ring' } } })
  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '0/1')
  assert.equal(JSON.stringify(page.data.gearEnhancementSheet.equipmentRows.map((row) => row.slot)), JSON.stringify(['finger1']))
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options[0].label, '+32主属性')
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].label, '苍穹全能')
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options[0].label, '奥纹内衬')
})

test('gear community template reconciles observed enhancements to verified option identities', async () => {
  const detailRequests = []
  const resolveRequests = []
  const option = (optionKey, type, value, displayLabel, extra = {}) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { [type]: value },
    ...extra
  })
  const gemOne = option('gem-240892', 'gem_id', '240892', '+32 急速')
  const gemTwo = option('gem-240900', 'gem_id', '240900', '+32 精通')
  const ringEnchant = option('ring-enchant-7967', 'enchant_id', '7967', '苍穹全能')
  const lining = option(
    'embellishment-arcanoweave-lining',
    'embellishment',
    'arcanoweave_lining',
    '奥纹内衬',
    { slotGroup: 'armor' }
  )
  const ring = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '277771',
    id: '277771',
    variantKey: 'ring-observed',
    displayName: 'Community Ring',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: true, canEmbellish: false }
  }
  const back = {
    slot: 'back',
    simcSlot: 'back',
    itemId: '277772',
    id: '277772',
    variantKey: 'back-observed',
    displayName: 'Community Cloak',
    armorType: 'Cloth',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
  }
  const gearPayload = {
    classKey: 'mage',
    specKey: 'frost',
    maxLevel: 90,
    gearPayloadMode: 'initial',
    slots: [
      { slot: 'back', simcSlot: 'back', label: '披风' },
      { slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }
    ],
    equippedSet: {},
    replacementCandidates: [
      {
        slot: 'back',
        simcSlot: 'back',
        label: '披风',
        detailMode: 'complete',
        items: [back],
        embellishmentOptions: [lining]
      },
      {
        slot: 'finger1',
        simcSlot: 'finger1',
        label: '戒指 1',
        detailMode: 'partial',
        items: [ring]
      }
    ],
    slotReadiness: {},
    readiness: { fullReady: true },
    resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear(params) {
      detailRequests.push(params)
      return Promise.resolve({
        fromFallback: false,
        error: '',
        payload: {
          replacementCandidates: [{
            slot: params.slot,
            simcSlot: params.slot,
            label: '戒指 1',
            detailMode: 'complete',
            items: [ring],
            socketOptions: [gemOne, gemTwo],
            enchantOptions: [ringEnchant]
          }]
        }
      })
    },
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalResolveTransport(selectionIntent)
    }
  })
  const template = {
    id: 'observed-enhancements',
    name: 'Observed Enhancements',
    canApplyGear: true,
    gearItems: [
      { ...ring, gem_id: '240892/240900', enchant_id: '7967' },
      { ...back, embellishment: 'arcanoweave_lining' }
    ]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost',
      gearPayload,
      selectedGearBySlot: {},
      enhancementBySlot: {},
      activeGearCommunityTemplates: [template],
      gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true },
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })

  assert.deepEqual(detailRequests.map((params) => `${params.mode}:${params.slot}`), ['slot:finger1'])
  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1)), {
    itemId: '277771',
    variantKey: 'ring-observed',
    gemOptionIds: ['gem-240892', 'gem-240900'],
    enchantOptionId: 'ring-enchant-7967',
    embellishmentOptionId: '',
    craftedOptionId: '',
    catalystOptionId: ''
  })
  assert.equal(resolveRequests[0].slots.back.embellishmentOptionId, 'embellishment-arcanoweave-lining')
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), {
    templateId: 'observed-enhancements',
    serial: 1,
    resolvedGearSignature: 'sha256:test-resolved',
    unresolvedBySlot: {},
    warnings: []
  })
})

test('gear community template slot detail failure imports matched facts and preserves unresolved evidence', async () => {
  const detailRequests = []
  const resolveRequests = []
  const matchedGem = {
    id: 'row-gem-240892',
    optionKey: 'gem-240892',
    displayLabel: '+32 急速',
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { gem_id: '240892' }
  }
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '288881', id: '288881', variantKey: 'ring-v1',
    displayName: 'Observed Ring', ilevel: 707, bonus_id: '12345', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
  }
  const back = {
    slot: 'back', simcSlot: 'back', itemId: '288882', id: '288882', variantKey: 'back-v1',
    displayName: 'Observed Cloak', armorType: 'Cloth', ilevel: 707, bonus_id: '12345', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90, gearPayloadMode: 'initial',
    slots: [
      { slot: 'back', simcSlot: 'back', label: '披风' },
      { slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }
    ],
    equippedSet: {},
    replacementCandidates: [
      {
        slot: 'back', simcSlot: 'back', label: '披风', detailMode: 'partial', items: [back]
      },
      {
        slot: 'finger1', simcSlot: 'finger1', label: '戒指 1', detailMode: 'complete',
        items: [ring], socketOptions: [matchedGem]
      }
    ],
    slotReadiness: {}, readiness: { fullReady: true }, resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear(params) {
      detailRequests.push(params)
      return Promise.reject(new Error('slot detail unavailable'))
    },
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalResolveTransport(selectionIntent)
    }
  })
  const template = {
    id: 'observed-detail-failure', canApplyGear: true,
    gearItems: [
      { ...ring, gem_id: '240892' },
      { ...back, embellishment: 'arcanoweave_lining' }
    ]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: true }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })

  assert.deepEqual(detailRequests.map((params) => `${params.mode}:${params.slot}`), ['slot:back'])
  assert.equal(page.data.selectedGearBySlot.finger1.itemId, ring.itemId)
  assert.equal(page.data.selectedGearBySlot.back.itemId, back.itemId)
  assert.equal(page.data.selectedGearBySlot.finger1.gem_id, undefined)
  assert.equal(page.data.selectedGearBySlot.back.embellishment, undefined)
  assert.deepEqual(JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1.gemOptionIds)), ['gem-240892'])
  assert.equal(resolveRequests[0].slots.back.embellishmentOptionId, '')
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), {
    templateId: 'observed-detail-failure',
    serial: 1,
    resolvedGearSignature: 'sha256:test-resolved',
    unresolvedBySlot: {
      back: {
        gemIds: [],
        enchantIds: [],
        embellishments: ['arcanoweave_lining'],
        readOnly: true
      }
    },
    warnings: ['1 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。']
  })
})

test('community explicit gem identity mirrors preserve whole ordered multiplicity', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })

  const rawBySlot = pageConfig.__detailHelpers.communityTemplateRawEnhancementBySlot({
    enhancementBySlot: {
      finger1: { gemOptionIds: ['same-gem', 'same-gem'] }
    },
    payload: {
      enhancementBySlot: {
        finger1: { gemOptionIds: ['same-gem', 'same-gem'] }
      }
    }
  })

  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.finger1.gemOptionIds)), [
    'same-gem',
    'same-gem'
  ])
  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.finger1.gemOptionIdSequences)), [
    ['same-gem', 'same-gem']
  ])
  assert.equal(rawBySlot.finger1.gemOptionConflict, false)
})

test('community conflicting explicit gem identity sequences fail closed without concatenation', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const option = (optionKey, gemId, displayLabel) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { gem_id: gemId }
  })
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '288890', id: '288890', variantKey: 'explicit-conflict',
    displayName: 'Explicit Conflict Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring],
      socketOptions: [
        option('same-gem', '240892', '+32 急速'),
        option('other-gem', '240900', '+32 精通')
      ]
    }],
    resolverContext: canonicalTestResolverContext()
  }
  const rawBySlot = pageConfig.__detailHelpers.communityTemplateRawEnhancementBySlot({
    enhancementBySlot: {
      finger1: { gemOptionIds: ['same-gem', 'same-gem'] }
    },
    payload: {
      enhancementBySlot: {
        finger1: { gemOptionIds: ['same-gem', 'other-gem'] }
      }
    }
  })

  const reconciliation = pageConfig.__detailHelpers.reconcileCommunityTemplateEnhancements(
    gearPayload,
    { finger1: ring },
    rawBySlot
  )

  assert.equal(rawBySlot.finger1.gemOptionConflict, true)
  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.finger1.gemOptionIds)), [])
  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.finger1.gemOptionIdSequences)), [
    ['same-gem', 'same-gem'],
    ['same-gem', 'other-gem']
  ])
  assert.deepEqual(JSON.parse(JSON.stringify(reconciliation.enhancementBySlot)), {})
  assert.deepEqual(JSON.parse(JSON.stringify(reconciliation.unresolvedBySlot)), {
    finger1: {
      gemIds: ['same-gem', 'same-gem', 'same-gem', 'other-gem'],
      enchantIds: [],
      embellishments: [],
      readOnly: true
    }
  })
})

test('community explicit enchant and embellishment identities retain unknown and conflicting facts', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const helpers = pageConfig.__detailHelpers
  const item = (slot, canEnchant, canEmbellish) => ({
    slot,
    simcSlot: slot,
    itemId: `explicit-${slot}`,
    id: `explicit-${slot}`,
    displayName: `Explicit ${slot}`,
    armorType: 'Cloth',
    simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant, canEmbellish }
  })
  const items = {
    finger1: item('finger1', true, false),
    finger2: item('finger2', true, false),
    chest: item('chest', true, false),
    feet: item('feet', true, false),
    back: item('back', false, true),
    wrist: item('wrist', false, true),
    waist: item('waist', false, true),
    legs: item('legs', false, true)
  }
  const option = (type, optionKey) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel: type === 'enchant' ? `附魔 ${optionKey}` : `美化 ${optionKey}`,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: type === 'enchant'
      ? { enchant_id: `simc-${optionKey}` }
      : { embellishment: `simc-${optionKey}` },
    payload: { qualityRank: 2, slotGroup: 'armor' }
  })
  const candidates = {
    finger1: [option('enchant', 'known-enchant')],
    finger2: [option('enchant', 'conflict-enchant-a'), option('enchant', 'conflict-enchant-b')],
    chest: [option('enchant', 'matched-enchant')],
    feet: [option('enchant', 'single-matched-enchant')],
    back: [option('embellishment', 'known-embellishment')],
    wrist: [option('embellishment', 'conflict-embellishment-a'), option('embellishment', 'conflict-embellishment-b')],
    waist: [option('embellishment', 'matched-embellishment')],
    legs: [option('embellishment', 'single-matched-embellishment')]
  }
  const gearPayload = {
    slots: Object.keys(items).map((slot) => ({ slot, simcSlot: slot, label: slot })),
    replacementCandidates: Object.keys(items).map((slot) => ({
      slot,
      simcSlot: slot,
      detailMode: 'complete',
      items: [items[slot]],
      enchantOptions: ['finger1', 'finger2', 'chest', 'feet'].includes(slot) ? candidates[slot] : [],
      embellishmentOptions: ['back', 'wrist', 'waist', 'legs'].includes(slot) ? candidates[slot] : []
    }))
  }
  const rawBySlot = helpers.communityTemplateRawEnhancementBySlot({
    enhancementBySlot: {
      finger1: { enchantOptionId: 'unknown-enchant' },
      finger2: { enchantOptionId: 'conflict-enchant-a' },
      chest: { enchantOptionId: 'matched-enchant' },
      feet: { enchantOptionId: 'single-matched-enchant' },
      back: { embellishmentOptionId: 'unknown-embellishment' },
      wrist: { embellishmentOptionId: 'conflict-embellishment-a' },
      waist: { embellishmentOptionId: 'matched-embellishment' },
      legs: { embellishmentOptionId: 'single-matched-embellishment' }
    },
    payload: {
      enhancementBySlot: {
        finger2: { enchantOptionId: 'conflict-enchant-b' },
        chest: { enchantOptionId: 'matched-enchant' },
        wrist: { embellishmentOptionId: 'conflict-embellishment-b' },
        waist: { embellishmentOptionId: 'matched-embellishment' }
      }
    }
  })
  const reconciliation = helpers.reconcileCommunityTemplateEnhancements(
    gearPayload,
    items,
    rawBySlot
  )

  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.finger2.enchantOptionIdSequences)), [
    ['conflict-enchant-a'],
    ['conflict-enchant-b']
  ])
  assert.equal(rawBySlot.finger2.enchantOptionConflict, true)
  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.chest.enchantOptionIdSequences)), [
    ['matched-enchant']
  ])
  assert.equal(rawBySlot.chest.enchantOptionConflict, false)
  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.wrist.embellishmentOptionIdSequences)), [
    ['conflict-embellishment-a'],
    ['conflict-embellishment-b']
  ])
  assert.equal(rawBySlot.wrist.embellishmentOptionConflict, true)
  assert.deepEqual(JSON.parse(JSON.stringify(rawBySlot.waist.embellishmentOptionIdSequences)), [
    ['matched-embellishment']
  ])
  assert.equal(rawBySlot.waist.embellishmentOptionConflict, false)
  assert.deepEqual(JSON.parse(JSON.stringify(reconciliation.enhancementBySlot)), {
    chest: { enchantOptionId: 'matched-enchant' },
    feet: { enchantOptionId: 'single-matched-enchant' },
    waist: { embellishmentOptionId: 'matched-embellishment' },
    legs: { embellishmentOptionId: 'single-matched-embellishment' }
  })
  assert.deepEqual(JSON.parse(JSON.stringify(reconciliation.unresolvedBySlot)), {
    finger1: { gemIds: [], enchantIds: ['unknown-enchant'], embellishments: [], readOnly: true },
    finger2: {
      gemIds: [],
      enchantIds: ['conflict-enchant-a', 'conflict-enchant-b'],
      embellishments: [],
      readOnly: true
    },
    back: { gemIds: [], enchantIds: [], embellishments: ['unknown-embellishment'], readOnly: true },
    wrist: {
      gemIds: [],
      enchantIds: [],
      embellishments: ['conflict-embellishment-a', 'conflict-embellishment-b'],
      readOnly: true
    }
  })
})

test('community enhancement reconciliation preserves duplicate gem multiplicity in Resolve', async () => {
  const resolveRequests = []
  const pageConfig = loadBuildsDetailPageConfig({
    exposeDetailHelpers: true,
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalResolveTransport(selectionIntent)
    }
  })
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '288891', id: '288891', variantKey: 'ring-duplicate-gems',
    displayName: 'Duplicate Gem Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', label: '戒指 1', detailMode: 'complete', items: [ring],
      socketOptions: [{
        id: 'row-gem-240892',
        optionKey: 'gem-240892',
        displayLabel: '+32 急速',
        displayStatus: 'verified',
        evidenceSource: 'test_authority',
        status: 'verified',
        simcOptions: { gem_id: '240892' }
      }]
    }],
    resolverContext: canonicalTestResolverContext()
  }
  const rawBySlot = pageConfig.__detailHelpers.communityTemplateRawEnhancementBySlot({
    enhancementBySlot: { finger1: { gem_id: '240892/240892' } },
    gearItems: [{ ...ring, gem_id: '240892/240892' }],
    payload: {
      enhancementBySlot: { finger1: { gem_id: '240892/240892' } },
      gearItems: [{ ...ring, gem_id: '240892/240892' }]
    }
  })
  const reconciliation = pageConfig.__detailHelpers.reconcileCommunityTemplateEnhancements(
    gearPayload,
    { finger1: ring },
    rawBySlot
  )
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: { finger1: ring },
      enhancementBySlot: {}, gearEnhancementSheet: { visible: false }, gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  await pageConfig.confirmAndResolveGearIntent.call(
    page,
    { finger1: ring },
    reconciliation.enhancementBySlot
  )

  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1.gemOptionIds)),
    ['gem-240892', 'gem-240892']
  )
  assert.deepEqual(JSON.parse(JSON.stringify(reconciliation.unresolvedBySlot)), {})
})

test('duplicate gem community import survives unchanged enhancement editor confirmation', async () => {
  const resolveRequests = []
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '288892', id: '288892', variantKey: 'ring-duplicate-editor',
    displayName: 'Duplicate Gem Editor Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    equippedSet: {},
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', label: '戒指 1', detailMode: 'complete', items: [ring],
      socketOptions: [{
        id: 'row-gem-240892',
        optionKey: 'gem-240892',
        displayLabel: '+32 急速',
        displayStatus: 'verified',
        evidenceSource: 'test_authority',
        status: 'verified',
        simcOptions: { gem_id: '240892' }
      }]
    }],
    slotReadiness: {}, readiness: { fullReady: true }, resolverContext: canonicalTestResolverContext()
  }
  const template = {
    id: 'duplicate-gem-editor-template', canApplyGear: true, readySlotCount: 1,
    gearItems: [{ ...ring, gem_id: '240892/240892' }]
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        `sha256:duplicate-editor-${resolveRequests.length}`,
        { finger1: { socketCount: 2, canEnchant: false, canEmbellish: false } }
      )
    }
  })
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearEnhancementSheet: { visible: false }, gearSlotSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })

  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1.gemOptionIds)),
    ['gem-240892', 'gem-240892']
  )

  await pageConfig.openGearEnhancementSheet.call(page)

  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.enhancementBySlot.finger1.gemOptionIds)),
    ['gem-240892', 'gem-240892']
  )
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.gemOptionIds)),
    ['gem-240892', 'gem-240892']
  )
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.blockers)), [])
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '2/2')

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(resolveRequests.length, 2)
  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[1].slots.finger1.gemOptionIds)),
    ['gem-240892', 'gem-240892']
  )
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.enhancementBySlot.finger1.gemOptionIds)),
    ['gem-240892', 'gem-240892']
  )
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '2/2')
})

test('explicit duplicate gem community import stays two through Resolve and unchanged confirmation', async () => {
  const resolveRequests = []
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '288894', id: '288894', variantKey: 'explicit-duplicate-editor',
    displayName: 'Explicit Duplicate Gem Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: false, canEmbellish: false }
  }
  const sameGem = {
    id: 'row-same-gem',
    optionKey: 'same-gem',
    displayLabel: '+32 急速',
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { gem_id: '240892' }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    equippedSet: {},
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', label: '戒指 1', detailMode: 'complete',
      items: [ring], socketOptions: [sameGem]
    }],
    slotReadiness: {}, readiness: { fullReady: true }, resolverContext: canonicalTestResolverContext()
  }
  const template = {
    id: 'explicit-duplicate-editor-template', canApplyGear: true, readySlotCount: 1,
    gearItems: [ring],
    enhancementBySlot: {
      finger1: { gemOptionIds: ['same-gem', 'same-gem'] }
    },
    payload: {
      enhancementBySlot: {
        finger1: { gemOptionIds: ['same-gem', 'same-gem'] }
      }
    }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        `sha256:explicit-duplicate-${resolveRequests.length}`,
        { finger1: { socketCount: 2, canEnchant: false, canEmbellish: false } }
      )
    }
  })
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearEnhancementSheet: { visible: false }, gearSlotSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })

  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1.gemOptionIds)),
    ['same-gem', 'same-gem']
  )
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '2/2')

  pageConfig.openGearEnhancementSheet.call(page)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.gemOptionIds)),
    ['same-gem', 'same-gem']
  )
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.blockers)), [])

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(resolveRequests.length, 2)
  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[1].slots.finger1.gemOptionIds)),
    ['same-gem', 'same-gem']
  )
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.enhancementBySlot.finger1.gemOptionIds)),
    ['same-gem', 'same-gem']
  )
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem').value, '2/2')
})

test('community enhancement reconciliation keeps conflicting gem source sequences wholly unresolved', async () => {
  const resolveRequests = []
  const pageConfig = loadBuildsDetailPageConfig({
    exposeDetailHelpers: true,
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalResolveTransport(selectionIntent)
    }
  })
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '288893', id: '288893', variantKey: 'ring-conflicting-gems',
    displayName: 'Conflicting Gem Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: false, canEmbellish: false }
  }
  const option = (gemId) => ({
    id: `row-gem-${gemId}`,
    optionKey: `gem-${gemId}`,
    displayLabel: gemId === '240892' ? '+32 急速' : '+32 精通',
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { gem_id: gemId }
  })
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', label: '戒指 1', detailMode: 'complete', items: [ring],
      socketOptions: [option('240892'), option('240900')]
    }],
    resolverContext: canonicalTestResolverContext()
  }
  const rawBySlot = pageConfig.__detailHelpers.communityTemplateRawEnhancementBySlot({
    enhancementBySlot: { finger1: { gem_id: '240892/240892' } },
    gearItems: [{ ...ring, gem_id: '240900/240900' }],
    payload: {
      enhancementBySlot: { finger1: { gem_id: '240900/240900' } },
      gearItems: [{ ...ring, gem_id: '240900/240900' }]
    }
  })
  const reconciliation = pageConfig.__detailHelpers.reconcileCommunityTemplateEnhancements(
    gearPayload,
    { finger1: ring },
    rawBySlot
  )
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: { finger1: ring },
      enhancementBySlot: {}, gearEnhancementSheet: { visible: false }, gearSlotSheet: {},
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } }
  }

  await pageConfig.confirmAndResolveGearIntent.call(
    page,
    { finger1: ring },
    reconciliation.enhancementBySlot
  )

  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1.gemOptionIds)), [])
  assert.deepEqual(JSON.parse(JSON.stringify(reconciliation)), {
    enhancementBySlot: {},
    unresolvedBySlot: {
      finger1: {
        gemIds: ['240892', '240892', '240900', '240900'],
        enchantIds: [],
        embellishments: [],
        readOnly: true
      }
    },
    warnings: ['1 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。']
  })
})

test('community enhancement reconciliation requires affirmative trust fields and a genuine display label', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const helpers = pageConfig.__detailHelpers
  const items = {
    finger1: {
      slot: 'finger1', simcSlot: 'finger1', itemId: '288901', id: '288901', displayName: 'Untrusted Ring',
      modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
    },
    finger2: {
      slot: 'finger2', simcSlot: 'finger2', itemId: '288902', id: '288902', displayName: 'Raw Label Ring',
      modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
    },
    neck: {
      slot: 'neck', simcSlot: 'neck', itemId: '288903', id: '288903', displayName: 'Wrong Rank Neck',
      modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
    },
    wrist: {
      slot: 'wrist', simcSlot: 'wrist', itemId: '288904', id: '288904', displayName: 'Raw Value Wrist',
      modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
    }
  }
  const rawBySlot = helpers.communityTemplateRawEnhancementBySlot({
    gearItems: [
      { ...items.finger1, gem_id: '240899' },
      { ...items.finger2, gem_id: '240900' },
      { ...items.neck, gem_id: '240901' },
      { ...items.wrist, gem_id: '240902' }
    ]
  })
  const result = helpers.reconcileCommunityTemplateEnhancements({
    replacementCandidates: [
      {
        slot: 'finger1', detailMode: 'complete', items: [items.finger1],
        socketOptions: [{
          id: 'missing-trust-gem-row', optionKey: 'gem-missing-trust',
          displayLabel: '+32 全能', evidenceSource: 'test_authority',
          simcOptions: { gem_id: '240899' }
        }]
      },
      {
        slot: 'finger2', detailMode: 'complete', items: [items.finger2],
        socketOptions: [{
          id: 'raw-label-gem-row', optionKey: 'gem-raw-label',
          displayLabel: '宝石 240900', displayStatus: 'verified', status: 'verified',
          evidenceSource: 'test_authority', simcOptions: { gem_id: '240900' }
        }]
      },
      {
        slot: 'neck', detailMode: 'complete', items: [items.neck],
        socketOptions: [{
          id: 'wrong-rank-gem-row', optionKey: 'gem-wrong-rank', qualityRank: 1,
          displayLabel: '+32 急速', displayStatus: 'verified', status: 'verified',
          evidenceSource: 'test_authority', simcOptions: { gem_id: '240901' }
        }]
      },
      {
        slot: 'wrist', detailMode: 'complete', items: [items.wrist],
        socketOptions: [{
          id: 'raw-value-gem-row', optionKey: 'gem-raw-value',
          displayLabel: '240-902', displayStatus: 'verified', status: 'verified',
          evidenceSource: 'test_authority', simcOptions: { gem_id: '240902' }
        }]
      }
    ]
  }, items, rawBySlot)

  assert.deepEqual(JSON.parse(JSON.stringify(result)), {
    enhancementBySlot: {},
    unresolvedBySlot: {
      finger1: { gemIds: ['240899'], enchantIds: [], embellishments: [], readOnly: true },
      finger2: { gemIds: ['240900'], enchantIds: [], embellishments: [], readOnly: true },
      neck: { gemIds: ['240901'], enchantIds: [], embellishments: [], readOnly: true },
      wrist: { gemIds: ['240902'], enchantIds: [], embellishments: [], readOnly: true }
    },
    warnings: ['4 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。']
  })
})

test('community enhancement reconciliation rejects options inapplicable to the current item capability', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const helpers = pageConfig.__detailHelpers
  const selectedChest = {
    slot: 'chest',
    simcSlot: 'chest',
    itemId: '299991',
    id: '299991',
    displayName: 'Unenchantable Chest',
    modCapabilities: { canEnchant: false }
  }
  const rawBySlot = helpers.communityTemplateRawEnhancementBySlot({
    gearItems: [{ ...selectedChest, enchant_id: '7967' }]
  })
  const result = helpers.reconcileCommunityTemplateEnhancements({
    slots: [{ slot: 'chest', simcSlot: 'chest', label: '胸部' }],
    replacementCandidates: [{
      slot: 'chest',
      simcSlot: 'chest',
      detailMode: 'complete',
      items: [selectedChest],
      enchantOptions: [{
        id: 'row-chest-enchant',
        optionKey: 'chest-enchant-7967',
        displayLabel: '胸部附魔',
        displayStatus: 'verified',
        evidenceSource: 'test_authority',
        status: 'verified',
        simcOptions: { enchant_id: '7967' },
        payload: { qualityRank: 2 }
      }]
    }]
  }, { chest: selectedChest }, rawBySlot)

  assert.deepEqual(JSON.parse(JSON.stringify(result)), {
    enhancementBySlot: {},
    unresolvedBySlot: {
      chest: { gemIds: [], enchantIds: ['7967'], embellishments: [], readOnly: true }
    },
    warnings: ['1 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。']
  })
})

test('community enhancement reconciliation keeps hidden unreadable unstable and wrong-slot facts unresolved', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const helpers = pageConfig.__detailHelpers
  const items = {
    neck: {
      slot: 'neck', simcSlot: 'neck', itemId: '299981', displayName: 'Socket Neck',
      modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
    },
    chest: {
      slot: 'chest', simcSlot: 'chest', itemId: '299982', displayName: 'Enchant Chest',
      modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: true, canEmbellish: false }
    },
    back: {
      slot: 'back', simcSlot: 'back', itemId: '299983', displayName: 'Embellish Cloak', armorType: 'Cloth',
      modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
    },
    finger1: {
      slot: 'finger1', simcSlot: 'finger1', itemId: '299984', displayName: 'Enchant Ring',
      modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: true, canEmbellish: false }
    }
  }
  const rawBySlot = helpers.communityTemplateRawEnhancementBySlot({
    gearItems: [
      { ...items.neck, gem_id: '240892' },
      { ...items.chest, enchant_id: '7967' },
      { ...items.back, embellishment: 'arcanoweave_lining' },
      { ...items.finger1, enchant_id: '7997' }
    ]
  })
  const result = helpers.reconcileCommunityTemplateEnhancements({
    replacementCandidates: [
      {
        slot: 'neck', detailMode: 'complete', items: [items.neck],
        socketOptions: [{
          id: 'hidden-gem-row', optionKey: 'gem-hidden', isVisible: false,
          displayLabel: '+32 急速', displayStatus: 'verified', status: 'verified',
          simcOptions: { gem_id: '240892' }, payload: { qualityRank: 2 }
        }]
      },
      {
        slot: 'chest', detailMode: 'complete', items: [items.chest],
        enchantOptions: [{
          id: 'unreadable-enchant-row', optionKey: 'enchant-unreadable',
          displayStatus: 'verified', status: 'verified',
          simcOptions: { enchant_id: '7967' }, payload: { qualityRank: 2 }
        }]
      },
      {
        slot: 'back', detailMode: 'complete', items: [items.back],
        embellishmentOptions: [{
          id: 'arcanoweave_lining',
          displayLabel: '奥纹内衬', displayStatus: 'verified', status: 'verified', slotGroup: 'armor',
          simcOptions: { embellishment: 'arcanoweave_lining' }, payload: { qualityRank: 2 }
        }]
      },
      {
        slot: 'finger1', detailMode: 'complete', items: [items.finger1],
        enchantOptions: [{
          id: 'wrong-slot-enchant-row', optionKey: 'ring-enchant-wrong-slot', applicableSlots: ['neck'],
          displayLabel: '戒指附魔', displayStatus: 'verified', status: 'verified',
          simcOptions: { enchant_id: '7997' }, payload: { qualityRank: 2 }
        }]
      }
    ]
  }, items, rawBySlot)

  assert.deepEqual(JSON.parse(JSON.stringify(result)), {
    enhancementBySlot: {},
    unresolvedBySlot: {
      neck: { gemIds: ['240892'], enchantIds: [], embellishments: [], readOnly: true },
      chest: { gemIds: [], enchantIds: ['7967'], embellishments: [], readOnly: true },
      back: { gemIds: [], enchantIds: [], embellishments: ['arcanoweave_lining'], readOnly: true },
      finger1: { gemIds: [], enchantIds: ['7997'], embellishments: [], readOnly: true }
    },
    warnings: ['4 个槽位的社区强化缺少当前可编辑证据，已按只读事实保留。']
  })
})

test('slower community enhancement hydration cannot overwrite a newer community import', async () => {
  const detailRequests = []
  const resolveRequests = []
  let finishOlderDetail
  let finishNewerDetail
  const olderRing = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299971', id: '299971', variantKey: 'older-ring',
    displayName: 'Older Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
  }
  const newerRing = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299972', id: '299972', variantKey: 'newer-ring',
    displayName: 'Newer Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: false, canEmbellish: false }
  }
  const compactGemOption = (optionKey, gemId, displayLabel) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { gem_id: gemId }
  })
  const detailResponse = (label, items, option) => ({
    fromFallback: false,
    error: '',
    payload: {
      replacementCandidates: [{
        slot: 'finger1',
        simcSlot: 'finger1',
        label,
        detailMode: 'complete',
        items,
        socketOptions: [option]
      }]
    }
  })
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90, gearPayloadMode: 'initial',
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    equippedSet: {},
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', label: 'initial', detailMode: 'partial',
      items: [olderRing, newerRing]
    }],
    slotReadiness: {}, readiness: { fullReady: true }, resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGear(params) {
      detailRequests.push(params)
      return new Promise((resolve) => {
        if (detailRequests.length === 1) {
          finishOlderDetail = () => resolve(detailResponse(
            'stale older detail',
            [olderRing],
            compactGemOption('older-gem', '240892', '+32 急速')
          ))
        } else {
          finishNewerDetail = () => resolve(detailResponse(
            'newer detail',
            [olderRing, newerRing],
            compactGemOption('newer-gem', '240900', '+32 精通')
          ))
        }
      })
    },
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalResolveTransport(selectionIntent)
    }
  })
  const olderTemplate = {
    id: 'older-import', canApplyGear: true, gearItems: [{ ...olderRing, gem_id: '240892' }]
  }
  const newerTemplate = {
    id: 'newer-import', canApplyGear: true, gearItems: [{ ...newerRing, gem_id: '240900' }]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [olderTemplate, newerTemplate],
      gearCommunityTemplateSheet: { visible: true }, gearSlotSheet: { visible: false },
      gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  const olderImport = pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: olderTemplate.id } }
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(detailRequests.map((params) => `${params.mode}:${params.slot}`), ['slot:finger1'])

  const newerImport = pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: newerTemplate.id } }
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(
    detailRequests.map((params) => `${params.mode}:${params.slot}`),
    ['slot:finger1', 'slot:finger1']
  )
  finishNewerDetail()
  await newerImport

  assert.equal(page.data.selectedGearBySlot.finger1.itemId, newerRing.itemId)
  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[0].slots.finger1.gemOptionIds)),
    ['newer-gem']
  )
  const cacheAfterNewerImport = JSON.parse(JSON.stringify(page.gearPayloadCache))
  const payloadAfterNewerImport = JSON.parse(JSON.stringify(page.data.gearPayload))
  const selectionAfterNewerImport = JSON.parse(JSON.stringify(page.data.selectedGearBySlot))
  const evidenceAfterNewerImport = JSON.parse(JSON.stringify(page.communityEnhancementImportState))

  finishOlderDetail()
  await olderImport

  assert.deepEqual(JSON.parse(JSON.stringify(page.gearPayloadCache)), cacheAfterNewerImport)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearPayload)), payloadAfterNewerImport)
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.selectedGearBySlot)), selectionAfterNewerImport)
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), evidenceAfterNewerImport)
  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), {
    templateId: 'newer-import',
    serial: 2,
    resolvedGearSignature: 'sha256:test-resolved',
    unresolvedBySlot: {},
    warnings: []
  })
})

test('multiple gem option identities preserve ordered multiplicity and legacy scalar reads', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const helpers = pageConfig.__detailHelpers

  const normalized = helpers.normalizedEnhancementBySlot({
    neck: {
      gemOptionIds: ['gem-first', ' gem-second ', 'gem-first', '', null]
    },
    finger1: {
      socketOptionId: 'legacy-gem'
    }
  })

  assert.deepEqual(JSON.parse(JSON.stringify(normalized)), {
    neck: {
      gemOptionIds: ['gem-first', 'gem-second', 'gem-first']
    },
    finger1: {
      socketOptionId: 'legacy-gem'
    }
  })
  assert.deepEqual(JSON.parse(JSON.stringify(helpers.optionIdentityEnhancementBySlot(normalized))), {
    neck: {
      gemOptionIds: ['gem-first', 'gem-second', 'gem-first']
    },
    finger1: {
      socketOptionId: 'legacy-gem'
    }
  })
  assert.deepEqual(JSON.parse(JSON.stringify(helpers.compactEnhancementRecord(normalized.neck))), {
    gemOptionIds: ['gem-first', 'gem-second', 'gem-first']
  })
  assert.equal(helpers.enhancementRecordSelectedCount(normalized.neck, 'gem'), 3)
  assert.equal(helpers.enhancementOptionSelected({ id: 'gem-second' }, normalized.neck, 'gem'), true)
  assert.equal(helpers.enhancementRecordSelectedCount(normalized.finger1, 'gem'), 1)
  assert.equal(helpers.enhancementOptionSelected({ id: 'legacy-gem' }, normalized.finger1, 'gem'), true)
})

test('gem option identity array overrides legacy scalar and raw fallbacks', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const helpers = pageConfig.__detailHelpers
  const selected = {
    gemOptionIds: ['canonical-gem'],
    socketOptionId: 'legacy-gem',
    gem_id: '240908'
  }

  assert.equal(helpers.enhancementOptionSelected({ id: 'canonical-gem' }, selected, 'gem'), true)
  assert.equal(helpers.enhancementOptionSelected({ id: 'legacy-gem' }, selected, 'gem'), false)
  assert.equal(helpers.enhancementOptionSelected({ id: 'raw-gem', simcOptions: { gem_id: '240908' } }, selected, 'gem'), false)
})

function embellishmentLimitBuilderFixture() {
  const slots = ['back', 'chest', 'wrist']
  const selectedGearBySlot = {}
  const replacementCandidates = slots.map((slot, index) => {
    const item = {
      slot, simcSlot: slot, itemId: `39900${index}`, id: `39900${index}`,
      displayName: `Canonical Embellishment ${slot}`, armorType: 'Cloth', simcReady: true,
      modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
    }
    const option = {
      id: `embellishment-${slot}`,
      displayLabel: `美化 ${slot}`,
      displayStatus: 'verified',
      evidenceSource: 'test_authority',
      status: 'verified',
      simcOptions: { embellishment: `embellishment_${slot}` },
      payload: { qualityRank: 2, slotGroup: 'armor' }
    }
    selectedGearBySlot[slot] = item
    return {
      slot, simcSlot: slot, detailMode: 'complete', items: [item],
      embellishmentOptions: [option]
    }
  })
  return {
    gearPayload: {
      classKey: 'mage', specKey: 'frost', maxLevel: 90,
      slots: slots.map((slot) => ({ slot, simcSlot: slot, label: slot })),
      replacementCandidates,
      resolverContext: canonicalTestResolverContext()
    },
    selectedGearBySlot
  }
}

test('enhancement sheet construction applies canonical embellishment max zero one and three', () => {
  const pageConfig = loadBuildsDetailPageConfig({ exposeDetailHelpers: true })
  const { gearPayload, selectedGearBySlot } = embellishmentLimitBuilderFixture()
  const buildSheet = pageConfig.__detailHelpers.buildGearEnhancementSheet
  const selected = (slots) => Object.fromEntries(slots.map((slot) => [slot, {
    embellishmentOptionId: `embellishment-${slot}`
  }]))

  const maxZero = buildSheet(gearPayload, selectedGearBySlot, {}, true, 'back', 0)
  assert.equal(maxZero.embellishmentMax, 0)
  assert.equal(maxZero.embellishmentUsed, 0)
  assert.equal(maxZero.embellishmentRows.every((row) => row.options.every((option) => option.disabled)), true)
  assert.deepEqual(JSON.parse(JSON.stringify(maxZero.blockers)), [])

  const maxOne = buildSheet(gearPayload, selectedGearBySlot, selected(['back']), true, 'back', 1)
  assert.equal(maxOne.embellishmentMax, 1)
  assert.equal(maxOne.embellishmentUsed, 1)
  assert.equal(maxOne.embellishmentRows.find((row) => row.slot === 'chest').options[0].disabled, true)
  const maxOneOverflow = buildSheet(gearPayload, selectedGearBySlot, selected(['back', 'chest']), true, 'back', 1)
  assert.ok(maxOneOverflow.blockers.includes('美化已超过上限 2/1'))

  const maxThree = buildSheet(gearPayload, selectedGearBySlot, selected(['back', 'chest']), true, 'back', 3)
  assert.equal(maxThree.embellishmentMax, 3)
  assert.equal(maxThree.embellishmentUsed, 2)
  assert.equal(maxThree.embellishmentRows.find((row) => row.slot === 'wrist').options[0].disabled, false)
  assert.deepEqual(JSON.parse(JSON.stringify(maxThree.blockers)), [])

  const legacy = buildSheet(gearPayload, selectedGearBySlot, selected(['back', 'chest', 'wrist']), true, 'back')
  assert.equal(legacy.embellishmentMax, 2)
  assert.ok(legacy.blockers.includes('美化已超过上限 3/2'))
})

function canonicalEmbellishmentLimitPageHarness(embellishmentMax, selectedSlots = []) {
  const { gearPayload, selectedGearBySlot } = embellishmentLimitBuilderFixture()
  const toasts = []
  const resolveRequests = []
  const constraintsBySlot = Object.fromEntries(Object.keys(selectedGearBySlot).map((slot) => [slot, {
    socketCount: 0, canEnchant: false, canEmbellish: true
  }]))
  const enhancementBySlot = Object.fromEntries(selectedSlots.map((slot) => [slot, {
    embellishmentOptionId: `embellishment-${slot}`
  }]))
  const resolvedSlots = Object.fromEntries(Object.keys(selectedGearBySlot).map((slot) => [slot, {
    itemLevel: 707,
    selectedOptions: {
      gemOptionIds: [],
      enchantOptionId: '',
      embellishmentOptionId: selectedSlots.includes(slot) ? `embellishment-${slot}` : ''
    }
  }]))
  const snapshot = {
    status: 'verified',
    resolvedGearSignature: `sha256:embellishment-max-${embellishmentMax}`,
    dependencyVector: {},
    staticAttributes: {},
    setState: { itemSetCounts: {}, activeDynamicEffects: [] },
    aggregateLegality: { status: 'verified', problemCodes: [] },
    profileReadiness: { status: 'verified', simcReady: true },
    constraints: { embellishmentMax, slots: constraintsBySlot },
    resolvedSlots
  }
  const pageConfig = loadBuildsDetailPageConfig({
    toasts,
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        `${snapshot.resolvedGearSignature}-resolved-${resolveRequests.length}`,
        constraintsBySlot,
        embellishmentMax
      )
    }
  })
  const workbenchState = require('../pages/builds/gear-workbench-state').createGearWorkbenchState(
    gearPayload.resolverContext,
    {}
  )
  Object.assign(workbenchState, {
    resolveStatus: 'verified',
    currentSnapshot: snapshot,
    lastVerifiedSnapshot: snapshot
  })
  const page = {
    gearPayloadCache: gearPayload,
    gearWorkbenchState: workbenchState,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearPayload, selectedGearBySlot, enhancementBySlot,
      gearEnhancementSheet: { visible: false }, gearSlotSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }
  return { pageConfig, page, toasts, resolveRequests }
}

test('canonical workbench without an accepted snapshot fails embellishments closed while legacy stays at two', async () => {
  const canonical = canonicalEmbellishmentLimitPageHarness(2)
  canonical.page.data.selectedGearBySlot.back.sourceType = 'crafted'
  canonical.page.gearWorkbenchState.currentSnapshot = null
  canonical.page.gearWorkbenchState.lastVerifiedSnapshot = null

  canonical.pageConfig.openGearEnhancementSheet.call(canonical.page)

  const canonicalSheet = canonical.page.data.gearEnhancementSheet
  assert.equal(canonicalSheet.embellishmentMax, 0)
  assert.equal(canonicalSheet.embellishmentRows[0].options[0].disabled, true)
  canonicalSheet.draftEnhancementBySlot = {
    back: { embellishmentOptionId: 'embellishment-back' }
  }

  await canonical.pageConfig.confirmGearEnhancementSheet.call(canonical.page)

  assert.equal(canonical.resolveRequests.length, 0)
  assert.ok(canonical.page.data.gearEnhancementSheet.blockers.includes('美化已超过上限 1/0'))

  const legacy = canonicalEmbellishmentLimitPageHarness(2)
  delete legacy.page.gearWorkbenchState
  legacy.pageConfig.openGearEnhancementSheet.call(legacy.page)

  assert.equal(legacy.page.data.gearEnhancementSheet.embellishmentMax, 2)
  assert.equal(legacy.page.data.gearEnhancementSheet.embellishmentRows[0].options[0].disabled, false)
})

test('canonical embellishment max zero and one block over-limit confirmation', async () => {
  for (const [embellishmentMax, selectedSlots, overflowSlot] of [
    [0, [], 'back'],
    [1, ['back'], 'chest']
  ]) {
    const { pageConfig, page, toasts, resolveRequests } = canonicalEmbellishmentLimitPageHarness(
      embellishmentMax,
      selectedSlots
    )
    pageConfig.openGearEnhancementSheet.call(page)
    const overflowOption = page.data.gearEnhancementSheet.embellishmentRows
      .find((row) => row.slot === overflowSlot).options[0]
    assert.equal(page.data.gearEnhancementSheet.embellishmentMax, embellishmentMax)
    assert.equal(overflowOption.disabled, true)
    page.data.gearEnhancementSheet.draftEnhancementBySlot = {
      ...page.data.gearEnhancementSheet.draftEnhancementBySlot,
      [overflowSlot]: { embellishmentOptionId: `embellishment-${overflowSlot}` }
    }

    await pageConfig.confirmGearEnhancementSheet.call(page)

    assert.equal(resolveRequests.length, 0)
    assert.ok(page.data.gearEnhancementSheet.blockers.includes(
      `美化已超过上限 ${selectedSlots.length + 1}/${embellishmentMax}`
    ))
    assert.match(toasts.at(-1).title, new RegExp(`${selectedSlots.length + 1}/${embellishmentMax}`))
  }
})

test('canonical embellishment max three allows a third option through confirmation', async () => {
  const { pageConfig, page, toasts, resolveRequests } = canonicalEmbellishmentLimitPageHarness(
    3,
    ['back', 'chest']
  )
  pageConfig.openGearEnhancementSheet.call(page)
  const thirdOption = page.data.gearEnhancementSheet.embellishmentRows
    .find((row) => row.slot === 'wrist').options[0]
  assert.equal(page.data.gearEnhancementSheet.embellishmentMax, 3)
  assert.equal(thirdOption.disabled, false)

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'wrist', type: 'embellishment', id: 'embellishment-wrist' } }
  })
  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(toasts.length, 0)
  assert.equal(resolveRequests.length, 1)
  assert.equal(resolveRequests[0].slots.back.embellishmentOptionId, 'embellishment-back')
  assert.equal(resolveRequests[0].slots.chest.embellishmentOptionId, 'embellishment-chest')
  assert.equal(resolveRequests[0].slots.wrist.embellishmentOptionId, 'embellishment-wrist')
  assert.equal(page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'embellishment').value, '3/3')
})

function multiGemEditorHarness({
  socketCount = 2,
  enhancementBySlot = {},
  optionIds = ['gem-first', 'gem-second', 'gem-third'],
  optionPayloadById = {},
  captureResolve = false,
  exposeDetailHelpers = false
} = {}) {
  const toasts = []
  const resolveRequests = []
  const pageConfig = loadBuildsDetailPageConfig({
    toasts,
    exposeDetailHelpers,
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalResolveTransport(selectionIntent)
    }
  })
  const socketOptions = optionIds.map((id, index) => ({
    id,
    displayLabel: `宝石 ${index + 1}`,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { gem_id: String(240901 + index) },
    payload: { qualityRank: 2, ...(optionPayloadById[id] || {}) }
  }))
  const selectedNeck = {
    slot: 'neck',
    simcSlot: 'neck',
    itemId: '299001',
    id: '299001',
    displayName: 'Canonical Socket Neck',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 3, canEnchant: false, canEmbellish: false },
    socketOptions
  }
  const gearPayload = {
    classKey: 'mage',
    specKey: 'frost',
    maxLevel: 90,
    slots: [{ slot: 'neck', simcSlot: 'neck', label: '项链' }],
    equippedSet: {},
    replacementCandidates: [{
      slot: 'neck',
      simcSlot: 'neck',
      label: '项链',
      items: [selectedNeck],
      socketOptions
    }],
    slotReadiness: {},
    readiness: { fullReady: true },
    resolverContext: canonicalTestResolverContext()
  }
  const page = {
    gearPayloadCache: gearPayload,
    gearWorkbenchState: {
      resolveStatus: 'verified',
      activeRequest: null,
      offline: false,
      readOnly: false,
      currentSnapshot: {
        status: 'verified',
        resolvedGearSignature: 'sha256:multi-gem-editor',
        constraints: {
          embellishmentMax: 2,
          slots: {
            neck: { socketCount, canEnchant: false, canEmbellish: false }
          }
        },
        resolvedSlots: {
          neck: {
            selectedOptions: {
              gemOptionIds: Array.isArray(enhancementBySlot.neck && enhancementBySlot.neck.gemOptionIds)
                ? [...enhancementBySlot.neck.gemOptionIds]
                : []
            }
          }
        }
      }
    },
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      gearPayload,
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      selectedGearBySlot: { neck: selectedNeck },
      enhancementBySlot,
      gearEnhancementSheet: { visible: false },
      gearSlotSheet: { visible: false },
      gearCommunityTemplateSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }
  if (captureResolve) page.confirmAndResolveGearIntent = pageConfig.confirmAndResolveGearIntent
  return { pageConfig, page, toasts, resolveRequests }
}

test('duplicate unique gem occurrences block confirmation without resolving', async () => {
  const { pageConfig, page, toasts, resolveRequests } = multiGemEditorHarness({
    socketCount: 2,
    enhancementBySlot: { neck: { gemOptionIds: ['primary-gem', 'primary-gem'] } },
    optionIds: ['primary-gem'],
    optionPayloadById: {
      'primary-gem': { uniqueGroup: 'primary_stat_gem', uniqueLimit: 1 }
    },
    captureResolve: true
  })

  pageConfig.openGearEnhancementSheet.call(page)

  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)),
    ['primary-gem', 'primary-gem']
  )
  const blockersBeforeConfirm = [...page.data.gearEnhancementSheet.blockers]

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.ok(blockersBeforeConfirm.includes('主属性宝石已超过上限 2/1'))
  assert.ok(page.data.gearEnhancementSheet.blockers.includes('主属性宝石已超过上限 2/1'))
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)),
    ['primary-gem', 'primary-gem']
  )
  assert.match(toasts.at(-1).title, /主属性宝石已超过上限 2\/1/)
  assert.equal(resolveRequests.length, 0)
})

test('gem option toggles preserve two identities and stop at canonical socket capacity', () => {
  const { pageConfig, page } = multiGemEditorHarness({ socketCount: 2 })
  pageConfig.openGearEnhancementSheet.call(page)

  ;['gem-first', 'gem-second'].forEach((id) => {
    pageConfig.selectGearEnhancementOption.call(page, {
      currentTarget: { dataset: { slot: 'neck', type: 'gem', id } }
    })
  })

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot)), {
    neck: { gemOptionIds: ['gem-first', 'gem-second'] }
  })
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options.find((option) => option.id === 'gem-first').selected, true)
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options.find((option) => option.id === 'gem-second').selected, true)
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options.find((option) => option.id === 'gem-third').disabled, true)

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'neck', type: 'gem', id: 'gem-third' } }
  })
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)), ['gem-first', 'gem-second'])
})

test('gem option toggle removes only the selected identity', () => {
  const { pageConfig, page } = multiGemEditorHarness({
    socketCount: 2,
    enhancementBySlot: { neck: { gemOptionIds: ['gem-first', 'gem-second'] } }
  })
  pageConfig.openGearEnhancementSheet.call(page)

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'neck', type: 'gem', id: 'gem-first' } }
  })

  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot)), {
    neck: { gemOptionIds: ['gem-second'] }
  })
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options.find((option) => option.id === 'gem-first').selected, false)
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options.find((option) => option.id === 'gem-second').selected, true)
})

test('gem option capacity overflow blocks confirmation without truncating identities', () => {
  const { pageConfig, page, toasts } = multiGemEditorHarness({
    socketCount: 2,
    enhancementBySlot: { neck: { gemOptionIds: ['gem-first', 'gem-second', 'gem-third'] } }
  })
  pageConfig.openGearEnhancementSheet.call(page)

  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)),
    ['gem-first', 'gem-second', 'gem-third']
  )
  assert.match(page.data.gearEnhancementSheet.blockers.join('；'), /宝石已超过插槽上限 3\/2/)

  pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)),
    ['gem-first', 'gem-second', 'gem-third']
  )
  assert.match(toasts.at(-1).title, /宝石已超过插槽上限 3\/2/)
})

test('gem option draft without surviving option rows blocks before pruning or Resolve', async () => {
  const { pageConfig, page, toasts, resolveRequests } = multiGemEditorHarness({
    socketCount: 0,
    optionIds: [],
    captureResolve: true
  })
  page.data.gearEnhancementSheet = {
    ...page.data.gearEnhancementSheet,
    visible: true,
    activeSlot: 'neck',
    draftEnhancementBySlot: {
      neck: { gemOptionIds: ['orphaned-gem'] }
    }
  }

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)),
    ['orphaned-gem']
  )
  assert.match(page.data.gearEnhancementSheet.blockers.join('；'), /宝石/)
  assert.match(toasts.at(-1).title, /宝石/)
  assert.equal(resolveRequests.length, 0)
})

test('gem option mixed matched and unmatched identities stay local and never reach Resolve', async () => {
  const { pageConfig, page, toasts, resolveRequests } = multiGemEditorHarness({
    socketCount: 2,
    optionIds: ['verified-gem'],
    captureResolve: true
  })
  page.data.gearEnhancementSheet = {
    ...page.data.gearEnhancementSheet,
    visible: true,
    activeSlot: 'neck',
    draftEnhancementBySlot: {
      neck: { gemOptionIds: ['verified-gem', '240908'] }
    }
  }

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.visible, true)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.draftEnhancementBySlot.neck.gemOptionIds)),
    ['verified-gem', '240908']
  )
  assert.match(page.data.gearEnhancementSheet.blockers.join('；'), /240908/)
  assert.match(toasts.at(-1).title, /240908/)
  assert.equal(resolveRequests.length, 0)
})

test('gem option pruning removes unmatched identities before direct Resolve entry', async () => {
  const { pageConfig, page, resolveRequests } = multiGemEditorHarness({
    socketCount: 2,
    optionIds: ['verified-gem'],
    captureResolve: true,
    exposeDetailHelpers: true
  })
  const prunedEnhancementBySlot = pageConfig.__detailHelpers.prunedEnhancementBySlot(
    page.data.gearPayload,
    page.data.selectedGearBySlot,
    { neck: { gemOptionIds: ['verified-gem', '240908'] } }
  )

  await page.confirmAndResolveGearIntent(page.data.selectedGearBySlot, prunedEnhancementBySlot)

  assert.equal(resolveRequests.length, 1)
  assert.deepEqual(
    JSON.parse(JSON.stringify(resolveRequests[0].slots.neck.gemOptionIds)),
    ['verified-gem']
  )
})

test('gear enhancement sheet renders verified label-only payload options', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const selectedRing = {
    slot: 'finger1',
    simcSlot: 'finger1',
    itemId: '277777',
    id: '277777',
    displayName: 'Verified Ring',
    ilevel: 707,
    bonus_id: '12345',
    simcReady: true,
    sourceType: 'observed_profile',
    modCapabilities: { hasSocket: true, canEnchant: true, canEmbellish: true, socketCount: 1 }
  }
  const page = {
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'hunter', websimSpecKey: 'beastmastery' },
      gearPayload: {
        slots: [{ slot: 'finger1', simcSlot: 'finger1', label: 'Ring 1' }],
        equippedSet: {},
        replacementCandidates: [{
          slot: 'finger1',
          simcSlot: 'finger1',
          label: 'Ring 1',
          items: [selectedRing],
          socketOptions: [{
            id: 'gem-label-only',
            label: '+23 Primary Stat +13 Armor',
            name: '+23 Primary Stat +13 Armor',
            status: 'verified',
            simcOptions: { gem_id: '240971' }
          }],
          enchantOptions: [{
            id: 'enchant-label-only',
            label: 'Observed enchant 7967',
            name: 'Observed enchant 7967',
            status: 'verified',
            simcOptions: { enchant_id: '7967' }
          }],
          embellishmentOptions: [{
            id: 'embellishment-label-only',
            label: '\u5723\u4f51\u7a7f\u5c71\u7532\u62a4\u7b26',
            name: '\u5723\u4f51\u7a7f\u5c71\u7532\u62a4\u7b26',
            status: 'verified',
            simcOptions: { embellishment: 'blessed_pango_charm' }
          }]
        }],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: { finger1: selectedRing },
      enhancementBySlot: {},
      gearEnhancementSheet: { visible: false }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }
  page.gearPayloadCache = page.data.gearPayload

  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.emptyText, '')
  assert.equal(page.data.gearEnhancementSheet.activeSlot, 'finger1')
  assert.equal(page.data.gearEnhancementSheet.activeGemRows.length, 1)
  assert.equal(page.data.gearEnhancementSheet.activeGemRows[0].options[0].label, '+23 Primary Stat +13 Armor')
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows.length, 1)
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].label, '\u9644\u9b54 7967')
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows.length, 1)
  assert.equal(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options[0].label, '\u5723\u4f51\u7a7f\u5c71\u7532\u62a4\u7b26')
})

test('successful community Resolve renders canonical enhancement counts and selected options', async () => {
  const verifiedOption = (optionKey, simcKey, value, displayLabel, extra = {}) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { [simcKey]: value },
    payload: { qualityRank: 2 },
    ...extra
  })
  const gemOne = verifiedOption('gem-one', 'gem_id', '240892', '+32 急速')
  const gemTwo = verifiedOption('gem-two', 'gem_id', '240900', '+32 精通')
  const enchant = verifiedOption('ring-enchant', 'enchant_id', '7967', '苍穹全能')
  const embellishment = verifiedOption(
    'cloak-embellishment',
    'embellishment',
    'arcanoweave_lining',
    '奥纹内衬',
    { slotGroup: 'armor' }
  )
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299981', id: '299981', variantKey: 'ring-canonical',
    displayName: 'Canonical Community Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: true, canEmbellish: false }
  }
  const back = {
    slot: 'back', simcSlot: 'back', itemId: '299982', id: '299982', variantKey: 'back-canonical',
    displayName: 'Canonical Community Cloak', armorType: 'Cloth', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [
      { slot: 'back', simcSlot: 'back', label: '披风' },
      { slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }
    ],
    replacementCandidates: [
      {
        slot: 'back', simcSlot: 'back', detailMode: 'complete', items: [back],
        embellishmentOptions: [embellishment]
      },
      {
        slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring],
        socketOptions: [gemOne, gemTwo], enchantOptions: [enchant]
      }
    ],
    resolverContext: canonicalTestResolverContext()
  }
  const signature = 'sha256:canonical-enhancements'
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return Promise.resolve({
        httpStatus: 200,
        fromFallback: false,
        payload: {
          contractRevision: 'gear-result-envelope-v1',
          status: 'resolved',
          problems: [],
          data: {
            contractRevision: 'gear-resolved-snapshot-v1',
            status: 'verified',
            resolvedGearSignature: signature,
            dependencyVector: {},
            staticAttributes: {},
            setState: { itemSetCounts: {}, activeDynamicEffects: [] },
            aggregateLegality: { status: 'verified', problemCodes: [] },
            profileReadiness: { status: 'verified', simcReady: true },
            constraints: {
              embellishmentMax: 2,
              slots: {
                back: { socketCount: 0, canEnchant: false, canEmbellish: true },
                finger1: { socketCount: 2, canEnchant: true, canEmbellish: false }
              }
            },
            resolvedSlots: {
              back: {
                itemLevel: 707,
                selectedOptions: { gemOptionIds: [], enchantOptionId: '', embellishmentOptionId: 'cloak-embellishment' }
              },
              finger1: {
                itemLevel: 707,
                selectedOptions: { gemOptionIds: ['gem-one', 'gem-two'], enchantOptionId: 'ring-enchant', embellishmentOptionId: '' }
              }
            },
            problems: []
          }
        }
      })
    }
  })
  const template = {
    id: 'canonical-enhancements', canApplyGear: true,
    gearItems: [
      { ...ring, gem_id: '240892/240900', enchant_id: '7967' },
      { ...back, embellishment: 'arcanoweave_lining' }
    ]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })
  pageConfig.openGearEnhancementSheet.call(page)

  const metric = (key) => page.data.gearAttributePanel.enhancementRows.find((row) => row.key === key)
  assert.equal(metric('gem').value, '2/2')
  assert.equal(metric('enchant').value, '1/1')
  assert.equal(metric('embellishment').value, '1/2')
  assert.equal(page.communityEnhancementImportState.resolvedGearSignature, signature)
  pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'back' } }
  })
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeEmbellishmentRows[0].options.map((option) => [option.id, option.selected]))),
    [['cloak-embellishment', true]]
  )
  pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'finger1' } }
  })
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeGemRows[0].options.map((option) => [option.id, option.selected]))),
    [['gem-one', true], ['gem-two', true]]
  )
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeEnchantRows[0].options.map((option) => [option.id, option.selected]))),
    [['ring-enchant', true]]
  )
})

test('unmatched inherited enhancement renders a read-only slot without raw identifiers or forged controls', async () => {
  const inheritedRawValue = 'unverified_embellishment_991'
  const back = {
    slot: 'back', simcSlot: 'back', itemId: '299991', id: '299991', variantKey: 'back-inherited',
    displayName: 'Inherited Community Cloak', armorType: 'Cloth', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'back', simcSlot: 'back', label: '披风' }],
    replacementCandidates: [{ slot: 'back', simcSlot: 'back', detailMode: 'complete', items: [back] }],
    resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return canonicalResolveTransport(selectionIntent, 'sha256:inherited-evidence')
    }
  })
  const template = {
    id: 'inherited-enhancement', canApplyGear: true,
    gearItems: [{ ...back, embellishment: inheritedRawValue }]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })
  pageConfig.openGearEnhancementSheet.call(page)

  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.equipmentRows.map((row) => row.slot))),
    ['back']
  )
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeInheritedRows)), [{
    slot: 'back',
    type: 'embellishment',
    label: '美化',
    statusLabel: '已继承，当前目录不可编辑',
    readOnly: true
  }])
  assert.doesNotMatch(JSON.stringify(page.data.gearEnhancementSheet.activeInheritedRows), new RegExp(inheritedRawValue))
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.back, undefined)

  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  assert.match(wxml, /gear-enhancement-inherited-row/)
  assert.match(wxml, /已继承，当前目录不可编辑/)
  const inheritedBlock = wxml.match(/<view class="gear-enhancement-inherited-row"[\s\S]*?<\/view>/)
  assert.ok(inheritedBlock)
  assert.doesNotMatch(inheritedBlock[0], /<button|data-id=|raw/i)
})

test('explicit unresolved enchant and embellishment identities render only generic inherited types', async () => {
  const rawIdentities = [
    'unknown-explicit-enchant',
    'conflicting-explicit-embellishment-a',
    'conflicting-explicit-embellishment-b'
  ]
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299976', id: '299976', variantKey: 'explicit-ring',
    displayName: 'Explicit Identity Ring', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: true, canEmbellish: false }
  }
  const back = {
    slot: 'back', simcSlot: 'back', itemId: '299977', id: '299977', variantKey: 'explicit-back',
    displayName: 'Explicit Identity Cloak', armorType: 'Cloth', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
  }
  const verifiedOption = (type, optionKey) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel: type === 'enchant' ? '已验证附魔' : '已验证美化',
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: type === 'enchant'
      ? { enchant_id: `simc-${optionKey}` }
      : { embellishment: `simc-${optionKey}` },
    payload: { qualityRank: 2, slotGroup: 'armor' }
  })
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [
      { slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' },
      { slot: 'back', simcSlot: 'back', label: '披风' }
    ],
    replacementCandidates: [
      {
        slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring],
        enchantOptions: [verifiedOption('enchant', 'known-ring-enchant')]
      },
      {
        slot: 'back', simcSlot: 'back', detailMode: 'complete', items: [back],
        embellishmentOptions: [
          verifiedOption('embellishment', 'conflicting-explicit-embellishment-a'),
          verifiedOption('embellishment', 'conflicting-explicit-embellishment-b')
        ]
      }
    ],
    resolverContext: canonicalTestResolverContext()
  }
  const resolveRequests = []
  const constraints = {
    finger1: { socketCount: 0, canEnchant: true, canEmbellish: false },
    back: { socketCount: 0, canEnchant: false, canEmbellish: true }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      resolveRequests.push(selectionIntent)
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        'sha256:explicit-unresolved-identities',
        constraints,
        2
      )
    }
  })
  const template = {
    id: 'explicit-unresolved-identities',
    canApplyGear: true,
    gearItems: [ring, back],
    enhancementBySlot: {
      finger1: { enchantOptionId: rawIdentities[0] },
      back: { embellishmentOptionId: rawIdentities[1] }
    },
    payload: {
      enhancementBySlot: {
        back: { embellishmentOptionId: rawIdentities[2] }
      }
    }
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })

  assert.equal(resolveRequests.length, 1)
  assert.equal(resolveRequests[0].slots.finger1.enchantOptionId, '')
  assert.equal(resolveRequests[0].slots.back.embellishmentOptionId, '')
  rawIdentities.forEach((identity) => assert.doesNotMatch(JSON.stringify(resolveRequests[0]), new RegExp(identity)))
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState.unresolvedBySlot)), {
    finger1: { gemIds: [], enchantIds: [rawIdentities[0]], embellishments: [], readOnly: true },
    back: { gemIds: [], enchantIds: [], embellishments: [rawIdentities[1], rawIdentities[2]], readOnly: true }
  })

  pageConfig.openGearEnhancementSheet.call(page)
  for (const [slot, type, label] of [
    ['finger1', 'enchant', '附魔'],
    ['back', 'embellishment', '美化']
  ]) {
    pageConfig.selectGearEnhancementSlot.call(page, { currentTarget: { dataset: { slot } } })
    assert.deepEqual(JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeInheritedRows)), [{
      slot,
      type,
      label,
      statusLabel: '已继承，当前目录不可编辑',
      readOnly: true
    }])
    rawIdentities.forEach((identity) => {
      assert.doesNotMatch(JSON.stringify(page.data.gearEnhancementSheet.activeInheritedRows), new RegExp(identity))
    })
  }

  const wxml = fs.readFileSync('pages/builds/detail.wxml', 'utf8')
  const inheritedBlock = wxml.match(/<view class="gear-enhancement-inherited-row"[\s\S]*?<\/view>/)
  assert.ok(inheritedBlock)
  assert.match(inheritedBlock[0], /row.label/)
  assert.match(inheritedBlock[0], /已继承，当前目录不可编辑/)
  assert.doesNotMatch(inheritedBlock[0], /option|data-id|identity|raw/i)
})

test('post-Resolve stat refresh preserves inherited enhancement summary', async () => {
  const back = {
    slot: 'back', simcSlot: 'back', itemId: '299992', id: '299992', variantKey: 'back-stat-refresh',
    displayName: 'Stat Refresh Community Cloak', armorType: 'Cloth', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'back', simcSlot: 'back', label: '披风' }],
    replacementCandidates: [{ slot: 'back', simcSlot: 'back', detailMode: 'complete', items: [back] }],
    resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        'sha256:inherited-stat-refresh',
        { back: { socketCount: 0, canEnchant: false, canEmbellish: false } }
      )
    },
    requestWebsimGearStatSnapshot() {
      return Promise.resolve(canonicalStatTransport({
        statStatus: 'verified',
        statSource: 'simulationcraft_json',
        blockers: [],
        primary: { key: 'intellect', label: '智力', value: '1,234', rawValue: 1234 },
        secondary: [],
        itemLevel: { key: 'itemLevel', label: '装备等级', value: '707', rawValue: 707 }
      }, 'sha256:stat-after-community'))
    }
  })
  const template = {
    id: 'inherited-stat-refresh', canApplyGear: true,
    gearItems: [{ ...back, embellishment: 'unmatched_stat_refresh_embellishment' }]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: 'STAT-REFRESH-TALENTS' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent,
    refreshGearStats: pageConfig.refreshGearStats
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })

  const metric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'embellishment')
  assert.equal(page.data.gearStatSnapshot.statStatus, 'verified')
  assert.equal(metric.value, '0/2')
  assert.equal(metric.inheritedCount, 1)
  assert.equal(metric.inheritedLabel, '另有 1 个已继承事实不可编辑')
})

test('unrelated verified enchant edit preserves unmatched inherited gem beside canonical gem', async () => {
  let resolveCount = 0
  const verifiedOption = (optionKey, simcKey, value, displayLabel) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { [simcKey]: value },
    payload: { qualityRank: 2 }
  })
  const neck = {
    slot: 'neck', simcSlot: 'neck', itemId: '299993', id: '299993', variantKey: 'neck-mixed-evidence',
    displayName: 'Mixed Evidence Neck', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 2, canEnchant: false, canEmbellish: false }
  }
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299994', id: '299994', variantKey: 'ring-mixed-evidence',
    displayName: 'Mixed Evidence Ring', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: true, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [
      { slot: 'neck', simcSlot: 'neck', label: '项链' },
      { slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }
    ],
    replacementCandidates: [
      {
        slot: 'neck', simcSlot: 'neck', detailMode: 'complete', items: [neck],
        socketOptions: [verifiedOption('known-neck-gem', 'gem_id', '240892', '+32 急速')]
      },
      {
        slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring],
        enchantOptions: [verifiedOption('replacement-ring-enchant', 'enchant_id', '7967', '苍穹全能')]
      }
    ],
    resolverContext: canonicalTestResolverContext()
  }
  const constraints = {
    neck: { socketCount: 2, canEnchant: false, canEmbellish: false },
    finger1: { socketCount: 0, canEnchant: true, canEmbellish: false }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      resolveCount += 1
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        resolveCount === 1 ? 'sha256:mixed-evidence-old' : 'sha256:mixed-evidence-enchant-edit',
        constraints
      )
    }
  })
  const template = {
    id: 'mixed-inherited-gem', canApplyGear: true,
    gearItems: [{ ...neck, gem_id: '240892/999999' }, ring]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })
  assert.deepEqual(JSON.parse(JSON.stringify(page.data.enhancementBySlot)), {
    neck: { gemOptionIds: ['known-neck-gem'] }
  })
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState.unresolvedBySlot)), {
    neck: { gemIds: ['999999'], enchantIds: [], embellishments: [], readOnly: true }
  })

  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementSlot.call(page, {
    currentTarget: { dataset: { slot: 'finger1' } }
  })
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'replacement-ring-enchant' } }
  })
  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.communityEnhancementImportState.resolvedGearSignature, 'sha256:mixed-evidence-enchant-edit')
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState.unresolvedBySlot)), {
    neck: { gemIds: ['999999'], enchantIds: [], embellishments: [], readOnly: true }
  })
  const gemMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem')
  const enchantMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant')
  assert.equal(gemMetric.value, '1/2')
  assert.equal(gemMetric.inheritedCount, 1)
  assert.equal(enchantMetric.value, '1/1')
})

test('canonical embellishment max zero remains zero in attribute panel and editor', async () => {
  const back = {
    slot: 'back', simcSlot: 'back', itemId: '299997', id: '299997', variantKey: 'back-zero-max',
    displayName: 'Zero Max Cloak', armorType: 'Cloth', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: true }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'back', simcSlot: 'back', label: '披风' }],
    replacementCandidates: [{ slot: 'back', simcSlot: 'back', detailMode: 'complete', items: [back] }],
    resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return canonicalEnhancementResolveTransport(
        selectionIntent,
        'sha256:zero-embellishment-max',
        { back: { socketCount: 0, canEnchant: false, canEmbellish: true } },
        0
      )
    }
  })
  const template = { id: 'zero-embellishment-max', canApplyGear: true, gearItems: [back] }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })
  pageConfig.openGearEnhancementSheet.call(page)

  const metric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'embellishment')
  assert.equal(metric.value, '0/0')
  assert.equal(metric.max, 0)
  assert.equal(page.data.gearEnhancementSheet.embellishmentMax, 0)
})

async function inheritedReplacementHarness({ replacementResult = 'verified' } = {}) {
  let resolveCount = 0
  const verifiedOption = (optionKey, simcKey, value, displayLabel) => ({
    id: `row-${optionKey}`,
    optionKey,
    displayLabel,
    displayStatus: 'verified',
    evidenceSource: 'test_authority',
    status: 'verified',
    simcOptions: { [simcKey]: value },
    payload: { qualityRank: 2 }
  })
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299995', id: '299995', variantKey: 'ring-inherited',
    displayName: 'Inherited Community Ring', simcReady: true,
    modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: true, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{
      slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring],
      socketOptions: [verifiedOption('replacement-gem', 'gem_id', '240892', '+32 急速')],
      enchantOptions: [verifiedOption('replacement-enchant', 'enchant_id', '7967', '苍穹全能')]
    }],
    resolverContext: canonicalTestResolverContext()
  }
  const constraints = {
    finger1: { socketCount: 1, canEnchant: true, canEmbellish: false }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      resolveCount += 1
      if (resolveCount === 1) {
        return canonicalEnhancementResolveTransport(selectionIntent, 'sha256:inherited-old', constraints)
      }
      if (replacementResult === 'verified') {
        return canonicalEnhancementResolveTransport(selectionIntent, 'sha256:inherited-replaced', constraints)
      }
      return Promise.resolve({
        httpStatus: 422,
        fromFallback: false,
        payload: {
          contractRevision: 'gear-result-envelope-v1',
          requestId: 'resolve-replacement-blocked',
          releaseContext: {},
          status: 'blocked',
          problems: [{ kind: 'ILLEGAL_SELECTION', code: 'GEAR_REPLACEMENT_BLOCKED', title: 'replacement blocked' }],
          data: {
            contractRevision: 'gear-resolved-snapshot-v1',
            status: 'blocked',
            resolvedGearSignature: 'sha256:blocked-different',
            constraints: {
              embellishmentMax: 0,
              slots: { finger1: { socketCount: 9, canEnchant: false, canEmbellish: false } }
            },
            resolvedSlots: {
              finger1: {
                itemLevel: 999,
                selectedOptions: {
                  gemOptionIds: ['blocked-gem'],
                  enchantOptionId: 'blocked-enchant',
                  embellishmentOptionId: ''
                }
              }
            }
          }
        }
      })
    }
  })
  const template = {
    id: 'inherited-replacement', canApplyGear: true,
    gearItems: [{ ...ring, gem_id: 'unmatched_gem_991', enchant_id: 'unmatched_enchant_992' }]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [template], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }
  await pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: template.id } }
  })
  return { pageConfig, page, getResolveCount: () => resolveCount }
}

test('closing inherited enhancement sheet discards unconfirmed verified replacement draft', async () => {
  const { pageConfig, page, getResolveCount } = await inheritedReplacementHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'replacement-enchant' } }
  })
  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1.enchantOptionId, 'replacement-enchant')

  pageConfig.closeGearEnhancementSheet.call(page)
  pageConfig.openGearEnhancementSheet.call(page)

  assert.equal(page.data.gearEnhancementSheet.draftEnhancementBySlot.finger1, undefined)
  assert.equal(page.data.gearEnhancementSheet.activeEnchantRows[0].options[0].selected, false)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeInheritedRows.map((row) => row.type))),
    ['gem', 'enchant']
  )
  assert.equal(getResolveCount(), 1)
})

test('successful verified replacement clears only that inherited type and rebinds evidence', async () => {
  const { pageConfig, page } = await inheritedReplacementHarness()
  pageConfig.openGearEnhancementSheet.call(page)
  const initialGemMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem')
  const initialEnchantMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant')
  assert.equal(initialGemMetric.value, '0/1')
  assert.equal(initialGemMetric.inheritedCount, 1)
  assert.equal(initialEnchantMetric.value, '0/1')
  assert.equal(initialEnchantMetric.inheritedCount, 1)

  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'replacement-enchant' } }
  })
  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.communityEnhancementImportState.resolvedGearSignature, 'sha256:inherited-replaced')
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState.unresolvedBySlot)), {
    finger1: {
      gemIds: ['unmatched_gem_991'],
      enchantIds: [],
      embellishments: [],
      readOnly: true
    }
  })
  const gemMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem')
  const enchantMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant')
  assert.equal(gemMetric.value, '0/1')
  assert.equal(gemMetric.inheritedCount, 1)
  assert.equal(enchantMetric.value, '1/1')
  assert.equal(enchantMetric.inheritedCount, undefined)
})

test('failed verified replacement retains inherited evidence and its prior binding', async () => {
  const { pageConfig, page } = await inheritedReplacementHarness({ replacementResult: 'blocked' })
  pageConfig.openGearEnhancementSheet.call(page)
  const evidenceBefore = JSON.parse(JSON.stringify(page.communityEnhancementImportState))
  pageConfig.selectGearEnhancementOption.call(page, {
    currentTarget: { dataset: { slot: 'finger1', type: 'enchant', id: 'replacement-enchant' } }
  })

  await pageConfig.confirmGearEnhancementSheet.call(page)

  assert.equal(page.gearWorkbenchState.resolveStatus, 'blocked')
  assert.equal(page.gearWorkbenchState.currentSnapshot.resolvedGearSignature, 'sha256:blocked-different')
  assert.equal(page.data.gearWorkbenchSignatureLabel, 'sha256:inherited-old')
  assert.doesNotMatch(page.data.gearWorkbenchSignatureLabel, /blocked-different/)
  assert.equal(page.data.gearWorkbenchStatusText, '当前装备配置未通过校验')
  assert.equal(page.data.gearWorkbenchProblemRows[0].code, 'GEAR_REPLACEMENT_BLOCKED')
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), evidenceBefore)
  const gemMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'gem')
  const enchantMetric = page.data.gearAttributePanel.enhancementRows.find((row) => row.key === 'enchant')
  assert.equal(gemMetric.value, '0/1')
  assert.equal(gemMetric.inheritedCount, 1)
  assert.equal(enchantMetric.value, '0/1')
  assert.equal(enchantMetric.inheritedCount, 1)
  pageConfig.openGearEnhancementSheet.call(page)
  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gearEnhancementSheet.activeInheritedRows.map((row) => row.type))),
    ['gem', 'enchant']
  )
  assert.equal(page.data.gearEnhancementSheet.embellishmentMax, 2)
  assert.equal(page.data.gearEnhancementSheet.equipmentRows[0].slot, 'finger1')
})

test('older community Resolve completion cannot bind or clear newer import evidence', async () => {
  const pendingResolves = []
  const ring = {
    slot: 'finger1', simcSlot: 'finger1', itemId: '299996', id: '299996', variantKey: 'ring-resolve-race',
    displayName: 'Resolve Race Ring', simcReady: true,
    modCapabilities: { hasSocket: false, socketCount: 0, canEnchant: false, canEmbellish: false }
  }
  const gearPayload = {
    classKey: 'mage', specKey: 'frost', maxLevel: 90,
    slots: [{ slot: 'finger1', simcSlot: 'finger1', label: '戒指 1' }],
    replacementCandidates: [{ slot: 'finger1', simcSlot: 'finger1', detailMode: 'complete', items: [ring] }],
    resolverContext: canonicalTestResolverContext()
  }
  const pageConfig = loadBuildsDetailPageConfig({
    requestWebsimGearResolve(selectionIntent) {
      return new Promise((resolve) => pendingResolves.push({ selectionIntent, resolve }))
    }
  })
  const olderTemplate = {
    id: 'older-resolve', canApplyGear: true,
    gearItems: [{ ...ring, enchant_id: 'older_raw_enchant' }]
  }
  const newerTemplate = {
    id: 'newer-resolve', canApplyGear: true,
    gearItems: [{ ...ring, embellishment: 'newer_raw_embellishment' }]
  }
  const page = {
    gearPayloadCache: gearPayload,
    data: {
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear', selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearSelectionKey: 'mage:frost', gearPayload, selectedGearBySlot: {}, enhancementBySlot: {},
      activeGearCommunityTemplates: [olderTemplate, newerTemplate], gearCommunityTemplateSheet: { visible: true },
      gearSlotSheet: { visible: false }, gearEnhancementSheet: { visible: false }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    confirmAndResolveGearIntent: pageConfig.confirmAndResolveGearIntent
  }

  const olderImport = pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: olderTemplate.id } }
  })
  await new Promise((resolve) => setImmediate(resolve))
  page.data.activeGearCommunityTemplates = [olderTemplate, newerTemplate]
  const newerImport = pageConfig.applyGearCommunityTemplate.call(page, {
    currentTarget: { dataset: { id: newerTemplate.id } }
  })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(pendingResolves.length, 2)

  pendingResolves[1].resolve(await canonicalEnhancementResolveTransport(
    pendingResolves[1].selectionIntent,
    'sha256:newer-resolve',
    { finger1: { socketCount: 0, canEnchant: false, canEmbellish: false } }
  ))
  await newerImport
  const newerEvidence = JSON.parse(JSON.stringify(page.communityEnhancementImportState))

  pendingResolves[0].resolve(await canonicalEnhancementResolveTransport(
    pendingResolves[0].selectionIntent,
    'sha256:older-resolve',
    { finger1: { socketCount: 0, canEnchant: false, canEmbellish: false } }
  ))
  await olderImport

  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), newerEvidence)
  assert.equal(page.communityEnhancementImportState.templateId, 'newer-resolve')
  assert.equal(page.communityEnhancementImportState.resolvedGearSignature, 'sha256:newer-resolve')
})

test('gear import sheet applies a saved personal gear template with enhancements', () => {
  const baseline = completeGearSelection(['back', 'neck'])
  const savedBack = {
    ...baseline.back,
    itemId: '277777',
    id: '277777',
    displayName: 'Saved Back'
  }
  const enhancementBySlot = {
    back: {
      enchantOptionId: 'cloak-speed',
      enchant_id: '123'
    }
  }
  const pageConfig = loadBuildsDetailPageConfig({
    storedTemplates: [{
      id: 'saved-gear',
      type: 'gear',
      title: '我的装备模板',
      classKey: 'mage',
      className: '法师',
      specKey: 'frost',
      specName: '冰霜',
      scenarioTitle: '单体',
      rawString: JSON.stringify({
        gearBySlot: { back: savedBack },
        enhancementBySlot
      }),
      metadata: {
        gearBySlot: { back: savedBack },
        enhancementBySlot
      },
      updatedAt: '2026-06-26T12:30:00.000Z',
      statusLabel: '完整配置'
    }]
  })
  const page = {
    ...pageConfig,
    communityEnhancementImportState: {
      templateId: 'community-before-saved', serial: 9, resolvedGearSignature: 'sha256:before-saved',
      unresolvedBySlot: { back: { gemIds: [], enchantIds: ['raw-saved'], embellishments: [], readOnly: true } },
      warnings: ['clear saved import evidence']
    },
    data: {
      ...pageConfig.data,
      selectedDetail: { details: { talents: { coreTalents: [], importCode: '' }, gear: {} } },
      activeQueryKey: 'gear',
      selectedSpec: { websimClassKey: 'mage', websimSpecKey: 'frost' },
      gearDataFallback: false,
      gearPayload: {
        slots: ['back', 'neck'].map((slot) => ({ slot, simcSlot: slot, label: slot })),
        equippedSet: baseline,
        replacementCandidates: [{
          slot: 'back',
          simcSlot: 'back',
          items: [savedBack],
          enchantOptions: [{
            id: 'cloak-speed',
            displayLabel: '披风附魔 迅捷之诵',
            status: 'verified',
            simcOptions: { enchant_id: '123' }
          }]
        }],
        slotReadiness: {},
        readiness: {}
      },
      selectedGearBySlot: baseline,
      enhancementBySlot: {},
      gearCommunityTemplateSheet: { visible: false },
      gearSlotSheet: { visible: true },
      gearEnhancementSheet: { visible: true }
    },
    setData(update) {
      this.data = { ...this.data, ...update }
    }
  }

  pageConfig.openGearCommunityTemplates.call(page)
  pageConfig.applySavedGearTemplate.call(page, { currentTarget: { dataset: { id: 'saved-gear' } } })

  assert.equal(page.data.savedGearTemplates.length, 1)
  assert.equal(page.data.savedGearTemplates[0].displayName, '我的装备模板')
  assert.equal(page.data.selectedGearBySlot.back.itemId, savedBack.itemId)
  assert.equal(page.data.selectedGearBySlot.neck.itemId, baseline.neck.itemId)
  assert.equal(page.data.enhancementBySlot.back.enchant_id, '123')
  assert.equal(page.data.gearCommunityTemplateSheet.visible, false)
  assert.equal(page.data.gearSlotSheet.visible, false)
  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), {
    templateId: '', serial: 0, resolvedGearSignature: '', unresolvedBySlot: {}, warnings: []
  })
})

test('specialization change clears bound community enhancement evidence', () => {
  const pageConfig = loadBuildsDetailPageConfig()
  const page = {
    communityEnhancementImportState: {
      templateId: 'community-before-spec', serial: 11, resolvedGearSignature: 'sha256:before-spec',
      unresolvedBySlot: { finger1: { gemIds: ['raw-spec'], enchantIds: [], embellishments: [], readOnly: true } },
      warnings: ['clear spec evidence']
    },
    data: {
      selectedClassIndex: 0,
      activeQueryKey: 'talents',
      selectedSpec: { id: 'old-spec' }
    },
    setData(update) { this.data = { ...this.data, ...update } },
    loadSelectedDetail() {}
  }

  pageConfig.selectSpec.call(page, { detail: { value: 0 } })

  assert.deepEqual(JSON.parse(JSON.stringify(page.communityEnhancementImportState)), {
    templateId: '', serial: 0, resolvedGearSignature: '', unresolvedBySlot: {}, warnings: []
  })
})

test('simc linkage derives talent and gear state from full specialization details', () => {
  const js = fs.readFileSync('pages/builds/detail.js', 'utf8')

  assert.match(js, /const talentDetail = detailForQuery\(selectedDetail,\s*'talents'\)/)
  assert.match(js, /buildTalentNodeRows\(talentDetail/)
  assert.match(js, /buildGearSlotRows/)
  assert.match(js, /websimClassKey/)
  assert.match(js, /websimSpecKey/)
})

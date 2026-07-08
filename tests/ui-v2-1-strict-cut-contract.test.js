const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { auditStaticScope } = require('../artifacts/ui-v2-1-strict-restoration/pass36-static-scope-audit')
const { buildRuntimeCaptureContract } = require('../artifacts/ui-v2-1-strict-restoration/pass36-runtime-capture-contract')
const { validatePass36FinalAcceptance } = require('../artifacts/ui-v2-1-strict-restoration/validate-pass36-final-acceptance')
const { buildRuntimeOperatorPackage } = require('../artifacts/ui-v2-1-strict-restoration/create-pass36l-runtime-operator-package')
const {
  MERGE_FILES,
  WRITE_DISABLE_ENV,
  buildControlledMergePlan,
  applyControlledMerge
} = require('../artifacts/ui-v2-1-strict-restoration/prepare-pass36-controlled-merge')
const {
  buildFinalReadinessReport,
  writeFinalReadinessReport
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass36-final-readiness-report')
const {
  buildPass36RequirementAudit,
  writePass36RequirementAudit
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass36-requirement-audit')
const {
  buildRecoveryPackage,
  extractHealthSummary,
  diagnosisForStatus
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass36-automation-recovery-package')
const {
  DIFF_GROUPS,
  buildCurrentDiffReport,
  writeCurrentDiffReport
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass36-current-diff-report')
const {
  buildWriteWindowPreflight,
  writeWriteWindowPreflight
} = require('../artifacts/ui-v2-1-strict-restoration/prepare-pass36-write-window-preflight')
const {
  buildAudit: buildAssetSliceWorkflowAudit
} = require('../artifacts/ui-v2-1-strict-restoration/audit-pass36-asset-slice-workflow')
const {
  STATUS_WORDS: PASS37_STATUS_WORDS,
  REQUIRED_ARTIFACTS: PASS37_REQUIRED_ARTIFACTS,
  PROHIBITED_DEVTOOLS_ACTIONS: PASS37_PROHIBITED_DEVTOOLS_ACTIONS,
  buildPass37ArchitectureInputPackage,
  renderMarkdown: renderPass37ArchitectureMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-architecture-input-package')
const {
  REQUIRED_FIXTURE_STATES: PASS37_REQUIRED_FIXTURE_STATES,
  VIEWPORT_PROFILES: PASS37_VIEWPORT_PROFILES,
  buildPass37ComponentRedlines,
  renderMarkdown: renderPass37ComponentRedlinesMarkdown,
  renderFixtureHtml: renderPass37ComponentRedlinesFixtureHtml
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-component-redlines')
const {
  forbiddenVisibleChromePattern: PASS37_PRECHECK_FORBIDDEN_CHROME,
  requiredLockedTargetText: PASS37_PRECHECK_REQUIRED_TARGET_TEXT,
  buildPass37ComponentPrecheckPlan
} = require('../artifacts/ui-v2-1-strict-restoration/run-pass37-component-precheck')
const {
  IMPLEMENTATION_COMPONENTS: PASS37_IMPLEMENTATION_COMPONENTS,
  buildPass37ImplementationMap,
  renderMarkdown: renderPass37ImplementationMapMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-implementation-map')
const {
  layoutRules: PASS37_NEWS_LAYOUT_RULES,
  cropTargets: PASS37_NEWS_LAYOUT_CROP_TARGETS,
  buildPass37NewsImplementationLayoutAuditPlan
} = require('../artifacts/ui-v2-1-strict-restoration/run-pass37-news-implementation-layout-audit')
const {
  REQUIRED_TICKET_TYPES: PASS37_RECOVERY_TICKET_TYPES,
  FOUNDATION_COMPONENTS: PASS37_RECOVERY_FOUNDATION_COMPONENTS,
  RECOVERY_SURFACES: PASS37_RECOVERY_SURFACES,
  buildPass37RecoveryTickets,
  renderMarkdown: renderPass37RecoveryTicketsMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-recovery-tickets')
const {
  REQUIRED_FOUNDATION_IDS: PASS37_FOUNDATION_IDS,
  CONTRACT_DETAILS: PASS37_FOUNDATION_CONTRACT_DETAILS,
  KEEP_REPLACE_QUARANTINE: PASS37_KEEP_REPLACE_QUARANTINE,
  buildPass37FoundationContracts,
  renderMarkdown: renderPass37FoundationContractsMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-contracts')
const {
  FOUNDATION_HARNESS_CROP_TARGETS: PASS37_FOUNDATION_HARNESS_CROP_TARGETS,
  forbiddenVisibleChromePattern: PASS37_FOUNDATION_HARNESS_FORBIDDEN_CHROME,
  buildPass37FoundationHarnessPlan
} = require('../artifacts/ui-v2-1-strict-restoration/run-pass37-foundation-harness')
const {
  REQUIRED_SURFACE_IDS: PASS37_PAGE_INTEGRATION_SURFACES,
  REQUIRED_FOUNDATION_COMPONENT_IDS: PASS37_PAGE_INTEGRATION_FOUNDATIONS,
  SURFACE_COMPONENT_ROLES: PASS37_PAGE_INTEGRATION_ROLES,
  buildPass37PageIntegrationMap,
  renderMarkdown: renderPass37PageIntegrationMapMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-page-integration-map')
const {
  REQUIRED_PACKETS: PASS37_STRICT_REQUIRED_PACKETS,
  DEVTOOLS_PROHIBITED_ACTIONS: PASS37_STRICT_DEVTOOLS_PROHIBITED_ACTIONS,
  FAILURE_DIAGNOSIS_LOCKS: PASS37_STRICT_FAILURE_DIAGNOSIS_LOCKS,
  COMPONENT_OWNERSHIP_LOCKS: PASS37_STRICT_COMPONENT_OWNERSHIP_LOCKS,
  PIXEL_MEASUREMENT_RULES: PASS37_STRICT_PIXEL_MEASUREMENT_RULES,
  ROUTE_INTERACTION_REQUIREMENTS: PASS37_STRICT_ROUTE_INTERACTION_REQUIREMENTS,
  FOUNDATION_RESET_GATES: PASS37_STRICT_FOUNDATION_RESET_GATES,
  SUSPENDED_SURFACE_PERMITS: PASS37_STRICT_SUSPENDED_SURFACE_PERMITS,
  EXECUTION_CONTROL_LOCKS: PASS37_STRICT_EXECUTION_CONTROL_LOCKS,
  IMPLEMENTATION_PERMIT_REQUIREMENTS: PASS37_STRICT_IMPLEMENTATION_PERMIT_REQUIREMENTS,
  EVIDENCE_PROMOTION_RULES: PASS37_STRICT_EVIDENCE_PROMOTION_RULES,
  ZERO_TOLERANCE_RUNTIME_FAILURES: PASS37_STRICT_ZERO_TOLERANCE_RUNTIME_FAILURES,
  buildPass37StrictSystemContract,
  renderMarkdown: renderPass37StrictSystemContractMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-strict-system-contract')
const {
  SURFACE_ID: PASS37_NEWS_PERMIT_SURFACE_ID,
  ROUTE: PASS37_NEWS_PERMIT_ROUTE,
  PRIMARY_OWNER: PASS37_NEWS_PERMIT_PRIMARY_OWNER,
  PERMIT_STATUS: PASS37_NEWS_PERMIT_STATUS,
  ALLOWED_PRODUCTION_FILES: PASS37_NEWS_PERMIT_ALLOWED_FILES,
  FORBIDDEN_PRODUCTION_FILES: PASS37_NEWS_PERMIT_FORBIDDEN_FILES,
  REQUIRED_ROUTE_SMOKE: PASS37_NEWS_PERMIT_ROUTE_SMOKE,
  FORBIDDEN_FAKE_FIELDS: PASS37_NEWS_PERMIT_FORBIDDEN_FAKE_FIELDS,
  buildPass37NewsSurfaceImplementationPermit,
  renderMarkdown: renderPass37NewsSurfaceImplementationPermitMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-news-surface-implementation-permit')
const {
  PERMIT_STATUS: PASS37_NEWS_FRESH_PERMIT_STATUS,
  ALLOWED_PRODUCTION_FILES: PASS37_NEWS_FRESH_PERMIT_ALLOWED_FILES,
  FORBIDDEN_PRODUCTION_FILES: PASS37_NEWS_FRESH_PERMIT_FORBIDDEN_FILES,
  buildPass37NewsSurfaceFreshImplementationPermit,
  renderMarkdown: renderPass37NewsSurfaceFreshImplementationPermitMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-news-surface-fresh-implementation-permit')
const {
  DECISION_STATUS: PASS37_REPERMIT_DECISION_STATUS,
  buildPass37RepermitDecisionRecord,
  renderMarkdown: renderPass37RepermitDecisionRecordMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-repermit-decision-record')
const {
  REQUIRED_FOUNDATION_COMPONENTS: PASS37_RESET_FOUNDATION_COMPONENTS,
  REQUIRED_FIXTURE_STATES: PASS37_RESET_FIXTURE_STATES,
  VIEWPORT_PROFILES: PASS37_RESET_VIEWPORT_PROFILES,
  SOURCE_COMPONENT_MAP: PASS37_RESET_SOURCE_COMPONENT_MAP,
  DEVTOOLS_ACTION_LEDGER_REQUIREMENTS: PASS37_RESET_DEVTOOLS_LEDGER_REQUIREMENTS,
  buildPass37FoundationResetPackage,
  renderMarkdown: renderPass37FoundationResetMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-reset-package')
const {
  ROOT_CAUSE_OVERRIDES: PASS37_ARCH_RESET_ROOT_CAUSES,
  REAL_COMPONENT_GATE_OWNERS: PASS37_ARCH_RESET_REAL_COMPONENT_OWNERS,
  STATE_VISUAL_MODES: PASS37_ARCH_RESET_STATE_VISUAL_MODES,
  ASSET_CLASSES_V2: PASS37_ARCH_RESET_ASSET_CLASSES,
  MEASUREMENT_REQUIRED_ITEMS: PASS37_ARCH_RESET_MEASUREMENT_ITEMS,
  ROUTE_SURFACE_GATES: PASS37_ARCH_RESET_ROUTE_GATES,
  RESTART_CONDITIONS: PASS37_ARCH_RESET_RESTART_CONDITIONS,
  buildPass37ArchitectureResetGateV2,
  renderMarkdown: renderPass37ArchitectureResetGateV2Markdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-architecture-reset-gate-v2')
const {
  LEDGER_ENTRY_FIELDS: PASS37_DEVTOOLS_LEDGER_FIELDS,
  DISTURBANCE_LEVELS: PASS37_DEVTOOLS_DISTURBANCE_LEVELS,
  PROHIBITED_WITHOUT_FRESH_APPROVAL: PASS37_DEVTOOLS_PROHIBITED_WITHOUT_APPROVAL,
  buildPass37DevToolsActionLedger,
  renderMarkdown: renderPass37DevToolsActionLedgerMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-devtools-action-ledger')
const {
  buildPass37FoundationFixtureMatrix,
  renderMarkdown: renderPass37FoundationFixtureMatrixMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-fixture-matrix')
const {
  MEASUREMENT_REQUIRED_ITEMS: PASS37_MEASUREMENT_PIPELINE_ITEMS,
  SURFACE_MEASUREMENT_PLAN: PASS37_MEASUREMENT_SURFACES,
  buildPass37MeasurementPipeline,
  renderMarkdown: renderPass37MeasurementPipelineMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-measurement-pipeline')
const {
  REQUIRED_SURFACE_IDS: PASS37_ROUTE_SMOKE_SURFACES,
  SCENARIO_REQUIREMENTS: PASS37_ROUTE_SMOKE_SCENARIOS,
  buildPass37RouteSmokeHarness,
  renderMarkdown: renderPass37RouteSmokeHarnessMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-route-smoke-harness')
const {
  SHELL_RISKS: PASS37_CROSS_SURFACE_SHELL_RISKS,
  buildPass37CrossSurfaceShellAudit,
  renderMarkdown: renderPass37CrossSurfaceShellAuditMarkdown
} = require('../artifacts/ui-v2-1-strict-restoration/create-pass37-cross-surface-shell-audit')

function readJson(path) {
  return JSON.parse(fs.readFileSync(path, 'utf8'))
}

function readProductionUi() {
  return [
    'pages/news/news.wxml',
    'pages/news/news.wxss',
    'components/channel-dock/channel-dock.wxml',
    'components/channel-dock/channel-dock.wxss',
    'components/ranked-feed/ranked-feed.wxml',
    'components/ranked-feed/ranked-feed.wxss',
    'pages/builds/builds.wxml',
    'pages/builds/builds.wxss',
    'pages/builds/workbench.wxml',
    'pages/builds/workbench.wxss'
  ].map((path) => fs.readFileSync(path, 'utf8')).join('\n')
}

function writeBytes(filePath, size = 6000) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, Buffer.alloc(size, 1))
}

function fixtureImageForLogicalSize(logicalSize) {
  const match = String(logicalSize || '').match(/(\d+)\s*x\s*(\d+)/i)
  const width = match ? Number(match[1]) * 2 : 780
  const height = match ? Math.max(1200, Number(match[2])) : 1524
  return { width, height }
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('pass36 automation recovery diagnoses headless DevTools windows', () => {
  const healthSummary = extractHealthSummary({
    summary: {
      captureSafe: false,
      runtimeResponsive: false,
      automatorConnected: true,
      noVisibleWindowRisk: true
    },
    devtoolsWindows: {
      count: 0,
      note: 'wechatdevtools is running but System Events reports zero windows.'
    },
    automator: {
      port: 9855,
      currentPage: { error: 'App.getCurrentPage timed out after 3000ms' },
      pageStack: { error: 'App.getPageStack timed out after 3000ms' }
    }
  })
  assert.equal(healthSummary.noVisibleWindowRisk, true)
  assert.equal(healthSummary.devtoolsWindowCount, 0)

  const diagnosis = diagnosisForStatus(
    'blocked_runtime_unresponsive',
    { activeShadowDrift: false },
    healthSummary
  )
  assert.ok(diagnosis.some((item) => /0 visible WeChat DevTools windows/.test(item)))
  assert.ok(diagnosis.some((item) => /stale or headless session/.test(item)))
})

test('pass36 automation recovery promotes DevTools login-required evidence', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-login-required-'))
  const artifactDir = path.join(root, 'artifacts')
  fs.mkdirSync(artifactDir, { recursive: true })
  writeJson(path.join(artifactDir, 'pass36aq-devtools-login-required.json'), {
    status: 'blocked_devtools_login_required',
    createdAt: '2026-07-05T13:21:26+08:00',
    facts: {
      visibleDevToolsWindowCount: 0,
      projectOpenResult: '需要重新登录 (code 10)',
      loginQrPath: '/tmp/wow-devtools-login.png',
      loginCompleted: false
    },
    requiredForResume: [
      'Scan /tmp/wow-devtools-login.png or regenerate it with cli login'
    ]
  })
  const healthReport = path.join(artifactDir, 'pass36-login-required-health.json')
  writeJson(healthReport, {
    summary: {
      captureSafe: false,
      runtimeResponsive: false,
      automatorConnected: false,
      noVisibleWindowRisk: false,
      healthCategory: 'devtools_login_false'
    },
    devtoolsWindows: {
      count: 1,
      note: 'fixture: login-required DevTools state'
    },
    automator: {
      port: 9855,
      connect: { error: 'fixture: login required' }
    }
  })

  const report = buildRecoveryPackage({
    repoRoot: process.cwd(),
    artifactDir,
    healthReport
  })

  assert.equal(report.status, 'blocked_devtools_login_required')
  assert.equal(report.devtoolsLoginRequired.loginCompleted, false)
  assert.match(report.userScannedLoginCommand, /cli login --qr-format image/)
  assert.match(report.openProjectAfterLoginCommand, /cli open --project/)
  assert.ok(report.diagnosis.some((item) => /需要重新登录/.test(item)))
  assert.ok(report.prohibitedActions.some((item) => /automated login loops/.test(item)))
})

test('pass36 automation recovery does not relabel no-visible-window as login required', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-no-visible-window-'))
  const artifactDir = path.join(root, 'artifacts')
  fs.mkdirSync(artifactDir, { recursive: true })
  writeJson(path.join(artifactDir, 'pass36aq-devtools-login-required.json'), {
    status: 'blocked_devtools_login_required',
    createdAt: '2026-07-05T13:21:26+08:00',
    facts: {
      visibleDevToolsWindowCount: 0,
      projectOpenResult: '需要重新登录 (code 10)',
      loginQrPath: '/tmp/wow-devtools-login.png',
      loginCompleted: false
    }
  })
  const healthReport = path.join(artifactDir, 'pass36-no-visible-health.json')
  writeJson(healthReport, {
    summary: {
      captureSafe: false,
      runtimeResponsive: false,
      automatorConnected: false,
      noVisibleWindowRisk: true,
      healthCategory: 'no_visible_devtools_window'
    },
    devtoolsWindows: {
      count: 0,
      note: 'wechatdevtools is running but System Events reports zero windows.'
    },
    automator: {
      port: 9854,
      portProfiles: [
        {
          port: 9854,
          category: 'not_listening_now',
          candidateForExplicitAutomator: false
        }
      ],
      diagnosis: {
        category: 'no_visible_devtools_window',
        reason: 'wechatdevtools is running but no visible window was reported.'
      }
    }
  })

  const report = buildRecoveryPackage({
    repoRoot: process.cwd(),
    artifactDir,
    healthReport
  })

  assert.equal(report.status, 'blocked_no_visible_devtools_window')
  assert.equal(report.devtoolsLoginRequiredSuppressedByCurrentHealth, true)
  assert.ok(report.diagnosis.some((item) => /not proof that WeChat login expired/.test(item)))
  assert.deepEqual(report.portProfiles.map((profile) => `${profile.port}:${profile.category}`), [
    '9854:not_listening_now'
  ])
})

test('pass36 automation recovery suppresses stale login-required evidence after current health recovers the window', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-stale-login-required-'))
  const artifactDir = path.join(root, 'artifacts')
  fs.mkdirSync(artifactDir, { recursive: true })
  writeJson(path.join(artifactDir, 'pass36aq-devtools-login-required.json'), {
    status: 'blocked_devtools_login_required',
    createdAt: '2026-07-05T13:21:26+08:00',
    facts: {
      visibleDevToolsWindowCount: 0,
      projectOpenResult: '需要重新登录 (code 10)',
      loginQrPath: '/tmp/wow-devtools-login.png',
      loginCompleted: false
    }
  })
  const healthReport = path.join(artifactDir, 'pass36-current-health.json')
  writeJson(healthReport, {
    createdAt: '2026-07-05T15:40:46.697Z',
    summary: {
      captureSafe: false,
      runtimeResponsive: false,
      automatorConnected: false,
      noVisibleWindowRisk: false,
      multiInstanceRisk: false,
      healthCategory: 'candidate_ports_not_miniprogram_automator'
    },
    devtoolsWindows: {
      count: 1,
      note: 'wechatdevtools has at least one System Events-visible window.'
    },
    automator: {
      port: 9854,
      portProfiles: [
        {
          port: 9854,
          category: 'non_runtime_tool_endpoint',
          candidateForExplicitAutomator: false,
          inCandidateList: true,
          reason: 'Connection reached a tool endpoint but not the mini program runtime.'
        },
        {
          port: 32123,
          category: 'devtools_debugger_json_endpoint',
          candidateForExplicitAutomator: false,
          inCandidateList: true,
          reason: 'The port exposes Chrome/DevTools debugger JSON.'
        }
      ],
      diagnosis: {
        category: 'candidate_ports_not_miniprogram_automator',
        reason: 'Detected ports responded like DevTools/debug endpoints.'
      }
    }
  })

  const report = buildRecoveryPackage({
    repoRoot: process.cwd(),
    artifactDir,
    healthReport
  })

  assert.equal(report.status, 'blocked_automator_endpoint_unavailable')
  assert.equal(report.devtoolsLoginRequiredSuppressedByCurrentHealth, true)
  assert.equal(report.health.healthCategory, 'candidate_ports_not_miniprogram_automator')
  assert.deepEqual(report.portProfiles.map((profile) => `${profile.port}:${profile.category}`), [
    '9854:non_runtime_tool_endpoint',
    '32123:devtools_debugger_json_endpoint'
  ])
  assert.ok(report.diagnosis.some((item) => /Health category: candidate_ports_not_miniprogram_automator/.test(item)))
  assert.ok(report.diagnosis.some((item) => /Port profile categories: 9854:non_runtime_tool_endpoint, 32123:devtools_debugger_json_endpoint/.test(item)))
  assert.match(report.automationEndpointRecovery.authorizedCliAutoCommand, /cli auto --project/)
  assert.equal(report.automationEndpointRecovery.requiresExplicitAuthorization, true)
})

function createCompletePass36Fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-final-validator-'))
  const artifactDir = path.join(root, 'artifacts')
  const contract = buildRuntimeCaptureContract()
  const required = contract.requiredArtifacts
  const scenes = required.screenshots.map((shot) => {
    const shotPath = `screens/${shot.id}-${shot.viewportId}.png`
    writeBytes(path.join(artifactDir, shotPath))
    return {
      id: shot.id,
      viewportId: shot.viewportId,
      logicalSize: shot.logicalSize,
      status: 'captured',
      path: shotPath,
      captureMethod: 'miniprogram-automator.real-devtools',
      visualCheck: {
        nonEmpty: true,
        bytes: 6000,
        image: fixtureImageForLogicalSize(shot.logicalSize),
        viewportWidthMatches: true
      }
    }
  })

  writeJson(path.join(artifactDir, required.manifestPattern), {
    pass: 'pass36l',
    strictGateEligible: true,
    runtimeScreenshot: true,
    devtools: {
      connection: 'connect-existing-real-devtools'
    },
    scenes
  })

  writeBytes(path.join(artifactDir, required.comparisonOverview))
  ;(required.componentComparisons || []).forEach((comparison) => writeBytes(path.join(artifactDir, comparison)))
  writeBytes(path.join(artifactDir, required.scorecardMd), 1200)

  const overlayMetrics = [
    {
      target: 'overlays-pass36l/news-target.png',
      candidate: 'overlays-pass36l/news-candidate.png',
      overlay: 'overlays-pass36l/news-overlay.png'
    }
  ]
  overlayMetrics.forEach((metric) => {
    writeBytes(path.join(artifactDir, metric.target), 1200)
    writeBytes(path.join(artifactDir, metric.candidate), 1200)
    writeBytes(path.join(artifactDir, metric.overlay), 1200)
  })
  writeJson(path.join(artifactDir, required.overlayMetrics), { metrics: overlayMetrics })
  writeJson(path.join(artifactDir, required.strictGateJson), { status: 'pass', failures: [] })

  const uniqueScreens = Array.from(new Set(required.screenshots.map((shot) => shot.id)))
  const scoreRows = uniqueScreens.map((screen) => ({
    screen,
    total: 92,
    gate: 'pass',
    scores: {
      layout_fidelity: 91,
      visual_hierarchy: 90,
      component_detail: 90,
      information_fidelity: 92,
      adaptation_quality: 91
    }
  }))
  writeJson(path.join(artifactDir, required.scorecardJson), {
    pass: 'pass36l',
    gateStatus: 'pass',
    strictGateEligible: true,
    runtimeScreenshot: true,
    total: 92,
    comparisonOverview: required.comparisonOverview,
    screens: scoreRows
  })

  return { root, artifactDir, contract }
}

test('ui v2.1 strict cut decomposition covers the approved targets and key regions', () => {
  const decomposition = readJson('artifacts/ui-v2-1-strict-restoration/target-decomposition.json')
  const screens = decomposition.screens || {}

  assert.equal(decomposition.visualBenchmark.news, 'artifacts/ui-v2-1-strict-restoration/normalized-targets/news-target-780.png')
  assert.equal(decomposition.visualBenchmark.builds, 'artifacts/ui-v2-1-strict-restoration/normalized-targets/builds-target-780.png')
  assert.equal(decomposition.visualBenchmark.workbench, 'artifacts/ui-v2-1-strict-restoration/normalized-targets/workbench-target-780.png')
  assert.equal(decomposition.mockChromePolicy.mockChromeRemovedFromBenchmarks, true)
  assert.match(decomposition.mockChromePolicy.reason, /real system chrome/)
  assert.ok(decomposition.mockChromePolicy.forbiddenInBenchmarks.includes('generated WeChat capsule'))
  assert.ok(decomposition.rules.some((rule) => /chrome-free normalized target images/.test(rule)))
  assert.ok(decomposition.rules.some((rule) => /Generated phone chrome/.test(rule)))
  assert.deepEqual(screens.news.targetSize, [780, 1826])
  assert.deepEqual(screens.builds.targetSize, [780, 1626])
  assert.deepEqual(screens.workbench.targetSize, [780, 1809])

  const expectedRegions = {
    news: ['nav_safe_area', 'intelligence_panel', 'hero_visual', 'channel_dock', 'ranked_feed'],
    builds: ['nav_safe_area', 'spec_console', 'workbench_panel', 'workflow_timeline'],
    workbench: ['nav_safe_area', 'identity_panel', 'verdict_slab', 'module_dock', 'evidence_ledger']
  }

  Object.entries(expectedRegions).forEach(([screen, ids]) => {
    const actual = new Set(((screens[screen] || {}).regions || []).map((region) => region.id))
    ids.forEach((id) => assert.ok(actual.has(id), `${screen} should decompose ${id}`))
  })

  assert.ok(decomposition.requiredStateCoverage.includes('workbench_ready'))
  assert.ok(decomposition.requiredStateCoverage.includes('news_scrolled_ranked_feed'))
  assert.equal(decomposition.scoreGate.minTotal, 90)
  assert.equal(decomposition.scoreGate.categoryFloors.layoutRestoration, 80)
})

test('ui v2.1 production manifest keeps imagegen assets low-semantic', () => {
  const manifest = readJson('assets/generated/ui-v2-1-slices/20260703/strict-production-manifest.json')

  assert.match(manifest.assetClasses.low_semantic_material.description, /panel furniture/)
  assert.match(manifest.assetClasses.product_ia_channel_marker.description, /fixed product information architecture categories/)
  assert.match(manifest.assetClasses.generated_category_thumbnail_fallback.allowedUse, /real article visualUrl is missing/)
  assert.match(manifest.assetClasses.real_wow_object_icon_source.allowedUse, /gameAsset\.iconUrl/)
  assert.match(manifest.assetClasses.reference_only_target.forbiddenUse.join('\n'), /WXML production rendering/)
  assert.match(manifest.globalFactBoundary.join('\n'), /Forbidden: real WoW class\/spec\/talent\/gear icon/)
  assert.ok(manifest.realAssetSources.includes('gameAsset.iconUrl from backend payloads'))
  assert.ok(manifest.realAssetSources.includes('WebSim/Battle.net read models'))
  assert.ok(manifest.realAssetSources.includes('pages/common/wow-spec-assets.js verified official icon-name mapping'))

  const productionUi = readProductionUi()
  ;(manifest.referenceOnlyAssets || []).forEach((asset) => {
    const filename = asset.split('/').pop()
    assert.doesNotMatch(productionUi, new RegExp(filename.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), `${filename} must stay reference-only`)
  })

  const groups = manifest.groups || []
  assert.ok(groups.some((group) => group.id === 'workbench_verdict' && /buildWorkbenchState/.test(group.dataOwner)))
  assert.ok(groups.some((group) => group.id === 'news_hero_and_ranked_feed' && /visualUrl must win/.test(group.dataOwner)))
  assert.ok(groups.some((group) => group.id === 'news_channel_dock' && /category UI markers/.test(group.dataOwner)))
  assert.ok(groups.some((group) => group.id === 'builds_workbench_panel' && /No DPS/.test(group.dataOwner)))
})

test('ui v2.1 pass36x asset slice workflow audit keeps generated assets production-safe', () => {
  const audit = buildAssetSliceWorkflowAudit()

  assert.equal(audit.pass, 'pass36x_asset_slice_workflow_audit')
  assert.equal(audit.status, 'pass')
  assert.equal(audit.devtoolsTouched, false)
  assert.equal(audit.runtimeScreenshot, false)
  assert.deepEqual(audit.failures, [])
  assert.ok(audit.counts.productionAssets > 0)
  assert.ok(audit.counts.productionReferences > 0)
  assert.equal(audit.counts.referencesNotInManifest, 0)
  assert.equal(audit.counts.missingMaterialCoverage, 0)
  assert.ok(audit.counts.quarantinedAssets > 0)
  assert.ok(
    audit.quarantinedAssets.some((asset) => /verdict_status_badge_blocked_component/.test(asset)),
    'baked blocked status drafts should be quarantined, not production referenced'
  )
  assert.ok(
    audit.productionAssets.every((asset) => asset.exists && !asset.overBudget),
    'every production imagegen asset should exist and stay under the DevTools-safe budget'
  )
  assert.ok(
    Object.values(audit.sourceReferencesByFile).flat().every((asset) =>
      audit.productionAssets.some((item) => item.asset === asset)
    ),
    'every generated asset referenced by production source should be declared in strict manifest productionAssets'
  )
})

test('pass37 architecture input package locks architecture-first gates before page implementation', () => {
  const report = buildPass37ArchitectureInputPackage({ repoRoot: process.cwd() })

  assert.equal(report.status, 'design_locked')
  assert.equal(report.outputMode, 'architecture_input_only')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.deepEqual(PASS37_STATUS_WORDS, [
    'draft',
    'design_locked',
    'component_precheck',
    'runtime_verified',
    'blocked',
    'final_accepted'
  ])
  assert.deepEqual(PASS37_REQUIRED_ARTIFACTS, [
    'current',
    'target',
    'decomposition',
    'assets',
    'implementation',
    'overlays',
    'scorecard',
    'routes',
    'devtools'
  ])

  const pageIds = new Set(report.pageArchitecture.map((page) => page.id))
  for (const id of [
    'app_shell',
    'news_home',
    'builds_tab',
    'current_spec_workbench',
    'talent_simulator',
    'gear_simulator',
    'simc_flow',
    'chickenbro',
    'profile_templates'
  ]) {
    assert.ok(pageIds.has(id), `missing page architecture ${id}`)
  }

  const componentIds = new Set(report.componentContracts.map((component) => component.id))
  for (const id of [
    'AppNav',
    'PageFrame',
    'WowPanel',
    'StatusBadge',
    'ChannelDock',
    'RankedFeed',
    'ModuleDock',
    'EvidenceLedger',
    'WorkbenchHero'
  ]) {
    assert.ok(componentIds.has(id), `missing component contract ${id}`)
  }

  assert.equal(report.gates.runtime.status, 'incomplete')
  assert.match(report.gates.runtime.gate, /runtime_verified requires captureSafe=true/)
  assert.equal(report.gates.imagegenAsset.status, 'source_contract_passed')
  assert.equal(report.gates.devtoolsSafety.status, 'pass')
  assert.ok(report.verificationMatrix.stateCoverage.length >= 14)
  assert.ok(report.verificationMatrix.routeCoverage.every((row) => row.status === 'blocked'))

  const readiness = buildFinalReadinessReport({ repoRoot: process.cwd() })
  assert.equal(readiness.latestPass37ArchitectureInputPackage.present, true)
  assert.equal(readiness.latestPass37ArchitectureInputPackage.status, 'design_locked')
  assert.equal(readiness.latestPass37ArchitectureInputPackage.runtimeGate, 'incomplete')
  assert.ok(readiness.objectiveRequirements.some((item) => (
    item.id === 'pass37_architecture_input' &&
    item.status === 'design_locked' &&
    /runtime gate still incomplete/.test(item.evidence)
  )))
})

test('pass37 package keeps imagegen and DevTools boundaries strict', () => {
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-architecture-input-package.js',
    'utf8'
  )
  const report = buildPass37ArchitectureInputPackage({ repoRoot: process.cwd() })
  const markdown = renderPass37ArchitectureMarkdown(report)

  for (const action of [
    'cli open by default',
    'cli close by default',
    'cli auto loop',
    'login probe by default',
    'clear cache',
    'restart DevTools',
    'switch appid',
    'switch project'
  ]) {
    assert.ok(PASS37_PROHIBITED_DEVTOOLS_ACTIONS.includes(action), `missing prohibited action ${action}`)
    assert.ok(report.gates.devtoolsSafety.prohibitedByDefault.includes(action), `report missing ${action}`)
  }

  assert.ok(report.assetManifestRequirements.productionBan.includes('real WoW icon generated by imagegen'))
  assert.ok(report.assetManifestRequirements.productionBan.includes('DPS, score, tier, improvement priority, or readiness conclusion generated by imagegen'))
  assert.match(markdown, /No true mini-program screenshot means no final visual score/)
  assert.doesNotMatch(markdown, /[—–]/, 'pass37 markdown should not use em dash or en dash separators')

  assert.doesNotMatch(source, /require\('node:child_process'\)/)
  assert.doesNotMatch(source, /execFile|spawn|osascript/)
})

test('pass37 component redlines lock target geometry and fixture coverage', () => {
  const report = buildPass37ComponentRedlines({ repoRoot: process.cwd() })

  assert.equal(report.status, 'design_locked')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.deepEqual(PASS37_REQUIRED_FIXTURE_STATES, [
    'min',
    'standard',
    'long_text',
    'missing_icon',
    'blocked',
    'partial',
    'stale',
    'ready',
    'source_reference'
  ])
  assert.deepEqual(PASS37_VIEWPORT_PROFILES.map((viewport) => viewport.id), [
    'compact',
    'standard',
    'large'
  ])
  assert.deepEqual(report.counts, {
    components: 9,
    requiredFixtureStates: 9,
    viewportProfiles: 3,
    harnessFixtures: 243,
    missingTargetRegions: 0
  })

  const byId = Object.fromEntries(report.componentRedlines.map((component) => [component.id, component]))
  assert.equal(byId.ChannelDock.targetRegions[0].metrics.width, 707)
  assert.equal(byId.ChannelDock.targetRegions[0].metrics.height, 131)
  assert.equal(byId.RankedFeed.targetRegions[0].metrics.width, 719)
  assert.equal(byId.RankedFeed.targetRegions[0].metrics.height, 717)
  assert.equal(byId.ModuleDock.targetRegions[0].metrics.width, 745)
  assert.equal(byId.ModuleDock.targetRegions[0].metrics.height, 235)
  assert.equal(byId.EvidenceLedger.targetRegions[0].metrics.width, 749)
  assert.equal(byId.EvidenceLedger.targetRegions[0].metrics.height, 553)
  assert.ok(byId.StatusBadge.targetRegions.some((region) => region.ref === 'workbench.verdict_slab'))
  assert.ok(byId.StatusBadge.requiredChecks.includes('glyphCenterDrift <= 4rpx'))
  assert.ok(byId.WorkbenchHero.requiredChecks.includes('fakeDpsScoreTierPriority == 0'))

  const readiness = buildFinalReadinessReport({ repoRoot: process.cwd() })
  assert.equal(readiness.latestPass37ComponentRedlines.present, true)
  assert.equal(readiness.latestPass37ComponentRedlines.status, 'design_locked')
  assert.equal(readiness.latestPass37ComponentRedlines.harnessFixtures, 243)
  assert.equal(readiness.latestPass37ComponentRedlines.nextGateStatus, 'component_precheck_required')
  assert.ok(readiness.objectiveRequirements.some((item) => (
    item.id === 'pass37_component_redlines' &&
    item.status === 'design_locked' &&
    /243 harness fixtures/.test(item.evidence)
  )))
})

test('pass37 component redline markdown and fixture board stay source-only', () => {
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-component-redlines.js',
    'utf8'
  )
  const report = buildPass37ComponentRedlines({ repoRoot: process.cwd() })
  const markdown = renderPass37ComponentRedlinesMarkdown(report)
  const html = renderPass37ComponentRedlinesFixtureHtml(report)

  assert.match(markdown, /component_precheck_required/)
  assert.match(markdown, /ChannelDock/)
  assert.match(markdown, /news\.channel_dock: 707x131rpx/)
  assert.match(html, /This HTML is a fixture board only/)
  assert.match(html, /data-component="StatusBadge"/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(html, /[—–]/)
  assert.doesNotMatch(source, /require\('node:child_process'\)/)
  assert.doesNotMatch(source, /execFile|spawn|osascript|connectMiniProgram|WECHAT_AUTOMATOR_PORT/)
})

test('pass37 component precheck records browser harness crops without becoming runtime evidence', () => {
  const plan = buildPass37ComponentPrecheckPlan()
  const report = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-component-precheck/pass37-component-precheck.json'
  )

  assert.equal(plan.pass, 'pass37_component_precheck')
  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
  assert.equal(plan.strictGateEligible, false)
  assert.equal(plan.expectedComponents, 9)
  assert.equal(plan.expectedHarnessFixtures, 243)
  assert.match(PASS37_PRECHECK_FORBIDDEN_CHROME, /battery/)
  assert.ok(PASS37_PRECHECK_REQUIRED_TARGET_TEXT.includes('news.channel_dock: 707x131rpx'))
  assert.ok(PASS37_PRECHECK_REQUIRED_TARGET_TEXT.includes('workbench.evidence_ledger: 749x553rpx'))

  assert.equal(report.status, 'component_precheck')
  assert.equal(report.precheckPassed, true)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.checks.filter((item) => item.status === 'pass').length, report.checks.length)
  assert.equal(report.checks.length, 13)
  assert.equal(report.crops.length, 9)
  assert.ok(report.crops.every((crop) => fs.existsSync(crop.path)))
  assert.ok(fs.existsSync(report.boardScreenshotPath))
  assert.ok(fs.existsSync(report.contactSheetScreenshotPath))
  const statusBadgeCheck = report.checks.find((item) => item.component === 'StatusBadge')
  assert.ok(statusBadgeCheck, 'component precheck should include StatusBadge measurement check')
  assert.equal(statusBadgeCheck.assetFit.objectFit, 'contain')
  assert.equal(statusBadgeCheck.glyphCenter.driftPx, 0)
  assert.equal(statusBadgeCheck.textMetrics.headerTitlePx, 18)
  assert.equal(statusBadgeCheck.textMetrics.targetPx, 13)
  assert.equal(statusBadgeCheck.textMetrics.slotPx, 11)
  assert.equal(statusBadgeCheck.textMetrics.statePx, 11)
  assert.ok(report.checks
    .filter((item) => item.component)
    .every((item) => Array.isArray(item.slotRects) && item.slotRects.length >= 3))

  const readiness = buildFinalReadinessReport({ repoRoot: process.cwd() })
  assert.equal(readiness.status, 'incomplete')
  assert.equal(readiness.latestPass37ComponentPrecheck.present, true)
  assert.equal(readiness.latestPass37ComponentPrecheck.status, 'component_precheck')
  assert.equal(readiness.latestPass37ComponentPrecheck.precheckPassed, true)
  assert.equal(readiness.latestPass37ComponentPrecheck.strictGateEligible, false)
  assert.ok(readiness.objectiveRequirements.some((item) => (
    item.id === 'pass37_component_precheck' &&
    item.status === 'component_precheck' &&
    /13\/13 browser checks/.test(item.evidence)
  )))
})

test('pass37 component precheck runner stays browser-only and avoids DevTools control', () => {
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/run-pass37-component-precheck.js',
    'utf8'
  )
  const markdown = fs.readFileSync(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-component-precheck/pass37-component-precheck.md',
    'utf8'
  )

  assert.match(markdown, /Status: component_precheck/)
  assert.match(markdown, /Strict gate eligible: false/)
  assert.match(markdown, /Strict Measurements/)
  assert.match(markdown, /StatusBadge: text=\(header 18px, target 13px, slot 11px, state 11px\); assetFit=contain/)
  assert.match(markdown, /glyph=0px drift/)
  assert.match(markdown, /Final visual acceptance still requires true WeChat mini-program screenshots/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /cli\s+open|cli\s+close|cli\s+auto|cli\s+login|osascript/)
})

test('pass37 implementation map binds news target slots to real source files', () => {
  const report = buildPass37ImplementationMap({ repoRoot: process.cwd() })
  const markdown = renderPass37ImplementationMapMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-implementation-map.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-implementation-map.js',
    'utf8'
  )

  assert.equal(report.status, 'implementation_mapped')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.outputMode, 'source_mapping_only')
  assert.equal(report.counts.components, 2)
  assert.equal(report.counts.mappedSlots, 13)
  assert.equal(report.counts.failures, 0)
  assert.deepEqual(report.scope.mappedComponents, ['ChannelDock', 'RankedFeed'])
  assert.ok(PASS37_IMPLEMENTATION_COMPONENTS.some((item) => item.id === 'ChannelDock'))
  assert.ok(PASS37_IMPLEMENTATION_COMPONENTS.some((item) => item.id === 'RankedFeed'))

  const byId = Object.fromEntries(report.components.map((item) => [item.id, item]))
  assert.equal(byId.ChannelDock.targetRegion, 'news.channel_dock')
  assert.equal(byId.ChannelDock.targetMetrics.width, 707)
  assert.equal(byId.ChannelDock.targetMetrics.height, 131)
  assert.equal(byId.RankedFeed.targetRegion, 'news.ranked_feed')
  assert.equal(byId.RankedFeed.targetMetrics.width, 719)
  assert.equal(byId.RankedFeed.targetMetrics.height, 717)
  assert.ok(byId.ChannelDock.productionFiles.includes('components/channel-dock/channel-dock.wxml'))
  assert.ok(byId.RankedFeed.productionFiles.includes('components/ranked-feed/ranked-feed.wxml'))
  assert.ok(byId.ChannelDock.dataSources.includes('NEWS_TAB_DEFS'))
  assert.ok(byId.RankedFeed.dataSources.includes('RANKED_FOCUS_COUNT = 5'))
  assert.ok(byId.ChannelDock.slots.some((slot) => slot.id === 'sixTabs' && slot.selector === '.news-tab-item'))
  assert.ok(byId.RankedFeed.slots.some((slot) => slot.id === 'thumbnail' && slot.selector === '.focus-thumb'))
  assert.ok(byId.RankedFeed.factsThatMustRemainReal.some((item) => /Article image wins/.test(item)))
  assert.ok(byId.ChannelDock.forbiddenImplementationMoves.some((item) => /fake read counts/.test(item)))
  assert.deepEqual(report.failures, [])

  assert.equal(artifact.status, 'implementation_mapped')
  assert.equal(artifact.strictGateEligible, false)
  assert.equal(artifact.nextGate.status, 'browser_layout_audit_required')
  assert.match(markdown, /ChannelDock/)
  assert.match(markdown, /RankedFeed/)
  assert.match(markdown, /news\.channel_dock: 707x131rpx/)
  assert.match(markdown, /news\.ranked_feed: 719x717rpx/)
  assert.match(markdown, /This artifact maps implementation surfaces only/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /cli\s+open|cli\s+close|cli\s+auto|cli\s+login|osascript/)

  const readiness = buildFinalReadinessReport({ repoRoot: process.cwd() })
  assert.equal(readiness.status, 'incomplete')
  assert.equal(readiness.latestPass37ImplementationMap.present, true)
  assert.equal(readiness.latestPass37ImplementationMap.status, 'implementation_mapped')
  assert.equal(readiness.latestPass37ImplementationMap.strictGateEligible, false)
  assert.ok(readiness.objectiveRequirements.some((item) => (
    item.id === 'pass37_implementation_map' &&
    item.status === 'implementation_mapped' &&
    /2 news components, 13 slots/.test(item.evidence)
  )))
})

test('pass37 news implementation layout audit records actual source crops without runtime promotion', () => {
  const plan = buildPass37NewsImplementationLayoutAuditPlan()
  const report = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-implementation-layout-audit/pass37-news-implementation-layout-audit.json'
  )
  const markdown = fs.readFileSync(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-implementation-layout-audit/pass37-news-implementation-layout-audit.md',
    'utf8'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/run-pass37-news-implementation-layout-audit.js',
    'utf8'
  )

  assert.equal(plan.pass, 'pass37_news_implementation_layout_audit')
  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
  assert.equal(plan.strictGateEligible, false)
  assert.equal(plan.sourceImplementationMapStatus, 'implementation_mapped')
  assert.equal(plan.sourcePageIntegrationMapStatus, 'page_integration_mapped')
  assert.equal(plan.sourcePageIntegrationMapComponentBindings, 45)
  assert.match(plan.forbiddenVisibleChromePattern, /battery/)
  assert.match(plan.forbiddenStrongClaimPattern, /综合评分/)
  assert.ok(PASS37_NEWS_LAYOUT_RULES.some((rule) => rule.id === 'page_integration_map_is_ready'))
  assert.ok(PASS37_NEWS_LAYOUT_RULES.some((rule) => rule.id === 'page_integration_strict_system_gate_is_ready'))
  assert.ok(PASS37_NEWS_LAYOUT_RULES.some((rule) => rule.id === 'news_surface_foundation_slots_present'))
  assert.ok(PASS37_NEWS_LAYOUT_RULES.some((rule) => rule.id === 'channel_dock_target_frame'))
  assert.ok(PASS37_NEWS_LAYOUT_RULES.some((rule) => rule.id === 'ranked_feed_target_frame'))
  assert.deepEqual(PASS37_NEWS_LAYOUT_CROP_TARGETS.map((target) => target.id), [
    'channel-section',
    'channel-dock',
    'ranked-feed-section',
    'ranked-feed-root'
  ])

  assert.equal(report.status, 'browser_layout_audit')
  assert.equal(report.auditPassed, true)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.sourceImplementationMapStatus, 'implementation_mapped')
  assert.equal(report.sourcePageIntegrationMapStatus, 'page_integration_mapped')
  assert.equal(report.sourcePageIntegrationMapComponentBindings, 45)
  assert.equal(report.checks.filter((item) => item.status === 'pass').length, report.checks.length)
  assert.equal(report.checks.length, 11)
  assert.ok(report.checks.some((item) => item.id === 'page_integration_map_is_ready' && item.status === 'pass'))
  assert.ok(report.checks.some((item) => item.id === 'page_integration_strict_system_gate_is_ready' && item.status === 'pass'))
  assert.ok(report.checks.some((item) => item.id === 'news_surface_foundation_slots_present' && item.status === 'pass'))
  assert.equal(report.crops.length, 4)
  assert.ok(report.crops.every((crop) => crop.path && fs.existsSync(crop.path)))
  assert.ok(report.crops.some((crop) => crop.id === 'channel-dock' && crop.width >= 362 && crop.width <= 372))
  assert.ok(report.crops.some((crop) => crop.id === 'ranked-feed-root' && crop.width >= 368 && crop.width <= 376))
  assert.ok(fs.existsSync(report.boardScreenshotPath))
  assert.ok(fs.existsSync(report.contactSheetScreenshotPath))
  assert.match(markdown, /Status: browser_layout_audit/)
  assert.match(markdown, /Component crops: 4/)
  assert.match(markdown, /Final pass36 acceptance still requires captureSafe=true WeChat mini-program screenshots/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /cli\s+open|cli\s+close|cli\s+auto|cli\s+login|osascript/)

  const readiness = buildFinalReadinessReport({ repoRoot: process.cwd() })
  assert.equal(readiness.status, 'incomplete')
  assert.equal(readiness.latestPass37NewsImplementationLayoutAudit.present, true)
  assert.equal(readiness.latestPass37NewsImplementationLayoutAudit.status, 'browser_layout_audit')
  assert.equal(readiness.latestPass37NewsImplementationLayoutAudit.strictGateEligible, false)
  assert.ok(readiness.objectiveRequirements.some((item) => (
    item.id === 'pass37_news_implementation_layout_audit' &&
    item.status === 'browser_layout_audit' &&
    /11\/11 checks/.test(item.evidence)
  )))
})

test('pass37 news target delta audit keeps target-current visual comparison source-only', () => {
  const report = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-target-delta-audit/pass37-news-target-delta-audit.json'
  )
  const markdown = fs.readFileSync(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-target-delta-audit/pass37-news-target-delta-audit.md',
    'utf8'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-news-target-delta-audit.py',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_news_target_delta_audit')
  assert.equal(report.status, 'source_delta_recorded')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.components.length, 2)
  assert.ok(fs.existsSync(report.board))
  assert.ok(fs.existsSync(report.jsonPath))
  assert.ok(fs.existsSync(report.markdownPath))
  for (const component of report.components) {
    assert.ok(['channel_dock', 'ranked_feed'].includes(component.id))
    assert.ok(fs.existsSync(component.target), `${component.id} target should exist`)
    assert.ok(fs.existsSync(component.currentBrowserCrop), `${component.id} current browser crop should exist`)
    assert.ok(fs.existsSync(component.currentResized), `${component.id} resized crop should exist`)
    assert.ok(fs.existsSync(component.deltaHeatmap), `${component.id} heatmap should exist`)
    assert.equal(typeof component.metrics.pixelSimilarity, 'number')
    assert.equal(typeof component.metrics.edgeDelta, 'number')
  }
  assert.match(markdown, /source_delta_recorded/)
  assert.match(markdown, /not a runtime score|not an acceptance score/i)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /cli\s+open|cli\s+close|cli\s+auto|cli\s+login|osascript/)

  const readiness = buildFinalReadinessReport({ repoRoot: process.cwd() })
  assert.equal(readiness.latestPass37NewsTargetDeltaAudit.present, true)
  assert.equal(readiness.latestPass37NewsTargetDeltaAudit.status, 'source_delta_recorded')
  assert.equal(readiness.latestPass37NewsTargetDeltaAudit.strictGateEligible, false)
  assert.equal(readiness.latestPass37NewsTargetDeltaAudit.components, 2)
  assert.ok(readiness.objectiveRequirements.some((item) => (
    item.id === 'pass37_news_target_delta_audit' &&
    item.status === 'source_delta_recorded' &&
    /minPixelSimilarity=/.test(item.evidence)
  )))
})

test('pass37 recovery tickets freeze page edits behind production-ready tickets', () => {
  const report = buildPass37RecoveryTickets({ repoRoot: process.cwd() })
  const markdown = renderPass37RecoveryTicketsMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-recovery-tickets.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-recovery-tickets.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_recovery_tickets')
  assert.equal(report.status, 'recovery_tickets_locked')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.outputMode, 'source_contract_only')
  assert.equal(report.recoveryLock.status, 'pass37 recovery-lock')
  assert.equal(report.recoveryLock.pageEditingFrozen, true)
  assert.equal(report.recoveryLock.pageWritesAllowed, false)
  assert.deepEqual(PASS37_RECOVERY_TICKET_TYPES, [
    'architecture',
    'asset',
    'component',
    'data',
    'route',
    'verification'
  ])
  assert.equal(PASS37_RECOVERY_FOUNDATION_COMPONENTS.length, 9)
  assert.deepEqual(PASS37_RECOVERY_FOUNDATION_COMPONENTS.map((component) => component.id), [
    'AppNav',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusBadge',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger'
  ])
  assert.equal(PASS37_RECOVERY_SURFACES.length, 5)
  assert.deepEqual(report.surfaces.map((surface) => surface.id), [
    'news_home_and_feed',
    'builds_tab',
    'current_spec_workbench',
    'simulator_and_captain',
    'profile_templates'
  ])
  assert.equal(report.counts.surfaces, 5)
  assert.equal(report.counts.foundationComponents, 9)
  assert.equal(report.counts.requiredTicketTypes, 6)
  assert.equal(report.counts.tickets, 30)
  assert.equal(report.counts.missingProductionFiles, 0)
  assert.equal(report.counts.unknownComponents, 0)
  assert.deepEqual(report.failures, [])

  for (const surface of report.surfaces) {
    assert.equal(surface.status, 'recovery_ticket_locked')
    assert.equal(surface.pageWritesAllowed, false)
    assert.deepEqual(surface.tickets.map((ticket) => ticket.type), PASS37_RECOVERY_TICKET_TYPES)
    assert.equal(surface.tickets.length, 6)
    assert.ok(surface.tickets.every((ticket) => ticket.pageWritesAllowed === false))
    assert.equal(surface.missingProductionFiles.length, 0)
    assert.equal(surface.unknownComponents.length, 0)
  }

  const workbench = report.surfaces.find((surface) => surface.id === 'current_spec_workbench')
  assert.ok(workbench.components.includes('StatusBadge'))
  assert.ok(workbench.forbiddenFields.includes('DPS before SimC-ready'))
  assert.ok(workbench.routeSmoke.includes('ready SimC action'))
  assert.ok(workbench.verificationEvidence.some((item) => /five status runtime screenshots/.test(item)))

  const architectureTicket = workbench.tickets.find((ticket) => ticket.type === 'architecture')
  assert.ok(architectureTicket.architectureBoundary.some((item) => /page composes foundation components only/.test(item)))
  assert.ok(architectureTicket.nonGoals.includes('no page-level margin guessing'))
  const assetTicket = workbench.tickets.find((ticket) => ticket.type === 'asset')
  assert.equal(assetTicket.manifestRequired, true)
  assert.ok(assetTicket.semanticBoundary.some((item) => /imagegen can provide material/.test(item)))
  assert.ok(assetTicket.semanticBoundary.some((item) => /state base and glyph stay separate/.test(item)))
  const verificationTicket = workbench.tickets.find((ticket) => ticket.type === 'verification')
  assert.equal(verificationTicket.maxStatusWithoutRuntime, 'source/browser evidence')
  assert.ok(verificationTicket.gates.includes('captureSafe=true mini-program screenshot'))

  assert.equal(artifact.status, 'recovery_tickets_locked')
  assert.equal(artifact.recoveryLock.pageEditingFrozen, true)
  assert.equal(artifact.recoveryLock.pageWritesAllowed, false)
  assert.equal(artifact.nextGate.status, 'foundation_component_contract_required')
  assert.equal(readinessArtifact.latestPass37RecoveryTickets.status, 'recovery_tickets_locked')
  assert.equal(readinessArtifact.latestPass37RecoveryTickets.pageEditingFrozen, true)
  assert.equal(readinessArtifact.latestPass37RecoveryTickets.pageWritesAllowed, false)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_recovery_tickets' &&
    item.status === 'recovery_tickets_locked' &&
    /5 surfaces, 9 foundation components, 30 tickets/.test(item.evidence)
  )))

  assert.match(markdown, /pass37 Recovery Tickets/)
  assert.match(markdown, /Page editing frozen: true/)
  assert.match(markdown, /Foundation components: 9/)
  assert.match(markdown, /Tickets: 30/)
  assert.match(markdown, /Final acceptance still requires captureSafe=true WeChat mini-program screenshots/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 foundation contracts lock keep replace quarantine before page rewrites', () => {
  const report = buildPass37FoundationContracts({ repoRoot: process.cwd() })
  const markdown = renderPass37FoundationContractsMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-contracts.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-contracts.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_foundation_contracts')
  assert.equal(report.status, 'foundation_contract_locked')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.outputMode, 'source_contract_only')
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.sourceRecoveryTickets.status, 'recovery_tickets_locked')
  assert.deepEqual(PASS37_FOUNDATION_IDS, [
    'AppNav',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusBadge',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger'
  ])
  assert.equal(Object.keys(PASS37_FOUNDATION_CONTRACT_DETAILS).length, 9)
  assert.equal(PASS37_KEEP_REPLACE_QUARANTINE.length, 5)
  assert.equal(report.counts.foundationContracts, 9)
  assert.equal(report.counts.surfaces, 5)
  assert.equal(report.counts.dispositionEntries, 32)
  assert.equal(report.counts.keepEntries, 16)
  assert.equal(report.counts.replaceEntries, 9)
  assert.equal(report.counts.quarantineEntries, 7)
  assert.equal(report.counts.contractFailures, 0)
  assert.equal(report.counts.dispositionFailures, 0)
  assert.deepEqual(report.failures, [])

  const byId = Object.fromEntries(report.foundationContracts.map((item) => [item.id, item]))
  assert.equal(byId.AppNav.pageCanOverrideInternals, false)
  assert.equal(byId.PageFrame.geometry.defaultGutter, '24rpx')
  assert.equal(byId.MaterialImage.geometry.referenceOnlyInProduction, '0')
  assert.equal(byId.GameObjectIcon.geometry.fakeObjectIconAllowed, false)
  assert.equal(byId.StatusBadge.geometry.bakedStateImageAllowed, false)
  assert.ok(byId.StatusBadge.stateCoverage.includes('question'))
  assert.ok(byId.StatusBadge.sourceBoundary.some((item) => /Pages pass status/.test(item)))
  assert.equal(byId.ActionButton.geometry.preferredPrimaryHeight, '72rpx')
  assert.equal(byId.ModuleCard.geometry.metricAboveMeta, true)
  assert.equal(byId.EvidenceLedger.geometry.rowMinHeight, '88rpx')
  assert.ok(byId.EvidenceLedger.stateCoverage.includes('source_reference'))

  const workbenchMap = report.keepReplaceQuarantine.find((surface) => surface.surfaceId === 'current_spec_workbench')
  assert.equal(workbenchMap.status, 'disposition_locked')
  assert.deepEqual(workbenchMap.counts, { keep: 3, replace: 2, quarantine: 2, total: 7 })
  assert.ok(workbenchMap.entries.some((entry) => entry.action === 'keep' && entry.id === 'workbench_state_model'))
  assert.ok(workbenchMap.entries.some((entry) => entry.action === 'replace' && entry.id === 'workbench_wxml_layout'))
  assert.ok(workbenchMap.entries.some((entry) => entry.action === 'quarantine' && entry.id === 'baked_status_badges'))

  assert.equal(artifact.status, 'foundation_contract_locked')
  assert.equal(artifact.nextGate.status, 'source_component_harness_required')
  assert.equal(readinessArtifact.latestPass37FoundationContracts.status, 'foundation_contract_locked')
  assert.equal(readinessArtifact.latestPass37FoundationContracts.sourceRecoveryTicketsStatus, 'recovery_tickets_locked')
  assert.equal(readinessArtifact.latestPass37FoundationContracts.pageWritesAllowed, false)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_foundation_contracts' &&
    item.status === 'foundation_contract_locked' &&
    /9 foundation components, 32 keep\/replace\/quarantine entries/.test(item.evidence)
  )))

  assert.match(markdown, /pass37 Foundation Contracts/)
  assert.match(markdown, /Status: foundation_contract_locked/)
  assert.match(markdown, /Keep entries: 16/)
  assert.match(markdown, /Replace entries: 9/)
  assert.match(markdown, /Quarantine entries: 7/)
  assert.match(markdown, /source-only harness for AppNav/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 foundation harness crops source components before page rewrites', () => {
  const plan = buildPass37FoundationHarnessPlan()
  const report = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-harness/pass37-foundation-harness.json'
  )
  const markdown = fs.readFileSync(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-harness/pass37-foundation-harness.md',
    'utf8'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/run-pass37-foundation-harness.js',
    'utf8'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )

  assert.equal(plan.pass, 'pass37_foundation_harness')
  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
  assert.equal(plan.strictGateEligible, false)
  assert.equal(plan.browserHarness, true)
  assert.equal(plan.expectedComponents, 9)
  assert.deepEqual(PASS37_FOUNDATION_HARNESS_CROP_TARGETS, [
    'AppNav',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusBadge',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger'
  ])
  assert.match(PASS37_FOUNDATION_HARNESS_FORBIDDEN_CHROME, /battery/)
  assert.match(PASS37_FOUNDATION_HARNESS_FORBIDDEN_CHROME, /Wi-Fi|wi-fi/i)

  assert.equal(report.status, 'foundation_harness')
  assert.equal(report.precheckPassed, true)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.browserHarness, true)
  assert.equal(report.sourceFoundationContractsStatus, 'foundation_contract_locked')
  assert.equal(report.checks.filter((item) => item.status === 'pass').length, report.checks.length)
  assert.equal(report.checks.length, 14)
  assert.ok(report.checks.some((item) => item.id === 'status_badge_base_glyph_center' && item.dx === 0 && item.dy === 0))
  assert.ok(report.checks.some((item) => item.id === 'action_button_touch_height' && item.height >= 48))
  assert.equal(report.crops.length, 9)
  assert.ok(report.crops.some((crop) => crop.component === 'EvidenceLedger'))
  assert.ok(report.crops.every((crop) => crop.path && fs.existsSync(crop.path)))
  assert.ok(fs.existsSync(report.boardScreenshotPath))
  assert.ok(fs.existsSync(report.contactSheetScreenshotPath))
  assert.deepEqual(report.failures, [])

  assert.equal(readinessArtifact.latestPass37FoundationHarness.status, 'foundation_harness')
  assert.equal(readinessArtifact.latestPass37FoundationHarness.precheckPassed, true)
  assert.equal(readinessArtifact.latestPass37FoundationHarness.sourceFoundationContractsStatus, 'foundation_contract_locked')
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_foundation_harness' &&
    item.status === 'foundation_harness' &&
    /14\/14 source browser checks/.test(item.evidence)
  )))

  assert.match(markdown, /Status: foundation_harness/)
  assert.match(markdown, /Component crops: 9/)
  assert.match(markdown, /Final visual acceptance still requires true WeChat mini-program screenshots/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 page integration map binds every surface to foundation components', () => {
  const report = buildPass37PageIntegrationMap({ repoRoot: process.cwd() })
  const markdown = renderPass37PageIntegrationMapMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-page-integration-map.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-page-integration-map.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_page_integration_map')
  assert.equal(report.status, 'page_integration_mapped')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.sourceRecoveryTicketsStatus, 'recovery_tickets_locked')
  assert.equal(report.sourceFoundationContractsStatus, 'foundation_contract_locked')
  assert.equal(report.sourceFoundationHarnessStatus, 'foundation_harness')
  assert.deepEqual(PASS37_PAGE_INTEGRATION_SURFACES, [
    'news_home_and_feed',
    'builds_tab',
    'current_spec_workbench',
    'simulator_and_captain',
    'profile_templates'
  ])
  assert.deepEqual(PASS37_PAGE_INTEGRATION_FOUNDATIONS, [
    'AppNav',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusBadge',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger'
  ])
  assert.equal(report.counts.surfaces, 5)
  assert.equal(report.counts.foundationComponents, 9)
  assert.equal(report.counts.componentBindings, 45)
  assert.equal(report.counts.cropBackedBindings, 45)
  assert.equal(report.counts.ownershipBackedBindings, 45)
  assert.equal(report.counts.packetCompleteSurfaces, 5)
  assert.equal(report.counts.missingProductionFiles, 0)
  assert.equal(report.counts.routeSmokeItems >= 20, true)
  assert.deepEqual(report.failures, [])

  for (const surface of report.surfaceIntegrations) {
    assert.equal(surface.status, 'page_integration_mapped')
    assert.equal(surface.pageWritesAllowed, false)
    assert.equal(surface.strictPacketGate.complete, true)
    assert.deepEqual(surface.strictPacketGate.present, PASS37_STRICT_REQUIRED_PACKETS)
    assert.equal(surface.ownershipBackedBindings, 9)
    assert.equal(surface.componentBindings.length, 9)
    assert.equal(surface.missingProductionFiles.length, 0)
    assert.ok(surface.keepTargets.length > 0)
    assert.ok(surface.replaceTargets.length > 0)
    assert.ok(surface.quarantineTargets.length > 0)
    assert.deepEqual(surface.componentBindings.map((binding) => binding.componentId), PASS37_PAGE_INTEGRATION_FOUNDATIONS)
    assert.ok(surface.componentBindings.every((binding) => binding.status === 'mapped_with_ownership_and_crop_evidence'))
    assert.ok(surface.componentBindings.every((binding) => binding.cropEvidence && fs.existsSync(binding.cropEvidence)))
    assert.ok(surface.componentBindings.every((binding) => binding.ownershipEvidence.notClassOnly === true))
    assert.ok(surface.componentBindings.every((binding) => binding.ownershipEvidence.sourceBoundaryCount > 0))
  }

  assert.equal(
    PASS37_PAGE_INTEGRATION_ROLES.news_home_and_feed.PageFrame.integrationMode,
    'replace_page_shell'
  )
  assert.equal(
    PASS37_PAGE_INTEGRATION_ROLES.current_spec_workbench.StatusBadge.integrationMode,
    'primary_state_owner'
  )
  assert.ok(
    PASS37_PAGE_INTEGRATION_ROLES.current_spec_workbench.MaterialImage.acceptance
      .some((item) => /shield base and exclamation/.test(item))
  )
  assert.equal(
    PASS37_PAGE_INTEGRATION_ROLES.current_spec_workbench.EvidenceLedger.integrationMode,
    'primary_evidence_owner'
  )
  const newsSurface = report.surfaceIntegrations.find((surface) => surface.surfaceId === 'news_home_and_feed')
  assert.ok(newsSurface.replaceTargets.some((entry) => entry.id === 'news_page_shell_styles'))
  const workbenchSurface = report.surfaceIntegrations.find((surface) => surface.surfaceId === 'current_spec_workbench')
  assert.ok(workbenchSurface.quarantineTargets.some((entry) => entry.id === 'baked_status_badges'))

  assert.equal(artifact.status, 'page_integration_mapped')
  assert.equal(artifact.counts.componentBindings, 45)
  assert.equal(artifact.counts.ownershipBackedBindings, 45)
  assert.equal(artifact.counts.packetCompleteSurfaces, 5)
  assert.equal(artifact.nextGate.status, 'controlled_surface_integration_required')
  assert.equal(readinessArtifact.latestPass37PageIntegrationMap.status, 'page_integration_mapped')
  assert.equal(readinessArtifact.latestPass37PageIntegrationMap.componentBindings, 45)
  assert.equal(readinessArtifact.latestPass37PageIntegrationMap.cropBackedBindings, 45)
  assert.equal(readinessArtifact.latestPass37PageIntegrationMap.ownershipBackedBindings, 45)
  assert.equal(readinessArtifact.latestPass37PageIntegrationMap.packetCompleteSurfaces, 5)
  assert.equal(readinessArtifact.latestPass37PageIntegrationMap.pageWritesAllowed, false)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_page_integration_map' &&
    item.status === 'page_integration_mapped' &&
    /45 ownership-backed bindings, 5 packet-complete surfaces/.test(item.evidence)
  )))

  assert.match(markdown, /pass37 Page Integration Map/)
  assert.match(markdown, /Component bindings: 45/)
  assert.match(markdown, /Ownership-backed bindings: 45/)
  assert.match(markdown, /Packet-complete surfaces: 5/)
  assert.match(markdown, /Strict packet gate: true/)
  assert.match(markdown, /controlled_surface_integration_required/)
  assert.match(markdown, /It does not create runtime evidence/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 strict system contract blocks page implementation behind system packets', () => {
  const report = buildPass37StrictSystemContract({ repoRoot: process.cwd() })
  const markdown = renderPass37StrictSystemContractMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-strict-system-contract.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-strict-system-contract.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_strict_system_contract')
  assert.equal(report.status, 'strict_system_contract_locked')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.outputMode, 'source_contract_only')
  assert.equal(report.sourceRecoveryTicketsStatus, 'recovery_tickets_locked')
  assert.deepEqual(report.sourceRecoveryTicketTypes, PASS37_STRICT_REQUIRED_PACKETS)
  assert.equal(report.sourceFoundationContractsStatus, 'foundation_contract_locked')
  assert.equal(report.sourcePageIntegrationMapStatus, 'page_integration_mapped')
  assert.equal(report.systemLock.status, 'pass37 strict-system-contract')
  assert.equal(report.systemLock.pageEditingFrozen, true)
  assert.equal(report.systemLock.pageWritesAllowed, false)
  assert.equal(report.systemLock.editPermitRequired, true)
  assert.equal(report.systemLock.pageLevelTuningAllowed, false)
  assert.equal(report.systemLock.foundationResetRequired, true)
  assert.equal(report.systemLock.allExistingSurfacePermitsSuspended, true)
  assert.equal(report.systemLock.scopedSourceEditsAllowed, false)
  assert.equal(report.foundationResetLock.status, 'foundation_reset_locked')
  assert.equal(report.foundationResetLock.scopedSourceEditsAllowed, false)
  assert.equal(report.foundationResetLock.allExistingSurfacePermitsSuspended, true)
  assert.ok(report.foundationResetLock.suspendedSurfacePermits.includes('news_home_and_feed'))
  assert.deepEqual(PASS37_STRICT_REQUIRED_PACKETS, [
    'architecture',
    'asset',
    'component',
    'data',
    'route',
    'verification'
  ])
  assert.equal(report.requiredPackets.length, 6)
  assert.ok(report.requiredPackets.every((packet) => packet.pageWritesAllowedWithoutPacket === false))
  assert.equal(PASS37_STRICT_FAILURE_DIAGNOSIS_LOCKS.length, 7)
  assert.equal(PASS37_STRICT_COMPONENT_OWNERSHIP_LOCKS.length, 9)
  assert.equal(PASS37_STRICT_PIXEL_MEASUREMENT_RULES.length, 8)
  assert.equal(PASS37_STRICT_ROUTE_INTERACTION_REQUIREMENTS.length, 10)
  assert.equal(PASS37_STRICT_FOUNDATION_RESET_GATES.length, 8)
  assert.equal(PASS37_STRICT_SUSPENDED_SURFACE_PERMITS.length, 1)
  assert.equal(PASS37_STRICT_EXECUTION_CONTROL_LOCKS.length, 8)
  assert.equal(PASS37_STRICT_IMPLEMENTATION_PERMIT_REQUIREMENTS.length, 11)
  assert.equal(PASS37_STRICT_EVIDENCE_PROMOTION_RULES.length, 5)
  assert.equal(PASS37_STRICT_ZERO_TOLERANCE_RUNTIME_FAILURES.length, 9)
  assert.equal(PASS37_STRICT_DEVTOOLS_PROHIBITED_ACTIONS.length, 9)
  assert.deepEqual(report.failures, [])

  const statusBadge = report.componentOwnershipLocks.find((item) => item.id === 'StatusBadge')
  assert.ok(statusBadge.requiredEvidence.includes('glyphCenterDrift <= 4rpx'))
  assert.ok(statusBadge.pageMustNot.some((item) => /bake status conclusion/.test(item)))
  const evidenceLedger = report.componentOwnershipLocks.find((item) => item.id === 'EvidenceLedger')
  assert.ok(evidenceLedger.owns.includes('blocker text'))
  assert.ok(evidenceLedger.requiredEvidence.includes('expanded ledger crop'))
  const devtoolsFailure = report.failureDiagnosisLocks.find((item) => item.id === 'devtools_state_instability')
  assert.equal(devtoolsFailure.owner, 'DevTools automation lock')
  assert.ok(devtoolsFailure.detection.includes('captureSafe=false'))
  assert.ok(report.devtoolsAutomation.actionLogRequired)
  assert.ok(report.devtoolsAutomation.captureSafeRequiredForRuntime)
  assert.ok(report.devtoolsAutomation.defaultAllowed.includes('low-disturbance health check'))
  assert.ok(report.devtoolsAutomation.defaultProhibited.includes('cli open'))
  assert.ok(report.devtoolsAutomation.defaultProhibited.includes('switch appid'))
  assert.ok(report.devtoolsAutomation.defaultProhibited.includes('delete user data'))
  assert.ok(report.devtoolsAutomation.incidentProtocol.includes('if captureSafe=false, stop at source/browser evidence'))
  const editPermitLock = report.executionControlLocks.find((item) => item.id === 'source_edit_permit_required')
  assert.match(editPermitLock.rule, /edit permit/)
  assert.ok(editPermitLock.blocks.includes('direct page-level CSS tuning'))
  assert.ok(report.implementationPermitRequirements.includes('allowed production files'))
  assert.ok(report.implementationPermitRequirements.includes('rollback or quarantine plan'))
  const runtimePromotion = report.evidencePromotionRules.find((item) => item.to === 'runtime_verified')
  assert.ok(runtimePromotion.requires.includes('fresh mini-program screenshots'))
  assert.ok(runtimePromotion.forbidden.includes('browser-only score'))
  assert.ok(report.zeroToleranceRuntimeFailures.some((item) => item.id === 'status_glyph_drift_or_baked_status'))
  assert.ok(report.zeroToleranceRuntimeFailures.some((item) => item.id === 'devtools_login_affecting_action_unlogged'))

  assert.equal(artifact.status, 'strict_system_contract_locked')
  assert.equal(artifact.systemLock.pageEditingFrozen, true)
  assert.equal(artifact.systemLock.pageWritesAllowed, false)
  assert.equal(artifact.systemLock.editPermitRequired, true)
  assert.equal(artifact.systemLock.pageLevelTuningAllowed, false)
  assert.equal(artifact.systemLock.foundationResetRequired, true)
  assert.equal(artifact.systemLock.allExistingSurfacePermitsSuspended, true)
  assert.equal(artifact.systemLock.scopedSourceEditsAllowed, false)
  assert.equal(artifact.foundationResetLock.status, 'foundation_reset_locked')
  assert.equal(artifact.foundationResetLock.scopedSourceEditsAllowed, false)
  assert.equal(artifact.counts.requiredPackets, 6)
  assert.equal(artifact.counts.componentOwners, 9)
  assert.equal(artifact.counts.foundationResetGates, 8)
  assert.equal(artifact.counts.suspendedSurfacePermits, 1)
  assert.equal(artifact.counts.executionControlLocks, 8)
  assert.equal(artifact.counts.implementationPermitRequirements, 11)
  assert.equal(artifact.counts.evidencePromotionRules, 5)
  assert.equal(artifact.counts.zeroToleranceRuntimeFailures, 9)
  assert.equal(artifact.counts.devtoolsProhibitedActions, 9)
  assert.equal(artifact.counts.recoveryTicketPacketTypes, 6)
  assert.deepEqual(artifact.sourceRecoveryTicketTypes, PASS37_STRICT_REQUIRED_PACKETS)
  assert.equal(artifact.nextGate.status, 'foundation_reset_gate_required_before_any_surface_permit')
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.status, 'strict_system_contract_locked')
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.pageEditingFrozen, true)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.pageWritesAllowed, false)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.editPermitRequired, true)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.pageLevelTuningAllowed, false)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.foundationResetStatus, 'foundation_reset_locked')
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.foundationResetRequired, true)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.allExistingSurfacePermitsSuspended, true)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.scopedSourceEditsAllowed, false)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.foundationResetGates, 8)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.suspendedSurfacePermits, 1)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.executionControlLocks, 8)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.implementationPermitRequirements, 11)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.evidencePromotionRules, 5)
  assert.equal(readinessArtifact.latestPass37StrictSystemContract.zeroToleranceRuntimeFailures, 9)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_strict_system_contract' &&
    item.status === 'strict_system_contract_locked' &&
    /6 required packets, 9 component owners, 7 failure diagnosis locks, 8 foundation reset gates, 1 suspended surface permits, 8 execution control locks/.test(item.evidence)
  )))

  assert.match(markdown, /pass37 Strict System Contract/)
  assert.match(markdown, /Foundation Reset Lock/)
  assert.match(markdown, /Suspended Surface Permits/)
  assert.match(markdown, /Required Packets/)
  assert.match(markdown, /StatusBadge/)
  assert.match(markdown, /EvidenceLedger/)
  assert.match(markdown, /Execution Control Locks/)
  assert.match(markdown, /Implementation Permit Requirements/)
  assert.match(markdown, /Evidence Promotion Rules/)
  assert.match(markdown, /Zero-Tolerance Runtime Failures/)
  assert.match(markdown, /Default prohibited: cli open; cli close; cli auto loop/)
  assert.match(markdown, /Final acceptance still requires captureSafe=true WeChat mini-program screenshots/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 news surface implementation permit is suspended behind foundation reset', () => {
  const report = buildPass37NewsSurfaceImplementationPermit({ repoRoot: process.cwd() })
  const markdown = renderPass37NewsSurfaceImplementationPermitMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-surface-implementation-permit.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-news-surface-implementation-permit.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_news_surface_implementation_permit')
  assert.equal(report.status, PASS37_NEWS_PERMIT_STATUS)
  assert.equal(report.surfaceId, PASS37_NEWS_PERMIT_SURFACE_ID)
  assert.equal(report.route, PASS37_NEWS_PERMIT_ROUTE)
  assert.equal(report.primaryOwner, PASS37_NEWS_PERMIT_PRIMARY_OWNER)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.scopedSourceEditsAllowed, false)
  assert.equal(report.unscopedPageWritesAllowed, false)
  assert.equal(report.suspension.status, 'foundation_reset_required')
  assert.match(report.suspension.reason, /Foundation Reset Lock/)
  assert.deepEqual(
    report.allowedProductionFiles.map((entry) => entry.file),
    PASS37_NEWS_PERMIT_ALLOWED_FILES.map((entry) => entry.file)
  )
  assert.deepEqual(
    report.forbiddenProductionFiles.map((entry) => entry.file),
    PASS37_NEWS_PERMIT_FORBIDDEN_FILES.map((entry) => entry.file)
  )
  assert.equal(report.allowedProductionFiles.length, 4)
  assert.equal(report.forbiddenProductionFiles.length, 6)
  assert.ok(report.allowedProductionFiles.some((entry) => (
    entry.file === 'pages/news/news.wxss' &&
    /gutter/.test(entry.scope)
  )))
  assert.ok(report.forbiddenProductionFiles.some((entry) => (
    entry.file === 'pages/news/news.js' &&
    /real data adapters/.test(entry.reason)
  )))
  assert.ok(report.forbiddenProductionFiles.some((entry) => (
    /news_full_layout_reference/.test(entry.file)
  )))
  assert.deepEqual(report.routeSmokePlan.map((item) => item.id), PASS37_NEWS_PERMIT_ROUTE_SMOKE.map((item) => item.id))
  assert.equal(report.routeSmokePlan.length, 4)
  assert.deepEqual(report.dataBoundary.forbiddenFakeFields, PASS37_NEWS_PERMIT_FORBIDDEN_FAKE_FIELDS)
  assert.ok(report.dataBoundary.realDataFields.includes('buildRankedHighlights(source)'))
  assert.ok(report.dataBoundary.objectSources.includes('published news payload thumbnail'))

  assert.equal(report.strictSystem.status, 'strict_system_contract_locked')
  assert.equal(report.strictSystem.editPermitRequired, true)
  assert.equal(report.strictSystem.pageLevelTuningAllowed, false)
  assert.equal(report.strictSystem.foundationResetStatus, 'foundation_reset_locked')
  assert.equal(report.strictSystem.allExistingSurfacePermitsSuspended, true)
  assert.equal(report.strictSystem.foundationResetGates, 8)
  assert.equal(report.pageIntegration.status, 'page_integration_mapped')
  assert.equal(report.pageIntegration.strictPacketGateComplete, true)
  assert.equal(report.pageIntegration.ownershipBackedBindings, 9)
  assert.equal(report.componentImplementation.status, 'implementation_mapped')
  assert.deepEqual(report.componentImplementation.components.map((item) => item.id), ['ChannelDock', 'RankedFeed'])
  assert.equal(report.componentImplementation.components[0].targetMetrics.width, 707)
  assert.equal(report.componentImplementation.components[1].targetMetrics.height, 717)
  assert.equal(report.componentImplementation.mappedSlots, 13)
  assert.equal(report.assetPermit.status, 'pass')
  assert.deepEqual(report.assetPermit.groups.map((group) => group.id), ['news_hero_and_ranked_feed', 'news_channel_dock'])
  assert.equal(report.currentRuntimeEvidence.status, 'runtime_reviewed_failed')
  assert.equal(report.currentRuntimeEvidence.runtimeScreenshot, true)
  assert.equal(report.currentRuntimeEvidence.strictGateEligible, false)
  assert.ok(report.currentRuntimeEvidence.total < 90)
  assert.equal(report.evidencePromotion.current, 'implementation_permit_suspended')
  assert.equal(report.evidencePromotion.next, 'fresh_permit_after_foundation_reset')
  assert.ok(report.evidencePromotion.requiredBeforePromotion.includes('complete all foundation reset gates'))
  assert.ok(report.evidencePromotion.forbiddenPromotionInputs.includes('this suspended permit as edit authorization'))
  assert.ok(report.evidencePromotion.forbiddenPromotionInputs.includes('browser-only screenshot'))
  assert.equal(report.nextGate.status, 'foundation_reset_required_before_news_source_integration')
  assert.deepEqual(report.failures, [])

  assert.equal(artifact.status, PASS37_NEWS_PERMIT_STATUS)
  assert.equal(artifact.scopedSourceEditsAllowed, false)
  assert.equal(artifact.unscopedPageWritesAllowed, false)
  assert.equal(artifact.suspension.status, 'foundation_reset_required')
  assert.equal(artifact.counts.allowedFiles, 4)
  assert.equal(artifact.counts.forbiddenFiles, 6)
  assert.equal(artifact.counts.targetComponents, 2)
  assert.equal(artifact.counts.routeSmokeItems, 4)
  assert.equal(artifact.counts.assetGroups, 2)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceImplementationPermit.status, PASS37_NEWS_PERMIT_STATUS)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceImplementationPermit.surfaceId, PASS37_NEWS_PERMIT_SURFACE_ID)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceImplementationPermit.scopedSourceEditsAllowed, false)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceImplementationPermit.unscopedPageWritesAllowed, false)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceImplementationPermit.suspensionStatus, 'foundation_reset_required')
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_news_surface_implementation_permit' &&
    item.status === 'implementation_permit_suspended' &&
    /news_home_and_feed/.test(item.evidence) &&
    /scopedSourceEditsAllowed=false/.test(item.evidence)
  )))
  assert.ok(readinessArtifact.nextStrictSteps.some((item) => /locked fresh news_home_and_feed permit/.test(item)))

  assert.match(markdown, /pass37 News Surface Implementation Permit/)
  assert.match(markdown, /Scoped source edits allowed: false/)
  assert.match(markdown, /Foundation Reset Lock/)
  assert.match(markdown, /Unscoped page writes allowed: false/)
  assert.match(markdown, /pages\/news\/news\.wxss/)
  assert.match(markdown, /browser-only screenshot/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 DevTools action ledger is present before runtime verification resumes', () => {
  const report = buildPass37DevToolsActionLedger({ repoRoot: process.cwd() })
  const markdown = renderPass37DevToolsActionLedgerMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-devtools-action-ledger.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-devtools-action-ledger.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_devtools_action_ledger')
  assert.equal(report.status, 'action_ledger_present')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.captureSafeRequiredForRuntime, true)
  assert.equal(report.noDevToolsActionThisRun, true)
  assert.deepEqual(PASS37_DEVTOOLS_LEDGER_FIELDS, PASS37_RESET_DEVTOOLS_LEDGER_REQUIREMENTS)
  assert.ok(PASS37_DEVTOOLS_DISTURBANCE_LEVELS.includes('login_affecting'))
  assert.ok(PASS37_DEVTOOLS_PROHIBITED_WITHOUT_APPROVAL.some((item) => /cache/i.test(item)))
  assert.equal(report.counts.entries, 0)
  assert.deepEqual(report.failures, [])

  assert.equal(artifact.status, 'action_ledger_present')
  assert.equal(artifact.devtoolsTouched, false)
  assert.equal(artifact.runtimeScreenshot, false)
  assert.equal(artifact.captureSafeRequiredForRuntime, true)
  assert.deepEqual(artifact.entryFields, PASS37_RESET_DEVTOOLS_LEDGER_REQUIREMENTS)

  assert.match(markdown, /pass37 DevTools Action Ledger/)
  assert.match(markdown, /No DevTools action this run: true/)
  assert.match(markdown, /runtime screenshot when captureSafe is false/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 foundation fixture matrix covers every foundation component state and viewport', () => {
  const report = buildPass37FoundationFixtureMatrix({ repoRoot: process.cwd() })
  const markdown = renderPass37FoundationFixtureMatrixMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-fixture-matrix.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-fixture-matrix.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_foundation_fixture_matrix')
  assert.equal(report.status, 'foundation_fixture_matrix_locked')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.counts.requiredComponents, 9)
  assert.equal(report.counts.requiredStates, 12)
  assert.equal(report.counts.viewportProfiles, 3)
  assert.equal(report.counts.expectedFixtures, 324)
  assert.equal(report.counts.fixtureCount, 324)
  assert.equal(report.counts.completeRows, 9)
  assert.deepEqual(report.failures, [])
  assert.ok(report.fixtures.some((fixture) => fixture.id === 'StatusBadge.blocked.compact' && fixture.assertions.some((item) => /glyph center/.test(item))))
  assert.ok(report.fixtures.some((fixture) => fixture.id === 'GameObjectIcon.missing_image.standard' && fixture.assertions.some((item) => /text fallback/.test(item))))

  assert.equal(artifact.status, 'foundation_fixture_matrix_locked')
  assert.equal(artifact.counts.fixtureCount, 324)
  assert.equal(artifact.devtoolsTouched, false)
  assert.equal(artifact.runtimeScreenshot, false)
  assert.equal(artifact.strictGateEligible, false)

  assert.match(markdown, /pass37 Foundation Fixture Matrix/)
  assert.match(markdown, /Fixture count: 324/)
  assert.match(markdown, /Runtime screenshot: false/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 measurement pipeline locks target current implementation evidence without runtime scoring', () => {
  const report = buildPass37MeasurementPipeline({ repoRoot: process.cwd() })
  const markdown = renderPass37MeasurementPipelineMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-measurement-pipeline.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-measurement-pipeline.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_measurement_pipeline')
  assert.equal(report.status, 'measurement_pipeline_complete')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.maxEvidenceLevel, 'component_precheck')
  assert.equal(report.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.scopedSourceEditsAllowed, false)
  assert.deepEqual(PASS37_MEASUREMENT_PIPELINE_ITEMS, PASS37_ARCH_RESET_MEASUREMENT_ITEMS)
  assert.equal(PASS37_MEASUREMENT_SURFACES.length, PASS37_ARCH_RESET_ROUTE_GATES.length)
  assert.equal(report.counts.requiredItems, 12)
  assert.equal(report.counts.surfaces, 5)
  assert.equal(report.counts.scriptsPresent, 4)
  assert.equal(report.counts.historicalArtifactsPresent, 3)
  assert.deepEqual(report.failures, [])
  assert.ok(report.requiredItems.some((row) => row.item === 'status center point' && row.owner === 'StatusBadge'))
  assert.ok(report.surfaces.some((surface) => surface.id === 'current_spec_workbench' && surface.criticalRects.includes('status badge')))
  assert.ok(report.blockedAssertions.some((item) => /no visual score/.test(item)))

  assert.equal(artifact.status, 'measurement_pipeline_complete')
  assert.equal(artifact.devtoolsTouched, false)
  assert.equal(artifact.runtimeScreenshot, false)
  assert.equal(artifact.runtimeVerified, false)
  assert.equal(artifact.strictGateEligible, false)
  assert.equal(artifact.finalScoreAllowedWithoutRuntime, false)
  assert.equal(artifact.counts.requiredItems, 12)
  assert.equal(artifact.counts.surfaces, 5)

  assert.match(markdown, /pass37 Measurement Pipeline/)
  assert.match(markdown, /Final score allowed without runtime: false/)
  assert.match(markdown, /Runtime screenshot: false/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 route smoke harness covers every planned route without runtime promotion', () => {
  const report = buildPass37RouteSmokeHarness({ repoRoot: process.cwd() })
  const markdown = renderPass37RouteSmokeHarnessMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-route-smoke-harness.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-route-smoke-harness.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_route_smoke_harness')
  assert.equal(report.status, 'route_smoke_harness_executable')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.runtimeExecuted, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.scopedSourceEditsAllowed, false)
  assert.deepEqual(report.requiredSurfaces, PASS37_ROUTE_SMOKE_SURFACES)
  assert.equal(Object.keys(PASS37_ROUTE_SMOKE_SCENARIOS).length, 29)
  assert.equal(report.counts.surfaces, 5)
  assert.equal(report.counts.routeSmokeItems, 29)
  assert.equal(report.counts.scenarios, 29)
  assert.equal(report.counts.executableScenarios, 29)
  assert.equal(report.counts.failedScenarios, 0)
  assert.equal(report.counts.missingRouteVariants, 0)
  assert.equal(report.counts.returnStateAssertions, 29)
  assert.equal(report.counts.failureStateAssertions, 29)
  assert.deepEqual(report.failures, [])
  assert.ok(report.surfaces.some((surface) => surface.surfaceId === 'current_spec_workbench' &&
    surface.scenarios.some((scenario) => scenario.smokeItem === 'ready SimC action')))
  assert.ok(report.surfaces.some((surface) => surface.surfaceId === 'simulator_and_captain' &&
    surface.scenarios.some((scenario) => scenario.smokeItem === 'long message scroll')))

  assert.equal(artifact.status, 'route_smoke_harness_executable')
  assert.equal(artifact.counts.routeSmokeItems, 29)
  assert.equal(artifact.counts.executableScenarios, 29)
  assert.equal(artifact.devtoolsTouched, false)
  assert.equal(artifact.runtimeScreenshot, false)
  assert.equal(artifact.runtimeExecuted, false)
  assert.equal(artifact.runtimeVerified, false)
  assert.equal(artifact.strictGateEligible, false)

  assert.match(markdown, /pass37 Route Smoke Harness/)
  assert.match(markdown, /Executable scenarios: 29\/29/)
  assert.match(markdown, /Runtime executed: false/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 cross-surface shell audit guards layout recurrence without runtime promotion', () => {
  const report = buildPass37CrossSurfaceShellAudit({ repoRoot: process.cwd() })
  const markdown = renderPass37CrossSurfaceShellAuditMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-cross-surface-shell-audit.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-cross-surface-shell-audit.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_cross_surface_shell_audit')
  assert.equal(report.status, 'cross_surface_shell_audit_source_ready')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.scopedSourceEditsAllowed, false)
  assert.equal(PASS37_CROSS_SURFACE_SHELL_RISKS.length, 6)
  assert.deepEqual(PASS37_CROSS_SURFACE_SHELL_RISKS.map((risk) => risk.id), [
    'duplicate_chrome',
    'edge_collision',
    'status_drift',
    'compressed_cta',
    'card_pileup',
    'evidence_overflow'
  ])
  assert.equal(report.counts.risks, 6)
  assert.equal(report.counts.guardedRisks, 6)
  assert.equal(report.counts.fakeChromeHits, 0)
  assert.equal(report.counts.artifactEvidenceReady, 4)
  assert.equal(report.counts.artifactEvidenceTotal, 4)
  assert.equal(report.fakeChromeScan.status, 'no_fake_chrome_tokens')
  assert.deepEqual(report.failures, [])
  assert.equal(report.artifacts.foundationFixtureMatrix.ready, true)
  assert.equal(report.artifacts.measurementPipeline.ready, true)
  assert.equal(report.artifacts.routeSmokeHarness.ready, true)
  assert.equal(report.artifacts.pageIntegrationMap.ready, true)
  assert.ok(report.shellRisks.every((risk) => risk.status === 'shell_recurrence_guarded'))

  assert.equal(artifact.status, 'cross_surface_shell_audit_source_ready')
  assert.equal(artifact.counts.guardedRisks, 6)
  assert.equal(artifact.counts.fakeChromeHits, 0)
  assert.equal(artifact.devtoolsTouched, false)
  assert.equal(artifact.runtimeScreenshot, false)
  assert.equal(artifact.runtimeVerified, false)
  assert.equal(artifact.strictGateEligible, false)

  assert.match(markdown, /pass37 Cross-Surface Shell Audit/)
  assert.match(markdown, /Fake chrome hits: 0/)
  assert.match(markdown, /duplicate_chrome/)
  assert.match(markdown, /evidence_overflow/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 news surface fresh implementation permit unlocks only scoped source integration', () => {
  const report = buildPass37NewsSurfaceFreshImplementationPermit({ repoRoot: process.cwd() })
  const markdown = renderPass37NewsSurfaceFreshImplementationPermitMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-news-surface-fresh-implementation-permit.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-news-surface-fresh-implementation-permit.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_news_surface_fresh_implementation_permit')
  assert.equal(report.status, PASS37_NEWS_FRESH_PERMIT_STATUS)
  assert.equal(report.surfaceId, PASS37_NEWS_PERMIT_SURFACE_ID)
  assert.equal(report.route, PASS37_NEWS_PERMIT_ROUTE)
  assert.equal(report.primaryOwner, PASS37_NEWS_PERMIT_PRIMARY_OWNER)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.scopedSourceEditsAllowed, true)
  assert.equal(report.unscopedPageWritesAllowed, false)
  assert.equal(report.supersedes.status, PASS37_NEWS_PERMIT_STATUS)
  assert.equal(report.supersedes.mayAuthorizeEdits, false)
  assert.equal(report.foundationResetPrerequisites.nonRepermitReady, true)
  assert.equal(report.foundationResetPrerequisites.decisionGateReady, true)
  assert.equal(report.foundationResetPrerequisites.crossSurfaceShellAuditStatus, 'cross_surface_shell_audit_source_ready')
  assert.deepEqual(
    report.allowedProductionFiles.map((entry) => entry.file),
    PASS37_NEWS_FRESH_PERMIT_ALLOWED_FILES.map((entry) => entry.file)
  )
  assert.deepEqual(
    report.forbiddenProductionFiles.map((entry) => entry.file),
    PASS37_NEWS_FRESH_PERMIT_FORBIDDEN_FILES.map((entry) => entry.file)
  )
  assert.equal(report.allowedProductionFiles.length, 7)
  assert.equal(report.forbiddenProductionFiles.length, 7)
  assert.ok(report.allowedProductionFiles.some((entry) => entry.file === 'components/channel-dock/channel-dock.wxml'))
  assert.ok(report.allowedProductionFiles.some((entry) => entry.file === 'components/ranked-feed/ranked-feed.wxss'))
  assert.ok(report.forbiddenProductionFiles.some((entry) => entry.file === 'pages/news/news.js'))
  assert.ok(report.forbiddenProductionFiles.some((entry) => entry.file === 'server/news_backend.py'))
  assert.equal(report.pageIntegration.status, 'page_integration_mapped')
  assert.equal(report.componentImplementation.status, 'implementation_mapped')
  assert.deepEqual(report.componentImplementation.components.map((item) => item.id), ['ChannelDock', 'RankedFeed'])
  assert.equal(report.assetPermit.status, 'pass')
  assert.equal(report.currentRuntimeEvidence.status, 'runtime_reviewed_failed')
  assert.equal(report.currentRuntimeEvidence.runtimeScreenshot, true)
  assert.equal(report.currentRuntimeEvidence.strictGateEligible, false)
  assert.ok(report.currentRuntimeEvidence.total < 90)
  assert.equal(report.routeSmokePlan.length, 4)
  assert.equal(report.nextGate.status, 'source_integration_allowed_for_news_home_and_feed')
  assert.deepEqual(report.failures, [])

  assert.equal(artifact.status, PASS37_NEWS_FRESH_PERMIT_STATUS)
  assert.equal(artifact.scopedSourceEditsAllowed, true)
  assert.equal(artifact.unscopedPageWritesAllowed, false)
  assert.equal(artifact.counts.allowedFiles, 7)
  assert.equal(artifact.counts.forbiddenFiles, 7)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceFreshImplementationPermit.status, PASS37_NEWS_FRESH_PERMIT_STATUS)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceFreshImplementationPermit.scopedSourceEditsAllowed, true)
  assert.equal(readinessArtifact.latestPass37NewsSurfaceFreshImplementationPermit.unscopedPageWritesAllowed, false)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_news_surface_fresh_implementation_permit' &&
    item.status === PASS37_NEWS_FRESH_PERMIT_STATUS &&
    /allowedFiles=7/.test(item.evidence) &&
    /scopedSourceEditsAllowed=true/.test(item.evidence)
  )))

  assert.match(markdown, /pass37 News Surface Fresh Implementation Permit/)
  assert.match(markdown, /Scoped source edits allowed: true/)
  assert.match(markdown, /Unscoped page writes allowed: false/)
  assert.match(markdown, /source_integration_allowed_for_news_home_and_feed/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 repermit decision record closes the foundation re-permit gate', () => {
  const report = buildPass37RepermitDecisionRecord({ repoRoot: process.cwd() })
  const markdown = renderPass37RepermitDecisionRecordMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-repermit-decision-record.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-repermit-decision-record.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_repermit_decision_record')
  assert.equal(report.status, PASS37_REPERMIT_DECISION_STATUS)
  assert.equal(report.surfaceId, PASS37_NEWS_PERMIT_SURFACE_ID)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.foundationReset.readyNonRepermitGates, 7)
  assert.equal(report.foundationReset.nonRepermitGates, 7)
  assert.deepEqual(report.foundationReset.partialGateIds, [])
  assert.equal(report.foundationReset.readyForDecision, true)
  assert.equal(
    report.foundationReset.decisionGatePendingOnly || report.foundationReset.decisionGateSatisfied,
    true
  )
  assert.equal(report.suspendedPermit.status, PASS37_NEWS_PERMIT_STATUS)
  assert.equal(report.suspendedPermit.mayAuthorizeEdits, false)
  assert.equal(report.freshPermit.status, PASS37_NEWS_FRESH_PERMIT_STATUS)
  assert.equal(report.freshPermit.scopedSourceEditsAllowed, true)
  assert.equal(report.freshPermit.unscopedPageWritesAllowed, false)
  assert.equal(report.decision.scopedImplementationMayStart, true)
  assert.equal(report.decision.unscopedPageWritesAllowed, false)
  assert.equal(report.decision.oldPermitReuseAllowed, false)
  assert.deepEqual(report.failures, [])

  assert.equal(artifact.status, PASS37_REPERMIT_DECISION_STATUS)
  assert.equal(artifact.decision.scopedImplementationMayStart, true)
  assert.equal(artifact.decision.unscopedPageWritesAllowed, false)
  assert.equal(readinessArtifact.latestPass37RepermitDecisionRecord.status, PASS37_REPERMIT_DECISION_STATUS)
  assert.equal(readinessArtifact.latestPass37RepermitDecisionRecord.scopedImplementationMayStart, true)
  assert.equal(readinessArtifact.latestPass37RepermitDecisionRecord.oldPermitReuseAllowed, false)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_repermit_decision_record' &&
    item.status === PASS37_REPERMIT_DECISION_STATUS &&
    /7\/7 non-repermit foundation gates/.test(item.evidence) &&
    /oldPermitReuseAllowed=false/.test(item.evidence)
  )))

  assert.match(markdown, /pass37 Repermit Decision Record/)
  assert.match(markdown, /Scoped implementation may start: true/)
  assert.match(markdown, /Old permit reuse allowed: false/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 foundation reset package records fresh permit readiness after re-permit decision', () => {
  const report = buildPass37FoundationResetPackage({ repoRoot: process.cwd() })
  const markdown = renderPass37FoundationResetMarkdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-foundation-reset-package.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-foundation-reset-package.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_foundation_reset_package')
  assert.equal(report.status, 'foundation_reset_ready_for_fresh_permit')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.scopedSourceEditsAllowed, false)
  assert.equal(report.goalDocumentHasFoundationResetLock, true)
  assert.equal(report.strictSystem.status, 'strict_system_contract_locked')
  assert.equal(report.strictSystem.foundationResetStatus, 'foundation_reset_locked')
  assert.equal(report.newsPermitStatus, PASS37_NEWS_PERMIT_STATUS)
  assert.equal(report.counts.foundationResetGates, PASS37_STRICT_FOUNDATION_RESET_GATES.length)
  assert.equal(report.foundationResetGates.length, 8)
  assert.equal(report.counts.blockedGates, 0)
  assert.equal(report.counts.partialGates, 0)
  assert.equal(report.counts.requiredFoundationComponents, 9)
  assert.deepEqual(PASS37_RESET_FOUNDATION_COMPONENTS, [
    'AppNav',
    'PageFrame',
    'WowPanel',
    'MaterialImage',
    'GameObjectIcon',
    'StatusBadge',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger'
  ])
  assert.equal(PASS37_RESET_FIXTURE_STATES.length, 12)
  assert.deepEqual(PASS37_RESET_VIEWPORT_PROFILES, ['compact', 'standard', 'large'])
  assert.equal(PASS37_RESET_SOURCE_COMPONENT_MAP.length, 9)
  assert.ok(PASS37_RESET_DEVTOOLS_LEDGER_REQUIREMENTS.includes('login/cache/project/appid risk'))
  assert.equal(report.counts.expectedFixtures, 324)
  assert.equal(report.counts.missingFixtureCount, 0)
  assert.equal(report.counts.componentSourceGaps, 0)
  assert.equal(report.counts.routeSmokeItems, 29)
  assert.equal(report.assetManifestGap.status, 'asset_manifest_ready_for_reset')
  assert.equal(report.devtoolsActionLedger.status, 'action_ledger_present')
  assert.equal(report.routeSmokeHarness.status, 'route_smoke_harness_executable')
  assert.equal(report.routeSmokeHarness.executableScenarios, 29)
  assert.equal(report.routeSmokeHarness.runtimeExecuted, false)
  assert.equal(report.routeSmokeHarness.runtimeVerified, false)
  assert.equal(report.routeSmokeHarness.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.measurementPipeline.status, 'measurement_pipeline_complete')
  assert.equal(report.measurementPipeline.maxEvidenceLevel, 'component_precheck')
  assert.equal(report.measurementPipeline.runtimeVerified, false)
  assert.equal(report.measurementPipeline.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.crossSurfaceShellAudit.status, 'cross_surface_shell_audit_source_ready')
  assert.equal(report.crossSurfaceShellAudit.runtimeVerified, false)
  assert.equal(report.crossSurfaceShellAudit.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.crossSurfaceShellAudit.fakeChromeScan.status, 'no_fake_chrome_tokens')
  assert.equal(report.rePermitDecision.status, PASS37_REPERMIT_DECISION_STATUS)
  assert.equal(report.rePermitDecision.freshPermitStatus, PASS37_NEWS_FRESH_PERMIT_STATUS)
  assert.equal(report.rePermitDecision.scopedImplementationMayStart, true)
  assert.equal(report.rePermitDecision.scopedSourceEditsAllowedByPermit, true)
  assert.equal(report.rePermitDecision.unscopedPageWritesAllowed, false)
  assert.deepEqual(report.failures, [])

  const gateStatuses = Object.fromEntries(report.foundationResetGates.map((gate) => [gate.id, gate.status]))
  assert.equal(gateStatuses.component_source_contract, 'source_contract_present')
  assert.equal(gateStatuses.asset_slice_manifest, 'source_contract_present')
  assert.equal(gateStatuses.component_fixture_matrix, 'component_precheck')
  assert.equal(gateStatuses.measurement_pipeline, 'component_precheck')
  assert.equal(gateStatuses.route_smoke_harness, 'component_precheck')
  assert.equal(gateStatuses.devtools_action_ledger, 'source_contract_present')
  assert.equal(gateStatuses.cross_surface_shell_audit, 'source_contract_present')
  assert.equal(gateStatuses.repermit_decision_record, 'source_contract_present')
  const pageFrame = report.sourceComponents.find((component) => component.id === 'PageFrame')
  const wowPanel = report.sourceComponents.find((component) => component.id === 'WowPanel')
  const gameObjectIcon = report.sourceComponents.find((component) => component.id === 'GameObjectIcon')
  const actionButton = report.sourceComponents.find((component) => component.id === 'ActionButton')
  const moduleCard = report.sourceComponents.find((component) => component.id === 'ModuleCard')
  const evidenceLedger = report.sourceComponents.find((component) => component.id === 'EvidenceLedger')
  assert.equal(pageFrame.sourceStatus, 'source_component_present')
  assert.equal(wowPanel.sourceStatus, 'source_component_present')
  assert.equal(gameObjectIcon.sourceStatus, 'source_component_present')
  assert.equal(actionButton.sourceStatus, 'source_component_present')
  assert.equal(moduleCard.sourceStatus, 'source_component_present')
  assert.equal(evidenceLedger.sourceStatus, 'source_component_present')
  assert.equal(pageFrame.blocker, false)
  assert.equal(wowPanel.blocker, false)
  assert.equal(gameObjectIcon.blocker, false)
  assert.equal(actionButton.blocker, false)
  assert.equal(moduleCard.blocker, false)
  assert.equal(evidenceLedger.blocker, false)

  assert.equal(artifact.status, 'foundation_reset_ready_for_fresh_permit')
  assert.equal(artifact.counts.blockedGates, 0)
  assert.equal(artifact.counts.partialGates, 0)
  assert.equal(artifact.counts.missingFixtureCount, 0)
  assert.equal(artifact.pageWritesAllowed, false)
  assert.equal(artifact.scopedSourceEditsAllowed, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.status, 'foundation_reset_ready_for_fresh_permit')
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.blockedGates, 0)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.partialGates, 0)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.componentSourceGaps, 0)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.missingFixtureCount, 0)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.measurementPipelineStatus, 'measurement_pipeline_complete')
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.measurementMaxEvidenceLevel, 'component_precheck')
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.measurementRuntimeVerified, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.measurementFinalScoreAllowedWithoutRuntime, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.routeSmokeHarnessStatus, 'route_smoke_harness_executable')
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.routeSmokeExecutableScenarios, 29)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.routeSmokeRuntimeExecuted, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.routeSmokeRuntimeVerified, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.crossSurfaceShellAuditStatus, 'cross_surface_shell_audit_source_ready')
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.crossSurfaceRuntimeVerified, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.crossSurfaceFinalScoreAllowedWithoutRuntime, false)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.crossSurfaceFakeChromeStatus, 'no_fake_chrome_tokens')
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.rePermitDecisionStatus, PASS37_REPERMIT_DECISION_STATUS)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.rePermitFreshPermitStatus, PASS37_NEWS_FRESH_PERMIT_STATUS)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.rePermitScopedImplementationMayStart, true)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.rePermitScopedSourceEditsAllowedByPermit, true)
  assert.equal(readinessArtifact.latestPass37FoundationResetPackage.rePermitUnscopedPageWritesAllowed, false)
  assert.deepEqual(readinessArtifact.latestPass37FoundationResetPackage.blockedGateIds, [])
  assert.deepEqual(readinessArtifact.latestPass37FoundationResetPackage.partialGateIds, [])
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_foundation_reset_package' &&
    item.status === 'foundation_reset_ready_for_fresh_permit' &&
    /0 blocked gates, 0 partial gates/.test(item.evidence) &&
    /rePermitDecision=repermit_decision_record_locked/.test(item.evidence) &&
    /scopedSourceEditsAllowed=false/.test(item.evidence)
  )))
  assert.ok(readinessArtifact.nextStrictSteps.some((item) => /Foundation reset is ready for the fresh permit/.test(item)))

  assert.match(markdown, /pass37 Foundation Reset Package/)
  assert.match(markdown, /Foundation Reset Gates/)
  assert.match(markdown, /EvidenceLedger/)
  assert.match(markdown, /DevTools Action Ledger/)
  assert.match(markdown, /repermit_decision_record_locked/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('pass37 architecture reset gate v2 locks systemic workflow before fresh permits', () => {
  const report = buildPass37ArchitectureResetGateV2({ repoRoot: process.cwd() })
  const markdown = renderPass37ArchitectureResetGateV2Markdown(report)
  const artifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass37-architecture-reset-gate-v2.json'
  )
  const readinessArtifact = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/pass36-final-readiness-report.json'
  )
  const source = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass37-architecture-reset-gate-v2.js',
    'utf8'
  )

  assert.equal(report.pass, 'pass37_architecture_reset_gate_v2')
  assert.equal(report.status, 'architecture_reset_gate_v2_locked')
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.pageWritesAllowed, false)
  assert.equal(report.scopedSourceEditsAllowed, false)
  assert.equal(report.freshPermitAllowed, true)
  assert.equal(report.strictSystem.status, 'strict_system_contract_locked')
  assert.equal(report.foundationReset.status, 'foundation_reset_ready_for_fresh_permit')
  assert.equal(report.foundationReset.blockedGates, 0)
  assert.equal(report.foundationReset.partialGates, 0)
  assert.equal(report.rootCauseOverride.localCssExplanationAllowed, false)
  assert.equal(report.realComponentGate.classOnlyOwnerCountsAsBlocker, true)
  assert.equal(report.realComponentGate.helperOnlyOwnerCountsAsBlocker, true)
  assert.equal(report.stateVisualContract.pageSplitBaseAndGlyphAllowed, false)
  assert.equal(report.stateVisualContract.bakedBusinessConclusionAllowed, false)
  assert.equal(report.designCandidateGate.minimumCandidates, 2)
  assert.equal(report.designCandidateGate.preferredCandidates, 3)
  assert.equal(report.assetSlicingGate.productionRequiresManifest, true)
  assert.equal(report.assetSlicingGate.wholeScreenReferenceOnly, true)
  assert.equal(report.assetSlicingGate.imagegenMayFakeWowFacts, false)
  assert.equal(report.measurementGate.finalScoreAllowedWithoutRuntime, false)
  assert.equal(report.measurementGate.browserHarnessMaxStatus, 'component_precheck')
  assert.equal(report.routeCoverageGate.routeMapRequiredBeforeImplementation, true)
  assert.equal(report.devtoolsPreservation.loginStateIsUserAsset, true)
  assert.equal(report.devtoolsPreservation.captureSafeRequiredForRuntime, true)
  assert.equal(report.restartCondition.pageCssPatchAfterTriggerAllowed, false)
  assert.deepEqual(report.failures, [])

  assert.equal(PASS37_ARCH_RESET_ROOT_CAUSES.length, 7)
  assert.deepEqual(PASS37_ARCH_RESET_REAL_COMPONENT_OWNERS, [
    'PageFrame',
    'WowPanel',
    'GameObjectIcon',
    'StatusBadge',
    'ActionButton',
    'ModuleCard',
    'EvidenceLedger'
  ])
  assert.deepEqual(PASS37_ARCH_RESET_STATE_VISUAL_MODES.map((mode) => mode.id), ['layered', 'atomic'])
  assert.ok(PASS37_ARCH_RESET_ASSET_CLASSES.includes('state-atomic'))
  assert.ok(PASS37_ARCH_RESET_ASSET_CLASSES.includes('reference-only'))
  assert.ok(PASS37_ARCH_RESET_MEASUREMENT_ITEMS.includes('route smoke result'))
  assert.equal(PASS37_ARCH_RESET_ROUTE_GATES.length, 5)
  assert.ok(PASS37_ARCH_RESET_ROUTE_GATES.some((gate) => gate.id === 'current_spec_workbench' && gate.required.includes('SimC jump and return')))
  assert.equal(PASS37_ARCH_RESET_RESTART_CONDITIONS.length, 5)

  assert.equal(artifact.status, 'architecture_reset_gate_v2_locked')
  assert.equal(artifact.counts.rootCauseOverrides, 7)
  assert.equal(artifact.counts.realComponentOwners, 7)
  assert.equal(artifact.counts.stateVisualModes, 2)
  assert.equal(artifact.counts.assetClasses, 8)
  assert.equal(artifact.counts.measurementRequiredItems, 12)
  assert.equal(artifact.counts.routeSurfaceGates, 5)
  assert.equal(artifact.freshPermitAllowed, true)
  assert.equal(artifact.pageWritesAllowed, false)
  assert.equal(artifact.scopedSourceEditsAllowed, false)
  assert.equal(readinessArtifact.latestPass37ArchitectureResetGateV2.status, 'architecture_reset_gate_v2_locked')
  assert.equal(readinessArtifact.latestPass37ArchitectureResetGateV2.freshPermitAllowed, true)
  assert.equal(readinessArtifact.latestPass37ArchitectureResetGateV2.stateVisualAllowsAtomic, true)
  assert.equal(readinessArtifact.latestPass37ArchitectureResetGateV2.stateVisualAllowsLayered, true)
  assert.ok(readinessArtifact.objectiveRequirements.some((item) => (
    item.id === 'pass37_architecture_reset_gate_v2' &&
    item.status === 'architecture_reset_gate_v2_locked' &&
    /atomic=true/.test(item.evidence) &&
    /freshPermitAllowed=true/.test(item.evidence)
  )))
  assert.ok(readinessArtifact.nextStrictSteps.some((item) => /Keep architecture-reset-gate-v2 active/.test(item)))

  assert.match(markdown, /pass37 Architecture Reset Gate v2/)
  assert.match(markdown, /State Visual Contract v2/)
  assert.match(markdown, /atomic/)
  assert.match(markdown, /layered/)
  assert.match(markdown, /Fresh permit allowed: true/)
  assert.match(markdown, /DevTools Preservation Gate v2/)
  assert.doesNotMatch(markdown, /[—–]/)
  assert.doesNotMatch(source, /connectMiniProgram|WECHAT_AUTOMATOR_PORT|WECHAT_DEVTOOLS_CLI_PORT/)
  assert.doesNotMatch(source, /child_process|execFile|spawn|osascript/)
})

test('ui v2.1 scoped source stays covered by target selectors and asset contract', () => {
  const audit = auditStaticScope()

  assert.equal(audit.sourceAuditStatus, 'pass')
  assert.equal(audit.strictGateEligible, false)
  assert.equal(audit.runtimeScreenshot, false)
  assert.equal(audit.devtoolsTouched, false)
  assert.deepEqual(audit.sourceFailures, [])
  assert.deepEqual(audit.assetContract.uncoveredAssets, [])
  assert.deepEqual(audit.assetContract.referenceOnlyUsed, [])
  assert.deepEqual(audit.assetContract.missingAssetFiles, [])
  assert.deepEqual(audit.bannedClaims, [])
  assert.ok(audit.layoutMaterialAudit, 'static scope audit should include layout/material guard evidence')
  assert.deepEqual(audit.layoutMaterialAudit.forbiddenSourceFindings, [])
  assert.deepEqual(
    audit.layoutMaterialAudit.materialLayers.map((item) => [item.file, item.count, item.max, item.status]),
    [
      ['pages/news/news.wxml', 5, 5, 'pass'],
      ['components/channel-dock/channel-dock.wxml', 3, 3, 'pass'],
      ['components/ranked-feed/ranked-feed.wxml', 3, 3, 'pass'],
      ['pages/builds/builds.wxml', 8, 8, 'pass'],
      ['pages/builds/workbench.wxml', 4, 6, 'pass']
    ]
  )
  assert.ok(
    audit.layoutMaterialAudit.cssContracts.every((item) => item.status === 'pass'),
    'every source-level layout contract should pass before runtime capture'
  )
  assert.ok(
    audit.layoutMaterialAudit.componentFidelityContracts.every((item) => item.status === 'pass'),
    'component-level fidelity contracts should pass before runtime capture'
  )
  assert.equal(audit.layoutMaterialAudit.mockChromeBoundary.status, 'pass')
  assert.deepEqual(audit.layoutMaterialAudit.mockChromeBoundary.sourceFindings, [])
  const contractIds = new Set(audit.layoutMaterialAudit.cssContracts.map((item) => item.id))
  ;[
    'news_ranked_feed_grid',
    'news_channel_dock_six_tabs',
    'builds_status_rows_grid',
    'builds_workflow_rows_grid',
    'workbench_control_strip_safe_flow',
    'workbench_module_cards_css_material',
    'workbench_evidence_rows_grid'
  ].forEach((id) => assert.ok(contractIds.has(id), `${id} should be audited`))
  const fidelityContractIds = new Set(audit.layoutMaterialAudit.componentFidelityContracts.map((item) => item.id))
  ;[
    'news_channel_dock_component_fidelity',
    'news_ranked_focus_list_component_fidelity',
    'mock_system_chrome_component_boundary'
  ].forEach((id) => assert.ok(fidelityContractIds.has(id), `${id} should be audited`))
  const focusContract = audit.layoutMaterialAudit.componentFidelityContracts.find((item) => item.id === 'news_ranked_focus_list_component_fidelity')
  assert.ok(focusContract.checks.some((check) => check.label === 'real article visual wins before fallback'))
  assert.ok(focusContract.checks.some((check) => check.label === 'rank/thumb/content/save proportions fixed'))
  const dockContract = audit.layoutMaterialAudit.componentFidelityContracts.find((item) => item.id === 'news_channel_dock_component_fidelity')
  assert.ok(dockContract.checks.some((check) => check.label === 'six equal columns'))
  assert.ok(dockContract.checks.some((check) => check.label === 'labels cannot wrap or overflow'))

  for (const screen of ['news', 'builds', 'workbench']) {
    assert.ok(audit.regionAudit[screen], `${screen} should be audited`)
    audit.regionAudit[screen].regions.forEach((region) => {
      assert.equal(region.status, 'covered', `${screen}/${region.id} should be covered`)
    })
  }

  const classes = new Set(audit.assetContract.classifiedAssets.map((item) => item.class))
  assert.ok(classes.has('low_semantic_material'))
  assert.ok(classes.has('product_ia_channel_marker'))
  assert.ok(classes.has('generated_category_thumbnail_fallback'))
})

test('ui v2.1 pass36 runtime capture uses a nonblocking capture gate and full evidence', () => {
  const contract = buildRuntimeCaptureContract()
  const template = readJson('artifacts/ui-v2-1-strict-restoration/visual-gate-template.json')
  const captureScript = fs.readFileSync(
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js',
    'utf8'
  )
  const expectedScreenshotCount = template.requiredScreens.length * template.requiredViewports.length

  assert.equal(contract.pass, 'pass36l_runtime_capture_contract')
  assert.equal(contract.devtoolsTouched, false)
  assert.equal(contract.strictGateEligible, false)
  assert.equal(contract.sourcePrerequisite.staticAuditReady, true)
  assert.equal(contract.authorization.requiredBeforeAnyDevToolsMutation, true)
  assert.equal(contract.authorization.requiredEnv, 'WOW_PASS36_CAPTURE_AUTHORIZED')
  assert.equal(contract.authorization.perTurnChatAuthorizationRequired, false)
  assert.equal(contract.authorization.codexMaySetCaptureGateWhenRuntimeHealthy, true)
  assert.equal(contract.authorization.hotSyncEnv, 'WOW_ALLOW_DEVTOOLS_HOT_SYNC')
  assert.equal(contract.authorization.cliOpenEnv, 'WOW_ALLOW_DEVTOOLS_CLI_OPEN')
  assert.equal(contract.authorization.requireCleanShadowEnv, 'WOW_REQUIRE_DEVTOOLS_SHADOW')
  assert.equal(contract.authorization.sourceWritePolicy.codexManagedWritesAllowed, true)
  assert.equal(contract.authorization.sourceWritePolicy.perTurnWriteAuthorizationRequired, false)
  assert.equal(contract.authorization.sourceWritePolicy.watchedSourceProjectForbiddenDuringImplementation, true)
  assert.equal(contract.authorization.sourceWritePolicy.watchedRuntimeProjectMutationForbiddenDuringImplementation, true)
  assert.match(contract.authorization.sourceWritePolicy.rule, /must not mutate the project directory currently watched/)
  assert.equal(contract.authorization.designGenerationPolicy.stagingRequiredByDefault, true)
  assert.equal(contract.authorization.designGenerationPolicy.targetAssetOutputEnv, 'WOW_UI_TARGET_OUTPUT_MODE=staging')
  assert.equal(contract.authorization.designGenerationPolicy.sourcePreviewOutputEnv, 'WOW_PASS36_SOURCE_PREVIEW_OUTPUT_MODE=staging')
  assert.equal(contract.authorization.designGenerationPolicy.repoWriteOverrideEnv, 'WOW_ALLOW_WATCHED_PROJECT_GENERATION=1')
  assert.match(contract.authorization.designGenerationPolicy.rule, /outside the watched mini-program project by default/)
  assert.equal(contract.requiredArtifacts.screenshots.length, expectedScreenshotCount)

  const shotsByScreen = new Map()
  for (const shot of contract.requiredArtifacts.screenshots) {
    if (!shotsByScreen.has(shot.id)) shotsByScreen.set(shot.id, new Set())
    shotsByScreen.get(shot.id).add(shot.viewportId)
    assert.ok(shot.route, `${shot.id} should declare a capture route`)
    assert.ok(shot.interaction, `${shot.id} should declare an interaction`)
  }

  for (const screen of template.requiredScreens) {
    assert.deepEqual(
      Array.from(shotsByScreen.get(screen) || []).sort(),
      template.requiredViewports.map((viewport) => viewport.id).sort(),
      `${screen} should require every viewport`
    )
  }

  const prohibited = contract.authorization.prohibitedActions.join('\n')
  assert.match(prohibited, /Do not run DevTools CLI login or islogin probes/)
  assert.match(prohibited, /Do not open, close, restart, or kill WeChat DevTools unless a separate CLI-control env/)
  assert.match(prohibited, /Do not run shadow hot sync/)
  assert.match(prohibited, /project directory currently watched by the active DevTools runtime/)
  assert.match(prohibited, /Do not run design asset generation in repo output mode/)

  const requiredArtifacts = JSON.stringify(contract.requiredArtifacts)
  assert.match(requiredArtifacts, /visual-scorecard-pass36l\.json/)
  assert.match(requiredArtifacts, /strict-visual-gate-pass36l\.json/)
  assert.match(requiredArtifacts, /comparison-news-tab-dock/)
  assert.match(requiredArtifacts, /comparison-news-focus-list/)

  assert.ok(contract.nextCommandsAfterRuntimeHealth.some((command) => /WOW_PASS36_CAPTURE_AUTHORIZED=1/.test(command)))
  assert.ok(contract.nextCommandsAfterRuntimeHealth.some((command) => /WOW_ALLOW_DEVTOOLS_HOT_SYNC=1/.test(command)))
  assert.ok(contract.nextCommandsAfterRuntimeHealth.some((command) => /WOW_REQUIRE_DEVTOOLS_SHADOW=1/.test(command)))
  assert.ok(contract.boundary.some((line) => /not a runtime capture/.test(line)))
  assert.match(captureScript, /WOW_CAPTURE_HARD_TIMEOUT_MS/)
  assert.match(captureScript, /updateManifestStage\(manifest,\s*'capturing_scene'/)
  assert.match(captureScript, /data\.deferredVisualsReady === true[\s\S]*pages\/builds\/builds/)
  assert.match(captureScript, /Array\.isArray\(data\.rankedHighlights\) && data\.rankedHighlights\.length > 0/)
  assert.match(captureScript, /setCurrentPageData\(miniProgram,\s*\{\s*deferredVisualsReady:\s*true\s*\}/)
  assert.match(captureScript, /async function scrollSelectorIntoView\(miniProgram, selector, targetTop = 142\)/)
  assert.match(captureScript, /scrollSelectorIntoView\(miniProgram,\s*'\.news-feed-section'/)
  assert.match(captureScript, /readySelector:\s*'\.focus-row\.is-final-focus-row'/)
  assert.match(captureScript, /009_news_long_missing_image[\s\S]*readySelector:\s*'\.news-feed-section'/)
  assert.match(captureScript, /page\.selectComponent && page\.selectComponent\('#rankedFeed'\)/)
  assert.match(captureScript, /NEWS_STRESS_FALLBACK_THUMBS/)
  assert.match(captureScript, /normalizeStressRow/)
  assert.match(captureScript, /news_thumb_fallback_source_reference_pass36ae\.png/)
  assert.match(captureScript, /thumbState:\s*item\.visualUrl \? 'article_image' : 'fallback_thumb'/)
  assert.doesNotMatch(captureScript, /002_news_home_scrolled[\s\S]{0,220}scrollBoundPage\(app,\s*720\)/)
})

test('ui v2.1 pass36m source preview is explicit non-runtime evidence', () => {
  const manifest = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/comparisons-pass36m-source-preview/manifest-pass36m-source-preview.json'
  )
  const scorecard = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/visual-scorecard-pass36m-source-preview.json'
  )
  const sourcePreviewScript = fs.readFileSync(
    'artifacts/ui-v2-1-strict-restoration/create-pass36m-source-preview.py',
    'utf8'
  )

  assert.equal(manifest.pass, 'pass36m_source_preview')
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.runtimeScreenshot, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.match(manifest.board, /comparison-news-components-target-pass36i-pass36m-source-preview\.png/)
  assert.equal(manifest.sourceSketch.enabled, true)
  assert.match(manifest.sourceSketch.basis, /Current WXSS dimensions/)
  assert.match(manifest.sourceSketch.basis, /Not runtime rendering/)
  assert.equal(manifest.cssValues['.news-tab-rail'].left, '7rpx')
  assert.equal(manifest.cssValues['.news-tab-rail']['border-radius'], '7rpx')
  assert.equal(manifest.cssValues['.news-tab-item::after']['border-radius'], '44rpx 44rpx 5rpx 5rpx')
  assert.equal(manifest.cssValues['.focus-row']['grid-template-columns'], '52rpx 116rpx minmax(0, 1fr) 32rpx')
  assert.equal(manifest.cssValues['.focus-row'].height, '116rpx')
  assert.equal(manifest.cssValues['.focus-thumb'].width, '116rpx')
  assert.equal(manifest.cssValues['.focus-thumb'].height, '96rpx')
  assert.equal(manifest.cssValues['.focus-save-mark'].height, '27rpx')
  assert.match(manifest.blockingFailures.join('\n'), /Need authorized pass36l runtime capture/)
  assert.doesNotMatch(sourcePreviewScript, /万阅读|阅读量/)

  assert.equal(scorecard.pass, 'pass36m_source_preview')
  assert.equal(scorecard.strictGateEligible, false)
  assert.equal(scorecard.total, null)
  assert.match(scorecard.reason, /Source-only preview/)
})

test('ui v2.1 pass36n three-screen preview stays source-only', () => {
  const manifest = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/comparisons-pass36n-source-preview/manifest-pass36n-source-preview.json'
  )
  const scorecard = readJson(
    'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36/visual-scorecard-pass36n-source-preview.json'
  )

  assert.equal(manifest.pass, 'pass36n_source_preview')
  assert.equal(manifest.devtoolsTouched, false)
  assert.equal(manifest.runtimeScreenshot, false)
  assert.equal(manifest.strictGateEligible, false)
  assert.match(manifest.board, /comparison-three-screens-target-source-pass36n\.png/)
  assert.ok(manifest.targetCrops.news.channel_dock.endsWith('news-target-channel_dock.png'))
  assert.ok(manifest.targetCrops.builds.workbench_panel.endsWith('builds-target-workbench_panel.png'))
  assert.ok(manifest.targetCrops.workbench.evidence_ledger.endsWith('workbench-target-evidence_ledger.png'))

  assert.equal(manifest.cssValues.news['.news-tab-rail'].left, '7rpx')
  assert.equal(manifest.cssValues.news['.news-tab-rail']['border-radius'], '7rpx')
  assert.equal(manifest.cssValues.news['.news-tab-orb'].width, '76rpx')
  assert.equal(manifest.cssValues.news['.focus-row']['grid-template-columns'], '52rpx 116rpx minmax(0, 1fr) 32rpx')
  assert.equal(manifest.cssValues.news['.focus-row'].height, '116rpx')
  assert.equal(manifest.cssValues.builds['.workbench-module-row']['grid-template-columns'], '66rpx minmax(0, 1fr) 150rpx')
  assert.equal(manifest.cssValues.builds['.query-card']['grid-template-columns'], '78rpx minmax(0, 1fr) 146rpx')
  assert.equal(manifest.cssValues.builds['.query-icon-socket'].width, '58rpx')
  assert.equal(manifest.cssValues.workbench['.workbench-cockpit']['min-height'], '246rpx')
  assert.equal(manifest.cssValues.workbench['.verdict-slab']['min-height'], '430rpx')
  assert.equal(manifest.cssValues.workbench['.module-band']['min-height'], '314rpx')
  assert.equal(manifest.cssValues.workbench['.game-icon-frame'].width, '66rpx')
  assert.equal(manifest.cssValues.workbench['.verdict-status-badge'].width, '236rpx')
  assert.equal(manifest.cssValues.workbench['.verdict-status-badge'].height, '290rpx')
  assert.equal(manifest.cssValues.workbench['.module-card']['min-height'], '178rpx')
  assert.equal(manifest.cssValues.workbench['.module-status']['max-width'], '58rpx')
  assert.equal(manifest.cssValues.workbench['.module-desc']['font-size'], '18rpx')
  assert.equal(manifest.cssValues.workbench['.evidence-section']['min-height'], '640rpx')
  assert.match(manifest.blockingFailures.join('\n'), /Need authorized pass36l runtime capture/)

  assert.equal(scorecard.pass, 'pass36n_source_preview')
  assert.equal(scorecard.strictGateEligible, false)
  assert.equal(scorecard.total, null)
  assert.match(scorecard.reason, /Source-only three-screen preview/)
})

test('ui v2.1 pass36 final validator rejects current runtime evidence below the visual gate', () => {
  const report = validatePass36FinalAcceptance({
    repoRoot: process.cwd(),
    artifactDir: 'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36',
    passName: 'pass36l'
  })

  assert.equal(report.status, 'fail')
  assert.equal(report.strictGateEligible, false)
  assert.equal(report.counts.requiredScreenshots, 27)
  assert.equal(report.counts.matchedScreenshots, 27)
  assert.ok(report.failures.some((failure) => /scorecard total 87 below 90/.test(failure)))
  assert.ok(report.failures.some((failure) => /Runtime UI is materially improved but still below the 90 percent strict restoration gate/.test(failure)))
})

test('ui v2.1 pass36 requirement audit refuses to collapse source progress into final UI acceptance', () => {
  const audit = buildPass36RequirementAudit({
    repoRoot: process.cwd(),
    artifactDir: path.join(process.cwd(), 'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36'),
    passName: 'pass36l'
  })

  assert.equal(audit.pass, 'pass36s_requirement_audit')
  assert.equal(audit.status, 'incomplete')
  assert.equal(audit.complete, false)
  assert.equal(audit.strictGateEligible, false)
  assert.equal(audit.devtoolsTouched, false)
  assert.equal(audit.runtimeScreenshot, false)
  assert.equal(audit.finalAcceptance.status, 'fail')
  assert.equal(audit.finalAcceptance.requiredScreenshots, 27)
  assert.equal(audit.finalAcceptance.matchedScreenshots, 27)
  assert.equal(audit.counts.proved, 2)
  assert.equal(audit.counts.source_only_progress, 2)
  assert.equal(audit.counts.failed_quality_gate, 2)
  assert.ok(audit.requirements.some((item) => item.id === 'retire_pass35_visual_pass' && item.status === 'proved'))
  assert.ok(audit.requirements.some((item) => item.id === 'news_channel_dock_component' && item.status === 'source_only_progress'))
  assert.ok(audit.requirements.some((item) => item.id === 'news_ranked_focus_list_component' && item.status === 'source_only_progress'))
  assert.ok(audit.requirements.some((item) => item.id === 'asset_workflow_fact_boundary' && item.status === 'source_contract_passed'))
  assert.ok(audit.requirements.some((item) => item.id === 'home_builds_workbench_sync_review' && item.status === 'failed_quality_gate'))
  assert.ok(audit.requirements.some((item) => item.id === 'before_after_crops_overlays' && item.status === 'structural_artifacts_present_but_failed'))
  assert.ok(audit.requirements.some((item) => item.id === 'pass36_runtime_scorecard' && item.status === 'failed_quality_gate'))
  assert.ok(audit.requirements.some((item) => item.id === 'related_test_validation' && item.status === 'proved'))
  assert.match(audit.boundary.join('\n'), /guarded preflight\/merge automation without per-turn user confirmation/)
  assert.match(audit.boundary.join('\n'), /does not touch WeChat DevTools/)
})

test('ui v2.1 pass36 requirement audit writes only to the requested artifact directory', () => {
  const artifactDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-requirement-audit-'))
  const audit = buildPass36RequirementAudit({
    repoRoot: process.cwd(),
    artifactDir: path.join(process.cwd(), 'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36'),
    passName: 'pass36l'
  })
  const paths = writePass36RequirementAudit(audit, { artifactDir })

  assert.equal(path.dirname(paths.jsonPath), artifactDir)
  assert.equal(path.dirname(paths.markdownPath), artifactDir)
  assert.equal(JSON.parse(fs.readFileSync(paths.jsonPath, 'utf8')).pass, 'pass36s_requirement_audit')
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Status: incomplete/)
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /今日重点列表组件级还原/)
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /This audit is read-only/)
})

test('ui v2.1 pass36 final validator accepts a complete runtime artifact set', () => {
  const fixture = createCompletePass36Fixture()
  const report = validatePass36FinalAcceptance({
    repoRoot: fixture.root,
    artifactDir: fixture.artifactDir,
    passName: 'pass36l',
    contract: fixture.contract
  })

  assert.equal(report.status, 'pass')
  assert.equal(report.strictGateEligible, true)
  assert.equal(report.counts.requiredScreenshots, 27)
  assert.equal(report.counts.matchedScreenshots, 27)
  assert.equal(report.failures.length, 0)
})

test('ui v2.1 pass36 final validator rejects mislabeled viewport screenshots', () => {
  const fixture = createCompletePass36Fixture()
  const required = fixture.contract.requiredArtifacts
  const manifestPath = path.join(fixture.artifactDir, required.manifestPattern)
  const manifest = readJson(manifestPath)
  const compact = manifest.scenes.find((scene) => scene.viewportId === 'compact')
  compact.visualCheck.image = { width: 780, height: 1524 }
  compact.visualCheck.viewportWidthMatches = false
  writeJson(manifestPath, manifest)

  const report = validatePass36FinalAcceptance({
    repoRoot: fixture.root,
    artifactDir: fixture.artifactDir,
    passName: 'pass36l',
    contract: fixture.contract
  })

  assert.equal(report.status, 'fail')
  assert.ok(report.failures.some((failure) => /does not match logical viewport width 375/.test(failure)))
  assert.ok(report.failures.some((failure) => /failed viewport width proof/.test(failure)))
})

test('ui v2.1 pass36 final validator rejects fallback screenshots and stale scorecards', () => {
  const fixture = createCompletePass36Fixture()
  const required = fixture.contract.requiredArtifacts
  const manifestPath = path.join(fixture.artifactDir, required.manifestPattern)
  const manifest = readJson(manifestPath)
  manifest.scenes[0].path = 'screens/os_fallback-news.png'
  manifest.scenes[0].captureMethod = 'os-window-fallback'
  writeBytes(path.join(fixture.artifactDir, manifest.scenes[0].path))
  writeJson(manifestPath, manifest)

  const scorecardPath = path.join(fixture.artifactDir, required.scorecardJson)
  const scorecard = readJson(scorecardPath)
  scorecard.currentScoreValidity = 'stale_after_static_component_remediation'
  writeJson(scorecardPath, scorecard)

  const report = validatePass36FinalAcceptance({
    repoRoot: fixture.root,
    artifactDir: fixture.artifactDir,
    passName: 'pass36l',
    contract: fixture.contract
  })

  assert.equal(report.status, 'fail')
  assert.ok(report.failures.some((failure) => /fallback capture method/.test(failure)))
  assert.ok(report.failures.some((failure) => /fallback screenshot path/.test(failure)))
  assert.ok(report.failures.some((failure) => /validity is stale/.test(failure)))
})

test('ui v2.1 pass36 runtime operator package covers every capture and crop without touching DevTools', () => {
  const pkg = buildRuntimeOperatorPackage()
  const contract = buildRuntimeCaptureContract()

  assert.equal(pkg.pass, 'pass36l_runtime_operator_package')
  assert.equal(pkg.devtoolsTouched, false)
  assert.equal(pkg.runtimeScreenshot, false)
  assert.equal(pkg.strictGateEligible, false)
  assert.equal(pkg.notAcceptanceArtifact, true)
  assert.equal(pkg.screenshotMatrix.length, contract.requiredArtifacts.screenshots.length)
  assert.equal(pkg.componentPlans.length, contract.requiredArtifacts.componentComparisons.length)
  assert.equal(pkg.finalValidator.expectedBeforeRuntimeCapture, 'fail')
  assert.equal(pkg.finalValidator.expectedAfterCompleteRuntimeCapture, 'pass')

  const outputs = new Set()
  for (const shot of pkg.screenshotMatrix) {
    assert.ok(shot.route, `${shot.id} should keep route`)
    assert.ok(shot.outputPath.startsWith(`screens-pass36l/${shot.viewportId}/`))
    assert.equal(shot.requiredVisualCheck.nonEmpty, true)
    assert.equal(shot.requiredVisualCheck.minBytes, 5000)
    assert.equal(shot.requiredVisualCheck.imageDimensions, true)
    assert.equal(shot.requiredVisualCheck.viewportWidthMatches, true)
    assert.ok(!outputs.has(shot.outputPath), `${shot.outputPath} should be unique`)
    outputs.add(shot.outputPath)
    shot.targetBoxes.forEach((target) => {
      assert.ok(Array.isArray(target.targetBox), `${shot.id}/${target.regionId} should map to target box`)
    })
  }

  const componentIds = pkg.componentPlans.map((plan) => plan.id)
  assert.deepEqual(componentIds, [
    'news_channel_tab_dock',
    'news_ranked_focus_list',
    'builds_tab_overview',
    'current_spec_workbench'
  ])
  assert.ok(pkg.componentPlans.every((plan) => plan.comparison && plan.overlay && plan.currentCrop))
  assert.match(pkg.operatorRules.join('\n'), /Do not run DevTools CLI login or islogin probes/)
  assert.match(pkg.acceptanceCommandsAfterRuntimeHealth.join('\n'), /low-disturbance runtime probe/)
  assert.match(pkg.acceptanceCommandsAfterAuthorization.join('\n'), /validate-pass36-final-acceptance/)
})

test('ui v2.1 pass36 controlled merge preflight allows Codex-managed writes without touching DevTools', () => {
  const sourceRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-merge-source-'))
  const targetRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-merge-target-'))
  for (const relativePath of MERGE_FILES) {
    const sourcePath = path.join(sourceRoot, relativePath)
    fs.mkdirSync(path.dirname(sourcePath), { recursive: true })
    fs.writeFileSync(sourcePath, `source:${relativePath}\n`, 'utf8')
  }
  const existingTarget = path.join(targetRoot, MERGE_FILES[0])
  fs.mkdirSync(path.dirname(existingTarget), { recursive: true })
  fs.writeFileSync(existingTarget, 'old target\n', 'utf8')

  const plan = buildControlledMergePlan({
    sourceRoot,
    targetRoot,
    env: {}
  })

  assert.equal(plan.pass, 'pass36_controlled_merge_preflight')
  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
  assert.equal(plan.watchedProjectWrite, false)
  assert.equal(plan.writeAuthorized, true)
  assert.deepEqual(plan.requiredEnv, [])
  assert.equal(plan.writePolicy.mode, 'codex_managed_controlled_write')
  assert.equal(plan.writePolicy.disableEnv, WRITE_DISABLE_ENV)
  assert.equal(plan.counts.files, MERGE_FILES.length)
  assert.equal(plan.counts.missingSources, 0)
  assert.ok(plan.changedFiles.includes(MERGE_FILES[0]))
  assert.match(plan.safetyRules.join('\n'), /Default audit mode is read-only/)
  assert.match(plan.safetyRules.join('\n'), /do not require a per-turn user write window/)
  assert.match(plan.safetyRules.join('\n'), /Do not launch, close, restart, login, or probe WeChat DevTools/)

  const result = applyControlledMerge({ sourceRoot, targetRoot, env: {} })
  assert.equal(result.writeAuthorized, true)
  assert.equal(result.devtoolsTouched, false)
  assert.equal(result.runtimeScreenshot, false)
  assert.equal(fs.readFileSync(existingTarget, 'utf8'), `source:${MERGE_FILES[0]}\n`)
})

test('ui v2.1 pass36 controlled merge can be disabled explicitly for dry runs', () => {
  const sourceRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-merge-source-'))
  const targetRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-merge-target-'))
  for (const relativePath of MERGE_FILES) {
    const sourcePath = path.join(sourceRoot, relativePath)
    fs.mkdirSync(path.dirname(sourcePath), { recursive: true })
    fs.writeFileSync(sourcePath, `source:${relativePath}\n`, 'utf8')
  }

  assert.throws(
    () => applyControlledMerge({
      sourceRoot,
      targetRoot,
      env: {
        [WRITE_DISABLE_ENV]: '1'
      }
    }),
    /disabled Codex-managed controlled writes/
  )

  const plan = buildControlledMergePlan({
    sourceRoot,
    targetRoot,
    env: {
      [WRITE_DISABLE_ENV]: '1'
    }
  })

  assert.equal(plan.writeAuthorized, false)
  assert.equal(plan.devtoolsTouched, false)
  assert.equal(plan.runtimeScreenshot, false)
})

test('ui v2.1 pass36 final readiness report refuses to close when capture is not safe', () => {
  const report = buildFinalReadinessReport({
    repoRoot: process.cwd(),
    artifactDir: path.join(process.cwd(), 'artifacts/miniprogram-screenshots/20260703-ui-v2-1-pass36'),
    targetRoot: '/Users/heyesheng/Documents/code/github/wow_mini_program',
    env: {}
  })

  assert.equal(report.pass, 'pass36_final_readiness_report')
  assert.equal(report.status, 'incomplete')
  assert.equal(report.complete, false)
  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.equal(report.watchedProjectWrite, false)
  assert.equal(report.gates.staticSourceAudit, 'pass')
  assert.equal(report.gates.finalRuntimeAcceptance, 'fail')
  assert.equal(report.gates.controlledMerge.writeAuthorized, true)
  assert.equal(
    report.gates.currentDiff.files,
    Object.values(DIFF_GROUPS).reduce((total, files) => total + files.length, 0)
  )
  assert.equal(report.gates.currentDiff.productionUiSourceSame, 15)
  assert.equal(report.gates.currentDiff.productionUiSourceTotal, 15)
  assert.equal(report.gates.currentDiff.pass36GeneratedAssetsSame, 8)
  assert.equal(report.gates.currentDiff.pass36GeneratedAssetsTotal, 8)
  assert.equal(report.gates.currentDiff.missingCurrent, 0)
  assert.equal(report.runtimeEvidence.requiredScreenshots, 27)
  assert.equal(report.runtimeEvidence.matchedScreenshots, 27)
  assert.equal(report.runtimeEvidence.operatorScreenshots, 27)
  assert.equal(report.runtimeEvidence.operatorComponentPlans, 4)
  assert.equal(report.latestRuntimeRunner.present, true)
  assert.ok(
    ['blocked_capture_not_safe', 'failed_runtime_capture'].includes(report.latestRuntimeRunner.status),
    `unexpected runtime runner status: ${report.latestRuntimeRunner.status}`
  )
  if (report.latestRuntimeRunner.status === 'blocked_capture_not_safe') {
    assert.equal(report.latestRuntimeRunner.captureSafe, false)
    assert.equal(report.latestRuntimeRunner.runtimeResponsive, false)
    assert.match(report.latestRuntimeRunner.blockedReason, /captureSafe=false/)
  } else {
    assert.equal(report.latestRuntimeRunner.captureSafe, true)
    assert.equal(report.latestRuntimeRunner.runtimeResponsive, true)
    assert.match(report.latestRuntimeRunner.blockedReason, /Runtime screenshot capture failed/)
  }
  assert.equal(report.latestRuntimeRunner.automatorConnected, true)
  assert.equal(Number.isInteger(report.latestRuntimeRunner.automatorPort), true)
  assert.ok(report.latestRuntimeRunner.automatorPort > 0)
  assert.equal(report.latestRuntimeRunner.automatorError, '')
  assert.ok(report.latestRuntimeRunner.connectionAttemptCount >= 1)
  assert.equal(report.latestBrowserLayoutAudit.present, true)
  assert.equal(report.latestBrowserLayoutAudit.status, 'pass')
  assert.equal(report.latestBrowserLayoutAudit.devtoolsTouched, false)
  assert.equal(report.latestBrowserLayoutAudit.runtimeScreenshot, false)
  assert.equal(report.latestBrowserLayoutAudit.strictGateEligible, false)
  assert.equal(report.latestBrowserLayoutAudit.passedChecks, 8)
  assert.equal(report.latestBrowserLayoutAudit.totalChecks, 8)
  assert.deepEqual(report.latestBrowserLayoutAudit.failures, [])
  assert.equal(report.latestBrowserSceneMatrix.present, true)
  assert.equal(report.latestBrowserSceneMatrix.status, 'pass')
  assert.equal(report.latestBrowserSceneMatrix.devtoolsTouched, false)
  assert.equal(report.latestBrowserSceneMatrix.runtimeScreenshot, false)
  assert.equal(report.latestBrowserSceneMatrix.strictGateEligible, false)
  assert.equal(report.latestBrowserSceneMatrix.scenesPassed, 27)
  assert.equal(report.latestBrowserSceneMatrix.scenesTotal, 27)
  assert.equal(report.latestBrowserSceneMatrix.htmlCount, 3)
  assert.equal(report.latestBrowserSceneMatrix.screenshotCount, 3)
  assert.deepEqual(report.latestBrowserSceneMatrix.failures, [])
  assert.equal(report.latestRuntimeShadowGuard.present, true)
  assert.equal(report.latestRuntimeShadowGuard.status, 'guard_applied_runtime_pending')
  assert.equal(report.latestRuntimeShadowGuard.devtoolsTouched, false)
  assert.match(report.latestRuntimeShadowGuard.changeSummary, /Removed the default WOW_ALLOW_DEVTOOLS_HOT_SYNC=1/)
  assert.ok(report.latestRuntimeShadowGuard.nextRuntimeRule.some((item) => /Pre-sync the clean shadow project/.test(item)))
  assert.equal(report.latestShadowSyncDryRun.present, true)
  assert.equal(report.latestShadowSyncDryRun.status, 'blocked_watched_project_mutation')
  assert.equal(report.latestShadowSyncDryRun.devtoolsTouched, false)
  assert.equal(report.latestShadowSyncDryRun.changeCount, 15)
  assert.ok(report.latestShadowSyncDryRun.copiedFiles.includes('app.json'))
  assert.ok(report.latestShadowSyncDryRun.copiedFiles.includes('pages/news/news.wxss'))
  assert.ok(report.latestShadowSyncDryRun.copiedFiles.includes('project.config.json'))
  assert.equal(report.shadowAppIdState.sourceAppid, 'wx17543b6fc4305479')
  assert.equal(report.shadowAppIdState.noAuthRequiresExplicitEnv, true)
  assert.ok(
    ['active_shadow_appid_matches_source', 'active_shadow_appid_drift'].includes(report.shadowAppIdState.status),
    `unexpected shadow appid status: ${report.shadowAppIdState.status}`
  )
  if (report.shadowAppIdState.status === 'active_shadow_appid_matches_source') {
    assert.equal(report.shadowAppIdState.activeShadowAppid, report.shadowAppIdState.sourceAppid)
    assert.equal(report.shadowAppIdState.activeShadowDrift, false)
    assert.equal(report.shadowAppIdState.activeShadowMatchesSource, true)
  } else {
    assert.notEqual(report.shadowAppIdState.activeShadowAppid, report.shadowAppIdState.sourceAppid)
    assert.equal(report.shadowAppIdState.activeShadowDrift, true)
  }
  assert.equal(report.designGenerationGuard.present, true)
  assert.equal(report.designGenerationGuard.status, 'guarded_staging_default')
  assert.equal(report.designGenerationGuard.devtoolsTouched, false)
  assert.equal(report.designGenerationGuard.watchedProjectWrite, false)
  assert.equal(report.designGenerationGuard.targetAssetsStageByDefault, true)
  assert.equal(report.designGenerationGuard.sourcePreviewStagesByDefault, true)
  assert.equal(report.designGenerationGuard.staticAuditStagesByDefault, true)
  assert.match(report.designGenerationGuard.rule, /staging by default/)
  assert.ok(report.runtimeEvidence.failures.some((failure) => /scorecard total 87 below 90/.test(failure)))
  assert.equal(report.requirementAudit.status, 'incomplete')
  assert.equal(report.requirementAudit.complete, false)
  assert.equal(report.requirementAudit.finalAcceptance.status, 'fail')
  assert.ok(report.requirementAudit.requirements.some((item) => item.id === 'news_ranked_focus_list_component' && item.status === 'source_only_progress'))
  assert.ok(report.requirementAudit.requirements.some((item) => item.id === 'related_test_validation' && item.status === 'proved'))
  assert.equal(report.currentDiff.devtoolsTouched, false)
  assert.equal(report.currentDiff.watchedProjectWrite, false)
  assert.ok(report.objectiveRequirements.some((item) => item.id === 'runtime_scorecard' && item.status === 'failed_quality_gate'))
  assert.ok(report.objectiveRequirements.some((item) => item.id === 'news_focus_list_component' && item.status === 'runtime_reviewed_failed'))
  assert.ok(report.nextStrictSteps.some((step) => /Controlled merge is already applied/.test(step)))
  assert.ok(report.nextStrictSteps.some((step) => /Keep imagegen target slicing and source-only previews in staging/.test(step)))
  assert.ok(report.nextStrictSteps.some((step) => /browser layout audit/.test(step)))
  assert.ok(report.nextStrictSteps.some((step) => /Fix the visual quality failures/.test(step)))
  assert.ok(report.nextStrictSteps.some((step) => /validate-pass36-final-acceptance/.test(step)))
})

test('ui v2.1 pass36 final readiness report writes only to the requested artifact directory', () => {
  const artifactDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-readiness-report-'))
  const report = buildFinalReadinessReport({
    repoRoot: process.cwd(),
    artifactDir,
    targetRoot: process.cwd(),
    env: {}
  })
  const paths = writeFinalReadinessReport(report, { artifactDir })

  assert.equal(path.dirname(paths.jsonPath), artifactDir)
  assert.equal(path.dirname(paths.markdownPath), artifactDir)
  assert.equal(JSON.parse(fs.readFileSync(paths.jsonPath, 'utf8')).pass, 'pass36_final_readiness_report')
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Status: incomplete/)
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Required screenshots: 27/)
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Design Generation Guard/)
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Requirement Audit/)
})

test('ui v2.1 pass36 current diff report classifies same different and missing files without writes', () => {
  const currentRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-diff-current-'))
  const sandboxRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-diff-sandbox-'))
  const groups = {
    productionUiSource: ['same.txt', 'different.txt'],
    pass36GeneratedAssets: ['missing-current.png'],
    verificationAndEvidence: ['missing-sandbox.js', 'missing-both.json']
  }

  fs.writeFileSync(path.join(currentRoot, 'same.txt'), 'same\n')
  fs.writeFileSync(path.join(sandboxRoot, 'same.txt'), 'same\n')
  fs.writeFileSync(path.join(currentRoot, 'different.txt'), 'current\n')
  fs.writeFileSync(path.join(sandboxRoot, 'different.txt'), 'sandbox\n')
  fs.writeFileSync(path.join(sandboxRoot, 'missing-current.png'), 'asset\n')
  fs.writeFileSync(path.join(currentRoot, 'missing-sandbox.js'), 'script\n')

  const report = buildCurrentDiffReport({ currentRoot, sandboxRoot, groups })

  assert.equal(report.devtoolsTouched, false)
  assert.equal(report.watchedProjectWrite, false)
  assert.deepEqual(report.summary, {
    files: 5,
    same: 1,
    different: 1,
    missingCurrent: 1,
    missingSandbox: 1,
    missingBoth: 1
  })
  assert.equal(report.groups.productionUiSource.counts.same, 1)
  assert.equal(report.groups.productionUiSource.counts.different, 1)
  assert.equal(report.groups.pass36GeneratedAssets.counts.missingCurrent, 1)
  assert.equal(report.groups.verificationAndEvidence.counts.missingSandbox, 1)
  assert.equal(report.groups.verificationAndEvidence.counts.missingBoth, 1)
})

test('ui v2.1 pass36 current diff report writes only to requested package directory', () => {
  const currentRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-diff-current-'))
  const sandboxRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-diff-sandbox-'))
  const packageRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-diff-package-'))
  const groups = { productionUiSource: ['same.txt'], pass36GeneratedAssets: [], verificationAndEvidence: [] }
  fs.writeFileSync(path.join(currentRoot, 'same.txt'), 'same\n')
  fs.writeFileSync(path.join(sandboxRoot, 'same.txt'), 'same\n')

  const report = buildCurrentDiffReport({ currentRoot, sandboxRoot, groups })
  const paths = writeCurrentDiffReport(report, { packageRoot })

  assert.equal(path.dirname(paths.jsonPath), packageRoot)
  assert.equal(path.dirname(paths.prettyJsonPath), packageRoot)
  assert.equal(path.dirname(paths.markdownPath), packageRoot)
  assert.equal(JSON.parse(fs.readFileSync(paths.jsonPath, 'utf8')).pass, 'pass36_current_vs_sandbox_readonly_diff')
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Watched project write: false/)
})

test('ui v2.1 pass36 controlled write preflight is ready only when UI source and assets match', () => {
  const currentRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-preflight-current-'))
  const sandboxRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-preflight-sandbox-'))
  const allFiles = Array.from(new Set([
    ...MERGE_FILES,
    ...Object.values(DIFF_GROUPS).flat()
  ]))

  allFiles.forEach((relativePath) => {
    const sandboxPath = path.join(sandboxRoot, relativePath)
    fs.mkdirSync(path.dirname(sandboxPath), { recursive: true })
    fs.writeFileSync(sandboxPath, `sandbox:${relativePath}\n`, 'utf8')
  })
  allFiles.forEach((relativePath) => {
    const currentPath = path.join(currentRoot, relativePath)
    fs.mkdirSync(path.dirname(currentPath), { recursive: true })
    fs.writeFileSync(currentPath, `sandbox:${relativePath}\n`, 'utf8')
  })

  const ready = buildWriteWindowPreflight({ currentRoot, sandboxRoot, env: {} })
  assert.equal(ready.pass, 'pass36_controlled_write_preflight')
  assert.equal(ready.legacyPassAlias, 'pass36_write_window_preflight')
  assert.equal(ready.status, 'ready_for_controlled_write')
  assert.equal(ready.devtoolsTouched, false)
  assert.equal(ready.watchedProjectWrite, false)
  assert.equal(ready.checks.productionUiSource.ready, true)
  assert.equal(ready.checks.pass36GeneratedAssets.ready, true)
  assert.equal(ready.checks.controlledMerge.missingSources, 0)
  assert.equal(ready.checks.unexpectedMergeFiles.length, 0)

  fs.writeFileSync(path.join(currentRoot, 'pages/news/news.wxss'), 'drift\n', 'utf8')
  const notReady = buildWriteWindowPreflight({ currentRoot, sandboxRoot, env: {} })
  assert.equal(notReady.status, 'not_ready_for_controlled_write')
  assert.equal(notReady.checks.productionUiSource.ready, false)
  assert.match(notReady.nextAction, /Do not apply controlled writes yet/)
})

test('ui v2.1 pass36 controlled write preflight writes only to requested package directory', () => {
  const currentRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-preflight-current-'))
  const sandboxRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-preflight-sandbox-'))
  const packageRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-preflight-package-'))
  const requiredFile = 'pages/news/news.js'
  fs.mkdirSync(path.dirname(path.join(currentRoot, requiredFile)), { recursive: true })
  fs.mkdirSync(path.dirname(path.join(sandboxRoot, requiredFile)), { recursive: true })
  fs.writeFileSync(path.join(currentRoot, requiredFile), 'same\n', 'utf8')
  fs.writeFileSync(path.join(sandboxRoot, requiredFile), 'same\n', 'utf8')
  const report = buildWriteWindowPreflight({ currentRoot, sandboxRoot, env: {} })
  const paths = writeWriteWindowPreflight(report, { packageRoot })

  assert.equal(path.dirname(paths.jsonPath), packageRoot)
  assert.equal(path.dirname(paths.markdownPath), packageRoot)
  assert.equal(JSON.parse(fs.readFileSync(paths.jsonPath, 'utf8')).pass, 'pass36_controlled_write_preflight')
  assert.match(fs.readFileSync(paths.markdownPath, 'utf8'), /Watched project write: false/)
})

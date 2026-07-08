const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { buildShadowAppIdState } = require('../artifacts/ui-v2-1-strict-restoration/pass36-shadow-appid-state')

test('mini-program pack options ignore non-client workspace directories without dropping runtime fallback modules', () => {
  const projectConfig = JSON.parse(fs.readFileSync('project.config.json', 'utf8'))
  const ignored = new Set((projectConfig.packOptions?.ignore || []).map((entry) => `${entry.type}:${entry.value}`))

  for (const value of [
    '.worktrees/**',
    '.git/**',
    'artifacts/**',
    'tmp/**',
    'tests/**',
    'docs/**',
    'websim/**'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  for (const value of [
    'assets/generated/ui-v2-1-slices/20260703/news_tab_icon_atlas_pass36.png',
    'assets/generated/ui-v2-1-slices/20260703/wow_layout_material_atlas.png',
    'assets/generated/ui-v2-1-slices/20260703/builds_workbench_material_atlas.png',
    'assets/generated/ui-v2-1-slices/20260703/builds_workbench_panel_atlas_v2.png'
  ]) {
    assert.ok(ignored.has(`file:${value}`), `${value} should be ignored because only sliced runtime assets belong in the package`)
  }

  for (const value of [
    'server/**/*.py',
    'server/*.py',
    'server/**/*.sql',
    'server/**/*.json',
    'server/**/*.pyc',
    'server/**/__pycache__/**',
    'server/data/**',
    'server/*.sh',
    'server/*.service',
    'server/*.timer'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  for (const value of [
    'assets/generated/**/design-board.*',
    'assets/generated/**/*source*.*',
    'assets/generated/**/*reference*.*',
    'assets/generated/**/*atlas*.*',
    'assets/generated/**',
    'assets/generated/ui-redesign/20260630/**',
    'assets/generated/ui-v2-restoration/**',
    'assets/generated/ui-v3/**',
    'assets/generated/ui-v3-1/**'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should keep design-only imagegen assets out of the runtime package`)
  }

  assert.equal(ignored.has('glob:server/**'), false, 'server JS fallback modules must stay package-visible')
  assert.ok(ignored.has('glob:scripts/**'), 'scripts should stay out of real-device source packages')

  for (const runtimeModule of [
    'server/news/home-payload.js',
    'server/news/articles.seed.js',
    'server/builds/home-payload.js',
    'server/pve/home-payload.js',
    'server/game-season.js'
  ]) {
    assert.ok(fs.existsSync(runtimeModule), `${runtimeModule} should remain available to mini-program require()`)
  }
})

test('pass36 runtime keeps the default WebView renderer until real DevTools screenshots are stable', () => {
  const appConfig = JSON.parse(fs.readFileSync('app.json', 'utf8'))

  assert.notEqual(appConfig.renderer, 'skyline')
  assert.equal(appConfig.rendererOptions, undefined)
  assert.equal(appConfig.componentFramework, undefined)
})

test('strict visual capture scripts keep runtime outputs outside the watched project tree', () => {
  const captureScripts = [
    'artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/capture-official.js',
    'artifacts/miniprogram-screenshots/20260702-real-ui-first-pass/capture-news-scrolled.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-news-pass/capture-news.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-official.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass3.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass4.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass5.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js',
    'artifacts/ui-v2-1-strict-restoration/devtools-window-capture.js'
  ]

  for (const scriptPath of captureScripts) {
    const source = fs.readFileSync(scriptPath, 'utf8')

    assert.match(source, /os\.tmpdir\(\)/, `${scriptPath} should default captures to the system temp directory`)
    assert.match(source, /wow-miniprogram-screenshots/, `${scriptPath} should write to the shared temp capture namespace`)
    assert.doesNotMatch(source, /const\s+artifactDir\s*=\s*__dirname/, `${scriptPath} should not write captures beside the script`)
    assert.doesNotMatch(source, /WOW_CAPTURE_ARTIFACT_DIR\s*\|\|\s*scriptDir/, `${scriptPath} should not fall back to the repo script dir`)
  }
})

test('active screenshot scripts refuse watched repo output unless explicitly overridden', () => {
  const captureScripts = [
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js',
    'artifacts/ui-v2-1-strict-restoration/devtools-window-capture.js'
  ]

  for (const scriptPath of captureScripts) {
    const source = fs.readFileSync(scriptPath, 'utf8')

    assert.match(source, /function isInside\(child, parent\)/, scriptPath)
    assert.match(source, /WOW_ALLOW_REPO_CAPTURE_OUTPUT !== '1'/, scriptPath)
    assert.match(source, /inside a project\/source tree|inside the watched repo tree/, scriptPath)
  }
})

test('DevTools window capture falls back to cropped fullscreen without retaining private screen dumps', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/devtools-window-capture.js', 'utf8')

  assert.match(source, /macos_fullscreen_crop_fallback/)
  assert.match(source, /full-screen-temp\.png/)
  assert.match(source, /fs\.rmSync\(fullScreenPath,\s*\{\s*force:\s*true\s*\}\)/)
  assert.match(source, /strictGateEligible:\s*false/)
  assert.match(source, /function inspectImage\(imagePath\)/)
  assert.match(source, /nearBlackRatio/)
  assert.match(source, /visible_window_black_or_capture_blank/)
  assert.match(source, /runtimeFactBoundary/)
  assert.match(source, /cannotProve/)
  assert.doesNotMatch(source, /fullScreen:\s*path\.relative/)
})

test('strict official capture script reuses existing DevTools by default', () => {
  const scriptPaths = [
    'artifacts/miniprogram-screenshots/20260702-ui-v2-restoration/capture-official.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-official.js'
  ]

  for (const scriptPath of scriptPaths) {
    const source = fs.readFileSync(scriptPath, 'utf8')
    assert.match(source, /const allowDevToolsLaunch = process\.env\.WOW_ALLOW_DEVTOOLS_LAUNCH === '1'/, scriptPath)
    assert.match(source, /const allowDevToolsAuto = process\.env\.WOW_ALLOW_DEVTOOLS_AUTO === '1'/, scriptPath)
    assert.match(source, /const reuseIdeAuto = process\.env\.WOW_REUSE_IDE_AUTO !== '0'/, scriptPath)
    assert.match(source, /!allowDevToolsAuto \|\| process\.env\.WOW_DIRECT_CONNECT_AUTO === '1'/, scriptPath)
    assert.match(source, /Refusing to launch a new WeChat DevTools instance/, scriptPath)
    assert.match(source, /WOW_CLOSE_DEVTOOLS_AFTER_CAPTURE === '1' && allowDevToolsLaunch/, scriptPath)
  }
})

test('legacy capture scripts guard DevTools login-affecting launch and close paths', () => {
  const legacyOfficialScripts = [
    'artifacts/miniprogram-screenshots/20260630-workbench-redesign/capture-official.js',
    'artifacts/miniprogram-screenshots/20260702-ui-implementation-v1/capture-official.js'
  ]

  for (const scriptPath of legacyOfficialScripts) {
    const source = fs.readFileSync(scriptPath, 'utf8')
    assert.match(source, /const allowDevToolsLaunch = process\.env\.WOW_ALLOW_DEVTOOLS_LAUNCH === '1'/, scriptPath)
    assert.match(source, /const allowDevToolsAuto = process\.env\.WOW_ALLOW_DEVTOOLS_AUTO === '1'/, scriptPath)
    assert.match(source, /const reuseIdeAuto = process\.env\.WOW_REUSE_IDE_AUTO !== '0'/, scriptPath)
    assert.match(source, /!allowDevToolsAuto \|\| process\.env\.WOW_DIRECT_CONNECT_AUTO === '1'/, scriptPath)
    assert.match(source, /Refusing to launch a new WeChat DevTools instance from this legacy capture script/, scriptPath)
    assert.match(source, /WOW_CLOSE_DEVTOOLS_AFTER_CAPTURE === '1' && allowDevToolsLaunch/, scriptPath)
  }

  const previewSource = fs.readFileSync(
    'artifacts/miniprogram-screenshots/20260630-workbench-redesign-preview/capture-preview.js',
    'utf8'
  )
  assert.match(previewSource, /const allowPreviewDevToolsLaunch = process\.env\.WOW_ALLOW_PREVIEW_DEVTOOLS_LAUNCH === '1'/)
  assert.match(previewSource, /Preview touristappid capture is disabled by default/)
  assert.match(previewSource, /WOW_CLOSE_PREVIEW_DEVTOOLS_AFTER_CAPTURE === '1'/)
  assert.doesNotMatch(previewSource, /miniProgram\) await miniProgram\.close\(\)/)
})

test('legacy news-only capture scripts do not enable DevTools automation by default', () => {
  const scriptPaths = [
    'artifacts/miniprogram-screenshots/20260702-real-ui-first-pass/capture-news-scrolled.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-news-pass/capture-news.js'
  ]

  for (const scriptPath of scriptPaths) {
    const source = fs.readFileSync(scriptPath, 'utf8')
    assert.match(source, /const allowDevToolsAuto = process\.env\.WOW_ALLOW_DEVTOOLS_AUTO === '1'/, scriptPath)
    assert.match(source, /Default path only connects to an already-open automation port/, scriptPath)
    assert.match(source, /if \(!allowDevToolsAuto\)/, scriptPath)
  }
})

test('strict pass capture records viewport ids for visual gate matching', () => {
  const source = fs.readFileSync('artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js', 'utf8')

  assert.match(source, /const captureViewportId = process\.env\.WOW_CAPTURE_VIEWPORT_ID \|\| 'standard'/)
  assert.match(source, /viewport:\s*captureViewportId/)
  assert.match(source, /viewportId:\s*captureViewportId/)
  assert.match(source, /viewportName:\s*captureViewportName/)
  assert.match(source, /logicalSize:\s*captureViewportName/)
  assert.match(source, /function readPngSize\(filePath\)/)
  assert.match(source, /viewportWidthMatches/)
  assert.match(source, /viewport_width_mismatch/)
  assert.match(source, /WOW_CAPTURE_SCENE_COOLDOWN_MS/)
  assert.match(source, /sceneCooldownMs/)
  assert.match(source, /WOW_CAPTURE_SKIP_HEALTH_GATE/)
  assert.match(source, /function runCaptureHealthGate\(\)/)
  assert.match(source, /--runtime-probe/)
  assert.match(source, /captureSafe/)
  assert.match(source, /capture_gate_not_safe/)
  assert.match(source, /checking_capture_health_gate/)
  assert.match(source, /const viewportSuffix = captureViewportId === 'standard' \? '' : `_\$\{captureViewportId\}`/)
  assert.match(source, /function sceneRecordKey\(record\)/)
  assert.match(source, /sceneRecordKey\(item\) !== sceneRecordKey\(record\)/)
  assert.match(source, /capturedViewports/)
})

test('strict pass capture diagnoses DevTools saveFile quota failures without treating them as visual evidence', () => {
  const source = fs.readFileSync('artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js', 'utf8')

  assert.match(source, /function collectDevToolsAppFileSystemStats\(appid\)/)
  assert.match(source, /App\.captureScreenshot saveFile limit/)
  assert.match(source, /function isDevToolsSaveFileLimitError\(error\)/)
  assert.match(source, /failureCategory = 'devtools_save_file_limit'/)
  assert.match(source, /strictGateEligible = false/)
  assert.match(source, /devtoolsAppFileSystem = collectDevToolsAppFileSystemStats/)
})

test('strict pass capture fails fast on App.captureScreenshot timeouts', () => {
  const source = fs.readFileSync('artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js', 'utf8')

  assert.match(source, /function isScreenshotTimeoutError\(error\)/)
  assert.match(source, /failureCategory = 'app_capture_screenshot_timeout'/)
  assert.match(source, /failed_screenshot_timeout/)
  assert.match(source, /stopping \$\{captureViewportId\} viewport early/)
})

test('strict pass capture can require a clean DevTools shadow project', () => {
  const source = fs.readFileSync('artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js', 'utf8')

  assert.match(source, /WOW_CAPTURE_RUNTIME_PROJECT_ROOT/)
  assert.match(source, /WOW_REQUIRE_DEVTOOLS_SHADOW/)
  assert.match(source, /inspectRuntimeProjectRoot/)
  assert.match(source, /usesShadowProject/)
  assert.match(source, /hasGitDir/)
  assert.match(source, /hasArtifactsDir/)

  const syncSource = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/sync-devtools-shadow.js', 'utf8')
  assert.match(syncSource, /wow_mini_program_devtools_run/)
  assert.ok(syncSource.includes("'.git/'"))
  assert.ok(syncSource.includes("'artifacts/'"))
  assert.match(syncSource, /WOW_OPEN_DEVTOOLS_SHADOW/)
  assert.match(syncSource, /WOW_DEVTOOLS_ACTIVE_SHADOW_RECORD/)
  assert.match(syncSource, /WOW_CLOSE_STALE_DEVTOOLS_SHADOWS/)
  assert.match(syncSource, /WOW_PASS36_CAPTURE_AUTHORIZED/)
  assert.match(syncSource, /WOW_ALLOW_DEVTOOLS_CLI_OPEN/)
  assert.match(syncSource, /WOW_ALLOW_DEVTOOLS_CLI_CLOSE/)
  assert.match(syncSource, /function assertDevToolsControlAuthorized/)
  assert.match(syncSource, /open-skipped-cli-control-not-authorized/)
  assert.match(syncSource, /cli-open-not-authorized/)
  assert.match(syncSource, /Opening or closing DevTools can disturb the current logged-in window/)
  assert.match(syncSource, /wow-devtools-active-shadow\.json/)
  assert.match(syncSource, /handleRecordedShadowBeforeOpen/)
  assert.match(syncSource, /Refusing to open another DevTools shadow/)
  assert.match(syncSource, /CLI close can disturb the logged-in WeChat DevTools window/)
  assert.match(syncSource, /\['close', '--project', recordedShadowRoot/)
  assert.ok(syncSource.includes('.devtools-shadow-source.json'))
  assert.match(syncSource, /Refusing to create DevTools shadow inside the watched source repo/)
})

test('DevTools shadow sync defaults to incremental stable-marker updates', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/sync-devtools-shadow.js', 'utf8')

  assert.match(source, /WOW_DEVTOOLS_SHADOW_SYNC_MODE \|\| 'incremental'/)
  assert.match(source, /syncMode === 'incremental'/)
  assert.match(source, /syncMode === 'full'/)
  assert.match(source, /writeJsonIfChanged\(shadowMarkerPath/)
  assert.match(source, /shadowMetadataRoot/)
  assert.match(source, /\$\{shadowRoot\}\.metadata/)
  assert.match(source, /legacyShadowManifestPath/)
  assert.doesNotMatch(source, /createdAt:\s*new Date\(\)\.toISOString\(\)/)
  assert.ok(source.includes("'websim/'"), 'runtime shadow should exclude WebSim source directories')
  assert.ok(source.includes("'server/data/'"), 'runtime shadow should exclude backend data directories')
  assert.ok(source.includes("'server/migrations/'"), 'runtime shadow should exclude backend migration directories')
  assert.match(source, /generatedRuntimeAssetAllowList/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_SHADOW_BULK_MUTATION/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_HOT_SYNC/)
  assert.match(source, /WOW_DEVTOOLS_CAPTURE_SAFE_HEALTH_REPORT/)
  assert.match(source, /readHotSyncCaptureSafeProof/)
  assert.match(source, /explicitly-allowed-with-capture-safe-proof/)
  assert.match(source, /missing-capture-safe-health-report/)
  assert.match(source, /capture-safe proof is missing, stale, or unsafe/)
  assert.match(source, /WOW_PASS36_CAPTURE_AUTHORIZED/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_CLI_OPEN/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_CLI_CLOSE/)
  assert.match(source, /Shadow sync completed without opening, closing, logging in, or probing WeChat DevTools/)
  assert.match(source, /WOW_DEVTOOLS_SHADOW_SYNC_DRY_RUN/)
  assert.match(source, /WOW_DEVTOOLS_SHADOW_DRY_RUN_OUTPUT/)
  assert.match(source, /pass36as_shadow_sync_dry_run_preflight/)
  assert.match(source, /fs\.writeFileSync\(dryRunOutputPath/)
  assert.match(source, /buildIncrementalMutationPlan/)
  assert.match(source, /safeGuardCheck/)
  assert.match(source, /Dry run only: no shadow files/)
  assert.match(source, /blocked_watched_project_mutation/)
  assert.match(source, /WOW_DEVTOOLS_SHADOW_BULK_MUTATION_LIMIT/)
  assert.match(source, /assertBulkShadowMutationSafe/)
  assert.match(source, /assertHotSyncSafe/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_SHADOW_MARKER_UPDATE/)
  assert.match(source, /devtools-running-bookkeeping-must-not-hot-compile/)
  assert.match(source, /markerUpdateSkipped/)
  assert.match(source, /runtimeCaptureAuthorized/)
  assert.match(source, /inspectDevToolsProcesses/)
  assert.match(source, /Codex-managed source writes are allowed in the repo/)
  assert.match(source, /active DevTools runtime project must not be mutated by iterative WXML\/WXSS\/JS edits/)
  assert.match(source, /hot-compile storm/)
  assert.match(source, /expose an expired DevTools login token/)
  assert.match(source, /Even single-file hot compiles can expose an expired DevTools login token/)
  assert.match(source, /collectExcludedShadowFiles/)
  assert.match(source, /removeShadowFiles/)
  assert.match(source, /--delete-excluded/)
  assert.match(source, /source\|reference\|atlas/)
  assert.match(source, /fileNeedsCopy/)
  assert.match(source, /copyFileToShadow/)
  assert.match(source, /pruneEmptyDirs/)
})

test('DevTools shadow sync preserves the real appid by default after developer authorization', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/sync-devtools-shadow.js', 'utf8')

  assert.match(source, /WOW_DEVTOOLS_SHADOW_NO_AUTH === '1'/)
  assert.match(source, /WOW_DEVTOOLS_SHADOW_APPID \|\| 'touristappid'/)
  assert.match(source, /function buildShadowProjectConfigContent/)
  assert.match(source, /appid:\s*shadowAppId/)
  assert.match(source, /relativePath === 'project\.config\.json'/)
  assert.match(source, /writeTextIfChanged\(projectConfigPath, buildShadowProjectConfigContent\(\)\)/)
  assert.match(source, /runtimeOverrides/)
  assert.match(source, /noAuthShadowAppId/)
})

test('strict UI production imagegen materials stay inside mini-program performance budget', () => {
  const manifest = JSON.parse(fs.readFileSync('assets/generated/ui-v2-1-slices/20260703/strict-production-manifest.json', 'utf8'))
  const budgetBytes = 100 * 1024
  const oversized = []

  for (const group of manifest.groups) {
    for (const asset of group.productionAssets) {
      const assetPath = `assets/generated/ui-v2-1-slices/${asset}`
      const stat = fs.statSync(assetPath)
      if (stat.size > budgetBytes) {
        oversized.push(`${group.id}:${asset}:${Math.round(stat.size / 1024)}KB`)
      }
    }
  }

  assert.deepEqual(oversized, [], 'production UI materials should stay below 100KB each to avoid DevTools simulator stalls')
})

test('strict UI production imagegen manifest forbids mock system chrome', () => {
  const manifest = JSON.parse(fs.readFileSync('assets/generated/ui-v2-1-slices/20260703/strict-production-manifest.json', 'utf8'))
  const text = JSON.stringify(manifest)

  assert.match(text, /system status bar/)
  assert.match(text, /clock/)
  assert.match(text, /battery/)
  assert.match(text, /Wi-Fi/)
  assert.match(text, /WeChat capsule/)
  assert.match(text, /phone chrome/)
  assert.match(text, /Do not render design mock status bars/)
})

test('target asset preparation stages generated files outside the watched mini-program by default', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/prepare-target-assets.py', 'utf8')

  assert.match(source, /WOW_UI_TARGET_OUTPUT_MODE",\s*"staging"/)
  assert.match(source, /WOW_UI_TARGET_STAGING_ROOT/)
  assert.match(source, /WOW_ALLOW_WATCHED_PROJECT_GENERATION/)
  assert.match(source, /Refusing to write generated UI target assets into the watched repo/)
  assert.match(source, /REPO_SLICE_DIR\s*=\s*ROOT \/ "assets\/generated\/ui-v2-1-slices\/20260702"/)
  assert.match(source, /"repoWritesAllowed":\s*paths\["mode"\]\s*==\s*"repo"/)
})

test('source-only visual previews stage comparison outputs outside the watched mini-program by default', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/create-pass36n-source-preview.py', 'utf8')

  assert.match(source, /WOW_PASS36_SOURCE_PREVIEW_OUTPUT_MODE",\s*"staging"/)
  assert.match(source, /WOW_PASS36_SOURCE_PREVIEW_OUTPUT_ROOT/)
  assert.match(source, /STAGING_ROOT \/ "artifacts\/miniprogram-screenshots\/20260703-ui-v2-1-pass36"/)
  assert.match(source, /"repoWritesAllowed":\s*OUTPUT_MODE\s*==\s*"repo"/)
  assert.match(source, /path_from_display/)
})

test('static visual audits stage report outputs outside the watched mini-program by default', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/pass36-static-scope-audit.js', 'utf8')

  assert.match(source, /WOW_PASS36_STATIC_AUDIT_OUTPUT_MODE \|\| 'staging'/)
  assert.match(source, /WOW_PASS36_STATIC_AUDIT_OUTPUT_ROOT/)
  assert.match(source, /wow-pass36-static-audit/)
  assert.match(source, /repoWritesAllowed:\s*outputMode === 'repo'/)
  assert.match(source, /displayPath\(auditJsonPath\)/)
})

test('DevTools health check reports multi-instance login risks', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/devtools-health-check.js', 'utf8')

  assert.match(source, /function inspectDevToolsProcesses\(\)/)
  assert.match(source, /function inspectDevToolsWindows\(\)/)
  assert.match(source, /count of windows/)
  assert.match(source, /noVisibleWindowRisk/)
  assert.match(source, /zero windows/)
  assert.match(source, /requireRuntimeResponsive/)
  assert.match(source, /runtimeSmoke/)
  assert.match(source, /runtime smoke currentPage/)
  assert.match(source, /multipleInstallPaths/)
  assert.match(source, /multipleUserDataDirs/)
  assert.match(source, /multipleMainInstances/)
  assert.match(source, /multiInstanceRisk/)
  assert.match(source, /WOW_DEVTOOLS_HEALTH_CLI_LOGIN_PROBE/)
  assert.match(source, /Default health checks avoid login-affecting probes/)
  assert.match(source, /WOW_DEVTOOLS_HEALTH_RUNTIME_PROBE/)
  assert.match(source, /Default health checks avoid runtime\/page\/selector probes/)
  assert.match(source, /runtimeResponsive/)
  assert.match(source, /captureSafe/)
  assert.match(source, /stepOk\(report\.automator\.currentPage\)/)
  assert.match(source, /function parseArgs\(argv\)/)
  assert.match(source, /--runtime-probe/)
  assert.match(source, /--output-dir/)
  assert.match(source, /--automator-port/)
  assert.match(source, /WOW_DEVTOOLS_HEALTH_SCREENSHOT_PROBE/)
  assert.match(source, /App\.captureScreenshot/)
  assert.match(source, /wechatwebdevtools\|微信开发者工具/)
  assert.match(source, /function inspectListeningTcpPorts\(\)/)
  assert.match(source, /function websocketProbeHint\(port\)/)
  assert.match(source, /function buildPortProfiles\(listeningTcpPorts, candidates\)/)
  assert.match(source, /function attachAutomatorAttemptsToPortProfiles\(portProfiles, attempts\)/)
  assert.match(source, /portProfiles/)
  assert.match(source, /devtools_debugger_json_endpoint/)
  assert.match(source, /miniprogram_automator_runtime_candidate/)
  assert.match(source, /candidateForExplicitAutomator/)
  assert.match(source, /function candidateAutomatorPorts\(listeningTcpPorts\)/)
  assert.match(source, /function connectExistingAutomator\(candidates\)/)
  assert.match(source, /function classifyAutomatorHealth\(report\)/)
  assert.match(source, /default_automator_port_closed/)
  assert.match(source, /candidate_ports_not_miniprogram_automator/)
  assert.match(source, /connected_non_runtime_tool_endpoint/)
  assert.match(source, /runtime_not_responsive/)
  assert.match(source, /healthCategory/)
  assert.match(source, /cliLifecycleCommandsUsed:\s*\[\]/)
  assert.match(source, /does not call DevTools open, close, quit, login, cache reset, project switch, or cleanup commands/)
  assert.match(source, /auto-detected-existing-devtools/)
  assert.match(source, /connectionAttempts/)
  assert.match(source, /hasRuntimeSdk/)
  assert.match(source, /fallbackConnection/)
  assert.match(source, /!explicitAutomatorPort && !connection\.hasRuntimeSdk/)
  assert.match(source, /record\.port >= 9000/)
  assert.match(source, /WECHAT_AUTOMATOR_PORT/)
  assert.match(source, /WOW_DEVTOOLS_HEALTH_NO_FORCE_EXIT/)
  assert.match(source, /process\.exit\(process\.exitCode \|\| 0\)/)

  const connectorSource = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/connect-miniprogram-automator.js', 'utf8')
  assert.match(connectorSource, /out\/Connection/)
  assert.match(connectorSource, /out\/MiniProgram/)
  assert.match(connectorSource, /Tool\.getInfo/)
  assert.match(connectorSource, /toolInfo\.SDKVersion \|\| toolInfo\.version/)
  assert.match(connectorSource, /hasRuntimeSdk/)
})

test('pass36 DevTools login resume does not treat QR timeout as completed login', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pass36-login-resume-'))
  const loginResultPath = path.join(root, 'login-result.json')
  fs.writeFileSync(loginResultPath, `${JSON.stringify({
    status: 'FAIL',
    errMsg: 'Error: 二维码超时，请重试 (code 25)'
  })}\n`)

  const modulePath = path.resolve('artifacts/ui-v2-1-strict-restoration/resume-pass36-after-devtools-login.js')
  const previousLoginResult = process.env.WOW_DEVTOOLS_LOGIN_RESULT
  process.env.WOW_DEVTOOLS_LOGIN_RESULT = loginResultPath
  delete require.cache[modulePath]
  const { buildReport } = require(modulePath)
  const report = buildReport({ runAfterLogin: true })
  delete require.cache[modulePath]
  if (previousLoginResult === undefined) {
    delete process.env.WOW_DEVTOOLS_LOGIN_RESULT
  } else {
    process.env.WOW_DEVTOOLS_LOGIN_RESULT = previousLoginResult
  }

  assert.equal(report.status, 'blocked_devtools_login_failed')
  assert.equal(report.login.loginCompleted, false)
  assert.equal(report.login.loginFailed, true)
  assert.equal(report.devtoolsLifecycleTouched, false)
  assert.equal(report.runtimeScreenshot, false)
  assert.deepEqual(report.steps, [])

  const source = fs.readFileSync(modulePath, 'utf8')
  assert.match(source, /waiting_for_user_scanned_login/)
  assert.match(source, /blocked_devtools_login_failed/)
  assert.match(source, /Runtime screenshots remain gated on captureSafe=true/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]login['"]/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]islogin['"]/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]auto['"]/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]preview['"]/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]upload['"]/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]close['"]/)
  assert.doesNotMatch(source, /runStep\([^,]+,\s*cliPath,\s*\[\s*['"]quit['"]/)
})

test('pass36 runtime acceptance runner is captureSafe-gated and does not control DevTools lifecycle', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/run-pass36-runtime-acceptance.js', 'utf8')

  assert.match(source, /devtools-health-check\.js/)
  assert.match(source, /--runtime-probe/)
  assert.match(source, /function parseArgs\(argv\)/)
  assert.match(source, /--wait-for-capture-safe/)
  assert.match(source, /WOW_PASS36_WAIT_FOR_CAPTURE_SAFE/)
  assert.match(source, /waitForCaptureSafe/)
  assert.match(source, /blocked_wait_timeout/)
  assert.match(source, /browserLayoutAuditPreflight/)
  assert.match(source, /gateBrowserLayoutAudit/)
  assert.match(source, /pass36u-browser-layout-audit\.json/)
  assert.match(source, /blocked_browser_layout_audit_/)
  assert.match(source, /browserSceneMatrixPreflight/)
  assert.match(source, /gateBrowserSceneMatrix/)
  assert.match(source, /pass36v-browser-scene-matrix\.json/)
  assert.match(source, /blocked_browser_scene_matrix_/)
  assert.match(source, /all 27 planned scenes/)
  assert.match(source, /before any DevTools health probe/)
  assert.match(source, /captureSafe/)
  assert.match(source, /blocked_capture_not_safe/)
  assert.match(source, /blocked_automator_unavailable/)
  assert.match(source, /sync-devtools-shadow\.js/)
  assert.match(source, /capture-pass6\.js/)
  assert.match(source, /create-pass36l-runtime-evidence\.py/)
  assert.match(source, /strict-visual-gate\.js/)
  assert.match(source, /validate-pass36-final-acceptance\.js/)
  assert.match(source, /WOW_CAPTURE_RUNTIME_PROJECT_ROOT/)
  assert.match(source, /WOW_SOURCE_REPO_ROOT/)
  assert.match(source, /WOW_CAPTURE_PASS/)
  assert.match(source, /WOW_CAPTURE_VIEWPORT_ID/)
  assert.match(source, /WOW_PASS36L_APPEND/)
  assert.match(source, /WOW_CAPTURE_ARTIFACT_DIR/)
  assert.match(source, /strict-visual-gate-\$\{passName\}\.json/)
  assert.match(source, /WOW_DEVTOOLS_ACTIVE_SHADOW_RECORD/)
  assert.match(source, /wow-devtools-active-shadow\.json/)
  assert.match(source, /function resolveShadowRoot\(\)/)
  assert.match(source, /recorded\.shadowRoot/)
  assert.match(source, /Optional wait mode only repeats the same health gate/)
  assert.match(source, /authorizes DevTools shadow hot-sync only after captureSafe=true/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_SHADOW_BULK_MUTATION:\s*'1'/)
  assert.match(source, /No visible DevTools window risk/)
  assert.match(source, /devtoolsWindowCount/)
  assert.match(source, /WOW_ALLOW_DEVTOOLS_HOT_SYNC:\s*'1'/)
  assert.match(source, /WOW_DEVTOOLS_CAPTURE_SAFE_HEALTH_REPORT:\s*report\.health\.reportPath/)
  assert.match(source, /captureSafe=true/)
  assert.match(source, /Shadow sync failed after captureSafe=true/)
  assert.doesNotMatch(source, /WECHAT_DEVTOOLS_CLI/)
  assert.doesNotMatch(source, /auto --project/)
  assert.doesNotMatch(source, /\['open'/)
  assert.doesNotMatch(source, /\['close'/)
  assert.doesNotMatch(source, /\['quit'/)
  assert.doesNotMatch(source, /\['login'/)
  assert.doesNotMatch(source, /\['islogin'/)
})

test('pass36 runtime evidence derives viewport proof from manifest dimensions', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/create-pass36l-runtime-evidence.py', 'utf8')

  assert.match(source, /def viewport_resize_summary\(manifest\):/)
  assert.match(source, /viewportWidthMatches/)
  assert.match(source, /len\(set\(required_widths\)\) == len\(required_widths\)/)
  assert.match(source, /viewportResizeSummary/)
  assert.match(source, /viewportResizeProven/)
  assert.doesNotMatch(source, /current files have identical pixel width/)
  assert.doesNotMatch(source, /archived PNG dimensions are identical/)
})

test('pass36 automation recovery package is read-only and keeps screenshot acceptance strict', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/create-pass36-automation-recovery-package.js', 'utf8')

  assert.match(source, /pass36ap_automation_recovery_package/)
  assert.match(source, /blocked_waiting_for_automation/)
  assert.match(source, /blocked_no_visible_devtools_window/)
  assert.match(source, /blocked_runtime_unresponsive/)
  assert.match(source, /blocked_automator_endpoint_unavailable/)
  assert.match(source, /blocked_devtools_login_required/)
  assert.match(source, /ready_to_resume_runtime_acceptance/)
  assert.match(source, /runtimeResponsive/)
  assert.match(source, /healthCategory/)
  assert.match(source, /healthDiagnosis/)
  assert.match(source, /noVisibleWindowRisk/)
  assert.match(source, /not proof that WeChat login expired/)
  assert.match(source, /devtoolsWindowCount/)
  assert.match(source, /latestDevToolsLoginRequiredState/)
  assert.match(source, /pass36aq-devtools-login-required\.json/)
  assert.match(source, /User-scanned login/)
  assert.match(source, /openProjectAfterLoginCommand/)
  assert.match(source, /automated login loops/)
  assert.match(source, /System Events reports/)
  assert.match(source, /runtimeErrors/)
  assert.match(source, /portProfiles/)
  assert.match(source, /Port profile categories/)
  assert.match(source, /page stack, runtime API, or selector probes/)
  assert.match(source, /WECHAT_AUTOMATOR_PORT=<port>/)
  assert.match(source, /Do not substitute source preview images for runtime screenshots/)
  assert.match(source, /automationEndpointRecovery/)
  assert.match(source, /authorizedEnableAutomationCommand/)
  assert.match(source, /cli auto --project/)
  assert.match(source, /requiresExplicitAuthorization/)
  assert.match(source, /CLI auto can enable automation/)
  assert.match(source, /Rerun devtools-health-check\.js --runtime-probe and require captureSafe=true/)
  assert.match(source, /unapproved cli auto --project or automation-enable loops/)
  assert.match(source, /visibleWindowDiagnostic/)
  assert.match(source, /buildShadowAppIdState/)
  assert.match(source, /Shadow AppID State/)
  assert.match(source, /shadowAppId/)
  assert.match(source, /touristappid evidence is not accepted/)
  assert.match(source, /devtools-window-capture\.js/)
  assert.match(source, /current visible simulator pixels/)
  assert.match(source, /90% strict gate/)
  assert.match(source, /validate-pass36-final-acceptance\.js passing against real runtime evidence/)
  assert.match(source, /devtoolsLifecycleTouched: false/)
  assert.match(source, /runtimeScreenshot: false/)
  assert.match(source, /watchedProjectWrite: false/)
  assert.doesNotMatch(source, /execFile/)
  assert.doesNotMatch(source, /spawn/)
  assert.doesNotMatch(source, /auto --project.*exec/)
})

test('pass36 final readiness report includes the latest automation recovery gate', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/create-pass36-final-readiness-report.js', 'utf8')

  assert.match(source, /function latestAutomationRecoveryState\(artifactDir\)/)
  assert.match(source, /pass36ap-automation-recovery-package\.json/)
  assert.match(source, /latestAutomationRecovery/)
  assert.match(source, /Latest Automation Recovery/)
  assert.match(source, /healthCategory/)
  assert.match(source, /Health category/)
  assert.match(source, /runtimeErrors/)
  assert.match(source, /Port profiles/)
  assert.match(source, /DevTools login-required suppressed by current health/)
  assert.match(source, /noVisibleWindowRisk/)
  assert.match(source, /DevTools window count/)
  assert.match(source, /DevTools window note/)
  assert.match(source, /function latestDevToolsLoginRequiredState\(artifactDir\)/)
  assert.match(source, /pass36aq-devtools-login-required\.json/)
  assert.match(source, /latestDevToolsLoginRequired/)
  assert.match(source, /Latest DevTools Login Required/)
  assert.match(source, /Project open result/)
  assert.match(source, /Login QR path/)
  assert.match(source, /function latestRuntimeShadowGuardState\(artifactDir\)/)
  assert.match(source, /pass36ar-runtime-shadow-hot-sync-guard\.json/)
  assert.match(source, /latestRuntimeShadowGuard/)
  assert.match(source, /Runtime Shadow Sync Guard/)
  assert.match(source, /function latestShadowSyncDryRunState\(artifactDir\)/)
  assert.match(source, /pass36as-shadow-sync-dry-run-preflight\.json/)
  assert.match(source, /latestShadowSyncDryRun/)
  assert.match(source, /Shadow Sync Dry-Run/)
  assert.match(source, /function latestVisibleWindowCaptureState\(artifactDir\)/)
  assert.match(source, /pass36_current_visible-manifest\.json/)
  assert.match(source, /latestVisibleWindowCapture/)
  assert.match(source, /Latest Visible Window Capture/)
  assert.match(source, /viewportNearBlackRatio/)
  assert.match(source, /function latestBrowserSceneMatrixState\(artifactDir\)/)
  assert.match(source, /pass36v-browser-scene-matrix\.json/)
  assert.match(source, /latestBrowserSceneMatrix/)
  assert.match(source, /Browser Scene Matrix Preflight/)
  assert.match(source, /Run pass36v browser scene matrix preflight/)
  assert.match(source, /buildShadowAppIdState/)
  assert.match(source, /shadowAppIdState/)
  assert.match(source, /Shadow AppID State/)
  assert.match(source, /activeShadowAppid/)
  assert.match(source, /touristappid\/no-auth screenshots are not pass36 acceptance evidence/)
  assert.match(source, /function latestAssetSliceWorkflowAuditState\(artifactDir\)/)
  assert.match(source, /pass36x-asset-slice-workflow-audit\.json/)
  assert.match(source, /latestAssetSliceWorkflowAudit/)
  assert.match(source, /Asset Slice Workflow Audit/)
  assert.match(source, /source_contract_passed/)
  assert.match(source, /quarantined high-semantic drafts/)
  assert.match(source, /Run pass36x asset slice workflow audit/)
})

test('pass36 asset slice workflow audit forbids reference-only and baked semantic generated assets', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/audit-pass36-asset-slice-workflow.js', 'utf8')

  assert.match(source, /pass36x-asset-slice-workflow-audit\.json/)
  assert.match(source, /strict-production-manifest\.json/)
  assert.match(source, /target-decomposition\.json/)
  assert.match(source, /referenceOnlyAssets/)
  assert.match(source, /highSemanticGeneratedPatterns/)
  assert.match(source, /verdict_status_badge_blocked_component/)
  assert.match(source, /generated_status_icon_reference/)
  assert.match(source, /full_layout_reference/)
  assert.match(source, /devtoolsTouched: false/)
  assert.match(source, /runtimeScreenshot: false/)
  assert.match(source, /WOW_PASS36_ASSET_AUDIT_OUTPUT_MODE/)
  assert.doesNotMatch(source, /execFile/)
  assert.doesNotMatch(source, /spawn/)
})

test('pass36 shadow appid state detects active touristappid drift after developer authorization', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-shadow-appid-state-'))
  const repoRoot = path.join(root, 'source')
  const shadowRoot = path.join(root, 'shadow')
  const recordPath = path.join(root, 'active-shadow.json')
  const syncScriptPath = path.join(root, 'sync-devtools-shadow.js')
  fs.mkdirSync(repoRoot, { recursive: true })
  fs.mkdirSync(shadowRoot, { recursive: true })
  fs.writeFileSync(path.join(repoRoot, 'project.config.json'), `${JSON.stringify({ appid: 'wx-real-appid' })}\n`)
  fs.writeFileSync(path.join(shadowRoot, 'project.config.json'), `${JSON.stringify({ appid: 'touristappid' })}\n`)
  fs.writeFileSync(recordPath, `${JSON.stringify({ shadowRoot })}\n`)
  fs.writeFileSync(syncScriptPath, "const useNoAuthShadowAppId = process.env.WOW_DEVTOOLS_SHADOW_NO_AUTH === '1'\n")

  const state = buildShadowAppIdState({
    repoRoot,
    syncScriptPath,
    env: {
      WOW_DEVTOOLS_ACTIVE_SHADOW_RECORD: recordPath,
      WOW_DEVTOOLS_SHADOW_ROOT: shadowRoot
    }
  })

  assert.equal(state.status, 'active_shadow_appid_drift')
  assert.equal(state.sourceAppid, 'wx-real-appid')
  assert.equal(state.activeShadowAppid, 'touristappid')
  assert.equal(state.activeShadowDrift, true)
  assert.equal(state.noAuthRequiresExplicitEnv, true)
  assert.ok(
    state.driftCandidates.some((candidate) => (
      candidate.shadowRoot === shadowRoot && candidate.appid === 'touristappid'
    ))
  )
})

test('strict screenshot and rect gates auto-detect existing DevTools automator port', () => {
  const scripts = [
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js',
    'artifacts/ui-v2-1-strict-restoration/rect-layout-gate.js'
  ]

  for (const scriptPath of scripts) {
    const source = fs.readFileSync(scriptPath, 'utf8')
    assert.match(source, /function inspectListeningTcpPorts\(\)/, scriptPath)
    assert.match(source, /function websocketProbeHint\(port\)/, scriptPath)
    assert.match(source, /function candidateAutomatorPorts\(listeningTcpPorts\)/, scriptPath)
    assert.match(source, /auto-detected-existing-devtools/, scriptPath)
    assert.match(source, /connectionAttempts/, scriptPath)
    assert.match(source, /WECHAT_AUTOMATOR_PORT/, scriptPath)
    assert.match(source, /hasRuntimeSdk/, scriptPath)
    assert.match(source, /fallbackConnection/, scriptPath)
    assert.match(source, /!explicitAutomatorPort && !connection\.hasRuntimeSdk/, scriptPath)
    assert.match(source, /record\.port >= 9000/, scriptPath)
    assert.doesNotMatch(
      source,
      /connectExisting\(autoPort\)/,
      `${scriptPath} should not connect only to the default 9854 port`
    )
  }
})

test('DevTools automator gates disconnect after probing existing simulator', () => {
  const scripts = [
    'artifacts/ui-v2-1-strict-restoration/devtools-health-check.js',
    'artifacts/ui-v2-1-strict-restoration/rect-layout-gate.js',
    'artifacts/miniprogram-screenshots/20260702-ui-v2-1-strict-gate/capture-pass6.js'
  ]

  for (const scriptPath of scripts) {
    const source = fs.readFileSync(scriptPath, 'utf8')
    assert.match(source, /disconnect\(/, `${scriptPath} should release the existing DevTools automator connection`)
  }
})

test('rect layout gate can derive viewport width when system info stalls', () => {
  const source = fs.readFileSync('artifacts/ui-v2-1-strict-restoration/rect-layout-gate.js', 'utf8')

  assert.match(source, /function systemInfoOrNull\(miniProgram, warnings\)/)
  assert.match(source, /system info unavailable/)
  assert.match(source, /function deriveSceneInfo\(baseInfo, scene, rects, warnings\)/)
  assert.match(source, /derived windowWidth=/)
  assert.match(source, /derivedFromSelector/)
  assert.match(source, /cannot compare without windowWidth/)
})

test('roadmap marks first-version deferred surfaces as pending planning', () => {
  const roadmap = fs.readFileSync('docs/roadmap.md', 'utf8')

  assert.match(roadmap, /\| 职业专精 \| [^\n|]*热门专精\/属性权重\/输出循环待规划/)
  assert.match(roadmap, /职业专精 tab 开放“天赋构筑”“装备模拟”“模拟 SimC”“任务列表”四个入口/)
  assert.match(roadmap, /\| PVE 专区 \| 待规划 \|/)
  assert.match(roadmap, /\| 智能分析 \/ SimC \| [^\n|]*首版只保留炸鸡队长/)
  assert.match(roadmap, /\| 智能分析 \/ SimC \| [^\n|]*SimC 与任务列表迁入职业专精/)
  assert.match(roadmap, /\| 智能分析 \/ SimC \| [^\n|]*WCL 待规划/)
  assert.match(roadmap, /\| 待规划 \| PVE 职业天梯移动端排行 \|/)
  assert.match(roadmap, /\| 待规划 \| WCL \/ 日志复盘链路 \|/)
})

const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const root = path.resolve(__dirname, '..')
const requirementPath = 'artifacts/releases/2026-07-24-taro-gear-editor-recovery/requirement.json'

function runRequirementCheck(checkRoot, relativePath) {
  return spawnSync(process.execPath, [
    path.join(root, 'scripts/project-harness.js'),
    '--root',
    checkRoot,
    '--json',
    '--check-requirement',
    '--requirement-file',
    relativePath,
  ], { encoding: 'utf8' })
}

test('the Task 1 Standard requirement passes the Harness requirement validator directly', () => {
  const result = runRequirementCheck(root, requirementPath)

  assert.equal(result.status, 0, result.stderr || result.stdout)
  const output = JSON.parse(result.stdout)
  assert.equal(output.status, 'project_harness_requirement_check_passed')
  assert.deepEqual(output.reasonCodes, [])
})

test('the direct Harness requirement check rejects an incomplete Standard packet', () => {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-requirement-check-'))
  const fixturePath = 'artifacts/releases/fixture/requirement.json'
  const requirement = JSON.parse(fs.readFileSync(path.join(root, requirementPath), 'utf8'))
  delete requirement.ownership
  fs.mkdirSync(path.dirname(path.join(fixtureRoot, fixturePath)), { recursive: true })
  fs.writeFileSync(path.join(fixtureRoot, fixturePath), `${JSON.stringify(requirement, null, 2)}\n`)

  const result = runRequirementCheck(fixtureRoot, fixturePath)

  assert.equal(result.status, 1)
  const output = JSON.parse(result.stdout)
  assert.equal(output.status, 'project_harness_requirement_check_failed')
  assert.ok(output.reasonCodes.includes('requirement_missing_ownership'))
})

test('the core interaction contract has one executable candidate apply flow per target route', () => {
  const contract = require('../docs/design/current-ui/core-interaction-contract.json')
  const routeIds = contract.interactions.map((interaction) => interaction.route)
  const gearInteractions = contract.interactions.filter((interaction) => interaction.route === 'gear_detail')
  const executor = fs.readFileSync(path.join(root, 'scripts/verify-ui-interactions.js'), 'utf8')
  const automator = fs.readFileSync(path.join(root, 'scripts/wechat-automator.js'), 'utf8')

  assert.equal(new Set(routeIds).size, routeIds.length)
  assert.equal(gearInteractions.length, 1)
  assert.equal(gearInteractions[0].selectorValue, 'gear-candidate-apply')
  assert.match(executor, /runGearDetailCandidateApplyFlow/u)
  assert.match(executor, /gear-candidate-row/u)
  assert.match(executor, /gear-candidate-variant/u)
  assert.match(executor, /if \(variants\.length > 0\)/u)
  assert.match(executor, /queryElementsWithXpathFallback/u)
  assert.match(executor, /gearCandidateVariantXpath/u)
  assert.match(automator, /getElementByXpath/u)
  assert.match(executor, /committed-item-id/u)
  assert.match(executor, /candidate-item-id/u)
  assert.match(executor, /candidate-draft-variant-key/u)
  assert.match(executor, /resolved-slot-item-id/u)
  assert.match(executor, /resolved-slot-variant-key/u)
  assert.match(executor, /committed-slot-variant-key/u)
  assert.match(executor, /gear-resolve-state-resolving/u)
  assert.match(executor, /gearApplyEvidenceMatches/u)
  assert.match(executor, /readSemanticValue/u)
  assert.doesNotMatch(executor, /attribute\('data-candidate-item-id'\)/u)
  assert.doesNotMatch(executor, /attribute\('data-candidate-draft-variant-key'\)/u)
  assert.match(executor, /committed id changed before apply/u)
  assert.match(executor, /verified resolve did not commit selected candidate/u)
  assert.doesNotMatch(executor, /waitForElementMissing\(page, applySelector\)/u)
})

test('the real gear interaction waits for route readiness before opening a slot', () => {
  const executor = fs.readFileSync(path.join(root, 'scripts/verify-ui-interactions.js'), 'utf8')
  const flowStart = executor.indexOf('async function runGearDetailCandidateApplyFlow')
  const readinessWait = executor.indexOf('await requiredRouteReady(page)', flowStart)
  const slotLookup = executor.indexOf("const mainHandSelector = '.wx-data-role-gear-slot-row", flowStart)

  assert.ok(flowStart >= 0)
  assert.ok(readinessWait > flowStart)
  assert.ok(slotLookup > readinessWait)
  assert.match(executor, /\.wx-data-route-state-ready/u)
})

test('gear apply evidence accepts verified or slot-resolved completion but rejects stale and error states', () => {
  const { gearApplyEvidenceMatches } = require('../scripts/gear-apply-evidence.js')
  const evidence = {
    candidateItemId: 'candidate-main-hand',
    candidateVariantKey: 'candidate-myth-289',
    committedBefore: 'old-main-hand',
    committedVariantBefore: 'old-hero-285',
    resolvedBefore: 'old-main-hand',
    resolvedVariantBefore: 'old-hero-285',
    committedAfter: 'candidate-main-hand',
    committedVariantAfter: 'candidate-myth-289',
    resolvedAfter: 'candidate-main-hand',
    resolvedVariantAfter: 'candidate-myth-289',
    resolveState: 'verified',
  }

  assert.equal(gearApplyEvidenceMatches({ ...evidence, sawResolving: false }), false)
  assert.equal(gearApplyEvidenceMatches({ ...evidence, sawResolving: true }), true)
  assert.equal(gearApplyEvidenceMatches({
    ...evidence,
    sawResolving: true,
    resolveState: 'idle',
  }), true)
  assert.equal(gearApplyEvidenceMatches({
    ...evidence,
    sawResolving: true,
    resolveState: 'error',
  }), false)
  assert.equal(gearApplyEvidenceMatches({
    ...evidence,
    sawResolving: true,
    resolvedAfter: 'old-main-hand',
  }), false)
  assert.equal(gearApplyEvidenceMatches({
    ...evidence,
    sawResolving: true,
    resolvedVariantAfter: 'candidate-hero-285',
  }), false)
})

test('the active page keeps draft item ids out of committed slot markers', () => {
  const page = fs.readFileSync(path.join(root, 'apps/mini-taro/src/pages/builds/detail.tsx'), 'utf8')
  const commitModel = fs.readFileSync(path.join(root, 'apps/mini-taro/src/pages/builds/gear-detail-editor-commit-model.ts'), 'utf8')
  const workbench = fs.readFileSync(path.join(root, 'packages/design-system/src/components/GearDetailComponents.tsx'), 'utf8')
  const editor = fs.readFileSync(path.join(root, 'packages/design-system/src/components/GearEditorSheets.tsx'), 'utf8')

  assert.match(page, /const applyCandidateDraft = async \(\)/u)
  assert.match(page, /transitionGearEditorCommit\(commitState[\s\S]*if \(!transition\.committed\) return[\s\S]*setEquipped\(transition\.state\.equipped\)/u)
  assert.match(page, /hydrateCompactSlotGroup\(group\)/u)
  assert.match(page, /snapshot: resolved\.snapshot/u)
  assert.doesNotMatch(page, /resolved\.snapshot\.selectionIntent \?\? resolved\.intent/u)
  assert.match(commitModel, /if \(event\.status !== 'resolved' && event\.status !== 'slot_resolved'\) \{\s*return \{ state, committed: false, reload: false \}/u)
  assert.match(commitModel, /gearEnhancementsFromResolvedSnapshot/u)
  assert.match(workbench, /data-committed-item-id=\{item\.itemId\}/u)
  assert.match(
    workbench,
    /dataSelectorClass\('has-committed-item', item\.state !== 'empty' && Boolean\(item\.itemId\)\)/u,
  )
  assert.match(workbench, /data-committed-slot-variant-key=\{committedSlotVariantKey\}/u)
  assert.match(workbench, /data-gear-resolve-state=\{resolveState\}/u)
  assert.match(workbench, /data-resolved-slot-item-id=\{resolvedSlotItemId\}/u)
  assert.match(workbench, /data-resolved-slot-variant-key=\{resolvedSlotVariantKey\}/u)
  assert.match(workbench, /data-resolved-slot-crafted-option-id=\{resolvedSlotCraftedOptionId\}/u)
  assert.match(workbench, /data-committed-slot-crafted-option-id=\{committedSlotCraftedOptionId\}/u)
  assert.match(editor, /data-candidate-item-id=\{item\.itemId\}/u)
  assert.match(editor, /data-candidate-draft-variant-key/u)
  assert.match(
    fs.readFileSync(path.join(root, 'scripts/verify-wechat-gear-matrix.js'), 'utf8'),
    /readSemanticValue\(row, 'has-committed-item'\)/u,
  )
})

test('selected-state partitioning validates independent gear enhancement selections', () => {
  const {
    summarizeSelectionPartitions,
  } = require('../scripts/verify-ui-selected-states.js')
  const contract = require('../docs/design/current-ui/selected-control-contract.json')
  const socketGroup = contract.groups.find((group) => group.route === 'gear_detail' && group.role === 'gear-enhancement-socket')
  const enhancementGroup = contract.groups.find((group) => group.route === 'gear_detail' && group.role === 'gear-enhancement-option')
  const audit = fs.readFileSync(path.join(root, 'scripts/audit-ui-architecture.js'), 'utf8')

  assert.equal(socketGroup.groupByAttribute, 'data-socket-index')
  assert.equal(enhancementGroup.groupByAttribute, 'data-enhancement-kind')
  assert.match(audit, /GearEditorSheets\.tsx', 'gear-enhancement-socket'/u)
  assert.match(audit, /grouped_selected_controls_publish_group_attributes/u)
  assert.deepEqual(
    summarizeSelectionPartitions(
      ['true', 'false', 'true', 'false'],
      ['0', '0', '1', '1'],
      socketGroup.minimumActive,
      socketGroup.maximumActive,
    ),
    [
      { key: '0', controls: 2, active: 1, pass: true },
      { key: '1', controls: 2, active: 1, pass: true },
    ],
  )
  assert.equal(
    summarizeSelectionPartitions(
      ['true', 'false', 'true', 'false'],
      ['0', '0', '0', '0'],
      socketGroup.minimumActive,
      socketGroup.maximumActive,
    )[0].pass,
    false,
  )
  assert.equal(
    summarizeSelectionPartitions(
      ['true'],
      [null],
      socketGroup.minimumActive,
      socketGroup.maximumActive,
    )[0].pass,
    false,
  )
  assert.deepEqual(
    summarizeSelectionPartitions(
      ['true', 'false', 'true', 'false'],
      ['enchant', 'enchant', 'embellishment', 'embellishment'],
      enhancementGroup.minimumActive,
      enhancementGroup.maximumActive,
    ),
    [
      { key: 'enchant', controls: 2, active: 1, pass: true },
      { key: 'embellishment', controls: 2, active: 1, pass: true },
    ],
  )
})

test('the UI architecture dry run accepts the Task 3 editor source markers', () => {
  const result = spawnSync(process.execPath, ['scripts/audit-ui-architecture.js'], {
    cwd: root,
    encoding: 'utf8',
  })

  assert.equal(result.status, 0, result.stderr || result.stdout)
  assert.equal(result.stderr, '')
  const output = JSON.parse(result.stdout)
  assert.equal(output.status, 'pass')
  assert.equal(output.findingCount, 0)
  assert.deepEqual(output.findings, [])
})

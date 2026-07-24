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

  assert.equal(new Set(routeIds).size, routeIds.length)
  assert.equal(gearInteractions.length, 1)
  assert.equal(gearInteractions[0].selectorValue, 'gear-candidate-apply')
  assert.match(executor, /runGearDetailCandidateApplyFlow/u)
  assert.match(executor, /gear-candidate-row/u)
  assert.match(executor, /gear-candidate-variant/u)
  assert.match(executor, /data-committed-item-id/u)
  assert.match(executor, /data-candidate-item-id/u)
  assert.match(executor, /gear-resolve-state-verified/u)
  assert.match(executor, /committed id changed before apply/u)
  assert.match(executor, /verified resolve did not commit selected candidate/u)
  assert.doesNotMatch(executor, /waitForElementMissing\(page, applySelector\)/u)
})

test('the active page keeps draft item ids out of committed slot markers', () => {
  const page = fs.readFileSync(path.join(root, 'apps/mini-taro/src/pages/builds/detail.tsx'), 'utf8')
  const workbench = fs.readFileSync(path.join(root, 'packages/design-system/src/components/GearDetailComponents.tsx'), 'utf8')
  const editor = fs.readFileSync(path.join(root, 'packages/design-system/src/components/GearEditorSheets.tsx'), 'utf8')

  assert.match(page, /const applyCandidateDraft = async \(\)/u)
  assert.match(page, /if \(resolved\.status !== 'resolved'\) return[\s\S]*setEquipped\(nextEquipped\)/u)
  assert.match(workbench, /data-committed-item-id=\{item\.itemId\}/u)
  assert.match(workbench, /data-gear-resolve-state=\{resolveState\}/u)
  assert.match(editor, /data-candidate-item-id=\{item\.itemId\}/u)
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

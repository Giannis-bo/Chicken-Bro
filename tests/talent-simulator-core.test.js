const test = require('node:test')
const assert = require('node:assert/strict')

const core = require('../pages/builds/talent-simulator-core')

function sampleNodes() {
  return [
    { id: 'granted', name: 'Granted Root', tree: 'class', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true },
    { id: 'granted-plus', name: 'Granted Plus', tree: 'class', treeType: 'class', row: 1, col: 2, maxRank: 2, grantedRank: 1 },
    { id: 'parent', name: 'Parent Talent', tree: 'class', treeType: 'class', row: 2, col: 1, maxRank: 1 },
    { id: 'child', name: 'Child Talent', tree: 'class', treeType: 'class', row: 3, col: 1, maxRank: 1, parentIds: ['parent'] },
    { id: 'parent-left', name: 'Left Path', tree: 'class', treeType: 'class', row: 2, col: 3, maxRank: 1 },
    { id: 'parent-right', name: 'Right Path', tree: 'class', treeType: 'class', row: 2, col: 5, maxRank: 1 },
    { id: 'branch-child', name: 'Branch Child', tree: 'class', treeType: 'class', row: 3, col: 4, maxRank: 1, parentIds: ['parent-left', 'parent-right'] },
    { id: 'all-child', name: 'All Parents Child', tree: 'class', treeType: 'class', row: 4, col: 4, maxRank: 1, parentIds: ['parent-left', 'parent-right'], parentMode: 'all' },
    { id: 'gate', name: 'Gate Talent', tree: 'class', treeType: 'class', row: 4, col: 1, maxRank: 1, requiredPoints: 3 },
    { id: 'choice-a', name: 'Choice A', tree: 'spec', treeType: 'spec', row: 1, col: 1, maxRank: 1, choiceGroup: 'choice-1' },
    { id: 'choice-b', name: 'Choice B', tree: 'spec', treeType: 'spec', row: 1, col: 2, maxRank: 1, choiceGroup: 'choice-1' },
    { id: 'hero-rank', name: 'Hero Rank', tree: 'hero', treeType: 'hero', row: 1, col: 1, maxRank: 2 }
  ]
}

test('talent rank helper grants starter ranks and prevents removing granted nodes', () => {
  const nodes = sampleNodes()
  const rankState = core.initialTalentRanks(nodes)

  assert.equal(rankState.baseTalentRanks.granted, 1)
  assert.equal(rankState.talentRanks.granted, 1)

  const result = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'granted', -1)

  assert.equal(result.changed, false)
  assert.equal(result.reason, 'granted')
  assert.equal(result.talentRanks.granted, 1)

  const upgraded = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'granted-plus', 1)

  assert.equal(upgraded.changed, true)
  assert.equal(upgraded.talentRanks['granted-plus'], 2)
  assert.equal(core.purchasedRankFor('granted-plus', upgraded.talentRanks, nodes, rankState.baseTalentRanks), 1)

  const downgraded = core.adjustTalentRank({
    nodes,
    talentRanks: upgraded.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'granted-plus', -1)
  assert.equal(downgraded.changed, true)
  assert.equal(downgraded.talentRanks['granted-plus'], 1)

  const belowFloor = core.adjustTalentRank({
    nodes,
    talentRanks: downgraded.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'granted-plus', -1)
  assert.equal(belowFloor.changed, false)
  assert.equal(belowFloor.reason, 'granted')
  assert.equal(belowFloor.talentRanks['granted-plus'], 1)
})

test('talent rank helper enforces parents point gates and point caps', () => {
  const nodes = sampleNodes()
  let rankState = core.initialTalentRanks(nodes, { pointCaps: { class: 2 } })

  let result = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    pointCaps: rankState.pointCaps
  }, 'child', 1)
  assert.equal(result.changed, false)
  assert.equal(result.reason, 'missing_parent')

  result = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    pointCaps: rankState.pointCaps
  }, 'parent', 1)
  assert.equal(result.changed, true)
  rankState = { ...rankState, talentRanks: result.talentRanks }

  result = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    pointCaps: rankState.pointCaps
  }, 'gate', 1)
  assert.equal(result.changed, false)
  assert.equal(result.reason, 'point_requirement')

  result = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    pointCaps: rankState.pointCaps
  }, 'child', 1)
  assert.equal(result.changed, true)
  assert.equal(result.talentRanks.child, 1)
})

test('talent dependencies treat multiple parents as any by default and support explicit all mode', () => {
  const nodes = sampleNodes()
  let rankState = core.initialTalentRanks(nodes)

  const left = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'parent-left', 1)
  assert.equal(left.changed, true)
  rankState = { ...rankState, talentRanks: left.talentRanks }

  const anyChild = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'branch-child', 1)
  assert.equal(anyChild.changed, true)
  assert.equal(anyChild.talentRanks['branch-child'], 1)

  const allChild = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'all-child', 1)
  assert.equal(allChild.changed, false)
  assert.equal(allChild.reason, 'missing_parent')
})

test('talent rank helper keeps choice groups mutually exclusive', () => {
  const nodes = sampleNodes()
  const rankState = core.initialTalentRanks(nodes)

  const first = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'choice-a', 1)
  const second = core.adjustTalentRank({
    nodes,
    talentRanks: first.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'choice-b', 1)

  assert.equal(second.changed, true)
  assert.equal(second.talentRanks['choice-a'] || 0, 0)
  assert.equal(second.talentRanks['choice-b'], 1)
})

test('talent export and import roundtrip preserves selected node ranks', () => {
  const talentRanks = { granted: 1, parent: 1, 'choice-b': 1, 'hero-rank': 2 }
  const code = core.buildTalentExportCode({
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'spellslinger',
    talentRanks
  })

  assert.equal(code, 'websim:mage:frost:spellslinger:choice-b:1,granted:1,hero-rank:2,parent:1')

  const parsed = core.parseTalentExportCode(code)
  assert.equal(parsed.classKey, 'mage')
  assert.equal(parsed.specKey, 'frost')
  assert.equal(parsed.heroKey, 'spellslinger')
  assert.deepEqual(parsed.talentRanks, talentRanks)
})

test('talent view model returns three laid out trees selected nodes and search state', () => {
  const nodes = sampleNodes()
  const rankState = core.initialTalentRanks(nodes)
  const talentRanks = { ...rankState.talentRanks, parent: 1, 'hero-rank': 2 }
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [
      { key: 'class', title: '职业天赋', tree: 'class' },
      { key: 'spec', title: '专精天赋', tree: 'spec' },
      { key: 'hero', title: '英雄天赋', tree: 'hero' }
    ],
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'spellslinger',
    talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    searchTerm: 'Hero'
  })

  assert.deepEqual(viewModel.sections.map((section) => section.key), ['class', 'spec', 'hero'])
  assert.equal(viewModel.sections[0].nodes.find((node) => node.id === 'parent').rank, 1)
  assert.equal(typeof viewModel.sections[0].nodes[0].leftPercent, 'number')
  assert.equal(typeof viewModel.sections[0].nodes[0].topPercent, 'number')
  assert.ok(viewModel.sections[0].links.some((link) => link.from === 'parent' && link.to === 'child'))
  assert.ok(viewModel.selectedNodes.some((node) => node.id === 'hero-rank' && node.rank === 2 && node.tree === 'hero'))
  assert.equal(viewModel.searchMatches.length, 1)
  assert.equal(viewModel.sections.find((section) => section.key === 'class').searchMatchCount, 0)
  assert.equal(viewModel.sections.find((section) => section.key === 'spec').searchMatchCount, 0)
  assert.equal(viewModel.sections.find((section) => section.key === 'hero').searchMatchCount, 1)
  const lockedChild = viewModel.sections[0].nodes.find((node) => node.id === 'branch-child')
  assert.equal(lockedChild.canSelect, false)
  assert.equal(lockedChild.lockReason, 'missing_parent')
  assert.deepEqual(lockedChild.nextUnlockSteps.map((step) => step.targetId), ['parent-left', 'parent-right'])
  assert.equal(viewModel.websimExportCode, 'websim:mage:frost:spellslinger:granted:1,granted-plus:1,hero-rank:2,parent:1')
})

test('community template helpers expose source status and scenario availability', () => {
  const templates = [
    {
      id: 'mplus-mainstream',
      scenarioKey: 'mythic_plus',
      name: '高层大秘 · 主流AOE',
      canApplyVisual: true,
      websimExportCode: 'websim:mage:arcane:spellslinger:granted:1'
    },
    {
      id: 'single-external',
      scenarioKey: 'single',
      name: '单体 · 爆发',
      canApplyVisual: false,
      rawImportCode: 'C4DA'
    }
  ]

  assert.deepEqual(core.templatesForScenario(templates, 'mythic_plus').map((item) => item.id), ['mplus-mainstream'])
  assert.equal(core.communityTemplateApplyMode(templates[0]), 'visual')
  assert.equal(core.communityTemplateApplyMode(templates[1]), 'simc_only')
  assert.match(core.communityTemplateStatusText({
    sourceStatus: 'partial',
    sources: {
      raiderio: { status: 'missing_credentials' },
      warcraftlogs: { status: 'missing_credentials' }
    }
  }), /待补齐 Raider\.IO、Warcraft Logs/)
  assert.match(core.communityTemplateStatusText({ sourceStatus: 'synced' }), /已同步/)
  assert.match(core.communityTemplateStatusText({ sourceStatus: 'missing_credentials' }), /API 凭据/)
})

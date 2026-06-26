const test = require('node:test')
const assert = require('node:assert/strict')

const core = require('../pages/builds/talent-simulator-core')

function distance(left, right) {
  const dx = left.x - right.x
  const dy = left.y - right.y
  return Math.sqrt(dx * dx + dy * dy)
}

function crossProduct(start, end, point) {
  return ((end.x - start.x) * (point.y - start.y)) - ((end.y - start.y) * (point.x - start.x))
}

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

test('hero tree point gates count the granted root talent', () => {
  const nodes = [
    { id: 'hero-root', name: 'Hero Root', tree: 'hero', treeType: 'hero', row: 1, col: 2, maxRank: 1, granted: true },
    { id: 'hero-child', name: 'Hero Child', tree: 'hero', treeType: 'hero', row: 2, col: 1, maxRank: 1, parentIds: ['hero-root'], requiredPoints: 1 }
  ]
  const rankState = core.initialTalentRanks(nodes, { pointCaps: { hero: 13 } })
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'hero', title: 'Hero', tree: 'hero', pointCap: 13 }],
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    pointCaps: rankState.pointCaps
  })
  const child = viewModel.sections[0].nodes.find((node) => node.id === 'hero-child')

  assert.equal(child.canSelect, true)
  assert.equal(child.lockReason, '')

  const selected = core.adjustTalentRank({
    nodes,
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks,
    pointCaps: rankState.pointCaps
  }, 'hero-child', 1)

  assert.equal(selected.changed, true)
  assert.equal(selected.talentRanks['hero-child'], 1)
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

test('talent dependencies require a ranked parent to be filled before unlocking children', () => {
  const nodes = [
    { id: 'root', name: 'Root', tree: 'class', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true },
    { id: 'ranked-parent', name: 'Ranked Parent', tree: 'class', treeType: 'class', row: 2, col: 1, maxRank: 2, parentIds: ['root'] },
    { id: 'branch-child', name: 'Branch Child', tree: 'class', treeType: 'class', row: 3, col: 1, maxRank: 1, parentIds: ['ranked-parent'] }
  ]
  const rankState = core.initialTalentRanks(nodes)
  const onePointRanks = { ...rankState.talentRanks, 'ranked-parent': 1 }
  const onePointView = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: 'Class', tree: 'class' }],
    talentRanks: onePointRanks,
    baseTalentRanks: rankState.baseTalentRanks
  })
  const onePointChild = onePointView.sections[0].nodes.find((node) => node.id === 'branch-child')
  const blocked = core.adjustTalentRank({
    nodes,
    talentRanks: onePointRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'branch-child', 1)

  assert.equal(onePointChild.canSelect, false)
  assert.equal(onePointChild.lockReason, 'missing_parent')
  assert.equal(blocked.changed, false)
  assert.equal(blocked.reason, 'missing_parent')

  const fullParentRanks = { ...rankState.talentRanks, 'ranked-parent': 2 }
  const fullParentView = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: 'Class', tree: 'class' }],
    talentRanks: fullParentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  })
  const fullParentChild = fullParentView.sections[0].nodes.find((node) => node.id === 'branch-child')
  const unlocked = core.adjustTalentRank({
    nodes,
    talentRanks: fullParentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  }, 'branch-child', 1)

  assert.equal(fullParentChild.canSelect, true)
  assert.equal(unlocked.changed, true)
  assert.equal(unlocked.talentRanks['branch-child'], 1)
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

test('talent view model normalizes node shapes for passive active and choice talents', () => {
  const nodes = [
    { id: 'passive', name: 'Passive', tree: 'class', treeType: 'class', row: 1, col: 1, maxRank: 1, shape: 'circle' },
    { id: 'active', name: 'Active', tree: 'class', treeType: 'class', row: 1, col: 2, maxRank: 1, shape: 'square' },
    { id: 'choice-a', name: 'Choice A', tree: 'class', treeType: 'class', row: 2, col: 1, maxRank: 1, shape: 'square', choiceGroup: 'choice-slot' },
    { id: 'payload-passive', name: 'Payload Passive', tree: 'class', treeType: 'class', row: 2, col: 2, maxRank: 1, payload: { shape: 'circle' } }
  ]
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: 'Class', tree: 'class' }]
  })
  const byId = new Map(viewModel.sections[0].nodes.map((node) => [node.id, node]))

  assert.equal(byId.get('passive').shape, 'circle')
  assert.equal(byId.get('active').shape, 'square')
  assert.equal(byId.get('choice-a').shape, 'choice')
  assert.equal(byId.get('choice-a').choice, true)
  assert.equal(byId.get('payload-passive').shape, 'circle')
})

test('talent view model renders selected choice peers and active arrows for shared choice slots', () => {
  const nodes = [
    { id: 'root', name: 'Root', tree: 'class', treeType: 'class', row: 1, col: 1, maxRank: 1, granted: true },
    { id: 'choice-a', name: 'Choice A', tree: 'class', treeType: 'class', row: 2, col: 1, maxRank: 1, parentIds: ['root'], choiceGroup: 'choice-slot' },
    { id: 'choice-b', name: 'Choice B', tree: 'class', treeType: 'class', row: 2, col: 1, maxRank: 1, parentIds: ['root'], choiceGroup: 'choice-slot' },
    { id: 'child', name: 'Child', tree: 'class', treeType: 'class', row: 3, col: 1, maxRank: 1, parentIds: ['choice-b'] }
  ]
  const rankState = core.initialTalentRanks(nodes)
  const talentRanks = { ...rankState.talentRanks, 'choice-b': 1, child: 1 }
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: 'Class', tree: 'class' }],
    talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  })
  const section = viewModel.sections[0]
  const renderedChoiceNodes = section.nodes.filter((node) => node.choiceGroup === 'choice-slot')

  assert.equal(renderedChoiceNodes.length, 1)
  assert.equal(renderedChoiceNodes[0].id, 'choice-b')
  assert.equal(renderedChoiceNodes[0].rank, 1)
  assert.equal(renderedChoiceNodes[0].selected, true)
  assert.equal(section.links.some((link) => link.from === 'root' && link.to === 'choice-a'), false)
  assert.equal(section.links.find((link) => link.from === 'root' && link.to === 'choice-b').active, true)
  assert.equal(section.links.find((link) => link.from === 'choice-b' && link.to === 'child').active, true)
})

test('talent view model offsets arrows around node edges and marks available paths', () => {
  const nodes = [
    { id: 'root', name: 'Root', tree: 'class', treeType: 'class', row: 1, col: 2, maxRank: 1, granted: true },
    { id: 'left', name: 'Left', tree: 'class', treeType: 'class', row: 2, col: 1, maxRank: 1, parentIds: ['root'] },
    { id: 'right', name: 'Right', tree: 'class', treeType: 'class', row: 2, col: 3, maxRank: 1, parentIds: ['root'] }
  ]
  const rankState = core.initialTalentRanks(nodes)
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: 'Class', tree: 'class' }],
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  })
  const section = viewModel.sections[0]
  const leftLink = section.links.find((link) => link.from === 'root' && link.to === 'left')
  const rightLink = section.links.find((link) => link.from === 'root' && link.to === 'right')

  assert.ok(leftLink.x1 < 37.5)
  assert.ok(rightLink.x1 > 37.5)
  assert.ok(leftLink.y1 > 12.5)
  assert.ok(rightLink.y1 > 12.5)
  assert.ok(leftLink.x2 > 12.5)
  assert.ok(rightLink.x2 < 62.5)
  assert.ok(leftLink.y2 < 37.5)
  assert.ok(rightLink.y2 < 37.5)
  assert.equal(leftLink.active, false)
  assert.equal(leftLink.available, true)
  assert.equal(section.nodes.find((node) => node.id === 'left').canSelect, true)
})

test('talent view model keeps arrow extension lines aligned through node centers', () => {
  const nodes = [
    { id: 'root', name: 'Root', tree: 'class', treeType: 'class', row: 1, col: 2, maxRank: 1, granted: true },
    { id: 'vertical', name: 'Vertical', tree: 'class', treeType: 'class', row: 2, col: 2, maxRank: 1, parentIds: ['root'] },
    { id: 'diagonal', name: 'Diagonal', tree: 'class', treeType: 'class', row: 2, col: 3, maxRank: 1, parentIds: ['root'] }
  ]
  const rankState = core.initialTalentRanks(nodes)
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: 'Class', tree: 'class' }],
    talentRanks: rankState.talentRanks,
    baseTalentRanks: rankState.baseTalentRanks
  })
  const section = viewModel.sections[0]
  const root = section.nodes.find((node) => node.id === 'root')
  const vertical = section.nodes.find((node) => node.id === 'vertical')
  const diagonal = section.nodes.find((node) => node.id === 'diagonal')

  ;[
    { link: section.links.find((item) => item.to === 'vertical'), child: vertical },
    { link: section.links.find((item) => item.to === 'diagonal'), child: diagonal }
  ].forEach(({ link, child }) => {
    const parentCenter = { x: root.leftRpx, y: root.topRpx }
    const childCenter = { x: child.leftRpx, y: child.topRpx }
    const start = { x: link.x1Rpx, y: link.y1Rpx }
    const end = { x: link.x2Rpx, y: link.y2Rpx }

    assert.ok(Math.abs(crossProduct(parentCenter, childCenter, start)) < 0.000001)
    assert.ok(Math.abs(crossProduct(parentCenter, childCenter, end)) < 0.000001)
    assert.ok(Math.abs(distance(parentCenter, start) - core.LINK_NODE_START_CLEARANCE_RPX) < 0.000001)
    assert.ok(Math.abs(distance(childCenter, end) - core.LINK_NODE_END_CLEARANCE_RPX) < 0.000001)
    assert.equal(Math.round(link.lengthRpx), Math.round(distance(start, end)))
  })
})

test('talent view model provides unique render keys for duplicate node ids', () => {
  const nodes = [
    { id: 'duplicate', name: 'Duplicate A', tree: 'class', treeType: 'class', row: 1, col: 1 },
    { id: 'duplicate', name: 'Duplicate B', tree: 'class', treeType: 'class', row: 2, col: 1, parentIds: ['duplicate'] }
  ]
  const viewModel = core.buildTalentViewModel({
    nodes,
    treeSections: [{ key: 'class', title: '职业天赋', tree: 'class' }]
  })
  const renderKeys = viewModel.sections[0].nodes.map((node) => node.renderKey)

  assert.equal(new Set(renderKeys).size, renderKeys.length)
  assert.equal(viewModel.sections[0].nodes[0].id, 'duplicate')
  assert.ok(viewModel.sections[0].links.every((link) => link.renderKey))
})

test('community template helpers expose source status and spec-scoped availability', () => {
  const templates = [
    {
      id: 'arcane-low',
      classKey: 'mage',
      specKey: 'arcane',
      heroKey: 'spellslinger',
      scenarioKey: 'mythic_plus',
      name: 'Same Arcane Player',
      canApplyVisual: true,
      websimExportCode: 'websim:mage:arcane:spellslinger:granted:1',
      playerId: 'ArcanePlayer',
      sampleCount: 2,
      maxKeyLevel: 20
    },
    {
      id: 'arcane-high',
      classKey: 'mage',
      specKey: 'arcane',
      heroKey: 'spellslinger',
      scenarioKey: 'mythic_plus',
      name: 'Same Arcane Player',
      canApplyVisual: true,
      websimExportCode: 'websim:mage:arcane:spellslinger:other:1',
      playerId: 'ArcanePlayer',
      sampleCount: 7,
      maxKeyLevel: 23
    },
    {
      id: 'arcane-other-a',
      classKey: 'mage',
      specKey: 'arcane',
      heroKey: 'sunfury',
      scenarioKey: 'single',
      name: '单体 · 爆发',
      canApplyVisual: false,
      rawImportCode: 'C4DA',
      sampleCount: 3,
      maxKeyLevel: 21
    },
    {
      id: 'arcane-other-b',
      classKey: 'mage',
      specKey: 'arcane',
      heroKey: 'spellslinger',
      scenarioKey: 'mythic_plus',
      name: 'Arcane B',
      canApplyVisual: true,
      websimExportCode: 'websim:mage:arcane:spellslinger:b:1',
      sampleCount: 2,
      maxKeyLevel: 20
    },
    {
      id: 'arcane-third',
      classKey: 'mage',
      specKey: 'arcane',
      heroKey: 'spellslinger',
      scenarioKey: 'mythic_plus',
      name: 'Arcane C',
      canApplyVisual: true,
      websimExportCode: 'websim:mage:arcane:spellslinger:c:1',
      sampleCount: 1,
      maxKeyLevel: 19
    },
    {
      id: 'frost-cross-spec',
      classKey: 'mage',
      specKey: 'frost',
      heroKey: 'spellslinger',
      scenarioKey: 'mythic_plus',
      name: 'Frost M+',
      canApplyVisual: true,
      websimExportCode: 'websim:mage:frost:spellslinger:frost:1',
      sampleCount: 99,
      maxKeyLevel: 30
    },
    {
      id: 'warrior-mplus',
      classKey: 'warrior',
      specKey: 'protection',
      scenarioKey: 'mythic_plus',
      name: 'Warrior M+',
      canApplyVisual: true,
      websimExportCode: 'websim:warrior:protection:mountain_thane:root:1'
    }
  ]

  assert.deepEqual(core.templatesForClass(templates, 'mage', 'arcane').map((item) => item.id), ['arcane-high', 'arcane-other-b', 'arcane-third'])
  assert.equal(core.communityTemplateApplyMode(templates[0]), 'visual')
  assert.equal(core.communityTemplateApplyMode(templates[2]), 'simc_only')
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

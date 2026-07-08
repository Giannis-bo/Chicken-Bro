const test = require('node:test')
const assert = require('node:assert/strict')

const { buildWorkbenchState } = require('../pages/builds/workbench-state')

const selectedSpec = {
  id: '法师-冰霜',
  className: '法师',
  specName: '冰霜',
  websimClassKey: 'mage',
  websimSpecKey: 'frost'
}

function talentPayload(overrides = {}) {
  return {
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'spellslinger',
    treeSections: [{ key: 'hero', title: '法术投射者' }],
    nodes: [{
      id: 'simc-spec-80241-mage-frost',
      name: '冰枪术',
      gameAsset: {
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/spell_frost_frostblast.jpg',
        fallbackText: '冰'
      }
    }],
    talentStatus: 'simc',
    dataStatus: 'verified',
    talentAuthority: { checkedAt: '2026-06-29T03:14:49+00:00' },
    talentReadiness: {
      treeReady: true,
      ruleReady: true,
      spellReady: true,
      encodingReady: true,
      simcReady: true,
      spellCoverage: { covered: 1, total: 1 },
      blockers: []
    },
    ...overrides
  }
}

function gearPayload(overrides = {}) {
  return {
    classKey: 'mage',
    specKey: 'frost',
    dataStatus: 'verified',
    catalogStatus: 'verified',
    checkedAt: '2026-06-29T16:40:25+00:00',
    catalogCheckedAt: '2026-06-29T15:26:29+00:00',
    slots: [{ slot: 'off_hand', label: '副手' }],
    equippedSet: {
      head: {
        slot: 'head',
        displayName: '虚空粉碎者的面纱',
        gameAsset: {
          iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helm_cloth_raidmagemidnight_d_01.jpg',
          fallbackText: '头'
        }
      }
    },
    readiness: {
      simcReadyCount: 16,
      selectedCount: 16,
      requiredReadyCount: 16,
      fullReady: true,
      missingRequiredSlots: [],
      itemLevel: { value: '291' },
      warnings: []
    },
    statSnapshot: {
      statStatus: 'verified',
      blockers: [],
      checkedAt: '2026-06-29T16:40:25+00:00'
    },
    catalogBlockers: [],
    ...overrides
  }
}

function stateFor(overrides = {}) {
  return buildWorkbenchState({
    selectedSpec,
    scenarioKey: 'single',
    talentsPayload: talentPayload(),
    gearPayload: gearPayload(),
    talentTemplates: [],
    gearTemplates: [],
    now: new Date('2026-06-30T00:00:00+08:00'),
    ...overrides
  })
}

test('ready_to_simulate requires executable talents and complete gear without exposing strong result', () => {
  const state = stateFor()

  assert.equal(state.state, 'ready_to_simulate')
  assert.equal(state.specIconUrl, 'https://render.worldofwarcraft.com/us/icons/56/spell_frost_frostbolt02.jpg')
  assert.equal(state.primaryAction.key, 'simc')
  assert.equal(state.primaryBlockerLabel, '检查项')
  assert.equal(state.primaryBlockerTitle, '输入完整')
  assert.equal(state.canShowStrongResult, false)
  assert.equal(state.moduleCards.find((item) => item.key === 'simc').status, 'ready_to_simulate')
  assert.equal(state.moduleCards.find((item) => item.key === 'simc').dockDesc, '进入现有 SimC')
  assert.equal(state.moduleCards.find((item) => item.key === 'simc').iconFallback, 'Sim')
  assert.deepEqual(
    state.evidencePreviewRows.map((item) => item.label),
    ['天赋构筑参考', '装备配置参考', '模拟设定说明', '队长条件说明']
  )
  assert.equal(state.evidencePreviewRows.find((item) => item.label === '队长条件说明').value, '解释阻断与来源，不替代结论')
})

test('blocked state prioritizes concrete gear blockers', () => {
  const state = stateFor({
    gearPayload: gearPayload({
      dataStatus: 'blocked',
      catalogStatus: 'partial',
      readiness: {
        simcReadyCount: 15,
        selectedCount: 15,
        requiredReadyCount: 15,
        fullReady: true,
        missingRequiredSlots: ['off_hand'],
        itemLevel: { value: '291' }
      },
      statSnapshot: {
        statStatus: 'blocked',
        blockers: ['Select complete SimC-ready gear and talents to calculate a verified stat snapshot.']
      }
    })
  })

  assert.equal(state.state, 'blocked')
  assert.equal(state.summary, '缺少核心装备，无法生成有效模拟结果。补齐后即可校验。')
  assert.equal(state.primaryAction.key, 'gear')
  assert.match(state.blockers[0].title, /缺少副手/)
  assert.deepEqual(state.secondaryBlockers, [])
  assert.equal(state.moduleCards.find((item) => item.key === 'gear').metric, '15/16 槽')
  assert.equal(state.moduleCards.find((item) => item.key === 'gear').dockDesc, '缺 1 项装备')
  assert.equal(state.evidenceRows.find((item) => item.label === '装备槽位').value, '15/16 槽')
})

test('blocked gear summary keeps long missing slot lists out of the first screen', () => {
  const state = stateFor({
    gearPayload: gearPayload({
      dataStatus: 'blocked',
      catalogStatus: 'partial',
      readiness: {
        simcReadyCount: 4,
        selectedCount: 4,
        requiredReadyCount: 4,
        fullReady: false,
        missingRequiredSlots: ['head', 'neck', 'shoulder', 'back', 'chest', 'wrist'],
        itemLevel: { value: '291' }
      }
    })
  })

  assert.equal(state.primaryBlockerTitle, '缺少 6 个装备槽')
  assert.equal(state.primaryBlockerDesc, '缺口：头部、颈部、肩部等 6 项')
  assert.equal(state.evidenceRows.find((item) => item.label === '缺口').value, '头部、颈部、肩部等 6 项')
})

test('gear slot metric caps backend candidate counts to the 16 equipped slots', () => {
  const state = stateFor({
    gearPayload: gearPayload({
      dataStatus: 'blocked',
      catalogStatus: 'partial',
      readiness: {
        simcReadyCount: 432,
        selectedCount: 432,
        requiredReadyCount: 448,
        fullReady: false,
        missingRequiredSlots: [
          'head',
          'neck',
          'shoulder',
          'back',
          'chest',
          'wrist',
          'hands',
          'waist',
          'legs',
          'feet',
          'finger1',
          'finger2',
          'trinket1',
          'trinket2',
          'main_hand',
          'off_hand'
        ]
      }
    })
  })

  assert.equal(state.moduleCards.find((item) => item.key === 'gear').metric, '0/16 槽')
  assert.equal(state.evidenceRows.find((item) => item.label === '装备槽位').value, '0/16 槽')
  assert.equal(state.evidencePreviewRows.find((item) => item.label === '装备配置参考').value, '缺少 16 个装备槽')
})

test('partial state keeps scan-friendly module evidence without inventing a result', () => {
  const state = stateFor({
    gearPayload: gearPayload({
      catalogStatus: 'partial',
      readiness: {
        simcReadyCount: 10,
        selectedCount: 10,
        requiredReadyCount: 16,
        fullReady: false,
        missingRequiredSlots: [],
        itemLevel: { value: '280' }
      },
      catalogBlockers: ['active season dungeon list is missing']
    })
  })

  assert.equal(state.state, 'partial')
  assert.equal(state.primaryAction.key, 'evidence')
  assert.equal(state.moduleCards.find((item) => item.key === 'gear').status, 'partial')
  assert.match(state.moduleCards.find((item) => item.key === 'chickenbro').dockDesc, /解释阻断和来源/)
  assert.equal(state.canShowStrongResult, false)
})

test('stale state is used when otherwise usable evidence is older than the freshness window', () => {
  const state = stateFor({
    gearPayload: gearPayload({
      checkedAt: '2026-05-01T00:00:00+00:00',
      catalogCheckedAt: '2026-05-01T00:00:00+00:00'
    })
  })

  assert.equal(state.state, 'stale')
  assert.equal(state.primaryAction.key, 'evidence')
})

test('source_reference state does not turn missing evidence into a fake error', () => {
  const state = buildWorkbenchState({
    selectedSpec,
    scenarioKey: 'single',
    now: new Date('2026-06-30T00:00:00+08:00')
  })

  assert.equal(state.state, 'source_reference')
  assert.equal(state.primaryAction.key, 'evidence')
  assert.equal(state.moduleCards.find((item) => item.key === 'simc').status, 'source_reference')
  assert.equal(state.moduleCards.find((item) => item.key === 'simc').iconFallback, 'Sim')
})

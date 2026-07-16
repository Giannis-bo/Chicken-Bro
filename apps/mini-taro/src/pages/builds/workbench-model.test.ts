import { describe, expect, it } from 'vitest'

import type { BuildsHomePayload, WebsimGearPayload, WebsimTalentsPayload } from '@wow-mini/domain'

import { buildCurrentSpecWorkbenchModel, type CurrentSpecWorkbenchPayload } from './workbench-model'

function home(): BuildsHomePayload {
  return {
    navTitle: '职业专精', kicker: '构筑准备', title: '职业专精', desc: '真实目录', dataStatus: 'verified',
    quickActions: [], featuredSpecializations: [], trustedSources: [], sourceRefs: [],
    currentSeason: { dataStatus: 'verified' },
    raiderio: { sourceName: 'Raider.IO', sourceStatus: 'blocked', sampleCount: 0, maxKeyLevel: 0, bestScore: 0 },
    classOptions: [{
      name: '法师', websimClassKey: 'mage', specializations: [{
        id: '法师-冰霜', name: '冰霜', title: '冰霜法师', className: '法师', specName: '冰霜',
        websimClassKey: 'mage', websimSpecKey: 'frost', sourceName: 'Battle.net', sourceUrl: 'https://example.test/spec',
        specIconUrl: 'https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg',
      }],
    }],
  }
}

function talents(): WebsimTalentsPayload {
  return {
    classKey: 'mage', specKey: 'frost', nodes: Array.from({ length: 111 }, (_, index) => ({ id: String(index), name: `节点${index}` })),
    treeSections: [], presets: [], communityTemplates: [], talentStatus: 'simc', errors: [],
    talentReadiness: { simcReady: true, blockers: ['55 个节点描述公式待核验'] },
    blockers: ['55 个节点描述公式待核验'],
  }
}

function gear(fullReady = false): WebsimGearPayload {
  const slotReadiness = Object.fromEntries(Array.from({ length: 16 }, (_, index) => [`slot-${index}`, {
    slot: `slot-${index}`, label: `槽位${index}`, status: index < 14 ? 'verified' : 'blocked', simcReady: index < 14,
  }]))
  return {
    classKey: 'mage', specKey: 'frost', slots: [], slotGroups: [], equippedSet: {}, replacementCandidates: [], communityTemplates: [],
    slotReadiness,
    readiness: {
      fullReady, simcReadyCount: 14, selectedCount: 361, candidateCount: 257, requiredReadyCount: 15,
      missingRequiredSlots: fullReady ? [] : ['finger2', 'trinket2'], missingCoreSlots: fullReady ? [] : ['finger2', 'trinket2'], warnings: [],
    },
    statSnapshot: {
      classKey: 'mage', specKey: 'frost', statStatus: 'blocked', blockers: [], primary: null, stamina: null, secondary: [], armor: null,
      weaponDps: null, itemLevel: { key: 'itemLevel', label: '装备等级', value: '0' },
    },
    catalogStatus: 'verified', catalogBlockers: [], dataStatus: 'verified',
  }
}

function payload(overrides: Partial<CurrentSpecWorkbenchPayload> = {}): CurrentSpecWorkbenchPayload {
  const ok = { fromFallback: false, error: '' }
  return {
    home: home(), talents: talents(), gear: gear(), talentTemplates: [], gearTemplates: [],
    sources: { home: ok, talents: ok, gear: ok, talentTemplates: ok, gearTemplates: ok },
    ...overrides,
  }
}

describe('current spec workbench truth model', () => {
  it('uses slot readiness instead of presenting candidate counts as equipped slots', () => {
    const model = buildCurrentSpecWorkbenchModel({ payload: payload(), routeState: 'ready', selectedSpecId: '法师-冰霜' })
    const gearModule = model.modules.find((module) => module.id === 'gear')

    expect(gearModule?.summary).toBe('14/15 必需槽可模拟')
    expect(JSON.stringify(model)).not.toContain('361')
    expect(JSON.stringify(model)).not.toContain('257')
  })

  it('keeps the four target module titles and compact truthful revisions', () => {
    const current = payload({
      talents: { ...talents(), talentSchemaRevision: 'websim-talent-rules-v1' },
      gear: { ...gear(), gearSchemaRevision: 'websim-gear-simulator-v1' },
    })
    const model = buildCurrentSpecWorkbenchModel({ payload: current, routeState: 'ready' })

    expect(model.modules.map((module) => module.title)).toEqual(['天赋', '装备', 'SimC', '队长'])
    expect(model.evidence.find((row) => row.id === 'talents')?.revisionLabel).toBe('天赋 v1')
    expect(model.evidence.find((row) => row.id === 'gear')?.revisionLabel).toBe('装备 v1')
  })

  it('keeps the selected specialization icon in the source-referenced identity', () => {
    const model = buildCurrentSpecWorkbenchModel({ payload: payload(), routeState: 'ready', selectedSpecId: '法师-冰霜' })

    expect(model.identity).toMatchObject({
      verified: true,
      iconUrl: 'https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg',
      trust: { level: 'source_referenced' },
    })
  })

  it('keeps talent description gaps separate from SimC encoding readiness', () => {
    const model = buildCurrentSpecWorkbenchModel({ payload: payload({ gear: gear(true) }), routeState: 'ready' })

    expect(model.modules.find((module) => module.id === 'talents')?.state).toBe('partial')
    expect(model.modules.find((module) => module.id === 'simc')?.state).toBe('ready')
    expect(model.overallState).toBe('ready')
  })

  it('keeps authenticated template fallback in the hero context without replacing ledger rows', () => {
    const blocked = { fromFallback: true, error: 'insecure api base url for authenticated request' }
    const current = payload({ sources: { ...payload().sources, talentTemplates: blocked, gearTemplates: blocked } })
    const model = buildCurrentSpecWorkbenchModel({ payload: current, routeState: 'ready' })

    expect(model.contextDetail).toContain('远端模板受限，本地暂无模板')
    expect(model.evidence.map((row) => row.id)).toEqual(['talents', 'gear', 'simc', 'assistant'])
    expect(model.overallState).toBe('partial')
  })

  it('does not copy target placeholder zeroes into evidence counts', () => {
    const model = buildCurrentSpecWorkbenchModel({ payload: payload(), routeState: 'ready' })

    expect(model.evidence.find((row) => row.id === 'gear')?.sourceCountLabel).toBe('来源 --')
    expect(model.evidence.every((row) => row.revisionLabel !== '草稿')).toBe(true)
  })

  it('retains four module and four evidence slots during initial loading', () => {
    const model = buildCurrentSpecWorkbenchModel({ routeState: 'loading' })

    expect(model.modules).toHaveLength(4)
    expect(model.evidence).toHaveLength(4)
    expect(model.modules.every((module) => module.state === 'loading')).toBe(true)
    expect(model.primaryAction.disabled).toBe(true)
  })

  it('fails closed when the requested specialization is absent', () => {
    const model = buildCurrentSpecWorkbenchModel({ payload: payload(), routeState: 'ready', selectedSpecId: '不存在-专精' })

    expect(model.selection).toBeNull()
    expect(model.overallState).toBe('blocked')
    expect(model.blockers).toContain('没有可用的职业专精映射')
  })
})

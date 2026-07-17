import { describe, expect, it } from 'vitest'

import type { BuildsHomePayload } from '@wow-mini/domain'

import { buildBuildsHomeModel } from './builds-home-model'

function payload(overrides: Partial<BuildsHomePayload> = {}): BuildsHomePayload {
  return {
    navTitle: '职业专精',
    kicker: '职业控制台',
    title: '职业专精',
    desc: '只展示保留来源的职业专精目录。',
    dataStatus: 'verified',
    currentSeason: { id: '17', label: '至暗之夜 Season 1', dataStatus: 'verified' },
    raiderio: { sourceName: 'Raider.IO', sourceStatus: 'blocked', sampleCount: 0, maxKeyLevel: 0, bestScore: 0 },
    quickActions: [
      { key: 'talents', title: '天赋构筑', desc: '读取天赋' },
      { key: 'gear', title: '装备模拟', desc: '读取装备' },
      { key: 'simc', title: '模拟 SimC', desc: '提交模拟' },
      { key: 'tasks', title: '任务列表', desc: '查看任务' },
    ],
    classOptions: [
      {
        name: '法师',
        websimClassKey: 'mage',
        specializations: [
          {
            name: '冰霜',
            id: '法师-冰霜',
            title: '冰霜法师',
            className: '法师',
            specName: '冰霜',
            websimClassKey: 'mage',
            websimSpecKey: 'frost',
            specIconUrl: 'https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg',
            sourceName: 'Archon',
            sourceUrl: 'https://www.archon.gg/wow',
            publishedAt: '2026-06-09',
          },
        ],
      },
    ],
    featuredSpecializations: [],
    trustedSources: [],
    sourceRefs: [],
    ...overrides,
  }
}

describe('builds home target model', () => {
  it('keeps four evidence slots and three workflow stages without fabricating collected counts', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready', selectedSpecId: '法师-冰霜' })

    expect(model.evidenceItems.map((item) => item.id)).toEqual(['talents', 'gear', 'simc', 'tasks'])
    expect(model.evidenceItems.map((item) => item.title)).toEqual(['天赋', '装备', 'SimC', '任务'])
    expect(model.evidenceItems.every((item) => !item.value.includes('/'))).toBe(true)
    expect(model.workflow.map((stage) => stage.id)).toEqual(['input', 'validation', 'tracking'])
    expect(model.workspace.summary).not.toMatch(/\d+\s*\/\s*\d+/u)
    expect(model.workspace.statusLabel).toBe('可进入工作台')
  })

  it('does not expose blocked Raider.IO zero values as observations', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready' })

    expect(model.healthState).toBe('partial')
    expect(model.headerSourceLabel).toBe('Archon')
    expect(JSON.stringify(model)).not.toContain('maxKeyLevel')
    expect(JSON.stringify(model)).not.toContain('bestScore')
  })

  it('retains all stable slots during initial loading', () => {
    const model = buildBuildsHomeModel({ routeState: 'loading' })

    expect(model.initialLoading).toBe(true)
    expect(model.evidenceItems).toHaveLength(4)
    expect(model.evidenceItems.every((item) => item.state === 'loading')).toBe(true)
    expect(model.workflow).toHaveLength(3)
    expect(model.workspace.disabled).toBe(true)
  })

  it('marks transport fallback as stale without inheriting verified wording', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'stale' })

    expect(model.healthState).toBe('stale')
    expect(model.headerSourceLabel).toBe('Archon')
    expect(model.evidenceItems.every((item) => item.state === 'stale')).toBe(true)
    expect(model.evidenceItems.every((item) => item.stateLabel === '缓存可用')).toBe(true)
    expect(model.specialization.stateLabel).toBe('缓存可用')
    expect(model.workspace.statusLabel).toBe('使用缓存进入')
  })

  it('fails closed for an explicit specialization id that is absent from the catalog', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready', selectedSpecId: '不存在-专精' })

    expect(model.selection).toBeNull()
    expect(model.workspace.disabled).toBe(true)
    expect(model.evidenceItems.every((item) => item.disabled)).toBe(true)
  })

  it('keeps a source-backed icon at source-reference trust instead of backend-verified trust', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready', selectedSpecId: '法师-冰霜' })

    expect(model.specialization.identity?.verified).toBe(true)
    expect(model.specialization.identity?.trust.level).toBe('source_referenced')
    expect(model.specialization.identity).toMatchObject({
      objectType: 'spec',
      objectId: '法师-冰霜',
      iconUrl: 'https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg',
    })
    expect(model.specialization.sourceLabel).toBe('Archon · 2026-06-09')
  })

  it('keeps the workspace slot actionable as retry when the route request fails', () => {
    const model = buildBuildsHomeModel({ routeState: 'error' })

    expect(model.workspace.actionMode).toBe('retry')
    expect(model.workspace.actionLabel).toBe('重试')
    expect(model.workspace.disabled).toBe(false)
  })
})

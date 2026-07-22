import { describe, expect, it } from 'vitest'

import type { BuildsHomePayload } from '@wow-mini/domain'

import { emptyBuildsHomeContext } from '../_shared/build-context'
import { buildBuildsHomeModel } from './builds-home-model'

function payload(overrides: Partial<BuildsHomePayload> = {}): BuildsHomePayload {
  return {
    navTitle: '职业专精',
    kicker: '职业控制台',
    title: '职业专精',
    desc: '只展示保留来源的职业专精目录。',
    dataStatus: 'verified',
    currentSeason: { id: '17', label: '至暗之夜 Season 1', dataStatus: 'verified' },
    raiderio: { sourceStatus: 'blocked', sampleCount: 0 },
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
        iconUrl: 'https://example.test/mage.jpg',
        specializations: [{
          name: '冰霜',
          id: '法师-冰霜',
          websimClassKey: 'mage',
          websimSpecKey: 'frost',
          sourceName: 'Archon',
          sourceUrl: 'https://www.archon.gg/wow',
        }],
      },
      { name: '武僧', websimClassKey: 'monk', specializations: [] },
    ],
    featuredSpecializations: [],
    trustedSources: [],
    sourceRefs: [],
    ...overrides,
  }
}

describe('builds home command deck model', () => {
  it('renders exactly four command cards without status or readiness fields', () => {
    const model = buildBuildsHomeModel({
      payload: payload(),
      routeState: 'ready',
      context: emptyBuildsHomeContext(),
    })

    expect(model.commandItems.map((item) => item.id)).toEqual(['talents', 'gear', 'simc', 'tasks'])
    expect(JSON.stringify(model.commandItems)).not.toMatch(/stateLabel|statusLabel|准备|未校验/u)
  })

  it('binds the four command cards to the reviewed Blizzard icon sources', () => {
    const model = buildBuildsHomeModel({
      payload: payload(),
      routeState: 'ready',
      context: emptyBuildsHomeContext(),
    })

    expect(model.commandItems.map(({ id, iconUrl }) => ({ id, iconUrl }))).toEqual([
      {
        id: 'talents',
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/spell_nature_natureblessing.jpg',
      },
      {
        id: 'gear',
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_misc_gear_01.jpg',
      },
      {
        id: 'simc',
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_misc_book_09.jpg',
      },
      {
        id: 'tasks',
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_scroll_11.jpg',
      },
    ])
  })

  it('keeps tasks independent while simulators expose the resolved launch spec', () => {
    const model = buildBuildsHomeModel({
      payload: payload(),
      routeState: 'ready',
      context: { selectedClassKey: 'mage', lastSpecByClass: {} },
    })

    expect(model.commandItems.find((item) => item.id === 'tasks')?.specId).toBeUndefined()
    expect(model.commandItems.find((item) => item.id === 'simc')?.specId).toBe('法师-冰霜')
    expect(model.commandItems.filter((item) => item.id !== 'tasks').every((item) => item.specId === '法师-冰霜')).toBe(true)
  })

  it('uses canonical class options, disables only classes without a valid launch, and keeps one selection', () => {
    const model = buildBuildsHomeModel({
      payload: payload(),
      routeState: 'ready',
      context: { selectedClassKey: 'monk', lastSpecByClass: {} },
    })

    expect(model.classOptions).toEqual([
      expect.objectContaining({ classKey: 'mage', label: '法师', iconUrl: 'https://example.test/mage.jpg', disabled: false, selected: true }),
      expect.objectContaining({ classKey: 'monk', label: '武僧', disabled: true, selected: false }),
    ])
    expect(model.selectedClassKey).toBe('mage')
    expect(model.classOptions.filter((item) => item.selected)).toHaveLength(1)
  })

  it('does not fabricate command specialization context when no class has one', () => {
    const model = buildBuildsHomeModel({
      payload: payload({ classOptions: [{ name: '武僧', websimClassKey: 'monk', specializations: [] }] }),
      routeState: 'blocked',
      context: emptyBuildsHomeContext(),
    })

    expect(model.launchSpecId).toBeUndefined()
    expect(model.commandItems.filter((item) => item.id !== 'tasks').every((item) => item.specId === undefined)).toBe(true)
    expect(model.classOptions).toEqual([expect.objectContaining({ disabled: true, selected: false })])
  })

  it('does not retain overview, evidence, workspace, or workflow fields', () => {
    const model = buildBuildsHomeModel({ payload: payload(), routeState: 'ready', context: emptyBuildsHomeContext() })

    expect(model).not.toHaveProperty('title')
    expect(model).not.toHaveProperty('selection')
    expect(model).not.toHaveProperty('specialization')
    expect(model).not.toHaveProperty('evidenceItems')
    expect(model).not.toHaveProperty('workspace')
    expect(model).not.toHaveProperty('workflow')
  })
})

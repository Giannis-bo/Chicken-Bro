import { describe, expect, it } from 'vitest'

import type { BuildsIntelPayload, SpecializationSummary } from '@wow-mini/domain'

import { buildBuildIntelModel, buildIntelRoleFilter } from './build-intel-model'

function item(overrides: Partial<SpecializationSummary> = {}): SpecializationSummary {
  return {
    id: 'mage-frost',
    className: '法师',
    specName: '冰霜',
    role: '远程输出',
    title: '冰霜法师',
    desc: '真实来源记录说明',
    iconUrl: 'https://wow.zamimg.com/images/wow/icons/large/spell_frost_frostbolt02.jpg',
    sourceName: 'Archon',
    sourceUrl: 'https://www.archon.gg/wow',
    analysisWindow: '近 14 天',
    raiderioSourceStatus: 'blocked',
    sampleCount: 0,
    maxKeyLevel: 0,
    bestScore: 0,
    ...overrides,
  }
}

function payload(items: readonly SpecializationSummary[]): BuildsIntelPayload {
  return {
    navTitle: '热门专精',
    title: '热门专精资讯',
    desc: '真实接口说明',
    count: items.length,
    items,
    analysisWindow: '近 14 天',
    dataStatus: 'verified',
  }
}

const records = [
  item(),
  item({ id: 'paladin-protection', title: '防护圣骑士', className: '圣骑士', specName: '防护', role: '坦克' }),
  item({ id: 'evoker-augmentation', title: '增辉唤魔师', className: '唤魔师', specName: '增辉', role: '辅助输出' }),
  item({ id: 'priest-discipline', title: '戒律牧师', className: '牧师', specName: '戒律', role: '治疗' }),
  item({ id: 'death-knight-blood', title: '鲜血死亡骑士', className: '死亡骑士', specName: '鲜血', role: '坦克' }),
]

describe('buildBuildIntelModel', () => {
  it('keeps all five real records reachable without exposing unusable numeric fields', () => {
    const model = buildBuildIntelModel({
      payload: payload(records),
      routeState: 'ready',
      activeFilter: 'all',
      sortId: 'source',
    })

    expect(model.cards).toHaveLength(5)
    expect(model.recordCountLabel).toBe('5 条来源记录')
    expect(model.stateLabel).toBe('来源已核验')
    expect(model.cards[0]?.state).toBe('source_reference')
    expect(model.cards[0]?.metadata[2].value).toBe('数值来源受限')
    expect(JSON.stringify(model.cards)).not.toMatch(/sampleCount|maxKeyLevel|bestScore|DPS|BiS/u)
  })

  it('filters roles deterministically and pads to three visible target slots', () => {
    const model = buildBuildIntelModel({
      payload: payload(records),
      routeState: 'ready',
      activeFilter: 'tank',
      sortId: 'source',
    })

    expect(records.map(buildIntelRoleFilter)).toEqual(['damage', 'tank', 'support', 'healer', 'tank'])
    expect(model.cards).toHaveLength(3)
    expect(model.cards.slice(0, 2).map((card) => card.title)).toEqual(['防护圣骑士', '鲜血死亡骑士'])
    expect(model.cards[2]?.kind).toBe('state')
  })

  it('uses name ordering only when explicitly selected', () => {
    const model = buildBuildIntelModel({
      payload: payload(records),
      routeState: 'ready',
      activeFilter: 'all',
      sortId: 'name',
    })

    const titles = model.cards.map((card) => card.title)
    expect(titles).toEqual([...titles].sort((left, right) => left.localeCompare(right, 'zh-CN')))
    expect(model.sortLabel).toBe('专精名称')
  })

  it('mounts three stable loading cards before the payload resolves', () => {
    const model = buildBuildIntelModel({
      routeState: 'loading',
      activeFilter: 'all',
      sortId: 'source',
    })

    expect(model.initialLoading).toBe(true)
    expect(model.cards).toHaveLength(3)
    expect(model.cards.every((card) => card.loading)).toBe(true)
  })

  it('keeps the composition and exposes one deterministic retry action on error', () => {
    const model = buildBuildIntelModel({
      routeState: 'error',
      routeReason: 'network unavailable',
      activeFilter: 'all',
      sortId: 'source',
    })

    expect(model.cards).toHaveLength(3)
    expect(model.cards[0]?.primaryAction).toBe('retry')
    expect(model.cards[0]?.description).toBe('network unavailable')
    expect(model.cards.slice(1).every((card) => card.primaryAction === 'none')).toBe(true)
  })
})

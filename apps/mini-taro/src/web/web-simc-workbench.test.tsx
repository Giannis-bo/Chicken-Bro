// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ listJobs: vi.fn(), getJob: vi.fn(), createJob: vi.fn(), createSnapshot: vi.fn(), getRuntime: vi.fn() }))
vi.mock('@wow-mini/api-client', () => ({ wowApi: { simc: api } }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag,
    Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id'].includes(key) || key.startsWith('data-'))))
  return { View: host('div'), Text: host('span'), Button: host('button'), ScrollView: host('div'),
    Input: (props: { value: string; onInput: (event: { detail: { value: string } }) => void }) =>
      element('input', { value: props.value, onChange: (event: { target: { value: string } }) =>
        props.onInput({ detail: { value: event.target.value } }) }) }
})

import WebSimcView from './WebSimcView'
import elementalReport from '../../../../tests/fixtures/simc/giannis_elemental_report.json'

const success = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
const actor = { name: '测试萨满', className: 'shaman', specialization: 'elemental', level: 90, race: 'orc' }
const scenario = { fightStyle: 'Patchwerk', desiredTargets: 1, iterations: 300, maxTime: 300, varyCombatLength: 0.2, targetError: 0, raidBuffs: true, bloodlust: true }
const report = {
  schemaVersion: 1, engine: { version: '1200-01', gameVersion: '12.0.1', build: '65500' },
  actor: { ...actor, talents: 'CgQAAAA-test-talents' }, metric: { name: 'dps', value: 125432.6, error: 54.2 },
  statistics: { iterations: 300, fightLengthSeconds: 300.4, elapsedSeconds: 8.2 },
  abilities: [{ name: 'Lightning Bolt', amount: 40000, portion: 32, executions: 34, critPercent: 28 }],
  buffs: [{ name: 'Bloodlust', uptime: 13.3 }], resources: [{ name: 'maelstrom', gained: 900, lost: 880 }],
  attributes: [{ name: 'intellect', value: 7000 }], gear: [{ slot: 'head', itemId: 12345, itemLevel: 200 }],
}
const job = {
  id: 'job-completed', snapshotId: 'snapshot', status: 'succeeded', scenarioHash: 'b'.repeat(64),
  compilerRevision: 'compiler-v2', runtimeRevision: 'runtime-old', errorCode: null,
  createdAt: '2026-09-06T04:30:00Z', updatedAt: '2026-09-06T04:31:00Z', character: actor, scenario,
  metric: { name: 'dps', value: 125432.6 }, attempts: [],
  result: { id: 'result', metricName: 'dps', metricValue: 125432.6, profileSha256: 'a'.repeat(64),
    runtimeRevision: 'runtime-old', compilerRevision: 'compiler-v2', createdAt: '2026-09-06T04:31:00Z',
    provenance: { scenarioHash: 'b'.repeat(64) }, report },
}
const snapshot = { id: 'snapshot', readiness: 'READY_FOR_SIMC', character: actor, provider: 'raiderio',
  revision: 1, missingFields: [], blockers: [], provenance: { sourceRevision: 'source-one' } }

describe('Web SimC workbench', () => {
  let container: HTMLDivElement
  let root: Root
  beforeEach(async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    vi.clearAllMocks()
    api.listJobs.mockResolvedValue(success({ items: [job], nextCursor: null }))
    api.getJob.mockResolvedValue(success(job))
    api.createJob.mockResolvedValue(success(job))
    api.createSnapshot.mockResolvedValue(success(snapshot))
    api.getRuntime.mockResolvedValue(success({ status: 'available', version: '1200-02', gameVersion: '12.0.1',
      build: '66000', sourceCommit: 'abc', runtimeRevision: 'runtime-current' }))
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    await act(async () => root.render(createElement(WebSimcView, { auth: { kind: 'web', csrfToken: 'csrf' } })))
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })
  function button(label: string) {
    const found = Array.from(container.querySelectorAll('button')).find((entry) => entry.textContent?.trim() === label)
    expect(found, `button ${label}`).toBeDefined()
    return found!
  }
  async function click(label: string) { await act(async () => button(label).click()) }
  async function input(name: string, value: string) {
    const field = container.querySelector<HTMLInputElement | HTMLSelectElement>(`[name="${name}"]`)
    expect(field, `field ${name}`).not.toBeNull()
    await act(async () => {
      const prototype = field!.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype
      Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(field, value)
      field!.dispatchEvent(new Event(field!.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
    })
  }
  async function openReport() {
    await click('模拟任务')
    await act(async () => container.querySelector<HTMLButtonElement>('[data-job-id="job-completed"]')!.click())
  }

  it('renders the real elemental report with named skills and buffs while preserving its metrics', async () => {
    const before = JSON.stringify(elementalReport)
    api.getJob.mockResolvedValue(success({ ...job, character: elementalReport.actor,
      result: { ...job.result, metricValue: elementalReport.metric.value, report: elementalReport } }))
    await openReport()
    expect(container.textContent).not.toContain('待收录')
    expect(container.textContent).toContain('先祖：熔岩爆裂')
    expect(container.textContent).toContain('原始风暴元素：风暴怒火')
    expect(container.textContent).toContain('元素奔涌')
    expect(container.textContent).toContain('过载！')
    expect(container.textContent).toContain('227,723.91')
    expect(container.textContent).toContain('4,070,169.42')
    expect(JSON.stringify(elementalReport)).toBe(before)
  })

  it('separates setup, tasks and the report while retaining the current engine version', async () => {
    expect(button('新建模拟').getAttribute('aria-current')).toBe('page')
    expect(container.querySelector('[data-job-id]')).toBeNull()
    expect(container.textContent).toContain('1200-02')
    await openReport()
    expect(container.querySelector('[name="sourceUrl"]')).toBeNull()
    expect(container.querySelector('[data-job-id]')).toBeNull()
    expect(container.textContent).toContain('模拟报告')
    expect(container.textContent).toContain('1200-02')
    expect(container.textContent).toContain('1200-01')
    await click('返回模拟任务')
    expect(container.querySelector('[data-job-id]')).not.toBeNull()
  })

  it('submits every visible option with the ready snapshot and opens the report', async () => {
    await input('sourceUrl', 'https://raider.io/characters/us/illidan/test')
    await click('读取角色')
    await input('fightStyle', 'LightMovement')
    await input('desiredTargets', '3')
    await input('iterations', '1000')
    await input('maxTime', '180')
    await input('varyCombatLength', '10')
    await input('targetError', '0.5')
    await act(async () => container.querySelector<HTMLInputElement>('[name="bloodlust"]')!.click())
    await click('开始模拟')
    expect(api.createJob.mock.calls[0]?.[0]).toMatchObject({ snapshotId: 'snapshot', scenario: {
      fightStyle: 'LightMovement', desiredTargets: 3, iterations: 1000, maxTime: 180,
      varyCombatLength: 0.1, targetError: 0.5, raidBuffs: true, bloodlust: false,
    } })
    expect(container.textContent).toContain('模拟报告')
  })

  it('blocks invalid or blank numeric values and incomplete role sources', async () => {
    expect(button('开始模拟').disabled).toBe(true)
    api.createSnapshot.mockResolvedValue(success({ ...snapshot, readiness: 'INCOMPLETE_FOR_SIMC', missingFields: ['talents'] }))
    await input('sourceUrl', 'https://raider.io/characters/us/illidan/test')
    await click('读取角色')
    expect(container.textContent).toContain('天赋')
    expect(button('开始模拟').disabled).toBe(true)
    api.createSnapshot.mockResolvedValue(success(snapshot))
    await click('读取角色')
    await input('targetError', '')
    expect(button('开始模拟').disabled).toBe(true)
    await input('targetError', '0')
    await input('maxTime', '601')
    expect(button('开始模拟').disabled).toBe(true)
    await input('maxTime', '300.5')
    expect(button('开始模拟').disabled).toBe(true)
  })

  it('shows real report sections, uncertainty and task engine without fabricated missing data', async () => {
    await openReport()
    for (const copy of ['125,432.6', '54.2', '技能贡献', '闪电箭', '增益覆盖', '13.3%',
      '资源', '900', '属性', '7,000', '装备与天赋', '12345', 'CgQAAAA-test-talents']) expect(container.textContent).toContain(copy)
  })

  it('uses mainland Chinese game labels without exposing engine tokens', async () => {
    expect(Array.from(container.querySelectorAll('option')).map(option => option.textContent)).toEqual(['站桩战斗', '多目标顺劈', '少量移动', '频繁移动'])
    expect(container.textContent).toContain('标准团队增益')
    await openReport()
    expect(container.textContent).toContain('每秒伤害')
    expect(container.textContent).toContain('闪电箭')
    expect(container.textContent).toContain('嗜血')
    for (const english of ['Lightning Bolt', 'Bloodlust', 'Buff', 'DPS', 'HPS', 'Patchwerk']) expect(container.textContent).not.toContain(english)
  })

  it('keeps unknown spell rows distinct without guessing Chinese translations', async () => {
    api.getJob.mockResolvedValue(success({ ...job, result: { ...job.result, report: { ...report,
      abilities: [{ ...report.abilities[0], name: 'future_spell_alpha' }, { ...report.abilities[0], name: 'future_spell_beta' }],
      buffs: [{ name: 'future_buff', uptime: 12 }], attributes: [{ name: 'speed_rating', value: 61 }],
    } } }))
    await openReport()
    expect(container.textContent).toContain('名称待收录的技能（1）')
    expect(container.textContent).toContain('名称待收录的技能（2）')
    expect(container.textContent).toContain('名称待收录的增益（1）')
    expect(container.textContent).toContain('加速等级')
    expect(container.textContent).not.toContain('future_')
    expect(container.textContent).not.toContain('speed_rating')
  })

  it('honestly downgrades historical results with no structured report', async () => {
    api.getJob.mockResolvedValue(success({ ...job, scenario: null, character: null, result: { ...job.result, report: null } }))
    await openReport()
    expect(container.textContent).toContain('该历史任务仅保存了结果摘要')
    expect(container.textContent).toContain('运行版本未记录')
    expect(container.textContent).toContain('125,432.6')
    expect(container.textContent).not.toContain('Lightning Bolt')
  })

  it.each([12.5, 0])('shows saved historical uncertainty even without a structured report: %s', async (metricError) => {
    api.getJob.mockResolvedValue(success({ ...job, result: { ...job.result, report: null, metricError } }))
    await openReport()
    expect(container.textContent).toContain(`误差 ± ${metricError}`)
    expect(container.textContent).not.toContain('误差未记录')
  })

  it('prefers structured report uncertainty over a historical summary value', async () => {
    api.getJob.mockResolvedValue(success({ ...job, result: { ...job.result, metricError: 999 } }))
    await openReport()
    expect(container.textContent).toContain('误差 ± 54.2')
    expect(container.textContent).not.toContain('误差 ± 999')
  })

  it('filters statuses in Chinese and presents failures with their actual diagnostic code', async () => {
    const failed = { ...job, id: 'job-failed', status: 'failed', metric: null, result: null, errorCode: 'SIMC_TIMEOUT' }
    api.listJobs.mockResolvedValue(success({ items: [job, failed], nextCursor: null }))
    await click('模拟任务')
    await click('刷新任务')
    await click('失败')
    expect(container.querySelectorAll('[data-job-id]')).toHaveLength(1)
    api.getJob.mockResolvedValue(success(failed))
    await act(async () => container.querySelector<HTMLButtonElement>('[data-job-id="job-failed"]')!.click())
    expect(container.textContent).toContain('模拟未完成')
    expect(container.textContent).toContain('云端模拟超时')
    expect(container.querySelector('[data-error-code="SIMC_TIMEOUT"]')).not.toBeNull()
    expect(container.textContent).not.toContain('125,432.6')
  })

  it('displays an unavailable engine honestly without using a runtime revision as version', async () => {
    api.getRuntime.mockResolvedValue(success({ status: 'unavailable', version: null, gameVersion: null, build: null,
      sourceCommit: null, runtimeRevision: 'runtime-only-hash' }))
    await act(async () => root.render(createElement(WebSimcView, { auth: { kind: 'web', csrfToken: 'other' } })))
    expect(container.textContent).toContain('SIMC 暂不可用')
    expect(container.textContent).not.toContain('runtime-only-hash')
  })

  it('recovers from an unavailable runtime by retrying without leaving the workbench', async () => {
    api.getRuntime.mockResolvedValue(success({ status: 'unavailable', version: null, gameVersion: null, build: null,
      sourceCommit: null, runtimeRevision: null }))
    await act(async () => root.render(createElement(WebSimcView, { auth: { kind: 'web', csrfToken: 'other' } })))
    await input('sourceUrl', 'https://raider.io/characters/us/illidan/test')
    await click('读取角色')
    expect(button('开始模拟').disabled).toBe(true)
    api.getRuntime.mockResolvedValue(success({ status: 'available', version: '1200-03', gameVersion: '12.0.1',
      build: '66100', sourceCommit: 'abc', runtimeRevision: 'runtime-current' }))
    await click('重试引擎')
    expect(container.textContent).toContain('SIMC 1200-03')
    expect(button('开始模拟').disabled).toBe(false)
  })

  it('refreshes the current runtime when entering new simulation', async () => {
    await click('模拟任务')
    api.getRuntime.mockResolvedValue(success({ status: 'available', version: '1200-04', gameVersion: '12.0.1',
      build: '66200', sourceCommit: 'abc', runtimeRevision: 'runtime-next' }))
    await click('新建模拟')
    expect(container.textContent).toContain('SIMC 1200-04')
  })

  it('refreshes server task status when returning from a report', async () => {
    await openReport()
    const changed = { ...job, character: { ...actor, name: '服务端更新后的角色' } }
    api.listJobs.mockResolvedValue(success({ items: [changed], nextCursor: null }))
    await click('返回模拟任务')
    expect(container.textContent).toContain('服务端更新后的角色')
  })

  it('does not describe a failed history request as an empty account', async () => {
    api.listJobs.mockResolvedValue({ payload: null, fromFallback: true, error: '历史读取失败', problemCode: 'NETWORK_ERROR' })
    await act(async () => root.render(createElement(WebSimcView, { auth: { kind: 'web', csrfToken: 'other' } })))
    await click('模拟任务')
    expect(container.textContent).toContain('历史读取失败')
    expect(container.textContent).not.toContain('还没有模拟任务')
  })

  it('requires reading the new source after editing a ready character URL', async () => {
    await input('sourceUrl', 'https://raider.io/characters/us/illidan/test')
    await click('读取角色')
    expect(button('开始模拟').disabled).toBe(false)
    await input('sourceUrl', 'https://raider.io/characters/us/illidan/another')
    expect(button('开始模拟').disabled).toBe(true)
    expect(container.textContent).not.toContain('角色已就绪')
  })

  it('updates a queued report with its real completed result after polling', async () => {
    vi.useFakeTimers()
    api.getJob.mockResolvedValue(success({ ...job, status: 'queued', result: null, metric: null }))
    await openReport()
    expect(container.textContent).toContain('任务已提交，等待云端模拟')
    expect(container.textContent).not.toContain('125,432.6')
    api.getJob.mockResolvedValue(success(job))
    await act(async () => vi.advanceTimersByTimeAsync(1000))
    expect(container.textContent).toContain('125,432.6')
    expect(container.textContent).not.toContain('任务已提交，等待云端模拟')
  })

  it('labels absent structured report sections as unrecorded', async () => {
    api.getJob.mockResolvedValue(success({ ...job, result: { ...job.result, report: {
      ...report, abilities: [], buffs: [], resources: [], attributes: [], gear: [], actor: { ...actor, talents: null },
    } } }))
    await openReport()
    for (const copy of ['未记录技能贡献', '未记录增益覆盖', '未记录资源收支', '未记录角色属性', '未记录装备', '未记录天赋']) expect(container.textContent).toContain(copy)
  })

  it('formats normalized combat percentages and ratings with Chinese stat labels', async () => {
    api.getJob.mockResolvedValue(success({ ...job, result: { ...job.result, report: {
      ...report, attributes: [
        { name: 'crit_pct', value: 25.37 }, { name: 'haste_pct', value: 18.2 }, { name: 'mastery_pct', value: 55.6 },
        { name: 'versatility_pct', value: 12.4 }, { name: 'avoidance_pct', value: 3 }, { name: 'leech_pct', value: 2 },
        { name: 'crit_rating', value: 1600 }, { name: 'manareg_per_second', value: 125 },
      ],
    } } }))
    await openReport()
    for (const copy of ['爆击25.37%', '急速18.2%', '精通55.6%', '全能12.4%', '闪避3%', '吸血2%', '爆击等级1,600', '每秒法力恢复125']) expect(container.textContent).toContain(copy)
    expect(container.textContent).not.toContain('2,537%')
  })

  it.each([
    ['Hunter', 'Beast Mastery', '野兽控制 猎人'],
    ['Death Knight', 'Frost', '冰霜 死亡骑士'],
  ])('localizes engine class and specialization names containing spaces: %s %s', async (className, specialization, expected) => {
    api.getJob.mockResolvedValue(success({ ...job, result: { ...job.result, report: {
      ...report, actor: { ...report.actor, className, specialization },
    } } }))
    await openReport()
    expect(container.textContent).toContain(expected)
  })
})

import { describe, expect, it } from 'vitest'

import type { SimulatorTaskRecord } from '@wow-mini/domain'

import { buildTaskDetailView, type TaskDetailRouteContext } from './task-detail-model'

const ready: TaskDetailRouteContext = { phase: 'ready', reason: '', refreshing: false }

function formalTask(overrides: Partial<SimulatorTaskRecord> = {}): SimulatorTaskRecord {
  return {
    taskId: 'formal-task',
    status: 'completed',
    mode: 'simcraft_template',
    question: '后端返回的任务标题',
    createdAt: '2026-07-15T01:00:00Z',
    analysis: {
      mode: 'simcraft_template',
      status: 'completed',
      recommendations: [],
      simcReport: {
        title: '后端 SimC 报告',
        summary: '后端正式报告摘要',
        profileSource: 'template',
        result: { ran: true, hasDps: true, dpsDisplay: '1,234,567 DPS', metricLabel: 'DPS' },
        timing: { startedAt: '2026-07-15T01:01:00Z', elapsedMs: 125000 },
        scenario: { label: '单体', fightStyle: 'Patchwerk', durationSeconds: 300, targets: 1, enemyLevel: 93 },
        build: {
          talentTemplate: { id: 'talent-1', title: '团本天赋' },
          gearTemplate: { id: 'gear-1', title: '团本装备' },
          statSnapshot: {
            statStatus: 'verified',
            statSource: 'websim',
            primary: { key: 'intellect', label: '智力', value: '50123' },
            secondary: [
              { key: 'haste', label: '急速', value: '25%' },
              { key: 'mastery', label: '精通', value: '18%' },
            ],
          },
        },
        preparation: {
          evidenceState: 'verified',
          summary: '后端准备配置',
          items: [
            { category: 'raid_buff_baseline', label: 'Full raid buff package', state: 'disabled', evidenceState: 'verified' },
            { category: 'self_class_raid_buff', label: 'Arcane Intellect', state: 'enabled', evidenceState: 'verified' },
            { category: 'temporary_combat_buffs', label: 'Temporary combat buffs', state: 'disabled', evidenceState: 'verified' },
          ],
        },
      },
    },
    ...overrides,
  }
}

describe('task_detail truth model', () => {
  it('preserves the target topology counts for a completed formal report', () => {
    const view = buildTaskDetailView(formalTask(), ready)
    expect(view.result).toMatchObject({ state: 'completed', metricValue: '1,234,567 DPS' })
    expect(view.metadata).toHaveLength(4)
    expect(view.result.progress).toHaveLength(4)
    expect(view.context).toHaveLength(4)
    expect(view.scenario).toHaveLength(4)
    expect(view.attributes).toHaveLength(6)
    expect(view.preparation).toHaveLength(5)
    expect(view.attributeVerified).toBe(true)
    expect(view.attributes.find((item) => item.id === 'intellect')?.value).toBe('50123')
  })

  it('withholds DPS unless every formal-result gate is satisfied', () => {
    const generated = formalTask({
      analysis: {
        mode: 'simcraft_template',
        status: 'completed',
        recommendations: [],
        simcReport: {
          profileSource: 'generated',
          result: { ran: true, hasDps: true, dpsDisplay: '9,999,999 DPS' },
        },
      },
    })
    const missingFlag = formalTask({
      analysis: {
        mode: 'simcraft_template',
        status: 'completed',
        recommendations: [],
        simcReport: { profileSource: 'template', result: { ran: true, hasDps: false, dpsDisplay: '9,999,999 DPS' } },
      },
    })
    expect(buildTaskDetailView(generated, ready).result).toMatchObject({ state: 'unsupported', metricValue: '未返回' })
    expect(buildTaskDetailView(missingFlag, ready).result).toMatchObject({ state: 'unsupported', metricValue: '未返回' })
  })

  it('maps queued, failed and non-SimC tasks without inventing report facts', () => {
    const queued = buildTaskDetailView({ taskId: 'queued', status: 'queued', mode: 'simcraft_template' }, ready)
    expect(queued.result.state).toBe('pending')
    expect(queued.result.progress.map((item) => item.state)).toEqual(['complete', 'active', 'waiting', 'waiting'])

    const failed = buildTaskDetailView({
      taskId: 'failed',
      status: 'failed',
      mode: 'simcraft_template',
      analysis: {
        mode: 'simcraft_template', status: 'failed', recommendations: [],
        simulation: { error: 'SimC process exited' },
      },
    }, ready)
    expect(failed.exception).toMatchObject({ state: 'failed', detail: 'SimC process exited' })
    expect(failed.result.metricValue).toBe('未返回')

    const wcl = buildTaskDetailView({ taskId: 'wcl', status: 'completed', mode: 'warcraft_logs' }, ready)
    expect(wcl.result).toMatchObject({ state: 'unsupported', metricValue: '未返回' })
  })

  it('keeps all cells neutral when the owner-scoped endpoint is blocked', () => {
    const view = buildTaskDetailView(undefined, { phase: 'blocked', reason: 'unauthorized', refreshing: false })
    expect(view.routePhase).toBe('blocked')
    expect(view.result.state).toBe('blocked')
    expect(view.exception).toMatchObject({ state: 'blocked', detail: 'unauthorized' })
    expect(view.metadata).toHaveLength(4)
    expect(view.context.every((item) => item.value === '未返回')).toBe(true)
    expect(view.attributes.every((item) => item.value === '未返回')).toBe(true)
  })

  it('uses returned verified attributes and preparation only', () => {
    const task = formalTask()
    const unverified = formalTask({
      analysis: {
        mode: 'simcraft_template',
        status: 'completed',
        recommendations: [],
        simcReport: {
          result: { ran: false, hasDps: false },
          build: { statSnapshot: { statStatus: 'partial', primary: { key: 'strength', value: '99999' } } },
          preparation: { evidenceState: 'partial', items: [] },
        },
      },
    })
    expect(buildTaskDetailView(task, ready).preparationState).toBe('verified')
    const view = buildTaskDetailView(unverified, ready)
    expect(view.attributeVerified).toBe(false)
    expect(view.attributes.every((item) => item.value === '未返回')).toBe(true)
    expect(view.preparationState).toBe('partial')
  })
})

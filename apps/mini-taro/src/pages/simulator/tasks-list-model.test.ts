import { describe, expect, it } from 'vitest'

import type { SimulatorTaskRecord } from '@wow-mini/domain'

import {
  filterAndSortTasks,
  formatTaskTime,
  latestTaskSummary,
  taskRecordView,
  taskStatusGroup,
  taskSummaryMetrics,
} from './tasks-list-model'

const tasks: SimulatorTaskRecord[] = [
  { taskId: 'queued', status: 'queued', mode: 'simcraft_template', createdAt: '2026-07-15T01:00:00Z' },
  { taskId: 'running', status: 'processing', createdAt: '2026-07-15T02:00:00Z' },
  { taskId: 'failed', status: 'canceled', createdAt: '2026-07-15T03:00:00Z' },
  { taskId: 'done', status: 'succeeded', createdAt: '2026-07-15T04:00:00Z' },
  { taskId: 'unknown', status: 'mystery', createdAt: 'invalid' },
]

describe('tasks_list truth model', () => {
  it('maps backend states without promoting unknown tasks', () => {
    expect(taskStatusGroup('queued')).toBe('queued')
    expect(taskStatusGroup('processing')).toBe('running')
    expect(taskStatusGroup('cancelled')).toBe('failed')
    expect(taskStatusGroup('ready')).toBe('completed')
    expect(taskStatusGroup('mystery')).toBe('unknown')
  })

  it('derives four overview metrics from real tasks only', () => {
    expect(taskSummaryMetrics(tasks).map((item) => item.count)).toEqual([1, 1, 1, 1])
  })

  it('filters and sorts owner-scoped tasks locally', () => {
    expect(filterAndSortTasks(tasks, 'all', 'newest').map((task) => task.taskId)).toEqual(['done', 'failed', 'running', 'queued', 'unknown'])
    expect(filterAndSortTasks(tasks, 'failed', 'oldest').map((task) => task.taskId)).toEqual(['failed'])
  })

  it('uses returned report facts and neutral missing-field labels', () => {
    const view = taskRecordView({
      taskId: 'report',
      status: 'completed',
      mode: 'simcraft_template',
      updatedAt: '2026-07-15T05:30:00Z',
      simcReportSummary: {
        title: '真实后端标题',
        summary: '真实后端摘要',
        statusText: '真实后端状态',
        build: { className: '法师', specName: '冰霜' },
        scenario: { key: 'mythic_plus' },
      },
    })
    expect(view).toMatchObject({
      title: '真实后端标题',
      description: '真实后端摘要',
      tags: ['法师 / 冰霜', 'mythic_plus', 'SimC 模板任务'],
      feedback: '真实后端状态',
      navigable: true,
    })
    expect(taskRecordView(tasks[0]!).description).toBe('后端未返回任务摘要')
    expect(taskRecordView(tasks[0]!).description).not.toContain('占位')
  })

  it('never presents invalid dates as real timestamps', () => {
    expect(formatTaskTime(tasks[0]!)).toBe('创建 2026-07-15 01:00')
    expect(formatTaskTime(tasks[4]!)).toBe('未返回时间')
    expect(latestTaskSummary([])).toEqual({ title: '暂无记录', detail: '当前 owner 未返回任务' })
  })
})

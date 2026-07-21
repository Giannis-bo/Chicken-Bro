import type { SimulatorTaskRecord } from '@wow-mini/domain'
import { describe, expect, it } from 'vitest'

import { buildRecentSimcTaskPreviews } from './builds-recent-simc-model'

function task(
  taskId: string,
  mode: string,
  updatedAt: string,
  status = 'succeeded',
): SimulatorTaskRecord {
  return {
    taskId,
    mode,
    status,
    updatedAt,
    simcReportSummary: {
      build: { className: '法师', specName: '冰霜' },
      scenario: { label: '大秘境基准' },
    },
  }
}

describe('builds home recent SimC preview model', () => {
  it('keeps only the three newest current SimC submissions across classes', () => {
    const previews = buildRecentSimcTaskPreviews([
      task('old-mage', 'simcraft_template', '2026-07-20T10:00:00Z'),
      task('legacy-agent', 'simcraft_agent', '2026-07-21T12:00:00Z'),
      task('latest-priest', 'simcraft_template', '2026-07-21T13:00:00Z'),
      task('middle-warrior', 'simcraft_template', '2026-07-21T12:00:00Z'),
      task('third-shaman', 'simcraft_template', '2026-07-21T11:00:00Z'),
      task('fourth-druid', 'simcraft_template', '2026-07-21T09:00:00Z'),
    ])

    expect(previews.map((item) => item.id)).toEqual([
      'latest-priest',
      'middle-warrior',
      'third-shaman',
    ])
  })

  it('uses neutral returned-field fallbacks and preserves the real task state', () => {
    const [preview] = buildRecentSimcTaskPreviews([
      { taskId: 'no-report', mode: 'simcraft_template', status: 'mystery', updatedAt: 'invalid' },
    ])

    expect(preview).toMatchObject({
      id: 'no-report',
      state: 'unknown',
      timeLabel: '未返回时间',
    })
    expect(preview?.title).not.toMatch(/DPS|BiS|占位/u)
  })
})

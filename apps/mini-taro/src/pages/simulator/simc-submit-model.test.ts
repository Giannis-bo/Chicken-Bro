import { describe, expect, it } from 'vitest'

import type { BuildTemplate } from '@wow-mini/domain'

import {
  simcBlockerRows,
  simcBuffRules,
  simcConfirmationLabel,
  simcSummaryRows,
  simcTemplateSlot,
} from './simc-submit-model'

const localTemplate: BuildTemplate = {
  id: 'local-talent', clientId: 'local-talent', type: 'talent', title: '本地天赋',
  classKey: 'mage', className: '法师', specKey: 'frost', specName: '冰霜',
  heroKey: '', heroLabel: '', scenarioKey: 'single', scenarioTitle: '单体', rawString: 'talents=',
  simcLines: [], status: 'ready', statusLabel: '本地', source: 'local', metadata: {},
  createdAt: '', updatedAt: '', remote: false, schemaVersion: 1,
  trust: { level: 'local_only', reason: '仅保存在当前设备' },
}

describe('SimC submit truth model', () => {
  it('preserves empty template slots without inventing templates', () => {
    expect(simcTemplateSlot('talent', [], '')).toMatchObject({
      valueLabel: '未选择天赋模板',
      helperLabel: '尚未保存模板',
      state: 'blocked',
      options: [],
    })
  })

  it('keeps local templates distinct from synchronized templates', () => {
    expect(simcTemplateSlot('talent', [localTemplate], localTemplate.id)).toMatchObject({
      valueLabel: '本地天赋',
      helperLabel: '仅保存在本机',
      state: 'partial',
    })
  })

  it('keeps four buff positions read-only and truth-safe', () => {
    expect(simcBuffRules).toHaveLength(4)
    expect(simcBuffRules.every((rule) => rule.value !== '未选择')).toBe(true)
    expect(simcBuffRules.some((rule) => rule.value.includes('未提供可验证输入'))).toBe(true)
  })

  it('derives six summary rows and five blockers from real readiness', () => {
    const input = {
      specializationLabel: '冰霜法师', raceLabel: '人类', scenarioLabel: '单体', durationSeconds: 300,
      talentTemplate: localTemplate, activeTaskCount: 0, confirmationState: 'unknown' as const,
    }
    expect(simcSummaryRows(input)).toHaveLength(6)
    const blockers = simcBlockerRows(input)
    expect(blockers).toHaveLength(5)
    expect(blockers.find((row) => row.id === 'gear')?.blocked).toBe(true)
    expect(blockers.find((row) => row.id === 'validation')?.blocked).toBe(true)
    expect(simcBlockerRows({ ...input, confirmationState: 'ready' })
      .find((row) => row.id === 'validation')?.detail).toBe('后端已确认当前组合')
  })

  it('does not claim a result before a returned task id exists', () => {
    expect(simcConfirmationLabel('ready', false, '')).toEqual({
      title: '组合校验通过', detail: '可提交真实任务', state: 'ready',
    })
    expect(simcConfirmationLabel('unknown', false, 'task-verified')).toEqual({
      title: '任务已提交', detail: 'task-verified', state: 'ready',
    })
  })
})

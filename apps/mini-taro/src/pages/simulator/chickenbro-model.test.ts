import { describe, expect, it } from 'vitest'

import type { ChatMessage } from '@wow-mini/domain'

import {
  boundedChickenbroMessage,
  chickenbroAnswerSource,
  chickenbroEvidenceRows,
  chickenbroLimitations,
  chickenbroMissingInputs,
  chickenbroVisibleTurns,
} from './chickenbro-model'

describe('chickenbro truth model', () => {
  it('shows only the latest two real turns without inventing history', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'one' }, { role: 'assistant', content: 'answer one' },
      { role: 'user', content: 'two' }, { role: 'assistant', content: 'answer two' },
      { role: 'user', content: 'three' },
    ]
    expect(chickenbroVisibleTurns(messages).map((turn) => turn.user.content)).toEqual(['two', 'three'])
    expect(chickenbroVisibleTurns([])).toEqual([])
  })

  it('keeps two evidence positions but never synthesizes references', () => {
    expect(chickenbroEvidenceRows(undefined)).toEqual([
      { id: 'evidence-1', title: '等待后端证据', detail: '未返回 evidenceRef', state: 'blocked' },
      { id: 'evidence-2', title: '等待后端证据', detail: '未返回 evidenceRef', state: 'blocked' },
    ])
    expect(chickenbroEvidenceRows({
      answerSource: 'evidence', confidence: 'medium', priorityActions: [],
      evidenceRefs: ['simc://task/verified'], limitations: [],
    })[0]).toMatchObject({ state: 'ready', detail: 'simc://task/verified' })
  })

  it('labels backend deterministic fallback instead of presenting it as evidence', () => {
    expect(chickenbroAnswerSource({
      answerSource: 'deterministic_fallback', confidence: 'low', priorityActions: [], evidenceRefs: [], limitations: [],
    })).toBe('后端通用建议')
  })

  it('retains three fixed boundary positions from backend codes', () => {
    const payload = {
      answerSource: 'deterministic_fallback', confidence: 'low', priorityActions: [], evidenceRefs: [],
      missingInputs: ['simc_or_wcl', 'published_profile'], limitations: ['missing_published_profile'],
    }
    expect(chickenbroMissingInputs(payload)).toHaveLength(3)
    expect(chickenbroMissingInputs(payload)[0]?.label).toBe('SimC 或 WCL')
    expect(chickenbroLimitations(payload)).toHaveLength(3)
    expect(chickenbroLimitations(payload)[0]?.label).toBe('缺少已发布配置')
  })

  it('trims and caps outgoing messages at 2000 characters', () => {
    expect(boundedChickenbroMessage(`  ${'x'.repeat(2100)}  `)).toHaveLength(2000)
  })
})

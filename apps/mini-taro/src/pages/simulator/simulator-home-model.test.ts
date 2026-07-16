import { describe, expect, it } from 'vitest'

import type { ChatMessage } from '@wow-mini/domain'

import {
  initialSimulatorHomeMessages,
  simulatorAssistantStatus,
  simulatorEvidenceCards,
  simulatorHomeContext,
  simulatorHomeSuggestions,
} from './simulator-home-model'

describe('simulator home truth model', () => {
  it('starts with one boundary message and three safe prompts', () => {
    const messages = initialSimulatorHomeMessages()
    expect(messages).toHaveLength(1)
    expect(messages[0]?.role).toBe('assistant')
    expect(messages[0]?.content).toContain('缺少资料')
    expect(simulatorHomeSuggestions).toHaveLength(3)
  })

  it('labels a real backend deterministic fallback without upgrading confidence', () => {
    const message: ChatMessage = {
      role: 'assistant',
      content: '有边界的通用建议',
      payload: {
        answerSource: 'deterministic_fallback',
        confidence: 'low',
        basisLabel: '通用建议',
        priorityActions: [],
        evidenceRefs: [],
        limitations: ['missing_published_profile'],
        missingInputs: ['class_spec'],
      },
    }

    expect(simulatorAssistantStatus(message, false)).toBe('通用建议 · 低置信度')
    expect(simulatorHomeContext([message])).toEqual({
      answerSourceLabel: '通用建议',
      confidenceLabel: '低置信度',
      evidenceCount: 0,
      evidenceStateLabel: '尚无可引用证据',
      missingInputs: ['class_spec'],
      limitations: ['missing_published_profile'],
    })
  })

  it('uses only returned evidence references and preserves three stable card slots', () => {
    const message: ChatMessage = {
      role: 'assistant',
      content: '基于证据的回答',
      payload: {
        answerSource: 'evidence',
        confidence: 'medium',
        priorityActions: [],
        evidenceRefs: ['simc://task/verified'],
        limitations: [],
      },
    }

    const cards = simulatorEvidenceCards([message])
    expect(cards).toHaveLength(3)
    expect(cards[0]).toMatchObject({ state: 'ready', title: 'simc://task/verified' })
    expect(cards[1]).toMatchObject({ state: 'blocked', title: '等待后端证据' })
    expect(cards[2]).toMatchObject({ state: 'unavailable', title: '证据导入暂未开放' })
  })

  it('distinguishes a transport failure from backend bounded guidance', () => {
    const message: ChatMessage = { role: 'assistant', content: '服务不可用' }
    expect(simulatorAssistantStatus(message, true)).toBe('服务不可用 · 可重试')
  })
})

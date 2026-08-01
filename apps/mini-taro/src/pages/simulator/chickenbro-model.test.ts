import { describe, expect, it } from 'vitest'

import type { ChatMessage } from '@wow-mini/domain'

import {
  boundedChickenbroMessage,
  chickenbroAttachmentRefs,
  chickenbroMarkMessageReceived,
  chickenbroTranscript,
} from './chickenbro-model'

describe('Captain conversation model', () => {
  it('keeps the complete server conversation in its returned order', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: '第一条问题' },
      { role: 'assistant', content: '第一条回答' },
      { role: 'user', content: '第二条问题' },
      { role: 'assistant', content: '第二条回答' },
      { role: 'user', content: '第三条问题' },
    ]

    expect(chickenbroTranscript(messages).map((message) => message.content)).toEqual([
      '第一条问题', '第一条回答', '第二条问题', '第二条回答', '第三条问题',
    ])
  })

  it('renders an attachment only for evidence references returned by an assistant message', () => {
    const assistant: ChatMessage = {
      role: 'assistant',
      content: '这是后端返回的回答。',
      payload: {
        answerSource: 'evidence', confidence: 'medium', priorityActions: [],
        evidenceRefs: ['simc://task/verified'], limitations: [],
      },
    }

    expect(chickenbroAttachmentRefs(assistant)).toEqual(['simc://task/verified'])
    expect(chickenbroAttachmentRefs({ role: 'assistant', content: '没有附件' })).toEqual([])
    expect(chickenbroAttachmentRefs({
      role: 'user',
      content: '用户文本',
      payload: assistant.payload!,
    })).toEqual([])
  })

  it('trims and bounds a text-only outgoing message', () => {
    expect(boundedChickenbroMessage(`  ${'x'.repeat(2100)}  `)).toHaveLength(2000)
  })

  it('marks only the acknowledged optimistic user message as received', () => {
    const messages: ChatMessage[] = [
      { messageId: 'local-user-1', role: 'user', content: '第一条问题', status: 'sending' },
      { messageId: 'server-user-2', role: 'user', content: '第二条问题', status: 'received' },
    ]

    expect(chickenbroMarkMessageReceived(messages, 'local-user-1')).toEqual([
      { messageId: 'local-user-1', role: 'user', content: '第一条问题', status: 'received' },
      { messageId: 'server-user-2', role: 'user', content: '第二条问题', status: 'received' },
    ])
  })
})

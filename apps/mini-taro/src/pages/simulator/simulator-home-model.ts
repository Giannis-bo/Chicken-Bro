import type { AssistantPayload, ChatMessage } from '@wow-mini/domain'

export type SimulatorHomeInputState = 'ready' | 'loading' | 'error'

export interface SimulatorHomeContextView {
  answerSourceLabel: string
  confidenceLabel: string
  evidenceCount: number
  evidenceStateLabel: string
  missingInputs: readonly string[]
  limitations: readonly string[]
}

export interface SimulatorEvidenceCardView {
  id: 'reference-1' | 'reference-2' | 'ingestion'
  eyebrow: string
  title: string
  state: 'ready' | 'blocked' | 'unavailable'
}

export const simulatorHomeSuggestions = [
  '缺资料时先给下一步，我再补充证据',
  '有什么关键信息还需要我提供？',
  '请只解释证据，先给结论要点',
] as const

export function initialSimulatorHomeMessages(): readonly ChatMessage[] {
  return [{
    messageId: 'assistant-boundary',
    role: 'assistant',
    content: '请描述职业、专精、场景和问题。我只会解释已提供的证据；缺少资料时，会先说明还需要什么。',
    status: '证据边界已开启',
  }]
}

function latestAssistantPayload(messages: readonly ChatMessage[]): AssistantPayload | undefined {
  return [...messages].reverse().find((message) => message.role === 'assistant' && message.payload)?.payload
}

function sourceLabel(payload: AssistantPayload | undefined): string {
  if (!payload) return '尚未调用分析服务'
  if (payload.basisLabel) return payload.basisLabel
  if (payload.answerSource === 'deterministic_fallback') return '通用建议'
  if (payload.answerSource === 'frontend_fallback') return '服务不可用'
  return payload.answerSource || '后端回答'
}

function confidenceLabel(payload: AssistantPayload | undefined): string {
  if (!payload) return '等待提问'
  if (payload.confidence === 'low') return '低置信度'
  if (payload.confidence === 'blocked') return '已阻断'
  return payload.confidence || '未标注置信度'
}

export function simulatorHomeContext(messages: readonly ChatMessage[]): SimulatorHomeContextView {
  const payload = latestAssistantPayload(messages)
  const evidenceCount = payload?.evidenceRefs.length ?? 0
  return {
    answerSourceLabel: sourceLabel(payload),
    confidenceLabel: confidenceLabel(payload),
    evidenceCount,
    evidenceStateLabel: evidenceCount > 0 ? `已连接 ${evidenceCount} 条来源` : '尚无可引用证据',
    missingInputs: payload?.missingInputs ?? [],
    limitations: payload?.limitations ?? [],
  }
}

export function simulatorAssistantStatus(message: ChatMessage, transportFallback: boolean): string {
  if (transportFallback) return '服务不可用 · 可重试'
  const payload = message.payload
  if (payload?.answerSource === 'deterministic_fallback') {
    return `${payload.basisLabel || '通用建议'} · 低置信度`
  }
  if (payload?.evidenceRefs.length) return `引用 ${payload.evidenceRefs.length} 条证据`
  return message.status || '后端回答'
}

function evidenceTitle(reference: string): string {
  const value = reference.trim()
  if (!value) return '证据未提供'
  return value.length > 28 ? `${value.slice(0, 27)}...` : value
}

export function simulatorEvidenceCards(messages: readonly ChatMessage[]): readonly SimulatorEvidenceCardView[] {
  const references = latestAssistantPayload(messages)?.evidenceRefs ?? []
  const referenceCard = (index: 0 | 1): SimulatorEvidenceCardView => {
    const reference = references[index]
    return reference
      ? {
          id: index === 0 ? 'reference-1' : 'reference-2',
          eyebrow: `来源参考 0${index + 1}`,
          title: evidenceTitle(reference),
          state: 'ready',
        }
      : {
          id: index === 0 ? 'reference-1' : 'reference-2',
          eyebrow: `来源参考 0${index + 1}`,
          title: '等待后端证据',
          state: 'blocked',
        }
  }

  return [
    referenceCard(0),
    referenceCard(1),
    {
      id: 'ingestion',
      eyebrow: '补充资料',
      title: '证据导入暂未开放',
      state: 'unavailable',
    },
  ]
}

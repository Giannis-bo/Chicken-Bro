import type { AssistantPayload, ChatMessage } from '@wow-mini/domain'

export interface ChickenbroContextValue {
  from?: string | undefined
  classKey?: string | undefined
  specKey?: string | undefined
  spec?: string | undefined
  scenario?: string | undefined
}

export interface ChickenbroTurn {
  user: ChatMessage
  assistant?: ChatMessage | undefined
}

export interface ChickenbroEvidenceRow {
  id: string
  title: string
  detail: string
  state: 'ready' | 'blocked'
}

export interface ChickenbroBoundaryItem {
  id: string
  label: string
  state: 'ready' | 'unavailable'
}

const missingInputLabels: Readonly<Record<string, string>> = {
  class_spec: '职业与专精',
  published_profile: '已发布配置',
  simc_or_wcl: 'SimC 或 WCL',
  scenario: '战斗场景',
  target_count: '目标数量',
  duration: '战斗时长',
}

const limitationLabels: Readonly<Record<string, string>> = {
  missing_published_profile: '缺少已发布配置',
  non_wow_topic: '超出问答范围',
  backend_unavailable: '后端不可用',
  no_evidence: '没有返回证据',
}

function displayCode(value: string, labels: Readonly<Record<string, string>>): string {
  return labels[value] ?? value.replaceAll('_', ' ')
}

export function chickenbroContextLabel(context: ChickenbroContextValue): string {
  if (context.spec) return context.spec
  if (context.classKey && context.specKey) return `${context.classKey} / ${context.specKey}`
  return '未带入职业与专精'
}

export function chickenbroScenarioLabel(context: ChickenbroContextValue): string {
  return context.scenario || '未带入场景'
}

export function chickenbroIntro(context: ChickenbroContextValue): string {
  const hasContext = Boolean(context.spec || context.classKey || context.specKey || context.scenario)
  return hasContext
    ? '已带入当前工作台上下文。我只解释后端返回的证据；资料不足时先说明缺口和下一步。'
    : '请描述职业、专精、场景和问题。我只解释后端证据，不会编造 DPS、排名、BiS 或来源。'
}

export function chickenbroVisibleTurns(messages: readonly ChatMessage[]): readonly ChickenbroTurn[] {
  const turns: ChickenbroTurn[] = []
  for (const message of messages) {
    if (message.role === 'user') {
      turns.push({ user: message })
      continue
    }
    if (message.role !== 'assistant') continue
    const pending = [...turns].reverse().find((turn) => !turn.assistant)
    if (pending) pending.assistant = message
  }
  return turns.slice(-2)
}

export function chickenbroLatestPayload(messages: readonly ChatMessage[]): AssistantPayload | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message?.role === 'assistant' && message.payload) return message.payload
  }
  return undefined
}

export function chickenbroAnswerSource(payload: AssistantPayload | undefined): string {
  if (!payload) return '等待后端回答'
  if (payload.answerSource === 'deterministic_fallback') return '后端通用建议'
  if (payload.answerSource === 'deterministic_scope_refusal') return '范围边界'
  return payload.basisLabel || payload.answerSource || '后端回答'
}

export function chickenbroConfidence(payload: AssistantPayload | undefined): string {
  if (!payload) return '未返回'
  const labels: Readonly<Record<string, string>> = {
    high: '高置信度', medium: '中置信度', low: '低置信度', blocked: '已阻断',
  }
  return labels[payload.confidence] ?? payload.confidence
}

export function chickenbroEvidenceRows(payload: AssistantPayload | undefined): readonly ChickenbroEvidenceRow[] {
  return Array.from({ length: 2 }, (_, index) => {
    const reference = payload?.evidenceRefs[index]
    return reference
      ? { id: `evidence-${index + 1}`, title: `证据引用 ${String(index + 1).padStart(2, '0')}`, detail: reference, state: 'ready' as const }
      : { id: `evidence-${index + 1}`, title: '等待后端证据', detail: '未返回 evidenceRef', state: 'blocked' as const }
  })
}

function boundaryItems(
  values: readonly string[] | undefined,
  labels: Readonly<Record<string, string>>,
  prefix: string,
): readonly ChickenbroBoundaryItem[] {
  return Array.from({ length: 3 }, (_, index) => {
    const value = values?.[index]
    return value
      ? { id: `${prefix}-${index + 1}`, label: displayCode(value, labels), state: 'ready' as const }
      : { id: `${prefix}-${index + 1}`, label: '未返回', state: 'unavailable' as const }
  })
}

export function chickenbroMissingInputs(payload: AssistantPayload | undefined): readonly ChickenbroBoundaryItem[] {
  return boundaryItems(payload?.missingInputs, missingInputLabels, 'missing')
}

export function chickenbroLimitations(payload: AssistantPayload | undefined): readonly ChickenbroBoundaryItem[] {
  return boundaryItems(payload?.limitations, limitationLabels, 'limitation')
}

export function chickenbroTopicPrompts(context: ChickenbroContextValue): readonly string[] {
  return chickenbroContextLabel(context) === '未带入职业与专精'
    ? [
        '帮我检查 SimC 前还缺什么证据',
        '如何整理可验证的天赋和装备上下文？',
        '解释后端返回证据的边界',
      ]
    : [
        '当前最大的证据阻断是什么？',
        '后端回答分别依据了哪些引用？',
        '下一步应该补什么输入？',
      ]
}

export function boundedChickenbroMessage(value: string): string {
  return value.trim().slice(0, 2000)
}

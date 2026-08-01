import type { ChatMessage } from '@wow-mini/domain'

export type ChickenbroInputState = 'idle' | 'loading' | 'ready' | 'error'

export function boundedChickenbroMessage(value: string): string {
  return value.trim().slice(0, 2000)
}

export function chickenbroTranscript(messages: readonly ChatMessage[]): readonly ChatMessage[] {
  return messages.filter((message) => message.role === 'user' || message.role === 'assistant')
}

export function chickenbroMarkMessageReceived(
  messages: readonly ChatMessage[],
  messageId: string,
): readonly ChatMessage[] {
  return messages.map((message) => (
    message.messageId === messageId ? { ...message, status: 'received' } : message
  ))
}

export function chickenbroAttachmentRefs(message: ChatMessage): readonly string[] {
  if (message.role !== 'assistant') return []
  return message.payload?.evidenceRefs ?? []
}

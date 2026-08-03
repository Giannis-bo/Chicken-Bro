import type { ChatMessage } from '@wow-mini/domain'

export type ChickenbroInputState = 'idle' | 'loading' | 'ready' | 'error'

export interface ChickenbroStreamState {
  requestId: string
  expectedSequence: number
  temporaryText: string
  active: boolean
  followLatest: boolean
  hasUnseen: boolean
}

export const CHICKENBRO_FOLLOW_DISTANCE_PX = 80

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

export function chickenbroStartStream(requestId: string): ChickenbroStreamState {
  return {
    requestId,
    expectedSequence: 1,
    temporaryText: '',
    active: true,
    followLatest: true,
    hasUnseen: false,
  }
}

export function chickenbroAppendStreamDelta(
  state: ChickenbroStreamState,
  requestId: string,
  sequence: number,
  text: string,
): { accepted: boolean; state: ChickenbroStreamState } {
  if (!state.active || state.requestId !== requestId || state.expectedSequence !== sequence || !text) {
    return { accepted: false, state }
  }
  return {
    accepted: true,
    state: {
      ...state,
      expectedSequence: sequence + 1,
      temporaryText: state.temporaryText + text,
    },
  }
}

export function chickenbroClearStream(state: ChickenbroStreamState): ChickenbroStreamState {
  return {
    ...state,
    requestId: '',
    temporaryText: '',
    active: false,
    expectedSequence: 1,
    hasUnseen: false,
  }
}

export function chickenbroFollowFromDistance(state: ChickenbroStreamState, distanceFromBottom: number): ChickenbroStreamState {
  const followLatest = distanceFromBottom <= CHICKENBRO_FOLLOW_DISTANCE_PX
  return { ...state, followLatest, hasUnseen: followLatest ? false : state.hasUnseen }
}

export function chickenbroNoteIncoming(state: ChickenbroStreamState): ChickenbroStreamState {
  return state.followLatest ? { ...state, hasUnseen: false } : { ...state, hasUnseen: true }
}

export function chickenbroResumeLatest(state: ChickenbroStreamState): ChickenbroStreamState {
  return { ...state, followLatest: true, hasUnseen: false }
}

import { createChatClient, type ChatClient } from './chat'
import { createSimcClient, type SimcClient } from './simc'
import { createTaroTransport, type ApiTransport, type TransportConfig } from './transport'
import { createWebAuthClient, type WebAuthClient } from './web-auth'

export interface WowApiClients {
  transport: ApiTransport
  chat: ChatClient
  simc: SimcClient
  webAuth: WebAuthClient
}

export type WowApiClientConfig = TransportConfig

export function createWowApiClients(config: WowApiClientConfig = {}): WowApiClients {
  const transport = createTaroTransport(config)
  return {
    transport,
    chat: createChatClient(transport),
    simc: createSimcClient(transport),
    webAuth: createWebAuthClient(transport),
  }
}

export const wowApi = createWowApiClients()

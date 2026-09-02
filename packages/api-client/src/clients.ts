import { AnalyticsEventsClient } from './analytics-events'
import { AuthClient } from './auth'
import { createBuildsClient, type BuildsClient } from './builds'
import { TimedCache } from './cache'
import { createChatClient, type ChatClient } from './chat'
import { createNewsClient, type NewsClient } from './news'
import { SimulatorClient } from './simulator'
import { taroStorage, type StorageAdapter } from './storage'
import { TemplateRepository } from './templates'
import { createTaroTransport, type ApiTransport, type TransportConfig } from './transport'
import { createWebsimClient, type WebsimClient } from './websim'
import { createWebAuthClient, type WebAuthClient } from './web-auth'
import { createPrototypeWebClient, type PrototypeWebClient } from './prototype-client'

export interface WowApiClients {
  transport: ApiTransport
  news: NewsClient
  builds: BuildsClient
  chat: ChatClient
  websim: WebsimClient
  simulator: SimulatorClient
  templates: TemplateRepository
  auth: AuthClient
  webAuth: WebAuthClient
  prototype: PrototypeWebClient
  analytics: AnalyticsEventsClient
  cache: TimedCache
}

export interface WowApiClientConfig extends TransportConfig {
  storage?: StorageAdapter
}

export function createWowApiClients(config: WowApiClientConfig = {}): WowApiClients {
  const storage = config.storage ?? taroStorage
  const transport = createTaroTransport({
    storage,
    ...(config.platform === undefined ? {} : { platform: config.platform }),
    ...(config.resolveBaseUrl === undefined ? {} : { resolveBaseUrl: config.resolveBaseUrl }),
    ...(config.resolveWebBaseUrl === undefined ? {} : { resolveWebBaseUrl: config.resolveWebBaseUrl }),
  })
  return {
    transport,
    news: createNewsClient(transport, storage),
    builds: createBuildsClient(transport),
    chat: createChatClient(transport),
    websim: createWebsimClient(transport),
    simulator: new SimulatorClient(transport, storage),
    templates: new TemplateRepository(transport, storage),
    auth: new AuthClient(transport, storage),
    webAuth: createWebAuthClient(transport),
    prototype: createPrototypeWebClient(transport),
    analytics: new AnalyticsEventsClient(transport, storage),
    cache: new TimedCache(),
  }
}

export const wowApi = createWowApiClients()

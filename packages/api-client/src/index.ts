export { clientAuthRequest } from './auth-context'
export { apiV2Path } from './api-v2-prefix'
export type { ClientAuthContext, ClientAuthRequest } from './auth-context'
export { createChatClient, CHAT_STREAM_TIMEOUT_MS } from './chat'
export type {
  ChatClient,
  ChatCreateRequest,
  ChatListRequest,
  ChatMessageRequest,
  ChatRequestOptions,
  ChatStreamOptions,
} from './chat'
export { createWowApiClients, wowApi } from './clients'
export type { WowApiClientConfig, WowApiClients } from './clients'
export { createSimcClient } from './simc'
export type {
  SimcClient,
  SimcJobMutationOptions,
  SimcRequestOptions,
  SimulationJobCreateRequest,
  SimulationJobListRequest,
  SimulationScenarioRequest,
  SourceSnapshotCreateRequest,
} from './simc'
export { taroStorage } from './storage'
export type { StorageAdapter } from './storage'
export {
  configuredApiBaseUrl,
  configuredWebAuthBaseUrl,
  createTaroTransport,
  DEV_API_BASE_URL,
  isInsecureHttpUrl,
  SseDecoder,
} from './transport'
export type {
  ApiResult,
  ApiStreamTask,
  ApiTransport,
  RequestBase,
  RequestCredentials,
  RequestData,
  RequestMethod,
  RequestOptions,
  SseStreamRequestOptions,
  TransportAuthContext,
  TransportConfig,
} from './transport'
export { createWebAuthClient, readWebCsrfCookie } from './web-auth'
export type { WebAuthClient } from './web-auth'

export { createAvatarClient } from './avatar'
export type { AvatarClient } from './avatar'
export * from './admin'

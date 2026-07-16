import type { EndpointId, RouteKey } from './route-contract'

export type ReadinessState =
  | 'loading'
  | 'empty'
  | 'error'
  | 'blocked'
  | 'partial'
  | 'ready'
  | 'stale'
  | 'source_reference'
  | 'unknown'

export type TrustLevel =
  | 'backend_verified'
  | 'source_referenced'
  | 'derived'
  | 'local_only'
  | 'unknown'
  | 'blocked'

export interface TrustDescriptor {
  level: TrustLevel
  sourceLabel?: string
  sourceUrl?: string
  reason?: string
}

export interface ApiResultLike<T> {
  payload: T
  fromFallback: boolean
  error: string
}

interface RouteStateBase {
  state: ReadinessState
  trust: TrustDescriptor
  updatedAt?: string
}

export type RouteDataState<T> =
  | (RouteStateBase & { state: 'loading'; previous?: T })
  | (RouteStateBase & { state: 'empty'; data?: never })
  | (RouteStateBase & { state: 'error'; error: string; previous?: T })
  | (RouteStateBase & { state: 'blocked'; reason: string; data?: never })
  | (RouteStateBase & { state: 'partial'; data: T; missing: readonly string[] })
  | (RouteStateBase & { state: 'ready'; data: T })
  | (RouteStateBase & { state: 'stale'; data: T; staleReason: string })
  | (RouteStateBase & { state: 'source_reference'; data: T; sourceUrl: string })
  | (RouteStateBase & { state: 'unknown'; reason: string; data?: T })

export type TaskStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'canceled'
  | 'unknown'

export interface SimulationTask {
  id: string
  status: TaskStatus
  createdAt?: string
  updatedAt?: string
  progress?: number
  error?: string
  trust: TrustDescriptor
}

export interface SimcSubmission {
  profileText: string
  scenario?: string
  iterations?: number
  templateId?: string
}

export type TemplateSourceClass =
  | 'local_draft'
  | 'account_synced'
  | 'raiderio_observed_profile'
  | 'backend_reference'
  | 'unknown'

export interface TemplateIdentity {
  id: string
  name: string
  type: string
  sourceClass: TemplateSourceClass
  sourceUrl?: string
  syncedAt?: string
  trust: TrustDescriptor
}

export interface VerifiedWowObjectReference {
  objectType: 'item' | 'spell' | 'talent' | 'class' | 'spec' | 'instance'
  objectId: string
  name?: string
  iconUrl?: string
  sourceUrl?: string
  verified: boolean
  trust: TrustDescriptor
}

export interface RouteRequestContext {
  routeKey: RouteKey
  endpoints: readonly EndpointId[]
  params: Readonly<Record<string, string | undefined>>
}

export interface NewsListParams {
  type?: string
  key?: string
  value?: string
}

export interface NewsDetailParams {
  id: string
}

export interface BuildParams {
  classId?: string
  specId?: string
  heroId?: string
}

export interface GearDetailParams extends BuildParams {
  id?: string
  query?: 'gear' | 'talents'
  slot?: string
}

export interface TaskDetailParams {
  id: string
  guestId?: string
}

export function fallbackTrust(reason: string): TrustDescriptor {
  return { level: 'unknown', reason }
}

export function isReadyState<T>(value: RouteDataState<T>): value is Extract<RouteDataState<T>, { state: 'ready' }> {
  return value.state === 'ready' && value.trust.level === 'backend_verified'
}

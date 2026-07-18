import type { ApiResultLike, RouteDataState, TrustDescriptor } from './models'

export interface StateMappingOptions<T> {
  isEmpty?: (payload: T) => boolean
  previous?: T
  fallbackReason?: string
  updatedAt?: string
}

export function trustForBackend(): TrustDescriptor {
  return { level: 'backend_verified' }
}

export function trustForLocal(reason = '仅保存在当前设备'): TrustDescriptor {
  return { level: 'local_only', reason }
}

export function trustForFallback(reason: string): TrustDescriptor {
  return { level: 'unknown', reason }
}

export function apiResultToRouteState<T>(
  result: ApiResultLike<T>,
  options: StateMappingOptions<T> = {},
): RouteDataState<T> {
  const updatedAt = options.updatedAt
  if (result.fromFallback) {
    const reason = result.error || options.fallbackReason || '后端数据不可用'
    if (options.previous !== undefined) {
      return {
        state: 'stale',
        data: options.previous,
        staleReason: reason,
        trust: trustForFallback(reason),
        ...(updatedAt === undefined ? {} : { updatedAt }),
      }
    }
    return {
      state: 'blocked',
      reason,
      trust: trustForFallback(reason),
      ...(updatedAt === undefined ? {} : { updatedAt }),
    }
  }
  if (options.isEmpty?.(result.payload)) {
    return {
      state: 'empty',
      trust: trustForBackend(),
      ...(updatedAt === undefined ? {} : { updatedAt }),
    }
  }
  return {
    state: 'ready',
    data: result.payload,
    trust: trustForBackend(),
    ...(updatedAt === undefined ? {} : { updatedAt }),
  }
}

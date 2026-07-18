import { isTabRoute, normalizeTabRoute } from './tab-bar-items'

type ActiveTabRouteListener = (pagePath: string) => void

export interface ActiveTabRouteStore {
  get(): string | null
  set(pagePath: string): boolean
  subscribe(listener: ActiveTabRouteListener): () => void
}

export function createActiveTabRouteStore(): ActiveTabRouteStore {
  let activeRoute: string | null = null
  const listeners = new Set<ActiveTabRouteListener>()

  return {
    get: () => activeRoute,
    set: (pagePath) => {
      const normalizedRoute = normalizeTabRoute(pagePath)
      if (!isTabRoute(normalizedRoute)) return false
      if (activeRoute === normalizedRoute) return true

      activeRoute = normalizedRoute
      listeners.forEach((listener) => listener(normalizedRoute))
      return true
    },
    subscribe: (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export const activeTabRouteStore = createActiveTabRouteStore()

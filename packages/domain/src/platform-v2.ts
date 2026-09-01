export type ComponentReadinessStatus = 'ready' | 'partial' | 'blocked' | 'unconfigured'

export interface ComponentReadiness {
  status: ComponentReadinessStatus
  code: string
}

export interface PlatformReadinessEnvelope {
  status: 'ready' | 'partial' | 'blocked'
  requestId: string
  components: Readonly<Record<string, ComponentReadiness>>
}


const OVERALL_STATUSES = new Set(['ready', 'partial', 'blocked'])
const COMPONENT_STATUSES = new Set(['ready', 'partial', 'blocked', 'unconfigured'])
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i


export function isPlatformReadinessEnvelope(value: unknown): value is PlatformReadinessEnvelope {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const root = value as Record<string, unknown>
  if (typeof root['status'] !== 'string' || !OVERALL_STATUSES.has(root['status'])) return false
  if (typeof root['requestId'] !== 'string' || !UUID_PATTERN.test(root['requestId'])) return false
  const components = root['components']
  if (typeof components !== 'object' || components === null || Array.isArray(components)) return false
  return Object.entries(components as Record<string, unknown>).every(([name, component]) => {
    if (!name || typeof component !== 'object' || component === null || Array.isArray(component)) return false
    const row = component as Record<string, unknown>
    return typeof row['status'] === 'string'
      && COMPONENT_STATUSES.has(row['status'])
      && typeof row['code'] === 'string'
  })
}

const defaultTrustedMediaHosts = [
  'wow.zamimg.com',
  'images.blz-contentstack.com',
  'bnetcmsus-a.akamaihd.net',
  'render.worldofwarcraft.com',
] as const

let trustedMediaHosts = new Set<string>(defaultTrustedMediaHosts)

function normalizeHost(host: string): string {
  return host.trim().toLowerCase().replace(/^\.+|\.+$/g, '')
}

export function configureTrustedMediaHosts(hosts: readonly string[]): void {
  trustedMediaHosts = new Set(hosts.map(normalizeHost).filter(Boolean))
}

export function resetTrustedMediaHosts(): void {
  trustedMediaHosts = new Set<string>(defaultTrustedMediaHosts)
}

export function currentTrustedMediaHosts(): readonly string[] {
  return [...trustedMediaHosts].sort()
}

export function isTrustedRuntimeMediaUrl(value: string | null | undefined): value is string {
  if (!value) return false
  try {
    const url = new URL(value)
    if (url.protocol !== 'https:' || url.username || url.password) return false
    const host = normalizeHost(url.hostname)
    return [...trustedMediaHosts].some((allowed) => host === allowed || host.endsWith(`.${allowed}`))
  } catch {
    return false
  }
}

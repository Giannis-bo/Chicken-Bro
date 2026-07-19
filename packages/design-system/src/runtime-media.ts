import {
  normalizeHost,
  normalizeRuntimeMediaRoot,
  parseTrustedMediaSource,
  runtimeMediaRootHost,
  runtimeMediaObjectPath,
} from './runtime-media-path.cjs'

const defaultTrustedMediaHosts = [
  'wow.zamimg.com',
  'images.blz-contentstack.com',
  'bnetcmsus-a.akamaihd.net',
  'render.worldofwarcraft.com',
] as const

let trustedMediaHosts = new Set<string>(defaultTrustedMediaHosts)
let runtimeMediaRoot = ''

export function configureTrustedMediaHosts(hosts: readonly string[]): void {
  trustedMediaHosts = new Set(hosts.map(normalizeHost).filter(Boolean))
}

export function resetTrustedMediaHosts(): void {
  trustedMediaHosts = new Set<string>(defaultTrustedMediaHosts)
}

export function configureRuntimeMediaRoot(root: string): void {
  runtimeMediaRoot = normalizeRuntimeMediaRoot(root)
}

export function resetRuntimeMediaRoot(): void {
  runtimeMediaRoot = ''
}

export function currentRuntimeMediaRoot(): string {
  return runtimeMediaRoot
}

export function currentTrustedMediaHosts(): readonly string[] {
  return [...trustedMediaHosts].sort()
}

export function isTrustedRuntimeMediaUrl(value: string | null | undefined): value is string {
  if (runtimeMediaRoot && value?.startsWith(`${runtimeMediaRoot}/`)) {
    return Boolean(parseTrustedMediaSource(value, [runtimeMediaRootHost(runtimeMediaRoot)]))
  }
  return Boolean(parseTrustedMediaSource(value, trustedMediaHosts))
}

export function resolveRuntimeMediaUrl(value: string | null | undefined): string {
  if (!value) return ''
  if (runtimeMediaRoot && value.startsWith(`${runtimeMediaRoot}/`)) {
    return isTrustedRuntimeMediaUrl(value) ? value : ''
  }
  const source = parseTrustedMediaSource(value, trustedMediaHosts)
  if (!source) return ''
  if (!runtimeMediaRoot) return source.url
  const objectPath = runtimeMediaObjectPath(value, trustedMediaHosts)
  return objectPath ? `${runtimeMediaRoot}/${objectPath}` : ''
}

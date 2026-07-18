export interface TrustedMediaSource {
  host: string
  pathname: string
  url: string
}

export function normalizeHost(host: string): string
export function normalizeRuntimeMediaRoot(value: string): string
export function parseTrustedMediaSource(value: string | null | undefined, hosts: Iterable<string>): TrustedMediaSource | null
export function runtimeMediaRootHost(value: string): string
export function runtimeMediaObjectPath(value: string | null | undefined, hosts: Iterable<string>): string

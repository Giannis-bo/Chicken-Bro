'use strict'

const immutableReleaseRootPattern = /^https:\/\/[^/?#\s]+(?:\/[^?#\s]*)?\/releases\/[a-z0-9][a-z0-9._-]{7,}\/?$/iu
const supportedImagePathPattern = /\.(?:jpe?g|png|webp)$/iu
const httpsUrlPattern = /^https:\/\/([^/?#\s]+)(\/[^?#\s]*)?$/iu
const hostnamePattern = /^(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?)$/u

function normalizeHost(host) {
  return String(host ?? '').trim().toLowerCase().replace(/^\.+|\.+$/gu, '')
}

function normalizeRuntimeMediaRoot(value) {
  const root = String(value ?? '').trim()
  if (!root) return ''
  if (!immutableReleaseRootPattern.test(root)) {
    throw new Error(`Runtime media root must use an immutable /releases/<release-id> HTTPS path: ${root}`)
  }
  return root.replace(/\/+$/gu, '')
}

function runtimeMediaRootHost(value) {
  const root = normalizeRuntimeMediaRoot(value)
  if (!root) return ''
  const match = httpsUrlPattern.exec(root)
  if (!match) return ''
  return normalizeHost(match[1])
}

function parseTrustedMediaSource(value, hosts) {
  if (!value) return null
  const match = httpsUrlPattern.exec(String(value).trim())
  if (!match) return null
  const authority = match[1] ?? ''
  if (authority.includes('@') || authority.includes(':')) return null
  const host = normalizeHost(authority)
  if (
    !host
    || !hostnamePattern.test(host)
    || host.includes('..')
    || host.split('.').some((label) => label.startsWith('-') || label.endsWith('-'))
  ) return null
  const pathname = match[2] || '/'
  const trustedHosts = [...hosts].map(normalizeHost).filter(Boolean)
  if (!trustedHosts.some((allowed) => host === allowed || host.endsWith(`.${allowed}`))) return null
  if (!supportedImagePathPattern.test(pathname)) return null
  if (/\\|%(?:2e|2f|5c)/iu.test(pathname) || /\/(?:\.{1,2})(?:\/|$)/u.test(pathname)) return null
  return { host, pathname, url: `https://${host}${pathname}` }
}

function runtimeMediaObjectPath(value, hosts) {
  const source = parseTrustedMediaSource(value, hosts)
  if (!source) return ''
  return `sources/${source.host}${source.pathname}`
}

module.exports = {
  normalizeHost,
  normalizeRuntimeMediaRoot,
  parseTrustedMediaSource,
  runtimeMediaRootHost,
  runtimeMediaObjectPath,
}

'use strict'

const immutableRemoteAssetRootPattern = /^https:\/\/[^/?#\s]+(?:\/[^?#\s]*)?\/releases\/[a-z0-9][a-z0-9._-]{7,}\/?$/iu

function isImmutableRemoteAssetRoot(value) {
  return immutableRemoteAssetRootPattern.test(value.trim())
}

function normalizeAssetRuntimeRoot(root) {
  const value = root.trim()
  if (!value || value === '/') return ''
  if (value === '.') return '.'
  if (/^https:\/\//iu.test(value)) {
    if (!isImmutableRemoteAssetRoot(value)) {
      throw new Error(`Remote asset runtime root must use an immutable /releases/<release-id> HTTPS path: ${value}`)
    }
    return value.replace(/\/+$/g, '')
  }
  if (/^[a-z][a-z\d+.-]*:\/\//iu.test(value)) {
    throw new Error(`Asset runtime root must use HTTPS: ${value}`)
  }
  return `/${value.replace(/^\/+|\/+$/g, '')}`
}

module.exports = { isImmutableRemoteAssetRoot, normalizeAssetRuntimeRoot }

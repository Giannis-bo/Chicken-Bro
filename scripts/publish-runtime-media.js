#!/usr/bin/env node
'use strict'

const { createHash } = require('node:crypto')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const {
  parseTrustedMediaSource,
  runtimeMediaObjectPath,
} = require('../packages/design-system/src/runtime-media-path.cjs')

const root = path.resolve(__dirname, '..')
const bucket = process.env.WOW_CDN_COS_BUCKET || 'zhajiduizhang-1257807175'
const region = process.env.WOW_CDN_COS_REGION || 'ap-shanghai'
const publicOrigin = process.env.WOW_CDN_PUBLIC_ORIGIN || 'https://static.chickenbro.cloud'
const apiBaseUrl = process.env.WOW_RUNTIME_MEDIA_API_BASE_URL || 'https://api.chickenbro.cloud'
const seedFile = process.env.WOW_RUNTIME_MEDIA_SEED_FILE || ''
const skipGearDiscovery = process.env.WOW_RUNTIME_MEDIA_SKIP_GEAR_DISCOVERY === '1'
const releasePrefix = 'wow-media/releases'
const trustedSourceHosts = ['wow.zamimg.com', 'render.worldofwarcraft.com']
const apiConcurrency = 4
const downloadConcurrency = 12
const verificationConcurrency = 12
const requestTimeoutMs = 30_000
const apiRequestTimeoutMs = 180_000
const maximumAttempts = 3
const maximumFiles = 12_000
const maximumFileBytes = 512 * 1024
const maximumTotalBytes = 128 * 1024 * 1024
const allowedContentTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const explicitSourceFallbacks = new Map([
  [
    'https://wow.zamimg.com/images/wow/icons/large/ability_demonhunter_specdevourer.jpg',
    'https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter_void.jpg',
  ],
])

function usage() {
  throw new Error('usage: node scripts/publish-runtime-media.js <prepare|publish|verify> <release-id>')
}

function validateReleaseId(value) {
  if (!/^[a-z0-9][a-z0-9._-]{7,63}$/u.test(value ?? '')) {
    throw new Error('release-id must be 8-64 lowercase URL-safe characters')
  }
  return value
}

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex')
}

function collectIconUrls(value, found = new Set(), invalid = []) {
  if (Array.isArray(value)) {
    for (const item of value) collectIconUrls(item, found, invalid)
    return { found, invalid }
  }
  if (!value || typeof value !== 'object') return { found, invalid }
  for (const [key, item] of Object.entries(value)) {
    if (/^(?:iconUrl|classIconUrl|specIconUrl)$/u.test(key) && typeof item === 'string' && item.trim()) {
      const source = parseTrustedMediaSource(item, trustedSourceHosts)
      if (source) found.add(source.url)
      else invalid.push({ key, value: item.slice(0, 400) })
    }
    collectIconUrls(item, found, invalid)
  }
  return { found, invalid }
}

function discoverSelections(home, bootstrap) {
  const selections = new Map()
  const add = (classKey, specKey) => {
    if (!classKey || !specKey) return
    selections.set(`${classKey}:${specKey}`, { classKey, specKey })
  }
  for (const item of home?.classOptions ?? []) {
    const classKey = item.websimClassKey || item.classKey || item.key
    for (const spec of item.specializations ?? item.specs ?? []) {
      add(classKey, spec.websimSpecKey || spec.specKey || spec.key)
    }
  }
  for (const item of bootstrap?.classes ?? []) {
    const classKey = item.key || item.classKey
    for (const spec of item.specs ?? []) add(classKey, spec.key || spec.specKey)
  }
  return [...selections.values()].sort((left, right) => (
    `${left.classKey}:${left.specKey}`.localeCompare(`${right.classKey}:${right.specKey}`)
  ))
}

async function fetchWithRetry(url, label, timeoutMs = requestTimeoutMs) {
  let lastFailure = 'unknown failure'
  for (let attempt = 1; attempt <= maximumAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        cache: 'no-store',
        headers: { 'user-agent': 'wow-mini-runtime-media-publisher/1' },
        signal: AbortSignal.timeout(timeoutMs),
      })
      if (response.ok) return response
      lastFailure = `HTTP ${response.status}`
    } catch (error) {
      lastFailure = error instanceof Error ? error.message : String(error)
    }
  }
  throw new Error(`${label} failed after ${maximumAttempts} attempts: ${lastFailure}`)
}

async function fetchJson(relativePath) {
  const url = `${apiBaseUrl.replace(/\/+$/u, '')}${relativePath}`
  const response = await fetchWithRetry(url, `API request ${relativePath}`, apiRequestTimeoutMs)
  return response.json()
}

async function mapConcurrent(items, concurrency, worker) {
  const results = new Array(items.length)
  let nextIndex = 0
  const run = async () => {
    while (nextIndex < items.length) {
      const index = nextIndex
      nextIndex += 1
      results[index] = await worker(items[index], index)
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, run))
  return results
}

async function discoverCatalog() {
  const [home, bootstrap, intel] = await Promise.all([
    fetchJson('/api/builds/home'),
    fetchJson('/api/websim/bootstrap'),
    fetchJson('/api/builds/intel'),
  ])
  const selections = discoverSelections(home, bootstrap)
  if (!selections.length) throw new Error('runtime media discovery returned no class/spec selections')
  const payloads = [home, bootstrap, intel]
  const selectionPayloads = await mapConcurrent(selections, apiConcurrency, async ({ classKey, specKey }) => {
    const query = `class=${encodeURIComponent(classKey)}&spec=${encodeURIComponent(specKey)}`
    return Promise.all([
      fetchJson(`/api/websim/talents?${query}`),
      ...(skipGearDiscovery ? [] : [fetchJson(`/api/websim/gear?${query}&compact=1`)]),
    ])
  })
  for (const pair of selectionPayloads) payloads.push(...pair)
  const found = new Set()
  const invalid = []
  for (const payload of payloads) collectIconUrls(payload, found, invalid)
  const requiredUrls = new Set(found)
  if (seedFile) {
    const seedPayload = JSON.parse(fs.readFileSync(path.resolve(seedFile), 'utf8'))
    const seedUrls = Array.isArray(seedPayload) ? seedPayload : seedPayload?.urls
    if (!Array.isArray(seedUrls)) throw new Error('WOW_RUNTIME_MEDIA_SEED_FILE must contain a JSON array or { urls: [] }')
    for (const value of seedUrls) {
      const source = parseTrustedMediaSource(value, trustedSourceHosts)
      if (source) found.add(source.url)
      else if (/^[a-z][a-z\d+.-]*:\/\//iu.test(String(value))) {
        invalid.push({ key: 'seedUrl', value: String(value).slice(0, 400) })
      }
    }
  } else if (skipGearDiscovery) {
    throw new Error('WOW_RUNTIME_MEDIA_SKIP_GEAR_DISCOVERY=1 requires WOW_RUNTIME_MEDIA_SEED_FILE')
  }
  if (invalid.length) {
    throw new Error(`runtime media discovery found ${invalid.length} untrusted icon URLs: ${JSON.stringify(invalid.slice(0, 5))}`)
  }
  const sourceUrls = [...found].sort()
  if (!sourceUrls.length || sourceUrls.length > maximumFiles) {
    throw new Error(`runtime media file count is outside bounds: ${sourceUrls.length}/${maximumFiles}`)
  }
  return {
    selections,
    sources: sourceUrls.map((sourceUrl) => ({ sourceUrl, required: requiredUrls.has(sourceUrl) })),
  }
}

function runtimeMediaFallbackCandidates(sourceUrl) {
  const candidates = []
  const explicit = explicitSourceFallbacks.get(sourceUrl)
  if (explicit) candidates.push(explicit)
  const source = parseTrustedMediaSource(sourceUrl, trustedSourceHosts)
  const wowheadPrefix = '/images/wow/icons/large/'
  if (source?.host === 'wow.zamimg.com' && source.pathname.startsWith(wowheadPrefix)) {
    candidates.push(`https://render.worldofwarcraft.com/us/icons/56/${path.posix.basename(source.pathname)}`)
  }
  return [...new Set(candidates)].filter((candidate) => candidate !== sourceUrl)
}

async function fetchMediaBytes(sourceUrl) {
  const response = await fetchWithRetry(sourceUrl, `media request ${sourceUrl}`)
  const contentType = String(response.headers.get('content-type') ?? '').split(';', 1)[0].trim().toLowerCase()
  if (!allowedContentTypes.has(contentType)) throw new Error(`unsupported media content type ${contentType}: ${sourceUrl}`)
  const bytes = Buffer.from(await response.arrayBuffer())
  if (!bytes.length || bytes.length > maximumFileBytes) {
    throw new Error(`runtime media object exceeds byte bounds ${bytes.length}/${maximumFileBytes}: ${sourceUrl}`)
  }
  return { bytes, contentType }
}

async function downloadRecord(sourceUrl) {
  const objectPath = runtimeMediaObjectPath(sourceUrl, trustedSourceHosts)
  if (!objectPath) throw new Error(`untrusted runtime media source: ${sourceUrl}`)
  const candidates = [sourceUrl, ...runtimeMediaFallbackCandidates(sourceUrl)]
  let lastFailure = ''
  for (const candidate of candidates) {
    try {
      const { bytes, contentType } = await fetchMediaBytes(candidate)
      return {
        path: objectPath,
        sourceUrl,
        ...(candidate !== sourceUrl ? { resolvedSourceUrl: candidate } : {}),
        contentType,
        bytes,
        size: bytes.length,
        sha256: sha256(bytes),
      }
    } catch (error) {
      lastFailure = error instanceof Error ? error.message : String(error)
    }
  }
  throw new Error(`${lastFailure}; fallbacks exhausted for ${sourceUrl}`)
}

async function buildRelease(releaseId) {
  const { selections, sources } = await discoverCatalog()
  const failures = []
  const requiredFailures = []
  const downloaded = await mapConcurrent(sources, downloadConcurrency, async ({ sourceUrl, required }) => {
    try {
      return await downloadRecord(sourceUrl)
    } catch (error) {
      const failure = { sourceUrl, error: error instanceof Error ? error.message : String(error) }
      if (required) requiredFailures.push(failure)
      else failures.push(failure)
      return null
    }
  })
  if (requiredFailures.length) {
    throw new Error(`current API contains ${requiredFailures.length} unavailable runtime media sources: ${JSON.stringify(requiredFailures.slice(0, 20))}`)
  }
  const records = downloaded.filter(Boolean)
  const totalBytes = records.reduce((sum, record) => sum + record.size, 0)
  if (totalBytes > maximumTotalBytes) throw new Error(`runtime media release byte cap exceeded: ${totalBytes}/${maximumTotalBytes}`)
  const stagingRoot = fs.mkdtempSync(path.join(os.tmpdir(), `wow-runtime-media-${releaseId}-`))
  try {
    for (const record of records) {
      const destination = path.join(stagingRoot, ...record.path.split('/'))
      fs.mkdirSync(path.dirname(destination), { recursive: true })
      fs.writeFileSync(destination, record.bytes, { flag: 'wx' })
    }
    const manifest = {
      schemaVersion: 1,
      releaseId,
      immutableRoot: `${publicOrigin}/${releasePrefix}/${releaseId}`,
      sourceApi: apiBaseUrl,
      catalogMode: skipGearDiscovery ? 'postgres-seed-plus-api-talents' : 'api-complete',
      selectionCount: selections.length,
      selections,
      fileCount: records.length,
      totalBytes,
      skippedOptionalSourceCount: failures.length,
      skippedOptionalSources: failures.slice(0, 100),
      files: records.map(({ path: filePath, sourceUrl, resolvedSourceUrl, contentType, size, sha256: hash }) => ({
        path: filePath, sourceUrl, ...(resolvedSourceUrl ? { resolvedSourceUrl } : {}), contentType, bytes: size, sha256: hash,
      })),
    }
    fs.writeFileSync(path.join(stagingRoot, 'release-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' })
    return { stagingRoot, manifest }
  } catch (error) {
    fs.rmSync(stagingRoot, { recursive: true, force: true })
    throw error
  }
}

function validateRemoteManifest(manifest, releaseId) {
  if (!manifest || manifest.schemaVersion !== 1 || manifest.releaseId !== releaseId) throw new Error('invalid runtime media release manifest identity')
  if (!Array.isArray(manifest.files) || manifest.files.length !== manifest.fileCount || !manifest.files.length) throw new Error('invalid runtime media release manifest file count')
  if (manifest.files.length > maximumFiles) throw new Error('runtime media release manifest exceeds file cap')
  const totalBytes = manifest.files.reduce((sum, record) => sum + Number(record.bytes || 0), 0)
  if (totalBytes !== manifest.totalBytes || totalBytes > maximumTotalBytes) throw new Error('invalid runtime media release manifest byte total')
  for (const record of manifest.files) {
    if (!/^sources\/[a-z0-9.-]+\//u.test(record.path) || !/^[a-f0-9]{64}$/u.test(record.sha256)) {
      throw new Error(`invalid runtime media release record: ${JSON.stringify(record).slice(0, 300)}`)
    }
  }
  return manifest
}

async function verifyRelease(releaseId, expectedManifest) {
  const releaseRoot = `${publicOrigin}/${releasePrefix}/${releaseId}`
  const response = await fetchWithRetry(`${releaseRoot}/release-manifest.json`, 'runtime media manifest request')
  const remoteManifest = validateRemoteManifest(await response.json(), releaseId)
  if (expectedManifest && sha256(Buffer.from(JSON.stringify(remoteManifest))) !== sha256(Buffer.from(JSON.stringify(expectedManifest)))) {
    throw new Error('remote runtime media manifest does not match the locally published release')
  }
  await mapConcurrent(remoteManifest.files, verificationConcurrency, async (record) => {
    const assetResponse = await fetchWithRetry(`${releaseRoot}/${record.path}`, `runtime media CDN request ${record.path}`)
    const bytes = Buffer.from(await assetResponse.arrayBuffer())
    if (bytes.length !== record.bytes || sha256(bytes) !== record.sha256) throw new Error(`runtime media CDN integrity mismatch: ${record.path}`)
  })
  return {
    status: 'pass', releaseId, publicRoot: remoteManifest.immutableRoot,
    selectionCount: remoteManifest.selectionCount, fileCount: remoteManifest.fileCount,
    totalBytes: remoteManifest.totalBytes,
  }
}

async function main() {
  const command = process.argv[2]
  const releaseId = validateReleaseId(process.argv[3])
  if (!['prepare', 'publish', 'verify'].includes(command)) usage()
  if (command === 'verify') {
    console.log(JSON.stringify(await verifyRelease(releaseId), null, 2))
    return
  }
  const release = await buildRelease(releaseId)
  if (command === 'prepare') {
    console.log(JSON.stringify({
      status: 'prepared', releaseId, stagingRoot: release.stagingRoot,
      publicRoot: release.manifest.immutableRoot, selectionCount: release.manifest.selectionCount,
      fileCount: release.manifest.fileCount, totalBytes: release.manifest.totalBytes,
    }, null, 2))
    return
  }
  const probe = spawnSync('coscli', ['--version'], { encoding: 'utf8' })
  if (probe.error?.code === 'ENOENT') throw new Error('coscli is required for publish; configure it outside the repository, then retry')
  if (probe.status !== 0) throw new Error(`coscli is unavailable: ${(probe.stderr || probe.stdout || '').trim()}`)
  try {
    const target = `cos://${bucket}/${releasePrefix}/${releaseId}/`
    const upload = spawnSync('coscli', ['cp', '-r', `${release.stagingRoot}/`, target, '--region', region], {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
    })
    if (upload.status !== 0) throw new Error(`COS upload failed: ${(upload.stderr || upload.stdout || '').trim().slice(-2000)}`)
    console.log(JSON.stringify(await verifyRelease(releaseId, release.manifest), null, 2))
  } finally {
    fs.rmSync(release.stagingRoot, { recursive: true, force: true })
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error.message)
    process.exitCode = 1
  })
}

module.exports = {
  collectIconUrls,
  discoverSelections,
  runtimeMediaFallbackCandidates,
  validateReleaseId,
  validateRemoteManifest,
}

'use strict'

// No credentials or cloud mutations: prepare a bounded upload or verify public CDN bytes.
const fs = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const { createHash } = require('node:crypto')
const { execFileSync } = require('node:child_process')
const root = path.resolve(__dirname, '..')
const cdn = require('../apps/mini-taro/src/web/web-theme-cdn.json')
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const cacheControl = 'public,max-age=31536000,immutable'

function collect() {
  if (!/^https:\/\/static\.chickenbro\.cloud\/wow-assets\/releases\/[a-z0-9][a-z0-9-]+$/u.test(cdn.root)) {
    throw new Error('Expected an immutable release on the approved CDN origin')
  }
  const files = Object.entries(cdn.images).map(([id, name]) => {
    if (!/^[a-z0-9-]+\.png$/u.test(name)) throw new Error('Invalid image filename')
    const source = `apps/mini-taro/src/web/assets/${id === 'horde' ? '' : 'themes/'}${name}`
    const bytes = fs.readFileSync(path.join(root, source))
    return { id, name, source, bytes: bytes.length, sha256: hash(bytes) }
  })
  if (files.length !== 7 || new Set(files.map(file => file.name)).size !== 7) throw new Error('Expected exactly seven unique images')
  const totalBytes = files.reduce((sum, file) => sum + file.bytes, 0)
  if (totalBytes > 16 * 1024 * 1024) throw new Error('Release exceeds 16 MiB')
  return { schemaVersion: 1, root: cdn.root, bucket: 'zhajiduizhang-1257807175', region: 'ap-shanghai', cacheControl, totalBytes, files }
}

function readPublic(url, head = false) {
  // curl uses the system trust store; response bytes stay in memory.
  return execFileSync('curl', ['--fail', '--silent', '--show-error', '--max-time', '45', ...(head ? ['--head'] : []), url], { maxBuffer: 20 * 1024 * 1024 })
}

function main(command) {
  const manifest = collect()
  if (command === 'prepare') {
    const stagingRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'chickenbro-web-themes-'))
    for (const file of manifest.files) fs.copyFileSync(path.join(root, file.source), path.join(stagingRoot, file.name), fs.constants.COPYFILE_EXCL)
    fs.writeFileSync(path.join(stagingRoot, 'release-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' })
    return { stagingRoot, ...manifest }
  }
  if (command === 'verify') {
    const published = JSON.parse(readPublic(`${cdn.root}/release-manifest.json`).toString())
    if (JSON.stringify(published) !== JSON.stringify(manifest)) throw new Error('Published manifest differs from local source')
    const verified = []
    for (const file of manifest.files) {
      const url = `${cdn.root}/${file.name}`
      const bytes = readPublic(url)
      if (bytes.length !== file.bytes || hash(bytes) !== file.sha256) throw new Error(`Integrity mismatch: ${file.name}`)
      const headers = readPublic(url, true).toString()
      const cache = headers.match(/^cache-control:\s*([^\r\n]+)/imu)?.[1] ?? ''
      if (!/^content-type:\s*image\/png\s*$/imu.test(headers)
        || !cache.split(',').map(value => value.trim()).includes('max-age=31536000')
        || !cache.split(',').map(value => value.trim()).includes('immutable')) throw new Error(`Missing image type or immutable cache policy: ${file.name}`)
      verified.push({ name: file.name, bytes: file.bytes, sha256: file.sha256 })
    }
    return { status: 'cdn_bytes_verified', checkedAt: new Date().toISOString(), root: cdn.root, cacheControl, verified }
  }
  throw new Error('Usage: node scripts/prepare-web-theme-cdn.cjs <prepare|verify>')
}

if (require.main === module) {
  try { console.log(JSON.stringify(main(process.argv[2]), null, 2)) }
  catch (error) { console.error(error.message); process.exitCode = 1 }
}
module.exports = { collect }

#!/usr/bin/env node
'use strict'

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const repositoryRoot = path.resolve(__dirname, '..')
const vectorRoot = path.join(repositoryRoot, 'packages/design-system/assets/vector')
const runtimeRoot = path.join(repositoryRoot, 'packages/design-system/assets/vector-runtime')
const manifest = require(path.join(vectorRoot, 'manifest.json'))
const runtimeColor = '#d8c7a4'
const runtimeSize = '96x96'
const maximumPngBytes = 256 * 1024

function runtimeRelativePath(filePath) {
  const source = path.resolve(repositoryRoot, filePath)
  const relative = path.relative(vectorRoot, source)
  if (!relative || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative) || path.extname(relative) !== '.svg') {
    throw new Error(`Vector asset is outside the registered SVG root: ${filePath}`)
  }
  return relative.replace(/\.svg$/u, '.png')
}

function renderPng(source, temporaryRoot, index) {
  const svg = fs.readFileSync(source, 'utf8').replaceAll('currentColor', runtimeColor)
  const temporarySvg = path.join(temporaryRoot, `${index}.svg`)
  const temporaryPng = path.join(temporaryRoot, `${index}.png`)
  fs.writeFileSync(temporarySvg, svg, { flag: 'wx' })
  const result = spawnSync('sips', [
    '-s', 'format', 'png',
    '-z', '96', '96',
    temporarySvg,
    '--out', temporaryPng,
  ], { encoding: 'utf8' })
  if (result.error) throw result.error
  if (result.status !== 0 || !fs.existsSync(temporaryPng)) {
    throw new Error(`sips failed for ${source}: ${String(result.stderr || result.stdout).slice(-1000)}`)
  }
  const png = fs.readFileSync(temporaryPng)
  if (png.length > maximumPngBytes) {
    throw new Error(`Derived vector PNG exceeds byte cap: ${source} (${png.length})`)
  }
  return png
}

function generate() {
  const assets = manifest.assets
  if (!Array.isArray(assets) || assets.length === 0) throw new Error('Vector manifest has no assets')
  fs.rmSync(runtimeRoot, { recursive: true, force: true })
  fs.mkdirSync(runtimeRoot, { recursive: true })
  const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-vector-runtime-'))

  let totalBytes = 0
  try {
    for (const [index, asset] of assets.entries()) {
      const source = path.resolve(repositoryRoot, asset.filePath)
      const destination = path.join(runtimeRoot, runtimeRelativePath(asset.filePath))
      const png = renderPng(source, temporaryRoot, index)
      fs.mkdirSync(path.dirname(destination), { recursive: true })
      fs.writeFileSync(destination, png, { flag: 'wx' })
      totalBytes += png.length
    }
  } finally {
    fs.rmSync(temporaryRoot, { recursive: true, force: true })
  }
  fs.copyFileSync(
    path.join(vectorRoot, 'LUCIDE-LICENSE.txt'),
    path.join(runtimeRoot, 'LUCIDE-LICENSE.txt'),
    fs.constants.COPYFILE_EXCL,
  )
  process.stdout.write(`${JSON.stringify({
    status: 'pass',
    assetCount: assets.length,
    runtimeColor,
    runtimeSize,
    totalBytes,
  })}\n`)
}

if (require.main === module) {
  try {
    generate()
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`)
    process.exit(1)
  }
}

module.exports = { generate, runtimeRelativePath }

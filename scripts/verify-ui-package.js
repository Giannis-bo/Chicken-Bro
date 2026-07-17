#!/usr/bin/env node
'use strict'

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const appRoot = path.join(root, 'apps/mini-taro')
const auditRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-mini-package-'))
const limits = {
  remoteTotalBytes: 2 * 1024 * 1024,
  commonJsBytes: 420 * 1024,
  commonWxssBytes: 400 * 1024,
}

function walk(directory) {
  if (!fs.existsSync(directory)) return []
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name)
    return entry.isDirectory() ? walk(target) : [target]
  })
}

function build(name, assetRuntimeRoot = '') {
  const outputRoot = path.join(auditRoot, name)
  const result = spawnSync(path.join(root, 'node_modules/.bin/taro'), ['build', '--type', 'weapp'], {
    cwd: appRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      NODE_ENV: 'production',
      WOW_TARO_ISOLATED_BUILD: '1',
      WOW_TARO_OUTPUT_ROOT: outputRoot,
      WOW_ASSET_RUNTIME_ROOT: assetRuntimeRoot,
    },
    maxBuffer: 2 * 1024 * 1024,
  })
  if (result.status !== 0) {
    const diagnostic = `${result.stderr || ''}\n${result.stdout || ''}`.trim().slice(-4000)
    throw new Error(`${name} production build failed\n${diagnostic}`)
  }
  const files = walk(outputRoot).filter((file) => !file.endsWith('.map'))
  return {
    outputRoot,
    totalBytes: files.reduce((total, file) => total + fs.statSync(file).size, 0),
    assetFileCount: files.filter((file) => file.startsWith(path.join(outputRoot, 'assets') + path.sep)).length,
    commonJsBytes: fs.statSync(path.join(outputRoot, 'common.js')).size,
    commonWxssBytes: fs.statSync(path.join(outputRoot, 'common.wxss')).size,
  }
}

try {
  const local = build('local')
  const remote = build('remote', 'https://assets.example.invalid/ui-v2')
  const failures = []
  if (remote.assetFileCount !== 0) failures.push(`remote build copied ${remote.assetFileCount} local asset files`)
  if (remote.totalBytes > limits.remoteTotalBytes) failures.push(`remote build is ${remote.totalBytes} bytes`)
  if (remote.commonJsBytes > limits.commonJsBytes) failures.push(`common.js is ${remote.commonJsBytes} bytes`)
  if (remote.commonWxssBytes > limits.commonWxssBytes) failures.push(`common.wxss is ${remote.commonWxssBytes} bytes`)
  console.log(JSON.stringify({
    status: failures.length ? 'fail' : 'pass',
    evidence: 'isolated_production_weapp_package',
    limits,
    local: { ...local, outputRoot: '<temporary>' },
    remote: { ...remote, outputRoot: '<temporary>' },
    failures,
  }, null, 2))
  if (failures.length) process.exitCode = 1
} finally {
  fs.rmSync(auditRoot, { recursive: true, force: true })
}

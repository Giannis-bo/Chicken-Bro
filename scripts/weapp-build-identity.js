#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const schemaRevision = 'wow-weapp-build-v1'
const identityFileName = 'wow-build.json'
const sourceInputs = [
  'apps/mini-taro/config',
  'apps/mini-taro/src',
  'apps/mini-taro/package.json',
  'packages/api-client/src',
  'packages/api-client/package.json',
  'packages/design-system/assets',
  'packages/design-system/src',
  'packages/design-system/package.json',
  'packages/domain/src',
  'packages/domain/package.json',
  'package-lock.json',
]

function relativePath(root, target) {
  return path.relative(root, target).split(path.sep).join('/')
}

function sourceFiles(root) {
  const files = []
  const visit = (target) => {
    const stat = fs.lstatSync(target)
    if (stat.isSymbolicLink()) {
      throw new Error(`WeChat source identity cannot follow symbolic links: ${target}`)
    }
    if (stat.isFile()) {
      files.push(target)
      return
    }
    if (!stat.isDirectory()) {
      throw new Error(`Unsupported WeChat source identity input: ${target}`)
    }
    for (const entry of fs.readdirSync(target).sort()) {
      visit(path.join(target, entry))
    }
  }
  for (const input of sourceInputs) {
    const target = path.join(root, input)
    if (fs.existsSync(target)) visit(target)
  }
  return files.sort((left, right) => relativePath(root, left).localeCompare(relativePath(root, right)))
}

function computeWeappSourceHash(root) {
  const hash = crypto.createHash('sha256')
  for (const file of sourceFiles(root)) {
    hash.update(relativePath(root, file))
    hash.update('\0')
    hash.update(fs.readFileSync(file))
    hash.update('\0')
  }
  return `sha256:${hash.digest('hex')}`
}

function currentGitHead(root) {
  const result = spawnSync('git', ['-C', root, 'rev-parse', 'HEAD'], { encoding: 'utf8' })
  if (result.status !== 0) {
    throw new Error(`Cannot resolve Git HEAD for WeChat build identity: ${String(result.stderr || '').trim()}`)
  }
  const head = String(result.stdout || '').trim()
  if (!/^[0-9a-f]{40}$/u.test(head)) {
    throw new Error(`Invalid Git HEAD for WeChat build identity: ${head || 'missing'}`)
  }
  return head
}

function createWeappBuildIdentity(root, options = {}) {
  const gitHead = String(options.gitHead || currentGitHead(root)).trim()
  const builtAt = String(options.builtAt || new Date().toISOString()).trim()
  if (!/^[0-9a-f]{40}$/u.test(gitHead)) {
    throw new Error(`Invalid Git HEAD for WeChat build identity: ${gitHead || 'missing'}`)
  }
  if (!Number.isFinite(Date.parse(builtAt))) {
    throw new Error(`Invalid WeChat build timestamp: ${builtAt || 'missing'}`)
  }
  return {
    schemaRevision,
    gitHead,
    sourceHash: computeWeappSourceHash(root),
    builtAt,
  }
}

function writeWeappBuildIdentity(root, outputRoot, options = {}) {
  const identity = createWeappBuildIdentity(root, options)
  fs.mkdirSync(outputRoot, { recursive: true })
  fs.writeFileSync(
    path.join(outputRoot, identityFileName),
    `${JSON.stringify(identity, null, 2)}\n`,
  )
  return identity
}

function readWeappBuildIdentity(outputRoot) {
  const identityPath = path.join(outputRoot, identityFileName)
  let identity
  try {
    identity = JSON.parse(fs.readFileSync(identityPath, 'utf8'))
  } catch (error) {
    throw new Error(`Missing or invalid WeChat build identity: ${identityPath}: ${error instanceof Error ? error.message : String(error)}`)
  }
  if (
    !identity
    || identity.schemaRevision !== schemaRevision
    || !/^[0-9a-f]{40}$/u.test(String(identity.gitHead || ''))
    || !/^sha256:[0-9a-f]{64}$/u.test(String(identity.sourceHash || ''))
    || !Number.isFinite(Date.parse(String(identity.builtAt || '')))
  ) {
    throw new Error(`Invalid WeChat build identity contract: ${identityPath}`)
  }
  return identity
}

function verifyWeappBuildIdentity(root, outputRoot) {
  const identity = readWeappBuildIdentity(outputRoot)
  const currentSourceHash = computeWeappSourceHash(root)
  if (identity.sourceHash !== currentSourceHash) {
    throw new Error(`WeChat build source identity mismatch: built=${identity.sourceHash} current=${currentSourceHash}`)
  }
  return identity
}

module.exports = {
  computeWeappSourceHash,
  createWeappBuildIdentity,
  identityFileName,
  readWeappBuildIdentity,
  verifyWeappBuildIdentity,
  writeWeappBuildIdentity,
}

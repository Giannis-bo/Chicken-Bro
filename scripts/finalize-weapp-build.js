#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')

const repositoryRoot = path.resolve(__dirname, '..')
const appRoot = path.join(repositoryRoot, 'apps/mini-taro')

function outputRoot() {
  const configured = process.env.WOW_TARO_OUTPUT_ROOT?.trim()
  return configured ? path.resolve(configured) : path.join(appRoot, 'dist/weapp')
}

function finalizeWeappBuild(root = outputRoot()) {
  const entryPath = path.join(root, 'app.js')
  const entry = fs.lstatSync(entryPath)
  if (!entry.isFile() || entry.isSymbolicLink()) throw new Error(`WeChat build entry must be a regular file: ${entryPath}`)
  const completedAt = new Date(Math.max(Date.now(), entry.mtimeMs + 1))
  fs.utimesSync(entryPath, entry.atime, completedAt)
  return { entryPath, completedAt: completedAt.toISOString() }
}

if (require.main === module) {
  try {
    process.stdout.write(`${JSON.stringify(finalizeWeappBuild())}\n`)
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`)
    process.exit(1)
  }
}

module.exports = { finalizeWeappBuild, outputRoot }

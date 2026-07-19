'use strict'

const path = require('node:path')

function repoRelativePath(value) {
  return String(value ?? '').replace(/\\/gu, '/')
}

function repoPathJoin(...segments) {
  return path.posix.join(...segments.map(repoRelativePath))
}

function repoPathDirname(value) {
  return path.posix.dirname(repoRelativePath(value))
}

module.exports = {
  repoRelativePath,
  repoPathDirname,
  repoPathJoin,
}

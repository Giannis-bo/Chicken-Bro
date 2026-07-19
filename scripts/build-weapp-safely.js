#!/usr/bin/env node
'use strict'

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const { finalizeWeappBuild } = require('./finalize-weapp-build')

const repositoryRoot = path.resolve(__dirname, '..')
const appRoot = path.join(repositoryRoot, 'apps/mini-taro')
const liveOutputRoot = path.join(appRoot, 'dist/weapp')
const maximumBuildFiles = 4096
const requiredEntries = ['app.json', 'app.js', 'app.wxss']
const requiredPageExtensions = ['js', 'json', 'wxml', 'wxss']

function relativeBuildPath(root, file) {
  return path.relative(root, file).split(path.sep).join('/')
}

function walkFiles(root) {
  if (!fs.existsSync(root)) return []
  const rootStat = fs.lstatSync(root)
  if (rootStat.isSymbolicLink()) throw new Error(`WeChat build root cannot be a symbolic link: ${root}`)
  if (!rootStat.isDirectory()) throw new Error(`WeChat build root must be a directory: ${root}`)
  const files = []
  const visit = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name)
      if (entry.isSymbolicLink()) throw new Error(`WeChat build cannot contain symbolic links: ${target}`)
      if (entry.isDirectory()) visit(target)
      else if (entry.isFile()) files.push(target)
      else throw new Error(`Unsupported WeChat build entry: ${target}`)
      if (files.length > maximumBuildFiles) {
        throw new Error(`WeChat build file cap exceeded: ${files.length}/${maximumBuildFiles}`)
      }
    }
  }
  visit(root)
  return files
}

function validateBuild(root) {
  const files = walkFiles(root)
  const relativeFiles = new Set(files.map((file) => relativeBuildPath(root, file)))
  for (const entry of requiredEntries) {
    if (!relativeFiles.has(entry)) throw new Error(`WeChat build is missing ${entry}: ${root}`)
  }
  let manifest
  try {
    manifest = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'))
  } catch (error) {
    throw new Error(`WeChat build app.json is invalid: ${error instanceof Error ? error.message : String(error)}`)
  }
  if (!Array.isArray(manifest.pages) || manifest.pages.length === 0) {
    throw new Error(`WeChat build app.json must declare at least one page: ${root}`)
  }
  for (const page of manifest.pages) {
    if (
      typeof page !== 'string'
      || !page
      || page.startsWith('/')
      || page.split('/').includes('..')
      || path.posix.normalize(page) !== page
    ) {
      throw new Error(`WeChat build app.json contains an invalid page path: ${String(page)}`)
    }
    for (const extension of requiredPageExtensions) {
      const entry = `${page}.${extension}`
      if (!relativeFiles.has(entry)) throw new Error(`WeChat build is missing page entry ${entry}: ${root}`)
    }
  }
  return files
}

function filesEqual(source, target) {
  if (!fs.existsSync(target)) return false
  const sourceStat = fs.statSync(source)
  const targetStat = fs.statSync(target)
  if (!targetStat.isFile() || sourceStat.size !== targetStat.size) return false
  return fs.readFileSync(source).equals(fs.readFileSync(target))
}

function atomicCopyFile(source, target, preservePath = false, forceReplace = false) {
  fs.mkdirSync(path.dirname(target), { recursive: true })
  if (!forceReplace && filesEqual(source, target)) return false
  if (preservePath && fs.existsSync(target)) {
    // DevTools treats a rename-over-app.json as a transient unlink and may
    // immediately compile a package that it believes has no manifest. Keep
    // the manifest inode/path alive for the rare build that actually changes
    // app.json; unchanged manifests are skipped above.
    const contents = fs.readFileSync(source)
    const currentSize = fs.statSync(target).size
    const writeBuffer = currentSize > contents.length
      ? Buffer.concat([contents, Buffer.alloc(currentSize - contents.length, 0x20)])
      : contents
    const descriptor = fs.openSync(target, 'r+')
    try {
      let offset = 0
      while (offset < writeBuffer.length) {
        const bytesWritten = fs.writeSync(
          descriptor,
          writeBuffer,
          offset,
          writeBuffer.length - offset,
          offset,
        )
        if (bytesWritten <= 0) {
          throw new Error(`Incomplete in-place manifest write: ${offset}/${writeBuffer.length}`)
        }
        offset += bytesWritten
      }
      // JSON permits trailing whitespace, so a shorter replacement remains
      // parseable even if DevTools observes the write before this truncate.
      fs.fsyncSync(descriptor)
      fs.ftruncateSync(descriptor, contents.length)
      fs.fsyncSync(descriptor)
    } finally {
      fs.closeSync(descriptor)
    }
    return true
  }
  const temporary = `${target}.wow-next-${process.pid}-${Date.now()}`
  try {
    fs.copyFileSync(source, temporary, fs.constants.COPYFILE_EXCL)
    fs.renameSync(temporary, target)
  } finally {
    fs.rmSync(temporary, { force: true })
  }
  return true
}

function removeEmptyDirectories(root) {
  if (!fs.existsSync(root)) return
  const visit = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.isDirectory() && !entry.isSymbolicLink()) visit(path.join(directory, entry.name))
    }
    if (directory !== root && fs.readdirSync(directory).length === 0) fs.rmdirSync(directory)
  }
  visit(root)
}

function resolveIsolatedOutputRoot(configuredRoot) {
  const resolved = path.resolve(appRoot, configuredRoot)
  const relativeToApp = path.relative(appRoot, resolved)
  const insideAppTree = relativeToApp === ''
    || (!relativeToApp.startsWith(`..${path.sep}`) && relativeToApp !== '..' && !path.isAbsolute(relativeToApp))
  if (insideAppTree) {
    throw new Error(`WOW_TARO_OUTPUT_ROOT must stay outside the watched app tree: ${resolved}`)
  }
  return resolved
}

function promoteWeappBuild(stagingRoot, destinationRoot = liveOutputRoot, options = {}) {
  const stagingFiles = validateBuild(stagingRoot)
  const relativeFiles = stagingFiles.map((file) => relativeBuildPath(stagingRoot, file))
  const stagedSet = new Set(relativeFiles)
  const notify = typeof options.afterMutation === 'function' ? options.afterMutation : () => {}

  // Reject unexpected filesystem entries before any copy can follow them.
  // A symlinked app.json would otherwise let the in-place manifest update
  // write outside the package root.
  walkFiles(destinationRoot)
  fs.mkdirSync(destinationRoot, { recursive: true })

  // Publish page files and shared dependencies before the manifest can refer
  // to them. app.js remains the final commit marker consumed by DevTools.
  const dependencyOrder = relativeFiles
    .filter((file) => file !== 'app.json' && file !== 'app.js')
    .sort()
    .concat('app.json')
  let installedFileCount = 0
  let unchangedFileCount = 0
  for (const relative of dependencyOrder) {
    const installed = atomicCopyFile(
      path.join(stagingRoot, relative),
      path.join(destinationRoot, relative),
      relative === 'app.json',
    )
    if (installed) {
      installedFileCount += 1
      notify({ type: 'install', relative })
    } else {
      unchangedFileCount += 1
      notify({ type: 'skip', relative })
    }
  }

  const staleFiles = walkFiles(destinationRoot)
    .map((file) => relativeBuildPath(destinationRoot, file))
    .filter((file) => !stagedSet.has(file))
    .sort()
  for (const relative of staleFiles) {
    fs.rmSync(path.join(destinationRoot, relative), { force: true })
    notify({ type: 'remove', relative })
  }
  removeEmptyDirectories(destinationRoot)

  const packageChangedBeforeCommit = installedFileCount > 0 || staleFiles.length > 0
  const appEntryInstalled = atomicCopyFile(
    path.join(stagingRoot, 'app.js'),
    path.join(destinationRoot, 'app.js'),
    false,
    packageChangedBeforeCommit,
  )
  if (appEntryInstalled) {
    installedFileCount += 1
    notify({ type: 'install', relative: 'app.js' })
  } else {
    unchangedFileCount += 1
    notify({ type: 'skip', relative: 'app.js' })
  }

  validateBuild(destinationRoot)
  return {
    destinationRoot,
    totalFileCount: relativeFiles.length,
    installedFileCount,
    unchangedFileCount,
    removedFileCount: staleFiles.length,
  }
}

function run() {
  const explicitOutputRoot = process.env.WOW_TARO_OUTPUT_ROOT?.trim()
  if (explicitOutputRoot) {
    const isolatedOutputRoot = resolveIsolatedOutputRoot(explicitOutputRoot)
    const result = spawnSync(path.join(repositoryRoot, 'node_modules/.bin/taro'), ['build', '--type', 'weapp'], {
      cwd: appRoot,
      env: process.env,
      stdio: 'inherit',
    })
    if (result.error) throw result.error
    if (result.status !== 0) throw new Error(`Taro WeChat build failed with status ${result.status ?? 1}`)
    finalizeWeappBuild(isolatedOutputRoot)
    return
  }

  // Keep staging outside the project tree. DevTools watches more than
  // miniprogramRoot and otherwise tries to hot-reload the incomplete staging
  // files even though the live package itself remains valid.
  const stagingRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-weapp-build-'))
  try {
    const result = spawnSync(path.join(repositoryRoot, 'node_modules/.bin/taro'), ['build', '--type', 'weapp'], {
      cwd: appRoot,
      env: {
        ...process.env,
        WOW_TARO_ISOLATED_BUILD: '1',
        WOW_TARO_OUTPUT_ROOT: stagingRoot,
      },
      stdio: 'inherit',
    })
    if (result.error) throw result.error
    if (result.status !== 0) throw new Error(`Taro WeChat build failed with status ${result.status ?? 1}`)
    finalizeWeappBuild(stagingRoot)
    const resultSummary = promoteWeappBuild(stagingRoot)
    process.stdout.write(`${JSON.stringify({ status: 'pass', strategy: 'staged-atomic-promotion', ...resultSummary })}\n`)
  } finally {
    fs.rmSync(stagingRoot, { recursive: true, force: true })
  }
}

if (require.main === module) {
  try {
    run()
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`)
    process.exit(1)
  }
}

module.exports = {
  liveOutputRoot,
  promoteWeappBuild,
  resolveIsolatedOutputRoot,
  validateBuild,
  walkFiles,
}

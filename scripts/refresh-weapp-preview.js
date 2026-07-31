#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')
const { verifyWeappBuildIdentity } = require('./weapp-build-identity')

function isFile(filePath) {
  try {
    return fs.statSync(filePath).isFile()
  } catch {
    return false
  }
}

function resolveDevToolsCli({ platform = process.platform, env = process.env, fileExists = isFile } = {}) {
  const pathApi = platform === 'win32' ? path.win32 : path
  const override = String(env.WECHAT_DEVTOOLS_CLI || '').trim()
  if (override) {
    const resolvedOverride = pathApi.resolve(override)
    return fileExists(resolvedOverride) ? resolvedOverride : null
  }

  const candidates = []
  if (platform === 'darwin') {
    candidates.push('/Applications/wechatwebdevtools.app/Contents/MacOS/cli')
  } else if (platform === 'win32') {
    for (const base of [env.LOCALAPPDATA, env.ProgramFiles, env['ProgramFiles(x86)']]) {
      if (!base) continue
      candidates.push(
        path.win32.join(base, 'Tencent', '微信web开发者工具', 'cli.bat'),
        path.win32.join(base, '微信开发者工具', 'cli.bat'),
      )
    }
  }

  return candidates.find(fileExists) || null
}

function countFiles(root) {
  let count = 0
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const entryPath = path.join(root, entry.name)
    if (entry.isDirectory()) {
      count += countFiles(entryPath)
    } else if (entry.isFile()) {
      count += 1
    }
  }
  return count
}

function verifyWeappOutput(root) {
  const projectRoot = path.join(root, 'apps', 'mini-taro')
  const projectConfigPath = path.join(projectRoot, 'project.config.json')
  const projectConfig = JSON.parse(fs.readFileSync(projectConfigPath, 'utf8'))
  if (projectConfig.miniprogramRoot !== 'dist/weapp/') {
    throw new Error(`Unexpected miniprogramRoot: ${projectConfig.miniprogramRoot || 'missing'}`)
  }

  const outputRoot = path.join(projectRoot, 'dist', 'weapp')
  for (const relativePath of ['app.json', 'app.js', 'common.wxss']) {
    const outputPath = path.join(outputRoot, relativePath)
    if (!isFile(outputPath)) {
      throw new Error(`Missing WeChat build output: ${outputPath}`)
    }
  }

  JSON.parse(fs.readFileSync(path.join(outputRoot, 'app.json'), 'utf8'))
  const identity = verifyWeappBuildIdentity(root, outputRoot)
  return {
    status: 'pass',
    projectRoot,
    outputRoot,
    fileCount: countFiles(outputRoot),
    gitHead: identity.gitHead,
    sourceHash: identity.sourceHash,
    builtAt: identity.builtAt,
  }
}

function writeRuntimeProjectConfig(destination, payload) {
  const encoded = `${JSON.stringify(payload, null, 2)}\n`
  if (isFile(destination) && fs.readFileSync(destination, 'utf8') === encoded) return

  const temporary = `${destination}.wow-next-${process.pid}-${Date.now()}`
  try {
    fs.writeFileSync(temporary, encoded, { encoding: 'utf8', flag: 'wx', mode: 0o600 })
    fs.renameSync(temporary, destination)
  } finally {
    fs.rmSync(temporary, { force: true })
  }
}

function ensureDevToolsRuntimeProject(verified) {
  const expectedOutputRoot = path.join(verified.projectRoot, 'dist', 'weapp')
  if (path.resolve(verified.outputRoot) !== path.resolve(expectedOutputRoot)) {
    throw new Error(`Unexpected WeChat runtime project root: ${verified.outputRoot}`)
  }
  const outputStat = fs.lstatSync(verified.outputRoot)
  if (!outputStat.isDirectory() || outputStat.isSymbolicLink()) {
    throw new Error(`WeChat runtime project root must be a real directory: ${verified.outputRoot}`)
  }

  const sourceConfigPath = path.join(verified.projectRoot, 'project.config.json')
  const sourceConfig = JSON.parse(fs.readFileSync(sourceConfigPath, 'utf8'))
  const runtimeConfig = {
    ...sourceConfig,
    compileType: 'miniprogram',
    miniprogramRoot: '',
    projectname: `${sourceConfig.projectname || 'wow-mini-taro'}-runtime`,
  }
  writeRuntimeProjectConfig(
    path.join(verified.outputRoot, 'project.config.json'),
    runtimeConfig,
  )

  const sourcePrivateConfigPath = path.join(verified.projectRoot, 'project.private.config.json')
  if (isFile(sourcePrivateConfigPath)) {
    const sourcePrivateConfig = JSON.parse(fs.readFileSync(sourcePrivateConfigPath, 'utf8'))
    writeRuntimeProjectConfig(
      path.join(verified.outputRoot, 'project.private.config.json'),
      {
        ...sourcePrivateConfig,
        projectname: runtimeConfig.projectname,
      },
    )
  }

  return verified.outputRoot
}

function defaultExecute(command, args, options) {
  return spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    shell: options.shell === true,
    stdio: 'inherit',
  })
}

function refreshWeappPreview({
  root = path.resolve(__dirname, '..'),
  platform = process.platform,
  env = process.env,
  execute = defaultExecute,
  resolveCli = resolveDevToolsCli,
} = {}) {
  const npmCommand = platform === 'win32' ? 'npm.cmd' : 'npm'
  const build = execute(npmCommand, ['run', 'build:weapp'], {
    cwd: root,
    env,
    // Windows cannot spawn a .cmd shim directly with Node child_process.
    shell: platform === 'win32',
  })
  if (build.status !== 0) {
    throw new Error(`npm run build:weapp failed with exit code ${build.status ?? 'unknown'}`)
  }

  const verified = verifyWeappOutput(root)
  const devToolsProjectRoot = ensureDevToolsRuntimeProject(verified)
  const cli = resolveCli({ platform, env })
  if (!cli) {
    return {
      ...verified,
      devToolsProjectRoot,
      status: 'manual_open_required',
      reason: `WeChat DevTools CLI was not found. Set WECHAT_DEVTOOLS_CLI or import ${devToolsProjectRoot} manually.`,
    }
  }

  const opened = execute(cli, ['open', '--project', devToolsProjectRoot, '--lang', 'zh'], {
    cwd: root,
    env,
    shell: platform === 'win32',
  })
  if (opened.status !== 0) {
    return {
      ...verified,
      devToolsProjectRoot,
      status: 'manual_open_required',
      cli,
      cliExitCode: opened.status,
      reason: 'The build is verified, but WeChat DevTools did not open it. Enable the DevTools service port and retry.',
    }
  }

  return {
    ...verified,
    devToolsProjectRoot,
    status: 'preview_refreshed',
    cli,
  }
}

function main() {
  try {
    const result = refreshWeappPreview()
    process.stdout.write(`${JSON.stringify(result)}\n`)
    if (result.status !== 'preview_refreshed') {
      process.exitCode = 2
    }
  } catch (error) {
    process.stderr.write(`${JSON.stringify({ status: 'failed', error: error.message })}\n`)
    process.exitCode = 1
  }
}

if (require.main === module) {
  main()
}

module.exports = {
  ensureDevToolsRuntimeProject,
  resolveDevToolsCli,
  verifyWeappOutput,
  refreshWeappPreview,
}

#!/usr/bin/env node

const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const { connectMiniProgram } = require('../../ui-v2-1-strict-restoration/connect-miniprogram-automator')

const artifactDir = __dirname
const preferredPorts = [
  Number(process.env.WECHAT_AUTOMATOR_PORT || 9854),
  9854
]

function withUnique(values) {
  return Array.from(new Set(values.filter((value) => Number.isFinite(value) && value > 0)))
}

function listeningWechatPorts() {
  let stdout = ''
  try {
    stdout = execFileSync('lsof', ['-nP', '-iTCP', '-sTCP:LISTEN'], {
      encoding: 'utf8',
      timeout: 4000
    })
  } catch (error) {
    return {
      error: error && error.message ? error.message : String(error),
      ports: []
    }
  }
  const ports = []
  const records = stdout
    .split('\n')
    .slice(1)
    .filter((line) => /wechatweb|wechatdevtools/i.test(line))
    .map((line) => {
      const match = line.match(/TCP\s+(\S+):(\d+)\s+\(LISTEN\)/)
      const port = match ? Number(match[2]) : null
      if (port) ports.push(port)
      return { port, raw: line.trim() }
    })
  return { ports: withUnique(ports), records }
}

async function probePort(port) {
  const wsEndpoint = `ws://127.0.0.1:${port}`
  const startedAt = new Date().toISOString()
  try {
    const { mini, toolInfo, hasRuntimeSdk } = await connectMiniProgram(wsEndpoint, {
      timeoutMs: 900,
      toolInfoTimeoutMs: 1200
    })
    mini.disconnect()
    return {
      port,
      wsEndpoint,
      startedAt,
      finishedAt: new Date().toISOString(),
      status: 'tool_info_ready',
      hasRuntimeSdk,
      toolInfoVersion: toolInfo && (toolInfo.version || toolInfo.SDKVersion || '')
    }
  } catch (error) {
    return {
      port,
      wsEndpoint,
      startedAt,
      finishedAt: new Date().toISOString(),
      status: 'unavailable',
      error: error && error.message ? error.message : String(error)
    }
  }
}

async function main() {
  const portScan = listeningWechatPorts()
  const ports = withUnique([
    ...preferredPorts,
    ...portScan.ports
  ])
  const results = []
  for (const port of ports) {
    results.push(await probePort(port))
  }
  const ready = results.filter((item) => item.status === 'tool_info_ready')
  const manifest = {
    status: ready.length ? 'automator_endpoint_probe_found_ready_endpoint' : 'automator_endpoint_probe_no_ready_endpoint',
    checkedAt: new Date().toISOString(),
    forbiddenActionsUsed: [],
    captureScreenshotUsed: false,
    navigationUsed: false,
    cliAutoUsed: false,
    note: 'Probe only attempts Tool.getInfo against existing listening ports. It does not close, restart, clear cache, switch appid, switch project, navigate, or capture screenshots.',
    portScan,
    results,
    recommendedAutomatorPort: ready.length ? ready[0].port : null
  }
  fs.writeFileSync(
    path.join(artifactDir, 'automator-endpoint-probe.json'),
    `${JSON.stringify(manifest, null, 2)}\n`
  )
  console.log(JSON.stringify({
    status: manifest.status,
    probedPortCount: results.length,
    recommendedAutomatorPort: manifest.recommendedAutomatorPort
  }, null, 2))
  process.exit(ready.length ? 0 : 2)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

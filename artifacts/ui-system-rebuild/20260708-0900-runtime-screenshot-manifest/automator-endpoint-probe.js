#!/usr/bin/env node

const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

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

function withTimeout(promise, ms, label) {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}

function safeClose(socket) {
  try {
    socket.close()
  } catch (error) {
    // Ignore close failures in a read-only probe.
  }
}

async function readToolInfo(wsEndpoint, timeoutMs) {
  return withTimeout(new Promise((resolve, reject) => {
    const socket = new WebSocket(wsEndpoint)
    const requestId = 1
    let settled = false
    const finish = (fn, value) => {
      if (settled) return
      settled = true
      safeClose(socket)
      fn(value)
    }
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({
        id: requestId,
        method: 'Tool.getInfo',
        params: {}
      }))
    })
    socket.addEventListener('message', (event) => {
      let message
      try {
        const raw = typeof event.data === 'string'
          ? event.data
          : Buffer.from(event.data).toString('utf8')
        message = JSON.parse(raw)
      } catch (error) {
        finish(reject, new Error(`invalid Tool.getInfo response: ${error.message}`))
        return
      }
      if (message.id !== requestId) return
      if (message.error) {
        finish(reject, new Error(message.error.message || JSON.stringify(message.error)))
        return
      }
      finish(resolve, message.result || message)
    })
    socket.addEventListener('error', (event) => {
      finish(reject, new Error(event && event.message ? event.message : 'websocket error'))
    })
    socket.addEventListener('close', () => {
      if (!settled) finish(reject, new Error('websocket closed before Tool.getInfo response'))
    })
  }), timeoutMs, `Tool.getInfo ${wsEndpoint}`)
}

async function probePort(port) {
  const wsEndpoint = `ws://127.0.0.1:${port}`
  const startedAt = new Date().toISOString()
  try {
    const toolInfo = await readToolInfo(wsEndpoint, 1200)
    const hasRuntimeSdk = !!(toolInfo && (toolInfo.SDKVersion || toolInfo.sdkVersion || toolInfo.version))
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

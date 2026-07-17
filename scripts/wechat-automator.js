'use strict'

const path = require('node:path')
const net = require('node:net')
const automator = require('miniprogram-automator')

const connectTimeoutMs = 30000

function timeout(promise, milliseconds, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${milliseconds}ms`)), milliseconds)),
  ])
}

async function connectMiniProgram() {
  const endpoint = process.env.WECHAT_AUTOMATOR_ENDPOINT
  if (endpoint) {
    return timeout(automator.connect({ wsEndpoint: endpoint }), connectTimeoutMs, `connect ${endpoint}`)
  }

  for (let port = 9420; port <= 9460; port += 1) {
    if (await portIsListening(port)) {
      return timeout(automator.connect({ wsEndpoint: `ws://127.0.0.1:${port}` }), connectTimeoutMs, `connect automation port ${port}`)
    }
  }

  if (process.env.WECHAT_AUTOMATOR_LAUNCH !== '1') {
    throw new Error('No reusable WeChat automation endpoint found on ports 9420-9460; refusing to relaunch DevTools. Start automation once with WECHAT_AUTOMATOR_LAUNCH=1 or provide WECHAT_AUTOMATOR_ENDPOINT.')
  }

  const projectPath = process.env.WECHAT_AUTOMATOR_PROJECT || path.resolve(__dirname, '../apps/mini-taro')
  const cliPath = process.env.WECHAT_DEVTOOLS_CLI
  return timeout(automator.launch({
    projectPath,
    trustProject: true,
    timeout: connectTimeoutMs,
    ...(cliPath ? { cliPath } : {}),
  }), connectTimeoutMs + 2000, 'launch automation channel')
}

function portIsListening(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port })
    const finish = (listening) => {
      socket.destroy()
      resolve(listening)
    }
    socket.setTimeout(120)
    socket.once('connect', () => finish(true))
    socket.once('error', () => finish(false))
    socket.once('timeout', () => finish(false))
  })
}

module.exports = { connectMiniProgram, timeout }

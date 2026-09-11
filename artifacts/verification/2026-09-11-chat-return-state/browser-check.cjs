const { chromium } = require('playwright-core')
const fs = require('node:fs/promises')
const path = require('node:path')
const assert = require('node:assert/strict')

;(async () => {
  const live = process.argv.includes('--live')
  const origin = live ? 'https://www.chickenbro.cloud' : 'https://chat-candidate.invalid'
  const build = path.resolve('apps/mini-taro/dist/h5')
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    await context.addCookies([{ name: '__Host-chickenbro-csrf', value: 'isolated-fixture-csrf', url: origin, secure: true }])
    const now = '2026-09-11T14:00:00.000Z'
    const a = { id: 'fixture-a', title: 'A 会话', status: 'active', createdAt: now, updatedAt: now }
    const b = { ...a, id: 'fixture-b', title: 'B 会话' }
    let admitted = false, completed = false
    await context.route('**/*', async route => {
      const url = new URL(route.request().url())
      if (url.pathname.startsWith('/api/')) {
        let data
        if (url.pathname.endsWith('/me')) data = { connected: true, displayName: '隔离验证账号' }
        else if (url.pathname.endsWith('/me/avatar')) data = { avatarDataUrl: null }
        else if (url.pathname.endsWith('/admin/access')) data = { isAdmin: false }
        else if (url.pathname.endsWith('/health/readiness')) data = { status: 'ready' }
        else if (url.pathname.endsWith('/chat/image-capabilities')) data = { enabled: false, maxImages: 3, maxBytes: 5242880 }
        else if (url.pathname.endsWith('/chat/conversations')) data = { items: [a, b], nextCursor: null }
        else if (url.pathname.endsWith('/fixture-a')) data = { ...a, messages: admitted ? [
          { id: 'fixture-question', role: 'user', content: '验证会话切换', createdAt: now },
          ...(completed ? [{ id: 'fixture-answer', role: 'assistant', content: '验证回答完成', createdAt: now }] : []),
        ] : [] }
        else if (url.pathname.endsWith('/fixture-b')) data = { ...b, messages: [] }
        else return route.fulfill({ status: 404, body: '{}' })
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
      }
      if (live) return route.continue()
      if (url.origin !== origin) return route.abort()
      const relative = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname).slice(1)
      const file = path.resolve(build, relative)
      if (!file.startsWith(build + path.sep)) return route.abort()
      try {
        const contentType = ({ '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.png': 'image/png', '.ico': 'image/x-icon' })[path.extname(file)] || 'application/octet-stream'
        return route.fulfill({ contentType, body: await fs.readFile(file) })
      } catch { return route.fulfill({ status: 404, body: '' }) }
    })
    await context.addInitScript(() => {
      const realFetch = window.fetch.bind(window)
      window.__fixtureSends = 0
      window.fetch = (url, options) => {
        if (String(url).includes('/messages/stream')) {
          window.__fixtureSends++
          const stream = new ReadableStream({ start(controller) { window.__fixtureStream = controller } })
          return Promise.resolve(new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }))
        }
        return realFetch(url, options)
      }
    })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(origin, { waitUntil: 'networkidle' })
    await page.locator('[data-conversation-id="fixture-a"]').waitFor()
    assert.equal(await page.getByText('研究额度', { exact: false }).count(), 0)
    await page.getByRole('textbox', { name: '消息内容' }).fill('验证会话切换')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await page.waitForFunction(() => window.__fixtureStream)
    const emit = async event => page.evaluate(event => window.__fixtureStream.enqueue(new TextEncoder().encode('data: ' + JSON.stringify(event) + '\n\n')), event)
    const base = { conversationId: a.id, requestId: 'fixture-request', runId: 'fixture-run' }
    admitted = true
    await emit({ ...base, type: 'started', sequence: 1 })
    const open = id => page.locator(`[data-conversation-id="${id}"]`).click()
    await open(b.id)
    await open(a.id)
    await page.getByRole('status', { name: '等待回复', exact: true }).waitFor()
    await page.getByRole('textbox', { name: '消息内容' }).fill('下一条问题')
    assert.equal(await page.getByRole('button', { name: '正在回复', exact: true }).isDisabled(), true)
    await open(b.id)
    await emit({ ...base, type: 'progress', sequence: 2, text: '正在核对验证数据' })
    assert.equal(await page.getByText('正在核对验证数据', { exact: true }).count(), 0)
    await open(a.id)
    await page.getByText('正在核对验证数据', { exact: true }).waitFor()
    await page.screenshot({ path: path.join(__dirname, live ? 'live-progress.png' : 'candidate-progress.png') })
    completed = true
    await emit({ ...base, type: 'completed', sequence: 3, text: '验证回答完成' })
    await page.evaluate(() => window.__fixtureStream.close())
    await page.getByRole('button', { name: '发送消息', exact: true }).waitFor()
    await page.getByText('验证回答完成', { exact: true }).waitFor()
    assert.equal(await page.getByRole('button', { name: '发送消息', exact: true }).isDisabled(), false)
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await page.waitForFunction(() => window.__fixtureSends === 2)
    assert.deepEqual(errors, [])
    const result = { mode: live ? 'public-artifact-with-isolated-api-fixture' : 'local-release-artifact-with-isolated-api-fixture', passed: true, checks: ['copy-removed', 'waiting-restored', 'background-isolated', 'progress-restored', 'completion-unlocks', 'followup-sent'], realModelCalls: 0, productionDataWrites: 0 }
    await fs.writeFile(path.join(__dirname, live ? 'live-browser.json' : 'candidate-browser.json'), JSON.stringify(result, null, 2) + '\n')
    console.log(JSON.stringify(result))
  } finally { await browser.close() }
})().catch(error => { console.error(error); process.exitCode = 1 })

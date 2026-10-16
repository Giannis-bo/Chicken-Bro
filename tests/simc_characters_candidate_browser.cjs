// Cloud-only acceptance: built Web, real API/PostgreSQL/source/queue/installed engine.
const { chromium } = require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs = require('node:fs')
const assert = require('node:assert/strict')
const root = '/opt/chickenbro-candidates/simc-character-bindings-20261016'
const origin = 'https://simc-characters-candidate.invalid'
const sessions = JSON.parse(fs.readFileSync('/tmp/simc-characters-private-20261016/sessions.json', 'utf8'))
const checks = [], errors = [], calls = []
let closing = false
const frozen = process.env.SIMC_CHARACTERS_FROZEN === '1'
async function account(browser, key, viewport = { width: 1440, height: 900 }) {
  const context = await browser.newContext({ viewport })
  await context.addCookies([
    { name: '__Host-simc-characters-session', value: sessions[key].token, url: origin, httpOnly: true, secure: true, sameSite: 'Lax' },
    { name: '__Host-chickenbro-csrf', value: sessions[key].csrf, url: origin, secure: true, sameSite: 'Lax' },
  ])
  // Transport-only proxy keeps synthetic cookies isolated on a non-public HTTPS origin.
  await context.route(origin + '/**', async route => {
    try {
    const request = route.request()
    const headers = await request.allHeaders()
    headers.host = new URL(origin).host
    delete headers['content-length']
    const original = new URL(request.url())
    const replay = frozen && original.pathname === '/api/v2/simc/snapshots' && request.method() === 'POST'
    const target = replay ? '/api/v2/simc/snapshots/' + sessions.A.snapshotId + original.search : original.pathname + original.search
    const response = await context.request.fetch('http://127.0.0.1:8885' + target,
      { method: replay ? 'GET' : request.method(), headers, ...(!replay && request.postDataBuffer() ? { data: request.postDataBuffer() } : {}), timeout: 65000 })
    if (new URL(request.url()).pathname.includes('/simc/')) calls.push({ method: request.method(), path: new URL(request.url()).pathname, status: response.status() })
    await route.fulfill({ response })
    } catch {
      if (!closing) errors.push('Candidate proxy transport failed')
      await route.abort('failed').catch(() => {})
    }
  })
  return context
}
async function main() {
  fs.mkdirSync(root + '/evidence', { recursive: true })
  const browser = await chromium.launch({ headless: true, executablePath: '/opt/chickenbro-candidates/poe2-20260918/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell', env: { ...process.env, LD_LIBRARY_PATH: '/opt/chickenbro-candidates/poe2-20260918/runtime/browser/root/usr/lib/x86_64-linux-gnu', FONTCONFIG_FILE: '/opt/chickenbro-candidates/poe2-20260918/runtime/browser/fonts.conf' }, args: ['--no-sandbox'] })
  const context = await account(browser, 'A')
  const page = await context.newPage()
  page.on('pageerror', e => errors.push(e.message))
  let job
  try {
    await page.goto(origin + '/simc', { waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: '手动输入', exact: true }).click()
    assert.equal(await page.locator('[name="characterRegion"]').inputValue(), 'cn')
    await page.locator('[name="characterName"]').fill('Giannis')
    await page.locator('[name="characterRealm"]').fill('白银之手')
    await page.screenshot({ path: root + '/evidence/desktop-manual.png', fullPage: true })
    checks.push('manual defaults CN and accepts Chinese realm')
    await page.getByRole('button', { name: '读取角色', exact: true }).click()
    await page.getByText('角色已就绪', { exact: false }).waitFor({ timeout: 65000 })
    assert.equal(await page.getByRole('button', { name: '开始模拟', exact: true }).isEnabled(), true)
    checks.push('real Chinese realm source ready')
    await page.getByRole('button', { name: '绑定此角色', exact: true }).click()
    await page.locator('[data-bound-id][aria-pressed="true"]').waitFor({ timeout: 65000 })
    await page.getByText('角色已就绪', { exact: false }).waitFor({ timeout: 65000 })
    assert.ok((await page.locator('body').innerText()).includes('已绑定 1/3'))
    checks.push('binds and selects on account')
    await page.screenshot({ path: root + '/evidence/desktop-bound.png', fullPage: true })
    const dimensions = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth, height: innerHeight, scrollHeight: document.documentElement.scrollHeight }))
    assert.ok(dimensions.scrollWidth <= dimensions.width + 1)
    checks.push('desktop has no horizontal overflow')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: root + '/evidence/mobile-bound.png', fullPage: true })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    assert.equal(await page.locator('[data-binding-count]').isVisible(), true)
    checks.push('390px has no horizontal overflow and shows binding limit')
    await page.setViewportSize({ width: 1366, height: 768 })
    const compact = await page.evaluate(() => ({ height: innerHeight, scrollHeight: document.documentElement.scrollHeight }))
    assert.ok(compact.scrollHeight <= compact.height + 1, JSON.stringify(compact))
    await page.screenshot({ path: root + '/evidence/desktop-1366.png', fullPage: true })
    checks.push('1366x768 bound role setup fits one screen')
    if (frozen) {
      assert.deepEqual(errors, [])
      fs.writeFileSync(root + '/evidence/browser-layout.json', JSON.stringify({ passed: true, checks, calls, errors, dimensions, compact, scope: 'Final build layout and binding UI with a copied, previously verified owner-scoped role snapshot. Snapshot reads replay fixed data; no new provider or engine call.' }, null, 2))
      console.log(JSON.stringify({ passed: true, scope: 'final layout with frozen verified snapshot', checks, compact }))
      return
    }
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.locator('[data-bound-id][aria-pressed="true"]').waitFor()
    await page.getByText('角色已就绪', { exact: false }).waitFor({ timeout: 65000 })
    checks.push('reload restores selected bound role without input')
    await page.locator('[name="iterations"]').fill('16')
    await page.locator('[name="maxTime"]').fill('30')
    const request = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/simc/jobs' && response.request().method() === 'POST', { timeout: 65000 })
    const sourcesBefore = calls.filter(call => call.method === 'POST' && call.path.endsWith('/snapshots')).length
    await page.getByRole('button', { name: '开始模拟', exact: true }).click()
    const created = await request
    assert.equal(created.status(), 202, await created.text())
    job = await created.json()
    assert.ok(calls.filter(call => call.method === 'POST' && call.path.endsWith('/snapshots')).length > sourcesBefore)
    checks.push('new submission refreshes selected character')
    await page.locator('[data-job-status="succeeded"] [data-result-id]').waitFor({ timeout: 65000 })
    const detail = await page.evaluate(async id => (await fetch('/api/v2/simc/jobs/' + id + '?view=workbench&scenarioVersion=6&reportLocale=zhCN')).json(), job.id)
    assert.equal(detail.character.name, 'Giannis')
    assert.ok(detail.result.metricValue > 0)
    assert.ok(detail.result.provenance.snapshotId === detail.snapshotId)
    checks.push('real queue worker positive DPS and matching character snapshot provenance')
    await page.screenshot({ path: root + '/evidence/report.png', fullPage: true })
    const other = await account(browser, 'B')
    const pageB = await other.newPage()
    await pageB.goto(origin + '/simc', { waitUntil: 'domcontentloaded' })
    await pageB.getByRole('button', { name: '手动输入', exact: true }).waitFor()
    const isolation = await pageB.evaluate(async ({ jobId, snapshotId, boundId, csrf }) => {
      const read = async path => { const response = await fetch(path); return { status: response.status, body: await response.json() } }
      return { characters: await read('/api/v2/simc/characters'), job: await read('/api/v2/simc/jobs/' + jobId),
        bind: (await fetch('/api/v2/simc/characters', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ snapshotId }) })).status,
        select: (await fetch('/api/v2/simc/characters/' + boundId + '/select', { method: 'POST', headers: { 'X-CSRF-Token': csrf } })).status }
    }, { jobId: job.id, snapshotId: detail.snapshotId, boundId: await page.locator('[data-bound-id]').count() ? await page.locator('[data-bound-id]').getAttribute('data-bound-id') : (await page.evaluate(async () => (await (await fetch('/api/v2/simc/characters')).json()).selectedId)), csrf: sessions.B.csrf })
    assert.equal(isolation.characters.body.items.length, 0)
    assert.equal(isolation.job.status, 404)
    assert.equal(isolation.bind, 404)
    assert.equal(isolation.select, 404)
    checks.push('B cannot read A roles/jobs or bind A snapshot or select A role')
    const freshContext = await account(browser, 'A')
    const freshPage = await freshContext.newPage()
    await freshPage.goto(origin + '/simc', { waitUntil: 'domcontentloaded' })
    await freshPage.locator('[data-bound-id][aria-pressed="true"]').waitFor()
    checks.push('independent browser restores account selection')
    await freshPage.getByRole('button', { name: /^解绑 / }).click()
    await freshPage.getByRole('button', { name: '手动输入', exact: true }).waitFor()
    assert.equal(await freshPage.locator('[data-bound-id]').count(), 0)
    assert.equal(await freshPage.getByRole('button', { name: '开始模拟', exact: true }).isEnabled(), false)
    const persisted = await freshPage.evaluate(async () => (await fetch('/api/v2/simc/jobs')).json())
    assert.ok(persisted.items.some(item => item.id === job.id))
    checks.push('unbind clears selected role and retains simulation history')
    assert.deepEqual(errors, [])
    fs.writeFileSync(root + '/evidence/browser-acceptance.json', JSON.stringify({ passed: true, checks, calls, errors, dimensions,
      job: { id: detail.id, character: detail.character, status: detail.status, metric: detail.result.metricValue, snapshotId: detail.snapshotId, runtimeRevision: detail.runtimeRevision },
      scope: 'loopback isolated Candidate; real built Web/API/PostgreSQL/source/queue/SimC; synthetic formal sessions; production and real QQ login not changed' }, null, 2))
    console.log(JSON.stringify({ passed: true, checks, jobId: job.id, metric: detail.result.metricValue }))
  } catch (error) {
    await page.screenshot({ path: root + '/evidence/browser-failure.png', fullPage: true })
    fs.writeFileSync(root + '/evidence/browser-failure.json', JSON.stringify({ calls, checks, errors }, null, 2))
    console.error(error.message)
    console.error((await page.locator('body').innerText()).slice(-2200))
    process.exitCode = 1
  } finally {
    closing = true
    for (const active of browser.contexts()) await active.unrouteAll({ behavior: 'wait' })
    await browser.close()
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })

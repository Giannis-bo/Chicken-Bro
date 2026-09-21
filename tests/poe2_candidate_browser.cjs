// Cloud-only browser acceptance; sessions are short-lived synthetic A/B fixtures.
const {chromium} = require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs = require('node:fs')
const assert = require('node:assert/strict')
const root = '/opt/chickenbro-candidates/poe2-20260918'
const sessions = JSON.parse(fs.readFileSync(root + '/runtime/browser/session-fixtures.json', 'utf8'))
const origin = 'https://www.chickenbro.cloud'
const cookieName = '__Host-chickenbro-poe2-candidate-session'
const csrfName = '__Host-chickenbro-poe2-candidate-csrf'
async function account(browser, name) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}})
  await context.addCookies([
    {name: cookieName, value: sessions[name].token, url: origin, httpOnly: true, secure: true, sameSite: 'Lax'},
    {name: csrfName, value: sessions[name].csrf, url: origin, secure: true, sameSite: 'Lax'},
  ])
  return context
}
async function main() {
  const browser = await chromium.launch({headless: true,
    executablePath: root + '/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell',
    args: ['--no-sandbox']})
  const context = await account(browser, 'A')
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  const requests = []
  page.on('response', r => {if (r.url().includes('/poe2/')) requests.push({url: new URL(r.url()).pathname, status: r.status()})})
  try {
    await page.goto(origin + '/poe2-candidate/', {waitUntil: 'domcontentloaded'})
    await page.getByLabel('选择游戏').selectOption('poe2')
    await page.locator('[aria-label="POE2 构筑"]').click()
    await page.getByRole('heading', {name: '我的构筑', exact: true}).waitFor()
    await page.getByRole('button', {name: /云端验证 · Fireball 基线/}).waitFor()
    console.log('workspace loaded')
    const title = '浏览器验证 ' + new Date().toISOString()
    await page.getByRole('button', {name: '① 导入构筑', exact: true}).click()
    await page.getByLabel('构筑名称', {exact: true}).fill(title)
    await page.getByLabel('构筑分享码', {exact: true}).fill(fs.readFileSync(root + '/evidence/fixtures/build-1.xml', 'utf8'))
    await page.getByRole('button', {name: '导入构筑', exact: true}).click()
    await page.getByRole('heading', {name: title, exact: true}).waitFor({timeout: 70000})
    console.log('real import completed')
    await page.getByRole('button', {name: '计算基线', exact: true}).click()
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent === '计算方案' && !b.disabled), null, {timeout: 70000})
    console.log('baseline completed')
    await page.getByLabel('装备文本', {exact: true}).first().fill('Rarity: Rare\nTest Ring\nGold Ring\n--------\n+50 to maximum Life')
    await page.getByRole('button', {name: '计算方案', exact: true}).click()
    await page.getByRole('heading', {name: '方案对比', exact: true}).waitFor({timeout: 70000})
    console.log('comparison completed')
    const lifeRow = page.locator('tr').filter({has: page.locator('td', {hasText: /^生命$/})})
    assert.ok((await lifeRow.innerText()).replace(/,/g, '').includes('1187'))
    await page.getByRole('button', {name: '查看完整详情 →', exact: true}).click()
    await page.getByRole('button', {name: '导出此方案', exact: true}).click()
    assert.ok((await page.getByLabel('导出的构筑').inputValue()).length > 100)
    await page.screenshot({path: root + '/evidence/browser-desktop.png', fullPage: true})
    await page.setViewportSize({width: 390, height: 844})
    await page.screenshot({path: root + '/evidence/browser-mobile.png', fullPage: true})
    const width = await page.evaluate(() => ({scroll: document.documentElement.scrollWidth, inner: innerWidth}))
    assert.ok(width.scroll <= width.inner + 4, JSON.stringify(width))
    await page.reload({waitUntil: 'domcontentloaded'})
    await page.getByRole('heading', {name: '我的构筑', exact: true}).waitFor()
    await page.getByLabel('选择游戏').selectOption('wow')
    await page.locator('[aria-label="SimC 模拟"]').click()
    assert.ok(page.url().includes('/simc'))
    await page.getByRole('button', {name: '账户菜单', exact: true}).click()
    await page.getByRole('button', {name: '退出登录', exact: true}).click()
    await page.getByLabel('选择游戏').waitFor({state: 'detached'})
    const other = await account(browser, 'B')
    const pageB = await other.newPage()
    await pageB.goto(origin + '/poe2-candidate/poe2', {waitUntil: 'domcontentloaded'})
    await pageB.getByRole('heading', {name: '我的构筑', exact: true}).waitFor()
    assert.ok(!(await pageB.locator('body').innerText()).includes(title))
    assert.ok((await pageB.locator('body').innerText()).includes('导入 PoB 2 构筑'))
    assert.deepEqual(errors, [])
    fs.writeFileSync(root + '/evidence/browser-acceptance.json', JSON.stringify({passed: true, title, requests, errors,
      checks: ['public load', 'game switch', 'real import', 'baseline', 'item candidate', 'compare', 'export', 'direct route reload', 'mobile width', 'wow navigation', 'logout', 'B isolation'],
      authScope: 'issued synthetic sessions; existing password login awaits user acceptance'}, null, 2))
    console.log('Browser acceptance passed: 13 checks')
  } catch (error) {
    await page.screenshot({path: root + '/evidence/browser-failure.png', fullPage: true})
    console.error(String(error)); console.error((await page.locator('body').innerText()).slice(-1800))
    process.exitCode = 1
  } finally {await browser.close()}
}
main().catch(error => {console.error(error.message); process.exitCode = 1})

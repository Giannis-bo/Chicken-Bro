// Cloud-only acceptance for the guided build workflow, using synthetic sessions.
const {chromium} = require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs = require('node:fs')
const assert = require('node:assert/strict')
const root = '/opt/chickenbro-candidates/poe2-20260918'
async function main() {
  const session = JSON.parse(fs.readFileSync(root + '/runtime/browser/session-fixtures.json', 'utf8')).A
  const browser = await chromium.launch({headless: true, executablePath: root + '/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell', args: ['--no-sandbox']})
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}})
  await context.addCookies([
    {name: '__Host-chickenbro-poe2-candidate-session', value: session.token, url: 'https://www.chickenbro.cloud', httpOnly: true, secure: true, sameSite: 'Lax'},
    {name: '__Host-chickenbro-poe2-candidate-csrf', value: session.csrf, url: 'https://www.chickenbro.cloud', secure: true, sameSite: 'Lax'},
  ])
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', e => errors.push(e.message))
  const checks = []
  try {
    await page.goto('https://www.chickenbro.cloud/poe2-candidate/poe2', {waitUntil: 'domcontentloaded'})
    await page.getByRole('button', {name: '① 导入构筑', exact: true}).click()
    await page.getByRole('heading', {name: '分享码从哪里来？'}).waitFor()
    assert.equal(await page.getByRole('link', {name: 'PoB 2 官方项目 ↗'}).getAttribute('href'), 'https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2')
    assert.equal(await page.getByRole('link', {name: 'PoB 2 官方下载 ↗'}).getAttribute('href'), 'https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2/releases')
    checks.push('import instructions and official links')
    await page.screenshot({path: root + '/evidence/flow-import-desktop.png', fullPage: true})
    await page.setViewportSize({width: 390, height: 844})
    await page.screenshot({path: root + '/evidence/flow-import-mobile.png', fullPage: true})
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 4))
    checks.push('mobile import layout')
    await page.getByRole('button', {name: '使用示例构筑', exact: true}).click()
    await page.getByRole('heading', {name: '第二步 · 调整与对比'}).waitFor({timeout: 70000})
    assert.ok((await page.getByLabel('装备文本', {exact: true}).first().inputValue()).includes('+50 to maximum Life'))
    assert.ok(await page.getByRole('button', {name: '计算方案', exact: true}).isDisabled())
    checks.push('real example import and baseline prerequisite')
    await page.getByRole('button', {name: '计算基线', exact: true}).click()
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent === '计算方案' && !b.disabled), null, {timeout: 70000})
    await page.getByRole('button', {name: '计算方案', exact: true}).click()
    await page.getByRole('heading', {name: '方案对比', exact: true}).waitFor({timeout: 70000})
    const lifeRow = page.locator('tr').filter({has: page.locator('td', {hasText: /^生命$/})})
    const life = (await lifeRow.locator('td').allTextContents()).slice(1, 3).map(t => Number(t.replace(/,/g, '')))
    assert.ok(life[1] > life[0], JSON.stringify(life))
    checks.push('real baseline and adjustment auto comparison')
    await page.setViewportSize({width: 1440, height: 1000})
    await page.screenshot({path: root + '/evidence/flow-compare-desktop.png', fullPage: true})
    await page.getByRole('button', {name: '查看完整详情 →', exact: true}).click()
    await page.getByRole('heading', {name: '第三步 · 查看详情'}).waitFor()
    assert.equal(await page.getByLabel('查看方案').locator('option').count(), 2)
    await page.getByRole('button', {name: '导出此方案', exact: true}).click()
    assert.ok((await page.getByLabel('导出的构筑').inputValue()).length > 100)
    await page.screenshot({path: root + '/evidence/flow-details-desktop.png', fullPage: true})
    checks.push('result selection and export')
    await page.getByRole('button', {name: '返回继续调整', exact: true}).click()
    await page.getByRole('heading', {name: '方案对比', exact: true}).waitFor()
    await page.reload({waitUntil: 'domcontentloaded'})
    await page.getByRole('heading', {name: '方案对比', exact: true}).waitFor({timeout: 30000})
    checks.push('back navigation and saved comparison reload')
    assert.deepEqual(errors, [])
    fs.writeFileSync(root + '/evidence/flow-browser.json', JSON.stringify({passed: true, checks, life, errors}, null, 2))
    console.log(JSON.stringify({passed: true, checks, life}))
  } catch (error) {
    await page.screenshot({path: root + '/evidence/flow-failure.png', fullPage: true})
    console.error(String(error)); console.error((await page.locator('body').innerText()).slice(-1800)); process.exitCode = 1
  } finally {await browser.close()}
}
main().catch(e => {console.error(e.message); process.exitCode = 1})

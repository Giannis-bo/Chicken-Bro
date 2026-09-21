// Cloud-only Candidate verification. Never print private codes or cookies.
const {chromium} = require('/opt/chickenbro-candidates/poe2-20260918/runtime/browser/node_modules/playwright')
const fs = require('node:fs'), assert = require('node:assert/strict')
const root = '/opt/chickenbro-candidates/poe2-20260918', origin = 'https://www.chickenbro.cloud'
const out = root + '/evidence/two-step-cn', prefix = origin + '/poe2-candidate/api/v2/poe2'
async function main() {
  const sessions = JSON.parse(fs.readFileSync(root + '/runtime/browser/two-step-cn-sessions.json', 'utf8'))
  const browser = await chromium.launch({headless: true, executablePath: root + '/runtime/browser/chrome-headless-shell-linux64/chrome-headless-shell', args: ['--no-sandbox']})
  const context = await browser.newContext({viewport: {width: 1440, height: 1100}})
  const cookies = row => [{name: '__Host-chickenbro-poe2-candidate-session', value: row.token, url: origin, httpOnly: true, secure: true, sameSite: 'Lax'}, {name: '__Host-chickenbro-poe2-candidate-csrf', value: row.csrf, url: origin, secure: true, sameSite: 'Lax'}]
  await context.addCookies(cookies(sessions.A))
  const page = await context.newPage(), errors = [], postedJobs = []
  page.setDefaultTimeout(90000)
  page.on('pageerror', error => errors.push(error.name))
  page.on('request', request => {if (request.url() === prefix + '/jobs' && request.method() === 'POST') postedJobs.push(request.postDataJSON()?.buildId)})
  try {
    await page.goto(origin + '/poe2-candidate/poe2', {waitUntil: 'domcontentloaded'})
    await page.getByRole('heading', {name: '我的构筑', exact: true}).waitFor()
    await page.getByRole('button', {name: '＋ 导入新构筑', exact: true}).click()
    assert.equal(await page.getByRole('navigation', {name: '构筑操作步骤'}).getByRole('button').count(), 2)
    await page.getByRole('textbox', {name: '构筑分享码', exact: true}).fill(fs.readFileSync(root + '/evidence/link-research/user-ninja-code-20260920.txt', 'utf8').trim())
    const imported = page.waitForResponse(r => r.url() === prefix + '/builds' && r.request().method() === 'POST')
    let importedId = ''
    const treeResponse = page.waitForResponse(r => importedId && r.url() === prefix + '/builds/' + importedId + '/tree' && r.status() === 200)
    await page.getByRole('button', {name: '导入构筑', exact: true}).click()
    const build = await (await imported).json()
    importedId = build.id
    const tree = await (await treeResponse).json()
    assert.equal(tree.buildId, build.id)
    const details = page.getByRole('region', {name: '构筑详情', exact: true})
    await details.waitFor()
    assert.ok((await page.getByRole('region', {name: '已解析角色'}).innerText()).includes('96 级'))
    for (const label of ['力量', '敏捷', '智慧', '精魂', '生命', '技能组']) assert.ok((await details.innerText()).includes(label), label)
    const jobs = (await (await context.request.get(prefix + '/jobs?buildId=' + build.id)).json()).items
    assert.equal(jobs.length, 1); const baseline = jobs[0]
    assert.equal(baseline.status, 'succeeded'); assert.deepEqual(baseline.changes, {})
    assert.equal(baseline.result.inputSha256, build.inputSha256)
    assert.equal(baseline.result.engineVersion, build.engineVersion)
    assert.ok(!postedJobs.includes(build.id), 'import must reuse its completed calculation')
    for (const node of tree.nodes) for (const text of [node.name, ...node.stats]) {
      assert.ok(!/[A-Za-z]{3,}/.test(text), 'untranslated node ' + node.id)
    }
    const panel = page.getByRole('region', {name: '构筑天赋树', exact: true})
    await panel.locator('canvas').waitFor()
    await page.waitForFunction(() => document.querySelector('[data-tree-nodes]')?.getAttribute('data-art-ready') === 'true')
    await page.getByRole('button', {name: '① 导入', exact: true}).scrollIntoViewIfNeeded()
    await page.screenshot({path: out + '/import-desktop.png'})
    await panel.screenshot({path: out + '/tree-desktop.png'})
    const asc = tree.nodes.find(n => n.allocated && n.ascendancy === tree.ascendancy && n.type === 'Notable')
    await page.getByRole('button', {name: /^升华 ·/}).first().click()
    await panel.getByRole('button', {name: new RegExp('#' + asc.id + '$')}).click()
    const nodeDetail = page.getByRole('complementary', {name: '节点详情', exact: true})
    for (const text of [asc.name, ...asc.stats]) assert.ok((await nodeDetail.innerText()).includes(text))
    await panel.screenshot({path: out + '/ascendancy-desktop.png'})
    await page.setViewportSize({width: 390, height: 844})
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
    await panel.screenshot({path: out + '/ascendancy-mobile.png'})
    await page.getByRole('button', {name: '① 导入', exact: true}).scrollIntoViewIfNeeded()
    await page.screenshot({path: out + '/import-mobile.png'})
    await page.setViewportSize({width: 1440, height: 1100})
    await page.getByRole('button', {name: '② 对比', exact: true}).click()
    await page.locator('[data-poe2-field]').filter({hasText: '调整内容'}).locator('select').selectOption('level')
    await page.getByRole('spinbutton', {name: '等级', exact: true}).fill('97')
    const compareResponse = page.waitForResponse(r => r.url() === prefix + '/compare' && r.status() === 200)
    await page.getByRole('button', {name: '计算方案', exact: true}).click()
    const comparison = await (await compareResponse).json()
    assert.equal(comparison.candidateChanges.level, 97)
    await page.getByRole('heading', {name: '方案对比', exact: true}).waitFor()
    assert.equal(await page.getByRole('button', {name: '③ 查看详情', exact: true}).count(), 0)
    const latest = (await (await context.request.get(prefix + '/jobs?buildId=' + build.id)).json()).items
    const candidate = latest.find(j => j.changes.level === 97)
    assert.equal(candidate.status, 'succeeded')
    await page.getByRole('combobox', {name: '查看方案', exact: true}).selectOption(candidate.id)
    await panel.getByText(/当前计算结果的天赋分配/).waitFor()
    await panel.locator('canvas').waitFor()
    await page.getByRole('heading', {name: '方案对比', exact: true}).scrollIntoViewIfNeeded()
    await page.screenshot({path: out + '/compare-desktop.png'})
    await page.getByRole('button', {name: '① 导入', exact: true}).click()
    assert.equal(await page.getByRole('combobox', {name: '查看方案', exact: true}).count(), 0)
    assert.ok((await details.innerText()).includes(baseline.result.stats.Life.toLocaleString('zh-CN', {maximumFractionDigits: 2})))
    const other = await browser.newContext(); await other.addCookies(cookies(sessions.B))
    for (const path of ['/builds/' + build.id, '/jobs/' + baseline.id, '/builds/' + build.id + '/tree']) assert.equal((await other.request.get(prefix + path)).status(), 404)
    await other.close()
    assert.deepEqual(errors, [])
    const report = {passed: true, buildId: build.id, baselineId: baseline.id, candidateId: candidate.id,
      importReusesCalculation: true, twoSteps: true, characterStatsSkillsImmediate: true,
      translatedNodes: tree.nodes.length, translatedEffects: tree.nodes.reduce((s,n) => s+n.stats.length,0),
      ascendancyChinese: true, mobileNoOverflow: true, actualComparison: true, ownerIsolation: true, errors}
    fs.writeFileSync(out + '/browser.json', JSON.stringify(report, null, 2)); console.log(JSON.stringify(report))
  } finally {await browser.close()}
}
main().catch(error => {console.error(error.name + ': ' + error.message.replace(/https?:\/\/\S+/g, '[URL]')); process.exitCode = 1})

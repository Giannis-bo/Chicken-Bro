const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('pve tab uses backend payload and removes legacy ranking sections', () => {
  const js = fs.readFileSync('pages/pve/pve.js', 'utf8')
  const wxml = fs.readFileSync('pages/pve/pve.wxml', 'utf8')

  assert.match(js, /requestPveHome/)
  assert.match(js, /fallbackPveHome/)
  assert.doesNotMatch(wxml, /class="metrics"/)
  assert.doesNotMatch(wxml, /大秘境榜单 top3/)
  assert.doesNotMatch(wxml, /wx:for="\{\{tasks\}\}"/)
})

test('pve page opens each zone module as a detail page instead of expanding records inline', () => {
  const app = JSON.parse(fs.readFileSync('app.json', 'utf8'))
  const js = fs.readFileSync('pages/pve/pve.js', 'utf8')
  const wxml = fs.readFileSync('pages/pve/pve.wxml', 'utf8')

  assert.ok(app.pages.includes('pages/pve/detail'))
  assert.match(wxml, /bindtap="openPveModule"/)
  assert.match(wxml, /data-key="\{\{module\.key\}\}"/)
  assert.match(wxml, /module\.itemCount/)
  assert.doesNotMatch(wxml, /wx:for="\{\{module\.items\}\}"/)
  assert.match(js, /openPveModule\(event\)/)
  assert.match(js, /wx\.navigateTo/)
  assert.match(js, /pages\/pve\/detail\?module=/)
})

test('pve backend payload exposes mythic plus and raid zones', () => {
  const { buildPveHomePayload } = require('../server/pve/home-payload')
  const payload = buildPveHomePayload()

  assert.equal(payload.navTitle, '副本')
  assert.equal(payload.metrics, undefined)
  assert.equal(payload.title, '大秘境与团队 Raid')
  assert.match(payload.desc, /当前赛季/)
  assert.equal(payload.currentSeason, '至暗之夜 Season 1')
  assert.doesNotMatch(JSON.stringify(payload), /The War Within/)
  assert.doesNotMatch(JSON.stringify(payload), /season-tww/)
  assert.deepEqual(
    payload.zones.map((zone) => zone.title),
    ['大秘境专区', '团队 raid 专区']
  )
  assert.deepEqual(
    payload.zones[0].modules.map((module) => module.title),
    ['队伍天梯', '职业天梯', '赛季副本']
  )
  assert.deepEqual(
    payload.zones[1].modules.map((module) => module.title),
    ['首杀战报', 'boss攻略']
  )
})

test('every pve zone module exposes real source-backed records', () => {
  const { buildPveHomePayload, getPveModuleDetail } = require('../server/pve/home-payload')
  const payload = buildPveHomePayload()
  const modules = payload.zones.flatMap((zone) => zone.modules)

  assert.equal(modules.length, 5)

  for (const module of modules) {
    assert.ok(Array.isArray(module.items), `${module.title} should expose records`)
    assert.ok(module.items.length > 0, `${module.title} should not be an empty entry`)
    assert.equal(module.itemCount, module.items.length)

    const detail = getPveModuleDetail(module.key)
    assert.equal(detail.key, module.key)
    assert.deepEqual(detail.items, module.items)

    for (const item of module.items) {
      assert.match(item.title, /\S/, `${module.title} item should have title`)
      assert.match(item.value, /\S/, `${module.title} item should have value`)
      assert.match(item.desc, /\S/, `${module.title} item should have desc`)
      assert.match(item.sourceName, /\S/, `${module.title} item should have sourceName`)
      assert.match(item.sourceUrl, /^https:\/\//, `${module.title} item should have sourceUrl`)
      assert.match(item.publishedAt, /^\d{4}-\d{2}-\d{2}$/, `${module.title} item should have publishedAt`)
      assert.match(item.analysisWindow, /\S/, `${module.title} item should have analysisWindow`)
    }
  }
})

test('pve detail page renders the selected module records and source evidence', () => {
  const js = fs.readFileSync('pages/pve/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/pve/detail.wxml', 'utf8')
  const json = JSON.parse(fs.readFileSync('pages/pve/detail.json', 'utf8'))

  assert.deepEqual(json.usingComponents, {
    'navigation-bar': '/components/navigation-bar/navigation-bar'
  })
  assert.match(js, /requestPveModule/)
  assert.match(js, /fallbackPveModule/)
  assert.match(js, /onLoad\(options\)/)
  assert.match(js, /options\.module/)
  assert.match(wxml, /wx:for="\{\{activeModule\.items\}\}"/)
  assert.match(wxml, /record\.title/)
  assert.match(wxml, /record\.value/)
  assert.match(wxml, /record\.desc/)
  assert.match(wxml, /record\.sourceName/)
  assert.match(wxml, /record\.publishedAt/)
  assert.match(wxml, /record\.analysisWindow/)
})

test('pve home and detail pages use a Horde visual palette', () => {
  const homeWxml = fs.readFileSync('pages/pve/pve.wxml', 'utf8')
  const homeCss = fs.readFileSync('pages/pve/pve.wxss', 'utf8')
  const detailWxml = fs.readFileSync('pages/pve/detail.wxml', 'utf8')
  const detailCss = fs.readFileSync('pages/pve/detail.wxss', 'utf8')
  const combined = `${homeWxml}\n${homeCss}\n${detailWxml}\n${detailCss}`

  assert.match(homeWxml, /background="#7A1116"/)
  assert.match(homeWxml, /color="#FFFFFF"/)
  assert.match(detailWxml, /background="#7A1116"/)
  assert.match(homeCss, /\.pve-hero[\s\S]*#7a1116/i)
  assert.match(homeCss, /\.pve-hero[\s\S]*#1d080a/i)
  assert.match(homeCss, /\.module-footer[\s\S]*#d7a33d/i)
  assert.match(detailCss, /\.detail-hero[\s\S]*#7a1116/i)
  assert.match(detailCss, /\.detail-hero[\s\S]*#1d080a/i)
  assert.match(detailCss, /\.record-value[\s\S]*#d7a33d/i)
  assert.doesNotMatch(combined, /#214f57/i)
  assert.doesNotMatch(combined, /#2f6b64/i)
})

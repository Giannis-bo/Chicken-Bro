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
  assert.equal(payload.currentSeason.seasonLabel, '至暗之夜 Season 1')
  assert.equal(payload.seasonLabel, '至暗之夜 Season 1')
  assert.match(payload.seasonRevision, /^season-midnight-season-1-/)
  assert.equal(payload.dataStatus, 'verified')
  assert.equal(payload.currentSeason.dungeons.length, 8)
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
    if (module.key === 'specLadder') {
      assert.ok(module.itemCount > module.items.length)
    } else {
      assert.equal(module.itemCount, module.items.length)
    }

    const detail = getPveModuleDetail(module.key)
    assert.equal(detail.key, module.key)
    assert.deepEqual(detail.items, module.items)
    assert.equal(detail.seasonRevision, payload.seasonRevision)
    assert.equal(detail.currentSeason.seasonRevision, payload.seasonRevision)

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

test('spec ladder payload exposes role-based Archon tiers and WCL details', () => {
  const { getPveModuleDetail } = require('../server/pve/home-payload')
  const detail = getPveModuleDetail('specLadder')

  assert.deepEqual(
    detail.roles.map((role) => role.key),
    ['dps', 'tank', 'healer']
  )
  assert.equal(detail.defaultRole, 'dps')
  assert.equal(detail.sourceName, 'Archon / Warcraft Logs')
  assert.equal(
    detail.itemCount,
    detail.roles.reduce((sum, role) => sum + role.count, 0)
  )
  assert.equal(detail.roles.find((role) => role.key === 'dps').active, true)
  assert.ok(detail.roles.every((role) => role.count > 0))
  assert.ok(detail.roles.every((role) => /^\d{4}-\d{2}-\d{2}$/.test(role.updatedAt)))

  for (const role of detail.roles) {
    const summary = detail.archonTierSummary[role.key]
    assert.equal(summary.sourceName, 'Archon')
    assert.match(summary.sourceUrl, /^https:\/\/www\.archon\.gg\/wow\/tier-list\//)
    assert.match(summary.analysisWindow, /\S/)
    assert.ok(summary.tiers.length > 0)

    for (const tier of summary.tiers) {
      assert.match(tier.tier, /^[SABC]$/)
      assert.ok(tier.items.length > 0)
      for (const item of tier.items) {
        assert.match(item.specId, /^[a-z]+-[a-z_]+$/)
        assert.match(item.className, /\S/)
        assert.match(item.specName, /\S/)
        assert.equal(item.gameAsset.entityType, 'playable_spec')
        assert.equal(item.gameAsset.entityId, item.specId)
        assert.equal(item.gameAsset.iconUrl, item.iconUrl)
        assert.equal(item.gameAsset.resolutionTier, 'icon_56')
        assert.equal(item.gameAsset.source, 'static_icon_name')
        assert.equal(item.gameAsset.status, 'fallback')
        assert.ok(item.gameAsset.semanticTags.includes('pve'))
        assert.ok(item.gameAsset.usage.includes('pve_spec_ladder'))
        assert.match(item.scoreLabel, /M\+ Score/)
        assert.ok(item.score > 0)
        assert.ok(item.sampleCount > 0)
        assert.equal(item.sourceName, 'Archon')
        assert.match(item.sourceUrl, /^https:\/\/www\.archon\.gg\/wow\/builds\//)
        assert.ok(Object.prototype.hasOwnProperty.call(detail.wclDetailsBySpec, item.specId))
        assert.equal(detail.wclDetailsBySpec[item.specId].role, role.key)
        assert.equal(detail.wclDetailsBySpec[item.specId].specId, item.specId)
      }
    }
  }

  const firstDps = detail.archonTierSummary.dps.tiers[0].items[0]
  const wcl = detail.wclDetailsBySpec[firstDps.specId]
  assert.equal(detail.selectedSpecId, firstDps.specId)
  assert.equal(wcl.sourceName, 'Warcraft Logs')
  assert.match(wcl.sourceUrl, /^https:\/\/www\.warcraftlogs\.com\/zone\/statistics\/47/)
  assert.equal(wcl.sourceStatus, 'verified')
  assert.ok(wcl.score > 0)
  assert.ok(wcl.max >= wcl.score)
  assert.ok(wcl.parses > 0)
  assert.ok(wcl.distribution.p95 >= wcl.distribution.p50)

  assert.deepEqual(
    detail.sourceChecks.map((source) => source.key),
    ['archon', 'warcraftlogs']
  )
  for (const source of detail.sourceChecks) {
    assert.match(source.domain, /^(archon\.gg|warcraftlogs\.com)$/)
    assert.match(source.checkedAt, /^\d{4}-\d{2}-\d{2}/)
    assert.match(source.analysisWindow, /\S/)
    assert.equal(source.status, 'verified')
    assert.ok(source.sampleCount > 0)
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

test('spec ladder detail page renders role tabs, Archon board, WCL statistics rows, and source checks', () => {
  const js = fs.readFileSync('pages/pve/detail.js', 'utf8')
  const wxml = fs.readFileSync('pages/pve/detail.wxml', 'utf8')
  const css = fs.readFileSync('pages/pve/detail.wxss', 'utf8')

  assert.match(js, /selectSpecLadderRole\(event\)/)
  assert.match(js, /selectSpecLadderSpec\(event\)/)
  assert.match(js, /prepareSpecLadderState/)
  assert.match(js, /activeWclRows/)
  assert.match(js, /wclRangeStyle/)
  assert.match(js, /wclBoxStyle/)
  assert.match(js, /wclScoreDotStyle/)
  assert.match(wxml, /wx:if="\{\{isSpecLadder\}\}"/)
  assert.match(wxml, /class="role-tabs"/)
  assert.match(wxml, /bindtap="selectSpecLadderRole"/)
  assert.match(wxml, /wx:if="\{\{activeRoleMeta\.updatedAt\}\}"/)
  assert.match(wxml, /class="archon-tier-board"/)
  assert.match(wxml, /activeArchonTiers/)
  assert.match(wxml, /bindtap="selectSpecLadderSpec"/)
  assert.match(wxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(wxml, /item\.iconUrl/)
  assert.match(wxml, /class="wcl-stat-board"/)
  assert.match(wxml, /class="wcl-filter-bars"/)
  assert.match(wxml, /class="wcl-filter-row primary"/)
  assert.match(wxml, /class="wcl-filter-row secondary"/)
  assert.match(wxml, /class="wcl-chart-table"/)
  assert.match(wxml, /class="wcl-chart-head"/)
  assert.match(wxml, /class="wcl-chart-row \{\{item\.rowClass\}\}"/)
  assert.match(wxml, /wx:for="\{\{activeWclRows\}\}"/)
  assert.match(wxml, /item\.wclRangeStyle/)
  assert.match(wxml, /item\.wclBoxStyle/)
  assert.match(wxml, /item\.wclMedianStyle/)
  assert.match(wxml, /item\.wclScoreDotStyle/)
  assert.match(wxml, /item\.scoreText/)
  assert.match(wxml, /item\.maxText/)
  assert.match(wxml, /item\.parsesText/)
  assert.match(wxml, /Points/)
  assert.match(wxml, /Normalized Scores/)
  assert.doesNotMatch(wxml, /class="wcl-detail-panel"/)
  assert.doesNotMatch(wxml, /wcl-filter-grid/)
  assert.doesNotMatch(wxml, /wcl-stat-row/)
  assert.match(wxml, /class="source-check-list"/)
  assert.match(wxml, /activeModule\.sourceChecks/)
  assert.match(wxml, /class="source-box" wx:if="\{\{!isSpecLadder\}\}"/)

  assert.match(css, /\.role-tabs/)
  assert.match(css, /\.archon-tier-board/)
  assert.match(css, /\.tier-label\.tier-s/)
  assert.match(css, /\.spec-pill\.active/)
  assert.match(css, /\.wcl-stat-board/)
  assert.match(css, /\.wcl-filter-bars/)
  assert.match(css, /\.wcl-filter-row\.primary/)
  assert.match(css, /\.wcl-chart-table/)
  assert.match(css, /\.wcl-chart-row/)
  assert.doesNotMatch(css, /\.wcl-filter-grid/)
  assert.doesNotMatch(css, /\.wcl-stat-row/)
  assert.match(css, /\.wcl-range-track/)
  assert.match(css, /\.wcl-range-line/)
  assert.match(css, /\.wcl-range-box/)
  assert.match(css, /\.wcl-score-dot/)
  assert.match(css, /\.source-check-list/)
})

test('pve home and detail pages use a dark competitive dungeon palette', () => {
  const homeWxml = fs.readFileSync('pages/pve/pve.wxml', 'utf8')
  const homeCss = fs.readFileSync('pages/pve/pve.wxss', 'utf8')
  const detailWxml = fs.readFileSync('pages/pve/detail.wxml', 'utf8')
  const detailCss = fs.readFileSync('pages/pve/detail.wxss', 'utf8')
  const combined = `${homeWxml}\n${homeCss}\n${detailWxml}\n${detailCss}`

  assert.match(homeWxml, /background="#111111"/)
  assert.match(homeWxml, /color="#FFFFFF"/)
  assert.match(detailWxml, /background="#111111"/)
  assert.match(homeCss, /\.pve-hero[\s\S]*#7a1116/i)
  assert.match(homeCss, /\.pve-hero[\s\S]*#060606/i)
  assert.match(homeCss, /\.module-footer[\s\S]*#f8b700/i)
  assert.match(detailCss, /\.detail-hero[\s\S]*#7a1116/i)
  assert.match(detailCss, /\.detail-hero[\s\S]*#060606/i)
  assert.match(detailCss, /\.record-value[\s\S]*#f8b700/i)
  assert.match(homeCss, /\.zone-item[\s\S]*border-radius:\s*16rpx;/)
  assert.doesNotMatch(combined, /#214f57/i)
  assert.doesNotMatch(combined, /#2f6b64/i)
})

test('mini program game image entries render through gameAsset while avatars stay user media', () => {
  const gameWxml = [
    'pages/builds/detail.wxml',
    'pages/builds/talent-simulator.wxml',
    'pages/pve/detail.wxml'
  ].map((file) => fs.readFileSync(file, 'utf8')).join('\n')
  const profileWxml = fs.readFileSync('pages/profile/profile.wxml', 'utf8')

  assert.match(gameWxml, /item\.gameAsset\.iconUrl/)
  assert.doesNotMatch(gameWxml, /<image[^>]+item\.iconUrl/)
  assert.match(profileWxml, /user\.avatarUrl/)
})

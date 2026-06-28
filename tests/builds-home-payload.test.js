const test = require('node:test')
const assert = require('node:assert/strict')

const {
  buildSpecializationHomePayload,
  buildSpecializationIntelPayload,
  getSpecializationDetail,
  queryTypes,
  trustedBuildSources
} = require('../server/builds/home-payload')

test('builds the specialization tab payload without legacy BD metrics', () => {
  const payload = buildSpecializationHomePayload()

  assert.equal(payload.navTitle, '职业专精')
  assert.equal(payload.title, '职业专精')
  assert.match(payload.desc, /最高端/)
  assert.equal(payload.metrics, undefined)
  assert.deepEqual(
    payload.quickActions.map((action) => action.key),
    ['talents', 'gear', 'simc', 'tasks']
  )
  assert.equal(payload.featuredSpecializations.length, 0)
  assert.equal(payload.classOptions.length, 13)
  assert.equal(payload.classOptions.flatMap((item) => item.specializations).length, 40)
  assert.equal(payload.specializations, undefined)
  assert.ok(
    Buffer.byteLength(JSON.stringify(payload), 'utf8') < 45000,
    'builds home payload should stay below the WeChat setData warning range'
  )
  assert.equal(payload.currentSeason.seasonLabel, '至暗之夜 Season 1')
  assert.match(payload.seasonRevision, /^season-midnight-season-1-/)
  assert.equal(payload.dataStatus, 'verified')
})

test('builds a complete specialization intel payload for the view-all page', () => {
  const homePayload = buildSpecializationHomePayload()
  const intelPayload = buildSpecializationIntelPayload()

  assert.equal(intelPayload.navTitle, '热门专精')
  assert.equal(intelPayload.title, '热门专精资讯')
  assert.equal(intelPayload.items.length, 5)
  assert.equal(homePayload.featuredSpecializations.length, 0)
  assert.ok(intelPayload.items.length > homePayload.featuredSpecializations.length)
  assert.equal(intelPayload.seasonRevision, homePayload.seasonRevision)

  for (const item of intelPayload.items) {
    assert.match(item.id, /\S/)
    assert.match(item.title, /\S/)
    assert.match(item.sourceName, /\S/)
    assert.match(item.sourceUrl, /^https:\/\//)
    assert.match(item.publishedAt, /^\d{4}-\d{2}-\d{2}$/)
    assert.match(item.analysisWindow, /\S/)
  }
})

test('dormant specialization intel payload keeps strict source evidence', () => {
  const payload = buildSpecializationIntelPayload()

  for (const specialization of payload.items) {
    assert.match(specialization.id, /\S/)
    assert.match(specialization.title, /\S/)
    assert.match(specialization.sourceName, /\S/)
    assert.match(specialization.sourceUrl, /^https:\/\//)
    assert.match(specialization.publishedAt, /^\d{4}-\d{2}-\d{2}$/)
    assert.match(specialization.analysisWindow, /\S/)
    assert.match(specialization.sourceNote, /\S/)
  }
})

test('specialization payload exposes WebSim class and spec keys', () => {
  const payload = buildSpecializationHomePayload()
  const specializations = payload.classOptions.flatMap((item) => item.specializations)
  const byId = Object.fromEntries(specializations.map((item) => [item.id, item]))

  assert.equal(byId['死亡骑士-冰霜'].websimClassKey, 'deathknight')
  assert.equal(byId['死亡骑士-冰霜'].websimSpecKey, 'frost')
  assert.equal(byId['猎人-野兽控制'].websimClassKey, 'hunter')
  assert.equal(byId['猎人-野兽控制'].websimSpecKey, 'beast_mastery')

  const frostMage = getSpecializationDetail('法师-冰霜')
  assert.equal(frostMage.websimClassKey, 'mage')
  assert.equal(frostMage.websimSpecKey, 'frost')
})

test('trusted source allowlist covers high-end mythic plus raid and WCL analysis', () => {
  assert.ok(trustedBuildSources.some((source) => source.name === 'Raider.IO'))
  assert.ok(trustedBuildSources.some((source) => source.name === 'Warcraft Logs'))
  assert.ok(trustedBuildSources.some((source) => source.name === 'Archon'))
  assert.ok(trustedBuildSources.some((source) => source.name === 'Subcreation'))
})

test('details expose all query types for every specialization', () => {
  const payload = buildSpecializationHomePayload()
  const specializations = payload.classOptions.flatMap((item) => item.specializations)

  for (const specialization of specializations) {
    const detail = getSpecializationDetail(specialization.id)

    assert.equal(detail.id, specialization.id)
    assert.equal(detail.seasonRevision, payload.seasonRevision)
    assert.equal(detail.currentSeason.seasonRevision, payload.seasonRevision)
    assert.deepEqual(Object.keys(detail.details).sort(), queryTypes.map((item) => item.key).sort())

    for (const queryType of queryTypes) {
      const section = detail.details[queryType.key]
      assert.match(section.title, /\S/)
      assert.ok(section.items.length > 0)
      assert.match(section.sourceName, /\S/)
      assert.match(section.sourceUrl, /^https:\/\//)
      assert.match(section.sourceNote, /\S/)
    }
  }
})

test('frost mage details use retrieved source-backed data instead of placeholders', () => {
  const detail = getSpecializationDetail('法师-冰霜')

  assert.match(detail.details.talents.importCode, /^CAE/)
  assert.match(detail.details.talents.sourceUrl, /wowhead\.com/)
  assert.deepEqual(
    detail.details.talents.coreTalents,
    ['Freezing Rain', 'Splitting Ice', 'Fractured Frost', 'Splintering Ray', 'Thermal Void']
  )
  assert.ok(detail.details.gear.gear.some((item) => item.name === 'Gaze of the Alnseer'))
  assert.ok(detail.details.gear.gear.some((item) => item.name === "Vaelgor's Final Stare"))
  assert.ok(detail.details.statWeights.stats.length >= 5)
  assert.equal(detail.details.statWeights.stats[0].name, 'Intellect')
  assert.ok(detail.details.rotation.rotation.some((item) => /Ray of Frost/.test(item.action)))

  for (const section of Object.values(detail.details)) {
    const text = JSON.stringify(section)
    assert.doesNotMatch(text, /需要由定时任务/)
    assert.doesNotMatch(text, /优先展示/)
    assert.doesNotMatch(text, /当前样本下/)
  }
})

test('all intel specializations have real module data without local placeholders', () => {
  const intelPayload = buildSpecializationIntelPayload()
  const placeholderPattern = /本地尚未写入|请以详情页来源字段|已完成检索的专精|装备列表按|属性模块需要|循环拆分为/

  for (const specialization of intelPayload.items) {
    const detail = getSpecializationDetail(specialization.id)

    assert.ok(detail.details.talents.coreTalents.length >= 4, `${specialization.id} should have core talents`)
    assert.ok(detail.details.gear.gear.length >= 4, `${specialization.id} should have gear rows`)
    assert.ok(detail.details.statWeights.stats.length >= 5, `${specialization.id} should have stat rows`)
    assert.ok(detail.details.rotation.rotation.length >= 3, `${specialization.id} should have rotation rows`)

    for (const section of Object.values(detail.details)) {
      const text = JSON.stringify(section)
      assert.doesNotMatch(text, placeholderPattern, `${specialization.id} should not use placeholder copy`)
      assert.match(section.sourceUrl, /^https:\/\//)
      assert.match(section.analysisWindow, /\S/)
    }
  }
})

test('all 40 specializations expose structured source-backed data without placeholders', () => {
  const payload = buildSpecializationHomePayload()
  const specializations = payload.classOptions.flatMap((item) => item.specializations)
  const placeholderPattern = /本地尚未写入|请以详情页来源字段|已完成检索的专精|装备列表按|属性模块需要|循环拆分为|暂无|待补充/

  assert.equal(specializations.length, 40)

  const devourer = specializations.find((item) => item.websimClassKey === 'demonhunter' && item.websimSpecKey === 'devourer')
  assert.ok(devourer, 'builds home should expose Devourer Demon Hunter')
  assert.equal(devourer.className, '恶魔猎手')
  assert.equal(devourer.specName, '噬灭')
  assert.equal(devourer.role, '近战输出')

  for (const specialization of specializations) {
    const detail = getSpecializationDetail(specialization.id)

    assert.ok(detail.details.talents.coreTalents.length >= 4, `${specialization.id} should have talent highlights`)
    assert.ok(detail.details.gear.gear.length >= 4, `${specialization.id} should have gear source rows`)
    assert.ok(detail.details.statWeights.stats.length >= 5, `${specialization.id} should have stat priority rows`)
    assert.ok(detail.details.rotation.rotation.length >= 3, `${specialization.id} should have rotation phases`)

    for (const section of Object.values(detail.details)) {
      const text = JSON.stringify(section)
      assert.doesNotMatch(text, placeholderPattern, `${specialization.id} should not expose placeholder copy`)
      assert.match(section.sourceName, /\S/)
      assert.match(section.sourceUrl, /^https:\/\//)
      assert.match(section.publishedAt, /^\d{4}-\d{2}-\d{2}$/)
      assert.match(section.analysisWindow, /\S/)
      assert.match(section.sourceNote, /\S/)
    }
  }
})

test('non-featured specializations use retrieved Archon snapshot data', () => {
  const fireMage = getSpecializationDetail('法师-火焰')
  const furyWarrior = getSpecializationDetail('战士-狂怒')

  assert.deepEqual(
    fireMage.details.statWeights.stats.map((item) => item.name),
    ['Intellect', 'Haste', 'Mastery', 'Vers', 'Crit']
  )
  assert.ok(fireMage.details.gear.gear.some((item) => item.name === "Voidbreaker's Veil"))
  assert.ok(fireMage.details.gear.gear.some((item) => item.metadataStatus === 'source_reference' && item.isReference))
  assert.match(fireMage.details.talents.analysisWindow, /推荐树热度 10\.8%/)
  assert.match(fireMage.details.talents.analysisWindow, /最高样本 \+21/)

  assert.deepEqual(
    furyWarrior.details.statWeights.stats.map((item) => item.name),
    ['Strength', 'Haste', 'Mastery', 'Crit', 'Vers']
  )
  assert.ok(furyWarrior.details.gear.gear.some((item) => item.name === "Night Ender's Tusks"))
  assert.match(furyWarrior.details.talents.analysisWindow, /推荐树热度 59\.9%/)
  assert.match(furyWarrior.details.talents.analysisWindow, /最高样本 \+23/)
})

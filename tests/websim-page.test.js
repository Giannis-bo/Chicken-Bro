const fs = require('node:fs')
const test = require('node:test')
const assert = require('node:assert/strict')

test('websim static page exposes the three planned modules and api hooks', () => {
  const html = fs.readFileSync('websim/index.html', 'utf8')
  const js = fs.readFileSync('websim/app.js', 'utf8')
  const css = fs.readFileSync('websim/app.css', 'utf8')

  assert.match(html, /天赋模拟器/)
  assert.match(html, /装备模拟器/)
  assert.match(html, /装备查询/)
  assert.match(html, /SimC 构筑工坊/)
  assert.match(html, /赛季校验中/)
  assert.match(html, /职业/)
  assert.match(html, /专精/)
  assert.match(html, /首领掉落/)
  assert.doesNotMatch(html, />Class</)
  assert.doesNotMatch(html, />Spec</)
  assert.match(js, /dataStatus/)
  assert.match(js, /赛季数据尚未通过暴雪官方 API 校验/)
  assert.match(js, /\/api\/websim\/bootstrap/)
  assert.match(js, /\/api\/websim\/talents/)
  assert.match(js, /\/api\/websim\/gear/)
  assert.match(js, /\/api\/websim\/loot/)
  assert.match(js, /\/api\/websim\/profile/)
  assert.match(js, /\/api\/websim\/simulate/)
  assert.match(css, /\.armory-layout/)
  assert.match(css, /\.journal-layout/)
  assert.match(css, /\.talent-tree/)
})

test('websim frontend helpers normalize gear and filter dungeon loot', () => {
  const helpers = require('../websim/app')
  const normalized = helpers.normalizeGearItem({
    itemId: 249343,
    slot: 'trinket1',
    name: 'Gaze of the Alnseer',
    enchantId: 123
  })

  assert.equal(normalized.itemId, '249343')
  assert.equal(normalized.slot, 'trinket1')
  assert.equal(normalized.name, 'Gaze of the Alnseer')

  const normalizedLootRow = helpers.normalizeGearItem({
    id: 'boss-1:249343',
    itemId: 249343,
    slot: 'trinket1',
    name: 'Gaze of the Alnseer'
  })
  assert.equal(normalizedLootRow.itemId, '249343')

  const rows = helpers.filterLootRows(
    [
      { instanceId: 'a', encounterId: 'boss-1', name: 'Gaze of the Alnseer', encounterName: 'Chimaerus' },
      { instanceId: 'b', encounterId: 'boss-2', name: 'Skybreaker Blade', encounterName: 'Zuraal' }
    ],
    { instanceId: 'a', q: 'gaze' }
  )

  assert.equal(rows.length, 1)
  assert.equal(rows[0].encounterName, 'Chimaerus')
})

const test = require('node:test')
const assert = require('node:assert/strict')

const {
  buildNewsHomePayload,
  createRefreshState,
  shouldAutoRefresh,
  trustedSources
} = require('../server/news/home-payload')

const article = (overrides) => ({
  id: 'news-1',
  title: 'War Within Season 3 tuning notes',
  summary: 'Class tuning and season changes collected for players.',
  channel: '正式服动态',
  category: '正式服',
  tags: ['class-change'],
  importance: 90,
  sourceName: 'Blizzard News',
  sourceUrl: 'https://worldofwarcraft.blizzard.com/news',
  publishedAt: '2026-06-09',
  sourceNote: 'Official World of Warcraft news page.',
  originalTitle: 'War Within Season 3 tuning notes',
  bodyZh: '中文正文：暴雪发布了完整的赛季调优说明，正文详细解释职业改动、赛季内容和玩家需要关注的时间点。\n\n这段内容用于验证前端不会把一句摘要当作完整正文展示。',
  bodyBlocksZh: [
    { type: 'paragraph', text: '暴雪发布了完整的赛季调优说明，正文详细解释职业改动。' },
    { type: 'heading', text: '职业' },
    { type: 'paragraph', text: '玩家可以关注正式服近期调整和时间点。' }
  ],
  tagItems: [{ id: 'class-change', label: '职业调整' }],
  contentStatus: 'ready',
  translationStatus: 'llm',
  translationFidelity: 'source_translation',
  verificationStatus: 'official_verified',
  licenseStatus: 'approved',
  sourceTier: 'official',
  sourceBadges: ['官方已核验', '全文翻译'],
  canonicalTopicId: 'news:24200001',
  readingMeta: { bodyBlockCount: 3 },
  ...overrides
})

test('builds the news home payload expected by the first tab', () => {
  const payload = buildNewsHomePayload([
    article({ id: 'a', importance: 100, channel: '正式服动态' }),
    article({ id: 'b', importance: 95, channel: '测试服前瞻', tags: ['ptr', 'class-change'] }),
    article({ id: 'c', importance: 90, channel: '职业强度变化', tags: ['class-change'] }),
    article({ id: 'd', importance: 40, channel: '正式服动态' })
  ], {
    lastRefreshedAt: '2026-06-09T08:00:00.000+08:00',
    refreshMode: 'scheduled'
  })

  assert.equal(payload.navTitle, '最新资讯')
  assert.equal(payload.heroNews.length, 3)
  assert.deepEqual(
    payload.channels.map((channel) => channel.title),
    ['正式服动态', '测试服前瞻', '职业强度变化']
  )
  assert.deepEqual(
    payload.metrics.map((metric) => metric.label),
    ['今日更新', '职业变动', '测试服重点']
  )
  assert.ok(payload.highlights.length >= 3)
})

test('keeps source and publication evidence on every visible story', () => {
  const payload = buildNewsHomePayload([
    article({ id: 'a', importance: 100 }),
    article({ id: 'b', importance: 95, channel: '测试服前瞻', tags: ['ptr'] }),
    article({ id: 'c', importance: 90, channel: '职业强度变化', tags: ['class-change'] })
  ])

  for (const story of [...payload.heroNews, ...payload.highlights]) {
    assert.match(story.sourceName, /\S/)
    assert.match(story.sourceUrl, /^https:\/\//)
    assert.match(story.publishedAt, /^\d{4}-\d{2}-\d{2}$/)
    assert.match(story.sourceNote, /\S/)
    assert.equal(story.contentStatus, 'ready')
    assert.match(story.originalTitle, /\S/)
    assert.match(story.bodyZh, /中文正文/)
    assert.ok(story.bodyZh.length > story.summary.length)
    assert.equal(story.translationStatus, 'llm')
    assert.equal(story.translationFidelity, 'source_translation')
    assert.equal(story.verificationStatus, 'official_verified')
    assert.equal(story.licenseStatus, 'approved')
    assert.equal(story.sourceTier, 'official')
    assert.deepEqual(story.sourceBadges, ['官方已核验', '全文翻译'])
    assert.equal(story.bodyBlocksZh.length, 3)
    assert.equal(story.canonicalTopicId, 'news:24200001')
    assert.equal(story.readingMeta.bodyBlockCount, 3)
    assert.deepEqual(story.tagItems, [{ id: 'class-change', label: '职业调整' }])
    assert.equal(story.originalBody, undefined)
    assert.equal(story.originalSummary, undefined)
  }
})

test('drops stories from untrusted, incomplete, or not-ready source records', () => {
  const payload = buildNewsHomePayload([
    article({ id: 'trusted' }),
    article({ id: 'bad-source', sourceName: 'Random Blog', sourceUrl: 'https://example.com/wow' }),
    article({ id: 'missing-date', publishedAt: '' }),
    article({ id: 'missing-body', bodyZh: '' }),
    article({ id: 'missing-blocks', bodyBlocksZh: [] }),
    article({ id: 'seed-translation', translationStatus: 'seed' }),
    article({ id: 'missing-source-fidelity', translationFidelity: '' }),
    article({ id: 'unverified', verificationStatus: 'unverified_blocked' }),
    article({ id: 'license-blocked', licenseStatus: 'reference_only' }),
    article({ id: 'summary-as-body', bodyZh: 'Class tuning and season changes collected for players.' }),
    article({ id: 'missing-tags', tagItems: [], tags: [] }),
    article({ id: 'blocked', contentStatus: 'blocked' })
  ])

  assert.deepEqual(payload.highlights.map((story) => story.id), ['trusted'])
})

test('keeps trusted stories when URL constructor is unavailable in webview runtime', () => {
  const originalUrl = global.URL
  global.URL = undefined

  try {
    const payload = buildNewsHomePayload([
      article({
        id: 'webview-compatible',
        sourceUrl: 'https://worldofwarcraft.blizzard.com/en-us/news/24266797/the-midnight-revelations-content-update-goes-live-17-june'
      })
    ])

    assert.equal(payload.metrics[0].value, '1')
    assert.equal(payload.highlights[0].id, 'webview-compatible')
  } finally {
    global.URL = originalUrl
  }
})

test('supports daily scheduled refresh metadata', () => {
  assert.ok(trustedSources.length >= 3)
  assert.equal(
    shouldAutoRefresh('2026-06-09T08:00:00.000+08:00', '2026-06-09T21:00:00.000+08:00'),
    false
  )
  assert.equal(
    shouldAutoRefresh('2026-06-09T08:00:00.000+08:00', '2026-06-10T08:01:00.000+08:00'),
    true
  )

  const state = createRefreshState('scheduled', '2026-06-10T08:01:00.000+08:00')
  assert.equal(state.refreshMode, 'scheduled')
  assert.equal(state.lastRefreshedAt, '2026-06-10T08:01:00.000+08:00')
})

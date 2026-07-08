const {
  fallbackPayload,
  rememberRefreshTime,
  requestNewsHome,
  shouldRefreshToday
} = require('./news-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { syncTabBarSelected } = require('../common/tabbar-sync')

function uniqueCount(values) {
  const seen = {}
  ;(values || []).forEach((value) => {
    const text = String(value || '').trim()
    if (text) seen[text] = true
  })
  return Object.keys(seen).length
}

function pad2(value) {
  return String(value).padStart(2, '0')
}

function formatDateTimeShort(value) {
  const text = String(value || '').trim()
  if (!text) return '未记录'
  const date = new Date(text)
  if (!Number.isFinite(date.getTime())) {
    return text.replace('T', ' ').replace(/([+-]\d{2}:\d{2}|Z)$/, '').slice(0, 16)
  }
  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

function formatDateShort(value) {
  const text = String(value || '').trim()
  if (!text) return '未记录'
  const date = new Date(text)
  if (!Number.isFinite(date.getTime())) {
    return text.replace('T', ' ').replace(/([+-]\d{2}:\d{2}|Z)$/, '').slice(5, 16)
  }
  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

function formatRelativeShort(value) {
  const text = String(value || '').trim()
  if (!text) return '未记录'
  const date = new Date(text)
  if (!Number.isFinite(date.getTime())) return formatDateShort(text)
  const diffMs = Date.now() - date.getTime()
  if (!Number.isFinite(diffMs) || diffMs < 0) return formatDateShort(text)
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 5) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  return formatDateShort(text)
}

function refreshModeLabel(mode, fromFallback) {
  if (fromFallback) return '本地缓存'
  const key = String(mode || '').trim()
  if (key === 'scheduled') return '定时更新'
  if (key === 'cached') return '最近缓存'
  if (key === 'manual') return '手动更新'
  return '已更新'
}

function firstNonEmpty(...values) {
  for (const value of values) {
    const text = String(value || '').trim()
    if (text) return text
  }
  return ''
}

function visualUrlForArticle(source) {
  const item = source || {}
  return firstNonEmpty(
    item.imageUrl,
    item.coverUrl,
    item.thumbnailUrl,
    item.thumbnail,
    item.heroImageUrl,
    item.image
  )
}

function visualTextForArticle(source) {
  const item = source || {}
  return firstNonEmpty(
    item.category,
    item.channel,
    (item.tagItems || [])[0] && (item.tagItems || [])[0].label,
    (item.tags || [])[0],
    item.sourceName,
    '讯'
  ).slice(0, 2)
}

function primaryTagLabelForArticle(source) {
  const item = source || {}
  const tagItems = Array.isArray(item.tagItems) ? item.tagItems : []
  const tags = Array.isArray(item.tags) ? item.tags : []
  return firstNonEmpty(
    tagItems[0] && tagItems[0].label,
    tags[0],
    item.category,
    item.channel,
    item.sourceName,
    '来源'
  ).slice(0, 4)
}

function visualToneForArticle(source) {
  const item = source || {}
  const text = [
    item.channel,
    item.category,
    item.sourceName,
    ...(item.tags || []),
    ...((item.tagItems || []).map((tag) => tag && tag.label))
  ].join(' ').toLowerCase()

  if (/ptr|beta|测试/.test(text)) return 'ptr'
  if (/class|职业|hotfix|热修/.test(text)) return 'class'
  if (/raid|团本|团队/.test(text)) return 'raid'
  if (/event|trading-post|weekly|rewards|活动|商栈|周报|奖励|timeways/.test(text)) return 'event'
  if (/community|社区/.test(text)) return 'community'
  if (/guide|攻略|指南|how to|玩法|build|rotation|simc|wcl/.test(text)) return 'guide'
  if (/content-update|patch|更新|补丁/.test(text)) return 'update'
  return 'official'
}

function visualSourceLabelForArticle(source) {
  const item = source || {}
  if (item.sourceTier === 'official') return '官方来源'
  if (item.verificationStatus === 'official_verified') return '已核验'
  return firstNonEmpty(item.sourceName, '来源')
}

function compactSourceName(sourceName) {
  const text = firstNonEmpty(sourceName, '来源')
  if (/blizzard/i.test(text)) return 'Blizzard'
  if (/wowhead/i.test(text)) return 'Wowhead'
  if (/icy/i.test(text)) return 'Icy Veins'
  return text.replace(/\s+official\s+/i, ' ').slice(0, 14)
}

function compactRankedTitle(value) {
  const title = firstNonEmpty(value, '待核验资讯')
    .replace(/（[^）]{1,24}）/g, '')
    .replace(/\([^)]{1,24}\)/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  return title.length > 24 ? `${title.slice(0, 24)}…` : title
}

function visualTextForChannel(channel) {
  const item = channel || {}
  return firstNonEmpty(item.title, item.id, '频').slice(0, 1)
}

function visualToneForChannel(channel) {
  const text = `${(channel || {}).id || ''} ${(channel || {}).title || ''}`.toLowerCase()
  if (/ptr|测试/.test(text)) return 'ptr'
  if (/class|职业/.test(text)) return 'class'
  if (/official|官方/.test(text)) return 'official'
  if (/event|活动|商栈/.test(text)) return 'event'
  if (/community|社区/.test(text)) return 'community'
  if (/guide|攻略/.test(text)) return 'guide'
  if (/update|更新/.test(text)) return 'update'
  return 'official'
}

function articleSearchText(article) {
  const item = article || {}
  const tagItems = Array.isArray(item.tagItems) ? item.tagItems : []
  return [
    item.title,
    item.summary,
    item.channel,
    item.category,
    item.sourceName,
    item.sourceTier,
    item.verificationStatus,
    ...(item.tags || []),
    ...tagItems.map((tag) => `${tag && tag.id || ''} ${tag && tag.label || ''}`)
  ].join(' ').toLowerCase()
}

function articleMatchesTab(article, key) {
  const text = articleSearchText(article)
  if (key === 'all') return true
  if (key === 'official') {
    return /blizzard|官方|official|official_verified/.test(text)
  }
  if (key === 'updates') {
    return /content-update|hotfix|patch|ptr|beta|class-change|更新|热修|测试服|职业调整/.test(text)
  }
  if (key === 'events') {
    return /event|trading-post|weekly|rewards|活动|商栈|周报|奖励|timeways/.test(text)
  }
  if (key === 'community') {
    return /community|社区|wowhead|icy veins|icy-veins/.test(text)
  }
  if (key === 'guides') {
    return /guide|攻略|指南|how to|玩法|build|rotation|simc|wcl/.test(text)
  }
  return false
}

const NEWS_TAB_DEFS = [
  { key: 'all', title: '综合', visualText: '综', queryType: 'metric', queryKey: 'today', queryValue: '' },
  { key: 'official', title: '官方', visualText: '官', queryType: 'metric', queryKey: 'official', queryValue: '' },
  { key: 'updates', title: '更新', visualText: '更', queryType: 'metric', queryKey: 'updates', queryValue: '' },
  { key: 'events', title: '活动', visualText: '活', queryType: 'metric', queryKey: 'events', queryValue: '' },
  { key: 'community', title: '社区', visualText: '社', queryType: 'metric', queryKey: 'community', queryValue: '' },
  { key: 'guides', title: '攻略', visualText: '攻', queryType: 'metric', queryKey: 'guides', queryValue: '' }
]

const NEWS_FALLBACK_THUMB_BY_KEY = {
  official: '/assets/tabbar/builds-selected.png',
  updates: '/assets/tabbar/simulator-selected.png',
  ptr: '/assets/tabbar/simulator-selected.png',
  class: '/assets/tabbar/builds-selected.png',
  raid: '/assets/tabbar/builds-selected.png',
  events: '/assets/tabbar/news-selected.png',
  guides: '/assets/tabbar/news-selected.png',
  community: '/assets/tabbar/profile-selected.png',
  source_reference: '/assets/tabbar/news-selected.png'
}

const NEWS_HERO_FALLBACK_URL = ''

const NEWS_FALLBACK_TAB_KEY_BY_CATEGORY = {
  official: 'official',
  updates: 'updates',
  ptr: 'updates',
  class: 'updates',
  raid: 'updates',
  events: 'events',
  guides: 'guides',
  community: 'community',
  all: 'all'
}

const RANKED_FOCUS_COUNT = 5
const initialFallbackPayload = fallbackPayload('bootstrap')

function deferAfterFirstPaint(callback) {
  const run = () => setTimeout(callback, 0)
  if (typeof wx !== 'undefined' && typeof wx.nextTick === 'function') {
    wx.nextTick(run)
    return
  }
  run()
}

function fallbackCategoryKeyForArticle(source) {
  const text = articleSearchText(source)

  if (/ptr|beta|测试服|测试/.test(text)) return 'ptr'
  if (/event|trading-post|weekly|rewards|活动|商栈|周报|奖励|timeways/.test(text)) return 'events'
  if (/content-update|patch|更新|补丁|内容更新/.test(text)) return 'updates'
  if (/class-change|class|职业|hotfix|热修|职业调整/.test(text)) return 'class'
  if (/raid|团本|团队|dungeon|地下城/.test(text)) return 'raid'
  if (articleMatchesTab(source, 'guides')) return 'guides'
  if (articleMatchesTab(source, 'community')) return 'community'
  if (articleMatchesTab(source, 'official')) return 'official'
  if (articleMatchesTab(source, 'updates')) return 'updates'
  return 'all'
}

function fallbackTabKeyForArticle(source) {
  const key = fallbackCategoryKeyForArticle(source)
  return NEWS_FALLBACK_TAB_KEY_BY_CATEGORY[key] || key
}

function fallbackThumbUrlForArticle(source) {
  const key = fallbackCategoryKeyForArticle(source)
  return NEWS_FALLBACK_THUMB_BY_KEY[key] || NEWS_FALLBACK_THUMB_BY_KEY.official || ''
}

function rankedArticleKey(source) {
  const item = source || {}
  return firstNonEmpty(item.id, item.canonicalTopicId, item.sourceUrl, item.title)
}

function evidenceGapRow(index) {
  const gapCopy = [
    {
      title: '等待更多官方来源核验后进入今日重点',
      meta: '暂无更多已发布来源 / 不伪造资讯',
      label: '待核'
    },
    {
      title: '社区线索进入待复核队列，确认后才会展示为资讯',
      meta: '来源参考待核验 / 不计入推荐',
      label: '参考'
    },
    {
      title: '版本线索缺少可公开来源，暂不生成标题或结论',
      meta: '证据缺口 / 等待同步',
      label: '缺口'
    }
  ][index % 3]
  return {
    id: `news-evidence-gap-${index + 1}`,
    isEvidenceGap: true,
    channel: '来源核验',
    category: '证据缺口',
    displayPublishedAt: '待核验',
    displayFeedMeta: gapCopy.meta,
    title: gapCopy.title,
    sourceName: '来源门禁',
    sourceNote: '仅展示可信资讯',
    visualUrl: '',
    visualText: '源',
    visualLabel: gapCopy.label,
    visualTone: 'source_reference',
    fallbackThumbUrl: NEWS_FALLBACK_THUMB_BY_KEY.source_reference || '',
    fallbackIconUrl: '',
    visualSourceLabel: '来源参考'
  }
}

function decorateArticle(item) {
  const source = item || {}
  const minutes = Number(source.readingMeta && source.readingMeta.estimatedReadingMinutes)
  const metaParts = [
    formatRelativeShort(source.publishedAt),
    visualSourceLabelForArticle(source)
  ].filter(Boolean)
  if (Number.isFinite(minutes) && minutes > 0) {
    metaParts.push(`${minutes}分钟读完`)
  }
  return {
    ...source,
    displayPublishedAt: formatDateShort(source.publishedAt),
    displayFeedMeta: metaParts.join(' · '),
    displayRankedTitle: compactRankedTitle(source.title),
    visualUrl: visualUrlForArticle(source),
    visualBroken: false,
    bannerFallbackUrl: NEWS_HERO_FALLBACK_URL,
    visualText: visualTextForArticle(source),
    visualLabel: primaryTagLabelForArticle(source),
    visualTone: visualToneForArticle(source),
    fallbackThumbUrl: fallbackThumbUrlForArticle(source),
    fallbackIconUrl: '',
    visualSourceLabel: visualSourceLabelForArticle(source)
  }
}

function decorateReferenceArticle(item) {
  return {
    ...decorateArticle(item),
    isEvidenceGap: true,
    isSourceReference: true,
    visualLabel: firstNonEmpty(primaryTagLabelForArticle(item), '参考').slice(0, 4),
    visualTone: 'source_reference',
    fallbackThumbUrl: NEWS_FALLBACK_THUMB_BY_KEY.source_reference || '',
    fallbackIconUrl: '',
    visualSourceLabel: '来源参考',
    displayRankedTitle: compactRankedTitle(item && item.title),
    displayFeedMeta: [
      formatRelativeShort(item && item.publishedAt),
      '待发布核验'
    ].filter(Boolean).join(' · ')
  }
}

function normalizeRankedHighlight(row, index) {
  const item = row || evidenceGapRow(index)
  const visualTone = item.visualTone || 'official'
  const isSourceReference = !!item.isSourceReference || visualTone === 'source_reference'
  const isEvidenceGap = !!item.isEvidenceGap || isSourceReference
  const fallbackThumbUrl = firstNonEmpty(
    item.fallbackThumbUrl,
    isEvidenceGap ? NEWS_FALLBACK_THUMB_BY_KEY.source_reference : '',
    fallbackThumbUrlForArticle(item)
  )
  const visualUrl = firstNonEmpty(item.visualUrl)
  return {
    ...item,
    isEvidenceGap,
    isSourceReference,
    rankIndex: index,
    rankNumber: String(index + 1),
    rowState: isEvidenceGap ? 'source_reference' : 'published',
    thumbState: visualUrl ? 'article_image' : (fallbackThumbUrl ? 'fallback_thumb' : 'glyph'),
    isOpenable: !isEvidenceGap && !!item.id,
    visualUrl,
    fallbackThumbUrl
  }
}

function decorateChannel(item) {
  const source = item || {}
  const updateCount = Number(source.updateCount)
  return {
    ...source,
    dockType: 'channel',
    dockKey: firstNonEmpty(source.id, source.title, 'channel'),
    dockValue: source.title || source.id || '',
    showCount: Number.isFinite(updateCount),
    visualText: visualTextForChannel(source),
    visualTone: visualToneForChannel(source)
  }
}

function buildIntelSummary(payload, fromFallback) {
  const source = payload || {}
  const heroNews = Array.isArray(source.heroNews) ? source.heroNews : []
  const highlights = Array.isArray(source.highlights) ? source.highlights : []
  const channels = Array.isArray(source.channels) ? source.channels : []
  const sourceNames = heroNews.concat(highlights).map((item) => item && item.sourceName)
  const updateCount = channels.reduce((total, item) => total + (Number(item && item.updateCount) || 0), 0)
  return {
    title: '今日情报台',
    status: refreshModeLabel(source.refreshMode, fromFallback),
    lastRefreshedAt: formatDateTimeShort(source.lastRefreshedAt),
    focusCount: highlights.length,
    channelCount: channels.length,
    sourceCount: uniqueCount(sourceNames),
    updateCount
  }
}

function buildNewsTabs(payload) {
  const articles = [
    ...((payload && payload.heroNews) || []),
    ...((payload && payload.highlights) || [])
  ]
  const byId = {}
  const uniqueArticles = articles.filter((article) => {
    const id = firstNonEmpty(article && article.id, article && article.title)
    if (!id || byId[id]) return false
    byId[id] = true
    return true
  })
  return NEWS_TAB_DEFS.map((tab, index) => {
    const count = uniqueArticles.filter((article) => articleMatchesTab(article, tab.key)).length
    return {
      ...tab,
      dockType: 'news_tab',
      dockKey: tab.key,
      dockValue: tab.queryValue,
      updateCount: count,
      showCount: false,
      isActive: index === 0,
      visualTone: visualToneForChannel(tab)
    }
  })
}

function buildRankedHighlights(payload) {
  const source = payload || {}
  const pool = [
    ...(Array.isArray(source.highlights) ? source.highlights : []),
    ...(Array.isArray(source.heroNews) ? source.heroNews : [])
  ]
  const seen = {}
  const ranked = []

  pool.forEach((article) => {
    const key = rankedArticleKey(article)
    if (!key || seen[key] || ranked.length >= RANKED_FOCUS_COUNT) return
    seen[key] = true
    ranked.push(decorateArticle(article))
  })

  const references = Array.isArray(source.sourceReferenceHighlights) ? source.sourceReferenceHighlights : []
  references.forEach((article) => {
    const key = rankedArticleKey(article)
    if (!key || seen[key] || ranked.length >= RANKED_FOCUS_COUNT) return
    seen[key] = true
    ranked.push(decorateReferenceArticle(article))
  })

  while (ranked.length < RANKED_FOCUS_COUNT) {
    ranked.push(evidenceGapRow(ranked.length))
  }

  return ranked.slice(0, RANKED_FOCUS_COUNT).map(normalizeRankedHighlight)
}

function buildHeroNews(payload) {
  const source = payload || {}
  const primary = Array.isArray(source.heroNews) ? source.heroNews : []
  if (primary.length) return primary.slice(0, 3).map(decorateArticle)

  const highlights = Array.isArray(source.highlights) ? source.highlights : []
  if (highlights.length) return highlights.slice(0, 3).map(decorateArticle)

  const fallback = fallbackPayload('hero-fallback')
  return [...(fallback.heroNews || []), ...(fallback.highlights || [])]
    .slice(0, 3)
    .map(decorateArticle)
}

Page({
  data: {
    navTitle: '最新资讯',
    intelSummary: buildIntelSummary(initialFallbackPayload, true),
    heroNews: [],
    channels: [],
    newsTabs: buildNewsTabs(initialFallbackPayload),
    highlights: [],
    rankedHighlights: [],
    lastRefreshedAt: '',
    refreshMode: '',
    refreshModeLabel: '本地缓存',
    requestError: '',
    loading: false,
    fromFallback: false,
    deferredVisualsReady: false,
    scrollTop: 0
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    this.newsBootStarted = false
    this.newsUnloaded = false
    syncTabBarSelected(this, 0)
    this.applyPayload(initialFallbackPayload, true)
  },

  onReady() {
    this.startDeferredBoot()
  },

  onShow() {
    syncTabBarSelected(this, 0)
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/news/news', { source: 'tab_resume' })
      trackEvent('news_home_view', { source: 'tab_resume' }, { page: 'pages/news/news' })
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/news/news', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onUnload() {
    this.newsUnloaded = true
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/news/news', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  startDeferredBoot() {
    if (this.newsBootStarted) return
    this.newsBootStarted = true
    deferAfterFirstPaint(() => {
      if (this.newsUnloaded) return
      trackPageView('pages/news/news', { source: 'tab' })
      trackEvent('news_home_view', { source: 'tab' }, { page: 'pages/news/news' })
      this.loadNews(shouldRefreshToday() ? 'scheduled' : 'cached')
    })
  },

  enableDeferredVisuals() {
    if (this.data.deferredVisualsReady) return
    this.setData({ deferredVisualsReady: true })
  },

  handleNewsScroll(event) {
    if (this.data.deferredVisualsReady) return
    const scrollTop = Number((event.detail || {}).scrollTop) || 0
    if (scrollTop > 96) this.enableDeferredVisuals()
  },

  handleHeroImageError(event) {
    const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
    const index = Number(dataset.index)
    if (!Number.isInteger(index) || index < 0 || index >= this.data.heroNews.length) return
    this.setData({ [`heroNews[${index}].visualBroken`]: true })
  },

  openArticle(event) {
    const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
    const detail = event.detail || {}
    const id = dataset.id || detail.id || ''
    if (!id) return
    trackEvent('news_article_open', { articleId: id, source: 'home' }, { page: 'pages/news/news' })
    wx.navigateTo({
      url: `/pages/news/detail?id=${encodeURIComponent(id)}`
    })
  },

  openChannel(event) {
    const { value } = event.currentTarget.dataset
    trackEvent('news_list_view', { type: 'channel', value: value || '', source: 'channel_item' }, { page: 'pages/news/news' })
    wx.navigateTo({
      url: `/pages/news/list?type=channel&value=${encodeURIComponent(value || '')}`
    })
  },

  openNewsTab(event) {
    const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
    const detail = event.detail || {}
    const key = dataset.key || detail.key || ''
    const type = dataset.type || detail.type || ''
    const value = dataset.value || detail.value || ''
    const tab = buildNewsTabs({ heroNews: [], highlights: [] }).find((item) => item.key === key) || NEWS_TAB_DEFS[0]
    const queryType = type || tab.queryType || 'metric'
    const queryKey = key || tab.queryKey || 'today'
    const queryValue = value || ''
    trackEvent('news_list_view', {
      type: 'news_tab',
      key: queryKey,
      value: queryValue,
      source: 'news_tab_dock'
    }, { page: 'pages/news/news' })
    wx.navigateTo({
      url: `/pages/news/list?type=${encodeURIComponent(queryType)}&key=${encodeURIComponent(queryKey)}&value=${encodeURIComponent(queryValue)}`
    })
  },

  loadNews(refreshMode) {
    this.setData({ loading: true })
    requestNewsHome(refreshMode).then(({ payload, fromFallback, error }) => {
      this.applyPayload(payload, fromFallback, error)
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  applyPayload(payload, fromFallback, error) {
    const source = payload || fallbackPayload('bootstrap')
    const intelSummary = buildIntelSummary(source, fromFallback)
    rememberRefreshTime(source.lastRefreshedAt)
    this.setData({
      navTitle: source.navTitle,
      intelSummary,
      heroNews: buildHeroNews(source),
      channels: (source.channels || []).map(decorateChannel),
      newsTabs: buildNewsTabs(source),
      highlights: (source.highlights || []).map(decorateArticle),
      rankedHighlights: buildRankedHighlights(source),
      lastRefreshedAt: source.lastRefreshedAt,
      refreshMode: source.refreshMode,
      refreshModeLabel: refreshModeLabel(source.refreshMode, fromFallback),
      requestError: error || '',
      fromFallback
    })
  }
})

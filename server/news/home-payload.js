const CHANNELS = [
  { id: 'retail', title: '正式服动态', desc: '官方公告、热修、活动与正式服版本内容' },
  { id: 'ptr', title: '测试服前瞻', desc: 'PTR / Beta 改动、前瞻与开发说明' },
  { id: 'class', title: '职业强度变化', desc: '职业调优、套装修正与强度趋势' }
]

const trustedSources = [
  { name: 'Blizzard News', hostnames: ['worldofwarcraft.blizzard.com', 'news.blizzard.com'] },
  { name: 'Wowhead', hostnames: ['www.wowhead.com'] },
  { name: 'Icy Veins', hostnames: ['www.icy-veins.com'] }
]

function isValidDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || '')
}

function hasChinese(value) {
  return /[\u4e00-\u9fff]/.test(value || '')
}

function hasCompleteChineseBody(story) {
  const body = String(story.bodyZh || '').replace(/\s+/g, ' ').trim()
  const summary = String(story.summary || '').replace(/\s+/g, ' ').trim()
  if (body.length < 70) return false
  if (!hasChinese(body)) return false
  if (summary && (body === summary || body === `中文正文：${summary}`)) return false
  return true
}

function blockText(block) {
  if (!block || typeof block !== 'object') return ''
  if (block.type === 'list') {
    return Array.isArray(block.items) ? block.items.join(' ') : ''
  }
  return String(block.text || '').trim()
}

function hasCompleteBodyBlocks(story) {
  if (!Array.isArray(story.bodyBlocksZh) || story.bodyBlocksZh.length === 0) return false
  return story.bodyBlocksZh.every((block) => {
    if (!block || typeof block !== 'object') return false
    if (!['paragraph', 'heading', 'list', 'quote'].includes(block.type)) return false
    if (block.type === 'list') {
      return Array.isArray(block.items) && block.items.length > 0 && block.items.every((item) => hasChinese(item))
    }
    return hasChinese(blockText(block))
  })
}

function hostnameFor(url) {
  const match = String(url || '').match(/^https?:\/\/([^/?#:]+)/i)
  return match ? match[1].toLowerCase() : ''
}

function isTrustedStory(story) {
  const hostname = hostnameFor(story.sourceUrl)
  const source = trustedSources.find((item) => item.name === story.sourceName)

  return Boolean(
    story.id &&
    story.title &&
    story.summary &&
    CHANNELS.some((channel) => channel.title === story.channel) &&
    story.sourceName &&
    story.sourceUrl &&
    story.sourceNote &&
    story.originalTitle &&
    hasCompleteChineseBody(story) &&
    hasCompleteBodyBlocks(story) &&
    story.contentStatus === 'ready' &&
    story.translationStatus === 'llm' &&
    story.translationFidelity === 'source_translation' &&
    story.verificationStatus === 'official_verified' &&
    story.licenseStatus === 'approved' &&
    story.sourceTier === 'official' &&
    Array.isArray(story.sourceBadges) &&
    story.sourceBadges.length > 0 &&
    Array.isArray(story.tagItems) &&
    story.tagItems.length > 0 &&
    isValidDate(story.publishedAt) &&
    source &&
    source.hostnames.includes(hostname)
  )
}

function sortStories(stories) {
  return [...stories].sort((a, b) => {
    const dateOrder = b.publishedAt.localeCompare(a.publishedAt)
    if (dateOrder !== 0) return dateOrder
    return b.importance - a.importance
  })
}

function visibleStory(story) {
  return {
    id: story.id,
    title: story.title,
    summary: story.summary,
    channel: story.channel,
    category: story.category,
    tags: story.tags || [],
    importance: story.importance,
    sourceName: story.sourceName,
    sourceUrl: story.sourceUrl,
    publishedAt: story.publishedAt,
    sourceNote: story.sourceNote,
    bodyZh: story.bodyZh,
    bodyBlocksZh: story.bodyBlocksZh || [],
    originalTitle: story.originalTitle || story.title,
    tagItems: story.tagItems || [],
    contentStatus: story.contentStatus || 'ready',
    translationStatus: story.translationStatus || '',
    translationFidelity: story.translationFidelity || '',
    verificationStatus: story.verificationStatus || '',
    licenseStatus: story.licenseStatus || '',
    sourceTier: story.sourceTier || '',
    sourceBadges: story.sourceBadges || [],
    canonicalTopicId: story.canonicalTopicId || '',
    readingMeta: story.readingMeta || {}
  }
}

function countByTag(stories, tag) {
  return stories.filter((story) => (story.tags || []).includes(tag)).length
}

function countByChannel(stories, channelTitle) {
  return stories.filter((story) => story.channel === channelTitle).length
}

function channelsWithCounts(stories) {
  return CHANNELS.map((channel) => ({
    ...channel,
    updateCount: countByChannel(stories, channel.title)
  }))
}

function buildNewsHomePayload(articles, refreshState = {}) {
  const stories = sortStories((articles || []).filter(isTrustedStory)).map(visibleStory)

  return {
    navTitle: '最新资讯',
    heroNews: stories.slice(0, 3),
    metrics: [
      { key: 'today', value: String(stories.length), label: '今日更新' },
      { key: 'class-change', value: String(countByTag(stories, 'class-change')), label: '职业变动' },
      { key: 'ptr', value: String(stories.filter((story) => story.channel === '测试服前瞻').length), label: '测试服重点' }
    ],
    channels: channelsWithCounts(stories),
    highlights: stories.slice(0, 6),
    lastRefreshedAt: refreshState.lastRefreshedAt || '',
    refreshMode: refreshState.refreshMode || 'bootstrap'
  }
}

function dateKey(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toISOString().slice(0, 10)
}

function shouldAutoRefresh(lastRefreshedAt, now = new Date().toISOString()) {
  if (!lastRefreshedAt) return true
  return dateKey(lastRefreshedAt) !== dateKey(now)
}

function createRefreshState(refreshMode = 'scheduled', now = new Date().toISOString()) {
  return {
    refreshMode,
    lastRefreshedAt: now
  }
}

module.exports = {
  buildNewsHomePayload,
  createRefreshState,
  shouldAutoRefresh,
  trustedSources
}

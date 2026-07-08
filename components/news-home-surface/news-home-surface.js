const STATE_LABELS = {
  ready_to_simulate: '可用',
  verified: '可用',
  blocked: '阻断',
  partial: '部分可用',
  stale: '需刷新',
  source_reference: '来源参考',
  loading: '读取中',
  unknown: '未知'
}

const STATE_GLYPHS = {
  ready_to_simulate: 'OK',
  verified: 'OK',
  blocked: '!',
  partial: '!',
  stale: '刷',
  source_reference: '源',
  loading: '读',
  unknown: '?'
}

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function normalizeState(value) {
  const state = cleanText(value, 'source_reference')
  return Object.prototype.hasOwnProperty.call(STATE_LABELS, state) ? state : 'source_reference'
}

function stateLabel(state, fallback) {
  return cleanText(fallback, STATE_LABELS[state] || STATE_LABELS.source_reference)
}

function stateGlyph(state, fallback) {
  return cleanText(fallback, STATE_GLYPHS[state] || STATE_GLYPHS.source_reference)
}

function normalizeChannel(channel, index, selectedChannelId) {
  const key = cleanText(channel.key || channel.id || channel.queryKey, `channel-${index}`)
  return {
    dockKey: key,
    queryType: cleanText(channel.queryType || channel.type, 'metric'),
    queryKey: key,
    queryValue: cleanText(channel.queryValue || channel.value),
    title: cleanText(channel.title || channel.label, '频道'),
    visualText: cleanText(channel.visualText || channel.iconText || channel.title || channel.label, '讯').slice(0, 2),
    visualTone: cleanText(channel.visualTone || channel.tone, 'source'),
    iconUrl: cleanText(channel.iconUrl),
    isActive: Boolean(channel.isActive || key === selectedChannelId)
  }
}

function normalizeArticle(item, index) {
  const id = cleanText(item.id || item.articleId, `article-${index}`)
  const state = normalizeState(item.state || item.rowState)
  return {
    id,
    rankNumber: cleanText(item.rankNumber || item.rank || index + 1),
    title: cleanText(item.title, '未命名资讯'),
    displayRankedTitle: cleanText(item.displayRankedTitle || item.title, '未命名资讯'),
    channel: cleanText(item.channel || item.category, '资讯'),
    displayFeedMeta: cleanText(item.displayFeedMeta || item.meta || item.publishedAt, '来源待确认'),
    visualLabel: cleanText(item.visualLabel || item.badge, '来源'),
    visualText: cleanText(item.visualText || item.channel || '讯').slice(0, 2),
    visualTone: cleanText(item.visualTone || item.tone, 'source'),
    visualUrl: cleanText(item.visualUrl || item.thumbnail),
    fallbackThumbUrl: cleanText(item.fallbackThumbUrl),
    fallbackIconUrl: cleanText(item.fallbackIconUrl),
    rowState: state,
    thumbState: item.visualUrl || item.thumbnail ? 'ready' : 'fallback',
    isEvidenceGap: Boolean(item.isEvidenceGap),
    isSourceReference: state === 'source_reference',
    isOpenable: item.isOpenable !== false && Boolean(id)
  }
}

function normalizeEvidenceRows(rows) {
  return normalizeArray(rows).map((row, index) => {
    const status = normalizeState(row.status || row.state)
    return {
      key: cleanText(row.key || row.id, `news-evidence-${index}`),
      iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
      label: cleanText(row.label, '证据'),
      value: cleanText(row.value || row.desc, '待读取'),
      status,
      statusLabel: stateLabel(status, row.statusLabel)
    }
  })
}

function buildState(data) {
  const state = normalizeState(data.state)
  const evidenceRows = normalizeEvidenceRows(data.evidenceRows)
  const previewRows = data.evidenceExpanded ? evidenceRows : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${state}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedState: state,
    normalizedStateLabel: stateLabel(state, data.stateLabel),
    normalizedStateGlyph: stateGlyph(state, data.stateGlyph),
    normalizedTitle: cleanText(data.title, '今日资讯'),
    normalizedMeta: cleanText(data.meta, '来源优先'),
    normalizedSummary: cleanText(data.summary, '官方、更新、活动、社区和攻略统一在同一套来源证据下展示。'),
    normalizedChannels: normalizeArray(data.channels).map((item, index) => normalizeChannel(item, index, data.selectedChannelId)),
    normalizedFocusItems: normalizeArray(data.focusItems).map(normalizeArticle).slice(0, 5),
    normalizedLatestItems: normalizeArray(data.latestItems).map(normalizeArticle).slice(0, 8),
    normalizedEvidenceRows: previewRows,
    normalizedEvidenceSummary: evidenceRows.length ? `${previewRows.length}/${evidenceRows.length} 条证据` : '等待资讯证据'
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: { type: String, value: 'source_reference' },
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    title: { type: String, value: '今日资讯' },
    meta: { type: String, value: '' },
    summary: { type: String, value: '' },
    selectedChannelId: { type: String, value: '' },
    channels: { type: Array, value: [] },
    focusItems: { type: Array, value: [] },
    latestItems: { type: Array, value: [] },
    evidenceRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    deferredVisualsReady: { type: Boolean, value: false },
    materialSrc: { type: String, value: '' },
    heroMaterialSrc: { type: String, value: '' },
    focusMaterialSrc: { type: String, value: '' },
    latestMaterialSrc: { type: String, value: '' },
    evidenceMaterialSrc: { type: String, value: '' },
    focusTitle: { type: String, value: '今日重点' },
    focusMeta: { type: String, value: '真实来源' },
    latestTitle: { type: String, value: '最新更新' },
    latestMeta: { type: String, value: '按时间' }
  },
  data: buildState({}),
  observers: {
    '**': function observeAll(data) {
      this.setData(buildState(data))
    }
  },
  methods: {
    handleChannelTap(event) {
      this.triggerEvent('channeltap', event.detail || {})
    },
    handleArticleTap(event) {
      this.triggerEvent('articletap', event.detail || {})
    },
    handleFocusAction(event) {
      this.triggerEvent('focusaction', event.detail || {})
    },
    handleLatestAction(event) {
      this.triggerEvent('latestaction', event.detail || {})
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle')
    },
    handleEvidenceRowTap(event) {
      this.triggerEvent('evidencerowtap', event.detail || {})
    }
  }
})

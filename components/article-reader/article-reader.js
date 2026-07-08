function asArray(value) {
  return Array.isArray(value) ? value : []
}

function text(value, fallback = '') {
  const normalized = String(value || '').trim()
  return normalized || fallback
}

function normalizeBlock(block, index) {
  const type = text(block.type, 'paragraph')
  return {
    key: text(block.key || block.id, `block-${index}`),
    type,
    text: text(block.text || block.content),
    items: asArray(block.items).map((item, itemIndex) => ({
      key: text(item.key || item.id, `item-${index}-${itemIndex}`),
      text: text(item.text || item)
    }))
  }
}

function normalizeChips(values) {
  return asArray(values).map((item, index) => ({
    key: text(item.key || item.id, `chip-${index}`),
    label: text(item.label || item.text || item.name || item)
  })).filter((item) => item.label)
}

function buildEvidenceRows(data, article) {
  const rows = []
  if (data.fromFallback || data.requestError) {
    rows.push({
      key: 'article-fallback',
      iconText: '缓',
      label: '详情来源',
      value: data.requestError || '当前详情来自缓存或 fallback',
      status: 'source_reference',
      statusLabel: '来源参考'
    })
  }
  if (article.sourceName || article.sourceUrl) {
    rows.push({
      key: 'article-source',
      iconText: '源',
      label: text(article.sourceName, '来源'),
      value: text(article.sourceUrl, '来源链接待补'),
      status: 'source_reference',
      statusLabel: '来源'
    })
  }
  return rows
}

function stateFor(data, article) {
  if (data.loading) return 'loading'
  if (data.missingId || data.notFound) return 'blocked'
  if (data.fromFallback || data.requestError) return 'source_reference'
  if (!article || !article.title) return 'empty'
  return 'ready_to_simulate'
}

function buildViewModel(data) {
  const article = data.article || {}
  const state = stateFor(data, article)
  const bodyBlocks = asArray(article.bodyBlocksZh || article.bodyBlocks).map(normalizeBlock)
  const sourceBadges = normalizeChips(article.sourceBadges)
  const metaChips = normalizeChips(article.metaChips || article.tagItems)
  return {
    rootClass: `state-${state}`,
    statusState: state,
    statusLabel: state === 'loading' ? '读取中' : state === 'blocked' ? '阻断' : state === 'source_reference' ? '来源参考' : '可阅读',
    panelVariant: state === 'blocked' ? 'danger' : state === 'source_reference' ? 'source' : 'flat',
    titleText: text(article.title, data.missingId ? '缺少文章 ID' : data.notFound ? '未找到文章' : '资讯详情'),
    originalTitleText: text(article.originalTitle),
    summaryText: text(article.summary),
    channelText: text(article.channel || article.category, '资讯'),
    publishedAtText: text(article.publishedAt, '时间待确认'),
    sourceNameText: text(article.sourceName, '来源待确认'),
    sourceUrlText: text(article.sourceUrl),
    bodyBlocks,
    hasBodyBlocks: bodyBlocks.length > 0,
    sourceBadges,
    metaChips,
    evidenceRows: buildEvidenceRows(data, article)
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    article: {
      type: Object,
      value: null
    },
    loading: {
      type: Boolean,
      value: false
    },
    missingId: {
      type: Boolean,
      value: false
    },
    notFound: {
      type: Boolean,
      value: false
    },
    fromFallback: {
      type: Boolean,
      value: false
    },
    requestError: {
      type: String,
      value: ''
    },
    homeButton: {
      type: Boolean,
      value: false
    }
  },
  data: buildViewModel({}),
  observers: {
    'article, loading, missingId, notFound, fromFallback, requestError': function updateReader() {
      this.setData(buildViewModel(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildViewModel(this.data))
    }
  },
  methods: {
    handleCopySource() {
      const sourceUrl = text(this.data.sourceUrlText)
      if (!sourceUrl) return
      this.triggerEvent('copysource', {
        sourceUrl: sourceUrl
      })
    },
    handleEvidenceToggle(event) {
      this.triggerEvent('evidencetoggle', event.detail || {})
    }
  }
})

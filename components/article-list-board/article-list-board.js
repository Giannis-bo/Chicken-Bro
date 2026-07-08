function asArray(value) {
  return Array.isArray(value) ? value : []
}

function text(value, fallback = '') {
  const normalized = String(value || '').trim()
  return normalized || fallback
}

function stateFor(data) {
  if (data.loading) return 'loading'
  if (data.fromFallback || data.requestError) return 'source_reference'
  if (data.empty || !asArray(data.articles).length) return 'empty'
  return 'ready_to_simulate'
}

function normalizeDensity(value) {
  return String(value || '').trim() === 'standard' ? 'standard' : 'compact'
}

function articleState(article, fallbackState) {
  const explicit = text(article.state)
  if (explicit) return explicit
  if (fallbackState === 'source_reference') return 'source_reference'
  return 'ready_to_simulate'
}

function normalizeArticles(articles, fallbackState) {
  return asArray(articles).map((article, index) => {
    const id = text(article.id, `article-${index}`)
    const sourceName = text(article.sourceName, '来源待确认')
    const sourceUrl = text(article.sourceUrl)
    return {
      id,
      rank: Number(article.rank || index + 1),
      title: text(article.title, '未命名资讯'),
      summary: text(article.summary, '暂无摘要'),
      channel: text(article.channel, '资讯'),
      publishedAt: text(article.publishedAt, '时间待确认'),
      sourceName,
      sourceUrl,
      thumbnail: text(article.thumbnail || article.visualUrl),
      fallbackText: text(article.fallbackText, sourceName.slice(0, 1) || '源'),
      state: articleState(article, fallbackState),
      stateLabel: text(article.stateLabel, articleState(article, fallbackState) === 'source_reference' ? '参考' : '可读')
    }
  })
}

function buildEvidenceRows(data, state) {
  if (!data.fromFallback && !data.requestError) return []
  return [
    {
      key: 'news-list-source-state',
      iconText: '源',
      label: '列表来源',
      value: data.requestError || '当前展示缓存或本地 fallback 资讯',
      status: state,
      statusLabel: state === 'source_reference' ? '来源参考' : '部分可用'
    }
  ]
}

function buildViewModel(data) {
  const state = stateFor(data)
  const articles = normalizeArticles(data.articles, state)
  const count = Number(data.count)
  const hasCount = Number.isFinite(count) && count >= 0
  return {
    rootClass: `state-${state} density-${normalizeDensity(data.density)}`,
    statusState: state,
    statusLabel: state === 'loading' ? '读取中' : state === 'empty' ? '暂无内容' : state === 'source_reference' ? '来源参考' : '可阅读',
    panelVariant: state === 'source_reference' ? 'source' : 'flat',
    countLabel: hasCount ? `${count} 条` : `${articles.length} 条`,
    visibleArticles: articles,
    hasArticles: articles.length > 0,
    evidenceRows: buildEvidenceRows(data, state)
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    query: {
      type: Object,
      value: null
    },
    title: {
      type: String,
      value: '资讯列表'
    },
    count: {
      type: Number,
      value: 0
    },
    articles: {
      type: Array,
      value: []
    },
    loading: {
      type: Boolean,
      value: false
    },
    empty: {
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
    density: {
      type: String,
      value: 'compact'
    }
  },
  data: buildViewModel({}),
  observers: {
    'articles, count, loading, empty, fromFallback, requestError, density': function updateBoard() {
      this.setData(buildViewModel(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildViewModel(this.data))
    }
  },
  methods: {
    handleArticleTap(event) {
      const dataset = (event.currentTarget && event.currentTarget.dataset) || {}
      const id = text(dataset.id)
      if (!id || this.data.loading) return
      this.triggerEvent('openarticle', {
        id,
        query: this.data.query || null
      })
    },
    handleEvidenceToggle(event) {
      this.triggerEvent('evidencetoggle', event.detail || {})
    }
  }
})

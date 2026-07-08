const { fallbackBuildsHome, requestBuildsHome } = require('./builds-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { syncTabBarSelected } = require('../common/tabbar-sync')
const { classIconUrlFor, specIconUrlFor } = require('../common/wow-spec-assets')

const defaultSpecId = '法师-冰霜'

function defaultSpecFromPayload(payload) {
  const classes = (payload && payload.classOptions) || []
  const specs = []
  classes.forEach((classItem) => {
    ;((classItem && classItem.specializations) || []).forEach((spec) => {
      specs.push(spec)
    })
  })
  return specs.find((spec) => spec && spec.id === defaultSpecId) || specs[0] || {}
}

function countSpecs(payload) {
  const classes = (payload && payload.classOptions) || []
  return classes.reduce((total, classItem) => {
    return total + (((classItem && classItem.specializations) || []).length)
  }, 0)
}

function buildHomeOverview(payload) {
  const source = payload || {}
  const classes = source.classOptions || []
  const classCount = classes.length || 13
  const specCount = countSpecs(source) || 40
  const actionCount = ((source.quickActions || []).filter(Boolean)).length || 4
  return {
    classCount,
    specCount,
    actionCount,
    chips: [
      { label: '职业', value: String(classCount) },
      { label: '专精', value: String(specCount) },
      { label: '流程', value: String(actionCount) }
    ]
  }
}

function buildWorkbenchEntry(payload) {
  const spec = defaultSpecFromPayload(payload)
  const specName = spec.specName || '冰霜'
  const specLabel = [spec.className, spec.specName].filter(Boolean).join(' · ') || '法师 · 冰霜'
  const classKey = spec.websimClassKey || spec.classKey || ''
  const specKey = spec.websimSpecKey || spec.specKey || ''
  const specIconUrl = (spec.gameAsset && spec.gameAsset.iconUrl) || spec.specIconUrl || spec.iconUrl || specIconUrlFor(specKey, classKey)
  const classIconUrl = (spec.classGameAsset && spec.classGameAsset.iconUrl) || spec.classIconUrl || classIconUrlFor(classKey)
  return {
    specId: spec.id || defaultSpecId,
    title: '当前专精工作台',
    specLabel,
    specInitial: specName.slice(0, 1),
    specIconUrl,
    classIconUrl,
    statusLabel: '等待证据',
    statusTone: 'waiting',
    readinessText: '先读取天赋与装备证据',
    blockerLabel: '缺证据时只给补齐动作',
    actionLabel: '进入',
    facts: [
      { label: '判断对象', value: specLabel },
      { label: '证据范围', value: '天赋 / 装备 / 模板' },
      { label: '输出边界', value: '只给下一步' }
    ],
    modules: [
      { key: 'talents', title: '天赋', iconText: '天', statusLabel: '待读取', statusTone: 'waiting', metaLabel: 'WebSim / 模板' },
      { key: 'gear', title: '装备', iconText: '装', statusLabel: '待读取', statusTone: 'waiting', metaLabel: '16 槽 / 模板' },
      { key: 'simc', title: 'SimC', iconText: 'Sim', statusLabel: '待输入', statusTone: 'idle', metaLabel: '固定模板' },
      { key: 'captain', title: '队长', iconText: '队', statusLabel: '待上下文', statusTone: 'idle', metaLabel: '只解释证据' }
    ]
  }
}

const fallbackHome = fallbackBuildsHome()

Page({
  data: {
    ...fallbackHome,
    buildsOverview: buildHomeOverview(fallbackHome),
    workbenchEntry: buildWorkbenchEntry(fallbackHome),
    loading: false,
    fromFallback: true,
    deferredVisualsReady: false,
    scrollTop: 0,
    requestError: ''
  },

  onLoad() {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    syncTabBarSelected(this, 1)
    trackPageView('pages/builds/builds', { source: 'tab' })
    trackEvent('builds_home_view', { source: 'tab' }, { page: 'pages/builds/builds' })
    this.loadBuildsHome()
  },

  onShow() {
    syncTabBarSelected(this, 1)
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/builds/builds', { source: 'tab_resume' })
      trackEvent('builds_home_view', { source: 'tab_resume' }, { page: 'pages/builds/builds' })
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/builds/builds', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onUnload() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/builds/builds', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  enableDeferredVisuals() {
    if (this.data.deferredVisualsReady) return
    this.setData({ deferredVisualsReady: true })
  },

  handleBuildsScroll(event) {
    if (this.data.deferredVisualsReady) return
    const scrollTop = Number((event.detail || {}).scrollTop) || 0
    if (scrollTop > 96) this.enableDeferredVisuals()
  },

  openQueryPage(event) {
    const queryKey = event.currentTarget.dataset.key
    trackEvent('builds_query_open', { queryKey: queryKey || '' }, { page: 'pages/builds/builds' })
    if (queryKey === 'talents') {
      wx.navigateTo({
        url: '/pages/builds/talent-simulator'
      })
      return
    }
    if (queryKey === 'simc') {
      wx.navigateTo({
        url: '/pages/simulator/simc?from=builds'
      })
      return
    }
    if (queryKey === 'tasks') {
      wx.navigateTo({
        url: '/pages/simulator/tasks?from=builds'
      })
      return
    }
    wx.navigateTo({
      url: `/pages/builds/detail?query=${encodeURIComponent(queryKey || '')}`
    })
  },

  openWorkbench() {
    const entry = this.data.workbenchEntry || buildWorkbenchEntry(this.data)
    trackEvent('builds_workbench_open', { specId: entry.specId || '' }, { page: 'pages/builds/builds' })
    wx.navigateTo({
      url: `/pages/builds/workbench?spec=${encodeURIComponent(entry.specId || defaultSpecId)}`
    })
  },

  loadBuildsHome() {
    this.setData({ loading: true })
    requestBuildsHome().then(({ payload, fromFallback, error }) => {
      this.setData({
        ...payload,
        buildsOverview: buildHomeOverview(payload),
        workbenchEntry: buildWorkbenchEntry(payload),
        fromFallback,
        requestError: error || ''
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  }
})

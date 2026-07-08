const { fallbackBuildsHome, requestBuildsHome } = require('./builds-api')
const { requestWebsimGear, requestWebsimTalents } = require('./websim-api')
const { buildWorkbenchState, scenarioOptions } = require('./workbench-state')
const { fetchBuildTemplates, listBuildTemplates } = require('../common/build-template-storage')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')

const defaultSpecId = '法师-冰霜'
const defaultHeroBySpec = {
  'mage:frost': 'spellslinger'
}

function flattenSpecs(classOptions) {
  const specs = []
  ;(classOptions || []).forEach((classItem, classIndex) => {
    ;((classItem && classItem.specializations) || []).forEach((spec, specIndex) => {
      specs.push({ classItem, spec, classIndex, specIndex })
    })
  })
  return specs
}

function findSpecSelection(classOptions, specId) {
  const specs = flattenSpecs(classOptions)
  const wanted = String(specId || defaultSpecId)
  return specs.find((item) => item.spec && item.spec.id === wanted) ||
    specs.find((item) => item.spec && item.spec.id === defaultSpecId) ||
    specs[0] ||
    { classItem: { specializations: [] }, spec: null, classIndex: 0, specIndex: 0 }
}

function specKeys(spec) {
  const source = spec || {}
  const classKey = source.websimClassKey || source.classKey || 'mage'
  const specKey = source.websimSpecKey || source.specKey || 'frost'
  return {
    classKey,
    specKey,
    heroKey: source.heroKey || defaultHeroBySpec[`${classKey}:${specKey}`] || ''
  }
}

function slimGameAsset(asset) {
  const source = asset || {}
  return {
    iconUrl: source.iconUrl || '',
    fallbackText: source.fallbackText || '',
    status: source.status || ''
  }
}

function slimSpecOption(spec, classItem) {
  const source = spec || {}
  const classSource = classItem || {}
  return {
    id: source.id || '',
    className: source.className || classSource.name || '',
    specName: source.specName || source.title || '',
    title: source.title || source.specName || '',
    websimClassKey: source.websimClassKey || classSource.websimClassKey || '',
    websimSpecKey: source.websimSpecKey || '',
    heroKey: source.heroKey || '',
    heroLabel: source.heroLabel || '',
    specIconUrl: source.specIconUrl || source.iconUrl || '',
    iconUrl: source.iconUrl || source.specIconUrl || '',
    gameAsset: slimGameAsset(source.gameAsset)
  }
}

function slimClassOptions(classOptions) {
  return (classOptions || []).map((classItem) => {
    const classSource = classItem || {}
    return {
      name: classSource.name || '',
      websimClassKey: classSource.websimClassKey || '',
      iconUrl: classSource.iconUrl || '',
      gameAsset: slimGameAsset(classSource.gameAsset),
      specializations: ((classSource.specializations || [])).map((spec) => slimSpecOption(spec, classSource))
    }
  })
}

function selectionData(classOptions, selection) {
  const classItem = selection.classItem || {}
  const specOptions = classItem.specializations || []
  const selectedSpec = selection.spec || specOptions[0] || {}
  const keys = specKeys(selectedSpec)
  return {
    classOptions,
    classIndex: selection.classIndex || 0,
    specOptions,
    specIndex: selection.specIndex || 0,
    selectedSpec,
    selectedClassName: classItem.name || '职业',
    selectedSpecName: selectedSpec.specName || selectedSpec.title || '专精',
    classKey: keys.classKey,
    specKey: keys.specKey,
    heroKey: keys.heroKey
  }
}

function summarizeWorkbenchTemplates(templates) {
  return (templates || []).map((template, index) => ({
    id: template.id || template.clientId || `${template.type || 'template'}-${index}`,
    clientId: template.clientId || '',
    type: template.type || '',
    status: template.status || '',
    statusLabel: template.statusLabel || '',
    updatedAt: template.updatedAt || template.createdAt || '',
    remote: !!template.remote
  }))
}

function firstIconFromNodes(nodes) {
  const node = (nodes || []).find((item) => item && item.gameAsset && item.gameAsset.iconUrl)
  if (!node) return { iconUrl: '', fallbackText: '天' }
  return {
    iconUrl: node.gameAsset.iconUrl || '',
    fallbackText: node.gameAsset.fallbackText || (node.name || '').slice(0, 1) || '天'
  }
}

function firstIconFromEquippedSet(equippedSet) {
  const item = Object.values(equippedSet || {}).find((entry) => entry && entry.gameAsset && entry.gameAsset.iconUrl)
  if (!item) return { iconUrl: '', fallbackText: '装' }
  return {
    iconUrl: item.gameAsset.iconUrl || '',
    fallbackText: item.gameAsset.fallbackText || (item.displayName || item.name || '').slice(0, 1) || '装'
  }
}

function slimTalentReadiness(readiness) {
  const source = readiness || {}
  return {
    simcReady: source.simcReady === true,
    spellReady: source.spellReady === true,
    treeReady: source.treeReady,
    blockers: Array.isArray(source.blockers) ? source.blockers.slice(0, 3) : [],
    spellCoverage: source.spellCoverage || {}
  }
}

function slimTalentsPayloadForWorkbench(payload) {
  const source = payload || {}
  const nodes = Array.isArray(source.nodes) ? source.nodes : []
  const heroSection = (Array.isArray(source.treeSections) ? source.treeSections : [])
    .find((item) => item && item.key === 'hero')
  return {
    classKey: source.classKey || '',
    specKey: source.specKey || '',
    heroKey: source.heroKey || '',
    heroName: source.heroName || '',
    heroLabel: source.heroLabel || '',
    nodeCount: nodes.length,
    firstTalentIcon: firstIconFromNodes(nodes),
    treeSections: heroSection ? [{ key: heroSection.key, title: heroSection.title || '' }] : [],
    talentReadiness: slimTalentReadiness(source.talentReadiness),
    talentStatus: source.talentStatus || '',
    dataStatus: source.dataStatus || '',
    errors: Array.isArray(source.errors) ? source.errors.slice(0, 3) : [],
    talentAuthority: {
      checkedAt: source.talentAuthority && source.talentAuthority.checkedAt ? source.talentAuthority.checkedAt : ''
    }
  }
}

function slimGearReadiness(readiness) {
  const source = readiness || {}
  return {
    fullReady: source.fullReady === true,
    simcReadyCount: source.simcReadyCount,
    selectedCount: source.selectedCount,
    requiredSlotCount: source.requiredSlotCount,
    requiredCount: source.requiredCount,
    requiredReadyCount: source.requiredReadyCount,
    missingRequiredSlots: Array.isArray(source.missingRequiredSlots) ? source.missingRequiredSlots.slice(0, 16) : [],
    itemLevel: source.itemLevel || null
  }
}

function slimGearPayloadForWorkbench(payload) {
  const source = payload || {}
  return {
    classKey: source.classKey || '',
    specKey: source.specKey || '',
    slots: (Array.isArray(source.slots) ? source.slots : []).map((slot) => ({
      slot: slot && slot.slot ? slot.slot : '',
      label: slot && slot.label ? slot.label : ''
    })),
    firstGearIcon: firstIconFromEquippedSet(source.equippedSet),
    readiness: slimGearReadiness(source.readiness),
    statSnapshot: {
      statStatus: source.statSnapshot && source.statSnapshot.statStatus ? source.statSnapshot.statStatus : '',
      blockers: source.statSnapshot && Array.isArray(source.statSnapshot.blockers)
        ? source.statSnapshot.blockers.slice(0, 3)
        : []
    },
    catalogStatus: source.catalogStatus || '',
    catalogBlockers: Array.isArray(source.catalogBlockers) ? source.catalogBlockers.slice(0, 3) : [],
    checkedAt: source.checkedAt || '',
    catalogCheckedAt: source.catalogCheckedAt || '',
    dataStatus: source.dataStatus || ''
  }
}

function workbenchStateFor(data, patch) {
  const source = {
    ...(data || {}),
    ...(patch || {})
  }
  return buildWorkbenchState({
    selectedSpec: source.selectedSpec,
    scenarioKey: source.scenarioKey,
    talentsPayload: source.talentsPayload,
    gearPayload: source.gearPayload,
    talentTemplates: source.talentTemplates,
    gearTemplates: source.gearTemplates
  })
}

function deferAfterFirstPaint(callback) {
  const run = () => setTimeout(callback, 0)
  if (typeof wx !== 'undefined' && typeof wx.nextTick === 'function') {
    wx.nextTick(run)
    return
  }
  run()
}

function deferWorkbenchTask(page, delayMs, callback) {
  setTimeout(() => {
    if (!page || page.workbenchUnloaded) return
    callback.call(page)
  }, delayMs)
}

function encodedSpecId(spec) {
  return encodeURIComponent((spec && spec.id) || defaultSpecId)
}

function encodeQuery(params) {
  return Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== null && params[key] !== '')
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&')
}

Page({
  data: {
    classOptions: [],
    classIndex: 0,
    specOptions: [],
    specIndex: 0,
    selectedSpec: null,
    classKey: 'mage',
    specKey: 'frost',
    heroKey: 'spellslinger',
    scenarioOptions,
    scenarioIndex: 0,
    scenarioKey: scenarioOptions[0].key,
    talentsPayload: null,
    gearPayload: null,
    talentTemplates: [],
    gearTemplates: [],
    templateLoading: false,
    templateSourceLabel: '本地模板',
    workbenchState: buildWorkbenchState({ scenarioKey: scenarioOptions[0].key }),
    evidenceExpanded: false,
    deferredVisualsReady: false,
    scrollTop: 0,
    loading: false,
    fromFallback: true,
    requestError: ''
  },

  onLoad(options) {
    this.analyticsStartedAt = Date.now()
    this.analyticsVisible = true
    this.requestSeq = 0
    this.templateRequestSeq = 0
    this.workbenchBootStarted = false
    this.workbenchUnloaded = false
    const homeClassOptions = slimClassOptions((fallbackBuildsHome() || {}).classOptions || [])
    const selection = findSpecSelection(homeClassOptions, options && options.spec ? decodeURIComponent(options.spec) : defaultSpecId)
    const initialSelection = selectionData(homeClassOptions, selection)
    const workbenchState = workbenchStateFor(this.data, initialSelection)
    this.setData({
      ...initialSelection,
      workbenchState,
      fromFallback: true,
      requestError: ''
    })
  },

  onReady() {
    this.startDeferredBoot()
  },

  onShow() {
    if (this.analyticsVisible === false) {
      this.analyticsStartedAt = Date.now()
      this.analyticsVisible = true
      trackPageView('pages/builds/workbench', { source: 'resume' })
    }
    if (this.workbenchBootStarted && this.data.selectedSpec) {
      this.refreshTemplates()
    }
  },

  onHide() {
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/builds/workbench', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  onUnload() {
    this.workbenchUnloaded = true
    if (this.analyticsVisible !== false) {
      trackPageLeave('pages/builds/workbench', this.analyticsStartedAt)
      this.analyticsVisible = false
    }
  },

  startDeferredBoot() {
    if (this.workbenchBootStarted) return
    this.workbenchBootStarted = true
    deferAfterFirstPaint(() => {
      if (this.workbenchUnloaded) return
      this.refreshTemplates()
      deferWorkbenchTask(this, 40, this.loadBuildsHome)
      deferWorkbenchTask(this, 120, this.loadWorkbenchData)
      deferWorkbenchTask(this, 1800, this.loadRemoteTemplates)
      trackPageView('pages/builds/workbench', { source: 'builds_tab' })
      trackEvent('builds_workbench_view', { source: 'builds_tab' }, { page: 'pages/builds/workbench' })
    })
  },

  enableDeferredVisuals() {
    if (this.data.deferredVisualsReady) return
    this.setData({ deferredVisualsReady: true })
  },

  handleWorkbenchScroll(event) {
    if (this.data.deferredVisualsReady) return
    const scrollTop = Number((event.detail || {}).scrollTop) || 0
    if (scrollTop > 96) this.enableDeferredVisuals()
  },

  loadBuildsHome() {
    requestBuildsHome().then(({ payload, fromFallback, error }) => {
      if (this.workbenchUnloaded) return
      const currentSpecId = (this.data.selectedSpec && this.data.selectedSpec.id) || defaultSpecId
      const classOptions = slimClassOptions((payload && payload.classOptions) || [])
      const selection = findSpecSelection(classOptions, currentSpecId)
      const selectionPatch = selectionData(classOptions, selection)
      const workbenchState = workbenchStateFor(this.data, selectionPatch)
      this.setData({
        ...selectionPatch,
        workbenchState,
        fromFallback,
        requestError: error || ''
      })
    })
  },

  refreshTemplates() {
    if (this.workbenchUnloaded) return
    const talentTemplates = summarizeWorkbenchTemplates(listBuildTemplates('talent'))
    const gearTemplates = summarizeWorkbenchTemplates(listBuildTemplates('gear'))
    const workbenchState = workbenchStateFor(this.data, { talentTemplates, gearTemplates })
    this.setData({
      talentTemplates,
      gearTemplates,
      templateSourceLabel: '本地模板',
      workbenchState
    })
  },

  loadRemoteTemplates() {
    this.templateRequestSeq = (this.templateRequestSeq || 0) + 1
    const seq = this.templateRequestSeq
    if (this.workbenchUnloaded) return
    this.setData({ templateLoading: true })
    Promise.all([
      fetchBuildTemplates('talent'),
      fetchBuildTemplates('gear')
    ]).then(([talentResult, gearResult]) => {
      if (this.workbenchUnloaded || seq !== this.templateRequestSeq) return
      const talentTemplates = summarizeWorkbenchTemplates(((talentResult && talentResult.payload) || {}).templates || listBuildTemplates('talent'))
      const gearTemplates = summarizeWorkbenchTemplates(((gearResult && gearResult.payload) || {}).templates || listBuildTemplates('gear'))
      const fromFallback = !!((talentResult && talentResult.fromFallback) && (gearResult && gearResult.fromFallback))
      const workbenchState = workbenchStateFor(this.data, { talentTemplates, gearTemplates })
      this.setData({
        talentTemplates,
        gearTemplates,
        templateSourceLabel: fromFallback ? '本地模板' : '账号模板',
        workbenchState
      })
    }).catch(() => {
      if (!this.workbenchUnloaded && seq === this.templateRequestSeq) this.refreshTemplates()
    }).finally(() => {
      if (!this.workbenchUnloaded && seq === this.templateRequestSeq) this.setData({ templateLoading: false })
    })
  },

  loadWorkbenchData() {
    const seq = ++this.requestSeq
    const params = {
      classKey: this.data.classKey,
      specKey: this.data.specKey,
      heroKey: this.data.heroKey
    }
    this.setData({ loading: true, requestError: '' })
    Promise.all([
      requestWebsimTalents(params),
      requestWebsimGear({ classKey: params.classKey, specKey: params.specKey, compact: true })
    ]).then(([talentResult, gearResult]) => {
      if (this.workbenchUnloaded || seq !== this.requestSeq) return
      const requestError = [talentResult && talentResult.error, gearResult && gearResult.error].filter(Boolean).join(' / ')
      const statePatch = {
        talentsPayload: slimTalentsPayloadForWorkbench(talentResult && talentResult.payload),
        gearPayload: slimGearPayloadForWorkbench(gearResult && gearResult.payload)
      }
      const workbenchState = workbenchStateFor(this.data, statePatch)
      this.setData({
        ...statePatch,
        workbenchState,
        requestError
      })
    }).finally(() => {
      if (!this.workbenchUnloaded && seq === this.requestSeq) this.setData({ loading: false })
    })
  },

  refreshWorkbenchState() {
    const workbenchState = buildWorkbenchState({
      selectedSpec: this.data.selectedSpec,
      scenarioKey: this.data.scenarioKey,
      talentsPayload: this.data.talentsPayload,
      gearPayload: this.data.gearPayload,
      talentTemplates: this.data.talentTemplates,
      gearTemplates: this.data.gearTemplates
    })
    this.setData({ workbenchState })
  },

  selectClass(event) {
    const classIndex = Number(event.detail.value) || 0
    const classItem = this.data.classOptions[classIndex] || { specializations: [] }
    const selection = {
      classItem,
      spec: (classItem.specializations || [])[0] || null,
      classIndex,
      specIndex: 0
    }
    this.setData(selectionData(this.data.classOptions, selection), () => {
      this.refreshWorkbenchState()
      this.loadWorkbenchData()
    })
  },

  selectSpec(event) {
    const specIndex = Number(event.detail.value) || 0
    const selectedSpec = this.data.specOptions[specIndex] || this.data.specOptions[0] || {}
    const selection = {
      classItem: this.data.classOptions[this.data.classIndex],
      spec: selectedSpec,
      classIndex: this.data.classIndex,
      specIndex
    }
    this.setData(selectionData(this.data.classOptions, selection), () => {
      this.refreshWorkbenchState()
      this.loadWorkbenchData()
    })
  },

  selectScenario(event) {
    const scenarioIndex = Number(event.currentTarget.dataset.index) || 0
    const scenario = this.data.scenarioOptions[scenarioIndex] || this.data.scenarioOptions[0]
    this.setData({
      scenarioIndex,
      scenarioKey: scenario.key
    }, () => {
      this.refreshWorkbenchState()
    })
  },

  toggleEvidence() {
    if (!this.data.evidenceExpanded) this.enableDeferredVisuals()
    this.setData({ evidenceExpanded: !this.data.evidenceExpanded })
  },

  openPrimaryAction() {
    const action = (this.data.workbenchState && this.data.workbenchState.primaryAction) || {}
    this.openActionByKey(action.key)
  },

  openModule(event) {
    this.openActionByKey(event.currentTarget.dataset.key)
  },

  openBlockerAction(event) {
    this.openActionByKey(event.currentTarget.dataset.key)
  },

  openActionByKey(key) {
    const actionKey = key || 'evidence'
    const spec = encodedSpecId(this.data.selectedSpec)
    const workbenchQuery = encodeQuery({
      from: 'workbench',
      spec: (this.data.selectedSpec && this.data.selectedSpec.id) || defaultSpecId,
      classKey: this.data.classKey,
      specKey: this.data.specKey,
      heroKey: this.data.heroKey,
      scenario: this.data.scenarioKey
    })
    trackEvent('builds_workbench_action', {
      actionKey,
      specId: (this.data.selectedSpec && this.data.selectedSpec.id) || '',
      state: (this.data.workbenchState && this.data.workbenchState.state) || ''
    }, { page: 'pages/builds/workbench' })
    if (actionKey === 'evidence') {
      this.enableDeferredVisuals()
      this.setData({ evidenceExpanded: true, scrollTop: 1080 })
      return
    }
    if (actionKey === 'simc') {
      wx.navigateTo({ url: `/pages/simulator/simc?${workbenchQuery}` })
      return
    }
    if (actionKey === 'talents') {
      wx.navigateTo({ url: `/pages/builds/talent-simulator?spec=${spec}` })
      return
    }
    if (actionKey === 'gear') {
      wx.navigateTo({ url: `/pages/builds/detail?query=gear&spec=${spec}` })
      return
    }
    if (actionKey === 'chickenbro') {
      wx.navigateTo({ url: `/pages/simulator/chickenbro?${workbenchQuery}` })
      return
    }
    if (actionKey === 'profile') {
      wx.switchTab({ url: '/pages/profile/profile' })
      return
    }
    wx.navigateTo({ url: `/pages/builds/detail?query=${encodeURIComponent(actionKey)}&spec=${spec}` })
  },

  openProfileTemplates() {
    this.openActionByKey('profile')
  }
})

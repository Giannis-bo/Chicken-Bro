const { fallbackPveModule, requestPveModule } = require('./pve-api')
const { trackEvent, trackPageLeave, trackPageView } = require('../common/analytics-client')
const { normalizeGameAsset } = require('../common/game-asset')

function formatNumber(value) {
  const number = Number(value || 0)
  if (!Number.isFinite(number)) return '0'
  return number.toLocaleString('en-US')
}

function firstSpecInTiers(tiers) {
  for (const tier of tiers || []) {
    if (tier.items && tier.items.length) return tier.items[0]
  }
  return null
}

function boundedPercent(value, max) {
  const number = Number(value || 0)
  const rangeMax = Number(max || 0)
  if (!Number.isFinite(number) || !Number.isFinite(rangeMax) || rangeMax <= 0) return 0
  return Math.max(0, Math.min(100, (number / rangeMax) * 100))
}

function roundedPercent(value) {
  return Math.round(value * 10) / 10
}

function buildWclRow(spec, detail, selectedSpecId) {
  const wclDetail = detail || {}
  const distribution = wclDetail.distribution || {}
  const max = Number(wclDetail.max) || 100
  const p50 = boundedPercent(distribution.p50, max)
  const p75 = boundedPercent(distribution.p75, max)
  const p95 = boundedPercent(distribution.p95, max)
  const score = boundedPercent(wclDetail.score, max)
  const rangeLeft = Math.max(0, Math.min(p50, score) - 10)
  const rangeRight = Math.min(100, Math.max(p95, score) + 5)
  const boxLeft = Math.max(0, Math.min(p50, p95))
  const boxWidth = Math.max(5, Math.abs(p95 - p50))
  const classColor = spec.classColor || '#8e8e8e'

  return {
    ...wclDetail,
    specId: spec.specId,
    rank: spec.rank,
    tier: spec.tier,
    className: spec.className,
    specName: spec.specName,
    fullName: spec.fullName,
    classColor,
    sourceStatusLabel: wclDetail.sourceStatusLabel || 'WCL partial',
    scoreText: wclDetail.scoreText || (wclDetail.score ? `${wclDetail.score}` : '-'),
    maxText: wclDetail.maxText || (wclDetail.max ? `${wclDetail.max}` : '-'),
    parsesText: wclDetail.parsesText || (wclDetail.parses ? formatNumber(wclDetail.parses) : '-'),
    metricLabel: wclDetail.metricLabel || 'Points',
    distribution,
    rowClass: spec.specId === selectedSpecId ? 'active' : '',
    wclRangeStyle: `left: ${roundedPercent(rangeLeft)}%; width: ${roundedPercent(Math.max(8, rangeRight - rangeLeft))}%; background-color: ${classColor};`,
    wclBoxStyle: `left: ${roundedPercent(boxLeft)}%; width: ${roundedPercent(boxWidth)}%; background-color: ${classColor};`,
    wclMedianStyle: `left: ${roundedPercent(p75)}%; background-color: ${classColor};`,
    wclScoreDotStyle: `left: ${roundedPercent(score)}%; background-color: ${classColor};`
  }
}

function prepareSpecLadderState(module, preferredRole, preferredSpecId) {
  const isSpecLadder = module && module.key === 'specLadder'
  if (!isSpecLadder) {
    return {
      isSpecLadder: false,
      specLadderRoles: [],
      selectedSpecRole: '',
      activeRoleMeta: null,
      activeArchonTiers: [],
      selectedSpecId: '',
      selectedWclDetail: null,
      activeWclRows: []
    }
  }

  const roles = Array.isArray(module.roles) ? module.roles : []
  const roleKey = roles.some((role) => role.key === preferredRole)
    ? preferredRole
    : (module.defaultRole || (roles[0] && roles[0].key) || 'dps')
  const summary = (module.archonTierSummary && module.archonTierSummary[roleKey]) || { tiers: [] }
  const activeRoleMeta = roles.find((role) => role.key === roleKey) || null
  const activeArchonTiers = (summary.tiers || []).map((tier) => ({
    ...tier,
    tierClass: `tier-label tier-${String(tier.tier || '').toLowerCase()}`,
    items: (tier.items || []).map((item) => {
      const gameAsset = normalizeGameAsset(item.gameAsset, {
        entityType: 'playable_spec',
        entityId: item.specId || `${item.classSlug || 'class'}-${item.specSlug || 'spec'}`,
        contextKey: `pve-spec-ladder:${roleKey}`,
        iconUrl: item.iconUrl || '',
        source: item.sourceName || 'legacy_icon_url',
        status: item.iconUrl ? 'fallback' : 'missing',
        semanticTags: ['game', 'pve', 'spec_ladder', roleKey, item.classSlug || '', item.specSlug || ''],
        usage: ['pve_spec_ladder', 'pve_detail'],
        fallbackText: item.fallbackText || item.specName || item.className || '?'
      })
      return {
        ...item,
        iconUrl: gameAsset.iconUrl,
        fallbackText: gameAsset.fallbackText,
        gameAsset,
        pillClass: item.specId === preferredSpecId ? 'spec-pill active' : 'spec-pill',
        iconStyle: `background-color: ${item.classColor || '#8e8e8e'};`
      }
    })
  }))
  const currentSpec = activeArchonTiers
    .flatMap((tier) => tier.items || [])
    .find((item) => item.specId === preferredSpecId) || firstSpecInTiers(activeArchonTiers)
  const selectedSpecId = currentSpec ? currentSpec.specId : ''
  const selectedWclDetail = selectedSpecId && module.wclDetailsBySpec
    ? module.wclDetailsBySpec[selectedSpecId]
    : null
  const preparedWclDetail = selectedWclDetail
    ? {
        ...selectedWclDetail,
        parsesText: selectedWclDetail.parsesText || formatNumber(selectedWclDetail.parses),
        distributionStyle: `width: ${Math.max(4, Math.min(100, Number(selectedWclDetail.distribution && selectedWclDetail.distribution.barPercent) || 0))}%;`
      }
    : null
  const activeSpecs = activeArchonTiers.flatMap((tier) => tier.items || [])
  const activeWclRows = activeSpecs
    .map((spec) => buildWclRow(spec, module.wclDetailsBySpec && module.wclDetailsBySpec[spec.specId], selectedSpecId))
    .filter((row) => row.role === roleKey || !row.role)

  return {
    isSpecLadder: true,
    specLadderRoles: roles.map((role) => ({
      ...role,
      tabClass: role.key === roleKey ? 'role-tab active' : 'role-tab'
    })),
    selectedSpecRole: roleKey,
    activeRoleMeta,
    activeArchonTiers: activeArchonTiers.map((tier) => ({
      ...tier,
      items: (tier.items || []).map((item) => ({
        ...item,
        pillClass: item.specId === selectedSpecId ? 'spec-pill active' : 'spec-pill'
      }))
    })),
    selectedSpecId,
    selectedWclDetail: preparedWclDetail,
    activeWclRows
  }
}

Page({
  data: {
    activeModule: fallbackPveModule('teamLadder'),
    loading: false,
    fromFallback: true,
    requestError: '',
    ...prepareSpecLadderState(fallbackPveModule('teamLadder'))
  },

  onLoad(options) {
    const moduleKey = options.module || 'teamLadder'
    const fallback = fallbackPveModule(moduleKey)
    this.analyticsStartedAt = Date.now()
    this.analyticsModuleKey = moduleKey
    trackPageView('pages/pve/detail', { moduleKey })
    trackEvent('pve_module_view', { moduleKey }, { page: 'pages/pve/detail' })
    this.setData({
      activeModule: fallback,
      ...prepareSpecLadderState(fallback)
    })
    this.loadModule(moduleKey)
  },

  onUnload() {
    trackPageLeave('pages/pve/detail', this.analyticsStartedAt, { moduleKey: this.analyticsModuleKey || '' })
  },

  loadModule(moduleKey) {
    this.setData({ loading: true })
    requestPveModule(moduleKey).then(({ payload, fromFallback, error }) => {
      this.setData({
        activeModule: payload,
        ...prepareSpecLadderState(payload, this.data.selectedSpecRole, this.data.selectedSpecId),
        fromFallback,
        requestError: error || ''
      })
    }).catch((error) => {
      this.setData({
        fromFallback: true,
        requestError: error && error.message ? error.message : 'request failed'
      })
    }).finally(() => {
      this.setData({ loading: false })
    })
  },

  selectSpecLadderRole(event) {
    const roleKey = event.currentTarget.dataset.role
    const nextState = prepareSpecLadderState(this.data.activeModule, roleKey, '')
    trackEvent('pve_spec_ladder_role_select', { roleKey: roleKey || '' }, { page: 'pages/pve/detail' })
    this.setData(nextState)
  },

  selectSpecLadderSpec(event) {
    const specId = event.currentTarget.dataset.spec
    const nextState = prepareSpecLadderState(this.data.activeModule, this.data.selectedSpecRole, specId)
    trackEvent('pve_spec_ladder_spec_select', { specId: specId || '' }, { page: 'pages/pve/detail' })
    this.setData(nextState)
  }
})

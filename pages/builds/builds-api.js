const {
  buildSpecializationHomePayload,
  buildSpecializationIntelPayload,
  getSpecializationDetail
} = require('../../server/builds/home-payload')
const { requestJson } = require('../common/api-client')

const FIRST_VERSION_QUERY_KEYS = ['talents', 'gear', 'simc', 'tasks']
const ACTION_META = {
  talents: {
    phaseLabel: '输入',
    actionLabel: '整理天赋',
    scopeLabel: '天赋树',
    evidenceLabel: 'WebSim / 模板',
    impactLabel: '决定构筑基础'
  },
  gear: {
    phaseLabel: '输入',
    actionLabel: '补齐装备',
    scopeLabel: '16 槽装备',
    evidenceLabel: '装备库 / 模板',
    impactLabel: '决定 SimC 可提交性'
  },
  simc: {
    phaseLabel: '验证',
    actionLabel: '模拟校验',
    scopeLabel: '固定模板',
    evidenceLabel: '天赋 + 装备',
    impactLabel: '生成可追踪任务'
  },
  tasks: {
    phaseLabel: '追踪',
    actionLabel: '查看任务',
    scopeLabel: '历史任务',
    evidenceLabel: 'SimC 结果',
    impactLabel: '继续复盘行动'
  }
}

function normalizeBuildsHomePayload(payload) {
  const fallback = rawFallbackBuildsHome()
  const home = payload || fallback
  const actions = Array.isArray(home.quickActions) ? home.quickActions : fallback.quickActions
  const filteredActions = actions.filter((action) => FIRST_VERSION_QUERY_KEYS.includes(action && action.key))
  const mergedActions = FIRST_VERSION_QUERY_KEYS.map((key) => {
    const action = filteredActions.find((item) => item && item.key === key) ||
      fallback.quickActions.find((action) => action && action.key === key)
    return action ? { ...action, ...(ACTION_META[key] || {}) } : null
  }).filter(Boolean)
  return {
    ...home,
    kicker: '职业控制台',
    quickActions: mergedActions,
    featuredSpecializations: []
  }
}

function rawFallbackBuildsHome() {
  return buildSpecializationHomePayload()
}

function fallbackBuildsHome() {
  return normalizeBuildsHomePayload(rawFallbackBuildsHome())
}

function fallbackBuildsIntel() {
  return buildSpecializationIntelPayload()
}

function fallbackBuildsDetail(specId) {
  return getSpecializationDetail(specId || '法师-冰霜')
}

function requestBuildsHome() {
  return requestJson('/api/builds/home', {
    fallback: fallbackBuildsHome,
    validate: (data) => data && data.navTitle && data.quickActions
  }).then((result) => {
    return {
      ...result,
      payload: normalizeBuildsHomePayload(result.payload)
    }
  })
}

function requestBuildsIntel() {
  return requestJson('/api/builds/intel', {
    fallback: fallbackBuildsIntel,
    validate: (data) => data && data.items
  })
}

function requestBuildsDetail(specId) {
  return requestJson(`/api/builds/detail?id=${encodeURIComponent(specId || '')}`, {
    fallback: () => fallbackBuildsDetail(specId),
    validate: (data) => data && data.id && data.details
  })
}

module.exports = {
  fallbackBuildsDetail,
  fallbackBuildsHome,
  fallbackBuildsIntel,
  requestBuildsDetail,
  requestBuildsHome,
  requestBuildsIntel
}

const {
  buildSpecializationHomePayload,
  buildSpecializationIntelPayload,
  getSpecializationDetail
} = require('../../server/builds/home-payload')
const { requestJson } = require('../common/api-client')

const FIRST_VERSION_QUERY_KEYS = ['talents', 'gear', 'simc', 'tasks']

function normalizeBuildsHomePayload(payload) {
  const fallback = fallbackBuildsHome()
  const home = payload || fallback
  const actions = Array.isArray(home.quickActions) ? home.quickActions : fallback.quickActions
  const filteredActions = actions.filter((action) => FIRST_VERSION_QUERY_KEYS.includes(action && action.key))
  const mergedActions = FIRST_VERSION_QUERY_KEYS.map((key) => {
    return filteredActions.find((action) => action && action.key === key) ||
      fallback.quickActions.find((action) => action && action.key === key)
  }).filter(Boolean)
  return {
    ...home,
    quickActions: mergedActions,
    featuredSpecializations: []
  }
}

function fallbackBuildsHome() {
  return buildSpecializationHomePayload()
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

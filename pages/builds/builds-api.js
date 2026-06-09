const {
  buildSpecializationHomePayload,
  buildSpecializationIntelPayload,
  getSpecializationDetail
} = require('../../server/builds/home-payload')
const { requestJson } = require('../common/api-client')

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

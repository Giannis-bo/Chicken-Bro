const { buildPveHomePayload, getPveModuleDetail } = require('../../server/pve/home-payload')
const { requestJson } = require('../common/api-client')

function fallbackPveHome() {
  return buildPveHomePayload()
}

function fallbackPveModule(moduleKey) {
  return getPveModuleDetail(moduleKey || 'teamLadder')
}

function requestPveHome() {
  return requestJson('/api/pve/home', {
    fallback: fallbackPveHome,
    validate: (data) => data && data.navTitle && data.zones
  })
}

function requestPveModule(moduleKey) {
  return requestJson(`/api/pve/module?key=${encodeURIComponent(moduleKey || 'teamLadder')}`, {
    fallback: () => fallbackPveModule(moduleKey),
    validate: (data) => data && data.key && data.items
  })
}

module.exports = {
  fallbackPveHome,
  fallbackPveModule,
  requestPveHome,
  requestPveModule
}

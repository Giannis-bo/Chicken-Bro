const { buildPveHomePayload, getPveModuleDetail } = require('../../server/pve/home-payload')
const { requestJson } = require('../common/api-client')

function fallbackPveHome() {
  return buildPveHomePayload()
}

function fallbackPveModule(moduleKey) {
  return getPveModuleDetail(moduleKey || 'teamLadder')
}

function hasCompleteSpecLadderPayload(data) {
  if (!data || data.key !== 'specLadder') return false
  if (!Array.isArray(data.items)) return false
  if (!Array.isArray(data.roles)) return false
  if (!data.archonTierSummary || !data.wclDetailsBySpec) return false
  if (!Array.isArray(data.sourceChecks)) return false

  const roleKeys = data.roles.map((role) => role.key)
  const requiredRoles = ['dps', 'tank', 'healer']
  const hasRoles = requiredRoles.every((roleKey) => roleKeys.includes(roleKey))
  const hasTierData = requiredRoles.every((roleKey) => {
    const summary = data.archonTierSummary[roleKey]
    return summary && Array.isArray(summary.tiers) && summary.tiers.some((tier) => Array.isArray(tier.items) && tier.items.length)
  })
  const hasWclData = Object.keys(data.wclDetailsBySpec).length > 0
  const hasSources = ['archon', 'warcraftlogs'].every((sourceKey) => data.sourceChecks.some((source) => source.key === sourceKey))

  return hasRoles && hasTierData && hasWclData && hasSources
}

function validatePveModulePayload(data, moduleKey) {
  if (!data || !data.key || !Array.isArray(data.items)) return false
  if (moduleKey && data.key !== moduleKey) return false
  if (data.key === 'specLadder') return hasCompleteSpecLadderPayload(data)
  return true
}

function hasRenderablePveHomePayload(data) {
  if (!data || !data.navTitle || !Array.isArray(data.zones)) return false
  return data.zones.some((zone) => Array.isArray(zone.modules) && zone.modules.length > 0)
}

function requestPveHome() {
  return requestJson('/api/pve/home', {
    fallback: fallbackPveHome,
    validate: hasRenderablePveHomePayload
  })
}

function requestPveModule(moduleKey) {
  const normalizedModuleKey = moduleKey || 'teamLadder'
  return requestJson(`/api/pve/module?key=${encodeURIComponent(normalizedModuleKey)}`, {
    fallback: () => fallbackPveModule(normalizedModuleKey),
    validate: (data) => validatePveModulePayload(data, normalizedModuleKey)
  })
}

module.exports = {
  fallbackPveHome,
  fallbackPveModule,
  hasCompleteSpecLadderPayload,
  hasRenderablePveHomePayload,
  requestPveHome,
  requestPveModule,
  validatePveModulePayload
}

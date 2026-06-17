const { requestJson } = require('../common/api-client')

function fallbackWebsimBootstrap() {
  return {
    navTitle: 'WebSim',
    classes: [],
    scenarios: [],
    gearSlots: [],
    defaultSelection: { classKey: 'mage', specKey: 'frost' },
    currentSeason: {
      dataStatus: 'blocked',
      errors: ['missing api base url']
    },
    dataStatus: 'blocked'
  }
}

function fallbackWebsimTalents(params) {
  const options = params || {}
  return {
    classKey: options.classKey || 'mage',
    specKey: options.specKey || 'frost',
    heroKey: options.heroKey || '',
    nodes: [],
    treeSections: [],
    presets: [],
    communityTemplates: [],
    communityTemplateSync: {
      sourceStatus: 'missing_credentials',
      sources: {},
      templates: { total: 0, verified: 0, blocked: 0 }
    },
    talentStatus: 'blocked',
    currentSeason: {
      dataStatus: 'blocked',
      errors: ['missing api base url']
    },
    errors: ['missing api base url']
  }
}

function fallbackWebsimProfile() {
  return {
    profile: '',
    profileStatus: 'blocked',
    talentEncoding: {
      status: 'failed',
      lines: [],
      errors: ['backend unavailable']
    }
  }
}

function requestWebsimBootstrap() {
  return requestJson('/api/websim/bootstrap', {
    fallback: fallbackWebsimBootstrap,
    validate: (data) => data && Array.isArray(data.classes)
  })
}

function requestWebsimTalents(params) {
  const options = params || {}
  const query = [
    `class=${encodeURIComponent(options.classKey || '')}`,
    `spec=${encodeURIComponent(options.specKey || '')}`
  ]
  if (options.heroKey) query.push(`hero=${encodeURIComponent(options.heroKey)}`)
  return requestJson(`/api/websim/talents?${query.join('&')}`, {
    fallback: () => fallbackWebsimTalents(options),
    validate: (data) => data && Array.isArray(data.nodes) && Array.isArray(data.treeSections)
  })
}

function requestWebsimProfile(payload) {
  return requestJson('/api/websim/profile', {
    method: 'POST',
    data: payload || {},
    timeout: 30000,
    fallback: fallbackWebsimProfile,
    validate: (data) => data && data.talentEncoding
  })
}

module.exports = {
  fallbackWebsimBootstrap,
  fallbackWebsimProfile,
  fallbackWebsimTalents,
  requestWebsimBootstrap,
  requestWebsimProfile,
  requestWebsimTalents
}

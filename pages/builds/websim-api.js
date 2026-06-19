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

function fallbackWebsimGear(params) {
  const options = params || {}
  return {
    classKey: options.classKey || 'mage',
    specKey: options.specKey || 'frost',
    slots: [],
    slotGroups: [],
    baselineSet: [],
    equippedSet: {},
    slotReadiness: {},
    replacementCandidates: [],
    readiness: {
      fullReady: false,
      itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
      warnings: ['backend unavailable']
    },
    statSnapshot: fallbackWebsimGearStats(options),
    gearSchemaRevision: 'websim-gear-simulator-v1',
    gearCatalogRevision: 'websim-gear-catalog-v1',
    catalogStatus: 'blocked',
    itemDatabaseRevision: '',
    variantRevision: '',
    catalogCheckedAt: '',
    catalogBlockers: ['backend unavailable'],
    maxLevel: 0,
    checkedAt: '',
    dataStatus: 'blocked'
  }
}

function fallbackWebsimGearStats(params) {
  const options = params || {}
  return {
    classKey: options.classKey || 'mage',
    specKey: options.specKey || 'frost',
    statStatus: 'blocked',
    blockers: ['backend unavailable'],
    primary: null,
    stamina: null,
    secondary: [],
    armor: null,
    weaponDps: null,
    itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
    gearReadiness: {
      fullReady: false,
      itemLevel: { key: 'itemLevel', label: '装备等级', value: '0', rawValue: 0 },
      warnings: ['backend unavailable']
    },
    talentEncoding: {
      status: 'failed',
      lines: [],
      errors: ['backend unavailable']
    },
    gearSchemaRevision: 'websim-gear-simulator-v1',
    maxLevel: 0,
    checkedAt: ''
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

function requestWebsimGear(params) {
  const options = params || {}
  const query = [
    `class=${encodeURIComponent(options.classKey || '')}`,
    `spec=${encodeURIComponent(options.specKey || '')}`
  ]
  return requestJson(`/api/websim/gear?${query.join('&')}`, {
    fallback: () => fallbackWebsimGear(options),
    validate: (data) => data && Array.isArray(data.slots) && data.equippedSet && data.readiness
  })
}

function requestWebsimGearStats(payload) {
  const source = payload || {}
  return requestJson('/api/websim/gear/stats', {
    method: 'POST',
    data: source,
    timeout: 60000,
    fallback: () => fallbackWebsimGearStats(source),
    validate: (data) => data && data.statStatus && Array.isArray(data.blockers)
  })
}

module.exports = {
  fallbackWebsimBootstrap,
  fallbackWebsimGear,
  fallbackWebsimGearStats,
  fallbackWebsimProfile,
  fallbackWebsimTalents,
  requestWebsimBootstrap,
  requestWebsimGear,
  requestWebsimGearStats,
  requestWebsimProfile,
  requestWebsimTalents
}
